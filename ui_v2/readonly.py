# -*- coding: utf-8 -*-
"""新 B UI 第一階段唯讀：畫面層的寫入控制開關（五頁共用）。

依據：客戶 2026-10-26 正式裁示（`docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`）
第 7 節「移除／隱藏新 B UI 第一階段所有寫入控制；`SET-4` 維持完全不顯示」；`DEC-2026-10-25-04` J-6（第一階段全部唯讀，
含 `SET-4` 類型）與 2026-10-26 J-14 補記（`SET-4` 參數編輯塊第一階段不出現）。

只管**正式模式**（`load_live` 有傳）畫不畫：
- 寫 `user_setting` 的按鈕（`_writes` 含 `user_setting`，即「存檔」類）一律不畫 —— 見 `strip_write_controls`。
- `SET-4` 參數編輯塊整塊不畫 —— 見 `visible_codes`。

不管：示範模式（fixtures，寫的是 in-memory 替身、不碰 Google Sheet）、`st.download_button`（本機下載）、
`SET-5`「重新取數」（`_writes` 是 `fetch_log`，另一批處理）。

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
    ("未存檔：欄位的觀察窗與比較基準日和已存值不同，存檔後下一次重新載入才生效",
     "欄位的觀察窗與比較基準日和已存值不同"),                          # `live.TEXT_UNSAVED_WINDOW`
    ("未存檔：勾選與已存清單不同，存檔後下一次重新載入才生效", "勾選與已存清單不同"),   # `live.TEXT_UNSAVED_PICKS`
    # hld
    ("；存檔後，下一次重新載入時生效。", "。"),                          # `live.TEXT_APPLY_NOT_SHOWN`
    ("「存檔」只寫使用者設定，", "本頁"),                                  # `logic.HLD4_SAVE_SCOPE_NOTE`
    # alo
    ("；這裡的存檔只存比重基準與類別名稱", ""),                          # `live.TEXT_ALO4_SHEETS`
    # exp
    ("未存檔：條件列與已存值不同，存檔後下一次重新載入才生效", "條件列與已存值不同"),   # `logic.TEXT_UNSAVED_RULES`
    ("未存檔：欄位勾選或排序欄位與已存值不同，存檔後下一次重新載入才生效",
     "欄位勾選或排序欄位與已存值不同"),                                # `live.TEXT_UNSAVED_EXP4`
    ("欄位勾選與排序欄位改了要按「存檔」，下一次重新載入才生效：", ""),     # `logic.TEXT_EXP4_LIVE`
    ("；「存檔」只寫 使用者設定，不寫入 持倉、保單、淨值、配息", "；本頁不寫入 持倉、保單、淨值、配息"),        # `EXP-4` 說明行（plain 換字後）
)


def _rewrite_text(text: str) -> str:
    for old, new in PHASE1_TEXT_REWRITES:
        text = text.replace(old, new)
    return text


def _rewrite(node) -> None:
    """就地改寫 dict／list 底下的每一個字串（保留物件身分：畫面層可能已拿著某一塊的參照）。"""
    if isinstance(node, dict):
        items = node.items()
    elif isinstance(node, list):
        items = enumerate(node)
    else:
        return
    for key, value in list(items):
        if isinstance(value, str):
            node[key] = _rewrite_text(value)
        elif isinstance(value, tuple):
            node[key] = tuple(_rewrite_text(v) if isinstance(v, str) else v for v in value)
        else:
            _rewrite(value)


def is_write_control(button) -> bool:
    """這一枚按鈕會寫第一階段禁寫的表？（讀模型自帶的 `_writes`，不比對標籤字串。）"""
    return bool(set(button.get("_writes") or ()) & PHASE1_BLOCKED_WRITES)


def strip_write_controls(model: dict) -> dict:
    """正式模式畫之前：把每一塊 `buttons` 裡的寫入按鈕拿掉，並改寫 `PHASE1_TEXT_REWRITES` 那幾段說明
    （就地改、也回傳同一份）。開關開著時不動。判定、狀態、顏色一個都不動。
    拿掉了幾枚記在 `model["_readonly_stripped"]`（給測試讀）。"""
    stripped = 0
    if not WRITE_CONTROLS_ENABLED:
        for block in model.get("blocks", ()):
            buttons = block.get("buttons")
            if buttons:
                kept = [b for b in buttons if not is_write_control(b)]
                stripped += len(buttons) - len(kept)
                block["buttons"] = kept
            _rewrite(block)
    model["_readonly_stripped"] = stripped
    return model


def visible_codes(codes) -> list:
    """正式模式某一層要畫的塊代號：第一階段整塊不畫的拿掉（開關開著時原樣）。"""
    if WRITE_CONTROLS_ENABLED:
        return list(codes)
    return [code for code in codes if code not in PHASE1_HIDDEN_CODES]
