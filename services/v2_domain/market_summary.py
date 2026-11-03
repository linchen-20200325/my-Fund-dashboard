# -*- coding: utf-8 -*-
"""🌍 首屏期間漲跌與新鮮度事實（BL-0536-H2；L2 純投影，沒有新公式）。

依據：`DEC-2026-11-03-04`（「H2 的期間漲跌必須與圖表使用一致的基準與資料視窗」）；`DEC-2026-11-03-01`
Q4 A（首屏「重要依據」＝ TAIEX／S&P 500 期間漲跌，基準同圖、隨期間切換、不放日期）與 Q5 B（首屏只一枚資料新鮮度
chip ＝ 門檻待裁示；延遲天數與日期只在圖卡）；`docs/v2/81` 第 2.3 節 G3、第 3.1 節、第 4 節、第 4.1 節。

1. 期間漲跌**不另算**：直接取 `normalization.SeriesResult.period_change`（＝該序列自己的 `last_normalized`
   減 `BASE_VALUE`，即圖上那條線末點的歸一化值減 100）。與圖表同一個基準日、同一個資料視窗、同一個期間，
   因為就是同一個物件。本模組沒有任何報酬率算式。
2. 只有畫出線的序列（`SeriesResult.status == "ok"`）才有期間漲跌；沒畫線的（退回單序列時被排除、`insufficient`、
   `missing`、`withheld` 等）`period_change` 為 None，`status` 原樣帶出真正原因代碼。不補 0、不補值。
3. `mode` 原樣帶出；`comparable` 只在 `mode == "pair"` 且比較 `status == "ok"` 時為 True —— 單序列／退回單序列模式
   的那一條漲跌是該序列自己視窗的漲跌，呈現層不得把它寫成比較。
4. 首屏摘要（`MarketFirstScreen`、`PeriodChange`）**刻意不帶任何日期欄位**（Q4 A、Q5 B、D3 (i)）；
   各序列最後觀測日在 `NormalizedComparison.series[i].last_obs_date` 與 `series_freshness`（圖卡用）。
5. 新鮮度：門檻未裁示（BL-0536-H4、BL-0369），本模組只給事實 —— 各序列經過天數（`freshness.delay_days`，
   算式不另寫）與一個中性狀態 `FRESHNESS_THRESHOLD_PENDING`；**不判新、舊、正常、過期**。
   經過天數若為負（最後觀測日晚於取得日，資料不一致）照實回報，不改成 0、不改成 None；如何呈現由呈現層決定。
   `fetched_at` 沒有時區而要換時區 → `freshness.NaiveTimestampError`（照原行為大聲失敗）。
6. 回傳 frozen dataclass；狀態一律中性英文代碼；不含畫面字樣（中文字樣在呈現層）；浮點數不四捨五入。

`FRESHNESS_THRESHOLD_PENDING` 的值刻意等於呈現規則表的鍵 `threshold_pending`（`⬜ 門檻待裁示`）；
New UI2 view model（`docs/v2/80` 第 6 節）的 `freshness_state` 詞彙裡對應的是 `undetermined`（`shared/ui_semantics/rules.py::FRESHNESS_TO_KEY`
把它對到同一個鍵），adapter 照此對應；一致性由測試鎖。
"""

from __future__ import annotations

from dataclasses import dataclass

from services.v2_domain.freshness import delay_days
from services.v2_domain.normalization import MODE_PAIR, STATUS_OK, NormalizedComparison

__all__ = (
    "FRESHNESS_THRESHOLD_PENDING",
    "PeriodChange", "MarketFirstScreen", "SeriesFreshness",
    "first_screen_summary", "series_freshness",
)

# 新鮮度門檻未裁示時唯一的狀態（BL-0536-H4／BL-0369；Q5 B）。門檻裁示前本模組不產生任何其他新鮮度狀態。
FRESHNESS_THRESHOLD_PENDING = "threshold_pending"


@dataclass(frozen=True)
class PeriodChange:
    """首屏一條序列的期間漲跌（無日期）。

    - `status`：該序列 `SeriesResult.status` 原樣；`ok` ⇔ 有畫線 ⇔ `period_change` 不為 None。
    - `period_change`：圖上該序列末點歸一化值減 `BASE_VALUE`（＝百分比點數的漲跌，例 5.0 即 +5%）；沒畫線為 None。
    """

    key: str
    status: str
    period_change: float | None


@dataclass(frozen=True)
class MarketFirstScreen:
    """🌍 首屏摘要的事實部分（無日期）。

    - `period`：與圖表相同的期間（`periods.PERIODS` 之一）。
    - `mode`／`comparable`：見模組 docstring 第 3 點。
    - `period_changes`：依 `NormalizedComparison.series` 順序的 `PeriodChange`。
    - `freshness_state`：恆為 `FRESHNESS_THRESHOLD_PENDING`（門檻未裁示；Q5 B 首屏只此一枚 chip）。
    """

    period: str
    mode: str
    comparable: bool
    period_changes: tuple
    freshness_state: str


@dataclass(frozen=True)
class SeriesFreshness:
    """圖卡用的一條序列新鮮度事實（日期與經過天數只在圖卡出現）。

    - `last_obs_date`：該序列自己的最後有效觀測日（＝ `SeriesResult.last_obs_date`；缺序列為 None）。
    - `elapsed_days`：`freshness.delay_days(last_obs_date, fetched_at)`；缺 `last_obs_date` 或 `fetched_at` 為 None。
    - `state`：恆為 `FRESHNESS_THRESHOLD_PENDING`。
    """

    key: str
    last_obs_date: str | None
    elapsed_days: int | None
    state: str


def _require_comparison(comparison) -> NormalizedComparison:
    if not isinstance(comparison, NormalizedComparison):
        raise TypeError(f"comparison must be a NormalizedComparison, got {type(comparison).__name__}")
    return comparison


def first_screen_summary(comparison: NormalizedComparison) -> MarketFirstScreen:
    """把 `normalize_pair` 的結果投影成首屏摘要事實（規則見模組 docstring 第 1～4 點）。"""
    comparison = _require_comparison(comparison)
    changes = []
    for result in comparison.series:
        drawn = result.status == STATUS_OK
        if drawn != (result.period_change is not None):  # 不變量：有線 ⇔ 有漲跌
            raise RuntimeError(f"series {result.key!r}: status {result.status!r} inconsistent with period_change")
        changes.append(PeriodChange(result.key, result.status, result.period_change))
    comparable = comparison.mode == MODE_PAIR and comparison.status == STATUS_OK
    return MarketFirstScreen(comparison.period, comparison.mode, comparable, tuple(changes),
                             FRESHNESS_THRESHOLD_PENDING)


def series_freshness(comparison: NormalizedComparison, fetched_at, *, tz=None) -> tuple:
    """各序列經過天數（圖卡用；規則見模組 docstring 第 5 點）。

    - `fetched_at`：dict，鍵必須恰為 `comparison.series` 的鍵；值為該序列的取得時間字串或 None（未取得）。
    - `tz`：同 `freshness.delay_days`（None＝取 `fetched_at` 前 10 碼）。
    """
    comparison = _require_comparison(comparison)
    keys = [result.key for result in comparison.series]
    if not isinstance(fetched_at, dict) or set(fetched_at) != set(keys):
        raise ValueError(f"fetched_at must be a dict with exactly the keys {keys!r}")
    out = []
    for result in comparison.series:
        stamp = fetched_at[result.key]
        if stamp is not None and not isinstance(stamp, str):
            raise ValueError(f"fetched_at[{result.key!r}] must be a string or None, got {type(stamp).__name__}")
        elapsed = None
        if result.last_obs_date is not None and stamp is not None:
            elapsed = delay_days(result.last_obs_date, stamp, tz=tz)
        out.append(SeriesFreshness(result.key, result.last_obs_date, elapsed, FRESHNESS_THRESHOLD_PENDING))
    return tuple(out)
