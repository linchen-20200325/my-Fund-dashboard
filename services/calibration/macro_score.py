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
- ~~`phase_accuracy(score, spx)`~~  v19.217 P0-3-#8 拔毒(production 0 caller)
- ~~`grid_search_phase_thresholds`~~ v19.217 P0-3-#8 拔毒
- `generate_synthetic_demo()`    — 60 月合成 + 2 段壓力事件，sandbox 用

純函式，沒 I/O；要餵真實資料的 caller 自己抓 FRED + yfinance。
"""
from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

# v19.217 P0-3-#8:shared.fred_series 整 import 區隨 fetch_real_macro_factors_monthly 拔毒移除
from shared.macro_thresholds_v2 import (  # F-GRAY-4 v19.169 + v19.179 PMI + v19.184 M2/FedBS
    HY_SPREAD_THRESHOLDS as _HY_THR,
    PMI_THRESHOLDS as _PMI_THR,
    M2_THRESHOLDS as _M2_THR,
    FED_BS_THRESHOLDS as _FEDBS_THR,
)

# F-GRAY-4 v19.169: HY_SPREAD score_function SSOT (SPEC §16.2)
_HY_TIGHT = _HY_THR["score_function"]["tight_below"]
_HY_WIDE = _HY_THR["score_function"]["wide_above"]

# F-GRAY-4 v19.179: PMI score_function SSOT (SPEC §16.2)
_PMI_EXPANSION = _PMI_THR["score_function"]["expansion_above"]  # 50.0
_PMI_RECESSION = _PMI_THR["score_function"]["recession_below"]  # 45.0

# F-GRAY-4 v19.184: M2 / Fed BS score_function SSOT (SPEC §16.2)
_M2_EASING = _M2_THR["score_function"]["easing_above"]            # 5.0
_M2_TIGHTENING = _M2_THR["score_function"]["tightening_below"]    # 0.0
_FEDBS_EXPANSION = _FEDBS_THR["score_function"]["expansion_above"]    # 5.0
_FEDBS_CONTRACTION = _FEDBS_THR["score_function"]["contraction_below"]  # -5.0


# ════════════════════════════════════════════════════════════════
# 14-factor 評分規則（與 services/macro_service.py:fetch_all_indicators 同邏輯）
# ════════════════════════════════════════════════════════════════
def _s_yield_10y2y(v):    return 2 if v > 0.5 else (-2 if v < 0 else 0)
def _s_yield_10y3m(v):    return 2 if v > 0.5 else (-2 if v < 0 else 0)
def _s_pmi(v):            return 2 if v >= _PMI_EXPANSION else (-2 if v < _PMI_RECESSION else -1)
def _s_hy_spread(v):      return 2 if v < _HY_TIGHT else (-2 if v > _HY_WIDE else 0)
def _s_m2(v):             return 1 if v > _M2_EASING else (-1 if v < _M2_TIGHTENING else 0)
def _s_breadth(chg):      return 1 if chg > 0.5 else (-1 if chg < -1 else 0)
def _s_dxy(chg_m):        return 1 if chg_m < -1 else (-1 if chg_m > 2 else 0)
def _s_fed_bs(v):         return 1 if v > _FEDBS_EXPANSION else (-1 if v < _FEDBS_CONTRACTION else 0)
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

    v19.1 (C-2)：每個 factor 的 weight 改走 ``get_weight_override(name, w)``；
    active.json 有就蓋、沒有就用 FACTORS 表硬編碼；total_weight 用即時 sum 重算。
    """
    try:
        from services.macro_weights_store import get_weight_override
    except ImportError:
        get_weight_override = None  # type: ignore[assignment]

    earned = 0.0
    total_w = 0.0
    for name, w_default, scorer, takes_prev in FACTORS:
        w = (get_weight_override(name, float(w_default))
             if get_weight_override else float(w_default))
        total_w += w
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
            # clamp to ±w（依當前生效權重，不是 FACTORS 表 default）
            s = max(-w, min(w, s))
            earned += s
        except (ValueError, TypeError):
            continue
    if total_w <= 0:
        return 0.0
    norm = (earned + total_w) / (2 * total_w) * 10
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


def _resolve_phase_thresholds(
    thresholds: tuple[float, float, float] | None,
) -> tuple[float, float, float]:
    """C-2：thresholds=None 時走 active.json，否則照舊用 caller 傳入值。

    Active.json 缺欄 / null / corrupt → 回退 ``PHASE_THRESHOLDS_DEFAULT``，
    讓既有 caller 不傳 thresholds 也能拿到跟 v18.x 一樣的 (8, 5, 3)。
    """
    if thresholds is not None:
        return thresholds
    try:
        from services.macro_weights_store import get_phase_thresholds
        return get_phase_thresholds(PHASE_THRESHOLDS_DEFAULT)
    except ImportError:
        return PHASE_THRESHOLDS_DEFAULT


def classify_phase(score: float,
                   thresholds: tuple[float, float, float] | None = None,
                   ) -> str:
    """0~10 → Peak / Expansion / Recovery / Recession。

    v19.1 (C-2)：``thresholds=None`` 時自動從 active.json 載入；
    傳入 tuple 則維持原行為（測試用 / overlay 用）。
    """
    p, e, r = _resolve_phase_thresholds(thresholds)
    if score >= p:
        return "Peak"
    if score >= e:
        return "Expansion"
    if score >= r:
        return "Recovery"
    return "Recession"



def forward_return(spx: pd.Series, horizon_months: int = 12) -> pd.Series:
    """t 月底買 SPX，t+horizon 月底賣的累計報酬。"""
    return spx.shift(-horizon_months) / spx - 1.0


# v19.217 P0-3-#8:phase_accuracy / overall_accuracy / grid_search_phase_thresholds
# 三 fn 拔毒(production 0 caller,只 test 孤兒)


# ════════════════════════════════════════════════════════════════
# 合成資料（sandbox demo / 測試用）
# ════════════════════════════════════════════════════════════════
def generate_synthetic_demo(n_months: int = 60, seed: int = 42
                            ) -> tuple[pd.DataFrame, pd.Series]:
    """產 14-factor 月序列 + SPX 月序列，內嵌 4 段壓力 / 反彈事件供 demo。

    v18.252 起調整：base_drift 0.005→0.003、σ 0.025→0.040，壓力事件
    擴為 3 段下殺 + 1 段強反彈，逼近真實 SPX 月報酬分佈以提升校準
    命中率（消除「合成資料只漲不跌」造成 Peak/Recession 永遠錯的假象）。

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
    # 壓力事件 1：第 12-18 月（高峰→衰退，6M）
    for i in range(12, 18):
        if i >= n_months: break
        rows[i].update({
            "YIELD_10Y2Y": -0.3, "YIELD_10Y3M": -0.4,
            "PMI": 44, "HY_SPREAD": 7.5, "VIX": 35,
            "M2": -1.0, "FED_BS": -8.0, "CPI": 5.5,
        })
    # 反彈段：第 18-22 月（復甦，FED 注入流動性 + PMI 反彈）
    for i in range(18, 22):
        if i >= n_months: break
        rows[i].update({
            "PMI": 53, "HY_SPREAD": 3.8, "VIX": 16,
            "M2": 8.0, "FED_BS": 12.0, "BREADTH": 1.5,
        })
    # 壓力事件 2：第 35-42 月（中段修正）
    for i in range(35, 42):
        if i >= n_months: break
        rows[i].update({
            "YIELD_10Y2Y": -0.5, "PMI": 42, "VIX": 38,
            "HY_SPREAD": 8.0, "UNEMP": 6.5,
            "CPI": 6.0, "M2": -2.0,
        })
    # 壓力事件 3：第 50-55 月（後期震盪）
    for i in range(50, 55):
        if i >= n_months: break
        rows[i].update({
            "PMI": 46, "VIX": 28, "HY_SPREAD": 6.5,
            "DXY": 3.5, "BREADTH": -1.5,
        })
    df = pd.DataFrame(rows, index=dates)

    # SPX：跟 Macro_Score 有訊號 + 加大噪音；關鍵是「score 先動、SPX 後動」（lead 3M）
    # 真實 SPX 月報酬約 N(0.6%, 4.5%)，年化 ~7%, σ ~15%
    # 領先機制：score 在 t 月觸發 → 影響 t+3 月起的 SPX 報酬
    score = compute_historical_score(df)
    base_drift = 0.003                        # 月 0.3% = 年 ~3.7%（保守）
    noise = rng.normal(0, 0.040, n_months)    # σ=4% 接近真實
    # score lead SPX by 3 months：用 shift(3) 把 score 影響推到未來
    score_lead = pd.Series(score.values, index=score.index).shift(3).fillna(5.0)
    score_effect = (score_lead.values - 5.0) * 0.012
    monthly_rets = base_drift + score_effect + noise
    # 壓力事件對 SPX 的衝擊延後 3 個月（讓 score 真的「領先」SPX 跌）
    for i in range(15, 21):    # score 12-18 → SPX 15-21
        if i < n_months: monthly_rets[i] = rng.normal(-0.05, 0.025)
    for i in range(38, 45):    # score 35-42 → SPX 38-45
        if i < n_months: monthly_rets[i] = rng.normal(-0.04, 0.025)
    for i in range(53, 58):    # score 50-55 → SPX 53-58
        if i < n_months: monthly_rets[i] = rng.normal(-0.03, 0.020)
    spx = pd.Series(4500.0 * np.exp(np.cumsum(monthly_rets)),
                    index=dates, name="SPX")
    return df, spx
