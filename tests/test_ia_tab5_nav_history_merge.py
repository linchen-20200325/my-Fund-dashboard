"""T23 守衛：⑤ 的「🗄️ NAV 歷史」—— 三個功能**一個**入口。

線框（客戶已拍板）：`docs/wireframes/fund-wireframe-final.html` §03 ⑤ B「合一」。

## 為什麼這一組測試長這樣（方法先講清楚，不要照抄成別的形狀）

派工單明令**不准**用「舊標題不見了」當守衛，而那個禁令是對的 ——
`assert "舊標題" not in ...` 在目標字串消失之後就變成**永遠會過的空操作**：
有人哪天把整塊 NAV 功能刪光，這種斷言只會更綠。本檔因此一律用**雙向**斷言：

* **正面**：合一入口**真的渲染得出來**，而且**做得到三件事**
  —— 以三條路徑各自的 `key=` 參數（實際送給 widget 的參數，不是原始碼字串）為證。
* **反面**：⑤ **沒有**持有旗標時，舊入口**照樣畫得出來**。

⭐ 少了反面那一半，「⑤ 持有 → 舊入口不畫」可以靠**把功能整個刪掉**達成而全綠。
   兩半合起來才逼出真正要的性質：**同一份東西，換了地方，只有一份。**

## ⚠️ 死分支陷阱（本 repo 已登記的失效模式，就地寫明）

把行為斷言用 `if False:` 這類**死分支**關掉，pytest 照樣報 **PASSED**、
`--collect-only` 的數字也一格不變 —— **守衛死掉看起來比活著更綠**。
`assert` 被拿掉、或整段被縮排進一個永遠不成立的分支，都是同一種病。
**唯一偵測得到它的就是突變測試本身**：每一條的突變實驗與實際輸出寫在各自 docstring。

## 每一條的突變實驗（拿掉修復必須轉紅）寫在各自的 docstring 裡。
"""
from __future__ import annotations

import contextlib

import pytest


# ══════════════════════════════════════════════════════════════════
# 假 streamlit：記錄**送給 widget 的參數**（key / label），不是原始碼字串
# ══════════════════════════════════════════════════════════════════
class _Rec:
    def __init__(self, *, button: bool = False, checkbox: bool = False) -> None:
        self.calls: list[tuple] = []      # (api, first_arg, key)
        self.session: dict = {}
        self._button = button
        self._checkbox = checkbox

    def api(self, name: str, ret=None):
        def _f(*a, **k):
            self.calls.append((name, a[0] if a else None, k.get("key")))
            return ret
        return _f

    def keys_of(self, *apis: str) -> set:
        """實際被渲染出來的 widget key 集合（`key=` 是送進去的參數，非文字比對）。"""
        return {k for n, _a, k in self.calls if n in apis and k}

    def args_of(self, name: str) -> list:
        return [a for n, a, _k in self.calls if n == name]

    def names(self) -> list[str]:
        return [n for n, _a, _k in self.calls]

    #: 欄/容器上直接呼叫的 widget 要回什麼（與模組級 patch 的回傳值一致）。
    def ret_for(self, name: str):
        if name in ("button", "download_button", "form_submit_button"):
            return self._button
        if name == "checkbox":
            return self._checkbox
        if name == "text_input":
            return ""
        if name in ("container", "expander", "spinner", "form", "status", "popover"):
            return _Ctx(self)
        return None


class _Ctx:
    """`st.columns()` / `st.container()` 回傳的東西 —— 它**同時**是 context manager
    與一個可以直接呼叫 widget 的物件（`_sc1.metric(...)`、`col.button(...)`）。

    ⚠️ 不能只做 `__enter__/__exit__`：本 repo 大量用 `_c1.metric(...)` 這種寫法，
    少了 `__getattr__` 會在半路 `AttributeError` 而不是走完渲染 —— 那會讓
    「畫了幾個 widget」的斷言在一個**根本沒跑完**的渲染上做出來。
    """

    def __init__(self, rec: "_Rec") -> None:
        self._rec = rec

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def __getattr__(self, name: str):
        return self._rec.api(name, ret=self._rec.ret_for(name))


@contextlib.contextmanager
def _fake_st(monkeypatch, *, checkbox: bool = False, button: bool = False):
    """把 streamlit 換成記錄器 —— patch 的是 `streamlit` 模組物件本身，
    所以每個 `import streamlit as st` 都吃到同一份。

    `button=False` 讓所有按鈕分支不進去（不打網路、不寫雲端）；
    `checkbox` 控制 ⑤ 的診斷 gate（要驗「gate 開著也只有一份」時給 True）。
    """
    import streamlit as st

    rec = _Rec(button=button, checkbox=checkbox)
    for _n in ("markdown", "caption", "info", "success", "warning", "error",
               "divider", "write", "metric", "dataframe", "subheader", "header",
               "code", "progress", "text", "json", "table"):
        monkeypatch.setattr(st, _n, rec.api(_n), raising=False)
    for _n in ("text_input",):
        monkeypatch.setattr(st, _n, rec.api(_n, ret=""), raising=False)
    for _n in ("file_uploader", "selectbox"):
        monkeypatch.setattr(st, _n, rec.api(_n, ret=None), raising=False)
    for _n in ("button", "download_button", "form_submit_button"):
        monkeypatch.setattr(st, _n, rec.api(_n, ret=button), raising=False)
    monkeypatch.setattr(st, "checkbox", rec.api("checkbox", ret=checkbox),
                        raising=False)
    monkeypatch.setattr(st, "columns",
                        lambda spec, **k: [_Ctx(rec) for _ in range(
                            spec if isinstance(spec, int) else len(spec))],
                        raising=False)
    for _n in ("container", "expander", "spinner", "form", "status", "popover"):
        monkeypatch.setattr(st, _n, rec.api(_n, ret=_Ctx(rec)), raising=False)
    monkeypatch.setattr(st, "session_state", rec.session, raising=False)
    monkeypatch.setattr(st, "rerun", lambda *a, **k: None, raising=False)

    # ⚠️ 種一檔已載入的持倉 —— **不是為了方便，是為了讓斷言有對象**。
    #    `_sec_nav_backfill_auto()` 在「沒有任何可補的基金」時會 `st.info(...)` 後
    #    **提前 return**，「🔄 開始補抓」那顆按鈕根本不會被畫。
    #    空 session 下驗「三個功能都在」，驗到的會是一個永遠只有 2 個 key 的假綠燈。
    rec.session["portfolio_funds"] = [
        {"code": "TESTFUND", "loaded": True, "load_error": None},
    ]
    # 選股池與雲端後端探測都會打外部（Google Sheets / secrets）—— 測試不打網路。
    import repositories.pool_repository as _pool_repo
    import services.nav_history_gs as _nh_gs
    monkeypatch.setattr(_pool_repo, "list_pool", lambda *a, **k: [], raising=False)
    monkeypatch.setattr(_nh_gs, "backend_status", lambda *a, **k: "local", raising=False)
    monkeypatch.setattr(_nh_gs, "status",
                        lambda *a, **k: {"enabled": False, "missing": ["stub"], "diag": {}},
                        raising=False)
    monkeypatch.setattr(_nh_gs, "coverage_status", lambda *a, **k: {}, raising=False)
    yield rec


# ── 三條路徑各自的 widget key（**實作端真的送出去的那個字串**）────────────
#: ② 一鍵自動補全（`nav_history_store.backfill_to_gs`）
KEY_AUTO_BACKFILL = "_nh_backfill_all"
#: ① 本地基底 CSV（`nav_history_store.import_nav_csv_multi`，多檔、寫本機 cache）
KEY_LOCAL_BASE_CSV = "_nh_upload_csv"
#: ① 對帳單 CSV（`nav_history_gs.import_csv_text`，單檔、代碼手填、只寫雲端）
KEY_STATEMENT_CSV = "navhist_import_file"

#: 三個功能全到齊 ＝ 這三個 key 全都被渲染出來。
NAV_FEATURE_KEYS = frozenset({KEY_AUTO_BACKFILL, KEY_LOCAL_BASE_CSV,
                              KEY_STATEMENT_CSV})


def _nav_keys(rec: _Rec) -> set:
    return rec.keys_of("button", "file_uploader") & NAV_FEATURE_KEYS


@pytest.fixture()
def _quiet_registry(monkeypatch):
    """把 ⑤ 診斷分區的前置（資料註冊表更新）換成 no-op —— 它會打網路。"""
    import ui.helpers.data_registry as _dr
    monkeypatch.setattr(_dr, "_update_data_registry", lambda *a, **k: None)


# ══════════════════════════════════════════════════════════════════
# 1) 正面：合一入口真的畫得出來，而且三個功能一個都沒少
# ══════════════════════════════════════════════════════════════════
def test_merged_entry_renders_all_three_nav_features(monkeypatch):
    """`render_nav_history_section()` 一次渲染 ＝ 三條路徑的 widget 全部到齊。

    ⚠️ 這一條刻意用 **`==`**（集合相等）而不是 `>=`／`in`：
    少一條 ＝ 那個功能在合併時被吃掉了（線框要的是「三個功能一個入口」，
    不是「三個功能砍成一個」）。

    突變實驗（實跑，輸出貼在 PR）：把
    `nav_history_section.render_nav_history_section()` 裡的
    `render_nav_statement_csv_import()` 那一行刪掉（＝ 合併時順手砍掉對帳單那條）
    → **本條轉紅**（實際 key 只剩 2 個，`navhist_import_file` 不見）。
    """
    from ui.helpers.settings_diag.nav_history_section import render_nav_history_section

    with _fake_st(monkeypatch) as rec:
        render_nav_history_section()

    assert _nav_keys(rec) == set(NAV_FEATURE_KEYS), (
        "合一區塊沒有把三個功能都畫出來 —— 那不是合併，是刪功能。\n"
        f"  期望：{sorted(NAV_FEATURE_KEYS)}\n"
        f"  實際：{sorted(_nav_keys(rec))}")


def test_merged_entry_uses_the_new_name_and_status_comes_first(monkeypatch):
    """標題用線框指定的「NAV 歷史」，且**累積狀態畫在兩條寫入路徑之前**。

    順序不是美觀問題：燈是 🔴「累積未啟用」時，下面兩條 CSV 匯入都只會落在本機、
    容器重啟就清空。放在動作之後 ＝ 使用者先上傳完才發現沒存進去（`CLAUDE.md §1`）。

    ⚠️ 標題用 **`==`** 比對整行，不是 `in` —— 「原名＋後綴」（例如
    `### 🗄️ NAV 歷史資料管理`）就能騙過子字串比對，而那正是要被拿掉的舊標題之一。

    突變實驗（實跑，輸出貼在 PR）：把 `render_nav_accumulation_status()` 那一行
    移到 `render_nav_statement_csv_import()` **之後** → **本條轉紅**
    （狀態燈的索引大於匯入 widget 的索引）。
    """
    from ui.helpers.settings_diag.nav_history_section import (
        NAV_HISTORY_HEADING,
        render_nav_history_section,
    )

    with _fake_st(monkeypatch) as rec:
        render_nav_history_section()

    _headings = [a for a in rec.args_of("markdown")
                 if isinstance(a, str) and a.startswith("### ")]
    assert NAV_HISTORY_HEADING in _headings, (
        f"合一區塊沒有畫出線框指定的標題 {NAV_HISTORY_HEADING!r}。實際：{_headings}")
    _exact = [h for h in _headings if h == NAV_HISTORY_HEADING]
    assert len(_exact) == 1, f"「NAV 歷史」標題不是恰好一份：{_headings}"

    # ── 順序：狀態燈必須畫在**第一個寫入 widget 之前** ──────────────────
    # ⚠️ 這裡刻意錨到**狀態燈本身那一則訊息**，不是「標題與 widget 之間有沒有東西」。
    #    第一版就是那樣寫的，結果把 `render_nav_accumulation_status()` 整個移到最後
    #    **照樣全綠** —— 因為區塊自己的 caption 就落在那個區間裡，斷言永遠有東西可看。
    #    **「中間非空」不等於「狀態燈在前面」**，那是一條測不到目標的斷言。
    #    `_fake_st` 已把 `nav_history_gs.status()` 釘成 enabled=False，
    #    所以狀態燈必然是那一則 🔴「累積未啟用」——**而這正是最要緊的情況**：
    #    雲端沒啟用時，下面兩條上傳都存不進雲端，燈必須先被看到。
    _light_idx = [i for i, (n, a, _k) in enumerate(rec.calls)
                  if n == "error" and isinstance(a, str) and "累積未啟用" in a]
    assert _light_idx, (
        "沒有畫出「累積未啟用」狀態燈 —— 斷言失去對象（狀態區被拿掉了？）。"
        f"實際呼叫：{rec.names()}")
    _first_write_widget = min(
        i for i, (n, _a, k) in enumerate(rec.calls) if k in NAV_FEATURE_KEYS)
    assert _light_idx[0] < _first_write_widget, (
        "🔴「累積未啟用」狀態燈畫在寫入 widget **之後** —— 使用者會先上傳完，"
        "才發現東西根本沒存進雲端（CLAUDE.md §1：不可讓流程看起來成功）。\n"
        f"  狀態燈 index={_light_idx[0]}，第一個寫入 widget index={_first_write_widget}")
    _heading_at = next(i for i, (n, a, _k) in enumerate(rec.calls)
                       if n == "markdown" and a == NAV_HISTORY_HEADING)
    assert _heading_at < _light_idx[0], "標題沒有畫在狀態燈之前 —— 區塊順序壞了"


# ══════════════════════════════════════════════════════════════════
# 2) 雙向：⑤ 持有 → 舊入口不畫；⑤ 沒持有 → 舊入口照畫
#    （少了下半，把功能整個刪掉也會全綠 —— 這是本檔最重要的一組）
# ══════════════════════════════════════════════════════════════════
def test_manage_page_still_renders_its_nav_block_when_five_does_not_own_it(
        monkeypatch):
    """**反面（不可省）**：⑤ 沒持有 `NAV_HISTORY` → 管理室照舊畫它自己那份 NAV。

    這一條擋的是「靠刪功能達成合併」：如果有人把管理室的 NAV 區塊整段刪掉，
    上面那條「⑤ 持有時不畫」會更綠，只有**這一條**會紅。

    突變實驗（實跑，輸出貼在 PR）：把 `ui/tab_manage.py::render_manage_tab` 內
    `if not _settings_page_owns(_SD_NAV_HISTORY):` 底下的 `_sec_nav_backfill()`
    整行刪掉 → **本條轉紅**（管理室再也畫不出 NAV widget）。
    """
    import ui.tab_manage as _tm

    with _fake_st(monkeypatch) as rec:
        _tm.render_manage_tab()

    _got = _nav_keys(rec)
    assert KEY_AUTO_BACKFILL in _got and KEY_LOCAL_BASE_CSV in _got, (
        "⑤ 沒持有旗標時，管理室**應該**照舊畫出自己那份 NAV 區塊 —— "
        f"畫不出來代表功能被刪掉了，不是被搬走。實際 key：{sorted(_got)}")


def test_manage_page_drops_its_nav_block_when_five_owns_it(monkeypatch):
    """**正面**：⑤ 持有 `NAV_HISTORY` → 管理室**一個** NAV widget 都不畫。

    ⚠️ 同時斷言**其他分區照畫**（`manage_notify_preview` 仍在）——
    否則「整支 render_manage_tab 壞掉不畫任何東西」也會讓本條全綠。

    突變實驗（實跑，輸出貼在 PR）：把 `render_manage_tab` 內的
    `if not _settings_page_owns(_SD_NAV_HISTORY):` 的 `not` 拿掉（極性反轉）
    → **本條轉紅**（⑤ 持有時反而畫了，⑤ 一頁出現兩份 NAV 匯入）。
    """
    import ui.tab_manage as _tm
    from ui.helpers.settings_diag.merge_context import NAV_HISTORY, settings_page_owns

    with _fake_st(monkeypatch) as rec:
        with settings_page_owns(NAV_HISTORY):
            _tm.render_manage_tab()

    assert not _nav_keys(rec), (
        f"⑤ 已持有 NAV_HISTORY，管理室卻還是畫了 NAV widget：{sorted(_nav_keys(rec))}")
    assert "manage_notify_preview" in rec.keys_of("button"), (
        "管理室連通報區都沒畫 —— 本條變成『整頁壞掉也會綠』的空斷言")


def test_data_guard_still_renders_its_nav_block_when_five_does_not_own_it(
        monkeypatch, _quiet_registry):
    """**反面（不可省）**：⑤ 沒持有 → 資料診斷照舊畫「🗂️ NAV 歷史匯入與累積狀態」。

    突變實驗（實跑，輸出貼在 PR）：把 `ui/tab5_data_guard.py` 內
    `render_nav_statement_csv_import()` 那一行刪掉 → **本條轉紅**。
    """
    import ui.tab5_data_guard as _t5

    with _fake_st(monkeypatch) as rec:
        _t5.render_data_guard_tab()

    assert KEY_STATEMENT_CSV in _nav_keys(rec), (
        "⑤ 沒持有旗標時，資料診斷**應該**照舊畫出對帳單匯入 —— "
        f"畫不出來代表功能被刪掉了。實際 key：{sorted(_nav_keys(rec))}")


def test_data_guard_drops_its_nav_block_when_five_owns_it(monkeypatch,
                                                          _quiet_registry):
    """**正面**：⑤ 持有 → 資料診斷不畫 NAV，但其他診斷內容照畫。

    ⚠️ 這一項是**最容易漏的一個**：所有權是 thread-local ＋ context manager 作用域，
    B 分區那個 `with` 一離開就還原了 —— `_render_diag_section()` 必須**自己**
    也持有 `NAV_HISTORY`，否則 D 分區會再畫一次。

    突變實驗（實跑，輸出貼在 PR）：把 `ui/tab5_data_guard.py` 的
    `if not _settings_page_owns(_SD_NAV_HISTORY):` 的 `not` 拿掉 → **本條轉紅**。
    """
    import ui.tab5_data_guard as _t5
    from ui.helpers.settings_diag.merge_context import NAV_HISTORY, settings_page_owns

    with _fake_st(monkeypatch) as rec:
        with settings_page_owns(NAV_HISTORY):
            _t5.render_data_guard_tab()

    assert not _nav_keys(rec), (
        f"⑤ 已持有 NAV_HISTORY，資料診斷卻還是畫了 NAV widget：{sorted(_nav_keys(rec))}")
    assert rec.args_of("markdown"), "資料診斷整頁沒畫東西 —— 本條變成空斷言"


# ══════════════════════════════════════════════════════════════════
# 3) 端到端：整頁跑一次（診斷 gate **開著**）只有一個 NAV 入口
# ══════════════════════════════════════════════════════════════════
def test_whole_page_renders_exactly_one_nav_entry(monkeypatch, _quiet_registry):
    """⑤ 整頁渲染（**診斷 gate 開著**）→ 每個 NAV widget key **恰好出現一次**。

    ⚠️ gate 刻意開著：合併前的緩解說法是「D 在 gate 之後 → 不會同屏出現兩份」，
    那只是把問題藏在一個 checkbox 後面 —— 使用者一勾就同屏看到兩份。
    本條就是要在**最壞情況**下驗。

    ⚠️ 用 `Counter` 驗**次數 == 1**，不是 `in` —— 「有畫到」和「只畫了一次」
    是兩件事，而這一批要的正是後者。

    突變實驗（實跑，輸出貼在 PR）：把 `ui/tab_settings_diag.py::_render_diag_section`
    的 `settings_page_owns(DATA_GUARD_HEADER, NAV_HISTORY)` 改回
    `settings_page_owns(DATA_GUARD_HEADER)` → **本條轉紅**
    （`navhist_import_file` 出現 2 次 ＝ 合一失效）。
    """
    from collections import Counter

    from ui.tab_settings_diag import render_settings_diag_tab

    with _fake_st(monkeypatch, checkbox=True) as rec:
        render_settings_diag_tab()

    _counts = Counter(k for _n, _a, k in rec.calls if k in NAV_FEATURE_KEYS)
    assert set(_counts) == set(NAV_FEATURE_KEYS), (
        "⑤ 整頁沒有把三個 NAV 功能都畫出來（或畫了不該有的）。\n"
        f"  期望：{sorted(NAV_FEATURE_KEYS)}\n  實際：{sorted(_counts)}")
    _dupes = {k: c for k, c in _counts.items() if c != 1}
    assert not _dupes, (
        "⑤ 一頁之內同一個 NAV widget 被畫了不只一次 —— 合一失效，"
        f"使用者又要面對兩個入口：{_dupes}")


def test_the_three_write_paths_are_not_interchangeable(monkeypatch):
    """三條路徑**不等價**，所以「挑一條留」＝ 刪功能 —— 這一條把理由釘成可執行的事實。

    驗的是**實際的模組級事實**（各自呼叫哪一支 service），不是註解怎麼寫：
    對帳單那條吃 `nav_history_gs.import_csv_text`（單檔、只寫雲端），
    基底那條吃 `nav_history_store.import_nav_csv_multi`（多檔、寫本機 cache）。
    兩支是不同模組的不同函式 —— 若哪天有人把其中一條改成呼叫另一支，
    本條會轉紅並逼他先解釋「那被刪掉的能力去哪了」。

    突變實驗（實跑，輸出貼在 PR）：把 `render_nav_statement_csv_import` 內的
    `from services.nav_history_gs import import_csv_text` 改成
    `from services.nav_history_store import import_nav_csv_multi as import_csv_text`
    → **本條轉紅**。
    """
    import ast
    import inspect

    import ui.tab5_data_guard as _t5
    import ui.tab_manage as _tm

    def _imported_names(fn) -> set:
        tree = ast.parse(inspect.getsource(fn).lstrip())
        return {f"{n.module}.{a.name}"
                for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module
                for a in n.names}

    _statement = _imported_names(_t5.render_nav_statement_csv_import)
    _base = _imported_names(_tm.render_nav_csv_manage_section)

    assert "services.nav_history_gs.import_csv_text" in _statement, (
        f"對帳單匯入不再走 `import_csv_text` —— 只寫雲端/兩欄 CSV 的能力還在嗎？{_statement}")
    assert "services.nav_history_store.import_nav_csv_multi" in _base, (
        f"本機基底匯入不再走 `import_nav_csv_multi` —— 多檔/寫本機 cache 的能力還在嗎？{_base}")
    assert not (_statement & _base), (
        "兩條匯入路徑開始共用同一支 service —— 若這是刻意收斂，請先說明哪一種 CSV "
        f"形狀被放棄了（線框要的是三個功能一個入口，不是砍成一個）：{_statement & _base}")
