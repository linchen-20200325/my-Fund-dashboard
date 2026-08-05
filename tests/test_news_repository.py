"""test_news_repository — v18.186 RSS 走 NAS Proxy + 友善空狀態

沙箱沒裝 feedparser、也不能連網，故用「假 feedparser 模組」+ mock
`infra.proxy.fetch_url` 驗證三條分支：全失敗 / 無命中 / 正常（systemic 排前）。
"""
from __future__ import annotations

import sys
import types
from unittest.mock import patch

from repositories.news_repository import fetch_market_news


def _fake_feedparser(entries: list):
    m = types.ModuleType("feedparser")
    m.parse = lambda *a, **k: types.SimpleNamespace(entries=entries)
    return m


def _entry(title, summary="", link="http://x", published="2026-05-24"):
    return types.SimpleNamespace(
        title=title, summary=summary, link=link, published=published,
    )


class _Resp:
    content = b"<rss></rss>"


def test_news_all_feeds_fail_returns_friendly_proxy_message():
    """所有來源無回應（Proxy 斷）→ 回 1 筆友善 ⚠️ 提示，不再靜默回空。"""
    with patch.dict(sys.modules, {"feedparser": _fake_feedparser([])}), \
         patch("infra.proxy.fetch_url", return_value=None):
        out = fetch_market_news()
    assert len(out) == 1
    assert out[0]["source"] == "system"
    assert out[0]["title"].startswith("⚠️")
    assert "無回應" in out[0]["summary"]


def test_news_fetched_but_no_keyword_match_returns_info_message():
    """抓得到但無命中關鍵字 → 回 ℹ️ 提示（與 Proxy 斷區分）。"""
    fake = _fake_feedparser([_entry("Cute cat video goes viral", "just a cat")])
    with patch.dict(sys.modules, {"feedparser": fake}), \
         patch("infra.proxy.fetch_url", return_value=_Resp()):
        out = fetch_market_news()
    assert len(out) == 1
    assert out[0]["title"].startswith("ℹ️")


def test_news_systemic_ranked_first():
    """命中後 systemic（戰爭 × 金融）永遠排在一般財經之前。

    2026-08-05 稽核後 summary 由 "war" 改為含金融詞的句子 —— 新規則要求
    地緣詞**必須與金融詞共現**（原本裸 "war" 就成立正是假警報來源）。
    """
    fake = _fake_feedparser([
        _entry("Fed signals possible rate cut", "inflation cooling"),
        _entry("Invasion escalates as global stocks plunge",
               "war sends bond markets into disarray", published="2026-05-23"),
    ])
    with patch.dict(sys.modules, {"feedparser": fake}), \
         patch("infra.proxy.fetch_url", return_value=_Resp()):
        out = fetch_market_news()
    assert len(out) == 2                      # 跨 5 feed 去重後留 2
    assert out[0]["is_systemic"] is True
    assert "invasion" in out[0]["title"].lower()
    assert out[1]["is_systemic"] is False


def test_news_routes_through_proxy_fetch_url():
    """確認真的有走 infra.proxy.fetch_url（而非 feedparser 裸連 URL）。"""
    fake = _fake_feedparser([_entry("Fed rate decision", "inflation")])
    with patch.dict(sys.modules, {"feedparser": fake}), \
         patch("infra.proxy.fetch_url", return_value=_Resp()) as _mock:
        fetch_market_news()
    assert _mock.called
    # 第一個位置參數應為 feed URL，且有帶 timeout
    assert _mock.call_args_list[0].args[0].startswith("http")
    assert _mock.call_args_list[0].kwargs.get("timeout")


# ── v18.196 Task3：依資產類別過濾 ──
from repositories.news_repository import (  # noqa: E402
    filter_news_by_asset_class,
    infer_asset_class,
)


def test_infer_asset_class_basic():
    assert infer_asset_class("安聯台灣大壩股票基金") == "stock"
    assert infer_asset_class("聯博全球高收益債券基金") == "bond"
    assert infer_asset_class("某某原油能源基金") == "commodity"
    assert infer_asset_class("多重資產收益組合") == "macro"   # 無命中 → macro
    assert infer_asset_class("") == "macro"


def test_filter_news_by_asset_class_filters_and_keeps_systemic():
    news = [
        {"title": "Treasury yields rise", "summary": "bond market", "is_systemic": False},
        {"title": "S&P 500 hits record", "summary": "stocks", "is_systemic": False},
        {"title": "War escalates", "summary": "", "is_systemic": True},
    ]
    titles = [n["title"] for n in filter_news_by_asset_class(news, "bond")]
    assert "Treasury yields rise" in titles
    assert "War escalates" in titles            # systemic 永遠保留
    assert "S&P 500 hits record" not in titles


def test_filter_macro_or_empty_returns_all():
    news = [{"title": "x", "summary": "", "is_systemic": False}]
    assert filter_news_by_asset_class(news, "macro") == news
    assert filter_news_by_asset_class(news, "") == news


def test_filter_empty_result_falls_back_to_all():
    news = [{"title": "cat video goes viral", "summary": "", "is_systemic": False}]
    assert filter_news_by_asset_class(news, "bond") == news   # 過濾後空 → 回原


def test_filter_chinese_alias_fx():
    news = [{"title": "美元走強", "summary": "匯率走勢", "is_systemic": False},
            {"title": "台股大漲", "summary": "股市", "is_systemic": False}]
    out = filter_news_by_asset_class(news, "匯")     # 中文別名 → fx
    assert any("美元" in n["title"] for n in out)
    assert all("台股" not in n["title"] for n in out)


def test_fetch_macro_news_fetches_then_filters(monkeypatch):
    import repositories.news_repository as nr
    fake = [{"title": "Treasury yields", "summary": "bond", "is_systemic": False},
            {"title": "Nasdaq up", "summary": "stocks", "is_systemic": False}]
    monkeypatch.setattr(nr, "fetch_market_news", lambda max_per_feed=5: fake)
    out = nr.fetch_macro_news("bond")
    assert [n["title"] for n in out] == ["Treasury yields"]








def test_fetch_stock_news_parses_entries():
    import repositories.news_repository as nr
    fake = _fake_feedparser([
        _entry("台積電法說會超預期", "半導體"),
        _entry("台積電擴廠計畫", ""),
    ])
    with patch.dict(sys.modules, {"feedparser": fake}), \
         patch("infra.proxy.fetch_url", return_value=_Resp()):
        out = nr.fetch_stock_news("台積電", max_items=3)
    assert len(out) == 2
    assert out[0]["title"].startswith("台積電")
    assert out[0]["url"].startswith("http")
    assert out[0]["source"]            # 預設 Google News


def test_fetch_stock_news_empty_query_returns_empty():
    import repositories.news_repository as nr
    assert nr.fetch_stock_news("") == []
    assert nr.fetch_stock_news("  ") == []


def test_fetch_stock_news_fetch_fail_returns_empty():
    import repositories.news_repository as nr
    with patch.dict(sys.modules, {"feedparser": _fake_feedparser([])}), \
         patch("infra.proxy.fetch_url", return_value=None):
        assert nr.fetch_stock_news("台積電") == []


def test_fetch_stock_news_respects_max_items():
    import repositories.news_repository as nr
    fake = _fake_feedparser([_entry(f"新聞{i}") for i in range(10)])
    with patch.dict(sys.modules, {"feedparser": fake}), \
         patch("infra.proxy.fetch_url", return_value=_Resp()):
        out = nr.fetch_stock_news("某股", max_items=3)
    assert len(out) == 3


# ══════════════════════════════════════════════════════════════════
# 2026-08-05 稽核 🔴 必修 1 — 系統性風險旗標假警報
#
# 【每條測試在「修正前」會不會紅】
#   下面 TestSystemicFalsePositives 全部 6 條:**修正前會紅**
#     — 舊碼是「~60 個單詞任一子字串命中即 True」,這 6 則稽核實抓的 BBC World
#       標題在舊碼下全部回 True(正是畫面上那「🔴 6 則系統性風險」)。
#   TestSystemicTruePositives:修正前**會綠**(舊碼也會判 True)。
#     保留理由:它們是「不可回退的保護網」—— 防止我們把過濾收太緊、
#     連真的銀行擠兌/戰爭衝擊市場都漏掉。
#   TestSystemicKeywordDrift:**修正前會紅**(舊表確實含裸國名與 geopolitical/rout/…)。
#   test_five_bucket_count_matches_low_risk_banner:**修正前會紅**
#     — 這條是端到端接線測試(PROCESS.md §4):它不測 classify_systemic 本身,
#       而是測「production 消費端真的數出 0 則」。若有人把 classify_systemic
#       改對了卻沒接進 fetch_market_news(算對了但沒接出去),這條會紅。
# ══════════════════════════════════════════════════════════════════
from repositories.news_repository import classify_systemic  # noqa: E402


# 稽核 2026-08-04~05 實抓 BBC World / 財經 feed 的真實標題(非杜撰)
_AUDIT_FALSE_POSITIVES = [
    ("Ukraine hits more Wildberries sites as strike kills five", ""),
    ("EU commends Spain's 'swift response' to Ceuta migrant crisis", ""),
    ("France wildfires reveal hundreds of WW2 shells", ""),
    ("What will happen when a SpaceX rocket collides with the Moon?", ""),
    ("BP posts 143% profit hike as Iran war sends oil and gas prices skyward", ""),
    ("Hormuz blockade eases as ceasefire deal reached; oil prices slide", ""),
]


class TestSystemicFalsePositives:
    """稽核實測的 6 則假警報 —— 全部必須是 False。"""

    def test_bare_country_name_no_longer_flags(self):
        ok, ev = classify_systemic(_AUDIT_FALSE_POSITIVES[0][0])
        assert ok is False, f"裸國名不應觸發系統性旗標;evidence={ev}"

    def test_non_financial_domain_no_longer_flags(self):
        for _t, _s in _AUDIT_FALSE_POSITIVES[1:4]:
            ok, ev = classify_systemic(_t, _s)
            assert ok is False, f"非金融領域不應觸發:{_t} / evidence={ev}"

    def test_benign_earnings_framing_vetoed(self):
        """「BP 財報大勝」實質是獲利新聞,即使句中含 iran + war + oil。"""
        ok, ev = classify_systemic(_AUDIT_FALSE_POSITIVES[4][0])
        assert ok is False
        assert any(e.startswith("veto-benign") for e in ev), ev

    def test_deescalation_vetoed(self):
        """停火 / 達成協議 = 緩和,不是升級(舊碼把緩和讀成升級)。"""
        ok, ev = classify_systemic(_AUDIT_FALSE_POSITIVES[5][0])
        assert ok is False
        assert any(e.startswith("veto-deescalation") for e in ev), ev

    def test_word_boundary_no_substring_hit(self):
        """舊碼裸 `in` 會讓 "war" 命中 "warning" / "forward"。"""
        ok, ev = classify_systemic("Fed issues warning on forward guidance", "")
        assert ok is False, ev

    def test_small_scale_bankruptcy_filtered(self):
        """規模過濾:小公司破產不是系統性事件(有金融詞、但無規模詞)。"""
        ok, ev = classify_systemic(
            "Small startup files for bankruptcy, investors lose stake", "")
        assert ok is False
        assert any("無規模詞" in e for e in ev), ev

    def test_evidence_always_returned_for_near_miss(self):
        """近失也要留證據(§2.2 血緣;讓 log 一次看完為什麼沒算)。"""
        _, ev = classify_systemic(_AUDIT_FALSE_POSITIVES[4][0])
        assert ev, "近失必須回傳證據,否則 log 無法收斂判斷鏈"


class TestSystemicTruePositives:
    """保護網:真的系統性事件不能因為過濾收緊而漏掉。"""

    def test_direct_bank_run(self):
        ok, ev = classify_systemic(
            "Bank run at regional lender forces emergency deposit guarantee", "")
        assert ok is True and any(e.startswith("L1") for e in ev), ev

    def test_direct_contagion(self):
        ok, _ = classify_systemic(
            "Global banks face contagion risk as credit spreads blow out", "")
        assert ok is True

    def test_geo_with_financial_cooccurrence(self):
        ok, ev = classify_systemic(
            "War escalates; global stock markets plunge and oil spikes", "")
        assert ok is True and any(e.startswith("L2") for e in ev), ev

    def test_large_scale_distress(self):
        ok, ev = classify_systemic(
            "Major bank collapses, billions in customer deposits frozen", "")
        assert ok is True and any(e.startswith("scale") for e in ev), ev

    def test_chinese_direct(self):
        ok, _ = classify_systemic("全球銀行擠兌恐引發金融危機", "")
        assert ok is True


class TestSystemicKeywordDrift:
    """SSOT 漂移鎖:被稽核點名移除的詞不得回流到任何一組表。"""

    def test_removed_terms_absent_everywhere(self):
        import repositories.news_repository as nr
        _banned = {"ukraine", "russia", "israel", "gaza", "iran",
                   "geopolitical", "rout", "selloff", "sanctions"}
        _all = (nr.SYSTEMIC_DIRECT_KEYWORDS
                | nr.SYSTEMIC_ESCALATION_KEYWORDS
                | nr.SYSTEMIC_DISTRESS_KEYWORDS)
        assert not (_banned & set(_all)), (
            f"稽核點名移除的詞回流:{_banned & set(_all)}")

    def test_geo_terms_require_financial_context(self):
        """地緣詞單獨出現(無金融詞)一律不成立 —— 這是 AND 規則的核心。"""
        for _kw in ("war", "invasion", "blockade", "missile strike"):
            ok, _ = classify_systemic(f"Report on {_kw} in remote region", "")
            assert ok is False, f"{_kw} 單獨出現不應成立"


def test_five_bucket_count_matches_low_risk_banner():
    """端到端接線:6 則稽核真實標題進 fetch_market_news → systemic 計數必須是 0。

    這條刻意**不呼叫 classify_systemic**,而是走 production 路徑,對齊
    `ui/helpers/macro/beginner_view.compute_five_bucket_summary` 的數法
    (`sum(1 for n in news if n.get("is_systemic"))`)。
    若 classify_systemic 改對了但沒接進 fetch_market_news(PROCESS.md §4
    「算對了但沒接出去」),這條會紅、而純函式測試仍會綠。
    """
    fake = _fake_feedparser([_entry(t, s) for t, s in _AUDIT_FALSE_POSITIVES])
    with patch.dict(sys.modules, {"feedparser": fake}), \
         patch("infra.proxy.fetch_url", return_value=_Resp()):
        out = fetch_market_news()
    _sys_count = sum(1 for n in out if n.get("is_systemic"))
    assert _sys_count == 0, (
        "頂端 banner ✅ LOW 與五桶卡 🔴 系統性警報自相矛盾的根因:"
        f"實際數出 {_sys_count} 則 / "
        f"{[n['title'] for n in out if n.get('is_systemic')]}")
