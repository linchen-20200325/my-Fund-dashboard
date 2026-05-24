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
