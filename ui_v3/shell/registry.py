# -*- coding: utf-8 -*-
"""五頁登錄表：頁序、頁名、是否掛載（純資料；不 import streamlit、不 import 任何頁）。

依據：80 第 7 節（五頁）、`DEC-2026-10-26-01`／`DEC-2026-10-29-06`（五頁 IA、不得有第六頁）、
`DEC-2026-10-29-07`（🤖 在 Phase 7 前不掛導覽）、`DEC-2026-10-27-10`／`-12`（不做空殼）。

- 頁序：🌍 → 💼 → 🔍 → 🤖 → ⚙️；頁名逐字與 `ui_v2/app_preview.py::PAGES` 的四頁一致（守衛：
  `tests/ui_v3/test_ui_v3_page_registry_guard.py` 以 AST 讀 ui_v2 檔，不 import）。
- url_path 沿用 ui_v2 慣例（mkt／ast／exp／set；🤖 取 `ai`，80 第 4.2 節建議）。
- **`registered` 是「已有核准 wireframe 且已實作的頁」**。批 1 沒有任何一頁，所以五頁皆 False；
  逐頁 wireframe 經客戶核准、實作後，由該批**有意識地**把對應頁改為 True 並同步改守衛。
- 🤖 `ai`：Phase 7（OneBrain）之前**禁止** registered=True（建構時就擋）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

REASON_WIREFRAME_PENDING = "wireframe_not_approved"  # 逐頁 wireframe 尚未經客戶核准／尚未實作
REASON_PHASE7 = "phase7_onebrain_not_enabled"  # DEC-2026-10-29-07：Phase 7 才加入導覽
_REASONS = (REASON_WIREFRAME_PENDING, REASON_PHASE7)

AI_SLUG = "ai"


@dataclass(frozen=True)
class PageSlot:
    """IA 的一個位置。`registered=False` 時必須說明原因；`ai` 不得在 Phase 7 前 registered。"""

    slug: str
    title: str
    registered: bool = False
    unregistered_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.slug or not self.title:
            raise ValueError("slug 與 title 不得為空")
        if self.registered and self.unregistered_reason is not None:
            raise ValueError("已掛載的頁不得帶 unregistered_reason")
        if not self.registered and self.unregistered_reason not in _REASONS:
            raise ValueError(f"未掛載的頁必須帶 unregistered_reason ∈ {_REASONS}")
        if self.slug == AI_SLUG and self.registered:
            raise ValueError("🤖 頁在 Phase 7（OneBrain Gate）前不得掛導覽（DEC-2026-10-29-07）")
        if self.slug == AI_SLUG and self.unregistered_reason != REASON_PHASE7:
            raise ValueError("🤖 頁的未掛載原因必須是 Phase 7")


# 頁序與頁名：80 第 7 節；與 ui_v2 預覽導覽的四頁逐字一致。
IA_PAGES: Tuple[PageSlot, ...] = (
    PageSlot("mkt", "🌍 市場與趨勢", False, REASON_WIREFRAME_PENDING),
    PageSlot("ast", "💼 我的資產", False, REASON_WIREFRAME_PENDING),
    PageSlot("exp", "🔍 找基金", False, REASON_WIREFRAME_PENDING),
    PageSlot(AI_SLUG, "🤖 AI 投資總結", False, REASON_PHASE7),
    PageSlot("set", "⚙️ 設定", False, REASON_WIREFRAME_PENDING),
)


def registered_pages() -> Tuple[PageSlot, ...]:
    """目前實際掛載進導覽的頁（保持 IA 順序）。批 1 恆為空 tuple。"""
    return tuple(p for p in IA_PAGES if p.registered)


class PreviewNotReady(RuntimeError):
    """沒有任何已核准且已實作的頁時，preview 入口拒絕啟動（Fail Loud；不畫空殼）。"""


def assert_preview_ready() -> Tuple[PageSlot, ...]:
    pages = registered_pages()
    if not pages:
        raise PreviewNotReady(
            "ui_v3 preview 尚無任何已核准並實作的頁（批 1 只有骨架）；依「不做空殼」，"
            "入口不註冊任何頁、也不渲染任何使用者可見內容。"
        )
    return pages
