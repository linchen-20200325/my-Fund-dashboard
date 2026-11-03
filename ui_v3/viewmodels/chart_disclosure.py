# -*- coding: utf-8 -*-
"""歸一化比較圖的揭露欄位（BL-0536-H3；`docs/v2/81` 第 2.3 節 G4、第 3.1 節「歸一化揭露」列；79 §4.4）。

客戶 2026-11-03（`DEC-2026-11-03-04`）：H3 至少揭露 基準日、基準值 100、資料頻率、缺值／缺序列處理。
本檔只放**代碼與事實**，不放任何畫面字樣 —— 81 第 3.1 節「字樣全部 PENDING」、第 8 節 T3「規則表缺歸一化揭露字樣」；
字樣由日後的 rendering 批經 Gate 取得，本檔不發明。

欄位語意（逐一對應客戶要求）：
- 基準日 → `base_date`（ISO `YYYY-MM-DD`；只在有線時有值，`status == "ok"` ⇔ 有基準日；一張圖至多一個基準日）。
- 基準值 100 → `base_value`（有基準日時恆為 `NORMALIZATION_BASE_VALUE`＝100，否則 None；與
  `services.v2_domain.normalization.BASE_VALUE` 相等由契約測試鎖 —— 本層不得 import services，故另存常數）。
- 資料頻率 → `frequency`（中性代碼；目前只有 `daily`：`normalize_pair` 的輸入定義就是日頻收盤）。
- 缺值處理 → `gap_policy`（中性代碼；目前只有 `no_fill`：缺口保留為 None、折線斷開，不補 0、不 ffill、不內插）。
- 缺序列處理 → `mode`（`pair`／`single`／`fallback`／`none`，與 L2 同值）＋ `series_issues`（沒畫線的序列鍵＋原因代碼）
  ＋ `fallback_reason`（只在 `fallback` 時有值）。只有 `mode == "pair"` 且有基準日才是比較（`comparable`）。
另帶 `status`（比較層狀態代碼，與 L2 同值；`pair` 兩條都不畫時真正原因只在這裡）與 `window_start`（基準所用的視窗起點）。

代碼值與 L2 的對照（`NORMALIZATION_MODES`、`COMPARISON_STATUSES`）由
`tests/ui_v3/test_ui_v3_chart_disclosure_contract.py` 對 `services.v2_domain.normalization` 鎖住。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional, Tuple

from ui_v3.viewmodels.common import require_key

# UI-13 A（`DEC-2026-11-02-07`）：歸一化基準值＝100（＝ services.v2_domain.normalization.BASE_VALUE；契約測試鎖）。
NORMALIZATION_BASE_VALUE = 100

MODE_PAIR = "pair"
MODE_SINGLE = "single"
MODE_FALLBACK = "fallback"
MODE_NONE = "none"
NORMALIZATION_MODES = (MODE_PAIR, MODE_SINGLE, MODE_FALLBACK, MODE_NONE)

COMPARISON_STATUS_OK = "ok"
COMPARISON_STATUS_BOTH_MISSING = "both_missing"
COMPARISON_STATUSES = (
    COMPARISON_STATUS_OK, "insufficient", "no_common_base", "too_few_common_days", "too_few_points",
    COMPARISON_STATUS_BOTH_MISSING,
)

FREQUENCY_DAILY = "daily"
FREQUENCIES = (FREQUENCY_DAILY,)

GAP_POLICY_NO_FILL = "no_fill"  # 缺口保留為 None、折線斷開；不補 0、不 ffill、不內插、不重抽樣
GAP_POLICIES = (GAP_POLICY_NO_FILL,)


def _iso_or_none(name: str, value: object) -> Optional[str]:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{name} 必須是 YYYY-MM-DD 字串或 None，收到 {value!r}")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"{name} 不是 ISO 日期：{value!r}") from None
    if parsed.isoformat() != value:
        raise ValueError(f"{name} 必須是標準 YYYY-MM-DD：{value!r}")
    return value


@dataclass(frozen=True)
class SeriesIssue:
    """沒畫線的一條序列：`series_key`（序列鍵）＋ `reason_code`（原因代碼；L2 的序列狀態原樣，或 adapter 的 `fetch_failed`）。"""

    series_key: str
    reason_code: str

    def __post_init__(self) -> None:
        require_key("series_key", self.series_key)
        require_key("reason_code", self.reason_code)


@dataclass(frozen=True)
class NormalizationDisclosure:
    """歸一化比較圖的揭露（代碼與事實；無畫面字樣）。不變量見模組 docstring 與 `__post_init__`。"""

    mode: str
    status: str
    base_date: Optional[str]
    window_start: Optional[str]
    base_value: Optional[int] = None
    frequency: str = FREQUENCY_DAILY
    gap_policy: str = GAP_POLICY_NO_FILL
    series_issues: Tuple[SeriesIssue, ...] = ()
    fallback_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if self.mode not in NORMALIZATION_MODES:
            raise ValueError(f"mode 必須在 {NORMALIZATION_MODES}，收到 {self.mode!r}")
        if self.status not in COMPARISON_STATUSES:
            raise ValueError(f"status 必須在 {COMPARISON_STATUSES}，收到 {self.status!r}")
        if self.frequency not in FREQUENCIES:
            raise ValueError(f"frequency 必須在 {FREQUENCIES}，收到 {self.frequency!r}")
        if self.gap_policy not in GAP_POLICIES:
            raise ValueError(f"gap_policy 必須在 {GAP_POLICIES}，收到 {self.gap_policy!r}")
        _iso_or_none("base_date", self.base_date)
        _iso_or_none("window_start", self.window_start)
        if not isinstance(self.series_issues, tuple) or not all(isinstance(i, SeriesIssue) for i in self.series_issues):
            raise TypeError("series_issues 必須是 SeriesIssue 的 tuple")
        keys = [i.series_key for i in self.series_issues]
        if len(set(keys)) != len(keys):
            raise ValueError("series_issues 的序列鍵不得重複")

        drawn = self.base_date is not None
        if drawn != (self.status == COMPARISON_STATUS_OK):
            raise ValueError("status == 'ok' ⇔ 有 base_date（有線才有基準日）")
        if drawn:
            if isinstance(self.base_value, bool) or self.base_value != NORMALIZATION_BASE_VALUE:
                raise ValueError(f"有基準日時 base_value 必須是 {NORMALIZATION_BASE_VALUE}，收到 {self.base_value!r}")
            if self.window_start is not None and self.base_date < self.window_start:
                raise ValueError("base_date 不得早於 window_start")
        elif self.base_value is not None:
            raise ValueError("沒有基準日時 base_value 必須是 None")

        if (self.mode == MODE_NONE) != (self.status == COMPARISON_STATUS_BOTH_MISSING):
            raise ValueError("mode == 'none' ⇔ status == 'both_missing'")
        if self.mode == MODE_PAIR and drawn:
            if self.series_issues:
                raise ValueError("pair 比較成立時不得有 series_issues")
        elif not self.series_issues:
            raise ValueError("沒有畫成比較時（缺序列、退回單序列、或不畫）必須以 series_issues 指明原因")
        if self.mode == MODE_FALLBACK:
            if self.fallback_reason is None:
                raise ValueError("mode == 'fallback' 必須帶 fallback_reason")
            require_key("fallback_reason", self.fallback_reason)
            if self.fallback_reason not in {i.reason_code for i in self.series_issues}:
                raise ValueError("fallback_reason 必須是某條被排除序列的 reason_code")
        elif self.fallback_reason is not None:
            raise ValueError("只有 mode == 'fallback' 可帶 fallback_reason")

    @property
    def comparable(self) -> bool:
        """只有兩條在同一基準日比較時為 True；single／fallback 的單線不是比較（81 第 9.1 節第 5 點）。"""
        return self.mode == MODE_PAIR and self.base_date is not None
