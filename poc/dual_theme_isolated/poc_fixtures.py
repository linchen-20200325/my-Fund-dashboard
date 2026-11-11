# -*- coding: utf-8 -*-
"""PoC 合成 fixture（非真實資料；沒有取數、沒有隨機：同一輸入永遠同一輸出）。

- 數列由確定性公式產生，日期是合成的工作日序列；一律在畫面標「合成示範資料」。
- 狀態字樣沿用規則表現有字樣（`shared/ui_semantics/rules.py` 的 wording）**只當 fixture 複製**，PoC 不 import 它、不改語意；
  `neutral` 在規則表沒有字樣，PoC 用明示的示範字樣。
"""
from __future__ import annotations

import math
from datetime import date, timedelta

SYNTHETIC_NOTE = "合成示範資料（隔離 PoC；非真實市場數據）"

# (key, chip 字樣（符號＋文字）, tone)
CHIPS = (
    ("attention", "◆ 需要注意", "neutral"),
    ("missing", "◇ 資料未備", "grey"),
    ("undetermined", "⬜ 無法判定", "grey"),
    ("failed", "⛔ 示範資料 取數失敗", "red"),
    ("stale", "◷ 不是最新", "yellow"),
    ("neutral", "● 中性（PoC 示範字樣）", "neutral"),
)

PERIODS = ("3M", "6M", "1Y", "3Y")
PERIOD_POINTS = {"3M": 63, "6M": 126, "1Y": 252, "3Y": 756}
DEFAULT_PERIOD = "1Y"
VIEWS = ("比較", "甲", "丙（資料未備示範）")
DEFAULT_VIEW = "比較"
MISSING_VIEW = "丙（資料未備示範）"

_N = 756


def _dates(n: int = _N):
    d, out = date(2023, 1, 2), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


DATES = tuple(_dates())


def series(name: str):
    """合成數列（已正規化到起點 = 100）。name ∈ {"甲","乙"}。"""
    if name == "甲":
        raw = [100 * (1 + 0.0004 * i + 0.06 * math.sin(i / 23.0)) for i in range(_N)]
    elif name == "乙":
        raw = [100 * (1 + 0.0002 * i + 0.09 * math.sin(i / 41.0 + 1.0)) for i in range(_N)]
    else:
        raise ValueError(f"未知的合成數列：{name!r}")
    base = raw[0]
    return tuple(round(v / base * 100, 4) for v in raw)


def window(name: str, period: str):
    if period not in PERIOD_POINTS:
        raise ValueError(f"未知的期間：{period!r}")
    n = PERIOD_POINTS[period]
    return DATES[-n:], series(name)[-n:]
