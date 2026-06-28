"""test_reconcile.py — F-RECON-1 v19.87 雙演算法對帳 unit tests"""
from __future__ import annotations
import pytest

from services.reconcile import (
    reconcile_pair,
    reconcile_us10y_yield,
    reconcile_fund_annual_return,
    reconcile_sharpe,
    reconcile_dividend_yield,
)


class TestReconcilePair:
    def test_agree_exact(self):
        r = reconcile_pair("X", 4.25, 4.25, source_a="A", source_b="B")
        assert r['agree'] is True
        assert r['status'] == 'agree'
        assert r['delta_abs'] == 0.0

    def test_agree_within_tolerance(self):
        r = reconcile_pair("X", 4.2500, 4.2501, source_a="A", source_b="B")
        assert r['agree'] is True

    def test_disagree_outside_tolerance(self):
        r = reconcile_pair("X", 4.25, 5.00, source_a="A", source_b="B")
        assert r['agree'] is False
        assert r['status'] == 'disagree'
        assert r['delta_abs'] == pytest.approx(0.75)

    def test_a_missing(self):
        r = reconcile_pair("X", None, 4.25, source_a="A", source_b="B")
        assert r['status'] == 'a_missing'
        assert r['agree'] is False

    def test_b_missing(self):
        r = reconcile_pair("X", 4.25, None, source_a="A", source_b="B")
        assert r['status'] == 'b_missing'

    def test_both_missing(self):
        r = reconcile_pair("X", None, None, source_a="A", source_b="B")
        assert r['status'] == 'both_missing'

    def test_relative_tolerance(self):
        r = reconcile_pair("X", 1000.0, 1000.5, source_a="A", source_b="B",
                            abs_tol=1.0, rel_tol=1e-3)
        assert r['agree'] is True


class TestReconcileUs10yYield:
    def test_fred_vs_yahoo_agree(self):
        r = reconcile_us10y_yield(4.25, 42.5)
        assert r['agree'] is True
        assert r['name'] == "US10Y_YIELD"
        assert r['value_a'] == 4.25
        assert r['value_b'] == 4.25

    def test_within_5bp_tolerance(self):
        r = reconcile_us10y_yield(4.25, 42.7)
        assert r['agree'] is True

    def test_outside_5bp_disagree(self):
        r = reconcile_us10y_yield(4.25, 45.0)
        assert r['agree'] is False
        assert r['status'] == 'disagree'

    def test_yahoo_missing(self):
        r = reconcile_us10y_yield(4.25, None)
        assert r['status'] == 'b_missing'

    def test_fred_missing(self):
        r = reconcile_us10y_yield(None, 42.5)
        assert r['status'] == 'a_missing'


class TestReconcileFundAnnualReturn:
    def test_agree(self):
        r = reconcile_fund_annual_return(0.15, 0.15)
        assert r['agree'] is True

    def test_within_50bp_tolerance(self):
        # 0.5pp diff <= abs_tol 0.005 → agree
        r = reconcile_fund_annual_return(0.15, 0.154)
        assert r['agree'] is True

    def test_outside_tolerance(self):
        # 2pp diff > abs_tol 0.005 (and > rel_tol 5%) → disagree
        r = reconcile_fund_annual_return(0.15, 0.30)
        assert r['agree'] is False


class TestReconcileSharpe:
    def test_agree(self):
        r = reconcile_sharpe(1.20, 1.20)
        assert r['agree'] is True

    def test_within_tolerance(self):
        # 0.05 diff < abs_tol 0.1 → agree
        r = reconcile_sharpe(1.20, 1.25)
        assert r['agree'] is True

    def test_disagree(self):
        # 0.5 diff > abs_tol 0.1 → disagree (and > rel_tol 10% of 1.20)
        r = reconcile_sharpe(1.20, 1.70)
        assert r['agree'] is False


class TestReconcileDividendYield:
    def test_agree(self):
        r = reconcile_dividend_yield(0.04, 0.04)
        assert r['agree'] is True

    def test_outside_tolerance(self):
        # 0.5pp diff > abs_tol 0.001 → check rel_tol
        # rel_tol=0.05 of 0.04 = 0.002 → 0.005 still exceeds → disagree
        r = reconcile_dividend_yield(0.04, 0.05)
        assert r['agree'] is False


def test_module_smoke():
    """import + 5 函式可叫"""
    from services import reconcile
    assert callable(reconcile.reconcile_pair)
    assert callable(reconcile.reconcile_us10y_yield)
    assert callable(reconcile.reconcile_fund_annual_return)
    assert callable(reconcile.reconcile_sharpe)
    assert callable(reconcile.reconcile_dividend_yield)
