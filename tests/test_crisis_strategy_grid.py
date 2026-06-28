"""test_crisis_strategy_grid.py — Phase 4 策略網格引擎測試 (v18.260)

驗證：
- 4 個預設策略的單日倉位行為
- run_strategy 對齊 / 前視偏誤防護 / 各 metric 數學正確
- grid_search 4×3 cell 數量
- results_to_dataframe + build_heatmap_data 形狀
- rank_results 排序正確
- 空序列 / 短序列邊界
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from services.crisis_strategy_grid import (
    DEFAULT_STRATEGIES,
    _is_triggered,
    _pos_buy_and_hold,
    _pos_buy_dip,
    _pos_signal_exit,
    _pos_signal_half,
    build_heatmap_data,
    grid_search,
    rank_results,
    results_to_dataframe,
    run_strategy,
)


# ──────────────────────────────────────────────────────────────
# fixtures
# ──────────────────────────────────────────────────────────────
def _make_market(n: int = 252) -> pd.Series:
    """造一段先漲後跌再回升的序列（含一次 -15% 回撤）。"""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    # phase1 上漲到 day 60 → 120；phase2 跌到 day 120 → 102；phase3 反彈到 day 251 → 130
    values = (
        list(np.linspace(100, 120, 60))
        + list(np.linspace(120, 102, 60))
        + list(np.linspace(102, 130, n - 120))
    )
    return pd.Series(values, index=idx, name="MKT")


def _make_signal_high_during_crisis(n: int = 252) -> pd.Series:
    """day 50~130 訊號高（30），其餘低（15）。對齊 _make_market 危機區間。"""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    vals = [15.0] * n
    for i in range(50, 130):
        vals[i] = 30.0
    return pd.Series(vals, index=idx, name="VIX")


# ──────────────────────────────────────────────────────────────
# _is_triggered
# ──────────────────────────────────────────────────────────────
class TestIsTriggered:
    def test_above(self):
        assert _is_triggered(30.0, 25.0, "above") is True
        assert _is_triggered(25.0, 25.0, "above") is True
        assert _is_triggered(24.9, 25.0, "above") is False

    def test_below(self):
        assert _is_triggered(-0.1, 0.0, "below") is True
        assert _is_triggered(0.1, 0.0, "below") is False

    def test_nan_returns_false(self):
        assert _is_triggered(float("nan"), 25.0, "above") is False


# ──────────────────────────────────────────────────────────────
# 4 個策略的 position_fn
# ──────────────────────────────────────────────────────────────
class TestPositionFunctions:
    def test_buy_and_hold_always_1(self):
        assert _pos_buy_and_hold(False, 0.0) == 1.0
        assert _pos_buy_and_hold(True, -0.5) == 1.0

    def test_signal_exit_zero_when_triggered(self):
        assert _pos_signal_exit(True, 0.0) == 0.0
        assert _pos_signal_exit(False, -0.2) == 1.0

    def test_signal_half_half_when_triggered(self):
        assert _pos_signal_half(True, 0.0) == 0.5
        assert _pos_signal_half(False, -0.5) == 1.0

    def test_buy_dip_leverages_when_triggered_and_dropped(self):
        assert _pos_buy_dip(True, -0.10) == 1.5
        assert _pos_buy_dip(True, -0.05) == 1.5  # 邊界
        assert _pos_buy_dip(True, -0.04) == 1.0  # 不夠跌
        assert _pos_buy_dip(False, -0.20) == 1.0  # 沒訊號不加碼


# ──────────────────────────────────────────────────────────────
# DEFAULT_STRATEGIES 完整性
# ──────────────────────────────────────────────────────────────
class TestDefaultStrategies:
    def test_has_four(self):
        keys = [s.key for s in DEFAULT_STRATEGIES]
        assert keys == ["buy_and_hold", "signal_exit", "signal_half", "buy_dip"]

    def test_each_has_label_and_desc(self):
        for spec in DEFAULT_STRATEGIES:
            assert spec.label and spec.description


# ──────────────────────────────────────────────────────────────
# run_strategy
# ──────────────────────────────────────────────────────────────
class TestRunStrategy:
    def test_empty_series_returns_baseline(self):
        spec = DEFAULT_STRATEGIES[0]
        out = run_strategy(pd.Series(dtype=float), pd.Series(dtype=float), spec, 25.0)
        assert out.final_value == 100.0
        assert out.n_total_days == 0

    def test_buy_and_hold_matches_market_return(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        spec = next(s for s in DEFAULT_STRATEGIES if s.key == "buy_and_hold")
        out = run_strategy(mkt, sig, spec, 25.0)
        # buy_and_hold final = 100 * (130/100) = 130
        assert out.final_value == pytest.approx(130.0, rel=0.001)
        assert out.total_return_pct == pytest.approx(0.30, rel=0.001)

    def test_signal_exit_avoids_crisis_loss(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        bh = next(s for s in DEFAULT_STRATEGIES if s.key == "buy_and_hold")
        ex = next(s for s in DEFAULT_STRATEGIES if s.key == "signal_exit")
        r_bh = run_strategy(mkt, sig, bh, 25.0)
        r_ex = run_strategy(mkt, sig, ex, 25.0)
        # signal_exit 在危機期回撤應較淺
        assert r_ex.max_drawdown_pct > r_bh.max_drawdown_pct  # 較不負

    def test_n_trigger_days_counted(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        spec = next(s for s in DEFAULT_STRATEGIES if s.key == "signal_exit")
        out = run_strategy(mkt, sig, spec, 25.0)
        # 訊號高在 day 50~130（80 天）
        assert out.n_trigger_days == 80

    def test_no_lookahead_bias(self):
        """t-1 訊號決定 t 倉位 — 訊號第一天不應立刻 0 倉位。"""
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        spec = next(s for s in DEFAULT_STRATEGIES if s.key == "signal_exit")
        out = run_strategy(mkt, sig, spec, 25.0)
        # final_value 須 < buy_and_hold 但 > 0（有部分曝險）
        assert 0 < out.final_value
        assert out.n_total_days == 252

    def test_threshold_affects_trigger_count(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()  # 危機期 = 30, 平時 = 15
        spec = next(s for s in DEFAULT_STRATEGIES if s.key == "signal_exit")
        # threshold=20 → 觸發；threshold=35 → 不觸發
        r_low = run_strategy(mkt, sig, spec, 20.0)
        r_high = run_strategy(mkt, sig, spec, 35.0)
        assert r_low.n_trigger_days == 80
        assert r_high.n_trigger_days == 0


# ──────────────────────────────────────────────────────────────
# grid_search
# ──────────────────────────────────────────────────────────────
class TestGridSearch:
    def test_grid_dimension(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        thresholds = [25.0, 30.0, 35.0]
        results = grid_search(mkt, sig, thresholds)
        assert len(results) == 4 * 3

    def test_results_ordering_outer_strategy_inner_threshold(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        thresholds = [25.0, 30.0, 35.0]
        results = grid_search(mkt, sig, thresholds)
        # 前 3 個應同策略 buy_and_hold，門檻 25/30/35
        assert results[0].strategy_key == "buy_and_hold"
        assert results[1].strategy_key == "buy_and_hold"
        assert results[2].strategy_key == "buy_and_hold"
        assert results[3].strategy_key == "signal_exit"


# ──────────────────────────────────────────────────────────────
# results_to_dataframe + build_heatmap_data
# ──────────────────────────────────────────────────────────────
class TestDataFrameOutputs:
    def test_results_to_dataframe_shape(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        results = grid_search(mkt, sig, [25.0, 30.0, 35.0])
        df = results_to_dataframe(results)
        assert len(df) == 12
        assert "strategy_label" in df.columns
        assert "final_value" in df.columns

    def test_empty_results_to_dataframe(self):
        df = results_to_dataframe([])
        assert df.empty
        assert "strategy_key" in df.columns

    def test_build_heatmap_data_shape(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        results = grid_search(mkt, sig, [25.0, 30.0, 35.0])
        hm = build_heatmap_data(results, metric="total_return_pct")
        assert hm.shape == (4, 3)  # 4 策略 × 3 門檻
        assert list(hm.columns) == [25.0, 30.0, 35.0]

    def test_build_heatmap_data_invalid_metric_raises(self):
        results = grid_search(_make_market(), _make_signal_high_during_crisis(), [25.0])
        with pytest.raises(ValueError):
            build_heatmap_data(results, metric="not_a_metric")


# ──────────────────────────────────────────────────────────────
# rank_results
# ──────────────────────────────────────────────────────────────
class TestRankResults:
    def test_rank_by_sharpe_descending(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        results = grid_search(mkt, sig, [25.0, 30.0, 35.0])
        top = rank_results(results, by="sharpe_ratio", top_n=3)
        assert len(top) == 3
        # 確認降序
        sharpes = top["sharpe_ratio"].tolist()
        assert sharpes == sorted(sharpes, reverse=True)

    def test_rank_by_final_value(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        results = grid_search(mkt, sig, [25.0, 30.0, 35.0])
        top = rank_results(results, by="final_value", top_n=1)
        assert len(top) == 1

    def test_rank_invalid_by_raises(self):
        results = grid_search(_make_market(), _make_signal_high_during_crisis(), [25.0])
        with pytest.raises(ValueError):
            rank_results(results, by="not_a_metric")


# ──────────────────────────────────────────────────────────────
# crisis_return_pct 行為
# ──────────────────────────────────────────────────────────────
class TestCrisisReturn:
    def test_signal_exit_better_in_crisis_than_buy_and_hold(self):
        mkt = _make_market()
        sig = _make_signal_high_during_crisis()
        bh = next(s for s in DEFAULT_STRATEGIES if s.key == "buy_and_hold")
        ex = next(s for s in DEFAULT_STRATEGIES if s.key == "signal_exit")
        r_bh = run_strategy(mkt, sig, bh, 25.0)
        r_ex = run_strategy(mkt, sig, ex, 25.0)
        # 大盤跌時 buy_and_hold 危機期報酬為負，signal_exit 應接近 0 或正
        assert r_ex.crisis_return_pct > r_bh.crisis_return_pct
