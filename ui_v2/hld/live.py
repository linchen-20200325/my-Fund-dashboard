# -*- coding: utf-8 -*-
"""持倉體檢**正式模式**才有的呈現層調整（純函式；不 import streamlit、不 import 舊樹、不 import fixtures）。

依據：客戶 2026-10-02 裁示的 `docs/wireframes/draft_hld_live.html` §G，以及客戶 2026-10-02 裁示 A（按鈕文案）。
體例照 `ui_v2/alo/live.py`、`ui_v2/set/live.py`：示範模式（`ui_v2/app_hld.py`）不經過本檔，一個字都不變。

本輪（hld 接真資料 S3）只做呈現層骨架，**不接任何取數**：
1. **「（示意）」全部拿掉**（裁示 2-A）—— 由 `logic.build_page_model(demo_hint=False)` 組模型時就不接，
   不是事後去字串裡刪（事後刪會連資料本身的字一起刪，那是改資料）。
2. **對帳時間欄**（裁示 4-C）—— HLD-5 展開欄位「最後對帳」改名「最後核對日（只記日期）」，值只留台灣日期；
   值不合格的那一格進 `系統錯誤`，整頁照常（S3 第二輪）。
3. **按鈕停用**（裁示 A，文案逐字）—— 「存檔」與「重新取數」停用並寫出原因。
   按鈕**出現在哪幾塊**一格不動，沿用 `logic` 既有規則（HLD-1／2／3 不掛重新取數；HLD-8 在任一值為
   `資料未備` 或 `系統錯誤` 時掛）；本檔只改已經在那裡的按鈕的啟用狀態，不新增、不拿掉任何一枚。

⛔ 頁面入口 `ui_v2/app_hld_live.py` 與取數 `ui_v2/hld/source.py` 是 S6 的工作，本輪不建。
⛔ 頁首副標（草稿 §E P1／P2：「資料為假資料…」「情境 …」）住在 `page.py::render`，那是入口接線的一部分，
   本輪不動；S6 接 `render(load_live=)` 時照 `ui_v2/alo/page.py` 的做法處理。
   → S6a 已照做：`page.render(load_live=)` 傳入時頁首只印提問句（入口 `app_hld_live.py` 仍是 S6 後半的工作）。

S4（裁示 3-B (ii)）：DIRECT 持倉另外列出、不計入體檢 —— 見 `direct_holding_rows` 與 `_apply_direct`。

S5（裁示 1-A＋1-C）：舊淨值的新鮮度標示 —— 見 `NAV_FRESH_DAYS_YELLOW`、`nav_freshness` 與 `_apply_freshness`。
本輪仍不接取數：`nav_provenance` 由呼叫端傳入。

S6b-2（第一塊）：`user_setting` 三個鍵的解析 —— 見 `parse_user_settings`（體例照 `ui_v2/alo/live.py`）。
S6b-2（第二塊）：L2 輸出 → `load_live` 回傳值的組裝 —— 見 `assemble_live_load`。

⚠️ 文案逐字照裁示；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
"""

from __future__ import annotations

import copy
import json
import math
import re
from datetime import date, datetime, timedelta, timezone

from . import logic

# 客戶 2026-10-02 裁示 A，逐字。⛔ 不准加字、不准補「請……」之類指示動作的句子。
# 「存檔」那一句與 `ui_v2/alo/live.py::SAVE_DISABLED_REASON` 逐字相同（本套件不 import ui_v2.alo，
# 兩份由 tests/ui_v2/test_hld_live_logic.py 逐字比對）。
SAVE_DISABLED_REASON = "存檔寫入端尚未接上，這一輪只讀不寫"
REFETCH_DISABLED_REASON = "重新取數尚未接上"

# 哪一類按鈕停用、原因是哪一句。以 `logic` 的按鈕類別（`44` 5.3）判，不以標籤字面判。
_DISABLED_BY_KIND = {
    "存檔": SAVE_DISABLED_REASON,
    "取數": REFETCH_DISABLED_REASON,
}

# 裁示 4-C：欄名逐字。舊欄名是 `logic._build_hld5` 的字面。
OLD_SYNC_LABEL = "最後對帳"
SYNC_LABEL = "最後核對日（只記日期）"


# 台灣日期用的時區（UTC+8）。
# ⚠️ 本套件不得 import `services`（`tests/ui_v2/test_ui_v2_live_import_guard.py` 第 (5) 條：
#    舊樹只准 `source.py` import），也不 import 別頁的 `ui_v2.alo`／`ui_v2.set`（各頁自足），
#    所以這裡另寫一份。出處：`services/v2_tables/nav_dividend.py::MARKET_DATE_TZ`（同值，L2 判未來日期用）；
#    同型的另兩份是 `ui_v2/alo/logic.py::DISPLAY_TZ` 與 `ui_v2/set/logic.py::DISPLAY_TZ`。
MARKET_DATE_TZ = timezone(timedelta(hours=8))

# `re.ASCII`：`\d` 只認 0～9。不加的話全形數字、阿拉伯-印度數字也算 `\d`，
# 擋不擋得下就變成看後面的 `fromisoformat` 收不收（S3 第三輪，規格組建議 1：讓正則自己負責）。
_DATE_ONLY = re.compile(r"\d{4}-\d{2}-\d{2}", re.ASCII)
# 日期時間：前 10 個字是 `YYYY-MM-DD`，第 11 個字是 `T` 或空白，接著至少到「時:分」。
# 先過這一關再交給 `datetime.fromisoformat` —— 3.11 的 `fromisoformat` 也收 `20260919`、`2026-W38-6`
# 這類寫法，那些不是本欄約定的形狀，一律不收。
_DATETIME_HEAD = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}", re.ASCII)


# ───────────────────────── 裁示 3-B (ii)：DIRECT 持倉另列 ─────────────────────────
# 出處：`docs/wireframes/draft_hld_live.html` §F 選項 3-B（文案原文、放在哪、什麼顏色、先定義 N）
#       與 §G 第 3 題、第 3a 題（客戶 2026-10-02 裁示：3-B，字面用 (ii)）。字面逐字，改字先回草稿。
#
# ⛔ **本檔不判定誰是 DIRECT。** 判定只有一處：L2 `services/v2_tables/alo_holdings.py::load_alo_tables`
#    （`_key_text(policy_id) == contract.DIRECT_POLICY_ID`）—— alo 頁吃的就是同一次判定的產物：
#    DIRECT 持倉**不產生 `holding` 列**（所以本頁每一塊的數字本來就不含它），另交一份 `direct` 清單。
#    本頁依 `tests/ui_v2/test_ui_v2_live_import_guard.py` 第 (2)(5) 條不得 import `services`，
#    所以 L2 的三個值由呼叫端（S6 的 `source.py`）以參數傳進來，本檔不另寫一份字面：
#    - `direct_policy_id`：`contract.DIRECT_POLICY_ID` —— 只拿來**驗** `holding` 裡沒有 DIRECT 列（S4 第二輪 M2）；
#    - `direct_sources`：L2 `direct` 清單合法的三種 `source`（`TAB_PROFILE`、`TAB_SUPPLEMENT`、`POLICY_TAB`）；
#    - `policy_tab_source`：`alo_holdings.POLICY_TAB` —— N 只數這一種。
DIRECT_EXCLUDED_TEXT = "⚠ DIRECT 列暫不支援，該筆不計入體檢（{n} 筆）"   # 黃
DIRECT_LOCATION_TEXT = "{tab} 第 {row} 列"                                # 灰，一行一筆
DIRECT_SUMMARY_SUFFIX = " · DIRECT {n} 筆未列入"                          # 收合時摘要尾端（有持倉時）
DIRECT_SUMMARY_ONLY = "DIRECT {n} 筆未列入"                               # HLD-5 摘要（持倉全空時，S4 第二輪 M1）

# 持倉全空而 N＞0 時（S4 第二輪 M1、第三輪 1，總管裁定）：`logic` 寫出「尚未建立任何持倉」的出口，**依位置**列名。
# 只換下表點名的（塊、欄位）；欄位是 list 時，只換那一欄裡**整行等於** `logic` 模板的那幾行。
# 上游的錯誤原文、保單名、分頁名一律不碰 —— 它們不住在這些位置（`HLD-1` 的上游原文住在
# `_placeholder.reason_text`，不在表內），即使剛好含那幾個字也照印。
# ⚠️ 第二輪是「整個模型裡值相等就換」＋「換完還找得到就 raise」：前者會連上游原文一起換，
#    後者會因上游原文含那幾個字而整頁失敗（第三輪紅隊 J1）。兩者都已拿掉，改由測試守住
#    「表沒漏列出口」（`test_hld_live_logic.py` 的組合測試）。
#   模板 A 恰為 `TEXT_NO_HOLDING`；模板 B `f"{ND_TEXT}：{TEXT_NO_HOLDING}"`；
#   模板 C `f"（另：{TEXT_NO_HOLDING}。{TEXT_SHEETS_READONLY}）"`。
_EMPTY_EXITS = (
    ("HLD-0", "text"),            # A
    ("HLD-0", "summary_text"),    # A
    ("HLD-0", "lines"),           # C（紅燈時的括號補述）
    ("HLD-1", "summary_text"),    # A
    ("HLD-1", "detail_lines"),    # A
    ("HLD-2", "summary_text"),    # A
    ("HLD-2", "detail_lines"),    # A
    ("HLD-3", "summary_text"),    # A
    ("HLD-3", "detail_lines"),    # A
    ("HLD-8", "summary_text"),    # B
    ("HLD-8", "detail_lines"),    # A
)
# HLD-5 另辦：摘要整句換成 `DIRECT_SUMMARY_ONLY`，`_HLD5_EMPTY_LINE` 那一行拿掉（不是換字）。
_HLD5_EMPTY_LINE = f"{logic.TEXT_NO_HOLDING}，沒有可以展開的檔。"


def _empty_replacements(warning: str) -> dict:
    nh = logic.TEXT_NO_HOLDING
    return {
        nh: warning,
        f"{logic.ND_TEXT}：{nh}": f"{logic.ND_TEXT}：{warning}",
        f"（另：{nh}。{logic.TEXT_SHEETS_READONLY}）": f"（另：{warning}。{logic.TEXT_SHEETS_READONLY}）",
    }


def _replace_exits(model: dict, warning: str) -> None:
    table = _empty_replacements(warning)
    for code, field in _EMPTY_EXITS:
        block = logic.find_block(model, code)
        value = block.get(field)
        if isinstance(value, str):
            block[field] = table.get(value, value)
        elif isinstance(value, list):
            block[field] = [table.get(line, line) if isinstance(line, str) else line for line in value]


def _require_text(value, name: str) -> str:
    if not isinstance(value, str):
        raise TypeError(f"{name} 應為字串：{value!r}")
    if not value.strip():
        raise ValueError(f"{name} 是空字串：{value!r}")
    return value


def direct_holding_rows(direct, *, policy_tab_source, direct_sources) -> list:
    """L2 `direct` 清單 → 只留保單分頁那一種（草稿 §F 3-B「先定義 N」：N 只數 `source` 為 `POLICY_TAB` 的列）。

    `_保單資料` 的 DIRECT 列是保單資料、不是持倉；`_持倉補充` 的 DIRECT 列與保單分頁那一列可能是
    同一筆持倉，一起數會數兩次 —— 兩種一律不數。
    **每一筆都驗，不只保單分頁那一種**（S4 第二輪 J1／J2）；不合格一律 raise，不略過、不去重：
    - `direct` 不是 list／tuple、元素不是 dict → TypeError；
    - 缺 `source` 鍵、`source` 不在 `direct_sources` 裡 → ValueError（認不得的來源不能默默不數）；
      `source` 不是字串（含 list、dict 這類不可雜湊的）→ TypeError，先驗型別再查集合（第三輪建議 3）；
    - `tab` 不是字串 → TypeError；空白、前後有空白、含換行 → ValueError，不 strip（第三輪建議 2）；
      `row` 不是正整數（含 `bool`）→ ValueError；
    - 同一筆（`source`、`tab`、`row` 都相同）出現兩次 → ValueError。
    """
    if not isinstance(direct, (list, tuple)):
        raise TypeError(f"direct 應為 list 或 tuple：{type(direct).__name__}")
    _require_text(policy_tab_source, "policy_tab_source")
    if not isinstance(direct_sources, (set, frozenset, list, tuple)):
        raise TypeError(f"direct_sources 應為集合：{type(direct_sources).__name__}")
    sources = {_require_text(v, "direct_sources 的元素") for v in direct_sources}
    if policy_tab_source not in sources:
        raise ValueError(f"policy_tab_source {policy_tab_source!r} 不在 direct_sources 裡")
    rows, seen = [], set()
    for index, entry in enumerate(direct):
        where = f"DIRECT 清單第 {index} 筆"
        if not isinstance(entry, dict):
            raise TypeError(f"{where}應為 dict：{entry!r}")
        if "source" not in entry:
            raise ValueError(f"{where}缺 source：{entry!r}")
        source = entry["source"]
        if not isinstance(source, str):
            raise TypeError(f"{where}的 source 應為字串，收到 {type(source).__name__}：{entry!r}")
        if source not in sources:
            raise ValueError(f"{where}的 source 認不得：{entry!r}")
        tab, row = entry.get("tab"), entry.get("row")
        if not isinstance(tab, str):
            raise TypeError(f"{where}的 tab 應為字串，收到 {type(tab).__name__}：{entry!r}")
        if not tab.strip():
            raise ValueError(f"{where}的 tab 是空白：{entry!r}")
        if tab != tab.strip() or "\n" in tab or "\r" in tab:
            raise ValueError(f"{where}的 tab 前後有空白或含換行：{entry!r}")
        if isinstance(row, bool) or not isinstance(row, int) or row <= 0:
            raise ValueError(f"{where}的 row 不是正整數：{entry!r}")
        key = (source, tab, row)
        if key in seen:
            raise ValueError(f"{where}重複（同一 source、tab、row）：{entry!r}")
        seen.add(key)
        if source == policy_tab_source:
            rows.append({"tab": tab, "row": row})
    return rows


def _check_no_direct_holding(dataset: dict, direct_policy_id: str) -> None:
    """`holding` 裡出現 DIRECT 列 → raise（S4 第二輪 M2，總管裁定）。

    L2 不為 DIRECT 產生 `holding` 列；真出現了，表示上游壞了 —— 照畫的話，同一筆會一邊被算進各塊、
    一邊在卡尾被說「不計入」。比對時去掉前後空白（與 L2 `_key_text` 同向，寧嚴勿寬）。
    """
    for holding in dataset.get("holding") or ():
        pid = holding.get("policy_id")
        if isinstance(pid, str) and pid.strip() == direct_policy_id:
            raise ValueError(f"holding 裡有 DIRECT 列（應由 L2 排除）：{holding.get('holding_id')!r}")


def _apply_direct(model: dict, rows: list, *, has_holdings: bool, holding_failed: bool = False) -> dict:
    """HLD-5 卡尾一行黃字＋逐筆位置（灰），收合摘要加 DIRECT 筆數；持倉全空時另把「尚未建立任何持倉」換掉。

    N＝0 時什麼都不加（草稿與 alo 都沒寫 N＝0 的畫法；本組的處理，已回報待裁）。
    各塊的 `_state`／`_tone`、按鈕都不動：這幾筆是「讀到了、照裁示不計入」，不是哪一塊算不出來。
    📌 2026-10-05「讀取失敗不說空」（總管 2026-10-05 裁定：不 raise，只加卡尾）：`holding_failed`
    ＝持倉表有取數失敗、而且一列也沒有讀到（例：部分分頁讀不到，見 `assemble_live_load`）。
    這時只加卡尾 —— HLD-5 的摘要與說明區是讀取失敗的原文，不換；`logic` 也不會寫出「尚未建立任何持倉」，
    沒有出口可換，所以不呼叫 `_replace_exits`。
    """
    if not rows:
        return model
    n = len(rows)
    warning = DIRECT_EXCLUDED_TEXT.format(n=n)
    hld5 = logic.find_block(model, "HLD-5")
    if has_holdings:
        hld5["summary_text"] = hld5["summary_text"] + DIRECT_SUMMARY_SUFFIX.format(n=n)
    elif not holding_failed:
        if _HLD5_EMPTY_LINE not in hld5["detail_lines"]:
            raise ValueError(f"HLD-5 空持倉的說明行「{_HLD5_EMPTY_LINE}」不在，logic 改了而本檔沒跟上")
        hld5["summary_text"] = DIRECT_SUMMARY_ONLY.format(n=n)
        hld5["detail_lines"] = [line for line in hld5["detail_lines"] if line != _HLD5_EMPTY_LINE]
    hld5["tail_notes"] = [{"text": warning, "_tone": "黃"}] + [
        {"text": DIRECT_LOCATION_TEXT.format(tab=r["tab"], row=r["row"]), "_tone": "灰"} for r in rows
    ]
    if has_holdings or holding_failed:
        return model
    _replace_exits(model, warning)
    return model


# ───────────────────────── 裁示 1-A＋1-C：舊淨值的新鮮度標示（S5） ─────────────────────────
# 出處：`docs/wireframes/draft_hld_live.html` §D（「N 的算法」那一列、選項 1-A、選項 1-C、選項 1-A＋1-C）
#       與 §G 第 1 題、第 1a 題（客戶 2026-10-02 裁示：1-A＋1-C，黃燈門檻 10 天）。字面逐字，改字先回草稿。
#
# 黃燈門檻：N（台灣今天的日期減該檔最後一筆 `nav_date`，日曆日）大於這個數 → 黃；小於或等於 → 中性。
# 客戶 2026-10-02 裁示（草稿 §G 第 1a 題），客戶要求註明的原話：
#   「門檻 10 天，非 44 規定，是本輪依長假實況訂的」
# 客戶理由（同處）：7 天遇到春節等長假，所有基金都會被誤標黃燈；使用者習慣忽略黃燈後，真正落後的反而看不到。
# ⛔ 不沿用 `shared/signal_thresholds.py::MJ_FRESH_DAYS_YELLOW`（那是 7，管的是 L2 `stale`，算法也不同）——
#    草稿 §D：「實作時要另設一個常數放 10，不要沿用 MJ_FRESH_DAYS_YELLOW」。
NAV_FRESH_DAYS_YELLOW = 10

FRESHNESS_TODAY_TEXT = "當日"                      # 1-A：N＝0（`44` §5.2 新鮮度字面）
FRESHNESS_DELAY_TEXT = "延遲 {n} 日"               # 1-A：N≥1（`44` §5.2 新鮮度字面）
CACHE_NOTE_OLD = "⚠ 淨值取自預存序列，不是本次取得；最近一筆 {day}，已超過 {limit} 日"   # 1-C ①，黃
CACHE_NOTE_FRESH = "淨值取自預存序列，不是本次取得；最近一筆 {day}"                       # 1-C ②，中性
CACHE_TAIL_TEXT = "本卡所列的檔中，{n} 檔的淨值取自預存序列，逐檔見 HLD-6"               # 1-C ③
CACHE_INPUT_SUFFIX = " · 預存序列"                                                       # 1-C：HLD-7 輸入欄尾端

# L2 `services/v2_tables/nav_dividend.py::rows_from_nav_series` 的 `provenance` 鍵（`build_nav_table` 回傳的
# `provenance[fund_code]`）。本頁不得 import `services`，所以由呼叫端原樣傳進來，本檔只驗形狀、只讀這兩個鍵。
_PROVENANCE_KEYS = ("cache_fallback", "stale")


def _nav_day(value, where: str) -> date:
    """`nav_date` → `date`。只收 `YYYY-MM-DD` 字串（假資料與 `logic` 的寫法）或 `date`（L2 的寫法）；
    `datetime`、其他字串、其他型別一律 raise —— 不交給誰去猜。"""
    if isinstance(value, datetime):
        raise TypeError(f"{where}的 nav_date 是 datetime，日期語意不明：{value!r}")
    if isinstance(value, date):
        return value
    if isinstance(value, str) and _DATE_ONLY.fullmatch(value):
        try:
            return date.fromisoformat(value)
        except ValueError:
            pass
    raise ValueError(f"{where}的 nav_date 不是 YYYY-MM-DD：{value!r}")


def _check_provenance(code: str, entry) -> dict:
    where = f"nav_provenance[{code!r}]"
    if not isinstance(entry, dict):
        raise TypeError(f"{where} 應為 dict：{entry!r}")
    missing = [k for k in _PROVENANCE_KEYS if k not in entry]
    if missing:
        raise ValueError(f"{where} 缺 {missing!r}：{entry!r}")
    fallback, stale = entry["cache_fallback"], entry["stale"]
    if not isinstance(fallback, bool):
        raise TypeError(f"{where} 的 cache_fallback 應為 bool：{fallback!r}")
    # L2：不是預存那一支 → `stale` 為 None；是預存那一支 → 取 `nav_quality["stale"]`（bool）或 None。
    if stale is not None and not isinstance(stale, bool):
        raise TypeError(f"{where} 的 stale 應為 bool 或 None：{stale!r}")
    if not fallback and stale is not None:
        raise ValueError(f"{where} 不是預存那一支，stale 卻不是 None（與 L2 不符）：{entry!r}")
    return entry


def nav_freshness(dataset: dict, nav_provenance, *, today: date) -> dict:
    """每一檔 → `{"days", "last", "cache_fallback", "badge", "note"}`（草稿 §D 1-A＋1-C）。

    - 只算**淨值表裡有列、而且淨值沒有取數失敗**的檔（表層級 `errors["nav"]` 或逐檔 `fund_errors["nav"]`）：
      那幾檔的值已經是 ⛔，再掛「延遲 N 日」等於說淨值還在（S2 的 ⛔ 與本輪的徽章不得打架）。
      沒有列的檔 N 算不出來，草稿沒寫畫法 —— 不掛、不補字（已回報）。
    - N ＝ `today`（台灣今天的日期）減該檔最後一筆 `nav_date`，日曆日；**不讀 `stale`**（草稿 §D：
      `stale` 為假不等於不舊、為空不等於判不出，各選項一律不吃它）。`stale` 只驗形狀。
    - 最後一筆晚於 `today`（N＜0）→ raise：L2 不寫未來日期，真出現了是上游或時鐘壞了。
    - 要算的檔在 `nav_provenance` 裡沒有一筆 → raise（判不出是不是預存的，不猜）。
    """
    if nav_provenance is None:
        raise ValueError("沒有給 nav_provenance，無法判定淨值是否取自預存序列")
    if not isinstance(nav_provenance, dict):
        raise TypeError(f"nav_provenance 應為 {{fund_code: provenance}}：{type(nav_provenance).__name__}")
    if isinstance(today, datetime) or not isinstance(today, date):
        raise TypeError(f"today 應為 date：{today!r}")
    for code in nav_provenance:
        if not isinstance(code, str) or not code:
            raise TypeError(f"nav_provenance 的鍵應為非空字串：{code!r}")
    if dataset.get("errors", {}).get("nav"):
        return {}
    failed = set(logic.fund_errors(dataset).get("nav", {}))
    last: dict = {}
    for index, row in enumerate(dataset.get("nav") or ()):
        code = row["fund_code"]
        day = _nav_day(row["nav_date"], f"nav 第 {index} 列（{code!r}）")
        if code not in last or day > last[code]:
            last[code] = day
    out = {}
    for code in sorted(last):
        if code in failed:
            continue
        if code not in nav_provenance:
            raise ValueError(f"{code!r} 有淨值列，nav_provenance 卻沒有這一檔")
        fallback = _check_provenance(code, nav_provenance[code])["cache_fallback"]
        days = (today - last[code]).days
        if days < 0:
            raise ValueError(f"{code!r} 最後一筆 nav_date {last[code].isoformat()} 晚於今天 {today.isoformat()}")
        old = days > NAV_FRESH_DAYS_YELLOW
        text = FRESHNESS_TODAY_TEXT if days == 0 else FRESHNESS_DELAY_TEXT.format(n=days)
        note = None
        if fallback:
            day_text = last[code].isoformat()
            note = (
                {"text": CACHE_NOTE_OLD.format(day=day_text, limit=NAV_FRESH_DAYS_YELLOW), "_tone": "黃"}
                if old
                else {"text": CACHE_NOTE_FRESH.format(day=day_text), "_tone": "中性"}
            )
            # S5 第二輪（紅隊建議 3）：375px 寬時日期被折成兩行。字面不變，只標出「這一段不斷行」，
            # 由 `page.py::_fresh_note_html` 包成不斷行的一段。
            note["_nowrap"] = [day_text]
        out[code] = {
            "days": days,
            "last": last[code],
            "cache_fallback": fallback,
            "old": old,
            # `44` §5.2 新鮮度徽章：「中性至黃，只映射日數」。
            "badge": {"_kind": "新鮮度", "_tone": "黃" if old else "中性", "text": text},
            "note": note,
        }
    return out


def _apply_freshness(model: dict, fresh: dict) -> dict:
    """把 `nav_freshness` 的結果掛到各塊（草稿 §D 1-A＋1-C「放在哪」）。各塊的 `_state`／`_tone`、按鈕、
    數值都不動：徽章與副標只說「多舊」「是不是預存的」，不改任何一個數（草稿 §D：數值照算、照印）。

    - HLD-2、HLD-3：每一檔分組加 `freshness_badge`（1-A）與 `freshness_note`（1-C ①②，只有預存那幾檔）；
    - HLD-8：每一列同上（1-A「表內每一列」；1-C「該檔標頭下一行」）；
    - HLD-5：每一檔加 `freshness_note`（1-C「該檔展開標頭下」；1-A 不掛在 HLD-5）；
    - HLD-6：`nav_groups` 逐檔分組，分組標頭帶徽章與副標（1-A／1-C「分組標頭」）；
    - HLD-7：預存那幾檔**以淨值為輸入**的列（`logic.NAV_INPUT_INDICATORS`），輸入欄尾端加 `CACHE_INPUT_SUFFIX`；
    - HLD-1：`freshness_tail`（1-C ③），只數出現在本卡列上的檔，排在既有卡尾之後。
    HLD-0 一格不動（草稿 §D「1-D 以外的選項，HLD-0 燈不動」）。
    """
    def badge(code):
        entry = fresh.get(code)
        return copy.deepcopy(entry["badge"]) if entry else None

    def note(code):
        entry = fresh.get(code)
        return copy.deepcopy(entry["note"]) if entry and entry["note"] else None

    for code in ("HLD-2", "HLD-3"):
        for group in logic.find_block(model, code)["fund_groups"]:
            group["freshness_badge"] = badge(group["_fund_code"])
            group["freshness_note"] = note(group["_fund_code"])
    for row in logic.find_block(model, "HLD-8")["_rows"]:
        row["freshness_badge"] = badge(row["_fund_code"])
        row["freshness_note"] = note(row["_fund_code"])
    hld5 = logic.find_block(model, "HLD-5")
    seen = set()
    for item in [*hld5.get("_items", []), *hld5.get("_rows", [])]:
        if id(item) not in seen:
            seen.add(id(item))
            item["freshness_note"] = note(item["_fund_code"])
    hld6 = logic.find_block(model, "HLD-6")
    groups = []
    for row in hld6["nav_rows"]:
        if not groups or groups[-1]["fund_code"] != row["_fund_code"]:
            groups.append(
                {
                    "fund_code": row["_fund_code"],
                    "freshness_badge": badge(row["_fund_code"]),
                    "freshness_note": note(row["_fund_code"]),
                    "rows": [],
                }
            )
        groups[-1]["rows"].append(row)
    hld6["nav_groups"] = groups
    # S5 第二輪（紅隊必修 M1，總管裁定）：尾巴只掛在**以淨值為輸入**的列。
    # 依據是 `logic.NAV_INPUT_INDICATORS` —— `logic._inputs_text` 就是拿它決定輸入欄讀淨值列還是配息列。
    # 配息類三列（含「配息佔淨值比」）與 HLD-1 帶來的「…與門檻的差額」列（`_indicator` 不在名單內）一律不掛。
    for row in logic.find_block(model, "HLD-7")["_rows"]:
        entry = fresh.get(row["_fund_code"])
        if entry and entry["cache_fallback"] and row["_indicator"] in logic.NAV_INPUT_INDICATORS:
            row["inputs_text"] = row["inputs_text"] + CACHE_INPUT_SUFFIX
    hld1 = logic.find_block(model, "HLD-1")
    listed = {row["_fund_code"] for row in hld1["_rows"]}
    cached = sorted(c for c in listed if c in fresh and fresh[c]["cache_fallback"])
    if cached:
        hld1["freshness_tail"] = {
            "text": CACHE_TAIL_TEXT.format(n=len(cached)),
            "_tone": "黃" if any(fresh[c]["old"] for c in cached) else "中性",
        }
    return model


def taiwan_today(now: datetime | None = None) -> date:
    """台灣的今天。`now`：帶時區的當下（測試注入用）；不傳就取當下。

    沒帶時區的 `now` 直接 raise（S3 第三輪，規格組建議 2）：`astimezone` 會把它當成本機時區，
    本機時區是什麼就換算出什麼，等於讓「今天」看機器設定。
    """
    if now is not None and (now.tzinfo is None or now.utcoffset() is None):
        raise ValueError(f"taiwan_today 的 now 沒有時區：{now!r}")
    moment = datetime.now(MARKET_DATE_TZ) if now is None else now
    return moment.astimezone(MARKET_DATE_TZ).date()


def sync_date(raw, *, today: date):
    """`last_synced_at` 原值 → 台灣日期字串 `YYYY-MM-DD`；不合格回 None（S3 第二輪，總管裁定 2）。

    - 只有日期（`YYYY-MM-DD`，且是真的日期，且不晚於 `today`）→ 照原樣；
    - 帶時區的 ISO 日期時間 → 換算成台灣時間（UTC+8）後取日期；
      換算後晚於 `today`（台灣日期）→ 不合格（核對時刻不可能在未來）；
    - 其餘（`None`、非字串、前後有空白、`2026/09/19`、`2026-02-30`、沒帶時區的日期時間、
      前 10 個字合格但後面接了別的東西）→ 不合格。
    - 只有日期而晚於 `today` → 同樣不合格（總管 S3 第二輪補充裁定：同步日不可能在未來）。
    ⚠️ ~~「晚於今天」只檢查換算過的日期時間 —— 裁定只寫了那一支；只有日期的值照原樣顯示。~~
       → 2026-10-02 補充裁定後兩支一致（有意識的更正，不是漏刪；決策者：總管）。
    """
    if not isinstance(raw, str):
        return None
    if _DATE_ONLY.fullmatch(raw):
        try:
            day = date.fromisoformat(raw)
        except ValueError:
            return None
        # 同步日不可能在未來；今天當天照樣合格（總管 S3 第二輪補充裁定）。
        return None if day > today else day.isoformat()
    if not _DATETIME_HEAD.match(raw):
        return None
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if moment.tzinfo is None or moment.utcoffset() is None:
        return None
    try:
        local = moment.astimezone(MARKET_DATE_TZ).date()
    except OverflowError:
        # 0001-01-01 帶正時差、9999-12-31 帶負時差，換算後跑出公元 1～9999 年之外（紅隊 M1）。
        return None
    if local > today:
        return None
    return local.isoformat()


def bad_sync_message(raw) -> str:
    """不合格那一格的訊息本文。外框沿用 `logic.fund_fetch_failed_text`（「⛔ 取數失敗：<代碼>：<訊息>」），
    這裡只寫出是哪一個值不合格，原值照印（`repr`，前後空白看得見）。"""
    return f"{SYNC_LABEL}的值不合格：{raw!r}"


def _walk_buttons(node):
    if isinstance(node, dict):
        if "_action_kind" in node:
            yield node
        for value in node.values():
            yield from _walk_buttons(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_buttons(value)


def _relabel_sync_field(block: dict, *, today: date) -> None:
    """HLD-5「最後對帳」→「最後核對日（只記日期）」，值換成台灣日期；不合格的那一格改成 `系統錯誤` 值節點。

    - 不合格只影響那一格：用 `logic._metric(error=...)` 做成值節點（走既有的值狀態機制，
      `logic.non_ok_value_nodes` 撈得到），原因行用既有模板 `logic.fund_fetch_failed_text` 寫進本塊說明區，
      尾端補一次 `logic.PRINT_AS_IS_LINE`（與核心卡同一個寫法）。
    - 原因行寫出是哪一張保單（S3 第三輪，紅隊 J2）：同一代碼可以掛在兩張保單下（`44` 4.1 一列＝一組
      `policy_id`＋`fund_code`），只寫代碼就分不出是哪一列。保單取**同一列展開欄位「保單」那一格的字**
      （保單名稱；`DIRECT` 為「直接持有」）—— 那是使用者在同一列上看得到的字，不另造一個識別碼。
      ⚠️ **一列一行、不去重**：`logic._fund_error_lines` 依字串去重，兩張保單的值與保單名都一樣時會合成一行，
      所以這裡不用它。
    - 塊層 `_state` 不動；`_tone` 在有 ⛔ 的值時為紅（比照 S2 裁定 7，`logic._block_tone_with_errors`；
      S3 第三輪，紅隊 J3）。⚠️ 現行 `page.py::_render_hld5` 只畫收合列，**沒有畫本塊的邊框**，所以這一項只改模型。
    - 找不到舊欄名就 raise（總管裁定 4）：那表示 `logic._build_hld5` 改了欄名、本檔沒跟上，
      靜默略過的話，正式畫面上會留一格沒驗過、沒換算的原值。
    - `_items` 與 `_rows` 在 `logic._build_hld5` 是同一份清單，但本檔不靠這個巧合：
      兩個鍵都走，以物件身分去重，同一列只處理一次。
    """
    seen = set()
    error_nodes = []
    for item in [*block.get("_items", []), *block.get("_rows", [])]:
        if id(item) in seen:
            continue
        seen.add(id(item))
        hits = [i for i, (label, _) in enumerate(item["_fields"]) if label == OLD_SYNC_LABEL]
        if len(hits) != 1:
            raise ValueError(
                f"HLD-5 {item.get('_holding_id')!r} 的展開欄位裡「{OLD_SYNC_LABEL}」有 {len(hits)} 格，應為 1 格"
            )
        fields = list(item["_fields"])
        raw = fields[hits[0]][1]
        shown = sync_date(raw, today=today)
        if shown is None:
            node = logic._metric(
                None, text="", ccy=None, error=bad_sync_message(raw), label=SYNC_LABEL, fund_scoped=True
            )
            policy_text = dict(item["_fields"])["保單"]
            error_nodes.append((item["_fund_code"], policy_text, node))
            fields[hits[0]] = (SYNC_LABEL, node)
        else:
            fields[hits[0]] = (SYNC_LABEL, shown)
        item["_fields"] = fields
    lines = [
        logic.fund_fetch_failed_text(code, f"{policy_text}：{node['reason_text']}")
        for code, policy_text, node in error_nodes
    ]
    if lines:
        lines.append(logic.PRINT_AS_IS_LINE)
        block["_tone"] = logic._block_tone_with_errors(block["_state"], [node["_state"] for *_, node in error_nodes])
    block["detail_lines"] = list(block["detail_lines"]) + lines


# S6a：畫面上交代開發過程的子句，正式模式不顯示（總管 S6a 第二輪裁定：**只刪不加**）。
# 每一列：（塊、欄位、原字串、刪減後的字串、是否一定出現、刪掉的那一段裡挑一小段當殘留檢查）。
# - 只刪「交代開發過程」的子句，留下的字一律不改、不新增；標點只做讓句子成立的最小調整。
#   ⇒ 刪減後的字串必須是原字串的**子序列**（`tests/ui_v2/test_hld_live_logic.py` 守住）。
# - 體例：`ui_v2/set/live.py` 的 `_DEMO_LINES`／`_strip_demo`（逐字比對整行，比對不到就不碰），
#   再加上本檔 `_apply_direct` 對 `_HLD5_EMPTY_LINE` 的做法（該在而不在就 raise）。
# - 「〔配息長條〕照畫 · 本輪以佔位框代替，不畫真圖」（HLD-5 佔位框）總管裁定**保留**：圖表確實還沒做，是真實資訊。
_DEV_TRIMS = (
    # a：只刪「已依客戶 2026-09-22 裁定」。
    ("HLD-2", "detail_lines", logic.HLD2_MOVED_NOTE,
     "第三個值「最大回撤」移到層 4 的 HLD-8。", True, "2026-09-22"),
    # b：同 a。
    ("HLD-3", "detail_lines", logic.HLD3_MOVED_NOTE,
     "第三個值「本金類配息佔比」移到層 4 的 HLD-8。配息類別未知的列仍計入期間配息合計。", True, "2026-09-22"),
    # c：刪「客戶 2026-09-22 裁定核心卡各留兩個主值，第三個值移到這一層」；前面的「；」與後面的「。」併成一個「。」。
    #    沒有持倉時 `logic._build_hld8` 整組說明區換掉、不印這一句 ⇒ 不是一定出現，字面漂移靠殘留檢查擋。
    ("HLD-8", "detail_lines", logic.HLD8_DETAIL_NOTE,
     "這兩個值原本各是績效與風險卡、配息與本金卡的第三個值。"
     "兩個值都是比率，逐檔仍寫出幣別字面值，本表沒有任何跨幣別的合計、平均或比值。", False, "2026-09-22"),
    # e：刪「兩句同時成立時哪一句出現，規格沒有寫」。只有空持倉且門檻未設時才出現。
    ("HLD-0", "lines", logic.HLD0_NO_RULES_ASIDE, "（另：尚未設定門檻。）", False, "規格沒有寫"),
    # S6a 第四輪（規格組必修 2／紅隊 J1，總管裁定）：不是開發過程字句，但同一體例（只刪不加）。
    # 正式版「存檔」停用，「兩枚按鈕並存，各做一件事。」這一句是假的 ⇒ 只刪這一句，後面講「套用」的照留。
    ("HLD-4", "notes", logic.HLD4_APPLY_NOTE,
     "「套用」只讀這些欄位的當下值、重算 HLD-1、HLD-2、HLD-3、HLD-5、HLD-7、HLD-8 六塊，"
     "不寫任何資料表、不改欄位的內容。", True, "兩枚按鈕並存"),
)


# S6b-1（T1）：上游錯誤原文進說明區的唯一入口是 `logic.fetch_failed_text`，以這一段開頭。
# 取自 logic 本身（不另抄字面）：logic 改模板時這裡跟著變。
_ERROR_LINE_PREFIX = logic.fetch_failed_text("")


def _is_upstream_error_line(line: str) -> bool:
    """這一行是 logic 用 `fetch_failed_text` 包起來的上游錯誤原文（資料，不是範本）。"""
    return line.startswith(_ERROR_LINE_PREFIX)


def _strip_dev_lines(model: dict) -> None:
    """把 `_DEV_TRIMS` 的原字串整行換成刪減後的版本（逐字比對，其餘行不碰）。

    - 一定出現的那幾句找不到 → raise：`logic` 改了字面而本檔沒跟上，靜默略過的話那一句會原封上正式畫面；
    - 換完之後該欄位還有任何一行**範本行**含殘留檢查那一小段 → raise（條件出現的那一句也靠這一條防字面漂移）。
      只查本表點名的（塊、欄位），不掃整個模型。
      ~~上游錯誤原文不住在這些位置（同 `_EMPTY_EXITS` 的理由）。~~
      → **S6b-1 更正（有意識的更正，不是漏刪；決策者：總管）**：上句是假的 —— `logic._build_core_card`
        回 `"detail_lines": detail_lines + error_lines`、`_build_hld8` 接 `_fund_error_lines`、
        `conclusion_light` 的 `lines` 帶 `HLD-1` 卡尾的逐檔失敗行，**上游錯誤原文就住在這些位置**；
        錯誤訊息裡碰巧有「2026-09-22」「規格沒有寫」時，舊寫法會把資料當成殘留而 raise（T1）。
      ⇒ 殘留檢查**只看 logic 自己產生的範本行**：上游**錯誤原文**只經 `logic.fetch_failed_text` 進這些欄位
        （`fund_fetch_failed_text` 也走它），那種行以 `_ERROR_LINE_PREFIX` 開頭，略過不查。
        其餘行照查 —— logic 改了字面而本檔沒跟上時照樣 raise。
        ⚠️ 第二輪補精確：「其餘行」不全是純範本字面 —— `HLD-0` 的 `lines` 另會從 `HLD-1` 帶進
        `⬜ 資料未備：<來源鍵> 尚無資料` 行（`logic._missing_other_lines`，無 `⛔` 前綴，內容是來源鍵）
        與「⛔ 另有 N 檔…取數失敗，未列入」行（只帶檔數），以及紅燈分支的「<塊名>：取數失敗。」。
        這幾種帶進的是**資料（來源鍵、檔數、塊名）**，不是上游錯誤原文；它們也照查，
        與殘留字串（日期、開發字句）撞上的機率視為可接受（本組逐一讀建構處判斷，單組未經第二組驗證）。
    """
    for code, field, original, trimmed, always, marker in _DEV_TRIMS:
        block = logic.find_block(model, code)
        lines = list(block[field])
        if always and original not in lines:
            raise ValueError(f"{code} 的 {field} 沒有「{original}」，logic 改了而本檔沒跟上")
        lines = [trimmed if line == original else line for line in lines]
        left = [
            line for line in lines
            if isinstance(line, str) and not _is_upstream_error_line(line) and marker in line
        ]
        if left:
            raise ValueError(f"{code} 的 {field} 還有開發過程字句：{left!r}")
        block[field] = lines


# S6a-1（客戶 2026-10-03 裁示，總管派工）：HLD-4 說明區講「存檔」的兩句在正式版不成立（「存檔」停用，裁示 A）
# ⇒ 整句不印（只刪不加）；示範模式照印。
# ~~`HLD4_APPLY_NOTE` 也整句不印（S6a-1：「套用」尚未接線）~~ → S6a-2 把「套用」接好了（有意識的更正，不是漏刪；
# 決策者：總管，依客戶 2026-10-03 範圍裁示第 1 項）：那一句改走 `_DEV_TRIMS`，只刪「兩枚按鈕並存，各做一件事。」，
# 「「套用」只讀這些欄位的當下值、重算…六塊…」恢復。
# 每一列：（塊、欄位、整句）。找不到就 raise（同 `_strip_dev_lines`）：logic 改了字面而本檔沒跟上時，
# 靜默略過的話那一句會原封上正式畫面。
_LIVE_DROPS = (
    ("HLD-4", "notes", logic.HLD4_SAVE_NOTE),
    ("HLD-4", "notes", logic.HLD4_SAVE_SCOPE_NOTE),
)


def _drop_live_lines(model: dict) -> None:
    for code, field, line in _LIVE_DROPS:
        block = logic.find_block(model, code)
        if line not in block[field]:
            raise ValueError(f"{code} 的 {field} 沒有「{line}」，logic 改了而本檔沒跟上")
        block[field] = [item for item in block[field] if item != line]


def apply_live_notes(model: dict, *, today: date | None = None) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。正式模式的四件事：

    1. HLD-5 的「最後對帳」改名「最後核對日（只記日期）」，值換成台灣日期；不合格的那一格進 `系統錯誤`
       （`today`：台灣的今天，可注入；不傳就取當下）；
    2. 「存檔」「重新取數」兩類按鈕停用，原因逐字照裁示 A；
    3. 畫面上交代開發過程的子句刪掉，只刪不加（S6a，`_DEV_TRIMS`）；
    4. HLD-4 講「存檔」的兩句整句不印（S6a-1，`_LIVE_DROPS`）。

    ⚠️ 示意字樣不在這裡拿 —— 那是組模型時就決定的（`build_live_model` 傳 `demo_hint=False`）。
       本函式若拿到一份示範模式的模型，示意字樣會原封留著；所以正式模式一律走 `build_live_model`。
    """
    out = copy.deepcopy(model)
    _strip_dev_lines(out)
    _drop_live_lines(out)
    _relabel_sync_field(logic.find_block(out, "HLD-5"), today=taiwan_today() if today is None else today)
    for button in _walk_buttons(out["blocks"]):
        reason = _DISABLED_BY_KIND.get(button["_action_kind"])
        if reason is not None:
            button["_enabled"] = False
            button["disabled_reason"] = reason
    return out


def build_live_model(
    dataset: dict,
    *,
    fields=None,
    viewport_width: int = 1280,
    open_fund=None,
    today: date | None = None,
    direct_policy_id=None,
    direct=(),
    policy_tab_source=None,
    direct_sources=None,
    nav_provenance=None,
    applied_window=None,
    applied_rules=None,
) -> dict:
    """正式模式的整頁模型：不帶示意字樣的 `logic.build_page_model`，再套 `apply_live_notes`。

    本輪 `dataset` 由呼叫端給（測試用假資料的 dataset）；S6 由 `source.py` 取數後給。
    L2 的三個值與 `direct` 清單由呼叫端傳（見本檔「裁示 3-B (ii)」那一段）：
    - `direct_policy_id`：**一律要給**，沒給就 raise（S4 第二輪 M2）；
    - `direct`：L2 `load_alo_tables` 交出的 `direct` 清單原樣；
    - `policy_tab_source`、`direct_sources`：`direct` 非空時要給，沒給就 raise，不猜。
    - `nav_provenance`（S5，裁示 1-A＋1-C）：L2 `build_nav_table` 回傳的 `provenance` 原樣
      （`{fund_code: {..., "cache_fallback", "stale"}}`）；**一律要給**，沒給或形狀不對就 raise。
      每檔最後一筆 `nav_date` 取自同一份 `dataset["nav"]`（畫面上 HLD-6 印的就是那幾列）。
    - `today`：台灣的今天（S3 的 `taiwan_today`；不傳就取當下）。核對日與新鮮度用**同一個** `today`。
    - `applied_window`、`applied_rules`：按「套用」時欄位的當下值，原樣轉給 `logic.build_page_model`（S6a 第三、四輪）。
    """
    if direct_policy_id is None:
        raise ValueError("沒有給 direct_policy_id，無法驗 holding 裡有沒有 DIRECT 列")
    _require_text(direct_policy_id, "direct_policy_id")
    _check_no_direct_holding(dataset, direct_policy_id)
    if not isinstance(direct, (list, tuple)):
        raise TypeError(f"direct 應為 list 或 tuple：{type(direct).__name__}")
    if direct and (policy_tab_source is None or direct_sources is None):
        raise ValueError("有 DIRECT 清單卻沒有給 policy_tab_source／direct_sources，無法決定哪些列算進 N")
    rows = (
        direct_holding_rows(direct, policy_tab_source=policy_tab_source, direct_sources=direct_sources)
        if direct
        else []
    )
    today = taiwan_today() if today is None else today
    fresh = nav_freshness(dataset, nav_provenance, today=today)
    model = logic.build_page_model(
        dataset,
        fields=fields,
        viewport_width=viewport_width,
        open_fund=open_fund,
        demo_hint=False,
        applied_window=applied_window,
        applied_rules=applied_rules,
    )
    out = apply_live_notes(model, today=today)
    out = _apply_freshness(out, fresh)
    return _apply_direct(
        out, rows, has_holdings=bool(dataset.get("holding")),
        # 與 `logic._build_page_model` 的 `holding_unknown` 同一個判定（「讀取失敗不說空」，2026-10-05）。
        holding_failed=bool(dataset.get("errors", {}).get("holding")) and not dataset.get("holding"),
    )


# ───────────────────────── S6b-2：user_setting 解析 ─────────────────────────
# 體例照 `ui_v2/alo/live.py::parse_user_settings`（`_PARSERS`、`BadSettingValue`）。本套件不 import
# `ui_v2.alo`（各頁自足），所以另寫一份；錯誤字句的**模板逐字沿用 alo 那一份**，不另造：
#   - 總前綴「設定值讀不到可用的形狀：」、`broken_keys` 的「{key} 這一列解析不了」；
#   - JSON 那幾句（不是字串／前後有空白／值裡有 NaN／不是 JSON（例外型別）／不是 JSON 陣列）。
# ⚠️ 日期格式不符、門檻元素形狀不符，alo 沒有逐字相同的句子（alo 的元素句寫死 `bucket` 欄名，套不上），
#    這兩類一律用「{key} 這一列解析不了」—— 是 alo 既有的字面，意思也成立（那一列確實解析不了）；
#    代價是訊息看不出是哪一個元素壞掉。要更細的字句得先送客戶，本輪不造。
#
# `hld_deviation_rules` 的線上格式：總管 2026-10-03 裁定（`docs/handover_2026_09_26_latest.md` S6b 小節）——
#   JSON 陣列，元素 `{"indicator": 字串, "direction": RULE_DIRECTIONS 之一, "value": 數}`。
#   `docs/v2/50_settings_sheet_design.md:86` 把 `rules` 的字串格式交給各頁序列化決定。

# 順序同 `ui_v2/hld/fixtures.py::user_settings`。`logic._setting` 找不到鍵就回 None，所以三列不必都在，
# 但這裡一律三列都給，沒設定的那一列值放 None（同 fixtures 的形狀）。
SETTING_KEYS = ("hld_window_start", "hld_window_end", "hld_deviation_rules")

_RULE_FIELDS = frozenset({"indicator", "direction", "value"})


class BadSettingValue(ValueError):
    """試算表上的設定字串不是本頁約定的形狀。訊息拿去填 `errors["user_setting"]`。"""


def _reject_constant(name):
    # `json.loads` 預設吃 NaN／Infinity；一律不收（同 alo、同 L2 `settings_store.value_matches_kind`）。
    raise BadSettingValue(f"值裡有 {name}")


def _row_unparsable(key: str) -> BadSettingValue:
    return BadSettingValue(f"{key} 這一列解析不了")


class _DuplicateJsonKey(ValueError):
    """JSON 物件裡同一個鍵出現兩次。`json.loads` 預設留後一個、默默丟掉前一個 —— 本頁不猜哪一個才對。"""


def _no_duplicate_keys(pairs):
    out = {}
    for name, value in pairs:
        if name in out:
            raise _DuplicateJsonKey(name)
        out[name] = value
    return out


def _parse_date(text: str, key: str) -> str:
    """只收嚴格的 `YYYY-MM-DD`（`_DATE_ONLY`，`re.ASCII`）且是真的日期；回原字串（`logic` 吃字串）。

    `date.fromisoformat` 在 3.11 也收 `20260601`、`2026-W23-1`，所以先過正則（同 `logic._ISO_DATE` 的理由）。
    起日晚於迄日、只設一端**不在這裡擋** —— 那是 `logic.window_is_valid` 既有的判定，各自畫各自的狀態。
    """
    if not isinstance(text, str) or not _DATE_ONLY.fullmatch(text):
        raise _row_unparsable(key)
    try:
        date.fromisoformat(text)
    except ValueError:
        raise _row_unparsable(key) from None
    return text


def _json_array(text: str, key: str) -> list:
    if not isinstance(text, str):
        raise BadSettingValue(f"{key} 的值不是字串")
    if text != text.strip():
        raise BadSettingValue(f"{key} 的值前後有空白")
    try:
        data = json.loads(text, parse_constant=_reject_constant, object_pairs_hook=_no_duplicate_keys)
    except _DuplicateJsonKey:
        # alo 沒有「重複鍵」的字句；沿用既有的「這一列解析不了」，不另造。
        raise _row_unparsable(key) from None
    except BadSettingValue as exc:
        raise BadSettingValue(f"{key} 的{exc}") from None
    except (ValueError, RecursionError) as exc:
        raise BadSettingValue(f"{key} 的值不是 JSON（{type(exc).__name__}）") from None
    if not isinstance(data, list):
        raise BadSettingValue(f"{key} 的值不是 JSON 陣列")
    return data


def _parse_rules(text: str, key: str) -> list:
    """JSON 陣列 → `[{"indicator", "direction", "value"}, ...]`（`logic.saved_rules` 吃的形狀）。

    與 `logic.rules_from_inputs` 對同一列的要求一致：指標名非空字串（照原字收，不去空白）、
    比較方向只收 `logic.RULE_DIRECTIONS`、數值是有限的數。差別只在輸入：那一支吃欄位的字串、
    這裡吃 JSON 的數，所以數值這一格不能直接交給它（`_RULE_NUMBER` 只認字串）。
    元素必須**恰好**這三個欄位；多一個少一個都不猜、不補。`bool` 在 Python 是 int，不當數字。
    """
    out = []
    for item in _json_array(text, key):
        if not isinstance(item, dict) or set(item) != _RULE_FIELDS:
            raise _row_unparsable(key)
        indicator, direction, value = item["indicator"], item["direction"], item["value"]
        if not isinstance(indicator, str) or indicator == "":
            raise _row_unparsable(key)
        if not isinstance(direction, str) or direction not in logic.RULE_DIRECTIONS:
            raise _row_unparsable(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _row_unparsable(key)
        # 先轉 float 再驗有限：超長整數（例如 400 個 9）是合法 JSON，`json.loads` 讀成 int，
        # 直接丟給 `math.isfinite` 會拋 OverflowError，接不住就變成整頁錯誤（稽核 M-1）。
        try:
            number = float(value)
        except OverflowError:
            raise _row_unparsable(key) from None
        if not math.isfinite(number):
            raise _row_unparsable(key)
        out.append({"indicator": indicator, "direction": direction, "value": number})
    return out


_PARSERS = {
    "hld_window_start": _parse_date,
    "hld_window_end": _parse_date,
    "hld_deviation_rules": _parse_rules,
}


def parse_user_settings(rows, broken_keys=(), *, tab_missing=False, bad_rows=()) -> tuple:
    """L2 `load_user_settings()` 的 `rows`／`broken_keys` → (本頁三列, 失敗訊息或 None)。

    - `setting_value` 為 None 或空字串 → 未設定（值放 None，交給 `logic` 既有的「未設定」畫法）；
    - 解析不了、或鍵在 `broken_keys` → 回訊息，**不把它當成「尚未設定」**
      （L1 `load_user_settings` 的 docstring：`broken_keys` 的鍵「畫面應顯示錯誤狀態，不是 ⬜ 未設定」）；
    - 本頁三鍵之外的列一律忽略（同一張表也住著 alo、set 的鍵）。

    - `rows` 不是 dict → 三鍵一律解析不了（不靜默當成未設定）；
    - 某鍵那一列在 `rows` 裡、卻是 None／不是 dict／缺 `setting_value` 鍵 → 該鍵解析不了（不是未設定）；
    - `broken_keys` 是字串 → TypeError（呼叫端寫錯；字串會被拆成一個個字元，等於沒傳）。

    R-7（客戶 2026-10-09 裁示）：下列三種情形實際上讀不到，一律回訊息，**不說「尚未設定」**：
    - `tab_missing`（L1 找不到設定分頁）→「找不到設定分頁」。hld 頁面級例外：設定是本頁的必要輸入；
      50 §7.1 對 alo、set 維持原規則（分頁不存在＝尚無資料），不得據此改其他頁。
    - 設定鍵空白：`bad_rows` 有一列鍵欄是空的、或 `rows`／`broken_keys` 有只由空白組成的鍵 →「有一列設定鍵空白」。
    - 鍵前後帶空白、去掉空白後是本頁的鍵 →「{鍵} 前後帶空白」。**判錯，不 strip 後照用。**
    三種同時發生時，照本函式既有慣例全部列出、以「；」串接，次序同上，排在逐鍵的訊息之前。
    只有標頭、零筆資料（`rows`、`bad_rows` 皆空、`tab_missing` 為 False）仍是「尚未設定」（50 §4.1）。

    ⚠️ **呼叫端契約：有訊息時，回傳的三列不得交給 `logic`，要交空列表。** 有失敗時三列裡
    仍可能留著解析成功的那幾個值（例如起日壞、迄日好 → 迄日照樣在）；交出部分結果會讓
    `logic` 只看到一半的設定。比照 `ui_v2/alo/source.py`：

        rows_out, problem = parse_user_settings(settings["rows"], settings["broken_keys"])
        if problem is not None:
            errors["user_setting"] = problem
            rows_out = []
    """
    if isinstance(broken_keys, (str, bytes)):
        raise TypeError(f"broken_keys 應為鍵的集合，不是字串：{broken_keys!r}")
    broken = set(broken_keys or ())
    rows_ok = isinstance(rows, dict)
    if not rows_ok:
        rows = {}
    problems = ["找不到設定分頁"] if tab_missing else []   # R-7
    keys_seen = [k for k in list(rows) + sorted(broken, key=str) if isinstance(k, str)]
    if any(k.strip() == "" for k in keys_seen) or any(   # R-7：鍵欄空白（L1 判成 bad_rows，或只有空白）
        str((item["cells"] or [""])[0]).strip() == "" for item in bad_rows
    ):
        problems.append("有一列設定鍵空白")
    problems += [   # R-7：鍵前後帶空白，不 strip 後照用
        f"{key} 前後帶空白" for key in SETTING_KEYS if any(k != k.strip() and k.strip() == key for k in keys_seen)
    ]
    problems += [f"{key} 這一列解析不了" for key in SETTING_KEYS if key in broken or not rows_ok]
    out = []
    for key in SETTING_KEYS:
        source = rows.get(key, {})
        if key in rows and (not isinstance(source, dict) or "setting_value" not in source):
            if key not in broken:
                problems.append(f"{key} 這一列解析不了")
            source = {}
            broken.add(key)
        raw = source.get("setting_value")
        value = None
        if raw is not None and raw != "" and key not in broken:
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


# ── S6b-2（第二塊）：L2 輸出 → load_live 回傳值的組裝 ──
def assemble_live_load(
    *,
    holding_tables,
    holding_error,
    settings,
    settings_error,
    key_results,
    nav_table,
    direct_policy_id,
    policy_tab_source,
    direct_sources,
    empty_without_reason,
    nav_unavailable_withheld,
    dividend_gate_open,
    mask,
) -> dict:
    """S6b-2：把 L2 的輸出組成 `page.render(load_live=...)` 要的回傳值 `{"dataset", "live_args"}`。

    純函式：不讀時鐘、不 import 任何新模組、不改輸入。L2 的常數一律由參數交進來，本檔不寫它們的字面值。

    - `holding_error`、`settings_error` 由呼叫端傳入時必須已經遮蔽；本函式不再遮。
    - 淨值的取數失敗：`nav_table["errors"]` 裡，除了「訊息恰為 `empty_without_reason` 且未取到任何列」的那幾檔，
      其餘一律以 `mask(原文)` 放進 `fund_errors["nav"]`；判斷用原文，只遮放進 `fund_errors` 的那幾筆；`skipped_tabs` 組出的 `errors["holding"]` 也由本函式遮（見下）。
    - 淨值被扣下（代碼在 `nav_unavailable_withheld` 裡）、代碼對照查不到（`ok is False`）、來源回空，
      三種一律不放任何東西 —— 那一檔在 dataset 裡就只是「沒有淨值列、也不在 `fund_errors`」，
      畫面由 logic 既有路徑印「⬜ 資料未備」（區間已設時；未設區間時與健康的檔同樣印「⬜ 不適用：尚未設定區間」），不新增字句。扣下代碼不在清單內 → raise。
    - L1 有回資料、但 L2 全數拒收（沒有淨值列、沒有錯誤、沒有扣下代碼）的檔，同樣不放任何東西。
    - 呼叫端**必須**只交幣別兩碼與取得時間兩碼；同一檔被給了互相矛盾輸入的那一碼只會因呼叫端組錯而出現，刻意不在清單內 → raise（契約被破壞不畫成 ⬜）。⚠️ 本函式不檢查清單內容：呼叫端若連那一碼也交進來，該檔會畫成 ⬜、不會 raise；「清單恰為四碼」列為 S6b-3 的驗收項。
    - `holding_tables["skipped_tabs"]` 有任何一筆（部分分頁讀取失敗或本次未讀）→ 持倉照交，另把各分頁的原因以 `mask` 遮過後放進 `errors["holding"]`。讀到的持倉不為空時，沿用 logic 既有的「有持倉時來源取數失敗」畫法，~~但 HLD-1 在零偏離時仍印「無偏離項」與「沒有任何一檔超出」—— 屬「結論燈兩句」那一塊，待修；~~ → 📌 2026-10-08 修好（有意識的更正，不是漏刪；「結論燈兩句」）：有持倉、零偏離又有略過分頁時，HLD-1 印「⛔ 取數失敗：<原文>」，不再印這兩句。~~讀到的持倉為空時，走 logic 空持倉那一支，畫面仍會印「尚未建立任何持倉」—— 屬「讀取失敗不說空」那一塊，待修。~~ → 📌 2026-10-05 修好（有意識的更正，不是漏刪；「讀取失敗不說空」）：讀到的持倉為空時，logic 把它當成讀取失敗畫、不說空；`direct` 清單照交時 HLD-5 只加卡尾（見 `_apply_direct`）。
    - `pending_tables` 固定為 `["fund_profile", "dividend"]`；配息閘門已打開 → raise（本頁尚未規定配息怎麼組）。
    - 設定有問題時交空列表、問題訊息進 `errors["user_setting"]`，不交部分結果。
      R-7：`settings["tab_missing"]`、`settings["bad_rows"]` 一併交給 `parse_user_settings`（缺鍵 → KeyError，不當成沒有）。
    - 持倉讀取成功時，另做四條一致性檢查（淨值表、代碼對照、持倉三者的代碼要對得上），不過就 raise。
    """
    if (holding_tables is None) == (holding_error is None):   # R-1
        raise ValueError("holding_tables 與 holding_error 要恰好給一個")
    if (settings is None) == (settings_error is None):   # R-2
        raise ValueError("settings 與 settings_error 要恰好給一個")
    if holding_error is not None:   # R-3
        _require_text(holding_error, "holding_error")
    if settings_error is not None:   # R-3
        _require_text(settings_error, "settings_error")
    if holding_tables is None and (key_results is not None or nav_table is not None):   # R-4
        raise ValueError("持倉表讀取失敗時，key_results、nav_table 一律不得給")
    if holding_tables is not None and (key_results is None or nav_table is None):   # R-5
        raise ValueError("持倉表讀取成功時，key_results、nav_table 一律要給")
    if type(dividend_gate_open) is not bool:   # R-6
        raise TypeError(f"dividend_gate_open 應為 bool：{dividend_gate_open!r}")
    _require_text(empty_without_reason, "empty_without_reason")   # R-7
    if isinstance(nav_unavailable_withheld, (str, bytes)) or not isinstance(   # R-8
        nav_unavailable_withheld, (list, tuple, set, frozenset)
    ):
        raise TypeError(f"nav_unavailable_withheld 應為集合：{type(nav_unavailable_withheld).__name__}")
    for reason in nav_unavailable_withheld:
        _require_text(reason, "nav_unavailable_withheld 的元素")
    if not callable(mask):   # R-12
        raise TypeError(f"mask 應為可呼叫：{type(mask).__name__}")
    if dividend_gate_open is True:   # R-9
        raise ValueError("配息閘門已打開，本頁尚未規定配息怎麼組")

    if holding_tables is not None:
        if not isinstance(key_results, (list, tuple)):
            raise TypeError(f"key_results 應為 list：{type(key_results).__name__}")
        codes_held = {h["fund_code"] for h in holding_tables["holding"]}
        nav_codes = {r["fund_code"] for r in nav_table["rows"]}
        for name in ("errors", "withheld", "skipped", "fetched", "skipped_rows", "provenance"):
            nav_codes |= set(nav_table[name])
        if nav_codes - codes_held:   # R-13
            raise ValueError(f"淨值表出現持倉裡沒有的代碼：{sorted(nav_codes - codes_held)!r}")
        for r in key_results:   # R-14
            if type(r["ok"]) is not bool:
                raise TypeError(f"代碼對照的 ok 應為 bool：{r['input']!r}")
        inputs = {r["input"] for r in key_results}
        if inputs != codes_held:   # R-14
            raise ValueError(
                f"代碼對照的輸入與持倉代碼不一致：多 {sorted(inputs - codes_held)!r}、少 {sorted(codes_held - inputs)!r}"
            )
        key_failed = {r["input"] for r in key_results if r["ok"] is False}
        if key_failed & nav_codes:   # R-15
            raise ValueError(f"代碼對照失敗的代碼不得出現在淨值表：{sorted(key_failed & nav_codes)!r}")
        key_ok = {r["input"] for r in key_results if r["ok"] is True}
        not_handed = {c for c in key_ok if c not in nav_table["fetched"] and c not in nav_table["withheld"]}
        if not_handed:   # R-16
            raise ValueError(f"代碼對照成功、卻沒有交給淨值表的代碼：{sorted(not_handed)!r}")

    errors = {}
    if holding_tables is None:
        holding, policy, direct = [], [], []
        errors["holding"] = holding_error
    else:
        holding = [dict(r) for r in holding_tables["holding"]]
        policy = [dict(r) for r in holding_tables["policy"]]
        direct = list(holding_tables["direct"])
        skipped_tabs = holding_tables["skipped_tabs"]
        if skipped_tabs:
            parts = []
            for tab_entry in skipped_tabs:
                tab = _require_text(tab_entry["tab"], "skipped_tabs 的 tab")
                error = tab_entry["error"]
                if isinstance(error, str) and error.strip():
                    parts.append(f"{tab}：{error}")
                else:
                    parts.append(tab)
            errors["holding"] = mask("；".join(parts))

    if settings is None:
        user_setting = []
        errors["user_setting"] = settings_error
    else:
        user_setting, problem = parse_user_settings(
            settings["rows"], settings["broken_keys"],
            tab_missing=settings["tab_missing"], bad_rows=settings["bad_rows"],
        )
        if problem is not None:
            errors["user_setting"] = problem
            user_setting = []

    nav, failures, provenance = [], {}, {}
    if holding_tables is not None:
        for code, message in nav_table["errors"].items():
            if message == empty_without_reason and nav_table["fetched"].get(code, 0) == 0:
                continue
            failures[code] = mask(message)
        for code, reason in nav_table["withheld"].items():
            if reason not in nav_unavailable_withheld:
                raise ValueError(f"淨值扣下原因 {reason!r} 不在本頁約定的清單內：{code!r}")   # R-10
        nav = [dict(r) for r in nav_table["rows"]]
        provenance = dict(nav_table["provenance"])

    return {
        "dataset": {
            "holding": holding,
            "nav": nav,
            "dividend": [],
            "policy": policy,
            "fund_profile": [],
            "user_setting": user_setting,
            "errors": errors,
            "pending_tables": ["fund_profile", "dividend"],
            "fund_errors": {"nav": failures} if failures else {},
        },
        "live_args": {
            "direct_policy_id": direct_policy_id,
            "direct": direct,
            "policy_tab_source": policy_tab_source,
            "direct_sources": direct_sources,
            "nav_provenance": provenance,
        },
    }
