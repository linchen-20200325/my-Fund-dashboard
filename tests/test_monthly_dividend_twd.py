"""v19.323 — 健診 ② 配息表「每月配息 (TWD)」SSOT 測試。

守住:
1. estimate_monthly_dividend_twd 前瞻算式 = 本金 × 年化配息率 / 12(截圖 11,292 對帳)
2. FX 中性(原幣本金 × fx 兩次約掉)— 與 investment.py 月配息(TWD) 同源
3. 邊界:本金 / adr 缺或 ≤ 0 → 顯式 None(§1 不填 0)
4. build_dividend_summary_row 整合:principal 有值 → 算出金額;None → None
5. DIVIDEND_COLUMNS 含新欄
"""
from __future__ import annotations

import math

import pytest

from services.health.dividend_calc import estimate_monthly_dividend_twd


# ── 1. 前瞻算式 + 截圖對帳 ────────────────────────────────
def test_screenshot_reconcile_1m_at_13_55pct():
    """截圖:100 萬 TWD × 13.55% / 12 ≈ 11,292 TWD。"""
    got = estimate_monthly_dividend_twd(1_000_000, 13.55)
    assert got is not None
    assert math.isclose(got, 1_000_000 * 13.55 / 100.0 / 12.0, rel_tol=1e-9)
    assert round(got) == 11292


def test_formula_is_principal_times_adr_over_1200():
    for principal, adr in [(500_000, 6.0), (2_000_000, 3.2), (1_000_000, 13.55)]:
        got = estimate_monthly_dividend_twd(principal, adr)
        assert math.isclose(got, principal * adr / 1200.0, rel_tol=1e-12)


# ── 2. FX 中性:與 investment.py 原「原幣本金 × fx」路徑等價 ──
@pytest.mark.parametrize("fx", [1.0, 32.035, 0.22, 145.6])
def test_fx_neutral_matches_original_currency_path(fx):
    """investment.py 舊算式:原幣本金 = TWD/fx;月配(原幣) = 原幣本金 × adr/1200;
    月配(TWD) = 月配(原幣) × fx。fx 應完全約掉 → 與 SSOT 一致。"""
    principal_twd, adr = 1_000_000.0, 13.55
    amt_local = principal_twd / fx
    mon_div_local = amt_local * adr / 100.0 / 12.0
    mon_div_twd_original_path = mon_div_local * fx
    ssot = estimate_monthly_dividend_twd(principal_twd, adr)
    assert math.isclose(ssot, mon_div_twd_original_path, rel_tol=1e-9)


# ── 3. 邊界:缺值 / ≤ 0 → None(不填 0)────────────────────
@pytest.mark.parametrize("principal,adr", [
    (None, 13.55),
    (1_000_000, None),
    (0, 13.55),
    (-100, 13.55),
    (1_000_000, 0),
    (1_000_000, -1.0),
    ("x", 13.55),
    (1_000_000, "y"),
])
def test_missing_or_nonpositive_returns_none(principal, adr):
    assert estimate_monthly_dividend_twd(principal, adr) is None


# ── 4. build_dividend_summary_row 整合 ───────────────────
def test_row_builder_computes_monthly_div_when_principal_given():
    from services.health.report import build_dividend_summary_row
    fd = {"moneydj_div_yield": 13.55, "fund_name": "聯博-美國成長基金AP"}
    row = build_dividend_summary_row(fd, "ALBT8", principal_twd=1_000_000)
    # adr 走 wb05 → 13.55;每月配息 = 100萬 × 13.55 / 1200
    assert math.isclose(row["年化配息率 %"], 13.55, rel_tol=1e-9)
    assert row["每月配息 (TWD)"] is not None
    assert round(row["每月配息 (TWD)"]) == 11292


def test_row_builder_none_principal_gives_none():
    from services.health.report import build_dividend_summary_row
    fd = {"moneydj_div_yield": 13.55, "fund_name": "X"}
    row = build_dividend_summary_row(fd, "X", principal_twd=None)
    assert row["每月配息 (TWD)"] is None


def test_row_builder_no_adr_gives_none_even_with_principal():
    from services.health.report import build_dividend_summary_row
    fd = {"fund_name": "無配息基金", "metrics": {}}
    row = build_dividend_summary_row(fd, "X", principal_twd=1_000_000)
    # 無 adr → 每月配息 None(不因有本金就捏造)
    assert row["每月配息 (TWD)"] is None


# ── 5. column schema 有掛新欄 ────────────────────────────
def test_dividend_columns_includes_monthly_div():
    from services.health.report import DIVIDEND_COLUMNS
    assert "每月配息 (TWD)" in DIVIDEND_COLUMNS
    # 位置:年化配息率 % 之後、吃本金燈號之前(語意相鄰)
    i_adr = DIVIDEND_COLUMNS.index("年化配息率 %")
    i_mon = DIVIDEND_COLUMNS.index("每月配息 (TWD)")
    i_eat = DIVIDEND_COLUMNS.index("吃本金燈號 (1Y·MK)")
    assert i_adr < i_mon < i_eat
