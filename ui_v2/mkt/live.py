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
8. Phase 3 P0-③（44 第七節第三小節之七其二第 5、7 條）：4b 的「套用」與 5 的「重新取數」在模型裡照舊停用＋原因，
   但**一般畫面不畫**（`hidden_in_live`；`MKT-0` 三塊皆空改畫「前往設定與診斷」，`light_needs_settings_link`）；
   `MKT-5` 改一份多選清單（`PICK_LABEL`、`initial_picks`）。BL-0228：從未存過＋一個都沒選不寫 `"[]"`（`mkt5_save_entry`）。

⚠️ 文案逐字照草稿；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
⚠️ 例外（據實寫明）：BL-0228 的停用原因 `logic.TEXT_SAVE_NOTHING_PICKED` 不是草稿字面 —— 本組擬定，44／59 未列。
"""

from __future__ import annotations

import copy
import json
import math
from datetime import date, datetime, timedelta, timezone

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
# 由 tests/ui_v2/test_mkt_settings_logic.py::test_L2型別檢查擋得下_value_kind與set頁一致 逐字比對（2026-10-13 更正：原寫的 test_mkt_settings.py 不存在）。
KEY_WINDOW = "mkt_window_days"
KEY_BASELINE = "mkt_baseline_date"
KEY_INDICATORS = "mkt_indicator_keys"
# B2（2026-10-13 稽核 G，總管裁定）：一致性憑證鍵。MKT-4 存檔時在兩鍵寫完之後**再寫**這一鍵，
# 值是兩個已寫入值的確定性組合 —— JSON 陣列 `[天數, "YYYY-MM-DD"]`（`value_kind` 為 `list`，
# `44` 4.5 的六種之一；總管舉的 `"5|2026-09-21"` 不合任何一種 `value_kind`，故改用 JSON 陣列，語意相同）。
# 讀回時只有三者一致才算完整設定；不一致（存檔中途失敗、設定頁單獨改了其中一鍵、或舊資料沒有憑證）
# → 三張核心卡「⬜ 設定不完整：比較條件不一致，請重新存檔」，不出任何比較數字。
KEY_PAIR = "mkt_compare_pair"
SETTING_KEYS = (KEY_WINDOW, KEY_BASELINE, KEY_INDICATORS)
VALUE_KINDS = {KEY_WINDOW: "int", KEY_BASELINE: "date", KEY_INDICATORS: "list", KEY_PAIR: "list"}


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
    if value > logic.WINDOW_DAYS_MAX:
        # B1：超出範圍的已存值（例如 1000000）當成讀取失敗，不交給 logic 去算（舊寫法會讓整頁溢位當掉）。
        raise BadSettingValue(f"{KEY_WINDOW} 超出範圍（{logic.TEXT_WINDOW_RANGE}）：{text!r}")
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


def pair_text(window_days: int, baseline_date: str) -> str:
    """一致性憑證的值（確定性：同一組兩鍵永遠得到同一個字串）。"""
    return json.dumps([int(window_days), str(baseline_date)], ensure_ascii=False)


def _pair_consistent(raw, broken, window_days, baseline_date):
    """兩鍵都在時才判（否則回 None，由 Q-07「缺哪一鍵」那條規則處理）。
    憑證缺、壞、或對不上 → False（從嚴；舊資料沒有憑證也算不一致，總管裁定）。"""
    if window_days is None or baseline_date is None:
        return None
    if raw is None or broken:
        return False
    try:
        value = json.loads(raw, parse_constant=_reject_constant)
    except (ValueError, RecursionError, BadSettingValue):
        return False
    # 型別嚴格（2026-10-13 稽核 G）：Python 的 `5.0 == 5`、`True == 1` 都成立，只比值會讓 `[5.0, …]`、
    # `[true, …]` 這種不是本頁寫出來的憑證蒙混過關（fail-open）。本頁寫的天數恆為 JSON 整數。
    if not (isinstance(value, list) and len(value) == 2 and type(value[0]) is int and type(value[1]) is str):
        return False
    return value == [window_days, baseline_date]


def parse_user_settings(rows, broken_keys=()) -> tuple:
    """L2 `load_user_settings()` 的 `rows`／`broken_keys` → (`{"window_days", "baseline_date",
    "indicator_keys", "pair_consistent"}`, 失敗訊息或 None)。

    `pair_consistent`（B2）：兩鍵都在時，與一致性憑證鍵 `mkt_compare_pair` 比對的結果；否則 None。

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
        empty = {"window_days": None, "baseline_date": None, "indicator_keys": None, "pair_consistent": None}
        return empty, "設定值讀不到可用的形狀：" + "；".join(problems)
    pair_raw = (rows.get(KEY_PAIR) or {}).get("setting_value")
    consistent = _pair_consistent(pair_raw, KEY_PAIR in broken, values[KEY_WINDOW], values[KEY_BASELINE])
    return {"window_days": values[KEY_WINDOW], "baseline_date": values[KEY_BASELINE],
            "indicator_keys": values[KEY_INDICATORS], "pair_consistent": consistent}, None


def mkt4_save_entries(window_days, baseline_date) -> list:
    """MKT-4 存檔要寫的三鍵（兩鍵 ＋ 一致性憑證，依序）→ `[{"key", "value", "value_kind", "error"}, ...]`。

    客戶 2026-10-13 裁示 Q-07：**兩欄都完整才能存**。任一欄缺或不合格 → 每一鍵**都**帶 `error`、
    一鍵也不寫（不得產生半套正式設定）。畫面上的存檔鈕本來就停用，這一層是第二道。
    B1：天數須介於 1 與 `logic.WINDOW_DAYS_MAX`。B2：憑證排最後 —— 前面任一鍵失敗，憑證就不會寫，
    讀回時兩鍵與憑證對不上 ⇒ 判不一致。
    """
    problem = None
    if window_days is None:
        problem = logic.TEXT_SAVE_MISSING_WINDOW
    elif not isinstance(window_days, int) or isinstance(window_days, bool) or window_days <= 0:
        problem = "日數為正整數"
    elif window_days > logic.WINDOW_DAYS_MAX:
        problem = logic.TEXT_WINDOW_RANGE
    elif not baseline_date:
        problem = logic.TEXT_SAVE_MISSING_BASELINE
    else:
        try:
            _parse_baseline(str(baseline_date))
        except BadSettingValue as exc:
            problem = str(exc)
    if problem:
        return [{"key": key, "value": None, "value_kind": VALUE_KINDS[key], "error": problem}
                for key in (KEY_WINDOW, KEY_BASELINE, KEY_PAIR)]
    return [
        {"key": KEY_WINDOW, "value": str(int(window_days)), "value_kind": VALUE_KINDS[KEY_WINDOW], "error": None},
        {"key": KEY_BASELINE, "value": str(baseline_date), "value_kind": VALUE_KINDS[KEY_BASELINE], "error": None},
        {"key": KEY_PAIR, "value": pair_text(window_days, baseline_date), "value_kind": VALUE_KINDS[KEY_PAIR],
         "error": None},
    ]


def mkt5_save_entry(selected, available, *, never_saved: bool = False) -> list:
    """MKT-5 存檔要寫的一鍵。依字面值排序（44 MKT-5：清單以字面值排列）。

    N6（2026-10-13 稽核 G）：含可勾清單以外的鍵、或重複的鍵 → **拒絕並說明**（帶 `error`，不寫）。
    ~~舊寫法把清單以外的鍵靜默濾掉再存~~ —— 使用者以為存了的東西沒存進去，而畫面不說。

    never_saved（BL-0228，Phase 3 P0-③）：「從未存過」＝ `user_setting` 裡**沒有** `mkt_indicator_keys` 這一列，
    或最新一筆的值已被清除（兩者 `parse_user_settings` 都交回 `indicator_keys is None`）；且沒有讀取失敗。
    實際判定就是 `indicator_keys is None and not settings_error`（`page.render` 算好傳進存檔回呼）。這時一個都沒選 → 拒絕（不寫 `"[]"`）。
    ⚠️ 判定照既有資料，不新發明：已存過的 `"[]"` 照舊是「已存、一個都沒選」（44 `MKT-5` 判準「取消全部勾選並存檔、
    重新載入，下方明細出現『尚未選定任何指標』」），所以**已存過**時清空再存照舊允許；只有「從未存過」才擋。
    畫面上的存檔鈕本來就停用（`logic._build_mkt5`），這一層是第二道。
    """
    selected = list(selected)
    allowed = set(available)
    unknown = sorted({k for k in selected if k not in allowed})
    duplicated = sorted({k for k in selected if selected.count(k) > 1})
    error = None
    if never_saved and not selected:
        error = logic.TEXT_SAVE_NOTHING_PICKED
    elif unknown:
        error = "勾選中有資料層未提供的鍵，未存檔：" + "、".join(unknown)
    elif duplicated:
        error = "勾選中有重複的鍵，未存檔：" + "、".join(duplicated)
    elif len(selected) > logic.INDICATOR_PICK_CAP:
        error = "已達勾選上限 6，請先取消一項"
    text = json.dumps(sorted(set(selected)), ensure_ascii=False)
    return [{"key": KEY_INDICATORS, "value": text, "value_kind": VALUE_KINDS[KEY_INDICATORS], "error": error}]


# ───────────────────── Phase 3 P0-③：正式模式一般畫面不畫的兩種按鈕、指標多選清單 ─────────────────────
# 44 第七節第三小節之七其二第 7 條：`MKT-4` 正式模式下永遠停用的「套用」，與每張卡（含 `MKT-0`）正式模式下
# 永遠停用的「重新取數」，一般畫面不畫；`MKT-0` 三塊皆空那一格改畫「前往設定與診斷」導覽鈕。
# ⚠️ 只改「畫不畫」：模型照舊帶著這兩種按鈕（停用＋原因；`apply_live_notes`），頁面模型與資料判定不變。
# ⚠️ 只擋「停用中」的那兩類 —— 日後若接上取數、那一枚變成可用，這裡不會把可用的按鈕藏掉（同條文末句）。
LIVE_HIDDEN_KINDS = ("套用", "取數")
# 44 第七節第三小節之七其二第 5 條：`MKT-5` 改一份多選清單（正式模式；示範模式照舊勾選框，同小節開頭第 4 條）。
PICK_LABEL = "要看的指標"


def hidden_in_live(button: dict) -> bool:
    """正式模式一般畫面不畫這一枚？只有停用中的「套用」與「重新取數」（`取數` 類）回 True。"""
    return button["_action_kind"] in LIVE_HIDDEN_KINDS and not button["_enabled"]


def light_needs_settings_link(block: dict) -> bool:
    """`MKT-0` 三塊皆空（燈上那一枚「重新取數」只在這時出現，`logic.conclusion_light`）且它在正式模式不畫 →
    改畫一枚「前往設定與診斷」（59 線框第 2.3a 節）。"""
    return any(b["_action_kind"] == "取數" and hidden_in_live(b) for b in block["buttons"])


def initial_picks(settings, keys, settings_error=None):
    """正式模式多選清單的初值（已存清單 ∩ 可選清單，依可選清單順序）；None ＝ 不填（從未存過或讀不到）。
    與 `initial_checkbox_values` 同一份判定，只是換成多選清單要的形狀。"""
    initial = initial_checkbox_values(settings, keys, settings_error)
    if initial is None:
        return None
    return [key for key in keys if initial[key]]


def initial_checkbox_values(settings, keys, settings_error=None):
    """正式模式勾選框的初值（`page.py` 只在 session 沒有那一格時才填）。回 `{鍵: bool}`，或 None ＝ 不填。

    - 讀不到設定 → None（勾選框停用、存檔停用；不拿猜的值去填）。
    - 已存過 → 依已存清單（只對可勾清單內的鍵）。
    - ~~N4：從未存過 → **全勾**，與下方明細「全部列出」一致~~ → **2026-10-13 總管裁定（有意識的更正，不是漏刪）：
      從未存過 → 不填（None），勾選框一個都不勾** —— `44` 1.1 節「輸入欄不帶非空預設值」與本塊紅線說明
      「勾選狀態由使用者自行輸入，系統不代填」；下方明細同時改為不全列（`logic.TEXT_UNSAVED_NONE`），
      「全不勾卻全列」的矛盾由明細那一側消失。
    """
    if settings_error:
        return None
    saved = settings.get("indicator_keys")
    if saved is None:
        return None
    return {key: key in saved for key in keys}


def run_saves(entries, save, *, stop_on_failure: bool = True) -> dict:
    """逐鍵寫入。回 `{鍵: None（已存）或失敗訊息原文}`。

    save：`source.save_setting(鍵, 值或 None, value_kind)`，回 L2 `save_setting_for_page` 的 dict。
    任一 entry 帶 `error` → **一鍵都不寫**（全部記成那個訊息）。
    stop_on_failure：前一鍵寫入失敗就不再寫下一鍵（MKT-4：先寫的那一鍵失敗時，不讓後面的鍵單獨落地）。
    ~~⚠️ 後一鍵失敗而前一鍵已寫入時，試算表上會留下半套 …；讀回時 `logic` 判成「設定不完整」~~
    → **2026-10-13 更正（稽核 G 指出；有意識的更正，不是漏刪）：上一句不實。** 兩鍵都是**改寫既有值**，
    後一鍵失敗時試算表上是「新天數 ＋ 舊基準日」這種**兩鍵齊全的混搭**，舊讀法會把它當完整設定照算。
    現行：L1 是逐列追加、沒有交易，這一層仍然擋不住混搭落地；擋在**讀回端** ——
    MKT-4 第三鍵是一致性憑證（`KEY_PAIR`，排最後寫），讀回時兩鍵與憑證對不上 → `logic` 判
    「⬜ 設定不完整：比較條件不一致，請重新存檔」，不出任何比較數字（`parse_user_settings`）。
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
        pair_consistent=settings.get("pair_consistent"),
        require_saved_selection=True,
    )
    model = apply_live_notes(model, notes, save_wired=save_wired)
    model = _mark_unsaved(model, settings, notes.get("settings_error"), field_window_days,
                          field_baseline_date, field_selected_keys)
    model = localize_detail_tables(model)
    return apply_save_results(model, save_results)


# ───────────────────────── MKT-6／MKT-7：時間轉台北時間、原始值換中文（BL-0250 批次 1） ─────────────────────────
# 客戶 2026-10-19 裁示（`docs/DECISIONS.md` `DEC-2026-10-19-04`，BL-0250 實機驗收回修批次 1）：
# - 44 `MKT-7` 規則欄逐字「時間一律以世界協調時間存放，顯示時轉當地時區並在表頭註明時區字面值」——
#   舊畫面印 ISO 的世界協調時間、只在表尾加一句「時間以 UTC 顯示」，沒有轉。改成台北時間（UTC+8），
#   時區字面值寫在表頭（同設定與診斷頁、資產配置頁既有寫法 `<欄名>（UTC+8）`、`YYYY-MM-DD HH:MM`）。
#   `MKT-6` 的「取得時間」欄同一份資料（`fetched_at`），一併轉。
# - 「是否修正」欄印布林原值 `True`／`False` → 「是」／「否」；表頭「指標鍵」→「指標」（列上的指標名本來就由 `plain` 換成中文名）。
# - **不改的**：延遲日數照舊以 `fetched_at` 的日期減 `obs_date`（`logic.delay_days`，44 逐字的算法）；
#   單位欄照舊印 `value_unit` 字面值（44 `MKT-6` 規則欄逐字「單位直接印 `value_unit` 的字面值，不做換算」）；
#   來源層級照舊印 `source_tier`（正式資料的值域是 44 4.5 的四個之一，`T1`／`T2` 只出現在示範資料）。
# - 只在正式模式（本檔）；示範模式不經過本檔，一個字都不變。
DISPLAY_TZ = timezone(timedelta(hours=8))
DISPLAY_TZ_LABEL = "UTC+8"
TEXT_INDICATOR_COLUMN = "指標"
REVISED_TEXT = {True: "是", False: "否"}
_STORAGE_TZ_LINE = f"時間以 {logic.STORAGE_TIMEZONE} 顯示"
_MKT7_KEY_WORD = "指標鍵"


def local_time_text(utc_text):
    """世界協調時間 ISO 字串 → 台北時間 `YYYY-MM-DD HH:MM`。不是時間的字（`⬜`、`◇`、`⛔` 那類空格）原樣交回。
    是時間卻解析不了 → 照拋（資料契約保證 `fetched_at` 帶時區；不猜）。"""
    if not isinstance(utc_text, str) or not utc_text[:1].isdigit():
        return utc_text
    moment = datetime.fromisoformat(utc_text.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError(f"取得時間沒有時區：{utc_text!r}")
    return f"{moment.astimezone(DISPLAY_TZ):%Y-%m-%d %H:%M}"


def _local_labels(labels) -> list:
    out = []
    for label in labels or ():
        if label == logic.MKT6_COLUMN_LABELS["indicator_key"]:
            label = TEXT_INDICATOR_COLUMN
        elif label in (logic.MKT6_COLUMN_LABELS["fetched_at"], "最近取得時間"):
            label = f"{label}（{DISPLAY_TZ_LABEL}）"
        out.append(label)
    return out


def localize_detail_tables(model: dict) -> dict:
    """`MKT-6`／`MKT-7` 的時間轉台北時間、表頭註明時區、布林改「是／否」、表頭「指標鍵」改「指標」（回複本）。"""
    out = copy.deepcopy(model)
    mkt6 = logic.find_block(out, "MKT-6")
    mkt6["column_labels"] = _local_labels(mkt6.get("column_labels"))
    for row in mkt6.get("_rows") or ():
        row["fetched_at"] = local_time_text(row.get("fetched_at"))
        if isinstance(row.get("is_revised"), bool):
            row["is_revised"] = REVISED_TEXT[row["is_revised"]]
    mkt7 = logic.find_block(out, "MKT-7")
    mkt7["column_labels"] = _local_labels(mkt7.get("column_labels"))
    for row in mkt7.get("_rows") or ():
        row["fetched_text"] = local_time_text(row.get("fetched_text"))
    mkt7["detail_lines"] = [line for line in mkt7.get("detail_lines") or () if line != _STORAGE_TZ_LINE]
    if isinstance(mkt7.get("summary_text"), str):
        mkt7["summary_text"] = mkt7["summary_text"].replace(_MKT7_KEY_WORD, TEXT_INDICATOR_COLUMN)
    return out


# N2（2026-10-13 稽核 G，總管裁定）：未存的欄位值只能出現在欄位本身與存檔區，另標「未存檔」。字面為本組擬定。
TEXT_UNSAVED_WINDOW = "未存檔：欄位的觀察窗與比較基準日和已存值不同，存檔後下一次重新載入才生效"
TEXT_UNSAVED_PICKS = "未存檔：勾選與已存清單不同，存檔後下一次重新載入才生效"


def _mark_unsaved(model, settings, settings_error, field_window_days, field_baseline_date, field_selected_keys):
    """在存檔區（該塊說明行）標出「欄位值 ≠ 已存值」。讀不到設定時不比（沒有已存值可比）。"""
    if settings_error:
        return model
    mkt4 = logic.find_block(model, "MKT-4")
    fields = (field_window_days, field_baseline_date)
    if fields != (None, None) and fields != (settings.get("window_days"), settings.get("baseline_date")):
        mkt4["detail_lines"].append(TEXT_UNSAVED_WINDOW)
    # 稽核 G（2026-10-13）：只比「使用者在勾選框上實際改了什麼」。比較基準 ＝ 勾選框剛載入時的樣子
    # （`initial_checkbox_values`：已存清單 ∩ 可勾清單；從未存過 ＝ 一個都不勾）。
    # ~~舊寫法拿整份已存清單（或從未存過時的「全部」）比~~ —— 已存清單裡已不在可勾清單的鍵、或從未存過，
    # 都會讓剛載入、什麼都沒動的畫面誤標「未存檔」。
    picks = set(field_selected_keys or ())
    keys = [item["name"] for item in logic.find_block(model, "MKT-5")["_items"]]
    initial = initial_checkbox_values(settings, keys) or {}
    baseline_picks = {key for key, checked in initial.items() if checked}
    if picks != baseline_picks:
        logic.find_block(model, "MKT-5")["detail_lines"].append(TEXT_UNSAVED_PICKS)
    return model


# 存檔結果的文案（字面為本組擬定；失敗那一句體例同 alo「存檔寫入失敗：…」，訊息原文照印、不改寫）。
TEXT_SAVED = "已存檔"
TEXT_SAVE_FAILED = "存檔寫入失敗："
_SAVE_BLOCK = {KEY_WINDOW: "MKT-4", KEY_BASELINE: "MKT-4", KEY_PAIR: "MKT-4", KEY_INDICATORS: "MKT-5"}


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


# ───────────────────────── 設定試算表尚未設定：一件事只用一種說法（BL-0250 批次 1）─────────────────────────
# 客戶 2026-10-19 裁示 G3（`docs/DECISIONS.md` `DEC-2026-10-19-04`）：同一件「設定試算表尚未設定」，本頁原本同時寫「⛔ 尚未設定」
# （資料狀態行、失敗摘要去重後）與「設定讀不到」（`MKT-4`／`MKT-5` 標題、停用原因、明細區那一行、核心卡副標）兩種說法。
# 已存設定**讀不到**的成因若是「尚未設定」那一族，那幾句改用同一種說法「尚未設定：<哪一項>」；真的讀取失敗（例：連線逾時）照舊「設定讀不到」。
# ⬜ 照舊（核心卡副標是「不適用」那一族，之七其四第 1 條）；判定、停用與否一個都不動，只換字。
_UNREADABLE_PHRASES = (
    # BL-0250 批次 2（批次 1 稽核建議）：核心卡副標原本會換成「⬜ 不適用：尚未設定：設定試算表」（兩個冒號），
    # 改把原因放進括號；⬜ 與「不適用」照舊，只修字句。須排在「比較條件讀不到」那一條前面。
    (logic.not_applicable_text("比較條件讀不到"), "⬜ 不適用（{reason}）"),
    (logic.TEXT_SHOW_ALL_UNREADABLE, "{reason}，暫時列出全部指標"),
    (logic.TEXT_SAVE_SETTINGS_UNREADABLE, "{reason}，暫不存檔"),
    ("比較條件讀不到", "{reason}"),
)


def relabel_unconfigured_settings(model: dict, reason: str) -> dict:
    """`reason`：「尚未設定：<哪一項>」。把本頁擬的「設定讀不到」那幾句換成 `reason`（就地改寫並回傳）。
    `_` 開頭的鍵底下的字一律不碰。"""
    def swap(text):
        for old, new in _UNREADABLE_PHRASES:
            text = text.replace(old, new.format(reason=reason))
        return reason if text == logic.TEXT_SETTINGS_UNREADABLE else text

    def visit(node, private=False):
        if isinstance(node, dict):
            for key in list(node):
                under = private or (isinstance(key, str) and key.startswith("_"))
                node[key] = visit(node[key], under)
            return node
        if isinstance(node, list):
            return [visit(item, private) for item in node]
        if isinstance(node, tuple):
            return tuple(visit(item, private) for item in node)
        if isinstance(node, str) and not private:
            return swap(node)
        return node

    return visit(model)
