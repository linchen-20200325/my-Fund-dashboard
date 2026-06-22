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

from shared.fred_series import (
    FRED_CPI,
    FRED_FED_BS,
    FRED_FED_FUNDS,
    FRED_HY_SPREAD,
    FRED_M2,
    FRED_PAYEMS_MANEMP,
    FRED_PPI,
    FRED_T10Y2Y,
    FRED_T10Y3M,
    FRED_UNRATE,
)


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
                   thresholds: tuple[float, float, float] | None = None
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
                     thresholds: tuple[float, float, float] | None = None
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


# ════════════════════════════════════════════════════════════════
# 真實資料抓取（FRED 14-series + yfinance SPX）
# ════════════════════════════════════════════════════════════════
# FRED series_id 映射；無 FRED 對應的指標走 yfinance 或派生
_FRED_SERIES_MAP = {
    "YIELD_10Y2Y": FRED_T10Y2Y,         # 10Y - 2Y treasury spread
    "YIELD_10Y3M": FRED_T10Y3M,         # 10Y - 3M treasury spread
    "PMI":         FRED_PAYEMS_MANEMP,  # 無 PMI FRED → 用就業代理；真實 PMI 需第三方
    "HY_SPREAD":   FRED_HY_SPREAD,
    "M2":          FRED_M2,             # M2 月底，YoY% 在 calling 端算
    "CPI":         FRED_CPI,            # CPI 月底，YoY% 在 calling 端算
    "FEDRATE":     FRED_FED_FUNDS,      # 月平均
    "UNEMP":       FRED_UNRATE,
    "PPI":         FRED_PPI,            # PPI YoY 在 calling 端算
    "FED_BS":      FRED_FED_BS,         # Fed 資產負債表，YoY% 在 calling 端算
}
_YF_TICKERS = {
    "VIX":     "^VIX",
    "DXY":     "DX-Y.NYB",
    "COPPER":  "HG=F",
    "BREADTH_NUM": "RSP",  # 等權 S&P
    "BREADTH_DEN": "SPY",  # 市值權 S&P
}


def _fred_monthly_yoy(series_df: pd.DataFrame) -> pd.Series:
    """FRED 日 / 月序列 → 月底 YoY%（給 M2 / CPI / FED_BS / PPI 用）。"""
    if series_df is None or series_df.empty:
        return pd.Series(dtype=float)
    s = (series_df.sort_values("date").set_index("date")["value"]
         .astype(float).resample("ME").last())
    return (s / s.shift(12) - 1.0) * 100.0


def _fred_monthly_value(series_df: pd.DataFrame) -> pd.Series:
    """FRED 日 / 月序列 → 月底原值（給 spread / FEDRATE / UNRATE 用）。"""
    if series_df is None or series_df.empty:
        return pd.Series(dtype=float)
    return (series_df.sort_values("date").set_index("date")["value"]
            .astype(float).resample("ME").last())


def _yf_monthly_pct_change(series: pd.Series) -> pd.Series:
    """yfinance 日序列 → 月底收盤的月變化%（給 DXY / COPPER 用）。"""
    if series is None or series.empty:
        return pd.Series(dtype=float)
    m = series.resample("ME").last()
    return (m / m.shift(1) - 1.0) * 100.0


def _yf_monthly_level(series: pd.Series) -> pd.Series:
    """yfinance 日序列 → 月底收盤（給 VIX 用）。"""
    if series is None or series.empty:
        return pd.Series(dtype=float)
    return series.resample("ME").last()


def fetch_real_macro_factors_monthly(
    fred_api_key: str,
    years: int = 10,
) -> tuple[pd.DataFrame, pd.Series, dict]:
    """抓 FRED 14-series + yfinance ^GSPC → 月度 DataFrame + SPX 月底收盤。

    Parameters
    ----------
    fred_api_key : str
        FRED API key（無則回空 DataFrame + 警告 dict）
    years : int
        歷史長度（年），預設 10 年

    Returns
    -------
    (df, spx, notes)
        df: DataFrame index=月底, 14 columns（缺欄留 NaN，計分器會跳過）
        spx: ^GSPC 月底收盤 Series
        notes: dict 含警告 / 失敗來源清單
    """
    notes: dict = {"missing_factors": [], "warnings": []}
    if not fred_api_key:
        notes["warnings"].append("FRED API key 未設置，無法抓真實資料")
        return pd.DataFrame(), pd.Series(dtype=float), notes
    try:
        from repositories.macro_repository import fetch_fred, fetch_yf_close
    except ImportError as e:
        notes["warnings"].append(f"import 失敗：{e}")
        return pd.DataFrame(), pd.Series(dtype=float), notes

    n_obs = years * 12 + 36  # 多抓 3 年讓 YoY 對齊
    series_map: dict[str, pd.Series] = {}

    # ── 1. FRED 8 個 spread / level 指標 ─────────────────────
    for factor, sid in _FRED_SERIES_MAP.items():
        try:
            df_f = fetch_fred(sid, fred_api_key, n=n_obs * 10)
            if df_f is None or df_f.empty:
                notes["missing_factors"].append(f"{factor}({sid})")
                continue
            if factor in ("M2", "CPI", "FED_BS", "PPI"):
                series_map[factor] = _fred_monthly_yoy(df_f)
            elif factor == "PMI":
                # MANEMP 是就業人數，YoY 當 PMI 代理（非完美）
                yoy = _fred_monthly_yoy(df_f)
                series_map[factor] = 50 + yoy * 5  # 粗略映射到 PMI 量級
                notes["warnings"].append("PMI 用就業人數 YoY 代理（FRED 無 PMI）")
            else:
                series_map[factor] = _fred_monthly_value(df_f)
        except Exception as e:
            notes["missing_factors"].append(f"{factor}: {type(e).__name__}")

    # ── 2. yfinance VIX / DXY / Copper ─────────────────────────
    yf_range = f"{years + 3}y" if years <= 10 else "max"
    for factor, ticker in _YF_TICKERS.items():
        if factor in ("BREADTH_NUM", "BREADTH_DEN"):
            continue  # 等下合成 BREADTH
        try:
            s = fetch_yf_close(ticker, range_=yf_range, interval="1d")
            if s is None or s.empty:
                notes["missing_factors"].append(f"{factor}({ticker})")
                continue
            try:
                s.index = s.index.tz_localize(None)
            except (AttributeError, TypeError):
                pass
            if factor == "VIX":
                series_map[factor] = _yf_monthly_level(s)
            else:  # DXY / COPPER → 月變化%
                series_map[factor] = _yf_monthly_pct_change(s)
        except Exception as e:
            notes["missing_factors"].append(f"{factor}: {type(e).__name__}")

    # ── 3. BREADTH = RSP / SPY 月變化% ───────────────────────────
    try:
        rsp = fetch_yf_close(_YF_TICKERS["BREADTH_NUM"], range_=yf_range,
                              interval="1d")
        spy = fetch_yf_close(_YF_TICKERS["BREADTH_DEN"], range_=yf_range,
                              interval="1d")
        if rsp is not None and not rsp.empty and spy is not None and not spy.empty:
            for s in (rsp, spy):
                try: s.index = s.index.tz_localize(None)
                except (AttributeError, TypeError): pass
            ratio = (rsp.resample("ME").last()
                     / spy.resample("ME").last())
            series_map["BREADTH"] = ((ratio / ratio.shift(1) - 1.0) * 100.0)
        else:
            notes["missing_factors"].append("BREADTH(RSP/SPY)")
    except Exception as e:
        notes["missing_factors"].append(f"BREADTH: {type(e).__name__}")

    if not series_map:
        notes["warnings"].append("所有指標抓取失敗")
        return pd.DataFrame(), pd.Series(dtype=float), notes

    # ── 4. 合併為 DataFrame（共同月份，缺欄留 NaN）─────────────
    df = pd.DataFrame(series_map)
    df = df.tail(years * 12)  # 截最後 N 年

    # ── 5. SPX 月底收盤 ───────────────────────────────────────
    try:
        spx_d = fetch_yf_close("^GSPC", range_=yf_range, interval="1d")
        if spx_d is None or spx_d.empty:
            notes["warnings"].append("SPX 抓取失敗")
            return df, pd.Series(dtype=float), notes
        try: spx_d.index = spx_d.index.tz_localize(None)
        except (AttributeError, TypeError): pass
        spx = spx_d.resample("ME").last().tail(years * 12 + 24)
    except Exception as e:
        notes["warnings"].append(f"SPX 異常：{type(e).__name__}: {e}")
        spx = pd.Series(dtype=float)

    return df, spx, notes
