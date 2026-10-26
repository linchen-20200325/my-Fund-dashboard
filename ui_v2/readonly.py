# -*- coding: utf-8 -*-
"""新 B UI 第一階段唯讀：畫面層的寫入控制開關（五頁共用）。

依據：客戶 2026-10-26 正式裁示（`docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`）
第 7 節「移除／隱藏新 B UI 第一階段所有寫入控制；`SET-4` 維持完全不顯示」；`DEC-2026-10-25-04` J-6（第一階段全部唯讀，
含 `SET-4` 類型）與 2026-10-26 J-14 補記（`SET-4` 參數編輯塊第一階段不出現）。

只管**正式模式**（`load_live` 有傳）畫不畫：
- 寫 `user_setting` 的按鈕（`_writes` 含 `user_setting`，即「存檔」類）一律不畫 —— 見 `strip_write_controls`。
- `SET-4` 參數編輯塊整塊不畫 —— 見 `visible_codes`。
- 存檔鈕拿掉後已不影響本次畫面結果、但仍顯示的輸入元件不畫（J-14 精神，2026-10-26）—— 見 `PHASE1_HIDDEN_INPUT_CODES`、
  `inputs_hidden`。

不管：示範模式（fixtures，寫的是 in-memory 替身、不碰 Google Sheet）、`st.download_button`（本機下載）、
`SET-5`「重新取數」（~~`_writes` 是 `fetch_log`，另一批處理~~ → 2026-10-26 裁示第 6 節已處理：取數紀錄改記在本次工作階段，
不寫任何 Google Sheet，見 `services/v2_tables/settings_store.py::RuntimeFetchStore`；按鈕照畫，它的 `_writes` 指的是
取數紀錄這張表的概念，現在只在記憶體）。

第二道防線在 L2／L1：`services/v2_tables/settings_store.py::save_setting_for_page` 在
`repositories/settings_sheet_repository.py::is_read_only()`（第一階段恆為 True）時短路回 `read_only`。
本開關是**常數**、不讀任何環境旗標：第一階段不得因設定變成可寫。測試要模擬休眠寫入路徑時以 monkeypatch 改它。
"""
from __future__ import annotations

WRITE_CONTROLS_ENABLED = False

# 第一階段不准有寫入控制的資料表（`44` 5.3：存檔類只寫 user_setting）。
PHASE1_BLOCKED_WRITES = frozenset({"user_setting"})

# 第一階段整塊不畫的塊（J-14：`SET-4` 參數編輯）。
PHASE1_HIDDEN_CODES = frozenset({"SET-4"})


# 拿掉存檔鈕之後會變成假話的說明（叫人按存檔、或說「存檔後…生效」）：正式模式畫之前就地改寫（子字串 → 取代）。
# 只收「指示或承諾存檔」那一段；描述狀態的句子（例「尚未存檔，預設顯示全部」）照留。字面是經過 `plain.plain_model`
# 之後的樣子（`user_setting` 等已換成中文），守衛見 `tests/ui_v2/test_readonly_write_surface_guard.py`。
PHASE1_TEXT_REWRITES = (
    # mkt
    ("，請重新存檔", ""),                                           # `logic.TEXT_INCOMPLETE_INCONSISTENT`
    ("，請在指標清單勾選並存檔", ""),                                 # `logic.TEXT_UNSAVED_NONE`
    ("存檔後，下一次重新載入才生效。", ""),                            # `MKT-5` 說明行
    # ~~→ "欄位的觀察窗與比較基準日和已存值不同"／"勾選與已存清單不同"~~ → 2026-10-26 輸入元件不畫之後（`PHASE1_HIDDEN_INPUT_CODES`）
    # 「和已存值不同」指的是看不到的欄位，整句拿掉（有意識的更正，不是漏刪；下同 exp 兩句）。
    ("未存檔：欄位的觀察窗與比較基準日和已存值不同，存檔後下一次重新載入才生效", ""),   # `live.TEXT_UNSAVED_WINDOW`
    ("未存檔：勾選與已存清單不同，存檔後下一次重新載入才生效", ""),   # `live.TEXT_UNSAVED_PICKS`
    # hld
    ("；存檔後，下一次重新載入時生效。", "。"),                          # `live.TEXT_APPLY_NOT_SHOWN`
    ("「存檔」只寫使用者設定，", "本頁"),                                  # `logic.HLD4_SAVE_SCOPE_NOTE`
    # alo
    ("；這裡的存檔只存比重基準與類別名稱", ""),                          # `live.TEXT_ALO4_SHEETS`
    # exp
    ("未存檔：條件列與已存值不同，存檔後下一次重新載入才生效", ""),   # `logic.TEXT_UNSAVED_RULES`
    ("未存檔：欄位勾選或排序欄位與已存值不同，存檔後下一次重新載入才生效", ""),   # `live.TEXT_UNSAVED_EXP4`
    ("欄位勾選與排序欄位改了要按「存檔」，下一次重新載入才生效：", ""),     # `logic.TEXT_EXP4_LIVE`
    # 2026-10-26：`EXP-4` 勾選框不畫之後，這半句講的是看不到的勾選框 → 拿掉（`logic._EXP4_LIVE_HEAD` 後半）。
    ("⚠ 取消勾基金名、其他欄仍勾著時，清單上就沒有基金名 —— ", ""),
    ("；「存檔」只寫 使用者設定，不寫入 持倉、保單、淨值、配息", "；本頁不寫入 持倉、保單、淨值、配息"),        # `EXP-4` 說明行（plain 換字後）
)


# ── 已無作用、但仍顯示的輸入元件（客戶 2026-10-25 `DEC-2026-10-25-04` J-14 精神：第一階段不出現暗示可修改的控制項）──
# 存檔鈕拿掉之後，下列各塊的輸入欄／勾選框／下拉／多選只影響「存檔寫什麼」與「和已存值不同」的提示，
# 不影響本次畫面上的任何正式結果（各頁的正式結果只讀已存設定：mkt `live.build_live_model`、hld `live.build_live_model`、
# exp `live.build_live_model`、alo `logic.build_page_model(dataset)`）⇒ 正式模式整組不畫。
# 會即時影響畫面的輸入照留：`ALO-3` 試算、`EXP-3`／`EXP-6`「對照」多選（不在本表）。
PHASE1_HIDDEN_INPUT_CODES = frozenset({"MKT-4", "MKT-5", "HLD-4", "EXP-1", "EXP-4", "EXP-5", "ALO-1", "ALO-4"})
# 塊上的旗標：畫面層的渲染函式看它決定畫不畫輸入元件（`inputs_hidden`）。
INPUTS_HIDDEN_FLAG = "_readonly_inputs_hidden"
# 只用來改輸入列的按鈕（新增一列、清除這一列）：輸入欄不畫，它們一併拿掉（讀模型的 `_action_kind`，不比對標籤）。
INPUT_EDIT_KINDS = frozenset({"新增列", "清除"})
# 只在某一塊改寫的說明（輸入元件不畫之後會變成暗示可改的句子；子字串 → 取代，空字串＝整句拿掉）。
PHASE1_HIDDEN_INPUT_TEXT = {
    "MKT-5": (("勾選只決定下方指標明細顯示哪些指標；", "下方指標明細只顯示已存的指標；"),),
    "ALO-1": (("目標在這裡輸入；", ""),),   # `ALO-1` 卡頭上方那一行（`plain` 換字後）
    "EXP-1": (("尚未新增任何條件列。", "沒有已存的條件列。"),),
    "EXP-5": (("尚未勾選任何基金", "本頁唯讀"),),
}


def hides_inputs(code: str) -> bool:
    """正式模式這一塊的輸入元件畫不畫（開關開著時一律畫）。組模型之前要知道時用它（例：不把 session 裡的勾選交給模型）。"""
    return not WRITE_CONTROLS_ENABLED and code in PHASE1_HIDDEN_INPUT_CODES


def inputs_hidden(block: dict) -> bool:
    """畫面層：這一塊的輸入元件要不要藏起來（`strip_write_controls` 掛上的旗標；示範模式沒有旗標 ⇒ 照畫）。"""
    return bool(block.get(INPUTS_HIDDEN_FLAG))


def _rewrite_text(text: str, rules=PHASE1_TEXT_REWRITES) -> str:
    for old, new in rules:
        text = text.replace(old, new)
    return text


def _rewrite(node, rules=PHASE1_TEXT_REWRITES) -> None:
    """就地改寫 dict／list 底下的每一個字串（保留物件身分：畫面層可能已拿著某一塊的參照）。
    清單裡被改寫成空字串的那一句整句拿掉（不留空行）；本來就是空字串的不動。"""
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list):
        items = enumerate(node)
    else:
        return
    dropped = []
    for key, value in list(items):
        if isinstance(value, str):
            node[key] = _rewrite_text(value, rules)
            if isinstance(node, list) and value and not node[key]:
                dropped.append(key)
        elif isinstance(value, tuple):
            node[key] = tuple(_rewrite_text(v, rules) if isinstance(v, str) else v for v in value)
        else:
            _rewrite(value, rules)
    for index in reversed(dropped):
        del node[index]


def is_write_control(button) -> bool:
    """這一枚按鈕會寫第一階段禁寫的表？（讀模型自帶的 `_writes`，不比對標籤字串。）"""
    return bool(set(button.get("_writes") or ()) & PHASE1_BLOCKED_WRITES)


def strip_write_controls(model: dict) -> dict:
    """正式模式畫之前：把每一塊 `buttons` 裡的寫入按鈕拿掉，並改寫 `PHASE1_TEXT_REWRITES` 那幾段說明
    （就地改、也回傳同一份）。開關開著時不動。判定、狀態、顏色一個都不動。
    拿掉了幾枚記在 `model["_readonly_stripped"]`（給測試讀）。

    2026-10-26（J-14 精神）另外：`PHASE1_HIDDEN_INPUT_CODES` 那幾塊掛上 `INPUTS_HIDDEN_FLAG`（畫面層據此不畫輸入元件）、
    拿掉只用來改輸入列的按鈕（`INPUT_EDIT_KINDS`，含每列的 `row_buttons`），並套該塊的 `PHASE1_HIDDEN_INPUT_TEXT`。
    掛了旗標的塊代號記在 `model["_readonly_inputs_hidden"]`。"""
    stripped = 0
    hidden = []
    if not WRITE_CONTROLS_ENABLED:
        for block in model.get("blocks", ()):
            buttons = block.get("buttons")
            if buttons:
                kept = [b for b in buttons if not is_write_control(b)]
                stripped += len(buttons) - len(kept)
                block["buttons"] = kept
            if block.get("code") in PHASE1_HIDDEN_INPUT_CODES:
                block[INPUTS_HIDDEN_FLAG] = True
                hidden.append(block["code"])
                block["buttons"] = [b for b in block.get("buttons") or () if b.get("_action_kind") not in INPUT_EDIT_KINDS]
                if "row_buttons" in block:
                    block["row_buttons"] = []
                _rewrite(block, PHASE1_HIDDEN_INPUT_TEXT.get(block["code"], ()))
            _rewrite(block)
    model["_readonly_stripped"] = stripped
    model["_readonly_inputs_hidden"] = hidden
    return model


def visible_codes(codes) -> list:
    """正式模式某一層要畫的塊代號：第一階段整塊不畫的拿掉（開關開著時原樣）。"""
    if WRITE_CONTROLS_ENABLED:
        return list(codes)
    return [code for code in codes if code not in PHASE1_HIDDEN_CODES]
