"""repositories/fund_repository.py — 基金資料 I/O Repository
（v11.0 B-9b-2 從 fund_fetcher.py 開始抽出；分多步逐批搬入）

設計原則：
- 純 I/O / 純抓取，所有業務指標計算（calc_metrics 等）留在 services/fund_service.py（C-12）
- 統一走 fetch_url_with_retry / safe_float 等 utility（暫時從 fund_fetcher import；
  B-9b-3 後改為從 services/fund_service 或本層自有 helper）

v11.0 分層歸位：本檔屬於 Repository Layer，HTTP / cache I/O。
向後相容：fund_fetcher.py 對應位置 re-export，既有 caller 零修改。

==== 已抽出的 _src_* adapters ====
  B-9b-2  Fundclear / AllianzGI（共 5 函式 + 1 dict + 2 const）
  B-9b-3  TBA（cnyes / TCB / Morningstar / yahoo / alphavantage / 保險公司 / 銀行平台 等）
"""
from __future__ import annotations

import re        # [Auto-Fixed v18.203] 原缺此 import，致多處 HTML 解析的 re.findall/search 被呼叫時 NameError→靜默失敗
import requests   # [Auto-Fixed v18.203] 原缺此 import，致 L341/406/434 的 requests.get 在被呼叫時 NameError→靜默落 fallback
import pandas as pd
from bs4 import BeautifulSoup

# v11.0 B-9b-5: 從 infra.cache 取 cache 機制（@register_cache / @_ttl_cache /
# _cache_load_* / _cache_save_* / _FUND_SNAPSHOT）— slice A 內含這些 decorators
from infra.cache import (  # noqa: F401
    _ttl_cache,
    register_cache,
    _CACHE_DIR,
    _FUND_SNAPSHOT,
    _cache_path,
    _cache_load_nav,
    _cache_save_nav,
    _cache_load_div,
    _cache_save_div,
    _cache_load_meta,
    _cache_save_meta,
)

# Utility from fund_fetcher — module-level import is partial-load safe，因為
# fund_fetcher 載入到本檔的 re-export 點（line ~663）時，下方 utility 已定義
# v18.122 issue 4 真根因：本檔 39+ 處用以下 symbol 但僅 import 3 個，其餘全 NameError
#   → 各 _src_* fallback chain 抓到 NameError 後吞掉 → series=0 假象
#   → 用 NAS Proxy 也救不了（NameError 在 HTTP 前就崩）
# 修補 6 個漏 import：HDR (13 callsites) / HDR_JSON (1) / PORTAL_CFG (8) /
#   normalize_result_state (6) / merge_non_empty (9) / classify_fetch_status (2)
from fund_fetcher import (  # noqa: F401
    safe_float,
    fetch_url_with_retry,
    is_valid_moneydj_page,
    HDR,
    HDR_JSON,
    PORTAL_CFG,
    TCB_BASE,
    _INSURANCE_SUBDOMAIN_HINTS,
    normalize_result_state,
    merge_non_empty,
    classify_fetch_status,
)

# v18.115 B-A: 修補 _proxies/_ssl_verify NameError（PR #171 已修）
from infra.proxy import _proxies, _ssl_verify  # noqa: F401

# v18.123 issue 4 round 6: _finish_metrics 內呼叫 calc_metrics 但漏 import
# 跨層 import（repository → service）為務實妥協 — 正規修法應把 _finish_metrics
# 搬到 services/fund_service.py，但範圍較大留下次重構
from services.fund_service import calc_metrics  # noqa: F401


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
        start_d = end_d - _dt.timedelta(days=400)
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
            if meta.get("fund_name"):
                print(f"[src_fundclear_meta] ✅ {code}: {meta['fund_name'][:20]}")
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


def _src_allianzgi_nav(code: str) -> pd.Series:
    """
    安聯投信官網歷史淨值抓取。
    Colab IP 對 allianzgi.com 無限制，是 ACTI 系列最可靠的來源。
    路徑：tw.allianzgi.com → ifund.allianzgi.com.tw
    """
    rows = {}
    # 優先從 ifund 平台抓淨值表（HTML 表格）
    for base_url in [
        _ALLIANZ_NAV_ENDPOINT,
        "https://tw.allianzgi.com/zh-tw/tools/fund-nav-search",
    ]:
        try:
            r = fetch_url_with_retry(base_url, timeout=15, retries=2)
            if r is None:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            import re as _re2
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
                            import datetime as _dtt2
                            _td2 = _dtt2.date.today()
                            try:
                                _mo2 = int(dt_txt.split("/")[0])
                                _da2 = int(dt_txt.split("/")[1])
                                _yr2 = _td2.year if (_mo2, _da2) <= (_td2.month, _td2.day) else _td2.year - 1
                                _v2  = safe_float(nav_txt)
                                if _v2 and _v2 > 0:
                                    rows[pd.Timestamp(_dtt2.date(_yr2, _mo2, _da2))] = _v2
                            except Exception:
                                pass
            if len(rows) >= 5:
                s = pd.Series(rows).sort_index()
                print(f"[src_allianz] ✅ {code} {len(s)} 筆（{base_url[:40]}）")
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
                    if meta.get("fund_name"):
                        print(f"[src_allianz_meta] ✅ {code}: {meta['fund_name'][:20]}")
                        return meta
    except Exception as e:
        print(f"[src_allianz_meta] {e}")
    return meta


# ════════════════════════════════════════════════════════════
# v11.0 B-9b-3：cnyes / cache_files / bank_platform / Morningstar /
#              Yahoo / Alphavantage adapters（從 fund_fetcher.py 抽出）
# 17 函式（13 _src_* + 4 _cnyes_* / _morningstar_search_secid 等 helper）
# ════════════════════════════════════════════════════════════

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
            url = (f"https://fund.api.cnyes.com/fund/api/v2/funds/search"
                   f"?key={_uquote(key)}&limit={limit}")
            r = requests.get(url, headers=_hdrs, timeout=10, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code == 200:
                data = r.json()
                items = (data.get("data", {}).get("list")
                         or data.get("data")
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
    start_d  = end_d - _dt2.timedelta(days=400)
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
        _url = (f"https://fund.api.cnyes.com/fund/api/v2/funds/{_cand}"
                f"/nav?start={start_ms}&end={end_ms}")
        try:
            r = requests.get(_url, headers=_hdrs, timeout=15, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code != 200:
                continue
            data = r.json()
            navs = (data.get("data", {}).get("nav")
                    or data.get("data", {}).get("navs")
                    or data.get("items")
                    or [])
            if not navs and isinstance(data, list):
                navs = data
            rows = _cnyes_parse_navs(navs)
            if rows:
                print(f"[cnyes_nav] ✅ {code}→{_cand} {len(rows)} 筆")
                return pd.Series(rows).sort_index()
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
        url = f"https://fund.api.cnyes.com/fund/api/v2/funds/{_code}/dividend"
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
    return divs


def _src_cnyes_nav(code: str) -> pd.Series:
    """鉅亨網歷史淨值（REST API，無 IP 封鎖）"""
    try:
        s = fetch_nav_cnyes(code)
        if len(s) >= 10:
            print(f"[src_cnyes] ✅ {code} {len(s)} 筆")
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
    cache_file = _Path(__file__).parent / "cache" / "nav" / f"{code}.json"
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
    _code = base_code.upper().strip()
    platforms = _BANK_PLATFORM_CODES.get(_code, [])
    if not platforms:
        return pd.Series(dtype=float)

    end_d   = _dt_bp.date.today()
    start_d = end_d - _dt_bp.timedelta(days=400)
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
                        return s

                # fallback：近30日頁（wb01/wb02）
                wb_url = f"{base_url}/w/wb/{page}.djhtm?a={full_code}"
                r2 = fetch_url_with_retry(wb_url, headers=_hdrs_bp, timeout=10, retries=2)
                if r2 and is_valid_moneydj_page(r2.text):
                    s2 = _parse_nav_html(r2.text)
                    if len(s2) >= 5:
                        print(f"[src_bank] ✅ {_code} @ {domain} wb {len(s2)} 筆（近30日）")
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
        print(f"[morningstar_search] '{query}': {_e}")
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
    start_d = end_d - _dt2.timedelta(days=400)
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
        f"https://tools.morningstar.co.uk/api/rest.svc/timeseries_price/{sec_id}"
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
    # Yahoo Finance v8 chart API（每日資料，近1年）
    url = (
        f"https://query2.finance.yahoo.com/v8/finance/chart/{yf_symbol}"
        f"?interval=1d&range=2y&includePrePost=false"
    )
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
        closes = (r.get("indicators", {})
                   .get("quote", [{}])[0]
                   .get("close", []))
        rows = {}
        for ts, cl in zip(timestamps, closes):
            if ts and cl:
                try:
                    rows[pd.Timestamp(ts, unit="s")] = float(cl)
                except Exception:
                    pass
        if rows:
            s = pd.Series(rows).sort_index()
            print(f"[src_yahoo] ✅ {_code} ({yf_symbol}) {len(s)} 筆")
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
                    v = float(ohlc.get("5. adjusted close", ohlc.get("4. close", 0)))
                    if v > 0:
                        rows[pd.Timestamp(date_str)] = v
                except (ValueError, KeyError):
                    pass
            if rows:
                s = pd.Series(rows).sort_index()
                print(f"[src_alphavantage] ✅ {symbol}: {len(s)} 筆")
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
    start_d = end_d - _dt_tl.timedelta(days=400)

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
    start_d = end_d - _dt.timedelta(days=400)
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
            nav_list = (d_j.get("navHistory") or d_j.get("priceHistory") or
                        d_j.get("data") or (d_j if isinstance(d_j, list) else []))
            for item in (nav_list or []):
                if isinstance(item, dict):
                    _d = str(item.get("date") or item.get("Date") or "")[:10]
                    _v = safe_float(item.get("nav") or item.get("price") or item.get("value"))
                    if _d and _v:
                        try:
                            rows[pd.Timestamp(_d)] = _v
                        except Exception:
                            pass
            # 嘗試取 ISIN
            if not _isin:
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
        return pd.Series(rows).sort_index()
    return pd.Series(dtype=float)


def _src_tcb_nav(code: str) -> pd.Series:
    """
    TCB / MoneyDJ 子網域歷史淨值。
    依照原始 fetch_nav 順序，逐一嘗試各子網域與端點。
    """
    import datetime as _dt
    import re as _re2
    today = _dt.date.today()
    start = today - _dt.timedelta(days=400)

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
                return s
        except Exception as e:
            print(f"[src_tcb] {code} yp004002 page={_page}: {e}")

    # ── 最終 fallback：近30日
    s30 = _src_nav_30day(code)
    if len(s30) >= 10:
        print(f"[src_tcb] ⤵ {code} 改用近30日 ({len(s30)}筆)")
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
        start = today - _dt.timedelta(days=400)
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

    for _candidate in code_candidates:
        _result = _fetch_fund_single(
            _candidate, force_refresh=force_refresh,
            page_type=page_type    # ← v13.4: 保留原始 page_type 傳遞
        )
        _status = classify_fetch_status(_result)
        print(f"[orchestrator] {_candidate} → {_status} (err:{_result.get('error','')[:40]})")
        if _status == "complete":
            return _result
        if best_result is None:
            best_result = _result
        elif (classify_fetch_status(best_result) == "failed"
              and _status == "partial"):
            best_result = _result

    return best_result or {
        "fund_code": code, "error": f"所有候選代碼均無資料：{code_candidates}",
        "series": None, "fund_name": "", "nav_latest": None,
        "dividends": [], "metrics": {}, "perf": {}, "risk_metrics": {},
    }


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
    today = _dt.date.today()
    start = today - _dt.timedelta(days=400)

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
                    return s
            except Exception as _e:
                print(f"[src_ins] {portal} yp004002: {_e}")
    return pd.Series(dtype=float)


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
    """
    v13.5: 計算 calc_metrics 並正確設置最終狀態。
    使用 normalize_result_state() 確保有資料時不顯示全失敗紅字。
    """
    s    = result.get("series")
    divs = result.get("dividends", [])
    code = result.get("fund_code", "?")
    src  = result.get("data_source", "")

    # ── 初始化 source_trace（若無則建立）─────────────────────────────
    if "source_trace" not in result:
        result["source_trace"] = []

    if s is not None and len(s) >= 10:
        try:
            combined_override = dict(result.get("risk_metrics") or {})
            if result.get("year_high_nav"):
                combined_override["year_high_nav"] = result["year_high_nav"]
            if result.get("year_low_nav"):
                combined_override["year_low_nav"]  = result["year_low_nav"]
            result["metrics"] = calc_metrics(s, divs, risk_override=combined_override)
            result["source_trace"].append({"source": "calc_metrics", "success": True})
            # v18.53: 境內基金 wb01 不存在 → perf["1Y"] 多半為空。
            # 把 calc_metrics 算出的 ret_1y_total（NAV + 累積配息）注入 perf["1Y"]，
            # 讓 Tab2 健康總覽 / 吃本金 KPI / Tab3 真實收益矩陣 / Tab5 資料診斷 都拿得到含息報酬。
            if not isinstance(result.get("perf"), dict):
                result["perf"] = {}
            if result["perf"].get("1Y") is None:
                # v18.65: 只當「真 1Y」（window ≥ 350 天）才注入 perf["1Y"]
                # 否則短窗口累積值會誤導 UI（之前 30 天年化 = 300% 假象）
                _m_local = result.get("metrics") or {}
                _local_1y = _m_local.get("ret_1y_total")
                _local_window = _m_local.get("ret_1y_window_days") or 0
                if _local_1y is not None and _local_window >= 350:
                    result["perf"]["1Y"] = _local_1y
                    result["perf_source"] = result.get("perf_source") or "local_calc"
                    print(f"[metrics] 🧮 {code} perf['1Y'] 用本地計算補：{_local_1y}%")
            print(f"[metrics] ✅ {code} 指標計算完成（{len(s)} 筆，src:{src}）")
        except Exception as _ce:
            result["source_trace"].append(
                {"source": "calc_metrics", "success": False, "error": str(_ce)[:60]})
            result["error"] = f"指標計算異常：{str(_ce)[:80]}"
            print(f"[metrics] ❌ calc_metrics: {_ce}")
    elif s is not None:
        result["source_trace"].append(
            {"source": "nav_series", "success": False,
             "error": f"只有 {len(s)} 筆（需≥10）"})
    else:
        result["source_trace"].append(
            {"source": "nav_series", "success": False, "error": "無淨值序列"})

    # ── 用 normalize_result_state 統一決定最終狀態 ────────────────────
    # 這是關鍵：有任何資料就不應顯示全失敗
    result = normalize_result_state(result)
    print(f"[metrics] {code} → status={result.get('status')} "
          f"error={str(result.get('error',''))[:40]} "
          f"warning={str(result.get('warning',''))[:40]}")


# ═══════════════════════════════════════════════════════
# MoneyDJ URL 一站式爬蟲（主要入口）
# 只需要貼網址即可取得所有 MK 分析所需資料
# ═══════════════════════════════════════════════════════
@register_cache
@_ttl_cache(ttl_sec=900, maxsize=64)   # v18.58: 同 code 跨多保單載入時免重複 HTTP，15min TTL
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
    BASE_LIST = [
        "https://tcbbankfund.moneydj.com/funddj",
        "https://www.moneydj.com/funddj",
    ]
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
                            except: pass
                    elif len(cells) >= 2:
                        dt = cells[0].get_text(strip=True)
                        if _re.match(r"\d{4}/\d{2}/\d{2}", dt):
                            try:
                                result["nav_date"]   = dt
                                result["nav_latest"] = float(cells[1].get_text(strip=True).replace(",",""))
                            except: pass
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
            for tbl in soup.find_all("table"):
                for row in tbl.find_all("tr"):
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        date_txt = cells[0].get_text(strip=True)
                        nav_txt  = cells[1].get_text(strip=True).replace(",","")
                        if _re.match(r"\d{2}/\d{2}", date_txt) and _re.match(r"[\d.]+$", nav_txt):
                            try: nav_rows[date_txt] = float(nav_txt)
                            except: pass
            # 轉換日期（MoneyDJ 近期只顯示 MM/DD，需補年份）
            import datetime as _dt
            today = _dt.date.today()
            parsed = {}
            for mmdd, v in nav_rows.items():
                try:
                    mo, da = int(mmdd.split("/")[0]), int(mmdd.split("/")[1])
                    yr = today.year if (mo, da) <= (today.month, today.day) else today.year - 1
                    parsed[_dt.date(yr, mo, da)] = v
                except: pass

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
                                except: pass
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
                except: pass
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
                    except: pass
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

    if result["series"] is not None and len(result["series"]) >= 10:
        # 合併 risk_metrics 與 year_high/low 一起傳入
        try:
            combined_override = dict(result.get("risk_metrics") or {})
            if result.get("year_high_nav"): combined_override["year_high_nav"] = result["year_high_nav"]
            if result.get("year_low_nav"):  combined_override["year_low_nav"]  = result["year_low_nav"]
            result["metrics"] = calc_metrics(
                result["series"], result["dividends"],
                risk_override=combined_override
            )
            # v18.53: 同 _finish_metrics — 境內缺 wb01 perf["1Y"] 改用本地計算
            if not isinstance(result.get("perf"), dict):
                result["perf"] = {}
            if result["perf"].get("1Y") is None:
                # v18.65: 只當「真 1Y」（window ≥ 350 天）才注入 perf["1Y"]
                # 否則短窗口累積值會誤導 UI（之前 30 天年化 = 300% 假象）
                _m_local = result.get("metrics") or {}
                _local_1y = _m_local.get("ret_1y_total")
                _local_window = _m_local.get("ret_1y_window_days") or 0
                if _local_1y is not None and _local_window >= 350:
                    result["perf"]["1Y"] = _local_1y
                    result["perf_source"] = result.get("perf_source") or "local_calc"
        except Exception as _cm_e:
            print(f"[calc_metrics] {_cm_e}")
            result["error"] = f"指標計算異常：{str(_cm_e)[:60]}"
    elif result["series"] is not None:
        result["error"] = f"只取到 {len(result['series'])} 筆淨值（建議≥10）"
    else:
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


def _parse_nav_html(html: str) -> pd.Series:
    """解析 MoneyDJ 淨值 HTML，回傳 pd.Series (date→float)"""
    soup = BeautifulSoup(html, "lxml")
    rows_data = []
    for tbl in soup.find_all("table"):
        txt = tbl.get_text()
        if not re.search(r"\d{2}/\d{2}", txt):
            continue
        for row in tbl.find_all("tr"):
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 2: continue
            try:
                ds = cols[0].strip()
                if re.match(r"^\d{2}/\d{2}$", ds):
                    import datetime
                    ds = f"{datetime.date.today().year}/{ds}"
                d = pd.to_datetime(ds)
                v = float(cols[1].replace(",", ""))
                if 0.01 < v < 100000:
                    rows_data.append((d, v))
            except:
                pass
    if rows_data:
        return pd.Series({r[0]: r[1] for r in rows_data}).sort_index().dropna()
    return pd.Series(dtype=float)


def fetch_nav(full_key: str, portal: str = "") -> pd.Series:
    """
    取基金淨值歷史。
    portal 子網域 → tcbbankfund（境內/境外通用）→ moneydj 主站（境外用 yp004001）
    """
    mj_short = full_key.split("-")[-1] if "-" in full_key else full_key
    _is_dom = _is_domestic_code(full_key)
    urls = []
    if portal in PORTAL_CFG:
        base = PORTAL_CFG[portal]["base_url"]
        urls.append(f"{base}/w/wf/wf01.djhtm?a={full_key}")
    urls += [
        f"{TCB_BASE}/w/wb/wb02.djhtm?a={full_key}",
        f"{TCB_BASE}/w/wf/wf01.djhtm?a={full_key}",
    ]
    # yp004001 = 境外基金淨值歷史頁（無日期 param 的簡單路徑）
    # 境內基金無此頁，靠 wf01/wb02 子網域 或 _src_tcb_nav 的 yp004002 段
    if not _is_dom:
        urls += [
            f"https://www.moneydj.com/funddj/yf/yp004001.djhtm?a={full_key}",
            f"https://www.moneydj.com/funddj/yf/yp004001.djhtm?a={mj_short}",
        ]
    for url in urls:
        try:
            r = requests.get(url, headers=HDR, timeout=25, proxies=_proxies(), verify=_ssl_verify())
            print(f"[fetch_nav] {url[:65]} → {r.status_code}")
            if r.status_code != 200: continue
            s = _parse_nav_html(r.text)
            if len(s) >= 10:
                print(f"[fetch_nav] ✅ {len(s)} 筆")
                return s
        except Exception as e:
            print(f"[fetch_nav] ERR: {e}")
    return pd.Series(dtype=float)


# ══════════════════════════════════════════════════════════════════
# v18.283: 長期 NAV 歷史抓取 — CnYES + MoneyDJ 歷史頁面
# fetch_nav 只給 ~30-400 天，對危機回測（2018/2020/2022）資料不夠
# ══════════════════════════════════════════════════════════════════

_NAV_HISTORY_CACHE_DIR = Path("cache") / "nav_history" if False else None  # 延後 import path
try:
    from pathlib import Path as _Path_nh
    _NAV_HISTORY_CACHE_DIR = _Path_nh("cache") / "nav_history"
except Exception:
    _NAV_HISTORY_CACHE_DIR = None

_NAV_HISTORY_CACHE_TTL_SEC = 86400  # 24 小時（NAV 日頻）


def _nav_history_cache_load(code: str) -> "pd.Series | None":
    """從本地 JSON cache 讀取（24h TTL）。"""
    if _NAV_HISTORY_CACHE_DIR is None:
        return None
    import json
    import time
    p = _NAV_HISTORY_CACHE_DIR / f"{code.upper()}.json"
    if not p.exists():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if (time.time() - float(data["timestamp"])) > _NAV_HISTORY_CACHE_TTL_SEC:
            return None
        dates = pd.to_datetime(data["dates"])
        return pd.Series(data["values"], index=dates, dtype=float).sort_index()
    except Exception:
        return None


def _nav_history_cache_save(code: str, s: "pd.Series") -> None:
    """寫到本地 disk cache。"""
    if s is None or s.empty or _NAV_HISTORY_CACHE_DIR is None:
        return
    import json
    import time
    try:
        _NAV_HISTORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        p = _NAV_HISTORY_CACHE_DIR / f"{code.upper()}.json"
        s = s.dropna().sort_index()
        p.write_text(json.dumps({
            "timestamp": time.time(),
            "dates": [str(d.date()) for d in s.index],
            "values": [float(v) for v in s.values],
        }, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def _parse_nav_json_items(items: list) -> "pd.Series":
    """從 JSON list of {date/value} dict 解析成 NAV Series。寬容多種欄位名 + Unix timestamp。"""
    if not items:
        return pd.Series(dtype=float)
    dates, values = [], []
    for item in items:
        if not isinstance(item, dict):
            continue
        d = (item.get("date") or item.get("nav_date") or item.get("publishDate")
             or item.get("trade_date") or item.get("d") or item.get("Date")
             or item.get("time") or item.get("ts") or item.get("timestamp"))
        v = (item.get("nav") or item.get("netAssetValue") or item.get("value")
             or item.get("price") or item.get("close") or item.get("v")
             or item.get("Nav") or item.get("Price"))
        if d is None or v is None:
            continue
        try:
            # v18.284: Unix timestamp 處理（CnYES 等 API 用 ms epoch）
            if isinstance(d, (int, float)):
                # 13 位數 = ms；10 位數 = sec
                _d_num = float(d)
                if _d_num > 1e12:
                    dt = pd.to_datetime(_d_num, unit="ms")
                elif _d_num > 1e9:
                    dt = pd.to_datetime(_d_num, unit="s")
                else:
                    dt = pd.to_datetime(d)
            else:
                dt = pd.to_datetime(d)
            vf = float(v)
            if vf > 0:
                dates.append(dt)
                values.append(vf)
        except Exception:
            continue
    if not dates:
        return pd.Series(dtype=float)
    s = pd.Series(values, index=pd.DatetimeIndex(dates), dtype=float)
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index()


def _walk_for_nav_items(obj, depth: int = 0, max_depth: int = 10) -> list:
    """遞迴在 nested JSON 中找 NAV items list（含 date + nav 欄位的 dict 陣列）。"""
    if depth > max_depth:
        return []
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys = set(obj[0].keys())
        date_keys = {"date", "nav_date", "publishDate", "trade_date", "Date",
                     "d", "time", "ts", "timestamp"}
        val_keys = {"nav", "netAssetValue", "value", "price", "close",
                    "Nav", "Price", "v"}
        if (keys & date_keys) and (keys & val_keys):
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = _walk_for_nav_items(v, depth + 1, max_depth)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _walk_for_nav_items(v, depth + 1, max_depth)
            if r:
                return r
    return []


def _fetch_nav_cnyes(code: str) -> "pd.Series | None":
    """CnYES（鉅亨網）NAV 歷史抓取 — v18.284 修成 user 提供的正確 URL pattern。

    User 反饋：CnYES 實際 API 是 `api.cnyes.com/media/api/v1/fund/...` 而不是
    invest/fund.cnyes 之類。多年歷史，**台灣境外基金主要來源**。

    Tries (in order):
      1. https://api.cnyes.com/media/api/v1/fund/{code}/nav            （已知端點）
      2. https://api.cnyes.com/media/api/v1/fund/nav/history?code={code}
      3. https://api.cnyes.com/fund/v1/funds/{code}/nav
      4. https://fund.cnyes.com/detail/{code}/Nav （HTML，__NEXT_DATA__ 或 table 解析）
    """
    import json
    import re
    _referer = f"https://fund.cnyes.com/detail/{code}/Nav"
    _hdr_json = {**HDR_JSON, "Referer": _referer}
    api_urls = [
        f"https://api.cnyes.com/media/api/v1/fund/{code}/nav",
        f"https://api.cnyes.com/media/api/v1/fund/{code}/nav-history",
        f"https://api.cnyes.com/media/api/v1/fund/nav/history?code={code}",
        f"https://api.cnyes.com/fund/v1/funds/{code}/nav",
    ]
    for url in api_urls:
        try:
            r = requests.get(url, headers=_hdr_json, timeout=20,
                             proxies=_proxies(), verify=_ssl_verify())
            print(f"[_fetch_nav_cnyes] {url[:80]} → {r.status_code}")
            if r.status_code != 200:
                continue
            data = r.json()
            items = _walk_for_nav_items(data)
            s = _parse_nav_json_items(items)
            if not s.empty and len(s) >= 50:
                return s
        except Exception as e:
            print(f"[_fetch_nav_cnyes] API {url[:60]} ERR: {e}")
    # HTML fallback
    try:
        html_url = f"https://fund.cnyes.com/detail/{code}/Nav"
        _hdr_html = {**HDR, "Referer": "https://fund.cnyes.com/"}
        r = requests.get(html_url, headers=_hdr_html, timeout=20,
                         proxies=_proxies(), verify=_ssl_verify())
        print(f"[_fetch_nav_cnyes] HTML {html_url[:80]} → {r.status_code}")
        if r.status_code != 200:
            return None
        m = re.search(r'<script[^>]*id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
                      r.text, re.DOTALL)
        if m:
            try:
                data = json.loads(m.group(1))
                items = _walk_for_nav_items(data)
                s = _parse_nav_json_items(items)
                if not s.empty and len(s) >= 50:
                    return s
            except Exception as _e_j:
                print(f"[_fetch_nav_cnyes] __NEXT_DATA__ JSON ERR: {_e_j}")
        return _parse_html_nav_table(r.text)
    except Exception as e:
        print(f"[_fetch_nav_cnyes] HTML ERR: {e}")
    return None


def _fetch_nav_moneydj_history(code: str) -> "pd.Series | None":
    """MoneyDJ 多年歷史 NAV 頁面 — v18.284 加 DataDetail（user 提到的嘉實核心 URL）。

    Tries:
      1. fund/djhtm/DataDetail.djhtm?a={code} — user 提到的嘉實標準歷史頁
      2. yp012000 / yp008000 — 境外基金歷史
      3. wb04 — 詳情頁
    """
    _referer = "https://www.moneydj.com/funddj/"
    _hdr = {**HDR, "Referer": _referer}
    urls = [
        f"https://www.moneydj.com/fund/djhtm/DataDetail.djhtm?a={code}",
        f"https://www.moneydj.com/funddj/yp/yp012000.djhtm?a={code}",
        f"https://www.moneydj.com/funddj/yp/yp008000.djhtm?a={code}",
        f"https://tcbbankfund.moneydj.com/funddj/yp/yp012000.djhtm?a={code}",
        f"https://www.moneydj.com/w/wb/wb04.djhtm?a={code}",
        f"https://tcbbankfund.moneydj.com/w/wb/wb04.djhtm?a={code}",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=_hdr, timeout=20,
                             proxies=_proxies(), verify=_ssl_verify())
            print(f"[_fetch_nav_moneydj_history] {url[:80]} → {r.status_code}")
            if r.status_code != 200:
                continue
            r.encoding = "big5"
            s = _parse_html_nav_table(r.text)
            if s is not None and not s.empty and len(s) >= 50:
                return s
        except Exception as e:
            print(f"[_fetch_nav_moneydj_history] {url[:60]} ERR: {e}")
    return None


def _fetch_nav_fundrich(code: str) -> "pd.Series | None":
    """基富通 FundRich 平台 — v18.284 新增（user 提到）。

    後端 API 串接，前端是 ISIN code 或平台自訂代碼。先試 code 直接打。
    """
    _referer = f"https://www.fundrich.com.tw/fund/{code}"
    _hdr = {**HDR_JSON, "Referer": _referer}
    urls = [
        f"https://www.fundrich.com.tw/api/v1/funds/{code}/nav-history",
        f"https://www.fundrich.com.tw/api/v1/funds/{code}/nav",
        f"https://api.fundrich.com.tw/v1/funds/{code}/nav-history",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=_hdr, timeout=20,
                             proxies=_proxies(), verify=_ssl_verify())
            print(f"[_fetch_nav_fundrich] {url[:80]} → {r.status_code}")
            if r.status_code != 200:
                continue
            data = r.json()
            items = _walk_for_nav_items(data)
            s = _parse_nav_json_items(items)
            if not s.empty and len(s) >= 50:
                return s
        except Exception as e:
            print(f"[_fetch_nav_fundrich] {url[:60]} ERR: {e}")
    return None


def _fetch_nav_fundclear(code: str) -> "pd.Series | None":
    """基金資訊觀測站（FundClear / 投信投顧公會 / 集保）— v18.284 新增（user 提到）。

    台灣所有合法上架基金的官方資料庫。歷史資料是公開 CSV / API。
    """
    _hdr = {**HDR_JSON, "Referer": "https://www.fundclear.com.tw/"}
    urls = [
        # 投信投顧公會 REST endpoints（不同年代 + 端點）
        f"https://announce.fundclear.com.tw/MoPSFundWeb/api/v1/fund/{code}/nav",
        f"https://www.fundclear.com.tw/api/v1/funds/{code}/nav-history",
        f"https://www.fundclear.com.tw/api/v1/funds/{code}/nav",
    ]
    for url in urls:
        try:
            r = requests.get(url, headers=_hdr, timeout=20,
                             proxies=_proxies(), verify=_ssl_verify())
            print(f"[_fetch_nav_fundclear] {url[:80]} → {r.status_code}")
            if r.status_code != 200:
                continue
            try:
                data = r.json()
                items = _walk_for_nav_items(data)
                s = _parse_nav_json_items(items)
                if not s.empty and len(s) >= 50:
                    return s
            except Exception:
                # CSV fallback
                import io
                try:
                    df = pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")
                    items = df.to_dict("records")
                    s = _parse_nav_json_items(items)
                    if not s.empty and len(s) >= 50:
                        return s
                except Exception as _e_c:
                    print(f"[_fetch_nav_fundclear] CSV parse ERR: {_e_c}")
        except Exception as e:
            print(f"[_fetch_nav_fundclear] {url[:60]} ERR: {e}")
    return None


def _parse_html_nav_table(html: str) -> "pd.Series | None":
    """從 HTML 找含日期 + NAV 數字的 table。寬容多種欄位順序。"""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return None
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            tds = tr.find_all(["td", "th"])
            if len(tds) < 2:
                continue
            txt_list = [td.get_text(strip=True) for td in tds]
            # 找第一個能解析成日期的 cell + 第一個能解析成 0.01-100000 數字的 cell
            dt = None
            for t in txt_list:
                try:
                    _dt = pd.to_datetime(t)
                    if pd.Timestamp("1990-01-01") < _dt < pd.Timestamp("2100-01-01"):
                        dt = _dt
                        break
                except Exception:
                    continue
            if dt is None:
                continue
            vf = None
            for t in txt_list:
                t2 = t.replace(",", "").replace("元", "").strip()
                try:
                    v = float(t2)
                    if 0.01 < v < 100000:
                        vf = v
                        break
                except Exception:
                    continue
            if vf is not None:
                rows.append((dt, vf))
    if not rows:
        return None
    s = pd.Series([v for _, v in rows], index=pd.DatetimeIndex([d for d, _ in rows]))
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index() if not s.empty else None


def fetch_nav_history_long(code: str, min_years: int = 10) -> pd.Series:
    """v18.283/284：抓取長期 NAV 歷史（多年）給危機回測等需要長序列的場景。

    Fallback chain (v18.284 加 FundRich + FundClear，CnYES URL 修正)：
      0. 本地 disk cache (cache/nav_history/{code}.json, 24h TTL)
      1. CnYES api.cnyes.com/media/api/v1/fund/{code}/nav  ← 正確 URL
      2. MoneyDJ DataDetail.djhtm + yp012000 等多年歷史頁
      3. 基富通 FundRich API
      4. 投信投顧公會 / FundClear（官方基金資訊觀測站）
      5. 退回 fetch_nav（短期，~30-400 天）

    Returns:
        pd.Series with DatetimeIndex; 空 Series 表示全部來源失敗。
        即使比 min_years 短也回傳（caller 自己判斷涵蓋率）。
    """
    code = str(code or "").strip().upper()
    if not code:
        return pd.Series(dtype=float)

    # 0. Disk cache
    cached = _nav_history_cache_load(code)
    if cached is not None and len(cached) >= 100:
        print(f"[fetch_nav_history_long] {code} cache hit ({len(cached)} 筆)")
        return cached

    # 1. CnYES（user 提到的正確 URL pattern）
    try:
        s = _fetch_nav_cnyes(code)
        if s is not None and not s.empty:
            print(f"[fetch_nav_history_long] {code} CnYES → {len(s)} 筆")
            if len(s) >= 100:
                _nav_history_cache_save(code, s)
                return s
    except Exception as e:
        print(f"[fetch_nav_history_long] CnYES ERR: {e}")

    # 2. MoneyDJ 歷史頁（DataDetail + yp012000 等）
    try:
        s = _fetch_nav_moneydj_history(code)
        if s is not None and not s.empty:
            print(f"[fetch_nav_history_long] {code} MoneyDJ history → {len(s)} 筆")
            if len(s) >= 100:
                _nav_history_cache_save(code, s)
                return s
    except Exception as e:
        print(f"[fetch_nav_history_long] MoneyDJ history ERR: {e}")

    # 3. v18.284: 基富通 FundRich
    try:
        s = _fetch_nav_fundrich(code)
        if s is not None and not s.empty:
            print(f"[fetch_nav_history_long] {code} FundRich → {len(s)} 筆")
            if len(s) >= 100:
                _nav_history_cache_save(code, s)
                return s
    except Exception as e:
        print(f"[fetch_nav_history_long] FundRich ERR: {e}")

    # 4. v18.284: 投信投顧公會 / FundClear（官方）
    try:
        s = _fetch_nav_fundclear(code)
        if s is not None and not s.empty:
            print(f"[fetch_nav_history_long] {code} FundClear → {len(s)} 筆")
            if len(s) >= 100:
                _nav_history_cache_save(code, s)
                return s
    except Exception as e:
        print(f"[fetch_nav_history_long] FundClear ERR: {e}")

    # 5. Fallback：既有 fetch_nav（短期）
    print(f"[fetch_nav_history_long] {code} 長期來源都失敗，退回 fetch_nav 短期")
    s = fetch_nav(code)
    if not s.empty:
        _nav_history_cache_save(code, s)
    return s

def fetch_div(full_key: str, portal: str = "") -> list:
    divs = []
    urls = []
    if portal in PORTAL_CFG:
        base = PORTAL_CFG[portal]["base_url"]
        urls.append(base + PORTAL_CFG[portal]["div_path"].format(fk=full_key))
    mj = full_key.split("-")[-1] if "-" in full_key else full_key
    _is_dom = _is_domestic_code(full_key)
    # yp004003 = 境外基金配息頁；境內基金使用 funddividend（子網域通用）
    if not _is_dom:
        urls += [
            f"https://www.moneydj.com/funddj/yf/yp004003.djhtm?a={full_key}",
            f"https://www.moneydj.com/funddj/yf/yp004003.djhtm?a={mj}",
        ]
    else:
        urls += [
            f"https://tcbbankfund.moneydj.com/funddj/yp/funddividend.djhtm?a={full_key}",
            f"https://www.moneydj.com/funddj/yp/funddividend.djhtm?a={full_key}",
        ]
    for url in urls:
        try:
            r = requests.get(url, headers=HDR, timeout=20, proxies=_proxies(), verify=_ssl_verify())
            if r.status_code != 200: continue
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                if not any(k in tbl.get_text() for k in ["配息","除息","配發"]): continue
                for row in tbl.find_all("tr")[1:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 2:
                        try:
                            d = pd.to_datetime(cols[0])
                            amt = 0.0
                            for c in cols[1:]:
                                nums = re.findall(r"[\d.]+",c.replace(",",""))
                                if nums:
                                    v = float(nums[0])
                                    if 0.0001 < v < 100: amt=v; break
                            if amt > 0: divs.append({"date":str(d)[:10],"amount":amt})
                        except: pass
            if divs: break
        except Exception as e:
            print(f"[div] {e}")
    seen=set(); out=[]
    for d in sorted(divs, key=lambda x:x["date"], reverse=True):
        if d["date"] not in seen: seen.add(d["date"]); out.append(d)
    return out[:24]



# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：perf/risk/holdings: _fetch_domestic_perf / fetch_performance_wb01 / fetch_risk_metrics / fetch_holdings
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# MK 指標計算
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# 績效評比（wb07.djhtm）: 標準差/Sharpe/Beta/同類排名
# ════════════════════════════════════════════════════════════
def _fetch_domestic_perf(code: str) -> dict:
    """
    v14.0: 境內基金績效資料取得。

    【重要發現】境內基金 MoneyDJ 頁面結構：
    - yp020000.djhtm?a=BFxxxx  → 整家公司旗下所有基金清單（Sharpe 全顯示 N/A）
    - 根本沒有 wb01/wb05/wb07  → 含息報酬率/Sharpe 不存在於境內頁面
    - 唯一有意義的績效資料：從淨值序列自行計算（calc_metrics 會處理）

    因此這個函式改為：嘗試抓 yp020000 的績效摘要表，
    若抓不到有效數字（N/A），則回傳空 dict（讓 calc_metrics 自己算）。
    """
    perf = {}
    # 嘗試從 yp020000 抓績效（注意：需要公司代碼 BFxxxx 而非基金代碼）
    # 實際上境內基金的 Sharpe/含息報酬 在 MoneyDJ 顯示 N/A
    # 程式會從淨值序列自動計算，所以直接回傳空值即可
    for base in ["https://tcbbankfund.moneydj.com/funddj",
                 "https://www.moneydj.com/funddj"]:
        try:
            r = fetch_url_with_retry(
                f"{base}/yp/yp020000.djhtm?a={code}", timeout=15)
            if r is None:
                continue
            soup = BeautifulSoup(r.text, "lxml")
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "報酬" not in txt and "績效" not in txt:
                    continue
                for row in tbl.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cells) < 2:
                        continue
                    for key, names in [
                        ("1M", ["1個月","近1月"]),
                        ("3M", ["3個月","近3月"]),
                        ("6M", ["6個月","近6月","半年"]),
                        ("1Y", ["1年","近1年","今年"]),
                        ("3Y", ["3年","近3年"]),
                    ]:
                        if any(n in cells[0] for n in names):
                            v = safe_float(cells[1])
                            if v is not None:   # N/A → None → 跳過
                                perf[key] = v
            if perf:
                print(f"[domestic_perf] ✅ {code} {list(perf.keys())}")
                return perf
        except Exception as e:
            print(f"[domestic_perf] {code}: {e}")
    # 境內基金績效需從淨值序列計算，此處不強制要求
    print(f"[domestic_perf] {code} → 無法從頁面取得，將從淨值序列計算")
    return perf


def fetch_performance_wb01(code: str) -> dict:
    """
    v13.9: 境外基金用 wb01（含息報酬率），境內基金用 yp020000（績效頁）。
    境內基金 MoneyDJ 根本沒有 wb01 頁面，必須改走不同路徑。
    """
    # 境內基金：用 yp020000 績效頁取代 wb01
    if _is_domestic_code(code):
        return _fetch_domestic_perf(code)
    # 境外基金：正常走 wb01（含息報酬率）
    out = {}
    BASE = "https://www.moneydj.com/funddj"
    TCB  = "https://tcbbankfund.moneydj.com"
    urls = [
        f"{TCB}/w/wb/wb01.djhtm?a={code}",
        f"{BASE}/yp/wb01.djhtm?a={code}",
        f"{TCB}/w/wb/wb01.djhtm?a={code.lower()}",
    ]
    PERIOD_MAP = {
        "一個月":"1M","三個月":"3M","六個月":"6M",
        "一年":"1Y","二年":"2Y","三年":"3Y","五年":"5Y",
        "1個月":"1M","3個月":"3M","6個月":"6M",
        "1M":"1M","3M":"3M","6M":"6M","1Y":"1Y","3Y":"3Y","5Y":"5Y",
        "1月":"1M","3月":"3M","6月":"6M",
    }
    for url in urls:
        try:
            hdr_ref = {**HDR, "Referer": f"{BASE}/yp/wb01.djhtm"}
            # v14.1: 用 fetch_url_with_retry，統一 Big5 解碼
            r = fetch_url_with_retry(url, headers=hdr_ref, timeout=25, retries=2)
            if r is None: continue
            soup = BeautifulSoup(r.text, "lxml")

            # ── Strategy 1: row label contains period name ──────
            for tbl in soup.find_all("table"):
                txt = tbl.get_text()
                if "報酬率" not in txt and "績效" not in txt: continue
                for row in tbl.find_all("tr"):
                    cols = [td.get_text(strip=True) for td in row.find_all(["td","th"])]
                    if len(cols) < 2: continue
                    label = cols[0]
                    for period_cn, period_key in PERIOD_MAP.items():
                        if period_cn in label and period_key not in out:
                            for c in cols[1:]:
                                c_c = c.replace("%","").replace(",","").strip()
                                try:
                                    v = float(c_c)
                                    if -99 < v < 500:
                                        out[period_key] = v; break
                                except: pass

            # ── Strategy 2: column headers contain period names ──
            if not out:
                for tbl in soup.find_all("table"):
                    txt = tbl.get_text()
                    if not any(p in txt for p in ["一年","三年","1Y","六個月"]): continue
                    rows = tbl.find_all("tr")
                    if len(rows) < 2: continue
                    # First try last header row
                    for hi in range(min(3, len(rows))):
                        header = [td.get_text(strip=True) for td in rows[hi].find_all(["th","td"])]
                        period_idx = {}
                        for ci, h in enumerate(header):
                            for period_cn, period_key in PERIOD_MAP.items():
                                if period_cn in h and ci not in period_idx:
                                    period_idx[ci] = period_key
                        if len(period_idx) >= 3:
                            # Next row(s) are data
                            for row in rows[hi+1:hi+4]:
                                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                                for ci, period_key in period_idx.items():
                                    if ci < len(cells) and period_key not in out:
                                        c_c = cells[ci].replace("%","").replace(",","").strip()
                                        try:
                                            v = float(c_c)
                                            if -99 < v < 500:
                                                out[period_key] = v
                                        except: pass
                            if out: break

            if out:
                print(f"[wb01 perf] ✅ {out}")
                break
        except Exception as e:
            print(f"[fetch_perf_wb01] {url[:50]} ERR: {e}")
    return out


def fetch_risk_metrics(code: str) -> dict:
    """
    抓取 MoneyDJ 績效評比頁（wb07.djhtm），回傳：
    {
      "risk_table":   {期間: {標準差, Sharpe, Alpha, Beta, R-squared, Tracking Error, Variance}}
      "peer_compare": {項目: {年平均報酬率, Sharpe, Beta, 標準差, 同類排名...}}
      "yearly_stats": {年份: {年化標準差, Beta, Sharpe Ratio, ...}}
    }
    """
    try:
        BASE = "https://www.moneydj.com/funddj"
        TCB  = "https://tcbbankfund.moneydj.com"
        urls = [
            f"{BASE}/yp/wb07.djhtm?a={code}",
            f"{TCB}/w/wb/wb07.djhtm?a={code}",
        ]
        out = {}

        for url in urls:
            # v14.2: Big5 統一解碼
            r = fetch_url_with_retry(url, headers={**HDR, "Referer": f"{BASE}/yp/wb07.djhtm"}, timeout=25, retries=2)
            if r is None: continue
            soup = BeautifulSoup(r.text, "lxml")
            tables = soup.find_all("table")

            for tbl in tables:
                txt = tbl.get_text()
                rows = tbl.find_all("tr")
                if len(rows) < 2: continue

                # ─── 主風險指標表（六個月/一年/三年/五年/十年 × 標準差/Sharpe/Alpha…）──
                # v14.3: 條件擴充 — 近三月/近3月 都算，且 Sharpe 是數字不受 Big5 影響
                if ("標準差" in txt or "Sharpe" in txt) and (
                    "一年" in txt or "三年" in txt or
                    "近三月" in txt or "近3月" in txt or "六個月" in txt
                ):
                    # v14.3: 加入所有實際出現的期間名稱（Big5 解碼後確認）
                    PERIODS = [
                        "近三月","近3月","三個月","六個月","近六月",  # 短期
                        "一年","二年","三年","五年","十年",            # 長期
                        "近一年","近三年","近五年",                    # 另一種寫法
                        "一個月","三個月","六個月",                   # 全寫
                    ]
                    # 同時建立 Big5 轉換對照（部分環境解碼不完整時備用）
                    PERIOD_ALIAS = {
                        "近三月":"近三月","近3月":"近三月",
                        "六個月":"六個月","三個月":"三個月",
                        "一年":"一年","三年":"三年","五年":"五年","十年":"十年",
                    }
                    # Find the header row that contains period names
                    hdr_idx = None
                    for ri, row in enumerate(rows):
                        cells_txt = [td.get_text(strip=True) for td in row.find_all(["th","td"])]
                        if any(p in cells_txt for p in PERIODS):
                            hdr_idx = ri; break
                    if hdr_idx is None: continue
                    hdr_cells = [td.get_text(strip=True) for td in rows[hdr_idx].find_all(["th","td"])]
                    # Map column index → period name
                    col_period = {}
                    for ci, h in enumerate(hdr_cells):
                        if h in PERIODS: col_period[ci] = h
                    if not col_period: continue
                    periods_found = list(col_period.values())
                    risk_table = {p: {} for p in periods_found}
                    for row in rows[hdr_idx+1:]:
                        cols = [td.get_text(strip=True) for td in row.find_all("td")]
                        if not cols or len(cols) < 2: continue
                        metric = cols[0]
                        if not metric: continue
                        for ci, period in col_period.items():
                            if ci < len(cols):
                                v_s = cols[ci].replace(",","").strip()
                                # v13: 用 safe_float 取代裸 float()
                                _sf = safe_float(v_s)
                                risk_table[period][metric] = _sf if _sf is not None else cols[ci]
                    if any(risk_table[p] for p in periods_found):
                        out["risk_table"] = risk_table
                        print(f"[risk_metrics] 風險指標 {periods_found}")

                # ─── 同類比較表（peer_compare）─────────────────────────
                elif ("同投資類型" in txt or "同投資區域" in txt or "同類" in txt) and "報酬" in txt:
                    # Try to find header row (3+ cells)
                    hdr_idx = None
                    for ri, row in enumerate(rows):
                        cells = row.find_all(["th","td"])
                        if len(cells) >= 3:
                            hdr_idx = ri; break
                    if hdr_idx is None: continue
                    hdr = [td.get_text(strip=True) for td in rows[hdr_idx].find_all(["th","td"])]
                    peer = {}
                    for row in rows[hdr_idx+1:]:
                        cols = [td.get_text(strip=True) for td in row.find_all("td")]
                        if not cols or len(cols) < 2: continue
                        row_key = cols[0]
                        if not row_key: continue
                        row_data = {}
                        for i in range(1, len(cols)):
                            h = hdr[i] if i < len(hdr) else f"col{i}"
                            v_s = cols[i].replace(",","").strip()
                            try: row_data[h] = float(v_s.replace("%",""))
                            except: row_data[h] = cols[i]
                        if row_data: peer[row_key] = row_data
                    if peer:
                        out["peer_compare"] = peer
                        print(f"[risk_metrics] 同類比較 {list(peer.keys())[:3]}")

                # ─── 年度統計（2020-2025）────────────────────────────
                elif "年化標準差" in txt and any(str(y) in txt for y in range(2019,2027)):
                    hdr_idx = None
                    for ri, row in enumerate(rows):
                        cells = [td.get_text(strip=True) for td in row.find_all(["th","td"])]
                        if any(c.isdigit() and 2018 <= int(c) <= 2030 for c in cells):
                            hdr_idx = ri; break
                    if hdr_idx is None: continue
                    hdr = [td.get_text(strip=True) for td in rows[hdr_idx].find_all(["th","td"])]
                    years = [h for h in hdr if h.isdigit() and 2018 <= int(h) <= 2030]
                    yearly = {}
                    for row in rows[hdr_idx+1:]:
                        cols = [td.get_text(strip=True) for td in row.find_all("td")]
                        if not cols or len(cols) < 2: continue
                        metric_name = cols[0]
                        if not metric_name: continue
                        for i, yr in enumerate(years):
                            if yr not in yearly: yearly[yr] = {}
                            if i+1 < len(cols):
                                try: yearly[yr][metric_name] = float(cols[i+1])
                                except: yearly[yr][metric_name] = cols[i+1]
                    if yearly:
                        out["yearly_stats"] = yearly
                        print(f"[risk_metrics] 年度統計 {list(yearly.keys())}")

            if out: break  # Got data from first working URL
        return out
    except Exception as e:
        print(f"[fetch_risk_metrics] {e}")
        return {}




# ════════════════════════════════════════════════════════════
# 持股（yp013001.djhtm）: 產業配置 + 前10大持股
# ════════════════════════════════════════════════════════════
def fetch_holdings(code: str) -> dict:
    """
    抓取 MoneyDJ 持股頁，回傳：
    {
      "data_date":   "2026/01",
      "sector_alloc": [{"name": str, "pct": float, "amount": float}],
      "top_holdings": [{"name": str, "sector": str, "pct": float}],
    }
    """
    try:
        # v14.5: 先試 tcbbankfund 子網域（Streamlit Cloud IP 封鎖較少），再試 www
        _hold_page = "yp013000" if _is_domestic_code(code) else "yp013001"
        _hold_urls = [
            f"https://tcbbankfund.moneydj.com/funddj/yp/{_hold_page}.djhtm?a={code}",
            f"https://www.moneydj.com/funddj/yp/{_hold_page}.djhtm?a={code}",
        ]
        r = None
        for _hu in _hold_urls:
            r = fetch_url_with_retry(_hu, headers=HDR, timeout=20, retries=2)
            if r is not None and len(r.text) > 500:
                break
            r = None
        if r is None:
            return {}
        soup = BeautifulSoup(r.text, "lxml")
        out = {}

        for tbl in soup.find_all("table"):
            txt = tbl.get_text()

            # ── 產業配置 ──
            if "資訊科技" in txt or "工業" in txt or "金融" in txt:
                rows = tbl.find_all("tr")
                sectors = []
                # MoneyDJ table rule: row0=title(colspan), row1=colheader, row2+=data
                # MUST skip row0 (title) AND row1 (column headers) → start from rows[2:]
                _SKIP_KW = ("資料日期","産業","投資名稱","比例","投資金額","名稱",
                            "Fund","月份","持股","類別","資料月份","日期")
                for row in rows[2:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 2:
                        name = cols[0].strip()
                        # Skip header-like or empty rows
                        if not name or any(kw in name for kw in _SKIP_KW): continue
                        if len(name) > 25: continue   # real sector names ≤ 25 chars
                        # Find pct: last column containing a number
                        pct = 0.0
                        amount = 0.0
                        for c in reversed(cols[1:]):
                            try:
                                pct = float(c.replace("%","").replace(",","").strip())
                                if 0 < pct < 100: break
                            except: pass
                        if len(cols) >= 3:
                            try: amount = float(cols[1].replace(",","").replace("%",""))
                            except: pass
                        if pct > 0 and name:
                            sectors.append({"name": name, "amount": amount, "pct": pct})
                if sectors:
                    out["sector_alloc"] = sectors
                    print(f"[holdings] 產業 {len(sectors)} 類")

            # ── 前10大持股 ──
            if "投資名稱" in txt and "比例" in txt:
                rows = tbl.find_all("tr")
                holdings = []
                # MoneyDJ: row0=title, row1=column headers, row2+=data → rows[2:]
                _SKIP_H = ("資料日期","投資名稱","比例","産業","持股","金額","名稱",
                           "月份","資料月份","日期","Fund","순위","排名")
                for row in rows[2:]:
                    cols = [td.get_text(strip=True) for td in row.find_all("td")]
                    if len(cols) >= 2:
                        raw = cols[0].strip()
                        # Skip header-like rows
                        if not raw: continue
                        if any(kw in raw for kw in _SKIP_H): continue
                        if len(raw) > 60: continue    # long = still a header or garbage
                        # Find pct: last numeric column
                        pct_txt = ""
                        for c in reversed(cols):
                            c2 = c.replace("%","").strip()
                            try:
                                v = float(c2)
                                if 0 < v < 100:
                                    pct_txt = c2; break
                            except: pass
                        # 格式: "NVIDIA CORP,資訊科技" or just "NVIDIA CORP"
                        parts = raw.split(",", 1)
                        name   = parts[0].strip()
                        sector = parts[1].strip() if len(parts) > 1 else ""
                        # Also try splitting by known sector keywords for TW domestic funds
                        if not sector and len(parts) == 1:
                            for _sk in ["資訊科技","金融","工業","非必需消費","健康護理",
                                        "通訊服務","能源","必需消費","材料","公用事業",
                                        "房地產","流動資金","原物料","其他"]:
                                if _sk in name:
                                    idx_sk = name.index(_sk)
                                    sector = name[idx_sk:]
                                    name   = name[:idx_sk].strip()
                                    break
                        try:
                            pct = float(pct_txt)
                            if name and pct > 0:
                                holdings.append({"name": name, "sector": sector, "pct": pct})
                        except: pass
                if holdings:
                    out["top_holdings"] = holdings[:10]
                    print(f"[holdings] 前10大持股 {len(out['top_holdings'])} 筆")

        # 資料日期
        import re as _re
        full_txt = soup.get_text()
        dm = _re.search(r"資料月份[:：]\s*(\d{4}/\d{2})", full_txt)
        if dm: out["data_date"] = dm.group(1)

        return out
    except Exception as e:
        print(f"[fetch_holdings] {e}")
        return {}



# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：fetch_fund_by_key / fetch_fund_by_code
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# 主入口：full_key → 淨值 + 配息 + MK
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
                except: pass
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
        result["metrics"]   = calc_metrics(s, divs)
        # v18.53: 同 _finish_metrics — 境內缺 wb01 perf["1Y"] 改用本地計算
        if not isinstance(result.get("perf"), dict):
            result["perf"] = {}
        if result["perf"].get("1Y") is None:
            _local_1y = (result.get("metrics") or {}).get("ret_1y_total")
            if _local_1y is not None:
                result["perf"]["1Y"] = _local_1y
                result["perf_source"] = result.get("perf_source") or "local_calc"
    else:
        result["error"] = f"{full_key} 只取到 {len(s)} 筆淨值（需≥20）"
    return result


# 保留相容性（舊 main.py 呼叫）
def fetch_fund_by_code(insurance_code: str, gemini_key: str = "",
                       manual_full_key: str = "",
                       manual_nav_csv: str = "") -> dict:
    """相容舊介面：直接用 insurance_code 當 full_key"""
    key = manual_full_key.strip().upper() if manual_full_key.strip() else insurance_code.strip().upper()
    return fetch_fund_by_key(key, manual_nav_csv=manual_nav_csv)





# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：structure: STRUCTURE_PAGES + _parse_pct_table + fetch_fund_structure
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# 基金結構分析（資產配置、持股、地區、績效）
# 從 MoneyDJ 保險子網域直接抓（與淨值/配息相同管道）
# ════════════════════════════════════════════════════════════

STRUCTURE_PAGES = {
    "資產配置": "/w/wh/wh02.djhtm?a={fk}",
    "地區配置": "/w/wh/wh03.djhtm?a={fk}",
    "持股明細": "/w/wq/wq06.djhtm?a={fk}",
    "債券明細": "/w/wq/wq06_bond.djhtm?a={fk}",
    "績效比較": "/w/wb/wb01.djhtm?a={fk}",
    "風險等級": "/w/wr/wr01.djhtm?a={fk}",
    "基金概況": "/w/wf/wf11.djhtm?a={fk}",
}

def _parse_pct_table(soup, keywords=None) -> list:
    """通用：從 HTML 中找含百分比或數字的表格，回傳 [{name, value, pct}]"""
    results = []
    for tbl in soup.find_all("table"):
        txt = tbl.get_text()
        if keywords and not any(k in txt for k in keywords):
            continue
        for row in tbl.find_all("tr")[1:]:
            cols = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cols) < 2:
                continue
            name = cols[0]
            val  = ""
            pct  = 0.0
            for c in cols[1:]:
                # 找百分比
                pm = re.search(r"([\d.]+)\s*%", c)
                if pm:
                    pct = float(pm.group(1))
                    val = c
                    break
                # 找數字
                nm = re.search(r"[\d,]+\.?\d*", c.replace(",",""))
                if nm:
                    val = c
            if name and (pct > 0 or val):
                results.append({"name": name, "value": val, "pct": pct})
    return results


def fetch_fund_structure(full_key: str, portal: str = "") -> dict:
    """
    抓取基金結構分析資料：
    - 資產配置（股/債/現金比例）
    - 地區配置（美國/亞洲/歐洲…）
    - 前10大持股或債券
    - 績效比較
    - 風險等級
    從 MoneyDJ 保險子網域直接存取（Colab 可用）。
    """
    if not full_key:
        return {}

    bases = []
    if portal in PORTAL_CFG:
        bases.append(PORTAL_CFG[portal]["base_url"])
    # 子網域猜測
    mj = full_key.split("-")[-1] if "-" in full_key else full_key
    for p_name, p_cfg in PORTAL_CFG.items():
        if p_cfg["base_url"] not in bases:
            bases.append(p_cfg["base_url"])
    # 通用 MoneyDJ fallback
    bases.append("https://www.moneydj.com/funddj")

    struct = {}

    for page_name, path_tmpl in STRUCTURE_PAGES.items():
        path = path_tmpl.format(fk=full_key)
        for base in bases:
            url = base.rstrip("/") + path
            try:
                r = requests.get(url, headers=HDR, timeout=20, proxies=_proxies(), verify=_ssl_verify())
                if r.status_code != 200:
                    continue
                if len(r.text) < 500:
                    continue
                soup = BeautifulSoup(r.text, "lxml")
                text = soup.get_text()

                # ── 資產配置 ──────────────────────────────────
                if page_name == "資產配置":
                    rows = _parse_pct_table(soup, ["股票","債券","現金","Cash","Bond","Stock"])
                    if rows:
                        struct["asset_allocation"] = rows
                        print(f"[structure 資產配置] {len(rows)} 類 ({url[:50]})")
                        break

                # ── 地區配置 ──────────────────────────────────
                elif page_name == "地區配置":
                    rows = _parse_pct_table(soup, ["美國","歐洲","亞洲","北美","新興"])
                    if rows:
                        struct["geo_allocation"] = rows
                        print(f"[structure 地區配置] {len(rows)} 地區")
                        break

                # ── 持股明細 ──────────────────────────────────
                elif page_name == "持股明細":
                    holdings = []
                    for tbl in soup.find_all("table"):
                        for row in tbl.find_all("tr")[1:16]:  # 前15筆
                            cols = [td.get_text(strip=True) for td in row.find_all("td")]
                            if len(cols) >= 2 and cols[0] and cols[1]:
                                pct = 0.0
                                for c in cols:
                                    pm = re.search(r"([\d.]+)\s*%", c)
                                    if pm: pct = float(pm.group(1)); break
                                holdings.append({"name": cols[0], "ticker": cols[1] if len(cols)>2 else "", "pct": pct})
                        if holdings: break
                    if holdings:
                        struct["top_holdings"] = holdings[:15]
                        print(f"[structure 持股] {len(holdings)} 筆")
                        break

                # ── 債券明細 ──────────────────────────────────
                elif page_name == "債券明細":
                    bonds = []
                    for tbl in soup.find_all("table"):
                        for row in tbl.find_all("tr")[1:16]:
                            cols = [td.get_text(strip=True) for td in row.find_all("td")]
                            if len(cols) >= 2 and cols[0]:
                                pct = 0.0
                                for c in cols:
                                    pm = re.search(r"([\d.]+)\s*%", c)
                                    if pm: pct = float(pm.group(1)); break
                                bonds.append({"name": cols[0], "coupon": cols[2] if len(cols)>2 else "", "pct": pct})
                        if bonds: break
                    if bonds:
                        struct["top_bonds"] = bonds[:15]
                        print(f"[structure 債券] {len(bonds)} 筆")
                        break

                # ── 績效比較 ──────────────────────────────────
                elif page_name == "績效比較":
                    rows = _parse_pct_table(soup, ["1月","3月","6月","1年","3年","基準"])
                    if rows:
                        struct["performance"] = rows
                        print(f"[structure 績效] {len(rows)} 筆")
                        break

                # ── 風險等級 ──────────────────────────────────
                elif page_name == "風險等級":
                    risk_text = ""
                    for tag in soup.find_all(["td","div","span","p"]):
                        t = tag.get_text(strip=True)
                        if re.search(r"[RR][Rr]|風險|等級|[1-7]級", t) and len(t) < 200:
                            risk_text = t; break
                    if risk_text:
                        struct["risk_info"] = risk_text
                        print(f"[structure 風險] {risk_text[:60]}")
                        break

                # ── 基金概況 ──────────────────────────────────
                elif page_name == "基金概況":
                    info = {}
                    for tbl in soup.find_all("table"):
                        for row in tbl.find_all("tr"):
                            cols = [td.get_text(strip=True) for td in row.find_all("td")]
                            if len(cols) >= 2:
                                k, v = cols[0], cols[1]
                                if any(x in k for x in ["成立","規模","基金","經理","計價","費率"]):
                                    info[k] = v
                    if info:
                        struct["fund_info"] = info
                        print(f"[structure 基金概況] {len(info)} 項")
                        break

            except Exception as e:
                print(f"[structure {page_name}] {url[:50]} ERR: {e}")
                continue

    return struct



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
            ("JPY", "USD"): ("DEXJPUS", False),
            ("CHF", "USD"): ("DEXSZUS", False),
            ("CNH", "USD"): ("DEXCHUS", False),
            ("CNY", "USD"): ("DEXCHUS", False),
            ("EUR", "USD"): ("DEXUSEU", "inv"),  # series 是 USD per EUR
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
                ("JPY", "USD"): "DEXJPUS",
                ("CHF", "USD"): "DEXSZUS",
                ("CNH", "USD"): "DEXCHUS",
                ("CNY", "USD"): "DEXCHUS",
                ("EUR", "USD"): "DEXUSEU",
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
@_ttl_cache(ttl_sec=300, maxsize=128)   # v18.58: T7 每 fund render 一次，盤中 5min 鮮度足夠
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
