"""② 持倉體檢新頁的骨架守衛 —— 線框 Tab 02 的五塊，一塊都不准少。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**骨架的形狀**：五個區塊都在、順序對、Form 真的 gate 住下游、
沒有持倉時走空狀態、有持倉時四塊各自誠實灰、逐檔表 9 欄逐字。

⛔ **本檔不守內容對不對** —— 本批的內容**本來就還沒填**（客戶 2026-09-05：
   骨架先上線、CI 綠、再分批填）。下一批把真內容接上時，
   `test_every_block_is_grey_until_its_content_lands` 會**轉紅** ——
   **那是預期的**，屆時請把它改成「真內容放行」，**不要把它放寬**
   （① 的同型守衛就是這樣從灰態放行轉成真內容放行的）。

⛔ **本檔不驗瀏覽器裡的真實版面**：欄寬、窄螢幕折行、`st.form` 送出後真正的
   rerun 次數 —— 那些是 Streamlit 的執行期行為，靜態規則與 recorder 都看不到。

⛔ **本檔不重複既有的全域規則**（`ui/**` 全掃的那幾條會自動涵蓋這個新檔）：
   `tests/test_ui_grid_contract.py`（欄數）、`tests/test_ui_rerun_contract.py`（form 站點）、
   `tests/test_batch2_top_card_grid.py`（`where=` 必填）、
   `tests/test_wpf_five_tab_wiring.py`（分頁名不得手抄）。
   **在這裡再抄一份等於製造第二把尺**（`CLAUDE.md §2.1`）。

⚠️ 獨立紅隊 2026-09-05 打穿的 fail-open（**逐項實跑，每一項都 18 passed**）
------------------------------------------------------------------------
**本批刻意不補**（總管排程裁決：下一批填真內容時這些守衛本來就要重寫，
補完再拆一次是白做兩次）。**寫在這裡是揭露義務**（`CLAUDE.md §-2` 規則 6）——
**讀本檔的人請據此打折信任它，不要把「18 passed」讀成「這一頁守住了」。**

- **語意維（4/4 全穿）**：灰態文案句尾加「目前一切正常，無異常」／三張卡的理由互換／
  指路改成假承諾「去 ④ 新增後這塊就會出現」／空狀態改成「若已新增代表系統判定無效」。
  ⚠️ 第三項尤其諷刺：`test_no_holdings_does_not_also_print_the_batch_pending_excuse`
  擋的是兩句**混在一起**，把假承諾**直接寫進灰態文案本身**完全不擋。
- **繞道維**：:func:`_segments` 回傳 dict，**同名單位後者覆蓋前者** ——
  掏空真區塊、畫捏造的 72、再造一個同名誘餌帶灰態 → 全綠。
  **「粒度降到一張卡」這個成果可以被一行繞過。**
  另：手刻 `st.markdown("⬜ …")` 不走 `not_ready()` 也照樣被認成灰態。
- **情境維**：`_holdings()` 的 `loaded` / `load_error` 過濾**零守衛**
  （整條拿掉 → 全綠），而那是本檔**唯一一條 §1 邏輯**；
  session 形狀只渲染過 `FAKE_HOLDINGS` 與 `[]` **兩種**。
- **`test_there_is_no_fund_code_input_box` 只擋兩個字面 attribute 名**：
  `from streamlit import text_input`／`getattr(st, "text_input")`／`st.chat_input`／
  `st.selectbox(accept_new_options=True)` **四種都穿過去**。
- **指路挑錯 key 沒有任何守衛**（本組修完 2026-09-05 那個 present bug 後自己掃出來的）：
  職責宣告那句改成 `where_to_find('portfolio')` 之後，**沒有任何測試在驗它** ——
  本檔沒有；全域的 `test_navigation_hints_go_through_story_nav` 只驗
  「同一語句子樹裡有沒有 story_nav 呼叫」，**換成任何一個 key 它都綠**。
  ⚠️ 也就是說：**改回 `pf_add`（那個已知是錯的 key）不會有任何東西轉紅。**
  **這是「走 SSOT」擋不到的那一類**：SSOT 保證名字不過期，**不保證你挑對了 key**。
- **`test_downstream_reads_the_applied_filters_not_the_widget_values` 分不出真假閘門**：
  `if True:` 與 `if not _gate:`（語意完全相反、功能整個壞掉）都全綠。
  ⚠️ 且「下游只讀 `_SK_APPLIED`」**目前是一句空話** —— 唯一呼叫點是
  `_render_filter_form()` 自己拿來當 widget 預設值，**本批沒有任何下游**。
  它是**寫給下一批的結構**，不是現在就在保護什麼。

錄製法：為什麼不用 AppTest
--------------------------
本頁尚未接進 `app.py`（客戶明令舊 ② 不動、不接線），AppTest 走不到它。
故以**替換 `st` 的渲染 API**錄下呼叫序列 —— 與 `tests/test_wf01_detail_zone_order.py`
同一套做法，那裡已經被三輪獨立稽核打過。
"""
from __future__ import annotations

import ast
import pathlib
import sys
import re
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_02_health.py"

#: 灰態的視覺記號（`ui/helpers/render_state.py::NOT_READY_MARK`）。
#: ⚠️ **從那個模組 import，不在這裡抄一份字面值** —— 抄了就是第二份真相源。
#: form 閘門守衛共用的 AST 偵測（`tests/_ast_bindings.py`）——
#: ⚠️ 這裡**不要**再抄一份掃描邏輯：②③④ 三頁曾各自抄一份較弱的版本，
#:    三份同時漏掉屬性賦值／`update()`／widget `key=` 三條管道（`CLAUDE.md §2.1`）。
#: ⚠️ `sys.path` 那一行不是多餘的：pytest 預設會把 `tests/` 放進 `sys.path`，
#:    但那是預設值的副作用，換 `--import-mode=importlib` 就沒了。
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from _ast_bindings import (gate_guarded_ids, gate_ifs,  # noqa: E402
                           guarded_key_names, session_writes)

from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.helpers.story_nav import where_to_find  # noqa: E402
from ui.views.page_02_health import (  # noqa: E402
    HEALTH_TABLE_COLUMNS,
    _PENDING_NOTE,
    render_holdings_health,
)

#: 會產生「使用者看得到的字」的 st API。錄下來當作區塊有沒有真的畫東西的證據。
_TEXT_APIS = (
    "markdown", "write", "caption", "text", "info", "warning", "error",
    "success", "metric", "dataframe", "table", "code", "header", "subheader",
    "title", "slider", "number_input", "checkbox", "form_submit_button",
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

    def __getattr__(self, name: str):
        def _fn(*args: Any, **kwargs: Any):
            if name in _TEXT_APIS:
                _bits = [str(a) for a in args if isinstance(a, (str, int, float))]
                # widget 的 label 是第一個位置引數；`metric` 的值是第二個。
                self.parts.append(f"[{name}] " + " ".join(_bits))
            if name in ("slider", "number_input"):
                return kwargs.get("value", args[2] if len(args) > 2 else 0)
            if name in ("checkbox", "toggle", "button", "form_submit_button"):
                return False
            if name == "columns":
                return [_Rec._Child(self) for _ in range(int(args[0] or 1))
                        if True] if isinstance(args[0], int) else [
                            _Rec._Child(self) for _ in (args[0] or [1])]
            return _Rec._Child(self)
        return _fn

    class _Child:
        """`st.columns()` / `st.expander()` 回傳的容器：寫回同一份紀錄。"""

        def __init__(self, root: "_Rec") -> None:
            self._root = root

        def __enter__(self):
            return self

        def __exit__(self, *_exc: Any) -> bool:
            return False

        def __getattr__(self, name: str):
            return getattr(self._root, name)


def _render(portfolio: list | None = None,
            applied: dict | None = None) -> list[str]:
    """跑一次整頁，回傳**有序**的渲染紀錄。

    ⚠️ 回傳 list 而不是一整塊字串 —— 順序本身是本檔要驗的東西之一，
    join 成一坨就驗不了「哪一句落在哪一塊底下」。
    """
    import sys

    # 匯入套件 → 它的 `__init__` 會把四個子模組都放進 `sys.modules`。
    # （被測模組本身已由本檔頂部的 import 註冊過。）
    import ui.helpers.ia  # noqa: F401

    # ⚠️ **一律走 `sys.modules`，不要用 `import a.b.c as x`。**
    #    `ui/helpers/ia/__init__.py` 有一行 `from ui.helpers.ia.empty_state import
    #    empty_state` —— 它把**函式**綁成了套件的 `empty_state` 屬性，於是
    #    `import ui.helpers.ia.empty_state as _e` 拿到的是那個**函式**而不是模組，
    #    `setattr(_e, "st", …)` 就打在函式身上、模組的 `st` 一動也沒動。
    #    **本檔初稿就是這樣寫的，症狀是空狀態的標題與 footer 整個錄不到**
    #    （灰字那行有錄到，因為它委派回 `render_state`，那個模組沒有被遮蔽）——
    #    也就是說：**錯的 patch 不會報錯，只會讓斷言對著半份畫面生效。**
    _targets = tuple(sys.modules[_n] for _n in (
        "ui.views.page_02_health",
        "ui.helpers.ia.cards",
        "ui.helpers.ia.empty_state",
        "ui.helpers.ia.gated_form",
        "ui.helpers.ia.layout",
        "ui.helpers.render_state",
    ))
    # ⚠️ **`ui.helpers.story_nav` 刻意不在上表**：它的 `render_story_nav()` 是
    #    **函式內** `import streamlit as st`，沒有 module 層的 `st` 可以換 ——
    #    也就是它那一行麵包屑 caption 走的是**真的** streamlit（bare 模式下無害）、
    #    **不會**進到紀錄裡。本檔沒有任何斷言依賴它，故不處理；
    #    **但若日後要驗麵包屑，改的是這裡，不是把斷言放寬。**
    #    （這件事是上面那條錨點斷言當場抓到的，不是事後推測。）

    _rec = _Rec()
    if portfolio is not None:
        _rec.session_state["portfolio_funds"] = portfolio
    if applied is not None:
        _rec.session_state["v02_health_applied_filters"] = applied

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
        render_holdings_health()
    finally:
        for _m, _old in _saved:
            _m.st = _old
    return _rec.parts


def _text(parts: list[str]) -> str:
    return "\n".join(parts)


#: 一級區塊的標題（`st.markdown("#### …")`）。
_BLOCK_OPEN = re.compile(r"^\[markdown\] #{4}\s+(.*)$")
#: 一張卡的標題 —— `ia.state_card()` 在灰態時畫的 `st.markdown(f"**{title}**")`。
#: ⚠️ **這一條是本檔的最小單位，不是裝飾**（理由見 `_units()`）。
_CARD_OPEN = re.compile(r"^\[markdown\] \*\*(.+)\*\*$")


def _units(parts: list[str]) -> list[tuple[str, list[str]]]:
    """把紀錄切成**有序**的最小單位：一級區塊，或**一張卡**。

    ⚠️ **這是本檔最重要的機制，而且它的粒度是被一次突變逼出來的，不是設計出來的。**

    初版只依 `#### 區塊名` 切段，突變「把『組合健康總分』的灰態換成
    `st.caption("—")`」**沒有轉紅**（實測 2 passed）—— 因為三張警示卡**沒有**自己的
    `####` 標題，它們的 ⬜ 全部落在「組合健康總分」那一段裡，
    於是「這一段有沒有 ⬜」永遠是 True。

    **同一個形狀在 ① 被獨立稽核連續打穿兩輪**（`tests/test_wf01_detail_zone_order.py`
    的沿革記著：`st.caption("—")` 18 passed、`st.success("✅ …無異常")` 662 passed、
    以及「同小節三張卡只捏造其中一張」683 passed）。**答案每次都一樣：把邊界往下降。**
    本檔一次降到底 —— **最小單位是一張卡**。

    ⛔ **不要為了讓斷言好寫而把邊界往上收。** 邊界一寬，鄰居的字就會替你通過。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _m = _BLOCK_OPEN.match(_p) or _CARD_OPEN.match(_p)
        if _m:
            _out.append((_m.group(1).strip(), []))
            continue
        if _out:
            _out[-1][1].append(_p)
    return _out


def _segments(parts: list[str]) -> dict[str, list[str]]:
    """`單位名 -> 該單位內的渲染紀錄`（`_units()` 的 dict 檢視）。"""
    return {_k: _v for _k, _v in _units(parts)}


#: 有持倉時應該出現的四個一級區塊（順序即線框 Tab 02 的順序）。
#: ⚠️ Form 沒有 `####` 標題（它是頁面最上面那一塊），故不在本表，另由
#: `test_the_filter_form_is_the_first_thing_on_the_page` 驗。
EXPECTED_BLOCKS: tuple[str, ...] = ("組合健康總分", "逐檔體檢表")

#: 三張警示卡的標題（線框 Tab 02 逐字）。
EXPECTED_CARDS: tuple[str, ...] = ("吃本金警示", "衛星連續落後", "影子基金重疊")

#: 一份「已載入」的假持股。欄位形狀取自 `ui/helpers/portfolio/load.py` 寫入的契約。
FAKE_HOLDINGS = [
    {"code": "ACDD19", "policy_id": "P1", "currency": "TWD",
     "loaded": True, "load_error": None},
]


# ══════════════════════════════════════════════════════════════════
# 骨架：五塊都在、順序對
# ══════════════════════════════════════════════════════════════════

def test_the_filter_form_is_the_first_thing_on_the_page():
    """線框 Tab 02 的第一塊就是 Form —— 而且它必須在任何診斷結果**之前**。

    順序不是美感問題：條件在結果**後面**的話，使用者會先看到一個他還沒設定條件的結論。
    """
    _parts = _render(portfolio=FAKE_HOLDINGS)
    _submit = [_i for _i, _p in enumerate(_parts) if _p.startswith("[form_submit_button]")]
    assert _submit, (
        "整頁沒有任何 `form_submit_button` —— 診斷條件沒有包在 `applied_form()` 裡。\n"
        "線框 Tab 02 就地點名舊 ② 的缺陷是「目前每拉一格全頁重繪，本次一併修掉」，"
        "那是四大鐵律之二，不是選配。")
    _first_block = next(
        (_i for _i, _p in enumerate(_parts) if _p.startswith("[markdown] #### ")), None)
    assert _first_block is not None, "找不到任何 `#### 區塊標題` —— 骨架的分段記號不見了。"
    assert _submit[0] < _first_block, (
        "送出鈕出現在第一個診斷區塊**之後** —— 條件必須在結果前面。\n"
        f"送出鈕在第 {_submit[0]} 筆，第一個區塊在第 {_first_block} 筆。")


def test_the_three_filters_from_the_wireframe_are_all_there():
    """線框逐字三個條件：輪動門檻 σ／回看窗（月）／只看衛星。少一個就紅。

    ⚠️ 用**標籤字**比對，因為線框定的就是這三個條件本身，不是它們的實作型別。
    """
    _all = _text(_render(portfolio=FAKE_HOLDINGS))
    for _label in ("輪動門檻", "回看窗", "只看衛星"):
        assert _label in _all, (
            f"診斷條件少了「{_label}」—— 線框 Tab 02 的 Form 逐字列了三個條件。")


def test_there_is_no_fund_code_input_box():
    """客戶 2026-09-05 裁決：**不保留手動輸入基金代號**，持股一律從組合帶入。

    ⚠️ 這條是**反向**規則（守「不要有」而不是「要有」），因為它擋的是一種
    看起來很貼心的退化：有人覺得「加個代號框比較方便」，就把 ③ 標的探索的職責
    搬進 ②。線框把「我沒持有的基金」明列在 Tab 02 的「這裡不放什麼」。
    """
    # 掃的是 `Call` 節點，所以 docstring 裡提到 `text_input` 這四個字不會誤判 ——
    # 字串常數不是呼叫。（本檔上面那段長 docstring 就提到它。）
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _bad = [f"第 {_n.lineno} 行 {ast.unparse(_n.func)}(…)"
            for _n in ast.walk(_tree)
            if isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
            and _n.func.attr in ("text_input", "text_area")]
    assert not _bad, (
        "本頁出現了自由文字輸入框 —— 客戶 2026-09-05 裁決「不保留手動輸入基金代號」，"
        "持股一律從 `portfolio_funds` 帶入：\n  " + "\n  ".join(_bad)
        + "\n若組合真的取不到持股，那是**新事實，要回報**，不是自己補一個輸入框。")


def test_all_four_content_blocks_are_present_and_in_wireframe_order():
    """有持倉時：組合健康總分 → 三張卡 → 逐檔體檢表，缺一或倒序即紅。"""
    _parts = _render(portfolio=FAKE_HOLDINGS)
    _seg = _segments(_parts)
    for _b in EXPECTED_BLOCKS:
        assert _b in _seg, (
            f"線框 Tab 02 的區塊「{_b}」不見了。現有區塊：{list(_seg)}")
    _order = [_p for _p in _parts if _p.startswith("[markdown] #### ")]
    _idx = {_b: next(_i for _i, _p in enumerate(_order) if _p.endswith(_b))
            for _b in EXPECTED_BLOCKS}
    assert _idx["組合健康總分"] < _idx["逐檔體檢表"], (
        "區塊順序與線框不符：總分應在逐檔表之前（先給結論、再給明細）。")
    _all = _text(_parts)
    for _c in EXPECTED_CARDS:
        assert _c in _all, (
            f"三張警示卡少了「{_c}」—— 線框 Tab 02 逐字列了三張。現況：\n{_all}")


def test_the_per_fund_table_keeps_the_nine_columns_from_the_wireframe():
    """逐檔體檢表 9 欄，逐字對線框。

    ⚠️ 欄位少一欄不會讓畫面壞掉，只會讓使用者少看到一個判斷依據 ——
    那正是「無聲退化」，所以要釘住。
    """
    assert HEALTH_TABLE_COLUMNS == (
        "代碼", "名稱", "幣別", "近 1 年", "Sharpe",
        "最大回撤", "配息覆蓋", "五桶評等", "資料日期"), (
        f"逐檔體檢表的欄位與線框 Tab 02 不符：{HEALTH_TABLE_COLUMNS}")
    assert len(HEALTH_TABLE_COLUMNS) == 9
    _all = _text(_render(portfolio=FAKE_HOLDINGS))
    for _col in HEALTH_TABLE_COLUMNS:
        assert _col in _all, f"畫面上看不到欄位「{_col}」。"


# ══════════════════════════════════════════════════════════════════
# 灰態：兩種灰的理由不同，文案必須分開
# ══════════════════════════════════════════════════════════════════

def test_no_holdings_shows_the_wireframe_empty_state_and_points_at_tab_four():
    """沒有持倉 → 線框指定的空狀態三要素，指路到 ④（**使用者照著做真的能解決**）。"""
    _all = _text(_render(portfolio=[]))
    assert "尚未設定持倉" in _all, "沒有持倉時應出現線框逐字的「尚未設定持倉」。"
    assert "還沒有任何保單或扣款標的" in _all, "空狀態缺了「缺什麼」這一要素。"
    assert where_to_find("pf_add") in _all, (
        "空狀態的「去哪補」沒有指到 ④ 的加入基金區塊 —— "
        f"應含 `where_to_find('pf_add')` ＝ {where_to_find('pf_add')!r}。")


def test_no_holdings_does_not_also_print_the_batch_pending_excuse():
    """兩種灰不得混在一起。

    ⚠️ 這條擋的是一個很容易犯、而且看起來無害的錯：沒有持倉時**同時**印出
    「本頁分批上線」的灰字。使用者會以為「去 ④ 加了基金這裡就會出現」—— 不會，
    因為內容根本還沒接上。**一次只給一個下一步。**
    """
    _all = _text(_render(portfolio=[]))
    # ⚠️ 比對 `_PENDING_NOTE` 本體，**不硬抄字面值**。
    #    硬抄的話，常數一改措辭這條就永遠是 True —— 它守的 bug 照樣存在、而它不再看得見。
    #    （獨立紅隊實證：改措辭 ＋ 同時重犯這個 bug → 本條 passed，fail-open。）
    assert _PENDING_NOTE not in _all, (
        "沒有持倉時不應同時印出「內容還沒接上」的灰字 —— 兩個下一步會互相抵消。\n"
        + _all)


def test_no_holdings_hides_the_diagnosis_blocks_entirely():
    """沒有持倉時，三塊診斷區塊**整個不畫**，而不是各印一句灰字。

    線框把空狀態畫成**取代**內容區，不是疊在它上面；四份在講同一件事的灰字
    就是鐵則 04 要禁的「冗餘占位」。
    """
    _seg = _segments(_render(portfolio=[]))
    _leaked = [_b for _b in EXPECTED_BLOCKS + EXPECTED_CARDS if _b in _seg]
    assert not _leaked, (
        f"沒有持倉時仍畫出了診斷區塊 {_leaked} —— 空狀態應**取代**它們。")


@pytest.mark.parametrize("block", EXPECTED_BLOCKS + EXPECTED_CARDS)
def test_every_block_is_grey_until_its_content_lands(block: str):
    """有持倉、但內容還沒接上 → 每一塊**各自**要有灰態記號與理由。

    ⚠️ **斷言的單位是「一級區塊」或「一張卡」，不是整頁，也不是整段。**
    本檔初版以「一級區塊」為單位，突變「只拿掉組合健康總分那一塊的灰態」
    **沒有轉紅**（三張卡的 ⬜ 落在同一段裡替它通過了）—— 粒度因此下降到一張卡。
    詳見 :func:`_units` 的長註。

    ⚠️ **下一批把真內容接上時，這條會轉紅 —— 那是預期的。**
    屆時請把它改成「真內容放行」（例如驗總分是數字、驗表格有列），
    **不要把它放寬成「有東西就好」**。① 就是這樣從灰態放行轉成真內容放行的。
    """
    _seg = _segments(_render(portfolio=FAKE_HOLDINGS))
    _body = "\n".join(_seg.get(block, []))
    assert _body.strip(), f"區塊「{block}」有標題但沒有任何內容 —— 那是空占位。"
    assert NOT_READY_MARK in _body, (
        f"區塊「{block}」沒有灰態記號 {NOT_READY_MARK!r} —— "
        "內容還沒接上就要誠實留灰，不得空著也不得填示意值（§1）。\n" + _body)
    assert _PENDING_NOTE in _body, (
        f"區塊「{block}」的灰態沒說「為什麼沒有」。\n" + _body)


#: 本條**實際釘住**的字面值。列成常數，是為了讓「它到底守了什麼」可以被讀出來，
#: 而不是藏在 docstring 的形容詞裡。
_PINNED_FAKE_VALUES: tuple[str, ...] = (
    "72 ／ 100", "72／100", "72/100", "0.78", "相似度 0.78",
)


def test_the_grey_blocks_never_print_the_illustrative_numbers_from_the_wireframe():
    """⛔ 線框那幾個**示意值**不准出現在畫面上（**只涵蓋下列字面寫法**）。

    為什麼要有這條：填一個看起來合理的分數，使用者**完全看不出它是假的**，
    而且會拿它去做決定（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ## ⚠️ 這條**實際**守得到什麼（照實寫，不要照抄上一版的形容詞）

    **只釘 `_PINNED_FAKE_VALUES` 這 5 個字面寫法**：`72 ／ 100`／`72／100`／`72/100`／
    `0.78`／`相似度 0.78`。

    **明確守不到（獨立紅隊 2026-09-05 逐項實跑，每一項都 18 passed）**：
      - **裸 `72`** —— `st.caption("參考：72 分")`、`st.metric("總分", 72)` 都穿過去；
      - **「2 檔」「1 檔」** —— 線框另外兩個示意值，**本條從來沒有釘過它們**；
      - **全形數字**（`０.７８`）。

    ⛔ **上一版的 docstring 寫「72／2 檔／1 檔／0.78 一個都不准出現」——那句是假的。**
    「2 檔／1 檔」在**整個測試檔只出現過一次，就是那句 docstring 自己**；
    斷言清單裡從來沒有它們。**一條自稱守 §1 的規則，自己的描述必須先為真**
    （`CLAUDE.md §-2`：沒查證的宣稱比沒有宣稱更危險）。

    📌 **本批刻意不補**（總管 2026-09-05 排程裁決）：下一批填真內容時，
    「哪些數字算捏造」的判準會整個改寫（屆時 72 分**可能是真的算出來的**），
    現在補完、下一批再拆一次是白做兩次。**已登記為下一批的入口條件。**
    """
    _all = _text(_render(portfolio=FAKE_HOLDINGS))
    for _fake in _PINNED_FAKE_VALUES:
        assert _fake not in _all, (
            f"畫面上出現了線框的示意值 {_fake!r} —— 那不是資料，是線框用來示範版面的假數字。")


def test_every_grey_block_says_where_to_look_instead():
    """每一塊灰態都要有「去哪補」，而且**不得手抄分頁名**。

    ⚠️ 這一頁的灰態有一個先天問題：內容還沒接上時，使用者**沒有地方可以去**。
    能給的最誠實的指路是「現在哪一塊是完整的」—— 所以本條驗的是
    `where_to_find('health')` 有出現，而不是隨便一句話。
    """
    _all = _text(_render(portfolio=FAKE_HOLDINGS))
    assert where_to_find("health") in _all, (
        "灰態的指路沒有走 `where_to_find('health')` —— "
        "手抄的分頁名在本 repo 已經指錯三次（見 `story_nav.RETIRED_TAB_LABELS`）。")


# ══════════════════════════════════════════════════════════════════
# 鐵則 02：form 要真的 gate 住下游（不是「有 form 就算」）
# ══════════════════════════════════════════════════════════════════

def test_downstream_reads_the_applied_filters_not_the_widget_values():
    """條件的**已套用值**與 widget 當下值必須是兩個東西。

    ⚠️ 這條守的是鐵則 02 真正的那一半。只包 `st.form` 只擋住「widget 互動觸發 rerun」，
    **沒有擋住重運算** —— 每次 rerun 照樣把下游跑一遍，畫面看起來沒問題、成本一分沒省
    （`ui/helpers/ia/gated_form.py` 模組 docstring 把這個陷阱寫得很清楚）。

    做法：以 AST 確認 `_applied_filters()` 讀的是 session 的已套用鍵，
    且 widget 的回傳值**只**在 `if <gate>:` 底下才被寫進 session。
        ## 這條看得見／看不見什麼（2026-09-05 重寫，**先讀這段再信它**）

    session 寫入有**四條管道**，本條靠 `tests/_ast_bindings.py::session_writes`
    四條全收：下標賦值／**屬性賦值**／`update()`＋`setdefault()`／**widget 的 `key=`**。
    ⚠️ **2026-09-05 第二輪：管道 4 已收窄，這不是放水，是修一條無解的偽陽性。**
    widget 一定建在 `with applied_form(...)` 內、閘門 `if` 一定在 `with` 外
    ⇒ 帶 `key=` 的 widget **結構上永遠不可能**落在閘門 body 裡；不收窄的話這條
    **沒有任何合法擺法能轉綠**（本 repo `ui/**` 有 231 處 `key=`，那是家風）。
    現行判準：`key=` **指到守衛在乎的那個 session key** 才算違規（常數名與字面值都認），
    widget 寫自己的鍵不是。**此判準不依賴任何未經實測的 streamlit runtime 語意。**
    ⚠️ 重寫前它**只認第一條**（`ast.Assign` ＋ target 是 `ast.Subscript`）——
    本組 2026-09-05 的基線實測：三頁 × 另外三條管道，注入裸寫入後**全部 18/18 綠**。
    其中**屬性賦值**是本 repo `ui/**` 跨 6 檔 27 處的主流寫法，
    **最可能被下一個人照家風真的踩到**；`key=` 那條最陰 —— streamlit **代呼叫端**
    把 widget 值寫進 session，AST 上是普通 `ast.Call`，任何「找賦值節點」的手段都收不到。

    「被閘門包住」的判準也換了：從「在**任何**一個 `ast.If` 底下」改成
    **「在 `with applied_form(...) as X` 綁出來的那個 `X` 所控制的 `if` 底下」**
    （`gate_ifs()`）。舊判準的洞：只要有人往這個函式加第二個 `if`
    （例如 `if not _funds: return`），藏在它底下的裸寫入就會被算成「已被閘門包住」。
    **實測**：重寫前本函式只有 `_gate` 一個 `if`，所以那個洞**尚未發作** ——
    修的是「下一個人加第二個 `if` 就會中」。

    ⛔ **仍然分不出真假閘門**：`if not _gate:` 的 test 一樣提到 `_gate`，
    本條照樣認它是閘門（`gate_ifs()` 的 docstring 就地寫明）。
    那一種要靠 AppTest 行為測試去驗，靜態規則做不到。
    ⛔ **不遞迴進被呼叫的函式**：把 `st.session_state` 傳出去、由別處寫，本條看不到。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _fns = {_n.name: _n for _n in ast.walk(_tree)
            if isinstance(_n, ast.FunctionDef)}
    assert "_applied_filters" in _fns, (
        "找不到 `_applied_filters()` —— 「已套用值」這一層被拿掉了，"
        "下游就會直接讀 widget 值，等於沒有 form。")
    _form_fn = _fns["_render_filter_form"]
        # ⚠️ 管道 4（widget `key=`）**必須**收窄成「只認守衛在乎的那個 session key」：
    #    widget 一定建在 `with applied_form(...)` 內，而閘門 `if` 一定在 `with` 外
    #    ⇒ 帶 `key=` 的 widget 結構上永遠不可能落在閘門 body 裡，不收窄就是一條
    #    **永遠無法滿足**的守衛（本 repo `ui/**` 有 231 處 `key=`，量測日 2026-09-05）。
    # ⚠️ **自動收齊模組層所有 `_SK_*`，不要列舉** —— 列舉一定會漏下一個新加的鍵。
    #    上一版只餵 `_SK_APPLIED`，於是 `key=_SK_PORTFOLIO`（使用者的 live 持股）
    #    那顆突變從紅掉成綠（2026-09-06 稽核 M-1，三頁 × 三序實測）。
    _applied_keys = guarded_key_names(_tree)
    _writes = session_writes(_form_fn, widget_key_names=_applied_keys)
    assert _writes, "`_render_filter_form()` 沒有把套用結果寫回 session。"
    _gate_ifs = gate_ifs(_form_fn)
    assert _gate_ifs, (
        "`_render_filter_form()` 裡找不到 `with applied_form(...) as <gate>:` 綁出來的那個閘門 `if` —— "
        "form 沒有 gate 住任何東西（或閘門換了寫法，請同步 `gate_ifs()` 的判準）。")
    # ⚠️ 只算閘門 `if` 的 **body** —— `else:` / `elif` 是閘門為假才跑的路徑，
    #    整棵 `ast.walk(_g)` 會把它們一起算成 guarded（2026-09-05 實測的洞）。
    _guarded = gate_guarded_ids(_form_fn)
    _naked = [_w for _w in _writes if id(_w) not in _guarded]
    assert not _naked, (
        "有 session 寫入**沒有**被送出閘門包住 —— 那代表每次 rerun 都會覆寫已套用值，\n"
        "使用者拖滑桿的當下就會觸發下游重算，form 等於白包。\n  "
        + "\n  ".join(f"第 {_w.lineno} 行：{ast.unparse(_w)[:70]}" for _w in _naked))


def test_the_page_never_reaches_into_the_data_layer():
    """客戶方針第 2 條：資料只走 `services/**`，**不碰** `repositories` / `infra` / 網路函式庫。

    ⚠️ 本批連 `services/**` 都沒有呼叫（骨架階段沒有東西要算）——
    但這條**現在就要在**，因為下一批填內容時它才是真正在守的那道線。
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _mods: list[str] = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.Import):
            _mods.extend(_a.name for _a in _n.names)
        elif isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.append(_n.module)
    _banned = ("repositories", "infra", "requests", "httpx", "yfinance",
               "gspread", "urllib", "bs4", "feedparser")
    _bad = [_m for _m in _mods if _m.split(".")[0] in _banned]
    assert not _bad, (
        "本頁 import 了資料層 / 網路函式庫：" + ", ".join(_bad)
        + "\n客戶方針第 2 條：UI 只讀對接既有 Service，取不到就誠實灰態，**不反向修底層**。")


def test_the_page_does_not_delegate_to_the_old_tab():
    """⛔ 不 import 舊 ②。它會在五頁驗收完成後**整批拔除**，每一條委派都是一處會斷頭。

    ⚠️ ① 留了一條對 `ui/tab1_macro_midcycle.py` 的委派並就地登記
    「有效期到舊 tab 整批拔除為止」—— **本頁一條都沒有，而且要維持這樣。**
    """
    _tree = ast.parse(SRC.read_text(encoding="utf-8"))
    _mods: list[str] = []
    for _n in ast.walk(_tree):
        if isinstance(_n, ast.ImportFrom) and _n.module:
            _mods.append(_n.module)
        elif isinstance(_n, ast.Import):
            _mods.extend(_a.name for _a in _n.names)
    _bad = [_m for _m in _mods
            if _m.startswith("ui.tab") or "fund_grp_health" in _m
            or "mk_dashboard" in _m]
    assert not _bad, (
        "本頁委派了舊 ② 或波段觀測站：" + ", ".join(_bad)
        + "\n舊實作會被整批拔除；波段觀測站是客戶指定的**下一個獨立批次**，本批不碰。")
