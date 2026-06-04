"""test_macro_signal_lookback.py — Phase 3 訊號回看引擎測試 (v18.260)

驗證：
- _is_warning 雙向判讀
- evaluate_signal_at_event 對空序列 / 不涵蓋 / 涵蓋 / 警戒命中 / lead_time 計算
- lookback_all_signals 批次串接
- compute_signal_hit_rate 統計正確性
- fetch_signal_series Yahoo / FRED wrapper（monkeypatch）
"""
from __future__ import annotations

import pandas as pd

from services.crisis_backtest import CrisisEvent
from services.macro_signal_lookback import (
    DEFAULT_SIGNALS,
    SignalLookback,
    SignalSpec,
    _is_warning,
    compute_signal_hit_rate,
    evaluate_signal_at_event,
    fetch_signal_series,
    lookback_all_signals,
)


def _event(peak: str = "2024-06-01", trough: str = "2024-07-01") -> CrisisEvent:
    return CrisisEvent(
        market="SPX",
        peak_date=pd.Timestamp(peak),
        trough_date=pd.Timestamp(trough),
        recovery_date=None,
        peak_value=100.0,
        trough_value=85.0,
        drawdown_pct=-0.15,
        duration_days=30,
        recovery_days=None,
    )


def _spec_above(thr: float = 25.0) -> SignalSpec:
    return SignalSpec(
        key="VIX", label="VIX 恐慌指數", source="yahoo",
        series_id="^VIX", threshold=thr, direction="above",
    )


def _spec_below(thr: float = 0.0) -> SignalSpec:
    return SignalSpec(
        key="T10Y2Y", label="10Y-2Y", source="fred",
        series_id="T10Y2Y", threshold=thr, direction="below",
    )


# ──────────────────────────────────────────────────────────────
# _is_warning
# ──────────────────────────────────────────────────────────────
class TestIsWarning:
    def test_above_triggers_when_ge_threshold(self):
        assert _is_warning(30.0, 25.0, "above") is True
        assert _is_warning(25.0, 25.0, "above") is True  # 等於也算
        assert _is_warning(24.9, 25.0, "above") is False

    def test_below_triggers_when_le_threshold(self):
        assert _is_warning(-0.1, 0.0, "below") is True
        assert _is_warning(0.0, 0.0, "below") is True
        assert _is_warning(0.1, 0.0, "below") is False


# ──────────────────────────────────────────────────────────────
# DEFAULT_SIGNALS 完整性
# ──────────────────────────────────────────────────────────────
class TestDefaultSignals:
    def test_default_signals_has_four(self):
        keys = {s.key for s in DEFAULT_SIGNALS}
        assert keys == {"VIX", "HY_SPREAD", "T10Y2Y", "UNRATE"}

    def test_t10y2y_direction_is_below(self):
        spec = next(s for s in DEFAULT_SIGNALS if s.key == "T10Y2Y")
        assert spec.direction == "below"
        assert spec.threshold == 0.0


# ──────────────────────────────────────────────────────────────
# evaluate_signal_at_event
# ──────────────────────────────────────────────────────────────
class TestEvaluateSignalAtEvent:
    def test_empty_series_returns_none_fields(self):
        ev = _event()
        out = evaluate_signal_at_event(ev, pd.Series(dtype=float), _spec_above())
        assert out.value_at_lookback is None
        assert out.triggered_at_lookback is False
        assert out.first_warning_date is None
        assert out.lead_time_days is None

    def test_series_entirely_after_peak_returns_none(self):
        ev = _event(peak="2024-06-01")
        # 序列全在 peak 之後
        s = pd.Series(
            [10, 12, 14],
            index=pd.date_range("2024-07-01", periods=3, freq="D"),
            name="VIX",
        )
        out = evaluate_signal_at_event(ev, s, _spec_above())
        assert out.value_at_lookback is None
        assert out.first_warning_date is None

    def test_value_at_lookback_takes_last_before_target(self):
        # peak=2024-06-01, lookback=90 → target≈2024-03-03
        ev = _event(peak="2024-06-01")
        s = pd.Series(
            [10, 20, 30, 40],
            index=pd.to_datetime(["2024-01-15", "2024-02-15", "2024-04-15", "2024-05-15"]),
            name="VIX",
        )
        # ≤ 2024-03-03 最後一筆 = 2024-02-15 = 20
        out = evaluate_signal_at_event(ev, s, _spec_above(thr=25.0), lookback_days=90)
        assert out.value_at_lookback == 20.0
        assert out.triggered_at_lookback is False  # 20 < 25

    def test_triggered_at_lookback_when_above_threshold(self):
        ev = _event(peak="2024-06-01")
        s = pd.Series(
            [30, 32],
            index=pd.to_datetime(["2024-02-15", "2024-04-15"]),
            name="VIX",
        )
        # target=03-03, ≤target 最後筆=02-15 → 30 ≥ 25
        out = evaluate_signal_at_event(ev, s, _spec_above(thr=25.0), lookback_days=90)
        assert out.value_at_lookback == 30.0
        assert out.triggered_at_lookback is True

    def test_lead_time_picks_first_warning_within_window(self):
        # peak=2024-06-01, max_lookback=180 → 區間=2023-12-04 ~ 2024-06-01
        ev = _event(peak="2024-06-01")
        # 訊號值：03-01 進警戒, 04-01 進警戒, 05-01 出警戒
        s = pd.Series(
            [10, 30, 35, 20],
            index=pd.to_datetime(["2024-01-01", "2024-03-01", "2024-04-01", "2024-05-01"]),
            name="VIX",
        )
        out = evaluate_signal_at_event(
            ev, s, _spec_above(thr=25.0),
            lookback_days=90, max_lookback_days=180,
        )
        # 第一次警戒 = 2024-03-01, lead = (06-01) - (03-01) = 92 天
        assert out.first_warning_date == pd.Timestamp("2024-03-01")
        assert out.lead_time_days == 92

    def test_no_warning_in_window_returns_none_lead(self):
        ev = _event(peak="2024-06-01")
        s = pd.Series(
            [10, 12, 15],
            index=pd.date_range("2024-01-01", periods=3, freq="30D"),
            name="VIX",
        )
        out = evaluate_signal_at_event(ev, s, _spec_above(thr=25.0))
        assert out.lead_time_days is None
        assert out.first_warning_date is None

    def test_below_direction_works(self):
        # T10Y2Y 倒掛：值 < 0 算警戒
        ev = _event(peak="2024-06-01")
        s = pd.Series(
            [0.5, -0.2, -0.3, 0.1],
            index=pd.to_datetime(["2024-01-01", "2024-02-01", "2024-03-01", "2024-05-01"]),
            name="T10Y2Y",
        )
        out = evaluate_signal_at_event(
            ev, s, _spec_below(thr=0.0),
            lookback_days=90, max_lookback_days=365,
        )
        # 第一次警戒 = 2024-02-01
        assert out.first_warning_date == pd.Timestamp("2024-02-01")
        assert out.lead_time_days == (pd.Timestamp("2024-06-01") - pd.Timestamp("2024-02-01")).days


# ──────────────────────────────────────────────────────────────
# lookback_all_signals
# ──────────────────────────────────────────────────────────────
class TestLookbackAllSignals:
    def test_batch_runs_for_all_specs(self):
        events = [_event(peak="2024-06-01"), _event(peak="2025-03-01", trough="2025-04-01")]
        vix = pd.Series(
            [30, 32, 35, 33, 30],
            index=pd.to_datetime(["2024-03-01", "2024-04-01", "2024-05-01", "2024-12-01", "2025-02-01"]),
            name="VIX",
        )
        specs = [_spec_above(thr=25.0)]
        out = lookback_all_signals(events, {"VIX": vix}, specs=specs)
        assert "VIX" in out
        assert len(out["VIX"]) == 2

    def test_missing_series_returns_none_results(self):
        events = [_event()]
        specs = [_spec_above()]
        out = lookback_all_signals(events, {}, specs=specs)  # 沒提供 VIX 序列
        assert out["VIX"][0].value_at_lookback is None
        assert out["VIX"][0].lead_time_days is None


# ──────────────────────────────────────────────────────────────
# compute_signal_hit_rate
# ──────────────────────────────────────────────────────────────
class TestComputeSignalHitRate:
    def _lb(self, value=None, lead=None, first_warn=None):
        return SignalLookback(
            event_peak_date=pd.Timestamp("2024-06-01"),
            signal_key="VIX", signal_label="VIX", threshold=25.0, direction="above",
            lookback_days=90,
            value_at_lookback=value, triggered_at_lookback=False,
            first_warning_date=first_warn, lead_time_days=lead,
        )

    def test_empty_list_zero(self):
        out = compute_signal_hit_rate([])
        assert out["n_total"] == 0
        assert out["hit_rate"] is None

    def test_all_hit_full_rate(self):
        lbs = [self._lb(value=30.0, lead=60, first_warn=pd.Timestamp("2024-04-01")) for _ in range(3)]
        out = compute_signal_hit_rate(lbs)
        assert out["n_total"] == 3
        assert out["n_covered"] == 3
        assert out["n_hit"] == 3
        assert out["hit_rate"] == 1.0
        assert out["avg_lead_days"] == 60.0

    def test_partial_hit(self):
        lbs = [
            self._lb(value=30.0, lead=60, first_warn=pd.Timestamp("2024-04-01")),
            self._lb(value=20.0, lead=None),  # 有 value 但沒觸發 → covered=True, hit=False
            self._lb(value=None, lead=None),  # 無覆蓋
        ]
        out = compute_signal_hit_rate(lbs)
        assert out["n_total"] == 3
        assert out["n_covered"] == 2
        assert out["n_hit"] == 1
        assert out["hit_rate"] == 0.5
        assert out["avg_lead_days"] == 60.0


# ──────────────────────────────────────────────────────────────
# fetch_signal_series (mocked)
# ──────────────────────────────────────────────────────────────
class TestFetchSignalSeries:
    def test_yahoo_success(self, monkeypatch):
        fake = pd.Series(
            [20.0, 22.0, 24.0],
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        def _fake_yf(ticker, range_, interval):
            assert ticker == "^VIX"
            assert range_ == "20y"
            return fake

        from repositories import macro_repository
        monkeypatch.setattr(macro_repository, "fetch_yf_close", _fake_yf)

        out = fetch_signal_series(_spec_above(), years=20)
        assert len(out) == 3
        assert out.name == "VIX"

    def test_yahoo_failure_returns_empty(self, monkeypatch):
        def _fake_yf(ticker, range_, interval):
            return pd.Series(dtype=float)

        from repositories import macro_repository
        monkeypatch.setattr(macro_repository, "fetch_yf_close", _fake_yf)

        out = fetch_signal_series(_spec_above(), years=20)
        assert out.empty
        assert out.name == "VIX"

    def test_fred_success(self, monkeypatch):
        fake_df = pd.DataFrame({
            "date": pd.to_datetime(["2024-01-01", "2024-02-01"]),
            "value": [0.5, -0.1],
        })

        def _fake_fred(sid, key, n):
            assert sid == "T10Y2Y"
            return fake_df

        from repositories import macro_repository
        monkeypatch.setattr(macro_repository, "fetch_fred", _fake_fred)

        out = fetch_signal_series(_spec_below(), years=20, fred_api_key="x")
        assert len(out) == 2
        assert out.name == "T10Y2Y"
        assert out.iloc[1] == -0.1


# ══════════════════════════════════════════════════════════════
# v18.281：edge mode (v2) 拐點偵測測試（鏡像 stock v18.160）
# ══════════════════════════════════════════════════════════════

class TestEvaluateEdgeMode:
    """v18.281 v2 edge detection 拐點偵測測試。"""

    def test_default_mode_is_edge(self):
        """預設 mode='edge'，與顯式指定 edge 結果一致。"""
        peak = pd.Timestamp("2024-06-01")
        event = _event(peak=str(peak.date()), trough="2024-07-01")
        # 在 window 內單一 transition：前 100 天 VIX=10，第 100 天起跳到 30
        idx = pd.date_range("2024-01-01", "2024-06-01", freq="D")
        values = [10.0] * 100 + [30.0] * (len(idx) - 100)
        series = pd.Series(values, index=idx, name="VIX")
        spec = _spec_above(25.0)
        default = evaluate_signal_at_event(event, series, spec)
        explicit = evaluate_signal_at_event(event, series, spec, mode="edge")
        assert default.lead_time_days == explicit.lead_time_days
        assert default.first_warning_date == explicit.first_warning_date

    def test_edge_detects_real_crossing(self):
        """v2 edge：series 從 10 → 30 的 transition 應被偵測為轉折日。"""
        peak = pd.Timestamp("2024-06-01")
        event = _event(peak=str(peak.date()), trough="2024-07-01")
        idx = pd.date_range("2024-01-01", "2024-06-01", freq="D")
        values = [10.0] * 100 + [30.0] * (len(idx) - 100)
        series = pd.Series(values, index=idx, name="VIX")
        lb = evaluate_signal_at_event(event, series, _spec_above(25.0), mode="edge")
        assert lb.lead_time_days is not None
        assert lb.first_warning_date == idx[100]

    def test_edge_ignores_persistent_warning_from_start(self):
        """v2 edge：全程在警戒（VIX 一直 ≥ 25）不算 crossing → 不命中。"""
        peak = pd.Timestamp("2024-06-01")
        event = _event(peak=str(peak.date()), trough="2024-07-01")
        idx = pd.date_range("2024-01-01", "2024-06-01", freq="D")
        series = pd.Series([30.0] * len(idx), index=idx, name="VIX")
        lb = evaluate_signal_at_event(event, series, _spec_above(25.0), mode="edge")
        assert lb.first_warning_date is None
        assert lb.lead_time_days is None

    def test_state_mode_legacy_v1_still_works(self):
        """v1 state mode：全程警戒會命中第一筆（驗證 v1 仍可用）。"""
        peak = pd.Timestamp("2024-06-01")
        event = _event(peak=str(peak.date()), trough="2024-07-01")
        idx = pd.date_range("2024-01-01", "2024-06-01", freq="D")
        series = pd.Series([30.0] * len(idx), index=idx, name="VIX")
        lb = evaluate_signal_at_event(event, series, _spec_above(25.0), mode="state")
        # v1 會把第一筆當「警戒命中」→ 有 lead_time
        assert lb.first_warning_date is not None
        assert lb.lead_time_days is not None

    def test_edge_vs_state_diverge_on_persistent_signal(self):
        """同 series 全程警戒：v2 None vs v1 有命中 → 證明 v2 修掉假預警。"""
        peak = pd.Timestamp("2024-06-01")
        event = _event(peak=str(peak.date()), trough="2024-07-01")
        idx = pd.date_range("2024-01-01", "2024-06-01", freq="D")
        series = pd.Series([30.0] * len(idx), index=idx, name="VIX")
        v2 = evaluate_signal_at_event(event, series, _spec_above(25.0), mode="edge")
        v1 = evaluate_signal_at_event(event, series, _spec_above(25.0), mode="state")
        assert v2.lead_time_days is None
        assert v1.lead_time_days is not None

    def test_edge_with_oscillation_picks_first_crossing(self):
        """series 在警戒邊界震盪：v2 應取第一次 transition 而非最後一次。"""
        peak = pd.Timestamp("2024-06-01")
        event = _event(peak=str(peak.date()), trough="2024-07-01")
        idx = pd.date_range("2024-01-01", "2024-06-01", freq="D")
        # 0-49 天 VIX=10，50-99 天 VIX=30（第一個 crossing），100-149 天 VIX=10
        # 150 天起又跳 30（第二個 crossing），到 peak
        values = ([10.0] * 50 + [30.0] * 50 + [10.0] * 50
                  + [30.0] * (len(idx) - 150))
        series = pd.Series(values, index=idx, name="VIX")
        lb = evaluate_signal_at_event(event, series, _spec_above(25.0),
                                       mode="edge", max_lookback_days=365)
        assert lb.first_warning_date == idx[50], \
            f"應取第一次 crossing (idx[50])，得 {lb.first_warning_date}"

    def test_lookback_all_signals_propagates_mode(self):
        """lookback_all_signals 應正確透傳 mode 給 evaluate。"""
        peak = pd.Timestamp("2024-06-01")
        event = _event(peak=str(peak.date()), trough="2024-07-01")
        idx = pd.date_range("2024-01-01", "2024-06-01", freq="D")
        series = pd.Series([30.0] * len(idx), index=idx, name="VIX")
        # 用 edge mode：全程警戒不應命中
        out_edge = lookback_all_signals(
            [event], {"VIX": series}, specs=[_spec_above(25.0)], mode="edge")
        # 用 state mode：全程警戒會命中
        out_state = lookback_all_signals(
            [event], {"VIX": series}, specs=[_spec_above(25.0)], mode="state")
        assert out_edge["VIX"][0].lead_time_days is None
        assert out_state["VIX"][0].lead_time_days is not None
