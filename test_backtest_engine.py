"""backtest_engine.py 單元測試（v18.17 新增）

涵蓋：
  - backtest_portfolio：權重歸一、全零防護、單一基金、買入持有、ME 月聚合
  - calc_performance_metrics：標準/零波動/不足三期/全下行
  - compare_with_benchmark：標準/freq 參數/期間不重疊
  - quick_backtest：標準/不足四期

主要回歸目的：防止 PR_C drift 類「主線修改後測試空白」風險。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from services.backtest_service import (
    backtest_portfolio,
    calc_performance_metrics,
    compare_with_benchmark,
    quick_backtest,
)


# ════════════════════════════════════════════════════════════
# Fixtures
# ════════════════════════════════════════════════════════════
@pytest.fixture
def monthly_nav_2y() -> pd.DataFrame:
    """24 個月 + 1 個起始月共 25 期；兩檔基金：A 線性 + B 波動。"""
    idx = pd.date_range("2024-01-31", periods=25, freq="ME")
    a = pd.Series(np.linspace(100.0, 130.0, 25), index=idx)
    b = pd.Series(100.0 + 10.0 * np.sin(np.linspace(0, 6.28, 25)), index=idx)
    return pd.DataFrame({"A": a, "B": b})


@pytest.fixture
def monthly_returns_24m() -> pd.Series:
    """24 期月報酬，平均約 1%，含正負交替。"""
    np.random.seed(42)
    return pd.Series(np.random.normal(0.01, 0.03, 24),
                     index=pd.date_range("2024-01-31", periods=24, freq="ME"))


# ════════════════════════════════════════════════════════════
# T1. backtest_portfolio
# ════════════════════════════════════════════════════════════
def test_backtest_portfolio_normal(monthly_nav_2y: pd.DataFrame) -> None:
    w = pd.Series({"A": 0.6, "B": 0.4})
    result = backtest_portfolio(monthly_nav_2y, w, rebalance="ME")
    assert set(result.columns) == {"equity_curve", "portfolio_return", "drawdown"}
    # equity 起點接近 1.0（首期報酬累計）
    assert result["equity_curve"].iloc[0] > 0
    # drawdown 永遠 <= 0
    assert (result["drawdown"].dropna() <= 0).all()


def test_backtest_portfolio_buy_and_hold(monthly_nav_2y: pd.DataFrame) -> None:
    w = pd.Series({"A": 0.5, "B": 0.5})
    result = backtest_portfolio(monthly_nav_2y, w, rebalance=None)
    assert not result.empty
    assert "equity_curve" in result.columns


def test_backtest_portfolio_single_asset(monthly_nav_2y: pd.DataFrame) -> None:
    """單一基金 weight=1，組合報酬應等同該基金月報酬。"""
    w = pd.Series({"A": 1.0, "B": 0.0})
    result = backtest_portfolio(monthly_nav_2y[["A", "B"]], w, rebalance=None)
    expected_ret = monthly_nav_2y["A"].pct_change().dropna()
    pd.testing.assert_series_equal(
        result["portfolio_return"], expected_ret,
        check_names=False, rtol=1e-9,
    )


def test_backtest_portfolio_weights_normalize(monthly_nav_2y: pd.DataFrame) -> None:
    """非歸一權重應被自動歸一（[3,2] → [0.6,0.4]）。"""
    w_raw  = pd.Series({"A": 3, "B": 2})
    w_norm = pd.Series({"A": 0.6, "B": 0.4})
    r1 = backtest_portfolio(monthly_nav_2y, w_raw,  rebalance=None)
    r2 = backtest_portfolio(monthly_nav_2y, w_norm, rebalance=None)
    pd.testing.assert_series_equal(r1["portfolio_return"], r2["portfolio_return"],
                                   rtol=1e-9)


def test_backtest_portfolio_weights_all_zero(monthly_nav_2y: pd.DataFrame) -> None:
    """權重全 0 不可 ZeroDivisionError（v18.17 防護）。

    應 fallback 為均等分配（equal weight）。
    """
    w_zero  = pd.Series({"A": 0.0, "B": 0.0})
    w_equal = pd.Series({"A": 0.5, "B": 0.5})
    r_zero  = backtest_portfolio(monthly_nav_2y, w_zero,  rebalance=None)
    r_equal = backtest_portfolio(monthly_nav_2y, w_equal, rebalance=None)
    pd.testing.assert_series_equal(r_zero["portfolio_return"],
                                   r_equal["portfolio_return"], rtol=1e-9)


# ════════════════════════════════════════════════════════════
# T2. calc_performance_metrics
# ════════════════════════════════════════════════════════════
def test_calc_metrics_normal(monthly_returns_24m: pd.Series) -> None:
    equity = (1 + monthly_returns_24m).cumprod()
    m = calc_performance_metrics(equity, monthly_returns_24m, rf=0.02, freq=12)
    # 標準欄位齊全
    for k in ("total_return", "ann_return", "ann_vol", "sharpe",
              "sortino", "max_drawdown", "calmar"):
        assert k in m, f"missing key {k}"
    # 數值合理範圍
    assert -50 < m["total_return"] < 200
    assert m["ann_vol"] > 0


def test_calc_metrics_zero_vol() -> None:
    """全零波動（同一報酬重複）：Sharpe / Sortino 應為 0 不 crash。"""
    rets = pd.Series([0.01] * 24,
                     index=pd.date_range("2024-01-31", periods=24, freq="ME"))
    equity = (1 + rets).cumprod()
    m = calc_performance_metrics(equity, rets, rf=0.02, freq=12)
    assert m["sharpe"] == 0.0
    assert m["sortino"] == 0.0
    assert m["max_drawdown"] == 0.0  # 持續上漲無回撤
    assert m["calmar"] == 0.0


def test_calc_metrics_too_short_returns_empty() -> None:
    """v18.110：returns < 2 期才回 {}（守哨）。"""
    rets = pd.Series([0.01],
                     index=pd.date_range("2024-01-31", periods=1, freq="ME"))
    equity = (1 + rets).cumprod()
    assert calc_performance_metrics(equity, rets) == {}


def test_calc_metrics_partial_two_periods() -> None:
    """v18.110：returns >= 2 期 → 至少回 total/ann/MDD/periods + is_partial=True。

    回歸目的：保護 Tab4「3 期月底 → 2 期 returns → KPI 全 —%」的 user-visible bug。
    σ-based 指標（ann_vol / sharpe / sortino / calmar）刻意不出現於短樣本。
    """
    rets = pd.Series([0.01, 0.02],
                     index=pd.date_range("2024-01-31", periods=2, freq="ME"))
    equity = (1 + rets).cumprod()
    m = calc_performance_metrics(equity, rets, rf=0.02, freq=12)
    # 三個基本指標 + is_partial 旗標必出現
    assert m["periods"] == 2
    assert m["is_partial"] is True
    assert "total_return" in m
    assert "ann_return" in m
    assert "max_drawdown" in m
    # σ-based 指標短樣本不出現
    assert "ann_vol" not in m
    assert "sharpe" not in m
    assert "sortino" not in m
    assert "calmar" not in m


def test_calc_metrics_three_periods_full() -> None:
    """v18.110：returns >= 3 期 → 完整 7 個指標 + is_partial=False。"""
    rets = pd.Series([0.01, 0.02, -0.005],
                     index=pd.date_range("2024-01-31", periods=3, freq="ME"))
    equity = (1 + rets).cumprod()
    m = calc_performance_metrics(equity, rets, rf=0.02, freq=12)
    assert m["periods"] == 3
    assert m["is_partial"] is False
    for k in ("total_return", "ann_return", "max_drawdown",
              "ann_vol", "sharpe", "sortino", "calmar"):
        assert k in m, f"完整指標漏 {k}"


def test_calc_metrics_negative_with_volatility() -> None:
    """負平均報酬 + 有變異：Sharpe < 0、max_drawdown < 0。"""
    rng = np.random.default_rng(0)
    rets = pd.Series(rng.normal(-0.01, 0.02, 24),
                     index=pd.date_range("2024-01-31", periods=24, freq="ME"))
    equity = (1 + rets).cumprod()
    m = calc_performance_metrics(equity, rets, rf=0.02, freq=12)
    assert m["sharpe"] < 0, f"預期 Sharpe<0，實際 {m['sharpe']}"
    assert m["max_drawdown"] < 0
    assert m["total_return"] < 0


# ════════════════════════════════════════════════════════════
# T3. compare_with_benchmark
# ════════════════════════════════════════════════════════════
def test_compare_with_benchmark_normal(monthly_returns_24m: pd.Series) -> None:
    port_curve  = (1 + monthly_returns_24m).cumprod()
    bench_rets  = monthly_returns_24m - 0.005  # 組合每月平均贏 0.5%
    bench_curve = (1 + bench_rets).cumprod()
    r = compare_with_benchmark(port_curve, bench_curve, freq=12)
    assert "error" not in r
    # 組合贏，alpha 應正
    assert r["alpha_ann"] > 0
    assert r["tracking_error"] >= 0


def test_compare_with_benchmark_freq_param(monthly_returns_24m: pd.Series) -> None:
    """freq 參數應實際影響年化計算（v18.17 新增）。"""
    port_curve  = (1 + monthly_returns_24m).cumprod()
    bench_curve = (1 + monthly_returns_24m - 0.005).cumprod()
    r_m = compare_with_benchmark(port_curve, bench_curve, freq=12)
    r_d = compare_with_benchmark(port_curve, bench_curve, freq=252)
    # 同一資料切月頻 vs 日頻年化係數差異 ≈ 252/12 = 21x
    assert r_d["alpha_ann"] != r_m["alpha_ann"]


def test_compare_with_benchmark_no_overlap() -> None:
    """期間完全不重疊應回 error。"""
    p = pd.Series([1, 1.1, 1.2],
                  index=pd.date_range("2024-01-31", periods=3, freq="ME"))
    b = pd.Series([1, 1.1, 1.2],
                  index=pd.date_range("2025-01-31", periods=3, freq="ME"))
    r = compare_with_benchmark(p, b)
    assert "error" in r


# ════════════════════════════════════════════════════════════
# T4. quick_backtest
# ════════════════════════════════════════════════════════════
def test_quick_backtest_normal(monthly_nav_2y: pd.DataFrame) -> None:
    r = quick_backtest(monthly_nav_2y["A"], freq=12)
    assert "error" not in r
    assert "sharpe" in r
    assert "periods" in r
    assert r["periods"] == 24


def test_quick_backtest_too_short() -> None:
    """NAV 少於 4 期回 error。"""
    s = pd.Series([100, 101, 102],
                  index=pd.date_range("2024-01-31", periods=3, freq="ME"))
    r = quick_backtest(s)
    assert "error" in r
