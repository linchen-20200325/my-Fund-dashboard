"""repositories/fund/fx_and_main.py — v19.200 P1-5 fetch_fund_by_* + FX/NAV helper。

從 fund_repository 主檔抽出(原 line 4547-5117):
- fetch_fund_by_key / fetch_fund_by_code
- get_latest_fx / _clear_fx_cache / diagnose_fx_sources / get_latest_nav
(v19.242 R10:fetch_fund_structure + _parse_pct_table dead chain 退役 0 production caller)
"""
from __future__ import annotations

import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

from infra.cache import (  # noqa: F401
    _ttl_cache, register_cache, _CACHE_DIR, _FUND_SNAPSHOT, _cache_path,
    _cache_load_nav, _cache_save_nav, _cache_load_div, _cache_save_div,
    _cache_load_meta, _cache_save_meta,
)
from shared.fred_series import FRED_CHF_USD, FRED_CNH_USD, FRED_EUR_USD, FRED_JPY_USD
from shared.ttls import TTL_5MIN, TTL_15MIN, TTL_30MIN
from fund_fetcher import (  # noqa: F401
    safe_float, fetch_url_with_retry, is_valid_moneydj_page,
    HDR, HDR_JSON, PORTAL_CFG, TCB_BASE, _INSURANCE_SUBDOMAIN_HINTS,
    normalize_result_state, merge_non_empty, classify_fetch_status,
)
from infra.proxy import _proxies, _ssl_verify  # noqa: F401
# v19.240 R8 EX-L1ORCH-1 退役:calc_metrics + perf 注入 + reconcile 業務邏輯已上提
# 至 services.fund_service.finalize_fund_metrics + L2 enriched wrapper
# (fetch_fund_by_key_enriched)。本層只回 raw result(無 metrics key,caller 走 L2
# wrapper 才會 enrich)。

from repositories.fund.sources import *  # noqa: F401, F403
from repositories.fund.nav_metrics import *  # noqa: F401, F403


# ════════════════════════════════════════════════════════════
def fetch_fund_by_key(full_key: str, fund_name: str = "",
                      portal: str = "", source: str = "",
                      manual_nav_csv: str = "") -> dict:
    """用已知的 full_key 取完整分析資料"""
    result = dict(
        full_key=full_key, fund_name=fund_name, portal=portal,
        series=None, dividends=[], metrics={}, error=None,
    )
    # 先嘗試鉅亨網（Colab 友善），再 MoneyDJ
    s = pd.Series(dtype=float)
    if (source == 'cnyes') or (len(full_key) < 8 and '-' not in full_key):
        s = fetch_nav_cnyes(full_key)
    if len(s) < 20:
        s = fetch_nav(full_key, portal)
    if len(s) < 20 and manual_nav_csv.strip():
        rows = []
        for line in manual_nav_csv.strip().split("\n"):
            parts = line.strip().split(",")
            if len(parts) >= 2:
                try: rows.append((pd.to_datetime(parts[0].strip()),float(parts[1].strip())))
                except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
        if len(rows) >= 20:
            s = pd.Series({r[0]:r[1] for r in rows}).sort_index()
    # 配息：cnyes 或 MoneyDJ
    if (source == 'cnyes') and len(full_key) < 8:
        divs = fetch_div_cnyes(full_key) if len(s) >= 5 else []
    else:
        divs = fetch_div(full_key, portal) if len(s) >= 5 else []
    if not divs and len(s) >= 5:
        divs = fetch_div(full_key, portal)
    if len(s) >= 20:
        result["series"]    = s
        result["dividends"] = divs
        # v19.240 R8 EX-L1ORCH-1 退役:metrics + perf 注入由 L2
        # services.fund_service.fetch_fund_by_key_enriched 統一處理。
        # F-PROV-1 phase 17 v19.103 — provenance(orchestrator-level;若 series 已有 attrs.source 則記錄)
        _s_src = s.attrs.get("source") if hasattr(s, "attrs") else None
        result["nav_source_used"] = _s_src or "unknown"
        result["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    else:
        result["error"] = f"{full_key} 只取到 {len(s)} 筆淨值（需≥20）"
    return result


# 保留相容性（舊 main.py 呼叫）
def fetch_fund_by_code(insurance_code: str, gemini_key: str = "",
                       manual_full_key: str = "",
                       manual_nav_csv: str = "") -> dict:
    """相容舊介面：直接用 insurance_code 當 full_key

    Provenance(C2 v19.208 F-PROV-1):pass-through fetch_fund_by_key,結果
    dict 已含 'source' + 'nav_source_used' + 'fetched_at'(§2.2 schema-additive)。
    """
    key = manual_full_key.strip().upper() if manual_full_key.strip() else insurance_code.strip().upper()
    return fetch_fund_by_key(key, manual_nav_csv=manual_nav_csv)






# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：Universal Ledger: get_latest_fx / get_latest_nav (yfinance auto-FX/NAV)
# ════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# Universal Ledger v1.0 — auto FX / NAV (yfinance 為主，舊來源 fallback)
# 對外契約：
#   get_latest_fx("USDTWD=X") -> float | None
#   get_latest_nav("VWO")     -> float | None
# ══════════════════════════════════════════════════════════════════════

# v18.275：手動 positive-only cache（避免 None 被 5min TTL 鎖住）
# 經 user Tab5 診斷證實：Yahoo + er-api 都能拿到值（31.29 / 31.48），但 Tab2
# widget 仍顯示「都暫無」是因為 @_ttl_cache 把更早一次失敗的 None 鎖了 5 分鐘。
# 改為手動字典 cache：只快取正值，None 不入 cache → 下次仍重試。
_FX_CACHE: dict[tuple[str, str], tuple[float, float]] = {}   # (pair, key_hash) -> (timestamp, rate)
_FX_CACHE_TTL = 300.0


class _FxCacheProxy:
    """v19.201 P2-6:把 `_FX_CACHE` raw dict 包裝為符合 `_CACHE_REGISTRY` 介面的 proxy。

    既保留 v18.275 positive-only 設計(None 不入 cache 避免 poisoning)又能受
    `clear_all_caches()` 一鍵清(過去 `_FX_CACHE` 漏網,只能個別呼叫 `_clear_fx_cache()`)。
    """
    __name__ = "_FX_CACHE"

    @staticmethod
    def cache_clear() -> None:
        _FX_CACHE.clear()

    @staticmethod
    def cache_info() -> dict:
        return {"name": "_FX_CACHE", "currsize": len(_FX_CACHE), "ttl": _FX_CACHE_TTL}


register_cache(_FxCacheProxy())


def get_latest_fx(currency_pair: str, fred_api_key: str = "") -> "float | None":
    """抓最新匯率（v18.275 精簡版）。

    Chain：
        TWD pair (USDTWD / EURTWD / JPYTWD ...): Yahoo → open.er-api（兩個都實測可用）
        非 TWD pair (EURUSD / JPYEUR ...): Yahoo → FRED DEX* → open.er-api → Frankfurter

    User 反饋 v18.273 後 FRED DEXTWUS 已停發、Frankfurter ECB 無 TWD 報價，
    對主流 USD/TWD 場景全是 dead path。本版本對 TWD pair 直接跳過 FRED / Frankfurter
    （也呼應 user「移除無法用的連線，只保留能用的」）。

    None poisoning 防護：positive-only 手動快取。

    Args:
        currency_pair: 例 "USDTWD=X" 或 "USDTWD"（補 =X）
        fred_api_key: FRED API key（給非 TWD pair fallback 用）

    Returns:
        rate (float > 0) 或 None；None 不會被快取。
    """
    import time as _t_fx
    if not currency_pair:
        return None
    pair = str(currency_pair).strip().upper()
    if not pair.endswith("=X"):
        pair = pair + "=X"

    # positive-only cache 查詢
    _cache_key = (pair, fred_api_key or "")
    _hit = _FX_CACHE.get(_cache_key)
    if _hit and (_t_fx.time() - _hit[0]) < _FX_CACHE_TTL:
        return _hit[1]

    # 解 ccy_base / ccy_quote：前 3 / 後 3 碼
    _stripped = pair.replace("=X", "")
    _ccy_base = _stripped[:3] if len(_stripped) >= 6 else _stripped
    _ccy_quote = _stripped[3:] if len(_stripped) >= 6 else ""
    _is_twd = "TWD" in (_ccy_base, _ccy_quote)

    def _store(rate: float) -> float:
        _FX_CACHE[_cache_key] = (_t_fx.time(), rate)
        return rate

    # 1. Yahoo Chart API (走 NAS proxy via fetch_yf_close 既有路徑)
    try:
        from repositories.macro_repository import fetch_yf_close as _yf_close
        _s = _yf_close(pair, range_="5d", interval="1d")
        if _s is not None and not _s.empty:
            v = float(_s.dropna().iloc[-1])
            if v > 0:
                return _store(v)
    except Exception as _e:
        print(f"[get_latest_fx] Yahoo {pair}: {_e}")

    # 2. FRED DEX* — 只跑非 TWD pair（DEXTWUS 已停發，所有 TWD 終點都死了）
    if (not _is_twd) and fred_api_key:
        _FRED_FX_MAP = {
            ("JPY", "USD"): (FRED_JPY_USD, False),
            ("CHF", "USD"): (FRED_CHF_USD, False),
            ("CNH", "USD"): (FRED_CNH_USD, False),
            ("CNY", "USD"): (FRED_CNH_USD, False),
            ("EUR", "USD"): (FRED_EUR_USD, "inv"),  # series 是 USD per EUR
        }
        _spec = _FRED_FX_MAP.get((_ccy_base, _ccy_quote))
        if _spec:
            _series_id, _mode = _spec
            try:
                from repositories.macro_repository import fetch_fred as _fred
                _df = _fred(_series_id, fred_api_key, n=10)
                if _df is not None and not _df.empty:
                    _val = float(_df.iloc[-1]["value"])
                    if _val > 0:
                        if _mode == "inv":
                            return _store(1.0 / _val)
                        return _store(_val)
            except Exception as _e:
                print(f"[get_latest_fx] FRED {_series_id}: {_e}")

    # 3. open.er-api.com (TWD pair 與其他 pair 都支援，免 auth)
    import requests as _req_fx
    try:
        from infra.proxy import get_proxy_config as _gp_fx
        _proxies_fx = _gp_fx() or {}
    except Exception:
        _proxies_fx = {}

    if _ccy_base and _ccy_quote and _ccy_base != _ccy_quote:
        try:
            _r = _req_fx.get(
                f"https://open.er-api.com/v6/latest/{_ccy_base}",
                proxies=_proxies_fx, timeout=15, verify=False,
            )
            if _r.status_code == 200:
                _d = _r.json()
                if _d.get("result") == "success":
                    _v = float(_d.get("rates", {}).get(_ccy_quote, 0) or 0)
                    if _v > 0:
                        return _store(_v)
        except Exception as _e:
            print(f"[get_latest_fx] open.er-api {_ccy_base}: {_e}")

    # 4. Frankfurter (ECB) — 非 TWD pair 才用（ECB 沒有 TWD）
    if (not _is_twd) and _ccy_base and _ccy_quote and _ccy_base != _ccy_quote:
        try:
            _r = _req_fx.get(
                "https://api.frankfurter.app/latest",
                params={"from": _ccy_base, "to": _ccy_quote},
                proxies=_proxies_fx, timeout=15, verify=False,
            )
            if _r.status_code == 200:
                _d = _r.json()
                _v = float(_d.get("rates", {}).get(_ccy_quote, 0) or 0)
                if _v > 0:
                    return _store(_v)
        except Exception as _e:
            print(f"[get_latest_fx] Frankfurter {_ccy_base}/{_ccy_quote}: {_e}")
    # 注意：None 不入 cache → 下次仍會 retry
    return None


def _clear_fx_cache() -> None:
    """測試 / 強制刷新用：清空 positive-only cache。"""
    _FX_CACHE.clear()


def diagnose_fx_sources(currency_pair: str, fred_api_key: str = "") -> dict:
    """逐一試 FX 來源，回傳每個 source 的狀態（給 Tab5 資料診斷用）。

    v18.275 改動：對 TWD pair 只回傳 Yahoo + er_api（FRED DEXTWUS 停發 / ECB 無 TWD，
    對 TWD pair 兩個都是 dead path）— user 反饋「移除無法用的連線，只保留能用的」。

    Returns:
        dict — 各 source 一個 key（TWD pair 只含 yahoo + er_api；其他 pair 含 4 個）。
        每個 value 為 dict: {ok: bool, rate: float|None, error: str|None, note: str}
    """
    if not currency_pair:
        return {}
    pair = str(currency_pair).strip().upper()
    if not pair.endswith("=X"):
        pair = pair + "=X"
    _stripped = pair.replace("=X", "")
    _ccy_base = _stripped[:3] if len(_stripped) >= 6 else _stripped
    _ccy_quote = _stripped[3:] if len(_stripped) >= 6 else ""
    _is_twd = "TWD" in (_ccy_base, _ccy_quote)

    out: dict = {
        "yahoo":       {"ok": False, "rate": None, "error": None, "note": "Yahoo Chart API + NAS proxy"},
        "er_api":      {"ok": False, "rate": None, "error": None, "note": "open.er-api.com（免 auth，支援 150+ 幣別含 TWD）"},
    }
    if not _is_twd:
        out["fred"] = {"ok": False, "rate": None, "error": None, "note": "FRED DEX* series"}
        out["frankfurter"] = {"ok": False, "rate": None, "error": None, "note": "Frankfurter ECB"}

    # 1. Yahoo
    try:
        from repositories.macro_repository import fetch_yf_close as _yf_close
        _s = _yf_close(pair, range_="5d", interval="1d")
        if _s is not None and not _s.empty:
            v = float(_s.dropna().iloc[-1])
            if v > 0:
                out["yahoo"]["ok"] = True
                out["yahoo"]["rate"] = v
            else:
                out["yahoo"]["error"] = "series 空或值 ≤ 0"
        else:
            out["yahoo"]["error"] = "Yahoo Chart API 回空 series"
    except Exception as e:
        out["yahoo"]["error"] = str(e)[:80]

    # 2. FRED (僅非 TWD pair；TWD pair 不顯示此欄)
    if "fred" in out:
        if not fred_api_key:
            out["fred"]["error"] = "未設定 FRED_API_KEY"
        else:
            _FRED_FX_MAP = {
                ("JPY", "USD"): FRED_JPY_USD,
                ("CHF", "USD"): FRED_CHF_USD,
                ("CNH", "USD"): FRED_CNH_USD,
                ("CNY", "USD"): FRED_CNH_USD,
                ("EUR", "USD"): FRED_EUR_USD,
            }
            _series_id = _FRED_FX_MAP.get((_ccy_base, _ccy_quote))
            if not _series_id:
                out["fred"]["error"] = f"{_ccy_base}/{_ccy_quote} 未在 FRED FX map"
            else:
                try:
                    from repositories.macro_repository import fetch_fred as _fred
                    _df = _fred(_series_id, fred_api_key, n=10)
                    if _df is None or _df.empty:
                        out["fred"]["error"] = f"FRED {_series_id} 回空"
                    else:
                        out["fred"]["ok"] = True
                        out["fred"]["rate"] = float(_df.iloc[-1]["value"])
                except Exception as e:
                    out["fred"]["error"] = str(e)[:80]

    # v18.273: er-api / Frankfurter 改用 requests.get 直連 proxy（同 sidebar 測試 path）
    import requests as _req_dx
    try:
        from infra.proxy import get_proxy_config as _gp_dx
        _proxies_dx = _gp_dx() or {}
    except Exception:
        _proxies_dx = {}

    # 3. open.er-api.com
    if not _ccy_base or not _ccy_quote or _ccy_base == _ccy_quote:
        out["er_api"]["error"] = "pair 解析失敗"
    else:
        try:
            _r = _req_dx.get(
                f"https://open.er-api.com/v6/latest/{_ccy_base}",
                proxies=_proxies_dx, timeout=15, verify=False,
            )
            if _r.status_code != 200:
                out["er_api"]["error"] = f"HTTP {_r.status_code}"
            else:
                _d = _r.json()
                if _d.get("result") != "success":
                    out["er_api"]["error"] = f"API 回 result={_d.get('result')}"
                else:
                    _v = float(_d.get("rates", {}).get(_ccy_quote, 0) or 0)
                    if _v > 0:
                        out["er_api"]["ok"] = True
                        out["er_api"]["rate"] = _v
                    else:
                        out["er_api"]["error"] = f"{_ccy_quote} 不在 rates 或值為 0"
        except Exception as e:
            out["er_api"]["error"] = str(e)[:80]

    # 4. Frankfurter (僅非 TWD pair；TWD pair 不顯示此欄)
    if "frankfurter" in out:
        if not _ccy_base or not _ccy_quote:
            out["frankfurter"]["error"] = "pair 解析失敗"
        else:
            try:
                _r = _req_dx.get(
                    "https://api.frankfurter.app/latest",
                    params={"from": _ccy_base, "to": _ccy_quote},
                    proxies=_proxies_dx, timeout=15, verify=False,
                )
                if _r.status_code != 200:
                    out["frankfurter"]["error"] = f"HTTP {_r.status_code}"
                else:
                    _d = _r.json()
                    _v = float(_d.get("rates", {}).get(_ccy_quote, 0) or 0)
                    if _v > 0:
                        out["frankfurter"]["ok"] = True
                        out["frankfurter"]["rate"] = _v
                    else:
                        out["frankfurter"]["error"] = f"{_ccy_quote} 不在 rates 或值為 0"
            except Exception as e:
                out["frankfurter"]["error"] = str(e)[:80]

    return out


@register_cache
@_ttl_cache(ttl_sec=TTL_5MIN, maxsize=128)   # v18.58: T7 每 fund render 一次
def get_latest_nav(fund_ticker: str) -> "float | None":
    """抓基金最新淨值。yfinance 為主，本檔既有 Morningstar / Cnyes 來源 fallback。

    回傳：最新淨值 (float)，全部失敗回 None。呼叫端不得自行偽造。
    """
    if not fund_ticker:
        return None
    code = str(fund_ticker).strip().upper()

    # 1) [Auto-Fixed v18.201] Yahoo Chart REST API + NAS proxy（取代直連 yfinance，
    #    避免 Cloud IP 403/限流）；lazy import 避免循環依賴。
    try:
        from repositories.macro_repository import fetch_yf_close as _yf_close
        _s = _yf_close(code, range_="5d", interval="1d")
        if _s is not None and not _s.empty:
            v = float(_s.dropna().iloc[-1])
            if v > 0:
                return v
    except Exception as _e:
        print(f"[get_latest_nav/yf] {code}: {_e}")

    # 2) Yahoo chart（_MORNINGSTAR_SECID_MAP 有 secId 才會命中）
    try:
        s = _src_yahoo_finance_nav(code)
        if s is not None and len(s.dropna()) > 0:
            return float(s.dropna().iloc[-1])
    except Exception as _e:
        print(f"[get_latest_nav/yh] {code}: {_e}")

    # 3) Cnyes（台灣境外/境內基金）
    try:
        s = _src_cnyes_nav(code)
        if s is not None and len(s.dropna()) > 0:
            return float(s.dropna().iloc[-1])
    except Exception as _e:
        print(f"[get_latest_nav/cnyes] {code}: {_e}")

    # 4) Morningstar（最後一路）
    try:
        s = _src_morningstar_nav(code)
        if s is not None and len(s.dropna()) > 0:
            return float(s.dropna().iloc[-1])
    except Exception as _e:
        print(f"[get_latest_nav/ms] {code}: {_e}")

    return None
