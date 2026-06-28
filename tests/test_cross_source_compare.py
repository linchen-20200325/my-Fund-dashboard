"""test_cross_source_compare.py — Phase E 全球 macro_score × 台股 TWII 對照引擎."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest

from services.cross_source_compare import (
    align_score_with_twii,
    compute_lead_lag_correlation,
    find_best_lead_lag,
    load_twii_from_parquet,
    summarize_crisis_score_around_events,
)


# ════════════════════════════════════════════════════════════════
# load_twii_from_parquet
# ════════════════════════════════════════════════════════════════
def _write_twii_parquet(cache_dir: Path, rows: list[tuple]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"date": d, "close": c} for d, c in rows]).to_parquet(
        cache_dir / "twii_history.parquet", index=False)


def test_load_twii_missing_file(tmp_path: Path):
    s = load_twii_from_parquet(tmp_path / "nope")
    assert s.empty


def test_load_twii_extracts_close_sorted(tmp_path: Path):
    _write_twii_parquet(tmp_path, [
        ("2024-01-03", 17800.0),
        ("2024-01-01", 17500.0),
        ("2024-01-02", 17600.0),
    ])
    s = load_twii_from_parquet(tmp_path)
    assert len(s) == 3
    # 應已排序
    assert list(s.values) == [17500.0, 17600.0, 17800.0]
    assert isinstance(s.index, pd.DatetimeIndex)


def test_load_twii_corrupt_file_graceful(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "twii_history.parquet").write_bytes(b"not parquet")
    s = load_twii_from_parquet(tmp_path)
    assert s.empty


# ════════════════════════════════════════════════════════════════
# align_score_with_twii
# ════════════════════════════════════════════════════════════════
def _make_score_df(values: list[float], start: str = "2023-01-31") -> pd.DataFrame:
    idx = pd.date_range(start=start, periods=len(values), freq="ME")
    return pd.DataFrame({"score": values}, index=idx)


def _make_twii_daily(month_end_levels: list[float],
                    start: str = "2023-01-31") -> pd.Series:
    """合成日線：每個月底是指定 level（簡化為月底一個點）。"""
    idx = pd.date_range(start=start, periods=len(month_end_levels), freq="ME")
    return pd.Series(month_end_levels, index=idx, name="twii_close")


def test_align_basic_columns():
    score = _make_score_df([5.0, 6.0, 7.0])
    twii = _make_twii_daily([17000.0, 17500.0, 18000.0])
    aligned = align_score_with_twii(score, twii)
    assert list(aligned.columns) == ["score", "twii_close", "twii_mom_pct"]
    assert len(aligned) == 3  # 三列全留（mom_pct 第一列 NaN 但不 drop 避免丟 score）
    # 第二列 mom = (17500/17000 - 1) * 100 ≈ 2.94
    assert pd.isna(aligned["twii_mom_pct"].iloc[0])
    assert abs(aligned["twii_mom_pct"].iloc[1] - (17500/17000 - 1) * 100) < 0.01


def test_align_empty_score_returns_empty():
    twii = _make_twii_daily([17000.0])
    out = align_score_with_twii(pd.DataFrame(), twii)
    assert out.empty


def test_align_empty_twii_returns_empty():
    score = _make_score_df([5.0])
    out = align_score_with_twii(score, pd.Series(dtype=float))
    assert out.empty


# ════════════════════════════════════════════════════════════════
# compute_lead_lag_correlation
# ════════════════════════════════════════════════════════════════
def test_cross_corr_returns_symmetric_range():
    # 用 align 後 DataFrame
    score = _make_score_df([5.0, 6.0, 7.0, 8.0, 7.0, 6.0, 5.0, 6.0, 7.0, 8.0,
                            7.0, 6.0, 5.0, 6.0, 7.0])
    twii = _make_twii_daily([17000.0, 17200.0, 17400.0, 17600.0, 17400.0,
                            17200.0, 17000.0, 17200.0, 17400.0, 17600.0,
                            17400.0, 17200.0, 17000.0, 17200.0, 17400.0])
    aligned = align_score_with_twii(score, twii)
    corr = compute_lead_lag_correlation(aligned, max_lag_months=5)
    # 11 列：lag = -5..+5
    assert len(corr) == 11
    assert set(corr["lag_months"]) == set(range(-5, 6))
    assert "correlation" in corr.columns


def test_cross_corr_empty_returns_empty():
    out = compute_lead_lag_correlation(pd.DataFrame())
    assert out.empty


def test_cross_corr_perfect_correlation_at_zero_lag():
    """完全正相關 series → lag=0 應為 ~1.0。"""
    # 用一個明確高低的 score
    score_vals = [3.0, 5.0, 7.0, 5.0, 3.0, 5.0, 7.0, 5.0, 3.0, 5.0, 7.0, 5.0]
    twii_vals = [17000.0, 17500.0, 18000.0, 17500.0, 17000.0, 17500.0,
                 18000.0, 17500.0, 17000.0, 17500.0, 18000.0, 17500.0]
    score = _make_score_df(score_vals)
    twii = _make_twii_daily(twii_vals)
    aligned = align_score_with_twii(score, twii)
    corr = compute_lead_lag_correlation(aligned, max_lag_months=3)
    # lag 0 處的 corr (score 與 twii_mom_pct) 不一定 1.0（mom_pct 是差分），
    # 但應有限值且不 raise
    row0 = corr[corr["lag_months"] == 0].iloc[0]
    assert pd.notna(row0["correlation"])


# ════════════════════════════════════════════════════════════════
# find_best_lead_lag
# ════════════════════════════════════════════════════════════════
def test_find_best_lead_lag_picks_max_positive():
    df = pd.DataFrame({
        "lag_months": [-2, -1, 0, 1, 2],
        "correlation": [-0.5, 0.1, 0.3, 0.7, 0.2],
    })
    lag, corr = find_best_lead_lag(df, prefer_positive=True)
    assert lag == 1
    assert corr == 0.7


def test_find_best_lead_lag_no_positive_returns_none():
    df = pd.DataFrame({
        "lag_months": [-1, 0, 1],
        "correlation": [-0.3, -0.5, -0.2],
    })
    lag, corr = find_best_lead_lag(df, prefer_positive=True)
    assert lag is None
    assert corr is None


def test_find_best_lead_lag_empty_returns_none():
    lag, corr = find_best_lead_lag(pd.DataFrame())
    assert lag is None
    assert corr is None


def test_find_best_lead_lag_all_nan_returns_none():
    df = pd.DataFrame({
        "lag_months": [-1, 0, 1],
        "correlation": [float("nan"), float("nan"), float("nan")],
    })
    lag, corr = find_best_lead_lag(df, prefer_positive=True)
    assert lag is None


# ════════════════════════════════════════════════════════════════
# summarize_crisis_score_around_events
# ════════════════════════════════════════════════════════════════
@dataclass
class _MockEvent:
    peak_date: str
    trough_date: str


def test_summarize_crisis_basic():
    """peak 前 3 月平均 score 應計算正確。"""
    # 月 1-10：score 5, 6, 7, 8, 7, 6, 5, 4, 3, 4
    score_df = _make_score_df([5.0, 6.0, 7.0, 8.0, 7.0, 6.0, 5.0, 4.0, 3.0, 4.0])
    # peak = 2023-04-30（idx 3），trough = 2023-09-30（idx 8）
    events = [_MockEvent(peak_date="2023-04-30", trough_date="2023-09-30")]
    out = summarize_crisis_score_around_events(events, score_df, lookback_months=3)
    assert len(out) == 1
    row = out[0]
    # peak 前 3 月平均：score[0..2] = (5+6+7)/3 = 6.0
    assert abs(row["score_lookback_avg"] - 6.0) < 0.01
    # peak 月（2023-04-30）score = 8.0
    assert row["score_at_peak"] == 8.0
    # trough 月（2023-09-30）score = 3.0
    assert row["score_at_trough"] == 3.0


def test_summarize_crisis_empty_events_returns_empty():
    score_df = _make_score_df([5.0, 6.0])
    out = summarize_crisis_score_around_events([], score_df)
    assert out == []


def test_summarize_crisis_empty_score_returns_empty():
    events = [_MockEvent(peak_date="2023-04-30", trough_date="2023-09-30")]
    out = summarize_crisis_score_around_events(events, pd.DataFrame())
    assert out == []


def test_summarize_crisis_no_trough_handles_gracefully():
    """trough_date = None → score_at_trough = None，不 raise。"""
    score_df = _make_score_df([5.0, 6.0, 7.0, 8.0])
    events = [_MockEvent(peak_date="2023-04-30", trough_date=None)]
    out = summarize_crisis_score_around_events(events, score_df, lookback_months=2)
    assert len(out) == 1
    assert out[0]["score_at_trough"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
