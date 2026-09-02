"""② 持倉體檢 — 健診大表上面只准有**一個**標題（2026-09-02 T19）。

## 病徵

這一頁只有一張 dataframe，但它上面原本印了**兩個 h4 標題**：

    #### 📊 健診大表（①②③ 已去重複合併成一張;橫向可滾動）     ← _render_health_3tables 印
    …（新鮮度 banner／失敗摘要／5 格 KPI／🩺 體檢 PK）…
    #### 健診總表（🧮 = 自行換算欄位）                          ← _render_health_table 印
    <dataframe>

兩句在講同一張表，中間還隔著好幾個區塊 —— 使用者會以為底下有兩張表，捲到最後只找得到一張。

## 修法與這裡守什麼

合併成單一 `_BIG_TABLE_HEADING` 常數（兩邊原本各自帶的資訊一項不減），並且讓它印在
**緊貼 dataframe** 的位置。本檔用實跑渲染來守三件事：

1. 整頁 `st.markdown` 出來的 h4 標題裡，**提到「健診大表 / 健診總表」的恰好一個**；
2. 那個標題與 `st.dataframe` 之間**不再夾著別的 h4 標題**（否則等於又分家了）；
3. 全失敗 early-return 路徑也印同一個標題字串（D2：至少讓使用者看到「這裡本來有一張表」）。

⚠️ 用 `==` 比對整個標題字串，不是 `in`：`in` 會被「原名＋後綴」繞過
（例如有人加一個 `#### 健診大表（舊版）` 就照樣通過）。

## ⚠️ 給下一個人：守衛是會無聲死掉的

把下面任一條斷言用 `if False:` 之類的死分支關掉，pytest 依然報 **PASSED**、
`--collect-only` 的條數**也不會變**。**唯一能偵測守衛還活著的方法就是突變測試**：
把第二個標題加回去，本檔必須轉紅。改動本檔時請重跑一次。
"""
from __future__ import annotations

import pytest

_ROWS = [{"code": "AAA111", "ok": True, "_fund_raw": {},
          "_principal_twd": 1_000_000.0, "fx_spot": 30.0}]


@pytest.fixture()
def _rendered(monkeypatch):
    """實跑 `_render_health_3tables`，回傳 `[(kind, payload), …]` 的渲染事件流。"""
    import services.fx_regime_service as _fxs
    import streamlit as st

    import ui.helpers.fund_checkup as _chk
    import ui.tab_fund_grp_health as T

    monkeypatch.setattr(_fxs, "fx_regime_by_ccy", lambda *a, **k: {}, raising=True)
    monkeypatch.setattr(_chk, "render_fund_checkup",
                        lambda funds, expanded=False: None, raising=True)

    events: list[tuple[str, str]] = []
    monkeypatch.setattr(st, "markdown",
                        lambda body="", **k: events.append(("md", str(body))),
                        raising=True)
    monkeypatch.setattr(st, "dataframe",
                        lambda *a, **k: events.append(("df", "")), raising=True)

    T._render_health_3tables(_ROWS, funds_extra=[{"code": "AAA111", "loaded": True}],
                             show_screener=False, source_tab="health")
    return events


def _h4_titles(events) -> list[str]:
    return [b for (k, b) in events if k == "md" and b.startswith("####")]


class TestSingleBigTableHeading:
    def test_exactly_one_big_table_heading(self, _rendered):
        """整頁只准出現一個「這是那張大表」的標題。

        突變：把 `#### 健診總表（🧮 = 自行換算欄位）` 加回 `_render_health_table` →
        本條轉紅（`AssertionError: 健診大表上面有 2 個標題 …`）。
        """
        import ui.tab_fund_grp_health as T

        titles = _h4_titles(_rendered)
        about_table = [t for t in titles
                       if ("健診大表" in t) or ("健診總表" in t)]
        assert len(about_table) == 1, (
            f"健診大表上面有 {len(about_table)} 個標題（應恰好 1 個）：{about_table}"
        )
        assert about_table[0] == T._BIG_TABLE_HEADING, (
            f"標題文字不是 SSOT 常數：{about_table[0]!r} != {T._BIG_TABLE_HEADING!r}"
        )

    def test_nothing_h4_between_the_heading_and_the_table(self, _rendered):
        """標題與 dataframe 之間不得再夾一個 h4 —— 夾了就等於又分成兩張表。

        突變：在 `st.dataframe(...)` 前面插一個 `st.markdown("#### 健診總表")` →
        本條轉紅（`AssertionError: 標題與表格之間夾了 h4 …`）。
        """
        import ui.tab_fund_grp_health as T

        idx_head = [i for i, (k, b) in enumerate(_rendered)
                    if k == "md" and b == T._BIG_TABLE_HEADING]
        idx_df = [i for i, (k, _b) in enumerate(_rendered) if k == "df"]
        assert idx_head, "健診大表標題沒有被印出來"
        assert idx_df, "健診大表沒有被渲染（st.dataframe 一次都沒被呼叫）"
        head, first_df_after = idx_head[0], min(i for i in idx_df if i > idx_head[0])
        between = [b for (k, b) in _rendered[head + 1:first_df_after]
                   if k == "md" and b.startswith("####")]
        assert not between, f"標題與表格之間夾了 h4：{between}"

    def test_all_fetch_failed_path_prints_the_same_heading(self, monkeypatch):
        """全失敗 early-return 也要印**同一個**標題（D2），不能各寫各的字面值。

        突變：把 early-return 的 `st.markdown(_BIG_TABLE_HEADING)` 改回手抄字串 →
        本條轉紅（`AssertionError: 全失敗路徑印的標題不是 SSOT 常數 …`）。
        """
        import streamlit as st

        import ui.tab_fund_grp_health as T

        events: list[str] = []
        monkeypatch.setattr(st, "markdown",
                            lambda body="", **k: events.append(str(body)), raising=True)
        monkeypatch.setattr(st, "error", lambda *a, **k: None, raising=True)

        T._render_health_3tables(
            [{"code": "AAA111", "ok": False, "error": "測試用失敗"}],
            funds_extra=[], show_screener=False, source_tab="health")

        heads = [e for e in events if e.startswith("####")]
        assert T._BIG_TABLE_HEADING in heads, (
            f"全失敗路徑印的標題不是 SSOT 常數：{heads}"
        )
