"""v19.252 R22 regression — fetch_holdings 依 _INSURANCE_SUBDOMAIN_HINTS 展開 portal。

User 反饋:R21 6-URL chain 對保險平台代碼(JFZN3/TLZF9/FLFM1 等)仍空。
本 R22 比照 _src_insurance_subdomain_nav 模式,依代碼前綴從
_INSURANCE_SUBDOMAIN_HINTS 展開 portal 子網域(JF→jpmorgan/jpmf/jpmfund 等),
套到 yp013xxx + wq06 兩頁,讓 fallback chain 自動 cover 保險平台代碼。
"""
from __future__ import annotations

from unittest.mock import patch


def test_fetch_holdings_expands_jf_prefix_to_jpmorgan_subdomains():
    """JF 前綴(如 JFZN3)應展開到 jpmorgan/jpmf/jpmfund 子網域。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    _called: list = []

    def _spy(url, **kw):
        _called.append(url)
        return None  # 全失敗 → fetcher 應繼續試完所有候選

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy):
        fetch_holdings("JFZN3")

    _subdomains = {url.split("//")[1].split("/")[0] for url in _called}
    # JF prefix → ["jpmorgan", "jpmf", "jpmfund"] 必須出現於 chain
    assert "jpmorgan.moneydj.com" in _subdomains, \
        f"JF→jpmorgan portal 必須加入 fallback chain,實際 {_subdomains}"
    assert "jpmf.moneydj.com" in _subdomains, \
        f"JF→jpmf portal 必須加入 fallback chain,實際 {_subdomains}"
    assert "jpmfund.moneydj.com" in _subdomains, \
        f"JF→jpmfund portal 必須加入 fallback chain,實際 {_subdomains}"


def test_fetch_holdings_expands_tl_prefix_to_taiwanlife_subdomains():
    """TL 前綴(如 TLZF9)應展開到 tlife/twlife/taiwanlife/tlins/tlinsfund 子網域。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    _called: list = []

    def _spy(url, **kw):
        _called.append(url)
        return None

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy):
        fetch_holdings("TLZF9")

    _subdomains = {url.split("//")[1].split("/")[0] for url in _called}
    # 至少 3 個 TL portal 出現(tlife/twlife/taiwanlife)
    _tl_match = {s for s in _subdomains
                 if any(p in s for p in ("tlife", "twlife", "taiwanlife"))}
    assert len(_tl_match) >= 3, \
        f"TL→tlife/twlife/taiwanlife 至少 3 portal 應出現,實際 {_tl_match}"


def test_fetch_holdings_non_insurance_code_skips_portal_expansion():
    """非保險前綴代碼(如 ACTI71)應只走基線 6 URL,不展開 portal。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    _called: list = []

    def _spy(url, **kw):
        _called.append(url)
        return None

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy):
        fetch_holdings("ACTI71")  # ACTI 不在 _INSURANCE_SUBDOMAIN_HINTS

    # 不應出現任何 insurance portal subdomain
    _insurance_kw = ("jpmorgan", "jpmf", "tlife", "taiwanlife", "franklin",
                     "cathaylife", "ctbclife", "nanshan", "fubonlife", "ing")
    for url in _called:
        for kw in _insurance_kw:
            assert kw not in url, \
                f"ACTI71 非保險前綴,不應展開 {kw} portal,實際出現 {url}"


def test_fetch_holdings_portals_chain_includes_both_yp013_and_wq06():
    """每個 portal 應同時展開 yp013xxx + wq06 兩個頁面(各 1 URL)。"""
    import fund_fetcher  # noqa: F401
    from repositories.fund.nav_metrics import fetch_holdings
    fetch_holdings.cache_clear()

    _called: list = []

    def _spy(url, **kw):
        _called.append(url)
        return None

    with patch("repositories.fund.nav_metrics.fetch_url_with_retry", side_effect=_spy):
        fetch_holdings("JFZN3")

    # jpmorgan portal 應同時有 yp013001 與 wq06
    _jpm_urls = [u for u in _called if "jpmorgan.moneydj.com" in u]
    assert any("yp013001" in u or "yp013000" in u for u in _jpm_urls), \
        f"jpmorgan portal 缺 yp013xxx 頁,實際 {_jpm_urls}"
    assert any("wq06" in u for u in _jpm_urls), \
        f"jpmorgan portal 缺 wq06 頁,實際 {_jpm_urls}"
