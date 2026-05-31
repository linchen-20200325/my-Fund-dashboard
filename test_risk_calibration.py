"""test_risk_calibration.py — v18.251 風險評分真值校準單元測試"""
import numpy as np
import pandas as pd

from services.risk_calibration import (
    CalibrationResult,
    compute_calibration,
    generate_synthetic_demo,
    grid_search_threshold,
    label_forward_drawdown,
    rolling_risk_score,
)


def test_label_forward_drawdown_obvious_crash():
    """100 → min(90,85,80) = 80, dd = -20% < -10% ⇒ 1"""
    spx = pd.Series(
        [100, 90, 85, 80, 82, 85],
        index=pd.date_range("2020-01-01", periods=6, freq="MS"),
    )
    lab = label_forward_drawdown(spx, horizon_months=3, threshold=-0.10)
    assert lab.iloc[0] == 1.0
    assert pd.isna(lab.iloc[-1])  # 最後 horizon 期 NaN


def test_label_forward_drawdown_calm_market():
    """平穩上漲 → 全 0（無 forward window 的尾段是 NaN）"""
    spx = pd.Series(
        [100 + i for i in range(12)],
        index=pd.date_range("2020-01-01", periods=12, freq="MS"),
    )
    lab = label_forward_drawdown(spx, horizon_months=3, threshold=-0.10)
    assert (lab.dropna() == 0.0).all()


def test_compute_calibration_perfect_predictor():
    score = pd.Series([0.0, 0.0, 1.0, 1.0, 0.0, 1.0])
    label = pd.Series([0.0, 0.0, 1.0, 1.0, 0.0, 1.0])
    r = compute_calibration(score, label, threshold=0.5)
    assert isinstance(r, CalibrationResult)
    assert r.precision == 1.0 and r.recall == 1.0 and r.f1 == 1.0
    assert r.tp == 3 and r.fp == 0 and r.fn == 0
    cm = r.confusion_matrix
    assert cm.shape == (2, 2)
    assert int(cm.loc["實際:危機", "預測:危機"]) == 3


def test_compute_calibration_empty_doesnt_crash():
    r = compute_calibration(pd.Series([], dtype=float), pd.Series([], dtype=float), 1.0)
    assert r.precision == 0.0 and r.recall == 0.0 and r.tp == 0


def test_compute_calibration_handles_nan_aligned_index():
    """score / label 有 NaN 應自動 dropna 不 crash"""
    idx = pd.date_range("2020-01-01", periods=6, freq="MS")
    score = pd.Series([1.0, np.nan, 2.0, 0.5, 1.5, np.nan], index=idx)
    label = pd.Series([1.0, 0.0, 1.0, 0.0, np.nan, 1.0], index=idx)
    r = compute_calibration(score, label, threshold=1.0)
    # 有效對齊 = (1,1) (2,1) (0.5,0) → 預測 1,1,0 → 實際 1,1,0
    assert r.tp == 2 and r.tn == 1 and r.fp == 0 and r.fn == 0


def test_grid_search_finds_best_threshold():
    score = pd.Series([0.0, 0.2, 0.5, 1.0, 1.5, 2.0, 2.5])
    label = pd.Series([0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
    df = grid_search_threshold(score, label)
    assert {"threshold", "precision", "recall", "f1"}.issubset(df.columns)
    assert df.iloc[0]["f1"] >= df.iloc[-1]["f1"]  # 排序遞減
    assert df["f1"].max() == 1.0


def test_synthetic_demo_shape_and_stress_signal():
    df_macro, spx = generate_synthetic_demo(n_months=60, seed=42)
    assert len(df_macro) == 60 and len(spx) == 60
    assert {"VIX", "HY_Spread", "Yield_Curve_10Y_2Y"}.issubset(df_macro.columns)
    assert (df_macro["VIX"] > 30).sum() >= 4  # 至少 4 個月的壓力
    assert spx.pct_change().min() < -0.05  # SPX 至少有一個月跌 > 5%


def test_rolling_risk_score_pipeline():
    df_macro, spx = generate_synthetic_demo(n_months=60, seed=42)
    score = rolling_risk_score(df_macro, window=24)
    label = label_forward_drawdown(spx, horizon_months=3, threshold=-0.10)
    assert score.iloc[:24].isna().all()
    assert score.iloc[24:].notna().any()
    df = grid_search_threshold(score, label)
    # pipeline 跑得通且至少能命中一些（合成資料 score 對 forward label 本來就 lag，
    # 這正是校準要揭露的真實侷限，故只驗證 > 0 而非高 F1）
    assert df["f1"].max() > 0.0
    assert (df["precision"] > 0).any()


def test_rolling_risk_score_missing_columns_returns_nan():
    df_macro = pd.DataFrame(
        {"VIX": [15, 16, 17]},
        index=pd.date_range("2020-01-01", periods=3, freq="MS"),
    )
    score = rolling_risk_score(df_macro, window=2)
    assert score.isna().all()


# ════════════════════════════════════════════════════════════
# fetch_real_3factor_monthly (v18.253) — 邊界 + import 防護
# ════════════════════════════════════════════════════════════
def test_fetch_real_3factor_monthly_no_api_key():
    from services.risk_calibration import fetch_real_3factor_monthly

    df, spx, notes = fetch_real_3factor_monthly("", years=10)
    assert df.empty
    assert spx.empty
    assert any("FRED API key" in w for w in notes["warnings"])


def test_fetch_real_3factor_monthly_returns_tuple_schema():
    from services.risk_calibration import fetch_real_3factor_monthly

    result = fetch_real_3factor_monthly("", years=5)
    assert isinstance(result, tuple) and len(result) == 3
    df, spx, notes = result
    assert hasattr(df, "columns") and hasattr(spx, "index")
    assert "missing_factors" in notes and "warnings" in notes
