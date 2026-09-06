"""repositories/fund/sources.py — v19.200 P1-5 全部 _src_* + 各 source adapter helper。

從 fund_repository 主檔抽出(原 line 80-2451):
- Fundclear / AllianzGI / Cnyes / Cache / Bank / Morningstar / Yahoo / Alphavantage /
  Insurance / Franklin / JPMorgan / MoneyDJ direct / TCB / SITCA / TDCC / Insurance subdomain
- code mapping helper(load_fund_code_mapping / canonicalize_moneydj_url / parse_moneydj_input /
  normalize_domestic_code / _is_domestic_code / get_page_types_to_try)

v19.248 R17 bug fix:Python `from X import *` 規則**不引入底線開頭名稱**,
P1-5 拆檔後 `fund_orchestration.py:32` 的 `from sources import *` 無法載入
任何 `_src_*` → NameError 全爆。**修法**:明確宣告 `__all__` SSOT export list
包含全部 `_src_*` 名單(有 `__all__` 時 `import *` 依名單載入,可含底線名)。
"""
from __future__ import annotations

import requests
import pandas as pd
from bs4 import BeautifulSoup

from infra.cache import (  # noqa: F401
    _ttl_cache, register_cache, _CACHE_DIR, _FUND_SNAPSHOT, _cache_path,
    _cache_load_nav, _cache_save_nav, _cache_load_div, _cache_save_div,
    _cache_load_meta, _cache_save_meta,
)
# v19.385 T2b:%-欄位(費用/TER)解析收 SSOT safe_num(內建 strip '%'/','+ 排 bool),
# 取代手動 safe_float(x.replace("%","").strip()) 反模式。純數值欄位仍用 safe_float(語意分工,見 shared/converters)。
from shared.converters import safe_num
from fund_fetcher import (  # noqa: F401
    safe_float, fetch_url_with_retry, is_valid_moneydj_page,
    HDR, HDR_JSON, PORTAL_CFG, TCB_BASE, _INSURANCE_SUBDOMAIN_HINTS,
    normalize_result_state, merge_non_empty, classify_fetch_status,
)
from infra.proxy import _proxies, _ssl_verify  # noqa: F401


# v19.248 R17 SSOT bug fix:`from X import *` 規則不引入底線開頭名(`_src_*` 全壞)。
# 顯式 `__all__` 名單支援 `import *` 取得所有 source adapter helper(含底線名)。
# 此 SSOT 為 `fund_orchestration.py` re-export 入口,新增 `_src_*` 必須同步加入。
__all__ = [
    # ── _src_* source adapters(基金 NAV / meta / div 各來源)──
    "_src_allianzgi_meta", "_src_allianzgi_nav",
    "_src_alphavantage_nav",
    "_src_bank_platform_nav",
    "_src_cache_files",
    "_src_cnyes_div", "_src_cnyes_nav",
    "_src_direct_moneydj_url",
    "_src_franklin_nav",
    "_src_fundclear_div", "_src_fundclear_meta", "_src_fundclear_nav",
    "_src_insurance_subdomain_nav",
    "_src_jpmorgan_nav",
    "_src_morningstar_meta", "_src_morningstar_nav",
    "_src_nav_30day",
    "_src_sitca_meta", "_src_sitca_nav",
    "_src_taiwanlife_nav",
    "_src_tcb_div", "_src_tcb_meta", "_src_tcb_nav",
    "_src_tdcc_meta",
    "_src_yahoo_finance_nav",
    # ── 內部 helper(orchestration 用)──
    "_cnyes_parse_navs", "_cnyes_resolve_code",
    # 2026-08-11:`_infer_year_for_mmdd`(v19.333 F5 抽出的 MM/DD 補年份純函式)
    # 新增為 orchestration consumer —— legacy pipeline 的近30日區塊原本 inline
    # 重寫一份且用 UTC today(§4.5 365 天錯置風險),改吃這支 SSOT。
    # ⚠️ 不列進 __all__ 的話 `import *` 拿不到底線名 → NameError(v19.248 R17 同型)。
    "_infer_year_for_mmdd",
    "_is_domestic_code",
    "_morningstar_search_secid",
    "_morningstar_screener_secid",     # v19.491:ISIN → secId 精確 screener 解析(同 host/token)
    "_tdcc_get", "_tdcc_resolve_fund_name",
    # v19.288 F405 掃描補洞:兩個 dict 常數先前未列進 __all__,
    # fund_orchestration.py 靠 `import *` 拿不到 → 對應 if 判斷式
    # 每次都拋 NameError(見同批補洞的 fetch_nav/fetch_risk_metrics/
    # fetch_performance_wb01 import)
    "_BANK_PLATFORM_CODES", "_MORNINGSTAR_SECID_MAP",
    # ── public functions ──
    "canonicalize_moneydj_url",
    "fetch_div_cnyes", "fetch_fund_multi_source",
    "fetch_holdings_cnyes", "fetch_holdings_morningstar", "fetch_nav_cnyes",
    "get_page_types_to_try",
    "load_fund_code_mapping",
    "normalize_domestic_code",
    "parse_moneydj_input",
    "probe_insurance_urls",
    "tdcc_get_agents", "tdcc_search_fund",
]


# Yahoo Finance v8 chart API — Morningstar {secId}.F symbol 專用 template。
# v19.230 P1-2 第二輪:深層稽核確認與 scripts/fetch_nav_cache.py:fetch_morningstar_via_yf
# 真重複(同字串,兩處 production-ish caller)→ SSOT 收口至此(production fetcher 為主,
# scripts 從這裡 import)。symbol 為 `{secId}.F`(_src_yahoo_finance_nav L830)。
# v19.477(user「淨值延長至 5 年」+ 提醒 code→ISIN→secId→Yahoo chart 流程):range 2y → 10y,
# 讓 Yahoo chart({secId}.F)也能回 5 年以上(對齊其餘來源 2000d 窗口;2y 為 3Y/5Y 指標不足根因)。
YF_MORNINGSTAR_CHART_URL = (
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval=1d&range=10y&includePrePost=false"
)


# ══════════════════════════════════════════════════════════════════════
# 來源 1：FundClear API（境外基金，Colab 最穩定）
# ══════════════════════════════════════════════════════════════════════

def _src_fundclear_nav(code: str) -> pd.Series:
    """
    從 FundClear REST API 取歷史淨值。
    境外基金（6位英數代碼）效果最佳，Colab IP 不會被擋。
    """
    try:
        import datetime as _dt
        end_d = _dt.date.today()
        # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
        # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
        start_d = end_d - _dt.timedelta(days=2000)
        url = (
            f"https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax/GetFundNAV"
            f"?FundCode={code}&StartDate={start_d.strftime('%Y/%m/%d')}"
            f"&EndDate={end_d.strftime('%Y/%m/%d')}"
        )
        r = fetch_url_with_retry(url, timeout=15, retries=2)
        if r is None:
            return pd.Series(dtype=float)
        data = r.json()
        rows = {}
        nav_list = (data.get("Data") or data.get("data") or
                    data.get("NAVList") or data.get("navList") or [])
        if not nav_list and isinstance(data, list):
            nav_list = data
        for item in nav_list:
            if isinstance(item, dict):
                d_val = (item.get("Date") or item.get("date") or
                         item.get("NavDate") or item.get("navDate") or "")
                n_val = safe_float(
                    item.get("NAV") or item.get("nav") or
                    item.get("NetAssetValue") or item.get("latestNav"))
                if d_val and n_val is not None:
                    try:
                        rows[pd.Timestamp(str(d_val)[:10])] = n_val
                    except Exception:
                        pass
        if rows:
            s = pd.Series(rows).sort_index()
            print(f"[src_fundclear] ✅ {code} {len(s)} 筆")
            # F-PROV-1 phase 7 v19.93 — provenance(Series.attrs)
            s.attrs["source"] = "FundClear:GetFundNAV"
            s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            return s
    except Exception as e:
        print(f"[src_fundclear] {code}: {e}")
    return pd.Series(dtype=float)


def _src_fundclear_meta(code: str) -> dict:
    """從 FundClear 取基金基本資料"""
    meta = {}
    try:
        url = (f"https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax"
               f"/GetFundBasicInfo?FundCode={code}")
        r = fetch_url_with_retry(url, timeout=12, retries=2)
        if r is None:
            return meta
        data = r.json()
        info = (data.get("Data") or data.get("data") or
                (data if isinstance(data, dict) else {}))
        if isinstance(info, list) and info:
            info = info[0]
        if isinstance(info, dict):
            meta["fund_name"]   = (info.get("FundName") or info.get("fundName") or
                                    info.get("ChtName") or "")
            meta["currency"]    = (info.get("Currency") or info.get("currency") or "USD")
            meta["risk_level"]  = str(info.get("RiskLevel") or info.get("riskLevel") or "")
            meta["category"]    = (info.get("FundType") or info.get("fundType") or "")
            meta["nav_latest"]  = safe_float(info.get("LatestNAV") or info.get("latestNav"))
            nav_d = (info.get("LatestNAVDate") or info.get("navDate") or "")
            meta["nav_date"]    = str(nav_d)[:10] if nav_d else ""
            # v19.370 真實 TER(FundClear fetcher):同一 GetFundBasicInfo 回應補抽
            # 「總費用率 / 經常性費用(OCF)」— 境外基金公開說明書/KIID 揭露的年度總內扣。
            # 零新增 HTTP;欄位名未知 → 多候選 or 鏈(比照 inception_date 既有防禦式抓法);
            # §3.2 合理性:TER 落在 (0, 10]% 才收,否則視為髒值顯式丟棄(§1 不造假)。
            _ter_raw = (info.get("TotalExpenseRatio") or info.get("ExpenseRatio") or
                        info.get("OngoingCharges") or info.get("OngoingChargesFigure") or
                        info.get("TER") or info.get("OCF") or info.get("AnnualExpenseRatio") or
                        info.get("totalExpenseRatio") or info.get("expenseRatio") or
                        info.get("ongoingCharges") or info.get("ter") or info.get("ocf") or
                        info.get("總費用率") or info.get("經常性費用") or
                        info.get("總開支比率") or "")
            _ter_v = safe_num(_ter_raw)
            if _ter_v is not None and 0 < _ter_v <= 10:
                meta["expense_ratio"] = _ter_v          # 揭露 TER(%),消費端優先於估計
                meta["expense_ratio_source"] = "FundClear:GetFundBasicInfo"
            # 成立日期（FundClear 可能欄位名稱不一）
            _inc_raw = (info.get("EstablishDate") or info.get("InceptionDate") or
                        info.get("LaunchDate") or info.get("FundCreationDate") or
                        info.get("establishDate") or info.get("inceptionDate") or
                        info.get("launchDate") or "")
            if _inc_raw:
                _inc_str = str(_inc_raw)[:10].replace("/", "-")
                if len(_inc_str) == 10:
                    meta["inception_date"] = _inc_str
            if meta.get("fund_name"):
                print(f"[src_fundclear_meta] ✅ {code}: {meta['fund_name'][:20]}")
                # F-PROV-1 phase 6 v19.92 — provenance(schema-additive)
                meta["source"] = "FundClear:GetFundBasicInfo"
                meta["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    except Exception as e:
        print(f"[src_fundclear_meta] {code}: {e}")
    return meta


def _src_fundclear_div(code: str) -> list:
    """從 FundClear 取配息資料"""
    divs = []
    try:
        url = (f"https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax"
               f"/GetFundDividend?FundCode={code}")
        r = fetch_url_with_retry(url, timeout=12, retries=2)
        if r is None:
            return divs
        data = r.json()
        items = (data.get("Data") or data.get("data") or
                 (data if isinstance(data, list) else []))
        for item in (items or []):
            amt = safe_float(item.get("DividendAmount") or
                             item.get("dividendAmount") or
                             item.get("Amount") or item.get("amount"))
            if amt is None or amt <= 0:
                continue
            d_str = (item.get("ExDividendDate") or item.get("exDividendDate") or
                     item.get("Date") or item.get("date") or "")
            divs.append({
                "date":      str(d_str)[:10],
                "ex_date":   str(d_str)[:10],
                "pay_date":  str(d_str)[:10],
                "amount":    amt,
                "yield_pct": safe_float(
                    item.get("DividendRate") or item.get("dividendRate"), 0) or 0,
                "currency":  item.get("Currency") or item.get("currency") or "USD",
            })
        if divs:
            print(f"[src_fundclear_div] ✅ {code} {len(divs)} 筆配息")
    except Exception as e:
        print(f"[src_fundclear_div] {code}: {e}")
    return divs


# ══════════════════════════════════════════════════════════════════════
# v13.7 替代資料來源：基金公司官網 Adapters
# 網路確認可存取：安聯投信 tw.allianzgi.com 對 Colab IP 無限制
# ══════════════════════════════════════════════════════════════════════

# ── 基金公司官網 URL 映射表 ───────────────────────────────────────────
_FUND_COMPANY_URLS = {
    # 安聯投信境內基金（ACTI/ACCP/ACDD 前綴）
    "ACTI71":  "https://tw.allianzgi.com/zh-tw/products-solutions/taiwan-onshore/allianz-global-investors-income-and-growth-balanced-fund-a1-twd",
    "ACTI98":  "https://tw.allianzgi.com/zh-tw/products-solutions/taiwan-onshore/allianz-global-investors-income-and-growth-balanced-fund-a-twd",
    "ACTI94":  "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACTI94",
    "ACCP138": "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACCP138",
    "ACDD19":  "https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACDD19",
}

# 安聯投信境內基金「ifund」電子交易平台淨值查詢（HTML 可抓）
_ALLIANZ_NAV_ENDPOINT = "https://ifund.allianzgi.com.tw/WebNav.aspx"
# 安聯投信 JSON 淨值 API（部分基金有效）
_ALLIANZ_NAV_API = "https://tw.allianzgi.com/api/sitecore/fund/GetFundNav"


def _infer_year_for_mmdd(mo: int, da: int, today) -> int:
    """「近30日」頁 MM/DD 條目補年份:MM/DD ≤ 今日 → 今年,否則 → 去年。

    v19.333 review F5 抽出成純函式(可測)。`today` 必須是 **TW 時區**的
    date(§4.5 慣例) — 用 UTC today 會在「TW 已跨日、UTC 未跨日」的 8 小時窗
    把當日條目錯置到去年(≈365 天位移)。跨年語意本身正確:1 月讀到 12/28
    → 去年 12/28(近30日窗內最近的一個 12/28)。
    """
    return today.year if (mo, da) <= (today.month, today.day) else today.year - 1


def _src_allianzgi_nav(code: str) -> pd.Series:
    """
    安聯投信官網歷史淨值抓取。
    Colab IP 對 allianzgi.com 無限制，是 ACTI 系列最可靠的來源。
    路徑：_ALLIANZ_NAV_API JSON API（2000d 歷史）→ MoneyDJ yp004002 完整歷史頁

    JSON API 結果只在 ≥90 筆時才短路返回；若只拿到近30日資料，繼續往 MoneyDJ yp004002 嘗試，
    確保回傳序列涵蓋至少 3 個月歷史（>90 交易日），而非僅最近 30 天。
    兩段都不足 90 筆時，回傳**兩者中較長的那一段**，並標上它自己的來源（不合併）。

    ── 2026-08-11 兩項修正（§1 / §2.2）─────────────────────────────────
    **(a) 三段共用 `rows` dict → 改成每段各自獨立。**
    原本 `rows` 在函式開頭建立一次，第 1 段（AllianzGI JSON API）、第 2 段
    （**MoneyDJ** tcbbankfund yp004002）、第 3 段都往同一個 dict 塞，兩個後果：
      - 第 2 段的 `len(rows) >= 90` 算的是「API 筆數 + MoneyDJ 筆數」的聯集 →
        回傳一條**兩個不同來源拼起來**的序列，標籤卻是單一來源。§2.1 明文
        「衝突時上層贏，禁止平均」—— 這裡比平均更糟：是按日期 key **靜默覆寫**，
        同一天兩源給不同值時後寫的贏，且無任何 log。
      - 這種序列單調遞增、全正值、筆數充足，**會通過 §4.2 的全部不變量斷言** ——
        是本 repo 最難察覺的一類假資料。

    **(b) 刪除原第 3 段（ifund/tw HTML「近30日」fallback）。**
    它請求的 `_ALLIANZ_NAV_ENDPOINT` / fund-nav-search **不帶基金代碼**，
    整段程式碼裡 `code` 只出現在 print 字串中：請求不帶 code、解析不比對 code、
    返回不驗證 code，卻在 `len(rows) >= 5` 時把「頁面上任何含『淨值』字樣的表格」
    當成 `code` 這一檔的 NAV 回傳。§1「寧可炸掉，不可造假」→ 無法證明資料屬於
    這一檔就不該回傳。`s.attrs["source"]` 標的是主機名，證明不了任何事（§2.2）。
    近30日的需求本來就有正牌來源 `_src_nav_30day`（waterfall 2f 順位），不缺這一條。

    ⚠️ (a)(b) 必須與「漏括號」同批交付：括號 bug 過去意外保證了 `rows` 進入
    第 2/3 段時恆為空，把共用容器的問題遮蔽住；修好括號等於解鎖它。
    """
    import datetime as _dt_az
    import re as _re2
    _today_az = _dt_az.date.today()
    _start_az = (_today_az - _dt_az.timedelta(days=2000)).strftime("%Y%m%d")
    # 每段各自獨立的容器 —— 刻意**不共用**，理由見 docstring (a)。
    _rows_api: dict = {}
    _rows_mj: dict = {}

    # ── 1. JSON API（支援 2000d 完整歷史）─────────────────────────────────────
    # 嘗試多種 request body 格式，因 Sitecore API 參數名稱不一定一致
    for _body in [
        {"FundCode": code, "Days": 2000},
        {"fundCode": code, "days": 2000},
        {"FundCode": code, "Period": "MAX"},
    ]:
        try:
            _api_resp = requests.post(
                _ALLIANZ_NAV_API,
                json=_body,
                headers={**HDR_JSON, "Referer": "https://tw.allianzgi.com/"},
                timeout=15,
                # 2026-08-11:此處原本寫 `proxies=_proxies, verify=_ssl_verify`
                # —— **漏了兩對括號**,傳進去的是 infra.proxy 的**函式物件**而非
                # 呼叫結果。requests 在 `merge_environment_settings()` 會對 proxies
                # 呼叫 `.get()`,函式沒有 `.get` → AttributeError 在「HTTP 送出之前」
                # 就被下面的 `except Exception` 接走,只印一行 log。
                # 後果:本區塊(安聯官方 JSON API,ACTI/ACCP/ACDD/ACTT + TLZF9/ANZ89
                # 唯一能拿 2000 天歷史的**非 MoneyDJ** 來源)**從未真的送出過請求**,
                # 三種 body 格式全都在同一行掛掉。全庫其餘 15 個呼叫點都寫 `()`,
                # 只有這行漏 —— 由 tests/test_nav_waterfall_no_overwrite.py::
                # test_proxy_helpers_are_called_not_passed_as_functions 守(AST 掃描)。
                proxies=_proxies(), verify=_ssl_verify(),
            )
            if not (_api_resp and _api_resp.status_code == 200):
                continue
            _api_data = _api_resp.json()
            _nav_list = (
                _api_data.get("Data") or _api_data.get("data") or
                _api_data.get("NavList") or _api_data.get("navList") or
                _api_data.get("Items") or _api_data.get("items") or
                (_api_data if isinstance(_api_data, list) else [])
            )
            _rows_api = {}      # 每個 body 格式各自重算
            for _item in (_nav_list if isinstance(_nav_list, list) else []):
                _dt_str = str(
                    _item.get("Date") or _item.get("date") or
                    _item.get("NavDate") or _item.get("navDate") or ""
                )[:10]
                _nav_val = safe_float(
                    _item.get("Nav") or _item.get("nav") or
                    _item.get("NAV") or _item.get("Price") or "")
                if _dt_str and _nav_val and _nav_val > 0:
                    try:
                        _rows_api[pd.Timestamp(_dt_str)] = _nav_val
                    except Exception:
                        pass
            # Accept JSON API result only when it clearly covers >90 days of history.
            # A 30-entry result means the API ignored `Days` and returned only recent data;
            # fall through to the yp004002 path which reliably provides full history.
            if len(_rows_api) >= 90:
                s = pd.Series(_rows_api).sort_index()
                print(f"[src_allianz] ✅ {code} {len(s)} 筆（JSON API {list(_body.keys())[1]}）")
                s.attrs["source"] = "AllianzGI:JSON_API"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
            if _rows_api:
                # 2026-08-11:原為 `rows.update(_rows_api)` —— 把 API 結果倒進與
                # 第 2 段(MoneyDJ)共用的容器,見 docstring (a)。改成留在自己的
                # `_rows_api` 裡,由函式結尾單獨評估、單獨標來源。
                print(f"[src_allianz] ⚠ {code} JSON API 只得 {len(_rows_api)} 筆，繼續嘗試 yp004002")
                break  # Got some data from API; no point retrying other body formats
        except Exception as _api_e:
            print(f"[src_allianz] JSON API fail({code}, {list(_body.keys())}): {_api_e}")

    # ── 2. MoneyDJ yp004002 完整歷史淨值頁（2000d 視窗，同 orchestration 2d 路徑）──
    # 境內 ACTI/ACCP/ACDD 使用 yp010000；境外走 yp010001。
    try:
        _pages_az = get_page_types_to_try(
            "yp010000" if _is_domestic_code(code) else "yp010001"
        )
        _params_az = {"A": code, "B": _start_az, "C": _today_az.strftime("%Y%m%d")}
        for _pg_az in _pages_az:
            _hdr_az = {**HDR, "Referer": f"https://tcbbankfund.moneydj.com/funddj/ya/{_pg_az}.djhtm?a={code}"}
            _rr = fetch_url_with_retry(
                "https://tcbbankfund.moneydj.com/funddj/yf/yp004002.djhtm",
                headers=_hdr_az, params=_params_az, timeout=25, retries=2,
            )
            if not (_rr and is_valid_moneydj_page(_rr.text)):
                print(f"[src_allianz] yp004002 {code} page={_pg_az} → 無效，換頁型")
                continue
            soup_az = BeautifulSoup(_rr.text, "lxml")
            for tbl in soup_az.find_all("table"):
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        dt_t = cells[0].get_text(strip=True)
                        nv_t = cells[1].get_text(strip=True).replace(",", "")
                        if _re2.match(r"\d{4}/\d{2}/\d{2}", dt_t):
                            v = safe_float(nv_t)
                            if v and v > 0:
                                try:
                                    _rows_mj[pd.Timestamp(dt_t)] = v
                                except Exception as _e_mj_row:
                                    # §1:不可靜默吞(原為 except: pass)
                                    print(f"[src_allianz] yp004002 日期解析跳過 "
                                          f"{dt_t}: {_e_mj_row}")
            if len(_rows_mj) >= 90:
                s = pd.Series(_rows_mj).sort_index()
                print(f"[src_allianz] ✅ {code} {len(s)} 筆（MoneyDJ yp004002）")
                s.attrs["source"] = "AllianzGI:moneydj_hist"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
            break  # Only try the first working page type
    except Exception as _mj_e:
        print(f"[src_allianz] yp004002 fail({code}): {_mj_e}")

    # ── 3.（2026-08-11 刪除）原「ifund / tw.allianzgi HTML 近30日」fallback ──
    # 刪除理由見 docstring (b)：該段請求的 URL **不帶基金代碼**，`code` 在整段裡
    # 只出現在 print 字串中，卻把「頁面上任何含『淨值』字樣的表格」當成 `code`
    # 這一檔的 NAV 回傳 → §1 造假 + §2.2 血緣錯標。近30日的需求另有正牌來源
    # `_src_nav_30day`（waterfall 2f 順位，URL 帶 `?a={code}`）。
    #
    # ── 3'. 兩段都不足 90 筆 → 回傳**較長的那一段**，標它自己的來源 ─────────
    # 刻意**不合併** `_rows_api` 與 `_rows_mj`：兩者分屬 AllianzGI 與 MoneyDJ，
    # 發布延遲不同（§2.3），按日期 key 混寫會產生「通過所有不變量斷言的假序列」。
    # §2.1「衝突時上層贏，禁止平均」→ 這裡直接取單一來源，不做任何跨源填補。
    # ⚠️ tie-break 語意:`max` 平手時取**第一個**,所以 list 順序 = 來源優先權。
    # AllianzGI 官方 API 排在 MoneyDJ 之前(§2.1 T1/T2 高於 T3)。**重排這個 list
    # 會靜默改變來源優先權**,不是純排版。
    _partials = [
        (_rows_api, "AllianzGI:JSON_API:partial"),
        (_rows_mj,  "AllianzGI:moneydj_hist:partial"),
    ]
    _best_rows, _best_tag = max(_partials, key=lambda _t: len(_t[0]))
    if len(_best_rows) >= 5:
        s = pd.Series(_best_rows).sort_index()
        print(f"[src_allianz] ⚠ {code} 兩段皆 <90 筆，取較長者 "
              f"{len(s)} 筆（{_best_tag}）")
        s.attrs["source"] = _best_tag
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return s
    print(f"[src_allianz] ❌ {code} 無可用資料"
          f"（API {len(_rows_api)} 筆 / yp004002 {len(_rows_mj)} 筆）")
    return pd.Series(dtype=float)


def _src_allianzgi_meta(code: str) -> dict:
    """
    安聯投信官網基本資料 + 最新淨值。
    tw.allianzgi.com 對 Colab 可用。

    ── 2026-08-11 §1 / §2.2 修正：加上「這頁真的是這一檔嗎」的驗證 ──────
    原本這裡請求的 `_ALLIANZ_NAV_ENDPOINT`（`https://ifund.allianzgi.com.tw/WebNav.aspx`）
    **不帶基金代碼**，`code` 在整個函式裡只出現在 print 字串中：請求不帶 code、
    解析不比對 code、回傳不驗證 code，卻把「頁面上任何含『基金名稱』或『淨值』的
    表格」當成 `code` 這一檔的 `fund_name` / `nav_latest` / `inception_date` /
    `mgmt_fee` / `total_expense_ratio` 回傳，還標 `source="AllianzGI:ifund_meta"`。

    這比同批刪掉的 `_src_allianzgi_nav` 第 3 段更危險，因為它污染的是**meta**：
    - `inception_date` →  3-3-3 的「成立滿 3 年」條件
    - `nav_latest` → KPI 卡的最新淨值
    - `total_expense_ratio` → 費用率比較
    而呼叫點 `fund_orchestration.py` 的條件是
    `if not meta.get("fund_name") and _is_domestic_code(_code)` ——
    **對所有境內代碼觸發**，user 的 AC* 持倉全中。

    修法（刻意不整段刪）：
    1. URL 帶上 `FundCode`，給端點一個回正確資料的機會；
    2. **回傳前驗證頁面內容真的提到 `code`**，否則一律 `{}` + 大聲 log。
       若端點忽略 `FundCode`（很可能），驗證就會擋下來 → 退化成「沒有這個來源」，
       而不是「回別檔基金的資料」。§1：寧可沒有，不可造假。
    3. `is_valid_moneydj_page` 靠不住（只要頁面出現「淨值/基金/日期/績效/配息/除息」
       任兩個中文詞就回 True），真正的守門員是第 2 點。
    """
    meta = {}
    # 優先 ifund 平台
    try:
        _url_meta = f"{_ALLIANZ_NAV_ENDPOINT}?FundCode={code.upper().strip()}"
        r = fetch_url_with_retry(_url_meta, timeout=15, retries=2)
        if r and code.upper().strip() not in (r.text or "").upper():
            # §1：無法證明這頁屬於這一檔 → 不回傳任何欄位
            print(f"[src_allianz_meta] ⛔ {code}：ifund 頁面內容未提及此代碼，"
                  f"拒絕當成本檔資料回傳（避免跨基金污染）")
            return {}
        if r and is_valid_moneydj_page(r.text):
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "基金名稱" not in txt and "淨值" not in txt:
                    continue
                rows_map = {}
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        rows_map[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)
                if rows_map:
                    meta["fund_name"] = rows_map.get("基金名稱", "")
                    meta["nav_latest"] = safe_float(rows_map.get("最新淨值") or rows_map.get("淨值"))
                    meta["currency"] = rows_map.get("計價幣別", "TWD")
                    # 成立日期（多個可能標籤）
                    import re as _re_m
                    _inc_raw = (rows_map.get("成立日期") or rows_map.get("設立日期") or
                                rows_map.get("成立日") or rows_map.get("基金成立日") or "")
                    if _inc_raw:
                        _inc_m = _re_m.search(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", _inc_raw)
                        if _inc_m:
                            meta["inception_date"] = _inc_m.group().replace("/", "-")
                    # 最高經理費 / 管理費
                    _fee_raw = (rows_map.get("最高經理費") or rows_map.get("經理費") or
                                rows_map.get("管理費") or "")
                    if _fee_raw:
                        _fee_v = safe_num(_fee_raw)
                        if _fee_v is not None:
                            meta["mgmt_fee"] = _fee_v
                    # v19.368 7/8:保管費(TER 估計第 2 主成分)
                    _cust_raw = (rows_map.get("最高保管費") or rows_map.get("保管費") or "")
                    if _cust_raw:
                        _cust_v = safe_num(_cust_raw)
                        if _cust_v is not None:
                            meta["custody_fee"] = _cust_v
                    # v19.370 真實 TER:同表若揭露「總費用率」→ 收真值(消費端優先於估計)
                    _ter_raw = (rows_map.get("總費用率") or rows_map.get("總開支比率") or
                                rows_map.get("經常性費用") or "")
                    if _ter_raw:
                        _ter_v = safe_num(_ter_raw)
                        if _ter_v is not None and 0 < _ter_v <= 10:
                            meta["total_expense_ratio"] = _ter_v
                    if meta.get("fund_name"):
                        print(f"[src_allianz_meta] ✅ {code}: {meta['fund_name'][:20]}")
                        # F-PROV-1 phase 15 v19.101 — provenance(schema-additive)
                        meta["source"] = "AllianzGI:ifund_meta"
                        meta["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                        return meta
    except Exception as e:
        print(f"[src_allianz_meta] {e}")
    return meta


# ════════════════════════════════════════════════════════════
# v11.0 B-9b-3：cnyes / cache_files / bank_platform / Morningstar /
#              Yahoo / Alphavantage adapters（從 fund_fetcher.py 抽出）
# 17 函式（13 _src_* + 4 _cnyes_* / _morningstar_search_secid 等 helper）
# ════════════════════════════════════════════════════════════

# ── SSOT:外部 API base(v19.279 收口 inline 重複)──────────────────────
# 同檔多 fetcher 共用同一 base path;各 fetcher 以 f"{BASE}/..." 串接不同 path。
# 收口前 cnyes base ×4 / Morningstar tools base ×2 散落 inline,現集中於此。
# 註:`lt.morningstar.com/.../SecuritySearch.ashx`(secId 搜尋)為**不同 host**,
#     不併入此 base(語意:搜尋 API vs 資料 API)。
_CNYES_FUND_API = "https://fund.api.cnyes.com/fund/api/v2/funds"   # 鉅亨網基金 REST
_MS_TOOLS_REST = "https://tools.morningstar.co.uk/api/rest.svc"    # Morningstar UK tools(token-free)

# ── 來源2：鉅亨網 API（無 IP 限制，伺服器可用）────────────────────────
def _cnyes_parse_navs(navs: list) -> dict:
    """解析 cnyes NAV 列表，回傳 {timestamp: float}"""
    rows = {}
    for item in navs:
        try:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                ts = pd.Timestamp(int(item[0]), unit="ms")
                v  = safe_float(item[1])
                if v and v > 0:
                    rows[ts.normalize()] = v
            elif isinstance(item, dict):
                d_val = (item.get("date") or item.get("Date")
                         or item.get("nav_date") or "")
                n_val = safe_float(item.get("nav") or item.get("NAV")
                                   or item.get("value"))
                if d_val and n_val:
                    rows[pd.Timestamp(str(d_val)[:10])] = n_val
        except Exception:
            pass
    return rows


def _cnyes_resolve_code(moneydj_code: str) -> list:
    """
    v6.11: 透過 cnyes search API 找出對應的 cnyes 基金代碼列表。
    新增 TDCC→cnyes 名稱橋接：保險平台代碼（如 TLZF9）在 cnyes 無法直接搜到，
    改用 TDCC 3-2 取得基金中文名稱，再用名稱搜 cnyes。
    回傳所有候選 cnyes 代碼，首位最優先。
    """
    from urllib.parse import quote as _uquote
    _code = moneydj_code.upper().strip()
    candidates = [_code, _code.lower()]   # 先試原始代碼
    _hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://fund.cnyes.com/",
    }

    def _cnyes_search(key: str, limit: int = 10) -> list:
        """呼叫 cnyes search API，回傳 fundCode 列表"""
        try:
            url = (f"{_CNYES_FUND_API}/search"
                   f"?key={_uquote(key)}&limit={limit}")
            r = requests.get(url, headers=_hdrs, timeout=10, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code == 200:
                data = r.json()
                # v19.337 review D:API 回 "data": null 時 .get("data", {}) 回 None
                # (key 在,default 不生效)→ None.get() AttributeError 被寬 except 吞,
                # 失敗被誤判為無資料。先判型再取。
                _d_raw = data.get("data")
                _d_dict = _d_raw if isinstance(_d_raw, dict) else {}
                items = (_d_dict.get("list")
                         or (_d_raw if isinstance(_d_raw, list) else None)
                         or data.get("items")
                         or [])
                if isinstance(items, list):
                    return [
                        (item.get("fundCode") or item.get("code")
                         or item.get("id") or "")
                        for item in items
                        if (item.get("fundCode") or item.get("code") or item.get("id"))
                    ]
        except Exception as _e:
            print(f"[cnyes_search] key={key!r}: {_e}")
        return []

    # Step 1: 直接用原始代碼搜
    found = _cnyes_search(_code)
    for c in found:
        if c and c not in candidates:
            candidates.append(c)
    print(f"[cnyes_search] {_code} 直接搜 → 候選: {candidates[:5]}")

    # Step 2: 若直接搜無新代碼，嘗試 TDCC 3-2 名稱橋接（適用保險平台代碼）
    if len(candidates) <= 2:
        tdcc_name = _tdcc_resolve_fund_name(_code)
        if tdcc_name:
            # 用基金名稱前 20 字元搜 cnyes（避免過長關鍵字無結果）
            key_short = tdcc_name[:20]
            found_by_name = _cnyes_search(key_short, limit=5)
            for c in found_by_name:
                if c and c not in candidates:
                    candidates.append(c)
            print(f"[cnyes_search] {_code} 名稱橋接 '{key_short}' → 候選: {candidates[:8]}")

    return candidates


def fetch_nav_cnyes(code: str) -> pd.Series:
    """
    鉅亨網歷史淨值（v6.7）。
    新增：search API 先找正確的 cnyes 代碼，再用代碼取歷史淨值。
    不依賴 MoneyDJ，Streamlit Cloud 可存取。
    """
    import datetime as _dt2
    import time as _time2
    end_d    = _dt2.date.today()
    # v19.281:400d(~13 月)→ 2000d(~5.5 年),讓 3Y/5Y 指標可算(user 反饋
    # MoneyDJ 有 3-5 年但本站只顯示 <1 年)。cnyes API 支援任意起訖日。
    start_d  = end_d - _dt2.timedelta(days=2000)
    end_ms   = int(_time2.mktime(end_d.timetuple())) * 1000
    start_ms = int(_time2.mktime(start_d.timetuple())) * 1000

    # Step 1: 解析候選代碼（含 search fallback）
    candidates = _cnyes_resolve_code(code)

    _hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://fund.cnyes.com/",
    }
    for _cand in candidates:
        _url = (f"{_CNYES_FUND_API}/{_cand}"
                f"/nav?start={start_ms}&end={end_ms}")
        try:
            r = requests.get(_url, headers=_hdrs, timeout=15, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code != 200:
                continue
            data = r.json()
            # v19.337 review D:同上 — "data": null → None.get() AttributeError;先判型
            _d_raw = data.get("data")
            _d_dict = _d_raw if isinstance(_d_raw, dict) else {}
            navs = (_d_dict.get("nav")
                    or _d_dict.get("navs")
                    or data.get("items")
                    or [])
            if not navs and isinstance(data, list):
                navs = data
            rows = _cnyes_parse_navs(navs)
            if rows:
                print(f"[cnyes_nav] ✅ {code}→{_cand} {len(rows)} 筆")
                s = pd.Series(rows).sort_index()
                # F-PROV-1 phase 16 v19.102 — provenance(Series.attrs)
                s.attrs["source"] = f"Cnyes:fund.api:v2/funds/{_cand}/nav"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
        except Exception as _e:
            print(f"[cnyes_nav] {_cand}: {_e}")

    return pd.Series(dtype=float)


def fetch_div_cnyes(code: str) -> list:
    """
    鉅亨網配息資料（REST API）。
    """
    divs = []
    _code = code.upper().strip()
    try:
        url = f"{_CNYES_FUND_API}/{_code}/dividend"
        r = requests.get(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            "Accept": "application/json",
            "Referer": "https://fund.cnyes.com/",
        }, timeout=15, proxies=_proxies(), verify=_ssl_verify())
        if r.status_code == 200:
            data = r.json()
            items = (data.get("data") or data.get("items") or [])
            if isinstance(items, list):
                for item in items:
                    d = (item.get("date") or item.get("exDate") or "")
                    amt = safe_float(item.get("dividend") or item.get("amount"))
                    if d and amt is not None:
                        divs.append({
                            "date": str(d)[:10],
                            "amount": amt,
                            "yield_pct": safe_float(item.get("yieldRate") or item.get("yield_pct"), 0),
                        })
    except Exception as _e:
        print(f"[cnyes_div] {_code}: {_e}")
    # v19.226 F-PROV-1 B2:list-of-dict 每 element 加 source + fetched_at(§2.2)
    if divs:
        _fa = pd.Timestamp.now('UTC').isoformat()
        for _d in divs:
            _d["source"] = f"Cnyes:dividend:{_code}"
            _d["fetched_at"] = _fa
    return divs


# ── v19.276 cnyes 持股 fallback(MoneyDJ yp013xxx 全失敗時的替代源)─────────
# 設計脈絡:user 反饋 ACTI71 / JFZN3 等基金 MoneyDJ 持股頁全空(子網域限制 /
# multi-asset 透明度不足),要求「找其他替代方案爬持股」。cnyes 已是現用 JSON
# API(NAV / 配息走同一 base URL + NAS proxy),為架構一致性最高的 fallback。
#
# ⚠️ cnyes 持股端點 JSON shape 無法於開發環境(local proxy 403)實測 →
#    採防禦式「多 endpoint × 多欄位名」解析:猜錯 → 回空 + log 真實 keys
#    (§1 Fail Loud:絕不崩潰、絕不偽造;production log 揭露真 shape 供下一輪精修)。
#    worst case = 跟現在一樣空,但多一條 fallback 路徑。
_CNYES_HOLD_NAME_KEYS = ("name", "stockName", "securityName", "holdingName",
                         "comName", "companyName", "secName", "fundName")
_CNYES_HOLD_SECTOR_KEYS = ("industry", "sector", "category", "categoryName",
                           "industryName", "type")
_CNYES_PCT_KEYS = ("weight", "ratio", "pct", "percentage", "percent",
                   "proportion", "rate", "weighting")
_CNYES_AMOUNT_KEYS = ("amount", "marketValue", "value", "netAsset")
# 持股陣列在 payload 中可能掛的 key
_CNYES_HOLD_LIST_KEYS = ("holdings", "topHoldings", "stockHoldings",
                         "holdingList", "topHolding", "stocks", "holding")
# 產業 / 資產 / 區域配置陣列可能掛的 key
_CNYES_SECTOR_LIST_KEYS = ("industryAllocation", "sectorAllocation",
                           "assetAllocation", "regionAllocation",
                           "industryList", "assetList", "allocation",
                           "industry", "sector", "asset", "region")
# 配置項額外名稱欄位(產業/資產/區域名)
_CNYES_SECTOR_NAME_KEYS = (_CNYES_HOLD_NAME_KEYS +
                           ("industryName", "sectorName", "assetName",
                            "categoryName", "regionName", "className"))


def _cnyes_pick(item: dict, keys):
    """從 dict 依候選 key 順序取第一個非空值;查無回 None。"""
    if not isinstance(item, dict):
        return None
    for k in keys:
        v = item.get(k)
        if v not in (None, "", [], {}):
            return v
    return None


def _cnyes_parse_holdings(data) -> dict:
    """
    防禦式解析 cnyes 持股 JSON(多 shape)。
    回傳 {top_holdings:[{name,sector,pct}], sector_alloc:[{name,pct,amount}],
          data_date}(任一項可缺;全缺回 {})。
    不寫 provenance(由 caller fetch_holdings_cnyes 統一加)。
    """
    out: dict = {}
    # 拆 payload:優先 data["data"](dict/list),否則 data 本體
    payload = data
    if isinstance(data, dict):
        _inner = data.get("data")
        payload = _inner if isinstance(_inner, (dict, list)) else data

    def _as_list(node, keys):
        if not isinstance(node, dict):
            return []
        for k in keys:
            v = node.get(k)
            if isinstance(v, list) and v:
                return v
        return []

    # ── top_holdings ──
    if isinstance(payload, list):
        hold_list = payload                       # data 直接是 holdings 陣列
    else:
        hold_list = _as_list(payload, _CNYES_HOLD_LIST_KEYS)
    holdings = []
    for item in hold_list:
        if not isinstance(item, dict):
            continue
        name = _cnyes_pick(item, _CNYES_HOLD_NAME_KEYS)
        pct = safe_float(_cnyes_pick(item, _CNYES_PCT_KEYS))
        if name and pct is not None and 0 < pct < 100:
            sector = _cnyes_pick(item, _CNYES_HOLD_SECTOR_KEYS) or ""
            holdings.append({"name": str(name).strip(),
                             "sector": str(sector).strip(),
                             "pct": pct})
    if holdings:
        out["top_holdings"] = holdings[:10]

    # ── sector / asset / region allocation ──
    sector_list = _as_list(payload, _CNYES_SECTOR_LIST_KEYS)
    sectors = []
    for item in sector_list:
        if not isinstance(item, dict):
            continue
        name = _cnyes_pick(item, _CNYES_SECTOR_NAME_KEYS)
        pct = safe_float(_cnyes_pick(item, _CNYES_PCT_KEYS))
        if name and pct is not None and 0 < pct <= 100:
            amount = safe_float(_cnyes_pick(item, _CNYES_AMOUNT_KEYS)) or 0.0
            sectors.append({"name": str(name).strip(),
                            "pct": pct, "amount": amount})
    if sectors:
        out["sector_alloc"] = sectors

    # ── data_date(盡力抓,缺無妨)──
    _dd = None
    if isinstance(data, dict):
        _dd = data.get("dataDate") or data.get("date")
        if not _dd and isinstance(data.get("data"), dict):
            _dd = data["data"].get("dataDate") or data["data"].get("date")
    if _dd:
        out["data_date"] = str(_dd)[:10]

    return out


def fetch_holdings_cnyes(code: str, diag: "list | None" = None) -> dict:
    """
    鉅亨網持股 / 資產配置 fallback(REST API)。MoneyDJ yp013xxx 全失敗時的替代源。
    回傳契約對齊 nav_metrics.fetch_holdings:
      {data_date, sector_alloc:[{name,pct,amount}], top_holdings:[{name,sector,pct}],
       source, fetched_at}
    抓不到 → {}(§1 Fail Loud:不偽造,log 真實 JSON keys 供 production 精修)。
    L1 純 fetcher,不自帶 cache(由 orchestrator fetch_holdings 的 @_daily_cache 統管)。

    diag:可選 list,逐步記錄抓取診斷(供 UI 顯示「有沒有抓到、抓到什麼」)。
    """
    import sys as _sys_c

    def _d(msg: str) -> None:
        if diag is not None:
            diag.append(f"cnyes｜{msg}")

    _code = (code or "").upper().strip()
    if not _code:
        _d("空代碼")
        return {}
    candidates = _cnyes_resolve_code(_code)
    _d(f"代碼解析候選={candidates[:5]}")
    _hdrs = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json",
        "Referer": "https://fund.cnyes.com/",
    }
    # cnyes 持股端點名未驗證 → 多候選 resource path 嘗試
    _resources = ("portfolio", "holding", "holdings", "asset")
    for _cand in candidates:
        for _res in _resources:
            _url = f"{_CNYES_FUND_API}/{_cand}/{_res}"
            try:
                r = requests.get(_url, headers=_hdrs, timeout=15,
                                 proxies=_proxies(), verify=_ssl_verify())
                if r.status_code != 200:
                    if r.status_code != 404:
                        _d(f"{_cand}/{_res} HTTP {r.status_code}")
                    continue
                data = r.json()
            except Exception as _e:
                _d(f"{_cand}/{_res} 例外 {type(_e).__name__}")
                print(f"[cnyes_holdings] {_cand}/{_res}: {_e}", file=_sys_c.stderr)
                continue
            out = _cnyes_parse_holdings(data)
            if out.get("top_holdings") or out.get("sector_alloc"):
                out["source"] = f"Cnyes:{_res}:{_cand}"
                out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                _d(f"✅ {_cand}/{_res} top={len(out.get('top_holdings', []))} "
                   f"sector={len(out.get('sector_alloc', []))}")
                print(f"[cnyes_holdings] ✅ {code}→{_cand}/{_res} "
                      f"top={len(out.get('top_holdings', []))} "
                      f"sector={len(out.get('sector_alloc', []))}",
                      file=_sys_c.stderr)
                return out
            # 200 但 shape 不認得 → log 真實 keys(§1,production 揭露真 shape)
            _keys = (list(data.keys()) if isinstance(data, dict)
                     else f"list[{len(data)}]" if isinstance(data, list)
                     else type(data).__name__)
            _d(f"{_cand}/{_res} 200 但無持股 keys={_keys}")
            print(f"[cnyes_holdings] {_cand}/{_res} 200 但無可解析持股 keys={_keys}",
                  file=_sys_c.stderr)
    return {}


# ── v19.278 Morningstar 持股 / 資產配置 fallback(cnyes 之後的第二替代源)──────
# 設計脈絡:user 反饋 ACTI71 / JFZN3 / ACCP138 / TLZF9 等**保單平台代碼**的
# 多重資產 / 組合(FoF)基金,MoneyDJ + cnyes 都抓不到 granular 持股。這些基金
# (如 Allianz Income & Growth = ISIN LU0689472784)在 Morningstar **有**資料。
# 本專案已有 secId 基礎建設:`_MORNINGSTAR_SECID_MAP`(TLZF9/JFZN3 已硬編)+
# `_morningstar_search_secid`(名稱搜尋)+ token-free `tools.morningstar.co.uk`
# (NAV 已用,美國 IP 可達)。本 fetcher 借同一條路抓 portfolio。
#
# ⚠️ Morningstar holdings 端點 JSON shape / viewId 無法於開發環境(proxy 403)
#    實測 → 防禦式多 viewId × 多欄位名解析:猜錯 → 回空 + log 真實 keys
#    (§1 Fail Loud,production log 揭露真 shape 供下一輪精修)。
_MS_HOLD_NAME_KEYS = ("securityName", "name", "holdingName", "stockName",
                      "Name", "SecurityName")
_MS_PCT_KEYS = ("weighting", "weight", "netAssetPercent", "percent",
                "Weighting", "percentage", "marketValuePercentage")
_MS_ASSET_NAME_KEYS = ("assetClass", "type", "name", "categoryName",
                       "AssetClass", "Type", "label")
# holdings 陣列可能掛的 key(snapshot / portfolio view 各異)
_MS_HOLD_LIST_KEYS = ("holdingDetails", "HoldingDetails", "topHoldings",
                      "holdings", "Holdings", "holdingActiveShare")
# 資產配置陣列可能掛的 key
_MS_ASSET_LIST_KEYS = ("assetAllocation", "AssetAllocation", "allocationMap",
                       "assetAllocList", "portfolioAllocation", "breakdowns")


def _pool_secid_lookup(code: str) -> str:
    """選股池已存的 secId / ISIN → Morningstar secId(v19.498 備源)。查無 / 池不可用回 ""。

    - **1) 池直接存的 `morningstar_secid`**(user 自填 / 系統回存)—— 最準、免搜。
    - **2) 池存 `isin` → v19.491 screener 精確解析**(`_morningstar_screener_secid`)。
    幣別走池存 currency(空 → USD,screener 預設)。
    §1:池讀失敗(無 SA / 網路 / 池模組不可用)一律 try/except + log,回 "" 讓上層
    續走硬編表 / 名稱搜尋,**不因池不可用而擋掉持股**。
    §8.2:L1 sources → L1 pool_repository(lazy import 避循環;L1→L1 允許)。
    """
    import sys as _sys_p
    try:
        from repositories.pool_repository import (
            resolve_currency, resolve_isin, resolve_secid,
        )
    except Exception:  # noqa: BLE001 — 池模組不可用(理論上不會)→ 跳過備源
        return ""
    _code = (code or "").upper().strip()
    if not _code:
        return ""
    # 1) 池直接存的 secId(最準,免搜)
    try:
        _rs = resolve_secid(_code)
        if _rs and _rs[0]:
            return str(_rs[0]).strip()
    except Exception as _e:  # noqa: BLE001
        print(f"[ms_secid_pool] {_code} resolve_secid 失敗:{type(_e).__name__}: {_e}",
              file=_sys_p.stderr)
    # 2) 池存 ISIN → v19.491 screener 精確解析
    try:
        _isin = resolve_isin(_code) or ""
        if _isin:
            _ccy = (resolve_currency(_code) or "USD").upper() or "USD"
            _sid = _morningstar_screener_secid(_isin, _ccy)
            if _sid:
                print(f"[ms_secid_pool] {_code} ISIN={_isin}({_ccy})→secId={_sid}",
                      file=_sys_p.stderr)
                return _sid
    except Exception as _e:  # noqa: BLE001
        print(f"[ms_secid_pool] {_code} ISIN→screener 失敗:{type(_e).__name__}: {_e}",
              file=_sys_p.stderr)
    return ""


def _resolve_ms_secid(code: str) -> str:
    """保單平台代碼 → Morningstar secId。查無回 ""。

    v19.498 解析順序(高→低可信):
      1. 選股池已存 secId(user 自填 / 系統回存,最準)  ┐ v19.498 備源:MoneyDJ 保單子
      2. 選股池 ISIN → screener 精確解析(v19.491)      ┘ 網域對雲端美國 IP 被擋,這類
         FoF/保單基金改用池存 secId/ISIN 走 Morningstar(host 美國 IP 可達,NAV 同源已驗)。
      3. 硬編表 _MORNINGSTAR_SECID_MAP(TLZF9/JFZN3 等)
      4. TDCC 名稱橋接搜尋(最不準,最後退路)
    """
    _code = (code or "").upper().strip()
    # 1+2) 選股池備源(secId → ISIN screener)
    _pool_sid = _pool_secid_lookup(_code)
    if _pool_sid:
        return _pool_sid
    # 3) 硬編表
    _mapped = _MORNINGSTAR_SECID_MAP.get(_code, ("", ""))
    if _mapped[0]:
        return _mapped[0]
    # 4) 用 TDCC 中文名搜 Morningstar(英文名較準,但中文也試)
    try:
        _name = _tdcc_resolve_fund_name(_code) or ""
    except Exception:
        _name = ""
    for _q in (_name, _code):
        if _q:
            _sid = _morningstar_search_secid(_q)
            if _sid:
                return _sid
    return ""


def _ms_parse_holdings(data) -> dict:
    """防禦式解析 Morningstar security_details JSON(多 viewId shape)。

    回傳 {top_holdings:[{name,sector,pct}], sector_alloc:[{name,pct,amount}]}
    (任一可缺;全缺回 {})。Morningstar 多重資產基金主要有資產配置(股/債/
    可轉債/現金),個股 top holdings 視 fund 而定 — 兩者都盡力抓。
    """
    out: dict = {}
    # 攤平:Morningstar 常把資料包在 Portfolios[0] / Portfolio / data 之下
    payloads = [data]
    if isinstance(data, dict):
        for _k in ("Portfolios", "portfolios", "Portfolio", "portfolio",
                   "data", "Data"):
            _v = data.get(_k)
            if isinstance(_v, list) and _v:
                payloads.extend([x for x in _v if isinstance(x, dict)])
            elif isinstance(_v, dict):
                payloads.append(_v)

    def _find_list(keys):
        for node in payloads:
            if not isinstance(node, dict):
                continue
            for k in keys:
                v = node.get(k)
                if isinstance(v, list) and v:
                    return v
        return []

    # top_holdings
    holdings = []
    for item in _find_list(_MS_HOLD_LIST_KEYS):
        if not isinstance(item, dict):
            continue
        name = _cnyes_pick(item, _MS_HOLD_NAME_KEYS)
        pct = safe_float(_cnyes_pick(item, _MS_PCT_KEYS))
        if name and pct is not None and 0 < pct < 100:
            sector = _cnyes_pick(item, ("sector", "Sector", "industry",
                                        "country", "Country")) or ""
            holdings.append({"name": str(name).strip(),
                             "sector": str(sector).strip(), "pct": pct})
    if holdings:
        out["top_holdings"] = holdings[:10]

    # sector_alloc(多重資產基金主要靠這個 — 資產類別 %)
    sectors = []
    for item in _find_list(_MS_ASSET_LIST_KEYS):
        if not isinstance(item, dict):
            continue
        name = _cnyes_pick(item, _MS_ASSET_NAME_KEYS)
        pct = safe_float(_cnyes_pick(item, _MS_PCT_KEYS))
        if name and pct is not None and 0 < pct <= 100:
            sectors.append({"name": str(name).strip(), "pct": pct,
                            "amount": 0.0})
    if sectors:
        out["sector_alloc"] = sectors
    return out


def fetch_holdings_morningstar(code: str, diag: "list | None" = None) -> dict:
    """Morningstar 持股 / 資產配置 fallback(cnyes 之後的第二替代源)。

    回傳契約對齊 nav_metrics.fetch_holdings:
      {data_date, sector_alloc:[{name,pct,amount}], top_holdings:[{name,sector,pct}],
       source, fetched_at}
    抓不到 → {}(§1 Fail Loud)。token-free `tools.morningstar.co.uk`,美國 IP /
    NAS proxy 皆可達(NAV 同源已驗)。

    diag:可選 list,逐步記錄抓取診斷(供 UI 顯示)。
    """
    import sys as _sys_m

    def _d(msg: str) -> None:
        if diag is not None:
            diag.append(f"Morningstar｜{msg}")

    _code = (code or "").upper().strip()
    if not _code:
        _d("空代碼")
        return {}
    sec_id = _resolve_ms_secid(_code)
    if not sec_id:
        _d(f"{_code} 無 secId(選股池 secId/ISIN 無 + 映射表無 + 名稱搜尋失敗)"
           " —— 到選股池補 morningstar_secid 或 isin 即可走本備源")
        print(f"[ms_holdings] {_code}: 無 secId(池/映射表/ISIN/名稱搜尋皆失敗)",
              file=_sys_m.stderr)
        return {}
    _d(f"{_code} secId={sec_id}")
    _hdrs = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://tools.morningstar.co.uk/",
    }
    # viewId 未驗證 → 多候選嘗試(snapshot 含資產配置;portfolio view 含 holdings)
    _views = ("PortfolioSAL", "snapshot", "Portfolio")
    for _view in _views:
        _url = (f"{_MS_TOOLS_REST}/security_details/"
                f"{sec_id}?viewId={_view}&idtype=Morningstar"
                f"&responseViewFormat=json&languageId=en-GB")
        try:
            r = requests.get(_url, headers=_hdrs, timeout=15,
                             proxies=_proxies(), verify=_ssl_verify())
            if r.status_code != 200:
                _d(f"{_view} HTTP {r.status_code}")
                continue
            data = r.json()
        except Exception as _e:
            _d(f"{_view} 例外 {type(_e).__name__}")
            print(f"[ms_holdings] {sec_id}/{_view}: {_e}", file=_sys_m.stderr)
            continue
        out = _ms_parse_holdings(data)
        if out.get("top_holdings") or out.get("sector_alloc"):
            out["source"] = f"Morningstar:holdings:{sec_id}:{_view}"
            out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            _d(f"✅ {_view} top={len(out.get('top_holdings', []))} "
               f"sector={len(out.get('sector_alloc', []))}")
            print(f"[ms_holdings] ✅ {code}→{sec_id}/{_view} "
                  f"top={len(out.get('top_holdings', []))} "
                  f"sector={len(out.get('sector_alloc', []))}",
                  file=_sys_m.stderr)
            return out
        _keys = (list(data.keys()) if isinstance(data, dict)
                 else f"list[{len(data)}]" if isinstance(data, list)
                 else type(data).__name__)
        _d(f"{_view} 200 但無持股 keys={_keys}")
        print(f"[ms_holdings] {sec_id}/{_view} 200 但無可解析持股 keys={_keys}",
              file=_sys_m.stderr)
    return {}


def _src_cnyes_nav(code: str) -> pd.Series:
    """鉅亨網歷史淨值（REST API，無 IP 封鎖）"""
    try:
        s = fetch_nav_cnyes(code)
        if len(s) >= 10:
            print(f"[src_cnyes] ✅ {code} {len(s)} 筆")
            # F-PROV-1 phase 10 v19.96 — provenance(Series.attrs;若上游已設則保留)
            if "source" not in s.attrs:
                s.attrs["source"] = "Cnyes:fund_nav_api"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            return s
    except Exception as e:
        print(f"[src_cnyes] {code}: {e}")
    return pd.Series(dtype=float)


def _src_cnyes_div(code: str) -> list:
    """鉅亨網配息（REST API，無 IP 封鎖）"""
    try:
        divs = fetch_div_cnyes(code)
        if divs:
            print(f"[src_cnyes_div] ✅ {code} {len(divs)} 筆")
            return divs
    except Exception as e:
        print(f"[src_cnyes_div] {code}: {e}")
    return []


# ══════════════════════════════════════════════════════════════════════
# v6.18 銀行/保險平台代碼映射 + 直連抓取
# 使用者提供的真實 URL（從 Google 搜尋確認）：
#   TLZF9 = 安聯收益成長基金-AMg7月收總收益類股(美元)
#   各平台有各自後綴代碼，透過不同 domain 提供相同資料
# ══════════════════════════════════════════════════════════════════════

# 各基金代碼在不同銀行/保險平台的完整代碼（base_code: [(domain, full_code, page_type)]）
# page_type: "moneydj" = /w/wb/wb01.djhtm 格式; "taiwanlife" = 台灣人壽 .aspx 格式
_BANK_PLATFORM_CODES: dict = {
    "TLZF9": [
        # 銀行自有 domain（非 moneydj.com，IP 封鎖機率低）
        ("fund.hncb.com.tw",                "TLZF9-1180",        "moneydj_wb02"),  # 華南銀行
        ("fundchannelnew2.sinotrade.com.tw", "TLZF9-57C0060T",   "moneydj_wb01"),  # 永豐金
        ("fundrwd.entiebank.com.tw",         "TLZF9-24A7",        "moneydj_wb01"),  # 遠東銀行
        # 台灣人壽自有伺服器（.aspx 非 MoneyDJ 格式）
        ("178.taiwanlife.com",               "TLZF9-F1740",       "taiwanlife_mobile"),
        # MoneyDJ 子網域（Streamlit Cloud 可能封鎖）
        ("taishinlife.moneydj.com",          "TLZF9-AL001",       "moneydj_wb01"),  # 台新人壽
    ],
    "ANZ89": [
        ("fund.megabank.com.tw",             "ANZ89-1G11",         "moneydj_wb02"),  # 兆豐銀行（非 moneydj.com）
        ("chbfund.moneydj.com",              "ANZ89-3827",         "moneydj_wb01"),  # 彰化銀行
    ],
    "ACTI94": [
        ("fund.megabank.com.tw",             "ACTI94-8A22",        "moneydj_wr02"),  # 兆豐銀行（非 moneydj.com）
        ("cardif.moneydj.com",               "ACTI94-AB116",       "moneydj_wr02"),  # 卡迪夫人壽
    ],
    # v6.21: 新增 CTZP0/JFZN3/FLFM1 平台代碼（優先使用非 moneydj.com 域名）
    "CTZP0": [
        ("invest.fubonlife.com.tw",          "CTZP0-IGB5",         "moneydj_wb02"),  # 富邦人壽（非 moneydj.com，Streamlit Cloud 較可能可達）
        ("chubb.moneydj.com",                "CTZP0-BNUIV018",     "moneydj_wb01"),  # CHUBB
    ],
    "JFZN3": [
        ("fund.taipeifubon.com.tw",          "JFZN3-BIAJ",         "moneydj_wb01"),  # 台北富邦銀行（非 moneydj.com）
        ("chubb.moneydj.com",                "JFZN3-BSUJF060",     "moneydj_wb01"),  # CHUBB
    ],
    "FLFM1": [
        ("cardif.moneydj.com",               "FLFM1-PV045",        "moneydj_wb01"),  # 卡迪夫人壽（BNP Paribas）
    ],
}


def _src_cache_files(code: str) -> "pd.Series":
    """v6.19: 讀取 GitHub Actions 每日預存的 cache/nav/{CODE}.json。
    這是 Streamlit Cloud IP 被封鎖時的最終保障：GitHub Actions 每日抓取，
    Streamlit Cloud 讀快取，完全繞過 IP 封鎖問題。
    """
    import json as _json
    from pathlib import Path as _Path
    # v19.319 修路徑 bug:GitHub Actions 寫入 repo 根目錄 cache/nav/(scripts/fetch_nav_cache.py
    # CACHE_DIR = __file__.parent.parent / cache/nav)。本檔 = repositories/fund/sources.py,
    # 原 .parent 指到 repositories/fund/cache/nav(不存在)→ 永遠讀不到。parents[2] = repo 根。
    cache_file = _Path(__file__).resolve().parents[2] / "cache" / "nav" / f"{code}.json"
    if not cache_file.exists():
        return pd.Series(dtype=float)
    try:
        data = _json.loads(cache_file.read_text(encoding="utf-8"))
        history = data.get("history", [])
        if not history:
            return pd.Series(dtype=float)
        rows = {}
        for item in history:
            try:
                rows[pd.Timestamp(item["date"])] = float(item["nav"])
            except (KeyError, ValueError, TypeError):
                pass
        s = pd.Series(rows).sort_index()
        updated_at = data.get("updated_at", "")
        print(f"[cache_files] ✅ {code}: {len(s)} 筆 (更新時間: {updated_at[:10]})")
        # F-PROV-1 phase 15 v19.101 — provenance(Series.attrs)
        s.attrs["source"] = f"GitHubActions:cache/nav/{code}.json"
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        # 註:cache file 自帶 updated_at,代表 GH Actions 寫入時間,與本次讀取(fetched_at)不同維度
        if updated_at:
            s.attrs["cache_updated_at"] = updated_at

        # ── 2026-08-27 品質閘 ────────────────────────────────────────────
        # 本路徑原本**只檢查 history 非空**就回傳,而同一條 chain 的其他路徑:
        #   live(`fetch_nav` 迴圈)  → len >= 10 **且** validate_fund_nav()
        #   長歷史(`nav_metrics`)   → len >= 50 / 100
        #   下游(`fetch_fund_by_key`)→ len >= 20 才收
        # 唯獨這條照單全收。實測 cache/nav/TLZF9.json = 10 點橫跨 14.43 年、最大空窗
        # 2,029 天、密度 0.69 點/年 —— 拿去算 Sharpe / σ / 最大回撤(年化 ×√252,
        # 假設每點=1 交易日)出來的是看起來像數字的雜訊。
        #
        # 兩段式,刻意不對稱(§1 Fail Loud:讓它誠實,而不是讓它消失):
        #   Tier A「擋」 = **補回既有標準,不是新標準** —— 筆數不足 / schema 違反。
        #        下游本來就會丟掉 <10 點的序列,故可用性零損失。
        #   Tier B「不擋,標註疑義」= 密度 / 空窗 / 新鮮度。序列**照回**,只掛旗標。
        #        ⚠️ 這裡刻意不擋:本函式是「Streamlit Cloud 美國 IP 被上游封鎖時
        #        唯一還吐得出 NAV 的來源」,擋掉會把「數字可疑」變成「完全沒資料」,
        #        那是更糟的失效模式。10 點裡最新那筆仍是真的 NAV。
        # 門檻全走 SSOT(§3.3),來源與理由見 shared/data_quality.py。
        from shared.data_quality import assess_nav_cache_quality
        _q = assess_nav_cache_quality(s, cache_updated_at=updated_at)
        if not _q["usable"]:
            # Tier A:與 live 分支同一把尺 → 不合格就不要污染 fallback chain
            print(f"[cache_files] ⛔ {code}: {_q['reason']} → 視同無快取")
            return pd.Series(dtype=float)
        try:
            # Tier A(二):live 分支跑的 schema,這條路徑原本從未跑過
            from shared.schemas import validate_fund_nav
            validate_fund_nav(s)
        except Exception as _ve:
            print(f"[cache_files] ⛔ {code}: 快取 schema 驗證失敗 → 視同無快取:{_ve}")
            return pd.Series(dtype=float)
        # Tier B:放行,但把疑義掛在 attrs 上讓下游看得見(§2.2 provenance 同機制)
        s.attrs["nav_quality"] = _q
        s.attrs["nav_quality_code"] = _q["code"]
        s.attrs["supports_annualized"] = _q["supports_annualized"]
        if _q["reason"]:
            print(f"[cache_files] ⚠️ {code}: {_q['reason']}")
        return s
    except Exception as e:
        print(f"[cache_files] {code} 讀取失敗: {e}")
        return pd.Series(dtype=float)


def _src_bank_platform_nav(base_code: str) -> "pd.Series":
    """
    v6.18: 透過銀行/保險平台 domain 取歷史淨值。
    優先嘗試銀行自有 domain（非 moneydj.com，較不容易被 IP 封鎖）。
    支援 MoneyDJ 格式（wb01/wb02/wr02）與台灣人壽 mobile .aspx 格式。
    """
    import datetime as _dt_bp, re as _re_bp, urllib.request as _ur_bp
    # v19.339(第五份 review Bug 4):_parse_nav_html 定義於 nav_metrics,本模組
    # 頂層從未 import(P1-5 拆檔後 hasattr(sources,'_parse_nav_html')=False)→
    # wb 近30日 fallback 一走到就 NameError 被外層 except 吞掉,路徑從未生效。
    # nav_metrics 頂層 star-import 本模組 → 循環,故採呼叫端 lazy import。
    from repositories.fund.nav_metrics import _parse_nav_html
    _code = base_code.upper().strip()
    platforms = _BANK_PLATFORM_CODES.get(_code, [])
    if not platforms:
        return pd.Series(dtype=float)

    end_d   = _dt_bp.date.today()
    # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
    # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
    start_d = end_d - _dt_bp.timedelta(days=2000)
    _hdrs_bp = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,*/*;q=0.9",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }

    for domain, full_code, ptype in platforms:
        base_url = f"https://{domain}"
        rows = {}

        try:
            if ptype == "taiwanlife_mobile":
                # 台灣人壽自有平台（ASP.NET，非 MoneyDJ 格式）
                url = f"{base_url}/mobile/b1.aspx?a={full_code}"
                _hdrs_bp["Referer"] = f"https://{domain}/"
                req = _ur_bp.Request(url, headers=_hdrs_bp)
                with _ur_bp.urlopen(req, timeout=10) as resp:
                    raw = resp.read()
                html = raw.decode("utf-8", errors="replace")
                soup = BeautifulSoup(html, "lxml")
                for tbl in soup.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            _d = cells[0].get_text(strip=True)
                            _v = safe_float(cells[1].get_text(strip=True).replace(",", ""))
                            if _re_bp.match(r"\d{4}[/-]\d{1,2}[/-]\d{1,2}", _d) and _v:
                                try:
                                    rows[pd.Timestamp(_d.replace("/", "-"))] = _v
                                except Exception:
                                    pass
                if rows:
                    s = pd.Series(rows).sort_index()
                    print(f"[src_bank] ✅ {_code} @ 台灣人壽 mobile {len(s)} 筆")
                    # F-PROV-1 phase 14 v19.100 — provenance(Series.attrs)
                    s.attrs["source"] = f"BankPlatform:{domain}:taiwanlife_mobile"
                    s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                    return s

            elif ptype.startswith("moneydj_"):
                page = ptype.split("_")[1]  # wb01 / wb02 / wr02
                # 先試歷史 NAV（yp004002，400 天）
                hist_url = (f"{base_url}/funddj/yf/yp004002.djhtm"
                            f"?A={full_code}&B={start_d.strftime('%Y%m%d')}"
                            f"&C={end_d.strftime('%Y%m%d')}")
                _hdrs_bp["Referer"] = f"{base_url}/funddj/ya/{page}.djhtm?a={full_code}"
                r = fetch_url_with_retry(hist_url, headers=_hdrs_bp, timeout=12, retries=2)
                if r and is_valid_moneydj_page(r.text):
                    soup = BeautifulSoup(r.text, "lxml")
                    for tbl in soup.find_all("table"):
                        for row in tbl.find_all("tr"):
                            cells = row.find_all("td")
                            if len(cells) >= 2:
                                _d = cells[0].get_text(strip=True)
                                _v = safe_float(cells[1].get_text(strip=True).replace(",", ""))
                                if _re_bp.match(r"\d{4}/\d{2}/\d{2}", _d) and _v:
                                    try:
                                        rows[pd.Timestamp(_d)] = _v
                                    except Exception:
                                        pass
                    if len(rows) >= 10:
                        s = pd.Series(rows).sort_index()
                        print(f"[src_bank] ✅ {_code} @ {domain} hist {len(s)} 筆")
                        # F-PROV-1 phase 14 v19.100 — provenance(Series.attrs)
                        s.attrs["source"] = f"BankPlatform:{domain}:yp004002:{page}"
                        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                        return s

                # fallback：近30日頁（wb01/wb02）
                wb_url = f"{base_url}/w/wb/{page}.djhtm?a={full_code}"
                r2 = fetch_url_with_retry(wb_url, headers=_hdrs_bp, timeout=10, retries=2)
                if r2 and is_valid_moneydj_page(r2.text):
                    s2 = _parse_nav_html(r2.text)
                    if len(s2) >= 5:
                        print(f"[src_bank] ✅ {_code} @ {domain} wb {len(s2)} 筆（近30日）")
                        # F-PROV-1 phase 14 v19.100 — provenance(Series.attrs)
                        s2.attrs["source"] = f"BankPlatform:{domain}:{page}:30day"
                        s2.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                        return s2

        except Exception as _e_bp:
            print(f"[src_bank] {domain} {full_code}: {_e_bp}")

    return pd.Series(dtype=float)


# ══════════════════════════════════════════════════════════════════════
# v6.15 Morningstar 國際資料源（FLFM1/JFZN3 等跨國基金適用）
# 原理：MoneyDJ 保險子網域封鎖 Streamlit Cloud IP
#       → 改從 Morningstar 全球 API 抓取，無 IP 限制
# 介面仍顯示中文（欄位名稱/標籤不變）
# ══════════════════════════════════════════════════════════════════════

# Morningstar 搜尋 secId 快取（避免重複查）
_ms_secid_cache: dict = {}
# v19.473:同一次搜尋順手記下晨星回傳的**基金名稱 / 幣別**（供「只填代號+ISIN,其餘自動」）。
#   幣別藏在晨星基金名稱後綴（如 "…AMg7 USD"）—— 用它自動判幣別,免使用者填(§4.1 不硬給 USD)。
_ms_name_cache: dict = {}
_ms_ccy_cache: dict = {}
# v19.491:ISIN → secId 走 Morningstar **screener**(精確 ISIN filter)的正/負快取。
#   與 SecuritySearch(_ms_secid_cache)分開,鍵一律大寫 ISIN。
_ms_screener_cache: dict = {}

# 幣別 token（英文碼 + 常見中文詞）→ ISO 幣別。掃描晨星基金名稱命中第一個即用。
_CCY_FROM_NAME = {
    "USD": "USD", "美元": "USD", "美金": "USD",
    "TWD": "TWD", "台幣": "TWD", "新台幣": "TWD", "臺幣": "TWD",
    "EUR": "EUR", "歐元": "EUR",
    "HKD": "HKD", "港幣": "HKD", "港元": "HKD",
    "AUD": "AUD", "澳幣": "AUD", "澳元": "AUD",
    "GBP": "GBP", "英鎊": "GBP",
    "JPY": "JPY", "日圓": "JPY", "日元": "JPY",
    "SGD": "SGD", "新幣": "SGD",
    "CNY": "CNY", "RMB": "CNY", "人民幣": "CNY",
    "ZAR": "ZAR", "南非幣": "ZAR", "南非": "ZAR",
    "CAD": "CAD", "加幣": "CAD",
    "NZD": "NZD", "紐幣": "NZD",
    "CHF": "CHF", "瑞郎": "CHF", "瑞士法郎": "CHF",
}


def _ccy_from_fund_name(name: str) -> str:
    """從晨星基金名稱抓計價幣別(如 "…AMg7 USD" → USD);抓不到回 ""(§1 不猜,由呼叫端退 USD)。

    英文碼優先用**詞邊界**比對(避免 "USDX" 之類誤中);中文詞直接 substring。
    """
    import re as _re_ccy
    _n = str(name or "")
    if not _n.strip():
        return ""
    _up = _n.upper()
    for _tok, _ccy in _CCY_FROM_NAME.items():
        if _tok.isascii() and _tok.isalpha():          # 英文碼:詞邊界
            if _re_ccy.search(rf"\b{_tok}\b", _up):
                return _ccy
        elif _tok in _n:                                # 中文詞:直接 substring
            return _ccy
    return ""

# v6.21: 已知的 Morningstar secId 硬編碼映射（跳過搜尋步驟，避免 lt.morningstar.com 封鎖）
# secId 格式：0P 開頭的 Morningstar 全球 ID（也是 Yahoo Finance {secId}.F 的基礎）
# 來源驗證：透過 investing.com / Yahoo Finance / global.morningstar.com 確認
_MORNINGSTAR_SECID_MAP: dict = {
    "TLZF9": ("0P0001J5YG", "USD"),  # Allianz Income and Growth AMg7 USD（ISIN: LU-）
    "ANZ89": ("0P0000X7WR", "USD"),  # Allianz Income and Growth AM USD（ISIN: LU0820561818）
    "JFZN3": ("0P0001N4II", "USD"),  # JPMorgan Global Income A (icdiv) USD hedged（ISIN: LU2347655073）
    "FLFM1": ("", "USD"),            # BNP Paribas Sustainable Global Corporate Bond Classic MD USD — secId 待補
    "CTZP0": ("", "USD"),            # Invesco Global Investment Grade Corporate Bond E-MD-1 USD — secId 待補
}

def _morningstar_search_secid(query: str, currency: str = "TWD") -> str:
    """
    透過 Morningstar 搜尋 API 取得 secId。
    query: 基金名稱（英文較準）或 ISIN。
    回傳 Morningstar secId 字串，找不到回傳 ""。
    """
    if query in _ms_secid_cache:
        return _ms_secid_cache[query]
    try:
        import urllib.request as _ur, json as _j, urllib.parse as _up
        _q = _up.quote(query[:60])
        # Morningstar 全球搜尋（無地區限制，不需登入）
        url = (
            f"https://lt.morningstar.com/j2uwuwirjh/util/SecuritySearch.ashx"
            f"?q={_q}&rows=5&Sound=0&F=0&MR=True&CF=0&EF=0"
            f"&category=&langId=zh-tw&SiteLanguage=zh-tw&ifIncludeAds=False&ProductType=FUND"
        )
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json, text/javascript, */*",
            "Referer": "https://www.morningstar.com/",
            "Origin": "https://www.morningstar.com",
        }
        req = _ur.Request(url, headers=hdrs)
        with _ur.urlopen(req, timeout=10) as resp:
            data = _j.loads(resp.read())
        results = data if isinstance(data, list) else data.get("r", [])
        if results:
            sec_id = results[0].get("i", "")
            fund_name_ms = results[0].get("n", "")
            print(f"[morningstar_search] '{query}' → secId={sec_id} ({fund_name_ms[:30]})")
            _ms_secid_cache[query] = sec_id
            # v19.473:順手記名稱 + 從名稱判幣別(供 ISIN 驅動路徑自動回填,免使用者填)
            _ms_name_cache[query] = fund_name_ms
            _ms_ccy_cache[query] = _ccy_from_fund_name(fund_name_ms)
            return sec_id
    except Exception as _e:
        # v19.339(第五份 review Bug 5):暫時性失敗(timeout/403/JSON 壞)原本也落到
        # 下方永久負快取 — 一次網路抖動就讓該基金的 Morningstar 長史救援
        # (span-extend)整個 process 存活期失效。失敗不入快取,下次呼叫重試
        # (對齊 v19.337 _daily_cache「失敗不快取」原則)。
        print(f"[morningstar_search] '{query}': {_e}")
        return ""
    # HTTP 200 但查無結果 = 確定性負結果 → 合法負快取(避免重複打搜尋 API)
    _ms_secid_cache[query] = ""
    return ""


# v19.491:ISIN → secId 走 Morningstar **screener** 端點(user 2026-08-20 提案)。
_MS_SCREENER_TOKEN = "klr5zyak8x"          # 與 NAV timeseries(_src_morningstar_nav 3b)同一把
# 宇宙用 Morningstar `FO<ISO-3166-alpha3>$$ALL` 註冊地慣例。精確 ISIN filter → 錯宇宙只回空、
# 不會誤中別檔,故可逐一試到命中即止(§1 不猜、不誤配)。排序:離岸盧森堡/愛爾蘭(你的保單
# 平台檔的**真正註冊地**,LU…/IE… 幾乎都在這)→ 台灣境內 → 美/英/港/星(常見計價地)。
# v19.491 稽核(API-shape agent)更正:原 "FOEUR$$ALL" 不合 FO<ISO3> 慣例(EUR 非國碼)且漏了
#   FOLUX/FOIRL —— LU 離岸基金正住那兩個 → 補上並前置、拿掉可疑的 FOEUR(避免對自己要救的檔回空)。
_MS_SCREENER_UNIVERSES = ("FOLUX$$ALL", "FOIRL$$ALL", "FOTWN$$ALL", "FOUSA$$ALL",
                          "FOGBR$$ALL", "FOHKG$$ALL", "FOSGP$$ALL")
# v19.491 稽核後補:screener 走**雙 host 備援**(user 2026-08-20 手機對 tools.morningstar.co.uk
#   回 DNS_PROBE_FINISHED_NXDOMAIN → 該 host 在某些網路/DNS 解不到)。tools 主(與 NAV timeseries
#   同,美國 IP 可達)、lt 備(SecuritySearch 同 host,DNS 較穩);連線層失敗跳下個 host。
_MS_SCREENER_HOSTS = (
    "https://tools.morningstar.co.uk/api/rest.svc",   # 主(= _MS_TOOLS_REST,NAV timeseries 同)
    "https://lt.morningstar.com/api/rest.svc",         # 備(lt SecuritySearch 同 host)
)
_MS_SCREENER_ROW_KEYS = ("rows", "results", "securities", "data")   # 可辨識的 row 容器鍵
_MS_SCREENER_SECID_KEYS = ("SecId", "secId", "SecID", "secid")      # 載重欄位大小寫容錯
_MS_SCREENER_NAME_KEYS = ("Name", "name", "LegalName", "legalName")
_MS_SCREENER_ISIN_KEYS = ("ISIN", "isin", "Isin")
_MS_SCREENER_CCY_KEYS = ("PriceCurrency", "BaseCurrency", "Currency")  # 依序取(§4.1 幣別不硬給)


def _screener_extract_rows(data) -> list:
    """從 screener JSON 取出 row list。晨星標準回 {"total":N,"rows":[...]},但不同版本/宇宙
    偶回 list 或 {"results":[...]} —— 因本沙盒無法連外實測 shape,防禦性多形容忍(§1 不硬解:
    非預期結構回 [] 讓上層退回 SecuritySearch/Yahoo,不炸、不假裝命中)。
    """
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for _k in _MS_SCREENER_ROW_KEYS:
            _v = data.get(_k)
            if isinstance(_v, list):
                return _v
    return []


def _screener_shape_recognized(data) -> bool:
    """回應是否為「可辨識的 screener 形狀」:bare list,或 dict 帶已知 row 容器鍵(值為 list)。

    非可辨識(如 {"error":...} 軟錯誤 body / rate-limit 字串 / None)→ False → 上層視為**異常**,
    **不入負快取**(§1:讓欄位名/端點錯誤在生產日誌現形,而非被當「確定查無」永久藏住)。
    """
    if isinstance(data, list):
        return True
    if isinstance(data, dict):
        return any(isinstance(data.get(_k), list) for _k in _MS_SCREENER_ROW_KEYS)
    return False


def _screener_row_get(row: dict, keys) -> str:
    """從 screener row 取 keys 中第一個非空欄 → str(strip);全無 → ""。容忍大小寫變體。"""
    for _k in keys:
        _v = row.get(_k)
        if _v not in (None, ""):
            return str(_v).strip()
    return ""


def _morningstar_screener_secid(isin: str, currency: str = "USD") -> str:
    """用 Morningstar **screener** 以精確 `filters=ISIN:IN:<isin>` 解析 secId(比 SecuritySearch
    模糊名稱搜尋準;保單平台基金常是後者查不到才卡住)。回傳晨星 **F 型 secId**(可直接餵
    `_MS_TOOLS_REST/timeseries_price`,與本檔 3a NAV 主路徑同 host + 同 token),查無 / 失敗回 ""。

    多宇宙嘗試(FOLUX/FOIRL 離岸 → FOTWN 台灣 → …):精確 ISIN filter 讓錯宇宙只回空、**不誤中別檔**,
    逐一試到命中即止。命中順手記名稱 + **screener 直接回的幣別**(比從名稱後綴猜準;猜為 fallback),
    供 `_src_morningstar_nav` ISIN 路徑自動回填選股池(§4.1 不硬給 USD)。

    §1 快取策略(對齊 `_morningstar_search_secid` / `_yahoo_search_secid_by_isin`):
      - 暫時性失敗(timeout / 連線 / JSON 壞)**不入負快取** → 下次可重試。
      - 回應形狀非預期 或 有 rows 卻抽不到 SecId(疑欄位名不符)= **解析異常** → 不負快取 + 大聲 log。
      - 唯有「全宇宙皆乾淨查無」(可辨識形狀 + rows 空)才負快取(避免重複打)。

    ⚠️ 本沙盒代理封鎖 tools.morningstar.co.uk(連既有 NAV 端點都 403),故 shape 未能連外實測;
       設計為**純附加 + 命中才回非空**,任何非預期 → 回 "" 讓上層退回既有解析鏈(零回歸風險)。
       上面「解析異常不負快取 + log」即為:萬一實測欄位名/宇宙與此不符,能在真環境日誌現形。
    """
    _isin = str(isin or "").strip().upper()
    if not _isin:
        return ""
    if _isin in _ms_screener_cache:
        return _ms_screener_cache[_isin]

    import json as _j, urllib.error as _uerr, urllib.parse as _up, urllib.request as _ur
    _hdrs = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://tools.morningstar.co.uk/",
    }
    _dp = _up.quote("SecId|Name|ISIN|PriceCurrency|BaseCurrency")
    _ccy = str(currency or "USD").strip().upper() or "USD"
    _transient = False       # timeout/連線/JSON 壞 → 可重試,不負快取
    _anomaly = False         # 形狀非預期 / 有 rows 抽不到 SecId → 疑欄位錯,不負快取 + 現形
    _logged_sample = False
    for _host in _MS_SCREENER_HOSTS:
        _hlabel = _host.split("//", 1)[-1].split("/", 1)[0]     # host 顯示名(日誌用)
        for _uni in _MS_SCREENER_UNIVERSES:
            url = (
                f"{_host}/{_MS_SCREENER_TOKEN}/security/screener"
                f"?page=1&pageSize=10&outputType=json&version=1&languageId=en-GB"
                f"&currencyId={_up.quote(_ccy)}&universeIds={_up.quote(_uni)}"
                f"&securityDataPoints={_dp}"
                f"&filters=ISIN%3AIN%3A{_up.quote(_isin)}"
            )
            try:
                req = _ur.Request(url, headers=_hdrs)
                with _ur.urlopen(req, timeout=12) as resp:
                    data = _j.loads(resp.read())
            except _uerr.HTTPError as _e:       # 有回應但狀態壞(可能 universe-specific)→ 試下個宇宙
                print(f"[ms_screener] {_isin} @ {_hlabel}/{_uni}: HTTP {_e.code}")
                _transient = True
                continue
            except (_uerr.URLError, OSError) as _e:  # DNS/連線層(NXDOMAIN 等)→ 整個 host 不通,跳下個 host
                print(f"[ms_screener] {_isin} @ {_hlabel} 連線失敗(跳下個 host):{_e}")
                _transient = True
                break
            except Exception as _e:  # noqa: BLE001 — JSON 壞等 → 試下個宇宙(§1 不入負快取)
                print(f"[ms_screener] {_isin} @ {_hlabel}/{_uni}: {_e}")
                _transient = True
                continue
            if not _screener_shape_recognized(data):
                # HTTP 200 但非 screener 形狀(軟錯誤 / rate-limit body)→ 異常,不當「確定查無」(§1)
                _anomaly = True
                if not _logged_sample:
                    print(f"[ms_screener] ⚠️ {_isin} @ {_hlabel}/{_uni} 回應非預期形狀"
                          f"(不負快取):{str(data)[:180]}")
                    _logged_sample = True
                continue
            _rows = _screener_extract_rows(data)
            for _r in _rows:
                if not isinstance(_r, dict):
                    continue
                _sec = _screener_row_get(_r, _MS_SCREENER_SECID_KEYS)
                _got_isin = _screener_row_get(_r, _MS_SCREENER_ISIN_KEYS).upper()
                # 雙保險:screener filter 已限定 ISIN,仍比對回傳 ISIN 欄(有回才比;沒回就信 filter)
                if _sec and (not _got_isin or _got_isin == _isin):
                    _name = _screener_row_get(_r, _MS_SCREENER_NAME_KEYS)
                    _rccy = _screener_row_get(_r, _MS_SCREENER_CCY_KEYS).upper()
                    print(f"[ms_screener] ✅ {_isin} @ {_hlabel}/{_uni} → secId={_sec} "
                          f"({_name[:30]}, {_rccy})")
                    _ms_screener_cache[_isin] = _sec
                    _ms_secid_cache[_isin] = _sec          # 與 SecuritySearch 共用正快取
                    if _name:
                        _ms_name_cache[_isin] = _name
                    # screener 直接回幣別 → 優先;無則退名稱後綴猜(§4.1 不硬給)
                    _ms_ccy_cache[_isin] = _rccy or _ccy_from_fund_name(_name)
                    return _sec
            # 本宇宙未命中。有 rows 卻抽不到合格 SecId → 解析異常(疑欄位名不符)→ 不負快取 + 現形
            if _rows:
                _anomaly = True
                if not _logged_sample:
                    _first = next((r for r in _rows if isinstance(r, dict)), None)
                    print(f"[ms_screener] ⚠️ {_isin} @ {_hlabel}/{_uni} 有 {len(_rows)} rows 但抽不到 "
                          f"SecId(不負快取,疑欄位名不符):keys={list(_first.keys()) if _first else None}")
                    _logged_sample = True
    # 全 host×宇宙跑完:唯「無暫時失敗 且 無解析異常」(= 皆乾淨查無)才負快取
    if not _transient and not _anomaly:
        _ms_screener_cache[_isin] = ""
    return ""


def _src_morningstar_nav(code: str, fund_name: str = "") -> "pd.Series":
    """
    v6.19: 從 Morningstar 全球 API 取歷史淨值。
    改進：
    1. 優先使用 _MORNINGSTAR_SECID_MAP 硬編碼（跳過搜尋，避免 lt.morningstar.com 封鎖）
    2. 使用正確 currencyId（USD vs TWD）
    3. 多端點嘗試 + Yahoo Finance 備援
    """
    import datetime as _dt2, json as _j2, urllib.request as _ur2
    rows = {}
    _code = code.upper().strip()

    # 1. 查映射:v19.472 先問**選股池(_fund_pool,併入的對照表)**(user 提案「兩表共用」),
    #    再退硬編碼 _MORNINGSTAR_SECID_MAP(TLZF9 等)。你的表優先 → 可覆蓋/補新檔。
    _user_mapped = None
    try:
        from repositories.pool_repository import resolve_secid as _resolve_user_secid
        _user_mapped = _resolve_user_secid(_code)
    except Exception:  # noqa: BLE001 — 選股池不可用不阻斷抓取鏈(退硬編/搜尋)
        _user_mapped = None
    _mapped = _user_mapped or _MORNINGSTAR_SECID_MAP.get(_code, ("", "USD"))
    sec_id, currency_id = _mapped if _mapped[0] else ("", "USD")

    # 2a. v19.470 ISIN 驅動:仍無 secId → 用選股池那列的 **ISIN** 去晨星搜(比名稱準);
    #     搜到 set_secid 回存(下次直接用、不重搜)。user 提案「填代號+ISIN,系統自動串」。
    #     v19.471 稽核修:優先用**使用者填的幣別**當 currency_id 抓 NAV,不硬給 USD。
    #     v19.473(user「只填代號+ISIN,其餘自動」):使用者沒填幣別時 → 用晨星回傳**基金名稱後綴**
    #     自動判幣別(如 "…USD");並把 secId + 自動判到的**幣別 + 名稱**一起回存到選股池那列
    #     (下次直接用、UI 表格自動顯示)。名稱既有則不覆蓋(set_secid 內部處理)。
    if not sec_id:
        try:
            # ⛔ 2026-09-06:`set_secid as _cache_secid` **已移除,不是漏刪**。
            #    只留讀取(`resolve_*`);回存 secId 的那一行見下方切除註。
            from repositories.pool_repository import (  # noqa: PLC0415
                resolve_currency as _resolve_user_ccy,
                resolve_isin as _resolve_user_isin,
            )
            _isin = _resolve_user_isin(_code)
            if _isin:
                _u_ccy = _resolve_user_ccy(_code)
                if _u_ccy:
                    currency_id = _u_ccy          # 使用者有填 → 尊重(§4.1 不硬給 USD)
                # v19.491:先走 **screener**(精確 ISIN filter,同 host + 同 token,保單平台更準),
                #   查無 / 端點不可用才退回既有 SecuritySearch(純附加、零回歸)。
                sec_id = (_morningstar_screener_secid(_isin, currency_id or "USD")
                          or _morningstar_search_secid(_isin, currency_id or "USD"))
                # 使用者沒填幣別 → 用晨星名稱自動判(命中才覆蓋 currency_id,免硬給 USD)
                _auto_ccy = "" if _u_ccy else _ms_ccy_cache.get(_isin, "")
                if _auto_ccy:
                    currency_id = _auto_ccy
                # ── 2026-09-06:查一檔基金**不再**把 secId 回寫進使用者的 Google Sheet ──
                # ~~if sec_id:~~
                # ~~    try:~~
                # ~~        # 回存 secId + 自動判到的幣別(空則不動既有)+ 晨星名稱(既有不覆蓋)~~
                # ~~        _cache_secid(_code, sec_id, currency=_auto_ccy,~~
                # ~~                     name=_ms_name_cache.get(_isin, ""))~~
                # ~~    except Exception:  # noqa: BLE001 — 回存失敗不影響本次抓取~~
                # ~~        pass~~
                #
                # **有意識的政策變更,不是漏刪**(日期 **2026-09-06** · 決策者:**客戶**)。
                # 客戶 2026-09-06 永久授權,逐字:「凡是『查詢/搜尋』功能,一律強制走
                # 『純讀取(唯讀)』,絕對禁止反向寫入我的 Google Sheet。不用問我,直接切斷寫入!」
                #
                # ## 可達性:兩組稽核結論相反 → 第三組仲裁,判定**走得到**(2026-09-06)
                # 仲裁組用離線寫入哨兵從 `fetch_fund_from_moneydj_url` 往下實跑,
                # `ws.update('A2:J2')` **當場觸發,而且函式正常回傳、不拋例外**
                # —— 也就是說這個寫入在 production 是**靜默**的。
                # 判「走不到」那組的呼叫圖從 `render_single_fund_tab` 只算出 15 個可達函式
                # (正確約 487、24 支 `_src_*` NAV adapter)—— 圖在三個別名處斷掉:
                #   ① `services/moneydj_fetcher.py` 的
                #      `... import fetch_fund_from_moneydj_url_enriched as fetch_fund_from_moneydj_url`
                #   ② `repositories/fund/__init__.py` 的 `globals()[_name] = getattr(_mod, _name)` 動態 re-export
                #   ③ `fund_orchestration` 的 `from ...sources import *` 產生的第二份 binding
                #
                # ## 觸發條件:**不是每次查詢都寫**(這是嚴重性的關鍵,不要讀成「每查必寫」)
                # 該檔在選股池那一列**有 ISIN、secId 還空著**,
                # 且本次先前的 NAV 來源沒給滿 ≥10 筆(閘門 2g)或序列跨度 <300 天(span-extend 閘門),
                # 且晨星 screener／Yahoo search 這次查得到 secId → **首次查該檔就寫**。
                # 三個放大點:
                #   (a) `_pool_secid_or_isin`(v19.505)已把閘門從「保單前綴」放寬到
                #       **任何池內有 ISIN 的檔**,境內 ACDD/ACCP 一樣中;
                #   (b) `_fetch_fund_single` / `fetch_fund_from_moneydj_url` / `fetch_fund_multi_source`
                #       **都沒有快取 decorator**,每按一次「🚀 分析」重跑一次;
                #   (c) 寫入外面包著 `except Exception: pass`,成功失敗**都不出現在畫面上**。
                #
                # **舊條文的理由仍然成立**:v19.473 要解的是「使用者只填代號 + ISIN,
                # 其餘自動」—— 第一次搜到 secId 就存回去,下次不必再搜一趟,又順便讓
                # ⑤ 設定頁的表格顯示得出晨星 ID 與幣別。省一趟往返、少一格要手填,
                # 那個設計目的一個字都沒有錯。
                # **被權衡掉的是它的形狀**:這段寫入**綁在「查詢成功」上,不綁在使用者的意圖上**
                # —— 沒有按鈕、沒有勾選框、沒有任何確認,使用者「只是查一下淨值」
                # 就會被改動他自己的試算表那一列;而且失敗還被 `except Exception: pass`
                # 整個吞掉,連 log 都沒有。
                #
                # ⚠️ **本次切除的是「寫」,不是「用」**:同一輪搜到的 `sec_id` / `currency_id`
                #    **照舊在本次抓取中使用**(見下方 `sec_id` 的後續消費),
                #    功能沒有消失,消失的只有「順手改你的表」。
                #    代價據實寫明:**下次查同一檔會再搜一次 secId**(多一趟外部往返),
                #    且 ⑤ 設定頁不會再自動長出晨星 ID —— 要永久存,請在 ⑤ 設定頁
                #    的選股池編輯器按存檔(`_render_pool_editor` 的 `set_secid`,
                #    那是使用者**明確按下**的動作,不在本次切除範圍內)。
                #
                # 📌 **登記(只登記,不動手)**:若客戶要保留「自動回填」這個便利,
                #    **正解是把它改成使用者明示動作**(勾選框／按鈕/表單送出才寫),
                #    而不是復活這一段。那會**新增視覺元件**,依 §-1.5.1c `03`-2 ①
                #    必須**先送客戶線框草稿**,**不在本批授權內**。
                #
                # ⛔ **本次刻意不動任何閘門邏輯**(`_pool_secid_or_isin` / 2g / 2g2 /
                #    span-extend 的觸發條件)—— 那是**取數行為**,不在本次授權射程內。
                #    切的只有「寫」這一個動作。
                #
                # ⛔ **不得**以「這只是補一格空欄、又不刪東西」為由復活它 ——
                #    客戶禁的是**查詢的副作用寫入**這個形狀本身,不是寫入的大小。
                # 守衛:`tests/test_readonly_query_paths.py`(第 7 節,tripwire + 別名感知 AST)。
        except Exception:  # noqa: BLE001 — 對照表/搜尋不可用不阻斷(退名稱搜尋)
            pass

    # 2b. 仍無 secId → 用名稱/代號搜尋(既有 fallback)
    if not sec_id:
        _query = fund_name.strip() if fund_name.strip() else _code
        if _query:
            sec_id = _morningstar_search_secid(_query)
            if not sec_id and _query != _code:
                sec_id = _morningstar_search_secid(_code)

    if not sec_id:
        print(f"[src_morningstar] {_code}: 無 secId（未在映射表且搜尋失敗）")
        return pd.Series(dtype=float)

    end_d   = _dt2.date.today()
    # v19.281:400d → 2000d(~5.5 年),讓 3Y/5Y 指標可算(保單代碼如 TLZF9
    # 走 Morningstar 時原僅 ~13 月 → 補足多年歷史)。tools.morningstar.co.uk
    # timeseries_price 支援任意起訖日。
    start_d = end_d - _dt2.timedelta(days=2000)
    _hdrs_ms = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Referer": "https://tools.morningstar.co.uk/",
    }

    def _parse_ms_compactjson(data2: dict) -> dict:
        result = {}
        securities = (data2.get("TimeSeries") or {}).get("Security") or []
        for sec in securities:
            for pt in (sec.get("HistoryDetail") or []):
                d_str = str(pt.get("EndDate", ""))[:10]
                v     = safe_float(pt.get("Value"))
                if d_str and v:
                    try:
                        result[pd.Timestamp(d_str)] = v
                    except Exception:
                        pass
        return result

    # 3a. 主端點：tools.morningstar.co.uk（secId 在 path，UK 伺服器，美國 IP 可用）
    url_uk = (
        f"{_MS_TOOLS_REST}/timeseries_price/{sec_id}"
        f"?currencyId={currency_id}&idtype=Morningstar&frequency=daily"
        f"&startDate={start_d.isoformat()}&endDate={end_d.isoformat()}"
        f"&outputType=COMPACTJSON"
    )
    try:
        req2 = _ur2.Request(url_uk, headers=_hdrs_ms)
        with _ur2.urlopen(req2, timeout=15) as resp2:
            data2 = _j2.loads(resp2.read())
        rows = _parse_ms_compactjson(data2)
        if rows:
            s = pd.Series(rows).sort_index()
            print(f"[src_morningstar] ✅ {_code} (secId={sec_id}, UK) {len(s)} 筆")
            # F-PROV-1 phase 10 v19.96 — provenance(Series.attrs)
            s.attrs["source"] = f"Morningstar:UK:timeseries:{sec_id}"
            s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            # 2026-09-01:宣告**這條序列是哪一種計價幣別**。晨星 timeseries 是拿
            # `currencyId` 要「換算後」的淨值,查不到使用者幣別時死預設 "USD" ——
            # 不宣告出來,下游長歷史救援就會拿它整條蓋掉別種幣別的序列(§1/§4.1)。
            # 慣例同 `repositories/fundclear_offshore.py` 的 attrs["currency"]。
            s.attrs["currency"] = str(currency_id or "").strip().upper()
            return s
    except Exception as _e2:
        print(f"[src_morningstar] {_code} UK timeseries: {_e2}")

    # 3b. 備援端點：lt.morningstar.com（token 在 path，secId 在 query param）
    # v19.491:第一把收斂到 _MS_SCREENER_TOKEN(同一把 klr5zyak8x),token 輪替只改一處(§3.3 DRY)。
    _tokens = [_MS_SCREENER_TOKEN, "j2uwuwirjh"]
    for _tok in _tokens:
        url_lt = (
            f"https://lt.morningstar.com/api/rest.svc/timeseries_price/{_tok}"
            f"?id={sec_id}::0&currencyId={currency_id}&idtype=Morningstar&frequency=daily"
            f"&startDate={start_d.isoformat()}&endDate={end_d.isoformat()}"
            f"&outputType=COMPACTJSON"
        )
        try:
            _hdrs_lt = {**_hdrs_ms, "Referer": "https://lt.morningstar.com/"}
            req3 = _ur2.Request(url_lt, headers=_hdrs_lt)
            with _ur2.urlopen(req3, timeout=12) as resp3:
                data3 = _j2.loads(resp3.read())
            rows = _parse_ms_compactjson(data3)
            if rows:
                s = pd.Series(rows).sort_index()
                print(f"[src_morningstar] ✅ {_code} (secId={sec_id}, lt/{_tok}) {len(s)} 筆")
                # F-PROV-1 phase 10 v19.96 — provenance(Series.attrs;含 token 識別)
                s.attrs["source"] = f"Morningstar:lt:{_tok}:{sec_id}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                s.attrs["currency"] = str(currency_id or "").strip().upper()  # 同上(§1/§4.1)
                return s
        except Exception as _e3:
            print(f"[src_morningstar] {_code} lt/{_tok}: {_e3}")

    return pd.Series(dtype=float)


# ISIN → Yahoo secId 快取(避免重複打 Yahoo search)
_yf_isin_secid_cache: dict = {}


def _yahoo_search_secid_by_isin(isin: str) -> str:
    """用 ISIN 問 Yahoo Finance search API → 回 Morningstar 基金 secId(Yahoo `{secId}.F`
    的 `0P…` 部分)。查無 / 失敗回 ""。

    v19.478(user 2026-08-19「流程本來就該用代號+星辰自動查,為何要我手填」):
    流程 code→ISIN→secId→Yahoo chart 的中間棒「晨星 SecuritySearch」從雲端搜不到 →
    改用 **Yahoo 自己的 search**(v1/finance/search):直接吃 ISIN、對到唯一 symbol
    (**無級別歧義** —— 手動查最卡的就是分不清 A/AP/MF2 哪個級別,Yahoo 用 ISIN 一對一解決),
    且從美國 IP(Streamlit Cloud)可達(同 chart 端點,已由 TLZF9 實測)。這一步讓
    「填代號+ISIN → 系統自動補 5 年」全自動,免手填 secId。
    暫時性失敗(timeout/JSON 壞)不入負快取(對齊 `_morningstar_search_secid` v19.339)。
    """
    import json as _js, urllib.parse as _ups, urllib.request as _us
    _isin = str(isin or "").strip().upper()
    if not _isin:
        return ""
    if _isin in _yf_isin_secid_cache:
        return _yf_isin_secid_cache[_isin]
    try:
        url = ("https://query1.finance.yahoo.com/v1/finance/search"
               f"?q={_ups.quote(_isin)}&quotesCount=10&newsCount=0")
        hdrs = {
            "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"),
            "Accept": "application/json",
        }
        req = _us.Request(url, headers=hdrs)
        with _us.urlopen(req, timeout=12) as resp:
            data = _js.loads(resp.read())
        for _q in (data.get("quotes") or []):
            _sym = str(_q.get("symbol") or "").strip()
            # Morningstar 基金 Yahoo symbol = `{0P…}.F`(_src_yahoo_finance_nav 用此格式)
            if _sym.endswith(".F") and _sym[:-2].upper().startswith("0P"):
                _sec = _sym[:-2]
                print(f"[yahoo_isin_search] '{_isin}' → {_sym} (secId={_sec})")
                _yf_isin_secid_cache[_isin] = _sec
                return _sec
    except Exception as _e:  # noqa: BLE001 — 暫時性失敗不入負快取,下次重試
        print(f"[yahoo_isin_search] '{_isin}': {_e}")
        return ""
    _yf_isin_secid_cache[_isin] = ""   # HTTP 200 但查無 `.F` symbol = 確定性負結果
    return ""


def _src_yahoo_finance_nav(code: str) -> "pd.Series":
    """
    v6.19: 透過 Yahoo Finance 取共同基金歷史淨值。
    Yahoo Finance 對 Morningstar 基金使用 {secId}.F 格式作為代碼。
    適用：**選股池**有 secId(或由 ISIN 自動解析),或 _MORNINGSTAR_SECID_MAP 有 secId 的基金。
    Yahoo Finance 端點從美國 IP 可存取，不受台灣 IP 封鎖影響。
    """
    import json as _jy, urllib.request as _ury
    _code = code.upper().strip()
    # v19.473:先問**選股池**(使用者 ISIN 驅動、由晨星搜到後存回的 secId),再退硬編表 →
    #   Yahoo `{secId}.F` 從此對「使用者自己填 ISIN 的檔」也生效(不再只限硬編幾檔)。
    _user_mapped = None
    try:
        from repositories.pool_repository import resolve_secid as _ru_secid
        _user_mapped = _ru_secid(_code)
    except Exception:  # noqa: BLE001 — 選股池不可用不阻斷(退硬編表)
        _user_mapped = None
    _mapped = _user_mapped or _MORNINGSTAR_SECID_MAP.get(_code, ("", "USD"))
    sec_id, currency_id = _mapped if _mapped[0] else ("", "USD")
    # v19.478:池中無 secId → 用 ISIN 問 Yahoo search 自動解析 secId(無級別歧義,雲端可達)
    #   → 回填選股池(下次即時 + UI 顯示)。這讓「代號+ISIN → 自動補 5 年」免手填 secId。
    if not sec_id:
        try:
            # ⛔ 2026-09-06:`set_secid as _wb_secid` **已移除,不是漏刪**(理由同下)。
            from repositories.pool_repository import (
                resolve_isin as _ru_isin,
            )
            _isin = _ru_isin(_code)
            if _isin:
                _found = _yahoo_search_secid_by_isin(_isin)
                if _found:
                    sec_id = _found
                    # ── 2026-09-06:同 `_src_morningstar_nav`,查詢不再回寫 Google Sheet ──
                    # ~~try:~~
                    # ~~    _wb_secid(_code, _found)   # 回填:下次直接用、UI 表格顯示~~
                    # ~~except Exception as _wbe:  # noqa: BLE001 — 回填失敗不阻斷本次抓取~~
                    # ~~    print(f"[src_yahoo] {_code} 回填 secId 失敗(非致命):{_wbe}")~~
                    #
                    # **有意識的政策變更,不是漏刪**(2026-09-06 · 決策者:**客戶**)。
                    # 完整理由見上方 `_src_morningstar_nav` 的同型切除註 ——
                    # **兩處是同一個終點**(`pool_repository.set_secid` → `upsert`
                    # → `Worksheet.update`),只是入口不同(晨星 / Yahoo),
                    # 故理由只寫一次、不重複貼。
                    # ⚠️ `_found` **照舊被本次抓取使用**(上一行已 `sec_id = _found`),
                    #    切掉的只有「順手改你的表」。
        except Exception as _re:  # noqa: BLE001 — 選股池/解析不可用不阻斷
            print(f"[src_yahoo] {_code} ISIN→Yahoo secId 解析失敗:{_re}")
    if not sec_id:
        return pd.Series(dtype=float)

    yf_symbol = f"{sec_id}.F"
    # Yahoo Finance v8 chart API（每日資料,近 2 年）—— v19.230 P1-2 第二輪:
    # URL template SSOT 同時提供給 scripts/fetch_nav_cache.py(production fetcher 為主)
    url = YF_MORNINGSTAR_CHART_URL.format(symbol=yf_symbol)
    hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
    }
    try:
        req = _ury.Request(url, headers=hdrs)
        with _ury.urlopen(req, timeout=15) as resp:
            data = _jy.loads(resp.read())
        result = data.get("chart", {}).get("result", [])
        if not result:
            print(f"[src_yahoo] {_code} ({yf_symbol}): 無結果")
            return pd.Series(dtype=float)
        r = result[0]
        # 2026-09-01:Yahoo v8 chart 的 `meta.currency` 一直都在,先前**整個丟掉**。
        # 這裡打的是 `{secId}.F`(法蘭克福掛牌)—— 同一檔基金的別種計價幣別在 Yahoo
        # 一樣查得到,不把幣別帶出來,下游救援就會拿它整條蓋掉正確幣別的序列(§1/§4.1)。
        # 讀不到就留空字串 = 未知(§1 不猜),由 shared.data_quality 那層當 unknown 處理。
        _yf_ccy = str((r.get("meta") or {}).get("currency") or "").strip().upper()
        timestamps = r.get("timestamp", [])
        # v19.333 review F2:.get("quote", [{}]) 的 default 只在 key 缺失時生效;
        # API 回 "quote": [](key 在但空 list)時 [0] 會 IndexError 被外層吞掉,
        # 錯誤訊息誤導(實為無資料非解析失敗)。顯式判空。
        _quote_list = r.get("indicators", {}).get("quote", [])
        closes = (_quote_list[0] if _quote_list else {}).get("close", [])
        rows = {}
        for ts, cl in zip(timestamps, closes):
            # cl 為 None(缺值)或 0 皆跳過 — NAV 必為正(§3.2 不變量),0 非合法淨值
            if ts and cl:
                try:
                    rows[pd.Timestamp(ts, unit="s")] = float(cl)
                except Exception:
                    pass
        if rows:
            s = pd.Series(rows).sort_index()
            print(f"[src_yahoo] ✅ {_code} ({yf_symbol}) {len(s)} 筆")
            # F-PROV-1 phase 10 v19.96 — provenance(Series.attrs)
            s.attrs["source"] = f"Yahoo:chart:{yf_symbol}"
            s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            s.attrs["currency"] = _yf_ccy        # 見上(§1/§4.1);空 = 未知,不猜
            return s
        print(f"[src_yahoo] {_code} ({yf_symbol}): 資料解析後為空")
    except Exception as _e:
        print(f"[src_yahoo] {_code} ({yf_symbol}): {_e}")
    return pd.Series(dtype=float)


def _src_alphavantage_nav(code: str) -> "pd.Series":
    """
    v6.22: 透過 Alpha Vantage API 取共同基金/ETF 歷史淨值。

    Alpha Vantage 是美國服務，Streamlit Cloud（Azure US）可存取，不受台灣 IP 封鎖。
    需在 Streamlit Secrets 或環境變數中設定 ALPHAVANTAGE_API_KEY。
    免費方案：25 req/day；若有付費 key 則無限制。

    搜尋策略：
    1. 使用 _MORNINGSTAR_SECID_MAP 中的 secId 直接當 symbol 查詢
       例如：TLZF9 → symbol = "0P0001J5YG.F"（Yahoo Finance 格式）
    2. 若無 secId，嘗試直接用 5 碼代碼搜尋
    """
    import json as _ja, urllib.request as _ura, os as _os
    _code = code.upper().strip()

    # 取得 API Key（優先 Streamlit secrets，次選環境變數）
    api_key = ""
    try:
        import streamlit as _st
        api_key = _st.secrets.get("ALPHAVANTAGE_API_KEY", "")
    except Exception:
        pass
    if not api_key:
        api_key = _os.environ.get("ALPHAVANTAGE_API_KEY", "")
    if not api_key:
        return pd.Series(dtype=float)

    _hdrs_av = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }

    def _av_time_series(symbol: str) -> "pd.Series":
        """呼叫 Alpha Vantage TIME_SERIES_DAILY_ADJUSTED，解析歷史淨值。"""
        url = (
            f"https://www.alphavantage.co/query"
            f"?function=TIME_SERIES_DAILY_ADJUSTED"
            f"&symbol={symbol}&outputsize=full&apikey={api_key}"
        )
        try:
            req = _ura.Request(url, headers=_hdrs_av)
            with _ura.urlopen(req, timeout=20) as resp:
                data = _ja.loads(resp.read())
            ts = data.get("Time Series (Daily)", {})
            if not ts:
                # API Key 超限或代碼不存在
                note = data.get("Note", data.get("Information", ""))
                if note:
                    print(f"[src_alphavantage] {symbol}: {note[:80]}")
                return pd.Series(dtype=float)
            rows = {}
            for date_str, ohlc in ts.items():
                try:
                    # 使用收盤價（adjusted close 更準確）
                    # v19.333 review F4:值可為 JSON null → 舊 float(None) 拋 TypeError,
                    # 不在 (ValueError, KeyError) 內 → 冒泡到外層丟「整段」序列。
                    # 改 safe_float(SSOT 轉換):None/非數值 → 只跳過該筆。
                    v = safe_float(ohlc.get("5. adjusted close", ohlc.get("4. close")))
                    if v is not None and v > 0:
                        rows[pd.Timestamp(date_str)] = v
                except (ValueError, KeyError):
                    pass
            if rows:
                s = pd.Series(rows).sort_index()
                print(f"[src_alphavantage] ✅ {symbol}: {len(s)} 筆")
                # F-PROV-1 phase 11 v19.97 — provenance(Series.attrs)
                s.attrs["source"] = f"AlphaVantage:TIME_SERIES_DAILY_ADJUSTED:{symbol}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
        except Exception as _e:
            print(f"[src_alphavantage] {symbol}: {_e}")
        return pd.Series(dtype=float)

    # 1. 嘗試 Morningstar secId 格式（{secId}.F）
    _mapped = _MORNINGSTAR_SECID_MAP.get(_code, ("", "USD"))
    sec_id = _mapped[0] if _mapped[0] else ""
    if sec_id:
        for sym in [f"{sec_id}.F", sec_id]:
            s = _av_time_series(sym)
            if len(s) >= 10:
                return s

    # 2. 直接搜尋 5 碼代碼
    s = _av_time_series(_code)
    if len(s) >= 10:
        return s

    print(f"[src_alphavantage] {_code}: 無資料（secId={sec_id or '無'}）")
    return pd.Series(dtype=float)


def _src_morningstar_meta(code: str, fund_name: str = "") -> dict:
    """
    v6.15: 從 Morningstar 取基金中文名稱與最新淨值。
    """
    meta = {}
    _code = code.upper().strip()
    _query = fund_name.strip() if fund_name.strip() else _code
    if not _query:
        return meta
    try:
        import urllib.request as _ur3, json as _j3, urllib.parse as _up3
        _q3 = _up3.quote(_query[:60])
        url3 = (
            f"https://lt.morningstar.com/j2uwuwirjh/util/SecuritySearch.ashx"
            f"?q={_q3}&rows=3&Sound=0&F=0&MR=True&CF=0&EF=0"
            f"&category=&langId=zh-tw&SiteLanguage=zh-tw&ifIncludeAds=False&ProductType=FUND"
        )
        hdrs3 = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://www.morningstar.com/",
        }
        req3 = _ur3.Request(url3, headers=hdrs3)
        with _ur3.urlopen(req3, timeout=10) as resp3:
            data3 = _j3.loads(resp3.read())
        results3 = data3 if isinstance(data3, list) else data3.get("r", [])
        if results3:
            r0 = results3[0]
            ms_name = r0.get("n", "")
            if ms_name:
                # Morningstar 回的是英文名稱，保留作參考（UI 中文 label 不受影響）
                meta["fund_name_intl"] = ms_name
                # 若 TDCC 沒找到中文名稱，用英文名稱暫代
                if not meta.get("fund_name"):
                    meta["fund_name"] = ms_name
                print(f"[src_morningstar_meta] ✅ {_code}: {ms_name[:40]}")
                # F-PROV-1 phase 15 v19.101 — provenance(schema-additive)
                meta["source"] = "Morningstar:lt:SecuritySearch"
                meta["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    except Exception as _e3:
        print(f"[src_morningstar_meta] {_code}: {_e3}")
    return meta



# ════════════════════════════════════════════════════════════
# v11.0 B-9b-4：保險公司 / URL canonicalize / 30day / TCB / SITCA
# 17 函式（共 996 行）從 fund_fetcher.py 抽出
# ════════════════════════════════════════════════════════════

# ══════════════════════════════════════════════════════════════════════
# v6.17 保險公司官網直連 + 連通性診斷工具
# 針對 TL（台灣人壽）/ FL（富蘭克林）/ JF（JP Morgan）等代碼
# ══════════════════════════════════════════════════════════════════════

def probe_insurance_urls(code: str = "TLZF9") -> dict:
    """
    v6.17 診斷工具：測試各個保險/基金網址是否在 Streamlit Cloud 可存取。
    在資料診斷頁面呼叫，幫助確認哪些 URL 真正可用。
    回傳：{url: {"ok": bool, "status": int, "ms": int}}
    """
    import urllib.request as _ur, time as _tm
    _code = code.upper().strip()
    results = {}
    candidates = [
        # ── 台灣人壽自有伺服器（.aspx 非 MoneyDJ 格式，較可能存取）────────
        f"https://178.taiwanlife.com/mobile/b1.aspx?a={_code}-F1740",
        # ── 銀行自有 domain（非 moneydj.com，IP 封鎖機率低）───────────────
        f"https://fund.hncb.com.tw/w/wb/wb02.djhtm?a={_code}-1180",           # 華南銀行
        f"https://fundchannelnew2.sinotrade.com.tw/w/wb/wb01.djhtm?a={_code}-57C0060T",  # 永豐金
        f"https://fundrwd.entiebank.com.tw/w/wb/wb01.djhtm?a={_code}-24A7",    # 遠東銀行
        "https://fund.megabank.com.tw/w/wb/wb02.djhtm?a=ANZ89-1G11",          # 兆豐銀行
        # ── TDCC OpenAPI（政府 API，無封鎖）────────────────────────────────
        "https://openapi.tdcc.com.tw/v1/opendata/3-2",
        # ── FundClear ──────────────────────────────────────────────────────
        f"https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax/GetFundNAV?FundCode={_code}&StartDate=2024/01/01&EndDate=2025/01/01",
        # ── Morningstar ────────────────────────────────────────────────────
        f"https://lt.morningstar.com/j2uwuwirjh/util/SecuritySearch.ashx?q={_code}&rows=3&ProductType=FUND",
        # ── MoneyDJ 子網域（台新人壽，可能封鎖）─────────────────────────
        f"https://taishinlife.moneydj.com/w/wb/wb01.djhtm?a={_code}-AL001",
        # ── 富蘭克林 TW / JP Morgan TW ────────────────────────────────────
        "https://www.franklintempleton.com.tw/",
        "https://am.jpmorgan.com/tw/zh/asset-management/gim/",
    ]
    hdrs = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "*/*"}
    for url in candidates:
        t0 = _tm.time()
        try:
            req = _ur.Request(url, headers=hdrs)
            with _ur.urlopen(req, timeout=6) as resp:
                status = resp.getcode()
                body_len = len(resp.read(500))
            ms = int((_tm.time() - t0) * 1000)
            results[url] = {"ok": True, "status": status, "ms": ms, "bytes": body_len}
            print(f"[probe] ✅ {status} {ms}ms {url[:60]}")
        except Exception as _e:
            ms = int((_tm.time() - t0) * 1000)
            _msg = str(_e)[:60]
            results[url] = {"ok": False, "status": 0, "ms": ms, "error": _msg}
            print(f"[probe] ❌ {_msg} {url[:60]}")
    return results


def _src_taiwanlife_nav(code: str) -> "pd.Series":
    """
    v6.17: 台灣人壽官網歷史淨值直連。
    台灣人壽依法需公開投資型保險基金淨值，嘗試多個可能端點。
    """
    import urllib.request as _ur_tl, json as _j_tl
    import datetime as _dt_tl
    rows = {}
    _code = code.upper().strip()
    end_d   = _dt_tl.date.today()
    # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
    # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
    start_d = end_d - _dt_tl.timedelta(days=2000)

    _hdrs_tl = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/html, */*",
        "Referer": "https://www.taiwanlife.com/",
        "Accept-Language": "zh-TW,zh;q=0.9",
    }

    # 嘗試台灣人壽 API 端點（多個可能路徑）
    _api_urls = [
        f"https://www.taiwanlife.com/API/Fund/GetHistoryPrice"
        f"?fundCode={_code}&startDate={start_d.isoformat()}&endDate={end_d.isoformat()}",
        f"https://www.taiwanlife.com/api/fund/navhistory?code={_code}",
        f"https://www.taiwanlife.com/Fund/GetFundNav?fundCode={_code}",
        # 富邦人壽（台灣人壽被富邦合併後）
        f"https://www.fubon-ins.com.tw/api/fund/GetFundPrice?code={_code}",
        f"https://www.fubon-ins.com.tw/insurance/fund/navHistory?code={_code}",
    ]
    for _url in _api_urls:
        try:
            req = _ur_tl.Request(_url, headers=_hdrs_tl)
            with _ur_tl.urlopen(req, timeout=8) as resp:
                raw = resp.read()
            # 先試 JSON 解析
            try:
                d = _j_tl.loads(raw)
                nav_list = (d.get("data") or d.get("navList") or d.get("Data") or
                            d.get("historyList") or (d if isinstance(d, list) else []))
                for item in (nav_list or []):
                    if not isinstance(item, dict):
                        continue
                    _d = str(item.get("date") or item.get("Date") or
                             item.get("navDate") or item.get("priceDate") or "")[:10]
                    _v = safe_float(item.get("nav") or item.get("NAV") or
                                    item.get("price") or item.get("value"))
                    if _d and _v:
                        try:
                            rows[pd.Timestamp(_d)] = _v
                        except Exception:
                            pass
            except Exception:
                # 若非 JSON，嘗試 HTML 解析
                from bs4 import BeautifulSoup as _BS_tl
                import re as _re_tl
                soup_tl = _BS_tl(raw.decode("utf-8", errors="replace"), "lxml")
                for tbl in soup_tl.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            _d = cells[0].get_text(strip=True)
                            _v = safe_float(cells[1].get_text(strip=True).replace(",", ""))
                            if _re_tl.match(r"\d{4}[/-]\d{2}[/-]\d{2}", _d) and _v:
                                try:
                                    rows[pd.Timestamp(_d)] = _v
                                except Exception:
                                    pass
            if rows:
                s = pd.Series(rows).sort_index()
                print(f"[src_taiwanlife] ✅ {_code} {len(s)} 筆 ({_url[:50]})")
                # F-PROV-1 phase 11 v19.97 — provenance(Series.attrs;host:endpoint)
                _host_tl = _url.split("/")[2] if "://" in _url else "taiwanlife"
                _ep_tl = _url.split("?")[0].rsplit("/", 1)[-1]
                s.attrs["source"] = f"InsuranceSubdomain:{_host_tl}:{_ep_tl}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
        except Exception as _e_tl:
            print(f"[src_taiwanlife] ❌ {_url[:50]}: {_e_tl}")

    return pd.Series(dtype=float)


# 各基金公司 API 端點對應表（key=代碼前綴 or 全代碼）
_FUND_COMPANY_DIRECT_MAP = {
    # 富蘭克林坦伯頓（FL 前綴）
    "FL": {
        "nav_api": "https://www.franklinresources.com/content/dam/data/navHistory.json",
        "search_api": "https://www.franklintempleton.com.tw/api/fund/search",
        "site": "franklintempleton.com.tw",
    },
    # JP Morgan Asset Management（JF 前綴）
    "JF": {
        "nav_api": "https://am.jpmorgan.com/content/dam/jpm-am-aem/global/en/prices",
        "search_api": "https://am.jpmorgan.com/tw/zh/asset-management/gim/adv/api/fund-finder",
        "site": "am.jpmorgan.com/tw",
    },
    # 富邦人壽（FS 前綴）
    "FS": {
        "site": "www.fubon-ins.com.tw",
    },
    # 南山人壽（NS 前綴）
    "NS": {
        "site": "www.nanshanlife.com.tw",
    },
}


def _src_franklin_nav(code: str) -> "pd.Series":
    """
    v6.16: 富蘭克林坦伯頓 TW 官網歷史淨值。
    FLFM1 等 FL 前綴代碼在 Streamlit Cloud 可存取。
    策略：先用台灣官網搜尋 API 找 ISIN，再查全球 NAV API。
    """
    import urllib.request as _ur, json as _j, urllib.parse as _up
    import datetime as _dt
    rows = {}
    _code = code.upper().strip()

    # Step 1: Franklin Templeton TW 基金搜尋
    _query = _up.quote(_code)
    _search_urls = [
        f"https://www.franklintempleton.com.tw/api/fund/search?q={_query}",
        f"https://www.franklintempleton.com.tw/funds/price-performance?search={_query}",
    ]
    _isin = ""
    for _su in _search_urls:
        try:
            req_s = _ur.Request(_su, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, */*",
                "Referer": "https://www.franklintempleton.com.tw/",
            })
            with _ur.urlopen(req_s, timeout=8) as resp_s:
                d_s = _j.loads(resp_s.read())
            # 嘗試從搜尋結果取 ISIN
            items = d_s if isinstance(d_s, list) else (d_s.get("funds") or d_s.get("data") or [])
            for item in (items or []):
                if isinstance(item, dict):
                    _isin = item.get("isin") or item.get("ISIN") or ""
                    if _isin:
                        print(f"[src_franklin] {_code} → ISIN={_isin}")
                        break
            if _isin:
                break
        except Exception as _se:
            print(f"[src_franklin] search {_su[:60]}: {_se}")

    # Step 2: 若找到 ISIN，嘗試 Morningstar（已有完整實作）
    if _isin:
        _ms_s = _src_morningstar_nav(code, fund_name=_isin)
        if len(_ms_s) >= 10:
            print(f"[src_franklin] ✅ {_code} via ISIN→Morningstar {len(_ms_s)} 筆")
            return _ms_s

    # Step 3: Franklin TW nav endpoint（備用，部分基金有效）
    end_d   = _dt.date.today()
    # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
    # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
    start_d = end_d - _dt.timedelta(days=2000)
    _nav_urls = [
        f"https://www.franklintempleton.com.tw/api/fund/nav?code={_code}"
        f"&startDate={start_d.isoformat()}&endDate={end_d.isoformat()}",
    ]
    for _nu in _nav_urls:
        try:
            req_n = _ur.Request(_nu, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json",
                "Referer": "https://www.franklintempleton.com.tw/",
            })
            with _ur.urlopen(req_n, timeout=10) as resp_n:
                d_n = _j.loads(resp_n.read())
            nav_list = d_n if isinstance(d_n, list) else (d_n.get("data") or d_n.get("navs") or [])
            for item in (nav_list or []):
                if isinstance(item, dict):
                    _d = str(item.get("date") or item.get("Date") or "")[:10]
                    _v = safe_float(item.get("nav") or item.get("NAV") or item.get("value"))
                    if _d and _v:
                        try:
                            rows[pd.Timestamp(_d)] = _v
                        except Exception:
                            pass
            if rows:
                s = pd.Series(rows).sort_index()
                print(f"[src_franklin] ✅ {_code} direct nav {len(s)} 筆")
                # F-PROV-1 phase 11 v19.97 — provenance(Series.attrs)
                s.attrs["source"] = "Franklin:franklintempleton.com.tw:nav_direct"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
        except Exception as _ne:
            print(f"[src_franklin] nav {_nu[:60]}: {_ne}")

    return pd.Series(dtype=float)


def _src_jpmorgan_nav(code: str) -> "pd.Series":
    """
    v6.16: JP Morgan Asset Management TW 官網歷史淨值。
    JFZN3 等 JF 前綴代碼在 Streamlit Cloud 可存取。
    """
    import urllib.request as _ur2, json as _j2
    rows = {}
    _code = code.upper().strip()

    # JP Morgan TW 基金查詢 API
    _jpm_urls = [
        f"https://am.jpmorgan.com/tw/zh/asset-management/gim/adv/api/fund-finder?q={_code}",
        f"https://am.jpmorgan.com/content/dam/jpm-am-aem/tw/zh/prices/{_code}.json",
    ]
    _isin = ""
    for _ju in _jpm_urls:
        try:
            req_j = _ur2.Request(_ju, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "application/json, */*",
                "Referer": "https://am.jpmorgan.com/tw/",
            })
            with _ur2.urlopen(req_j, timeout=10) as resp_j:
                d_j = _j2.loads(resp_j.read())
            # 嘗試直接取 NAV 序列
            # v19.336 review M6:d_j 可能是 list — 原寫法第一個 d_j.get() 先炸
            # AttributeError,尾端 isinstance(d_j, list) 分支永遠執行不到(dead code),
            # list 型回應被外層 except 靜默丟棄(誤判為該 URL 失敗)。先判型再取。
            if isinstance(d_j, dict):
                nav_list = (d_j.get("navHistory") or d_j.get("priceHistory") or
                            d_j.get("data") or [])
            else:
                nav_list = d_j if isinstance(d_j, list) else []
            for item in (nav_list or []):
                if isinstance(item, dict):
                    _d = str(item.get("date") or item.get("Date") or "")[:10]
                    _v = safe_float(item.get("nav") or item.get("price") or item.get("value"))
                    if _d and _v:
                        try:
                            rows[pd.Timestamp(_d)] = _v
                        except Exception:
                            pass
            # 嘗試取 ISIN(v19.336 M6:同樣先判 dict,list 型回應無 ISIN 可取)
            if not _isin and isinstance(d_j, dict):
                _isin = (d_j.get("isin") or d_j.get("ISIN") or
                         (d_j.get("fund") or {}).get("isin") or "")
                if _isin:
                    print(f"[src_jpmorgan] {_code} → ISIN={_isin}")
            if rows:
                break
        except Exception as _je:
            print(f"[src_jpmorgan] {_ju[:60]}: {_je}")

    if rows:
        s = pd.Series(rows).sort_index()
        print(f"[src_jpmorgan] ✅ {_code} {len(s)} 筆")
        # F-PROV-1 phase 11 v19.97 — provenance(Series.attrs)
        s.attrs["source"] = "JPMorgan:am.jpmorgan.com/tw:nav_direct"
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return s

    # fallback: 用 ISIN 走 Morningstar
    if _isin:
        _ms_s = _src_morningstar_nav(code, fund_name=_isin)
        if len(_ms_s) >= 10:
            print(f"[src_jpmorgan] ✅ {_code} via ISIN→Morningstar {len(_ms_s)} 筆")
            return _ms_s

    return pd.Series(dtype=float)


_DEFAULT_MAPPING = {
    "ACTI171": {"public_code": "ACTI71",  "page_type": "yp010000", "note": "平台碼→公開碼"},
    "ACTI71":  {"public_code": "ACTI71",  "page_type": "yp010000", "note": "境內基金"},
    "ACTI7":   {"public_code": "ACTI71",  "page_type": "yp010000", "note": "ACTI7→ACTI71"},  # v6.9
    "ACTI98":  {"public_code": "ACTI98",  "page_type": "yp010000", "note": "境內基金"},
    "ACTI94":  {"public_code": "ACTI94",  "page_type": "yp010000", "note": "境內基金"},
    "ACCP138": {"public_code": "ACCP138", "page_type": "yp010000", "note": "境內基金"},
    "ACDD19":  {"public_code": "ACDD19",  "page_type": "yp010000", "note": "境內基金"},
    "TLZF9":   {"public_code": "TLZF9",   "page_type": "yp010001", "note": "境外基金(台灣人壽)"},  # v6.9
    "FLFM1":   {"public_code": "FLFM1",   "page_type": "yp010001", "note": "境外基金"},
    "CTZP0":   {"public_code": "CTZP0",   "page_type": "yp010001", "note": "境外基金"},
    "ANZ89":   {"public_code": "ANZ89",   "page_type": "yp010001", "note": "境外基金"},
    "JFZN3":   {"public_code": "JFZN3",   "page_type": "yp010001", "note": "境外基金"},
}

def load_fund_code_mapping(path: str = "fund_code_mapping.csv") -> dict:
    """
    載入基金代碼映射表（CSV），不存在時回傳內建預設表。
    CSV 格式：input_code, public_code, page_type, note
    """
    import os as _os
    mapping = dict(_DEFAULT_MAPPING)   # 先用內建預設
    if _os.path.exists(path):
        try:
            df_map = pd.read_csv(path)
            for _, row in df_map.iterrows():
                k = str(row.get("input_code", "")).upper().strip()
                if k:
                    mapping[k] = {
                        "public_code": str(row.get("public_code", k)).upper().strip(),
                        "page_type":   str(row.get("page_type", "yp010001")).lower().strip(),
                        "note":        str(row.get("note", "")),
                    }
            print(f"[mapping] ✅ 載入 {path}：{len(df_map)} 筆（+內建 {len(_DEFAULT_MAPPING)} 筆）")
        except Exception as _e:
            print(f"[mapping] {path} 讀取失敗：{_e}，使用內建預設")
    return mapping


def canonicalize_moneydj_url(url: str) -> str:
    """
    v18.22: 把非 canonical 的 MoneyDJ 變體 URL 統一轉成
    `www.moneydj.com/funddj/ya/yp01000X.djhtm?a={base_code}`，
    讓後續解析器只認單一格式（既有 _src_direct_moneydj_url 即可重用）。

    處理對象：
      - m.moneydj.com/a1.aspx?a=acdd01            （MoneyDJ 行動版）
      - chubb.moneydj.com/w/wr/wr01.djhtm?a=ACDD01-EQTAL005  （平台子網域）
      - tcbbankfund.moneydj.com/w/wb/wb01.djhtm?a=TLZF9-...  （平台子網域）
      - 已是 yp{6位數字} canonical 格式 → 原樣回傳
      - 純代碼 / 解析不出代碼 → 原樣回傳（caller 自處理）

    複合代碼處理：`ACDD01-EQTAL005` → base_code = `ACDD01`；
    canonical URL 只攜帶 base code，平台後綴在原 fetcher 仍由
    `_BANK_PLATFORM_CODES` 路徑處理（不打架）。

    境內 / 境外推斷：用 `_DOMESTIC_PREFIXES` 前綴規則。
    """
    import re as _re_cz
    if not url or not isinstance(url, str):
        return url or ""
    s = url.strip()
    if not s.lower().startswith("http"):
        return s

    # 已是 canonical 格式 → 直接回
    if _re_cz.search(r"www\.moneydj\.com/funddj/ya/[Yy][Pp]\d{6}\.djhtm", s):
        return s

    m = _re_cz.search(r"[?&][aA]=([A-Z0-9a-z][A-Z0-9a-z\-]{1,29})", s)
    if not m:
        return s
    full_code = m.group(1).upper()
    base_code = full_code.split("-", 1)[0]  # 去平台後綴
    if not base_code:
        return s

    # 命中以下任一才做 canonicalize（避免動到其他正常 URL）
    # 注意：chubb.moneydj.com/w/wr/wr01.djhtm 等平台桌面頁**不**在此列；
    #       平台桌面頁仍走原 _BANK_PLATFORM_CODES 流程，保留平台後綴
    #       才能拿到正確的「該保單該基金」NAV（扣手續費後）
    _patterns = (
        r"://m\.moneydj\.com/",
        r"\.moneydj\.com/mobile/",        # taishinlife.moneydj.com/mobile/b1.aspx
        r"/a1\.aspx",
        r"/mobile/b1\.aspx",
    )
    if not any(_re_cz.search(p, s, _re_cz.I) for p in _patterns):
        return s

    # 推 page_type（用模組級 _DOMESTIC_PREFIXES）
    _pt = "yp010000" if base_code.startswith(_DOMESTIC_PREFIXES) else "yp010001"
    return f"https://www.moneydj.com/funddj/ya/{_pt}.djhtm?a={base_code}"


def parse_moneydj_input(user_input: str) -> dict:
    """
    v13.6: 解析使用者輸入，保留 code / page_type / full_url。
    同時支援：
      - 完整 URL（https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9）
      - 純代碼（tlzf9 / TLZF9 / acdd19）
      - 短碼（大小寫均可）
    """
    import re as _re_pi
    text = (user_input or "").strip()
    info = {
        "raw_input":  text,
        "code":       "",
        "page_type":  "",
        "full_url":   "",
        "is_url":     False,
    }
    if text.lower().startswith("http"):
        info["is_url"]   = True
        info["full_url"] = text
        # 支援 ?a= 和 &a= 參數，代碼包含字母+數字+dash，長度放寬到 30
        m_code = _re_pi.search(
            r"[?&][aA]=([A-Z0-9a-z][A-Z0-9a-z\-]{1,29})", text, _re_pi.I)
        if m_code:
            info["code"] = m_code.group(1).upper()
        # 保留 page type — 含 v14.x 的桌面 yp\d{6} 與 v18.22 的平台/行動版路徑：
        #   /funddj/ya/yp010000.djhtm  → yp010000 (境內 canonical)
        #   /funddj/ya/yp010001.djhtm  → yp010001 (境外 canonical)
        #   /w/wb/wb01.djhtm | wb02 | wb05  → wb01/wb02/wb05（銀行平台桌面）
        #   /w/wr/wr01.djhtm | wr02         → wr01/wr02（保險平台桌面）
        #   /a1.aspx                        → a1_mobile（MoneyDJ 行動版）
        #   /mobile/b1.aspx                 → b1_mobile（台灣人壽行動版）
        m_page = _re_pi.search(r"/([Yy][Pp]\d{6})\.djhtm", text, _re_pi.I)
        if m_page:
            info["page_type"] = m_page.group(1).lower()
        else:
            m_alt = _re_pi.search(
                r"/w/(?:wb/wb0[125]|wr/wr0[12])\.djhtm|/a1\.aspx|/mobile/b1\.aspx",
                text, _re_pi.I,
            )
            if m_alt:
                _hit = m_alt.group(0).lower()
                if "/a1.aspx" in _hit:
                    info["page_type"] = "a1_mobile"
                elif "/mobile/b1.aspx" in _hit:
                    info["page_type"] = "b1_mobile"
                else:
                    # /w/wb/wb01 → wb01；/w/wr/wr02 → wr02
                    _pg = _hit.rsplit("/", 1)[-1].split(".")[0]
                    info["page_type"] = _pg
    else:
        # 純代碼輸入：直接 upper，允許大小寫混合
        _raw = text.upper().strip()
        # 只取 code 部分（去掉多餘空白或後綴）
        _m_pure = _re_pi.match(r"^([A-Z0-9]{3,30}(?:-[A-Z0-9]{2,20})?)$", _raw)
        if _m_pure:
            info["code"] = _m_pure.group(1)
        else:
            info["code"] = _raw[:30]   # 兜底：最多 30 字元
    return info




def _pick_fund_category(rows_map: dict) -> str:
    """MoneyDJ 頁面 rows_map → 乾淨「基金類別」。

    v19.419 修:原本 `投資標的優先` 會把**公開說明書描述**(長句,如「本基金投資於中華民國
    境內之有價證券…」)當類別。實際「基金類型」(平衡型/債券型/股票型…)才是類別;「投資標的」
    多為短分類標籤、但部分基金填長描述。故:投資標的**僅在夠短(≤15字,像標籤)時**採用,
    否則退回基金類型;都不合則空。避免長描述污染 UI 與輪動跨類別配對。
    """
    _it = (rows_map.get("投資標的") or "").strip()
    _ct = (rows_map.get("基金類型") or "").strip()
    return (_it if 0 < len(_it) <= 15 else "") or _ct


def _src_direct_moneydj_url(full_url: str) -> dict:
    """
    直接抓使用者提供的完整 MoneyDJ 頁面。
    優先解析：基金名稱、最新淨值、淨值日期、年高/年低。
    即使沒有完整歷史資料，meta 資料本身就很有價值。
    """
    import re as _re_dm
    out = {
        "fund_name":    "",
        "nav_latest":   None,
        "nav_date":     "",
        "year_high_nav": None,
        "year_low_nav":  None,
        "currency":     "USD",
        "risk_level":   "",
        "dividend_freq": "",
        "fund_scale":   "",
        "category":     "",
        "mgmt_fee":     "",
        "error":        None,
        "data_source":  "direct_url",
    }
    try:
        r = fetch_url_with_retry(full_url, timeout=20, retries=2)
        if r is None or not is_valid_moneydj_page(r.text):
            out["error"] = "direct_url_invalid"
            return out

        soup = BeautifulSoup(r.text, "lxml")
        for tbl in soup.find_all("table"):
            txt = tbl.get_text(" ", strip=True)
            if "基金名稱" not in txt and "淨值" not in txt:
                continue
            rows_map = {}
            for row in tbl.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) == 2:
                    k = cells[0].get_text(strip=True)
                    v = cells[1].get_text(strip=True)
                    if k:
                        rows_map[k] = v
                elif len(cells) >= 4:
                    for i in range(0, len(cells)-1, 2):
                        k = cells[i].get_text(strip=True)
                        v = cells[i+1].get_text(strip=True)
                        if k:
                            rows_map[k] = v
            # 基本資料
            if rows_map.get("基金名稱"):
                out["fund_name"]    = rows_map.get("基金名稱", "")
                out["currency"]     = rows_map.get("計價幣別", "USD").replace(" ", "")
                out["risk_level"]   = rows_map.get("風險報酬等級", "").replace(" ", "")
                out["dividend_freq"]= rows_map.get("配息頻率", "").replace(" ", "")
                out["fund_scale"]   = rows_map.get("基金規模", "")
                out["category"]     = _pick_fund_category(rows_map)
                out["mgmt_fee"]     = rows_map.get("最高經理費(%)", "")
                # v19.368 7/8:同表補抽保管費 → TER 估計第 2 主成分(零新增 HTTP)
                out["custody_fee"]  = (rows_map.get("最高保管費(%)") or
                                       rows_map.get("保管費(%)") or
                                       rows_map.get("保管費", ""))
                # v19.370 真實 TER:同表若揭露「總費用率」→ 收真值(消費端優先於估計)
                out["total_expense_ratio"] = (rows_map.get("總費用率(%)") or
                                              rows_map.get("總費用率") or
                                              rows_map.get("總開支比率(%)") or
                                              rows_map.get("經常性費用(%)") or "")
            # 最新淨值 + 年高低（日期格式行）
            for row in tbl.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    dt = cells[0].get_text(strip=True)
                    if _re_dm.match(r"\d{4}/\d{2}/\d{2}", dt):
                        out["nav_date"]   = dt
                        out["nav_latest"] = safe_float(cells[1].get_text(strip=True))
                        if len(cells) >= 4:
                            out["year_high_nav"] = safe_float(cells[2].get_text(strip=True))
                            out["year_low_nav"]  = safe_float(cells[3].get_text(strip=True))
            if out["fund_name"] or out["nav_latest"]:
                print(f"[direct_url] ✅ {out['fund_name'][:20]} NAV={out['nav_latest']}")
                return out
    except Exception as e:
        out["error"] = str(e)
        print(f"[direct_url] ❌ {e}")
    return out


# ── 境內基金代碼正規化（v13.3）──────────────────────────────────────
def normalize_domestic_code(code: str) -> list:
    """
    v13.4: 境內基金代碼候選清單。
    1. 先查 mapping table（最可靠）
    2. ACTI1XX → 嘗試去掉 '1'（ACTI171→ACTI71）
    3. 回傳候選清單，由 orchestrator 逐一嘗試
    """
    c = (code or "").upper().strip()
    candidates = [c]
    # 1. mapping table 直接給答案
    mapping = load_fund_code_mapping()
    if c in mapping:
        pub = mapping[c].get("public_code", c)
        if pub != c:
            candidates.insert(0, pub)   # 公開碼優先
    # 2. ACTI1XX → 去掉第五位 '1'
    if c.startswith("ACTI") and len(c) >= 7 and c[4] == "1":
        alt = "ACTI" + c[5:]
        if alt not in candidates:
            candidates.append(alt)
    return list(dict.fromkeys(candidates))


# 境內基金前綴清單（從已知投信代碼整理）
_DOMESTIC_PREFIXES = (
    "ACTI", "ACTT", "ACCP", "ACDD",  # 安聯投信
    "BFAB", "BFAC", "BFAD",           # 部分境內 BF 前綴
    "ICPF", "ICPD",                    # 中國信託
    "JFPF", "JFPD",                    # 摩根
    "SCAP", "SCAD",                    # 富蘭克林華美
)

def _is_domestic_code(code: str, page_type: str = "") -> bool:
    """
    v14.4: page-aware 境內基金判斷（擴充版）。
    優先順序：
      1. page_type == "yp010000" → 直接確認境內
      2. page_type == "yp010001" → 直接確認境外
      3. mapping table 查詢
      4. code 前綴規則（擴充清單）
      5. 預設：境外（保守）
    """
    if page_type == "yp010000":
        return True
    if page_type == "yp010001":
        return False
    c = (code or "").upper().strip()
    # mapping table 優先查
    mapping = load_fund_code_mapping()
    if c in mapping:
        return mapping[c].get("page_type", "") == "yp010000"
    # 前綴規則（境內投信代碼格式：ACXX + 數字）
    return c.startswith(_DOMESTIC_PREFIXES)


# ── v13.8 頁型互換工具 ──────────────────────────────────────────────
def get_page_types_to_try(primary_page: str) -> list:
    """
    回傳 [首選頁型, 備用頁型]。
    若首選失敗，自動互換 yp010000 ↔ yp010001 重試。
    """
    alt = {"yp010000": "yp010001", "yp010001": "yp010000"}
    primary = primary_page or "yp010001"
    fallback = alt.get(primary, "yp010001")
    return [primary, fallback]


# ── 來源3：tcbbankfund.moneydj.com（子網域，限制較少）──────────────
def _src_nav_30day(code: str, page_type: str = "") -> pd.Series:
    """
    v14.3: 從 MoneyDJ 主淨值頁直接解析近30日淨值表。

    MoneyDJ 主 nav 頁（ya/yp010001 或 ya/yp010000）上永遠有
    近30日淨值表，格式為 MM/DD | 淨值，不需要帶 params。
    這是 yf/yp004002.djhtm 被 Colab IP 封鎖時的關鍵 fallback。

    URL 結構（確認）：
      境外: https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=FLFM1
      境內: https://www.moneydj.com/funddj/ya/yp010000.djhtm?a=ACTI98
      兩者都在同頁面含近30日淨值表，MM/DD 格式
    """
    import re as _re_n30
    import datetime as _dtt
    rows = {}

    _page = page_type or ("yp010000" if _is_domestic_code(code) else "yp010001")
    _pages = get_page_types_to_try(_page)

    bases = [
        "https://tcbbankfund.moneydj.com/funddj",
        "https://chubb.moneydj.com/funddj",
        "https://www.moneydj.com/funddj",
    ]

    for _pg in _pages:
        if len(rows) >= 10:
            break
        for base in bases:
            try:
                url = f"{base}/ya/{_pg}.djhtm?a={code}"
                r = fetch_url_with_retry(url, timeout=20, retries=2)
                if r is None:
                    continue
                soup = BeautifulSoup(r.text, "lxml")
                # 2026-08-11:原為 `_dtt.date.today()`(Streamlit Cloud 是 UTC)。
                # 本頁的 MM/DD 條目要靠「今天」補年份,UTC 比 TW 慢最多 8 小時 →
                # 「TW 已跨日、UTC 未跨日」的窗內,當日條目會被推回**去年同日**
                # (≈365 天錯置,§4.5)。同一個 bug v19.333 F5 已在安聯路徑修過,
                # 這條路徑漏掉 —— 而 user 8 檔持倉現在**全部**走這條。
                # 年份推斷收 SSOT 純函式 `_infer_year_for_mmdd`(v19.333 抽出,
                # 由 tests/test_review_fixes_v19_333.py 守)。
                _today = _dtt.datetime.now(
                    _dtt.timezone(_dtt.timedelta(hours=8))).date()
                _tmp = {}
                for tbl in soup.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) < 2:
                            continue
                        dt_txt  = cells[0].get_text(strip=True)
                        nav_txt = cells[1].get_text(strip=True).replace(",", "")
                        # YYYY/MM/DD 格式
                        if _re_n30.match(r"\d{4}/\d{2}/\d{2}", dt_txt):
                            v = safe_float(nav_txt)
                            if v and v > 0:
                                try:
                                    _tmp[pd.Timestamp(dt_txt.replace("/", "-"))] = v
                                except Exception:
                                    pass
                        # MM/DD 格式（近30日表格）
                        elif _re_n30.match(r"\d{2}/\d{2}$", dt_txt):
                            v = safe_float(nav_txt)
                            if v and v > 0:
                                try:
                                    _mo = int(dt_txt.split("/")[0])
                                    _da = int(dt_txt.split("/")[1])
                                    _yr = _infer_year_for_mmdd(_mo, _da, _today)
                                    _tmp[pd.Timestamp(_dtt.date(_yr, _mo, _da))] = v
                                except Exception as _e_n30:
                                    # §1:不可靜默吞(原為 except: pass);
                                    # 含 2/29 推到非閏年等日期建構失敗
                                    print(f"[src_nav30] MM/DD 條目跳過 "
                                          f"{dt_txt}: {_e_n30}")
                if len(_tmp) >= 10:
                    rows = _tmp
                    print(f"[src_nav30] ✅ {code} {len(rows)} 筆 (page={_pg}, base={base[:30]})")
                    break
            except Exception as e:
                print(f"[src_nav30] {code} {_pg}: {e}")
        if len(rows) >= 10:
            break

    if rows:
        s = pd.Series(rows).sort_index()
        # F-PROV-1 phase 11 v19.97 — provenance(Series.attrs)
        s.attrs["source"] = "MoneyDJ:nav_30day:table_parse"
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return s
    return pd.Series(dtype=float)


def _src_tcb_nav(code: str) -> pd.Series:
    """
    TCB / MoneyDJ 子網域歷史淨值。
    依照原始 fetch_nav 順序，逐一嘗試各子網域與端點。
    """
    import datetime as _dt
    import re as _re2
    # v19.339(Bug 4):同 _src_bank_platform_nav — lazy import 解 NameError 潛伏
    from repositories.fund.nav_metrics import _parse_nav_html
    today = _dt.date.today()
    # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
    # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
    start = today - _dt.timedelta(days=2000)

    # ── 優先嘗試原始 wf01/wb02 路徑（境內/境外通用，子網域限制最少）
    _dom = _is_domestic_code(code)
    _simple_urls = [
        f"https://tcbbankfund.moneydj.com/w/wf/wf01.djhtm?a={code}",
        f"https://tcbbankfund.moneydj.com/w/wb/wb02.djhtm?a={code}",
        f"https://chubb.moneydj.com/w/wf/wf01.djhtm?a={code}",
    ]
    if not _dom:
        # v6.10: 境外基金先試子網域的 yp004001（Streamlit Cloud 封鎖 www 但子網域可存取）
        _simple_urls.extend([
            f"https://tcbbankfund.moneydj.com/funddj/yf/yp004001.djhtm?a={code}",
            f"https://chubb.moneydj.com/funddj/yf/yp004001.djhtm?a={code}",
            f"https://www.moneydj.com/funddj/yf/yp004001.djhtm?a={code}",  # fallback（本地/Colab 可用）
        ])
    for _url in _simple_urls:
        try:
            hdr = {**HDR, "Referer": "https://www.moneydj.com/"}
            r = fetch_url_with_retry(_url, headers=hdr, timeout=20, retries=2)
            if r is None:
                continue
            s = _parse_nav_html(r.text)
            if len(s) >= 10:
                print(f"[src_tcb] ✅ {code} {len(s)} 筆（{_url[:55]}）")
                # F-PROV-1 phase 9 v19.95 — provenance(Series.attrs;源 URL 摘要)
                _src_short = _url.split("/")[2] + ":" + _url.split("/")[-1].split("?")[0]
                s.attrs["source"] = f"MoneyDJ:{_src_short}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
            print(f"[src_tcb] {code} → {len(s)} 筆 ({_url[:45]})")
        except Exception as e:
            print(f"[src_tcb] {code} {_url[:45]}: {e}")

    # ── 次要：yp004002 帶日期區間（需 A/B/C params）
    base  = "https://tcbbankfund.moneydj.com/funddj"
    params = {
        "A": code,
        "B": start.strftime("%Y%m%d"),
        "C": today.strftime("%Y%m%d"),
    }
    _primary_page = "yp010000" if _is_domestic_code(code) else "yp010001"
    for _page in get_page_types_to_try(_primary_page):
        hdr = {**HDR,
               "Referer": f"https://tcbbankfund.moneydj.com/funddj/ya/{_page}.djhtm?a={code}"}
        try:
            r = fetch_url_with_retry(
                f"{base}/yf/yp004002.djhtm",
                headers=hdr, params=params, timeout=25
            )
            if r is None:
                continue
            rows = {}
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        dt_txt  = cells[0].get_text(strip=True)
                        nav_txt = cells[1].get_text(strip=True).replace(",", "")
                        if _re2.match(r"\d{4}/\d{2}/\d{2}", dt_txt):
                            v = safe_float(nav_txt)
                            if v is not None:
                                rows[pd.Timestamp(dt_txt)] = v
            if len(rows) >= 10:
                s = pd.Series(rows).sort_index()
                print(f"[src_tcb] ✅ {code} {len(s)} 筆（yp004002 page={_page}）")
                # F-PROV-1 phase 9 v19.95 — provenance(Series.attrs)
                s.attrs["source"] = f"MoneyDJ:tcbbankfund:yp004002:{_page}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
        except Exception as e:
            print(f"[src_tcb] {code} yp004002 page={_page}: {e}")

    # ── 最終 fallback：近30日
    s30 = _src_nav_30day(code)
    if len(s30) >= 10:
        print(f"[src_tcb] ⤵ {code} 改用近30日 ({len(s30)}筆)")
        # F-PROV-1 phase 9 v19.95 — provenance(若 _src_nav_30day 已設則保留)
        if "source" not in s30.attrs:
            s30.attrs["source"] = "MoneyDJ:nav_30day:fallback"
            s30.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return s30
    return pd.Series(dtype=float)


def _src_tcb_meta(code: str) -> dict:
    """
    TCB MoneyDJ 子網域基本資料（含年高/年低）。
    v14.0: 從境內基金導覽列解析績效公司代碼(BFxxxx)
    v18.19: 補 www.moneydj.com fallback + 補寫 investment_target / fund_region / fund_type
    """
    import re as _re2
    # 雙 base：tcb 優先；www 為主站 fallback（解 JFZA4 這類 tcb 子網域無此基金的情況）
    bases = ["https://tcbbankfund.moneydj.com/funddj",
             "https://www.moneydj.com/funddj"]
    # v13.8: 首選頁型 + 自動互換備用頁型
    _dom    = _is_domestic_code(code)
    _pages  = get_page_types_to_try("yp010000" if _dom else "yp010001")
    # v14.2: 境內用 yp011000，境外用 yp011001（確認自實際頁面）
    _info_page = "yp011000" if _dom else "yp011001"
    _meta_paths = [
        f"/ya/{_pages[0]}.djhtm?a={code}",
        f"/yp/{_info_page}.djhtm?a={code}",
        f"/ya/{_pages[1]}.djhtm?a={code}",    # 備用：換頁型重試
    ]
    meta = {}  # Bug fix: 初始化 meta，避免後續 meta["fund_name"] 拋 NameError
    _try_pairs = [(b, p) for b in bases for p in _meta_paths]
    for base, path in _try_pairs:
        try:
            r = fetch_url_with_retry(f"{base}{path}", timeout=20)
            if r is None or not is_valid_moneydj_page(r.text):
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "基金名稱" in txt or "淨值" in txt:
                    rows_map = {}
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) == 2:
                            rows_map[cells[0].get_text(strip=True)] = cells[1].get_text(strip=True)
                        elif len(cells) >= 4:
                            for i in range(0, len(cells)-1, 2):
                                k = cells[i].get_text(strip=True)
                                if k: rows_map[k] = cells[i+1].get_text(strip=True)
                    if rows_map.get("基金名稱"):
                        meta["fund_name"]   = rows_map.get("基金名稱", "")
                        meta["currency"]    = rows_map.get("計價幣別", "USD").replace(" ", "")
                        meta["risk_level"]  = rows_map.get("風險報酬等級", "").replace(" ", "")
                        meta["dividend_freq"] = rows_map.get("配息頻率", "").replace(" ", "")
                        meta["fund_scale"]  = rows_map.get("基金規模", "")
                        meta["category"]    = _pick_fund_category(rows_map)
                        meta["mgmt_fee"]    = rows_map.get("最高經理費(%)", "")
                        # v19.368 7/8:同表補抽保管費(TER 估計第 2 主成分)
                        meta["custody_fee"] = (rows_map.get("最高保管費(%)") or
                                               rows_map.get("保管費(%)") or
                                               rows_map.get("保管費", ""))
                        # v19.370 真實 TER:同表若揭露「總費用率」→ 收真值(消費端優先於估計)
                        meta["total_expense_ratio"] = (rows_map.get("總費用率(%)") or
                                                       rows_map.get("總費用率") or
                                                       rows_map.get("總開支比率(%)") or
                                                       rows_map.get("經常性費用(%)") or "")
                        # v18.19: 補三個 Tab5「基本資料」診斷需用的獨立欄位
                        meta["investment_target"] = rows_map.get("投資標的", "").replace(" ", "")
                        meta["fund_region"]       = rows_map.get("投資區域", "").replace(" ", "")
                        meta["fund_type"]         = rows_map.get("基金類型", "").replace(" ", "")
                    # v14.0: 從導覽列超連結抓境內基金的「績效公司代碼」(BFxxxx)
                    # 境內基金績效頁 yp020000?a=BFxxxx 用的是公司代碼而非基金代碼
                    for a_tag in tbl.find_all("a", href=True):
                        href = a_tag.get("href", "")
                        _bf = _re2.search(r"yp020000\.djhtm\?a=([A-Z0-9]+)", href, _re2.I)
                        if _bf:
                            meta["perf_company_code"] = _bf.group(1).upper()
                            break
                    # 年高低點
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 4:
                            dt = cells[0].get_text(strip=True)
                            if _re2.match(r"\d{4}/\d{2}/\d{2}", dt):
                                meta["nav_date"]     = dt
                                meta["nav_latest"]   = safe_float(cells[1].get_text(strip=True))
                                meta["year_high_nav"] = safe_float(cells[2].get_text(strip=True))
                                meta["year_low_nav"]  = safe_float(cells[3].get_text(strip=True))
                    if meta.get("fund_name"):
                        print(f"[src_tcb_meta] ✅ {code}: {meta['fund_name'][:20]}")
                        # F-PROV-1 phase 15 v19.101 — provenance(schema-additive)
                        _host_tm = base.split("/")[2] if "://" in base else "moneydj"
                        _ep_tm = path.split("?")[0].rsplit("/", 1)[-1]
                        meta["source"] = f"MoneyDJ:{_host_tm}:{_ep_tm}"
                        meta["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                        return meta
        except Exception as e:
            print(f"[src_tcb_meta] {code} {path}: {e}")
    return meta


def _src_tcb_div(code: str) -> list:
    """
    TCB MoneyDJ 配息資料。
    v13.9: 境內基金用 yp013000，境外基金用 wb05（路徑不同）
    v18.19: tcbbankfund 子網域對部分基金（如 JFZA4）回空頁 → 補 www.moneydj.com fallback
    v18.51: tcbbankfund 對部分境內代碼（ACCP138 翰亞 / ACTI71 聯博）回**有表頭但無資料列**
            的空頁。舊邏輯只檢查「配息基準日 in r.text」就 break，導致 www.moneydj.com
            fallback 永遠不啟動 → dividends 為空 → 配息率 / 含息報酬率全空。
            改為：(a) 把 parse 搬到 loop 內，**只在解析出非空 divs 才 return**；
            (b) 境內也加 wb05 作次援（截圖示主站對 ACCP138 都有 funddividend 完整資料）。
    """
    divs: list = []
    bases = ["https://tcbbankfund.moneydj.com/funddj",
             "https://www.moneydj.com/funddj"]
    _is_dom = _is_domestic_code(code)
    # v18.51: 境內也試 wb05 作備援（主站對部分境內代碼也有 wb05 頁）
    _div_paths = (
        [f"/yp/funddividend.djhtm?a={code}", f"/yp/wb05.djhtm?a={code}"]
        if _is_dom else
        [f"/yp/wb05.djhtm?a={code}", f"/yp/funddividend.djhtm?a={code}"]
    )

    def _parse_div_html(_html: str) -> list:
        """v14.2 表格結構：col[0]=配息基準日 col[1]=除息日 col[2]=發放日
        col[3]="配息" col[4]=每單位配息額 col[5]=年化配息率% col[6]=幣別"""
        _out: list = []
        try:
            _soup = BeautifulSoup(_html, "lxml")
            for _tbl in _soup.find_all("table"):
                _t = _tbl.get_text()
                if "配息基準日" not in _t and "除息日" not in _t:
                    continue
                for _row in _tbl.find_all("tr")[1:60]:
                    _cols = [td.get_text(strip=True) for td in _row.find_all("td")]
                    if len(_cols) < 6:
                        continue
                    if not _cols[0] or "/" not in _cols[0]:
                        continue
                    _amt = safe_float(_cols[4])
                    if _amt is None or _amt <= 0 or _amt > 1000:
                        continue
                    _yld = safe_float(_cols[5]) or 0
                    _cur = (_cols[6].strip() if len(_cols) > 6 and _cols[6].strip()
                            else ("TWD" if _is_dom else "USD"))
                    _out.append({
                        "date": _cols[0], "ex_date": _cols[1], "pay_date": _cols[2],
                        "amount": _amt, "yield_pct": _yld, "currency": _cur,
                    })
                if _out:
                    break   # 已解析出有效表 → 不用看其他 table
        except Exception:
            return _out
        return _out

    try:
        for _base in bases:
            for _dp in _div_paths:
                r = fetch_url_with_retry(f"{_base}{_dp}", timeout=20)
                if r is None:
                    continue
                if "配息基準日" not in r.text and "除息日" not in r.text:
                    continue
                # v18.51: 解析後才決定要不要繼續試其他 URL（避免 tcbbankfund 空頁誤判）
                _parsed = _parse_div_html(r.text)
                if _parsed:
                    print(f"[src_tcb_div] ✅ {code} {len(_parsed)} 筆 "
                          f"({_base.split('//')[-1].split('/')[0]}{_dp})")
                    return _parsed
                # 有表頭但無資料 → 換下一個 URL（換 base 或換 path）
    except Exception as e:
        print(f"[src_tcb_div] {code}: {e}")
    return divs


# ── 來源4：SITCA（境內基金基本資料）───────────────────────────────────
def _src_sitca_meta(code: str) -> dict:
    """
    SITCA 投信投顧公會公開查詢（境內基金）。
    適用於 ACTI71, ACTI98 等境內基金代碼。
    """
    meta = {}
    try:
        # SITCA 境內基金淨值查詢
        url = f"https://www.sitca.org.tw/ROC/Industry/IN2213.aspx?txtFundCode={code}"
        r = fetch_url_with_retry(url, timeout=15, retries=2)
        if r is None:
            return meta
        soup = BeautifulSoup(r.text, "lxml")
        # 找基金名稱
        for tag in soup.find_all(["h1","h2","h3","td","th","title"]):
            txt = tag.get_text(strip=True)
            if len(txt) > 4 and "基金" in txt and len(txt) < 60:
                meta["fund_name"] = txt
                break
        # 找最新淨值表格
        for tbl in soup.find_all("table"):
            txt = tbl.get_text()
            if "淨值" in txt or "NAV" in txt.upper():
                for row in tbl.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cells) >= 2:
                        nav_v = safe_float(cells[-1])
                        if nav_v and nav_v > 0:
                            meta["nav_latest"] = nav_v
                            break
                break
        if meta.get("fund_name"):
            print(f"[src_sitca] ✅ {code}: {meta['fund_name'][:20]}")
            # F-PROV-1 phase 15 v19.101 — provenance(schema-additive)
            meta["source"] = "SITCA:IN2213.aspx:meta"
            meta["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    except Exception as e:
        print(f"[src_sitca] {code}: {e}")
    return meta


def _src_sitca_nav(code: str) -> pd.Series:
    """SITCA 境內基金歷史淨值（若有公開資料）"""
    rows = {}
    import re as _re3
    try:
        import datetime as _dt
        today = _dt.date.today()
        # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
        # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
        start = today - _dt.timedelta(days=2000)
        url = (f"https://www.sitca.org.tw/ROC/Industry/IN2213.aspx"
               f"?txtFundCode={code}"
               f"&txtBeginDate={start.strftime('%Y/%m/%d')}"
               f"&txtEndDate={today.strftime('%Y/%m/%d')}")
        r = fetch_url_with_retry(url, timeout=20)
        if r is None:
            return pd.Series(dtype=float)
        soup = BeautifulSoup(r.text, "lxml")
        for tbl in soup.find_all("table"):
            for row in tbl.find_all("tr"):
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 2:
                    dt_txt  = cells[0]
                    nav_txt = cells[1].replace(",", "")
                    if _re3.match(r"\d{4}[/-]\d{2}[/-]\d{2}", dt_txt):
                        v = safe_float(nav_txt)
                        if v is not None and v > 0:
                            try:
                                rows[pd.Timestamp(dt_txt.replace("/", "-"))] = v
                            except Exception:
                                pass
        if len(rows) >= 10:
            s = pd.Series(rows).sort_index()
            print(f"[src_sitca_nav] ✅ {code} {len(s)} 筆")
            # F-PROV-1 phase 12 v19.98 — provenance(Series.attrs)
            s.attrs["source"] = "SITCA:IN2213.aspx"
            s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
            return s
    except Exception as e:
        print(f"[src_sitca_nav] {code}: {e}")
    return pd.Series(dtype=float)




# ════════════════════════════════════════════════════════════
# v11.0 B-9b-5：TDCC OpenAPI 整合（5 函式，從 fund_fetcher.py 抽出）
# ════════════════════════════════════════════════════════════


# ═════════════════════════════════════════════════════════
# TDCC OpenAPI 整合
# https://openapi.tdcc.com.tw/swagger-ui/index.html
# 3-1 境外基金總代理資訊 ✅（可用）
# 3-2 境外基金基本資料  （視資料更新而定）
# 3-4 境外基金淨值      （視資料更新而定）
# ═════════════════════════════════════════════════════════
import threading as _th
_tdcc_cache = {}
_tdcc_lock  = _th.Lock()

def _tdcc_get(ep: str) -> list:
    """GET https://openapi.tdcc.com.tw/v1/opendata/{ep}"""
    with _tdcc_lock:
        if ep in _tdcc_cache:
            return _tdcc_cache[ep]
    try:
        url  = f"https://openapi.tdcc.com.tw/v1/opendata/{ep}"
        hdrs = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept": "application/json",
            "Referer": "https://openapi.tdcc.com.tw/swagger-ui/index.html",
        }
        import urllib.request as _ur, json as _j
        req  = _ur.Request(url, headers=hdrs)
        with _ur.urlopen(req, timeout=8) as r:
            data = _j.loads(r.read())
        with _tdcc_lock:
            _tdcc_cache[ep] = data if isinstance(data, list) else []
        return _tdcc_cache[ep]
    except Exception as e:
        print(f"[_tdcc_get] {ep} 失敗:{e}")
        return []


def _src_tdcc_meta(code: str) -> dict:
    """
    TDCC OpenAPI 境外基金 metadata（3-2 + 3-4）。
    提供：基金名稱、計價幣別、最新淨值、淨值日期。
    注意：僅有最新淨值，無歷史序列。
    """
    meta = {}
    _c = code.upper().strip()
    try:
        # 3-2 基本資料（名稱、幣別）
        basic = _tdcc_get("3-2")
        for item in basic:
            item_code = (item.get("基金代碼") or item.get("境外基金代碼") or "").upper()
            if item_code == _c:
                meta["fund_name"] = item.get("基金名稱", "")
                meta["currency"]  = item.get("計價幣別", "USD")
                print(f"[src_tdcc_meta] 3-2 ✅ {_c}: {meta['fund_name'][:25]}")
                break
    except Exception as _e:
        print(f"[src_tdcc_meta] 3-2 {_c}: {_e}")
    try:
        # 3-4 最新淨值
        navs = _tdcc_get("3-4")
        for item in navs:
            # Bug fix: 同時檢查 基金代碼 與 境外基金代碼，與 3-2 一致
            item_code = (item.get("基金代碼") or item.get("境外基金代碼") or "").upper()
            if item_code == _c:
                nav = safe_float(item.get("基金淨值"))
                date_str = str(item.get("日期", ""))[:10]
                if nav:
                    meta["nav_latest"] = nav
                    meta["nav_date"]   = date_str
                if not meta.get("fund_name"):
                    meta["fund_name"] = item.get("基金名稱", "")
                print(f"[src_tdcc_meta] 3-4 ✅ {_c}: nav={nav} @ {date_str}")
                break
    except Exception as _e:
        print(f"[src_tdcc_meta] 3-4 {_c}: {_e}")
    # F-PROV-1 phase 6 v19.92 — provenance(schema-additive,僅在實際拿到資料時寫入)
    if meta:
        meta.setdefault("source", "TDCC:OpenAPI:3-2+3-4")
        meta.setdefault("fetched_at", pd.Timestamp.now('UTC').isoformat())
    return meta


def tdcc_search_fund(keyword: str) -> list:
    """
    搜尋境外基金，整合三個 TDCC endpoint：
    3-1 總代理資訊 → 確認基金機構
    3-2 基金基本資料 → 搜尋基金名稱
    3-4 淨值 → 最新淨值

    回傳格式：
    [{"基金名稱": "...", "基金代碼": "...", "總代理": "...", "淨值": "...", "日期": "..."}]
    """
    results = []
    seen    = set()

    # ── 3-2 基金基本資料 ──────────────────────────────────
    basic = _tdcc_get("3-2")
    if basic:
        for item in basic:
            name = item.get("基金名稱","")
            code = item.get("基金代碼","") or item.get("境外基金代碼","")
            if keyword.lower() in name.lower() or keyword.lower() in code.lower():
                key  = name or code
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "基金名稱": name,
                        "基金代碼": code,
                        "總代理":   item.get("總代理名稱",""),
                        "淨值":     "",
                        "日期":     "",
                        "來源":     "TDCC-3-2",
                    })

    # ── 3-4 淨值（補充淨值欄位）────────────────────────────
    navs = _tdcc_get("3-4")
    nav_map = {}
    if navs:
        for item in navs:
            code = item.get("基金代碼","")
            name = item.get("基金名稱","")
            if code: nav_map[code] = item
            if name: nav_map[name] = item

    for r in results:
        key = r["基金代碼"] or r["基金名稱"]
        if key in nav_map:
            r["淨值"] = nav_map[key].get("基金淨值","")
            r["日期"] = nav_map[key].get("日期","")

    # 若 3-2 沒資料，嘗試從 3-4 直接搜尋
    if not results and navs:
        for item in navs:
            name = item.get("基金名稱","")
            code = item.get("基金代碼","")
            if keyword.lower() in name.lower() or keyword.lower() in code.lower():
                key  = name or code
                if key not in seen:
                    seen.add(key)
                    results.append({
                        "基金名稱": name,
                        "基金代碼": code,
                        "總代理":   "",
                        "淨值":     item.get("基金淨值",""),
                        "日期":     item.get("日期",""),
                        "來源":     "TDCC-3-4",
                    })

    # ── 3-1 總代理（補充機構資訊）──────────────────────────
    agents = _tdcc_get("3-1")
    if agents and results:
        agent_map = {a.get("境外基金機構名稱","").upper(): a.get("總代理名稱","")
                     for a in agents}
        for r in results:
            if not r["總代理"]:
                for org, agent in agent_map.items():
                    if org and org[:6] in r.get("基金名稱","").upper():
                        r["總代理"] = agent
                        break

    # ── Fundclear 備援搜尋（當 TDCC 3-2 無資料時）──────────────────
    if not results:
        try:
            import urllib.request as _ur2, json as _j2, urllib.parse as _up
            fc_url = (
                "https://www.fundclear.com.tw/investBase/goGetSearchFundList.action"
                f"?keyword={_up.quote(keyword)}&fundType=2"
            )
            hdrs2 = {
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json, text/javascript, */*; q=0.01",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "https://www.fundclear.com.tw/",
            }
            req2 = _ur2.Request(fc_url, headers=hdrs2)
            with _ur2.urlopen(req2, timeout=8) as resp:
                fc_data = _j2.loads(resp.read())
            # fundclear returns: [{fundName, fundCode, nav, navDate, ...}]
            items = fc_data if isinstance(fc_data, list) else fc_data.get("list", [])
            for item in items[:20]:
                name = item.get("fundName", item.get("基金名稱", ""))
                code = item.get("fundCode", item.get("基金代碼", ""))
                nav  = str(item.get("nav", item.get("淨值", "")))
                date = str(item.get("navDate", item.get("日期", "")))
                agent= item.get("agentName", item.get("總代理名稱", ""))
                if name and name not in seen:
                    seen.add(name)
                    results.append({
                        "基金名稱": name,
                        "基金代碼": code,
                        "總代理":   agent,
                        "淨值":     nav,
                        "日期":     date,
                        "來源":     "FundClear",
                    })
        except Exception:
            pass

    return results


def tdcc_get_agents() -> list:
    """取得所有境外基金總代理列表（3-1）"""
    data = _tdcc_get("3-1")
    return [{"機構": d.get("境外基金機構名稱",""),
             "總代理": d.get("總代理名稱",""),
             "核准基金數": d.get("核准基金筆數",""),
             "類股數": d.get("申報基金總類股數",""),
             "網址": d.get("總代理網址","")}
            for d in data]


def _tdcc_resolve_fund_name(code: str) -> str:
    """
    v6.11: 從 TDCC 3-2 查詢境外基金中文名稱。
    保險平台代碼（如 TLZF9）在 TDCC 登記為境外基金，可找到完整名稱。
    """
    _c = code.upper().strip()
    try:
        basic = _tdcc_get("3-2")
        for item in basic:
            item_code = (item.get("基金代碼") or item.get("境外基金代碼") or "").upper()
            if item_code == _c:
                name = item.get("基金名稱", "")
                if name:
                    print(f"[tdcc_resolve_name] {_c} → {name[:40]}")
                    return name
    except Exception as _e:
        print(f"[tdcc_resolve_name] {_c}: {_e}")
    return ""


# ════════════════════════════════════════════════════════════
# v11.0 B-9b-5：多源聚合 + Insurance subdomain + 主入口
# fetch_fund_multi_source / _src_insurance_subdomain_nav /
# _fetch_fund_single / _finish_metrics / fetch_fund_from_moneydj_url
# 共 5 函式 / 1017 行（從 fund_fetcher.py 抽出）
# ════════════════════════════════════════════════════════════

# ── 主 Orchestrator：統一入口 ──────────────────────────────────────────
def fetch_fund_multi_source(code: str,
                             force_refresh: bool = False,
                             page_type: str = "") -> dict:
    """
    多來源基金資料抓取主函式（v13.4）。

    v13.4 新增：
      - page_type 參數：從 parse_moneydj_input() 保留的頁型直接傳入
      - normalize_domestic_code()：含 mapping table 優先查詢
      - 境內/境外路由完全分流

    抓取優先順序：
      NAV：快取 → FundClear → 鉅亨網 → TCB MoneyDJ → SITCA
      Meta：快取 → TCB MoneyDJ → FundClear → SITCA
      配息：快取 → TCB MoneyDJ → FundClear → 鉅亨網
    """
    # ── 候選代碼清單（mapping table + ACTI 系列展開）────────────────
    _is_dom = _is_domestic_code(code, page_type)
    code_candidates = (
        normalize_domestic_code(code)
        if _is_dom
        else [code.upper().strip()]
    )
    best_result = None
    # v19.226 F-PROV-1 B4:orchestrator-level provenance(§2.2)
    _fa = pd.Timestamp.now('UTC').isoformat()

    def _attach_prov(r: dict, suffix: str = "") -> dict:
        """orchestrator setdefault 不蓋過 inner fetcher 已 set 的 source。"""
        if isinstance(r, dict):
            r.setdefault("source", f"Fund:multi_source_orchestrator{suffix}")
            r.setdefault("fetched_at", _fa)
        return r

    # v19.340(第六份 review Bug 6 同病灶,ruff F821 抓出):v19.248 拆檔後
    # _fetch_fund_single 已住 fund_orchestration(該檔 L34 頂層 star-import 本檔,
    # 本檔頂層回頭 import 會循環)→ 與 v19.339 _parse_nav_html 同解法:呼叫端
    # lazy import。此前本函式(多來源聚合主入口)每呼叫必 NameError,被 caller
    # `except Exception: print` 吞掉 → fetch_fund_from_moneydj_url 的 Step 2
    # 多來源聚合 + alt page_type 重試(境內↔境外切換)自 v19.248 全滅。
    from repositories.fund.fund_orchestration import _fetch_fund_single

    for _candidate in code_candidates:
        _result = _fetch_fund_single(
            _candidate, force_refresh=force_refresh,
            page_type=page_type    # ← v13.4: 保留原始 page_type 傳遞
        )
        _status = classify_fetch_status(_result)
        # 2026-08-11 修:原本寫 `_result.get('error','')[:40]`。`error` 這個 key
        # **一定存在**(`_fetch_fund_single` 的 result dict 初始化就有 `error=None`),
        # 所以 default `''` 永遠用不到,`.get()` 回的是 `None` → `None[:40]` →
        # **TypeError**。
        # 語意剛好反過來:`normalize_result_state` 只在 status=="failed"(什麼都沒抓到)
        # 時才寫錯誤字串;抓到任何資料 → "partial" → `error` 保持 None → **本行炸掉**。
        # 也就是「抓成功就炸、抓全失敗才活」。例外往上被 fund_orchestration.py
        # Step 2 的 `except Exception` 吞成一行「多來源異常」,整條多來源 waterfall
        # 的結果被丟棄,實際上線的是 legacy 爬蟲的「近30日」路徑 —— 這正是
        # user 8 檔持倉「每檔剛好 30 點」的直接成因(§1 靜默失敗)。
        # stderr:Streamlit Cloud 的 log 面板**只顯示 stderr**,stdout 的 print
        # 線上完全看不到。這一行是「waterfall 每個候選代碼的結果」唯一的線上訊號。
        import sys as _sys_orch
        # ⚠️ `len(x.get("series") or [])` **不可以這樣寫** —— `or` 會對 pd.Series
        # 做 `bool()` → ValueError: truth value of a Series is ambiguous。
        # 這正是本輪在 merge_non_empty 追的同一顆雷,寫診斷訊息時自己又踩一次,
        # 由 test_multi_source_survives_partial_result_with_error_none 當場抓到。
        _ser_orch = _result.get("series")
        _n_orch = len(_ser_orch) if _ser_orch is not None else 0
        print(f"[orchestrator] {_candidate} → {_status} "
              f"(nav={_n_orch}筆 "
              f"src={_result.get('data_source') or '—'} "
              f"err:{(_result.get('error') or '')[:40]})",
              file=_sys_orch.stderr)
        if _status == "complete":
            return _attach_prov(_result, ":complete")
        if best_result is None:
            best_result = _result
        elif (classify_fetch_status(best_result) == "failed"
              and _status == "partial"):
            best_result = _result

    if best_result:
        return _attach_prov(best_result, ":partial_or_failed")
    return _attach_prov({
        "fund_code": code, "error": f"所有候選代碼均無資料：{code_candidates}",
        "series": None, "fund_name": "", "nav_latest": None,
        "dividends": [], "metrics": {}, "perf": {}, "risk_metrics": {},
    }, ":all_failed")


def _src_insurance_subdomain_nav(code: str) -> pd.Series:
    """
    v6.8: 根據代碼前綴推測保險公司 MoneyDJ 子網域，逐一嘗試。
    當 tcbbankfund 無此基金時（如 TLZF9 屬台灣人壽、FLFM1 屬富蘭克林）才啟動。
    """
    _code = code.upper().strip()
    portals = []
    for prefix, names in _INSURANCE_SUBDOMAIN_HINTS.items():
        if _code.startswith(prefix):
            portals.extend(names)
    if not portals:
        return pd.Series(dtype=float)

    import datetime as _dt
    # v19.339(Bug 4):同 _src_bank_platform_nav — lazy import 解 NameError 潛伏
    from repositories.fund.nav_metrics import _parse_nav_html
    today = _dt.date.today()
    # v19.291:400d(~13 月)→ 2000d(~5.5 年),對齊 v19.281 cnyes/Morningstar 已做的窗口延伸
    # ——本函式先前漏做,是保單代碼(如 JFZN3) 3-3-3「成立 0.1 年」誤判的根因之一
    start = today - _dt.timedelta(days=2000)

    for portal in portals:
        base = f"https://{portal}.moneydj.com"
        # 先試簡單的 wf01/wb02（無需日期參數）
        for path in [f"/w/wf/wf01.djhtm?a={_code}",
                     f"/w/wb/wb02.djhtm?a={_code}"]:
            try:
                r = fetch_url_with_retry(base + path, timeout=6, retries=1)
                if r is None:
                    continue
                s = _parse_nav_html(r.text)
                if len(s) >= 10:
                    print(f"[src_ins] ✅ {_code} @ {portal} wf01/wb02 → {len(s)} 筆")
                    # F-PROV-1 phase 12 v19.98 — provenance(Series.attrs)
                    _ep_ins = path.split("?")[0].rsplit("/", 1)[-1]
                    s.attrs["source"] = f"InsuranceSubdomain:{portal}.moneydj.com:{_ep_ins}"
                    s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                    return s
            except Exception as _e:
                print(f"[src_ins] {portal} {path}: {_e}")
        # 再試 yp004002（帶日期）
        params = {"A": _code, "B": start.strftime("%Y%m%d"), "C": today.strftime("%Y%m%d")}
        for page in ["yp010001", "yp010000"]:
            hdr = {**HDR, "Referer": f"{base}/funddj/ya/{page}.djhtm?a={_code}"}
            try:
                r = fetch_url_with_retry(f"{base}/funddj/yf/yp004002.djhtm",
                                         headers=hdr, params=params, timeout=8, retries=1)
                if r is None:
                    continue
                import re as _re_ins
                rows = {}
                soup = BeautifulSoup(r.text, "lxml")
                for tbl in soup.find_all("table"):
                    for row in tbl.find_all("tr"):
                        cells = row.find_all("td")
                        if len(cells) >= 2:
                            dt_t = cells[0].get_text(strip=True)
                            nv_t = cells[1].get_text(strip=True).replace(",", "")
                            if _re_ins.match(r"\d{4}/\d{2}/\d{2}", dt_t):
                                v = safe_float(nv_t)
                                if v:
                                    rows[pd.Timestamp(dt_t)] = v
                if len(rows) >= 10:
                    s = pd.Series(rows).sort_index()
                    print(f"[src_ins] ✅ {_code} @ {portal} yp004002 → {len(s)} 筆")
                    # F-PROV-1 phase 12 v19.98 — provenance(Series.attrs)
                    s.attrs["source"] = f"InsuranceSubdomain:{portal}.moneydj.com:yp004002:{page}"
                    s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                    return s
            except Exception as _e:
                print(f"[src_ins] {portal} yp004002: {_e}")
    return pd.Series(dtype=float)
