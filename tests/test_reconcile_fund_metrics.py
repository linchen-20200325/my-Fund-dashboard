"""tests/test_reconcile_fund_metrics.py — §4.3 fund metrics 對帳守(v19.166)

services/reconcile.py 內 fund 指標雙演算法對帳函式測試。對應 CLAUDE.md §4.3
「基金 1Y 報酬 / Sharpe / 配息殖利率 對帳」。

新增 caller-side regression guard:容差設定 + 邊界 case + 缺值處理。
"""
from __future__ import annotations

import pytest

from services.reconcile import (
    reconcile_fund_annual_return,
    reconcile_sharpe,
    reconcile_dividend_yield,
    reconcile_us10y_yield,
)


# ════════════════════════════════════════════════════════════════
# 1. 基金 1Y 報酬對帳(abs_tol=0.005,rel_tol=0.05)
# ════════════════════════════════════════════════════════════════
class TestFundAnnualReturn:
    def test_exact_match(self):
        r = reconcile_fund_annual_return(0.123, 0.123)
        assert r['agree']
        assert r['status'] == 'agree'
        assert r['name'] == 'FUND_1Y_RETURN'

    def test_within_abs_tolerance(self):
        """abs diff 0.004 < 0.005 → agree。"""
        r = reconcile_fund_annual_return(0.150, 0.154)
        assert r['agree']

    def test_outside_abs_tolerance(self):
        """abs diff 0.01 > 0.005 → disagree(15% vs 16% NAV 計算差)。"""
        r = reconcile_fund_annual_return(0.150, 0.160)
        assert not r['agree']
        assert r['status'] == 'disagree'

    def test_rel_tolerance_for_high_values(self):
        """高值用 rel tol:50% vs 52% → rel diff 4% < 5% → agree。"""
        r = reconcile_fund_annual_return(0.50, 0.52)
        assert r['agree']

    def test_a_missing(self):
        r = reconcile_fund_annual_return(None, 0.15)
        assert r['status'] == 'a_missing'
        assert not r['agree']

    def test_b_missing(self):
        r = reconcile_fund_annual_return(0.15, None)
        assert r['status'] == 'b_missing'

    def test_both_missing(self):
        r = reconcile_fund_annual_return(None, None)
        assert r['status'] == 'both_missing'

    def test_provenance_in_result(self):
        """source_a / source_b 應反映自算 vs MoneyDJ。"""
        r = reconcile_fund_annual_return(0.15, 0.15)
        assert 'self_calc' in r['source_a']
        assert 'MoneyDJ' in r['source_b']


# ════════════════════════════════════════════════════════════════
# 2. Sharpe 對帳(abs_tol=0.1)
# ════════════════════════════════════════════════════════════════
class TestReconcileSharpe:
    def test_exact_match(self):
        r = reconcile_sharpe(1.5, 1.5)
        assert r['agree']

    def test_within_tolerance(self):
        """abs diff 0.08 < 0.1 → agree。"""
        r = reconcile_sharpe(1.50, 1.58)
        assert r['agree']

    def test_outside_tolerance(self):
        """abs diff 0.2 > 0.1 → disagree。"""
        r = reconcile_sharpe(1.5, 1.7)
        assert not r['agree']

    def test_negative_sharpe_within(self):
        """負 Sharpe 也對帳。"""
        r = reconcile_sharpe(-0.5, -0.55)
        assert r['agree']

    def test_provenance_naming(self):
        r = reconcile_sharpe(1.5, 1.5)
        assert 'mean/std' in r['source_a']
        assert 'wb07' in r['source_b']


# ════════════════════════════════════════════════════════════════
# 3. 配息殖利率對帳(abs_tol=0.001,rel_tol=0.05)
# ════════════════════════════════════════════════════════════════
class TestDividendYield:
    def test_exact_match(self):
        r = reconcile_dividend_yield(0.05, 0.05)
        assert r['agree']

    def test_tight_abs_tolerance(self):
        """配息殖利率精度高:abs diff 0.0008 < 0.001 → agree。"""
        r = reconcile_dividend_yield(0.0500, 0.0508)
        assert r['agree']

    def test_outside_abs_tolerance(self):
        """abs diff 0.002 > 0.001 → 看 rel_tol。
        rel = 0.002 / 0.052 ≈ 0.038 < 0.05 → agree(rel kicks in)。"""
        r = reconcile_dividend_yield(0.050, 0.052)
        assert r['agree']  # rel tol 救援

    def test_clear_disagreement(self):
        """高殖利率差異 6% vs 8% → 兩 tol 都超 → disagree。"""
        r = reconcile_dividend_yield(0.06, 0.08)
        assert not r['agree']

    def test_provenance_naming(self):
        r = reconcile_dividend_yield(0.05, 0.05)
        assert 'sum(12M_div)/current_nav' in r['source_a']
        assert 'MoneyDJ' in r['source_b']


# ════════════════════════════════════════════════════════════════
# 4. US10Y 殖利率對帳(FRED vs Yahoo TNX/10)
# ════════════════════════════════════════════════════════════════
class TestUS10YYield:
    def test_tnx_conversion(self):
        """Yahoo TNX = yield × 10,須先除 10 才能對帳。"""
        # FRED 4.25%,Yahoo 報 42.5 → /10 = 4.25 → agree
        r = reconcile_us10y_yield(4.25, 42.5)
        assert r['agree']
        assert r['value_b'] == 4.25

    def test_within_5bp(self):
        """abs diff 4bp < 5bp → agree。"""
        r = reconcile_us10y_yield(4.25, 42.9)  # 4.29 vs 4.25
        assert r['agree']

    def test_outside_5bp(self):
        """abs diff 10bp > 5bp → disagree。"""
        r = reconcile_us10y_yield(4.25, 43.5)  # 4.35 vs 4.25
        assert not r['agree']

    def test_a_missing(self):
        r = reconcile_us10y_yield(None, 42.5)
        assert r['status'] == 'a_missing'

    def test_b_missing(self):
        r = reconcile_us10y_yield(4.25, None)
        assert r['status'] == 'b_missing'


# ════════════════════════════════════════════════════════════════
# 5. 結果 schema 一致性(所有 reconcile 函式回傳同 shape)
# ════════════════════════════════════════════════════════════════
class TestResultShape:
    REQUIRED_KEYS = {
        'name', 'value_a', 'value_b', 'source_a', 'source_b',
        'delta_abs', 'delta_rel', 'agree', 'status',
    }

    def test_fund_return_shape(self):
        r = reconcile_fund_annual_return(0.15, 0.15)
        assert set(r.keys()) >= self.REQUIRED_KEYS

    def test_sharpe_shape(self):
        r = reconcile_sharpe(1.5, 1.5)
        assert set(r.keys()) >= self.REQUIRED_KEYS

    def test_dividend_yield_shape(self):
        r = reconcile_dividend_yield(0.05, 0.05)
        assert set(r.keys()) >= self.REQUIRED_KEYS

    def test_us10y_shape(self):
        r = reconcile_us10y_yield(4.25, 42.5)
        assert set(r.keys()) >= self.REQUIRED_KEYS
