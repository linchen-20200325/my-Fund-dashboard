"""v19.182 Bug 5 — services.portfolio_service 組合排名 + 回撤純函式測試。

涵蓋:
1. compute_max_drawdown — 單檔最大回撤
2. compute_portfolio_drawdown — 組合加權回撤 + 各年度報酬
3. rank_funds_within_portfolio — 組內排名 + 同類 percentile

§6 自審「3 個最容易出錯的輸入」:
  1. 空 / 單筆 NAV → None 欄位,不偽造 0
  2. NAV 含非正值(停售/清算 0)→ Fail Loud
  3. 各基金歷史重疊太少(共同日 < 2)→ note 警示
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from services.portfolio_service import (
    compute_max_drawdown,
    compute_portfolio_drawdown,
    rank_funds_within_portfolio,
)


def _mk_series(values, start="2023-01-02", freq="B"):
    idx = pd.bdate_range(start=start, periods=len(values), freq=freq) \
        if freq == "B" else pd.date_range(start=start, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, name="nav")


# ════════════════════════════════════════════════════════════════
# 1. compute_max_drawdown
# ════════════════════════════════════════════════════════════════

class TestMaxDrawdown:
    def test_monotonic_up_zero_drawdown(self):
        s = _mk_series([10, 11, 12, 13, 14])
        r = compute_max_drawdown(s)
        assert r["max_dd_pct"] == 0.0  # 一路漲 → 無回撤
        assert r["n_obs"] == 5

    def test_known_drawdown(self):
        # 高點 20 → 谷底 15 → 回撤 = (15-20)/20 = -25%
        s = _mk_series([10, 20, 18, 15, 17])
        r = compute_max_drawdown(s)
        assert r["max_dd_pct"] == pytest.approx(-25.0, abs=1e-6)
        assert r["trough_date"] is not None
        assert r["peak_date"] is not None

    def test_peak_before_trough(self):
        s = _mk_series([10, 20, 15, 25, 12])
        r = compute_max_drawdown(s)
        # 最深:25 → 12 = -52%
        assert r["max_dd_pct"] == pytest.approx((12 - 25) / 25 * 100, abs=1e-6)

    def test_empty_series_fail_loud(self):
        r = compute_max_drawdown(None)
        assert r["max_dd_pct"] is None
        assert r["n_obs"] == 0

    def test_single_obs_fail_loud(self):
        r = compute_max_drawdown(_mk_series([10]))
        assert r["max_dd_pct"] is None
        assert r["n_obs"] == 1

    def test_non_positive_nav_fail_loud(self):
        # NAV 含 0(停售/清算)→ 不偽造,回 None
        s = _mk_series([10, 0, 8])
        r = compute_max_drawdown(s)
        assert r["max_dd_pct"] is None

    def test_nan_dropped(self):
        s = _mk_series([10, np.nan, 20, 15])
        r = compute_max_drawdown(s)
        # dropna 後 [10,20,15] → -25%
        assert r["max_dd_pct"] == pytest.approx(-25.0, abs=1e-6)
        assert r["n_obs"] == 3


# ════════════════════════════════════════════════════════════════
# 2. compute_portfolio_drawdown
# ════════════════════════════════════════════════════════════════

class TestPortfolioDrawdown:
    def test_equal_weight_two_funds(self):
        # 兩檔同步,組合回撤 = 個檔回撤
        a = _mk_series([10, 20, 15, 18], freq="D")
        b = _mk_series([5, 10, 7.5, 9], freq="D")  # 同形狀(比例一致)
        funds = [{"code": "A", "series": a}, {"code": "B", "series": b}]
        r = compute_portfolio_drawdown(funds)
        assert r["n_funds"] == 2
        assert r["n_obs"] == 4
        # 兩檔都 20→15 = -25%,等權合成仍 -25%
        assert r["max_dd_pct"] == pytest.approx(-25.0, abs=1e-6)

    def test_weights_normalized(self):
        a = _mk_series([10, 20, 10, 20], freq="D")   # 漲跌大
        b = _mk_series([10, 10, 10, 10], freq="D")   # 持平
        funds = [{"code": "A", "series": a}, {"code": "B", "series": b}]
        # 全壓 A → 回撤接近 A;全壓 B → 0
        r_a = compute_portfolio_drawdown(funds, weights={"A": 1.0, "B": 0.0})
        r_b = compute_portfolio_drawdown(funds, weights={"A": 0.0, "B": 1.0})
        assert r_a["max_dd_pct"] == pytest.approx(-50.0, abs=1e-6)  # 20→10
        assert r_b["max_dd_pct"] == pytest.approx(0.0, abs=1e-6)

    def test_yearly_returns(self):
        # 跨 2 年:2023 漲到 2024
        idx = pd.date_range("2023-06-01", periods=400, freq="D")
        vals = np.linspace(10, 14, 400)
        s = pd.Series(vals, index=idx, name="nav")
        funds = [{"code": "X", "series": s}]
        r = compute_portfolio_drawdown(funds)
        assert 2023 in r["yearly_returns"]  # 至少有一個完整年度跨點

    def test_empty_fail_loud(self):
        r = compute_portfolio_drawdown([])
        assert r["max_dd_pct"] is None
        assert r["note"] is not None

    def test_no_overlap_fail_loud(self):
        # 兩檔時間完全不重疊 → 共同日 0
        a = _mk_series([10, 11, 12], start="2020-01-01", freq="D")
        b = _mk_series([10, 11, 12], start="2023-01-01", freq="D")
        funds = [{"code": "A", "series": a}, {"code": "B", "series": b}]
        r = compute_portfolio_drawdown(funds)
        assert r["max_dd_pct"] is None
        assert "不足" in (r["note"] or "")

    def test_non_positive_nav_dropped(self):
        a = _mk_series([10, 20, 0, 15], freq="D")  # 含 0
        r = compute_max_drawdown(a)
        assert r["max_dd_pct"] is None  # 個檔層 fail loud


# ════════════════════════════════════════════════════════════════
# 3. rank_funds_within_portfolio
# ════════════════════════════════════════════════════════════════

class TestRankWithinPortfolio:
    def _fund(self, code, mgmt_fee=None, ret1y=None, peer_rank=None):
        f = {"code": code, "name": code, "moneydj_raw": {}, "metrics": {}}
        if mgmt_fee is not None:
            f["moneydj_raw"]["mgmt_fee"] = mgmt_fee
        if ret1y is not None:
            f["moneydj_raw"]["perf"] = {"1Y": ret1y}
        if peer_rank is not None:
            f["moneydj_raw"]["risk_metrics"] = {
                "peer_compare": {"本基金": {"同類排名": peer_rank}}
            }
        return f

    def test_expense_rank_ascending(self):
        funds = [
            self._fund("A", mgmt_fee=1.5),
            self._fund("B", mgmt_fee=0.8),
            self._fund("C", mgmt_fee=2.0),
        ]
        r = rank_funds_within_portfolio(funds)
        assert r["B"]["expense_rank"] == 1   # 最便宜
        assert r["A"]["expense_rank"] == 2
        assert r["C"]["expense_rank"] == 3
        assert r["A"]["expense_n"] == 3

    def test_return_rank_descending(self):
        funds = [
            self._fund("A", ret1y=10.0),
            self._fund("B", ret1y=15.0),
            self._fund("C", ret1y=5.0),
        ]
        r = rank_funds_within_portfolio(funds)
        assert r["B"]["return_rank"] == 1   # 最高報酬
        assert r["C"]["return_rank"] == 3

    def test_missing_metric_excluded(self):
        funds = [
            self._fund("A", mgmt_fee=1.0),
            self._fund("B"),  # 無 mgmt_fee
        ]
        r = rank_funds_within_portfolio(funds)
        assert r["A"]["expense_rank"] == 1
        assert r["A"]["expense_n"] == 1     # 只有 1 檔有費用率
        assert r["B"]["expense_rank"] is None

    def test_peer_percentile_first_place(self):
        funds = [self._fund("A", peer_rank="1/45")]
        r = rank_funds_within_portfolio(funds)
        assert r["A"]["peer_percentile"] == 100.0
        assert r["A"]["peer_rank_raw"] == "1/45"

    def test_peer_percentile_last_place(self):
        funds = [self._fund("A", peer_rank="45/45")]
        r = rank_funds_within_portfolio(funds)
        assert r["A"]["peer_percentile"] == 0.0

    def test_peer_percentile_missing(self):
        funds = [self._fund("A", mgmt_fee=1.0)]
        r = rank_funds_within_portfolio(funds)
        assert r["A"]["peer_percentile"] is None  # Fail Loud,不偽造

    def test_empty(self):
        assert rank_funds_within_portfolio([]) == {}
