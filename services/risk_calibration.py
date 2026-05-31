"""services/risk_calibration.py — v18.253 風險評分真值校準

提供「composite_risk score」對歷史「forward SPX drawdown 標籤」的校準工具：
- label_forward_drawdown: SPX 月序列 → t+1..t+H 期間最大跌幅 < threshold ⇒ 1
- compute_calibration: score + label + 門檻 → confusion matrix / precision / recall / F1
- grid_search_threshold: 掃描門檻 → 各門檻 metrics 表（依 F1 排序）
- rolling_risk_score: 對 (VIX, HY_Spread, Yield_Curve_10Y_2Y) 跑滑動 Z-score → 時序 risk_score
- generate_synthetic_demo: 60 月合成資料（內嵌 2 段壓力事件）給 sandbox demo / 測試用
- fetch_real_3factor_monthly: 真實 FRED + yfinance 抓 3-factor + SPX 月度（v18.253）

Ground truth 預設：未來 3 個月 SPX 最大回檔 < -10% ⇒ 高風險命中。
此模組純函式，沒有 I/O；要餵真實資料的 caller 自己抓 FRED + yfinance。
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

_MACRO_COLS = ("VIX", "HY_Spread", "Yield_Curve_10Y_2Y")
_WEIGHTS = {"VIX": 0.3, "HY_Spread": 0.4, "Yield_Curve_10Y_2Y": 0.3}


@dataclass(frozen=True)
class CalibrationResult:
    threshold: float
    precision: float
    recall: float
    f1: float
    accuracy: float
    tp: int
    fp: int
    tn: int
    fn: int

    @property
    def confusion_matrix(self) -> pd.DataFrame:
        return pd.DataFrame(
            [[self.tn, self.fp], [self.fn, self.tp]],
            index=["實際:正常", "實際:危機"],
            columns=["預測:正常", "預測:危機"],
        )


def label_forward_drawdown(
    spx: pd.Series,
    horizon_months: int = 3,
    threshold: float = -0.10,
) -> pd.Series:
    """SPX 月序列 → 對每個月 t 評估 t+1..t+horizon 期間相對 t 的最大跌幅。

    跌幅 < threshold ⇒ 1（命中），否則 0；最後 horizon 個月 forward window 不足 ⇒ NaN。
    """
    spx = spx.copy().sort_index()
    n = len(spx)
    out = pd.Series(np.nan, index=spx.index, dtype=float)
    for i in range(n - horizon_months):
        window = spx.iloc[i + 1 : i + 1 + horizon_months]
        if window.empty:
            continue
        max_dd = (window.min() / spx.iloc[i]) - 1.0
        out.iloc[i] = 1.0 if max_dd < threshold else 0.0
    return out


def compute_calibration(
    risk_score: pd.Series,
    label: pd.Series,
    threshold: float,
) -> CalibrationResult:
    """給定 score / label / 門檻 → confusion matrix + metrics。score ≥ threshold ⇒ 預測 1。"""
    df = pd.concat(
        [risk_score.rename("score"), label.rename("label")], axis=1
    ).dropna()
    if df.empty:
        return CalibrationResult(float(threshold), 0.0, 0.0, 0.0, 0.0, 0, 0, 0, 0)
    pred = (df["score"] >= threshold).astype(int)
    actual = df["label"].astype(int)
    tp = int(((pred == 1) & (actual == 1)).sum())
    fp = int(((pred == 1) & (actual == 0)).sum())
    tn = int(((pred == 0) & (actual == 0)).sum())
    fn = int(((pred == 0) & (actual == 1)).sum())
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall) > 0
        else 0.0
    )
    total = tp + fp + tn + fn
    accuracy = (tp + tn) / total if total > 0 else 0.0
    return CalibrationResult(
        float(threshold), precision, recall, f1, accuracy, tp, fp, tn, fn
    )


def grid_search_threshold(
    risk_score: pd.Series,
    label: pd.Series,
    grid: np.ndarray | None = None,
) -> pd.DataFrame:
    """掃描門檻 → 回傳每門檻 metrics 表（依 F1 由大到小排序）。"""
    if grid is None:
        grid = np.round(np.arange(-1.0, 3.1, 0.1), 2)
    rows = []
    for t in grid:
        r = compute_calibration(risk_score, label, float(t))
        rows.append(
            {
                "threshold": r.threshold,
                "precision": r.precision,
                "recall": r.recall,
                "f1": r.f1,
                "accuracy": r.accuracy,
                "tp": r.tp,
                "fp": r.fp,
                "tn": r.tn,
                "fn": r.fn,
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["f1", "threshold"], ascending=[False, True])
        .reset_index(drop=True)
    )


def rolling_risk_score(
    df_macro: pd.DataFrame,
    window: int = 24,
) -> pd.Series:
    """對 df_macro 跑滑動視窗 Z-score → 時序 risk_score（與 PSE.calculate_composite_risk 同公式）。

    對每個 t 用 [t-window, t-1] 計算 mean/std；前 window 期回 NaN。
    """
    if df_macro is None or df_macro.empty:
        return pd.Series([], dtype=float)
    out = pd.Series(np.nan, index=df_macro.index, dtype=float)
    cols = [c for c in _MACRO_COLS if c in df_macro.columns]
    if len(cols) < 3:
        return out
    for i in range(window, len(df_macro)):
        hist = df_macro[cols].iloc[i - window : i]
        means = hist.mean()
        stds = hist.std().replace(0, np.nan)
        latest = df_macro[cols].iloc[i]
        z = ((latest - means) / stds).dropna()
        if len(z) < 3:
            continue
        out.iloc[i] = float(sum(_WEIGHTS[c] * z[c] for c in cols if c in z.index))
    return out


def generate_synthetic_demo(
    n_months: int = 60,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series]:
    """合成 60 月 macro + SPX（內嵌 2 段壓力事件）給 sandbox demo 用。

    壓力事件位置：t=12-15、t=40-43，VIX/HY 跳升、SPX 下跌 ~20%。
    """
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2020-01-01", periods=n_months, freq="MS")
    vix = 17 + rng.normal(0, 2.5, n_months).cumsum() * 0.2
    hy = 3.8 + rng.normal(0, 0.25, n_months).cumsum() * 0.04
    yc = 0.6 + rng.normal(0, 0.18, n_months).cumsum() * 0.04
    spx_ret = rng.normal(0.006, 0.035, n_months)
    spx = 100 * np.exp(np.cumsum(spx_ret))

    for start in (12, 40):
        if start + 6 >= n_months:
            continue
        for k in range(4):
            vix[start + k] += 22 + k * 6
            hy[start + k] += 2.2 + k * 0.6
            yc[start + k] -= 0.5
            spx[start + k] *= 0.93 - 0.025 * k
        for k in range(4, 9):
            if start + k < n_months:
                vix[start + k] = max(15.0, vix[start + k] - 6)
                hy[start + k] = max(3.5, hy[start + k] - 0.5)

    df_macro = pd.DataFrame(
        {
            "VIX": np.clip(vix, 9.0, 85.0),
            "HY_Spread": np.clip(hy, 2.5, 14.0),
            "Yield_Curve_10Y_2Y": np.clip(yc, -1.8, 2.8),
        },
        index=idx,
    )
    spx_series = pd.Series(spx, index=idx, name="SPX")
    return df_macro, spx_series


# ════════════════════════════════════════════════════════════════
# 真實資料抓取（FRED + yfinance）v18.253
# ════════════════════════════════════════════════════════════════
def fetch_real_3factor_monthly(
    fred_api_key: str,
    years: int = 10,
) -> tuple[pd.DataFrame, pd.Series, dict]:
    """抓 3-factor (VIX/HY_Spread/Yield_Curve_10Y_2Y) + SPX 月度真實資料。

    Parameters
    ----------
    fred_api_key : str
        FRED API key（無則回空 + notes 警告）
    years : int
        歷史長度（年），預設 10 年

    Returns
    -------
    (df_macro, spx, notes)
        df_macro: DataFrame index=月底, 3 columns (VIX/HY_Spread/Yield_Curve_10Y_2Y)
        spx: ^GSPC 月底收盤 Series
        notes: dict 含 missing_factors / warnings 清單
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

    n_obs = years * 12 + 24
    series_map: dict[str, pd.Series] = {}

    # ── FRED：HY_Spread (BAMLH0A0HYM2) + Yield_Curve_10Y_2Y (T10Y2Y) ──
    _fred_map = {"HY_Spread": "BAMLH0A0HYM2", "Yield_Curve_10Y_2Y": "T10Y2Y"}
    for col, sid in _fred_map.items():
        try:
            df_f = fetch_fred(sid, fred_api_key, n=n_obs * 10)
            if df_f is None or df_f.empty:
                notes["missing_factors"].append(f"{col}({sid})")
                continue
            series_map[col] = (df_f.sort_values("date").set_index("date")["value"]
                               .astype(float).resample("ME").last())
        except Exception as e:
            notes["missing_factors"].append(f"{col}: {type(e).__name__}")

    # ── yfinance：VIX 月底收盤 ────────────────────────────────────
    yf_range = f"{years + 2}y" if years <= 10 else "max"
    try:
        s = fetch_yf_close("^VIX", range_=yf_range, interval="1d")
        if s is None or s.empty:
            notes["missing_factors"].append("VIX(^VIX)")
        else:
            try: s.index = s.index.tz_localize(None)
            except (AttributeError, TypeError): pass
            series_map["VIX"] = s.resample("ME").last()
    except Exception as e:
        notes["missing_factors"].append(f"VIX: {type(e).__name__}")

    if not series_map:
        notes["warnings"].append("所有指標抓取失敗")
        return pd.DataFrame(), pd.Series(dtype=float), notes

    df_macro = pd.DataFrame(series_map).tail(years * 12)

    # ── SPX 月底收盤 ─────────────────────────────────────────────
    try:
        spx_d = fetch_yf_close("^GSPC", range_=yf_range, interval="1d")
        if spx_d is None or spx_d.empty:
            notes["warnings"].append("SPX 抓取失敗")
            return df_macro, pd.Series(dtype=float), notes
        try: spx_d.index = spx_d.index.tz_localize(None)
        except (AttributeError, TypeError): pass
        spx = spx_d.resample("ME").last().tail(years * 12 + 12)
    except Exception as e:
        notes["warnings"].append(f"SPX 異常：{type(e).__name__}: {e}")
        spx = pd.Series(dtype=float)

    return df_macro, spx, notes
