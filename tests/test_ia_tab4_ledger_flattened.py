"""④ 資產配置 —— 交易帳本拉平（T5）的漂移鎖。

客戶拍板線框：④ 內部**不得**再開一層 `st.tabs`，分區靠「區塊 + 標題 + 錨點」。

## 為什麼要有這個檔（不是儀式）

`ui/tab3_t7_ledger.py` 是**全站最後一個真的會畫出第二層分頁列**的地方。
⚠️ 本 repo 已經因為這件事留下**兩句假宣稱**：
  · `ui/tab_settings_diag.py` 檔頭 ~~「全站最後一層巢狀 `st.tabs` 自此消失」~~
    （已就地劃線更正，收窄成「⑤ 這一頁自此沒有」）；
  · #747 的 PR 標題同樣宣稱巢狀分頁已消失。
**兩句都是真的把自己那一頁掃乾淨了，但都掃不到本檔。** 所以第 1 條規則
刻意**不是**「檢查某個字串不見了」，而是「`tabs(...)` 呼叫數 == 0」——
無論用什麼別名寫都算。

## ⚠️ 給下一個維護者：一種看起來比活著更綠的死法

把本檔任何一條斷言用 `if False:` / `return` 之類**死分支**關掉，
pytest 照樣報 **PASSED**、`--collect-only` 的數字也一格不變 ——
**守衛死掉會比它活著更綠。** 靜態掃描、覆蓋率、測試數量**都偵測不到**這件事。
**唯一偵測得到它的就是突變測試本身**：改壞 production code，確認本檔真的轉紅。
（本批實測：把 `test_render_path_uses_the_ssot_headings_in_order` 的斷言關進
`if False:`，同時真的刪掉 production 的 `_t7_section_heading("b")` ——
**collect 11 → 11、11 passed 全綠**。）
動到本檔時請重跑一次突變，不要只看 CI 是綠的。

## 判定方向：fail-closed

規則 1（無巢狀分頁）是**負向**斷言，單獨存在會有「東西被整段刪光也照樣綠」的
空操作風險。故一律與**正向**斷言配對：三段必須真的被畫出來、標題逐字正確、
順序正確、而且**是 production 路徑在畫**（後者靠 AST，理由見 `ledger_rendered`）。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

# 復用既有規則檔的 receiver 剝殼與呼叫正規化（§2.1 SSOT：不另寫第二份）。
from test_render_state_color_separation import ROOT  # noqa: E402

LEDGER = ROOT / "ui" / "tab3_t7_ledger.py"


# ══════════════════════════════════════════════════════════════════
# 共用：AST / 假 streamlit
# ══════════════════════════════════════════════════════════════════
def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


class _Ctx:
    """可當 context manager 的回傳值，並記錄自己被 enter / exit。"""

    def __init__(self, log: list, name: str) -> None:
        self._log = log
        self._name = name

    def __enter__(self):
        self._log.append(("__enter__", self._name))
        return self

    def __exit__(self, *exc):
        self._log.append(("__exit__", self._name))
        return False


class _ColumnConfig:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class _FakeSt:
    """寬鬆的假 streamlit：記錄呼叫，其餘一律 no-op 並回可當 context 的物件。

    刻意用 `__getattr__` 全包而不是逐一列舉 API —— 逐一列舉的清單日後一定漏，
    那正是本 repo 白名單守衛失效的同一種病（見 `CLAUDE.md §8.2.A.0 規則 2`）。
    """

    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.session_state: dict = {}
        self.column_config = _ColumnConfig()

    def __getattr__(self, name):
        def _f(*a, **k):
            self.calls.append((name, a, k))
            return _Ctx(self.calls, name)
        return _f


# ══════════════════════════════════════════════════════════════════
# T5-1 巢狀分頁不得復辟（結構，alias 不敏感）
# ══════════════════════════════════════════════════════════════════
def test_ledger_has_no_nested_tabs() -> None:
    """`ui/tab3_t7_ledger.py` 內 `tabs(...)` 呼叫數必須是 **0**。

    ⚠️ **alias 不敏感**：比對的是「屬性名叫 `tabs`」與「裸呼叫 `tabs(...)`
    且 `tabs` 是從 streamlit import 進來的」，**不比對模組別名**。
    寫死 `st.tabs` 的字串 grep 會被 `import streamlit as _st_mod` 整個繞過
    —— 本 repo 真的有這種寫法（`ui/helpers/macro/ndc.py`）。

    ⚠️ **docstring / 註解不算**：本檔上方那段搬遷說明逐字引用了舊的
    `st.tabs([...])`，那是**記錄歷史**，不是呼叫。只看 `ast.Call`。

    突變實驗：在本檔任何位置加一行 `_x = st.tabs(["a", "b"])`
    或 `_m = streamlit; _x = _m.tabs(["a"])` → **本條轉紅**。
    """
    t = _tree(LEDGER)

    # `from streamlit import tabs [as X]` → 裸呼叫也要抓
    bare: set[str] = set()
    for n in ast.walk(t):
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("streamlit"):
            for a in n.names:
                if a.name == "tabs":
                    bare.add(a.asname or a.name)

    hits: list[str] = []
    for n in ast.walk(t):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        if isinstance(f, ast.Attribute) and f.attr == "tabs":
            hits.append(f"{LEDGER.name}:{n.lineno} {ast.unparse(f)}(...)")
        elif isinstance(f, ast.Name) and f.id in bare:
            hits.append(f"{LEDGER.name}:{n.lineno} {f.id}(...)")

    assert hits == [], (
        "④ 交易帳本又開了子分頁：\n  " + "\n  ".join(hits) +
        "\n客戶拍板線框：④ 內部不得再開一層 `st.tabs`（分區靠「區塊 + 標題 + 錨點」）。"
        "\n本檔是全站最後一個會畫出第二層分頁列的地方 —— 它長回來就等於整批白做。")


# ══════════════════════════════════════════════════════════════════
# T5-2 三段真的被畫出來（行為；與上一條配對，防「刪光也算過」）
# ══════════════════════════════════════════════════════════════════
@pytest.fixture()
def ledger_rendered(monkeypatch):
    """把**版面骨架函式**跑一次（目錄 + 三個段標題），回傳呼叫紀錄。

    ⛔ **這不是整頁渲染，也不是 production 路徑** —— T7 主體需要 OAuth / NAV / FX，
    沙箱一律拿不到，`render_t7_section()` 在這裡跑不完。

    ⚠️ **因此本 fixture 上的兩條測試「只驗 helper 自己前後一致」，
    它們看不到 production 路徑有沒有真的呼叫這些 helper。**
    這一點**實測過，不是推論**：把 `render_t7_section` 內的
    `_t7_section_heading("b")` 換成手寫的 `st.subheader("B 投入再平衡（暫停使用）",
    anchor="t7-b")` —— 本 fixture 上的測試**全綠**。
    **把 helper 綁回 production 路徑的是下面三條 AST 測試**
    （`..._uses_the_ssot_headings_in_order` / `..._no_handwritten_...` /
    `..._not_inside_an_expander`），**缺了它們，本 fixture 這兩條就是同義反覆。**
    """
    import ui.tab3_t7_ledger as _led

    fake = _FakeSt()
    monkeypatch.setattr(_led, "st", fake)
    _led._t7_render_toc()
    for _k, _ in _led._T7_SECTIONS:
        _led._t7_section_heading(_k)
    return fake


def _render_fn() -> ast.FunctionDef:
    """`render_t7_section` 的 AST 節點 —— production 路徑的入口。"""
    for n in ast.walk(_tree(LEDGER)):
        if isinstance(n, ast.FunctionDef) and n.name == "render_t7_section":
            return n
    raise AssertionError("ui/tab3_t7_ledger.py 找不到 render_t7_section()")


def _heading_calls_in_render() -> list[str]:
    """production 路徑內 `_t7_section_heading("x")` 的常數引數，**依原始碼順序**。"""
    out: list[tuple[int, str]] = []
    for n in ast.walk(_render_fn()):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id == "_t7_section_heading" and n.args
                and isinstance(n.args[0], ast.Constant)):
            out.append((n.lineno, str(n.args[0].value)))
    return [k for _ln, k in sorted(out)]


def _toc_anchors(fake: _FakeSt) -> list[str]:
    import re
    toc = [a[0] for n, a, _k in fake.calls
           if n == "markdown" and a and isinstance(a[0], str) and "📑" in a[0]]
    assert len(toc) == 1, f"目錄應該恰好畫一次，實際 {len(toc)} 次"
    return re.findall(r"\]\(#([^)]+)\)", toc[0])


def _subheader_anchors(fake: _FakeSt) -> list[str]:
    return [k["anchor"] for n, _a, k in fake.calls
            if n == "subheader" and k.get("anchor")]


def _subheader_titles(fake: _FakeSt) -> list[str]:
    return [a[0] for n, a, _k in fake.calls if n == "subheader" and a]


def test_toc_and_sections_agree(ledger_rendered) -> None:
    """目錄列的每個 anchor 都要有對應的 `st.subheader(anchor=...)`，**且反之亦然**。

    這條擋兩個方向：
    - **目錄有、區塊沒有** → 使用者點了不會動（最惡劣：畫面沒有任何錯誤訊息）；
    - **區塊有 anchor、目錄沒列** → 一個進不去的區塊。

    比對用 `==`（順序敏感的 list 相等），**不是 `in`** —— 子字串比對下
    「原名＋後綴」就能繞過。

    突變實驗 A：`_t7_render_toc()` 的 for-loop 改成 `_T7_SECTIONS[:-1]` → **轉紅**。
    突變實驗 B：把 `_T7_ANCHOR_PREFIX` 改掉但只改一邊 → **轉紅**。
    """
    from ui.tab3_t7_ledger import _T7_SECTIONS, _t7_anchor

    want = [_t7_anchor(k) for k, _ in _T7_SECTIONS]
    assert _toc_anchors(ledger_rendered) == want
    assert _subheader_anchors(ledger_rendered) == want


def test_section_titles_are_rendered_verbatim(ledger_rendered) -> None:
    """三段標題必須**逐字** == `_T7_SECTIONS` 的標籤欄，順序也要對。

    `==` 而非 `in`：後者在「A 新投入」→「A 新投入（暫停使用）」這種改動下
    照樣會過，而使用者看到的已經是另一句話了。

    順序 A→B→C 是線框指定的操作順序（先加碼、再用投入調整、最後才轉換），
    不是隨便排的。

    突變實驗：把 `_T7_SECTIONS` 任一列的標籤改字 → **轉紅**（因為 `want`
    與實際畫出來的都來自同一個 SSOT，改字兩邊會一起動 —— 故本條真正擋的是
    「有人繞過 SSOT 另外手寫一個 `st.subheader`」與「順序被調換」）。
    """
    from ui.tab3_t7_ledger import _T7_SECTIONS

    assert _subheader_titles(ledger_rendered) == [lbl for _, lbl in _T7_SECTIONS]


# ══════════════════════════════════════════════════════════════════
# T5-3 把 helper 綁回 production 路徑（AST；上面那組行為測試缺這個就是同義反覆）
# ══════════════════════════════════════════════════════════════════
def test_render_path_uses_the_ssot_headings_in_order() -> None:
    """`render_t7_section()` 內必須依序呼叫三個 `_t7_section_heading`。

    **這條才是把 SSOT 綁到 production 路徑上的那一條。** 上面的行為測試
    （`test_toc_and_sections_agree` / `..._verbatim`）是拿 SSOT 渲染再跟 SSOT 比，
    **改壞 production 路徑它們不會紅**（已實測，見 `ledger_rendered` docstring）。

    比對用 `==`（順序敏感），不是 `in`：A→B→C 是線框指定的操作順序
    （先加碼 → 用投入調整 → 最後才轉換）。

    突變實驗：把 `_t7_section_heading("b")` 換成手寫 `st.subheader(...)` → **轉紅**；
    把 B 段與 C 段對調 → **轉紅**。
    """
    from ui.tab3_t7_ledger import _T7_SECTIONS

    want = [k for k, _ in _T7_SECTIONS]
    got = _heading_calls_in_render()
    assert got == want, (
        f"production 路徑畫出來的段落與 `_T7_SECTIONS` 不符\n"
        f"render_t7_section 內實際呼叫={got}\n應為={want}\n"
        "· 少了 → 有一段沒有標題與錨點，目錄點過去會落空；\n"
        "· 順序不同 → 線框指定的操作順序被打亂。")


def test_no_handwritten_section_heading_bypasses_the_ssot() -> None:
    """帶 `anchor=` 的 `st.subheader` **只准**出現在 `_t7_section_heading` 內。

    擋的是「繞過 SSOT 自己手寫一個 `st.subheader(..., anchor=...)`」——
    那會讓標題與目錄各走各的，而 `_T7_SECTIONS` 一欄制的防漂移保證當場失效。

    ⚠️ 這是**集合式**的 fail-closed 檢查（合法位置恰好一處），
    不是「檔案裡沒有某字串」的 `not in`。

    突變實驗：在 `render_t7_section` 內加一行
    `st.subheader("B 投入再平衡（暫停使用）", anchor="t7-b")` → **轉紅**。
    """
    tree = _tree(LEDGER)
    # 先找出 `_t7_section_heading` 這個函式體內的節點 id（合法位置）
    legal: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_t7_section_heading":
            legal = {id(x) for x in ast.walk(n)}
            break
    assert legal, "找不到 `_t7_section_heading`（SSOT 標題函式被刪了？）"

    offenders: list[str] = []
    for n in ast.walk(tree):
        if not (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "subheader"):
            continue
        if not any(kw.arg == "anchor" for kw in n.keywords):
            continue
        if id(n) not in legal:
            offenders.append(f"{LEDGER.name}:{n.lineno} {ast.unparse(n)[:70]}")

    assert offenders == [], (
        "有人繞過 `_t7_section_heading` 手寫帶 anchor 的標題：\n  "
        + "\n  ".join(offenders) +
        "\n段標題與目錄必須同出一源（`_T7_SECTIONS`），否則兩邊會各自漂移。")


def test_section_headings_are_not_inside_an_expander() -> None:
    """三段標題**不得**被包進 `st.expander` —— 線框明禁用收合取代分頁。

    收合的內容**不在 DOM 裡** → 殺掉 Ctrl-F，錨點也跳不進去。
    要收合請用「整段一個總開關」，內部結構不變。

    ⚠️ 這條是 **AST 的語法巢狀**檢查，看的是 production 路徑，
    **不是**「檔案裡沒有 expander」的字串檢查 —— 本檔別處本來就有合法的
    expander（「✏️ 編輯持倉」），那些不在 `_t7_section_heading` 的上游。

    突變實驗：把 `_t7_section_heading("a")` 那行改成包在
    `with st.expander("A 新投入"):` 底下 → **轉紅**。
    """
    bad: list[str] = []

    def _walk(node, in_expander: bool) -> None:
        for child in ast.iter_child_nodes(node):
            nxt = in_expander
            if isinstance(child, ast.With):
                for item in child.items:
                    ce = item.context_expr
                    if (isinstance(ce, ast.Call) and isinstance(ce.func, ast.Attribute)
                            and ce.func.attr == "expander"):
                        nxt = True
            if (in_expander and isinstance(child, ast.Call)
                    and isinstance(child.func, ast.Name)
                    and child.func.id == "_t7_section_heading"):
                bad.append(f"{LEDGER.name}:{child.lineno} {ast.unparse(child)}")
            _walk(child, nxt)

    _walk(_render_fn(), False)

    assert bad == [], (
        "這些段標題被包進 `st.expander` 裡：\n  " + "\n  ".join(bad) +
        "\n收合內容不在 DOM 裡 → Ctrl-F 找不到、錨點跳不進去。"
        "\n線框明訂：拉平之後不得用預設收合的 expander 取代分頁。")


def test_toc_is_rendered_in_the_production_path() -> None:
    """`render_t7_section()` 內必須呼叫 `_t7_render_toc()`。

    沒有目錄 = 三段攤平之後使用者只能用捲的，錨點也沒有入口 ——
    那不是「拉平」，是「把分頁列刪掉」。

    突變實驗：把 `render_t7_section` 內的 `_t7_render_toc()` 註解掉 → **轉紅**。
    """
    called = {
        n.func.id for n in ast.walk(_render_fn())
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
    }
    assert "_t7_render_toc" in called, (
        "production 路徑沒有畫錨點目錄 —— 三段攤平後就沒有導覽入口了。")
