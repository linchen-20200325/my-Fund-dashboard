#!/usr/bin/env python3
"""scripts/calibrate_macro_score.py — Macro Score 閾值校準 (D 案修正版 / v18.279).

User 需求：「我要不會過度擬合誤判的」。對齊 sister repo my-stock-dashboard
calibrate_macro_traffic.py 的 walk-forward + 票選 + drift 警語 4 重保護，
fund 端再加 ⑤ **末段 holdout 完全凍結** + ④ **bootstrap CI 顯著性檢定**，
共 5 重 anti-overfit gate。

校準對象（v18.279 起手版 + C2-C v19.159 SSOT 對齊）
==================================================
只校 VIX 兩個 cut-point：
- VIX_CRISIS_THRESHOLD（預設 30，grid [25, 27, 30, 32, 35]，cap [25, 35]）
- VIX_WARNING_THRESHOLD（C2-C v19.159 預設 22，grid [18, 20, 22, 24, 26],
  cap [18, 26]）— 對齊 macro_buckets._VIX_YELLOW SSOT
- 單調性約束：warning < crisis（無效 cell 自動剔除）

Ground truth：spx_history.parquet 月末 close → 3M forward return (Spearman corr)
Penalty：偏離教科書常數的線性懲罰（λ = 0.01）

5 重 anti-overfit gate
=====================
① 正則項 + 越界守門     — objective 含 deviation penalty + JSON loader 越界 fallback
② Walk-forward 4 折    — 滾動切折，永不在 train 自評
③ 折間票選 + drift 警語 — Counter 取多數 cell；過半折 drift > 30% 強制回退預設
④ Bootstrap 1000 次 CI — 訓練池 resample，95% CI 下界 ≤ 0 拒絕（顯著性不夠）
⑤ Holdout 末 36 月凍結 — 完全不進校準流程，最後拿來算 OOS final exam

CLI
===
    python scripts/calibrate_macro_score.py --bootstrap        # 標準跑
    python scripts/calibrate_macro_score.py --n-folds 3 --n-bootstrap 500
    python scripts/calibrate_macro_score.py --holdout-months 24
    python scripts/calibrate_macro_score.py \
        --emit-json data_cache/macro_thresholds_global.json \
        --emit-proposal MACRO_SCORE_CALIBRATION_PROPOSAL.md
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# scripts/ 下執行也能 import services.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd


CACHE_DIR = Path("data_cache")

# ════════════════════════════════════════════════════════════════
# Threshold spec — 校準對象的單一閾值規格
# ════════════════════════════════════════════════════════════════
# C2-C v19.159:VIX 閾值預設改 import SSOT(對齊 services/macro_validation.py)
from shared.macro_buckets import _VIX_RED as _MB_VIX_RED, _VIX_YELLOW as _MB_VIX_YELLOW

DEFAULT_VIX_CRISIS = _MB_VIX_RED         # = 30
DEFAULT_VIX_WARNING = _MB_VIX_YELLOW     # = 22(C2-C 從 18 改 SSOT)

# 越界守門(鏡像 services/macro_validation 重定 bound)
VIX_CRISIS_CAP = (25.0, 35.0)
VIX_WARNING_CAP = (18.0, 26.0)  # C2-C v19.159:原 (14, 22) → SSOT 重心 (18, 26)

# Grid(cap 內等距)
VIX_CRISIS_GRID: tuple = (25.0, 27.0, 30.0, 32.0, 35.0)
VIX_WARNING_GRID: tuple = (18.0, 20.0, 22.0, 24.0, 26.0)  # C2-C v19.159

# Penalty：偏離教科書常數每 1 點扣 λ
_PENALTY_WEIGHT = 0.01


@dataclass(frozen=True)
class CalibrationConfig:
    n_folds: int = 4
    holdout_months: int = 36          # 最後 36 月凍結
    n_bootstrap: int = 1000
    ci_alpha: float = 0.05            # 95% CI
    drift_warn_pct: float = 30.0      # 折間 drift 警語門檻
    horizon_months: int = 3           # forward return horizon
    min_samples_per_fold: int = 24    # 月頻每折至少 24 月（2 年）


# ════════════════════════════════════════════════════════════════
# I/O：spx_history.parquet → 月末 close series
# ════════════════════════════════════════════════════════════════
def load_spx_from_parquet(cache_dir: Path = CACHE_DIR) -> pd.Series:
    """讀 data_cache/spx_history.parquet → 月末 close。

    缺檔/壞檔 → 回空 Series。
    """
    path = cache_dir / "spx_history.parquet"
    if not path.exists():
        return pd.Series(dtype=float)
    try:
        df = pd.read_parquet(path)
        if df.empty or not {"date", "close"}.issubset(df.columns):
            return pd.Series(dtype=float)
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"])
        s = df.set_index("date")["close"].sort_index()
        return s.resample("ME").last().dropna()
    except Exception as e:  # noqa: BLE001
        print(f"[calibrate/load_spx] 讀檔失敗：{type(e).__name__}: {e}")
        return pd.Series(dtype=float)


# ════════════════════════════════════════════════════════════════
# score_fn override：用閾值 overrides 建構新 SCORE_RULES dict
# ════════════════════════════════════════════════════════════════
def _make_vix_score_fn(crisis_thr: float, warning_thr: float) -> Callable[[float], float]:
    """根據閾值產生 VIX score 函式（鏡像 SCORE_RULES['VIX'] 結構）。

    v < warning → +1.0（低恐慌，多頭）
    v > crisis  → -1.0（高恐慌，空頭）
    其他        →  0.0（震盪）
    """
    def _fn(v: float) -> float:
        if v < warning_thr:
            return 1.0
        if v > crisis_thr:
            return -1.0
        return 0.0
    return _fn


def build_score_rules_with_overrides(
    base_rules: dict, vix_crisis: float = DEFAULT_VIX_CRISIS,
    vix_warning: float = DEFAULT_VIX_WARNING,
) -> dict:
    """clone base SCORE_RULES，套用 VIX 閾值 override。其他指標不動。"""
    out = dict(base_rules)
    vix_weight = base_rules.get("VIX", (1.0, None))[0]
    out["VIX"] = (vix_weight, _make_vix_score_fn(vix_crisis, vix_warning))
    return out


# ════════════════════════════════════════════════════════════════
# Score series 與 forward return 對齊
# ════════════════════════════════════════════════════════════════
def compute_score_series_with_overrides(
    indicators: dict, vix_crisis: float, vix_warning: float,
    years: int = 15, freq: str = "ME",
) -> pd.DataFrame:
    """套用閾值 overrides → 重算月度 macro_score 序列。

    為避免循環依賴 services/macro_validation，這裡複製 calc_macro_score_series
    的核心邏輯，只把 SCORE_RULES 換成 override 版本。
    """
    from services.macro_validation import (
        SCORE_RULES as _BASE_RULES, aggregate_score,
    )

    rules = build_score_rules_with_overrides(
        _BASE_RULES, vix_crisis=vix_crisis, vix_warning=vix_warning)

    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=int(years))
    date_range = pd.date_range(start=start, end=end, freq=freq)

    aligned: dict[str, pd.Series] = {}
    for key in rules:
        ind = indicators.get(key)
        if not ind:
            continue
        s = ind.get("series")
        if s is None or (hasattr(s, "empty") and s.empty):
            continue
        s = s.copy()
        if not isinstance(s.index, pd.DatetimeIndex):
            try:
                s.index = pd.to_datetime(s.index)
            except Exception:
                continue
        aligned[key] = s.sort_index().reindex(date_range, method="ffill")

    rows = []
    for dt in date_range:
        scored: dict[str, tuple[float, float]] = {}
        for key, (w, score_fn) in rules.items():
            if key not in aligned:
                continue
            v = aligned[key].loc[dt]
            if pd.isna(v):
                continue
            try:
                s = float(score_fn(float(v)))
            except Exception:
                continue
            s = max(-w, min(w, s))
            scored[key] = (w, s)
        score, phase = aggregate_score(scored)
        rows.append({"date": dt, "score": score, "phase": phase,
                     "n_indicators": len(scored)})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.set_index("date")


def align_score_with_forward_return(
    score_df: pd.DataFrame, spx_monthly: pd.Series, horizon_months: int = 3,
) -> pd.DataFrame:
    """對齊 score(t) 與 SPX forward return(t → t+horizon)。

    Returns DataFrame[score, fwd_ret] 去除 NaN 列。
    """
    if score_df is None or score_df.empty or spx_monthly is None or spx_monthly.empty:
        return pd.DataFrame(columns=["score", "fwd_ret"])
    spx = spx_monthly.copy()
    # forward return: (spx_{t+h} / spx_t - 1) → shift -h
    fwd = (spx.shift(-int(horizon_months)) / spx - 1.0)
    df = pd.DataFrame({
        "score": score_df["score"],
        "fwd_ret": fwd,
    })
    return df.dropna()


# ════════════════════════════════════════════════════════════════
# Objective：Spearman correlation - deviation penalty
# ════════════════════════════════════════════════════════════════
def _spearman_corr(x: pd.Series, y: pd.Series) -> float:
    """純函式 Spearman（避開 scipy 依賴）。樣本 < 3 回 0.0。"""
    if x is None or y is None or len(x) < 3 or len(y) < 3:
        return 0.0
    xr = x.rank(method="average")
    yr = y.rank(method="average")
    if xr.std() == 0 or yr.std() == 0:
        return 0.0
    return float(xr.corr(yr))


def compute_objective(
    aligned: pd.DataFrame, vix_crisis: float, vix_warning: float,
    penalty_weight: float = _PENALTY_WEIGHT,
) -> float:
    """目標 = Spearman(score, fwd_ret) - λ × |偏離教科書常數|.

    score 高 → 擴張 → 預期 forward return 高 → 正相關
    懲罰：vix_crisis 偏離 30 / vix_warning 偏離 18 越遠扣越多
    """
    if aligned is None or aligned.empty:
        return float("-inf")
    corr = _spearman_corr(aligned["score"], aligned["fwd_ret"])
    deviation = abs(vix_crisis - DEFAULT_VIX_CRISIS) + abs(vix_warning - DEFAULT_VIX_WARNING)
    return corr - penalty_weight * deviation


# ════════════════════════════════════════════════════════════════
# Grid search：對單一 (crisis, warning) 組合算 objective
# ════════════════════════════════════════════════════════════════
def iter_valid_cells(
    crisis_grid: tuple = VIX_CRISIS_GRID, warning_grid: tuple = VIX_WARNING_GRID,
) -> list[tuple[float, float]]:
    """產生所有 (crisis, warning) 候選，強制 warning < crisis。"""
    out = []
    for c in crisis_grid:
        for w in warning_grid:
            if w < c:
                out.append((float(c), float(w)))
    return out


def grid_search_on_sample(
    indicators: dict, spx_monthly: pd.Series, sample_index: pd.DatetimeIndex,
    cells: list[tuple[float, float]], years: int = 15, horizon_months: int = 3,
) -> tuple[tuple[float, float], float]:
    """在 sample_index 上 grid search → 回 (best_cell, best_obj)。

    sample_index 是 train fold 的月末 timestamp；
    我們把 score 序列重算一次（全 15 年），再 .loc 取 sample_index 子集評分。
    """
    best_obj = float("-inf")
    best_cell = (DEFAULT_VIX_CRISIS, DEFAULT_VIX_WARNING)
    for crisis, warning in cells:
        score_df = compute_score_series_with_overrides(
            indicators, vix_crisis=crisis, vix_warning=warning,
            years=years, freq="ME")
        aligned = align_score_with_forward_return(
            score_df, spx_monthly, horizon_months=horizon_months)
        # 限制在 sample_index 範圍內
        sub = aligned.loc[aligned.index.isin(sample_index)]
        obj = compute_objective(sub, vix_crisis=crisis, vix_warning=warning)
        if obj > best_obj:
            best_obj = obj
            best_cell = (crisis, warning)
    return best_cell, best_obj


# ════════════════════════════════════════════════════════════════
# Bootstrap CI：訓練池 resample → 顯著性檢定
# ════════════════════════════════════════════════════════════════


# ════════════════════════════════════════════════════════════════
# Walk-forward + Holdout：5 重 gate 串接
# ════════════════════════════════════════════════════════════════
def walk_forward_calibrate(
    indicators: dict, spx_monthly: pd.Series, cfg: CalibrationConfig,
    years: int = 15, cells: Optional[list[tuple[float, float]]] = None,
) -> dict:
    """主流程：5 重 gate 串接 → 回完整校準結果 dict。

    Returns dict keys:
      - recommended: (vix_crisis, vix_warning)
      - default:     (30.0, 18.0)
      - status:      'adopted' / 'fallback_overfit' / 'fallback_bootstrap'
                     / 'fallback_capped' / 'fallback_insufficient'
      - reason:      若 fallback，敘述觸發的 gate
      - folds:       list of fold details
      - bootstrap:   {mean_diff, ci_low, ci_high}
      - holdout:     {n_months, obj_default, obj_rec, default_corr, rec_corr}
      - votes:       Counter 票選結果
    """
    if cells is None:
        cells = iter_valid_cells()

    default_cell = (DEFAULT_VIX_CRISIS, DEFAULT_VIX_WARNING)
    result = {
        "recommended": default_cell,
        "default": default_cell,
        "status": "adopted",
        "reason": "",
        "folds": [],
        "bootstrap": None,
        "holdout": None,
        "votes": None,
        "config": {
            "n_folds": cfg.n_folds,
            "holdout_months": cfg.holdout_months,
            "n_bootstrap": cfg.n_bootstrap,
            "horizon_months": cfg.horizon_months,
        },
    }

    # 基準 score 序列（default cell）
    score_df_default = compute_score_series_with_overrides(
        indicators, *default_cell, years=years)
    aligned_default = align_score_with_forward_return(
        score_df_default, spx_monthly, horizon_months=cfg.horizon_months)

    if aligned_default.empty:
        result["status"] = "fallback_insufficient"
        result["reason"] = "score×forward_return 對齊後無有效樣本"
        return result

    # Gate ⑤：holdout split（最後 N 月凍結）
    max_date = aligned_default.index.max()
    holdout_cutoff = max_date - pd.DateOffset(months=cfg.holdout_months)
    train_pool = aligned_default[aligned_default.index <= holdout_cutoff]
    holdout_set = aligned_default[aligned_default.index > holdout_cutoff]

    if len(train_pool) < cfg.n_folds * cfg.min_samples_per_fold:
        result["status"] = "fallback_insufficient"
        result["reason"] = (
            f"train_pool 樣本 {len(train_pool)} 月 < "
            f"{cfg.n_folds} 折 × {cfg.min_samples_per_fold} 月門檻"
        )
        return result

    # Gate ②：walk-forward grid search
    n = len(train_pool)
    fold_size = n // (cfg.n_folds + 1)  # 留 1 份初始 train
    folds = []
    for k in range(cfg.n_folds):
        train_end = (k + 1) * fold_size
        test_end = train_end + fold_size
        if test_end > n:
            break
        train_idx = train_pool.index[:train_end]
        test_idx = train_pool.index[train_end:test_end]
        if len(train_idx) < cfg.min_samples_per_fold or len(test_idx) < 12:
            continue

        best_cell, train_obj = grid_search_on_sample(
            indicators, spx_monthly, train_idx, cells,
            years=years, horizon_months=cfg.horizon_months)

        # test OOS：固定 best_cell 重算 score → 取 test_idx 子集
        score_df_best = compute_score_series_with_overrides(
            indicators, *best_cell, years=years)
        aligned_best = align_score_with_forward_return(
            score_df_best, spx_monthly, horizon_months=cfg.horizon_months)
        test_sub = aligned_best.loc[aligned_best.index.isin(test_idx)]
        test_obj = compute_objective(test_sub, *best_cell)

        # drift：(train - test) / |train|
        drift_pct = (
            (train_obj - test_obj) / max(abs(train_obj), 1e-6) * 100
            if abs(train_obj) > 1e-6 else 0.0
        )
        folds.append({
            "fold": k + 1,
            "train_start": train_idx[0].strftime("%Y-%m"),
            "train_end": train_idx[-1].strftime("%Y-%m"),
            "test_start": test_idx[0].strftime("%Y-%m"),
            "test_end": test_idx[-1].strftime("%Y-%m"),
            "best_crisis": best_cell[0],
            "best_warning": best_cell[1],
            "train_obj": round(train_obj, 4),
            "test_obj": round(test_obj, 4),
            "drift_pct": round(drift_pct, 1),
        })
    result["folds"] = folds

    if not folds:
        result["status"] = "fallback_insufficient"
        result["reason"] = "所有折樣本不足，無法完成 walk-forward"
        return result

    # Gate ③：folds drift 過半 > drift_warn → fallback default
    high_drift = sum(1 for f in folds if f["drift_pct"] > cfg.drift_warn_pct)
    if high_drift > len(folds) // 2:
        result["status"] = "fallback_overfit"
        result["reason"] = (
            f"{high_drift}/{len(folds)} 折 drift > {cfg.drift_warn_pct}%，"
            "過擬合警語觸發"
        )
        return result

    # Gate ③ part 2：票選 + 多數規則
    votes = Counter((f["best_crisis"], f["best_warning"]) for f in folds)
    rec_cell, vote_count = votes.most_common(1)[0]
    result["votes"] = {f"{c}/{w}": v for (c, w), v in votes.items()}

    # Gate ①：越界守門
    rec_c, rec_w = rec_cell
    if not (VIX_CRISIS_CAP[0] <= rec_c <= VIX_CRISIS_CAP[1]
            and VIX_WARNING_CAP[0] <= rec_w <= VIX_WARNING_CAP[1]
            and rec_w < rec_c):
        result["status"] = "fallback_capped"
        result["reason"] = (
            f"票選結果 (crisis={rec_c}, warning={rec_w}) 越界，"
            f"caps: crisis∈{VIX_CRISIS_CAP}, warning∈{VIX_WARNING_CAP}"
        )
        return result

    # 若票選結果 = default → 跳過 bootstrap，直接採用（無變動）
    if rec_cell == default_cell:
        result["recommended"] = default_cell
        result["status"] = "adopted"
        result["reason"] = "票選結果與預設一致，無需調整"
        # 仍算 holdout 供報告
        result["holdout"] = _eval_holdout(
            holdout_set, default_cell, default_cell, indicators, spx_monthly,
            years=years, horizon=cfg.horizon_months)
        return result

    # Gate ④：bootstrap CI 顯著性
    # 在 train_pool 上對比 rec vs default 的 objective 差
    score_df_rec = compute_score_series_with_overrides(
        indicators, *rec_cell, years=years)
    aligned_rec_train = align_score_with_forward_return(
        score_df_rec, spx_monthly, horizon_months=cfg.horizon_months)
    aligned_rec_train = aligned_rec_train.loc[aligned_rec_train.index <= holdout_cutoff]

    # bootstrap 需要 rec 與 default 在同樣 sample 上比；對齊兩者 index
    common_idx = train_pool.index.intersection(aligned_rec_train.index)
    paired = pd.DataFrame({
        "score_rec": aligned_rec_train.loc[common_idx, "score"],
        "score_def": train_pool.loc[common_idx, "score"],
        "fwd_ret": train_pool.loc[common_idx, "fwd_ret"],
    }).dropna()

    boot_diffs = _bootstrap_paired_diff(
        paired, n_bootstrap=cfg.n_bootstrap, seed=42)
    mean_diff = float(np.mean(boot_diffs)) if boot_diffs else 0.0
    ci_low = float(np.quantile(boot_diffs, cfg.ci_alpha / 2)) if boot_diffs else 0.0
    ci_high = float(np.quantile(boot_diffs, 1 - cfg.ci_alpha / 2)) if boot_diffs else 0.0
    result["bootstrap"] = {
        "n": cfg.n_bootstrap,
        "mean_diff": round(mean_diff, 4),
        "ci_low": round(ci_low, 4),
        "ci_high": round(ci_high, 4),
    }

    if ci_low <= 0:
        result["status"] = "fallback_bootstrap"
        result["reason"] = (
            f"bootstrap 95% CI 下界 {ci_low:.4f} ≤ 0，"
            "rec 未顯著優於 default"
        )
        return result

    # 全 gate 通過 → 採用 rec_cell
    result["recommended"] = rec_cell
    result["status"] = "adopted"
    result["reason"] = (
        f"票選 {vote_count}/{len(folds)} 折；"
        f"bootstrap 95% CI = [{ci_low:.4f}, {ci_high:.4f}]"
    )

    # Holdout final exam
    result["holdout"] = _eval_holdout(
        holdout_set, rec_cell, default_cell, indicators, spx_monthly,
        years=years, horizon=cfg.horizon_months)

    return result


def _bootstrap_paired_diff(
    paired: pd.DataFrame, n_bootstrap: int, seed: int = 42,
) -> list[float]:
    """在 paired (score_rec, score_def, fwd_ret) 上 resample → Spearman 差。"""
    if paired is None or paired.empty:
        return []
    rng = np.random.default_rng(seed)
    n = len(paired)
    diffs = []
    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        sub = paired.iloc[idx]
        corr_rec = _spearman_corr(sub["score_rec"], sub["fwd_ret"])
        corr_def = _spearman_corr(sub["score_def"], sub["fwd_ret"])
        diffs.append(corr_rec - corr_def)
    return diffs


def _eval_holdout(
    holdout: pd.DataFrame, cell_rec: tuple[float, float],
    cell_default: tuple[float, float], indicators: dict, spx: pd.Series,
    years: int, horizon: int,
) -> dict:
    """holdout 末段以 rec vs default 各自重算 score → Spearman。"""
    if holdout is None or holdout.empty:
        return {"n_months": 0, "rec_corr": None, "default_corr": None}
    # default 已是 holdout 那個 score（aligned_default 來源）
    default_corr = _spearman_corr(holdout["score"], holdout["fwd_ret"])
    # rec 重算
    score_rec = compute_score_series_with_overrides(
        indicators, *cell_rec, years=years)
    aligned_rec = align_score_with_forward_return(
        score_rec, spx, horizon_months=horizon)
    rec_holdout = aligned_rec.loc[aligned_rec.index.isin(holdout.index)]
    rec_corr = _spearman_corr(rec_holdout["score"], rec_holdout["fwd_ret"])
    return {
        "n_months": len(holdout),
        "rec_corr": round(rec_corr, 4),
        "default_corr": round(default_corr, 4),
    }


# ════════════════════════════════════════════════════════════════
# Emit：JSON + Markdown proposal
# ════════════════════════════════════════════════════════════════
def emit_thresholds_json(result: dict, path: Path) -> bool:
    """寫 macro_thresholds_global.json；值未變回 False（避免空 commit）。"""
    rec_c, rec_w = result["recommended"]
    payload = {
        "VIX_CRISIS_THRESHOLD": float(rec_c),
        "VIX_WARNING_THRESHOLD": float(rec_w),
        "status": result["status"],
        "reason": result["reason"],
        "last_calibrated": _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "method": (
            f"walk-forward {result['config']['n_folds']} folds × "
            f"holdout {result['config']['holdout_months']}m × "
            f"bootstrap {result['config']['n_bootstrap']}"
        ),
    }
    if result.get("bootstrap"):
        payload["bootstrap_ci_low"] = result["bootstrap"]["ci_low"]
        payload["bootstrap_ci_high"] = result["bootstrap"]["ci_high"]
    if result.get("holdout"):
        payload["holdout_rec_corr"] = result["holdout"].get("rec_corr")
        payload["holdout_default_corr"] = result["holdout"].get("default_corr")

    # 比對舊值（值未變不寫）
    if path.exists():
        try:
            old = json.loads(path.read_text(encoding="utf-8"))
            if (old.get("VIX_CRISIS_THRESHOLD") == payload["VIX_CRISIS_THRESHOLD"]
                and old.get("VIX_WARNING_THRESHOLD") == payload["VIX_WARNING_THRESHOLD"]
                and old.get("status") == payload["status"]):
                print(f"[emit-json] 值未變，跳過寫入 {path}")
                return False
        except Exception:
            pass

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8")
    print(f"[emit-json] ✅ 寫入 {path}")
    return True


def build_proposal_report(result: dict) -> str:
    """產出 MACRO_SCORE_CALIBRATION_PROPOSAL.md。"""
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    md = ["# MACRO_SCORE_CALIBRATION_PROPOSAL.md — VIX 閾值校準建議"]
    md.append("")
    md.append(f"> 自動產生：{now}　|　模式：D 案修正版（5 重 anti-overfit gate）")
    md.append("")
    rec_c, rec_w = result["recommended"]
    def_c, def_w = result["default"]
    md.append("## 🎯 建議 vs 預設")
    md.append("")
    md.append("| 參數 | 預設（教科書）| 建議 | 變動 |")
    md.append("|------|---------------|------|------|")
    md.append(f"| `VIX_CRISIS_THRESHOLD` | {def_c} | **{rec_c}** | {rec_c - def_c:+.1f} |")
    md.append(f"| `VIX_WARNING_THRESHOLD` | {def_w} | **{rec_w}** | {rec_w - def_w:+.1f} |")
    md.append("")
    md.append(f"**狀態**：`{result['status']}`")
    md.append("")
    md.append(f"**理由**：{result['reason']}")
    md.append("")

    if result["status"].startswith("fallback"):
        md.append("> ⚠️ **anti-overfit gate 觸發**：建議**維持預設不調整**。")
        md.append("> 本報告僅供觀察 walk-forward 結果，**不建議 merge 套用**。")
        md.append("")

    if result.get("folds"):
        md.append("## 🔍 各折細節（walk-forward）")
        md.append("")
        md.append("| 折 | Train 窗 | Test 窗 | best (C/W) | Train obj | Test obj | Drift |")
        md.append("|----|----------|---------|------------|-----------|----------|-------|")
        for f in result["folds"]:
            md.append(
                f"| {f['fold']} | {f['train_start']}~{f['train_end']} | "
                f"{f['test_start']}~{f['test_end']} | "
                f"{f['best_crisis']}/{f['best_warning']} | "
                f"{f['train_obj']} | **{f['test_obj']}** | {f['drift_pct']}% |"
            )
        md.append("")

    if result.get("votes"):
        md.append("## 🗳️ 折間票選")
        md.append("")
        for k, v in sorted(result["votes"].items(), key=lambda x: -x[1]):
            md.append(f"- `{k}`：{v} 折")
        md.append("")

    if result.get("bootstrap"):
        b = result["bootstrap"]
        md.append("## 📊 Bootstrap 顯著性（rec − default）")
        md.append("")
        md.append(f"- N = {b['n']}")
        md.append(f"- mean Δobj = **{b['mean_diff']}**")
        md.append(f"- 95% CI = [{b['ci_low']}, {b['ci_high']}]")
        md.append("- 採用條件：CI 下界 > 0（rec 顯著優於 default）")
        md.append("")

    if result.get("holdout"):
        h = result["holdout"]
        md.append("## 🔒 Holdout Final Exam（凍結末段）")
        md.append("")
        md.append(f"- N = {h['n_months']} 月")
        md.append(f"- 預設配置 Spearman = **{h['default_corr']}**")
        md.append(f"- 建議配置 Spearman = **{h['rec_corr']}**")
        md.append("")

    md.append("## 🛡️ 5 重 anti-overfit gate")
    md.append("")
    md.append("1. **正則項 + 越界守門**：objective 含 deviation penalty；JSON loader 越界自動回退")
    md.append("2. **Walk-forward 4 折**：每折 train 找最佳、test 報告 OOS，永不在 train 自評")
    md.append("3. **折間票選 + drift 警語**：取多數 cell；過半 drift > 30% 強制回退預設")
    md.append("4. **Bootstrap 1000 次 CI**：訓練池 resample，95% CI 下界 ≤ 0 拒絕")
    md.append("5. **Holdout 末 36 月凍結**：完全不參與校準，最後拿來算 final exam")
    md.append("")
    md.append(f"*產生工具：`scripts/calibrate_macro_score.py`　|　報告時間：{now}*")
    return "\n".join(md)


# ════════════════════════════════════════════════════════════════
# CLI 主流程
# ════════════════════════════════════════════════════════════════
def main():
    p = argparse.ArgumentParser()
    p.add_argument("--years", type=int, default=15,
                   help="score 序列重算年數（預設 15）")
    p.add_argument("--n-folds", type=int, default=4)
    p.add_argument("--holdout-months", type=int, default=36)
    p.add_argument("--n-bootstrap", type=int, default=1000)
    p.add_argument("--horizon-months", type=int, default=3,
                   help="SPX forward return horizon（預設 3 月）")
    p.add_argument("--emit-json", default="data_cache/macro_thresholds_global.json")
    p.add_argument("--emit-proposal", default="MACRO_SCORE_CALIBRATION_PROPOSAL.md")
    args = p.parse_args()

    print("\n📊 calibrate_macro_score.py（D 案修正版 5 重 gate）起跑\n")

    from services.macro_validation import load_indicators_from_parquet
    indicators = load_indicators_from_parquet(CACHE_DIR)
    if not indicators:
        print(f"❌ {CACHE_DIR}/*.parquet 缺/壞，無 indicators 可校準")
        return 1
    print(f"📦 載入 {len(indicators)} 個指標：{list(indicators.keys())}")

    spx = load_spx_from_parquet(CACHE_DIR)
    if spx.empty:
        print(f"❌ {CACHE_DIR}/spx_history.parquet 缺/壞")
        return 1
    print(f"📦 SPX 月線：{len(spx)} 月（{spx.index.min().date()}~{spx.index.max().date()}）")

    cfg = CalibrationConfig(
        n_folds=args.n_folds,
        holdout_months=args.holdout_months,
        n_bootstrap=args.n_bootstrap,
        horizon_months=args.horizon_months,
    )

    print(f"\n🚀 跑 walk-forward {cfg.n_folds} 折 + bootstrap {cfg.n_bootstrap} 次...\n")
    result = walk_forward_calibrate(
        indicators, spx, cfg, years=args.years)

    print(f"\n✅ 完成！狀態：{result['status']}")
    print(f"   建議：crisis={result['recommended'][0]}, warning={result['recommended'][1]}")
    print(f"   理由：{result['reason']}")

    if args.emit_json:
        emit_thresholds_json(result, Path(args.emit_json))
    if args.emit_proposal:
        Path(args.emit_proposal).write_text(
            build_proposal_report(result), encoding="utf-8")
        print(f"[emit-proposal] ✅ 寫入 {args.emit_proposal}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
