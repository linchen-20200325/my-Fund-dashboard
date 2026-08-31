"""WP-F 七 → 五分頁接線的守衛（`app.py` + `ui/helpers/story_nav.py`）。

線框（客戶已拍板）：`docs/wireframes/fund-wireframe-final.html` §03。
接線內容：`st.tabs` 由 7 → 5、③ 掛合併頁「基金研究」、⑤ 掛合併頁「設定與診斷」、
巢狀 `st.tabs` 消失、`_update_data_registry()` 的直接呼叫隨資料診斷搬進 ⑤ 的 gate 之後。

## 方法（先講清楚，因為本 repo 已實證過弱守衛）

沿用 WP-C／WP-E 的兩把尺：

1. **AST（結構）** —— 用在「這個呼叫有沒有真的被包在那個 `with` 裡面」這種
   **只有形狀能表達**的規則上。字串 grep 在這裡不合格：`app.py` 的註解本身
   就在講 `settings_page_owns`，grep 會被自己的說明文字騙過
   （本 repo 2026-08-28 已實證同型假綠）。
2. **sentinel（行為）** —— 用在「這一塊到底畫了幾次」上。

## 每一條的突變實驗（拿掉約束必須轉紅）寫在各自的 docstring 裡，
   並在 PR 描述附上實跑結果。
"""
from __future__ import annotations

import ast
import contextlib
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "app.py"

#: 接線後 `app.py` 應該掛上的五個頂層分頁 key（順序＝分頁列順序＝站號 ①~⑤）。
_FIVE_KEYS = ["macro", "health", "research", "portfolio", "settings"]


def _app_tree() -> ast.Module:
    return ast.parse(APP.read_text(encoding="utf-8"))


def _call_name(node: ast.AST) -> str:
    """`ast.Call` → 被呼叫者的名字（`a.b.c()` 取 `c`，`f()` 取 `f`；底線前綴剝掉）。"""
    if not isinstance(node, ast.Call):
        return ""
    _f = node.func
    _n = _f.attr if isinstance(_f, ast.Attribute) else getattr(_f, "id", "")
    return str(_n).lstrip("_")


# ══════════════════════════════════════════════════════════════════
# 1) 五個 slot 全部走 tab_label()（不是 4 個 —— 舊測試只涵蓋決策動線 4 站）
# ══════════════════════════════════════════════════════════════════
def _top_level_tabs_call() -> ast.Call:
    """`app.py` 頂層唯一的 `st.tabs([...])` 呼叫。

    ⚠️ 接線後 `app.py` **不該再有第二個** `st.tabs`（舊「參考 / 診斷」的巢狀
    子分頁已隨 ⑤ 合併頁消失）→ 這裡順便把「只有一個」鎖住。
    """
    _calls = [n for n in ast.walk(_app_tree())
              if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "tabs"
              and isinstance(n.func.value, ast.Name) and n.func.value.id == "st"]
    assert _calls, "app.py 找不到 st.tabs(...) 呼叫"
    assert len(_calls) == 1, (
        f"app.py 出現 {len(_calls)} 個 st.tabs —— 七→五之後巢狀分頁應該已經消失；"
        "全站唯一的三層巢狀分頁入口就是舊的「參考 / 診斷」。")
    return _calls[0]


def test_all_five_slots_go_through_tab_label():
    """**五個** slot 都必須是 `tab_label("<key>")` 呼叫，一個字面值都不准有。

    為什麼要新寫一條（既有 `test_app_tabs_are_wired_to_story_nav` 不夠）：
    那一條只遍歷 `_STEPS`（決策動線 **4** 站），**`settings` 不在裡面** ——
    也就是 ⑤ 的分頁名寫成字面值時它照樣綠。這正是本 repo 兩次「第二份標籤」
    事故的形狀：不在清單裡的那個分頁沒人守。

    突變實驗：把任一 slot 改回寫死字串（例如 `"⚙️ 設定與診斷"`）→ **本條轉紅**。
    """
    _elts = _top_level_tabs_call().args[0].elts
    assert len(_elts) == 5, f"app.py 的頂層分頁數不是 5，而是 {len(_elts)}"

    _keys: list[str] = []
    for _i, _e in enumerate(_elts):
        assert isinstance(_e, ast.Call) and _call_name(_e) == "tab_label", (
            f"第 {_i + 1} 個 slot 不是 tab_label(...) 呼叫，而是 "
            f"{ast.dump(_e)[:120]} —— app.py 與 story_nav 又變成兩份標籤。")
        assert _e.args and isinstance(_e.args[0], ast.Constant), (
            f"第 {_i + 1} 個 slot 的 tab_label 參數不是字面 key，無法靜態驗證")
        _keys.append(_e.args[0].value)

    assert _keys == _FIVE_KEYS, (
        f"分頁 key 或**順序**不對：{_keys} != {_FIVE_KEYS}。"
        "順序即站號 ①②③④⑤，不是裝飾。")


def test_slot_keys_all_resolve_in_story_nav():
    """五個 key 都必須真的能從 SSOT 取到標籤（fail loud 會在這裡先炸）。"""
    from ui.helpers.story_nav import tab_label

    for _k in _FIVE_KEYS:
        assert tab_label(_k), f"tab_label('{_k}') 取不到標籤"


def test_old_seven_tab_entrypoints_are_no_longer_imported_by_app():
    """五個舊入口不得再由 `app.py` 直接 import —— 它們現在住在兩個合併頁裡面。

    留著會有兩種讀法（「app.py 到底掛了幾個入口」），而且下一個人很容易
    順手把它們再掛回 `st.tabs`，變成同一塊畫兩次。

    突變實驗：把 `from ui.tab2_single_fund import render_single_fund_tab` 加回
    `app.py` → **本條轉紅**。
    """
    _dead = {
        "render_single_fund_tab", "render_batch_analysis_tab",
        "render_manage_tab", "render_data_guard_tab", "render_manual_tab",
    }
    _imported: set[str] = set()
    for _n in ast.walk(_app_tree()):
        if isinstance(_n, (ast.Import, ast.ImportFrom)):
            _imported |= {a.asname or a.name.split(".")[-1] for a in _n.names}
    _leftover = sorted(_dead & _imported)
    assert not _leftover, (
        f"app.py 仍直接 import 舊分頁入口 {_leftover} —— "
        "七→五之後它們應由 ③/⑤ 兩個合併頁自己 lazy import。")


def test_app_no_longer_calls_update_data_registry_directly():
    """`_update_data_registry()` 的直接呼叫必須隨資料診斷搬進 ⑤ 的 gate 之後。

    它內含一次**真的打網路**的 USDTWD 抓取（`tests/test_audit_20260814_batch01.py`
    的檔頭就是這麼記載的）。留在 `app.py` module body 等於**每次 rerun 無條件跑**，
    而使用者可能根本沒打開 ⑤。它的 caller 契約（「渲染資料診斷前先更新註冊表」）
    已由 `ui/tab_settings_diag.py::_render_diag_section` 承接，並由
    `tests/test_settings_diag_merge.py::test_diag_gate_on_runs_registry_before_data_guard`
    守住順序。

    突變實驗：在 `app.py` 加回一行 `_update_data_registry()` → **本條轉紅**。
    """
    _hits = [n.lineno for n in ast.walk(_app_tree())
             if isinstance(n, ast.Call) and _call_name(n) == "update_data_registry"]
    assert not _hits, f"app.py 仍直接呼叫 _update_data_registry() 於行 {_hits}"


# ══════════════════════════════════════════════════════════════════
# 2) ⭐ 抓取診斷細節：③ 與 ⑤ 不得各畫一份
# ══════════════════════════════════════════════════════════════════
def _fetch_diag_owner_with(tree: ast.Module) -> ast.With | None:
    """回傳 `app.py` 裡那個 `with settings_page_owns(FETCH_DIAG):` 節點（沒有則 None）。

    比對的是**被呼叫者的名字**與**參數的名字**（`_SD_FETCH_DIAG` / `FETCH_DIAG`
    皆可），不是原始碼字串 —— 註解裡也寫著這幾個字，字串比對會假綠。

    ⚠️ **一定要傳入 tree，不能自己 parse。** 本函式的第一版是自己 `ast.parse()`，
    於是 caller 拿到的 owner 節點與 caller 自己那棵樹**屬於兩棵不同的 AST** ——
    任何 `node is owner` 的祖先比對永遠為 False，測試變成**恆綠**。
    實測（2026-08-31 突變 M8）：把所有權 `with` 移進 `with tab_settings:` 裡面，
    `test_fetch_diag_owner_wraps_the_tabs_not_the_other_way_round` **照樣綠燈** ——
    也就是那條守衛當時完全沒有在守。改成共用同一棵樹後該突變才轉紅。
    """
    for _n in ast.walk(tree):
        if not isinstance(_n, ast.With):
            continue
        for _item in _n.items:
            _c = _item.context_expr
            if _call_name(_c) != "settings_page_owns":
                continue
            _argnames = {getattr(a, "id", "") for a in getattr(_c, "args", [])}
            if any(a.lstrip("_").upper().endswith("FETCH_DIAG") for a in _argnames):
                return _n
    return None


def test_fetch_diag_is_owned_by_app():
    """⭐ **本批最重要的一條**：`FETCH_DIAG` 的所有權必須由 `app.py` 持有，
    而且範圍要涵蓋**全部五個**分頁的 `with tab_*:` 區塊。

    為什麼不能讓 ⑤ 自己 `with`（這是本條存在的全部理由）：
    旗標是 thread-local context manager，**只在 `with` 區塊內成立**；而
    Streamlit 的 `st.tabs` 一次 run 會把五個分頁的 body 全部執行過，順序就是
    程式碼順序 —— **③ 跑在 ⑤ 之前**。⑤ 就算把自己整個包起來，那時 ③ 底下的
    `ui/tab2_single_fund.py` 早就把「🔍 抓取診斷細節」畫出去了，回頭關不掉。
    結果就是同一塊在 ③ 與 ⑤ 各出現一次。

    突變實驗：把 `app.py` 的 `with _settings_page_owns(_SD_FETCH_DIAG):` 整個
    拿掉（五個 `with tab_*:` 退回頂層）→ **本條轉紅**。
    只把其中一個 `with tab_*:` 移出該區塊 → **本條也轉紅**（涵蓋範圍檢查）。
    """
    _tree = _app_tree()
    _owner = _fetch_diag_owner_with(_tree)
    assert _owner is not None, (
        "app.py 沒有 `with settings_page_owns(FETCH_DIAG):` —— "
        "「🔍 抓取診斷細節」會在 ③ 與 ⑤ 各畫一份。")

    # 該 with 區塊內含的 `with <name>:` 所使用的變數名
    _inside: set[str] = set()
    for _n in ast.walk(_owner):
        if isinstance(_n, ast.With) and _n is not _owner:
            for _item in _n.items:
                if isinstance(_item.context_expr, ast.Name):
                    _inside.add(_item.context_expr.id)

    # app.py 全檔的 `with tab_*:` 變數名（即五個分頁 context）——**同一棵樹**
    _all_tabs = {
        _item.context_expr.id
        for _n in ast.walk(_tree) if isinstance(_n, ast.With)
        for _item in _n.items
        if isinstance(_item.context_expr, ast.Name)
        and _item.context_expr.id.startswith("tab_")
    }
    assert len(_all_tabs) == 5, f"app.py 的 `with tab_*:` 區塊數不是 5：{sorted(_all_tabs)}"
    _outside = sorted(_all_tabs - _inside)
    assert not _outside, (
        f"這些分頁不在 FETCH_DIAG 的所有權範圍內：{_outside}。"
        "只要有任何一個分頁跑在 `with` 之外，它底下的子頁就會自己畫一份抓取診斷。")


def test_fetch_diag_owner_wraps_the_tabs_not_the_other_way_round():
    """所有權必須**包住**分頁，不是被包在某一個分頁裡面。

    這條擋的是一種很自然的誤修：有人為了讓測試過，把
    `with settings_page_owns(FETCH_DIAG):` 塞進 `with tab_settings:` 裡面 ——
    形狀看起來很像，但那就退回「⑤ 自己 with」，③ 照樣先畫一份。

    突變實驗（2026-08-31 實跑，M8）：把 owner `with` 移進 `with tab_settings:`
    → **本條轉紅**。
    ⚠️ 本條的**第一版是恆綠的假守衛**：`_fetch_diag_owner_with()` 當時自己
    `ast.parse()`，與這裡的 `_app_tree()` 是兩棵樹，`is` 比對永遠不成立 ——
    M8 突變照樣綠燈。修法是共用同一棵樹（見 `_fetch_diag_owner_with` docstring）。
    """
    _tree = _app_tree()
    _owner = _fetch_diag_owner_with(_tree)
    assert _owner is not None
    _ancestors_are_tab = []
    for _n in ast.walk(_tree):
        if not (isinstance(_n, ast.With) and _n is not _owner):
            continue
        if any(_c is _owner for _c in ast.walk(_n)):
            _ancestors_are_tab += [
                _i.context_expr.id for _i in _n.items
                if isinstance(_i.context_expr, ast.Name)
                and _i.context_expr.id.startswith("tab_")]
    assert not _ancestors_are_tab, (
        f"FETCH_DIAG 的 with 被包在分頁 {_ancestors_are_tab} 裡面 —— "
        "那等於回到「⑤ 自己持有」，③ 仍會先畫一份。")


class _Rec:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.session: dict = {}

    def api(self, name: str):
        def _f(*a, **k):
            self.calls.append((name, a[0] if a else None))
        return _f


class _Col:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@contextlib.contextmanager
def _fake_streamlit(monkeypatch):
    import streamlit as st

    rec = _Rec()
    for _n in ("markdown", "caption", "info", "success", "warning", "error",
               "divider", "write", "metric", "dataframe", "subheader",
               "header", "code"):
        monkeypatch.setattr(st, _n, rec.api(_n), raising=False)
    monkeypatch.setattr(st, "columns",
                        lambda spec, **k: [_Col() for _ in range(
                            spec if isinstance(spec, int) else len(spec))],
                        raising=False)
    monkeypatch.setattr(st, "container", lambda *a, **k: _Col(), raising=False)
    monkeypatch.setattr(st, "session_state", rec.session, raising=False)
    monkeypatch.setattr(st, "checkbox", lambda *a, **k: False, raising=False)
    yield rec


def test_flag_actually_flips_the_two_consumers(monkeypatch):
    """行為面補證：旗標**真的**能一邊關掉、另一邊照畫（形狀對了但機制壞掉也會出事）。

    上面兩條 AST 測試證明「app.py 的形狀對」；本條證明「那個形狀有用」——
    兩者缺一不可，因為 AST 測不到 thread-local 是不是真的生效。

    - ③ 端（`ui/tab2_single_fund.py`）：`owned_by_settings_page(FETCH_DIAG)` 為 True
      時跳過（它的 guard 極性另由
      `test_settings_diag_merge.py::test_tab2_fetch_diag_call_is_behind_the_settings_guard`
      以 AST 鎖住）。
    - ⑤ 端（`render_fetch_diag_from_session`）：**無條件**渲染。

    突變實驗：把 `merge_context.settings_page_owns` 的 `_cur.update(parts)` 拿掉
    （context manager 變成空殼）→ **本條轉紅**。
    """
    import ui.helpers.settings_diag.fetch_diag_section as _fds
    from ui.helpers.settings_diag.merge_context import (
        FETCH_DIAG, owned_by_settings_page, settings_page_owns,
    )

    _drawn: list[int] = []
    monkeypatch.setattr(_fds, "render_fetch_diag_section",
                        lambda *a, **k: _drawn.append(1))

    with _fake_streamlit(monkeypatch) as rec:
        rec.session["fund_data"] = {"status": "partial", "fund_name": "測試基金"}
        assert not owned_by_settings_page(FETCH_DIAG), "預設不該有人持有"
        with settings_page_owns(FETCH_DIAG):
            # ③ 端的判斷（tab2 就是這樣問的）
            assert owned_by_settings_page(FETCH_DIAG), (
                "旗標持有中卻回 False —— ③ 會照畫一份，變成兩份")
            # ⑤ 端：無條件畫
            _fds.render_fetch_diag_from_session()
        assert not owned_by_settings_page(FETCH_DIAG), "離開 with 沒有還原（會外洩到下一頁）"

    assert _drawn == [1], f"⑤ 端應該恰好畫一次，實際 {len(_drawn)} 次"


# ══════════════════════════════════════════════════════════════════
# 3) 分頁隔離：五段 try/except 的分頁名不得寫死
# ══════════════════════════════════════════════════════════════════
def test_every_tab_render_is_wrapped_in_isolation():
    """五個 `with tab_*:` 裡面都必須走分頁隔離（一頁炸掉不連坐其他頁）。

    `st.tabs` 單次 run 會渲染全部分頁，任一頁拋未捕捉例外會中止整個 script →
    **其後所有分頁空白**（§1 分頁隔離，v19.429）。

    突變實驗：把任一個 `_render_isolated("x", fn)` 改成直接 `fn()` → **本條轉紅**。
    """
    _bad: list[str] = []
    for _n in ast.walk(_app_tree()):
        if not (isinstance(_n, ast.With)
                and any(isinstance(i.context_expr, ast.Name)
                        and i.context_expr.id.startswith("tab_")
                        for i in _n.items)):
            continue
        _tabname = next(i.context_expr.id for i in _n.items
                        if isinstance(i.context_expr, ast.Name))
        _isolated = [c for c in ast.walk(_n)
                     if isinstance(c, ast.Call) and _call_name(c) == "render_isolated"]
        _has_try = [c for c in ast.walk(_n) if isinstance(c, ast.Try)]
        if not _isolated and not _has_try:
            _bad.append(_tabname)
    assert not _bad, (
        f"這些分頁沒有任何隔離（既不是 _render_isolated 也沒有 try）：{_bad} —— "
        "它們一炸，後面所有分頁會整片空白。")


def test_tab_error_titles_go_through_tab_label():
    """分頁隔離的錯誤標題不得寫死分頁名 —— 名字只准有一個來源。

    原本五段 try/except 各自帶一份中文分頁名（「「🌐 市場定調」分頁渲染失敗」…），
    分頁一改名就會有人漏改；2026-08-05 與 08-14 兩次稽核抓到的都是這個形狀。

    突變實驗：把 `_render_isolated` 的 f-string 改成寫死
    `f"「🌐 市場定調」分頁渲染失敗"` → **本條轉紅**。
    """
    _src = APP.read_text(encoding="utf-8")
    _tree = ast.parse(_src)

    # 找出所有「分頁渲染失敗」訊息所在的字串（含 f-string 片段）
    _fail_msgs = [n for n in ast.walk(_tree)
                  if isinstance(n, ast.JoinedStr)
                  and "分頁渲染失敗" in ast.unparse(n)]
    # ⚠️ f-string 的**固定片段**（`」分頁渲染失敗`）在 AST 裡也是 `ast.Constant`，
    #    直接掃 Constant 會把合規的寫法誤判成寫死（本檔第一版就是這樣紅的）。
    #    故先把 JoinedStr 底下的 Constant 全部排除，只留真正獨立的字串常數。
    _in_fstring = {id(c) for m in _fail_msgs for c in ast.walk(m)
                   if isinstance(c, ast.Constant)}
    _plain = [n for n in ast.walk(_tree)
              if isinstance(n, ast.Constant) and isinstance(n.value, str)
              and "分頁渲染失敗" in n.value and id(n) not in _in_fstring]
    assert not _plain, (
        f"分頁隔離的錯誤標題是寫死字串：{[n.value for n in _plain]} —— "
        "分頁名必須走 story_nav.tab_label()。")
    assert _fail_msgs, "找不到任何「分頁渲染失敗」訊息 —— 分頁隔離被移除了？"
    for _m in _fail_msgs:
        assert "tab_label" in ast.unparse(_m), (
            f"錯誤標題沒有走 tab_label()：{ast.unparse(_m)[:120]}")


# ══════════════════════════════════════════════════════════════════
# 4) 指路文案：指到「頁內分區」的地方必須走 where_to_find()
# ══════════════════════════════════════════════════════════════════
#: (檔案, 該檔指到的分區 key)。
#: ⚠️ 這張表**不是窮舉** —— 它是本組單組 grep 的結果，只鎖已知的這幾處。
_SECTION_HINT_SITES = (
    ("ui/helpers/fund_grp_health/ai.py", "fund"),
    ("ui/helpers/settings_diag/fetch_diag_section.py", "fund"),
)


@pytest.mark.parametrize("relpath,key", _SECTION_HINT_SITES,
                         ids=[p.split("/")[-1] for p, _ in _SECTION_HINT_SITES])
def test_section_hints_use_where_to_find(relpath: str, key: str):
    """指到**頁內分區**的文案必須吃 `where_to_find()`，且不得殘留舊分頁名字面值。

    為什麼要新開一條（既有測試蓋不到這兩處）：
    - `ui/helpers/fund_grp_health/ai.py` 原本寫 `tab_label('fund')` ——
      七→五之後**會 KeyError**，但它只在「前十大持股名稱全空」時才走到，
      **全 repo 沒有任何測試覆蓋那條分支**（跑全套也看不到的 latent 破壞）。
    - `ui/helpers/settings_diag/fetch_diag_section.py` 原本把
      `"🔍 個基深掘 → 輸入代碼 → 🚀 分析"` **寫死成字串**，不經 `tab_label`
      所以**連 raise 都不會** —— 只會安靜地指到一個分頁列上不存在的名字。
      **「不會炸、只會指錯」才是最難發現的那一種。**

    突變實驗（2026-08-31 實跑，見 PR 突變表 N7／N8）：
    - `ai.py` 的 `where_to_find('fund')` 改回 `tab_label('fund')` → **本條轉紅**。
    - `fetch_diag_section.py` 的 `where=` 改回寫死「🔍 個基深掘 …」→ **本條轉紅**。
    """
    from ui.helpers.story_nav import _SECTION_LABELS, tab_label

    _src = (ROOT / relpath).read_text(encoding="utf-8")
    _tree = ast.parse(_src)

    # (a) 該 key 真的被傳進 where_to_find(...)
    _passed = [c.args[0].value for c in ast.walk(_tree)
               if isinstance(c, ast.Call) and _call_name(c) == "where_to_find"
               and c.args and isinstance(c.args[0], ast.Constant)]
    assert key in _passed, (
        f"{relpath} 沒有 where_to_find('{key}') 呼叫 —— "
        f"指到頁內分區的文案必須帶上所屬分頁名（否則使用者在分頁列上找不到）。")

    # (b) 不得再把分區 key 傳給 tab_label（七→五之後那會 KeyError）
    _bad = [c.args[0].value for c in ast.walk(_tree)
            if isinstance(c, ast.Call) and _call_name(c) == "tab_label"
            and c.args and isinstance(c.args[0], ast.Constant)
            and c.args[0].value in _SECTION_LABELS]
    assert not _bad, (
        f"{relpath} 仍把分區 key {_bad} 傳給 tab_label() —— 七→五之後會 KeyError")

    # (c) 不得殘留舊分頁名的**活字串**（docstring／註解講歷史可以）
    _docs = set()
    for _n in ast.walk(_tree):
        if isinstance(_n, (ast.Module, ast.FunctionDef,
                           ast.AsyncFunctionDef, ast.ClassDef)):
            _b = getattr(_n, "body", None)
            if (_b and isinstance(_b[0], ast.Expr)
                    and isinstance(_b[0].value, ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _docs.add(id(_b[0].value))
    _live = [n.value for n in ast.walk(_tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str)
             and id(n) not in _docs]
    for _dead in ("🔍 個基深掘", "📦 批次分析", "📋 我的管理室"):
        _hits = [s for s in _live if _dead in s]
        assert not _hits, (
            f"{relpath} 仍有舊分頁名「{_dead}」的活字串：{_hits} —— "
            f"它不經 tab_label 所以不會 raise，只會安靜地指錯地方。")
    # 順帶確認新分頁名沒有被手抄成第二份
    assert not [s for s in _live if tab_label("research") in s], (
        f"{relpath} 手抄了分頁名「{tab_label('research')}」—— 應由 where_to_find 產生")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
