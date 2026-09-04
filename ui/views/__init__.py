"""ui/views/ —— 五分頁動線重構（WF-IA-1）的全新 View 層。

客戶 2026-09-04 頒布的架構方針第 1 條：

    UI 渲染層全面「打掉重練」：不要在舊的 `ui/tab*.py` 上修改，直接開闢全新檔案，
    嚴格依照已拍板的《五分頁動線重構》（WF-IA-1）與四大鐵律，從零開始乾淨撰寫全新 View。

本套件的檔案一律**從零撰寫**，不是舊 `tab*.py` 的搬運。舊檔依方針第 3 條
**暫留作為參考**，待新版 5 頁驗收完成後整批拔除 —— 本批**一個字都沒有動它們**。

⚠️ **為什麼放在 `ui/views/` 而不是 top-level `views/`**（總管 2026-09-04 拍板，理由是實測）：
守衛的掃描根是 `ui/`，所以放進 `ui/` 底下才會被涵蓋。

⚠️ **2026-09-04 回修（有意識的更正，不是漏刪 · 決策者：回修組 WF01-F）**：
本段原寫 ~~「**四道**鐵律守衛」~~ 並只列四個檔 ——
**那是低估，數字與清單都不對**。**這是低估、不是說反**：結論（放 `ui/views/`
才會被守衛涵蓋）在正確的數字下**只會更成立**。以下為實測後的正確版本。

**(1) 共用真相源 `UI_SOURCES` —— 定義一處、六個檔共用**
定義在 `tests/test_render_state_color_separation.py`（hub）：

    UI_SOURCES = sorted((ROOT / "ui").rglob("*.py")) + [ROOT / "app.py"]

用它的六個檔（`git grep -l "UI_SOURCES" -- tests/`，量測日 2026-09-04）：

    tests/test_render_state_color_separation.py          （hub 本身；鐵則 03 三態顏色）
    tests/test_tricolor_colour_provenance.py             （鐵則 03 顏色來源）
    tests/test_ui_grid_contract.py                       （鐵則 01 三欄網格）← 舊清單漏了它
    tests/test_ui_rerun_contract.py                      （鐵則 02 Form 防重繪）
    tests/test_ia_switch_advisor_moved_to_portfolio.py   ← 舊清單漏了它
    tests/test_ia_tab4_ledger_flattened.py               ← 舊清單漏了它

**(2) 另外自己寫一份 `ui/` 掃描根、不走 hub 的**
枚舉指令（本行**逐字重跑過**，回 **8 個檔**；扣掉下方註明的 2 個即下表的 6 個）：

    git grep -lE "['\"]ui['\"][)]?[.]rglob" -- tests/

    tests/test_batch2_top_card_grid.py          `pathlib.Path("ui").rglob("*.py")`
    tests/test_tab1_macro.py                    `(_root / "ui").rglob("*.py")`
    tests/test_audit_20260805_evidence_notes.py `(_ROOT / "ui").rglob("*.py")`
    tests/test_audit_20260805_tab1_summary.py   同上
    tests/test_audit_20260805_tab1_ui.py        同上
    tests/test_audit_20260805_tab1_wiring.py    同上

⚠️ **那 8 個裡有 2 個不算在本組**，據實寫明：
`test_render_state_color_separation.py` —— 它命中的是 (1) 的 **hub 定義本身**
（另有一次是它 docstring 裡的示例字串），已列在 (1)；
`test_tricolor_colour_provenance.py` —— 命中的是一行**註解**
（記載它 2026-09-04 之前自己複製過一份 glob、後來改為從 hub 匯入），不是活的掃描根。

**(3) 實測「誰真的讀到了本套件的檔案」**（不靠讀 source 推測）
作法：包住 `pathlib.Path.read_text`，命中 `ui/views/*.py` 時記下當時的測試檔。
上列 (1)+(2) **共 12 個檔全部命中**（`ui/views/__init__.py` 與
`ui/views/page_01_macro.py` 兩個檔都是），量測日 2026-09-04。

⚠️ **不宣稱窮舉**：上面的候選集是 grep 出來的，**沒有掃過的寫法就掃不到**
（動態組出的路徑、經另一個模組轉一手的掃描根…）。**12 是下界，不是母體。**
本段要用的是「**掃描根是 `ui/`**」這個機制，不是這個數字。

放 top-level `views/` 會讓上列守衛對新頁**全部瞎掉**；放 `ui/views/` 則自動被涵蓋。
客戶原文寫的是「例如 `views/page_01_macro.py`」——「**例如**」是示例，
而目錄命名屬 `CLAUDE.md §-1.5.1c v3 §03-1`「資料庫結構與搬遷排程」的**內部自決區**。

⚠️ **連帶後果，據實寫明**：本套件的檔案**從第一行起就在上列守衛的射程內**。
這是刻意的（第一天就守住），代價是不能「先寫髒的再說」。
"""
from __future__ import annotations
