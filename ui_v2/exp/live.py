# -*- coding: utf-8 -*-
"""標的探索正式模式才有的資料組裝與畫面調整（純函式；不 import streamlit、不 import 舊樹、不 import fixtures）。

依據：客戶 2026-10-13 裁示（B 線標的探索正式模式第一批 —— 骨架＋設定存讀＋母體代碼）：
- **篩選條件只有成功儲存的設定才生效**；儲存後於下一次重新載入／重新整理時套用；
  未儲存的暫存條件不得影響正式結果（`build_live_model` → `logic.build_page_model(saved_only=True)`）。
- **基本資料缺欄：基金仍保留在清單**，缺哪欄就顯示「⬜ 資料未備」，不得因單一欄位缺失讓整檔無聲消失。
  本批只有代碼，其餘欄一律 ⬜ 並寫出原因（`CELL_REASON`）。
  → 2026-10-14 C2 接線（狀態更新，不是漏刪）：基本資料、淨值、配息比已接上（`assemble_wired`，客戶同日裁示的規則
  逐條寫在該段）；`CELL_REASON` 只剩「沒有接線結果的舊呼叫端」那一條路在用。
- **禁止從基金名稱、代碼或 AI 推測任何屬性；缺值保持缺值、不填 0。**

示範模式（`ui_v2/app_exp.py`）不經過本檔，一個字都不變。分層照姊妹頁 mkt／alo：
`source.py`（L3 呼叫薄層，讀秘密值、呼叫 L2）→ 本檔（組 dataset、解析設定、組存檔輸入）→ `page.py`（純渲染）。

⚠️ 本檔新寫的畫面文案（`CELL_REASON`、`TEXT_*`）**沒有經過客戶草稿**（`49` §3.4 第 7 列：新文案一律先出草稿），
   字面為本組擬定，逐條列在交付報告的待裁段。
"""

from __future__ import annotations

import ast
import copy
import json
import math
import re
from datetime import date, datetime, timedelta, timezone

from .. import thresholds
from . import logic

# 正式模式 widget 鍵用的情境名（2026-10-14 由 `page._LIVE_SCENARIO` 移來；值不變，`page.py` 改讀這裡）。
LIVE_SCENARIO = "live"

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


# 「大於／小於」只能比數值（總管 2026-10-13 決定，比照客戶同日對 Q-07「單填一欄禁止存檔、存檔區寫明缺什麼」的前例）。
NUMERIC_OPERATORS = ("大於", "小於")


def numeric_value_text(index: int, value: str) -> str:
    """存檔區那一句（字面照總管派工單）。"""
    return f"第 {index} 列：條件數值「{value}」不是數值，大於／小於只能比數值"


def rule_value_problems(field_rules) -> list:
    """條件列裡「大於／小於」配上轉不成數的數值 → 每列一句（`numeric_value_text`）；沒有回空清單。

    - 數值欄留空的列**不算**（`44` `EXP-1`：留空 → 該列不生效，維持原行為）；
    - 「nan」「inf」這類 `float()` 吃得下、但比不出大小的字，同樣算轉不成數；
    - 只判斷，**不修正、不丟棄**那一列 —— 交回的句子只用來停用存檔並寫在存檔區。
    ⚠️ 刻意不併進 `rule_problem`：那一支也用在解析已存設定，併進去會讓雲端上已存的舊條件整份讀不了。
    """
    out = []
    for index, rule in enumerate(field_rules or (), start=1):
        if rule.get("op") not in NUMERIC_OPERATORS:
            continue
        value = str(rule.get("value", ""))
        if value.strip() == "":
            continue
        try:
            ok = math.isfinite(float(value))
        except (TypeError, ValueError):
            ok = False
        if not ok:
            out.append(numeric_value_text(index, value))
    return out


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


def build_dataset(pool, settings, wired=None) -> dict:
    """L2 `exp_universe.load_pool_codes` 的回傳 ＋ 已存設定（＋ C2 接線結果）→ 與示範資料同形的 dataset。

    - 母體讀不到（`failed`）或未設定雲端（`pool_not_cloud`）→ `fund_profile` 為空、`errors["fund_profile"]`
      放訊息原文（已遮蔽）；`logic` 照取數失敗那條路畫，**不講成「沒有符合的基金」**。
    - `wired`（2026-10-14 C2 接線；`assemble_wired` 的回傳）：給了就用它的 `fund_profile` 列、可用的最新淨值列
      與配息比；那幾格的原因與來源標示放在 `wired["cells"]`（`source.load_live` 交給 `notes["cells"]`）。
    - `wired` 為 None（只有代碼的舊呼叫端，例 `tests/ui_v2/_exp_live_stub.py`）→ 行為與接線前相同：
      其餘欄一律 None，那幾格由 `apply_live_notes` 寫「⬜ 資料未備：…尚未接入」。
      ⚠️ 2026-10-14 修正輪：這條路**只留給測試替身**（`notes[UNWIRED_FOR_TESTS] is True`）；正式入口母體讀到了
      卻沒有逐格原因，`apply_live_notes` 會 raise。
    """
    errors = {}
    profiles, navs, ratios = [], [], {}
    if pool["status"] == "ok":
        if wired is None:
            profiles = [_profile_row(code) for code in pool["codes"]]
        else:
            profiles = [dict(row) for row in wired["fund_profile"]]
            navs = [dict(row) for row in wired["nav"]]
            ratios = dict(wired["div_ratio_pct"])
            errors.update(wired["errors"])
    else:
        errors["fund_profile"] = pool["message"] or pool["status"]
    return {
        "fund_profile": profiles,
        "nav": navs,
        "dividend": [],
        "user_setting": _setting_rows(settings),
        "div_ratio_pct": ratios,
        "errors": errors,
        "save_errors": {},
    }


# ───────────────────────── C2 接線：基本資料、淨值、配息比（2026-10-14） ─────────────────────────
#
# 客戶已裁示的規則（派工單編號）逐條落在下面的函式；本段一律純函式，`today`、`mask` 由 `source.py` 注入。
# L2 的狀態字面在這裡**鏡像**一份（本檔不得 import services），由 tests/ui_v2/test_exp_live_wiring_logic.py 對拍。

PROFILE_STATUS_OK = "ok"                    # exp_profile.STATUS_OK
PROFILE_STATUS_NOT_READY = "not_ready"      # exp_profile.STATUS_NOT_READY
PROFILE_STATUS_FAILED = "fetch_failed"      # exp_profile.STATUS_FAILED
PROFILE_STATUS_INCONSISTENT = "inconsistent"  # exp_profile.STATUS_INCONSISTENT（畫面以 ⬜ 呈現）
TEXT_KEY_FAILED = "代碼無法對照：{reason}"   # exp_profile.TEXT_KEY_FAILED（逐字相同）
DIVIDEND_POLICY_ACCUM = "accum"             # exp_profile.DIVIDEND_POLICY_ACCUM

PROFILE_COLUMNS = ("fund_name", "ccy", "inception_on", "dividend_policy", "mgmt_fee_rate_pct")
NAV_COLUMNS = ("nav_date", "nav_orig_ccy", "div_ratio_pct")

# 規則 11：門檻只有一個出處（`ui_v2/thresholds.py`）；判定方向「大於」，等於 10 不算舊。
NAV_OLD_DAYS = thresholds.NAV_NOT_READY_DAYS
# 規則 11 的文字：與 `ui_v2/alo/logic.py::NAV_NOT_READY_DATED_TEXT` 逐字相同（本頁不 import alo，由測試比對），
# 不另編新文案。後半段同 `ui_v2/hld/live.py::NAV_NOTE_NOT_READY`。
NAV_NOT_READY_DATED_TEXT = "⬜ 資料未備：最近一筆淨值 {day}，已超過 {days} 日"
# 規則 13：近 12 個月確認完整且確定無配息。字面照派工單；主值字面 `⬜ 不適用` 是 `44` 5.1 `業務例外` 那一列。
TEXT_DIV_NONE_12M = logic.not_applicable_text("近 12 個月無配息")
# `docs/v2/49` Q7（客戶 2026-09-26 已同意）：配息幣別與淨值幣別不同 → 不適用（認不出的幣別仍是資料未備）。
TEXT_DIV_CCY_DIFFERS_NA = logic.not_applicable_text("配息幣別與淨值幣別不同")
# 總管 2026-10-14 裁定（Q7 只看配息比窗口）：衝突不在窗口內、或無法確認在不在 → 資料未備（本組擬定字面）。
TEXT_DIV_CCY_DIFFERS_BEFORE = "配息幣別與淨值幣別不同的紀錄只出現在近 12 個月以前，本格不下結論"
TEXT_DIV_CCY_DIFFERS_OUTSIDE = "配息幣別與淨值幣別不同的紀錄只出現在近 12 個月窗口之外，本格不下結論"
TEXT_DIV_CCY_DIFFERS_UNKNOWN = "無法確認幣別不同的配息是否在近 12 個月內"
TAG_DIV_CCY_DECLARED = "配息幣別宣告"
TIP_DIV_CCY_DECLARED = "來源：配息資料（各筆幣別宣告）"
# 2026-10-15 #966 修正輪 2（稽核 P 必修）：資料層有被剔除的配息列時 tooltip 的揭露句（字面為本組擬定）。
TIP_DIV_REJECTED = "另有 {n} 筆配息被資料層剔除（原因見資料層紀錄），無法確認是否為近 12 個月內幣別不同的配息"
TIP_DIV_REJECTED_UNKNOWN = "資料層沒有交出被剔除的配息筆數，無法確認是否還有近 12 個月內幣別不同的配息"

# 下列原因句為本組擬定（派工單沒有給字面；交付報告列待覆核）。
TEXT_NAV_NO_ROWS = "淨值來源沒有交出可用的淨值列"
TEXT_NAV_CCY_MISMATCH = "淨值資料幣別 {nav} 與基本資料幣別 {profile} 不同，淨值與配息比不計算"
TEXT_DIV_NOT_SETTLED = "配息資料未確認完整，配息比不計算"
TEXT_DIV_COVERAGE_SHORT = "配息資料最早只到 {start}，未涵蓋近 12 個月（窗口起點 {window}），配息比不計算"
# 總管 2026-10-14 裁定（規則 13 的依據）：沒有任何配息列時，只憑「各來源都回報沒有配息」不足以推到近 12 個月 ——
# 無法排除配息端點只保留近期、或退化回空。只有基本資料「配息政策」已確認為累積型時才畫不適用。
TEXT_DIV_NONE_UNVERIFIED = "各來源皆認得本檔且無配息紀錄，但無法確認來源保留期涵蓋近 12 個月"
# 規則 13 的畫面字樣不改；`ccy_undetermined` 的畫面字樣（總管 2026-10-14 修正輪：使用者可見文字不寫內部名稱）。
TEXT_CCY_UNDETERMINED = "計價幣別未確定（基本資料各來源幣別缺或不一致），淨值與配息比不取數"

# 來源標示（規則 10）。
SOURCE_SEP = "+"
TAG_FAILED = "{names} 失敗"
TAG_RATIO = "計算"
TAG_DIV_REPORTED = "來源回報"


# ───────── 原因白話化（總管 2026-10-14 修正輪：使用者可見文字不得出現內部名稱） ─────────
#
# 白名單對照（逐條、固定字串或固定樣式）＋ 通則（Python 字面與函式呼叫樣式改寫成字面文字）。
# ⛔ 不吞原因：認不得的字照原樣留下，只拿掉程式語法的外殼（引號、大括號、函式呼叫）。

_PLAIN_FIXED = (
    ("；完整原文見 source_status", ""),
    ("完整原文見 source_status", ""),
    ("A 鏈另走了 legacy 段的 wb05 內嵌解析（該段沒有取數狀態）", "另走了舊版配息頁解析（該段沒有取數狀態）"),
    # ~~("A 鏈", "淨值與配息取數")~~ → 2026-10-14 合併修正輪 D3（有意識的更正，不是漏刪）：一律換同一個詞時
    # 「A 鏈配息瀑布…」會變成「淨值與配息取數配息瀑布…」，語句不通；改成先換較長的片語。
    ("A 鏈配息瀑布", "配息"),
    ("A 鏈配息", "配息"),
    ("A 鏈", "多來源取數"),
)
# MoneyDJ 基本資料頁的頁型與主機（`repositories/fund/declared_profile.py` 的 `_DOMESTIC_INFO_PAGE`／`_OFFSHORE_INFO_PAGE`／
# `MONEYDJ_HOSTS`；#967 的逐網址原因寫成 `頁型@主機：原因`）。表外的頁型、主機照原字留下（不刪資訊）。
_PAGE_NAMES = {"yp011000": "境內基本資料頁", "yp011001": "境外基本資料頁"}
_HOST_NAMES = {"tcbbankfund.moneydj.com": "合庫子網域", "www.moneydj.com": "主站"}
_PLAIN_WORDS = {
    # 解析器標記（`repositories/fund/sources.py::DIV_PARSER_*`）
    "tcb_moneydj_div": "合庫配息頁", "fundclear_div": "FundClear 配息", "cnyes_div": "鉅亨配息",
    # 配息取數狀態（`DIV_OUTCOME_*`／`DIV_STATUS_*`）
    "none_confirmed": "確認沒有配息", "undetermined": "無法判定", "failed": "取數失敗", "rows": "有配息列",
    "empty": "沒有配息紀錄", "unknown": "狀態不明",
    # 丟列明細的鍵（`div_dropped_total`）
    "truncated": "截斷", "filtered": "過濾", "other_tables": "其他表格",
}
# A 鏈入口：整段是內部名稱，拿掉；外面剛好包著一對括號（「A 鏈（auto_fetch_moneydj('G07')）」）時連那一對一起拿掉。
# ~~拿掉之後再全域刪「（）」「()」~~ → 2026-10-15 #966 修正輪 2（稽核 Q 可選項；有意識的更正，不是漏刪；決策者：AI 總管）：
# 全域刪會把原因裡本來就有的空括號吃掉（`int()` → `int`）；改成只拿掉包著入口呼叫的那一對。
# 舊做法的用意（入口呼叫拿掉後不要留下一對空括號）仍然成立，由下面三支交替保住。
_INTERNAL_CALL = re.compile(r"（auto_fetch_moneydj\([^()]*\)）|\(auto_fetch_moneydj\([^()]*\)\)|auto_fetch_moneydj\([^()]*\)")
_CALL = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\(([^()（）]*)\)")             # 其他 name(args)：去掉呼叫樣式、留內容
_PAGE_AT_HOST = re.compile(r"\b([a-z]{2}\d{6})@([A-Za-z0-9.-]+)")          # yp011001@www.moneydj.com
# [yp010000] FundClear：
# ~~`\[([a-z]{2}\d{6})\]\s*([^\[\]：\n；]+?)：`~~ → 2026-10-15 #966 修正輪 3（獨立稽核必修；有意識的更正，不是漏刪；
# 決策者：AI 總管）：`\s*` 與第二組都吃得下空白，頁型標記後接一長串空白（半形、tab、全形「　」、NBSP）又沒有「：」時，
# `\s*` 每退一格第二組就重掃到尾 —— 平方時間（實測 f383c0c：`[yp010000]` 後接 2 萬個空白約 3.4 秒）。
# 改為第二組（來源名稱）第一個字不得是空白：`\s*` 退回的那一格一定是空白，第二組當場失敗，整體線性。
# **語意只差一個邊角**：舊式在「頁型後只有空白、緊接「：」」（`[yp010000]   ：`）時會把空白當成來源名稱命中，
# 名稱是冒號前那一個空白，畫成「 （頁面 yp010000）：」（開頭多一個空白）；新式不命中，改由 `_PAGE_TYPE` 畫成「（頁面 yp010000）：」。空白不是來源名稱，
# 以新式為準（測試釘住）。其餘輸入新舊逐字相同（等價性測試）。
_PAGE_SOURCE = re.compile(r"\[([a-z]{2}\d{6})\]\s*([^\[\]：\n；\s][^\[\]：\n；]*?)：")
_PAGE_TYPE = re.compile(r"\[([a-z]{2}\d{6})\]\s*")                       # 其餘 [yp010000]
_DICT = re.compile(r"\{[^{}]*\}")                                         # {'rows': 3}
_STATUS_WORD = re.compile(r"(狀態 |：)'?(none_confirmed|undetermined|failed|rows|empty|unknown)'?(?![A-Za-z0-9_])")
# 即時序列:'EUR'、MoneyDJ:'美元'。
# ~~`([^\s:：（(、，；]+):'`（名稱段沒有上限）~~ → 2026-10-15 #966 修正輪 2（稽核 Q 效能必修；有意識的更正，不是漏刪；
# 決策者：AI 總管）：本 pattern 開頭的字元類別沒有錨點、任一位置都能起頭，一長串不含空白、也沒有 `:'` 的字
# 會讓每一個起點都掃到尾再退回 —— 平方時間（實測 d00365c：1 萬個「中」約 1 秒、4 萬個約 15 秒）。
# 名稱段加上限 64：L2 原因裡出現在 `:'` 前的都是來源名稱（即時序列、MoneyDJ、TDCC、FundClear…），遠短於 64。
# **輸出逐字相同、不丟字**：名稱段由「從起點到冒號前那一串連續字元」唯一決定，舊式在最早的起點命中；
# 新式在那一串超過 64 字時改從冒號前第 64 字起頭命中，前面那一段原樣留在輸出裡，替換結果仍是同一串字
# （新舊對照見 tests/ui_v2/test_exp_live_wiring_logic.py 的等價性測試）。
_DECLARED = re.compile(r"([^\s:：（(、，；]{1,64}):'([^']*)'")
# 只認「前後不緊接英數字」的成對單引號：`can't parse 'x' near 'y` 只換 `'x'`，不把縮寫的撇號當引號。
_QUOTED = re.compile(r"(?<![A-Za-z0-9])'([^'\n]*)'(?![A-Za-z0-9])")


def _page_at_host(match) -> str:
    page, host = match.group(1), match.group(2)
    return f"{_PAGE_NAMES.get(page, '頁面 ' + page)}（{_HOST_NAMES.get(host, host)}）"


def _strip_shell(text: str) -> str:
    """讀不懂的字面只去殼：大括號換成全形括號、拿掉單引號，其餘逐字留下（不刪內容）。"""
    return text.replace("{", "（").replace("}", "）").replace("'", "")


def _plain_dict(match) -> str:
    try:
        value = ast.literal_eval(match.group(0))
    # ~~`except (ValueError, SyntaxError)`~~ → 2026-10-15 #966 修正輪 2（有意識的更正，不是漏刪；決策者：AI 總管）：
    # 實測 `{[1]}`（集合裡放清單）丟 TypeError、`{'a': 1+1+…}` 十萬字丟 RecursionError、`{'a': ---…1}` 丟 MemoryError
    # （剖析器堆疊溢位），都會讓 `plain_reason` 連帶整頁組裝炸掉。這些都只表示「這段不是讀得懂的 dict 字面」，照下面去殼處理。
    except (ValueError, SyntaxError, TypeError, RecursionError, MemoryError):
        return _strip_shell(match.group(0))
    if not isinstance(value, dict):
        return match.group(0)
    # 2026-10-15 #966 修正輪 3（獨立稽核小修；決策者：AI 總管）：讀得懂之後的格式化也可能失敗 —— 實測
    # `{'a': 0xfff…}`（4000 位十六進位）在 `str()` 轉十進位時超過 Python 4300 位上限丟 ValueError，整頁組裝跟著炸。
    # 格式化失敗同樣只表示「這段沒辦法換成白話」，照去殼處理。只收 ValueError（實測得到的那一種），其他例外照常往上拋。
    try:
        parts = [f"{_PLAIN_WORDS.get(str(k), str(k))} {'未記錄' if v is None else v}" for k, v in value.items()]
    except ValueError:
        return _strip_shell(match.group(0))
    # ~~空 dict →「（空）」~~ → 2026-10-15 #966 修正輪 2（稽核 Q 可選項；有意識的更正，不是漏刪；決策者：AI 總管）：
    # 字面 `{}` 不一定是「空的明細」（也可能是格式字串沒填的佔位），寫成「（空）」等於替原文下結論；改為原樣留下。
    return "、".join(parts) if parts else match.group(0)


def plain_reason(text: str) -> str:
    """L2 原因原文 → 使用者看得懂的字（集中一處；EXP-2／EXP-3／EXP-6 的文字、標示、tooltip 都走 `_finish`）。

    1. 固定字串對照（`_PLAIN_FIXED`）：「完整原文見 source_status」拿掉、「A 鏈…」改成白話片語；
    2. A 鏈入口的函式呼叫（`auto_fetch_moneydj('G07')`）整段拿掉、包著它的那一對括號一併拿掉；其他 `name(args)`
       改成「name（args）」（去掉呼叫樣式、內容保留；`int()` →「int（）」；巢狀呼叫只改最內層）；頁型保留：`[yp010000] FundClear：` →「FundClear（頁面 yp010000）：」，
       `yp011001@www.moneydj.com` →「境外基本資料頁（主站）」（表外頁型、主機照原字）；
    3. 狀態字（`狀態 'undetermined'`、`FundClear：empty`）與解析器標記照 `_PLAIN_WORDS` 換字；
    4. Python dict 字面（`{'rows': 3}`）換成「鍵 值」（空的 `{}` 原樣留下；讀不懂的字面只去殼）；`來源:'值'` 換成「來源 宣告「值」」；其餘 `'x'` 換成「x」。
    認不得的內容不刪，只去掉程式語法外殼。
    """
    if not isinstance(text, str):
        raise TypeError(f"plain_reason 只收字串（{type(text).__name__}）")
    out = text
    for old, new in _PLAIN_FIXED:
        out = out.replace(old, new)
    out = _INTERNAL_CALL.sub("", out)
    out = _CALL.sub(lambda m: f"{m.group(1)}（{m.group(2)}）", out)
    # ~~`_PAGE_TYPE.sub("", out)`（頁型整個刪掉）~~ → 2026-10-14 合併修正輪 B1（有意識的更正，不是漏刪）：
    # 刪掉之後同一來源的兩個頁型結果會畫成「FundClear：沒有配息紀錄；FundClear：取數失敗」自相矛盾；改為保留頁型。
    out = _PAGE_AT_HOST.sub(_page_at_host, out)
    out = _PAGE_SOURCE.sub(lambda m: f"{m.group(2)}（頁面 {m.group(1)}）：", out)
    out = _PAGE_TYPE.sub(lambda m: f"（頁面 {m.group(1)}）", out)
    out = _DICT.sub(_plain_dict, out)
    out = _STATUS_WORD.sub(lambda m: m.group(1) + _PLAIN_WORDS[m.group(2)], out)
    for word in ("tcb_moneydj_div", "fundclear_div", "cnyes_div"):
        out = out.replace(word, _PLAIN_WORDS[word])
    out = _DECLARED.sub(lambda m: f"{m.group(1)} 宣告「{m.group(2)}」", out)
    out = _QUOTED.sub(lambda m: f"「{m.group(1)}」", out)
    return out


def _note(text, state, tag=None, tip=None) -> dict:
    """一格的畫面調整：`text` 為 None ＝ 值照 `logic` 畫的（只掛來源標示）；否則覆寫該格文字與狀態。"""
    return {"text": text, "state": state, "source_tag": tag or None, "source_tip": tip or None}


def _finish(note: dict, mask) -> dict:
    """寫出點的最後一步（`exp_profile` 檔頭：原文不遮蔽，遮蔽在 L3）：文字、標示、tooltip 三者各自
    先遮蔽（秘密值以原文比對，必須在任何改寫之前）、再白話化（`plain_reason`）。"""
    out = dict(note)
    for key in ("text", "source_tag", "source_tip"):
        if out[key] is not None:
            masked = mask(out[key])
            if not isinstance(masked, str):
                raise TypeError(f"mask 應回傳字串（{type(masked).__name__}）")
            out[key] = plain_reason(masked)
    return out


def _source_tag(sources, failed=()) -> str:
    parts = []
    if sources:
        parts.append(SOURCE_SEP.join(sources))
    if failed:
        parts.append(TAG_FAILED.format(names="、".join(failed)))
    return " · ".join(parts)


def _source_tip(column, cell) -> str:
    lines = []
    if cell["sources"]:
        what = "計價幣別出處（來源自報）" if column == "ccy" else "出處"
        lines.append(f"{what}：{SOURCE_SEP.join(cell['sources'])}")
    if cell["failed_sources"]:
        lines.append(f"取數失敗的來源：{'、'.join(cell['failed_sources'])}")
    if cell.get("reason"):
        lines.append(f"原因：{cell['reason']}")
    return "；".join(lines)


def profile_cell_note(column: str, cell: dict) -> dict:
    """`exp_profile` 的一格（Cell）→ 畫面調整（規則 1、3、5、8、12）。

    - `ok` → 值照畫，掛來源標示；有失敗來源（規則 12，`PARTIAL_FAILURE_POLICY="accept"`）→ 標示寫出失敗來源，
      tooltip 寫原因；失敗來源不進 `sources`（L2 已處理，本層只照實呈現）。
    - `not_ready`／`inconsistent` → `⬜ 資料未備：<原因>`（規則 1；不一致 L2 註明「畫面以 ⬜ 呈現」）。
    - `fetch_failed` → `⛔ 取數失敗：<原因>`（規則 8）。
    其他狀態、或非 ok 卻沒有原因 → raise（契約被破壞，不猜）。
    """
    status = cell.get("status")
    tag = _source_tag(cell.get("sources") or (), cell.get("failed_sources") or ())
    tip = _source_tip(column, {"sources": cell.get("sources") or (), "failed_sources": cell.get("failed_sources") or (),
                               "reason": cell.get("reason")})
    if status == PROFILE_STATUS_OK:
        return _note(None, logic.STATE_OK, tag, tip)
    reason = cell.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError(f"{column}：狀態 {status!r} 卻沒有原因（{cell!r}）")
    if status in (PROFILE_STATUS_NOT_READY, PROFILE_STATUS_INCONSISTENT):
        return _note(f"{logic.ND_TEXT}：{reason}", logic.STATE_MISSING, tag, tip)
    if status == PROFILE_STATUS_FAILED:
        return _note(logic.fetch_failed_text(reason), logic.STATE_ERROR, tag, tip)
    raise ValueError(f"{column}：未知的基本資料狀態 {status!r}")


def profile_notes(profiles: dict) -> dict:
    """`exp_profile.build_profiles` 的 `cells` → `{代碼: {欄: note}}`（未遮蔽；遮蔽在 `assemble_wired` 一次做）。"""
    out = {}
    for code, cells in profiles["cells"].items():
        missing = [c for c in PROFILE_COLUMNS if c not in cells]
        if missing:
            raise ValueError(f"{code!r}：基本資料缺欄 {missing}")
        out[code] = {column: profile_cell_note(column, cells[column]) for column in PROFILE_COLUMNS}
    return out


def nav_codes_needed(profile_rows, settings, settings_error) -> list:
    """要去取淨值的代碼：`EXP-2` 會列出的檔（通過非淨值篩選、或因缺值而無法判定者；`EXP-3` 只從這些檔挑）。

    規則 7：篩選只用**已存**設定。讀不到設定 → 不列任何一檔 → 不取（那一輪 `EXP-2` 只寫失敗行）。
    沒有條件 → `EXP-2` 不列任何一檔 → 不取。條件只引用 `fund_profile` 欄，所以「先篩後取」不改變名單。
    """
    if settings_error:
        return []
    rules = tuple(settings.get(KEY_RULES) or ())
    if not rules:
        return []
    _steps, listed, _undet = logic.apply_rules_tristate(list(profile_rows), rules)
    return list(dict.fromkeys(row["fund_code"] for row in listed))


def nav_requests(codes, key_results, declared) -> tuple:
    """要取淨值的代碼 → (`exp_nav.load_nav_dividend` 的輸入, `{代碼: 代碼無法對照的原因}`)。

    幣別未確定（`declared` 為 `(None, None)`）→ 照傳 `declared_ccy=None`、`declared_ccy_source=None`，
    資料層隔離成 `ccy_undetermined`（本層不擋、不猜）。
    """
    by_code = {}
    for result in key_results:
        by_code.setdefault(result["input"], result)
    funds, unresolved = [], {}
    for code in codes:
        result = by_code.get(code)
        if result is None:
            raise ValueError(f"{code!r} 不在代碼對照結果裡")
        if result.get("ok") is not True:
            unresolved[code] = TEXT_KEY_FAILED.format(reason=result.get("error"))
            continue
        ccy, ccy_source = declared.get(code, (None, None))
        funds.append({
            "fund_code": code,
            "full_key": result["full_key"],
            "portal": result["portal"],
            "chain_code": result["parsed_code"],
            "declared_ccy": ccy,
            "declared_ccy_source": ccy_source,
        })
    return funds, unresolved


def _as_date(value, where: str) -> date:
    """L2 的日期（`date`）或 `YYYY-MM-DD` 字串 → `date`；`datetime` 與其他一律 raise（不猜時區）。"""
    if isinstance(value, datetime):
        raise TypeError(f"{where} 是 datetime，日期語意不明：{value!r}")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and len(value) == 10:
        try:
            parsed = date.fromisoformat(value)
        except ValueError:
            parsed = None
        if parsed is not None and parsed.isoformat() == value:
            return parsed
    raise ValueError(f"{where} 不是日期：{value!r}")


def window_start(nav_day: date) -> date:
    """配息比窗口起點（不含）：最新淨值日往前 12 個月的同一天；2/29 往前一年沒有 2/29 → 2/28。"""
    try:
        return nav_day.replace(year=nav_day.year - 1)
    except ValueError:
        return nav_day.replace(year=nav_day.year - 1, day=28)


def in_ratio_window(day: date, nav_day: date) -> bool:
    """配息比窗口 W ＝ (`window_start(nav_day)`, nav_day]：起點那一天不含、最新淨值日含。
    `dividend_ratio` 與 Q7 幣別衝突的判斷共用這一支（不另寫一份窗口）。"""
    return window_start(nav_day) < day <= nav_day


# 客戶 2026-10-18 裁示 BL-0375（`docs/DECISIONS.md` `DEC-2026-10-18-02`；44 第七節第三小節之十）：淨值超過門檻、而且資料層已確認
# 是即時取數失敗後退回的預存序列 → 三格寫 `⛔ 取數失敗：改用 <日期> 的預存淨值`（44 第五節第五小節模板；日期是畫面實際用的那一期），
# 不寫資料未備。門檻、判定方向與「不參與任何計算」照舊（這幾檔一列都不交給 `logic`）。
# 「已確認」只讀 L2 provenance 既有的兩個鍵（鏡像 `services/v2_tables/nav_dividend.py`，本檔不 import services，由測試對拍）：
# `cache_fallback` 為真（L1 只在即時網址全敗時交出 `cache/nav` 預存序列），而且 `latest_from` 不是累積表
# （累積表那一支 `cache_fallback` 也為真、但不是取數失敗；目前由 `NAV_HISTORY_PROVENANCE_VERIFIED` 關閉）。
# ⚠️ 只在閘門關閉時成立：閘門打開後，即時一段都沒有、`latest_from` 為累積表的那一種實為取數失敗後退回，這裡會漏判成
# 資料未備 —— 打開閘門前必須重審（`docs/BACKLOG.md` BL-0376；稽核建議改看 `live_error`）。
NAV_LATEST_FROM_HISTORY = "nav_history"    # nav_dividend.LATEST_FROM_NAV_HISTORY
NAV_RETREAT_FAILED_TEXT = "改用 {day} 的預存淨值"   # 與 `ui_v2/hld/live.py::NAV_RETREAT_FAILED_TEXT` 逐字相同（由測試比對）
TIP_NAV_RETREAT = "即時取數失敗，淨值取自預存序列，不是本次取得"


def nav_retreat_failed(prov) -> bool:
    """L2 provenance 是否已確認「即時取數失敗後退回預存序列」（見上方常數註解）。形狀不對 → 不算（照舊資料未備，不猜）。"""
    if not isinstance(prov, dict) or prov.get("cache_fallback") is not True:
        return False
    return prov.get("latest_from") != NAV_LATEST_FROM_HISTORY


def nav_is_old(last: date, today: date) -> bool:
    """規則 11：台灣今天減最後一筆 `nav_date` **大於** `NAV_OLD_DAYS`（＝`thresholds.NAV_NOT_READY_DAYS`）→ 舊（剛好 10 天不算）。"""
    days = (today - last).days
    if days < 0:
        raise ValueError(f"最後一筆淨值日 {last.isoformat()} 晚於今天 {today.isoformat()}")
    return days > NAV_OLD_DAYS


def dividend_ratio(nav_value, nav_ccy, nav_day, div_rows, *, settled, coverage_start, accum_confirmed) -> tuple:
    """近 12 個月配息佔淨值比 → `(kind, ratio 或 None, 原因或明細)`；
    `kind` ∈ {"ok", "none", "ccy_differs", "not_ready"}。

    算式：窗口 W ＝ (`window_start(d)`, d]，d ＝ 最新一筆 `nav_date`（含 d、不含起點那一天）；
        ratio ＝ Σ{ div_per_unit_orig_ccy ｜ ex_date ∈ W } ÷ 最新淨值 × 100（`math.fsum`）。
    前提（不成立 → `not_ready`，寫原因）：
    - `settled` 為 True（資料層確認每一筆都寫進來了）；
    - 有配息列時，覆蓋起點 `coverage_start` ≤ 窗口起點（否則窗口前段沒有證據）；
    - **一筆配息列都沒有**（資料層的「各來源都認得本檔、都回報沒有配息」，`coverage_start` 不存在）時：
      只有 `accum_confirmed`（基本資料配息政策已確認為累積型）才算確定無配息 → `none`；
      其餘（配息型、⬜、⛔、不一致）→ `not_ready`（`TEXT_DIV_NONE_UNVERIFIED`；總管 2026-10-14 裁定）。
    窗口內有配息列的幣別與淨值幣別不同 → `ccy_differs`（`49` Q7：不適用，不換算）。
    有配息列、覆蓋起點成立、窗口內 0 筆或合計為 0（`math.isclose`）→ `none`（規則 13）：不顯示 0.00%。
    逐筆走訪一次，O(n)。
    """
    if not settled:
        return "not_ready", None, TEXT_DIV_NOT_SETTLED
    start = window_start(nav_day)
    window_text = f"除息日在 {start.isoformat()}（不含）至 {nav_day.isoformat()} 之間"
    if not div_rows:
        if accum_confirmed:
            return "none", None, f"各來源皆認得本檔且無配息紀錄，基本資料配息政策為累積型；{window_text}沒有配息"
        return "not_ready", None, TEXT_DIV_NONE_UNVERIFIED
    cover = None if coverage_start is None else _as_date(coverage_start, "coverage_start")
    if cover is None or cover > start:
        return "not_ready", None, TEXT_DIV_COVERAGE_SHORT.format(
            start=cover.isoformat() if cover else "（未記錄）", window=start.isoformat())
    amounts, bad_ccy = [], set()
    for index, row in enumerate(div_rows):
        ex_day = _as_date(row["ex_date"], f"dividend 第 {index} 列 ex_date")
        if not in_ratio_window(ex_day, nav_day):
            continue
        if row["ccy"] != nav_ccy:
            bad_ccy.add(str(row["ccy"]))
            continue
        amounts.append(float(row["div_per_unit_orig_ccy"]))
    if bad_ccy:
        return "ccy_differs", None, f"配息幣別 {'、'.join(sorted(bad_ccy))}，淨值幣別 {nav_ccy}；不換算、不計算"
    total = math.fsum(amounts)
    if not amounts or math.isclose(total, 0.0, rel_tol=0.0, abs_tol=1e-12):
        return "none", None, f"{window_text}沒有配息；配息資料已確認完整"
    if not (isinstance(nav_value, (int, float)) and math.isfinite(nav_value) and nav_value > 0):
        raise ValueError(f"最新淨值不是正數：{nav_value!r}")
    ratio = total / nav_value * 100.0
    detail = (f"{window_text}的配息共 {len(amounts)} 筆，合計 {total:g} {nav_ccy} ÷ 最新淨值 {nav_value:g} {nav_ccy}"
              f" × 100")
    return "ok", ratio, detail


def _group(rows) -> dict:
    out = {}
    for row in rows:
        out.setdefault(row["fund_code"], []).append(row)
    return out


def _nav_tip(prov: dict, extra=None) -> str:
    parts = []
    source = prov.get("source")
    if source:
        parts.append(f"淨值來源：{source}")
    if prov.get("fetched_at"):
        parts.append(f"取得時間：{prov['fetched_at']}")
    if extra:
        parts.append(extra)
    return "；".join(parts)


def _all_nav(text, state, tag=None, tip=None) -> dict:
    return {column: _note(text, state, tag, tip) for column in NAV_COLUMNS}


def nav_notes_and_rows(codes, nav_out, *, unresolved, profile_ccy, accum_codes, today, withheld_texts,
                       input_conflict, div_ccy_differs) -> tuple:
    """淨值與配息比（規則 8、11、13、14 與配息比定義）→ `(nav 列, {代碼: 配息比}, {代碼: {欄: note}})`。

    - `nav_out`：`exp_nav.load_nav_dividend` 的回傳（`codes` 全部代碼無法對照時可為 None）。
    - `withheld_texts`：**封閉**的淨值扣下代碼 → 固定文字（None ＝ 用資料層的 `skipped` 原文）；
      不在裡面的扣下代碼、或 `input_conflict` → raise（契約被破壞，不猜）。
    - `accum_codes`：基本資料配息政策已確認為累積型的代碼（規則 13 無配息列時的依據）。
    - `div_ccy_differs`：資料層「配息幣別認得出、但與淨值幣別不同」的扣下代碼（`49` Q7 → 不適用）。
    - 只把**可用的最新一筆**淨值交給 `logic`：過舊（規則 11）、幣別衝突（規則 14）、扣下、失敗的檔一列都不交，
      所以它們不參與任何計算（含排序與配息比）。
    """
    nav_rows, ratios, notes = [], {}, {}
    nav_part = div_part = None
    if nav_out is not None:
        nav_part, div_part = nav_out["nav"], nav_out["dividend"]
    nav_by = _group(nav_part["rows"]) if nav_part else {}
    div_by = _group(div_part["rows"]) if div_part else {}
    for code in codes:
        if code in unresolved:
            notes[code] = _all_nav(f"{logic.ND_TEXT}：{unresolved[code]}", logic.STATE_MISSING)
            continue
        if nav_part is None:
            raise ValueError(f"{code!r} 需要淨值，卻沒有淨值結果")
        prov = nav_part["provenance"].get(code) or {}
        tag = str(prov["source"]) if prov.get("source") else None
        error = nav_part["errors"].get(code)
        withheld = nav_part["withheld"].get(code)
        skipped = "；".join(str(line) for line in nav_part["skipped"].get(code) or ())
        if error:
            notes[code] = _all_nav(logic.fetch_failed_text(str(error)), logic.STATE_ERROR, tag, _nav_tip(prov))
            continue
        if withheld:
            if withheld == input_conflict or withheld not in withheld_texts:
                raise ValueError(f"{code!r}：未登記的淨值扣下代碼 {withheld!r}（{skipped}）")
            reason = withheld_texts[withheld] or skipped or withheld
            notes[code] = _all_nav(f"{logic.ND_TEXT}：{reason}", logic.STATE_MISSING, tag, _nav_tip(prov, reason))
            continue
        rows = nav_by.get(code) or []
        if not rows:
            reason = skipped or TEXT_NAV_NO_ROWS
            notes[code] = _all_nav(f"{logic.ND_TEXT}：{reason}", logic.STATE_MISSING, tag, _nav_tip(prov, reason))
            continue
        latest = max(rows, key=lambda r: _as_date(r["nav_date"], f"{code} nav_date"))
        last = _as_date(latest["nav_date"], f"{code} nav_date")
        if nav_is_old(last, today):                                             # 規則 11
            if nav_retreat_failed(prov):                                        # BL-0375（客戶 2026-10-18 裁示）
                text = logic.fetch_failed_text(NAV_RETREAT_FAILED_TEXT.format(day=last.isoformat()))
                notes[code] = _all_nav(text, logic.STATE_ERROR, tag, _nav_tip(prov, TIP_NAV_RETREAT))
                continue
            text = NAV_NOT_READY_DATED_TEXT.format(day=last.isoformat(), days=NAV_OLD_DAYS)
            notes[code] = _all_nav(text, logic.STATE_MISSING, tag, _nav_tip(prov))
            continue
        declared = profile_ccy.get(code)
        if declared is not None and latest["ccy"] != declared:                  # 規則 14（資料層之外再擋一次）
            reason = TEXT_NAV_CCY_MISMATCH.format(nav=latest["ccy"], profile=declared)
            notes[code] = _all_nav(f"{logic.ND_TEXT}：{reason}", logic.STATE_MISSING, tag, _nav_tip(prov, reason))
            continue
        nav_rows.append({"fund_code": code, "nav_date": last.isoformat(), "nav_orig_ccy": latest["nav_orig_ccy"],
                         "ccy": latest["ccy"]})
        tip = _nav_tip(prov, f"資料日期：{last.isoformat()}")
        cells = {"nav_date": _note(None, logic.STATE_OK, tag, tip), "nav_orig_ccy": _note(None, logic.STATE_OK, tag, tip)}
        cells["div_ratio_pct"] = _ratio_note(code, latest, last, div_part, div_by, ratios,
                                             accum=code in accum_codes, input_conflict=input_conflict,
                                             div_ccy_differs=div_ccy_differs)
        notes[code] = cells
    return nav_rows, ratios, notes


def _div_basis(prov: dict) -> str:
    """配息那一格 tooltip 的「依據」：L2 實際交出的取數狀態（`outcome_detail`，逐來源回報），經白話化後上畫面。"""
    detail = prov.get("outcome_detail")
    return f"配息依據：{str(detail).replace(chr(10), '；')}" if detail else ""


def _ccy_differs_note(prov: dict, nav_ccy: str, nav_day: date, basis: str, skipped: str) -> dict:
    """資料層 `div_ccy_differs`（配息宣告的幣別認得出、但與淨值幣別不同）→ 該格（總管 2026-10-14 裁定 C2）。

    - 至少一筆衝突除息日落在配息比窗口內（`in_ratio_window`，與 `dividend_ratio` 同一個窗口）→ `⬜ 不適用`；
    - 任一筆衝突取不到除息日、或資料層沒有交出衝突日期 → `⬜ 資料未備`（無法確認）；
    - 資料層有被剔除的配息列（`conflict_rejected_rows` > 0）、或沒有交出這個計數 → `⬜ 資料未備`（無法確認）；
    - 其餘（衝突全在窗口外、而且沒有被剔除的列）→ `⬜ 資料未備`（只在以前／窗口外，本格不下結論）。
    tooltip 附上資料層 `skipped` 原文（幣別值、筆數、被剔除各列的原因；與其他字一樣在 `_finish` 先遮蔽、再白話化）。

    2026-10-15 #966 修正輪 2（稽核 P 必修；決策者：AI 總管；讀碼確認，不是猜）：L2 `rows_from_chain_dividends` 在這一支
    提早回傳，被剔除的列（日期格式不對、出處對不上、沒宣告幣別）原本只記在函式內、不交出，而日期壞掉的那一筆根本進不了
    `conflict_ex_dates`（`conflict_ex_dates_missing` 因此恆為 0）—— 舊版會把「2020 年 EUR ＋ 一筆壞日期 EUR」說成
    「只出現在近 12 個月以前」。L2 改為交出 `conflict_rejected_rows`（本支專用），本層據此判斷；被剔除的列可能是窗口內的
    另一筆不同幣別配息，所以只要有就不下「以前／窗口外」的結論。至少一筆**已確認**落在窗口內時仍畫不適用（那一筆就是證據）。
    本輪不拿窗口內同幣別的配息去算配息比。來源標示照實寫「配息幣別宣告」（資料層這一支沒有配息來源欄可用）。
    """
    raw = prov.get("conflict_ex_dates")
    missing = prov.get("conflict_ex_dates_missing")
    rejected = prov.get("conflict_rejected_rows")
    l2_line = f"資料層紀錄：{skipped}" if skipped else ""
    tip_parts = [TIP_DIV_CCY_DECLARED, f"淨值幣別 {nav_ccy}；配息比窗口：除息日在 {window_start(nav_day).isoformat()}"
                 f"（不含）至 {nav_day.isoformat()} 之間"]
    if not isinstance(raw, list) or not raw or not isinstance(missing, int) or missing or any(d is None for d in raw):
        tip = "；".join(p for p in [*tip_parts, "配息宣告的幣別與淨值幣別不同，但有衝突筆取不到除息日", l2_line, basis]
                       if p)
        return _note(f"{logic.ND_TEXT}：{TEXT_DIV_CCY_DIFFERS_UNKNOWN}", logic.STATE_MISSING, TAG_DIV_CCY_DECLARED, tip)
    days = [_as_date(d, "conflict_ex_dates") for d in raw]
    shown = "、".join(d.isoformat() for d in days)
    if not isinstance(rejected, int) or isinstance(rejected, bool) or rejected < 0:
        unsure = TIP_DIV_REJECTED_UNKNOWN
    elif rejected:
        unsure = TIP_DIV_REJECTED.format(n=rejected)
    else:
        unsure = ""
    tip = "；".join(p for p in [*tip_parts, f"配息宣告的幣別與淨值幣別不同的除息日：{shown}", unsure, l2_line, basis]
                   if p)
    if any(in_ratio_window(d, nav_day) for d in days):
        return _note(TEXT_DIV_CCY_DIFFERS_NA, logic.STATE_BIZ, TAG_DIV_CCY_DECLARED, tip)
    if unsure:
        return _note(f"{logic.ND_TEXT}：{TEXT_DIV_CCY_DIFFERS_UNKNOWN}", logic.STATE_MISSING, TAG_DIV_CCY_DECLARED, tip)
    reason = (TEXT_DIV_CCY_DIFFERS_BEFORE if all(d <= window_start(nav_day) for d in days)
              else TEXT_DIV_CCY_DIFFERS_OUTSIDE)
    return _note(f"{logic.ND_TEXT}：{reason}", logic.STATE_MISSING, TAG_DIV_CCY_DECLARED, tip)


def _ratio_note(code, latest, last, div_part, div_by, ratios, *, accum, input_conflict, div_ccy_differs) -> dict:
    if div_part is None:
        raise ValueError(f"{code!r} 有淨值，卻沒有配息結果")
    prov = div_part["provenance"].get(code) or {}
    sources = prov.get("source")
    tag_src = SOURCE_SEP.join(map(str, sources)) if isinstance(sources, (list, tuple)) else (sources or None)
    basis = _div_basis(prov)
    skipped = "；".join(str(line) for line in div_part["skipped"].get(code) or ())
    error = div_part["errors"].get(code)

    def tip_of(*parts):
        return "；".join(p for p in (f"配息來源：{tag_src}" if tag_src else "", *parts, basis) if p)

    if error:
        return _note(logic.fetch_failed_text(str(error)), logic.STATE_ERROR, tag_src, tip_of())
    withheld = div_part["withheld"].get(code)
    if withheld == input_conflict:
        raise ValueError(f"{code!r}：配息輸入矛盾（{skipped}）")
    if withheld == div_ccy_differs:                                            # `49` Q7（只看配息比窗口）
        return _ccy_differs_note(prov, latest["ccy"], last, basis, skipped)
    if withheld or div_part["pending"].get(code):
        reason = skipped or str(withheld or div_part["pending"].get(code))
        return _note(f"{logic.ND_TEXT}：{reason}", logic.STATE_MISSING, tag_src, tip_of(reason))
    rows = div_by.get(code) or []
    kind, ratio, detail = dividend_ratio(
        latest["nav_orig_ccy"], latest["ccy"], last, rows,
        settled=div_part["settled"].get(code) is True, coverage_start=prov.get("coverage_start"),
        accum_confirmed=accum)
    # 規則 13 那一格不寫「計算」：沒有配息列時標示是來源回報（依據在 tooltip）；有配息列時標示是配息來源。
    tag = TAG_RATIO if kind == "ok" else (tag_src or TAG_DIV_REPORTED)
    if kind == "ok":
        ratios[code] = ratio
        return _note(None, logic.STATE_OK, tag, tip_of(detail))
    if kind == "none":
        return _note(TEXT_DIV_NONE_12M, logic.STATE_BIZ, tag, tip_of(detail))
    if kind == "ccy_differs":
        return _note(TEXT_DIV_CCY_DIFFERS_NA, logic.STATE_BIZ, tag, tip_of(detail))
    # 格內只寫本層的判定句；資料層的 `skipped` 原文（白話化後）放 tooltip。
    return _note(f"{logic.ND_TEXT}：{detail}", logic.STATE_MISSING, tag, tip_of(detail, skipped))


def assemble_wired(profiles, codes, nav_out, *, unresolved, today, mask, withheld_texts, input_conflict,
                   div_ccy_differs) -> dict:
    """C2 接線的總裝（純函式）→ `build_dataset(..., wired=...)` 吃的形狀：
    `{"fund_profile", "nav", "div_ratio_pct", "errors", "cells"}`。`cells` 每一格都已經過 `mask` 與 `plain_reason`。

    `today`：台灣今天的日期（`date`，不收 `datetime`）。
    """
    if isinstance(today, datetime) or not isinstance(today, date):
        raise TypeError(f"today 應為 date：{today!r}")
    if not callable(mask):
        raise TypeError("mask 必須給（遮蔽在寫出點做一次）")
    cells = profile_notes(profiles)
    profile_ccy = {code: (c["ccy"]["value"] if c["ccy"]["status"] == PROFILE_STATUS_OK else None)
                   for code, c in profiles["cells"].items()}
    accum_codes = {code for code, c in profiles["cells"].items()
                   if c["dividend_policy"]["status"] == PROFILE_STATUS_OK
                   and c["dividend_policy"]["value"] == DIVIDEND_POLICY_ACCUM}
    nav_rows, ratios, nav_notes = nav_notes_and_rows(
        codes, nav_out, unresolved=unresolved, profile_ccy=profile_ccy, accum_codes=accum_codes, today=today,
        withheld_texts=withheld_texts, input_conflict=input_conflict, div_ccy_differs=div_ccy_differs)
    for code, notes in nav_notes.items():
        cells.setdefault(code, {}).update(notes)
    done = {code: {column: _finish(note, mask) for column, note in notes.items()} for code, notes in cells.items()}
    return {"fund_profile": [dict(row) for row in profiles["rows"]], "nav": nav_rows, "div_ratio_pct": ratios,
            "errors": {}, "cells": done}


TEXT_KEYS_FAILED_SUMMARY = "⛔ 取數失敗：代碼對照表讀取失敗，無法列出候選"


def wiring_failed(message: str) -> dict:
    """代碼對照表讀不到（整批無從取數）→ `fund_profile` 取數失敗（規則 8；訊息由呼叫端遮蔽）。
    `EXP-2` 摘要改寫成 `TEXT_KEYS_FAILED_SUMMARY`（`apply_live_notes`），不寫「0 檔候選」。"""
    return {"fund_profile": [], "nav": [], "div_ratio_pct": {}, "errors": {"fund_profile": message}, "cells": {}}


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
# 母體讀不到時 `EXP-2` 的摘要（稽核 L 第六輪：不得寫「0 檔候選」）。字面為本組擬定；燈與狀態照舊走取數失敗那一路。
TEXT_POOL_FAILED = "⛔ 取數失敗：選股池這次讀不到，候選清單不列任何一檔"
TEXT_POOL_COOLING = "⛔ 取數失敗：選股池冷卻中，本次未重新讀取，候選清單不列任何一檔"
# 〔已撤〕「⛔ 未讀取選股池：未設定雲端來源，候選清單不列任何一檔」→ 總管 2026-10-13 第七輪裁決：改回 `44` 第五節
#   系統錯誤模板體例（⛔ 取數失敗：<原因>），與同卡說明行、`EXP-0` 用詞一致；燈色與 `EXP-0` 文案不動。
#   「未設定是否該從取數失敗拆出、改灰」屬 `44` 規格層級，登記在 `44` 檔尾 7.3.2，待另案。
TEXT_POOL_NOT_CLOUD = "⛔ 取數失敗：選股池未設定雲端來源（沒有服務帳戶憑證），候選清單不列任何一檔"


def pool_lines(pool) -> list:
    """`EXP-2` 說明行：母體從哪裡來、略過了什麼（只在讀到時寫；讀不到由 `logic` 照取數失敗畫）。"""
    if pool["status"] != "ok":
        return []
    lines = [
        (f"母體：選股池的基金代碼 {len(pool['codes'])} 檔。只取代碼；"
         "選股池上的名稱、幣別、類別一律不用（不可信，客戶 2026-10-13 判定）。"),
    ]
    read_line = pool_read_line(pool)
    if read_line:
        lines.append(read_line)
    if pool["dropped_blank"]:
        lines.append(f"選股池有 {pool['dropped_blank']} 列代碼為空白，未列入。")
    if pool["duplicates"]:
        lines.append(f"選股池有 {pool['duplicates']} 列代碼重複，只列一次。")
    return lines


TAIPEI = timezone(timedelta(hours=8))


def _interval_text(seconds) -> str:
    if seconds and seconds % 3600 == 0:
        return f"{seconds // 3600} 小時"
    return f"{int(seconds or 0) // 60} 分鐘"


def pool_read_line(pool) -> str | None:
    """2026-10-13 第二輪複驗回修：交代母體的延遲 —— L2 只快取成功結果（`ttl_sec`），快取命中時沿用原讀取時間。
    `read_at` 缺或解析不了 → 不寫這一行（不編一個時間）。字面為本組擬定。"""
    raw = pool.get("read_at")
    if not raw:
        return None
    try:
        when = datetime.fromisoformat(raw)
    except (TypeError, ValueError):
        return None
    if when.tzinfo is None:
        return None
    shown = when.astimezone(TAIPEI).strftime("%Y-%m-%d %H:%M")
    return f"選股池讀取於 {shown}（台北時間），最長約 {_interval_text(pool.get('ttl_sec'))}更新一次。"


def _fill_missing(cells):
    for column, cell in cells.items():
        if cell["_state"] == logic.STATE_MISSING and cell["text"] == "⬜" and column in CELL_REASON:
            cell["text"] = missing_text(column)


def _apply_cell_notes(code, cells, by_code):
    """C2 接線：逐格套用 `notes["cells"][代碼][欄]`（`assemble_wired` 產出，已遮蔽）。

    - note 有 `text`：該格必須是 `logic` 畫的缺格（值沒交給 `logic`）—— 換成 note 的文字與狀態；
      值卻在 → raise（資料與原因互相矛盾，不猜哪一邊對）。
    - note 沒有 `text`：值照 `logic` 畫的；該格卻是缺格 → raise（缺了卻沒有原因）。
    - 兩種都掛 `source_tag`／`source_tip`（規則 10：不加欄，值旁標示＋tooltip；`page.py` 負責 escape）。
    只處理有 note 網域的欄（`PROFILE_COLUMNS`＋`NAV_COLUMNS`）；代碼欄、篩選判定欄不動。
    """
    notes = by_code.get(code)
    for column, cell in cells.items():
        if column not in PROFILE_COLUMNS and column not in NAV_COLUMNS:
            continue
        note = (notes or {}).get(column)
        if note is None:
            raise ValueError(f"{code!r} 的「{column}」沒有原因紀錄（接線結果缺這一格）")
        is_missing_cell = cell["_state"] == logic.STATE_MISSING and cell["text"] == "⬜"
        if note["text"] is not None:
            if not is_missing_cell:
                raise ValueError(f"{code!r} 的「{column}」有值，原因紀錄卻說不可用：{note['text']!r}")
            cell["text"] = note["text"]
            cell["_state"] = note["state"]
            cell["_tone"] = logic.tone_for_state(note["state"])
        elif is_missing_cell:
            raise ValueError(f"{code!r} 的「{column}」是缺格，原因紀錄卻說可用")
        if note["source_tag"]:
            cell["source_tag"] = note["source_tag"]
        if note["source_tip"]:
            cell["source_tip"] = note["source_tip"]


# 未接線模式的開關（`notes` 的鍵）：**只有測試替身**可以設為 True（正式入口 `source.load_live` 一律交 `cells`）。
UNWIRED_FOR_TESTS = "unwired_for_tests"


# ───────────────────────── 一般畫面字句（BL-0250 批次 1）─────────────────────────
# 客戶 2026-10-19 裁示（`docs/DECISIONS.md` `DEC-2026-10-19-04`）：下列幾句是元件說明、開發沿革或工程字樣，正式模式改寫或拿掉；
# 示範模式不經過本檔，照舊。整句相等才換（值為 None ＝ 整句拿掉）；判定、計數、寫入一個都不動。
# ⛔ 不改的：排序那一句保留「幣別混排」的提醒（只拿掉「44 …」那半句）；`EXP-4` 那一句保留「取消勾基金名時清單上就沒有基金名」的提醒。
TEXT_EXP6_NONE = "先在結果清單勾一檔「對照」"
TEXT_EXP7_FAILED = "取數失敗，暫無篩選軌跡"
TEXT_SORT_MIXED_CCY = "⚠ 目前依最近淨值（原幣）排序，不同幣別的數字因此被放在同一個順序裡比大小。"
LIVE_TEXT_EDITS = {
    # `EXP-0` 說明行：元件說明（燈讀哪幾塊），不是給使用者的資訊。
    "本塊不自取數：只讀 EXP-2 的列數與 EXP-1 的條件列數。": None,
    # `EXP-6` 說明行：沒有要顯示的基金時，寫使用者要做什麼才看得到。
    "本塊目前沒有要顯示的基金。": TEXT_EXP6_NONE,
    # `EXP-7` 空狀態：上游取數失敗時那一句。
    "上游取數失敗，本塊不列出任何軌跡列。": TEXT_EXP7_FAILED,
    # `EXP-2` 依最近淨值排序時那一句：拿掉「44 允許……」半句，留幣別混排的提醒。
    TEXT_SORT_MIXED_CCY + "44 允許使用者自選排序欄位，也沒有一條規則擋這一種；就地寫出來，不自行拿掉這一項。":
        TEXT_SORT_MIXED_CCY,
    # `EXP-4`（兩鍵一成一敗）、`EXP-5`（停用不出失敗框）兩句條件式登記：開發沿革，整句拿掉。
    "⚠ 這一枚按鈕同時寫兩鍵。兩鍵一成一敗時畫面長什麼樣，44 沒有寫，本頁不替它選；目前這個畫面演的是兩鍵都失敗。": None,
    "⚠ 這一枚按鈕目前停用，所以不出存檔失敗框。按不到的按鈕會不會有失敗態，44 沒有寫，本頁取「停用就不出失敗框」這一邊。":
        None,
    # `EXP-4` 說明行（`logic.TEXT_EXP4_LIVE` 經 `_drop_dev_notes` 之後）：拿掉「正式模式的」。
    logic.LIVE_DEV_NOTE_EDITS[logic.TEXT_EXP4_LIVE]:
        logic.LIVE_DEV_NOTE_EDITS[logic.TEXT_EXP4_LIVE].replace("正式模式的候選清單", "候選清單"),
}


def _edit_exact(node, edits):
    """整句相等 → 換成表裡的值；值為 None 就整句拿掉（就地改寫並回傳）。"""
    if isinstance(node, dict):
        for key, value in node.items():
            node[key] = _edit_exact(value, edits)
        return node
    if isinstance(node, (list, tuple)):
        kept = [_edit_exact(v, edits) for v in node if not (isinstance(v, str) and v in edits and edits[v] is None)]
        return type(node)(kept)
    if isinstance(node, str) and node in edits and edits[node] is not None:
        return edits[node]
    return node


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


def apply_live_notes(model: dict, notes: dict, *, save_wired: bool = False) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。

    - 缺的格寫原因（`EXP-2`、`EXP-3`、`EXP-6`）；
    - `EXP-2` 說明行寫母體來源；`EXP-1` 說明行補比較方向可填哪些；
    - 「存檔」類按鈕：沒接上寫入函式 → 停用；已存設定讀不到 → 停用（存了會蓋掉讀不到的那一份）。
    """
    out = _edit_exact(_drop_dev_notes(copy.deepcopy(model)), LIVE_TEXT_EDITS)
    by_code = notes.get("cells")
    exp6 = logic.find_block(out, "EXP-6")
    exp6_cells = dict(zip((key for key, _label in logic.EXP6_FIELDS), exp6["_fields"])) if exp6["_fields"] else {}
    if by_code is None and notes["pool"]["status"] == "ok" and notes.get(UNWIRED_FOR_TESTS) is not True:
        # 總管 2026-10-14 修正輪（Q O3）：正式入口母體讀到了卻沒有逐格原因 ＝ 接線斷了；不得靜默印「尚未接入」。
        raise ValueError("母體已讀到，卻沒有逐格原因（notes['cells']）；正式入口一定要交接線結果")
    if by_code is None:
        # 未接線模式：**只給測試替身用**（`notes[UNWIRED_FOR_TESTS] is True`，例 `tests/ui_v2/_exp_live_stub.py`），
        # 或母體讀不到（沒有任何一列可畫）。缺的格寫「…尚未接入」。
        for row in logic.find_block(out, "EXP-2")["_rows"]:
            _fill_missing(row["_cells"])
        for column in logic.find_block(out, "EXP-3")["_columns"]:
            _fill_missing(column["_cells"])
        if exp6_cells:
            _fill_missing(exp6_cells)
    else:
        for row in logic.find_block(out, "EXP-2")["_rows"]:
            _apply_cell_notes(row["_fund_code"], row["_cells"], by_code)
        for column in logic.find_block(out, "EXP-3")["_columns"]:
            _apply_cell_notes(column["_fund_code"], column["_cells"], by_code)
        if exp6_cells:
            _apply_cell_notes(exp6["_fund_code"], exp6_cells, by_code)
    exp2 = logic.find_block(out, "EXP-2")
    exp2["detail_lines"].extend(pool_lines(notes["pool"]))
    pool = notes["pool"]
    if pool["status"] != "ok":
        exp2["summary_text"] = (
            TEXT_POOL_NOT_CLOUD if pool["status"] == "pool_not_cloud"
            else TEXT_POOL_COOLING if pool.get("cooling")
            else TEXT_POOL_FAILED
        )
    elif notes.get("wiring_error"):
        # 代碼對照表讀不到（`wiring_failed`）：據實寫，不寫「0 檔候選」（Q 修正輪必修 9）。
        exp2["summary_text"] = TEXT_KEYS_FAILED_SUMMARY
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
    # 總管 2026-10-13 決定：「大於／小於」配上轉不成數的數值 → 不寫（畫面上存檔已停用，這裡是第二道）。
    problems.extend(rule_value_problems(rules))
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
        tristate=True,
        code_column=True,
    )
    model = apply_live_notes(model, notes, save_wired=save_wired)
    value_problems = rule_value_problems(field_rules)
    if value_problems:
        # 總管 2026-10-13 決定（比照 Q-07 前例）：存檔停用，存檔區逐列寫明；不自動修正、不丟棄該列。
        exp1 = logic.find_block(model, "EXP-1")
        exp1["detail_lines"].extend(value_problems)
        for button in exp1["buttons"]:
            if button["_action_kind"] == ACTION_SAVE and button["_enabled"]:
                button["_enabled"] = False
                button["disabled_reason"] = "；".join(value_problems)
    if not settings_error and (field_columns is not None or field_sort is not None):
        settings = notes.get("settings") or {}
        if set(field_columns or ()) != set(settings.get(KEY_COLUMNS) or ()) \
                or field_sort != settings.get(KEY_SORT):
            logic.find_block(model, "EXP-4")["detail_lines"].append(TEXT_UNSAVED_EXP4)
    card_provenance_not_applicable(model)
    return apply_save_results(model, save_results)


# ───────────── BL-0250 批次 3-A：三張核心卡的「來源／新鮮度」→ ⬜ 不適用（客戶 2026-10-19 批次 3 裁示第 1 點） ─────────────
# 客戶原文：「採 ⬜ 不適用。理由：卡片本身沒有單一來源／單一新鮮度屬性，不是資料未備。不得擴張成其他缺資料情境也使用 ⬜。」
# 44 第七節第三小節之十二。射程只有標的探索這三張卡（`EXP-1`／`EXP-2`／`EXP-3`）卡片層級那一組佔位徽章（`logic.placeholder_badge`，
# 草稿 §H T-17「每卡掛一組，刻意畫成佔位」）；逐檔、逐格的來源與缺值照舊（缺資料照舊 ◇／⛔，不用 ⬜）。示範模式不經過本檔，照舊。
# 字面的括號理由為實作組依裁示理由擬定（線框第六版的「各檔來源見每列展開」指的是 3-B 才做的列展開，本批還沒有，所以不寫），可推翻。
CARD_PROVENANCE_CODES = ("EXP-1", "EXP-2", "EXP-3")
TEXT_CARD_PROVENANCE_NA = "⬜ 不適用（這張卡由多檔基金組成，沒有單一的來源與新鮮度）"


def card_provenance_not_applicable(model: dict) -> int:
    """三張核心卡上那兩枚佔位徽章（〔來源層級〕〔新鮮度〕）→ 一枚「⬜ 不適用（…）」（就地改寫）。回改了幾張卡。
    只認 `_placeholder` 為真的來源／新鮮度徽章；其他徽章一枚不動。"""
    count = 0
    for code in CARD_PROVENANCE_CODES:
        block = logic.find_block(model, code)
        badges = block.get("badges") or []
        placeholders = [b for b in badges if b.get("_placeholder") and b.get("_kind") in ("來源", "新鮮度")]
        if not placeholders:
            continue
        kept = [b for b in badges if b not in placeholders]
        block["badges"] = kept + [{"_kind": "來源", "_tone": "中性", "_not_applicable": True,
                                   "text": TEXT_CARD_PROVENANCE_NA}]
        count += 1
    return count


# ───────────── BL-0250 批次 3-B：「對照」「觀察清單」兩份多選清單、結果清單每列的來源展開（44 第七節第三小節之十三） ─────────────
# 客戶 2026-10-19 批次 3 裁示（`DEC-2026-10-19-05`；線框第六版 4.5、4.4、待裁示 (5b) 推薦案）。只給正式模式（`page._render_exp2_live`）；
# 示範模式不經過本段，照舊每列兩組勾選框。純函式：讀 `logic`／`plain`／`symbols`／`health` 已經改完字的模型，不改模型、不取數、不寫入。
#
# - 兩份多選清單取代每列兩組勾選框（之七其二第 5 條已授權）：選項＝目前結果清單的檔、順序同結果清單、不預先選任何一檔；
#   兩份各自獨立；「對照」同時最多 3 檔（上限照 `logic.COMPARE_LIMIT`）；「觀察清單」不受上限拘束。勾選狀態照舊只存在
#   `logic.checked_key` 那一份 session 狀態，存檔路徑（`exp5_save_entries`）一字未改。
# - 每列展開只放來源資訊（客戶裁示第 5 點第三項：僅限來源資訊）：該列各格已畫出的來源標示與滑鼠提示，拆成
#   「欄位｜來源｜取得時間（台北時間）｜資料日期｜備註」一張小表；格內的來源標示與滑鼠提示照舊（線框第 11 節：格內來源名先保留）。
#   拆法只認本檔自己寫出滑鼠提示的那兩個段首（`_nav_tip` 的「取得時間：」與「資料日期：」），其餘段落原樣放進備註，不改寫、不刪。

PICK_GROUPS = (logic.GROUP_COMPARE, logic.GROUP_WATCH)
PICK_LABELS = {
    logic.GROUP_COMPARE: f"要對照的基金（最多 {logic.COMPARE_LIMIT} 檔）",
    logic.GROUP_WATCH: "要加入觀察清單的基金",
}
PICK_PLACEHOLDER = "選擇基金"
PICK_CAPS = {logic.GROUP_COMPARE: logic.COMPARE_LIMIT, logic.GROUP_WATCH: None}
TEXT_PICK_COUNT = "已選 {n}／{cap}"
# 選滿時那一行沿用現行字（線框第六版 4.5 互動規則 4；字面與 `logic` 第 4 個勾選框的停用原因同一句）。
TEXT_PICK_FULL = f"同時最多對照 {logic.COMPARE_LIMIT} 檔"
TEXT_WATCHED_SUFFIX = f"（{logic.TEXT_ALREADY_WATCHED}）"
PICK_NAME_SEP = "　"

ROW_SOURCE_TITLE = "來源與取得時間"
ROW_SOURCE_LABELS = ("欄位", "來源", "取得時間（台北時間）", "資料日期", "備註")
ROW_SOURCE_NONE = "—"
_TIP_SEP = "；"
_TIP_FETCHED = "取得時間："
_TIP_DATA_DATE = "資料日期："


def pick_options(block: dict) -> list:
    """多選清單的選項：`EXP-2` 目前畫出的每一列的基金代碼，順序同結果清單（不另外排序）。"""
    return [row["_fund_code"] for row in block.get("_rows") or ()]


def _row(block: dict, code: str):
    return next((row for row in block.get("_rows") or () if row["_fund_code"] == code), None)


def already_watched(block: dict, code: str) -> bool:
    """該檔已在已存的觀察清單裡（`logic` 掛在「觀察清單」那一組的註記；本函式不另判）。"""
    row = _row(block, code)
    box = ((row or {}).get("_checkboxes") or {}).get(logic.GROUP_WATCH) or {}
    return box.get("note") == logic.TEXT_ALREADY_WATCHED


def pick_label(block: dict, code: str, group: str) -> str:
    """選項文字「代碼　基金名」：基金名取結果清單上那一格（畫出來、而且是值的那一格）；那一格沒有值（缺、失敗、或欄被隱藏）
    就只寫代碼，不猜名稱。「觀察清單」那一份，已在觀察清單的檔加註「（已在觀察清單）」。"""
    row = _row(block, code) or {}
    cell = (row.get("_cells") or {}).get("fund_name") or {}
    name = cell.get("text") if cell.get("_state") == logic.STATE_OK else None
    label = f"{code}{PICK_NAME_SEP}{name}" if name else code
    if group == logic.GROUP_WATCH and already_watched(block, code):
        label += TEXT_WATCHED_SUFFIX
    return label


def merge_picks(previous, visible, picked) -> tuple:
    """多選清單改了之後的勾選狀態：清單上看得到的檔照多選清單；看不到的檔（例：條件改了、不在本次結果裡）原樣留著。
    與每列勾選框一格一格切換的結果相同（`logic.toggle_checked` 只動被按的那一檔）。回排序過的 tuple。"""
    visible = set(visible)
    return tuple(sorted({code for code in previous or () if code not in visible} | set(picked or ())))


def shown_picks(checked, options) -> list:
    """畫多選清單時要先放進去的已選項：勾選狀態裡、而且在本次選項裡的檔，順序同選項。"""
    checked = set(checked or ())
    return [code for code in options if code in checked]


def pick_captions(group: str, count: int) -> list:
    """多選清單下方的說明行。「對照」：已選幾檔／上限；選滿時加一行沿用的上限句。「觀察清單」：沒有。"""
    cap = PICK_CAPS[group]
    if cap is None:
        return []
    lines = [TEXT_PICK_COUNT.format(n=count, cap=cap)]
    if count >= cap:
        lines.append(TEXT_PICK_FULL)
    return lines


def taipei_time_text(raw) -> str:
    """取得時間（資料層原值，ISO 8601）→「YYYY-MM-DD HH:MM」台北時間。讀不懂、或沒有時區 → 原樣（不猜時區、不補值）。"""
    text = str(raw)
    try:
        when = datetime.fromisoformat(text.replace("Z", "+00:00") if text.endswith("Z") else text)
    except ValueError:
        return text
    if when.tzinfo is None:
        return text
    return when.astimezone(TAIPEI).strftime("%Y-%m-%d %H:%M")


def split_tip(tip) -> tuple:
    """一格的滑鼠提示 → (取得時間原值或 None, 資料日期或 None, 備註)。只拿掉「取得時間：」「資料日期：」兩種段落
    （各取第一段），其餘段落依原順序以「；」接回備註，一個字不改。"""
    fetched = day = None
    rest = []
    for part in str(tip).split(_TIP_SEP) if tip else ():
        if fetched is None and part.startswith(_TIP_FETCHED):
            fetched = part[len(_TIP_FETCHED):]
        elif day is None and part.startswith(_TIP_DATA_DATE):
            day = part[len(_TIP_DATA_DATE):]
        else:
            rest.append(part)
    return fetched, day, _TIP_SEP.join(rest)


def source_rows(block: dict, row: dict) -> list:
    """一列的來源展開：`[(欄位, 來源, 取得時間（台北時間）, 資料日期, 備註), ...]`，依結果清單的欄序。
    只列有來源資訊（來源標示或滑鼠提示）的格；一格都沒有 → 空清單（那一列不畫展開）。缺的那一格寫「—」。"""
    out = []
    labels = dict(zip(block.get("column_keys") or (), block.get("column_labels") or ()))
    for key in block.get("column_keys") or ():
        cell = (row.get("_cells") or {}).get(key) or {}
        tag, tip = cell.get("source_tag"), cell.get("source_tip")
        if not tag and not tip:
            continue
        fetched, day, note = split_tip(tip)
        out.append((
            labels.get(key, key),
            tag or ROW_SOURCE_NONE,
            taipei_time_text(fetched) if fetched else ROW_SOURCE_NONE,
            day or ROW_SOURCE_NONE,
            note or ROW_SOURCE_NONE,
        ))
    return out
