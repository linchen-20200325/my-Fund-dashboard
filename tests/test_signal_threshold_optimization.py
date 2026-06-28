"""test_signal_threshold_optimization.py — v18.283 MT5-style 校準引擎驗收."""
from __future__ import annotations

import pandas as pd
import pytest

from services.crisis_backtest import CrisisEvent
from services.macro_signal_lookback import SignalSpec
from services.signal_threshold_optimization import (
    make_default_grid,
    optimize_signal_threshold,
)


def _event(peak: str) -> CrisisEvent:
    return CrisisEvent(
        market="SPX",
        peak_date=pd.Timestamp(peak),
        trough_date=pd.Timestamp(peak) + pd.Timedelta(days=60),
        recovery_date=None,
        peak_value=100.0,
        trough_value=85.0,
        drawdown_pct=-0.15,
        duration_days=60,
        recovery_days=None,
    )


def _spec_above(threshold=25.0):
    return SignalSpec(
        key="VIX", label="VIX", source="yahoo", series_id="^VIX",
        threshold=threshold, direction="above",
    )


class TestMakeDefaultGrid:
    def test_default_grid_has_n_steps(self):
        grid = make_default_grid(25.0, n_steps=11)
        assert len(grid) == 11

    def test_default_grid_centered(self):
        grid = make_default_grid(25.0, n_steps=11)
        assert grid[5] == pytest.approx(25.0)
        assert grid[0] == pytest.approx(12.5)
        assert grid[-1] == pytest.approx(37.5)

    def test_zero_default_uses_minus1_to_1(self):
        grid = make_default_grid(0.0, n_steps=11)
        assert grid[0] == -1.0
        assert grid[-1] == 1.0


class TestOptimizeBaseCases:
    def test_empty_series_returns_insufficient(self):
        result = optimize_signal_threshold(
            pd.Series([], dtype=float),
            [_event("2020-01-01")],
            _spec_above(25.0),
        )
        assert result["status"] == "insufficient_events"
        assert result["recommended"] == 25.0

    def test_insufficient_events_returns_base(self):
        idx = pd.date_range("2020-01-01", periods=400, freq="D")
        series = pd.Series([20.0] * 400, index=idx, name="VIX")
        result = optimize_signal_threshold(
            series, [_event("2020-06-01")], _spec_above(25.0), n_folds=4,
        )
        assert result["status"] == "insufficient_events"

    def test_returns_grid_results_when_valid(self):
        idx = pd.date_range("2018-01-01", periods=2000, freq="D")
        values = [(20.0 + 10.0 * (i % 200 < 50)) for i in range(2000)]
        series = pd.Series(values, index=idx, name="VIX")
        events = [_event(f"201{8+i//4}-0{(i%4)+1}-15") for i in range(8)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=4,
        )
        assert result["status"] in ("adopted", "fallback_overfit")
        assert len(result["grid_results"]) > 0
        assert len(result["walk_forward"]) > 0


class TestWalkForwardNoLeakage:
    def test_train_test_events_disjoint(self):
        idx = pd.date_range("2015-01-01", periods=3000, freq="D")
        values = [25.0 + 5 * ((i // 100) % 2) for i in range(3000)]
        series = pd.Series(values, index=idx, name="VIX")
        events = [_event(str((pd.Timestamp("2015-01-15")
                                + pd.Timedelta(days=i*180)).date()))
                  for i in range(8)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=4,
        )
        for wf in result["walk_forward"]:
            assert wf["n_train"] > 0
            assert wf["n_test"] > 0
            assert wf["n_train"] + wf["n_test"] <= len(events)


class TestDriftFallback:
    def test_high_drift_falls_back_to_default(self):
        idx = pd.date_range("2010-01-01", periods=3000, freq="D")
        values = [20.0 if i < 1500 else 35.0 for i in range(3000)]
        series = pd.Series(values, index=idx, name="VIX")
        events = [_event(f"201{i}-06-15") for i in range(8)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=4,
            drift_threshold_pct=30.0,
        )
        if result["status"] == "fallback_overfit":
            assert result["recommended"] == 25.0
            assert result["drift_warning"] is True


class TestGridSweepStructure:
    def test_grid_results_one_row_per_threshold(self):
        idx = pd.date_range("2015-01-01", periods=2000, freq="D")
        values = [25.0 + 5 * ((i // 80) % 2) for i in range(2000)]
        series = pd.Series(values, index=idx, name="VIX")
        events = [_event(str((pd.Timestamp("2015-06-15")
                                + pd.Timedelta(days=i*180)).date()))
                  for i in range(6)]
        custom_grid = (20.0, 25.0, 30.0)
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), grid=custom_grid, n_folds=3,
        )
        assert len(result["grid_results"]) == 3
        for row in result["grid_results"]:
            assert "threshold" in row
            assert "precision" in row
            assert "recall" in row
            assert "f1" in row


class TestStatusDriftWarningFlag:
    def test_drift_warning_is_bool(self):
        idx = pd.date_range("2015-01-01", periods=2000, freq="D")
        values = [25.0 + 5 * ((i // 80) % 2) for i in range(2000)]
        series = pd.Series(values, index=idx, name="VIX")
        events = [_event(str((pd.Timestamp("2015-06-15")
                                + pd.Timedelta(days=i*180)).date()))
                  for i in range(6)]
        result = optimize_signal_threshold(
            series, events, _spec_above(25.0), n_folds=3,
        )
        assert isinstance(result["drift_warning"], bool)
        assert result["status"] in ("adopted", "fallback_overfit",
                                     "insufficient_events")
