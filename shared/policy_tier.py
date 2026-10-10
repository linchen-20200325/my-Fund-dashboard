r"""shared/policy_tier.py — 核心／衛星「級別」的唯一詞彙與唯一判定（L0・純函式・零 IO）。

## 為什麼住在 L0（而不是跟 `resolve_core_flag` 一起待在 L3）

同一把尺有兩個消費者，分屬不同層：

* `repositories/snapshot_repository.py`（**L1**）—— 寫 `_持倉總覽` 的「級別」欄；
* `ui/helpers/portfolio/allocation.py`（**L3**）—— 全站配置比例的級別判定。

`CLAUDE.md §8.2` 硬規則明禁**跨層上行 import**（L1 不得 import L2/L3），
所以判定本體只能住在 L0（被全層 import 的跨層基底），兩層各自**下行** import。
把它放在 L3 再讓 L1 去 import，會是本 repo 第一個 `repositories/ → ui/` 依賴
（實測 `git grep -n 'from ui\.' -- 'repositories/**'` 在 `9cbf0377` 為 **0 命中**）。

## ⭐ 三態，不是二態

`"core"` / `"satellite"` / **`None`**。

**`None` ＝「使用者還沒決定」，不是「衛星」。**
客戶就本題拍板：**空白就是空白，不要猜。**

在這之前，系統會用**基金名稱關鍵字**猜一個級別出來，覆寫掉從 Google Sheet 讀回的值，
再於下一次存檔寫回 Sheet —— 也就是把猜測**寫進客戶的資料**，而且每存一次就再蓋一次。
那條鏈的 bug 是結構性的：`ui/helpers/session.py::_CORE_KEYWORDS` 含「配息」且**先被檢查**，
而台灣基金名稱依法幾乎都帶「(基金之配息來源可能為本金)」
⇒ 命中「配息」⇒ **一律被判成核心**（實測：同一檔科技基金加上該法定揭露字樣後，
判定由衛星翻成核心）。

## 級別的優先序（`resolve_tier`）

1. `policy_tier` —— v1 保單分頁 schema 的欄位（`repositories/policy/v1.py`）。
2. `is_core` —— v2 schema 讀回時由 `tier` 欄映射成的**三態**布林
   （`ui/helpers/cloud_io.py`：`core→True` / `satellite→False` / 空白→`None`）。
3. 兩者都沒有 → `None`（未設定）。

兩個鍵是**兩條讀取路徑各自的產物**，不是同一件事的兩種寫法：
v1 路徑只寫 `policy_tier`、v2 路徑只寫 `is_core`。故兩個都要看，且 v1 優先
（使用者在 Sheet 上明示的欄位）。

⛔ **本模組不做、也不得加入任何名稱啟發式。** 這裡沒有「猜不出來就回 satellite」
這條路 —— 猜不出來就是 `None`，由呼叫端自己決定要怎麼呈現「未設定」。
"""
from __future__ import annotations

from typing import Any, Mapping, Optional

CORE_TIER = "core"
SATELLITE_TIER = "satellite"

#: Sheet 上代表「未設定」的值。**空字串，不是 "satellite"。**
UNSET_SHEET_VALUE = ""

_VALID_TIERS = (CORE_TIER, SATELLITE_TIER)


def normalize_tier(raw: Any) -> Optional[str]:
    """把 Sheet 上的原始字串正規化成 `"core"` / `"satellite"` / `None`。

    大小寫不分、前後空白不計；**任何非法值一律回 `None`（未設定），不猜、不退衛星**。
    """
    _t = str(raw or "").strip().lower()
    return _t if _t in _VALID_TIERS else None


def resolve_tier(fund: Mapping[str, Any] | None) -> Optional[str]:
    """這一筆持倉的級別：`"core"` / `"satellite"` / `None`（**使用者還沒決定**）。

    優先序見 module docstring：`policy_tier`（v1 欄）→ `is_core`（v2 三態）→ `None`。

    ⚠️ `is_core` 只認**真正的布林**：`True`→core、`False`→satellite。
    `None` / 缺鍵 / 其他型別一律視為未設定 —— 刻意**不**用 `bool(...)` 去壓，
    因為 `bool(None)` 是 `False`，那會把「還沒決定」默默變成「衛星」，
    正是本模組要終結的那個 bug。
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
    """級別 → 寫回 Sheet 的字串。**未設定寫空字串，不得寫成 satellite。**"""
    return tier if tier in _VALID_TIERS else UNSET_SHEET_VALUE


def fund_tier_sheet_value(fund: Mapping[str, Any] | None) -> str:
    """`resolve_tier` ＋ `tier_to_sheet_value` 的合成：持倉 dict → 要寫回 Sheet 的字串。

    所有**寫回客戶 Google Sheet** 的路徑一律走這一支，不要在呼叫點自己寫三元式 ——
    本 repo 原本有三處各寫一份
    （`ui/helpers/cloud_io.py` ×2、`repositories/snapshot_repository.py` ×1），
    而三處都只讀 `is_core`、**完全無視 `policy_tier`**：
    使用者在 v1 Sheet 明示 `core` 的基金，存檔時會被名稱猜測的結果覆寫掉。
    """
    return tier_to_sheet_value(resolve_tier(fund))
