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
    "_is_domestic_code",
    "_morningstar_search_secid",
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
YF_MORNINGSTAR_CHART_URL = (
    "https://query2.finance.yahoo.com/v8/finance/chart/{symbol}"
    "?interval=1d&range=2y&includePrePost=false"
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
        # ——本函式先前漏做,是保單代碼(如 JFZN3)MK 3-3-3「成立 0.1 年」誤判的根因之一
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
    路徑：_ALLIANZ_NAV_API JSON API（2000d 歷史）→ MoneyDJ yp004002 完整歷史頁 → ifund/tw HTML（近30日）

    JSON API 結果只在 ≥90 筆時才短路返回；若只拿到近30日資料，繼續往 MoneyDJ yp004002 嘗試，
    確保回傳序列涵蓋至少 3 個月歷史（>90 交易日），而非僅最近 30 天。
    """
    import datetime as _dt_az
    import re as _re2
    _today_az = _dt_az.date.today()
    _start_az = (_today_az - _dt_az.timedelta(days=2000)).strftime("%Y%m%d")
    rows = {}

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
                proxies=_proxies, verify=_ssl_verify,
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
            _rows_api: dict = {}
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
                rows.update(_rows_api)
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
                                    rows[pd.Timestamp(dt_t)] = v
                                except Exception:
                                    pass
            if len(rows) >= 90:
                s = pd.Series(rows).sort_index()
                print(f"[src_allianz] ✅ {code} {len(s)} 筆（MoneyDJ yp004002）")
                s.attrs["source"] = "AllianzGI:moneydj_hist"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
            break  # Only try the first working page type
    except Exception as _mj_e:
        print(f"[src_allianz] yp004002 fail({code}): {_mj_e}")

    # ── 3. Fallback：HTML scraper（近30日）────────────────────────────────────
    for base_url in [
        _ALLIANZ_NAV_ENDPOINT,
        "https://tw.allianzgi.com/zh-tw/tools/fund-nav-search",
    ]:
        try:
            r = fetch_url_with_retry(base_url, timeout=15, retries=2)
            if r is None:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "淨值" not in txt and "NAV" not in txt.upper():
                    continue
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        dt_txt  = cells[0].get_text(strip=True)
                        nav_txt = cells[1].get_text(strip=True).replace(",", "")
                        if _re2.match(r"\d{4}[/-]\d{2}[/-]\d{2}", dt_txt):
                            v = safe_float(nav_txt)
                            if v and v > 0:
                                try:
                                    rows[pd.Timestamp(dt_txt.replace("/", "-"))] = v
                                except Exception:
                                    pass
                        elif _re2.match(r"\d{2}/\d{2}$", dt_txt):
                            # MM/DD 格式（近30日頁面）補年份
                            # v19.333 review F5:改用 TW 時區今日(§4.5 慣例)。
                            # Streamlit Cloud 為 UTC,比 TW 慢最多 8 小時 — Allianz 頁
                            # 若已列出「TW 已到、UTC 未到」的日期(如 TW 01/05 vs UTC 01/04),
                            # 舊 date.today() 會把該筆推回去年同日(≈365 天錯置)。
                            import datetime as _dtt2
                            _td2 = _dtt2.datetime.now(
                                _dtt2.timezone(_dtt2.timedelta(hours=8))).date()
                            try:
                                _mo2 = int(dt_txt.split("/")[0])
                                _da2 = int(dt_txt.split("/")[1])
                                _yr2 = _infer_year_for_mmdd(_mo2, _da2, _td2)
                                _v2  = safe_float(nav_txt)
                                if _v2 and _v2 > 0:
                                    rows[pd.Timestamp(_dtt2.date(_yr2, _mo2, _da2))] = _v2
                            except Exception as _e_mmdd:
                                # §1:不可靜默吞;含 2/29 推到非閏年等日期建構失敗
                                print(f"[src_allianz] MM/DD 條目跳過 {dt_txt}: {_e_mmdd}")
            if len(rows) >= 5:
                s = pd.Series(rows).sort_index()
                print(f"[src_allianz] ✅ {code} {len(s)} 筆（{base_url[:40]}）")
                # F-PROV-1 phase 11 v19.97 — provenance(Series.attrs)
                _host_ay = base_url.split("/")[2] if "://" in base_url else "allianzgi"
                s.attrs["source"] = f"AllianzGI:{_host_ay}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                return s
        except Exception as e:
            print(f"[src_allianz] {base_url[:40]}: {e}")
    return pd.Series(dtype=float)


def _src_allianzgi_meta(code: str) -> dict:
    """
    安聯投信官網基本資料 + 最新淨值。
    tw.allianzgi.com 對 Colab 可用。
    """
    meta = {}
    # 優先 ifund 平台
    try:
        r = fetch_url_with_retry(_ALLIANZ_NAV_ENDPOINT, timeout=15, retries=2)
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


def _resolve_ms_secid(code: str) -> str:
    """保單平台代碼 → Morningstar secId(硬編表 → TDCC 名稱橋接搜尋)。查無回 ""。"""
    _code = (code or "").upper().strip()
    _mapped = _MORNINGSTAR_SECID_MAP.get(_code, ("", ""))
    if _mapped[0]:
        return _mapped[0]
    # 用 TDCC 中文名搜 Morningstar(英文名較準,但中文也試)
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
        _d(f"{_code} 無 secId(映射表無 + 名稱搜尋失敗)")
        print(f"[ms_holdings] {_code}: 無 secId(未在映射表且搜尋失敗)",
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
    # ——本函式先前漏做,是保單代碼(如 JFZN3)MK 3-3-3「成立 0.1 年」誤判的根因之一
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

    # 1. 查硬編碼映射（TLZF9 等已知 secId，不需搜尋）
    _mapped = _MORNINGSTAR_SECID_MAP.get(_code, ("", "USD"))
    sec_id, currency_id = _mapped if _mapped[0] else ("", "USD")

    # 2. 若無硬編碼，嘗試 Morningstar 搜尋
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
            return s
    except Exception as _e2:
        print(f"[src_morningstar] {_code} UK timeseries: {_e2}")

    # 3b. 備援端點：lt.morningstar.com（token 在 path，secId 在 query param）
    _tokens = ["klr5zyak8x", "j2uwuwirjh"]
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
                return s
        except Exception as _e3:
            print(f"[src_morningstar] {_code} lt/{_tok}: {_e3}")

    return pd.Series(dtype=float)


def _src_yahoo_finance_nav(code: str) -> "pd.Series":
    """
    v6.19: 透過 Yahoo Finance 取共同基金歷史淨值。
    Yahoo Finance 對 Morningstar 基金使用 {secId}.F 格式作為代碼。
    適用：_MORNINGSTAR_SECID_MAP 中有 secId 的基金。
    Yahoo Finance 端點從美國 IP 可存取，不受台灣 IP 封鎖影響。
    """
    import json as _jy, urllib.request as _ury
    _code = code.upper().strip()
    _mapped = _MORNINGSTAR_SECID_MAP.get(_code, ("", "USD"))
    sec_id, currency_id = _mapped if _mapped[0] else ("", "USD")
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
        f"https://fund.megabank.com.tw/w/wb/wb02.djhtm?a=ANZ89-1G11",          # 兆豐銀行
        # ── TDCC OpenAPI（政府 API，無封鎖）────────────────────────────────
        f"https://openapi.tdcc.com.tw/v1/opendata/3-2",
        # ── FundClear ──────────────────────────────────────────────────────
        f"https://www.fundclear.com.tw/SmartFundAPI/api/FundAjax/GetFundNAV?FundCode={_code}&StartDate=2024/01/01&EndDate=2025/01/01",
        # ── Morningstar ────────────────────────────────────────────────────
        f"https://lt.morningstar.com/j2uwuwirjh/util/SecuritySearch.ashx?q={_code}&rows=3&ProductType=FUND",
        # ── MoneyDJ 子網域（台新人壽，可能封鎖）─────────────────────────
        f"https://taishinlife.moneydj.com/w/wb/wb01.djhtm?a={_code}-AL001",
        # ── 富蘭克林 TW / JP Morgan TW ────────────────────────────────────
        f"https://www.franklintempleton.com.tw/",
        f"https://am.jpmorgan.com/tw/zh/asset-management/gim/",
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
    # ——本函式先前漏做,是保單代碼(如 JFZN3)MK 3-3-3「成立 0.1 年」誤判的根因之一
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
    # ——本函式先前漏做,是保單代碼(如 JFZN3)MK 3-3-3「成立 0.1 年」誤判的根因之一
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
                out["category"]     = rows_map.get("投資標的", rows_map.get("基金類型", ""))
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
                _today = _dtt.date.today()
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
                                    _yr = _today.year if (_mo, _da) <= (_today.month, _today.day) else _today.year - 1
                                    _tmp[pd.Timestamp(_dtt.date(_yr, _mo, _da))] = v
                                except Exception:
                                    pass
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
    # ——本函式先前漏做,是保單代碼(如 JFZN3)MK 3-3-3「成立 0.1 年」誤判的根因之一
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
                        meta["category"]    = rows_map.get("投資標的", rows_map.get("基金類型", ""))
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
        # ——本函式先前漏做,是保單代碼(如 JFZN3)MK 3-3-3「成立 0.1 年」誤判的根因之一
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
        print(f"[orchestrator] {_candidate} → {_status} (err:{_result.get('error','')[:40]})")
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
    # ——本函式先前漏做,是保單代碼(如 JFZN3)MK 3-3-3「成立 0.1 年」誤判的根因之一
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
