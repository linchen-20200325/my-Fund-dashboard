# -*- coding: utf-8 -*-
"""全站共用 Navigation Shell 的 view model（BL-0536 Shell 批；純 Python、frozen、建構時驗證；無 streamlit／services）。

只放代碼與事實，不放畫面字樣（暫時字樣在 `preview_wording.py`）：資料狀態只有三個層級（齊全／部分／全缺）加計數，
最後更新時間是**取得時間**（`fetched_at`，不是資料日）。**沒有任何推估**：沒有取得時間就是 None（呈現成缺資料），不補、不猜。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

LEVEL_OK = "ok"
LEVEL_PARTIAL = "partial"
LEVEL_NONE = "none"
LEVELS = (LEVEL_OK, LEVEL_PARTIAL, LEVEL_NONE)

REFRESH_NOT_WIRED = "refresh_not_wired"   # 尚未接上正式 refresh 流程（見 docs/v2/80 第 17 節）
REFRESH_REASONS = (REFRESH_NOT_WIRED,)


@dataclass(frozen=True)
class ShellStatus:
    """Status Bar／Sidebar 資料狀態區共用的一份資料。

    - `level`：`ok`＝全部主要序列取得；`partial`＝至少一項取得、至少一項沒有；`none`＝一項也沒取得。
    - `ok_count`／`total`：主要序列取得數／總數；`failed_count`：其中取數失敗（不是缺資料）的項數。
    - `last_fetched_at`：各主要序列取得時間（帶時區的 ISO 字串）中最晚的一個；沒有就是 None。
    - `refresh_available`：更新資料 CTA 是否可用；不可用時必帶 `refresh_reason_code`。
    """

    level: str
    ok_count: int
    total: int
    failed_count: int
    last_fetched_at: Optional[str]
    refresh_available: bool
    refresh_reason_code: Optional[str]

    def __post_init__(self) -> None:
        if self.level not in LEVELS:
            raise ValueError(f"level 必須在 {LEVELS}，收到 {self.level!r}")
        for name in ("ok_count", "total", "failed_count"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} 必須是非負 int")
        if self.total == 0 or self.ok_count > self.total or self.failed_count > self.total - self.ok_count:
            raise ValueError("計數不一致（total>0、ok≤total、failed≤非 ok）")
        expected = LEVEL_OK if self.ok_count == self.total else LEVEL_NONE if self.ok_count == 0 else LEVEL_PARTIAL
        if self.level != expected:
            raise ValueError(f"level={self.level} 與計數 {self.ok_count}/{self.total} 不一致（應為 {expected}）")
        if self.last_fetched_at is not None and not str(self.last_fetched_at).strip():
            raise ValueError("last_fetched_at 不得是空字串（沒有就是 None）")
        if self.refresh_available and self.refresh_reason_code is not None:
            raise ValueError("可用的 CTA 不得帶 refresh_reason_code")
        if not self.refresh_available and self.refresh_reason_code not in REFRESH_REASONS:
            raise ValueError(f"不可用的 CTA 必須帶 refresh_reason_code ∈ {REFRESH_REASONS}")
