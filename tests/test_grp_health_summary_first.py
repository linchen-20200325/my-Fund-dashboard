"""② 持倉體檢 — 5 格結論摘要必須排在整頁**最前面**（2026-09-02 T20）。

拍板線框 Tab 02 的順序是「Form ─ 診斷條件 → 組合健康總分＋警示卡 → 逐檔體檢表」，
也就是**結論先講**。修正前這 5 格（檢查檔數 / 🟢 健康 / 🟡 警示 / 🔴 吃本金 /
累積 TWD 配息）住在 `_render_health_table` 裡，排在 🧭 核心/衛星分布、🎯 選基金、
🔴 淘汰候選紅區、🛡️ 持倉互斥避險**四個區塊之後** —— 使用者要先捲過四塊才看得到
「這次總共幾檔、幾檔在吃本金」。

## 這裡守什麼（三條，缺一不可）

1. **五格都在、名字對**（`==` 比對整組 label 集合，不是 `in`；`in` 會被「原名＋後綴」
   繞過，例如 `🔴 吃本金檔數` ⊃ `🔴 吃本金`）；
2. **它排在下游第一個區塊標題之前** —— 只驗「五格有渲染」擋不住「它還在原地」；
3. **失敗摘要（`st.error`）仍緊排在五格之前**。這一條不是附帶的：2026-08-05 稽核
   「必修 4」刻意把「❌ 有 N 檔抓取失敗」放在 KPI 正上方，因為「檢查檔數」只算成功數，
   使用者看到「1」時必須當場知道另一檔怎麼了。**只搬五格、把失敗摘要留在原地，
   等於把那個修正打回去** —— 所以本檔把「兩者相鄰且順序正確」一起釘住。

## ⚠️ 給下一個人：守衛是會無聲死掉的

把下面任一條斷言用 `if False:` 之類的死分支關掉，pytest 依然報 **PASSED**、
`--collect-only` 的條數**也不會變**。**唯一能偵測守衛還活著的方法就是突變測試**：
把 `_render_health_summary(rows)` 的呼叫搬回 `_render_health_table` 內，本檔必須轉紅。
改動本檔時請重跑一次。
"""
from __future__ import annotations

import pytest

#: 五格的 metric label（`==` 整組比對）。
_KPI_LABELS = {"檢查檔數", "🟢 健康", "🟡 警示", "🔴 吃本金", "累積 TWD 配息 🧮"}

_ROWS_OK = [{"code": "AAA111", "ok": True, "_fund_raw": {},
             "_principal_twd": 1_000_000.0, "fx_spot": 30.0}]
_ROWS_MIXED = _ROWS_OK + [{"code": "BBB222", "ok": False, "error": "測試用失敗"}]


@pytest.fixture()
def _render(monkeypatch):
    """回傳一個 `run(rows) -> events` 的函式；events 是 `(kind, payload)` 事件流。"""
    import services.fx_regime_service as _fxs
    import streamlit as st

    import ui.helpers.fund_checkup as _chk
    import ui.tab_fund_grp_health as T

    monkeypatch.setattr(_fxs, "fx_regime_by_ccy", lambda *a, **k: {}, raising=True)
    monkeypatch.setattr(_chk, "render_fund_checkup",
                        lambda funds, expanded=False: None, raising=True)

    events: list[tuple[str, str]] = []

    class _Col:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def metric(self, label="", *a, **k):
            events.append(("metric", str(label)))

    monkeypatch.setattr(st, "columns", lambda spec, **kw: [
        _Col() for _ in range(spec if isinstance(spec, int) else len(spec))],
        raising=True)
    monkeypatch.setattr(st, "metric",
                        lambda label="", *a, **k: events.append(("metric", str(label))),
                        raising=True)
    monkeypatch.setattr(st, "markdown",
                        lambda body="", **k: events.append(("md", str(body))),
                        raising=True)
    monkeypatch.setattr(st, "error",
                        lambda body="", **k: events.append(("error", str(body))),
                        raising=True)

    def _run(rows):
        events.clear()
        T._render_health_3tables(rows, funds_extra=[{"code": "AAA111", "loaded": True}],
                                 show_screener=False, source_tab="health")
        return list(events)

    return _run


class TestSummaryComesFirst:
    def test_all_five_kpis_are_rendered(self, _render):
        """五格都在、名字對（整組 `==`，不是 `in`）。

        突變：刪掉 `k5.metric("累積 TWD 配息 🧮", …)` → 本條轉紅。
        """
        events = _render(_ROWS_OK)
        got = {p for (k, p) in events if k == "metric"}
        assert _KPI_LABELS <= got, f"少了這幾格：{_KPI_LABELS - got}"

    def test_summary_precedes_every_downstream_section(self, _render):
        """五格必須排在**所有**下游區塊標題之前。

        修正前它排在 🧭 核心/衛星、🎯 選基金、🔴 淘汰紅區、🛡️ 持倉互斥之後。

        突變：把 `_render_health_summary(rows)` 的呼叫從 `_render_health_3tables`
        開頭移回 `_render_health_table` 內 → 本條轉紅
        （`AssertionError: 5 格結論摘要排在這些區塊之後 …`）。
        """
        events = _render(_ROWS_OK)
        first_kpi = next((i for i, (k, p) in enumerate(events)
                          if k == "metric" and p in _KPI_LABELS), None)
        assert first_kpi is not None, "五格一格都沒渲染"
        before = [p for (k, p) in events[:first_kpi]
                  if k == "md" and p.lstrip().startswith("#")]
        assert not before, f"5 格結論摘要排在這些區塊之後：{before}"

    def test_failure_summary_stays_immediately_above_the_kpis(self, _render):
        """失敗摘要必須**緊排在**五格之前（2026-08-05 必修 4，搬家時不得拆散）。

        突變：把 `if err_rows: st.error(...)` 留在 `_render_health_table`、
        只把五格搬上來 → 本條轉紅（`AssertionError: 失敗摘要沒有排在 5 格之前`）。
        """
        events = _render(_ROWS_MIXED)
        first_kpi = next((i for i, (k, p) in enumerate(events)
                          if k == "metric" and p in _KPI_LABELS), None)
        errs = [i for i, (k, p) in enumerate(events)
                if k == "error" and "抓取失敗" in p]
        assert first_kpi is not None, "五格一格都沒渲染"
        assert errs, "有失敗的檔，卻沒有印出前置的失敗摘要"
        assert errs[0] < first_kpi, "失敗摘要沒有排在 5 格之前（檢查檔數只算成功數）"
        # 兩者之間不得夾任何區塊標題 —— 夾了就不叫「緊排在之前」。
        between = [p for (k, p) in events[errs[0] + 1:first_kpi]
                   if k == "md" and p.lstrip().startswith("#")]
        assert not between, f"失敗摘要與 5 格之間夾了區塊標題：{between}"
