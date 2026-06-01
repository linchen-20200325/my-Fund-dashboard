"""macro_validation.py — Tab1 Macro Score 預測力驗證 (v18.260, Phase 6a).

User 需求：「我比較想驗證目前我的總經 Tab 的歷史資料與歷史景氣變差的差異
（這樣才知道看總經 Tab 準不準）」。

實作策略：
- 不依賴歷史 macro_score DB（不存在）
- 即時利用 fetch_all_indicators() 各 indicator 的 .series 欄位（FRED 多年歷史時序）
- 逐月對齊每個指標到 month-end，套用與 fetch_all_indicators() 完全一致的閾值規則打分
- 聚合公式鏡像 services.macro_service.calc_macro_phase：
    norm = (earned_w + total_w) / (2 * total_w) * 10
- 與既有 services.crisis_backtest.detect_crisis_events 輸出對齊，量化「peak 前 N 月
  score 降幅 ≥ threshold 才算預警」的命中率，並做 crisis vs 平時的 t-test。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd


# ────────────────────────────────────────────────────────────────────
# 各指標的 (weight, 閾值打分) — 鏡像 services/macro_service.py:fetch_all_indicators
# 只收 series 已為「絕對值」（可直接 ffill 對齊月末）的核心指標，
# 排除 ADL/DXY/cross-rates（series 是 ratio/level，score 看 monthly change，回測對齊複雜）
# ────────────────────────────────────────────────────────────────────
ScoreFn = Callable[[float], float]

SCORE_RULES: dict[str, tuple[float, ScoreFn]] = {
    "PMI":          (2.0, lambda v: 2.0 if v >= 50 else (-2.0 if v < 45 else -1.0)),
    "YIELD_10Y2Y":  (2.0, lambda v: 2.0 if v > 0.5 else (-2.0 if v < 0 else 0.0)),
    "YIELD_10Y3M":  (2.0, lambda v: 2.0 if v > 0 else -2.0),
    "HY_SPREAD":    (2.0, lambda v: 2.0 if v < 4 else (-2.0 if v > 6 else 0.0)),
    "M2":           (1.0, lambda v: 1.0 if v > 5 else (-1.0 if v < 0 else 0.0)),
    "FED_BS":       (1.0, lambda v: 1.0 if v > 5 else (-1.0 if v < -5 else 0.0)),
    "VIX":          (1.0, lambda v: 1.0 if v < 18 else (-1.0 if v > 30 else 0.0)),
    "CPI":          (0.5, lambda v: 1.0 if 1 < v < 2.5 else (-1.0 if v > 4 else 0.0)),
    "UNEMPLOYMENT": (0.5, lambda v: 1.0 if v < 4.5 else (-2.0 if v > 6 else 0.0)),
}


def aggregate_score(scored: dict[str, tuple[float, float]]) -> tuple[float, str]:
    """把 {key: (weight, score)} 聚合成 (0-10 score, phase 名稱).

    與 services.macro_service.calc_macro_phase 公式一致：
        norm = (earned_w + total_w) / (2 * total_w) * 10
    """
    if not scored:
        return 5.0, "復甦"
    total_w = sum(w for w, _ in scored.values())
    earned_w = sum(s for _, s in scored.values())
    if total_w <= 0:
        norm = 5.0
    else:
        # 每個指標 score 已 clip 到 [-w, +w]（由 SCORE_RULES 保證），此處不再 clip
        norm = (earned_w + total_w) / (2 * total_w) * 10
    score = round(max(0.0, min(10.0, norm)), 1)
    if score >= 8:
        phase = "高峰"
    elif score >= 5:
        phase = "擴張"
    elif score >= 3:
        phase = "復甦"
    else:
        phase = "衰退"
    return score, phase


def calc_macro_score_series(
    indicators_now: dict,
    years: int = 15,
    freq: str = "ME",
) -> pd.DataFrame:
    """重算過去 N 年每月 macro_score → 拿來驗證 Tab1 預測力.

    Args:
        indicators_now: fetch_all_indicators(fred_api_key) 輸出
                        — 每個 indicator dict 必含 "series" (pd.Series with DatetimeIndex)
        years: 回看年數（預設 15；最大受限於各 series 涵蓋範圍）
        freq: 重算頻率 ('ME' 月末 / 'W' 週末)

    Returns:
        DataFrame indexed by date with columns [score, phase, n_indicators].
        n_indicators = 該日期實際參與打分的指標數（未涵蓋的不算）
    """
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=int(years))
    date_range = pd.date_range(start=start, end=end, freq=freq)

    # 對齊每個 indicator series 到 date_range（forward-fill 取≤該日期最後已知值）
    aligned: dict[str, pd.Series] = {}
    for key in SCORE_RULES:
        ind = (indicators_now or {}).get(key)
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
        s = s.sort_index()
        aligned[key] = s.reindex(date_range, method="ffill")

    rows = []
    for dt in date_range:
        scored: dict[str, tuple[float, float]] = {}
        for key, (w, score_fn) in SCORE_RULES.items():
            if key not in aligned:
                continue
            v = aligned[key].loc[dt]
            if pd.isna(v):
                continue
            try:
                s = float(score_fn(float(v)))
            except Exception:
                continue
            # clip 到 [-w, +w] 保險（鏡像 calc_macro_phase 行 861）
            s = max(-w, min(w, s))
            scored[key] = (w, s)
        score, phase = aggregate_score(scored)
        rows.append({
            "date": dt,
            "score": score,
            "phase": phase,
            "n_indicators": len(scored),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    return df.set_index("date")


@dataclass
class CrisisVerifyResult:
    """單一危機事件的 macro_score 預警判定結果."""
    peak_date: pd.Timestamp
    trough_date: Optional[pd.Timestamp]
    score_lead: Optional[float]      # peak 前 lead_months 個月的 score
    score_peak: Optional[float]      # peak 月的 score
    score_trough: Optional[float]    # trough 月的 score
    score_drop_pct: Optional[float]  # (score_peak - score_lead) / score_lead
    hit: bool                        # drop_pct ≤ -drop_threshold 算預警成功


def verify_score_vs_crises(
    score_series: pd.DataFrame,
    events: list,
    lead_months: int = 6,
    drop_threshold: float = 0.20,
) -> list[CrisisVerifyResult]:
    """對每個 crisis event 判斷「峰前 N 月 score 是否預警下降」.

    判定規則：score 由 lead 點到 peak 點降幅 ≥ drop_threshold → 命中。
    """
    out: list[CrisisVerifyResult] = []
    if score_series is None or score_series.empty:
        return out
    scores = score_series["score"]

    def _score_at(dt: pd.Timestamp) -> Optional[float]:
        mask = scores.index <= dt
        if not mask.any():
            return None
        return float(scores[mask].iloc[-1])

    for ev in events or []:
        peak_dt = pd.Timestamp(ev.peak_date) if getattr(ev, "peak_date", None) is not None else None
        trough_dt = pd.Timestamp(ev.trough_date) if getattr(ev, "trough_date", None) is not None else None
        if peak_dt is None:
            continue
        lead_dt = peak_dt - pd.DateOffset(months=int(lead_months))

        s_lead = _score_at(lead_dt)
        s_peak = _score_at(peak_dt)
        s_trough = _score_at(trough_dt) if trough_dt is not None else None

        drop_pct: Optional[float] = None
        hit = False
        if s_lead is not None and s_peak is not None and s_lead > 0:
            drop_pct = (s_peak - s_lead) / s_lead
            hit = drop_pct <= -float(drop_threshold)

        out.append(CrisisVerifyResult(
            peak_date=peak_dt,
            trough_date=trough_dt,
            score_lead=s_lead,
            score_peak=s_peak,
            score_trough=s_trough,
            score_drop_pct=drop_pct,
            hit=hit,
        ))
    return out


def compute_period_stats(
    score_series: pd.DataFrame,
    events: list,
) -> dict:
    """crisis 期間 vs 平時 score 分佈差異 (含 Welch t-test p-value).

    crisis 期 = peak_date 到 trough_date 之間（含端點）；其餘為平時。
    """
    blank = {
        "crisis_mean": None, "normal_mean": None,
        "crisis_std": None, "normal_std": None,
        "n_crisis": 0, "n_normal": 0,
        "p_value": None,
    }
    if score_series is None or score_series.empty:
        return blank

    in_crisis = pd.Series(False, index=score_series.index)
    for ev in events or []:
        peak_dt = getattr(ev, "peak_date", None)
        trough_dt = getattr(ev, "trough_date", None)
        if peak_dt is None or trough_dt is None:
            continue
        peak_dt = pd.Timestamp(peak_dt)
        trough_dt = pd.Timestamp(trough_dt)
        mask = (score_series.index >= peak_dt) & (score_series.index <= trough_dt)
        in_crisis = in_crisis | mask

    scores = score_series["score"]
    crisis_scores = scores[in_crisis]
    normal_scores = scores[~in_crisis]

    p_value: Optional[float] = None
    if len(crisis_scores) >= 5 and len(normal_scores) >= 5:
        try:
            from scipy.stats import ttest_ind
            _t, p = ttest_ind(crisis_scores, normal_scores, equal_var=False)
            if pd.notna(p):
                p_value = float(p)
        except Exception:
            p_value = None

    return {
        "crisis_mean": float(crisis_scores.mean()) if len(crisis_scores) > 0 else None,
        "normal_mean": float(normal_scores.mean()) if len(normal_scores) > 0 else None,
        "crisis_std": float(crisis_scores.std()) if len(crisis_scores) > 1 else None,
        "normal_std": float(normal_scores.std()) if len(normal_scores) > 1 else None,
        "n_crisis": int(in_crisis.sum()),
        "n_normal": int((~in_crisis).sum()),
        "p_value": p_value,
    }
