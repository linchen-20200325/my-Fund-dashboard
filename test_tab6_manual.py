"""test_tab6_manual.py — ui/tab6_manual.py smoke 測試（v18.117 B-C.1）

驗證 B-C.1 抽出後 Tab6 render 函式：
- module import 不報錯
- render_manual_tab 是 callable，且不需要參數
- 函式內部使用 streamlit + pandas（mock 後驗證 sub-tabs 數量與標題正確）

跑 streamlit 真 render 屬 slow tier（AppTest），本檔只做 fast tier 必要的契約驗證。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch



def test_module_imports_ok():
    """ui/tab6_manual.py 可被 import；render_manual_tab callable + 無位置 arg。"""
    from ui.tab6_manual import render_manual_tab
    import inspect
    assert callable(render_manual_tab)
    sig = inspect.signature(render_manual_tab)
    assert len(sig.parameters) == 0   # 純無參數函式


class _FakeCM:
    """Streamlit context-manager stub（兼任 col / expander / form / spinner）。

    `.button()` 一律回 False（不觸發送出分支，避免 render 試圖讀 session_state）；
    其他子方法（text_input / number_input / file_uploader 等）回 MagicMock。
    """
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def __getattr__(self, name):
        if name == "button":
            return lambda *a, **kw: False
        if name == "file_uploader":
            return lambda *a, **kw: None
        if name == "selectbox":
            # 回 options[0] 確保 pandas 比較有可比型別（None 為 fallback）
            return lambda *a, **kw: (kw.get("options") or a[1] if len(a) > 1 else [None])[0]
        if name in ("text_input", "text_area"):
            return lambda *a, **kw: kw.get("value", "")
        if name in ("number_input", "slider"):
            return lambda *a, **kw: kw.get("value", 0)
        if name == "multiselect":
            return lambda *a, **kw: []
        return MagicMock()


def _build_fake_st(captured_labels: list | None = None) -> MagicMock:
    """共用 streamlit mock fixture — primitives 全配齊 + button=False 鎖死靜態路徑。"""
    fake_st = MagicMock()

    if captured_labels is not None:
        def _fake_tabs(labels):
            captured_labels.extend(labels)
            return [_FakeCM() for _ in labels]
        fake_st.tabs.side_effect = _fake_tabs
    else:
        fake_st.tabs.return_value = [_FakeCM() for _ in range(10)]

    def _fake_columns(spec):
        # st.columns 兩種呼叫：st.columns(3) 或 st.columns([1, 2, 1])
        n = spec if isinstance(spec, int) else len(spec)
        return [_FakeCM() for _ in range(n)]
    fake_st.columns.side_effect = _fake_columns
    fake_st.expander = MagicMock(return_value=_FakeCM())
    fake_st.form = MagicMock(return_value=_FakeCM())
    fake_st.spinner = MagicMock(return_value=_FakeCM())
    fake_st.button = MagicMock(return_value=False)
    fake_st.file_uploader = MagicMock(return_value=None)
    return fake_st


def test_render_calls_streamlit_tabs_with_10_subtabs():
    """render_manual_tab 內部建立 10 個 sub-tab（v18.169 加第 9、v18.174 加第 10）。"""
    from ui import tab6_manual as t6
    captured_labels: list = []
    fake_st = _build_fake_st(captured_labels)

    with patch.object(t6, "st", fake_st):
        t6.render_manual_tab()

    assert len(captured_labels) == 10
    for kw in ["Macro Score", "景氣天氣", "六因子", "吃本金", "再平衡",
               "台股TPI", "核心衛星", "汰弱留強",
               "Sheet 資料結構", "全局指標關聯地圖"]:
        assert any(kw in lbl for lbl in captured_labels), f"missing sub-tab: {kw}"


def test_render_static_path_runs_without_session_state_access():
    """v18.117 B-C.1 PoC 設計準則弱化版：Tab6 靜態 render path（button 未按）
    不應讀寫 session_state。`button=False` 鎖死所有 submit 分支，
    觸發 session_state 即視為違反靜態渲染契約。"""
    from ui import tab6_manual as t6
    fake_st = _build_fake_st()
    # session_state 設成屬性級攔截 — 一旦被讀就拋
    sentinel = MagicMock()
    sentinel.get.side_effect = AssertionError(
        "靜態 render path 不應觸發 session_state.get"
    )
    fake_st.session_state = sentinel

    with patch.object(t6, "st", fake_st):
        t6.render_manual_tab()
