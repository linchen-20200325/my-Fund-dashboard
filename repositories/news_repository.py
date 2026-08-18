"""repositories/news_repository.py — 國際財經新聞 RSS Repository
（v11.0 B-10 從 fund_fetcher.py 抽出）

純資料層：feedparser 抓 RSS feed → 過濾 + 排序 → 回 list[dict]。
（v19.354 文件校正：實際 FEEDS 現為 5 個 — MarketWatch / Yahoo Finance /
 CNBC Economy / CNBC Finance / BBC World；Reuters(3)/FT/Investing/Bloomberg
 已於 v19.293~297 陸續下架移除。原 docstring「11 個」為漂移。）
- 一般財經關鍵字命中即收錄；`classify_systemic()` 判定為系統性者 is_systemic=True 並永遠排前
- ⚠️ `is_systemic` 的語意是**排序權重**，不是風險告警等級（2026-08-05 稽核釐清；
  風險告警請用 `services.macro.us_indicators.detect_systemic_risk()` 的加權分）
- 不依賴 streamlit；caller 自行 cache（不在這層使用 @st.cache_data）

v11.0 分層歸位：Repository Layer（純 RSS 抓取）。
向後相容：fund_fetcher.py 原位置改為 `from repositories.news_repository import fetch_market_news`
        re-export，既有 caller `from fund_fetcher import fetch_market_news` 零修改。
"""
from __future__ import annotations

import datetime as _dt
import re as _re


def _now_iso_utc() -> str:
    """C2 v19.208 F-PROV-1:回 UTC ISO timestamp,供 news dict 加 fetched_at(§2.2)。"""
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


# ══════════════════════════════════════════════════════════════════════
# 系統性風險旗標 SSOT(2026-08-05 稽核重寫)
# ══════════════════════════════════════════════════════════════════════
# 【為什麼重寫】舊表(v18.86)是「~60 個單詞,任一子字串命中即 is_systemic=True」。
# 三個結構缺陷,實測 2026-08-04~05 造成 6 則假警報(同畫面頂端 banner 還顯示 ✅ LOW):
#
#   1. **無方向性過濾** — 緩和被讀成升級。荷姆茲海峽談判「有進展」照樣命中。
#   2. **無領域過濾**   — 裸國名 ukraine/russia/israel/gaza/iran + war/geopolitical
#      讓 BBC World(綜合國際新聞 feed)**結構上保證每天命中**。實測誤觸包含
#      「Ceuta migrant crisis」(移民)、「WW2 shells」(考古)、「SpaceX rocket
#      collides with the Moon」(太空)。
#   3. **無規模過濾**   — 小旅行社倒閉也吃到 "bankruptcy"。
#   (外加)舊碼用裸 `in` 子字串比對 → "war" 命中 "warning" / "forward"。
#
# 【現在的規則】三層命中 + 兩道否決,全部走 word-boundary(CJK 走子字串,無詞界概念):
#
#   L1 直接命中   DIRECT             —— 本身就是「金融 × 系統性 × 大規模」的詞,單獨成立
#   L2 地緣共現   ESCALATION ∧ FINANCIAL   —— 地緣/軍事升級詞**必須**與金融詞共現
#   L3 困境共現   DISTRESS ∧ FINANCIAL ∧ SCALE —— 企業/主權困境詞另需規模詞(規模過濾)
#
#   否決 A 方向性 DEESCALATION —— 停火/達成協議/危機化解 → 這是緩和,不是升級
#   否決 B 獲利框架 BENIGN     —— 財報大勝/創新高 → 例:「BP posts 143% profit hike
#                                as Iran war sends oil prices skyward」實質是財報新聞
#   兩道否決**只作用於 L2 / L3**,不否決 L1:L1 詞(bank run / lehman / 擠兌 …)語意
#   已經封閉,「bank run averted」這種要靠 A 擋,而它確實會被 A 擋 —— 但若是
#   「lehman-style collapse」配上財報詞,不該因為出現 "profit" 就放行,故 L1 不受否決。
#
# 【旗標 vs 風險分 — 別再混用】(這正是假警報的根因)
#   本旗標 = **排序權重**:回答「這則該不該排在最前面」。
#   風險告警請吃 `services.macro.us_indicators.detect_systemic_risk()` 的加權分
#   (44 詞 × 權重 1~4 → HIGH/MEDIUM/LOW)。兩者詞表不同、語意不同。
#   目前 `ui/helpers/macro/beginner_view.compute_five_bucket_summary` 仍以本旗標
#   的「命中則數」渲染五桶卡 —— 本次先把旗標修準(治本),UI 端遷移到 risk_level
#   屬 L3 檔案,不在本次所有權內,見交付報告。
# ──────────────────────────────────────────────────────────────────────

# L1 直接命中:金融 × 系統性 × 大規模,單詞即成立(不需共現、不受否決)
SYSTEMIC_DIRECT_KEYWORDS: frozenset = frozenset({
    # 銀行 / 流動性
    "bank run", "bank runs", "bank failure", "bank failures", "deposit run",
    "liquidity crisis", "credit crunch", "credit crisis", "debt crisis",
    "financial crisis", "banking crisis", "systemic risk", "contagion",
    "too big to fail", "fdic", "bail-in", "bail in", "bailout",
    "discount window", "emergency rate cut", "emergency rate hike",
    # 具名事件(歷史錨點,出現即高度相關)
    "lehman", "credit suisse", "silicon valley bank", "signature bank",
    "first republic", "svb",
    # 市場失序
    "circuit breaker", "trading halt", "flight to safety", "panic selling",
    "margin call", "margin calls", "sovereign default",
    # 中文
    "金融危機", "系統性風險", "流動性危機", "信用緊縮",
    "擠兌", "兌付危機", "雷曼", "崩盤", "股災", "黑天鵝",
})

# L2 地緣 / 軍事升級詞 —— **需與 FINANCIAL 共現**
# ⚠️ 刻意**不含**裸國名(ukraine / russia / israel / gaza / iran)與
#    geopolitical / sanctions / rout / selloff / nuclear —— 這五類在綜合國際
#    新聞 feed 上是背景雜訊,不具「系統性金融風險」鑑別力(2026-08-05 稽核點名)。
SYSTEMIC_ESCALATION_KEYWORDS: frozenset = frozenset({
    "war", "warfare", "invasion", "invades", "invaded",
    "missile strike", "missile attack", "airstrike", "air strike",
    "drone strike", "embargo", "blockade", "military conflict",
    "escalation", "escalates", "escalating",
    "taiwan strait", "south china sea", "north korea",
    "coup", "terror attack", "nuclear strike",
    "戰爭", "戰事", "侵略", "軍事衝突", "封鎖海峽", "台海",
})

# L3 企業 / 主權困境詞 —— **需 FINANCIAL ∧ SCALE 共現**(規模過濾)
SYSTEMIC_DISTRESS_KEYWORDS: frozenset = frozenset({
    "bankrupt", "bankruptcy", "insolvency", "insolvent",
    "default", "defaults", "defaulted",
    "collapse", "collapses", "collapsed", "meltdown",
    "破產", "倒閉", "違約",
})

# 金融 / 市場領域詞(領域過濾:L2 / L3 的必要條件)
SYSTEMIC_FINANCIAL_KEYWORDS: frozenset = frozenset({
    "market", "markets", "stock", "stocks", "equity", "equities", "shares",
    "s&p", "nasdaq", "dow jones", "wall street", "index futures",
    "bond", "bonds", "treasury", "treasuries", "yield", "yields",
    "credit", "spread", "spreads", "investor", "investors",
    "bank", "banks", "lender", "lenders", "insurer", "central bank",
    "fed", "federal reserve", "ecb", "boj",
    "dollar", "currency", "forex", "exchange rate",
    "oil", "crude", "brent", "commodity", "commodities", "gold",
    "inflation", "economy", "economic", "recession", "gdp", "trading",
    "股市", "股票", "台股", "美股", "債市", "債券", "市場", "投資人",
    "銀行", "央行", "美元", "匯率", "油價", "通膨", "經濟", "金融",
})

# 規模詞(L3 專用:過濾「小旅行社倒閉」這類非系統性事件)
SYSTEMIC_SCALE_KEYWORDS: frozenset = frozenset({
    "billion", "billions", "trillion", "trillions",
    "systemic", "global", "nationwide", "worldwide",
    "major", "biggest", "largest", "giant", "sovereign",
    "bank", "banks", "lender", "lenders", "insurer", "insurers",
    "兆", "億", "全球", "大型", "最大", "主權", "銀行",
})

# 否決 A:方向性 —— 緩和 / 化解,不是升級
SYSTEMIC_DEESCALATION_KEYWORDS: frozenset = frozenset({
    "ceasefire", "cease-fire", "truce", "peace deal", "peace talks",
    "peace agreement", "de-escalation", "de-escalate", "de-escalates",
    "deescalation", "agreement reached", "deal reached", "talks progress",
    "sanctions lifted", "sanctions eased", "eases", "easing tensions",
    "averted", "resolved", "resolution reached", "rescued",
    "停火", "和談", "和平協議", "達成協議", "解除制裁", "緩和", "化解",
})

# 否決 B:獲利 / 創高框架 —— 實質是財報或多頭新聞
SYSTEMIC_BENIGN_KEYWORDS: frozenset = frozenset({
    "profit", "profits", "profitable",
    "earnings beat", "beats estimates", "tops estimates",
    "record high", "all-time high", "record profit", "record results",
    "revenue jump", "rally", "rallies", "surge to record", "upgraded",
    "獲利", "創新高", "優於預期", "大漲",
})

# 非 ASCII(CJK)判定門檻:CJK 無「詞界」概念,只能子字串比對
_CJK_START = 0x2E80


def _compile_term(term: str):
    """英文詞編成 word-boundary regex;含 CJK 者回 None(改走子字串)。

    用 lookaround 而非 `\\b`:詞條含 `&`(s&p)、`-`(bail-in)時 `\\b` 行為不直覺。
    這一步同時修掉舊碼裸 `in` 造成的 "war" 命中 "warning" / "forward"。
    """
    if any(ord(_c) >= _CJK_START for _c in term):
        return None
    return _re.compile(r"(?<![a-z0-9])" + _re.escape(term) + r"(?![a-z0-9])")


def _compile_set(terms) -> tuple:
    """frozenset → ((term, compiled_or_None), ...),import 時一次編譯(避免逐則重編)。"""
    return tuple((_t, _compile_term(_t)) for _t in sorted(terms))


_RE_DIRECT = _compile_set(SYSTEMIC_DIRECT_KEYWORDS)
_RE_ESCALATION = _compile_set(SYSTEMIC_ESCALATION_KEYWORDS)
_RE_DISTRESS = _compile_set(SYSTEMIC_DISTRESS_KEYWORDS)
_RE_FINANCIAL = _compile_set(SYSTEMIC_FINANCIAL_KEYWORDS)
_RE_SCALE = _compile_set(SYSTEMIC_SCALE_KEYWORDS)
_RE_DEESCALATION = _compile_set(SYSTEMIC_DEESCALATION_KEYWORDS)
_RE_BENIGN = _compile_set(SYSTEMIC_BENIGN_KEYWORDS)


def _hits(compiled: tuple, text_lower: str) -> list:
    """回傳命中的詞(list[str]);未命中回 []。"""
    out = []
    for _t, _rx in compiled:
        if (_rx.search(text_lower) if _rx is not None else (_t in text_lower)):
            out.append(_t)
    return out


def classify_systemic(title: str, summary: str = "") -> tuple:
    """(is_systemic, evidence) —— 純函式,零 I/O,可直接單測。

    `evidence` 一律回傳(即使 is_systemic=False),格式 ``["L1:bank run", ...]`` /
    ``["L2:war", "fin:oil", "veto-benign:profit"]``。**近失命中也回**,因為稽核
    2026-08-05 明確要求「跑一次就能 100% 收斂」—— 只印命中的無法回答「為什麼這則
    沒被算進去」,近失證據才能一次看完整判斷鏈(§2.2 血緣)。
    """
    _text = f"{title or ''} {summary or ''}".lower()
    if not _text.strip():
        return False, []

    _ev: list = []

    _d = _hits(_RE_DIRECT, _text)
    if _d:
        _ev.extend(f"L1:{_t}" for _t in _d)
        return True, _ev

    _esc = _hits(_RE_ESCALATION, _text)
    _dis = _hits(_RE_DISTRESS, _text)
    if not (_esc or _dis):
        return False, _ev                      # 連候選詞都沒有 → 安靜略過

    _ev.extend(f"L2:{_t}" for _t in _esc)
    _ev.extend(f"L3:{_t}" for _t in _dis)

    _fin = _hits(_RE_FINANCIAL, _text)
    if not _fin:
        _ev.append("miss:無金融詞共現")        # 領域過濾:migrant crisis / WW2 shells
        return False, _ev
    _ev.extend(f"fin:{_t}" for _t in _fin[:3])

    _veto_a = _hits(_RE_DEESCALATION, _text)
    if _veto_a:
        _ev.extend(f"veto-deescalation:{_t}" for _t in _veto_a)
        return False, _ev                      # 方向過濾:停火 / 達成協議
    _veto_b = _hits(_RE_BENIGN, _text)
    if _veto_b:
        _ev.extend(f"veto-benign:{_t}" for _t in _veto_b)
        return False, _ev                      # 框架過濾:財報大勝 / 創新高

    if _esc:
        return True, _ev                       # L2 成立:地緣升級 ∧ 金融

    _scale = _hits(_RE_SCALE, _text)
    if not _scale:
        _ev.append("miss:無規模詞共現")        # 規模過濾:小公司倒閉
        return False, _ev
    _ev.extend(f"scale:{_t}" for _t in _scale[:3])
    return True, _ev                           # L3 成立:困境 ∧ 金融 ∧ 規模


def fetch_market_news(max_per_feed: int = 5) -> list:
    """
    從 RSS 抓取會影響股市、匯率、債券的國際財經新聞 + 系統性風險事件。
    v18.86：加 SYSTEMIC_RISK 關鍵字（戰爭/銀行倒閉/黑天鵝），命中者 is_systemic=True，
            排序時 systemic 永遠在前；給  AI 判斷系統性風險用，
            目的：戰爭、雷曼兄弟級事件、銀行擠兌等重大利空不會被一般財經新聞淹沒。
    回傳: [{title, summary, source, published, url, is_systemic}]

    2026-08-05 稽核：`is_systemic` 判定改走模組層 `classify_systemic()`
            （三層命中 + 兩道否決，見該函式與其上方 SSOT 註解）。
            **語意仍是「排序權重」**；要做風險告警請用
            `services.macro.us_indicators.detect_systemic_risk()` 的加權分。
            同時補齊 log：每則命中/近失印標題 + 命中詞、每個 feed 印 entries/kept/systemic、
            全批印總結 —— 跑一次即可完整還原判斷鏈（原本 feed 回空/gzip 完全看不出來）。

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

    # v18.86 的 SYSTEMIC_RISK_KEYWORDS 已於 2026-08-05 稽核重寫為模組層 SSOT
    # (三層命中 + 兩道否決),見本檔頂部 `classify_systemic`。

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
            _n_entries = len(getattr(d, "entries", []) or [])
            _n_sys = 0
            for entry in d.entries:
                if count >= max_per_feed:
                    break
                title   = getattr(entry, "title", "")
                summary = getattr(entry, "summary", "")[:300]
                url     = getattr(entry, "link", "")
                pub     = getattr(entry, "published", "")[:25]

                text_check = (title + " " + summary).lower()
                # 2026-08-05 稽核:systemic 判定改走三層 + 兩道否決(見 classify_systemic)
                _is_sys, _sys_ev = classify_systemic(title, summary)
                _is_fin = any(kw.lower() in text_check for kw in KEYWORDS)
                # 稽核要求(必修 1-5):把「命中的標題 + 命中詞」印出來,讓下次跑一次
                # 就能 100% 收斂判斷鏈 —— 上一輪稽核只握有 BBC World 內容,
                # Yahoo / MarketWatch / CNBC 三個 feed 回 gzip 或空值無法查證。
                if _is_sys:
                    _n_sys += 1
                    print(f"[news/systemic] 🚨 {source_name} | {title[:120]} "
                          f"| 命中: {', '.join(_sys_ev)}")
                elif _sys_ev:
                    # 近失(有候選詞但被領域/方向/規模過濾擋下)→ 也印,才看得出「為什麼沒算」
                    print(f"[news/systemic] ⬜ 未達門檻 {source_name} | {title[:120]} "
                          f"| 證據: {', '.join(_sys_ev)}")
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
            # 每個 feed 的抓取實況(entries=0 即可一眼認出 gzip / 空回應 / 來源死亡)
            print(f"[news/feed] {source_name} entries={_n_entries} "
                  f"kept={count} systemic={_n_sys}")
        except Exception as _e_feed:
            # v18.186：不再靜默 — 累計失敗來源;2026-08-05 補印例外型別(原本吞掉細節)
            print(f"[news/feed] ⚠️ {source_name} 失敗: {type(_e_feed).__name__}: {_e_feed}")
            failed.append(source_name)
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
    # 全批總結:一行看完「幾個 feed 活著 / 收了幾則 / 幾則掛旗標」
    print(f"[news] feeds={len(FEEDS)} failed={failed or '-'} "
          f"kept={len(results)} systemic={len(sys_news)}")
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
