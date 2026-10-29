"""DG-2 §10（docs/v2/70 §14 已知缺陷 1～4）解析缺陷：characterization → 修正後鎖定。

第一個 commit 只釘「現況」（缺陷行為）；修正 commit 會把對應斷言翻轉並註明。
無網路：以 monkeypatch 取代 `fetch_url_with_retry`／`_src_cache_files`。
"""
from __future__ import annotations

import pandas as pd
import pytest

_URL_UP = "HTTPS://WWW.MONEYDJ.COM/FUNDDJ/YA/YP010001.DJHTM?A=TLZF9-AL001"
_URL = "https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=TLZF9-AL001"


# ── A. 手動加入把網址整行轉大寫 ───────────────────────────────
def test_A_現況_網址先轉大寫再交給取數_組出a等於HTTPS的網址():
    from repositories.fund.sources import parse_moneydj_input
    from services.moneydj_fetcher import build_moneydj_url
    up = _URL.strip().upper()  # ui/tab3_t7_ledger.py、ui/tab3_portfolio.py 現行寫法
    built = build_moneydj_url(up, "yp010001")  # startswith("http") 大小寫敏感 → 不短路
    assert built.endswith("?a=HTTPS://WWW.MONEYDJ.COM/FUNDDJ/YA/YP010001.DJHTM?A=TLZF9-AL001")
    assert parse_moneydj_input(built)["code"] == "HTTPS"


# ── B. fetch_nav / fetch_div 以後綴當代碼 ─────────────────────
@pytest.fixture
def _nav_spy(monkeypatch):
    from repositories.fund import nav_metrics as nm
    urls, cache_codes = [], []

    def _fake_fetch(url, **kw):
        urls.append(url)
        return None

    def _fake_cache(code):
        cache_codes.append(code)
        return pd.Series(dtype=float)

    monkeypatch.setattr(nm, "fetch_url_with_retry", _fake_fetch)
    monkeypatch.setattr(nm, "_src_cache_files", _fake_cache)
    return nm, urls, cache_codes


def _fresh(fn):
    fn = getattr(fn, "__wrapped__", fn)
    return fn


def test_B_現況_fetch_nav_以後綴AL001當代碼(_nav_spy):
    nm, urls, cache_codes = _nav_spy
    nm.fetch_nav("TLZF9-AL001")
    assert any(u.endswith("yp004001.djhtm?a=AL001") for u in urls)
    assert cache_codes == ["AL001"]


def test_B_現況_fetch_div_以後綴AL001當代碼(_nav_spy):
    nm, urls, _ = _nav_spy
    nm.fetch_div("TLZF9-AL001")
    assert any(u.endswith("yp004003.djhtm?a=AL001") for u in urls)


# ── C. policy v1 _extract_code_from_url ───────────────────────
@pytest.mark.parametrize("raw,expected", [
    (_URL + "#frag", "TLZF9-AL001#FRAG"),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm?area=TW&a=TLZF9-AL001", "TW"),
])
def test_C_現況_缺陷輸入(raw, expected):
    from repositories.policy.v1 import _extract_code_from_url
    assert _extract_code_from_url(raw) == expected


# ── D. infra.cache._normalize_moneydj_url_for_cache（production 0 呼叫者）──
def test_D_現況_小寫a與裸碼都得空碼鍵():
    from infra.cache import _normalize_moneydj_url_for_cache as n
    assert n("https://www.moneydj.com/funddj/ya/yp010001.djhtm?a=tlzf9-al001") == "fetch_fund||default"
    assert n("TLZF9-AL001") == "fetch_fund||default"
