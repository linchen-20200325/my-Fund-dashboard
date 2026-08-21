"""v19.500:fetch_holdings 兩變體都試(修 ACCP138/ALZF9/PYZW3 持股全空)。

根因:原 `_hold_page = yp013000 if domestic else yp013001` 只試一個變體、永不 fallback,
而 prefix 分類對組合/保單基金會猜錯(ACCP∈_DOMESTIC_PREFIXES→yp013000,但實際持股頁
確認為 yp013001,見 test_fetch_holdings_multi_asset)。NAV 早就兩頁都試,持股卻只試一個。
修:兩變體都建 URL(primary 排前、命中即 break),provenance 記實際命中的頁。
"""
from __future__ import annotations

from unittest.mock import patch


class _FakeResp:
    def __init__(self, text: str):
        self.text = text
        self.status_code = 200
        self.encoding = "big5"


_HOLDINGS_HTML = """<html><body>
<table>
  <tr><td colspan='3'>基金投資分佈(依產業)</td></tr>
  <tr><td>產業</td><td>投資金額(以萬元)</td><td>比例(%)</td></tr>
  <tr><td>資訊科技</td><td>619,378.80</td><td>26.69</td></tr>
  <tr><td>工業</td><td>372,464.30</td><td>12.03</td></tr>
  <tr><td>通訊服務</td><td>341,076.80</td><td>11.55</td></tr>
</table>
<table>
  <tr><td colspan='3'>基金前十大持股</td></tr>
  <tr><td>投資名稱</td><td>產業</td><td>比例(%)</td></tr>
  <tr><td>NVIDIA CORP</td><td>資訊科技</td><td>2.81</td></tr>
  <tr><td>APPLE INC</td><td>資訊科技</td><td>2.44</td></tr>
</table>
</body></html>""" + "<!-- pad -->" * 60      # 撐過 len>500 門檻


def _urls_tried(code: str) -> list:
    """spy fetch_url_with_retry,全失敗 → 收集所有嘗試 URL。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()
    called: list = []
    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               side_effect=lambda url, **kw: called.append(url) or None):
        fetch_holdings(code)
    return called


# ── 兩變體都試 ──────────────────────────────────────────────────────────
def test_accp138_tries_both_yp013_variants():
    """ACCP138(prefix 判境內→primary yp013000),但也必須試 yp013001(真實持股頁)。"""
    urls = _urls_tried("ACCP138")
    assert any("yp013000" in u for u in urls), "須含境內變體 yp013000"
    assert any("yp013001" in u for u in urls), "★ 修正重點:也須試境外變體 yp013001"


def test_offshore_code_tries_both_too():
    """ALZF9(prefix 判境外→primary yp013001),也必須試 yp013000。"""
    urls = _urls_tried("ALZF9")
    assert any("yp013001" in u for u in urls)
    assert any("yp013000" in u for u in urls), "★ 反向也要 fallback 到另一變體"


# ── happy-path:primary 變體排前(命中即停 → 無延遲回歸)──────────────────
def test_primary_variant_urls_come_first():
    """境內判定 → 首個 yp013 URL 應是 yp013000(primary);境外判定 → yp013001。"""
    # ACCP138 判境內 → primary yp013000 先
    urls_dom = [u for u in _urls_tried("ACCP138") if "yp013" in u]
    assert "yp013000" in urls_dom[0], f"境內 primary 應排首,實際 {urls_dom[0]}"
    # ALZF9 判境外 → primary yp013001 先
    urls_off = [u for u in _urls_tried("ALZF9") if "yp013" in u]
    assert "yp013001" in urls_off[0], f"境外 primary 應排首,實際 {urls_off[0]}"


# ── provenance 記實際命中的頁(非 primary 猜測)────────────────────────────
def test_provenance_reflects_winning_variant():
    """ACCP138 primary=yp013000 全 miss、yp013001 命中 → source 應記 yp013001。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    def _spy(url, **kw):
        # 只有 yp013001 頁回真實 HTML;yp013000 / wq06 全 miss
        if "yp013001" in url:
            return _FakeResp(_HOLDINGS_HTML)
        return None

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy):
        out = fetch_holdings("ACCP138")

    assert out.get("top_holdings") or out.get("sector_alloc"), "應解析出持股/產業"
    assert out.get("source") == "MoneyDJ:yp:yp013001", \
        f"provenance 應記實際命中頁 yp013001,實際 {out.get('source')}"


def test_winning_page_parses_holdings():
    """命中頁能解析出 NVIDIA/APPLE 前十大 + 產業分布。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()
    with patch("repositories.fund.nav_metrics.fetch_url_with_retry",
               side_effect=lambda url, **kw: _FakeResp(_HOLDINGS_HTML)):
        out = fetch_holdings("ALZF9")
    _names = {h.get("name", "") for h in (out.get("top_holdings") or [])}
    assert any("NVIDIA" in n for n in _names)
    _sectors = {s.get("name", "") for s in (out.get("sector_alloc") or [])}
    assert any("資訊科技" in s for s in _sectors)
