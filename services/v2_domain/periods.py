# -*- coding: utf-8 -*-
"""時間序列的期間切片（原 `ui_v2/mkt/chart.py`，2026-11-02 PORT，切片邊界一字未改）。

規則（原 chart.py 檔頭照搬）：
- 缺資料不補：`value_num` 是 None／NaN／非數字的點保留為 None（折線在那裡斷開），不補 0、不 ffill、不內插；
- 全空 → `STATUS_EMPTY`；
- 期間不足就說不足：最早一筆有值的觀測日**晚於**視窗起點 → `STATUS_INSUFFICIENT`，**不**縮短區間冒充；
  視窗以「最後一筆有值的觀測日」往回推整數個日曆月，不以今天推；
- 已知限制：視窗起點落在週末／假日時，最早有值觀測日必晚於起點而被判不足（不另發明容忍規則）。
"""

from __future__ import annotations

import math
from datetime import date, timedelta

__all__ = (
    "PERIODS", "PERIOD_MONTHS", "DEFAULT_PERIOD",
    "STATUS_OK", "STATUS_EMPTY", "STATUS_INSUFFICIENT",
    "is_number", "clean_points", "months_back", "slice_period",
)

# 期間（客戶裁示：3M／6M／1Y／3Y；預設 1Y）。月數是定義，不是門檻。
PERIODS = ("3M", "6M", "1Y", "3Y")
PERIOD_MONTHS = {"3M": 3, "6M": 6, "1Y": 12, "3Y": 36}
DEFAULT_PERIOD = "1Y"

STATUS_OK = "ok"
STATUS_EMPTY = "empty"
STATUS_INSUFFICIENT = "insufficient"


def is_number(value) -> bool:
    """有限的 int／float（bool 不算）。"""
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def clean_points(points) -> list:
    """排序並把無效值（None／NaN／非數字）一律變成 None（保留這一天，折線在此斷開）。"""
    cleaned = [{"obs_date": p["obs_date"], "value_num": p["value_num"] if is_number(p.get("value_num")) else None}
               for p in points]
    return sorted(cleaned, key=lambda p: p["obs_date"])


def months_back(day: date, months: int) -> date:
    """往回推整數個日曆月；目標月沒有該日（例 3/31 回推 1 個月）取該月最後一天。"""
    total = day.year * 12 + (day.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    # 該月最後一天
    next_first = date(year + (month == 12), (month % 12) + 1, 1)
    last_day = (next_first - timedelta(days=1)).day
    return date(year, month, min(day.day, last_day))


def slice_period(points, period: str) -> dict:
    """依期間切片。回傳 `{"status", "period", "points", "window_start", "window_end", "first_obs", "last_obs"}`。

    - `points`：`[{"obs_date": "YYYY-MM-DD", "value_num": float|None}, ...]`（可無序）。
    - `status == STATUS_EMPTY`：沒有任何有值的點；`points` 為 []。
    - `status == STATUS_INSUFFICIENT`：最早有值的觀測日晚於視窗起點；`points` 為 []（不縮短冒充）。
    - `status == STATUS_OK`：`points` 為視窗內全部點（含 None 的點，供斷線）。
    - `period` 不在 `PERIOD_MONTHS` → `ValueError`。
    """
    if period not in PERIOD_MONTHS:
        raise ValueError(f"period must be one of {PERIODS}: {period!r}")
    cleaned = clean_points(points)
    valued = [p for p in cleaned if p["value_num"] is not None]
    base = {"period": period, "points": [], "window_start": None, "window_end": None,
            "first_obs": None, "last_obs": None}
    if not valued:
        return {**base, "status": STATUS_EMPTY}
    first_obs, last_obs = valued[0]["obs_date"], valued[-1]["obs_date"]
    start = months_back(date.fromisoformat(last_obs), PERIOD_MONTHS[period]).isoformat()
    base.update(window_start=start, window_end=last_obs, first_obs=first_obs, last_obs=last_obs)
    if first_obs > start:
        return {**base, "status": STATUS_INSUFFICIENT}
    window = [p for p in cleaned if start <= p["obs_date"] <= last_obs]
    return {**base, "status": STATUS_OK, "points": window}
