"""⑧ `[新] 標的探索` 接線守衛 —— 只守**別處沒有人在守**的那兩件事。

背景（客戶 2026-09-07「雙軌並行」）
----------------------------------
新 ③（`ui/views/page_03_research.py`）以**新增 Tab** 的形式掛成第 ⑧ 格，
舊 ③（`ui/tab_fund_research.py`）**留在原位一個字都不動**。兩條鏈因此
**在同一次 `st.tabs` run 裡同時渲染** —— Streamlit 一次 run 會把所有分頁的
body 全部執行過，這是本檔存在的前提。

⚠️ **本檔刻意不重複既有守衛**（重複的守衛會讓人以為多了一層，其實只是同一層寫兩遍）：
  - 「⑧ 有沒有掛上、掛的是不是 `render_fund_research`」→ `tests/test_ia_kit.py::_SLOT_RENDER`
  - 「⑧ 的標籤走不走 `preview_tab_label` SSOT、順序對不對」→ `tests/test_wpf_five_tab_wiring.py`
  - 「⑧ 有沒有 try/except 隔離、有沒有走 friendly_error」→ `tests/test_tab_isolation_v19502.py`
  - 「⑧ 在不在 `FETCH_DIAG` 所有權範圍內」→ `tests/test_wpf_five_tab_wiring.py::test_fetch_diag_is_owned_by_app`

本檔只守下面兩件**上面全部加起來也看不到**的事。

════════════════════════════════════════════════════════════════════
1) widget key 命名空間 —— 雙軌並行下最會出事的那一個
════════════════════════════════════════════════════════════════════
新舊 ③ 同時在線，**任何一個具名 key 撞上就是整個 App 當場崩潰**（`DuplicateWidgetID`），
不是某一格壞掉而已。⑤ ↔ ⑦ 已經因為這件事付過一次代價（見
`ui/views/page_05_settings.py::_render_maintain` 那道 Checkbox Gate）。

**接線當下的實測是乾淨的**（2026-09-07，AST，指令見 PR 描述）：
新 ③ 的具名 key 只有 `v03_batch_download` 一個，與舊 ③ 的 17 個 key、
以及其他所有已掛載鏈的 152 個 key，交集**都是 0**；全 repo 18 個 form key 無重複。

**但「現在沒撞」不是守衛。** 本檔守的是**下一次**有人在新 ③ 加 widget 時：
只要 key 帶 `v03_` 前綴，就結構上不可能撞到別頁；而別頁也不准偷用這個前綴。

⛔ **`applied_form()` 把 key 位置傳給 `st.form()`，只掃 `key=` kwarg 會看不到它。**
   本檔因此**兩種形態都掃**。這不是多餘的謹慎 —— 本批第一版掃描器就是只掃 `key=`，
   結構上漏掉全部 18 個 form key（同 `CLAUDE.md §-1.5.1c 判定 2` 記載的
   「字表/樣式選錯 → 掃再多次都漏同一處」）。

════════════════════════════════════════════════════════════════════
2) ⑧ 不得自己畫「🔍 抓取診斷細節」
════════════════════════════════════════════════════════════════════
⑦（`render_fetch_diag_from_session()`）是**無條件**渲染那一塊的；舊 ③ 底下的
`ui/tab2_single_fund.py` 靠 `FETCH_DIAG` 旗標被關掉，所以全站現在剛好一份。
**⑧ 目前一份都沒畫**（本批實測），所以掛上去不會變兩份。
一旦有人在 ⑧ 裡加一塊，`FETCH_DIAG` 旗標**擋不住它**（新 ③ 根本沒 import
`merge_context`）→ ⑦ 與 ⑧ 各一份。本條就是那個當下唯一會響的東西。

════════════════════════════════════════════════════════════════════
3) 無 `key=` 的 widget：(型別, label) 必須全 App 唯一
════════════════════════════════════════════════════════════════════
新 ③ 的 4 個輸入 widget **一個 `key=` 都沒有**，走 Streamlit 自動產生的 ID
（依 (元素型別, label, 其餘參數, form_id) 產生）。**上面第 1 節完全沒有涵蓋這一層。**

**為什麼驗 (型別, label) 就夠**：它是**充分條件** —— 兩個 widget 的 label 不同，
ID 就不可能相同。這條推論**不需要**「form_id 有沒有進雜湊」那個前提（本 repo
沒有 streamlit 可讀原始碼求證，本檔刻意不依賴它）。
⚠️ **反向不成立**：(型別,label) 重複**不代表**一定撞（其餘參數或 form_id 可能不同）。
所以本條紅了要**人工判讀**，補一個具名 `key=`（走 `v03_` 命名空間）就能解。

⛔ **為什麼這一條非有不可（2026-09-07 就地補，起因是一個被推翻的假設）**：
本檔第一版把這一層外包給 `tests/test_app_apptest.py::test_app_runs_without_exception`，
寫著「執行層才是唯一真憑據」。**那句話是假的，已刪。** 獨立稽核在別的批次上實測發現：
`app.py` 每格分頁的 `except Exception` → `friendly_error(level="error")` → **`st.error()`**，
而那條測試只斷言 **`assert not at.exception`** —— **撞 key 會被接住畫成紅字，測試照樣綠**。
（全 repo 也找不到任何「跑完不得有紅字」的斷言；補那一層的工作在 **#819**，不在本檔。）
**把一層安全性外包給一個看不見它的測試，比沒有守衛更危險** —— 因為它會讓人以為驗過了。

════════════════════════════════════════════════════════════════════
⚠️ 本檔**看不到**的形態（誠實揭露，不是免責）
════════════════════════════════════════════════════════════════════
- **動態組出來的 key / label**：f-string / 變數 / `getattr` / dict 派發 / 由參數傳進來的。
  本檔只認**字面值**與**模組層級的字串常數**。
- **執行層本檔一概沒有**：本檔是純靜態的。理由見上方第 3 節那段 ⛔ ——
  這個 repo 目前**沒有**任何測試看得見「畫面上出現了一行紅字」。
"""
from __future__ import annotations

import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = ROOT / "ui" / "views" / "page_03_research.py"

#: ⑧ 這一頁保留的 widget key 前綴。與 `v01_` / `v02_` / `v04_` 同一套慣例。
_NS = "v03_"

#: key 以第一個位置引數傳入的呼叫（**不是** `key=` kwarg）。
#: `applied_form(key)` 直接把它轉交給 `st.form(key, ...)`。
_POSITIONAL_KEY_CALLS = {"st.form", "applied_form", "_applied_form"}


def _module_str_consts(tree: ast.Module) -> dict[str, str]:
    """模組層級的 `NAME = "literal"` / `NAME: str = "literal"`。"""
    out: dict[str, str] = {}
    for node in tree.body:
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, ast.AnnAssign) and node.target is not None:
            targets = [node.target]
        value = getattr(node, "value", None)
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for t in targets:
                if isinstance(t, ast.Name):
                    out[t.id] = value.value
    return out


def _widget_keys(path: pathlib.Path) -> list[tuple[str, int, str]]:
    """(key, lineno, 呼叫名) —— `key=` kwarg **與** 位置傳入的 form key 都收。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    consts = _module_str_consts(tree)
    found: list[tuple[str, int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        try:
            fname = ast.unparse(node.func)
        except Exception:                                    # pragma: no cover
            continue
        for kw in node.keywords:
            if kw.arg == "key" and isinstance(kw.value, ast.Constant) \
                    and isinstance(kw.value.value, str):
                found.append((kw.value.value, node.lineno, fname))
        if fname in _POSITIONAL_KEY_CALLS and node.args:
            a0 = node.args[0]
            if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
                found.append((a0.value, node.lineno, fname))
            elif isinstance(a0, ast.Name) and a0.id in consts:
                found.append((consts[a0.id], node.lineno, fname))
    return found


def _production_py() -> list[pathlib.Path]:
    return [p for p in ROOT.rglob("*.py")
            if not any(part in {".git", "tests", "node_modules", ".venv"}
                       for part in p.relative_to(ROOT).parts)]


# ══════════════════════════════════════════════════════════════════
# 1) key 命名空間
# ══════════════════════════════════════════════════════════════════
def test_page_03_widget_keys_all_live_in_the_v03_namespace():
    """⑧ 的每一個 widget key / form key 都必須以 `v03_` 開頭。

    突變實驗（本批實跑，指令與輸出見 PR 描述）：
    把 `key="v03_batch_download"` 改成 `key="fr_mode"`（舊 ③ 真的有的 key）
    → **本條轉紅**。改成 `key="batch_download"`（沒有前綴）→ **也轉紅**。
    """
    keys = _widget_keys(PAGE)
    # ── 輸入非空斷言：掃不到東西時必須紅，不能靜靜地「全部通過」 ──
    assert keys, (
        f"{PAGE.relative_to(ROOT)} 一個 widget key 都沒掃到 —— "
        "本條會變成恆綠的假守衛。要嘛掃描器壞了，要嘛那一頁的 key 改成了動態組法"
        "（後者請回頭讀本檔開頭的『看不到的形態』並補一條新的守衛）。")
    bad = sorted((k, ln, fn) for k, ln, fn in keys if not k.startswith(_NS))
    assert not bad, (
        f"⑧ 有 widget key 不在 `{_NS}` 命名空間內：{bad}。\n"
        "新舊 ③ 在同一次 `st.tabs` run 裡同時渲染，key 撞上 = 整個 App 當場崩潰"
        "（不是那一格壞掉而已）。前綴是這件事唯一的結構性保證。")


def test_no_other_production_module_squats_on_the_v03_namespace():
    """`v03_` 前綴是 ⑧ 專用 —— 別的 production 檔不准用。

    這條是上一條的另一半：上一條保證「⑧ 的 key 都在命名空間內」，
    這條保證「命名空間裡沒有別人」。**只有兩條同時成立，前綴才真的等於不會撞。**

    突變實驗：在 `ui/tab_fund_research.py` 加一個
    `st.checkbox("x", key="v03_batch_download")` → **本條轉紅**。
    """
    files = _production_py()
    assert len(files) > 100, (
        f"production .py 只掃到 {len(files)} 個 —— rglob 壞了，本條會變成恆綠假守衛")
    squatters: list[tuple[str, str, int]] = []
    for p in files:
        if p == PAGE:
            continue
        try:
            for k, ln, _fn in _widget_keys(p):
                if k.startswith(_NS):
                    squatters.append((str(p.relative_to(ROOT)), k, ln))
        except SyntaxError:                                  # pragma: no cover
            continue
    assert not squatters, (
        f"`{_NS}` 是 ⑧ 專用命名空間，這些檔佔用了它：{sorted(squatters)}")


# ══════════════════════════════════════════════════════════════════
# 2) ⑧ 不得自己畫抓取診斷
# ══════════════════════════════════════════════════════════════════
def test_page_03_never_renders_the_fetch_diag_block_itself():
    """⑧ 不得呼叫抓取診斷的任何一個渲染入口。

    ⑦ 是**無條件**畫那一塊的；舊 ③ 底下那份由 `FETCH_DIAG` 旗標關掉。
    ⑧ **沒有 import `merge_context`**，所以旗標對它完全無效 ——
    一旦它自己畫一份，畫面上就會有兩份，而且沒有任何既有守衛看得到。

    ⛔ 這條**不是**在禁止 ⑧ 顯示抓取失敗的原因。上游 fetcher 塞在
    `holdings["diag"]` 裡的失敗原因字串是**另一件事**，⑧ 現在就在用它，
    本條刻意只認渲染函式名，不認 `diag` 這三個字母。

    突變實驗：在 `ui/views/page_03_research.py` 加一行
    `render_fetch_diag_from_session()` → **本條轉紅**。
    """
    tree = ast.parse(PAGE.read_text(encoding="utf-8"), str(PAGE))
    banned = {"render_fetch_diag_section", "render_fetch_diag_from_session"}
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name in banned:
                hits.append((str(name), node.lineno))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            for a in node.names:
                if a.name in banned:
                    hits.append((a.name, node.lineno))
    assert not hits, (
        f"⑧ 自己畫了抓取診斷：{hits} —— ⑦ 也在畫同一塊，畫面上會有兩份。"
        "那塊的家是 ⑤ / ⑦（線框 §03 已拍板），不要在 ⑧ 再開一份。")


# ══════════════════════════════════════════════════════════════════
# 3) 無 key= 的 widget：(型別, label) 全 App 唯一
# ══════════════════════════════════════════════════════════════════
#: 會產生 widget 的 `st.*` 方法（第一個位置引數是 label）。
_WIDGETS = {
    "text_input", "selectbox", "checkbox", "radio", "slider", "number_input",
    "text_area", "file_uploader", "download_button", "button", "multiselect",
    "toggle", "date_input", "time_input", "color_picker", "camera_input",
    "select_slider", "data_editor", "pills", "segmented_control", "chat_input",
}


def _widget_labels(path: pathlib.Path) -> list[tuple[str, str, int, bool]]:
    """(widget 名, label, lineno, 有沒有具名 key)。label 只認字面值與模組層級常數。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    consts = _module_str_consts(tree)
    out: list[tuple[str, str, int, bool]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr not in _WIDGETS or not node.args:
            continue
        has_key = any(k.arg == "key" for k in node.keywords)
        a0 = node.args[0]
        label: str | None = None
        if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
            label = a0.value
        elif isinstance(a0, ast.Name) and a0.id in consts:
            label = consts[a0.id]
        if label is not None:
            out.append((node.func.attr, label, node.lineno, has_key))
    return out


def test_page_03_keyless_widgets_have_an_app_wide_unique_label():
    """⑧ 沒帶 `key=` 的 widget，其 (型別, label) 不得與全 App 任何一處重複。

    突變實驗（本批實跑）：把 `_LABEL_SOURCE` 由 `"來源"` 改成 `"幣別（外幣/台幣）"`
    （`ui/tab_fund_grp_health.py` 真的有的 `multiselect` label）→ **不會紅**，
    因為型別不同（`selectbox` vs `multiselect`）—— 這是**對的**，型別不同就不會撞。
    改成同型別同 label 才紅，見 PR 描述的 M5 / M6。
    """
    keyless = [(w, lab, ln) for w, lab, ln, hk in _widget_labels(PAGE) if not hk]
    # ── 輸入非空斷言 ──
    assert keyless, (
        f"{PAGE.relative_to(ROOT)} 掃不到任何『無 key 且 label 可解析』的 widget —— "
        "本條會變成恆綠的假守衛。若那一頁的 label 改成動態組法，"
        "請回頭讀本檔開頭的『看不到的形態』並補一條新的守衛。")

    files = _production_py()
    assert len(files) > 100, f"production .py 只掃到 {len(files)} 個 —— rglob 壞了"

    elsewhere: dict[tuple[str, str], list[str]] = {}
    for p in files:
        try:
            for w, lab, ln, _hk in _widget_labels(p):
                if p == PAGE:
                    continue
                elsewhere.setdefault((w, lab), []).append(f"{p.relative_to(ROOT)}:{ln}")
        except SyntaxError:                                  # pragma: no cover
            continue

    clashes = [(w, lab, ln, elsewhere[(w, lab)])
               for w, lab, ln in keyless if (w, lab) in elsewhere]
    assert not clashes, (
        f"⑧ 有無 key 的 widget 與別處同型別同 label：{clashes}\n"
        "Streamlit 對沒有具名 key 的 widget 以 (型別, label, 其餘參數, form_id) 產生 ID，"
        "這是**可能**撞的形狀（不是一定撞 —— 其餘參數或 form_id 可能不同）。\n"
        f"最省事也最明確的解法：給它一個 `{_NS}` 前綴的具名 key。"
    )
