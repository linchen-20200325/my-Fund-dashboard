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


def test_row_builder_none_when_fx_missing():
    from services.health.report import build_dividend_summary_row
    row = build_dividend_summary_row(
        _fd_with_divs(), "ALBT8", principal_twd=1_000_000, fx=None)
    assert row["每月配息單位數"] is None


def test_row_builder_none_when_no_dividends():
    from services.health.report import build_dividend_summary_row
    fd = {"fund_name": "X", "metrics": {"nav": 10.0}}  # 無 dividends
    row = build_dividend_summary_row(fd, "X", principal_twd=1_000_000, fx=1.0)
    assert row["每月配息單位數"] is None


# ── 4. column schema 換欄 ────────────────────────────────
def test_dividend_columns_uses_units_not_twd():
    from services.health.report import DIVIDEND_COLUMNS
    assert "每月配息單位數" in DIVIDEND_COLUMNS
    assert "每月配息 (TWD)" not in DIVIDEND_COLUMNS   # v19.323 估算欄已退役
    i_adr = DIVIDEND_COLUMNS.index("年化配息率 %")
    i_mon = DIVIDEND_COLUMNS.index("每月配息單位數")
    i_eat = DIVIDEND_COLUMNS.index("吃本金燈號 (1Y·MK)")
    assert i_adr < i_mon < i_eat


def test_estimate_twd_function_removed():
    """v19.323 估算函式應已移除(SSOT 只留真實記錄版)。"""
    import services.health.dividend_calc as dc
    assert not hasattr(dc, "estimate_monthly_dividend_twd")
