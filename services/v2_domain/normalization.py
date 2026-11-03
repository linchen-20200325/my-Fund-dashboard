# -*- coding: utf-8 -*-
"""🌍 TAIEX vs S&P 500 歸一化比較（BL-0536-H1＋H1b；L2 純計算，新寫，不沿用 Old UI `services/benchmark_compare.py`）。

依據（客戶裁示，逐字檔 `docs/evidence/decisions/2026-11-03_mkt_wireframe_ruling.md`；`docs/DECISIONS.md`
`DEC-2026-11-03-01`；`docs/v2/81_new_ui2_wireframe_01_market.md` 第 7 節 Q2-a／b／c A、第 4 節與 4.1 節情境表）；
H1b（2026-11-03 A2／B2／C2，`DEC-2026-11-03-04`，逐字檔
`docs/evidence/decisions/2026-11-03_normalization_abc_and_min_cost_rule.md`）改寫第 4、7 點並新增第 12、13 點：

1. 輸入：兩條日頻收盤序列（各自 `[{"obs_date", "value_num"}, ...]`）＋ 期間（`periods.PERIODS`）。
   無效值（None／NaN／±inf／bool／非數字）一律當缺口（None），不補 0、不 ffill、不內插、不重抽樣
   （沿用 `periods.clean_points`；`CLAUDE.md` §1、§4.5）。
2. 各序列的視窗起點＝該序列自己的 `periods.slice_period` 起點（以該序列最後一筆有值觀測日往回推
   `PERIOD_MONTHS` 個日曆月；本檔不另寫月份算術）。
3. 比較視窗起點 W＝兩條起點中**較晚者**（Q2-a A）。
4. 涵蓋判定（A2，H1b 改寫）：pair 模式以**比較視窗起點 W** 判定，不以各序列自己的起點判定 ——
   序列涵蓋比較視窗 ⇔ 它在 W 當日或之前有一筆有效觀測（歷史確實延伸到 W；W 當天沒有觀測只是無觀測日，
   不是歷史不足）；否則該序列 `insufficient`。不設 ±N 日容忍、不用交易日曆，只看資料本身。
   單序列模式（缺一條或退回單序列）的比較視窗就是那一條自己的視窗，同一條規則（＝ `slice_period` 既有判定）。
   殘留邊界（待客戶確認，見 `docs/v2/81` 第 9 節 H1b 註記）：W 是週末／休市日、而序列有史以來第一筆觀測恰是
   其後第一個交易日 —— 單憑資料無法證明它涵蓋（需要日曆或容忍才能證明），本規則判 `insufficient`。
5. 基準日＝比較視窗起點當日或之後、兩條**都有**有效收盤的第一天；兩條在該日都等於 `BASE_VALUE`
   （＝ 原值 / 基準日原值 × 100）。不得以兩條各自的首筆為基準（Q2-a C 未採；客戶「不得用兩條各自不同日期的首筆都設為 100」）。
6. 終點：各序列畫到**自己的**最後有效觀測日（Q2-b A）；每條結果各自帶 `last_obs_date`、`last_normalized`、
   `period_change`（＝ `last_normalized - BASE_VALUE`），三者都指同一條序列自己的那一天。
   本模組**刻意不提供**任何「共同終點日」欄位，避免讓人以為兩條最後一天相同。
7. 比較視窗內兩條沒有任何共同有效日 → `no_common_base`；只有一天 → `too_few_common_days`
   （Q2-a A「視窗內共同有值日不足 2 天 → 無法判定（一個點畫不成線）」）。H1b（C2）：若恰有一條在比較視窗內
   有效觀測不足 2 筆（＝它的最後有效觀測日早於 W，或 W 之後只剩一筆就停了；即停更），退回單序列模式
   （第 12 點），停更那條標該代碼；兩條都夠 2 筆（只是日期錯開）或兩條都不夠 → 兩條皆 `withheld`、不畫線。
8. 缺一條（呼叫端傳 None，或整條沒有任何有效值）→ 單序列模式（Q2-c A，`mode == single`）：另一條照算，
   基準日改取該條自己視窗內的第一筆有效值；`missing_keys` 指明缺哪一條；有效點不足 2 個 → `too_few_points`。
   兩條都缺 → `both_missing`，不畫線。
9. 格式錯誤一律大聲失敗（`NormalizationInputError`，`ValueError` 子類）：同一序列內 `obs_date` 重複（不去重）、
   `obs_date` 不是日期（只收 `datetime.date`（不收 `datetime.datetime`）或標準 `YYYY-MM-DD` 字串）、
   點不是 dict、序列不是 list／tuple、基準日原值 ≤ 0（無法當除數）。
   未排序的輸入照 `periods.clean_points` 既有行為先排序（與 ui_v2 期間切片一致）。
10. 回傳 frozen dataclass；狀態一律中性英文代碼，不含任何畫面字樣（`CLAUDE.md` §8.2 L2；中文字樣在呈現層）；
    浮點數不四捨五入。日期一律以 `YYYY-MM-DD` 字串回傳（與 `periods.slice_period` 一致）。
11. 不含任何門檻、新鮮度判斷或狀態詞；VIX／殖利率不在本模組射程。
12. 退回單序列（B2／C2，H1b 新增，`mode == fallback`）：兩條都在、但不能比較，且原因只落在其中一條
    （該條比較視窗不足＝B2；該條停更＝C2）→ 另一條照第 8 點的單序列規則畫（自己的視窗、自己視窗內首筆有效值＝100；
    與「那一條傳 None」時逐欄相同，被排除那條的資料不影響它）；被排除那條不出線、`status` 標真正原因
    （`insufficient`／`no_common_base`／`too_few_common_days`），`fallback_reason` 同此代碼。
    不補值、不補 0、不假造基準；結果只有一條線、只有一個基準日，不會出現兩個不同日期的 100。
13. 模式一律明示：`pair`＝兩條在同一基準日比較；`single`＝缺一條；`fallback`＝兩條都在但不比較、至多畫一條；
    `none`＝兩條都缺。呈現層只有在 `mode == pair` 且 `status == ok` 時才可呈現為比較。

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
    clean_points,
    slice_period,
)

__all__ = (
    "BASE_VALUE", "MIN_LINE_POINTS",
    "STATUS_OK", "STATUS_INSUFFICIENT", "STATUS_NO_COMMON_BASE", "STATUS_TOO_FEW_COMMON_DAYS",
    "STATUS_TOO_FEW_POINTS", "STATUS_BOTH_MISSING",
    "SERIES_MISSING", "SERIES_WITHHELD",
    "MODE_PAIR", "MODE_SINGLE", "MODE_FALLBACK", "MODE_NONE",
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

# 序列層另有的兩個狀態（`SeriesResult.status`；其餘沿用 ok／insufficient／too_few_points，
# 退回單序列時被排除那條另可為 no_common_base／too_few_common_days，見模組 docstring 第 12 點）。
SERIES_MISSING = "missing"      # 呼叫端傳 None，或整條沒有任何有效值
SERIES_WITHHELD = "withheld"    # 本序列涵蓋比較視窗，但整個比較不可畫、且不退回單序列（兩條日期錯開等），故不出線

MODE_PAIR = "pair"              # 兩條在同一基準日比較
MODE_SINGLE = "single"          # 缺一條（Q2-c A）
MODE_FALLBACK = "fallback"      # 兩條都在但不比較，至多畫一條（H1b B2／C2）
MODE_NONE = "none"              # 兩條都缺


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

    - `mode`：`pair`（兩條在同一基準日比較）／`single`（缺一條）／`fallback`（兩條都在但不比較，至多畫一條）／
      `none`（兩條都缺）。只有 `pair` 且 `ok` 才是比較；`single`／`fallback` 的 `ok` 只有一條線。
    - `window_start`：基準所用的視窗起點（pair＝兩條起點較晚者；single／fallback＝被畫那一條自己的起點）；算不出為 None。
    - `base_date`／`base_value`：只在 ok 時有值；`base_value` 恆為 `BASE_VALUE`。
    - `series`：依輸入順序的兩筆 `SeriesResult`。
    - `missing_keys`：缺的序列鍵（依輸入順序）。
    - `fallback_reason`：只在 `fallback` 時有值＝被排除那條的 `status`（`insufficient`／`no_common_base`／
      `too_few_common_days`）；其餘模式為 None。
    """

    status: str
    mode: str
    period: str
    window_start: str | None
    base_date: str | None
    base_value: int | None
    series: tuple
    missing_keys: tuple
    fallback_reason: str | None


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


def _result(status, mode, period, window_start, series, missing, base_date=None,
            fallback_reason=None) -> NormalizedComparison:
    return NormalizedComparison(status, mode, period, window_start, base_date,
                                BASE_VALUE if base_date is not None else None, tuple(series), tuple(missing),
                                fallback_reason)


def normalize_pair(series, period: str) -> NormalizedComparison:
    """兩條日頻收盤序列在共同基準日歸一化為 `BASE_VALUE`（規則見模組 docstring 第 1～13 點）。

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

    sliced, cleaned = {}, {}
    for key in keys:
        points = series[key]
        if points is None:
            sliced[key] = None
            continue
        validated = _validated(key, points)
        cut = slice_period(validated, period)
        sliced[key] = None if cut["status"] not in (STATUS_OK, STATUS_INSUFFICIENT) else cut  # empty → 缺
        cleaned[key] = clean_points(validated)

    present = [k for k in keys if sliced[k] is not None]
    missing = [k for k in keys if sliced[k] is None]

    if not present:
        return _result(STATUS_BOTH_MISSING, MODE_NONE, period, None,
                       [_not_drawn(k, SERIES_MISSING) for k in keys], missing)

    if len(present) == 1:
        other = _not_drawn(missing[0], SERIES_MISSING)
        return _single(keys, sliced, present[0], period, other, MODE_SINGLE, missing)
    return _pair(keys, sliced, cleaned, period)


def _single(keys, sliced, key, period, other, mode, missing=(), fallback_reason=None) -> NormalizedComparison:
    """單序列：`key` 依自己的 `slice_period` 視窗畫（涵蓋＝自身起點當日或之前有有效觀測），`other` 為另一條的結果。"""
    cut = sliced[key]

    def build(own):
        return [own if k == key else other for k in keys]

    def fail(status):
        return _result(status, mode, period, cut["window_start"], build(_not_drawn(key, status, cut)), missing,
                       fallback_reason=fallback_reason)

    if cut["status"] == STATUS_INSUFFICIENT:
        return fail(STATUS_INSUFFICIENT)
    valued = [p for p in cut["points"] if p["value_num"] is not None]
    if len(valued) < MIN_LINE_POINTS:
        return fail(STATUS_TOO_FEW_POINTS)
    base_date, base_raw = valued[0]["obs_date"], valued[0]["value_num"]
    own = _drawn(key, cut["window_start"], cut["last_obs"], cut["points"], base_date, base_raw)
    return _result(STATUS_OK, mode, period, cut["window_start"], build(own), missing, base_date, fallback_reason)


def _fallback(keys, sliced, excluded, reason, period) -> NormalizedComparison:
    """B2／C2：排除 `excluded`（標 `reason`），另一條退回單序列（與另一條傳 None 時同一套規則）。"""
    kept = next(k for k in keys if k != excluded)
    other = _not_drawn(excluded, reason, sliced[excluded])
    return _single(keys, sliced, kept, period, other, MODE_FALLBACK, fallback_reason=reason)


def _pair(keys, sliced, cleaned, period) -> NormalizedComparison:
    window_start = max(sliced[k]["window_start"] for k in keys)
    # A2：涵蓋＝比較視窗起點當日或之前有有效觀測（不是各自起點、不設容忍、不用日曆）。
    short = [k for k in keys if sliced[k]["first_obs"] > window_start]
    if len(short) == len(keys):
        return _result(STATUS_INSUFFICIENT, MODE_PAIR, period, window_start,
                       [_not_drawn(k, STATUS_INSUFFICIENT, sliced[k]) for k in keys], [])
    if short:  # B2
        return _fallback(keys, sliced, short[0], STATUS_INSUFFICIENT, period)

    windows = {k: [p for p in cleaned[k] if window_start <= p["obs_date"] <= sliced[k]["last_obs"]] for k in keys}
    valued = {k: {p["obs_date"]: p["value_num"] for p in windows[k] if p["value_num"] is not None} for k in keys}
    common = sorted(set(valued[keys[0]]) & set(valued[keys[1]]))
    if len(common) < MIN_LINE_POINTS:
        status = STATUS_NO_COMMON_BASE if not common else STATUS_TOO_FEW_COMMON_DAYS
        stopped = [k for k in keys if len(valued[k]) < MIN_LINE_POINTS]   # C2：比較視窗內有效觀測不足 2 筆＝停更
        if len(stopped) == 1:
            return _fallback(keys, sliced, stopped[0], status, period)
        return _result(status, MODE_PAIR, period, window_start,
                       [_not_drawn(k, SERIES_WITHHELD, sliced[k]) for k in keys], [])

    base_date = common[0]
    results = [_drawn(k, sliced[k]["window_start"], sliced[k]["last_obs"], windows[k], base_date, valued[k][base_date])
               for k in keys]
    return _result(STATUS_OK, MODE_PAIR, period, window_start, results, [], base_date)
