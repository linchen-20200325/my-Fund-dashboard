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
        "render_macro_tab",
        "render_single_fund_tab",
        "render_portfolio_tab",
        "render_data_guard_tab",
        "render_manual_tab",
    ):
        assert f"from ui.tab" in src   # 至少有一個 ui.tab import
        assert fn in src, f"{fn} not found in app.py"
    assert "render_backtest_tab" not in src, "回測 Tab 應已移除，app.py 不該再引用 render_backtest_tab"
