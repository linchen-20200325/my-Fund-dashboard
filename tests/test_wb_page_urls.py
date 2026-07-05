"""回歸網 — v19.310 Bug B:MoneyDJ wb01/wb07 候選 URL 須依保單代碼前綴展開子網域。

真 bug(user 貼健診表):`fetch_performance_wb01`(wb01=3Y/5Y 績效)/
`fetch_risk_metrics`(wb07=Sortino/Calmar/同儕排名)原本只試 `tcbbankfund` +
`www.moneydj.com` 兩個 host → **非合庫的保單基金**(JF/TL/ANZ/FL 前綴 + 走安達/Chubb
平台的 AC* 代碼)全 miss,連鎖讓健診 4 表的多年期/進階欄位全空。

`_wb_page_urls` 比照已驗證的 `fetch_holdings`(nav_metrics.py L906+)展開子網域:
基線 host(tcbbankfund/chubb/taishinlife + www)+ `_INSURANCE_SUBDOMAIN_HINTS` 前綴 portal,
路徑用 tcbbankfund 既有 proven 的 `/w/wb/{page}.djhtm`(www 走 `/yp/`)。

本檔守:展開後 URL 清單含正確 host + page,不重複,空代碼不炸。
"""
from __future__ import annotations

from repositories.fund.nav_metrics import _wb_page_urls


def test_baseline_hosts_always_present():
    """基線 host(tcbbankfund/chubb/www)對任何代碼都在 —— AC* 保單常走安達/Chubb 平台。"""
    urls = _wb_page_urls("ACTI71", "wb01")
    joined = " ".join(urls)
    assert "tcbbankfund.moneydj.com" in joined
    assert "chubb.moneydj.com" in joined
    assert "www.moneydj.com" in joined


def test_page_name_in_every_url():
    for page in ("wb01", "wb07"):
        urls = _wb_page_urls("JFZN3", page)
        assert urls, "URL 清單不可為空"
        assert all(f"{page}.djhtm" in u for u in urls), f"{page} 應出現在每個 URL"


def test_jf_prefix_expands_jpmorgan_portal():
    """JF 前綴 → jpmorgan/jpmf portal 子網域(_INSURANCE_SUBDOMAIN_HINTS)。"""
    joined = " ".join(_wb_page_urls("JFZN3", "wb07"))
    assert "jpmorgan.moneydj.com" in joined


def test_tl_prefix_expands_tlife_portal():
    joined = " ".join(_wb_page_urls("TLZF9", "wb01"))
    assert "tlife.moneydj.com" in joined


def test_anz_and_fl_prefixes_expand():
    assert "anz.moneydj.com" in " ".join(_wb_page_urls("ANZ89", "wb01"))
    assert "franklintem.moneydj.com" in " ".join(_wb_page_urls("FLFM1", "wb07"))


def test_no_duplicate_urls():
    urls = _wb_page_urls("JFZN3", "wb01")
    assert len(urls) == len(set(urls)), "候選 URL 不應重複(host 去重保序)"


def test_empty_code_does_not_crash():
    urls = _wb_page_urls("", "wb01")
    assert urls  # 基線 host 仍在,不因空代碼回空清單
    assert all("wb01.djhtm" in u for u in urls)


def test_proven_path_pattern_on_subdomain():
    """子網域走 proven 的 /w/wb/ 路徑,www 走 /yp/(既有 pattern,不發明 URL)。"""
    urls = _wb_page_urls("JFZN3", "wb01")
    assert any(u.startswith("https://tcbbankfund.moneydj.com/w/wb/wb01.djhtm") for u in urls)
    assert any(u.startswith("https://www.moneydj.com/funddj/yp/wb01.djhtm") for u in urls)
