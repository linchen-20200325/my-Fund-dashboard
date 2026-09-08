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
  📌 **2026-09-07 狀態更新（不是更正 —— 上句是條件句，它在當時與現在都為真）**：
  **那個條件已經達成** —— #814 已把舊 ② 接回 `app.py` 的 `tab_health`
  （新 View 改掛 `tab_preview_health`，雙軌並行），**所以那六塊現在看得到了**。
  ⛔ 但**本條的射程一個字都沒變**：它仍然只保證「路徑存在且完好」；
  「它現在被掛出來了」由 :func:`test_app_mounts_the_new_health_view` 守。
  ⚠️ 加這一句的理由：上句雖然是條件句，**讀者很容易只讀到後半段**
  （本批就有一段引用它時把它當成「目前不可見」的證據）。
* :func:`_sinks` 是**名字比對**（`ast.walk`，不看分支、不看可達性、不看引數）——
  它會**誤報**（`EXCEPTIONS.md §8.3.P` 的 `P-SINKGRAIN-1` 就是一個實證）。
  本檔用它做的是**差集**，兩邊同一把尺，偽陽性在相減時會抵銷。
"""
from __future__ import annotations

import ast
import pathlib
import re
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
#: ⛔⛔ **先讀這一段再讀表 —— 這張表的「敘述欄」不是機器產生的，它會說謊。**
#:
#: **處置欄（第一格）有機器在守**：`test_every_dropped_renderer_has_a_named_disposition`
#: 驗它是不是合法值，`test_a_page_three_label_must_be_reachable_from_page_three` /
#: `test_a_pending_label_must_still_have_a_live_path` /
#: `test_an_intentional_label_must_declare_where_it_still_lives` 驗它與可達性一致。
#: **但敘述欄（第二格）是人手寫的散文，機器只驗得動其中極小一塊**
#: （目前只有「唯一 caller 是 X」這一種句型，見
#: :func:`test_a_sole_caller_claim_must_actually_be_sole`）。
#:
#: **歷史紀錄（2026-09-07，同一天）：本表的標籤與敘述已被抓到 7 處與實際不符**
#: （**其中第 7 處翻面兩次**，見表中 `7b` —— 刻意不計成「第 8 處」，
#: 它是同一列的同一句話被同一個外因推翻第二次，不是新發現的一處）。
#: **⚠️ 這是「已知 7 處」，不是「已全部更正」，更不是窮舉** ——
#: 已更正的是這幾處，**沒有人查過有沒有下一處**，本檔也不宣稱沒有。
#:
#: ==== ================================================== ==================================
#: #    被抓到的不符                                         誰、用什麼切法抓到
#: ==== ================================================== ==================================
#: 1-2  八筆 ~~`已搬 ③`~~ 裡有六筆連 ③ 都到不了               獨立稽核，AST 遞移閉包重掃
#: 3    `render_mj_freshness_banner`「唯一 caller」是假的      獨立稽核，全 repo caller 掃描
#: 4    `_render_health_summary`「另三格」與自己的列舉矛盾      實測舊 ② 畫的是 5 格 KPI
#: 5    `_render_pairs_ui`「唯一 caller」是假的（實測 2 支）    獨立稽核；而且 `CLAUDE.md`
#:                                                          的 `P-SINKGRAIN-1` **早就寫著**
#: 6    `_render_pairs_body`「下游：同上」錯兩層（實測 2 支，   同上
#:      且直接 caller 根本不是上一列那支）
#: 7    `_MOVED`「它**現在**看得見，靠的是雙軌」是假的 ——      獨立稽核；而且**本檔開頭
#:      當時舊 ② 沒掛在 `app.py` 上，那六塊不可見              「不守什麼」那一段早就寫著**
#: 7b   **同一列的更正本身，幾分鐘後又翻面** —— 它寫「五個      獨立稽核（第二輪）；
#:      分頁槽」「連 import 都沒有」「畫面上看不到」，          **成因與 1~7 完全不同**
#:      #814 合併後三句全假                                  （見下方 ⚠️）
#: ==== ================================================== ==================================
#:
#: ⚠️ **六處的共通點，比六處本身重要**：**每一次都是「只查了被點名的那幾筆」。**
#:    第 1-2 處修完，沒有人拿同一把尺去掃第 3 處；第 3-4 處修完，
#:    沒有人拿同一把尺去掃 `刻意不接` 那一族（**它當時零機器守衛**）。
#:    第 5 處尤其刺眼：**推翻它的證據一直躺在同一份 `CLAUDE.md` 裡，
#:    而且就在上一列自己引用的那一段**（`P-SINKGRAIN-1` 逐字寫著
#:    「傳 `True` 的是批次那一支 `render_rotation_section_from_df`」）。**沒有人回頭讀。**
#:    **第 7 處更近**：推翻它的那句話就在**本檔開頭**（「不守什麼」段），
#:    離它不到三百行。**docstring 誠實、表格誇大，而沒有人交叉讀。**
#:
#: ⚠️ **`7b` 的成因與 1~7 完全不同，不要混為一談** ——
#:    1~7 全是「**沒有人回頭讀**」；**`7b` 是「寫的時候是真的，外面的世界變了**」：
#:    `#814`（雙軌並行）在本批交件後**幾分鐘**合併，一次推翻三項前提。
#:    ⇒ **教訓不是「要更小心」，是「時效性宣稱要把條件寫進句子本身」** ——
#:    `7b` 那三句是**無條件的現在式事實**，旁邊那句「截至本次修改」的時間戳
#:    **保護不了它們**。對照本檔開頭「不守什麼」那一段：它用的是**條件句**
#:    （「在那之前…」），所以 #814 之後**它仍然為真**，只需要補一則狀態更新。
#:    **同一件事、兩種寫法，一種要改、一種不用 —— 差別只在有沒有把條件寫進去。**
#:    ⚠️ 而且 `7b` 這一輪**CI 三條 lane 全綠、本檔 12 條守衛全綠** ——
#:    **散文不是斷言，綠燈不保證文件為真。**
#:
#: ⚠️ **第 7 處還帶出另一件事：修這張表的那一批自己也會犯同一個病。**
#:    本輪（2026-09-07 第二輪）在守衛 docstring、commit 訊息與 PR 描述**三個永久紀錄**裡
#:    寫過「三句原話原封放回去，三次全轉紅」—— **那是假的**：
#:    #3／#6 的**原始措辭**沒有反引號識別字，:func:`test_a_sole_caller_claim_must_actually_be_sole`
#:    **結構上看不見它們**（實測 🟢）。被展示成「轉紅」的 #3 是**改寫過的句子**。
#:    **一條在修『說謊的表』的改動，自己說了謊 —— 而且說在守衛自己的 docstring 上。**
#:    ⇒ 已就地改成誠實版（見該守衛 docstring 的射程表）。
#:
#: ⇒ **動這張表的任何一列時，把同一把尺對全部同類列重跑一次**
#:   （`EXCEPTIONS.md §8.2.A.1` 驗證段 ④ 的既有教訓：「只改被點名的那一條 ＝ 沒改」）。
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
#: ══ `刻意不接` 的**可達性標記** —— 三選一，機器逐列比對 ══════════════════════
#:
#: ⚠️ **為什麼要有這三個字串（這一段是 2026-09-07 第五／第六處不符的解藥）**：
#: `刻意不接` 這一族在本檔**原本零機器守衛** —— 上面兩條新規則只管
#: `③ 已到得了` 與 `判給 ③（尚未實作）`，`刻意不接` **完全在射程外**。
#: 於是它底下兩句「唯一 caller 是 X」的**假全稱句**活了整整一輪，**CI 一次都沒紅過**。
#:
#: **假話本身不是最糟的，糟的是它把因果講反**：「下游：唯一 caller 是 X」讀起來像
#: 「X 被 ② 移出 ⇒ 這一支跟著從 App 消失」。**實際上它們經 ③／④ 都還活著。**
#: 與 `render_mj_freshness_banner` 完全同型：**掉的是 ② 的入口，不是那個東西本身**——
#: 而這兩種情況的**補法完全不同**（前者只要接回入口，後者要重做一個東西）。
#:
#: ⇒ 所以標記釘的不是「理由寫得好不好」（機器判不動），而是**一個可量測的事實**：
#: **除了保留的舊 ② 以外，還有沒有活的分頁到得了它。**
#:
#: ⛔ **「活路徑」的定義刻意排除舊 ②**（含日後舊 ② 被接回成為某個分頁槽的情形）——
#: 否則舊 ② 一接回，六列標記會同時翻面，而那**不是**可達性真的改變了。
_STILL_LIVES: str = "［其他活路徑：有］"
#: 只剩保留的舊 ② 到得了 ⇒ **② 的入口沒了，靠雙軌還看得見**。
_ONLY_OLD_TWO: str = "［其他活路徑：無（僅保留的舊 ②）］"
#: 全 App 都到不了 ⇒ 這是**真的移除**。允許，但**必須明講**，不准用「刻意不接」四個字含混過去。
_GONE_EVERYWHERE: str = "［其他活路徑：無（全 App 都到不了）］"

_LIVE_PATH_TAGS: "tuple[str, ...]" = (_STILL_LIVES, _ONLY_OLD_TWO, _GONE_EVERYWHERE)

_MOVED: str = (
    "~~已搬 ③~~ → **判給 ③（尚未實作）**（2026-09-07 就地更正，"
    "**有意識的更正，不是漏刪**；決策者：AI 總管，依獨立稽核實測）。"
    "**實測：③ 的活入口到不了它，尚未掛載的新 ③ view 也到不了。** "
    "線框 §04 判給 ③ 是**真的**，被推翻的是「已搬」二字隱含的『③ 已經有了』。"
    "~~⚠️ **它現在看得見，靠的是雙軌**：…本支經**保留的舊 ②**仍到得了。~~ "
    "~~⛔ 2026-09-07 更正：『現在看得見』是假的 —— `app.py` 的**五個**分頁槽裡沒有舊 ②，~~"
    "~~`render_fund_grp_health_tab` **連 import 都沒有**；**在那之前，畫面上看不到**。~~ "
    "⛔ **2026-09-07 同日第二次更正：上面那段（第七處的更正本身）也翻面了。**"
    "**有意識的更正，不是漏刪**（日期 **2026-09-07** · 決策者：**AI 總管**，依獨立稽核實測）。"
    "**它寫下時為真，`#814` 在幾分鐘後合併把三項前提一次推翻** ——"
    "「五個分頁槽」現在是**七**個；「連 import 都沒有」現在**有**；"
    "「畫面上看不到」現在**看得到**（`tab_health` 掛的就是舊 ②）。"
    "⚠️ **那三句是無條件的現在式事實宣稱，"
    "「截至本次修改」那個 hedge 保護不了它們** —— 這是本輪自己踩到的教訓："
    "**時效性寫法要把條件寫進句子本身，不能靠一句時間戳兜底。**"
    "**現行（實測 `origin/main` `c6b4d1b`，本分支已 merge）**：客戶 2026-09-07 原則是"
    "**舊 Tab 原位保留、新 View 並行掛新 Tab**；舊 ② 已接回 `app.py` 的 `tab_health`，"
    "**該條件已達成** ⇒ **本支經保留的舊 ② 在畫面上看得到**，"
    "呼叫圖上的路徑由 `test_a_pending_label_must_still_have_a_live_path` 釘住。"
    "⛔ **但那條守衛保證的仍只有「路徑存在且完好」，不是「它現在被掛出來了」** ——"
    "掛載那一面由 `test_app_mounts_the_new_health_view` 負責（它現在**兩格都釘**："
    "新頁在 `tab_preview_health`、舊 ② 在 `tab_health`，少一格就紅）。"
    "⇒ **本句今天為真是因為那條掛載守衛在守它，不是因為有人記得回來改這裡。**"
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
         "——『回答該買哪一檔而不是哪一檔有問題』。"
         "⚠️ 它**不在** `page_02_health.MOVED_TO_PAGE_03` 裡（那個常數只收 "
         "`render_fund_grp_health_extras` 底下的，而本支住在舊 ② 根檔）—— "
         "**這句仍然成立，2026-09-07 原樣保留**（本批只改標籤，沒有動那個常數）。"
         "~~⭐ 本批新查出。~~（那是 2026-09-07 之前那一批的字，"
         "留著會讓讀者以為它是今天才被發現的。）" + _MOVED),

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
                      "守衛對它是**已知偽陽性**（`EXCEPTIONS.md §8.3.P` 的 `P-SINKGRAIN-1`），"
                      "但偽陽性不是把它接回來的理由，也不是改守衛的理由。"
                      + _STILL_LIVES),
    "ui.helpers.fund_grp_health.rotation::_render_pairs_ui":
        ("刻意不接",
         "~~下游：唯一 caller 是 `render_rotation_section`。~~ "
         "⛔ **2026-09-07 更正：那句是假的 —— 本表第五處被抓到的『唯一 caller』"
         "全稱句**（**有意識的更正，不是漏刪**；決策者：AI 總管，依獨立稽核實測）。"
         "實測全 repo（排除 `tests/`／`scripts/`）呼叫它的有**兩支**："
         "`render_rotation_section` **與 `render_rotation_section_from_df`**。"
         "⚠️ **推翻它的證據一直躺在同一份文件裡**：`EXCEPTIONS.md §8.3.P` 的 "
         "`P-SINKGRAIN-1` 逐字寫著「（傳 `True` 的是批次那一支 "
         "`render_rotation_section_from_df`）」—— 那句話的意思就是"
         "**`render_rotation_section_from_df` 也呼叫本函式**，"
         "而 `P-SINKGRAIN-1` 正是上一列自己引用的那一段。**沒有人回頭讀。**"
         "⚠️ **舊理由不只少算一個 caller，它把因果講反了**（與 "
         "`render_mj_freshness_banner` 同型）：照它讀，`render_rotation_section` "
         "一旦被 ② 移出，本函式就跟著從 App 消失 —— **不會**。"
         "**掉的是 ② 的入口，不是這個東西本身。** 它經 **④ 持倉組合**"
         "（`ui/tab3_portfolio.py::render_portfolio_tab` → `render_rotation_section`）"
         "仍然到得了，機器規則見 "
         "`test_an_intentional_label_must_declare_where_it_still_lives`。"
         "⚠️ **本更正自己的界線，先講清楚，免得變成第七處不符**："
         "第二個 caller `render_rotation_section_from_df` **自己是 production 0 caller**"
         "（它的 docstring 自陳「production 端 `ui/tab_batch_analysis.py` 已不再呼叫它」，"
         "本組實測相符）—— 所以「本函式還活著」**靠的是 ④ 那條線，不是它**。"
         "**兩件事都是真的，但不要混成一句。**"
         + _STILL_LIVES),
    "ui.helpers.fund_grp_health.rotation::_render_pairs_body":
        ("刻意不接",
         "~~下游：同上。~~ ⛔ **2026-09-07 更正：那句是假的，而且錯兩層 —— "
         "本表第六處被抓到的不符**（**有意識的更正，不是漏刪**；"
         "決策者：AI 總管，依獨立稽核實測）。"
         "**第一層**：「同上」指向上一列的 `render_rotation_section`，"
         "但本函式的直接 caller **根本不是它** —— 是 `_render_pairs_ui`。"
         "**第二層**：caller 也不只一支，實測**兩支** —— `_render_pairs_ui` "
         "**與 `render_complementary_explorer_from_df`**（後者直接呼叫本函式，"
         "不經 `_render_pairs_ui`）。"
         "⚠️ **因果同樣講反了**（與 `render_mj_freshness_banner` 同型）："
         "`render_complementary_explorer_from_df` 那條線經 "
         "`ui/tab_batch_analysis.py` 從 **③** 獨立到得了，"
         "**跟 ② 接不接毫無關係**。**掉的是 ② 的入口，不是這個東西本身。**"
         "（原句其餘部分仍然成立，原樣保留：）它就是那個偽陽性寫入槽本身"
         "（`to_csv` 在 `if offer_download:` 內，而 ② 那條委派入口硬編 "
         "`offer_download=False`）。⚠️ 但**另一條入口 "
         "`render_rotation_section_from_df` 硬編 `offer_download=True`** ——"
         "「委派入口硬編 False」只對 ② 那一條成立，不是對全部 caller 成立。"
         + _STILL_LIVES),
    "ui.helpers.story_nav::render_flow_nav":
        ("刻意不接", "新 View 一律只畫 `render_story_nav`，不畫四層流程導覽 —— "
                      "① `page_01_macro` 與 ⑤ `page_05_settings` 已是同樣作法（既有前例，"
                      "非本批發明）。ui/tab1_macro.py 就地註明「render_flow_nav 移除」。"
                      "⚠️ **2026-09-07 就地補測**：本列的「⑤ 已是同樣作法」只對 "
                      "`page_05_settings` **自己的程式碼**成立 —— 它委派的 "
                      "`ui.tab_manage::render_manage_tab` **仍然呼叫** `render_flow_nav`，"
                      "所以 ⑤ 的畫面上其實還看得到它。**本列不改判**（該句字面沒錯），"
                      "但標記如實記載可達性，不讓讀者以為它已經全站絕跡。"
                      + _STILL_LIVES),
    "ui.tab_fund_grp_health::_render_health_table":
        ("刻意不接", "新頁自己畫線框指定的 **9 欄**逐檔體檢表"
                      "（`page_02_health._render_health_table`），不是舊的 48 欄大表。"
                      + _ONLY_OLD_TWO),
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
                      "「另三格」會讓下一個人補完三格就以為結清了。"
                      + _ONLY_OLD_TWO),

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

    ⚠️ **2026-09-07 由雙軌並行改寫：這一格驗的東西從「換掉」變成「兩格都對」。**
    **有意識的政策變更，不是把規則改鬆**（決策者：客戶 2026-09-07
    「舊 ② 保留原位……新 ② 則掛為獨立新 Tab」）。

    **舊斷言**（原地保留、加刪除線，不刪）::

        ~~assert _in_slot == ["render_holdings_health"]~~

    **舊斷言的理由一個字都沒有被推翻** —— 它要防的是「新頁算對了卻沒接出去」
    （本 repo 的既有病）。下面**兩條**斷言接的是同一根針，而且**多釘了一格**：
    新頁必須掛在 `tab_preview_health`（沒接出去 → 紅），
    **舊頁必須還在 `tab_health`**（被覆蓋掉 → 也紅，
    那正是客戶明令禁止的「破壞現有線上正常運作的舊版 Tab」）。
    **被權衡掉的只有「新頁必須佔住 `tab_health` 那一格」這個前提**，
    因為客戶把它改成並行了。

    ⚠️ 只驗 ② 那一格；①③④⑤ 由 `tests/test_ia_kit.py::_SLOT_RENDER` 整表守。
    """
    _app = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "from ui.views.page_02_health import" in _app, (
        "`app.py` 沒有 import 新 ② —— 接線鏈斷在 app.py 這一節。")
    _tree = ast.parse(_app)
    def _renders_in(slot: str) -> list:
        return [
            _c.func.id
            for _n in ast.walk(_tree) if isinstance(_n, ast.With)
            for _it in _n.items
            if isinstance(_it.context_expr, ast.Name)
            and _it.context_expr.id == slot
            for _c in ast.walk(_n)
            if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)
            and _c.func.id.startswith("render_")
        ]

    # ① 新頁真的掛出去了（掛在 [新] 並行預覽那一格）
    assert _renders_in("tab_preview_health") == ["render_holdings_health"], (
        f"`with tab_preview_health:` 呼叫的是 {_renders_in('tab_preview_health')}，應為 "
        "['render_holdings_health'] —— 新頁沒接出去，底下所有證明都是在證一個沒人打開的檔案。")

    # ② ⭐ **舊頁必須還在原位** —— 客戶 2026-09-07 明令舊 Tab 原樣保留。
    #    ⛔ 這一條不可以省：少了它，「把舊頁換掉」這個動作會**靜默通過**，
    #       而那正是本次要撤銷的東西。
    assert _renders_in("tab_health") == ["render_fund_grp_health_tab"], (
        f"`with tab_health:` 呼叫的是 {_renders_in('tab_health')}，應為 "
        "['render_fund_grp_health_tab'] —— 舊 ② 被覆蓋掉了，那是客戶明令禁止的。")
    assert "from ui.tab_fund_grp_health import" in _app, (
        "`app.py` 沒有 import 舊 ② —— 舊分頁的接線鏈斷了。")


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
    📌 **2026-09-07 狀態更新（同檔頭那一段；上句是條件句，兩種世界下都為真）**：
    **#814 已把舊 ② 接回 `tab_health`** ⇒ 那個「若」不再成立，**現在看得到**。
    **本條的斷言與射程一個字都沒改** —— 它守的仍是「路徑存在且完好」。
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


# ══════════════════════════════════════════════════════════════════
# 3｜⭐ 2026-09-07（第二輪）：`刻意不接` 這一族的兩條守衛
#
# **為什麼補這兩條** —— 上面第 8／9 條是 2026-09-07 第一輪的解藥，但它們的射程
# **只有兩個標籤**（`③ 已到得了` / `判給 ③（尚未實作）`）。標 `刻意不接` 的那六列
# **完全在射程外** ⇒ 它底下兩句假的下游敘述（#5 寫「唯一 caller 是
# `render_rotation_section`」、#6 寫「下游：同上」）**CI 一次都沒紅過**，
# 最後是靠人回頭讀 `CLAUDE.md` 才撿到。
#
# ⚠️ **這張表今天被三組人各抓到一批，每一組都只查了自己被點名的那幾筆。**
#    那不是誰不用心 —— **是沒有機器在守。**
# ══════════════════════════════════════════════════════════════════
def _strip_struck(text: str) -> str:
    """把 `~~…~~` 的**已撤回**字串挖掉，只留還在生效的敘述。

    ⚠️ 本檔的慣例是「舊表述加刪除線保留、不刪」（`CLAUDE.md` 全域慣例）——
    所以**不挖掉劃線段，任何規則都會被自己保留下來的舊錯誤觸發**，
    那會逼下一個人為了讓 CI 變綠而去**刪掉歷史**，正好與那條慣例相反。
    """
    return re.sub(r"~~.*?~~", "", text, flags=re.S)


#: 「唯一 caller 是 `X`」這一類**全稱句**。容忍「唯一的 caller」「唯一 production caller」。
_SOLE_CALLER_RE = re.compile(
    r"唯一\s*(?:的)?\s*(?:production\s+)?caller\s*(?:是|為)\s*`([A-Za-z_][A-Za-z0-9_.]*)`")


def _sole_caller_claims(text: str) -> "list[str]":
    """從**未撤回**的敘述裡抽出所有「唯一 caller 是 `X`」宣稱，回傳 `X` 清單。"""
    return _SOLE_CALLER_RE.findall(_strip_struck(text))


def _callers(target: "tuple[str, str]") -> "set[tuple[str, str]]":
    """全 repo（**已排除 `tests/` 與 `scripts/`**，見 :func:`_index`）誰參照 `target`。

    回傳 `(module, 頂層符號名)`。與 :func:`_reach` **同一把尺**：
    「呼叫 ＋ 裸參照」都算邊 —— 本 repo 的委派慣例 `safe_section("標籤", _render_x)`
    是裸參照，只跟 `ast.Call` 會嚴重低估（#805 的教訓）。

    ⛔ **射程外，照實列**（不要把本函式的沉默讀成「沒有別的 caller」）：
    * **模組層**的參照（`_FN = render_x` 寫在任何 def 之外）——本函式只走頂層定義底下。
    * `getattr` / 字典派發 / 字串組出來的動態呼叫（同 :func:`_reach` 的射程外）。
    * `tests/` 與 `scripts/` **刻意不算**：本表描述的是 **production 可達性**。
    """
    _out: set[tuple[str, str]] = set()
    for (_m, _top), _node in _NODES.items():
        if (_m, _top) == target:
            continue
        for _n in ast.walk(_node):
            _t = None
            if isinstance(_n, ast.Name) and isinstance(_n.ctx, ast.Load):
                _t = _resolve(_m, _n.id)
            elif (isinstance(_n, ast.Attribute) and isinstance(_n.ctx, ast.Load)
                  and isinstance(_n.value, ast.Name)):
                _am = _ALIAS.get(_m, {}).get(_n.value.id)
                if _am and _am in _MODS and _n.attr in _DEFS.get(_am, ()):
                    _t = (_am, _n.attr)
            if _t == target:
                _out.add((_m, _top))
                break
    return _out


def test_a_sole_caller_claim_must_actually_be_sole():
    """⭐ **2026-09-07（第二輪）：表上任何「唯一 caller 是 `X`」，都要真的只有 X。**

    ⛔⛔ **先讀這一段：本條只看得見一種寫法，它不是那兩處不符的「解藥」。**

    :data:`_SOLE_CALLER_RE` 要求「唯一 caller 是」後面接一個**反引號包住的識別字**。
    下面是**已知的**原始措辭（逐字取自 `c321c0a`）與逐句實測落點 ——
    **這張表是實跑出來的，不是推論**（把刪除線拿掉讓原話重新生效，逐句各跑一次）：

    ==== ====================================== ================================ ======
    #    原始措辭（逐字）                          本條看得見嗎                        結果
    ==== ====================================== ================================ ======
    #1   下游：唯一 caller 是 `_render_             ✅ 有反引號識別字                  🔴 紅
         holdings_block`（已搬 ③）。
    #2   下游：唯一 caller 是 `_render_per_         ✅ 有反引號識別字                  🔴 紅
         fund_news_expanders`（已搬 ③）。
    #5   下游：唯一 caller 是 `render_              ✅ 有反引號識別字                  🔴 紅
         rotation_section`。
    #3   下游：唯一 caller 是**上一列那支包裝**。    ⛔ **沒有反引號識別字**            🟢 綠
    #6   下游：**同上**。                          ⛔ 連「唯一 caller」都沒出現        🟢 綠
    ==== ====================================== ================================ ======

    ⇒ **分類敘述（⛔ 不是窮舉）**：本條攔得住的是**帶反引號識別字**的那一類
    （已知 3 句，全紅）；**看不見**的是**不含反引號識別字**的那一類
    （已知 2 句，全綠）。**兩類都不宣稱窮舉** —— 「`c321c0a` 上只有這 5 句」
    取決於「有沒有漏看」，**本檔不作此宣稱**。

    ⚠️ **這張表自己就被抓到過一次低估**（2026-09-07，獨立稽核）：
    上一版只列 4 句、漏掉 **#2 `render_holdings_diag`**，於是把守備範圍寫成
    ~~「四句原話裡只攔得住兩句」~~ —— **實測是 3 紅 / 2 盲**。
    **有意識的更正，不是漏刪**（決策者：AI 總管，依獨立稽核實測）。
    ⚠️ **誤差方向是低估自己，不是誇大** —— 但**低估一樣要改**：
    一個把自己講得比實際弱的射程表，會讓下一個人去重造一條已經存在的規則。
    ⚠️ #3 之所以在別處被描述成「回溯轉紅」，是因為那裡引的是**改寫成
    ``唯一 caller 是 `_render_mj_freshness_banner`。`` 之後的句子**，不是原話。
    **改寫後才紅 —— 那證明的是正則會動，不是它涵蓋得到原始措辭。**

    ⛔ **所以不要把本條讀成「這個形狀已經有機器在守」** —— 只有**帶反引號識別字**的
    那一種寫法有。「同上」「上一列那支」「僅有的 caller 是 …」這些**都沒有**，
    下一處不符很可能就長成它們的樣子。**（射程外的規避寫法另見下方 ⛔ 段。）**

    **本條實際擋得住的**：`_render_pairs_ui` 那種寫法 —— 寫「唯一 caller 是
    `render_rotation_section`」而實測有兩支（另一支 `render_rotation_section_from_df`）。

    ⛔ **最刺眼的一點，寫在守衛裡而不是只寫在 PR 描述裡**（PR 描述沒有人會回頭讀）：
    推翻第一句的證據**一直躺在同一份文件裡** —— `EXCEPTIONS.md §8.3.P` 的
    `P-SINKGRAIN-1` 逐字寫著「（傳 `True` 的是批次那一支
    `render_rotation_section_from_df`）」，而 `P-SINKGRAIN-1` **正是上一列自己引用的那一段**。
    **沒有人回頭讀。**

    ⚠️ **本條對「劃掉的舊表述」視而不見**（:func:`_strip_struck`）——
    本檔慣例是舊表述加刪除線保留，不挖掉的話規則會被自己保留的歷史觸發。

    ⛔ **射程外，照實列（登記，不修）**：下列寫法本條**一律看不見** ——
    「下游：同上」「唯一 caller 是**上一列那支**」「**僅有的** caller 是 `X`」
    「caller **只有** `X` 一支」，以及任何不用反引號標識別字的講法。
    **這不是「還沒做」，是「本條的形狀就是這樣」** ——
    想涵蓋它們要換一種驗法（例如強制敘述用結構化欄位而不是散文），不是把正則加寬。

    ⚠️ **正對照在下面就地做**（沒有它，本條在表上零宣稱時會退化成恆綠）。
    """
    # ── 正對照 ①：抽取器看得見一個合成宣稱 ──────────────────────────
    _fixture = "下游：唯一 caller 是 `render_rotation_section`。"
    assert _sole_caller_claims(_fixture) == ["render_rotation_section"], (
        f"抽取器看不見最直白的宣稱：{_sole_caller_claims(_fixture)} —— 本條等於恆綠。")
    # ── 正對照 ②：抽取器 ＋ 掃描器合起來真的判得出「這句是假的」──────
    _probe = _callers(("ui.helpers.fund_grp_health.rotation", "_render_pairs_ui"))
    assert {_s for _m, _s in _probe} != {"render_rotation_section"}, (
        "合成探針失效：掃描器認為 `_render_pairs_ui` 真的只有一個 caller —— "
        "那正是本輪被推翻的那句話，掃描器若同意它，本條就抓不到同型的下一次。")
    assert len(_probe) >= 2, f"掃描器只看到 {sorted(_probe)} —— 少於實測的兩支。"
    # ── 負對照：劃掉的舊表述不得被抽出；虛構符號零命中 ─────────────
    assert _sole_caller_claims("~~" + _fixture + "~~") == [], (
        "劃掉的舊表述也被抽出來了 —— 本檔「舊表述保留不刪」的慣例會逼人刪歷史。")
    assert not _callers(("ui.helpers.fund_grp_health.rotation", "_render_bogus_zzz_9999"))

    # ── 本體：逐列驗 ──────────────────────────────────────────────
    _bad: "list[str]" = []
    for _k, (_disp, _why) in DROPPED_WITH_REASON.items():
        _m, _, _sym = _k.partition("::")
        for _claim in _sole_caller_claims(_why):
            _tgt = _resolve(_m, _sym)
            if _tgt is None:
                _bad.append(f"{_k}：本列的符號解析不到，宣稱無從驗起。")
                continue
            _actual = sorted({_s for _, _s in _callers(_tgt)})
            if _actual != [_claim]:
                _bad.append(
                    f"{_k}\n      宣稱：唯一 caller 是 `{_claim}`"
                    f"\n      實測：{_actual or '（零個）'}")
    assert not _bad, (
        f"下列 {len(_bad)} 筆的「唯一 caller」宣稱與實測不符：\n  "
        + "\n  ".join(_bad)
        + "\n⛔ 這種句子最貴的地方不是少算一個 caller，是**它把因果講反** —— "
          "\n   「下游：唯一 caller 是 X」讀起來像「X 被 ② 移出 ⇒ 這支跟著從 App 消失」，"
          "\n   而實際上它經 ③／④ 還活著。**掉的是 ② 的入口，不是那個東西本身。**"
          "\n   兩者的補法完全不同：前者接回入口就好，後者要重做一個已經存在的東西。"
          "\n⛔ 不要為了變綠就把宣稱刪掉 —— 改成**實測的樣子**，舊表述加刪除線保留。")


def test_an_intentional_label_must_declare_where_it_still_lives():
    """⭐ **2026-09-07（第二輪）：標「刻意不接」的，必須據實交代它還活在哪。**

    **這一條補的是一個射程缺口，不是一個新想法。** 第 8／9 條把
    `③ 已到得了` / `判給 ③（尚未實作）` 兩個標籤釘成機器驗得動的東西，
    但 **`刻意不接` 完全沒被涵蓋** —— 而本輪兩處不符**全部**長在那一族裡。

    **釘什麼**：不是「理由寫得好不好」（機器判不動），是**一個可量測的事實** ——
    **除了保留的舊 ② 以外，還有沒有活的分頁到得了它。** 三選一，逐列比對：

    * :data:`_STILL_LIVES` —— 還有別條活路徑 ⇒ **它沒有從 App 消失**。
    * :data:`_ONLY_OLD_TWO` —— 只剩保留的舊 ② ⇒ **② 的入口沒了，靠雙軌還看得見**。
    * :data:`_GONE_EVERYWHERE` —— 全 App 到不了 ⇒ **真的移除**，允許但必須明講。

    ⛔ **「活路徑」刻意排除舊 ②**（含日後舊 ② 被接回成為某個分頁槽的情形），
       否則舊 ② 一接回六列會同時翻面，而那**不是**可達性真的改變了。

    ⛔ **本條守不到什麼，照實列（不要讀成「這一族已經證完了」）**：
    * 它驗**可達性**，**不驗理由文字對不對**。一列可以掛對標記、理由整段瞎編。
      理由那一半由 :func:`test_a_sole_caller_claim_must_actually_be_sole` 接手
      **一種**句型（「唯一 caller 是 X」），**其餘句型仍然零守衛**。
    * 它是**呼叫圖**可達，**不是**「使用者螢幕上看得到」。
      本輪就地實測到一個現成例子：`render_flow_nav` 那一列寫
      「⑤ `page_05_settings` 已是同樣作法」——`page_05_settings` **自己的程式碼**
      確實沒畫它，但它委派的 `ui.tab_manage::render_manage_tab` **仍然呼叫** ——
      **圖上到得了，畫面上也真的看得到**。兩者這次剛好一致，**下次不保證**。
    * :func:`_reach` 的既有射程外（`getattr` / 字典派發 / 字串組出來的呼叫）照舊。

    **突變驗證（2026-09-07 實跑，逐列各一次）**：把任一列的標記換成另外兩個之一
    → **本條轉紅並指名那一列、印出實測值**；還原 → 轉綠。
    """
    _rows = _rows_labelled("刻意不接")
    assert _rows, (
        "沒有任何一筆標 `刻意不接` —— 本條會退化成恆綠。\n"
        "⛔ 若真的一筆都不剩，請連同本條一起改，不要讓它空掃。")

    _entries = _live_entries()
    assert _entries, "`app.py` 一個分頁槽都抽不到 —— 掃描輸入是空的，本條結論沒有意義。"
    _old_tgt = _resolve(*OLD_ENTRY)
    assert _old_tgt, f"舊 ② 入口解析不到：{OLD_ENTRY}"
    #: 「其他活路徑」＝ `app.py` 掛著的分頁，**扣掉**掛的是舊 ② 的那一格。
    _other: "dict[str, set[tuple[str, str]]]" = {
        f"app.py::{_slot}": _reach(_ent)
        for _slot, _ent in sorted(_entries.items())
        if _resolve(*_ent) != _old_tgt}
    assert _other, "扣掉舊 ② 之後一條活路徑都不剩 —— 掃描輸入是空的。"
    for _lbl, _set in _other.items():
        assert len(_set) > 20, f"路徑「{_lbl}」可達集合只有 {len(_set)} 個 —— walker 可能壞了。"
    _old_reach = _reach(OLD_ENTRY)
    assert len(_old_reach) > 50, f"舊 ② 可達集合只有 {len(_old_reach)} 個 —— walker 可能壞了。"

    _bad: "list[str]" = []
    for _k in _rows:
        _m, _, _sym = _k.partition("::")
        _tgt = _resolve(_m, _sym)
        assert _tgt is not None, f"`{_k}` 解析不到 —— 它是不是被改名或刪掉了？"
        _hit = sorted(_lbl for _lbl, _set in _other.items() if _tgt in _set)
        _want = (_STILL_LIVES if _hit
                 else _ONLY_OLD_TWO if _tgt in _old_reach
                 else _GONE_EVERYWHERE)
        #: ⚠️ **走 `_strip_struck`，與守衛 1 同一把尺**（2026-09-07 稽核 N1 補）。
        #: 少了它會兩個方向同時壞掉，**而且反方向更痛**：
        #: (a) 把標記整個包進 `~~…~~`（＝已撤回）仍算數 → **該紅不紅**；
        #: (b) 照本 repo「舊表述劃線保留 ＋ 新表述」的慣例更正一列標記時，
        #:     會被數成**兩個**標記 → **恆紅，逼下一個人刪掉歷史** ——
        #:     那正是 :func:`_strip_struck` 自己寫著要避免的事。
        #: **兩種都已實測**（見本批 PR 描述），修法就是這一行。
        _why = _strip_struck(DROPPED_WITH_REASON[_k][1])
        _found = [_t for _t in _LIVE_PATH_TAGS if _t in _why]
        if len(_found) != 1:
            _bad.append(f"{_k}\n      標記：{_found or '（一個都沒有）'}"
                        f"\n      應為（實測）：{_want}"
                        f"\n      實測其他活路徑：{_hit or '（無）'}")
        elif _found[0] != _want:
            _bad.append(f"{_k}\n      標記：{_found[0]}"
                        f"\n      實測應為：{_want}"
                        f"\n      實測其他活路徑：{_hit or '（無）'}"
                        f"\n      舊 ② 到得了：{_tgt in _old_reach}")
    assert not _bad, (
        f"下列 {len(_bad)} 筆 `刻意不接` 的可達性標記與實測不符：\n  "
        + "\n  ".join(_bad)
        + f"\n\n合法標記（三選一，恰好一個）：\n  " + "\n  ".join(_LIVE_PATH_TAGS)
        + "\n\n⛔ 這一族在 2026-09-07 第一輪之後**仍然零守衛**，"
          "\n   於是兩句『唯一 caller 是 X』的假話活了整整一輪、CI 一次都沒紅過。"
          "\n   標記存在的意義是：**「② 不接它」與「它從 App 消失了」是兩件事**，"
          "\n   而含混會讓下一個人去重做一個已經存在的東西。")

    # 負對照：虛構符號不得命中任何一條路徑。
    _bogus = _resolve("ui.helpers.fund_grp_health.rotation", "_render_bogus_zzz_9999")
    assert _bogus is None and not any(_bogus in _s for _s in _other.values())


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
