"""ui/views/ —— 五分頁動線重構（WF-IA-1）的全新 View 層。

客戶 2026-09-04 頒布的架構方針第 1 條：

    UI 渲染層全面「打掉重練」：不要在舊的 `ui/tab*.py` 上修改，直接開闢全新檔案，
    嚴格依照已拍板的《五分頁動線重構》（WF-IA-1）與四大鐵律，從零開始乾淨撰寫全新 View。

本套件的檔案一律**從零撰寫**，不是舊 `tab*.py` 的搬運。舊檔依方針第 3 條
**暫留作為參考**，待新版 5 頁驗收完成後整批拔除 —— 本批**一個字都沒有動它們**。

⚠️ **為什麼放在 `ui/views/` 而不是 top-level `views/`**（總管 2026-09-04 拍板，理由是實測）：
四道鐵律守衛的掃描根**全部**是 `ui/`——

    tests/test_render_state_color_separation.py   `sorted((ROOT / "ui").rglob("*.py")) + [ROOT / "app.py"]`
    tests/test_batch2_top_card_grid.py            `pathlib.Path("ui").rglob("*.py")`
    tests/test_ui_rerun_contract.py               同上（`UI_SOURCES`）
    tests/test_tricolor_colour_provenance.py      與第一個共用 `UI_SOURCES`

放 top-level `views/` 會讓這四道守衛對新頁**全部瞎掉**；放 `ui/views/` 則自動被涵蓋。
客戶原文寫的是「例如 `views/page_01_macro.py`」——「**例如**」是示例，
而目錄命名屬 `CLAUDE.md §-1.5.1c v3 §03-1`「資料庫結構與搬遷排程」的**內部自決區**。

⚠️ **連帶後果，據實寫明**：本套件的檔案**從第一行起就在四道守衛的射程內**。
這是刻意的（第一天就守住），代價是不能「先寫髒的再說」。
"""
from __future__ import annotations
