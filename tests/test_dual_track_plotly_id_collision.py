"""雙軌並行：舊 ② 與新 ⑥ 委派同一批舊模組 → `st.plotly_chart` 重複 element id。

本檔要擋的那顆 bug，**CI 結構上看不到**
================================================================
`st.tabs` 一次 run 會把**所有**分頁的 body 全部執行（`app.py` 就地註解）。
2026-09-07 雙軌之後：

    tab_health         → ui/tab_fund_grp_health.py::render_fund_grp_health_tab   （舊 ②）
    tab_preview_health → ui/views/page_02_health.py::render_holdings_health      （新 ⑥）

**兩邊委派同一批舊模組**（`backtest_section` / `correlation` / `dividend` / …），
所以同一個 run 裡同一支 renderer 會被呼叫兩次。

為什麼永遠測不到
----------------
舊 ② 在 `st.session_state["_fund_grp_health_ran"]` 沒被設起來之前**直接 `return`**，
而那面旗要使用者**按過一次「🩺 開始健診」**才會是 True。
CI 既沒有持倉、也不會去按那顆鈕 ⇒ **舊 ② 那一半永遠不執行** ⇒ 永遠不會有兩份 ⇒
**測試永遠是綠的**。**但客戶有持倉，而且旗標按過一次就一直留在 session 裡** ——
從那一刻起他每一次 rerun 都同時渲染兩份。

⚠️ 危險的是 `plotly_chart`，**不是** `dataframe` —— 這個不對稱要講清楚
================================================================
讀 **streamlit 1.59.1**（`requirements.txt` 釘 `>=1.59.1,<1.60.0`）原始碼求證：

- `elements/plotly_chart.py` 就地註解逐字寫著
  「We are computing the widget id for all plotly uses」，
  `compute_and_register_element_id(...)` **不在任何 `if` 底下** ⇒ **每一次呼叫都註冊**。
  id 由 `plotly_spec`（圖的 JSON）＋config＋theme＋寬高算出 ⇒ **同資料同圖 ⇒ 同 id**。
- `elements/lib/utils.py::_register_element_id` ⇒ 重複時
  `raise StreamlitDuplicateElementId(element_type)`。
- `elements/arrow.py`（`st.dataframe`）的同一支呼叫**包在 `if is_selection_activated:` 裡**，
  而 `is_selection_activated = on_select != "ignore"`，**預設就是 `"ignore"`**
  ⇒ 沒傳 `on_select` 的 `st.dataframe` **根本不註冊 id，撞不了**。

⛔ **交接說明把 `backtest_section.py` 的「3 個 dataframe ＋ 1 個 plotly_chart」
當成同一種危險 —— 實測不是**：危險的只有那 1 個 `plotly_chart`；
而真正的 collision surface **另外還有兩個 `plotly_chart`**
（`correlation.py::_render_correlation_matrix` 與 `dividend.py::_render_dividend_matrix`），
那兩支交接說明完全沒有提到。**多算了 3 個、漏掉了 2 個。**

本檔**看不到**的形態（誠實揭露，不是免責）
================================================================
- **動態組出來的呼叫**：`getattr(st, "plotly" + "_chart")`、dict 派發、
  由參數傳進來的 renderer —— 本檔只認 `st.<attr>(...)` 的字面形狀。
- **再往下一層的委派**：本檔只掃 `DELEGATED_ENTRIES` 直接指名的那幾個模組**檔案本身**，
  **沒有**遞迴走它們 import 的模組。⇒ 若某支 renderer 把畫圖再委派下去，本檔看不到。
- **`st.plotly_chart` 以外、其他會註冊 id 的元件**：本檔的
  :data:`_ALWAYS_REGISTERS` 只收了經原始碼確認的那些；streamlit 改版新增的不會自動進來。
- **執行層的真憑據**本檔給不了：本機沒有 streamlit，作者**無法**實跑重現那顆
  `StreamlitDuplicateElementId`。本檔的機制結論來自**讀 1.59.1 原始碼**（靜態），
  行為斷言來自**假 streamlit**（`_Rec`），**都不是真 runtime**。
  ⇒ **不得**把本檔全綠讀成「線上一定不會撞」。
"""
from __future__ import annotations

import ast
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "ui" / "views" / "page_02_health.py"
OLD_TAB = ROOT / "ui" / "tab_fund_grp_health.py"

#: 經 streamlit 1.59.1 原始碼確認：**無條件**註冊 element id 的元件。
#: 沒有 `key=` 時，同一份 spec 畫兩次 ⇒ 同一個 id ⇒ `StreamlitDuplicateElementId`。
_ALWAYS_REGISTERS = frozenset({"plotly_chart"})

#: 經同版原始碼確認：**只有** `on_select != "ignore"` 時才註冊 ⇒ 預設撞不了。
#: 列在這裡是為了讓「為什麼 dataframe 不算」這件事**可稽核**，不是裝飾。
_REGISTERS_ONLY_WITH_ON_SELECT = frozenset({"dataframe"})


def _page_const(name: str):
    """讀 `page_02_health.py` 模組層常數，**不 import**（本機沒有 streamlit）。"""
    tree = ast.parse(PAGE.read_text(encoding="utf-8"), str(PAGE))
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and node.target.id == name and node.value is not None:
            return ast.literal_eval(node.value)
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name) and tgt.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(f"{PAGE.name} 找不到模組層常數 {name}")


def _st_calls(path: pathlib.Path) -> list[tuple[str, int, bool, bool]]:
    """(元件名, lineno, 有沒有 key=, 有沒有 on_select=)，只認 `<something>.<attr>(...)`。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    out = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute):
            kw = {k.arg for k in n.keywords}
            out.append((n.func.attr, n.lineno, "key" in kw, "on_select" in kw))
    return out


def _delegated_module_paths() -> list[pathlib.Path]:
    """`DELEGATED_ENTRIES` 指名的模組 → 檔案路徑。"""
    paths = []
    for mod, _sym in _page_const("DELEGATED_ENTRIES"):
        p = ROOT / pathlib.Path(mod.replace(".", "/") + ".py")
        assert p.exists(), f"DELEGATED_ENTRIES 指到一個不存在的模組：{mod} → {p}"
        paths.append(p)
    return paths


# ══════════════════════════════════════════════════════════════════
# 1｜collision surface 是什麼：分類敘述，不寫「只有 N 處」
# ══════════════════════════════════════════════════════════════════
def test_the_collision_surface_is_classified_not_guessed():
    """委派模組裡**無 `key=` 且會註冊 id** 的元件 → 全部落在已知分類內。

    ⛔ 本條**刻意不斷言「只有 N 處」**（`CLAUDE.md §-1.5.1c 判定 2` 的方法教訓：
    能被一條 grep 推翻的全稱句就不該寫）。它斷言的是**分類**：
    每一個危險站點都必須是 :data:`_ALWAYS_REGISTERS` 裡的型別；
    新出現的型別會讓本條轉紅，逼人回來讀上面那段機制。
    """
    risky, safe = [], []
    for p in _delegated_module_paths():
        for attr, ln, has_key, has_on_select in _st_calls(p):
            rel = f"{p.relative_to(ROOT)}:{ln}"
            if attr in _ALWAYS_REGISTERS and not has_key:
                risky.append((attr, rel))
            elif attr in _REGISTERS_ONLY_WITH_ON_SELECT and not has_key and has_on_select:
                risky.append((attr, rel))
            elif attr in _REGISTERS_ONLY_WITH_ON_SELECT and not has_key:
                safe.append((attr, rel))

    # ── 輸入非空錨點：掃不到東西的話本條會變成恆綠的假守衛 ──
    assert risky, (
        "掃不到任何『無 key 且會註冊 element id』的站點 —— 本條變成假守衛。\n"
        "要嘛委派清單被改空了，要嘛那些呼叫改成了本檔看不到的動態形狀"
        "（見模組 docstring 的『看不到的形態』）。")
    assert safe, (
        "掃不到任何 `st.dataframe`（無 key、無 on_select）—— "
        "那是本檔用來對照『為什麼 dataframe 不算危險』的樣本，不該是空的。")

    _bad_types = {a for a, _ in risky} - set(_ALWAYS_REGISTERS)
    assert not _bad_types, (
        f"出現了本檔沒有分類過的危險型別：{sorted(_bad_types)}\n"
        "請先讀 streamlit 該元件的原始碼，確認它是否無條件註冊 element id，"
        f"再決定要不要收進 _ALWAYS_REGISTERS。目前站點：{sorted(risky)}")


# ══════════════════════════════════════════════════════════════════
# 2｜靜態：gate 是唯一入口，而且 fail-closed
# ══════════════════════════════════════════════════════════════════
def _delegated_fn() -> ast.FunctionDef:
    tree = ast.parse(PAGE.read_text(encoding="utf-8"), str(PAGE))
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == "_render_delegated_sections":
            return n
    raise AssertionError("page_02_health.py 找不到 `_render_delegated_sections`")


def _gate_names(fn: ast.FunctionDef) -> set[str]:
    """gate 變數名：`_x = st.checkbox(...)`，且**整個右手邊就是那個呼叫**。

    ⭐ 「整個右手邊就是那個呼叫」是本檔擋布林短路的關鍵：
    `_open = not True and st.checkbox(...)` 的右手邊是 `BoolOp`，**不會**被收進來。
    """
    names = set()
    for stmt in fn.body:
        if isinstance(stmt, ast.Assign) and len(stmt.targets) == 1 \
                and isinstance(stmt.targets[0], ast.Name) \
                and isinstance(stmt.value, ast.Call) \
                and isinstance(stmt.value.func, ast.Attribute) \
                and stmt.value.func.attr == "checkbox":
            assert not any(k.arg == "key" for k in stmt.value.keywords), (
                "gate 的 `st.checkbox` 帶了 `key=` —— streamlit 會代呼叫端把值寫進 "
                "`st.session_state`，那是每次渲染都發生、不經任何閘門的寫入，會踩 "
                "`test_wf02_health_no_writes.py::test_the_page_only_writes_its_own_session_namespace`。\n"
                "正解：`st.checkbox(標籤, value=False)`，直接用回傳值當條件。")
            names.add(stmt.targets[0].id)
    return names


def _gate_guard(fn: ast.FunctionDef, gate_names: set[str]) -> ast.If | None:
    """找『`if not <gate>:` → body 內有 `return`』這個守門子句。

    ⚠️ **必須比對 gate 變數名** —— 本函式上方還有一個 `if not _funds: return`
    （沒有持倉的早退）。初版只找「第一個 `if not X: return`」，於是抓到那一個、
    對著它做斷言 ⇒ **把 gate 整個拿掉照樣綠**。本機實跑當場抓到，就地修正。
    """
    for stmt in fn.body:
        if isinstance(stmt, ast.If) and isinstance(stmt.test, ast.UnaryOp) \
                and isinstance(stmt.test.op, ast.Not) \
                and isinstance(stmt.test.operand, ast.Name) \
                and stmt.test.operand.id in gate_names \
                and any(isinstance(x, ast.Return) for x in stmt.body):
            return stmt
    return None


def test_the_gate_is_the_only_way_in():
    """委派區必須被一個 **`st.checkbox` 守門子句**擋住，而且該子句 fail-closed。

    ⭐ **本條專門擋布林短路繞過** —— `if not True and st.checkbox(...)` 這種寫法
    畫面上有勾選框、AST 上也「有 checkbox」，但 gate 實質上被跳過了。
    （姊妹批次的第一版守衛就是被這一招騙過去的。）
    **做法：要求 gate 變數的來源是一個「整個右手邊就是 `st.checkbox(...)`」的賦值**
    （見 :func:`_gate_names`），任何 `BoolOp` / `Compare` / 常數混進來一律紅。
    """
    fn = _delegated_fn()
    gate_names = _gate_names(fn)
    assert gate_names, (
        "`_render_delegated_sections` 裡找不到『整個右手邊就是 `st.checkbox(...)`』的賦值。\n"
        "⛔ 這正是本條要擋的形狀：`if not True and st.checkbox(...)` 之類的布林短路，"
        "畫面上有勾選框、gate 卻是空的。gate 必須是一個乾淨的賦值。")

    guard = _gate_guard(fn, gate_names)
    assert guard is not None, (
        "委派區沒有『`if not <gate>: … return`』守門子句（或它守的不是那個乾淨的 gate 變數）"
        " —— 舊 ② 與本頁會在同一個 run 各畫一次 `st.plotly_chart`，線上直接紅字塊。")


def test_there_is_exactly_one_gate_and_zero_is_also_red():
    """委派區的 gate checkbox **恰好 1 個**。

    ⛔ **0 也要紅** —— 整塊 gate 被刪掉時，如果只斷言「不超過 1 個」，
    守衛會安靜地全綠通過。這是本批被點名的既有失效模式。
    """
    fn = _delegated_fn()
    n = sum(1 for x in ast.walk(fn)
            if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)
            and x.func.attr == "checkbox")
    assert n == 1, (
        f"委派區的 gate checkbox 有 {n} 個，應該**恰好 1 個**。\n"
        "0 個 ＝ gate 被拿掉了（舊 ② 與本頁會同時畫圖）；"
        "2 個以上 ＝ 出現第二道語意不明的閘門，使用者不知道該勾哪一個。")


def test_the_grey_text_never_sells_checking_as_the_fix():
    """灰態本文必須寫**勾下去會發生什麼**，不得把「勾下去」當成解法。

    ⛔ 起因是姊妹批次在 ⑦ 抓到的原文：「勾上面那個選項，本頁才會載入自己的一份」——
    而**勾下去正是撞的那一刻**。**說反了比沒說更糟**：使用者照著做就撞。

    ⚠️ **本條的前兩版都被自己的突變殺穿，兩顆都留在這裡當說明**（本機實跑）：

    ==== ============================================== ==========================
    #    突變                                            初版         現版
    ==== ============================================== ==========================
    M4   `where=` 改成指向 gate 自己                      **存活**     轉紅
         （`f"上方「{DELEGATE_GATE_LABEL}」"`）
    M5   本文把「會撞…重複元件 ID」換成「會需要重新載入」   **存活**     轉紅
    ==== ============================================== ==========================

    **M4 為什麼存活**：`where=` 是 f-string，`DELEGATE_GATE_LABEL` 在 AST 上是
    `Name` 節點、**不是字面值** ⇒ 只掃 `ast.Constant` 的初版一個字都看不到它。
    **M5 為什麼存活**：初版寫 `"撞" in said or "重複元件" in said`，而本文**後面還有
    第二個「撞」**（「那一刻就會撞」）⇒ 把前面那句換掉，`or` 照樣成立。
    ⇒ **`or` 串起來的關鍵字檢查，只要文案裡任何一處提過就會過；它擋不住「改掉關鍵那一句」。**
    """
    fn = _delegated_fn()
    guard = _gate_guard(fn, _gate_names(fn))
    assert guard is not None, "沒有 gate 守門子句，本條無從驗起（見上一條）"

    said = " ".join(
        node.value for node in ast.walk(guard)
        if isinstance(node, ast.Constant) and isinstance(node.value, str))

    # ── (a) 後果必須寫出來，而且是**具體**的那一句 ──
    #    刻意用 `and` 不用 `or`：`or` 只要文案任一處提過就過（M5 就是這樣活下來的）。
    for _must in ("撞", "重複元件"):
        assert _must in said, (
            f"灰態本文沒有講出後果（缺「{_must}」）。\n"
            "本文必須明寫：兩邊同時載入會**撞 Streamlit 的重複元件 ID**、畫面會出現紅字塊。\n"
            f"目前字面：{said!r}")

    # ── (b) 不得使用 ⑦ 那個說反了的句型 ──
    for _banned in ("才會載入", "才能載入", "才會顯示"):
        assert _banned not in said, (
            f"灰態本文出現「{_banned}」—— 那是 ⑦ 被抓到的說反句型："
            "把「勾下去」講成解法，而勾下去正是撞的那一刻。\n"
            "要寫的是「勾下去**會發生什麼**」，不是「勾下去才看得到」。")

    # ── (c) `where=`（去哪補）不得指向 gate 自己 ──
    #    ⚠️ 必須同時看**字面值**與 **Name 參照** —— f-string 裡的常數是 `Name`，
    #    只掃 `Constant` 會整個看不到（M4 就是這樣活下來的）。
    _wheres = [k.value for node in ast.walk(guard)
               if isinstance(node, ast.Call)
               for k in node.keywords if k.arg == "where"]
    assert _wheres, "灰態沒有 `where=`（去哪補）—— 線框 Rule 04 三要素缺一。"

    _label = _page_const("DELEGATE_GATE_LABEL")
    for _w in _wheres:
        _names = {n.id for n in ast.walk(_w) if isinstance(n, ast.Name)}
        _lits = " ".join(c.value for c in ast.walk(_w)
                         if isinstance(c, ast.Constant) and isinstance(c.value, str))
        assert "DELEGATE_GATE_LABEL" not in _names and _label not in _lits, (
            "`where=`（去哪補）指向 gate 自己 —— 那就是把「勾下去」講成解法。\n"
            "內容現在真的在舊 ② 分頁，指路應該走 `where_to_find('health')` 指那裡。")
        assert "where_to_find" in _names, (
            "`where=` 沒有走 `where_to_find()` SSOT，而是手抄分頁名 —— "
            "七→五改名之後手抄的指路會指到一個不存在的分頁（本 repo 已發作兩次）。")


# ══════════════════════════════════════════════════════════════════
# 3｜前提守衛：gate 哪天不需要了，要有人叫一聲
# ══════════════════════════════════════════════════════════════════
def test_the_gate_still_has_a_reason_to_exist():
    """gate 的存在前提 ＝ **舊 ② 仍然會畫同一批圖**。前提沒了就該轉紅。

    ⭐ 這一條是「gate」勝過「誠實留白（乾脆不委派）」的**全部理由**：
    留白**不可逆** —— 它把「舊 ② 還在」寫死成永久假設，而**沒有任何機制**
    會在假設失效的那天叫一聲。gate 有本條守著：舊 ② 整批拔除、或它不再委派
    那些會畫 `plotly_chart` 的模組時，本條轉紅 ⇒ 那時就可以把 gate 拿掉。

    ⚠️ 本條紅了**不是** bug，是**該回來重新判斷**的訊號。訊息就是這樣寫的。
    """
    risky_mods = set()
    for p in _delegated_module_paths():
        if any(a in _ALWAYS_REGISTERS and not hk for a, _ln, hk, _os in _st_calls(p)):
            risky_mods.add(p)
    assert risky_mods, "委派模組裡已經沒有無 key 的 plotly_chart —— 見上面第 1 條"

    old_src = OLD_TAB.read_text(encoding="utf-8")
    old_tree = ast.parse(old_src, str(OLD_TAB))
    old_imports = {
        n.module for n in ast.walk(old_tree)
        if isinstance(n, ast.ImportFrom) and n.module}

    # 舊 ② 直接 import 的，加上它經 `fund_grp_health_extras` 橋接的那一批。
    bridge = ROOT / "ui" / "helpers" / "fund_grp_health_extras.py"
    if bridge.exists():
        old_imports |= {
            n.module for n in ast.walk(ast.parse(bridge.read_text(encoding="utf-8")))
            if isinstance(n, ast.ImportFrom) and n.module}

    still = {p for p in risky_mods
             if any(p == ROOT / pathlib.Path(m.replace(".", "/") + ".py")
                    for m in old_imports)}
    assert still, (
        "⚠️ **前提可能已經失效，請回來重新判斷（本條紅了不一定是 bug）**：\n"
        "舊 ② 看起來已經不再委派任何『會畫無 key `plotly_chart`』的模組。\n"
        f"（本頁委派且有風險的模組：{sorted(str(p.relative_to(ROOT)) for p in risky_mods)}）\n"
        "如果舊 ② 真的整批拔除了 ⇒ `_render_delegated_sections` 的 Checkbox Gate "
        "已經沒有存在理由，**請連同本條一起移除**，不要讓一個永久的勾選框留在畫面上。")
