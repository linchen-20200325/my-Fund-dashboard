"""v19.192 regression — AAII fetch fallback chain。

User 螢幕截圖回報 AAII 情緒「待取得 ❌ fetch_url 回 None」。
單一 URL 沒 fallback → Cloudflare 擋一次就全黑。

守住:
- 首 URL 成功 → 不打第 2/3(快速路徑保留)
- 首 URL 401/403/500/None → 自動回退第 2 URL
- 全 3 URL 失敗 → _err 帶完整 trace(每段失敗原因)
- 失敗 trace 與成功路徑都帶 provenance(source / fetched_at)
- 成功 dict 帶 url_used 欄(audit trail)
"""
from __future__ import annotations

from unittest.mock import patch

import pytest


class _MockResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


_GOOD_HTML = "<p>Bullish 35.0%</p><p>Bearish 30.0%</p>"


def _clear():
    from repositories.macro_repository import fetch_aaii_sentiment
    fetch_aaii_sentiment.cache_clear()


class TestFallbackChainFirstUrlSuccessV192:
    def test_first_url_success_no_retry(self):
        """首 URL 命中 → fetch_url 只被叫 1 次,不浪費後續 URL。"""
        _clear()
        from repositories import macro_repository as mr
        with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, _GOOD_HTML)) as mock_fu:
            r = mr.fetch_aaii_sentiment()
        assert "_err" not in r
        assert r["value"] == pytest.approx(5.0)
        assert r["url_used"] == mr.AAII_FALLBACK_URLS[0]
        assert mock_fu.call_count == 1, (
            "首 URL 成功時必須短路後續 URL,實際打了 "
            f"{mock_fu.call_count} 次"
        )

    def test_success_carries_provenance(self):
        _clear()
        from repositories import macro_repository as mr
        with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, _GOOD_HTML)):
            r = mr.fetch_aaii_sentiment()
        assert r["source"].startswith("AAII"), "F-PROV-1 source 必須帶 AAII"
        assert "fetched_at" in r, "F-PROV-1 fetched_at 必須帶"


class TestFallbackChainRecoversFromFirstFailV192:
    def test_first_403_falls_back_to_second(self):
        """首 URL 403(Cloudflare)→ 第 2 URL 接手成功。"""
        _clear()
        from repositories import macro_repository as mr
        responses = [_MockResp(403), _MockResp(200, _GOOD_HTML), _MockResp(200, _GOOD_HTML)]
        with patch("repositories.macro.alternate.fetch_url", side_effect=responses) as mock_fu:
            r = mr.fetch_aaii_sentiment()
        assert "_err" not in r, "第 2 URL 接得到應視為成功"
        assert r["url_used"] == mr.AAII_FALLBACK_URLS[1]
        assert mock_fu.call_count == 2, "第 2 URL 成功應停手不打第 3"

    def test_first_none_falls_back(self):
        """首 URL fetch_url 回 None(proxy 失敗)→ 第 2 URL 接手。"""
        _clear()
        from repositories import macro_repository as mr
        responses = [None, _MockResp(200, _GOOD_HTML), _MockResp(200, _GOOD_HTML)]
        with patch("repositories.macro.alternate.fetch_url", side_effect=responses):
            r = mr.fetch_aaii_sentiment()
        assert "_err" not in r
        assert r["bull"] == 35.0

    def test_first_two_fail_third_recovers(self):
        """首 2 URL 全失敗 → 第 3 URL 拯救(URL fallback chain 完整覆蓋)。"""
        _clear()
        from repositories import macro_repository as mr
        responses = [_MockResp(403), None, _MockResp(200, _GOOD_HTML)]
        with patch("repositories.macro.alternate.fetch_url", side_effect=responses) as mock_fu:
            r = mr.fetch_aaii_sentiment()
        assert "_err" not in r
        assert r["url_used"] == mr.AAII_FALLBACK_URLS[2]
        assert mock_fu.call_count == 3


class TestFallbackChainAllFailFailLoudV192:
    """§1 Fail Loud — 全失敗時必須回 _err,trace 帶完整三段。"""

    def test_all_three_403(self):
        _clear()
        from repositories import macro_repository as mr
        with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(403)):
            r = mr.fetch_aaii_sentiment()
        assert "_err" in r
        assert "全失敗" in r["_err"]
        # trace 必須有 3 段(每段都帶 HTTP 403)
        assert r["_err"].count("HTTP 403") == 3, (
            f"trace 應記錄 3 段 HTTP 403,實際 _err={r['_err']!r}"
        )
        # F-PROV-1:_err 路徑也要帶 source + fetched_at
        assert r["source"].startswith("AAII")
        assert "fetched_at" in r

    def test_all_three_none(self):
        """所有 URL 都 fetch_url 回 None → _err 含 fetch_url None × 3。"""
        _clear()
        from repositories import macro_repository as mr
        with patch("repositories.macro.alternate.fetch_url", return_value=None):
            r = mr.fetch_aaii_sentiment()
        assert "_err" in r
        assert "全失敗" in r["_err"]
        assert r["_err"].count("None") == 3

    def test_mixed_failures_trace_all_segments(self):
        """403 → None → regex no match,_err trace 必須含全部三段症狀。"""
        _clear()
        from repositories import macro_repository as mr
        responses = [_MockResp(403), None, _MockResp(200, "<html>blank</html>")]
        with patch("repositories.macro.alternate.fetch_url", side_effect=responses):
            r = mr.fetch_aaii_sentiment()
        assert "_err" in r
        assert "403" in r["_err"]
        assert "None" in r["_err"]
        assert "regex" in r["_err"]


class TestFetcherUsesBrowserHeadersV192:
    """v19.192 strengthened headers:完整 Chrome UA + Accept,降低 Cloudflare bot 判定機率。"""

    def test_browser_headers_passed_to_fetch_url(self):
        _clear()
        from repositories import macro_repository as mr
        with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, _GOOD_HTML)) as mock_fu:
            mr.fetch_aaii_sentiment()
        # fetch_url 必須以 headers=AAII_BROWSER_HEADERS 呼叫
        _, kwargs = mock_fu.call_args
        assert kwargs.get("headers") is not None, (
            "v19.192:必須帶完整 Chrome UA + Accept headers,Cloudflare 才不會直接 403"
        )
        ua = kwargs["headers"]["User-Agent"]
        assert "Chrome/" in ua, f"UA 必須帶 Chrome 版本(防 Cloudflare bot),實際: {ua!r}"
        assert "Safari/" in ua, "UA 必須帶 Safari engine 標記"

    def test_timeout_extended_for_nas_relay(self):
        """v19.192:timeout 8→20 配合 NAS Squid 中繼 + Cloudflare challenge 較長 RTT。"""
        _clear()
        from repositories import macro_repository as mr
        with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, _GOOD_HTML)) as mock_fu:
            mr.fetch_aaii_sentiment()
        _, kwargs = mock_fu.call_args
        assert kwargs.get("timeout", 0) >= 15, (
            f"v19.192:timeout 須 ≥15s 配合 NAS 中繼,實際 {kwargs.get('timeout')}"
        )


class TestBackwardCompatV192:
    """v19.192 不能破壞既有 caller 介面(services.us_liquidity_engine._aaii_with_judgment)。"""

    def test_services_layer_still_reads_value_and_unit(self):
        _clear()
        from repositories import macro_repository as mr
        from services import us_liquidity_engine as ule
        with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, _GOOD_HTML)):
            ule.fetch_aaii_sentiment.cache_clear()
            r = ule._aaii_with_judgment()
        assert "value" in r
        assert r.get("unit") == "%"
        assert "label" in r and "color" in r, "L2 service 必須補上 label/color"
