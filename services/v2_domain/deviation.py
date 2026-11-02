# -*- coding: utf-8 -*-
"""門檻偏離的純計算（原 `ui_v2/hld/logic.py::deviation_rows`／`_breaches` 的計算部分，2026-11-02 PORT）。

只搬「比較方向怎麼比、差額怎麼算、未列入原因怎麼去重」三件事；逐檔逐條走訪 ui_v2 的指標節點
（`_state` 中文狀態字面、`_raw`、`_fund_code`）與組畫面列（字樣、徽章）仍留在 `ui_v2/hld/logic.py`，
因為那是 ui_v2 的呈現形狀，不得帶進 L2（`docs/v2/80` 第 14 節 R1）。

比較方向用中性代碼：`DIRECTION_BELOW`（ui_v2 的「低於」）、`DIRECTION_ABOVE`（ui_v2 的「高於」）；
中文方向字面 → 代碼的對照住在 ui_v2 包裝裡。
"""

from __future__ import annotations

__all__ = (
    "DIRECTION_BELOW", "DIRECTION_ABOVE", "DIRECTIONS",
    "SKIP_KINDS", "SKIP_KINDS_YIELDING_TO_ERROR",
    "breaches", "deviation_delta", "apply_error_precedence",
)

DIRECTION_BELOW = "below"
DIRECTION_ABOVE = "above"
DIRECTIONS = (DIRECTION_BELOW, DIRECTION_ABOVE)

# 未列入原因的五類鍵（中性英文，與原 ui_v2 `deviation_rows` 的 `skipped` 鍵相同）。
SKIP_KINDS = ("missing", "missing_other", "error", "na", "not_ready")
# 取數失敗優先：同一檔只算「取數失敗」，不再同時算進下列四類（原 ui_v2 總管 2026-10-02 J1 裁定）。
SKIP_KINDS_YIELDING_TO_ERROR = ("missing", "missing_other", "na", "not_ready")


def breaches(direction, value, threshold) -> bool:
    """`value` 是否超出門檻：低於 → `value < threshold`；高於 → `value > threshold`；其他方向 → False。"""
    if direction == DIRECTION_BELOW:
        return value < threshold
    if direction == DIRECTION_ABOVE:
        return value > threshold
    return False


def deviation_delta(actual, threshold):
    """差額 ＝ 該檔的實際值減門檻值。"""
    return actual - threshold


def apply_error_precedence(skipped) -> dict:
    """就地把「取數失敗」那幾檔從其他四類拿掉（集合差）；回同一個 dict。"""
    for kind in SKIP_KINDS_YIELDING_TO_ERROR:
        skipped[kind] -= skipped["error"]
    return skipped
