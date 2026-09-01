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
import re

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

    # ⚠️ **必須把 alias 解析回原函式名，不能看呼叫點長什麼樣**（2026-08-31 補）。
    # ~~舊寫法 `assert "tab_label" in ast.unparse(_m)`~~ 是**純字串比對**：
    # 它只問「這段 f-string 的原始碼裡有沒有出現 `tab_label` 這七個字」。
    # **有意識的政策變更，不是漏改**（日期 2026-08-31 · 決策者：AI 總管）。
    # 舊寫法的理由**仍然成立** —— 它比「完全不檢查」強，而且抓得到「把標題改回
    # 寫死字串」這個最常見的突變（那種寫法連 `tab_label` 三個字都沒有）。
    # 被權衡掉的原因：它與本檔下方 `test_section_hints_use_where_to_find` 修過的
    # **N10 是同一個洞**，只是沒人回頭補這一處。實測（2026-08-31，本批重跑）：
    # 把 `app.py` 的 import 改成 `section_label as _tab_label_err` 並在五段 f-string
    # 裡呼叫 `_tab_label_err('macro')` —— 呼叫點的原始碼**含有 `tab_label` 這七個字**
    # （它是 alias 名字的一部分），舊斷言 **23 passed 全綠**；而實際執行時
    # `section_label('macro')` 會 `KeyError`，例外從 `except` handler 內部拋出
    # → **逸出分頁隔離**，整個 script run 中止，渲染元素由 126 掉到 13（全站空白）。
    # **守衛全綠、畫面全白**，正是本 repo 已實證過兩次的假守衛形狀。
    # 修法比照下方那一條：用 `ImportFrom` 建 alias → 原名 的對照表。
    _alias: dict[str, str] = {}
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.ImportFrom) and (_n.module or "").endswith("story_nav"):
            for _a in _n.names:
                _alias[_a.asname or _a.name] = _a.name

    for _m in _fail_msgs:
        _resolved = set()
        for _c in ast.walk(_m):
            if isinstance(_c, ast.Call):
                _nm = getattr(_c.func, "id", None) or getattr(_c.func, "attr", None)
                if _nm:
                    _resolved.add(_alias.get(_nm, _nm))
        assert "tab_label" in _resolved, (
            f"錯誤標題沒有**真的**呼叫到 story_nav.tab_label()："
            f"{ast.unparse(_m)[:120]}；解析出來的呼叫 = {sorted(_resolved)}，"
            f"已解析的 story_nav alias = {_alias}。\n"
            "（只是名字裡帶 `tab_label` 三個字不算 —— 那是 N10 那個洞。）")


# ══════════════════════════════════════════════════════════════════
# 4) 指路文案 SSOT —— **全 repo 掃描，兩條並行**
# ══════════════════════════════════════════════════════════════════
# ⚠️ 這一節在 2026-08-31 被整段重寫。**有意識的政策變更，不是漏刪**
#    （日期 2026-08-31 · 決策者：AI 總管）。
#
# ~~舊設計：`_SECTION_HINT_SITES` 三檔白名單 + `test_section_hints_use_where_to_find`
#   逐檔 parametrize。~~
#
# **舊設計的理由仍然成立**：它把當時已知的三處鎖得很死（(a) 真的呼叫到
# `where_to_find` (b) 不得把分區 key 傳給 `tab_label` (c) 不得殘留舊分頁名活字串），
# 三條檢查本身都是對的，而且它自己就誠實寫著「⚠️ 這張表**不是窮舉**」。
#
# **被權衡掉的原因**：那句誠實的自述正是它的死因 —— 一份白名單**結構上**抓不到
# 名單外的第 N+1 處。2026-08-31 稽核實測：本批打壞的 6 處指路文案，
# **一處都不在那三個檔裡**，守衛全綠。這與本 repo 已發作三次的同一個病同源
# （2026-08-05 必修 2、2026-08-14 sidebar 三處、2026-08-31 本次）。
#
# ⚠️ **而且「換成黑名單」也不夠** —— 這一點是本次最重要的發現，寫在最前面：
# 另一組同日撿到 4 處寫著「組合配置」的指路文案，而「組合配置」
# **從來沒有進過任何一版的 `_TAB_LABELS`**（④ 七→五前叫「📊 配置 & 帳本」、
# 之後叫「📊 我的配置」）。也就是說，**任何以「比對歷史分頁名」為基礎的字表，
# 結構上都掃不到「有人憑印象發明的新錯名字」** —— 那只是把白名單換一層皮。
#
# 故本節是**兩條並行的守衛，缺一不可**：
#   1. **黑名單向**（`test_no_live_string_hardcodes_a_tab_name`）——
#      字表 = 現行 `_TAB_LABELS` 值 ∪ `RETIRED_TAB_LABELS` ∪ `MISWRITTEN_TAB_NAMES`，
#      **單一出處在 `ui/helpers/story_nav.py`**，本檔不另存一份。
#      它同時擋「指到已退役的分頁」與「把現行分頁名手抄第二份」。
#   2. **形態向**（`test_navigation_hints_go_through_story_nav`）——
#      活字串帶「指路形狀」卻沒有經過 `tab_label` / `where_to_find` / `section_label`
#      求值 → 紅。**這條不依賴任何字表**，所以「有人又發明一個新錯名字」也擋得住。
#      驗收突變（2026-08-31 實跑，見 PR 突變表 F-M6）：在任一 UI 檔加一句
#      `st.caption("請到「隨便一個沒人聽過的分頁」看")` → **本條轉紅**。
#
# 另補第 3 條（`test_no_section_key_reaches_tab_label`）：舊設計的檢查 (b) 也
# 全 repo 化 —— `tab_label('fund'/'batch'/'manage'/'diag'/'manual')` 會 `KeyError`。

#: 掃描範圍：production 端會渲染給使用者看的程式碼。
#: ⚠️ **`tests/` 不在範圍內是刻意的、且不是「整目錄豁免」**：測試裡的字串是
#: **期望值**，本來就必須寫得出具體的名字（否則測試等於拿被測物驗被測物）。
#: 但期望值**不該寫死已失效的名字** —— 那會變成「保護 bug 不被修掉」的測試，
#: 本批就修過一個實例（`tests/test_alloc_weight_mode_honesty.py` 原本把
#: 「組合配置」釘成期望值）。那一類要靠 code review，不是靠本節。
_SCAN_GLOBS = ("ui/**/*.py", "services/**/*.py", "repositories/**/*.py",
               "shared/**/*.py", "infra/**/*.py")
_SCAN_EXTRA = ("app.py",)

#: 指路形狀（形態向用）。三個 pattern 是**互補**的，不是同義：
#:   A  「X」分頁 / 「X」Tab      —— 帶分頁詞的引用名
#:   A2 分頁「X」                —— 反向語序
#:   B  請至 / 請先到 / 切到「X」 —— **不帶分頁詞**的導引（本批 6 處裡有 3 處是這種）
#: ⚠️ B 的動詞表刻意**不含**單字「去」：實測會把「減去「過去 12 個月最低值」」
#:    這種數學說明誤判成指路（2026-08-31 調參時實際踩到）。
_QUOTED = r"[「『][^」』]{1,24}[」』]"
_NAV_SHAPES = (
    re.compile(_QUOTED + r"[^\S\n]{0,2}(?:分頁|頁籤|Tab)"),
    re.compile(r"(?:分頁|頁籤|Tab)[^\S\n]{0,2}" + _QUOTED),
    re.compile(r"(?:請至|請到|請先到|先到|切到|切換到|回到|前往)[^\S\n]{0,3}" + _QUOTED),
)

#: story_nav 的三個求值入口（alias 會被解析回這些名字）。
_NAV_FNS = frozenset({"tab_label", "section_label", "where_to_find"})

# ── 豁免表 ─────────────────────────────────────────────────────────────
# ⚠️ **逐條具名 + 附理由，不得整檔或整目錄豁免。** 格式：(相對路徑, 字串片段, 理由)。
# 只有「檔案相符 **且** 該片段出現在那個字串裡」才豁免 —— 換句話說，同一個檔案裡
# **其他**字串照樣受檢。

#: (1) **真的合規**：這些字串不是指路文案，或它指的東西本來就不是頂層分頁。
_LEGIT_EXEMPT: tuple[tuple[str, str, str], ...] = (
    ("ui/helpers/story_nav.py", "",
     "本模組**就是** SSOT 本身 —— 分頁名與分區名的字面值定義在這裡，"
     "退役名字表也在這裡。掃描它等於要求 SSOT 不准定義自己。"),
    ("ui/tab3_portfolio.py", "組合配置與健康度",
     "AI 摘要 prompt 的**章節標題**（`_sections_t3` 清單），不是指路文案 —— "
     "它是要 AI 產出的段落名，使用者不會拿它去分頁列上找東西。"
     "它命中黑名單純粹因為字面上包含「組合配置」四個字。"),
    ("ui/tab6_manual.py", "📚 宏觀教學文獻",
     # ⚠️ 2026-08-31 理由文字更正（**有意識的更正，不是漏刪** · 決策者：AI 總管）。
     # ~~舊理由：「說明書**自己那層 `st.tabs`** 的子分頁名（`_t6`）」~~ ——
     # 說明書已於 2026-08-31 改為單頁 + 錨點目錄，`_t6` 那層 `st.tabs` 連同它的
     # 子分頁名一起消失，**舊理由指向一個不存在的東西**。
     # **舊理由在寫下的當天是對的**，被權衡掉的只是它的狀態；
     # **豁免本身實質未變** —— 這個字串現在是 `_CHAPTERS` 的**目錄短標**，
     # 由本檔自己建立、自己引用，仍然**不是** `_TAB_LABELS` 管的頂層分頁名。
     # ⚠️ 只改理由文字，needle 與豁免範圍一字未動（needle 仍命中，本條原本就不會紅）。
     "說明書**自己的章節目錄短標**（`ui/tab6_manual.py::_CHAPTERS` 第 2 欄），"
     "由本檔自己建立、自己引用（目錄與章節標題都從這張表產生），"
     "不是 `_TAB_LABELS` 管的頂層分頁。story_nav 的兩張表都不該收它"
     "（收了會讓 `tab_label()` 回一個頂層分頁列上不存在的名字，正是它要防的事）。"),
)

#: (2) **已知的既有債 —— 不是合規，只是本批未受指派**。
#: ⚠️ 這張表與 `_LEGIT_EXEMPT` **性質完全不同**，刻意分開兩個常數而不是併成一個：
#: 併起來會讓「這樣寫是對的」與「這樣寫是錯的、還沒修」長得一模一樣，
#: 那正是 `CLAUDE.md §8.2.A.0 規則 5` 點名的「把違憲寫成合憲」。
#: **歸因**：以下每一條在 `origin/main` 上就已經指向不存在的東西，
#: **不是七→五打壞的**。本批的授權範圍是稽核點名的 6 處回歸 + 協調者指派的 4 處，
#: 這些**不在其中**（`CLAUDE.md §-1`：沒有指派、沒有 bug 觸發就不動工；
#: `§8.4 步驟 4`：範圍要不要擴大是客戶 / 總管的決定，不是執行組自己拍板）。
#: 已在 PR 描述具名回報，等總管裁決是否納入下一批。
# **出處（怎麼找到的、憑什麼說是「既有債」）—— 下一批的接手依據**
# - **發現方式**：2026-08-31 本節兩條守衛首次全 repo 開跑時命中，不是人工翻出來的。
#   每條的「由哪一條抓到」寫在該條理由的開頭（黑名單向 / 形態向）。
# - **「既有債」不是本組的口頭宣稱，是實測**：下列 7 條的字串**逐條**在
#   `origin/main`（`8eb13b8`）上比對過，**全部命中** → 它們在本批動手之前就已經存在，
#   **不是七→五打壞的**。複驗指令（下一批可直接重跑）：
#       for p in <path>; do git show origin/main:$p | grep -F '<needle>'; done
#   ⚠️ 本檢查**刻意不寫成測試**：CI 的 `actions/checkout@v4` 預設 `fetch-depth: 1`，
#   `origin/main` 不保證存在，寫成測試會在 CI 變成偽紅。
#
#   ⛔ **上面那條指令有一個邏輯缺口，下一批沿用前必讀**（2026-08-31 第三組複驗指出）：
#   它只證明「**這個字串在 main 上存在**」，**不證明「它在 main 上當時就已經是錯的」**。
#   兩者不同 —— 一個字串可以在 main 上逐字存在、而且**當時完全正確**，
#   是後來的改動把它變錯的（那就是**回歸**，不是既有債）。
#   **反例就發生在本批**：`ui/tab6_manual.py` 的「Tab2 個基深掘」在 main 上逐字存在，
#   但「個基深掘」當時**是有效的分頁名** —— 是七→五把它降級成分區才變錯。
#   前一版就是這樣把 2 處**本批回歸**誤分類成「誤判」，第三組複驗才抓出來。
#   → **完整判準需要兩步**：
#       (1) 該 needle 在 `origin/main` 上存在？（上面那條指令）
#       (2) **該 needle 引用的標籤，有沒有被那一批退役掉？**
#           查法：拿 needle 裡的名字去比對該批**改動前後**的 `_TAB_LABELS`
#           （本批即 `git show origin/main:ui/helpers/story_nav.py` 的 `_TAB_LABELS`
#            vs 現行 `_TAB_LABELS` ∪ `RETIRED_TAB_LABELS`）。
#       **(1) 成立且 (2) 否** → 既有債；**(1) 成立但 (2) 是** → **那是回歸，必修，不是債。**
# - **處置決定**：**不納入 #744**（2026-08-31，決策者：AI 總管）。理由是本批已從
#   「修 2 項必修」長到動了十幾個檔，再吞這 7 條會讓它自己變成下一個難以複驗的大批次；
#   且這 7 條沒有「使用者正在被誤導」的急迫性（它們在 main 上已經存在一段時間）。
#   → **另立獨立一批，排在 #744 合併之後。**
_KNOWN_DEBT: tuple[tuple[str, str, str], ...] = (
    ("ui/helpers/macro/linkage.py", "「總經」Tab",
     "【形態向抓到｜main 已存在】既有債：「總經」不是任何時期的分頁名"
     "（① 一直叫「🌐 市場定調」）。修法明確：`tab_label('macro')`，屬字串修正、無設計決定。"),
    ("ui/helpers/portfolio/fee_deduction.py", "「💼 T7 帳本」",
     "【形態向抓到｜main 已存在】既有債：T7 帳本是 ④ **頁內**的區塊，不是分頁；"
     "且它不在 `_SECTION_LABELS` 裡 —— 要修得先決定「④ 的頁內區塊要不要進分區 SSOT」，"
     "**那是設計決定，不是字串修正**（下一批要先答這題，才動得了這條與 tab3_t7 那條）。"),
    ("ui/tab1_macro_ai.py", "「🔬 資料診斷」",
     "【形態向抓到｜main 已存在】既有債：emoji 就寫錯了（現行分區是「🔭 資料診斷」，"
     "🔬 vs 🔭）。修法明確：`where_to_find('diag')`，屬字串修正、無設計決定。"),
    ("ui/tab2_single_fund.py", "請至「資料診斷」",
     "【形態向抓到｜main 已存在】既有債：少了所屬分頁名，使用者在分頁列上找不到"
     "「資料診斷」。修法明確：`where_to_find('diag')`，屬字串修正、無設計決定。"),
    ("ui/tab3_t7_ledger.py", "請至「📋 保單管理」",
     "【形態向抓到｜main 已存在】既有債：保單管理是 ④ 頁內區塊，"
     "**與 `fee_deduction` 那條卡在同一個設計決定上**（頁內區塊要不要進分區 SSOT），"
     "兩條應在同一批一起處置，不要拆開修。"),
    ("ui/tab5_data_guard.py", "「組合基金」Tab",
     "【形態向抓到｜main 已存在】既有債：「單一基金」/「組合基金」都不是任何時期的"
     "分頁名。⚠️ 修法**不完全明確**：「組合基金」語意上可能指 ② 也可能指 ④，"
     "下一批要先確認它實際要把使用者送去哪裡，不可望文生義。"),
    ("ui/tab5_data_guard.py", "Tab 4 組合配置",
     "【黑名單向抓到（`組合配置` 在 `MISWRITTEN_TAB_NAMES`）｜main 已存在】"
     "既有債，且**不只這一列**：同一張診斷總表有「🌐 Tab 1 …／🔍 Tab 2 單一基金／"
     "💊 Tab 3 組合健診／📊 Tab 4 組合配置」四列，站號與名字在七→五之後全部對不上"
     "（組合健診現在是 ②、不是 Tab 3）。修它是**整張表重寫**，屬 scope 決定。"
     "⚠️ 其中「💊 Tab 3 組合健診」那一列**兩條守衛目前都抓不到**"
     "（去 emoji 變體不在字表、句子也不帶指路形狀）—— 見上方"
     "`test_no_live_string_hardcodes_a_tab_name` docstring 的『盲點』段。"),
)


def _docstring_ids(tree: ast.Module) -> set:
    """module / class / function 的 docstring 節點 id —— 掃描一律排除。

    理由：docstring 與註解是**講歷史**的地方（本 repo 的慣例就是「舊條文保留不刪、
    加刪除線 + 兩邊理由並陳」），把它們算進去等於禁止記錄歷史。
    註解根本不進 AST，天然排除。
    """
    _out: set = set()
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.Module, ast.FunctionDef,
                           ast.AsyncFunctionDef, ast.ClassDef)):
            _b = getattr(_n, "body", None)
            if (_b and isinstance(_b[0], ast.Expr)
                    and isinstance(_b[0].value, ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _out.add(id(_b[0].value))
    return _out


def _scan_files() -> list:
    _fs = []
    for _g in _SCAN_GLOBS:
        _fs += list(ROOT.glob(_g))
    _fs += [ROOT / _x for _x in _SCAN_EXTRA]
    return sorted({_f for _f in _fs if _f.is_file()})


def _live_strings(path: pathlib.Path):
    """(字串, 行號) —— 只回**活字串**（非 docstring、非註解）。"""
    _tree = ast.parse(path.read_text(encoding="utf-8"))
    _docs = _docstring_ids(_tree)
    for _n in ast.walk(_tree):
        if (isinstance(_n, ast.Constant) and isinstance(_n.value, str)
                and id(_n) not in _docs):
            yield _n.value, _n.lineno


def _story_nav_alias(tree: ast.Module) -> dict:
    """`from ...story_nav import X as _y` → {_y: X}。

    ⚠️ **不能只看呼叫點的名字** —— 呼叫點叫什麼是呼叫者自己取的（N10 突變：
    `tab_label as _where_to_find`，呼叫點一個字不用改就能騙過字串比對）。
    """
    _a: dict = {}
    for _n in ast.walk(tree):
        if isinstance(_n, ast.ImportFrom) and (_n.module or "").endswith("story_nav"):
            for _nm in _n.names:
                _a[_nm.asname or _nm.name] = _nm.name
    return _a


def _exempted(relpath: str, text: str) -> str:
    """回傳豁免 / 既有債的理由字串；都不符合則回 ""。"""
    for _tbl in (_LEGIT_EXEMPT, _KNOWN_DEBT):
        for _p, _needle, _why in _tbl:
            if relpath == _p and (_needle == "" or _needle in text):
                return _why
    return ""


def test_no_live_string_hardcodes_a_tab_name():
    """**黑名單向**：活字串不得含任何「分頁名」字面值（現行的也不行）。

    字表的三個來源與**為什麼三個都要**：
    - **現行 `_TAB_LABELS` 值** —— 手抄一份現行名字不會馬上壞，但**下一次改名就會漏改**。
      本 repo 分頁改名漏改已發作三次，每次都是這個形狀。
    - **`RETIRED_TAB_LABELS`** —— 已退役的名字，寫在文案裡就是**現在就已經指錯**。
    - **`MISWRITTEN_TAB_NAMES`** —— 從來不存在、憑印象手寫的名字（如「組合配置」）。

    ⚠️ **字表的唯一出處是 `ui/helpers/story_nav.py`**，本檔不另存一份 ——
    測試自己抄一份字表，就是它要禁止的那個行為的翻版。

    突變實驗（2026-08-31 實跑，PR 突變表 F-M2）：把
    `ui/helpers/settings_diag/policy_admin_bridge.py` 的 `where=` 改回寫死
    `"📊 配置 & 帳本 → 📋 保單管理（Google Sheets）"` → **本條轉紅**。

    ## ⚠️ 本條的**實際涵蓋範圍**（2026-08-31 補；不得讀成「涵蓋所有退役名字」）

    **比對規則是「完整標籤（含 emoji 前綴）的子字串出現」。**
    也就是說，它擋得住「**原封抄整個標籤**」，擋不住「**只抄名字、丟掉 emoji**」
    或「把標籤改寫成別的形狀」。

    ### F-M3 的根因（稽核點名要查清楚的那一條，逐項實測）

    突變：把 `ui/tab6_manual.py` 的指路改回 `"🔭 資料診斷(「參考 / 診斷」分頁內)"`。
    **本條照樣綠。** 逐項驗過：

    | 問題 | 實測 |
    |---|---|
    | 「📖 參考 / 診斷」有沒有在 `RETIRED_TAB_LABELS` 裡？ | **有** |
    | 突變字串裡有沒有完整標籤「📖 參考 / 診斷」？ | **沒有** |
    | 突變字串裡有沒有「參考 / 診斷」（去掉 emoji）？ | **有** |

    → **不是字表漏了這個值，是那個寫法讓子字串比對不成立**：
    程式碼只抄了標籤的「名字」那半，`📖 ` 前綴沒抄。
    **同一個突變由形態向那一條抓到**（「參考 / 診斷」＋`分頁` 命中指路形狀）。

    ### 為什麼**刻意不**把「去 emoji 變體」加進字表（實測後的取捨，不是懶）

    實測（2026-08-31 收尾批，**必修 1 修完後的現行樹**）：加進去會多出
    ~~**11 處**~~ **10 處**命中，拆解為 ~~**3 處真死指路 + 8 處真誤判**~~
    **3 處真死指路 + 7 處真誤判**。
    ~~誤判那 8 處是：~~ **誤判當時列了 8 處，末筆已失效 → 現行 7 處**，逐項是
    （有意識的更正，不是漏刪 · 2026-08-31 · AI 總管 · 原因同下方 ⚠️ 更正註）：
    「組合健診大表」是**表名**（`tab_batch_analysis` ×5）、
    「### 💊 基金組合健診」是本頁自己的**區塊標題**、
    `merge_context.py`「未知的『設定與診斷』區塊名稱」是**錯誤訊息**、
    ~~`app.py` 的 **CSS 字串**~~（⚠️ **本 PR 已將該處自 live string 移入 Python 註解，
    此命中不再存在** —— 有意識的更正，不是漏刪 · 2026-08-31 · AI 總管）。
    ~~把 8 個假豁免塞進豁免表~~ **把 7 個假豁免塞進豁免表**（有意識的更正，不是漏刪 ·
    2026-08-31 · AI 總管 · 原因同下方 ⚠️ 更正註），換來的涵蓋率**形態向已經免費提供**，
    而且會讓豁免表本身變得沒人讀得完（豁免表一長，它就退化成白名單）。

    ⚠️ **有意識的更正，不是漏刪**（日期 **2026-08-31** · 決策者 **AI 總管** · 依據：本組拿
    本守衛自己的 `_scan_files()` / `_live_strings()` / `_exempted()` 重跑同一個實驗 ——
    `b2bd587` = **11**、`d2d6c38` = **10**，差的正是上面被劃掉的那一筆）。
    **兩邊理由並陳**：舊表述「11 / 8」**在它寫下的當天是對的** —— `app.py` 那一筆命中當時
    真的存在；**是本批自己的「必修 2」把它變成不成立的**（該處敘述已從 live string 移進
    Python 註解）。
    ⚠️ **這一筆的失效形態與前三輪不同，請記著**：前三輪抓到的都是「**diff 裡新寫的假話**」，
    這一筆是「**diff 讓別處的真話變成假話**」—— 本檔這一輪一行都沒改，是被 `app.py` 的改動
    **從外部弄假的**。**它不在 diff 裡，所以只讀 diff 的自掃結構上掃不到它。**

    ⚠️ **這個數字前一版寫錯過，更正紀錄留著（§-2 規則 6）**
    ~~前一版寫「13 處命中，其中 **10 處是真誤判**」。~~
    **有意識的更正，不是漏改**（日期 2026-08-31 · 決策者：AI 總管 · 依據：第三組複驗實測）。
    正確拆解是 **3 真死指路 + 2 被誤分類 + 8 誤判**：被歸進「誤判」的那 2 處
    （`ui/tab6_manual.py` 的「Tab2 個基深掘的「四分位」燈號」與
    「#### B. 個基深掘的「四分位」」）**其實是真死指路，而且 AppTest 實測使用者看得到**。
    ⚠️ **它們是本批的回歸、不是既有債** ——「個基深掘」在 `origin/main` 上是**有效的分頁名**，
    是七→五把它變成退役名，與已列為必修並修掉的那 6 處**完全同類**；
    漏網的唯一原因就是本節這個去 emoji 盲點。**兩處已於同批修掉**，
    故~~現行命中降為 11~~ **當時降為 11（13−2）；本輪 `app.py` 那筆移出 live string 後，
    現行為 10**（有意識的更正，不是漏刪 · 2026-08-31 · AI 總管 · 原因同上方 ⚠️ 更正註）。
    **本 docstring 是指定給下一批的交接依據，把真死指路寫成誤判會讓下一批建立在假前提上
    繼續蓋 —— 那正是 §-2 規則 6 點名最貴的一步。**

    ⚠️ **剩下的 3 處是真的、而且兩條守衛目前都抓不到**（誠實登記，交下一批）：
    `ui/tab5_data_guard.py`「💊 Tab 3 組合健診」（與 `_KNOWN_DEBT` 已收的
    「Tab 4 組合配置」是**同一張診斷總表的不同列**）、
    `ui/tab_manage.py`「先到 Tab④/組合健診 載入基金」、
    同檔「或到組合健診載入基金」。
    後兩者**不帶引號、也不帶「分頁 / Tab」緊接名字**，所以形態向也掃不到。
    ⛔ **不得**把「本條 + 形態向都綠」讀成「這個檔沒有死指路」。

    ### 兩條的盲點各自在哪（合起來仍不是全覆蓋）

    | | 擋得住 | **擋不住** |
    |---|---|---|
    | 黑名單向（本條） | 原封抄整個標籤（含 emoji）、手抄現行分頁名 | 丟掉 emoji 的變體、改寫過的標籤、**全新發明的錯名字** |
    | 形態向 | 句子帶「「X」分頁 / 分頁「X」/（請至 · 請到 · 請先到 · 先到 · 切到 · 切換到 · 回到 · 前往）「X」」的形狀 | ① **不帶引號**的指路句（「先到組合健診載入基金」）；② 不帶「分頁 / Tab」字樣；③ **帶引號但導引動詞不在 `_NAV_SHAPES` 的動詞表內** |

    ⚠️ **盲點 ③ 是 2026-08-31 第三組複驗補上的**，本組原本沒寫。實測的動詞至少有
    `可到` / `可至` / `詳見` / `見` / `改到`，命中 2 處真死指路（皆 `origin/main` 已存在、
    **非本批造成**，已逐條 `git show origin/main` 比對）：
    `ui/components/mutual_exclusion.py`「可到「⑤ 資料診斷」查來源狀態」、
    `ui/tab2_single_fund.py`「可至「📋 保單管理」改抓 FundClear 備援」。
    ⛔ **刻意不把這些動詞加進 `_NAV_SHAPES`**：理由與不補字表相同 ——
    動詞表本身也是一份會漏的清單，補一輪只是把盲點往後推，
    而且會讓本批再度膨脹（總管 2026-08-31 裁決：既有債另立一批）。
    **重點是把射程寫清楚，不是假裝射程等於全部。**

    ### ⚠️ 盲點的**規模**（不寫數量級，等於沒寫）

    - **第三組複驗（四種方法交叉掃）**：兩條守衛都抓不到的活字串
      **65 筆 / 15 檔**，`tab6_manual` 19、`tab5_data_guard` 11 為大宗；
      ⑤ 渲染出來的文字裡就有 `Tab1`~`Tab4` 這種過期指涉。
      ⚠️ **此數字為轉述第三組實測，本組未複現該方法。**
    - **本組自行交叉掃（判準較寬，含 CSS 之類的誤判）**：**72 筆 / 22 檔**，
      前兩名同樣是 `tab6_manual`（20）與 `tab5_data_guard`（13）。
      兩組數字不同是判準不同，**量級一致、熱點檔一致**。
    - ✅ **決定性歸因（第三組以 main vs HEAD 活字串集合 diff + 逐筆回查得出）**：
      **本批引入的新盲點死指路 0 筆** —— 上述全部是既有債。

    ### ⛔ **實測：本條抓不到「它自己當初漏掉的那一類」**（F-M9，2026-08-31 收尾批）

    總管指定的驗收突變：把 `ui/tab6_manual.py` 剛修好的那 2 處**改回寫死的「個基深掘」**。
    **行為證明**：活字串含「個基深掘」的字串常數 **0 → 2**（真的變了，不是假突變）。
    **守衛結果：黑名單向 GREEN、形態向 GREEN —— 兩條都沒紅。**

    為什麼：
    - **黑名單向**：字表存的是完整標籤「🔍 個基深掘」，突變寫的是不帶 emoji 的
      「個基深掘」→ 子字串比對不成立（**與 F-M3 同一個去 emoji 盲點**）。
    - **形態向**：`「Tab2 個基深掘的「四分位」燈號」` 裡被引號括住的是**「四分位」**，
      **分頁名本身沒有被引號括住**；`Tab` 與 `「` 之間隔了 6 個字，
      三個 `_NAV_SHAPES` 一個都不成立。

    ⚠️ **這一條必須留在這裡，不能只寫「已修好」**：它是本守衛**射程的下界證據** ——
    本批的 2 處回歸就是這樣漏掉的，而**修好之後，同樣的寫法再來一次還是會漏**。
    ⛔ **刻意不為了讓它轉紅而硬加字表 / 硬加動詞**（總管 2026-08-31 明示）：
    那會讓兩條守衛退化成白名單，正是本節開頭論證要消滅的東西。

    ### 📌 交下一批的具體提案（**本批不實作，scope 屬總管**）

    把兩條守衛的**條件做成合取**，而不是各自放寬字表：

        「**去 emoji 的分頁名**」 AND 「**導覽語境**」
        導覽語境 = TabN 編號 | 分頁 | 頁籤 | 請至 | 請到 | 請先到 | 先到 |
                   切到 | 切換到 | 回到 | 前往 | 可到 | 可至 | 改到 | 詳見

    **本組實測過這個提案（不是空想）**：
    - 在現行樹命中 ~~**5 處 = 3 處真死指路 + 2 處誤判**~~
      **4 處 = 3 處真死指路 + 1 處誤判**
      （對照：單純把去 emoji 變體加進字表是 ~~11 處 = 3 真 + **8** 誤判~~
       **10 處 = 3 真 + 7 誤判**；有意識的更正，不是漏刪 · 2026-08-31 · AI 總管 ·
       理由見上方「為什麼**刻意不**把「去 emoji 變體」加進字表」段的更正註）。
      → **誤判由 ~~8~~ 7 降到 ~~2~~ 1；3 處真死指路全數命中（這 3 處未變）。**
        （有意識的更正，不是漏刪 · 2026-08-31 · AI 總管 · 原因同上方 ⚠️ 更正註）

      ⚠️ **5→4 / 2→1 是 2026-09-01 的更正**（**有意識的更正，不是漏刪** ·
      日期 **2026-09-01** · 決策者 **AI 總管** · 依據：拿本守衛自己的
      `_scan_files()` / `_live_strings()` / `_exempted()` **實作這個合取提案並在兩棵樹上重跑**
      —— `b2bd587` = **5**、`a2ebb53` = **4**，逐筆列印比對）。
      **兩邊理由並陳**：舊表述「5 = 3 + 2」**在它寫下的當天是對的**；
      **是本批自己把它變成不成立的** —— 消失的那一筆就是 `app.py` 的 CSS 字串，
      隨本 PR 移出 live string 而不再被 `_live_strings()` 掃到。
      **它與上面 11→10 少掉的是同一筆、同一個原因**，不是另一次獨立的變動。
      現行 4 筆是：`ui/tab5_data_guard.py`「💊 Tab 3 組合健診」、
      `ui/tab_manage.py` 兩處（＝上方「剩下的 3 處」那三筆，皆真死指路）＋
      `ui/tab_batch_analysis.py`「與「組合健診」同一張大表」（誤判：那是**表名**）。
      ⛔ **這一行是「只改一半」的字面標本，留著當教訓**：`efe5e2b` 把同一行的
      ~~8~~ 改成 7，**隔幾個字的 `2` 卻沒動** —— 同一行內的兩個數字同源，
      改其中一個時必須把整行的每個數字都重問一次「它還成立嗎」。
      ⚠️ **本 docstring 是交下一批的依據**：下一批若照舊值 `5 = 3 + 2` 去實作合取守衛，
      **第一次實跑就會對不上**。
    - 對 F-M9 的三個突變字串：**1 個 RED、2 個 GREEN**
      （`Tab2 個基深掘…` 會紅 → **整條測試會轉紅**；
       但裸標題 `#### B. 個基深掘的「四分位」` 因為沒有導覽語境，仍然漏）。
    ⚠️ **所以它是「把射程往外推一格」，不是「補完」** —— 交接時請照這句寫，
    不要讀成「下一批做完就全覆蓋了」。

    **兩條的盲點不重疊，所以並行有意義；但兩條的盲點聯集不是空集（規模見上），
    所以不得宣稱全覆蓋。**
    """
    from ui.helpers.story_nav import (
        MISWRITTEN_TAB_NAMES, RETIRED_TAB_LABELS, _TAB_LABELS,
    )

    _banned = (set(_TAB_LABELS.values()) | set(RETIRED_TAB_LABELS)
               | set(MISWRITTEN_TAB_NAMES))
    _bad: list[str] = []
    for _f in _scan_files():
        _rel = str(_f.relative_to(ROOT))
        for _txt, _ln in _live_strings(_f):
            _hit = sorted(_n for _n in _banned if _n in _txt)
            if not _hit:
                continue
            if _exempted(_rel, _txt):
                continue
            _bad.append(f"{_rel}:{_ln} 命中 {_hit}：{_txt[:70]!r}")
    assert not _bad, (
        "以下活字串把分頁名寫死了（分頁名只准有一個來源 "
        "`ui/helpers/story_nav.py`）：\n  " + "\n  ".join(_bad) +
        "\n\n改吃 `tab_label()` / `section_label()` / `where_to_find()`；"
        "若確認它不是指路文案，請具名加進 `_LEGIT_EXEMPT` 並寫明理由。")


def test_navigation_hints_go_through_story_nav():
    """**形態向**：活字串帶「指路形狀」就必須經過 story_nav 求值。

    ## 這條為什麼是結構性的（本節的重點）

    黑名單只能擋**已知**的錯名字。這條不看名字、只看**形狀** ——
    「請到「X」」「「X」分頁」這種句子，不管 X 是什麼，只要那個表達式裡沒有
    真正呼叫到 `tab_label` / `section_label` / `where_to_find`，就是**有人手打了一個
    分頁名**。所以「有人又發明一個新錯名字」也擋得住，而黑名單擋不住。

    ## 判定範圍

    往上找到最近的陳述層（`Expr` / `Assign` / `Call` / `keyword` / `JoinedStr`），
    在那整棵子樹裡找 story_nav 呼叫 —— 因為指路文案常是
    `f"…{where_to_find('x')}…"` 或 `not_ready(msg, where=f"{tab_label('x')} → …")`，
    字串常數與那個呼叫是**兄弟節點**，只看字串自己永遠找不到。
    alias 一律解析回原名（理由見 `_story_nav_alias`）。

    ## 驗收突變（2026-08-31 實跑，PR 突變表 F-M6）

    在 `ui/tab6_manual.py` 加一句
    `st.caption("請到「隨便一個沒人聽過的分頁」看")` → **本條轉紅**。
    ⚠️ 這個突變是**驗收條件不是加分題**：它綠燈就代表本條還是一個換皮的白名單。
    """
    _bad: list[str] = []
    for _f in _scan_files():
        _rel = str(_f.relative_to(ROOT))
        _src = _f.read_text(encoding="utf-8")
        _tree = ast.parse(_src)
        _docs = _docstring_ids(_tree)
        _alias = _story_nav_alias(_tree)
        _parent: dict = {}
        for _n in ast.walk(_tree):
            for _c in ast.iter_child_nodes(_n):
                _parent[id(_c)] = _n

        for _n in ast.walk(_tree):
            if not (isinstance(_n, ast.Constant) and isinstance(_n.value, str)):
                continue
            if id(_n) in _docs:
                continue
            _shape = next((p.search(_n.value) for p in _NAV_SHAPES
                           if p.search(_n.value)), None)
            if _shape is None:
                continue
            # 往上收斂到最近的陳述層，再看整棵子樹有沒有 story_nav 呼叫
            _cur, _top = _n, _n
            for _ in range(14):
                _p = _parent.get(id(_cur))
                if _p is None or isinstance(_p, (ast.Module, ast.FunctionDef,
                                                 ast.AsyncFunctionDef, ast.ClassDef)):
                    break
                _cur = _p
                if isinstance(_p, (ast.Expr, ast.Assign, ast.Call,
                                   ast.keyword, ast.JoinedStr)):
                    _top = _p
            _resolved = set()
            for _c in ast.walk(_top):
                if isinstance(_c, ast.Call):
                    _nm = getattr(_c.func, "id", None) or getattr(_c.func, "attr", None)
                    if _nm:
                        _resolved.add(_alias.get(_nm, _nm))
            if _resolved & _NAV_FNS:
                continue
            if _exempted(_rel, _n.value):
                continue
            _bad.append(f"{_rel}:{_n.lineno} 指路形狀 {_shape.group(0)!r}："
                        f"{_n.value[:70]!r}")
    assert not _bad, (
        "以下活字串長得像指路文案，卻沒有經過 `ui/helpers/story_nav` 求值 —— "
        "也就是那個分頁 / 分區名是手打的：\n  " + "\n  ".join(_bad) +
        "\n\n改吃 `where_to_find()`（會自動帶上所屬分頁名與站號）；"
        "若它指的不是頂層分頁，請具名加進 `_LEGIT_EXEMPT` 並寫明理由。")


def test_no_section_key_reaches_tab_label():
    """分區 key 不得傳進 `tab_label()` —— 七→五之後那會 `KeyError`。

    舊設計的檢查 (b) 全 repo 化。它會炸得很難看（不是靜默指錯，是當場拋例外，
    而且若發生在 `except` handler 裡會**逸出分頁隔離**、整站空白）。

    ⚠️ alias 一律解析回原名。2026-08-31 實測，本 repo 有**三處**是靠 alias 藏著的
    （`_tab_label_t2('fund')` / `_tab_label_tb('batch')` / `_tab_label_tm('manage')`），
    純字串 grep `tab_label('fund')` **一處都掃不到**。它們沒炸過只是因為
    分支恆不觸發 —— 埋在死碼裡的地雷，本批已改為 `section_label()`。

    突變實驗（2026-08-31 實跑，PR 突變表 F-M5）：把 `ui/tab_manage.py` 的
    `section_label as _section_label_tm` 改回 `tab_label as _section_label_tm`
    → **本條轉紅**（呼叫點一個字都不用改）。
    """
    from ui.helpers.story_nav import _SECTION_LABELS

    _bad: list[str] = []
    for _f in _scan_files():
        _tree = ast.parse(_f.read_text(encoding="utf-8"))
        _alias = _story_nav_alias(_tree)
        for _c in ast.walk(_tree):
            if not (isinstance(_c, ast.Call) and _c.args
                    and isinstance(_c.args[0], ast.Constant)):
                continue
            _nm = getattr(_c.func, "id", None) or getattr(_c.func, "attr", None)
            if _alias.get(_nm) != "tab_label":
                continue
            if _c.args[0].value in _SECTION_LABELS:
                _bad.append(f"{_f.relative_to(ROOT)}:{_c.lineno} "
                            f"tab_label({_c.args[0].value!r})")
    assert not _bad, (
        "以下呼叫把**分區 key** 傳給 `tab_label()`，執行到就 KeyError：\n  "
        + "\n  ".join(_bad) + "\n改用 `section_label()` 或 `where_to_find()`。")


def test_exemption_tables_do_not_rot():
    """豁免 / 既有債表的每一條都必須**還指得到東西**（否則它是殭屍條目）。

    存在的理由：豁免表最常見的失效模式不是「寫錯」，是「那處早就改掉了，
    條目卻留著」—— 留著的條目會替**下一個**碰巧含有同一片段的字串開一個後門，
    而且沒有人會發現。故每次跑測試都驗一次：條目指的檔案還在、片段還命中。

    突變實驗（2026-08-31 實跑，PR 突變表 F-M7）：在 `_KNOWN_DEBT` 加一條
    `("ui/tab6_manual.py", "這個字串不存在", "假條目")` → **本條轉紅**。
    """
    _dead: list[str] = []
    for _label, _tbl in (("_LEGIT_EXEMPT", _LEGIT_EXEMPT),
                         ("_KNOWN_DEBT", _KNOWN_DEBT)):
        for _p, _needle, _why in _tbl:
            _f = ROOT / _p
            if not _f.is_file():
                _dead.append(f"{_label}: 檔案不存在 {_p}")
                continue
            assert _why.strip(), f"{_label}: {_p} / {_needle!r} 沒有寫理由"
            if _needle == "":
                continue
            if not any(_needle in _t for _t, _ in _live_strings(_f)):
                _dead.append(f"{_label}: {_p} 已無活字串含 {_needle!r}")
    assert not _dead, (
        "豁免 / 既有債表有殭屍條目（指到的東西已經不在了）：\n  "
        + "\n  ".join(_dead) + "\n請刪掉該條目 —— 留著等於留一個沒人知道的後門。")


def test_retired_and_current_tab_labels_are_disjoint():
    """退役名字表不得與現行 `_TAB_LABELS` 重疊（重疊 = 有一邊寫錯了）。

    `macro` / `health` 兩個 key 的值七→五未變，所以它們**不該**出現在退役表裡；
    反過來，任何一個退役名字若又變回現行值，代表 `_TAB_LABELS` 或退役表其中之一
    沒跟上，而這兩張表是黑名單守衛的全部依據。
    """
    from ui.helpers.story_nav import (
        MISWRITTEN_TAB_NAMES, RETIRED_TAB_LABELS, _TAB_LABELS,
    )

    _cur = set(_TAB_LABELS.values())
    assert not (_cur & set(RETIRED_TAB_LABELS)), (
        f"退役表與現行分頁名重疊：{sorted(_cur & set(RETIRED_TAB_LABELS))}")
    assert not (_cur & set(MISWRITTEN_TAB_NAMES)), (
        f"錯名字表與現行分頁名重疊：{sorted(_cur & set(MISWRITTEN_TAB_NAMES))}")
    assert not (set(RETIRED_TAB_LABELS) & set(MISWRITTEN_TAB_NAMES)), (
        "退役表與錯名字表重疊 —— 兩者性質不同（曾經對過 vs 從來沒對過），"
        "不可混放，否則 PR 描述的歸因會寫錯。")


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
