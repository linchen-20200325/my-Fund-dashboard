"""③ 基金研究 / ⑤ 設定與診斷 兩個合併頁的 **section 級隔離** 守衛。

## 為什麼需要這一檔（不是為了好看，是七→五製造出來的新風險）

`app.py` 的五段 try/except 是**分頁級**隔離：一個分頁炸掉，其他四個還在。
七→五之前這樣就夠了 —— 因為一個分頁裡通常只裝一件事。

七→五之後不是了：
- **⑤** 一頁同時裝著「🔌 連線與帳號 / 🗄️ 資料維護與通報 / 🔭 資料診斷 / 📖 說明書」。
  這四塊在舊七分頁時代分屬 `tab_manage` 與 `tab_ref` **兩個**分頁、各有自己的 try。
  合併之後它們共用 ⑤ 的**同一個** try →
  **管理室當掉會一併帶走 🔭 資料診斷與 📖 說明書。**
  而那兩塊正是使用者出事時要去的地方（⑤ 的一句話職責：「東西沒抓到的時候來這裡查」）。
- **③** 一頁裝著共用頂部的「找代號」工具（唯一會打外部網路的區塊）＋ 兩個模式本體。
  不隔離的話，一次搜尋例外會連模式切換鍵一起帶走 —— 使用者連換去另一個模式都做不到。

## 方法：sentinel（行為），不是 AST（形狀）

**刻意不用 AST。** 「有沒有 try」是形狀；本檔要驗的是「**那個 try 有沒有用**」——
讓某一個分區真的丟例外，然後數其他分區有沒有照樣渲染。
形狀對了但機制壞掉（例如 `safe_section` 把例外再往上拋）AST 測不出來。

## 每一條的突變實驗寫在各自的 docstring 裡。
"""
from __future__ import annotations

import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]


class _Col:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture()
def fake_st(monkeypatch):
    """把 streamlit 換成記錄器：只記「畫了什麼」，不做逐字斷言。"""
    import streamlit as st

    drawn: list[tuple] = []
    session: dict = {}

    def _api(name):
        def _f(*a, **k):
            drawn.append((name, a[0] if a else None))
            return None
        return _f

    for _n in ("markdown", "caption", "info", "success", "warning", "error",
               "divider", "write", "metric", "dataframe", "subheader",
               "header", "code", "text", "json", "table", "plotly_chart"):
        monkeypatch.setattr(st, _n, _api(_n), raising=False)
    monkeypatch.setattr(st, "columns",
                        lambda spec, **k: [_Col() for _ in range(
                            spec if isinstance(spec, int) else len(spec))],
                        raising=False)
    monkeypatch.setattr(st, "container", lambda *a, **k: _Col(), raising=False)
    monkeypatch.setattr(st, "expander", lambda *a, **k: _Col(), raising=False)
    monkeypatch.setattr(st, "spinner", lambda *a, **k: _Col(), raising=False)
    monkeypatch.setattr(st, "session_state", session, raising=False)
    monkeypatch.setattr(st, "checkbox", lambda *a, **k: False, raising=False)
    monkeypatch.setattr(st, "radio", lambda _l, opts, **k: opts[0], raising=False)
    monkeypatch.setattr(st, "button", lambda *a, **k: False, raising=False)
    monkeypatch.setattr(st, "text_input", lambda *a, **k: "", raising=False)
    monkeypatch.setattr(st, "selectbox", lambda _l, opts, **k: (opts or [None])[0],
                        raising=False)
    return drawn


def _headings(drawn) -> list[str]:
    """畫出來的分區標題（`subheader` 的第一個參數）。"""
    return [str(a) for n, a in drawn if n == "subheader"]


# ══════════════════════════════════════════════════════════════════
# ⑤ 設定與診斷
# ══════════════════════════════════════════════════════════════════
def test_settings_diag_one_broken_section_does_not_take_the_others(
        fake_st, monkeypatch):
    """⑤：**管理室炸掉，🔭 資料診斷與 📖 說明書必須照樣畫出來。**

    這是本檔最重要的一條 —— 它就是七→五製造出來的那個風險本身。

    突變實驗（2026-08-31 實跑，PR 突變表 F-M4）：把
    `ui/tab_settings_diag.py::render_settings_diag_tab` 的
    `safe_section("🗄️ 資料維護與通報", _render_maintain_section)`
    改回直接 `_render_maintain_section()` → **本條轉紅**
    （例外外拋，`🔭 資料診斷` 與 `📖 說明書` 兩個 subheader 一個都沒畫）。
    ⚠️ 該突變**確實改變行為**（不是只改寫法）：轉紅時畫出來的分區標題數
    由 4 掉到 2，且例外直接逸出 `render_settings_diag_tab()`。
    """
    import ui.tab_settings_diag as sd

    _boom = RuntimeError("管理室模擬故障")

    def _explode() -> None:
        raise _boom

    monkeypatch.setattr(sd, "_render_maintain_section", _explode)
    monkeypatch.setattr(sd, "_render_conn_section", lambda: None)
    # 資料診斷有 checkbox gate（fake 回 False）→ 只會畫標題 + 灰色說明，不打網路
    monkeypatch.setattr(sd, "_render_manual_section",
                        lambda: __import__("streamlit").subheader("📖 說明書"))

    # 不得外拋 —— 一旦外拋，app.py 的分頁級 try 會把整個 ⑤ 換成一則錯誤訊息
    sd.render_settings_diag_tab()

    _h = _headings(fake_st)
    assert "🔭 資料診斷" in _h, (
        f"管理室炸掉之後「🔭 資料診斷」沒有被畫出來 —— 分區沒有隔離。實際畫了：{_h}")
    assert "📖 說明書" in _h, (
        f"管理室炸掉之後「📖 說明書」沒有被畫出來 —— 分區沒有隔離。實際畫了：{_h}")

    # 失敗本身必須**顯式紅燈**，不能靜默吞（CLAUDE.md §1）
    _errs = [a for n, a in fake_st if n == "error"]
    assert any("資料維護與通報" in str(a) for a in _errs), (
        f"分區失敗沒有就地顯示紅燈 —— 那會變成靜默吞例外。error 呼叫：{_errs}")


def test_settings_diag_all_four_sections_are_isolated(fake_st, monkeypatch):
    """⑤ 的**每一個**分區都要隔離，不是只挑一個做。

    逐一讓其中一個分區爆炸，其餘三個都必須照畫。

    突變實驗（2026-08-31 實跑）：把**任一**個 `safe_section(...)` 改回直接呼叫
    → **本條轉紅**（該分區爆炸那一輪，其後的分區不會被畫）。
    """
    import ui.tab_settings_diag as sd

    _names = ["_render_conn_section", "_render_maintain_section",
              "_render_diag_section", "_render_manual_section"]
    for _victim in _names:
        _drawn: list[tuple] = []
        with pytest.MonkeyPatch.context() as _mp:
            import streamlit as st
            _mp.setattr(st, "subheader",
                        lambda *a, **k: _drawn.append(("subheader", a[0] if a else None)),
                        raising=False)
            for _n in _names:
                if _n == _victim:
                    _mp.setattr(sd, _n, _make_exploder(), raising=False)
                else:
                    _mp.setattr(sd, _n, _make_marker(_n), raising=False)
            sd.render_settings_diag_tab()   # 不得外拋
        _ok = {a for n, a in _drawn if n == "subheader"}
        _expected = {_n for _n in _names if _n != _victim}
        assert _expected <= _ok, (
            f"{_victim} 爆炸時，這些分區沒被畫出來：{sorted(_expected - _ok)}")


def _make_exploder():
    def _f() -> None:
        raise RuntimeError("模擬故障")
    return _f


def _make_marker(name: str):
    def _f() -> None:
        import streamlit as st
        st.subheader(name)
    return _f


# ══════════════════════════════════════════════════════════════════
# ③ 基金研究
# ══════════════════════════════════════════════════════════════════
def test_fund_research_code_finder_failure_keeps_the_mode_switch(
        fake_st, monkeypatch):
    """③：「找代號」工具炸掉，**模式切換鍵與模式本體必須還在**。

    「找代號」是本頁唯一會打外部網路的區塊（`tdcc_search_fund` → TDCC / FundClear），
    也就是最可能失敗的那一塊。不隔離的話，一次搜尋失敗會讓使用者連
    「切去批次掃描」都做不到。

    突變實驗（2026-08-31 實跑，PR 突變表 F-M4b）：把
    `ui/tab_fund_research.py::_render_shared_top` 的
    `safe_section("🔍 找代號", render_code_finder)` 改回 `render_code_finder()`
    → **本條轉紅**（例外外拋，`_render_single_mode` 從未被呼叫）。
    """
    import ui.tab_fund_research as fr

    monkeypatch.setattr(fr, "render_code_finder", _make_exploder())
    _mode_ran: list[str] = []
    monkeypatch.setattr(fr, "_render_single_mode",
                        lambda: _mode_ran.append("single"))
    monkeypatch.setattr(fr, "_render_batch_mode",
                        lambda: _mode_ran.append("batch"))

    fr.render_fund_research_tab()   # 不得外拋

    assert _mode_ran == ["single"], (
        f"找代號工具炸掉之後模式本體沒有跑 —— 共用頂部沒有隔離。實際：{_mode_ran}")
    _errs = [a for n, a in fake_st if n == "error"]
    assert any("找代號" in str(a) for a in _errs), (
        f"找代號失敗沒有就地顯示紅燈（靜默吞例外違 §1）。error 呼叫：{_errs}")


def test_fund_research_mode_failure_keeps_the_shared_top(fake_st, monkeypatch):
    """③：模式本體炸掉，**共用頂部（大標 + 找代號 + 切換鍵）必須還在**。

    否則使用者被卡在一個炸掉的模式裡，連切回另一個模式的 radio 都消失了。

    突變實驗（2026-08-31 實跑，PR 突變表 F-M4c）：把
    `safe_section(MODE_SINGLE, _render_single_mode)` 改回 `_render_single_mode()`
    → **本條轉紅**。
    """
    import ui.tab_fund_research as fr

    _top_ran: list[str] = []
    monkeypatch.setattr(fr, "render_code_finder",
                        lambda: _top_ran.append("code_finder"))
    monkeypatch.setattr(fr, "_render_single_mode", _make_exploder())

    fr.render_fund_research_tab()   # 不得外拋

    assert _top_ran == ["code_finder"], "共用頂部沒有畫"
    _errs = [a for n, a in fake_st if n == "error"]
    assert _errs, "模式本體失敗沒有就地顯示紅燈（靜默吞例外違 §1）"


# ══════════════════════════════════════════════════════════════════
# safe_section 本身
# ══════════════════════════════════════════════════════════════════
def test_safe_section_does_not_swallow_silently(fake_st):
    """`safe_section` 必須**顯式紅燈 + 不外拋**，兩者缺一不可。

    只做「不外拋」＝ `except: pass`，直接違 `CLAUDE.md §1`（掩蓋而非解決）。

    突變實驗（2026-08-31 實跑，PR 突變表 F-M4d）：把
    `ui/helpers/render_state.py::safe_section` 的 `system_error(...)` 那一行刪掉
    （只留 `except Exception: pass` 的效果）→ **本條轉紅**。
    """
    from ui.helpers.render_state import safe_section

    def _boom() -> None:
        raise ValueError("測試用例外")

    safe_section("測試分區", _boom)          # 不得外拋
    _errs = [a for n, a in fake_st if n == "error"]
    assert any("測試分區" in str(a) for a in _errs), (
        f"safe_section 靜默吞掉了例外（§1 違憲）。error 呼叫：{_errs}")


def test_safe_section_passes_through_args_and_return(fake_st):
    """正常路徑：參數要原樣傳進去，且不得把成功也當失敗。"""
    from ui.helpers.render_state import safe_section

    _got: list[tuple] = []
    safe_section("x", lambda *a, **k: _got.append((a, k)), 1, 2, key="v")
    assert _got == [((1, 2), {"key": "v"})], f"參數沒有原樣傳遞：{_got}"
    assert not [a for n, a in fake_st if n == "error"], "成功路徑不該畫紅燈"
