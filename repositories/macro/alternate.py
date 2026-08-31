"""repositories/macro/alternate.py — Alternate data 抓取(B1 拆自 macro_repository v19.205).

從原 1078 LOC god module 拆出:
- DefiLlama 穩定幣總市值
- AAII Sentiment(多源 fallback chain)
- ISM PMI(FRED + MacroMicro + ISM World + Stooq + Philly Fed + Conf Board CCI)
(原 fetch_macro_compass 已於 2026-08-05 隨 🧭 總經指南針整條鏈退役,見下方註解。)

依賴 fred.fetch_fred。
"""
from __future__ import annotations

import datetime
import math
import re

import pandas as pd

from infra.proxy import fetch_url
from infra.cache import mark_fetch_failed
from fund_fetcher import _ttl_cache, register_cache
from shared.fred_series import (
    FRED_BSCICP02,
    FRED_PHILLY_FED,
    PHILLY_FED_PMI_BASE,
    PHILLY_FED_TO_PMI_DIVISOR,
)
from shared.ttls import TTL_30MIN

from .fred import fetch_fred


# ══════════════════════════════════════════════════════════════
# DefiLlama 穩定幣總市值（影子/數位流動性因子用）— 免 API key，走 NAS proxy
# ══════════════════════════════════════════════════════════════
DEFILLAMA_STABLECOIN_URL = "https://stablecoins.llama.fi/stablecoincharts/all"


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)   # 穩定幣市值日頻
def fetch_defillama_stablecoin_mcap() -> pd.Series:
    """抓 DefiLlama 全市場穩定幣「總流通市值」歷史（USD，日頻）。

    Returns
    -------
    pd.Series  index=DatetimeIndex, value=總流通市值(USD)。失敗回空 Series。

    快取語意(2026-08-31,v3 §02「只快取成功結果」):
        **只有 `fetch_url` 回 None 那一支帶 `mark_fetch_failed` 標記 → 不入
        `@_ttl_cache`**,下次呼叫真的重試。HTTP 200 之後的各種空結果
        (JSON 壞掉 / 解不出 rows / schema 驗證不過)**刻意不標記** ——
        來源活著且已回答,重抓拿到的是同一份東西。
    """
    r = fetch_url(DEFILLAMA_STABLECOIN_URL, timeout=20)
    if r is None:
        # 抓失敗 → 標記後不入快取(原本被鎖 TTL_30MIN)
        return mark_fetch_failed(
            pd.Series(dtype=float, name="stablecoin_mcap"),
            "fetch_url returned None: DefiLlama:stablecoin_mcap")
    try:
        data = r.json()
    except Exception as e:
        print(f"[defillama] 穩定幣 JSON 解析失敗: {e}")
        # 刻意不標記(同 yf.py / fred.py 該處):200 已到手,重抓不會變好。
        return pd.Series(dtype=float, name="stablecoin_mcap")
    rows: dict = {}
    for item in (data or []):
        try:
            ts = int(item["date"])
            tc = item.get("totalCirculatingUSD") or item.get("totalCirculating") or {}
            # totalCirculatingUSD 為 {peg類型: 金額} → 加總所有數值欄；或本身即數值
            if isinstance(tc, dict):
                val = float(sum(v for v in tc.values() if isinstance(v, (int, float))))
            else:
                val = float(tc)
            if val > 0:
                rows[pd.Timestamp(ts, unit="s").normalize()] = val
        except (KeyError, ValueError, TypeError):
            continue
    if not rows:
        return pd.Series(dtype=float, name="stablecoin_mcap")
    s = pd.Series(rows, name="stablecoin_mcap").sort_index()
    # F-PROV-1 v19.84 phase 3:provenance via Series.attrs(§2.2)
    s.attrs["source"] = "DefiLlama:stablecoincharts:total_circulating"
    s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    # F-SCHEMA-1 餘量輕量驗證(v19.369 8/8):壞形狀 → log + 回空(§1 不靜默流入)
    try:
        from repositories.external_market_repository import _validate_market_series
        _validate_market_series(s, "defillama:stablecoin_mcap")
    except AssertionError as _ve:
        print(f"[macro/alternate] stablecoin 驗證失敗:{_ve}")
        return pd.Series(dtype=float, name="stablecoin_mcap")
    return s


# ══════════════════════════════════════════════════════════════
# AAII 散戶情緒調查 — 純 I/O + parse（F-H1 v19.77：從 us_liquidity_engine 下沉）
#   來源：aaii.com/sentimentsurvey HTML scrape，週頻更新。
#   回 raw dict {bull, bear, spread, date} 或 {_err: ...}；
#   color/label 業務判讀由 L2 service (us_liquidity_engine) 處理。
#
# v19.192：硬化策略(回應 user「沒用 NAS proxy 中繼站」報修)
#   1. URL fallback chain 3 段:主頁 → sent_results → 子頁,
#      模仿 §2.1 MoneyDJ 子網域 fallback pattern。
#   2. UA 補完 Chrome/124 full string(原本 Mozilla 截斷,Cloudflare 易判 bot)。
#   3. Accept / Accept-Language 帶齊,模擬真實瀏覽器。
#   4. timeout 8 → 20s(原 8 太短,NAS Squid 中繼 + Cloudflare challenge 常 > 8s)。
#   5. trace 累加每段失敗原因,_err 帶完整鏈路,user 看得出哪段失敗。
#   `fetch_url` 本身已透過 `get_proxy_config()` 走 NAS Squid 中繼(infra/proxy.py:144),
#   本層不需另外注入 proxy — 改善的是「中繼後仍被擋」的成功率。
# ══════════════════════════════════════════════════════════════
AAII_SENTIMENT_URL = "https://www.aaii.com/sentimentsurvey"
AAII_FALLBACK_URLS = (
    "https://www.aaii.com/sentimentsurvey",
    "https://www.aaii.com/sentimentsurvey/sent_results",
    "https://www.aaii.com/SentimentSurvey",  # 大小寫變體,部分 CDN edge 視為不同 cache key
)
AAII_BROWSER_HEADERS = {
    # F-AAII v19.192:Cloudflare 反爬對截斷 Mozilla string 較敏感,補 Chrome/124 full UA。
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

# ══════════════════════════════════════════════════════════════
# AAII 三欄表格 parser(稽核修正 2026-08-05)
#
# 舊寫法對**原始 HTML**(`r.text`)跑 `[Bb]ullish[^0-9]{0,40}(\d{1,2}\.\d)\s*%`,
# 會吃到 markup 裡的非調查數字(CSS 進度條 width / 圖表 JSON / 投票 widget)。
# 現場實測:系統顯示 spread +50.00(bull 50.0 / bear 0.0),而官網當週實際是
# bull 31.0 / neutral 26.9 / bear 42.1 → spread −11.1,**誤差 61 個百分點且符號相反**。
#
# 三個結構缺陷 → 三件套修法:
#   1. 改用 `BeautifulSoup(...).get_text()` 剝除 markup(沿用同檔 PMI 分支既有寫法);
#   2. 對齊官網 `Week Ending | Bullish | Neutral | Bearish` 表格結構:以「週結日 +
#      緊接三個百分比」為錨,**欄序由表頭實際出現順序決定**(不寫死 bull/bear 位置);
#   3. 三條不變量防呆(常數 SSOT 在 shared/schemas.py):各欄 ∈ [0,100]、
#      三欄和 ≈ 100、|bull−bear| ≤ 60。任一條不過 → raise ValueError,
#      由 caller 轉 `_err`(§1:寧可沒有數字,不可回一個能通過 schema 的垃圾數字)。
#   4. `date` 填**真實週結日**(ISO),取代原本硬編碼的 "weekly"(§2.3 PIT:
#      無時點字串連「這筆是不是上週的」都判斷不了)。
# ══════════════════════════════════════════════════════════════
# 表頭三個欄名(key → 官網英文字);欄序由各字在表頭的實際位置排出,不假設固定順序。
_AAII_HEADER_WORDS = (("bull", "Bullish"), ("neutral", "Neutral"), ("bear", "Bearish"))
# 官方固定欄序。`_aaii_column_order` 解析結果若與此不符 → raise(§1),
# 因為下游三條不變量對 bull↔bear 互換完全不敏感(見該函式註解)。
_AAII_CANONICAL_ORDER = ["bull", "neutral", "bear"]
# 一列資料 = 週結日(M/D/YYYY)後**緊接**三個百分比(中間只允許空白)。
# 「緊接」是關鍵:官網同頁另有「1-Year Bullish High: 49.5% Week Ending 1/14/2026」
# 這種「先百分比後日期」的敘述,以及無日期的 Historical Averages 列,都不會誤命中。
_AAII_ROW_RE = re.compile(
    r"(?P<mo>\d{1,2})/(?P<dy>\d{1,2})/(?P<yr>20\d{2})\s+"
    r"(?P<c1>\d{1,3}(?:\.\d+)?)\s*%\s+"
    r"(?P<c2>\d{1,3}(?:\.\d+)?)\s*%\s+"
    r"(?P<c3>\d{1,3}(?:\.\d+)?)\s*%"
)
# 官網「Week Ending」表格固定顯示最近 4 週;掃描上限給 12 列緩衝即足夠。
_AAII_MAX_ROWS_SCAN: int = 12


def _aaii_column_order(text_before_row: str) -> list[str] | None:
    """由資料列**之前**最靠近的表頭字位置決定三欄順序。

    回 ['bull','neutral','bear'] 之類的 key 順序;任一字找不到 → None(視為結構不符)。
    用 rfind:頁面前段導覽/行銷文也會出現這些字,取「最靠近資料列的那次出現」= 表頭。
    """
    pos: dict[str, int] = {}
    for key, word in _AAII_HEADER_WORDS:
        i = text_before_row.rfind(word)
        if i < 0:
            return None
        pos[key] = i
    order = [k for k, _ in sorted(pos.items(), key=lambda kv: kv[1])]
    if len(set(order)) != 3:
        return None
    # ⚠️ 欄序必須等於官方固定順序,否則 fail loud(§1)。
    # 理由:本函式下游的三條不變量(各欄 ∈[0,100]、三欄和≈100、|bull−bear|≤60)
    # **全部對 bull↔bear 互換不敏感** —— 加法可交換、絕對值對稱、值域對稱。
    # 若頁面改版讓表頭相對位置變動,parser 會靜默回傳 bull/bear 顛倒的結果,
    # spread 由 −11.1 翻成 +11.1(散戶偏空 → 極度貪婪),而四道防呆全綠。
    # AAII 官網二十年未改欄序;真改了也該由人來看,不該由 rfind 啟發式猜。
    if order != _AAII_CANONICAL_ORDER:
        raise ValueError(
            f"AAII 表頭欄序異常:解析得 {order},官方固定為 {_AAII_CANONICAL_ORDER}"
            "(頁面可能改版 → 拒絕猜測,§1 Fail Loud)"
        )
    return order


def _parse_aaii_table(html: str) -> dict:
    """從 AAII 頁面 HTML 解析最新一週的 bull/neutral/bear + 週結日。

    Returns
    -------
    dict  {value(spread), unit, bull, neutral, bear, date('YYYY-MM-DD')}

    Raises
    ------
    ValueError  結構不符 / 防呆不過(§1 Fail Loud — 由 caller 轉為 _err trace)
    """
    from bs4 import BeautifulSoup

    from shared.schemas import (
        AAII_PCT_MAX,
        AAII_PCT_MIN,
        AAII_SPREAD_ABS_MAX_PCT,
        AAII_SUM_ABS_TOL_PCT,
        AAII_SUM_TOTAL_PCT,
    )

    txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    rows: list[tuple[datetime.date, dict[str, float]]] = []
    for m in _AAII_ROW_RE.finditer(txt):
        order = _aaii_column_order(txt[:m.start()])
        if order is None:
            continue
        try:
            week = datetime.date(int(m.group("yr")), int(m.group("mo")), int(m.group("dy")))
        except ValueError:
            continue  # 2026-13-45 之類的假日期 → 非資料列
        vals = dict(zip(order, (float(m.group("c1")), float(m.group("c2")),
                                float(m.group("c3")))))
        rows.append((week, vals))
        if len(rows) >= _AAII_MAX_ROWS_SCAN:
            break
    if not rows:
        # trace 保留 "regex" 字樣:既有 fallback chain 測試以此辨識「結構沒命中」
        raise ValueError("regex no match(找不到「週結日 + 三欄百分比」表格列)")

    week, vals = max(rows, key=lambda t: t[0])
    # PIT:週結日是**過去的週三**,不可能晚於今天(容 1 天時區差)。
    today = datetime.date.today()
    if week > today + datetime.timedelta(days=1):
        raise ValueError(f"防呆不過:週結日 {week} 晚於今日 {today}(解析錯位)")

    bull, neutral, bear = vals["bull"], vals["neutral"], vals["bear"]
    for k, v in (("bull", bull), ("neutral", neutral), ("bear", bear)):
        if not (AAII_PCT_MIN <= v <= AAII_PCT_MAX):
            raise ValueError(
                f"防呆不過:{k}={v} 越界 [{AAII_PCT_MIN:.0f},{AAII_PCT_MAX:.0f}]")
    total = bull + neutral + bear
    if not math.isclose(total, AAII_SUM_TOTAL_PCT, abs_tol=AAII_SUM_ABS_TOL_PCT):
        raise ValueError(
            f"防呆不過:bull+neutral+bear={total:.1f} 應 ≈ {AAII_SUM_TOTAL_PCT:.0f}"
            f"(±{AAII_SUM_ABS_TOL_PCT});抓到的很可能不是調查值 "
            f"(bull={bull} neutral={neutral} bear={bear} week={week})")
    spread = bull - bear
    if abs(spread) > AAII_SPREAD_ABS_MAX_PCT:
        raise ValueError(
            f"防呆不過:|bull−bear|={abs(spread):.1f} > {AAII_SPREAD_ABS_MAX_PCT:.0f} "
            f"個百分點,超出歷史極值範圍(week={week})")
    return {
        "value": round(spread, 1),
        "unit": "%",
        "bull": bull,
        "neutral": neutral,
        "bear": bear,
        "date": week.isoformat(),
    }


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)
def fetch_aaii_sentiment() -> dict:
    """抓 AAII Investor Sentiment Survey 散戶情緒週度數值（best-effort scrape）。

    v19.192:從單 URL 改成 3 段 fallback chain(模仿 MoneyDJ 子網域 pattern),
    補完整 Chrome UA + Accept headers,timeout 提到 20s 配合 NAS Squid 中繼。

    解析與防呆見 `_parse_aaii_table`(2026-08-05 稽核修正:改吃 get_text 純文字 +
    三欄表格結構 + 三條不變量 + 真實週結日,取代原本直接對 HTML 跑 regex 的寫法)。

    Returns
    -------
    dict
        成功:{value(spread), unit, bull, neutral, bear, date('YYYY-MM-DD'),
              source, fetched_at, url_used}
        失敗:{_err: 多段 trace, source, fetched_at}(fail-loud token,L2 caller 視為錯誤狀態)

    F-PROV-1 v19.84 phase 3:provenance(§2.2)— 全路徑(含 _err)皆帶 source + fetched_at。
    """
    # F-PROV-1 v19.84:provenance 全路徑共享(成功/失敗 caller 都能追溯)
    _prov = {
        "source": "AAII:sentimentsurvey",
        "fetched_at": pd.Timestamp.now('UTC').isoformat(),
    }
    trace: list[str] = []
    for url in AAII_FALLBACK_URLS:
        try:
            r = fetch_url(url, headers=AAII_BROWSER_HEADERS, timeout=20)
            if r is None:
                trace.append(f"{url.rsplit('/', 1)[-1] or 'aaii'}:fetch_url None")
                continue
            if r.status_code != 200:
                trace.append(f"{url.rsplit('/', 1)[-1] or 'aaii'}:HTTP {r.status_code}")
                continue
            try:
                parsed = _parse_aaii_table(r.text)
            except ValueError as pe:
                # §1:結構不符或防呆不過 → 記 trace 換下一段,**不**回退到任何猜測值
                trace.append(f"{url.rsplit('/', 1)[-1] or 'aaii'}:{pe}")
                continue
            return {**parsed, "url_used": url, **_prov}
        except Exception as e:
            trace.append(f"{url.rsplit('/', 1)[-1] or 'aaii'}:{type(e).__name__}")
    # 三段全失敗 → §1 Fail Loud,_err 帶完整 trace 供 user/audit 判讀
    return {"_err": f"AAII fallback chain 全失敗:{' → '.join(trace)}", **_prov}


# ══════════════════════════════════════════════════════════════
# ISM 製造業 PMI — 5 段備援共用函式（v1.1 兩端統一）
#
# 為什麼 5 段？
#   FRED NAPM / ISPMANPMI 自 2016-08 ISM 收回授權後停更，但保留以防重啟；
#   MacroMicro / ISM World 為主存活源但 HTML 結構易變動；
#   DBnomics 為 ISM JSON 鏡像（無需 key）；
#   OECD US Business Confidence 在 FRED 上仍持續更新，作為「概念替代指標」，
#   值約 98–102（非 PMI 的 30–70 區間），與 ISM PMI 相關性 ~0.7。
# ══════════════════════════════════════════════════════════════

def fetch_ism_pmi(fred_api_key: str = "", *, max_age_days: int = 90) -> dict:
    """抓取 ISM 製造業 PMI（5 段備援，月頻）。

    Returns
    -------
    dict
      命中：{'value': float, 'date': 'YYYY-MM-DD', 'label': str,
             'source': str, 'is_proxy': bool, 'series_id': str,
             'dates': [...], 'values': [...], 'proxy_note'?: str}
      失敗：{'_err_pmi': str, 'value': None}
    """
    import datetime as _dt
    import re as _re
    today = _dt.date.today()
    errs: list[str] = []

    # ── 方案 1+2: FRED NAPM / ISPMANPMI（max_age_days 時效檢查）──
    if fred_api_key:
        for sid, lbl in [('NAPM', 'FRED NAPM'), ('ISPMANPMI', 'FRED ISPMANPMI')]:
            try:
                # v18.119 issue 1 真正修法：n=144 + tail(120) 拉滿 10 年月頻
                # 原 n=36 + tail(24) 只 24 期 → Phase 4 min_overlap=24 + lag=3
                # → .shift(-3).dropna() = 21 < 24 → return out_empty
                df = fetch_fred(sid, fred_api_key, n=144)
                if df.empty or len(df) < 5:
                    continue
                df = df.tail(120)
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age > max_age_days:
                    print(f'[macro_core/PMI/FRED] ⚠️ {sid} 最新={last_date} '
                          f'已停更 {age} 天 > {max_age_days}，跳過')
                    continue
                v = round(float(df['value'].iloc[-1]), 1)
                print(f'[macro_core/PMI/FRED] ✅ {sid}={v} date={last_date} '
                      f'series={len(df)} 期')
                # F-PROV-1 phase 18 v19.156 — 加 fetched_at(source 已存在)
                return {
                    'value': v, 'date': str(last_date), 'label': lbl,
                    'source': f'FRED:{sid}', 'is_proxy': False, 'series_id': sid,
                    'fetched_at': pd.Timestamp.now('UTC').isoformat(),
                    'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                    'values': [round(float(x), 1) for x in df['value']],
                }
            except Exception as e:
                errs.append(f'FRED.{sid}:{type(e).__name__}')
                print(f'[macro_core/PMI/FRED/{sid}] ❌ {e}')

    # ── 方案 3: MacroMicro 財經 M 平方（中文 HTML）──
    try:
        from bs4 import BeautifulSoup
        for url in ('https://www.macromicro.me/charts/950/us-ism-mfg-pmi',
                    'https://www.macromicro.me/charts/2/economic-monitor-pmi'):
            r = fetch_url(url, timeout=12)
            if r is None:
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(?:ISM[^。]{0,40}?PMI|製造業\s*PMI)[^。]{0,200}?'
                r'(\d{2}\.\d)[^。]{0,80}?(20\d{2})[\s/年-]+(\d{1,2})',
                txt)
            if m:
                v = float(m.group(1)); yr = m.group(2); mo = int(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    date = f'{yr}-{mo:02d}-01'
                    print(f'[macro_core/PMI/MacroMicro] ✅ {v} date={date}')
                    # F-PROV-1 phase 18 v19.156 — 加 fetched_at
                    return {'value': v, 'date': date,
                            'label': 'MacroMicro ISM PMI',
                            'source': 'MacroMicro:us-ism-mfg-pmi', 'is_proxy': False,
                            'series_id': '950',
                            'fetched_at': pd.Timestamp.now('UTC').isoformat()}
    except Exception as e:
        errs.append(f'MacroMicro:{type(e).__name__}')
        print(f'[macro_core/PMI/MacroMicro] ❌ {e}')

    # ── 方案 4: ISM World 官方月報（英文 HTML，最一手）──
    try:
        from bs4 import BeautifulSoup
        url = ('https://www.ismworld.org/supply-management-news-and-reports/'
               'reports/ism-report-on-business/pmi/')
        r = fetch_url(url, timeout=12)
        if r is not None:
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(?:Manufacturing\s+PMI[^.]{0,40}?(?:at|registered)|'
                r'PMI[^.]{0,15}?registered)[^\d]{0,15}(\d{2}\.\d)\s*(?:%|percent)',
                txt, _re.IGNORECASE)
            if m:
                v = float(m.group(1))
                if 30 <= v <= 70:
                    m_dt = _re.search(
                        r'(January|February|March|April|May|June|July|August|'
                        r'September|October|November|December)\s+(20\d{2})', txt)
                    date = ''
                    if m_dt:
                        MO = {'January':1,'February':2,'March':3,'April':4,
                              'May':5,'June':6,'July':7,'August':8,
                              'September':9,'October':10,'November':11,'December':12}
                        date = f'{m_dt.group(2)}-{MO[m_dt.group(1)]:02d}-01'
                    print(f'[macro_core/PMI/ISM] ✅ {v} date={date or "?"}')
                    # F-PROV-1 phase 18 v19.156 — 加 fetched_at
                    return {'value': v, 'date': date,
                            'label': 'ISM World Official',
                            'source': 'ISM:ismworld.org', 'is_proxy': False,
                            'series_id': 'ismworld.org',
                            'fetched_at': pd.Timestamp.now('UTC').isoformat()}
    except Exception as e:
        errs.append(f'ISM:{type(e).__name__}')
        print(f'[macro_core/PMI/ISM] ❌ {e}')

    # ── 方案 5: DBnomics（純 JSON，ISM 鏡像，無需 key）──
    try:
        url = 'https://api.db.nomics.world/v22/series/ISM/pmi/pm'
        r = fetch_url(url, params={'observations': '1', 'limit': '24'}, timeout=15)
        if r is not None:
            d = r.json()
            docs = d.get('series', {}).get('docs', []) or []
            if docs:
                periods = docs[0].get('period', []) or []
                values  = docs[0].get('value',  []) or []
                last_idx = -1
                for i in range(len(values) - 1, -1, -1):
                    vi = values[i]
                    if vi is None: continue
                    try:
                        if isinstance(vi, float) and (vi != vi):  # NaN
                            continue
                    except Exception:
                        pass
                    last_idx = i; break
                if last_idx >= 0:
                    v = round(float(values[last_idx]), 1)
                    period_str = str(periods[last_idx])
                    last_date = _dt.datetime.strptime(period_str[:7], '%Y-%m').date()
                    age = (today - last_date).days
                    if age <= max_age_days and 30 <= v <= 70:
                        date = f'{period_str[:7]}-01'
                        print(f'[macro_core/PMI/DBnomics] ✅ {v} date={date}')
                        # F-PROV-1 phase 18 v19.156 — 加 fetched_at
                        return {'value': v, 'date': date,
                                'label': 'DBnomics ISM/pmi/pm',
                                'source': 'DBnomics:ISM/pmi/pm', 'is_proxy': False,
                                'series_id': 'ISM/pmi/pm',
                                'fetched_at': pd.Timestamp.now('UTC').isoformat()}
                    else:
                        print(f'[macro_core/PMI/DBnomics] ⚠️ '
                              f'最新={period_str} v={v} age={age}d 不通過防呆')
    except Exception as e:
        errs.append(f'DBnomics:{type(e).__name__}')
        print(f'[macro_core/PMI/DBnomics] ❌ {e}')

    # ── 方案 6: Phil Fed 製造業擴散指數（FRED GACDFSA066MSFRBPHI）──
    #   FRED 上仍持續更新；範圍 -50~+50；線性映到 PMI 等價刻度：
    #   PMI_eq = PHILLY_FED_PMI_BASE + diffusion / PHILLY_FED_TO_PMI_DIVISOR → 區間 33~67。
    #   ⚠️ 稽核更正(2026-08-05)：原註解寫「與 ISM PMI 歷史相關性 ~0.85」，**過度宣稱**。
    #     Phil Fed = 單一聯準區約 250 家廠商的「本月 vs 上月」變化擴散指數；
    #     ISM = 全國 16 大產業複合指數，母體與構造都不同。實證反例 2026-07：
    #     Phil Fed 10.3 → 41.4（+31.1），同月官方 ISM 只有 53.3 → 55.6（+2.3），
    #     換算值 63.8 若當真將是 1983 年以來最高 ISM 讀數。
    #     → 只能看方向，不可當 ISM PMI 的水準值讀；換算常數見 shared/fred_series.py。
    #   標 is_proxy=True，UI 顯示「Phil Fed 替代計」。
    if fred_api_key:
        try:
            # v18.119 issue 1: 拉滿月頻 series 供 Phase 4/3-B 使用
            df = fetch_fred(FRED_PHILLY_FED, fred_api_key, n=144)
            if not df.empty and len(df) >= 5:
                df = df.tail(120).copy()
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age <= max_age_days:
                    # 轉換為 PMI 等價刻度(常數 SSOT:shared/fred_series.py,
                    # 該處註解載明此係數無官方出處、僅作刻度對映)
                    df['value'] = (PHILLY_FED_PMI_BASE
                                   + df['value'] / PHILLY_FED_TO_PMI_DIVISOR)
                    v = round(float(df['value'].iloc[-1]), 1)
                    print(f'[macro_core/PMI/PhilFed] ⚠️ 採用替代計 '
                          f'PMI_eq={v} (Phil Fed Diffusion 轉換) date={last_date}')
                    # F-PROV-1 phase 18 v19.156 — 加 fetched_at
                    return {
                        'value': v, 'date': str(last_date),
                        'label': 'Phil Fed 製造業擴散（轉 PMI 刻度）',
                        'source': 'FRED:GACDFSA066MSFRBPHI:proxy', 'is_proxy': True,
                        'series_id': 'GACDFSA066MSFRBPHI',
                        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
                        'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                        'values': [round(float(x), 1) for x in df['value']],
                        'proxy_note': (
                            f'⚠️ 這不是 ISM PMI：來源為費城聯準銀行製造業擴散指數'
                            f'（單一聯準區、約 250 家廠商，問「本月 vs 上月」變化），'
                            f'已用 PMI_eq = {PHILLY_FED_PMI_BASE:.0f} + diffusion/'
                            f'{PHILLY_FED_TO_PMI_DIVISOR:.0f} 線性換算到 PMI 刻度。'
                            f'該換算係數無官方出處，僅為刻度對映；ISM 為全國 16 大產業'
                            f'複合指數，兩者波動幅度差異極大（2026-07 實例：Phil Fed '
                            f'+31.1 而 ISM 僅 +2.3）。**只可看方向，不可當 ISM PMI 的'
                            f'水準值讀**。'),
                    }
        except Exception as e:
            errs.append(f'PhilFed-Proxy:{type(e).__name__}')
            print(f'[macro_core/PMI/PhilFed] ❌ {e}')

    # ── 方案 7: OECD US Business Confidence（FRED BSCICP02USM460S, Proxy）──
    #   最後手段；非 ISM PMI；月頻；值 ~98–102（非 30–70）；與 ISM PMI 相關性 ~0.7。
    #   UI 必須以 is_proxy=True 標註，且分數刻度與 PMI 不同。
    if fred_api_key:
        try:
            # v18.119 issue 1: 拉滿月頻 series
            df = fetch_fred(FRED_BSCICP02, fred_api_key, n=144)
            if not df.empty and len(df) >= 5:
                df = df.tail(120)
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age <= max_age_days:
                    v = round(float(df['value'].iloc[-1]), 2)
                    print(f'[macro_core/PMI/OECD-Proxy] ⚠️ 採用替代指標 '
                          f'BSCICP02USM460S={v} date={last_date}')
                    # F-PROV-1 phase 18 v19.156 — 加 fetched_at
                    return {
                        'value': v, 'date': str(last_date),
                        'label': 'OECD US Business Confidence (Proxy)',
                        'source': 'FRED:BSCICP02USM460S:proxy', 'is_proxy': True,
                        'series_id': 'BSCICP02USM460S',
                        'fetched_at': pd.Timestamp.now('UTC').isoformat(),
                        'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                        'values': [round(float(x), 2) for x in df['value']],
                        'proxy_note': '⚠️ 替代指標：OECD 美國商業信心指數。'
                                      '值域 ~98–102（100 為長期平均，非 50 榮枯線）。'
                                      '與 ISM PMI 相關性 ~0.7，請參考趨勢方向而非絕對位階。',
                    }
                else:
                    errs.append(f'OECD-Proxy:過時 {age} 天')
        except Exception as e:
            errs.append(f'OECD-Proxy:{type(e).__name__}')
            print(f'[macro_core/PMI/OECD-Proxy] ❌ {e}')

    err_msg = ' | '.join(errs) or 'all 7 stages failed'
    print(f'[macro_core/PMI] ❌ 7 段備援全失敗：{err_msg}')
    # F-PROV-1 phase 18 v19.156 — fail token 也帶 source + fetched_at(便於 audit)
    return {'_err_pmi': err_msg, 'value': None,
            'source': 'ISM-PMI:all_7_stages_failed',
            'fetched_at': pd.Timestamp.now('UTC').isoformat()}


# ══════════════════════════════════════════════════════════════
# (已退役 2026-08-05) 總經指南針三指標 fetcher — 隨 🧭 指南針 UI 一併移除。
#   L3 元件 → L2 facade → 本 L1 fetcher 整條鏈 production 0 consumer,
#   依 `PROCESS.md §4` 0-consumer 條款刪除;三個讀數在 🎯 短線雷達都有現成燈號
#   (services/risk_radar.py 的 vix_level / yield_10y_shock / spx_trend_break)。
#   回退:git history 保有完整實作。
#
# (原本這下面還有一條「純數學工具」的分節橫幅,但 v19.205 B1 拆檔時內容已全部
#  搬到 `repositories/macro/math_utils.py`,橫幅本身標的是空的 —— 一併清掉,
#  免得下一個人以為這裡還有東西沒讀到。)
# ══════════════════════════════════════════════════════════════
