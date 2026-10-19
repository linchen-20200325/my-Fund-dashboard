# -*- coding: utf-8 -*-
"""設定與診斷**正式模式**才有的畫面調整（純函式；不 import streamlit、不 import 舊樹、不 import fixtures）。

依據：客戶 2026-09-26 核准的文字線框草稿「設定與診斷（SET）正式模式」第二版（含第 10、12 節裁示）。
全部只在正式模式生效；示範模式（`ui_v2/app_set.py`）不經過本檔，一個字都不變。

本檔做三件事，都不改 `logic.py` 的任何判定（草稿第 8 節：「本稿只加字，不改判定」）：
1. **拿掉示範字樣**（草稿 ✂1～✂4）：頁首副標在 `page.py` 處理；✂2～✂4 在 `apply_live_notes`。
2. **加上新文案**（草稿 ★1～★10）：每一句逐字照草稿，集中在下方常數；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
3. **按鈕的正式行為**：「存檔」與「重新取數」的停用原因、執行中、結果行（草稿第 6 節）。

「尚未接上」一律由 L2 交出的旗標決定（草稿 B7；`notes["pending_tables"]` 等），本檔不自己猜。
遮蔽記號由 L2 交出（`notes["mask_token"]`），本檔不另寫一份。

`notes` 的形狀見 `ui_v2/set/source.py::load_live` 的 docstring。
"""

from __future__ import annotations

import copy
import math

from .. import plain
from . import logic

# ───────────────────────── 草稿文案（逐字；出處見各行註解） ─────────────────────────

MASKED_NOTE = "已遮蔽憑證"  # ★5，ACCEPTANCE.md 7.4 逐字
# ~~TEXT_PENDING_NAV_DIVIDEND = "淨值、配息尚未接取數來源"  # ★1，客戶 2026-09-26 定稿~~
# → 2026-10-09 換句（狀態更新，不是漏刪）：客戶裁示 Q1 不存 NAV、即時取得，「淨值尚未接」自此為假；
#   新句為客戶 2026-10-02 核准的 B 句，2026-10-09 再核准（`docs/v2/53_nav_source_plan.md` §7 第 1 列）。
TEXT_PENDING_DIVIDEND = "配息尚未接取數來源；淨值即時取得"  # ★1（SET-0），配息仍待接就印、不再看 nav
TEXT_REASON_KIND_PENDING = "原因：這一類的存放處尚未接上，暫無取得時間"  # ★2（SET-1）
TEXT_REASON_TIER_PENDING = "原因：這一層級的取數尚未接上"  # ★2（SET-2）
# ~~TEXT_LOG_SCOPE = "取數紀錄只記從 set 頁觸發的取數；市場總覽頁開頁時自己的取數不記在這裡。"  # ★3~~
# → 客戶 2026-10-19 裁示（`docs/DECISIONS.md` `DEC-2026-10-19-04`，BL-0250 批次 1；有意識的政策變更，不是漏刪）：
#   舊句在 `SET-0`、`SET-2`、`SET-6` 各印一次（同一句全頁三次），且「set 頁」是工程字樣。只留 `SET-6`（取數紀錄那一塊）一處，
#   改寫成下面這一句。舊句的用意（取數紀錄的射程只到本頁按的那幾次）完全保留；被權衡掉的是重複與工程字樣。
TEXT_LOG_SCOPE = "這裡只記在本頁按「重新取數」的結果；其他頁開頁時的取數不在這裡"  # ★3（只在 SET-6）
# ~~「set 頁」~~ → 「本頁」（同上裁示；只換這兩個字，句意不動）。
TEXT_MI_TIME_SCOPE = "這個時間是本頁最近一次取數存入的時間，不是市場總覽頁畫面上那一份的時間"  # ★4
# SET-1 淨值列有時間時才印（客戶 2026-10-09 核准，`docs/v2/53_nav_source_plan.md` §7 第 4 列）。
TEXT_NAV_TIME_SCOPE = "這個時間是本頁最近一次重新取數淨值的時間，不是持倉頁畫面上那一份的時間"
# 客戶 2026-10-19 裁示（同上）：`SET-4` 某鍵沒有任何畫面用到時那一行。~~「改這個鍵會影響：44 各塊的來源欄沒有宣告用它」~~
# （`logic._used_by_text`，示範模式照舊）→ 正式模式寫這一句。
TEXT_USED_BY_NONE = "目前沒有畫面用到這個設定"
_USED_BY_NONE_DEMO = "改這個鍵會影響：44 各塊的來源欄沒有宣告用它"
# 客戶 2026-10-19 裁示（同上）：`SET-3`／`SET-4` 收合摘要不再列原始鍵名，只寫「N 個設定，M 個未設定」。
TEXT_SET4_SUMMARY = "{n} 個設定，{unset} 個未設定"
TEXT_SET4_SUMMARY_ALL_SET = "{n} 個設定，皆已設定"
# 客戶 2026-10-19 裁示（同上）：一般畫面上「服務帳戶（google_service_account）」寫成「Google 服務帳戶」；
# 讀取情境的「⛔ 未設定試算表 ID，暫停寫入」寫成「⛔ 尚未設定：試算表 ID」（存檔按鈕的停用原因屬寫入情境，照舊）。
# `SET-2`、`SET-6` 照印原文（44 `SET-2` 規則欄、第七節第三小節之七其二第 2 條），不換。
SERVICE_ACCOUNT_WORDS = (
    ("未設定服務帳戶（google_service_account）", "未設定 Google 服務帳戶"),
    ("服務帳戶（google_service_account）", "Google 服務帳戶"),
)
TEXT_NO_SHEET_ID_READ = "尚未設定：試算表 ID"
_RAW_TEXT_CODES = ("SET-2", "SET-6", "SET-7")

# ★6（草稿 6.1）
TEXT_SAVED = "已存檔"  # 客戶 2026-09-26 定稿
TEXT_SAVE_MAYBE_WRITTEN = "未存檔。這次可能其實已寫入，請先重新整理本頁確認，再決定要不要重存"
TEXT_HINT_403 = "服務帳戶可能只有檢視權限，需要編輯者"
TEXT_HINT_404 = "請確認試算表 ID，以及已分享給服務帳戶"  # 後面接一個空格與 client_email（有才接）
TEXT_NO_SHEET_ID = "未設定試算表 ID，暫停寫入"  # 客戶 2026-09-26 定稿（B11：非燈位置全站統一這一句）
TEXT_NO_SERVICE_ACCOUNT = "未設定服務帳戶"  # `50` 第 8 節
TEXT_SHEET_COOLING = "設定試算表暫停重試，約剩 {n} 秒"  # 草稿擬（B2：統一用「約剩」）

# ★7
TEXT_SETTING_PENDING = "設定已存，{codes} 接上後生效"  # 客戶 2026-09-26 定稿格式

# ★8（草稿 6.2）
TEXT_TIER_NOT_WIRED = "這一層級的取數尚未接上"
TEXT_RUNNING = "取數中：{tier}"
TEXT_DONE = "取數完成：{tier}，取回 {n} 列；結果記在取數紀錄（層 4）"
# 取數紀錄寫不進去時（開始列或結束列），後半句「結果記在取數紀錄」是假話 → 只印前半（2026-09-26 總管裁示）。
TEXT_DONE_NOT_LOGGED = "取數完成：{tier}，取回 {n} 列"
TEXT_DONE_EMPTY = "取數完成：{tier}，" + logic.TEXT_EMPTY_RESPONSE
TEXT_LOG_WRITE_FAILED = "⛔ 取數紀錄寫入失敗：{message}"
# ~~TEXT_SET5_NOTE = "目前只有市場指標可以重新取數；取回的列存進設定試算表，市場總覽頁不會因此重新整理。"~~
# → 2026-10-09 換句（狀態更新，不是漏刪；客戶核准，`docs/v2/53_nav_source_plan.md` §7 第 9 列）。
TEXT_SET5_NOTE = ("目前市場指標與淨值可以重新取數。市場指標取回的列存進設定試算表，市場總覽頁不會因此重新整理；"
                  "淨值只取持倉基金，除了記一筆取數紀錄，不寫入任何表。")

# ★9（草稿 ★9 細項；`50` 5.2／5.3／7.1／第 8 節，🟡 統一改成本頁的 ⚠，草稿 B3）
TEXT_HEADER_MISMATCH = "⛔ 標頭與規格不符：{tab}"
TEXT_HEADER_SPEC = "規格：{columns}"
TEXT_HEADER_SHEET = "試算表：{columns}"
TEXT_BAD_ROWS = "⚠ {n} 列格式不符，未採用"
TEXT_PK_CONFLICT = "⚠ 主鍵矛盾 {n} 組，未採用"
TEXT_REVISED_MISMATCH = "⚠ is_revised 與重算不符 {n} 列"
TEXT_DUPLICATE_LOG = "⚠ 重複紀錄 {n} 筆"

# `SET-0` 說明行（44 `SET-0` 來源欄；客戶 2026-10-18 裁示 S4，`DEC-2026-10-18-01`）：正式模式補明第三個輸入；
# 示範模式那一行（`logic._build_set0` 的 `detail_lines`）照舊。
TEXT_SET0_INPUTS_DEMO = logic.TEXT_LAMP_DATA_ONLY + "。本燈只讀 SET-1 的逾期筆數與 SET-2 的失敗來源數。"
TEXT_SET0_INPUTS = logic.TEXT_LAMP_DATA_ONLY + "。本燈讀三個輸入：SET-1 的逾期筆數、SET-2 的失敗來源數、設定試算表是否已設定。"

# 存檔失敗但「根本沒寫」的錯誤碼：這些不印「可能其實已寫入」那一行（2026-09-26 總管裁示）。
_NOT_WRITTEN_CODES = ("cooling", "not_configured", "no_service_account", "header_mismatch")

# ★10
TEXT_TITLE = "設定試算表：{title}"
TEXT_TITLE_FAILED = "⛔ 讀不到試算表名稱：{message}"

# 客戶 2026-09-26 已核准的市場總覽正式入口文案（草稿 6.2：「mkt 已核准文案，逐字沿用」）。
# 本套件不 import ui_v2.mkt（見 `__init__.py`），由 tests/ui_v2/test_set_live_logic.py 與 mkt 那一份逐字比對。
TEXT_SOURCE_COOLING = "來源冷卻中：{source}，約剩 {n} 秒"
TEXT_SOURCE_COOLING_MORE = "，另有 {n} 個來源冷卻中"

# 示範模式才有、正式模式要拿掉的字樣（草稿 ✂2～✂4）。
_DEMO_LINES = (
    logic.HINT_NOTE,
    "⚠ 本頁沒有後端：「存檔」按得下去，但不寫任何東西。",
    "⚠ 本頁沒有後端：「重新取數」按得下去，但不取數、不寫 fetch_log，也不演執行中那一態。",
)

# `SET-1` 資料類 → 表；`SET-2` 層級 → 表（★2 判斷「尚未接上」用）。
_KIND_TABLE = dict(logic.KIND_TABLES)
_TIER_TABLE = {"淨值": "nav", "配息": "dividend", "市場指標": "market_indicator", "其他": None}
# `notes["source_cooldowns"]` 是哪一層的來源（`source.load_live` 放的是 `market_indicator.source_cooldowns()`）。
# 其他層沒有對應的冷卻清單 → 不印冷卻原因（2026-10-09 總管裁示：不自創新句）。
_COOLDOWN_TIER = "市場指標"

# 哪一塊讀哪一張分頁（★9 標頭不符、格式不符出在哪；草稿 ★9「以讀到該分頁的塊為準」）。
_BLOCKS_READING = {
    "user_setting": ("SET-1", "SET-3", "SET-4", "SET-6"),
    "market_indicator": ("SET-1",),
    "fetch_log": ("SET-2", "SET-6"),
}


def _node(text, tone="中性") -> dict:
    return {"text": text, "_tone": tone}


def _masked(text, token) -> bool:
    return bool(token) and isinstance(text, str) and token in text


def seconds_left(remaining_sec) -> int:
    return math.ceil(remaining_sec or 0)


def sheet_cooling_text(remaining_sec) -> str:
    return TEXT_SHEET_COOLING.format(n=seconds_left(remaining_sec))


def cooldown_reason(cooldowns):
    """列出剩餘秒數最長的那一個來源，再加一句另有幾個；沒有冷卻中的來源回 None（同 mkt 已核准寫法）。"""
    live = [c for c in cooldowns or () if c.get("remaining_sec", 0) > 0]
    if not live:
        return None
    top = max(live, key=lambda c: c["remaining_sec"])
    text = TEXT_SOURCE_COOLING.format(source=top["source"], n=math.ceil(top["remaining_sec"]))
    others = len(live) - 1
    if others:
        text += TEXT_SOURCE_COOLING_MORE.format(n=others)
    return text


def sheet_configured(notes) -> bool:
    """設定試算表有沒有設定（44 `SET-0` 來源欄第二輪擴寫的那一個輸入；之八其三 (c-1)）。
    讀寫入閘門（`notes["gate"]`，不打上游）：狀態為 `not_configured` ⇒ 沒設。缺鍵就 `KeyError`，不猜。"""
    return notes["gate"]["state"] != "not_configured"


def service_account_configured(notes) -> bool:
    """服務帳戶有沒有設定（客戶 2026-10-18 裁示 C1／S1，`DEC-2026-10-18-01`）。只在設定試算表未設定時才需要
    （寫入閘門先判 ID，ID 沒設時閘門看不到服務帳戶）：閘門不是 `not_configured` → 回 True（閘門已經把缺服務帳戶判成
    `no_service_account`，那一支照 44 字面是 ⛔，不經本函式）。`not_configured` 時讀 `notes["service_account"]`，缺鍵就 `KeyError`，不猜。"""
    if notes["gate"]["state"] != "not_configured":
        return True
    return bool(notes["service_account"]["configured"])


def gate_reason(gate):
    """寫入閘門 → 停用原因（None＝可寫）。草稿 6.1／6.2 缺設定與設定試算表冷卻中那幾列。"""
    state = (gate or {}).get("state")
    if state == "ok":
        return None
    if state == "not_configured":
        return TEXT_NO_SHEET_ID
    if state == "no_service_account":
        return TEXT_NO_SERVICE_ACCOUNT
    if state == "cooling":
        return sheet_cooling_text(gate.get("remaining_sec"))
    raise ValueError(f"未知的寫入閘門狀態 {state!r}")


# ───────────────────────── 按鈕 ─────────────────────────


def save_button(notes) -> dict:
    """SET-4「存檔」（草稿 6.1）：缺設定或設定試算表冷卻中 → 停用並寫原因；其餘可按。"""
    reason = gate_reason(notes["gate"])
    return logic._button(logic.TEXT_SAVE, "存檔", enabled=reason is None, disabled_reason=reason or "")


def refetch_button(picked, notes, *, running=False) -> dict:
    """SET-5「重新取數」（草稿 6.2）。判定順序：未選 → 層級未接上 → 缺設定 → 來源冷卻（只看市場指標層，見 `_COOLDOWN_TIER`）→ 設定試算表冷卻。"""
    if picked is not None and picked not in logic.TIERS:
        raise ValueError(f"來源層級 {picked!r} 不在 `44` 第四節那四個之內")
    if running:
        reason = TEXT_RUNNING.format(tier=picked)
    elif picked is None:
        reason = logic.TEXT_NO_TIER_PICKED
    elif picked not in notes["wired_tiers"]:
        reason = TEXT_TIER_NOT_WIRED
    else:
        gate = notes["gate"]
        reason = None
        if gate.get("state") in ("not_configured", "no_service_account"):
            reason = gate_reason(gate)
        if reason is None and picked == _COOLDOWN_TIER:
            reason = cooldown_reason(notes.get("source_cooldowns"))
        if reason is None and gate.get("state") == "cooling":
            reason = gate_reason(gate)
    return logic._button(logic.TEXT_REFETCH, "取數", enabled=reason is None, disabled_reason=reason or "")


def refetch_result_lines(result, mask_token) -> list:
    """重新取數的結果行（草稿 6.2 成功／回空／失敗／取數紀錄寫入失敗）。回 `[node, ...]`。

    `result` 見 `source.refetch`：分工照 `services/v2_tables/settings_store.py` 的 docstring ——
    - `log_message`：與寫進 `fetch_log.message` 的字串逐字相同（`44` SET-5 判準），`begin` 成功才有；
    - `masked_errors`：已遮蔽的真錯誤；`begin` 失敗（沒有 `log_message`）時以它組失敗行；
    - `empty`：來源回空、原因未提供（`44` SET-5 的回空，不是失敗）；
    - `message`：設定試算表本身的錯誤（寫不進取數紀錄），`stage` 為 `fetch_log_open`／`fetch_log` 時上畫面。
    """
    tier = result["tier"]
    failure = result.get("log_message")
    if failure is None and result.get("masked_errors"):
        failure = "\n".join(f"{k}: {v}" for k, v in result["masked_errors"].items())
    log_failed = result.get("stage") in ("fetch_log_open", "fetch_log")
    lines = []
    if failure:
        lines.append(_node(logic.fetch_failed_text(failure), "紅"))
        if _masked(failure, mask_token):
            lines.append(_node(MASKED_NOTE, "灰"))
    elif result.get("empty") and not result.get("fetched"):
        lines.append(_node(TEXT_DONE_EMPTY.format(tier=tier)))
    else:
        done = TEXT_DONE_NOT_LOGGED if log_failed else TEXT_DONE
        lines.append(_node(done.format(tier=tier, n=result.get("fetched", 0))))
    if log_failed and result.get("message"):
        message = result["message"]
        lines.append(_node(TEXT_LOG_WRITE_FAILED.format(message=message), "紅"))
        if _masked(message, mask_token):
            lines.append(_node(MASKED_NOTE, "灰"))
    return lines


def changed_settings(inputs, current_values) -> list:
    """「存檔」要寫哪幾鍵：輸入欄當下值與已存值不同的鍵（`44` SET-4：被編輯的那個鍵）。

    `inputs` 是 SET-4 模型的 `inputs`；`current_values` 是 `{鍵: 輸入欄當下字串}`。
    輸入欄清空 → `setting_value` 為 None（`44`：清除後是空值，不是空字串；清除＝清空後存檔）。
    回 `[(鍵, 值或 None, value_kind), ...]`，照 SET-4 的鍵順序。
    """
    out = []
    for field in inputs:
        key = field["name"]
        if key not in current_values:
            continue
        raw = current_values[key]
        # 只有空白或留空 → 清除這個鍵；其餘照原值比對、照原值寫（前後帶空白由型別檢查擋下，不靜默去掉）。
        value = None if raw is None or raw.strip() == "" else raw
        if value != field["_value"]:
            out.append((key, value, field["_kind"]))
    return out


def dataset_with_save_results(dataset, results):
    """把上一次「存檔」的結果疊進 dataset（不改呼叫端那一份）：沒存成的鍵，輸入欄畫當下輸入
    （`44` SET-4：該欄的當下輸入留在畫面上不清掉）；寫入失敗的鍵另帶失敗訊息（已遮蔽）。
    型別不符的鍵只放當下輸入 —— `logic` 會依它畫出型別說明（`44`：欄位下方顯示型別說明，不存檔）。"""
    if not results:
        return dataset
    out = dict(dataset)
    out["save_inputs"] = dict(dataset.get("save_inputs") or {})
    out["save_errors"] = dict(dataset.get("save_errors") or {})
    for key, result in results.items():
        if result["status"] == "saved":
            continue
        out["save_inputs"][key] = result.get("attempted")
        if result["status"] == "failed":
            out["save_errors"][key] = result["message"]
    return out


# ───────────────────────── 模型調整 ─────────────────────────


def _fail_map(dataset, notes) -> dict:
    """各表讀取失敗的畫面字串 → (正式模式顯示的字串, 下接的行, 色調)。燈（SET-0）不走這裡（照 `44` 字面）。"""
    token = notes["mask_token"]
    out = {}
    for table, message in (dataset.get("errors") or {}).items():
        info = notes["table_errors"].get(table, {})
        raw = logic.fetch_failed_text(message)
        extra = []
        if info.get("code") == "not_configured":
            shown = f"{logic.FETCH_FAIL_GLYPH} {message}"  # B11：非燈位置統一「⛔ 未設定試算表 ID，暫停寫入」
        elif info.get("code") == "header_mismatch":
            shown = TEXT_HEADER_MISMATCH.format(tab=info["tab"])
            extra.append(_node(TEXT_HEADER_SPEC.format(columns="、".join(info["expected"])), "紅"))
            sheet_line = TEXT_HEADER_SHEET.format(columns="、".join(info["actual"]))
            extra.append(_node(sheet_line, "紅"))
            if _masked(sheet_line, token):
                extra.append(_node(MASKED_NOTE, "灰"))
        else:
            shown = raw
        if _masked(shown, token):
            extra.insert(0, _node(MASKED_NOTE, "灰"))
        # 幾張表同一句失敗（例如同一次冷卻）時字串相同，取哪一張的轉換都一樣。
        out.setdefault(raw, (shown, extra, table))
    return out


def _decorate_placeholder(node, fail_map, notes, code, dataset=None):
    if not node or node.get("text") not in fail_map:
        return node
    shown, extra, _table = fail_map[node["text"]]
    info = notes["table_errors"].get("user_setting", {})
    setting_error = (dataset or {}).get("errors", {}).get("user_setting")
    if code in ("SET-3", "SET-4") and info.get("code") == "cooling" \
            and node["text"] == logic.fetch_failed_text(setting_error):
        # 草稿 6.1 末注：冷卻期間讀設定也被跳過；SET-3／SET-4 的值格改顯示暫停（黃，B4），不是 ⬜ 未設定。
        return {**node, "text": f"{logic.WARN_GLYPH} " + sheet_cooling_text(info.get("remaining_sec")),
                "_tone": "黃", "note_lines": []}
    return {**node, "text": shown, "note_lines": list(extra)}


def _strip_demo(lines):
    return [line for line in lines if line not in _DEMO_LINES]


def _structure_lines(notes, code) -> list:
    """★9：讀設定試算表時的結構檢查計數（大於 0 才出）。"""
    s = notes.get("structure") or {}
    lines = []
    if code == "SET-1":
        mi = s.get("market_indicator") or {}
        if mi.get("conflicts"):
            lines.append(_node(TEXT_PK_CONFLICT.format(n=mi["conflicts"]), "黃"))
        if mi.get("is_revised_mismatch"):
            lines.append(_node(TEXT_REVISED_MISMATCH.format(n=mi["is_revised_mismatch"]), "黃"))
        if mi.get("bad_rows"):
            lines.append(_node(TEXT_BAD_ROWS.format(n=mi["bad_rows"]), "黃"))
    if code in ("SET-3", "SET-4"):
        us = s.get("user_setting") or {}
        if us.get("bad_rows"):
            lines.append(_node(TEXT_BAD_ROWS.format(n=us["bad_rows"]), "黃"))
    if code == "SET-6":
        fl = s.get("fetch_log") or {}
        if fl.get("duplicates"):
            lines.append(_node(TEXT_DUPLICATE_LOG.format(n=fl["duplicates"]), "黃"))
        if fl.get("bad_rows"):
            lines.append(_node(TEXT_BAD_ROWS.format(n=fl["bad_rows"]), "黃"))
    return lines


def _save_fail_lines(result, token) -> list:
    """★6 失敗框（草稿 6.1）：第 1、2 行照既有；第 3 行「未存檔。…」；403／404 另加一行；含遮蔽加 ★5。"""
    message = result["message"]
    lines = [logic.save_failed_text(message)]
    if _masked(message, token):
        lines.append(MASKED_NOTE)
    lines.append(logic.TEXT_KEEP_INPUT)
    hint = result.get("hint") or ""
    is_403 = result.get("http_status") == 403 or hint == TEXT_HINT_403
    is_404 = result.get("http_status") == 404 or hint.startswith(TEXT_HINT_404)
    # 「可能其實已寫入」只限一般失敗：冷卻、缺設定、標頭不符、403／404（打不開或沒有權限）都是根本沒寫。
    if result.get("code") not in _NOT_WRITTEN_CODES and not is_403 and not is_404:
        lines.append(TEXT_SAVE_MAYBE_WRITTEN)
    if is_403:
        lines.append(TEXT_HINT_403)
    elif is_404:
        email = result.get("client_email") or ""
        lines.append(f"{TEXT_HINT_404} {email}" if email else TEXT_HINT_404)
    return lines


def _drop_dev_notes(node):
    """BL-0345（2026-10-19）：把 `logic.LIVE_DEV_NOTE_EDITS` 列的純開發註記從正式模式拿掉（整棵模型走一遍）。

    只認整句相等：句子等於表裡的鍵 → 換成表裡的值；值為 None 就整句拿掉。**只刪、不新寫任何字。**
    示範模式不經過本函式，輸出不變。
    """
    edits = logic.LIVE_DEV_NOTE_EDITS
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = _drop_dev_notes(value)
        return node
    if isinstance(node, (list, tuple)):
        kept = [_drop_dev_notes(v) for v in node if not (isinstance(v, str) and v in edits and edits[v] is None)]
        return type(node)(kept)
    if isinstance(node, str) and node in edits and edits[node] is not None:
        return edits[node]
    return node


def apply_live_notes(model: dict, dataset: dict, notes: dict, *, save_results=None) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。

    `dataset`：交給 `logic.build_page_model` 的那一份（讀它的 `errors` 對出失敗字串）。
    `save_results`：上一次按「存檔」的結果 `{鍵: result}`（`source.save_setting` 的回傳），沒有就 None。
    """
    out = _drop_dev_notes(copy.deepcopy(model))
    token = notes["mask_token"]
    fail_map = _fail_map(dataset, notes)
    pending_tables = set(notes["pending_tables"])
    wired_tiers = set(notes["wired_tiers"])

    # ── SET-0：燈的外框與文字照 `44`（含 5.5 系統錯誤模板 `logic.fetch_failed_text`），只在下一行加 ★5；說明行加 ★1、★3 ──
    set0 = logic.find_block(out, "SET-0")
    if not sheet_configured(notes) and not service_account_configured(notes):
        # 客戶 2026-10-18 裁示 C1（`DEC-2026-10-18-01`）：設定試算表與服務帳戶都沒設時，讀取失敗看到的只有「沒設 ID」，
        # 缺服務帳戶被蓋掉；燈改用缺服務帳戶那一句（與只缺服務帳戶時同一盞 ⛔ 讀取失敗），不出第三句（`sections.set_conclusion`）。
        message = notes["service_account"]["message"]
        set0.update(_tone="紅", _state="讀取失敗", glyph=logic.FETCH_FAIL_GLYPH, state_word="狀態：取數失敗",
                    text=logic.fetch_failed_text(message))
    set0["note_lines"] = [MASKED_NOTE] if _masked(set0["text"], token) else []
    # 客戶 2026-10-18 裁示 S4：說明行補明第三個輸入（設定試算表是否已設定）。示範模式不經過本檔，照舊。
    set0["detail_lines"] = [TEXT_SET0_INPUTS if line == TEXT_SET0_INPUTS_DEMO else line for line in set0["detail_lines"]]
    if "dividend" in pending_tables:
        set0["detail_lines"].append(TEXT_PENDING_DIVIDEND)
    # ~~set0["detail_lines"].append(TEXT_LOG_SCOPE)~~ → 客戶 2026-10-19 裁示：取數紀錄的射程說明只留在 `SET-6`。

    # ── SET-1 ──
    set1 = logic.find_block(out, "SET-1")
    for row in set1["_rows"]:
        table = _KIND_TABLE[row["_kind_label"]]
        row["note_lines"], row["at_note_lines"] = [], []
        if row["_empty"] and table in pending_tables:
            row["note_lines"].append(TEXT_REASON_KIND_PENDING)  # ★2
        if row["_failed"] and row["at_text"] in fail_map:
            shown, extra, _t = fail_map[row["at_text"]]
            row["at_text"] = shown
            row["at_note_lines"] = [n["text"] for n in extra]
        if table == "market_indicator" and not row["_failed"] and not row["_empty"]:
            row["note_lines"].append(TEXT_MI_TIME_SCOPE)  # ★4
        if table == "nav" and not row["_failed"] and not row["_empty"]:
            row["note_lines"].append(TEXT_NAV_TIME_SCOPE)  # 2026-10-09 核准
    set1["fail_nodes"] = [_decorate_placeholder(n, fail_map, notes, "SET-1") for n in set1["fail_nodes"]]
    set1["live_lines"] = _structure_lines(notes, "SET-1")
    set1["detail_lines"] = _strip_demo(set1["detail_lines"])  # ✂2
    # 客戶 2026-10-19 裁示：新鮮度上限那一行不帶括號裡的鍵名（`（set_max_age_days）`，一般畫面換字後是「（新鮮度上限日數）」）。
    set1["limit_lines"] = [line.replace(f"（{logic.MAX_AGE_KEY}）", "") for line in set1.get("limit_lines") or ()]

    # ── SET-2 ──
    set2 = logic.find_block(out, "SET-2")
    set2["placeholder"] = _decorate_placeholder(set2["placeholder"], fail_map, notes, "SET-2")
    for row in set2["_rows"]:
        row["note_lines"], row["message_note_lines"] = [], []
        table = _TIER_TABLE[row["_tier"]]
        record_missing = row["result_text"] == "⬜"
        not_wired = row["_tier"] not in wired_tiers and (table is None or table in pending_tables)
        if record_missing and not_wired:
            row["note_lines"].append(TEXT_REASON_TIER_PENDING)  # ★2
        if _masked(row["message_text"], token):
            row["message_note_lines"].append(MASKED_NOTE)  # ★5
    set2["detail_lines"] = _strip_demo(set2["detail_lines"])  # ✂2（★3 只留在 SET-6，客戶 2026-10-19 裁示）

    # ── SET-3：★10 在卡頭下方第一行 ──
    set3 = logic.find_block(out, "SET-3")
    title = notes["title"]
    head = []
    if title["state"] == "ok":
        head.append(_node(TEXT_TITLE.format(title=title["text"])))
    elif title["state"] == "not_configured":
        head.append(_node(f"{logic.FETCH_FAIL_GLYPH} {TEXT_NO_SHEET_ID}", "紅"))
    elif title["state"] == "cooling":
        # 草稿 B4：設定試算表冷卻是暫停、不是失敗，與 SET-3／SET-4 同一句黃色暫停句。
        head.append(_node(f"{logic.WARN_GLYPH} " + sheet_cooling_text(title.get("remaining_sec")), "黃"))
    else:
        head.append(_node(TEXT_TITLE_FAILED.format(message=title["text"]), "紅"))
        if _masked(title["text"], token):
            head.append(_node(MASKED_NOTE, "灰"))
    set3["head_lines"] = head
    placeholder = _decorate_placeholder(set3["placeholder"], fail_map, notes, "SET-3", dataset)
    if placeholder and title["state"] == "not_configured" and placeholder["text"] == head[0]["text"]:
        placeholder = None  # 草稿 7.1：同一句不重複印，★10 那一行即本塊的失敗行
    set3["placeholder"] = placeholder
    broken = set((notes.get("structure") or {}).get("user_setting", {}).get("broken_keys", ()))
    for row in set3["_rows"]:
        if row["_key"] in broken:  # `50` 第 8 節：最新一列解析不了 → 錯誤狀態，不是 ⬜ 未設定
            row["value_text"] = TEXT_BAD_ROWS.format(n=1)
            row["raw_text"] = ""
    set3["live_lines"] = _structure_lines(notes, "SET-3")
    set3["detail_lines"] = _strip_demo(set3["detail_lines"])  # ✂2

    # ── SET-4 ──
    set4 = logic.find_block(out, "SET-4")
    set4["fail_nodes"] = [_decorate_placeholder(n, fail_map, notes, "SET-4", dataset) for n in set4["fail_nodes"]]
    top = []
    gate = notes["gate"]
    setting_code = notes["table_errors"].get("user_setting", {}).get("code")
    if gate["state"] in ("not_configured", "no_service_account") and setting_code != gate["state"]:
        # 去重比對錯誤碼、不比對字串：讀設定已因同一個缺設定失敗時，本塊的失敗行就是這件事，不再多印一行。
        top.append(_node(f"{logic.FETCH_FAIL_GLYPH} {gate_reason(gate)}", "紅"))
    set4["top_lines"] = top
    reading = set(notes["pages_reading_settings"])
    results = save_results or {}
    for field in set4["inputs"]:
        key = field["name"]
        prefix = key.split("_", 1)[0]
        if prefix not in reading:
            blocks = dict(dataset["spec"]["key_used_by"]).get(key, ())
            if field["_value"] is None:
                field["used_by_text"] = None  # 草稿 B9：未設定的鍵不出 ★7，只留「⬜ 未設定」
            elif blocks:
                field["used_by_text"] = TEXT_SETTING_PENDING.format(codes="、".join(blocks))  # ★7
        if key in broken:
            field["unset_lines"] = [TEXT_BAD_ROWS.format(n=1)]
        result = results.get(key)
        field["saved_lines"] = []
        if result is None:
            continue
        if result["status"] == "saved":
            field["saved_lines"] = [TEXT_SAVED]
        elif result["status"] == "failed":
            field["fail_lines"] = _save_fail_lines(result, token)
        elif result["status"] == "kind_missing":
            # 客戶 2026-09-26 裁示後每一鍵都有型別（alo_basis 定為 list 枚舉）；走到這裡是本頁的 bug，當場炸（§1）。
            raise ValueError(f"{key} 的 value_kind 未定，正式模式不該發生（{result.get('message')}）")
        # kind_mismatch：型別說明由 logic 依當下輸入畫出（`dataset["save_inputs"]`），這裡不另加。
    if not set4["inputs"]:
        # 讀不到設定、畫面上沒有輸入欄（SET-GAP-失敗無輸入欄）：上游失敗後存檔與讀取共用冷卻，所以正式模式下
        # 這是存檔失敗後最常見的樣子。「上面這一欄…」那一行照 logic 不印（會是假話），其餘照 ★6。
        set4["orphan_fail_lines"] = [
            [line for line in _save_fail_lines(results[k], token) if line != logic.TEXT_KEEP_INPUT]
            for k in sorted(results) if results[k]["status"] == "failed"
        ]
    for field in set4["inputs"]:
        if field.get("used_by_text") == _USED_BY_NONE_DEMO:
            field["used_by_text"] = TEXT_USED_BY_NONE
        # 客戶 2026-10-19 裁示：輸入欄標籤 ~~`<鍵名>（<value_kind>）`~~（`logic` SET-GAP-輸入欄型態，示範模式照舊）→ 中文設定名
        # （對照只維護 `ui_v2/plain.py` 一份；找不到中文名的鍵照原字）。底層鍵、`value_kind`、存檔內容一個都不動。
        field["label"] = plain.key_name(field["name"])
    if not set4["fail_nodes"]:
        unset = sum(1 for field in set4["inputs"] if field["_value"] is None)
        n = len(set4["inputs"])
        set4["summary_text"] = (TEXT_SET4_SUMMARY.format(n=n, unset=unset) if unset
                                else TEXT_SET4_SUMMARY_ALL_SET.format(n=n))
    set4["buttons"] = [save_button(notes)]
    set4["live_lines"] = _structure_lines(notes, "SET-4")
    set4["detail_lines"] = _strip_demo(set4["detail_lines"])  # ✂3

    # ── SET-5：說明行換成 ★8（✂4）；按鈕由 page 依當下單選呼叫 `refetch_button` ──
    set5 = logic.find_block(out, "SET-5")
    set5["detail_lines"] = _strip_demo(set5["detail_lines"]) + [TEXT_SET5_NOTE]
    set5["buttons"] = [refetch_button(None, notes)]

    # ── SET-6 ──
    set6 = logic.find_block(out, "SET-6")
    set6["placeholder"] = _decorate_placeholder(set6["placeholder"], fail_map, notes, "SET-6")
    for row in set6["_rows"]:
        row["cell_notes"] = {6: [MASKED_NOTE]} if _masked(row["cells"][6], token) else {}
    tail = []
    for line in set6["tail_lines"]:
        for raw, (shown, _extra, _t) in fail_map.items():
            if raw in line:
                line = line.replace(raw, shown)
        tail.append(line)
    set6["tail_lines"] = tail
    set6["live_lines"] = _structure_lines(notes, "SET-6")
    set6["detail_lines"] = _strip_demo(set6["detail_lines"]) + [TEXT_LOG_SCOPE]  # ✂2、★3
    return _plain_set_words(out)


def _plain_set_words(model: dict) -> dict:
    """客戶 2026-10-19 裁示（BL-0250 批次 1）：一般畫面的兩處字樣（就地改寫並回傳）。
    `SET-2`、`SET-6`、`SET-7` 照印原文、不換；按鈕的停用原因（寫入情境）不換。"""
    read_line = f"{logic.FETCH_FAIL_GLYPH} {TEXT_NO_SHEET_ID}"

    def visit(node, key=None):
        if isinstance(node, dict):
            for name in list(node):
                if name == "disabled_reason":
                    continue
                node[name] = visit(node[name], name)
            return node
        if isinstance(node, list):
            return [visit(item, key) for item in node]
        if isinstance(node, tuple):
            return tuple(visit(item, key) for item in node)
        if isinstance(node, str) and not (isinstance(key, str) and key.startswith("_")):
            if node == read_line:
                node = f"{logic.FETCH_FAIL_GLYPH} {TEXT_NO_SHEET_ID_READ}"
            for raw, shown in SERVICE_ACCOUNT_WORDS:
                node = node.replace(raw, shown)
        return node

    for block in model.get("blocks") or ():
        if block.get("code") in _RAW_TEXT_CODES:
            continue
        visit(block)
    return model
