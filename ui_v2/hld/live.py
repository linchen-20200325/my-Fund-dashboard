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

S4（裁示 3-B (ii)）：DIRECT 持倉另外列出、不計入體檢 —— 見 `direct_holding_rows` 與 `_apply_direct`。

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

# 持倉全空而 N＞0 時（S4 第二輪 M1，總管裁定）：`logic` 寫出「尚未建立任何持倉」的出口，逐一列名。
# 只認這幾個**完整字串**；`_apply_direct` 換完之後，模型裡若還找得到那幾個字就 raise ——
# 那表示 `logic` 多了一個本表沒列到的出口（寧可整頁失敗，不讓畫面一邊說 N 筆、一邊說沒有持倉）。
#   1. 恰為 `TEXT_NO_HOLDING`：HLD-0 `text`／`summary_text`；HLD-1、HLD-2、HLD-3 `summary_text` 與 `detail_lines`；
#      HLD-8 `detail_lines`。
#   2. `f"{ND_TEXT}：{TEXT_NO_HOLDING}"`：HLD-8 `summary_text`。
#   3. `f"（另：{TEXT_NO_HOLDING}。{TEXT_SHEETS_READONLY}）"`：HLD-0 紅燈時的 `lines`。
#   4. HLD-5：摘要整句換成 `DIRECT_SUMMARY_ONLY`，`_HLD5_EMPTY_LINE` 那一行拿掉（不是換字）。
_HLD5_EMPTY_LINE = f"{logic.TEXT_NO_HOLDING}，沒有可以展開的檔。"


def _empty_replacements(warning: str) -> dict:
    nh = logic.TEXT_NO_HOLDING
    return {
        nh: warning,
        f"{logic.ND_TEXT}：{nh}": f"{logic.ND_TEXT}：{warning}",
        f"（另：{nh}。{logic.TEXT_SHEETS_READONLY}）": f"（另：{warning}。{logic.TEXT_SHEETS_READONLY}）",
    }


def _replace_strings(node, table: dict):
    if isinstance(node, str):
        return table.get(node, node)
    if isinstance(node, dict):
        return {k: _replace_strings(v, table) for k, v in node.items()}
    if isinstance(node, list):
        return [_replace_strings(v, table) for v in node]
    if isinstance(node, tuple):
        return tuple(_replace_strings(v, table) for v in node)
    return node


def _strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _strings(v)
    elif isinstance(node, (list, tuple)):
        for v in node:
            yield from _strings(v)


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
    - `tab` 不是字串 → TypeError；只有空白 → ValueError；`row` 不是正整數（含 `bool`）→ ValueError；
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
    for entry in direct:
        if not isinstance(entry, dict):
            raise TypeError(f"DIRECT 清單的元素應為 dict：{entry!r}")
        if "source" not in entry:
            raise ValueError(f"DIRECT 列缺 source：{entry!r}")
        source = entry["source"]
        if source not in sources:
            raise ValueError(f"DIRECT 列的 source 認不得：{entry!r}")
        tab, row = entry.get("tab"), entry.get("row")
        if not isinstance(tab, str):
            raise TypeError(f"DIRECT 列的分頁名應為字串：{entry!r}")
        if not tab.strip():
            raise ValueError(f"DIRECT 列的分頁名是空白：{entry!r}")
        if isinstance(row, bool) or not isinstance(row, int) or row <= 0:
            raise ValueError(f"DIRECT 列的列號不是正整數：{entry!r}")
        key = (source, tab, row)
        if key in seen:
            raise ValueError(f"DIRECT 列重複（同一來源、分頁、列號）：{entry!r}")
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
    model = _replace_strings(model, _empty_replacements(warning))
    left = [text for text in _strings(model) if logic.TEXT_NO_HOLDING in text]
    if left:
        raise ValueError(f"「{logic.TEXT_NO_HOLDING}」還有沒換到的出口：{left!r}")
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


def apply_live_notes(model: dict, *, today: date | None = None) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。正式模式的兩件事：

    1. HLD-5 的「最後對帳」改名「最後核對日（只記日期）」，值換成台灣日期；不合格的那一格進 `系統錯誤`
       （`today`：台灣的今天，可注入；不傳就取當下）；
    2. 「存檔」「重新取數」兩類按鈕停用，原因逐字照裁示 A。

    ⚠️ 示意字樣不在這裡拿 —— 那是組模型時就決定的（`build_live_model` 傳 `demo_hint=False`）。
       本函式若拿到一份示範模式的模型，示意字樣會原封留著；所以正式模式一律走 `build_live_model`。
    """
    out = copy.deepcopy(model)
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
) -> dict:
    """正式模式的整頁模型：不帶示意字樣的 `logic.build_page_model`，再套 `apply_live_notes`。

    本輪 `dataset` 由呼叫端給（測試用假資料的 dataset）；S6 由 `source.py` 取數後給。
    L2 的三個值與 `direct` 清單由呼叫端傳（見本檔「裁示 3-B (ii)」那一段）：
    - `direct_policy_id`：**一律要給**，沒給就 raise（S4 第二輪 M2）；
    - `direct`：L2 `load_alo_tables` 交出的 `direct` 清單原樣；
    - `policy_tab_source`、`direct_sources`：`direct` 非空時要給，沒給就 raise，不猜。
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
    model = logic.build_page_model(
        dataset,
        fields=fields,
        viewport_width=viewport_width,
        open_fund=open_fund,
        demo_hint=False,
    )
    out = apply_live_notes(model, today=today)
    return _apply_direct(out, rows, has_holdings=bool(dataset.get("holding")))
