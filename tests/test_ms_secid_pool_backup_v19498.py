"""v19.498:Morningstar 持股備源 —— `_resolve_ms_secid` 用選股池 secId/ISIN 優先。

MoneyDJ 保單子網域對雲端美國 IP 被擋,這類 FoF/保單基金改用池存 secId/ISIN 走
Morningstar。驗證解析四層優先順序(池 secId → 池 ISIN→screener → 硬編表 → 名稱搜尋)
+ 池讀失敗優雅退層(§1 不因池不可用擋掉持股)。
"""
import pytest

import repositories.fund.sources as S
import repositories.pool_repository as P


@pytest.fixture
def _no_name_search(monkeypatch):
    # 隔離:名稱搜尋 / TDCC 名 / 硬編表都空,只留池備源兩層可命中
    monkeypatch.setattr(S, "_morningstar_search_secid", lambda *a, **k: "")
    monkeypatch.setattr(S, "_tdcc_resolve_fund_name", lambda *a, **k: "")
    monkeypatch.setattr(S, "_MORNINGSTAR_SECID_MAP", {}, raising=False)


def _patch_pool(monkeypatch, *, secid=None, isin=None, ccy=None):
    monkeypatch.setattr(P, "resolve_secid", lambda c: secid)
    monkeypatch.setattr(P, "resolve_isin", lambda c: isin)
    monkeypatch.setattr(P, "resolve_currency", lambda c: ccy)


# ── 1) 池存 secId 最優先,命中即不再 screener / 名稱搜尋 ─────────────────────
def test_pool_secid_wins_no_screener_no_search(monkeypatch, _no_name_search):
    _patch_pool(monkeypatch, secid=("F00000ABCD", "USD"))
    _called = {"screener": False, "search": False}
    monkeypatch.setattr(S, "_morningstar_screener_secid",
                        lambda *a, **k: _called.__setitem__("screener", True) or "SCREENER")
    monkeypatch.setattr(S, "_morningstar_search_secid",
                        lambda *a, **k: _called.__setitem__("search", True) or "SEARCH")
    assert S._resolve_ms_secid("JFZN3") == "F00000ABCD"
    assert _called == {"screener": False, "search": False}     # 池 secId 命中 → 不再搜


# ── 2) 池無 secId、有 ISIN → screener 精確解析(帶對池幣別)──────────────────
def test_pool_isin_to_screener(monkeypatch, _no_name_search):
    _patch_pool(monkeypatch, secid=None, isin="LU0766462157", ccy="EUR")
    _seen = {}

    def _scr(isin, currency="USD"):
        _seen["isin"], _seen["ccy"] = isin, currency
        return "F00000EUR9"

    monkeypatch.setattr(S, "_morningstar_screener_secid", _scr)
    assert S._resolve_ms_secid("XXXX") == "F00000EUR9"
    assert _seen == {"isin": "LU0766462157", "ccy": "EUR"}


def test_pool_isin_default_usd_when_no_ccy(monkeypatch, _no_name_search):
    _patch_pool(monkeypatch, secid=None, isin="LU0766462157", ccy=None)
    _seen = {}

    def _scr(isin, currency="USD"):
        _seen["ccy"] = currency
        return "SID"

    monkeypatch.setattr(S, "_morningstar_screener_secid", _scr)
    assert S._resolve_ms_secid("XXXX") == "SID"
    assert _seen["ccy"] == "USD"                                # 池幣別空 → 退 USD(§4.1)


# ── 3) 池全空 → 退硬編表(不呼叫 screener)───────────────────────────────────
def test_falls_to_hardcode_when_pool_empty(monkeypatch, _no_name_search):
    _patch_pool(monkeypatch, secid=None, isin=None, ccy=None)
    monkeypatch.setattr(S, "_MORNINGSTAR_SECID_MAP",
                        {"TLZF9": ("F00000HARD", "USD")}, raising=False)
    monkeypatch.setattr(S, "_morningstar_screener_secid", lambda *a, **k: "SHOULD_NOT")
    assert S._resolve_ms_secid("TLZF9") == "F00000HARD"


# ── 4) 池 + 硬編皆空 → 名稱搜尋(最後退路)──────────────────────────────────
def test_falls_to_name_search_last(monkeypatch):
    _patch_pool(monkeypatch, secid=None, isin=None, ccy=None)
    monkeypatch.setattr(S, "_MORNINGSTAR_SECID_MAP", {}, raising=False)
    monkeypatch.setattr(S, "_tdcc_resolve_fund_name", lambda c: "Allianz Income Growth")
    monkeypatch.setattr(S, "_morningstar_search_secid", lambda q, **k: "F00000NAME" if q else "")
    assert S._resolve_ms_secid("ZZZ") == "F00000NAME"


# ── §1:池讀失敗(GS down)→ 不 raise、退硬編,不擋持股 ─────────────────────
def test_pool_read_raises_falls_through(monkeypatch, _no_name_search):
    def _boom(c):
        raise RuntimeError("GS down")

    monkeypatch.setattr(P, "resolve_secid", _boom)
    monkeypatch.setattr(P, "resolve_isin", _boom)
    monkeypatch.setattr(P, "resolve_currency", lambda c: None)
    monkeypatch.setattr(S, "_MORNINGSTAR_SECID_MAP",
                        {"QQ": ("F00000FALLBACK", "USD")}, raising=False)
    assert S._resolve_ms_secid("QQ") == "F00000FALLBACK"       # 兩層炸掉照樣退硬編


def test_empty_code_short_circuits(monkeypatch):
    _patch_pool(monkeypatch, secid=("X", "USD"))                # 即使池有,空 code 也不查
    assert S._pool_secid_lookup("") == ""


def test_pool_secid_lookup_returns_secid_directly(monkeypatch):
    _patch_pool(monkeypatch, secid=("F0GBR04ABC", "GBP"))
    assert S._pool_secid_lookup("ANY") == "F0GBR04ABC"
