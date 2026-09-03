"""v19.189 guard — 逐檔財務健診（render_fund_checkup）移到「健診總表」上方。

user 截圖回報：基金組合健檢 tab 的「逐檔財務健診（4 大功能 + 健診摘要表 PK + 健診卡）」
原本顯示在「健診總表（🧮 = 自行換算欄位）」**下方**的「進階分析」區塊，要求上移到
健診總表之上（易讀的摘要 PK 先看到）。

本檔守：
1. tab_fund_grp_health._render_health_table 接收 funds_extra 並在健診大表標題前渲染 checkup。
2. fund_grp_health_extras 不再重複渲染 checkup（避免上下兩份）。

⚠️ **2026-09-02 T19 更新（有意識的修改，不是漏刪）**：本檔原本的順序檢查是
`src.index("健診總表（🧮 = 自行換算欄位）")` —— 拿**原始碼字串位置**當「渲染順序」的代理。
T19 把這一頁上面那兩個 h4 標題（`📊 健診大表…` 與 `健診總表（🧮 = 自行換算欄位）`）
合併成一個之後，那個字串**只剩下註解裡還有**，`src.index()` 於是指到註解、
拿一個註解的位置去跟渲染順序比大小 —— 得到的是一個**看起來有在檢查、實際毫無意義**的結果。
故該條改寫為**實跑渲染、看真正的呼叫順序**（行為斷言）。舊條的用意（checkup 要在大表標題
之前）**一字未改**，換掉的只是它證明這件事的方法。

⚠️ 給下一個人：本檔其餘三條仍是**子字串比對**，保留是因為它們守的是「簽名／有沒有這個
呼叫」這種靜態事實；但要記得子字串看不到「傳進去的值是什麼」——
`tests/test_grp_health_checkup_reachable.py` 才是守可達性的那一份。
"""
from __future__ import annotations

_HEALTH = "ui/tab_fund_grp_health.py"
_EXTRAS = "ui/helpers/fund_grp_health_extras.py"


def _src(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestCheckupAboveHealthTable:
    def test_health_table_accepts_funds_extra(self):
        src = _src(_HEALTH)
        assert "def _render_health_table(rows" in src, "簽名應為 _render_health_table(rows, ...)"
        assert "funds_extra" in src, "_render_health_table 應接收 funds_extra 供上移渲染"

    def test_checkup_rendered_before_the_big_table_heading(self, monkeypatch):
        """實跑渲染：`render_fund_checkup` 必須排在健診大表標題**之前**。

        突變：把 `_render_health_table` 內 `render_fund_checkup(...)` 那一段搬到
        `st.markdown(_BIG_TABLE_HEADING)` 之後 → 本條轉紅
        （`AssertionError: render_fund_checkup 排在健診大表標題之後`）。
        """
        import services.fx_regime_service as _fxs
        import streamlit as st

        import ui.helpers.fund_checkup as _chk
        import ui.tab_fund_grp_health as T

        monkeypatch.setattr(_fxs, "fx_regime_by_ccy", lambda *a, **k: {}, raising=True)
        order: list[str] = []
        monkeypatch.setattr(
            st, "markdown",
            lambda body="", **k: order.append(f"md:{body}"), raising=True)
        monkeypatch.setattr(
            _chk, "render_fund_checkup",
            lambda funds, expanded=False: order.append("checkup"), raising=True)

        T._render_health_3tables(
            [{"code": "AAA111", "ok": True, "_fund_raw": {},
              "_principal_twd": 1_000_000.0, "fx_spot": 30.0}],
            funds_extra=[{"code": "AAA111", "loaded": True}],
            show_screener=False, source_tab="health")

        heads = [i for i, e in enumerate(order)
                 if e == f"md:{T._BIG_TABLE_HEADING}"]
        assert len(heads) == 1, (
            f"健診大表標題應**恰好印一次**，實際 {len(heads)} 次（T19：兩個標題已合成一個）"
        )
        assert "checkup" in order, "render_fund_checkup 沒有被渲染"
        assert order.index("checkup") < heads[0], (
            "render_fund_checkup 排在健診大表標題之後（上移目標是它要先被看到）"
        )

    def test_tab_passes_funds_extra_into_health_table(self):
        src = _src(_HEALTH)
        assert "_render_health_table(rows, funds_extra=" in src, \
            "render_fund_grp_health_tab 應把 funds_extra 傳入 _render_health_table"

    def test_extras_no_longer_renders_checkup(self):
        src = _src(_EXTRAS)
        assert "render_fund_checkup(funds)" not in src, \
            "render_fund_grp_health_extras 不應再渲染 render_fund_checkup（已上移避免上下重複）"
