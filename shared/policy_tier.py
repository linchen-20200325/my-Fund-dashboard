"""shared/policy_tier.py — 核心／衛星「級別」的唯一判定（L0・純函式・零 IO）。

三態：`"core"` / `"satellite"` / **`None`（未設定）**。`None` 不是衛星。

為什麼住 L0：`repositories/snapshot_repository.py`（L1）與
`ui/helpers/portfolio/allocation.py`（L3）都要用同一把尺；
`CLAUDE.md §8.2` 禁跨層上行 import，判定本體只能放在兩層都能下行 import 的 L0。

優先序（`resolve_tier`）：
1. `policy_tier` —— v1 保單分頁欄位（`repositories/policy/v1.py` 讀回時寫入）。
2. `is_core` —— v2 讀回時由 `tier` 欄映射的三態布林（`ui/helpers/cloud_io.py`），
   **只認真正的 `True` / `False`**；`None`、缺鍵、其他型別一律視為未設定。
3. 都沒有 → `None`。

⛔ 本模組不得加入任何基金名稱關鍵字邏輯：猜不出來就是 `None`。
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

CORE_TIER = "core"
SATELLITE_TIER = "satellite"

#: Sheet 上代表「未設定」的值：空字串，不是 "satellite"。
UNSET_SHEET_VALUE = ""

_VALID_TIERS = (CORE_TIER, SATELLITE_TIER)


def normalize_tier(raw: Any) -> Optional[str]:
    """Sheet 原始字串 → `"core"` / `"satellite"` / `None`（大小寫、前後空白不計；非法值 → None）。"""
    _t = str(raw or "").strip().lower()
    return _t if _t in _VALID_TIERS else None


def resolve_tier(fund: Mapping[str, Any] | None) -> Optional[str]:
    """這一筆持倉的級別：`"core"` / `"satellite"` / `None`（未設定）。

    ⚠️ 刻意不用 `bool(is_core)`：`bool(None)` 是 `False`，會把未設定壓成衛星。
    """
    _f = fund or {}
    _explicit = normalize_tier(_f.get("policy_tier"))
    if _explicit is not None:
        return _explicit
    _is_core = _f.get("is_core")
    if _is_core is True:
        return CORE_TIER
    if _is_core is False:
        return SATELLITE_TIER
    return None


def tier_to_sheet_value(tier: Optional[str]) -> str:
    """級別 → 寫回 Sheet 的字串。未設定寫空字串。"""
    return tier if tier in _VALID_TIERS else UNSET_SHEET_VALUE


def fund_tier_sheet_value(fund: Mapping[str, Any] | None) -> str:
    """持倉 dict → 寫回 Sheet 的級別字串。所有寫回 Sheet 的路徑一律走這一支。"""
    return tier_to_sheet_value(resolve_tier(fund))
