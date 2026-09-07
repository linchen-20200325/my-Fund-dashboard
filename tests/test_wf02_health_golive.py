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
DROPPED_WITH_REASON: "dict[str, tuple[str, str]]" = {
    # ── 核准線框 §04 明文「搬 ③ 基金研究」──────────────────────────
    "ui.helpers.fund_grp_health.investment::_render_investment_calc":
        ("已搬 ③", "線框 §04：每檔一個 expander ＝ 單檔細節，一律屬 ③。"
                    "已登記於 page_02_health.MOVED_TO_PAGE_03。"),
    "ui.helpers.fund_grp_health.investment::_render_holdings_block":
        ("已搬 ③", "同上（TER ＋ 前十大持股）。已登記於 MOVED_TO_PAGE_03。"),
    "ui.helpers.fund_grp_health.signals::_render_bollinger_expanders":
        ("已搬 ③", "線框 §04：⑪ Bollinger 詳圖 → ③。已登記於 MOVED_TO_PAGE_03。"),
    "ui.helpers.fund_grp_health.ai::_render_per_fund_news_expanders":
        ("已搬 ③", "線框 §04：⑬ 個股新聞 → ③。已登記於 MOVED_TO_PAGE_03。"),
    "ui.helpers.fund_grp_health.ai::_render_per_fund_three_ratio_expanders":
        ("已搬 ③", "線框 §04：⑭ 三率穿透 → ③。已登記於 MOVED_TO_PAGE_03。"),
    "ui.helpers.holdings::render_holdings_detail":
        ("已搬 ③", "下游：唯一 caller 是 `_render_holdings_block`（已搬 ③）。"),
    "ui.helpers.holdings::render_holdings_diag":
        ("已搬 ③", "下游：唯一 caller 是 `_render_per_fund_news_expanders`（已搬 ③）。"),
    "ui.tab_fund_grp_health::_render_low_base_screener":
        ("已搬 ③", "⭐ **本批新查出**。核准線框 §04 逐字：「🎯 選基金（低基期進場點）"
                    "｜tab_fund_grp_health.py::_render_low_base_screener｜搬｜③ 基金研究」"
                    "——『回答該買哪一檔而不是哪一檔有問題』。"
                    "⚠️ 它**不在** page_02_health.MOVED_TO_PAGE_03 裡（那個常數只收"
                    "`render_fund_grp_health_extras` 底下的，而本支住在舊 ② 根檔）。"),

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
                      "⚠️ 另三格（檢查檔數／🟢 健康／🟡 警示／累積 TWD 配息）與"
                      "『抓取失敗前置摘要』**沒有承接者** —— 見下方 `未登記缺口`。"),

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
        ("未登記缺口", "下游：唯一 caller 是上一列那支包裝。"),
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
