"""test_dividend_current_fx.py — v18.273 配息折算用即時 FX

User 反饋「組合買入的匯率固定，但轉配息由美元轉台必須要即時匯率」。
驗 estimate_dividend_split 新加的 current_fx 參數行為。
"""
from __future__ import annotations

import pytest

from repositories.policy_repository import estimate_dividend_split


def test_no_current_fx_falls_back_to_avg_fx_backward_compat():
    """不傳 current_fx → 行為等同 v18.272 之前（fx_ratio=1）。"""
    r = estimate_dividend_split(
        invest_twd=1_000_000,
        annual_div_rate_pct=6.0,
        div_cash_pct=100,
        avg_nav=10.0,
        avg_fx=32.0,
    )
    # invest_twd × ADR% × fx_ratio = 1M × 6% × 1.0 = 60,000
    assert r["annual_div_twd"] == pytest.approx(60_000.0)
    assert r["fx_ratio"] == pytest.approx(1.0)


def test_current_fx_higher_than_avg_increases_dividend_twd():
    """TWD 貶值（current_fx > avg_fx）→ 配息 TWD 變多。"""
    r = estimate_dividend_split(
        invest_twd=1_000_000,
        annual_div_rate_pct=6.0,
        div_cash_pct=100,
        avg_nav=10.0,
        avg_fx=30.0,
        current_fx=33.0,  # 30 → 33 = 貶值 10%
    )
    # 60,000 × (33/30) = 66,000
    assert r["annual_div_twd"] == pytest.approx(66_000.0)
    assert r["fx_ratio"] == pytest.approx(33.0 / 30.0)


def test_current_fx_lower_than_avg_decreases_dividend_twd():
    """TWD 升值（current_fx < avg_fx）→ 配息 TWD 變少。"""
    r = estimate_dividend_split(
        invest_twd=1_000_000,
        annual_div_rate_pct=6.0,
        div_cash_pct=100,
        avg_nav=10.0,
        avg_fx=33.0,
        current_fx=30.0,
    )
    # 60,000 × (30/33) ≈ 54,545
    assert r["annual_div_twd"] == pytest.approx(60_000.0 * 30 / 33)
    assert r["fx_ratio"] == pytest.approx(30.0 / 33.0)


def test_current_fx_zero_treats_as_no_value():
    """current_fx=0 → 視為未傳 → fallback avg_fx。"""
    r = estimate_dividend_split(
        invest_twd=1_000_000,
        annual_div_rate_pct=6.0,
        div_cash_pct=100,
        avg_nav=10.0,
        avg_fx=32.0,
        current_fx=0.0,
    )
    assert r["fx_ratio"] == pytest.approx(1.0)


def test_new_units_uses_current_fx_and_nav():
    """再投入 new_units 應該用 current_nav × current_fx 還原。"""
    r = estimate_dividend_split(
        invest_twd=1_000_000,
        annual_div_rate_pct=6.0,
        div_cash_pct=50,  # 50% reinvest
        avg_nav=10.0,
        avg_fx=30.0,
        current_fx=33.0,
        current_nav=9.5,
    )
    # annual_div_twd = 60_000 × (33/30) = 66_000
    # reinvest_twd = 33_000
    # new_units = 33_000 / (9.5 × 33) = 105.26
    assert r["reinvest_twd"] == pytest.approx(33_000.0)
    assert r["new_units"] == pytest.approx(33_000.0 / (9.5 * 33.0))


def test_zero_avg_fx_safe_fallback():
    """avg_fx=0 → fx_ratio 安全回 1.0 不會 ZeroDivision。"""
    r = estimate_dividend_split(
        invest_twd=1_000_000,
        annual_div_rate_pct=6.0,
        div_cash_pct=100,
        avg_nav=10.0,
        avg_fx=0.0,
        current_fx=32.0,
    )
    assert r["fx_ratio"] == 1.0
    assert r["annual_div_twd"] == pytest.approx(60_000.0)


def test_fx_ratio_in_output():
    """output 含 fx_ratio 欄方便 UI 顯示。"""
    r = estimate_dividend_split(
        invest_twd=500_000,
        annual_div_rate_pct=8.0,
        div_cash_pct=50,
        avg_nav=15.0,
        avg_fx=30.5,
        current_fx=32.8,
    )
    assert "fx_ratio" in r
    assert r["fx_ratio"] == pytest.approx(32.8 / 30.5)
