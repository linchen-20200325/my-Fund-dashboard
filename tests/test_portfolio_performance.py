"""tests/test_portfolio_performance.py — 組合層績效(v19.421)。

驗:年化/σ/Sharpe 對帳、權重歸一、排除(壞NAV/0權重)、共同交易日對齊、貢獻拆解、空→blank。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.portfolio_performance import (
    contribution_by_fund,
    performance_metrics,
    portfolio_returns,
)

_D = pd.date_range("2022-01-03", periods=505, freq="B")   # ~2 年交易日


def _wavy(mu: float, amp: float, n: int) -> np.ndarray:
    """日報酬 = mu ± amp 交替 → 均值 ≈ mu、有變異(供 σ/Sharpe 非零)。"""
    return np.array([mu + (amp if i % 2 == 0 else -amp) for i in range(n)])


def _nav(rets: np.ndarray) -> pd.Series:
    return pd.Series(100 * np.cumprod(np.concatenate([[1.0], 1 + rets])), index=_D[:len(rets) + 1])


def test_portfolio_metrics_and_sharpe_ties_out():
    m = performance_metrics(
        {"A": _nav(_wavy(0.0006, 0.008, 400)), "B": _nav(_wavy(0.0002, 0.004, 400))},
        {"A": 0.6, "B": 0.4})
    assert m["n_funds_used"] == 2
    assert m["ann_vol_pct"] > 0 and m["sharpe"] is not None
    assert m["max_drawdown_pct"] <= 0
    # Sharpe(rf=0)= 年化報酬 / 年化波動 → 用顯示值對帳
    assert abs(m["sharpe"] - m["ann_return_pct"] / m["ann_vol_pct"]) < 0.02


def test_weights_normalized_subset():
    res = portfolio_returns(
        {"A": _nav(_wavy(0.0006, 0.008, 300)), "B": _nav(_wavy(0.0002, 0.004, 300))},
        {"A": 6, "B": 4})                       # 未歸一 → 應自動歸一 0.6/0.4
    assert res is not None
    _port, _used, _w, _exc = res
    assert abs(sum(_w.values()) - 1.0) < 1e-9
    assert abs(_w["A"] - 0.6) < 1e-9


def test_excluded_bad_nav_and_zero_weight():
    m = performance_metrics(
        {"A": _nav(_wavy(0.0006, 0.008, 300)),
         "B": pd.Series([100.0], index=_D[:1]),    # 只有 1 點 → 壞 NAV
         "C": _nav(_wavy(0.0006, 0.008, 300))},
        {"A": 1.0, "B": 1.0, "C": 0.0})            # C 權重 0
    _excl = {e["code"] for e in m["excluded"]}
    assert "B" in _excl and "C" in _excl
    assert m["n_funds_used"] == 1                  # 只 A


def test_common_dates_alignment_shorter_fund_limits():
    m = performance_metrics(
        {"A": _nav(_wavy(0.0006, 0.008, 400)),     # 長
         "B": _nav(_wavy(0.0002, 0.004, 200))},    # 短(限制共同期間)
        {"A": 0.5, "B": 0.5})
    assert m["n_funds_used"] == 2
    assert m["n_days"] <= 200                       # 受較短的 B 限制


def test_empty_or_single_point_blank():
    assert performance_metrics({}, {})["sharpe"] is None
    assert performance_metrics({"A": pd.Series([100.0], index=_D[:1])},
                               {"A": 1.0})["ann_return_pct"] is None
    assert performance_metrics({"A": _nav(_wavy(0.0006, 0.008, 300))},
                               {"A": 0.0})["ann_return_pct"] is None   # 全 0 權重


def test_contribution_decomposition():
    c = contribution_by_fund(
        {"A": _nav(_wavy(0.0006, 0.008, 300)), "B": _nav(_wavy(0.0002, 0.004, 300))},
        {"A": 0.6, "B": 0.4})
    assert set(c.keys()) == {"A", "B"}
    assert abs(c["A"]["weight_pct"] - 60.0) < 0.01
    # 貢獻 = 權重 × 該檔報酬
    assert abs(c["A"]["contribution_pct"] - 0.6 * c["A"]["fund_return_pct"]) < 0.05


def test_single_fund_ok():
    m = performance_metrics({"A": _nav(_wavy(0.0006, 0.008, 300))}, {"A": 1.0})
    assert m["n_funds_used"] == 1 and m["ann_return_pct"] is not None
