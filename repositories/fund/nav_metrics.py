"""repositories/fund/nav_metrics.py — v19.200 P1-5 NAV history + perf/risk/holdings/div。

從 fund_repository 主檔抽出(原 line 3555-4546):
- fetch_nav / fetch_nav_history_long / _fetch_nav_* (multi-source NAV)
- fetch_div / _fetch_domestic_perf / fetch_performance_wb01
- fetch_risk_metrics / fetch_holdings
"""
from __future__ import annotations

import re
import requests
import pandas as pd
from bs4 import BeautifulSoup

from infra.cache import (  # noqa: F401
    _ttl_cache, _daily_cache, register_cache, _CACHE_DIR, _FUND_SNAPSHOT, _cache_path,
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

from repositories.fund.sources import *  # noqa: F401, F403


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
            except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
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
                # F-PROV-1 phase 16 v19.102 — provenance(Series.attrs;動態 host:endpoint)
                _host_fn = url.split("/")[2] if "://" in url else "moneydj"
                _ep_fn = url.split("?")[0].rsplit("/", 1)[-1]
                s.attrs["source"] = f"MoneyDJ:{_host_fn}:{_ep_fn}:fetch_nav"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                # v19.162 A1 Phase B 後續:pandera schema 驗 final contract
                # (NAV-specific:>0 / 多源 source prefix);schema 違反 = 上游 bug,
                # 不掩蓋(§1 Fail Loud)
                from shared.schemas import validate_fund_nav
                validate_fund_nav(s)
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
    except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
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
                # F-PROV-1 phase 16 v19.102 — provenance(Series.attrs)
                _ep_cn = url.split("?")[0].rsplit("/", 1)[-1]
                s.attrs["source"] = f"Cnyes:api:v1/fund:{_ep_cn}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
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
                    s.attrs["source"] = "Cnyes:html:__NEXT_DATA__"
                    s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                    return s
            except Exception as _e_j:
                print(f"[_fetch_nav_cnyes] __NEXT_DATA__ JSON ERR: {_e_j}")
        s_tbl = _parse_html_nav_table(r.text)
        if isinstance(s_tbl, pd.Series) and not s_tbl.empty:
            s_tbl.attrs["source"] = "Cnyes:html:nav_table"
            s_tbl.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        return s_tbl
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
                # F-PROV-1 phase 16 v19.102 — provenance(動態 host:endpoint)
                _host_mh = url.split("/")[2] if "://" in url else "moneydj"
                _ep_mh = url.split("?")[0].rsplit("/", 1)[-1]
                s.attrs["source"] = f"MoneyDJ:{_host_mh}:{_ep_mh}:nav_history_long"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
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
                # F-PROV-1 phase 16 v19.102 — provenance(Series.attrs)
                _ep_fr = url.split("?")[0].rsplit("/", 1)[-1]
                s.attrs["source"] = f"FundRich:api:v1/funds:{_ep_fr}"
                s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
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
                    # F-PROV-1 phase 16 v19.102 — provenance(Series.attrs)
                    _host_fc = url.split("/")[2] if "://" in url else "fundclear"
                    s.attrs["source"] = f"FundClear:{_host_fc}:nav_history_long:json"
                    s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                    return s
            except Exception:
                # CSV fallback
                import io
                try:
                    df = pd.read_csv(io.BytesIO(r.content), encoding="utf-8-sig")
                    items = df.to_dict("records")
                    s = _parse_nav_json_items(items)
                    if not s.empty and len(s) >= 50:
                        _host_fc = url.split("/")[2] if "://" in url else "fundclear"
                        s.attrs["source"] = f"FundClear:{_host_fc}:nav_history_long:csv"
                        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
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
        # v19.226 F-PROV-1 B3:disk cache load 後 attrs 不存,補 source(§2.2)
        cached.attrs.setdefault("source", f"Fund:fetch_nav_history_long:disk_cache:{code}")
        cached.attrs.setdefault("fetched_at", pd.Timestamp.now('UTC').isoformat())
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
        # v19.226 F-PROV-1 B3:fallback path 補 source(§2.2 schema-additive,
        # 不蓋過 fetch_nav 已 set 的 source)
        s.attrs.setdefault("source", f"Fund:fetch_nav_history_long:fallback_fetch_nav:{code}")
        s.attrs.setdefault("fetched_at", pd.Timestamp.now('UTC').isoformat())
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
                        except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
            if divs: break
        except Exception as e:
            print(f"[div] {e}")
    seen=set(); out=[]
    for d in sorted(divs, key=lambda x:x["date"], reverse=True):
        if d["date"] not in seen: seen.add(d["date"]); out.append(d)
    out = out[:24]
    # v19.163 A1 Phase B 後續 part 2:pandera schema 驗 final contract
    # (list[dict] / 長度 <= 24 / amount > 0 且 < 100 / date unique)
    # schema 違反 = 上游 HTML 解析 bug,當場 raise(§1 Fail Loud)
    from shared.schemas import validate_fund_dividends
    validate_fund_dividends(out)
    # v19.226 F-PROV-1 B2:list-of-dict 每 element 加 source + fetched_at(§2.2)
    # schema-additive,在 validate 後加避免 pandera schema 不認得
    if out:
        _fa = pd.Timestamp.now('UTC').isoformat()
        for _d in out:
            _d["source"] = f"MoneyDJ:fetch_div:{full_key}"
            _d["fetched_at"] = _fa
    return out



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
                # v19.233 F-PROV-1 cluster C 補洞:dict 加 _source(schema-additive,
                # caller 用 perf["1Y"] 直接 key access 不會踩到 _source key)
                perf["_source"] = f"MoneyDJ:{base.split('//')[1].split('/')[0]}:yp020000:{code}"
                perf["_fetched_at"] = pd.Timestamp.now('UTC').isoformat()
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
                                except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
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
                                        except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                            if out: break

            if out:
                print(f"[wb01 perf] ✅ {out}")
                # F-PROV-1 phase 13 v19.99 — provenance(schema-additive)
                _host_wb = url.split("/")[2] if "://" in url else "moneydj"
                out["source"] = f"MoneyDJ:{_host_wb}:wb01"
                out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
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
                            except Exception: row_data[h] = cols[i]
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
                                except Exception: yearly[yr][metric_name] = cols[i+1]
                    if yearly:
                        out["yearly_stats"] = yearly
                        print(f"[risk_metrics] 年度統計 {list(yearly.keys())}")

            if out:
                # F-PROV-1 phase 13 v19.99 — provenance(schema-additive)
                _host_wb07 = url.split("/")[2] if "://" in url else "moneydj"
                out["source"] = f"MoneyDJ:{_host_wb07}:wb07"
                out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
                break  # Got data from first working URL
        return out
    except Exception as e:
        print(f"[fetch_risk_metrics] {e}")
        return {}




# ════════════════════════════════════════════════════════════
# 持股（yp013001.djhtm）: 產業配置 + 前10大持股
# ════════════════════════════════════════════════════════════
@register_cache
@_daily_cache  # v19.250 R20:MoneyDJ 持股月更新,改日 cache(保存當日,隔日 TW 午夜 miss 重抓)
def fetch_holdings(code: str) -> dict:
    """
    抓取 MoneyDJ 持股頁，回傳：
    {
      "data_date":   "2026/01",
      "sector_alloc": [{"name": str, "pct": float, "amount": float}],
      "top_holdings": [{"name": str, "sector": str, "pct": float}],
    }
    """
    import sys as _sys_h
    try:
        # v14.5 + v19.251 R21 + v19.252 R22:擴大 fallback chain + 保險平台子網域
        # User 反饋(R22):R21 6 URL 對保險平台代碼(JFZN3/TLZF9/FLFM1 等)仍空,
        # 比照 _src_insurance_subdomain_nav(sources.py L2406-2473)依代碼前綴展開
        # _INSURANCE_SUBDOMAIN_HINTS portal,套到 yp013xxx 頁。
        # NAS proxy 已內建於 fetch_url_with_retry → infra.proxy.fetch_url。
        _code_up = (code or "").upper().strip()
        _hold_page = "yp013000" if _is_domestic_code(_code_up) else "yp013001"
        # 基線 6 URL(R21 chain)
        _hold_urls = [
            f"https://tcbbankfund.moneydj.com/funddj/yp/{_hold_page}.djhtm?a={code}",
            f"https://chubb.moneydj.com/funddj/yp/{_hold_page}.djhtm?a={code}",
            f"https://www.moneydj.com/funddj/yp/{_hold_page}.djhtm?a={code}",
            f"https://taishinlife.moneydj.com/funddj/yp/{_hold_page}.djhtm?a={code}",
            f"https://www.moneydj.com/funddj/wq/wq06.djhtm?a={code}",
            f"https://tcbbankfund.moneydj.com/funddj/wq/wq06.djhtm?a={code}",
        ]
        # v19.252 R22:依 _INSURANCE_SUBDOMAIN_HINTS 前綴展開 portal 子網域 yp013xxx 頁
        # JF→jpmorgan/jpmf/jpmfund;TL→tlife/twlife/taiwanlife;FL→franklintem/franklin;
        # CT→cathaylife/ctbclife/ctlife;NS→nanshan;FS→fubonlife;...
        # 同時對 wq06 替代頁也展開(部分 fund 走 /w/wq 路徑)。
        _ins_portals: list = []
        for _pfx, _portals in _INSURANCE_SUBDOMAIN_HINTS.items():
            if _code_up.startswith(_pfx):
                _ins_portals.extend(_portals)
        # 去重保序
        _seen_p: set = set()
        _ins_portals = [p for p in _ins_portals if not (p in _seen_p or _seen_p.add(p))]
        for _p in _ins_portals:
            _hold_urls.append(
                f"https://{_p}.moneydj.com/funddj/yp/{_hold_page}.djhtm?a={code}")
            _hold_urls.append(
                f"https://{_p}.moneydj.com/w/wq/wq06.djhtm?a={code}")
        r = None
        _attempts: list = []  # 診斷:每個 URL 試了什麼結果
        for _hu in _hold_urls:
            try:
                _r = fetch_url_with_retry(_hu, headers=HDR, timeout=20, retries=2)
                _len = len(_r.text) if _r is not None else 0
                _attempts.append({"url": _hu, "status": "ok" if _r else "no_resp", "len": _len})
                if _r is not None and _len > 500:
                    r = _r
                    print(f"[holdings:{code}] ✅ {_hu[:60]}... len={_len}",
                          file=_sys_h.stderr)
                    break
            except Exception as _e:
                _attempts.append({"url": _hu, "status": f"err:{type(_e).__name__}", "len": 0})
                print(f"[holdings:{code}] ❌ {_hu[:60]}... {type(_e).__name__}: {_e}",
                      file=_sys_h.stderr)
        if r is None:
            # Fail Loud(§1):列出全部嘗試的 URL 給 audit
            print(f"[holdings:{code}] 全 {len(_hold_urls)} 候選 URL 失敗:"
                  f"{[(a['status'], a['len']) for a in _attempts]}",
                  file=_sys_h.stderr)
            # v19.276 fallback:MoneyDJ 全失敗 → 試 cnyes 持股 API
            _cy = fetch_holdings_cnyes(code)
            if _cy.get("top_holdings") or _cy.get("sector_alloc"):
                print(f"[holdings:{code}] ↩ cnyes fallback 命中(MoneyDJ 全失敗)",
                      file=_sys_h.stderr)
                return _cy
            return {"source": "MoneyDJ:all_failed",
                    "attempts": _attempts,
                    "fetched_at": pd.Timestamp.now('UTC').isoformat()}
        soup = BeautifulSoup(r.text, "lxml")
        out = {}

        for tbl in soup.find_all("table"):
            txt = tbl.get_text()

            # ── 產業配置 ──
            # v19.249 R18 bug fix:原寫死 keyword 「資訊科技/工業/金融」只覆蓋股票型 sector,
            # multi-asset fund(ACCP138 等)的 asset class「全球股票/投資等級債券/現金與約當現金」
            # 完全 0 命中 → sector_alloc 沒抓 → out 空 → AI 顯示「MoneyDJ 未提供持股」。
            # 改用結構性偵測:含 sector 類 header(產業/資產類別/類別/地區)+ 比例 + 無投資名稱
            # column(避免吃到 top_holdings table)。對齊 SSOT 結構契約而非 hardcoded names。
            _SECTOR_HEADER_KW = ("產業", "産業", "資產類別", "類別", "地區")  # 涵蓋股票/多重資產/區域
            _has_sector_header = any(kw in txt for kw in _SECTOR_HEADER_KW)
            _has_pct_header = "比例" in txt
            _has_top_holdings_marker = "投資名稱" in txt
            if _has_sector_header and _has_pct_header and not _has_top_holdings_marker:
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
                            except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                        if len(cols) >= 3:
                            try: amount = float(cols[1].replace(",","").replace("%",""))
                            except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                        if pct > 0 and name:
                            sectors.append({"name": name, "amount": amount, "pct": pct})
                if sectors:
                    out["sector_alloc"] = sectors
                    print(f"[holdings] 產業 {len(sectors)} 類")

            # ── 前10大持股 ──
            # v19.249 R18:加「目前無資料」explicit skip 避免日後 parser 誤吃空表 garbage
            if "目前無資料" in txt and "投資名稱" in txt:
                print(f"[holdings] top_holdings 表存在但顯示「目前無資料」(multi-asset / 透明度不足 fund 常態)")
                continue
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
                            except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
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
                        except (ValueError, TypeError, AttributeError, IndexError, KeyError): pass  # smoke-allow-pass — parse best-effort,row invalid skip
                if holdings:
                    out["top_holdings"] = holdings[:10]
                    print(f"[holdings] 前10大持股 {len(out['top_holdings'])} 筆")

        # 資料日期
        import re as _re
        full_txt = soup.get_text()
        dm = _re.search(r"資料月份[:：]\s*(\d{4}/\d{2})", full_txt)
        if dm: out["data_date"] = dm.group(1)

        # F-PROV-1 phase 13 v19.99 — provenance(schema-additive,僅實際拿到資料時寫入)
        if out:
            out["source"] = f"MoneyDJ:yp:{_hold_page}"
            out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
        # v19.276 fallback:MoneyDJ 頁抓到但無持股(multi-asset / FoF 透明度不足 /
        # parser 0 命中)→ 試 cnyes 持股 API。命中則整包以 cnyes 為準(provenance
        # 一致),不與 MoneyDJ 空殼合併以免血緣混淆(§2.2)。
        if not (out.get("top_holdings") or out.get("sector_alloc")):
            _cy = fetch_holdings_cnyes(code)
            if _cy.get("top_holdings") or _cy.get("sector_alloc"):
                print(f"[holdings:{code}] ↩ cnyes fallback 命中(MoneyDJ 頁無持股)",
                      file=_sys_h.stderr)
                return _cy
        return out
    except Exception as e:
        print(f"[fetch_holdings] {e}")
        return {}



# ════════════════════════════════════════════════════════════
# v11.0 B-9b-6：fetch_fund_by_key / fetch_fund_by_code
# ════════════════════════════════════════════════════════════

# ════════════════════════════════════════════════════════════
# 主入口：full_key → 淨值 + 配息 + MK
