"""test_tab6_manual.py — ui/tab6_manual.py smoke 測試（v18.117 B-C.1）

驗證 B-C.1 抽出後 Tab6 render 函式：
- module import 不報錯
- render_manual_tab 是 callable，且不需要參數
- 函式內部使用 streamlit + pandas（mock 後驗證 sub-tabs 數量與標題正確）

跑 streamlit 真 render 屬 slow tier（AppTest），本檔只做 fast tier 必要的契約驗證。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def test_module_imports_ok():
    """ui/tab6_manual.py 可被 import；render_manual_tab callable + 無位置 arg。"""
    from ui.tab6_manual import render_manual_tab
    import inspect
    assert callable(render_manual_tab)
    sig = inspect.signature(render_manual_tab)
    assert len(sig.parameters) == 0   # 純無參數函式


def test_render_calls_streamlit_tabs_with_8_subtabs():
    """render_manual_tab 內部建立 8 個 sub-tab（與既有 app.py Tab6 結構一致）。"""
    from ui import tab6_manual as t6
    captured_labels: list = []

    class _FakeTab:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    def _fake_tabs(labels):
        captured_labels.extend(labels)
        return [_FakeTab() for _ in labels]

    fake_st = MagicMock()
    fake_st.tabs.side_effect = _fake_tabs
    fake_st.markdown = MagicMock()
    fake_st.caption = MagicMock()
    fake_st.dataframe = MagicMock()

    with patch.object(t6, "st", fake_st):
        t6.render_manual_tab()

    # 8 個 sub-tab 標題包含預期關鍵字
    assert len(captured_labels) == 8
    for kw in ["Macro Score", "景氣天氣", "六因子", "吃本金", "再平衡",
               "台股TPI", "核心衛星", "汰弱留強"]:
        assert any(kw in lbl for lbl in captured_labels), f"missing sub-tab: {kw}"


def test_render_does_not_touch_session_state():
    """v18.117 B-C.1 PoC 設計準則：Tab6 純靜態 markdown，不應讀寫 session_state。

    用 fake_st 沒設 session_state → 若 render 嘗試讀 session_state 會 AttributeError。
    """
    from ui import tab6_manual as t6

    class _FakeTab:
        def __enter__(self): return self
        def __exit__(self, *a): return False

    fake_st = MagicMock(spec=["markdown", "caption", "dataframe", "tabs"])
    fake_st.tabs.return_value = [_FakeTab() for _ in range(8)]

    with patch.object(t6, "st", fake_st):
        # 若 render 試圖 .session_state.xxx 會 AttributeError（spec 沒列）
        t6.render_manual_tab()
