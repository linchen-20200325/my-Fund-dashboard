# -*- coding: utf-8 -*-
"""ui_v3（New UI2）獨立 **Preview App** 入口 —— 目前只有 🌍 市場與趨勢（BL-0536 rendering 批；客戶 2026-11-03 授權只進 Preview）。

⛔ 這**不是**正式入口：不切正式 Streamlit entrypoint、不 cutover、Old UI 與 `ui_v2` 不在這裡、也不在這裡暴露；
   preview ≠ 正式 App（`DEC-2026-11-02-06`、`DEC-2026-11-03-04`）。本檔不得被 `app.py`、`ui/`、`ui_v2/` 引用
   （守衛：`tests/ui_v3/test_ui_v3_preview_not_formal_guard.py`）；絕不可設為 Streamlit Cloud 的 main file。
⛔ 不得 import `ui_v3.fixtures`（preview 不得顯示 fake 資料）、不得 import ui_v2／Old UI。

執行：repo 根目錄 `streamlit run ui_v3/app_preview.py`。`main()` 會把 repo 根目錄補進 `sys.path`（`streamlit run` 只加腳本所在資料夾）。

設計：
- 所有 import（含 streamlit）都在函式內：import 本檔零副作用（只有定義；`main()` 只在 `__main__` 才執行）。
- 只導覽 `shell.registry.registered_pages()` 的頁；沒有已核准並實作的頁 → `PreviewNotReady`（不渲染空殼）；
  登錄為已掛載、卻沒有對應 renderer → `NotImplementedError`（Fail Loud，不畫空殼）。
- 導覽：routing 用 `st.navigation(position="hidden")`，五頁導覽（桌機側欄＋手機底部導覽）與 Status Bar 由 `pages/chrome.py` 自畫（Shell；`docs/v2/80` 第 17 節）；未掛載的頁可見但不可進、不建空殼。
- 資料：由 `adapters.market_page.load()` 呼叫既有 L2→L1（不新增資料源、不新增 dependency）；FRED 金鑰沿用 `st.secrets`／環境變數 `FRED_API_KEY`。
"""
from __future__ import annotations


def _ensure_repo_root_on_path() -> None:
    import pathlib
    import sys

    root = str(pathlib.Path(__file__).resolve().parents[1])
    if root not in sys.path:
        sys.path.insert(0, root)


def _render_mkt() -> None:
    """🌍 頁：讀 controls → adapter 取數並組 view model → 頁渲染（頁只吃 view model）。"""
    import os

    import streamlit as st

    from ui_v3.adapters import market_page as adapter
    from ui_v3.adapters import shell_status
    from ui_v3.pages import chrome, mkt

    period, view, rates_key = mkt.selected_controls()
    market_view, table = adapter.load([st.secrets, os.environ])
    model = adapter.build_market_page(market_view, table, period=period, primary_view=view, rates_key=rates_key)
    chrome.render_status(shell_status.from_market_model(model))   # Status Bar＋側欄資料狀態區＋更新資料 CTA（來源：既有 health）
    mkt.render(model)
    chrome.render_footer()


def main() -> None:
    """註冊已掛載的頁並啟動導覽。沒有已掛載的頁 → `PreviewNotReady`。"""
    _ensure_repo_root_on_path()
    import streamlit as st

    from ui_v3.shell.registry import assert_preview_ready

    pages = assert_preview_ready()
    renderers = {"mkt": _render_mkt}
    missing = [p.slug for p in pages if p.slug not in renderers]
    if missing:
        raise NotImplementedError(f"已掛載的頁沒有 renderer：{missing}（不畫空殼）")
    from ui_v3.pages import chrome

    st.set_page_config(page_title=pages[0].title, page_icon="🌍", layout="wide", initial_sidebar_state="expanded")
    st_pages = {p.slug: st.Page(renderers[p.slug], title=p.title, url_path=p.slug, default=i == 0) for i, p in enumerate(pages)}
    navigation = st.navigation(list(st_pages.values()), position="hidden")   # routing 只用 Streamlit；導覽畫面由 Shell 自畫
    chrome.render_navigation(st_pages, next((p.slug for p in pages if p.title == navigation.title), None))   # 五頁導覽（側欄＋手機底部導覽）；未掛載的頁可見但不可進，不建空殼
    navigation.run()


if __name__ == "__main__":
    main()
