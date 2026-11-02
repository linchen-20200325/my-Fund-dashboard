# -*- coding: utf-8 -*-
"""ui_v3（New UI2）獨立 preview 入口 —— **批 1：存在，但不註冊任何頁、不可當作 main file 使用**。

為什麼不渲染任何東西（`DEC-2026-10-27-10`／`-12`「不做空殼」、80 第 9、10 節、`PROJECT_RULES.md` 13.2）：
- 五頁都還沒有經客戶核准的 New UI2 wireframe（`CLAUDE.md` §-1.5.4；80 第 10 節階段 3），
  任何使用者可見的頁（含「建置中」「規劃中」）都是空殼。
- 因此本入口**不 import streamlit、不呼叫 `st.navigation`／`st.Page`、不畫任何元素**。
  以 `python ui_v3/app_preview.py` 執行會拋 `PreviewNotReady`（測試有覆蓋）。以 `streamlit run` 直接跑
  **未實測**：預期會大聲失敗（`PreviewNotReady`，或因 sys.path 未調整而 `ModuleNotFoundError`），
  不會產生「看起來可用」的畫面。**絕不可設為 Streamlit Cloud 的 main file**；頁出現之前設計上即不可用。
- import 本檔零副作用（只有定義；`main()` 只在 `__main__` 才執行）。

接手說明：第一頁 wireframe 經客戶核准並實作後，由該批在 `ui_v3/shell/registry.py` 把該頁改為
`registered=True`，並在此處補 `st.navigation`；同批必須同步改
`tests/ui_v3/test_ui_v3_page_registry_guard.py` 與 `tests/ui_v3/test_ui_v3_preview_not_formal_guard.py`。
正式 cutover（BL-0535）與本檔無關：preview ≠ 正式入口（`DEC-2026-11-02-06`）；
本檔不得被 `app.py`、`ui/`、`ui_v2/` 引用（守衛：test_ui_v3_preview_not_formal_guard）。

⛔ 不得 import `ui_v3.fixtures`（preview 不得顯示 fake 資料）、不得 import ui_v2／Old UI。
"""
from __future__ import annotations

from ui_v3.shell.registry import assert_preview_ready


def main() -> None:
    """註冊頁並啟動導覽。批 1 沒有可註冊的頁 → `PreviewNotReady`。"""
    assert_preview_ready()
    # 批 1 不可能走到這裡（assert_preview_ready 在沒有頁時一定拋出）。
    # 之後有已核准的頁時，在此以 shell.registry.registered_pages() 建立導覽。
    raise NotImplementedError("navigation wiring 待第一頁 wireframe 核准後的批次實作")


if __name__ == "__main__":
    main()
