"""④ 資產配置新頁的**零寫入**守衛 —— 渲染一輪不得動客戶的 Google Sheet 或磁碟。

客戶 2026-09-06 永久授權（逐字）
--------------------------------
> 「凡是『查詢/搜尋』功能，一律強制走純讀取（唯讀），**絕對禁止反向寫入我的 Google Sheet**。
>   不用問我，直接切斷寫入！」

本檔守的是 ④ 這一頁的那道切斷。**它現在就要在，而不是等委派落地才補** ——
理由是 `ui/views/page_02_health.py` 的實證：② 的同型守衛因為走**靜態 import 閉包**，
委派一加就**自動**把新模組納入射程（實測閉包 65 → 95），
**機器本來就設計對了，不需要有人記得回來改**。本檔沿用同一個結構。

⚠️ **本檔為什麼不長得像 `test_wf02_health_no_writes.py`**（刻意的，逐條說明）
---------------------------------------------------------------------------
派工單點名不要照抄那一份的弱點。本檔的三處差異：

1. ⛔ **不用「函式名白名單」，也不用「import 來源白名單」。**
   本 repo 已實測那種守衛擋不住四種寫法：
   ``from m import f as g`` ／ ``g = m.f`` 再 ``g()`` ／ ``getattr`` ／ ``importlib``。
   → 本檔比對的是**低階寫入動作本身的名字**（`append_row` / `update` / `write_text` …），
     那是 gspread 與 `pathlib` 的 API 表面，**不是本 repo 可以改名繞過的東西**。
2. ⭐ **涵蓋 `ast.Attribute` —— 把寫入方法「當引數傳出去」也算命中。**
   `_with_quota_retry(ws.append_row, ...)` 這種寫法**沒有呼叫節點**
   （`ws.append_row` 是 `ast.Attribute`，被當引數傳給包裝器，由包裝器去呼叫）。
   只看 `ast.Call` 的偵測器**看不到它**。
   ⚠️ 這不是假想：`bacfe06`（「補掉 M5c —— 把寫入函式**當引數傳出去**也算命中」）
   就是為了同一個形狀而補的。由 :func:`test_the_detector_sees_the_four_evasions` 釘住。
3. ⭐ **哨兵記名、不拋例外。**
   會 `raise` 的哨兵會被上層 ``try/except`` 吃掉 —— 那等於沒有守衛，
   而且**吃掉之後畫面看起來一切正常**，比沒有守衛更糟。
   由 :func:`test_the_sentinel_records_instead_of_raising` 與
   :func:`test_a_swallowing_caller_cannot_hide_a_write` 釘住。

⚠️ 這道守衛看得見什麼、看不見什麼（照實寫，不要讀成「守死了」）
----------------------------------------------------------------
**看得見**

* 頁面**靜態 import 閉包**內任何一支 repo 模組裡的寫入動作 ——
  無論它是被呼叫（`ast.Call`）還是被當引數傳出去（`ast.Attribute`）。
* 那些寫入動作**有沒有被按鈕擋住**（`st.button` / `st.form_submit_button` /
  `st.checkbox` / `st.download_button`，含「先存成變數再 `if`」那種寫法）。
  這正是 `#800` 的教訓：`_maybe_snapshot()` **一渲染就寫**，
  唯一的閘門是一個 session 旗標 —— 而**「少寫幾次」不叫切斷**。

**看不見（已知缺口，逐條寫出來，不要當成保證）**

1. **只追靜態 import。** `importlib.import_module("a." + "b")` 這種動態載入
   不在閉包內，本檔看不到它引進來的模組。
2. **閘門偵測是語法層的。** 一個 `if _go:` 而 `_go` 來自別的函式的回傳值，
   本檔會判成**未被擋住**（偽陽性，從嚴）。**寧可誤報，不可漏報。**
3. ⛔ **本檔不驗執行期。** 它讀 AST，不渲染。真的跑一輪、用假件攔截的那一層，
   由 `tests/test_portfolio_perf_render_no_writes.py` 負責（deny-by-default 假件）。
   **兩者互補，不重疊**：那一份只罩「📈 組合績效追蹤」那一條路，本檔罩整個閉包。
4. **本地無 `streamlit`，故本檔刻意設計成不需要它** —— 見上一條。

⚠️ **本檔由執行組單組產出，未經第二組獨立複驗**（`CLAUDE.md §-2` 規則 6）。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_PAGE = "ui.views.page_04_portfolio"
#: 閉包只追這幾個頂層套件 —— 其餘（`streamlit` / `pandas` / stdlib）不是本 repo 的程式碼。
_REPO_ROOTS = ("ui", "services", "shared", "repositories", "infra")

#: gspread 試算表物件上的**寫入**方法。
#: ⚠️ 這是**第三方 API 的表面**，不是本 repo 的函式名 —— 所以它不會因為
#:    我們自己改名／取別名而失效。這正是它比「函式名白名單」強的地方。
_SHEET_WRITES: frozenset[str] = frozenset({
    "append_row", "append_rows", "update", "batch_update", "update_cell",
    "update_cells", "update_acell", "insert_row", "insert_rows",
    "add_worksheet", "del_worksheet", "delete_rows", "delete_columns",
    "clear", "resize", "values_append", "values_update", "values_clear",
})
#: 磁碟寫入（本地 JSON / parquet 後端那一路）。
_DISK_WRITES: frozenset[str] = frozenset({
    "write_text", "write_bytes", "mkdir", "makedirs", "touch", "unlink",
    "rmdir", "remove", "rename", "replace", "to_csv", "to_parquet", "to_json",
})
_WRITE_SINKS: frozenset[str] = _SHEET_WRITES | _DISK_WRITES

#: 使用者**明示意圖**的 streamlit 元件。寫入只能發生在它們的正分支裡。
#: ⛔ **session 旗標不在此列，而且永遠不會加進來** —— `#800` 的教訓逐字：
#:    session 旗標「只把『每個 session 寫一次』變成『少寫幾次』，
#:    寫入依然發生在使用者沒有表達任何意圖的時候。**少寫幾次不叫切斷。**」
_INTENT_WIDGETS: frozenset[str] = frozenset({
    "button", "form_submit_button", "checkbox", "download_button",
    "toggle", "confirm",
})


# ══════════════════════════════════════════════════════════════════════
# 偵測器
# ══════════════════════════════════════════════════════════════════════

def _mod_path(mod: str) -> "pathlib.Path | None":
    _p = _REPO / (mod.replace(".", "/") + ".py")
    if _p.exists():
        return _p
    _pkg = _REPO / mod.replace(".", "/") / "__init__.py"
    return _pkg if _pkg.exists() else None


def _imports(tree: ast.AST) -> set[str]:
    _out: set[str] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            _out.update(_a.name for _a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.level == 0 and _n.module:
            _out.add(_n.module)
            _out.update(f"{_n.module}.{_a.name}" for _a in _n.names)
    return _out


def _closure(root: str = _PAGE) -> dict[str, pathlib.Path]:
    """`root` 靜態 import 得到的所有 repo 模組。**委派一加，這裡自動變大。**"""
    _seen: dict[str, pathlib.Path] = {}
    _stack = [root]
    while _stack:
        _m = _stack.pop()
        if _m in _seen:
            continue
        _p = _mod_path(_m)
        if _p is None:
            continue
        _seen[_m] = _p
        for _x in _imports(ast.parse(_p.read_text(encoding="utf-8"))):
            if _x.split(".")[0] in _REPO_ROOTS and _x not in _seen:
                _stack.append(_x)
    return _seen


def _intent_names(tree: ast.AST) -> set[str]:
    """被指派成「使用者按了某個東西」的變數名（`_go = st.button(...)`）。"""
    _out: set[str] = set()
    for _n in ast.walk(tree):
        if not isinstance(_n, ast.Assign) or not isinstance(_n.value, ast.Call):
            continue
        try:
            _base = ast.unparse(_n.value.func).split(".")[-1]
        except Exception:                                    # pragma: no cover
            continue
        if _base in _INTENT_WIDGETS:
            _out.update(_t.id for _t in _n.targets if isinstance(_t, ast.Name))
    return _out


def _write_refs(tree: ast.AST) -> list[tuple[int, str, bool]]:
    """`(行號, 寫入動作, 有沒有被使用者意圖擋住)` —— **呼叫與傳參都算**。

    ⚠️ **兩種形狀都要收**（缺一就是 `bacfe06` 補過的那個洞）::

        ws.append_row(row)                      # ast.Call    ← 只看這個會漏掉下一行
        _with_quota_retry(ws.append_row, row)   # ast.Attribute（當引數傳出去）
    """
    _parent: dict[int, ast.AST] = {}
    for _n in ast.walk(tree):
        for _c in ast.iter_child_nodes(_n):
            _parent[id(_c)] = _n
    _intent = _intent_names(tree)

    def _gated(node: ast.AST) -> bool:
        _cur = node
        while id(_cur) in _parent:
            _up = _parent[id(_cur)]
            if isinstance(_up, ast.If) and _cur in _up.body:
                try:
                    _src = ast.unparse(_up.test)
                except Exception:                            # pragma: no cover
                    _src = ""
                if any(f".{_w}(" in _src or _src.startswith(f"{_w}(")
                       for _w in _INTENT_WIDGETS):
                    return True
                if any(isinstance(_t, ast.Name) and _t.id in _intent
                       for _t in ast.walk(_up.test)):
                    return True
            _cur = _up
        return False

    _out: list[tuple[int, str, bool]] = []
    _seen: set[tuple[int, str]] = set()
    for _n in ast.walk(tree):
        if not isinstance(_n, ast.Attribute) or _n.attr not in _WRITE_SINKS:
            continue
        # `ast.Call` 的 func 與被當引數傳出去的裸 `ast.Attribute` 是同一個節點型別，
        # 所以只要掃 Attribute 就兩種都收到了 —— 這正是本函式不掃 `ast.Call` 的原因。
        _key = (_n.lineno, _n.attr)
        if _key in _seen:
            continue
        _seen.add(_key)
        _out.append((_n.lineno, _n.attr, _gated(_n)))
    return _out


# ══════════════════════════════════════════════════════════════════════
# 正對照 —— 偵測器沒瞎
# ══════════════════════════════════════════════════════════════════════

_EVASIONS = '''
import streamlit as st
def a(ws, row):
    ws.append_row(row)                       # 1 直接呼叫
def b(ws, row, wrap):
    wrap(ws.update_cell, row)                # 2 當引數傳出去（沒有 Call 節點）
    # ⚠️ 這裡刻意用 `update_cell` 而不是 `append_row` —— 下面的斷言比對的是**集合**，
    #    若第 1、2 種用同一個方法名，第 2 種被漏掉時集合**不會變**，斷言就抓不到。
    #    （本註是突變測試 M7 當場打出來的：初版兩處都用 `append_row`，
    #      把偵測器改成只看 `ast.Call` 之後**測試照樣全綠**。）
def c(ws, row):
    if st.session_state.get("done"): return  # 3 session 旗標**不算**閘門
    ws.append_rows([row])
def c2(ws, row):
    # 3b ⭐ `#800` 的真實形狀：寫入**就長在** session 旗標的正分支裡。
    #     這一格必須被判成「**沒有**被擋住」——「少寫幾次」不叫切斷。
    #     （本案例是突變測試 M8 當場逼出來的：初版只有 c()，而那裡的寫入在
    #       early-return 的 `if` **外面**，所以把 session_state 加進閘門判準時
    #       **測試照樣全綠** —— 等於這條規則從來沒被驗過。）
    if not st.session_state.get("snapshot_done"):
        ws.insert_row(row)
def d(p, text):
    p.write_text(text)                       # 4 磁碟
def gated(ws, row):
    if st.button("存"):                      # 這一個**應該**被判成有擋住
        ws.append_row(row)
'''


def test_the_detector_sees_the_four_evasions():
    """⭐ **正對照：四種寫法都要被抓到，而且 `st.button` 那一個要被判成「有擋住」。**

    ⚠️ **這條為什麼是本檔最重要的一條**：主規則
    （:func:`test_the_page_closure_never_writes_on_render`）的形狀是
    「掃到的未擋住寫入 == 空集合」—— 那個形狀在**偵測器變瞎的時候恆真**。
    偵測器壞掉的那一天，主規則會安靜地全綠。**空掃就是最危險的那種綠燈。**

    第 2 種（當引數傳出去）與第 3 種（session 旗標不算閘門）
    **是本檔相對既有守衛真正多守到的東西**，不是湊數。
    """
    _refs = _write_refs(ast.parse(_EVASIONS))
    _ungated = sorted({_a for _l, _a, _g in _refs if not _g})
    assert _ungated == ["append_row", "append_rows", "insert_row",
                        "update_cell", "write_text"], (
        "偵測器沒有抓到全部四種規避寫法。\n"
        f"實際抓到（未被擋住的）：{_ungated}\n"
        "⛔ 特別注意第 2 種 `wrap(ws.append_row, row)` —— 它沒有 `ast.Call` 節點，"
        "只掃 `ast.Call` 的偵測器看不到它。")
    _gated = sorted({_a for _l, _a, _g in _refs if _g})
    assert _gated == ["append_row"], (
        f"`if st.button(...)` 那一個應該被判成「有擋住」，實際：{_gated}\n"
        "閘門偵測壞了 —— 它會把合法的按鈕寫入也報成違規，"
        "然後有人為了讓 CI 綠而把整條守衛放寬。")


def test_the_detector_finds_real_writes_in_a_known_writer():
    """正對照之二：拿 repo 內**真的會寫**的模組跑一次，必須抓到東西。

    ⚠️ 上一條用的是本檔自己寫的合成字串 —— 一個只看得懂自己 fixture 的偵測器
    也能過那一關。本條改用**真實程式碼**（`services/nav_history_gs.py`，
    它就地記載自己會 `add_worksheet` / `ws.update` / `append_rows`）。
    """
    _p = _REPO / "services" / "nav_history_gs.py"
    assert _p.exists(), f"正對照的檔案不見了：{_p}（改名了就換一個真的會寫的模組）"
    _found = {_a for _l, _a, _g in _write_refs(ast.parse(_p.read_text(encoding="utf-8")))}
    for _expect in ("add_worksheet", "update", "append_rows"):
        assert _expect in _found, (
            f"偵測器在一個已知會寫的模組裡找不到 `{_expect}` —— 它瞎了。\n"
            f"找到的：{sorted(_found)}")


def test_the_closure_is_not_empty_and_contains_the_page_itself():
    """正對照之三：閉包非空，而且真的含本頁與幾個已知一定會被拉進來的模組。"""
    _c = _closure()
    assert _PAGE in _c, f"閉包裡沒有本頁自己 —— `{_PAGE}` 解析失敗了？"
    assert len(_c) >= 5, (
        f"閉包只有 {len(_c)} 個模組，太小了，主規則會空轉。\n掃到：{sorted(_c)}")
    for _anchor in ("ui.helpers.render_state", "ui.helpers.ia.gated_form"):
        assert _anchor in _c, (
            f"閉包裡沒有 `{_anchor}` —— import 追蹤壞了。\n掃到：{sorted(_c)}")


# ══════════════════════════════════════════════════════════════════════
# 主規則
# ══════════════════════════════════════════════════════════════════════

def test_the_page_closure_never_writes_on_render():
    """⭐ **本檔的本體：④ 這一頁 import 得到的任何地方，都不得在渲染期寫入。**

    「渲染期」＝**沒有被使用者明示意圖擋住**。寫入只能長在
    `if st.button(...)` / `if st.form_submit_button(...)` 這種正分支裡。

    **紅了要做什麼**：看那一行是不是真的會在渲染時跑到。
    - 是 → **修程式，把它移到按鈕的正分支裡**（`#800` 的修法）。
    - 不是（例如閘門用了本檔看不懂的寫法）→ 那是本檔的已知缺口 2，
      **在被測模組就地寫清楚，並在此處具名豁免**，不要整條放寬。

    ⛔ **絕對不要**用「加一個 session 旗標」來讓本條變綠 ——
       :data:`_INTENT_WIDGETS` 刻意不收 session 旗標，理由見該常數。
    """
    _bad: list[str] = []
    for _mod, _path in sorted(_closure().items()):
        _tree = ast.parse(_path.read_text(encoding="utf-8"))
        for _line, _attr, _gated in _write_refs(_tree):
            if not _gated:
                _bad.append(
                    f"{_path.relative_to(_REPO)}:{_line}  `.{_attr}(…)`  （模組 {_mod}）")
    assert not _bad, (
        "④ 的 import 閉包裡有**沒有被按鈕擋住**的寫入動作 —— "
        "使用者只是打開這一頁，它就會動到磁碟或他的 Google Sheet：\n  "
        + "\n  ".join(_bad)
        + "\n\n客戶 2026-09-06 永久授權逐字：「絕對禁止反向寫入我的 Google Sheet…"
          "不用問我，直接切斷寫入！」")


# ══════════════════════════════════════════════════════════════════════
# 哨兵機制 —— 記名、不拋例外
# ══════════════════════════════════════════════════════════════════════

class _Recorder:
    """把一個物件包起來：**寫入方法被碰到就記一筆，然後安靜地回 None**。

    ⭐ **為什麼不 `raise`**（本類別存在的全部理由）：
    會拋例外的哨兵，遇到 ``try/except Exception`` 就被吃掉了 ——
    守衛沒響、畫面一切正常、而那一筆寫入**照樣送出去了**。
    **記名不拋** 讓呼叫端無從吞掉它：`records` 是外部可讀的證據。
    """

    def __init__(self, inner: object = None) -> None:
        self.records: list[str] = []
        self._inner = inner

    def __getattr__(self, name: str):
        if name in _WRITE_SINKS:
            def _noop(*_a, **_kw):
                self.records.append(name)
                return None
            return _noop
        return getattr(self._inner, name)


def test_the_sentinel_records_instead_of_raising():
    """哨兵被碰到時**記一筆並回 None**，不得拋例外。"""
    _ws = _Recorder()
    _ws.append_row(["a"])
    _ws.update("A1", [["b"]])
    assert _ws.records == ["append_row", "update"], (
        f"哨兵沒有記到兩筆寫入，實際：{_ws.records}")


def test_a_swallowing_caller_cannot_hide_a_write():
    """⭐ 呼叫端包了 ``try/except Exception`` 也藏不住 —— 這就是「不拋例外」的用處。

    ⚠️ **對照組（會 `raise` 的哨兵在這裡就失效了）**：若哨兵改成拋例外，
    下面這個 ``except Exception: pass`` 會把它整個吃掉，
    `records` 是空的、測試通過、而寫入其實發生過。
    """
    _ws = _Recorder()
    try:
        _ws.append_rows([["x"]])
    except Exception:            # noqa: BLE001  ← 這正是實務上會出現的吞法
        pass
    assert _ws.records == ["append_rows"], (
        "呼叫端的 `try/except` 把哨兵吃掉了 —— 哨兵不能靠拋例外來報告。")


def test_the_sentinel_also_catches_a_write_passed_as_an_argument():
    """⭐ 把寫入方法**當引數傳給包裝器**，哨兵一樣要記到。

    這是執行期版本的「`ast.Attribute` 那一半」——
    對應 `_with_quota_retry(ws.append_row, ...)` 這種真實寫法。
    """
    _ws = _Recorder()

    def _with_quota_retry(fn, *args):
        return fn(*args)

    _with_quota_retry(_ws.append_row, ["y"])
    assert _ws.records == ["append_row"], (
        "把寫入方法當引數傳出去之後，哨兵沒記到 —— "
        "那正是 `bacfe06` 補過的那個形狀。")


@pytest.mark.parametrize("sink", sorted(_SHEET_WRITES | _DISK_WRITES))
def test_every_declared_sink_is_actually_intercepted(sink: str):
    """:data:`_WRITE_SINKS` 裡宣告的每一個名字，哨兵都要真的攔得到。

    ⚠️ 擋的是「清單上寫了、但攔截邏輯漏掉」這種**宣告與實作不同步**：
    一個只寫在常數裡、實際沒被攔的名字，會讓讀表的人以為它被守住了。
    """
    _r = _Recorder()
    getattr(_r, sink)()
    assert _r.records == [sink], f"`{sink}` 宣告在 `_WRITE_SINKS` 裡，但哨兵沒攔到它。"
