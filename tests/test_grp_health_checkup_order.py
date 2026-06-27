"""v19.189 guard — 逐檔財務健診（render_fund_checkup）移到「健診總表」上方。

user 截圖回報：基金組合健檢 tab 的「逐檔財務健診（4 大功能 + 健診摘要表 PK + 健診卡）」
原本顯示在「健診總表（🧮 = 自行換算欄位）」**下方**的「進階分析」區塊，要求上移到
健診總表之上（易讀的摘要 PK 先看到）。

本檔守：
1. tab_fund_grp_health._render_health_table 接收 funds_extra 並在健診總表標題前渲染 checkup。
2. fund_grp_health_extras 不再重複渲染 checkup（避免上下兩份）。
"""
from __future__ import annotations

_HEALTH = "/home/user/my-Fund-dashboard/ui/tab_fund_grp_health.py"
_EXTRAS = "/home/user/my-Fund-dashboard/ui/helpers/fund_grp_health_extras.py"

_HEADING = "健診總表（🧮 = 自行換算欄位）"


def _src(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestCheckupAboveHealthTable:
    def test_health_table_accepts_funds_extra(self):
        src = _src(_HEALTH)
        assert "def _render_health_table(rows" in src, "簽名應為 _render_health_table(rows, ...)"
        assert "funds_extra" in src, "_render_health_table 應接收 funds_extra 供上移渲染"

    def test_checkup_called_before_health_table_heading(self):
        src = _src(_HEALTH)
        assert "render_fund_checkup" in src, "_render_health_table 應呼叫 render_fund_checkup"
        i_chk = src.index("render_fund_checkup")
        i_tbl = src.index(_HEADING)
        assert i_chk < i_tbl, "render_fund_checkup 必須出現在『健診總表』標題之前（上移目標）"

    def test_tab_passes_funds_extra_into_health_table(self):
        src = _src(_HEALTH)
        assert "_render_health_table(rows, funds_extra=" in src, \
            "render_fund_grp_health_tab 應把 funds_extra 傳入 _render_health_table"

    def test_extras_no_longer_renders_checkup(self):
        src = _src(_EXTRAS)
        assert "render_fund_checkup(funds)" not in src, \
            "render_fund_grp_health_extras 不應再渲染 render_fund_checkup（已上移避免上下重複）"
