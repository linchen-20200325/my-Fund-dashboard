"""repositories/fund/fund_orchestration.py — v19.200 P1-5 主編排 + search。

從 fund_repository 主檔抽出(原 line 2452-3554):
- _fetch_fund_single / _finish_metrics
- fetch_fund_from_moneydj_url
- search_fundclear / search_moneydj_by_name / _parse_nav_html

(fetch_fund_multi_source 留在 sources.py,邏輯上是 source dispatcher。)
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
# v19.240 R8 EX-L1ORCH-1 退役:calc_metrics + reconcile + perf 注入業務邏輯已上提
# 至 services.fund_service.finalize_fund_metrics + 2 enriched wrapper。本層
# 只回 raw result(metrics 由 L2 wrapper 補)。

from repositories.fund.sources import *  # noqa: F401, F403 — 所有 _src_* re-export


def _fetch_fund_single(code: str, force_refresh: bool = False,
                       page_type: str = "") -> dict:
    """單一代碼的多來源抓取（由 fetch_fund_multi_source 呼叫）"""
    _code = code.upper().strip()
    _page_type = page_type or (
        "yp010000" if _is_domestic_code(_code) else "yp010001"
    )
    # [Auto-Fixed v18.203] _is_insurance_code 原本到函式後段（L2581）才賦值，但前面
    # 「nav<10 短資料」的 Morningstar/TDCC fallback 分支（L2484+）已引用它 → 短資料時
    # UnboundLocalError（正中「查無資料 / 新基金 / 抓取失敗」edge case）。提前計算一次。
    _is_insurance_code = (not _is_domestic_code(_code) and
                          any(_code.startswith(p) for p in _INSURANCE_SUBDOMAIN_HINTS))
    result = dict(
        fund_name="", full_key=_code, fund_code=_code,
        category="", risk_level="", dividend_freq="", currency="USD",
        fund_scale="", fund_region="", fund_type="",
        moneydj_div_yield=None,
        investment_target="", fund_rating="", umbrella_fund="",
        mgmt_fee="", is_esg="",
        nav_latest=None, nav_date="",
        year_high_nav=None, year_low_nav=None,
        series=None, dividends=[], perf={}, metrics={},
        risk_metrics={}, holdings={}, error=None,
        data_source="",     # 記錄實際使用的來源
    )

    # ── Step 2: 並行嘗試多來源（NAV）────────────────────────────────
    nav_s = pd.Series(dtype=float)
    nav_source = ""

    # 0. 安聯投信官網（ACTI/ACCP/ACDD 境內基金首選，Colab 友善）
    # v6.23 fix: 加入 len(nav_s) < 10 防護，避免覆蓋 GitHub Actions 快取資料
    if len(nav_s) < 10 and _is_domestic_code(_code) and any(_code.startswith(p) for p in ("ACTI","ACCP","ACDD","ACTT")):
        _allianz_s = _src_allianzgi_nav(_code)
        if len(_allianz_s) >= 5:
            nav_s = _allianz_s
            nav_source = "allianzgi_tw"

    # 2a. FundClear（境外最穩）
    if len(nav_s) < 20:
        nav_s = _src_fundclear_nav(_code)
        if len(nav_s) >= 20:
            nav_source = "FundClear"

    # 2b. 鉅亨網
    if len(nav_s) < 20:
        nav_s = _src_cnyes_nav(_code)
        if len(nav_s) >= 20:
            nav_source = "cnyes"

    # 2c. TCB MoneyDJ（子網域）
    if len(nav_s) < 20:
        nav_s = _src_tcb_nav(_code)
        if len(nav_s) >= 10:
            nav_source = "tcb_moneydj"

    # 2c2. v6.8: 保險公司專屬 MoneyDJ 子網域（TL=台灣人壽, FL=富蘭克林 等）
    if len(nav_s) < 10:
        _ins_s = _src_insurance_subdomain_nav(_code)
        if len(_ins_s) >= 10:
            nav_s = _ins_s
            nav_source = "insurance_subdomain"
            result.setdefault("source_trace", []).append(
                {"source": "insurance_subdomain", "success": True, "nav_count": len(_ins_s)})

    # 2d. www.moneydj.com（主站，最後才試，IP 限制多）
    if len(nav_s) < 10:
        try:
            import datetime as _dt2
            import re as _re4
            base_www = "https://www.moneydj.com/funddj"
            today2 = _dt2.date.today()
            st2 = today2 - _dt2.timedelta(days=400)
            # v13.8: page_type 互換 — 首選失敗自動換頁型重試
            _pages2 = get_page_types_to_try(
                "yp010000" if _is_domestic_code(_code) else "yp010001"
            )
            params_www = {
                "A": _code,
                "B": st2.strftime("%Y%m%d"),
                "C": today2.strftime("%Y%m%d"),
            }
            rw = None
            for _pg2 in _pages2:
                hdr2 = {**HDR,
                        "Referer": f"https://www.moneydj.com/funddj/ya/{_pg2}.djhtm?a={_code}"}
                rw = fetch_url_with_retry(
                    f"{base_www}/yf/yp004002.djhtm",
                    headers=hdr2, params=params_www, timeout=25, retries=2
                )
                if rw and is_valid_moneydj_page(rw.text):
                    print(f"[www_fallback] ✅ {_code} page={_pg2}")
                    break
                print(f"[www_fallback] {_code} page={_pg2} → 無效，換頁型")
                rw = None
            if rw and is_valid_moneydj_page(rw.text):
                soup_w = BeautifulSoup(rw.text, "lxml")
                _www_rows = {}
                for tbl in soup_w.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            dt_t = cells[0].get_text(strip=True)
                            nv_t = cells[1].get_text(strip=True).replace(",", "")
                            if _re4.match(r"\d{4}/\d{2}/\d{2}", dt_t):
                                v = safe_float(nv_t)
                                if v: _www_rows[pd.Timestamp(dt_t)] = v
                if len(_www_rows) >= 10:
                    nav_s = pd.Series(_www_rows).sort_index()
                    nav_source = "moneydj_www"
                    print(f"[src_www] ✅ {_code} {len(nav_s)} 筆")
        except Exception as _we:
            print(f"[src_www] {_code}: {_we}")

    # 2e. SITCA（境內基金備援）
    if len(nav_s) < 10:
        nav_s = _src_sitca_nav(_code)
        if len(nav_s) >= 10:
            nav_source = "sitca"

    # 2f. 近30日 nav 頁直接解析（最終 fallback，yf/yp004002 全被封鎖時使用）
    # 近30日雖然只有約25~30筆，足以計算 Sharpe/標準差
    if len(nav_s) < 10:
        nav_s = _src_nav_30day(_code, _page_type)
        if len(nav_s) >= 10:
            nav_source = "moneydj_nav30"
            print(f"[orchestrator] 📅 {_code} 使用近30日淨值（{len(nav_s)}筆）")

    # 2f2. v6.18: 銀行/保險平台直連（有明確代碼映射的基金優先）
    # 使用真實 URL（華南銀行/遠東銀行/台灣人壽），非 moneydj.com domain 較不被封鎖
    if len(nav_s) < 10 and _code in _BANK_PLATFORM_CODES:
        _bp_s = _src_bank_platform_nav(_code)
        if len(_bp_s) >= 5:
            nav_s = _bp_s
            nav_source = "bank_platform"
            result.setdefault("source_trace", []).append(
                {"source": "bank_platform", "success": True, "nav_count": len(_bp_s)})
            print(f"[orchestrator] 🏦 {_code} 銀行平台直連 {len(_bp_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "bank_platform", "success": False, "error": "所有平台均無回應"})

    # 2g. v6.19: Morningstar 國際資料源（改進版：使用硬編碼 secId + 正確 currencyId）
    # TLZF9 = 0P0001J5YG (Allianz Income and Growth AMg7 USD)，已確認存在於 Morningstar
    if len(nav_s) < 10 and _is_insurance_code:
        _ms_name = result.get("fund_name") or ""
        _ms_s = _src_morningstar_nav(_code, fund_name=_ms_name)
        if len(_ms_s) >= 10:
            nav_s = _ms_s
            nav_source = "morningstar"
            result.setdefault("source_trace", []).append(
                {"source": "morningstar", "success": True, "nav_count": len(_ms_s)})
            print(f"[orchestrator] 🌐 {_code} Morningstar 命中 {len(_ms_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "morningstar", "success": False,
                 "error": "查無資料"})

    # 2g2. v6.19: Yahoo Finance 備援（Morningstar secId.F 格式，美國 IP 可存取）
    # Yahoo Finance 對共同基金使用 {morningstar_secId}.F 作為代碼
    if len(nav_s) < 10 and _is_insurance_code and _code in _MORNINGSTAR_SECID_MAP:
        _yf_s = _src_yahoo_finance_nav(_code)
        if len(_yf_s) >= 10:
            nav_s = _yf_s
            nav_source = "yahoo_finance"
            result.setdefault("source_trace", []).append(
                {"source": "yahoo_finance", "success": True, "nav_count": len(_yf_s)})
            print(f"[orchestrator] 📈 {_code} Yahoo Finance 命中 {len(_yf_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "yahoo_finance", "success": False,
                 "error": "查無資料或代碼未在映射表"})

    # 2g3. v6.22: Alpha Vantage API（需 ALPHAVANTAGE_API_KEY，美國 IP 可存取）
    # 設定方式：Streamlit Cloud → Settings → Secrets → ALPHAVANTAGE_API_KEY = "你的KEY"
    # 免費 key：25 req/day，https://www.alphavantage.co/support/#api-key
    if len(nav_s) < 10 and _is_insurance_code:
        _av_s = _src_alphavantage_nav(_code)
        if len(_av_s) >= 10:
            nav_s = _av_s
            nav_source = "alphavantage"
            result.setdefault("source_trace", []).append(
                {"source": "alphavantage", "success": True, "nav_count": len(_av_s)})
            print(f"[orchestrator] 📊 {_code} Alpha Vantage 命中 {len(_av_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "alphavantage", "success": False,
                 "error": "無資料或未設定 API Key"})

    # 2h. v6.21: 基金公司官網直連（Morningstar 也沒有時，試各公司 TW 官網）
    # 注意：FLFM1 是 BNP Paribas（法巴），不是 Franklin（富蘭克林）！
    # FL 前綴判斷需排除 FLFM（BNP Paribas 在台灣的代碼前綴）
    _FRANKLIN_PREFIX = ("FLZ", "FLA", "FLB", "FLC", "FLD", "FLE")   # 富蘭克林實際前綴
    _BNP_FL_CODES = {"FLFM1", "FLFM2"}                               # 法巴用 FL 前綴的代碼
    if len(nav_s) < 10 and _is_insurance_code:
        _intl_s = pd.Series(dtype=float)
        if _code.startswith("FL") and _code not in _BNP_FL_CODES:
            _intl_s = _src_franklin_nav(_code)
            _intl_src = "franklin_tw"
        elif _code.startswith("JF"):
            _intl_s = _src_jpmorgan_nav(_code)
            _intl_src = "jpmorgan_tw"
        else:
            _intl_src = ""
        if len(_intl_s) >= 10:
            nav_s = _intl_s
            nav_source = _intl_src
            result.setdefault("source_trace", []).append(
                {"source": _intl_src, "success": True, "nav_count": len(_intl_s)})
            print(f"[orchestrator] 🏢 {_code} 基金公司直連 {len(_intl_s)} 筆")

    # 2i. v6.17: 台灣人壽官網直連（TL 前綴，TLZF9 等）
    if len(nav_s) < 10 and _is_insurance_code and _code.startswith("TL"):
        _tl_s = _src_taiwanlife_nav(_code)
        if len(_tl_s) >= 10:
            nav_s = _tl_s
            nav_source = "taiwanlife_direct"
            result.setdefault("source_trace", []).append(
                {"source": "taiwanlife_direct", "success": True, "nav_count": len(_tl_s)})
            print(f"[orchestrator] 🏛 {_code} 台灣人壽官網直連 {len(_tl_s)} 筆")
        else:
            result.setdefault("source_trace", []).append(
                {"source": "taiwanlife_direct", "success": False,
                 "error": "官網端點查無資料或 URL 需更新"})

    if len(nav_s) >= 10:
        result["series"]      = nav_s
        result["data_source"] = nav_source
        result.setdefault("source_trace", []).append(
            {"source": nav_source, "success": True, "nav_count": len(nav_s)})
    else:
        result.setdefault("source_trace", []).append(
            {"source": "nav_all", "success": False,
             "error": f"所有來源均不足10筆（最多:{len(nav_s)}）"})

    # ── Step 3: 基本資料（Meta）─────────────────────────────────────
    meta = {}

    # v6.14: 保險公司代碼（TL/FL/CT 等）優先嘗試 TDCC OpenAPI
    # 原因：此類代碼的 MoneyDJ 保險子網域在 Streamlit Cloud 上全部被封鎖 IP，
    #       但 TDCC 是政府 API，無 IP 限制，可取得基金名稱與最新淨值。
    # v18.203：_is_insurance_code 已於函式開頭計算（避免短資料 fallback 引用未賦值）
    if _is_insurance_code:
        _tdcc_early = _src_tdcc_meta(_code)
        if _tdcc_early.get("fund_name") or _tdcc_early.get("nav_latest"):
            meta = merge_non_empty(meta, _tdcc_early)
            result.setdefault("source_trace", []).append(
                {"source": "tdcc_meta_early", "success": True})
            print(f"[orchestrator] 🏛 {_code} TDCC early 命中: "
                  f"{_tdcc_early.get('fund_name','')[:25]} "
                  f"nav={_tdcc_early.get('nav_latest')}")

    # 境內基金優先安聯投信官網
    if not meta.get("fund_name") and _is_domestic_code(_code):
        meta = _src_allianzgi_meta(_code)
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "allianzgi_meta", "success": True})
    # 優先 TCB MoneyDJ（含年高/年低）
    if not meta.get("fund_name"):
        meta = _src_tcb_meta(_code)
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "tcb_meta", "success": True})
    # 再試 FundClear
    if not meta.get("fund_name"):
        meta = merge_non_empty(meta, _src_fundclear_meta(_code))
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "fundclear_meta", "success": True})
    # 最後 SITCA（境內基金）
    if not meta.get("fund_name"):
        meta = merge_non_empty(meta, _src_sitca_meta(_code))
        if meta.get("fund_name"):
            result["source_trace"].append({"source": "sitca_meta", "success": True})
    # 最終備援：TDCC OpenAPI（境外基金官方登記，MoneyDJ 被封鎖時仍可存取）
    if not meta.get("fund_name") and not _is_domestic_code(_code):
        _tdcc_m = _src_tdcc_meta(_code)
        if _tdcc_m.get("fund_name") or _tdcc_m.get("nav_latest"):
            meta = merge_non_empty(meta, _tdcc_m)
            result["source_trace"].append({"source": "tdcc_meta", "success": True})
            print(f"[orchestrator] 🏛 {_code} TDCC metadata 命中: {_tdcc_m.get('fund_name','')[:25]}")

    if meta:
        # v13.5: 用 merge_non_empty，不讓空值覆蓋前面成功的資料
        result = merge_non_empty(result, meta)

    # ── Step 4: 配息資料 ───────────────────────────────────────────
    divs = result.get("dividends") or []
    if not divs:
        divs = _src_tcb_div(_code)
    if not divs:
        divs = _src_fundclear_div(_code)
    if not divs:
        divs = _src_cnyes_div(_code)
    if divs:
        result["dividends"] = divs
        latest_yield = divs[0].get("yield_pct", 0)
        if latest_yield > 0:
            result["moneydj_div_yield"] = round(latest_yield, 2)

    # ── Step 5: 風險指標（wb07，MoneyDJ 才有）───────────────────────
    try:
        risk_data = fetch_risk_metrics(_code)
        if risk_data:
            result["risk_metrics"] = risk_data
            perf_wb01 = fetch_performance_wb01(_code)
            if perf_wb01:
                result["perf"].update(perf_wb01)
                result["perf_source"] = "wb01"
    except Exception as _re5:
        print(f"[orchestrator] risk_metrics: {_re5}")

    # ── Step 6: 計算 MK 指標 ────────────────────────────────────────
    _finish_metrics(result)

    # ── v6.14: 保險代碼專屬提示 ─────────────────────────────────────
    # 當代碼被識別為保險公司專屬，且歷史序列為空時，給予明確引導。
    # normalize_result_state 已處理 partial/failed 狀態，此處只覆寫訊息文字。
    if _is_insurance_code:
        _has_series = result.get("series") is not None and len(result.get("series", [])) >= 10
        if not _has_series:
            if result.get("fund_name") or result.get("nav_latest"):
                # 有部分資料（名稱/淨值）→ 黃色 warning，清除紅色 error
                result["error"] = None
                result["warning"] = (
                    f"⚠️ 保險平台專屬代碼（{_code}）在 Streamlit Cloud 上無法下載歷史淨值。"
                    "MoneyDJ 保險子網域封鎖雲端 IP，Morningstar 亦無此代碼的歷史序列。"
                    " 上方已顯示 TDCC 最新淨值。如需走勢分析，請使用「手動淨值輸入」功能。"
                )
            else:
                # 完全無資料 → 紅色 error 但說明原因
                result["error"] = (
                    f"❌ 保險平台專屬代碼（{_code}）：MoneyDJ 保險子網域封鎖雲端 IP，"
                    "TDCC 及 Morningstar 亦查無此代碼。"
                    "請確認代碼是否正確，或改用「手動淨值輸入」功能。"
                )

    return result


def _finish_metrics(result: dict):
    """v19.240 R8 EX-L1ORCH-1 退役後純化:本層只做 L1 狀態收尾(初始化
    source_trace + normalize_result_state)。metrics + perf 注入 + reconcile
    業務邏輯由 L2 services.fund_service.finalize_fund_metrics 處理(`_fetch_fund_single`
    走 L2 wrapper(services.fund_service.fetch_fund_*_enriched) 才會 enrich)。
    """
    s    = result.get("series")
    code = result.get("fund_code", "?")

    if "source_trace" not in result:
        result["source_trace"] = []

    if s is None:
        result["source_trace"].append(
            {"source": "nav_series", "success": False, "error": "無淨值序列"})
    elif len(s) < 10:
        result["source_trace"].append(
            {"source": "nav_series", "success": False,
             "error": f"只有 {len(s)} 筆(需≥10)"})

    result = normalize_result_state(result)
    print(f"[orchestrator] {code} → status={result.get('status')} "
          f"error={str(result.get('error',''))[:40]} "
          f"warning={str(result.get('warning',''))[:40]}")


def fetch_fund_from_moneydj_url(url: str) -> dict:
    """
    輸入任何 MoneyDJ 基金頁面網址（或純代碼如 tlzf9），
    自動抓取：基本資料、近一年淨值歷史、績效、配息。

    回傳格式（與 fetch_fund_by_key 相容）：
    {
      "fund_name": str, "full_key": str, "fund_code": str,
      "category": str, "risk_level": str, "dividend_freq": str,
      "currency": str, "fund_scale": str,
      "nav_latest": float, "nav_date": str,
      "series": pd.Series,        # 日期→淨值，可直接給 calc_metrics
      "dividends": list,           # [{date, amount, yield_pct}]
      "perf": dict,                # {1M, 3M, 6M, 1Y, 3Y, 5Y, sharpe, beta, std}
      "metrics": dict,             # calc_metrics 結果
      "error": str or None,
    }
    """
    import re as _re
    import datetime as _dt_mj   # v19.61 E1：抓取時戳

    # ── 1. 解析代碼 ──────────────────────────────────────
    # v19.61 E1：_moneydj_fetched_at 記錄抓取當下 wallclock（YYYY-MM-DD HH:MM:SS），
    # 給 Tab5 組合健檢「資料新鮮度」banner 顯示「抓取於 / NAV 日期 / 延遲 Nd」用。
    # 純新增欄位，零影響既有 caller（讀不到的就跳過）。
    result = dict(fund_name="", full_key="", fund_code="", category="",
                  risk_level="", dividend_freq="", currency="USD",
                  fund_scale="", fund_region="", fund_type="",
                  moneydj_div_yield=None,
                  investment_target="", fund_rating="", umbrella_fund="",
                  mgmt_fee="", is_esg="",
                  nav_latest=None, nav_date="",
                  year_high_nav=None, year_low_nav=None,
                  series=None, dividends=[], perf={}, metrics={},
                  risk_metrics={}, holdings={}, error=None,
                  # C2 v19.208 F-PROV-1:加 source orchestrator-level(§2.2)
                  source="MoneyDJ:fund_url_orchestrator",
                  _moneydj_fetched_at=_dt_mj.datetime.now().strftime(
                      "%Y-%m-%d %H:%M:%S"))

    # ── v18.22: 先 canonicalize 非標準變體 URL（mobile / 平台子網域）──
    #           m.moneydj.com / chubb.moneydj.com /w/wr/ 等都轉成
    #           www.moneydj.com/funddj/ya/yp01000X.djhtm?a={base_code}
    _canonical_url = canonicalize_moneydj_url(url)
    if _canonical_url != url:
        print(f"[fetch] canonicalize: {url[:60]} → {_canonical_url[:60]}")

    # ── v13.4: parse_moneydj_input — 保留 page_type，不再丟失境內路由資訊 ──
    _input_info = parse_moneydj_input(_canonical_url)
    code = _input_info.get("code", "")

    # 若輸入只是純代碼（非 URL），嘗試 regex 補救
    if not code:
        import re as _re
        m = _re.search(r"[?&][aA]=([A-Z0-9]{3,25}(?:-[A-Z0-9]{3,20})?)", url, _re.I)
        if m:
            code = m.group(1).upper()
        elif _re.match(r"^[A-Z0-9]{3,25}(-[A-Z0-9]{3,20})?$", url.strip(), _re.I):
            code = url.strip().upper()
    if not code:
        result["error"] = "無法解析代碼，請輸入 MoneyDJ 網址或代碼（如 tlzf9）"
        return result

    _page_type = _input_info.get("page_type", "")   # 保留原始頁型（URL 輸入最準）

    # 查 mapping table：補全 public_code 與 page_type
    _mapping = load_fund_code_mapping()
    if code in _mapping:
        _m = _mapping[code]
        code       = _m.get("public_code", code)
        _page_type = _m.get("page_type", _page_type)
        print(f"[fetch] mapping 命中：{_input_info['code']} → {code} (page:{_page_type})")

    # 若 page_type 仍空白（純代碼輸入），自動推斷
    if not _page_type:
        _page_type = "yp010000" if _is_domestic_code(code) else "yp010001"
        print(f"[fetch] page_type 自動推斷：{code} → {_page_type}")

    result["full_key"]  = code
    result["fund_code"] = code

    # ── Step 1: 直接抓使用者提供的原始 URL（最高優先）───────────────
    if _input_info.get("is_url") and _input_info.get("full_url"):
        _direct = _src_direct_moneydj_url(_input_info["full_url"])
        if _direct.get("fund_name") or _direct.get("nav_latest"):
            for _k, _v in _direct.items():
                if _v not in (None, "", {}, []):
                    result[_k] = _v
            print(f"[fetch] direct_url meta: {result.get('fund_name','')[:20]} NAV={result.get('nav_latest')}")

    # ── Step 2: 多來源 Orchestrator（帶 page_type）──────────────────
    try:
        _ms_result = fetch_fund_multi_source(
            code, force_refresh=False, page_type=_page_type
        )
        # 合併策略：series/metrics/perf 優先用 multi_source，meta 保留 direct_url 結果
        # v13.5: merge_non_empty，保留 direct_url meta，補入 multi_source 的 series/metrics
        if _ms_result:
            _protect = ("fund_name","currency","risk_level","nav_latest","nav_date",
                        "year_high_nav","year_low_nav")
            _saved_meta = {k: result[k] for k in _protect if result.get(k)}
            result = merge_non_empty(result, _ms_result)
            for _k, _v in _saved_meta.items():
                if _v:
                    result[_k] = _v
            result = normalize_result_state(result)

        _s_ok = result.get("series") is not None and len(result.get("series", [])) >= 10
        _m_ok = result.get("fund_name") and result.get("nav_latest")
        if _s_ok:
            print(f"[fetch] ✅ 主路線成功（src:{result.get('data_source','')} "
                  f"status:{result.get('status','')} page:{_page_type}）")
            return result
        # v18.121 issue 4: series 缺失但 fund_name+nav 有 → 不再提早 return（之前 bug）
        # 自動切 alternative page_type 重試一次（境內↔境外 mapping 錯誤的 case）
        # 例：ACTI71 mapping table 標境內 yp010000 但實際境外，切 yp010001 重試可拿到 series
        elif _m_ok:
            _alt_pt = "yp010001" if _page_type == "yp010000" else "yp010000"
            print(f"[fetch] ⚠️ {code} 主路線 ({_page_type}) series=0 但 meta 有；"
                  f"切 {_alt_pt} fallback 重試...")
            try:
                _alt_result = fetch_fund_multi_source(
                    code, force_refresh=False, page_type=_alt_pt
                )
                if _alt_result:
                    _alt_s = _alt_result.get("series")
                    _alt_s_ok = (_alt_s is not None and hasattr(_alt_s, "__len__")
                                 and len(_alt_s) >= 10)
                    if _alt_s_ok:
                        # alt page_type 拿到 series → 合併到既有 meta（保留主路線拿到的 name/nav）
                        _meta_protect = ("fund_name", "currency", "risk_level",
                                         "nav_latest", "nav_date",
                                         "year_high_nav", "year_low_nav")
                        _saved_meta = {k: result[k] for k in _meta_protect if result.get(k)}
                        result = merge_non_empty(result, _alt_result)
                        for _k, _v in _saved_meta.items():
                            if _v:
                                result[_k] = _v
                        result = normalize_result_state(result)
                        print(f"[fetch] ✅ alt page_type ({_alt_pt}) fallback 成功，"
                              f"series={len(_alt_s)}（meta 保留主路線結果）")
                        return result
                    else:
                        print(f"[fetch] alt page_type ({_alt_pt}) 仍 series=0，"
                              f"繼續原始流程")
            except Exception as _alt_e:
                print(f"[fetch] alt page_type fallback 異常: {_alt_e}")
            # 兩個 page_type 都拿不到 series → 繼續走 Step 3+ 原始 _src_* 流程
            print(f"[fetch] ⚠️ 兩個 page_type 都不足，繼續原始流程")
        else:
            print(f"[fetch] ⚠️ 不足，繼續原始流程（page:{_page_type}）")
    except Exception as _ms_e:
        print(f"[fetch] 多來源異常: {_ms_e}，繼續原始流程")

    # ── 判斷境內/境外基金（影響爬蟲路徑）──────────────────
    # 境內基金（投信，如聯博/安聯投信/富達投信）：
    #   www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACTI71
    # 境外基金（ISIN/境外代碼）：
    #   www.moneydj.com/funddj/ya/YP081000.djhtm?a=TLZF9
    # tcbbankfund 子網域對境內/境外都相容，且 Colab IP 封鎖較少

    _portal_auto = ""
    _code_upper = code.upper()

    # BASE 一律優先走 tcbbankfund（對 Colab IP 最友善）
    BASE = "https://tcbbankfund.moneydj.com/funddj"
    print(f"[fetch] code={code}  BASE={BASE}")

    # ── 2. 基本資料 yp011001（tcbbankfund 優先，www fallback）──
    try:
        # v14.4: 境內用 yp011000，境外用 yp011001（從實際 HTML 確認）
        _info_page_type = "yp011000" if _is_domestic_code(code, _page_type) else "yp011001"
        _info_pages_try = [_info_page_type]
        # 互換備用：yp011000 失敗試 yp011001，反之亦然
        _info_pages_try.append("yp011001" if _info_page_type == "yp011000" else "yp011000")

        _info_urls = []
        for _ip in _info_pages_try:
            _info_urls.extend([
                f"https://tcbbankfund.moneydj.com/funddj/yp/{_ip}.djhtm?a={code}",
                f"https://www.moneydj.com/funddj/yp/{_ip}.djhtm?a={code}",
            ])
        r = None
        for _iu in _info_urls:
            # v14.4: fetch_url_with_retry (Big5 統一解碼)
            r = fetch_url_with_retry(_iu, timeout=20, retries=1)
            if r is not None and len(r.text) > 500:
                break
        if r is not None and len(r.text) > 500:
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "基金名稱" not in txt: continue
                # 建立 key→value map（支援多欄 row: col0=key1, col1=val1, col2=key2, col3=val2）
                rows_map = {}
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    # 單欄對 (key, value)
                    if len(cells) == 2:
                        k = cells[0].get_text(strip=True)
                        v = cells[1].get_text(strip=True)
                        rows_map[k] = v
                    # 雙欄對 (key1, val1, key2, val2)
                    elif len(cells) >= 4:
                        for i in range(0, len(cells)-1, 2):
                            k = cells[i].get_text(strip=True)
                            v = cells[i+1].get_text(strip=True)
                            if k: rows_map[k] = v
                result["fund_name"]       = rows_map.get("基金名稱", "")
                result["currency"]        = rows_map.get("計價幣別", "USD").replace(" ","")
                result["risk_level"]      = rows_map.get("風險報酬等級", "").replace(" ","")
                result["dividend_freq"]   = rows_map.get("配息頻率", "").replace(" ","")
                result["fund_scale"]      = rows_map.get("基金規模", "")
                result["category"]        = rows_map.get("投資標的", rows_map.get("基金類型", "")).replace(" ","")
                result["fund_region"]     = rows_map.get("投資區域", "").replace(" ","")
                result["fund_type"]       = rows_map.get("基金類型", "").replace(" ","")
                result["investment_target"]= rows_map.get("投資標的", "").replace(" ","")
                result["fund_rating"]     = rows_map.get("基金評等", "")
                result["umbrella_fund"]   = rows_map.get("傘型架構", "").replace(" ","")
                result["mgmt_fee"]        = rows_map.get("最高經理費(%)", "")
                result["is_esg"]          = rows_map.get("是否為ESG", "")
                # latest NAV + 年度高低點 from this page
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 4:
                        # 行格式: 淨值日期 | 淨值 | 最高淨值(年) | 最低淨值(年)
                        dt = cells[0].get_text(strip=True)
                        if _re.match(r"\d{4}/\d{2}/\d{2}", dt):
                            try:
                                result["nav_date"]    = dt
                                result["nav_latest"]   = safe_float(cells[1].get_text(strip=True))
                                result["year_high_nav"] = safe_float(cells[2].get_text(strip=True))
                                result["year_low_nav"]  = safe_float(cells[3].get_text(strip=True))
                                print(f"[fetch_basic] 年高={result['year_high_nav']} 年低={result['year_low_nav']}")
                            except (ValueError, TypeError, IndexError) as _e:
                                # W5-1 §1 Fail Loud: bare except → narrow + log
                                print(f"[fetch_basic] ⚠️ 年高低解析失敗 dt={dt}: {_e}")
                    elif len(cells) >= 2:
                        dt = cells[0].get_text(strip=True)
                        if _re.match(r"\d{4}/\d{2}/\d{2}", dt):
                            try:
                                result["nav_date"]   = dt
                                result["nav_latest"] = float(cells[1].get_text(strip=True).replace(",",""))
                            except (ValueError, TypeError) as _e:
                                # W5-1 §1 Fail Loud: bare except → narrow + log
                                print(f"[fetch_basic] ⚠️ nav_latest 解析失敗 dt={dt}: {_e}")
                break
    except Exception as e:
        print(f"[fetch_basic] {e}")

    # ── 3. 淨值歷史（近30日）→ 再查詢歷史區間 ──
    # v13.8: page_type 互換 — 首選失敗自動換 yp010000 ↔ yp010001
    try:
        _primary_nav_page = _page_type if _page_type else (
            "yp010000" if _is_domestic_code(code) else "yp010001"
        )
        _nav_page_candidates = get_page_types_to_try(_primary_nav_page)
        _nav_bases = [
            BASE,
            TCB_BASE + "/funddj",
            "https://www.moneydj.com/funddj",
            "https://tcbbankfund.moneydj.com/funddj",
        ]
        _nav_r = None
        # 外層：依次嘗試各 base；若回傳無效，換頁型再試一遍
        for _nav_pg in _nav_page_candidates:
            if _nav_r is not None:
                break
            for _nb_url in _nav_bases:
                try:
                    _nav_r = fetch_url_with_retry(
                        f"{_nb_url}/ya/{_nav_pg}.djhtm?a={code}",
                        timeout=25, retries=1
                    )
                    if _nav_r is not None:
                        print(f"[nav30] ✅ {code} page={_nav_pg} base={_nb_url[:30]}")
                        break
                except Exception as _ne:
                    print(f"[nav fallback] {_nb_url}: {_ne}")
                    continue
        r = _nav_r
        # v13.6: fetch_url_with_retry 不回 status_code，直接判斷 r is not None
        if r is not None:
            soup = BeautifulSoup(r.text, "lxml")
            nav_rows = {}
            _nav30_parse_fail = 0  # W5-1 §1 Fail Loud: 計數解析失敗(逐 row 細 log 會 noise)
            for tbl in soup.find_all("table"):
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        date_txt = cells[0].get_text(strip=True)
                        nav_txt  = cells[1].get_text(strip=True).replace(",","")
                        if _re.match(r"\d{2}/\d{2}", date_txt) and _re.match(r"[\d.]+$", nav_txt):
                            try:
                                nav_rows[date_txt] = float(nav_txt)
                            except (ValueError, TypeError):
                                # 已通過 regex 預檢仍解析失敗(如 "1.2.3"),累計後彙總 log
                                _nav30_parse_fail += 1
            if _nav30_parse_fail > 0:
                print(f"[nav30] ⚠️ {code} nav 解析失敗 {_nav30_parse_fail} 筆(已過 regex 預檢)")
            # 轉換日期（MoneyDJ 近期只顯示 MM/DD，需補年份）
            import datetime as _dt
            today = _dt.date.today()
            parsed = {}
            for mmdd, v in nav_rows.items():
                try:
                    mo, da = int(mmdd.split("/")[0]), int(mmdd.split("/")[1])
                    yr = today.year if (mo, da) <= (today.month, today.day) else today.year - 1
                    parsed[_dt.date(yr, mo, da)] = v
                except Exception as e:
                    # v19.184 F-MED:加 stderr log(§3.3 反捏造)
                    import sys as _sys
                    print(f'[fund_repository] nav_rows mmdd parse fail "{mmdd}": '
                          f'{type(e).__name__}: {e}', file=_sys.stderr)

            # 再查詢整年歷史（使用查詢 endpoint）
            end_dt   = today
            start_dt = today - _dt.timedelta(days=400)
            # v13.8: page_type 互換 — 首選失敗自動換頁型重試
            _hist_pages = get_page_types_to_try(
                "yp010000" if _is_domestic_code(code) else "yp010001"
            )
            _hist_params = {
                "A": code, "B": start_dt.strftime("%Y%m%d"), "C": end_dt.strftime("%Y%m%d")
            }
            _hist_urls = [
                f"{BASE}/yf/yp004002.djhtm",
                f"{TCB_BASE}/funddj/yf/yp004002.djhtm",
                f"https://www.moneydj.com/funddj/yf/yp004002.djhtm",
                f"https://tcbbankfund.moneydj.com/funddj/yf/yp004002.djhtm",
            ]
            r2 = None
            for _hpage in _hist_pages:
                if r2 is not None:
                    break
                hdr_ext = {**HDR,
                           "Referer": f"https://www.moneydj.com/funddj/ya/{_hpage}.djhtm?a={code}"}
                for _hu in _hist_urls:
                    try:
                        _r2_try = fetch_url_with_retry(
                            _hu, headers=hdr_ext,
                            params=_hist_params, timeout=25, retries=2
                        )
                        if _r2_try is not None:
                            r2 = _r2_try
                            print(f"[hist] ✅ {code} page={_hpage}")
                            break
                    except Exception as _he:
                        print(f"[hist fallback] {_hu}: {_he}")
                        continue
            if r2 is not None:
                soup2 = BeautifulSoup(r2.text, "lxml")
                hist_rows = {}
                for tbl in soup2.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            dt_txt  = cells[0].get_text(strip=True)
                            nav_txt = cells[1].get_text(strip=True).replace(",","")
                            if _re.match(r"\d{4}/\d{2}/\d{2}", dt_txt) and _re.match(r"[\d.]+$", nav_txt):
                                try:
                                    import pandas as _pd
                                    hist_rows[_pd.to_datetime(dt_txt)] = float(nav_txt)
                                except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                if len(hist_rows) >= 20:
                    import pandas as _pd
                    result["series"] = _pd.Series(hist_rows).sort_index()
                    print(f"[fetch_nav_hist] ✅ {len(result['series'])} 筆")

            # v14.4: 若歷史查詢失敗，用近30日資料（parsed 已是 date key）
            if result["series"] is None and len(parsed) >= 5:
                import pandas as _pd
                try:
                    _s30 = _pd.Series({_pd.Timestamp(k): v for k,v in parsed.items()}).sort_index()
                    result["series"] = _s30
                    print(f"[fetch_nav_30] ✅ {len(result['series'])} 筆（近30日）")
                except Exception as _ps_e:
                    print(f"[fetch_nav_30] 轉換失敗: {_ps_e}")
                    # 最後備援：呼叫 _src_nav_30day
                    _s30b = _src_nav_30day(code, _page_type)
                    if len(_s30b) >= 5:
                        result["series"] = _s30b
                        print(f"[fetch_nav_30b] ✅ {len(_s30b)} 筆")
    except Exception as e:
        print(f"[fetch_nav] {e}")

    # ── 4. 績效評比 wb07 (標準差/Sharpe/Alpha/Beta/R²/Tracking Error) ──
    try:
        risk_data = fetch_risk_metrics(code)
        result["risk_metrics"] = risk_data
        # 從 peer_compare 取年報酬率 → perf["1Y"]（備援）
        peer = risk_data.get("peer_compare", {})
        for row_name, row_vals in peer.items():
            if "基金" in row_name or (code.upper() in row_name.upper()):
                try:
                    yr_txt = str(list(row_vals.values())[0]).replace("%","")
                    result["perf"]["1Y"] = float(yr_txt)
                except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                break
    except Exception as e:
        print(f"[fetch_risk] {e}")

    # ── 4c. 含息總報酬率 wb01（優先使用，MoneyDJ 說明：已考慮配息）─────
    try:
        perf_wb01 = fetch_performance_wb01(code)
        if perf_wb01:
            # wb01 資料覆蓋 peer_compare 估算值（更精確）
            for k, v in perf_wb01.items():
                result["perf"][k] = v
            result["perf_source"] = "wb01"
    except Exception as e:
        print(f"[fetch_perf_wb01] {e}")

    # ── 4b. 持股（產業配置 + 前10大持股）─────────────────
    try:
        holdings_data = fetch_holdings(code)
        result["holdings"] = holdings_data
    except Exception as e:
        print(f"[fetch_holdings] {e}")

    # ── 5. 配息 wb05 ──────────────────────────────────────
    try:
        # v14.4: 境內用 funddividend，境外用 wb05（與 _src_tcb_div 邏輯一致）
        _is_dom_div = _is_domestic_code(code, _page_type)
        _div_page = "funddividend" if _is_dom_div else "wb05"
        _div_fallback = "wb05" if _is_dom_div else "funddividend"
        _wb05_r = None
        for _div_pg in [_div_page, _div_fallback]:
            for _db in [BASE, TCB_BASE + "/funddj",
                        "https://www.moneydj.com/funddj",
                        "https://tcbbankfund.moneydj.com/funddj"]:
                # v14.4: fetch_url_with_retry (Big5)
                _try_r = fetch_url_with_retry(f"{_db}/yp/{_div_pg}.djhtm?a={code}",
                                              timeout=20, retries=1)
                if _try_r is not None:
                    _wb05_r = _try_r
                    print(f"[div] ✅ {code} 配息頁={_div_pg}")
                    break
            if _wb05_r is not None:
                break
        r = _wb05_r
        if r is not None:
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "配息基準日" not in txt and "除息日" not in txt: continue
                rows = tbl.find_all("tr")[1:]
                for row in rows[:36]:  # 最多3年
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) < 5: continue
                    try:
                        # v14.4: col[3]=TEXT"配息", col[4]=配息金額, col[5]=年化率, col[6]=幣別
                        if len(cols) < 5: continue
                        if "/" not in cols[0]: continue   # 跳過非日期行
                        _amt = safe_float(cols[4])
                        if _amt is None or _amt <= 0 or _amt > 1000: continue
                        _yld = safe_float(cols[5]) or 0.0 if len(cols) > 5 else 0.0
                        _cur = (cols[6].strip() if len(cols) > 6 and cols[6].strip()
                                else result.get("currency", "USD"))
                        result["dividends"].append({
                            "date":      cols[0],
                            "ex_date":   cols[1],
                            "pay_date":  cols[2],
                            "amount":    _amt,
                            "yield_pct": _yld,
                            "currency":  _cur,
                        })
                    except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                # v10: 取最新一筆 年化配息率% 作為 MoneyDJ 官方值
                if result["dividends"]:
                    latest_yield = result["dividends"][0].get("yield_pct", 0)
                    if latest_yield > 0:
                        result["moneydj_div_yield"] = round(latest_yield, 2)
                        print(f"[wb05] MoneyDJ 年化配息率: {latest_yield:.2f}%")
                break
    except Exception as e:
        print(f"[fetch_div] {e}")

    # ── 6. 計算 MK 指標（優先使用 wb07 標準差）────────────
    # ── 最終備援：使用 fetch_nav() 完整 TCB 多路徑爬取 ─────────────
    if result["series"] is None or len(result["series"]) < 10:
        try:
            _fallback_s = fetch_nav(code, portal="")
            if len(_fallback_s) >= 10:
                result["series"] = _fallback_s
                result["error"] = None
                print(f"[fetch_nav_fallback] \u2705 {len(_fallback_s)} \u7b46")
        except Exception as _fnf_e:
            print(f"[fetch_nav_fallback] {_fnf_e}")

    # v19.240 R8 EX-L1ORCH-1 退役:metrics + perf 注入 + reconcile 上提 L2
    # services.fund_service.finalize_fund_metrics(走 fetch_fund_from_moneydj_url_enriched
    # wrapper)。本層只 packaging raw series + dividends。
    if result["series"] is not None and len(result["series"]) < 10:
        result["error"] = f"只取到 {len(result['series'])} 筆淨值（建議≥10）"
    elif result["series"] is None:
        # v10.7.1 改善：淨值歷史失敗時，嘗試從 perf/risk 數據重建部分指標
        # 並給出明確的操作指引
        _has_perf = bool(result.get("perf"))
        _has_risk = bool(result.get("risk_metrics"))
        if _has_perf or _has_risk:
            result["error"] = (
                "⚠️ 淨值歷史抓取失敗（MoneyDJ 可能封鎖伺服器 IP）\n"
                "但已取得部分績效/風險數據，可繼續查看。\n"
                "💡 建議：直接貼 MoneyDJ 完整網址以取得最佳結果"
            )
        else:
            # ── 記憶體快照 fallback（網路斷線時顯示上次成功資料）──
            _snap_key = (code or result.get("full_key", "")).upper()
            if _snap_key and _snap_key in _FUND_SNAPSHOT:
                _snap = _FUND_SNAPSHOT[_snap_key]
                result.update({k: v for k, v in _snap.items() if v})
                result["error"]   = None
                result["warning"] = "⚠️ 網路暫時無法連線，顯示上次快照資料（數值可能稍舊）"
                print(f"[snapshot] ✅ {_snap_key} 使用記憶體快照")
            else:
                result["error"] = (
                    "❌ 無法取得基金資料（所有來源均失敗）\n"
                    "💡 解決方案：\n"
                    "① 直接貼 MoneyDJ 完整網址（比代碼更準確）：\n"
                    "   境內基金：www.moneydj.com/funddj/ya/yp010000.djhtm?a={code}\n"
                    "   境外基金：www.moneydj.com/funddj/ya/yp010001.djhtm?a={code}\n"
                    "② 於下方手動填入淨值、配息數據"
                ).format(code=result.get("full_key","???"))

    # ── 成功取得資料時更新記憶體快照 ──────────────────────────────────
    _snap_key = (code or result.get("full_key", "")).upper()
    if _snap_key and result.get("series") is not None and result.get("error") is None:
        # 快照不含 series（節省記憶體），保留 metrics/perf/fund_name 等輕量欄位
        _FUND_SNAPSHOT[_snap_key] = {
            k: v for k, v in result.items()
            if k not in ("series",) and v not in (None, [], {})
        }
        print(f"[snapshot] 💾 {_snap_key} 快照已更新")

    return result




# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：search_fundclear / search_moneydj_by_name / _parse_nav_html / fetch_nav / fetch_div
# ════════════════════════════════════════════════════════════

def search_fundclear(keyword: str) -> list:
    """用 fundclear REST API 搜尋境外基金（Colab 可存取）"""
    results = []
    seen = set()
    kw = keyword.strip()
    try:
        body = {
            "fundName": kw, "fundCode": "",
            "fundAsset": "all", "fundAssetSub": "all",
            "fundInv": "all", "invArea": "all", "invAreaSub": "all",
            "agentCode": "all", "orgCode": "all",
            "pageNum": 1, "pageSize": 20,
        }
        r = requests.post(
            "https://www.fundclear.com.tw/api/offshore/fund-info/fund-search/query",
            json=body, headers=HDR_JSON, timeout=20, proxies=_proxies(), verify=_ssl_verify()
        )
        print(f"[fundclear] status={r.status_code}")
        if r.status_code == 200:
            d = r.json()
            # 嘗試各種回傳結構
            raw = d.get("data") or {}
            fund_list = (raw.get("list") or raw.get("fundList") or
                         (raw if isinstance(raw, list) else []))
            for item in fund_list:
                code = str(item.get("fundCode") or item.get("code") or "")
                name = str(item.get("fundName") or item.get("name") or "")
                nav  = float(item.get("nav") or item.get("latestNav") or 0)
                if not code or not name or code in seen: continue
                seen.add(code)
                portal = "allianz" if ("安聯" in name or "AGIF" in code) else ""
                results.append({"full_key": code, "name": name,
                                 "portal": portal, "nav": nav, "source": "fundclear"})
            print(f"[fundclear] {len(results)} 筆")
    except Exception as e:
        print(f"[fundclear] ERR: {e}")
    return results


def search_moneydj_by_name(keyword: str) -> list:
    """搜尋基金：① fundclear API → ② MoneyDJ 選單 → ③ fundsearch"""
    kw = keyword.strip()
    kw_up = kw.upper()
    results = []
    seen = set()

    # ① fundclear
    for r in search_fundclear(kw):
        if r["full_key"] not in seen:
            seen.add(r["full_key"]); results.append(r)

    # ② MoneyDJ fund-page.html 選單
    for portal_name, url in [
        ("allianz", "https://tcbbankfund.moneydj.com/fund-page.html"),  # Fix: correct subdomain
        ("chubb",   "https://chubb.moneydj.com/fund-page.html?sUrl=$W$HTML$SELECT]DJHTM"),
    ]:
        try:
            r = requests.get(url, headers=HDR, timeout=20, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code != 200: continue
            # v13.3: 同時支援 TLZF9 / ACTI98（無 dash）和 ABC-XYZ123（有 dash）
            for val, text in re.findall(
                r'value="([A-Z0-9a-z]{4,25}(?:-[A-Z0-9a-z]{3,20})?)"[^>]*>([^<]+)<',
                r.text, re.IGNORECASE
            ):
                if kw_up in text.upper():
                    fk = val.upper()
                    if fk in seen: continue
                    seen.add(fk)
                    name = re.sub(r"^[A-Z0-9]{3,20}\s*[-\u2013]\s*", "",
                                  text.strip(), flags=re.IGNORECASE).strip()
                    results.append({"full_key": fk, "name": name or text.strip(),
                                    "portal": portal_name, "nav": 0.0, "source": "moneydj_menu"})
        except Exception as e:
            print(f"[fund_page {portal_name}] ERR: {e}")

    # ③ fundsearch 備援
    if not results:
        try:
            url = f"https://www.moneydj.com/funddjx/fundsearch.xdjhtm?keyword={requests.utils.quote(kw)}"
            r = requests.get(url, headers=HDR, timeout=15, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "lxml")
                for tbl in soup.find_all("table"):
                    for row in tbl.find_all("tr")[1:]:
                        fk = ""; name = ""
                        for a in row.find_all("a", href=True):
                            mx = re.search(r"[aA]=([A-Z0-9a-z]{3,25})", a["href"])
                            if mx: fk = mx.group(1); name = a.get_text(strip=True); break
                        if fk and len(name) >= 3 and fk not in seen:
                            seen.add(fk)
                            results.append({"full_key": fk, "name": name,
                                            "portal": "", "nav": 0.0, "source": "mj_search"})
        except Exception as e:
            print(f"[fundsearch] ERR: {e}")

    print(f"[search_total] {kw!r} → {len(results)} 筆")
    return results[:15]
