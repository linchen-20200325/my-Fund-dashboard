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
8. :func:`test_a_page_three_label_must_be_reachable_from_page_three` —— ⭐ **2026-09-07 新增**
9. :func:`test_a_pending_label_must_still_have_a_live_path` —— ⭐ **2026-09-07 新增**

   ⛔ **第 8／9 條是一對，它們是 2026-09-07 事故的解藥，比事故本身的補救更重要。**
   事故不是「誰漏接了六支」，是 ~~`已搬 ③`~~ 這個標籤**含混**
   （「移轉完成」vs「線框判給」兩種讀法都成立），
   而**上面第 5／6 條都驗不到它是哪一種** —— 第 5 條問「有沒有登記」、
   第 6 條問「有沒有被新 ② 到得了」，**沒有一條問「它宣稱的那個去處真的有嗎」**。
   於是八筆標「已搬 ③」的東西裡有**六筆連 ③ 都到不了**，本檔照樣全綠。

   新的兩條把標籤釘成**機器驗得動**的斷言，而且**兩個方向都 fail-closed**：
   標「③ 已到得了」卻到不了 → 紅；標「判給 ③（尚未實作）」卻其實到得了 → 也紅。
   **含混之所以能活這麼久，就是因為沒有任何一個方向會紅。**

⛔ **不守什麼（照實列，不要讀成「功能未丟失已經證完了」）**
------------------------------------------------------------
* 本檔是**靜態**的。第 5／6 條回答「哪些渲染函式**呼叫圖上**到不了」，
  **不回答**「使用者實際少看到什麼」—— 同一個畫面可以由不同函式畫出來。
* :func:`_reach` 的射程外：`getattr` / 字典派發 / 字串組出來的動態呼叫。
  **本檔不宣稱窮舉。**
* **第 9 條不驗「舊 ② 有沒有掛在 `app.py` 上」。** 那不是漏掉，是那個斷言**兩邊都會錯**
  （寫「必須掛著」在舊 ② 接回之前恆紅，寫「必須沒掛」在接回當天恆紅）。
  ⇒ 它保證的是「**路徑存在且完好**」，**不是**「**它現在被掛出來了**」。
  舊 ② 的接回是另一組的 PR；在那之前，那六塊對使用者**仍然是看不見的**。
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
#:
#: ⛔⛔ **2026-09-07：~~`已搬 ③`~~ 整個退場，拆成兩個「機器驗得動」的標籤。**
#: **有意識的政策變更，不是漏刪** · 日期 **2026-09-07** ·
#: 決策者：**AI 總管（依獨立稽核實測）**。
#:
#: **舊標籤錯在哪 —— 這一段是本次事故的全部**：`已搬 ③` **含混**，
#: 它既可讀成「**移轉完成、③ 到得了**」，也可讀成「**線框判給 ③**（還沒人做）」。
#: 而**沒有任何機器規則在驗它是哪一種** —— 於是 ② 切換上線之後，
#: 八筆標「已搬 ③」的東西裡有**六筆連 ③ 都到不了**，而本檔**全綠**。
#:
#: **實測（2026-09-07，於 `d0efb98`；AST 遞移閉包，「呼叫 ＋ 裸參照」都算邊）**：
#: 從 `app.py` **自動抽出**的 ③ 活入口出發（可達 **344** 個符號），
#: 八筆裡**只有 2 筆**（`render_holdings_detail` / `render_holdings_diag`）到得了；
#: 另外**六筆全部到不了**。對**尚未掛載**的新 ③ view
#: （`ui/views/page_03_research.py::render_fund_research`，可達 **106**）再掃一次，
#: **八筆一個都到不了**。
#: **正對照**：同一次掃描裡那 2 筆**確實可達** ⇒ 掃描器不是恆假。
#: **負對照**：虛構符號解析不到、零命中。
#:
#: **新的兩個標籤，各自有一條機器規則盯著（這才是重點，不是改字）**：
#:
#: ================== ============================================ ==========================
#: 標籤                機器意義（fail-closed）                        守它的規則
#: ================== ============================================ ==========================
#: `③ 已到得了`        **③ 的活入口真的到得了**                        `test_a_page_three_label_
#:                                                                  must_be_reachable_from_
#:                                                                  page_three`
#: `判給 ③（尚未實作）` **③ 到不了**，但**至少有一條活路徑到得了**        `test_a_pending_label_
#:                    （雙軌之下 ＝ 保留不動的舊 ②）                    must_still_have_a_live_
#:                                                                  path`
#: ================== ============================================ ==========================
#:
#: ⛔ **兩者互斥且雙向 fail-closed**：標「已到得了」卻到不了 → 紅；
#: 標「尚未實作」卻其實到得了 → 也紅（那就該改標另一個）。
#: **含混之所以能活這麼久，就是因為沒有任何一個方向會紅。**
_DISPOSITIONS = frozenset({
    "③ 已到得了",      # ③ 的活入口**實測可達**（不宣稱它是「被搬過去的」）
    "判給 ③（尚未實作）",  # 核准線框判給 ③，但 ③ 還沒實作；目前靠保留的舊 ② 仍看得見
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
#: 六筆「核准線框判給 ③、但 ③ 尚未實作」共用的更正註。
#:
#: ⚠️ **寫成常數而不是抄六份**：六份手抄的更正註，下一次只會有一份被改到
#: （本 repo 已實證過這個形狀 —— 見本檔 2026-09-07 抓到的另外兩處「唯一 caller」）。
#:
#: ⚠️ **代價，據實寫明（我自己當場踩到，所以留在這裡）**：用 `"…" + _MOVED` 拼接之後，
#: :data:`DROPPED_WITH_REASON` **不再能被 `ast.literal_eval` 靜態求值**
#: （它變成 `ast.BinOp`，不是字面值）。本檔自己不受影響 —— 表是 module 層由 Python
#: 直接求值的；但**任何想「不 import 就讀這張表」的工具會當場炸掉**
#: （本批寫稽核探針時就是這樣炸的）。
#: **2026-09-07 實測全 repo：目前沒有任何東西靜態解析這張表**
#: （`grep -rn "DROPPED_WITH_REASON" --include=*.py` 只命中本檔），所以現在是安全的。
#: ⛔ **哪天要加一個靜態讀它的工具，先改這裡（拆回字面值），不要去改那個工具。**
_MOVED: str = (
    "~~已搬 ③~~ → **判給 ③（尚未實作）**（2026-09-07 就地更正，"
    "**有意識的更正，不是漏刪**；決策者：AI 總管，依獨立稽核實測）。"
    "**實測：③ 的活入口到不了它，尚未掛載的新 ③ view 也到不了。** "
    "線框 §04 判給 ③ 是**真的**，被推翻的是「已搬」二字隱含的『③ 已經有了』。"
    "⚠️ **它現在看得見，靠的是雙軌**：客戶 2026-09-07 原則 —— "
    "新 UI 以**新增 Tab 並行掛載**、**舊 Tab 一律保留不動**，直到客戶親自驗收才刪。"
    "本支經**保留的舊 ②**仍到得了（守衛："
    "`test_a_pending_label_must_still_have_a_live_path`）。"
    "⛔ **不得**把它讀成「所以可以不用做 ③」——"
    "它讀作「**債還在，而且現在有機器盯著它有沒有路可走**」。")


DROPPED_WITH_REASON: "dict[str, tuple[str, str]]" = {
    # ── 核准線框 §04 判給 ③，但 ③ 尚未實作；靠保留的舊 ② 仍看得見 ──────
    "ui.helpers.fund_grp_health.investment::_render_investment_calc":
        ("判給 ③（尚未實作）",
         "線框 §04：每檔一個 expander ＝ 單檔細節，一律屬 ③。" + _MOVED),
    "ui.helpers.fund_grp_health.investment::_render_holdings_block":
        ("判給 ③（尚未實作）", "同上（TER ＋ 前十大持股）。" + _MOVED),
    "ui.helpers.fund_grp_health.signals::_render_bollinger_expanders":
        ("判給 ③（尚未實作）", "線框 §04：⑪ Bollinger 詳圖 → ③。" + _MOVED),
    "ui.helpers.fund_grp_health.ai::_render_per_fund_news_expanders":
        ("判給 ③（尚未實作）", "線框 §04：⑬ 個股新聞 → ③。" + _MOVED),
    "ui.helpers.fund_grp_health.ai::_render_per_fund_three_ratio_expanders":
        ("判給 ③（尚未實作）", "線框 §04：⑭ 三率穿透 → ③。" + _MOVED),
    "ui.tab_fund_grp_health::_render_low_base_screener":
        ("判給 ③（尚未實作）",
         "核准線框 §04 逐字：「🎯 選基金（低基期進場點）"
         "｜tab_fund_grp_health.py::_render_low_base_screener｜搬｜③ 基金研究」"
         "——『回答該買哪一檔而不是哪一檔有問題』。" + _MOVED),

    # ── ③ 的活入口實測可達（**不是**因為被搬過去，理由見各列）──────────
    "ui.helpers.holdings::render_holdings_detail":
        ("③ 已到得了",
         "~~下游：唯一 caller 是 `_render_holdings_block`（已搬 ③）。~~ "
         "⛔ **2026-09-07 更正：那句是假的**（**有意識的更正，不是漏刪**；"
         "決策者：AI 總管，依獨立稽核實測）。實測全 repo（排除 `tests/`／`scripts/`）"
         "參照它的模組有**兩個**：`ui.helpers.fund_grp_health.investment` **與** "
         "**`ui/tab2_single_fund.py`**。"
         "⇒ 它**到得了 ③**（`ui.tab_fund_research` → `tab2_single_fund`），"
         "而且**跟 `_render_holdings_block` 搬不搬毫無關係** —— "
         "它是**共用 helper**，不是那一支的專屬下游。"
         "⚠️ **舊理由不只是講錯一個 caller，它把因果整個講反了**："
         "照它讀，`_render_holdings_block` 一旦回到 ②，這一支就會跟著離開 ③ —— "
         "**不會**，`tab2_single_fund` 那條線獨立存在。"),
    "ui.helpers.holdings::render_holdings_diag":
        ("③ 已到得了",
         "~~下游：唯一 caller 是 `_render_per_fund_news_expanders`（已搬 ③）。~~ "
         "⛔ **同上，2026-09-07 更正：假的**。實測參照它的模組是 "
         "`ui.helpers.fund_grp_health.ai` **與 `ui/tab2_single_fund.py`** 兩個，"
         "經後者從 ③ 可達。"),

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
                      "列舉互相矛盾**（**有意識的更正，不是漏刪**；決策者：AI 總管，"
                      "依實測）。舊 ② `_render_health_summary` 實測畫 **5 格** KPI"
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
        ("未登記缺口",
         "~~下游：唯一 caller 是上一列那支包裝。~~ "
         "⛔ **2026-09-07 更正：那句是假的 —— 本表第三處被抓到的『唯一 caller』"
         "全稱句**（**有意識的更正，不是漏刪**；決策者：AI 總管，依獨立稽核實測）。"
         "實測全 repo（排除 `tests/`／`scripts/`）另有兩個呼叫端："
         "`ui/tab2_single_fund.py` 與 `ui/tab3_portfolio.py`，"
         "本函式因此**經 ③ 與 ④ 仍然可達、並沒有從 App 消失**。"
         "⇒ 真正掉的只有上一列那支 **② 專屬的包裝**（`_render_mj_freshness_banner`，"
         "吃 `ok_rows`）。**本列因此是「② 的入口沒了」，不是「這個 banner 沒了」** —— "
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
          "\n   ⚠️ 2026-09-07 起 ~~`已搬 ③`~~ 已拆成兩個**機器驗得動**的標籤，"
          "\n   合法答案：`③ 已到得了`（③ 真的到得了）／`判給 ③（尚未實作）`"
          "（③ 到不了，但有活路徑）／`刻意不接`（具名理由）／`待客戶裁決`／`橋接容器`。"
          "\n   真的還沒有答案 → 標 `未登記缺口` 並寫進 PR 描述，**不要靜默略過**。")
    _bad = {k: v[0] for k, v in DROPPED_WITH_REASON.items() if v[0] not in _DISPOSITIONS}
    assert not _bad, f"處置欄用了未定義的值：{_bad}（合法值：{sorted(_DISPOSITIONS)}）"


#: ③ 的分頁槽名（`app.py` 的 `with tab_research:`）。
#: ⚠️ **刻意不寫死入口函式** —— ③ 隨時可能從 `ui.tab_fund_research` 換成
#: `ui/views/page_03_research.py`；寫死的話那一天守衛會**靜默地驗錯對象**。
_SLOT_PAGE_THREE = "tab_research"


def _live_entries() -> "dict[str, tuple[str, str]]":
    """`app.py` **當下真的掛著**的分頁 → `(module, symbol)`，從原始碼抽，不寫死。

    ⚠️ 這支存在的理由與整個 2026-09-07 事故同源：**任何寫死的「現況」都會過期，
    而過期不會有人通知你**。分頁槽（`with tab_health:`）是 `app.py` 自己的結構，
    改接線一定會動到它 ⇒ 拿它當真相源，守衛就會自己跟上。
    """
    _tree = ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    _bind: dict[str, tuple[str, str]] = {}
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.ImportFrom) and _n.module and not _n.level:
            for _a in _n.names:
                _bind[_a.asname or _a.name] = (_n.module, _a.name)
    _out: dict[str, tuple[str, str]] = {}
    for _n in ast.walk(_tree):
        if not isinstance(_n, ast.With):
            continue
        for _it in _n.items:
            _ce = _it.context_expr
            if not (isinstance(_ce, ast.Name) and _ce.id.startswith("tab_")):
                continue
            for _c in ast.walk(_n):
                if (isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)
                        and _c.func.id.startswith("render_") and _c.func.id in _bind):
                    _out[_ce.id] = _bind[_c.func.id]
    return _out


def _rows_labelled(disposition: str) -> "list[str]":
    return sorted(_k for _k, _v in DROPPED_WITH_REASON.items() if _v[0] == disposition)


def test_a_page_three_label_must_be_reachable_from_page_three():
    """⭐ **2026-09-07 新增（其一）：標「③ 已到得了」的，③ 就必須真的到得了。**

    **這一條與它的雙生條，就是 2026-09-07 事故的解藥。**
    事故不是「誰漏接了六支」，是 ~~`已搬 ③`~~ 這個標籤**含混**
    （「移轉完成」vs「線框判給」兩種讀法），而**沒有任何機器規則在驗它是哪一種** ——
    於是八筆裡有六筆連 ③ 都到不了，本檔照樣全綠。

    ⛔ **fail-closed 的兩個方向都要有**：本條擋「說到得了、其實到不了」；
       :func:`test_a_pending_label_must_still_have_a_live_path` 擋反方向。
       **只有一個方向的規則，含混就會往沒被守的那一邊漂。**

    ⚠️ **③ 的入口從 `app.py` 抽，不寫死**（見 :func:`_live_entries`）——
    ③ 哪天換成 `ui/views/page_03_research.py`，本條自動跟著換對象。

    **突變驗證（2026-09-07 實跑）**：把任一筆 `判給 ③（尚未實作）` 改標成
    `③ 已到得了` → **本條轉紅並指名那一筆**；還原 → 轉綠。
    """
    _rows = _rows_labelled("③ 已到得了")
    assert _rows, (
        "沒有任何一筆標 `③ 已到得了` —— 本條會退化成恆綠。\n"
        "⛔ 若真的一筆都不剩，請連同本條一起改，不要讓它空掃。")

    _entries = _live_entries()
    _e3 = _entries.get(_SLOT_PAGE_THREE)
    assert _e3, (
        f"`app.py` 的 `with {_SLOT_PAGE_THREE}:` 抽不到 render 入口 —— "
        "掃描輸入是空的，本條結論沒有意義。")
    _reach3 = _reach(_e3)
    assert len(_reach3) > 50, f"③ 可達集合只有 {len(_reach3)} 個 —— walker 可能壞了。"

    _bad = []
    for _k in _rows:
        _m, _, _sym = _k.partition("::")
        if _resolve(_m, _sym) not in _reach3:
            _bad.append(_k)
    assert not _bad, (
        f"下列 {len(_bad)} 筆標著「③ 已到得了」，但從 ③ 的活入口 "
        f"`{_e3[0]}::{_e3[1]}` **到不了**：\n  " + "\n  ".join(_bad)
        + "\n⛔ 這正是 2026-09-07 事故的形狀：**標籤說在 ③，實際上 ③ 沒有。**"
          "\n   ③ 真的還沒實作 → 改標 `判給 ③（尚未實作）`（那一條會驗它還有沒有活路徑）。"
          "\n   ⛔ 不要為了讓本條變綠就把它從表上刪掉 —— 那才是讓它無聲消失。")

    # 負對照：虛構符號不得解析（沒有這行，上面的 `not in` 可能只是恆真）。
    assert _resolve("ui.helpers.holdings", "render_bogus_zzz_9999") is None


def test_a_pending_label_must_still_have_a_live_path():
    """⭐ **2026-09-07 新增（其二）：標「判給 ③（尚未實作）」的，必須還有一條活路徑。**

    **客戶 2026-09-07 架構原則（本條的法源）**：新 UI 一律以**新增 Tab 並行掛載**，
    **舊 Tab 一律保留不動**，直到客戶親自驗收新頁通過才下令刪除舊版。
    ⇒ 「③ 還沒實作」**不等於**「使用者看不到」—— 它應該經**保留的舊 ②**還看得到。
    **本條就是在釘那個「應該」。**

    **兩個方向都驗（缺一就會往沒被守的那邊漂）**：

    1. **不得從 ③ 到得了** —— 到得了就該改標 `③ 已到得了`。
       （這一半讓兩個標籤**互斥**，含混無處可去。）
    2. **必須從「活路徑」到得了** —— 活路徑 ＝ `app.py` 當下掛著的分頁
       **∪** 保留不動的舊 ②（:data:`OLD_ENTRY`）。

    ⚠️ **據實揭露一個本條刻意不驗的東西（不要讀成它已經被保證了）**：
    本條**不驗舊 ② 有沒有掛在 `app.py` 上**。理由不是漏掉，是那個斷言**兩邊都會錯** ——
    寫「必須掛著」則在舊 ② 接回之前恆紅，寫「必須沒掛」則接回當天恆紅。
    **舊 ② 的接回是另一組的 PR，本批不動 `app.py`。**
    ⇒ 若舊 ② 尚未接回，這幾塊對使用者**仍然是看不見的**；
      本條保證的是「**路徑存在且完好**」，不是「**它現在被掛出來了**」。
      掛載那一面由 :func:`test_app_mounts_the_new_health_view` 與另一組的 PR 負責。
    **這一段刻意寫在守衛裡，不是只寫在 PR 描述裡** —— PR 描述沒有人會回頭讀。

    **突變驗證（2026-09-07 實跑，兩條軸各一次）**：
    (a) 把任一筆改標成 `③ 已到得了` → **另一條**轉紅（互斥那一半）；
    (b) 從舊 ② 拿掉 `_render_low_base_screener(ok_rows)` 那個呼叫
        （**暫時**改 `ui/tab_fund_grp_health.py`，測完還原並 `cmp` 逐位元組比對）
        → **本條轉紅並指名那一筆**；還原 → 轉綠。
    """
    _rows = _rows_labelled("判給 ③（尚未實作）")
    assert _rows, (
        "沒有任何一筆標 `判給 ③（尚未實作）` —— 本條會退化成恆綠。\n"
        "⛔ 若 ③ 真的全部實作完了，請連同本條一起改，並把那幾筆改標 `③ 已到得了`。")

    _entries = _live_entries()
    assert _entries, "`app.py` 一個分頁槽都抽不到 —— 掃描輸入是空的。"
    _e3 = _entries.get(_SLOT_PAGE_THREE)
    assert _e3, f"抽不到 ③ 的入口（`with {_SLOT_PAGE_THREE}:`）。"
    _reach3 = _reach(_e3)

    #: 活路徑 ＝ `app.py` 當下掛著的每一頁 ＋ 保留不動的舊 ②（雙軌）。
    _paths: "dict[str, set[tuple[str, str]]]" = {
        f"app.py::{_slot}": _reach(_ent) for _slot, _ent in sorted(_entries.items())}
    _paths[f"保留的舊 ②（{OLD_ENTRY[0]}）"] = _reach(OLD_ENTRY)
    for _label, _set in _paths.items():
        assert len(_set) > 20, f"路徑「{_label}」可達集合只有 {len(_set)} 個 —— walker 可能壞了。"

    _should_be_moved, _orphaned = [], []
    for _k in _rows:
        _m, _, _sym = _k.partition("::")
        _tgt = _resolve(_m, _sym)
        assert _tgt is not None, f"`{_k}` 解析不到 —— 它是不是被改名或刪掉了？"
        if _tgt in _reach3:
            _should_be_moved.append(_k)
            continue
        if not any(_tgt in _set for _set in _paths.values()):
            _orphaned.append(_k)

    assert not _should_be_moved, (
        f"下列 {len(_should_be_moved)} 筆標著「判給 ③（尚未實作）」，"
        "但 ③ **其實已經到得了**：\n  " + "\n  ".join(_should_be_moved)
        + "\n⛔ 改標 `③ 已到得了` —— **一張說謊的對照表比沒有表更糟**，"
          "\n   而且這個方向的謊會讓 ③ 的實作被誤判成「還沒做」。")

    assert not _orphaned, (
        f"下列 {len(_orphaned)} 筆標著「判給 ③（尚未實作）」，"
        "但**沒有任何一條活路徑到得了它們** —— 也就是它們在整個 App 消失了：\n  "
        + "\n  ".join(_orphaned)
        + "\n\n已檢查的路徑：\n  " + "\n  ".join(sorted(_paths))
        + "\n\n⛔ 這正是 2026-09-07 事故本身。客戶 2026-09-07 原則："
          "**舊 Tab 一律保留不動**，直到客戶驗收新頁才刪 —— "
          "\n   所以正解是**把舊 ② 那條路留住／接回**，"
          "\n   ⛔ **不是**把它們硬塞進新 ②（線框判給 ③，塞進 ② 反而牴觸核准線框），"
          "\n   ⛔ **也不是**把它們從表上刪掉。")

    # 負對照：虛構符號不得命中任何一條路徑。
    _bogus = _resolve("ui.tab_fund_grp_health", "_render_bogus_zzz_9999")
    assert _bogus is None and not any(_bogus in _s for _s in _paths.values())


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
