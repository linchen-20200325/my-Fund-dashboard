"""test_calc_twd_investment.py — v18.252 台幣輸入投資試算純函式驗算"""
import pytest

from fund_fetcher import calc_twd_investment  # re-export，避免 partial-load 循環


# ── 用戶截圖的真實數字驗算 ────────────────────────────────────────────
# NAV: 12.24 美元, ADR: 9.1%, 投入 1,000,000 TWD, 假設 USDTWD = 32.0
# 1) 1,000,000 / 32 = 31,250 USD
# 2) 31,250 / 12.24 = 2,553.4314 單位
# 3) 配息 USD = 2,553.4314 × 12.24 × 9.1% = 31,250 × 9.1% = 2,843.75 USD
# 4) 配息 TWD = 2,843.75 × 32 = 91,000 TWD/年 → 7,583.33 TWD/月
# 5) 殖利率 TWD = 91,000 / 1,000,000 = 9.10%（理應 = ADR）

def test_user_screenshot_numbers_match():
    r = calc_twd_investment(
        twd_amount=1_000_000,
        nav=12.24,
        annual_div_rate_pct=9.1,
        fx_ccy_to_twd=32.0,
    )
    assert r["has_fx"] is True
    assert r["ccy_amount"] == pytest.approx(31_250.0, rel=1e-6)
    assert r["units"] == pytest.approx(31_250 / 12.24, rel=1e-6)
    assert r["div_ccy_year"] == pytest.approx(31_250 * 0.091, rel=1e-6)
    assert r["div_twd_year"] == pytest.approx(91_000.0, rel=1e-6)
    assert r["div_twd_month"] == pytest.approx(91_000 / 12, rel=1e-6)
    # FX 完全對沖：實際殖利率 = ADR
    assert r["yield_twd_pct"] == pytest.approx(9.1, rel=1e-6)


def test_no_fx_falls_back_to_ccy_mode():
    r = calc_twd_investment(
        twd_amount=1_000_000,
        nav=12.24,
        annual_div_rate_pct=9.1,
        fx_ccy_to_twd=None,
    )
    assert r["has_fx"] is False
    # 把 1,000,000 當原幣處理
    assert r["ccy_amount"] == pytest.approx(1_000_000.0)
    assert r["units"] == pytest.approx(1_000_000 / 12.24, rel=1e-6)
    assert r["div_ccy_year"] == pytest.approx(1_000_000 * 0.091, rel=1e-6)
    # 無 FX → 沒有 TWD 配息
    assert r["div_twd_year"] == 0.0
    assert r["div_twd_month"] == 0.0
    assert r["yield_twd_pct"] == pytest.approx(9.1)


def test_zero_fx_treated_as_no_fx():
    r = calc_twd_investment(1_000_000, 12.24, 9.1, fx_ccy_to_twd=0.0)
    assert r["has_fx"] is False
    assert r["div_twd_year"] == 0.0


def test_zero_nav_returns_safe_zeros():
    r = calc_twd_investment(1_000_000, 0.0, 9.1, fx_ccy_to_twd=32.0)
    assert r["units"] == 0.0 and r["div_ccy_year"] == 0.0
    assert r["div_twd_year"] == 0.0


def test_negative_twd_returns_safe_zeros():
    r = calc_twd_investment(-100, 12.24, 9.1, fx_ccy_to_twd=32.0)
    assert r["units"] == 0.0 and r["div_twd_year"] == 0.0


def test_zero_adr_returns_zero_dividend_but_units_ok():
    r = calc_twd_investment(1_000_000, 12.24, 0.0, fx_ccy_to_twd=32.0)
    assert r["units"] > 0.0
    assert r["div_ccy_year"] == 0.0
    assert r["div_twd_year"] == 0.0
    assert r["yield_twd_pct"] == 0.0


def test_eur_currency_with_eurtwd_fx():
    # EUR 35.0 TWD, NAV 9.5 EUR, ADR 7.5%
    r = calc_twd_investment(
        twd_amount=2_000_000,
        nav=9.5,
        annual_div_rate_pct=7.5,
        fx_ccy_to_twd=35.0,
    )
    assert r["ccy_amount"] == pytest.approx(2_000_000 / 35.0)
    assert r["units"] == pytest.approx(2_000_000 / 35.0 / 9.5)
    # FX 完全對沖：年息 TWD = TWD × ADR%
    assert r["div_twd_year"] == pytest.approx(2_000_000 * 0.075)
    assert r["yield_twd_pct"] == pytest.approx(7.5)


def test_none_amount_safe():
    r = calc_twd_investment(None, 12.24, 9.1, fx_ccy_to_twd=32.0)
    assert r["units"] == 0.0


def test_round_trip_invariant():
    """核心不變量：FX 完全對沖時，配息 TWD 殖利率必須等於 ADR。"""
    for twd, nav, adr, fx in [
        (500_000, 8.5, 6.0, 32.5),
        (3_000_000, 15.0, 11.2, 31.8),
        (1_500_000, 10.0, 4.5, 33.0),
    ]:
        r = calc_twd_investment(twd, nav, adr, fx)
        assert r["yield_twd_pct"] == pytest.approx(adr, rel=1e-9)
        # 配息 TWD ≈ 投入 TWD × ADR%（FX 自然抵銷）
        assert r["div_twd_year"] == pytest.approx(twd * adr / 100.0, rel=1e-9)
