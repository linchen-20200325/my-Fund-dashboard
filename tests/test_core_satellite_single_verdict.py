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
2. **戰情室**（必修 6 附帶）：`tag_mk_class` 原本只讀 `is_core`、無視
   `policy_tier` —— Sheet 標 `core` 的基金在保單卡片顯示「🛡️核心」，在檔數 KPI
   與 戰情室卻算成衛星。
3. **兩把尺**（必修 3 → 2026-08-07 user 裁決收尾）：Tab3 同一次捲動內有兩個口徑
   不同的核心%，下方那個原本還給方向相反的行動建議。上一輪只降級了 Tab3 embed；
   本輪 user 拍板「Sheet `policy_tier` 是唯一真相，健診那份降為純資訊」——
   **兩個 Tab 都唯讀**、L2 的建議核心區間常數整組移除、模擬本金不進比例分母。

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
# 3. 戰情室分類走同一把尺（必修 6 附帶）
# ══════════════════════════════════════════════════════════════
class TestMkClassUsesTheSameRuler:
    def test_policy_tier_beats_is_core(self):
        """**修正前必紅（行為衝突）** —— 舊碼只讀 `is_core`，`policy_tier` 完全無效。

        使用者在 Google Sheet 標 `core` 的基金，保單卡片顯示「🛡️核心」
        （那裡走 `resolve_core_flag`），戰情室與檔數 KPI 卻算成衛星。
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
    def test_verdict_points_to_the_single_source_of_truth(self):
        """兩個 Tab 都要指路到「唯一有行動建議的那一格」，但指的地方不同。

        **修正前必紅（行為衝突）**：健診 Tab 舊版根本沒有指路句 —— 它自己就在
        給建議（`if source_tab == "health": return f"{status} {csa['message']}"`）。
        """
        from ui.tab_fund_grp_health import _core_satellite_verdict_caption
        _embed = _core_satellite_verdict_caption(_CSA_RED, "portfolio")
        _health = _core_satellite_verdict_caption(_CSA_RED, "health")
        assert "上方" in _embed, "Tab3 embed 沒指出行動建議在本頁上方"
        assert "上方" not in _health, (
            "健診 Tab 沒有「上方那一格」—— 指過去會讓使用者找一個不存在的東西")
        # ⚠️ 2026-08-31 WP-F 修正（**有意識的修改，不是漏改** · 決策者：AI 總管）：
        # 期望值 ~~寫死 `"組合配置"`~~ 改為 runtime 讀 `tab_label("portfolio")`。
        # **舊寫法的理由仍然成立**（要驗「有沒有指向 ④」，拿名字當指紋最直接）；
        # **被權衡掉的原因**：那個指紋是**假的** ——「組合配置」從來不是任何時期的
        # ④ 分頁名（七→五前是「📊 配置 & 帳本」、之後是「📊 我的配置」）。
        # 測試把錯名字釘住＝**保護那個 bug 不被修掉**：修 production 反而弄紅測試。
        from ui.helpers.story_nav import tab_label as _tl

        assert _tl("portfolio") in _health, (
            f"健診 Tab 應指向 ④「{_tl('portfolio')}」，實際：{_health}")
        for _cap in (_embed, _health):
            assert "policy_tier" in _cap, "沒講唯一真相是 Sheet 標的級別"

    def test_verdict_surfaces_coverage_note_only_when_unreliable(self):
        """分類涵蓋不足時要把 L2 的資料品質說明接出來（§1 缺料揭露）。

        **修正前必紅（KeyError/行為紅）**：`coverage_note` 是本輪新增欄位，
        舊版沒有；若只產生不接出去，就是 `PROCESS.md §4` 點名的失效模式。
        """
        from services.health.asset_class import COVERAGE_OK, COVERAGE_UNRELIABLE
        from ui.tab_fund_grp_health import _core_satellite_verdict_caption
        _bad = {**_CSA_RED, "status": COVERAGE_UNRELIABLE,
                "coverage_note": "待定 45% 過多"}
        assert "待定 45% 過多" in _core_satellite_verdict_caption(_bad, "health")
        _ok = {**_CSA_RED, "status": COVERAGE_OK,
               "coverage_note": "待定 5%,屬性分類涵蓋足夠"}
        assert "待定 5%" not in _core_satellite_verdict_caption(_ok, "health")

    @pytest.mark.parametrize("source_tab", [None, "portfolio", "health"])
    def test_embedded_verdict_is_read_only(self, source_tab):
        """**修正前必紅（行為衝突）** —— `source_tab="health"` 那一組。

        上一輪只把 Tab3 embed 降為唯讀，健診 Tab 仍照印 L2 的行動建議；同一套
        屬性分類器在 A 頁是「建議」、在 B 頁是「參考」，換個 Tab 就換一套結論。
        2026-08-07 user 裁決：這一份**一律**降為純資訊。原本的情境仍成立 ——

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
        # 數字本身仍要在（降級的是建議，不是揭露）
        assert "40" in _cap and "35" in _cap and "25" in _cap

    def test_ruler_note_states_which_ruler_and_carries_no_target(self):
        """**修正前必紅（行為衝突）** —— 舊版在這句裡印「參考區間核心 50~80%」。

        把一個建議區間印在「核心 40%」旁邊，即使不寫「該調整」也已經是隱含評價；
        user 裁決本表不設目標，所以這句話裡不得再出現任何建議佔比。
        """
        from ui.tab_fund_grp_health import _core_satellite_ruler_note
        _note = _core_satellite_ruler_note()
        assert "3-3-3" in _note and "類別" in _note, "沒講分類依據"
        assert "policy_tier" in _note, "沒講它**不是**使用者標的那一把尺"
        assert "參考區間" not in _note, "本表已無目標值，不得再帶建議佔比區間"
        assert "不設" in _note, "應明講本表不設建議核心佔比"

    def test_contrast_note_covers_all_three_differences(self):
        """三項差異（分母 / 分類 / 目標）都要講 —— 少講一項，數字差就變成「誰算錯」。

        **修正前必紅（行為衝突）**：分母那一項本輪改了語意 —— 兩邊現在**同樣只計
        使用者實際填過的本金**，未填者的 100 萬模擬本金不進比例。舊文案（「本區把
        沒填的以 100 萬估算後計入」）現在是一句準確描述舊行為的假話。
        """
        from ui.tab_fund_grp_health import _CS_PORTFOLIO_CONTRAST_NOTE as _n
        assert "分母" in _n and "分類依據" in _n and "目標值" in _n
        assert "policy_tier" in _n
        assert "100 萬" in _n and "不進" in _n, (
            "必須講清楚 100 萬模擬本金不進配置比例")
        assert "估算後計入" not in _n, "舊分母描述殘留 = 對使用者說謊"


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

    def test_tab3_no_longer_embeds_the_health_tables(self, tab3_tree) -> None:
        """~~**修正前必紅（AST：呼叫沒有 source_tab 關鍵字）**。Tab3 embed 必須自報身分。
        ⚠️ 這是「講清楚」而非「開關」—— render 的預設分支本來就是唯讀（見
        `_core_satellite_verdict_caption` docstring），所以拿掉這一行不會讓畫面回到
        打臉狀態，但會讓下一個人以為 Tab3 沒有特殊處置。~~

        → **2026-08-31 WP-G 收斂：④ 已不再 embed 健診 3 表，本條改守「不得再 embed」。**
        **有意識的政策變更，不是漏刪**；決策者 **user**（2026-08-31 直接指派：
        「各頁不重複渲染相同功能 …… ④ 健診改單行連結」）。原 docstring 一字未刪、
        加刪除線保留 —— 它記錄的是「當年為什麼要有 `source_tab="portfolio"`」，
        那個來歷仍值得後人讀到。

        **兩邊理由並陳（舊條的理由仍然成立，只是它的前提被拿掉了）**：

        - **舊條為什麼是對的**：當年要求 ④ 自報身分，是因為 ④ **同一頁**上方另有一個
          「🛡️ 核心資產比例」，跟 embed 進來的「🧭 核心/衛星資產屬性分布」是**兩把
          不同的尺**（分類依據、分母、有無目標值都不同）。不講清楚，使用者會把兩個
          數字讀成「其中一個算錯了」。**這個顧慮今天依然正確。**
        - **新條為什麼勝出**：客戶把 ④ 的健診整區改成單行連結 → **兩把尺不再同頁出現**。
          舊條想防的問題是**被從根拿掉**，不是被放寬。留著舊斷言不但擋住這次交付，
          還會誤導後人以為「④ 應該要 embed」。

        **本條現在方向相反、而且更嚴（fail-closed）**：④ 不得再出現健診 3 表的呼叫
        （含改別名）。細部守衛（import / 呼叫 / 單行連結走 SSOT / 下游耦合保留）見
        `tests/test_wpg_portfolio_health_link_20260831.py`。

        ⚠️ **連帶失效、但本批未動的東西**（本次授權明文禁止動 ② 端一個字 → **登記不動**）：
        `_CS_WHERE_PORTFOLIO` 與 `_CS_PORTFOLIO_CONTRAST_NOTE`（連同
        `if source_tab != "health":` 那個分支）自此在 production **不可達** ——
        它們是專為 ④ embed 寫的。依 `CLAUDE.md` §-1.5.1c 判定 3(4)「因本次改動才變成
        沒用的」本該同批清掉，已列入 PR 待辦。**同班的
        `test_render_prints_the_contrast_note` 因此變成「守著一段死碼」**，一併登記。

        突變實驗（實跑）：把 `_render_health_tbl(_ok_health, funds_extra=_funds_extra,
        source_tab="portfolio")` 放回 `ui/tab3_portfolio.py` → **本條轉紅**
        （`AssertionError: 行 [...]：④ 又 embed 了健診 3 表`）。還原後轉綠。
        """
        _calls = [n for n in ast.walk(tab3_tree)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                  and n.func.id in ("_render_health_tbl", "_render_health_3tables")]
        assert not _calls, (
            f"行 {[c.lineno for c in _calls]}：④ 又 embed 了健診 3 表。\n"
            f"WP-G 之後 ④ 只留一行連結指向 ②（健診的唯一主場）。要恢復 embed 屬"
            f"**版面變更**，依 `CLAUDE.md` §-1.5 v3 §03-2 ① 須先出線框草稿給客戶拍板，"
            f"不能靠改測試放行。")


# ══════════════════════════════════════════════════════════════
# 5. 模擬本金不進配置比例（user 裁決第 4 點）
#
# `ui/tab3_portfolio.py` 對「使用者從未填過 invest_twd」的基金補 100 萬，好讓
# 逐檔配息試算算得出「每月配息 TWD」。那筆錢是模擬值，不是他的錢 —— 若進了
# 屬性比例分母，一檔沒填就能把比例整個帶偏，而且 `weight_mode` 會推斷成
# "amount"，caption 於是用捏造的金額背書「依各檔投入本金加權，總計 X TWD」。
# ══════════════════════════════════════════════════════════════
_HEALTH_ROWS = [{"核心/衛星": "🟦 核心"}, {"核心/衛星": "🟠 衛星"}]


class TestSimulatedPrincipalExcludedFromRatio:
    def test_simulated_principal_gets_zero_weight(self):
        """**修正前必紅（行為衝突）** —— 舊碼直接用 `_principal_twd`。

        使用者只填了核心那檔 20 萬、衛星那檔沒填（被補 100 萬）：
        舊行為 → 核心 20/120 ≈ 17%；正確 → 分母只有真實的 20 萬 → 核心 100%。
        """
        from ui.tab_fund_grp_health import _core_satellite_items
        _rows = [
            {"_principal_twd": 200_000.0},
            {"_principal_twd": 1_000_000.0, "_principal_is_default": True},
        ]
        _items, _n_sim = _core_satellite_items(_HEALTH_ROWS, _rows)
        assert _n_sim == 1
        assert _items[1]["weight"] == 0, "模擬本金仍被計入分母"
        assert _items[0]["weight"] == 200_000.0

    def test_excluded_weight_keeps_the_ratio_and_mode_honest(self):
        """端到端：接進 L2 後，比例與 `weight_mode` 都不得被模擬金額汙染。"""
        from services.health.asset_class import summarize_core_satellite_allocation
        from ui.tab_fund_grp_health import _core_satellite_items
        _rows = [
            {"_principal_twd": 200_000.0},
            {"_principal_twd": 1_000_000.0, "_principal_is_default": True},
        ]
        _csa = summarize_core_satellite_allocation(
            _core_satellite_items(_HEALTH_ROWS, _rows)[0])
        assert _csa["core_pct"] == 100.0
        assert _csa["total_weight"] == 200_000.0
        assert _csa["weight_mode"] == "single", (
            "只剩一筆真實金額卻被推斷成 amount → caption 會謊稱金額加權")

    def test_health_tab_broadcast_principal_unaffected(self):
        """健診 Tab 走使用者輸入的單一本金 broadcast，**不帶**旗標 → 行為零變化。"""
        from ui.tab_fund_grp_health import _core_satellite_items
        _rows = [{"_principal_twd": 1_000_000.0}, {"_principal_twd": 1_000_000.0}]
        _items, _n_sim = _core_satellite_items(_HEALTH_ROWS, _rows)
        assert _n_sim == 0
        assert [i["weight"] for i in _items] == [1_000_000.0, 1_000_000.0]

    def test_missing_label_falls_back_to_undetermined(self):
        """缺「核心/衛星」欄 → 待定（§1 不亂扣），不是靜默歸核心。"""
        from ui.tab_fund_grp_health import _core_satellite_items
        _items, _ = _core_satellite_items([{}, {"核心/衛星": ""}],
                                          [{"_principal_twd": 1}, {"_principal_twd": 1}])
        assert [i["label"] for i in _items] == ["待定", "待定"]


class TestSimulatedPrincipalWiring:
    """接線（`PROCESS.md §4`）：旗標與消費端必須同批存在，缺一即無效。"""

    def test_render_delegates_item_building_to_the_helper(self, grp_tree) -> None:
        """**修正前必紅（AST 找不到 `_core_satellite_items`）**。

        拿掉 render 那一行呼叫（改回 inline 迴圈直接吃 `_principal_twd`），本條紅。
        """
        _fn = _func_def(grp_tree, "_render_health_3tables")
        _names = {n.func.id for n in ast.walk(_fn)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "_core_satellite_items" in _names, (
            "render 沒走 items helper —— 模擬本金剔除等於沒接出去")

    def test_tab3_actually_stamps_the_flag(self, tab3_tree) -> None:
        """**修正前必紅（AST 找不到該欄位寫入）** —— 產生端的另一半。

        helper 讀得再對，Tab3 不 stamp 旗標就永遠讀到 None，模擬本金照樣進分母。
        一律走 AST（`ast.Subscript` 的字面 slice），不用 `re.search` 掃原始碼 ——
        本 repo 有過測試被自己的註解騙過的紀錄。
        """
        _field = "_principal" + "_is_default"      # 不讓字面值單獨出現在掃描面
        _writes = [n for n in ast.walk(tab3_tree)
                   if isinstance(n, ast.Subscript)
                   and isinstance(n.slice, ast.Constant)
                   and n.slice.value == _field
                   and isinstance(n.ctx, ast.Store)]
        assert _writes, "Tab3 未把「這檔用的是模擬本金」旗標寫回 row"
