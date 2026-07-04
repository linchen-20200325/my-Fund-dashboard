"""v19.190 guard — 組合健檢 / 總經 三個 UI bug fix。

user 截圖回報（2026-06-27）：
A. 「多基金績效比較」圖表 + 比較表全顯示 0.00%。根因：v19.148 把欄位改名為
   「X% (全期自算)」，但此圖表/比較表仍讀舊鍵「年化…% 🧮」→ .get() 全 None → 0。
B. 「逐檔財務健診（4 大功能）」上移後預設收合在 expander 內，user 以為「沒有」。
   render_fund_checkup 加 expanded 參數，組合健檢傳 True 直接展開。
C. 總經 tab「持倉紅綠燈」同一檔列出 2-3 次（portfolio_funds 重複載入累積）→ 依 code 去重。
"""
from __future__ import annotations

_GRP = "ui/tab_fund_grp_health.py"
# B1 v19.205 / P2-7:ui/helpers/fund_checkup.py 已搬 ui/helpers/fund/checkup.py
_CHK = "ui/helpers/fund/checkup.py"
# v19.262 P3-A6: 持倉紅綠燈隨拐點警報整 section 抽至 ui/tab1_macro_inflection.py
_MACRO = "ui/tab1_macro_inflection.py"


def _src(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


class TestPerfChartKeys:
    def test_chart_uses_adaptive_basis(self):
        # v19.304 fix（user 2026-07-04「多檔比較資料都是 0」）：圖表基準改自適應。
        # 舊版寫死讀「(年化)」→ 短歷史整排 None → float(None or 0) 全 0 空圖。
        # 新版走 _pick_comparison_basis(ok_rows)：全檔皆年化 → 年化;任一短歷史 → 全期實際。
        src = _src(_GRP)
        assert "_pick_comparison_basis(ok_rows)" in src, "圖表應改走自適應基準 helper"
        # f-string 組鍵，兩套欄名都可能被讀到
        assert 'f"配息率% ({_basis})"' in src
        assert 'f"含息% ({_basis})"' in src
        assert 'f"淨值% ({_basis})"' in src

    def test_old_renamed_keys_gone(self):
        """v19.148 改名前的舊鍵不得殘留（否則又會讀到 None → 0）。"""
        src = _src(_GRP)
        assert "年化配息率% 🧮" not in src
        assert "含息年化% 🧮" not in src
        assert "年化淨值% 🧮" not in src

    def test_process_one_fund_emits_both_bases(self):
        """確認 row dict 同時有「(年化)」+「(全期實際)」兩套鍵（v19.180 拆欄 + v19.304 需 fallback）。"""
        src = _src(_GRP)
        assert '"配息率% (年化)": s[' in src
        assert '"含息% (年化)": s[' in src
        assert '"淨值% (年化)": s[' in src
        assert '"配息率% (全期實際)": s[' in src
        assert '"含息% (全期實際)": s[' in src
        assert '"淨值% (全期實際)": s[' in src


class TestComparisonBasisPicker:
    """v19.304 純函式回歸網 — _pick_comparison_basis 基準決策。"""

    def test_all_annual_present_picks_annual(self):
        from ui.tab_fund_grp_health import _pick_comparison_basis
        rows = [
            {"配息率% (年化)": 9.09, "含息% (年化)": 10.8, "淨值% (年化)": 1.7},
            {"配息率% (年化)": 11.0, "含息% (年化)": 12.6, "淨值% (年化)": 1.6},
        ]
        assert _pick_comparison_basis(rows) == "年化"

    def test_any_short_history_falls_back_to_quanqi(self):
        """任一檔年化為 None（持有 < 0.5 年）→ 全圖退全期實際，避免全 0 空圖。"""
        from ui.tab_fund_grp_health import _pick_comparison_basis
        rows = [
            {"配息率% (年化)": 9.09, "含息% (年化)": 10.8, "淨值% (年化)": 1.7,
             "配息率% (全期實際)": 4.62, "含息% (全期實際)": 6.3, "淨值% (全期實際)": 1.7},
            # 短歷史檔:年化三軸皆 None,只有全期實際有值(截圖 TLZF9/JFZN3/ACTI71 情境)
            {"配息率% (年化)": None, "含息% (年化)": None, "淨值% (年化)": None,
             "配息率% (全期實際)": 5.53, "含息% (全期實際)": 7.2, "淨值% (全期實際)": 1.64},
        ]
        assert _pick_comparison_basis(rows) == "全期實際"

    def test_partial_none_in_single_row_falls_back(self):
        """單檔只有部分年化欄 None 也算不完整 → 退全期實際（基準統一）。"""
        from ui.tab_fund_grp_health import _pick_comparison_basis
        rows = [
            {"配息率% (年化)": 9.09, "含息% (年化)": None, "淨值% (年化)": 1.7},
        ]
        assert _pick_comparison_basis(rows) == "全期實際"


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
        # 去重區塊存在於持倉紅綠燈渲染之前
        # v19.262 P3-A6: docstring 也含「🚦 持倉紅綠燈」,改抓真渲染呼叫定位
        i_dedup = src.find("_seen_tl")
        i_light = src.find('st.markdown("#### 🚦 持倉紅綠燈")')
        assert i_dedup != -1, "持倉紅綠燈缺少去重邏輯（_seen_tl）"
        assert i_light != -1, "找不到持倉紅綠燈渲染呼叫"
        assert i_dedup < i_light, "去重應在渲染持倉紅綠燈之前"
