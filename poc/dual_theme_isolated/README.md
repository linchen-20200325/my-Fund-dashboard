# 雙模式（淺色／深色）隔離技術 PoC —— 非 production、對外不可用

- 授權：`docs/DECISIONS.md` `DEC-2026-11-11-02`（T1／T3／T4，僅隔離 PoC；**不是**正式雙模式 UI 施工授權）。
- 範圍：只在本目錄與 `tests/poc_dual_theme/`；不得被 `app.py`／`ui/`／`ui_v2/`／`ui_v3/`／`services/`／`repositories/`／`shared/`／`infra/`／`scripts/`／`.github/`／`.streamlit/` 引用（有守衛測試）。
- 所有資料為**合成示範資料**，沒有任何真實數據、取數、Sheet；不使用 JS、不使用 browser storage、不寫檔；模式只存在 `st.session_state`（session-only）。
- 暗色 HEX 為研究示例／PoC 測試用固定值，**不是**核准色票；PoC-only 變體在 `poc_palettes.py` 內逐項標註。
- 本目錄**不得**有 `pages/` 子目錄。
- 手動執行：`streamlit run poc/dual_theme_isolated/app_poc.py`
