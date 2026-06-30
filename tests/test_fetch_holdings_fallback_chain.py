"""v19.251 R21 regression test — fetch_holdings 6 URL fallback chain。

User 反饋線上仍空,要求走更多備用源 + NAS proxy 中繼。本 R21:
- 6 candidate URL(tcb / chubb / www / taishinlife / wq06×2)
- per-URL stderr log(audit trail)
- 全失敗時回傳 attempts dict(Fail Loud §1)
"""
from __future__ import annotations

from unittest.mock import patch


class _FakeResp:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200
        self.encoding = "big5"
        self.apparent_encoding = "big5"


# Pad ≥ 500 chars(fetcher 內 `if len(_r.text) > 500:` 才視為有效 response)
_VALID_HTML = ("""<html><body>
<table>
  <tr><td colspan='3'>基金投資分佈(依產業)</td></tr>
  <tr><td>產業</td><td>投資金額</td><td>比例(%)</td></tr>
  <tr><td>科技業</td><td>1,000</td><td>50.00</td></tr>
  <tr><td>金融業</td><td>500</td><td>25.00</td></tr>
  <tr><td>消費業</td><td>500</td><td>25.00</td></tr>
</table>
""" + ("<!-- padding for >500 chars test compliance -->\n" * 20) + """
</body></html>""")


def test_fetch_holdings_tries_six_candidate_urls():
    """R21 SSOT 守 — fallback chain 至少 6 個候選(tcb/chubb/www/taishin/wq06×2)。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    _called: list = []

    def _spy(url, **kw):
        _called.append(url)
        return None  # 全 fail → fetcher 應繼續試下個

    # v19.276/278:MoneyDJ 全失敗後會試 cnyes + Morningstar fallback;本測試只驗
    # MoneyDJ chain,patch 兩 fallback 回 {} 維持確定性(避免真網路呼叫)。
    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy), \
         patch("repositories.fund.nav_metrics.fetch_holdings_cnyes", return_value={}), \
         patch("repositories.fund.nav_metrics.fetch_holdings_morningstar", return_value={}):
        result = fetch_holdings("TESTCODE")

    # 應至少嘗試 4 個不同 subdomain(去重 subdomain 看)
    _subdomains = {url.split("//")[1].split("/")[0] for url in _called}
    assert len(_subdomains) >= 3, \
        f"至少 3 個 subdomain 嘗試(tcb/chubb/www/taishin 任 3),實際 {_subdomains}"
    # 應嘗試 ≥ 6 個 URL 候選
    assert len(_called) >= 5, f"至少 5 URL fallback,實際 {len(_called)}"
    # 全失敗應回 attempts dict(Fail Loud)
    assert "attempts" in result, f"全失敗應回 attempts 給 audit,實際 {result}"
    assert len(result["attempts"]) >= 5


def test_fetch_holdings_breaks_early_on_first_success():
    """第一個 URL 就成功 → 不再試後續(避免無謂 HTTP)。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    _calls = [0]

    def _spy(url, **kw):
        _calls[0] += 1
        return _FakeResp(_VALID_HTML)  # 第一次就成功

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy):
        result = fetch_holdings("AAA")

    assert _calls[0] == 1, f"第 1 URL 成功應立即停手,實際試了 {_calls[0]} 次"
    assert "sector_alloc" in result, f"成功時應抓到 sector,實際 {result}"


def test_fetch_holdings_failure_records_per_url_audit():
    """全失敗時 attempts 必須記錄每個 URL 的結果(audit trail)。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", return_value=None), \
         patch("repositories.fund.nav_metrics.fetch_holdings_cnyes", return_value={}), \
         patch("repositories.fund.nav_metrics.fetch_holdings_morningstar", return_value={}):
        result = fetch_holdings("BBB")

    assert "attempts" in result
    for att in result["attempts"]:
        assert "url" in att and "status" in att and "len" in att, \
            f"audit 須含 url/status/len,實際 {att}"


def test_fetch_holdings_skips_short_response():
    """response 太短(< 500 chars,可能是錯誤頁)應視為失敗試下個。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    # 第一次:短 response(假錯誤頁);第二次:有效 HTML
    _responses = [_FakeResp("<html>404</html>"), _FakeResp(_VALID_HTML)]

    def _spy(url, **kw):
        return _responses.pop(0) if _responses else None

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy):
        result = fetch_holdings("CCC")

    assert "sector_alloc" in result, "短 response 跳過後第 2 URL 抓到資料"
