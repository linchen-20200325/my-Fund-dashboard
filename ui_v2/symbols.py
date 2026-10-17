# -*- coding: utf-8 -*-
"""正式模式的 ◆／◇ 符號（Phase 3 ◆／◇ 小批；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其三、其四，
之八其三 (c-2)；客戶裁示 `DEC-2026-10-17-03` 第 (3)(4) 題、`DEC-2026-10-17-07`）。

純函式模組：**不 import streamlit、不 import 舊樹、不 import 任何模組**（`tests/ui_v2/test_ui_v2_live_import_guard.py`）。

輸入一律是 `plain.plain_model` 交出來的一般畫面模型（已深拷貝）；本模組**就地改寫**那一份，只做兩件事：

1. **◆ 需要注意**（其三）：`HLD-0`「偏離筆數大於零」與 `ALO-0`「超出容許帶」兩種情形（各頁 logic 判成黃燈的那一支），
   燈改為不著色（中性文字色），圖示 `◆`、狀態字「需要注意」，燈上那一句文案字面照舊
   （「有 N 檔超出你設定的門檻」、「<類別名> 與目標差 N 個百分點」）。
   偏離筆數怎麼算、容許帶內外怎麼判、門檻與容許帶由誰輸入，一個都不碰 —— 本模組只認 logic 已經交出的黃燈。
   持倉體檢那一行「黃燈說的是……」在這裡已經沒有黃燈，改寫成同義的一句（`HLD0_NOTE_FROM`／`HLD0_NOTE_TO`）。
2. **◇ 資料未備**（其四）：畫面上的「`⬜ 資料未備`」（卡片 `資料未備` 主值、空狀態 `來源缺`、各塊寫資料未備的主值與列尾）
   一律改成「`◇ 資料未備`」；空狀態 `來源缺` 的佔位圖示 `⬜` 改成 `◇`。顏色照舊（灰）。

**不做什麼（護欄 2）**：
- `_` 開頭的鍵底下的**字串值**一個都不改（狀態、嚴重度、程式拿去比對的值、匯出檔內容 `_export_text`）；
  只有 ◆ 那一支改燈的 `_tone`（顏色語意 黃 → 中性）—— 那正是第 (3) 題要改的「燈的顏色」，判定（`_state`、偏離筆數、
  `_max_bucket`）一個都不碰。
- `⬜` 照舊留給「無法判定」與「不適用」那一族（`⬜ 不適用：…`、`⬜ 無法判定`、`⬜ 未設定`、表格裡單獨一個 `⬜` 的缺值格）；
  表格缺值格依成因改 `◇` 那一條（其四第 2 條）逐塊對照隨實作批寫明，**本批不動**。
- `◷`、`⛔`、黃燈的 `⚠`（`MKT-0`、`SET-0` 等資料面黃燈）不動。
- 不新增任何一列、一個按鈕、一段；不搬層次（P1-④）。

**示範模式不經過本模組**（44 第七節第三小節之七開頭第 4 條；`docs/BACKLOG.md` BL-0367）；只由各頁 `page.py` 的正式模式分支呼叫。
"""

from __future__ import annotations

# ───────────────────────── 字面 ─────────────────────────

SYMBOL_ATTENTION = "◆"
TEXT_ATTENTION = "需要注意"
SYMBOL_MISSING = "◇"
SYMBOL_UNDECIDABLE = "⬜"

# 44 第五節第一小節 `資料未備` 主值、第五節第五小節 `來源缺` 模板的舊字首 → 新字首（其四表第三列）。
MISSING_OLD = f"{SYMBOL_UNDECIDABLE} 資料未備"
MISSING_NEW = f"{SYMBOL_MISSING} 資料未備"

# 改成 ◆ 的燈：只有這兩塊（其三第 1 條）；其餘各頁的黃燈（`MKT-0`、`SET-0` 等）屬資料狀態，照舊（其三第 5 條）。
ATTENTION_CODES = frozenset({"HLD-0", "ALO-0"})
_WARN_TONE = "黃"
NEUTRAL_TONE = "中性"

# 持倉體檢偏離那一支的說明句：舊句寫「黃燈」，自本批起畫面上沒有黃燈，舊句會變成假話。
# 只換主詞，句意（要不要多看一眼，不是該調整了）一字不改。
HLD0_NOTE_FROM = "黃燈說的是「要不要多看一眼」，不是「該調整了」。"
HLD0_NOTE_TO = f"「{SYMBOL_ATTENTION} {TEXT_ATTENTION}」說的是「要不要多看一眼」，不是「該調整了」。"

_EMPTY_KIND_SOURCE_MISSING = "來源缺"


# ───────────────────────── ◆ 需要注意 ─────────────────────────


def mark_attention(display: dict) -> list:
    """`HLD-0`／`ALO-0` 被 logic 判成黃燈的那一塊 → 不著色、`◆`、「需要注意」（就地改寫）。回改到的塊代號。

    只認 `_tone == "黃"`：兩塊的黃燈各只有一支（`HLD-0` 偏離筆數大於零、`ALO-0` 超出容許帶），本模組不另判。
    """
    changed = []
    for block in display.get("blocks") or ():
        if block.get("code") not in ATTENTION_CODES or block.get("_tone") != _WARN_TONE:
            continue
        block["_tone"] = NEUTRAL_TONE
        block["glyph"] = SYMBOL_ATTENTION
        block["state_word"] = TEXT_ATTENTION
        if isinstance(block.get("detail_lines"), list):
            block["detail_lines"] = [HLD0_NOTE_TO if line == HLD0_NOTE_FROM else line for line in block["detail_lines"]]
        changed.append(block["code"])
    return changed


# ───────────────────────── ◇ 資料未備 ─────────────────────────


def _swap(text: str) -> str:
    return text.replace(MISSING_OLD, MISSING_NEW)


def _visit(node, own_key_private: bool) -> int:
    """回改了幾個字串。`own_key_private`：這個值掛在 `_` 開頭的鍵上（那裡的字串照原字，見模組說明）。"""
    count = 0
    if isinstance(node, dict):
        if node.get("_empty_kind") == _EMPTY_KIND_SOURCE_MISSING and node.get("glyph") == SYMBOL_UNDECIDABLE:
            node["glyph"] = SYMBOL_MISSING
            count += 1
        for key in list(node):
            value = node[key]
            private = isinstance(key, str) and key.startswith("_")
            if isinstance(value, str):
                if not private and MISSING_OLD in value:
                    node[key] = _swap(value)
                    count += 1
            else:
                count += _visit(value, private)
        return count
    if isinstance(node, list):
        for index, item in enumerate(node):
            if isinstance(item, str):
                if not own_key_private and MISSING_OLD in item:
                    node[index] = _swap(item)
                    count += 1
            else:
                count += _visit(item, own_key_private)
        return count
    if isinstance(node, tuple):
        # tuple 不能就地改：只往下走 dict／list；裡面的字串照原字（現行模型的 tuple 都是程式用的鍵清單）。
        for item in node:
            if not isinstance(item, str):
                count += _visit(item, own_key_private)
    return count


def mark_missing(display: dict) -> int:
    """畫面上的「⬜ 資料未備」→「◇ 資料未備」，`來源缺` 佔位的 `⬜` 圖示 → `◇`（就地改寫）。回改了幾處。"""
    return _visit(display, False)


def apply(display: dict) -> dict:
    """正式模式頁面一次套用兩件事（就地改寫並回傳同一份）。呼叫點：`plain.plain_model` 之後、`health.dedupe_failures` 之前。"""
    mark_attention(display)
    mark_missing(display)
    return display
