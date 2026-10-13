# -*- coding: utf-8 -*-
"""標的探索正式模式才有的資料組裝與畫面調整（純函式；不 import streamlit、不 import 舊樹、不 import fixtures）。

依據：客戶 2026-10-13 裁示（B 線標的探索正式模式第一批 —— 骨架＋設定存讀＋母體代碼）：
- **篩選條件只有成功儲存的設定才生效**；儲存後於下一次重新載入／重新整理時套用；
  未儲存的暫存條件不得影響正式結果（`build_live_model` → `logic.build_page_model(saved_only=True)`）。
- **基本資料缺欄：基金仍保留在清單**，缺哪欄就顯示「⬜ 資料未備」，不得因單一欄位缺失讓整檔無聲消失。
  本批只有代碼，其餘欄一律 ⬜ 並寫出原因（`CELL_REASON`）。
- **禁止從基金名稱、代碼或 AI 推測任何屬性；缺值保持缺值、不填 0。**

示範模式（`ui_v2/app_exp.py`）不經過本檔，一個字都不變。分層照姊妹頁 mkt／alo：
`source.py`（L3 呼叫薄層，讀秘密值、呼叫 L2）→ 本檔（組 dataset、解析設定、組存檔輸入）→ `page.py`（純渲染）。

⚠️ 本檔新寫的畫面文案（`CELL_REASON`、`TEXT_*`）**沒有經過客戶草稿**（`49` §3.4 第 7 列：新文案一律先出草稿），
   字面為本組擬定，逐條列在交付報告的待裁段。
"""

from __future__ import annotations

import copy
import json

from . import logic

# ───────────────────────── user_setting：四個 exp_ 鍵 ─────────────────────────
# 鍵名與 value_kind 是 `ui_v2/set/spec.py::SPEC_SETTING_KEYS` 那四列的鏡像（本檔不 import set 頁），
# 由 tests/ui_v2/test_exp_live_logic.py 逐字比對。
KEY_RULES = "exp_filter_rules"
KEY_COLUMNS = "exp_visible_columns"
KEY_SORT = "exp_sort_column"
KEY_WATCH = "exp_watchlist"
SETTING_KEYS = (KEY_RULES, KEY_COLUMNS, KEY_SORT, KEY_WATCH)
VALUE_KINDS = {KEY_RULES: "rules", KEY_COLUMNS: "list", KEY_SORT: "list", KEY_WATCH: "list"}

# 比較方向（`fixtures.OPERATORS` 的鏡像；正式路徑不 import fixtures —— 由測試比對兩者相等）。
RULE_OPERATORS = ("等於", "不等於", "大於", "小於", "早於或等於", "晚於")
_RULE_FIELDS = ("field", "op", "value")


class BadSettingValue(ValueError):
    """試算表上的設定字串不是本頁約定的形狀。"""


def _reject_constant(name):
    raise BadSettingValue(f"不收 {name}")


def _json_list(key, text):
    try:
        value = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError):
        raise BadSettingValue(f"{key} 不是 JSON 陣列：{text!r}") from None
    if not isinstance(value, list):
        raise BadSettingValue(f"{key} 不是 JSON 陣列：{text!r}")
    return value


def _parse_rules(text):
    out = []
    for index, rule in enumerate(_json_list(KEY_RULES, text), start=1):
        if not isinstance(rule, dict) or set(rule) != set(_RULE_FIELDS) \
                or not all(isinstance(rule[name], str) for name in _RULE_FIELDS):
            raise BadSettingValue(f"{KEY_RULES} 第 {index} 列不是「欄位＋比較方向＋數值」三個字串：{rule!r}")
        problem = rule_problem(rule)
        if problem:
            raise BadSettingValue(f"{KEY_RULES} 第 {index} 列{problem}")
        out.append({name: rule[name] for name in _RULE_FIELDS})
    return tuple(out)


def _parse_columns(text):
    value = _json_list(KEY_COLUMNS, text)
    if not all(isinstance(v, str) and v in logic.COLUMN_ORDER for v in value):
        raise BadSettingValue(f"{KEY_COLUMNS} 含可選欄位以外的值：{text!r}")
    if len(set(value)) != len(value):
        raise BadSettingValue(f"{KEY_COLUMNS} 有重複的欄位：{text!r}")
    return tuple(value)


def _parse_sort(text):
    """`exp_sort_column` 的存法（本組擬定；`44` 4.5 的 `value_kind` 六種沒有一種是「單一欄位名」，`E-17`）：
    `value_kind` 取 `ui_v2/set/spec.py` 已登記的 `list`，值為長度 0 或 1 的 JSON 陣列 ——
    `[]` ＝ 存了「不排序」，`["nav_date"]` ＝ 依該欄排序。"""
    value = _json_list(KEY_SORT, text)
    if len(value) > 1 or not all(isinstance(v, str) and v in logic.COLUMN_ORDER for v in value):
        raise BadSettingValue(f"{KEY_SORT} 須為空陣列或只含一個可選欄位：{text!r}")
    return value[0] if value else None


def _parse_watchlist(text):
    value = _json_list(KEY_WATCH, text)
    if not all(isinstance(v, str) and v.strip() and v == v.strip() for v in value):
        raise BadSettingValue(f"{KEY_WATCH} 須為不帶前後空白的非空字串：{text!r}")
    if len(set(value)) != len(value):
        raise BadSettingValue(f"{KEY_WATCH} 有重複的代碼：{text!r}")
    return tuple(value)


_PARSERS = {KEY_RULES: _parse_rules, KEY_COLUMNS: _parse_columns, KEY_SORT: _parse_sort, KEY_WATCH: _parse_watchlist}
EMPTY_SETTINGS = {KEY_RULES: None, KEY_COLUMNS: None, KEY_SORT: None, KEY_WATCH: None}


def rule_problem(rule) -> str | None:
    """一列條件能不能存／能不能用：欄位要在 `fund_profile` 欄位名清單內、比較方向要在六個之內。
    數值欄可以留空（`44` `EXP-1`：留空 → 該列不生效）。沒問題回 None。"""
    if rule.get("field") not in logic.FUND_PROFILE_FIELDS:
        return f"的欄位「{rule.get('field')}」不在可選欄位內"
    if rule.get("op") not in RULE_OPERATORS:
        return f"的比較方向「{rule.get('op')}」不在可選的六個之內"
    return None


def parse_user_settings(rows, broken_keys=()) -> tuple:
    """L2 `load_user_settings()` 的 `rows`／`broken_keys` → (`{鍵: 解析後的值或 None}`, 失敗訊息或 None)。

    沒有那一列（或值為空）→ None（未設定）。解析不了 → 回訊息、四個值一律 None ——
    **不把它當成「尚未設定」**（L1 docstring：`broken_keys` 的鍵「畫面應顯示錯誤狀態，不是 ⬜ 未設定」），
    也不交部分結果（體例同 mkt／hld）。
    `exp_sort_column` 存了 `[]`（不排序）與沒有那一列，兩者解析後都是 None —— 對畫面而言同一件事（都不排序）。
    """
    rows = dict(rows or {})
    broken = set(broken_keys or ())
    problems = [f"{key} 這一列解析不了" for key in SETTING_KEYS if key in broken]
    values = dict(EMPTY_SETTINGS)
    for key in SETTING_KEYS:
        raw = (rows.get(key) or {}).get("setting_value")
        if raw in (None, "") or key in broken:
            continue
        try:
            values[key] = _PARSERS[key](raw)
        except BadSettingValue as exc:
            problems.append(str(exc))
    if problems:
        return dict(EMPTY_SETTINGS), "設定值讀不到可用的形狀：" + "；".join(problems)
    return values, None


# ───────────────────────── dataset ─────────────────────────


def _profile_row(code):
    """只有代碼的 `fund_profile` 列：其餘欄一律 None（**缺值保持缺值、不填 0、不從代碼推任何屬性**）。"""
    row = {name: None for name in logic.FUND_PROFILE_FIELDS}
    row["fund_code"] = code
    return row


def _setting_rows(settings) -> list:
    """`logic` 讀的 `user_setting` 形狀（與示範資料同形：`setting_value` 已解析成 list／字串）。"""
    out = []
    for key in SETTING_KEYS:
        value = settings.get(key)
        if key == KEY_SORT:
            shown = value
        else:
            shown = list(value) if value is not None else None
        out.append({"setting_key": key, "setting_value": shown, "value_kind": VALUE_KINDS[key],
                    "updated_at": None})
    return out


def build_dataset(pool, settings) -> dict:
    """L2 `exp_universe.load_pool_codes` 的回傳 ＋ 已存設定 → 與示範資料同形的 dataset。

    - 母體讀不到（`failed`）或未設定雲端（`pool_not_cloud`）→ `fund_profile` 為空、`errors["fund_profile"]`
      放訊息原文（已遮蔽）；`logic` 照取數失敗那條路畫，**不講成「沒有符合的基金」**。
    - `nav`、`dividend`、`div_ratio_pct` 本批**沒有去取**（不是讀失敗）→ 空，不進 `errors`；
      那幾格由 `apply_live_notes` 寫「⬜ 資料未備：淨值／配息尚未接入」。
    """
    errors = {}
    profiles = []
    if pool["status"] == "ok":
        profiles = [_profile_row(code) for code in pool["codes"]]
    else:
        errors["fund_profile"] = pool["message"] or pool["status"]
    return {
        "fund_profile": profiles,
        "nav": [],
        "dividend": [],
        "user_setting": _setting_rows(settings),
        "div_ratio_pct": {},
        "errors": errors,
        "save_errors": {},
    }


# ───────────────────────── 畫面調整 ─────────────────────────

REASON_PROFILE = "基本資料尚未接入"
REASON_NAV = "淨值尚未接入"
REASON_DIVIDEND = "配息尚未接入"
CELL_REASON = {
    "fund_name": REASON_PROFILE,
    "ccy": REASON_PROFILE,
    "inception_on": REASON_PROFILE,
    "dividend_policy": REASON_PROFILE,
    "mgmt_fee_rate_pct": REASON_PROFILE,
    "nav_date": REASON_NAV,
    "nav_orig_ccy": REASON_NAV,
    "div_ratio_pct": REASON_DIVIDEND,
}


def missing_text(column) -> str:
    return f"{logic.ND_TEXT}：{CELL_REASON[column]}"


# 按鈕類別（`logic.BUTTON_KINDS` 的兩個成員）；`page.py` 依類別接 on_click，字面住在這裡、不寫在畫面層。
ACTION_SAVE = "存檔"
ACTION_ADD_ROW = "新增列"

SAVE_DISABLED_REASON = "設定存檔尚未接上，存了也留不到下次開頁"
SAVE_UNREADABLE_REASON = "已存設定讀不到，暫不提供存檔（存了會蓋掉讀不到的那一份）"
TEXT_OPERATORS = "比較方向可填：" + "、".join(RULE_OPERATORS) + "。"
TEXT_UNSAVED_EXP4 = "未存檔：欄位勾選或排序欄位與已存值不同，存檔後下一次重新載入才生效"


def pool_lines(pool) -> list:
    """`EXP-2` 說明行：母體從哪裡來、略過了什麼（只在讀到時寫；讀不到由 `logic` 照取數失敗畫）。"""
    if pool["status"] != "ok":
        return []
    lines = [
        (f"母體：選股池的基金代碼 {len(pool['codes'])} 檔。只取代碼；"
         "選股池上的名稱、幣別、類別一律不用（不可信，客戶 2026-10-13 判定）。"),
    ]
    if pool["dropped_blank"]:
        lines.append(f"選股池有 {pool['dropped_blank']} 列代碼為空白，未列入。")
    if pool["duplicates"]:
        lines.append(f"選股池有 {pool['duplicates']} 列代碼重複，只列一次。")
    return lines


def _fill_missing(cells):
    for column, cell in cells.items():
        if cell["_state"] == logic.STATE_MISSING and cell["text"] == "⬜" and column in CELL_REASON:
            cell["text"] = missing_text(column)


def apply_live_notes(model: dict, notes: dict, *, save_wired: bool = False) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。

    - 缺的格寫原因（`EXP-2`、`EXP-3`、`EXP-6`）；
    - `EXP-2` 說明行寫母體來源；`EXP-1` 說明行補比較方向可填哪些；
    - 「存檔」類按鈕：沒接上寫入函式 → 停用；已存設定讀不到 → 停用（存了會蓋掉讀不到的那一份）。
    """
    out = copy.deepcopy(model)
    for row in logic.find_block(out, "EXP-2")["_rows"]:
        _fill_missing(row["_cells"])
    for column in logic.find_block(out, "EXP-3")["_columns"]:
        _fill_missing(column["_cells"])
    exp6 = logic.find_block(out, "EXP-6")
    if exp6["_fields"]:
        _fill_missing(dict(zip((key for key, _label in logic.EXP6_FIELDS), exp6["_fields"])))
    logic.find_block(out, "EXP-2")["detail_lines"].extend(pool_lines(notes["pool"]))
    logic.find_block(out, "EXP-1")["detail_lines"].append(TEXT_OPERATORS)

    reason = None
    if not save_wired:
        reason = SAVE_DISABLED_REASON
    elif notes.get("settings_error"):
        reason = SAVE_UNREADABLE_REASON
    if notes.get("settings_error"):
        # 2026-10-13 稽核 L 回修：讀不到設定時「新增條件」也停用 —— 那一輪新增的列沒有已存值可對照，
        # 恢復後存檔會把它連同空白蓋回雲端。
        for button in logic.find_block(out, "EXP-1")["buttons"]:
            if button["_action_kind"] == ACTION_ADD_ROW:
                button["_enabled"] = False
                button["disabled_reason"] = SAVE_UNREADABLE_REASON
    if reason:
        for code in ("EXP-1", "EXP-4", "EXP-5"):
            for button in logic.find_block(out, code)["buttons"]:
                if button["_action_kind"] == ACTION_SAVE:
                    button["_enabled"] = False
                    button["disabled_reason"] = reason
    return out


# ───────────────────────── 存檔輸入 ─────────────────────────


def _entry(key, value, error=None):
    return {"key": key, "value": value, "value_kind": VALUE_KINDS[key], "error": error}


def exp1_save_entries(field_rules) -> list:
    """`EXP-1` 存檔：條件列的當下內容原樣寫回 `exp_filter_rules`（`44` `EXP-1` 判準：重新載入後逐字相同）。

    欄位或比較方向不在可選清單內 → 帶 `error`、不寫（那一列存回去下一次載入會讀不了）。
    ⚠️ 數值留空的列**照樣寫回**（`44` `EXP-1` 塊下方「其三」未裁；本組取「原樣寫回」，理由是同一塊判準要
    「條件列的內容與存檔前填進去的逐字相同」）—— 列在交付報告待裁段。
    """
    rules = [{name: str(rule.get(name, "")) for name in _RULE_FIELDS} for rule in field_rules]
    problems = []
    for index, rule in enumerate(rules, start=1):
        problem = rule_problem(rule)
        if problem:
            problems.append(f"第 {index} 列{problem}")
    if problems:
        return [_entry(KEY_RULES, None, "未存檔：" + "；".join(problems))]
    return [_entry(KEY_RULES, json.dumps(rules, ensure_ascii=False))]


def exp4_save_entries(field_columns, field_sort) -> list:
    """`EXP-4` 存檔：一枚按鈕寫兩鍵（`44` `EXP-4`：「一枚按鈕同時寫兩鍵，不拆成兩枚」）。"""
    columns = [c for c in logic.COLUMN_ORDER if c in set(field_columns or ())]
    unknown = sorted(set(field_columns or ()) - set(logic.COLUMN_ORDER))
    if unknown or (field_sort is not None and field_sort not in logic.COLUMN_ORDER):
        error = "未存檔：含可選欄位以外的值：" + "、".join(unknown + ([field_sort] if field_sort else []))
        return [_entry(KEY_COLUMNS, None, error), _entry(KEY_SORT, None, error)]
    return [
        _entry(KEY_COLUMNS, json.dumps(columns, ensure_ascii=False)),
        _entry(KEY_SORT, json.dumps([field_sort] if field_sort else [], ensure_ascii=False)),
    ]


def exp5_save_entries(saved_watchlist, picked, settings_error=None) -> list:
    """`EXP-5` 存檔：已存觀察清單 ∪ 這次勾起的檔（同一檔按兩次只出現一次；`44` `EXP-5` 判準）。

    已存設定讀不到 → 帶 `error`、不寫：那時「已存觀察清單」是未知的，照寫會把它蓋成只剩這次勾的幾檔。
    """
    if settings_error:
        return [_entry(KEY_WATCH, None, SAVE_UNREADABLE_REASON)]
    after = sorted(set(saved_watchlist or ()) | set(picked or ()))
    if not after:
        return [_entry(KEY_WATCH, None, logic.TEXT_NO_PICK)]
    return [_entry(KEY_WATCH, json.dumps(after, ensure_ascii=False))]


def run_saves(entries, save, *, stop_on_failure: bool = True) -> dict:
    """逐鍵寫入。回 `{鍵: None（已存）或失敗訊息原文}`（體例照 `ui_v2/mkt/live.py::run_saves`，本檔不 import 姊妹頁）。

    save：`source.save_setting(鍵, 值或 None, value_kind)`，回 L2 `save_setting_for_page` 的 dict。
    任一 entry 帶 `error` → **一鍵都不寫**（全部記成那個訊息）。
    stop_on_failure：前一鍵寫入失敗就不再寫下一鍵（`EXP-4`：先寫的那一鍵失敗時，不讓後面那一鍵單獨落地）。
    ⚠️ 後一鍵失敗而前一鍵已寫入時，試算表上會留下「新欄位 ＋ 舊排序」—— 兩鍵各自合法、讀得回來；
    畫面上逐鍵寫出哪一鍵成功、哪一鍵失敗（`apply_save_results`），不整體顯示成功。
    寫入以外的例外照樣往上拋，不吞。
    """
    blocked = [e for e in entries if e["error"] is not None]
    if blocked:
        return {e["key"]: blocked[0]["error"] for e in entries}
    results = {}
    failed = False
    for entry in entries:
        if failed and stop_on_failure:
            # ~~"前一個鍵存檔失敗，本鍵未寫入"~~ → 2026-10-13 稽核回修：這一鍵沒有去寫，不冠「寫入失敗」。
            results[entry["key"]] = TEXT_SKIPPED
            continue
        out = save(entry["key"], entry["value"], entry["value_kind"])
        if out["status"] == "saved":
            results[entry["key"]] = None
        else:
            results[entry["key"]] = out.get("message") or out["status"]
            failed = True
    return results


TEXT_SAVED = "已存檔"
# 2026-10-13 稽核回修（字面為本組擬定）：
# - 前一鍵失敗而本鍵沒有去寫：照實寫「未寫入」，不冠「存檔寫入失敗」（本鍵根本沒有寫入動作）。
# - 上次存檔成功、之後又改了欄位：不再單寫「已存檔」（那會與同卡的「未存檔」並排、互相矛盾）。
TEXT_SKIPPED = "未寫入：前一個鍵存檔失敗"
TEXT_SAVED_THEN_EDITED = "上次存檔已成功；目前有未存的變更"
_SAVE_BLOCK = {KEY_RULES: "EXP-1", KEY_COLUMNS: "EXP-4", KEY_SORT: "EXP-4", KEY_WATCH: "EXP-5"}
# 欄位與已存值不同時，各塊說明行上的那一句（`apply_save_results` 據此判斷「存完又改了」）。
_UNSAVED_MARK = {"EXP-1": logic.TEXT_UNSAVED_RULES, "EXP-4": TEXT_UNSAVED_EXP4}


def apply_save_results(model: dict, results) -> dict:
    """把按「存檔」那一次的逐鍵結果寫到該塊（回複本）。

    一塊的鍵全部成功 → 說明行一行「已存檔」（下一次重新載入才生效 —— 正式結果只吃已存值）；
    任一鍵失敗 → **逐鍵**寫：成功的那一鍵在說明行寫「<鍵>：已存檔」，失敗的那一鍵在失敗行寫
    「存檔寫入失敗：<鍵>：<訊息原文>」（`44` `EXP-1`／`EXP-4`／`EXP-5` 空狀態欄：卡上顯示失敗訊息原文）。
    `EXP-4` 一成一敗時因此照實講哪一鍵成功、哪一鍵失敗，**不整體顯示成功**（`44` `EXP-4` 塊下方登記的那一題，
    本組取「逐鍵照實寫」，不替客戶決定要不要回滾成功的那一鍵 —— 列在待裁段）。
    """
    out = copy.deepcopy(model)
    by_block = {}
    for key, message in (results or {}).items():
        by_block.setdefault(_SAVE_BLOCK[key], []).append((key, message))
    for code, pairs in by_block.items():
        block = logic.find_block(out, code)
        edited = _UNSAVED_MARK.get(code) in block["detail_lines"]
        saved_text = TEXT_SAVED_THEN_EDITED if edited else TEXT_SAVED
        failed = [(key, message) for key, message in pairs if message is not None]
        if not failed:
            block["detail_lines"].append(saved_text)
            continue
        for key, message in pairs:
            if message is None:
                block["detail_lines"].append(f"{key}：{saved_text}")
            elif message == TEXT_SKIPPED:
                block.setdefault("error_lines", []).append(f"{key}：{TEXT_SKIPPED}")
            else:
                block.setdefault("error_lines", []).append(f"{logic.TEXT_SAVE_FAILED}：{key}：{message}")
    return out


# ───────────────────────── 已存值指紋（2026-10-13 稽核 L 回修：防止空值蓋掉雲端） ─────────────────────────


def settings_fingerprint(settings) -> str:
    """已存設定的確定性指紋。`page.py` 記下「本 session 的輸入欄是用哪一版已存值填的」，
    指紋一變（首次、讀失敗後恢復、他處改了設定）就強制以已存值覆寫輸入欄，
    不讓讀失敗那一輪留下的空白輸入欄在恢復後被存回去蓋掉雲端。"""
    def plain(value):
        if isinstance(value, tuple):
            return [plain(v) for v in value]
        if isinstance(value, dict):
            return {k: plain(v) for k, v in sorted(value.items())}
        return value
    return json.dumps({key: plain(settings.get(key)) for key in SETTING_KEYS}, ensure_ascii=False, sort_keys=True)


def settings_after_saves(settings, entries, results) -> dict:
    """存檔後「試算表上應該是什麼」：只把**寫成功**的鍵換成寫進去的值（解析成與 `parse_user_settings` 同形），
    其餘照舊。`page.py` 存檔成功後以它更新指紋 —— 下一次重跑讀回的已存值與它相同，就不會被當成「他處改了」。"""
    out = dict(settings)
    for entry in entries:
        if (results or {}).get(entry["key"], "x") is None and entry["value"] is not None:
            out[entry["key"]] = _PARSERS[entry["key"]](entry["value"])
    return out


def build_live_model(live_input: dict, *, field_rules=None, field_columns=None, field_sort=None,
                     compare_checked=(), watch_checked=(), save_wired: bool = False, save_results=None) -> dict:
    """正式模式整頁模型（`page.render` 正式路徑呼叫這一支；測試可直接走 source → 本函式 → 模型）。

    客戶 2026-10-13 裁示的分工全寫在這一處：
    - **正式結果只讀 `load_live` 交回的已存設定**（`dataset["user_setting"]`）—— 篩選、顯示欄、排序、觀察清單；
    - `field_*` ＝ 輸入欄／勾選框**當下**的值，只決定欄位怎麼畫、存檔寫什麼，**不進任何正式計算**；
    - `compare_checked`／`watch_checked` 是兩組勾選框的當下狀態（只餵 `EXP-3`／`EXP-6` 與 `EXP-5` 的存檔，
      不是篩選條件）。
    """
    dataset = live_input["dataset"]
    notes = live_input["notes"]
    settings_error = notes.get("settings_error")
    if field_rules is not None:
        # 畫面層的列可能帶自己的列識別碼；比對「與已存值是否不同」只看三個欄位。
        field_rules = [{name: str(rule.get(name, "")) for name in _RULE_FIELDS} for rule in field_rules]
    model = logic.build_page_model(
        dataset,
        draft_rules=field_rules,
        compare_checked=compare_checked,
        watch_checked=watch_checked,
        demo_hint=False,
        saved_only=True,
        settings_error=settings_error,
        unspecified_as_error=True,
        code_column=True,
    )
    model = apply_live_notes(model, notes, save_wired=save_wired)
    if not settings_error and (field_columns is not None or field_sort is not None):
        settings = notes.get("settings") or {}
        if set(field_columns or ()) != set(settings.get(KEY_COLUMNS) or ()) \
                or field_sort != settings.get(KEY_SORT):
            logic.find_block(model, "EXP-4")["detail_lines"].append(TEXT_UNSAVED_EXP4)
    return apply_save_results(model, save_results)
