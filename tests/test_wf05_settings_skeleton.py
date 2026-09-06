"""⑤ 設定與診斷的守衛 —— **(A) 路線委派殼**：五塊照線框順序、功能委派舊模組。

錄製法：**用真的 Streamlit 跑（AppTest），不用假的 recorder** —— 同 ④
（`tests/test_wf04_portfolio_skeleton.py` 的同名段落逐條寫了理由，這裡不重述）。

⚠️ **2026-09-06：本檔隨被測檔一起從「骨架 + 灰態」改寫成「委派殼」**
=====================================================================
⑤ 是五頁裡唯一一頁在 (A) 路線拍板**之前**就寫成獨立重寫的。改寫之後：

- 「資料來源健康度」「連線與金鑰」「使用手冊」**不再是灰態佔位** —— 它們委派給
  `render_data_guard_tab()` / `render_policy_admin_bridge()` ＋
  `render_fetch_diag_from_session()` / `render_manual_tab()`，**現在有真內容**。
- 「手動補資料」**不再是一個按了不會寫的假 Form** —— 委派給
  `render_nav_manual_section()`，三條真的寫入路徑。
- 「NAV 累積狀態」**維持本檔實作**（總管裁決 2），因為委派回去會把一個
  **已知的假數字**放回線上（見 :func:`test_the_old_status_block_really_does_print_a_bare_zero_span`）。

⛔ **本輪的守衛增減，逐條列出（不要以為是漏刪）**
-----------------------------------------------

⚠️ **本段的數字是實測的，而且改正過一次。** 本組第一版在這裡寫「移除 6 條」——
**實測是 17 條**（AST 比對 `origin/main` 與本檔的 `test_*` 函式名，62 → 60；分類 A2／B1／C5／D9）。
⛔ **一段在講「守衛為什麼可以消失」的文字，自己的計數必須先為真**
（`CLAUDE.md §-2` 規則 6）。**下面是重數之後的版本。**

**移除 17 條，分成四類**（類別是本組的判讀，數字是量出來的）：

== ==== ============================================================ ==================================
類  條數  哪幾條                                                       為什麼
== ==== ============================================================ ==================================
A  2    `test_all_units_are_present_and_in_wireframe_order`           **純改名**（`units`→`blocks`）／
        `test_unit_names_are_unique`                                  **換成更強的**
                                                                      （`test_each_block_heading_is_drawn_exactly_once`
                                                                      雙向驗每個標題恰好 1 次）
B  1    `test_the_page_does_not_delegate_to_the_old_tabs`              **語意翻面**：它禁止的正是 (A) 路線
                                                                      要求的事。取代品是封閉集合、
                                                                      雙向 fail-closed，**射程更大**
C  5    `test_every_grey_unit_is_grey_until_its_content_lands`         **對象消失**：那三塊接上真內容了。
        `test_every_grey_unit_says_where_to_look`                      舊條自己的 docstring 就寫著
        `test_the_form_block_is_not_grey`                              「真內容接上時會轉紅 ——
        `test_the_manual_is_static_text_not_a_grey_placeholder`        **那是預期的**」。
        `test_the_manual_lists_exactly_the_wireframe_three`            改由
                                                                      `test_the_delegated_blocks_have_real_content_not_a_grey_placeholder`
                                                                      ＋ `test_both_gates_are_grey_and_point_at_themselves`
                                                                      兩條接手
D  9    Form 那一整節（`test_the_write_block_is_form_wrapped` /         **對象消失**：自寫 Form 退役。
        `test_the_three_fields_are_present_and_default_to_doing_nothing` / **真正的契約沒有失去守衛** ——
        `test_pressing_submit_with_no_source_never_counts_as_a_request` /  委派之後三條寫入路徑由
        `test_pressing_submit_with_a_source_records_the_applied_request` / `tests/test_ia_tab5_nav_history_merge.py`
        `test_normalise_request_coerces_to_bool` /                        `::test_every_write_path_is_wrapped_in_a_form`
        `test_applied_request_ignores_a_corrupted_session_value` /        守（驗實際送給 `st.form()` 的 key，
        `test_pressing_submit_says_the_backfill_is_not_wired_yet`）        **比原本那條深**）；
        ＋ `test_the_pending_pointer_is_a_place_not_a_status_sentence`     指路那條**純改名**為
        （改名）／`test_the_pending_pointer_is_honest_about_being_ineffective` `test_the_pointer_is_a_place_not_a_status_sentence`
== ==== ============================================================ ==================================

⚠️ **A／B 是「換成更強的」，C／D 是「對象真的消失了」。兩種不要混為一談。**

⛔ **另有 1 條是本組差點弄丟的，據實記在這裡**：
`test_the_page_writes_only_its_own_session_key` 原本落在被丟棄的區間裡，
**本組在做「舊 vs 新逐條對帳」時才發現它不見了** ——
也就是說，**如果沒有回頭數一次，它會無聲消失**。已補回並**收緊**：
舊版的形態 4 是「只要 widget 帶 `key=` 就紅」，那擋不住「帶了一個**別人的** key」
（它根本不看 key 是什麼）；現在改成**看 key 的名字**，不在白名單裡才紅。
四條寫入管道各有一顆突變（M18~M21），全部 KILLED。

**新增 15 條**（委派白名單、禁委派回會說謊的那塊、上游假數字的實證、
旗標靜態綁定 ＋ 呼叫當下 sentinel、`POLICY_ADMIN` 未開、兩個 gate 的灰態與指路、
gate 預設與 key 命名空間、gate 的呼叫次數與順序、每個標題恰好一次、
六區塊順序、委派區塊有真內容、新舊委派集合對帳、指路形狀）。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**委派殼的形狀**：六個區塊都在、順序照線框、**每個區塊標題只畫一次**、
兩個 gate 沒勾就不做任何 I/O、NAV 那一塊四種狀態各自誠實、
`NAV_HISTORY` 旗標在兩處委派都被持有（否則畫面上會有兩份 NAV）、
`POLICY_ADMIN` 一格未開、以及線框的示意值一個都沒有畫出來。

⛔ **本檔不守被委派模組的內容** —— (A) 路線明令舊模組原封不動，它們的正確性由
   它們自己的守衛負責（`tests/test_settings_diag_merge.py`、
   `tests/test_ia_tab5_nav_history_merge.py`、`tests/test_manual_anchor_toc.py` …）。
   **在這裡再抄一份等於製造第二把尺**（`CLAUDE.md §2.1`）。
⛔ **本檔不驗瀏覽器裡的真實版面**：欄寬、窄螢幕折行、`expander` 收合後的實際高度。
⛔ **本檔不重複既有的全域規則**（`ui/**` 全掃的那幾條會自動涵蓋這個檔）。

⚠️ **明確守不到的（照實列，不要用形容詞）**
-------------------------------------------
- ⛔ **示意值黑名單只有 `_PINNED_FAKE_VALUES` 那幾個字面寫法。** 裸數字、全形數字、
  換算成別的寫法、以及任何線框以外的捏造值都抓不到。
  ⚠️ 「正常」**刻意不進**這份全頁名單（它是極常見的一般用詞，而且**被委派模組會用它**）；
  收得起裸「正常」的是那份**只掃帶 ⬜ 的灰態單位**的窄名單 :data:`_CONCLUSION_WORDS`。
- ⛔ **委派之後，「畫面上出現的字」有一大半不是本檔寫的** —— 任何「全頁掃字串」的
  規則（示意值、結論字表）**現在同時掃到被委派模組的輸出**。
  ⚠️ **這是本輪新增的偽陽性來源，據實登記**：哪天 `render_manage_tab()` 裡出現
  「42 檔」這種字，本檔會紅，而**錯不在本檔**。屆時正解是把該規則收窄成
  「只掃本頁自己畫的區間」，**不是把黑名單放寬**。
- ⛔ **`getattr(st, "columns")(3)` / `from streamlit import columns as _c` 繞得過**
  :func:`test_the_page_draws_no_grid_form_or_tabs_of_its_own` —— repo 既有性質（③ 已登記）。
- ⛔ **`_holdings()` 只測到 `None` / 非 list / 非 dict 元素三種**；舊版 payload 形狀沒測。
- ⛔ **頁首（`## 標題` ＋ `st.caption`）落在所有 unit-scoped 守衛的射程之外** ——
  :func:`_units` 會丟掉第一個區塊標題之前的全部文字。**既有登記，本輪未修。**

⚠️ **`_units()` 的切法本輪換過，理由要記住**
--------------------------------------------
舊版依 `#### ` ＋ `**粗體**` ＋ 空狀態 ＋ 展開器切段。委派之後**被委派模組自己會畫
一堆 `### ` 與 `**粗體**`**，照舊切法會把它們也切成「單位」，於是
「哪一塊該灰」這類斷言的邊界會隨舊模組的內容漂移。
→ **現行只認本頁自己那六個區塊標題**（:data:`_BLOCK_ORDER`，逐一具名比對）。
⛔ **代價據實寫**：區塊**內部**不再有更細的邊界，所以「同一塊裡 A 卡的灰字替 B 卡過關」
   這種繞道**本檔抓不到了** —— 但那個粒度在委派之下本來就不屬於本頁的責任範圍。
"""
from __future__ import annotations

import ast
import contextlib
import functools
import pathlib
import re
from typing import Any, Iterator

import pytest

streamlit_testing = pytest.importorskip(
    "streamlit.testing.v1", reason="streamlit < 1.28 不支援 AppTest")
AppTest = streamlit_testing.AppTest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_05_settings.py"

#: 灰態的視覺記號（`ui/helpers/render_state.py::NOT_READY_MARK`）。
#: ⚠️ **從那個模組 import，不在這裡抄一份字面值** —— 抄了就是第二份真相源。
from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import section_label, where_to_find  # noqa: E402
from ui.views.page_05_settings import (  # noqa: E402
    BLOCK_HEALTH,
    BLOCK_KEYS,
    BLOCK_MANUAL,
    DIAG_GATE_LABEL,
    NAV_DETAIL_LABEL,
    NAV_GATE_LABEL,
    POINTS_UNIT,
    SPAN_PHRASE,
    _DIAG_NOT_LOADED_NOTE,
    _EMPTY_TITLE,
    _NOT_LOADED_NOTE,
    _SK_DIAG_GATE,
    _holdings,
    _where,
    coverage_headline,
    coverage_line,
    coverage_lines,
    maintain_label,
    nav_manual_label,
    nav_status_label,
    span_days_or_unknown,
)

#: AppTest 跑的 script。**只做兩件事**：把 repo 根加進 `sys.path`、呼叫被測 View。
#: ⚠️ 刻意**不**走 `app.py` —— 本頁本批尚未接線（客戶明令舊分頁不動），
#:    `AppTest.from_file("app.py")` 到不了這裡。
_SCRIPT = (
    f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    "from ui.views.page_05_settings import render_settings_and_diagnostics\n"
    "render_settings_and_diagnostics()\n"
)

#: 一份持倉。形狀就是 `ui/helpers/portfolio/load.py` 寫進 session 的那個。
#: ⚠️ **刻意混一個 `loaded=False`**：被測檔的 `_holdings()` 對 ⑤ **不做 `loaded` 過濾**
#:    （理由見該函式 docstring：這一頁就是要看「哪幾檔還沒補齊」）。
FAKE_HOLDINGS: list[dict[str, Any]] = [
    {"code": "TESTCODE1", "name": "測試標的一", "loaded": True},
    {"code": "TESTCODE2", "name": "測試標的二", "loaded": False},
]


def _reset_streamlit_container_stack() -> None:
    """把 Streamlit 的「目前開著哪個容器」重設回乾淨狀態。

    **為什麼需要這個 —— 這不是儀式，是實測出來的跨檔污染（2026-09-05）。**
    完整機制（逐行讀 streamlit 原始碼 + 實跑確認）逐字寫在
    `tests/test_wf04_portfolio_skeleton.py::_reset_streamlit_container_stack`。
    一句話版本：`st.form()` 會把 form 標記蓋在**行程層級的單例** `st._main` 上、
    離開 `with` 不還原；bare 模式下看不見，**到 `AppTest` 底下有 runtime 才引爆** ——
    下一個 `st.form(` 當場拋 `Forms cannot be nested in other forms.`

    ⚠️ **委派之後本頁仍然一定會踩到它** —— 被委派的
    `render_nav_manual_section()` 內部有三個 `st.form`。

    ⚠️ **刻意用 fail-loud 的寫法**（§1）：這裡碰的是 Streamlit 的私有名稱，
    哪天改名就會直接 `ImportError` / `AttributeError` 炸開，**不會**靜默跳過。
    """
    from streamlit.delta_generator import context_dg_stack
    from streamlit.delta_generator_singletons import get_dg_singleton_instance

    _main = get_dg_singleton_instance().main_dg
    # 這一行才是關鍵：清掉蓋在單例上的 form 標記。
    _main._form_data = None
    # 堆疊順帶回到乾淨狀態；正常情況它本來就是 `(main_dg,)`。
    context_dg_stack.set((_main,))


def _app(funds: list[dict[str, Any]] | None) -> Any:
    """跑一次整頁，回傳 `AppTest`。`funds=None` 代表 session 裡根本沒有那個鍵。"""
    # 進場先洗乾淨：別人留下的 form 容器會讓被委派的 form 當場炸掉。
    _reset_streamlit_container_stack()
    _at = AppTest.from_string(_SCRIPT, default_timeout=120)
    if funds is not None:
        _at.session_state["portfolio_funds"] = funds
    try:
        _at.run()
    finally:
        # 出場也洗乾淨：本檔不把髒堆疊留給後面跑的測試檔（同一個行程）。
        _reset_streamlit_container_stack()
    assert not _at.exception, (
        "整頁渲染時拋了未捕捉例外 —— 委派殼連跑都跑不起來：\n"
        + "\n".join(str(_e.value) for _e in _at.exception))
    return _at


def _rerun(at: Any) -> Any:
    """把一個已經跑過的 `AppTest` 再跑一次（用於「勾起來之後會怎樣」）。"""
    _reset_streamlit_container_stack()
    try:
        at.run()
    finally:
        _reset_streamlit_container_stack()
    return at


def _flat(node: Any) -> list[str]:
    """把 AppTest 的元素樹壓成**有序**的一串字。

    ⚠️ 回傳 list 而不是一整塊字串 —— 順序本身是本檔要驗的東西之一。
    ⚠️ **走 `children` 這個 dict 並依 key 排序**：直接 `for c in block` 會無限遞迴
    （Block 的 `__iter__` 會把自己也走進去）。
    ⚠️ **widget 的 `.value` 要包 try**：被委派模組裡有些 widget（例如 `st.data_editor`）
    在沒有 session 值時取 `.value` 會 `KeyError`。**本檔記標籤不記值**，
    所以取不到值不是問題 —— 但不包起來會讓整條測試在一個與規格無關的地方炸掉。
    """
    _out: list[str] = []
    _ch = getattr(node, "children", None)
    if not isinstance(_ch, dict):
        return _out
    for _, _c in sorted(_ch.items()):
        _t = type(_c).__name__
        try:
            _v = getattr(_c, "value", None)
        except Exception:                                   # pragma: no cover
            _v = None
        _lbl = getattr(_c, "label", None)
        if _t in ("Markdown", "Caption", "Text", "Header", "Subheader",
                  "Title", "Code", "Info", "Warning", "Error", "Success"):
            _out.append(f"[{_t}] {_v}")
        elif _lbl is not None:
            # widget：**記標籤不記值** —— 值是使用者的東西，標籤才是線框定的。
            _out.append(f"[{_t}] {_lbl}")
        else:
            _out.append(f"[{_t}]")
        _out.extend(_flat(_c))
    return _out


@functools.lru_cache(maxsize=8)
def _stream(kind: str) -> tuple[str, ...]:
    """三種 session 形狀的渲染結果（快取：同一形狀只真的跑一次）。

    - `"empty"`   —— `portfolio_funds` 是空 list
    - `"missing"` —— 根本沒有那個鍵（第一次進站）
    - `"loaded"`  —— 兩檔已列入（其中一檔 `loaded=False`，見 :data:`FAKE_HOLDINGS`）
    """
    _funds = {"empty": [], "missing": None, "loaded": FAKE_HOLDINGS}[kind]
    return tuple(_flat(_app(_funds).main))


def _text(parts: tuple[str, ...] | list[str]) -> str:
    return "\n".join(parts)


# ══════════════════════════════════════════════════════════════════
# NAV 累積狀態的 Checkbox Gate ＋ L2 取數（2026-09-06 第一批 P05-1）
# ══════════════════════════════════════════════════════════════════

def _cb(at: Any, label: str) -> Any:
    """依**標籤**取 checkbox，不用索引。

    ⛔ **不要用 `at.checkbox[0]`。** 2026-09-06 之前本檔到處這樣寫，
    而那時 `[0]` 剛好是 Form 的第一個欄位；接上 gate 之後 `[0]` 變成**gate**，
    於是「勾一個來源再送出」那幾條測試會**在完全沒有錯的情況下**去勾錯的框，
    然後測出一個假的結論。索引是位置的函數，位置會變；標籤是規格的函數。
    """
    for _c in at.checkbox:
        if _c.label == label:
            return _c
    raise AssertionError(
        f"畫面上找不到標籤為 {label!r} 的 checkbox：{[_c.label for _c in at.checkbox]}")


#: `status()` 未啟用時的回傳形狀（照 `services/nav_history_gs.py::status` 的契約）。
BACKEND_OFF: dict = {"enabled": False,
                     "missing": ["google_service_account", "NAV_SHEET_ID"],
                     "diag": {"google_service_account": "absent"}}
#: `status()` 啟用時的回傳形狀。
BACKEND_ON: dict = {"enabled": True, "missing": [], "diag": {"nav_sheet_id": "ok"}}

#: 一份**有資料**的涵蓋度。
#: ⚠️ **檔數刻意不是 42**：`_PINNED_FAKE_VALUES` 收了字面值 `"42 檔"`，
#:    而本頁現在會印**真的**「N 檔」—— 資料剛好 42 檔時那條守衛會誤紅。
#:    這是黑名單式守衛的既有性質（登記，不是沒看到）。
FAKE_COVERAGE: dict = {
    "TESTCODE1": {"points": 137, "first": "2024-01-05", "last": "2026-08-29",
                  "span_days": 967},
    "ZZOTHER9": {"points": 2, "first": "2019-03-01", "last": "2026-03-01",
                 "span_days": 2557},
}


@contextlib.contextmanager
def _patched_backend(backend: Any, coverage: Any) -> Iterator[dict]:
    """把頁面模組上的兩個 L2 入口換掉，並**數它們被叫了幾次**。

    ⚠️ **一定要 patch 模組屬性**（`ui.views.page_05_settings.fetch_nav_*`），
    不是 patch `services.nav_history_gs` —— 頁面在 import 時就把名字綁進自己的
    globals 了，改 service 端那一份對已經綁好的名字**沒有作用**。

    ⚠️ **次數本身就是斷言的對象**：本批最重要的一條性質是
    「**gate 沒勾就一次都不讀**」。看畫面驗不到它（沒讀也可能剛好沒東西可印），
    只有數呼叫次數驗得到。

    `coverage` 傳一個 `Exception` 實例 → 呼叫時 raise（模擬 `NavHistoryError`）。
    """
    import ui.views.page_05_settings as _mod
    _calls = {"backend": 0, "coverage": 0}

    def _fake_backend() -> Any:
        _calls["backend"] += 1
        return backend

    def _fake_coverage(*_a: Any, **_k: Any) -> Any:
        _calls["coverage"] += 1
        if isinstance(coverage, BaseException):
            raise coverage
        return coverage

    _orig = (_mod.fetch_nav_backend_status, _mod.fetch_nav_coverage)
    _mod.fetch_nav_backend_status, _mod.fetch_nav_coverage = _fake_backend, _fake_coverage
    try:
        yield _calls
    finally:
        _mod.fetch_nav_backend_status, _mod.fetch_nav_coverage = _orig


def _run_gated(backend: Any, coverage: Any, *,
               funds: list[dict[str, Any]] | None = None,
               open_gate: bool = True) -> tuple[list[str], dict]:
    """跑一次整頁（可選擇把 gate 勾起來），回傳 `(渲染流, 呼叫次數)`。

    ⚠️ 勾 gate 之後**一定要再 run 一次** —— Streamlit 的 widget 值要下一輪才生效。
    """
    with _patched_backend(backend, coverage) as _calls:
        _at = _app(funds)
        if open_gate:
            _cb(_at, NAV_GATE_LABEL).check()
            _rerun(_at)
        return _flat(_at.main), dict(_calls)


def _live_strings(tree: ast.AST) -> list[ast.Constant]:
    """檔內**活字串**（排除 module / class / function 的 docstring）。

    ⚠️ 沒有這個排除，本檔的規則會被**被測檔自己的說明文字**打紅 ——
    例如模組 docstring 裡就寫著「本檔沒有自己拼 ⬜ 的字串」。
    """
    _docs: set[int] = set()
    for _n in ast.walk(tree):
        if isinstance(_n, (ast.Module, ast.ClassDef, ast.FunctionDef,
                           ast.AsyncFunctionDef)):
            _b = getattr(_n, "body", None)
            if (_b and isinstance(_b[0], ast.Expr)
                    and isinstance(_b[0].value, ast.Constant)
                    and isinstance(_b[0].value.value, str)):
                _docs.add(id(_b[0].value))
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str)
            and id(_n) not in _docs]


def _tree() -> ast.Module:
    return ast.parse(SRC.read_text(encoding="utf-8"))


def _module_level_names(tree: ast.AST) -> list[ast.Name]:
    """檔內**所有**被賦值的名字（`Assign` ＋ `AnnAssign` ＋ `AugAssign`）。

    ⛔ **不要只走 `ast.Assign`（這是 ④ 被獨立稽核抓到的那個洞）**：
    `ui/views/**` 整族的模組常數**幾乎都是 `AnnAssign`**（`BLOCK_X: str = "…"`），
    只走 `Assign` 的守衛**一個字都看不到**。被測檔自己就是這個寫法 ——
    也就是說，照本檔既有風格新增一行常數，舊射程**結構上**看不到它。

    ⚠️ 三種節點的 target 形狀不同，**不能共用一行**：
    `Assign` 是 `targets`（**清單**），`AnnAssign` / `AugAssign` 是 `target`（**單一**）。
    """
    _names: list[ast.Name] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Assign):
            _names.extend(_t for _t in _n.targets if isinstance(_t, ast.Name))
        elif isinstance(_n, (ast.AnnAssign, ast.AugAssign)):
            if isinstance(_n.target, ast.Name):
                _names.append(_n.target)
    return _names


def _dotted(node: ast.AST) -> str:
    """把 `st.session_state.foo` 這種鏈還原成字串（拿不到就回空字串）。"""
    try:
        return ast.unparse(node)
    except Exception:                                   # pragma: no cover
        return ""


def _attr_calls(tree: ast.AST, names: tuple[str, ...]) -> list[str]:
    return [f"第 {_n.lineno} 行 {ast.unparse(_n.func)}(…)"
            for _n in ast.walk(tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in names]


def _imported_modules(tree: ast.AST) -> list[str]:
    """檔內 import 到的模組路徑。

    ⛔ **`ImportFrom` 一定要把「被 import 的名字」也接回模組路徑上（本組的實測教訓）**：
    `from ui import tab6_manual` 的 `node.module` 只有 **`"ui"`** ——
    只收 `node.module` 的話，**最自然的那種同層 import 完全看不到**。
    本組第一版就是這樣寫的，突變 **M13（委派舊分頁）在三種順序下全數存活**，
    是**跑突變才發現的，不是讀出來的**。

    ⚠️ 因此這裡對 `ImportFrom` **同時**吐兩種：
    `"ui"`（模組本身）與 `"ui.tab6_manual"`（模組 ＋ 被 import 的名字）——
    後者才擋得到 `from X import Y` 這條路。
    ⚠️ 代價：`from ui.helpers.ia import STATE_NOT_READY` 會多吐一個
    `"ui.helpers.ia.STATE_NOT_READY"` 這種**不是模組的字串**。
    ⛔ **2026-09-05 獨立稽核更正 —— 本段原本的自我背書有兩個錯，都不要留**：
    原寫 ~~「本檔的**兩個**消費者都是 `startswith` / 取第一段的比對，**多吐無害**」~~。
    **(1) 實際是三個消費者**（取第一段的 `..._never_reaches_into_the_data_layer`、
    `startswith` 的 `..._does_not_delegate_to_the_old_tabs`、以及
    `..._does_not_render_cache_or_backoff_state` —— **第三個是 `in` 子字串比對
    ＋ `endswith`，既不是 `startswith` 也不是取第一段**）。
    **(2)「多吐無害」是假的**：稽核逐案實測，多吐**確實會產生偽陽性** ——
    `from ui import tab_manage_v2` / `from ui import tab6_manual_helpers`
    （`startswith` **沒有點邊界**）、
    `from ui.helpers.render_state import backoff_free_note`（子字串命中 `backoff`）
    —— **三者在新版都會誤紅，舊版不會**。
    ⚠️ **今天沒有一處真的誤紅**（本檔實際 import 只有 `__future__` / `typing` /
    `streamlit` / `ui.helpers.*`），所以這不是 bug；**但那句自陳必須改成誠實版**：
    **三個消費者；多吐會產生偽陽性，只是目前沒有觸發。**
    （`startswith` 那一處已於同輪補上點邊界，子字串那一處**沒有**修 —— 見該條註記。）
    """
    _mods: list[str] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            _mods.extend(_a.name for _a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.append(_n.module)
            _mods.extend(f"{_n.module}.{_a.name}" for _a in _n.names)
    return _mods



# ══════════════════════════════════════════════════════════════════
# 區塊切法：**只認本頁自己那六個標題**（理由見模組 docstring）
# ══════════════════════════════════════════════════════════════════

def _block_order() -> tuple[str, ...]:
    """本頁由上而下的六個區塊，**兩個走 SSOT、三個線框字面、一個是登記在案的偏離**。

    ⚠️ 做成函式而不是 module 常數：`section_label()` 在 import 期炸掉會讓整個
    測試檔收集失敗，而那個錯誤訊息會指向 import 行，不是指向真正的原因。
    """
    return (BLOCK_HEALTH, nav_status_label(), BLOCK_KEYS,
            nav_manual_label(), maintain_label(), BLOCK_MANUAL)


#: 一級區塊標題（`st.markdown("### …")`）。
#: ⚠️ `#{3}(?!#)` —— **不能吃到 `#### `**：被委派模組內部有 `#### ` 小標。
_H3_OPEN = re.compile(r"^\[Markdown\] #{3}(?!#)\s+(.*)$")
#: **空狀態**的標題 —— `ia.empty_state()` 畫的是**裸 HTML div**，不是 `**粗體**`。
#: ⚠️ **一定要釘 `font-weight:600`**：`empty_state()` 的 **footer** 也是一個
#: `<div style='…'>`，不區分的話 footer 會被當成另一個空狀態。
_EMPTY_OPEN = re.compile(
    r"^\[Markdown\] <div style='[^']*font-weight:600[^']*'>(.+?)</div>$")


def _units(parts: tuple[str, ...] | list[str]) -> list[tuple[str, list[str]]]:
    """把渲染流切成**有序**的區塊：`(區塊名, 該區塊內的全部渲染紀錄)`。

    ⛔ **只認 :func:`_block_order` 裡那六個名字**（逐一具名比對），
    **不是**「所有 `### 開頭的行」——被委派模組自己會畫一堆 `### `
    （`### 📁 選股池(候選基金)`、`### 🔔 換股通報(LINE)` …），
    把它們當成區塊會讓所有 unit-scoped 斷言的邊界隨舊模組的內容漂移。

    ⚠️ **代價據實寫**：區塊**內部**不再有更細的邊界。
       「同一塊裡 A 的灰字替 B 過關」這種繞道本函式抓不到 ——
       但在 (A) 路線之下，區塊內部的內容是**被委派模組的責任**，不是本頁的。
    """
    _known = set(_block_order())
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _m = _H3_OPEN.match(_p)
        if _m and _m.group(1).strip() in _known:
            _out.append((_m.group(1).strip(), []))
            continue
        if _out:
            _out[-1][1].append(_p)
    return _out


def _segments(parts: tuple[str, ...] | list[str]) -> dict[str, list[str]]:
    """`區塊名 -> 該區塊內的渲染紀錄`（:func:`_units` 的 dict 檢視）。"""
    return {_k: _v for _k, _v in _units(parts)}


#: `st.expander` 的標題。⚠️ 型別名是 `Expander`（實測 AppTest 的元素樹）。
_EXPANDER_OPEN = re.compile(r"^\[Expander\] (.+)$")


def _nav_parts(parts: tuple[str, ...] | list[str]) -> list[str]:
    """**只**回「NAV 累積狀態」那一塊的渲染紀錄。

    ⭐ **這是本輪最重要的一個 helper，理由請讀完再改**：委派之後，畫面上的字
    有一大半**不是被測檔寫的**。任何「掃全頁字串」的內容規則
    （帶時間長度的字、結論字表、空狀態計數、展開器計數）**現在同時掃到
    被委派模組的輸出** —— 而那些輸出的正確性**不是本頁的責任**（(A) 路線）。

    **實測**：本輪第一版把那些規則留在全頁，結果 `📖 使用手冊`（`tab6_manual.py`）
    裡的教學文（「✅ 配置正常，無需再平衡」「約 5.5 年」）**當場打紅 5 條**，
    而被測檔一個字都沒錯。

    → **內容規則一律縮到本頁自己畫內容的那一塊**，也就是 NAV 累積狀態。
    ⚠️ **代價據實寫**：本頁在別的區塊裡若真的印了一個裸跨度或一句結論，
       這些規則**看不到**。那個缺口由「被測檔幾乎不自己畫內容」這個**結構**擋著，
       而不是由規則擋著 —— 哪天本頁又開始自己畫東西，這裡要一起放大。
    """
    return _segments(parts).get(nav_status_label(), [])


def _page_authored_parts(parts: tuple[str, ...] | list[str]) -> list[str]:
    """被測檔**自己畫**的那些渲染紀錄（NAV 區塊 ＋ 兩個 gate 沒勾時的健康度區塊）。

    ⚠️ **只在兩個 gate 都沒勾時成立** —— gate 一勾，健康度區塊裡就全是
    `render_data_guard_tab()` 的輸出。本檔的 :func:`_stream` 三種形狀
    **gate 都沒勾**（`value=False` / 預設不勾），所以對它們成立。
    ⛔ 拿它去看 `_run_gated(..., open_gate=True)` 的結果是錯的。
    """
    _seg = _segments(parts)
    return list(_seg.get(BLOCK_HEALTH, [])) + list(_seg.get(nav_status_label(), []))


def _nav_expanders(parts: tuple[str, ...] | list[str]) -> list[str]:
    """NAV 區塊內的展開器標題。**不含**被委派模組的展開器（它們多得是）。"""
    return [_m.group(1).strip() for _p in _nav_parts(parts)
            if (_m := _EXPANDER_OPEN.match(_p))]


def _nav_expander_body(parts: tuple[str, ...] | list[str], label: str) -> list[str]:
    """NAV 區塊內某個展開器底下的內容（到下一個展開器為止）。"""
    _out: list[str] = []
    _in = False
    for _p in _nav_parts(parts):
        _m = _EXPANDER_OPEN.match(_p)
        if _m:
            _in = _m.group(1).strip() == label
            continue
        if _in:
            _out.append(_p)
    return _out


# ══════════════════════════════════════════════════════════════════
# 骨架：六個區塊都在、順序照線框、每個標題只畫一次
# ══════════════════════════════════════════════════════════════════

def test_all_blocks_are_present_and_in_wireframe_order():
    """線框 Tab 05 由上而下：健康度 → NAV → 金鑰 → 手動補資料 →（維護）→ 使用手冊。

    ⚠️ 「🗄️ 資料維護與通報」**不是線框的區塊** —— 線框只在「從哪裡搬來」列了
    `ui/tab_manage.py`，五個 `<h4>` 裡沒有它。被測檔就地登記為 (D-5) 的偏離，
    本條把那個**現況**釘住：哪天客戶／總管裁決它該搬走或該併進別塊，這條會轉紅。
    """
    _got = [_n for _n, _ in _units(_stream("loaded"))]
    _want = list(_block_order())
    _missing = [_u for _u in _want if _u not in _got]
    assert not _missing, (
        f"⑤ 的區塊少了：{_missing}\n實際渲染順序：{_got}")
    _idx = [_got.index(_u) for _u in _want]
    assert _idx == sorted(_idx), (
        f"區塊順序與線框不符。\n線框：{_want}\n實際：{_got}")


@pytest.mark.parametrize("block", _block_order())
def test_each_block_heading_is_drawn_exactly_once(block: str):
    """⭐ 每個區塊標題在整頁**恰好出現一次**。

    ⛔ **這條抓的是一個真的發生過的 bug**：改寫的第一版讓本檔畫
    `### 手動補資料`，而被委派的 `render_nav_manual_section()` **自己也會畫同一行**
    （`nav_history_section.NAV_MANUAL_HEADING`，同一份 SSOT、同一級、逐字相同）——
    畫面上連著出現兩個一模一樣的標題。
    → 現行：區塊 4 的標題**刻意不由被測檔畫**，由被委派函式畫（見被測檔的註記）。

    ⚠️ **兩個方向都要**：出現 0 次代表那一塊消失了；出現 2 次代表畫重複了。
    """
    _lines = [_m.group(1).strip() for _p in _stream("loaded")
              if (_m := _H3_OPEN.match(_p))]
    _n = _lines.count(block)
    assert _n == 1, (
        f"區塊標題「{block}」在整頁出現 {_n} 次（應為 1 次）。\n"
        "0 次 ＝ 那一塊不見了；2 次 ＝ 被測檔與被委派模組各畫了一次"
        "（畫面上會連著出現兩個一樣的標題）。\n"
        f"實際的全部 `### ` 標題：{_lines}")


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_page_renders_in_every_session_shape(kind: str):
    """三種 session 形狀都要能跑完，而且**六個區塊一個都不少**。

    ⚠️ 這條釘的是 **D-2 的另一半**：⑤ **沒有**頁面層級空狀態 ——
    沒有基金時，其餘五塊**照樣要在**。
    ⛔ 若哪天有人照抄 ④ 的做法在 ⑤ 加一個「沒持倉就整頁只剩空狀態」，這條會轉紅。
    """
    _names = [_n for _n, _ in _units(_stream(kind))]
    for _u in _block_order():
        assert _u in _names, (
            f"（{kind}）區塊「{_u}」不見了 —— ⑤ 沒有頁面層級空狀態（D-2）。\n"
            f"實際：{_names}")


# ══════════════════════════════════════════════════════════════════
# (A) 路線：委派給誰、不委派給誰、以及旗標有沒有持對
# ══════════════════════════════════════════════════════════════════

#: 本頁**唯一**准許委派過去的舊模組 public 入口。
#: 形狀是 `(模組, 符號)`，**封閉集合、fail-closed** ——
#: 多委派一支沒登記的，:func:`test_the_page_delegates_to_exactly_the_documented_public_entries`
#: 會紅；登記了卻沒有真的委派，同一條的**反向**斷言也會紅。
#:
#: ⛔ **這張表取代了舊的 `test_the_page_does_not_delegate_to_the_old_tabs`。**
#:    保護方向從「不准委派」翻成「**只准委派這幾支**」——
#:    (A) 路線之下前者禁止的正是規格要求的事，後者才是還有牙的那一版。
_DELEGATION_ALLOWLIST: frozenset = frozenset({
    ("ui.tab5_data_guard", "render_data_guard_tab"),
    ("ui.tab_manage", "render_manage_tab"),
    ("ui.tab6_manual", "render_manual_tab"),
    ("ui.helpers.settings_diag.nav_history_section", "render_nav_manual_section"),
    ("ui.helpers.settings_diag.policy_admin_bridge", "render_policy_admin_bridge"),
    ("ui.helpers.settings_diag.fetch_diag_section", "render_fetch_diag_from_session"),
    # 資料診斷的 caller 契約：呼叫 `render_data_guard_tab()` 前必須先更新註冊表。
    ("ui.helpers.data_registry", "_update_data_registry"),
})

#: ⛔ **刻意不在名單裡的那一支，理由寫在這裡（這是總管裁決 2 的機器版）**：
#: `ui.helpers.settings_diag.nav_history_section.render_nav_status_section` ——
#: 委派過去會把「涵蓋天數 0 · ≈0.0 年」這個**已知的假數字**放回線上。
_FORBIDDEN_DELEGATION: frozenset = frozenset({
    ("ui.helpers.settings_diag.nav_history_section", "render_nav_status_section"),
    ("ui.tab5_data_guard", "render_nav_accumulation_status"),
})


def _import_pairs() -> list[tuple[str, str]]:
    """被測檔內每一個 `from <module> import <name>`（含函式內 lazy import）。

    ⚠️ **一定要走 `ImportFrom` 的 `names`，不能只看 `node.module`** ——
    `from ui import tab6_manual` 的 `node.module` 只有 `"ui"`。
    本檔的委派全部寫成 `from ui.tab6_manual import render_manual_tab`，
    所以 `(module, name)` 這個 pair 就是「委派了誰」的完整資訊。
    """
    _tree_ = ast.parse(SRC.read_text(encoding="utf-8"))
    return [(_n.module, _a.name)
            for _n in ast.walk(_tree_)
            if isinstance(_n, ast.ImportFrom) and _n.module
            for _a in _n.names]


def test_the_page_delegates_to_exactly_the_documented_public_entries():
    """⭐ (A) 路線：委派的對象**必須恰好是**登記在案的那幾支 public 入口。

    ⛔ **這是封閉集合、雙向 fail-closed**：
    - **多**委派一支沒登記的 → 紅（新增依賴必須經過一次 diff 上看得見的登記）；
    - 登記了卻**沒有**真的委派 → 也紅（表變成只增不減的紙，等於沒有規則）。

    ⚠️ **它取代的是 `test_the_page_does_not_delegate_to_the_old_tabs`**：
    那一條禁止的正是 (A) 路線要求的事。**移除它不是放寬** ——
    本條把「不准委派」翻成「只准委派這幾支」，抓得到的違規反而更多
    （舊條只認四個舊 `tab*.py`；本條連 `ui/helpers/**` 的委派也管）。
    """
    _pairs = set(_import_pairs())
    _ui = {_p for _p in _pairs if _p[0].startswith("ui.tab")
           or _p[0].startswith("ui.helpers.settings_diag")
           or _p[0] == "ui.helpers.data_registry"}
    # `merge_context` 是**旗標**不是委派對象，另有 `test_..._flags` 守它。
    _ui = {_p for _p in _ui if not _p[0].endswith("merge_context")}
    _extra = sorted(_ui - _DELEGATION_ALLOWLIST)
    assert not _extra, (
        f"被測檔委派給了沒有登記的入口：{_extra}\n"
        "(A) 路線只准呼叫登記在案的 public 入口 —— 新增一支請先加進 "
        "`_DELEGATION_ALLOWLIST` 並在 PR 描述寫理由（登記本身就是那份紀錄）。")
    _missing = sorted(_DELEGATION_ALLOWLIST - _ui)
    assert not _missing, (
        f"登記在案、但被測檔根本沒有委派的入口：{_missing}\n"
        "⚠️ 這代表某一塊的功能**悄悄消失了**（或那個登記已經沒有用途）。\n"
        "**這條紅燈是提醒不是責備**：如果是刻意拿掉的，請同時把表降下來。")


def test_the_new_page_delegates_the_same_set_as_the_old_one_minus_the_lying_block():
    """⭐⭐ **功能沒有在改寫途中掉東西** —— 用「委派給誰」這個集合直接對帳。

    ⛔ **這是本檔最便宜、也最抓得到「悄悄少一塊」的一條**：
    (A) 路線之下，「使用者做得到什麼」幾乎完全等於「委派了哪些入口」。
    把新頁與**仍然接在 `app.py` 的舊 ⑤**（`ui/tab_settings_diag.py`）逐一對帳，
    差集必須**恰好是那一支**刻意不委派的：`render_nav_status_section`。

    ⚠️ **雙向**：
    - 新頁少了什麼（`舊 - 新`）→ 只准是 `render_nav_status_section`（裁決 2）；
    - 新頁多了什麼（`新 - 舊`）→ 一律紅，那代表新頁自己長出了舊 ⑤ 沒有的依賴，
      **應該先問「那一塊是不是該進 (A) 路線的委派清單」**。

    ⚠️ **本條刻意拿舊 ⑤ 當基準，而不是拿一份手抄的清單** ——
    手抄的清單會漂移；舊 ⑤ 是**今天真的在線上跑的那一份**，它就是規格。
    ⛔ **代價據實寫**：舊 ⑤ 哪天被下架（接線批次會做），本條就失去基準、必須改寫。
       屆時正解是把基準換成 `_DELEGATION_ALLOWLIST`，**不是刪掉本條**。
    """
    def _entries(rel: str) -> set:
        _t = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        return {(_n.module, _a.name) for _n in ast.walk(_t)
                if isinstance(_n, ast.ImportFrom) and _n.module
                and (_n.module.startswith("ui.tab")
                     or _n.module.startswith("ui.helpers.settings_diag")
                     or _n.module == "ui.helpers.data_registry")
                and not _n.module.endswith("merge_context")
                for _a in _n.names}

    _old = _entries("ui/tab_settings_diag.py")
    _new = _entries("ui/views/page_05_settings.py")
    assert _old, "舊 ⑤ 掃不到任何委派 —— 基準沒了，本條失去對象。"

    _lost = sorted(_old - _new)
    assert _lost == [("ui.helpers.settings_diag.nav_history_section",
                      "render_nav_status_section")], (
        f"新 ⑤ 少委派了舊 ⑤ 有的入口：{_lost}\n"
        "⛔ (A) 路線之下，少一支委派幾乎就等於**少一塊使用者做得到的事**。\n"
        "唯一准許缺席的是 `render_nav_status_section`（總管裁決 2：它會印假數字）。")
    _gained = sorted(_new - _old)
    assert not _gained, (
        f"新 ⑤ 多了舊 ⑤ 沒有的依賴：{_gained}\n"
        "先問：那一塊是不是該正式進 (A) 路線的委派清單、由誰裁決？")


def test_the_page_never_delegates_the_lying_nav_status_block():
    """⭐⭐ **總管裁決 2 的機器版**：不准委派回會印假數字的那兩支。

    `render_nav_status_section()` → `render_nav_accumulation_status()` 把
    `coverage_status()` 的 `span_days` 原封放進 DataFrame 的「涵蓋天數」「≈年」兩欄，
    而上游在日期 parse 失敗時把「未知」編成 `0`
    —— 於是「算不出來」與「真的 0 天」在畫面上一模一樣。
    實證見 :func:`test_the_old_status_block_really_does_print_a_bare_zero_span`。

    ⛔ **這是全頁唯一一塊不走 (A) 路線的**，所以它需要一條**自己的**守衛：
    上面那條白名單只擋「多委派沒登記的」，而**把 NAV 狀態委派回去**
    在語意上恰恰是「回到 (A) 路線」—— 不特別禁，它會被當成修正而放行。
    """
    _pairs = set(_import_pairs())
    _bad = sorted(_pairs & _FORBIDDEN_DELEGATION)
    assert not _bad, (
        f"被測檔委派回了會印假數字的舊 NAV 狀態塊：{_bad}\n"
        "那一塊會把「跨度未知」印成「涵蓋天數 0 · ≈0.0 年」，"
        "與「真的 0 天」在畫面上完全分不出來（`CLAUDE.md §1`：\n"
        "錯誤的數字比沒有數字更危險）。\n"
        "⚠️ 若那個假數字**在上游被修好了**（`coverage_status` 不再把未知編成 0，"
        "或舊塊不再裸印跨度），本條就該連同被測檔的 (D-4) 一起收掉 —— "
        "**但要先實測，不是先刪守衛。**")


def test_the_old_status_block_really_does_print_a_bare_zero_span():
    """⭐ **裁決 2 的前提是不是真的**：舊塊的資料來源真的會把「未知」編成 0 嗎？

    ⛔ **這一條驗的是【別人的行為】，而且是刻意的**：
    上面那條禁令（不准委派回去）的**全部理由**就是這個事實。
    沒有這條，那個禁令會變成一句**沒有人查證過的傳說** ——
    而本 repo 一再記過：**沒查證的宣稱比沒有宣稱更危險**。
    哪天上游修好了，這條會轉紅，那正是要人回來重新評估裁決 2 的時候。

    ⚠️ **走真的 `coverage_status()`，注入假 worksheet** —— 不是重寫一份它的邏輯。
    """
    import services.nav_history_gs as _gs

    class _WS:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def get_all_values(self) -> list:
            return self._rows

    class _SH:
        def __init__(self, ws: Any) -> None:
            self._ws = ws

        def worksheet(self, _n: str) -> Any:
            return self._ws

    _rows = [
        ["code", "date", "nav", "name", "src", "at", "ccy"],
        # 壞日期（民國年）＋ 好日期 → 真實跨度約 1.4 年，但 parse 會失敗
        ["BBB", "113/01/02", "10.0", "", "", "", ""],
        ["BBB", "2025-06-01", "12.0", "", "", "", ""],
        # 同一天一筆 → **真的** 0 天
        ["DDD", "2024-05-05", "9.0", "", "", "", ""],
    ]
    _cov = _gs.coverage_status(_sheet=_SH(_WS(_rows)))

    assert _cov["BBB"]["span_days"] == 0, (
        "上游不再把「跨度未知」編成 0 了 —— 裁決 2 的前提可能已經消失。\n"
        f"實際：{_cov['BBB']}\n"
        "請重新評估：NAV 累積狀態那一塊還需不需要維持本頁自己的實作？")
    assert _cov["DDD"]["span_days"] == 0, _cov["DDD"]
    # ⭐ 這一行才是重點：**兩者的 `span_days` 完全相同**，
    #    所以舊塊那張「涵蓋天數 / ≈年」的表把它們畫成同一個東西。
    assert _cov["BBB"]["span_days"] == _cov["DDD"]["span_days"], (
        "「算不出來」與「真的 0 天」在上游已經分得開了 —— 請重新評估裁決 2。")

    # 對照組：被測檔的純函式**把兩者分開**（這是不委派換來的東西）。
    assert span_days_or_unknown("113/01/02", "2025-06-01", 0) is None, (
        "被測檔的 `span_days_or_unknown()` 沒有把「算不出來」判成未知 —— "
        "那是裁決 2 唯一的產出。")
    assert span_days_or_unknown("2024-05-05", "2024-05-05", 0) == 0, (
        "被測檔把「真的 0 天」也判成未知了 —— 那會把一個誠實的 0 藏起來。")


def _guard_flags(fn_name: str) -> list[str]:
    """被測檔某個函式裡 `settings_page_owns(...)` 的引數（原始名稱）。

    **fail-closed**：引數不是單純名稱、或追不到 `merge_context` 的 import，一律 assert 失敗。
    形狀照抄 `tests/test_settings_diag_merge.py::_resolved_guard_flags`
    （**刻意不 import 它** —— 那一支綁死在四個舊子頁的表上，射程不同）。
    """
    _tree_ = ast.parse(SRC.read_text(encoding="utf-8"))
    _bind: dict[str, tuple[str, str]] = {}
    for _n in ast.walk(_tree_):
        if isinstance(_n, ast.ImportFrom) and _n.module:
            for _a in _n.names:
                _bind[_a.asname or _a.name] = (_n.module, _a.name)
    _fn = next((_n for _n in ast.walk(_tree_)
                if isinstance(_n, ast.FunctionDef) and _n.name == fn_name), None)
    assert _fn is not None, f"被測檔裡找不到函式 {fn_name!r} —— 斷言失去對象。"
    _flags: list[str] = []
    for _n in ast.walk(_fn):
        if not (isinstance(_n, ast.Call)
                and getattr(_n.func, "id", "") == "settings_page_owns"):
            continue
        assert _n.args and not _n.keywords, (
            f"{fn_name} 的 settings_page_owns(...) 形狀本守衛認不得："
            f"{ast.unparse(_n)}（fail-closed 視為綁錯）")
        for _a in _n.args:
            assert isinstance(_a, ast.Name), (
                f"{fn_name} 的旗標引數不是單純名稱：{ast.unparse(_a)}（fail-closed）")
            assert _a.id in _bind, (
                f"{fn_name} 的旗標引數 {_a.id} 追不到 import 來源（fail-closed）")
            _mod, _orig = _bind[_a.id]
            assert _mod == "ui.helpers.settings_diag.merge_context", (
                f"{fn_name} 的旗標 {_a.id} 綁到 {_mod}.{_orig}，不是 merge_context 的旗標")
            _flags.append(_orig)
    return _flags


#: `委派函式 -> 它必須持有的旗標集合`。**用 `==` 比集合，不是「至少包含」。**
_EXPECTED_FLAGS: dict = {
    "_render_source_health": {"DATA_GUARD_HEADER", "NAV_HISTORY"},
    "_render_maintain": {"MANAGE_HEADER", "NAV_HISTORY"},
    "_render_manual": {"MANUAL_HEADER"},
}


@pytest.mark.parametrize("fn_name", sorted(_EXPECTED_FLAGS))
def test_each_delegation_holds_exactly_the_flags_it_must(fn_name: str):
    """⭐ **旗標漏掉不會報錯，只會讓畫面上多一塊 —— 所以要靜態釘住。**

    - `*_HEADER` 三支 → 被委派的舊子頁不再畫**它自己的 `##` 頁面大標**
      （⑤ 已經畫了區塊標題）。
    - **`NAV_HISTORY`** → `render_manage_tab()` 跳過 `_sec_nav_backfill()`、
      `render_data_guard_tab()` 跳過 `render_nav_accumulation_status()` ＋
      `render_nav_statement_csv_import()`。
      ⛔ **漏掉它的後果是同一頁出現兩份 NAV，而且沒有任何東西會叫。**
      ⚠️ 它必須在**兩處**都持有：所有權是 thread-local ＋ context manager 作用域，
      一離開 `with` 就還原了。
    """
    _got = _guard_flags(fn_name)
    assert set(_got) == _EXPECTED_FLAGS[fn_name], (
        f"{fn_name} 持有的旗標是 {sorted(set(_got))}，應為 "
        f"{sorted(_EXPECTED_FLAGS[fn_name])}。")
    assert len(_got) == len(set(_got)), f"{fn_name} 重複持有同一支旗標：{_got}"


def test_the_page_renders_exactly_one_nav_status_block():
    """⭐ **整頁只有一份 NAV** —— 旗標粒度的**行為面**佐證。

    上一條驗「靜態綁定就是那幾支」，本條驗「跑起來真的只有一份」。
    ⚠️ 兩者互補，**不是重複**：靜態綁對了但 `with` 的範圍包錯（例如包在
    `render_manage_tab()` 呼叫的**外面**而不是**裡面**）靜態看不出來。

    ⛔ **判準不能用 `NAV_STATUS_HEADING`**（本組第一版就是這樣寫的，當場自己打自己）：
    那個常數是 ``f"### {section_label('nav_status')}"``，而**被測檔自己畫的區塊標題
    逐字就是它** —— 兩份 NAV 與一份 NAV 在那個判準下完全一樣。
    → 改用**兩個舊入口各自獨有的字**：
    - `補歷史淨值` —— `ui/tab_manage.py::render_manage_tab()` 的 NAV 區塊；
    - `NAV 歷史匯入與累積狀態` —— `ui/tab5_data_guard.py` 的 NAV 區塊。
    兩者都由 `NAV_HISTORY` 旗標守著，⑤ 持有時**一個字都不該出現**。

    ⚠️ **本條只驗得到 `render_manage_tab()` 那一邊**（它在預設渲染流裡真的跑了）；
       資料診斷那一邊 gate 預設不勾、跑不到 ——
       那一半由 :func:`test_the_delegation_really_holds_the_nav_flag_at_call_time`
       用 sentinel 驗（**不必真的去跑那個會對外取數的模組**）。
    """
    _all = _text(_stream("loaded"))
    for _marker, _who in (("補歷史淨值", "ui/tab_manage.py 的 NAV 區塊"),
                          ("NAV 歷史匯入與累積狀態", "ui/tab5_data_guard.py 的 NAV 區塊")):
        assert _marker not in _all, (
            f"畫面上出現了 {_who}（命中 {_marker!r}）——\n"
            "代表某個委派沒有持住 `NAV_HISTORY`，同一頁會有兩份 NAV。")


def test_the_delegation_really_holds_the_nav_flag_at_call_time():
    """⭐ **sentinel**：呼叫舊模組的那一刻，`NAV_HISTORY` 真的在手上嗎？

    ⛔ **靜態綁定驗不到這件事**：`with settings_page_owns(NAV_HISTORY):` 綁對了，
    但如果 `render_manage_tab()` 的呼叫寫在 `with` **外面**，靜態守衛照樣全綠，
    而畫面上會多一塊。**所有權是 context manager 的作用域，錯在範圍不在名字。**

    做法：把被委派的入口換成一個**只做一件事**的探針 —— 記下「被呼叫的當下，
    `owned_by_settings_page(NAV_HISTORY)` 是什麼」。這樣**不必真的跑那些會對外
    取數的模組**，也驗得到範圍。
    """
    import sys

    import ui.views.page_05_settings as _mod
    from ui.helpers.settings_diag.merge_context import (
        NAV_HISTORY as _NAV,
        owned_by_settings_page as _owned,
    )

    _seen: dict[str, bool] = {}

    class _FakeManage:
        @staticmethod
        def render_manage_tab(*_a: Any, **_k: Any) -> None:
            _seen["manage"] = _owned(_NAV)

    class _FakeRegistry:
        @staticmethod
        def _update_data_registry(*_a: Any, **_k: Any) -> None:
            _seen["registry"] = _owned(_NAV)

    class _FakeGuard:
        @staticmethod
        def render_data_guard_tab(*_a: Any, **_k: Any) -> None:
            _seen["guard"] = _owned(_NAV)

    _fakes = {"ui.tab_manage": _FakeManage,
              "ui.helpers.data_registry": _FakeRegistry,
              "ui.tab5_data_guard": _FakeGuard}
    _orig = {_n: sys.modules.get(_n) for _n in _fakes}
    for _n, _f in _fakes.items():
        sys.modules[_n] = _f                                    # type: ignore[assignment]
    import streamlit as _st
    _orig_cb = _st.checkbox
    try:
        _st.session_state.clear()
        _mod._render_maintain()
        # ⚠️ **把 gate 直接換成「回 True」，不是塞 session_state** —— bare 模式下
        #    `st.checkbox(..., key=…)` 不讀 session 的既有值，一律回預設 `False`
        #    （同 :func:`test_the_diag_gate_really_gates_the_registry_update` 的登記）。
        #    本條驗的是**旗標的作用域**，不是 gate 本身，所以直接跳過 gate 是對的切法。
        _st.checkbox = lambda *_a, **_k: True                # type: ignore[assignment]
        _mod._render_source_health()
    finally:
        _st.checkbox = _orig_cb                             # type: ignore[assignment]
        for _n, _m in _orig.items():
            if _m is None:
                sys.modules.pop(_n, None)
            else:
                sys.modules[_n] = _m
        _st.session_state.clear()

    assert _seen.get("manage") is True, (
        "`render_manage_tab()` 被呼叫時 `NAV_HISTORY` **不在手上** —— "
        "管理室會把它自己那份「🗄️ 補歷史淨值」再畫一次。\n"
        f"實際：{_seen}")
    assert _seen.get("guard") is True, (
        "`render_data_guard_tab()` 被呼叫時 `NAV_HISTORY` **不在手上** —— "
        "資料診斷會把「🗂️ NAV 歷史匯入與累積狀態」再畫一次。\n"
        f"實際：{_seen}")


def test_the_page_never_opens_the_policy_admin_flag():
    """⛔ **`POLICY_ADMIN` 一格未開**（總管指示 ＋ 三條未處置的硬前置）。

    今天 `app.py` 一次都沒有持有它 → `render_policy_admin_bridge()` 只畫一句灰色指路，
    它掛的那一整支 Google Sheets 寫入是**死碼**。順手打開它會讓一整批寫入路徑活過來，
    而 `policy_admin_bridge` 的 docstring 明列了三條尚未處置的硬前置
    （session_state 先寫後讀耦合 / `sheet_client` 無 SSOT / oauth snapshot 紀律）。

    ⚠️ **兩個方向都擋**：不准把 `POLICY_ADMIN` 放進任何 `settings_page_owns(...)`，
    也不准傳一個非 None 的 `sheet_client`（那是旗標開啟後才用得到的東西，
    先傳進去等於替下一個人把前置條件的最後一道擋板拆掉）。
    """
    _all_flags = [_f for _fn in _EXPECTED_FLAGS for _f in _guard_flags(_fn)]
    assert "POLICY_ADMIN" not in _all_flags, (
        "被測檔持有了 `POLICY_ADMIN` —— 那會讓一整批 Google Sheets 寫入路徑活過來，"
        "而它有三條尚未處置的硬前置（見 `policy_admin_bridge` 的 docstring）。")
    _tree_ = ast.parse(SRC.read_text(encoding="utf-8"))
    for _n in ast.walk(_tree_):
        if (isinstance(_n, ast.Call)
                and getattr(_n.func, "id", "") == "render_policy_admin_bridge"):
            for _k in _n.keywords:
                if _k.arg == "sheet_client":
                    assert (isinstance(_k.value, ast.Constant)
                            and _k.value.value is None), (
                        f"L{_n.lineno} 傳了非 None 的 `sheet_client`："
                        f"{ast.unparse(_k.value)} —— 本批一律傳 None。")


# ══════════════════════════════════════════════════════════════════
# 兩個 gate：沒勾就不做任何 I/O（總管裁決 3）
# ══════════════════════════════════════════════════════════════════

def test_both_gates_are_grey_and_point_at_themselves():
    """⭐ 兩個 gate 沒勾時**各自**掛灰態，而且指路指向**那個 checkbox 本身**。

    ⚠️ 這一則指路是本頁少數「**去了真的有用**」的：勾起來就會載入。
       字面吃 :data:`DIAG_GATE_LABEL` / :data:`NAV_GATE_LABEL`，**不手抄** ——
       手抄的那一刻它就開始漂移，而本 repo 的「指路指到不存在的東西」已發作三次。
    ⚠️ 順帶驗「那個 checkbox 真的在畫面上」—— 指到一個不存在的按鈕比沒有指路更糟。
    """
    _parts = _stream("loaded")
    _seg = _segments(_parts)
    for _block, _label, _note in (
            (BLOCK_HEALTH, DIAG_GATE_LABEL, _DIAG_NOT_LOADED_NOTE),
            (nav_status_label(), NAV_GATE_LABEL, _NOT_LOADED_NOTE)):
        _body = _text(_seg.get(_block, []))
        assert _body, f"區塊「{_block}」是空的。"
        assert NOT_READY_MARK in _body, (
            f"gate 沒勾時，「{_block}」沒有灰態記號 {NOT_READY_MARK!r}：\n{_body}")
        assert _note in _body, (
            f"「{_block}」的灰態沒有帶它該帶的那句說明：\n{_body}")
        assert f"上方「{_label}」" in _body, (
            f"「{_block}」的灰態沒有指向那個 gate（`上方「{_label}」`）：\n{_body}")
        assert f"[Checkbox] {_label}" in _parts, (
            f"指路指向的 checkbox {_label!r} 不在畫面上 —— 指到了不存在的地方。")


def test_the_diag_gate_is_off_by_default_and_uses_its_own_key():
    """⭐ 資料診斷 gate **預設不勾**，而且**不共用舊 ⑤ 的 key**。

    - **預設不勾**（總管裁決 3）：`render_data_guard_tab()` 開頭有一次**無條件的
      匯率抓取** ＋ caller 契約要求先跑 `_update_data_registry()`。
      **拿掉這個 gate ＝ 打開 ⑤ 就對外取數。**
    - **不共用 key**：舊 ⑤（`ui/tab_settings_diag.py`）用的是 `"sd_diag_gate"`，
      而它**仍然接在 `app.py`**。兩頁共用同一個 widget key，在「兩頁同時被渲染」
      的那一刻會直接拋 `StreamlitDuplicateElementKey`。
    """
    assert _SK_DIAG_GATE != "sd_diag_gate", (
        "新頁與舊 ⑤ 共用了同一個 widget key —— 兩頁同時渲染時會直接炸。")
    assert _SK_DIAG_GATE.startswith("v05_"), (
        f"gate 的 key {_SK_DIAG_GATE!r} 不在本頁的命名空間裡。")
    _at = _app(FAKE_HOLDINGS)
    _gate = next(_c for _c in _at.checkbox if _c.label == DIAG_GATE_LABEL)
    assert _gate.value is False, "資料診斷 gate 預設是勾起來的 —— 打開 ⑤ 就會對外取數。"


def test_the_diag_gate_really_gates_the_registry_update():
    """⭐ **gate 沒勾 → `_update_data_registry()` 與 `render_data_guard_tab()`
    一次都不會被呼叫；勾起來才會，而且順序是「先更新註冊表、再畫診斷」。**

    ⛔ **看畫面驗不到這件事**（「沒跑」與「跑了但沒東西可畫」長得一樣），
       所以本條數**呼叫次數與順序**。這正是總管裁決 3 要保住的東西：
       **拿掉這個 gate ＝ 打開 ⑤ 就對外取數。**
    ⚠️ 順序是 `ui/tab5_data_guard.py` 的 **caller 契約**，不是風格 ——
       註冊表沒先更新，診斷頁讀到的是上一輪的狀態。

    ⛔ **一定要走 `AppTest`，不能在 bare 模式下塞 `session_state` 再直接呼叫**：
       bare 模式（沒有 runtime）下 `st.checkbox(..., key=…)` **不會**去讀
       session_state 的既有值，一律回預設 `False` —— 本組第一版就是這樣寫的，
       於是「勾起來之後」那一半**永遠測不到**（`_calls` 恆為空）。
       **一條在兩種情況下都回同一個答案的斷言，等於沒有斷言。**
    """
    import sys

    _calls: list[str] = []

    class _FakeRegistry:
        @staticmethod
        def _update_data_registry(*_a: Any, **_k: Any) -> None:
            _calls.append("registry")

    class _FakeGuard:
        @staticmethod
        def render_data_guard_tab(*_a: Any, **_k: Any) -> None:
            _calls.append("guard")

    _fakes = {"ui.helpers.data_registry": _FakeRegistry,
              "ui.tab5_data_guard": _FakeGuard}
    _orig = {_n: sys.modules.get(_n) for _n in _fakes}
    for _n, _f in _fakes.items():
        sys.modules[_n] = _f                                    # type: ignore[assignment]
    try:
        _at = _app(FAKE_HOLDINGS)
        assert _calls == [], (
            f"gate 還沒勾就跑了對外取數的前置：{_calls}\n"
            "⛔ 打開 ⑤ 就更新註冊表 ＋ 抓匯率，正是這個 gate 存在的理由。")
        next(_c for _c in _at.checkbox if _c.label == DIAG_GATE_LABEL).check()
        _rerun(_at)
        assert _calls == ["registry", "guard"], (
            f"勾起來之後的呼叫順序不對或漏跑：{_calls}\n"
            "caller 契約是**先更新註冊表、再畫診斷**"
            "（`ui/tab5_data_guard.py` 的模組 docstring）。")
    finally:
        for _n, _m in _orig.items():
            if _m is None:
                sys.modules.pop(_n, None)
            else:
                sys.modules[_n] = _m


def test_the_delegated_blocks_have_real_content_not_a_grey_placeholder():
    """⭐ **四個委派區塊不准只是一句灰字。**

    ⛔ 這一條取代了三條舊守衛（`test_the_form_block_is_not_grey` /
    `test_the_manual_is_static_text_not_a_grey_placeholder` /
    `test_the_manual_lists_exactly_the_wireframe_three`），而且**比它們強** ——
    舊的三條各守一塊、而且只驗「有沒有 ⬜」；本條驗**每一塊都有真的東西**。

    ⚠️ **判準是「這一塊裡有沒有 widget 或多於一行的內容」**，不是比對特定字串 ——
    比對字串等於把被委派模組的文案抄一份進來（第二份真相源，且必然漂移）。
    ⚠️ **「連線與金鑰」與「使用手冊」不在本條射程內**，理由不同、逐一寫明：
    - **連線與金鑰**：兩個承接對象在測試環境**本來就會是灰態**
      （沒有 OAuth token → 保單橋接灰；沒有抓取紀錄 → 抓取診斷灰）。
      那是**真實狀態**，不是佔位。
    - **使用手冊**：它收在 `st.expander` 裡，AppTest 仍會渲染其內容，
      故它**在**射程內（見下方 `_want`）。
    """
    _seg = _segments(_stream("loaded"))
    _want = (nav_manual_label(), maintain_label(), BLOCK_MANUAL)
    for _b in _want:
        _body = _seg.get(_b, [])
        assert _body, f"區塊「{_b}」什麼都沒畫 —— 委派沒有生效。"
        _widgets = [_p for _p in _body
                    if _p.startswith(("[Button]", "[TextInput]", "[Checkbox]",
                                      "[FileUploader]", "[Expander]", "[Selectbox]",
                                      "[NumberInput]", "[DateInput]", "[Radio]"))]
        _rich = [_p for _p in _body if _p.startswith(("[Markdown]", "[Caption]"))]
        assert _widgets or len(_rich) >= 2, (
            f"區塊「{_b}」看起來仍是佔位（widget {len(_widgets)} 個、"
            f"文字 {len(_rich)} 行）：\n{_text(_body)}")
        assert not (len(_body) == 1 and NOT_READY_MARK in _body[0]), (
            f"區塊「{_b}」只有一句灰字 —— 委派應該帶來真內容。")


# ══════════════════════════════════════════════════════════════════
# 唯讀閘門：NAV gate 一個 session 都不准寫、一次寫入都不准做
# ══════════════════════════════════════════════════════════════════

#: 會產生使用者輸入的 widget —— 線框那句「寫入類動作，**全部 Form 封裝**」管的就是這些。
#: ⚠️ 這是**白名單，不是窮舉**：Streamlit 新增的輸入元件不會自動進來。
_INPUT_WIDGETS: frozenset = frozenset({
    "checkbox", "toggle", "slider", "select_slider", "number_input",
    "text_input", "text_area", "selectbox", "multiselect", "radio",
    "date_input", "time_input", "file_uploader", "color_picker", "camera_input",
})


def _input_widget_calls(tree: ast.AST) -> list[ast.Call]:
    """檔內所有 `st.<輸入元件>(...)` 呼叫。"""
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in _INPUT_WIDGETS]


#: 而且**只放得下 checkbox / toggle 這種布林閘門**。
#: 任何人想把一個 form 欄位搬出去，只要它會寫東西，那條證明就會紅。
READ_ONLY_GATE_FUNCS: frozenset = frozenset({"_render_nav_status"})

#: 會寫入 nav_history 的 L2 入口（`services/nav_history_gs.py::__all__` 的寫入側）。
#: 唯讀閘門函式裡出現任何一個 → 它就不是唯讀的。
_WRITE_CALL_NAMES: frozenset = frozenset({
    "append_point", "append_points", "import_csv_text",
})
#: 唯讀閘門裡**唯一**允許的輸入元件形態（布林開關）。
_GATE_ONLY_WIDGETS: frozenset = frozenset({"checkbox", "toggle"})


def _func_defs(tree: ast.AST) -> dict[str, ast.FunctionDef]:
    return {_n.name: _n for _n in ast.walk(tree)
            if isinstance(_n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _read_only_gate_ranges(tree: ast.AST) -> list[tuple[int, int]]:
    """:data:`READ_ONLY_GATE_FUNCS` 各函式的行區間。"""
    _defs = _func_defs(tree)
    return [(_d.lineno, getattr(_d, "end_lineno", _d.lineno))
            for _n, _d in _defs.items() if _n in READ_ONLY_GATE_FUNCS]


def test_the_read_only_gate_really_is_read_only():
    """⭐ 唯讀閘門的**豁免證明** —— 沒有這條，上面那條豁免就是一個洞。

    四項全部要過（任一不過 ＝ 那個函式不配拿豁免）：

    1. **名單上的函式真的存在** —— 打錯字會讓豁免對一個不存在的名字生效，
       而豁免區間變成空集合的話上面那條會**照常綠**（因為 form 外本來就沒東西）。
       ⛔ 這一項擋的是「豁免悄悄失效」與「豁免悄悄擴大」兩個方向裡的**後者的入口**。
    2. **函式內一個 session 都不寫**（下標／屬性／`update` / `setdefault` /
       widget `key=` 四條管道全看，形狀沿用 :func:`test_the_page_writes_only_its_own_session_key`）。
    3. **函式內不呼叫任何寫入類 L2 入口**（:data:`_WRITE_CALL_NAMES`）。
    4. **函式內 form 外的輸入元件只能是 checkbox / toggle** —— 布林閘門。
       ⛔ 這一項擋的是「把一個 `text_input` 搬進閘門函式來躲 form」。

    ⚠️ **本條守不到的（照實列）**：
    - 豁免是**以函式為單位**的，所以在 `_render_nav_status` 裡多放**第二個** checkbox
      不會紅（第 4 項只管型別，不管數量）。目前那個函式只有一個 gate；
      要不要連數量一起釘，本組判斷**不值得**（會把「多一個唯讀開關」也打紅）。**登記。**
    - 第 3 項是**裸函式名**比對，`getattr(mod, "append_points")(...)` 這種非字面呼叫抓不到
      （同本檔其他 AST 條的既有限制）。
    - 「唯讀」只驗到**寫入的四條管道 ＋ 寫入類 L2 入口**；一個會寫檔案的新 helper
      （例如 `pathlib.Path.write_text`）**不在射程內**。
    """
    _tree_ = _tree()
    _defs = _func_defs(_tree_)
    _missing = sorted(READ_ONLY_GATE_FUNCS - set(_defs))
    assert not _missing, (
        f"唯讀閘門名單上的 {_missing} 在被測檔裡不存在 —— "
        "豁免正指著一個不存在的名字（改名之後這個豁免會靜靜留在檔案裡）。")

    for _name in sorted(READ_ONLY_GATE_FUNCS):
        _fn = _defs[_name]
        _bad: list[str] = []
        for _n in ast.walk(_fn):
            _targets: list[ast.AST] = []
            if isinstance(_n, ast.Assign):
                _targets = list(_n.targets)
            elif isinstance(_n, (ast.AugAssign, ast.AnnAssign)):
                _targets = [_n.target]
            for _t in _targets:
                if (isinstance(_t, (ast.Subscript, ast.Attribute))
                        and "session_state" in _dotted(getattr(_t, "value", _t))):
                    _bad.append(f"L{_n.lineno} 寫 session {_dotted(_t)}")
            if isinstance(_n, ast.Call):
                _d = _dotted(_n.func)
                _leaf = _d.rsplit(".", 1)[-1]
                if "session_state" in _d and _leaf in ("update", "setdefault"):
                    _bad.append(f"L{_n.lineno} {_d}(...)")
                if _d.startswith("st.") and any(_k.arg == "key" for _k in _n.keywords):
                    _bad.append(f"L{_n.lineno} widget key= → {_d}")
                if _leaf in _WRITE_CALL_NAMES:
                    _bad.append(f"L{_n.lineno} 寫入類呼叫 {_d}(...)")
        assert not _bad, (
            f"「{_name}」拿了唯讀閘門豁免，但它會寫東西：{_bad}\n"
            "⛔ 豁免只給**唯讀**閘門 —— 會寫的東西一律回到 `applied_form(...)` 裡面。")

        _widgets = [_c for _c in _input_widget_calls(_fn)]
        _wrong = sorted({_c.func.attr for _c in _widgets} - _GATE_ONLY_WIDGETS)
        assert not _wrong, (
            f"「{_name}」裡的輸入元件 {_wrong} 不是布林閘門 —— "
            f"唯讀閘門只放得下 {sorted(_GATE_ONLY_WIDGETS)}；"
            "其他輸入元件請回到 `applied_form(...)` 裡面。")
        assert _widgets, (
            f"「{_name}」在唯讀閘門名單上，卻一個輸入元件都沒有 —— "
            "這個豁免已經沒有用途，請把它降回來（雙向 ratchet）。")


def test_the_pointer_is_a_place_not_a_status_sentence():
    """`_where()` 回傳的必須是一個**地方**（`分頁 → 區塊`）。

    `not_ready()` 會把它包成「（請先到：…）」—— 塞一句狀態陳述進去
    會產生一句**不可執行的指令**（③ 2026-09-05 被獨立紅隊實測抓到的錯）。
    """
    _got = _where(nav_manual_label())
    assert _got == f"{where_to_find('settings')} → {nav_manual_label()}", _got
    assert "目前" not in _got and "只有" not in _got, (
        f"指路變成狀態陳述了：{_got!r}")


# ══════════════════════════════════════════════════════════════════
# D-2：只有 NAV 那一塊可能真的空
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_no_block_is_empty_before_the_gate_is_opened(kind: str):
    """⭐ **gate 沒勾 → 一個空狀態都不准有。**（2026-09-06 P05-1 取代舊條）

    ⛔ **舊條的形狀是錯的，這是本批最重要的一次語意更正**：
    2026-09-06 之前，NAV 那一塊在 `portfolio_funds` 為空時就畫空狀態
    「這個工作階段還沒載入任何基金 …… 就沒有涵蓋度可看」。
    **那句話的前提是假的** —— `coverage_status()` 讀的是**整張雲端 sheet**，
    它與 `portfolio_funds`（一個開站不會自動載入的 session 鍵）**毫無關係**。
    一個雲端累積了三年的人，開站第一眼看到的是「沒有涵蓋度可看」。

    **現行**：空狀態只在**真的讀成功、而且真的一筆都沒有**時出現。
    gate 沒勾 ＝ 我們**什麼都還沒讀**，那時唯一誠實的畫面是**灰態**，不是空狀態。
    → 由 :func:`test_the_empty_state_only_appears_after_a_successful_read` 從另一邊守。
    """
    _empty = [_m.group(1).strip() for _p in _nav_parts(_stream(kind)) if (_m := _EMPTY_OPEN.match(_p))]
    assert _empty == [], (
        f"（{kind}）gate 還沒勾就出現了空狀態 {_empty} —— "
        "我們一次都還沒讀雲端，說不出「沒有」（§1：不知道 ≠ 沒有）。")


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_nav_block_is_grey_and_reads_nothing_before_the_gate(kind: str):
    """⭐ **gate 沒勾 → `status()` 與 `coverage_status()` 一次都不會被呼叫。**

    ⛔ **這一條看的是呼叫次數，不是畫面。** 看畫面驗不到它：
    「沒讀」與「讀了但沒東西可印」長得一模一樣。
    這是本批選 Checkbox Gate（而不是 UI 層 `@st.cache_data`）**唯一真正買到的東西** ——
    首屏一次 Google Sheets 往返都沒有。
    """
    _parts, _calls = _run_gated(
        BACKEND_ON, FAKE_COVERAGE,
        funds={"empty": [], "missing": None, "loaded": FAKE_HOLDINGS}[kind],
        open_gate=False)
    assert _calls == {"backend": 0, "coverage": 0}, (
        f"（{kind}）gate 都還沒勾，L2 就被呼叫了 {_calls} —— "
        "首屏無條件取數正是 Checkbox Gate 要擋掉的那件事。")
    _body = _text(_segments(_parts).get(nav_status_label(), []))
    assert NOT_READY_MARK in _body and _NOT_LOADED_NOTE in _body, (
        f"（{kind}）gate 未勾時，NAV 那一塊沒有誠實說「還沒讀」：\n{_body}")


def test_a_read_failure_takes_down_only_the_nav_card():
    """⭐ `coverage_status()` 拋例外 → **只有 NAV 那一張卡變紅框**，另外兩張照常。

    ⚠️ **這不是假想的失敗路徑**：`services/nav_history_gs.py::load_points` 在
    **來源冷卻期內**（前一次失敗登記了 cooldown）與**真 I/O 失敗**時
    都會拋 `NavHistoryError` —— 那是 L2 刻意的 §1 行為（回 `[]` 會與
    「這檔真的還沒累積」同義），**不是 bug，是這一塊的正常路徑之一**。

    ⛔ **少了 `_render_grid()` 裡那一層 `safe_section()`，外層那個
    `safe_section("狀態三卡", _render_grid)` 會把三張卡一起換成一個紅框** ——
    「資料來源健康度」與「連線與金鑰」明明沒壞，卻跟著消失。
    `render_state.safe_section` 的 docstring 逐字寫著這句：
    **「把診斷跟故障綁在同一條命上，是最糟的順序。」**

    ⚠️ **本條驗的是「隔離」，不驗紅框長什麼樣**（那是 `system_error()` 的事）。
    """
    class _Boom(RuntimeError):
        pass

    _parts, _calls = _run_gated(BACKEND_ON, _Boom("nav_history load 失敗（模擬冷卻期）"),
                                funds=FAKE_HOLDINGS)
    assert _calls["coverage"] == 1, f"沒有真的走到取數：{_calls}"
    _reds = [_p for _p in _parts if _p.startswith("[Error]")]
    assert len(_reds) == 1, (
        f"讀取失敗時的紅框有 {len(_reds)} 個，應該恰好 1 個（只有 NAV 那一張）：{_reds}")
    _names = [_n for _n, _ in _units(_parts)]
    for _u in (BLOCK_HEALTH, BLOCK_KEYS, nav_manual_label(), BLOCK_MANUAL):
        assert _u in _names, (
            f"NAV 讀取失敗把「{_u}」一起帶走了 —— 區塊隔離沒有生效。\n實際單位：{_names}")


def test_opening_the_gate_reads_exactly_once():
    """勾了 gate → 兩個 L2 入口**各被呼叫一次**（不是 0 次，也不是每塊各一次）。

    ⚠️ 這條與上一條是一對：上一條防「沒勾也讀」，本條防「勾了不讀」。
    只留其中一條，另一個方向就沒人守。
    """
    _parts, _calls = _run_gated(BACKEND_ON, FAKE_COVERAGE, funds=FAKE_HOLDINGS)
    assert _calls == {"backend": 1, "coverage": 1}, (
        f"勾了 gate 之後 L2 的呼叫次數是 {_calls}，應該各恰好一次。")


#: NAV 那一塊的四種狀態 → `(backend, coverage, 要不要勾 gate)`。
#: ⚠️ **四種是窮舉的**（`_render_nav_status` 只有這四條 return 路徑），
#:    但那是**讀出來的**，不是量出來的 —— 加第五條路徑時本表不會自動長大。
_NAV_STATES: dict = {
    "gate 未勾": (BACKEND_ON, FAKE_COVERAGE, False),
    "後端未啟用": (BACKEND_OFF, FAKE_COVERAGE, True),
    "讀到空": (BACKEND_ON, {}, True),
    "讀到有資料": (BACKEND_ON, FAKE_COVERAGE, True),
}


@pytest.mark.parametrize("state", sorted(_NAV_STATES))
def test_the_nav_block_keeps_its_unit_boundary_in_every_state(state: str):
    """⭐ **四種狀態下，「NAV 累積狀態」都必須是一個【單位】。**

    ⛔ **這一條是實測逼出來的，不是風格潔癖。** `ia.state_card(state=STATE_OK)` 走的是
    `st.metric(title, value)`，而 `st.metric` 在 AppTest 的元素樹裡是
    `[Metric] 標籤`、**不是** `[Markdown] **標題**` —— :func:`_units` 的 `_CARD_OPEN`
    認不出它。若這一塊照抄別頁用 `state_card` 畫「有資料」的狀態，
    **它會在終於有內容的那一刻停止成為一個單位**：
    灰態、結論字表、指路那幾條 unit-scoped 守衛會**全部靜靜停止覆蓋它**，
    而且**沒有任何一條測試會紅**（它們只會去看「這個單位」有沒有問題，
    而那個單位已經不存在了）。
    → 故 `_render_nav_status()` **四種狀態一律先手寫同一個標題**。

    ⚠️ 順帶釘住邊界：這一塊的內容**不准溢出到隔壁那張卡**（資料來源健康度）。

    ⚠️ **這一條的突變驗證第一次寫錯了，記在這裡不美化**（2026-09-06）：
    第一顆突變（M6）把 `state_card` 放在一個 `if st.session_state.get("__mut6"):`
    分支底下，而那個鍵**從來沒有被設過** —— 也就是那顆突變**根本沒有改到行為**，
    於是它「存活」了（三序 **89 passed**）。
    ⛔ **一顆存活的突變有兩種意思：守衛有洞、或突變沒生效。**
    分不清就寫「守衛有洞」是把自己的錯記到守衛頭上；分不清就寫「守衛沒問題」
    更糟 —— 那正是本 repo 記載過的「假的補償控制」。
    **改寫成真的把手寫標題拿掉、整組走 `state_card` 的版本（M6b）之後：三序皆
    6 failed，其中 4 條是本函式的四個參數化。**
    """
    _backend, _cov, _open = _NAV_STATES[state]
    _parts, _ = _run_gated(_backend, _cov, funds=FAKE_HOLDINGS, open_gate=_open)
    _names = [_n for _n, _ in _units(_parts)]
    assert nav_status_label() in _names, (
        f"（{state}）「{nav_status_label()}」不再是一個單位 —— "
        "unit-scoped 的守衛會全部對它失效，而且不會有人發現。\n"
        f"實際單位：{_names}")
    _seg = _segments(_parts)
    assert NAV_GATE_LABEL in _text(_seg[nav_status_label()]), (
        f"（{state}）gate 沒有落在 NAV 那個單位裡 —— "
        "它會被算進**前一張卡**（資料來源健康度），那張卡的斷言就會被它污染。")
    assert NAV_GATE_LABEL not in _text(_seg.get(BLOCK_HEALTH, [])), (
        f"（{state}）gate 溢出到「{BLOCK_HEALTH}」那個單位裡了。")


@pytest.mark.parametrize("state", sorted(_NAV_STATES))
def test_the_nav_block_has_exactly_one_state_at_a_time(state: str):
    """⭐ 四種狀態**互斥**：一次只講一件事，不准把兩種灰疊在一起。

    ⛔ 「還沒讀」「讀不到」「讀到了是空的」「讀到了有資料」是**四個不同的事實**，
    疊在一起使用者無從判斷下一步該做什麼（本頁的職責就是回答「要不要我補」）。
    """
    _backend, _cov, _open = _NAV_STATES[state]
    _parts, _ = _run_gated(_backend, _cov, funds=FAKE_HOLDINGS, open_gate=_open)
    _body = _text(_segments(_parts)[nav_status_label()])
    _seen = {
        "還沒讀": _NOT_LOADED_NOTE in _body,
        "讀不到": any(_m in _body for _m in BACKEND_OFF["missing"]),
        "有資料": SPAN_PHRASE in _text(_parts),
    }
    # 空狀態自己是一個獨立單位（`_EMPTY_OPEN`），故在整份渲染流裡數。
    _seen["是空的"] = bool([_p for _p in _nav_parts(_parts) if _EMPTY_OPEN.match(_p)])
    _on = sorted(_k for _k, _v in _seen.items() if _v)
    _want = {"gate 未勾": ["還沒讀"], "後端未啟用": ["讀不到"],
             "讀到空": ["是空的"], "讀到有資料": ["有資料"]}[state]
    assert _on == _want, (
        f"（{state}）NAV 那一塊同時講了 {_on}，應該只有 {_want}：\n{_body}")


# ══════════════════════════════════════════════════════════════════
# 裁決 3：跨度**永遠**與點數同行 —— 驗的是機制，不是某一行長怎樣
# ══════════════════════════════════════════════════════════════════

#: 餵給 :func:`coverage_line` 的邊界輸入。**刻意包含壞值** ——
#: 「跨度不准單獨出現」這條性質**在壞資料上也必須成立**（那時最容易只印得出跨度）。
_LINE_INPUTS: tuple[dict, ...] = (
    {"points": 1, "first": "2026-01-01", "last": "2026-01-01", "span_days": 0},
    {"points": 2, "first": "2019-03-01", "last": "2026-03-01", "span_days": 2557},
    {"points": 9999, "first": "1990-01-01", "last": "2026-09-06", "span_days": 13398},
    {"points": 0, "first": "", "last": "", "span_days": 0},
    {"points": None, "first": None, "last": None, "span_days": None},
    {"points": "壞掉", "first": 12345, "last": [], "span_days": "壞掉"},
    {},
)


@pytest.mark.parametrize("entry", _LINE_INPUTS)
@pytest.mark.parametrize("held", [True, False])
def test_a_span_never_appears_without_its_point_count(entry: dict, held: bool):
    """⭐ **`coverage_line()` 的輸出裡只要有「跨度」，就一定有「點數」。**

    ⛔ **為什麼這條規則存在**：`span_days = last - first`，**它一個字都沒說中間有沒有斷**。
    單獨印一個「6.2 年」會被讀成「我有六年的完整歷史」，而真相可能是
    **兩個點相距六年**（:data:`_LINE_INPUTS` 第二筆就是這個形狀）。
    點數是唯一能戳破它的東西，所以兩者不准分開。

    ⚠️ **這是性質，不是字串比對**：對**任意**輸入（含壞值、空 dict）都成立，
    不綁死在任何一句文案上。改文案不會讓它失效。
    """
    _line = coverage_line("ABC123", entry, held=held)
    if SPAN_PHRASE in _line:
        assert POINTS_UNIT in _line, (
            f"這一行印了跨度卻沒有點數：{_line!r}\n"
            "跨度單獨出現會把「兩個點相距六年」講成「六年的歷史」（§1）。")
        _before = _line.split(SPAN_PHRASE, 1)[0]
        assert any(_ch.isdigit() for _ch in _before.split(POINTS_UNIT, 1)[0]), (
            f"這一行有「{POINTS_UNIT}」但它前面沒有數字，點數不是真的印出來了：{_line!r}")


def test_an_uncomputable_count_is_never_rendered_as_zero():
    """⭐ **點數算不出來時，畫面上不准出現 `0`** —— `0` 是宣稱，`None` 是「不知道」。

    ⛔ **這是本批自查出來的一個 §1 破口，不是派工單交代的。** 第一版寫的是
    `int(entry.get("points") or 0)` ＋ `except: _points = 0` ——
    一個讀不出來的值會被畫成「**0 筆**」，而它跟「**真的一筆都沒有**」
    在畫面上**長得一模一樣**。這一頁的職責正好是回答「這個數字可不可信」。

    **現行**：算不出來 → 整行改成「這一筆的點數讀不出來（原始值 …）」，
    而且**連跨度都不印**（沒有點數的跨度是這一頁最危險的那種數字：
    它看起來像一段完整歷史，而我們連有幾個點都不知道）。

    ⚠️ **本條驗的是性質，對每一種算不出來的形態都成立**，不綁死在某個字串。
    """
    for _bad in (None, "壞掉", [], {}, object()):
        _line = coverage_line("ABC123", {"points": _bad, "span_days": 999,
                                         "first": "2020-01-01", "last": "2026-01-01"})
        assert SPAN_PHRASE not in _line, (
            f"點數是 {_bad!r} 算不出來，卻還是印了跨度：{_line!r}")
        assert f"0 {POINTS_UNIT}" not in _line, (
            f"點數是 {_bad!r} 算不出來，卻被畫成 0：{_line!r}\n"
            "⛔ 0 是一個宣稱（「一筆都沒有」），我們沒有資格說它。")
    # 真的是 0 → 照印 0（那是一個我們算得出來的事實，不是猜的）。
    _zero = coverage_line("ABC123", {"points": 0, "span_days": 0,
                                     "first": "2026-01-01", "last": "2026-01-01"})
    assert f"0 {POINTS_UNIT}" in _zero and SPAN_PHRASE in _zero, _zero


def test_the_headline_says_when_some_counts_are_unreadable():
    """總結句**不准無聲低報** —— 算不出來的那幾筆要說出來。

    ⛔ 只把壞值「跳過」的話，總數會比實際少，而畫面上**完全看不出少了東西**。
    那是 §1 的另一種形狀：不是造假，是**無聲的低報**。
    """
    _mixed = {"OK1": {"points": 10, "first": "2026-01-01", "last": "2026-02-01",
                      "span_days": 31},
              "BAD1": {"points": "壞掉", "first": "", "last": "", "span_days": 0},
              "BAD2": {"points": None, "first": "", "last": "", "span_days": 0}}
    _got = coverage_headline(_mixed)
    assert f"10 {POINTS_UNIT}" in _got, f"可算的那一筆沒有被算進去：{_got!r}"
    assert "2" in _got and "讀不出來" in _got, (
        f"總結句沒有說出有幾筆算不出來，等於無聲低報：{_got!r}")
    assert SPAN_PHRASE not in _got and "年" not in _got, (
        f"總結句裡出現了跨度：{_got!r}")


#: 「一段時間有多長」在畫面上的形狀：**一個十進位數字，緊接著一個時間單位**。
#:
#: ⛔ **第一版寫成「有數字 or 有單位字」的兩個 `any()`，當場誤紅四個 state** ——
#:    `'⑤'.isdigit()` 在 Python 是 **`True`**（圈號屬 Numeric_Type=Digit），
#:    於是灰態那句「⑤ ⚙️ 設定與診斷 → …資料**日**期」同時滿足「有數字」與「有單位」。
#:    **那不是誤紅一次就算了的小事**：一條會誤紅的規則會被下一個人放寬或刪掉，
#:    然後真正的繞道就沒人擋了。改成**相鄰**判斷之後，那四個 state 全部乾淨。
#: ⚠️ **白名單，抓不到名單外的第 N+1 種寫法**（`weeks` / `季` / 中文數字「七年」）。**登記。**
#: ⚠️ **已知的偽陽性方向**：若哪天日期改成 `2024年01月05日` 這種寫法，本條會要求同行帶點數。
#:    那是**往安全側錯**（多一個「筆」不會說謊），登記，不是沒看到。
_DURATION_RE = re.compile(r"[0-9０-９]+(?:[.,][0-9０-９]+)?\s*(?:年|個月|月|週|天|日)")


def _duration_bearing_parts(parts: tuple[str, ...] | list[str]) -> list[str]:
    """渲染流裡印出「**一段時間有多長**」的那些元素（數字**緊接著**時間單位）。"""
    return [_p for _p in parts if _DURATION_RE.search(_p)]


@pytest.mark.parametrize("state", sorted(_NAV_STATES))
def test_no_rendered_line_shows_a_duration_without_its_point_count(state: str):
    """⭐⭐ **整頁**任何一則「有數字＋有時間單位」的字，都必須同行帶點數。

    ⛔ **2026-09-06 獨立稽核必修：本檔原本那三層「跨度不得單獨出現」的防禦，
    實際只有一層有效。** 稽核組加了一段**從 `first`/`last` 自己算年數**的程式
    （**完全沒碰 `"span_days"` 這個字串**）、印出 `[Caption] 最長 7.0 年`，
    然後 **92 passed × 3 序** —— 三層全瞎：

    ===================================  ======================================
    原本那一層                             為什麼看不到
    ===================================  ======================================
    AST：`"span_days"` 只在一處被讀         它沒有用那個字串
    渲染層：含 `SPAN_PHRASE` 的行要有點數    它印的是「最長 N 年」，不含「首末相距」
    純函式：`coverage_headline()` 不含跨度   它印在那個函式**外面一行**
    黑名單：`_PINNED_FAKE_VALUES` 釘 6.2 年  它印 7.0
    ===================================  ======================================

    ⚠️ **M3 突變（2 failed ×3）給了錯誤的信心** —— M3 改的是 `coverage_headline()`
    **內部**，所以純函式那條抓得到；**把同一句話印在那個函式外面一行，四層全部通過。**

    **本條是替代品，判準改成看「畫面上印了什麼」，不看「程式怎麼寫的」**：
    只要一個渲染元素同時有數字與時間單位，就必須同行帶 :data:`POINTS_UNIT`。
    **繞不過去** —— 因為要說謊就一定得把那個數字印出來。

    ⚠️ **本條是【整頁】的，不是 unit-scoped** —— 這是刻意的：
    本檔既有的 unit-scoped 守衛**全部看不見頁首**（`_units()` 只認 `####`，
    而頁首是 `## ` ＋ `st.caption`）。本條掃 `_flat()` 的全部元素，**含頁首**。

    ⚠️ **本條守不到的（照實列）**：
    - :data:`_DURATION_UNITS` 是白名單 —— 「個月」以外的寫法、英文 `years`、
      全形數字，都抓不到。
    - 它要求的是「**同一個渲染元素**內有點數」；把點數印在**上一行**、跨度印在下一行，
      本條看不到（那是 `_flat()` 以元素為單位的既有性質）。
    """
    _backend, _cov, _open = _NAV_STATES[state]
    _parts, _ = _run_gated(_backend, _cov, funds=FAKE_HOLDINGS, open_gate=_open)
    # ⛔ **縮到 NAV 區塊**（2026-09-06 委派化）：全頁掃會掃到被委派模組的教學文
    #    （`ui/tab6_manual.py` 裡就有「約 5.5 年」這種字），而那不是本頁寫的。
    #    完整理由與代價見 :func:`_nav_parts`。
    for _p in _duration_bearing_parts(_nav_parts(_parts)):
        assert POINTS_UNIT in _p, (
            f"（{state}）畫面上有一則帶時間長度的字，卻沒有點數：\n{_p}\n"
            "⛔ 一段沒有點數的「N 年 / N 天」會被讀成「我有這麼長的完整歷史」，"
            "而真相可能是兩個點（§1）。")


# ══════════════════════════════════════════════════════════════════
# 必修：上游把「跨度未知」編成 0 —— 不准照著印
# ══════════════════════════════════════════════════════════════════

def test_an_unknown_span_is_never_rendered_as_a_real_number():
    """⭐⭐ **上游的 `span_days == 0` 有兩個意思，畫面上不准把它們畫成同一個。**

    ⛔ **2026-09-06 獨立稽核必修，本組已端到端重現（不是讀出來的）**：
    `services/nav_history_gs.py::coverage_status` 在日期 parse 失敗時
    **把「未知」編成 `0`** —— 那一行的註解自己寫著「**跨度未知**，點數仍誠實回報」。
    而 `norm_date_key()` **刻意讓壞日期的原字串通過**，所以它真的會走到畫面上：

    ``BBB {'points': 2, 'first': '113/01/02', 'last': '2025-06-01', 'span_days': 0}``
    → 真實跨度 **約 1.4 年**，畫面卻印「首末相距 **0** 天」，
    與真的只有一天的 ``DDD`` **一模一樣**。

    ⚠️ **本條也記下本檔原本防錯格子這件事**：`_as_int → None` 那一整套瞄準的是
    `points`，而 `points` 在 production 恆為 `len(_ds)`、**永遠是 int**；
    **真正會出現「未知」的是 `span_days`** —— 防禦蓋在不會壞的那一格，會壞的那一格沒蓋。
    """
    _unknown = {"points": 2, "first": "113/01/02", "last": "2025-06-01",
                "span_days": 0}
    _really_zero = {"points": 1, "first": "2024-05-05", "last": "2024-05-05",
                    "span_days": 0}
    _l_unknown = coverage_line("BBB", _unknown)
    _l_zero = coverage_line("DDD", _really_zero)
    assert SPAN_PHRASE not in _l_unknown, (
        f"上游把「未知」編成 0，畫面照著印了一個假的跨度：{_l_unknown!r}")
    assert SPAN_PHRASE in _l_zero and f"{SPAN_PHRASE} 0 天" in _l_zero, (
        f"真的是 0 天卻不敢印 —— 那是反向的錯（§1 不是「什麼都別說」）：{_l_zero!r}")
    assert _l_unknown != _l_zero, "「未知」與「真的 0 天」畫成了同一行。"
    # 兩行都仍然要帶點數（跨度規則不因這次改動被繞開）。
    for _l in (_l_unknown, _l_zero):
        assert POINTS_UNIT in _l, _l


def test_the_unknown_span_rule_is_reproduced_against_the_real_service():
    """⭐ 用**真的** `coverage_status()`（注入假 worksheet，零網路）再證一次。

    ⛔ 上一條餵的是**手寫的** dict —— 那只證明「本頁對這個形狀的反應」。
    本條把同一件事**從上游走一遍**，證明**那個形狀真的產得出來**。
    ⚠️ 走 `_sheet=` 注入（`load_points` 的測試注入口），**不碰 gspread、不連網**。
    """
    from services.nav_history_gs import coverage_status as _real_coverage

    class _WS:
        def __init__(self, rows: list) -> None:
            self._rows = rows

        def get_all_values(self) -> list:
            return self._rows

    class _SH:
        def __init__(self, rows: list) -> None:
            self._ws = _WS(rows)

        def worksheet(self, _name: str) -> Any:
            return self._ws

    _rows = [
        ["code", "date", "nav", "fund_name", "source", "recorded_at", "currency"],
        ["BBB", "113/01/02", "10.0", "", "", "", ""],      # 民國年 → parse 不出來
        ["BBB", "2025-06-01", "11.0", "", "", "", ""],
        ["DDD", "2024-05-05", "12.0", "", "", "", ""],     # 只有一天 → 真的 0
    ]
    _got = _real_coverage(_sheet=_SH(_rows))
    assert _got["BBB"]["span_days"] == 0 and _got["DDD"]["span_days"] == 0, (
        f"上游不再把「未知」與「真的 0」編成同一個值了 —— 本條的前提變了，"
        f"請回頭重新評估 `span_days_or_unknown()` 還需不需要：{_got}")
    _lines = coverage_lines(_got, set())
    _bbb = [_l for _l in _lines if "BBB" in _l][0]
    _ddd = [_l for _l in _lines if "DDD" in _l][0]
    assert SPAN_PHRASE not in _bbb, f"未知的跨度被印出來了：{_bbb!r}"
    assert SPAN_PHRASE in _ddd, f"真的 0 天沒印出來：{_ddd!r}"


@pytest.mark.parametrize(
    "first,last,reported,want",
    [
        ("2024-01-01", "2024-01-01", 0, 0),          # 真的 0 天
        ("2024-01-01", "2024-12-31", 365, 365),      # 正常
        ("113/01/02", "2025-06-01", 0, None),        # 一端 parse 不出來
        ("2024-01-01", "壞掉", 0, None),              # 另一端 parse 不出來
        ("", "", 0, None),                           # 兩端都空
        ("2024-01-01", "2024-12-31", 999, None),     # 與上游回報不一致 → 不猜
        ("2024-12-31", "2024-01-01", -365, None),    # 負數 → 不合理
        ("2024-01-01", "20240101", 0, 0),            # ⚠️ 見下方偽陽性說明
        ("2024-01-01", "2024-W01-1", 0, 0),          # 同上（ISO 週日期，也是同一天）
    ],
)
def test_span_days_or_unknown_is_a_pure_decision(first: str, last: str,
                                                 reported: Any, want: Any):
    """:func:`span_days_or_unknown` 的判準 —— 純函式，逐案釘住。

    ⚠️ **最後兩列是刻意放進來的，而且它們的例子與派工單給的不一樣 —— 本組實測後更正**：
    派工單說「`date.fromisoformat` 在 3.11+ 接受 `2024-1-1`」。
    **實測（`python3.11.15`）：`2024-1-1` 會 `ValueError: Invalid isoformat string`**
    —— 3.11 放寬的是**大部分 ISO-8601 格式**，**不含未補零的欄位**。
    ⛔ **但那個顧慮的形狀是真的，只是例子舉錯了**：`"20240101"` 與 `"2024-W01-1"`
    **都 parse 得出來、都等於 `2024-01-01`、字串卻不同** —— 本組實測命中。
    → 也就是說，「`first != last` 而 `span_days == 0` ⟺ 至少一端 parse 不出來」
    **那條啟發式確實有偽陽性**，只是觸發它的是這兩個寫法而不是 `2024-1-1`。
    ✅ **本函式不用那條啟發式**（改成兩端各自 parse ＋ 與上游對帳），
    所以這兩列**回的是 0 而不是 None** —— **沒有那個偽陽性。**
    """
    assert span_days_or_unknown(first, last, reported) == want


# ══════════════════════════════════════════════════════════════════
# 應修：讀不懂的條目不准無聲丟棄
# ══════════════════════════════════════════════════════════════════

def test_unreadable_entries_are_disclosed_not_dropped():
    """⭐ 非 dict 的條目**要被說出來**，不准無聲丟棄成「0 檔」。

    ⛔ **2026-09-06 獨立稽核應修。** 原本 `coverage_headline` / `coverage_lines`
    兩處都是 `if not isinstance(_e, dict): continue` —— **同一個迴圈裡防了一種
    （`points` 讀不出來會揭露），漏了另一種（非 dict 連揭露都沒有）**：

    ``{'AAA': None, 'BBB': 'corrupt', 'CCC': [1, 2]}`` → 「**0 檔 · 共 0 筆**」
    ＋ 一個**空的**「逐檔明細」展開器。

    「0 檔」是一句**斷言**（你什麼都沒累積），而事實是我們收到了三筆讀不懂的東西（§1）。
    """
    _junk = {"AAA": None, "BBB": "corrupt", "CCC": [1, 2]}
    _head = coverage_headline(_junk)
    assert "3" in _head and "讀不出來" in _head, (
        f"三筆讀不懂的東西被無聲丟棄了：{_head!r}")
    assert "可讀取 0 檔" in _head, (
        f"「0 檔」沒有被限定成「可讀取 0 檔」—— 那是一句對使用者資產的斷言：{_head!r}")
    _lines = coverage_lines(_junk, set())
    assert len(_lines) == 3, f"讀不懂的條目沒有各自一行：{_lines}"
    for _c in _junk:
        assert any(_c in _l and "讀不出來" in _l for _l in _lines), (
            f"「{_c}」沒有被說出來：{_lines}")
    for _l in _lines:
        assert SPAN_PHRASE not in _l, f"讀不懂的條目卻印了跨度：{_l!r}"


def test_a_wholly_unreadable_payload_never_draws_an_empty_expander():
    """整包讀不懂時**不准畫一個空的展開器**（鐵則 04）。

    ⚠️ 舊版 `test_the_detail_expander_exists_only_when_there_is_data` 用
    `if not _coverage` 判斷，**不是**「有沒有可渲染的行」——
    `{'AAA': None}` 這種**非空但讀不懂**的回傳照樣過關。
    """
    _parts, _ = _run_gated(BACKEND_ON, {"AAA": None, "BBB": "x"},
                           funds=FAKE_HOLDINGS)
    assert NAV_DETAIL_LABEL in _nav_expanders(_parts), (
        "有讀不懂的條目要列出來，展開器不該消失。")
    _body = _text(_nav_expander_body(_parts, NAV_DETAIL_LABEL))
    assert "讀不出來" in _body, f"展開器是空的：{_body!r}"


def test_span_days_is_read_in_exactly_one_place():
    """⭐ **全檔只有 :func:`coverage_line` 可以讀 `span_days`。**

    上一條保證「那一個地方」不會只印跨度；本條保證**沒有第二個地方**。
    ⛔ 少了本條，任何人都可以在別處寫 `st.metric("最長", f"{e['span_days']//365} 年")`
    ——上一條完全看不到它（它只驗 `coverage_line` 的輸出）。
    **兩條合起來才是那句裁決；只留一條等於沒守。**

    ⚠️ **守不到的**：`entry.get(_K)`（把鍵名藏進一個常數）、
    `for k, v in entry.items()` 這種不提鍵名的走訪、以及 `**entry` 解包。
    本條認的是**字面字串 `"span_days"`**。**登記，不是沒看到。**
    """
    _tree_ = _tree()
    _defs = _func_defs(_tree_)
    _owner: dict[int, str] = {}
    for _name, _fn in _defs.items():
        for _n in ast.walk(_fn):
            _owner[id(_n)] = _name
    _hits = sorted({_owner.get(id(_n), "<module>")
                    for _n in _live_strings(_tree_) if _n.value == "span_days"})
    assert _hits == ["coverage_line"], (
        f"讀 `span_days` 的地方是 {_hits}，應該只有 `coverage_line`。\n"
        "⛔ 跨度只准由那一個函式印出來，因為只有它保證會同時印出點數（裁決 3）。")


def test_the_rendered_detail_never_shows_a_span_alone():
    """⭐ 渲染層再驗一次：畫面上任何一則帶 `SPAN_PHRASE` 的字，都要有點數。

    上面兩條走 AST／純函式；本條走**真的渲染出來的那串字**——
    三個角度都成立才算數（AST 可能被非字面寫法繞過，純函式測不到「誰真的被畫出來」）。
    """
    _parts, _ = _run_gated(BACKEND_ON, FAKE_COVERAGE, funds=FAKE_HOLDINGS)
    _with_span = [_p for _p in _parts if SPAN_PHRASE in _p and _p.startswith("[Markdown]")]
    assert _with_span, (
        f"有資料時畫面上找不到任何逐檔明細（`{SPAN_PHRASE}`）：\n{_text(_parts)}")
    for _p in _with_span:
        assert POINTS_UNIT in _p, (
            f"畫面上有一行只印了跨度、沒有點數：{_p!r}")


def test_the_headline_counts_but_never_spans():
    """總結那一句**只講數量**（檔數 ＋ 點數），一個跨度字都不准有。

    ⛔ 線框的示意值是「42 檔 · **最長 6.2 年**」—— 後半正是本裁決要擋的形狀：
    一個**單獨出現的跨度**，而且是**最大值**（最容易誤導的那一種）。
    """
    for _cov in (FAKE_COVERAGE, {}, _PROBE_COVERAGES[0], _PROBE_COVERAGES[1]):
        _got = coverage_headline(_cov)
        assert SPAN_PHRASE not in _got and "年" not in _got, (
            f"總結句裡出現了跨度：{_got!r}")
        assert POINTS_UNIT in _got and "檔" in _got, (
            f"總結句沒有同時給出檔數與點數：{_got!r}")
    # ⚠️ **「可讀取」三個字是承重的**（2026-09-06 獨立稽核）：沒有它，
    #    「0 檔」會被讀成「你一檔都沒累積」，而事實可能是「收到的東西全都讀不懂」。
    assert coverage_headline(FAKE_COVERAGE) == (
        f"可讀取 {len(FAKE_COVERAGE)} 檔 · 共 "
        f"{sum(_e['points'] for _e in FAKE_COVERAGE.values())} {POINTS_UNIT}")


def test_the_detail_is_sorted_and_marks_only_what_is_loaded():
    """逐檔明細**依代碼排序**（順序不隨 dict 插入序漂移），且只標記已列入的那些。

    ⛔ **沒列入的不准寫任何否定的話** —— `portfolio_funds` 開站不自動載入，
    「這一檔你沒有」是一句我們證明不了的話（§1）。本條只驗**有標記的那些是對的**。
    """
    _codes = sorted(FAKE_COVERAGE)
    _lines = coverage_lines(FAKE_COVERAGE, {"TESTCODE1"})
    assert [_ln.split("`")[1] for _ln in _lines] == _codes, (
        f"逐檔明細沒有依代碼排序：{_lines}")
    assert "已列入" in _lines[_codes.index("TESTCODE1")]
    assert "已列入" not in _lines[_codes.index("ZZOTHER9")]
    for _ln in _lines:
        for _lie in ("你沒有", "未持有", "不在你的"):
            assert _lie not in _ln, (
                f"逐檔明細對使用者的持有下了斷言 {_lie!r}：{_ln!r}")


def test_the_detail_expander_exists_only_when_there_is_data():
    """「逐檔可展開」**只在真的有逐檔可展開時才畫**（鐵則 04：不畫空的占位）。

    ⚠️ **本條有一個洞，2026-09-06 獨立稽核指出，已由另一條補上（本條保留）**：
    它餵的 `coverage` 要嘛有正常資料、要嘛是 `{}` —— **沒有測「非空但整包讀不懂」**
    （`{'AAA': None}`）。而頁面當時判斷用的是 `if not _coverage`，
    那種回傳**會走進資料分支、畫一個空的展開器**，本條完全看不到。
    → 補上的是 :func:`test_a_wholly_unreadable_payload_never_draws_an_empty_expander`；
    頁面端也改成看「**有沒有可渲染的行**」（`_lines`）而不是「dict 空不空」。
    **本條仍然有價值**（它守的是另外三種狀態不准畫展開器），故保留、不合併。
    """
    _with_data, _ = _run_gated(BACKEND_ON, FAKE_COVERAGE, funds=FAKE_HOLDINGS)
    assert NAV_DETAIL_LABEL in _nav_expanders(_with_data), (
        f"有資料卻沒有「{NAV_DETAIL_LABEL}」展開器。")
    for _label, _backend, _cov in (
            ("gate 未勾", BACKEND_ON, FAKE_COVERAGE),
            ("後端未啟用", BACKEND_OFF, FAKE_COVERAGE),
            ("讀到空", BACKEND_ON, {})):
        _parts, _ = _run_gated(_backend, _cov, funds=FAKE_HOLDINGS,
                               open_gate=_label != "gate 未勾")
        assert NAV_DETAIL_LABEL not in _nav_expanders(_parts), (
            f"（{_label}）沒有任何逐檔資料，卻先畫了一個空的「{NAV_DETAIL_LABEL}」展開器。")


# ══════════════════════════════════════════════════════════════════
# 裁決 2：「未啟用」與「一筆都沒有」是兩件事，不得共用文案
# ══════════════════════════════════════════════════════════════════

#: 用來驗「未啟用時畫面上不准出現數量」的**探針**涵蓋度。
#: ⚠️ 數字刻意是罕見長串 —— 本條要驗的是「**對任意 `coverage_status()` 回傳值成立**」，
#:    所以探針值由測試注入、不綁死頁面上任何一句文案。
_PROBE_COVERAGES: tuple[dict, ...] = (
    {"PRB1": {"points": 987654321, "first": "2001-02-03", "last": "2009-08-07",
              "span_days": 424242}},
    {"PRB2": {"points": 555555, "first": "1999-12-31", "last": "2000-01-01",
              "span_days": 313131},
     "PRB3": {"points": 777777, "first": "2010-10-10", "last": "2011-11-11",
              "span_days": 191919}},
    {},
)


@pytest.mark.parametrize("probe", _PROBE_COVERAGES)
def test_a_disabled_backend_never_prints_a_quantity(probe: dict):
    """⭐ **`status()["enabled"]` 是 False 時，畫面上不得出現任何代表「數量」的數字。**

    **機制有兩半，兩半都驗**（不綁死在任何一句產品文案上）：
    (a) **`coverage_status()` 一次都不會被呼叫** —— 沒讀就不可能有數字；
    (b) 即使把它換成會回**任意值**的探針，那些值**一個字都不會出現在畫面上**。

    ⛔ **為什麼要有這一條**：`coverage_status()` 在「未啟用」與「工作表不存在」時
    **都回 `{}`**（它自己的 docstring 逐字寫著「呼叫端須據此顯示『未啟用』
    而非『0 點』」）。少了 `enabled` 這道分流，一個**根本沒設定**的人
    會看到「0 檔 · 共 0 筆」——**那是一個我們沒有查證過的數字**（§1）。
    """
    _parts, _calls = _run_gated(BACKEND_OFF, probe, funds=FAKE_HOLDINGS)
    assert _calls["coverage"] == 0, (
        f"後端未啟用，卻還是去讀了雲端（{_calls}）—— "
        "分流的順序反了：要先問「能不能看」，再問「看到什麼」。")
    _all = _text(_parts)
    for _entry in probe.values():
        for _v in _entry.values():
            assert str(_v) not in _all, (
                f"後端未啟用，畫面上卻印出了探針值 {_v!r}：\n{_all}")
    assert "0 檔" not in _all, (
        "後端未啟用卻印了「0 檔」—— 我們沒看過那張表，說不出 0（§1：不知道 ≠ 沒有）。")


def test_the_disabled_state_names_what_is_missing():
    """未啟用時要說出**缺哪幾把 secret**，不只是「不可用」。

    `status()` 回的 `missing` 是它唯一能給的可行動資訊；吞掉它等於把
    「你少設了 google_service_account」壓成「這裡沒東西」。
    """
    _parts, _ = _run_gated(BACKEND_OFF, {}, funds=FAKE_HOLDINGS)
    _body = _text(_segments(_parts).get(nav_status_label(), []))
    for _m in BACKEND_OFF["missing"]:
        assert _m in _body, (
            f"未啟用的灰態沒有指名缺少的 {_m!r}：\n{_body}")
    assert NOT_READY_MARK in _body, "未啟用是灰態（我們看不到），不是空狀態（我們看到了、是空的）。"


def test_the_empty_state_only_appears_after_a_successful_read():
    """⭐ **空狀態只在「讀成功 ＋ 真的一筆都沒有」時出現。**

    這一條是舊 `test_the_empty_state_never_claims_the_user_has_no_funds` 的**替代品**，
    而且比它強：舊條要求文案帶「這個 session」這種限定詞，**因為那時我們根本沒讀**；
    現在我們**真的讀了**，所以可以對那張表下斷言 —— 而這條保證
    **只有讀成功那條路徑到得了空狀態**。

    ⛔ 三種路徑各驗一次：未啟用 → 灰態（0 個空狀態）；讀到空 → 恰好 1 個；讀到有資料 → 0 個。
    """
    _off, _ = _run_gated(BACKEND_OFF, {}, funds=FAKE_HOLDINGS)
    assert not [_p for _p in _nav_parts(_off) if _EMPTY_OPEN.match(_p)], (
        "後端未啟用卻走了空狀態 —— 「看不到」被講成「看到了、是空的」。")

    _on_empty, _ = _run_gated(BACKEND_ON, {}, funds=FAKE_HOLDINGS)
    _titles = [_m.group(1).strip() for _p in _nav_parts(_on_empty)
               if (_m := _EMPTY_OPEN.match(_p))]
    assert _titles == [_EMPTY_TITLE], (
        f"讀成功且一筆都沒有時，空狀態應恰好 1 個且是那一句：{_titles}")

    _on_data, _ = _run_gated(BACKEND_ON, FAKE_COVERAGE, funds=FAKE_HOLDINGS)
    assert not [_p for _p in _nav_parts(_on_data) if _EMPTY_OPEN.match(_p)], (
        "已經讀到資料了還畫空狀態。")


def test_the_empty_state_asserts_nothing_about_the_users_funds():
    """⭐ **客戶紅線：任何文案都不得對使用者的雲端資產下斷言。**

    ⛔ 2026-09-05 獨立稽核抓到的那組謊話（「一檔都還沒列入」「還沒有任何基金」）
    **黑名單原封保留**；改掉的只有**限定詞那半**——
    舊版要求文案帶「這個 session / 已載入」，理由是**我們那時根本沒讀過雲端**。
    現在空狀態只在讀成功之後出現（見上一條），那個限定詞會變成一句**假話**
    （它會說成「這個 session 沒載入」，而事實是「那張表真的是空的」）。
    **承重的保護搬去上一條**（＝結構性的「只有讀成功才到得了」），黑名單留著當第二層。

    ⚠️ 標題與內文**各查一次**，不查聯集 —— 使用者可能只讀到粗體標題那一行
    （2026-09-06 稽核必修的形狀，原封沿用）。
    """
    _parts, _ = _run_gated(BACKEND_ON, {}, funds=FAKE_HOLDINGS)
    _titles = [_m.group(1).strip() for _p in _nav_parts(_parts)
               if (_m := _EMPTY_OPEN.match(_p))]
    assert len(_titles) == 1, f"空狀態單位應恰好 1 個：{_titles}"
    # ⚠️ 委派化之後 `_units()` 只認六個區塊標題，空狀態**不再自成一個單位** ——
    #    改取整個 NAV 區塊當本文（走到空狀態時那一塊裡就只有它，見被測檔的四態分流）。
    _body = _text(_nav_parts(_parts))
    for _where, _txt in (("標題", _titles[0]), ("內文", _body)):
        for _lie in ("一檔都還沒列入", "還沒有任何基金", "你沒有基金", "一檔都沒有",
                     "你的基金", "你沒有累積"):
            assert _lie not in _txt, (
                f"空狀態的{_where}對使用者的資產下了斷言 {_lie!r}：\n{_txt}\n"
                "我們讀到的是**那張試算表**是空的，不是「他沒有基金」。")
        assert "nav_history" in _txt or "雲端" in _txt or "工作表" in _txt, (
            f"空狀態的{_where}沒有講清楚「空的是什麼」：\n{_txt}\n"
            "只寫「沒有資料」會被讀成「你沒有基金」。")


def test_the_empty_state_pointer_actually_works():
    """空狀態的「去哪補」是一個**地方**，而且指向本頁真的能動的那一塊。

    ⚠️ **與舊版同名，但驗的東西換了**：舊版驗「列入基金之後空狀態會消失」——
    那條路徑已經不存在（空狀態不再由 `portfolio_funds` 決定）。
    現在驗的是「指路指向 `手動補資料`」＋「那一塊真的在畫面上」。
    ⛔ **不宣稱它有效** —— 手動補抓本身還沒接上，那件事由
    :func:`test_pressing_submit_says_the_backfill_is_not_wired_yet` 誠實說出來。
    """
    _parts, _ = _run_gated(BACKEND_ON, {}, funds=FAKE_HOLDINGS)
    _titles = [_m.group(1).strip() for _p in _nav_parts(_parts)
               if (_m := _EMPTY_OPEN.match(_p))]
    # ⚠️ 委派化之後 `_units()` 只認六個區塊標題，空狀態**不再自成一個單位** ——
    #    改取整個 NAV 區塊當本文（走到空狀態時那一塊裡就只有它，見被測檔的四態分流）。
    _body = _text(_nav_parts(_parts))
    assert _where(nav_manual_label()) in _body, (
        f"空狀態沒有帶指路：\n{_body}")
    assert nav_manual_label() in [_n for _n, _ in _units(_parts)], (
        "空狀態指向「手動補資料」，但那一塊不在畫面上 —— 指路指到了不存在的地方。")


def test_the_empty_state_does_not_also_print_the_pending_excuse():
    """空狀態**不得**同時印「本頁分批上線」那句。

    兩種灰的下一步不同：空狀態的下一步是**去補資料**，
    「還沒接上」的下一步是**等我們接線**（使用者做不了）。
    ⛔ 疊在一起會讓使用者以為補資料也沒用 —— 一次只給一個。
    """
    _parts, _ = _run_gated(BACKEND_ON, {}, funds=FAKE_HOLDINGS)
    _empty_names = {_m.group(1).strip() for _p in _nav_parts(_parts)
                    if (_m := _EMPTY_OPEN.match(_p))}
    assert _empty_names, "讀成功且沒有資料時應該要有空狀態。"
    # 空狀態是 NAV 區塊**內**的一個東西，切段也要在那一塊裡做。
    _seg = {_t: _nav_parts(_parts) for _t in _empty_names}
    for _name in _empty_names:
        # ⚠️ 2026-09-06 委派化：「本頁分批上線」那句灰態**已經不存在**（那一塊接上了），
        #    本條的對象換成**還存在的**那一種灰 —— gate 沒勾的「尚未讀取」。
        #    **性質一字未變**：兩種灰的下一步不同（去補資料 vs 勾 gate），一次只給一個。
        assert _NOT_LOADED_NOTE not in _text(_seg.get(_name, [])), (
            f"空狀態單位「{_name}」裡混進了「尚未讀取」那句 —— "
            "我們已經讀到了（否則畫不出空狀態），一次只給一個。")

#:   「接上後這裡會逐源顯示**正常**或異常」，本條會**誤紅**（三序實測 1 failed）。
#:   下一批接真取數時第一個會撞到這個 —— **那時請改文案或就地收窄本條，不要靜靜刪掉它。**
#: ⚠️ 下面四個 `正常` 系片語已被裸「正常」涵蓋，**刻意保留**當作稽核抓到的原始紀錄。
_CONCLUSION_WORDS: tuple[str, ...] = (
    "正常",
    "全部正常", "沒有任何異常", "沒有異常", "資料可信", "都正常", "一切正常",
    "全部來源都正常", "無異常",
)


def test_no_grey_unit_states_a_conclusion():
    """⛔ 灰態單位內**不准下結論** —— 一塊還沒接線的東西，說不出「你的資料正常」。

    ⚠️ **本條是 2026-09-05 才補上的，補的是一個我自己宣稱「已經有人守」的缺口。**
    PR 描述與模組 docstring 原本寫著「『正常』那一格改由**『連線與金鑰必須是灰態』
    反向守** —— 一張灰卡不可能同時印一個『正常』的結論」。
    **那句是假的**：稽核四顆突變全數存活、三序一致 ——
    把 `_PENDING_NOTE` 換成「你的資料全部正常，沒有任何異常」→ **47 passed**；
    在金鑰灰卡的**同一個單位內**印「全部來源都正常，你的資料可信。」→ **47 passed**。
    **根因**：`STATE_NOT_READY` 無條件前綴 ⬜，而那條守衛只查 `⬜ in _body`。
    ⛔ **一句自稱有替代保護、實際沒有的宣稱，比單純「沒守到」更危險** ——
    它讓後人以為那一格有人看著。**那句已撤回**，本條是它的替代品。

    ⚠️ **本條同樣是黑名單，抓不到 `_CONCLUSION_WORDS` 以外的第 N+1 種說法**
    （例如「你的資料沒問題」）。**不要把它讀成「灰態不可能說謊了」。**

    ⛔ **2026-09-06 補：字表以外還有兩個【結構性】繞道，比「第 N+1 個詞」嚴重。**
    「抓不到第 N+1 個詞」是機率問題；下面兩個是**確定性**的 —— 只要不印在
    「有 ⬜ 的單位」裡面，**整份字表完全不生效**：
    - ⛔ **印在第一個單位之前**（頁首那兩行 `## 標題` ＋ `st.caption(...)`）→
      **綠**。`## ` 不是 `_L4_OPEN`（它只認 `####`），所以第一個 opener 是
      「**資料來源健康度**」那張卡；:func:`_units` 會**丟掉第一個 opener 之前的所有文字**。
      → **本頁自己的頁首 caption 落在每一條 unit-scoped 守衛的射程之外。**
    - ⛔ **印在刻意不灰的單位裡**（例如「使用手冊」）→ **綠**，因為
      `if NOT_READY_MARK not in _joined: continue` 直接跳過沒有 ⬜ 的單位。
      三序實測：把四個字表詞全塞進手冊的 caption → **50 passed**。
    ⚠️ **本輪不補這兩個洞**：頁首與非灰單位本來就允許出現一般說明文字，
    在骨架階段把字表擴到全頁會與 :data:`_PINNED_FAKE_VALUES` 的「不收正常」正面打架。
    **登記在此，不是沒看到。**
    """
    for _kind in ("empty", "missing", "loaded"):
        # ⛔ **只掃被測檔自己畫的那兩塊**（2026-09-06 委派化，見 :func:`_page_authored_parts`）：
        #    委派之後，別的區塊裡的字是**被委派模組**寫的 —— 例如 `📖 使用手冊`
        #    的教學文就有「✅ 配置正常，無需再平衡」，全頁掃會被它打紅，而本頁沒錯。
        for _unit, _body in ((_n, _b) for _n, _b in _units(_stream(_kind))
                             if _n in (BLOCK_HEALTH, nav_status_label())):
            _joined = _text(_body)
            if NOT_READY_MARK not in _joined:
                continue
            for _w in _CONCLUSION_WORDS:
                assert _w not in _joined, (
                    f"（{_kind}）灰態單位「{_unit}」裡出現了結論性字眼 {_w!r}：\n"
                    f"{_joined}\n"
                    "⛔ 這一塊還沒接線，我們沒有查過任何來源 —— "
                    "說「正常」是憑空捏造一個系統健康狀態的結論（§1）。")

def test_the_page_never_hand_rolls_the_grey_mark():
    """⬜ 一律由 `render_state` 產生 —— 被測檔不准自己拼那個字元。

    ⚠️ 自己拼 ⬜ 等於繞過三態 SSOT（鐵則 03）：顏色語意就有了第二個決定點。
    """
    _bad = [f"第 {_n.lineno} 行 {_n.value!r}" for _n in _live_strings(_tree())
            if NOT_READY_MARK in _n.value]
    assert not _bad, (
        f"被測檔自己拼了灰態記號 {NOT_READY_MARK!r}：{_bad}\n"
        "請走 `render_state.not_ready()` / `ia.state_card(state=STATE_NOT_READY)`。")

# ══════════════════════════════════════════════════════════════════
# D-3：線框示意值一個都不准畫
# ══════════════════════════════════════════════════════════════════

#: 線框 Tab 05 三張示意卡上的 `<span class="big">` 值，以及它們的組成片段。
#: ⚠️ 「正常」**刻意不收**（理由見模組 docstring 的「守不到」段）。
_PINNED_FAKE_VALUES: tuple[str, ...] = (
    "18 源 · 2 異常", "18 源", "2 異常",
    "42 檔 · 最長 6.2 年", "42 檔", "最長 6.2 年", "6.2 年",
)


def test_the_page_never_prints_the_illustrative_values_from_the_wireframe():
    """⛔ 線框那幾張示意卡上的數字不准出現在畫面上（**只涵蓋下列字面寫法**）。

    **為什麼這一頁尤其要有這條**：使用者進 ⑤ 就是要問「我的資料到底可不可信」——
    一個假的「2 異常」或「42 檔」會**直接被當成那個問題的答案**，
    而他**完全看不出它是假的**（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ## ⚠️ 這條**實際**守得到什麼（照實寫，不要用形容詞）

    **只釘 `_PINNED_FAKE_VALUES` 這 7 個字面寫法。**
    **明確守不到**：裸數字（`18` / `42` 不帶單位字）、全形數字、換成別的寫法
    （「18 個來源」）、以及**任何線框以外的捏造值** ——
    黑名單結構上抓不到名單外的第 N+1 個。

    ## ⚠️ 「正常」為什麼不在名單裡

    它是極常見的一般用詞，釘它會把往後任何一句合法說明打紅。
    ⛔ **2026-09-05 撤回**：本段原接著寫 ~~「那一格改由『連線與金鑰必須是灰態』
    **反向守** —— 一張灰卡不可能同時印一個「正常」的結論」~~ —— **實測為假**
    （四顆突變全存活，理由與根因見模組 docstring）。
    **那一格現在由 :func:`test_no_grey_unit_states_a_conclusion` 用另一份黑名單守，
    不是由「必須是灰態」那條反向守。**

    ⛔ **2026-09-06 再修一次 —— 上面那句在寫下的當天做不到它宣稱的事。**
    那份黑名單當時**八個全是片語、沒有裸「正常」**，於是在灰卡的同一單位內印
    `st.caption("18 個來源目前狀態：正常")` → **50 passed 三序，一條都沒紅**。
    **前一輪撤回了一句假的補償控制（「灰態那條反向守」），然後換上另一句假的。**
    現已把裸「正常」補進 :data:`_CONCLUSION_WORDS`，該突變三序皆紅。
    ⚠️ **兩份名單的政策不同，不要混為一談**：本條（全頁）**仍然不收**「正常」，
    理由如上；收得起的是那份**只掃帶 ⬜ 的灰態單位**的窄名單。
    ⚠️ 因此「正常」**只在灰態單位內**被擋 —— 印在頁首 caption 或使用手冊裡，
    **兩份名單都看不到**（見 :func:`test_no_grey_unit_states_a_conclusion` 的登記）。
    """
    for _kind in ("empty", "missing", "loaded"):
        _all = _text(_stream(_kind))
        for _fake in _PINNED_FAKE_VALUES:
            assert _fake not in _all, (
                f"（{_kind}）畫面上出現了線框的示意值 {_fake!r} —— "
                "那不是資料，是線框用來示範版面的假數字。"
                "這一頁的職責就是回答「資料可不可信」，在這裡放假數字是最壞的一種。")


def test_the_page_invents_no_source_list_or_column_list():
    """⛔ 不准自己發明一份「來源清單」或「欄位清單」。

    線框對「資料來源健康度」**只寫了內容類型**（每源最後成功時間與資料日期），
    **沒有列出是哪 18 個源**；對「逐檔結果」也沒有列欄位。
    憑印象補一份，下一批接真資料時就會發現對不上 —— 那是自己發明規格。

    ⛔ **判準是「模組層有沒有一個看起來像清單的常數」**，不是「畫面上有沒有那些字」——
    後者在骨架階段恆為真（什麼都還沒接），驗不到任何東西。

    ⛔ **本條走 `Assign` ＋ `AnnAssign` 兩種**（見 :func:`_module_level_names`）——
    ④ 的同型守衛原本只走 `ast.Assign`，而被測族的常數**幾乎都是 `AnnAssign`**，
    那條守衛因此**一個字都看不到**，2026-09-05 由獨立稽核抓到。
    """
    _bad = [_t.id for _t in _module_level_names(_tree())
            if any(_k in _t.id.upper() for _k in ("COLUMN", "SOURCES", "SOURCE_LIST"))]
    assert not _bad, (
        f"被測檔多了看起來像清單的常數：{_bad}\n"
        "線框沒有列出來源清單／欄位清單 —— 補一份等於自己發明規格。")

def test_the_page_draws_no_grid_form_or_tabs_of_its_own():
    """鐵則 01 / 02 一律走共用元件；巢狀 `st.tabs` 一個都不准有。

    ⚠️ **`st.columns` 那半只有本條在守**（全域 `tests/test_ui_grid_contract.py`
    抓的是「欄數不是 3」，欄數剛好是 3 的自建網格它放行）。
    ⛔ **繞得過**：`getattr(st, "columns")(3)` / `from streamlit import columns as _c`
    —— repo 既有性質（③ 已登記），不是本頁造成的。
    """
    _bad = _attr_calls(_tree(), ("columns", "form", "tabs", "dataframe"))
    assert not _bad, (
        f"被測檔自己畫了網格／表單／分頁／大表：{_bad}\n"
        "鐵則 01/02 一律走 `ui.helpers.ia`（`card_row` / `applied_form` / `wide_table`）；"
        "巢狀 `st.tabs` 線框明文禁止。")

#: ⚠️ **2026-09-06（P05-1）從「一個都不准」放寬成「只准這一個」，理由寫在這裡。**
#:    舊版寫「本批連取數都還沒有，更不該有」—— 那句話在**骨架批**是對的，
#:    它的前提是「這一頁還沒有任何真內容」。P05-1 把 NAV 累積狀態接上了真取數，
#:    **前提消失，條文跟著換**（不是把守衛放寬去遷就程式碼）。
#: ⛔ **放寬的射程只有一個模組名**：`repositories`（L1）、`infra`（L0）、
#:    `requests` / `httpx` / `gspread` / `yfinance` / `pandas` **一個都沒鬆**，
#:    其餘 `services.*` 也**一個都沒鬆** —— 想再加一個就得再改這一行，
#:    而改這一行會出現在 diff 裡。**這正是它該長的樣子。**
#: ⚠️ `ui/**` → `services/**` 是 `CLAUDE.md §8.2` 的**正常方向**（L3→L2），
#:    不需要任何憲法例外；本 repo 既有的 `ui/tab5_data_guard.py` 也是這樣呼叫它。
_ALLOWED_SERVICE_MODULES: frozenset = frozenset({"services.nav_history_gs"})


def test_the_page_never_reaches_into_the_data_layer():
    """View 不得直接碰 L1／L0／HTTP；L2 只准 :data:`_ALLOWED_SERVICE_MODULES` 那一個。

    ⚠️ **`_imported_modules()` 對 `from X import Y` 會同時吐 `X` 與 `X.Y`**
    （見該函式 docstring），所以判定要**兩種形狀都認**：
    `services.nav_history_gs` 本身、以及 `services.nav_history_gs.<符號>`。
    ⛔ **點邊界不能省**：裸 `startswith` 會讓 `services.nav_history_gs_v2`
    這種**不同的模組**跟著被放行（同本檔 `..._does_not_delegate_to_the_old_tabs`
    2026-09-05 修過的那個洞）。
    """
    _banned_roots = ("repositories", "infra", "requests", "httpx",
                     "pandas", "yfinance", "gspread")
    _bad: list[str] = []
    for _m in _imported_modules(_tree()):
        _root = _m.split(".")[0]
        if _root in _banned_roots:
            _bad.append(_m)
        elif _root == "services" and not any(
                _m == _a or _m.startswith(_a + ".") for _a in _ALLOWED_SERVICE_MODULES):
            _bad.append(_m)
    assert not _bad, (
        f"被測檔 import 了不准碰的資料／計算層：{_bad}\n"
        f"L2 只准 {sorted(_ALLOWED_SERVICE_MODULES)}；L1（`repositories`）與 L0（`infra`）"
        "以及任何 HTTP client 一律不得直呼。")


def test_the_service_allowlist_is_not_a_dead_letter():
    """⭐ 錨點：白名單上的模組**必須真的存在，而且真的被本頁 import**。

    ⛔ 沒有這一條，白名單就會變成一張**只增不減**的紙：
    模組改名 → 上一條照樣綠（它只檢查「有沒有 import 不該 import 的」，
    白名單上的東西不見了它一個字都不會說），於是那一行放寬會**永久留在檔案裡**，
    替下一個人開一道沒有人記得為什麼存在的門。
    """
    for _a in _ALLOWED_SERVICE_MODULES:
        assert (ROOT / (_a.replace(".", "/") + ".py")).is_file(), (
            f"白名單上的 {_a!r} 在磁碟上不存在 —— 放寬條文指向一個不存在的模組。")
    _imported = set(_imported_modules(_tree()))
    _unused = sorted(_a for _a in _ALLOWED_SERVICE_MODULES if _a not in _imported)
    assert not _unused, (
        f"白名單上的 {_unused} 本頁根本沒有 import —— "
        "放寬條文已經沒有用途，請把它降回來（`CLAUDE.md §8.2.A.0` 規則 2 的雙向 ratchet）。")

def test_the_page_does_not_render_cache_or_backoff_state():
    """⛔ 線框「這裡不放什麼」逐字：「**快取與退避狀態不做成畫面**」。

    ⚠️ 判準是**模組層有沒有相關常數／有沒有 import 那些模組**，
    不是「畫面上有沒有那幾個字」—— 後者在骨架階段恆為真，驗不到東西。
    """
    _names = [_t.id.upper() for _t in _module_level_names(_tree())]
    # ⚠️ **2026-09-06 補登記：這一行的子字串比對也會誤紅，而且機率遠高於下面那個
    #    `_bad_imports`（它已經有五行登記，這一行原本一個字都沒有）。**
    #    `"TTL" in _n` 會命中 `_SETTLEMENT_DATE_COL`（基金**交割日**欄名，
    #    與快取毫無關係）—— **三序實測：`常數 ['_SETTLEMENT_DATE_COL']` 打紅。**
    #    同族還有 `_SETTLE_*` / `_BOTTLENECK_*`。
    #    ⛔ **本輪刻意不收窄判準**：改成 `_TTL` / `TTL_` 之類的前後綴會不會**漏放**
    #    （例如 `NAV_TTL_SECONDS` 以外的寫法）**需要另外評估，不在本批射程**。
    #    取捨與下面那段相同：這一條要防的東西（偷偷把快取／退避狀態做成畫面）
    #    值得寧可誤紅、不可漏放 —— 真的誤紅時改的人會來讀這一行並就地決定。
    #    **登記在此，不是沒看到。**
    _bad_names = [_n for _n in _names
                  if any(_k in _n for _k in ("BACKOFF", "CACHE", "TTL"))]
    # ⚠️ **這一處刻意保留寬鬆的子字串比對**（2026-09-05 稽核點名）：
    #    `"backoff" in _m` 會把 `from ui.helpers.render_state import backoff_free_note`
    #    這種名字誤判成「碰了退避」。**本批不收窄，理由是這一條要防的東西
    #    （偷偷把退避狀態做成畫面）值得寧可誤紅、不可漏放** ——
    #    真的誤紅時，改的人會來讀這一行並就地決定；漏放則沒有人會發現。
    #    **登記在此，不是沒看到。**
    _bad_imports = [_m for _m in _imported_modules(_tree())
                    if "backoff" in _m or "source_backoff" in _m or _m.endswith("ttls")]
    assert not _bad_names and not _bad_imports, (
        f"被測檔碰了快取／退避：常數 {_bad_names}、import {_bad_imports}\n"
        "線框明文：那批不必改任何畫面，本次不推翻。")

def test_the_page_writes_only_its_own_session_key():
    """本頁只准寫**自己命名空間**的 session 鍵，不准動別人的。

    ⚠️ **session 寫入有四條管道，四條都要看**（本 repo 既有的失效模式）：

    == ======================== ==============================================
    #  管道                      長相
    == ======================== ==============================================
    1  下標賦值                  `st.session_state["k"] = v`
    2  **屬性賦值**              `st.session_state.k = v`（本 repo 的主流寫法）
    3  `.update()` / `.setdefault()`
    4  ⭐ **widget 的 `key=`**   streamlit **代呼叫端寫入**；AST 上是普通 `ast.Call`，
                                **任何「找賦值節點」的手段都收不到它**
    == ======================== ==============================================

    ⚠️ **2026-09-06 委派化：白名單從 `_SK_APPLIED` 換成 `_SK_DIAG_GATE`。**
    自寫 Form 退役 → 那個鍵沒了；新增的是資料來源健康度 gate 的 key。
    **白名單仍然只有一個名字**，射程一格未鬆。

    ⛔ **本條在委派之下更重要，不是更不重要**：被測檔現在會呼叫四支舊模組，
    而那些模組**自己**會寫一堆 session —— 本條只掃**被測檔自己的原始碼**（AST），
    所以委派進來的寫入不會誤紅，但**被測檔自己順手寫別人的鍵**照樣會紅。

    📌 **待辦（登記，本輪沒做）**：`tests/_ast_bindings.py`（#785 已合併）有這段共用實作，
    `wf02`/`wf03`/`wf04`/`settings_diag_merge` 四檔已改為 import 它。
    **本檔還沒改，而且是刻意的** —— 那是一次會動到本條斷言邏輯的重構，
    不在本批射程內。**共用 helper 已經在了，本條應改為 import 它、不要留兩份**
    （`CLAUDE.md §2.1`）；交給碰到本檔的下一批。本組沒有做，不假裝做了。
    """
    _tree_ = _tree()
    _allowed = {_SK_DIAG_GATE}
    _writes: list[str] = []
    for _n in ast.walk(_tree_):
        _targets: list[ast.AST] = []
        if isinstance(_n, ast.Assign):
            _targets = list(_n.targets)
        elif isinstance(_n, (ast.AugAssign, ast.AnnAssign)):
            _targets = [_n.target]
        for _t in _targets:
            # `x = st.session_state.get(...)` 是**讀**，target 是 Name，不會命中。
            if isinstance(_t, ast.Subscript) and "session_state" in _dotted(_t.value):
                _key = _dotted(_t.slice)
                if _key not in {"_SK_DIAG_GATE"} | {repr(_k) for _k in _allowed}:
                    _writes.append(f"L{_n.lineno} 下標賦值 {_dotted(_t)}")
            elif isinstance(_t, ast.Attribute) and "session_state" in _dotted(_t.value):
                _writes.append(f"L{_n.lineno} 屬性賦值 {_dotted(_t)}")
        if isinstance(_n, ast.Call):
            _d = _dotted(_n.func)
            if ("session_state" in _d
                    and _d.rsplit(".", 1)[-1] in ("update", "setdefault")):
                _writes.append(f"L{_n.lineno} {_d}(...)")
            # 形態 4：widget 帶 `key=` —— streamlit 會代為寫入 session_state。
            # ⚠️ **2026-09-06 收緊而不是放寬**：舊版是「只要帶 `key=` 就紅」，
            #    那在被測檔一個 `key=` 都沒有的時候等價於本版，**但它擋不住**
            #    「帶了一個**別人的** key」——因為它根本不看 key 是什麼。
            #    現在改成**看 key 的名字**：不在白名單裡才紅。
            # ⛔ **fail-closed**：key 不是單純名稱／字面值（例如算出來的 f-string）→
            #    照樣紅，因為那時本守衛**無法證明**它在白名單內。
            for _k in _n.keywords:
                if _k.arg != "key" or not _d.startswith("st."):
                    continue
                _src = _dotted(_k.value)
                if _src not in {"_SK_DIAG_GATE"} | {repr(_x) for _x in _allowed}:
                    _writes.append(f"L{_n.lineno} widget key={_src} → {_d}")
    assert _writes == [], (
        f"被測檔寫了自己命名空間以外的 session：{_writes}\n"
        f"本頁只准寫 {_SK_DIAG_GATE!r}（`portfolio_funds` 是**別人定義**的鍵，只讀不寫）。\n"
        "（widget `key=` 也算：streamlit 會代你把 widget 值寫進 session_state。）")


def test_the_page_does_not_call_a_no_op_story_nav():
    """⛔ 不准照抄 `render_story_nav("settings")` —— 它會**靜默什麼都不畫**。

    `story_nav.render_story_nav()` 第一行是
    ``if _as_tab_key(current) not in _VALID: return``，而決策動線只有**四站**；
    `render_flow_nav` 的 docstring 自己就寫著「**⑤ 設定與診斷不在其中**」。

    ⚠️ 照抄 ①②③④ 那一行進來，會得到一個**看起來有做、實際是 no-op** 的呼叫，
    下一個人得自己去讀 `_VALID` 才知道它從來沒生效過。
    """
    _bad = [f"L{_n.lineno}" for _n in ast.walk(_tree())
            if isinstance(_n, ast.Call) and _dotted(_n.func).endswith("render_story_nav")]
    assert not _bad, (
        f"被測檔呼叫了 `render_story_nav()`：{_bad}\n"
        "⑤ 不在決策動線四站內，那個呼叫會靜默 no-op —— "
        "一個看起來有做、實際沒生效的呼叫，比不寫更糟。")

# ══════════════════════════════════════════════════════════════════
# 區塊名：兩個走 SSOT、三個線框字面；以及那個尚未裁決的撞名
# ══════════════════════════════════════════════════════════════════

def test_the_two_ssot_block_names_are_not_hand_copies():
    """`NAV 累積狀態` / `手動補資料` **必須**走 `section_label()`，不得手抄字面。

    ⚠️ 這兩個**在 SSOT 裡有 key**（`nav_status` / `nav_manual`，2026-09-02 加入）——
    有 key 卻手抄，就是本 repo 已經發作三次的那個病（指路指到不存在的東西）。
    ⚠️ 另外三塊（健康度／金鑰／使用手冊）**SSOT 沒有 key**，本批不得新增 key，
    故照線框字面 —— 那三個不在本條射程內。
    """
    _src = SRC.read_text(encoding="utf-8")
    assert "section_label(\"nav_status\")" in _src, (
        "「NAV 累積狀態」沒有走 SSOT —— 它在 `_SECTION_LABELS` 裡有 key。")
    assert "section_label(\"nav_manual\")" in _src, (
        "「手動補資料」沒有走 SSOT —— 它在 `_SECTION_LABELS` 裡有 key。")
    for _n in _live_strings(_tree()):
        assert _n.value != section_label("nav_status"), (
            f"第 {_n.lineno} 行手抄了 SSOT 的字面值 {_n.value!r}，請走 `section_label()`。")
        assert _n.value != section_label("nav_manual"), (
            f"第 {_n.lineno} 行手抄了 SSOT 的字面值 {_n.value!r}，請走 `section_label()`。")


def test_the_three_wireframe_literal_names_match_the_wireframe():
    """另外三塊的字面值必須與線框 `<h4>` 逐字相同。

    ⚠️ 這條**不比對線框檔案本身**（那會讓測試依賴一份 HTML 的排版），
    而是把線框逐字釘在這裡 —— 線框哪天改了，這條會轉紅，那正是要人回來看的時候。
    """
    assert BLOCK_HEALTH == "資料來源健康度", BLOCK_HEALTH
    assert BLOCK_KEYS == "連線與金鑰", BLOCK_KEYS
    assert BLOCK_MANUAL == "使用手冊", BLOCK_MANUAL


def test_the_manual_name_collision_is_still_registered():
    """⚠️ **狀態鎖**：`BLOCK_MANUAL`（「使用手冊」）與 `section_label("manual")`
    （「📖 說明書」）**目前是兩份真相源，而這件事尚未裁決**。

    被測檔的模組 docstring 已就地登記並回報總管；本條把那個**狀態**釘住：
    哪天 SSOT 那一格被改成線框字面（＝正解落地、撞名消失），**這條會轉紅** ——
    那正是要人回來把被測檔的那段登記收掉、改走 `section_label("manual")` 的時候。

    ⛔ **這條不是在說現在的做法是對的**，它是在說「這個歧異還在，別忘了它」。
    """
    assert BLOCK_MANUAL != section_label("manual"), (
        f"`BLOCK_MANUAL`（{BLOCK_MANUAL!r}）與 `section_label('manual')`"
        f"（{section_label('manual')!r}）現在一樣了 —— 撞名已消失。\n"
        "請把被測檔模組 docstring 裡那段「尚未裁決的張力」收掉，"
        "並把 `BLOCK_MANUAL` 改成走 `section_label('manual')`，然後刪掉本條。")

# ══════════════════════════════════════════════════════════════════
# `_holdings()`：⑤ 刻意不做 loaded 過濾
# ══════════════════════════════════════════════════════════════════

def test_holdings_keeps_the_not_yet_loaded_ones_on_purpose():
    """⭐ ⑤ 的 `_holdings()` **刻意不過濾 `loaded`** —— 與 ②④ 故意不同。

    ②④ 問的是「**拿這幾檔去算**」，沒載入的算進去會生出不完整的結論（§1）；
    ⑤ 的 NAV 累積狀態問的是「**雲端歷史涵蓋了哪幾檔**」，
    而**「已列入但還沒抓回來」正是這一頁最該顯示的那一種** ——
    把它濾掉，等於讓「該補的那幾檔」從一個專門看「要不要我補」的畫面上消失。
    """
    import streamlit as _st
    try:
        _st.session_state["portfolio_funds"] = FAKE_HOLDINGS
        _got = _holdings()
        assert len(_got) == 2, (
            f"⑤ 不該過濾 `loaded=False` 的項目 —— 那正是這一頁要顯示的：{_got}")
    finally:
        _st.session_state.pop("portfolio_funds", None)


@pytest.mark.parametrize("bad", [None, "不是 list", 123, {"a": 1}])
def test_holdings_survives_a_corrupted_session_value(bad: Any):
    """session 裡是髒值 → 回空 list，不炸也不假裝有資料。"""
    import streamlit as _st
    try:
        _st.session_state["portfolio_funds"] = bad
        assert _holdings() == []
    finally:
        _st.session_state.pop("portfolio_funds", None)


def test_holdings_drops_non_dict_entries():
    """list 裡混了非 dict 的東西 → 丟掉它，不讓它流進下游。"""
    import streamlit as _st
    try:
        _st.session_state["portfolio_funds"] = [{"code": "A"}, "壞掉的項目", None]
        assert _holdings() == [{"code": "A"}]
    finally:
        _st.session_state.pop("portfolio_funds", None)

# ══════════════════════════════════════════════════════════════════
# 沒有任何一塊悄悄變成紅框
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_no_block_silently_renders_a_system_error(kind: str):
    """任何一塊拋例外都會被 `safe_section()` 畫成紅框 —— 骨架階段不該有任何紅框。

    ⚠️ `safe_section` **不吞例外**（§1），它畫顯式紅框 ＋ traceback；
    但**紅框不會讓測試失敗**，所以要有這條去看它。
    """
    _reds = [_p for _p in _stream(kind) if _p.startswith("[Error]")]
    assert not _reds, (
        f"（{kind}）有區塊掉進 `safe_section()` 的紅框：\n" + "\n".join(_reds))
