"""services/macro_score_calibration.py — v18.252 AI Macro Score (14-factor) 校準

對 services.macro_service.calc_macro_phase 用的 14-factor 景氣分數做歷史回測：

校準目標
========
逐月套用同一套 14-factor 評分規則 → 回算歷史 Macro_Score → 對應 4 個景氣位階
（高峰/擴張/復甦/衰退），驗證每個位階的「建議行動」對未來 SPX 是否真的對得上。

真值定義（per 位階）
====================
- 高峰 (8-10)：應減碼 → 真值命中 = 後 horizon 月 SPX 跌（fwd_ret < 0）
- 擴張 (5-7) ：應持有 → 真值命中 = 後 horizon 月 SPX 漲（fwd_ret > 0）
- 復甦 (3-4) ：應加碼 → 真值命中 = 後 horizon 月 SPX 大漲（fwd_ret > +10%）
- 衰退 (0-2) ：應防禦 → 真值命中 = 後 horizon 月 SPX 跌或橫盤（fwd_ret < 0）

對外 API
========
- `compute_historical_score(df)` — 逐月套 14-factor → 月度 Macro_Score
- `classify_phase(score)`        — 0~10 → "Peak/Expansion/Recovery/Recession"
- `phase_accuracy(score, spx)`   — 每位階 hit_rate + 平均後 horizon 月報酬
- `grid_search_phase_thresholds` — 掃 phase 門檻組合，找最高總命中率
- `generate_synthetic_demo()`    — 60 月合成 + 2 段壓力事件，sandbox 用

純函式，沒 I/O；要餵真實資料的 caller 自己抓 FRED + yfinance。
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd


# ════════════════════════════════════════════════════════════════
# 14-factor 評分規則（與 services/macro_service.py:fetch_all_indicators 同邏輯）
# ════════════════════════════════════════════════════════════════
def _s_yield_10y2y(v):    return 2 if v > 0.5 else (-2 if v < 0 else 0)
def _s_yield_10y3m(v):    return 2 if v > 0.5 else (-2 if v < 0 else 0)
def _s_pmi(v):            return 2 if v >= 50 else (-2 if v < 45 else -1)
def _s_hy_spread(v):      return 2 if v < 4 else (-2 if v > 6 else 0)
def _s_m2(v):             return 1 if v > 5 else (-1 if v < 0 else 0)
def _s_breadth(chg):      return 1 if chg > 0.5 else (-1 if chg < -1 else 0)
def _s_dxy(chg_m):        return 1 if chg_m < -1 else (-1 if chg_m > 2 else 0)
def _s_fed_bs(v):         return 1 if v > 5 else (-1 if v < -5 else 0)
def _s_vix(v):            return 1 if v < 18 else (-1 if v > 30 else 0)
def _s_cpi(v):            return 1 if 1 < v < 2.5 else (-1 if v > 4 else 0)
def _s_fedrate(v, p):     return 0.5 if v < p else (-0.5 if v > 5 else 0)
def _s_unemp(v):          return 0.5 if v < 4.5 else (-1 if v > 6 else 0)
def _s_ppi(v):            return 0.5 if 0 < v < 3 else (-0.5 if v > 5 else 0)
def _s_copper(chg):       return 0.5 if chg > 2 else (-0.5 if chg < -5 else 0)


# (name, weight, scorer, takes_extra_prev)
FACTORS: list[tuple[str, float, Callable, bool]] = [
    ("YIELD_10Y2Y", 2.0,  _s_yield_10y2y, False),
    ("YIELD_10Y3M", 2.0,  _s_yield_10y3m, False),
    ("PMI",          2.0, _s_pmi,         False),
    ("HY_SPREAD",    2.0, _s_hy_spread,   False),
    ("M2",           1.0, _s_m2,          False),
    ("BREADTH",      1.0, _s_breadth,     False),  # 餵 RSP/SPY 月變化
    ("DXY",          1.0, _s_dxy,         False),  # 餵月變化（%）
    ("FED_BS",       1.0, _s_fed_bs,      False),  # 餵 YoY%
    ("VIX",          1.0, _s_vix,         False),
    ("CPI",          1.0, _s_cpi,         False),
    ("FEDRATE",      0.5, _s_fedrate,     True),   # 需要 prev
    ("UNEMP",        0.5, _s_unemp,       False),
    ("PPI",          0.5, _s_ppi,         False),
    ("COPPER",       0.5, _s_copper,      False),  # 餵月變化（%）
]
TOTAL_WEIGHT = sum(w for _, w, _, _ in FACTORS)   # = 14.5


# ════════════════════════════════════════════════════════════════
# Score 計算
# ════════════════════════════════════════════════════════════════
def compute_score_row(row: dict | pd.Series, prev: dict | None = None) -> float:
    """逐月用 14-factor → Macro_Score 0~10。

    Parameters
    ----------
    row : dict / pd.Series
        當月 14 factor value（key 對齊 FACTORS）
    prev : dict / None
        上月 row（FEDRATE 需上月才能判斷「降息」）；None 則 FEDRATE 得 0
    """
    earned = 0.0
    for name, w, scorer, takes_prev in FACTORS:
        v = row.get(name) if hasattr(row, "get") else (
            row[name] if name in row.index else None)
        if v is None or (isinstance(v, float) and np.isnan(v)):
            continue
        try:
            if takes_prev:
                p = prev.get(name) if prev else None
                if p is None or (isinstance(p, float) and np.isnan(p)):
                    continue
                s = scorer(float(v), float(p))
            else:
                s = scorer(float(v))
            # clamp to ±w
            s = max(-w, min(w, s))
            earned += s
        except (ValueError, TypeError):
            continue
    norm = (earned + TOTAL_WEIGHT) / (2 * TOTAL_WEIGHT) * 10
    return float(max(0.0, min(10.0, norm)))


def compute_historical_score(df: pd.DataFrame) -> pd.Series:
    """每月一行的 DataFrame → Macro_Score 時序。

    df.index 必須是 monthly DatetimeIndex；columns 為 FACTORS 名稱（缺欄該因子算 0）。
    """
    out = []
    prev_row = None
    for _, row in df.iterrows():
        out.append(compute_score_row(row, prev_row))
        prev_row = row
    return pd.Series(out, index=df.index, name="Macro_Score")


# ════════════════════════════════════════════════════════════════
# Phase 映射 + 真值定義
# ════════════════════════════════════════════════════════════════
PHASE_THRESHOLDS_DEFAULT = (8.0, 5.0, 3.0)  # peak / expansion / recovery 下界


def classify_phase(score: float,
                   thresholds: tuple[float, float, float] = PHASE_THRESHOLDS_DEFAULT
                   ) -> str:
    """0~10 → Peak / Expansion / Recovery / Recession。"""
    p, e, r = thresholds
    if score >= p:
        return "Peak"
    if score >= e:
        return "Expansion"
    if score >= r:
        return "Recovery"
    return "Recession"


# 真值規則：每位階 lambda fwd_ret → 是否命中
_TRUTH_RULES: dict[str, Callable[[float], bool]] = {
    "Peak":      lambda r: r < 0.0,        # 應減碼 → 真跌
    "Expansion": lambda r: r > 0.0,        # 應持有 → 真漲
    "Recovery":  lambda r: r > 0.10,       # 應加碼 → 真大漲
    "Recession": lambda r: r < 0.0,        # 應防禦 → 真跌
}


def forward_return(spx: pd.Series, horizon_months: int = 12) -> pd.Series:
    """t 月底買 SPX，t+horizon 月底賣的累計報酬。"""
    return spx.shift(-horizon_months) / spx - 1.0


def phase_accuracy(score: pd.Series,
                   spx: pd.Series,
                   horizon_months: int = 12,
                   thresholds: tuple[float, float, float] = PHASE_THRESHOLDS_DEFAULT
                   ) -> pd.DataFrame:
    """每位階：n 個樣本、hit 個命中、命中率、平均/中位數後 horizon 月 SPX 報酬。"""
    fwd = forward_return(spx, horizon_months)
    phases = score.apply(lambda s: classify_phase(s, thresholds))
    df = pd.DataFrame({"score": score, "phase": phases, "fwd_ret": fwd}).dropna()
    rows = []
    for phase, rule in _TRUTH_RULES.items():
        sub = df[df["phase"] == phase]
        n = len(sub)
        if n == 0:
            rows.append({"phase": phase, "n": 0, "hit": 0, "hit_rate_pct": None,
                         "mean_fwd_pct": None, "median_fwd_pct": None})
            continue
        hit = int(sub["fwd_ret"].apply(rule).sum())
        rows.append({
            "phase": phase, "n": n, "hit": hit,
            "hit_rate_pct": round(hit / n * 100, 1),
            "mean_fwd_pct": round(float(sub["fwd_ret"].mean()) * 100, 1),
            "median_fwd_pct": round(float(sub["fwd_ret"].median()) * 100, 1),
        })
    return pd.DataFrame(rows)


def overall_accuracy(score: pd.Series,
                     spx: pd.Series,
                     horizon_months: int = 12,
                     thresholds: tuple[float, float, float] = PHASE_THRESHOLDS_DEFAULT
                     ) -> float:
    """加權平均命中率（按樣本數）。"""
    df = phase_accuracy(score, spx, horizon_months, thresholds)
    df = df.dropna(subset=["hit_rate_pct"])
    if df.empty:
        return 0.0
    total_n = df["n"].sum()
    if total_n == 0:
        return 0.0
    return float((df["hit"].sum() / total_n) * 100.0)


def grid_search_phase_thresholds(score: pd.Series,
                                 spx: pd.Series,
                                 horizon_months: int = 12,
                                 peak_grid: tuple = (7.0, 7.5, 8.0, 8.5),
                                 exp_grid: tuple = (4.0, 4.5, 5.0, 5.5),
                                 rec_grid: tuple = (2.0, 2.5, 3.0, 3.5),
                                 ) -> pd.DataFrame:
    """掃描 phase 門檻組合 → 各組合總命中率，按 overall_acc 排序。"""
    out = []
    for p in peak_grid:
        for e in exp_grid:
            for r in rec_grid:
                if not (p > e > r):
                    continue
                acc = overall_accuracy(score, spx, horizon_months, (p, e, r))
                out.append({"peak_thr": p, "expansion_thr": e,
                            "recovery_thr": r, "overall_acc_pct": round(acc, 1)})
    if not out:
        return pd.DataFrame(columns=["peak_thr", "expansion_thr", "recovery_thr",
                                      "overall_acc_pct"])
    return pd.DataFrame(out).sort_values("overall_acc_pct", ascending=False
                                          ).reset_index(drop=True)


# ════════════════════════════════════════════════════════════════
# 合成資料（sandbox demo / 測試用）
# ════════════════════════════════════════════════════════════════
def generate_synthetic_demo(n_months: int = 60, seed: int = 42
                            ) -> tuple[pd.DataFrame, pd.Series]:
    """產 14-factor 月序列 + SPX 月序列，內嵌 2 段壓力事件供 demo。

    Returns
    -------
    (df_factors, spx_series)
        df_factors: DataFrame, index=monthly, 14 columns
        spx_series: SPX 月底收盤，同 index
    """
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2020-01-31", periods=n_months, freq="ME")
    # 基準正常期：擴張到復甦間漂移
    rows = []
    for i in range(n_months):
        rows.append({
            "YIELD_10Y2Y": float(rng.normal(0.6, 0.3)),
            "YIELD_10Y3M": float(rng.normal(0.8, 0.3)),
            "PMI":         float(rng.normal(51, 3)),
            "HY_SPREAD":   float(rng.normal(4.0, 0.6)),
            "M2":          float(rng.normal(5, 2)),
            "BREADTH":     float(rng.normal(0.3, 0.6)),
            "DXY":         float(rng.normal(0.0, 1.0)),
            "FED_BS":      float(rng.normal(3.0, 2.0)),
            "VIX":         float(rng.normal(18, 4)),
            "CPI":         float(rng.normal(2.5, 0.8)),
            "FEDRATE":     float(rng.normal(3.0, 1.0)),
            "UNEMP":       float(rng.normal(4.0, 0.5)),
            "PPI":         float(rng.normal(2.5, 1.5)),
            "COPPER":      float(rng.normal(0.5, 3.0)),
        })
    # 壓力事件 1：第 15-22 月（高峰→衰退）
    for i in range(15, 23):
        if i >= n_months: break
        rows[i].update({
            "YIELD_10Y2Y": -0.3, "YIELD_10Y3M": -0.4,
            "PMI": 44, "HY_SPREAD": 7.5, "VIX": 35,
            "M2": -1.0, "FED_BS": -8.0, "CPI": 5.5,
        })
    # 壓力事件 2：第 42-48 月（衰退→復甦）
    for i in range(42, 49):
        if i >= n_months: break
        rows[i].update({
            "YIELD_10Y2Y": -0.5, "PMI": 42, "VIX": 38,
            "HY_SPREAD": 8.0, "UNEMP": 6.5,
        })
    df = pd.DataFrame(rows, index=dates)

    # SPX：跟 Macro_Score 弱相關（讓校準有訊號）
    score = compute_historical_score(df)
    # SPX 月報酬 = base drift + score 偏離 5 (中性) 的線性效應 + noise
    base_drift = 0.005
    score_effect = (score - 5.0) * 0.012  # 1 分價值 1.2%
    noise = rng.normal(0, 0.025, n_months)
    monthly_rets = base_drift + score_effect.values + noise
    # 壓力事件強制負報酬
    for i in range(15, 23):
        if i < n_months: monthly_rets[i] = rng.normal(-0.04, 0.02)
    for i in range(42, 49):
        if i < n_months: monthly_rets[i] = rng.normal(-0.03, 0.02)
    spx = pd.Series(4500.0 * np.exp(np.cumsum(monthly_rets)),
                    index=dates, name="SPX")
    return df, spx
