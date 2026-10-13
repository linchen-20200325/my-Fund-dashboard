# -*- coding: utf-8 -*-
"""FRED 三鍵（`credit_spread_pct`／`term_spread_pct`／`policy_rate_pct`）的 L2 轉換測試（fast lane；不打網路）。

依據：docs/v2/49 §6.2 T1、§6.3 N-3、§4.1（缺金鑰）、§1.3 出入 2；44 `market_indicator` 表
（`release_date`＝對外公布日、主鍵含 `release_date`、修正不覆蓋原列、`is_revised`）。

核心反例（客戶 2026-10-13 派工單點名）：**目前版本的生效日 ≠ 首次公布日** 時，
`is_revised` 為否的那一列必須用首次公布日；對不上公布日的觀測不寫。
L1 一律以替身注入（`mi.fetch_fred_vintages_with_error`）；`fetch_fred`／`fetch_fred_with_error`
（只拿得到「目前版本」的 `realtime_start`）被呼叫就紅。
"""
from __future__ import annotations

import datetime as dt

import pandas as pd
import pytest

from services.v2_tables import contract
from services.v2_tables import market_indicator as mi
from shared import fred_series

_FETCHED = "2026-10-13T06:00:00+00:00"
_TODAY = dt.date(2026, 10, 13)
_FLOOR = (_TODAY - dt.timedelta(days=mi.FRED_LOOKBACK_DAYS)).isoformat()
_FRED_KEYS = ("credit_spread_pct", "term_spread_pct", "policy_rate_pct")


def _frame(records, *, fetched_at=_FETCHED, floor=_FLOOR):
    """records：[(date, realtime_start, realtime_end, value)]，形狀同 L1 `fetch_fred_vintages`。"""
    df = pd.DataFrame({
        "date": pd.to_datetime([r[0] for r in records]),
        "value": pd.Series([r[3] for r in records], dtype="float64"),
        "realtime_start": pd.to_datetime([r[1] for r in records], errors="coerce"),
        "realtime_end": [r[2] for r in records],
    })
    if fetched_at is not None:
        df.attrs["fetched_at"] = fetched_at
    if floor is not None:
        df.attrs["realtime_floor"] = floor
    df.attrs["source"] = "FRED:X:vintages"
    return df


_NOW = "9999-12-31"
# 修正序列：2026-07-01 那一期 8/1 首次公布 4.33，9/1 修正成 4.32（目前版本生效日 9/1 ≠ 首次公布日 8/1）。
_REVISED = [("2026-07-01", "2026-08-01", "2026-08-31", 4.33),
            ("2026-07-01", "2026-09-01", _NOW, 4.32),
            ("2026-08-01", "2026-09-02", _NOW, 4.30)]


@pytest.fixture
def l1(monkeypatch):
    """FRED 替身；另外把只拿得到目前版本的兩支 L1 與國發會、Yahoo 擋起來。"""
    import repositories.macro.fred as fred

    def forbid(name):
        def boom(*a, **k):
            raise AssertionError(f"不得呼叫 {name}")
        return boom

    for name in ("fetch_fred", "fetch_fred_with_error"):
        monkeypatch.setattr(fred, name, forbid(name))
    monkeypatch.setattr(mi, "fetch_yf_close_with_error",
                        lambda *a, **k: (pd.Series(dtype=float), "Yahoo 不在本檔射程"))
    monkeypatch.setattr(mi, "_utc_today", lambda: _TODAY)
    table = {sid: (_frame(_REVISED), None) for sid in
             (fred_series.FRED_HY_SPREAD, fred_series.FRED_T10Y2Y, fred_series.FRED_FED_FUNDS)}
    calls = []

    def fake(series_id, api_key, observation_start):
        calls.append((series_id, api_key, observation_start))
        value = table[series_id]
        if isinstance(value, BaseException):
            raise value
        return value

    monkeypatch.setattr(mi, "fetch_fred_vintages_with_error", fake)
    fake.table, fake.calls = table, calls
    return fake


def _rows(out, key):
    return [r for r in out["rows"] if r["indicator_key"] == key]


# ═══════════════════════ 首次公布日（PIT） ═══════════════════════


def test_修正序列_首次公布日寫在非修正列_修正另成一列(l1):
    out = mi.build_market_indicator_table(fred_api_key="KEY")
    rows = _rows(out, "policy_rate_pct")
    jul = [r for r in rows if r["obs_date"] == "2026-07-01"]
    assert [(r["release_date"], r["value_num"], r["is_revised"]) for r in jul] == [
        ("2026-08-01", 4.33, False),     # 首次公布日 ≠ 目前版本生效日 9/1
        ("2026-09-01", 4.32, True),      # 修正不覆蓋原列（44 主鍵含 release_date）
    ]
    aug = [r for r in rows if r["obs_date"] == "2026-08-01"]
    assert [(r["release_date"], r["is_revised"]) for r in aug] == [("2026-09-02", False)]
    for row in out["rows"]:
        assert contract.market_indicator_row_problems(row) == []
        assert row["source_tier"] == "市場指標" and row["fetched_at"] == _FETCHED
        assert row["release_date"] >= row["obs_date"]


def test_is_revised與設定試算表讀取端的重算規則一致(l1):
    from repositories.settings_sheet_repository import _mi_revised
    rows = mi.build_market_indicator_table(fred_api_key="KEY")["rows"]
    pks = {(r["indicator_key"], r["obs_date"], r["release_date"]) for r in rows}
    assert len(pks) == len(rows)                       # 主鍵不撞
    for r in rows:
        assert r["is_revised"] == _mi_revised((r["indicator_key"], r["obs_date"], r["release_date"]), pks)


def test_一律走逐版次L1_序列ID取自SSOT_觀測起點為今天往回730日(l1):
    mi.build_market_indicator_table(fred_api_key="KEY")
    assert sorted(c[0] for c in l1.calls) == sorted(
        [fred_series.FRED_HY_SPREAD, fred_series.FRED_T10Y2Y, fred_series.FRED_FED_FUNDS])
    assert {c[1] for c in l1.calls} == {"KEY"}
    assert {c[2] for c in l1.calls} == {_FLOOR}
    assert mi.INDICATOR_SPECS["credit_spread_pct"]["source"][1] is fred_series.FRED_HY_SPREAD


def test_單位照44_值不換算(l1):
    out = mi.build_market_indicator_table(fred_api_key="KEY")
    assert {r["value_unit"] for r in _rows(out, "credit_spread_pct")} == {"pp"}
    assert {r["value_unit"] for r in _rows(out, "term_spread_pct")} == {"pp"}
    assert {r["value_unit"] for r in _rows(out, "policy_rate_pct")} == {"%"}
    assert sorted({r["value_num"] for r in _rows(out, "credit_spread_pct")}) == [4.30, 4.32, 4.33]


# ═══════════════════════ 對不上公布日 → 不寫 ═══════════════════════


@pytest.mark.parametrize("records, reason", [
    # 某一版的公布日缺 → 整期不寫
    ([("2026-07-01", None, "2026-08-31", 4.33), ("2026-07-01", "2026-09-01", _NOW, 4.32)],
     "公布日（realtime_start）缺或解析不了"),
    # 首次公布日等於查詢下界 → 分不出是否被截斷
    ([("2026-07-01", _FLOOR, _NOW, 4.33)], "首次公布日等於查詢下界"),
    # 公布日早於觀測期間
    ([("2026-07-01", "2026-06-30", _NOW, 4.33)], "首次公布日早於觀測期間"),
    # 公布日晚於取得日
    ([("2026-07-01", "2026-10-14", _NOW, 4.33)], "公布日晚於取得日"),
    # 兩個版次公布日相同 → 主鍵會撞
    ([("2026-07-01", "2026-08-01", "2026-08-31", 4.33), ("2026-07-01", "2026-08-01", _NOW, 4.32)],
     "同一期間兩個版次公布日相同"),
    # 現行版次已不含此觀測
    ([("2026-07-01", "2026-08-01", "2026-08-31", 4.33)], "現行版次已不含此觀測"),
    # 現行版次為缺值（FRED "."）
    ([("2026-07-01", "2026-08-01", "2026-08-31", 4.33), ("2026-07-01", "2026-09-01", _NOW, float("nan"))],
     "現行版次的值為缺值"),
])
def test_對不上公布日_該期間整筆不寫_其餘照寫(l1, records, reason):
    ok = [("2026-08-01", "2026-09-02", _NOW, 4.30)]
    l1.table[fred_series.FRED_FED_FUNDS] = (_frame(records + ok), None)
    out = mi.build_market_indicator_table(fred_api_key="KEY")
    rows = _rows(out, "policy_rate_pct")
    assert [(r["obs_date"], r["release_date"]) for r in rows] == [("2026-08-01", "2026-09-02")]
    assert any(reason in s for s in out["skipped"]["policy_rate_pct"]), out["skipped"]
    assert "policy_rate_pct" not in out["errors"]
    assert out["fetched"]["policy_rate_pct"] == len(records) + 1   # 取回的列數（過濾前）


def test_中間某版為缺值_那一版不寫_首個有值的版次為非修正(l1):
    l1.table[fred_series.FRED_FED_FUNDS] = (_frame([
        ("2026-07-01", "2026-08-01", "2026-08-15", float("nan")),
        ("2026-07-01", "2026-08-15", _NOW, 4.33)]), None)
    rows = _rows(mi.build_market_indicator_table(fred_api_key="KEY"), "policy_rate_pct")
    assert [(r["release_date"], r["is_revised"]) for r in rows] == [("2026-08-15", False)]


def test_邊界_公布日等於觀測日_照寫不擋(l1):
    """M8（2026-10-13 稽核突變存活）：`before_obs` 擋的是「早於」；同一天公布（日頻常見）要寫。"""
    l1.table[fred_series.FRED_T10Y2Y] = (_frame([("2026-09-30", "2026-09-30", _NOW, 0.55)]), None)
    rows = _rows(mi.build_market_indicator_table(fred_api_key="KEY"), "term_spread_pct")
    assert [(r["obs_date"], r["release_date"], r["value_num"], r["is_revised"]) for r in rows] == [
        ("2026-09-30", "2026-09-30", 0.55, False)]


def test_中間版次為缺值_那一版不寫_不以前後版補值(l1):
    """M14（2026-10-13 稽核突變存活）：值—缺值—值 三版，只寫兩個有值的版次；缺值那一版的公布日不出現。"""
    l1.table[fred_series.FRED_FED_FUNDS] = (_frame([
        ("2026-07-01", "2026-08-01", "2026-08-15", 4.33),
        ("2026-07-01", "2026-08-15", "2026-09-01", float("nan")),
        ("2026-07-01", "2026-09-01", _NOW, 4.32)]), None)
    rows = _rows(mi.build_market_indicator_table(fred_api_key="KEY"), "policy_rate_pct")
    assert [(r["release_date"], r["value_num"], r["is_revised"]) for r in rows] == [
        ("2026-08-01", 4.33, False), ("2026-09-01", 4.32, True)]


@pytest.mark.parametrize("attrs_patch, needle", [
    ({"fetched_at": None}, "fetched_at"),
    ({"floor": None}, "realtime_floor"),
])
def test_取得時間或查詢下界缺_整鍵不寫_不以當下時間補(l1, attrs_patch, needle):
    kw = {"fetched_at": _FETCHED, "floor": _FLOOR, **attrs_patch}
    l1.table[fred_series.FRED_FED_FUNDS] = (_frame(_REVISED, **kw), None)
    out = mi.build_market_indicator_table(fred_api_key="KEY")
    assert _rows(out, "policy_rate_pct") == []
    assert any(needle in s for s in out["skipped"]["policy_rate_pct"])


# ═══════════════════════ 失敗與缺金鑰 ═══════════════════════


@pytest.mark.parametrize("key", [None, "", "   "])
def test_缺金鑰_不打L1_寫成取數失敗而不是資料未備(l1, key):
    out = mi.build_market_indicator_table(fred_api_key=key)
    assert l1.calls == []
    for k in _FRED_KEYS:
        assert out["errors"][k] == mi.MISSING_FRED_API_KEY == "未設定 FRED_API_KEY"
        assert k not in out["pending"] and _rows(out, k) == [] and out["fetched"][k] == 0


def test_L1失敗原文逐字保留_空表沒原因寫弱訊息_例外轉原文(l1):
    l1.table[fred_series.FRED_HY_SPREAD] = (pd.DataFrame(), "fetch_url returned None: FRED:BAMLH0A0HYM2 (vintages)")
    l1.table[fred_series.FRED_T10Y2Y] = (pd.DataFrame(), None)
    l1.table[fred_series.FRED_FED_FUNDS] = RuntimeError("boom")
    out = mi.build_market_indicator_table(fred_api_key="KEY")
    assert out["errors"]["credit_spread_pct"] == "fetch_url returned None: FRED:BAMLH0A0HYM2 (vintages)"
    assert out["errors"]["term_spread_pct"] == mi.EMPTY_WITHOUT_REASON
    assert out["errors"]["policy_rate_pct"] == "RuntimeError: boom"
    assert [r for r in out["rows"] if r["indicator_key"] in _FRED_KEYS] == []


def test_冷卻狀態也看FRED主機():
    assert mi.phase1_hosts() == ["query1.finance.yahoo.com", "api.stlouisfed.org"]


def test_金鑰讀取_st_secrets優先_缺檔不炸_都沒有回空字串():
    class _Broken:
        def get(self, _k):
            raise FileNotFoundError("no secrets.toml")

    assert mi.fred_api_key_from([_Broken(), {"FRED_API_KEY": "env"}]) == "env"
    assert mi.fred_api_key_from([{"FRED_API_KEY": "sec"}, {"FRED_API_KEY": "env"}]) == "sec"
    assert mi.fred_api_key_from([{"FRED_API_KEY": "  "}, {}]) == ""
    assert mi.fred_api_key_from([None]) == ""


# ═══════════════════════ 接到畫面（既有 logic，不改） ═══════════════════════


def test_接到mkt既有logic_信用利差與政策利率出數_修正列掛修正過(l1):
    from ui_v2.mkt import logic
    out = mi.build_market_indicator_table(fred_api_key="KEY")
    model = logic.build_page_model({"rows": out["rows"], "errors": {}})
    mkt1 = {mv["_source_key"]: mv for mv in logic.find_block(model, "MKT-1")["main_values"]}
    assert mkt1["credit_spread_pct"]["value_text"] == "4.30"
    mkt3 = {mv["_source_key"]: mv for mv in logic.find_block(model, "MKT-3")["main_values"]}
    assert mkt3["policy_rate_pct"]["value_text"] == "4.30"
    revised = [r for r in logic.find_block(model, "MKT-6")["_rows"] if r["_row_badge"] == "修正過"]
    assert revised and all(r["indicator_key"] in _FRED_KEYS for r in revised)
