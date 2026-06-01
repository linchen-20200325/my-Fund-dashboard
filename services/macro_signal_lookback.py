"""macro_signal_lookback.py — 總經訊號歷史回看引擎 (v18.260, Phase 3).

User 需求第 3 階段：驗證 Tab1 總經訊號（VIX / HY 利差 / 殖利率倒掛 等）
對歷史危機事件的預測力 — 「峰前 N 天訊號是否真的有警示？」

設計原則：
- 純後端、純函式式，不依賴 Streamlit
- 預先抓全歷史序列一次，事件迴圈內僅做 lookup（不重複抓）
- 4 個預設訊號（與 Tab1 一致）：VIX / HY_SPREAD / T10Y2Y / UNRATE

後續 Phase（PR #113+）：策略 grid_search → AI 建議
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

import pandas as pd

from services.crisis_backtest import CrisisEvent

# 訊號方向：above = 超過閾值算警戒；below = 低於閾值算警戒
Direction = Literal["above", "below"]


@dataclass(frozen=True)
class SignalSpec:
    """單一訊號的取得與判讀規格。"""
    key: str            # 內部 key
    label: str          # UI 顯示中文名
    source: Literal["yahoo", "fred"]
    series_id: str      # Yahoo ticker 或 FRED series_id
    threshold: float    # 警戒線
    direction: Direction
    unit: str = ""      # UI 顯示用單位
    note: str = ""      # 解讀備註


# 預設訊號表 — 與 Tab1 巨觀儀表板邏輯對齊
DEFAULT_SIGNALS: list[SignalSpec] = [
    SignalSpec(
        key="VIX",
        label="VIX 恐慌指數",
        source="yahoo",
        series_id="^VIX",
        threshold=25.0,
        direction="above",
        unit="",
        note="VIX > 25 = 市場恐慌升溫",
    ),
    SignalSpec(
        key="HY_SPREAD",
        label="HY 信用利差",
        source="fred",
        series_id="BAMLH0A0HYM2",
        threshold=6.0,
        direction="above",
        unit="%",
        note="HY OAS > 6% = 信用緊縮",
    ),
    SignalSpec(
        key="T10Y2Y",
        label="10Y-2Y 殖利率利差",
        source="fred",
        series_id="T10Y2Y",
        threshold=0.0,
        direction="below",
        unit="%",
        note="T10Y2Y < 0 = 殖利率倒掛（衰退領先指標）",
    ),
    SignalSpec(
        key="UNRATE",
        label="美國失業率",
        source="fred",
        series_id="UNRATE",
        threshold=5.0,
        direction="above",
        unit="%",
        note="UNRATE > 5% = 就業惡化（同時指標）",
    ),
]


@dataclass
class SignalLookback:
    """單一事件 × 單一訊號的回看結果。"""
    event_peak_date: pd.Timestamp
    signal_key: str
    signal_label: str
    threshold: float
    direction: Direction
    # 峰前 lookback_days 天的訊號值（若序列涵蓋）
    lookback_days: int
    value_at_lookback: Optional[float]
    triggered_at_lookback: bool
    # 峰前最後 max_lookback_days 內第一次進入警戒區的日期
    first_warning_date: Optional[pd.Timestamp]
    lead_time_days: Optional[int]   # peak - first_warning（正數）

    def to_dict(self) -> dict:
        return {
            "event_peak_date": str(self.event_peak_date.date()) if self.event_peak_date is not None else None,
            "signal_key": self.signal_key,
            "signal_label": self.signal_label,
            "threshold": float(self.threshold),
            "direction": self.direction,
            "lookback_days": int(self.lookback_days),
            "value_at_lookback": float(self.value_at_lookback) if self.value_at_lookback is not None else None,
            "triggered_at_lookback": bool(self.triggered_at_lookback),
            "first_warning_date": str(self.first_warning_date.date()) if self.first_warning_date is not None else None,
            "lead_time_days": int(self.lead_time_days) if self.lead_time_days is not None else None,
        }


def _is_warning(value: float, threshold: float, direction: Direction) -> bool:
    if direction == "above":
        return value >= threshold
    return value <= threshold


def fetch_signal_series(
    spec: SignalSpec,
    years: int = 20,
    fred_api_key: str = "",
) -> pd.Series:
    """抓取單一訊號的歷史序列（多年）。

    Yahoo: 走 fetch_yf_close(ticker, range_="{years}y")
    FRED:  走 fetch_fred(series_id, api_key, n=years*365)（保守抓上限）

    失敗回空 Series。
    """
    try:
        if spec.source == "yahoo":
            from repositories.macro_repository import fetch_yf_close
            s = fetch_yf_close(spec.series_id, range_=f"{int(years)}y", interval="1d")
            if s is None or s.empty:
                return pd.Series(dtype=float, name=spec.key)
            s = s.dropna()
            s.name = spec.key
            return s
        # FRED
        from repositories.macro_repository import fetch_fred
        n = max(int(years) * 365, 250)
        df = fetch_fred(spec.series_id, fred_api_key, n=n)
        if df is None or df.empty:
            return pd.Series(dtype=float, name=spec.key)
        s = pd.Series(df["value"].values, index=pd.to_datetime(df["date"]), name=spec.key, dtype=float)
        return s.dropna()
    except Exception as e:
        print(f"[macro_signal_lookback.fetch_signal_series] {spec.key} 抓取失敗：{e}")
        return pd.Series(dtype=float, name=spec.key)


def evaluate_signal_at_event(
    event: CrisisEvent,
    signal_series: pd.Series,
    spec: SignalSpec,
    lookback_days: int = 90,
    max_lookback_days: int = 365,
) -> SignalLookback:
    """對單一事件單一訊號做回看判讀。

    1. 取峰日往前 lookback_days 那一天最近的觀測值 → triggered_at_lookback
    2. 在峰前 max_lookback_days 區間找「最早一次」進入警戒區 → lead_time_days

    無資料涵蓋 → 各欄為 None / False。
    """
    if signal_series is None or signal_series.empty or event.peak_date is None:
        return SignalLookback(
            event_peak_date=event.peak_date,
            signal_key=spec.key,
            signal_label=spec.label,
            threshold=spec.threshold,
            direction=spec.direction,
            lookback_days=lookback_days,
            value_at_lookback=None,
            triggered_at_lookback=False,
            first_warning_date=None,
            lead_time_days=None,
        )

    peak = event.peak_date
    target = peak - pd.Timedelta(days=lookback_days)
    before_peak = signal_series[signal_series.index <= peak]
    if before_peak.empty:
        return SignalLookback(
            event_peak_date=peak,
            signal_key=spec.key,
            signal_label=spec.label,
            threshold=spec.threshold,
            direction=spec.direction,
            lookback_days=lookback_days,
            value_at_lookback=None,
            triggered_at_lookback=False,
            first_warning_date=None,
            lead_time_days=None,
        )

    # 1) value_at_lookback：取 ≤ target 最後一筆
    on_or_before = before_peak[before_peak.index <= target]
    value_at_lb: Optional[float] = float(on_or_before.iloc[-1]) if not on_or_before.empty else None
    triggered_lb = (value_at_lb is not None) and _is_warning(value_at_lb, spec.threshold, spec.direction)

    # 2) 峰前 max_lookback_days 內第一次進入警戒區
    window_start = peak - pd.Timedelta(days=max_lookback_days)
    window = before_peak[(before_peak.index >= window_start) & (before_peak.index <= peak)]
    first_warn_date: Optional[pd.Timestamp] = None
    lead_days: Optional[int] = None
    if not window.empty:
        warn_mask = window.apply(lambda v: _is_warning(float(v), spec.threshold, spec.direction))
        warn_idx = window.index[warn_mask]
        if len(warn_idx) > 0:
            first_warn_date = warn_idx[0]
            lead_days = (peak - first_warn_date).days

    return SignalLookback(
        event_peak_date=peak,
        signal_key=spec.key,
        signal_label=spec.label,
        threshold=spec.threshold,
        direction=spec.direction,
        lookback_days=lookback_days,
        value_at_lookback=value_at_lb,
        triggered_at_lookback=triggered_lb,
        first_warning_date=first_warn_date,
        lead_time_days=lead_days,
    )


def lookback_all_signals(
    events: list[CrisisEvent],
    series_by_key: dict[str, pd.Series],
    specs: list[SignalSpec] = None,
    lookback_days: int = 90,
    max_lookback_days: int = 365,
) -> dict[str, list[SignalLookback]]:
    """對所有事件 × 所有訊號做回看。

    Args:
        events: Phase 1 偵測到的危機事件
        series_by_key: 預先抓好的 {spec.key: series}
        specs: 訊號規格清單（預設用 DEFAULT_SIGNALS）
        lookback_days: 點觀測 offset
        max_lookback_days: 第一次警戒搜尋上限

    Returns:
        {spec.key: [SignalLookback per event]}
    """
    if specs is None:
        specs = DEFAULT_SIGNALS
    out: dict[str, list[SignalLookback]] = {}
    for spec in specs:
        series = series_by_key.get(spec.key, pd.Series(dtype=float))
        out[spec.key] = [
            evaluate_signal_at_event(ev, series, spec, lookback_days, max_lookback_days)
            for ev in events
        ]
    return out


def compute_signal_hit_rate(lookbacks: list[SignalLookback]) -> dict:
    """統計單一訊號的命中率 + 平均提前天數。

    命中 = lead_time_days is not None（峰前 max_lookback_days 內曾警戒）
    覆蓋 = value_at_lookback is not None（序列有涵蓋）
    """
    if not lookbacks:
        return {"n_total": 0, "n_covered": 0, "n_hit": 0, "hit_rate": None, "avg_lead_days": None}
    n_total = len(lookbacks)
    covered = [lb for lb in lookbacks if lb.value_at_lookback is not None or lb.first_warning_date is not None]
    n_covered = len(covered)
    hits = [lb for lb in lookbacks if lb.lead_time_days is not None]
    n_hit = len(hits)
    hit_rate = (n_hit / n_covered) if n_covered > 0 else None
    avg_lead = (sum(lb.lead_time_days for lb in hits) / n_hit) if n_hit > 0 else None
    return {
        "n_total": n_total,
        "n_covered": n_covered,
        "n_hit": n_hit,
        "hit_rate": hit_rate,
        "avg_lead_days": avg_lead,
    }
