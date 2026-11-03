# -*- coding: utf-8 -*-
"""🌍 TAIEX vs S&P 500 歸一化比較（BL-0536-H1；L2 純計算，新寫，不沿用 Old UI `services/benchmark_compare.py`）。

依據（客戶裁示，逐字檔 `docs/evidence/decisions/2026-11-03_mkt_wireframe_ruling.md`；`docs/DECISIONS.md`
`DEC-2026-11-03-01`；`docs/v2/81_new_ui2_wireframe_01_market.md` 第 7 節 Q2-a／b／c A、第 4 節與 4.1 節情境表）：

1. 輸入：兩條日頻收盤序列（各自 `[{"obs_date", "value_num"}, ...]`）＋ 期間（`periods.PERIODS`）。
   無效值（None／NaN／±inf／bool／非數字）一律當缺口（None），不補 0、不 ffill、不內插、不重抽樣
   （沿用 `periods.clean_points`，經 `slice_period` 呼叫；`CLAUDE.md` §1、§4.5）。
2. 各序列的視窗起點＝該序列自己的 `periods.slice_period` 起點（以該序列最後一筆有值觀測日往回推
   `PERIOD_MONTHS` 個日曆月；本檔不另寫月份算術）。
3. 比較視窗起點＝兩條起點中**較晚者**（Q2-a A）。
4. 任一條涵蓋不到自己的期間起點（`slice_period` 回 `STATUS_INSUFFICIENT`）→ 整個比較標
   `insufficient`、不畫線、不縮短冒充（Q2-a A「任一條涵蓋不到所選期間 → 該期間標不足」；
   客戶「歷史不足就明確顯示不足，不偷偷縮短定義」）。單序列模式下則是那一條自己不足 → 比較標 `insufficient`。
5. 基準日＝比較視窗起點當日或之後、兩條**都有**有效收盤的第一天；兩條在該日都等於 `BASE_VALUE`
   （＝ 原值 / 基準日原值 × 100）。不得以兩條各自的首筆為基準（Q2-a C 未採；客戶「不得用兩條各自不同日期的首筆都設為 100」）。
6. 終點：各序列畫到**自己的**最後有效觀測日（Q2-b A）；每條結果各自帶 `last_obs_date`、`last_normalized`、
   `period_change`（＝ `last_normalized - BASE_VALUE`），三者都指同一條序列自己的那一天。
   本模組**刻意不提供**任何「共同終點日」欄位，避免讓人以為兩條最後一天相同。
7. 比較視窗內兩條沒有任何共同有效日 → `no_common_base`；只有一天 → `too_few_common_days`
   （Q2-a A「視窗內共同有值日不足 2 天 → 無法判定（一個點畫不成線）」）；兩者皆不畫線。
8. 缺一條（呼叫端傳 None，或整條沒有任何有效值）→ 單序列模式（Q2-c A）：另一條照算，基準日改取該條自己
   視窗內的第一筆有效值（Q2-c A「基準日改取該條視窗首筆並標明」）；`missing_keys` 指明缺哪一條；
   有效點不足 2 個 → `too_few_points`（一個點畫不成線）。兩條都缺 → `both_missing`，不畫線。
9. 格式錯誤一律大聲失敗（`NormalizationInputError`，`ValueError` 子類）：同一序列內 `obs_date` 重複（不去重）、
   `obs_date` 不是日期（只收 `datetime.date`（不收 `datetime.datetime`）或標準 `YYYY-MM-DD` 字串）、
   點不是 dict、序列不是 list／tuple、基準日原值 ≤ 0（無法當除數）。
   未排序的輸入照 `periods.clean_points` 既有行為先排序（與 ui_v2 期間切片一致）。
10. 回傳 frozen dataclass；狀態一律中性英文代碼，不含任何畫面字樣（`CLAUDE.md` §8.2 L2；中文字樣在呈現層）；
    浮點數不四捨五入。日期一律以 `YYYY-MM-DD` 字串回傳（與 `periods.slice_period` 一致）。
11. 不含任何門檻、新鮮度判斷或狀態詞；VIX／殖利率不在本模組射程。

`BASE_VALUE = 100`：New UI2 跨頁歸一化基準值（`docs/v2/79` UI-13 A，`DEC-2026-11-02-07`）。
`MIN_LINE_POINTS = 2`：一個點畫不成線（Q2-a A 原文「不足 2 天」）；這是定義，不是可調門檻。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from services.v2_domain.periods import (
    PERIOD_MONTHS,
    PERIODS,
    STATUS_INSUFFICIENT,
    STATUS_OK,
    slice_period,
)

__all__ = (
    "BASE_VALUE", "MIN_LINE_POINTS",
    "STATUS_OK", "STATUS_INSUFFICIENT", "STATUS_NO_COMMON_BASE", "STATUS_TOO_FEW_COMMON_DAYS",
    "STATUS_TOO_FEW_POINTS", "STATUS_BOTH_MISSING",
    "SERIES_MISSING", "SERIES_WITHHELD",
    "MODE_PAIR", "MODE_SINGLE", "MODE_NONE",
    "NormalizationInputError", "NormalizedPoint", "SeriesResult", "NormalizedComparison",
    "normalize_pair",
)

# UI-13 A（`DEC-2026-11-02-07`）：歸一化基準值＝100。
BASE_VALUE = 100
# 一個點畫不成線（Q2-a A「視窗內共同有值日不足 2 天 → 無法判定」）。定義，不是門檻。
MIN_LINE_POINTS = 2

# 比較層狀態（`NormalizedComparison.status`）；`ok`／`insufficient` 沿用 `periods` 的同一個代碼。
STATUS_NO_COMMON_BASE = "no_common_base"
STATUS_TOO_FEW_COMMON_DAYS = "too_few_common_days"
STATUS_TOO_FEW_POINTS = "too_few_points"
STATUS_BOTH_MISSING = "both_missing"

# 序列層另有的兩個狀態（`SeriesResult.status`；其餘沿用 ok／insufficient／too_few_points）。
SERIES_MISSING = "missing"      # 呼叫端傳 None，或整條沒有任何有效值
SERIES_WITHHELD = "withheld"    # 本序列自己涵蓋期間，但整個比較不可畫（另一條不足、無共同基準日等），故不出線

MODE_PAIR = "pair"
MODE_SINGLE = "single"
MODE_NONE = "none"


class NormalizationInputError(ValueError):
    """輸入格式錯誤（大聲失敗，不猜、不去重）。訊息為中性英文。"""


@dataclass(frozen=True)
class NormalizedPoint:
    """一個歸一化點。`value` 為 None ＝ 該日原值無效（缺口保留，折線在此斷開）。"""

    obs_date: str
    value: float | None


@dataclass(frozen=True)
class SeriesResult:
    """單一序列的結果；所有日期與數字都只屬於這一條序列自己。

    - `own_window_start`：本序列自己 `slice_period` 的視窗起點（缺序列為 None）。
    - `last_obs_date`：本序列自己的最後有效觀測日（只要序列不是 missing 就有值，即使沒畫線）。
    - `base_raw`：基準日當天本序列的原值（只在畫線時有值）。
    - `points`：自基準日起到 `last_obs_date` 的歸一化點（含 None 缺口；基準日之前的點不輸出）；不畫線時為 ()。
    - `last_normalized`／`period_change`：本序列最後有效觀測日的歸一化值，與它減 `BASE_VALUE`；不畫線時為 None。
    """

    key: str
    status: str
    own_window_start: str | None
    last_obs_date: str | None
    base_raw: float | None
    points: tuple
    last_normalized: float | None
    period_change: float | None


@dataclass(frozen=True)
class NormalizedComparison:
    """比較結果。`status == STATUS_OK` ⇔ `base_date` 不為 None ⇔ 至少一條序列有線。

    - `mode`：`pair`（兩條都在）／`single`（缺一條）／`none`（兩條都缺）。
    - `window_start`：比較視窗起點（pair＝兩條起點較晚者；single＝那一條自己的起點）；算不出為 None。
    - `base_date`／`base_value`：只在 ok 時有值；`base_value` 恆為 `BASE_VALUE`。
    - `series`：依輸入順序的兩筆 `SeriesResult`。
    - `missing_keys`：缺的序列鍵（依輸入順序）。
    """

    status: str
    mode: str
    period: str
    window_start: str | None
    base_date: str | None
    base_value: int | None
    series: tuple
    missing_keys: tuple


# ─────────────────────────────── 輸入驗證 ───────────────────────────────


def _iso_day(value) -> str:
    """`datetime.date`（不收 `datetime.datetime`）或標準 `YYYY-MM-DD` 字串 → 標準字串；其餘大聲失敗。"""
    if isinstance(value, datetime):
        raise NormalizationInputError(f"obs_date must be a date, not a datetime: {value!r}")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            raise NormalizationInputError(f"obs_date is not an ISO date: {value!r}") from None
        if parsed.isoformat() != value:  # 只收標準 YYYY-MM-DD（periods 以字串比大小）
            raise NormalizationInputError(f"obs_date is not a canonical YYYY-MM-DD string: {value!r}")
        return value
    raise NormalizationInputError(f"obs_date must be a date or YYYY-MM-DD string: {value!r}")


def _validated(key: str, points) -> list:
    if not isinstance(points, (list, tuple)):
        raise NormalizationInputError(f"series {key!r}: points must be a list or tuple")
    seen = set()
    out = []
    for point in points:
        if not isinstance(point, dict) or "obs_date" not in point:
            raise NormalizationInputError(f"series {key!r}: each point must be a dict with 'obs_date'")
        day = _iso_day(point["obs_date"])
        if day in seen:
            raise NormalizationInputError(f"series {key!r}: duplicate obs_date {day}")
        seen.add(day)
        out.append({"obs_date": day, "value_num": point.get("value_num")})
    return out


# ─────────────────────────────── 計算 ───────────────────────────────


def _normalized_points(cleaned_window, base_date: str, base_raw: float) -> tuple:
    return tuple(
        NormalizedPoint(p["obs_date"], None if p["value_num"] is None else p["value_num"] / base_raw * BASE_VALUE)
        for p in cleaned_window if p["obs_date"] >= base_date
    )


def _drawn(key, own_start, last_obs, window_points, base_date, base_raw) -> SeriesResult:
    if not base_raw > 0:
        raise NormalizationInputError(f"series {key!r}: base value must be > 0, got {base_raw!r} on {base_date}")
    points = _normalized_points(window_points, base_date, base_raw)
    last = next(p for p in reversed(points) if p.value is not None)
    if last.obs_date != last_obs:  # 不變量：slice_period 的視窗終點即本序列最後有效觀測日
        raise RuntimeError(f"series {key!r}: last point {last.obs_date} != last valid obs {last_obs}")
    return SeriesResult(key, STATUS_OK, own_start, last_obs, base_raw, points, last.value, last.value - BASE_VALUE)


def _not_drawn(key, status, sliced=None) -> SeriesResult:
    own_start = sliced["window_start"] if sliced else None
    last_obs = sliced["last_obs"] if sliced else None
    return SeriesResult(key, status, own_start, last_obs, None, (), None, None)


def _result(status, mode, period, window_start, series, missing, base_date=None) -> NormalizedComparison:
    return NormalizedComparison(status, mode, period, window_start, base_date,
                                BASE_VALUE if base_date is not None else None, tuple(series), tuple(missing))


def normalize_pair(series, period: str) -> NormalizedComparison:
    """兩條日頻收盤序列在共同基準日歸一化為 `BASE_VALUE`（規則見模組 docstring 第 1～11 點）。

    - `series`：恰好兩個鍵的 dict，鍵為非空字串（例 `{"taiex": [...], "sp500": [...]}`），值為點序列或 None（缺）。
      結果的 `series` 依此 dict 的順序。
    - `period`：`periods.PERIODS` 之一，否則 `ValueError`。
    """
    if period not in PERIOD_MONTHS:
        raise ValueError(f"period must be one of {PERIODS}: {period!r}")
    if not isinstance(series, dict) or len(series) != 2:
        raise NormalizationInputError("series must be a dict with exactly two keys")
    keys = tuple(series)
    for key in keys:
        if not isinstance(key, str) or not key:
            raise NormalizationInputError(f"series key must be a non-empty string: {key!r}")

    sliced = {}
    for key in keys:
        points = series[key]
        if points is None:
            sliced[key] = None
            continue
        cut = slice_period(_validated(key, points), period)
        sliced[key] = None if cut["status"] not in (STATUS_OK, STATUS_INSUFFICIENT) else cut  # empty → 缺

    present = [k for k in keys if sliced[k] is not None]
    missing = [k for k in keys if sliced[k] is None]

    if not present:
        return _result(STATUS_BOTH_MISSING, MODE_NONE, period, None,
                       [_not_drawn(k, SERIES_MISSING) for k in keys], missing)

    if len(present) == 1:
        return _single(keys, sliced, present[0], missing, period)
    return _pair(keys, sliced, period)


def _single(keys, sliced, key, missing, period) -> NormalizedComparison:
    cut = sliced[key]

    def build(own):
        return [own if k == key else _not_drawn(k, SERIES_MISSING) for k in keys]

    if cut["status"] == STATUS_INSUFFICIENT:
        return _result(STATUS_INSUFFICIENT, MODE_SINGLE, period, cut["window_start"],
                       build(_not_drawn(key, STATUS_INSUFFICIENT, cut)), missing)
    valued = [p for p in cut["points"] if p["value_num"] is not None]
    if len(valued) < MIN_LINE_POINTS:
        return _result(STATUS_TOO_FEW_POINTS, MODE_SINGLE, period, cut["window_start"],
                       build(_not_drawn(key, STATUS_TOO_FEW_POINTS, cut)), missing)
    base_date, base_raw = valued[0]["obs_date"], valued[0]["value_num"]
    own = _drawn(key, cut["window_start"], cut["last_obs"], cut["points"], base_date, base_raw)
    return _result(STATUS_OK, MODE_SINGLE, period, cut["window_start"], build(own), missing, base_date)


def _pair(keys, sliced, period) -> NormalizedComparison:
    window_start = max(sliced[k]["window_start"] for k in keys)
    insufficient = [k for k in keys if sliced[k]["status"] == STATUS_INSUFFICIENT]
    if insufficient:
        return _result(STATUS_INSUFFICIENT, MODE_PAIR, period, window_start,
                       [_not_drawn(k, STATUS_INSUFFICIENT if k in insufficient else SERIES_WITHHELD, sliced[k])
                        for k in keys], [])

    windows = {k: [p for p in sliced[k]["points"] if p["obs_date"] >= window_start] for k in keys}
    valued = {k: {p["obs_date"]: p["value_num"] for p in windows[k] if p["value_num"] is not None} for k in keys}
    common = sorted(set(valued[keys[0]]) & set(valued[keys[1]]))
    if len(common) < MIN_LINE_POINTS:
        status = STATUS_NO_COMMON_BASE if not common else STATUS_TOO_FEW_COMMON_DAYS
        return _result(status, MODE_PAIR, period, window_start,
                       [_not_drawn(k, SERIES_WITHHELD, sliced[k]) for k in keys], [])

    base_date = common[0]
    results = [_drawn(k, sliced[k]["window_start"], sliced[k]["last_obs"], windows[k], base_date, valued[k][base_date])
               for k in keys]
    return _result(STATUS_OK, MODE_PAIR, period, window_start, results, [], base_date)
