# -*- coding: utf-8 -*-
"""市場總覽正式模式才有的畫面調整（純函式；不 import streamlit、不 import 舊樹）。

依據：客戶 2026-09-26 核准的文字線框草稿（正式入口 `ui_v2/app_mkt_live.py`）。
全部只在正式模式生效；示範模式（`ui_v2/app_mkt.py`）不經過本檔，一個字都不變。

1. 頁首只留提問句 —— 在 `page.py` 處理，本檔不涉。
2. 失敗訊息經過遮蔽（`ui_v2/mkt/source.py` 呼叫 L2 遮蔽）後，含遮蔽記號的訊息在下一行加註 `MASKED_NOTE`。
3. 資料未備的值，下一行寫原因（`REASON_TEXT`，依 L2 交出的原因代碼對照）。
4. ~~「存檔」停用並寫出原因~~ → **客戶 2026-10-13 裁示（狀態更新，不是漏刪）：存檔接上 `user_setting`**
   （`page.render(save_live=...)` 有傳時）；沒傳寫入函式時照舊停用並寫出原因。
   in-memory 說明與 updated_at 那一行不顯示（在 `page.py` 處理）。
4b. 客戶 2026-10-13 裁示：「套用」（只重算、不存檔）在正式模式停用並寫出原因 ——
   **未儲存的暫存設定不得影響正式結果**；正式結果只讀已存設定，存檔後下一次重新載入生效。
7. `user_setting` 三個 `mkt_` 鍵的解析與存檔輸入組成（`parse_user_settings`、`mkt4_save_entries`、
   `mkt5_save_entry`、`run_saves`；體例照 `ui_v2/alo/live.py`）。
5. 「重新取數」停用並寫出原因；來源冷卻中時改寫剩餘秒數。
6. 不新增「舊資料」字樣（本檔沒有這一條文案；新鮮度照舊由「延遲 N 日」交代）。

⚠️ 文案逐字照草稿；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
"""

from __future__ import annotations

import copy
import json
import math
from datetime import date

from . import logic

MASKED_NOTE = "已遮蔽憑證"
# 沒有傳寫入函式時（例如只傳 `load_live` 的呼叫端）照舊停用存檔並寫這一句。
SAVE_DISABLED_REASON = "設定存檔尚未接上，存了也留不到下次開頁"
# 客戶 2026-10-13 裁示：正式模式的「套用」停用（字面為本組擬定）。
APPLY_DISABLED_REASON = "正式結果只讀已存設定：請按「存檔」，下一次重新載入時生效"
RETRY_DISABLED_REASON = "重新取數尚未接上"

# 原因代碼（L2 `services/v2_tables/market_indicator.py` 的 PENDING_*）→ 畫面文案。
REASON_TEXT = {
    "fred_release_date": "原因：公布日尚未接上，暫不寫入",
    "ndc_no_release_date": "原因：來源不提供公布日",
    "fx_obs_date_rule": "原因：本指標規則未定，暫不顯示",  # 客戶 2026-09-26 裁示改白話
}

_CARD_CODES = ("MKT-1", "MKT-2", "MKT-3")


def cooldown_reason(cooldowns) -> str | None:
    """列出剩餘秒數最長的那一個來源，再加一句另有幾個；沒有冷卻中的來源回 None。"""
    live = [c for c in cooldowns or () if c.get("remaining_sec", 0) > 0]
    if not live:
        return None
    top = max(live, key=lambda c: c["remaining_sec"])
    text = f"來源冷卻中：{top['source']}，約剩 {math.ceil(top['remaining_sec'])} 秒"
    others = len(live) - 1
    if others:
        text += f"，另有 {others} 個來源冷卻中"
    return text


def _walk_buttons(node):
    if isinstance(node, dict):
        if "_action_kind" in node:
            yield node
        for value in node.values():
            yield from _walk_buttons(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_buttons(value)


def apply_live_notes(model: dict, notes: dict, *, save_wired: bool = False) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。

    notes：`{"pending": {鍵: 原因代碼}, "masked_keys": [鍵...], "cooldowns": [...]}`。
    未知的原因代碼當場 KeyError —— 沒有核准文案的原因不上畫面（§1：不自行編原因）。
    save_wired：存檔已接上 `user_setting`（`page.render` 有傳 `save_live`）。
    接上時存檔照 `logic` 的判定（兩欄完整才可存等）；沒接上時照舊一律停用。
    「套用」在正式模式一律停用（客戶 2026-10-13 裁示：未存的值不得進入正式結果）。
    """
    out = copy.deepcopy(model)
    pending = dict(notes.get("pending", {}))
    masked = set(notes.get("masked_keys", ()))

    for code in _CARD_CODES:
        block = logic.find_block(out, code)
        for mv in block["main_values"]:
            key = mv["_source_key"]
            lines = []
            if mv["_state"] == logic.STATE_MISSING and key in pending:
                lines.append(REASON_TEXT[pending[key]])
            if mv["_state"] == logic.STATE_ERROR and key in masked:
                lines.append(MASKED_NOTE)
            if lines:
                mv["note_lines"] = lines

    mkt7 = logic.find_block(out, "MKT-7")
    for row in mkt7["_rows"]:
        key = row["indicator_key"]
        if key in pending and any(b.get("text") == logic.STATE_MISSING for b in row["badges"]):
            mkt7["detail_lines"].append(f"{key}　{REASON_TEXT[pending[key]]}")

    retry_reason = cooldown_reason(notes.get("cooldowns")) or RETRY_DISABLED_REASON
    for button in _walk_buttons(out["blocks"]):
        if button["_action_kind"] == "取數":
            button["_enabled"] = False
            button["disabled_reason"] = retry_reason
        elif button["_action_kind"] == "存檔" and not save_wired:
            button["_enabled"] = False
            button["disabled_reason"] = SAVE_DISABLED_REASON
        elif button["_action_kind"] == "套用":
            button["_enabled"] = False
            button["disabled_reason"] = APPLY_DISABLED_REASON
    return out


# ───────────────────────── user_setting：三個 mkt_ 鍵 ─────────────────────────
# 鍵名與 value_kind 是 `ui_v2/set/spec.py::SPEC_SETTING_KEYS` 那三列的鏡像（本檔不 import set 頁），
# 由 tests/ui_v2/test_mkt_settings.py 逐字比對。
KEY_WINDOW = "mkt_window_days"
KEY_BASELINE = "mkt_baseline_date"
KEY_INDICATORS = "mkt_indicator_keys"
SETTING_KEYS = (KEY_WINDOW, KEY_BASELINE, KEY_INDICATORS)
VALUE_KINDS = {KEY_WINDOW: "int", KEY_BASELINE: "date", KEY_INDICATORS: "list"}


class BadSettingValue(ValueError):
    """試算表上的設定字串不是本頁約定的形狀。"""


def _reject_constant(name):
    # `json.loads` 預設吃 NaN／Infinity；一律不收（同 alo、同 L2 `settings_store.value_matches_kind`）。
    raise BadSettingValue(f"不收 {name}")


def _parse_window(text: str) -> int:
    digits = text.removeprefix("-")
    if not digits or not all("0" <= ch <= "9" for ch in digits):
        raise BadSettingValue(f"{KEY_WINDOW} 不是整數：{text!r}")
    value = int(text)
    if value <= 0:
        raise BadSettingValue(f"{KEY_WINDOW} 不是正整數：{text!r}")
    return value


def _parse_baseline(text: str) -> str:
    try:
        parsed = date.fromisoformat(text)
    except ValueError:
        raise BadSettingValue(f"{KEY_BASELINE} 不是 YYYY-MM-DD 日期：{text!r}") from None
    if parsed.isoformat() != text:
        raise BadSettingValue(f"{KEY_BASELINE} 不是 YYYY-MM-DD 日期：{text!r}")
    return text


def _parse_indicators(text: str) -> list:
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise BadSettingValue(f"{KEY_INDICATORS} 不是 JSON 陣列：{text!r}") from None
    if not isinstance(value, list) or not all(isinstance(v, str) and v.strip() for v in value):
        raise BadSettingValue(f"{KEY_INDICATORS} 須為非空字串組成的 JSON 陣列：{text!r}")
    if len(set(value)) != len(value):
        raise BadSettingValue(f"{KEY_INDICATORS} 有重複的鍵：{text!r}")
    if len(value) > logic.INDICATOR_PICK_CAP:
        raise BadSettingValue(f"{KEY_INDICATORS} 超過勾選上限 {logic.INDICATOR_PICK_CAP}：{text!r}")
    return value


_PARSERS = {KEY_WINDOW: _parse_window, KEY_BASELINE: _parse_baseline, KEY_INDICATORS: _parse_indicators}


def parse_user_settings(rows, broken_keys=()) -> tuple:
    """L2 `load_user_settings()` 的 `rows`／`broken_keys` → (`{"window_days", "baseline_date",
    "indicator_keys"}`, 失敗訊息或 None)。

    沒有那一列（或值為空）→ None（未設定）。解析不了 → 回訊息、三個值一律 None ——
    **不把它當成「尚未設定」**（L1 `load_user_settings` 的 docstring：`broken_keys` 的鍵
    「畫面應顯示錯誤狀態，不是 ⬜ 未設定」），也不交部分結果（體例同 hld）。
    ⚠️ **只存了半套（只有觀察窗或只有基準日）不是解析失敗**：照實交出，由 `logic` 判成「設定不完整」
    （客戶 2026-10-13 裁示 Q-07）。
    """
    rows = dict(rows or {})
    broken = set(broken_keys or ())
    problems = [f"{key} 這一列解析不了" for key in SETTING_KEYS if key in broken]
    values = {}
    for key in SETTING_KEYS:
        raw = (rows.get(key) or {}).get("setting_value")
        values[key] = None
        if raw is None or key in broken:
            continue
        try:
            values[key] = _PARSERS[key](raw)
        except BadSettingValue as exc:
            problems.append(str(exc))
    if problems:
        empty = {"window_days": None, "baseline_date": None, "indicator_keys": None}
        return empty, "設定值讀不到可用的形狀：" + "；".join(problems)
    return {"window_days": values[KEY_WINDOW], "baseline_date": values[KEY_BASELINE],
            "indicator_keys": values[KEY_INDICATORS]}, None


def mkt4_save_entries(window_days, baseline_date) -> list:
    """MKT-4 存檔要寫的兩鍵 → `[{"key", "value", "value_kind", "error"}, ...]`。

    客戶 2026-10-13 裁示 Q-07：**兩欄都完整才能存**。任一欄缺或不合格 → 兩鍵**都**帶 `error`、
    一鍵也不寫（不得產生半套正式設定）。畫面上的存檔鈕本來就停用，這一層是第二道。
    """
    problem = None
    if not logic._window_given(window_days):
        problem = logic.TEXT_SAVE_MISSING_WINDOW if window_days is None else "日數為正整數"
    elif not baseline_date:
        problem = logic.TEXT_SAVE_MISSING_BASELINE
    else:
        try:
            _parse_baseline(str(baseline_date))
        except BadSettingValue as exc:
            problem = str(exc)
    if problem:
        return [{"key": key, "value": None, "value_kind": VALUE_KINDS[key], "error": problem}
                for key in (KEY_WINDOW, KEY_BASELINE)]
    return [
        {"key": KEY_WINDOW, "value": str(int(window_days)), "value_kind": VALUE_KINDS[KEY_WINDOW], "error": None},
        {"key": KEY_BASELINE, "value": str(baseline_date), "value_kind": VALUE_KINDS[KEY_BASELINE], "error": None},
    ]


def mkt5_save_entry(selected, available) -> list:
    """MKT-5 存檔要寫的一鍵。只收可勾清單裡的鍵、依字面值排序（44 MKT-5：清單以字面值排列）。"""
    allowed = set(available)
    chosen = sorted(k for k in selected if k in allowed)
    error = None
    if len(chosen) > logic.INDICATOR_PICK_CAP:
        error = "已達勾選上限 6，請先取消一項"
    text = json.dumps(chosen, ensure_ascii=False)
    return [{"key": KEY_INDICATORS, "value": text, "value_kind": VALUE_KINDS[KEY_INDICATORS], "error": error}]


def run_saves(entries, save, *, stop_on_failure: bool = True) -> dict:
    """逐鍵寫入。回 `{鍵: None（已存）或失敗訊息原文}`。

    save：`source.save_setting(鍵, 值或 None, value_kind)`，回 L2 `save_setting_for_page` 的 dict。
    任一 entry 帶 `error` → **一鍵都不寫**（全部記成那個訊息）。
    stop_on_failure：前一鍵寫入失敗就不再寫下一鍵（MKT-4 兩鍵：先寫的那一鍵失敗時，不讓後一鍵單獨落地成半套）。
    ⚠️ 後一鍵失敗而前一鍵已寫入時，試算表上會留下半套 —— L1 是逐列追加、沒有交易，這一層擋不住；
       讀回時 `logic` 判成「設定不完整」，不出任何比較數字（Q-07 讀取端的規則）。已登記待裁。
    寫入以外的例外照樣往上拋，不吞。
    """
    blocked = [e for e in entries if e["error"] is not None]
    if blocked:
        return {e["key"]: blocked[0]["error"] for e in entries}
    results = {}
    failed = False
    for entry in entries:
        if failed and stop_on_failure:
            results[entry["key"]] = "前一個鍵存檔失敗，本鍵未寫入"
            continue
        out = save(entry["key"], entry["value"], entry["value_kind"])
        if out["status"] == "saved":
            results[entry["key"]] = None
        else:
            # 訊息已由 L2 遮蔽；萬一是空字串，退回狀態碼原文，不讓失敗變成「看起來成功」。
            results[entry["key"]] = out.get("message") or out["status"]
            failed = True
    return results


def build_live_model(live_input: dict, *, field_window_days=None, field_baseline_date=None,
                     field_selected_keys=(), save_wired: bool = False, save_results=None) -> dict:
    """正式模式整頁模型（`page.render` 正式路徑呼叫這一支；測試可直接走 source → 本函式 → 模型）。

    客戶 2026-10-13 裁示的分工，全寫在這一處：
    - **正式結果只讀 `load_live` 交回的已存設定**（`notes["settings"]`）——三張核心卡的比較條件、
      下方明細的勾選過濾，一律取這一組；
    - `field_*` ＝ 輸入欄／勾選框**當下**的值，只交給 `logic` 決定欄位怎麼畫、存檔能不能按，
      **不進任何正式計算**（未儲存的暫存設定不得影響正式結果）；
    - 可勾清單取資料層註冊的鍵（`notes["available_keys"]`）。
    """
    dataset = live_input["dataset"]
    notes = live_input["notes"]
    settings = notes.get("settings") or {}
    model = logic.build_page_model(
        dataset,
        window_days=settings.get("window_days"),
        baseline_date=settings.get("baseline_date"),
        selected_keys=settings.get("indicator_keys"),
        field_window_days=field_window_days,
        field_baseline_date=field_baseline_date,
        field_selected_keys=list(field_selected_keys or ()),
        available_keys=notes.get("available_keys"),
        settings_error=notes.get("settings_error"),
    )
    model = apply_live_notes(model, notes, save_wired=save_wired)
    return apply_save_results(model, save_results)


# 存檔結果的文案（字面為本組擬定；失敗那一句體例同 alo「存檔寫入失敗：…」，訊息原文照印、不改寫）。
TEXT_SAVED = "已存檔"
TEXT_SAVE_FAILED = "存檔寫入失敗："
_SAVE_BLOCK = {KEY_WINDOW: "MKT-4", KEY_BASELINE: "MKT-4", KEY_INDICATORS: "MKT-5"}


def apply_save_results(model: dict, results) -> dict:
    """把正式模式按「存檔」那一次的逐鍵結果寫到該塊的說明行（回複本，不改呼叫端那一份）。

    results：`{鍵: None（已存）或失敗訊息原文}`（`run_saves` 的回傳，`page.py` 記在 session）。
    一塊的鍵全部存成功 → 一行「已存檔」；任一鍵失敗 → 逐鍵寫失敗訊息原文（44 MKT-4：
    「存檔寫入失敗 → 欄位下方顯示失敗訊息原文」）。失敗不改任何正式結果（三張核心卡只讀已存設定）。
    """
    out = copy.deepcopy(model)
    by_block = {}
    for key, message in (results or {}).items():
        by_block.setdefault(_SAVE_BLOCK[key], []).append((key, message))
    for code, pairs in by_block.items():
        block = logic.find_block(out, code)
        failed = [(key, message) for key, message in pairs if message is not None]
        if failed:
            block["detail_lines"].extend(f"{TEXT_SAVE_FAILED}{key}：{message}" for key, message in failed)
        else:
            block["detail_lines"].append(TEXT_SAVED)
    return out
