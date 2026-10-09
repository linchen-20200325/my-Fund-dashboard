# -*- coding: utf-8 -*-
"""資產配置正式模式才有的純函式：設定值解析、示意字樣移除、寫入端按鈕的停用原因。

依據 docs/v2/49_data_integration_plan.md §3.3（`source.py` 那一列）、§3.4 第 6 項（正式入口不帶示意字樣），
以及 2026-09-28 客戶核准的 `docs/wireframes/draft_alo_live.html`。

- **不 import streamlit、不 import 舊樹、不 import fixtures。** 本檔是純函式，可以在沒有 streamlit
  的直譯器裡單獨測（守衛：tests/ui_v2/test_ui_v2_live_import_guard.py）。
- 本檔只做兩件事：(1) 把試算表上的設定字串解析成 `logic` 吃得下的原生值；
  (2) 把 `logic.build_page_model` 產出的模型調整成正式模式該有的樣子。
- ~~本輪（接線骨架）只接讀，不接寫。~~ → 2026-10-09 起 ALO-1／ALO-4 兩枚「存檔」接上寫入
  （本檔放組值與判讀成敗的純函式，寫入本身在 `source.py`、呼叫在 `page.py`）；ALO-3 的存檔
  客戶仍未授權，照舊停用。草稿 §D 的七件新東西（DIRECT 警示、讀取量診斷、
  沒寫進持倉的附表、`_保單資料` 缺列、E1～E14 文案、新增類別元件）**不在本檔**，下一輪再做。

⚠️ 文案逐字照草稿；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
"""

from __future__ import annotations

import copy
import json
import math
import re

from . import logic

# ~~本輪只接讀不接寫 ⇒ 會寫 `user_setting` 的按鈕一律停用並寫出原因：~~
# → 2026-10-09 更正：ALO-1／ALO-4 的存檔已接上寫入（`SAVE_WIRED_KEYS`），停用只剩**還沒接上的那一類** ——
#    實質就是 ALO-3（`alo_scenario_input`，客戶 2026-10-09 仍未授權其存檔）。以下理由對那一枚照舊成立：
# 一枚按得下去、按了卻什麼都不會被存下來的「存檔」，就是 `CLAUDE.md` §1 禁止的「讓流程看起來成功」。
#
# 文案由**客戶 2026-09-28 逐字核准**（草稿 `docs/wireframes/draft_alo_save_disabled.html`，PR #861 已 merge）。
# ⛔ 逐字，不准加字、不准補後半句：客戶砍掉了原提案的後半句「按了不會存下任何東西」，
#    理由是那半句在本頁**誤導** —— 它暗示「有存但不會持久」，而本頁**根本沒有存這個動作**。
# ⚠️ **刻意不沿用** `ui_v2/mkt/live.py` 的「設定存檔尚未接上，存了也留不到下次開頁」：
#    那一句對 mkt 字面正確（`ui_v2/mkt/page.py` 有 2 個 `on_click`，`_on_save` 真的寫進 `st.session_state`），
#    但對本頁是**假的**（`ui_v2/alo/page.py` 的 `on_click` 0 命中、`ui_v2/alo/source.py` 沒有任何 save 函式）。
#    量測見上述草稿；本組亦於 `6c78294` 重跑確認（mkt 2／alo 0／alo source 0）。
# ✅ 正例（`CLAUDE.md` §-2.A 第 3 款：禁令要同時寫出正例）：**只停用會寫的那一類**。
#    「匯出」（真的能下載）、「前往 Sheets 維護持倉」、「新增假設」三枚 `_writes` 為空，**一律不停用**；
#    「匯出」自己那條「目前沒有可匯出的列」是另一回事，不歸本檔管、一個字不碰。
# ~~接上寫入之後這一段就該整段拿掉。~~ → 2026-10-09：只接上了四個鍵，ALO-3 那一枚仍要這一句，所以留著；
#    本句對 ALO-3 仍為真（該鍵在本頁沒有寫入路徑）。等 ALO-3 也接上，這一段才整段拿掉。
SAVE_DISABLED_REASON = "存檔寫入端尚未接上，這一輪只讀不寫"

# `44` 4.5 `user_setting` 裡屬於本頁的五個鍵（順序同 `ui_v2/alo/fixtures.py::user_settings`）。
# `logic._setting_row` 讀不到就 KeyError，所以五列**一定要都在**，沒設定的那一列值放 None。
SETTING_KEYS = (
    "alo_target_weights",
    "alo_tolerance_pp",
    "alo_basis",
    "alo_bucket_names",
    "alo_scenario_input",
)


# 已接上寫入的四個鍵（ALO-1 兩鍵、ALO-4 兩鍵）。`apply_live_notes` 依按鈕的 `_keys` 判斷要不要停用：
# 一枚按鈕要寫的鍵**全部**在這裡才放行，否則照舊停用（fail-closed；不認塊代碼字串）。
SAVE_WIRED_KEYS = frozenset({
    "alo_target_weights",
    "alo_tolerance_pp",
    "alo_basis",
    "alo_bucket_names",
})

# 寫入時交給 L2 的 `value_kind`。`alo_basis` 的 "list" 是 L2 `settings_store.ENUM_KIND` 的鏡像
# （本檔不得 import services），由 tests/test_v2_tables_settings_store_page.py 無條件比對；
# 就算鏡像漂移，L2 `check_setting_value` 也會回 `kind_mismatch` 不存 —— 寫不進去，不會寫錯。
VALUE_KINDS = {
    "alo_target_weights": "list",
    "alo_tolerance_pp": "float",
    "alo_basis": "list",
    "alo_bucket_names": "list",
}


class BadSettingValue(ValueError):
    """試算表上的設定字串不是本頁約定的形狀。訊息拿去填 `errors["user_setting"]`。"""


def _reject_constant(name):
    # `json.loads` 預設吃 NaN／Infinity；本頁一律不收（同 L2 `settings_store.value_matches_kind`）。
    raise BadSettingValue(f"值裡有 {name}")


def _json_array(text: str, key: str) -> list:
    if not isinstance(text, str):
        raise BadSettingValue(f"{key} 的值不是字串")
    if text != text.strip():
        raise BadSettingValue(f"{key} 的值前後有空白")
    try:
        data = json.loads(text, parse_constant=_reject_constant)
    except BadSettingValue as exc:
        # `parse_constant` 收不到鍵名，在這裡補上 —— 訊息要看得出是哪一個鍵壞掉。
        raise BadSettingValue(f"{key} 的{exc}") from None
    except (ValueError, RecursionError) as exc:
        raise BadSettingValue(f"{key} 的值不是 JSON（{type(exc).__name__}）") from None
    if not isinstance(data, list):
        raise BadSettingValue(f"{key} 的值不是 JSON 陣列")
    return data


def _finite_number(value):
    """回 float；不是有限的數就回 None。`True`／`False` 在 Python 裡是 int，這裡不當數字。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) else None


def _object_rows(text: str, key: str, value_field: str, coerce) -> list:
    """共用：JSON 陣列 → `[{"bucket": 字串, <value_field>: 值或 None}, ...]`。

    元素必須是**恰好**只有這兩個欄位的物件；多一個少一個都當形狀不符，不猜、不補。
    `bucket` 不做去空白 —— 去了就等於悄悄改掉使用者寫在試算表上的類別名。
    """
    out = []
    for index, item in enumerate(_json_array(text, key), start=1):
        if not isinstance(item, dict) or set(item) != {"bucket", value_field}:
            raise BadSettingValue(f"{key} 第 {index} 個元素不是只含 bucket 與 {value_field} 的物件")
        bucket = item["bucket"]
        if not isinstance(bucket, str) or not bucket.strip():
            raise BadSettingValue(f"{key} 第 {index} 個元素的 bucket 不是非空字串")
        out.append({"bucket": bucket, value_field: coerce(item[value_field], key, index)})
    return out


def _weight_ratio(value, key: str, index: int):
    """`44` 4.5 逐字「小數，區間 0 到 1」。留空（null）是合法的（`44` ALO-1 空狀態）。"""
    if value is None:
        return None
    number = _finite_number(value)
    if number is None:
        raise BadSettingValue(f"{key} 第 {index} 個元素的 weight_ratio 不是有限的數")
    if not 0.0 <= number <= 1.0:
        # `CLAUDE.md` §4.1 百分比 vs 小數：寫成 60 而不是 0.6 就是 100 倍誤差，寧可炸掉。
        raise BadSettingValue(f"{key} 第 {index} 個元素的 weight_ratio 不在 0 到 1（{number}）")
    return number


def _amount_twd(value, key: str, index: int):
    """金額是整數新臺幣；留空（null）是合法的。浮點只收剛好是整數的那一種（同一個數，不是換算）。"""
    if value is None:
        return None
    if isinstance(value, bool):
        raise BadSettingValue(f"{key} 第 {index} 個元素的 amount_twd 不是整數")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    raise BadSettingValue(f"{key} 第 {index} 個元素的 amount_twd 不是整數")


def _parse_target_weights(text: str, key: str) -> list:
    return _object_rows(text, key, "weight_ratio", _weight_ratio)


def _parse_scenario_input(text: str, key: str) -> list:
    return _object_rows(text, key, "amount_twd", _amount_twd)


def _parse_bucket_names(text: str, key: str) -> list:
    names = _json_array(text, key)
    for index, name in enumerate(names, start=1):
        if not isinstance(name, str) or not name.strip():
            raise BadSettingValue(f"{key} 第 {index} 個元素不是非空字串")
    return list(names)


def _parse_tolerance_pp(text: str, key: str) -> float:
    if not isinstance(text, str) or text != text.strip():
        raise BadSettingValue(f"{key} 的值不是前後無空白的字串")
    try:
        number = float(text)
    except ValueError:
        raise BadSettingValue(f"{key} 的值不是數（{key}）") from None
    if not math.isfinite(number):
        raise BadSettingValue(f"{key} 的值不是有限的數")
    return number


def _parse_basis(text: str, key: str) -> str:
    # 可選值的真相源在 L2（`settings_store.ENUM_SETTING_VALUES["alo_basis"]`）；
    # `logic.BASIS_COST`／`BASIS_MV` 是同一份的鏡像，由
    # tests/test_v2_tables_settings_store_page.py::test_跨頁守衛_alo比重基準存值須與L2可選值一致 無條件比對。
    if text not in (logic.BASIS_COST, logic.BASIS_MV):
        raise BadSettingValue(f"{key} 的值不是 {logic.BASIS_COST} 或 {logic.BASIS_MV}")
    return text


_PARSERS = {
    "alo_target_weights": _parse_target_weights,
    "alo_tolerance_pp": _parse_tolerance_pp,
    "alo_basis": _parse_basis,
    "alo_bucket_names": _parse_bucket_names,
    "alo_scenario_input": _parse_scenario_input,
}


def parse_user_settings(rows, broken_keys=()) -> tuple:
    """L2 `load_user_settings()` 的 `rows`／`broken_keys` → (本頁五列, 失敗訊息或 None)。

    `rows` 的 `setting_value` 是試算表上的**原字串**；本頁的 `logic` 吃的是原生值（list／float／字串），
    所以中間一定要有這一層。解析不了 → 回訊息，**不把它當成「尚未設定」**
    （L1 `load_user_settings` 的 docstring 逐字：`broken_keys` 的鍵「畫面應顯示錯誤狀態，不是 ⬜ 未設定」）。

    **線上格式（本層自訂；`44` 只訂 `value_kind`，沒有訂 JSON 形狀）**：
    - `alo_target_weights`：JSON 陣列，每個元素 `{"bucket": 字串, "weight_ratio": 0~1 的數或 null}`
    - `alo_scenario_input`：JSON 陣列，每個元素 `{"bucket": 字串, "amount_twd": 整數或 null}`
    - `alo_bucket_names`：JSON 陣列，元素是非空字串
    - `alo_tolerance_pp`：一個數的字面值（`value_kind` ＝ `float`）
    - `alo_basis`：`成本` 或 `市值`（`value_kind` ＝ `list` 枚舉，值域在 L2）
    """
    rows = dict(rows or {})
    problems = [f"{key} 這一列解析不了" for key in SETTING_KEYS if key in set(broken_keys or ())]
    out = []
    for key in SETTING_KEYS:
        source = rows.get(key) or {}
        raw = source.get("setting_value")
        value = None
        if raw is not None and key not in set(broken_keys or ()):
            try:
                value = _PARSERS[key](raw, key)
            except BadSettingValue as exc:
                problems.append(str(exc))
        out.append({
            "setting_key": key,
            "setting_value": value,
            "value_kind": source.get("value_kind"),
            "updated_at": source.get("updated_at"),
        })
    if problems:
        return out, "設定值讀不到可用的形狀：" + "；".join(problems)
    return out, None


def tables_failed_together(message: str) -> dict:
    """`holding` 與 `policy` 同時標失敗。

    ⚠️ 示範模式與正式模式在這裡對不起來，據實寫明：`ui_v2/alo/fixtures.py` 把 `holding`／`policy`
    當成**兩個可以各自失敗**的鍵（`holdfail`／`policyfail` 兩種情境），但正式模式這兩張表是
    `services/v2_tables/alo_holdings.py::load_alo_tables` **同一次呼叫**的產物 —— 它拋
    `PolicySupplementError` 時，兩張表一起沒有，分不出是誰壞的。所以正式模式一律兩個鍵一起標，
    不假裝其中一張還活著。
    """
    return {"holding": message, "policy": message}


def _walk_buttons(node):
    if isinstance(node, dict):
        if "_action_kind" in node:
            yield node
        for value in node.values():
            yield from _walk_buttons(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_buttons(value)


def _strip_hint(node):
    """把 `logic.HINT_NOTE` 從模型裡任何一串字串清單裡拿掉（`49` §3.4 第 6 項：正式入口不帶示意字樣）。

    刻意不逐個欄位列名：列名就等於要維護一份「示意行住在哪幾個欄位」的清單，
    漏一個就會有一行示意字樣留在正式畫面上。這裡走整棵模型，只認那一個字串。
    """
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = _strip_hint(value)
        return node
    if isinstance(node, list):
        return [_strip_hint(v) for v in node if v != logic.HINT_NOTE]
    if isinstance(node, tuple):
        return tuple(_strip_hint(v) for v in node if v != logic.HINT_NOTE)
    return node


def apply_live_notes(model: dict, *, wired_keys=SAVE_WIRED_KEYS) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。正式模式的三件事：

    1. 頁首的示意行不印（`hint_note` 清空；`page.py` 正式模式那一支也不印它）；
    2. 每一塊的示意行拿掉（`logic.HINT_NOTE`）；
    3. 會寫 `user_setting`、但要寫的鍵還沒接上的按鈕停用並寫出原因（見 `SAVE_DISABLED_REASON`）。

    wired_keys：已接上寫入的鍵。預設 `SAVE_WIRED_KEYS`；呼叫端沒有寫入函式可用時（`page.render`
    沒拿到 `save_live`）要傳空的 —— 那時每一枚存檔都按了不會存，一律照舊停用。

    **本輪不動任何既有文案**：這裡只做「拿掉」與「停用」，沒有新增任何一句話上畫面
    （停用原因顯示在按鈕的 tooltip）。
    """
    wired = frozenset(wired_keys)
    out = _strip_hint(copy.deepcopy(model))
    out["hint_note"] = ""
    for button in _walk_buttons(out["blocks"]):
        if not button["_writes"]:      # `logic._BUTTON_WRITES`：只有「存檔」會寫 user_setting
            continue
        keys = set(button["_keys"])
        if keys and keys <= wired:
            continue                   # 要寫的鍵全部接上了 ⇒ 照 logic 原樣（可按）
        button["_enabled"] = False
        button["disabled_reason"] = SAVE_DISABLED_REASON
    return out


# ───────────────────────── 存檔（ALO-1／ALO-4）─────────────────────────
#
# 流程：畫面輸入欄的當下字串 → `save_entries` 組出每一鍵要寫的試算表字串
# → **先丟回 `_PARSERS` 解析一次**（解析不過不寫，訊息用解析器原文）→ `run_saves` 逐鍵呼叫寫入函式
# → 每鍵的成敗交給 `merge_save_results` 記帳 → 下一輪 `dataset_with_save_errors` 併進 `save_errors`。
# ⛔ 一律不改寫使用者打的字：不 strip、不補 0、不把非數字當 null（`CLAUDE.md` §1）。
#    寫進去的就是畫面上的原字；形狀不對就由解析器擋下來，訊息照原文上畫面。

# JSON 數字的文法（RFC 8259）。比重欄的字串**整段**符合才原樣嵌進 JSON 當數字；
# 其餘（含前後空白、`.6`、`nan`、`六成`）一律當 JSON 字串嵌入，交給解析器以「不是有限的數」擋下。
_JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


def _row_count(values, name_of) -> int:
    count = 0
    while name_of(count) in values:
        count += 1
    return count


def _target_weights_text(values):
    """目標列 → `[{"bucket": 字串, "weight_ratio": 數或 null}, ...]`，順序同畫面列序；一列也沒有 → None。"""
    count = _row_count(values, lambda i: f"alo_target_{i}_bucket")
    if count == 0:
        return None
    items = []
    for index in range(count):
        bucket = values[f"alo_target_{index}_bucket"]
        weight = values[f"alo_target_{index}_weight"]
        if weight == "":
            token = "null"                                  # `44` ALO-1：比重可以留空
        elif isinstance(weight, str) and _JSON_NUMBER.fullmatch(weight):
            token = weight                                  # 原字照嵌，不經 float 轉一手
        else:
            token = json.dumps(weight, ensure_ascii=False)  # 不是數字 ⇒ 當字串嵌，讓解析器擋
        items.append('{"bucket": ' + json.dumps(bucket, ensure_ascii=False)
                     + ', "weight_ratio": ' + token + "}")
    return "[" + ", ".join(items) + "]"


def _bucket_names_text(values):
    count = _row_count(values, lambda i: f"alo_bucket_name_{i}")
    if count == 0:
        return None
    return json.dumps([values[f"alo_bucket_name_{i}"] for i in range(count)], ensure_ascii=False)


def _blank_is_none(value):
    return None if value is None or value == "" else value


_COMPOSERS = {
    "alo_target_weights": _target_weights_text,
    "alo_tolerance_pp": lambda values: _blank_is_none(values["alo_tolerance_pp"]),
    "alo_basis": lambda values: values["alo_basis"],          # radio 未選 → None
    "alo_bucket_names": _bucket_names_text,
}


def save_entries(keys, values, *, settings_failed=False) -> list:
    """一枚存檔要寫的鍵 → `[{"key", "value"（試算表字串或 None）, "value_kind", "error"}, ...]`。

    values：`{輸入欄 name（如 alo_target_0_bucket、alo_basis）: 畫面上的當下值}`。
    `error` 非 None ⇒ 解析不過，**不寫**，訊息是 `BadSettingValue` 原文。
    settings_failed：`user_setting` 讀失敗時畫面上沒有已存值可編（`logic` 那時不畫輸入欄），
    此時一律不寫（回空清單）—— 寫了就是拿空白去蓋掉讀不到的真值（`CLAUDE.md` §1）。
    """
    if settings_failed:
        return []
    out = []
    for key in keys:
        if key not in SAVE_WIRED_KEYS:
            raise ValueError(f"{key} 的寫入尚未接上")
        text = _COMPOSERS[key](values)
        error = None
        if text is not None:
            try:
                _PARSERS[key](text, key)
            except BadSettingValue as exc:
                error = str(exc)
        out.append({"key": key, "value": text, "value_kind": VALUE_KINDS[key], "error": error})
    return out


def run_saves(entries, save) -> dict:
    """逐鍵寫入。回 `{鍵: None（已存）或失敗訊息原文}`。

    save：`source.save_setting(鍵, 值或 None, value_kind)`，回 L2 `save_setting_for_page` 的 dict。
    一鍵失敗不擋另一鍵（客戶 2026-10-09 裁示：已成功的鍵保留，不 rollback）。
    寫入以外的例外照樣往上拋，不吞。
    """
    results = {}
    for entry in entries:
        if entry["error"] is not None:
            results[entry["key"]] = entry["error"]
            continue
        out = save(entry["key"], entry["value"], entry["value_kind"])
        if out["status"] == "saved":
            results[entry["key"]] = None
        else:
            # 訊息已由 L2 遮蔽；萬一是空字串，退回 L2 的狀態碼原文，不讓失敗變成「看起來成功」。
            results[entry["key"]] = out.get("message") or out["status"]
    return results


def merge_save_results(previous, results) -> dict:
    """把這一次的逐鍵結果併進累積的失敗字典（不改呼叫端那一份）：成功的鍵移除、失敗的鍵寫入訊息。"""
    out = dict(previous or {})
    for key, message in results.items():
        if message is None:
            out.pop(key, None)
        else:
            out[key] = message
    return out


def dataset_with_save_errors(dataset, errors) -> dict:
    """把累積的存檔失敗併進 `dataset["save_errors"]`（淺複本，不改呼叫端那一份）。"""
    out = dict(dataset)
    out["save_errors"] = {**(dataset.get("save_errors") or {}), **dict(errors or {})}
    return out
