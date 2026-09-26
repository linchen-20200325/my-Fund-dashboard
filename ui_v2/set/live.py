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

from . import logic

# ───────────────────────── 草稿文案（逐字；出處見各行註解） ─────────────────────────

MASKED_NOTE = "已遮蔽憑證"  # ★5，ACCEPTANCE.md 7.4 逐字
TEXT_PENDING_NAV_DIVIDEND = "淨值、配息尚未接取數來源"  # ★1，客戶 2026-09-26 定稿
TEXT_REASON_KIND_PENDING = "原因：這一類的存放處尚未接上，暫無取得時間"  # ★2（SET-1）
TEXT_REASON_TIER_PENDING = "原因：這一層級的取數尚未接上"  # ★2（SET-2）
TEXT_LOG_SCOPE = "取數紀錄只記從 set 頁觸發的取數；市場總覽頁開頁時自己的取數不記在這裡。"  # ★3
TEXT_MI_TIME_SCOPE = "這個時間是 set 頁最近一次取數存入的時間，不是市場總覽頁畫面上那一份的時間"  # ★4

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
TEXT_SET5_NOTE = "目前只有市場指標可以重新取數；取回的列存進設定試算表，市場總覽頁不會因此重新整理。"

# ★9（草稿 ★9 細項；`50` 5.2／5.3／7.1／第 8 節，🟡 統一改成本頁的 ⚠，草稿 B3）
TEXT_HEADER_MISMATCH = "⛔ 標頭與規格不符：{tab}"
TEXT_HEADER_SPEC = "規格：{columns}"
TEXT_HEADER_SHEET = "試算表：{columns}"
TEXT_BAD_ROWS = "⚠ {n} 列格式不符，未採用"
TEXT_PK_CONFLICT = "⚠ 主鍵矛盾 {n} 組，未採用"
TEXT_REVISED_MISMATCH = "⚠ is_revised 與重算不符 {n} 列"
TEXT_DUPLICATE_LOG = "⚠ 重複紀錄 {n} 筆"

# 型別未定的鍵（`alo_basis`，SET-GAP-型別本頁配）存檔時的說明。⚠️ 待客戶核准：草稿沒有這一句，
# 由本組以既有的型別說明體例組成（2026-09-26 總管裁示：暫緩，先保留現狀、抽成常數）。
TEXT_KIND_MISSING = "型別說明：這個鍵的 value_kind 未定。" + logic.TEXT_NOT_SAVED

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
    """SET-5「重新取數」（草稿 6.2）。判定順序：未選 → 層級未接上 → 缺設定 → 來源冷卻 → 設定試算表冷卻。"""
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
        if reason is None:
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
        value = None if raw is None or raw.strip() == "" else raw.strip()   # 寫進去的是 strip 後的值
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


def apply_live_notes(model: dict, dataset: dict, notes: dict, *, save_results=None) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。

    `dataset`：交給 `logic.build_page_model` 的那一份（讀它的 `errors` 對出失敗字串）。
    `save_results`：上一次按「存檔」的結果 `{鍵: result}`（`source.save_setting` 的回傳），沒有就 None。
    """
    out = copy.deepcopy(model)
    token = notes["mask_token"]
    fail_map = _fail_map(dataset, notes)
    pending_tables = set(notes["pending_tables"])
    wired_tiers = set(notes["wired_tiers"])

    # ── SET-0：燈的外框與文字照 `44`（含 5.5 系統錯誤模板 `logic.fetch_failed_text`），只在下一行加 ★5；說明行加 ★1、★3 ──
    set0 = logic.find_block(out, "SET-0")
    set0["note_lines"] = [MASKED_NOTE] if _masked(set0["text"], token) else []
    if {"nav", "dividend"} <= pending_tables:
        set0["detail_lines"].append(TEXT_PENDING_NAV_DIVIDEND)
    set0["detail_lines"].append(TEXT_LOG_SCOPE)

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
    set1["fail_nodes"] = [_decorate_placeholder(n, fail_map, notes, "SET-1") for n in set1["fail_nodes"]]
    set1["live_lines"] = _structure_lines(notes, "SET-1")
    set1["detail_lines"] = _strip_demo(set1["detail_lines"])  # ✂2

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
    set2["detail_lines"] = _strip_demo(set2["detail_lines"]) + [TEXT_LOG_SCOPE]  # ✂2、★3

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
            # `44` SET-4：不符就不存檔；型別未定的鍵（SET-GAP-型別本頁配）同樣不存，說明照型別說明的體例。
            field["hint_lines"] = [TEXT_KIND_MISSING]
        # kind_mismatch：型別說明由 logic 依當下輸入畫出（`dataset["save_inputs"]`），這裡不另加。
    if not set4["inputs"]:
        # 讀不到設定、畫面上沒有輸入欄（SET-GAP-失敗無輸入欄）：上游失敗後存檔與讀取共用冷卻，所以正式模式下
        # 這是存檔失敗後最常見的樣子。「上面這一欄…」那一行照 logic 不印（會是假話），其餘照 ★6。
        set4["orphan_fail_lines"] = [
            [line for line in _save_fail_lines(results[k], token) if line != logic.TEXT_KEEP_INPUT]
            for k in sorted(results) if results[k]["status"] == "failed"
        ]
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
    return out
