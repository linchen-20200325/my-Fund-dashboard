"""test_cluster_calibration.py — v18.292 per-cluster F1 backtest"""
from __future__ import annotations

import json

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _isolate_cache(tmp_path, monkeypatch):
    """每 test 換 tmp_path 不污染 cache/cluster_calibration.json。"""
    from services import cluster_calibration
    monkeypatch.setattr(
        cluster_calibration, "_CACHE_FILE",
        tmp_path / "cluster_calibration.json",
    )
    monkeypatch.setattr(cluster_calibration, "_CACHE_DIR", tmp_path)
    yield


# ─── compute_cluster_f1 ───────────────────────────────
def test_f1_perfect_match():
    """signal 紅燈 ↔ truth 1 完全對應 → F1 = 1.0"""
    from services.cluster_calibration import compute_cluster_f1
    idx = pd.date_range("2020-01-31", periods=5, freq="ME")
    signals = pd.Series(["🔴 危險", "🟢 安全", "🔴 危險", "🟢 安全", "🟢 安全"], index=idx)
    truth = pd.Series([1, 0, 1, 0, 0], index=idx, dtype=float)
    r = compute_cluster_f1(signals, truth)
    assert r["tp"] == 2 and r["fp"] == 0 and r["fn"] == 0 and r["tn"] == 3
    assert r["precision"] == 1.0
    assert r["recall"] == 1.0
    assert r["f1"] == 1.0


def test_f1_all_wrong():
    """signal 紅燈時 truth 都 0 → F1 = 0"""
    from services.cluster_calibration import compute_cluster_f1
    idx = pd.date_range("2020-01-31", periods=4, freq="ME")
    signals = pd.Series(["🔴 危險", "🔴 危險", "🟢 安全", "🟢 安全"], index=idx)
    truth = pd.Series([0, 0, 1, 1], index=idx, dtype=float)
    r = compute_cluster_f1(signals, truth)
    assert r["tp"] == 0
    assert r["precision"] == 0.0
    assert r["recall"] == 0.0
    assert r["f1"] == 0.0


def test_f1_high_precision_low_recall():
    """signal 紅燈每次都對，但漏抓很多 → precision=1, recall 低"""
    from services.cluster_calibration import compute_cluster_f1
    idx = pd.date_range("2020-01-31", periods=10, freq="ME")
    # 5 真危險 + 5 平安；只 1 個 cluster 抓對
    signals = pd.Series(
        ["🔴 危險"] + ["🟢 安全"] * 9, index=idx,
    )
    truth = pd.Series([1] * 5 + [0] * 5, index=idx, dtype=float)
    r = compute_cluster_f1(signals, truth)
    assert r["tp"] == 1 and r["fp"] == 0 and r["fn"] == 4
    assert r["precision"] == 1.0
    assert r["recall"] == 0.2
    # F1 = 2 * 1 * 0.2 / 1.2 ≈ 0.333
    assert r["f1"] == pytest.approx(0.333, abs=0.01)


def test_f1_empty_returns_zeros():
    from services.cluster_calibration import compute_cluster_f1
    r = compute_cluster_f1(pd.Series(dtype=str), pd.Series(dtype=float))
    assert r["f1"] == 0.0
    assert r["n_obs"] == 0


def test_f1_drops_nan():
    """NaN 值不算進去。"""
    from services.cluster_calibration import compute_cluster_f1
    idx = pd.date_range("2020-01-31", periods=4, freq="ME")
    signals = pd.Series(["🔴 危險", None, "🔴 危險", "🟢 安全"], index=idx)
    truth = pd.Series([1, 1, 1, 0], index=idx, dtype=float)
    r = compute_cluster_f1(signals, truth)
    # 只剩 3 個有效對應
    assert r["n_obs"] == 3


# ─── _signal_from_norm ─────────────────────────────────
def test_signal_from_norm_thresholds():
    from services.cluster_calibration import _signal_from_norm
    assert _signal_from_norm(0.5).startswith("🟢")
    assert _signal_from_norm(0.3).startswith("🟢")  # 邊界
    assert _signal_from_norm(0.29).startswith("🟡")
    assert _signal_from_norm(0.0).startswith("🟡")
    assert _signal_from_norm(-0.29).startswith("🟡")
    assert _signal_from_norm(-0.3).startswith("🔴")  # 邊界
    assert _signal_from_norm(-1.0).startswith("🔴")


# ─── _spx_forward_drawdown_labels ─────────────────────
def test_truth_label_no_crash_below_threshold():
    """SPX 線性上漲 → 沒月份觸發 -10% → 全 0。"""
    from services.cluster_calibration import _spx_forward_drawdown_labels
    idx = pd.date_range("2020-01-01", periods=365 * 2, freq="D")
    spx = pd.Series(range(100, 100 + len(idx)), index=idx, dtype=float)
    labels = _spx_forward_drawdown_labels(spx, horizon_months=3, threshold=-0.10)
    assert (labels.dropna() == 0).all()


def test_truth_label_detects_crash():
    """SPX 跌 30% → 該月應標 1。"""
    from services.cluster_calibration import _spx_forward_drawdown_labels
    idx = pd.date_range("2020-01-01", periods=200, freq="D")
    # 前 50 天高位 100，後 150 天跌到 70
    vals = [100.0] * 50 + list(range(100, 70, -1)) + [70.0] * (200 - 50 - 30)
    spx = pd.Series(vals[:200], index=idx, dtype=float)
    labels = _spx_forward_drawdown_labels(spx, horizon_months=3, threshold=-0.10)
    # 前段應該有月份是 1（因為後續會跌 30%）
    assert (labels.dropna() == 1).any()


def test_truth_label_empty_returns_empty():
    from services.cluster_calibration import _spx_forward_drawdown_labels
    r = _spx_forward_drawdown_labels(pd.Series(dtype=float))
    assert r.empty


# ─── _cluster_norm_history ─────────────────────────────
def test_cluster_norm_history_uses_only_available_keys():
    """只給 PMI（屬製造業）→ 製造業 cluster 應有值，其他 cluster 為空。"""
    from services.cluster_calibration import _cluster_norm_history
    idx = pd.date_range("2020-01-31", periods=3, freq="ME")
    score_df = pd.DataFrame({"PMI": [2.0, -2.0, 0.0]}, index=idx)
    weights = {"PMI": 2.0}
    out = _cluster_norm_history(score_df, weights)
    assert "製造業景氣" in out.columns
    # PMI = 2.0 / w=2 → norm = 1.0
    assert out["製造業景氣"].iloc[0] == 1.0
    assert out["製造業景氣"].iloc[1] == -1.0
    assert out["製造業景氣"].iloc[2] == 0.0
    # 其他 cluster 應為 NaN（無對應 key）
    assert out["匯率"].isna().all()


# ─── f1_to_grade ───────────────────────────────────────
def test_grade_thresholds():
    from services.cluster_calibration import f1_to_grade
    assert f1_to_grade(0.85)[0] == "可信"
    assert f1_to_grade(0.7)[0] == "可信"  # 邊界
    assert f1_to_grade(0.69)[0] == "參考"
    assert f1_to_grade(0.5)[0] == "參考"
    assert f1_to_grade(0.49)[0] == "雜訊"
    assert f1_to_grade(0.0)[0] == "雜訊"
    assert f1_to_grade(None)[0] == "n/a"


# ─── cache save/load ──────────────────────────────────
def test_cache_save_and_load():
    from services.cluster_calibration import (
        get_cached_calibration, save_calibration,
    )
    import time as _t
    payload = {"timestamp": _t.time(), "clusters": [{"name": "test", "f1": 0.6}]}
    assert save_calibration(payload) is True
    cached = get_cached_calibration()
    assert cached is not None
    assert cached["clusters"][0]["name"] == "test"


def test_cache_expired_returns_none():
    """timestamp 超過 30 天 → 視為過期。"""
    from services.cluster_calibration import (
        get_cached_calibration, save_calibration,
    )
    import time as _t
    payload = {"timestamp": _t.time() - 31 * 86400, "clusters": []}
    save_calibration(payload)
    assert get_cached_calibration() is None


def test_cache_missing_returns_none():
    from services.cluster_calibration import get_cached_calibration
    assert get_cached_calibration() is None
