"""test_quadrant_simulator.py — v18.285 FX × NAV 4 象限策略模擬"""
from __future__ import annotations

import pandas as pd
import pytest

from services.quadrant_simulator import (
    DEFAULT_QUADRANTS,
    QuadrantScenario,
    compare_strategies_per_quadrant,
    simulate_quadrant,
    summarize_best_per_quadrant,
)


# ──────────────────────────────────────────────────────────────
# Scenario 結構
# ──────────────────────────────────────────────────────────────
def test_default_quadrants_are_four():
    assert len(DEFAULT_QUADRANTS) == 4
    codes = [q.code for q in DEFAULT_QUADRANTS]
    assert codes == ["Q1", "Q2", "Q3", "Q4"]


def test_default_quadrants_cover_all_4_combinations():
    """Q1 ~ Q4 應涵蓋 (FX± × NAV±) 4 種組合。"""
    sigs = [(q.fx_change_pct_year > 0, q.nav_change_pct_year > 0)
            for q in DEFAULT_QUADRANTS]
    # 應有 (F,F)=Q1 / (T,F)=Q2 / (F,T)=Q3 / (T,T)=Q4
    assert set(sigs) == {(False, False), (True, False), (False, True), (True, True)}


# ──────────────────────────────────────────────────────────────
# simulate_quadrant
# ──────────────────────────────────────────────────────────────
def test_simulate_drip_increases_units():
    """DRIP 配股再投入 → final units > initial units。"""
    q = DEFAULT_QUADRANTS[3]  # Q4 雙利
    r = simulate_quadrant(q, initial_twd=1_000_000, nav=10.0, fx=32.0,
                          annual_div_rate_pct=6.0, horizon_months=12,
                          strategy="DRIP")
    initial_units = 1_000_000 / 32.0 / 10.0
    assert r["final_units"] > initial_units


def test_simulate_cash_accumulates_twd_dividends():
    """CASH 領現 → dividends_total_twd > 0。"""
    q = DEFAULT_QUADRANTS[3]
    r = simulate_quadrant(q, initial_twd=1_000_000, nav=10.0, fx=32.0,
                          annual_div_rate_pct=6.0, horizon_months=12,
                          strategy="CASH")
    assert r["dividends_total_twd"] > 0


def test_simulate_stay_keeps_units_constant():
    """STAY 停泊 → units 不變（配息留原幣）。"""
    q = DEFAULT_QUADRANTS[3]
    r = simulate_quadrant(q, initial_twd=1_000_000, nav=10.0, fx=32.0,
                          annual_div_rate_pct=6.0, horizon_months=12,
                          strategy="STAY")
    initial_units = 1_000_000 / 32.0 / 10.0
    assert r["final_units"] == pytest.approx(initial_units)


def test_q4_double_positive_all_strategies_profit():
    """Q4 雙重利 → 3 個策略都應該賺錢（報酬 > 0）。"""
    q = DEFAULT_QUADRANTS[3]
    for s in ("DRIP", "CASH", "STAY"):
        r = simulate_quadrant(q, initial_twd=1_000_000, nav=10.0, fx=32.0,
                              annual_div_rate_pct=6.0, horizon_months=12,
                              strategy=s)
        assert r["total_return_pct"] > 0, f"Q4 {s} 應賺錢但 ret={r['total_return_pct']}"


def test_q1_double_negative_all_strategies_lose():
    """Q1 雙重打擊 → 3 個策略全部虧（FX 損 + NAV 損遠大於配息）。"""
    q = DEFAULT_QUADRANTS[0]  # -5% FX, -10% NAV
    for s in ("DRIP", "CASH", "STAY"):
        r = simulate_quadrant(q, initial_twd=1_000_000, nav=10.0, fx=32.0,
                              annual_div_rate_pct=6.0, horizon_months=12,
                              strategy=s)
        assert r["total_return_pct"] < 0, f"Q1 {s} 應虧損但 ret={r['total_return_pct']}"


def test_simulate_zero_initial_twd_returns_safe_zeros():
    q = DEFAULT_QUADRANTS[0]
    r = simulate_quadrant(q, initial_twd=0, nav=10.0, fx=32.0,
                          annual_div_rate_pct=6.0, strategy="DRIP")
    assert r["final_value_twd"] == 0.0


def test_simulate_unknown_strategy_raises():
    q = DEFAULT_QUADRANTS[0]
    with pytest.raises(ValueError, match="unknown strategy"):
        simulate_quadrant(q, 1_000_000, 10.0, 32.0, 6.0, strategy="WTF")


# ──────────────────────────────────────────────────────────────
# compare_strategies_per_quadrant + summarize
# ──────────────────────────────────────────────────────────────
def test_compare_returns_12_rows_4_quadrants_x_3_strategies():
    df = compare_strategies_per_quadrant(
        initial_twd=1_000_000, nav=10.0, fx=32.0,
        annual_div_rate_pct=6.0, horizon_months=12,
    )
    assert len(df) == 12
    assert set(df["象限"].unique()) == {q.name for q in DEFAULT_QUADRANTS}
    assert set(df["策略"].unique()) == {"DRIP", "CASH", "STAY"}


def test_compare_marks_one_best_per_quadrant():
    df = compare_strategies_per_quadrant()
    # 每個象限只應有 1 個 🏆
    for q in DEFAULT_QUADRANTS:
        n_best = (df[df["象限"] == q.name]["最佳"] == "🏆").sum()
        assert n_best == 1, f"{q.name} 應有 1 個最佳但有 {n_best}"


def test_summarize_returns_4_rows():
    df = compare_strategies_per_quadrant()
    s = summarize_best_per_quadrant(df)
    assert len(s) == 4
    assert list(s.columns) == ["象限", "最佳策略", "期末 TWD", "報酬 %"]


def test_summarize_empty_input_safe():
    s = summarize_best_per_quadrant(pd.DataFrame())
    assert s.empty
