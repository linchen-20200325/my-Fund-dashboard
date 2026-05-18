"""test_tab4_backtest.py — ui/tab4_backtest.py smoke 測試（v18.124 B-C.2）

驗證 B-C.2 抽出後 Tab4 render 函式：
- module import 不報錯
- render_backtest_tab 是 callable、無位置 arg（零閉包依賴設計核心）
- 不接收 ind/phase 等參數（與 Tab6 相同的純無參數設計）
- 走 session_state.portfolio_funds 為空時也能 render（顯示 info 而非 crash）
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_module_imports_ok():
    """ui/tab4_backtest.py 可被 import；render_backtest_tab callable + 無位置 arg。"""
    # 先 import fund_fetcher（解 circular import）
    import fund_fetcher  # noqa: F401
    from ui.tab4_backtest import render_backtest_tab
    import inspect
    assert callable(render_backtest_tab)
    sig = inspect.signature(render_backtest_tab)
    assert len(sig.parameters) == 0, "render_backtest_tab 應為純無參數函式（零閉包依賴）"


def test_render_with_empty_portfolio_shows_info_not_crash():
    """portfolio_funds 為空時應顯示 info 而非 crash（與 B-C.1 Tab6 同設計準則）。"""
    import fund_fetcher  # noqa: F401
    from ui import tab4_backtest as t4
    info_called: list = []
    radio_called: list = []

    class _FakeCol:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_radio(label, options, **kw):
        radio_called.append((label, options))
        return options[0]   # 預設第一個（按保單組合）

    fake_st = MagicMock()
    fake_st.session_state = MagicMock()
    fake_st.session_state.portfolio_funds = []   # 空組合
    fake_st.radio.side_effect = _fake_radio
    fake_st.columns.return_value = (_FakeCol(), _FakeCol())
    fake_st.info.side_effect = lambda msg: info_called.append(msg)
    # 其他常用 widget mock 成 no-op
    fake_st.markdown = MagicMock()
    fake_st.caption = MagicMock()
    fake_st.selectbox = MagicMock(return_value="近 3 年")
    fake_st.text_input = MagicMock(return_value="")
    fake_st.button = MagicMock(return_value=False)
    fake_st.checkbox = MagicMock(return_value=False)
    fake_st.divider = MagicMock()

    with patch.object(t4, "st", fake_st):
        t4.render_backtest_tab()

    # 空組合時應 render 兩個 info：「組合基金尚無已載入資料」+ 「請先在上方選取基金」
    assert len(info_called) >= 1
    assert any("尚無已載入" in m or "選取基金" in m for m in info_called)
    # radio widget 應被呼叫（兩個模式選擇器）
    assert len(radio_called) == 1
    assert "回測模式" in radio_called[0][0]
