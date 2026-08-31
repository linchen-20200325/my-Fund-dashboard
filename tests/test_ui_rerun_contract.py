"""鐵律 2：`st.form` 防重繪 —— 既有的 form 不准退化，多輸入區塊不准裸奔。

## 為什麼非有這個檔不可（實測，不是推測）

2026-08-28 稽核組突變實測：把 `ui/helpers/fund_grp_health/switch_advisor_section.py`
的 `with st.form(...)` 改成 `with st.container()`、`st.form_submit_button` 改成
`st.button` —— **fast lane 與 slow lane 全綠**。同一輪一共注入 5 個違反四大鐵律的
改動，全 suite 結果與基線**逐項相同**（`14 failed / 5347 passed`）。

`st.form` 在 Streamlit 是「這一整組輸入按下送出前不要 rerun」的唯一機制。
拆掉它，使用者每敲一個字、每選一次下拉，整個 script 就從頭跑一次
（本 repo 的 Tab 動輒抓 NAV / 打 Google Sheets）。**畫面看起來一樣，體驗完全不同**
—— 這正是一種「肉眼 review 抓不到、測試也沒在看」的退化。

## 四條規則與它們各自的方向

| # | 規則 | 方向 | 現況 |
|---|---|---|---|
| 1 | 既有 `st.form` 站點不准消失 | 資產登記（`==`） | 6 處 / 4 檔 |
| 2 | 每個 `with st.form(...)` 內必須有 `form_submit_button` | fail-closed，無額度 | 0 違規 |
| 3 | 同一區塊 ≥2 個輸入 + 其後的 `st.button` → 必須包 form | fail-closed + ratchet | 4 處 / 3 函式 |
| 4 | 既有的 checkbox / button 延遲載入 gate 不准被刪 | 資產登記（子集） | 22 函式 / 64 處 |

⚠️ **規則 4 的方向是本檔唯一一條「不對稱」的 ratchet，理由寫在這裡供覆核**：
規則 1~3 守的是**違規存量**（壞東西），依 `CLAUDE.md` 既有慣例用**雙向 `==`**，
因為單向額度會被「還一筆借一筆」的淨零置換繞過
（見 `test_a_caught_exception_backlog_only_shrinks` 的 X-4b 否證紀錄）。
規則 4 守的是**資產存量**（gate 是好東西），淨零置換的攻擊面不存在
—— 「多一個 gate」不是借，是還。若也用 `==`，等於**每加一個按鈕就把 CI 弄紅**，
而且會與正在新增 `ui/components/` 元件的另一組正面衝突。
故規則 4 採**子集斷言**：登記過的函式必須**至少還有一個 gate**；新增 gate 不罰。
📌 **這是實作組的判斷，不是規格明文** —— 派工規格寫的是「記錄現況站點、只准減不准增」，
而「只准減」對一個好東西是反向的。**已就地揭露，請總管裁決**（`CLAUDE.md §-2` 規則 6）。

## receiver 剝殼

`st.form` / `col1.form` / `_s.form`（`import streamlit as _s`）都要認得。
**直接復用** `test_render_state_color_separation` 的 `_receiver_root` /
`_st_container_names`，不另寫一份（§2.1 SSOT）。

## ⚠️ 已知會誤紅 / 守不到的情形（不要事後才發現）

- **錨點失效（規則 1）**：把一個 form 從 `render_t7_section()` 搬進新的
  `_render_t7_form()`，**form 還在、寫法完全正確**，但鍵從
  `…::render_t7_section()×3` 變成兩個鍵 → **會紅**。
  這是刻意的：拆函式是版面/結構改動，值得在 diff 裡被看到；正解是更新 `FORM_SITES`。
- **守不到（規則 3）**：輸入與按鈕被拆進**不同函式**（`_inputs()` + `_actions()`），
  本檔只在**同一個語句區塊**內配對，跨函式的資料流不追。
- **守不到（規則 3）**：`st.data_editor` / `st.chat_input` / `st.file_uploader`
  等不在 `_INPUT_WIDGETS` 內的輸入型元件。集合漏一個，規則在那個方向上就是瞎的
  —— 這裡據實列出，**不要讀成「已經涵蓋所有輸入」**。
- **守不到（規則 4）**：把 gate 的條件改成恆真（`if st.button(...) or True:`）——
  gate 還在、形狀還在，但已經不 gate 了。
- **守不到（全檔）**：`getattr(st, "form")` 這種動態取屬性；
  跨函式傳進來的容器、存進 dict / list 的容器（`_st_container_names` 的既有邊界）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest
from test_render_state_color_separation import (
    ROOT,
    UI_SOURCES,
    _receiver_root,
    _st_container_names,
)

#: 會讓「每敲一下就整頁重跑」的輸入元件。
#: ⚠️ 刻意**不含** `data_editor` / `file_uploader` / `chat_input` —— 它們的送出語意
#: 與純輸入不同，硬塞進來會製造誤紅。**這代表本規則在那幾個方向上是瞎的**，已在檔頭列明。
_INPUT_WIDGETS = frozenset({
    "text_input", "number_input", "selectbox", "date_input", "multiselect",
})

#: 延遲載入 gate：用它包住重運算，讓首屏不要無條件跑。
_GATE_WIDGETS = frozenset({"checkbox", "button", "toggle"})


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    out: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            out[id(child)] = node
    return out


def _enclosing_function(node: ast.AST, parents: dict[int, ast.AST]) -> str:
    cur = node
    while id(cur) in parents:
        cur = parents[id(cur)]
        if isinstance(cur, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return cur.name
    return "<module>"


def _is_st_call(node: ast.AST, containers: frozenset[str], attr: str) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr == attr
            and _receiver_root(node.func.value) in containers)


def _form_with_nodes(tree: ast.AST, containers: frozenset[str]) -> list[ast.With]:
    """所有 `with st.form(...):` 的 With 節點。"""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)) and any(
                _is_st_call(item.context_expr, containers, "form") for item in node.items):
            out.append(node)
    return out


def _form_site_counts(paths) -> dict[str, int]:
    counts: dict[str, int] = {}
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        containers = _st_container_names(tree)
        parents = _parents(tree)
        for node in _form_with_nodes(tree, containers):
            key = f"{path.relative_to(ROOT)}::{_enclosing_function(node, parents)}()"
            counts[key] = counts.get(key, 0) + 1
    return counts


def _as_table(counts: dict[str, int]) -> frozenset[str]:
    return frozenset(f"{k}×{v}" for k, v in counts.items())


# ── 規則 3 用：把每個呼叫歸給「它最近的那個語句區塊」──────────────────
def _block_index(tree: ast.AST):
    """`id(stmt) -> (區塊 id, 在區塊內的序號)`。

    刻意以**語句區塊**（statement list）為單位，而不是 `ast.walk` 整棵子樹：
    後者會讓外層區塊把內層的輸入一起算進來，同一批輸入被重複歸屬到每一層祖先
    （初稿實測：28 個重複命中 vs 實際 4 處）。
    """
    out: dict[int, tuple[int, int]] = {}
    for node in ast.walk(tree):
        for field in ("body", "orelse", "finalbody"):
            block = getattr(node, field, None)
            if isinstance(block, list) and block and isinstance(block[0], ast.stmt):
                for i, stmt in enumerate(block):
                    out[id(stmt)] = (id(block), i)
    return out


def _naked_multi_input_keys(path: pathlib.Path) -> list[str]:
    """同一區塊出現 ≥2 個輸入、其後又有 `st.button`，而且**沒有**被 form 包住。

    這是鐵律 2 的**反向**規則：規則 1 守「既有 form 不要不見」，
    本規則守「該包 form 的地方不要一直不包」。少了它，只要不去動既有那 5 處，
    新寫的多輸入區塊可以永遠裸奔。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    blocks = _block_index(tree)

    inside_form: set[int] = set()
    for node in _form_with_nodes(tree, containers):
        for sub in ast.walk(node):
            inside_form.add(id(sub))

    per_block: dict[int, list[tuple[int, ast.Call]]] = {}
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr not in _INPUT_WIDGETS | {"button"}:
            continue
        if _receiver_root(node.func.value) not in containers:
            continue
        if id(node) in inside_form:
            continue                                   # 已經在 form 裡 → 合規
        cur: ast.AST = node                            # 找它所屬的那一個語句
        while id(cur) in parents and id(cur) not in blocks:
            cur = parents[id(cur)]
        if id(cur) not in blocks:
            continue
        block_id, idx = blocks[id(cur)]
        per_block.setdefault(block_id, []).append((idx, node))

    out: list[str] = []
    for items in per_block.values():
        inputs = [(i, c) for i, c in items if c.func.attr in _INPUT_WIDGETS]
        buttons = [(i, c) for i, c in items if c.func.attr == "button"]
        if len(inputs) < 2 or not buttons:
            continue
        last_input = max(i for i, _ in inputs)
        after = [c for i, c in buttons if i >= last_input]   # 「緊接其後」的送出鈕
        if not after:
            continue
        out.append(f"{path.relative_to(ROOT)}::"
                   f"{_enclosing_function(after[0], parents)}()")
    return out


def _gate_function_keys(path: pathlib.Path) -> list[str]:
    """`if st.checkbox(...) / st.button(...) / st.toggle(...):` 這種延遲載入 gate。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        if any(_is_st_call(sub, containers, sub.func.attr)
               and sub.func.attr in _GATE_WIDGETS
               for sub in ast.walk(node.test) if isinstance(sub, ast.Call)
               and isinstance(sub.func, ast.Attribute)):
            out.append(f"{path.relative_to(ROOT)}::{_enclosing_function(node, parents)}()")
    return out


# ══════════════════════════════════════════════════════════════════
# 規則 1：既有的 `st.form` 站點（資產登記）
# ══════════════════════════════════════════════════════════════════
# 量測日 2026-08-31、基準 commit `5f798ee`：`ui/**` + `app.py` 共 **6 個**
# `with st.form(...)`，分佈 4 檔。（`tests/test_app_smoke.py` 內另有 1 個，
#  不在 `UI_SOURCES` 範圍內，本表不含 —— 測試檔不是產品程式碼。）
# ⚠️ 本表由本組**自行重掃**產出，不是照抄派工單。
# 沿革：量測日 2026-08-28（commit `a28e6a3`）為 5 個 / 3 檔；2026-08-31 新增元件 B 一處。
FORM_SITES = frozenset({
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()×1",
    # 2026-08-31：③ 批次「🧩 互補配對探索」的 3 支門檻滑桿包進 form + 「套用門檻」submit。
    # **這是新增一處 form（好事），不是搬家** —— #738 建元件 B 時就該包，當時因本檔正由
    # #736 佔用（File Boundary 防撞）而具名延後，阻擋解除後於本批補上。
    # 客戶已拍板線框（`docs/wireframes/rotation-components-wireframe.html` §03 區塊 1
    # 「3 欄滑桿 ＋『套用門檻』鈕」）即長這樣，故屬「實作補齊既有規格」而非新設計。
    "ui/helpers/fund_grp_health/rotation.py::render_complementary_explorer_from_df()×1",
    # WP-D 2026-08-28：下面這組原本掛在 `ui/tab3_portfolio.py::render_portfolio_tab()`，
    # 因「📋 保單管理（Google Sheets）」整段（790 行）抽成 `policy_admin_section.py`
    # 而改掛新函式。**違規呼叫數一個沒有增減**（見該批 PR 的守恆對照），
    # 這是本檔 docstring 寫的「錨點失效（拆函式）→ 更新表」那一種，不是新增豁免。
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()×1",
    "ui/tab3_t7_ledger.py::render_t7_section()×3",
})
FORM_SITE_TOTAL = 6   # 2026-08-31：5 → 6（元件 B 門檻列包 form；上一行那筆）


def test_existing_forms_must_not_degrade():
    """既有的 `st.form` 不准被換成 `st.container` —— 這正是稽核組突變過、全綠的那一招。

    雙向 `==`：拆掉 form 會紅；**新增** form 也會紅（提醒你把表一起加上去）。
    新增 form 是好事，紅燈只是要你留一筆紀錄，不是叫你別加。
    """
    found = _as_table(_form_site_counts(UI_SOURCES))
    lost = sorted(FORM_SITES - found)
    added = sorted(found - FORM_SITES)
    assert not lost, (
        "以下 `st.form` 站點不見了（或函式改名 / form 數量變了）。\n"
        "`st.form` 是「送出前不要 rerun」的唯一機制，拆掉它畫面看起來一樣、"
        "但使用者每敲一個字整個 Tab 就重抓一次資料：\n  "
        + "\n  ".join(lost)
        + "\n⚠️ 若你是**刻意搬家 / 拆函式**：form 還在就把 `FORM_SITES` 一起更新。")
    assert not added, (
        "新增了 `st.form` 站點（這是好事）—— 請把它加進 `FORM_SITES`，"
        "讓下一個人也不能把它拆掉：\n  " + "\n  ".join(added))


def test_form_site_total_matches_the_table():
    """總數也要對得上 —— 擋「拆掉一處、別處補一處」的淨零置換。"""
    total = sum(_form_site_counts(UI_SOURCES).values())
    assert total == FORM_SITE_TOTAL, (
        f"`st.form` 站點總數從 {FORM_SITE_TOTAL} 變成 {total} —— "
        f"請連同 `FORM_SITES` 一起更新（並確認不是把某處拆掉換來的）。")


@pytest.mark.parametrize("path", UI_SOURCES, ids=lambda p: str(p.name))
def test_every_form_has_a_submit_button(path: pathlib.Path):
    """`with st.form(...)` 內必須至少有一個 `form_submit_button`。

    fail-closed，沒有豁免額度（量測日 2026-08-28 現況 0 違規）。
    一個沒有 `form_submit_button` 的 form 在 Streamlit 執行期會直接丟
    `StreamlitAPIException` —— 但那是**跑到那一頁才會炸**，而本 repo 的
    slow lane 只跑 AppTest smoke，不保證每個 form 都被走到。
    把它變成靜態規則，才是「跑不到也守得住」。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"))
    containers = _st_container_names(tree)
    parents = _parents(tree)
    bad = []
    for node in _form_with_nodes(tree, containers):
        has_submit = any(
            isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
            and sub.func.attr == "form_submit_button"
            for sub in ast.walk(node))
        if not has_submit:
            bad.append(f"{path.relative_to(ROOT)}::"
                       f"{_enclosing_function(node, parents)}()（第 {node.lineno} 行）")
    assert not bad, (
        "以下 `st.form` 區塊內沒有 `form_submit_button`，使用者按不出去：\n  "
        + "\n  ".join(bad))


# ══════════════════════════════════════════════════════════════════
# 規則 3：多輸入區塊必須進 form（fail-closed + ratchet）
# ══════════════════════════════════════════════════════════════════
# 量測日 2026-08-28、基準 commit `a28e6a3`：**4 處 / 3 個函式**。
# ⚠️ 這不是「批准這樣寫」，是**待辦的可見化**。四處都是真的（人工複核過）：
#   - `_render_pool_editor()` 的「改型態 / 移除」兩個 selectbox + 兩顆按鈕；
#     以及進階區的 3 個輸入（基金 / secId / 幣別）+「存晨星代碼」按鈕。
#   - `render_first_use_wizard()` / `render_portfolio_tab()` 同型態。
# 每一處都會讓使用者**還沒填完就整頁重跑**。
NAKED_MULTI_INPUT_SITES = frozenset({
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()×2",
    "ui/helpers/v2_editor.py::render_first_use_wizard()×1",
    # WP-D 2026-08-28：下面這組原本掛在 `ui/tab3_portfolio.py::render_portfolio_tab()`，
    # 因「📋 保單管理（Google Sheets）」整段（790 行）抽成 `policy_admin_section.py`
    # 而改掛新函式。**違規呼叫數一個沒有增減**（見該批 PR 的守恆對照），
    # 這是本檔 docstring 寫的「錨點失效（拆函式）→ 更新表」那一種，不是新增豁免。
    "ui/helpers/portfolio/policy_admin_section.py::render_policy_admin_section()×1",
})
NAKED_MULTI_INPUT_TOTAL = 4


def test_multi_input_blocks_must_be_wrapped_in_a_form():
    """≥2 個輸入 + 其後的按鈕 → 必須包 `st.form`，否則進 ratchet 具名登記。

    ⚠️ **fail-closed**：規則不是「命中某個已知壞檔才檢查」，而是掃全部
    `ui/**` + `app.py`，不在表上就紅。新寫的多輸入區塊不包 form → 當場紅。
    ⚠️ 雙向 `==`：修好一處（包進 form）→ 本條轉紅 → 逼你把表一起降。
    **紅燈在這裡是提醒不是責備。**
    """
    counts: dict[str, int] = {}
    for path in UI_SOURCES:
        for key in _naked_multi_input_keys(path):
            counts[key] = counts.get(key, 0) + 1
    found = _as_table(counts)
    new = sorted(found - NAKED_MULTI_INPUT_SITES)
    fixed = sorted(NAKED_MULTI_INPUT_SITES - found)
    assert not new, (
        "以下區塊有 2 個以上輸入元件、後面接著一顆 `st.button`，卻沒有包在 `st.form` 裡 ——\n"
        "使用者每改一個欄位，整個 Tab 就從頭重跑一次（本 repo 的 Tab 會重抓 NAV / 打 Sheets）。\n"
        "請用 `with st.form(...)` 包起來、按鈕改 `st.form_submit_button`：\n  "
        + "\n  ".join(new))
    assert not fixed, (
        "以下站點已經修好（或改名），請把 `NAKED_MULTI_INPUT_SITES` 與 "
        "`NAKED_MULTI_INPUT_TOTAL` 一起降下來。**這條紅燈是提醒不是責備。**\n"
        "⚠️ 若你是**把輸入欄位整個刪掉**才讓它消失：那不算修好，請確認功能沒有默默少一塊。\n  "
        + "\n  ".join(fixed))
    total = sum(counts.values())
    assert total == NAKED_MULTI_INPUT_TOTAL, (
        f"裸奔的多輸入區塊從 {NAKED_MULTI_INPUT_TOTAL} 變成 {total} —— 請一起更新常數。")


# ══════════════════════════════════════════════════════════════════
# 規則 4：既有的延遲載入 gate（資產登記，子集斷言 —— 方向理由見檔頭）
# ══════════════════════════════════════════════════════════════════
# 量測日 2026-08-28、基準 commit `a28e6a3`：22 個函式、共 64 處 `if st.<gate>(...)`。
# 本表只記「**哪些函式有 gate**」，**刻意不記次數** —— 次數（×17 / ×11）每加一顆
# 按鈕就變動，會把 CI 變成噪音來源，且會與正在新增 `ui/components/` 的另一組衝突。
GATE_FUNCTIONS = frozenset({
    "ui/helpers/fund_grp_health/switch_advisor_section.py::_render_pool_editor()",
    "ui/helpers/fund_grp_health/switch_advisor_section.py::render_switch_advisor_section()",
    "ui/helpers/io/freshness.py::_render_data_health_ai()",
    "ui/helpers/portfolio/linkage.py::render_fund_portfolio_membership()",
    "ui/helpers/v2_editor.py::_render_new_policy_section()",
    "ui/helpers/v2_editor.py::_render_policy_block()",
    "ui/helpers/v2_editor.py::render_first_use_wizard()",
    "ui/helpers/v2_editor.py::render_v2_section()",
    "ui/hot_money.py::render_hot_money_section()",
    "ui/sidebar.py::render_sidebar()",
    "ui/tab1_macro_longterm.py::render_long_term_section()",
    "ui/tab1_macro_radar.py::render_short_radar_section()",
    "ui/tab2_single_fund.py::render_single_fund_tab()",
    "ui/tab3_portfolio.py::render_portfolio_tab()",
    "ui/tab3_t7_ledger.py::render_t7_section()",
    "ui/tab5_data_guard.py::render_data_guard_tab()",
    "ui/tab_batch_analysis.py::_render_recent_checkpoints()",
    "ui/tab_fund_grp_health.py::render_fund_grp_health_tab()",
    "ui/tab_manage.py::_sec_dividend_calendar()",
    "ui/tab_manage.py::_sec_nav_backfill()",
    "ui/tab_manage.py::_sec_nav_backfill_auto()",
    "ui/tab_manage.py::_sec_notify()",
})

#: 量測日 2026-08-28 的 gate 總處數。錨點用（防「規則對空氣生效」），不是上限。
GATE_ANCHOR_MIN_SITES = 55


def test_existing_lazy_load_gates_must_not_disappear():
    """登記過的函式必須**至少還有一個** gate —— 刪掉 gate ＝ 首屏無條件跑重運算。

    ⚠️ **子集斷言，不是 `==`**（本檔唯一一條不對稱的 ratchet，理由見檔頭）：
    新增 gate 是好事，不該讓 CI 紅。這條只擋「把既有的 gate 拿掉」。
    📌 派工規格原本寫的是「只准減不准增」；本組判定那對一個**好東西**是反向的，
    改為子集斷言並就地揭露 —— **請總管裁決**（`CLAUDE.md §-2` 規則 6）。
    """
    found = {k for p in UI_SOURCES for k in _gate_function_keys(p)}
    lost = sorted(GATE_FUNCTIONS - found)
    assert not lost, (
        "以下函式原本用 checkbox / button gate 擋住重運算，現在 gate 不見了 ——\n"
        "使用者一進分頁就會無條件觸發抓取（鐵律 2 / 鐵律 4）：\n  "
        + "\n  ".join(lost)
        + "\n⚠️ 若你是**刻意搬家 / 改名**：gate 還在就把 `GATE_FUNCTIONS` 一起更新。")


def test_gate_anchor_still_detectable():
    """錨點：gate 還掃得到嗎？

    不加這條，有人把 `if st.button(...)` 換成別的寫法時，上一條會**對空氣生效**。
    """
    n = sum(len(_gate_function_keys(p)) for p in UI_SOURCES)
    assert n >= GATE_ANCHOR_MIN_SITES, (
        f"只掃到 {n} 處延遲載入 gate（量測日 2026-08-28 為 64，錨點下限 "
        f"{GATE_ANCHOR_MIN_SITES}）—— gate 規則可能正在對空氣生效。")


#: `form_submit_button` 的數量下限 —— **等於當下實測值,刻意不留容忍度**。
#: ⚠️ 2026-08-31 稽核指出:本條原本寫死 `>= 5`,而實測自 2026-08-28 起就是 6、
#: 本批之後是 7 —— 也就是**容忍度從 1 悄悄變成 2**:可以無聲拆掉兩個 form 而本條不紅。
#: 「下限沒跟著實測值走」本身就是一種靜默弱化,所以現在把它綁死在實測值上。
#: **這是「會漂移的量測值」**:每次有意增減 form 都要一起改這個數字(改它是正常維護,
#: 不是繞過守衛)—— 相對地,**沒改它就退化,一定會紅**,那正是本條要的效果。
_FORM_SUBMIT_FLOOR = 7


def test_form_anchor_still_detectable():
    """錨點：`st.form` 與 `form_submit_button` 還掃得到嗎？

    ⚠️ 這條與 `test_existing_forms_must_not_degrade` **不重複**：那條比對的是
    「是哪幾處」，本條守的是「偵測邏輯本身還活著」。若 `_st_container_names`
    哪天壞掉、`_form_with_nodes` 一律回空集合，那條會因為 `found` 是空集合而紅 ——
    但錯誤訊息會說「form 不見了」，把讀者導向錯誤方向。本條讓真正的原因先現形。
    """
    submits = 0
    for path in UI_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        submits += sum(1 for n in ast.walk(tree)
                       if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                       and n.func.attr == "form_submit_button")
    assert submits >= _FORM_SUBMIT_FLOOR, (
        f"只掃到 {submits} 個 `form_submit_button`，少於下限 {_FORM_SUBMIT_FLOOR}"
        "（量測日 2026-08-31 為 7；2026-08-28 為 6，差額為元件 B 的「套用門檻」）"
        " —— form 偵測可能已經對空氣生效。"
        "\n若這是**有意**移除某個 form，請同步下修 `_FORM_SUBMIT_FLOOR` 並在 commit 說明；"
        "本條刻意不留容忍度,理由見該常數上方註解。")


def test_declared_form_paths_still_exist():
    """`FORM_SITES` / `GATE_FUNCTIONS` 寫死了路徑 —— 檔案改名要出聲。"""
    declared = {k.split("::")[0] for k in
                {s.rsplit("×", 1)[0] for s in FORM_SITES} | GATE_FUNCTIONS}
    missing = sorted(p for p in declared if not (ROOT / p).is_file())
    assert not missing, f"下列路徑已不存在，本檔規則正在對空氣生效：{missing}"
