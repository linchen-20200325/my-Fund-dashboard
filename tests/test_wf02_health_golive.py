"""② 切換上線的三道靜態守衛 —— **接線** ＋ **寫入面** ＋ **掉了什麼**。

本檔為什麼獨立存在（不併進 `tests/test_wf02_health_skeleton.py`）
------------------------------------------------------------------
那一份**替換 `st` 的渲染 API 錄呼叫序列**，需要 streamlit（以及被它拉進來的
pandas / plotly）；本檔**純 AST，不 import 被測模組**。分開的好處很具體：
渲染側的依賴哪天在 CI 裝不起來，那一份會整檔 error，而本檔照跑 ——
**接線、寫入面、功能有沒有掉，這三件事不該跟 runtime 綁在一起。**
形狀逐字比照 ⑤ 切換時的 `tests/test_wf05_settings_golive.py`。

守什麼
------
1. :func:`test_app_mounts_the_new_health_view` —— `app.py` 的 ② 真的掛新 View。
2. :func:`test_the_switch_adds_no_write_surface` —— 切換**沒有**把任何新的寫入槽
   拉進射程（新頁閉包的寫入面 ⊆ 舊 ②）。
3. :func:`test_the_page_itself_writes_nothing` —— 被測檔**自己**零寫入 primitive。
4. :func:`test_the_scanner_can_actually_see_a_write` —— **正對照**：掃描器不是恆綠。
5. :func:`test_every_dropped_renderer_has_a_named_disposition` —— ⭐ **本檔的重點**：
   切換之後**到不了**的每一個渲染函式，都必須在 :data:`DROPPED_WITH_REASON` 裡
   有一筆具名去處。**沒登記的東西不准無聲消失。**
6. :func:`test_the_disposition_table_never_lists_something_still_reachable` ——
   反向：表上不准出現「其實還在」的項目（一張會說謊的表比沒有表更糟）。
7. :func:`test_the_old_page_is_still_the_fallback` —— 舊 ② 還在磁碟上。
8. :func:`test_the_reattached_blocks_are_reachable_from_page_two` —— ⭐ **2026-09-07 新增**：
   登記為「已接回 ②」的那幾塊，必須真的從 ② 的入口**到得了**。
   （2026-09-07 事故的根因是「已搬 ③」這個標籤含混、而**沒有機器規則在驗它** ——
   **這一條才是擋住下一次的那個**，接回去只修今天這幾支。）
9. :func:`test_the_blocked_reattach_cannot_disappear_quietly` —— ⭐ **2026-09-07 新增**：
   同一批裡**接不回來**的那一支，必須具名掛在 :data:`DROPPED_WITH_REASON` 上，
   不准無聲消失第二次。

⛔ **不守什麼（照實列，不要讀成「功能未丟失已經證完了」）**
------------------------------------------------------------
* 本檔是**靜態**的。第 5／6 條回答「哪些渲染函式**呼叫圖上**到不了」，
  **不回答**「使用者實際少看到什麼」—— 同一個畫面可以由不同函式畫出來。
* :func:`_reach` 的射程外：`getattr` / 字典派發 / 字串組出來的動態呼叫。
  **本檔不宣稱窮舉。**
* :func:`_sinks` 是**名字比對**（`ast.walk`，不看分支、不看可達性、不看引數）——
  它會**誤報**（`CLAUDE.md §8.3.P` 的 `P-SINKGRAIN-1` 就是一個實證）。
  本檔用它做的是**差集**，兩邊同一把尺，偽陽性在相減時會抵銷。
"""
from __future__ import annotations

import ast
import pathlib
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 舊 ② 的入口（回退路徑，仍在磁碟上）。
OLD_ENTRY = ("ui.tab_fund_grp_health", "render_fund_grp_health_tab")
#: 新 ② 的入口（2026-09-07 起掛在 `app.py`）。
NEW_ENTRY = ("ui.views.page_02_health", "render_holdings_health")
NEW_SRC = ROOT / "ui" / "views" / "page_02_health.py"
OLD_SRC = ROOT / "ui" / "tab_fund_grp_health.py"

_PKG_ROOTS = ("ui", "services", "repositories", "shared", "infra")

#: 逐字取自 `tests/test_wf02_health_no_writes.py::_WRITE_PRIMITIVES`。
#: ⚠️ **刻意不 import 那一份** —— 它在模組層 import streamlit，會把本檔的
#:    「純 AST、不依賴 runtime」這個賣點整個抵銷掉。**同一把尺、兩份拷貝**是
#:    有代價的，代價寫在這裡：那邊加了新 primitive，這邊要跟著加。
_WRITE_PRIMITIVES = frozenset({
    "append_row", "append_rows", "append_point", "append_points",
    "insert_row", "insert_rows", "insert_cols", "insert_note", "insert_notes",
    "update_cell", "update_acell", "update_cells", "update_note", "update_notes",
    "update_title", "update_index", "batch_update", "batch_clear",
    "delete_rows", "delete_columns", "delete_dimension",
    "add_worksheet", "del_worksheet", "del_worksheet_by_id", "add_rows", "add_cols",
    "values_append", "values_update", "values_clear",
    "values_batch_update", "values_batch_clear", "import_csv",
    "write_text", "write_bytes", "unlink", "mkdir", "makedirs",
    "rmdir", "removedirs", "rmtree", "touch",
    "to_parquet", "to_csv", "to_json", "to_excel", "to_pickle", "to_feather", "to_sql",
})


# ══════════════════════════════════════════════════════════════════
# 0｜模組表與 import 綁定
# ══════════════════════════════════════════════════════════════════
def _module_path(mod: str) -> "pathlib.Path | None":
    _p = ROOT / mod.replace(".", "/")
    for _c in (_p.with_suffix(".py"), _p / "__init__.py"):
        if _c.exists():
            return _c
    return None


def _absolutise(mod: str, path: pathlib.Path, node: ast.ImportFrom) -> str:
    """把 `from . import x` / `from ..y import z` 解析成絕對模組名。"""
    if node.level == 0:
        return node.module or ""
    _pkg = mod if path.name == "__init__.py" else mod.rpartition(".")[0]
    _bits = _pkg.split(".") if _pkg else []
    _drop = node.level - 1
    if _drop:
        _bits = _bits[:-_drop] if _drop <= len(_bits) else []
    if node.module:
        _bits = _bits + node.module.split(".")
    return ".".join(_bits)


def _closure(entry: str) -> "dict[str, pathlib.Path]":
    """`entry` 的**靜態 import** 轉移閉包（只含本 repo 的套件）。"""
    _seen: dict[str, pathlib.Path] = {}
    _stack = [entry]
    while _stack:
        _m = _stack.pop()
        if _m in _seen:
            continue
        _p = _module_path(_m)
        if _p is None:
            continue
        _seen[_m] = _p
        try:
            _tree = ast.parse(_p.read_text(encoding="utf-8"))
        except SyntaxError:                                   # pragma: no cover
            continue
        for _n in ast.walk(_tree):
            if isinstance(_n, ast.ImportFrom):
                _base = _absolutise(_m, _p, _n)
                if _base and _base.split(".")[0] in _PKG_ROOTS:
                    _stack.append(_base)
                    _stack.extend(f"{_base}.{_a.name}" for _a in _n.names)
            elif isinstance(_n, ast.Import):
                _stack.extend(_a.name for _a in _n.names
                              if _a.name.split(".")[0] in _PKG_ROOTS)
    return _seen


def _functions(node: ast.AST, prefix: str = ""):
    """`node` 底下的函式，回傳 `(qualname, node)`；**含 class 方法與巢狀函式**。"""
    for _ch in ast.iter_child_nodes(node):
        if isinstance(_ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield f"{prefix}{_ch.name}", _ch
            yield from _functions(_ch, f"{prefix}{_ch.name}.")
        elif isinstance(_ch, ast.ClassDef):
            yield from _functions(_ch, f"{prefix}{_ch.name}.")


def _write_sinks_in(tree: ast.AST) -> "set[tuple[str, str]]":
    return {(_qual, _n.func.attr)
            for _qual, _fn in _functions(tree)
            for _n in ast.walk(_fn)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in _WRITE_PRIMITIVES}


def _sinks(entry: str) -> "set[tuple[str, str, str]]":
    _out: set[tuple[str, str, str]] = set()
    for _mod, _path in _closure(entry).items():
        try:
            _tree = ast.parse(_path.read_text(encoding="utf-8"))
        except SyntaxError:                                   # pragma: no cover
            continue
        for _qual, _prim in _write_sinks_in(_tree):
            _out.add((_mod, _qual, _prim))
    return _out


# ══════════════════════════════════════════════════════════════════
# 1｜呼叫圖遞移閉包（「呼叫 ＋ 裸參照」都算邊）
# ══════════════════════════════════════════════════════════════════
#: ⚠️ **只跟 `ast.Call` 會嚴重低估**：本 repo 的委派慣例是
#:    `safe_section("標籤", _render_x)` —— 那是**裸參照**，不是呼叫節點。
#:    #805 已經在零寫入守衛上吃過同一個教訓（「靜態層從只看呼叫擴為呼叫 ＋ 裸參照」）。
def _index():
    """一次建好：模組樹、頂層定義、import 綁定、模組別名、`import *` shim。"""
    _mods: dict[str, pathlib.Path] = {}
    for _p in ROOT.rglob("*.py"):
        if any(_x in _p.parts for x in () for _x in ()):      # pragma: no cover
            continue
        if any(_x in _p.parts for _x in (".git", "__pycache__", "tests", "scripts")):
            continue
        _rel = list(_p.relative_to(ROOT).parts)
        _m = ".".join(_rel[:-1]) if _rel[-1] == "__init__.py" \
            else ".".join(_rel[:-1] + [_rel[-1][:-3]])
        if _m:
            _mods[_m] = _p
    _trees, _defs, _nodes = {}, {}, {}
    _bind: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    _alias: dict[str, dict[str, str]] = defaultdict(dict)
    _star: dict[str, list[str]] = defaultdict(list)
    for _m, _p in _mods.items():
        try:
            _t = ast.parse(_p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError):             # pragma: no cover
            continue
        _trees[_m] = _t
        _names = set()
        for _n in _t.body:
            if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                _names.add(_n.name)
                _nodes[(_m, _n.name)] = _n
        _defs[_m] = _names
        for _n in ast.walk(_t):
            if isinstance(_n, ast.ImportFrom):
                if _n.level or not _n.module:
                    continue
                for _a in _n.names:
                    if _a.name == "*":
                        _star[_m].append(_n.module)
                        continue
                    _bind[_m][_a.asname or _a.name] = (_n.module, _a.name)
                    if f"{_n.module}.{_a.name}" in _mods:
                        _alias[_m][_a.asname or _a.name] = f"{_n.module}.{_a.name}"
            elif isinstance(_n, ast.Import):
                for _a in _n.names:
                    _alias[_m][_a.asname or _a.name.split(".")[0]] = (
                        _a.name if _a.asname else _a.name.split(".")[0])
                    _alias[_m][_a.name] = _a.name
    return _mods, _defs, _nodes, _bind, _alias, _star


_MODS, _DEFS, _NODES, _BIND, _ALIAS, _STAR = _index()


def _resolve(mod: str, name: str, depth: int = 0) -> "tuple[str, str] | None":
    if depth > 10:
        return None
    if name in _DEFS.get(mod, ()):
        return (mod, name)
    _b = _BIND.get(mod, {}).get(name)
    if not _b:
        for _sm in _STAR.get(mod, ()):        # 追 `from X import *` shim
            if _sm in _MODS:
                _r = _resolve(_sm, name, depth + 1)
                if _r:
                    return _r
        return None
    _src, _orig = _b
    if _src not in _MODS:
        return None                            # 外部套件
    if _orig in _DEFS.get(_src, ()):
        return (_src, _orig)
    return _resolve(_src, _orig, depth + 1)    # `__init__.py` 的 re-export


def _reach(entry: "tuple[str, str]") -> "set[tuple[str, str]]":
    """從 `entry` 出發的遞移可達集合（呼叫 ＋ 裸參照）。"""
    _start = _resolve(*entry)
    assert _start, f"入口解析不到：{entry[0]}::{entry[1]}"
    _seen: set[tuple[str, str]] = set()
    _stack = [_start]
    while _stack:
        _cur = _stack.pop()
        if _cur in _seen:
            continue
        _seen.add(_cur)
        _node = _NODES.get(_cur)
        if _node is None:
            continue
        _cm = _cur[0]
        for _n in ast.walk(_node):
            _t = None
            if isinstance(_n, ast.Name) and isinstance(_n.ctx, ast.Load):
                _t = _resolve(_cm, _n.id)
            elif (isinstance(_n, ast.Attribute) and isinstance(_n.ctx, ast.Load)
                  and isinstance(_n.value, ast.Name)):
                _am = _ALIAS.get(_cm, {}).get(_n.value.id)
                if _am and _am in _MODS and _n.attr in _DEFS.get(_am, ()):
                    _t = (_am, _n.attr)
                else:
                    _r = _resolve(_cm, _n.value.id)
                    if _r and f"{_r[0]}.{_r[1]}" in _MODS \
                            and _n.attr in _DEFS.get(f"{_r[0]}.{_r[1]}", ()):
                        _t = (f"{_r[0]}.{_r[1]}", _n.attr)
            if _t:
                _stack.append(_t)
    return _seen


def _renderers(nodes: "set[tuple[str, str]]") -> "set[str]":
    """會畫畫面的那些（名字含 `render`）—— 本檔只對這一類要求去處。"""
    return {f"{_m}::{_n}" for _m, _n in nodes if "render" in _n.lower()}


# ══════════════════════════════════════════════════════════════════
# 2｜⭐ 掉了什麼 —— 每一筆都要有具名去處
# ══════════════════════════════════════════════════════════════════
#: 允許的處置。**沒有「還沒排到」這一種** —— 那正是本表要消滅的東西。
_DISPOSITIONS = frozenset({
    "已搬 ③",          # 核准線框判給 ③ 基金研究
    "刻意不接",        # 具名理由（零寫入裁決／黑名單／新頁自己重畫）
    "待客戶裁決",      # 送出去了、還沒回來
    "橋接容器",        # 它本身不畫內容，只是舊頁的容器／橋
    "未登記缺口",      # ⚠️ 本批新查出、尚無去處 —— 見 PR 描述
})

#: 切換之後**到不了**的渲染函式，逐一具名去處。
#:
#: ⚠️ **這張表不是「可以一直缺下去的清單」** —— `未登記缺口` 那幾筆是本批
#:    用 AST 遞移閉包**新查出來的**，在此之前**沒有任何地方記載它們**
#:    （`ui/views/page_02_health.py` 的四個常數都沒有收它們）。
#:    登記在這裡是為了讓它們**不能無聲消失**，不是為了讓它們合理化。
#:
#: ⚠️ **處置欄的權威來源**：核准線框 `docs/wireframes/wireframe-macro-health.html`
#:    §04 搬移對照表（逐字），以及 `ui/views/page_02_health.py` 的四個常數。
#: ⛔⛔ **2026-09-07：本表被實測抓到會說謊，七筆已移除、一筆改判。讀完再改這張表。**
#: **有意識的更正，不是漏刪** · 日期 **2026-09-07** ·
#: 決策者：**AI 總管（依獨立稽核實測）**。
#:
#: **病根不是「誰漏接了幾支」，是「已搬 ③」這個標籤本身含混** ——
#: 它既可讀成「**移轉完成**」，也可讀成「**線框判給 ③**」，
#: 而**沒有任何機器規則在驗它是不是真的**。於是 ② 切換上線的那一刻，
#: 八筆標「已搬 ③」的東西裡有**六筆在整個 App 都到不了了，全綠**。
#:
#: **實測（2026-09-07，於 `d0efb98`；AST 遞移閉包，「呼叫 ＋ 裸參照」都算邊）**：
#: 從 `app.py` 現行掛載的**五個活分頁入口**出發（可達 994 個符號），
#: 下列六支**一個都不可達**；對**尚未掛載**的新 ③ view
#: （`ui/views/page_03_research.py::render_fund_research`，可達 106 個）單獨再掃，
#: **同樣一個都不可達** ——
#: `_render_investment_calc` / `_render_holdings_block` /
#: `_render_bollinger_expanders` / `_render_per_fund_news_expanders` /
#: `_render_per_fund_three_ratio_expanders` / `_render_low_base_screener`。
#: **正對照**：同一次掃描裡 `render_holdings_detail` / `render_holdings_diag` **可達**
#: ⇒ 掃描器不是恆假。**負對照**：虛構符號解析不到、零命中。
#:
#: **兩種被抓到的說謊，逐一寫明（不要只讀結論）**
#:
#: 1. **「已搬 ③」對六筆為假** —— ③ 從來沒有接過它們。線框寫的是「**搬**」，
#:    不是「刪除」；② 與 ③ 都沒有 ⇒ **線框未被滿足**。
#:    **處置**：五筆**接回 ②**（`page_02_health.REATTACHED_PENDING_PAGE_03`，
#:    ③ 實作好要移走），故從本表移除 —— 本表只收「**到不了**」的東西。
#:    第六筆 `_render_low_base_screener` **接不回來**，改判 `刻意不接` 並具名三道阻擋（見該列）。
#: 2. ~~「`render_holdings_detail` 的**唯一 caller** 是 `_render_holdings_block`」~~
#:    ~~「`render_holdings_diag` 的**唯一 caller** 是 `_render_per_fund_news_expanders`」~~
#:    —— **兩句都是假的**。實測全 repo（排除 `tests/`、`scripts/`）參照它們的模組各有**兩個**：
#:    另一個是 **`ui/tab2_single_fund.py`**，而它經 ③ `ui.tab_fund_research` 可達。
#:    ⇒ 這兩支**當時根本沒有掉**，是被一個假的下游推論列進來的。
#:    **它們自 2026-09-07 起經接回的 `_render_holdings_block` /
#:    `_render_per_fund_news_expanders` 也從 ② 可達**，故一併從本表移除。
#:
#: ⚠️ **為什麼既有守衛沒擋住**：`test_the_disposition_table_never_lists_something_still_reachable`
#: 比對的是「**新 ② 到不到得了**」，而這兩支當時對 ② 確實到不了 ——
#: **表上的「處置」是 ②-scoped，但「理由」寫的是 repo-wide 的全稱句**，
#: 兩者射程不同，而**沒有任何規則在驗理由**。
#: ⛔ 新增或修改任何一列的理由時，**「唯一 caller 是 X」這種全稱句要實測再寫**
#: （`git grep` 之後**逐一判讀是 import、字串還是註解**），否則就別寫。
DROPPED_WITH_REASON: "dict[str, tuple[str, str]]" = {
    # ── 核准線框 §04 明文「搬 ③ 基金研究」，但 ③ 從來沒有接過 ────────
    #    ⭐ 五筆（投資試算／TER＋持股／Bollinger／個股新聞／三率穿透）與
    #       `render_holdings_detail` / `render_holdings_diag` 兩筆已於 2026-09-07 移除，
    #       理由見本常數上方。**它們現在從 ② 可達，留在表上就是說謊。**
    "ui.tab_fund_grp_health::_render_low_base_screener":
        ("刻意不接", "🎯 選基金（低基期進場點）。核准線框 §04 逐字判給 ③ "
                      "（『回答該買哪一檔而不是哪一檔有問題』），"
                      "~~但本列 2026-09-07 之前標的是「已搬 ③」，而 ③ 從來沒有接過它~~ —— "
                      "**有意識的更正，不是漏刪**（2026-09-07，AI 總管，依獨立稽核實測）。"
                      "與同批接回 ② 的五塊是**同一個病**，但它**接不回來**，三道阻擋各自獨立、"
                      "任何一道都不該為了它而放寬（逐條見 "
                      "`page_02_health.BLOCKED_FROM_REATTACH`）："
                      "(1) 它住在**舊 ② 的 tab 檔本身**，而 "
                      "`test_the_page_does_not_delegate_to_the_old_tab` 對 `ui.tab*` "
                      "是**無白名單出口的硬封鎖**；"
                      "(2) `st.download_button(..., _df.to_csv(index=False).encode(...), ...)` "
                      "—— `to_csv` 是引數，在 `if not rows: return` 早退之後**無條件求值**"
                      "（實測 `if` 巢深 0），依「② 零寫入」裁決不接。"
                      "⚠️ **這正是當初被誤記在 `render_rotation_section` 頭上的機制**，"
                      "在這一支身上是真的；"
                      "(3) 它吃**健診大表列** `ok_rows`（每列帶 `_fund_raw`），不是本頁的持股項，"
                      "需要 rows adapter —— 與下方兩筆「待客戶裁決」同類，規格未定，"
                      "**不硬湊一份假的 rows**（§1）。"
                      "⛔ 要接回它，正解是**先解掉阻擋**（搬出舊 tab 檔／把 `to_csv` 移進"
                      "使用者觸發的分支／定出 adapter 規格），**不是改守衛**。"),

    # ── 刻意不接（具名理由）────────────────────────────────────────
    "ui.helpers.fund_grp_health.rotation::render_rotation_section":
        ("刻意不接", "page_02_health.DROPPED_FOR_ZERO_WRITE：依「② 零寫入」裁決移出。"
                      "守衛對它是**已知偽陽性**（`CLAUDE.md §8.3.P` 的 `P-SINKGRAIN-1`），"
                      "但偽陽性不是把它接回來的理由，也不是改守衛的理由。"),
    "ui.helpers.fund_grp_health.rotation::_render_pairs_ui":
        ("刻意不接", "下游：唯一 caller 是 `render_rotation_section`。"),
    "ui.helpers.fund_grp_health.rotation::_render_pairs_body":
        ("刻意不接", "下游：同上。它就是那個偽陽性寫入槽本身（`to_csv` 在 "
                      "`if offer_download:` 內，而委派入口硬編 `offer_download=False`）。"),
    "ui.helpers.story_nav::render_flow_nav":
        ("刻意不接", "新 View 一律只畫 `render_story_nav`，不畫四層流程導覽 —— "
                      "① `page_01_macro` 與 ⑤ `page_05_settings` 已是同樣作法（既有前例，"
                      "非本批發明）。ui/tab1_macro.py 就地註明「render_flow_nav 移除」。"),
    "ui.tab_fund_grp_health::_render_health_table":
        ("刻意不接", "新頁自己畫線框指定的 **9 欄**逐檔體檢表"
                      "（`page_02_health._render_health_table`），不是舊的 48 欄大表。"),
    "ui.tab_fund_grp_health::_render_health_summary":
        ("刻意不接", "新頁以「組合健康總分」＋三張警示卡取代 5 格 KPI；"
                      "其中『🔴 吃本金』那一格由 `_eating_tally()` 承接。"
                      "⚠️ ~~另三格~~ → **另四格**（檢查檔數／🟢 健康／🟡 警示／"
                      "累積 TWD 配息）與『抓取失敗前置摘要』**沒有承接者**。"
                      "**2026-09-07 更正：本表第四處被抓到的不符 —— 數字與它自己的"
                      "列舉互相矛盾**（有意識的更正，不是漏刪；AI 總管，依實測）。"
                      "舊 ② `_render_health_summary` 實測畫 **5 格** KPI "
                      "（`k1`~`k5`），其中 `🔴 吃本金` 由 `_eating_tally()` 承接 "
                      "⇒ 剩下的是 **4 格**，不是 3 格。"
                      "⚠️ **一個數字對不上自己的清單，讀者只會相信數字** —— "
                      "「另三格」會讓下一個人補完三格就以為結清了。"),

    # ── 橋接容器（本身不畫內容）────────────────────────────────────
    "ui.helpers.fund_grp_health::render_fund_grp_health_extras":
        ("橋接容器", "舊 ② 的整包橋。新頁改為**逐支具名委派**（page_02_health."
                      "DELEGATED_ENTRIES），刻意不走整包 —— 整包會把黑名單那兩支"
                      "（會寫客戶 Google Sheet）一起帶進射程。"),
    "ui.tab_fund_grp_health::_render_health_3tables":
        ("橋接容器", "舊 ② 自己的三表容器。它底下的內容各自在本表另有一列。"),

    # ── 待客戶裁決 ─────────────────────────────────────────────────
    "ui.helpers.fund_grp_health.switch_section::render_switch_section":
        ("待客戶裁決", "page_02_health.DEFERRED_ENTRIES：吃健診大表列，"
                        "與本頁 9 欄列 key 交集 0/8，需要 rows adapter，規格未定。"),
    "ui.helpers.fund_grp_health.regime_section::render_regime_fit_section":
        ("待客戶裁決", "同上（key 交集 0/4）。線框 §04 寫「併 ② 市場環境一行」，"
                        "而新頁目前沒有那一行。"),

    # ── ⚠️ 未登記缺口（本批新查出）─────────────────────────────────
    "ui.tab_fund_grp_health::_render_mj_freshness_banner":
        ("未登記缺口", "⭐ **本批新查出**。核准線框把它列在「大表區 8 塊」之一"
                        "（逐字：「MoneyDJ 資料新鮮度 banner　_render_mj_freshness_banner」）"
                        "，但**沒有給處置**；新頁也沒有等價物。"
                        "⚠️ #809 的獨立稽核已就 ④ 點名過同一支「本表未記」。"
                        "⛔ 本批**不補**：補它要決定新頁哪裡放、吃哪一份 rows，那是規格。"),
    "ui.helpers.io.freshness::render_mj_freshness_banner":
        ("未登記缺口", "~~下游：唯一 caller 是上一列那支包裝。~~ "
                        "⛔ **2026-09-07 更正：那句是假的 —— 本表第三處被抓到的"
                        "「唯一 caller」全稱句**（有意識的更正，不是漏刪；AI 總管，依實測）。"
                        "實測全 repo（排除 `tests/`／`scripts/`）另有兩個呼叫端："
                        "`ui/tab2_single_fund.py` 與 `ui/tab3_portfolio.py`，"
                        "本函式因此**經 ③ 與 ④ 仍然可達、並沒有從 App 消失**。"
                        "⇒ 真正掉的只有上一列那支**② 專屬的包裝**"
                        "（`_render_mj_freshness_banner`，吃 `ok_rows`）。"
                        "**本列因此是「② 的入口沒了」，不是「這個 banner 沒了」** —— "
                        "兩者的補法完全不同，含混會讓下一個人去重做一個已經存在的東西。"
                        "⛔ 本批仍**不補**（補它要決定新頁哪裡放、吃哪一份 rows，那是規格）。"),
}


def test_app_mounts_the_new_health_view():
    """② 真的掛在 `app.py` 上 —— 而且是**新** View。

    ⛔ 沒有這一條，底下所有「新頁沒有多寫、沒有掉東西」的證明都可能是在證明一個
       **沒有人打開**的檔案（本 repo 的既有病：「算對了沒接出去」）。
    ⚠️ 只驗 ② 那一格；①③④⑤ 由 `tests/test_ia_kit.py::_SLOT_RENDER` 整表守。
    """
    _app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from ui.views.page_02_health import" in _app, (
        "`app.py` 沒有 import 新 ② —— 接線鏈斷在 app.py 這一節。")
    _tree = ast.parse(_app)
    _in_slot = [
        _c.func.id
        for _n in ast.walk(_tree) if isinstance(_n, ast.With)
        for _it in _n.items
        if isinstance(_it.context_expr, ast.Name) and _it.context_expr.id == "tab_health"
        for _c in ast.walk(_n)
        if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)
        and _c.func.id.startswith("render_")
    ]
    assert _in_slot == ["render_holdings_health"], (
        f"`with tab_health:` 呼叫的是 {_in_slot}，應為 ['render_holdings_health']。")


def test_the_switch_adds_no_write_surface():
    """⭐ 切換 ② **沒有**把任何新的寫入槽拉進射程（新頁閉包的寫入面 ⊆ 舊 ②）。

    這是「切換不增加 Google Sheet 風險」最便宜的可執行版本：② 本來就在線上，
    **舊 ② 碰得到的東西，使用者今天就已經碰得到**。要證的不是「新頁不寫東西」，
    而是「**新頁沒有帶進舊頁沒有的寫入面**」。

    ⚠️ 反方向（舊有新無）**刻意不斷言**：切換移除寫入面是安全方向，
    釘死它只會讓下一次合理的移除誤紅。本批實測移除 2 個（都是 `to_csv`）。
    """
    _old, _new = _sinks(OLD_ENTRY[0]), _sinks(NEW_ENTRY[0])
    assert _old, f"舊 ②（{OLD_ENTRY[0]}）一個寫入槽都沒掃到 —— 基準沒了。"
    assert _new, f"新 ②（{NEW_ENTRY[0]}）一個寫入槽都沒掃到 —— 掃描器可能壞了。"
    _extra = sorted(_new - _old)
    assert not _extra, (
        f"新 ② 的閉包多出了舊 ② 沒有的寫入槽（{len(_extra)} 個）：\n  "
        + "\n  ".join(f"{_m}::{_q} → .{_p}(…)" for _m, _q, _p in _extra)
        + "\n⛔ 切換 ② 不該擴大寫入面。")


def test_the_page_itself_writes_nothing():
    """被測檔**自己**一個寫入 primitive 都沒有 —— 它是版面殼，不該自己動手寫。

    ⚠️ 與上一條**不重複**：上一條看整個閉包（含被委派的舊模組），本條只看這一個檔。
    """
    _own = sorted(_write_sinks_in(ast.parse(NEW_SRC.read_text(encoding="utf-8"))))
    assert not _own, (
        f"被測檔自己出現了寫入 primitive：{_own}\n"
        "⛔ (A) 路線：新頁只做版面與編排，寫入一律呼叫既有舊模組。")


def test_the_scanner_can_actually_see_a_write():
    """⭐ **正對照** —— 沒有這一條，上面兩條可能只是恆綠。"""
    _plain = _write_sinks_in(ast.parse("def f(ws):\n    ws.append_rows([[1]])\n"))
    assert ("f", "append_rows") in _plain, (
        f"掃描器看不見最直白的 gspread 寫入：{_plain} —— 上面兩條等於恆綠。")
    _method = _write_sinks_in(ast.parse(
        "class R:\n    def save(self, p):\n        p.write_text('x')\n"))
    assert ("R.save", "write_text") in _method, (
        f"掃描器走不進 class 方法：{_method} —— class 方法形態的寫入會漏掉。")


def test_the_call_graph_walker_is_not_a_no_op():
    """⭐ **正對照** —— `_reach` 真的走得動，而且走得進「裸參照」那條邊。

    ⛔ 沒有這一條，下面兩條「差集」規則可能只是在比較兩個空集合。
    """
    _new = _reach(NEW_ENTRY)
    _old = _reach(OLD_ENTRY)
    assert len(_new) > 50, f"新 ② 可達集合只有 {len(_new)} 個 —— walker 可能壞了。"
    assert len(_old) > 50, f"舊 ② 可達集合只有 {len(_old)} 個 —— walker 可能壞了。"
    # 裸參照那條邊：`safe_section("診斷條件", _render_filter_form)` 沒有呼叫節點。
    assert ("ui.views.page_02_health", "_render_filter_form") in _new, (
        "走不到 `_render_filter_form` —— `safe_section(標籤, fn)` 這種**裸參照**"
        "委派沒有被算成邊，整個閉包會嚴重低估（#805 已經吃過同一個教訓）。")
    # 負對照：虛構符號不得命中。
    assert ("ui.views.page_02_health", "_render_nothing_at_all_xyz") not in _new


def test_every_dropped_renderer_has_a_named_disposition():
    """⭐ 切換之後**到不了**的每一個渲染函式，都必須有一筆具名去處。

    **這一條就是「功能未丟失」的可執行版本。** 沒有它，下一次有人動委派清單時，
    掉下去的東西**不會有任何紅燈**（#809 的獨立稽核就是靠人工第二種切法才撿回
    三支「兩張表都沒有它」的東西 —— 那不該靠運氣）。

    ⛔ **它不保證「使用者沒有少看到東西」** —— 同一個畫面可以由不同函式畫出來，
       而本條只看呼叫圖。它保證的是**沒有東西無聲消失**。
    """
    _lost = sorted(_renderers(_reach(OLD_ENTRY)) - _renderers(_reach(NEW_ENTRY))
                   - {f"{OLD_ENTRY[0]}::{OLD_ENTRY[1]}"})
    assert _lost, "舊 ② 與新 ② 的渲染差集是空的 —— 對帳失去對象，先確認 walker 沒壞。"
    _unlisted = [x for x in _lost if x not in DROPPED_WITH_REASON]
    assert not _unlisted, (
        f"切換 ② 讓下列 {len(_unlisted)} 個渲染函式變成到不了，"
        "而它們在 DROPPED_WITH_REASON 裡**沒有去處**：\n  "
        + "\n  ".join(_unlisted)
        + "\n⛔ 不要為了讓本條變綠就隨手補一行 —— 先回答：它去哪了？"
          "\n   四種合法答案：已搬 ③／刻意不接（具名理由）／待客戶裁決／橋接容器。"
          "\n   真的還沒有答案 → 標 `未登記缺口` 並寫進 PR 描述，**不要靜默略過**。")
    _bad = {k: v[0] for k, v in DROPPED_WITH_REASON.items() if v[0] not in _DISPOSITIONS}
    assert not _bad, f"處置欄用了未定義的值：{_bad}（合法值：{sorted(_DISPOSITIONS)}）"


def _page_const(name: str) -> tuple:
    """從**被測頁的原始碼**讀出一個 tuple 常數（`ast.literal_eval`，不 import 本頁）。

    ⚠️ 與 `tests/test_wf02_health_skeleton.py` 的同名 helper 是**同一把尺的兩份拷貝**，
    刻意不互相 import —— 本檔的賣點是「純 AST、不碰 runtime」，
    那一份在模組層 import streamlit。代價寫在這裡：常數改名兩邊都要改。
    """
    for _n in ast.parse(NEW_SRC.read_text(encoding="utf-8")).body:
        _t = (_n.targets[0] if isinstance(_n, ast.Assign)
              else getattr(_n, "target", None) if isinstance(_n, ast.AnnAssign) else None)
        if isinstance(_t, ast.Name) and _t.id == name:
            return ast.literal_eval(_n.value)
    raise AssertionError(
        f"{NEW_SRC.name} 裡找不到常數 {name} —— 它是機器規則的 SSOT，不可以被改名或刪掉。")


def test_the_reattached_blocks_are_reachable_from_page_two():
    """⭐ **2026-09-07 新增：接回 ② 的那幾塊，必須真的從 ② 的入口到得了。**

    **這條為什麼比「把它們接回去」更重要**
    --------------------------------------
    2026-09-07 的事故不是「有人漏接了六支」，是**一張表用了一個含混的標籤**
    （「已搬 ③」既可讀成「移轉完成」也可讀成「線框判給」），
    而**沒有任何機器規則在驗它是不是真的**。
    接回去只修今天這幾支；**這條才擋得住下一次**。

    ⛔ **它是 fail-closed 的**：常數空了、符號解析不到、或委派被拿掉，**三種都紅**。

    **突變驗證（2026-09-07 逐支實跑，五支各驗一次）**：
    把 `page_02_health._render_reattached_sections` 裡任一支的委派拿掉 →
    **本條轉紅並指名那一支**；還原 → 轉綠。
    第六支（`_render_low_base_screener`，接不回來）由
    :func:`test_the_blocked_reattach_cannot_disappear_quietly` 承接。

    ⚠️ **本條不宣稱「使用者看得到它們」** —— 它只看呼叫圖（同本檔其餘規則的射程限制）。
    畫面側由 `tests/test_wf02_health_skeleton.py` 的渲染守衛負責。
    """
    _entries = [tuple(_e) for _e in _page_const("REATTACHED_PENDING_PAGE_03")]
    assert _entries, (
        "`REATTACHED_PENDING_PAGE_03` 是空的 —— 本條會退化成恆綠。\n"
        "⛔ 若那幾塊真的搬去 ③ 了，請連同本條與 `DELEGATED_ENTRIES` 一起改，"
        "並在 `DROPPED_WITH_REASON` 補上它們的新去處。")

    _reachable = _reach(NEW_ENTRY)
    assert len(_reachable) > 50, (
        f"新 ② 可達集合只有 {len(_reachable)} 個 —— walker 可能壞了，本條結論沒有意義。")

    _missing = [f"{_m}::{_s}" for _m, _s in _entries
                if _resolve(_m, _s) is None or _resolve(_m, _s) not in _reachable]
    assert not _missing, (
        f"下列 {len(_missing)} 支登記為「已接回 ②」，但從 ② 的入口 "
        f"`{NEW_ENTRY[0]}::{NEW_ENTRY[1]}` **到不了**：\n  "
        + "\n  ".join(_missing)
        + "\n⛔ 這正是 2026-09-07 那次事故的形狀：**表上寫著有，實際上哪裡都沒有。**"
          "\n   要嘛把委派接回 `_render_reattached_sections()`，"
          "\n   要嘛把它從 `REATTACHED_PENDING_PAGE_03` 移走並在 "
          "`DROPPED_WITH_REASON` 給它一筆具名去處 —— **不准兩邊都沒有。**")

    # 負對照：虛構符號不得命中（沒有這一行，上面的 `not in` 可能只是恆真）。
    assert _resolve("ui.helpers.fund_grp_health.investment",
                    "_render_nothing_at_all_xyz_9999") is None


def test_the_blocked_reattach_cannot_disappear_quietly():
    """⭐ **2026-09-07 新增：接不回來的那一支，必須具名掛在對照表上。**

    `_render_low_base_screener` 與接回的那五塊是**同一個病**（標「已搬 ③」、
    五個活分頁與新 ③ view 都到不了），但它有三道各自獨立的阻擋（見
    `page_02_health.BLOCKED_FROM_REATTACH`）。
    **接不回來不是「可以讓它消失」** —— 它必須留在 :data:`DROPPED_WITH_REASON` 裡，
    這樣它**不能無聲消失第二次**。

    ⛔ **本條不驗那三道阻擋還成不成立**（那要跑 runtime 與讀另一份測試檔）；
       它只釘住「**這一支有沒有被除名**」。阻擋的內容由該常數的註解負責。

    **突變驗證（2026-09-07 實跑）**：把它從 `DROPPED_WITH_REASON` 刪掉 →
    本條 ＋ :func:`test_every_dropped_renderer_has_a_named_disposition` **兩條同時轉紅**；
    還原 → 轉綠。
    """
    _blocked = [tuple(_e) for _e in _page_const("BLOCKED_FROM_REATTACH")]
    assert _blocked, (
        "`BLOCKED_FROM_REATTACH` 是空的 —— 若那一支真的接回來了，"
        "請把它移進 `REATTACHED_PENDING_PAGE_03` 與 `DELEGATED_ENTRIES`。")

    _reachable = _reach(NEW_ENTRY)
    for _m, _sym in _blocked:
        _key = f"{_m}::{_sym}"
        assert _key in DROPPED_WITH_REASON, (
            f"`{_key}` 登記為「接不回來」，卻**不在 DROPPED_WITH_REASON 裡** —— "
            "那就等於它可以無聲消失，正是 2026-09-07 事故的形狀。")
        assert DROPPED_WITH_REASON[_key][0] in _DISPOSITIONS, (
            f"`{_key}` 的處置欄用了未定義的值：{DROPPED_WITH_REASON[_key][0]!r}")
        assert _resolve(_m, _sym) not in _reachable, (
            f"`{_key}` 登記為「接不回來」，但新 ② **其實到得了它** —— "
            "一張說謊的對照表比沒有表更糟；請把它移出 `BLOCKED_FROM_REATTACH`。")


def test_the_disposition_table_never_lists_something_still_reachable():
    """反向：表上不准出現「其實還在」的項目。

    ⚠️ **一張會說謊的對照表比沒有表更糟** —— ④ 的 `test_wf04_old_block_inventory.py`
    就地記著同一件事：「於是表上寫著『已委派』的東西**其實兩邊都不存在**」。
    本條擋的是相反方向：寫著「已搬走／刻意不接」，但它其實還在新頁的射程裡。
    """
    _still = sorted(set(DROPPED_WITH_REASON) & _renderers(_reach(NEW_ENTRY)))
    assert not _still, (
        "DROPPED_WITH_REASON 說這些掉了，但新 ② **仍然到得了**它們：\n  "
        + "\n  ".join(_still)
        + "\n⛔ 把它們從表上刪掉 —— 一張說謊的對照表比沒有表更糟。")


def test_the_old_page_is_still_the_fallback():
    """舊 ② 一個字都沒動、還在磁碟上 —— 它是回退路徑，也是新頁委派的對象。

    ⚠️ 本條**不驗內容是否一字未改**（那是 PR 邊界的事，`git` 比 AST 準）；
    它只擋「順手把舊檔刪了」這一種。
    """
    assert OLD_SRC.exists(), (
        f"{OLD_SRC.relative_to(ROOT).as_posix()} 不見了 —— 那是 ② 的回退路徑，"
        "而且新頁委派的正是它底下那些舊模組。")
    _tree = ast.parse(OLD_SRC.read_text(encoding="utf-8"))
    _tops = {n.name for n in _tree.body
             if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assert OLD_ENTRY[1] in _tops, (
        f"舊 ② 的入口 `{OLD_ENTRY[1]}` 不見了 —— 回退路徑斷了。")
