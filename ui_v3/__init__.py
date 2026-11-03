# -*- coding: utf-8 -*-
"""ui_v3 — New UI2（唯一未來正式 presentation layer）。批 1：機械式骨架。

依據：`docs/v2/80_new_ui2_architecture_proposal.md`（第 4、5、6、8、9、10、13 節；已凍結，
`DEC-2026-11-02-05`）、正式 Streamlit 顯示規則 `DEC-2026-11-02-06`（`PROJECT_RULES.md` 13.2）。

~~本批只有機械式骨架，沒有任何使用者可見頁面~~ → 2026-11-03 BL-0536 rendering 批：**只有 🌍 市場與趨勢**（Preview App only；其餘四頁無核准線框、不做空殼，`DEC-2026-10-27-10`）。以下為批 1 骨架說明（原文保留）：

- `viewmodels/`  純 Python view model dataclass（無 streamlit、無 I/O、無 services import）。
- `fixtures/`    fake scenario 資料；**明確標示 FAKE**；正式路徑（含 `app_preview.py`）不得 import。
- `adapters/`    **唯一**可 import `services.v2_tables`／`services.v2_domain` 的位置；本批只有 stub、零 import。
- `shell/`       五頁登錄表（頁序、頁名、是否掛載）；純資料，本批不 import streamlit。
- `design/`      token 命名（批 2b，值未定）；`pages/` 保留位置（批 3～逐頁 wireframe 核准後才有內容）。
- 呈現規則資料表住 `shared/ui_semantics/`（批 2b）；`viewmodels/`、`pages/` 可 import（守衛明列白名單）。
- `app_preview.py`     獨立 preview 入口；本批**不註冊任何頁、不可當正式 main file**（見該檔 docstring）。

⛔ 不得 import Old UI（`ui/`、根目錄 `app.py`）或 `ui_v2`（不開任何 reuse 白名單）；`shared/` 只准 `shared.ui_semantics`。
⛔ 本檔 import 時零副作用。
"""
