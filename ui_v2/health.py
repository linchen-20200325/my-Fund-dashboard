# -*- coding: utf-8 -*-
"""四頁頁首「資料狀態行」與同源錯誤去重（Phase 3 P0-②；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其二第 3、4 條）。

純函式模組：**不 import streamlit、不 import 舊樹**（`tests/ui_v2/test_ui_v2_live_import_guard.py`），
只 import 同樹的 `ui_v2.plain` 與 `ui_v2.page_health`（後者只用在檔尾「各頁資料狀態總表的原因項目」那一段）。畫法（`st.markdown`、`st.page_link`）住在 `ui_v2/health_view.py`。

輸入一律是 `plain.plain_model` 交出來的**一般畫面用的模型**（已深拷貝、已換成使用者語言）。本模組只做三件事：

1. **同源錯誤一頁只摘要一次**（其二第 3 條）：`plain` 寫出的失敗摘要（「⛔ <資料類> 取數失敗：<狀態句>」、
   「⛔ 設定讀不到：<狀態句>」）只在頁首資料狀態行出現一次；頁面其餘位置改寫成：
   - 該塊本身是 `系統錯誤`（模型既有的 `_state`；資產配置沒有 `_state`，看塊裡有沒有 `_empty_kind` 為 `系統錯誤`
     的佔位）→ 該塊第一處（不在表格列裡、前面沒有接別的字）寫「⛔ 此區塊暫時無法判定」，**一塊只寫一次**；
   - 其餘位置 → 只留狀態族：「⛔ 取數失敗」／「⛔ 尚未設定」／「⛔ 設定讀不到」；逐檔的那一種留基金代碼
     （「⛔ <代碼> 取數失敗」—— 哪一檔失敗是該塊自己的內容，不是摘要）。
   - 同一串說明行裡因此變成一模一樣的 ⛔ 行，只留第一行（BL-0146）。
   - 結論燈（①）那一句若以燈自己的圖示開頭，拿掉重複的圖示；剩下的字與狀態字相同就整句不畫
     （Phase 3 P1-④；`trim_light_echo`。例：「⛔ 狀態：取數失敗 ⛔ 尚未設定」→「⛔ 狀態：取數失敗 尚未設定」；
     「⬜ 狀態：中性 ⬜ 資料未備」→「⬜ 狀態：中性 資料未備」。依據與變動範圍見該函式）。
   ⛔ 與紅色照舊：`_` 開頭的鍵（狀態、顏色、嚴重度）一個都不碰，**判定照舊**（護欄 2）。
2. **資料狀態行**（其二第 4 條、59 線框第 2.6 節）：四種 —— `◷` 不是最新（只顯示最後有效資料）、`◇` 資料未備、
   `⛔` 取數失敗、尚未設定 —— 同類只列一次，附資料截至日；**沒有任何一種時不寫「資料齊」或「正常」，只寫資料截至日**。
   判定沿用模型既有的 `_state`／`_empty_kind`（`資料未備`、`來源缺`、`部分缺` → `◇`）與失敗摘要；
   `◷` 由呼叫端依該頁既有的標示交進來（目前只有持倉體檢有「淨值取自預存序列」這一種）。
   符號只是呈現；卡片內既有符號（`⬜` 等）本批不動（→ ◆／◇ 小批起，卡片內的「⬜ 資料未備」改 ◇、偏離黃燈改 ◆，住在 `ui_v2/symbols.py`，
   在本模組之前套用）。
3. **核心卡的來源與新鮮度徽章移到 ④「證據／來源」**（其二第 4 條）：② 卡上 `_kind` 為 `來源`／`新鮮度` 的徽章
   拿下來、交給呼叫端畫在 ④；不刪除（來源、取得時間、資料截至日只能換位置，不能消失）。

**示範模式不經過本模組**（BL-0367）。
"""

from __future__ import annotations

import re
from datetime import date

from . import page_health, plain

# ───────────────────────── 畫面字樣 ─────────────────────────
# 字面為本組依 44 第七節第三小節之七其二第 3、4 條與 59 線框第 2.5、2.6 節擬定；只描述狀態、不指示動作
# （客戶 2026-10-03、2026-10-02 兩則裁示）。

STATUS_LABEL = "資料狀態："
AS_OF_LABEL = "資料截至"
AS_OF_UNKNOWN = "—"

SYMBOL_STALE = "◷"
SYMBOL_MISSING = "◇"
SYMBOL_ERROR = "⛔"

TEXT_STALE = "不是最新：部分只顯示最後有效資料"
TEXT_MISSING = "資料未備"
TEXT_FETCH_FAILED = "取數失敗"
TEXT_NOT_CONFIGURED = "尚未設定"
TEXT_SETTINGS_UNREADABLE = "設定讀不到"
# 44 第七節第三小節之七其二第 3 條逐字。
TEXT_BLOCK_UNDECIDABLE = "此區塊暫時無法判定"

LINE_BLOCK_UNDECIDABLE = f"{SYMBOL_ERROR} {TEXT_BLOCK_UNDECIDABLE}"
LINE_FETCH_FAILED = f"{SYMBOL_ERROR} {TEXT_FETCH_FAILED}"
LINE_NOT_CONFIGURED = f"{SYMBOL_ERROR} {TEXT_NOT_CONFIGURED}"
LINE_SETTINGS_UNREADABLE = f"{SYMBOL_ERROR} {TEXT_SETTINGS_UNREADABLE}"

# 導覽（44 第五節第三小節 `導覽`，其五）：只換頁。
SETTINGS_LINK_LABEL = "前往設定與診斷"
# 單頁入口（沒有 `st.navigation`，換不了頁）只寫這一行。
SETTINGS_ELSEWHERE_TEXT = "完整資料狀態在「設定與診斷」頁"

# ④「證據／來源」裡承接核心卡徽章的那一枚展開區（預設收合）。
PROVENANCE_TITLE = "核心卡的來源與新鮮度"

# 兩鍵一起存、兩鍵都沒存進去時卡片層那一行（BL-0177；58 U-44 三態之一）。
TEXT_SAVE_FAILED_BOTH = "儲存失敗"

# 資產配置「存檔寫入失敗」的前綴（真身 `ui_v2/alo/logic.py::TEXT_SAVE_FAILED` ＋「：」；測試逐字比對）。
_ALO_SAVE_FAILED_PREFIX = "存檔寫入失敗："

# ───────────────────────── 失敗摘要的形狀（`plain` 寫出來的那幾種） ─────────────────────────

# 「尚未設定」那一族的狀態句（`plain._KNOWN_MESSAGES` 的第三欄；寫入用的 `NOT_CONFIGURED_MESSAGE` 被讀取端回報時也落在這裡）。
NOT_CONFIGURED_STATES = tuple(state for _message, _class, state in plain._KNOWN_MESSAGES)
_ALL_STATES = NOT_CONFIGURED_STATES + (plain.STATE_FETCH_DEFAULT, plain.STATE_SETTINGS_DEFAULT)
_STATE_ALT = "|".join(re.escape(s) for s in sorted(_ALL_STATES, key=len, reverse=True))

# `plain._rewrite_failure` 第一支：`{prefix}⛔ {資料類} 取數失敗：{代碼 的}{狀態句}`（資料類不含空白與全形冒號）。
_FETCH_SUMMARY = re.compile(
    r"⛔ (?P<cls>[^\s：]+) 取數失敗：(?:(?P<fund>[A-Za-z0-9][A-Za-z0-9._-]{0,30}) 的)?(?P<state>" + _STATE_ALT + r")"
)
# 客戶 2026-10-18 裁示 BL-0375（`DEC-2026-10-18-02`；44 第七節第三小節之十）：`plain` 照留的那一句
# `⛔ 淨值 取數失敗：[<代碼>：]改用 <日期> 的預存淨值` —— 日期是裁示要留在畫面上的那一期，**不換成狀態族、不收成
# 「此區塊暫時無法判定」**；只把資料類記進資料狀態行（與其他取數失敗同一個狀態族），並記為「畫面上看得到失敗摘要」的塊。
_RETREAT_SUMMARY = re.compile(
    r"⛔ (?P<cls>[^\s：]+) 取數失敗：(?:[A-Za-z0-9][A-Za-z0-9._-]{0,30}：)?"
    + plain._NAV_RETREAT.pattern.lstrip("^").rstrip("$")
)
# 第二支：`⛔ 設定讀不到：{狀態句}`。
_SETTINGS_SUMMARY = re.compile(re.escape(plain.SETTINGS_UNREADABLE_PREFIX) + r"(?P<state>" + _STATE_ALT + r")")

_ERROR_STATE = "系統錯誤"
# 「資料未備」那一族（`◇`）：卡片 `資料未備`、空狀態 `來源缺`、`部分缺`（44 第五節第一、五小節）。
_MISSING_STATES = frozenset({"資料未備"})
_MISSING_EMPTY_KINDS = frozenset({"來源缺", "部分缺"})
_MISSING_LINE = f"{SYMBOL_MISSING} {TEXT_MISSING}"

# 表格列與逐檔分組：這裡面的失敗是那一列／那一檔自己的內容，不寫「此區塊暫時無法判定」，只留狀態族。
_ROW_KEYS = frozenset({"_rows", "_cells", "rows", "cells", "nav_rows", "nav_groups", "fund_groups",
                       "_items", "items", "_assign_rows", "_checkboxes"})


# 按「存檔」那一次的逐鍵結果（資產配置一鍵失敗時畫在該鍵原位，字形借用取數失敗的模板）：那是寫入結果、不是讀取的
# 失敗摘要，不去重、不進資料狀態行（否則會把寫入失敗說成取數失敗）。
_SAVE_RESULT_KEYS = frozenset({"key_error_lines"})


def not_configured_reason(*names) -> str:
    """「尚未設定：<哪一項>」（客戶 2026-10-19 裁示 G3，`DEC-2026-10-19-04`：尚未設定與取數失敗是不同原因，原因文字不得合併；
    原因寫「尚未設定：〈哪一項〉」）。多項以「、」連接。"""
    return f"{TEXT_NOT_CONFIGURED}：{'、'.join(n for n in names if n)}"


def not_configured_name(state: str) -> str:
    """「設定試算表尚未設定」→「設定試算表」（狀態行「尚未設定：」後面那一段）。"""
    suffix = TEXT_NOT_CONFIGURED
    return state[: -len(suffix)] if state.endswith(suffix) else state


class _Dedupe:
    def __init__(self) -> None:
        self.fetch_failed: list = []      # 中文資料類（不含尚未設定那一族）
        self.not_configured: list = []    # 尚未設定的對象（「設定試算表」…）
        self.affected: list = []          # 寫了「此區塊暫時無法判定」的塊代號
        self.explained: list = []         # 畫面上看得到的位置有失敗摘要的塊代號（不論是取數失敗還是尚未設定）
        # 逐塊記成因（BL-0250 批次 1，客戶 G3）：塊代號 → {"fetch": 有沒有真的取數失敗, "names": [尚未設定的對象…]}。
        self.block_causes: dict = {}
        # 逐字串記成因（BL-0250 批次 3-A）：`_rewrite` 每認出一句失敗摘要就記一筆「unconfigured」或「fetch」，
        # 給 `_walk` 判斷「這一個值節點的失敗是不是全部屬尚未設定」（`_drop_fetch_badge`）。
        self.string_kinds: list = []
        self.string_names: list = []      # 與 `string_kinds` 一一對應：尚未設定的對象（取數失敗那一筆是 None）
        # 值那一格的失敗全部屬尚未設定的值節點（`relabel_unconfigured` 拿掉它們的「取數失敗」徽章；本步驟不改結構）。
        self.unconfigured_values: list = []
        self.unconfigured_value_names: list = []   # 與 `unconfigured_values` 一一對應：那一個值尚未設定的對象（依出現順序、不重複）

    def cause(self, code, *, fetch=False, name=None) -> None:
        if code is None:
            return
        entry = self.block_causes.setdefault(code, {"fetch": False, "names": []})
        if fetch:
            entry["fetch"] = True
        if name and name not in entry["names"]:
            entry["names"].append(name)

    def note(self, cls, state) -> bool:
        """記一筆，回「是不是尚未設定那一族」。"""
        if state in NOT_CONFIGURED_STATES:
            name = not_configured_name(state)
            if name not in self.not_configured:
                self.not_configured.append(name)
            return True
        if cls and cls not in self.fetch_failed:
            self.fetch_failed.append(cls)
        return False


def _block_is_error(block) -> bool:
    if not block:
        return False
    if "_state" in block:
        return block.get("_state") == _ERROR_STATE
    return _has_empty_kind(block, _ERROR_STATE)


def _has_empty_kind(node, kind) -> bool:
    if isinstance(node, dict):
        if node.get("_empty_kind") == kind:
            return True
        return any(_has_empty_kind(v, kind) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(_has_empty_kind(v, kind) for v in node)
    return False


def _shown(block, field) -> bool:
    """這個欄位畫不畫在畫面上：`summary_text` 只當展開區（層 3、層 4）的標題；燈與核心卡（層 1、層 2）不畫它
    （五頁 `page.py` 只有展開區的標題讀 `summary_text`）。不畫的位置不拿來放「此區塊暫時無法判定」。"""
    return not (field == "summary_text" and (block or {}).get("_layer") in (1, 2))


def _rewrite(text: str, block, in_rows: bool, ctx: _Dedupe, field=None) -> str:
    """一個字串裡的失敗摘要 → 狀態族（或該塊第一處的「此區塊暫時無法判定」）。沒有摘要 → 原樣。"""
    out, pos = [], 0
    for match in sorted(
        [*_FETCH_SUMMARY.finditer(text), *_SETTINGS_SUMMARY.finditer(text), *_RETREAT_SUMMARY.finditer(text)],
        key=lambda m: m.start(),
    ):
        if match.start() < pos:
            continue
        if match.re is _RETREAT_SUMMARY:
            # BL-0375：日期句照留（原字不換），只把資料類記進資料狀態行、記為看得到失敗摘要的塊（見 `_RETREAT_SUMMARY`）；
            # 同一字串裡的其他失敗摘要照常往下改寫（2026-10-18 獨立稽核回修：原本整串早退，會漏改其他摘要）。
            ctx.cause((block or {}).get("code"), fetch=True)
            ctx.string_kinds.append(_KIND_FETCH)
            ctx.string_names.append(None)
            if _shown(block, field):
                ctx.note(match.group("cls"), None)
                code = (block or {}).get("code")
                if code is not None and code not in ctx.explained:
                    ctx.explained.append(code)
            out.append(text[pos:match.end()])
            pos = match.end()
            continue
        groups = match.groupdict()
        cls, fund, state = groups.get("cls"), groups.get("fund"), groups["state"]
        if cls is None:
            cls = plain.TABLE_NAMES["user_setting"]
        # 畫面上不畫的位置不進資料狀態行（那一句使用者看不到，狀態行就不能替它說話）；照樣換成狀態族。
        unconfigured = ctx.note(cls, state) if _shown(block, field) else state in NOT_CONFIGURED_STATES
        code = (block or {}).get("code")
        if unconfigured:
            ctx.cause(code, name=not_configured_name(state))
        else:
            ctx.cause(code, fetch=True)
        ctx.string_kinds.append(_KIND_UNCONFIGURED if unconfigured else _KIND_FETCH)
        ctx.string_names.append(not_configured_name(state) if unconfigured else None)
        if _shown(block, field) and code is not None and code not in ctx.explained:
            ctx.explained.append(code)
        whole = not text[: match.start()].strip() and not text[match.end():].strip()
        if (whole and not fund and not in_rows and _block_is_error(block) and _shown(block, field)
                and code is not None and code not in ctx.affected):
            ctx.affected.append(code)
            line = LINE_BLOCK_UNDECIDABLE
        elif fund:
            line = f"{SYMBOL_ERROR} {fund} {TEXT_NOT_CONFIGURED if unconfigured else TEXT_FETCH_FAILED}"
        elif unconfigured:
            # 失敗摘要一頁只出現一次（之七其二第 3 條）：塊內這一處只留狀態族「⛔ 尚未設定」，哪一項寫在資料狀態行；
            # 燈、展開區摘要、③ 另由 `relabel_unconfigured` 寫「尚未設定：<哪一項>」（客戶 G3 點名的位置）。
            line = LINE_NOT_CONFIGURED
        elif "cls" in groups:
            line = LINE_FETCH_FAILED
        else:
            line = LINE_SETTINGS_UNREADABLE
        out.append(text[pos:match.start()])
        out.append(line)
        pos = match.end()
    if not out:
        return text
    out.append(text[pos:])
    return "".join(out)


def _dedupe_lines(items: list) -> list:
    """一串說明行裡一模一樣的 ⛔ 行只留第一行（BL-0146）；其他行一行不動。"""
    if not items or not all(isinstance(i, str) for i in items):
        return items
    seen, out = set(), []
    for item in items:
        if SYMBOL_ERROR in item:
            if item in seen:
                continue
            seen.add(item)
        out.append(item)
    return out


def _walk(node, block, ctx: _Dedupe, *, private=False, in_rows=False, field=None):
    """與 `plain._walk` 同一套走法（`_` 開頭鍵底下的字串、受保護的鍵、輸入欄的當下值一律不碰）。"""
    if isinstance(node, dict):
        if isinstance(node.get("code"), str) and node.get("code") in plain.BLOCK_NAMES:
            block, in_rows = node, False
        kinds, names = [], []   # 本節點自己的字串欄位認出的失敗摘要成因與尚未設定的對象（BL-0250 批次 3-A）
        for key in list(node):
            value = node[key]
            if plain._protected(key) or key in _SAVE_RESULT_KEYS:
                continue
            rows = in_rows or key in _ROW_KEYS
            if isinstance(key, str) and key.startswith("_"):
                if isinstance(value, (dict, list, tuple)):
                    node[key] = _walk(value, block, ctx, private=True, in_rows=rows, field=key)
                continue
            if key == "value_text" and plain._is_input_field(node):
                continue
            before = len(ctx.string_kinds)
            node[key] = _walk(value, block, ctx, in_rows=rows, field=key)
            if isinstance(value, str) and key in _VALUE_FIELDS:   # 只看「值」那一格（徽章掛在它旁邊）；停用原因等別的欄位不算
                kinds.extend(ctx.string_kinds[before:])
                names.extend(n for n in ctx.string_names[before:] if n and n not in names)
        if kinds and all(k == _KIND_UNCONFIGURED for k in kinds) and any(_is_fetch_badge(b) for b in node.get("badges") or ()):
            ctx.unconfigured_values.append(node)   # 去重這一步只記、不改結構（判定與結構的不變式）；拿掉徽章在 `relabel_unconfigured`
            ctx.unconfigured_value_names.append(names)
        return node
    if isinstance(node, list):
        out = [_walk(item, block, ctx, private=private, in_rows=in_rows, field=field) for item in node]
        return out if private else _dedupe_lines(out)
    if isinstance(node, tuple):
        return tuple(_walk(item, block, ctx, private=private, in_rows=in_rows, field=field) for item in node)
    if isinstance(node, str) and not private:
        return _rewrite(node, block, in_rows, ctx, field)
    return node


def dedupe_failures(display: dict):
    """一般畫面模型 → (同一份模型〔就地改寫並回傳〕, 摘要)。

    摘要：`{"fetch_failed": [資料類…], "not_configured": [對象…], "affected_blocks": [塊代號…]}`。
    `affected_blocks` 的長度 ＝ 畫面上「此區塊暫時無法判定」的次數（測試以此對照）。
    呼叫端傳進來的必須是 `plain.plain_model` 交出的深拷貝（本函式就地改寫）。
    """
    ctx = _Dedupe()
    _walk(display, None, ctx)
    for block in display.get("blocks") or ():
        if block.get("_layer") == 1:
            trim_light_echo(block)
    return display, {
        "fetch_failed": list(ctx.fetch_failed),
        "not_configured": list(ctx.not_configured),
        "affected_blocks": list(ctx.affected),
        "explained_blocks": list(ctx.explained),
        "block_causes": {code: {"fetch": c["fetch"], "names": list(c["names"])} for code, c in ctx.block_causes.items()},
        # BL-0250 批次 3-A：值那一格的失敗全部屬尚未設定、旁邊卻掛著「取數失敗」徽章的值節點（物件本身，不是快照）。
        "unconfigured_value_nodes": list(ctx.unconfigured_values),
        "unconfigured_value_names": [list(n) for n in ctx.unconfigured_value_names],
    }


# ───────────────────────── 尚未設定 ≠ 取數失敗（客戶 2026-10-19 裁示 G3） ─────────────────────────
# 客戶 2026-10-19 裁示 G3（`docs/DECISIONS.md` `DEC-2026-10-19-04`，BL-0250 批次 1）：「尚未設定」與「已設定但取數失敗」是不同原因，
# 即使兩者都畫 ⛔，原因文字也不得合併；不得把尚未設定偽裝成已取數後失敗。
# 本段只改**本頁自己擬的**字（結論燈的狀態字與那一句、展開區摘要那一行）：該塊的失敗摘要**全部**屬「尚未設定」那一族、
# 沒有任何真的取數失敗時，那幾處的「取數失敗」改寫成「尚未設定：<哪一項>」。
# ⛔ 不改的（44 字面規定或 44 不能唯一決定，交回總管進 Decision Gate）：卡片 `系統錯誤` 主值「⛔ 取數失敗」（44 第五節第一小節模板）、
#    狀態徽章「取數失敗」（44 第五節第二小節七個字面值的封閉集合）、「⛔ 此區塊暫時無法判定」（之七其二第 3 條逐字）、
#    `MKT-5`／`MKT-6`／`MKT-7` 依 BL-0373 掛的「取數失敗」（之九其二：資料層回報失敗的鍵；未設定金鑰算不算，44 沒有分）。
# 符號照舊：判定（`_state`、`_empty_kind`、`_tone`）一個都不動，紅燈照舊畫 ⛔（44：`系統錯誤` → ⛔）。
_FETCH_WORD = TEXT_FETCH_FAILED
UNCONFIGURED_KEY = "_unconfigured"

# ───────────── BL-0250 批次 3-A：尚未設定的值旁不掛「取數失敗」狀態徽章（客戶 2026-10-19 批次 3 裁示第 2 點） ─────────────
# 客戶原文：「同一值旁不得再同時掛『取數失敗』原因。但真正已執行 fetch／連線後失敗，仍是 ⛔ 取數失敗。兩者原因不得混用。」
# 44 第七節第三小節之十二。只拿掉 `狀態` 那一類、字面為「取數失敗」的那一枚徽章；不新增第八個徽章字面（第五節第二小節七個照舊），
# 也不碰別的徽章。判定（`_state`、`_tone`、`_empty_kind`）一個都不動。混有任何真的取數失敗的節點照舊掛。
_KIND_UNCONFIGURED = "unconfigured"
_KIND_FETCH = "fetch"
_FETCH_BADGE_TEXT = TEXT_FETCH_FAILED
_STATUS_BADGE_KIND = "狀態"
# 值節點上「值」那一格的欄位名（徽章畫在它旁邊）。同一節點其他欄位（例：`MKT-5` 可選項目的停用原因「設定讀不到」）的成因
# 不是那一枚徽章說的事，不拿來判斷（否則會把真的取數失敗那一枚也拿掉）。
_VALUE_FIELDS = frozenset({"value_text", "text"})


def _is_fetch_badge(badge) -> bool:
    return isinstance(badge, dict) and badge.get("_kind") == _STATUS_BADGE_KIND and badge.get("text") == _FETCH_BADGE_TEXT


def _drop_fetch_badge(node: dict) -> None:
    badges = node.get("badges")
    if isinstance(badges, list) and any(_is_fetch_badge(b) for b in badges):
        node["badges"] = [b for b in badges if not _is_fetch_badge(b)]


def _relabel_error_placeholders(node, names) -> None:
    """成因全部是尚未設定的塊（`unconfigured_only` 收的）：`_` 開頭鍵底下那幾個 `系統錯誤` 佔位主值（例：持倉體檢偏離提示卡
    `_placeholder`），字面「⛔ 取數失敗」→「⛔ 尚未設定：<哪一項>」（`names`，不得為空），同一節點上的「取數失敗」狀態徽章拿掉
    （就地改寫）。~~哪一項不寫在這裡（失敗摘要一頁只出現一次）~~ → 總管適用客戶 `DEC-2026-10-19-05` 第 2 點的格式補上哪一項
    （有意識的更正，不是漏刪）；去重後的失敗摘要照舊一頁一次（之七其二第 3 條，`_rewrite` 那一條不動）。
    `_rewrite` 走不到 `_` 開頭鍵底下的字（那裡的字串照規則不碰），所以這一處由本函式補。只換那一句與那一枚，判定照舊。
    ⚠️ 只動那一個佔位節點：同一塊其他節點的徽章說的可能是別的事（例：`MKT-5` 可選項目上的「取數失敗」是那一個指標的取數狀態，
    成因不是本塊的「設定試算表尚未設定」），不得跟著拿掉。"""
    if isinstance(node, dict):
        if node.get("_state") == _ERROR_STATE and any(node.get(f) == LINE_FETCH_FAILED for f in ("text", "value_text")):
            for field in ("text", "value_text"):
                if node.get(field) == LINE_FETCH_FAILED:
                    if not names:
                        raise ValueError("尚未設定的成因沒有對象，不改寫")
                    # ~~`LINE_NOT_CONFIGURED`（只寫狀態族）~~ → 總管適用客戶 `DEC-2026-10-19-05` 第 2 點（格式「⛔ 尚未設定：〈哪一項〉」；
                    # 有意識的更正，不是漏刪；44 第七節第三小節之十二其二）：補上哪一項。舊寫法的用意（哪一項一頁只交代一次，
                    # 之七其二第 3 條）照舊適用於去重後的失敗摘要；被權衡掉的是主值位置不說是哪一項沒設。
                    node[field] = f"{SYMBOL_ERROR} {not_configured_reason(*names)}"
            _drop_fetch_badge(node)
        for value in node.values():
            _relabel_error_placeholders(value, names)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _relabel_error_placeholders(value, names)


_BARE_NOT_CONFIGURED = re.compile(re.escape(LINE_NOT_CONFIGURED) + r"(?!：)")


def _relabel_mixed(block: dict, value_names: dict) -> None:
    """同批稽核回修（BL-0250 批次 3-A；44 第七節第三小節之十二其十第 1 條）：成因混合的塊（同一塊裡既有尚未設定、又有
    真的取數失敗，不在 `unconfigured_only` 裡）（就地改寫）：

    - **代表整塊的收合標題／摘要**（`summary_text`）去重後只剩狀態族「⛔ 尚未設定」→ 照客戶核准推薦 (2)「混合的照寫取數失敗」
      寫「⛔ 取數失敗」；
    - 值那一格自己的成因全部屬尚未設定（`unconfigured_value_nodes`）→「⛔ 尚未設定：<哪一項>」（客戶裁示第 2 點的格式）；
    - 其餘（塊內說明行、依各自成因去重出來的字）一字不動 —— 自身成因是尚未設定的那一行照舊寫「⛔ 尚未設定」。
      ~~其他位置（收合標題、摘要、說明行、混了兩種成因的值）→ 照混合規則寫「⛔ 取數失敗」~~（同批第二次稽核：射程寫太寬，
      總管派工單自身錯誤；有意識的更正，不是漏刪；決策者 AI 總管）。"""
    if isinstance(block.get("summary_text"), str):
        block["summary_text"] = _BARE_NOT_CONFIGURED.sub(LINE_FETCH_FAILED, block["summary_text"])
    _relabel_mixed_values(block, value_names)


def _relabel_mixed_values(node, value_names: dict) -> None:
    """`_walk` 同一套走法（`_` 開頭鍵、受保護的鍵、存檔結果鍵、輸入欄當下值不碰），只換值節點那一格。"""
    if isinstance(node, dict):
        names = value_names.get(id(node))
        for key in list(node):
            value = node[key]
            if plain._protected(key) or key in _SAVE_RESULT_KEYS or (isinstance(key, str) and key.startswith("_")):
                continue
            if key == "value_text" and plain._is_input_field(node):
                continue
            if isinstance(value, str):
                if names and key in _VALUE_FIELDS and value == LINE_NOT_CONFIGURED:
                    node[key] = f"{SYMBOL_ERROR} {not_configured_reason(*names)}"
            else:
                _relabel_mixed_values(value, value_names)
    elif isinstance(node, list):
        for value in node:
            _relabel_mixed_values(value, value_names)


def unconfigured_only(display: dict, summary: dict) -> dict:
    """塊代號 → 尚未設定的對象（只收「失敗摘要全部屬尚未設定那一族、沒有任何真的取數失敗」的 `系統錯誤` 塊）。只讀已記的成因。"""
    out = {}
    for block in display.get("blocks") or ():
        code = block.get("code")
        cause = (summary.get("block_causes") or {}).get(code)
        if not cause or cause["fetch"] or not cause["names"]:
            continue
        if block.get("_layer") == 1:
            continue
        out[code] = list(cause["names"])
    return out


def page_unconfigured_only(display: dict, summary: dict) -> bool:
    """整頁的失敗是不是全部屬「尚未設定」那一族（沒有任何真的取數失敗、也沒有交代不到的 `系統錯誤`）。"""
    return (bool(summary.get("not_configured")) and not summary.get("fetch_failed")
            and not _unexplained_error(display, summary.get("explained_blocks", ()))
            and not any(c["fetch"] for c in (summary.get("block_causes") or {}).values()))


def _swap_fetch_word(text, names) -> str:
    if not isinstance(text, str) or _FETCH_WORD not in text:
        return text
    return text.replace(_FETCH_WORD, not_configured_reason(*names))


def relabel_unconfigured(display: dict, summary: dict) -> dict:
    """客戶 G3：本頁自己擬的「取數失敗」字樣，成因全部是尚未設定時改寫成「尚未設定：<哪一項>」（就地改寫）。回改到的塊代號 → 對象。

    - 層 2～4 的塊（`unconfigured_only` 收的）：展開區摘要那一行（`summary_text`）裡的「取數失敗」；並在塊上記
      `_unconfigured`（給 `sections` 組 ③ 與入口標題時讀；不是判定，只是成因的記號）。
    - 結論燈（層 1）：整頁的失敗全部屬尚未設定時，狀態字「狀態：取數失敗」→「狀態：尚未設定」，燈上那一句與說明行裡的
      「取數失敗」→「尚未設定：<哪幾項>」；不是整頁都屬尚未設定時，只換以「<塊名>：取數失敗」形狀點名、而那一塊屬尚未設定的那一段。
    """
    only = unconfigured_only(display, summary)
    for node in summary.get("unconfigured_value_nodes") or ():   # BL-0250 批次 3-A：尚未設定的值旁不掛「取數失敗」徽章
        _drop_fetch_badge(node)
    value_names = {id(node): names for node, names in zip(summary.get("unconfigured_value_nodes") or (),
                                                           summary.get("unconfigured_value_names") or ())}
    causes = summary.get("block_causes") or {}
    for block in display.get("blocks") or ():
        code = block.get("code")
        cause = causes.get(code) or {}
        if code not in only and cause.get("fetch") and cause.get("names"):
            _relabel_mixed(block, value_names)   # 同批稽核回修：混合成因的塊不留光禿禿的「⛔ 尚未設定」
    titles = {}
    for block in display.get("blocks") or ():
        code = block.get("code")
        if code in only:
            block[UNCONFIGURED_KEY] = list(only[code])
            _relabel_error_placeholders(block, only[code])   # BL-0250 批次 3-A
            summary_text = block.get("summary_text")
            if summary_text == LINE_NOT_CONFIGURED:   # 去重後只剩狀態族的摘要：補上哪一項
                summary_text = f"{SYMBOL_ERROR} {not_configured_reason(*only[code])}"
            block["summary_text"] = _swap_fetch_word(summary_text, only[code])
            # 說明行裡以「取數失敗」起頭的那一句（本頁擬的空狀態句，例：標的探索篩選軌跡「取數失敗，暫無篩選軌跡」）。
            if isinstance(block.get("detail_lines"), list):
                block["detail_lines"] = [
                    _swap_fetch_word(line, only[code]) if isinstance(line, str) and line.startswith(_FETCH_WORD) else line
                    for line in block["detail_lines"]
                ]
            titles[block.get("title")] = only[code]
    page_only = page_unconfigured_only(display, summary)
    names = list(summary.get("not_configured") or ())
    for block in display.get("blocks") or ():
        if block.get("_layer") != 1:
            continue
        if page_only:
            word = block.get("state_word")
            if isinstance(word, str) and word.endswith(_FETCH_WORD):
                block["state_word"] = word[: -len(_FETCH_WORD)] + TEXT_NOT_CONFIGURED
            for field in ("text", "summary_text"):
                if block.get(field) in (TEXT_NOT_CONFIGURED, LINE_NOT_CONFIGURED):   # 只剩狀態族：補上哪幾項
                    block[field] = not_configured_reason(*names)
                block[field] = _swap_fetch_word(block.get(field), names)
            for field in ("lines", "detail_lines"):
                if isinstance(block.get(field), list):
                    block[field] = [_swap_fetch_word(line, names) for line in block[field]]
            trim_light_echo(block)
        elif titles and isinstance(block.get("text"), str):
            parts = block["text"].split("；")
            for index, part in enumerate(parts):
                title, sep, rest = part.partition("：")
                if sep and rest == _FETCH_WORD and title in titles:
                    parts[index] = f"{title}：{not_configured_reason(*titles[title])}"
            block["text"] = "；".join(parts)
        if titles and not page_only and isinstance(block.get("lines"), list):
            # 同批稽核回修（G3 同一條規則套到燈的說明行）：「<塊名>、<塊名>：取數失敗。」那一句一次點名多塊，其中屬尚未設定的塊
            # 分開寫「<塊名>：尚未設定：<哪一項>」，其餘照寫「取數失敗」（原本整句寫取數失敗，與卡上主值的成因不一致）。
            block["lines"] = [_split_named_line(line, titles) for line in block["lines"]]
    return only


def _split_named_line(line, titles: dict):
    """「A、B、C：取數失敗。」→ 依成因分段（相鄰同一種成因合併）：例「A：尚未設定：X；B、C：取數失敗。」。不是這個形狀、
    或沒有一塊屬尚未設定 → 原樣。"""
    if not isinstance(line, str) or not line.endswith(f"：{_FETCH_WORD}。"):
        return line
    named = line[: -len(f"：{_FETCH_WORD}。")].split("、")
    if not any(name in titles for name in named):
        return line
    groups: list = []
    for name in named:
        key = tuple(titles[name]) if name in titles else None
        if groups and groups[-1][0] == key:
            groups[-1][1].append(name)
        else:
            groups.append((key, [name]))
    parts = [f"{'、'.join(names)}：{not_configured_reason(*key) if key else _FETCH_WORD}" for key, names in groups]
    return "；".join(parts) + "。"


# ───────────────────────── 結論燈：同一則訊息不印兩次（Phase 3 P1-④） ─────────────────────────

# 狀態字的前綴（持倉體檢、資產配置的 `state_word` 自帶；標的探索的 `state_word` 不帶、由 `page.py` 補）。
LIGHT_STATE_PREFIX = "狀態："


def trim_light_echo(block: dict) -> bool:
    """結論燈（①）右側那一句若以燈自己的圖示開頭，就把那個圖示拿掉；拿掉後剩下的字若與狀態字相同，整句不畫（就地改寫）。
    回「有沒有改」。

    例：資產配置設定試算表讀不到時，燈畫「⛔ 狀態：取數失敗 ⛔ 尚未設定」→「⛔ 狀態：取數失敗 尚未設定」；
    取數失敗時「⛔ 狀態：取數失敗 ⛔ 取數失敗」→「⛔ 狀態：取數失敗」。
    依據：⛔ 那幾句 —— 58 U-31「同一則原文重複印多次本身是錯，可視為修正錯誤」、44 第七節第三小節之七其二第 3 條
    （同源失敗一頁只摘要一次）、59 線框第 1.1 節（同源錯誤只在資料狀態行與 ① 各出現一次）。
    ⬜ 那幾句（「⬜ 資料未備」「⬜ 不適用…」）只依 58 U-31 的一般原則做呈現去重，**不屬於** 44 其二第 3 條
    （那一條只管同源的系統錯誤）。44 其四的 ◇ 落地後，資料未備的句首改成 ◇、與燈的 ⬜ 不同，本規則對資料未備不再觸發。

    變動範圍（2026-10-17 量測，只對下列兩組情境成立，不宣稱窮舉）：
    - `tests/ui_v2/_plain_scan.py` 的正式模式畫面：資產配置「未設定」「未設定保單」「取數失敗」「局部失敗」四個情境、
      持倉體檢「超過10日」，共 5 處。
    - `tests/ui_v2/test_plain_logic.py::_all_models()` 的正式模型：持倉體檢「⬜ 資料未備」9 個（full/21、srcmiss/21、
      bizexc/21、noexceed/21、other_window/21、onenav/21、tiedstate/10、tiedstate/21、full_then_badrange/21）、
      持倉體檢「⬜ 不適用」2 個（bizexc/10、onenav/10）、資產配置 nobasis、nofx 兩個 ⬜，
      資產配置 holdfail、fxfail、settingfail 三個「⛔ 取數失敗」整句不畫，共 16 處。
    → 2026-10-17 ◆／◇ 小批落地後（狀態更新，不是漏刪）：正式模式的「⬜ 資料未備」在本函式之前已改成「◇ 資料未備」，
      上列持倉體檢「⬜ 資料未備」9 處自此不再觸發（燈仍是 ⬜、句首是 ◇）；其餘各處照舊。上列量測值在寫下當時為真。

    只動 `text` 這一個顯示字串：`glyph`、`state_word`、`_tone`、`_state` 與任何判定一個都不碰（護欄 2）；
    圖示不同（例：燈 ⬜、句首 ◇）不動；句首沒有圖示不動。
    """
    glyph, text, word = block.get("glyph"), block.get("text"), block.get("state_word")
    if not (isinstance(glyph, str) and glyph.strip() and isinstance(text, str)):
        return False
    head = f"{glyph} "
    if not text.startswith(head):
        return False
    rest = text[len(head):].strip()
    payload = word[len(LIGHT_STATE_PREFIX):] if isinstance(word, str) and word.startswith(LIGHT_STATE_PREFIX) else word
    block["text"] = "" if rest == payload else rest
    return True


# ───────────────────────── 資料未備（◇）的判定：沿用模型既有的狀態 ─────────────────────────


def has_missing(node) -> bool:
    """模型裡有沒有 `資料未備`（`_state`）或 `來源缺`／`部分缺`（`_empty_kind`）。只讀既有判定，不新算。"""
    if isinstance(node, dict):
        if node.get("_state") in _MISSING_STATES or node.get("_empty_kind") in _MISSING_EMPTY_KINDS:
            return True
        return any(has_missing(v) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(has_missing(v) for v in node)
    return False


def has_missing_marker(node, private: bool = False) -> bool:
    """模型裡有沒有畫成 `◇` 的資料未備：logic 記為資料未備的缺值格（`_missing_cells`／`_missing_fields` 列出的格，
    經 `symbols` 換成 `◇`），或給人看的字串裡有「◇ 資料未備」。只讀既有判定與已畫出的符號，不新算。

    給資產配置用（BL-0250 批次 1，`DEC-2026-10-19-04`）：資產配置的資料未備大多寫在表格格內與列尾
    （例：`ALO-2` 某類別目標比重留空 → 「◇ 資料未備」、`ALO-6` 缺基準值的格 → `◇`），沒有 `_state`，
    `has_missing` 讀不到，資料狀態行因此漏報 ◇（44 第七節第三小節之七其二第 4 條：四頁都要報）。"""
    if isinstance(node, dict):
        for cell in node.get("_missing_cells") or ():
            if node.get(cell) == SYMBOL_MISSING:
                return True
        labels = set(node.get("_missing_fields") or ())
        for field in node.get("_fields") or ():
            if isinstance(field, tuple) and len(field) == 2 and field[0] in labels and field[1] == SYMBOL_MISSING:
                return True
        if node.get("_empty_kind") in _MISSING_EMPTY_KINDS:
            return True
        for key, value in node.items():
            under = private or (isinstance(key, str) and key.startswith("_"))
            if isinstance(value, str):
                if not under and _MISSING_LINE in value:
                    return True
            elif has_missing_marker(value, under):
                return True
        return False
    if isinstance(node, (list, tuple)):
        for item in node:
            if isinstance(item, str):
                if not private and _MISSING_LINE in item:
                    return True
            elif has_missing_marker(item, private):
                return True
    return False


def has_error_state(node) -> bool:
    """模型裡有沒有 `系統錯誤`（`_state` 或 `_empty_kind`）。"""
    if isinstance(node, dict):
        if node.get("_state") == _ERROR_STATE or node.get("_empty_kind") == _ERROR_STATE:
            return True
        return any(has_error_state(v) for v in node.values())
    if isinstance(node, (list, tuple)):
        return any(has_error_state(v) for v in node)
    return False


def _unexplained_error(display: dict, explained) -> bool:
    """有沒有 `系統錯誤` 的塊，畫面上一句失敗摘要都沒有（那一塊的錯誤，狀態行的類別句與尚未設定句都沒有交代到）。"""
    # 層 1 的結論燈不算：燈不自己取數，它的 `系統錯誤` 來自同頁其他塊（44 第二節），那幾塊自己會被數到。
    explained = set(explained)
    return any(_block_is_error(block) and block.get("_layer") != 1 and block.get("code") not in explained
               for block in display.get("blocks") or ())


def latest_date(rows, key):
    """一串 dict 裡 `key` 欄（ISO 日期字串）最晚的那一天，`YYYY-MM-DD`；一筆都沒有 → None。不合格的值跳過（不猜）。"""
    best = None
    for row in rows or ():
        raw = row.get(key) if isinstance(row, dict) else None
        if not isinstance(raw, str) or len(raw) < 10:
            continue
        try:
            day = date.fromisoformat(raw[:10])
        except ValueError:
            continue
        if best is None or day > best:
            best = day
    return best.isoformat() if best else None


# ───────────────────────── 資料狀態行 ─────────────────────────


def status_line(display: dict, summary: dict, *, as_of, stale: bool = False, missing: bool = False) -> dict:
    """資料狀態行的內容（給 `health_view.render_status_line` 畫）。

    `missing`：呼叫端另外確認過的資料未備（資產配置傳 `has_missing_marker`；BL-0250 批次 1）。與 `has_missing` 取聯集。

    回 `{"items": [(符號或空字串, 文字, 色調), ...], "as_of": "YYYY-MM-DD" 或 "—", "text": 整行純文字}`。
    `items` 依 ◷ → ◇ → ⛔ → 尚未設定 排；同類只一筆。`items` 為空 ⇒ 只寫資料截至日（不寫「資料齊」「正常」）。
    """
    items = []
    if stale:
        items.append((SYMBOL_STALE, TEXT_STALE, "中性"))
    if missing or has_missing(display):
        items.append((SYMBOL_MISSING, TEXT_MISSING, "灰"))
    # ⛔ 與「尚未設定」各自獨立判斷（不因為有尚未設定就省掉 ⛔）：有取數失敗的類別 → 列類別；
    # 沒有類別、但有 `系統錯誤` 的塊在畫面上沒有任何一句失敗摘要（取數失敗或尚未設定都沒有）→ 照樣報 ⛔ 取數失敗。
    if summary["fetch_failed"]:
        items.append((SYMBOL_ERROR, f"{TEXT_FETCH_FAILED}：{'、'.join(summary['fetch_failed'])}", "紅"))
    elif _unexplained_error(display, summary.get("explained_blocks", ())):
        items.append((SYMBOL_ERROR, TEXT_FETCH_FAILED, "紅"))
    if summary["not_configured"]:
        items.append(("", f"{TEXT_NOT_CONFIGURED}：{'、'.join(summary['not_configured'])}", "中性"))
    as_of_text = as_of or AS_OF_UNKNOWN
    tail = f"{AS_OF_LABEL} {as_of_text}"
    if items:
        body = "　".join(f"{symbol} {text}".strip() for symbol, text, _tone in items)
        text = f"{STATUS_LABEL}{body}　·　{tail}"
    else:
        text = tail
    return {"items": items, "as_of": as_of_text, "text": text}


# ───────────────────────── 核心卡的來源與新鮮度徽章 → ④「證據／來源」 ─────────────────────────

_PROVENANCE_KINDS = frozenset({"來源", "新鮮度"})


def _is_provenance(badge) -> bool:
    return isinstance(badge, dict) and badge.get("_kind") in _PROVENANCE_KINDS


# 新鮮度徽章「畫成黃的那一段」（44 第五節第二小節新鮮度列、第七節第三小節之七其四表）：色調沿用各頁 logic／live 交出的
# `_tone`，本模組不新算、不看日數。
_STALE_TONE = "黃"


def _is_stale_badge(badge) -> bool:
    return isinstance(badge, dict) and badge.get("_kind") == "新鮮度" and badge.get("_tone") == _STALE_TONE


def _stale_marker(badge) -> dict:
    """留在 ② 卡上的那一枚：同一枚徽章（同色調、同類別）、文字前加 `◷ `（44 既有字面，例「◷ 延遲 N 日」）。"""
    marker = dict(badge)
    text = str(badge.get("text", ""))
    marker["text"] = text if text.startswith(f"{SYMBOL_STALE} ") else f"{SYMBOL_STALE} {text}"
    return marker


def move_card_provenance(display: dict, codes) -> list:
    """把 `codes` 那幾塊（② 核心卡）上的來源／新鮮度徽章拿下來（就地改寫），回 ④ 要畫的列：
    `[(卡名, 項目名, [徽章文字…]), ...]`，依卡、依主值／逐檔分組的順序。④ 那份的徽章文字不改字。

    拿的位置：塊層級 `badges`、主值 `main_values[*].badges`、逐檔分組 `fund_groups[*].freshness_badge`。
    ⚠️ 例外（44 第七節第三小節之七其二第 4 條「延遲的值在 ② 卡上保留 ◷ 記號」）：新鮮度徽章依既有色調畫成**黃**的那一枚，
    卡上**留一枚** `◷ <原字面>`（同色調）；中性與灰色的不留。④ 照樣列原字面（換位置，不刪除）。
    """
    def split(badges):
        keep, moved = [], []
        for badge in badges or ():
            if _is_provenance(badge):
                moved.append(badge)
                if _is_stale_badge(badge):
                    keep.append(_stale_marker(badge))
            else:
                keep.append(badge)
        return keep, moved

    rows = []
    for block in display.get("blocks") or ():
        if block.get("code") not in codes:
            continue
        title = block.get("title", "")
        keep, moved = split(block.get("badges"))
        if moved:
            rows.append((title, "", [b["text"] for b in moved]))
            block["badges"] = keep
        for value in block.get("main_values") or ():
            keep, moved = split(value.get("badges"))
            if moved:
                rows.append((title, value.get("label", ""), [b["text"] for b in moved]))
                value["badges"] = keep
        for group in block.get("fund_groups") or ():
            badge = group.get("freshness_badge")
            if _is_provenance(badge):
                rows.append((title, group.get("head_text", ""), [badge["text"]]))
                group["freshness_badge"] = _stale_marker(badge) if _is_stale_badge(badge) else None
    return rows


def has_stale_marker(display: dict, codes) -> bool:
    """`codes` 那幾塊（② 卡）上有沒有 `move_card_provenance` 留下的 `◷` 徽章（給資料狀態行的 `stale`）。"""
    for block in display.get("blocks") or ():
        if block.get("code") not in codes:
            continue
        badges = list(block.get("badges") or ())
        for value in block.get("main_values") or ():
            badges += list(value.get("badges") or ())
        for group in block.get("fund_groups") or ():
            badges.append(group.get("freshness_badge"))
        if any(_is_stale_badge(b) and str(b.get("text", "")).startswith(f"{SYMBOL_STALE} ") for b in badges):
            return True
    return False


def mark_last_valid(display: dict, codes, prefix: str) -> bool:
    """② 卡上「只顯示最後有效資料」那一類副標（`freshness_note`，中性色、文字以 `prefix` 起頭）前加 `◷ `（就地改寫）。
    回「有沒有這一類」（給資料狀態行的 `stale`）。只認中性色那一種：灰色那一種是超過門檻的資料未備（`◇`）。
    """
    found = False

    def visit(node):
        nonlocal found
        if isinstance(node, dict):
            note = node.get("freshness_note")
            text = str(note.get("text", "")) if isinstance(note, dict) else ""
            marked = text.startswith(f"{SYMBOL_STALE} ")
            if note and note.get("_tone") == "中性" and (text[2:] if marked else text).startswith(prefix):
                found = True
                if not marked:
                    note["text"] = f"{SYMBOL_STALE} {text}"
            for value in node.values():
                visit(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                visit(value)

    for block in display.get("blocks") or ():
        if block.get("code") in codes:
            visit(block)
    return found


# ───────────────────────── 整頁載入失敗（BL-0362；Phase 3 P1-⑤） ─────────────────────────


def load_failure_line(exc: BaseException, mask_error, fetch_failed_text) -> str:
    """正式模式 `load_live()` 拋例外時那一行原文：「⛔ 取數失敗：<型別>：<遮蔽後訊息>」（給設定與診斷頁的進階診斷）。

    組法照持倉體檢既有的 `ui_v2/hld/page.py::_live_error_line`（總管 2026-10-03 裁定）：型別名與訊息都經 `mask_error`。
    `fetch_failed_text`：該頁 `logic.fetch_failed_text`（44 第五節第五小節 `系統錯誤` 那一列的模板；本模組不另寫一份）。
    退路（**不往外拋** —— 往外拋就是整段 Traceback）：沒有遮蔽函式（`mask_error is None`）、`str(exc)` 本身拋、
    遮蔽拋、或回傳非字串 ⇒ 只寫例外型別，**不帶任何訊息內容**（沒有遮蔽過的原文不收進進階診斷）。
    沒有遮蔽函式時只寫型別，是本組擬定（44／59 沒有寫；理由：進階診斷的說明句寫「原文已遮蔽憑證」）。
    """
    type_name = type(exc).__name__
    if mask_error is None:
        return fetch_failed_text(type_name)
    try:
        masked_type = mask_error(type_name)
        masked = mask_error(str(exc))
        if not isinstance(masked_type, str) or not isinstance(masked, str):
            raise TypeError("mask_error 應回傳字串")
    except Exception:  # noqa: BLE001 —— 不是吞：照樣組出錯誤行，只是不帶訊息內容
        return fetch_failed_text(type_name)
    return fetch_failed_text(f"{masked_type}：{masked}")


# ───────────────────────── 兩鍵一起存、兩鍵都失敗（BL-0177） ─────────────────────────


def both_keys_save_failed(display: dict, code: str, keys, save_errors, where: str):
    """資產配置一枚存檔寫兩鍵的塊（ALO-1、ALO-4）兩鍵都沒存進去時：卡片層那一行改成「儲存失敗」（就地改寫），
    兩鍵的原文各一筆交給進階診斷。回 `[{"where", "text"}, ...]`；不是兩鍵都失敗 → 回空清單、一個字都不動。

    `save_errors`：`{鍵: 原文}`（`ui_v2/alo/page.py` 交給 logic 的同一份）。只看 `keys` 這兩鍵。
    """
    errors = dict(save_errors or {})
    keys = tuple(keys)
    if len(keys) != 2 or not all(errors.get(key) for key in keys):
        return []
    for block in display.get("blocks") or ():
        if block.get("code") == code:
            lines = list(block.get("error_lines") or ())
            block["error_lines"] = [
                TEXT_SAVE_FAILED_BOTH if line.startswith(_ALO_SAVE_FAILED_PREFIX) else line for line in lines
            ]
    return [{"where": where, "text": f"{_ALO_SAVE_FAILED_PREFIX}{key}：{errors[key]}"} for key in keys]


# ───────────────────────── 各頁資料狀態總表的原因項目（BL-0250 批次 3-B） ─────────────────────────
# 總管 2026-10-19 裁定 (a)(b)(c) 與第二輪裁定第 1～5 點；44 第七節第三小節之十三。原則：**總表只彙整各頁已經畫出來的狀態，
# 不重新判一次符號**。本段只讀：一般畫面模型上既有的狀態（`_state`／`_empty_kind`／缺格標記／「◇ 資料未備」字樣／「取數失敗」
# 結構標記／尚未設定的成因）與產生處寫在同一個節點上的資料類標記（`ui_v2/page_health.py` 的 `FETCH_CLASSES_KEY` 等）。
# 判定、符號、畫面字一個都不改。

_UNREADABLE_STATES = frozenset({_ERROR_STATE, "資料未備"})
_UNREADABLE_EMPTY = frozenset({_ERROR_STATE, "來源缺", "部分缺"})
_LABEL_KEYS = ("label", "head_text", "indicator_key", "bucket_text", "fund_text", "fund_code", "key_text")
_STATUS_MISSING_BADGE = "資料未備"


# 尚未設定的對象 → 它擋住的是哪一類資料（`plain._KNOWN_MESSAGES` 那一張表本來就寫了；`None` ＝ 那一張表沒寫，明細表寫「—」不猜）。
_UNCONFIGURED_CLASS = {not_configured_name(state): cls for _message, cls, state in plain._KNOWN_MESSAGES}


class MissingClassError(ValueError):
    """畫成 ◇ 的節點沒有在產生處寫資料類，也沒有標為衍生（總管第二輪裁定第 1 點：找不到類別就報錯，不靠略過）。"""


def _node_label(node) -> str:
    for key in _LABEL_KEYS:
        value = node.get(key) if isinstance(node, dict) else None
        if isinstance(value, str) and value:
            return value
    return ""


def _own_missing_markers(node: dict, private: bool) -> bool:
    """這一個 dict **自己**有沒有畫成 ◇ 的地方（不看子節點）。讀法與 `has_missing`／`has_missing_marker` 相同，
    另加狀態徽章「資料未備」（例：市場總覽指標清單的可選項目）。"""
    if node.get("_state") in _MISSING_STATES or node.get("_empty_kind") in _MISSING_EMPTY_KINDS:
        return True
    for cell in node.get("_missing_cells") or ():
        if node.get(cell) == SYMBOL_MISSING:
            return True
    labels = set(node.get("_missing_fields") or ())
    for field in node.get("_fields") or ():
        if isinstance(field, tuple) and len(field) == 2 and field[0] in labels and field[1] == SYMBOL_MISSING:
            return True
    for badge in node.get("badges") or ():
        if isinstance(badge, dict) and badge.get("_kind") == _STATUS_BADGE_KIND and badge.get("text") == _STATUS_MISSING_BADGE:
            return True
    # `private`：這一層在 `_` 開頭的鍵底下 —— 只有表格列與格（`_ROW_KEYS`）與佔位（`_placeholder`）那幾種會上畫面
    # （例：資產配置目標修改紀錄那一列的「◇ 資料未備：尚未設定過」），其餘（例：`_values` 的計算中間值）不看。
    if private and private not in _RENDERED_PRIVATE:
        return False
    for key, value in node.items():
        if isinstance(key, str) and key.startswith("_"):
            continue
        if _missing_string(value):
            return True
        if isinstance(value, (list, tuple)) and any(_missing_string(v) for v in value):
            return True
    return False


def _missing_string(value) -> bool:
    """一句畫成 ◇ 的字：含「◇ 資料未備」，或以 ◇ 起頭（3-B 第二輪稽核回修可選 2：例「◇ 另有 N 檔淨值超過 10 日未更新…」，
    畫在 `HLD-1` 的 `tail_lines`、`HLD-6` 的 `detail_lines` 等各種 lines 欄位）。"""
    return isinstance(value, str) and (_MISSING_LINE in value or value.startswith(f"{SYMBOL_MISSING} "))


_RENDERED_PRIVATE = _ROW_KEYS | {"_placeholder", "_columns", "_fields"}


def _walk_nodes(node, block, path, out, private=None):
    """一般畫面模型裡每一個 dict：`(dict, 所在的塊, 路徑, 最近一層 _ 開頭的鍵〔沒有 → None〕)`。"""
    if isinstance(node, dict):
        if isinstance(node.get("code"), str) and node.get("code") in plain.BLOCK_NAMES:
            block = node
        out.append((node, block, path, private))
        for key, value in node.items():
            if isinstance(value, (dict, list, tuple)):
                under = private
                # 進入 `_` 開頭的鍵：目前還在會上畫面的位置時，記下這一層的鍵；已經在不上畫面的位置底下就一直不上畫面。
                if isinstance(key, str) and key.startswith("_") and (private is None or private in _RENDERED_PRIVATE):
                    under = key
                _walk_nodes(value, block, f"{path}.{key}", out, under)
    elif isinstance(node, (list, tuple)):
        for index, value in enumerate(node):
            _walk_nodes(value, block, f"{path}[{index}]", out, private)


def _label_map(node, out=None, prefix=""):
    """明細表「項目」欄用的名字：`id(dict)` → 名字。一檔的列或群組（帶 `_fund_code` 的 dict）底下的每一格，名字前面接那一檔
    （群組的標頭字，例「基金 B · 幣別 USD」；沒有標頭字就寫代碼，例「G07」），同一欄多檔出問題各成一列、不去重成一列
    （3-B 稽核回修第 7 條）。不在任何一檔底下 → 照舊取節點自己的名字。"""
    if out is None:
        out = {}
    if isinstance(node, dict):
        own = _node_label(node)
        if isinstance(node.get("_fund_code"), str) and node.get("_fund_code"):
            prefix = own or node["_fund_code"]
            out[id(node)] = prefix
        else:
            out[id(node)] = f"{prefix} {own}" if prefix and own and own != prefix else (own or prefix)
        for value in node.values():
            if isinstance(value, (dict, list, tuple)):
                _label_map(value, out, prefix)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _label_map(value, out, prefix)
    return out


def _check_mapped(block, path, values) -> None:
    for value in values:
        if page_health.is_unmapped(value):
            raise MissingClassError(f"{(block or {}).get('code')} {path}：資料類查表沒有收錄 {value[len(page_health.UNMAPPED_PREFIX):]!r}")


_BOX = "⬜"


def drawn_box(node) -> bool:
    """這個節點在頁上畫的是 ⬜（值那一格的字以 ⬜ 起頭）。總表只彙整頁上已畫的狀態、不重判（之十三其五之四），⬜ 不計數
    （3-B 第二輪稽核回修 B；客戶：不得重新定義 ⬜）。"""
    if not isinstance(node, dict):
        return False
    texts = [node.get(k) for k in _VALUE_FIELDS if isinstance(node.get(k), str)]
    return bool(texts) and any(t.startswith(_BOX) for t in texts) and not any(
        t.startswith((f"{SYMBOL_MISSING} ", f"{SYMBOL_ERROR} ")) for t in texts)


def boxed_entries(display: dict) -> list:
    """明細表「沒有異常」那幾列之外，頁上畫成 ⬜、產生處卻記了資料未備的那幾處（例：標的探索篩選判定格「⬜ 無法判定（…）」）：
    不計數，狀態欄照抄頁上那一句 ⬜（3-B 第二輪稽核回修 B）。資料類取自產生處記的鍵（使用者設定的鍵寫使用者設定）。"""
    nodes = []
    _walk_nodes(display, None, "", nodes)
    labels = _label_map(display)
    out = []
    for node, block, _path, private in nodes:
        if block is None or not drawn_box(node) or not _own_missing_markers(node, private) or node.get(page_health.DERIVED_KEY):
            continue
        keys = node.get(page_health.MISSING_KEYS_KEY) or ()
        _check_mapped(block, _path, keys)   # 查表未收錄的鍵照樣報錯，由錯誤邊界接住（第一輪回修第 2 條）
        classes = list(dict.fromkeys(plain.TABLE_NAMES["user_setting"] if k in page_health.SETTING_KEYS else k
                                     for k in keys))
        text = next(node.get(k) for k in _VALUE_FIELDS if isinstance(node.get(k), str) and node.get(k).startswith(_BOX))
        out.append(page_health.affected(block.get("title", ""), labels.get(id(node), _node_label(node)),
                                        data_class="、".join(classes) or None, status=text))
    return out


def _unreadable(node, block) -> bool:
    target = node if isinstance(node, dict) else block
    return (target.get("_state") in _UNREADABLE_STATES or target.get("_empty_kind") in _UNREADABLE_EMPTY
            or (target is block and _block_is_error(block)))


_ORDER_BLOCK = 10000
_ORDER_SHADOWED = 5000


def collect_page_items(display: dict, summary: dict, fetch_events, cards, *, trace=None) -> tuple:
    """一般畫面模型（`dedupe_failures` 與 `relabel_unconfigured` 之後、`move_card_provenance` 之前）→ `(原因項目, 認不出資料類的取數失敗)`。

    - `fetch_events`：`plain.plain_model` 交出的每一句取數失敗與它產生處記的資料類；`cards`：本頁 ② 核心卡的塊代號。
    - 尚未設定：`summary["block_causes"]` 與結構標記 `_unconfigured`；鍵＝尚未設定的對象。
    - 取數失敗：`fetch_events` 與結構標記 `FETCH_CLASS_KEY`；鍵＝產生處記的資料類。認不出 → 鍵記 `plain.DATA_CLASS_DEFAULT`
      並列進第二個回傳值（總管第二輪裁定第 4 點：逐處列出，不猜）。
    - 資料未備：畫成 ◇ 的節點；鍵＝產生處記的 `MISSING_KEYS_KEY`；標為衍生的不計數；兩者都沒有 → `MissingClassError`。
    - 同順位比到第三步時的「該頁固定順序」＝這個原因第一次出現的那一塊在本頁塊序（`display["blocks"]` 的順序，即 44 的塊序）裡的位置
      （總管第二輪裁定第 5 點：由塊序產生，不手寫）。
    不是最新（◷）不在這裡：它要在 `move_card_provenance` 之後才看得到，見 `stale_items`。
    頁上畫成 ⬜ 的節點不計數（3-B 第二輪稽核回修 B），明細照抄那一句，見 `boxed_entries`。
    `trace`：給守衛用 —— 傳一個 list 進來，每收下一處就記 `(id(節點), 種類, 鍵)`。
    """
    blocks = list(display.get("blocks") or ())
    order = {block.get("code"): index for index, block in enumerate(blocks)}
    cards = set(cards)
    items, unresolved = [], []
    labels = _label_map(display)

    def entry(block, node, *, data_class=None, unreadable=None):
        code = (block or {}).get("code")
        core = code in cards
        hit = _unreadable(node, block) if unreadable is None else unreadable
        # 3-B 稽核回修第 4 條：~~`unreadable=core and hit`~~ —— 讀不到照實記，不論是不是核心卡；件數只數核心卡
        # （`page_health.main_unreadable_cards`）。第 7 條：一檔底下的格，名字前面接那一檔（`_label_map`）。
        label = "" if node is block else labels.get(id(node), _node_label(node))
        return page_health.affected((block or {}).get("title", ""), label, core=core, unreadable=hit,
                                    data_class=data_class)

    seq = {}

    def add(kind, key, block, node, *, data_class=None, unreadable=None, retreat=None, shadowed=False, no_retreat=()):
        # 該頁固定順序：塊序在前；同一塊之內（3-B 稽核回修第 5 條）畫面上寫出的成因依收下的先後（＝該塊畫出的次序），
        # 被蓋住、沒畫出的成因一律排在畫出的之後（`_ORDER_SHADOWED`）。
        code = (block or {}).get("code")
        n = seq[code] = seq.get(code, -1) + 1
        rank = order.get(code, len(blocks)) * _ORDER_BLOCK + (_ORDER_SHADOWED if shadowed else 0) + n
        if trace is not None:
            trace.append((id(node), kind, key))
        items.append(page_health.make_item(
            kind, key, [entry(block, node, data_class=data_class, unreadable=unreadable)],
            lamp=(block or {}).get("_layer") == 1, order=rank, retreat=retreat, no_retreat=no_retreat))

    by_code = {block.get("code"): block for block in blocks}
    nodes = []
    _walk_nodes(display, None, "", nodes)

    # 尚未設定
    named_values = {}
    for node, names in zip(summary.get("unconfigured_value_nodes") or (), summary.get("unconfigured_value_names") or ()):
        for name in names:
            named_values.setdefault(name, set()).add(id(node))
    for code, cause in (summary.get("block_causes") or {}).items():
        block = by_code.get(code)
        if block is None:
            continue
        for name in cause["names"]:
            ids = named_values.get(name, set())
            value_hit = any(id(node) in ids for node, owner, _path, _private in nodes if owner is block)
            add(page_health.KIND_UNCONFIGURED, name, block, block, data_class=_UNCONFIGURED_CLASS.get(name),
                unreadable=value_hit or _block_is_error(block))
    for node, block, _path, _private in nodes:
        name = node.get(page_health.UNCONFIGURED_KEY)
        if isinstance(name, str) and name and block is not None:
            add(page_health.KIND_UNCONFIGURED, name, block, node, data_class=_UNCONFIGURED_CLASS.get(name), unreadable=True)

    # 取數失敗
    for event in fetch_events or ():
        if any(f in _SAVE_RESULT_KEYS for f in event.get("fields") or ()):
            continue   # 按「存檔」的逐鍵結果是寫入結果，不是讀取失敗（同 `_SAVE_RESULT_KEYS`）
        block = by_code.get(event.get("code"))
        if block is None or not _shown(block, event.get("field")):
            continue
        container = event.get("container")
        node = container if isinstance(container, dict) else block
        classes = tuple(event.get("data_classes") or ())
        _check_mapped(block, event.get("field"), classes)
        if not classes:
            unresolved.append({"code": event.get("code"), "field": event.get("field"), "raw": event.get("raw")})
            classes = (plain.DATA_CLASS_DEFAULT,)
        retreat = ({"day": event["retreat_day"], "codes": [event["fund"]] if event.get("fund") else []}
                   if event.get("retreat_day") else None)
        # 3-B 第二輪稽核回修 A：逐檔的取數失敗沒有預存可退 → 記下代碼（同一類有退回預存時，主要原因句尾點名「沒有預存淨值」）。
        no_retreat = (event["fund"],) if event.get("fund") and not event.get("retreat_day") else ()
        for data_class in classes:
            add(page_health.KIND_FETCH, data_class, block, node, data_class=data_class, retreat=retreat,
                no_retreat=no_retreat)
    for node, block, path, _private in nodes:
        data_class = node.get(page_health.FETCH_CLASS_KEY)
        if isinstance(data_class, str) and data_class and block is not None:
            _check_mapped(block, path, (data_class,))
            add(page_health.KIND_FETCH, data_class, block, node, data_class=data_class, unreadable=True)

    # 被蓋住的成因（3-B 稽核回修第 5 條）：同一塊另一個成因的那一句畫在畫面上，這一個沒畫出來，但它一樣讓這一塊讀不到。
    # 原文屬「尚未設定」那一族 → 尚未設定、鍵＝尚未設定的對象；否則 → 取數失敗、鍵＝產生處記的資料類。
    for node, block, path, _private in nodes:
        for message, data_class in node.get(page_health.SHADOWED_KEY) or ():
            if block is None:
                continue
            _check_mapped(block, path, (data_class,))
            state = plain.not_configured_state(message)
            if state:
                name = not_configured_name(state)
                add(page_health.KIND_UNCONFIGURED, name, block, node,
                    data_class=_UNCONFIGURED_CLASS.get(name), unreadable=True, shadowed=True)
            else:
                add(page_health.KIND_FETCH, data_class, block, node, data_class=data_class, unreadable=True, shadowed=True)

    # 資料未備
    for node, block, path, private in nodes:
        if block is None or not _own_missing_markers(node, private):
            continue
        if node.get(page_health.DERIVED_KEY) or drawn_box(node):
            continue
        keys = node.get(page_health.MISSING_KEYS_KEY)
        if not keys:
            raise MissingClassError(f"{block.get('code')} {path}：畫成 ◇，產生處沒有寫資料類，也沒有標為衍生")
        _check_mapped(block, path, keys)
        for key in keys:
            # 客戶 2026-10-20 裁示 Q1（`docs/DECISIONS.md` `DEC-2026-10-20-01`；44 第七節第三小節之十三其八第 23 條）：
            # 使用者自己的參數留空（產生處記的鍵是設定的中文名：目標比重、情境試算金額、容許帶、篩選條件）不計入資料狀態件數、
            # 不進主要原因、也不列進明細（資料健康 ≠ 使用者輸入）。~~計為 ◇ 資料未備、鍵用該設定的中文名~~（總管第二輪裁定第 2 點
            # 「本批照頁面現況計數」，待客戶確認；有意識的政策變更，不是漏刪；決策者：客戶）。頁上那一格照舊畫 ◇，產生處的記號照舊。
            # 一格兩種成因（裁定第 3 點）只略過設定那一個鍵，基準值缺的那一類照算。
            if key in page_health.SETTING_KEYS:
                continue
            # ~~`data_class = plain.TABLE_NAMES["user_setting"] if key in page_health.SETTING_KEYS else key`~~：
            # 設定鍵已在上一行略過，那一支成了死分支（同批獨立稽核可選 (c)；行為不變，有意識的更正，不是漏刪）。
            add(page_health.KIND_MISSING, key, block, node, data_class=key, unreadable=True)
    return page_health.merge_items(items), unresolved


def _block_has_stale(block: dict) -> bool:
    badges = list(block.get("badges") or ())
    notes = []
    for value in block.get("main_values") or ():
        badges += list(value.get("badges") or ())
    for group in block.get("fund_groups") or ():
        badges.append(group.get("freshness_badge"))
        notes.append(group.get("freshness_note"))
    for row in block.get("_rows") or ():
        if isinstance(row, dict):
            badges.append(row.get("freshness_badge"))
            notes.append(row.get("freshness_note"))
    if any(_is_stale_badge(b) and str(b.get("text", "")).startswith(f"{SYMBOL_STALE} ") for b in badges):
        return True
    return any(isinstance(n, dict) and str(n.get("text", "")).startswith(f"{SYMBOL_STALE} ") for n in notes)


def stale_items(display: dict, cards) -> list:
    """不是最新（◷）：② 卡上留著 `◷` 記號的那幾張（`move_card_provenance`、`mark_last_valid` 之後）。整頁只算一項。"""
    blocks = list(display.get("blocks") or ())
    hit = [(index, block) for index, block in enumerate(blocks) if block.get("code") in cards and _block_has_stale(block)]
    if not hit:
        return []
    return [page_health.make_item(page_health.KIND_STALE, page_health.STALE_KEY,
                                  [page_health.affected(block.get("title", ""), core=True) for _i, block in hit],
                                  order=hit[0][0])]


_NOT_APPLICABLE_PREFIX = "⬜ "


def _value_unreadable(value) -> bool:
    """一個主值畫成 ⛔／◇ 沒有（讀狀態與畫出來的字；不另判）。"""
    if not isinstance(value, dict):
        return False
    if value.get("_state") in _UNREADABLE_STATES:
        return True
    return any(str(value.get(key) or "").startswith((f"{SYMBOL_ERROR} ", f"{SYMBOL_MISSING} "))
               for key in ("value_text", "text"))


def normal_entries(display: dict, cards, data_class=None) -> list:
    """明細表裡「沒有異常的項目」那幾列（總管裁定 (b)：狀態欄寫「—」）：② 核心卡上每一個值與它的來源、新鮮度徽章
    （`move_card_provenance` 之前讀；來源徽章 → 來源層級欄、新鮮度徽章 → 延遲天數欄、「⬜ 不適用」那一句 → 狀態欄），以及市場總覽 `MKT-7` 的每一列。
    `data_class`：該頁這幾個值共同的資料類（市場總覽＝市場指標；其他頁不給，寫「—」，不猜）。每一筆另記這個值畫成 ⛔／◇ 沒有
    （`unreadable`），給明細表判斷塊層成因涵蓋哪幾個值（3-B 稽核回修第 6 條）。
    只照抄畫面上已有的字，不另算；有異常的那幾項由 `page_health.detail_rows` 依原因項目列，這裡同一張卡同一個值的那一列會被略過。"""
    out = []

    def entry(title, label, badges, *, unreadable=False):
        by_kind, status = {}, []
        for badge in badges or ():
            if _is_provenance(badge):
                text = str(badge.get("text", ""))
                if text.startswith(_NOT_APPLICABLE_PREFIX):   # 卡上「⬜ 不適用」那一句是狀態，不是來源或延遲（3-B 稽核回修第 7 條）
                    status.append(text)
                else:
                    by_kind.setdefault(badge["_kind"], []).append(text)
        return page_health.affected(title, label, tier="、".join(by_kind.get("來源", ())) or None,
                                    delay="、".join(by_kind.get("新鮮度", ())) or None, data_class=data_class,
                                    unreadable=unreadable, status="、".join(status) or None)

    for block in display.get("blocks") or ():
        if block.get("code") not in cards:
            continue
        title = block.get("title", "")
        if any(_is_provenance(b) for b in block.get("badges") or ()):
            out.append(entry(title, "", block.get("badges")))
        for value in block.get("main_values") or ():
            out.append(entry(title, value.get("label", ""), value.get("badges"), unreadable=_value_unreadable(value)))
        for group in block.get("fund_groups") or ():
            out.append(entry(title, group.get("head_text", ""), [group.get("freshness_badge")],
                             unreadable=any(_value_unreadable(v) for v in group.get("main_values") or ())))
    for block in display.get("blocks") or ():
        if block.get("code") != "MKT-7":
            continue
        for row in block.get("_rows") or ():
            out.append(page_health.affected(
                block.get("title", ""), str(row.get("indicator_key", "")),
                data_class=plain.TABLE_NAMES["market_indicator"], obs=row.get("obs_text"), fetched=row.get("fetched_text"),
                delay=row.get("delay_text"), tier=row.get("tier_text"),
                unreadable=any(isinstance(v, str) and (v in (SYMBOL_ERROR, SYMBOL_MISSING)
                                                       or v.startswith((f"{SYMBOL_ERROR} ", f"{SYMBOL_MISSING} ")))
                               for k, v in row.items() if not str(k).startswith("_"))))
    return out
