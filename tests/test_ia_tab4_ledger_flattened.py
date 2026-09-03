"""④ 資產配置 —— 交易帳本拉平（T5）＋ 真實收益矩陣去重（T21）的漂移鎖。

客戶拍板線框：④ 內部**不得**再開一層 `st.tabs`；同一個東西不要在兩頁各印一次。

## 為什麼要有這個檔（不是儀式）

**T5** —— `ui/tab3_t7_ledger.py` 是**全站最後一個真的會畫出第二層分頁列**的地方。
⚠️ 本 repo 已經因為這件事留下**兩句假宣稱**：
  · `ui/tab_settings_diag.py` 檔頭 ~~「全站最後一層巢狀 `st.tabs` 自此消失」~~
    （已就地劃線更正，收窄成「⑤ 這一頁自此沒有」）；
  · #747 的 PR 標題同樣宣稱巢狀分頁已消失。
**兩句都是真的把自己那一頁掃乾淨了，但都掃不到本檔。** 所以本檔的第 1 條規則
刻意**不是**「檢查某個字串不見了」，而是「`tabs(...)` 呼叫數 == 0」——
無論用什麼別名寫都算。

**T21** —— 真實收益矩陣曾是 clone×2（`STATE.md` 自陳）。把 ④ 那份拿掉之後，
最容易靜靜壞掉的方式是**兩個相反的方向**：有人把它加回 ④（又變兩份），
或有人把 ② 那份也刪了（功能整個消失、而「④ 沒有它」的斷言照樣綠）。
故本檔用**集合精確相等**（`==`，不是 `in`、不是 `not in`）把「渲染點恰好一處、
且就是 ② 那一處」釘死 —— **兩個方向都會紅。**

## ⚠️ 給下一個維護者：一種看起來比活著更綠的死法

把本檔任何一條行為斷言用 `if False:` / `return` 之類**死分支**關掉，
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
順序正確。負向與正向同時成立，才叫「拉平了」而不是「不見了」。

⚠️ **而「正向」還有第二層陷阱，本批實際踩過**：拿 SSOT 去渲染、再跟 SSOT 比對，
是**同義反覆** —— 改壞 production 路徑它照樣綠。故行為測試（`ledger_rendered`
那組）**必須**搭配把 helper 綁回 production 路徑的 AST 測試
（`..._uses_the_ssot_headings_in_order` / `..._no_handwritten_...` /
`..._not_inside_an_expander` / `..._toc_is_rendered_...`）。
**四條缺一，前面那組就退化成「helper 自己跟自己一致」。**

## ⛔ 本檔守不到的（2026-09-02 獨立稽核實測，就地登記，不要當成已涵蓋）

⚠️ **2026-09-03 重寫（有意識的更正，不是漏刪 · 依據：獨立稽核實測 + 本組逐條複跑）。**
本節原本用一句話蓋住全部缺口：~~「**這是所有靜態守衛的共同上限，不是本檔的實作瑕疵**」~~
—— **那句話對其中四條不成立**。那四條 AST 完全擋得住，是**普通的覆蓋缺口**，
不是物理上限。**把可修的漏洞說成「靜態守衛的物理上限」，等於替它發了一張免修證明。**
故本節改為**分兩層登記**：A 是真的守不到，B 是當時漏掉、現已補上。

### A 組｜可達性缺口（**真的守不到，靜態分析的物理上限**）

AST 看得到「這一行寫在 `render_t7_section` 裡」，**看不到那一行會不會被執行到**。
下列改動會讓本檔**全部通過**（實測）：

1. `_t7_section_heading("b")` 關進 `if False:`
2. `_t7_render_toc()` 關進 `if False:`
3. **三段標題全部關進 `if False:`（拉平在畫面上整個消失）**
4. `_render_dividend_matrix(funds)` 關進 `if False:`
5. ④ 的指路 caption 改成「留著 `where_to_find('health')` 呼叫但不渲染」
6. **死分支保留合法呼叫（騙過 AST 順序檢查）＋ 手寫一份不含指紋的替代品** ——
   例：`if False: _t7_section_heading("b")` ＋ `st.markdown("#### B 段（改名）")`
   （2026-09-03 本組實測 **13 passed**；畫面上標題與目錄對不起來）

**要擋住 A 組得整頁真渲染**，而 T7 主體在沙箱拿不到 OAuth / NAV / FX。
**對照組（證明只有刻意的死分支會漏）**：真的**刪掉**指路 caption 連同 import → **轉紅**；
真的**刪掉** `_t7_section_heading("b")` 再手寫替代品（不用 `if False:`）→ **轉紅**。

### B 組｜語法層覆蓋缺口（**當時漏掉，2026-09-03 已補，四條各自實測轉紅**）

⚠️ 這四條**不屬於** A 組，**不得**引用 A 組那句「靜態守衛的上限」替它們免修 ——
它們從頭到尾都是 AST 擋得住的，只是當時沒有人去擋：

| # | 繞道寫法 | 補之前 | 補之後 |
|---|---|---|---|
| M4 | 保留 `_t7_render_toc()`，另手寫第二份 toc | GREEN | **RED** |
| M5 | `st.header("B 投入再平衡", anchor="t7-b")` | GREEN | **RED** |
| M6 | `from streamlit import subheader` **裸名**手寫 | GREEN | **RED** |
| M10 | `st.markdown("#### B 投入再平衡（暫停使用）")` | GREEN | **RED** |

補的是 `test_no_handwritten_toc_or_heading_text_bypasses_the_ssot`。
⚠️ **M10 不是人造情境** —— 本檔既有慣例就是 `st.markdown("#### 📒 目前帳本…")`。
⚠️ **M6 說明為什麼要做裸名／alias 敏感**：`from streamlit import X` 在本 repo 是**活的
慣用寫法**（實測 8 處），任何寫死 `st.` 前綴的檢查都會被它整個繞過。

### 📌 附記｜一個差點漏掉的跨檔近失（2026-09-03 稽核指出，非本檔守備範圍，登記備查）

`tests/test_audit_20260810_tab2356_shells.py::test_growth_curve_yaxis_is_not_called_total_assets`
對 `ui/tab3_portfolio.py` 做 AST，**正向**斷言 `any("模擬市值" in t)`。
本批刪掉了該檔的 `yaxis_title="報酬率 / 配息率 (%)"`（矩陣那張圖），
**剛好不是承重的那一個** —— `模擬市值` 還剩 1 處，斷言因此照樣成立（本組實跑：1 passed）。
**再往左一步就是靜默轉紅**：那正是「main 上的測試在讀我改的檔」這種
git 看不見的語意衝突。**動 `ui/tab3_portfolio.py` 的人請先看這條。**

⛔ **因此不得把本檔讀成「④ 的版面已經被完整守住」。** 本檔守的是
**形狀與來源**（有沒有巢狀分頁、標題與目錄是不是同出一源、有沒有被包進 expander），
**不是**「使用者真的看得到」。後者只有真渲染或人工驗收擋得住。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

# 復用既有規則檔的 receiver 剝殼與呼叫正規化（§2.1 SSOT：不另寫第二份）。
from test_render_state_color_separation import (  # noqa: E402
    ROOT,
    UI_SOURCES,
    _callee,
    _st_container_names,
)

LEDGER = ROOT / "ui" / "tab3_t7_ledger.py"
PORTFOLIO = ROOT / "ui" / "tab3_portfolio.py"

#: 真實收益矩陣的**唯一**主場（② 持倉體檢）。
MATRIX_HOME = ROOT / "ui" / "helpers" / "fund_grp_health" / "dividend.py"

#: 用來辨識「這是矩陣的標題」的字。刻意取兩頁都用過的那一段，
#: 而不是整句 —— 整句一旦被微調（加個 emoji）就會靜靜失效。
MATRIX_HEADING_MARK = "健康矩陣"

#: 會畫出「標題」的 streamlit API。⚠️ 刻意**不含 `st.caption`** ——
#: ④ 留下來的那行灰色指路正是 caption，它是**指路不是渲染**。
HEADING_CALLS = frozenset({"st.markdown", "st.subheader", "st.header", "st.title"})


# ══════════════════════════════════════════════════════════════════
# 共用：AST / 假 streamlit
# ══════════════════════════════════════════════════════════════════
def _tree(path: pathlib.Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _docstring_ids(tree: ast.AST) -> frozenset[int]:
    """module / class / def 的 docstring 節點 id —— 掃字串時一律排除。

    理由同 `tests/test_manual_anchor_toc.py`：docstring 與註解是**講歷史**的地方
    （本 repo 慣例「舊條文保留不刪 + 加刪除線 + 兩邊理由並陳」），
    把它們算進掃描等於禁止記錄歷史。註解不進 AST，天然排除。
    """
    out: set[int] = set()
    for n in ast.walk(tree):
        if isinstance(n, (ast.Module, ast.FunctionDef,
                          ast.AsyncFunctionDef, ast.ClassDef)):
            b = getattr(n, "body", None)
            if (b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)
                    and isinstance(b[0].value.value, str)):
                out.add(id(b[0].value))
    return frozenset(out)


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

    ⚠️ **但那三條只到語法層**：它們確認「這一行寫在 production 函式裡」，
    **不確認那一行會被執行到**（把它關進 `if False:` → 全綠，稽核實測）。
    完整上限見模組 docstring「本檔守不到的」。
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


def _toc_markdown(fake: _FakeSt) -> str:
    toc = [a[0] for n, a, _k in fake.calls
           if n == "markdown" and a and isinstance(a[0], str) and "📑" in a[0]]
    assert len(toc) == 1, f"目錄應該恰好畫一次，實際 {len(toc)} 次"
    return toc[0]


def _toc_anchors(fake: _FakeSt) -> list[str]:
    import re
    return re.findall(r"\]\(#([^)]+)\)", _toc_markdown(fake))


def _toc_labels(fake: _FakeSt) -> list[str]:
    r"""目錄連結的**文字**（`[這一段]`），不是 anchor。

    ⚠️ 本 docstring 前面那個 `r` 前綴**不能拿掉** —— 它引用了正則 `\]\(#`，
    在非 raw 字串裡 `\]` 是 invalid escape sequence，會噴 DeprecationWarning
    （本批第一版就踩到，全套 warnings 4 → 7；由 `tests/test_nav_waterfall_no_overwrite.py`
    編譯全 repo 原始碼時浮出來，報成 `<unknown>:270`）。

    ⚠️ 這個 helper 是 2026-09-02 獨立稽核補的，補的是一個**真實的漏洞**：
    `_toc_anchors()` 的正則 `\]\(#([^)]+)\)` **只抓 `(#anchor)`，把 `[連結文字]`
    整個丟掉**，而 `test_section_titles_are_rendered_verbatim` 只比對 subheader
    —— 兩條加起來**沒有任何一條把目錄的連結文字綁回 `_T7_SECTIONS`**。
    """
    import re
    return re.findall(r"\[([^\]]+)\]\(#", _toc_markdown(fake))


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


def test_toc_link_text_matches_the_ssot_labels(ledger_rendered) -> None:
    """目錄連結的**文字**必須逐字 == `_T7_SECTIONS` 的標籤欄，順序也要對。

    ⚠️ **本條是 2026-09-02 獨立稽核抓到本檔漏洞後補的，不是原設計的一部分。**
    補之前，本檔（連同 production 註解、commit message、PR 描述）都宣稱
    「一欄制讓目錄與標題漂移**結構上不可能發生**」——**那句話當時是假的**，
    而且被實測繞過：

        突變 B1：`_t7_render_toc()` 內把連結文字硬寫成另一組字
                （`A 加碼(舊名)` / `B 再平衡(舊名)` / `C 轉換(舊名)`），
                anchor 仍走 `_t7_anchor` → **全套 11 passed 全綠**，
                而畫面上目錄的字與段標題完全對不起來。

    根因：舊有的兩條測試一條只看 anchor、一條只看 subheader，
    **目錄的連結文字沒有任何一條在守。**

    本條擋住的是「有人繞過那一欄、**在目錄裡手寫另一組字**」。

    ⚠️ **2026-09-03 第三次更正（有意識的更正，不是漏刪 · 依據：獨立稽核 + 本組複跑）**：
    本段原寫 ~~「補上本條之後，那句話才變成真的」~~ —— **又被推翻了一次。**
    本條走的是 `_FakeSt` **實際渲染**，只看得到「目錄真的被畫出來時，字對不對」；
    它**看不到**「有人另外手寫第二份目錄」，也**看不到**死分支。稽核實測：

        M4  保留 `_t7_render_toc()`，另手寫第二份 toc          → 當時全綠
        M5  `st.header("B 投入再平衡", anchor="t7-b")`        → 當時全綠
        M6  `from streamlit import subheader` 裸名手寫          → 當時全綠
        M10 `st.markdown("#### B 投入再平衡（暫停使用）")`      → 當時全綠

    **那四條已由 `test_no_handwritten_toc_or_heading_text_bypasses_the_ssot` 補上
    （四條各自實測轉紅）**；但**仍有一個守不到的殘留**：用 `if False:` 保留合法呼叫
    騙過 AST、同時手寫一份**不含段標籤／`t7-`／`](#` 指紋**的替代品 → **仍然全綠**。

    ⛔ **故本檔不再宣稱那句絕對語成立。** 「一欄制消滅了第二欄」為真；
    「因此漂移不可能發生」**為假**，已被推翻三次（原句 → B1 → if-False 變體）。
    完整分層清單見模組 docstring「本檔守不到的」。

    突變實驗（實跑）：上述 B1 → **本條轉紅**。
    """
    from ui.tab3_t7_ledger import _T7_SECTIONS

    assert _toc_labels(ledger_rendered) == [lbl for _, lbl in _T7_SECTIONS], (
        "目錄的連結文字與 `_T7_SECTIONS` 不符 —— 有人繞過 SSOT 在目錄裡手寫了字。\n"
        f"目錄實際={_toc_labels(ledger_rendered)}\n"
        f"應為={[lbl for _, lbl in _T7_SECTIONS]}")


# ══════════════════════════════════════════════════════════════════
# T5-3 把 helper 綁回 production 路徑（AST **語法層**；可達性守不到，見模組 docstring）
# ══════════════════════════════════════════════════════════════════
def test_render_path_uses_the_ssot_headings_in_order() -> None:
    """`render_t7_section()` 內必須依序呼叫三個 `_t7_section_heading`。

    **這條才是把 SSOT 綁到 production 路徑上的那一條（限語法層）。** 上面的行為測試
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
    """`st.subheader` **只准**出現在 `_t7_section_heading` 內（**不論帶不帶 `anchor=`**）。

    擋的是「繞過 SSOT 自己手寫一個 `st.subheader(..., anchor=...)`」——
    那會讓標題與目錄各走各的，而 `_T7_SECTIONS` 一欄制的防漂移保證當場失效。

    ⚠️ 這是**集合式**的 fail-closed 檢查（合法位置恰好一處），
    不是「檔案裡沒有某字串」的 `not in`。

    ⚠️ **2026-09-02 收緊（獨立稽核指出）**：本條原本只抓**帶 `anchor=`** 的
    `st.subheader` —— 於是手寫一個**不帶 anchor** 的標題就能整個繞過，
    畫面上會同時出現兩個互相矛盾的段標題而全套照樣全綠。
    現在改為「**本檔任何一處 `st.subheader`，只要不在 `_t7_section_heading` 裡，
    就是違規**」。實測本檔的 `st.subheader` 呼叫**只有 SSOT 那一處**，
    故這條收緊不會誤傷既有寫法。

    突變實驗（兩種都實跑過）：在 `render_t7_section` 內加
    `st.subheader("B 投入再平衡（暫停使用）", anchor="t7-b")` → **轉紅**；
    加**不帶 anchor** 的 `st.subheader("B 投入再平衡（暫停使用）")` → **同樣轉紅**。
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
        if id(n) not in legal:
            offenders.append(f"{LEDGER.name}:{n.lineno} {ast.unparse(n)[:70]}")

    assert offenders == [], (
        "有人繞過 `_t7_section_heading` 手寫段標題：\n  "
        + "\n  ".join(offenders) +
        "\n段標題與目錄必須同出一源（`_T7_SECTIONS`），否則兩邊會各自漂移。")


def test_no_handwritten_toc_or_heading_text_bypasses_the_ssot() -> None:
    """本檔任何「畫字」的呼叫，都不得手寫段標籤 / `t7-` 錨點 / 目錄連結。

    ⚠️ **2026-09-03 新增（獨立稽核實測，總管裁決「語法層一律補守衛」）。**
    上一條 `..._no_handwritten_section_heading_bypasses_the_ssot` 只看
    `st.subheader`，於是**四種語法層繞道全部照樣全綠**（稽核實跑）：

    | 突變 | 寫法 | 舊守衛 |
    |---|---|---|
    | M4 | 保留 `_t7_render_toc()`，另手寫第二份目錄 | GREEN |
    | M5 | `st.header("B 投入再平衡", anchor="t7-b")` | GREEN |
    | M6 | `from streamlit import subheader` 後**裸名**呼叫 | GREEN |
    | M10 | `st.markdown("#### B 投入再平衡（暫停使用）")` | GREEN |

    ⚠️ **M10 不是人造情境** —— 本檔既有慣例就是
    `st.markdown("#### 📒 目前帳本…")`，手寫一個 `#### ` 標題完全不突兀。

    **本條擋的是「字從哪裡來」，不是「用哪個 API」** —— 只要一個會畫字的呼叫
    裡出現下列任一指紋，就代表有人手抄了本該由 `_T7_SECTIONS` 產生的東西：

    1. **段標籤逐字**（抓 M6 / M10）；
    2. **`t7-` 錨點前綴**（抓 M5）；
    3. **目錄連結語法 `](#`**（抓 M4）。

    合法產出點**恰好兩處**：`_t7_section_heading` 與 `_t7_render_toc`，
    兩者都是**從 `_T7_SECTIONS` 組字**、檔內沒有任何字面標籤 ——
    所以這條收緊**零誤傷**（實測現行 production 命中數 = 0）。

    ⚠️ **裸名 / alias 敏感**，比照 `test_ledger_has_no_nested_tabs`：
    `from streamlit import subheader` 在本 repo 是**活的慣用寫法**（實測 8 處），
    寫死 `st.` 前綴的檢查會被 M6 整個繞過。

    ⛔ **本條只到語法層。** 「留著合法呼叫但用 `if False:` 關掉、另外手寫一份」
    （M13 / M14）**本條擋不住** —— 理由與完整清單見模組 docstring
    「本檔守不到的」B 組。**不要**把本條讀成「手寫繞道已經不可能」。
    """
    from ui.tab3_t7_ledger import _T7_ANCHOR_PREFIX, _T7_SECTIONS

    tree = _tree(LEDGER)
    docs = _docstring_ids(tree)
    containers = _st_container_names(tree)

    # 合法產出點：SSOT 的兩個函式體
    legal: set[int] = set()
    for n in ast.walk(tree):
        if (isinstance(n, ast.FunctionDef)
                and n.name in {"_t7_section_heading", "_t7_render_toc"}):
            legal |= {id(x) for x in ast.walk(n)}
    assert legal, "找不到 SSOT 的標題/目錄函式（被改名或刪了？）"

    # `from streamlit import markdown [as X]` → 裸呼叫也要抓（M6）
    bare: set[str] = set()
    want_attrs = {c.split(".", 1)[1] for c in HEADING_CALLS}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").startswith("streamlit"):
            for a in n.names:
                if a.name in want_attrs:
                    bare.add(a.asname or a.name)

    labels = [lbl for _, lbl in _T7_SECTIONS]
    offenders: list[str] = []
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call) or id(n) in legal:
            continue
        f = n.func
        is_heading = _callee(n, containers) in HEADING_CALLS or (
            isinstance(f, ast.Name) and f.id in bare)
        if not is_heading:
            continue
        for sub in ast.walk(n):
            if not (isinstance(sub, ast.Constant) and isinstance(sub.value, str)):
                continue
            if id(sub) in docs:          # docstring 是紀錄，不是渲染
                continue
            v = sub.value
            why = ("段標籤" if any(lb in v for lb in labels)
                   else "t7- 錨點" if _T7_ANCHOR_PREFIX in v
                   else "目錄連結" if "](#" in v
                   else "")
            if why:
                offenders.append(
                    f"{LEDGER.name}:{n.lineno} [{why}] {ast.unparse(n)[:80]}")
                break

    assert offenders == [], (
        "有人繞過 `_T7_SECTIONS` 手寫了段標題／錨點／目錄：\n  "
        + "\n  ".join(offenders) +
        "\n這些字只能由 `_t7_section_heading` / `_t7_render_toc` 從 SSOT 產生，"
        "手寫一份就會與另一邊各自漂移（而且畫面上看起來完全正常）。")


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


# ══════════════════════════════════════════════════════════════════
# T21 真實收益矩陣：全站恰好一處，且就是 ② 那一處
# ══════════════════════════════════════════════════════════════════
def _matrix_heading_sites() -> set[str]:
    """全站**畫出**矩陣標題的檔案集合（相對 repo 根的 posix 路徑）。

    「畫出」= 標題字出現在 `st.markdown/subheader/header/title` 的參數裡。
    刻意排除 `st.caption`（灰色指路）與 docstring（歷史紀錄）。
    """
    out: set[str] = set()
    for path in UI_SOURCES:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - 壞檔另有守衛
            continue
        docs = _docstring_ids(tree)
        containers = _st_container_names(tree)
        for n in ast.walk(tree):
            if not isinstance(n, ast.Call):
                continue
            if _callee(n, containers) not in HEADING_CALLS:
                continue
            for sub in ast.walk(n):
                if (isinstance(sub, ast.Constant) and isinstance(sub.value, str)
                        and id(sub) not in docs
                        and MATRIX_HEADING_MARK in sub.value):
                    out.add(path.relative_to(ROOT).as_posix())
    return out


def test_dividend_matrix_is_rendered_in_exactly_one_place() -> None:
    """全站畫「真實收益 vs 配息率健康矩陣」標題的地方**恰好一處**，且是 ② 那一處。

    ⚠️ 這是**集合精確相等**（`==`），不是 `not in` —— 兩個方向都會紅：
    - 有人把矩陣加回 ④（或第三頁）→ 集合變大 → **轉紅**；
    - 有人把 ② 那份也刪了 → 集合變空 → **轉紅**（功能整個消失時，
      一條「④ 沒有它」的 `not in` 斷言會照樣是綠的 —— 那正是本 repo
      已登記的空操作失效模式，本條刻意不用那種寫法）。

    突變實驗 A：在 `ui/tab3_portfolio.py` 加回
    `st.markdown("### 📊 真實收益 vs 配息率健康矩陣")` → **轉紅**（2 處）。
    突變實驗 B：把 `ui/helpers/fund_grp_health/dividend.py` 的該行標題刪掉
    → **轉紅**（0 處）。
    """
    want = {MATRIX_HOME.relative_to(ROOT).as_posix()}
    got = _matrix_heading_sites()
    assert got == want, (
        f"真實收益矩陣的渲染點應恰好是 {sorted(want)}，實際 {sorted(got)}。\n"
        "· 多了 → 同一張圖在兩頁各印一次（客戶拍板線框明禁）；\n"
        "· 少了 → 功能整個消失，② 持倉體檢那個唯一主場被拆掉了。")


def test_matrix_home_actually_renders_the_heading() -> None:
    """② 那份**真的畫得出來**（行為），不是只有一行字面值躺在檔案裡。

    上一條是靜態集合比對；靜態看得到「字串在那裡」，看不到「它會不會被執行到」。
    本條把 `_render_dividend_matrix` 實際跑一次，斷言標題真的被送進 `st.markdown`。

    突變實驗：把 `_render_dividend_matrix` 開頭改成 `return`（或把
    `if not funds: return` 改成 `if True: return`）→ **轉紅**。
    """
    import ui.helpers.fund_grp_health.dividend as _dv

    fake = _FakeSt()
    import unittest.mock as _mock
    with _mock.patch.object(_dv, "st", fake):
        # 一檔最小 fund dict：走得到標題那幾行就夠，後面算不出來不影響本條。
        _dv._render_dividend_matrix([{"code": "TEST01", "name": "測試基金"}])

    headings = [a[0] for n, a, _k in fake.calls
                if n in {"markdown", "subheader"} and a and isinstance(a[0], str)]
    assert any(MATRIX_HEADING_MARK in h for h in headings), (
        "② 持倉體檢的真實收益矩陣沒有畫出標題 —— "
        f"實際畫出的標題：{headings}")


def test_matrix_home_is_still_wired_into_the_health_tab() -> None:
    """② 的呼叫鏈完整：`app.py` → 健檢 Tab → extras → `_render_dividend_matrix`。

    上一條證明「那個函式會畫」，本條證明「有人會呼叫它」。
    兩條都要 —— 只證明前者的話，整條鏈被拔掉時本檔照樣全綠。

    突變實驗：把 `ui/helpers/fund_grp_health/__init__.py` 裡的
    `_render_dividend_matrix(funds)` 那行註解掉 → **轉紅**。
    """
    chain = [
        (ROOT / "app.py", "render_fund_grp_health_tab"),
        (ROOT / "ui" / "tab_fund_grp_health.py", "render_fund_grp_health_extras"),
        (ROOT / "ui" / "helpers" / "fund_grp_health" / "__init__.py",
         "_render_dividend_matrix"),
    ]
    broken: list[str] = []
    for path, callee in chain:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        called = {
            n.func.id for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        } | {
            n.func.attr for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
        }
        if callee not in called:
            broken.append(f"{path.relative_to(ROOT).as_posix()} 沒有呼叫 {callee}()")
    assert broken == [], (
        "② 真實收益矩陣的呼叫鏈斷了：\n  " + "\n  ".join(broken) +
        "\n④ 那份已經拿掉了，這條鏈一斷，功能就整個消失。")


def test_portfolio_points_users_to_the_health_tab_via_ssot() -> None:
    """④ 必須留一行指路，且分頁名走 `story_nav` SSOT（不得手抄「持倉體檢」）。

    「搬了但沒留指路」是本 repo 已經發作過的失效模式（一批 UI 重整打壞 6 處
    使用者可見的指路，由紅隊擋下）；「手抄分頁名」則是已經指錯三次的寫法 ——
    七→五改版後寫死的名字會指到分頁列上不存在的地方，而且**不會 raise**，
    只會安靜地錯。

    本條斷言的是**呼叫**：`where_to_find("health")` 真的被呼叫（`==` 比對
    參數常數），不是「檔案裡有 health 這個字」。

    突變實驗：把那行 caption 的 `_where_to_find_rc('health')` 換成寫死的
    「② 持倉體檢」→ **轉紅**。
    """
    tree = _tree(PORTFOLIO)
    # 找出所有 where_to_find 的別名（`from ... import where_to_find as X`）
    aliases = {"where_to_find"}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and (n.module or "").endswith("story_nav"):
            for a in n.names:
                if a.name == "where_to_find":
                    aliases.add(a.asname or a.name)

    args_seen = {
        n.args[0].value
        for n in ast.walk(tree)
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
        and n.func.id in aliases and n.args
        and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)
    }
    assert "health" in args_seen, (
        "④ 沒有用 `where_to_find('health')` 指路到 ② 持倉體檢。\n"
        f"目前 ④ 呼叫 where_to_find 的 key：{sorted(args_seen)}\n"
        "矩陣搬走了就必須告訴使用者去哪，而分頁名必須走 SSOT。")
