"""④ 資產配置新頁的骨架守衛 —— 線框 Tab 04 的四塊，一塊都不准少。

錄製法：**用真的 Streamlit 跑（AppTest），不用假的 recorder**
------------------------------------------------------------
① ② ③ 三頁的同型守衛都是「替換模組層的 `st`」錄下呼叫序列 ——
理由是那三頁**當時**尚未接進 `app.py`，`AppTest.from_file("app.py")` 走不到它們。

**本檔改用 `AppTest.from_string()`**：它不需要頁面被接進 `app.py`，
直接把「import 這個 View 並呼叫它」當成一支 script 跑，拿到的是**真的 Streamlit
渲染出來的元素樹**。三個具體好處，每一個都對應到前三頁踩過的坑：

1. **不會有「patch 打歪」的靜默失效。** ③ 的測試檔就地記著：
   `import ui.helpers.ia.empty_state as _e` 拿到的是**函式**不是模組，
   `setattr(_e, "st", …)` 打在函式身上、模組的 `st` 一動也沒動 ——
   **錯的 patch 不會報錯，只會讓斷言對著半份畫面生效。** 本檔沒有 patch，所以沒有這個面。
2. **元素順序是真的順序**（含 `st.columns` 的欄內巢狀），不是我自己拼的字串流。
3. ⭐ **可以真的按下去。** 本檔因此能回答前三頁**回答不了**的那個問題：
   **「照著那句指路做，那一塊真的會離開灰態嗎？」**（見下方「兩種灰的指路，實跑結果不同」）

⚠️ **代價，據實寫**：AppTest 比假 recorder 慢（每次 `run()` 都真的跑一次 script），
   故本檔用 :func:`_stream` 快取三種 session 形狀的渲染結果，同一形狀只跑一次。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**骨架的形狀**：六個單位都在、順序對、沒有持倉時只畫空狀態、
有持倉時五個灰態單位**各自**誠實灰、Form 那一塊**不灰**（它是本批唯一做完的）、
以及線框的示意值一個都沒有畫出來。

⛔ **本檔不守內容對不對** —— 本批的內容**本來就還沒填**。下一批把真內容接上時，
   `test_every_grey_unit_is_grey_until_its_content_lands` 會**轉紅** ——
   **那是預期的**，屆時請把它改成「真內容放行」，**不要把它放寬**。

⛔ **本檔不驗瀏覽器裡的真實版面**：欄寬、窄螢幕折行、真正的 rerun 次數 ——
   AppTest 沒有瀏覽器，那些看不到。

⛔ **本檔不重複既有的全域規則**（`ui/**` 全掃的那幾條會自動涵蓋這個新檔）：
   `tests/test_ui_grid_contract.py`（欄數）、`tests/test_ui_rerun_contract.py`（form 站點）、
   `tests/test_batch2_top_card_grid.py`（`where=` 必填、灰卡要有 remedy）、
   `tests/test_wpf_five_tab_wiring.py`（分頁名不得手抄）、
   `tests/test_ia_switch_advisor_moved_to_portfolio.py`（換股顧問渲染點恰好一個）。
   **在這裡再抄一份等於製造第二把尺**（`CLAUDE.md §2.1`）。

兩種灰的指路，實跑結果不同 —— 這是本檔最重要的一段
--------------------------------------------------
被測檔有兩種灰，文案刻意分開。**本檔把「照著做有沒有用」真的按了一次**：

===================== ============================================ ==========
灰的種類               指路指到哪                                    照著做有效嗎
===================== ============================================ ==========
**沒有持倉**（空狀態）  ④ 📊 資產配置 → ➕ 加入與管理基金               ✅ **有效**
**內容還沒接上**       ④ 📊 資產配置 → 再平衡試算                     ❌ **無效**
===================== ============================================ ==========

- ✅ 那一列由 :func:`test_the_empty_state_pointer_actually_works` 實跑：
  照著做（讓 `portfolio_funds` 有已載入的項目）→ 空狀態**真的消失**、四塊**真的出現**。
- ❌ 那一列由 :func:`test_the_pending_pointer_is_honest_about_being_ineffective` 實跑：
  照著做（回到再平衡試算、填金額、按「試算」）→ **五條灰態逐字完全相同**。
  ⛔ **這不是 bug，是本批的實況**：這一塊沒接上，去任何地方都不會讓它出現。
  **本檔把它寫成一條會轉紅的斷言，而不是一句形容詞** ——
  哪天它真的變有效了（內容接上了），那條測試會紅，而那正是要人回來改文案的時候。
  ⚠️ **為什麼不乾脆把 `where=` 拿掉**：全域
  `tests/test_batch2_top_card_grid.py::test_where_is_mandatory` 規定
  `not_ready()` / `empty_state()` **一定要帶 `where=`**，而它的豁免表
  `WHERE_MISSING_EXEMPT` 目前是空的、且該檔就地寫著「**應該保持空的**」。
  本批的檔案邊界不含那個檔（也不該為了自己方便去動全域豁免表），
  所以誠實的做法是：**給一個真的地方，然後把「去了沒用」寫成可被驗證的事實。**
  ⚠️ **但那條全域規則的射程比它看起來窄，本組實測**：它的判準是
  ``[... for _f, _ln, _fn, _w in _where_sites() if _w is None]`` ——
  **看的是「`where=` 這個關鍵字在不在」，不是「它是不是空的」**。
  突變 **M16** 把空狀態改成 ``where=""``（關鍵字還在、值是空字串）→
  **七個全域守衛檔 1001 passed 全綠**，只有本檔的
  :func:`test_nothing_renders_before_holdings_land` 抓到（因為它比對的是
  `where_to_find("pf_add")` 這個**實際字串**有沒有印在畫面上）。

⭐ 本檔實測到的**全域守衛盲點**（登記給後人；不是本頁造成的）
------------------------------------------------------------
下面九條突變**各自對七個全域守衛檔跑過一次**
（`test_ui_grid_contract` / `test_ui_rerun_contract` / `test_wpf_five_tab_wiring` /
`test_batch2_top_card_grid` / `test_ia_switch_advisor_moved_to_portfolio` /
`test_ia_kit` / `test_render_state_color_separation`；基線 **1001 passed, 32 skipped**，
量測日 2026-09-05）。**九條裡只有一條讓全域轉紅。**

======= ========================================== ==================== ==========
突變     內容                                        全域七檔              本檔
======= ========================================== ==================== ==========
M28     呼叫換股顧問既有的渲染函式（第二個渲染點）      **1 failed** ✅       4 failed
M03     拿掉交易帳本的 ``empty_where=``               1001 passed（全綠）    1 failed
M06     保單區塊名改成另一份線框的字面                  1001 passed（全綠）    1 failed
M07     換股顧問改成手抄字面、不走 SSOT                1001 passed（全綠）    1 failed
M12     把線框的示意值畫到畫面上                       1001 passed（全綠）    1 failed
M13     本頁自己開一個**合規的** ``st.columns(3)``     1001 passed（全綠）    1 failed
M14     本頁自己開巢狀 ``st.tabs``                     1001 passed（全綠）    1 failed
M16     空狀態的 ``where`` 改成空字串                  1001 passed（全綠）    2 failed
M25     自己拼 ⬜ 字串、不走 ``not_ready()``            1001 passed（全綠）    2 failed
======= ========================================== ==================== ==========

**四條值得單獨記住的**：

- **M13**：`GRID_EXEMPT_CALL_TOTAL` 是精確 `==`，但它數的是「**欄數不是 3**」的呼叫 ——
  **合規的 3 欄它一動也不動**。所以「本頁不得自己開網格」這條**全域沒有網子**。
  （③ 的紅隊 2026-09-05 先發現了這件事；**本組是自己重跑一次確認的，不是轉述。**）
- **M14**：**巢狀 `st.tabs` 在 `ui/views/**` 沒有任何全域守衛。**
  `tests/test_ia_tab4_ledger_flattened.py` 與
  `test_ia_switch_advisor_moved_to_portfolio.py::test_the_moved_block_opens_no_nested_tabs`
  **都只掃它們各自點名的那一個檔**。而「⚠️ 巢狀 `st.tabs` 一律不留」是線框 Tab 04
  「這裡不放什麼」的逐字條文 —— **本頁自己守，別指望全域。**
- **M16**：見上（`where=""` 穿過去了）。
- **M07**：手抄一個**分區**名（不是分頁名）**不會**讓
  `test_wpf_five_tab_wiring.py` 轉紅 —— 它的黑名單是 `_TAB_LABELS` ∪
  `RETIRED_TAB_LABELS` ∪ `MISWRITTEN_TAB_NAMES`，**`_SECTION_LABELS` 不在裡面**。

⛔ **本段是登記，不是動工授權**（`CLAUDE.md §-1`）。要補全域網子是另一批的事，
且依 §-2 規則 4 不該由本組自己承接。

本檔**已知打不到的地方**（照實寫，不要用形容詞蓋過去）
------------------------------------------------------
- ⛔ **語意維（沒有解）**：灰態斷言驗的是**符號**（⬜）與**常數**（`_PENDING_NOTE`），
  **不驗那句話的意思**。把五個單位的灰態理由**互換**、或在灰態裡塞一句
  投資承諾，本檔**一條都不會響**。這是 ② ③ 被獨立紅隊打穿的同一個維度，
  本檔**沒有比它們好**。
- ⛔ **繞道維（只解掉「字面」那一半）**：
  :func:`test_the_page_never_hand_rolls_the_grey_mark` 只擋得住**字面** `⬜`。
  從 SSOT `from ui.helpers.render_state import NOT_READY_MARK` 再自己拼一句 caption、
  或 `chr(0x2B1C)`，**兩種都繞得過**（③ 已登記同一個洞，本檔沒有修）。
- ⛔ **示意值黑名單只有 `_PINNED_FAKE_VALUES` 那幾個字面寫法。**
  裸數字、全形數字、換算成別的寫法、以及**任何線框以外的捏造值**都抓不到 ——
  黑名單結構上抓不到名單外的第 N+1 個。
- ⛔ **指路挑錯 key 沒有守衛**：職責宣告那一句裡的 `health` / `research` 兩個 key
  換成別的**合法** key，本檔不會有任何東西轉紅。
  **這是「走 SSOT」擋不到的那一類**：SSOT 保證名字不過期，**不保證你挑對了 key**。
  （`_pending_where()` 的 `portfolio` 有守，因為 :func:`test_the_pending_pointer_is_a_place`
  比對的是完整字串。）
- ⛔ **`getattr(st, "columns")(3)` / `from streamlit import columns as _c` 繞得過**
  :func:`test_the_page_draws_no_grid_form_or_tabs_of_its_own`
  —— 但全域 `tests/test_ui_grid_contract.py` 對 alias 同樣失明，
  那是 repo 既有性質，不是本頁造成的（③ 已登記）。
- ⛔ **`_holdings()` 對髒值只測到 `None` / 非 list / 缺旗標三種**；
  舊版 payload 形狀沒有測。

⚠️ 一處**尚未裁決的線框衝突**（本檔只釘住「本批畫成什麼」，不主張它是對的）
--------------------------------------------------------------------------
④ 同時被 `fund-wireframe-final.html`／`policy-split-wireframe.html`／
`ia-wireframe.html` 三份已拍板線框寫過，而三份的**區塊清單幾乎不相交**；
`docs/wireframes/README.md` 明文寫著三者之間的**射程仍未釐清、不替它下結論**。
完整並陳與三條「本批為什麼畫 ia 那一份」的依據，寫在
`ui/views/page_04_portfolio.py` 的模組 docstring。
⛔ **本檔的斷言是「骨架長得跟 ia Tab 04 一樣」，不是「ia Tab 04 是對的」。**
   總管裁決若判定 ④ 應含 policy-split 的區塊，**本檔多條會轉紅 —— 那時是要改本檔，
   不是要把它放寬。**
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
SRC = ROOT / "ui" / "views" / "page_04_portfolio.py"

#: 灰態的視覺記號（`ui/helpers/render_state.py::NOT_READY_MARK`）。
#: ⚠️ **從那個模組 import，不在這裡抄一份字面值** —— 抄了就是第二份真相源。
from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import section_label, where_to_find  # noqa: E402
from ui.views.page_04_portfolio import (  # noqa: E402
    BLOCK_DIVIDEND_CAL,
    BLOCK_FORM,
    BLOCK_LEDGER,
    BLOCK_MIX,
    BLOCK_POLICY,
    SUBMIT_LABEL,
    _DEFAULT_BUDGET_TWD,
    _DEFAULT_CORE_PCT,
    _DEFAULT_SATELLITE_ONLY,
    _LABEL_BUDGET,
    _LABEL_CORE_PCT,
    _LABEL_SATELLITE_ONLY,
    _PENDING_NOTE,
    _holdings,
    _normalise_plan,
    _pending_where,
    switch_block_label,
)

#: AppTest 跑的 script。**只做兩件事**：把 repo 根加進 `sys.path`、呼叫被測 View。
#: ⚠️ 刻意**不**走 `app.py` —— 本頁本批尚未接線（客戶明令舊 ④ 不動），
#:    `AppTest.from_file("app.py")` 到不了這裡。
_SCRIPT = (
    f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
    "from ui.views.page_04_portfolio import render_asset_allocation\n"
    "render_asset_allocation()\n"
)

#: 一份「已載入」的持倉。形狀就是 `ui/helpers/portfolio/load.py` 寫進 session 的那個。
FAKE_HOLDINGS: list[dict[str, Any]] = [
    {"code": "TESTCODE1", "name": "測試標的一", "loaded": True},
    {"code": "TESTCODE2", "name": "測試標的二", "loaded": True},
]


def _app(funds: list[dict[str, Any]] | None) -> Any:
    """跑一次整頁，回傳 `AppTest`。`funds=None` 代表 session 裡根本沒有那個鍵。"""
    _at = AppTest.from_string(_SCRIPT, default_timeout=120)
    if funds is not None:
        _at.session_state["portfolio_funds"] = funds
    _at.run()
    assert not _at.exception, (
        "整頁渲染時拋了未捕捉例外 —— 骨架連跑都跑不起來：\n"
        + "\n".join(str(_e.value) for _e in _at.exception))
    return _at


def _flat(node: Any) -> list[str]:
    """把 AppTest 的元素樹壓成**有序**的一串字。

    ⚠️ 回傳 list 而不是一整塊字串 —— 順序本身是本檔要驗的東西之一，
    join 成一坨就驗不了「哪一句落在哪一塊底下」。
    ⚠️ **走 `children` 這個 dict 並依 key 排序**：直接 `for c in block` 會無限遞迴
    （Block 的 `__iter__` 會把自己也走進去），這一點是實跑撞到的，不是推論。
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
    - `"loaded"`  —— 兩檔已載入
    """
    _funds = {"empty": [], "missing": None, "loaded": FAKE_HOLDINGS}[kind]
    return tuple(_flat(_app(_funds).main))


def _text(parts: tuple[str, ...] | list[str]) -> str:
    return "\n".join(parts)


#: 一級區塊標題（`st.markdown("#### …")`）。
_L4_OPEN = re.compile(r"^\[Markdown\] #{4}\s+(.*)$")
#: 一張卡的標題 —— `ia.state_card()` 在灰態時畫的 `st.markdown(f"**{title}**")`。
#: ⚠️ **這一條是本檔的最小單位，不是裝飾**（理由見 :func:`_units`）。
_CARD_OPEN = re.compile(r"^\[Markdown\] \*\*(.+)\*\*$")


def _units(parts: tuple[str, ...] | list[str]) -> list[tuple[str, list[str]]]:
    """把渲染流切成**有序**的最小單位：一級段落，或**一張卡**。

    ⚠️ **粒度是「一張卡」，這是被 ② 的一次突變逼出來的，不是設計出來的。**
    `tests/test_wf02_health_skeleton.py::_units` 記著：初版只依 `#### 區塊名` 切段，
    突變「只拿掉其中一塊的灰態」**沒有轉紅** —— 因為同一段裡別張卡的 ⬜ 替它過關了。
    同一個形狀在 ① 被獨立稽核連續打穿兩輪。**答案每次都一樣：把邊界往下降。**

    ⛔ **不要為了讓斷言好寫而把邊界往上收。** 邊界一寬，鄰居的字就會替你通過。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _m = _L4_OPEN.match(_p) or _CARD_OPEN.match(_p)
        if _m:
            _out.append((_m.group(1).strip(), []))
            continue
        if _out:
            _out[-1][1].append(_p)
    return _out


def _segments(parts: tuple[str, ...] | list[str]) -> dict[str, list[str]]:
    """`單位名 -> 該單位內的渲染紀錄`（:func:`_units` 的 dict 檢視）。

    ⚠️ **dict 會讓同名單位後者覆蓋前者** —— 那正是 ② 被紅隊打穿的繞道。
    本檔用 :func:`test_unit_names_are_unique` 把「不會有同名單位」變成一條**斷言**，
    而不是一個假設。
    """
    return {_k: _v for _k, _v in _units(parts)}


def _expected_units() -> tuple[str, ...]:
    """線框 Tab 04 由上而下的六個單位。**`換股顧問` 走 SSOT，不在這裡抄字面。**"""
    return (BLOCK_MIX, BLOCK_FORM, switch_block_label(),
            BLOCK_POLICY, BLOCK_DIVIDEND_CAL, BLOCK_LEDGER)


def _grey_units() -> tuple[str, ...]:
    """**每一個都要各自帶灰態**的五個單位。

    ⚠️ `BLOCK_FORM` 不在這裡：它是本批**唯一真的做完**的一塊，
    由 :func:`test_the_form_block_is_not_grey` 反向守著（它一旦變灰，那條就紅）。
    """
    return tuple(_u for _u in _expected_units() if _u != BLOCK_FORM)


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


def _imported_modules(tree: ast.AST) -> list[str]:
    _mods: list[str] = []
    for _n in ast.walk(tree):
        if isinstance(_n, ast.Import):
            _mods.extend(_a.name for _a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.append(_n.module)
    return _mods


# ══════════════════════════════════════════════════════════════════
# 骨架：六個單位都在、順序對、名字唯一
# ══════════════════════════════════════════════════════════════════

def test_all_units_are_present_and_in_wireframe_order():
    """有持倉之後：核心／衛星 → 再平衡試算 → 換股顧問 → 保單 → 配息月曆 → 交易帳本。

    順序不是美感問題：線框把「現況 vs 建議」擺在最前面，是因為**先知道差多少，
    才知道要不要調** —— 把試算 Form 擺到現況前面，等於要使用者先填一個
    他還不知道該填什麼的目標值。

    ⚠️ **這一條同時是三份線框衝突的紀錄點**：它釘的是 `ia-wireframe.html` Tab 04
    的清單與順序。若總管裁決 ④ 應含 `policy-split-wireframe.html` 的區塊，
    **本條會轉紅 —— 那時是要改本條，不是要把它放寬。**
    """
    _parts = _stream("loaded")
    _names = [_k for _k, _ in _units(_parts)]
    assert _names == list(_expected_units()), (
        f"單位順序與線框 Tab 04 不符：\n實際：{_names}\n應為：{list(_expected_units())}")


def test_unit_names_are_unique():
    """**單位名不得重複** —— 這條堵的是 ② 被紅隊打穿的那條繞道。

    ② 的 `_segments()` 回傳 dict，**同名單位後者覆蓋前者**；紅隊因此可以
    「把真區塊掏空、另造一個同名誘餌帶著灰態」→ 全綠。
    只要單位名保證唯一，dict 檢視就不會遮蔽任何東西。

    ⚠️ 這條同時是 :func:`_segments` 的**前提** —— 它紅了，所有用 `_segments()`
    的斷言都要重新看，不是只有這一條。
    """
    for _kind in ("empty", "missing", "loaded"):
        _names = [_k for _k, _ in _units(_stream(_kind))]
        _dupes = sorted({_n for _n in _names if _names.count(_n) > 1})
        assert not _dupes, (
            f"（{_kind}）出現同名單位 {_dupes} —— "
            "`_segments()` 的 dict 檢視會讓後者覆蓋前者，"
            "等於在灰態斷言上開一道後門。請把段落名改成唯一。")


def test_the_block_names_are_the_wireframe_wording_verbatim():
    """四個區塊名**逐字對 `ia-wireframe.html` Tab 04**。

    ⚠️ **釘線框的字面值，不是釘模組常數**（③ 的第二輪突變 M02 抓到的坑）：
    如果寫成 `assert BLOCK_MIX == BLOCK_MIX` 那種從被測模組 import 進來的自我參照，
    改常數時兩邊一起變，斷言**永遠是 True**。這裡右邊是**寫死的線框字面**。

    ⚠️ `保單與扣款標的` 是**未裁決**的名字（`policy-split-wireframe.html` 把 ④ 那一區
    改名「📋 保單資料」）—— 本條釘的是「本批畫成什麼」，**不是**「它是對的」。
    裁決若改用另一個名字，改 `BLOCK_POLICY` 一個常數 ＋ 本條一行即可。
    """
    assert BLOCK_MIX == "核心 ／ 衛星現況 vs 建議", (
        f"`BLOCK_MIX` 是 {BLOCK_MIX!r} —— 線框 Tab 04 那張全寬卡逐字是這個。")
    assert BLOCK_FORM == "再平衡試算", (
        f"`BLOCK_FORM` 是 {BLOCK_FORM!r} —— 線框寫的是「Form ─ 再平衡試算」。")
    assert BLOCK_POLICY == "保單與扣款標的", (
        f"`BLOCK_POLICY` 是 {BLOCK_POLICY!r} —— 線框 Tab 04 逐字是這個。")
    assert BLOCK_DIVIDEND_CAL == "配息月曆", (
        f"`BLOCK_DIVIDEND_CAL` 是 {BLOCK_DIVIDEND_CAL!r} —— 線框 Tab 04 逐字是這個。")
    assert BLOCK_LEDGER == "交易帳本", (
        f"`BLOCK_LEDGER` 是 {BLOCK_LEDGER!r} —— 線框 Tab 04 逐字是這個。")


def test_the_switch_block_name_comes_from_the_ssot_not_a_hand_copy():
    """換股顧問那一塊**必須**吃 `story_nav.section_label('switch')`，不得手抄線框字面。

    ## 為什麼這一塊與其他四塊處理不同

    `ui/helpers/story_nav.py::_SECTION_LABELS["switch"]` **已經是這個分區的 SSOT**，
    而且它的就地註解逐字寫著它來自「2026-09-01（客戶拍板線框 `ia-wireframe.html` Tab 04）」。
    ④ 裡已經有人在用它（`ui/helpers/fund_grp_health/switch_advisor_section.py`
    的 `st.subheader(f"{_section_label('switch')}…")`）。
    本頁若手抄一次線框的「換股顧問」，**同一個區塊在 ④ 就有兩個名字** ——
    那正是 `story_nav` 整個模組在防的事（本 repo 死指路已發作三次）。

    ## 兩件事分開驗，避免自我參照的恆真式

    (a) 畫面上那個單位名 **等於** `section_label("switch")`（跨模組比對，不是自己比自己）；
    (b) 被測檔的**活字串裡沒有**「換股顧問」四個字（手抄當場轉紅）。
    """
    _seg = _segments(_stream("loaded"))
    assert section_label("switch") in _seg, (
        f"畫面上找不到 `section_label('switch')` ＝ {section_label('switch')!r} 這個單位。\n"
        f"現有單位：{list(_seg)}")
    _bad = [f"第 {_n.lineno} 行 {_n.value[:40]!r}"
            for _n in _live_strings(_tree()) if "換股顧問" in _n.value]
    assert not _bad, (
        "本頁把「換股顧問」手抄成活字串了 —— 這個分區已經有 SSOT "
        "（`story_nav.section_label('switch')`），手抄會讓 ④ 出現兩個名字：\n  "
        + "\n  ".join(_bad))


# ══════════════════════════════════════════════════════════════════
# 鐵則 02 / 04：沒有持倉就什麼都不畫
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("kind", ["empty", "missing"])
def test_nothing_renders_before_holdings_land(kind: str):
    """一檔持倉都沒有 → 只有空狀態三要素，下面**四塊都不畫**。

    線框 Rule 04：「無資料不畫空表格外框，改用空狀態三要素：標題、缺什麼、去哪補」。

    ⚠️ 兩種 session 形狀都測：**空 list** 與 **鍵根本不存在**（第一次進站）。
    前三頁的同型守衛只測了一種，而「`.get()` 回 `None` 時炸掉」是真的會發生的。
    """
    _parts = _stream(kind)
    _seg = _segments(_parts)
    _leaked = [_u for _u in _expected_units() if _u in _seg]
    assert not _leaked, (
        f"（{kind}）還沒有持倉就畫出了 {_leaked} —— 空狀態應**取代**它們。")
    _all = _text(_parts)
    assert "尚未設定持倉" in _all, f"（{kind}）沒有空狀態的標題。\n{_all}"
    assert "還沒有任何已載入的保單或扣款標的" in _all, (
        f"（{kind}）空狀態缺了「缺什麼」這一要素。\n{_all}")
    assert where_to_find("pf_add") in _all, (
        "空狀態的「去哪補」沒有指到加入基金的地方 —— "
        f"應含 `where_to_find('pf_add')` ＝ {where_to_find('pf_add')!r}。\n{_all}")


def test_the_empty_state_does_not_also_print_the_pending_excuse():
    """兩種灰不得混在一起。

    ⚠️ 這條擋的是一個很容易犯、而且看起來無害的錯：沒有持倉時**同時**印出
    「本頁分批上線」的灰字。使用者會以為「加了基金就會看到配置建議」—— 不會，
    加完看到的是另一種灰。**一次只給一個下一步。**

    ⚠️ 比對 `_PENDING_NOTE` 本體，**不硬抄字面值**。硬抄的話，常數一改措辭
    這條就永遠是 True —— 它守的 bug 照樣存在、而它不再看得見。
    """
    for _kind in ("empty", "missing"):
        _all = _text(_stream(_kind))
        assert _PENDING_NOTE not in _all, (
            f"（{_kind}）沒有持倉時不應同時印出「內容還沒接上」的灰字 —— "
            "兩個下一步會互相抵消。\n" + _all)


def test_the_empty_state_pointer_actually_works():
    """⭐ **照著空狀態的指路做，這一頁真的會離開空狀態** —— 實跑，不是推論。

    指路寫的是「④ 📊 資產配置 → ➕ 加入與管理基金」，而那個區塊做的事就是
    把基金寫進 `portfolio_funds`（`ui/tab3_portfolio.py` 現行 ④ 真的有
    `### ➕ 加入與管理基金` 這個標題）。本條**在同一個 AppTest session 裡**
    模擬「使用者照著做完了」：把已載入的持倉放進 session，再跑一次。

    ⛔ **本條驗的是「機制通了」，不驗「那個按鈕長什麼樣」** ——
    AppTest 到不了舊 ④（本頁尚未接線），所以它按不到那顆真的按鈕。
    **本條證明的是：那句指路描述的那件事一旦發生，這一塊真的會換掉。**

    ⚠️ **它同時是未決事項 (A) 的哨兵**：`ia-wireframe.html` Tab 04 的清單裡
    **沒有**「加入與管理基金」。若 ④ 日後真的被收斂成 ia 的六塊，這句指路會變成
    死指路（而且使用者將無處可加基金）—— 那時要改的是線框的裁決，不是這條測試。
    """
    _at = _app([])
    assert any("尚未設定持倉" in _p for _p in _flat(_at.main)), "起手式應該是空狀態。"
    # 照著指路做：那個區塊做的事 ＝ 把已載入的基金寫進 `portfolio_funds`。
    _at.session_state["portfolio_funds"] = FAKE_HOLDINGS
    _at.run()
    _after = _flat(_at.main)
    assert not any("尚未設定持倉" in _p for _p in _after), (
        "照著空狀態的指路做完之後，空狀態**還在** —— 那句指路是無效的。\n"
        + _text(_after))
    _names = [_k for _k, _ in _units(_after)]
    assert _names == list(_expected_units()), (
        "照著做之後，四塊沒有如預期出現。\n"
        f"實際：{_names}\n應為：{list(_expected_units())}")


# ══════════════════════════════════════════════════════════════════
# 灰態：五個單位各自誠實
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("unit", _grey_units())
def test_every_grey_unit_is_grey_until_its_content_lands(unit: str):
    """有持倉、但內容還沒接上 → 每一個單位**各自**要有灰態記號與理由。

    ⚠️ **斷言的單位是「一段」或「一張卡」，不是整頁，也不是整塊。**
    ② 的初版以「一級區塊」為單位，突變「只拿掉其中一塊的灰態」**沒有轉紅**
    （同一段裡別張卡的 ⬜ 替它通過了）—— 粒度因此下降。詳見 :func:`_units` 的長註。

    ⚠️ **下一批把真內容接上時，這條會轉紅 —— 那是預期的。**
    屆時請把它改成「真內容放行」，**不要把它放寬成「有東西就好」**。
    """
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」有標題但沒有任何內容 —— 那是空占位。"
    assert NOT_READY_MARK in _body, (
        f"單位「{unit}」沒有灰態記號 {NOT_READY_MARK!r} —— "
        "內容還沒接上就要誠實留灰，不得空著也不得填示意值（§1）。\n" + _body)
    assert _PENDING_NOTE in _body, (
        f"單位「{unit}」的灰態沒說「為什麼沒有」。\n" + _body)


@pytest.mark.parametrize("unit", _grey_units())
def test_every_grey_unit_says_where_to_look(unit: str):
    """每一個灰態單位**各自**要有「去哪補」，而且不得手抄分頁名。

    ## ⚠️ 粒度必須是「一個單位」，整頁 containment 會被打穿

    **以下是 ③ 的紀錄，本組照抄，沒有重跑**（`CLAUDE.md §-2` 規則 6）：
    ③ 的同型守衛原本是 `assert where_to_find(...) in 整頁`，紅隊拿掉三處
    `wide_table(empty_where=)` → 該組記載「**1007 passed，一條都沒響**」，
    而畫面上那三塊**真的失去了「（請先到：…）」**。兩個原因疊在一起：
    全域網子（`tests/test_batch2_top_card_grid.py::_where_sites`）
    **不收 `wide_table(empty_where=)` 這個形狀**，而該守衛當時的粒度是整頁。

    ✅ **本組自己驗的是這一條**：本檔的 `wide_table(empty_where=)`（交易帳本那一塊）
    被拿掉時（突變 **M03**）—— **七個全域守衛檔 1001 passed 全綠**，
    只有本條轉紅。**也就是那個形狀今天仍然在全域網子的射程外。**
    → **本檔從第一版就是逐單位。**

    ⚠️ 這條驗的是「**有沒有指路**」，**不驗「照著做有沒有用」** ——
    後者由 :func:`test_the_pending_pointer_is_honest_about_being_ineffective` 實跑，
    而且答案是**沒用**。兩件事不要混為一談。
    """
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」不見了。"
    assert where_to_find("portfolio") in _body, (
        f"單位「{unit}」的灰態沒有「去哪補」—— 指路要走 `where_to_find('portfolio')`，"
        "手抄的分頁名在本 repo 已經指錯三次（見 `story_nav.RETIRED_TAB_LABELS`）。\n"
        + _body)
    assert BLOCK_FORM in _body, (
        f"單位「{unit}」指路提到的「{BLOCK_FORM}」在畫面上找不到 —— "
        "指到一個使用者看不到的名字，等於沒有指路。")


def test_the_pending_pointer_is_a_place_not_a_status_sentence():
    """`_pending_where()` 回傳的必須是一個**地方**，不是一句狀態陳述。

    ## 這條是 ③ 的紅隊突變 R5 逼出來的（本檔從第一版就帶著它）

    ③ 的 `_pending_where()` 原本回傳
    ``f"{where_to_find('research')} → 目前只有「{block}」是完整的"``，
    而 `render_state.not_ready()` 會把它包成「（請先到：…）」——
    畫面上於是印出一句**不可執行的指令**：「請先到：③ … → 目前只有「搜尋條件」是完整的」。
    修好之後 ③ 把它退回舊寫法重跑，**1014 passed 一條都沒紅** ——
    也就是**修好了渲染，卻沒有任何東西在防它退回去**。

    ## 判準用**結構相等**，不用關鍵字黑名單

    黑名單（「不准出現『完整』兩個字」之類）只擋得住上一次那個寫法，換個措辭就繞過。
    本條直接釘住組成：**分頁路徑 ＋ `→` ＋ 區塊名**，中間不得夾任何述語。
    """
    for _block in (BLOCK_FORM, "任意區塊名"):
        assert _pending_where(_block) == f"{where_to_find('portfolio')} → {_block}", (
            f"`_pending_where({_block!r})` ＝ {_pending_where(_block)!r}\n"
            "它會被 `render_state.not_ready()` 包成「（請先到：…）」——"
            "所以它必須是一個**地方**（分頁路徑 → 區塊名），不能是一句狀態陳述。")
    # 也驗它進到畫面上之後的形狀，不是只驗回傳值。
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(BLOCK_MIX, []))
    assert f"（請先到：{where_to_find('portfolio')} → {BLOCK_FORM}）" in _body, (
        "畫面上那句「請先到：…」不是預期的地方字串。\n" + _body)


def test_the_pending_pointer_is_honest_about_being_ineffective():
    """⭐ **照著灰態的指路做，這一頁「不會」離開灰態** —— 本條把那個事實釘成斷言。

    ## 這條為什麼要存在（它看起來像在測一個 bug）

    被測檔的 `_pending_where()` docstring 就地寫著「這一族的指路有效性有限」。
    **一句寫在註解裡的自陳，沒有任何東西在守它** —— 而本 repo 的病史一再證明：
    沒有守衛的自陳，會在下一次改動時默默變成假話。

    本條實跑「使用者照著做」：回到「再平衡試算」，填一個金額，按下「試算」。
    **結果：五條灰態逐字完全相同。** 本條把它變成一個會轉紅的事實。

    ## ⚠️ 這條紅了代表什麼（不要直覺地把它刪掉）

    - **下一批把內容接上了** → 它會紅，因為灰態真的消失了。
      **正解是刪掉本條、並把 `_pending_where()` 的 docstring 那段一起改掉**，
      而不是把它放寬。
    - **有人把指路改成一個「照著做真的有用」的地方** → 它也會紅。那是好事，
      同樣是刪本條 ＋ 改文案，不是繞過。
    """
    _at = _app(FAKE_HOLDINGS)
    _before = [_p for _p in _flat(_at.main) if NOT_READY_MARK in _p]
    assert len(_before) == len(_grey_units()), (
        f"有持倉時應該剛好 {len(_grey_units())} 條灰態，實際 {len(_before)} 條：\n"
        + _text(_before))
    # 照著指路做：回到「再平衡試算」，填金額、按「試算」。
    _at.number_input[0].set_value(150_000)
    _at.button[0].click()
    _at.run()
    assert not _at.exception, "按下「試算」之後整頁炸了。"
    _after = [_p for _p in _flat(_at.main) if NOT_READY_MARK in _p]
    assert _after == _before, (
        "照著灰態的指路做完之後，灰態**變了** —— 那麼被測檔 `_pending_where()` 的 "
        "docstring（「這一族的指路去了也沒用」）就是假話，要一起改。\n"
        f"之前：{_before}\n之後：{_after}")


def test_the_form_block_is_not_grey():
    """再平衡試算那一塊**不得**是灰的 —— 它是本批唯一真的做完的一塊。

    ⚠️ 這是**反向**斷言，存在的理由是：所有灰態的指路都指向它。
    它哪天自己也變灰了，整頁的指路就會指向一塊同樣沒做完的東西 ——
    那時使用者拿到的是一個閉環。
    """
    _seg = _segments(_stream("loaded"))
    _body = "\n".join(_seg.get(BLOCK_FORM, []))
    assert _body.strip(), f"單位「{BLOCK_FORM}」不見了。"
    assert NOT_READY_MARK not in _body, (
        f"「{BLOCK_FORM}」變成灰態了 —— 它是本批唯一做完的一塊，"
        "而且是所有灰態指路的終點。\n" + _body)
    for _lbl in (_LABEL_CORE_PCT, _LABEL_BUDGET, _LABEL_SATELLITE_ONLY):
        assert any(_lbl in _p for _p in _seg[BLOCK_FORM]), (
            f"「{BLOCK_FORM}」少了「{_lbl}」這個欄位。\n" + _body)


def test_the_page_never_hand_rolls_the_grey_mark():
    """⛔ 不准自己拼 ⬜ 字串 —— 灰態一律委派 `render_state` / `ia` 的入口。

    ⚠️ 這條堵的是 ② 被紅隊打穿的繞道：**手刻 `st.markdown("⬜ …")` 不走
    `not_ready()`，也照樣被灰態斷言認成灰態。** 自己拼的 ⬜ 不會有 `where=`、
    不會跟著 `render_state` 的視覺一起變，等於在 SSOT 旁邊長出第二套灰。

    ⛔ **只擋得住字面值。** 從 SSOT import `NOT_READY_MARK` 再自己拼、
    或 `chr(0x2B1C)`，**兩種都繞得過**（③ 已登記同一個洞，本檔沒有修）。
    """
    _bad = [f"第 {_n.lineno} 行 {_n.value[:40]!r}"
            for _n in _live_strings(_tree()) if NOT_READY_MARK in _n.value]
    assert not _bad, (
        f"本頁的活字串裡出現了 {NOT_READY_MARK!r} —— 灰態請走 "
        "`ui.helpers.render_state.not_ready()` / `ui.helpers.ia.empty_state()` / "
        "`state_card(state=STATE_NOT_READY)`：\n  " + "\n  ".join(_bad))


# ══════════════════════════════════════════════════════════════════
# Form：三個欄位、一個刻意的偏離、以及「0 不算送出」
# ══════════════════════════════════════════════════════════════════

def test_the_three_fields_and_the_submit_verb_come_from_the_wireframe():
    """線框 Tab 04 的 Form 逐字：「目標核心比例」「可動用金額」「只調衛星」「試算」。

    ⚠️ **送出鈕的字是「試算」不是「套用」** —— `ui.helpers.ia.APPLY_LABEL` 的預設值是
    「套用」，線框 Tab 04 明確畫的是「試算」。這不是文案潔癖：
    使用者要知道按下去會發生什麼，「套用」在一個模擬器上不知所云。

    ⚠️ **標籤上多的單位是刻意的**：畫面上是「目標核心比例（%）」「可動用金額（TWD）」。
    線框把單位寫在**值**上（「70%」「TWD 200,000」），而本 repo 的
    `CLAUDE.md §4.1` 要求「新增變數**必須**編碼單位」，且本 repo 真的有多幣別基金 ——
    一個沒有幣別的金額框正是那一節點名的陷阱。故單位進標籤，**線框的字一個沒少**。
    """
    assert (_LABEL_CORE_PCT, _LABEL_BUDGET, _LABEL_SATELLITE_ONLY) == (
        "目標核心比例", "可動用金額", "只調衛星"), (
        "欄位標籤被改了 —— 線框 Tab 04 的 Form 逐字寫的是這三個。")
    assert SUBMIT_LABEL == "試算", (
        f"`SUBMIT_LABEL` 被改成 {SUBMIT_LABEL!r} —— 線框 Tab 04 的送出鈕是「試算」。")
    _at = _app(FAKE_HOLDINGS)
    assert [_s.label for _s in _at.slider] == [f"{_LABEL_CORE_PCT}（%）"]
    assert [_n.label for _n in _at.number_input] == [f"{_LABEL_BUDGET}（TWD）"]
    assert [_c.label for _c in _at.checkbox] == [_LABEL_SATELLITE_ONLY]
    assert [_b.label for _b in _at.button] == [SUBMIT_LABEL], (
        "整頁的按鈕不是「恰好一顆送出鈕」—— 骨架階段不該有第二顆按鈕。")


def test_the_budget_default_deviates_from_the_wireframe_on_purpose():
    """⚠️ 可動用金額預設 **0**，**刻意不照線框的 TWD 200,000**。

    這是本檔唯一一處偏離線框字面的地方，理由寫在被測檔的模組 docstring：
    **那是使用者的錢，不是模擬參數。** 預先填一個金額，使用者只要沒注意到，
    就會拿到一份「用他沒有的 20 萬」算出來的再平衡計畫（`CLAUDE.md §1`）。

    另外兩個預設值**照線框**：目標核心比例 70、只調衛星勾選。
    ⚠️ 70 這個數字同時是線框那張卡的示意「建議 70 ／ 30」——
    **本檔畫 Form 的預設值、不畫卡片上的建議值**，分界見被測檔 docstring。
    """
    assert _DEFAULT_BUDGET_TWD == 0, (
        f"`_DEFAULT_BUDGET_TWD` 變成 {_DEFAULT_BUDGET_TWD!r} —— "
        "預填一個金額會讓使用者拿到一份用他沒有的錢算出來的計畫（§1）。")
    assert _DEFAULT_CORE_PCT == 70, "線框 Tab 04 的 Form 寫的是「目標核心比例　70%」。"
    assert _DEFAULT_SATELLITE_ONLY is True, "線框 Tab 04 的「只調衛星」是勾起來的（☑）。"
    _at = _app(FAKE_HOLDINGS)
    assert _at.number_input[0].value == 0
    assert _at.slider[0].value == 70
    assert _at.checkbox[0].value is True


def test_a_zero_budget_never_counts_as_applied():
    """沒有可動用金額 → **不算送出** —— 這是本頁唯一一條 §1 邏輯，所以它要有自己的測試。

    再平衡試算回答的是「這筆錢怎麼分」。硬把 0 當成一次有效試算，
    畫面會停在一份與任何投入都無關的結果上。

    ⚠️ 兩個層次都測：純函式（快、精確）＋ AppTest 實跑（證明它真的接在送出路徑上）。
    只測純函式的話，有人把 `_normalise_plan` 從 `_render_rebalance_form` 拆掉，
    這條照樣全綠。
    """
    assert _normalise_plan(70, 0, True) is None
    assert _normalise_plan(70, None, True) is None
    assert _normalise_plan(70, -1, True) is None
    assert _normalise_plan(70, 150_000, True) == {
        "core_pct": 70, "budget_twd": 150_000, "satellite_only": True}
    # 實跑：預設 0，直接按「試算」→ 不得寫進任何已送出條件。
    _at = _app(FAKE_HOLDINGS)
    _at.button[0].click()
    _at.run()
    assert _at.session_state["v04_portfolio_applied_plan"] is None, (
        "金額 0 的送出被當成一次有效試算了。")
    # 對照組：填了金額才算數。
    _at2 = _app(FAKE_HOLDINGS)
    _at2.number_input[0].set_value(150_000)
    _at2.button[0].click()
    _at2.run()
    assert _at2.session_state["v04_portfolio_applied_plan"] == {
        "core_pct": _DEFAULT_CORE_PCT, "budget_twd": 150_000,
        "satellite_only": _DEFAULT_SATELLITE_ONLY}, (
        "填了金額按下試算，卻沒有寫進已送出條件 —— 那個閘門根本沒接上。")


def test_downstream_reads_the_applied_plan_not_the_widget_values():
    """試算的**已送出值**與 widget 當下值必須是兩個東西。

    ⚠️ 這條守的是鐵則 02 真正的那一半。只包 `st.form` 只擋住「widget 互動觸發 rerun」，
    **沒有擋住重運算** —— 每次 rerun 照樣把下游跑一遍，畫面看起來沒問題、成本一分沒省
    （`ui/helpers/ia/gated_form.py` 模組 docstring 把這個陷阱寫得很清楚）。

    ⚠️ **這條分不出真假閘門**（② 的紅隊實測：`if True:` 與 `if not _gate:` 都全綠）——
    它只驗「session 寫入有沒有被某個 `if` 包住」。**登記，本批不補。**
    ✅ 但 :func:`test_a_zero_budget_never_counts_as_applied` 的 AppTest 那半
    **會**抓到「閘門恆真」那一種（沒按也寫進去）。兩條互補。
    """
    _t = _tree()
    _fns = {_n.name: _n for _n in ast.walk(_t) if isinstance(_n, ast.FunctionDef)}
    for _need in ("_applied_plan", "_normalise_plan"):
        assert _need in _fns, (
            f"找不到 `{_need}()` —— 「已送出值」這一層被拿掉了，"
            "下游就會直接讀 widget 值，等於沒有 form。")
    _form_fn = _fns["_render_rebalance_form"]
    _writes = [_n for _n in ast.walk(_form_fn)
               if isinstance(_n, ast.Assign)
               and any(isinstance(_t2, ast.Subscript) for _t2 in _n.targets)]
    assert _writes, "`_render_rebalance_form()` 沒有把送出結果寫回 session。"
    _guarded: list[int] = []
    for _if in ast.walk(_form_fn):
        if isinstance(_if, ast.If):
            _guarded.extend(id(_n) for _n in ast.walk(_if)
                            if isinstance(_n, ast.Assign))
    _naked = [_w for _w in _writes if id(_w) not in _guarded]
    assert not _naked, (
        "有 session 寫入**沒有**被送出閘門包住 —— 那代表每次 rerun 都會覆寫已送出值，\n"
        "使用者拖滑桿的當下就會觸發下游重算，form 等於白包。\n  "
        + "\n  ".join(f"第 {_w.lineno} 行" for _w in _naked))


# ══════════════════════════════════════════════════════════════════
# §1：線框的示意值一個都不准畫
# ══════════════════════════════════════════════════════════════════

#: 本條**實際釘住**的字面值 —— 線框 Tab 04 四張示意卡與 Form 上的東西。
#: 列成常數，是為了讓「它到底守了什麼」可以被讀出來，而不是藏在 docstring 的形容詞裡。
_PINNED_FAKE_VALUES: tuple[str, ...] = (
    "現況 62 ／ 38", "建議 70 ／ 30", "62 ／ 38", "70 ／ 30",
    "2 組建議", "3 張保單", "本月 4 筆",
    "TWD 200,000", "200,000",
)


def test_the_grey_blocks_never_print_the_illustrative_values_from_the_wireframe():
    """⛔ 線框那幾張示意卡上的東西不准出現在畫面上（**只涵蓋下列字面寫法**）。

    為什麼要有這條：填一個看起來合理的核心／衛星比例，使用者**完全看不出它是假的**，
    而且會拿它去調真的部位（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ## ⚠️ 這條**實際**守得到什麼（照實寫，不要用形容詞）

    **只釘 `_PINNED_FAKE_VALUES` 這 9 個字面寫法。**
    **明確守不到**：裸數字（`62` / `38` 不帶那個全形斜線）、半形斜線的寫法、
    以及**任何線框以外的捏造值** —— 黑名單結構上抓不到名單外的第 N+1 個。

    ## ⚠️ 一個**刻意的例外**：Form 上的預設值 70

    `70` 是線框給「目標核心比例」的預設值（一個**使用者可以改的參數**），
    同時也出現在示意卡的「建議 70 ／ 30」（一個**系統宣稱的事實**）。
    本條釘的是後者那個**組合字串**（`"70 ／ 30"`），**不釘裸的 70** ——
    釘裸數字會把 Form 的合法預設值一起打紅。
    """
    for _kind in ("empty", "missing", "loaded"):
        _all = _text(_stream(_kind))
        for _fake in _PINNED_FAKE_VALUES:
            assert _fake not in _all, (
                f"（{_kind}）畫面上出現了線框的示意值 {_fake!r} —— "
                "那不是資料，是線框用來示範版面的假數字。")


def test_the_ledger_invents_no_column_list():
    """⛔ 交易帳本**不准**自己發明一份欄位清單。

    線框對交易帳本**只寫了內容類型**（買賣紀錄／成本／已實現損益／對帳），
    **沒有像 Tab 02 那樣逐欄列舉**。憑印象補一份欄位表，
    下一批接真資料時就會發現欄位對不上 —— 那是自己發明規格。

    ⛔ **對照**：`page_02_health.py::HEALTH_TABLE_COLUMNS` 之所以能釘住 9 欄，
    是因為**線框真的逐字列了那 9 欄**。這裡沒有，所以這裡不釘。

    ⚠️ 判準是「模組層有沒有一個看起來像欄位表的常數」，不是「畫面上有沒有欄位名」——
    後者在骨架階段恆為真（表是空的），驗不到任何東西。
    """
    _bad = [_t.id for _n in ast.walk(_tree()) if isinstance(_n, ast.Assign)
            for _t in _n.targets
            if isinstance(_t, ast.Name) and "COLUMN" in _t.id.upper()]
    assert not _bad, (
        f"被測檔多了看起來像欄位清單的常數：{_bad}\n"
        "線框對交易帳本沒有列欄位 —— 補一份等於自己發明規格。")


# ══════════════════════════════════════════════════════════════════
# 邊界：走共用元件、不碰底層、不委派舊頁、不搶別人的渲染點
# ══════════════════════════════════════════════════════════════════

def test_the_page_draws_no_grid_form_or_tabs_of_its_own():
    """鐵則 01 / 02 一律走共用元件；巢狀 `st.tabs` 一個都不准有。

    ⚠️ **`st.columns` 那半只有本條在守。** 全域
    `tests/test_ui_grid_contract.py::GRID_EXEMPT_CALL_TOTAL` 抓的是「**欄數不是 3**」
    的呼叫 —— 合規的 `st.columns(3)`（＝鐵則 01 叫你開的那個）它**一動也不動**
    （③ 的獨立紅隊 2026-09-05 實測）。
    ⚠️ **`st.form` 那半有全域網子**：`FORM_SITE_TOTAL` 是精確 `==`，多一個站點就紅。
    ⚠️ **`st.tabs` 是線框 Tab 04 的「這裡不放什麼」逐字**：
       「⚠️ **巢狀 `st.tabs` 一律不留**；分頁只有一層」。

    ⛔ **本條擋得住的只有這三個 attribute 名。** `getattr(st, "columns")(3)` 與
    `from streamlit import columns as _c` 都繞得過 —— 但全域那條對 alias 同樣失明，
    那是 repo 既有性質，不是本頁造成的。
    """
    _bad = _attr_calls(_tree(), ("columns", "form", "tabs"))
    assert not _bad, (
        "本頁自己開了網格 / 表單 / 巢狀分頁，沒有走 IA kit：\n  " + "\n  ".join(_bad)
        + "\n請改用 `ui.helpers.ia.render_cards()` 與 `ui.helpers.ia.applied_form()`；"
          "巢狀 `st.tabs` 依線框 Tab 04「這裡不放什麼」一律不留。")


def test_the_wide_table_goes_through_wide_table_not_st_dataframe():
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


def test_the_page_never_reaches_into_the_data_layer():
    """客戶方針第 2 條：資料只走 `services/**`，**不碰** `repositories` / `infra` / 網路函式庫。

    ⚠️ 本批連 `services/**` 都沒有呼叫（骨架階段沒有東西要算）——
    但這條**現在就要在**，因為下一批填內容時它才是真正在守的那道線。
    """
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.split(".")[0] in ("repositories", "infra", "requests", "httpx",
                                    "yfinance", "gspread", "urllib", "bs4",
                                    "feedparser")]
    assert not _bad, (
        "本頁 import 了資料層 / 網路函式庫：" + ", ".join(_bad)
        + "\n客戶方針第 2 條：UI 只讀對接既有 Service，取不到就誠實灰態，**不反向修底層**。")


def test_the_page_does_not_delegate_to_the_old_tabs():
    """⛔ 不 import 線框「從哪裡搬來」列的那幾個舊檔，也不 import 已經住在 ④ 的換股顧問。

    它們會在五頁驗收完成後**整批拔除**，每一條委派都是一處會斷頭。
    ⚠️ ① 留了一條對 `ui/tab1_macro_midcycle.py` 的委派並就地登記
    「有效期到舊 tab 整批拔除為止」—— **本頁一條都沒有，而且要維持這樣。**
    """
    _bad = [_m for _m in _imported_modules(_tree())
            if _m.startswith("ui.tab")
            or "fund_grp_health" in _m
            or "ui.helpers.portfolio" in _m
            or "portfolio_perf" in _m]
    assert not _bad, (
        "本頁委派了舊 ④ 的來源檔：" + ", ".join(_bad)
        + "\n舊實作會被整批拔除；本頁一律自己畫完。")


def test_the_page_never_renders_the_switch_advisor_section():
    """⛔ 本頁**不得**呼叫 `render_switch_advisor_section` —— 那一塊已經有唯一渲染點。

    `tests/test_ia_switch_advisor_moved_to_portfolio.py::`
    `test_switch_advisor_renders_only_from_the_portfolio_tab` 釘住它的呼叫點**恰好一個**
    （在舊 ④）。本頁若「順手也 render 一次」，那條全域守衛會當場轉紅，
    而且線上會撞 widget key `switch_advise_btn` → `DuplicateWidgetID`。

    ⚠️ 本條與那條全域守衛**不重複**：那條問「全 repo 有幾個呼叫點」，
    本條問「**本檔**有沒有」—— 本檔紅時訊息會直接指向這裡，不必去讀另一個檔的集合差。
    """
    _bad = [f"第 {_n.lineno} 行" for _n in ast.walk(_tree())
            if isinstance(_n, ast.Call)
            and (getattr(_n.func, "id", None) == "render_switch_advisor_section"
                 or getattr(_n.func, "attr", None) == "render_switch_advisor_section")]
    assert not _bad, (
        "本頁呼叫了 `render_switch_advisor_section` —— 它的渲染點必須恰好一個：\n  "
        + "\n  ".join(_bad))


def test_holdings_filters_out_the_not_yet_loaded_and_the_failed():
    """`_holdings()` 只回**已載入且沒有錯誤**的項目，其餘一律排除。

    ⚠️ **這個過濾是刻意的**：`portfolio_funds` 裡會有「已列入但 NAV 還沒抓回來」
    與「抓取失敗」的項目（`ui/helpers/portfolio/load.py` 寫入 `loaded` / `load_error`）。
    拿那些去算配置比例，等於用不完整的資料生一個看起來完整的結論（§1）。

    ⛔ **本條沒有測到的**：舊版 payload 形狀（缺 `loaded` 以外的其他欄位組合）。
    ⚠️ **本條直接寫 bare-mode 的 `st.session_state`，跑完會還原** ——
    不還原的話，它會依測試順序污染別的測試（`AppTest` 有自己的 session，不受影響，
    但同檔／同 session 的其他直呼路徑會）。
    """
    import streamlit as _st

    _cases = (
        (None, 0),
        ("不是 list", 0),
        ([], 0),
        ([{"code": "A"}], 0),                                   # 沒有 loaded
        ([{"code": "A", "loaded": True}], 1),
        ([{"code": "A", "loaded": True, "load_error": "429"}], 0),
        ([{"code": "A", "loaded": True}, {"code": "B"}], 1),
        (["不是 dict", {"code": "A", "loaded": True}], 1),
    )
    _had = "portfolio_funds" in _st.session_state
    _saved = _st.session_state.get("portfolio_funds") if _had else None
    try:
        for _raw, _want in _cases:
            _st.session_state["portfolio_funds"] = _raw
            assert len(_holdings()) == _want, (
                f"`_holdings()` 對 {_raw!r} 回了 {_holdings()!r}，預期 {_want} 筆。")
    finally:
        if _had:
            _st.session_state["portfolio_funds"] = _saved
        else:
            _st.session_state.pop("portfolio_funds", None)


@pytest.mark.parametrize("kind", ["empty", "missing", "loaded"])
def test_no_block_silently_renders_a_system_error(kind: str):
    """⛔ 三種 session 形狀下，**都不得**有任何區塊掉進 `safe_section()` 的紅框。

    ## 這條擋的是一種「測起來會綠、實際壞掉」的形狀

    `render_asset_allocation()` 把每一塊都包在 `safe_section()` 裡（區塊級隔離）。
    那是對的 —— 但它的**副作用**是：某一塊拋例外時，**AppTest 不會有 `exception`**，
    只會多出一個 `st.error` 紅框，而其他斷言（順序、灰態）**只看得到那一塊不見了**，
    訊息會指向「單位不見了」而不是「它炸了」。

    本條直接驗**渲染流裡沒有 `Error` / `Warning` 元素**，
    紅了就會直接把 `friendly_error()` 印的例外類型與訊息貼出來。

    ⚠️ **`Warning` 也一起擋**：`render_state.system_error(degraded=True)` 走的是
    `st.warning`（`ui/helpers/render_state.py` 的五態表）。骨架階段**不該有任何一種**。
    ⚠️ **反過來說，這條在下一批會需要重看**：真內容接上後，
    某些區塊可能**合法地**出現業務警示或降級橘框。**屆時要改的是本條的射程
    （限定「不得有 `system_error` 紅框」），不是把它刪掉。**
    """
    _bad = [_p for _p in _stream(kind)
            if _p.startswith("[Error]") or _p.startswith("[Warning]")]
    assert not _bad, (
        f"（{kind}）有區塊掉進 `safe_section()` 的紅框 —— 骨架階段不該有任何例外：\n  "
        + "\n  ".join(_bad))
