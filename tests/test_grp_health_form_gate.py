"""② 持倉體檢 —「診斷條件」必須包在 `st.form` 裡（2026-09-02 T1）。

拍板線框（`docs/wireframes/ia-wireframe.html` Rule 02 ＋ Tab 02「Form ─ 診斷條件」）就地
點名了這一頁的現況：「**目前每拉一格全頁重繪，本次一併修掉**」。

## 為什麼這一頁特別貴

`render_fund_grp_health_tab` 的重運算是 `_run_batch_health()`（逐檔打 MoneyDJ / FundClear
抓淨值與配息）＋ `record_batch_nav_points()`（往 Google Sheets 的 nav_history 分頁 append）。
沒有 form 時，使用者在「本金」按一下上下鍵就會觸發一輪完整 rerun —— 對外部來源是一次
白打的往返。

## 這裡守的是**行為**，不是關鍵字

`ui/helpers/ia/gated_form.py` 的 docstring 自己就寫了這條規則最常見的漏法：
「`with st.form(...)` 有寫、`form_submit_button` 也有寫，**但回傳值沒有被拿去 gate 運算**
→ form 只擋住了 widget 互動，重運算照跑，畫面看起來沒問題、成本一分沒省。」
一個 `assert "st.form" in src` 的檢查**完全看不到**那種寫法。

所以本檔實跑 `render_fund_grp_health_tab()`，記錄：
- 每個輸入 widget 被呼叫時**當下的 form 巢狀深度**（>0 才算在 form 內）；
- 送出鈕回 False 時，`_run_batch_health` 有沒有被呼叫（必須沒有）；
- 送出鈕回 True 時，`_run_batch_health` 有沒有被呼叫（必須有 —— 否則是「gate 太緊，
  按了也沒反應」，那是另一半的錯，同樣要擋）。

## ⚠️ 給下一個人：守衛是會無聲死掉的

把下面任一條斷言用 `if False:` / 提早 `return` 之類的死分支關掉，pytest 依然報 **PASSED**、
`--collect-only` 的條數**也不會變** —— 「守衛死掉」看起來比「守衛活著」更綠。
**唯一能偵測守衛還活著的方法就是突變測試**：把 form 拆回裸 widget，本檔必須轉紅。
改動本檔時請重跑一次突變。
"""
from __future__ import annotations

import pytest


#: 會讓使用者「改一格就重跑」的互動 widget。form 內才允許出現。
_INPUT_WIDGETS = (
    "text_area", "text_input", "number_input", "slider", "select_slider",
    "selectbox", "multiselect", "checkbox", "radio", "toggle", "date_input",
)


class _FormRecorder:
    """把 `st.form` 換成會記深度的假物件，其餘 widget 記下呼叫當下的深度。"""

    def __init__(self, monkeypatch, *, submit: bool):
        import streamlit as st

        self.depth = 0
        self.calls: list[tuple[str, int, object]] = []
        self._submit = submit
        _self = self

        class _Form:
            def __init__(self, key):
                self.key = key

            def __enter__(self):
                _self.depth += 1
                _self.calls.append(("__form_enter__", _self.depth, self.key))
                return self

            def __exit__(self, *exc):
                _self.calls.append(("__form_exit__", _self.depth, self.key))
                _self.depth -= 1
                return False

        monkeypatch.setattr(st, "form", lambda key=None, **kw: _Form(key), raising=True)

        def _rec(name, ret):
            def _fn(*a, **k):
                _self.calls.append((name, _self.depth, (a[0] if a else k.get("label"))))
                return ret
            return _fn

        for _w in _INPUT_WIDGETS:
            monkeypatch.setattr(st, _w, _rec(_w, ""), raising=True)
        # 代號框要回一個非空值，否則主流程會在「請至少輸入 1 個基金代號」就 return，
        # 那樣 gate=True 的那一條會驗不到東西。
        monkeypatch.setattr(st, "text_area", _rec("text_area", "AAA111"), raising=True)
        monkeypatch.setattr(st, "number_input", _rec("number_input", 1_000_000.0), raising=True)
        monkeypatch.setattr(st, "checkbox", _rec("checkbox", False), raising=True)
        monkeypatch.setattr(st, "multiselect", _rec("multiselect", []), raising=True)
        monkeypatch.setattr(st, "button", _rec("button", False), raising=True)
        monkeypatch.setattr(
            st, "form_submit_button", _rec("form_submit_button", submit), raising=True)

    def named(self, name: str) -> list[tuple[str, int, object]]:
        return [c for c in self.calls if c[0] == name]


def _run(monkeypatch, *, submit: bool):
    """實跑 ② 分頁 render，回傳 (recorder, 重運算被呼叫幾次)。"""
    import ui.tab_fund_grp_health as T

    rec = _FormRecorder(monkeypatch, submit=submit)

    heavy: list = []
    monkeypatch.setattr(
        T, "_run_batch_health",
        lambda *a, **k: heavy.append(a) or [], raising=True)
    # 不打外網／不寫 Google Sheets。`get_latest_vix` 在 submit=True 的路徑上是**無條件**
    # 呼叫的（235 加碼水位那一段），不擋掉的話這條測試會真的去打 Yahoo。
    import services.fund_service as _fs
    import ui.helpers.nav_history_hook as _nh
    monkeypatch.setattr(_nh, "record_batch_nav_points", lambda *a, **k: None, raising=True)
    monkeypatch.setattr(_fs, "get_latest_vix", lambda *a, **k: None, raising=True)

    # 每條測試都從乾淨的「還沒跑過」狀態開始（session_state 是跨測試存活的）。
    import streamlit as st
    try:
        st.session_state.pop("_fund_grp_health_ran", None)
    except Exception:      # noqa: BLE001 — bare mode 沒有 session context 時忽略
        pass

    T.render_fund_grp_health_tab()
    return rec, len(heavy)


class TestDiagnosisInputsAreInsideAForm:
    def test_every_input_widget_is_called_inside_an_open_form(self, monkeypatch):
        """輸入 widget 被呼叫的**那一刻**必須有一個 form 開著（深度 > 0）。

        突變：把 `with applied_form(...)` 整段拆掉、widget 拉回裸呼叫 → 本條轉紅
        （`AssertionError: 這些輸入 widget 在 form 外面 …`）。
        """
        rec, _ = _run(monkeypatch, submit=False)
        outside = [(n, lbl) for (n, d, lbl) in rec.calls
                   if n in _INPUT_WIDGETS and d == 0]
        assert not outside, (
            f"這些輸入 widget 在 form 外面（改一格就整頁重跑）：{outside}"
        )
        # 光是「沒有 widget 在外面」還不夠 —— 一個什麼都沒畫的頁面也滿足它。
        assert rec.named("text_area"), "代號輸入框沒有被渲染 —— 這一頁壞了，不是通過"
        assert rec.named("number_input"), "本金輸入框沒有被渲染 —— 這一頁壞了，不是通過"

    def test_a_submit_button_exists(self, monkeypatch):
        """form 必須有送出鈕，且它必須開在 form 裡面。

        突變：拆掉 form → `form_submit_button` 一次都不會被呼叫 → 本條轉紅。
        """
        rec, _ = _run(monkeypatch, submit=False)
        subs = rec.named("form_submit_button")
        assert subs, "沒有 form_submit_button —— Streamlit 會在跑到這一頁時才丟例外"
        assert all(d > 0 for (_n, d, _l) in subs), "送出鈕開在 form 外面"

    def test_heavy_work_is_gated_by_submit(self, monkeypatch):
        """**沒按送出就不准重抓**：`_run_batch_health` 一次都不能被呼叫。

        這一條擋的是 `gated_form` docstring 點名的那種假 form：form 有包、送出鈕也有，
        但回傳值沒被拿去 gate → 每次 rerun 照樣重抓。

        突變：把 `if _health_gate:` 改成 `if True:` → 本條轉紅
        （`AssertionError: 沒按送出就重抓了 1 次`）。
        """
        _rec, n_heavy = _run(monkeypatch, submit=False)
        assert n_heavy == 0, f"沒按送出就重抓了 {n_heavy} 次（form 沒有 gate 住重運算）"

    def test_pressing_submit_actually_runs_the_diagnosis(self, monkeypatch):
        """按下送出**必須**真的跑一次 —— 防「gate 太緊，按了沒反應」。

        突變：把 `if _health_gate:` 改成 `if False:` → 本條轉紅
        （`AssertionError: 按了送出卻沒有跑健診`）。
        """
        _rec, n_heavy = _run(monkeypatch, submit=True)
        assert n_heavy == 1, f"按了送出卻沒有跑健診（實際呼叫 {n_heavy} 次）"
