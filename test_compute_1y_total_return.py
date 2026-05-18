"""test_compute_1y_total_return.py — v18.134 共用 1Y 含息報酬 helper 測試

修使用者反饋「Tab2 vs Tab3 同基金 1Y 報酬不同」— 抽 helper 後驗證統一行為。
"""
from __future__ import annotations

from ui.helpers.macro_helpers import compute_1y_total_return


def test_perf_1y_takes_priority():
    """perf['1Y'] 應該最優先（wb01 真 1Y 最權威，PR #122 設計）。"""
    obj = {
        "metrics": {"ret_1y_total": 37.6, "ret_1y": 10.0},   # 本地計算 high
        "moneydj_raw": {"perf": {"1Y": 9.09}},                 # wb01 low
    }
    v, src = compute_1y_total_return(obj)
    assert v == 9.09
    assert "perf" in src.lower() or "wb01" in src.lower()


def test_wb01_source_label():
    obj = {
        "moneydj_raw": {"perf": {"1Y": 9.09}},
        "perf_source": "wb01",
    }
    v, src = compute_1y_total_return(obj)
    assert v == 9.09
    assert "wb01" in src


def test_local_calc_source_label():
    obj = {
        "moneydj_raw": {"perf": {"1Y": 12.5}},
        "perf_source": "local_calc",
    }
    v, src = compute_1y_total_return(obj)
    assert v == 12.5
    assert "本地還原淨值法" in src or "local" in src.lower()


def test_fallback_to_ret_1y_total():
    """perf['1Y'] 缺 → fallback ret_1y_total。"""
    obj = {"metrics": {"ret_1y_total": 15.2}, "moneydj_raw": {}}
    v, src = compute_1y_total_return(obj)
    assert v == 15.2
    assert "ret_1y_total" in src


def test_short_window_label():
    """ret_1y_window_days < 350 應標短窗口。"""
    obj = {
        "metrics": {"ret_1y_total": 25.0, "ret_1y_window_days": 90},
        "moneydj_raw": {},
    }
    v, src = compute_1y_total_return(obj)
    assert v == 25.0
    assert "90d" in src or "短窗口" in src or "窗口" in src


def test_fallback_to_ret_1y():
    """ret_1y_total 也缺 → ret_1y（純 NAV）。"""
    obj = {"metrics": {"ret_1y": 8.5}, "moneydj_raw": {}}
    v, src = compute_1y_total_return(obj)
    assert v == 8.5
    assert "ret_1y" in src or "NAV" in src


def test_all_missing_returns_none():
    obj = {"metrics": {}, "moneydj_raw": {}}
    v, src = compute_1y_total_return(obj)
    assert v is None
    assert src == "—"


def test_nav_series_fallback():
    """metrics 全缺、有 NAV series → 自算年化。"""
    import pandas as pd
    idx = pd.date_range("2024-01-01", "2025-01-01", freq="D")
    s = pd.Series([100.0] * len(idx[:-1]) + [110.0], index=idx)
    obj = {"metrics": {}, "moneydj_raw": {}, "series": s}
    v, src = compute_1y_total_return(obj)
    assert v is not None
    assert abs(v - 10.0) < 1.0   # ~10% over 1 year
    assert "NAV" in src
