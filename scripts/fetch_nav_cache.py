#!/usr/bin/env python3
"""
fetch_nav_cache.py — GitHub Actions 每日淨值快取抓取器 v1.0

執行環境：GitHub Actions (ubuntu-latest, Azure IP)
目的：繞過 Streamlit Cloud US IP 被台灣財務網站封鎖的問題。
     每日定時抓取 TDCC/MoneyDJ 淨值，存入 cache/nav/{CODE}.json，
     Streamlit Cloud 再從快取讀取。

快取格式（cache/nav/TLZF9.json）：
{
  "code": "TLZF9",
  "updated_at": "2026-03-29T00:30:00",
  "source": "tdcc",
  "count": 365,
  "history": [{"date": "2026-03-28", "nav": 12.34}, ...]
}
"""
import json, time, datetime, re, os, sys
from pathlib import Path

# v18.222：把 repo root 加進 sys.path，讓「python scripts/fetch_nav_cache.py」
# 也能 import repositories.*（Sheet 自動同步用）；否則 sys.path[0] 只有 scripts/。
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

# ── 目標基金代碼 ─────────────────────────────────────────────────────
# v18.178 (#2)：補齊組合內所有 code（與 user 持倉對齊）。
#   原漏列 ACDD01（安聯台灣大壩）→ 無 cache → T5 相關係數矩陣算不出（NaN/0）。
#   ⚠️ 此清單須與 Google Sheet 保單分頁的基金代碼保持同步；新增基金時記得補。
FUND_CODES = [
    "TLZF9", "ACTI71", "ACTI98", "FLFM1", "CTZP0",
    "ANZ89", "JFZN3",  "ACTI94", "ACCP138", "ACDD19",
    "ACDD01",
]

# 境內基金代碼（安聯台灣境內，走 SITCA 而非 TDCC 境外 API）
DOMESTIC_PREFIXES = ("ACTI", "ACCP", "ACDD", "ACTT")


def _codes_from_sheet() -> set:
    """v18.202：CI 若提供 SA 憑證 + sheet id（env）→ 從保單分頁讀真實持倉代碼。
    無憑證 → 回空集合（不 import gspread、零副作用）。"""
    sa = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON") or os.environ.get("GSPREAD_SA_JSON")
    sid = os.environ.get("POLICY_SHEET_ID") or os.environ.get("SHEET_ID")
    if not (sa and sid):
        return set()
    from repositories.policy_repository import (  # lazy：無憑證時不載
        _extract_code_from_url,
        get_gspread_client,
        load_all_policy_worksheets,
    )
    client = get_gspread_client(json.loads(sa))
    df = load_all_policy_worksheets(client, sid)
    out = set()
    for _u in (df["fund_url"] if "fund_url" in df.columns else []):
        _c = _extract_code_from_url(str(_u))
        if _c:
            out.add(_c.upper())
    print(f"[codes] ✅ Sheet 同步取得 {len(out)} 檔持倉代碼")
    return out


def _discover_fund_codes() -> list:
    """v18.202：彙整要抓的基金代碼 — 硬編碼 baseline ∪ 既有 cache 檔（self-heal）
    ∪ Sheet（CI 有 SA 憑證時）。解「新增基金忘了補 FUND_CODES → 無 cache → T5 算不出」。"""
    codes = {c.upper() for c in FUND_CODES if c}
    # (1) self-heal：已有 cache 檔的 code 一律持續刷新（即使被移出 FUND_CODES）
    try:
        for p in CACHE_DIR.glob("*.json"):
            if not p.stem.startswith("_"):
                codes.add(p.stem.upper())
    except Exception:
        pass
    # (2) Sheet 同步（僅當 CI 提供 SA 憑證；失敗不擋）
    try:
        codes |= _codes_from_sheet()
    except Exception as _e:
        print(f"[codes] Sheet 同步略過：{_e}")
    return sorted(c for c in codes if c)

def is_domestic_code(code: str) -> bool:
    return any(code.upper().startswith(p) for p in DOMESTIC_PREFIXES)

CACHE_DIR = Path(__file__).parent.parent / "cache" / "nav"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# ── v18.221：NAS proxy 中繼（解 GitHub Actions 美國 IP 被台灣站點擋）──────
#   與 app 同一把 secret 名稱（PROXY_URL = http://user:pwd@host:3128）。
#   CI 由 GitHub secret 注入同名環境變數；未設 → 直連（維持原行為）。
#   走 proxy 時 verify=False（Squid CONNECT 相容，比照 infra/proxy.py）。
_PROXY_URL = os.environ.get("PROXY_URL", "").strip()
if _PROXY_URL:
    SESSION.proxies.update({"http": _PROXY_URL, "https": _PROXY_URL})
    SESSION.verify = False
    try:
        import urllib3
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    except Exception:
        pass
    print(f"[proxy] ✅ 啟用 NAS proxy 中繼（{_PROXY_URL.rsplit('@', 1)[-1]}）")
else:
    print("[proxy] ⚠️ 未設定 PROXY_URL — 直連（GitHub IP 可能被台灣站點擋，覆蓋率低）")


# ══════════════════════════════════════════════════════════════════════
# 資料來源 1：TDCC OpenAPI 3-4（政府開放 API，最穩）
# ══════════════════════════════════════════════════════════════════════
def fetch_tdcc_all() -> dict:
    """從 TDCC OpenAPI 3-4 取得所有境外基金最新淨值。回傳 {代碼: item_dict}"""
    url = "https://openapi.tdcc.com.tw/v1/opendata/3-4"
    try:
        r = SESSION.get(url, timeout=45)
        r.raise_for_status()
        items = r.json()
        result = {}
        for item in items:
            code = (item.get("基金代號") or item.get("境外基金代碼") or "").strip().upper()
            if code:
                result[code] = item
        print(f"[TDCC 3-4] 取得 {len(result)} 筆最新淨值")
        return result
    except Exception as e:
        print(f"[TDCC 3-4] 失敗: {e}")
        return {}


def fetch_tdcc_basic() -> dict:
    """從 TDCC OpenAPI 3-2 取得境外基金基本資料（含中文名稱）。"""
    url = "https://openapi.tdcc.com.tw/v1/opendata/3-2"
    try:
        r = SESSION.get(url, timeout=45)
        r.raise_for_status()
        items = r.json()
        result = {}
        for item in items:
            code = (item.get("基金代號") or item.get("境外基金代碼") or "").strip().upper()
            if code:
                result[code] = item
        print(f"[TDCC 3-2] 取得 {len(result)} 筆基本資料")
        return result
    except Exception as e:
        print(f"[TDCC 3-2] 失敗: {e}")
        return {}


# ══════════════════════════════════════════════════════════════════════
# 資料來源 2：MoneyDJ yp004002（400 日歷史淨值）
# ══════════════════════════════════════════════════════════════════════
def fetch_moneydj_history(code: str, domain: str = "www.moneydj.com") -> list:
    """從 MoneyDJ yp004002 抓 400 日歷史淨值。回傳 [{"date": "YYYY-MM-DD", "nav": float}]"""
    end = datetime.date.today()
    start = end - datetime.timedelta(days=420)
    url = (
        f"https://{domain}/funddj/yf/yp004002.djhtm"
        f"?A={code}&B={start.strftime('%Y/%m/%d')}&C={end.strftime('%Y/%m/%d')}"
    )
    try:
        r = SESSION.get(
            url, timeout=30,
            headers={**HEADERS, "Referer": f"https://{domain}/"}
        )
        r.raise_for_status()
        html = r.text
        # 解析表格：日期 YYYY/MM/DD 與淨值
        rows = []
        matches = re.findall(
            r"(\d{4}/\d{2}/\d{2})[^<]*</td>[^<]*<td[^>]*>([0-9]+\.[0-9]+)",
            html
        )
        if not matches:
            # fallback: 更寬鬆的 regex
            matches = re.findall(r"(\d{4}/\d{2}/\d{2}).*?(\d+\.\d{2,4})", html[:50000])
        seen = set()
        for date_str, nav_str in matches:
            d = date_str.replace("/", "-")
            if d not in seen:
                seen.add(d)
                try:
                    rows.append({"date": d, "nav": float(nav_str)})
                except ValueError:
                    pass
        rows.sort(key=lambda x: x["date"], reverse=True)
        print(f"[MoneyDJ] {code}@{domain}: {len(rows)} 筆")
        return rows
    except Exception as e:
        print(f"[MoneyDJ] {code}@{domain} 失敗: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════
# 資料來源 3：MoneyDJ wb01（近 30 日 fallback）
# ══════════════════════════════════════════════════════════════════════
def fetch_moneydj_30day(code: str, domain: str = "www.moneydj.com") -> list:
    url = f"https://{domain}/w/wb/wb01.djhtm?a={code}"
    try:
        r = SESSION.get(url, timeout=25, headers={**HEADERS, "Referer": f"https://{domain}/"})
        r.raise_for_status()
        html = r.text
        rows = []
        seen = set()
        matches = re.findall(
            r"(\d{4}/\d{2}/\d{2})[^<]*</td>[^<]*<td[^>]*>([0-9]+\.[0-9]+)", html
        )
        for date_str, nav_str in matches:
            d = date_str.replace("/", "-")
            if d not in seen:
                seen.add(d)
                try:
                    rows.append({"date": d, "nav": float(nav_str)})
                except ValueError:
                    pass
        rows.sort(key=lambda x: x["date"], reverse=True)
        print(f"[MoneyDJ-30] {code}@{domain}: {len(rows)} 筆")
        return rows
    except Exception as e:
        print(f"[MoneyDJ-30] {code}@{domain} 失敗: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════
# 資料來源 4：AllianzGI 安聯官網（境內 ACTI/ACCP/ACDD 主力,直接用內部碼,無需 ISIN）
# ══════════════════════════════════════════════════════════════════════
# v19.351:境內主力來源。鏡像 app 的 repositories/fund/sources._src_allianzgi_nav 解析
# 邏輯 —— CI 精簡環境不能 import 該檔(會拉進 streamlit),故在此做精簡平行實作。
_ALLIANZ_NAV_API = "https://tw.allianzgi.com/api/sitecore/fund/GetFundNav"


def fetch_allianzgi_history(code: str) -> list:
    """安聯投信官網歷史 NAV(境內 ACTI/ACCP/ACDD 主力)。**直接用內部碼,無需 ISIN。**

    路徑:安聯 Sitecore JSON API(2000d)→ MoneyDJ yp004002 完整歷史頁(境內 yp010000)。
    §1:抓不到回 [](不偽造);§5:各步印診斷。
    ⚠️ 沙盒測不了(安聯站擋非台灣 IP),需經 NAS 代理的真實 run 確認。
    """
    import datetime
    today = datetime.date.today()
    start = today - datetime.timedelta(days=2000)
    rows: dict = {}

    # 1) 安聯 Sitecore JSON API(參數名不一定一致,試多種 body)
    for _body in ({"FundCode": code, "Days": 2000},
                  {"fundCode": code, "days": 2000},
                  {"FundCode": code, "Period": "MAX"}):
        try:
            r = SESSION.post(_ALLIANZ_NAV_API, json=_body,
                             headers={"Referer": "https://tw.allianzgi.com/"}, timeout=15)
            if not r or r.status_code != 200:
                continue
            data = r.json()
            nav_list = (data.get("Data") or data.get("data") or data.get("NavList")
                        or data.get("navList") or data.get("Items") or data.get("items")
                        or (data if isinstance(data, list) else []))
            got: dict = {}
            for it in (nav_list if isinstance(nav_list, list) else []):
                if not isinstance(it, dict):
                    continue
                ds = str(it.get("Date") or it.get("date") or it.get("NavDate")
                         or it.get("navDate") or "")[:10]
                _nv = (it.get("Nav") or it.get("nav") or it.get("NAV") or it.get("Price"))
                try:
                    nv = float(str(_nv).replace(",", "")) if _nv not in (None, "") else 0.0
                except (TypeError, ValueError):
                    nv = 0.0
                if ds and nv > 0:
                    got[ds.replace("/", "-")] = nv
            # ≥90 筆才短路(30 筆代表 API 忽略 Days 只回近期 → 續走 yp004002 拿完整歷史)
            if len(got) >= 90:
                out = sorted(({"date": d, "nav": v} for d, v in got.items()),
                             key=lambda x: x["date"], reverse=True)
                print(f"[AllianzGI] {code}: {len(out)} 筆 (JSON API {list(_body.keys())[0]})")
                return out
            if got:
                rows.update(got)
                print(f"[AllianzGI] {code} JSON API 只得 {len(got)} 筆,續試 yp004002")
                break
        except Exception as e:
            print(f"[AllianzGI] {code} JSON API fail({list(_body.keys())}): {str(e)[:80]}")

    # 2) MoneyDJ yp004002 完整歷史頁(境內 yp010000)
    try:
        from bs4 import BeautifulSoup
    except Exception:
        BeautifulSoup = None
    if BeautifulSoup is not None:
        try:
            params = {"A": code, "B": start.strftime("%Y%m%d"),
                      "C": today.strftime("%Y%m%d")}
            hdr = {"Referer": f"https://tcbbankfund.moneydj.com/funddj/ya/yp010000.djhtm?a={code}"}
            r = SESSION.get("https://tcbbankfund.moneydj.com/funddj/yf/yp004002.djhtm",
                            params=params, headers=hdr, timeout=25)
            if r is not None and r.status_code == 200:
                r.encoding = "big5"
                soup = BeautifulSoup(r.text, "lxml")
                for tbl in soup.find_all("table"):
                    for tr in tbl.find_all("tr"):
                        cells = tr.find_all("td")
                        if len(cells) >= 2:
                            dt_t = cells[0].get_text(strip=True)
                            nv_t = cells[1].get_text(strip=True).replace(",", "")
                            if re.match(r"\d{4}/\d{2}/\d{2}", dt_t):
                                try:
                                    v = float(nv_t)
                                    if v > 0:
                                        rows[dt_t.replace("/", "-")] = v
                                except ValueError:
                                    pass
        except Exception as e:
            print(f"[AllianzGI] {code} yp004002 fail: {str(e)[:80]}")

    out = sorted(({"date": d, "nav": v} for d, v in rows.items()),
                 key=lambda x: x["date"], reverse=True)
    if out:
        print(f"[AllianzGI] {code}: {len(out)} 筆 (含 MoneyDJ yp004002)")
    else:
        print(f"[AllianzGI] {code}: 0 筆 ⚠️ 安聯 API + yp004002 皆無資料")
    return out


def fetch_sitca_history(code: str) -> list:
    """⛔ 已停用(v19.351):SITCA IN2213.aspx 確認為「投信公司 + 年月 + 類別」下拉月報表頁,
    **無單檔基金代碼查詢欄位**——v19.350 探針 run #70 證實表單只有 ddlQ_YM / ddlQ_Comid /
    ddlQ_CLASS + BtnQuery(填 code/begin/end 皆 False;POST 觸發 ASP.NET EventValidation
    server error)。故無法用它取單檔 NAV 時序。境內改走 fetch_allianzgi_history。
    保留此函式僅為記錄結論 + 明確 skip(§1 不偽造、不再無謂打壞端點)。
    """
    print(f"[SITCA] {code}: 略過(IN2213 為公司/月份下拉月報表頁,不支援單檔查詢;見 v19.350 探針)")
    return []


# ══════════════════════════════════════════════════════════════════════
# 資料來源 4b：CnYES 鉅亨網（境外基金主要來源,直接用內部碼,無需 ISIN）— v19.352
# ══════════════════════════════════════════════════════════════════════
# 鏡像 app 的 repositories/fund/nav_metrics._fetch_nav_cnyes 之 API 路徑 + 解析
# (CI 精簡環境不能 import 該檔——會拉 streamlit——故平行精簡實作)。
# 安聯境外基金(原廠 AllianzGI API 也可抓;見 MORNINGSTAR_SECID_MAP 註解)。
_ALLIANZ_OFFSHORE_CODES = {"TLZF9", "ANZ89"}  # Allianz Income and Growth AMg7/AM USD


def _cnyes_walk_nav_items(obj, depth: int = 0) -> list:
    """遞迴在 nested JSON 找 NAV items list(含 date + nav 的 dict 陣列)。鏡像 app _walk_for_nav_items。"""
    if depth > 10:
        return []
    if isinstance(obj, list) and obj and isinstance(obj[0], dict):
        keys = set(obj[0].keys())
        date_keys = {"date", "nav_date", "publishDate", "trade_date", "Date",
                     "d", "time", "ts", "timestamp"}
        val_keys = {"nav", "netAssetValue", "value", "price", "close", "Nav", "Price", "v"}
        if (keys & date_keys) and (keys & val_keys):
            return obj
    if isinstance(obj, dict):
        for v in obj.values():
            r = _cnyes_walk_nav_items(v, depth + 1)
            if r:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _cnyes_walk_nav_items(v, depth + 1)
            if r:
                return r
    return []


def _cnyes_parse_items(items: list) -> list:
    """JSON items → [{date,nav}](寬容欄位名 + Unix ms/s timestamp)。鏡像 app _parse_nav_json_items。"""
    out, seen = [], set()
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        d = (it.get("date") or it.get("nav_date") or it.get("publishDate")
             or it.get("trade_date") or it.get("d") or it.get("Date")
             or it.get("time") or it.get("ts") or it.get("timestamp"))
        v = (it.get("nav") or it.get("netAssetValue") or it.get("value")
             or it.get("price") or it.get("close") or it.get("v")
             or it.get("Nav") or it.get("Price"))
        if d is None or v is None:
            continue
        try:
            if isinstance(d, (int, float)):
                _n = float(d)
                if _n > 1e12:
                    ds = datetime.datetime.utcfromtimestamp(_n / 1000).strftime("%Y-%m-%d")
                elif _n > 1e9:
                    ds = datetime.datetime.utcfromtimestamp(_n).strftime("%Y-%m-%d")
                else:
                    ds = str(d)[:10]
            else:
                ds = str(d)[:10].replace("/", "-")
            vf = float(v)
            if vf > 0 and ds and ds not in seen:
                seen.add(ds)
                out.append({"date": ds, "nav": vf})
        except (ValueError, TypeError):
            continue
    out.sort(key=lambda x: x["date"], reverse=True)
    return out


def fetch_cnyes_history(code: str) -> list:
    """CnYES 鉅亨網境外基金歷史 NAV(app 標定的境外主要來源,**直接用內部碼**)。
    §1:抓不到回 [](不偽造)。⚠️ 沙盒測不了(CnYES 擋非台灣 IP),需 NAS 代理真實 run 確認。
    """
    _hdr = {"Referer": f"https://fund.cnyes.com/detail/{code}/Nav"}
    for url in (f"https://api.cnyes.com/media/api/v1/fund/{code}/nav",
                f"https://api.cnyes.com/media/api/v1/fund/{code}/nav-history",
                f"https://api.cnyes.com/media/api/v1/fund/nav/history?code={code}",
                f"https://api.cnyes.com/fund/v1/funds/{code}/nav"):
        try:
            r = SESSION.get(url, headers=_hdr, timeout=20)
            if r is None or r.status_code != 200:
                continue
            out = _cnyes_parse_items(_cnyes_walk_nav_items(r.json()))
            if len(out) >= 30:
                print(f"[CnYES] {code}: {len(out)} 筆 ({url.rsplit('/', 1)[-1][:24]})")
                return out
        except Exception as e:
            print(f"[CnYES] {code} {url.rsplit('/', 1)[-1][:20]} err: {str(e)[:60]}")
    print(f"[CnYES] {code}: 0 筆 ⚠️ CnYES API 皆無資料")
    return []


# ══════════════════════════════════════════════════════════════════════
# 資料來源 5：Yahoo Finance（境外基金，需 Morningstar secId 映射）
# ══════════════════════════════════════════════════════════════════════
# 已知 Morningstar secId 映射
MORNINGSTAR_SECID_MAP = {
    "TLZF9": "0P0001J5YG",  # Allianz Income and Growth AMg7 USD
    "ANZ89": "0P0000X7WR",  # Allianz Income and Growth AM USD
    "JFZN3": "0P0001N4II",  # JPMorgan Global Income A icdiv USD hedged
}

def fetch_yahoo_finance_history(code: str) -> list:
    """從 Yahoo Finance 取歷史淨值（使用 Morningstar secId.F 格式）。
    Yahoo Finance 為美國服務，GitHub Actions 可存取。
    """
    sec_id = MORNINGSTAR_SECID_MAP.get(code, "")
    if not sec_id:
        return []
    yf_symbol = f"{sec_id}.F"
    # v19.230 P1-2 第二輪:URL template SSOT 走 production fetcher(repositories/fund/sources.py)
    from repositories.fund.sources import YF_MORNINGSTAR_CHART_URL
    url = YF_MORNINGSTAR_CHART_URL.format(symbol=yf_symbol)
    hdrs = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json",
    }
    try:
        r = SESSION.get(url, headers=hdrs, timeout=20)
        r.raise_for_status()
        data = r.json()
        result = data.get("chart", {}).get("result", [])
        if not result:
            print(f"[Yahoo] {code} ({yf_symbol}): 無結果")
            return []
        r0 = result[0]
        timestamps = r0.get("timestamp", [])
        closes = (r0.get("indicators", {}).get("quote", [{}])[0].get("close", []))
        rows = []
        seen = set()
        for ts, cl in zip(timestamps, closes):
            if ts and cl:
                try:
                    import datetime
                    d = datetime.date.fromtimestamp(ts).isoformat()
                    if d not in seen:
                        seen.add(d)
                        rows.append({"date": d, "nav": float(cl)})
                except Exception:
                    pass
        rows.sort(key=lambda x: x["date"], reverse=True)
        print(f"[Yahoo] {code} ({yf_symbol}): {len(rows)} 筆")
        return rows
    except Exception as e:
        print(f"[Yahoo] {code} ({yf_symbol}) 失敗: {e}")
        return []


# ══════════════════════════════════════════════════════════════════════
# 銀行平台代碼對應（可提供更高存活率）
# ══════════════════════════════════════════════════════════════════════
BANK_PLATFORM_CODES = {
    "TLZF9":  [("fund.hncb.com.tw", "TLZF9-1180"), ("fundrwd.entiebank.com.tw", "TLZF9-24A7")],
    "ANZ89":  [("fund.megabank.com.tw", "ANZ89-1G11")],
    "ACTI94": [("fund.megabank.com.tw", "ACTI94-8A22")],
}

def fetch_bank_platform_history(base_code: str) -> list:
    """試用銀行平台代碼從 MoneyDJ yp004002 取歷史淨值。"""
    platforms = BANK_PLATFORM_CODES.get(base_code, [])
    for domain, full_code in platforms:
        rows = fetch_moneydj_history(full_code, domain=domain)
        if len(rows) >= 10:
            return rows
        rows = fetch_moneydj_30day(full_code, domain=domain)
        if len(rows) >= 5:
            return rows
    return []


# ══════════════════════════════════════════════════════════════════════
# 主流程
# ══════════════════════════════════════════════════════════════════════
def load_cache(code: str) -> dict:
    cache_file = CACHE_DIR / f"{code}.json"
    if cache_file.exists():
        try:
            return json.loads(cache_file.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_cache(code: str, history: list, source: str, fund_name: str = "") -> None:
    cache_file = CACHE_DIR / f"{code}.json"
    data = {
        "code": code,
        "fund_name": fund_name,
        "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": source,
        "count": len(history),
        "history": history,
    }
    # v19.311:結尾補 "\n" — 否則 pre-commit end-of-file-fixer 在後續 PR 的
    # `--all-files` 掃描會判 cache/nav/*.json 缺檔尾換行而紅(每日 cron 寫檔 [skip ci]
    # 自己不跑 hook,卻會擋下一個 PR 的 CI)。對齊 update_macro_history.py:367。
    cache_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[cache] ✅ {code}: 已儲存 {len(history)} 筆 → cache/nav/{code}.json")


def merge_history(existing: list, new_rows: list) -> list:
    """合併新舊歷史，去重排序，最多保留 750 筆。"""
    merged = {r["date"]: r["nav"] for r in existing}
    for r in new_rows:
        merged[r["date"]] = r["nav"]
    result = [{"date": d, "nav": v} for d, v in sorted(merged.items(), reverse=True)]
    return result[:750]


def _emit_coverage_alert(summary: list) -> dict:
    """v19.321 §1 Fail-Loud / §5 可觀測:抓取覆蓋過低時發 GitHub Actions warning
    annotation + step summary,終結「每天綠勾但其實 0 新抓取」的靜默失敗
    (症狀:所有 code 只重存舊快取 source=cache_only,新持倉永遠拿不到種子檔)。

    覆蓋 = 本次真的抓到「新資料」(fresh=True)的比例。過半沒抓到 → 極可能是
    GitHub Actions 美國 IP 被台灣站點(TDCC/SITCA/MoneyDJ)封鎖、且 PROXY_URL
    secret 未生效 → fetch 全敗。不 hard-fail(仍保留既有快取),只讓失敗「被看見」。
    回傳診斷 dict 供測試 / log。
    """
    total = len(summary)
    fresh = [r["code"] for r in summary if r.get("fresh")]
    no_data = [r["code"] for r in summary if int(r.get("count") or 0) == 0]
    frac = (len(fresh) / total) if total else 1.0
    low = total > 0 and frac < 0.5
    _proxy_on = bool(_PROXY_URL)
    if low:
        # v19.348 §1:訊息依「代理實際狀態」誠實分流,不再無腦甩鍋 PROXY_URL。
        # (舊版不論 proxy 有無開都印「PROXY_URL 未生效」→ 誤導,proxy 明明啟用了。)
        if _proxy_on:
            _cause = (
                f"NAS proxy **已啟用**（{_PROXY_URL.rsplit('@', 1)[-1]}）但來源仍幾乎全失敗 → "
                f"排除『沒設代理』;請查 (1) NAS Squid 是否可達/逾時 "
                f"(2) 來源端點是否改版(SITCA IN2213 GET→需 POST?、MoneyDJ 版型、TDCC API)。"
                f"看各來源 fetcher 的診斷 log 定位。"
            )
        else:
            _cause = (
                f"**未啟用 proxy**(PROXY_URL 未設)→ GitHub Actions 美國 IP 極可能被台灣站點"
                f"(TDCC/SITCA/MoneyDJ)封鎖。請至 repo Settings → Secrets and variables → "
                f"Actions 設 PROXY_URL(NAS Squid,與 app 同一把)。"
            )
        msg = (
            f"NAV 快取覆蓋過低:{total} 檔僅 {len(fresh)} 檔本次抓到新資料"
            f"({len(no_data)} 檔完全無快取)。{_cause}"
        )
        # GitHub Actions annotation:顯示在 run 頁 + PR checks(單行,去換行)
        print(f"::warning title=NAV 快取覆蓋過低::{msg.replace(chr(10), ' ')}")
        _gs = os.environ.get("GITHUB_STEP_SUMMARY")
        if _gs:
            try:
                with open(_gs, "a", encoding="utf-8") as _f:
                    _f.write(
                        f"### ⚠️ NAV 快取覆蓋過低（{len(fresh)}/{total} 檔有新資料）\n\n"
                        f"{msg}\n\n"
                        f"- 本次有新資料:{', '.join(fresh) or '（無）'}\n"
                        f"- 完全無快取:{', '.join(no_data) or '（無）'}\n"
                    )
            except Exception as _e:
                print(f"[step-summary] 寫入失敗:{_e}")
    else:
        print(f"[coverage] ✅ {len(fresh)}/{total} 檔本次有新資料")
    return {"total": total, "fresh": fresh, "no_data": no_data,
            "frac_fresh": round(frac, 3), "low": low, "proxy_on": _proxy_on}


def main():
    print(f"\n{'='*60}")
    print(f"NAV Cache Fetcher — {datetime.datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    # 一次性取得 TDCC 全量資料（含最新淨值 + 基本資料）
    tdcc_nav  = fetch_tdcc_all()
    tdcc_meta = fetch_tdcc_basic()
    time.sleep(1)

    # v18.178 (#2)：累計每檔結果供結尾診斷表（定位卡 fallback / 歷史太短的 fund）
    _summary: list[dict] = []

    _codes = _discover_fund_codes()   # v18.202：baseline ∪ 既有 cache ∪ Sheet
    print(f"📋 目標基金代碼共 {len(_codes)} 檔：{', '.join(_codes)}\n")
    for code in _codes:
        print(f"\n── {code} ──────────────────────────────")
        existing_cache = load_cache(code)
        existing_history = existing_cache.get("history", [])
        fund_name = existing_cache.get("fund_name", "")

        # 更新基金名稱（從 TDCC 取）
        if not fund_name and code in tdcc_meta:
            meta = tdcc_meta[code]
            fund_name = (
                meta.get("基金中文名稱") or meta.get("基金名稱") or
                meta.get("基金簡稱") or ""
            )

        new_rows = []
        source_used = "cache_only"
        _is_domestic = is_domestic_code(code)

        if _is_domestic:
            # ── 境內基金（ACTI/ACCP/ACDD）：走 AllianzGI 安聯官網（app 主力，直接用內部碼）──
            # v19.351:SITCA IN2213 確認是「公司/月份下拉月報表頁」、抓不到單檔(見 fetch_sitca_history),
            # 改走安聯官網 JSON API + MoneyDJ yp004002(境內 yp010000)。
            print(f"  [境內基金] 走 AllianzGI（安聯官網）路徑")
            if len(existing_history) + len(new_rows) < 30:
                hist = fetch_allianzgi_history(code)
                if hist:
                    new_rows = merge_history(new_rows, hist)
                    source_used = "allianzgi"
                else:
                    fetch_sitca_history(code)  # 記錄 SITCA 已停用結論(§5),不影響結果
                time.sleep(0.5)
        else:
            # ── 境外基金：走 TDCC + MoneyDJ + Yahoo Finance ──
            # 1. TDCC 最新淨值（只有一筆，但每天都更新）
            if code in tdcc_nav:
                item = tdcc_nav[code]
                date_raw = item.get("淨值日期") or item.get("最新淨值日期") or ""
                nav_raw  = item.get("單位淨值") or item.get("最新淨值") or ""
                if not fund_name:
                    fund_name = item.get("基金中文名稱") or item.get("基金名稱") or ""
                try:
                    d = date_raw.strip().replace("/", "-")
                    n = float(str(nav_raw).replace(",", ""))
                    if d and n > 0:
                        new_rows.append({"date": d, "nav": n})
                        source_used = "tdcc"
                        print(f"  TDCC: {d} → {n}")
                except (ValueError, AttributeError):
                    pass

            # 1b. CnYES 境外歷史（app 標定的境外主要來源，直接用內部碼）— v19.352
            if len(existing_history) + len(new_rows) < 30:
                hist = fetch_cnyes_history(code)
                if hist:
                    new_rows = merge_history(new_rows, hist)
                    source_used = "cnyes"
                time.sleep(0.5)

            # 1c. 安聯境外（TLZF9/ANZ89）：走原廠 AllianzGI GetFundNav（最權威）— v19.352
            if len(existing_history) + len(new_rows) < 30 and code in _ALLIANZ_OFFSHORE_CODES:
                hist = fetch_allianzgi_history(code)
                if hist:
                    new_rows = merge_history(new_rows, hist)
                    source_used = "allianzgi"
                time.sleep(0.5)

            # 2. Yahoo Finance（Morningstar secId.F，GitHub Actions 可存取）
            if len(existing_history) + len(new_rows) < 30 and code in MORNINGSTAR_SECID_MAP:
                hist = fetch_yahoo_finance_history(code)
                if hist:
                    new_rows = merge_history(new_rows, hist)
                    source_used = "yahoo_finance"
                time.sleep(0.5)

            # 3. MoneyDJ 歷史（直接用基金代碼）
            if len(existing_history) + len(new_rows) < 30:
                hist = fetch_moneydj_history(code)
                if hist:
                    new_rows = merge_history(new_rows, hist)
                    source_used = "moneydj"
                time.sleep(0.8)

            # 4. 銀行平台代碼 fallback
            if len(existing_history) + len(new_rows) < 10 and code in BANK_PLATFORM_CODES:
                hist = fetch_bank_platform_history(code)
                if hist:
                    new_rows = merge_history(new_rows, hist)
                    source_used = "bank_platform"
                time.sleep(0.8)

            # 5. MoneyDJ 30 日 fallback
            if len(existing_history) + len(new_rows) < 10:
                hist = fetch_moneydj_30day(code)
                if hist:
                    new_rows = merge_history(new_rows, hist)
                    source_used = "moneydj_30d"
                time.sleep(0.5)

        # 合併並儲存
        final_history = merge_history(existing_history, new_rows)
        if final_history:
            save_cache(code, final_history, source_used, fund_name)
            _final_count, _final_src = len(final_history), source_used
        else:
            print(f"  ⚠️  {code}: 本次無任何資料（保留既有快取 {len(existing_history)} 筆）")
            if existing_history:
                save_cache(code, existing_history, existing_cache.get("source", "cache_only"), fund_name)
            _final_count = len(existing_history)
            _final_src = existing_cache.get("source", "cache_only")

        _summary.append({"code": code, "count": _final_count, "source": _final_src,
                         "fresh": bool(new_rows)})
        time.sleep(0.5)

    # ── v18.178 (#2)：診斷彙整表 — 一眼看哪些 fund 歷史太短 / 卡 fallback ──
    print(f"\n{'='*60}")
    print("📊 NAV 快取診斷彙整（count = 最終快取筆數）")
    print(f"{'='*60}")
    print(f"{'代碼':<10}{'筆數':>6}  {'狀態':<14}{'來源'}")
    print(f"{'-'*60}")
    for r in sorted(_summary, key=lambda x: x["count"]):
        n = r["count"]
        if   n >= 252: status = "✅ ≥1年(可回測)"
        elif n >= 60:  status = "🟡 ≥季線"
        elif n >= 30:  status = "🟠 僅短期"
        else:          status = "🔴 嚴重不足"
        print(f"{r['code']:<10}{n:>6}  {status:<14}{r['source']}")
    _short = [r["code"] for r in _summary if r["count"] < 60]
    if _short:
        print(f"\n⚠️  以下 {len(_short)} 檔 <60 筆（季線/回測/相關係數會受限，需查來源）："
              f"{', '.join(_short)}")
    # v19.321：覆蓋過低 → 發 GitHub Actions warning（§1 Fail-Loud，別再靜默綠勾）
    _emit_coverage_alert(_summary)
    print(f"\n{'='*60}")
    print("完成！")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
