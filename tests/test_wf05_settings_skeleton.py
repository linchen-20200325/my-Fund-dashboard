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
→ **現行只認本頁自己那六個區塊標題**（:func:`_block_order`，逐一具名比對）。
   ⚠️ **2026-09-06 就地更正**（有意識的更正，不是漏刪）：本行原寫
   ~~`:data:`_BLOCK_ORDER``~~ —— **本檔沒有這個名字**（實測 0 個定義），
   它是一個**函式** `_block_order()`。同型錯誤本輪共修 5 處，逐處就地標註。
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
    CONCLUSION_HEADING,
    DIAG_GATE_LABEL,
    EVIDENCE_HEADING,
    _FAILURE_ALLOWANCE,
    _VERDICT_CHECKED,
    _VERDICT_UNCHECKED,
    NAV_DETAIL_LABEL,
    NAV_GATE_LABEL,
    POINTS_UNIT,
    SPAN_PHRASE,
    _DIAG_NOT_LOADED_NOTE,
    _EMPTY_TITLE,
    _NOT_LOADED_NOTE,
    _SK_DIAG_GATE,
    _below,
    _conclusion_cards,
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


def _str_consts_in(fn: ast.FunctionDef) -> list[str]:
    """函式體裡的**字串字面值**，**docstring 除外**。

    ⭐ **2026-09-09 第三輪回修新增。它存在的理由是一顆存活的突變。**

    `test_the_key_card_does_not_point_at_a_block_that_cannot_answer_it` 原本拿
    **呼叫名**（`_dotted(call.func)`）去找「這個函式有沒有開始自己畫金鑰面板」——
    但畫東西的證據**不在呼叫名裡，在傳給它的字串裡**：
    `st.markdown("### ④ 🔑 API 金鑰狀態")` 的呼叫名是 `st.markdown`，
    跟任何別的 `st.markdown` 一模一樣。**要量的是引數，不是被呼叫的那個名字。**

    ⚠️ **為什麼一定要排除 docstring**：`_render_keys` 的 docstring **正當地**討論
    「API 金鑰狀態 / NAS Proxy 測試仍住在 `render_data_guard_tab()` 深處」——
    那是**登記一個已知缺口**，不是在畫面上畫它。
    把 docstring 算進來會讓這條**對一份誠實的登記發紅燈**，
    而下一個人最省事的解法就是**把那段登記刪掉**——
    **一條會逼人刪掉誠實紀錄的守衛，比沒有守衛更糟。**

    ⚠️ **擋不到什麼，照實寫**：f-string 裡**插值出來**的字（`f"### {x}"` 的 `x`）
    本函式看得到 `"### "` 但看不到 `x` 的值；動態組字串（`"##" + "# 標題"`）看不到。
    **它驗字面值，不驗執行後的畫面。**
    """
    _body = (fn.body[1:] if (fn.body and isinstance(fn.body[0], ast.Expr)
                             and isinstance(fn.body[0].value, ast.Constant)
                             and isinstance(fn.body[0].value.value, str))
             else fn.body)
    return [_n.value for _st in _body for _n in ast.walk(_st)
            if isinstance(_n, ast.Constant) and isinstance(_n.value, str)]


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
    **(1) 實際是三個消費者**（~~取第一段的 `..._never_reaches_into_the_data_layer`、
    `startswith` 的 `..._does_not_delegate_to_the_old_tabs`、以及
    `..._does_not_render_cache_or_backoff_state`~~）。

    ⚠️ **2026-09-06 就地更正：上面那份【名單】已經過期（有意識的更正，不是漏刪）。**
    `test_the_page_does_not_delegate_to_the_old_tabs` **在本 PR 內被移除了**
    （commit `7e5677a`，見模組 docstring 的移除表 B 類），
    所以它**不再是本函式的消費者**。
    ⚠️ **講精確一點，不要講過頭**：那個名字**不是全 repo 消失** ——
    `tests/test_wf03_research_skeleton.py` 與 `tests/test_wf04_portfolio_skeleton.py`
    **各自還有一條同名守衛**（③④ 的，射程不同、也不呼叫本函式）。
    **消失的是「本檔的那一條」** —— 而本段講的正是「**本檔**的消費者」，
    所以照著它在本檔裡找的人會找不到。
    ⛔ **注意「三個」這個數字碰巧仍然對，但成員錯了一格** ——
    那正是 `CLAUDE.md §-2.A` 記過的「**數字對了不代表清單對了**」。
    **實測（AST 數 `_imported_modules(` 的呼叫點，非 grep）**：
    `origin/main` **4 處**、本分支 **3 處**，現行三個消費者是：

    ===================================================  =========================
    消費者                                                 它怎麼比對
    ===================================================  =========================
    `test_the_page_never_reaches_into_the_data_layer`      取第一段 ＋ **帶點邊界**的 `startswith`
    `test_the_service_allowlist_is_not_a_dead_letter`      **精確 `in` 集合成員**（多吐在這裡是承重的）
    `test_the_page_does_not_render_cache_or_backoff_state`  `in` 子字串 ＋ `endswith`
    ===================================================  =========================

    ⚠️ **「帶點邊界的 `startswith`」現在住在第一個消費者裡**，不是住在那支被刪掉的。
    **(2)「多吐無害」是假的**：稽核逐案實測，多吐**確實會產生偽陽性** ——
    `from ui import tab_manage_v2` / `from ui import tab6_manual_helpers`
    （`startswith` **沒有點邊界**）、
    `from ui.helpers.render_state import backoff_free_note`（子字串命中 `backoff`）
    —— **三者在新版都會誤紅，舊版不會**。
    ⚠️ **今天沒有一處真的誤紅**（本檔實際 import 只有 `__future__` / `typing` /
    `streamlit` / `ui.helpers.*`），所以這不是 bug；**但那句自陳必須改成誠實版**：
    **三個消費者；多吐會產生偽陽性，只是目前沒有觸發。**
    （~~`startswith` 那一處已於同輪補上點邊界~~ → **2026-09-06 更正**：那一處指的是
    已被刪除的 `..._does_not_delegate_to_the_old_tabs`；**點邊界今天在
    `test_the_page_never_reaches_into_the_data_layer` 裡**，見上表。
    子字串那一處**仍然沒有**修 —— 見該條註記。）
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

    ⚠️ **2026-09-07 順序變更（有意識的政策變更，不是漏刪 · 決策者：客戶）**
    -------------------------------------------------------------------
    舊順序 ~~`(BLOCK_HEALTH, nav_status_label(), BLOCK_KEYS, nav_manual_label(),
    maintain_label(), BLOCK_MANUAL)`~~ —— `maintain_label()` 原本夾在
    「手動補資料」與「使用手冊」之間。

    客戶 2026-09-07 逐字裁決：「🗄️ 資料維護與通報 決策【**保留**】在 ⑤ 的**最底部**
    作為**進階折疊區（`st.expander`）**。理由：系統維護與通報屬管理設定範疇，
    折疊收攏即可，不影響主視覺。」→ 移到 tuple 末端。

    **舊順序的理由仍然成立**（它跟著「從哪裡搬來」的檔案順序走，且不動線框五塊的相對序）；
    **被權衡掉的是它的視覺成本** —— 那一塊展開後很長，夾在中間會把使用手冊推到很下面。

    ⛔ **這次只動 `maintain_label()` 一格的位置。**
       線框五塊彼此的相對順序（健康度 → NAV → 金鑰 → 手動補資料 → 使用手冊）**一格未動**，
       :func:`test_all_blocks_are_present_and_in_wireframe_order` 仍然在守它。
    ⛔ **區塊數仍然是 6，一塊都沒有被刪掉** ——
       :func:`test_each_block_heading_is_drawn_exactly_once` 的雙向斷言（0 次／2 次都紅）
       與 :func:`test_the_page_renders_in_every_session_shape` 的「六塊一個都不少」
       **一個字未改**，它們會繼續抓「搬一搬結果搬丟了」。
    """
    return (BLOCK_HEALTH, nav_status_label(), BLOCK_KEYS,
            nav_manual_label(), BLOCK_MANUAL, maintain_label())


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

    ⚠️ **2026-09-08 就地更正：本函式的名字自本日起比它的內容大（有意識的更正，不是漏刪）。**
    本頁新增了 **🧾 ① 結論層**，那也是「被測檔自己畫的內容」——
    但它排在第一個 `### ` 區塊**之前**，:func:`_units` / :func:`_segments`
    **結構上看不到它**，所以本函式**回傳值裡沒有它**。
    ⛔ **本輪刻意不把它加進來，理由是「不要靜靜擴大一個既有 helper 的語意」**：
       本函式今天在檔內**只被一段註解引用**（`git grep` 實測：定義 1 處、註解 1 處、
       0 個真正的呼叫端），把結論層塞進來不會讓任何一條規則變強，
       只會讓下一個人以為「用它就掃得到全部自畫內容」。
    ✅ **結論層由專屬的 :func:`_conclusion_parts` ＋ 該節四條守衛涵蓋**
       （`test_no_conclusion_word_appears_in_the_conclusion_layer` /
        `test_the_verdict_names_the_only_switch_it_can_see` /
        `test_the_conclusion_says_it_does_not_know_instead_of_guessing` /
        `test_every_conclusion_card_points_at_a_block_that_is_really_on_screen`）。
    ⛔ **要拿本函式當「本頁自畫內容的全集」之前，先把結論層加進來並跑一次突變。**
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
    """線框 Tab 05 由上而下：健康度 → NAV → 金鑰 → 手動補資料 → 使用手冊 →（維護）。

    ⚠️ 「🗄️ 資料維護與通報」**不是線框的區塊** —— 線框只在「從哪裡搬來」列了
    `ui/tab_manage.py`，五個 `<h4>` 裡沒有它。被測檔就地登記為 (D-5) 的偏離，
    本條把那個**現況**釘住：哪天客戶／總管裁決它該搬走或該併進別塊，這條會轉紅。

    ⚠️ **2026-09-07 就地更正（有意識的政策變更，不是漏刪 · 決策者：客戶）**：
       本行原寫 ~~「…手動補資料 →（維護）→ 使用手冊」~~ ——
       客戶同日裁決把（維護）移到**最底部**當折疊區，故改為
       「…手動補資料 → 使用手冊 →（維護）」。
       ⛔ **這一條的用意一字未變**：它釘的是「六塊都在、而且照這個順序」；
          它**不是**在替（維護）背書一個線框位置 —— (D-5) 的偏離登記照舊有效。
       ⛔ **線框五塊彼此的相對順序一格未動**，本次只搬了那個「線框沒有給位置」的第六塊。
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


# ══════════════════════════════════════════════════════════════════
# 客戶 2026-09-07 裁決：🗄️ 資料維護與通報 ＝ 最底部的進階折疊區
# ══════════════════════════════════════════════════════════════════

def test_the_maintain_block_is_the_last_thing_on_the_page():
    """⭐ 客戶 2026-09-07 裁決的**位置**那一半：那一塊必須排在**最底部**。

    客戶逐字：「決策【**保留**】在 ⑤ 的**最底部**作為**進階折疊區（`st.expander`）**。」

    ⚠️ **本條與 :func:`test_all_blocks_are_present_and_in_wireframe_order` 不重複**：
    那一條驗的是「六塊都在、而且照 :func:`_block_order` 的順序」——
    也就是說，**有人把 `_block_order()` 一起改掉，那一條就會跟著綠**。
    本條**不讀 `_block_order()`**，它直接釘「**最後一塊必須是維護**」這個
    客戶裁決的字面，所以改 `_block_order()` 繞不過它。

    ⛔ **這正是本 repo 反覆記載的那個病**：把守衛跟著被測物一起改，紅燈就消失了。
       兩條的判準必須來自**不同的地方**，否則第二條只是第一條的影子。
    """
    _got = [_n for _n, _ in _units(_stream("loaded"))]
    assert _got, "整頁一個區塊都沒認出來 —— 本條失去對象（fail-closed）。"
    assert _got[-1] == maintain_label(), (
        f"⑤ 的最後一塊是「{_got[-1]}」，客戶 2026-09-07 裁決要求是「{maintain_label()}」。\n"
        f"實際渲染順序：{_got}\n"
        "⚠️ 若這是一次有意的改版，請先回去看客戶那句裁決 —— 它是 UI 決定，不是實作細節。")


def test_the_maintain_block_is_folded_and_collapsed_by_default():
    """⭐ 客戶 2026-09-07 裁決的**包裝**那一半：`st.expander`、而且**預設收合**。

    **靜態 ＋ 行為兩邊都驗，因為它們各自有守不到的東西**：

    - **靜態（AST）** 驗得到 `expanded=False` —— 行為面驗不到（:func:`_flat`
      只記 expander 的**標籤**，不記它展開沒有）。
    - **行為（AppTest）** 驗得到「委派的內容**真的**落在那個 expander 底下」——
      靜態只看得到 `with` 寫在原始碼裡，看不到 `render_manage_tab()`
      是不是被寫在 `with` **外面**（那正是本檔 sentinel 那條記載過的形狀）。

    ⛔ **`expanded=False` 不准省略也不准寫成別的**：`st.expander` 的預設值本來就是
       `False`，所以「省略」在今天等價 —— 但客戶要的是**明示**的收合，
       而預設值是 Streamlit 的、不是我們的。fail-closed：省略即紅。
    """
    # ── (1) 靜態：`_render_maintain` 用 `st.expander(..., expanded=False)` 包住委派 ──
    _fn = next((_n for _n in ast.walk(_tree())
                if isinstance(_n, ast.FunctionDef) and _n.name == "_render_maintain"), None)
    assert _fn is not None, "被測檔裡找不到 `_render_maintain` —— 斷言失去對象（fail-closed）。"

    _folds = [_w for _w in ast.walk(_fn) if isinstance(_w, ast.With)
              for _it in _w.items
              if isinstance(_it.context_expr, ast.Call)
              and isinstance(_it.context_expr.func, ast.Attribute)
              and _it.context_expr.func.attr == "expander"
              and isinstance(_it.context_expr.func.value, ast.Name)
              and _it.context_expr.func.value.id == "st"]
    assert len(_folds) == 1, (
        f"`_render_maintain` 裡的 `st.expander(...)` 有 {len(_folds)} 個（應為 1 個）。\n"
        "客戶 2026-09-07 裁決：這一塊收成**一個**進階折疊區。")

    _call = next(_it.context_expr for _it in _folds[0].items
                 if isinstance(_it.context_expr, ast.Call))
    _kw = {_k.arg: _k.value for _k in _call.keywords}
    assert "expanded" in _kw, (
        "`st.expander(...)` 沒有明寫 `expanded=` —— 客戶要的是**明示收合**。\n"
        "⚠️ Streamlit 的預設值今天剛好也是 False，但那是**它的**預設值，不是我們的決定。")
    assert isinstance(_kw["expanded"], ast.Constant) and _kw["expanded"].value is False, (
        f"`expanded=` 不是字面的 False，而是 {ast.unparse(_kw['expanded'])} —— "
        "fail-closed 視為沒有收合。")

    # 委派呼叫必須真的落在那個 `with` 裡面（不是寫在外面）。
    _inside = {ast.unparse(_n.func) for _n in ast.walk(_folds[0])
               if isinstance(_n, ast.Call)}
    assert "render_manage_tab" in _inside, (
        "`render_manage_tab()` 不在那個 `st.expander` 的 `with` 裡面 —— "
        "折疊區會是空的，而委派的內容會落在折疊區外面。")

    # ── (2) 行為：那一塊的第一個元素就是標籤正確的 expander ──
    _seg = _segments(_stream("loaded")).get(maintain_label())
    assert _seg, (
        f"渲染流裡找不到「{maintain_label()}」那一塊 —— 本條失去對象（fail-closed）。")
    _first = _seg[0]
    assert _first == f"[Expander] {maintain_label()}", (
        f"「{maintain_label()}」那一塊的第一個元素是 {_first!r}，\n"
        f"應為 [Expander] {maintain_label()} —— 也就是內容**沒有**被收進折疊區。\n"
        "⚠️ `safe_section()` 本身不畫任何東西，所以這一格就是委派內容的第一個元素。")


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
    - 新頁多了什麼（`新 - 舊`）→ 紅，那代表新頁自己長出了舊 ⑤ 沒有的**委派**，
      **應該先問「那一塊是不是該進 (A) 路線的委派清單」**。

    ⛔ **2026-09-06 就地更正：「一律紅」不成立（有意識的更正，不是漏刪）。**
    舊表述：~~「新頁多了什麼（`新 - 舊`）→ **一律紅**」~~ —— **本組已重現，不是轉述**。
    :func:`_entries` 的過濾器**只認三種前綴**（`ui.tab*` / `ui.helpers.settings_diag*` /
    `ui.helpers.data_registry`，且排除 `merge_context`），**其餘一個字都看不到**。

    **突變實測（本組自己跑，AST，非字面 grep；附正對照）**：
    在新頁加上三支 Google Sheets 寫入入口 ——
    `repositories.pool_repository.PoolRepo` / `services.macro.weights_store.save_weights` /
    `repositories.snapshot_repository.save_holdings_overview` ——
    `_gained` 仍是 **`[]`**，本條 **GREEN、突變存活**。
    （**正對照**：改加一支 `from ui.tab_manage import _AUDIT_PROBE`，`_gained` 立刻非空 ——
    證明過濾器不是壞掉，是**射程本來就窄**。）

    ✅ **整體沒有破口，破的只有這一條的自我描述**：那三支會被
    :func:`test_the_page_never_reaches_into_the_data_layer` 接住（`repositories` 是
    banned root、`services.macro.*` 不在白名單）。
    ⛔ **但「一律」這兩個字必須拿掉** —— 本條被 commit `7e5677a` 當賣點寫進訊息，
    ②③④ 照抄就是四份假記錄。**本條真正的承諾是：新頁不得長出舊 ⑤ 沒有的
    「委派類」依賴**（那三種前綴之內），不是「任何新依賴」。

    ⚠️ **同一件事的另一個面向：「`新 − 舊` ＝ 空」也只在這個窄過濾器下為真。**
    **本組實測（量測日 2026-09-06，改用「全部 import 符號、不過濾」重算）**：
    `新 − 舊` ＝ **7**（`datetime` / `typing.Any` 兩個 stdlib ＋ 下列 5 個）——

    - `services.nav_history_gs.coverage_status`
    - `services.nav_history_gs.status`
    - `ui.helpers.ia.empty_state.empty_state`
    - `ui.helpers.story_nav.section_label`
    - `ui.helpers.story_nav.where_to_find`

    `舊 − 新` ＝ **1**（就是 `render_nav_status_section`）。
    → **扣掉 stdlib 就是 5 個，其中 `services.nav_history_gs` 佔 2 個** ——
    那 2 個正是總管裁決 2「NAV 那一塊自己實作」必然帶進來的取數入口，
    **不是偷加的依賴**（它們另有 :func:`test_the_page_never_reaches_into_the_data_layer`
    的白名單 ＋ 2026-09-06 新增的寫入面黑名單在守）。
    ⛔ **引用「`新 − 舊` ＝ 空」時務必附上射程限定**，否則那句話會被讀成
    「新頁沒有任何新依賴」—— **那是假的**。

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
        # ⚠️ **把 gate 直接換成「回 True」，不是塞 session_state** —— bare 模式下
        #    `st.checkbox(..., key=…)` 不讀 session 的既有值，一律回預設 `False`
        #    （同 :func:`test_the_diag_gate_really_gates_the_registry_update` 的登記）。
        #    本條驗的是**旗標的作用域**，不是 gate 本身，所以直接跳過 gate 是對的切法。
        # ⚠️ **2026-09-07：`_render_maintain()` 移到這一行之下。有意識的變更，不是漏改。**
        #    （決策者：AI 總管，雙軌並行裁決 2）
        #    **舊寫法**（原地保留、加刪除線，不刪）::
        #
        #        ~~_mod._render_maintain()~~          # ← 在 patch 之前，那時它沒有 gate
        #        ~~_st.checkbox = lambda *_a, **_k: True~~
        #        ~~_mod._render_source_health()~~
        #
        #    **舊寫法的理由一個字都沒有被推翻**，斷言也一個字都沒改 —— 本條驗的仍然是
        #    「呼叫 `render_manage_tab()` 的那一刻 `NAV_HISTORY` 在不在手上」。
        #    **被權衡掉的是它的一個前提：「維護區沒有 gate，直接呼叫就會委派」。**
        #    雙軌並行之後維護區也有 gate 了（舊 ⑤ 同時在跑同一支 `render_manage_tab()`，
        #    不 gate 會撞重複 widget key），不跳過 gate 就**根本走不到被測的那一行**，
        #    `_seen["manage"]` 會整個不存在 —— 那不是守衛抓到東西，是**守衛失去對象**。
        #    ⛔ 這是把兩個 gated 區塊**一視同仁**，不是放寬：`_render_source_health()`
        #       從一開始就是這樣處理的，本行只是讓 `_render_maintain()` 跟它一致。
        _st.checkbox = lambda *_a, **_k: True                # type: ignore[assignment]
        _mod._render_maintain()
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
    """⭐ **委派區塊不准只是一句灰字。**（實際斷言 **3 塊**，逐塊具名於 `_want`）

    ⛔ 這一條取代了三條舊守衛（`test_the_form_block_is_not_grey` /
    `test_the_manual_is_static_text_not_a_grey_placeholder` /
    `test_the_manual_lists_exactly_the_wireframe_three`），而且**比它們強** ——
    舊的三條各守一塊、而且只驗「有沒有 ⬜」；本條驗**每一塊都有真的東西**。

    ⚠️ **判準是「這一塊裡有沒有 widget 或多於一行的內容」**，不是比對特定字串 ——
    比對字串等於把被委派模組的文案抄一份進來（第二份真相源，且必然漂移）。
    ⚠️ **2026-09-06 就地更正：本段的兩句話原本自相矛盾（有意識的更正，不是漏刪）。**
    舊標題寫 ~~「**四個**委派區塊」~~，舊引言寫 ~~「「連線與金鑰」與「使用手冊」
    **不在**本條射程內」~~ —— 而它**自己的下一個 bullet** 就寫著使用手冊「**在**射程內」，
    程式碼 `_want` 也把 `BLOCK_MANUAL` 收了進去。**三者互相打架，以程式碼為準。**
    **據實的版本**：委派區塊共 **5** 塊（健康度／金鑰／手動補資料／維護／使用手冊），
    **本條斷言其中 3 塊**，**2 塊在射程外**，理由逐一寫明：
    - **資料來源健康度**：它整塊在 Checkbox Gate 之後，而 :func:`_stream` 三種形狀
      **gate 都沒勾** —— 這時它**本來就該是灰態**（那正是
      :func:`test_both_gates_are_grey_and_point_at_themselves` 在守的事）。
    - **連線與金鑰**：兩個承接對象在測試環境**本來就會是灰態**
      （沒有 OAuth token → 保單橋接灰；沒有抓取紀錄 → 抓取診斷灰）。
      那是**真實狀態**，不是佔位。
    - **使用手冊**：它收在 `st.expander` 裡，AppTest 仍會渲染其內容，
      故它**在**射程內（見下方 `_want`）。

    ⚠️ **2026-09-07 就地更正：使用手冊那一列現在是「形式通過」，不是「內容通過」**
    （**有意識的更正，不是漏刪** · 日期 **2026-09-07** · 決策者：**AI 總管**）。
    雙軌並行（#814）之後 `_render_manual` **加了 Checkbox Gate**（理由見被測檔該函式：
    舊 ⑤ 也無條件畫同一份說明書，兩份一起畫會撞 `render_indicator_map` 那張**不帶 key**
    的 `plotly_chart`，使用者**零點擊**就會看到紅字）。
    → gate 沒勾時，`BLOCK_MANUAL` 那一段裡的 `[Expander]` 與 `[Checkbox]`
    **本身就滿足下方的 `_widgets` 判準** —— 也就是說，**這一列現在即使委派被整個
    拿掉也照樣綠**。
    ⛔ **據實寫出來，不假裝它還守著原本那件事。** 真正在守「委派沒有被拿掉」的是
    `tests/test_wf05_settings_golive.py::test_the_dual_track_delegations_stay_behind_a_checkbox_gate`
    的斷言 (1)（2026-09-07 已把 `_render_manual` / `_render_keys` 加進 `_MUST_BE_GATED`）。
    **覆蓋沒有消失，是換了地方**；本行的作用是讓下一個人知道該去哪裡看。
    ⚠️ 另兩列（手動補資料 / 維護區）**本來就已經在 gate 之後**，狀況與本列相同，
    只是那兩顆 gate 更早加、當時沒有人把這件事寫下來。
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
    """⭐ `coverage_status()` 拋例外 → **只有 NAV 那一塊變紅框**，其餘照常。

    ⚠️ **2026-09-06 就地更正（有意識的更正，不是漏刪）**：標題原寫
    ~~「另外**兩張**照常」~~ —— 本條實際逐一斷言 **4 個區塊**還在
    （資料來源健康度／連線與金鑰／手動補資料／使用手冊，見下方 for 迴圈），
    整頁則有 **6** 個區塊。「兩張」是骨架時代「狀態三卡」留下的字，**與程式碼不符**。
    ⚠️ 順帶登記本條**沒有**斷言的那一塊：**🗄️ 資料維護與通報**
    （它不在那個迴圈裡）。**登記，不是沒看到。**

    ⚠️ **這不是假想的失敗路徑**：`services/nav_history_gs.py::load_points` 在
    **來源冷卻期內**（前一次失敗登記了 cooldown）與**真 I/O 失敗**時
    都會拋 `NavHistoryError` —— 那是 L2 刻意的 §1 行為（回 `[]` 會與
    「這檔真的還沒累積」同義），**不是 bug，是這一塊的正常路徑之一**。

    ⛔ **少了每一塊各自那一層 `safe_section()`，整頁會被一個紅框吃掉一片** ——
    「資料來源健康度」與「連線與金鑰」明明沒壞，卻跟著消失。

    ⚠️ **2026-09-06 就地更正（有意識的更正，不是漏刪）**：上句原寫
    ~~「少了 `_render_grid()` 裡那一層 `safe_section()`，外層那個
    `safe_section("狀態三卡", _render_grid)` 會把三張卡一起換成一個紅框」~~ ——
    **`_render_grid` 與 `"狀態三卡"` 在本 PR 的被測檔裡都已經不存在**
    （實測：`origin/main` 的 `ui/views/page_05_settings.py` 各有命中，本分支 **0 命中**；
    `_render_grid` 這個名字**全 repo 也已經沒有任何定義**，AST 掃 649 個 `.py` 檔為 0）。委派殼改成
    **六個區塊各自一次 `safe_section(區塊名, 區塊函式)`**，不再有那層外殼。
    **這條守衛要守的性質完全沒變**（區塊之間互相隔離），變的只是它引用的實作長相。
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
    `[Metric] 標籤`、**不是** `[Markdown] ### 標題` —— :func:`_units` 的開頭判準
    認不出它。
    ⚠️ **2026-09-06 就地更正（有意識的更正，不是漏刪）**：本行原寫
    ~~「`[Markdown] **標題**` —— :func:`_units` 的 `_CARD_OPEN`」~~ ——
    **`_CARD_OPEN` 在本檔已經不存在**（本檔：`origin/main` 3 處命中 → 現在 0 處定義）。
    ⚠️ **它不是全 repo 消失** —— `tests/test_wf03_research_skeleton.py` /
    `tests/test_wf04_portfolio_skeleton.py` **各自有一份同名的**（③④ 的，與本檔無關）。
    委派化之後 :func:`_units` 改認 :data:`_H3_OPEN`（`### ` 開頭 ＋ 六個具名區塊）。
    **本條要守的性質一字未變**（那一塊在四種狀態下都必須是一個單位）。若這一塊照抄別頁用 `state_card` 畫「有資料」的狀態，
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
    """⭐⭐ 任何一則「有數字＋有時間單位」的字，都必須同行帶點數。
    **射程：NAV 累積狀態那一塊**（不是整頁 —— 理由與更正見下）。

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

    ⛔ **2026-09-06 就地更正：本段與程式碼相反（有意識的更正，不是漏刪）。**
    舊表述：~~「本條是【整頁】的，不是 unit-scoped …… 本條掃 `_flat()` 的全部元素，
    **含頁首**。」~~ —— **實際的迴圈是 `_duration_bearing_parts(_nav_parts(_parts))`**，
    也就是**只掃 NAV 累積狀態那一塊**，下面第二行的 ⛔ 註解自己就寫著「**縮到 NAV 區塊**」。
    **兩句話在同一個 docstring 裡互相打架，而下面那一句才是真的。**
    ⚠️ **這句一旦被當真，後果不是小事**：它會讓人以為頁首與其他五塊也被守著，
    於是**在那些地方印一個裸跨度不會有人擋** —— 本節整篇正是在防這種「以為有人看著」。
    **縮小射程是委派化的刻意取捨**（全頁掃會掃到 `ui/tab6_manual.py` 的教學文「約 5.5 年」，
    那不是本頁寫的），**代價就地寫明**：頁首與其他五塊的裸跨度，本條看不到。
    ⚠️ 順帶更正舊表述裡的另一個過期事實：~~`_units()` 只認 `####`~~ ——
    委派化之後它認的是 **`### ` ＋ 六個具名區塊**（:data:`_H3_OPEN`）。
    「頁首落在 unit-scoped 守衛射程外」這個結論**不變**（:func:`_units` 仍會丟掉
    第一個區塊標題之前的全部文字），變的只是那個判準的長相。

    ⚠️ **本條守不到的（照實列）**：
    - :data:`_DURATION_RE` 的單位字是白名單 —— 「個月」以外的寫法、英文 `years`，
      都抓不到。（⚠️ **2026-09-06 就地更正**：本行原寫 ~~`:data:`_DURATION_UNITS``~~，
      **本檔沒有這個名字**；另原寫 ~~「全形數字」抓不到~~ 也是假的 ——
      該 regex 的字元類寫著 `[0-9０-９]`，**全形數字是抓得到的**。）
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
      **綠**。`## ` 不是區塊開頭（:data:`_H3_OPEN` 只認 `### ` ＋ 六個具名區塊），
      所以第一個 opener 是「**資料來源健康度**」那一塊；
      :func:`_units` 會**丟掉第一個 opener 之前的所有文字**。
      ⚠️ **2026-09-06 就地更正（有意識的更正，不是漏刪）**：本行原寫
      ~~「`## ` 不是 `_L4_OPEN`（它只認 `####`）」~~ —— **`_L4_OPEN` 在本檔
      已經不存在**（本檔：`origin/main` 4 處命中 → 現在 0 處定義；
      **③④ 的守衛檔裡各有一份同名的，那不是本檔的**），委派化之後換成
      :data:`_H3_OPEN`。**結論一字未變**（頁首確實在射程外），變的只是判準的名字。
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

#: ⛔ **2026-09-06 新增：白名單降到【符號粒度】，寫入面明文排除。**
#:
#: **為什麼要有這一層（本組已重現，不是轉述）**：上面那份白名單是**模組粒度**，
#: 而 `services.nav_history_gs` **同時裝著讀取面與寫入面**
#: （`__all__` 實測：`append_point` / `append_points` / `import_csv_text` 是寫入，
#: `load_points` / `load_series` / `coverage_status` / `status` / `is_enabled` 是讀取）。
#: **突變實測**：在被測檔加 `from services.nav_history_gs import append_points`
#: （以及 `append_point` / `import_csv_text`）→ 上面那條 **三顆全部 GREEN、存活**。
#: **正對照**：同一條規則對 `import gspread` 立刻轉紅 —— 規則沒壞，是粒度不夠細。
#:
#: ⚠️ **讀取面刻意保留放行，理由是實測出來的、不是推定的**：
#: `load_points()` 走 **`sh.worksheet(...)` 直取**，**不經**那支會
#: `add_worksheet(...)` ＋ `ws.update("A1", …)` 補 header 的 `_get_worksheet()`
#: （AST 實測：`load_points` 的呼叫集合裡沒有 `_get_worksheet` / `add_worksheet` /
#: `update` / `append_rows`；`append_points` 則兩者都有）。
#: → **本頁的兩個入口（`coverage_status` / `status`）在唯讀原則下成立。**
#:
#: ⛔ **這是黑名單，不是白名單，所以它抓不到第 N+1 支新的寫入函式** ——
#: 上游哪天在 `services/nav_history_gs.py` 加一支新的寫入入口，本表**不會自己長大**。
#: 登記在此，**不是沒看到**。
_FORBIDDEN_SERVICE_SYMBOLS: frozenset = frozenset({
    "services.nav_history_gs.append_point",
    "services.nav_history_gs.append_points",
    "services.nav_history_gs.import_csv_text",
})

#: 上面那些符號的**裸名字**（給 call-site 比對用）。
#: ⚠️ 只驗 import 會漏掉 `import services.nav_history_gs` ＋
#: `services.nav_history_gs.append_points(...)` 這條路 —— 那條路的 import 是模組本身，
#: **在白名單上**。故 import 與呼叫**兩邊都看**。
_FORBIDDEN_SERVICE_LEAVES: frozenset = frozenset(
    _s.rsplit(".", 1)[-1] for _s in _FORBIDDEN_SERVICE_SYMBOLS)


def test_the_page_never_reaches_into_the_data_layer():
    """View 不得直接碰 L1／L0／HTTP；L2 只准 :data:`_ALLOWED_SERVICE_MODULES` 那一個。

    ⚠️ **`_imported_modules()` 對 `from X import Y` 會同時吐 `X` 與 `X.Y`**
    （見該函式 docstring），所以判定要**兩種形狀都認**：
    `services.nav_history_gs` 本身、以及 `services.nav_history_gs.<符號>`。
    ⛔ **點邊界不能省**：裸 `startswith` 會讓 `services.nav_history_gs_v2`
    這種**不同的模組**跟著被放行（~~同本檔 `..._does_not_delegate_to_the_old_tabs`
    2026-09-05 修過的那個洞~~ → **2026-09-06 就地更正，有意識的更正，不是漏刪**：
    那條守衛**已於本 PR 從本檔移除**（commit `7e5677a`），所以「同**本檔**……」
    這句指向一個**本檔已經沒有的東西**。
    ⚠️ 同名守衛在 `tests/test_wf03_research_skeleton.py` /
    `tests/test_wf04_portfolio_skeleton.py` **仍然存在**（③④ 的），
    **不要**把本更正讀成「那條守衛被全 repo 刪掉了」。
    **那個洞本身是真的、也真的修過**，只是它今天**就在本函式裡**
    —— 這一行原本在指的那個「別處」，現在是「這裡」）。
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

    # ⛔ **2026-09-06 新增的第二層：白名單模組【內部】的寫入面一律不准碰。**
    #    理由與實測見 :data:`_FORBIDDEN_SERVICE_SYMBOLS` 上方的登記。
    _writes = sorted(set(_imported_modules(_tree())) & _FORBIDDEN_SERVICE_SYMBOLS)
    for _n in ast.walk(_tree()):
        if (isinstance(_n, ast.Call)
                and _dotted(_n.func).rsplit(".", 1)[-1] in _FORBIDDEN_SERVICE_LEAVES):
            _writes.append(f"L{_n.lineno} {_dotted(_n.func)}(…)")
    assert not _writes, (
        f"被測檔碰了 nav_history 的**寫入面**：{sorted(set(_writes))}\n"
        "⛔ 本頁的 NAV 區塊是**唯讀**的（`_render_nav_status` 拿的是唯讀閘門豁免，"
        "見 `test_the_read_only_gate_really_is_read_only`）；三條真的寫入路徑一律"
        "委派給 `render_nav_manual_section()`，不由本頁自己呼叫。\n"
        f"讀取面（{sorted(set(_s.rsplit('.', 1)[-1] for _s in _FORBIDDEN_SERVICE_SYMBOLS))} "
        "以外的）照舊放行。")


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


# ══════════════════════════════════════════════════════════════════
# 🧾 ① 結論 ／ 🧾 ② 依據 兩層（2026-09-08，客戶拍板線框 §3）
# ══════════════════════════════════════════════════════════════════
#: 客戶 2026-09-08 逐字拍板的那份線框。**本節的字表唯一出處。**
#:
#: ⭐ **為什麼是讀那個檔，而不是在這裡手抄一份字串**：手抄的字表**跟著被測檔一起改**
#:    就會一起綠 —— 那正是本 repo 反覆記載的「守衛跟著被測物改，紅燈就消失了」。
#:    線框是**客戶簽核過的那一份**，它不會因為有人改了 `.py` 而跟著變。
#: ⛔ **代價據實寫**：這條連結只驗「字串在線框裡出現過」，
#:    **不驗**「它出現在對的位置」——線框把同一串字寫在別的段落也會通過。
#:    收窄成「⑦ 那一節之內」已經做了（見 :func:`_wireframe_p7`），
#:    再往下（哪一張圖、哪一行）本檔沒有做。
WIREFRAME = ROOT / "docs" / "wireframes" / "draft-four-page-content.html"

#: ⑦ 那一節的邊界。**兩個錨點都取自線框自己的 `<h2>`**。
_WF_P7_START = "<h2>3 · ⑦ ⚙️ 設定與診斷</h2>"
_WF_P7_END = "<h2>4 · ⑧ 🔍 標的探索</h2>"


def _squash(text: str) -> str:
    """去掉標記、空白與 ASCII-art 框線，只留「字」。

    ⚠️ **非做不可**：線框的 `<pre class="wf">` 把一句話**折成兩行**、
    每行前後包 `│` 與一堆對齊用的空白。直接 `in` 比對**一定 miss**，
    而 miss 會被讀成「這句話不是線框寫的」——那是一個假的紅燈。
    """
    _t = re.sub(r"<[^>]+>", "", text)
    _t = (_t.replace("&lt;", "<").replace("&gt;", ">")
            .replace("&amp;", "&").replace("&quot;", '"'))
    return "".join(_c for _c in _t
                   if not _c.isspace() and _c not in "│┌┐└┘├┤─")


#: ⑦ 那一節裡的 **ASCII 線框圖**（狀態 (1) 與狀態 (2) 兩張）。
_WF_PRE = re.compile(r'<pre class="wf">(.*?)</pre>', re.S)


@functools.lru_cache(maxsize=1)
def _wireframe_p7() -> str:
    """⑦ 那**兩張 ASCII 線框圖**的「只留字」版本。**不是整節。**

    ⛔⛔ **只取 `<pre class="wf">`，這一步是本條的全部力量所在 —— 讀完再改。**

    **本組第一版取的是整節，而它當場被自己的突變測試打穿**：
    把 :data:`DIAG_GATE_LABEL` 改回舊值 `"🔭 載入資料診斷"` →
    **本條照樣 GREEN、突變存活**。
    **根因**：⑦ 那一節的散文裡（「這一頁改了什麼」那個 `<li>`）**逐字引用了舊文案**
    ——「現況是「`🔭 載入資料診斷`」「`讀取雲端 NAV 累積狀態`」」。
    也就是說：**線框裡同時有「新的」和「它要取代的舊的」，
    整節比對會把「改回舊的」也判成合格。**

    **修法**：只取兩張 `<pre class="wf">` 線框圖 —— **那是客戶看到的畫面本身**，
    散文是它的說明。舊文案只出現在散文裡（實測：兩個舊值在 `<pre>` 內 **0 命中**）。

    ⚠️ **這一筆值得記的不是修法，是它怎麼被抓到的**：本條的 docstring 原本寫著
    「要騙過它得去改客戶簽核的那份線框」—— **那句話在寫下的當天是假的**，
    改一行 `.py` 就騙得過。**是突變測試抓到的，不是人讀出來的。**
    """
    _raw = WIREFRAME.read_text(encoding="utf-8")
    assert _WF_P7_START in _raw and _WF_P7_END in _raw, (
        f"線框 {WIREFRAME.name} 裡找不到 ⑦ 那一節的錨點 —— "
        "本節全部的字表比對都會失去對象（fail-closed）。\n"
        f"錨點：{_WF_P7_START!r} / {_WF_P7_END!r}")
    _sec = _raw[_raw.index(_WF_P7_START):_raw.index(_WF_P7_END)]
    _pres = _WF_PRE.findall(_sec)
    assert len(_pres) == 2, (
        f"⑦ 那一節的 ASCII 線框圖有 {len(_pres)} 張，應為 2 張"
        "（狀態 (1) 完全沒資料 ／ 狀態 (2) 有資料）——"
        "數量對不上代表錨點或線框結構變了，本節的字表比對會失去對象（fail-closed）。")
    return _squash("\n".join(_pres))


#: 線框自己畫的**狀態記號**，不是文案的一部分。
#:
#: ⚠️ **只有這兩個，而且是刻意手寫的** —— 它們是 ASCII 圖裡的 checkbox 與灰態方塊
#:    （見 §3 狀態 (1)：`☐ 🔭 查一次資料來源狀態`、`⬜ 還沒去查。…`）。
#:    畫面上那顆 checkbox 的**標籤**不含 `☐`（那是 Streamlit 自己畫的），
#:    灰態本文也不含 `⬜`（那是 `render_state.not_ready()` 加的，＝ :data:`NOT_READY_MARK`）。
#: ⛔ **不要往這裡加東西來讓某個字串通過** —— 每多一個記號，
#:    「整行」的邊界就往右移一格，:func:`_wf_line_runs` 的完整性就鬆一格。
_WF_LINE_MARKERS: tuple[str, ...] = ("☐", NOT_READY_MARK)


@functools.lru_cache(maxsize=1)
def _wf_line_runs() -> frozenset[str]:
    """⑦ 那兩張線框圖裡，**每一段「整行、或連續數整行」的可能組合**（squash 後）。

    ⭐⭐ **本函式是 2026-09-09 第三輪回修的核心，讀完再改。**

    **它解的問題**：:func:`_wireframe_p7` 回的是一整塊**沒有邊界**的字，
    而原本的判準是 `_squash(值) in _wireframe_p7()` —— **`in` 是子字串比對，
    任何截斷仍然是子字串**。實測（本組自己重量，不是轉述）：

    ==================================  ======  ================================
    值                                   `in`?   說明
    ==================================  ======  ================================
    ``"🔭 查一次資料來源狀態"``            True    正確
    ``"🔭 查一次資料"``                   True    **被截短了，照樣通過**
    ``"### 🧾 ① 結論 — 現在能不能…"``      True    正確
    ``"### 🧾 ① 結論"``                  True    **被截短了，照樣通過**
    ``"🔭 載入資料診斷"``（舊值）          False   正確擋下
    ==================================  ======  ================================

    ⇒ **舊判準擋得住「換成別的字」，擋不住「把字剪短」。**
    而剪短同樣是在改**客戶親自拍板的畫面文案**，同樣不該單方面發生在 `.py` 裡。

    **修法＝把「有沒有出現過」換成「是不是一整行」（正向完整性要求）**：
    線框的每一個 UI 字串都**佔滿它自己那一行**（標題、閘門標籤各一行；
    兩句灰態各折成兩行）。所以合法的值 ＝ **一行、或連續數行的接合**，
    而「剪短」必然停在某一行的中間 ⇒ 不會等於任何一種組合。

    ⚠️ **為什麼不能改用「邊界字元」判斷（本組試過，會漏）**：
       `_squash` 連空白一起吃掉，而 ``### 🧾 ① 結論 — 現在…`` 的 ``結論`` 後面
       **本來就是一個空白**，所以「後面必須接邊界」對這一顆**判不出來**。
       **行才是硬邊界，空白不是。**

    ⚠️ **代價，照實寫**：本函式產生 O(n²) 個組合（兩張圖各約 30 / 20 行 ⇒ 數百個字串）。
       量很小，但它的意思是「**接得起來的都算合法**」—— 也就是說，
       **把兩個不相鄰的整行接起來**這種值本函式擋不到（它只保證「整行」，
       不保證「是同一段話」）。**擋得到的是截斷，擋不到的是重組。**
    """
    _runs: set[str] = set()
    for _pre in _WF_PRE.findall(
            _raw_p7()[_raw_p7().index(_WF_P7_START):_raw_p7().index(_WF_P7_END)]):
        _lines = [_l for _l in (_squash(_ln) for _ln in _pre.splitlines()) if _l]
        for _i in range(len(_lines)):
            # ⚠️ **記號只在起頭那一行剝**：`☐ 🔭 查一次…` 的 `☐` 是線框畫的框，
            #    畫面上那顆 checkbox 的標籤不含它。
            _first = _lines[_i]
            _heads = {_first}
            for _mk in _WF_LINE_MARKERS:
                if _first.startswith(_mk):
                    _heads.add(_first[len(_mk):])
            for _head in _heads:
                _acc = _head
                _runs.add(_acc)
                for _j in range(_i + 1, len(_lines)):
                    _acc += _lines[_j]
                    _runs.add(_acc)
    return frozenset(_runs)


@functools.lru_cache(maxsize=1)
def _raw_p7() -> str:
    """線框原始碼。**單獨拉出來只是為了讓 :func:`_wf_line_runs` 不必再讀一次檔。**"""
    return WIREFRAME.read_text(encoding="utf-8")


#: 本批**逐字**照抄線框的六個字串（兩個標題 ＋ 兩顆閘門標籤 ＋ 兩句灰態）。
#: ⚠️ 值一律 **import 自被測檔**，不在這裡抄第二份。
_VERBATIM_FROM_WIREFRAME: tuple[tuple[str, str], ...] = (
    ("結論層標題", CONCLUSION_HEADING),
    ("依據層標題", EVIDENCE_HEADING),
    ("資料來源健康度 gate 標籤", DIAG_GATE_LABEL),
    ("NAV gate 標籤", NAV_GATE_LABEL),
    ("資料來源健康度 gate 灰態", _DIAG_NOT_LOADED_NOTE),
    ("NAV gate 灰態", _NOT_LOADED_NOTE),
)


@pytest.mark.parametrize("what,value", _VERBATIM_FROM_WIREFRAME,
                         ids=[_w for _w, _ in _VERBATIM_FROM_WIREFRAME])
def test_the_wireframe_verbatim_strings_really_come_from_the_wireframe(
        what: str, value: str):
    """⭐ 被測檔宣稱「線框逐字」的六個字串，**必須真的在客戶簽核的線框裡**。

    ⛔ **這是本節最重要的一條，因為它是唯一一條判準不在 repo 程式碼裡的守衛。**
    其餘每一條都可以靠「改被測檔 ＋ 改守衛」一起變綠；本條不行 ——
    要騙過它得去改客戶簽核的那份線框，而那件事會出現在 diff 的最顯眼處。

    ⚠️⚠️ **上面那句話已經被推翻【兩次】，兩次都是同一句自我描述、不同的理由。
       兩次都原地保留，因為「一條守衛說自己騙不過」本身就是最該被懷疑的那種句子。**

    **第一次（2026-09-08，第一版）**：拿**整節**去比對，而該節的散文逐字引用了
       **要被取代的舊文案**，於是「把標籤改回舊值」這顆突變**存活**。
       修法：只取兩張 `<pre class="wf">` 線框圖（見 :func:`_wireframe_p7`）。

    **第二次（2026-09-09，第三輪獨立稽核）—— 上一輪修完之後，那句話【仍然】是假的**：
       判準是 ``_squash(value) in _wireframe_p7()``，而 **`in` 是子字串比對 ——
       任何【截斷】仍然是子字串**。稽核逐顆實跑、本組逐顆重跑：
       :data:`CONCLUSION_HEADING` 砍掉破折號後半、:data:`DIAG_GATE_LABEL` →
       ``"🔭 查一次資料"``、:data:`NAV_GATE_LABEL` → ``"讀一次雲端"``、
       :data:`EVIDENCE_HEADING` → ``"### 🧾 ② 依據"`` —— **四顆全部 150 passed 存活**，
       而正對照（改回舊值）RED。**改一行 `.py` 就騙得過，線框一個字都不用動。**
       修法：加上 :func:`_wf_line_runs` 的**整行完整性**要求（見本函式 (2)）。

    ⛔ **這兩次要一起讀，因為它們的共通點比各自的修法重要**：
       **第一次修完之後，沒有人回頭問「這句話現在為真了嗎」** ——
       上一輪就地寫下了「是突變測試抓到的，不是人讀出來的」這個教訓，
       卻**沒有替那句話再跑一次突變**。同一句自我描述，連續兩輪為假，
       第二次**沒有被揭露**（PR 與 commit 都照舊宣稱「要騙過它得去改線框」）。
       ⇒ **一條守衛的自我描述，跟它守的東西一樣需要突變驗證。**

    ⚠️ **雙向都擋得到嗎？照實寫：只擋一個方向。**
    - **擋得到**：有人把畫面文案改成線框沒有的字（含「改回舊文案」）→ 紅。
    - **擋不到**：線框裡還有**別的**該落地而沒落地的字（本條不列舉線框、只驗這六個）。
      那一半由 :func:`test_the_conclusion_and_evidence_headings_are_on_screen_in_order`
      與人工對照補，**不是由本條**。
    """
    # ── (1) 有沒有出現過 —— 擋「換成別的字」（含「改回舊文案」）────────────
    assert _squash(value) in _wireframe_p7(), (
        f"「{what}」的現行值不在客戶簽核的線框 ⑦ 那一節裡：\n  {value!r}\n"
        f"線框：{WIREFRAME}\n"
        "⛔ 這幾個字串是**客戶拍板的畫面文案**，不是實作細節 —— "
        "要改請先回去改線框（那是一次 UI 決定），不要單方面改 `.py`。")

    # ── (2) 是不是**一整行** —— 擋「把字剪短」（2026-09-09 第三輪回修新增）──
    # ⛔ 少了這一條，(1) 形同虛設：`in` 是子字串比對，**任何截斷仍然是子字串**。
    #    實測四顆截斷突變（標題砍後半／閘門標籤砍尾）在只有 (1) 時 **150 passed 全部存活**。
    assert _squash(value) in _wf_line_runs(), (
        f"「{what}」的現行值**出現在線框裡，但不是一整行**：\n  {value!r}\n"
        "⇒ 最可能的原因：**它被剪短了**（截斷後仍然是子字串，(1) 看不到）。\n"
        f"線框：{WIREFRAME}\n"
        "⛔ 剪短同樣是在改**客戶拍板的畫面文案**。要改請先回去改線框。\n"
        "⚠️ 若線框真的把這句話拆到不相鄰的兩處，那是線框結構變了 —— "
        "請一起改 `_wf_line_runs()`，並在 PR 裡講明為什麼（fail-closed）。")


def _conclusion_parts(parts: tuple[str, ...] | list[str]) -> list[str]:
    """結論層那一段的渲染紀錄（`### 🧾 ① 結論 …` 之後、`### 🧾 ② 依據 …` 之前）。

    ⚠️ **不能用 :func:`_units`** —— 它只認 :func:`_block_order` 那六個名字，
    而結論層排在第一個區塊**之前**，:func:`_units` 會把它整段丟掉
    （模組 docstring 已登記過這個射程：「頁首落在所有 unit-scoped 守衛的射程之外」）。
    **本 helper 就是補那個縫的。**
    """
    _out: list[str] = []
    _in = False
    for _p in parts:
        if _p == f"[Markdown] {CONCLUSION_HEADING}":
            _in = True
            continue
        if _p == f"[Markdown] {EVIDENCE_HEADING}":
            break
        if _in:
            _out.append(_p)
    return _out


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_conclusion_and_evidence_headings_are_on_screen_in_order(kind: str):
    """⭐ 線框 §1 的四層閱讀順序：**① 結論 → 卡 → ② 依據 → 五塊**。

    ⛔ **順序本身就是規格**（線框 §1 逐字：「把『你要知道的』和『憑什麼』分開，
       新手可以只讀上半、老手可以往下讀」）。把結論放到依據後面 ＝ 那句話白寫。

    ⚠️ **三種 session 形狀都驗** —— 結論層不得只在「有持倉」時才出現。
    """
    _parts = list(_stream(kind))
    _c = f"[Markdown] {CONCLUSION_HEADING}"
    _e = f"[Markdown] {EVIDENCE_HEADING}"
    assert _parts.count(_c) == 1, (
        f"（{kind}）結論層標題出現 {_parts.count(_c)} 次（應為 1）：\n{_c}")
    assert _parts.count(_e) == 1, (
        f"（{kind}）依據層標題出現 {_parts.count(_e)} 次（應為 1）：\n{_e}")
    _first_block = next(
        (_i for _i, _p in enumerate(_parts)
         if (_m := _H3_OPEN.match(_p)) and _m.group(1).strip() in set(_block_order())),
        None)
    assert _first_block is not None, "一個線框區塊標題都沒認出來（fail-closed）。"
    assert _parts.index(_c) < _parts.index(_e) < _first_block, (
        f"（{kind}）四層閱讀順序不對。\n"
        f"結論 @{_parts.index(_c)} / 依據 @{_parts.index(_e)} / 第一個區塊 @{_first_block}")


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_conclusion_says_it_does_not_know_instead_of_guessing(kind: str):
    """⭐⭐ **結論層一次都沒有量過東西，所以它畫出來的每一格都必須是灰的。**

    ⛔ **這是本節的 §1 那一條**：這一頁的職責是回答「資料可不可信」，
       而結論層排在所有 gate **之前** —— 它手上一個真數字都沒有。
       在這一格畫一個綠的 `st.metric` 或一句「都正常」，是這一頁最壞的一種謊
       （`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    **判準（兩個方向都要，少一個就能被繞過）**：
    - 結論層裡**每一則 Caption 都帶 ⬜**（`render_state.not_ready()` 的記號）；
    - 結論層裡**一個 `st.metric` 都沒有**（`ia.state_card` 的 `STATE_OK` 分支走它）。

    ⚠️ **擋不到什麼，照實寫**：`st.markdown("一切正常")` 這種**直接寫死的字**
       本條看不到（它只驗形態，不驗字）。字那一半由
       :func:`test_the_page_never_prints_the_illustrative_values_from_the_wireframe`
       （只擋線框那 7 個示意值）與 :func:`test_the_wireframe_verbatim_strings_...`
       （只擋那 6 個字串漂移）擋一部分 —— **合起來仍然不是「灰態不可能說謊了」。**
    """
    _body = _conclusion_parts(_stream(kind))
    assert _body, f"（{kind}）結論層底下一個元素都沒有 —— 本條失去對象（fail-closed）。"
    _captions = [_p for _p in _body if _p.startswith("[Caption]")]
    assert _captions, f"（{kind}）結論層一則說明都沒有：\n{_body}"
    _no_mark = [_p for _p in _captions if NOT_READY_MARK not in _p]
    assert not _no_mark, (
        f"（{kind}）結論層有 {len(_no_mark)} 則說明沒有灰態記號 {NOT_READY_MARK!r}：\n"
        + "\n".join(_no_mark)
        + "\n⛔ 結論層在所有 gate 之前，它一次都還沒量過東西 —— "
          "不灰就是在宣稱一個沒有量過的結論。")
    _metrics = [_p for _p in _body if _p.startswith("[Metric]")]
    assert not _metrics, (
        f"（{kind}）結論層畫了 {len(_metrics)} 個 `st.metric`：{_metrics}\n"
        "⛔ `st.metric` 是 `ia.state_card` 的 `STATE_OK` 分支 —— "
        "那是一張「一切正常」的卡，而我們一次都還沒查。")


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_every_conclusion_card_points_at_a_block_that_is_really_on_screen(kind: str):
    """⭐⭐ **死指路守衛**：三張卡的「去哪補」指的區塊，必須真的在畫面上。

    ⛔ **這一條只有真的把頁面跑起來才驗得到。** 靜態看 `_below(BLOCK_KEYS)`
       永遠是對的（那是一個合法的常數）；它會不會指到一個**畫面上不存在的區塊**，
       取決於那個區塊當下有沒有被畫出來 —— 而那是 runtime 的事。
       本 repo 的「指路指到不存在的東西」已發作三次，每一次都是這個形狀。

    ⚠️ **同時驗「指的是本頁，不是別頁」**：結論層那三張卡就長在這一頁最上面，
       對它們講「請先到 ⚙️ 設定與診斷」是一句**繞回原地**的指令
       —— 所以 :func:`_below` 產生的是「下方「X」」而不是 :func:`_where` 的分頁座標。
    """
    _parts = _stream(kind)
    _headings = {_m.group(1).strip() for _p in _parts if (_m := _H3_OPEN.match(_p))}
    _seg = _conclusion_parts(_parts)
    _body = _text(_seg)
    assert _body, f"（{kind}）結論層是空的（fail-closed）。"
    _cards = _conclusion_cards()
    assert len(_cards) == 3, f"結論層的卡片數是 {len(_cards)}，線框 §3 三張。"
    for _spec in _cards:
        _target = _spec["where"].removeprefix("下方「").removesuffix("」")
        assert _spec["where"] == _below(_target), (
            f"卡片「{_spec['title']}」的指路不是 `_below()` 產生的：{_spec['where']!r}\n"
            "⛔ 手抄的指路在本 repo 已經指錯三次。")
        assert _target in _headings, (
            f"（{kind}）卡片「{_spec['title']}」指向「{_target}」，"
            f"但畫面上沒有這個 `### ` 標題。\n畫面上的標題：{sorted(_headings)}\n"
            "⛔ 指到一個不存在的地方，比沒有指路更糟。")
        # ⛔⛔ **2026-09-09 第三輪回修：這一格原本可以被「兩張卡指同一個地方」互相頂替
        #    （有意識的更正，不是漏刪 · 決策者：AI 總管，依獨立稽核）。**
        #
        # **舊寫法**（原地保留、加刪除線，不刪）::
        #
        #     ~~assert _spec["where"] in _body~~
        #
        # `_body` 是**整個結論層**壓成的一塊字，而 🔭 卡與 🔑 卡的 `where`
        # **逐字相同**（兩張都是 `_below(BLOCK_HEALTH)`，本組實測：三張卡只有
        # **兩個相異的 `where` 值**）。⇒ 只要**其中一張**印出來，另一張就跟著過。
        # **實測**：把 🔭 卡改走 `business_alert`（它的 `where` 一個字都不印）
        # → 舊寫法**照樣通過**，被 🔑 卡那一份頂了過去。
        #
        # **修法＝逐卡驗**：找到這張卡自己的標題元素，它的**下一個**元素就是它的說明，
        # 指路必須印在**那一則**裡面。
        _title_at = next(
            (_i for _i, _p in enumerate(_seg) if _p == f"[Markdown] **{_spec['title']}**"),
            None)
        assert _title_at is not None, (
            f"（{kind}）畫面上找不到卡片「{_spec['title']}」的標題元素（fail-closed）。\n"
            + "\n".join(f"  {_p[:100]}" for _p in _seg))
        _own = _seg[_title_at + 1] if _title_at + 1 < len(_seg) else ""
        assert _own.startswith("[Caption]"), (
            f"（{kind}）卡片「{_spec['title']}」的標題後面不是它的說明，而是 {_own[:80]!r}。\n"
            "⛔ `state_card()` 的 `STATE_NOT_READY` 分支是「標題 ＋ 一則灰態說明」——"
            "少了說明代表這張卡換了分支（`business_alert` / `st.metric` 都不畫說明）。")
        assert _spec["where"] in _own, (
            f"（{kind}）卡片「{_spec['title']}」**自己那一則說明**沒有印出指路："
            f"{_spec['where']!r}\n實際：{_own}\n"
            "⛔ 不要拿整個結論層去比對 —— 兩張卡的指路可能逐字相同，"
            "一張沒印會被另一張頂過去（那正是本行修掉的東西）。")

    # ── 結論那一句本身的指路 —— **卡片以外，還有這一個，別漏掉** ──────────
    # ⚠️ 它指的**不是**一個 `### ` 區塊，而是**那一顆要按的 checkbox** ——
    #    所以「畫面上有沒有」要去 checkbox 的標籤裡找，不是去標題裡找。
    #    上面那個 for 迴圈**結構上看不到它**（它只走 `_conclusion_cards()`）。
    _labels = {_m.group(1) for _p in _parts
               if (_m := re.match(r"^\[Checkbox\] (.+)$", _p))}
    # ⚠️ **靠「順序」定位，不靠字串比對**：三張卡的指路長得跟它一模一樣
    #    （都是「請先到：下方「…」」），拿字串挑會一次挑到四則。
    #    結論那一句是**卡片網格之前**的第一則說明 —— 那是版面規格本身
    #    （線框 §1：一句結論 → 卡），所以拿它當判準是有出處的，不是巧合。
    _seg = _conclusion_parts(_parts)
    _grid = next((_i for _i, _p in enumerate(_seg) if _p.startswith("[Column]")),
                 len(_seg))
    _verdict = [_p for _p in _seg[:_grid] if _p.startswith("[Caption]")]
    assert len(_verdict) == 1, (
        f"（{kind}）卡片網格之前的說明有 {len(_verdict)} 則（線框 §1：一句結論）：\n"
        + "\n".join(_verdict))
    assert "請先到：下方「" in _verdict[0], (
        f"（{kind}）結論那一句沒有帶「去哪補」，或它指的不是本頁下面："
        f"\n{_verdict[0]}")
    _target = _verdict[0].split("請先到：下方「", 1)[1].split("」", 1)[0]
    assert _target in _labels | _headings, (
        f"（{kind}）結論那一句指向「{_target}」，"
        "但畫面上既沒有這個 `### ` 標題、也沒有這個 checkbox。\n"
        f"checkbox：{sorted(_labels)}\n標題：{sorted(_headings)}")


#: 結論層那三支函式。**AST 守衛的對象**。
_CONCLUSION_FUNCS: tuple[str, ...] = (
    "_render_conclusion", "_conclusion_cards", "_diag_gate_is_on")

#: 結論層**一個都不准呼叫**的名字（本頁僅有的兩支 L2 取數入口）。
_NO_READ_IN_CONCLUSION: frozenset = frozenset({
    "fetch_nav_backend_status", "fetch_nav_coverage",
    "coverage_status", "status", "get_secret",
})


def test_the_conclusion_layer_reads_nothing_at_all():
    """⭐⭐ **結論層零外部呼叫** —— 這是它能排在所有 gate 之前的**唯一**理由。

    ⛔ **為什麼要有一條【靜態】的，明明已經有一條【行為】的**
    （:func:`test_the_nav_block_is_grey_and_reads_nothing_before_the_gate` 數呼叫次數）：
    那一條**只在 gate 沒勾時**跑，而且它數的是被 patch 過的那兩個名字。
    有人在結論層裡 lazy-import 一支**第三個**取數入口（例如
    `from services.nav_history_gs import coverage_status`，繞過模組屬性），
    那一條的 `_calls` **不會動** —— 它 patch 的是 `page_05_settings.fetch_nav_coverage`，
    不是 service 端那一份。**本條看的是原始碼，繞不過那個縫。**

    ⚠️ **擋不到什麼**：`getattr(_mod, "fetch_nav_coverage")()` 這種動態取名。
       repo 既有性質（③ 已登記同型），**登記，不是沒看到**。
    """
    _tree_ = _tree()
    _fns = {_n.name: _n for _n in ast.walk(_tree_)
            if isinstance(_n, ast.FunctionDef) and _n.name in _CONCLUSION_FUNCS}
    _missing = sorted(set(_CONCLUSION_FUNCS) - set(_fns))
    assert not _missing, (
        f"結論層的函式不見了：{_missing} —— 本條失去對象（fail-closed）。\n"
        "⚠️ 若是刻意改名，請同時改 `_CONCLUSION_FUNCS`；**不要只刪這一條**。")
    _bad: list[str] = []
    for _name, _fn in _fns.items():
        for _n in ast.walk(_fn):
            if isinstance(_n, ast.Call):
                _leaf = _dotted(_n.func).rsplit(".", 1)[-1]
                if _leaf in _NO_READ_IN_CONCLUSION:
                    _bad.append(f"{_name} L{_n.lineno} {_dotted(_n.func)}(…)")
            if isinstance(_n, (ast.Import, ast.ImportFrom)):
                _bad.append(f"{_name} L{_n.lineno} 函式內 import")
    assert not _bad, (
        "結論層做了外部呼叫或 lazy import：\n  " + "\n  ".join(_bad) + "\n"
        "⛔ 結論層排在**所有 gate 之前**，它一動就等於「打開 ⑦ 就對外取數」——"
        "那正是兩顆 Checkbox Gate 存在的全部理由。\n"
        "⚠️ 若這是一次有意的取捨（例如要讓結論層畫出線框那句「有 N 項沒設定完」），"
        "請先讀被測檔模組 docstring 的 **(D-6)** —— 那是一個**待裁決**的問題，"
        "不是實作組自己決定的事。")


#: **進度語言**的字表 —— 線框 §0 推翻 1 要換掉的就是這種措辭。
#: ⚠️ **黑名單，抓不到第 N+1 種說法**（「初始化中」「準備中」…）。
_PROGRESS_WORDS: tuple[str, ...] = ("載入", "讀取", "尚未")


@pytest.mark.parametrize("what,value", (
    ("資料來源健康度 gate 標籤", DIAG_GATE_LABEL),
    ("NAV gate 標籤", NAV_GATE_LABEL),
    ("資料來源健康度 gate 灰態", _DIAG_NOT_LOADED_NOTE),
    ("NAV gate 灰態", _NOT_LOADED_NOTE),
), ids=["diag-label", "nav-label", "diag-note", "nav-note"])
def test_the_two_remaining_gates_stopped_talking_about_themselves(
        what: str, value: str):
    """⭐ 線框 §0 推翻 1：留下來的閘門要從**進度語言**換成**處境語言**。

    線框逐字：「現在的字在講『**為什麼系統不幫你做**』（進度語言），
    該換成『**這一項要花多久、你要不要現在花**』（處境語言）」。

    ⛔ **只管這兩顆。** 另外四顆是**雙軌鷹架**（線框 §0 推翻 1 的表），
       它們的文案講的正是「舊分頁已經在跑同一塊」——那是**真的原因**，不是進度語言，
       而且它們會在舊 ⑤ 下架那一批**整顆消失**。本條刻意不掃它們。

    ⚠️ **這是黑名單，弱**：它擋得住「改回舊文案」（舊值含「載入」／「讀取」／「尚未」），
       擋不住換一種新的進度講法。真正釘住文案的是
       :func:`test_the_wireframe_verbatim_strings_really_come_from_the_wireframe`。
       **兩條一起看才有意義：本條擋方向，那條擋字面。**
    """
    _hit = [_w for _w in _PROGRESS_WORDS if _w in value]
    assert not _hit, (
        f"「{what}」又開始講系統自己了：命中 {_hit}\n  {value!r}\n"
        "⛔ 線框 §0 推翻 1：「載入」是系統在講自己；使用者要知道的是"
        "「這一下要花我多久、不按會怎樣」。")


# ══════════════════════════════════════════════════════════════════
# 2026-09-08 回修：把內容型守衛的射程放大到結論層
# ══════════════════════════════════════════════════════════════════
# ⛔⛔ **這一節補的是本檔自己早就登記過的那個縫，而且是被它放走一顆真違規之後才補的。**
#
# 本檔模組 docstring 的「守不到」清單第 4 條逐字寫著：
#   「**頁首（`## 標題` ＋ `st.caption`）落在所有 unit-scoped 守衛的射程之外** ——
#     :func:`_units` 會丟掉第一個區塊標題之前的全部文字。**既有登記，本輪未修。**」
# 而 :func:`_nav_parts` 的長註記也寫著
#   「**哪天本頁又開始自己畫東西，這裡要一起放大**」。
# **2026-09-08 這一批就是那一天** —— 新增的結論層排在第一個 `### ` 之前，
# 於是 :func:`_units` 結構上看不到它，`_CONCLUSION_WORDS` 那份黑名單對它**完全不生效**。
#
# **獨立稽核的實證（本組已自行重現，附三道正對照）**：把 verdict 換成
#   「一切正常，全部來源都正常，你的資料可信」→ **132 passed、突變存活**
#   （三個詞逐字都在 :data:`_CONCLUSION_WORDS` 上）；
#   「可以信。今天每一個來源都抓到了，沒有一項缺設定。」→ **132 passed、突變存活**
#   （**這一顆連黑名單的邊都沒沾到** —— 它是本節第二條規則存在的理由）。
#
# ⛔ **修法是【放大射程】，不是【放寬條件】** —— 沒有動 :data:`_CONCLUSION_WORDS`
#    一個字、沒有加任何豁免、沒有調降任何下限。

@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_no_conclusion_word_appears_in_the_conclusion_layer(kind: str):
    """⭐ 把 :data:`_CONCLUSION_WORDS` 那份既有黑名單**放大到結論層**。

    ⛔ **這條與 :func:`test_no_grey_unit_states_a_conclusion` 用的是同一份字表，
       但掃的是不同的地方** —— 那一條掃 :func:`_units` 認得的六個區塊，
       而結論層排在第一個區塊之前，**它結構上看不到**。

    ⚠️ **它擋不到什麼，照實寫**：黑名單抓不到字表以外的第 N+1 種說法
    （稽核那第二顆突變「可以信。今天每一個來源都抓到了」**一個詞都沒命中**）。
    **那一半由 :func:`test_the_verdict_names_the_only_switch_it_can_see` 用
    「正向要求」擋，不是靠把黑名單愈加愈長。** 兩條要一起看。
    """
    _body = _text(_conclusion_parts(_stream(kind)))
    assert _body, f"（{kind}）結論層是空的 —— 本條失去對象（fail-closed）。"
    for _w in _CONCLUSION_WORDS:
        assert _w not in _body, (
            f"（{kind}）結論層出現了結論性字眼 {_w!r}：\n{_body}\n"
            "⛔ 結論層排在**所有閘門之前**，它一次都還沒量過任何來源 —— "
            "說「正常」是憑空捏造一個系統健康狀態（`CLAUDE.md §1`）。")


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_verdict_names_the_only_switch_it_can_see(kind: str):
    """⭐⭐ **正向要求**：結論那句話必須**指名它量到的那一顆開關**。

    ⛔ **這是本節唯一擋得住「換一種說法」的規則，理由請讀完再改。**

    這一層唯一量得到的東西是 :data:`_SK_DIAG_GATE`（本頁自己寫的那個鍵，見
    :func:`_diag_gate_is_on`）。**一句沒有指名自己量了什麼的結論，不是結論，是斷言。**
    於是規則反過來寫：**本文裡必須出現 :data:`DIAG_GATE_LABEL`。**

    - 稽核突變 A「一切正常，全部來源都正常，你的資料可信」→ 沒指名 → **紅**；
    - 稽核突變 B「可以信。今天每一個來源都抓到了，沒有一項缺設定。」→ 沒指名 → **紅**。
      ⭐ **B 是黑名單抓不到的那一顆** —— 它證明「正向要求」比「再加幾個詞」強。

    ⚠️ **`（請先到：…）` 那一段要先切掉再驗**：未勾那一支的 `where=` 本來就帶著
    同一個標籤，不切掉的話「本文有沒有指名」這件事會被指路**免費送過關** ——
    那就變成一條看起來有牙、實際恆真的規則。

    ⚠️ **它擋不到什麼**：指名了、然後在後面再接一句謊
    （「「🔭 …」是關的，但我可以告訴你一切正常」）——本條看得到前半、擋不到後半，
    那一半由上一條黑名單接。**兩條都不是「結論層不可能說謊了」。**
    """
    _seg = _conclusion_parts(_stream(kind))
    _grid = next((_i for _i, _p in enumerate(_seg) if _p.startswith("[Column]")), len(_seg))
    _verdict = [_p for _p in _seg[:_grid] if _p.startswith("[Caption]")]
    assert len(_verdict) == 1, (
        f"（{kind}）卡片網格之前的說明有 {len(_verdict)} 則（線框 §1：一句結論）：\n"
        + "\n".join(_verdict))
    _body = _verdict[0].split("（請先到：", 1)[0]
    assert DIAG_GATE_LABEL in _body, (
        f"（{kind}）結論那一句沒有指名它量到的那一顆開關 "
        f"（{DIAG_GATE_LABEL!r} 不在本文裡）：\n{_body}\n"
        "⛔ 這一層唯一量得到的就是那顆開關的狀態。**一句沒有指名自己量了什麼的結論，"
        "不是結論，是斷言** —— 而斷言在這一頁上就是 `CLAUDE.md §1` 的造假。\n"
        "⚠️ 若你想讓結論說更多，正解是先讀被測檔的 **(D-6)**："
        "那是一個**待裁決**的問題，不是實作組自己決定的事。")


#: 兩顆留下來的閘門的 `help=` tooltip。**AST 取值，不手抄。**
def _gate_helps() -> dict[str, str]:
    """`{閘門常數名: help= 的字面值}` —— 只收 :data:`DIAG_GATE_LABEL` /
    :data:`NAV_GATE_LABEL` 那兩顆。

    ⛔ **另外四顆是雙軌鷹架，刻意不收**：它們的 `help=` 講的是「舊分頁已經在跑同一塊」
    ——那是**真的原因**，不是進度語言，而且它們會在舊 ⑤ 下架那一批**整顆消失**。

    ⚠️ **只認 `Constant`**：四顆雙軌的 `help=` 是 f-string（`JoinedStr`），
    本函式拿不到值 —— 但那正好是刻意不收的那四顆，所以**這個限制在今天沒有缺口**。
    ⛔ **哪天那兩顆的 `help=` 改成 f-string，本函式會靜默漏掉它** ——
    故下方 :func:`test_..._in_the_tooltip_too` 對「取不到值」**fail-closed**。
    """
    _out: dict[str, str] = {}
    for _n in ast.walk(_tree()):
        if not (isinstance(_n, ast.Call)
                and getattr(_n.func, "attr", None) == "checkbox" and _n.args):
            continue
        _lbl = _dotted(_n.args[0])
        if _lbl not in ("DIAG_GATE_LABEL", "NAV_GATE_LABEL"):
            continue
        _h = next((_k.value for _k in _n.keywords if _k.arg == "help"), None)
        _out[_lbl] = (_h.value if isinstance(_h, ast.Constant)
                      and isinstance(_h.value, str) else None)     # type: ignore[assignment]
    return _out


@pytest.mark.parametrize("gate", ["DIAG_GATE_LABEL", "NAV_GATE_LABEL"])
def test_the_two_remaining_gates_stopped_talking_about_themselves_in_the_tooltip_too(
        gate: str):
    """⭐ 線框 §0 推翻 1 那條規則，**射程放大到 `help=` tooltip**。

    ⛔ **為什麼要有這一條（它補的是一個真的漏掉，不是假想的）**：
    2026-09-08 第一版把兩顆閘門的**標籤與灰態**換成處境語言，
    **`help=` 卻原封留著**「診斷區**載入**時會更新資料註冊表…」。
    **它會被漏掉不是巧合** —— :func:`test_the_two_remaining_gates_stopped_talking_about_themselves`
    的參數表是 label ＋ note 四個字串，**結構上看不到 `help=`**。
    → **文案與守衛射程一起修**（`CLAUDE.md §8.2.A.1` 驗證段 ④：
      更正一個被點名的項目時，必須把同一把尺對全部同類項目重跑）。

    ⚠️ **與那條的關係**：同一份 :data:`_PROGRESS_WORDS`（**一個字都沒動**），
       掃的是不同的位置。**放大射程，不是放寬條件。**
    """
    _helps = _gate_helps()
    assert gate in _helps, (
        f"AST 掃不到 {gate} 那顆 checkbox —— 本條失去對象（fail-closed）。\n"
        f"掃到的：{sorted(_helps)}")
    _v = _helps[gate]
    assert isinstance(_v, str), (
        f"{gate} 的 `help=` 不是字面字串（可能改成了 f-string）——"
        "本條讀不到值，**fail-closed**：請改回字面值，或把本函式一起放大。")
    _hit = [_w for _w in _PROGRESS_WORDS if _w in _v]
    assert not _hit, (
        f"{gate} 的 `help=` 又開始講系統自己了：命中 {_hit}\n  {_v!r}\n"
        "⛔ 線框 §0 推翻 1：使用者要知道的是「這一下要花我多久、不按會怎樣」。")


#: 金鑰／Proxy 面板**實際**住的那兩個標題（`ui/tab5_data_guard.py`）。
#: ⚠️ **這兩個字串是本檔對【別的檔案】的唯一硬編引用** —— 它們是**錨點**：
#:    哪天那兩塊被搬走或改名，下面那條會 **fail-closed**（而不是靜靜地繼續綠），
#:    因為那正是「🔑 那張卡該指去哪」需要重新裁決的時刻。
_KEY_PANEL_HEADINGS: tuple[str, ...] = (
    "### ④ 🔑 API 金鑰狀態", "### ③ 🌐 NAS Proxy 中繼站狀態")


def test_the_key_card_does_not_point_at_a_block_that_cannot_answer_it():
    """⭐⭐ 🔑 那張卡**不准指向一個自陳裝不下那個答案的區塊**。

    ⛔ **這條補的是 2026-09-08 回修裡唯一存活下來的那顆突變。**
    把 :data:`_CARD_KEYS_NOTE` 改回「回答：上面那兩件事能不能做。**先看這一塊再看上面。**」
    → 修完第一版之後 **140 passed、突變存活**。也就是說 ⛔2 那個錯**可以被原封改回去**
    而沒有任何一條規則會叫 —— 一個「修好了但沒有守衛」的修正，等於還沒修。

    **本條驗三件事，前兩件是【重量事實】、第三件才是斷言**
    （事實一旦不成立就 fail-closed，因為那正是該重新裁決的時刻）：

    1. **金鑰／Proxy 的面板真的住在 `ui/tab5_data_guard.py`**（:data:`_KEY_PANEL_HEADINGS`）；
    2. **`_render_keys()` 真的沒有它們** —— 它委派的只有
       `render_policy_admin_bridge` ＋ `render_fetch_diag_from_session`；
    3. ⇒ 🔑 那張卡的 `where` **不得**指向 `BLOCK_KEYS`，而它的說明**必須指名**
       答案真正住的那一塊（:data:`BLOCK_HEALTH`，因為 tab5 由它委派）。

    ⚠️ **這一條不是在說「連線與金鑰這一塊沒用」** —— 它裝的東西（保單管理指路、
    抓取診斷）是真的；本條只禁止**把一個它答不出來的問題指給它**。
    ⚠️ **擋不到什麼**：卡片說明可以指名 `BLOCK_HEALTH` 之後再接一句別的謊。
    本條驗「有沒有指到對的地方」，**不驗整段文案為真**。
    """
    # ── (1) 事實：那兩塊真的在 tab5 ──────────────────────────────────
    _tab5 = (ROOT / "ui" / "tab5_data_guard.py").read_text(encoding="utf-8")
    _absent = [_h for _h in _KEY_PANEL_HEADINGS if _h not in _tab5]
    assert not _absent, (
        f"`ui/tab5_data_guard.py` 裡找不到 {_absent} —— 金鑰／Proxy 面板被搬走或改名了。\n"
        "⛔ 這不是本條壞了，是**該重新裁決 🔑 那張卡指去哪**的時刻（fail-closed）。")

    # ── (2) 事實：`_render_keys()` 沒有它們，只委派那兩支 ──────────────
    _fn = next((_n for _n in ast.walk(_tree())
                if isinstance(_n, ast.FunctionDef) and _n.name == "_render_keys"), None)
    assert _fn is not None, "`_render_keys` 不見了 —— 本條失去對象（fail-closed）。"
    _delegates = {_dotted(_n.func) for _n in ast.walk(_fn) if isinstance(_n, ast.Call)}
    assert "render_policy_admin_bridge" in _delegates, (
        f"`_render_keys` 不再委派保單管理橋接 —— 那一塊的內容變了，本條的前提要重驗。\n"
        f"實際呼叫：{sorted(_delegates)}")
    # ⛔⛔ **2026-09-09 第三輪回修：這一格量錯了東西（有意識的更正，不是漏刪）。**
    #
    # **舊寫法**（原地保留、加刪除線，不刪）::
    #
    #     ~~assert not any(_h.split()[-1] in _s for _h in _KEY_PANEL_HEADINGS~~
    #     ~~               for _s in _delegates)~~
    #
    # **它拿【中文標題的字尾】去比對【Python 呼叫名】**，本組實測：
    #     `_h.split()[-1]`  → `['金鑰狀態', '中繼站狀態']`      ← 中文
    #     `_delegates`      → `{'render_policy_admin_bridge', 'st.checkbox', …}` ← 識別字
    #     `any(...)`        → **False，而且是恆 False**
    # **中文永遠不會出現在 Python 識別字裡 ⇒ 這個 `assert not any(...)` 恆真。**
    # 正對照（本組實測）：把一個含那段中文的假名字塞進 `_delegates` → `any(...)` 為 True
    # ⇒ **比對式本身會動，錯的是它量的位置。**
    # **突變實測**：在 `_render_keys()` 裡直接寫
    # `st.markdown("### ④ 🔑 API 金鑰狀態")` —— **它宣稱在偵測的那件事逐字發生了，
    # 150 條全綠存活**，而那個世界裡 🔑 卡的「底下那一塊今天回答不了金鑰」當場變成假話。
    #
    # ⚠️ **這與本輪 ⛔1 的 `.count("")` 是同一族**：工具沒有量到它宣稱在量的東西，
    #    而空結果被讀成「沒問題」。**修法是換量測位置，不是刪掉這條斷言。**
    _consts = _str_consts_in(_fn)
    #: 標題去掉 `### ` 與圈號之後的**識別部分**（`'### ④ 🔑 API 金鑰狀態'` → `'🔑 API 金鑰狀態'`）。
    #: ⚠️ 用它而不是整個標題：`### 🔑 API 金鑰狀態`（少了圈號）同樣是在畫那塊面板。
    _cores = [_h.split(maxsplit=2)[-1] for _h in _KEY_PANEL_HEADINGS]
    _drawn = [_c for _c in _consts if any(_core in _c for _core in _cores)]
    assert not _drawn, (
        f"`_render_keys` 的函式體裡出現了金鑰／Proxy 面板的標題字：{_drawn}\n"
        f"（判準：{_cores}）\n"
        "⇒ 它看起來開始**自己畫**金鑰／Proxy 了 —— 若屬實，"
        "🔑 那張卡就該改指回 `BLOCK_KEYS`，請一起改本條（fail-closed）。")
    # ── 封閉版：這一塊**只委派、不自己畫標題**，所以它不該有任何 `### ` 字面值 ──
    # ⛔ 上面那條是**黑名單**（只認那兩個面板）；這一條是**封閉的** ——
    #    它不問「畫的是不是金鑰」，只問「有沒有自己畫標題」。
    #    本塊的合法產出只有：`render_policy_admin_bridge` ／ 一顆 gate ／ 一句 `not_ready`
    #    ／`render_fetch_diag_from_session`，**一個 `### ` 都不該有**
    #    （區塊標題由 `render_settings_and_diagnostics` 統一畫，見該函式的註記）。
    _headings = [_c for _c in _consts if "###" in _c]
    assert not _headings, (
        f"`_render_keys` 的函式體裡出現了 `### ` 標題字面值：{_headings}\n"
        "⛔ 這一塊只委派、不自己畫標題（區塊標題由 `render_settings_and_diagnostics` 畫，"
        "`test_each_block_heading_is_drawn_exactly_once` 數的就是那些）。\n"
        "⇒ 它開始自己畫東西了，🔑 那張卡「底下那一塊回答不了金鑰」要重新裁決（fail-closed）。")

    # ── (3) 斷言：卡片指去答案真正住的那一塊 ─────────────────────────
    _card = next((_c for _c in _conclusion_cards() if "金鑰" in _c["title"]), None)
    assert _card is not None, (
        f"結論層沒有金鑰那張卡了：{[_c['title'] for _c in _conclusion_cards()]}")
    assert _card["where"] != _below(BLOCK_KEYS), (
        f"🔑 那張卡指向「{BLOCK_KEYS}」，但那一塊**回答不了金鑰** ——\n"
        "被測檔 `_render_keys` 自己的 docstring 就寫著「「API 金鑰狀態 / NAS Proxy 測試」"
        "仍住在 `render_data_guard_tab()` 深處……**這是已知缺口，不是漏做**」。\n"
        "⛔ 一塊自陳裝不下的區塊，不可以被新加的卡說成答案在那裡"
        "（線框 §3 末項授權的是「**登記，不動工**」，不是「加一張卡宣稱它已經裝得下了」）。")
    assert _card["where"] == _below(BLOCK_HEALTH), (
        f"🔑 那張卡的指路是 {_card['where']!r}，但金鑰／Proxy 由「{BLOCK_HEALTH}」"
        "那一塊委派的 `render_data_guard_tab()` 畫。")
    assert BLOCK_HEALTH in _card["note"], (
        f"🔑 那張卡的說明沒有指名答案真正住的那一塊（「{BLOCK_HEALTH}」）：\n"
        f"{_card['note']}\n"
        "⛔ 只把 `where` 改對、說明還在講「先看這一塊」，使用者讀到的仍然是錯的地方。")


# ══════════════════════════════════════════════════════════════════
# 2026-09-08 第二輪回修：把「禁令」變成「守衛」
# ══════════════════════════════════════════════════════════════════
# ⛔⛔ **本節補的是同一個病的第二次發作，而診斷書是我自己在上一輪寫的**：
#   PR §4 逐字：「**一個修好了但沒有守衛的修正等於還沒修。**」
#   —— 上一輪對 🔑 卡照做了（補了 `test_the_key_card_does_not_point_at_...`），
#   **對結論層沒有**。第二輪獨立稽核用五顆突變證明了這一點：
#
#   | 稽核突變 | 修前 |
#   |---|---|
#   | **K1** 畫新線框的四個示意值（`0.4 秒`／`3 天前`／`16 源`／`5 檔`） | **存活** |
#   | **K2/K3** 把線框那兩句判定硬寫進 verdict | **存活** |
#   | **A3** 整頁全稱句原封改回、句首加一個 gate 標籤 | **存活** |
#   | **A4** 改回「逐源結果」那個承諾 | **存活** |
#   | **A5** 指名 gate ＋ 新編一句沒命中黑名單的謊 | **存活** |
#
#   **K0 正對照**（塞舊值 `42 檔 · 最長 6.2 年` → RED）證明既有的全頁字表守衛
#   **已經看得到結論層** —— 所以修法有界，不必發明新機制。

def _wireframe_illustrative_values() -> tuple[str, ...]:
    """從**客戶簽核的線框** ⑦ 那兩張 ASCII 圖裡，自動萃取「帶單位的數字」。

    ⭐⭐ **為什麼是「自動萃取」而不是再手抄一份字表 —— 這是本條的全部重點。**

    既有的 :data:`_PINNED_FAKE_VALUES` 是**手抄的，而且抄的是上一版線框**。
    **本組實測（`0` / `1` 是出現次數）**：
    新線框 ⑦ 的 `<pre>` 裡 `0.4 秒` **1**、`3 天前` **1**、`16 源` **1**、`5 檔` **1**、
    `2 項` **1**、`2 個來源` **1**、`42 檔` **1**；
    而字表釘的 `6.2 年` **0**、`18 源` **0**、`2 異常` **0**。
    ⇒ **字表七個值裡只有 `42 檔` 還在新線框上**，其餘六個釘的是**上一版的東西**，
    而**新線框的四個示意值一個都沒被釘住**。
    **一份手抄的黑名單，會在線框改版的那一刻靜靜地開始守錯的東西。**

    ⇒ **本函式讓字表跟著客戶簽核的那份檔案走**：線框改了，禁令自動跟著改。

    ⚠️ **它擋不到什麼，照實寫**：只認 `數字[.數字] + 量詞` 這個形狀。
       線框裡不帶單位的裸數字、換算成別的寫法（「十六個來源」）、
       以及**線框以外**的任何捏造值，**本函式結構上看不到**。
       ⛔ 所以 :data:`_PINNED_FAKE_VALUES` **刻意保留不刪** ——
       它釘的是**上一版線框**的值，那些在今天仍然不該出現在畫面上。
       **兩份一起看：一份跟著線框走，一份是歷史沉澱。**
    """
    _sec = _wireframe_p7_raw()
    _txt = re.sub(r"<[^>]+>", "", _sec)
    _txt = (_txt.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&"))
    _txt = "".join(_c if _c not in "│┌┐└┘├┤─" else " " for _c in _txt)
    _re = re.compile(r"\d+(?:\.\d+)?\s*(?:秒|天前|天|檔|源|項|個來源|個|年|筆|次|%)")
    return tuple(sorted({_m.group(0) for _m in _re.finditer(_txt)}))


@functools.lru_cache(maxsize=1)
def _wireframe_p7_raw() -> str:
    """⑦ 那兩張 `<pre class="wf">` 的**原始**內容（未去空白）。fail-closed 同 :func:`_wireframe_p7`。"""
    _raw = WIREFRAME.read_text(encoding="utf-8")
    assert _WF_P7_START in _raw and _WF_P7_END in _raw, (
        f"線框 {WIREFRAME.name} 裡找不到 ⑦ 那一節的錨點（fail-closed）。")
    _pres = _WF_PRE.findall(_raw[_raw.index(_WF_P7_START):_raw.index(_WF_P7_END)])
    assert len(_pres) == 2, f"⑦ 的 ASCII 線框圖有 {len(_pres)} 張，應為 2 張（fail-closed）。"
    return "\n".join(_pres)


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_page_never_prints_an_illustrative_value_from_the_current_wireframe(kind: str):
    """⭐⭐ **稽核 K1**：新線框那幾個示意值，一個都不准出現在畫面上。

    被測檔自己寫了兩處禁令 —— (D-6) 的「⛔ 線框那三張卡的數字一個都不准畫
    （`0.4 秒` / `3 天前` / `42 檔` / `16 源` / `5 檔`）」與
    :data:`_VERDICT_UNCHECKED` 的「⛔ 也不准退而求其次去畫」——
    **而在本條之前，五個裡只有 `42 檔` 有守衛**（那還是因為它剛好落在
    :data:`_PINNED_FAKE_VALUES` 這份**上一版**的字表裡）。
    **禁令是對的，缺的是牙。**

    ⚠️ **字表由 :func:`_wireframe_illustrative_values` 從線框自動萃取**，
       不是再手抄一份 —— 手抄的那一份已經示範過它會怎麼過期。
    """
    _vals = _wireframe_illustrative_values()
    assert len(_vals) >= 5, (
        f"從線框只萃取到 {len(_vals)} 個示意值 {_vals} —— 少於 5 個代表萃取器"
        "或線框結構變了，本條正在對空氣生效（fail-closed）。")
    _all = _text(_stream(kind))
    for _v in _vals:
        assert _v not in _all, (
            f"（{kind}）畫面上出現了線框的示意值 {_v!r}。\n"
            "⛔ 那不是資料，是線框用來示範版面的假數字 —— 而這一頁的職責就是回答"
            "「資料可不可信」，在這裡放假數字是最壞的一種（`CLAUDE.md §1`）。")


#: 結論那兩句話的**逐字底本**。⚠️ **這是一份刻意的第二份真相源，理由寫在下面那條守衛裡。**
_VERDICT_PINNED: dict = {
    "unchecked": (
        "**這一格只回答一件事：「{gate}」這個開關現在是關的，所以資料來源狀態還沒查。** "
        "其餘各塊**各自**寫了自己現在的狀態 —— 這一格**看不到它們，也不替它們發言**"
        "（它們的開關沒有留下這一格讀得到的痕跡）。"),
    "checked": (
        "**這一格只回答一件事：「{gate}」這個開關已經打開了。** "
        "查到什麼、{fail}，在底下「{block}」那一塊 —— 這一格**不**替它壓成一句話"
        "（壓了就會變成第二份跟底下不同步的真相，而使用者會信排在前面的那一句）。"
        "其餘各塊同樣**各自**寫自己的狀態，這一格看不到它們。"),
}


def test_the_verdict_text_is_pinned_word_for_word():
    """⭐⭐⭐ **稽核 A3 / A4 / A5 的終點**：結論那兩句話**逐字釘死**。

    ⛔⛔ **為什麼非得是逐字，而不是再多幾條語意規則 —— 讀完再改。**

    上一輪加了兩條規則（黑名單 ＋「必須指名那顆開關」），第二輪稽核用三顆突變證明
    **兩條合起來仍然擋不住**：
    - **A3**：把整頁全稱句**原封改回去、句首加一個 gate 標籤** → 兩條都過；
    - **A4**：改回「逐源結果」那個承諾 → 兩條都過；
    - **A5**：指名 gate ＋ **新編一句沒命中黑名單的謊** → 兩條都過。
    **A5 是關鍵**：它是**照著黑名單的補集構造**出來的 ——
    **任何黑名單對它都必敗**，而本檔自己的 docstring 早就寫了這句話。
    ⇒ **要關掉「第 N+1 種說法」，只有一個辦法：把合法說法列成【封閉集合】。**

    ## ⚠️ 這是一份**刻意的第二份真相源**，代價據實寫

    本 repo 一般禁止在測試裡抄產品碼的字面值（那會讓「改被測檔 ＋ 改守衛」一起變綠）。
    **本條刻意例外，理由與 :func:`test_the_wireframe_verbatim_strings_...` 同族**：
    這兩句話是 **§1 承重的宣稱**（它們對使用者斷言「這一頁現在知道什麼」），
    不是實作細節。**要改動一句 §1 承重的宣稱，本來就應該同時改動它的守衛** ——
    那正是 `_DELEGATION_ALLOWLIST` 已經在用的形狀：**封閉集合 ＋ 雙向 fail-closed**。
    ⛔ **代價**：任何合法的措辭調整都會紅。**那是本條的用意，不是它的瑕疵。**
    ⚠️ **它擋不到的那一種**：有人**同時**改被測檔與本表。**那是一次看得見的 diff**，
       而且會撞上下面三條「有理由的」守衛（它們解釋 why，本條只負責關住 N+1）。

    ⚠️ **`{gate}` / `{block}` / `{fail}` 這三個佔位符刻意保留** ——
       它們的值分別走 :data:`DIAG_GATE_LABEL` / :data:`BLOCK_HEALTH` /
       :data:`_FAILURE_ALLOWANCE`，**本表不抄那三個值**（抄了才真的是第二份真相源）。
    """
    assert _VERDICT_UNCHECKED == _VERDICT_PINNED["unchecked"], (
        "結論（開關關著那一支）的文字被改了。\n"
        f"現行：{_VERDICT_UNCHECKED!r}\n底本：{_VERDICT_PINNED['unchecked']!r}\n"
        "⛔ 這是一句 **§1 承重的宣稱**：它對使用者斷言「這一頁現在知道什麼」。\n"
        "   本層唯一量得到的是 `_SK_DIAG_GATE` 一個鍵 —— 任何超出那一顆開關的說法"
        "（「這一頁一次都還沒去查」「底下每一塊都要你按一下才會去查」）**都是假的**：\n"
        "   前者在使用者勾了 NAV 閘門時當場被推翻；後者六塊裡有四塊按下去是**紅色錯誤**，\n"
        "   不是「去查」（見那四塊自己的灰態原文）。\n"
        "✅ 若這是一次**有意的**改寫，請把新文字同時放進 `_VERDICT_PINNED` —— "
        "**登記本身就是那份紀錄**。")
    assert _VERDICT_CHECKED == _VERDICT_PINNED["checked"], (
        "結論（開關開著那一支）的文字被改了。\n"
        f"現行：{_VERDICT_CHECKED!r}\n底本：{_VERDICT_PINNED['checked']!r}\n"
        "⛔ 特別注意「**逐源結果**」那個舊承諾不得回來：`_render_source_health` 走 "
        "`safe_section()`，委派拋例外時底下是**一個紅框**，沒有任何逐源結果。\n"
        "✅ 有意改寫請同步 `_VERDICT_PINNED`。")


#: 「這一格看得到整頁」這種**範圍宣稱**的字表。
#: ⚠️ 黑名單，抓不到第 N+1 種說法 —— **關住 N+1 的是上面那條逐字釘**；
#:    本條的價值在於**它的失敗訊息說得出「為什麼那句話是假的」**（有量到的反證）。
_PAGE_SCOPE_WORDS: tuple[str, ...] = (
    "這一頁", "整頁", "每一塊", "每一項", "所有區塊", "全部區塊", "所有來源", "每一個來源")


def test_the_verdict_is_not_contradicted_by_what_the_page_really_did():
    """⭐⭐ **稽核 A3 的「有理由」那一半**：用一個**真的渲染出來的世界**證明範圍宣稱是假的。

    **做法**：把 **NAV 閘門勾起來、資料來源閘門不勾**，L2 走 patch（⛔ 不打外部）。
    在那個世界裡：

    1. **本條先量**：`coverage` 真的被呼叫了 —— 也就是**這一頁確實查過東西**；
    2. 而 `_diag_gate_is_on()` 仍是 `False`，所以結論走的是**「還沒查」那一支**；
    3. ⇒ **任何「這一頁一次都還沒去查」形狀的句子，在這個畫面上當場為假。**

    ⛔ **這不是假想的世界**：`NAV_GATE_LABEL` 那顆閘門就在同一頁上，使用者點得到，
       而它**沒有帶 `key=`**（帶了會違反 `test_the_page_writes_only_its_own_session_key`）
       —— 所以結論層**結構上不可能知道**它被勾了。**這正是「收窄宣稱」的全部理由。**

    ⚠️ **字表是黑名單，擋不住第 N+1 種範圍宣稱** ——
       那一半由 :func:`test_the_verdict_text_is_pinned_word_for_word` 關住。
       **本條負責的是「說得出為什麼」，不是「關得住全部」。**
    """
    _parts, _calls = _run_gated(BACKEND_ON, FAKE_COVERAGE, funds=FAKE_HOLDINGS,
                               open_gate=True)
    assert _calls["coverage"] >= 1, (
        f"NAV 閘門勾起來之後 L2 一次都沒被呼叫（{_calls}）—— "
        "本條的反證世界沒有成立，它正在對空氣生效（fail-closed）。")
    _seg = _conclusion_parts(_parts)
    _grid = next((_i for _i, _p in enumerate(_seg) if _p.startswith("[Column]")), len(_seg))
    _verdict = [_p for _p in _seg[:_grid] if _p.startswith("[Caption]")]
    assert len(_verdict) == 1, f"卡片網格之前的說明有 {len(_verdict)} 則：\n{_verdict}"
    _body = _verdict[0].split("（請先到：", 1)[0]
    _hit = [_w for _w in _PAGE_SCOPE_WORDS if _w in _body]
    assert not _hit, (
        f"結論那一句做了範圍宣稱：命中 {_hit}\n{_body}\n"
        f"⛔ **而這個畫面本身就是反證**：同一輪裡 NAV 那一塊真的讀了雲端"
        f"（`coverage` 被呼叫 {_calls['coverage']} 次），"
        "而結論層**看不到那顆閘門**（它沒有 `key=`）。\n"
        "⇒ 這一格只能講它自己那顆開關，不能講「這一頁」。")


#: 「先去打開那個開關」這個祈使句的**唯一措辭**（被測檔 `_CARD_KEYS_UNCHECKED` 的字面）。
#: ⚠️ 具名是為了讓失敗訊息說得出「哪一句在開關已開時變成假的」。
_OPEN_IT_FIRST: str = "要先打開那個開關才看得到"


def test_anything_that_promises_a_result_also_allows_failure():
    """⭐⭐ **稽核 A4 ＋ 必修 B**：凡是承諾「打開之後看得到什麼」的句子，都要允許失敗。

    **本條先量一個真的世界**：把 `render_data_guard_tab` 換成會拋例外的假件、
    閘門勾起來 —— 底下出現的是 :func:`safe_section` 的**紅框**，不是任何結果。
    ⇒ **在那個畫面上，「就看得到」是一句假話**，除非它同時說「或看不到、以及為什麼」。

    ⛔ **這一條抓的是一個真的發作過兩次的病**：
    第一輪回修時 :data:`_CARD_HEALTH_CHECKED` 已經寫了對沖，
    **結論與 🔑 卡都沒有** —— **同一把尺沒有對它們重跑**
    （`EXCEPTIONS.md §8.2.A.1` 驗證段 ④：更正一個被點名的項目時，
    必須把同一把尺對全部同類項目重跑）。
    現在三處共用 :data:`_FAILURE_ALLOWANCE` 一個常數，**少寫一處守衛就看得見**。
    """
    import sys

    class _Boom(RuntimeError):
        pass

    class _FakeRegistry:
        @staticmethod
        def _update_data_registry(*_a: Any, **_k: Any) -> None:
            return None

    class _FakeGuard:
        @staticmethod
        def render_data_guard_tab(*_a: Any, **_k: Any) -> None:
            raise _Boom("模擬 render_data_guard_tab 整塊炸掉")

    _fakes = {"ui.helpers.data_registry": _FakeRegistry,
              "ui.tab5_data_guard": _FakeGuard}
    _orig = {_n: sys.modules.get(_n) for _n in _fakes}
    for _n, _f in _fakes.items():
        sys.modules[_n] = _f                                    # type: ignore[assignment]
    try:
        _at = _app(FAKE_HOLDINGS)
        _cb(_at, DIAG_GATE_LABEL).check()
        _rerun(_at)
        _parts = _flat(_at.main)
    finally:
        for _n, _m in _orig.items():
            if _m is None:
                sys.modules.pop(_n, None)
            else:
                sys.modules[_n] = _m

    assert [_p for _p in _parts if _p.startswith("[Error]")], (
        "委派拋了例外，畫面上卻沒有任何紅框 —— 本條的反證世界沒有成立（fail-closed）。")

    # ⛔⛔ **這一行是被一顆存活的突變逼出來的，刪掉本條就白留**：
    #    把 `_FAILURE_ALLOWANCE` 掏空成 `""` → `"任何字串".count("")` 回傳的是
    #    **字元數 + 1**（一個很大的數），於是下面的 `>= 3` **恆真、突變存活**
    #    （實測 150 passed）。**這正是本 session 反覆記載的那個形狀：
    #    工具沒有量到它宣稱在量的東西，而空結果被讀成「沒問題」。**
    # ⚠️⚠️ **登記：這一條 fail-closed 量的是【長度】，不是【語意】**
    #    （2026-09-09 第三輪稽核指出，本組實測確認 —— **只登記，本輪不動工**）。
    #    **實測**：`_FAILURE_ALLOWANCE = "或或或或"` → **155 passed 存活**。
    #    四個無意義的字通過 `len(...) >= 4`，也通過下面的 `.count(...) >= N`
    #    （四處都會印出它），於是「每一句承諾都有對沖」在形式上成立、**在語意上全空**。
    # ⛔ **要記的不是「4 應該改成幾」** —— 換成任何長度門檻都是同一個病。
    #    上一輪把 `.count("")` 恆真那個洞補成 `len(...) >= 4`，
    #    **治法是「量長度」，而那件事本來就不是長度問題**：
    #    它要保證的是「這句話真的在對沖失敗」，而長度量不到那個。
    # ⚠️ **本條也不被 `_CARD_TEXT_PINNED` 擋到**：那份底本**刻意保留 `{fail}` 佔位符
    #    不展開**（不抄那個值，理由見該表），所以 `_FAILURE_ALLOWANCE` 換成什麼
    #    對它都是透明的。**這是那份底本的設計取捨，不是它壞了 —— 但缺口要寫明。**
    # ⚠️ **本組未評估修法**（可能的方向：把它一起釘進底本？那會讓底本抄一份值；
    #    或改驗「它出現在承諾句的同一句裡」？那仍是形態不是語意）。**留給下一組。**
    assert len(_FAILURE_ALLOWANCE) >= 4, (
        f"`_FAILURE_ALLOWANCE` 是 {_FAILURE_ALLOWANCE!r} —— 太短或被掏空。\n"
        "⛔ 空字串會讓下面那個 `.count(...) >= N` **恆真**，本條當場失去對象"
        "（fail-closed）。對沖要對沖得出來，它得是一句真的話。\n"
        "⚠️ **本條只量長度，量不到語意** —— 見上方登記（`或或或或` 照樣通過）。")
    _body = _text(_conclusion_parts(_parts))
    assert _body, "結論層是空的（fail-closed）。"
    # ⚠️⚠️ **這個下限被逼上來【兩次】，兩次都是同一個病：N 等於「已經補好的那幾個」。**
    #
    #    **第一次（2026-09-08 第二輪）**：寫 `>= 2`，而拿掉 🔑 卡的對沖之後
    #    結論 ＋ 🔭 卡仍有 2 句 → **突變存活**。改成 3。
    #    **第二次（2026-09-09 第三輪獨立稽核）**：`3` 只數了
    #    **結論 ＋ 🔭 卡 ＋ 🔑 卡** —— 而**同型的站點有四個**：
    #    🗂️ NAV 那張卡也寫著「**答案在下面那一塊**」，那同樣是一句
    #    「打開之後看得到什麼」的承諾，而**那一塊同樣會失敗**。
    #    **本組實測的那個世界**（`NAV_GATE_LABEL` 勾起 ＋ `fetch_nav_coverage` 拋例外）：
    #    `[Error]` 元素 1 個（`safe_section` 的紅框），而那張卡仍在說「答案在下面那一塊」。
    #
    # ⛔⛔ **要記的不是「3 應該是 4」，是【這個數字的來源方式本身有問題】**：
    #    `_WANT` 一直被設成「**我剛剛補好了幾處**」，而不是「**該有幾處**」——
    #    於是它結構上永遠看不到第 N+1 個站點。
    #    （`EXCEPTIONS.md §8.2.A.1` 驗證段 ④：更正一個被點名的項目時，
    #    必須把同一把尺對**全部**同類項目重跑。**這裡連續兩輪都沒有做到。**）
    # ⚠️ **本輪的做法**：把 N **從卡片清單推導**，不再手寫 —— 卡片多一張、
    #    承諾就多一句，下限自己跟著長。**⛔ 不要改回手寫的數字。**
    _WANT = 1 + len(_conclusion_cards())   # 結論那一句 ＋ 每張卡各一句
    assert _body.count(_FAILURE_ALLOWANCE) >= _WANT, (
        f"開關已開的畫面上，帶「{_FAILURE_ALLOWANCE}」對沖的句子只有 "
        f"{_body.count(_FAILURE_ALLOWANCE)} 句，應有 {_WANT} 句"
        "（結論那一句 ＋ 🔭 卡 ＋ 🔑 卡）。\n"
        f"{_body}\n"
        "⛔ 這個畫面上底下就是一個紅框 —— 任何『打開就看得到』的承諾在這裡是假的。")

    # ── 必修 A：🔑 卡必須跟著同一顆開關翻面 ─────────────────────────
    # ⛔ **這一段抓的是一顆真的存活過的突變**：把 `_CARD_KEYS_CHECKED` 直接指成
    #    `_CARD_KEYS_UNCHECKED`（＝不翻面）→ **150 passed、存活**。
    #    那正是被擋下來的原錯：同一畫面上，結論說「這個開關**已經打開了**」，
    #    四行之後那張卡說「**要先打開**」。
    from ui.views.page_05_settings import (           # noqa: PLC0415
        _CARD_KEYS_CHECKED, _CARD_KEYS_UNCHECKED)
    assert _CARD_KEYS_CHECKED != _CARD_KEYS_UNCHECKED, (
        "🔑 那張卡的兩支文案一模一樣 —— 它不會跟著開關翻面。\n"
        "⛔ 它講的是 `DIAG_GATE_LABEL`，而那顆的狀態在同一次渲染裡**被讀過**"
        "（`_diag_gate_is_on()`）。**讀得到卻不讀，就是一句當場就假掉的話。**\n"
        "⚠️ 它不能引用 `_CARD_NAV_NOTE` 那個免責 —— 那張卡的免責是"
        "「`NAV_GATE_LABEL` 沒有 `key=`、讀不到」，**🔑 卡沒有這個免責**。")
    assert _OPEN_IT_FIRST not in _body, (
        f"開關已經打開的畫面上，結論層還在叫使用者「{_OPEN_IT_FIRST}」：\n{_body}\n"
        "⛔ 同一個畫面上，結論那一行剛說完「這個開關**已經打開了**」。")


#: `結論卡的標題關鍵字 -> (它該指的區塊, 那一塊為什麼答得出來的【可重量事實】)`。
#:
#: ⛔ **每一列的第二欄是一個 AST 可驗的錨點，不是註解** —— 事實一旦翻轉就 fail-closed，
#:    因為那正是「這張卡該改指哪裡」需要重新裁決的時刻（同 🔑 卡那條的做法）。
_CARD_ANSWERED_BY: tuple[tuple[str, str, str, str], ...] = (
    ("資料來源健康度", "BLOCK_HEALTH", "_render_source_health", "render_data_guard_tab"),
    ("NAV",           "nav_status_label", "_render_nav_status", "fetch_nav_coverage"),
    ("金鑰",           "BLOCK_HEALTH", "_render_source_health", "render_data_guard_tab"),
)


@pytest.mark.parametrize("title_key,block_src,fn_name,must_call",
                         _CARD_ANSWERED_BY,
                         ids=[_t for _t, _, _, _ in _CARD_ANSWERED_BY])
def test_every_card_points_at_the_block_that_can_actually_answer_it(
        title_key: str, block_src: str, fn_name: str, must_call: str):
    """⭐⭐ **必修 C**：把「不得指向答不了的區塊」這條規則**放大到三張卡**。

    ⛔ **上一輪只替 🔑 一張卡長了守衛。** 第二輪稽核把 🗂️ NAV 卡的 `where` 改指
    「連線與金鑰」（**存在、但答非所問**）→ **GREEN 存活**。
    既有的 :func:`test_every_conclusion_card_points_at_a_block_that_is_really_on_screen`
    只驗「那個區塊在不在畫面上」—— **在，但答不出來**，正好從它底下溜過去。

    **本條的判準**：每張卡指的那一塊，**必須真的在做那件事**（AST 重量）：

    ===================  =========================================
    卡                    那一塊必須呼叫
    ===================  =========================================
    🔭 資料來源健康度       `render_data_guard_tab`
    🗂️ 雲端 NAV 累積      `fetch_nav_coverage`
    🔑 金鑰與連線          `render_data_guard_tab`（金鑰住在它的委派深處）
    ===================  =========================================

    ⚠️ **🔑 那一列刻意與 🔭 同指向**，理由見被測檔 :data:`_CARD_KEYS_UNCHECKED`
       的回修註記（`### ④ 🔑 API 金鑰狀態` 住在 `ui/tab5_data_guard.py`，
       由「資料來源健康度」那一塊委派）。**那不是重複，是同一個答案的兩個問題。**
    """
    _block = {"BLOCK_HEALTH": BLOCK_HEALTH,
              "nav_status_label": nav_status_label()}[block_src]
    _fn = next((_n for _n in ast.walk(_tree())
                if isinstance(_n, ast.FunctionDef) and _n.name == fn_name), None)
    assert _fn is not None, f"`{fn_name}` 不見了 —— 本條失去對象（fail-closed）。"
    _calls = {_dotted(_n.func).rsplit(".", 1)[-1]
              for _n in ast.walk(_fn) if isinstance(_n, ast.Call)}
    assert must_call in _calls, (
        f"`{fn_name}` 不再呼叫 `{must_call}` —— 「{_block}」那一塊不再回答這張卡的問題了。\n"
        f"實際呼叫：{sorted(_calls)}\n"
        "⛔ 這不是本條壞了，是**該重新裁決這張卡指去哪**的時刻（fail-closed）。")
    _card = next((_c for _c in _conclusion_cards() if title_key in _c["title"]), None)
    assert _card is not None, (
        f"結論層找不到標題含「{title_key}」的卡："
        f"{[_c['title'] for _c in _conclusion_cards()]}")
    assert _card["where"] == _below(_block), (
        f"卡片「{_card['title']}」指向 {_card['where']!r}，"
        f"但回答它的是「{_block}」（那一塊呼叫 `{must_call}`）。\n"
        "⛔ 指到一個**存在、但答非所問**的區塊，比指到不存在的更難發現 ——"
        "使用者會捲過去、看完、然後以為自己看錯了。")


# ══════════════════════════════════════════════════════════════════
# 2026-09-09 第三輪回修：把「禁令」換成【封閉集合】
#
# ⛔⛔ **本節解的是一個【方法】上的失敗，不是四個漏洞。讀完再改。**
#
# 第二輪的 commit 訊息逐字寫著：「**要關掉「第 N+1 種說法」，只有把合法說法
# 列成【封閉集合】**」「四層，**最後一層才是關住 N+1 的**」。
# **那句話在寫下的當天是假的** —— 被封閉的只有 :data:`_VERDICT_PINNED` 那兩句
# verdict 常數，而**結論層還有至少四條路可以把字印到畫面上，四條全沒封閉**
# （第三輪獨立稽核逐顆實跑、本組逐顆重跑，三道正對照齊全）：
#
#   ==========================================================  ==============
#   突變（都在 `_render_conclusion` 內）                           修前
#   ==========================================================  ==============
#   verdict **上面一行**加 `st.markdown("🟢 **可以信。…**")`        150 存活
#   卡片之後加 `st.markdown("**你目前的設定是完整的，…**")`           150 存活
#   `st.success("設定完整，可以放心使用畫面上的數字。")`              150 存活
#   多一個 `st.expander("📖 這一頁怎麼讀")` 內含「目前判定：可以信任。」 150 存活
#   （對照）同一句話改用 `st.caption`                              **RED** ✅
#   （對照）多一張**卡**                                          **RED** ✅
#   ==========================================================  ==============
#
# ⚠️ **第一顆用的句子，是逐字照抄被測檔自己 docstring 裡「稽核突變 B ⇒ 紅」的那一句。**
#    它**只在放進 Caption 時是紅的**；往上挪一行變 `st.markdown`，就綠。
#    ⇒ **既有的判準驗的是「Caption 有沒有 ⬜」與「有沒有 Metric」，
#      而那是【形態】判準 —— 換一個形態就繞過去了。**
#
# ⚠️ 它踩的是被測檔 :func:`_render_conclusion` 自己的頭條禁令：
#    「**一句話 ＋ 三張卡，沒有第四樣東西**……加一張表、加一段教學，就是把密度搬回來」
#    —— 「第四張**卡**」有牙（卡片數 ＝ 3），「**加一張表／加一段教學**」一條守衛都沒有。
#    **這是第三次同型**（⛔1 的「線框數字一個都不准畫」、`P-FLOORSLACK-1` 的
#    「⛔ 不要改大它來閉嘴」）：**一句寫在註解／docstring 裡的禁令，沒有牙。**
#
# ⭐ **總管裁決（2026-09-09）：做成一個封閉集合，不要補四個洞。**
#    ⛔ **明令不得**針對上表那四顆各補一條斷言 —— 「把稽核列出來的形狀各釘一顆」
#    正是第二輪已經證明會失敗的做法（**下一組換個角度就再撿到第五個**）。
# ══════════════════════════════════════════════════════════════════

#: 結論層**允許出現的元素種類**，以及它們的順序 —— **由卡片清單推導，不是手抄。**
#:
#: ⭐ 形狀（本組實測，三種 session 形狀 `empty` / `missing` / `loaded` **完全相同**）::
#:
#:     [Caption]  ← 結論那一句（verdict）
#:     [Block]    ← `render_cards()` 的三欄網格容器
#:       [Column] [Markdown] **標題**  [Caption] 說明     ← 每張卡三個
#:       [Column] [Markdown] **標題**  [Caption] 說明
#:       [Column] [Markdown] **標題**  [Caption] 說明
#:
#: ⚠️ **`Block` / `Column` 是純版面容器（本身不帶字）**，其餘兩種才會把字印到畫面上。
def _expected_conclusion_kinds() -> list[str]:
    """結論層該有的元素種類序列。**長度隨卡片數走，不是寫死的 11。**"""
    return ["Caption", "Block"] + ["Column", "Markdown", "Caption"] * len(_conclusion_cards())


#: 從 `[Kind] payload` 取出 `Kind`。
_ELEM_KIND = re.compile(r"^\[([A-Za-z]+)\]")


def _kinds(parts: list[str]) -> list[str]:
    return [_m.group(1) for _p in parts if (_m := _ELEM_KIND.match(_p))]


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_conclusion_layer_may_only_emit_the_shape_it_is_allowed_to(kind: str):
    """⭐⭐⭐ **封閉集合**：結論層只准長成【一句話 ＋ N 張卡】那個形狀，**沒有第四樣東西**。

    ⛔⛔ **本條是本節的全部力量所在。它與既有那幾條的差別，是【黑名單 vs 封閉集合】**：
    - 既有的 `test_the_conclusion_says_it_does_not_know_instead_of_guessing`
      問「**Caption 有沒有 ⬜**、**有沒有 Metric**」→ 那是**形態黑名單**，
      換一個形態（`st.markdown` / `st.success` / `st.expander`）就繞過去了；
    - **本條問「這裡出現的東西，在不在允許清單上」** —— 允許清單有多長，
      由 :func:`_conclusion_cards` 決定，**不由誰想得到幾種違規決定**。

    **兩層，兩層都是雙向 fail-closed（多一個紅、少一個也紅）**：

    1. **種類序列** ＝ :func:`_expected_conclusion_kinds`。
       多畫任何東西（`Success` / `Info` / `Warning` / `Expander` / `Metric` / 多一則
       `Markdown`）→ 序列長度或內容當場不符。
       **少畫**也一樣：把某張卡改走 `business_alert`（`state=STATE_BUSINESS`）
       會讓那張卡只剩 `[Column] [Markdown]`、**沒有 `[Caption]`** —— 本組實測 10 ≠ 11。
    2. **帶字的元素必須「有出處」** —— 每一個 `[Caption]` / `[Markdown]` 的內容，
       都必須對得上**卡片清單或 verdict 常數**裡的某一個來源，而且**一對一**。
       這一層擋的是「種類對、但內容是新編的」：例如把某張卡的標題換成一句結論。

    ⚠️ **為什麼種類序列可以寫得這麼死（會不會太脆）**：`[Block]` / `[Column]`
       這兩個容器名來自 AppTest 的元素樹，本檔**早就依賴它**
       （`test_every_conclusion_card_points_at_a_block_that_is_really_on_screen`
       用 `_p.startswith("[Column]")` 定位卡片網格）。**本條沒有引入新的依賴。**
       真的哪天容器結構變了 → 紅燈，而那**正是該重新看一眼這一層長什麼樣的時刻**。

    ⚠️ **擋不到什麼，照實寫（這一段不要刪）**：
    - **本條不驗那些字是不是真的。** 卡片說明可以在允許的位置說一句假話；
      那一半由 :data:`_VERDICT_PINNED` 的逐字釘、線框逐字比對、
      `_PROGRESS_WORDS` / `_CONCLUSION_WORDS` 那幾個黑名單各擋一部分，**不是本條**。
    - **同時改被測檔與本條**仍然騙得過 —— **那是一次看得見的 diff**，
      本 repo 對這一點的既有立場沒有變。
    - **卡片數本身不由本條封閉**（它從 `_conclusion_cards()` 推導，多一張卡兩邊一起長）。
      封閉卡片數的是 `test_every_conclusion_card_points_at_a_block_that_is_really_on_screen`
      的 `len(_cards) == 3`（本組實測：多一張卡 → **RED**）。**兩條合起來才是完整的。**
    """
    _seg = _conclusion_parts(_stream(kind))
    assert _seg, f"（{kind}）結論層底下一個元素都沒有 —— 本條失去對象（fail-closed）。"

    # ── (1) 種類序列：多一個紅、少一個也紅 ──────────────────────────────
    _want, _got = _expected_conclusion_kinds(), _kinds(_seg)
    assert _got == _want, (
        f"（{kind}）結論層的元素種類序列不對。\n"
        f"  應為（{len(_want)} 個）：{_want}\n"
        f"  實際（{len(_got)} 個）：{_got}\n"
        "實際內容：\n" + "\n".join(f"  {_i:2} {_p[:100]}" for _i, _p in enumerate(_seg)) + "\n"
        "⛔ 結論層只准長成【一句話 ＋ N 張卡】：`[Caption]` ＋ `[Block]` ＋ "
        "每張卡的 `[Column] [Markdown] [Caption]`。\n"
        "⇒ **多出來的元素**：被測檔 `_render_conclusion` 自己的第一條 docstring 寫著"
        "「一句話 ＋ 三張卡，**沒有第四樣東西**……加一張表、加一段教學，就是把密度搬回來」。\n"
        "⇒ **少掉的元素**：最可能是某張卡不再走 `STATE_NOT_READY`"
        "（`business_alert` / `st.metric` 分支不會畫出 `[Caption]`）——"
        "而這一層在所有 gate 之前，一個真數字都沒有，"
        "畫莓紅警示或綠色數字都是在宣稱一個沒有量過的結論（`CLAUDE.md §1`）。")

    # ── (2) 帶字的元素必須有出處，一對一 ────────────────────────────────
    # ⚠️ **來源清單由資料推導**：卡片標題／說明來自 `_conclusion_cards()`，
    #    verdict 來自 `_VERDICT_PINNED`（那份已經是逐字釘死的封閉集合）。
    #    **這裡不手抄任何一句文案。**
    # ⚠️⚠️ **兩個 gate 狀態的卡片文案【都要】收進來，這不是寬鬆，是正確性 ——
    #    而且它是被一個真的紅燈逼出來的（本組自己踩到，就地記錄）**：
    #    本條第一版只收 `_conclusion_cards()` **當下**回傳的那一份，結果
    #    **單獨跑綠、整檔跑紅** —— 因為 `_stream()` 是 `lru_cache` 的（gate 關著時算的），
    #    而 `_conclusion_cards()` 讀的是**當下的** `st.session_state`，
    #    前面某條測試把 `_SK_DIAG_GATE` 留成 True 之後，兩邊就對不上了。
    #    ⇒ **封閉集合要封閉的是「這些卡片【可能】印出哪些字」，不是「此刻剛好印了什麼」。**
    #    ⛔ 這不會讓本條變鬆：兩個狀態的文案**都是**卡片常數，新編一句話仍然無處可認。
    import streamlit as _st                                     # noqa: PLC0415

    _snap = _st.session_state.get(_SK_DIAG_GATE)
    try:
        _both: list[dict] = []
        for _gate in (False, True):
            _st.session_state[_SK_DIAG_GATE] = _gate
            _both.extend(_conclusion_cards())
    finally:
        if _snap is None:
            _st.session_state.pop(_SK_DIAG_GATE, None)
        else:
            _st.session_state[_SK_DIAG_GATE] = _snap

    _sources: list[tuple[str, str]] = [
        (f"卡片標題「{_c['title']}」", f"**{_c['title']}**") for _c in _both]
    _sources += [(f"卡片說明「{_c['title']}」", _c["note"]) for _c in _both]
    _sources += [("verdict", _v.format(gate=DIAG_GATE_LABEL, block=BLOCK_HEALTH,
                                       fail=_FAILURE_ALLOWANCE))
                 for _v in _VERDICT_PINNED.values()]

    _texted = [_p for _p in _seg if _ELEM_KIND.match(_p).group(1) in ("Caption", "Markdown")]
    _unclaimed_elems: list[str] = []
    _used: set[int] = set()
    for _p in _texted:
        _hit = [_i for _i, (_n, _src) in enumerate(_sources)
                if _i not in _used and _src and _src in _p]
        if not _hit:
            _unclaimed_elems.append(_p)
        else:
            _used.add(_hit[0])
    assert not _unclaimed_elems, (
        f"（{kind}）結論層有 {len(_unclaimed_elems)} 個帶字的元素**找不到出處**：\n"
        + "\n".join(f"  {_p[:160]}" for _p in _unclaimed_elems) + "\n"
        f"允許的出處（{len(_sources)} 個）：{[_n for _n, _ in _sources]}\n"
        "⛔ 結論層畫出來的每一個字，都必須來自**卡片清單**或**釘死的 verdict** ——\n"
        "   那兩者各自有守衛（線框逐字比對／`_VERDICT_PINNED` 逐字釘）。\n"
        "   在這裡直接寫一句新的字，等於**繞過那兩道守衛**：\n"
        "   它不會被線框比對到、也不會被逐字釘擋到，因為它不經過任何一個常數。")


#: 結論層三張卡的**逐字底本**（標題 ＋ 兩支說明文案）。
#:
#: ⭐⭐ **2026-09-09 第三輪回修新增。它補的是【封閉集合裡的一個洞】，
#:    而那個洞是本組自己在驗收上一條時撿到的，不是稽核指出的 —— 照實記。**
#:
#: :func:`test_the_conclusion_layer_may_only_emit_the_shape_it_is_allowed_to`
#: 的「出處」那一層，是**從 `_conclusion_cards()` 推導**的 —— 也就是說
#: **卡片說它算數，它就算數**。本組實測的那顆突變::
#:
#:     {"title": _CARD_NAV_TITLE, "note": "你的雲端歷史夠長，長期指標都算得出來。", …}
#:
#: → **153 passed、存活**。它避開了 :data:`_CONCLUSION_WORDS` 的每一個字
#: （沒有「正常」「無異常」「可信」），所以那份黑名單也看不到它。
#: **而它是一句這一層根本不可能知道的話**（NAV 閘門沒勾，一個點都沒讀過）。
#:
#: ⇒ **上一條關住的是「可以出現什麼【元素】」，這一條關住「可以出現什麼【字】」。
#:    兩條缺一不可 —— 只有前者，換一句新編的卡片文案就繞過去了。**
#:
#: ⚠️ **代價與 :data:`_VERDICT_PINNED` 完全相同，理由也相同**：合法改寫也會紅。
#:    這三張卡對使用者斷言「這一頁現在知道什麼、答案在哪」，是 §1 承重的宣稱。
#:    ✅ **有意改寫請同步本表** —— **登記本身就是那份紀錄。**
#: ⚠️ **佔位符 `{block}` / `{fail}` 刻意保留不展開**（同 `_VERDICT_PINNED`）：
#:    它們的值走 :data:`BLOCK_HEALTH` / :data:`_FAILURE_ALLOWANCE`，本表**不抄那兩個值**。
_CARD_TEXT_PINNED: frozenset = frozenset({
    # 標題
    "🔭 資料來源健康度",
    "🗂️ 雲端 NAV 累積",
    "🔑 金鑰與連線",
    # 🔭 卡：兩支（開關關著／開著）
    "回答：畫面上那些數字是不是今天抓到的。還沒去查 —— 查一次要幾秒。",
    "回答：畫面上那些數字是不是今天抓到的。這一輪已經去查了 —— 查到什麼、{fail}，在下面那一塊。",
    # 🗂️ 卡：一支（與 gate 狀態無關，理由見被測檔 `_CARD_NAV_NOTE` 的回修註記）
    "回答：長期指標（年化、最大回撤）有沒有足夠的歷史可以算。"
    "答案在下面那一塊 —— 它要按一下才會去讀你的 Google 試算表，讀到什麼、{fail}，都在那裡。",
    # 🔑 卡：兩支（開關關著／開著）
    "回答：上面那兩件事**能不能做**。⚠️ **底下「連線與金鑰」今天回答不了金鑰** —— "
    "它裝的是保單管理的指路與抓取診斷開關；"
    "**API 金鑰與 NAS Proxy 的狀態住在「{block}」的委派深處**，要先打開那個開關才看得到。",
    "回答：上面那兩件事**能不能做**。⚠️ **底下「連線與金鑰」今天回答不了金鑰** —— "
    "它裝的是保單管理的指路與抓取診斷開關；"
    "**API 金鑰與 NAS Proxy 的狀態住在「{block}」的委派深處**，"
    "而那個開關已經打開了 —— 往下捲就看得到（{fail}）。",
})


def test_the_conclusion_cards_say_only_what_they_are_pinned_to_say():
    """⭐⭐⭐ **封閉集合的第二層**：三張卡只准說 :data:`_CARD_TEXT_PINNED` 裡的話。

    ⛔⛔ **為什麼上一條不夠（這一段是本條存在的全部理由）**：
    上一條驗「結論層出現的元素，在不在允許清單上」，而**允許清單是從卡片推導的** ——
    卡片自己說一句新的話，那句話就自動變成合法出處。**本組實測的那顆突變**
    （把 🗂️ 卡的 `note` 換成「你的雲端歷史夠長，長期指標都算得出來。」）
    **153 passed 存活**：它避開了 :data:`_CONCLUSION_WORDS` 的每一個字，
    也在上一條的允許清單裡（因為那份清單就是它自己）。

    ⚠️ **這正是第二輪 commit 訊息那句話真正該指的東西**：
       「要關掉『第 N+1 種說法』，只有把合法說法列成**封閉集合**」——
       第二輪只把 **verdict** 列成封閉集合，**三張卡沒有**。
       而三張卡跟 verdict 一樣，是這一層對使用者的斷言。

    **雙向 fail-closed（兩個方向都要，這是「封閉」的定義）**：
    - **多**：卡片說了底本以外的話 → 紅（新編的文案無處可認）；
    - **少**：底本裡有一句**再也不會出現在任何 gate 狀態下** → 紅
      （代表那支文案已死，底本該一起清 —— 不清就會變成一份沒有人在守的殭屍登記）。

    ⚠️ **擋不到什麼，照實寫**：
    - **同時**改被測檔與本表 —— 那是一次看得見的 diff（同 `_VERDICT_PINNED`）。
    - 本條驗**字**，不驗**指路**（`where`）；指路由
      `test_every_card_points_at_the_block_that_can_actually_answer_it` 與
      `test_every_conclusion_card_points_at_a_block_that_is_really_on_screen` 驗。
    - 本條**不驗那些字是不是真的** —— 它只保證「只有這幾句話說得出口」。
      **這句話為真的責任，在把它寫進本表的那一次 review。**
    """
    import streamlit as _st                                     # noqa: PLC0415

    _snap = _st.session_state.get(_SK_DIAG_GATE)
    try:
        _seen: set[str] = set()
        for _gate in (False, True):
            _st.session_state[_SK_DIAG_GATE] = _gate
            for _c in _conclusion_cards():
                _seen.add(_c["title"])
                _seen.add(_c["note"])
    finally:
        if _snap is None:
            _st.session_state.pop(_SK_DIAG_GATE, None)
        else:
            _st.session_state[_SK_DIAG_GATE] = _snap

    # ⚠️ 卡片實際帶的是**已經展開佔位符**的字；底本刻意保留佔位符（不抄那兩個值），
    #    所以比對前把底本用同一組值展開。**展開用的是被測檔的常數，不是抄一份。**
    _pinned = {_t.format(block=BLOCK_HEALTH, fail=_FAILURE_ALLOWANCE,
                         gate=DIAG_GATE_LABEL) for _t in _CARD_TEXT_PINNED}

    _extra = sorted(_seen - _pinned)
    assert not _extra, (
        "結論層的卡片說了**底本以外**的話：\n"
        + "\n".join(f"  {_t!r}" for _t in _extra) + "\n"
        "⛔ 這三張卡是 **§1 承重的宣稱**：它們對使用者斷言「這一頁現在知道什麼、"
        "答案在哪一塊」。而這一層排在所有 gate 之前，**一個真數字都沒有** ——\n"
        "   任何超出「那一顆開關勾了沒有」的說法，都是在宣稱一個沒有量過的結論。\n"
        "✅ 若這是一次**有意的**改寫，請把新文字同時放進 `_CARD_TEXT_PINNED` —— "
        "**登記本身就是那份紀錄**（同 `_VERDICT_PINNED`）。")

    _dead = sorted(_pinned - _seen)
    assert not _dead, (
        "底本 `_CARD_TEXT_PINNED` 裡有**再也不會出現**的文案：\n"
        + "\n".join(f"  {_t!r}" for _t in _dead) + "\n"
        "⇒ 那支文案已經死了（任何 gate 狀態下都畫不出來）。\n"
        "⛔ 留著它會讓本表慢慢變成一份**沒有人在守的殭屍登記** ——"
        "底本越長，「多出來的那一句」就越不顯眼。**請一起清掉。**")


def test_every_block_including_the_conclusion_is_wrapped_in_safe_section():
    """⭐⭐ **必修 W4**：本頁**每一個**區塊渲染函式都必須走 :func:`safe_section`。

    ⛔ **這條是【封閉】的，不是「補上結論層那一個」**：它不列舉哪幾塊該包，
    而是**先數出檔內所有 `_render_*`**，再要求**每一個**都只以
    `safe_section(…, fn)` 的形式被 :func:`render_settings_and_diagnostics` 使用。
    ⇒ 哪天新增第七塊，本條**自己會長大**；忘了包 → 紅。

    **被測檔自己寫過這條規矩，但它沒有牙（第三次同型）**：
    :func:`render_settings_and_diagnostics` 的 docstring 逐字 ——
    「**每個區塊各自走 `safe_section()`，這是本頁最重要的一條紀律。**
    合併成一頁之後六個區塊共用同一次 script run：管理室當掉會一併帶走
    🔭 資料診斷與 📖 說明書，而那兩塊正是使用者出事時要去的地方」；
    結論層那一行旁邊也寫著「**結論層炸掉不得帶走下面的依據**」。
    **本組實測**：把 `safe_section("結論", _render_conclusion)` 改成
    `_render_conclusion()` → **150 passed 存活**。

    ⚠️ **這一顆與本輪 ⛔1／⛔3 是同一族，但它【不是說謊類，是韌性類】** ——
       畫面不會因此說假話，但「出事時第一個進來」的那一頁會在最需要它的時候整頁變紅框。
       **既然檔案裡把它寫成「最重要的一條紀律」，它就該有牙。**

    ⚠️ **擋不到什麼**：本條驗**接線形狀**（AST），不驗 `safe_section` 自己有沒有效。
       那一半由 `test_no_block_silently_renders_a_system_error` 等真渲染守衛負責。
    """
    _tree_ = _tree()
    _defined = {_n.name for _n in _tree_.body
                if isinstance(_n, ast.FunctionDef) and _n.name.startswith("_render_")}
    assert _defined, "檔內一個 `_render_*` 都沒有 —— 本條失去對象（fail-closed）。"

    _entry = next((_n for _n in ast.walk(_tree_)
                   if isinstance(_n, ast.FunctionDef)
                   and _n.name == "render_settings_and_diagnostics"), None)
    assert _entry is not None, "`render_settings_and_diagnostics` 不見了（fail-closed）。"

    _wrapped: set[str] = set()
    _bare: set[str] = set()
    for _n in ast.walk(_entry):
        if not isinstance(_n, ast.Call):
            continue
        _name = (_n.func.id if isinstance(_n.func, ast.Name)
                 else getattr(_n.func, "attr", None))
        if _name == "safe_section":
            _wrapped |= {_a.id for _a in _n.args
                         if isinstance(_a, ast.Name) and _a.id.startswith("_render_")}
        elif _name and _name.startswith("_render_"):
            _bare.add(_name)

    assert not _bare, (
        f"下列區塊被**直接呼叫**，沒有走 `safe_section()`：{sorted(_bare)}\n"
        "⛔ 被測檔自己的 docstring 寫著「**每個區塊各自走 `safe_section()`，"
        "這是本頁最重要的一條紀律**」——\n"
        "   六塊共用同一次 script run，任何一塊當掉會**一併帶走**其他塊，\n"
        "   而這一頁的職責是「**出事時第一個進來**」。把診斷跟故障綁在同一條命上，\n"
        "   等於在最需要它的時候把它拿走。")

    _unwrapped = sorted(_defined - _wrapped)
    assert not _unwrapped, (
        f"下列區塊有定義，但沒有被 `safe_section()` 包起來使用：{_unwrapped}\n"
        f"（已包：{sorted(_wrapped)}）\n"
        "⛔ 若它已經不再被用到，請**一起刪掉**（`CLAUDE.md §-1.5.1c 01`-2："
        "本次改動造成的孤兒，是本次的收尾義務）；\n"
        "   若它是新的一塊，請照其餘各塊的做法包 `safe_section()`（fail-closed）。")
