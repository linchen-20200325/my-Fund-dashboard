# -*- coding: utf-8 -*-
"""`ActionSlot`：行動欄位的**佔位**（80 第 2 節「未來接口的佔位規則」、第 6 節；67 第 2 節六個行動詞）。

⛔ 本批不實作 Risk Cap、System Action State、Decision Digest、OneBrain（`DEC-2026-10-26-01`；79 §6.1）。
因此在 Phase 7 Gate 通過前：
- `state` 只能是 None（不顯示）或「無法判定」；
- `source_ref` 必為 None（行動來源只能是 System Action State，現在不存在，不得由 view model 推出）。
Gate 通過後，由持有該 Gate 的批次**有意識地**把 `ACTION_SLOT_SOURCES_ENABLED` 改為 True 並改測試；
詞彙驗證（六個詞）不隨 Gate 改變。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from shared.ui_semantics import rules as _rules
from ui_v3.viewmodels.common import optional_text, require_key

# 67 第 2 節六個行動詞（語意邊界 SSOT）。逐字，不增不減；單一來源 `shared/ui_semantics/rules.py::ACTION_WORDS`（批 2b）。
ACTION_VOCABULARY = _rules.ACTION_WORDS
(
    ACTION_CONTINUE,
    ACTION_WATCH,
    ACTION_REDUCE_EXPOSURE,
    ACTION_TRIM,
    ACTION_COMPARE_ALTERNATIVE,
    ACTION_UNDETERMINED,
) = ACTION_VOCABULARY

# Phase 7（System Action State 存在）之前恆為 False。
ACTION_SLOT_SOURCES_ENABLED = False


@dataclass(frozen=True)
class ActionSlot:
    """`state`：六詞之一或 None（不顯示）；`reason`：原因鍵；`source_ref`：System Action State 的參照。

    無法判定必須說明缺什麼（67 §2.6），故 `state="無法判定"` 必帶 `reason`（鍵值，非自由文字）。
    """

    state: Optional[str] = None
    reason: Optional[str] = None
    source_ref: Optional[str] = None

    def __post_init__(self) -> None:
        if self.state is not None and self.state not in ACTION_VOCABULARY:
            raise ValueError(f"ActionSlot.state 只能是 {ACTION_VOCABULARY} 或 None，收到 {self.state!r}")
        if self.reason is not None:
            require_key("reason", self.reason)
        optional_text("source_ref", self.source_ref)
        if self.state is None:
            if self.reason is not None or self.source_ref is not None:
                raise ValueError("不顯示（state=None）時不得帶 reason／source_ref")
            return
        if not ACTION_SLOT_SOURCES_ENABLED:
            if self.state != ACTION_UNDETERMINED:
                raise ValueError("Phase 7 前 ActionSlot 只能是「無法判定」或不顯示；不得由 view model 推出行動")
            if self.source_ref is not None:
                raise ValueError("Phase 7 前沒有 System Action State，不得帶 source_ref")
        if self.state == ACTION_UNDETERMINED and self.reason is None:
            raise ValueError("「無法判定」必須說明缺什麼（reason）")
        if self.state != ACTION_UNDETERMINED and self.source_ref is None:
            raise ValueError("行動詞必須帶 source_ref（來源只能是 System Action State）")

    @property
    def visible(self) -> bool:
        return self.state is not None
