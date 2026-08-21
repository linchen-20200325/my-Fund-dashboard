"""v19.499:多來源主路線提早 return 跳過持股抓取的修正。

根因:fetch_fund_from_moneydj_url 在 _s_ok(L780)/ alt page_type(L809)兩個提早
return 都在 legacy fetch_holdings(L1144/L1239)之前,而 fetch_fund_multi_source
不抓持股 → result["holdings"] 停在裸 {}(無 source/diag)→ Tab2 顯示「來源=—、無 diag」
(user 2026-08-20 回報 PYZW3/JFZN3/ACCP138…)。修:_ensure_holdings 在兩 return 前補抓。

本檔守:
1. _ensure_holdings 冪等(有持股不重抓)/ 空補抓 / 例外自組 diag(不留裸 {})。
2. 整合:走主路線(series≥10)提早 return 的基金,result["holdings"] 被補上(非裸 {})。
"""
import pandas as pd
import pytest

import repositories.fund.fund_orchestration as O


@pytest.fixture(autouse=True)
def _clear_holdings_ttl():
    """每個 case 前清 1hr 負快取(_holdings_ttl @_ttl_cache),避免同代號跨 case 命中舊 mock。"""
    O._holdings_ttl.cache_clear()
    yield
    O._holdings_ttl.cache_clear()


# ── 單元:_ensure_holdings ───────────────────────────────────────────────
def test_ensure_holdings_idempotent_when_present(monkeypatch):
    """已有持股 → 不重抓(冪等,避免與 legacy L1144/L1239 雙抓)。"""
    def _boom(_c):
        raise AssertionError("有持股時不該再呼叫 fetch_holdings")
    monkeypatch.setattr(O, "fetch_holdings", _boom)
    r = {"holdings": {"source": "MoneyDJ:tcb", "top_holdings": [{"name": "台積電"}]}}
    O._ensure_holdings(r, "JFZN3")
    assert r["holdings"]["source"] == "MoneyDJ:tcb"      # 原封不動


def test_ensure_holdings_fills_when_empty(monkeypatch):
    """裸 {} → 補抓,寫入 fetch_holdings 回傳(帶 source+diag)。"""
    _fake = {"source": "MoneyDJ:all_failed", "diag": ["12 候選 URL 全失敗"],
             "top_holdings": [], "sector_alloc": []}
    monkeypatch.setattr(O, "fetch_holdings", lambda _c: _fake)
    r = {"holdings": {}}
    O._ensure_holdings(r, "PYZW3")
    assert r["holdings"] is _fake
    assert r["holdings"]["source"] == "MoneyDJ:all_failed"
    assert r["holdings"]["diag"]                          # 面板有 diag 可顯示


def test_ensure_holdings_missing_key_also_fills(monkeypatch):
    """result 連 holdings key 都沒有 → 也補(falsy 判定)。"""
    monkeypatch.setattr(O, "fetch_holdings", lambda _c: {"source": "x", "top_holdings": [{"n": 1}]})
    r = {}
    O._ensure_holdings(r, "ALZF9")
    assert r["holdings"]["source"] == "x"


def test_ensure_holdings_exception_synthesizes_diag_never_bare(monkeypatch):
    """fetch_holdings 拋例外 → 自組 source+diag dict,§1/§2 絕不留裸 {}。"""
    def _raise(_c):
        raise RuntimeError("cache 層炸了")
    monkeypatch.setattr(O, "fetch_holdings", _raise)
    r = {"holdings": {}}
    O._ensure_holdings(r, "ACCP138")
    h = r["holdings"]
    assert h != {}                                       # 不留裸 {}(否則面板「來源=—」)
    assert h["source"] == "fetch_holdings:exception"
    assert h["diag"] and "cache 層炸了" in h["diag"][0]
    assert h["fetched_at"]


# ── 整合:主路線提早 return 也帶持股 ─────────────────────────────────────
def _series(n=12):
    idx = pd.date_range("2026-01-01", periods=n, freq="D")
    return pd.Series(range(10, 10 + n), index=idx, dtype=float)


def test_early_return_path_now_has_holdings(monkeypatch):
    """走主路線(series≥10)提早 return 的基金,holdings 不再是裸 {}。"""
    # multi_source 成功回 series,但**不含持股**(重現根因來源)
    def _fake_multi(code, force_refresh=False, page_type=""):
        return {"fund_name": "施羅德環球收益成長", "nav_latest": 12.0,
                "series": _series(), "currency": "USD", "status": "complete"}
    _holdings = {"source": "Morningstar:holdings:F00000XXXX:PortfolioSAL",
                 "top_holdings": [{"name": "AAPL", "pct": 3.1}],
                 "sector_alloc": [{"name": "Tech", "pct": 30.0}],
                 "diag": ["Morningstar｜secId=F00000XXXX ✅"]}
    monkeypatch.setattr(O, "fetch_fund_multi_source", _fake_multi)
    monkeypatch.setattr(O, "fetch_holdings", lambda _c: _holdings)

    out = O.fetch_fund_from_moneydj_url("PYZW3")           # 純代碼,非 URL

    assert out.get("series") is not None and len(out["series"]) >= 10  # 確實走 _s_ok 路
    assert out["holdings"] == _holdings                   # ★ 修正前這裡是裸 {}
    assert out["holdings"]["source"].startswith("Morningstar")
    assert out["holdings"]["top_holdings"]


def test_early_return_holdings_failure_carries_diag(monkeypatch):
    """主路線成功、但持股全失敗 → holdings 帶 all_failed diag(非裸 {},面板不顯「來源=—」)。"""
    def _fake_multi(code, force_refresh=False, page_type=""):
        return {"fund_name": "瀚亞多重收益", "nav_latest": 10.5,
                "series": _series(), "currency": "USD", "status": "complete"}
    _failed = {"source": "MoneyDJ:all_failed",
               "diag": ["MoneyDJ｜12 候選 URL 全失敗", "cnyes｜無持股", "Morningstar｜無 secId"],
               "top_holdings": [], "sector_alloc": []}
    monkeypatch.setattr(O, "fetch_fund_multi_source", _fake_multi)
    monkeypatch.setattr(O, "fetch_holdings", lambda _c: _failed)

    out = O.fetch_fund_from_moneydj_url("ACCP138")
    assert out["holdings"]["source"] == "MoneyDJ:all_failed"
    assert len(out["holdings"]["diag"]) == 3              # 面板顯示逐源 diag,不再「無 diag」


def test_negative_result_cached_within_ttl(monkeypatch):
    """稽核 F1 緩解:抓不到持股的基金,同一 TTL 窗內不重抓(_daily_cache 不存 all_failed,
    靠 _holdings_ttl 1hr 負快取擋掉每次載入重跑完整多 URL 嘗試)。"""
    _calls = {"n": 0}
    def _count_fail(_c):
        _calls["n"] += 1
        return {"source": "MoneyDJ:all_failed", "diag": ["全失敗"], "top_holdings": []}
    monkeypatch.setattr(O, "fetch_holdings", _count_fail)

    r1 = {"holdings": {}}
    r2 = {"holdings": {}}
    O._ensure_holdings(r1, "PYZW3")
    O._ensure_holdings(r2, "PYZW3")                       # 同代號第二次
    assert _calls["n"] == 1                               # ★ 只真抓一次(第二次命中負快取)
    assert r1["holdings"]["source"] == "MoneyDJ:all_failed"
    assert r2["holdings"]["source"] == "MoneyDJ:all_failed"
