"""換股顧問搬家漂移鎖 —— 「只在 ④ 資產配置渲染，② 持倉體檢只留指路」。

客戶 2026-09-01 拍板的線框（`docs/wireframes/ia-wireframe.html`，規範性文件）：

- Tab 02「持倉體檢」→「**這裡不放什麼**」：
  「換股建議與再平衡試算 → **04**（那是決策，不是診斷）」
- Tab 04「資產配置」→「**從哪裡搬來**」：「**換股顧問 ─ 自 02 的健診段切出**」

也就是說這不是一個實作偏好，是客戶逐字給的資訊架構決定。本檔把它釘成 CI 紅燈。

## 為什麼要有這個檔（不是儀式）

搬家這件事有**三種**會靜靜壞掉的方式，而且三種都不會讓任何既有測試轉紅：

1. **搬了但沒搬乾淨** —— 兩頁都渲染。畫面上會出現兩個「產生換股建議」按鈕，
   而它們共用同一個 widget key（`switch_advise_btn`）→ Streamlit 會丟
   `DuplicateWidgetID`。本 repo 已經因為同一個原因處理過一次
   （v19.433 把選股池 CRUD 從本區塊移去管理室）。
2. **搬了但沒留指路** —— 使用者原本在 ② 找得到的東西消失了，沒有人告訴他去哪。
   本 repo 前例：一批 UI 重整打壞 6 處使用者可見的指路，由紅隊擋下。
3. **搬了但重抓一次資料** —— ④ 已經有一份持倉健診結果（`_funds_extra`，餵給
   輪動配對／組合績效／效率前緣）。為了搬家再抓一次 = `CLAUDE.md §-1.5.1c v3
   §01-2`「同一個資料來源全站只能有一處取數實作」的正面違規，
   而且會讓同一頁出現兩份可能不一致的持倉資料。

## 判定方向：fail-closed

第 1 條規則不是「檢查 ② 有沒有呼叫」（那種寫法把呼叫搬到第三個檔案就隱形），
而是**掃 `ui/**` ＋ `app.py` 全部，呼叫點集合必須恰好等於預期的那一個**。

## 突變驗證（逐條實跑，結果貼在 PR 描述）

每一條斷言都實際注入過反向改動並確認轉紅；轉不紅的（如果有）在該條 docstring
就地標明它只是形態偵測。**沒有實測過會紅的斷言等於沒守到東西。**
"""
from __future__ import annotations

import ast
import pathlib

import pytest

# 刻意復用既有規則檔的 receiver 剝殼與呼叫正規化（§2.1 SSOT：不另寫第二份）。
from test_render_state_color_separation import (  # noqa: E402
    ROOT,
    UI_SOURCES,
    _callee,
    _st_container_names,
)

#: 唯一允許渲染換股顧問的地方。
EXPECTED_RENDER_SITE = "ui/tab3_portfolio.py::render_portfolio_tab"

#: 被搬走的那個區塊的入口函式名。
RENDER_FN = "render_switch_advisor_section"

#: 換股顧問的實作檔（**刻意不搬檔**，理由見該檔 module docstring）。
SECTION_REL = pathlib.Path("ui") / "helpers" / "fund_grp_health" / "switch_advisor_section.py"

#: ② 持倉體檢的主檔 —— 這裡只准留一行灰色指路。
HEALTH_REL = pathlib.Path("ui") / "tab_fund_grp_health.py"

#: ④ 資產配置的主檔。
PORTFOLIO_REL = pathlib.Path("ui") / "tab3_portfolio.py"


def _tree(rel: pathlib.Path | str) -> ast.AST:
    return ast.parse((ROOT / rel).read_text(encoding="utf-8"))


def _enclosing(tree: ast.AST, node: ast.AST) -> str:
    """node 落在哪個 def 裡（找不到回 `<module>`）。"""
    best = "<module>"
    best_line = -1
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if fn.lineno <= node.lineno <= (fn.end_lineno or fn.lineno):
            if fn.lineno > best_line:          # 取最內層（行號最大的那個 def）
                best, best_line = fn.name, fn.lineno
    return best


def _aliases_of(tree: ast.AST, original: str) -> frozenset[str]:
    """`from x import <original> as <alias>` 綁出來的所有本地名字（含未改名的）。

    **為什麼需要它**：本 repo 到處都是 `import ... as _where_to_find_sw` 這種
    區域別名（`# noqa: PLC0415` 的延後 import 尤其常見）。用字串比對函式名的規則
    在別名下會**靜默失效** —— 那正是 `tests/test_ui_grid_contract.py` 檔頭寫的
    「白名單式規則會被一個 helper 一秒繞過」的同一種病。
    """
    out = {original}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom):
            for a in n.names:
                if a.name == original and a.asname:
                    out.add(a.asname)
    return frozenset(out)


def _calls_to(tree: ast.AST, original: str, scope: ast.AST | None = None):
    """`scope`（預設整個 tree）底下，所有呼叫 `original`（含別名）的 `ast.Call`。"""
    names = _aliases_of(tree, original)
    for n in ast.walk(scope if scope is not None else tree):
        if isinstance(n, ast.Call) and _callee(n) in names:
            yield n


def _func_named(tree: ast.AST, name: str) -> ast.FunctionDef:
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.FunctionDef) and n.name == name), None)
    assert fn is not None, f"找不到函式 {name}() —— 它被改名或刪掉了，本檔的規則會對空氣生效"
    return fn


# ══════════════════════════════════════════════════════════════════
# 規則 1：渲染點恰好一個，而且在 ④
# ══════════════════════════════════════════════════════════════════
def test_switch_advisor_renders_only_from_the_portfolio_tab() -> None:
    """`render_switch_advisor_section(...)` 的呼叫點集合 == {④ 那一個}。

    **fail-closed**：掃 `ui/**` ＋ `app.py` 全部，不是只看 ② 有沒有呼叫 ——
    把呼叫搬到第三個檔案（例如某個 `ui/helpers/**` 的 wrapper）不會讓規則失效。

    突變驗證（實跑）
    ----------------
    - 把 `render_switch_advisor_section(_funds_extra)` 加回
      `ui/tab_fund_grp_health.py::_render_health_advanced` → **轉紅**
      （集合多出 `ui/tab_fund_grp_health.py::_render_health_advanced`）。
    - 把 ④ 的呼叫刪掉 → **轉紅**（集合變空）。
    - **S4（沉默突變，第一版漏掉）**：在 ② 寫
      `from ... import render_switch_advisor_section as _r` 再 `_r(_funds_extra)`
      → 第一版**全綠**（`_callee` 回 `_r`，字串比不到）。已改成解析 import 別名，
      現在**轉紅**。⚠️ 仍擋不住 `getattr(mod, "render_...")()` 這種動態取屬性 ——
      那需要跨程序資料流分析，屬已知射程外，據實寫在這裡而不是假裝守得到。
    """
    found: set[str] = set()
    for path in UI_SOURCES:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # ⚠️ **必須解析別名**：本檔第一版用 `_callee(node) == RENDER_FN` 直接比字串，
        #    突變實測（S4：`import ... as _r` 之後 `_r(_funds_extra)`）→ 本條**全綠**，
        #    只有隔壁那條 import 規則抓到。也就是規則 1 在別名下是瞎的。
        #    別名一旦出現在**沒有 import 規則守著的第三個檔案**，就完全隱形。
        for node in _calls_to(tree, RENDER_FN):
            found.add(f"{path.relative_to(ROOT).as_posix()}::{_enclosing(tree, node)}")
    assert found == {EXPECTED_RENDER_SITE}, (
        "換股顧問的渲染點不是「恰好一個、而且在 ④ 資產配置」。\n"
        f"實測：{sorted(found)}\n"
        f"預期：{[EXPECTED_RENDER_SITE]}\n"
        "客戶拍板線框 Tab 02「這裡不放什麼」：換股建議 → 04（那是決策，不是診斷）。\n"
        "⚠️ 兩頁同時渲染還會撞 widget key `switch_advise_btn` → DuplicateWidgetID。")


def test_health_tab_does_not_even_import_the_section() -> None:
    """② 連 import 都不准留 —— 死 import 會讓下一個人以為它還在這裡渲染。

    與規則 1 **不重複**：規則 1 看的是「有沒有呼叫」，本條看的是「有沒有引用」。
    留一個沒有呼叫的 import 不會讓規則 1 紅，但它是**假的線索**
    （`CLAUDE.md §-2`：沒查證的宣稱比沒有宣稱更危險）。

    突變驗證（實跑）：在 ② 加回
    `from ui.helpers.fund_grp_health.switch_advisor_section import render_switch_advisor_section`
    （不呼叫）→ **轉紅**，而規則 1 仍綠 —— 證明兩條各守各的。
    """
    src = (ROOT / HEALTH_REL).read_text(encoding="utf-8")
    tree = ast.parse(src)
    bad = [
        f"line {n.lineno}: {ast.unparse(n)}"
        for n in ast.walk(tree)
        if isinstance(n, (ast.Import, ast.ImportFrom))
        and "switch_advisor_section" in ast.unparse(n)
    ]
    assert not bad, (
        f"{HEALTH_REL} 還留著換股顧問的 import（沒有呼叫，但會誤導讀者）：\n  "
        + "\n  ".join(bad))


# ══════════════════════════════════════════════════════════════════
# 規則 2：② 必須留下指路，而且要走 SSOT、要是灰的
# ══════════════════════════════════════════════════════════════════
def test_health_tab_points_users_to_the_new_home_via_ssot() -> None:
    """② 必須有一行指路，且分頁／分區名走 `story_nav.where_to_find('switch')`。

    **為什麼不准手抄字串**：本 repo 的指路已經指錯三次（見
    `ui/helpers/story_nav.py` 模組 docstring）。手抄「④ 資產配置」在下一次改名時
    **不會報錯**，只會安靜地叫使用者去找一個不存在的地方。

    突變驗證（實跑）
    ----------------
    - 把那一行 `st.caption(...)` 整段刪掉 → **轉紅**（找不到 `where_to_find('switch')`）。
    - 把 `_where_to_find_sw('switch')` 換成寫死的 `"④ 資產配置 → 🎯 換股顧問"`
      → **轉紅**（同上）。
    """
    tree = _tree(HEALTH_REL)
    calls = [n for n in _calls_to(tree, "where_to_find")
             if n.args and isinstance(n.args[0], ast.Constant)
             and n.args[0].value == "switch"]
    assert calls, (
        f"{HEALTH_REL} 找不到 `where_to_find('switch')` —— 換股顧問被搬走了，"
        "② 卻沒有告訴使用者它去了哪裡。\n"
        "⚠️ 手抄「④ 資產配置」也算沒有：那正是本 repo 已經指錯三次的寫法，"
        "請走 `ui.helpers.story_nav.where_to_find` SSOT。")


def test_the_pointer_is_grey_not_an_error() -> None:
    """指路是**灰色 caption**，不是 `st.error` / `st.warning` / `st.info`。

    三態顏色分離（客戶鐵則 03）：「功能搬到別頁」既不是系統故障、也不是業務警示，
    它是一句說明。把它畫成紅／橘會稀釋真正的紅燈
    （`ui/helpers/render_state.py` 整篇在講這件事）。
    處置與 `ui/tab3_portfolio.py` WP-G 那一行「健診請看 ②」的指路一致。

    突變驗證（實跑）：把 `st.caption(...)` 改成 `st.warning(...)` → **轉紅**。
    """
    src = (ROOT / HEALTH_REL).read_text(encoding="utf-8")
    tree = ast.parse(src)
    containers = _st_container_names(tree)
    bad: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        # 找「引數子樹裡含 where_to_find('switch')」的那個渲染呼叫
        _wtf = set(_aliases_of(tree, "where_to_find"))
        if not any(isinstance(sub, ast.Call) and _callee(sub) in _wtf
                   and sub.args and isinstance(sub.args[0], ast.Constant)
                   and sub.args[0].value == "switch"
                   for a in node.args for sub in ast.walk(a)):
            continue
        name = _callee(node, containers)
        if name in {"st.error", "st.warning", "st.info", "st.exception"}:
            bad.append(f"line {node.lineno}: {name}(...)")
    assert not bad, (
        "換股顧問的指路被畫成錯誤／警示色 —— 功能搬家不是故障（鐵則 03 三態分離）：\n  "
        + "\n  ".join(bad))


# ══════════════════════════════════════════════════════════════════
# 規則 3：④ 重用既有資料，不得為了搬家再抓一次
# ══════════════════════════════════════════════════════════════════
def test_portfolio_tab_feeds_it_the_existing_funds_extra() -> None:
    """④ 傳給換股顧問的必須是 `_switch_funds`，而 `_switch_funds` 只能來自兩個地方：
    空 list（尚未載入）或既有的 `_funds_extra`（持倉健診本來就算好的那一份）。

    **這一條守的是「不得重抓」**（`CLAUDE.md §-1.5.1c v3 §01-2`：同一個資料來源
    全站只能有一處取數實作）。為了搬家在 ④ 再跑一次 `process_one_fund` /
    `_build_fund_dict`，會讓同一頁出現兩份可能不一致的持倉資料。

    突變驗證（實跑）
    ----------------
    - 把 `_switch_funds = _funds_extra` 改成
      `_switch_funds = [_build_fund_dict(...) for ...]` → **轉紅**
      （右手邊不是 `_funds_extra` 也不是空 list）。
    - 把 `render_switch_advisor_section(_switch_funds)` 改成
      `render_switch_advisor_section(st.session_state.portfolio_funds)` → **轉紅**
      （引數不是 `_switch_funds`；順帶一提那樣傳的 dict 形狀也不對）。
    """
    tree = _tree(PORTFOLIO_REL)
    fn = _func_named(tree, "render_portfolio_tab")

    # (a) 引數必須是裸名 `_switch_funds`
    call = next((n for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and _callee(n) == RENDER_FN), None)
    assert call is not None, "④ 沒有呼叫 render_switch_advisor_section()"
    assert len(call.args) == 1 and isinstance(call.args[0], ast.Name) \
        and call.args[0].id == "_switch_funds", (
        f"傳進換股顧問的不是 `_switch_funds`，而是 "
        f"`{ast.unparse(call.args[0]) if call.args else '(無引數)'}`。")

    # (b) `_switch_funds` 的每一次指派，右手邊只准是 `[]` 或 `_funds_extra`
    rhs: list[str] = []
    for node in ast.walk(fn):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets = [node.target]
        if any(isinstance(t, ast.Name) and t.id == "_switch_funds" for t in targets):
            rhs.append(ast.unparse(node.value))
    assert rhs, "`_switch_funds` 從來沒有被指派過"
    bad = [r for r in rhs if r not in {"[]", "_funds_extra"}]
    assert not bad, (
        "`_switch_funds` 被指派成 `[]` / `_funds_extra` 以外的東西 —— "
        "換股顧問只能吃 ④ 本來就算好的那一份持倉健診結果，**不得為了搬家再抓一次**"
        "（同一個資料來源全站只能有一處取數實作）：\n  " + "\n  ".join(bad))


def test_the_handoff_sits_right_next_to_the_data_it_hands_off() -> None:
    """`_switch_funds = _funds_extra` 必須**緊接在** `_funds_extra = [...]` 之後。

    **這一條是沉默突變抓出來的**（本批自己回打，不是稽核抓的）：
    把 handoff 塞進一個不可達分支（`if False:`）→ 換股顧問**永遠**顯示空狀態，
    即使使用者明明有持倉 —— 而本檔前一版的每一條斷言**全綠**
    （右手邊仍然是 `_funds_extra`、引數仍然是 `_switch_funds`、順序也沒動）。
    「畫面永遠是空的」正是本 repo §1 最在意的那種失效：它看起來不像壞掉。

    位置相鄰是可以靜態驗證的最強形式：只要 handoff 被搬離那一行的正下方
    （搬進 if / 搬到別的函式 / 搬到另一個 `with`），本條就紅。

    突變驗證（實跑）
    ----------------
    - `_switch_funds = _funds_extra` → `if False: _switch_funds = _funds_extra` → **轉紅**。
    - 把 handoff 整行刪掉 → **轉紅**（下一句不是它）。
    """
    tree = _tree(PORTFOLIO_REL)
    fn = _func_named(tree, "render_portfolio_tab")
    found = False
    for node in ast.walk(fn):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for i, stmt in enumerate(body[:-1]):
            if not (isinstance(stmt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "_funds_extra"
                            for t in stmt.targets)):
                continue
            nxt = body[i + 1]
            if (isinstance(nxt, ast.Assign)
                    and any(isinstance(t, ast.Name) and t.id == "_switch_funds"
                            for t in nxt.targets)
                    and isinstance(nxt.value, ast.Name)
                    and nxt.value.id == "_funds_extra"):
                found = True
    assert found, (
        "`_switch_funds = _funds_extra` 不在 `_funds_extra = [...]` 的正下方 —— "
        "handoff 一旦被搬進條件分支或別的地方，換股顧問會**永遠顯示空狀態**，"
        "而其他每一條斷言都還是綠的（實測過）。")


def test_the_render_call_is_not_gated_on_having_holdings() -> None:
    """`render_switch_advisor_section(...)` **不得**被 `if _switch_funds:` 之類的
    真值判斷包住。

    **這一條也是沉默突變抓出來的。** 把呼叫包成 `if _switch_funds: render(...)`
    看起來像「沒資料就不要畫」的好意，實際上是把**鐵則 04 的空狀態三要素**整個關掉：
    使用者一檔都沒載入時，④ 會**什麼都不顯示**，而他剛從 ② 被指路過來。
    鐵則 04 說的是「不畫**空表格外框**」，不是「什麼都不要畫」——
    空狀態三要素（標題／缺什麼／去哪補）正是它要求的替代品。

    突變驗證（實跑）：加上 `if _switch_funds:` → **轉紅**（第一版全綠）。
    """
    tree = _tree(PORTFOLIO_REL)
    fn = _func_named(tree, "render_portfolio_tab")
    names = _aliases_of(tree, RENDER_FN)
    bad: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.If):
            continue
        if "_switch_funds" not in {n.id for n in ast.walk(node.test)
                                   if isinstance(n, ast.Name)}:
            continue
        if any(isinstance(c, ast.Call) and _callee(c) in names
               for c in ast.walk(node)):
            bad.append(f"line {node.lineno}: if {ast.unparse(node.test)}: … render(…)")
    assert not bad, (
        "換股顧問的渲染被「有沒有持倉」的判斷擋住了 —— 沒持倉時整區會消失，"
        "而使用者剛從 ② 被指路過來。鐵則 04 要的是**空狀態三要素**，"
        "不是什麼都不畫：\n  " + "\n  ".join(bad))


def test_switch_block_is_entered_last_so_no_existing_order_moves() -> None:
    """④ 的 `with _sec_switch:` 必須是**最後**一個進入的區塊。

    理由（本檔最容易被「好意」破壞的一條）：`ui/tab3_portfolio.py` 開頭那段長註解
    列出**至少四處**同一次 run 內的 session_state 先寫後讀耦合
    （`portfolio_core_pct` / `policy_sheet_id` / `gsheet_tokens` / `_schema_ver`，
    且自陳非窮舉）。把新區塊插到中間 = 讓既有數字翻面而畫面看起來一樣。
    排在最後就結構上不可能改到任何既有的先後關係。

    ⚠️ `tests/test_wpd_portfolio_layout.py::test_execution_order_...` 已經用
    **整條 tuple 精確比對**守住同一件事；本條**不是複製**，它守的是
    「為什麼是最後一個」這個**理由**，而且在 tuple 被整體重寫時仍然成立。

    突變驗證（實跑）：把 `with _sec_switch:` 整段移到 `with _sec_ai:` 之前
    → **轉紅**（同時 WP-D 那條也紅 —— 兩條都在看，這是刻意的縱深）。
    """
    tree = _tree(PORTFOLIO_REL)
    fn = _func_named(tree, "render_portfolio_tab")
    order = [
        item.context_expr.id
        for stmt in fn.body if isinstance(stmt, ast.With)
        for item in stmt.items if isinstance(item.context_expr, ast.Name)
    ]
    assert order and order[-1] == "_sec_switch", (
        "`with _sec_switch:` 不是最後一個進入的區塊 —— 它一旦插到中間，"
        "就可能改到既有的 session_state 先寫後讀關係（畫面一樣、數字會變）。\n"
        f"實測 `with` 進入順序：{order}")


# ══════════════════════════════════════════════════════════════════
# 規則 4：這個區塊自己不製造新的耦合 / 新的巢狀分頁
# ══════════════════════════════════════════════════════════════════
#: 換股顧問**直接**寫入的 session_state key（實測：全 repo 只有它自己讀寫）。
OWN_SESSION_KEYS = frozenset({"_perf_snapshot_done", "_switch_advise_done"})


def test_switch_section_writes_only_its_own_session_keys() -> None:
    """換股顧問直接寫的 session_state key ⊆ 它自己的兩把。

    這是「排在最後不會影響任何人」這個主張的**可執行版本**：只要它開始寫別人
    也在讀的 key，執行順序就重新變成一件要想的事，本條會當場紅。

    ⚠️ **本條只看「直接寫入」，不做跨函式追蹤 —— 這是已知的射程限制，不是保證。**
    已知的**間接**寫入有一處，據實寫在這裡而不是藏起來：
    `_pool_oauth_client()` → `ui.helpers.io.oauth_state._get_oauth_client()` 內部會
    `st.session_state["gsheet_tokens"] = toks`（token 到期前自動 refresh）。
    本組的判讀是它不構成順序耦合 —— 每個 `gsheet_tokens` 的消費者
    （`policy_admin_section` 等）都自己呼叫 `_get_oauth_client()` 做同一次 refresh，
    沒有人依賴「別人先幫我 refresh 過」；而且該路徑只在使用者按下
    「產生換股建議」之後才會走到。**這個判讀是本組單組實測，未經第二組驗證**
    （`CLAUDE.md §-2` 規則 6），不得當成已查證的事實引用。

    突變驗證（實跑）：在 `render_switch_advisor_section` 內加一行
    `st.session_state["portfolio_core_pct"] = 70` → **轉紅**。
    """
    tree = _tree(SECTION_REL)
    written: set[str] = set()
    for node in ast.walk(tree):
        targets = node.targets if isinstance(node, ast.Assign) else []
        for t in targets:
            if (isinstance(t, ast.Subscript)
                    and isinstance(t.value, ast.Attribute)
                    and t.value.attr == "session_state"
                    and isinstance(t.slice, ast.Constant)):
                written.add(t.slice.value)
    assert written <= OWN_SESSION_KEYS, (
        "換股顧問開始寫它自己以外的 session_state key —— "
        "「排在最後所以不影響任何人」這個前提失效了，執行順序要重新盤過：\n  "
        f"實測寫入 {sorted(written)}，允許 {sorted(OWN_SESSION_KEYS)}")


def test_nobody_else_touches_those_two_keys() -> None:
    """反向：全 repo（production）只有換股顧問自己碰那兩把 key。

    上一條證明「它只寫自己的」，本條證明「自己的那兩把沒有別人在讀」——
    兩條合起來才等於「它不參與任何跨區塊耦合」。**少任何一條都只是半個宣稱。**

    突變驗證（實跑）：在 `ui/tab3_portfolio.py` 加一行
    `if st.session_state.get("_switch_advise_done"): pass` → **轉紅**。
    """
    hits: list[str] = []
    for path in sorted(ROOT.rglob("*.py")):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("tests/", ".git/")) or rel == SECTION_REL.as_posix():
            continue
        src = path.read_text(encoding="utf-8")
        for key in OWN_SESSION_KEYS:
            for i, line in enumerate(src.splitlines(), 1):
                if key in line and not line.lstrip().startswith("#"):
                    hits.append(f"{rel}:{i} {line.strip()[:90]}")
    assert not hits, (
        "換股顧問的私有 session key 出現在別的 production 檔案裡 —— "
        "它不再是「只讀不寫、放最後也不影響任何人」：\n  " + "\n  ".join(hits))


def test_the_moved_block_opens_no_nested_tabs() -> None:
    """被搬進 ④ 的這個區塊自己**不得**開一層 `st.tabs`（客戶鐵則：分頁只有一層）。

    ⚠️ **射程要講清楚，不要讀成全站宣稱**：本條只掃**換股顧問這一個檔**。
    ④ 底下**另有**一處既有的巢狀 `st.tabs`（`ui/tab3_t7_ledger.py::render_t7_section`
    的 A/B/C 再平衡子分頁），那是**本批之前就存在的**、且已就地登記在
    `ui/tab_settings_diag.py` 的 2026-09-01 更正註記裡。
    **本批沒有讓它消失，也沒有讓它變多。**

    偵測方式對 alias 不敏感（`import streamlit as _s` 之後的 `_s.tabs` 一樣抓得到）。

    突變驗證（實跑）：在 `render_switch_advisor_section` 內加
    `_t1, _t2 = st.tabs(["建議", "選股池"])` → **轉紅**。
    """
    tree = _tree(SECTION_REL)
    containers = _st_container_names(tree)
    bad = [f"line {n.lineno}: {ast.unparse(n.func)}(...)"
           for n in ast.walk(tree)
           if isinstance(n, ast.Call) and _callee(n, containers) == "st.tabs"]
    assert not bad, (
        f"{SECTION_REL} 開了巢狀 `st.tabs` —— 客戶鐵則：分頁只有一層，"
        "頁內分區請用「區塊 + 標題 + 錨點」：\n  " + "\n  ".join(bad))


# ══════════════════════════════════════════════════════════════════
# 規則 5：搬過去之後的呈現要符合客戶鐵則（03 三態 / 04 空狀態 / 錨點）
# ══════════════════════════════════════════════════════════════════
def test_empty_holdings_uses_the_three_element_empty_state() -> None:
    """一檔持倉都沒有時，走**空狀態三要素**（鐵則 04），不是藍色 `st.info`。

    搬家之前這裡是 `st.info("尚未載入持倉基金 → 先在上方載入基金…")`，
    有**兩個**問題，兩個都是搬家造成的：
    1. **顏色**：藍色 info 在本 repo 沒有被指派任何語意（三態只有灰／莓紅／紅）；
       「還沒載入」是**前提不足** → 灰。
    2. **文案**：「先在**上方**載入基金」在 ② 是對的（貼碼框就在上面），
       搬到 ④ 之後「上方」指的是別的東西 —— **指路一旦搬家就會說謊**。

    突變驗證（實跑）：把 `empty_state(...)` 改回 `st.info(...)` → **轉紅**。
    """
    tree = _tree(SECTION_REL)
    fn = _func_named(tree, RENDER_FN)
    empty_calls = [n for n in ast.walk(fn)
                   if isinstance(n, ast.Call) and _callee(n) == "empty_state"]
    assert empty_calls, (
        "換股顧問在「沒有持倉」時沒有走 `ui.helpers.ia.empty_state` 的三要素 —— "
        "鐵則 04 要求標題／缺什麼／去哪補三項齊全，不得只丟一句 st.info。")
    # 三要素：title(位置) + missing(位置) + where(關鍵字)
    call = empty_calls[0]
    kw = {k.arg for k in call.keywords}
    assert len(call.args) >= 2 and "where" in kw, (
        "`empty_state(...)` 少了三要素之一（標題／缺什麼／**去哪補**）。"
        "「去哪補」是最容易被省掉、也最有價值的一項 —— 沒有它，"
        f"空狀態只是把『消失』換成『灰色的消失』。實測 args={len(call.args)}, kwargs={sorted(kw)}")


def test_empty_state_where_goes_through_the_section_label_ssot() -> None:
    """「去哪補」指到的區塊名走 `story_nav.section_label(...)`，不得手抄。

    突變驗證（實跑）：把 `where=f"本頁的「{_sl('pf_add')}」…"` 改成
    `where="本頁的「➕ 加入與管理基金」…"` → **轉紅**。
    """
    tree = _tree(SECTION_REL)
    fn = _func_named(tree, RENDER_FN)
    call = next(n for n in ast.walk(fn)
                if isinstance(n, ast.Call) and _callee(n) == "empty_state")
    where = next((k.value for k in call.keywords if k.arg == "where"), None)
    assert where is not None
    _sl_names = _aliases_of(tree, "section_label")
    uses_ssot = any(isinstance(sub, ast.Call) and _callee(sub) in _sl_names
                    for sub in ast.walk(where))
    assert uses_ssot, (
        "空狀態的「去哪補」手抄了區塊名 —— 請走 `story_nav.section_label()` SSOT，"
        f"實測：{ast.unparse(where)}")


def test_section_heading_uses_the_ssot_label_and_a_stable_anchor() -> None:
    """區塊標題吃 `section_label('switch')`，且帶顯式 `anchor=`。

    ④ 不得再開一層 `st.tabs` → 分區只能靠「區塊 + 標題 + 錨點」。
    Streamlit 對中文標題自動產生的 anchor 不可靠，所以顯式指定
    （沿用 `ui/tab_settings_diag.py` 的 `ANCHOR_*` 慣例）。

    突變驗證（實跑）
    ----------------
    - 把 `st.subheader(..., anchor=ANCHOR_SWITCH)` 改回
      `st.markdown("### 🎯 換股顧問…")` → **轉紅**（找不到帶 anchor 的 subheader）。
    - 把標題裡的 `_section_label('switch')` 換成寫死字串 → **轉紅**。
    """
    from ui.helpers.fund_grp_health.switch_advisor_section import ANCHOR_SWITCH

    assert ANCHOR_SWITCH, "ANCHOR_SWITCH 不得是空字串（空 anchor = 沒有錨點）"

    tree = _tree(SECTION_REL)
    fn = _func_named(tree, RENDER_FN)
    subs = [n for n in ast.walk(fn)
            if isinstance(n, ast.Call) and _callee(n) == "st.subheader"]
    assert subs, f"{SECTION_REL}::{RENDER_FN} 沒有 `st.subheader(...)` 標題"
    head = subs[0]
    anchors = [k for k in head.keywords if k.arg == "anchor"]
    assert anchors, "區塊標題沒有帶 `anchor=` —— 沒有錨點就沒辦法從別頁指到這一區"
    assert isinstance(anchors[0].value, ast.Name) and anchors[0].value.id == "ANCHOR_SWITCH", (
        f"`anchor=` 不是走 `ANCHOR_SWITCH` 常數：{ast.unparse(anchors[0].value)}")
    assert head.args, "st.subheader 沒有標題引數"
    _sl_names = _aliases_of(tree, "section_label")
    uses_ssot = any(isinstance(sub, ast.Call) and _callee(sub) in _sl_names
                    for sub in ast.walk(head.args[0]))
    assert uses_ssot, (
        "區塊標題手抄了分區名 —— 它必須與 ② 那一行指路是**同一個字串**，"
        f"請走 `story_nav.section_label('switch')`。實測：{ast.unparse(head.args[0])}")


# ══════════════════════════════════════════════════════════════════
# 規則 6：分區 SSOT 本身指對地方
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("key,expect_tab", [("switch", "portfolio"), ("pf_add", "portfolio")])
def test_new_section_keys_live_under_the_portfolio_tab(key: str, expect_tab: str) -> None:
    """`where_to_find('switch' / 'pf_add')` 必須解析到 ④ 資產配置。

    比對的是 `tab_label(expect_tab)` **求值後的字串**，不是寫死「📊 資產配置」——
    寫死等於在測試裡再抄第四份分頁名（本 repo 已經因為手抄指路錯三次）。

    突變驗證（實跑）：把 `_SECTION_TO_TAB['switch']` 改成 `'health'` → **轉紅**。
    """
    from ui.helpers.story_nav import section_label, tab_label, where_to_find

    got = where_to_find(key)
    assert tab_label(expect_tab) in got, (
        f"where_to_find({key!r}) = {got!r}，沒有指到 {tab_label(expect_tab)!r}")
    assert section_label(key) in got, (
        f"where_to_find({key!r}) 沒有帶上分區名 {section_label(key)!r}")
