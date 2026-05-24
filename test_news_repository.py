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
    """命中後 systemic（戰爭）永遠排在一般財經之前。"""
    fake = _fake_feedparser([
        _entry("Fed signals possible rate cut", "inflation cooling"),
        _entry("Russia invasion escalates", "war", published="2026-05-23"),
    ])
    with patch.dict(sys.modules, {"feedparser": fake}), \
         patch("infra.proxy.fetch_url", return_value=_Resp()):
        out = fetch_market_news()
    assert len(out) == 2                      # 跨 11 feed 去重後留 2
    assert out[0]["is_systemic"] is True
    assert ("invasion" in out[0]["title"].lower()
            or "russia" in out[0]["title"].lower())
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
    filter_news_by_keywords,
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


# ── v18.205 個股新聞面：filter_news_by_keywords ──

def test_filter_news_by_keywords_matches_any():
    news = [
        {"title": "Apple unveils new chip", "summary": "tech", "is_systemic": False},
        {"title": "Fed holds rates steady", "summary": "macro", "is_systemic": False},
        {"title": "台積電 法說會超預期", "summary": "半導體", "is_systemic": False},
    ]
    titles = [n["title"] for n in filter_news_by_keywords(news, ["Apple", "台積電"])]
    assert "Apple unveils new chip" in titles
    assert "台積電 法說會超預期" in titles
    assert "Fed holds rates steady" not in titles


def test_filter_news_by_keywords_empty_returns_empty():
    news = [{"title": "x", "summary": "", "is_systemic": False}]
    assert filter_news_by_keywords(news, []) == []
    assert filter_news_by_keywords(news, None) == []


def test_filter_news_by_keywords_no_match_no_fallback():
    """個股無命中 → 回空（不像 asset_class 會 fallback 全部）。"""
    news = [{"title": "Fed holds rates", "summary": "macro", "is_systemic": False}]
    assert filter_news_by_keywords(news, ["NVIDIA"]) == []
