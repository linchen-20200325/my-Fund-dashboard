"""test_tab6_manual.py — ui/tab6_manual.py smoke 測試（v18.117 B-C.1）

驗證 B-C.1 抽出後 Tab6 render 函式：
- module import 不報錯
- render_manual_tab 是 callable，且不需要參數
- 函式內部使用 streamlit + pandas（mock 後驗證 ~~sub-tabs 數量~~ →
  **單頁 10 章 + 目錄**的數量與標題正確；2026-08-31 客戶拍板線框把 10 個
  子分頁改成錨點目錄，**有意識的政策變更，不是漏刪**，理由見
  `test_render_draws_10_chapters_as_a_single_page` 的 docstring）

跑 streamlit 真 render 屬 slow tier（AppTest），本檔只做 fast tier 必要的契約驗證。
"""
from __future__ import annotations

import pytest
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


def test_render_draws_10_chapters_as_a_single_page():
    """render_manual_tab 畫出 **10 章**（單頁 + 錨點目錄），而**不是** 10 個 sub-tab。

    ~~原名 `test_render_calls_streamlit_tabs_with_10_subtabs`，斷言
    `len(captured_labels) == 10`（`st.tabs` 收到 10 個標籤）。~~
    **有意識的政策變更，不是漏刪**（日期 2026-08-31 · 決策者：客戶，線框
    `docs/wireframes/fund-wireframe-final.html` §03 PAGE 5「E · 📖 說明書」逐字拍板
    「10 個主題改為錨點目錄」）。

    **舊斷言的理由仍然成立**：它守的是「十章一章都不能少」這件事 —— 那個要求
    **完全沒有變**，本測試照樣守（下方逐章 keyword 檢查一字未減）。
    **被權衡掉的只有它綁定的載體**：舊版把「十章存在」綁死在 `st.tabs` 這個
    **實作手段**上，於是換掉手段時它會轉紅 —— 而且是**保護舊設計不被改**的那種紅。
    #744 的守衛 docstring 已就地登記過這個形態
    （「期望值**不該寫死已失效的名字** —— 那會變成『保護 bug 不被修掉』的測試」）。

    ⚠️ **本測試現在的職責邊界**：它只驗「十章都畫了、名字都在」。
    「目錄 ⇔ 章節 anchor 對得上」「不得再開 `st.tabs`」由
    `tests/test_manual_anchor_toc.py` 負責（含突變驗證）——
    **刻意不在這裡重複**，兩處各驗一半比兩處各抄一份好。

    突變實驗：把任一 `_chapter("...")` 呼叫刪掉 → **本條轉紅**（少一章）。
    """
    from ui import tab6_manual as t6
    captured_labels: list = []
    fake_st = _build_fake_st(captured_labels)

    with patch.object(t6, "st", fake_st):
        t6.render_manual_tab()

    # 子分頁已經沒有了 —— 這一條同時是「巢狀分頁不得復辟」的行為面複驗。
    assert captured_labels == [], (
        f"說明書又開了 sub-tab：{captured_labels} —— "
        "線框要求單頁 + 錨點目錄（另見 tests/test_manual_anchor_toc.py）。")

    # 章節標題改由 `st.subheader` 畫出（`_chapter()` → `st.subheader(title, anchor=...)`）。
    _titles = [c.args[0] for c in fake_st.subheader.call_args_list if c.args]
    assert len(_titles) == 11, (
        f"應有 10 章 + 1 張頁首資料地圖 = 11 個 subheader，實際 {len(_titles)}：{_titles}")

    # ⚠️ 關鍵字比對的對象是**目錄列**，不是章節標題 —— 這是刻意的，不是圖方便：
    #    這份關鍵字清單原本比對的是 `st.tabs` 的**子分頁標籤**（「🌤️ 2. 景氣天氣」），
    #    而**目錄短標**才是那些標籤的直接繼承者（「🌤️ 景氣天氣」）。
    #    章節**標題**一直都是另一套字（那一章的標題是「總經天氣預報 — Score → 天氣映射」，
    #    從來就不含「景氣天氣」四個字）—— 拿標題來比對會逼著我們去改標題文字遷就測試，
    #    那是**讓測試去改產品**，方向反了。
    _toc = [c.args[0] for c in fake_st.markdown.call_args_list
            if c.args and isinstance(c.args[0], str) and "📑 目錄" in c.args[0]]
    assert len(_toc) == 1, f"目錄應該恰好畫一次，實際 {len(_toc)} 次"
    for kw in ["Macro Score", "景氣天氣", "健診評等", "吃本金", "再平衡",
               "核心衛星", "汰弱留強",
               "Sheet 資料結構", "全局指標關聯地圖", "宏觀教學文獻"]:
        assert kw in _toc[0], f"目錄少了一章：{kw}"


def test_manual_has_no_phantom_chapters():
    """說明書不得出現「系統沒實作」的幽靈章節標題（原則 3）。

    這三個字串曾經整章存在，但 grep 全 repo 只出現在說明書自己：
    - 台股 TPI 水溫：三個權重常數只有定義→import→re-export，零計算零渲染
    - β 係數分類的兩個標籤：畫面上沒有任何 β 標籤
    修正前本測試會紅（舊行為衝突紅）。
    """
    from ui import tab6_manual as t6
    captured_labels: list = []
    fake_st = _build_fake_st(captured_labels)
    _md_texts: list = []
    fake_st.markdown.side_effect = lambda *a, **kw: _md_texts.append(
        a[0] if a else "")

    with patch.object(t6, "st", fake_st):
        t6.render_manual_tab()

    _all = "\n".join(str(t) for t in _md_texts) + "\n".join(captured_labels)
    for _phantom in ("TPI", "定海神針", "衝鋒陷陣"):
        assert _phantom not in _all, f"說明書仍出現零實作章節關鍵字：{_phantom}"


@pytest.mark.skip(reason="v19.40 PR2: Tab11 宏觀教學文獻 reads _macro_ind from session_state; static-path contract no longer fully applies to tab6")
def test_render_static_path_runs_without_session_state_access():
    """v18.117 B-C.1 PoC 設計準則弱化版：Tab6 靜態 render path（button 未按）
    不應讀寫 session_state。`button=False` 鎖死所有 submit 分支，
    觸發 session_state 即視為違反靜態渲染契約。

    v19.40 PR2：Tab11 宏觀教學文獻 reads st.session_state.get("_macro_ind") → 測試停用。
    _macro_ind stash 契約改由 test_tab1_macro.py 驗守（tab1 寫入路徑）。
    """
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
