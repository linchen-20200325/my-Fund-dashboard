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
def test_A_舊寫法仍會產生HTTPS_證明缺陷機制存在():
    """舊 UI 寫法（先 upper）的機制仍成立；修正在 UI 端改用 normalize_manual_fund_input。"""
    from repositories.fund.sources import parse_moneydj_input
    from services.moneydj_fetcher import build_moneydj_url
    built = build_moneydj_url(_URL.strip().upper(), "yp010001")
    assert parse_moneydj_input(built)["code"] == "HTTPS"


@pytest.mark.parametrize("raw,expected", [
    (_URL, "TLZF9-AL001"),
    ("  " + _URL + "  ", "TLZF9-AL001"),
    (_URL.upper(), "TLZF9-AL001"),
    ("HTTPS://WWW.MONEYDJ.COM/FUNDDJ/YA/YP010000.DJHTM?a=acdd01", "ACDD01"),
    ("https://m.moneydj.com/a1.aspx?a=acdd01", "ACDD01"),
    ("https://www.moneydj.com/funddj/ya/yp010001.djhtm", ""),   # 抽不出代碼 → 空（不猜）
])
def test_A_網址先判斷再取代碼(raw, expected):
    from services.moneydj_fetcher import normalize_manual_fund_input
    assert normalize_manual_fund_input(raw) == expected


@pytest.mark.parametrize("raw", ["tlzf9", "TLZF9", " acdd01 ", "TLZF9-AL001", "tlzf9-al001", "a" * 40, "", "  ", "ab c", "中文"])
def test_A_裸碼行為與修正前逐字相同(raw):
    from services.moneydj_fetcher import normalize_manual_fund_input
    assert normalize_manual_fund_input(raw) == raw.strip().upper()


def test_A_None安全():
    from services.moneydj_fetcher import normalize_manual_fund_input
    assert normalize_manual_fund_input(None) == ""


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


def test_B_fetch_nav_不再以後綴AL001當代碼(_nav_spy):
    nm, urls, cache_codes = _nav_spy
    nm.fetch_nav("TLZF9-AL001")
    assert not any("a=AL001" in u for u in urls)
    assert any(u.endswith("yp004001.djhtm?a=TLZF9-AL001") for u in urls)  # 完整鍵照舊先試
    assert "AL001" not in cache_codes and cache_codes == []  # 含 '-' 的鍵不查預存檔(不新增讀取)


def test_B_fetch_div_不再以後綴AL001當代碼(_nav_spy):
    nm, urls, _ = _nav_spy
    nm.fetch_div("TLZF9-AL001")
    assert not any("a=AL001" in u for u in urls)
    assert any(u.endswith("yp004003.djhtm?a=TLZF9-AL001") for u in urls)


def test_B_無破折號的鍵_網址序列與預存檔查詢逐字不變(_nav_spy):
    nm, urls, cache_codes = _nav_spy
    nm.fetch_nav("tlzf9")  # 修正前後皆:境外 → wb02、wf01、yp004001(一次,原本 mj_short==full_key 會重複同一網址)
    assert cache_codes == ["TLZF9"]
    assert urls[0].endswith("/w/wb/wb02.djhtm?a=tlzf9") and urls[1].endswith("/w/wf/wf01.djhtm?a=tlzf9")
    assert urls.count("https://www.moneydj.com/funddj/yf/yp004001.djhtm?a=tlzf9") == 1


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


def test_A_兩個UI入口都改用helper_不再先轉大寫():
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[1]
    t7 = (root / "ui/tab3_t7_ledger.py").read_text(encoding="utf-8")
    pf = (root / "ui/tab3_portfolio.py").read_text(encoding="utf-8")
    assert "_new_code_clean = normalize_manual_fund_input(_a_new_code)" in t7
    assert "_a_new_code.strip().upper()" not in t7
    assert "_code = normalize_manual_fund_input(_line)" in pf
    assert "_code = _line.upper()" not in pf
