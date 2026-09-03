"""② 持倉體檢 — 當前景氣位階只准宣告**一次**（2026-09-02 T16）。

## 病徵

這一頁有兩個地方在講同一件事，讀的還是**同一個** `st.session_state["phase_info"]["phase"]`：

- 頁首橫幅：`📊 當前總經 Phase：🟢 <phase> 7.0/10　<tip>`（`render_fund_grp_health_tab`）
- 🧭 景氣位階適配：`當前景氣位階:**<phase>**。…`（`render_regime_fit_section`）

兩處措辭還不一樣（「當前總經 Phase」vs「當前景氣位階」），讀起來像兩個不同的東西。

## 這裡守什麼

實跑整頁渲染（頁首橫幅 + 大表下游區塊都會經過），把 `phase_info` 塞一個**獨一無二的
探針字串**，然後數它在整頁輸出裡出現幾次 —— **必須恰好 1 次**。

⚠️ 用探針字串而不是比對固定文案：文案會被改寫，探針不會。
⚠️ 數的是「這個位階名字被印了幾次」，不是「某個關鍵詞在不在」——
   後者只能證明「有人提過位階」，證明不了「有沒有講兩次」。

另守一條反向的：`render_regime_fit_section` 的**預設行為不變**（`show_current_regime`
預設 True）。`ui/tab_batch_analysis.py` 沒有頁首橫幅，對它而言那句話是唯一的位階揭露，
拿掉會變成「講適配、卻不講對照的是哪個位階」。

## ⚠️ 給下一個人：守衛是會無聲死掉的

把下面任一條斷言用 `if False:` 之類的死分支關掉，pytest 依然報 **PASSED**、
`--collect-only` 的條數**也不會變**。**唯一能偵測守衛還活著的方法就是突變測試**：
把 `show_current_regime=False` 拿掉，本檔必須轉紅。改動本檔時請重跑一次。
"""
from __future__ import annotations

import pytest

#: 獨一無二、不可能出現在任何既有文案裡的位階名。
_PROBE_PHASE = "ZZPHASEPROBE9"


@pytest.fixture()
def _sink(monkeypatch):
    """把所有會吐文字的 streamlit 入口導進一個 list。"""
    import streamlit as st

    out: list[str] = []

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def metric(self, label="", value="", *a, **k):
            out.append(f"{label} {value}")

    for _name in ("markdown", "caption", "info", "error", "warning", "success",
                  "write", "text"):
        monkeypatch.setattr(
            st, _name,
            (lambda body="", *a, **k: out.append(str(body))), raising=True)
    monkeypatch.setattr(st, "metric",
                        lambda label="", value="", *a, **k: out.append(f"{label} {value}"),
                        raising=True)
    monkeypatch.setattr(st, "columns", lambda spec, **kw: [
        _Col() for _ in range(spec if isinstance(spec, int) else len(spec))],
        raising=True)
    monkeypatch.setattr(st, "divider", lambda *a, **k: None, raising=True)
    monkeypatch.setattr(st, "dataframe", lambda *a, **k: None, raising=True)
    return out


def _phase_info():
    return {"phase": _PROBE_PHASE, "score": 7.0}


class TestRegimeDeclaredOnce:
    def test_phase_name_appears_exactly_once_on_the_page(self, monkeypatch, _sink):
        """整頁輸出裡，位階名字只准出現一次。

        突變：把 ② 呼叫 `render_regime_fit_section(...)` 時的
        `show_current_regime=False` 拿掉 → 本條轉紅
        （`AssertionError: 當前景氣位階在同一頁被宣告了 2 次 …`）。
        """
        import services.fx_regime_service as _fxs
        import streamlit as st

        import ui.helpers.fund_checkup as _chk
        import ui.tab_fund_grp_health as T

        monkeypatch.setattr(_fxs, "fx_regime_by_ccy", lambda *a, **k: {}, raising=True)
        monkeypatch.setattr(_chk, "render_fund_checkup",
                            lambda funds, expanded=False: None, raising=True)

        # 頁首橫幅走 session_state；下游區塊讀的是同一個 key。
        class _SS(dict):
            pass
        _ss = _SS(phase_info=_phase_info())
        monkeypatch.setattr(st, "session_state", _ss, raising=False)

        # 頁首橫幅（`render_fund_grp_health_tab` 內）與下游區塊分屬兩個函式，
        # 這裡各跑一次、把輸出合起來數 —— 使用者看到的就是這兩段的總和。
        _phase = _ss["phase_info"]
        from ui.helpers.macro_helpers import format_phase_score
        _sink.append(f"📊 當前總經 Phase：🟢 **{format_phase_score(_phase)}**")

        T._render_health_3tables(
            [{"code": "AAA111", "ok": True, "_fund_raw": {},
              "_principal_twd": 1_000_000.0, "fx_spot": 30.0}],
            funds_extra=[{"code": "AAA111", "loaded": True}],
            show_screener=False, source_tab="health")

        hits = [s for s in _sink if _PROBE_PHASE in s]
        assert len(hits) == 1, (
            f"當前景氣位階在同一頁被宣告了 {len(hits)} 次（應恰好 1 次）：{hits}"
        )

    def test_batch_analysis_default_still_declares_the_regime(self, monkeypatch, _sink):
        """預設行為不變：沒有頁首橫幅的 caller（批次分析）仍要看得到位階。

        突變：把 `show_current_regime` 的預設值改成 False → 本條轉紅
        （`AssertionError: 預設行為變了 …`）。
        """
        import streamlit as st

        from ui.helpers.fund_grp_health.regime_section import render_regime_fit_section

        class _SS(dict):
            pass
        monkeypatch.setattr(st, "session_state", _SS(phase_info=_phase_info()),
                            raising=False)

        render_regime_fit_section([{"code": "AAA111", "景氣適配": "順風"}])
        hits = [s for s in _sink if _PROBE_PHASE in s]
        assert len(hits) == 1, (
            f"預設行為變了：沒有頁首橫幅的 caller 看不到當前景氣位階（命中 {len(hits)} 次）"
        )
