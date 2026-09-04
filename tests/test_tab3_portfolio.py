"""test_tab3_portfolio.py — ui/tab3_portfolio.py smoke 測試（v18.128 B-C.6 最終）

驗證 B-C.6 抽出後 Tab3 render 函式：
- module import OK
- render_portfolio_tab callable + 無位置 arg（**6/6 tab 完成**）
- 內部 alias 從 ui.helpers.session 正確

Tab3 為最大 tab（3897 行 body，合併原 app.py 兩個 with tab3: block）。
"""
from __future__ import annotations


def test_module_imports_ok():
    """tab3_portfolio.py 可被 import；render_portfolio_tab 無位置 arg。"""
    import fund_fetcher  # noqa: F401
    from ui.tab3_portfolio import render_portfolio_tab
    import inspect
    assert callable(render_portfolio_tab)
    sig = inspect.signature(render_portfolio_tab)
    assert len(sig.parameters) == 0, "render_portfolio_tab 應為純無參數函式"


def test_friendly_error_alias():
    import fund_fetcher  # noqa: F401
    from ui.tab3_portfolio import _friendly_error
    from ui.helpers.session import friendly_error
    assert _friendly_error is friendly_error


def test_is_core_fund_alias():
    import fund_fetcher  # noqa: F401
    from ui.tab3_portfolio import _is_core_fund
    from ui.helpers.session import is_core_fund
    assert _is_core_fund is is_core_fund


def test_app_py_only_has_render_calls_for_all_5_tabs():
    """app.py 應該只剩 5 個 render_*_tab() 呼叫，沒有 inline tab block。

    v18.176：移除回測 Tab → render_backtest_tab 不再出現於 app.py。
    """
    from pathlib import Path
    src = (Path(__file__).parents[1] / "app.py").read_text(encoding="utf-8")
    for fn in (
        # 2026-09-04 五分頁動線重構（WF-IA-1）：① 的 render 函式換成
        # `ui/views/page_01_macro.py::render_market_overview`。
        # 改的只是 ① 那一個名字。舊 `ui/tab1_macro.py::render_macro_tab` 一個字都沒動
        # （客戶方針第 3 條「舊版 tab 檔案暫留作為參考」），只是不再被 app.py 掛上 ①。
        #
        # ⚠️ **2026-09-04 回修（有意識的更正，不是漏刪 · 決策者：回修組 WF01-F）**：
        # 上一版這裡寫 ~~「本條守的東西一字未減：app.py 仍然必須為每個分頁**各有一個
        # render 呼叫**、**仍然不准有 inline tab block**、仍然不准回頭引用
        # `render_backtest_tab`」~~ —— **前兩項這條測試守不住**，據實改寫。
        #
        # **本條實際做的三件事（讀 assert 即可自驗）**：
        #   1) `"from ui.tab" in src`         —— 至少有一個 `ui.tab` import
        #   2) `<每個名字> in src`             —— **子字串存在**檢查，不是呼叫檢查
        #   3) `"render_backtest_tab" not in src`
        #
        # **突變實測（2026-09-04，在記憶體裡對 app.py 原始碼字串突變，未寫回磁碟）**：
        #   A 在 `with tab_macro:` 內塞 `st.markdown` ＋ `st.metric`  → **仍綠**
        #   B 把 `render_market_overview(` 整句註解掉（名字仍在檔內）→ **仍綠**
        #   C 把名字整個換掉                                        → 轉紅 ✅
        #   D 讓 `render_backtest_tab` 重新出現                     → 轉紅 ✅
        # → A 證明它**不守** inline tab block；B 證明它守的是**名字出現過**、
        #   不是「各有一個呼叫」。守得住的只有 C、D 兩個方向。
        #
        # ⚠️ **這是既有射程缺口，不是本 PR 弄壞的** —— 同樣的突變在 base
        #    （`c892830`）上跑也是綠的。本輪**只改敘述、不動測試邏輯**：擴射程屬另立批次。
        #    （本函式 docstring 那句「沒有 inline tab block」同屬既有表述，本輪未動。）
        "render_market_overview",
        "render_single_fund_tab",
        "render_portfolio_tab",
        "render_data_guard_tab",
        "render_manual_tab",
    ):
        assert "from ui.tab" in src   # 至少有一個 ui.tab import
        assert fn in src, f"{fn} not found in app.py"
    assert "render_backtest_tab" not in src, "回測 Tab 應已移除，app.py 不該再引用 render_backtest_tab"
