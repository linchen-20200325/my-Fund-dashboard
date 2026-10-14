# -*- coding: utf-8 -*-
"""`services/v2_tables/exp_nav.py`（exp 淨值逐檔記憶，`49` §4.4 的有意偏離）守衛。

第一段是**計數測試**（派工要求先寫）：用 `tests/_a_chain_stub.py` 把 A 鏈每一個會發請求的葉節點換成記錄呼叫的替身，
走**真的** A 鏈（`build_nav_dividend_tables` → `fetch_chain_with_error` → `auto_fetch_moneydj` → L1 十五分鐘快取），
數第二次呼叫還出不出門 —— 這是「要不要做成功記憶」的依據。全程不打網路。
"""
from __future__ import annotations

import contextlib
import datetime as dt
import io

import pandas as pd
import pytest

import _a_chain_stub as H
from services.v2_tables import exp_nav as EN
from services.v2_tables import nav_dividend as ND

NOW = dt.datetime(2026, 10, 1, 0, 0, tzinfo=dt.timezone.utc)
L1_AT = "2026-09-30T08:00:00+00:00"
META = "meta:MoneyDJ+TDCC"


@pytest.fixture(autouse=True)
def _clean():
    EN.clear_memo()
    yield
    EN.clear_memo()


def _funds(code, *, ccy="USD", source=META, full_key=None, chain_code=None):
    return [{"fund_code": code, "full_key": full_key or code, "chain_code": chain_code or code, "portal": "",
             "declared_ccy": ccy, "declared_ccy_source": source}]


def _quiet(fn, *a, **k):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **k)


def _fc_count(calls, start=0):
    return [c[0] for c in calls[start:]].count("_src_fundclear_nav")


# `nav_history.load_points` 在替身裡是**整支換掉**的（`H.install`），所以 `nav_history_shared_reads(skip_reads=True)`
# 的「範圍內不打 Sheets」在替身上不生效、每次都會記一筆；真的 `load_points` 在 B 線範圍內直接回 `[]`、不出門
# （`services/nav_history_gs.py::shared_reads`）。數「出門次數」時把它排除。
def _outbound(calls, start=0):
    return [c for c in calls[start:] if c[0] != "nav_history.load_points"]


# ═══════════════════════ 計數測試（依據）═══════════════════════

class TestCountBasis:
    def test_L2本身沒有記憶_同一份輸入兩次_chain_fetch被呼叫兩次(self):
        calls = []
        fetch = _chain(calls, {"MZ01": _ok_res("MZ01")})
        ND.build_nav_dividend_tables(_funds("MZ01"), now=NOW, chain_fetch=fetch)
        ND.build_nav_dividend_tables(_funds("MZ01"), now=NOW, chain_fetch=fetch)
        assert len(calls) == 2

    def test_真A鏈_每個元件都成功_第二次不出門(self, monkeypatch):
        code, sc = H.full_success_scenario()
        calls = H.install(monkeypatch, sc)
        _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
        n = len(calls)
        _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
        assert _outbound(calls[:n]) and _outbound(calls, n) == []   # L1 十五分鐘快取命中：一個葉節點都沒打

    @pytest.mark.parametrize("name", ["S1_complete_fundclear", "S3_all_fail"])
    def test_真A鏈_淨值可用但元件不全或全敗_第二次照樣出門(self, monkeypatch, name):
        # S1：淨值 25 筆、名稱有，但沒有 wb07／wb01／持股 → L1 不快取（B 線卻拿得到淨值）；S3：全敗 → L1 不快取
        code, sc = H.scenarios()[name]
        calls = H.install(monkeypatch, sc)
        _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
        n = len(calls)
        first = _fc_count(calls[:n])
        _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
        assert first > 0 and _fc_count(calls, n) == first

    def test_真A鏈_S1第一次就有淨值列(self, monkeypatch):
        # 證明 S1 是「B 線可用」的成功（不是失敗）—— 所以成功記憶有存在的必要
        code, sc = H.scenarios()["S1_complete_fundclear"]
        H.install(monkeypatch, sc)
        out = _quiet(ND.build_nav_dividend_tables, _funds(code), now=NOW)
        assert out["nav"]["rows"] and code not in out["nav"]["errors"]

    @pytest.mark.parametrize("name", ["S1_complete_fundclear", "S3_all_fail"])
    def test_真A鏈_經exp_nav_第二次不出門(self, monkeypatch, name):
        code, sc = H.scenarios()[name]
        calls = H.install(monkeypatch, sc)
        first = _quiet(EN.load_nav_dividend, _funds(code), now=NOW, clock=lambda: 100.0)
        n = len(calls)
        second = _quiet(EN.load_nav_dividend, _funds(code), now=NOW, clock=lambda: 101.0)
        assert n > 0 and len(calls) == n
        assert second["memo"][code]["hit"] is True
        assert second["nav"] == first["nav"] and second["dividend"] == first["dividend"]


# ═══════════════════════ 替身 ═══════════════════════

def _ok_res(code, n=5):
    attrs = {"source": "FundClear:GetFundNAV", "fetched_at": L1_AT}
    return {"full_key": code, "series": H.series(n, start="2026-08-03", attrs=attrs), "dividends": [],
            "data_source": "FundClear", "chain_started_at": "2026-09-30T07:00:00+00:00"}


def _fail_res(code):
    return {"full_key": code, "series": pd.Series(dtype=float), "error": "全部來源失敗", "dividends": []}


def _chain(calls, by_code):
    def fetch(chain_code, full_key):
        calls.append((chain_code, full_key))
        res = by_code[chain_code]
        series, error = ND._nav_from_chain(res, "yp010000", chain_code, full_key)
        return series, error, ND._div_from_chain(res, full_key)
    return fetch


class _Clock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


def _load(funds, calls, by_code, *, now=NOW, clock=None):
    return EN.load_nav_dividend(funds, now=now, clock=clock or _Clock(), chain_fetch=_chain(calls, by_code))


# ═══════════════════════ 記憶 ═══════════════════════

def test_形狀與build_nav_dividend_tables相同_多檔():
    by = {"MZ01": _ok_res("MZ01"), "MZ02": _fail_res("MZ02"), "MZ03": _ok_res("MZ03", 3)}
    funds = _funds("MZ01") + _funds("MZ02") + _funds("MZ03")
    want = ND.build_nav_dividend_tables(funds, now=NOW, chain_fetch=_chain([], by))
    got = _load(funds, [], by)
    assert got["nav"] == want["nav"] and got["dividend"] == want["dividend"]
    assert set(got["memo"]) == {"MZ01", "MZ02", "MZ03"}
    assert all(m == {"hit": False, "cooling": False, "cooling_remaining_sec": None} for m in got["memo"].values())


def test_成功_899秒命中_900秒不命中():
    calls, clock = [], _Clock()
    by = {"MZ01": _ok_res("MZ01")}
    first = _load(_funds("MZ01"), calls, by, clock=clock)
    clock.t += 899
    hit = _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 1 and hit["memo"]["MZ01"] == {"hit": True, "cooling": False, "cooling_remaining_sec": None}
    assert hit["nav"]["rows"] == first["nav"]["rows"]                    # fetched_at 沿用當初那一份
    clock.t += 1
    miss = _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 2 and miss["memo"]["MZ01"]["hit"] is False


def test_失敗_300秒記憶_冷卻旗標與剩餘秒數():
    calls, clock = [], _Clock()
    by = {"MZ01": _fail_res("MZ01")}
    first = _load(_funds("MZ01"), calls, by, clock=clock)
    assert "MZ01" in first["nav"]["errors"]
    clock.t += 299
    hit = _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 1
    assert hit["memo"]["MZ01"] == {"hit": True, "cooling": True, "cooling_remaining_sec": 1.0}
    assert hit["nav"]["errors"] == first["nav"]["errors"]                # 上一次的失敗原文
    clock.t += 1
    _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 2


def test_幣別閘扣下不算失敗_記成功TTL():
    calls, clock = [], _Clock()
    res = _ok_res("MZ01")
    res["series"].attrs["currency"] = "JPY"                              # 序列宣告與 meta 不同 → 扣下
    by = {"MZ01": res}
    first = _load(_funds("MZ01"), calls, by, clock=clock)
    assert first["nav"]["withheld"] == {"MZ01": ND.WITHHELD_CCY_CONFLICT}
    clock.t += 600
    hit = _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 1 and hit["memo"]["MZ01"]["cooling"] is False


@pytest.mark.parametrize("a, b, same", [
    (dt.datetime(2026, 10, 1, 15, 59, 58, tzinfo=dt.timezone.utc),
     dt.datetime(2026, 10, 1, 15, 59, 59, tzinfo=dt.timezone.utc), True),     # 台灣同一天（23:59:58／23:59:59）
    (dt.datetime(2026, 10, 1, 15, 59, 59, tzinfo=dt.timezone.utc),
     dt.datetime(2026, 10, 1, 16, 0, 0, tzinfo=dt.timezone.utc), False),      # 台灣跨日（23:59:59 → 00:00:00）
])
def test_台灣日期跨日不命中(a, b, same):
    calls, clock = [], _Clock()
    by = {"MZ01": _ok_res("MZ01")}
    _load(_funds("MZ01"), calls, by, now=a, clock=clock)
    _load(_funds("MZ01"), calls, by, now=b, clock=clock)
    assert len(calls) == (1 if same else 2)


@pytest.mark.parametrize("change", [
    {"full_key": "MZ01X"}, {"chain_code": "MZ01Y"}, {"ccy": "EUR"}, {"source": "meta:MoneyDJ"}, {"ccy": None},
])
def test_任一鍵不同不命中(change):
    calls, clock = [], _Clock()
    base = {"MZ01": _ok_res("MZ01"), "MZ01Y": _ok_res("MZ01")}
    _load(_funds("MZ01"), calls, base, clock=clock)
    kwargs = dict(change)
    funds = _funds("MZ01", **kwargs)
    if "full_key" in kwargs:
        base = {"MZ01": _ok_res("MZ01X")}
    _load(funds, calls, base, clock=clock)
    assert len(calls) == 2


def test_不同代碼不命中():
    calls, clock = [], _Clock()
    by = {"MZ01": _ok_res("MZ01"), "MZ02": _ok_res("MZ02")}
    _load(_funds("MZ01"), calls, by, clock=clock)
    _load(_funds("MZ02"), calls, by, clock=clock)
    assert [c[0] for c in calls] == ["MZ01", "MZ02"]


def test_clear_memo_清掉_有登記在全域清除名單():
    from infra.cache import _CACHE_REGISTRY
    assert any(getattr(c, "__name__", "") == "exp_nav_memo" for c in _CACHE_REGISTRY)
    calls, clock = [], _Clock()
    by = {"MZ01": _ok_res("MZ01")}
    _load(_funds("MZ01"), calls, by, clock=clock)
    EN.clear_memo()
    _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 2


def test_交出深拷貝_下游改寫碰不到記憶():
    calls, clock = [], _Clock()
    by = {"MZ01": _ok_res("MZ01")}
    first = _load(_funds("MZ01"), calls, by, clock=clock)
    first["nav"]["rows"][0]["nav_orig_ccy"] = -1.0
    first["nav"]["provenance"]["MZ01"]["source"] = "被改"
    second = _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 1 and second["memo"]["MZ01"]["hit"] is True
    assert second["nav"]["rows"][0]["nav_orig_ccy"] != -1.0
    assert second["nav"]["provenance"]["MZ01"]["source"] != "被改"


def test_持倉手填_ValueError():
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": "", "holding_ccy": "USD"}]
    with pytest.raises(ValueError, match="meta 模式"):
        EN.load_nav_dividend(funds, now=NOW, chain_fetch=_chain([], {}))


def test_沒帶declared鍵_ValueError():
    funds = [{"fund_code": "MZ01", "full_key": "MZ01", "chain_code": "MZ01", "portal": ""}]
    with pytest.raises(ValueError, match="declared_ccy"):
        EN.load_nav_dividend(funds, now=NOW, chain_fetch=_chain([], {}))


def test_壞出處照nav_dividend的白名單擋():
    with pytest.raises(ValueError, match="declared_ccy_source"):
        EN.load_nav_dividend(_funds("MZ01", source="meta:meta:X"), now=NOW, chain_fetch=_chain([], {}))


def test_同一檔輸入矛盾_不取數_不記憶():
    calls = []
    funds = _funds("MZ01") + _funds("MZ01", full_key="MZ01Z")
    out = _load(funds, calls, {})
    assert calls == [] and out["nav"]["withheld"] == {"MZ01": ND.WITHHELD_INPUT_CONFLICT}
    assert EN._REGISTERED.cache_info()["size"] == 0


def test_TTL常數():
    from shared.ttls import TTL_5MIN, TTL_15MIN
    assert EN.SUCCESS_TTL_SEC == TTL_15MIN and EN.FAILURE_TTL_SEC == TTL_5MIN == 300


# ═══════════════════════ 2026-10-14 稽核 V／W 回修 ═══════════════════════

def test_取得時間晚於當下的扣下_不記憶_下一次重判():
    # 稽核 V 的重現：第一次 fetched_at 比當下晚 400 秒（超過 300 秒容忍）→ 扣下；200 秒後同一天再查，
    # 直接呼叫 nav_dividend 已經寫得出列，記憶不得把舊的扣下重播出來。
    calls, clock = [], _Clock()
    res = _ok_res("MZ01")
    res["series"].attrs["fetched_at"] = (NOW + dt.timedelta(seconds=400)).isoformat()
    first = _load(_funds("MZ01"), calls, {"MZ01": res}, clock=clock)
    assert first["nav"]["withheld"] == {"MZ01": ND.WITHHELD_FETCHED_AT_FUTURE}
    clock.t += 200
    later = NOW + dt.timedelta(seconds=200)
    second = _load(_funds("MZ01"), calls, {"MZ01": res}, now=later, clock=clock)
    direct = ND.build_nav_dividend_tables(_funds("MZ01"), now=later, chain_fetch=_chain([], {"MZ01": res}))
    assert len(calls) == 2 and second["memo"]["MZ01"]["hit"] is False
    assert second["nav"] == direct["nav"] and len(second["nav"]["rows"]) == 5


def test_配息逐筆取得時間晚於當下_也不記憶():
    import repositories.fund.sources as S
    from repositories.fund import fund_orchestration as FO
    future = (NOW + dt.timedelta(seconds=400)).isoformat()
    item = {"date": "2026-08-05", "ex_date": "2026-08-05", "pay_date": "2026-08-05", "amount": 0.04,
            "yield_pct": 0, "currency": "USD",
            S.DIV_PROVENANCE_KEY: {"parser": S.DIV_PARSER_FUNDCLEAR, "date_field": "ExDividendDate",
                                   "currency_field": "Currency", "amount_field": "DividendAmount",
                                   "fetched_at": future}}
    res = _ok_res("MZ01")
    res["dividends"] = [item]
    res[FO.DIVIDENDS_OUTCOME_KEY] = {
        "outcome": FO.DIV_OUTCOME_ROWS, "legacy_inline_parse": False, "none_evidenced": False,
        "sources": [{"source": "FundClear", "parser": S.DIV_PARSER_FUNDCLEAR, "status": S.DIV_STATUS_ROWS,
                     "detail": "", "page_type": "yp010000",
                     "dropped": {"truncated": 0, "filtered": 0, "other_tables": 0}}]}
    calls, clock = [], _Clock()
    first = _load(_funds("MZ01"), calls, {"MZ01": res}, clock=clock)
    lines = list(first["dividend"]["skipped"].get("MZ01") or [])
    assert any(EN.TIME_DEPENDENT_REASON_MARK in line for line in lines), first["dividend"]
    _load(_funds("MZ01"), calls, {"MZ01": res}, clock=clock)
    assert len(calls) == 2


def test_晚於當下的理由字樣_與nav_dividend一致():
    _iso, code, why = ND._fetched_at_check((NOW + dt.timedelta(hours=1)).isoformat(), NOW)
    assert code == ND.WITHHELD_FETCHED_AT_FUTURE and why.startswith(EN.TIME_DEPENDENT_REASON_MARK)
    # 依日期判定的那一種不含這個字樣（鍵裡有台灣日期，同一天判斷不變，可以記）
    assert EN.TIME_DEPENDENT_REASON_MARK not in ND._date_bounds_reason(dt.date(2026, 10, 2), dt.date(2026, 10, 1))


def test_計價幣別未確定_逐檔隔離_其他檔照常():
    calls = []
    funds = _funds("MZ01") + _funds("MZ02", ccy=None, source=None) + _funds("MZ03")
    out = _load(funds, calls, {"MZ01": _ok_res("MZ01"), "MZ03": _ok_res("MZ03")})
    assert [c[0] for c in calls] == ["MZ01", "MZ03"]                     # MZ02 不取數
    assert out["not_fetched"] == {"MZ02": EN.TEXT_CCY_UNDETERMINED}
    assert out["nav"]["withheld"] == {"MZ02": EN.WITHHELD_CCY_UNDETERMINED}
    assert out["dividend"]["withheld"]["MZ02"] == EN.WITHHELD_CCY_UNDETERMINED
    assert out["nav"]["skipped"]["MZ02"] == [EN.TEXT_CCY_UNDETERMINED]
    assert out["dividend"]["settled"]["MZ02"] is False
    assert {r["fund_code"] for r in out["nav"]["rows"]} == {"MZ01", "MZ03"}
    assert list(out["memo"]) == ["MZ01", "MZ02", "MZ03"]
    assert EN._REGISTERED.cache_info()["size"] == 2                    # MZ02 不記憶


def test_計價幣別未確定_同一檔有一筆None_整檔不取():
    calls = []
    funds = _funds("MZ01") + _funds("MZ01", ccy=None, source=None)
    out = _load(funds, calls, {"MZ01": _ok_res("MZ01")})
    assert calls == [] and "MZ01" in out["not_fetched"]


def test_清除與進行中讀取_清除後不寫回():
    calls, clock = [], _Clock()
    inner = _chain(calls, {"MZ01": _ok_res("MZ01")})

    def racing(chain_code, full_key):
        out = inner(chain_code, full_key)
        EN.clear_memo()                     # 取數進行中，另一邊按了「重新取數」
        return out
    EN.load_nav_dividend(_funds("MZ01"), now=NOW, clock=clock, chain_fetch=racing)
    assert EN._REGISTERED.cache_info()["size"] == 0                    # 清除前開始的那一筆沒有寫回
    _load(_funds("MZ01"), calls, {"MZ01": _ok_res("MZ01")}, clock=clock)
    assert len(calls) == 2


def test_沒有清除時照常寫回():
    calls, clock = [], _Clock()
    _load(_funds("MZ01"), calls, {"MZ01": _ok_res("MZ01")}, clock=clock)
    assert EN._REGISTERED.cache_info()["size"] == 1


def test_鍵含portal_portal不同不命中():
    # 稽核 W（突變存活）：鍵拿掉 portal 要紅 —— 先以空 portal 成功記住，再給非空 portal，必須照實回 portal 錯誤
    calls, clock = [], _Clock()
    _load(_funds("MZ01"), calls, {"MZ01": _ok_res("MZ01")}, clock=clock)
    funds = [dict(_funds("MZ01")[0], portal="X")]
    out = _load(funds, calls, {"MZ01": _ok_res("MZ01")}, clock=clock)
    assert out["memo"]["MZ01"]["hit"] is False
    assert "portal" in out["nav"]["errors"]["MZ01"] and out["nav"]["rows"] == []


def test_命中時也交出深拷貝_改寫命中結果碰不到記憶():
    # 稽核 W（突變存活）：命中路徑拿掉 deepcopy 要紅
    calls, clock = [], _Clock()
    by = {"MZ01": _ok_res("MZ01")}
    _load(_funds("MZ01"), calls, by, clock=clock)
    hit = _load(_funds("MZ01"), calls, by, clock=clock)
    assert hit["memo"]["MZ01"]["hit"] is True
    hit["nav"]["rows"][0]["nav_orig_ccy"] = -1.0
    hit["nav"]["provenance"]["MZ01"]["source"] = "被改"
    again = _load(_funds("MZ01"), calls, by, clock=clock)
    assert len(calls) == 1 and again["memo"]["MZ01"]["hit"] is True
    assert again["nav"]["rows"][0]["nav_orig_ccy"] != -1.0
    assert again["nav"]["provenance"]["MZ01"]["source"] != "被改"
