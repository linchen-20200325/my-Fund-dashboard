"""tests/test_eval_macro_consensus.py — scripts/eval_macro_consensus.py smoke + 邊界."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

_spec = importlib.util.spec_from_file_location(
    "eval_macro_consensus",
    _REPO_ROOT / "scripts" / "eval_macro_consensus.py",
)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

from services.crisis_backtest import CrisisEvent  # noqa: E402


# ════════════════════════════════════════════════════════════════
# §1 build_factor_panel
# ════════════════════════════════════════════════════════════════
class TestBuildFactorPanel:
    def _fred(self, n=24):
        idx = pd.date_range("2020-01-31", periods=n, freq="ME")
        return pd.DataFrame({
            "DGS10": [2.5] * n,
            "DGS2": [1.0] * n,
            "DGS3MO": [0.5] * n,
            "BAMLH0A0HYM2": [3.5] * n,
            "CPIAUCSL": [260.0 + 0.5 * i for i in range(n)],
            "M2SL": [20000.0 + 100 * i for i in range(n)],
            "UNRATE": [4.5] * n,
            "WALCL": [8_000_000.0 + 1000 * i for i in range(n)],
        }, index=idx)

    def test_yield_spreads(self):
        fred = self._fred()
        vix = pd.Series([18.0] * 24, index=fred.index)
        panel = _mod.build_factor_panel(fred, vix)
        assert panel["YIELD_10Y2Y"].iloc[-1] == 1.5
        assert panel["YIELD_10Y3M"].iloc[-1] == 2.0

    def test_hy_spread_passthrough(self):
        fred = self._fred()
        vix = pd.Series([18.0] * 24, index=fred.index)
        panel = _mod.build_factor_panel(fred, vix)
        assert panel["HY_SPREAD"].iloc[-1] == 3.5

    def test_cpi_yoy_calculated(self):
        fred = self._fred(n=24)
        vix = pd.Series([18.0] * 24, index=fred.index)
        panel = _mod.build_factor_panel(fred, vix)
        # 月增 0.5，12 個月共 +6 → YoY ≈ 6/260 ≈ 2.3%
        cpi_yoy = panel["CPI"].iloc[-1]
        assert pd.notna(cpi_yoy)
        assert 1.5 < cpi_yoy < 3.0

    def test_fedrate_proxy_used(self):
        fred = self._fred()
        vix = pd.Series([18.0] * 24, index=fred.index)
        panel = _mod.build_factor_panel(fred, vix)
        assert panel["FEDRATE"].iloc[-1] == 0.5  # DGS3MO 值

    def test_vix_aligned(self):
        fred = self._fred()
        vix = pd.Series([22.0] * 24, index=fred.index)
        panel = _mod.build_factor_panel(fred, vix)
        assert panel["VIX"].iloc[-1] == 22.0

    def test_missing_series_skipped_gracefully(self):
        idx = pd.date_range("2020-01-31", periods=14, freq="ME")
        fred = pd.DataFrame({"DGS10": [2.0] * 14}, index=idx)
        vix = pd.Series([18.0] * 14, index=idx)
        panel = _mod.build_factor_panel(fred, vix)
        # 缺 DGS2 / DGS3MO → 無 spread columns
        assert "YIELD_10Y2Y" not in panel.columns
        assert "YIELD_10Y3M" not in panel.columns
        assert "FEDRATE" not in panel.columns
        # 缺 v19.29 新 series → 無 DXY / PPI / COPPER columns（9-factor fallback）
        assert "DXY" not in panel.columns
        assert "PPI" not in panel.columns
        assert "COPPER" not in panel.columns
        # VIX 仍出現
        assert "VIX" in panel.columns

    def test_v1929_dxy_factor_computed(self):
        """v19.29 補 DTWEXBGS → DXY 月變化 %."""
        idx = pd.date_range("2020-01-31", periods=24, freq="ME")
        # DTWEXBGS 月遞增 1%（每月 *1.01）
        dxy_vals = [100.0]
        for _ in range(23):
            dxy_vals.append(dxy_vals[-1] * 1.01)
        fred = pd.DataFrame({"DTWEXBGS": dxy_vals}, index=idx)
        vix = pd.Series([18.0] * 24, index=idx)
        panel = _mod.build_factor_panel(fred, vix)
        assert "DXY" in panel.columns
        # 每月 +1% → DXY 值應接近 1.0
        assert abs(panel["DXY"].iloc[-1] - 1.0) < 0.01

    def test_v1929_ppi_yoy_computed(self):
        """v19.29 補 PPIACO → PPI YoY %."""
        idx = pd.date_range("2020-01-31", periods=24, freq="ME")
        # PPIACO 12 個月 +6%（月 +0.5）→ YoY ~6%
        ppi_vals = [200.0 + 0.5 * i for i in range(24)]
        fred = pd.DataFrame({"PPIACO": ppi_vals}, index=idx)
        vix = pd.Series([18.0] * 24, index=idx)
        panel = _mod.build_factor_panel(fred, vix)
        assert "PPI" in panel.columns
        # YoY = 6/200 ≈ 3%
        ppi_yoy = panel["PPI"].iloc[-1]
        assert pd.notna(ppi_yoy)
        assert 2.5 < ppi_yoy < 3.5

    def test_v1929_copper_month_change_computed(self):
        """v19.29 補 PCOPPUSDM → Copper 月變化 %."""
        idx = pd.date_range("2020-01-31", periods=12, freq="ME")
        copper_vals = [7000.0 * (1.02 ** i) for i in range(12)]  # 月 +2%
        fred = pd.DataFrame({"PCOPPUSDM": copper_vals}, index=idx)
        vix = pd.Series([18.0] * 12, index=idx)
        panel = _mod.build_factor_panel(fred, vix)
        assert "COPPER" in panel.columns
        assert abs(panel["COPPER"].iloc[-1] - 2.0) < 0.01

    def test_v1929_full_12_factor_panel(self):
        """v19.29 bootstrap 後 full 12-factor panel."""
        idx = pd.date_range("2020-01-31", periods=24, freq="ME")
        fred = pd.DataFrame({
            "DGS10": [2.5] * 24, "DGS2": [1.0] * 24, "DGS3MO": [0.5] * 24,
            "BAMLH0A0HYM2": [3.5] * 24,
            "CPIAUCSL": [260.0 + 0.5 * i for i in range(24)],
            "M2SL": [20000.0 + 100 * i for i in range(24)],
            "UNRATE": [4.5] * 24,
            "WALCL": [8e6 + 1000 * i for i in range(24)],
            "DTWEXBGS": [100.0 + 0.5 * i for i in range(24)],
            "PPIACO": [200.0 + 0.5 * i for i in range(24)],
            "PCOPPUSDM": [7000.0 + 50 * i for i in range(24)],
        }, index=idx)
        vix = pd.Series([18.0] * 24, index=idx)
        panel = _mod.build_factor_panel(fred, vix)
        # 12 factor + VIX = 13 column（不含 BREADTH/PMI）
        expected = {"YIELD_10Y2Y", "YIELD_10Y3M", "HY_SPREAD", "M2", "CPI",
                    "FEDRATE", "UNEMP", "FED_BS", "DXY", "PPI", "COPPER", "VIX"}
        assert expected.issubset(set(panel.columns))


# ════════════════════════════════════════════════════════════════
# §2 strategy_b_radar_proxy
# ════════════════════════════════════════════════════════════════
class TestStrategyBRadarProxy:
    def _ev(self, peak: pd.Timestamp, dd: float = -0.30) -> CrisisEvent:
        return CrisisEvent(
            market="SPX",
            peak_date=peak,
            trough_date=peak + pd.DateOffset(months=2),
            recovery_date=None,
            peak_value=4000.0,
            trough_value=4000.0 * (1 + dd),
            drawdown_pct=dd,
            duration_days=60,
            recovery_days=None,
        )

    def test_radar_hit_when_a_misses(self):
        idx = pd.date_range("2019-01-31", periods=24, freq="ME")
        score = pd.DataFrame({"score": [5.0] * 24}, index=idx)
        vix = pd.DataFrame({
            "vix_close": [18.0] * 24,
            "vix_mean": [18.0] * 22 + [45.0, 50.0],
        }, index=idx)
        ev = self._ev(idx[-1])
        results = _mod.strategy_b_radar_proxy(
            score, [ev], vix,
            radar_threshold=30.0, lookback_months=3,
        )
        assert results[0]["a_hit"] is False
        assert results[0]["b_radar_hit"] is True
        assert results[0]["combined_pre_hit"] is True
        assert results[0]["b_vix_max"] == 50.0

    def test_calm_vix_no_radar_hit(self):
        idx = pd.date_range("2017-01-31", periods=12, freq="ME")
        score = pd.DataFrame({"score": [5.0] * 12}, index=idx)
        vix = pd.DataFrame({
            "vix_close": [15.0] * 12,
            "vix_mean": [15.0] * 12,
        }, index=idx)
        ev = self._ev(idx[-1], dd=-0.05)
        results = _mod.strategy_b_radar_proxy(
            score, [ev], vix,
            radar_threshold=30.0, lookback_months=3,
        )
        assert results[0]["b_radar_hit"] is False
        assert results[0]["combined_pre_hit"] is False

    def test_long_term_hit_a_alone_passes_combined(self):
        idx = pd.date_range("2019-01-31", periods=24, freq="ME")
        # score 從 8 → 4 = drop 50% (遠超 20% drop_threshold)
        # lead window 預設 6 月 → idx[-7] = 8.0, idx[-1] = 4.0
        scores = [8.0] * 18 + [7.0, 6.0, 5.5, 5.0, 4.5, 4.0]
        score = pd.DataFrame({"score": scores}, index=idx)
        vix = pd.DataFrame({
            "vix_close": [15.0] * 24,
            "vix_mean": [15.0] * 24,
        }, index=idx)
        ev = self._ev(idx[-1])
        results = _mod.strategy_b_radar_proxy(
            score, [ev], vix,
            radar_threshold=30.0, lookback_months=3,
        )
        assert results[0]["a_hit"] is True
        assert results[0]["b_radar_hit"] is False
        assert results[0]["combined_pre_hit"] is True

    def test_both_hit(self):
        idx = pd.date_range("2019-01-31", periods=24, freq="ME")
        scores = [8.0] * 18 + [7.0, 6.0, 5.5, 5.0, 4.5, 4.0]
        score = pd.DataFrame({"score": scores}, index=idx)
        vix = pd.DataFrame({
            "vix_close": [15.0] * 24,
            "vix_mean": [15.0] * 22 + [40.0, 55.0],
        }, index=idx)
        ev = self._ev(idx[-1])
        results = _mod.strategy_b_radar_proxy(
            score, [ev], vix,
            radar_threshold=30.0, lookback_months=3,
        )
        assert results[0]["a_hit"] is True
        assert results[0]["b_radar_hit"] is True
        assert results[0]["combined_pre_hit"] is True

    def test_during_radar_hits_when_pre_misses(self):
        """C 策略覆蓋 dual_verdict real-time 防守設計：peak 之後才 spike 也算."""
        idx = pd.date_range("2019-01-31", periods=24, freq="ME")
        score = pd.DataFrame({"score": [5.0] * 24}, index=idx)
        # peak 之前 VIX 平靜，peak → trough 之間才 spike
        vix = pd.DataFrame({
            "vix_close": [15.0] * 24,
            "vix_mean": [15.0] * 22 + [55.0, 45.0],
        }, index=idx)
        # peak = idx[-3]，trough = idx[-1]，pre window 看 idx[-6:-3] 都 15
        peak = idx[-3]
        ev = CrisisEvent(
            market="SPX",
            peak_date=peak,
            trough_date=idx[-1],
            recovery_date=None,
            peak_value=4000.0,
            trough_value=2800.0,
            drawdown_pct=-0.30,
            duration_days=60,
            recovery_days=None,
        )
        results = _mod.strategy_b_radar_proxy(
            score, [ev], vix,
            radar_threshold=30.0, lookback_months=3,
        )
        assert results[0]["b_radar_hit"] is False  # peak 前平靜
        assert results[0]["c_radar_hit"] is True   # peak → trough 期間 spike
        assert results[0]["combined_pre_hit"] is False
        assert results[0]["combined_during_hit"] is True

    def test_empty_events_returns_empty(self):
        idx = pd.date_range("2019-01-31", periods=12, freq="ME")
        score = pd.DataFrame({"score": [5.0] * 12}, index=idx)
        vix = pd.DataFrame({
            "vix_close": [15.0] * 12,
            "vix_mean": [15.0] * 12,
        }, index=idx)
        results = _mod.strategy_b_radar_proxy(score, [], vix)
        assert results == []


# ════════════════════════════════════════════════════════════════
# §3 print_table 不爆 + 處理空表
# ════════════════════════════════════════════════════════════════
class TestPrintTable:
    def test_empty_results(self, capsys):
        _mod.print_table(
            [],
            lead_months=6, drop_threshold=0.2,
            radar_threshold=30.0, radar_lookback=3,
        )
        out = capsys.readouterr().out
        assert "純長期" in out

    def test_renders_row(self, capsys):
        results = [{
            "peak_date": pd.Timestamp("2020-02-29"),
            "trough_date": pd.Timestamp("2020-03-31"),
            "drawdown": -0.34,
            "a_hit": False,
            "a_drop": -0.05,
            "a_score_lead": 6.0,
            "a_score_peak": 5.7,
            "b_radar_hit": False,
            "b_vix_max": 18.0,
            "c_radar_hit": True,
            "c_vix_max": 60.0,
            "combined_pre_hit": False,
            "combined_during_hit": True,
        }]
        _mod.print_table(
            results,
            lead_months=6, drop_threshold=0.2,
            radar_threshold=30.0, radar_lookback=3,
        )
        out = capsys.readouterr().out
        assert "2020-02" in out
        assert "60.0" in out
        assert "✅" in out
