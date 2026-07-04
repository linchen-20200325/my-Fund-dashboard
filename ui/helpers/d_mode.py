"""ui/helpers/d_mode.py — v18.239 D 模式（C 轉換再平衡的「跨保單買方候選」）helper

抽出來成獨立模組，理由：
- 純函式 + lazy import → 不會把 bs4 / streamlit / fund_repository 等重依賴
  拖進 module load（讓單元測試環境無 bs4 也能跑）
- caller `ui/tab3_t7_ledger.py:render_t7_section` 內 import + 呼叫

D 模式 use case：
1. **跨保單借**：其他保單已有的基金當買方候選（秒成、免抓 NAV）
2. **全新基金**：不在任何保單內，用 MoneyDJ 代碼自動抓 NAV/FX/配息

v18.234 原 bug 復原（NoneType subscript）：本 fetch helper 保證 dict schema
完整、所有外部 fetch 例外都安全降級 ok=False。
"""
from __future__ import annotations


def fetch_fund_meta_safe(code: str, _fetch=None, _fx_lookup=None,
                          _existing=None) -> dict:
    """從 MoneyDJ + 多源抓基金 metadata，**永遠回完整 schema 的 dict**。

    Args:
        code: 基金代碼
        _fetch: 注入式 fetcher（測試用），None → lazy import
                `fund_fetcher.fetch_fund_from_moneydj_url`（v18.241 改用主流程）
        _fx_lookup: 注入式 FX 查詢（測試用），None → lazy import
                    `fund_fetcher.get_latest_fx`
        _existing: v18.242 in-session cache。dict[code → fund_dict]，
                   code 命中且 series 有效 → 秒回不再呼叫 fetcher。
                   fund_dict 期待 schema：name/currency/series/dividends/
                   fx_avg(或 fx_rate)/policy_id。

    Returns:
        {
          "ok":         bool,
          "fund_name":  str,
          "currency":   str (upper, default "USD"),
          "nav":        float (series.iloc[-1]),
          "fx":         float (currency→TWD; TWD=1.0; 查失敗 fallback 31.0),
          "series":     pd.Series (dropna 後；ok=False 時為空 series),
          "dividends":  list,
          "error":      str (ok=False 時的原因),
        }

    任何 fetcher 異常 / 非 dict / 缺欄 / series=None 都不會拋例外、
    不會「'NoneType' object is not subscriptable」(v18.234 原 bug)。
    """
    import pandas as pd  # noqa: PLC0415

    out: dict = {
        "ok": False, "fund_name": "", "currency": "USD",
        "nav": 0.0, "fx": 31.0,
        "series": pd.Series(dtype=float), "dividends": [],
        "error": "",
    }
    _code = str(code or "").strip().upper()
    if not _code:
        out["error"] = "代碼為空"
        return out

    # v18.242: 先查 in-session cache（user 反饋「曾經抓過的不需要重複抓取」）
    if _existing:
        _hit = _existing.get(_code)
        if _hit is not None:
            try:
                _hs = _hit.get("series")
                if _hs is not None and hasattr(_hs, "dropna"):
                    _hs = _hs.dropna()
                    if len(_hs) > 0:
                        _ccy = str(_hit.get("currency") or "USD").upper().strip()
                        _fx = _hit.get("fx_avg") or _hit.get("fx_rate") or 0
                        out.update({
                            "ok": True,
                            "fund_name": (str(_hit.get("name") or "").strip()
                                          or _code),
                            "currency": _ccy,
                            "nav": float(_hs.iloc[-1]),
                            "fx": (1.0 if _ccy == "TWD"
                                   else (float(_fx) if _fx and float(_fx) > 0
                                         else 31.0)),
                            "series": _hs,
                            "dividends": list(_hit.get("dividends") or []),
                            # v18.246: 帶 metrics + moneydj_raw 給 _get_dy_t7
                            "metrics": dict(_hit.get("metrics") or {}),
                            "moneydj_raw": dict(_hit.get("moneydj_raw") or {}),
                            "from_cache": True,
                            "cache_pid": str(_hit.get("policy_id") or ""),
                        })
                        return out
            except Exception:
                pass  # 任何錯誤都安全 fallback 到網路 fetch

    try:
        if _fetch is None:
            # v18.241: 改用主流程 entry point fetch_fund_from_moneydj_url
            # —— user 質疑「為什麼不重用本來就有的抓取」。原本直 call
            # fetch_fund_multi_source 缺 mapping 預查 + normalize 容錯，
            # ACCP138 走多源時某 fetcher 漏防護 None。改用 high-level entry
            # 自動帶 mapping → page_type、保 meta、normalize_result_state。
            # v19.307: 改走 L2 enriched wrapper —— raw 版 metrics 永遠 {}，
            # 導致本函式 out["metrics"]（T7 配息殖利率用）恆空 → dy=0。
            from services.fund_service import (
                fetch_fund_from_moneydj_url_enriched as _fetch,
            )
        _r = _fetch(_code)
    except Exception as _e:
        # v18.240: 把 traceback 最內層 frame 帶到 error 訊息（root cause 定位用）
        import traceback  # noqa: PLC0415
        _frames = traceback.extract_tb(_e.__traceback__)
        _last = _frames[-1] if _frames else None
        _loc = (f"{_last.filename.rsplit('/', 1)[-1]}:{_last.lineno}"
                f" in {_last.name}") if _last else ""
        out["error"] = f"抓取例外：{type(_e).__name__}: {_e}" + (
            f"（at {_loc}）" if _loc else "")
        return out
    if not isinstance(_r, dict):
        out["error"] = f"回傳非 dict（{type(_r).__name__}）"
        return out

    # series 防呆：None / list / Series 都要安全處理
    _s = _r.get("series")
    try:
        if _s is None:
            _s = pd.Series(dtype=float)
        elif not isinstance(_s, pd.Series):
            _s = pd.Series(_s) if _s else pd.Series(dtype=float)
        _s = _s.dropna()
    except Exception:
        _s = pd.Series(dtype=float)
    if len(_s) == 0:
        out["error"] = "抓不到 NAV 序列"
        return out

    out["series"] = _s
    try:
        out["nav"] = float(_s.iloc[-1])
    except Exception:
        out["error"] = "NAV 末值解析失敗"
        return out
    out["fund_name"] = (str(_r.get("fund_name") or _r.get("name") or "").strip()
                          or _code)
    out["currency"] = str(_r.get("currency") or "USD").strip().upper()
    out["dividends"] = list(_r.get("dividends") or [])
    # v18.246: 帶 metrics + moneydj_raw 給 _get_dy_t7（沒這兩個 key → dy = 0）
    out["metrics"] = dict(_r.get("metrics") or {})
    _mj = (_r.get("moneydj_raw")
           or {"moneydj_div_yield": _r.get("moneydj_div_yield")})
    out["moneydj_raw"] = dict(_mj or {})

    if out["currency"] == "TWD":
        out["fx"] = 1.0
    else:
        try:
            if _fx_lookup is None:
                from services.fund_service import get_latest_fx as _fx_lookup
            _fxv = _fx_lookup(f"{out['currency']}TWD")
            out["fx"] = float(_fxv) if (_fxv and _fxv > 0) else 31.0
        except Exception:
            out["fx"] = 31.0
    out["ok"] = True
    return out
