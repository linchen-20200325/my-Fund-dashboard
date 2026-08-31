"""鐵律 1：固定 3 欄自適應網格 —— fail-closed 的結構守衛。

## 為什麼非有這個檔不可（實測，不是推測）

2026-08-28 稽核組做了一次突變實測：把 `ui/tab1_macro_inflection.py` 的
`st.columns(3)` 改成 `st.columns(6)`、下面照樣只用前 3 個回傳值 ——
**fast lane 與 slow lane 全綠**。同一輪一共注入 5 個違反四大鐵律的改動，
全 suite 的結果與基線**逐項相同**（`14 failed / 5347 passed`）。

也就是說：在本檔誕生前，「我維持了 3 欄自適應網格」是一句**沒有任何機器查得到**
的宣稱。依 `CLAUDE.md §-2` 規則 6，那種宣稱不得當成事實交付。

## 判定方向：fail-closed（這是本檔最重要的設計決定）

規則不是「命中某個形狀才檢查」，而是「**不是 3 就紅**」。
理由是本 repo 已經踩過的坑：鐵律 3（顏色分離）用的是白名單式偵測，於是
「把渲染呼叫包進一個自訂 helper」就能讓整條規則隱形（稽核 M2 實測全綠）。
白名單式規則會被一個 `_grid3()` helper 一秒繞過。

具體三條：

1. **欄數**：`st.columns(N)`
   - `N` 是**整數字面** → 必須 `== 3`，否則進豁免表才放行。
   - `N` 是**序列字面**（`[1, 2, 1]`）→ 一律要豁免登記。比例欄是刻意的版面決定，
     不是「自適應網格」，所以它**不會**因為 `len(...) == 3` 就自動合格。
   - `N` **不是字面**（變數 / `len(x)` / 函式呼叫）→ **一律視為違規**。
     「靜態證不出它是 3」＝ 違規；**刻意不留「動態算的就放行」這條路**，
     否則 `st.columns(_n)` 就是萬用通行證。
2. **寫死像素**：網格內的渲染呼叫不得帶整數字面的 `width=`，
   也不得 `use_container_width=False` —— 兩者都會讓欄位不再隨寬度自適應。
   （量測日 2026-08-28：現況 0 處，故這條是**乾淨的 fail-closed**，沒有豁免額度。）
3. **receiver 剝殼**：`st.sidebar.columns` / `col1.columns` / `_cols[2].columns` /
   `import streamlit as _s` 之後的 `_s.columns` 都要認得。
   **直接復用** `test_render_state_color_separation` 的 `_receiver_root` /
   `_st_container_names` —— 另寫一份會變成第二個 SSOT，而那正是本 repo
   `CLAUDE.md §2.1` 明文禁止的事（也是該檔自己踩過的坑：兩把尺量同一件事）。

## 豁免表的形狀：`路徑::函式()  columns(<shape>)×<次數>`

- **不寫行號**（沿用 `DIRECTION_A_SITES` 的理由：行號每次重構都漂，函式名不會）。
- **帶次數**：只記「這個函式有非 3 欄」會讓「把 `columns(2)` 改成 `columns(7)`」
  隱形；帶上 shape 與次數之後，任何形狀變動都會讓鍵不一致。
- **雙向 `==`，不是單向 `<=`**：直接抄 `test_a_caught_exception_backlog_only_shrinks`
  的形狀。單向額度會被「還一筆借一筆」的淨零置換繞過 —— 那條規則已經因為
  只寫 `<=` 被否證過一次（見該檔 X-4b 註記）。修好一處 → 本檔轉紅 →
  逼你把表一起降。**紅燈在這裡是提醒不是責備。**

## ⚠️ 已知會誤紅 / 守不到的情形（不要事後才發現）

- **誤紅（設計如此）**：新寫一個合理的 `st.columns(2)`（例如左右對照）會紅。
  正解是**登記進豁免表並寫理由**，不是把規則放寬 —— 登記本身就是那份「為什麼
  這裡不是 3 欄」的紀錄。
- **誤紅（跨組協作）**：另一組正在新增 `ui/components/` 元件。
  它們若**合規地**用 `st.columns(3)` → 不會進豁免表、不會紅（豁免表只綁**違規**
  站點，不綁所有站點）。但若新元件用了非 3 欄 → **會紅**，需同批登記。
- **守不到**：欄數對了、但內容把三欄塞成視覺上的一欄（CSS / `st.markdown` 手刻
  `<div style="display:grid">`）—— 那是字串內容，AST 看不到。
- **守不到**：跨函式傳進來的容器、存進 dict / list 的容器
  （`_st_container_names` 只認同一檔內由 `<streamlit 名>.<factory>(...)` 直接綁出的名字）。
- **守不到**：`getattr(st, "columns")(6)` 這種動態取屬性。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

# ⚠️ 刻意從既有規則檔匯入，不另寫一份 receiver 剝殼邏輯（§2.1 SSOT）。
from test_render_state_color_separation import (
    ROOT,
    UI_SOURCES,
    _receiver_root,
    _st_container_names,
)

#: 唯一合格的欄數。客戶 2026-08-28 拍板的「固定 3 欄自適應網格」。
REQUIRED_COLUMNS = 3

#: 會產生「網格內元素」的 st API —— 寫死寬度的檢查對象。
#: 刻意寬：漏一個，規則就在那個方向上是瞎的（同顏色規則檔 A3 的教訓）。
_WIDTH_SENSITIVE_ATTRS = frozenset({
    "dataframe", "table", "image", "plotly_chart", "altair_chart", "pyplot",
    "vega_lite_chart", "bokeh_chart", "map", "button", "download_button",
    "form_submit_button", "text_input", "number_input", "selectbox",
    "multiselect", "date_input", "text_area", "slider", "data_editor",
    "metric", "markdown", "container",
})


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    out: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[id(child)] = node
    return out


def _enclosing_function(node: ast.AST, parents: dict[int, ast.AST]) -> str:
    """這個節點住在哪個函式裡？找不到就是 `<module>`（module 層直接跑的）。"""
    cur = node
    while id(cur) in parents:
        cur = parents[id(cur)]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
    return "<module>"


def _columns_spec(call: ast.Call) -> ast.AST | None:
    """取 `st.columns(...)` 的欄數參數（位置或 `spec=` 關鍵字）。"""
    if call.args:
        return call.args[0]
    for kw in call.keywords:
        if kw.arg == "spec":
            return kw.value
    return None


def _shape_of(spec: ast.AST | None) -> str | None:
    """把欄數參數歸類成一個**穩定的字串**；回 None 表示合格（就是 3）。

    fail-closed：只有「整數字面 3」回 None，其餘一律歸類成違規形狀。
    """
    if isinstance(spec, ast.Constant) and isinstance(spec.value, int) \
            and not isinstance(spec.value, bool):
        return None if spec.value == REQUIRED_COLUMNS else f"int:{spec.value}"
    if isinstance(spec, (ast.List, ast.Tuple)):
        # 比例欄（`[2, 2, 1]`）即使剛好 3 格也要登記 —— 它是刻意的版面決定，
        # 不是「自適應等寬網格」。`len(...) == 3` 不構成自動合格。
        return f"seq:{len(spec.elts)}"
    if spec is None:
        return "missing"
    return "dynamic"          # 變數 / len(x) / 呼叫 …… 靜態證不出來 ＝ 違規


def _grid_violation_keys(path: pathlib.Path) -> list[str]:
    """本檔的欄數違規，回傳**結構鍵**（不含行號）。逐檔規則與 ratchet 共用這一把尺。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "columns":
            continue
        if _receiver_root(node.func.value) not in containers:
            continue                      # 不是 streamlit 的 columns（例如 pandas）
        shape = _shape_of(_columns_spec(node))
        if shape is None:
            continue                      # 合格：st.columns(3)
        out.append(f"{path.relative_to(ROOT)}::"
                   f"{_enclosing_function(node, parents)}()  columns({shape})")
    return out


def _grid_site_counts(paths) -> dict[str, int]:
    """`結構鍵 → 出現次數`。帶次數是為了讓「加第二個 columns(2)」也看得見。"""
    counts: dict[str, int] = {}
    for path in paths:
        for key in _grid_violation_keys(path):
            counts[key] = counts.get(key, 0) + 1
    return counts


def _as_table(counts: dict[str, int]) -> frozenset[str]:
    return frozenset(f"{k}×{v}" for k, v in counts.items())


def _all_streamlit_calls(path: pathlib.Path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if _receiver_root(node.func.value) not in containers:
            continue
        yield node, parents


# ══════════════════════════════════════════════════════════════════
# 豁免表（＝ 待辦的可見化，不是「這樣寫沒關係」）
# ══════════════════════════════════════════════════════════════════
# 量測日 2026-08-28、基準 commit `a28e6a3`：`ui/**` + `app.py` 共 109 個
# streamlit `columns()` 呼叫，其中 **21 個是合格的 `columns(3)`**，
# 其餘 **88 個**列在下表（53 個結構鍵）。
#
# ⚠️ 這不是「批准這樣寫」，是**把現況變成可見的待辦**：
#   - 數字與站點都只准在「有人真的改成 3 欄」時往下走；
#   - 想新增一個非 3 欄的版面 → 必須動這張表，而動表會出現在 diff 裡被 review 看到。
# ⚠️ 量測方法：`_grid_site_counts(UI_SOURCES)`，與逐檔規則同一把尺 —— 不要換尺再比大小。
GRID_EXEMPT_SITES = frozenset({
    "ui/components/macro_card.py::render_macro_card_grid()  columns(dynamic)×1",
    "ui/components/mk_clock.py::render_macro_clock()  columns(seq:2)×1",
    "ui/components/mk_dashboard.py::render_mk_war_room()  columns(seq:2)×1",
    "ui/helpers/fund_grp_health/ai.py::_render_per_fund_news_expanders()  columns(seq:2)×1",
    "ui/helpers/fund_grp_health/ai.py::_render_per_fund_three_ratio_expanders()  columns(seq:2)×1",
    "ui/helpers/fund_grp_health/investment.py::_render_investment_calc()  columns(int:4)×1",
    "ui/helpers/fund_grp_health/investment.py::_render_investment_calc()  columns(seq:2)×1",
    "ui/helpers/fund_grp_health/regime_section.py::render_regime_fit_section()  columns(int:4)×1",
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()  columns(int:2)×3",
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()  columns(seq:3)×1",
    "ui/helpers/fund_grp_health/switch_advisor_section.py::render_portfolio_tracking()  columns(int:4)×1",
    "ui/helpers/holdings.py::render_holdings_detail()  columns(int:2)×1",
    "ui/helpers/portfolio/linkage.py::render_fund_portfolio_membership()  columns(seq:2)×1",
    "ui/helpers/portfolio_perf.py::render_portfolio_performance()  columns(int:4)×1",
    "ui/helpers/v2_editor.py::_render_div_split_estimate()  columns(seq:2)×1",
    "ui/helpers/v2_editor.py::_render_new_policy_section()  columns(seq:2)×1",
    "ui/helpers/v2_editor.py::render_first_use_wizard()  columns(int:2)×2",
    "ui/helpers/v2_editor.py::render_first_use_wizard()  columns(seq:2)×1",
    "ui/hot_money.py::render_hot_money_section()  columns(int:2)×1",
    "ui/hot_money.py::render_hot_money_section()  columns(int:4)×1",
    "ui/hot_money.py::render_hot_money_section()  columns(seq:2)×1",
    "ui/hot_money.py::render_hot_money_section()  columns(seq:4)×1",
    "ui/tab1_macro.py::_render_realtime_decision_dashboard()  columns(dynamic)×1",
    "ui/tab1_macro_inflection.py::render_inflection_alert_section()  columns(int:2)×1",
    "ui/tab1_macro_inflection.py::render_inflection_alert_section()  columns(int:5)×1",
    "ui/tab1_macro_longterm.py::render_long_term_section()  columns(int:4)×1",
    "ui/tab1_macro_longterm.py::render_long_term_section()  columns(seq:2)×1",
    "ui/tab1_macro_midcycle.py::render_mid_cycle_section()  columns(int:5)×1",
    "ui/tab1_macro_radar.py::render_short_radar_section()  columns(int:5)×1",
    "ui/tab1_macro_radar.py::render_short_radar_section()  columns(seq:2)×2",
    "ui/tab2_single_fund.py::render_single_fund_tab()  columns(int:2)×1",
    "ui/tab2_single_fund.py::render_single_fund_tab()  columns(int:4)×1",
    # 2026-08-31 WP-F：×5 → ×4（**變少，不是漏登**）。刪掉的那一個是孤兒關鍵字搜尋框
    # 裡的 `st.columns([4,1])`（輸入框 + 搜尋鈕）—— 該分支自七→五接線起在 production
    # 恆不觸發（唯一 caller 永遠持有 SHARED_SEARCH 旗標），整段已實體刪除。
    # 「找代號」工具現在只有一份，住在 `ui/helpers/fund_research/code_finder.py`。
    "ui/tab2_single_fund.py::render_single_fund_tab()  columns(seq:2)×4",
    # WP-D 2026-08-28：下面這組原本掛在 `ui/tab3_portfolio.py::render_portfolio_tab()`，
    # 因「📋 保單管理（Google Sheets）」整段（790 行）抽成 `policy_admin_section.py`
    # 而改掛新函式。**違規呼叫數一個沒有增減**（見該批 PR 的守恆對照），
    # 這是本檔 docstring 寫的「錨點失效（拆函式）→ 更新表」那一種，不是新增豁免。
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()  columns(int:2)×3",
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()  columns(int:5)×1",
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()  columns(seq:2)×4",
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()  columns(seq:3)×1",
    "ui/tab3_portfolio.py::render_portfolio_tab()  columns(seq:2)×4",
    "ui/tab3_portfolio.py::render_portfolio_tab()  columns(seq:3)×1",
    "ui/tab3_t7_ledger.py::render_t7_section()  columns(dynamic)×5",
    "ui/tab3_t7_ledger.py::render_t7_section()  columns(int:2)×2",
    "ui/tab3_t7_ledger.py::render_t7_section()  columns(seq:2)×3",
    "ui/tab3_t7_ledger.py::render_t7_section()  columns(seq:3)×3",
    "ui/tab3_t7_ledger.py::render_t7_section()  columns(seq:6)×2",
    "ui/tab5_data_guard.py::render_data_guard_tab()  columns(int:2)×2",
    "ui/tab5_data_guard.py::render_data_guard_tab()  columns(int:4)×5",
    "ui/tab5_data_guard.py::render_data_guard_tab()  columns(seq:2)×3",
    "ui/tab5_data_guard.py::render_data_guard_tab()  columns(seq:3)×1",
    "ui/tab_batch_analysis.py::_render_existing_results()  columns(int:4)×1",
    "ui/tab_batch_analysis.py::_render_recent_checkpoints()  columns(seq:2)×1",
    "ui/tab_batch_analysis.py::render_batch_analysis_tab()  columns(int:2)×1",
    "ui/tab_batch_analysis.py::render_batch_analysis_tab()  columns(seq:3)×1",
    "ui/tab_fund_grp_health.py::_render_health_3tables()  columns(int:4)×1",
    "ui/tab_fund_grp_health.py::_render_health_table()  columns(int:5)×1",
    "ui/tab_fund_grp_health.py::_render_low_base_screener()  columns(int:2)×1",
})

#: 量測日 2026-08-28 的**違規呼叫總數**（不是鍵數）。與上表一起降。
# 2026-08-31 WP-F：88 → 87（**變少**；刪掉孤兒搜尋框的 `st.columns([4,1])`，
# 理由見上方 `tab2_single_fund` 那一列的註記）。
GRID_EXEMPT_CALL_TOTAL = 87

#: 量測日 2026-08-28 掃到的 streamlit `columns()` 呼叫總數（合格 + 違規）。
#: 錨點用：低於這個數字代表 `st.columns` 被換成別的寫法，規則正在對空氣生效。
GRID_ANCHOR_MIN_COLUMNS_CALLS = 100


def test_grid_columns_must_be_three_or_be_registered():
    """欄數不是 3 就紅 —— 除非它在 `GRID_EXEMPT_SITES` 裡具名登記。

    ⚠️ 這條是 **fail-closed**：它抓的不是「某個已知壞形狀」，而是「**所有不是 3 的**」。
    包成 helper（`def _grid3(): return st.columns(3)`）**不會**讓非 3 欄隱形 ——
    因為規則掃的是 `columns()` 呼叫本身，不是呼叫它的地方。
    """
    counts = _grid_site_counts(UI_SOURCES)
    found = _as_table(counts)
    new = sorted(found - GRID_EXEMPT_SITES)
    fixed = sorted(GRID_EXEMPT_SITES - found)
    assert not new, (
        "以下位置的欄數不是 3（或靜態證不出它是 3），而且沒有在 `GRID_EXEMPT_SITES` 登記。\n"
        "客戶 2026-08-28 拍板的鐵律 1 是「固定 3 欄自適應網格」；\n"
        "若這裡確實不該是 3 欄（比例欄 / 左右對照 / 動態欄數），"
        "請把它加進 `GRID_EXEMPT_SITES` 並在 PR 描述寫理由 —— 登記本身就是那份紀錄。\n  "
        + "\n  ".join(new))
    assert not fixed, (
        "以下站點已經修好（或檔案／函式改名），但 `GRID_EXEMPT_SITES` 還留著它 ——\n"
        "請把表一起更新。**這條紅燈是提醒不是責備。**\n"
        "⚠️ 若你是**把整個區塊刪掉**才讓它消失：那也要更新表，但請確認畫面沒有默默少一塊。\n  "
        + "\n  ".join(fixed))


def test_grid_exempt_total_matches_the_table():
    """豁免**呼叫數**也要對得上 —— 擋「還一筆借一筆」的淨零置換。

    只斷言站點集合時，同一個結構鍵底下多加一個同形狀的 `columns(2)` 會讓
    `×N` 變動而被上一條抓到；本條再多守一層總數，讓「表沒更新」在數字上也現形。
    （形狀直接抄 `test_a_caught_exception_backlog_only_shrinks`，該規則已因為
      原本只寫單向 `<=` 被實測否證過一次。）
    """
    total = sum(_grid_site_counts(UI_SOURCES).values())
    assert total == GRID_EXEMPT_CALL_TOTAL, (
        f"非 3 欄的 `columns()` 呼叫從 {GRID_EXEMPT_CALL_TOTAL} 變成 {total}。\n"
        f"⚠️ 變**少**是好事，請把 `GRID_EXEMPT_CALL_TOTAL` 一起改成 {total}；\n"
        f"⚠️ 變**多**請改成 3 欄，或連同 `GRID_EXEMPT_SITES` 一起登記並附理由。")


def test_grid_anchor_streamlit_columns_still_detectable():
    """錨點：`st.columns` 還在被掃到嗎？

    不加這條，有人把 `st.columns` 換成別的寫法（自訂 helper 回傳容器、
    `getattr(st, "columns")`）時，上面兩條會**對空氣生效**、天天綠。
    ⚠️ 這條守的是「規則還看得見東西」，不是「欄數對不對」。
    """
    n = sum(1 for p in UI_SOURCES
            for call, _ in _all_streamlit_calls(p)
            if call.func.attr == "columns")
    assert n >= GRID_ANCHOR_MIN_COLUMNS_CALLS, (
        f"只掃到 {n} 個 streamlit `columns()` 呼叫（量測日 2026-08-28 為 109，"
        f"錨點下限 {GRID_ANCHOR_MIN_COLUMNS_CALLS}）——\n"
        "欄數規則可能正在對空氣生效。請確認 `st.columns` 沒有被包進看不見的 helper，"
        "或是這批真的整批刪掉了版面（那要一起降錨點）。")


@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_grid_cells_do_not_hardcode_width(path: pathlib.Path):
    """網格內不得寫死像素寬 —— 寫死了就不叫「自適應」。

    兩種寫法都紅：
      - `width=<整數字面>`（`width="stretch"` / `width="content"` 這種語意值不受影響）；
      - `use_container_width=False`（明確關掉自適應）。

    量測日 2026-08-28 現況 **0 處** —— 這是一條**乾淨的 fail-closed**，沒有豁免額度。
    ⚠️ 守不到：CSS 手刻的固定寬（`st.markdown('<div style="width:400px">')`）——
    那是字串內容，AST 看不到。
    """
    bad = []
    for call, parents in _all_streamlit_calls(path):
        if call.func.attr not in _WIDTH_SENSITIVE_ATTRS:
            continue
        where = f"{path.relative_to(ROOT)}::{_enclosing_function(call, parents)}()"
        for kw in call.keywords:
            v = kw.value
            if kw.arg == "width" and isinstance(v, ast.Constant) \
                    and isinstance(v.value, int) and not isinstance(v.value, bool):
                bad.append(f"{where}  {ast.unparse(call.func)}(width={v.value})"
                           f"（第 {call.lineno} 行）")
            if kw.arg == "use_container_width" and isinstance(v, ast.Constant) \
                    and v.value is False:
                bad.append(f"{where}  {ast.unparse(call.func)}"
                           f"(use_container_width=False)（第 {call.lineno} 行）")
    assert not bad, (
        "以下位置把寬度寫死，欄位不會再隨視窗自適應（鐵律 1）：\n  "
        + "\n  ".join(bad)
        + "\n請改用 `use_container_width=True`（或 `width=\"stretch\"`）。")


def test_grid_declared_sources_still_exist():
    """`UI_SOURCES` 掃得到東西嗎？—— 規則整條蒸發是無聲的。

    parametrize 到 0 個 case 也算通過；ratchet 只擋得住「數字變大」，
    擋不住「掃描範圍變成空集合」。（同顏色規則檔 `test_a_declared_batch_scope_still_exists`。）
    """
    missing = sorted(str(p) for p in UI_SOURCES if not p.is_file())
    assert not missing, f"下列路徑已不存在：{missing}"
    assert len(UI_SOURCES) >= 40, (
        f"`UI_SOURCES` 只有 {len(UI_SOURCES)} 個檔（量測日 2026-08-28 遠多於此）——"
        "掃描範圍可能壞了，本檔所有規則正在對空氣生效。")
