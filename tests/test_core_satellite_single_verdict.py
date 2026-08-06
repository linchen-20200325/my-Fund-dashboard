# -*- coding: utf-8 -*-
"""核心 / 衛星：全站一把尺 + 同一頁只有一個行動建議（2026-08-06 稽核 🔴 必修 3/5/6）。

本檔補的是 `tests/test_portfolio_allocation.py` 缺的那一半 —— 那 16 條全是純函式
測試，把 `ui/tab3_portfolio.py` 任何一個呼叫端換回舊的 inline 邏輯，16 條**全綠**，
而「4 處收斂到 1 處」正是 `ui/helpers/portfolio/allocation.py` 存在的唯一理由。
判準走 `PROCESS.md §4`：拿掉呼叫端那一行，測試必須紅。

三組守衛
========
1. **接線**（必修 6）：`ui/tab3_portfolio.py` 的四個消費點（保單分組 / ① KPI 卡 /
   Hero 卡 / 基金卡角色標）+ AI 快照，全部走 allocation SSOT；目標值不得寫死。
2. **MK 戰情室**（必修 6 附帶）：`tag_mk_class` 原本只讀 `is_core`、無視
   `policy_tier` —— Sheet 標 `core` 的基金在保單卡片顯示「🛡️核心」，在檔數 KPI
   與 MK 戰情室卻算成衛星。
3. **兩把尺**（必修 3）：Tab3 同一次捲動內有兩個口徑不同的核心%，下方那個原本還
   給方向相反的行動建議。現在下方降為唯讀對照 + 明講差異。

修正前紅的類型都標在各條 docstring；`ImportError 紅` 一律另外註明，因為那只證明
「函式存在」，不證明「有人呼叫它」。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
_TAB3 = ROOT / "ui" / "tab3_portfolio.py"
_GRP = ROOT / "ui" / "tab_fund_grp_health.py"
_ALLOC_MODULE = "ui.helpers.portfolio.allocation"


@pytest.fixture(scope="module")
def tab3_tree() -> ast.AST:
    return ast.parse(_TAB3.read_text(encoding="utf-8"), filename=str(_TAB3))


@pytest.fixture(scope="module")
def grp_tree() -> ast.AST:
    return ast.parse(_GRP.read_text(encoding="utf-8"), filename=str(_GRP))


# ══════════════════════════════════════════════════════════════
# AST 小工具（一律 AST：註解與說明文案不得影響判定）
# ══════════════════════════════════════════════════════════════
def _aliases_of(tree: ast.AST, original: str, module: str = _ALLOC_MODULE) -> set[str]:
    """`from <module> import <original> as <alias>` → {alias}（未改名則為原名）。"""
    out: set[str] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == module:
            for a in n.names:
                if a.name == original:
                    out.add(a.asname or a.name)
    return out


def _calls_named(tree: ast.AST, names: set[str]) -> list[ast.Call]:
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id in names]


def _calls_to_ssot(tree: ast.AST, original: str) -> list[ast.Call]:
    return _calls_named(tree, _aliases_of(tree, original))


def _kwarg(call: ast.Call, key: str):
    for kw in call.keywords:
        if kw.arg == key:
            return kw.value
    return None


def _func_def(tree: ast.AST, name: str) -> ast.FunctionDef:
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == name:
            return n
    raise AssertionError(f"找不到函式 {name}")


# ══════════════════════════════════════════════════════════════
# 1. Tab3 四個消費點的接線（必修 6）
# ══════════════════════════════════════════════════════════════
# 稽核點名的四個位置：保單分組 enriched(`is_core`)、① KPI 卡、Hero 卡 + 甜甜圈、
# 基金卡角色標；另有 AI 快照也吃同一套。每個都是「換回 inline 就少一次呼叫」，
# 所以用**下限計數**釘住：拿掉任一呼叫端 → 計數下降 → 本條紅。
_MIN_SUMMARIZE_CALLS = 4      # 保單分組 / ① KPI / Hero / AI 快照
_MIN_TARGET_CALLS = 4         # 同上，目標值一律走同一支
_MIN_RESOLVE_FLAG_CALLS = 3   # 保單分組 enriched / 基金卡角色標 / AI 快照


def test_summarize_core_satellite_is_the_only_amount_math(tab3_tree) -> None:
    """**修正前綠（回歸鎖 → 但對「改回 inline」是行為衝突紅）**。

    把任一處換回自己 sum 金額、自己算百分比，本條立刻紅。
    """
    _calls = _calls_to_ssot(tab3_tree, "summarize_core_satellite")
    assert len(_calls) >= _MIN_SUMMARIZE_CALLS, (
        f"Tab3 只剩 {len(_calls)} 處走金額加權 SSOT（應 ≥ {_MIN_SUMMARIZE_CALLS}）"
        " —— 有人把某一區換回 inline 計算了，同一頁又會出現兩個核心%。")


def test_every_summary_call_gets_a_non_literal_target(tab3_tree) -> None:
    """目標值一律 `get_core_target_pct`，不得在呼叫點寫死數字（§3.3）。

    **修正前綠（回歸鎖）**：寫死 `target_pct=75` / `80` 會讓 slider 調了沒反應，
    而畫面照樣印「目標核心 75%」—— 說謊型缺陷，lint 完全抓不到。
    """
    offenders = []
    for _c in _calls_to_ssot(tab3_tree, "summarize_core_satellite"):
        _t = _kwarg(_c, "target_pct")
        if _t is None:
            continue   # 不做偏差判定的用法是允許的（見 allocation.py docstring）
        if isinstance(_t, ast.Constant):
            offenders.append(_c.lineno)
    assert not offenders, (
        f"行 {offenders}：`target_pct` 傳了常數字面值，目標值與 ⚙️ 組合設定脫鉤。")


def test_core_target_always_from_ssot_helper(tab3_tree) -> None:
    _calls = _calls_to_ssot(tab3_tree, "get_core_target_pct")
    assert len(_calls) >= _MIN_TARGET_CALLS, (
        f"只剩 {len(_calls)} 處走 `get_core_target_pct`（應 ≥ {_MIN_TARGET_CALLS}）")


def test_core_flag_always_from_ssot_helper(tab3_tree) -> None:
    """級別判定（policy_tier → is_core）不得在 Tab3 各處各寫一份。"""
    _calls = _calls_to_ssot(tab3_tree, "resolve_core_flag")
    assert len(_calls) >= _MIN_RESOLVE_FLAG_CALLS, (
        f"只剩 {len(_calls)} 處走 `resolve_core_flag`（應 ≥ {_MIN_RESOLVE_FLAG_CALLS}）"
        " —— 少一處就會出現「卡片寫核心、KPI 算衛星」。")


# ══════════════════════════════════════════════════════════════
# 2. 說明 caption 只印一次（必修 5）
# ══════════════════════════════════════════════════════════════
def test_core_satellite_caption_printed_exactly_once(tab3_tree) -> None:
    """**修正前必紅（行為衝突）** —— 上一輪新製造的重複。

    `:1679`（💡 這四格的基數）與 `:1894`（Hero 甜甜圈下）輸入等價（同一個
    `_pf_loaded`）→ 輸出 byte-identical，同一頁把同一句話貼兩遍。
    """
    _calls = _calls_to_ssot(tab3_tree, "format_core_satellite_caption")
    assert len(_calls) == 1, (
        f"`format_core_satellite_caption` 被呼叫 {len(_calls)} 次（應為 1 次）"
        " —— 輸入相同時輸出逐字相同，多印一次只是把同一句話貼兩遍。")


# ══════════════════════════════════════════════════════════════
# 3. MK 戰情室分類走同一把尺（必修 6 附帶）
# ══════════════════════════════════════════════════════════════
class TestMkClassUsesTheSameRuler:
    def test_policy_tier_beats_is_core(self):
        """**修正前必紅（行為衝突）** —— 舊碼只讀 `is_core`，`policy_tier` 完全無效。

        使用者在 Google Sheet 標 `core` 的基金，保單卡片顯示「🛡️核心」
        （那裡走 `resolve_core_flag`），MK 戰情室與檔數 KPI 卻算成衛星。
        """
        from ui.components.mk_dashboard import tag_mk_class
        assert tag_mk_class({"policy_tier": "core", "is_core": False}) == "Core"
        assert tag_mk_class({"policy_tier": "satellite", "is_core": True}) == "Satellite"

    def test_falls_back_to_is_core_when_tier_absent(self):
        from ui.components.mk_dashboard import tag_mk_class
        assert tag_mk_class({"is_core": True}) == "Core"
        assert tag_mk_class({"is_core": False}) == "Satellite"

    def test_no_third_state_that_vanishes_from_both_tables(self):
        """**修正前必紅（行為衝突）** —— 舊碼 `is_core` 缺值回 "Unknown"。

        下游三處（`ui/helpers/portfolio/health.py` 檔數 KPI、核心戰情室、
        波段觀測站）都用 `== "Core"` / `== "Satellite"` 過濾，"Unknown" 的基金
        會**同時從兩張表消失**，使用者看不到它去哪了。
        """
        from ui.components.mk_dashboard import tag_mk_class
        for _f in ({}, {"is_core": None}, {"policy_tier": "中性"}):
            assert tag_mk_class(_f) in ("Core", "Satellite"), (
                f"{_f} 產生了第三態，該檔會在核心 / 衛星兩張表都不見")

    def test_matches_the_amount_weighted_classifier_exactly(self):
        """漂移鎖：檔數版與金額版必須同一套規則，否則同頁兩個核心%又會打架。"""
        from ui.components.mk_dashboard import tag_mk_class
        from ui.helpers.portfolio.allocation import resolve_core_flag
        _cases = [
            {"policy_tier": "core", "is_core": False},
            {"policy_tier": "SATELLITE", "is_core": True},
            {"policy_tier": "  Core "},
            {"is_core": True},
            {"is_core": False},
            {},
        ]
        for _f in _cases:
            _expect = "Core" if resolve_core_flag(_f) else "Satellite"
            assert tag_mk_class(_f) == _expect, f"{_f} 兩把尺結論不一致"


# ══════════════════════════════════════════════════════════════
# 4. 兩把尺：同一頁只留一個行動建議（必修 3）
# ══════════════════════════════════════════════════════════════
_CSA_RED = {
    "core_pct": 40.0, "satellite_pct": 35.0, "undetermined_pct": 25.0,
    "n_core": 2, "n_satellite": 2, "n_undetermined": 1,
    "total_weight": 5_000_000.0, "weight_mode": "equal",
    "status": "🔴",
    "message": "核心僅 40% < 目標 50%,衛星過重(35%)— 追超額報酬但波動 / 風險偏高",
}


class TestDualRulerCaption:
    def test_health_tab_keeps_the_actionable_message(self):
        """💊 健診 Tab 全頁只有這一個核心% → 照常給行動建議（行為不變）。"""
        from ui.tab_fund_grp_health import _core_satellite_verdict_caption
        _cap = _core_satellite_verdict_caption(_CSA_RED, "health")
        assert _CSA_RED["message"] in _cap
        assert _CSA_RED["status"] in _cap

    @pytest.mark.parametrize("source_tab", [None, "portfolio"])
    def test_embedded_verdict_is_read_only(self, source_tab):
        """**修正前必紅（行為衝突）** —— Tab3 embed 時不得再輸出行動建議。

        上方 Hero 卡剛說「核心過重，可贖回轉衛星」，下方這一區說「衛星過重」，
        同一次捲動內兩個方向相反的建議，使用者只能二選一，而那正是他無從判斷的。

        `source_tab=None`（未宣告身分）也走唯讀側：fail-safe，新 caller 忘了宣告時
        寧可少給一個建議，也不要又製造一對互相打臉的結論。
        """
        from ui.tab_fund_grp_health import _core_satellite_verdict_caption
        _cap = _core_satellite_verdict_caption(_CSA_RED, source_tab)
        assert _CSA_RED["message"] not in _cap, "行動建議仍被印出來"
        for _banned in ("衛星過重", "偏保守"):
            assert _banned not in _cap, f"仍留行動語氣「{_banned}」"
        assert "唯讀" in _cap, "沒告訴使用者這一區是唯讀對照"
        assert "上方" in _cap, "沒指出行動建議在哪一處"
        # 數字本身仍要在（降級的是建議，不是揭露）
        assert "40" in _cap and "35" in _cap and "25" in _cap

    def test_ruler_note_states_which_ruler_and_uses_ssot_numbers(self):
        """表上方必須先講「這是哪一把尺」，門檻值從 L2 常數取，不在 UI 寫死。"""
        from services.health.asset_class import (
            CORE_TARGET_MAX_PCT, CORE_TARGET_MIN_PCT,
        )
        from ui.tab_fund_grp_health import _core_satellite_ruler_note
        _note = _core_satellite_ruler_note()
        assert "3-3-3" in _note and "類別" in _note, "沒講分類依據"
        assert "policy_tier" in _note, "沒講它**不是**使用者標的那一把尺"
        assert f"{CORE_TARGET_MIN_PCT:.0f}~{CORE_TARGET_MAX_PCT:.0f}%" in _note, (
            "參考區間應由 `services/health/asset_class` 常數帶出（§3.3 不寫死）")

    def test_contrast_note_covers_all_three_differences(self):
        """三項差異（分母 / 分類 / 目標）都要講 —— 少講一項，數字差就變成「誰算錯」。"""
        from ui.tab_fund_grp_health import _CS_PORTFOLIO_CONTRAST_NOTE as _n
        assert "分母" in _n and "分類依據" in _n and "目標值" in _n
        assert "policy_tier" in _n
        assert "0 計" in _n and "100 萬" in _n, (
            "分母差異是致命的那一項：一邊未填算 0、一邊補 100 萬 → "
            "只要有一檔沒填，兩個百分比數學上不可能相等")


class TestDualRulerWiring:
    """接線（`PROCESS.md §4`）：helper 寫得再好，render 沒呼叫就等於不存在。"""

    def test_render_uses_the_verdict_helper_not_the_raw_message(self, grp_tree) -> None:
        """**修正前必紅（AST 找不到 `_core_satellite_verdict_caption`）**。

        同時反向擋住「helper 加了但 render 仍直接印 `_csa['message']`」。
        """
        _fn = _func_def(grp_tree, "_render_health_3tables")
        _names = {n.func.id for n in ast.walk(_fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "_core_satellite_verdict_caption" in _names, "結論句沒走 helper"
        assert "_core_satellite_ruler_note" in _names, "沒印「這是哪一把尺」"

        offenders = []
        for n in ast.walk(_fn):
            # `_csa["message"]`
            if (isinstance(n, ast.Subscript)
                    and isinstance(n.value, ast.Name) and n.value.id == "_csa"
                    and isinstance(n.slice, ast.Constant)
                    and n.slice.value == "message"):
                offenders.append(n.lineno)
            # `_csa.get("message")`
            if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                    and n.func.attr == "get"
                    and isinstance(n.func.value, ast.Name)
                    and n.func.value.id == "_csa"
                    and n.args and isinstance(n.args[0], ast.Constant)
                    and n.args[0].value == "message"):
                offenders.append(n.lineno)
        assert not offenders, (
            f"行 {offenders}：render 又直接印 L2 的行動建議，繞過唯讀分支。")

    def test_render_prints_the_contrast_note(self, grp_tree) -> None:
        """**修正前必紅（AST 找不到 `_CS_PORTFOLIO_CONTRAST_NOTE`）**。"""
        _fn = _func_def(grp_tree, "_render_health_3tables")
        assert any(isinstance(n, ast.Name)
                   and n.id == "_CS_PORTFOLIO_CONTRAST_NOTE"
                   for n in ast.walk(_fn)), (
            "兩把尺的差異說明沒被 render 讀出來（產生端對了、沒接出去）")

    def test_tab3_declares_itself_as_the_embedding_page(self, tab3_tree) -> None:
        """**修正前必紅（AST：呼叫沒有 source_tab 關鍵字）**。

        Tab3 embed 必須自報身分。⚠️ 這是「講清楚」而非「開關」——
        render 的預設分支本來就是唯讀（見 `_core_satellite_verdict_caption`
        docstring），所以拿掉這一行不會讓畫面回到打臉狀態，但會讓下一個人
        以為 Tab3 沒有特殊處置。
        """
        _calls = [n for n in ast.walk(tab3_tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id == "_render_health_tbl"]
        assert _calls, "Tab3 應仍 embed 健診 3 表"
        for _c in _calls:
            _st = _kwarg(_c, "source_tab")
            assert isinstance(_st, ast.Constant) and _st.value == "portfolio", (
                f"行 {_c.lineno}：Tab3 embed 未宣告 source_tab=\"portfolio\"")
