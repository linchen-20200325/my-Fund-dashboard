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

Sheet 字串辨識（`normalize_tier`）：`core` / `satellite`（大小寫不計）＋ 中文「核心」「衛星」。

寫回 Sheet：session 端的值由 `fund_tier_sheet_value` 給（未設定 → 空字串）；
真正寫進格子之前，寫回路徑再走 `merge_sheet_tier` —— 未設定的列**保留 Sheet 原值**
（不把客戶的設定、或本程式認不得的值洗成空白）。

⛔ 本模組不得加入任何基金名稱關鍵字邏輯：猜不出來就是 `None`。
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

CORE_TIER = "core"
SATELLITE_TIER = "satellite"

#: Sheet 上代表「未設定」的值：空字串，不是 "satellite"。
UNSET_SHEET_VALUE = ""

_VALID_TIERS = (CORE_TIER, SATELLITE_TIER)


#: 客戶在 Sheet 上可能手打的中文同義詞（只收這兩個；不另擴充）。
_ZH_SYNONYMS = {"核心": CORE_TIER, "衛星": SATELLITE_TIER}


def normalize_tier(raw: Any) -> Optional[str]:
    """Sheet 原始字串 → `"core"` / `"satellite"` / `None`（大小寫、前後空白不計；非法值 → None）。

    中文「核心」「衛星」視同 `core` / `satellite`（客戶在 Sheet 上手打中文的情形）。
    """
    _t = str(raw or "").strip()
    _t = _ZH_SYNONYMS.get(_t, _t.lower())
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


def merge_sheet_tier(tier: Optional[str], sheet_raw: Any) -> str:
    """寫回 Sheet 前，把這次要寫的級別與 Sheet 上**現有的原值**合併，回傳該寫進格子的字串。

    - `tier` 為未設定（`None` 或非法值）→ **原樣保留 Sheet 現值**（含空白、含無法辨識的字串）。
      session 沒有客戶級別不代表客戶在 Sheet 上沒設定（例如剛還原 JSON 備份、或 Sheet 上的值
      本程式認不得）—— 寫空白會把客戶的資料洗掉。
    - `tier` 有明確級別、且 Sheet 現值語意相同（例如現值是「核心」、這次要寫 `core`）→
      保留 Sheet 現值，不改寫客戶的拼法。
    - 其他 → 寫 `tier`（`"core"` / `"satellite"`）。

    `tier` 先經 `normalize_tier`，所以傳 Sheet 字串（`"core"`、`""`）或三態值都可以。
    """
    _raw = "" if sheet_raw is None else str(sheet_raw)
    _want = normalize_tier(tier)
    if _want is None:
        return _raw
    if normalize_tier(_raw) == _want:
        return _raw
    return _want
