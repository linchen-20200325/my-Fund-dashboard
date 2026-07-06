"""v19.324 — 健診 ② 配息表「每月配息單位數」(真實記錄版) SSOT 測試。

取代 v19.323 年化÷12 估算(test_monthly_dividend_twd.py 已刪)。

守住:
1. latest_dividend_per_unit — 取最近一筆真實配息(date/ex_date 降序 + slash 正規化)
2. monthly_dividend_from_records — d × 持有單位 / NAV(原幣/TWD/單位三軸)
3. 邊界:無記錄 / 全 ≤ 0 / 缺 units/nav → None(§1 不估算)
4. build_dividend_summary_row 整合:有 fx → 算出單位數;無 fx → None
5. DIVIDEND_COLUMNS 用新欄「每月配息單位數」取代「每月配息 (TWD)」
"""
from __future__ import annotations

import math

import pytest

from services.health.dividend_calc import (
    latest_dividend_per_unit,
    monthly_dividend_from_records,
)


# ── 1. latest_dividend_per_unit ──────────────────────────
def test_latest_picks_most_recent_by_date():
    divs = [
        {"date": "2026-03-15", "amount": 0.40},
        {"date": "2026-05-15", "amount": 0.55},   # 最新
        {"date": "2026-04-15", "amount": 0.50},
    ]
    assert latest_dividend_per_unit(divs) == 0.55


def test_latest_ex_date_fallback_and_slash_normalize():
    divs = [
        {"ex_date": "2026/05/20", "amount": 0.60},   # slash + ex_date
        {"ex_date": "2026/04/20", "amount": 0.50},
    ]
    assert latest_dividend_per_unit(divs) == 0.60


@pytest.mark.parametrize("divs", [
    [],
    None,
    [{"date": "2026-05-01", "amount": 0}],       # 全 ≤ 0
    [{"date": "2026-05-01", "amount": -0.1}],
    [{"date": "", "amount": 0.5}],               # 無日期
    [{"amount": 0.5}],                           # 無日期鍵
    ["not-a-dict"],
])
def test_latest_missing_or_nonpositive_returns_none(divs):
    assert latest_dividend_per_unit(divs) is None


# ── 2. monthly_dividend_from_records 算式 ────────────────
def test_monthly_units_formula():
    """每月配息單位數 = 最近一筆實配 × 持有單位 / NAV。"""
    divs = [{"date": "2026-05-15", "amount": 0.5}]
    r = monthly_dividend_from_records(divs, units_held=424.82, nav=73.48, fx=32.035)
    assert r["latest_div_per_unit"] == 0.5
    assert math.isclose(r["mon_div_ccy"], 0.5 * 424.82, rel_tol=1e-9)
    assert math.isclose(r["mon_div_twd"], 0.5 * 424.82 * 32.035, rel_tol=1e-9)
    assert math.isclose(r["mon_div_units"], 0.5 * 424.82 / 73.48, rel_tol=1e-9)


def test_monthly_units_twd_fund_fx_1():
    divs = [{"date": "2026-05-15", "amount": 1.2}]
    r = monthly_dividend_from_records(divs, units_held=1000.0, nav=10.0, fx=1.0)
    assert math.isclose(r["mon_div_ccy"], 1200.0, rel_tol=1e-9)
    assert math.isclose(r["mon_div_twd"], 1200.0, rel_tol=1e-9)   # fx=1
    assert math.isclose(r["mon_div_units"], 120.0, rel_tol=1e-9)  # 1200/10


@pytest.mark.parametrize("divs,units,nav", [
    ([], 100.0, 10.0),                                # 無記錄
    ([{"date": "2026-05-01", "amount": 0.5}], None, 10.0),   # 缺 units
    ([{"date": "2026-05-01", "amount": 0.5}], 100.0, None),  # 缺 nav
    ([{"date": "2026-05-01", "amount": 0.5}], 0, 10.0),      # units ≤ 0
    ([{"date": "2026-05-01", "amount": 0.5}], 100.0, 0),     # nav ≤ 0
])
def test_monthly_units_missing_inputs_return_none(divs, units, nav):
    r = monthly_dividend_from_records(divs, units, nav, fx=1.0)
    assert r["mon_div_units"] is None


def test_monthly_units_bad_fx_still_gives_units_but_no_twd():
    """fx 缺 → mon_div_twd None,但單位數(不需 fx)仍算得出。"""
    divs = [{"date": "2026-05-15", "amount": 0.5}]
    r = monthly_dividend_from_records(divs, units_held=100.0, nav=10.0, fx=None)
    assert r["mon_div_units"] is not None
    assert r["mon_div_twd"] is None


# ── 2b. 來源標記 + 年化估算 fallback (v19.325) ─────────────
def test_source_is_records_when_real_dividends():
    divs = [{"date": "2026-05-15", "amount": 0.5}]
    r = monthly_dividend_from_records(divs, 100.0, 10.0, fx=1.0, adr_pct=6.0)
    assert r["source"] == "records"          # 有真實記錄 → 優先真實,不走估算


def test_source_is_estimate_when_no_records_but_adr():
    """無真實記錄但有 adr → 估算 = 持有單位 × adr / 1200(nav 約掉)。"""
    r = monthly_dividend_from_records([], units_held=100.0, nav=10.0, fx=1.0, adr_pct=6.0)
    assert r["source"] == "estimate"
    assert r["latest_div_per_unit"] is None
    assert math.isclose(r["mon_div_units"], 100.0 * 6.0 / 1200.0, rel_tol=1e-9)
    # mon_div_ccy = 原幣本金(100×10) × 6% / 12 = 1000 × 0.005 = 5.0
    assert math.isclose(r["mon_div_ccy"], 1000.0 * 6.0 / 100.0 / 12.0, rel_tol=1e-9)


def test_source_none_when_no_records_and_no_adr():
    r = monthly_dividend_from_records([], units_held=100.0, nav=10.0, fx=1.0, adr_pct=None)
    assert r["source"] is None
    assert r["mon_div_units"] is None


def test_estimate_units_independent_of_nav():
    """估算單位數 = units × adr / 1200,與 NAV 無關(nav 約掉)。"""
    r1 = monthly_dividend_from_records([], 100.0, 10.0, fx=1.0, adr_pct=6.0)
    r2 = monthly_dividend_from_records([], 100.0, 999.0, fx=1.0, adr_pct=6.0)
    assert math.isclose(r1["mon_div_units"], r2["mon_div_units"], rel_tol=1e-12)


# ── 3. build_dividend_summary_row 整合 ───────────────────
def _fd_with_divs():
    return {
        "fund_name": "聯博-美國成長基金AP",
        "metrics": {"nav": 73.48},
        "dividends": [
            {"date": "2026-03-15", "amount": 0.40},
            {"date": "2026-05-15", "amount": 0.50},
        ],
    }


def test_row_builder_units_when_fx_and_principal_given():
    from services.health.report import build_dividend_summary_row
    row = build_dividend_summary_row(
        _fd_with_divs(), "ALBT8", principal_twd=1_000_000, fx=32.035)
    # units_held = (100萬/32.035)/73.48;每月配息單位數 = 0.5 × units / 73.48
    _units = (1_000_000 / 32.035) / 73.48
    assert math.isclose(row["每月配息單位數"], 0.5 * _units / 73.48, rel_tol=1e-9)
    # v19.326:每月配息金額(TWD) = 0.5 × units × fx
    assert math.isclose(row["每月配息 (TWD)"], 0.5 * _units * 32.035, rel_tol=1e-9)


def test_row_builder_none_when_fx_missing():
    from services.health.report import build_dividend_summary_row
    row = build_dividend_summary_row(
        _fd_with_divs(), "ALBT8", principal_twd=1_000_000, fx=None)
    assert row["每月配息單位數"] is None


def test_row_builder_none_when_no_dividends_and_no_adr():
    from services.health.report import build_dividend_summary_row
    fd = {"fund_name": "X", "metrics": {"nav": 10.0}}  # 無 dividends + 無 adr
    row = build_dividend_summary_row(fd, "X", principal_twd=1_000_000, fx=1.0)
    assert row["每月配息單位數"] is None
    assert row["配息來源"] == "—"


def test_row_builder_source_records():
    from services.health.report import build_dividend_summary_row
    row = build_dividend_summary_row(
        _fd_with_divs(), "ALBT8", principal_twd=1_000_000, fx=32.035)
    assert row["配息來源"] == "真實"          # 有逐筆記錄 → 真實


def test_row_builder_estimate_fallback_when_no_records():
    """無逐筆記錄但有年化配息率 → 估算 fallback + 配息來源=估算。"""
    from services.health.report import build_dividend_summary_row
    fd = {"fund_name": "X", "metrics": {"nav": 10.0},
          "moneydj_div_yield": 6.0}          # 有 adr,無 dividends
    row = build_dividend_summary_row(fd, "X", principal_twd=1_000_000, fx=1.0)
    assert row["配息來源"] == "估算"
    assert row["每月配息單位數"] is not None


# ── 4. column schema 換欄 ────────────────────────────────
def test_dividend_columns_have_twd_amount_and_units():
    """v19.326:每月配息金額(TWD) + 每月配息單位數 並列,順序:年化率 → TWD → 單位 → 來源 → 吃本金。"""
    from services.health.report import DIVIDEND_COLUMNS
    assert "每月配息 (TWD)" in DIVIDEND_COLUMNS       # v19.326 加回「金額」欄
    assert "每月配息單位數" in DIVIDEND_COLUMNS
    assert "配息來源" in DIVIDEND_COLUMNS
    i_adr = DIVIDEND_COLUMNS.index("年化配息率 %")
    i_twd = DIVIDEND_COLUMNS.index("每月配息 (TWD)")
    i_unit = DIVIDEND_COLUMNS.index("每月配息單位數")
    i_src = DIVIDEND_COLUMNS.index("配息來源")
    i_eat = DIVIDEND_COLUMNS.index("吃本金燈號 (1Y·MK)")
    assert i_adr < i_twd < i_unit < i_src < i_eat


def test_estimate_twd_function_removed():
    """v19.323 估算函式應已移除(SSOT 只留真實記錄版)。"""
    import services.health.dividend_calc as dc
    assert not hasattr(dc, "estimate_monthly_dividend_twd")
