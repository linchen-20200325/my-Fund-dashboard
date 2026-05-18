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


def fetch_market_news(max_per_feed: int = 5) -> list:
    """
    從 RSS 抓取會影響股市、匯率、債券的國際財經新聞 + 系統性風險事件。
    v18.86：加 SYSTEMIC_RISK 關鍵字（戰爭/銀行倒閉/黑天鵝），命中者 is_systemic=True，
            排序時 systemic 永遠在前；給 MK AI 判斷系統性風險用，
            目的：戰爭、雷曼兄弟級事件、銀行擠兌等重大利空不會被一般財經新聞淹沒。
    回傳: [{title, summary, source, published, url, is_systemic}]
    """
    try:
        import feedparser as _fp
    except ImportError:
        return [{"title": "feedparser 未安裝", "summary": "pip install feedparser",
                 "source": "system", "published": "", "url": "",
                 "is_systemic": False}]

    FEEDS = [
        # ── 美國 / 全球財經主流 ──
        ("Reuters Business", "https://feeds.reuters.com/reuters/businessNews"),
        ("Reuters Markets",  "https://feeds.reuters.com/reuters/companyNews"),
        ("MarketWatch",      "https://feeds.content.dowjones.io/public/rss/mw_bulletins"),
        ("FT Markets",       "https://www.ft.com/rss/home/uk"),
        ("Yahoo Finance",    "https://finance.yahoo.com/rss/2.0/headline?s=%5EGSPC&region=US&lang=en-US"),
        ("Investing.com",    "https://www.investing.com/rss/news_14.rss"),
        ("CNBC Economy",     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258"),
        ("CNBC Finance",     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10000664"),
        # v18.86：地緣政治 / 突發新聞專屬 feed — 純財經 feed 對「戰爭爆發」捕捉較慢
        ("BBC World",         "https://feeds.bbci.co.uk/news/world/rss.xml"),
        ("Reuters Top News",  "https://feeds.reuters.com/reuters/topNews"),
        ("Bloomberg Markets", "https://feeds.bloomberg.com/markets/news.rss"),
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

    for source_name, feed_url in FEEDS:
        try:
            d = _fp.parse(feed_url)
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
                })
                count += 1
        except Exception as _e:
            pass  # skip failed feeds silently

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
