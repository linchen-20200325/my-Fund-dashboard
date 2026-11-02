# -*- coding: utf-8 -*-
"""淨值序列的三個區間指標（純數學；原 `ui_v2/hld/logic.py`，2026-11-02 PORT，算式一字未改）。

輸入 `navs`：依日期排好的淨值數列（呼叫端負責切區間與排序）。筆數少於 2、或遇到 0 分母 → 回 `None`
（算不出來就是算不出來，不回 0；`CLAUDE.md` §1）。浮點零判定一律用 `math.isclose`（§4.3）。

年化基數 `TRADING_DAYS_PER_YEAR` 取 L0 SSOT `shared/signal_thresholds.py`（值 252，與原 ui_v2 本地常數相同）；
原本 ui_v2 自己寫一份只因為 ui_v2 的 import 守衛不准它碰 `shared`。
"""

from __future__ import annotations

import math

from shared.signal_thresholds import TRADING_DAYS_PER_YEAR

__all__ = ("TRADING_DAYS_PER_YEAR", "return_pct", "drawdown_pct", "vol_pct")


def return_pct(navs) -> float | None:
    """區間報酬率：以區間首末兩筆計算，單位百分點。"""
    if not navs or len(navs) < 2:
        return None
    first = navs[0]
    if math.isclose(first, 0.0, abs_tol=1e-12):
        return None
    return (navs[-1] / first - 1.0) * 100.0


def drawdown_pct(navs) -> float | None:
    """最大回撤：逐日除以之前的最高值，取最小值後減一。"""
    if not navs or len(navs) < 2:
        return None
    peak = navs[0]
    worst = 0.0
    for value in navs:
        peak = max(peak, value)
        if math.isclose(peak, 0.0, abs_tol=1e-12):
            return None
        worst = min(worst, value / peak - 1.0)
    return worst * 100.0


def vol_pct(navs) -> float | None:
    """期間波動：日報酬標準差年化，年化基數為交易日 252。"""
    if not navs or len(navs) < 2:
        return None
    rets = []
    for previous, current in zip(navs, navs[1:]):
        if math.isclose(previous, 0.0, abs_tol=1e-12):
            return None
        rets.append(current / previous - 1.0)
    if len(rets) < 2:
        return None
    mean = sum(rets) / len(rets)
    variance = sum((r - mean) ** 2 for r in rets) / len(rets)
    return math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR) * 100.0
