"""test_tab1_macro.py — ui/tab1_macro.py smoke 測試（v18.127 B-C.5）

驗證 B-C.5 抽出後 Tab1 render 函式：
- module import OK
- render_macro_tab callable + 無位置 arg（與其他 4 個 tab 同設計）
- render_indicator_map private helper 也 callable
- _calc_data_health / _friendly_error alias 正確
"""
from __future__ import annotations


def test_module_imports_ok():
    """tab1_macro.py 可被 import；render_macro_tab 無位置 arg。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import render_macro_tab
    import inspect
    assert callable(render_macro_tab)
    sig = inspect.signature(render_macro_tab)
    assert len(sig.parameters) == 0, "render_macro_tab 應為純無參數函式"


def test_render_indicator_map_callable():
    """render_indicator_map (Tab1 私有 Sankey helper) 從 app.py 搬入後 callable。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import render_indicator_map
    import inspect
    assert callable(render_indicator_map)
    assert len(inspect.signature(render_indicator_map).parameters) == 0


def test_friendly_error_alias():
    """_friendly_error 從 ui.helpers.session 正確 import。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _friendly_error
    from ui.helpers.session import friendly_error
    assert _friendly_error is friendly_error


def test_calc_data_health_wrapper():
    """_calc_data_health(ind) delegate to ui.helpers.session。"""
    import fund_fetcher  # noqa: F401
    from ui.tab1_macro import _calc_data_health
    ind = {"PMI": {"value": 50}}
    pct, traffic = _calc_data_health(ind)
    assert pct == 6
    assert traffic == "🔴"


def test_app_py_shim_render_indicator_map_still_works():
    """app.py 保留 render_indicator_map shim（純 source 驗證避免觸發 streamlit）。"""
    from pathlib import Path
    src = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    # B-C.5 後應該有 shim line
    assert "from ui.tab1_macro import render_indicator_map" in src
