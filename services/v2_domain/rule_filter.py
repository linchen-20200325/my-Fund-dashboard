# -*- coding: utf-8 -*-
"""條件篩選的純計算（原 `ui_v2/exp/logic.py` 的 `is_missing`、`_finite_number`、`_compare`、`compare_tristate`、
`rule_is_effective`、`apply_rules_tristate`，2026-11-02 PORT，判定一字未改）。

三態語意（客戶 2026-10-13 裁示）：欄位值缺 → **無法判定**（不算符合、也不排除）；不得把未知當成不符合，
也不得當成符合。

呈現分離（`docs/v2/80` 第 14 節 R1）：
- 比較方向用中性代碼（`OP_*`）；ui_v2 的中文方向字面（等於／不等於／大於／小於／早於或等於／晚於）
  → 代碼的對照住在 ui_v2 包裝裡；
- 無法判定的原因回中性代碼（`UNDET_*`），不回中文原因字；ui_v2 包裝換回原字；
- 比較撞到沒訂的情形丟 `UncomparableValues`（帶 `kind` 代碼），ui_v2 包裝換回原本的
  `UnspecifiedComparison` 與原字訊息。
"""

from __future__ import annotations

import decimal

__all__ = (
    "OP_EQ", "OP_NE", "OP_GT", "OP_LT", "OP_ON_OR_BEFORE", "OP_AFTER",
    "OPERATOR_CODES", "NUMERIC_OPERATOR_CODES",
    "UNDET_MISSING", "UNDET_LEFT_NOT_NUMBER", "UNDET_RIGHT_NOT_NUMBER",
    "UNCOMPARABLE_LEFT_MISSING", "UNCOMPARABLE_NOT_NUMBER", "UNCOMPARABLE_UNKNOWN_OPERATOR",
    "UncomparableValues", "is_missing", "finite_number", "compare_values", "compare_tristate",
    "rule_is_effective", "apply_rules_tristate",
)

# 比較方向（中性代碼；順序與 ui_v2 `KNOWN_OPERATORS` 一一對應）。
OP_EQ = "eq"                    # 字串相等
OP_NE = "ne"                    # 字串不相等
OP_GT = "gt"                    # 數值大於
OP_LT = "lt"                    # 數值小於
OP_ON_OR_BEFORE = "on_or_before"  # 字串（ISO 日期）小於或等於
OP_AFTER = "after"              # 字串（ISO 日期）大於
OPERATOR_CODES = (OP_EQ, OP_NE, OP_GT, OP_LT, OP_ON_OR_BEFORE, OP_AFTER)
NUMERIC_OPERATOR_CODES = (OP_GT, OP_LT)

# 無法判定的原因（中性代碼）。
UNDET_MISSING = "missing"                    # 欄位值缺
UNDET_LEFT_NOT_NUMBER = "left_not_number"    # 數值比較的欄位值不是有限數
UNDET_RIGHT_NOT_NUMBER = "right_not_number"  # 數值比較的條件數值不是有限數

# `UncomparableValues.kind`。
UNCOMPARABLE_LEFT_MISSING = "left_missing"
UNCOMPARABLE_NOT_NUMBER = "not_number"
UNCOMPARABLE_UNKNOWN_OPERATOR = "unknown_operator"


class UncomparableValues(Exception):
    """一格比較撞到沒有訂的情形（欄位值為 None、數值比較轉不成數、比較方向不認得）。炸掉，不靜默選一邊。"""

    def __init__(self, kind, op, left, right):
        self.kind = kind
        self.op = op
        self.left = left
        self.right = right
        super().__init__(f"uncomparable ({kind}): op={op!r} left={left!r} right={right!r}")


def is_missing(value) -> bool:
    """缺值判定：None、空字串（含只有空白）、浮點 NaN（含 numpy 純量）、`Decimal` 的 NaN／sNaN、pandas 的 NA／NaT。

    只認純量：list、tuple、dict、set 與 numpy 陣列（含 0 維）一律不算缺值；其餘任何比較會炸的型別也不算，
    **絕不往上拋**。本模組不 import pandas／numpy —— NA／NaT／ndarray 以型別名判斷，NaN 以「自己不等於自己」判斷。
    """
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, (list, tuple, dict, set, frozenset)) or type(value).__name__ == "ndarray":
        return False
    if isinstance(value, decimal.Decimal):
        return value.is_nan()            # 含 sNaN；不做比較，避免 sNaN 的 InvalidOperation
    if type(value).__name__ in ("NAType", "NaTType"):
        return True
    try:
        return bool(value != value)
    except Exception:  # noqa: BLE001 — 只做判定，任何型別都不得讓它炸（docstring）
        return False


def finite_number(value) -> bool:
    """轉得成數、而且是有限數（排除 nan、inf）。`float()` 丟 TypeError／ValueError 以外的例外照拋。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return number == number and number not in (float("inf"), float("-inf"))


def compare_values(left, op, right) -> bool:
    """一格比較（兩態）。欄位值為 None、數值比較轉不成數、方向不認得 → `UncomparableValues`。
    判定順序與原 ui_v2 `_compare` 相同：先看欄位值是否為 None，再看方向。"""
    if left is None:
        raise UncomparableValues(UNCOMPARABLE_LEFT_MISSING, op, left, right)
    if op in (OP_EQ, OP_NE):
        same = str(left) == str(right)
        return same if op == OP_EQ else not same
    if op in (OP_GT, OP_LT):
        try:
            a, b = float(left), float(right)
        except (TypeError, ValueError):
            raise UncomparableValues(UNCOMPARABLE_NOT_NUMBER, op, left, right)
        return a > b if op == OP_GT else a < b
    if op in (OP_ON_OR_BEFORE, OP_AFTER):
        a, b = str(left), str(right)
        return a <= b if op == OP_ON_OR_BEFORE else a > b
    raise UncomparableValues(UNCOMPARABLE_UNKNOWN_OPERATOR, op, left, right)


def compare_tristate(left, op, right):
    """一格比較的三種結果：回 `(True／False／None, 無法判定的原因代碼或 None)`。

    - 欄位值缺（`is_missing`）→ `(None, UNDET_MISSING)`，不分比較方向；
    - 數值比較的欄位值不是有限數 → `(None, UNDET_LEFT_NOT_NUMBER)`；
    - 數值比較的條件數值不是有限數 → `(None, UNDET_RIGHT_NOT_NUMBER)`；
    - 比較方向不在 `OPERATOR_CODES` → `UncomparableValues`（那不是資料缺，是條件本身壞了）。
    """
    if op not in OPERATOR_CODES:
        raise UncomparableValues(UNCOMPARABLE_UNKNOWN_OPERATOR, op, left, right)
    if is_missing(left):
        return None, UNDET_MISSING
    if op in NUMERIC_OPERATOR_CODES:
        if not finite_number(left):
            return None, UNDET_LEFT_NOT_NUMBER
        if not finite_number(right):
            return None, UNDET_RIGHT_NOT_NUMBER
    try:
        return compare_values(left, op, right), None
    except UncomparableValues:
        try:
            float(left)
        except (TypeError, ValueError):
            return None, UNDET_LEFT_NOT_NUMBER
        return None, UNDET_RIGHT_NOT_NUMBER


def rule_is_effective(rule: dict) -> bool:
    """數值欄留空 → 該列不生效。"""
    return str(rule.get("value", "")).strip() != ""


def apply_rules_tristate(rows, rules, compare=compare_tristate):
    """逐檔累計判定。回 `(steps, listed, undet)`：

    - `steps`：`[(條件, 套用前, 符合, 無法判定), ...]` —— 「符合」＝到這一條為止每一條都明確符合；
      「無法判定」＝到這一條為止沒有一條明確不符合、但至少一條無法判定；下一條的「套用前」＝兩者之和；
    - `listed`：明確符合 ＋ 無法判定的檔，保持輸入順序；
    - `undet`：`{fund_code: [(原因, 欄位), ...]}`（原因是 `compare` 回的第二個值）。
    任一條**明確不符合** → 該檔不列。數值欄留空的條件不生效，兩個數照抄上一列。

    `compare(left, op, right)` 預設是本模組的 `compare_tristate`（中性方向代碼）；ui_v2 傳它自己的包裝
    （中文方向字面、中文原因字），走訪順序與每個欄位被讀的時機與原 ui_v2 實作相同。
    """
    alive = list(rows)
    undet = {}
    steps = []
    for rule in rules:
        before = len(alive)
        if rule_is_effective(rule):
            kept = []
            for row in alive:
                result, why = compare(row.get(rule["field"]), rule["op"], rule["value"])
                if result is False:
                    undet.pop(row["fund_code"], None)
                    continue
                if result is None:
                    undet.setdefault(row["fund_code"], []).append((why, rule["field"]))
                kept.append(row)
            alive = kept
        sure = sum(1 for row in alive if row["fund_code"] not in undet)
        steps.append((rule, before, sure, len(alive) - sure))
    return steps, alive, undet
