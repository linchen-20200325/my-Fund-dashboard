"""v19.190 guard — 組合健檢 / 總經 三個 UI bug fix。

user 截圖回報（2026-06-27）：
A. 「多基金績效比較」圖表 + 比較表全顯示 0.00%。根因：v19.148 把欄位改名為
   「X% (全期自算)」，但此圖表/比較表仍讀舊鍵「年化…% 🧮」→ .get() 全 None → 0。
B. 「逐檔財務健診（4 大功能）」上移後預設收合在 expander 內，user 以為「沒有」。
   render_fund_checkup 加 expanded 參數，組合健檢傳 True 直接展開。
C. 總經 tab「持倉紅綠燈」同一檔列出 2-3 次（portfolio_funds 重複載入累積）→ 依 code 去重。
"""
from __future__ import annotations

_GRP = "/home/user/my-Fund-dashboard/ui/tab_fund_grp_health.py"
_CHK = "/home/user/my-Fund-dashboard/ui/helpers/fund_checkup.py"
_MACRO = "/home/user/my-Fund-dashboard/ui/tab1_macro.py"


def _src(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestPerfChartKeys:
    def test_chart_reads_quanqi_keys(self):
        # v19.194 merge reconcile：並行線 v19.180 把欄位拆成「(全期實際)」+「(年化)」，
        # 圖表改取年化（= annual_*_pct，跨檔可比）。
        src = _src(_GRP)
        assert 'r.get("配息率% (年化)")' in src
        assert 'r.get("含息% (年化)")' in src
        assert 'r.get("淨值% (年化)")' in src

    def test_old_renamed_keys_gone(self):
        """v19.148 改名前的舊鍵不得殘留（否則又會讀到 None → 0）。"""
        src = _src(_GRP)
        assert "年化配息率% 🧮" not in src
        assert "含息年化% 🧮" not in src
        assert "年化淨值% 🧮" not in src

    def test_process_one_fund_emits_quanqi_keys(self):
        """確認 row dict 真的有圖表來源的「(年化)」鍵（v19.180 後欄位拆兩套）。"""
        src = _src(_GRP)
        assert '"配息率% (年化)": s[' in src
        assert '"含息% (年化)": s[' in src
        assert '"淨值% (年化)": s[' in src


class TestCheckupExpanded:
    def test_render_fund_checkup_has_expanded_param(self):
        src = _src(_CHK)
        assert "def render_fund_checkup(portfolio_funds: list | None, expanded: bool = False)" in src
        assert "expanded=expanded" in src, "expander 應吃 expanded 參數而非寫死 False"

    def test_grp_health_passes_expanded_true(self):
        src = _src(_GRP)
        assert "render_fund_checkup(funds_extra, expanded=True)" in src


class TestTrafficLightDedup:
    def test_traffic_light_dedups_by_code(self):
        src = _src(_MACRO)
        # 去重區塊存在於持倉紅綠燈之前
        i_dedup = src.find("_seen_tl")
        i_light = src.find("🚦 持倉紅綠燈")
        assert i_dedup != -1, "持倉紅綠燈缺少去重邏輯（_seen_tl）"
        assert i_dedup < i_light, "去重應在渲染持倉紅綠燈之前"
