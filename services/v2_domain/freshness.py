# -*- coding: utf-8 -*-
"""延遲日數（原 `ui_v2/mkt/logic.py::delay_days`，2026-11-02 PORT，算式一字未改）。

延遲日數 ＝ `fetched_at` 的日期減 `obs_date`，單位日曆日（`44` MKT-7）。
`tz` 為 None：取 `fetched_at` 字串前 10 碼（存放的世界協調時間日期）；給了時區：把 `fetched_at` 換到該時區再取日期。
`fetched_at` 沒有時區而又要換時區 → `NaiveTimestampError`（`ValueError` 的子類），不猜。
"""

from __future__ import annotations

from datetime import date, datetime

__all__ = ("NaiveTimestampError", "delay_days")


class NaiveTimestampError(ValueError):
    """要換時區，但 `fetched_at` 沒有時區。"""

    def __init__(self, fetched_at):
        self.fetched_at = fetched_at
        super().__init__(f"fetched_at has no timezone: {fetched_at!r}")


def delay_days(obs_date: str, fetched_at: str, *, tz=None) -> int:
    if tz is None:
        fetched_day = date.fromisoformat(fetched_at[:10])
    else:
        moment = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
        if moment.tzinfo is None:
            raise NaiveTimestampError(fetched_at)
        fetched_day = moment.astimezone(tz).date()
    return (fetched_day - date.fromisoformat(obs_date)).days
