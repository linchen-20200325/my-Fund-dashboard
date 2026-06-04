"""test_multi_factor_optimization.py — v18.285 多因子權重最佳化引擎驗收."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from services.crisis_backtest import CrisisEvent
from services.multi_factor_optimization import (
    FACTOR_POOL,
    FACTOR_POOL_BY_KEY,
    build_plateau_heatmap_2d,
    build_plateau_surface_3d,
    compute_composite_score,
    evaluate_f1,
    evaluate_plateau,
    evaluate_sharpe,
    find_plateau_optimum,
    generate_simplex_grid,
    grid_search_performance,
    score_to_signal,
    walk_forward_validate,
)


def _mock_event(peak: str) -> CrisisEvent:
    p = pd.Timestamp(peak)
    return CrisisEvent(
        market="SPX",
        peak_date=p,
        trough_date=p + pd.Timedelta(days=60),
        recovery_date=None,
        peak_value=100.0,
        trough_value=85.0,
        drawdown_pct=-0.15,
        duration_days=60,
        recovery_days=None,
    )


def _mock_factor_series(n: int = 1500, seed: int = 1) -> dict[str, pd.Series]:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    out = {}
    for f in FACTOR_POOL[:4]:
        out[f.key] = pd.Series(rng.normal(0, 1, n).cumsum() / 10 + 20.0,
                               index=idx, name=f.key)
    return out


def _mock_returns(n: int = 1500, seed: int = 2) -> pd.Series:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2018-01-01", periods=n, freq="D")
    price = 100 * (1 + rng.normal(0, 0.01, n)).cumprod()
    return pd.Series(price, index=idx, name="SPX")


class TestComputeCompositeScore:
    def test_empty_weights_raises(self):
        with pytest.raises(ValueError):
            compute_composite_score({}, {})

    def test_lag_prevents_future_leak(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="D")
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
                      index=idx, name="VIX")
        score = compute_composite_score({"VIX": s}, {"VIX": 1.0}, lag_days=1)
        assert score.index[0] >= idx[1]

    def test_zero_weight_skipped(self):
        idx = pd.date_range("2020-01-01", periods=50, freq="D")
        s_a = pd.Series(np.arange(50, dtype=float), index=idx, name="VIX")
        s_b = pd.Series(np.arange(50, dtype=float) * 2, index=idx, name="UNRATE")
        sc_one = compute_composite_score({"VIX": s_a, "UNRATE": s_b},
                                          {"VIX": 1.0, "UNRATE": 0.0})
        sc_two = compute_composite_score({"VIX": s_a}, {"VIX": 1.0})
        assert np.allclose(sc_one.values, sc_two.values)

    def test_direction_below_flips_sign(self):
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        s = pd.Series(np.arange(30, dtype=float), index=idx, name="T10Y2Y")
        sc = compute_composite_score({"T10Y2Y": s}, {"T10Y2Y": 1.0})
        assert sc.iloc[0] > sc.iloc[-1]


class TestScoreToSignal:
    def test_edge_detection_only_crossings(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="D")
        score = pd.Series([0.5, 0.5, 1.5, 1.5, 0.5, 1.5, 1.5, 1.5, 0.5, 1.5],
                          index=idx)
        cross = score_to_signal(score, threshold=1.0)
        assert cross.sum() == 3
        assert cross.iloc[2] == 1 and cross.iloc[3] == 0


class TestEvaluateF1:
    def test_empty_returns_zero(self):
        stat = evaluate_f1(pd.Series(dtype=int), [])
        assert stat["f1"] == 0.0

    def test_no_crossings_returns_zero(self):
        idx = pd.date_range("2020-01-01", periods=10, freq="D")
        cross = pd.Series([0] * 10, index=idx)
        stat = evaluate_f1(cross, [_mock_event("2020-01-05")])
        assert stat["f1"] == 0.0

    def test_perfect_hit_gives_one(self):
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        cross = pd.Series([0] * 30, index=idx)
        cross.iloc[0] = 1
        stat = evaluate_f1(cross, [_mock_event("2020-01-10")],
                           max_forward_days=30)
        assert stat["precision"] == 1.0
        assert stat["recall"] == 1.0
        assert stat["f1"] == 1.0


class TestEvaluateSharpe:
    def test_empty_returns_zero(self):
        stat = evaluate_sharpe(pd.Series(dtype=int), pd.Series(dtype=float))
        assert stat["sharpe"] == 0.0

    def test_no_trades_returns_zero(self):
        idx = pd.date_range("2020-01-01", periods=100, freq="D")
        cross = pd.Series([0] * 100, index=idx)
        ret = pd.Series(np.random.default_rng(0).normal(100, 1, 100), index=idx)
        stat = evaluate_sharpe(cross, ret)
        assert stat["n_trades"] == 0


class TestGenerateSimplexGrid:
    def test_2d_step_05_gives_3_points(self):
        combos = generate_simplex_grid(["A", "B"], step=0.5)
        assert len(combos) == 3
        assert all(abs(sum(w.values()) - 1.0) < 1e-9 for w in combos)

    def test_3d_step_05_gives_6_points(self):
        combos = generate_simplex_grid(["A", "B", "C"], step=0.5)
        assert len(combos) == 6
        assert all(abs(sum(w.values()) - 1.0) < 1e-9 for w in combos)

    def test_empty_keys_returns_empty(self):
        assert generate_simplex_grid([], 0.2) == []

    def test_invalid_step_returns_empty(self):
        assert generate_simplex_grid(["A"], step=0) == []
        assert generate_simplex_grid(["A"], step=2.0) == []


class TestGridSearchPerformance:
    def test_empty_factors_returns_empty(self):
        result = grid_search_performance({}, pd.Series(dtype=float), [], [],
                                          step=0.5)
        assert len(result["combos"]) == 0

    def test_basic_run_has_combos(self):
        factor_series = _mock_factor_series(500)
        returns = _mock_returns(500)
        events = [_mock_event(str((pd.Timestamp("2018-06-01")
                                    + pd.Timedelta(days=i * 100)).date()))
                  for i in range(3)]
        result = grid_search_performance(
            factor_series, returns, events,
            ["VIX", "HY_SPREAD"], step=0.5,
        )
        assert len(result["combos"]) == 3
        assert result["f1"].shape == (3,)
        assert result["sharpe"].shape == (3,)


class TestEvaluatePlateau:
    def test_empty_returns_empty(self):
        result = {"combos": [], "f1": np.array([]), "sharpe": np.array([]),
                  "n_crossings": np.array([])}
        plateau = evaluate_plateau(result, [], 0.5)
        assert len(plateau) == 0

    def test_flat_perf_interior_beats_corner_v19_8(self):
        """v19.8 F4：即使績效全平，corner 點鄰居 < interior → plateau lower."""
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        f1 = np.array([0.6, 0.6, 0.6])
        result = {"combos": combos, "f1": f1, "sharpe": f1.copy(),
                  "n_crossings": np.array([10, 10, 10])}
        plateau = evaluate_plateau(result, ["A", "B"], step=0.5, radius=1,
                                   lambda_std=0.5)
        # interior (center) 鄰居=3=max；corner 鄰居=2 → sqrt(2/3)≈0.816
        assert plateau[1] == pytest.approx(0.6, abs=1e-9)
        assert plateau[0] == pytest.approx(0.6 * np.sqrt(2 / 3), abs=1e-9)
        assert plateau[2] == pytest.approx(0.6 * np.sqrt(2 / 3), abs=1e-9)
        assert plateau[0] < plateau[1]

    def test_low_n_crossings_filtered_to_minus_inf_v19_8_F3(self):
        """v19.8 F3：n_crossings < min_crossings → plateau = -inf."""
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        f1 = np.array([0.9, 0.5, 0.5])  # corner 假高 F1
        result = {"combos": combos, "f1": f1, "sharpe": f1.copy(),
                  "n_crossings": np.array([1, 5, 5])}  # corner 只 1 次觸發
        plateau = evaluate_plateau(result, ["A", "B"], step=0.5, radius=1,
                                   lambda_std=0.5, min_crossings=2)
        assert plateau[0] == -np.inf
        assert np.isfinite(plateau[1])
        assert np.isfinite(plateau[2])

    def test_corner_vertex_loses_to_interior_v19_8(self):
        """v19.8 整合 F3+F4：合理場景下 interior 應贏 corner。

        Corner F1=0.9 但只 1 次觸發（偽贏家），interior F1=0.6 但 5 次觸發。
        """
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        f1 = np.array([0.9, 0.6, 0.5])
        result = {"combos": combos, "f1": f1, "sharpe": f1.copy(),
                  "n_crossings": np.array([1, 5, 5])}
        plateau = evaluate_plateau(result, ["A", "B"], step=0.5, radius=1,
                                   lambda_std=0.5)
        winner = int(np.argmax(plateau))
        assert winner == 1, f"interior 應贏，實際 winner={winner}, plateau={plateau}"


class TestFindPlateauOptimum:
    def test_empty_returns_zero(self):
        result = {"combos": [], "f1": np.array([]), "sharpe": np.array([]),
                  "n_crossings": np.array([])}
        opt = find_plateau_optimum(result, np.array([]))
        assert opt["argmax_idx"] == -1

    def test_returns_argmax(self):
        combos = [{"A": 1.0}, {"A": 0.5}, {"A": 0.0}]
        result = {"combos": combos, "f1": np.array([0.1, 0.5, 0.2]),
                  "sharpe": np.array([0, 0, 0]),
                  "n_crossings": np.array([1, 1, 1])}
        opt = find_plateau_optimum(result, np.array([0.1, 0.7, 0.2]))
        assert opt["argmax_idx"] == 1
        assert opt["weights"] == {"A": 0.5}

    def test_all_minus_inf_returns_empty_v19_8(self):
        """v19.8：F3 全濾掉 → find_plateau_optimum 回空 weights（不亂選 idx=0）。"""
        combos = [{"A": 1.0}, {"A": 0.5}, {"A": 0.0}]
        result = {"combos": combos, "f1": np.array([0.1, 0.5, 0.2]),
                  "sharpe": np.array([0, 0, 0]),
                  "n_crossings": np.array([1, 1, 1])}
        opt = find_plateau_optimum(result, np.array([-np.inf, -np.inf, -np.inf]))
        assert opt["argmax_idx"] == -1
        assert opt["weights"] == {}


class TestWalkForwardValidate:
    def test_no_factors_returns_empty(self):
        result = walk_forward_validate({}, pd.Series(dtype=float), [], [])
        assert result["n_folds"] == 0
        assert result["status"] == "no_factors"

    def test_window_larger_than_data_returns_empty(self):
        idx = pd.date_range("2020-01-01", periods=30, freq="D")
        s = pd.Series(np.arange(30, dtype=float), index=idx, name="VIX")
        result = walk_forward_validate(
            {"VIX": s}, pd.Series(dtype=float), [], ["VIX"],
            train_months=12, test_months=6, step=0.5,
        )
        assert result["status"] == "window_larger_than_data"

    def test_basic_walk_forward_produces_folds(self):
        factor_series = _mock_factor_series(1500)
        returns = _mock_returns(1500)
        events = [_mock_event(str((pd.Timestamp("2019-06-01")
                                    + pd.Timedelta(days=i * 180)).date()))
                  for i in range(5)]
        result = walk_forward_validate(
            factor_series, returns, events, ["VIX", "HY_SPREAD"],
            train_months=12, test_months=6, step=0.5,
        )
        assert result["n_folds"] >= 1
        for fold in result["folds"]:
            assert sum(fold["weights"].values()) == pytest.approx(1.0, abs=1e-9)


class TestPlotlyFigures:
    def test_2d_heatmap_returns_figure(self):
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        result = {"combos": combos, "f1": np.array([0.3, 0.5, 0.4]),
                  "sharpe": np.array([0, 0, 0]),
                  "n_crossings": np.array([1, 1, 1])}
        fig = build_plateau_heatmap_2d(result, np.array([0.3, 0.5, 0.4]),
                                       ["A", "B"], ("A", "B"))
        assert fig is not None
        assert len(fig.data) == 1

    def test_3d_surface_returns_figure(self):
        combos = [{"A": 1.0, "B": 0.0},
                  {"A": 0.5, "B": 0.5},
                  {"A": 0.0, "B": 1.0}]
        result = {"combos": combos, "f1": np.array([0.3, 0.5, 0.4]),
                  "sharpe": np.array([0, 0, 0]),
                  "n_crossings": np.array([1, 1, 1])}
        fig = build_plateau_surface_3d(result, np.array([0.3, 0.5, 0.4]),
                                       ["A", "B"], ("A", "B"))
        assert fig is not None
        assert len(fig.data) == 1


class TestFactorPool:
    def test_pool_size(self):
        # v19.4: 13 → 23（+ SAHM / SLOOS / LEI / PPI / JOBLESS / CONT_CLAIMS /
        #                    CONSUMER_CONF / PERMIT_HOUSING / FED_BS / INFL_EXP_5Y）
        assert len(FACTOR_POOL) == 23

    def test_keys_unique(self):
        keys = [f.key for f in FACTOR_POOL]
        assert len(set(keys)) == len(keys)

    def test_lookup_by_key(self):
        assert FACTOR_POOL_BY_KEY["VIX"].source == "yahoo"

    def test_v18_286_new_factors_present(self):
        assert "MOVE" in FACTOR_POOL_BY_KEY
        assert "NFCI" in FACTOR_POOL_BY_KEY
        assert "COPPER_GOLD_RATIO" in FACTOR_POOL_BY_KEY

    def test_v18_286_factor_metadata(self):
        move = FACTOR_POOL_BY_KEY["MOVE"]
        assert move.source == "yahoo" and move.series_id == "^MOVE" and move.direction == "above"
        nfci = FACTOR_POOL_BY_KEY["NFCI"]
        assert nfci.source == "fred" and nfci.series_id == "NFCI" and nfci.direction == "above"
        cg = FACTOR_POOL_BY_KEY["COPPER_GOLD_RATIO"]
        assert cg.source == "calculated" and cg.direction == "below"


class TestV19_4FactorPool:
    """v19.4：FACTOR_POOL 13 → 23，補 10 個 FRED 因子。"""

    _NEW_KEYS = [
        "SAHM", "SLOOS", "LEI", "PPI", "JOBLESS", "CONT_CLAIMS",
        "CONSUMER_CONF", "PERMIT_HOUSING", "FED_BS", "INFL_EXP_5Y",
    ]
    _EXPECTED = {
        "SAHM":            ("SAHMCURRENT", "above"),
        "SLOOS":           ("DRTSCILM",    "above"),
        "LEI":             ("USSLIND",     "below"),
        "PPI":             ("PPIACO",      "above"),
        "JOBLESS":         ("ICSA",        "above"),
        "CONT_CLAIMS":     ("CCSA",        "above"),
        "CONSUMER_CONF":   ("UMCSENT",     "below"),
        "PERMIT_HOUSING":  ("PERMIT",      "below"),
        "FED_BS":          ("WALCL",       "below"),
        "INFL_EXP_5Y":     ("T5YIE",       "above"),
    }

    def test_all_new_keys_present(self):
        for k in self._NEW_KEYS:
            assert k in FACTOR_POOL_BY_KEY, f"{k} 漏加進 FACTOR_POOL"

    def test_all_new_are_fred_source(self):
        for k in self._NEW_KEYS:
            assert FACTOR_POOL_BY_KEY[k].source == "fred", f"{k} source 應為 fred"

    def test_series_id_and_direction_correct(self):
        for k, (sid, dirn) in self._EXPECTED.items():
            spec = FACTOR_POOL_BY_KEY[k]
            assert spec.series_id == sid, f"{k} series_id 應為 {sid}"
            assert spec.direction == dirn, f"{k} direction 應為 {dirn}"

    def test_series_ids_unique_across_pool(self):
        # 不允許 series_id 重複（FRED ID 衝突會抓同一條 series）
        sids = [f.series_id for f in FACTOR_POOL]
        assert len(set(sids)) == len(sids), f"series_id 重複：{sids}"

    def test_all_new_have_note(self):
        for k in self._NEW_KEYS:
            assert FACTOR_POOL_BY_KEY[k].note, f"{k} note 為空"


class TestFetchFactorSeries:
    """v18.286 lazy fetch helper — 3 source types。"""

    def test_yahoo_source_calls_fetch_yf_close(self, monkeypatch):
        from services import multi_factor_optimization as mfo
        called = {}

        def _fake(ticker, range_="2y", interval="1d"):
            called["ticker"] = ticker
            return pd.Series([10.0, 11.0, 12.0],
                             index=pd.date_range("2024-01-01", periods=3))

        monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _fake)
        s = mfo.fetch_factor_series(mfo.FACTOR_POOL_BY_KEY["MOVE"], years=5)
        assert called["ticker"] == "^MOVE"
        assert len(s) == 3
        assert s.name == "MOVE"

    def test_fred_source_calls_fetch_fred(self, monkeypatch):
        from services import multi_factor_optimization as mfo
        called = {}

        def _fake(sid, key, n=250):
            called["sid"] = sid
            return pd.DataFrame({
                "date": pd.date_range("2024-01-01", periods=3),
                "value": [0.1, 0.2, 0.3],
            })

        monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fake)
        s = mfo.fetch_factor_series(mfo.FACTOR_POOL_BY_KEY["NFCI"],
                                    years=3, fred_api_key="dummy")
        assert called["sid"] == "NFCI"
        assert len(s) == 3

    def test_calculated_copper_gold(self, monkeypatch):
        from services import multi_factor_optimization as mfo
        seen = []

        def _fake_yf(ticker, range_="2y", interval="1d"):
            seen.append(ticker)
            base = 4.0 if ticker == "HG=F" else 2000.0
            return pd.Series([base, base + 0.1, base + 0.2],
                             index=pd.date_range("2024-01-01", periods=3))

        monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _fake_yf)
        s = mfo.fetch_factor_series(mfo.FACTOR_POOL_BY_KEY["COPPER_GOLD_RATIO"],
                                    years=5)
        assert set(seen) == {"HG=F", "GC=F"}
        assert len(s) == 3
        assert s.iloc[0] == pytest.approx(4.0 / 2000.0)

    def test_empty_on_fetcher_failure(self, monkeypatch):
        from services import multi_factor_optimization as mfo
        monkeypatch.setattr(
            "repositories.macro_repository.fetch_yf_close",
            lambda *a, **k: pd.Series(dtype=float),
        )
        s = mfo.fetch_factor_series(mfo.FACTOR_POOL_BY_KEY["MOVE"], years=1)
        assert s.empty


# ════════════════════════════════════════════════════════════════
# v19.2 hotfix：empty series 必須是 DatetimeIndex 避免 walk-forward TypeError
# ════════════════════════════════════════════════════════════════
class TestEmptyFactorSeriesIndexType:
    """v18.296 引入的 bug：fetch 失敗時回 RangeIndex 空 Series，
    下游 _slice_series 做 ``RangeIndex >= Timestamp`` 比較直接 TypeError 全爆。"""

    def test_fetch_failure_returns_datetime_indexed_empty(self, monkeypatch):
        """yahoo / fred / calculated 三條失敗 path 都要回 DatetimeIndex。"""
        from services import multi_factor_optimization as mfo

        # 模擬 fetch_yf_close 回 None（網路失敗）
        def _yf_fail(*args, **kwargs):
            return None
        monkeypatch.setattr(
            "repositories.macro_repository.fetch_yf_close", _yf_fail,
        )

        # yahoo 路徑
        spec_y = mfo.FactorSpec("X", "X", "yahoo", "BAD", "above")
        s_y = mfo.fetch_factor_series(spec_y, years=1)
        assert s_y.empty
        assert isinstance(s_y.index, pd.DatetimeIndex), \
            f"yahoo empty 應為 DatetimeIndex，實際 {type(s_y.index).__name__}"

        # calculated 路徑（依賴 yahoo）
        spec_c = mfo.FactorSpec(
            "COPPER_GOLD_RATIO", "銅金比", "calculated", "HG=F/GC=F", "below",
        )
        s_c = mfo.fetch_factor_series(spec_c, years=1)
        assert s_c.empty
        assert isinstance(s_c.index, pd.DatetimeIndex)

    def test_slice_series_skips_non_datetime_indexed(self):
        """``_slice_series`` 對誤入的 RangeIndex empty Series 必須回 empty DatetimeIndex，
        不能爆 TypeError。"""
        from services import multi_factor_optimization as mfo

        # 一好一壞：good 是 DatetimeIndex，bad 是預設 RangeIndex
        good = pd.Series(
            [1.0, 2.0, 3.0],
            index=pd.date_range("2020-01-01", periods=3, freq="D"),
            name="GOOD",
        )
        bad = pd.Series(dtype=float, name="BAD")  # default RangeIndex
        start = pd.Timestamp("2020-01-01")
        end = pd.Timestamp("2020-01-05")

        # 修補前這行會 TypeError
        out = mfo._slice_series({"GOOD": good, "BAD": bad}, start, end)
        assert len(out["GOOD"]) == 3
        assert out["BAD"].empty
        assert isinstance(out["BAD"].index, pd.DatetimeIndex)

    def test_walk_forward_handles_mixed_empty_factors(self):
        """walk_forward_validate 收到「部分因子抓失敗（空）」應正常跑完不爆。"""
        from services import multi_factor_optimization as mfo

        good = pd.Series(
            np.random.RandomState(42).randn(500),
            index=pd.date_range("2018-01-01", periods=500, freq="D"),
            name="GOOD",
        )
        bad = pd.Series(dtype=float, name="BAD")
        returns = pd.Series(
            np.random.RandomState(7).randn(500) * 0.01,
            index=good.index, name="ret",
        )

        # 應正常 return（可能 status 不 ok 但不爆 TypeError）
        result = mfo.walk_forward_validate(
            {"GOOD": good, "BAD": bad}, returns, [], ["GOOD", "BAD"],
            train_months=6, test_months=3,
        )
        assert "folds" in result
        assert "n_folds" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
