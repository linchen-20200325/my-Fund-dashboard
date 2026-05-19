"""test_tab2_single_fund.py — ui/tab2_single_fund.py smoke 測試（v18.126 B-C.4）

驗證 B-C.4 抽出後 Tab2 render 函式：
- module import 不報錯
- render_single_fund_tab 是 callable + 無位置 arg
- 內部 _calc_data_health helper 與 ui.helpers.session 同源
- _friendly_error / _is_core_fund alias 從 ui.helpers.session 正確 import

不直接 mock-render（Tab2 內容複雜、需大量 session_state 鋪墊，留 deploy 驗證）
"""
from __future__ import annotations


def test_module_imports_ok():
    """tab2_single_fund.py 可被 import；render_single_fund_tab 無位置 arg。"""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import render_single_fund_tab
    import inspect
    assert callable(render_single_fund_tab)
    sig = inspect.signature(render_single_fund_tab)
    assert len(sig.parameters) == 0, "render_single_fund_tab 應為純無參數函式"


def test_friendly_error_imported():
    """_friendly_error 從 ui.helpers.session 正確 import."""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import _friendly_error
    from ui.helpers.session import friendly_error
    assert _friendly_error is friendly_error


def test_is_core_fund_imported():
    """_is_core_fund 從 ui.helpers.session 正確 import."""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import _is_core_fund
    # 用幾個關鍵字驗 round-trip
    assert _is_core_fund("摩根多重收益基金") is True
    assert _is_core_fund("AI 半導體基金") is False
    assert _is_core_fund("") is False


def test_calc_data_health_returns_pct_traffic():
    """_calc_data_health 應 delegate 給 ui.helpers.session.calc_data_health。"""
    import fund_fetcher  # noqa: F401
    from ui.tab2_single_fund import _calc_data_health
    ind = {"PMI": {"value": 50}, "VIX": {"value": 18}}   # 2/16 = 12.5%
    pct, traffic = _calc_data_health(ind)
    assert pct == 12
    assert traffic == "🔴"


def test_app_py_shim_friendly_error():
    """app.py 內 _friendly_error / _is_core_fund shim 仍存在。"""
    from pathlib import Path
    src = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    assert "from ui.helpers.session import friendly_error as _friendly_error" in src
    assert "from ui.helpers.session import (" in src   # is_core_fund block
    assert "is_core_fund as _is_core_fund" in src
