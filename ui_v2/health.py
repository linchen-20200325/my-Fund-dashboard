# -*- coding: utf-8 -*-
"""四頁頁首「資料狀態行」與同源錯誤去重（Phase 3 P0-②；`docs/v2/44_fund_ui_ssot.md` 第七節第三小節之七其二第 3、4 條）。

純函式模組：**不 import streamlit、不 import 舊樹**（`tests/ui_v2/test_ui_v2_live_import_guard.py`），
只 import 同樹的 `ui_v2.plain`。畫法（`st.markdown`、`st.page_link`）住在 `ui_v2/health_view.py`。

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
   符號只是呈現；卡片內既有符號（`⬜` 等）本批不動。
3. **核心卡的來源與新鮮度徽章移到 ④「證據／來源」**（其二第 4 條）：② 卡上 `_kind` 為 `來源`／`新鮮度` 的徽章
   拿下來、交給呼叫端畫在 ④；不刪除（來源、取得時間、資料截至日只能換位置，不能消失）。

**示範模式不經過本模組**（BL-0367）。
"""

from __future__ import annotations

import re
from datetime import date

from . import plain

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
# 第二支：`⛔ 設定讀不到：{狀態句}`。
_SETTINGS_SUMMARY = re.compile(re.escape(plain.SETTINGS_UNREADABLE_PREFIX) + r"(?P<state>" + _STATE_ALT + r")")

_ERROR_STATE = "系統錯誤"
# 「資料未備」那一族（`◇`）：卡片 `資料未備`、空狀態 `來源缺`、`部分缺`（44 第五節第一、五小節）。
_MISSING_STATES = frozenset({"資料未備"})
_MISSING_EMPTY_KINDS = frozenset({"來源缺", "部分缺"})

# 表格列與逐檔分組：這裡面的失敗是那一列／那一檔自己的內容，不寫「此區塊暫時無法判定」，只留狀態族。
_ROW_KEYS = frozenset({"_rows", "_cells", "rows", "cells", "nav_rows", "nav_groups", "fund_groups",
                       "_items", "items", "_assign_rows", "_checkboxes"})


# 按「存檔」那一次的逐鍵結果（資產配置一鍵失敗時畫在該鍵原位，字形借用取數失敗的模板）：那是寫入結果、不是讀取的
# 失敗摘要，不去重、不進資料狀態行（否則會把寫入失敗說成取數失敗）。
_SAVE_RESULT_KEYS = frozenset({"key_error_lines"})


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
        [*_FETCH_SUMMARY.finditer(text), *_SETTINGS_SUMMARY.finditer(text)], key=lambda m: m.start()
    ):
        if match.start() < pos:
            continue
        groups = match.groupdict()
        cls, fund, state = groups.get("cls"), groups.get("fund"), groups["state"]
        if cls is None:
            cls = plain.TABLE_NAMES["user_setting"]
        # 畫面上不畫的位置不進資料狀態行（那一句使用者看不到，狀態行就不能替它說話）；照樣換成狀態族。
        unconfigured = ctx.note(cls, state) if _shown(block, field) else state in NOT_CONFIGURED_STATES
        code = (block or {}).get("code")
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
            node[key] = _walk(value, block, ctx, in_rows=rows, field=key)
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
    }


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


def status_line(display: dict, summary: dict, *, as_of, stale: bool = False) -> dict:
    """資料狀態行的內容（給 `health_view.render_status_line` 畫）。

    回 `{"items": [(符號或空字串, 文字, 色調), ...], "as_of": "YYYY-MM-DD" 或 "—", "text": 整行純文字}`。
    `items` 依 ◷ → ◇ → ⛔ → 尚未設定 排；同類只一筆。`items` 為空 ⇒ 只寫資料截至日（不寫「資料齊」「正常」）。
    """
    items = []
    if stale:
        items.append((SYMBOL_STALE, TEXT_STALE, "中性"))
    if has_missing(display):
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
