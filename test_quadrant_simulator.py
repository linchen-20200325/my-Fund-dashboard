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


# ──────────────────────────────────────────────────────────────
# v18.286 Part B: 歷史四象限分類
# ──────────────────────────────────────────────────────────────
def test_classify_historical_quadrants_q1_double_negative():
    """合成資料：NAV 跌 + FX 跌（TWD 升值）→ 應分到 Q1。"""
    from services.quadrant_simulator import classify_historical_quadrants
    idx = pd.date_range("2023-01-31", periods=12, freq="ME")
    nav = pd.Series([10.0 - i * 0.1 for i in range(12)], index=idx)
    fx = pd.Series([32.0 - i * 0.1 for i in range(12)], index=idx)
    df = classify_historical_quadrants(nav, fx, window_months=3)
    assert not df.empty
    assert (df["quadrant"] == "Q1").all()


def test_classify_historical_quadrants_q4_double_positive():
    """NAV 漲 + FX 漲（TWD 貶值）→ 應分到 Q4。"""
    from services.quadrant_simulator import classify_historical_quadrants
    idx = pd.date_range("2023-01-31", periods=12, freq="ME")
    nav = pd.Series([10.0 + i * 0.1 for i in range(12)], index=idx)
    fx = pd.Series([32.0 + i * 0.1 for i in range(12)], index=idx)
    df = classify_historical_quadrants(nav, fx, window_months=3)
    assert not df.empty
    assert (df["quadrant"] == "Q4").all()


def test_classify_handles_empty_series():
    from services.quadrant_simulator import classify_historical_quadrants
    assert classify_historical_quadrants(pd.Series(dtype=float), pd.Series(dtype=float)).empty


def test_summarize_historical_distribution_pct_sums_to_100():
    from services.quadrant_simulator import (
        classify_historical_quadrants,
        summarize_historical_distribution,
    )
    idx = pd.date_range("2020-01-31", periods=48, freq="ME")
    import numpy as np
    rng = np.random.default_rng(0)
    nav = pd.Series(10.0 * np.cumprod(1 + rng.normal(0, 0.02, 48)), index=idx)
    fx = pd.Series(32.0 * np.cumprod(1 + rng.normal(0, 0.01, 48)), index=idx)
    df = classify_historical_quadrants(nav, fx, window_months=3)
    out = summarize_historical_distribution(df)
    assert out["_total"] > 0
    total_pct = sum(out[q]["pct"] for q in ("Q1", "Q2", "Q3", "Q4"))
    assert abs(total_pct - 100.0) < 0.01


# ──────────────────────────────────────────────────────────────
# v18.286 Part A: per-phase strategy
# ──────────────────────────────────────────────────────────────
def test_default_phase_script_each_has_alloc():
    """v18.286 後預設 4 phase 都應該帶 drip/cash/stay 欄位。"""
    from services.allocation_simulator import DEFAULT_PHASE_SCRIPT
    for seg in DEFAULT_PHASE_SCRIPT:
        assert "drip_pct" in seg
        assert "cash_pct" in seg
        assert "stay_pct" in seg
        # 三者總和應 = 100（normalize 前）
        assert seg["drip_pct"] + seg["cash_pct"] + seg["stay_pct"] == 100


def test_per_phase_allocation_used_in_timeline():
    """phase_alloc dict 應被 timeline 帶出來。"""
    from services.allocation_simulator import _build_phase_timeline
    script = [
        {"months": 2, "phase": "復甦", "monthly_nav_change_pct": 0.5,
         "drip_pct": 80, "cash_pct": 10, "stay_pct": 10},
    ]
    tl = _build_phase_timeline(script)
    assert len(tl) == 2
    # 4-tuple format
    _m, _ph, _navchg, _alloc = tl[0]
    assert _ph == "復甦"
    assert _alloc["drip_pct"] == 80
    assert _alloc["cash_pct"] == 10


def test_timeline_missing_alloc_returns_empty_dict():
    """phase 沒帶 alloc 欄位時 alloc dict 應為空，由 caller fallback params 全期值。"""
    from services.allocation_simulator import _build_phase_timeline
    script = [{"months": 1, "phase": "復甦", "monthly_nav_change_pct": 0.5}]
    tl = _build_phase_timeline(script)
    _m, _ph, _navchg, _alloc = tl[0]
    assert _alloc == {}
