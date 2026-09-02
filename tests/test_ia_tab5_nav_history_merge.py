"""T23 守衛：⑤ 的 NAV 兩塊 —— 「NAV 累積狀態」（唯讀）＋「手動補資料」（寫入類）。

線框（客戶已拍板）：`docs/wireframes/ia-wireframe.html` **Tab 05**（2026-09-01），
它取代了較舊的 `fund-wireframe-final.html` §03「三個功能一個入口」。

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


# ── 三條路徑各自的識別字串（**實作端真的送出去的那個參數**）────────────────
#: ① 一鍵自動補全（`nav_history_store.backfill_to_gs`）。
#: ⚠️ 錨的是 **form 的 key**，不是按鈕的 key —— 這條路徑沒有輸入 widget，
#:    鐵則 02 之後它的送出鈕變成 `form_submit_button`（沒有自己的 key）。
KEY_AUTO_BACKFILL = "_nh_backfill_all_form"
#: ③ 本地基底 CSV（`nav_history_store.import_nav_csv_multi`，多檔、寫本機 cache）
KEY_LOCAL_BASE_CSV = "_nh_upload_csv"
#: ② 對帳單 CSV（`nav_history_gs.import_csv_text`，單檔、代碼手填、只寫雲端）
KEY_STATEMENT_CSV = "navhist_import_file"

#: 三條路徑全到齊 ＝ 這三個字串全都被渲染出來。
NAV_FEATURE_KEYS = frozenset({KEY_AUTO_BACKFILL, KEY_LOCAL_BASE_CSV,
                              KEY_STATEMENT_CSV})


def _nav_identities(rec: _Rec) -> list:
    """本次渲染送出的 NAV 路徑識別字串（依呼叫順序，含重複）。

    widget 走 `key=`；`st.form()` 的 key 是**第一個位置引數**（`applied_form` 就是
    這樣呼叫的），兩種都要收 —— 只收 `key=` 會漏掉整條 form 化的路徑。
    """
    out = []
    for _n, _a, _k in rec.calls:
        _id = _a if _n == "form" else _k
        if _id in NAV_FEATURE_KEYS:
            out.append(_id)
    return out


def _nav_keys(rec: _Rec) -> set:
    return set(_nav_identities(rec))


@pytest.fixture()
def _quiet_registry(monkeypatch):
    """把 ⑤ 診斷分區的前置（資料註冊表更新）換成 no-op —— 它會打網路。"""
    import ui.helpers.data_registry as _dr
    monkeypatch.setattr(_dr, "_update_data_registry", lambda *a, **k: None)


# ══════════════════════════════════════════════════════════════════
# 1) 正面：合一入口真的畫得出來，而且三個功能一個都沒少
# ══════════════════════════════════════════════════════════════════
def test_manual_block_renders_all_three_write_paths(monkeypatch):
    """`render_nav_manual_section()` 一次渲染 ＝ 三條路徑的 widget 全部到齊。

    ⚠️ 這一條刻意用 **`==`**（集合相等）而不是 `>=`／`in`：
    少一條 ＝ 那個功能在合併時被吃掉了（線框要的是「三個功能一個入口」，
    不是「三個功能砍成一個」）。

    突變實驗（實跑，輸出貼在 PR）：把
    `nav_history_section.render_nav_manual_section()` 裡的
    `render_nav_statement_csv_import()` 那一行刪掉（＝ 分塊時順手砍掉對帳單那條）
    → **本條轉紅**（`navhist_import_file` 不見）。
    """
    from ui.helpers.settings_diag.nav_history_section import render_nav_manual_section

    with _fake_st(monkeypatch) as rec:
        render_nav_manual_section()

    assert _nav_keys(rec) == set(NAV_FEATURE_KEYS), (
        "「手動補資料」沒有把三條路徑都畫出來 —— 那不是分塊，是刪功能。\n"
        f"  期望：{sorted(NAV_FEATURE_KEYS)}\n"
        f"  實際：{sorted(_nav_keys(rec))}")


def test_two_blocks_use_the_ssot_labels_and_status_comes_before_manual(monkeypatch):
    """兩塊各自畫出來、名字吃 `story_nav` SSOT，且**狀態塊在寫入塊之前**。

    ⚠️ **順序錨的是「兩個區塊」的相對位置，不是「相鄰」** —— 線框 Tab 05 的最終
    順序在兩者之間夾了「連線與金鑰」。錨到相鄰，會在 ⑤ 依線框重組（T18）當天
    無故轉紅，而那時什麼都沒壞。

    ⛔ **給 T18：本條「需要」更新驅動點，不要以為它會自動存活。**
    斷言的**語意**會存活（比的是相對索引，中間插入什麼都不影響），
    **但它驅動的入口 `_render_maintain_section()` 會消失** ——「連線與金鑰」夾在
    兩塊中間，T18 必須把兩塊拆出這個入口。2026-09-02 獨立稽核實際模擬過一次
    （把 manual 塊移出該函式、另成 `safe_section`，全域相對順序仍是狀態在前）：
        FAILED test_two_blocks_use_the_ssot_labels_and_status_comes_before_manual
        E AssertionError: 沒畫出「手動補資料」標題 '### 手動補資料'
    → **把驅動點換成新的入口（或整頁渲染），不是刪掉本條。**

    ⚠️ 標題用 **`==`** 比對整行，不是 `in` —— 「原名＋後綴」就能騙過子字串比對。

    突變實驗（實跑，輸出貼在 PR）：把 `_render_maintain_section` 內
    `render_nav_status_section()` 與 `render_nav_manual_section()` 兩行**對調**
    → **本條轉紅**（狀態塊索引大於寫入塊）。
    ⚠️ 第一版在這個突變下**全綠**，因為它自己在測試裡照順序呼叫那兩個函式；
    改成驅動 `_render_maintain_section()` 之後才真的抓得到。
    """
    import ui.tab_settings_diag as _sd
    from ui.helpers.settings_diag.nav_history_section import (
        NAV_MANUAL_HEADING,
        NAV_STATUS_HEADING,
    )

    # ⚠️ **驅動真正的呼叫端**（⑤ 的 B 分區），不是在測試裡自己照順序呼叫兩個函式。
    #    第一版就是後者 —— 於是把 `_render_maintain_section` 裡的兩行**對調**之後
    #    本條照樣 12 passed：測試驗的是它自己寫的順序，不是產品的順序。
    #    **一條「自己擺好順序再驗順序」的斷言，永遠不會抓到順序錯誤。**
    with _fake_st(monkeypatch) as rec:
        _sd._render_maintain_section()

    _h = [a for a in rec.args_of("markdown")
          if isinstance(a, str) and a.startswith("### ")]
    assert [x for x in _h if x == NAV_STATUS_HEADING], (
        f"沒畫出「NAV 累積狀態」標題 {NAV_STATUS_HEADING!r}。實際：{_h}")
    assert [x for x in _h if x == NAV_MANUAL_HEADING], (
        f"沒畫出「手動補資料」標題 {NAV_MANUAL_HEADING!r}。實際：{_h}")

    _status_at = next(i for i, (n, a, _k) in enumerate(rec.calls)
                      if n == "markdown" and a == NAV_STATUS_HEADING)
    _manual_at = next(i for i, (n, a, _k) in enumerate(rec.calls)
                      if n == "markdown" and a == NAV_MANUAL_HEADING)
    assert _status_at < _manual_at, (
        "「NAV 累積狀態」畫在「手動補資料」之後 —— 雲端沒啟用時使用者會先上傳完，"
        "才發現東西根本沒存進雲端（CLAUDE.md §1：不可讓流程看起來成功）。")


def test_block_headings_are_not_hand_copied_literals():
    """兩塊的標題必須**吃 `story_nav.section_label()`**，不得手抄字面值。

    驗法是執行期比對：把 SSOT 改掉，標題常數必須跟著變。
    手抄的字面值不會跟著變 —— 那正是本 repo 已經發作三次的「指路指到不存在的東西」。

    突變實驗（實跑，輸出貼在 PR）：把 `nav_history_section.py` 的
    `NAV_STATUS_HEADING` 改成寫死的 `"### NAV 累積狀態"` → **本條轉紅**。
    """
    import importlib

    import ui.helpers.settings_diag.nav_history_section as _sec
    import ui.helpers.story_nav as _sn

    _orig = dict(_sn._SECTION_LABELS)
    try:
        _sn._SECTION_LABELS["nav_status"] = "漂移哨兵A"
        _sn._SECTION_LABELS["nav_manual"] = "漂移哨兵B"
        _reloaded = importlib.reload(_sec)
        assert _reloaded.NAV_STATUS_HEADING == "### 漂移哨兵A", (
            f"「NAV 累積狀態」標題沒有跟著 SSOT 走：{_reloaded.NAV_STATUS_HEADING!r}")
        assert _reloaded.NAV_MANUAL_HEADING == "### 漂移哨兵B", (
            f"「手動補資料」標題沒有跟著 SSOT 走：{_reloaded.NAV_MANUAL_HEADING!r}")
    finally:
        _sn._SECTION_LABELS.clear()
        _sn._SECTION_LABELS.update(_orig)
        importlib.reload(_sec)


def test_every_write_path_is_wrapped_in_a_form(monkeypatch):
    """鐵則 02：「手動補資料」的每一條寫入路徑都要經過 `st.form` 送出閘門。

    驗的是**實際送給 `st.form()` 的 key**（真的建立了幾個 form），
    不是原始碼裡有沒有 `applied_form` 這幾個字。

    ⚠️ 用 `>=` 而不是 `==`：③ 那條的「下載 cache」用 `st.download_button`，
    Streamlit **原始碼層面無條件禁止它出現在 form 內**
    （`button.py`：``st.download_button() can't be used in an st.form()``），
    所以 ③ 只有**上傳**在 form 內，逐檔維護動作必須留在 form 外。
    硬包會讓整塊 render 當場丟 `StreamlitAPIException`。

    突變實驗（實跑，輸出貼在 PR）：把 `render_nav_statement_csv_import()` 的
    `applied_form(...)` 拆掉、改回裸 `st.button` → **本條轉紅**（少一個 form）。
    """
    from ui.helpers.settings_diag.nav_history_section import render_nav_manual_section

    with _fake_st(monkeypatch) as rec:
        render_nav_manual_section()

    _forms = [a for n, a, _k in rec.calls if n == "form"]
    _want = {"_nh_backfill_all_form", "navhist_import_form", "_nh_upload_csv_form"}
    assert _want <= set(_forms), (
        "有寫入路徑沒有包進 st.form（線框 Tab 05：手動補資料＝寫入類，全部 Form 封裝）。\n"
        f"  期望至少：{sorted(_want)}\n  實際建立的 form：{sorted(_forms)}")


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

    _counts = Counter(_nav_identities(rec))
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


# ══════════════════════════════════════════════════════════════════
# 4) 三態顏色：「沒設定」＝灰　vs　「設定了但爆掉」＝紅
#    （總管 2026-09-02 裁決的第四條路：不弱化既有斷言、不藏狀態、不動 tab5 語意）
# ══════════════════════════════════════════════════════════════════
def test_unconfigured_cloud_is_grey_not_red(monkeypatch):
    """雲端**沒設定** → ⬜ 灰色空狀態三要素，**不得**畫成 🔴 紅框。

    依據：四大鐵則三態（灰＝未載入／前提不足；紅框＝系統真出錯）＋
    `CLAUDE.md` 引 v3 §02「介面狀態嚴格分離……**杜絕假性錯誤滿版**」。
    什麼都沒壞、只是還沒設定 —— 畫紅框是過度示警，而滿版假紅字會讓**真的紅**沒人看見。

    ⚠️ 這一條同時是 `tests/test_settings_diag_merge.py` 那兩條頁級斷言
    （`assert "error" not in rec.names()`）能**原樣保留**的原因 ——
    本批沒有放寬任何既有斷言，是把顏色改對。

    突變實驗（實跑，輸出貼在 PR）：把 `render_nav_accumulation_status()` 的
    `not_ready(...)` 改回 `st.error(...)` → **本條轉紅**。
    """
    import ui.tab5_data_guard as _t5

    with _fake_st(monkeypatch) as rec:
        _t5.render_nav_accumulation_status()

    _errs = [a for a in rec.args_of("error") if isinstance(a, str)]
    assert not [e for e in _errs if "累積" in e], (
        f"「雲端沒設定」被畫成紅框 —— 那是前提不足，不是系統故障。實際 error：{_errs}")
    _caps = [a for a in rec.args_of("caption") if isinstance(a, str)]
    _grey = [c for c in _caps if "累積未啟用" in c]
    assert _grey, (
        f"沒設定時連灰色狀態都沒畫 —— 使用者會盲傳（三要素消失）。實際 caption：{_caps}")
    assert any("Secrets" in c for c in _grey), (
        f"灰色空狀態缺「去哪補」那一項 —— 沒有它只是把消失換成灰色的消失：{_grey}")


def test_real_failure_is_still_red(monkeypatch):
    """**反面（不可省）**：狀態查詢**真的爆掉** → 仍然是 🔴 紅框。

    少了這一條，「把紅色全部改成灰色」也會讓上一條全綠 ——
    那會把真正的系統故障藏起來，比原本的過度示警更糟。

    突變實驗（實跑，輸出貼在 PR）：把 `render_nav_accumulation_status()` 的
    `except` 分支從 `system_error(...)` 改成 `not_ready(...)` → **本條轉紅**。
    """
    import ui.tab5_data_guard as _t5

    def _boom(*a, **k):
        raise RuntimeError("模擬 Sheets 連線爆炸")

    with _fake_st(monkeypatch) as rec:
        monkeypatch.setattr(_t5, "_cached_nh_status", _boom, raising=False)
        _t5.render_nav_accumulation_status()

    _errs = [a for a in rec.args_of("error") if isinstance(a, str)]
    assert _errs, (
        "狀態查詢真的爆掉卻沒有紅框 —— 系統故障被畫成了「還沒設定」，"
        f"使用者會以為只要去設定就好。實際呼叫：{rec.names()}")


# ══════════════════════════════════════════════════════════════════
# 5) 送出閘門真的擋住寫入（不是「有沒有建 form」，是「沒送出就不寫」）
# ══════════════════════════════════════════════════════════════════
class _FakeUpload:
    """假的上傳檔：只要 `getvalue()`，回一份最小的合法 CSV。"""

    def __init__(self, payload: bytes = b"CODE,DATE,NAV\nTEST1,2026-01-02,10.5\n") -> None:
        self._payload = payload

    def getvalue(self) -> bytes:
        return self._payload


def _run_local_base_upload(monkeypatch, *, submitted: bool):
    """跑一次「本地基底 CSV」區塊，回傳 `import_nav_csv_multi` 被呼叫的次數。

    ⚠️ 監看點放在 **`services.nav_history_store`**（實作模組）而不是呼叫端的區域別名 ——
    區域別名是在函式內 `from ... import ... as _nh_import_multi` 綁的，
    patch 呼叫端拿不到；patch 來源模組才會被那行 import 取到。
    """
    import services.nav_history_store as _store
    import ui.tab_manage as _tm

    calls: list = []

    def _spy(payload):
        calls.append(payload)
        return {"codes": [], "results": {}, "points": [], "errors": []}

    with _fake_st(monkeypatch, button=submitted) as rec:
        monkeypatch.setattr(_store, "import_nav_csv_multi", _spy, raising=True)
        # 上傳欄回一個「使用者已經選好檔」的狀態 —— 這正是舊行為會立刻寫入的情境。
        _orig_uploader = None

        def _uploader(*a, **k):
            rec.calls.append(("file_uploader", a[0] if a else None, k.get("key")))
            return _FakeUpload()

        monkeypatch.setattr(__import__("streamlit"), "file_uploader", _uploader,
                            raising=False)
        _tm.render_nav_csv_manage_section()
    return len(calls), rec


def test_local_base_csv_does_not_write_until_submitted(monkeypatch):
    """**選好檔但還沒按送出 → 一筆都不准寫。**

    這一條守的是本批**刻意的行為變更**：原碼是「檔案一選好就立刻
    `import_nav_csv_multi(...)` ＋ `st.rerun()`」，使用者**沒有反悔的機會** ——
    選錯檔的當下就已經寫進本機 cache 與雲端了。

    ⚠️ **為什麼 `test_every_write_path_is_wrapped_in_a_form` 不夠**：那條只驗
    「有沒有建立 `_nh_upload_csv_form` 這個 form」，**不驗「沒送出就不寫」**。
    2026-09-02 獨立稽核把本行為改回舊版跑全套，得到
    `6567 passed, 13 skipped` —— **與未突變的 head 一模一樣，整個 corpus 沒有一條
    釘住它**。那就是「拔掉修復不會轉紅」，本條即為補上的那一條。

    突變實驗（實跑，輸出貼在 PR）：把 `render_nav_csv_manage_section()` 的
    `elif _up_gate and _nh_file is not None:` 改回 `elif _nh_file is not None:`
    （＝ 回到「選好就寫」）→ **本條轉紅**（未送出卻呼叫了 1 次）。
    """
    _n, _rec = _run_local_base_upload(monkeypatch, submitted=False)
    assert _n == 0, (
        f"使用者只是選了檔、還沒按送出，就已經寫進 cache／雲端了（呼叫 {_n} 次）——"
        "選錯檔沒有反悔的機會。")


def test_local_base_csv_writes_exactly_once_when_submitted(monkeypatch):
    """**反面（不可省）**：按了送出 → **恰好寫一次**。

    少了這一條，「把整條寫入路徑刪掉」也會讓上一條全綠 ——
    那不是修好，是把功能弄不見。用 `== 1` 而不是 `>= 1`：重複寫入同樣是缺陷。

    突變實驗（實跑，輸出貼在 PR）：把那一段 `elif` 分支整個拿掉
    （＝ 按了送出也不寫）→ **本條轉紅**（呼叫 0 次）。
    """
    _n, _rec = _run_local_base_upload(monkeypatch, submitted=True)
    assert _n == 1, (
        f"按了送出卻沒有恰好寫一次（實際 {_n} 次）—— 0 次代表功能不見了，"
        "多次代表同一份 CSV 被重複匯入。")
