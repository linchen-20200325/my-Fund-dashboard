# -*- coding: utf-8 -*-
"""持倉體檢**正式模式**才有的呈現層調整（純函式；不 import streamlit、不 import 舊樹、不 import fixtures）。

依據：客戶 2026-10-02 裁示的 `docs/wireframes/draft_hld_live.html` §G，以及客戶 2026-10-02 裁示 A（按鈕文案）。
體例照 `ui_v2/alo/live.py`、`ui_v2/set/live.py`：示範模式（`ui_v2/app_hld.py`）不經過本檔，一個字都不變。

本輪（hld 接真資料 S3）只做呈現層骨架，**不接任何取數**：
1. **「（示意）」全部拿掉**（裁示 2-A）—— 由 `logic.build_page_model(demo_hint=False)` 組模型時就不接，
   不是事後去字串裡刪（事後刪會連資料本身的字一起刪，那是改資料）。
2. **對帳時間欄**（裁示 4-C）—— HLD-5 展開欄位「最後對帳」改名「最後核對日（只記日期）」，值只留日期。
3. **按鈕停用**（裁示 A，文案逐字）—— 「存檔」與「重新取數」停用並寫出原因。
   按鈕**出現在哪幾塊**一格不動，沿用 `logic` 既有規則（HLD-1／2／3 不掛重新取數；HLD-8 在任一值為
   `資料未備` 或 `系統錯誤` 時掛）；本檔只改已經在那裡的按鈕的啟用狀態，不新增、不拿掉任何一枚。

⛔ 頁面入口 `ui_v2/app_hld_live.py` 與取數 `ui_v2/hld/source.py` 是 S6 的工作，本輪不建。
⛔ 頁首副標（草稿 §E P1／P2：「資料為假資料…」「情境 …」）住在 `page.py::render`，那是入口接線的一部分，
   本輪不動；S6 接 `render(load_live=)` 時照 `ui_v2/alo/page.py` 的做法處理。

⚠️ 文案逐字照裁示；改字要先回草稿（`CLAUDE.md` §-1.5.4）。
"""

from __future__ import annotations

import copy
from datetime import date

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


def _date_only(value: str) -> str:
    """只收 `YYYY-MM-DD`。值是推定的（當日 12:00），所以畫面只記日期（裁示 4-C 客戶理由）。

    `logic._build_hld5` 已經只取 `last_synced_at` 的前 10 個字；這裡再驗一次那 10 個字真的是日期 ——
    不是的話，前 10 個字可能是任何東西，照印就是把一段不知道是什麼的字當日期給人看（§1：寧可炸掉）。
    """
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"最後核對日不是 YYYY-MM-DD：{value!r}")
    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"最後核對日不是 YYYY-MM-DD：{value!r}") from None
    return value


def _walk_buttons(node):
    if isinstance(node, dict):
        if "_action_kind" in node:
            yield node
        for value in node.values():
            yield from _walk_buttons(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            yield from _walk_buttons(value)


def _relabel_sync_field(block: dict) -> None:
    # `_items` 與 `_rows` 在 `logic._build_hld5` 是同一份清單，但本檔不靠這個巧合：
    # 兩個鍵都走一次（已改過的那一格不再含舊欄名，第二次走是空轉）。
    for item in [*block.get("_items", []), *block.get("_rows", [])]:
        fields = []
        for label, value in item["_fields"]:
            if label == OLD_SYNC_LABEL:
                fields.append((SYNC_LABEL, _date_only(value)))
            else:
                fields.append((label, value))
        item["_fields"] = fields


def apply_live_notes(model: dict) -> dict:
    """回傳調整過的模型複本（不改呼叫端手上的那一份）。正式模式的兩件事：

    1. HLD-5 的「最後對帳」改名「最後核對日（只記日期）」，值驗過是日期；
    2. 「存檔」「重新取數」兩類按鈕停用，原因逐字照裁示 A。

    ⚠️ 示意字樣不在這裡拿 —— 那是組模型時就決定的（`build_live_model` 傳 `demo_hint=False`）。
       本函式若拿到一份示範模式的模型，示意字樣會原封留著；所以正式模式一律走 `build_live_model`。
    """
    out = copy.deepcopy(model)
    _relabel_sync_field(logic.find_block(out, "HLD-5"))
    for button in _walk_buttons(out["blocks"]):
        reason = _DISABLED_BY_KIND.get(button["_action_kind"])
        if reason is not None:
            button["_enabled"] = False
            button["disabled_reason"] = reason
    return out


def build_live_model(dataset: dict, *, fields=None, viewport_width: int = 1280, open_fund=None) -> dict:
    """正式模式的整頁模型：不帶示意字樣的 `logic.build_page_model`，再套 `apply_live_notes`。

    本輪 `dataset` 由呼叫端給（測試用假資料的 dataset）；S6 由 `source.py` 取數後給。
    """
    model = logic.build_page_model(
        dataset,
        fields=fields,
        viewport_width=viewport_width,
        open_fund=open_fund,
        demo_hint=False,
    )
    return apply_live_notes(model)
