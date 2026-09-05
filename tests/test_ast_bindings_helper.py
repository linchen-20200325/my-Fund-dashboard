"""`tests/_ast_bindings.py` 自己的守衛 —— **把它 docstring 裡的宣稱變成可執行的**。

為什麼需要這一檔
----------------
`_ast_bindings.py` 是 ②③④ 三頁 form 閘門守衛 ＋ ⑤ 設定頁 guard 綁定守衛的**共用底層**。
它壞掉 = 上面**四個檔一起變成空轉**，而且是**安靜地**空轉（測試照樣全綠，只是什麼都沒守到）——
那正是 `CLAUDE.md §-2` 反覆點名的失效模式：**會說謊的守衛比沒有守衛更危險**。

⛔ **本檔不是「多一層測試比較安心」**：它釘的是**四條 session 寫入管道**與**綁定形態**
   這兩張表本身。有人為了「簡化」把 `session_writes()` 收窄回只認 `ast.Assign`
   （那正是 2026-09-05 之前三頁各自的寫法），本檔會**當場轉紅**，
   而 ②③④ 三頁的守衛**不會**（它們的 production 檔本來就只有一個合規的下標寫入）。

⛔ **本檔不驗 streamlit 的執行期行為**：`key=` 到底會不會寫進 session、
   `st.form` 的 rerun 次數 —— 那些是執行期的事，靜態規則看不到，
   由 ②③④ 各自的 AppTest 條目去驗。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

from _ast_bindings import (bound_names, dotted, gate_guarded_ids,
                           gate_ifs, session_writes)  # noqa: E402


def _fn(body: str) -> ast.FunctionDef:
    """把一段函式本體包成 `def f(): ...` 並回傳那個 FunctionDef。"""
    src = "def f():\n" + "\n".join("    " + line for line in body.splitlines())
    return ast.parse(src).body[0]  # type: ignore[return-value]


# ── session_writes：四條管道，一條都不准漏 ──────────────────────────────
#: 每一列都必須被認成「一次 session 寫入」。
#: ⚠️ 這張表就是 `session_writes()` docstring 那張表的可執行版本 ——
#:    改那張表就要改這裡，**兩邊不同步會紅**（這是刻意的）。
WRITES = {
    "下標賦值": 'st.session_state["k"] = 1',
    "屬性賦值": "st.session_state.k = 1",
    "下標 AnnAssign": 'st.session_state["k"]: dict = {}',
    "屬性 AnnAssign": "st.session_state.k: int = 1",
    "AugAssign": 'st.session_state["k"] += 1',
    "tuple 解包": 'st.session_state["k"], x = 1, 2',
    "starred 解包": 'x, *st.session_state["k"] = [1, 2]',
    "for target": 'for st.session_state["k"] in [1]:\n    pass',
    "with as target": 'with open("f") as st.session_state["k"]:\n    pass',
    "update()": "st.session_state.update(k=1)",
    "setdefault()": 'st.session_state.setdefault("k", 1)',
    "widget key=": 'st.text_input("x", key="k")',
    "sidebar widget key=": 'st.sidebar.text_input("x", key="k")',
    "alias 屬性賦值": "_s.session_state.k = 1",
    "alias update()": "_s.session_state.update(k=1)",
}

#: 每一列都**不准**被認成寫入（讀取、或與 session 無關的呼叫）。
#: 偽陽性和漏抓一樣糟：守衛一旦亂叫，下一個人就會把它放寬掉。
NON_WRITES = {
    "讀 get()": 'x = st.session_state.get("k")',
    "讀下標": 'x = st.session_state["k"]',
    "讀屬性": "x = st.session_state.k",
    "別人的 key=": 'foo.bar(key="k")',
    "別人的 update()": "d.update(k=1)",
    "無關賦值": "x = 1",
}


@pytest.mark.parametrize("case", sorted(WRITES))
def test_every_documented_write_channel_is_detected(case: str) -> None:
    assert session_writes(_fn(WRITES[case])), (
        f"`session_writes()` 漏掉「{case}」：{WRITES[case]!r}\n"
        "這條管道漏掉 = ②③④ 三頁的 form 閘門守衛對它完全無感。")


@pytest.mark.parametrize("case", sorted(NON_WRITES))
def test_reads_and_unrelated_calls_are_not_counted_as_writes(case: str) -> None:
    assert not session_writes(_fn(NON_WRITES[case])), (
        f"`session_writes()` 把「{case}」誤判成寫入：{NON_WRITES[case]!r}\n"
        "偽陽性會逼下一個人把守衛放寬，比漏抓更難救。")


def test_a_write_is_reported_once_with_a_usable_lineno() -> None:
    """回傳的必須是**可定位**的節點（錯誤訊息要印得出行號與原文），且不重複計數。"""
    fn = _fn('st.session_state["a"] = 1\nst.session_state.b = 2')
    hits = session_writes(fn)
    assert len(hits) == 2, f"應為 2 次寫入，實得 {len(hits)}"
    assert [n.lineno for n in hits] == [2, 3], "回傳未依行號排序"
    assert all(ast.unparse(n) for n in hits)


# ── gate_ifs：只認閘門那個 if ────────────────────────────────────────────
_GATED = (
    'with applied_form("k") as _gate:\n'
    '    pass\n'
    'if _gate:\n'
    '    st.session_state["k"] = 1'
)
_SECOND_IF = (
    'with applied_form("k") as _gate:\n'
    '    pass\n'
    'if True:\n'
    '    st.session_state["k"] = 1\n'
    'if _gate:\n'
    '    st.session_state["ok"] = 1'
)


def test_the_gate_if_is_recognised() -> None:
    gates = gate_ifs(_fn(_GATED))
    assert len(gates) == 1 and gates[0].lineno == 4


def test_an_unrelated_if_is_not_treated_as_the_gate() -> None:
    """本檔存在的**主要理由之一**：舊寫法把「任何一個 `ast.If`」都當閘門。

    2026-09-05 實測：在三頁的 form 函式各插一段 `if True:` 包住的裸寫入 →
    **舊守衛三頁全綠**（洞），改用 `gate_ifs()` 後**三頁全紅**。
    """
    fn = _fn(_SECOND_IF)
    gates = gate_ifs(fn)
    guarded = {id(n) for g in gates for n in ast.walk(g)}
    naked = [w for w in session_writes(fn) if id(w) not in guarded]
    assert len(naked) == 1 and naked[0].lineno == 5, (
        "藏在與閘門無關的 `if` 底下的裸寫入必須仍算裸寫入。")


_ELSE_BRANCH = (
    'with applied_form("k") as _gate:\n'
    '    pass\n'
    'if _gate:\n'
    '    st.session_state["ok"] = 1\n'
    'else:\n'
    '    st.session_state["bad"] = 1'
)
_ELIF_BRANCH = (
    'with applied_form("k") as _gate:\n'
    '    pass\n'
    'if _gate:\n'
    '    st.session_state["ok"] = 1\n'
    'elif True:\n'
    '    st.session_state["bad"] = 1'
)


@pytest.mark.parametrize("case", [_ELSE_BRANCH, _ELIF_BRANCH])
def test_the_else_branch_of_the_gate_is_not_guarded(case: str) -> None:
    """`else:` / `elif` 是**閘門為假**才跑的路徑 —— 寫在那裡就是 bug 本身。

    ⚠️ 這條守的是一個**真的踩過的洞**（2026-09-05 品管組實測）：
    `ast.walk(gate_if)` 會連 `orelse` 一起收，導致「沒按送出鈕卻寫 session」
    被算成「已被閘門包住」。三頁 × 兩種分支 × 三種測試順序，六格全綠 → 修後全紅。
    ⚠️ 洞**不是** 2026-09-05 重寫造成的，`origin/main` 的舊寫法同樣看不見它。

    **突變驗證**：把 :func:`gate_guarded_ids` 換回 `ast.walk(gate)`，本條必須轉紅。
    """
    fn = _fn(case)
    naked = [w for w in session_writes(fn) if id(w) not in gate_guarded_ids(fn)]
    # `_fn()` 會補一行 `def f():`，故片段第 6 行 → 第 7 行（同檔既有測試的慣例）。
    assert [n.lineno for n in naked] == [7], (
        "閘門 `if` 的 else／elif 分支底下的寫入必須算裸寫入 —— "
        "那正是『沒送出卻覆寫已套用值』的形狀。")


def test_the_true_branch_is_still_guarded() -> None:
    """反向：真分支必須仍算 guarded，否則上面那條是靠誤殺換來的。"""
    fn = _fn(_ELSE_BRANCH)
    guarded = gate_guarded_ids(fn)
    writes = session_writes(fn)
    assert any(id(w) in guarded for w in writes), "真分支的寫入被誤判成裸寫入。"


def test_no_gate_means_everything_counts_as_naked() -> None:
    """認不出閘門時要 **fail-closed**（全部算裸寫入），不是靜靜放行。"""
    fn = _fn('_gate = some_other_form("k")\nif _gate:\n    st.session_state["k"] = 1')
    assert gate_ifs(fn) == []


# ── bound_names：include_imports 兩種語意都要在 ──────────────────────────
_BINDINGS = 'import os\nfrom m import X as Y\nA = 1\nB: int = 2\nC += 3\nfor D in []:\n    pass\n'


def test_bound_names_covers_the_documented_binding_forms() -> None:
    tree = ast.parse(_BINDINGS + "(E := 4)\n")
    got = bound_names(tree)
    assert {"os", "Y", "A", "B", "C", "D", "E"} <= got, f"漏了：{got}"


def test_include_imports_false_is_not_a_cosmetic_flag() -> None:
    """`include_imports=False` 是 `test_settings_diag_merge.py` 語意的一半。

    那裡問的是「import 綁定**有沒有被遮蔽**」，所以 import 本身不算重新指派。
    2026-09-05 實測：拿掉這個開關直接照搬，該檔由 26 passed 變成 5 failed / 21 passed。
    """
    tree = ast.parse(_BINDINGS)
    assert "os" in bound_names(tree, include_imports=True)
    assert "Y" in bound_names(tree, include_imports=True)
    assert "os" not in bound_names(tree, include_imports=False)
    assert "Y" not in bound_names(tree, include_imports=False)
    assert "A" in bound_names(tree, include_imports=False)


def test_dotted_refuses_to_guess() -> None:
    """認不得的形狀要回空字串，**不要拼出一個看起來像真的路徑**。"""
    assert dotted(ast.parse("a.b.c", mode="eval").body) == "a.b.c"
    assert dotted(ast.parse("f().b", mode="eval").body) == ""
    assert dotted(ast.parse('d["k"].b', mode="eval").body) == ""
