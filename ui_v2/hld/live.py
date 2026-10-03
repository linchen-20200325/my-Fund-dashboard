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

⚠️ 文案逐字照裁示；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
"""

from __future__ import annotations

import copy
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


def _apply_direct(model: dict, rows: list, *, has_holdings: bool) -> dict:
    """HLD-5 卡尾一行黃字＋逐筆位置（灰），收合摘要加 DIRECT 筆數；持倉全空時另把「尚未建立任何持倉」換掉。

    N＝0 時什麼都不加（草稿與 alo 都沒寫 N＝0 的畫法；本組的處理，已回報待裁）。
    各塊的 `_state`／`_tone`、按鈕都不動：這幾筆是「讀到了、照裁示不計入」，不是哪一塊算不出來。
    """
    if not rows:
        return model
    n = len(rows)
    warning = DIRECT_EXCLUDED_TEXT.format(n=n)
    hld5 = logic.find_block(model, "HLD-5")
    if has_holdings:
        hld5["summary_text"] = hld5["summary_text"] + DIRECT_SUMMARY_SUFFIX.format(n=n)
    else:
        if _HLD5_EMPTY_LINE not in hld5["detail_lines"]:
            raise ValueError(f"HLD-5 空持倉的說明行「{_HLD5_EMPTY_LINE}」不在，logic 改了而本檔沒跟上")
        hld5["summary_text"] = DIRECT_SUMMARY_ONLY.format(n=n)
        hld5["detail_lines"] = [line for line in hld5["detail_lines"] if line != _HLD5_EMPTY_LINE]
    hld5["tail_notes"] = [{"text": warning, "_tone": "黃"}] + [
        {"text": DIRECT_LOCATION_TEXT.format(tab=r["tab"], row=r["row"]), "_tone": "灰"} for r in rows
    ]
    if has_holdings:
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
)


def _strip_dev_lines(model: dict) -> None:
    """把 `_DEV_TRIMS` 的原字串整行換成刪減後的版本（逐字比對，其餘行不碰）。

    - 一定出現的那幾句找不到 → raise：`logic` 改了字面而本檔沒跟上，靜默略過的話那一句會原封上正式畫面；
    - 換完之後該欄位還有任何一行含殘留檢查那一小段 → raise（條件出現的那一句也靠這一條防字面漂移）。
      只查本表點名的（塊、欄位），不掃整個模型 —— 上游錯誤原文不住在這些位置（同 `_EMPTY_EXITS` 的理由）。
    """
    for code, field, original, trimmed, always, marker in _DEV_TRIMS:
        block = logic.find_block(model, code)
        lines = list(block[field])
        if always and original not in lines:
            raise ValueError(f"{code} 的 {field} 沒有「{original}」，logic 改了而本檔沒跟上")
        lines = [trimmed if line == original else line for line in lines]
        left = [line for line in lines if isinstance(line, str) and marker in line]
        if left:
            raise ValueError(f"{code} 的 {field} 還有開發過程字句：{left!r}")
        block[field] = lines


def apply_live_notes(model: dict, *, today: date | None = None) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。正式模式的三件事：

    1. HLD-5 的「最後對帳」改名「最後核對日（只記日期）」，值換成台灣日期；不合格的那一格進 `系統錯誤`
       （`today`：台灣的今天，可注入；不傳就取當下）；
    2. 「存檔」「重新取數」兩類按鈕停用，原因逐字照裁示 A；
    3. 畫面上交代開發過程的子句刪掉，只刪不加（S6a，`_DEV_TRIMS`）。

    ⚠️ 示意字樣不在這裡拿 —— 那是組模型時就決定的（`build_live_model` 傳 `demo_hint=False`）。
       本函式若拿到一份示範模式的模型，示意字樣會原封留著；所以正式模式一律走 `build_live_model`。
    """
    out = copy.deepcopy(model)
    _strip_dev_lines(out)
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
    )
    out = apply_live_notes(model, today=today)
    out = _apply_freshness(out, fresh)
    return _apply_direct(out, rows, has_holdings=bool(dataset.get("holding")))
