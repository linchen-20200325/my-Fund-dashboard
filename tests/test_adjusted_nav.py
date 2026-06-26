"""tests/test_adjusted_nav.py — §4.5 配息還原 NAV 序列守(v19.167)"""
from __future__ import annotations

import math

import pandas as pd
import pytest

from services.adjusted_nav import (
    adjust_nav_for_dividends,
    is_nav_likely_dividend_adjusted,
)


def _build_nav(values: list[float], start: str = "2026-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="D")
    s = pd.Series(values, index=idx, dtype=float, name="NAV")
    s.attrs["source"] = "MoneyDJ:test"
    s.attrs["fetched_at"] = "2026-06-26T12:00:00+00:00"
    return s


# ════════════════════════════════════════════════════════════════
# 1. 基本還原邏輯
# ════════════════════════════════════════════════════════════════
class TestBasicAdjustment:
    def test_single_dividend_adjusts_prior_nav(self):
        """單筆配息:ex-date 為第 4 天,前 3 天 NAV 應放大,後不變。

        NAV: 10, 10.1, 10.2, 9.7(ex-date 跳空) , 9.8
        Dividend: 2026-01-04, amount=0.5
        nav_before(2026-01-03) = 10.2
        factor = (10.2 + 0.5) / 10.2 ≈ 1.0490
        Adjusted: 10*1.0490, 10.1*1.0490, 10.2*1.0490, 9.7, 9.8
                = 10.49, 10.595, 10.701, 9.7, 9.8
        """
        nav = _build_nav([10.0, 10.1, 10.2, 9.7, 9.8])
        divs = [{"date": "2026-01-04", "amount": 0.5}]
        adj = adjust_nav_for_dividends(nav, divs)
        factor = (10.2 + 0.5) / 10.2
        assert math.isclose(adj.iloc[0], 10.0 * factor, abs_tol=1e-6)
        assert math.isclose(adj.iloc[2], 10.2 * factor, abs_tol=1e-6)
        # ex-date 當日 + 之後不變
        assert math.isclose(adj.iloc[3], 9.7, abs_tol=1e-9)
        assert math.isclose(adj.iloc[4], 9.8, abs_tol=1e-9)

    def test_multiple_dividends_cascade(self):
        """兩筆配息,放大效應應累積。"""
        # NAV: 10, 9.5 (ex1), 9.6, 9.1 (ex2), 9.2
        # Div1: date=01-02 amount=0.5 → nav_before(01-01)=10, factor1=1.05
        # Div2: date=01-04 amount=0.5 → nav_before(01-03 in adjusted)=adj[2]=9.6*1.05=10.08
        #       factor2 = (10.08+0.5)/10.08 ≈ 1.0496
        # 但因 div1 已先 apply,div2 套用順序為升序(01-02 先,01-04 後)
        # 演算法升序處理 → div1 先放大 0,1 天;div2 在已放大的基礎上找 nav_before
        nav = _build_nav([10.0, 9.5, 9.6, 9.1, 9.2])
        divs = [
            {"date": "2026-01-04", "amount": 0.5},  # 故意亂序輸入
            {"date": "2026-01-02", "amount": 0.5},
        ]
        adj = adjust_nav_for_dividends(nav, divs)
        # adj[0] 經 div1(01-02)放大 + div2(01-04)放大
        # div1 first: adj[0..1] *= 1.05(nav_before=10, factor=1.05)
        # after div1: [10.5, 9.975, 9.6, 9.1, 9.2]
        # div2 next: nav_before(01-03 in current adj) = 9.6, amt=0.5, factor=(9.6+0.5)/9.6
        # adj[0..2] *= factor2
        f1 = (10.0 + 0.5) / 10.0
        # nav_before for div2 in adjusted-after-div1: 9.6(adj[2] 未經 div1 放大)
        f2 = (9.6 + 0.5) / 9.6
        expected_0 = 10.0 * f1 * f2
        assert math.isclose(adj.iloc[0], expected_0, abs_tol=1e-6)


# ════════════════════════════════════════════════════════════════
# 2. attrs preservation
# ════════════════════════════════════════════════════════════════
class TestAttrsPreserved:
    def test_attrs_kept_after_adjustment(self):
        nav = _build_nav([10.0, 10.5, 10.3])
        divs = [{"date": "2026-01-03", "amount": 0.2}]
        adj = adjust_nav_for_dividends(nav, divs)
        assert adj.attrs["source"] == "MoneyDJ:test"
        assert adj.attrs["fetched_at"] == "2026-06-26T12:00:00+00:00"

    def test_caller_nav_not_mutated(self):
        """caller 傳入的 nav 不應被修改。"""
        nav = _build_nav([10.0, 10.5, 10.3])
        original_values = nav.copy().tolist()
        divs = [{"date": "2026-01-03", "amount": 0.2}]
        adjust_nav_for_dividends(nav, divs)
        assert nav.tolist() == original_values


# ════════════════════════════════════════════════════════════════
# 3. 邊界條件
# ════════════════════════════════════════════════════════════════
class TestEdgeCases:
    def test_empty_nav(self):
        empty = pd.Series(dtype=float)
        divs = [{"date": "2026-01-01", "amount": 0.5}]
        assert adjust_nav_for_dividends(empty, divs).empty

    def test_empty_dividends(self):
        nav = _build_nav([10.0, 10.5])
        out = adjust_nav_for_dividends(nav, [])
        assert out.equals(nav)

    def test_dividend_before_nav_range(self):
        """ex-date 在 NAV 範圍之前 → skip,NAV 不變。"""
        nav = _build_nav([10.0, 10.5], start="2026-06-01")
        divs = [{"date": "2025-01-01", "amount": 0.5}]  # 配息在 NAV 之前
        adj = adjust_nav_for_dividends(nav, divs)
        # 沒前筆可放大,skip
        assert math.isclose(adj.iloc[0], 10.0, abs_tol=1e-9)
        assert math.isclose(adj.iloc[1], 10.5, abs_tol=1e-9)

    def test_dividend_at_first_nav_date(self):
        """ex-date 等於 NAV 第一天 → 無前筆,skip。"""
        nav = _build_nav([10.0, 10.5])
        divs = [{"date": "2026-01-01", "amount": 0.5}]
        adj = adjust_nav_for_dividends(nav, divs)
        assert math.isclose(adj.iloc[0], 10.0, abs_tol=1e-9)

    def test_negative_dividend_skipped(self):
        """負配息 → skip + log,NAV 不變。"""
        nav = _build_nav([10.0, 10.5])
        divs = [{"date": "2026-01-02", "amount": -0.5}]
        adj = adjust_nav_for_dividends(nav, divs)
        assert math.isclose(adj.iloc[0], 10.0, abs_tol=1e-9)


# ════════════════════════════════════════════════════════════════
# 4. 輸入驗證
# ════════════════════════════════════════════════════════════════
class TestInputValidation:
    def test_non_dict_dividend_raises(self):
        nav = _build_nav([10.0, 10.5])
        with pytest.raises(ValueError, match="dict"):
            adjust_nav_for_dividends(nav, [("2026-01-02", 0.5)])  # tuple 不是 dict

    def test_missing_date_key_raises(self):
        nav = _build_nav([10.0, 10.5])
        with pytest.raises(ValueError, match="缺 date"):
            adjust_nav_for_dividends(nav, [{"amount": 0.5}])

    def test_missing_amount_key_raises(self):
        nav = _build_nav([10.0, 10.5])
        with pytest.raises(ValueError, match="缺 date/amount"):
            adjust_nav_for_dividends(nav, [{"date": "2026-01-02"}])

    def test_unparseable_date_raises(self):
        nav = _build_nav([10.0, 10.5])
        with pytest.raises(ValueError, match="date 無法 parse"):
            adjust_nav_for_dividends(nav, [{"date": "Not-A-Date", "amount": 0.5}])


# ════════════════════════════════════════════════════════════════
# 5. is_nav_likely_dividend_adjusted heuristic
# ════════════════════════════════════════════════════════════════
class TestIsLikelyAdjusted:
    def test_unadjusted_nav_with_jump(self):
        """NAV 在 ex-date 有 3% 跌幅 → 看似未還原。"""
        # NAV: 10, 10.1, 10.2, 9.7(-4.9%), 9.8
        nav = _build_nav([10.0, 10.1, 10.2, 9.7, 9.8])
        divs = [{"date": "2026-01-04", "amount": 0.5}]
        assert is_nav_likely_dividend_adjusted(nav, divs) is False

    def test_adjusted_nav_without_jump(self):
        """還原後的 NAV 平滑,無跳空 → 看似已還原。"""
        adj_nav = _build_nav([10.5, 10.6, 10.7, 9.7, 9.8])  # ex-date 之前已放大
        # ex-date 跳空 = (9.7-10.7)/10.7 ≈ -9.3%,還是有跌空
        # 用更平滑的例子:
        adj_nav = _build_nav([10.0, 10.05, 10.10, 10.08, 10.12])  # 完全沒跌空
        divs = [{"date": "2026-01-04", "amount": 0.5}]
        assert is_nav_likely_dividend_adjusted(adj_nav, divs) is True

    def test_empty_inputs(self):
        assert is_nav_likely_dividend_adjusted(pd.Series(dtype=float), [{"date": "2026-01-01", "amount": 0.5}]) is False
        assert is_nav_likely_dividend_adjusted(_build_nav([10.0]), []) is False
