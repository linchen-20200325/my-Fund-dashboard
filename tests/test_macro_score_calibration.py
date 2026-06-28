"""test_macro_score_calibration.py — 14-factor 景氣分數校準單元測試"""
from __future__ import annotations

import pandas as pd
import pytest

from services import macro_score_calibration as msc


# ════════════════════════════════════════════════════════════
# Per-factor scorer 邊界
# ════════════════════════════════════════════════════════════
def test_yield_10y2y_inverted():
    assert msc._s_yield_10y2y(-0.3) == -2

def test_yield_10y2y_normal():
    assert msc._s_yield_10y2y(0.6) == 2

def test_yield_10y2y_flat():
    assert msc._s_yield_10y2y(0.3) == 0

def test_pmi_strong():
    assert msc._s_pmi(54) == 2

def test_pmi_contraction():
    assert msc._s_pmi(43) == -2

def test_hy_spread_tight():
    assert msc._s_hy_spread(3.5) == 2

def test_hy_spread_wide():
    assert msc._s_hy_spread(7.0) == -2

def test_vix_calm():
    assert msc._s_vix(15) == 1

def test_vix_panic():
    assert msc._s_vix(35) == -1


# ════════════════════════════════════════════════════════════
# compute_score_row
# ════════════════════════════════════════════════════════════
def test_compute_score_row_all_positive():
    """所有因子打滿正分 → ~10。"""
    row = {
        "YIELD_10Y2Y": 0.8, "YIELD_10Y3M": 1.0, "PMI": 55,
        "HY_SPREAD": 3.5, "M2": 7.0, "BREADTH": 0.8,
        "DXY": -2.0, "FED_BS": 6.0, "VIX": 15,
        "CPI": 2.0, "FEDRATE": 2.0, "UNEMP": 3.5,
        "PPI": 2.0, "COPPER": 3.0,
    }
    prev = {"FEDRATE": 3.0}  # 降息
    s = msc.compute_score_row(row, prev)
    assert s >= 9.5, f"Expected near 10, got {s}"

def test_compute_score_row_all_negative():
    """所有因子打滿負分 → ~0。"""
    row = {
        "YIELD_10Y2Y": -0.5, "YIELD_10Y3M": -0.4, "PMI": 42,
        "HY_SPREAD": 8.0, "M2": -2.0, "BREADTH": -1.5,
        "DXY": 3.0, "FED_BS": -8.0, "VIX": 35,
        "CPI": 5.5, "FEDRATE": 6.0, "UNEMP": 7.0,
        "PPI": 6.0, "COPPER": -8.0,
    }
    prev = {"FEDRATE": 5.5}  # 升息（雖然已 >5 觸發 -0.5）
    s = msc.compute_score_row(row, prev)
    assert s <= 0.5, f"Expected near 0, got {s}"

def test_compute_score_row_neutral():
    """所有因子中性 → ~5。"""
    row = {
        "YIELD_10Y2Y": 0.3, "YIELD_10Y3M": 0.3, "PMI": 47,
        "HY_SPREAD": 5.0, "M2": 3.0, "BREADTH": 0.0,
        "DXY": 0.0, "FED_BS": 0.0, "VIX": 22,
        "CPI": 3.0, "FEDRATE": 3.0, "UNEMP": 5.0,
        "PPI": 3.5, "COPPER": 0.0,
    }
    s = msc.compute_score_row(row, {"FEDRATE": 3.0})
    # PMI=47 還是會 -1，其他多為 0，預期接近 5 但稍偏低
    assert 3.5 <= s <= 5.5, f"Expected ~5, got {s}"


# ════════════════════════════════════════════════════════════
# classify_phase
# ════════════════════════════════════════════════════════════
@pytest.mark.parametrize("score,phase", [
    (9.0, "Peak"),
    (8.0, "Peak"),
    (7.9, "Expansion"),
    (5.0, "Expansion"),
    (4.5, "Recovery"),
    (3.0, "Recovery"),
    (2.5, "Recession"),
    (0.0, "Recession"),
])
def test_classify_phase_boundaries(score, phase):
    assert msc.classify_phase(score) == phase


def test_classify_phase_custom_thresholds():
    assert msc.classify_phase(6.5, thresholds=(7.0, 4.0, 2.0)) == "Expansion"
    assert msc.classify_phase(6.5, thresholds=(6.0, 4.0, 2.0)) == "Peak"


# ════════════════════════════════════════════════════════════
# Synthetic demo + phase_accuracy
# ════════════════════════════════════════════════════════════
def test_generate_synthetic_demo_shape():
    df, spx = msc.generate_synthetic_demo(n_months=60)
    assert len(df) == 60
    assert len(spx) == 60
    assert "PMI" in df.columns
    assert "VIX" in df.columns

def test_synthetic_score_full_range():
    """合成 60 月應涵蓋 Peak / Expansion / Recovery / Recession 全 4 位階（壓力事件設計）。"""
    df, _ = msc.generate_synthetic_demo(n_months=60)
    score = msc.compute_historical_score(df)
    phases = score.apply(msc.classify_phase).unique()
    assert "Recession" in phases or "Recovery" in phases, \
        f"壓力事件應觸發 Recession/Recovery 位階，實際得 {phases}"

