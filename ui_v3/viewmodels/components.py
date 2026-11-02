# -*- coding: utf-8 -*-
"""元件級 view model（80 第 6 節）。純 Python、frozen、建構時驗證；不 import streamlit／services。

每個元件都在建構時拒絕違反契約的組合（Missing 帶數值、缺 provenance、自由文字狀態……），
讓「從 UI 狀態反推事實」「Missing 補 0」這類錯誤無法被建出來，而不是靠下游記得檢查。

⚠️ 本層沒有格式化邏輯：`display_value` 由呼叫端（日後的 view model builder）提供，
本層只驗證它與 `value` 的一致性（None ↔ `◇ 資料未備`）。規則資料表住 `shared/ui_semantics/`（批 2b）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple, Union

from ui_v3.viewmodels.common import (
    FactMeta,
    MISSING_TEXT,
    STATUS_FAILED,
    STATUS_MISSING,
    STATUS_OK,
    ValueFacts,
    optional_text,
    require_key,
    require_number_or_none,
    require_text,
)

# 80 第 5 節 status chips 的 kind。字樣由規則表依 kind 給，這裡不放字樣：kind → 規則鍵的對照住
# `shared/ui_semantics/rules.py::CHIP_KIND_TO_KEY`（批 2b；兩邊一致由 `tests/ui_v3/test_ui_v3_semantics_rules.py` 鎖）。
CHIP_KINDS = ("attention", "missing", "undetermined", "failed", "stale", "neutral")
CHART_PERIODS = ("3M", "6M", "1Y", "3Y")
DEFAULT_CHART_PERIOD = "1Y"
MAX_CHART_SERIES = 3
MAX_CHART_CHIPS = 3


@dataclass(frozen=True)
class StatusChip:
    """狀態 chip：只接受規則表 kind 與鍵值 `label_key`，不接受自由文字狀態。"""

    kind: str
    label_key: str

    def __post_init__(self) -> None:
        if self.kind not in CHIP_KINDS:
            raise ValueError(f"StatusChip.kind 必須在 {CHIP_KINDS}，收到 {self.kind!r}")
        require_key("label_key", self.label_key)


@dataclass(frozen=True)
class MetricCard:
    """指標卡：`value` 為 None → `display_value` 必為 `◇ 資料未備`（不顯示 0）；有值 → 不得顯示缺值字樣。"""

    title: str
    facts: ValueFacts
    display_value: str
    delta: Optional[ValueFacts] = None

    def __post_init__(self) -> None:
        require_text("title", self.title)
        require_text("display_value", self.display_value)
        if not isinstance(self.facts, ValueFacts):
            raise TypeError("facts 必須是 ValueFacts")
        if self.delta is not None and not isinstance(self.delta, ValueFacts):
            raise TypeError("delta 必須是 ValueFacts 或 None")
        if self.facts.value is None:
            if self.display_value != MISSING_TEXT:
                raise ValueError(f"value 為 None 時 display_value 必須是 {MISSING_TEXT!r}（不得顯示 0 或其他值）")
        elif self.display_value == MISSING_TEXT:
            raise ValueError("有 value 時 display_value 不得是缺值字樣")


@dataclass(frozen=True)
class ChartPoint:
    """圖點：`date`（ISO 字串，嚴格遞增由 ChartSeries 驗）＋ value（None＝缺段，斷線不補、不畫零）。"""

    date: str
    value: Optional[float]

    def __post_init__(self) -> None:
        require_text("date", self.date)
        require_number_or_none("value", self.value)


@dataclass(frozen=True)
class ChartSeries:
    """圖卡的一條序列：各自帶共同欄位（`FactMeta`）。

    - `missing`／`failed` → 不得有任何非 None 的點。
    - `ok` → 至少一個非 None 的點。
    - 點的日期須嚴格遞增（不重複、不亂序；對應 §4.2 時序不變量）。
    """

    label: str
    meta: FactMeta
    points: Tuple[ChartPoint, ...] = ()

    def __post_init__(self) -> None:
        require_text("label", self.label)
        if not isinstance(self.meta, FactMeta):
            raise TypeError("meta 必須是 FactMeta")
        if not isinstance(self.points, tuple) or not all(isinstance(p, ChartPoint) for p in self.points):
            raise TypeError("points 必須是 ChartPoint 的 tuple")
        dates = [p.date for p in self.points]
        if any(b <= a for a, b in zip(dates, dates[1:])):
            raise ValueError("points 的 date 必須嚴格遞增（不得重複或亂序）")
        has_value = any(p.value is not None for p in self.points)
        if self.meta.is_missing and has_value:
            raise ValueError("Missing／failed 的序列不得攜帶數值點")
        if self.meta.status == STATUS_OK and not has_value:
            raise ValueError("status=ok 的序列至少要有一個數值點；缺值請用 status=missing")


@dataclass(frozen=True)
class EvidenceItem:
    """依據項。`rule_ref` 只有正式規則存在才填；不得自造 Rule ID。

    ⚠️ 本層無法驗證 rule_ref 是否存在於正式規則登錄（view model 不得 import 下層）；
    該驗證屬 adapters／批 2。本層只擋空字串；批 1 的 fixtures 一律不填 rule_ref。
    """

    label: str
    rule_ref: Optional[str] = None

    def __post_init__(self) -> None:
        require_text("label", self.label)
        optional_text("rule_ref", self.rule_ref)


@dataclass(frozen=True)
class MissingItem:
    """缺什麼：presentation 恆為 `◇ 資料未備`＋原因（原因鍵 `reason_code`）。"""

    what: str
    reason_code: str
    PRESENTATION = MISSING_TEXT  # class 常數（無型別註記 → 不是 dataclass 欄位）

    def __post_init__(self) -> None:
        require_text("what", self.what)
        require_key("reason_code", self.reason_code)


@dataclass(frozen=True)
class ProvenanceTag:
    """血緣標籤：完整（`source` 與 `as_of` 皆有）或明確缺值（`missing_reason_code`），二擇一。

    完整時不得同時宣稱缺值；缺值時 `fallback_used` 必為 False（沒有資料就沒有備援可言）。
    """

    source: Optional[str] = None
    as_of: Optional[str] = None
    fallback_used: bool = False
    missing_reason_code: Optional[str] = None

    def __post_init__(self) -> None:
        optional_text("source", self.source)
        optional_text("as_of", self.as_of)
        if not isinstance(self.fallback_used, bool):
            raise TypeError("fallback_used 必須是 bool")
        complete = self.source is not None and self.as_of is not None
        if self.missing_reason_code is not None:
            require_key("missing_reason_code", self.missing_reason_code)
            if complete:
                raise ValueError("source／as_of 皆齊全時不得同時宣稱缺值")
            if self.fallback_used:
                raise ValueError("缺值的 ProvenanceTag 不得標 fallback_used")
        elif not complete:
            raise ValueError("ProvenanceTag 需要 source 與 as_of，或明確的 missing_reason_code")


ChartDetail = Union[EvidenceItem, MissingItem, ProvenanceTag]


@dataclass(frozen=True)
class ChartCard:
    """圖卡：標題＋≤3 chips＋≤3 series＋period＋detail（收合內容）。缺段斷線不補（由 ChartPoint None 表達）。"""

    title: str
    series: Tuple[ChartSeries, ...]
    chips: Tuple[StatusChip, ...] = ()
    period: str = DEFAULT_CHART_PERIOD
    detail: Tuple[ChartDetail, ...] = ()

    def __post_init__(self) -> None:
        require_text("title", self.title)
        if self.period not in CHART_PERIODS:
            raise ValueError(f"period 必須在 {CHART_PERIODS}，收到 {self.period!r}")
        if not isinstance(self.series, tuple) or not all(isinstance(s, ChartSeries) for s in self.series):
            raise TypeError("series 必須是 ChartSeries 的 tuple")
        if len(self.series) > MAX_CHART_SERIES:
            raise ValueError(f"series 至多 {MAX_CHART_SERIES} 條")
        if not isinstance(self.chips, tuple) or not all(isinstance(c, StatusChip) for c in self.chips):
            raise TypeError("chips 必須是 StatusChip 的 tuple")
        if len(self.chips) > MAX_CHART_CHIPS:
            raise ValueError(f"chips 至多 {MAX_CHART_CHIPS} 個")
        if not isinstance(self.detail, tuple) or not all(
            isinstance(d, (EvidenceItem, MissingItem, ProvenanceTag)) for d in self.detail
        ):
            raise TypeError("detail 只能含 EvidenceItem／MissingItem／ProvenanceTag")
