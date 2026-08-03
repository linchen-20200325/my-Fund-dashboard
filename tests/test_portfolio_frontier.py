"""tests/test_portfolio_frontier.py — 效率前緣診斷(v19.424)。

驗:年化 moments、分散降 vol、max-Sharpe ≥ 隨機雲、前緣涵蓋 μ 區間、current 對帳、種子可重現、
邊界(<2檔/短史/無共同日/零變異/退化μ/低信賴)誠實 None+旗標。SLSQP 用寬容差(§4.3)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from services.portfolio_frontier import (
    aligned_returns_matrix,
    annualized_moments,
    efficient_frontier,
    efficient_frontier_diagnostic,
    max_sharpe_portfolio,
    min_variance_portfolio,
    portfolio_point,
    random_portfolio_cloud,
)

_D = pd.date_range("2022-01-03", periods=520, freq="B")


def _nav(rets: np.ndarray) -> pd.Series:
    return pd.Series(100 * np.cumprod(np.concatenate([[1.0], 1 + rets])), index=_D[:len(rets) + 1])


def _two_funds(n=300, seed=0):
    """部分負相關(共同因子相反)+ 各自噪音 → Σ 非奇異、有分散效益。"""
    rng = np.random.default_rng(seed)
    _common = rng.normal(0.0004, 0.008, n)
    _a = 0.0010 + 0.6 * _common + rng.normal(0, 0.005, n)
    _b = 0.0008 - 0.6 * _common + rng.normal(0, 0.005, n)
    return _nav(_a), _nav(_b)


def _moments(n=300, seed=0):
    a, b = _two_funds(n, seed)
    rdf, codes, _exc, _r = aligned_returns_matrix({"A": a, "B": b})
    return annualized_moments(rdf)


def test_moments_shapes_and_annualization():
    a, b = _two_funds(300)
    rdf, _c, _e, _r = aligned_returns_matrix({"A": a, "B": b})
    mu, Sig, codes = annualized_moments(rdf)
    assert mu.shape == (2,) and Sig.shape == (2, 2) and codes == ["A", "B"]
    assert np.allclose(Sig, Sig.T)                                   # 對稱
    assert mu[0] == pytest.approx(rdf["A"].mean() * 252, rel=1e-9)   # 年化


def test_min_var_below_individual_vols():
    mu, Sig, _c = _moments()
    mv = min_variance_portfolio(mu, Sig)
    _ind_vol = float(np.sqrt(np.diag(Sig)).min())
    assert mv is not None
    assert mv["vol"] <= _ind_vol + 1e-6                             # 分散效益(≤ 最小單檔 vol)
    assert abs(mv["weights"].sum() - 1.0) < 1e-6 and (mv["weights"] >= -1e-8).all()


def test_max_sharpe_beats_random_cloud():
    mu, Sig, _c = _moments()
    ms = max_sharpe_portfolio(mu, Sig)
    cloud = random_portfolio_cloud(mu, Sig, n=2000)
    assert ms is not None
    assert ms["sharpe"] >= np.nanmax(cloud["sharpe"]) - 1e-2        # 最佳化 ≥ 最佳隨機
    assert abs(ms["weights"].sum() - 1.0) < 1e-6


def test_frontier_spans_mu_range():
    mu, Sig, _c = _moments()
    fr = efficient_frontier(mu, Sig, grid_size=25)
    assert len(fr) >= 2
    _rets = [p["ret"] for p in fr]
    assert max(_rets) == pytest.approx(float(mu.max()), rel=1e-3)
    assert min(_rets) == pytest.approx(float(mu.min()), rel=1e-3)


def test_current_point_ties_out():
    mu, Sig, _c = _moments()
    w = np.array([0.6, 0.4])
    p = portfolio_point(mu, Sig, w, rf_annual=0.0)
    assert p["ret"] == pytest.approx(float(w @ mu))
    assert p["vol"] == pytest.approx(float(np.sqrt(w @ Sig @ w)))
    assert p["sharpe"] == pytest.approx(p["ret"] / p["vol"])


def test_reproducible_seed():
    mu, Sig, _c = _moments()
    c1 = random_portfolio_cloud(mu, Sig, n=500, seed=42)
    c2 = random_portfolio_cloud(mu, Sig, n=500, seed=42)
    assert np.array_equal(c1["vol"], c2["vol"]) and np.array_equal(c1["ret"], c2["ret"])
    c3 = random_portfolio_cloud(mu, Sig, n=500, seed=7)
    assert not np.array_equal(c1["vol"], c3["vol"])


def test_single_fund_not_ok():
    a, _b = _two_funds()
    r = efficient_frontier_diagnostic({"A": a}, {"A": 1.0})
    assert r["ok"] is False and "至少 2" in r["reason"]


def test_short_history_not_ok():
    a, b = _two_funds(n=40)                                          # ~40 交易日 < 60
    r = efficient_frontier_diagnostic({"A": a, "B": b}, {"A": 0.5, "B": 0.5})
    assert r["ok"] is False and "樣本太少" in r["reason"]


def test_no_common_dates_not_ok():
    a = pd.Series(100 * np.cumprod(1 + np.full(80, 0.001)), index=pd.date_range("2022-01-03", periods=80, freq="B"))
    b = pd.Series(100 * np.cumprod(1 + np.full(80, 0.001)), index=pd.date_range("2024-01-03", periods=80, freq="B"))
    r = efficient_frontier_diagnostic({"A": a, "B": b}, {"A": 0.5, "B": 0.5})
    assert r["ok"] is False and "共同交易日" in r["reason"]


def test_zero_variance_fund_flagged():
    a, _b = _two_funds(n=200)
    flat = pd.Series(100.0, index=a.index)                          # 常數 NAV → 零變異
    r = efficient_frontier_diagnostic({"A": a, "FLAT": flat}, {"A": 0.5, "FLAT": 0.5})
    assert r["ok"] is True
    assert "FLAT" in r["flags"]["zero_variance_codes"]
    assert r["flags"]["near_singular"] or r["flags"]["ridge_applied"]
    assert abs(r["min_var"]["weights"]["A"] + r["min_var"]["weights"]["FLAT"] - 1.0) < 1e-6


def test_degenerate_equal_mu_flag():
    a, _b = _two_funds(n=200, seed=1)
    r = efficient_frontier_diagnostic({"A": a, "B": a.copy()}, {"A": 0.5, "B": 0.5})   # 兩檔相同
    assert r["ok"] is True and r["flags"]["mu_degenerate"] is True
    assert r["min_var"] is not None


def test_low_confidence_flag():
    a, b = _two_funds(n=120)                                        # 60 ≤ n < 252
    r = efficient_frontier_diagnostic({"A": a, "B": b}, {"A": 0.5, "B": 0.5})
    assert r["ok"] is True and r["flags"]["low_confidence"] is True


def test_current_none_when_all_zero_weights():
    a, b = _two_funds(n=300)
    r = efficient_frontier_diagnostic({"A": a, "B": b}, {"A": 0.0, "B": 0.0})
    assert r["ok"] is True and r["current"] is None      # 權重全 0 → 無 current 點,不 crash


def test_frontier_upper_branch_monotone():
    mu, Sig, _c = _moments()
    fr = efficient_frontier(mu, Sig, grid_size=30)
    mv = min_variance_portfolio(mu, Sig)
    _upper = sorted([p for p in fr if p["ret"] >= mv["ret"] - 1e-9], key=lambda p: p["ret"])
    _vols = [p["vol"] for p in _upper]
    # 效率上支:報酬越高 → 風險非遞減(允許 SLSQP 微小數值鬆動)
    assert all(_vols[i + 1] >= _vols[i] - 1e-4 for i in range(len(_vols) - 1))


def test_diagnostic_smoke():
    a, b = _two_funds(n=300)
    r = efficient_frontier_diagnostic({"A": a, "B": b}, {"A": 0.6, "B": 0.4})
    assert r["ok"] is True and r["caveat"] and len(r["frontier"]) >= 2
    for _k in ("current", "max_sharpe", "min_var"):
        assert isinstance(r[_k], dict) and np.isfinite(r[_k]["vol"]) and np.isfinite(r[_k]["ret"])
    assert len(r["random_cloud"]["vol"]) == 3000
