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
from datetime import date

from .. import thresholds
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


# ═══════════════════════ 淨值與非美元匯率（2026-10-13 客戶裁示：B 線資產配置必須是真資料）═══════════════════════
#
# 淨值走 L2 `services/v2_tables/nav_dividend.py::build_nav_table`（A 鏈，#946），組輸入與判讀淨值表的規則
# **一律照 `ui_v2/hld/source.py` ＋ `ui_v2/hld/live.py::assemble_live_load`**（幣別、拒收、閘門都在 L2，本頁不另寫一套）：
# - 被扣下（`nav_unavailable_withheld` 四碼）、代碼對照查不到（`ok is False`）、來源回空且沒有原因
#   → 那一檔沒有淨值列 ⇒ `logic.basis_value` 照既有路徑寫「⬜ 資料未備：nav 尚無資料」，不新增字句。
#   （總管 2026-10-13 裁決：只有淨值日超過門檻那一種〔`too_old`〕改寫 ~~「⬜ 資料未備：最近淨值已超過 N 日」~~
#    → 客戶 2026-10-14 裁示「舊淨值要標示實際資料日期」（狀態更新，不是漏刪）：正式模式改寫
#    「⬜ 資料未備：最近一筆淨值 {日期}，已超過 N 日」（`logic.NAV_NOT_READY_DATED_TEXT`；類別層逐檔列「日期（代碼）」），
#    日期取 `assemble_nav` 的 `too_old_last`，由 `source.py` 經 dataset 的 `nav_not_ready`〔`codes`／`days`／`last`〕
#    交給 `logic`；上面這三種照舊。）
# - 其餘取數失敗 → 原文經 `mask` 遮過，逐檔以「代碼：原文」串成一句放進 `errors["nav"]`
#   （體例同 hld 的 `skipped_tabs`）。本頁沒有逐檔失敗的畫法（hld 有 `fund_errors`，本頁沒有），
#   所以照 ALO-GAP-取數失敗走表層失敗：市值基準下 ALO-2／ALO-4／ALO-6 畫 ⛔，成本基準不受影響。
# - 扣下代碼不在清單內（例 `input_conflict`）→ raise（契約被破壞，不畫成 ⬜；同 hld R-10）。
# - 2026-10-13 稽核 N1（總管技術裁定，fail closed）：過期或預存淨值 —— provenance 帶 `cache_fallback` 或 `stale`、
#   ~~或淨值列 `is_estimated` 為真~~ → 或淨值列 `is_estimated` 不是 False（含缺欄或 None；第二輪文字對齊，與程式一致）、
#   或（第二輪 N-b）該檔最新淨值日距 `today` 超過 `max_age_days` 個日曆日 —— 一律不交進 dataset，
#   該檔在市值基準下視為缺淨值（logic.GAPS「ALO-GAP-過期淨值不納入」）。
#   本頁沒有新鮮度位置，交進去就是把舊值靜默當成現值（CLAUDE.md §2.4「禁止靜默返回」）。
#   淨值日一律取資料列本身的 `nav_date`，不用 `fetched_at`（即時取回的也可能是好幾個月前的淨值）。
# - 2026-10-13 稽核 N2：`notes["nav"]["provenance"]` 裡的 `live_error` 是 L1 原文，經 `mask` 才放進 notes。
#   第二輪 N-c：`chain_failures` 與 `nav_history.read_error` 同樣是 L1 原文，一併經 `mask`（深拷貝，不改輸入）。

# 市值基準的淨值日上限（日曆日；N ＝ 台灣今天的日期減該檔最後一筆 `nav_date`，N **大於**這個數 → 不納入）。
# ~~第二輪：引用 `shared/signal_thresholds.py::MJ_FRESH_DAYS_YELLOW`（7），經 `services/v2_tables/contract.py`
# 的 `NAV_MAX_AGE_DAYS` 轉交~~ → **2026-10-13 第三輪總管裁定（有意識的更正，不是漏刪；決策者：AI 總管，
# 錯在上一輪派工單沒查到 B 線已有客戶裁示）**：改用 B 線既有、客戶裁示過的門檻 10 天 ——
# 出處 `ui_v2/hld/live.py::NAV_FRESH_DAYS_YELLOW`，客戶 2026-10-02 裁示（草稿 `docs/wireframes/draft_hld_live.html`
# §G 第 1a 題），客戶要求註明的原話：
#   「門檻 10 天，非 44 規定，是本輪依長假實況訂的」
# 客戶理由：7 天遇到春節等長假會把所有基金誤標；草稿 §D 明寫「不要沿用 MJ_FRESH_DAYS_YELLOW」。
# 稽核組 7 實跑：7 天在 2026 春節期間會連續 3～4 天把國內基金整片排除。舊值 7 的用意（§2.4 不得靜默返回舊值）仍然成立，
# 被權衡掉的是它的數字 —— 它不是 B 線對淨值新鮮度的現行裁示。
# 判定方向與 hld 黃燈一致：hld 是 `days > NAV_FRESH_DAYS_YELLOW` 才黃，本頁是 `> NAV_MAX_AGE_DAYS` 才排除。
# ~~兩頁不互相 import（各自是頁面模組），由 tests/ui_v2/test_alo_live_logic.py 鎖住兩者相等，防止脫鉤。~~
# ~~`NAV_MAX_AGE_DAYS = 10`（本檔寫死）~~ → 2026-10-13 客戶裁示（有意識的更正，不是漏刪）：10 天要有單一、
# 明確的共用定義 —— 兩個寫死的 10 只靠測試鎖相等，仍是兩個數字。兩頁照舊不互相 import，
# 改為同引 `ui_v2/thresholds.py::NAV_NOT_READY_DAYS`；本名保留為別名，判定方向 `> NAV_MAX_AGE_DAYS` 不變。
NAV_MAX_AGE_DAYS = thresholds.NAV_NOT_READY_DAYS


def wants_market_value(setting_rows) -> bool:
    """已存的比重基準是不是「市值」。只有這時本頁才去取淨值與匯率（成本基準用不到，取回來只會多打來源；
    v3 §02）。設定讀不到或解析不了 → `setting_rows` 為空 → 假：各塊本來就畫設定失敗框。"""
    for row in setting_rows or ():
        if row.get("setting_key") == "alo_basis":
            return row.get("setting_value") == logic.BASIS_MV
    return False


def assemble_nav(*, holding_codes, key_results, nav_table, empty_without_reason,
                 nav_unavailable_withheld, mask, today, max_age_days) -> dict:
    """L2 淨值表 → `{"nav": 列, "error": 已遮蔽的失敗原文或 None, "notes": {...}}`（純函式，不改輸入、不讀時鐘）。

    一致性檢查同 hld `assemble_live_load` 的 R-10、R-13～R-16，不過就 raise（呼叫端組錯，不是資料問題）。
    `today`：台灣日曆日（`datetime.date`，呼叫端以 L2 的 `MARKET_DATE_TZ` 算好交進來）；
    `max_age_days`：淨值日距今的上限天數（呼叫端傳本檔的 `NAV_MAX_AGE_DAYS`；~~SSOT `contract.NAV_MAX_AGE_DAYS`~~ 第三輪改）。
    """
    if not callable(mask):
        raise TypeError(f"mask 應為可呼叫：{type(mask).__name__}")
    if type(today) is not date:
        raise TypeError(f"today 應為 datetime.date：{type(today).__name__}")
    if type(max_age_days) is not int or max_age_days < 0:
        raise TypeError(f"max_age_days 應為非負整數：{max_age_days!r}")
    codes_held = list(dict.fromkeys(holding_codes))
    nav_codes = {r["fund_code"] for r in nav_table["rows"]}
    for name in ("errors", "withheld", "skipped", "fetched", "skipped_rows", "provenance"):
        nav_codes |= set(nav_table[name])
    if nav_codes - set(codes_held):
        raise ValueError(f"淨值表出現持倉裡沒有的代碼：{sorted(nav_codes - set(codes_held))!r}")
    for r in key_results:
        if type(r["ok"]) is not bool:
            raise TypeError(f"代碼對照的 ok 應為 bool：{r['input']!r}")
    inputs = {r["input"] for r in key_results}
    if inputs != set(codes_held):
        raise ValueError(f"代碼對照的輸入與持倉代碼不一致：多 {sorted(inputs - set(codes_held))!r}、"
                         f"少 {sorted(set(codes_held) - inputs)!r}")
    key_failed = {r["input"] for r in key_results if r["ok"] is False}
    if key_failed & nav_codes:
        raise ValueError(f"代碼對照失敗的代碼不得出現在淨值表：{sorted(key_failed & nav_codes)!r}")
    not_handed = {r["input"] for r in key_results if r["ok"] is True
                  and r["input"] not in nav_table["fetched"] and r["input"] not in nav_table["withheld"]}
    if not_handed:
        raise ValueError(f"代碼對照成功、卻沒有交給淨值表的代碼：{sorted(not_handed)!r}")
    for code, reason in nav_table["withheld"].items():
        if reason not in nav_unavailable_withheld:
            raise ValueError(f"淨值扣下原因 {reason!r} 不在本頁約定的清單內：{code!r}")

    parts = []
    for code in codes_held:
        message = nav_table["errors"].get(code)
        if message is None:
            continue
        if message == empty_without_reason and nav_table["fetched"].get(code, 0) == 0:
            continue   # 來源回空、沒有原因 → 資料未備，不是失敗（同 hld）
        parts.append(f"{code}：{mask(message)}")

    not_fresh = set()
    for code, prov in nav_table["provenance"].items():
        if prov and (prov.get("cache_fallback") or prov.get("stale")):
            not_fresh.add(code)
    not_fresh |= {r["fund_code"] for r in nav_table["rows"] if r.get("is_estimated") is not False}
    newest = {}
    for r in nav_table["rows"]:
        day = date.fromisoformat(r["nav_date"])   # 契約保證 YYYY-MM-DD；不是就是契約被破壞，照拋
        if r["fund_code"] not in newest or day > newest[r["fund_code"]]:
            newest[r["fund_code"]] = day
    too_old = {code for code, day in newest.items() if (today - day).days > max_age_days}
    not_fresh |= too_old
    provenance = {}
    for code, prov in nav_table["provenance"].items():
        prov = copy.deepcopy(dict(prov or {}))
        for name in ("live_error", "chain_failures"):
            if prov.get(name) is not None:
                prov[name] = mask(str(prov[name]))
        hist = prov.get("nav_history")
        if isinstance(hist, dict) and hist.get("read_error") is not None:
            hist["read_error"] = mask(str(hist["read_error"]))
        provenance[code] = prov
    return {
        "nav": [dict(r) for r in nav_table["rows"] if r["fund_code"] not in not_fresh],
        "error": "；".join(parts) if parts else None,
        "notes": {
            "withheld": dict(nav_table["withheld"]),
            "key_failed": sorted(key_failed),
            "not_fresh": sorted(not_fresh),     # 過期或預存淨值，市值基準下不納入（ALO-GAP-過期淨值不納入）
            "too_old": sorted(too_old),         # 其中因淨值日超過門檻而不納入的（N-b）
            # 客戶 2026-10-14 裁示「舊淨值要標示實際資料日期」：過期各檔的最後一筆 `nav_date`（ISO，取自資料列本身，
            # 不是 `fetched_at`），經 `source.py` 的 `nav_not_ready["last"]` 交給 `logic` 寫進「資料未備」那一句。
            "too_old_last": {code: newest[code].isoformat() for code in sorted(too_old)},
            "provenance": provenance,
        },
    }


def fx_ccys_needed(nav_rows) -> list:
    """淨值列裡新臺幣與美元以外的幣別（依出現順序、不重複）。美元走設定試算表那一份（市場總覽頁落地），
    其餘依 49 §6.1 Q9 由本頁經 L2 取。"""
    return list(dict.fromkeys(r["ccy"] for r in nav_rows if r["ccy"] not in ("TWD", "USD")))


def merge_fx_table(indicator_rows, indicator_error, fx_table, mask) -> tuple:
    """設定試算表上的 `market_indicator` 列 ＋ L2 `build_fx_indicator_table` 的非美元匯率列。

    回 `(列, 已遮蔽的失敗原文或 None, pending)`。
    - 試算表讀失敗（`indicator_error` 已遮蔽）→ 照舊放前面；非美元那幾鍵的取數失敗以「鍵：原文」接在後面
      （ALO-GAP-缺匯率從嚴：market_indicator 有任何取數失敗，市值基準下整張 ALO-2 進系統錯誤）。
    - `pending`（閘門未開）不是失敗：不進錯誤、那幾鍵沒有列 ⇒ 該類別「⬜ 資料未備：缺換算匯率 <鍵>」。
    """
    rows = [dict(r) for r in indicator_rows] + [dict(r) for r in fx_table["rows"]]
    parts = [indicator_error] if indicator_error else []
    parts.extend(f"{key}：{mask(message)}" for key, message in fx_table["errors"].items())
    return rows, ("；".join(parts) if parts else None), dict(fx_table["pending"])


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


def apply_live_notes(model: dict, *, wired_keys=()) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。正式模式的三件事：

    1. 頁首的示意行不印（`hint_note` 清空；`page.py` 正式模式那一支也不印它）；
    2. 每一塊的示意行拿掉（`logic.HINT_NOTE`）；
    3. 會寫 `user_setting`、但要寫的鍵還沒接上的按鈕停用並寫出原因（見 `SAVE_DISABLED_REASON`）。

    wired_keys：已接上寫入的鍵。**預設空（fail-closed）**：沒明講就當沒接上，三枚存檔一律停用。
    `page.render` 拿到 `save_live` 時才明確傳 `SAVE_WIRED_KEYS`。

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
# ⛔ 2026-10-09 稽核回修：**使用者沒動過的欄位，寫回已存的原值，不寫顯示字串。**
#    輸入欄的初值是 `logic._field` 經 `format_number` 格式化過的顯示字串（最多四位小數），
#    把它寫回去會把 0.333333 存成 0.3333、0.00001 存成 0 —— 使用者一個字都沒改，真值卻被覆蓋
#    （`44` ALO-1「不代使用者填任何值」、判準「與存檔前逐字相同」）。判斷「沒動過」：當下字串 ＝ 該欄的 `value_text`。
#    比重寫回已存 float 的 JSON 表示；容許帶寫回試算表上的原字串（`source` 經 `notes["setting_raw"]` 交出）。

# JSON 數字的文法（RFC 8259）。比重欄的字串**整段**符合才原樣嵌進 JSON 當數字；
# 其餘（含前後空白、`.6`、`nan`、`六成`）一律當 JSON 字串嵌入，交給解析器以「不是有限的數」擋下。
_JSON_NUMBER = re.compile(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?")


def _row_count(values, name_of) -> int:
    count = 0
    while name_of(count) in values:
        count += 1
    return count


def _unchanged(name, values, fields) -> bool:
    """這一欄的當下字串等於它畫上去時的 `value_text` ⇒ 使用者沒動過。畫面上沒有這一欄 ⇒ 不算沒動過。"""
    field = fields.get(name)
    return field is not None and values[name] == field["value_text"]


def _target_weights_text(values, fields, raw):
    """目標列 → `[{"bucket": 字串, "weight_ratio": 數或 null}, ...]`，順序同畫面列序；一列也沒有 → None。"""
    count = _row_count(values, lambda i: f"alo_target_{i}_bucket")
    if count == 0:
        return None
    items = []
    for index in range(count):
        bucket = values[f"alo_target_{index}_bucket"]
        weight = values[f"alo_target_{index}_weight"]
        weight_name = f"alo_target_{index}_weight"
        if _unchanged(weight_name, values, fields):
            stored = fields[weight_name]["_value"]
            # 沒動過 ⇒ 寫回已存值（已存 float 的 JSON 表示），不寫四捨五入過的顯示字串。
            token = "null" if stored is None else json.dumps(stored)
        elif weight == "":
            token = "null"                                  # `44` ALO-1：比重可以留空
        elif isinstance(weight, str) and _JSON_NUMBER.fullmatch(weight):
            token = weight                                  # 原字照嵌，不經 float 轉一手
        else:
            token = json.dumps(weight, ensure_ascii=False)  # 不是數字 ⇒ 當字串嵌，讓解析器擋
        items.append('{"bucket": ' + json.dumps(bucket, ensure_ascii=False)
                     + ', "weight_ratio": ' + token + "}")
    return "[" + ", ".join(items) + "]"


def _bucket_names_text(values, fields, raw):
    count = _row_count(values, lambda i: f"alo_bucket_name_{i}")
    if count == 0:
        return None
    return json.dumps([values[f"alo_bucket_name_{i}"] for i in range(count)], ensure_ascii=False)


def _blank_is_none(value):
    return None if value is None or value == "" else value


def _tolerance_text(values, fields, raw):
    if _unchanged("alo_tolerance_pp", values, fields):
        # 沒動過 ⇒ 寫回試算表上的原字串（`raw` 裡沒有這個鍵就是呼叫端漏傳，當場 KeyError，不猜）。
        return raw["alo_tolerance_pp"]
    return _blank_is_none(values["alo_tolerance_pp"])


# 類別與類別名稱是字串、基準是 radio 的原值：畫上去就是原字，沒有格式化，不必另走「沒動過」那一支。
_COMPOSERS = {
    "alo_target_weights": _target_weights_text,
    "alo_tolerance_pp": _tolerance_text,
    "alo_basis": lambda values, fields, raw: values["alo_basis"],          # radio 未選 → None
    "alo_bucket_names": _bucket_names_text,
}


def save_entries(keys, values, *, fields=(), raw=None, settings_error=None) -> list:
    """一枚存檔要寫的鍵 → `[{"key", "value"（試算表字串或 None）, "value_kind", "error"}, ...]`。

    values：`{輸入欄 name（如 alo_target_0_bucket、alo_basis）: 畫面上的當下值}`。
    fields：該塊畫上去的輸入欄節點（`logic._field`；帶 `_value` 已存值與 `value_text` 顯示字串）。
    raw：`{鍵: 試算表上的原字串或 None}`（`source.load_live` 的 `notes["setting_raw"]`）。
    `error` 非 None ⇒ **不寫**：解析不過時是 `BadSettingValue` 原文。
    `skip` 為真 ⇒ **不寫、也不算失敗**：要寫的是清除（None），而 `raw` 明載該鍵本來就沒有值 ——
    使用者沒填、試算表上也沒有，寫下去只會多一列空值（2026-10-15 Phase 2 批 2 重現後修正）。
    `raw` 沒帶那個鍵 ⇒ 不知道有沒有值 ⇒ 不跳過（照舊寫清除，不猜）。
    settings_error：`user_setting` 讀失敗的訊息原文（`logic.settings_failure`）。讀失敗時畫面上沒有已存值可編，
    寫了就是拿空白去蓋掉讀不到的真值 ⇒ 每一鍵都不寫、`error` 填這個原文，交 `run_saves` 記成存檔失敗
    （卡片層既有的「存檔寫入失敗：…」）—— 不讓「按了沒反應」看起來像成功（`CLAUDE.md` §1）。
    """
    for key in keys:
        if key not in SAVE_WIRED_KEYS:
            raise ValueError(f"{key} 的寫入尚未接上")
    if settings_error is not None:
        return [{"key": key, "value": None, "value_kind": VALUE_KINDS[key], "error": settings_error,
                 "skip": False} for key in keys]
    by_name = {field["name"]: field for field in fields}
    raw = raw if raw is not None else {}
    out = []
    for key in keys:
        text = _COMPOSERS[key](values, by_name, raw)
        error = None
        if text is not None:
            try:
                _PARSERS[key](text, key)
            except BadSettingValue as exc:
                error = str(exc)
        skip = text is None and key in raw and raw[key] is None
        out.append({"key": key, "value": text, "value_kind": VALUE_KINDS[key], "error": error,
                    "skip": skip})
    return out


def run_saves(entries, save) -> dict:
    """逐鍵寫入。回 `{鍵: None（已存）或失敗訊息原文}`。

    save：`source.save_setting(鍵, 值或 None, value_kind)`，回 L2 `save_setting_for_page` 的 dict。
    一鍵失敗不擋另一鍵（客戶 2026-10-09 裁示：已成功的鍵保留，不 rollback）。
    `skip` 為真的鍵不呼叫寫入、記為 None（沒有東西要寫；之前留下的失敗訊息一併消掉，因為畫面上已回到與表上一致）。
    寫入以外的例外照樣往上拋，不吞。
    """
    results = {}
    for entry in entries:
        if entry.get("skip"):
            results[entry["key"]] = None
            continue
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
