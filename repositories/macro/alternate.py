"""repositories/macro/alternate.py — Alternate data 抓取(B1 拆自 macro_repository v19.205).

從原 1078 LOC god module 拆出:
- DefiLlama 穩定幣總市值
- AAII Sentiment(多源 fallback chain)
- ISM PMI(FRED + MacroMicro + ISM World + Stooq + Philly Fed + Conf Board CCI)
- fetch_macro_compass(^VIX + ^TNX + ^GSPC 三大盤面指標)

依賴 fred.fetch_fred / yf.fetch_yf_close。
"""
from __future__ import annotations

import pandas as pd

from infra.proxy import fetch_url
from fund_fetcher import _ttl_cache, register_cache
from shared.colors import TRAFFIC_GREEN, TRAFFIC_YELLOW, TRAFFIC_RED
from shared.fred_series import FRED_BSCICP02, FRED_PHILLY_FED
from shared.ttls import TTL_5MIN, TTL_30MIN

from .fred import fetch_fred
from .yf import fetch_yf_close


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
    """
    r = fetch_url(DEFILLAMA_STABLECOIN_URL, timeout=20)
    if r is None:
        return pd.Series(dtype=float, name="stablecoin_mcap")
    try:
        data = r.json()
    except Exception as e:
        print(f"[defillama] 穩定幣 JSON 解析失敗: {e}")
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


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)
def fetch_aaii_sentiment() -> dict:
    """抓 AAII Investor Sentiment Survey 散戶情緒週度數值（best-effort scrape）。

    v19.192:從單 URL 改成 3 段 fallback chain(模仿 MoneyDJ 子網域 pattern),
    補完整 Chrome UA + Accept headers,timeout 提到 20s 配合 NAS Squid 中繼。

    Returns
    -------
    dict
        成功:{value(spread), unit, bull, bear, date, source, fetched_at, url_used}
        失敗:{_err: 多段 trace, source, fetched_at}(fail-loud token,L2 caller 視為錯誤狀態)

    F-PROV-1 v19.84 phase 3:provenance(§2.2)— 全路徑(含 _err)皆帶 source + fetched_at。
    """
    import re as _re
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
            m_bull = _re.search(r"[Bb]ullish[^0-9]{0,40}(\d{1,2}\.\d)\s*%", r.text)
            m_bear = _re.search(r"[Bb]earish[^0-9]{0,40}(\d{1,2}\.\d)\s*%", r.text)
            if not m_bull or not m_bear:
                trace.append(f"{url.rsplit('/', 1)[-1] or 'aaii'}:regex no match")
                continue
            bull = float(m_bull.group(1))
            bear = float(m_bear.group(1))
            return {
                "value": bull - bear,
                "unit": "%",
                "bull": bull,
                "bear": bear,
                "date": "weekly",
                "url_used": url,
                **_prov,
            }
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
    #   FRED 上仍持續更新；範圍 -50~+50；數學轉換為 PMI 等價刻度：
    #   PMI_eq = 50 + diffusion / 3 → 區間 33~67，與 ISM PMI 歷史相關性 ~0.85。
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
                    # 轉換為 PMI 等價刻度
                    df['value'] = 50.0 + df['value'] / 3.0
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
                        'proxy_note': '⚠️ 替代指標：Phil Fed 製造業擴散指數，'
                                      '已用 PMI_eq = 50 + diffusion/3 轉換為 PMI 刻度。'
                                      '與 ISM PMI 歷史相關性 ~0.85。',
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
# 總經指南針 (Top-Down Macro Compass) — Phase 1 規格三大指標
#   VIX / TNX / GSPC + 60MA，固定於頁面頂部供新人秒懂市場大環境。
#   呼叫端：app.py 的 render_macro_compass()（在 st.tabs() 之前渲染）。
# ══════════════════════════════════════════════════════════════

@register_cache
@_ttl_cache(ttl_sec=TTL_5MIN, maxsize=8)   # v18.58: 每次 rerun 都觸發 — 避免 widget 互動連環抓
def fetch_macro_compass(range_: str = "6mo") -> dict:
    """Phase 1 — 一次抓 ^VIX / ^TNX / ^GSPC 三大美股指標 + GSPC 60MA。

    所有抓取都走 macro_core.fetch_yf_close()（NAS proxy → Yahoo Chart REST API），
    避開 yfinance 直連被 Streamlit Cloud IP 限流。失敗欄位填 None，UI 端優雅降級。

    Returns dict:
      vix  : {'value', 'series', 'dates', 'signal':(light, label, color)} | None
      tnx  : 同上                                                          | None
      gspc : 同上 + {'ma60', 'ma60_series'}                                | None
    """
    # F-PROV-1 v19.86 phase 5:provenance(§2.2)
    _fetched_at = pd.Timestamp.now('UTC').isoformat()
    out: dict = {'vix': None, 'tnx': None, 'gspc': None,
                  'source': 'Yahoo:^VIX+^TNX+^GSPC:compass',
                  'fetched_at': _fetched_at}

    def _sig_vix(v):
        # Phase 1 規格：>25 黃 / >30 綠（恐慌貪婪區=逢低加碼時機）
        if v > 30: return ('🟢', '恐慌貪婪區（準備跌深就買）', TRAFFIC_GREEN)
        if v > 25: return ('🟡', '波動加劇', TRAFFIC_YELLOW)
        return ('🟢', '市場平靜', TRAFFIC_GREEN)

    def _sig_tnx(t):
        # 估值壓力：≥4.5% 紅 / 3.5–4.5 黃 / <3.5 綠（寬鬆）
        if t >= 4.5: return ('🔴', '估值壓力（科技股不利）', TRAFFIC_RED)
        if t >= 3.5: return ('🟡', '中性區', TRAFFIC_YELLOW)
        return ('🟢', '寬鬆有利', TRAFFIC_GREEN)

    def _sig_gspc(g, ma):
        # Phase 1 規格：站上 60MA=多頭、跌破=趨勢轉弱
        if ma is None or g is None:
            return ('⚪', '60MA 計算中', '#8b949e')
        if g >= ma: return ('🟢', '多頭格局（股優於債）', TRAFFIC_GREEN)
        return ('🔴', '趨勢轉弱（提高防禦）', TRAFFIC_RED)

    # ── ^VIX ────────────────────────────────────────────────
    try:
        s = fetch_yf_close('^VIX', range_=range_)
        if not s.empty:
            v = round(float(s.iloc[-1]), 2)
            tail = s.tail(90)
            out['vix'] = {
                'value': v,
                'series': [round(float(x), 2) for x in tail.tolist()],
                'dates':  [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_vix(v),
            }
    except Exception as e:
        print(f'[macro_compass] VIX fetch failed: {e}')

    # ── ^TNX ────────────────────────────────────────────────
    try:
        s = fetch_yf_close('^TNX', range_=range_)
        if not s.empty:
            t = round(float(s.iloc[-1]), 3)
            tail = s.tail(90)
            out['tnx'] = {
                'value': t,
                'series': [round(float(x), 3) for x in tail.tolist()],
                'dates':  [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_tnx(t),
            }
    except Exception as e:
        print(f'[macro_compass] TNX fetch failed: {e}')

    # ── ^GSPC + 60MA ────────────────────────────────────────
    try:
        s = fetch_yf_close('^GSPC', range_=range_)
        if not s.empty:
            g = round(float(s.iloc[-1]), 2)
            ma60_ser = s.rolling(60).mean()
            ma60_last = ma60_ser.dropna()
            ma60 = round(float(ma60_last.iloc[-1]), 2) if not ma60_last.empty else None
            tail = s.tail(90)
            ma_tail = ma60_ser.tail(90)
            out['gspc'] = {
                'value': g,
                'ma60': ma60,
                'series': [round(float(x), 2) for x in tail.tolist()],
                'ma60_series': [None if pd.isna(x) else round(float(x), 2) for x in ma_tail.tolist()],
                'dates': [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_gspc(g, ma60),
            }
    except Exception as e:
        print(f'[macro_compass] GSPC fetch failed: {e}')

    return out


# ══════════════════════════════════════════════════════════════
# 純數學工具(不需要網路,兩邊共用)
# ══════════════════════════════════════════════════════════════
