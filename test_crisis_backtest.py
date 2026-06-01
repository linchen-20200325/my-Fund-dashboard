"""test_crisis_backtest.py — services/crisis_backtest.py 單元測試 (v18.260)

驗證危機事件偵測引擎在合成資料上的正確性，以及與真實基金 NAV 序列的整合。
不發 HTTP — fetch_market_series 的 wrapper 行為由 mock 驗證。
"""
from __future__ import annotations

import pandas as pd
import pytest

from services.crisis_backtest import (
    CrisisEvent,
    MARKET_TICKERS,
    attach_fund_drawdown,
    detect_crisis_events,
    fetch_market_series,
    summarize_events_with_fund,
)


def _series(values: list[float], start: str = "2020-01-01", freq: str = "D") -> pd.Series:
    """建構日度價格序列。"""
    idx = pd.date_range(start=start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, name="SPX")


# ──────────────────────────────────────────────────────────────
# detect_crisis_events
# ──────────────────────────────────────────────────────────────
class TestDetectCrisisEvents:
    def test_empty_series_returns_empty(self):
        assert detect_crisis_events(pd.Series(dtype=float)) == []

    def test_single_value_returns_empty(self):
        assert detect_crisis_events(_series([100.0])) == []

    def test_no_drawdown_returns_empty(self):
        # 一路漲，零事件
        s = _series([100, 105, 110, 115, 120])
        assert detect_crisis_events(s, threshold=-0.10) == []

    def test_small_drawdown_below_threshold_skipped(self):
        # 跌 5% < 10% 門檻 → 不算事件
        s = _series([100, 95, 100, 105])
        assert detect_crisis_events(s, threshold=-0.10) == []

    def test_single_drawdown_with_recovery(self):
        # 跌 20% 後完全回升
        s = _series([100, 90, 80, 90, 100, 105])
        evs = detect_crisis_events(s, threshold=-0.10)
        assert len(evs) == 1
        ev = evs[0]
        assert ev.peak_value == 100.0
        assert ev.trough_value == 80.0
        assert ev.drawdown_pct == pytest.approx(-0.20)
        assert ev.recovery_date is not None
        assert ev.duration_days == 2  # peak(day0) → trough(day2)

    def test_drawdown_without_recovery_still_recorded(self):
        # 跌完沒回到高點 → 仍要記錄（recovery_date=None）
        s = _series([100, 80, 70, 75])
        evs = detect_crisis_events(s, threshold=-0.10)
        assert len(evs) == 1
        assert evs[0].recovery_date is None
        assert evs[0].recovery_days is None
        assert evs[0].trough_value == 70.0

    def test_multiple_independent_events(self):
        # 兩個獨立危機事件
        s = _series([100, 80, 100, 110, 88, 110, 115])
        evs = detect_crisis_events(s, threshold=-0.10)
        assert len(evs) == 2
        assert evs[0].peak_value == 100.0
        assert evs[1].peak_value == 110.0

    def test_invalid_positive_threshold_raises(self):
        with pytest.raises(ValueError, match="threshold 必須為負數"):
            detect_crisis_events(_series([100, 90]), threshold=0.10)

    def test_market_label_propagated(self):
        s = _series([100, 80, 100])
        evs = detect_crisis_events(s, threshold=-0.10, market="TWII")
        assert evs[0].market == "TWII"

    def test_to_dict_serializes_dates(self):
        s = _series([100, 80, 100], start="2024-03-01")
        ev = detect_crisis_events(s, threshold=-0.10)[0]
        d = ev.to_dict()
        assert d["peak_date"] == "2024-03-01"
        assert d["drawdown_pct"] == pytest.approx(-0.20)
        assert isinstance(d["duration_days"], int)


# ──────────────────────────────────────────────────────────────
# attach_fund_drawdown
# ──────────────────────────────────────────────────────────────
class TestAttachFundDrawdown:
    def test_empty_nav_returns_unchanged(self):
        s = _series([100, 80, 100])
        ev = detect_crisis_events(s, threshold=-0.10)[0]
        out = attach_fund_drawdown(ev, pd.Series(dtype=float))
        assert out.fund_drawdown_pct is None

    def test_nav_outside_event_window_returns_unchanged(self):
        # 事件 2024-01-01 ~ 2024-01-02，NAV 完全不涵蓋
        s = _series([100, 80, 100], start="2024-01-01")
        ev = detect_crisis_events(s, threshold=-0.10)[0]
        nav = pd.Series(
            [10, 10.5],
            index=pd.date_range("2025-01-01", periods=2, freq="D"),
        )
        out = attach_fund_drawdown(ev, nav)
        assert out.fund_drawdown_pct is None

    def test_nav_covers_event_window_attached(self):
        # 事件 day0=peak 100, day2=trough 80, day4=recovery 100
        s = _series([100, 90, 80, 90, 100], start="2024-01-01")
        ev = detect_crisis_events(s, threshold=-0.10)[0]
        # 基金 NAV：peak 50 → trough 35 → recovery 48
        nav = pd.Series(
            [50, 45, 35, 40, 48],
            index=pd.date_range("2024-01-01", periods=5, freq="D"),
        )
        out = attach_fund_drawdown(ev, nav)
        assert out.fund_peak_value == 50.0
        assert out.fund_trough_value == 35.0
        assert out.fund_drawdown_pct == pytest.approx((35 - 50) / 50)
        assert out.fund_recovery_pct == pytest.approx((48 - 35) / 35)

    def test_nav_recovery_window_empty_keeps_dd(self):
        # 事件期間有資料、但 trough 之後 NAV 序列就結束 → recovery_pct=None
        s = _series([100, 80, 100], start="2024-01-01")
        ev = detect_crisis_events(s, threshold=-0.10)[0]
        nav = pd.Series(
            [50, 35],
            index=pd.date_range("2024-01-01", periods=2, freq="D"),
        )
        out = attach_fund_drawdown(ev, nav)
        assert out.fund_drawdown_pct is not None
        assert out.fund_recovery_pct is None


# ──────────────────────────────────────────────────────────────
# summarize_events_with_fund — 一條龍
# ──────────────────────────────────────────────────────────────
class TestSummarizeEventsWithFund:
    def test_no_fund_returns_events_only(self):
        s = _series([100, 80, 100, 110, 88, 110])
        evs = summarize_events_with_fund(s, fund_nav=None, threshold=-0.10)
        assert len(evs) == 2
        assert all(e.fund_drawdown_pct is None for e in evs)

    def test_with_fund_attaches_all(self):
        s = _series([100, 80, 100, 110, 88, 110], start="2024-01-01")
        nav = pd.Series(
            [50, 40, 50, 55, 44, 55],
            index=pd.date_range("2024-01-01", periods=6, freq="D"),
        )
        evs = summarize_events_with_fund(s, fund_nav=nav, threshold=-0.10)
        assert len(evs) == 2
        # 兩事件都應該被 attach
        assert all(e.fund_drawdown_pct is not None for e in evs)


# ──────────────────────────────────────────────────────────────
# fetch_market_series — wrapper 行為（mock）
# ──────────────────────────────────────────────────────────────
class TestFetchMarketSeries:
    def test_unknown_market_raises(self):
        with pytest.raises(ValueError, match="未知 market"):
            fetch_market_series(market="DAX")

    def test_known_markets_have_tickers(self):
        assert "SPX" in MARKET_TICKERS
        assert "TWII" in MARKET_TICKERS
        assert MARKET_TICKERS["SPX"] == "^GSPC"
        assert MARKET_TICKERS["TWII"] == "^TWII"

    def test_fetch_empty_on_proxy_failure(self, monkeypatch):
        """fetch_yf_close 抓不到 → 回空 Series 不爆。"""
        def _fake_fetch(ticker, range_, interval):
            return pd.Series(dtype=float)

        from repositories import macro_repository
        monkeypatch.setattr(macro_repository, "fetch_yf_close", _fake_fetch)

        out = fetch_market_series("SPX", years=5)
        assert out.empty
        assert out.name == "SPX"

    def test_fetch_returns_named_series(self, monkeypatch):
        """成功路徑：回傳 Series 並標 name。"""
        fake_data = pd.Series(
            [100, 101, 102],
            index=pd.date_range("2024-01-01", periods=3, freq="D"),
        )

        def _fake_fetch(ticker, range_, interval):
            assert ticker == "^GSPC"
            assert range_ == "5y"
            return fake_data

        from repositories import macro_repository
        monkeypatch.setattr(macro_repository, "fetch_yf_close", _fake_fetch)

        out = fetch_market_series("SPX", years=5)
        assert len(out) == 3
        assert out.name == "SPX"
