"""cross_source_compare.py — Phase E 全球 macro_score × 台股 TWII 對照引擎.

User 需求（Phase E）：把 fund repo 的「全球 FRED 合成 0-10 macro_score」與台股
TWII 走勢同框比對，看全球景氣弱化是否領先 TWII 崩盤 → 找最佳 lead-lag 月數。

設計：
- 純函式，零 I/O（除了讀 Parquet）+ 零 streamlit 相依
- 上游：services/macro_validation.calc_macro_score_series（已存在）→ 月度 0-10 score
- 上游：data_cache/twii_history.parquet（PR Phase E 新增 cron 抓 ^TWII 日線）
- 下游：ui/tab_crisis_backtest._render_phase_e_cross_source_section

API
===
- load_twii_from_parquet(cache_dir) → pd.Series  # 日線收盤
- align_score_with_twii(score_df, twii_series, freq='ME') → pd.DataFrame
- compute_lead_lag_correlation(aligned_df, max_lag_months=12) → pd.DataFrame
- summarize_crisis_score_around_events(events, score_series, lookback_months=6)
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

DEFAULT_PARQUET_CACHE_DIR = Path("data_cache")


def load_twii_from_parquet(
    cache_dir: Path = DEFAULT_PARQUET_CACHE_DIR,
) -> pd.Series:
    """讀 `data_cache/twii_history.parquet` → 日線 close Series（DatetimeIndex）.

    缺檔 / 壞檔 / 空檔 → 回空 Series（不 raise）。
    """
    path = cache_dir / "twii_history.parquet"
    if not path.exists():
        return pd.Series(dtype=float, name="twii_close")
    try:
        df = pd.read_parquet(path)
    except Exception as e:  # noqa: BLE001
        print(f"[cross_source/load_twii] read failed: {e}")
        return pd.Series(dtype=float, name="twii_close")
    if df.empty or not {"date", "close"}.issubset(df.columns):
        return pd.Series(dtype=float, name="twii_close")
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    s = df.set_index("date")["close"].sort_index().dropna()
    s.name = "twii_close"
    return s


def align_score_with_twii(
    score_df: pd.DataFrame,
    twii_series: pd.Series,
    freq: str = "ME",
) -> pd.DataFrame:
    """把月度 macro_score 與 TWII 對齊到同頻 → DataFrame[score, twii_close, twii_mom_pct].

    Args:
        score_df: services.macro_validation.calc_macro_score_series 的輸出
                  （DatetimeIndex + columns 含 'score'）
        twii_series: load_twii_from_parquet 的輸出（DatetimeIndex 日線）
        freq: 對齊頻率（預設 ME 月末；W = 週末）

    Returns:
        DataFrame indexed by date with columns:
        - score: 月末 macro_score（0-10）
        - twii_close: 該月末 TWII 收盤（forward-fill 取≤該月底最後已知值）
        - twii_mom_pct: TWII 月變化率（pct）—— 第一列為 NaN
    """
    if score_df is None or score_df.empty:
        return pd.DataFrame(columns=["score", "twii_close", "twii_mom_pct"])
    if twii_series is None or twii_series.empty:
        return pd.DataFrame(columns=["score", "twii_close", "twii_mom_pct"])

    # 確保 DatetimeIndex
    score = score_df["score"].copy()
    if not isinstance(score.index, pd.DatetimeIndex):
        score.index = pd.to_datetime(score.index)
    twii = twii_series.copy()
    if not isinstance(twii.index, pd.DatetimeIndex):
        twii.index = pd.to_datetime(twii.index)

    # score 通常已是月末；twii 是日線 → resample 月末取 last
    twii_m = twii.resample(freq).last()

    # 共同 index：取兩者的 union 再 ffill twii（score 不 ffill 因為已是月末打分）
    aligned = pd.DataFrame({"score": score})
    aligned = aligned.join(twii_m.rename("twii_close"), how="inner")
    aligned["twii_mom_pct"] = aligned["twii_close"].pct_change() * 100.0
    return aligned.dropna(subset=["score", "twii_close"])


def compute_lead_lag_correlation(
    aligned_df: pd.DataFrame,
    max_lag_months: int = 12,
) -> pd.DataFrame:
    """計算 macro_score 領先 TWII 月變化率的 cross-correlation.

    公式：lag = k → corr( score.shift(k), twii_mom_pct ) for k ∈ [-max, +max]
    正 k = score 領先 twii_mom_pct 即「macro_score 高峰先於 TWII 起漲」
    負 k = score 落後 twii_mom_pct

    Args:
        aligned_df: align_score_with_twii 的輸出
        max_lag_months: 最大 lag 視窗（預設 ±12 月）

    Returns:
        DataFrame[lag_months, correlation] — len = 2*max+1（含 0）
        欄位：lag_months（int）/ correlation（float, NaN 若樣本不足）
    """
    if aligned_df is None or aligned_df.empty:
        return pd.DataFrame(columns=["lag_months", "correlation"])
    if "score" not in aligned_df.columns or "twii_mom_pct" not in aligned_df.columns:
        return pd.DataFrame(columns=["lag_months", "correlation"])

    s = aligned_df["score"]
    t = aligned_df["twii_mom_pct"]

    rows = []
    for lag in range(-int(max_lag_months), int(max_lag_months) + 1):
        if lag >= 0:
            # score 領先 lag 月 → shift score forward
            corr = s.shift(lag).corr(t)
        else:
            corr = s.corr(t.shift(-lag))
        rows.append({"lag_months": lag, "correlation": corr})
    return pd.DataFrame(rows)


def find_best_lead_lag(
    corr_df: pd.DataFrame,
    prefer_positive: bool = True,
) -> tuple[Optional[int], Optional[float]]:
    """從 cross-correlation 表挑出絕對值最大那筆 (lag, corr).

    Args:
        corr_df: compute_lead_lag_correlation 的輸出
        prefer_positive: True → 只挑正相關（macro_score 高 → TWII 漲）；False → 看絕對值

    Returns:
        (best_lag_months, best_correlation)；空表 / 全 NaN → (None, None)
    """
    if corr_df is None or corr_df.empty:
        return None, None
    df = corr_df.dropna(subset=["correlation"])
    if df.empty:
        return None, None
    if prefer_positive:
        df = df[df["correlation"] > 0]
        if df.empty:
            return None, None
        row = df.loc[df["correlation"].idxmax()]
    else:
        row = df.loc[df["correlation"].abs().idxmax()]
    return int(row["lag_months"]), float(row["correlation"])


def summarize_crisis_score_around_events(
    events: list,
    score_series: pd.DataFrame,
    lookback_months: int = 6,
) -> list[dict]:
    """每場 crisis 事件統計 peak 前 N 月 macro_score 平均 + peak/trough 點值.

    Args:
        events: services.crisis_backtest.detect_crisis_events 的輸出
                （每個 element 需有 .peak_date / .trough_date attribute）
        score_series: services.macro_validation.calc_macro_score_series 的輸出
        lookback_months: peak 前向回看 N 月算平均（預設 6）

    Returns:
        list of dict — 每場 crisis 一筆，含：
        - peak_date / trough_date (YYYY-MM)
        - score_lookback_avg: peak 前 N 月平均
        - score_at_peak: peak 月 score
        - score_at_trough: trough 月 score
        - score_drop_from_avg: score_at_peak - score_lookback_avg
    """
    out: list[dict] = []
    if not events or score_series is None or score_series.empty:
        return out
    scores = score_series["score"]
    if not isinstance(scores.index, pd.DatetimeIndex):
        scores.index = pd.to_datetime(scores.index)

    def _score_at(dt: Optional[pd.Timestamp]) -> Optional[float]:
        if dt is None:
            return None
        mask = scores.index <= dt
        if not mask.any():
            return None
        return float(scores[mask].iloc[-1])

    def _avg_in_window(end_dt: Optional[pd.Timestamp]) -> Optional[float]:
        if end_dt is None:
            return None
        start_dt = end_dt - pd.DateOffset(months=int(lookback_months))
        mask = (scores.index >= start_dt) & (scores.index < end_dt)
        if not mask.any():
            return None
        return float(scores[mask].mean())

    for ev in events:
        peak = getattr(ev, "peak_date", None)
        trough = getattr(ev, "trough_date", None)
        peak_ts = pd.Timestamp(peak) if peak is not None else None
        trough_ts = pd.Timestamp(trough) if trough is not None else None

        s_avg = _avg_in_window(peak_ts)
        s_peak = _score_at(peak_ts)
        s_trough = _score_at(trough_ts)
        drop = (s_peak - s_avg) if (s_peak is not None and s_avg is not None) else None

        out.append({
            "peak_date": peak_ts.strftime("%Y-%m") if peak_ts is not None else None,
            "trough_date": trough_ts.strftime("%Y-%m") if trough_ts is not None else None,
            "score_lookback_avg": s_avg,
            "score_at_peak": s_peak,
            "score_at_trough": s_trough,
            "score_drop_from_avg": drop,
        })
    return out
