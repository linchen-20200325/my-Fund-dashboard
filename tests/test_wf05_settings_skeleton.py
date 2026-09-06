"""⑤ 設定與診斷新頁的骨架守衛 —— 線框 Tab 05 的五塊，一塊都不准少。

錄製法：**用真的 Streamlit 跑（AppTest），不用假的 recorder** —— 同 ④
（`tests/test_wf04_portfolio_skeleton.py` 的同名段落逐條寫了理由，這裡不重述）。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**骨架的形狀**：五個單位都在、順序對、三個灰態單位**各自**誠實灰、
Form 那一塊**不灰**（本批唯一做完的）、使用手冊**不是灰態**（D-1）、
NAV 那一塊在沒有基金時走**空狀態**而其餘四塊照樣渲染（D-2）、
以及線框的示意值一個都沒有畫出來（D-3）。

⛔ **本檔不守內容對不對** —— 本批的內容**本來就還沒填**。下一批把真內容接上時，
   :func:`test_every_grey_unit_is_grey_until_its_content_lands` 會**轉紅** ——
   **那是預期的**，屆時請把它改成「真內容放行」，**不要把它放寬**。

⛔ **本檔不驗瀏覽器裡的真實版面**：欄寬、窄螢幕折行、`expander` 收合後的實際高度 ——
   AppTest 沒有瀏覽器，那些看不到。

⛔ **本檔不重複既有的全域規則**（`ui/**` 全掃的那幾條會自動涵蓋這個新檔）：
   `tests/test_ui_grid_contract.py`（欄數）、`tests/test_ui_rerun_contract.py`（form 站點）、
   `tests/test_batch2_top_card_grid.py`（`where=` 必填、灰卡要有 remedy）、
   `tests/test_wpf_five_tab_wiring.py`（分頁名不得手抄）。
   **在這裡再抄一份等於製造第二把尺**（`CLAUDE.md §2.1`）。

⚠️ **突變覆蓋率：38/38 個 test 函式各有至少一顆會殺死它的突變（2026-09-05 實測）**
-------------------------------------------------------------------------------
⛔ **這一行是被稽核打出來的，寫下它的來歷比寫下數字重要。**
本檔第一版的 PR 描述寫「**18/18 KILLED**」—— **字面為真，但那是「18 顆突變全被殺」，
不是「守衛都是活的」**：當時檔內有 35 個 test 函式，也就是有一大半**從頭到尾
沒有被任何突變測試過**，而 2026-09-05 獨立稽核抓到的**四項必修裡有兩項就長在那裡面**
（`test_the_write_block_is_form_wrapped` 完全沒被測過、
「灰卡不可能印『正常』」那句補償控制根本不存在）。
**「N/N 全殺」是分母自己挑的，它衡量的是突變寫得準不準，不是守衛有沒有洞。**

**現行做法**：用 35 顆突變逐一記錄「它打紅了哪幾條」，再取**相異** test 函式的聯集 ——
實測 **38/38，且 35 顆每一顆都至少殺到一條**（沒有白寫的突變）。
⚠️ **仍然不等於「守衛都是對的」**：突變只證明「這條測試看得到這種改法」，
**看不到的改法它一樣看不到** —— 本檔下面那串「守不到什麼」才是那一半。

⚠️ **本檔明確守不到的（照實列，不要用形容詞）**
-----------------------------------------------
- ⛔ **示意值黑名單只有 `_PINNED_FAKE_VALUES` 那幾個字面寫法。**
  裸數字（`18` / `42` 不帶單位字）、全形數字、換算成別的寫法、以及
  **任何線框以外的捏造值**都抓不到 —— 黑名單結構上抓不到名單外的第 N+1 個。
  ⚠️ 「正常」兩個字**刻意不進**示意值黑名單（它是極常見的一般用詞，
  釘它會把往後任何一句合法說明打紅）。
  ⚠️ **這句只管這一份【全頁】名單** —— 灰態單位那份**窄**名單
  （:data:`_CONCLUSION_WORDS`）**2026-09-06 起有收**裸「正常」，見下。
  **兩份名單政策不同，不要讀成同一件事。**
  ⛔ **2026-09-05 撤回一句假的補償控制**：本段原寫
  ~~「那一格改由『連線與金鑰必須是灰態』**反向守** —— 一張灰卡不可能同時印一個
  「正常」的結論」~~ —— **那句是假的，而且比單純沒守到更危險，因為它讓後人以為
  那一格有人看著**。實測四顆突變**全部存活、三序一致**：把 `_PENDING_NOTE` 換成
  「你的資料全部正常，沒有任何異常」→ **47 passed**；在灰卡旁印
  「全部來源都正常，你的資料可信。」→ **47 passed**。
  **根因**：`state_card(state=STATE_NOT_READY)` 無條件前綴 ⬜，而守衛只查
  `NOT_READY_MARK in _body` —— **⬜ 之後接什麼都行。**
  → **現行**：見 :func:`test_no_grey_unit_states_a_conclusion`
  （2026-09-05 新增的**黑名單**，同樣抓不到名單外的第 N+1 個）。
  ⛔ **2026-09-06 再修一次，因為上面那句在寫下的當天仍然是假的**：該黑名單
  當時**八個都是片語、沒有裸「正常」**，所以在灰卡同一單位內印
  「18 個來源目前狀態：**正常**」→ **50 passed 三序，那一格還是沒有人守**。
  **前一輪撤回了一句假的補償控制，然後換上另一句假的。** 現已把裸「正常」補進字表
  （三序驗證：未突變 50 passed、該突變 1 failed）。
  ⚠️ **但它只掃「帶 ⬜ 的灰態單位」** —— 印在第一個單位之前（頁首 caption）
  或印在**刻意不灰**的單位（使用手冊）裡，本條**結構上看不到**，見該函式的登記。
- ⛔ **指路挑錯 key 沒有守衛**：職責宣告那一句裡的 `macro` / `portfolio` 兩個 key
  換成別的**合法** key，本檔不會有任何東西轉紅。
  **這是「走 SSOT」擋不到的那一類**：SSOT 保證名字不過期，**不保證你挑對了 key**。
- ⛔ **`getattr(st, "columns")(3)` / `from streamlit import columns as _c` 繞得過**
  :func:`test_the_page_draws_no_grid_form_or_tabs_of_its_own` —— repo 既有性質（③ 已登記）。
- ⛔ **`_holdings()` 只測到 `None` / 非 list / 非 dict 元素三種**；舊版 payload 形狀沒測。
- ⛔ **「使用手冊不是灰態」守的是「它沒有 ⬜、也沒走 empty_state」**，
  **不守**「它的內容是對的」—— 那三行目錄的正確性靠線框逐字比對（:func:`test_the_manual_lists_exactly_the_wireframe_three`）。

⚠️ **本檔對 `_SECTION_LABELS` 的依賴，據實寫**
---------------------------------------------
被測檔的五個區塊名裡**只有兩個**走 SSOT（`nav_status` / `nav_manual`），
另外三個是線框字面常數（`BLOCK_HEALTH` / `BLOCK_KEYS` / `BLOCK_MANUAL`）——
理由（SSOT 沒有那三個 key、本批不得新增 key）寫在被測檔的模組 docstring。
:func:`test_the_two_ssot_block_names_are_not_hand_copies` 只釘住**那兩個確實有 key 的**
不准被改成手抄字面；**其餘三個本檔只比對線框字面**，沒有 SSOT 可比。

⚠️ **`BLOCK_MANUAL`（「使用手冊」）與 `section_label("manual")`（「📖 說明書」）
並存，是一個尚未裁決的第二份真相源** —— 被測檔已就地登記並回報總管。
本檔:func:`test_the_manual_name_collision_is_still_registered` **把這個狀態釘住**：
哪天 SSOT 那一格被改成線框字面（＝正解落地），那條會轉紅，提醒人回來收掉這份登記。
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
    NAV_DETAIL_LABEL,
    NAV_GATE_LABEL,
    POINTS_UNIT,
    SPAN_PHRASE,
    SUBMIT_LABEL,
    _DEFAULT_ONLY_MISSING,
    _DEFAULT_SOURCE_CSV,
    _DEFAULT_SOURCE_REFETCH,
    _EMPTY_TITLE,
    _LABEL_ONLY_MISSING,
    _LABEL_SOURCE_CSV,
    _LABEL_SOURCE_REFETCH,
    _NOT_LOADED_NOTE,
    _PENDING_NOTE,
    _SK_APPLIED,
    _applied_request,
    _holdings,
    _normalise_request,
    _pending_where,
    coverage_headline,
    coverage_line,
    coverage_lines,
    nav_manual_label,
    nav_status_label,
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
#:    這份 fixture 把那個差異變成一條會轉紅的斷言，而不是一句註解。
FAKE_HOLDINGS: list[dict[str, Any]] = [
    {"code": "TESTCODE1", "name": "測試標的一", "loaded": True},
    {"code": "TESTCODE2", "name": "測試標的二", "loaded": False},
]


def _reset_streamlit_container_stack() -> None:
    """把 Streamlit 的「目前開著哪個容器」重設回乾淨狀態。

    **為什麼需要這個 —— 這不是儀式，是實測出來的跨檔污染（2026-09-05）。**
    完整機制（逐行讀 streamlit 原始碼 + 實跑確認）逐字寫在
    `tests/test_wf04_portfolio_skeleton.py::_reset_streamlit_container_stack`，
    **這裡不重抄一份**（抄了就是第二份會各自漂移的說明）。一句話版本：

    `st.form()` 會把 form 標記蓋在**行程層級的單例** `st._main` 上、離開 `with` 不還原；
    bare 模式下 `form_utils._current_form()` 第一行是 ``if not runtime.exists(): return None``
    所以**看不見**、什麼都不會炸；**到 `AppTest` 底下有 runtime 才引爆** ——
    下一個 `st.form(` 當場拋 `Forms cannot be nested in other forms.`

    ⚠️ **本頁有 Form，所以一定會踩到這個。** 被測檔的
    `_render_backfill_form()` 走 `applied_form`，只要同一個 pytest 行程裡先跑過
    任何一個以 bare 模式渲染 form 的測試檔（例：`tests/test_wf01_detail_zone_order.py`），
    本檔的每一次 `AppTest` 都會掉進紅框。

    ⛔ **本函式只是把本檔隔離起來，沒有修掉那個病。** 真正的修法要動
    `ui/helpers/ia/gated_form.py` 或加一支共用 `conftest.py` 的 autouse fixture，
    **兩者都不在本批的檔案邊界內**（且 `ia/gated_form.py` 另有一批正在動），已具名回報總管。

    ⚠️ **刻意用 fail-loud 的寫法**（§1）：這裡碰的是 Streamlit 的私有名稱，
    哪天改名就會直接 `ImportError` / `AttributeError` 炸開，**不會**靜默跳過。
    靜默跳過等於這道隔離悄悄失效，而失效的樣子跟「本來就沒事」一模一樣。
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
    # 進場先洗乾淨：別人留下的 form 容器會讓本頁的 `applied_form` 當場炸掉。
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
        "整頁渲染時拋了未捕捉例外 —— 骨架連跑都跑不起來：\n"
        + "\n".join(str(_e.value) for _e in _at.exception))
    return _at


def _rerun(at: Any) -> Any:
    """把一個已經跑過的 `AppTest` 再跑一次（用於「按下去之後會怎樣」）。"""
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
    """
    _out: list[str] = []
    _ch = getattr(node, "children", None)
    if not isinstance(_ch, dict):
        return _out
    for _, _c in sorted(_ch.items()):
        _t = type(_c).__name__
        _v = getattr(_c, "value", None)
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


#: 一級區塊標題（`st.markdown("#### …")`）。
_L4_OPEN = re.compile(r"^\[Markdown\] #{4}\s+(.*)$")
#: 一張卡的標題 —— `ia.state_card()` 在灰態時畫的 `st.markdown(f"**{title}**")`。
_CARD_OPEN = re.compile(r"^\[Markdown\] \*\*(.+)\*\*$")
#: **空狀態**的標題 —— `ia.empty_state()` 畫的是**裸 HTML div**，不是 `**粗體**`。
#: ⚠️ **這一條是 ④ 沒有的**：④ 的空狀態在頁面層級（整頁只剩它），
#:    ⑤ 的空狀態在**單一區塊內**（D-2），所以它必須能被切成一個「單位」，
#:    否則它底下的字會被算進**前一個**單位，讓「每塊各自誠實」這條斷言失去邊界。
#: ⚠️ **一定要釘 `font-weight:600`**：`empty_state()` 的 **footer** 也是一個
#: `<div style='…'>`，不區分的話 footer 會被切成一個**假單位**，
#: 於是「空狀態恰好 1 個」那條會數到 2、且它底下的字會離開真正的空狀態單位。
#: （本組第一版就是這樣紅的，記在這裡不美化。）
_EMPTY_OPEN = re.compile(
    r"^\[Markdown\] <div style='[^']*font-weight:600[^']*'>(.+?)</div>$")
#: `st.expander` 的標題（使用手冊那一塊）。
#: ⚠️ 型別名是 `Expander`（實測 AppTest 的元素樹），**不是** `Expandable`。
_EXPANDER_OPEN = re.compile(r"^\[Expander\] (.+)$")


def _units(parts: tuple[str, ...] | list[str]) -> list[tuple[str, list[str]]]:
    """把渲染流切成**有序**的最小單位：一級段落／一張卡／一個空狀態／一個展開器。

    ⚠️ **粒度是「一張卡」，這是被 ② 的一次突變逼出來的，不是設計出來的。**
    `tests/test_wf02_health_skeleton.py::_units` 記著：初版只依 `#### 區塊名` 切段，
    突變「只拿掉其中一塊的灰態」**沒有轉紅** —— 因為同一段裡別張卡的 ⬜ 替它過關了。

    ⛔ **不要為了讓斷言好寫而把邊界往上收。** 邊界一寬，鄰居的字就會替你通過。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _m = (_L4_OPEN.match(_p) or _CARD_OPEN.match(_p)
              or _EMPTY_OPEN.match(_p) or _EXPANDER_OPEN.match(_p))
        if _m:
            _out.append((_m.group(1).strip(), []))
            continue
        if _out:
            _out[-1][1].append(_p)
    return _out


def _segments(parts: tuple[str, ...] | list[str]) -> dict[str, list[str]]:
    """`單位名 -> 該單位內的渲染紀錄`（:func:`_units` 的 dict 檢視）。

    ⚠️ **dict 會讓同名單位後者覆蓋前者** —— 那正是 ② 被紅隊打穿的繞道。
    本檔用 :func:`test_unit_names_are_unique` 把「不會有同名單位」變成一條**斷言**。
    """
    return {_k: _v for _k, _v in _units(parts)}


def _expected_units() -> tuple[str, ...]:
    """線框 Tab 05 由上而下的單位（**有基金時**）。

    **`NAV 累積狀態` 與 `手動補資料` 走 SSOT，不在這裡抄字面。**
    ⚠️ 「手動補資料」這幾個字在渲染流裡**出現兩次**（`#### 區塊標題` ＋ Form 內的
    `st.caption` 開頭），但**只有前者會被切成單位** —— `st.caption` 不符合
    :func:`_units` 的任何一條開頭樣式。故本 tuple 裡它仍是**一個**單位，
    且 :func:`test_unit_names_are_unique` 會在哪天真的變成兩個單位時轉紅。
    """
    return (BLOCK_HEALTH, nav_status_label(), BLOCK_KEYS,
            nav_manual_label(), BLOCK_MANUAL)


def _grey_units() -> tuple[str, ...]:
    """**每一個都要各自帶灰態**的三個單位（有基金時、gate 未勾）。

    ⚠️ `nav_manual_label()`（Form）不在這裡：它是本批**唯一真的做完**的一塊，
    由 :func:`test_the_form_block_is_not_grey` 反向守著。
    ⚠️ `BLOCK_MANUAL`（使用手冊）**也不在這裡**：D-1 判定它是**靜態文字不是灰態**，
    由 :func:`test_the_manual_is_static_text_not_a_grey_placeholder` 反向守著。

    ⚠️ **2026-09-06 起 `nav_status_label()` 的灰態意思變了**（P05-1 接上取數）：
    它**不再**是「這一塊的內容還沒接上」，而是「**gate 沒勾，所以還沒去讀**」——
    兩者的**指路不同**（前者指手動補資料、後者指 gate 自己就在旁邊），
    所以 :data:`_GREY_POINTER` 把「哪一塊該指哪裡」寫成表，不再假設三塊共用一句。
    ⛔ 這一塊**只在 gate 未勾時**是灰的；勾起來之後它有四種狀態，
    由 :func:`test_the_nav_block_has_exactly_one_state_at_a_time` 等條守。
    """
    return (BLOCK_HEALTH, nav_status_label(), BLOCK_KEYS)


def _GREY_POINTER() -> dict[str, str]:
    """`灰態單位 -> 它應該帶的那一句指路`。

    ⛔ **不要退回「三塊共用一句」** —— 那正是把 NAV 那一塊的指路指錯的方法：
    它的下一步是**勾旁邊那個 gate**，不是去手動補資料。
    """
    return {
        BLOCK_HEALTH: _pending_where(nav_manual_label()),
        BLOCK_KEYS: _pending_where(nav_manual_label()),
        # gate 未勾 → 下一步就在同一張卡上（勾它）。指到自己這一塊是**有效**的指路。
        nav_status_label(): _pending_where(nav_status_label()),
    }


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
# 骨架：五個單位都在、順序對、名字唯一
# ══════════════════════════════════════════════════════════════════

def test_all_units_are_present_and_in_wireframe_order():
    """線框 Tab 05 由上而下：健康度 → NAV → 金鑰 → 手動補資料 → 使用手冊。

    ⚠️ 用 `loaded` 這個形狀跑 —— 沒有基金時 NAV 那一塊會換成空狀態
    （標題不同，D-2），那條由 :func:`test_the_nav_block_is_the_only_one_that_can_be_empty` 守。
    """
    _got = [_n for _n, _ in _units(_stream("loaded"))]
    _want = list(_expected_units())
    _idx = [_got.index(_u) for _u in _want if _u in _got]
    _missing = [_u for _u in _want if _u not in _got]
    assert not _missing, (
        f"線框 Tab 05 的單位少了：{_missing}\n實際渲染順序：{_got}")
    assert _idx == sorted(_idx), (
        f"單位順序與線框不符。\n線框：{_want}\n實際：{_got}")


def test_unit_names_are_unique():
    """單位名不得重複 —— 否則 :func:`_segments` 會讓後者悄悄覆蓋前者。

    ⚠️ 這條是 ② 被紅隊打穿之後才加的：`_segments` 是 dict，同名單位會互相蓋掉，
    於是「每一塊都要各自誠實」那條斷言就少驗了一塊，**而且不會有任何人發現**。
    """
    _names = [_n for _n, _ in _units(_stream("loaded"))]
    _dupes = sorted({_n for _n in _names if _names.count(_n) > 1})
    assert not _dupes, (
        f"有同名單位 {_dupes} —— `_segments()` 會讓後者覆蓋前者，"
        "使「每一塊各自誠實」這條斷言少驗掉一塊。")


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_the_page_renders_in_every_session_shape(kind: str):
    """三種 session 形狀都要能跑完，而且**四個非 NAV 單位一個都不少**。

    ⚠️ 這條釘的是 **D-2 的另一半**：⑤ **沒有**頁面層級空狀態 ——
    沒有基金時，健康度／金鑰／手動補資料／使用手冊**照樣要在**。
    ⛔ 若哪天有人照抄 ④ 的做法在 ⑤ 加一個「沒持倉就整頁只剩空狀態」，這條會轉紅。
    """
    _names = [_n for _n, _ in _units(_stream(kind))]
    for _u in (BLOCK_HEALTH, BLOCK_KEYS, nav_manual_label(), BLOCK_MANUAL):
        assert _u in _names, (
            f"（{kind}）單位「{_u}」不見了 —— ⑤ 沒有頁面層級空狀態（D-2）：\n"
            f"沒有基金時，除了 NAV 那一塊以外都該照常渲染。\n實際：{_names}")


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
    _empty = [_m.group(1).strip() for _p in _stream(kind) if (_m := _EMPTY_OPEN.match(_p))]
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
    _seen["是空的"] = bool([_p for _p in _parts if _EMPTY_OPEN.match(_p)])
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
    assert coverage_headline(FAKE_COVERAGE) == (
        f"{len(FAKE_COVERAGE)} 檔 · 共 "
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
    """「逐檔可展開」**只在真的有逐檔可展開時才畫**（鐵則 04：不畫空的占位）。"""
    _with_data, _ = _run_gated(BACKEND_ON, FAKE_COVERAGE, funds=FAKE_HOLDINGS)
    assert NAV_DETAIL_LABEL in [_n for _n, _ in _units(_with_data)], (
        f"有資料卻沒有「{NAV_DETAIL_LABEL}」展開器。")
    for _label, _backend, _cov in (
            ("gate 未勾", BACKEND_ON, FAKE_COVERAGE),
            ("後端未啟用", BACKEND_OFF, FAKE_COVERAGE),
            ("讀到空", BACKEND_ON, {})):
        _parts, _ = _run_gated(_backend, _cov, funds=FAKE_HOLDINGS,
                               open_gate=_label != "gate 未勾")
        assert NAV_DETAIL_LABEL not in [_n for _n, _ in _units(_parts)], (
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
    assert not [_p for _p in _off if _EMPTY_OPEN.match(_p)], (
        "後端未啟用卻走了空狀態 —— 「看不到」被講成「看到了、是空的」。")

    _on_empty, _ = _run_gated(BACKEND_ON, {}, funds=FAKE_HOLDINGS)
    _titles = [_m.group(1).strip() for _p in _on_empty if (_m := _EMPTY_OPEN.match(_p))]
    assert _titles == [_EMPTY_TITLE], (
        f"讀成功且一筆都沒有時，空狀態應恰好 1 個且是那一句：{_titles}")

    _on_data, _ = _run_gated(BACKEND_ON, FAKE_COVERAGE, funds=FAKE_HOLDINGS)
    assert not [_p for _p in _on_data if _EMPTY_OPEN.match(_p)], (
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
    _titles = [_m.group(1).strip() for _p in _parts if (_m := _EMPTY_OPEN.match(_p))]
    assert len(_titles) == 1, f"空狀態單位應恰好 1 個：{_titles}"
    _body = _text(_segments(_parts).get(_titles[0], []))
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
    _titles = [_m.group(1).strip() for _p in _parts if (_m := _EMPTY_OPEN.match(_p))]
    _body = _text(_segments(_parts).get(_titles[0], []))
    assert _pending_where(nav_manual_label()) in _body, (
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
    _empty_names = {_m.group(1).strip() for _p in _parts if (_m := _EMPTY_OPEN.match(_p))}
    assert _empty_names, "讀成功且沒有資料時應該要有空狀態。"
    _seg = _segments(_parts)
    for _name in _empty_names:
        assert _PENDING_NOTE not in _text(_seg.get(_name, [])), (
            f"空狀態單位「{_name}」裡混進了「還沒接上」那句 —— "
            "兩種灰的下一步不同，一次只給一個。")


# ══════════════════════════════════════════════════════════════════
# 灰態：三塊各自誠實灰；Form 不灰；使用手冊不是灰態（D-1）
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("unit", _grey_units())
def test_every_grey_unit_is_grey_until_its_content_lands(unit: str):
    """三個灰態單位**各自**要有 ⬜ —— 不准靠鄰居的灰字過關。

    ⚠️ 粒度是「一張卡」（見 :func:`_units`）。若哪天真內容接上了，這條會轉紅 ——
    **那是預期的**，屆時請把它改成「真內容放行」，不要把它放寬。
    """
    _body = _segments(_stream("loaded")).get(unit)
    assert _body is not None, f"單位「{unit}」根本沒出現在渲染流裡。"
    assert any(NOT_READY_MARK in _p for _p in _body), (
        f"單位「{unit}」沒有自己的灰態記號 {NOT_READY_MARK!r} —— "
        "本批這一塊還沒接線，就必須誠實說出來（§1），不得留白也不得靠鄰居的灰字。")


@pytest.mark.parametrize("unit", _grey_units())
def test_every_grey_unit_says_where_to_look(unit: str):
    """每個灰態單位都要帶「去哪補」—— 沒有它，占位只是把「消失」換成「灰色的消失」。"""
    _body = _text(_segments(_stream("loaded")).get(unit, []))
    _want = _GREY_POINTER()[unit]
    assert _want in _body, (
        f"單位「{unit}」的灰態沒有帶它該帶的那一句指路 {_want!r}。\n"
        "線框 §02：這是最容易省掉、也最有價值的一項。\n"
        "⚠️ 三塊的指路**不一樣**（見 `_GREY_POINTER`）—— "
        "NAV 那一塊的下一步是勾同一張卡上的 gate，不是去手動補資料。\n"
        f"{_body}")


def test_the_form_block_is_not_grey():
    """手動補資料是本批**唯一做完**的一塊 —— 它不准是灰態。

    ⚠️ 這條是 :func:`test_every_grey_unit_is_grey_until_its_content_lands` 的反向守衛：
    把 Form 那一塊做壞成灰態（或整塊拿掉換成灰字），這條會轉紅。
    """
    _body = _text(_segments(_stream("loaded")).get(nav_manual_label(), []))
    assert _body, f"「{nav_manual_label()}」單位是空的 —— Form 沒有渲染出來。"
    assert NOT_READY_MARK not in _body, (
        f"「{nav_manual_label()}」被畫成灰態了 —— 它是本批唯一真的做完的一塊。")


def test_the_manual_is_static_text_not_a_grey_placeholder():
    """⭐ **D-1**：使用手冊那張卡的 `dim` **不是灰態**，不准畫成未載入佔位。

    **依據**（`grep -n 'dim' docs/wireframes/ia-wireframe.html`，全檔僅 5 個命中）：
    `:193/:198` 是 CSS；`:379` 與 `:552` 兩張 `card dim` **都帶 `灰態` chip**；
    **`:706` 使用手冊那張沒有 `灰態` chip**，內文寫「**純文字**」。
    → `dim` 在這份線框裡承擔**兩種**意思；使用手冊那張是**視覺降權**，
    **不是「還沒接上」**。

    ⛔ 它是**現在就能出的靜態文字**，畫成「未載入」是對使用者說一句**假話**（§1）——
    而且是在這一頁上：本頁的職責就是回答「資料可不可信」。

    ⚠️ **這條守的是「它沒有 ⬜」，不守「它的內容是對的」**（後者見
    :func:`test_the_manual_lists_exactly_the_wireframe_three`）。
    """
    for _kind in ("empty", "missing", "loaded"):
        _body = _text(_segments(_stream(_kind)).get(BLOCK_MANUAL, []))
        assert _body, f"（{_kind}）「{BLOCK_MANUAL}」單位是空的。"
        assert NOT_READY_MARK not in _body, (
            f"（{_kind}）「{BLOCK_MANUAL}」被畫成灰態了 —— D-1：線框那張卡的 `dim` "
            "**沒有** `灰態` chip，它是視覺降權不是「還沒接上」。"
            "把現在就能出的靜態文字畫成「未載入」是說謊（§1）。")


#: 線框 Tab 05 使用手冊那張卡逐字列的三項。**目錄就是全部內容，多一項都不行。**
_MANUAL_ITEMS: frozenset = frozenset({"指標定義", "門檻由來", "常見誤讀"})
#: 抓 markdown 目錄項 `- **X**`。
#: ⚠️ **`\[Markdown\] ` 這個可選前綴不能省**：`_flat()` 把整個 `st.markdown` 區塊
#:    記成**一行** `[Markdown] - **指標定義**\n- **門檻由來**\n…`，
#:    所以**第一項**的行首是 `[Markdown] `、不是 `-`。少了這個前綴，
#:    第一項會被漏掉 —— 本組第一版就是這樣，被自己的集合相等當場抓出來
#:    （`少了：['指標定義']`）。**這正是「只驗有沒有」看不到、「集合相等」才看得到的那種錯。**
#: ⛔ **項目符號要吃 `-` / `*` / `+` / `1.` / `1)` 五種**（2026-09-06 補）：
#: 原本只認 `-`，於是多列一項寫成 `1. **投資建議**` → **50 passed 三序**，
#: **集合相等整個看不見它**。那正是本條要擋的「多列一項＝自己發明規格」。
#: ⚠️ **仍守不到**：`<li>` 之類的裸 HTML、以及不帶 `**粗體**` 的寫法。
_MANUAL_ITEM_RE = re.compile(
    r"^(?:\[Markdown\] )?(?:[-*+]|\d+[.)])\s+\*\*(.+?)\*\*\s*$", re.M)


def test_the_manual_lists_exactly_the_wireframe_three():
    """使用手冊只列線框逐字的三項目錄 —— **不准編一段內文充數，也不准多列**。

    線框逐字：「指標定義、門檻由來、常見誤讀。純文字，不佔首屏。」
    ⛔ 在一份**專門用來解釋門檻由來**的文件裡編內容，是最壞的一種造假（§1）。

    ⛔ **2026-09-05 獨立稽核必修 —— 本條名字裡的 `exactly` 原本是假的。**
    舊版只做 `for _item in (三個): assert _item in _body`，**只驗有沒有，不驗有沒有多**。
    兩顆突變因此全數存活（三序一致）：
    把 caption 換成編造的「指標定義：**Sharpe 大於 1 就是好基金**；門檻由來：**業界共識**。」
    → **47 passed**；目錄多列「**投資建議**」「**保證報酬**」→ **47 passed**。
    **一條 docstring 明寫「不准編一段內文充數」的守衛，放行了一段編出來的內文。**
    現行改**集合相等**。

    ⛔ **2026-09-06 更正：上一行原寫「集合相等，**兩顆一起擋掉**」—— 那句是假的，
    而且它自己三行後就寫著「caption 本條看不到」，前後自相矛盾。**
    集合相等做在 :data:`_MANUAL_ITEM_RE` 撈出來的**目錄項集合**上，
    **結構上看不見 caption**。三序重測（`-p no:randomly` ＋ seed 101 ＋ seed 20260906）：
    - 目錄多列「投資建議」「保證報酬」→ **1 failed**（✅ 這一顆確實擋掉了）；
    - caption 換成編造的「指標定義：Sharpe 大於 1 就是好基金；門檻由來：業界共識。」
      → **50 passed**（❌ **這一顆沒擋到，從頭到現在都沒有**）。
    **實際是擋掉一顆、放行一顆。**

    ⚠️ **仍然守不到**：目錄項以外的地方（例如 caption）寫了什麼，本條看不到。
    ⛔ **2026-09-06 更正：原寫「那由 `test_no_grey_unit_states_a_conclusion` 的字表
    「部分」涵蓋」—— 那也是假的，實際是【完全不涵蓋】。**
    根因：那條守衛的迴圈開頭是 `if NOT_READY_MARK not in _joined: continue`，
    而**使用手冊這一塊刻意不畫成灰態**（D-1：`dim` 是視覺降權、不是灰態）→
    **沒有 ⬜ → 整個單位直接被跳過**。三序實測：把該字表的四個詞全塞進手冊的 caption
    → **50 passed**。**覆蓋率是 0，不是「部分」。**
    → 也就是說：**使用手冊的 caption 目前沒有任何守衛在看**，
    而這是一份**專門用來解釋門檻由來**的文件。**登記在此，不是沒看到。**
    """
    _body = _text(_segments(_stream("loaded")).get(BLOCK_MANUAL, []))
    _got = set(_MANUAL_ITEM_RE.findall(_body))
    assert _got == _MANUAL_ITEMS, (
        f"使用手冊的目錄項與線框不符。\n線框：{sorted(_MANUAL_ITEMS)}\n"
        f"實際：{sorted(_got)}\n"
        f"少了：{sorted(_MANUAL_ITEMS - _got)}／多了：{sorted(_got - _MANUAL_ITEMS)}\n"
        "⛔ 多列一項就是自己發明規格；在一份專門解釋門檻由來的文件裡編內容，"
        "是最壞的一種造假（§1）。")


#: 灰態單位內**不准出現的結論性字眼**。⚠️ **這是黑名單，抓不到名單外的第 N+1 個。**
#: 存在的理由：`state_card(state=STATE_NOT_READY)` 無條件前綴 ⬜，而
#: :func:`test_every_grey_unit_is_grey_until_its_content_lands` 只查「有沒有 ⬜」——
#: **⬜ 之後接什麼都行**。2026-09-05 稽核用四顆突變證明了這個縫
#: （「你的資料全部正常，沒有任何異常」等，全部存活）。
#: ⚠️ **2026-09-06：裸「正常」補進來了** —— 在此之前這個字表**八個都是片語**，
#: 於是在灰卡的同一單位內印 `st.caption("18 個來源目前狀態：正常")` → **50 passed 三序**。
#: **那一格當時沒有任何人守著**，而模組 docstring 與 D-3 那條都寫著「由本條守」。
#: ⚠️ **本 repo 對「正常」有兩份不同的政策，不要混為一談**：
#:   - :data:`_PINNED_FAKE_VALUES` 是**全頁**黑名單 → 「正常」**仍然不收**（釘它會把
#:     任何一句合法說明打紅，那個理由今天依然成立）；
#:   - 本字表只掃**帶 ⬜ 的灰態單位** → 射程窄得多，收得起。
#: ⛔ **代價是真的，實測記在這裡**：灰卡若要寫一句合法說明如
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
        for _unit, _body in _units(_stream(_kind)):
            _joined = _text(_body)
            if NOT_READY_MARK not in _joined:
                continue
            for _w in _CONCLUSION_WORDS:
                assert _w not in _joined, (
                    f"（{_kind}）灰態單位「{_unit}」裡出現了結論性字眼 {_w!r}：\n"
                    f"{_joined}\n"
                    "⛔ 這一塊還沒接線，我們沒有查過任何來源 —— "
                    "說「正常」是憑空捏造一個系統健康狀態的結論（§1）。")


# ⛔ **`test_the_empty_state_never_claims_the_user_has_no_funds` 與其 helper
#    `_check_empty_state_is_honest` 已於 2026-09-06（P05-1）整段移除，取代品是
#    :func:`test_the_empty_state_only_appears_after_a_successful_read` ＋
#    :func:`test_the_empty_state_asserts_nothing_about_the_users_funds`。**
#
#    **這是有意識的替換，不是把一條客戶紅線的守衛刪掉，理由請讀完再動它：**
#    舊條有兩半 —— (a) 說謊黑名單、(b) 「文案必須帶『這個 session / 已載入』這種限定詞」。
#    - **(a) 原封保留**（黑名單搬進 `..._asserts_nothing_about_the_users_funds`，
#      而且**多收了兩個**：「你的基金」「你沒有累積」）。
#    - **(b) 必須拿掉，因為它在新行為下會強迫產生一句假話**：那個限定詞存在的唯一理由是
#      「**我們那時根本沒讀過雲端**，只知道這個 session 沒載入」。P05-1 之後空狀態
#      **只在真的讀成功之後**才出現 —— 這時再寫「這個 session 還沒載入」是錯的，
#      事實是「**那張表真的是空的**」。
#    - **承重的保護不是搬走而是換成更強的**：`..._only_appears_after_a_successful_read`
#      是**結構性**的（未啟用 → 0 個空狀態；讀到空 → 恰好 1 個；讀到有資料 → 0 個），
#      它管的是「這句話有沒有資格被說出口」，比「這句話裡有沒有某個詞」上游。
#    ⚠️ **據實登記代價**：舊條會擋下「空狀態文案裡出現名單外的第 N+1 種說法」的機率
#      **沒有變好也沒有變差**（黑名單本來就抓不到）；真正變掉的是
#      **舊條那半條結構性要求（兩半各自都要帶限定詞）不再存在**。
#      新條的結構性要求換成了「只有讀成功才到得了空狀態」——**不是同一件事**，
#      只是本組判斷它在新行為下更貼題。**這是判斷，不是量出來的。**


def test_pressing_submit_says_the_backfill_is_not_wired_yet():
    """⭐ 按下「開始補抓」之後，畫面**必須說出**「實際補抓還沒接上」。

    ⛔ **2026-09-05 獨立稽核應修。** 在補上之前：勾選 → 按鈕 → rerun，
    **整頁一個字都沒變**，只有 session 靜靜寫入；而畫面上寫著
    「勾選的當下不會發生任何事，按『開始補抓』**才算**」，
    另外三塊都誠實掛著 ⬜「這一塊的內容還沒接上」，**唯獨這一塊沒有** ——
    而它是唯一一個帶**動作動詞**、看起來會寫資料的。

    ⚠️ 「不接真寫入」這個取捨本身是對的（一個按了會真的寫的鈕，接在還沒驗過的骨架上
    更危險）；**錯的是不說**。「看起來會寫、其實不寫、而且不說」在一個職責是
    「資料可不可信」的頁面上，比多一句話糟得多（§1）。
    """
    _at = _app(FAKE_HOLDINGS)
    # ⚠️ **依標籤取，不用索引**（2026-09-06）：接上 NAV gate 之後 `checkbox[0]` 是 gate，
    #    照舊寫法會勾錯框、然後測出一個假的結論。見 :func:`_cb`。
    _cb(_at, _LABEL_SOURCE_CSV).check()
    _at.button[0].click()
    _rerun(_at)
    _all = _text(_flat(_at.main))
    assert "尚未接上" in _all or "還沒接上" in _all, (
        "按下送出之後，畫面上沒有任何一句說明「實際補抓還沒接上」：\n" + _all)
    assert "已記下" in _all, (
        "按下送出之後，畫面上沒有告訴使用者「選擇已被記下」——\n"
        "一個按了完全沒有回饋的鈕，使用者只會再按一次。\n" + _all)


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


# ══════════════════════════════════════════════════════════════════
# 鐵則 02：寫入類動作全部 Form 封裝
# ══════════════════════════════════════════════════════════════════

#: 會產生使用者輸入的 widget —— 線框那句「寫入類動作，**全部 Form 封裝**」管的就是這些。
#: ⚠️ 這是**白名單，不是窮舉**：Streamlit 新增的輸入元件不會自動進來。
_INPUT_WIDGETS: frozenset = frozenset({
    "checkbox", "toggle", "slider", "select_slider", "number_input",
    "text_input", "text_area", "selectbox", "multiselect", "radio",
    "date_input", "time_input", "file_uploader", "color_picker", "camera_input",
})


def _applied_form_with() -> ast.With | None:
    """回傳包住 `applied_form(...)` 的那個 `ast.With`；沒有就回 `None`。"""
    for _n in ast.walk(_tree()):
        if isinstance(_n, ast.With):
            for _it in _n.items:
                _c = _it.context_expr
                if (isinstance(_c, ast.Call)
                        and _dotted(_c.func).endswith("applied_form")):
                    return _n
    return None


def _input_widget_calls(tree: ast.AST) -> list[ast.Call]:
    """檔內所有 `st.<輸入元件>(...)` 呼叫。"""
    return [_n for _n in ast.walk(tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in _INPUT_WIDGETS]


#: **唯讀閘門**：可以把輸入元件放在 `applied_form(...)` 之外的函式。
#:
#: ⚠️ **2026-09-06（P05-1）新增的豁免，理由與它的證明一起寫在這裡。**
#: 線框那句粗體管的是「**寫入類**動作，全部 Form 封裝」。
#: NAV 累積狀態的 Checkbox Gate **不是寫入類** —— 它是一個
#: 「**要不要去讀一次**」的唯讀開關，作用**恰好相反**：把一次 Google Sheets 往返
#: 擋在點擊之後。把它塞進補資料的 form 裡，使用者就得**按下「開始補抓」才能看涵蓋度**，
#: 那是把一個唯讀動作綁在一個寫入鈕上。
#:
#: ⛔ **豁免不是憑一句話成立的，它有機器證明**（見
#: :func:`test_the_read_only_gate_really_is_read_only`）：名單上的函式必須
#: **真的存在**、**一個 session 都不寫**、**不呼叫任何寫入類 L2 入口**、
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


def test_the_write_block_is_form_wrapped():
    """⭐ 線框**唯一**用粗體寫的硬要求：「寫入類動作，**全部 Form 封裝**」。

    ⛔ **2026-09-05 獨立稽核必修 —— 本條原本形同虛設，這段病史請留著。**
    舊版斷言是 `len(_at.button) >= 1` ＋ `SUBMIT_LABEL in _labels`，
    docstring 還宣稱「驗的是**畫面上真的有一個 form 送出鈕**」。
    **那句宣稱做不到**：`AppTest` **沒有 `.form` 屬性**（實測 `hasattr(AppTest, "form")` → `False`），
    form 的送出鈕在元素樹裡就是一顆普通 `Button`、form 本體是一個無標記 `Block` ——
    **`at.button` 兩者皆收**，所以那兩條斷言**對一顆裸 `st.button` 恆真**。
    稽核把 `with applied_form(...) as _gate:` 換成 `if True: _gate = st.button(SUBMIT_LABEL)`，
    **本地 47 passed、六支全域守衛 467 passed —— 一條都沒紅。**

    ⛔ **全域也補不到這個洞**：`tests/test_ui_rerun_contract.py` 的 `FORM_SITE_TOTAL`
    數的是 **raw `st.form(` 站點**，而 ⑤ 走共用 `applied_form()`，**本身不貢獻任何 form 站點**；
    `git grep applied_form -- tests/` 顯示**沒有任何守衛在數 `applied_form()` 的呼叫點**。
    （repo 自己在 `FORM_SITES` 的註解裡預言過這件事，但沒補。**五分頁族全部走
    `applied_form`，所以這個洞不只是 ⑤ 的** —— 全域版須另批處理，見 PR 描述的登記。）

    **現行做法：AST，不看渲染結果。**
    (1) 頁面**必須**有一個包住 `applied_form(...)` 的 `with`；
    (2) 檔內**每一個**輸入元件呼叫都必須落在那個 `with` 的 body 行區間內。
    → 把 `applied_form` 換成裸 `st.button`，(1) 當場失敗。
    → 把某個 checkbox 搬到 form 外面，(2) 當場失敗。

    ⚠️ **本條守不到的**：`_INPUT_WIDGETS` 是白名單，Streamlit 新增的輸入元件不會自動進來；
    以及 `getattr(st, "checkbox")(...)` 這種非字面呼叫（同本檔其他 AST 條的既有限制）。

    ⛔ **2026-09-06 補登記：本條會把一個【合法且自然】的重構打紅。**
    :func:`_input_widget_calls` **全檔**掃 `st.<widget>` 並用 `lineno` 判斷落不落在
    那個 `with` 的行區間內 —— **它不看呼叫關係**。所以把 CSV 那顆 checkbox 抽成
    module 層 helper `_csv_box()`、再於 form 內呼叫（**行為完全相同、widget 仍在
    form 裡渲染**）→ **1 failed 三序一致**，因為 helper 的 `def` 在 `with` 之外。
    ⚠️ **下一批接真內容時，把 widget 抽成 helper 是最自然的一步** ——
    屆時錯誤訊息會寫「**有輸入元件落在 form 之外**」，而**那句話是錯的**；
    而且**消紅最省事的做法是把 helper 內聯回去** —— 也就是
    **這條守衛會把人推向比較差的寫法**。碰到時請改守衛（例如改判「呼叫點是否在
    form body 內」而不是「def 在哪一行」），**不要為了消紅而放棄抽 helper**。
    ✅ **對「行號位移」本身不脆弱**：`_lo` / `_hi` 是從 AST 現算的，
    在 form 之前或之後插入任意行數都不會誤紅（本輪另兩顆突變已證）。

    ⚠️ **另一個誤紅來源（2026-09-06 補登記，機率低但真的）**：
    :func:`_input_widget_calls` 只比對 `ast.Attribute` 的 **`.attr` 名字**，
    **不看那個物件是不是 `st`** —— 所以任何**非 streamlit** 物件呼叫同名方法
    （`_cfg.checkbox(...)` / `_form.radio(...)`）落在 form 外，也會被判成
    「輸入元件在 form 之外」。三序實測：在 form 外加一行 `_CFG.checkbox("x")`
    → **1 failed**。**登記，不是沒看到。**
    """
    _with = _applied_form_with()
    assert _with is not None, (
        "頁面沒有任何包住 `applied_form(...)` 的 `with` —— "
        "線框粗體要求「寫入類動作，全部 Form 封裝」。\n"
        "⚠️ 換成裸 `st.button` 是渲染層看不出來的（AppTest 沒有 `.form`），"
        "所以這條必須走 AST。")
    _tree_ = _tree()
    _lo = min(_st.lineno for _st in _with.body)
    _hi = max(getattr(_st, "end_lineno", _st.lineno) for _st in _with.body)
    _gate_ranges = _read_only_gate_ranges(_tree_)
    _outside = [
        f"L{_c.lineno} st.{_c.func.attr}(…)"
        for _c in _input_widget_calls(_tree_)
        if not (_lo <= _c.lineno <= _hi)
        and not any(_a <= _c.lineno <= _b for _a, _b in _gate_ranges)]
    assert not _outside, (
        f"有輸入元件落在 `applied_form(...)` 的 `with` 之外：{_outside}\n"
        f"（form body 行區間 = {_lo}~{_hi}；唯讀閘門豁免區間 = {_gate_ranges}）\n"
        "線框粗體：「寫入類動作，**全部 Form 封裝**」—— form 外的 widget "
        "每動一下就觸發一次 rerun，那正是鐵則 02 要買掉的成本。\n"
        f"⚠️ 唯讀閘門的豁免名單是 {sorted(READ_ONLY_GATE_FUNCS)}，"
        "而且**要通過 `test_the_read_only_gate_really_is_read_only` 的證明**才算數。")
    # 送出鈕的字仍然要對得上（這一條**恆真**，見 PR 描述的登記 10：
    # 測試 import 的就是頁面同一個常數，改字不可能紅；它的價值只有
    # 「鈕沒用到那個常數」這一種死法）。
    _at = _app(FAKE_HOLDINGS)
    assert SUBMIT_LABEL in [_b.label for _b in _at.button], (
        f"畫面上找不到字為 {SUBMIT_LABEL!r} 的送出鈕：{[_b.label for _b in _at.button]}")


def test_the_three_fields_are_present_and_default_to_doing_nothing():
    """三個欄位都在，而且**兩個來源預設都不勾**。

    ⛔ **這是寫入類動作**：預設勾好等於使用者一按鈕就寫了他沒想寫的東西。
    ⚠️ 「只補有缺口的檔」預設**勾選**是同一個原則的另一面 ——
       它是**縮小**寫入範圍的開關，預設縮小同樣是「不做事的那一邊」。
    """
    _all = _text(_stream("loaded"))
    for _lbl in (_LABEL_SOURCE_CSV, _LABEL_SOURCE_REFETCH, _LABEL_ONLY_MISSING):
        assert _lbl in _all, f"Form 少了欄位「{_lbl}」。"
    assert _DEFAULT_SOURCE_CSV is False and _DEFAULT_SOURCE_REFETCH is False, (
        "兩個**來源**欄位的預設值必須是「不勾」—— 這是寫入類動作，"
        "預設勾好等於使用者一按鈕就寫了他沒想寫的東西。")
    assert _DEFAULT_ONLY_MISSING is True, (
        "「只補有缺口的檔」預設應為勾選 —— 它是縮小寫入範圍的開關，"
        "預設縮小同樣是「不做事的那一邊」。")


def test_pressing_submit_with_no_source_never_counts_as_a_request():
    """兩個來源都沒勾就按送出 → **不算一次已送出的請求**。

    「按了鈕」不等於「有事要做」（同 ④「可動用金額 0 不算試算」）。
    ⛔ 若這裡放行，下一批接上真寫入時，一次誤觸就會跑一輪全站補抓。
    """
    _at = _app(FAKE_HOLDINGS)
    _at.button[0].click()
    _rerun(_at)
    # ⚠️ `AppTest.session_state` 是 `SafeSessionState`，**沒有 `.get()`**
    #    （`__getattr__` 會把 `get` 當成一個 key 去查，然後 `AttributeError`）。
    #    用 `in` + `[]`，不要照抄一般 dict 的寫法。
    assert _SK_APPLIED not in _at.session_state, (
        "兩個來源都沒勾卻記下了一次補資料請求 —— "
        f"session[{_SK_APPLIED!r}] = {_at.session_state[_SK_APPLIED]!r}")


def test_pressing_submit_with_a_source_records_the_applied_request():
    """勾了來源再送出 → 請求**被記下來**，而且形狀是 `_normalise_request` 那個。

    ⚠️ 這條與上一條是一對：上一條防「按了就寫」，這條防「按了不寫」——
    只留其中一條，另一個方向就沒人守。
    """
    _at = _app(FAKE_HOLDINGS)
    # 勾一個來源、按送出，**同一次 run** —— 這才是使用者真的做的事
    #（form 內的 widget 值本來就要等送出才提交，中間不該多跑一輪）。
    _cb(_at, _LABEL_SOURCE_CSV).check()      # 依標籤，不用索引（見 `_cb`）
    _at.button[0].click()
    _rerun(_at)
    assert _SK_APPLIED in _at.session_state, (
        f"勾了來源並送出，卻沒有記下請求：session 裡沒有 {_SK_APPLIED!r}")
    _got = _at.session_state[_SK_APPLIED]
    assert isinstance(_got, dict), (
        f"已送出請求不是 dict：{_got!r}")
    assert set(_got) == set(_normalise_request(True, False, True)), (
        f"已送出請求的形狀與 `_normalise_request()` 不一致：{_got!r}")


def test_normalise_request_coerces_to_bool():
    """`_normalise_request()` 一律吐 `bool` —— 不把 widget 的原始值直接存進 session。"""
    _got = _normalise_request("yes", 0, None)
    assert _got == {"csv_import": True, "refetch": False, "only_missing": False}, _got
    assert all(isinstance(_v, bool) for _v in _got.values()), _got


def test_applied_request_ignores_a_corrupted_session_value():
    """session 裡被塞了非 dict → `_applied_request()` 回 `None`，不當成請求。"""
    import streamlit as _st
    try:
        _st.session_state[_SK_APPLIED] = "不是 dict"
        assert _applied_request() is None
    finally:
        # ⚠️ 一定要清掉：bare 模式的 session_state 是**行程層級**的，
        #    留著會污染同一個行程裡後面跑的測試（本檔與別檔皆然）。
        _st.session_state.pop(_SK_APPLIED, None)


# ══════════════════════════════════════════════════════════════════
# 邊界：走共用元件、不碰底層、不委派舊頁、不自己寫別人的 session
# ══════════════════════════════════════════════════════════════════

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


#: 本頁**唯一**准許 import 的 L2 service。
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


def test_the_page_does_not_delegate_to_the_old_tabs():
    """⛔ 不准 import 或委派線框「從哪裡搬來」列的四個舊檔。

    客戶方針：**打掉重練，不改舊 `tab*.py`** —— 委派過去等於把舊頁的行為
    原封搬進新頁，那不是重刻，是包一層。
    """
    _old = ("ui.tab5_data_guard", "ui.tab_manage", "ui.tab_settings_diag",
            "ui.tab6_manual")
    # ⚠️ `_m == _o or _m.startswith(_o + ".")` —— **點邊界不能省**（2026-09-05 稽核）：
    #    裸 `startswith` 會把 `ui.tab_manage_v2` / `ui.tab6_manual_helpers`
    #    這種**不同的模組**一起誤判成舊分頁。
    _bad = [_m for _m in _imported_modules(_tree())
            if any(_m == _o or _m.startswith(_o + ".") for _o in _old)]
    assert not _bad, (
        f"被測檔委派給了舊分頁：{_bad}\n線框「從哪裡搬來」的四個檔是**參考**，不是依賴。")


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

    📌 **另一組正在把這段共用實作收進 `tests/_ast_bindings.py`**
    （分支 `claude/fund-guard-ast-sn42bh`，本批**不得碰、也不得 import** —— 它還沒合併）。
    **共用 helper 合併後，本條應改為 import 它，不要留兩份**（`CLAUDE.md §2.1`）。
    本檔目前的寫法比照 `tests/test_wpg_portfolio_health_link_20260831.py`。
    """
    _tree_ = _tree()
    _allowed = {_SK_APPLIED}
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
                if _key not in {"_SK_APPLIED"} | {repr(_k) for _k in _allowed}:
                    _writes.append(f"L{_n.lineno} 下標賦值 {_dotted(_t)}")
            elif isinstance(_t, ast.Attribute) and "session_state" in _dotted(_t.value):
                _writes.append(f"L{_n.lineno} 屬性賦值 {_dotted(_t)}")
        if isinstance(_n, ast.Call):
            _d = _dotted(_n.func)
            if ("session_state" in _d
                    and _d.rsplit(".", 1)[-1] in ("update", "setdefault")):
                _writes.append(f"L{_n.lineno} {_d}(...)")
            # 形態 4：widget 帶 `key=` —— streamlit 會代為寫入 session_state。
            # ⚠️ `applied_form(_FORM_KEY, ...)` 不是 `st.` 開頭，不會命中（那是共用元件，
            #    它自己的 key 由 `ia/gated_form.py` 負責），這是刻意的射程。
            if _d.startswith("st.") and any(_k.arg == "key" for _k in _n.keywords):
                _writes.append(f"L{_n.lineno} widget key= → {_d}")
    assert _writes == [], (
        f"被測檔寫了自己命名空間以外的 session：{_writes}\n"
        f"本頁只准寫 {_SK_APPLIED!r}（`portfolio_funds` 是**別人定義**的鍵，只讀不寫）。\n"
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
# 指路：兩種灰，一種有效一種無效 —— 兩個方向都釘住
# ══════════════════════════════════════════════════════════════════

def test_the_pending_pointer_is_a_place_not_a_status_sentence():
    """`_pending_where()` 回傳的必須是一個**地方**（`分頁 → 區塊`）。

    `not_ready()` 會把它包成「（請先到：…）」—— 塞一句狀態陳述進去
    會產生一句**不可執行的指令**（③ 2026-09-05 被獨立紅隊實測抓到的錯）。
    """
    _got = _pending_where(nav_manual_label())
    assert _got == f"{where_to_find('settings')} → {nav_manual_label()}", _got
    assert "目前" not in _got and "只有" not in _got, (
        f"指路變成狀態陳述了：{_got!r}")


def test_the_pending_pointer_is_honest_about_being_ineffective():
    """❌ 「內容還沒接上」那種灰，指路**照著做也沒有用** —— 把它釘成斷言，不是形容詞。

    照著做（回到手動補資料、勾一個來源、按送出）→ **三條灰態逐字完全相同**。
    ⛔ **這不是 bug，是本批的實況**：這一塊沒接上，去任何地方都不會讓它出現。
    ✅ 哪天它真的變有效了（內容接上了），這條會**轉紅** ——
       而那正是要人回來改文案的時候。
    """
    _before = {_u: _text(_segments(_stream("loaded")).get(_u, []))
               for _u in _grey_units()}
    _at = _app(FAKE_HOLDINGS)
    _cb(_at, _LABEL_SOURCE_CSV).check()      # 依標籤，不用索引（見 `_cb`）
    _at.button[0].click()
    # ⚠️ **一定要跑兩次，這不是保險是必需**（2026-09-05 獨立稽核應修）：
    #    `render_settings_and_diagnostics()` 裡 `_render_grid()` 在**最前面**、
    #    Form 的送出處理（寫 `_SK_APPLIED`）在**最後面** ——
    #    也就是說，**任何吃 `_SK_APPLIED` 的內容都要到「下一次 run」才顯形**。
    #    只跑一次 `_rerun` 的話，本條承諾的「哪天真的變有效了會轉紅」**做不到**：
    #    稽核用一顆「讓灰卡吃 `_SK_APPLIED`」的突變實測，三種順序**全數存活**。
    _rerun(_at)
    _rerun(_at)
    _after_seg = _segments(_flat(_at.main))
    for _u in _grey_units():
        assert _text(_after_seg.get(_u, [])) == _before[_u], (
            f"照著指路做完之後，「{_u}」的灰態變了 —— "
            "本批這一塊沒接線，照理不該有任何變化。"
            "若是內容真的接上了，請改這條測試的預期（不要放寬它）。")


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
