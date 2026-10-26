# -*- coding: utf-8 -*-
"""測試用：模擬「新 B UI 第一階段唯讀」解除，讓**休眠中的寫入路徑**測得到。

依據：客戶 2026-10-26 正式裁示第 7 節（新 B UI 預設唯讀；旗標只准用作更嚴格控制／測試）、
`DEC-2026-10-25-04` J-6 與 2026-10-26 J-14 補記。第一階段 production：
- `repositories/settings_sheet_repository.py::is_read_only()` 恆為 True（`save_setting_for_page` 短路回 `read_only`）；
- `ui_v2/readonly.py::WRITE_CONTROLS_ENABLED` 為 False（五頁正式模式不畫「存檔」、`SET-4` 整塊不畫）。

既有測試驗的是「存檔怎麼寫、寫成怎樣、失敗怎麼顯示」這些寫入能力本身（保留為休眠能力，未刪）；這些測試以本模組
把兩道開關同時打開再驗，**不是**宣稱 production 可寫。第一階段的真實行為（不畫、短路、零呼叫）見
`tests/ui_v2/test_readonly_write_surface_guard.py`。
"""
from __future__ import annotations


def enable(monkeypatch) -> None:
    from repositories import settings_sheet_repository as repo
    from ui_v2 import readonly

    monkeypatch.setattr(readonly, "WRITE_CONTROLS_ENABLED", True)
    monkeypatch.setattr(repo, "is_read_only", lambda: False)
