"""③ 標的探索新頁的骨架守衛 —— 線框 Tab 03 的四塊，一塊都不准少。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**骨架的形狀**：四個區塊都在、順序對、Form 真的 gate 住下游、
還沒搜尋時只畫空狀態、送出後八個單位**各自**誠實灰、深度區的五塊 ＋ 來源標註逐字。

⛔ **本檔不守內容對不對** —— 本批的內容**本來就還沒填**（客戶 2026-09-05：
   骨架先上線、CI 綠、再分批填）。下一批把真內容接上時，
   `test_every_grey_unit_is_grey_until_its_content_lands` 會**轉紅** ——
   **那是預期的**，屆時請把它改成「真內容放行」，**不要把它放寬**
   （① 與 ② 的同型守衛就是這樣從灰態放行轉成真內容放行的）。

⛔ **本檔不守「選定後展開」這個 gate** —— 骨架階段沒有東西可以被選定，
   那個 gate 在本批**還不存在**（理由見 `ui/views/page_03_research.py` 的模組 docstring）。
   下一批接上結果卡時，
   `test_all_blocks_are_present_and_in_wireframe_order` 會因為深度區不再無條件渲染而轉紅
   —— **正解是把它改成 gate 驗證，不是把斷言放寬。**

⛔ **本檔不驗瀏覽器裡的真實版面**：欄寬、窄螢幕折行、`st.form` 送出後真正的
   rerun 次數 —— 那些是 Streamlit 的執行期行為，靜態規則與 recorder 都看不到。

⛔ **本檔不重複既有的全域規則**（`ui/**` 全掃的那幾條會自動涵蓋這個新檔）：
   `tests/test_ui_grid_contract.py`（欄數）、`tests/test_ui_rerun_contract.py`（form 站點）、
   `tests/test_batch2_top_card_grid.py`（`where=` 必填、灰卡要有 remedy）、
   `tests/test_wpf_five_tab_wiring.py`（分頁名不得手抄）。
   **在這裡再抄一份等於製造第二把尺**（`CLAUDE.md §2.1`）。

本檔**已知打不到的地方**（照實寫，不要用形容詞蓋過去）
------------------------------------------------------
這三條是 ② `tests/test_wf02_health_skeleton.py` 被獨立紅隊打穿的三個維度。
本檔**只解掉其中一條半**，其餘照實登記 —— 讀本檔的人請據此打折信任它。

- **繞道維（本檔已解）**：② 的 `_segments()` 回傳 dict，**同名單位後者覆蓋前者**，
  於是「掏空真區塊 ＋ 另造一個同名誘餌帶灰態」可以全綠。
  本檔補了 :func:`test_unit_names_are_unique`，同名誘餌**當場轉紅**（突變 M11 實測）。
- **繞道維（本檔已解另一半）**：② 的「手刻 `st.markdown("⬜ …")` 不走 `not_ready()`
  也照樣被認成灰態」。本檔補了
  :func:`test_the_page_never_hand_rolls_the_grey_mark`（AST，活字串不得含 ⬜）。
- ⛔ **語意維（本檔**沒有**解）**：所有灰態斷言驗的是**符號**（⬜）與**常數**
  （`_PENDING_NOTE`），**不驗那句話的意思**。把灰態文案改成
  「⬜ 本頁分批上線，這一塊的內容還沒接上。目前一切正常，無異常。」——
  **本檔全綠**。同理，八個單位的灰態理由**互換**（把配息的理由掛到持股上）也全綠。
- ⛔ **情境維（本檔只覆蓋到一半）**：頁面只被渲染過 **兩種** session 形狀
  （`None` 與一份 `{"term","source"}`）。`_applied_query()` 對**非 dict 髒值**
  （字串／list／舊版 payload）的行為**沒有任何斷言**。
  `_normalise_query()` 本身有直接測（:func:`test_a_blank_search_never_counts_as_applied`），
  但它與 `_render_search_form()` 之間的接線**只由 AST 驗形狀，沒有跑過**。
- ⛔ **指路挑錯 key 沒有守衛**：`_pending_where()` 若把 `where_to_find('research')`
  換成任何一個**別的合法 key**，:func:`test_every_grey_says_where_to_look` 才會紅；
  但職責宣告那一句裡的 `health` / `portfolio` 兩個 key **換成別的合法 key 不會有任何東西轉紅**。
  **這是「走 SSOT」擋不到的那一類**：SSOT 保證名字不過期，**不保證你挑對了 key**。
- ⛔ **`test_the_two_fields_and_the_submit_verb_come_from_the_wireframe` 只驗標籤字**，
  不驗 widget 型別 —— 把 `text_input` 換成 `chat_input`、把 `selectbox` 換成 `radio`，
  只要標籤沒變就全綠。

⚠️ 兩個**全域守衛的實測盲點**（本檔的突變順便量到的，登記給後人，不是本檔的功勞）
------------------------------------------------------------------------------
下面兩項不是本檔的缺口 —— 是「本頁**只靠全域守衛**會漏掉什麼」。
兩項都是**本批實跑**（各跑 5 個測試檔、503 passed 的那一輪）：

- **突變 M15：把指路的分頁名手抄成去掉 emoji 的「標的探索」** →
  `tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`
  **沒有轉紅**，只有本檔的 `test_every_grey_says_where_to_look` 抓到。
  原因是那條守衛的黑名單**只對 `RETIRED_TAB_LABELS` / `MISWRITTEN_TAB_NAMES` 展開
  「去 emoji 變體」**，**現行**分頁名只比對含 emoji 的完整標籤
  （該守衛自己的 docstring 就寫著這個取捨）。
  → **手抄一個現行分頁名、順手把 emoji 丟掉，全域網子接不住。**
- **突變 M09：本頁自己寫 `st.columns(3)`** →
  `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL` **沒有轉紅**
  （它抓的是「**欄數不是 3**」的呼叫，3 欄是合規的），只有本檔的
  `test_the_page_draws_no_grid_or_form_of_its_own` 抓到。
  → 那個精確 `==` 的計數器**不會**因為本頁多寫一個合規 3 欄而動，
  也就是說「本頁不得自己開網格」這條**只有本檔在守**。

錄製法：為什麼不用 AppTest
--------------------------
本頁尚未接進 `app.py`（客戶明令舊三頁不動、不接線），AppTest 走不到它。
故以**替換 `st` 的渲染 API**錄下呼叫序列 —— 與
`tests/test_wf01_detail_zone_order.py` / `tests/test_wf02_health_skeleton.py`
同一套做法，那裡已經被多輪獨立稽核打過。
"""
from __future__ import annotations

import ast
import pathlib
import re
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_03_research.py"

#: 灰態的視覺記號（`ui/helpers/render_state.py::NOT_READY_MARK`）。
#: ⚠️ **從那個模組 import，不在這裡抄一份字面值** —— 抄了就是第二份真相源。
from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import where_to_find  # noqa: E402
from ui.views.page_03_research import (  # noqa: E402
    BLOCK_BATCH,
    BLOCK_DEEP,
    BLOCK_FORM,
    BLOCK_RESULTS,
    DEEP_DIVE_CARDS,
    DEEP_DIVE_PROVENANCE,
    DEEP_DIVE_TABLES,
    SOURCE_OPTIONS,
    SUBMIT_LABEL,
    _PENDING_NOTE,
    _normalise_query,
    render_fund_research,
)

#: 會產生「使用者看得到的字」的 st API。錄下來當作單位有沒有真的畫東西的證據。
_TEXT_APIS = (
    "markdown", "write", "caption", "text", "info", "warning", "error",
    "success", "metric", "dataframe", "table", "code", "header", "subheader",
    "title", "slider", "number_input", "checkbox", "text_input", "selectbox",
    "form_submit_button",
)


class _Rec:
    """把 `st.<api>(...)` 錄成一串字，其餘屬性一律回傳可呼叫 / 可進 `with` 的假物件。"""

    def __init__(self) -> None:
        self.parts: list[str] = []
        self.session_state: dict[str, Any] = {}

    # ── context manager（`with st.container():` 之類）────────────────
    def __enter__(self) -> "_Rec":
        return self

    def __exit__(self, *_exc: Any) -> bool:
        return False

    def _child(self) -> "_Rec._Child":
        return _Rec._Child(self)

    def __getattr__(self, name: str):
        def _fn(*args: Any, **kwargs: Any):
            if name in _TEXT_APIS:
                _bits = [str(a) for a in args if isinstance(a, (str, int, float))]
                # widget 的 label 是第一個位置引數；`metric` 的值是第二個。
                self.parts.append(f"[{name}] " + " ".join(_bits))
            if name == "text_input":
                return kwargs.get("value", "")
            if name == "selectbox":
                _opts = kwargs.get("options") or (args[1] if len(args) > 1 else ())
                _opts = list(_opts or [])
                return _opts[kwargs.get("index", 0) or 0] if _opts else ""
            if name in ("slider", "number_input"):
                return kwargs.get("value", args[2] if len(args) > 2 else 0)
            if name in ("checkbox", "toggle", "button", "form_submit_button"):
                return False
            if name == "columns":
                _spec = args[0] if args else 1
                _n = _spec if isinstance(_spec, int) else len(list(_spec))
                return [self._child() for _ in range(max(int(_n), 1))]
            return self._child()
        return _fn

    class _Child:
        """`st.columns()` / `st.form()` 回傳的容器：寫回同一份紀錄。"""

        def __init__(self, root: "_Rec") -> None:
            self._root = root

        def __enter__(self):
            return self

        def __exit__(self, *_exc: Any) -> bool:
            return False

        def __getattr__(self, name: str):
            return getattr(self._root, name)


def _render(applied: dict | None = None) -> list[str]:
    """跑一次整頁，回傳**有序**的渲染紀錄。

    ⚠️ 回傳 list 而不是一整塊字串 —— 順序本身是本檔要驗的東西之一，
    join 成一坨就驗不了「哪一句落在哪一塊底下」。
    """
    import sys

    # 匯入套件 → 它的 `__init__` 會把四個子模組都放進 `sys.modules`。
    import ui.helpers.ia  # noqa: F401

    # ⚠️ **一律走 `sys.modules`，不要用 `import a.b.c as x`。**
    #    `ui/helpers/ia/__init__.py` 有一行 `from ui.helpers.ia.empty_state import
    #    empty_state` —— 它把**函式**綁成了套件的 `empty_state` 屬性，於是
    #    `import ui.helpers.ia.empty_state as _e` 拿到的是那個**函式**而不是模組，
    #    `setattr(_e, "st", …)` 就打在函式身上、模組的 `st` 一動也沒動。
    #    **② 的同型測試初稿就是這樣寫的，症狀是空狀態的標題與 footer 整個錄不到**
    #    —— 也就是說：**錯的 patch 不會報錯，只會讓斷言對著半份畫面生效。**
    _targets = tuple(sys.modules[_n] for _n in (
        "ui.views.page_03_research",
        "ui.helpers.ia.cards",
        "ui.helpers.ia.empty_state",
        "ui.helpers.ia.gated_form",
        "ui.helpers.ia.layout",
        "ui.helpers.render_state",
    ))
    # ⚠️ **`ui.helpers.story_nav` 刻意不在上表**：它的 `render_story_nav()` 是
    #    **函式內** `import streamlit as st`，沒有 module 層的 `st` 可以換 ——
    #    它那一行麵包屑 caption 走的是**真的** streamlit（bare 模式下無害）、
    #    **不會**進到紀錄裡。本檔沒有任何斷言依賴它。

    _rec = _Rec()
    if applied is not None:
        _rec.session_state["v03_research_applied_query"] = applied

    _saved = [(_m, getattr(_m, "st", None)) for _m in _targets]
    # 錨點：每一個目標模組**都要**真的有 `st` 可以換掉。少一個就代表上面那個
    # 遮蔽陷阱又發作了，而它的症狀是**靜默漏錄**，不是報錯。
    _blind = [_m.__name__ for _m, _old in _saved if _old is None]
    assert not _blind, (
        f"下列模組沒有 module 層的 `st` 可以替換：{_blind}\n"
        "錄不到它們畫的東西，本檔所有斷言會對著半份畫面生效。")
    try:
        for _m in _targets:
            _m.st = _rec
        render_fund_research()
    finally:
        for _m, _old in _saved:
            _m.st = _old
    return _rec.parts


def _text(parts: list[str]) -> str:
    return "\n".join(parts)


#: 一級區塊標題（`st.markdown("#### …")`）。
_L4_OPEN = re.compile(r"^\[markdown\] #{4}\s+(.*)$")
#: 深度區裡的次級段落（`st.markdown("##### …")`）。
_L5_OPEN = re.compile(r"^\[markdown\] #{5}\s+(.*)$")
#: 一張卡的標題 —— `ia.state_card()` 在灰態時畫的 `st.markdown(f"**{title}**")`。
#: ⚠️ **這一條是本檔的最小單位，不是裝飾**（理由見 :func:`_units`）。
_CARD_OPEN = re.compile(r"^\[markdown\] \*\*(.+)\*\*$")


def _units(parts: list[str]) -> list[tuple[str, list[str]]]:
    """把紀錄切成**有序**的最小單位：一級／次級段落，或**一張卡**。

    ⚠️ **粒度是「一張卡」，這是被 ② 的一次突變逼出來的，不是設計出來的。**
    `tests/test_wf02_health_skeleton.py::_units` 記著：初版只依 `#### 區塊名` 切段，
    突變「只拿掉其中一塊的灰態」**沒有轉紅** —— 因為同一段裡別張卡的 ⬜ 替它過關了。
    同一個形狀在 ① 被獨立稽核連續打穿兩輪。**答案每次都一樣：把邊界往下降。**

    ⛔ **不要為了讓斷言好寫而把邊界往上收。** 邊界一寬，鄰居的字就會替你通過。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _m = _L4_OPEN.match(_p) or _L5_OPEN.match(_p) or _CARD_OPEN.match(_p)
        if _m:
            _out.append((_m.group(1).strip(), []))
            continue
        if _out:
            _out[-1][1].append(_p)
    return _out


def _segments(parts: list[str]) -> dict[str, list[str]]:
    """`單位名 -> 該單位內的渲染紀錄`（:func:`_units` 的 dict 檢視）。

    ⚠️ **dict 會讓同名單位後者覆蓋前者** —— 那正是 ② 被紅隊打穿的繞道。
    本檔用 :func:`test_unit_names_are_unique` 把「不會有同名單位」變成一條**斷言**，
    而不是一個假設。**本函式因此可以安全地用 dict。**
    """
    return {_k: _v for _k, _v in _units(parts)}


#: 一級區塊（`####`）的順序，即線框 Tab 03 由上而下的順序。
EXPECTED_BLOCKS: tuple[str, ...] = (BLOCK_RESULTS, BLOCK_DEEP, BLOCK_BATCH)

#: **每一個都要各自帶灰態**的最小單位（八個）。
#: ⚠️ `BLOCK_DEEP` 不在這裡：它是**純容器**（標題底下直接接三張卡），
#:    它的「內容」就是下面這幾個單位，各自有自己的灰。
GREY_UNITS: tuple[str, ...] = (
    (BLOCK_RESULTS,) + DEEP_DIVE_CARDS + DEEP_DIVE_TABLES
    + (DEEP_DIVE_PROVENANCE, BLOCK_BATCH)
)

#: 一份「已送出」的查詢。形狀就是 `_normalise_query()` 的回傳值。
FAKE_QUERY = {"term": "ACDD", "source": SOURCE_OPTIONS[0]}


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


def _attr_calls(tree: ast.AST, names: tuple[str, ...]) -> list[str]:
    return [f"第 {_n.lineno} 行 {ast.unparse(_n.func)}(…)"
            for _n in ast.walk(tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in names]


# ══════════════════════════════════════════════════════════════════
# 骨架：四塊都在、順序對
# ══════════════════════════════════════════════════════════════════

def test_the_search_form_is_the_first_thing_on_the_page():
    """線框 Tab 03 的第一塊就是 Form —— 而且它必須在任何結果**之前**。

    順序不是美感問題：搜尋條件在結果**後面**的話，使用者會先看到一堆
    他還沒下條件的東西。
    """
    _parts = _render(applied=FAKE_QUERY)
    _submit = [_i for _i, _p in enumerate(_parts)
               if _p.startswith("[form_submit_button]")]
    assert _submit, (
        "整頁沒有任何 `form_submit_button` —— 搜尋條件沒有包在 `applied_form()` 裡。\n"
        "線框 Rule 02「篩選、輸入框、滑桿一律 `st.form` 包住」是四大鐵律之二，不是選配。")
    _first_block = next(
        (_i for _i, _p in enumerate(_parts) if _L4_OPEN.match(_p)), None)
    assert _first_block is not None, "找不到任何 `#### 區塊標題` —— 骨架的分段記號不見了。"
    assert _submit[0] < _first_block, (
        "送出鈕出現在第一個內容區塊**之後** —— 搜尋條件必須在結果前面。\n"
        f"送出鈕在第 {_submit[0]} 筆，第一個區塊在第 {_first_block} 筆。")


def test_the_two_fields_and_the_submit_verb_come_from_the_wireframe():
    """線框 Tab 03 的 Form 逐字：「代碼或名稱」「來源」「搜尋」。少一個就紅。

    ⚠️ **送出鈕的字是「搜尋」不是「套用」** —— `ui.helpers.ia.APPLY_LABEL` 的預設值是
    「套用」，線框 Tab 03 明確畫的是「搜尋」（Tab 02 才是「套用」）。
    這不是文案潔癖：使用者要知道按下去會發生什麼事，「套用」在一個搜尋框上不知所云。

    ⚠️ 用**標籤字**比對，因為線框定的就是這兩個欄位本身，不是它們的實作型別
    （型別本檔不驗，見模組 docstring 的已知缺口）。
    """
    _all = _text(_render(applied=FAKE_QUERY))
    for _label in ("代碼或名稱", "來源"):
        assert _label in _all, (
            f"搜尋條件少了「{_label}」—— 線框 Tab 03 的 Form 逐字列了兩個欄位。")
    assert f"[form_submit_button] {SUBMIT_LABEL}" in _all, (
        f"送出鈕不是「{SUBMIT_LABEL}」—— 線框 Tab 03 畫的是這兩個字。\n" + _all)
    assert SUBMIT_LABEL == "搜尋", (
        f"`SUBMIT_LABEL` 被改成 {SUBMIT_LABEL!r} —— 線框 Tab 03 的送出鈕是「搜尋」。")


def test_the_source_filter_does_not_invent_options():
    """⛔ 「來源」下拉**只准有線框給的那一個值**，不准憑印象補一份來源清單。

    線框只寫了「來源　全部」。這個站點實際支援哪幾個來源要等取數接上才知道；
    先列一份，使用者挑了一個實際上不生效的來源 —— 那是 §1 的**假選項**，
    比少一個選項危險得多（他會以為自己已經篩掉了別的來源）。

    ⚠️ **下一批把真來源集合接上時，這條會轉紅 —— 那是預期的。**
    屆時請把它改成「選項必須來自取數層回報的來源集合」，**不要**直接刪掉它。
    """
    assert SOURCE_OPTIONS == ("全部",), (
        f"`SOURCE_OPTIONS` 變成 {SOURCE_OPTIONS!r} —— 線框只給了「全部」。\n"
        "多出來的選項如果不是取數層真的支援的，它就是一個會騙人的篩選條件（§1）。")


def test_all_blocks_are_present_and_in_wireframe_order():
    """送出搜尋後：搜尋結果 → 單一基金深度 → 批次分析，缺一或倒序即紅。

    ⚠️ **下一批把「選定後展開」的 gate 接上時，這條會轉紅** ——
    因為深度區將不再無條件渲染。**正解是改成 gate 驗證，不是放寬。**
    """
    _parts = _render(applied=FAKE_QUERY)
    _seg = _segments(_parts)
    for _b in EXPECTED_BLOCKS:
        assert _b in _seg, (
            f"線框 Tab 03 的區塊「{_b}」不見了。現有單位：{list(_seg)}")
    _order = [_m.group(1).strip() for _m in
              (_L4_OPEN.match(_p) for _p in _parts) if _m]
    assert _order == list(EXPECTED_BLOCKS), (
        f"一級區塊順序與線框 Tab 03 不符：{_order}\n"
        f"應為：{list(EXPECTED_BLOCKS)}（先給結果，再給單檔深度，最後才是批次）。")


def test_deep_dive_keeps_the_five_blocks_and_the_source_annotation():
    """單一基金深度：3 欄 ×3 ＋ 大表全寬 ×2 ＋ 來源標註，逐字對線框。

    線框原文：「NAV 走勢 · 績效分期 · 風險指標 · 前十大持股 · 配息紀錄 ·
    資料來源與抓取時間。**五個區塊各自 3 欄，持股與配息為大表全寬。**」

    ⚠️ **那句話列了六項卻說「五個區塊」，是線框自己的歧義**（見被測檔的模組 docstring）。
    本檔的處理方式讓**兩種讀法都通過**：五塊各有自己的段落，
    來源標註**也有**自己的段落 —— 突變拿掉其中任何一個都會轉紅。
    """
    assert DEEP_DIVE_CARDS == ("NAV 走勢", "績效分期", "風險指標"), (
        f"深度區的 3 欄卡與線框不符：{DEEP_DIVE_CARDS}")
    assert DEEP_DIVE_TABLES == ("前十大持股", "配息紀錄"), (
        f"深度區的大表與線框不符：{DEEP_DIVE_TABLES}")
    assert DEEP_DIVE_PROVENANCE == "資料來源與抓取時間", (
        f"來源標註與線框不符：{DEEP_DIVE_PROVENANCE!r}")
    _seg = _segments(_render(applied=FAKE_QUERY))
    for _name in DEEP_DIVE_CARDS + DEEP_DIVE_TABLES + (DEEP_DIVE_PROVENANCE,):
        assert _name in _seg, (
            f"深度區少了「{_name}」這一段。現有單位：{list(_seg)}")


def test_unit_names_are_unique():
    """**單位名不得重複** —— 這條堵的是 ② 被紅隊打穿的那條繞道。

    ② 的 `_segments()` 回傳 dict，**同名單位後者覆蓋前者**；紅隊因此可以
    「把真區塊掏空、另造一個同名誘餌帶著灰態」→ 全綠。
    只要單位名保證唯一，dict 檢視就不會遮蔽任何東西。

    ⚠️ 這條同時是 :func:`_segments` 的**前提** —— 它紅了，所有用 `_segments()`
    的斷言都要重新看，不是只有這一條。
    """
    for _applied in (None, FAKE_QUERY):
        _names = [_k for _k, _ in _units(_render(applied=_applied))]
        _dupes = sorted({_n for _n in _names if _names.count(_n) > 1})
        assert not _dupes, (
            f"（applied={_applied is not None}）出現同名單位 {_dupes} —— "
            "`_segments()` 的 dict 檢視會讓後者覆蓋前者，"
            "等於在灰態斷言上開一道後門。請把段落名改成唯一。")


def test_the_two_contested_block_names_go_through_story_nav():
    """⛔ 「單檔」與「多檔」兩塊的名字**必須走 `section_label()`**，不得寫死字面值。

    ## 這條守的是一個**未裁決的衝突**，不是一個已定案的規則

    兩份**都已客戶拍板**的線框對同樣這兩塊給了不同的名字：

    | 線框 | 日期 | 這兩塊叫什麼 |
    |---|---|---|
    | `docs/wireframes/wireframe-fund-research.html` | 2026-08-31 | 🔍 單檔深掘 ／ 📦 批次掃描 |
    | `docs/wireframes/ia-wireframe.html` | 2026-09-01 | 單一基金深度 ／ 批次分析 |

    而 `docs/wireframes/README.md` 的「版本關係」段**沒有登記**後者覆蓋前者
    （它只登記了 ia-wireframe 覆蓋 `fund-wireframe-final.html` 的兩處：分頁命名與 ⑤ 的區塊切分）。

    **本批取 SSOT（＝前者，已登記進 `story_nav._SECTION_LABELS` 的 `fund` / `batch`），
    但那是暫行，不是裁決** —— 完整理由寫在被測檔 `BLOCK_DEEP` 上方。
    其中最硬的一條是可自驗的：**「📦 批次分析」是已退役的頂層分頁名**
    （`story_nav.RETIRED_TAB_LABELS`），寫成活字串會讓
    `tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name` 轉紅。

    ⚠️ **總管若裁決以 ia-wireframe 的字面為準，這條會轉紅 —— 那是預期的。**
    屆時要一起處理的是那條全域守衛（「批次分析」還在退役字表裡），
    **不是**把這條刪掉了事。
    """
    _t = _tree()
    _assigned = {
        _n.target.id: _n.value for _n in ast.walk(_t)
        if isinstance(_n, ast.AnnAssign) and isinstance(_n.target, ast.Name)
        and _n.value is not None
    }
    for _const in ("BLOCK_DEEP", "BLOCK_BATCH"):
        _v = _assigned.get(_const)
        assert _v is not None, f"找不到模組層的 `{_const}` 定義。"
        _fns = {getattr(_c.func, "id", None) or getattr(_c.func, "attr", None)
                for _c in ast.walk(_v) if isinstance(_c, ast.Call)}
        assert "section_label" in _fns, (
            f"`{_const}` 被寫成字面值（{ast.unparse(_v)}）—— "
            "這兩塊的名字目前卡在兩份已核准線框的衝突上，"
            "在總管裁決之前一律走 `story_nav.section_label()`，理由見被測檔。")
    assert BLOCK_DEEP and BLOCK_BATCH and BLOCK_DEEP != BLOCK_BATCH


def test_the_wide_tables_go_through_wide_table_not_st_dataframe():
    """大表一律走 `ui.helpers.ia.wide_table()`，不得自己 `st.dataframe`。

    線框 Rule 04：「無資料不畫空表格外框」。而 `st.dataframe(空)` 的**預設行為
    正好就是畫一個空框** —— 把判斷收在唯一的大表入口，這條規則才有著力點
    （`ui/helpers/ia/layout.py` 的模組 docstring）。
    """
    _bad = _attr_calls(_tree(), ("dataframe", "table"))
    assert not _bad, (
        "本頁自己畫了表格，繞過 `wide_table()` 的空狀態分支：\n  "
        + "\n  ".join(_bad)
        + "\n空資料時它會畫一個空表格外框，正是鐵則 04 要禁的冗餘占位。")


def test_the_page_draws_no_grid_or_form_of_its_own():
    """鐵則 01 / 02 一律走共用元件：本檔不得有 `st.columns` 或 `st.form`。

    ⚠️ 這條不是為了好看：自己寫 `st.columns` 會讓
    `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL`（精確 `==`）轉紅；
    自己寫 `st.form` 會讓 `tests/test_ui_rerun_contract.py::FORM_SITE_TOTAL` 轉紅。
    **在這裡先擋一次，是為了讓錯誤訊息指向本頁，而不是指向一個全域計數器。**
    """
    _bad = _attr_calls(_tree(), ("columns", "form"))
    assert not _bad, (
        "本頁自己開了網格 / 表單，沒有走 IA kit：\n  " + "\n  ".join(_bad)
        + "\n請改用 `ui.helpers.ia.render_cards()` 與 `ui.helpers.ia.applied_form()`。")


# ══════════════════════════════════════════════════════════════════
# 鐵則 02 / 04：Form 之前什麼都不畫
# ══════════════════════════════════════════════════════════════════

def test_nothing_below_the_form_renders_before_a_search():
    """還沒送出查詢 → 只有 Form ＋ 空狀態三要素，下面**一塊都不畫**。

    兩條線框依據，缺一不可：
      - **Rule 04**「無資料不畫空表格外框，改用空狀態三要素」；
      - Tab 03 批次分析的 chip「**Form 後才跑**」（長時間運算不得在載入時自己啟動）。
    """
    _parts = _render(applied=None)
    _seg = _segments(_parts)
    _leaked = [_b for _b in EXPECTED_BLOCKS + GREY_UNITS if _b in _seg]
    assert not _leaked, (
        f"還沒搜尋就畫出了 {_leaked} —— 空狀態應**取代**它們，"
        "而且批次分析的「Form 後才跑」不允許它在載入時就出現。")
    _all = _text(_parts)
    assert "還沒開始搜尋" in _all, "還沒搜尋時應出現空狀態的標題。"
    assert "還沒有查詢條件" in _all, "空狀態缺了「缺什麼」這一要素。"
    assert where_to_find("research") in _all, (
        "空狀態的「去哪補」沒有指回本頁的搜尋條件 —— "
        f"應含 `where_to_find('research')` ＝ {where_to_find('research')!r}。")


def test_the_empty_state_does_not_also_print_the_batch_pending_excuse():
    """兩種灰不得混在一起。

    ⚠️ 這條擋的是一個很容易犯、而且看起來無害的錯：還沒搜尋時**同時**印出
    「本頁分批上線」的灰字。使用者會以為「輸入代碼按下去就會看到績效」—— 不會，
    因為內容根本還沒接上。**一次只給一個下一步。**

    ⚠️ 比對 `_PENDING_NOTE` 本體，**不硬抄字面值**。硬抄的話，常數一改措辭
    這條就永遠是 True —— 它守的 bug 照樣存在、而它不再看得見。
    """
    _all = _text(_render(applied=None))
    assert _PENDING_NOTE not in _all, (
        "還沒搜尋時不應同時印出「內容還沒接上」的灰字 —— 兩個下一步會互相抵消。\n"
        + _all)


def test_a_blank_search_never_counts_as_applied():
    """空白查詢**不算送出** —— 這是本頁唯一一條 §1 邏輯，所以它要有自己的測試。

    使用者把欄位清空再按一次送出，語意是「我不查了」；若把空字串當成一次有效查詢，
    畫面會停在一堆與任何查詢條件都無關的灰態上。

    ⚠️ 這條**直接呼叫 `_normalise_query()`**，不經渲染 ——
    recorder 的送出鈕恆為 `False`，走渲染路徑測不到這一段（模組 docstring 已登記）。
    """
    assert _normalise_query("", SOURCE_OPTIONS[0]) is None
    assert _normalise_query("   ", SOURCE_OPTIONS[0]) is None
    assert _normalise_query(None, SOURCE_OPTIONS[0]) is None  # type: ignore[arg-type]
    _q = _normalise_query("  ACDD19 ", SOURCE_OPTIONS[0])
    assert _q == {"term": "ACDD19", "source": SOURCE_OPTIONS[0]}, (
        f"非空查詢應被收成 `{{'term','source'}}`，實際得到 {_q!r}。")
    # `source` 給空**不得自己挑一個來源** —— 退回第一個選項（目前是「全部」）。
    assert _normalise_query("ACDD19", "") == {
        "term": "ACDD19", "source": SOURCE_OPTIONS[0]}


def test_downstream_reads_the_applied_query_not_the_widget_values():
    """查詢的**已送出值**與 widget 當下值必須是兩個東西。

    ⚠️ 這條守的是鐵則 02 真正的那一半。只包 `st.form` 只擋住「widget 互動觸發 rerun」，
    **沒有擋住重運算** —— 每次 rerun 照樣把下游跑一遍，畫面看起來沒問題、成本一分沒省
    （`ui/helpers/ia/gated_form.py` 模組 docstring 把這個陷阱寫得很清楚）。

    ⚠️ **這條分不出真假閘門**（② 的紅隊實測：`if True:` 與 `if not _gate:` 都全綠）——
    它只驗「session 寫入有沒有被某個 `if` 包住」。**登記，本批不補。**
    """
    _t = _tree()
    _fns = {_n.name: _n for _n in ast.walk(_t) if isinstance(_n, ast.FunctionDef)}
    for _need in ("_applied_query", "_normalise_query"):
        assert _need in _fns, (
            f"找不到 `{_need}()` —— 「已送出值」這一層被拿掉了，"
            "下游就會直接讀 widget 值，等於沒有 form。")
    _form_fn = _fns["_render_search_form"]
    _writes = [_n for _n in ast.walk(_form_fn)
               if isinstance(_n, ast.Assign)
               and any(isinstance(_t2, ast.Subscript) for _t2 in _n.targets)]
    assert _writes, "`_render_search_form()` 沒有把送出結果寫回 session。"
    _guarded = []
    for _if in ast.walk(_form_fn):
        if isinstance(_if, ast.If):
            _guarded.extend(id(_n) for _n in ast.walk(_if)
                            if isinstance(_n, ast.Assign))
    _naked = [_w for _w in _writes if id(_w) not in _guarded]
    assert not _naked, (
        "有 session 寫入**沒有**被送出閘門包住 —— 那代表每次 rerun 都會覆寫已送出值，\n"
        "使用者打字的當下就會觸發下游重算，form 等於白包。\n  "
        + "\n  ".join(f"第 {_w.lineno} 行" for _w in _naked))


# ══════════════════════════════════════════════════════════════════
# 灰態：八個單位各自誠實
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("unit", GREY_UNITS)
def test_every_grey_unit_is_grey_until_its_content_lands(unit: str):
    """送出搜尋、但內容還沒接上 → 每一個單位**各自**要有灰態記號與理由。

    ⚠️ **斷言的單位是「一段」或「一張卡」，不是整頁，也不是整塊。**
    ② 的初版以「一級區塊」為單位，突變「只拿掉其中一塊的灰態」**沒有轉紅**
    （同一段裡別張卡的 ⬜ 替它通過了）—— 粒度因此下降。詳見 :func:`_units` 的長註。

    ⚠️ **下一批把真內容接上時，這條會轉紅 —— 那是預期的。**
    屆時請把它改成「真內容放行」（例如驗結果卡有基金名、驗持股表有列），
    **不要把它放寬成「有東西就好」**。
    """
    _seg = _segments(_render(applied=FAKE_QUERY))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」有標題但沒有任何內容 —— 那是空占位。"
    assert NOT_READY_MARK in _body, (
        f"單位「{unit}」沒有灰態記號 {NOT_READY_MARK!r} —— "
        "內容還沒接上就要誠實留灰，不得空著也不得填示意值（§1）。\n" + _body)
    assert _PENDING_NOTE in _body, (
        f"單位「{unit}」的灰態沒說「為什麼沒有」。\n" + _body)


def test_every_grey_says_where_to_look():
    """每一塊灰態都要有「去哪補」，而且**不得手抄分頁名**。

    ⚠️ 這一頁的灰態有一個先天問題：內容還沒接上時，使用者**沒有地方可以去**。
    能給的最誠實的指路是「現在哪一塊是完整的」（＝搜尋條件）——
    所以本條驗的是 `where_to_find('research')` 有出現，而不是隨便一句話。
    """
    _all = _text(_render(applied=FAKE_QUERY))
    assert where_to_find("research") in _all, (
        "灰態的指路沒有走 `where_to_find('research')` —— "
        "手抄的分頁名在本 repo 已經指錯三次（見 `story_nav.RETIRED_TAB_LABELS`）。")
    assert BLOCK_FORM in _all, (
        f"指路提到的「{BLOCK_FORM}」在畫面上找不到 —— "
        "指到一個使用者看不到的名字，等於沒有指路。")


def test_the_page_never_hand_rolls_the_grey_mark():
    """⛔ 不准自己拼 ⬜ 字串 —— 灰態一律委派 `render_state` / `ia` 的入口。

    ⚠️ 這條堵的是 ② 被紅隊打穿的另一條繞道：**手刻
    `st.markdown("⬜ …")` 不走 `not_ready()`，也照樣被灰態斷言認成灰態。**
    自己拼的 ⬜ 不會有 `where=`、不會跟著 `render_state` 的視覺一起變，
    等於在 SSOT 旁邊長出第二套灰。

    ⚠️ 只掃**活字串**：被測檔的 docstring 本身就寫著「本檔沒有自己拼 ⬜ 的字串」，
    不排除 docstring 的話，這條規則會被那句說明打紅。
    """
    _bad = [f"第 {_n.lineno} 行 {_n.value[:40]!r}"
            for _n in _live_strings(_tree()) if NOT_READY_MARK in _n.value]
    assert not _bad, (
        f"本頁的活字串裡出現了 {NOT_READY_MARK!r} —— 灰態請走 "
        "`ui.helpers.render_state.not_ready()` / `ui.helpers.ia.empty_state()` / "
        "`state_card(state=STATE_NOT_READY)`：\n  " + "\n  ".join(_bad))


#: 本條**實際釘住**的字面值 —— 線框 Tab 03 三張示意結果卡上的東西。
#: 列成常數，是為了讓「它到底守了什麼」可以被讀出來，而不是藏在 docstring 的形容詞裡。
_PINNED_FAKE_VALUES: tuple[str, ...] = (
    "安聯台灣智慧基金", "貝萊德世界礦業", "元大高股息平衡",
    "ACDD19", "0P00000XYZ",
    "+12.4%", "+3.1%", "Sharpe 0.81", "0.81", "0.22",
)


def test_the_grey_blocks_never_print_the_illustrative_values_from_the_wireframe():
    """⛔ 線框那三張示意卡上的東西不准出現在畫面上（**只涵蓋下列字面寫法**）。

    為什麼要有這條：填一個看起來合理的績效，使用者**完全看不出它是假的**，
    而且會拿它去決定要不要買（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ## ⚠️ 這條**實際**守得到什麼（照實寫，不要用形容詞）

    **只釘 `_PINNED_FAKE_VALUES` 這 10 個字面寫法。**

    **明確守不到**：裸數字（`12.4` / `3.1` 不帶 `+` 與 `%`）、全形數字、
    把示意值換算成別的寫法（`0.810`）、以及**任何線框以外的捏造值**
    —— 本條是黑名單，黑名單結構上抓不到名單外的第 N+1 個。

    ## ⚠️ 一個**刻意的例外**：`0P0000ABCD`

    它是線框給輸入框的 **placeholder**（灰色格式提示），**不是畫面上的資料** ——
    不會被讀成任何一檔基金的績效或分數，而線框正是用它來指定這個欄位收什麼形狀的字。
    故本條**不釘它**，被測檔的 `_CODE_PLACEHOLDER` 就地寫了同一段理由。
    ⛔ 若客戶認為連 placeholder 都不該出現一個像真的代碼，改那個常數即可。
    """
    _all = _text(_render(applied=FAKE_QUERY))
    for _fake in _PINNED_FAKE_VALUES:
        assert _fake not in _all, (
            f"畫面上出現了線框的示意值 {_fake!r} —— "
            "那不是資料，是線框用來示範版面的假數字。")


# ══════════════════════════════════════════════════════════════════
# 邊界：只讀對接既有 Service，不碰底層、不委派舊頁
# ══════════════════════════════════════════════════════════════════

def _imported_modules(tree: ast.AST) -> list[str]:
    _mods: list[str] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            _mods.extend(_a.name for _a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.append(_n.module)
    return _mods


def test_the_page_never_reaches_into_the_data_layer():
    """客戶方針第 2 條：資料只走 `services/**`，**不碰** `repositories` / `infra` / 網路函式庫。

    ⚠️ 本批連 `services/**` 都沒有呼叫（骨架階段沒有東西要算）——
    但這條**現在就要在**，因為下一批填內容時它才是真正在守的那道線。
    ⚠️ **③ 特別容易犯**：搜尋在 `services/**` **沒有入口**（實測），
    現行實作住在 L1 `repositories.fund.tdcc_search_fund`。
    「反正 `EX-PASSTHRU-1` 有登記」**不是**在這裡 import 它的理由 ——
    那條例外的升級觸發條件就是「出現第二個 UI caller」，要總管裁決。
    """
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.split(".")[0] in ("repositories", "infra", "requests", "httpx",
                                    "yfinance", "gspread", "urllib", "bs4",
                                    "feedparser")]
    assert not _bad, (
        "本頁 import 了資料層 / 網路函式庫：" + ", ".join(_bad)
        + "\n客戶方針第 2 條：UI 只讀對接既有 Service，取不到就誠實灰態，**不反向修底層**。")


def test_the_page_does_not_delegate_to_the_old_tabs():
    """⛔ 不 import 線框「從哪裡搬來」列的那三個舊頁。

    它們會在五頁驗收完成後**整批拔除**，每一條委派都是一處會斷頭。
    ⚠️ ① 留了一條對 `ui/tab1_macro_midcycle.py` 的委派並就地登記
    「有效期到舊 tab 整批拔除為止」—— **本頁一條都沒有，而且要維持這樣。**
    """
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.startswith("ui.tab") or "fund_research" in _m
            or "batch_analysis" in _m or "single_fund" in _m]
    assert not _bad, (
        "本頁委派了舊 ③ 的來源分頁：" + ", ".join(_bad)
        + "\n舊實作會被整批拔除；本頁一律自己畫完。")


def test_the_page_does_not_assume_i_already_hold_these_funds():
    """線框 Tab 03 畫底線的那半句：**這裡的基金不預設我有持有**。

    ⚠️ 這條是**反向**規則（守「不要有」而不是「要有」），因為它擋的是一種
    看起來很貼心的退化：順手讀 `portfolio_funds`，在結果卡上標「你已持有」。
    那會把 ② 持倉體檢的職責搬進 ③，而線框把「我持有部位的健康度」
    明列在 Tab 03 的「這裡不放什麼」。
    """
    _bad = [f"第 {_n.lineno} 行 {_n.value!r}"
            for _n in _live_strings(_tree()) if "portfolio_funds" in _n.value]
    assert not _bad, (
        "本頁讀了組合持股的 session 契約：\n  " + "\n  ".join(_bad)
        + "\n線框 Tab 03：「這裡的基金**不預設我有持有**」。"
          "要標示持有狀態是 ② 的職責，不是這裡的。")
