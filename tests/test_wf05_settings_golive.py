"""⑤ 切換上線的兩道靜態守衛 —— **接線** ＋ **寫入面**。

本檔為什麼獨立存在（不併進 `tests/test_wf05_settings_skeleton.py`）
------------------------------------------------------------------
那一份用 **AppTest 真的渲染**，需要 streamlit runtime；本檔**純 AST，不 import
被測模組、不需要 streamlit**。分開的好處是具體的：streamlit 哪天在 CI 裝不起來，
那一份會整檔 error，而本檔照跑 —— **接線與寫入面這兩件事不該跟 runtime 綁在一起**。

守什麼
------
1. :func:`test_app_mounts_the_new_settings_view` —— `app.py` 的 ⑤ 真的掛新 View。
2. :func:`test_the_new_page_adds_no_write_surface` —— 切換**沒有**把任何新的
   寫入槽拉進射程（新頁閉包的寫入面 ⊆ 舊 ⑤）。
3. :func:`test_the_page_itself_writes_nothing` —— 被測檔**自己**一個寫入 primitive 都沒有。
4. :func:`test_the_scanner_can_actually_see_a_write` —— **正對照**：掃描器不是恆綠。

⛔ **不守什麼（照實列，不要讀成「零寫入已經證完了」）**
--------------------------------------------------------
* **本檔是靜態的**。它回答「切換有沒有把新東西拉進射程」，
  **不回答**「渲染一輪會不會真的寫下去」。後者要執行期哨兵（形狀見
  `tests/test_wf02_health_no_writes.py`），**本檔沒有做，也不宣稱做了**。
* :data:`_WRITE_PRIMITIVES` 是**名字清單，不窮舉**。`getattr(ws, "append_rows")(…)`
  這種非字面呼叫、以及任何不在字表裡的寫法都看不到。
* 靜態 import 閉包 **≠ 呼叫可達**：閉包裡有寫入槽**不代表**渲染會走到它
  （反過來也一樣——本檔不用它下「會不會寫」的結論）。
* **判準刻意沿用 `tests/test_wf02_health_no_writes.py`**（`_PKG_ROOTS` /
  `_WRITE_PRIMITIVES` / `_closure` 的形狀），不自己另發明一把尺
  （`CLAUDE.md §2.1`：同一個事實只准有一個真相源）。
  ⚠️ **代價據實寫**：那邊的字表改了，這邊**不會自動跟上**——
  兩份是**複製**不是 import（跨測試檔 import 會把 streamlit 依賴一起拖進來，
  正是本檔開頭說要避開的那件事）。**登記，不是沒看到。**

⚠️ **第 2 條的基準會消失，屆時要改寫不是刪除**
----------------------------------------------
它拿**舊 ⑤**（`ui/tab_settings_diag.py`）當基準，理由與
`test_wf05_settings_skeleton.py::test_the_new_page_delegates_the_same_set_as_the_old_one_minus_the_lying_block`
相同：舊 ⑤ 是**今天真的跑過生產**的那一份，它就是規格。
⛔ 舊 ⑤ 哪天被下架，本條失去基準 —— **正解是把基準換成一份明列的白名單，不是刪掉本條。**
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
OLD_PAGE = "ui.tab_settings_diag"
NEW_PAGE = "ui.views.page_05_settings"
NEW_SRC = ROOT / "ui" / "views" / "page_05_settings.py"

#: 只跟著本 repo 自己的套件走（外部套件沒有原始碼可掃）。
_PKG_ROOTS = ("ui", "services", "repositories", "shared", "infra")

#: 「這一行真的會寫下去」的方法名。**複製自** `tests/test_wf02_health_no_writes.py`。
#: ⚠️ 刻意**不收** `update` / `write` / `open` / `dump` 這種含糊名字 ——
#:    它們同時是 `dict.update` / `list.clear` 的名字，收進來會在無辜的函式上命中，
#:    那一刻起任何路徑碰到它就是**偽陽性紅燈**。
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


def _module_path(mod: str) -> pathlib.Path | None:
    _p = ROOT / mod.replace(".", "/")
    for _c in (_p.with_suffix(".py"), _p / "__init__.py"):
        if _c.exists():
            return _c
    return None


def _absolutise(mod: str, path: pathlib.Path, node: ast.ImportFrom) -> str:
    """把 `from . import x` / `from ..y import z` 解析成絕對模組名。

    ⚠️ **少了這一段的代價很具體**（② 那一份的實測教訓）：只跟 `level == 0` 的話，
    `repositories/policy/__init__.py` 那一串 `from .v1 import …` 全部斷掉。
    """
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


def _closure(entry: str) -> dict[str, pathlib.Path]:
    """`entry` 的**靜態** import 轉移閉包（只含本 repo 的套件）。"""
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
    """`node` 底下的函式，回傳 `(qualname, node)`；**含 class 方法與巢狀函式**。

    ⚠️ 只走 `tree.body` 的頂層 `FunctionDef` 會漏掉 class 方法 ——
    `repositories/pool_repository.py` 的寫入就是 class 方法（② 那一份的實測教訓）。
    """
    for _ch in ast.iter_child_nodes(node):
        if isinstance(_ch, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield f"{prefix}{_ch.name}", _ch
            yield from _functions(_ch, f"{prefix}{_ch.name}.")
        elif isinstance(_ch, ast.ClassDef):
            yield from _functions(_ch, f"{prefix}{_ch.name}.")


def _write_sinks_in(tree: ast.AST) -> set[tuple[str, str]]:
    """某棵樹裡「函式 → 它呼叫的寫入 primitive」。"""
    return {(_qual, _n.func.attr)
            for _qual, _fn in _functions(tree)
            for _n in ast.walk(_fn)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in _WRITE_PRIMITIVES}


def _sinks(entry: str) -> set[tuple[str, str, str]]:
    """`entry` 閉包內的全部寫入槽 `(module, qualname, primitive)`。"""
    _out: set[tuple[str, str, str]] = set()
    for _mod, _path in _closure(entry).items():
        try:
            _tree = ast.parse(_path.read_text(encoding="utf-8"))
        except SyntaxError:                                   # pragma: no cover
            continue
        for _qual, _prim in _write_sinks_in(_tree):
            _out.add((_mod, _qual, _prim))
    return _out


def test_app_mounts_the_new_settings_view():
    """⑤ 真的掛在 `app.py` 上 —— 而且是**新** View。

    ⛔ 沒有這一條，前面所有「新頁很乾淨」的證明都可能是在證明一個**沒有人打開**
       的檔案（本 repo 的既有病：「算對了沒接出去」）。
    ⚠️ 只驗 ⑤ 那一格；①②③④ 由 `tests/test_ia_kit.py::_SLOT_RENDER` 整表守。
    """
    _app = (ROOT / "app.py").read_text(encoding="utf-8")
    _tree = ast.parse(_app)
    assert "from ui.views.page_05_settings import" in _app, (
        "`app.py` 沒有 import 新 ⑤ —— 接線鏈斷在 app.py 這一節。")
    _in_slot = [
        _c.func.id
        for _n in ast.walk(_tree) if isinstance(_n, ast.With)
        for _it in _n.items
        if isinstance(_it.context_expr, ast.Name) and _it.context_expr.id == "tab_settings"
        for _c in ast.walk(_n)
        if isinstance(_c, ast.Call) and isinstance(_c.func, ast.Name)
        and _c.func.id.startswith("render_")
    ]
    assert _in_slot == ["render_settings_and_diagnostics"], (
        f"`with tab_settings:` 呼叫的是 {_in_slot}，應為 "
        "['render_settings_and_diagnostics']。")


def test_the_new_page_adds_no_write_surface():
    """⭐ 切換 ⑤ **沒有**把任何新的寫入槽拉進射程（新頁閉包的寫入面 ⊆ 舊 ⑤）。

    這是「切換不增加 Google Sheet 風險」最便宜的可執行版本：⑤ 本來就已經在線上，
    **舊 ⑤ 碰得到的東西，使用者今天就已經碰得到**。所以真正要證的不是
    「新頁不寫東西」，而是「**新頁沒有帶進舊頁沒有的寫入面**」。

    ⚠️ **這一條不是「零寫入」的證明** —— ⑤ 底下本來就有會寫客戶 Google Sheet 的
    路徑（NAV 手動匯入、保單管理），那些是**使用者明示動作**才寫，本來就該保留。
    本條證的是**切換這個動作本身**沒有改變那個集合。
    """
    _old, _new = _sinks(OLD_PAGE), _sinks(NEW_PAGE)
    # fail-closed：兩邊都掃到東西，本條才有意義（否則「差集是空的」只是恆綠）。
    assert _old, f"舊 ⑤（{OLD_PAGE}）一個寫入槽都沒掃到 —— 基準沒了，本條失去對象。"
    assert _new, f"新 ⑤（{NEW_PAGE}）一個寫入槽都沒掃到 —— 掃描器可能壞了。"

    _extra = sorted(_new - _old)
    assert not _extra, (
        f"新 ⑤ 的閉包多出了舊 ⑤ 沒有的寫入槽（{len(_extra)} 個）：\n  "
        + "\n  ".join(f"{_m}::{_q} → .{_p}(…)" for _m, _q, _p in _extra)
        + "\n⛔ 切換 ⑤ 不該擴大寫入面。先問：那條路徑是使用者明示動作才走的嗎？"
          "\n   若確實該有，請在 PR 描述寫明理由 —— 登記本身就是那份紀錄。")


def test_the_page_itself_writes_nothing():
    """被測檔**自己**一個寫入 primitive 都沒有 —— 它是委派殼，不該自己動手寫。

    ⚠️ 與上一條**不重複**：上一條看的是**整個閉包**（含被委派的舊模組），
    本條只看**這一個檔**。閉包那條在舊模組本來就有寫入時**永遠不會**替本檔說話。
    """
    _own = sorted(_write_sinks_in(ast.parse(NEW_SRC.read_text(encoding="utf-8"))))
    assert not _own, (
        f"被測檔自己出現了寫入 primitive：{_own}\n"
        "⛔ (A) 路線：新頁只做版面與編排，寫入一律呼叫既有舊模組。")


def test_the_scanner_can_actually_see_a_write():
    """⭐ **正對照** —— 沒有這一條，上面兩條可能只是恆綠。

    分兩層驗，因為它們會壞在不同的地方：
    (1) `_write_sinks_in` 認得出一個**明擺著的** gspread 寫入；
    (2) `_functions` 走得進 **class 方法**（本 repo 真的有 class 方法形態的寫入，
        只走頂層 `FunctionDef` 的掃描器會整個漏掉）。
    """
    _plain = _write_sinks_in(ast.parse(
        "def f(ws):\n    ws.append_rows([[1]])\n"))
    assert ("f", "append_rows") in _plain, (
        f"掃描器看不見最直白的 gspread 寫入：{_plain} —— 上面兩條等於恆綠。")

    _method = _write_sinks_in(ast.parse(
        "class R:\n    def save(self, p):\n        p.write_text('x')\n"))
    assert ("R.save", "write_text") in _method, (
        f"掃描器走不進 class 方法：{_method} —— class 方法形態的寫入會整個漏掉。")
