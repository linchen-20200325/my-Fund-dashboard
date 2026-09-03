"""② 持倉體檢 —「🎯 選基金（低基期）」四個篩選控制項必須包在 `st.form` 裡（2026-09-02 T3）。

拍板線框 Rule 02：「篩選、輸入框、滑桿一律 `st.form` 包住，按『套用』才運算。」

## 成本在哪（不是在篩選本身）

`services.fund_screening.screen_funds` 是 L2 純函式，輸入已經在記憶體裡，很便宜。
真正貴的是**它上游那一輪頁面 rerun**：這四個控制項原本是裸 widget，撥一下就觸發整頁
rerun，而 `render_fund_grp_health_tab` 在旗標已設的狀態下每一輪都會重跑
`_run_batch_health()`（逐檔打 MoneyDJ / FundClear）。四個控制項各撥一下 = 四輪。

所以本檔守的是「**widget 在不在 form 裡**」，不是「篩選有沒有被 gate 住」——
本區刻意不 gate `screen_funds`（理由就地寫在 `_render_low_base_screener` 內）。

## ⚠️ 給下一個人：守衛是會無聲死掉的

把下面任一條斷言用 `if False:` 之類的死分支關掉，pytest 依然報 **PASSED**、
`--collect-only` 的條數**也不會變**。**唯一能偵測守衛還活著的方法就是突變測試**：
把 form 拆掉、四個 widget 拉回裸呼叫，本檔必須轉紅。改動本檔時請重跑一次。
"""
from __future__ import annotations

#: 四個篩選控制項的 label（== 比對，不用 `in` —— 「原名＋後綴」就能繞過子字串比對）。
_EXPECTED_LABELS = {
    "幣別（外幣/台幣）",
    "基金類別",
    "只留不吃本金（綠/黃燈）",
    "只留低基期",
}

_OK_ROWS = [{
    "code": "AAA111",
    "基金名": "PROBE FUND",
    "ccy": "USD",
    "_fund_raw": {
        "fund_name": "PROBE FUND",
        "series": [],
        "currency": "USD",
        "moneydj_raw": {"category": "全球股票"},
    },
}]


class _Rec:
    """記錄每個 widget 被呼叫時的 form 巢狀深度。`st.columns` 回的 column 物件也要記。"""

    def __init__(self, monkeypatch):
        import streamlit as st

        self.depth = 0
        self.calls: list[tuple[str, int, object]] = []
        _self = self

        class _Form:
            def __init__(self, key):
                self.key = key

            def __enter__(self):
                _self.depth += 1
                return self

            def __exit__(self, *exc):
                _self.depth -= 1
                return False

        def _rec(name, ret):
            def _fn(*a, **k):
                _self.calls.append((name, _self.depth, (a[0] if a else k.get("label"))))
                return ret
            return _fn

        class _Col:
            """欄物件：`_cc1.checkbox(...)` 這種寫法必須跟 `st.checkbox` 記同一份。"""

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def checkbox(self, *a, **k):
                return _rec("checkbox", False)(*a, **k)

            def multiselect(self, *a, **k):
                return _rec("multiselect", [])(*a, **k)

        monkeypatch.setattr(st, "form", lambda key=None, **kw: _Form(key), raising=True)
        monkeypatch.setattr(st, "columns", lambda spec, **kw: [
            _Col() for _ in range(spec if isinstance(spec, int) else len(spec))],
            raising=True)
        monkeypatch.setattr(st, "multiselect", _rec("multiselect", []), raising=True)
        monkeypatch.setattr(st, "checkbox", _rec("checkbox", False), raising=True)
        monkeypatch.setattr(
            st, "form_submit_button", _rec("form_submit_button", False), raising=True)

    def labels_of(self, *names: str) -> set:
        return {c[2] for c in self.calls if c[0] in names}


def _run(monkeypatch) -> _Rec:
    import ui.tab_fund_grp_health as T
    rec = _Rec(monkeypatch)
    T._render_low_base_screener(_OK_ROWS)
    return rec


class TestLowBaseScreenerFilters:
    def test_all_four_filters_render_inside_a_form(self, monkeypatch):
        """四個篩選控制項**都**要在 form 內（深度 > 0）。

        突變：把 `with applied_form("lb_screener_filters"):` 拆掉 → 本條轉紅
        （`AssertionError: 這些篩選控制項在 form 外面 …`）。
        """
        rec = _run(monkeypatch)
        widgets = [c for c in rec.calls if c[0] in ("multiselect", "checkbox")]
        assert widgets, "四個篩選控制項一個都沒渲染 —— 這一區壞了，不是通過"
        outside = [(n, lbl) for (n, d, lbl) in widgets if d == 0]
        assert not outside, f"這些篩選控制項在 form 外面（撥一下就整頁重跑）：{outside}"

    def test_the_four_expected_controls_are_all_there(self, monkeypatch):
        """數量與身分都要對 —— 只驗「有東西在 form 裡」會被「少畫一個」矇混過去。

        用 `==` 比對整組 label 集合（不是 `in`）：`in` 會被「原名＋後綴」繞過。

        突變：把 `只留低基期` 那個 checkbox 移到 form 外 → 上一條轉紅；
              把它整個刪掉 → 本條轉紅（`AssertionError: form 內的篩選控制項對不上 …`）。
        """
        rec = _run(monkeypatch)
        got = {lbl for (n, d, lbl) in rec.calls
               if n in ("multiselect", "checkbox") and d > 0}
        assert got == _EXPECTED_LABELS, (
            f"form 內的篩選控制項對不上：多了 {got - _EXPECTED_LABELS}、"
            f"少了 {_EXPECTED_LABELS - got}"
        )

    def test_form_has_a_submit_button(self, monkeypatch):
        """form 少了送出鈕，Streamlit 會在**跑到這一頁時**才丟例外（不是寫的時候）。

        突變：拆掉 form → `form_submit_button` 一次都不會被呼叫 → 本條轉紅。
        """
        rec = _run(monkeypatch)
        subs = [c for c in rec.calls if c[0] == "form_submit_button"]
        assert subs, "沒有 form_submit_button"
        assert all(d > 0 for (_n, d, _l) in subs), "送出鈕開在 form 外面"
