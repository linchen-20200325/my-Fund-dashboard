# -*- coding: utf-8 -*-
"""View model 共同欄位與驗證輔助（80 第 6 節；純 Python，只用標準函式庫）。

硬規則（80 第 1 節、第 6 節「禁止」）：
- Missing ≠ 0／中性／HOLD／safe：`status` 為 missing／failed 時 `value` 必為 None，且必帶 `reason_code`。
- view model 不創造 objective facts：`ok`／`stale` 帶值時必須帶 `source` 與 `as_of`。
- 值只能是有限數字或 None：NaN／inf／bool／字串一律拒絕（缺值以 None 表達，不以 NaN 表達）。

本檔**不是**呈現規則資料表：規則表住 `shared/ui_semantics/`（批 2b；80 第 3.3 節 (c)）。這裡只有契約需要的最小鍵集，
`MISSING_TEXT` 由規則表取得（單一來源，值不變）。
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from shared.ui_semantics import rules as _rules

# 缺值的 presentation 字樣（BL-0532：正式模式統一為 `◇ 資料未備`；80 第 5 節 empty／error 列）。
# 單一來源：`shared/ui_semantics/rules.py`（規則表 `missing` 列）。
MISSING_TEXT = _rules.MISSING_TEXT

# 資料狀態鍵（80 第 6 節共同欄位 `status`）。
STATUS_OK = "ok"
STATUS_MISSING = "missing"
STATUS_FAILED = "failed"
STATUS_STALE = "stale"
STATUS_UNDETERMINED = "undetermined"
STATUSES = (STATUS_OK, STATUS_MISSING, STATUS_FAILED, STATUS_STALE, STATUS_UNDETERMINED)

# 新鮮度狀態（80 第 6 節：`freshness_state`；門檻未裁示＝undetermined）。
# ⚠️ 規格缺口：80 只點名 `undetermined`，未列舉其他值；此處取最小集合（fresh／stale／undetermined），
#    待客戶裁示覆核；view model 不自行判新鮮度，只承載下層或正式規則的結果。
#    批 2b：三個值對到規則表的對照見 `shared/ui_semantics/rules.py::FRESHNESS_TO_KEY`（一致性由測試鎖）。
FRESH_FRESH = "fresh"
FRESH_STALE = "stale"
FRESH_UNDETERMINED = "undetermined"
FRESHNESS_STATES = (FRESH_FRESH, FRESH_STALE, FRESH_UNDETERMINED)

_KEY_RE = re.compile(r"^[a-z][a-z0-9_.]*$")


def require_key(name: str, value: object) -> str:
    """鍵值（`label_key`、`reason_code` 這類）：小寫英數／底線／點，不接受自由文字。"""
    if not isinstance(value, str) or not _KEY_RE.match(value):
        raise ValueError(f"{name} 必須是小寫鍵值字串（不接受自由文字），收到 {value!r}")
    return value


def require_text(name: str, value: object) -> str:
    """非空白字串。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} 必須是非空字串，收到 {value!r}")
    return value


def optional_text(name: str, value: object) -> Optional[str]:
    return None if value is None else require_text(name, value)


def require_number_or_none(name: str, value: object) -> Optional[float]:
    """有限數字或 None。bool 是 int 的子類，明確擋掉；NaN／inf 擋掉（缺值用 None，不用 NaN）。"""
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} 必須是數字或 None，收到 {type(value).__name__}")
    if not math.isfinite(value):
        raise ValueError(f"{name} 不得為 NaN／inf（缺值請用 None），收到 {value!r}")
    return value


@dataclass(frozen=True)
class FactMeta:
    """帶值元件共同欄位中「值以外」的部分：`unit`／`source`／`as_of`／`retrieved_at`／`freshness_state`／
    `status`／`reason_code`。

    規則：
    - `status` ∈ STATUSES；`freshness_state` ∈ FRESHNESS_STATES（預設 undetermined）。
    - `missing`／`failed` 必帶 `reason_code`（原因鍵）。
    - `ok`／`stale` 必帶 `source` 與 `as_of`（逐欄 as_of，不以頁級時間代替）。
    - 其餘（`undetermined`）可無 source／as_of，但若有，不得是空字串。
    """

    status: str
    source: Optional[str] = None
    as_of: Optional[str] = None
    retrieved_at: Optional[str] = None
    unit: Optional[str] = None
    freshness_state: str = FRESH_UNDETERMINED
    reason_code: Optional[str] = None

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"status 必須在 {STATUSES}，收到 {self.status!r}")
        if self.freshness_state not in FRESHNESS_STATES:
            raise ValueError(f"freshness_state 必須在 {FRESHNESS_STATES}，收到 {self.freshness_state!r}")
        for name in ("source", "as_of", "retrieved_at", "unit"):
            optional_text(name, getattr(self, name))
        if self.reason_code is not None:
            require_key("reason_code", self.reason_code)
        if self.status in (STATUS_MISSING, STATUS_FAILED) and self.reason_code is None:
            raise ValueError(f"status={self.status} 必須帶 reason_code")
        if self.status in (STATUS_OK, STATUS_STALE):
            if self.source is None or self.as_of is None:
                raise ValueError(f"status={self.status} 必須帶 source 與 as_of（view model 不創造事實）")

    @property
    def is_missing(self) -> bool:
        return self.status in (STATUS_MISSING, STATUS_FAILED)


@dataclass(frozen=True)
class ValueFacts:
    """單一數值事實：`value`（原值；不是格式化字串）＋ `FactMeta`。

    不變量：`missing`／`failed` 時 value 必為 None（Missing 不得攜帶數值）；`ok` 時 value 必不為 None。
    `stale`／`undetermined` 兩者皆可（過期值照實顯示，由符號標示；無法判定可無值）。
    """

    value: Optional[float]
    meta: FactMeta

    def __post_init__(self) -> None:
        require_number_or_none("value", self.value)
        if not isinstance(self.meta, FactMeta):
            raise TypeError("meta 必須是 FactMeta")
        if self.meta.is_missing and self.value is not None:
            raise ValueError("Missing／failed 不得攜帶數值（Missing ≠ 0／中性）")
        if self.meta.status == STATUS_OK and self.value is None:
            raise ValueError("status=ok 必須有 value；缺值請用 status=missing 並帶 reason_code")

    @property
    def has_value(self) -> bool:
        return self.value is not None
