"""tests/test_flow_layer1.py — 四層流程改造 Layer 1（市場與全球總經層）回歸鎖。

對應 2026-08-14 user 提供的系統流程圖第 ① 層：
    全球總經 & 股債風向 → 美債殖利率 & 匯率走勢(USD/TWD) → 影響全系統風控係數

本批交付三件事，每件都要能在 revert 時變紅：
1. **四層流程導覽**（`story_nav` 升級）+ 7 個分頁名全部收進 SSOT
2. **E11 雷達門檻漂移**：UI 手抄的 5 組門檻改 import service SSOT
   （實測 3 組已漂移：VIX 黃 25 vs 22、PCR 紅 1.5 vs 1.2、
     sector_rotation 連量綱都錯 —— 比值 vs 百分點）
3. **USD/TWD 與台股外資解耦**：原本 FinMind 外資一掛，Yahoo 明明抓得到的
   匯率也一起凍住（實機看到 140 天前），而匯率是流程圖第 ① 層的一級訊號
4. **A10 清快取假成功**：失敗被 `pass` 吞掉，卻仍宣告「已重新載入最新」
"""
from __future__ import annotations

import inspect
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _code_lines(src: str, needle: str) -> list[str]:
    """含 needle 的**程式碼**行（排除純註解行）。說明註解會引用舊寫法。"""
    return [ln for ln in src.splitlines()
            if needle in ln and not ln.strip().startswith("#")]


def _read(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text(encoding="utf-8")


# ══════════════════════════════════════════════════════════════════════════
# 1) 分頁名 SSOT — 7 個分頁全收
# ══════════════════════════════════════════════════════════════════════════
class TestTabLabelCoversAllTabs:
    def test_all_seven_tabs_have_labels(self):
        from ui.helpers.story_nav import _TAB_LABELS
        assert set(_TAB_LABELS) == {
            "macro", "health", "batch", "fund", "portfolio", "manage", "ref",
        }, "分頁名 SSOT 沒有涵蓋全部 7 個頂層分頁"

    def test_app_no_longer_hardcodes_tab_names(self):
        """`app.py` 的 st.tabs 不得再出現寫死的分頁名字面值。

        原本「📦 批次分析 / 📋 我的管理室 / 📖 參考 / 診斷」三個是字面值 ——
        那就是第二份標籤，而 sidebar 的三處死指路正是同一種病的第二次發作。
        """
        _src = _read("app.py")
        for _dead in ('"📦 批次分析"', '"📋 我的管理室"', '"📖 參考 / 診斷"'):
            _hits = _code_lines(_src, _dead)
            assert not _hits, f"app.py 仍寫死分頁名 {_dead}：{_hits}"

    def test_unknown_key_still_fails_loud(self):
        from ui.helpers.story_nav import tab_label
        with pytest.raises(KeyError):
            tab_label("nope")


# ══════════════════════════════════════════════════════════════════════════
# 2) 四層流程導覽
# ══════════════════════════════════════════════════════════════════════════
class TestFlowNav:
    def test_layer_mapping(self):
        from ui.helpers.story_nav import layer_of
        assert layer_of("macro") == "L1"
        assert layer_of("fund") == "L2"
        assert layer_of("batch") == "L2"
        assert layer_of("health") == "L3"
        assert layer_of("portfolio") == "L3"
        assert layer_of("manage") == "L3"
        assert layer_of("ref") == "", "支援型分頁不該被歸進流程任何一層"

    def test_current_layer_highlighted(self):
        from ui.helpers.story_nav import flow_nav_markdown
        md = flow_nav_markdown("macro")
        assert "**:blue[① 市場與全球總經]**" in md
        assert ":gray[② 基金核心分析]" in md

    def test_shows_sibling_tabs_and_next_layer(self):
        from ui.helpers.story_nav import flow_nav_markdown
        md = flow_nav_markdown("fund")
        assert "📦 批次分析" in md, "同層的其他分頁沒列出來"
        assert "🔍 個基深掘" not in md.split("\n\n")[-1], (
            "『本層另有』不該把你正在看的這頁也列進去"
        )
        assert "下一層" in md

    def test_support_tab_says_it_is_outside_the_flow(self):
        from ui.helpers.story_nav import flow_nav_markdown
        md = flow_nav_markdown("ref")
        assert ":blue[" not in md, "不在流程內的分頁不該 highlight 任何一層"
        assert "支援" in md

    def test_accepts_layer_id_directly(self):
        from ui.helpers.story_nav import flow_nav_markdown
        assert "**:blue[④ 行動閉環]**" in flow_nav_markdown("L4")

    # v19.476（user「說明欄位太多太複雜,請簡化」）:市場定調(macro)上方 meta 精簡,
    # 刻意移除 render_flow_nav("macro"),只留單行決策動線 render_story_nav。故 macro 不在
    # 本 flow_nav 接線清單;其餘 5 頁仍須接線(render_flow_nav 非死碼)。macro 的 story_nav
    # 接線由 test_tab_is_wired_to_story_nav 另守(見下)。
    @pytest.mark.parametrize("relpath,key", [
        ("ui/tab2_single_fund.py", "fund"),
        ("ui/tab3_portfolio.py", "portfolio"),
        ("ui/tab_fund_grp_health.py", "health"),
        ("ui/tab_batch_analysis.py", "batch"),
        ("ui/tab_manage.py", "manage"),
    ])
    def test_tab_is_wired_to_flow_nav(self, relpath, key):
        """接線驗證：`render_flow_nav` 寫好但沒被 caller 接出去 = 沒交付。"""
        _src = _read(relpath)
        assert _code_lines(_src, f'render_flow_nav("{key}")'), (
            f"{relpath} 沒有呼叫 render_flow_nav(\"{key}\")"
        )

    def test_macro_kept_story_nav_after_flow_nav_removed(self):
        """v19.476:macro 移除 flow_nav 後,仍須保留單行決策動線 story_nav(否則等於全砍)。"""
        _src = _read("ui/tab1_macro.py")
        assert _code_lines(_src, 'render_story_nav("macro")'), (
            "ui/tab1_macro.py 應保留 render_story_nav(\"macro\")"
        )
        assert not _code_lines(_src, 'render_flow_nav("macro")'), (
            "v19.476 已移除 macro 的 render_flow_nav"
        )


# ══════════════════════════════════════════════════════════════════════════
# 3) E11 — 雷達門檻 SSOT
# ══════════════════════════════════════════════════════════════════════════
class TestRadarThresholdSSOT:
    def test_service_exports_thresholds(self):
        import services.risk_radar as _rr
        for _n in ("RADAR_VIX_YELLOW", "RADAR_VIX_RED",
                   "RADAR_PCR_YELLOW", "RADAR_PCR_RED",
                   "RADAR_SECTOR_GAP_YELLOW_PP", "RADAR_SECTOR_GAP_RED_PP",
                   "RADAR_MOVE_YELLOW", "RADAR_MOVE_RED",
                   "RADAR_VIX_TS_YELLOW", "RADAR_VIX_TS_RED"):
            assert hasattr(_rr, _n), f"services.risk_radar 沒有 export {_n}"

    def test_vix_yellow_is_the_global_ssot_22_not_25(self):
        """v19.157 已把全站 VIX 黃燈統一為 22，UI 卻還畫 25。"""
        from services.risk_radar import RADAR_VIX_YELLOW
        from shared.macro_buckets import _VIX_YELLOW
        assert RADAR_VIX_YELLOW == float(_VIX_YELLOW)
        assert RADAR_VIX_YELLOW != 25.0, "VIX 黃燈又漂回 25（與全站 SSOT 脫鉤）"

    def test_pcr_red_matches_service_judgement(self):
        """PCR 紅燈 SSOT 是 1.20，UI 原本畫 1.50 → 燈亮了線還沒到。"""
        from services.risk_radar import RADAR_PCR_RED
        assert RADAR_PCR_RED == 1.20

    def test_sector_rotation_is_percentage_points_not_ratio(self):
        """量綱鎖：sector_rotation 是**百分點差**，不是 XLP/XLY 比值。

        原本 UI 畫在 1.00 / 1.20（比值刻度），而 service 判燈用 2 / 4 pp。
        實機觀測值 −0.84（負數）本身就證明它不可能是比值。
        """
        from services.risk_radar import (
            RADAR_SECTOR_GAP_RED_PP, RADAR_SECTOR_GAP_YELLOW_PP,
        )
        assert RADAR_SECTOR_GAP_YELLOW_PP == 2.0
        assert RADAR_SECTOR_GAP_RED_PP == 4.0
        assert RADAR_SECTOR_GAP_RED_PP > 1.5, (
            "sector_rotation 門檻掉回比值刻度（1.x）—— 量綱又錯了"
        )

    def test_ui_imports_thresholds_instead_of_hardcoding(self):
        import ui.tab1_macro as _t1
        _src = inspect.getsource(_t1._radar_threshold_lines)
        assert "from services.risk_radar import" in _src, (
            "UI 又自己手抄一份雷達門檻（§3.3 第二份真相）"
        )
        for _bad in ("25.0,", "1.50,", "(1.20,"):
            assert _bad not in _src, f"UI 仍有寫死的門檻字面值 {_bad}"

    def test_service_uses_its_own_constants(self):
        """service 端自己也要吃常數，否則常數與判燈邏輯還是兩份。"""
        import services.risk_radar as _rr
        _src = inspect.getsource(_rr)
        for _n in ("RADAR_VIX_RED", "RADAR_PCR_RED", "RADAR_SECTOR_GAP_RED_PP",
                   "RADAR_MOVE_RED", "RADAR_VIX_TS_RED"):
            # 定義 1 次 + 至少被判燈邏輯用 1 次
            assert len(_code_lines(_src, _n)) >= 2, (
                f"{_n} 只有定義沒有被使用 —— 判燈邏輯仍是 inline 字面值"
            )


# ══════════════════════════════════════════════════════════════════════════
# 4) USD/TWD 與台股外資解耦
# ══════════════════════════════════════════════════════════════════════════
class TestUsdTwdDecoupled:
    def test_fx_stashed_independently_of_foreign_flow(self):
        """外資掛掉時，匯率仍要能獨立落地。

        原碼 `if flow_df.empty or fx_df.empty: return False` 在外資失敗時直接
        整包放棄 → Yahoo 明明抓得到的匯率被一起凍住（實機 140 天前）。
        """
        import ui.hot_money as _hm
        _src = inspect.getsource(_hm.refresh_hot_money_data)
        assert _code_lines(_src, "_macro_usdtwd"), (
            "匯率沒有獨立 stash —— 又會被 FinMind 外資綁架"
        )
        # 獨立落地必須發生在「兩者皆需」的早退之前
        _lines = _src.splitlines()
        _i_stash = next(i for i, ln in enumerate(_lines)
                        if "_macro_usdtwd" in ln and not ln.strip().startswith("#"))
        _i_bail = next(i for i, ln in enumerate(_lines)
                       if "flow_df.empty or fx_df.empty" in ln
                       and not ln.strip().startswith("#"))
        assert _i_stash < _i_bail, (
            "匯率落地寫在早退之後 —— 外資一掛就永遠執行不到"
        )

    def test_failure_message_says_which_source_died(self):
        import ui.hot_money as _hm
        _src = inspect.getsource(_hm.refresh_hot_money_data)
        assert "FinMind" in _src and "Yahoo" in _src, (
            "失敗訊息沒有區分是外資還是匯率掛掉 —— 使用者不知道該修哪一邊"
        )

    def test_registry_has_a_consumer_for_the_new_stash(self):
        """PROCESS.md §4 0-consumer 條款：產生端與消費端必須同批交付。"""
        import ui.helpers.io.data_registry as _dr
        _src = inspect.getsource(_dr._update_data_registry)
        assert _code_lines(_src, "_macro_usdtwd"), (
            "`_macro_usdtwd` 有產生端卻沒有任何讀取方（算對了沒接出去）"
        )
        assert "總經_USDTWD_TREND" in _src


# ══════════════════════════════════════════════════════════════════════════
# 5) A10 — 清快取失敗不得偽裝成成功
# ══════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("relpath,tag", [
    ("ui/tab1_macro.py", "[tab1_macro/clear_cache]"),
    ("ui/tab1_macro_longterm.py", "[tab1_longterm/clear_cache]"),
])
def test_clear_cache_failure_leaves_a_trace(relpath, tag):
    """清快取失敗原本被 `pass` 吞掉，卻仍往下跑「已載入最新」的流程。

    使用者按了「強制重抓最新（清快取）」，拿到的其實是舊快取。

    ⚠️ **2026-08-28 顏色批次二之一改寫，兩邊理由並陳（不是放寬）**：
    - 舊寫法：`assert _code_lines(_src, "st.warning")` —— 全檔只要**任何地方**有一行
      `st.warning` 就算過。它的理由今天仍然成立（那時 `st.warning` 是唯一的告知方式，
      而且它擋住了「改回 `pass` 靜默吞掉」這個原病）。
    - 被權衡掉的原因有兩個，而且第二個更重要：
      (a) 客戶 2026-08-28 Q2 把「清快取失敗」這種**數字可能是錯的**失敗改走
          `render_state.system_error()`（🔴），逐字釘住 `st.warning` 會把**正確的修法**
          判成違規；
      (b) 舊寫法**根本沒有檢查到正確的位置** —— `ui/tab1_macro.py` 之所以通過，是因為
          該檔別處另有 `st.warning`（「市場相位資料缺失」等），與清快取這個 handler 無關。
          **實測（不是推論）**：在 `origin/main`（461f811）上把清快取那段 `st.warning`
          整段換成 `pass`，本測試 **2 passed** —— 原病完整復發而測試全綠。
          （複現：`git worktree add <tmp> origin/main`，改該段為 `pass`，
            跑 `pytest tests/test_flow_layer1.py::test_clear_cache_failure_leaves_a_trace`。）
    - 新寫法改用 AST：找到**含這個 stderr tag 的那個 except handler**，要求它裡面有一個
      對使用者可見的告知呼叫。**範圍變窄、強度變強**，不是放寬。
    """
    import ast as _ast

    _src = _read(relpath)
    assert tag in _src, f"{relpath} 清快取失敗沒有 stderr 留痕"

    # 對使用者可見的「這次不是最新」告知：舊寫法（st.warning / st.error）與
    # 現行寫法（render_state.system_error / friendly_error）都算數。
    _REPORTERS = {"st.warning", "st.error", "system_error", "friendly_error"}

    def _name(call: _ast.Call) -> str:
        if isinstance(call.func, _ast.Attribute):
            _v = call.func.value
            while isinstance(_v, (_ast.Attribute, _ast.Subscript)):
                _v = _v.value
            _root = _v.id if isinstance(_v, _ast.Name) else None
            return f"st.{call.func.attr}" if _root == "st" else call.func.attr
        return call.func.id if isinstance(call.func, _ast.Name) else ""

    _handlers = [h for h in _ast.walk(_ast.parse(_src))
                 if isinstance(h, _ast.ExceptHandler)
                 and tag in _ast.unparse(h)]
    assert _handlers, (
        f"{relpath} 找不到帶 {tag} 的 except handler —— stderr 留痕搬走了？"
    )
    for _h in _handlers:
        _reported = [_name(c) for c in _ast.walk(_h)
                     if isinstance(c, _ast.Call) and _name(c) in _REPORTERS]
        assert _reported, (
            f"{relpath} 帶 {tag} 的 handler 裡沒有任何對使用者可見的告知 —— "
            f"清快取失敗會靜默,使用者拿到舊快取卻以為是最新。"
            f"可用的告知入口：{sorted(_REPORTERS)}"
        )
