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

⚠️ **本檔明確守不到的（照實列，不要用形容詞）**
-----------------------------------------------
- ⛔ **示意值黑名單只有 `_PINNED_FAKE_VALUES` 那幾個字面寫法。**
  裸數字（`18` / `42` 不帶單位字）、全形數字、換算成別的寫法、以及
  **任何線框以外的捏造值**都抓不到 —— 黑名單結構上抓不到名單外的第 N+1 個。
  ⚠️ 「正常」兩個字**刻意不進黑名單**：它是極常見的一般用詞，
  釘它會把往後任何一句合法說明打紅。**那一格改由「連線與金鑰必須是灰態」反向守**
  （:func:`test_every_grey_unit_is_grey_until_its_content_lands`）——
  一張灰卡不可能同時印一個「正常」的結論。
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
import functools
import pathlib
import re
from typing import Any

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
    SUBMIT_LABEL,
    _DEFAULT_ONLY_MISSING,
    _DEFAULT_SOURCE_CSV,
    _DEFAULT_SOURCE_REFETCH,
    _LABEL_ONLY_MISSING,
    _LABEL_SOURCE_CSV,
    _LABEL_SOURCE_REFETCH,
    _PENDING_NOTE,
    _SK_APPLIED,
    _applied_request,
    _holdings,
    _normalise_request,
    _pending_where,
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
    """**每一個都要各自帶灰態**的三個單位（有基金時）。

    ⚠️ `nav_manual_label()`（Form）不在這裡：它是本批**唯一真的做完**的一塊，
    由 :func:`test_the_form_block_is_not_grey` 反向守著。
    ⚠️ `BLOCK_MANUAL`（使用手冊）**也不在這裡**：D-1 判定它是**靜態文字不是灰態**，
    由 :func:`test_the_manual_is_static_text_not_a_grey_placeholder` 反向守著。
    """
    return (BLOCK_HEALTH, nav_status_label(), BLOCK_KEYS)


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
    本檔的兩個消費者都是 `startswith` / 取第一段的比對，多吐無害；
    **但它不是一份「真的 import 到的模組」清單，別拿去做別的用途。**
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

@pytest.mark.parametrize("kind", ["empty", "missing"])
def test_the_nav_block_is_the_only_one_that_can_be_empty(kind: str):
    """沒有基金時，**只有** NAV 那一塊走空狀態；其餘四塊不得出現空狀態。

    D-2：「資料來源健康度」「連線與金鑰」是**系統自己的狀態**，永遠有話可說；
    「手動補資料」是 Form、「使用手冊」是靜態文字 —— 都不會空。
    """
    _names = [_n for _n, _ in _units(_stream(kind))]
    assert nav_status_label() not in _names, (
        f"（{kind}）一檔基金都沒有，NAV 那一塊卻還印著「{nav_status_label()}」的灰卡 —— "
        "它應該走空狀態（D-2）。")
    # 空狀態標題是被測檔自己寫的一句話（不是 SSOT），這裡只驗「有一個空狀態單位」。
    _empty_titles = [_m.group(1).strip() for _p in _stream(kind)
                     if (_m := _EMPTY_OPEN.match(_p))]
    assert len(_empty_titles) == 1, (
        f"（{kind}）空狀態單位有 {len(_empty_titles)} 個，應該恰好 1 個"
        f"（只有 NAV 那一塊可能空）：{_empty_titles}")


def test_the_empty_state_pointer_actually_works():
    """空狀態的「去哪補」**照著做真的有效** —— 實跑，不是形容詞。

    照做（讓 `portfolio_funds` 有項目）→ 空狀態**真的消失**、NAV 灰卡**真的出現**。
    ⛔ 這條與 :func:`test_the_pending_pointer_is_honest_about_being_ineffective` 是一對：
       **本頁的兩種灰，一種指路有效、一種無效**，本檔把兩者都釘成會轉紅的斷言。
    """
    _before = _stream("missing")
    assert where_to_find("pf_add") in _text(_before), (
        "空狀態沒有指向 ④ 的「加入與管理基金」—— 那是唯一能讓它離開空狀態的地方。")
    _after = [_n for _n, _ in _units(_stream("loaded"))]
    assert nav_status_label() in _after, (
        "照著空狀態的指路做（列入基金）之後，NAV 那一塊沒有離開空狀態 —— "
        "那句指路是死的。")


def test_the_empty_state_does_not_also_print_the_pending_excuse():
    """空狀態**不得**同時印「本頁分批上線」那句。

    兩種灰的下一步不同：空狀態的下一步是**使用者去列入基金**（有效），
    「還沒接上」的下一步是**等我們接線**（使用者做不了）。
    ⛔ 疊在一起會讓使用者以為列入基金也沒用 —— 一次只給一個。
    """
    _parts = _stream("missing")
    _empty_names = {_m.group(1).strip() for _p in _parts
                    if (_m := _EMPTY_OPEN.match(_p))}
    assert _empty_names, "（missing）根本沒有空狀態單位 —— NAV 那一塊應該要走空狀態。"
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
    assert _pending_where(nav_manual_label()) in _body, (
        f"單位「{unit}」的灰態沒有帶指路。線框 §02：這是最容易省掉、也最有價值的一項。")


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


def test_the_manual_lists_exactly_the_wireframe_three():
    """使用手冊只列線框逐字的三項目錄 —— **不准編一段內文充數**。

    線框逐字：「指標定義、門檻由來、常見誤讀。純文字，不佔首屏。」
    ⛔ 在一份**專門用來解釋門檻由來**的文件裡編內容，是最壞的一種造假（§1）。
    """
    _body = _text(_segments(_stream("loaded")).get(BLOCK_MANUAL, []))
    for _item in ("指標定義", "門檻由來", "常見誤讀"):
        assert _item in _body, (
            f"使用手冊少了線框逐字列的「{_item}」：\n{_body}")


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
    那一格改由「連線與金鑰必須是灰態」反向守
    （:func:`test_every_grey_unit_is_grey_until_its_content_lands`）——
    **一張灰卡不可能同時印一個「正常」的結論。**
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

def test_the_write_block_is_form_wrapped():
    """線框用**粗體**寫的硬要求：「寫入類動作，**全部 Form 封裝**」。

    ⚠️ 這條驗的是**畫面上真的有一個 form 送出鈕**，不是「原始碼裡有 `applied_form` 這個字」——
    後者被註解掉一半也照樣通過。
    """
    _at = _app(FAKE_HOLDINGS)
    assert len(_at.button) >= 1, (
        "畫面上沒有任何送出鈕 —— 手動補資料是寫入類動作，線框要求全部 Form 封裝。")
    _labels = [_b.label for _b in _at.button]
    assert SUBMIT_LABEL in _labels, (
        f"送出鈕的字不是 {SUBMIT_LABEL!r}：{_labels}")


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
    _at.checkbox[0].check()
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


def test_the_page_never_reaches_into_the_data_layer():
    """View 不得直接碰 L1／L2 —— 本批連取數都還沒有，更不該有。"""
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.split(".")[0] in ("repositories", "services", "infra", "requests",
                                    "httpx", "pandas", "yfinance", "gspread")]
    assert not _bad, (
        f"被測檔 import 了資料／計算層：{_bad}\n"
        "本批只做骨架，沒有取數；接線那一批也要走 L2 service，不得直呼 L1。")


def test_the_page_does_not_delegate_to_the_old_tabs():
    """⛔ 不准 import 或委派線框「從哪裡搬來」列的四個舊檔。

    客戶方針：**打掉重練，不改舊 `tab*.py`** —— 委派過去等於把舊頁的行為
    原封搬進新頁，那不是重刻，是包一層。
    """
    _old = ("ui.tab5_data_guard", "ui.tab_manage", "ui.tab_settings_diag",
            "ui.tab6_manual")
    _bad = [_m for _m in _imported_modules(_tree())
            if any(_m.startswith(_o) for _o in _old)]
    assert not _bad, (
        f"被測檔委派給了舊分頁：{_bad}\n線框「從哪裡搬來」的四個檔是**參考**，不是依賴。")


def test_the_page_does_not_render_cache_or_backoff_state():
    """⛔ 線框「這裡不放什麼」逐字：「**快取與退避狀態不做成畫面**」。

    ⚠️ 判準是**模組層有沒有相關常數／有沒有 import 那些模組**，
    不是「畫面上有沒有那幾個字」—— 後者在骨架階段恆為真，驗不到東西。
    """
    _names = [_t.id.upper() for _t in _module_level_names(_tree())]
    _bad_names = [_n for _n in _names
                  if any(_k in _n for _k in ("BACKOFF", "CACHE", "TTL"))]
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
    _at.checkbox[0].check()
    _at.button[0].click()
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
