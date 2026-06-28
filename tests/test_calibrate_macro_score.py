"""test_calibrate_macro_score.py — D 案修正版 5 重 anti-overfit gate (v18.279)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.calibrate_macro_score import (
    CalibrationConfig,
    DEFAULT_VIX_CRISIS,
    DEFAULT_VIX_WARNING,
    VIX_CRISIS_CAP,
    VIX_WARNING_CAP,
    _bootstrap_paired_diff,
    _make_vix_score_fn,
    _spearman_corr,
    align_score_with_forward_return,
    build_proposal_report,
    build_score_rules_with_overrides,
    compute_objective,
    emit_thresholds_json,
    iter_valid_cells,
    load_spx_from_parquet,
    walk_forward_calibrate,
)


# ════════════════════════════════════════════════════════════════
# load_spx_from_parquet
# ════════════════════════════════════════════════════════════════
def _write_spx_parquet(cache_dir: Path, rows: list[tuple]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"date": d, "close": c} for d, c in rows]).to_parquet(
        cache_dir / "spx_history.parquet", index=False)


def test_load_spx_missing_file(tmp_path: Path):
    s = load_spx_from_parquet(tmp_path / "nope")
    assert s.empty


def test_load_spx_resamples_to_month_end(tmp_path: Path):
    _write_spx_parquet(tmp_path, [
        ("2024-01-15", 4800.0), ("2024-01-31", 4850.0),
        ("2024-02-15", 4900.0), ("2024-02-29", 4950.0),
    ])
    s = load_spx_from_parquet(tmp_path)
    assert len(s) == 2
    assert s.iloc[0] == 4850.0  # Jan last
    assert s.iloc[1] == 4950.0  # Feb last


def test_load_spx_corrupt_file_graceful(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "spx_history.parquet").write_bytes(b"not parquet")
    s = load_spx_from_parquet(tmp_path)
    assert s.empty


# ════════════════════════════════════════════════════════════════
# _make_vix_score_fn / build_score_rules_with_overrides
# ════════════════════════════════════════════════════════════════
def test_make_vix_score_fn_boundary():
    fn = _make_vix_score_fn(crisis_thr=30.0, warning_thr=18.0)
    assert fn(15.0) == 1.0    # 低恐慌
    assert fn(18.0) == 0.0    # 警戒邊界（非嚴格小於）
    assert fn(20.0) == 0.0    # 中性
    assert fn(30.0) == 0.0    # 危機邊界（非嚴格大於）
    assert fn(35.0) == -1.0   # 高恐慌


def test_make_vix_score_fn_custom_thresholds():
    fn = _make_vix_score_fn(crisis_thr=25.0, warning_thr=15.0)
    assert fn(14.0) == 1.0
    assert fn(20.0) == 0.0
    assert fn(26.0) == -1.0


def test_build_score_rules_overrides_only_vix():
    from services.macro_validation import SCORE_RULES as BASE
    out = build_score_rules_with_overrides(BASE, vix_crisis=27.0, vix_warning=16.0)
    # VIX 用新閾值
    assert out["VIX"][1](15.0) == 1.0
    assert out["VIX"][1](20.0) == 0.0
    assert out["VIX"][1](28.0) == -1.0
    # 其他指標不動
    assert out["PMI"][1](55) == 2.0
    assert out["HY_SPREAD"][1](3) == 2.0
    # weight 不動
    assert out["VIX"][0] == 1.0


# ════════════════════════════════════════════════════════════════
# _spearman_corr
# ════════════════════════════════════════════════════════════════
def test_spearman_perfect_positive():
    x = pd.Series([1, 2, 3, 4, 5])
    y = pd.Series([10, 20, 30, 40, 50])
    assert _spearman_corr(x, y) == pytest.approx(1.0)


def test_spearman_perfect_negative():
    x = pd.Series([1, 2, 3, 4, 5])
    y = pd.Series([50, 40, 30, 20, 10])
    assert _spearman_corr(x, y) == pytest.approx(-1.0)


def test_spearman_zero_variance():
    x = pd.Series([5, 5, 5, 5])
    y = pd.Series([1, 2, 3, 4])
    assert _spearman_corr(x, y) == 0.0


def test_spearman_insufficient_samples():
    assert _spearman_corr(pd.Series([1]), pd.Series([1])) == 0.0
    assert _spearman_corr(pd.Series([], dtype=float), pd.Series([], dtype=float)) == 0.0


# ════════════════════════════════════════════════════════════════
# compute_objective — penalty 必須懲罰偏離
# ════════════════════════════════════════════════════════════════
def test_objective_penalty_grows_with_deviation():
    aligned = pd.DataFrame({
        "score": [5.0, 6.0, 7.0, 8.0, 7.0, 6.0],
        "fwd_ret": [0.05, 0.06, 0.07, 0.08, 0.07, 0.06],
    })
    # default = (30, 18) → 0 deviation
    obj_default = compute_objective(aligned, 30.0, 18.0)
    # 偏離 default → penalty 觸發
    obj_off = compute_objective(aligned, 35.0, 14.0)
    # 兩者相關性相同（aligned 不變），但 obj_off 應該因 penalty 更低
    assert obj_default > obj_off


def test_objective_empty_returns_neg_inf():
    assert compute_objective(pd.DataFrame(), 30.0, 18.0) == float("-inf")


# ════════════════════════════════════════════════════════════════
# iter_valid_cells — warning < crisis 強制
# ════════════════════════════════════════════════════════════════
def test_iter_valid_cells_filters_monotonic():
    cells = iter_valid_cells(
        crisis_grid=(25.0, 30.0),
        warning_grid=(18.0, 22.0, 28.0),
    )
    # (25, 28) 應被剔除（28 ≥ 25）
    # (25, 22) ✓ (25, 18) ✓ (30, 28) ✓ (30, 22) ✓ (30, 18) ✓
    assert (25.0, 28.0) not in cells
    assert (25.0, 22.0) in cells
    assert (30.0, 28.0) in cells
    assert len(cells) == 5


def test_iter_valid_cells_default_full():
    cells = iter_valid_cells()
    # v19.174:C2-C v19.159 後 warning_grid 對齊 SSOT 22 重心移到 (18,20,22,24,26)。
    # crisis_grid=(25,27,30,32,35), warning_grid=(18,20,22,24,26)
    # c=25 排除 w=26(w>=c)→ 4 個;其餘 c ∈ {27,30,32,35} 全 5 個保留 → 4+5×4 = 24
    assert len(cells) == 24


# ════════════════════════════════════════════════════════════════
# align_score_with_forward_return
# ════════════════════════════════════════════════════════════════
def test_align_basic_3m_forward():
    idx = pd.date_range("2024-01-31", periods=6, freq="ME")
    score_df = pd.DataFrame({"score": [5, 6, 7, 6, 5, 4]}, index=idx)
    spx = pd.Series([100, 110, 121, 133, 146, 160], index=idx)
    aligned = align_score_with_forward_return(score_df, spx, horizon_months=3)
    # 第 0 個月：score=5, fwd=spx[3]/spx[0]-1 = 133/100-1 = 0.33
    assert aligned["score"].iloc[0] == 5
    assert aligned["fwd_ret"].iloc[0] == pytest.approx(0.33, abs=0.01)
    # 最後 3 個月 fwd_ret 應 NaN → dropna 剔除
    assert len(aligned) == 3


def test_align_empty_inputs():
    assert align_score_with_forward_return(pd.DataFrame(), pd.Series(dtype=float)).empty


# ════════════════════════════════════════════════════════════════
# Bootstrap CI 結構
# ════════════════════════════════════════════════════════════════
def test_bootstrap_paired_diff_returns_list():
    paired = pd.DataFrame({
        "score_rec": [5, 6, 7, 8, 7, 6, 5, 4, 5, 6] * 3,
        "score_def": [5, 5, 6, 7, 7, 6, 5, 4, 5, 5] * 3,
        "fwd_ret": [0.05, 0.06, 0.07, 0.08, 0.07, 0.06, 0.05, 0.04, 0.05, 0.06] * 3,
    })
    diffs = _bootstrap_paired_diff(paired, n_bootstrap=50)
    assert len(diffs) == 50
    assert all(isinstance(d, float) for d in diffs)


def test_bootstrap_paired_diff_empty():
    assert _bootstrap_paired_diff(pd.DataFrame(), n_bootstrap=10) == []




# ════════════════════════════════════════════════════════════════
# walk_forward_calibrate — 5 重 gate
# ════════════════════════════════════════════════════════════════
def _make_synthetic_indicators(n_months: int = 200) -> dict:
    """合成 indicators dict，給 walk_forward_calibrate 用。

    僅生成 VIX（其他指標未提供 → 不參與聚合，但 aggregate_score 仍會回 5.0）。
    """
    idx = pd.date_range(end=pd.Timestamp.today(), periods=n_months, freq="ME")
    # VIX 模擬：均值 20，波動 5，週期性 spike 模擬 crisis
    rng = np.random.default_rng(42)
    vix = 20 + 5 * np.sin(np.arange(n_months) * 2 * np.pi / 24) + rng.normal(0, 2, n_months)
    vix = np.clip(vix, 10, 45)
    return {
        "VIX": {"series": pd.Series(vix, index=idx, name="vix_close")},
    }


def _make_synthetic_spx(n_months: int = 200) -> pd.Series:
    idx = pd.date_range(end=pd.Timestamp.today(), periods=n_months, freq="ME")
    rng = np.random.default_rng(43)
    rets = rng.normal(0.005, 0.04, n_months)
    levels = 1000 * np.exp(np.cumsum(rets))
    return pd.Series(levels, index=idx, name="spx")


def test_walk_forward_insufficient_returns_fallback():
    """樣本太少 → fallback_insufficient，建議回 default。"""
    indicators = _make_synthetic_indicators(n_months=20)  # 20 月，4 折×24 月門檻不夠
    spx = _make_synthetic_spx(n_months=20)
    cfg = CalibrationConfig(n_folds=4, holdout_months=6, n_bootstrap=50,
                            min_samples_per_fold=24)
    result = walk_forward_calibrate(indicators, spx, cfg, years=2)
    assert result["status"] == "fallback_insufficient"
    assert result["recommended"] == (DEFAULT_VIX_CRISIS, DEFAULT_VIX_WARNING)


def test_walk_forward_full_pipeline_no_raise():
    """合成資料跑完整 pipeline，僅驗結構不 raise + status 在已知集合內。"""
    indicators = _make_synthetic_indicators(n_months=200)
    spx = _make_synthetic_spx(n_months=200)
    cfg = CalibrationConfig(n_folds=4, holdout_months=36, n_bootstrap=100,
                            min_samples_per_fold=24)
    result = walk_forward_calibrate(indicators, spx, cfg, years=17,
                                    cells=[(30.0, 18.0), (27.0, 16.0), (32.0, 20.0)])
    assert result["status"] in {
        "adopted", "fallback_overfit", "fallback_bootstrap",
        "fallback_capped", "fallback_insufficient",
    }
    # recommended 必須在 cap 內
    rec_c, rec_w = result["recommended"]
    assert VIX_CRISIS_CAP[0] <= rec_c <= VIX_CRISIS_CAP[1]
    assert VIX_WARNING_CAP[0] <= rec_w <= VIX_WARNING_CAP[1]


def test_walk_forward_empty_alignment_returns_fallback():
    """SPX 為空 → align 空 → fallback_insufficient。"""
    indicators = _make_synthetic_indicators(n_months=100)
    spx = pd.Series(dtype=float)
    cfg = CalibrationConfig(n_folds=4, holdout_months=12, n_bootstrap=20)
    result = walk_forward_calibrate(indicators, spx, cfg, years=8)
    assert result["status"] == "fallback_insufficient"


# ════════════════════════════════════════════════════════════════
# emit_thresholds_json
# ════════════════════════════════════════════════════════════════
def test_emit_thresholds_json_new_file(tmp_path: Path):
    result = {
        "recommended": (28.0, 17.0),
        "default": (30.0, 18.0),
        "status": "adopted",
        "reason": "test",
        "config": {"n_folds": 4, "holdout_months": 36, "n_bootstrap": 1000,
                   "horizon_months": 3},
        "bootstrap": {"ci_low": 0.05, "ci_high": 0.15},
        "holdout": {"rec_corr": 0.45, "default_corr": 0.40},
    }
    path = tmp_path / "macro_thresholds_global.json"
    wrote = emit_thresholds_json(result, path)
    assert wrote is True
    cfg = json.loads(path.read_text(encoding="utf-8"))
    assert cfg["VIX_CRISIS_THRESHOLD"] == 28.0
    assert cfg["VIX_WARNING_THRESHOLD"] == 17.0
    assert cfg["status"] == "adopted"
    assert "last_calibrated" in cfg
    assert cfg["bootstrap_ci_low"] == 0.05


def test_emit_thresholds_json_no_write_if_unchanged(tmp_path: Path):
    path = tmp_path / "macro_thresholds_global.json"
    result = {
        "recommended": (30.0, 18.0),
        "default": (30.0, 18.0),
        "status": "adopted", "reason": "first",
        "config": {"n_folds": 4, "holdout_months": 36, "n_bootstrap": 1000,
                   "horizon_months": 3},
    }
    emit_thresholds_json(result, path)
    # 第二次相同值 → skip
    wrote = emit_thresholds_json(result, path)
    assert wrote is False


# ════════════════════════════════════════════════════════════════
# build_proposal_report
# ════════════════════════════════════════════════════════════════
def test_proposal_report_contains_key_sections():
    result = {
        "recommended": (28.0, 17.0),
        "default": (30.0, 18.0),
        "status": "adopted",
        "reason": "test reason",
        "folds": [{
            "fold": 1, "train_start": "2010-01", "train_end": "2013-12",
            "test_start": "2014-01", "test_end": "2014-12",
            "best_crisis": 28.0, "best_warning": 17.0,
            "train_obj": 0.3, "test_obj": 0.25, "drift_pct": 16.7,
        }],
        "votes": {"28.0/17.0": 3, "30.0/18.0": 1},
        "bootstrap": {"n": 1000, "mean_diff": 0.05, "ci_low": 0.02, "ci_high": 0.08},
        "holdout": {"n_months": 36, "rec_corr": 0.45, "default_corr": 0.40},
        "config": {"n_folds": 4, "holdout_months": 36, "n_bootstrap": 1000,
                   "horizon_months": 3},
    }
    md = build_proposal_report(result)
    assert "VIX_CRISIS_THRESHOLD" in md
    assert "VIX_WARNING_THRESHOLD" in md
    assert "walk-forward" in md.lower()
    assert "bootstrap" in md.lower()
    assert "holdout" in md.lower()
    assert "28.0" in md or "28" in md


def test_proposal_report_fallback_marks_warning():
    result = {
        "recommended": (30.0, 18.0),
        "default": (30.0, 18.0),
        "status": "fallback_overfit",
        "reason": "drift 過半觸發",
        "folds": [], "votes": None, "bootstrap": None, "holdout": None,
        "config": {"n_folds": 4, "holdout_months": 36, "n_bootstrap": 1000,
                   "horizon_months": 3},
    }
    md = build_proposal_report(result)
    assert "不建議 merge" in md or "anti-overfit gate 觸發" in md


# ════════════════════════════════════════════════════════════════
# services/macro_validation 的 JSON loader hook
# ════════════════════════════════════════════════════════════════
def test_macro_validation_loader_reads_calibrated_json(tmp_path: Path, monkeypatch):
    """寫 JSON → import macro_validation 看 SCORE_RULES['VIX'] 是否吃新閾值。

    v19.174:C2-C v19.159 後 loader warning 越界守門改為 [18, 26](對齊 SSOT 22 重心)。
    原 warning=16.0 在新範圍外 → loader fallback 至 SSOT(crisis=30, warning=22)導致 assert 失敗。
    改用合法值 warning=20.0(在 [18,26])測讀取正確。
    """
    cfg = {
        "VIX_CRISIS_THRESHOLD": 27.0,
        "VIX_WARNING_THRESHOLD": 20.0,
    }
    (tmp_path / "macro_thresholds_global.json").write_text(
        json.dumps(cfg), encoding="utf-8")
    from services.macro_validation import _load_vix_calibrated_thresholds
    c, w = _load_vix_calibrated_thresholds(tmp_path)
    assert c == 27.0
    assert w == 20.0


def test_macro_validation_loader_rejects_out_of_cap(tmp_path: Path):
    cfg = {
        "VIX_CRISIS_THRESHOLD": 50.0,  # 越界
        "VIX_WARNING_THRESHOLD": 16.0,
    }
    (tmp_path / "macro_thresholds_global.json").write_text(
        json.dumps(cfg), encoding="utf-8")
    from services.macro_validation import (
        DEFAULT_VIX_CRISIS as D_C, DEFAULT_VIX_WARNING as D_W,
        _load_vix_calibrated_thresholds,
    )
    c, w = _load_vix_calibrated_thresholds(tmp_path)
    assert (c, w) == (D_C, D_W)  # fallback


def test_macro_validation_loader_rejects_warning_ge_crisis(tmp_path: Path):
    cfg = {
        "VIX_CRISIS_THRESHOLD": 28.0,
        "VIX_WARNING_THRESHOLD": 28.0,  # warning == crisis 不允許
    }
    (tmp_path / "macro_thresholds_global.json").write_text(
        json.dumps(cfg), encoding="utf-8")
    from services.macro_validation import (
        DEFAULT_VIX_CRISIS as D_C, DEFAULT_VIX_WARNING as D_W,
        _load_vix_calibrated_thresholds,
    )
    c, w = _load_vix_calibrated_thresholds(tmp_path)
    assert (c, w) == (D_C, D_W)


def test_macro_validation_loader_missing_file_returns_default(tmp_path: Path):
    from services.macro_validation import (
        DEFAULT_VIX_CRISIS as D_C, DEFAULT_VIX_WARNING as D_W,
        _load_vix_calibrated_thresholds,
    )
    c, w = _load_vix_calibrated_thresholds(tmp_path)  # tmp_path 內無 JSON
    assert (c, w) == (D_C, D_W)


def test_macro_validation_loader_corrupt_json_graceful(tmp_path: Path):
    (tmp_path / "macro_thresholds_global.json").write_text(
        "{not valid json", encoding="utf-8")
    from services.macro_validation import (
        DEFAULT_VIX_CRISIS as D_C, DEFAULT_VIX_WARNING as D_W,
        _load_vix_calibrated_thresholds,
    )
    c, w = _load_vix_calibrated_thresholds(tmp_path)
    assert (c, w) == (D_C, D_W)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
