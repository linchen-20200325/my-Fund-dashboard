"""repositories/news_repository.py — 國際財經新聞 RSS Repository
（v11.0 B-10 從 fund_fetcher.py 抽出）

純資料層：feedparser 抓 11 個 RSS feed → 過濾 + 排序 → 回 list[dict]。
- 一般財經關鍵字命中即收錄；系統性風險關鍵字命中者 is_systemic=True 並永遠排前
- 不依賴 streamlit；caller 自行 cache（不在這層使用 @st.cache_data）

v11.0 分層歸位：Repository Layer（純 RSS 抓取）。
向後相容：fund_fetcher.py 原位置改為 `from repositories.news_repository import fetch_market_news`
        re-export，既有 caller `from fund_fetcher import fetch_market_news` 零修改。
"""
from __future__ import annotations

import datetime as _dt


def _now_iso_utc() -> str:
    """C2 v19.208 F-PROV-1:回 UTC ISO timestamp,供 news dict 加 fetched_at(§2.2)。"""
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def fetch_market_news(max_per_feed: int = 5) -> list:
    """
    從 RSS 抓取會影響股市、匯率、債券的國際財經新聞 + 系統性風險事件。
    v18.86：加 SYSTEMIC_RISK 關鍵字（戰爭/銀行倒閉/黑天鵝），命中者 is_systemic=True，
            排序時 systemic 永遠在前；給 MK AI 判斷系統性風險用，
            目的：戰爭、雷曼兄弟級事件、銀行擠兌等重大利空不會被一般財經新聞淹沒。
    回傳: [{title, summary, source, published, url, is_systemic}]

    v18.186：RSS 改走 NAS Proxy（infra.proxy.fetch_url，含 timeout + 自動降級直連），
            不再用 feedparser 內建裸連 → 修 Streamlit Cloud IP 被封時新聞整條死。
            抓取失敗不再靜默：累計失敗來源，結果為空時回友善提示（區分 Proxy 斷 vs 無命中）。
    """
    _fetched_at = _now_iso_utc()
    try:
        import feedparser as _fp
    except ImportError:
        return [{"title": "feedparser 未安裝", "summary": "pip install feedparser",
                 "source": "system", "published": "", "url": "",
                 "is_systemic": False, "fetched_at": _fetched_at}]

    # v18.186：透過 NAS Proxy 抓 RSS bytes（feedparser 解析 bytes，不自己連網）。
    # 取不到（無 streamlit / infra 不可用）時退回 feedparser 直連，行為與舊版一致。
    try:
        from infra.proxy import fetch_url as _fetch_url
    except Exception:
        _fetch_url = None

    FEEDS = [
        # ── 美國 / 全球財經主流 ──
        # v19.293: Reuters feeds.reuters.com dead since June 2020 (all 404) — removed 3 entries
        # v19.295: FT Markets requires subscription (near-empty content) — removed
        # v19.295: Investing.com blocked (403 without login) — removed
        # v19.295: Bloomberg Markets blocked for non-subscribers — removed
        ("MarketWatch",      "https://feeds.content.dowjones.io/public/rss/mw_bulletins"),
        # v19.297: rss/2.0/headline?s=%5EGSPC 回空（已死亡）→ 改用 news/rssindex（實測有 application/xml 回傳）
        ("Yahoo Finance",    "https://finance.yahoo.com/news/rssindex"),
        ("CNBC Economy",     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
        ("CNBC Finance",     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"),
        # v18.86：地緣政治 / 突發新聞專屬 feed — 純財經 feed 對「戰爭爆發」捕捉較慢
        ("BBC World",         "https://feeds.bbci.co.uk/news/world/rss.xml"),
    ]

    # 一般財經 — 任一命中就保留
    KEYWORDS = [
        "Fed", "interest rate", "inflation", "CPI", "GDP", "recession",
        "bond", "treasury", "yield", "currency", "dollar", "yen", "euro",
        "stock market", "S&P", "Nasdaq", "earnings", "trade war", "tariff",
        "PMI", "unemployment", "central bank", "ECB", "BOJ", "PBOC",
        "China", "Taiwan", "semiconductor", "AI", "technology", "emerging market",
        "利率", "通膨", "聯準會", "美元", "匯率", "債券", "股市",
    ]

    # v18.86：系統性風險關鍵字（戰爭 / 銀行倒閉 / 黑天鵝），命中者排序最優先
    SYSTEMIC_RISK_KEYWORDS = [
        # 戰爭 / 地緣政治
        "war", "invasion", "ukraine", "russia", "israel", "gaza", "iran",
        "taiwan strait", "south china sea", "north korea", "missile",
        "drone strike", "sanctions", "embargo", "geopolitical", "nuclear",
        # 金融危機 / 破產
        "bankrupt", "bankruptcy", "collapse", "default", "bailout",
        "lehman", "credit suisse", "svb", "silicon valley bank",
        "signature bank", "first republic",
        "bank failure", "bank run", "deposit run", "liquidity crisis",
        "systemic risk", "contagion", "meltdown",
        # 央行緊急動作
        "emergency rate", "qt halt", "qe restart", "discount window",
        "fdic", "bail-in", "bail in",
        # 市場崩盤訊號
        "circuit breaker", "trading halt", "vix spike",
        "credit spread widening", "yield curve invert",
        "flight to safety", "panic selling", "rout", "selloff",
        # 中文
        "戰爭", "戰事", "侵略", "倒閉", "破產", "雷曼", "金融危機",
        "信用緊縮", "崩盤", "黑天鵝", "系統性風險", "流動性危機",
        "兌付危機", "擠兌", "違約",
    ]

    results = []
    seen_titles = set()
    failed: list = []          # v18.186：抓取失敗的來源名（供空結果時友善提示）
    _FEED_TIMEOUT = 12         # 秒：單一 feed 上限，避免某來源卡住拖垮整批

    for source_name, feed_url in FEEDS:
        try:
            if _fetch_url is not None:
                _resp = _fetch_url(feed_url, timeout=_FEED_TIMEOUT, retries=2)
                if _resp is None or not getattr(_resp, "content", b""):
                    failed.append(source_name)   # Proxy/來源無回應 → 記下不靜默
                    continue
                d = _fp.parse(_resp.content)
            else:
                d = _fp.parse(feed_url)          # 無 proxy 模組 → 退回直連
            count = 0
            for entry in d.entries:
                if count >= max_per_feed:
                    break
                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")[:300]
                url     = getattr(entry, "link", "")
                pub     = getattr(entry, "published", "")[:25]

                text_check = (title + " " + summary).lower()
                # v18.86：systemic 永遠收錄；一般財經則需命中 KEYWORDS
                _is_sys = any(kw in text_check for kw in SYSTEMIC_RISK_KEYWORDS)
                _is_fin = any(kw.lower() in text_check for kw in KEYWORDS)
                if not (_is_sys or _is_fin):
                    continue
                if title in seen_titles:
                    continue
                seen_titles.add(title)

                results.append({
                    "title":       title,
                    "summary":     summary,
                    "source":      source_name,
                    "published":   pub,
                    "url":         url,
                    "is_systemic": _is_sys,
                    "fetched_at":  _fetched_at,
                })
                count += 1
        except Exception:
            failed.append(source_name)   # v18.186：不再靜默 — 累計失敗來源
            continue

    # v18.186：友善空狀態 — 區分「全失敗（可能 Proxy 斷）」vs「正常但無命中」
    if not results:
        if failed:
            return [{
                "title": "⚠️ 暫時無法取得財經新聞",
                "summary": (f"已嘗試 {len(FEEDS)} 個來源、{len(failed)} 個無回應"
                            "（可能 NAS Proxy 斷線或來源暫時不可用），稍後重試。"),
                "source": "system", "published": "", "url": "",
                "is_systemic": False, "fetched_at": _fetched_at,
            }]
        return [{
            "title": "ℹ️ 目前沒有符合追蹤條件的財經新聞",
            "summary": "RSS 來源正常，但近期標題未命中追蹤關鍵字。",
            "source": "system", "published": "", "url": "",
            "is_systemic": False, "fetched_at": _fetched_at,
        }]

    # v18.86：systemic 永遠排前面（同類別內按日期新→舊）
    sys_news = sorted(
        [r for r in results if r.get("is_systemic")],
        key=lambda x: x.get("published", ""), reverse=True,
    )
    gen_news = sorted(
        [r for r in results if not r.get("is_systemic")],
        key=lambda x: x.get("published", ""), reverse=True,
    )
    return (sys_news + gen_news)[:30]


# ══════════════════════════════════════════════════════════════════════
# v18.196（v5.0 Task3）：依資產類別過濾新聞
#   - fetch_macro_news(asset_class)：spec 接口 — 抓 + 依類別過濾（會打網路）
#   - filter_news_by_asset_class()：純過濾既有清單（給 UI 過濾 session 快取、零網路）
#   - infer_asset_class()：從基金名稱/類別字串推資產類別
# ══════════════════════════════════════════════════════════════════════

# 資產類別 → 命中關鍵字（大小寫不敏感）。空清單（macro/all）= 不過濾。
ASSET_CLASS_KEYWORDS: dict = {
    "stock": ["stock", "equity", "equities", "s&p", "nasdaq", "dow", "shares",
              "earnings", "ipo", "股", "股市", "股票", "台股", "美股", "權值"],
    "bond": ["bond", "treasury", "yield", "credit", "duration", "coupon",
             "債", "債券", "公債", "殖利率", "利差", "固定收益", "投資等級", "高收益"],
    "fx": ["currency", "dollar", "yen", "euro", "forex", "exchange rate",
           "美元", "日圓", "歐元", "新台幣", "匯率", "貶值", "升值"],
    "commodity": ["oil", "crude", "brent", "wti", "gold", "copper", "commodity",
                  "commodities", "metals", "原油", "黃金", "原物料", "大宗商品", "能源"],
    "macro": [],   # 總經 / 全部 — 不過濾
}

# 推類別時的偵測順序（多重資產 → 命不中任一 → 落 macro）
_CLASS_ORDER = ("bond", "stock", "commodity", "fx")


def _normalize_asset_class(asset_class: str) -> str:
    """中文/英文/同義詞 → 標準 key（未知或總經 → 'macro'）。"""
    a = str(asset_class or "").strip().lower()
    if a in ASSET_CLASS_KEYWORDS:
        return a
    alias = {
        "股票": "stock", "股": "stock", "equity": "stock",
        "債券": "bond", "債": "bond", "fixed income": "bond",
        "匯率": "fx", "匯": "fx", "currency": "fx",
        "原物料": "commodity", "商品": "commodity", "能源": "commodity",
        "總經": "macro", "all": "macro", "": "macro",
    }
    return alias.get(a, "macro")


def infer_asset_class(text: str) -> str:
    """從基金名稱/類別字串推資產類別；多重資產或無法判別 → 'macro'。"""
    t = str(text or "").lower()
    if not t:
        return "macro"
    for cls in _CLASS_ORDER:
        if any(kw.lower() in t for kw in ASSET_CLASS_KEYWORDS[cls]):
            return cls
    return "macro"


def filter_news_by_asset_class(news: list, asset_class: str) -> list:
    """純過濾既有新聞清單（不打網路）。systemic 永遠保留；
    過濾後若為空則回原清單（有總比沒有好）。macro/未知 → 不過濾。"""
    cls = _normalize_asset_class(asset_class)
    kws = ASSET_CLASS_KEYWORDS.get(cls) or []
    items = list(news or [])
    if not kws:
        return items
    out = []
    for n in items:
        if not isinstance(n, dict):
            continue
        if n.get("is_systemic"):
            out.append(n)
            continue
        _txt = (str(n.get("title", "")) + " " + str(n.get("summary", ""))).lower()
        if any(kw.lower() in _txt for kw in kws):
            out.append(n)
    return out or items


_GOOGLE_NEWS_RSS = "https://news.google.com/rss/search"


def fetch_stock_news(query: str, max_items: int = 3,
                     lang: str = "zh-TW", region: str = "TW") -> list:
    """v18.206：對「特定個股 / 關鍵字」用 Google News RSS 搜尋近期新聞（走 NAS proxy）。

    與 fetch_market_news（廣義財經 RSS）不同：這裡針對單一持股名查詢，台股/中文名
    也抓得到。回傳 [{title, summary, source, published, url, is_systemic}]；失敗回 []。
    """
    q = str(query or "").strip()
    if not q:
        return []
    _fetched_at = _now_iso_utc()
    try:
        import feedparser as _fp
    except ImportError:
        return []
    try:
        from infra.proxy import fetch_url as _fetch_url
    except Exception:
        _fetch_url = None

    _params = {"q": q, "hl": lang, "gl": region,
               "ceid": f"{region}:{lang.split('-')[0]}"}
    try:
        if _fetch_url is not None:
            _r = _fetch_url(_GOOGLE_NEWS_RSS, params=_params, timeout=12, retries=2)
            if _r is None or not getattr(_r, "content", b""):
                return []
            d = _fp.parse(_r.content)
        else:
            from urllib.parse import urlencode
            d = _fp.parse(f"{_GOOGLE_NEWS_RSS}?{urlencode(_params)}")
    except Exception:
        return []

    out = []
    for e in getattr(d, "entries", [])[:max_items]:
        _title = getattr(e, "title", "")
        if not _title:
            continue
        _srcobj = getattr(e, "source", None)
        _src = (getattr(_srcobj, "title", "") if _srcobj is not None else "") or "Google News"
        out.append({
            "title":       _title,
            "summary":     getattr(e, "summary", "")[:200],
            "source":      _src,
            "published":   getattr(e, "published", "")[:25],
            "url":         getattr(e, "link", ""),
            "is_systemic": False,
            "fetched_at":  _fetched_at,
        })
    return out


def fetch_macro_news(asset_class: str = "", max_per_feed: int = 5) -> list:
    """v5.0 Task3 接口：抓財經新聞並依資產類別過濾。

    Provenance(C2 v19.208 F-PROV-1):pass-through fetch_market_news,每個
    news dict 已含 'source' + 'fetched_at'(§2.2 schema-additive),
    filter_news_by_asset_class 不改 dict 內容,inheritance 直通。

    asset_class: stock / bond / fx / commodity / macro（或中文：股/債/匯/原物料/總經）。
                 空字串或 macro → 不過濾（等同 fetch_market_news）。
    """
    return filter_news_by_asset_class(
        fetch_market_news(max_per_feed=max_per_feed), asset_class)
