"""crisis_backtest.py — 危機事件偵測 + 基金回測引擎 (v18.260, Phase 1).

User 需求：「回測大盤下跌時，驗證總經訊號預測力 + 該基金最大跌幅 + 策略比較」。
本檔聚焦 Phase 1 純後端引擎（不含 UI）：
- 從 SPX / TWII 月度收盤偵測歷史危機事件（MaxDD ≥ 門檻）
- 對每個事件補上該基金當時跌幅（若 NAV 序列涵蓋該期間）
- 純函式式設計，所有 I/O 集中在 fetch_market_series

後續 Phase（PR #111+）：UI Tab → 總經訊號歷史回看 → 策略 grid_search → AI 建議
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


MARKET_TICKERS: dict[str, str] = {
    "SPX": "^GSPC",
    "TWII": "^TWII",
}


@dataclass
class CrisisEvent:
    """單一危機事件 — 從高點到低點再到回升的完整週期。"""
    market: str
    peak_date: pd.Timestamp
    trough_date: pd.Timestamp
    recovery_date: Optional[pd.Timestamp]
    peak_value: float
    trough_value: float
    drawdown_pct: float                       # 負數，例如 -0.234
    duration_days: int                        # peak → trough
    recovery_days: Optional[int]              # trough → recovery（None = 尚未回到 peak）
    # 該基金在此事件期間的對照（若 nav_series 涵蓋）
    fund_peak_value: Optional[float] = None
    fund_trough_value: Optional[float] = None
    fund_drawdown_pct: Optional[float] = None
    fund_recovery_pct: Optional[float] = None  # 從 trough 到 recovery_date 的反彈

    def to_dict(self) -> dict:
        return {
            "market": self.market,
            "peak_date": str(self.peak_date.date()) if self.peak_date is not None else None,
            "trough_date": str(self.trough_date.date()) if self.trough_date is not None else None,
            "recovery_date": str(self.recovery_date.date()) if self.recovery_date is not None else None,
            "peak_value": float(self.peak_value),
            "trough_value": float(self.trough_value),
            "drawdown_pct": float(self.drawdown_pct),
            "duration_days": int(self.duration_days),
            "recovery_days": int(self.recovery_days) if self.recovery_days is not None else None,
            "fund_peak_value": float(self.fund_peak_value) if self.fund_peak_value is not None else None,
            "fund_trough_value": float(self.fund_trough_value) if self.fund_trough_value is not None else None,
            "fund_drawdown_pct": float(self.fund_drawdown_pct) if self.fund_drawdown_pct is not None else None,
            "fund_recovery_pct": float(self.fund_recovery_pct) if self.fund_recovery_pct is not None else None,
        }


def fetch_market_series(market: str = "SPX", years: int = 10) -> pd.Series:
    """抓 SPX 或 TWII N 年的月度（實作為日度，呼叫端可自行 resample）收盤序列。

    走 repositories.macro_repository.fetch_yf_close（Yahoo Chart API + NAS proxy）。

    Args:
        market: "SPX" 或 "TWII"
        years: 抓取年數（轉換為 yfinance range_，例：10y）

    Returns:
        pd.Series with DatetimeIndex, 名為 market；空 Series 表示抓取失敗
    """
    if market not in MARKET_TICKERS:
        raise ValueError(f"未知 market: {market}，支援：{list(MARKET_TICKERS)}")
    ticker = MARKET_TICKERS[market]
    range_ = f"{int(years)}y"
    try:
        from repositories.macro_repository import fetch_yf_close
        s = fetch_yf_close(ticker, range_=range_, interval="1d")
        if s is None or s.empty:
            return pd.Series(dtype=float, name=market)
        s = s.dropna()
        s.name = market
        # F-PROV-1 phase 18 v19.104 — provenance(Series.attrs;若上游 fetch_yf_close 已寫入則保留)
        if "source" not in s.attrs:
            s.attrs["source"] = f"Yahoo:fetch_yf_close:{ticker}:{range_}:crisis_backtest"
            import pandas as _pd_cb
            s.attrs["fetched_at"] = _pd_cb.Timestamp.now('UTC').isoformat()
        return s
    except Exception as e:
        print(f"[crisis_backtest.fetch_market_series] {market} 抓取失敗：{e}")
        return pd.Series(dtype=float, name=market)


def detect_crisis_events(
    series: pd.Series,
    threshold: float = -0.10,
    market: str = "SPX",
) -> list[CrisisEvent]:
    """從價格序列偵測 MaxDD ≥ |threshold| 的所有獨立危機事件。

    演算法：
    1. 走訪序列，維護 running HWM
    2. 若回撤 ≤ threshold，標記事件開始（peak = 最近 HWM）
    3. 持續追蹤 trough，直到價格回到 ≥ peak（即 recovery）或序列結束
    4. recovery 達成後重置 HWM，繼續找下一個事件

    Args:
        series: 日度（或月度）價格序列，DatetimeIndex
        threshold: 觸發門檻，負數，例如 -0.10 = 跌 10%
        market: 標記到 CrisisEvent.market

    Returns:
        list[CrisisEvent]，按 peak_date 排序
    """
    if series is None or series.empty or len(series) < 2:
        return []
    if threshold >= 0:
        raise ValueError(f"threshold 必須為負數，收到 {threshold}")

    events: list[CrisisEvent] = []
    in_event = False
    peak_value = float(series.iloc[0])
    peak_idx = series.index[0]
    trough_value = peak_value
    trough_idx = peak_idx

    for ts, val in series.items():
        v = float(val)
        if not in_event:
            if v >= peak_value:
                peak_value = v
                peak_idx = ts
                trough_value = v
                trough_idx = ts
            else:
                dd = (v - peak_value) / peak_value
                if dd <= threshold:
                    in_event = True
                    trough_value = v
                    trough_idx = ts
                # 否則：小回檔，繼續觀察
        else:
            # 事件進行中：更新 trough，檢查是否 recovery
            if v < trough_value:
                trough_value = v
                trough_idx = ts
            if v >= peak_value:
                # Recovery 達成
                dd_pct = (trough_value - peak_value) / peak_value
                duration = (trough_idx - peak_idx).days
                recovery_days = (ts - trough_idx).days
                events.append(CrisisEvent(
                    market=market,
                    peak_date=peak_idx,
                    trough_date=trough_idx,
                    recovery_date=ts,
                    peak_value=peak_value,
                    trough_value=trough_value,
                    drawdown_pct=dd_pct,
                    duration_days=duration,
                    recovery_days=recovery_days,
                ))
                # 重置 HWM
                in_event = False
                peak_value = v
                peak_idx = ts
                trough_value = v
                trough_idx = ts

    # 序列結束時仍在事件中（尚未 recovery）→ 仍記錄
    if in_event:
        dd_pct = (trough_value - peak_value) / peak_value
        duration = (trough_idx - peak_idx).days
        events.append(CrisisEvent(
            market=market,
            peak_date=peak_idx,
            trough_date=trough_idx,
            recovery_date=None,
            peak_value=peak_value,
            trough_value=trough_value,
            drawdown_pct=dd_pct,
            duration_days=duration,
            recovery_days=None,
        ))
    return events


def attach_fund_drawdown(
    event: CrisisEvent,
    nav_series: pd.Series,
) -> CrisisEvent:
    """對單一事件補上該基金當時的高點/低點/跌幅/反彈。

    若 nav_series 完全沒涵蓋事件期間，回傳原 event 不變（4 個 fund_* 欄維持 None）。

    Returns:
        新的 CrisisEvent（不 mutate 原物件）
    """
    if nav_series is None or nav_series.empty:
        return event

    # 取事件期間（peak ~ trough）內基金 NAV
    mask_dd = (nav_series.index >= event.peak_date) & (nav_series.index <= event.trough_date)
    nav_in_event = nav_series[mask_dd].dropna()
    if nav_in_event.empty:
        return event

    fund_peak = float(nav_in_event.max())
    fund_trough = float(nav_in_event.min())
    if fund_peak <= 0:
        return event
    fund_dd_pct = (fund_trough - fund_peak) / fund_peak

    fund_recovery_pct: Optional[float] = None
    if event.recovery_date is not None:
        mask_rec = (nav_series.index > event.trough_date) & (nav_series.index <= event.recovery_date)
        nav_rec = nav_series[mask_rec].dropna()
        if not nav_rec.empty and fund_trough > 0:
            fund_recovery_pct = (float(nav_rec.iloc[-1]) - fund_trough) / fund_trough

    return CrisisEvent(
        market=event.market,
        peak_date=event.peak_date,
        trough_date=event.trough_date,
        recovery_date=event.recovery_date,
        peak_value=event.peak_value,
        trough_value=event.trough_value,
        drawdown_pct=event.drawdown_pct,
        duration_days=event.duration_days,
        recovery_days=event.recovery_days,
        fund_peak_value=fund_peak,
        fund_trough_value=fund_trough,
        fund_drawdown_pct=fund_dd_pct,
        fund_recovery_pct=fund_recovery_pct,
    )


def summarize_events_with_fund(
    market_series: pd.Series,
    fund_nav: pd.Series | None,
    threshold: float = -0.10,
    market: str = "SPX",
) -> list[CrisisEvent]:
    """一條龍：偵測事件 → 對每個事件補上該基金跌幅。

    便利包裝，呼叫端不需要分別呼叫 detect + attach。
    """
    events = detect_crisis_events(market_series, threshold=threshold, market=market)
    if fund_nav is None or fund_nav.empty:
        return events
    return [attach_fund_drawdown(ev, fund_nav) for ev in events]
