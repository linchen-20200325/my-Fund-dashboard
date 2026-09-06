"""② 持倉體檢新頁的骨架守衛 —— 線框 Tab 02 的五塊，一塊都不准少。

守什麼、不守什麼（先講清楚，避免下一個人以為這裡已經守死了）
------------------------------------------------------------
本檔守的是**骨架的形狀**：五個區塊都在、順序對、Form 真的 gate 住下游、
沒有持倉時走空狀態、有持倉時四塊各自誠實灰、逐檔表 9 欄逐字。

⭐ **2026-09-06：真內容接上了，本檔的守法跟著換了一次方向。**
骨架批的 `test_every_block_is_grey_until_its_content_lands` 自己就寫著
「下一批把真內容接上時，這條會**轉紅** —— 那是預期的，屆時請把它改成
『真內容放行』，**不要把它放寬成「有東西就好」**」。**本次照辦，並且拆成三條**：

- :func:`test_deferred_blocks_stay_grey_and_say_exactly_why` —— **還沒接**的兩塊
  （組合健康總分／衛星連續落後）必須灰，而且理由必須是**那一塊自己的**
  （前身只驗「有沒有灰」，於是紅隊把三張卡的理由互換照樣全綠）；
- :func:`test_wired_blocks_show_real_content_when_the_data_is_there` —— **已接上**的
  三塊在資料齊全時**不得再是灰的**（反方向釘死，不是放寬）；
- :func:`test_wired_blocks_go_grey_again_when_the_data_is_missing` —— 反過來，資料不齊
  時必須誠實退回灰態，**不得把「算不出來」印成 `0 檔`**（那會被讀成「檢查過了，沒事」）。

⚠️ 兩張清單（`_DEFERRED` / `_WIRED`）由
:func:`test_the_two_tables_together_cover_every_block_exactly_once` 釘住**不重不漏** ——
否則新增一塊卻兩張都忘了登記時，上面三條**都不會轉紅**。

⛔ **本檔仍不守「數字算得對不對」**（那是 `services/**` 各自的測試在守）。
   本檔守的是「**這個數字是不是 SSOT 算的**」——
   :func:`test_the_numbers_on_the_cards_come_from_the_ssot` 把 SSOT 的回答換掉，
   畫面若不跟著動就轉紅。**那比列舉「哪些字面值算捏造」強得多**（後者擋不掉裸 `72`）。

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

⚠️ **本批新增的三個守衛，各自守不到什麼（誠實揭露，`CLAUDE.md §-2` 規則 6）**：
- `test_the_eating_principal_card_never_uses_the_momentum_signal` 掃的是**符號名**，
  有人把那段滾動報酬邏輯**照抄並改名**就掃不到；
- `test_blank_holding_names_never_become_a_perfect_match` 只擋「純空白名」這**一個**
  已知成因。持股清單被上游截斷成 1～2 筆時，兩檔共享那一筆一樣會算出 1.0 ——
  **那是這個指標本身的稀疏樣本問題，本批沒有解，也不假裝有解**；
- `test_the_numbers_on_the_cards_come_from_the_ssot` 證明「畫面跟著 SSOT 走」，
  **不證明 SSOT 算得對**，也不證明**挑對了 SSOT**（挑錯 SSOT 由上面那條專門守，
  而它只守得住已知的那一個）。

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

from ui.helpers.render_state import (  # noqa: E402
    BUSINESS_ALERT_ON_DARK, BUSINESS_ALERT_RAIL_PX, NOT_READY_MARK)
from ui.helpers.story_nav import where_to_find  # noqa: E402
from ui.views.page_02_health import (  # noqa: E402
    HEALTH_TABLE_COLUMNS,
    _num,
    _pct,
    _uniq_by_code,
    _LAG_PENDING_NOTE,
    _SCORE_PENDING_NOTE,
    _table_rows,
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
            # ⭐ `metric` 與 `dataframe` 各自拆成兩筆，**這不是美化，是為了讓
            #    `_units()` 看得見它們**（理由見 `_units()` 的「三種卡開頭」長註）：
            #    通用分支會把 label 與 value 併成一行（`[metric] 影子基金重疊 0 對`），
            #    於是「卡片標題」再也切不出來；`dataframe` 更慘 —— 它的引數是
            #    list[dict]，不是 str/int/float，通用分支**一個字都錄不到**，
            #    於是「畫面上看得到每一欄」會對著一片空白做斷言。
            if name == "metric":
                _label = str(args[0]) if args else str(kwargs.get("label", ""))
                _value = (str(args[1]) if len(args) > 1
                          else str(kwargs.get("value", "")))
                self.parts.append(f"[metric] {_label}")
                self.parts.append(f"[metric_value] {_value}")
                return None
            if name == "dataframe":
                _data = args[0] if args else kwargs.get("data")
                _cols = (list(_data[0].keys())
                         if isinstance(_data, list) and _data
                         and isinstance(_data[0], dict) else [])
                _n = len(_data) if isinstance(_data, list) else -1
                self.parts.append("[dataframe] " + "　".join(map(str, _cols)))
                for _r in (_data if isinstance(_data, list) else []):
                    if isinstance(_r, dict):
                        self.parts.append(
                            "[dataframe_row] "
                            + "　".join(str(_v) for _v in _r.values()))
                self.parts.append(f"[dataframe_rows] {_n}")
                return None
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


def _holdings_of(portfolio: list) -> list:
    """用給定的 session 內容跑一次 `_holdings()`（那個過濾是本頁唯一一條 §1 邏輯）。

    ⚠️ `_holdings()` 直接讀 `st.session_state`，所以要驗它就得把模組的 `st` 換掉 ——
    與 :func:`_render` 同一套手法，只是不渲染。
    """
    from ui.views import page_02_health as _mod
    _rec = _Rec()
    _rec.session_state["portfolio_funds"] = portfolio
    _saved = _mod.st
    try:
        _mod.st = _rec
        return _mod._holdings()
    finally:
        _mod.st = _saved



#: 一級區塊的標題（`st.markdown("#### …")`）。
_BLOCK_OPEN = re.compile(r"^\[markdown\] #{4}\s+(.*)$")
#: 一張**灰態**卡的標題 —— `ia.state_card()` 灰態時畫的 `st.markdown(f"**{title}**")`。
_CARD_NOT_READY = re.compile(r"^\[markdown\] \*\*(.+)\*\*$")
#: 一張 **`STATE_OK`** 卡的標題 —— `state_card()` 走 `st.metric(title, value)`。
_CARD_OK = re.compile(r"^\[metric\] (.+)$")
#: 一張 **`STATE_BUSINESS`** 卡的標題 —— `render_state.business_alert()` 把
#: 標題、數值、說明**全部塞進同一個 `st.markdown` 的 HTML 裡**。
#: ⚠️ 左軌那段特徵值**從 `render_state` import，不在這裡抄 hex**（§3.3；
#:    `tests/test_ia_kit.py` 也禁 IA 套件內出現 hex 字面值，同一個理由）。
_CARD_BUSINESS = re.compile(
    r"^\[markdown\] <div style='background:[^']*;border-left:"
    + re.escape(f"{BUSINESS_ALERT_RAIL_PX}px solid {BUSINESS_ALERT_ON_DARK}")
    + r"[^>]*>\s*<div style='[^']*'>(.*?)</div>")


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

    ⭐ **2026-09-06：三種卡開頭都要認，否則這個機制在本批當場失效。**
    骨架批三張卡**全是灰的**，而灰態卡的開頭是 `st.markdown("**標題**")` ——
    所以初版只認那一種就夠了。本批把兩張卡接上真資料之後：

    ========== ============================================ ==================
    卡片狀態    `state_card()` 實際畫出來的東西                 開頭長什麼樣
    ========== ============================================ ==================
    NOT_READY  `st.markdown("**標題**")` ＋ 灰字              `[markdown] **標題**`
    OK         `st.metric(標題, 值)` ＋ `st.caption(說明)`    `[metric] 標題`
    BUSINESS   `business_alert()` —— 標題／值／說明**全在
               同一個 `st.markdown` 的 HTML 裡**              `[markdown] <div …>`
    ========== ============================================ ==================

    **只認第一種的後果不是報錯，是那兩張卡從 `_segments()` 裡整個消失** ——
    於是任何「這張卡有沒有畫東西」的斷言都變成**對著不存在的 key 做檢查**，
    fail-open。**也就是說：這個好不容易降下來的粒度，會在卡片一接上真資料的那一刻
    自己失效，而且沒有任何東西會轉紅。** 本次連同另外兩種開頭一起認。

    ⚠️ **兩個容易被搞混的數字，據實分開寫**（量測日 2026-09-06，本組逐 fixture 實測）：

    - **落在所有單位之外的筆數 ＝ 7，而且對每一個「有持倉」的 fixture 都一樣。**
      成分固定：頁面 `## 標題` ＋ 職責 caption ＋ **整個 form**（caption ＋ 3 個 widget
      ＋ 送出鈕 ＝ 5 筆）。**也就是 unit-scoped 的斷言看不到 form 裡的任何東西。**
    - **整頁總筆數才是會漂移的那個**：`UNLOADED`／`DUPLICATE` = 19、`RICH`／`FAKE` = 20、
      `NEAR` = 21、`MIXED` = 23 —— 它跟著卡片狀態與表格列數走，**不要把它釘成一個數字**。
    - **空持倉是另一種形狀**：`units = 0`、**10 筆全部在單位外**（空狀態取代了所有區塊）。

    ⚠️ **本組第一次量這個時把兩者搞混了**：用「總筆數 − 單位內筆數」去算 outside，
    而 OK／BUSINESS 卡的 opener **自己就在 body 裡**（見下），於是每有一張這種卡就
    多扣一筆 —— `RICH` 因此被算成 5 而不是 7。**正確的量法是「第一個 opener 的索引」。**

    ⚠️ **OK／BUSINESS 兩種的 opener 自己就帶著內容**（`st.metric` 的值在下一筆
    `[metric_value]`；`business_alert` 的值與說明就在同一筆），所以它們的 body
    **包含 opener 自己那一筆**；`####` 區塊與灰態卡的 opener 只是標題，body 不含它。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _m = _BLOCK_OPEN.match(_p) or _CARD_NOT_READY.match(_p)
        if _m:
            _out.append((_m.group(1).strip(), []))
            continue
        _m2 = _CARD_OK.match(_p) or _CARD_BUSINESS.match(_p)
        if _m2:
            # opener 自帶內容 → 自己也算進 body（理由見上）。
            _out.append((_m2.group(1).strip(), [_p]))
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
#: ⚠️ **它刻意沒有 `moneydj_raw` / `metrics`** —— 也就是「已載入、但一個指標都算不出來」。
#: 本批之後它代表的是**資料不足**那條路徑，不是「一切正常」那條。
FAKE_HOLDINGS = [
    {"code": "ACDD19", "policy_id": "P1", "currency": "TWD",
     "loaded": True, "load_error": None},
]

#: 持股名清單。`_H_A` 與 `_H_A2` 的 Jaccard ＝ 3/4 ＝ 0.75（> 門檻 0.70 → 影子基金）；
#: `_H_B` 與前兩者交集為空 → 0.0。
#: ⚠️ **刻意不讓兩檔「完全相同」**：完全相同會算出 1.0，而 1.0 是一個
#:    「就算計算壞掉也很容易剛好出現」的值（本批修的那個空白名缺陷產出的正是 1.0）。
#:    用 0.75 這種**只有算對才會出現**的數字，突變才殺得死。
_H_A = [{"name": "AAPL", "pct": 10.0}, {"name": "MSFT", "pct": 9.0},
        {"name": "NVDA", "pct": 8.0}]
_H_A2 = _H_A + [{"name": "GOOG", "pct": 7.0}]
_H_B = [{"name": "TSM", "pct": 8.0}, {"name": "2330", "pct": 7.0}]


def _fund(code: str, *, div: float | None = 8.0, ret: float | None = 2.0,
          holdings: list | None = None, sharpe: float | None = 0.4,
          max_dd: float | None = -12.5, nav_date: str = "2026-09-01",
          ccy: str = "USD") -> dict:
    """一檔**指標算得出來**的持股。

    形狀是 `check_eating_principal_1y_mk` 文件裡的 **Nested**
    （`{moneydj_raw: {...}, metrics: {...}}`），也就是 `portfolio_funds` 的真實形狀
    （`ui/helpers/portfolio/load.py::_FUND_INFO_KEYS` 明列 `moneydj_raw` / `metrics`）。

    ⚠️ **`div=8.0, ret=2.0` 會被判成 🔴 吃本金**（含息 2% 低於配息 8%，缺口 6pp
    > `NEAR_DIVIDEND_WARNING_PCT`）—— 這不是隨手挑的數字，是本檔「有壞消息」情境的來源。
    """
    return {
        "code": code, "name": f"{code} 基金", "currency": ccy,
        "loaded": True, "load_error": None,
        "moneydj_raw": {
            "moneydj_div_yield": div, "perf": {"1Y": ret},
            "nav_date": nav_date, "currency": ccy,
            "holdings": {"top_holdings": holdings if holdings is not None else _H_A,
                         "sector_alloc": []},
        },
        "metrics": {"sharpe": sharpe, "max_drawdown": max_dd},
    }


#: 兩檔**吃本金且持股高度重疊**（→ 兩張卡都該亮業務警示）＋ 一檔健康且不重疊。
RICH_HOLDINGS = [
    _fund("AAA", holdings=_H_A),
    _fund("BBB", holdings=_H_A2),
    _fund("CCC", div=3.0, ret=9.0, holdings=_H_B),
]

#: 一檔落在**黃燈**（接近警戒）的持股：缺口 1pp，小於
#: `shared.signal_thresholds.NEAR_DIVIDEND_WARNING_PCT`（2pp）。
#: ⚠️ **這份 fixture 是被一顆存活的突變逼出來的**：`RICH_HOLDINGS` 裡一檔黃燈都沒有，
#:    於是「黃燈算不算吃本金」那條分支**根本沒被走到**，把它改成「黃燈也算吃本金」
#:    照樣全綠。**沒有走到的分支等於沒有守衛。**
NEAR_HOLDINGS = [_fund("NNN", div=8.0, ret=7.0, holdings=_H_B)]

#: 「已列入但還沒載入成功」的兩種持股 —— `_holdings()` 的過濾對象。
#: ⚠️ 同樣是被突變逼出來的（拿掉整條過濾照樣全綠）。**而它是本頁唯一一條 §1 邏輯。**
UNLOADED_HOLDINGS = [
    _fund("AAA", holdings=_H_A),
    {**_fund("BAD1", holdings=_H_A), "loaded": False},
    {**_fund("BAD2", holdings=_H_A), "load_error": "NAV 抓不到"},
]

#: **判得動的與判不動的混在一起** —— 1 檔吃本金 ＋ 1 檔覆蓋充足 ＋ 2 檔資料不足。
#: ⚠️ **這份 fixture 是被兩顆存活的突變逼出來的，而根因是覆蓋率、不是邏輯錯。**
#:    獨立稽核用探針量到 `_eating_note()` 在整個測試檔被呼叫 16 次，
#:    **`unknown` 每一次都是 0** —— 也就是「已判定 ＋ 資料不足」的混合情境
#:    **從來沒有任何 fixture 走到過**。於是說明句裡「N 檔覆蓋充足」與
#:    「N 檔資料不足、未列入判定」兩段可以整段砍掉而測試全綠。
#:    **程式本來就是對的；缺的是走到那條路的輸入。**
#: ⚠️ 「資料不足」那兩檔用的是「已載入、但沒有任何指標」的形狀（同 `FAKE_HOLDINGS`）——
#:    那是真的會發生的情況：NAV 抓回來了，但 MoneyDJ 的配息／績效沒抓到。
MIXED_HOLDINGS = [
    _fund("EAT", div=8.0, ret=2.0, holdings=_H_A),      # 🔴 吃本金
    _fund("OK1", div=3.0, ret=9.0, holdings=_H_B),      # 🟢 覆蓋充足
    {"code": "NA1", "name": "NA1 基金", "currency": "TWD",
     "loaded": True, "load_error": None},               # ⬜ 資料不足
    {"code": "NA2", "name": "NA2 基金", "currency": "TWD",
     "loaded": True, "load_error": None},               # ⬜ 資料不足
]

#: 同一檔基金買在兩張保單 —— `portfolio_funds` 的主鍵是 `(policy_id, code)`。
DUPLICATE_HOLDINGS = [
    {**_fund("AAA", holdings=_H_A), "policy_id": "P1"},
    {**_fund("AAA", holdings=_H_A), "policy_id": "P2"},
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
    """逐檔體檢表 9 欄，逐字對線框 —— 而且**是真表頭，不是一行 caption**。

    ⚠️ 欄位少一欄不會讓畫面壞掉，只會讓使用者少看到一個判斷依據 ——
    那正是「無聲退化」，所以要釘住。

    ⭐ **2026-09-06 依骨架批的登記改寫（那是登記說好的正解，不是把斷言放寬）。**
    骨架批表是空的，於是用一行 `st.caption("代碼／名稱／…")` 先告訴使用者這張表會有什麼；
    `_render_health_table` 的 docstring 就地登記了「**下一批請刪掉**，真資料接上之後
    表頭會講同一件事 —— 屆時它就變成鐵則 04 要禁的冗餘占位」，並指定
    「**正解是改成驗真表頭，不是刪掉那個斷言**」。本次照辦：

    - `_table_rows()` 產出的 **key 順序**必須逐字等於 `HEALTH_TABLE_COLUMNS`
      （這一半是結構的，看的是程式真的會拿什麼當表頭）；
    - 畫面紀錄裡的 `[dataframe]` 那一筆必須列出九欄
      （這一半是畫面的，看的是使用者真的看得到）。

    ⛔ **兩半都要**：只驗結構的話，`wide_table()` 被拿掉都不會紅；
       只驗畫面的話，欄序被打亂（例如改用 `dict` 重組）不會紅。
    """
    assert HEALTH_TABLE_COLUMNS == (
        "代碼", "名稱", "幣別", "近 1 年", "Sharpe",
        "最大回撤", "配息覆蓋", "五桶評等", "資料日期"), (
        f"逐檔體檢表的欄位與線框 Tab 02 不符：{HEALTH_TABLE_COLUMNS}")
    assert len(HEALTH_TABLE_COLUMNS) == 9

    # ── 一半：真表頭（欄名**與順序**都要對）────────────────────────
    _rows = _table_rows(RICH_HOLDINGS)
    assert _rows, "`_table_rows()` 對有持股的輸入回了空清單。"
    for _r in _rows:
        assert tuple(_r) == HEALTH_TABLE_COLUMNS, (
            "逐檔體檢表的欄名／欄序與線框不符。\n"
            f"  實際：{tuple(_r)}\n  線框：{HEALTH_TABLE_COLUMNS}")

    # ── 另一半：畫面上真的看得到那九欄 ─────────────────────────────
    _parts = _render(portfolio=RICH_HOLDINGS)
    _header = [_p for _p in _parts if _p.startswith("[dataframe] ")]
    assert _header, (
        "畫面上沒有任何表格 —— 有持股時逐檔體檢表應該畫得出來。\n"
        + "\n".join(_parts))
    for _col in HEALTH_TABLE_COLUMNS:
        assert _col in _header[0], f"表頭上看不到欄位「{_col}」：{_header[0]}"


def test_the_table_never_shows_a_bucket_grade_because_there_is_no_such_thing():
    """⛔「五桶評等」整欄必須是 `⬜`，而且畫面上要說明為什麼。

    **這是本批唯一一個「明明有東西可以填、但刻意不填」的欄位**，所以要釘住。

    線框寫的「五桶評等」在本 repo 是**總經**概念（`shared/macro_buckets.py`：
    長期／中期／短線／拐點／新聞），**沒有逐檔基金版本**。逐檔真正存在的是
    `services/health/grade.py::compute_4d_health` 的 **4D/5D Grade（A～F）**——
    維度不同、級距不同、名字不同。**把 4D Grade 印在「五桶評等」欄底下，
    使用者完全看不出那是另一套評等**（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險），
    而這正是本批在 `Principal_Erosion` 上避開的同一個坑。

    ⚠️ 空欄若不說明，會被讀成「這幾檔沒有評等」而不是「這個系統沒有這個評等」——
    所以除了留白，畫面上還要有一句話。
    """
    _rows = _table_rows(RICH_HOLDINGS)
    _bad = [_r["代碼"] for _r in _rows if _r["五桶評等"] != NOT_READY_MARK]
    assert not _bad, (
        f"「五桶評等」欄被填了東西（{_bad}）—— 本站沒有逐檔的五桶評等。\n"
        "若要改用 4D Grade，那是**換一個評等定義**，屬客戶 gate，不是實作細節。")
    # ⭐ **斷言範圍限定在逐檔體檢表這個單位內**（2026-09-06 獨立稽核第四項）。
    #    原本這裡用的是 `_text(...)`（**整頁**），於是刪掉逐檔表底下那句說明照樣全綠 ——
    #    因為「組合健康總分」那一塊的灰字**同時含有「五桶」與「4D Grade」**，
    #    **鄰居的字替它通過了**（實測：刪掉 caption → 29 passed）。
    #    這正是 `_units()` docstring 自己寫的那句：「**邊界一寬，鄰居的字就會替你通過**」——
    #    只是本條當初用的是 `_text()` 而不是 `_segments()`，所以沒享受到那個粒度。
    _table_body = "\n".join(
        _segments(_render(portfolio=RICH_HOLDINGS)).get("逐檔體檢表", []))
    assert _table_body, "逐檔體檢表這個單位不見了。"
    assert "五桶" in _table_body and "4D" in _table_body, (
        "「五桶評等」整欄留白，但**這張表底下**沒有解釋為什麼 —— "
        "沒解釋的空欄會被讀成「這幾檔沒有評等」。\n"
        "⚠️ 別把別的區塊的說明算進來：使用者看表的時候不會滑上去讀總分那一塊。\n"
        + _table_body)


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


def test_no_holdings_does_not_also_print_the_deferred_block_excuses():
    """兩種灰不得混在一起。

    ⚠️ 這條擋的是一個很容易犯、而且看起來無害的錯：沒有持倉時**同時**印出
    那兩塊「還沒接上」的灰字。使用者會以為「去 ④ 加了基金這裡就會出現」——
    其中一塊不會（評等定義未定），另一塊也不會（要等下一個批次）。**一次只給一個下一步。**

    ⚠️ **比對模組常數本體，不硬抄字面值。** 硬抄的話，常數一改措辭這條就永遠是 True ——
    它守的 bug 照樣存在、而它不再看得見（獨立紅隊實證過這個 fail-open）。

    📌 **2026-09-06 改名＋換受測對象**：舊版比對的是骨架批的共用常數 `_PENDING_NOTE`
    （「本頁分批上線，這一塊的內容還沒接上」）。本批把三塊接上真資料後，
    那個共用常數已**整個刪除**（見 `page_02_health.py` 該處的長註：留一句含糊的話
    給兩個具體原因共用，等於把可行動的原因蓋掉）。**本條守的東西沒有變**，
    換的只是它現在要盯住的那兩句具名理由。
    """
    _all = _text(_render(portfolio=[]))
    for _note in (_SCORE_PENDING_NOTE, _LAG_PENDING_NOTE):
        assert _note not in _all, (
            "沒有持倉時不應同時印出「這一塊還沒接上」的灰字 —— 兩個下一步會互相抵消。\n"
            f"洩漏的是：{_note}\n\n" + _all)


def test_no_holdings_hides_the_diagnosis_blocks_entirely():
    """沒有持倉時，三塊診斷區塊**整個不畫**，而不是各印一句灰字。

    線框把空狀態畫成**取代**內容區，不是疊在它上面；四份在講同一件事的灰字
    就是鐵則 04 要禁的「冗餘占位」。
    """
    _seg = _segments(_render(portfolio=[]))
    _leaked = [_b for _b in EXPECTED_BLOCKS + EXPECTED_CARDS if _b in _seg]
    assert not _leaked, (
        f"沒有持倉時仍畫出了診斷區塊 {_leaked} —— 空狀態應**取代**它們。")


#: 本批**刻意維持灰態**的兩塊，以及各自的具名理由。
#: ⚠️ **這張表是「還沒接上的清單」，不是「可以一直灰下去的清單」。**
#:    每一項都必須有一個**具體、可被推翻的**理由；接上了就從這裡移走，
#:    移走的同時 `_DEFERRED` 會少一項，下面那條 `test_wired_blocks_show_real_content`
#:    的參數就多一項 —— 兩張表是互補的，不會有東西掉在中間。
_DEFERRED: dict[str, str] = {
    "組合健康總分": _SCORE_PENDING_NOTE,
    "衛星連續落後": _LAG_PENDING_NOTE,
}

#: 本批**已接上真資料**的三塊。
_WIRED: tuple[str, ...] = ("吃本金警示", "影子基金重疊", "逐檔體檢表")


def test_the_two_tables_together_cover_every_block_exactly_once():
    """`_DEFERRED` ∪ `_WIRED` 必須**恰好**等於畫面上的五塊，不重不漏。

    ⚠️ 沒有這一條的話，新增一塊卻兩張表都忘了登記，**下面兩條測試都不會轉紅**
    —— 那一塊就變成完全沒有人在看的區域（本檔前身正是靠 parametrize 的清單
    在守，而清單漏一項是無聲的）。
    """
    assert set(_DEFERRED) | set(_WIRED) == set(EXPECTED_BLOCKS) | set(EXPECTED_CARDS)
    assert not (set(_DEFERRED) & set(_WIRED)), "同一塊不能同時算「還沒接」與「已接上」。"


@pytest.mark.parametrize("block", sorted(_DEFERRED))
def test_deferred_blocks_stay_grey_and_say_exactly_why(block: str):
    """**刻意還沒接**的那兩塊：要有灰態記號，而且理由必須是**那一塊自己的**。

    ⚠️ **重點在後半句。** 前身版本只驗「有沒有灰、有沒有共用的那句理由」，
    於是**三張卡的理由互換**照樣全綠（獨立紅隊 2026-09-05 打穿的四項之一）。
    本條改成比對**該塊自己的具名常數**：理由互換 ⇒ 兩塊都轉紅。

    ⛔ **這條不是「允許一直灰下去」的許可證。** 它釘的是「灰的時候必須說清楚為什麼」；
       兩個理由都是**可被推翻的具體事實**（一個等客戶回覆評等定義，
       一個等波段觀測站搬遷），推翻了就把它從 `_DEFERRED` 移到 `_WIRED`。
    """
    _seg = _segments(_render(portfolio=RICH_HOLDINGS))
    assert block in _seg, (
        f"區塊「{block}」在畫面上不見了。現有單位：{list(_seg)}")
    _body = "\n".join(_seg[block])
    assert NOT_READY_MARK in _body, (
        f"區塊「{block}」沒有灰態記號 {NOT_READY_MARK!r} —— "
        "內容還沒接上就要誠實留灰，不得空著也不得填示意值（§1）。\n" + _body)
    assert _DEFERRED[block] in _body, (
        f"區塊「{block}」的灰態理由不是它自己的那一句 —— "
        "理由互換會讓使用者拿到一個對別的區塊才成立的解釋。\n"
        f"應含：{_DEFERRED[block]}\n實際：{_body}")


@pytest.mark.parametrize("block", _WIRED)
def test_wired_blocks_show_real_content_when_the_data_is_there(block: str):
    """**已接上**的三塊：資料齊全時必須畫出真內容，**不得再是灰的**。

    ⚠️ 這條是前身 `test_every_block_is_grey_until_its_content_lands` 的**反面**，
    也是它自己的 docstring 指定的下場：「下一批把真內容接上時，這條會轉紅 ——
    **那是預期的**，屆時請把它改成『真內容放行』，**不要把它放寬成「有東西就好」**」。
    本次照辦：不是放寬，是**換一個方向釘死** —— 資料齊全卻仍是灰的，就是退化。
    """
    _seg = _segments(_render(portfolio=RICH_HOLDINGS))
    assert block in _seg, (
        f"區塊「{block}」在畫面上不見了。現有單位：{list(_seg)}")
    _body = _seg[block]
    assert "\n".join(_body).strip(), f"區塊「{block}」有標題但沒有任何內容 —— 那是空占位。"
    # ⚠️ 判準是「**有沒有一個灰態 widget**」，不是「內文有沒有出現 ⬜ 這個字」。
    #    `render_state.not_ready()` 畫的是 `st.caption(f"{NOT_READY_MARK} …")`
    #    ⇒ 灰態 ＝ **開頭就是 ⬜ 的 caption**。
    #    用「內文含 ⬜」會誤判：逐檔體檢表的「五桶評等」欄每一格都是 ⬜（整欄沒有來源，
    #    見該欄自己的測試），那是**表格內容**，不是「這一塊沒接上」。
    _grey = [_p for _p in _body
             if _p.startswith(f"[caption] {NOT_READY_MARK}")]
    assert not _grey, (
        f"區塊「{block}」在資料齊全時仍是灰態 —— 那是退化。\n"
        + "\n".join(_grey))


def test_wired_blocks_go_grey_again_when_the_data_is_missing():
    """反過來：資料**不齊**時，那三塊必須誠實退回灰態，**不得印 0**。

    ⛔ **這條擋的是本批最危險的一種退化**：把「算不出來」顯示成「0 檔吃本金」。
       兩者在畫面上長得一模一樣，但意思相反 —— 一個是「檢查過了，沒事」，
       另一個是「根本沒檢查成」。使用者只會看到綠色的 0（`CLAUDE.md §1`）。

    `FAKE_HOLDINGS` 是「已載入、但沒有任何指標」的那種持股（真的會發生：
    NAV 抓回來了但 MoneyDJ 的配息／績效沒抓到）。
    """
    _seg = _segments(_render(portfolio=FAKE_HOLDINGS))
    for _b in ("吃本金警示", "影子基金重疊"):
        assert _b in _seg, f"區塊「{_b}」不見了。現有單位：{list(_seg)}"
        _body = "\n".join(_seg[_b])
        assert NOT_READY_MARK in _body, (
            f"「{_b}」在算不出來時沒有退回灰態。\n" + _body)
        assert "0 檔" not in _body and "0 對" not in _body, (
            f"「{_b}」把「算不出來」印成了 0 —— 那會被讀成「檢查過了，沒事」。\n" + _body)


#: 本條**實際釘住**的字面值。列成常數，是為了讓「它到底守了什麼」可以被讀出來，
#: 而不是藏在 docstring 的形容詞裡。
#:
#: ⚠️ **2026-09-06 縮小射程，理由必須看懂，否則下一個人會以為這是放水。**
#: 骨架批四塊全灰，所以「線框的示意值一個都不准出現在**整頁**」是對的。
#: 本批把三塊接上真資料之後，那個寫法**會開始誤判**：
#: `0.78` 是一個**合法的相似度**，真的算出 0.78 的那一天，這條會把**正確的畫面**判成造假。
#: 一條把真資料判成假資料的規則，下一個人只會把它刪掉 —— **那才是真正的損失。**
#: 現行射程：**只釘還沒接上的那兩塊**（見 `_DEFERRED`），它們印出任何數字都是捏造。
#: 已接上的那三塊改由 `test_the_numbers_on_the_cards_come_from_the_ssot` 守
#: —— 那條問的是「**這個數字是不是 SSOT 算的**」，比列舉字面值強得多。
_PINNED_FAKE_VALUES: tuple[str, ...] = (
    "72 ／ 100", "72／100", "72/100", "0.78", "相似度 0.78", "1 檔", "2 檔",
)


def test_the_deferred_blocks_never_print_the_illustrative_numbers_from_the_wireframe():
    """⛔ 線框那幾個**示意值**不准出現在**還沒接上的那兩塊**裡。

    為什麼要有這條：填一個看起來合理的分數，使用者**完全看不出它是假的**，
    而且會拿它去做決定（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ## ⚠️ 這條**實際**守得到什麼（照實寫，不要照抄上一版的形容詞）

    **只在 `_DEFERRED` 那兩塊的範圍內、只釘 `_PINNED_FAKE_VALUES` 這幾個字面寫法。**

    **明確守不到（獨立紅隊 2026-09-05 逐項實跑，每一項都 18 passed；本批未改善）**：
      - **裸 `72`** —— `st.caption("參考：72 分")`、`st.metric("總分", 72)` 都穿過去；
      - **全形數字**（`０.７８`）。

    ⚠️ **上一版的射程是整頁，本批縮到只剩兩塊** —— 理由寫在 `_PINNED_FAKE_VALUES`
    上面（整頁射程會在真資料算出 0.78 的那天把正確畫面判成造假）。
    **已接上的三塊不是沒人守，是換人守**：`test_the_numbers_on_the_cards_come_from_the_ssot`
    直接驗「畫面上的數字跟著 SSOT 走」，那是列舉字面值做不到的事。
    """
    _seg = _segments(_render(portfolio=RICH_HOLDINGS))
    for _block in _DEFERRED:
        _body = "\n".join(_seg.get(_block, []))
        for _fake in _PINNED_FAKE_VALUES:
            assert _fake not in _body, (
                f"還沒接上的區塊「{_block}」印出了線框的示意值 {_fake!r} —— "
                "那不是資料，是線框用來示範版面的假數字。\n" + _body)


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
# 真資料：數字必須是 SSOT 算的，而且必須是**對的那個** SSOT
# ══════════════════════════════════════════════════════════════════

def test_the_numbers_on_the_cards_come_from_the_ssot():
    """卡片上的數字**跟著 SSOT 走**。換掉 SSOT 的答案，畫面必須跟著換。

    ⭐ **這條取代了「列舉哪些字面值算捏造」那種守法，而且強得多。**
    列舉法只能擋「線框裡那幾個示意數字」，擋不掉**任何**其他捏造值
    （紅隊實測：裸 `72`、`st.metric("總分", 72)` 全部穿過去）。
    本條問的是另一個問題：**這個數字到底是不是算出來的？**
    —— 把 SSOT 的回答換掉，畫面若不動，就代表它根本沒在讀 SSOT。

    ⚠️ patch 的是**定義處的模組屬性**（`services.health.dividend.…`），
    這是本頁刻意用**函式內 lazy import** 的原因之一：
    module 層 `from X import f` 會把函式綁進本頁的命名空間，之後 patch `X.f` 完全無效。
    """
    from unittest import mock

    # ── 吃本金：SSOT 說三檔全紅 → 卡片必須說 3 檔 ──────────────────
    with mock.patch("services.health.dividend.check_eating_principal_1y_mk",
                    return_value={"alert_level": "red", "coverage": 0.25}):
        _seg = _segments(_render(portfolio=RICH_HOLDINGS))
    _body = "\n".join(_seg.get("吃本金警示", []))
    assert "3 檔" in _body, (
        "SSOT 說三檔都在吃本金，卡片卻沒有顯示 3 檔 —— 這個數字不是算出來的。\n" + _body)

    # ── 同一份持股，SSOT 改口說全綠 → 卡片必須跟著變 0 檔 ──────────
    with mock.patch("services.health.dividend.check_eating_principal_1y_mk",
                    return_value={"alert_level": "green", "coverage": 1.5}):
        _seg = _segments(_render(portfolio=RICH_HOLDINGS))
    _body = "\n".join(_seg.get("吃本金警示", []))
    assert "0 檔" in _body, (
        "SSOT 改口說沒有人吃本金，卡片卻沒有跟著變 —— 數字被寫死了。\n" + _body)

    # ── 影子基金：SSOT 給幾對就是幾對 ─────────────────────────────
    # ⚠️ **這裡刻意給「兩對」而不是一對。** 真實 fixture 本來就只算得出一對，
    #    所以若用一對來驗，把對數**寫死成 `"1 對"`** 的突變會存活（實測過）——
    #    斷言值必須是「只有真的讀了 SSOT 才會出現」的那個數。
    with mock.patch("services.portfolio_service.calc_holdings_overlap",
                    return_value={"matrix": object(), "method": "holdings",
                                  "notes": "", "shadow_pairs": [("AAA", "BBB", 0.91),
                                                                ("AAA", "CCC", 0.83)]}):
        _seg = _segments(_render(portfolio=RICH_HOLDINGS))
    _body = "\n".join(_seg.get("影子基金重疊", []))
    assert "2 對" in _body and "0.91" in _body, (
        "影子基金卡沒有反映 SSOT 給的那兩對（2 對 / 最高 0.91）。\n" + _body)


def test_the_eating_principal_card_never_uses_the_momentum_signal():
    """⛔ 吃本金**只准**走含息 vs 配息率的 SSOT，**不准**改接淨值動能訊號。

    **這是本批最貴的一個坑，所以用一條測試把它焊死。**

    `ui/components/mk_dashboard.py::tag_principal_erosion` 產出的欄位叫
    **`Principal_Erosion`（直譯就是「吃本金」）**，名字和這張卡完全對得上 ——
    但它自己的 docstring 逐字寫著：

        ⚠️ v19.402 正名：本訊號實為「淨值連續下跌動能」，**非配息覆蓋/吃本金**。
        …與「吃本金」（含息總報酬 vs 配息率）是**不同訊號**，**勿混用**。

    接錯的後果**不是畫面壞掉，是一張標題正確、數字正確、意思完全錯的卡**：
    一檔**完全不配息**的基金淨值連跌三個月就會被標成「吃本金」。
    使用者看不出來 —— 那正是 `CLAUDE.md §1` 說的「錯誤的數字比沒有數字更危險」。

    ⚠️ **本條與 `test_the_page_does_not_delegate_to_the_old_tab` 不重複。**
       那條擋的是 `import`；本條擋的是**符號名出現在本檔任何地方**
       （含有人把那段邏輯**照抄**進來 —— 抄過來就沒有 import 可以擋了）。
    ⛔ **本條看不到的**：有人把同樣的滾動報酬邏輯抄進來**並改名**。
       靜態規則到此為止；那一種要靠 code review。
    """
    _src = SRC.read_text(encoding="utf-8")
    _tree = ast.parse(_src)
    # 呼叫與屬性存取都掃 —— 只掃 import 會漏掉「照抄過來」那條路。
    _bad = [f"第 {_n.lineno} 行 {ast.unparse(_n)[:60]}"
            for _n in ast.walk(_tree)
            if (isinstance(_n, ast.Name) and _n.id in
                ("tag_principal_erosion", "Principal_Erosion"))
            or (isinstance(_n, ast.Attribute) and _n.attr == "tag_principal_erosion")]
    assert not _bad, (
        "吃本金卡接到了「淨值連續下跌動能」訊號（`Principal_Erosion`）——\n  "
        + "\n  ".join(_bad)
        + "\n那是**不同的訊號**（該函式的 docstring 自己寫著「勿混用」）。"
        "\n正解是 `services.health.dividend.check_eating_principal_1y_mk`。")
    # 而且真正該用的那一個必須在場（否則上面那條可以靠「什麼都不接」通過）。
    assert "check_eating_principal_1y_mk" in _src, (
        "本頁沒有呼叫吃本金的 SSOT `check_eating_principal_1y_mk` —— "
        "那張卡的數字不可能是對的。")


def test_blank_holding_names_never_become_a_perfect_match():
    """⛔ 持股名稱是**純空白**時，不得產生「相似度 1.00」的假影子警示。

    **這條擋的是一個實際存在的上游缺陷，不是假想的。**
    SSOT `services/portfolio_service.py::calc_holdings_overlap` 收集持股名時寫的是
    ``{… for h in tops if h.get("name")}`` —— 過濾取的是 **strip 之前**的 truthy。
    名稱為 `"  "` 時：通過過濾 → 正規化成 `""` → 集合變成 `{""}` →
    **兩檔共享 `{""}` ⇒ Jaccard = 1.0 ⇒ 一對「相似度 1.00」的影子基金**。

    **本組 2026-09-06 於 `origin/main` 實跑確認缺陷仍在**（見 PR 描述的指令與輸出）；
    `services/homogeneity.py::_has_dims` 也早就就地記著這件事
    （「根因在 SSOT 端把純空白名當資料（既有行為，本批無權改）」）。

    本頁的處置是**把它擋在自己的輸入邊界**（`_clean_holdings`，判準與 `homogeneity`
    的鏡像版一致：strip **後**非空），**不改 SSOT** —— 那是 8 個 caller 共用的計算入口，
    且本批的檔案邊界只有兩個檔。

    ⚠️ **本條在上游被修好之後也不會誤紅**：它斷言的是「畫面上不出現假警示」，
       上游修好了照樣成立。但**移除 `_clean_holdings` 會讓它立刻轉紅** —— fail-closed。
    """
    _blank = [_fund("AAA", holdings=[{"name": "   ", "pct": 10.0}]),
              _fund("BBB", holdings=[{"name": "\t", "pct": 10.0}])]
    _seg = _segments(_render(portfolio=_blank))
    _body = "\n".join(_seg.get("影子基金重疊", []))
    assert "1.00" not in _body and "1 對" not in _body, (
        "兩檔基金的持股名稱其實都是空白，卻被判成「完全重疊」——\n"
        "那是一個**最高信心的假警示**（Jaccard=1.0），使用者完全看不出來。\n" + _body)
    assert NOT_READY_MARK in _body, (
        "持股名稱全為空白 ＝ 沒有可比對的持股資料，應誠實走灰態。\n" + _body)


def test_the_shadow_card_owns_up_to_the_funds_it_could_not_compare():
    """被排除在比對之外的檔**要具名說出來**，不得靜默縮小比對範圍。

    `services/homogeneity.py` 的模組 docstring 點名的正是這個病：
    「現況兩個計算入口對缺資料檔**靜默縮小比對範圍**…本檔把被跳過的檔**具名帶出**，
    供 UI ⬜ 誠實揭露（§1）」。一張說「0 對影子基金」的卡，若其中兩檔根本沒被比到，
    那個 0 是**誤導**。
    """
    _mixed = [_fund("AAA", holdings=_H_A), _fund("BBB", holdings=_H_B),
              _fund("CCC", holdings=[])]
    _seg = _segments(_render(portfolio=_mixed))
    _body = "\n".join(_seg.get("影子基金重疊", []))
    assert "CCC" in _body, (
        "有一檔沒有持股／產業資料、根本沒被比對到，卡片卻沒說 —— "
        "那會讓「沒有影子基金」這個結論看起來比實際上更有把握。\n" + _body)


def test_a_thin_margin_is_not_reported_as_eating_principal():
    """黃燈（缺口在警戒線內）**不算**吃本金 —— 跨頁數字必須一致。

    ⚠️ **這條是被一顆存活的突變逼出來的**：`RICH_HOLDINGS` 裡一檔黃燈都沒有，
    所以把「黃燈也算吃本金」寫進去照樣全綠。**沒有被走到的分支等於沒有守衛。**

    為什麼是「不算」：`red` 是本 repo **既有的、production 正在用的**判準 ——
    `ui/tab_fund_grp_health.py::_eats_principal_flag` 逐字寫
    「red→吃本金；green/**yellow**→不吃（黃＝margin 薄但未吃）」，
    `services/switch_advisor.py` 與 NAS 週報也吃同一個 `status`。
    本頁若改用「覆蓋率 < 1.0」，同一個組合在 ② 會顯示「3 檔」、在 ④ 換股顧問顯示「1 檔」
    —— **兩個都對，但使用者只會覺得系統壞了**（`CLAUDE.md §2.1`）。

    ⚠️ **黃燈沒有被丟掉**：它必須以「接近警戒」出現在說明裡，不得靜默併進綠燈。
    """
    _seg = _segments(_render(portfolio=NEAR_HOLDINGS))
    _body = "\n".join(_seg.get("吃本金警示", []))
    assert "0 檔" in _body, (
        "缺口在警戒線內（黃燈）被算成了吃本金 —— 那會和 ④ 換股顧問的數字打架。\n" + _body)
    assert "接近警戒" in _body, (
        "黃燈被靜默併進「健康」了 —— 使用者看不到「這檔margin 已經很薄」。\n" + _body)


def test_funds_that_never_loaded_are_left_out_of_every_conclusion():
    """⛔「已列入但沒載入成功」的持股**不得**進入任何診斷結論。

    ⚠️ **這條是被一顆存活的突變逼出來的，而且它守的是本頁唯一一條 §1 邏輯**
    ——`_holdings()` 的 `loaded` / `load_error` 過濾。骨架批的守衛清單就地登記過
    「整條拿掉 → 全綠」；本批之前那還只是「少過濾幾筆」，**本批之後它會直接餵髒資料
    進 SSOT**：一檔 NAV 沒抓回來的基金，`compute_1y_total_return` 會回 None，
    於是它被算成「資料不足」而稀釋掉分母 —— 使用者看到的「N 檔資料不足」裡，
    混進了根本還沒開始載入的檔。

    `UNLOADED_HOLDINGS` = 1 檔正常（吃本金）＋ 1 檔 `loaded=False` ＋ 1 檔有 `load_error`。
    正確行為：三塊都只看得到那 1 檔。
    """
    _rows = _table_rows(_uniq_by_code(_holdings_of(UNLOADED_HOLDINGS)))
    _codes = [_r["代碼"] for _r in _rows]
    assert _codes == ["AAA"], (
        "沒載入成功的基金進了逐檔體檢表 —— 拿不完整的資料生一個看起來完整的結論（§1）。\n"
        f"實際列出：{_codes}")
    _all = _text(_render(portfolio=UNLOADED_HOLDINGS))
    for _bad in ("BAD1", "BAD2"):
        assert _bad not in _all, f"沒載入成功的「{_bad}」出現在畫面上。\n{_all}"


def test_the_same_fund_across_two_policies_is_counted_once():
    """同一檔基金買在兩張保單，**只能算一次**。

    ⚠️ 同樣是被一顆存活的突變逼出來的（拿掉去重照樣全綠，因為 fixture 裡沒有重複 code）。

    `portfolio_funds` 的主鍵是 `(policy_id, code)`，所以同一檔基金買在兩張保單就有兩筆。
    不去重的話「2 檔吃本金」可能其實只有 1 檔 —— 而使用者**無從得知**。
    更糟的是影子基金那張卡：同一檔基金會和**它自己**比對出 1.00 的完美重疊。
    """
    _rows = _table_rows(_uniq_by_code(_holdings_of(DUPLICATE_HOLDINGS)))
    assert [_r["代碼"] for _r in _rows] == ["AAA"], (
        f"同一檔基金跨兩張保單被算了兩次：{[_r['代碼'] for _r in _rows]}")
    _seg = _segments(_render(portfolio=DUPLICATE_HOLDINGS))
    _eat = "\n".join(_seg.get("吃本金警示", []))
    assert "1 檔" in _eat, f"吃本金檔數把同一檔算了兩次。\n{_eat}"
    _shadow = "\n".join(_seg.get("影子基金重疊", []))
    assert "1.00" not in _shadow and "1 對" not in _shadow, (
        "同一檔基金和它自己比出了「完美重疊」的影子警示。\n" + _shadow)


def test_the_table_falls_back_to_the_empty_state_when_no_row_survives():
    """一列都湊不出來時，走**空狀態**，不畫空表格外框（鐵則 04）。

    ⚠️ 這條看起來像永遠走不到 —— 沒有持倉時 `render_holdings_health()` 就提早
    走空狀態了。但**有一條窄路**：持股存在、卻全部沒有可用的 `code`
    （`_uniq_by_code()` 以 code 為鍵，空 code 會被丟掉）。
    突變「空表時塞一列 `—`」原本存活，正是因為沒有任何情境走到這條路。
    """
    _blank_code = [{**_fund("AAA", holdings=_H_A), "code": "  "}]
    _parts = _render(portfolio=_blank_code)
    assert not [_p for _p in _parts if _p.startswith("[dataframe] ")], (
        "一列都沒有卻還是畫了表格 —— 鐵則 04：不畫空表格外框。\n" + "\n".join(_parts))
    assert "逐檔體檢還沒有可顯示的列" in _text(_parts), (
        "一列都沒有時沒有走空狀態三要素。\n" + "\n".join(_parts))


# ══════════════════════════════════════════════════════════════════
# §1 的核心不變量：「算不出來」與「真的是 0」不得長得一樣
# ══════════════════════════════════════════════════════════════════

def test_a_value_we_could_not_compute_never_renders_as_zero():
    """⛔ 算不出來 → `⬜`；真的是 0 → `0`。**兩者不得相同。**

    **這條是 2026-09-06 獨立稽核抓到的第一項：本頁最核心的 §1 不變量原本零守衛。**
    把 `_pct` / `_num` 的 `NOT_READY_MARK` 換成 `"0"`，**29 顆測試全綠**：

        {'代碼':'ACDD19', 'Sharpe':'0.00', '最大回撤':'0.0%', '配息覆蓋':'0.00'}  → 29 passed

    ⚠️ `_pct` 自己的 docstring 早就寫著「`0` 與『不知道』在一張表裡長得一模一樣，
    而它們的意思完全相反」——**話寫了，但沒有任何東西守著它。**

    為什麼特別貴：
    - `最大回撤 0.0%` 讀起來是「這檔從沒跌過」，真相是「我們沒有它的淨值歷史」；
    - `配息覆蓋 0.00` 更糟 —— 那是**憑空生出來的最壞值**，等於對一檔我們一無所知的
      基金**報一個假警**（`CLAUDE.md §1`：錯誤的數字比沒有數字更危險）。

    ⚠️ **這一項的嚴重度被一件事放大**：本頁**目前沒有任何 production caller**
    （`git grep -c 'page_02_health' origin/main -- app.py` → 0）——
    沒有人在畫面上看得到它，**守衛就是唯一的防線**。
    """
    assert _pct(None) == NOT_READY_MARK, "`_pct(None)` 應為灰態記號。"
    assert _num(None) == NOT_READY_MARK, "`_num(None)` 應為灰態記號。"
    # ⭐ 關鍵的一半：**真的是 0 的時候要照印 0**。
    #    只驗「None → ⬜」不夠 —— 把兩者都回 ⬜ 也會通過，那是另一個方向的說謊。
    assert _pct(0.0) == "0.0%", "真的是 0% 的時候不可以被藏成灰態。"
    assert _num(0.0) == "0.00", "真的是 0 的時候不可以被藏成灰態。"
    assert _pct(None) != _pct(0.0) and _num(None) != _num(0.0), (
        "「算不出來」與「真的是 0」在畫面上長得一模一樣 —— 那兩件事意思相反。")


def test_a_row_we_know_nothing_about_is_blank_in_every_computed_column():
    """一檔「已載入、但一個指標都算不出來」的基金：**每一個計算欄都必須是 `⬜`。**

    這是上一條的端到端版本 —— 上一條驗格式化函式，這一條驗**真的走完整條路之後**
    沒有人在中途塞一個 0 進來。`FAKE_HOLDINGS` 就是那條路（已載入，但無
    `moneydj_raw` / `metrics`，真的會發生：NAV 抓回來了但配息／績效沒抓到）。

    ⚠️ **代碼／名稱／幣別不在受檢範圍** —— 那三欄是 session 契約直接帶來的真值，
    本來就該有東西。受檢的是**要靠計算才有的那些**。
    """
    _rows = _table_rows(_uniq_by_code(_holdings_of(FAKE_HOLDINGS)))
    assert _rows, "`FAKE_HOLDINGS` 應該產出一列。"
    _computed = ("近 1 年", "Sharpe", "最大回撤", "配息覆蓋", "五桶評等")
    for _r in _rows:
        for _col in _computed:
            assert _r[_col] == NOT_READY_MARK, (
                f"「{_col}」算不出來卻印了 {_r[_col]!r} —— "
                "那會被讀成一個真實的觀測值（§1）。\n" + str(_r))
        assert _r["資料日期"].startswith(NOT_READY_MARK), (
            f"沒有淨值日期卻印了 {_r['資料日期']!r}。")


def test_the_thresholds_printed_on_the_cards_come_from_the_ssot():
    """卡片**說明句裡的門檻數字**也必須跟著 SSOT 走，不只是主數值。

    **這是 2026-09-06 獨立稽核抓到的第二項。** 原本有
    `test_the_numbers_on_the_cards_come_from_the_ssot`，名字看起來涵蓋這件事，
    但它 patch 的是**產出結果的函式**（`check_eating_principal_1y_mk` /
    `calc_holdings_overlap`），**沒有 patch 門檻常數** —— **值有守、門檻文案沒守**。
    實測兩顆突變都存活：

        `_eating_note` 門檻寫死 1     → 畫面印「超過 **1** 個百分點」（真實判定仍是 2）→ 29 passed
        `_shadow_formula` 寫死 0.99   → 畫面印「相似度 ≥ **0.99**」（真實判定仍是 0.70）→ 29 passed

    ⚠️ **`_shadow_formula` 自己的 docstring 逐字預言了這件事**：「SSOT 一改，
    判定會跟著改、而畫面上的說明不會 … **卻沒有任何東西會報錯**。」**實測：那句話是真的。**

    ⚠️ 為什麼這比看起來嚴重：畫面上的門檻**是使用者用來理解那個數字的唯一線索**。
    門檻說 0.99、實際用 0.70，使用者會以為「沒被標示的那幾對都很不像」——
    但其實 0.70~0.99 之間那些**已經被判為影子基金了**。**數字沒錯，解釋錯了。**
    """
    from unittest import mock

    _base = _text(_render(portfolio=RICH_HOLDINGS))
    assert "超過 2 個百分點" in _base and "≥ 0.70" in _base, (
        "基線與 SSOT 現值對不上，本條的前提不成立。\n" + _base)

    # ⚠️ patch 的是**常數的定義處**。本頁的兩個函式都是**呼叫當下**才 import 它們，
    #    所以 patch 得到；換成 module 層 import 就會 patch 不到（那也正是本頁
    #    刻意用函式內 lazy import 的理由之一）。
    with mock.patch("shared.signal_thresholds.NEAR_DIVIDEND_WARNING_PCT", 5.0), \
         mock.patch("shared.signal_thresholds.SHADOW_FUND_THRESHOLD_RATIO", 0.55):
        _patched = _text(_render(portfolio=RICH_HOLDINGS))
    assert "超過 5 個百分點" in _patched, (
        "吃本金卡的門檻文案沒有跟著 SSOT 走 —— 它被寫死在畫面上了。\n" + _patched)
    assert "≥ 0.55" in _patched, (
        "影子基金卡的門檻文案沒有跟著 SSOT 走 —— 它被寫死在畫面上了。\n" + _patched)


def test_the_eating_card_accounts_for_every_fund_it_looked_at():
    """吃本金說明句**四個成分一個都不能少** —— 沒講出來的，使用者會自己補。

    **這是 2026-09-06 獨立稽核抓到的第三項。** 原本只有「另有 N 檔接近警戒」有守衛
    （`test_a_thin_margin_is_not_reported_as_eating_principal`），另外兩段砍掉都全綠。

    ⚠️ **根因是覆蓋率不是邏輯錯** —— 稽核組用探針量到 `_eating_note()` 被呼叫 16 次、
    **`unknown` 每一次都是 0**：「已判定 ＋ 資料不足」的混合情境**沒有任何 fixture 走到**。
    `MIXED_HOLDINGS` 就是補上那條路的（它自己的註記寫著來歷）。

    ⚠️ 「資料不足」那一段特別要緊：`_eating_verdict` 的 docstring 有一句**承重宣稱** ——
    「例外收成 `_EAT_UNKNOWN` … **且會被計入卡片說明的「N 檔資料不足」**——
    不是靜默吞掉（§1）」。**那句話原本沒有守衛**；本條就是它的守衛。

    ⛔ 卡片上的主數字只有一個（幾檔吃本金），但它背後有四種落點。
       **沒被講出來的那幾種，使用者多半會補成「其餘都健康」** —— 而那正好是最危險的誤讀：
       「資料不足」被讀成「檢查過了，沒事」。
    """
    _seg = _segments(_render(portfolio=MIXED_HOLDINGS))
    _body = "\n".join(_seg.get("吃本金警示", []))
    assert _body, f"吃本金卡不見了。現有單位：{list(_seg)}"
    # 1 檔 eating / 1 檔 healthy / 2 檔 unknown（見 MIXED_HOLDINGS）
    assert "1 檔" in _body, f"主數字（吃本金檔數）不對。\n{_body}"
    assert "1 檔覆蓋充足" in _body, (
        "說明句沒有交代「幾檔是健康的」—— 那一段砍掉不會有任何東西轉紅（實測）。\n" + _body)
    assert "2 檔資料不足" in _body and "未列入判定" in _body, (
        "說明句沒有交代「幾檔根本判不動」——\n"
        "而 `_eating_verdict` 的 docstring 承諾了它會被計入（§1 不得靜默吞掉）。\n" + _body)


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

    ⚠️ **已知漏洞，本批刻意不修（登記後果，不只登記決定）—— 2026-09-06 稽核**：
    本函式的 `_mods` 是**就地寫的**，`ImportFrom` **只吐 `_n.module`**
    （`extend(_a.name …)` 那一支是給 `ast.Import` 用的，`ImportFrom` 走不到）。
    ③④ 已改成「`module` 與 `module.name` 兩個都吐」，**本函式沒有跟上**。
    **實測後果（rc=0，也就是放行）**：

        from ui import tab3_portfolio        → `_mods = ["ui"]`
                                               `"ui".startswith("ui.tab")` 為 False ⇒ **綠**
        from ui.helpers import fund_grp_health → `_mods = ["ui.helpers"]`
                                               `"fund_grp_health" in "ui.helpers"` 為 False ⇒ **綠**

    也就是說**本頁對「同層 import 舊 ②／`fund_grp_health`」是不設防的**。
    ③④ 的 PR 描述寫過「② 沒有 `_imported_modules`，刻意不為此新增」——
    那句只講了**決定**，沒講**後果**；後果就是上面這兩行。
    ⛔ 要修請一併看 ③④ 的 `_imported_modules` 註解裡登記的「回傳 `(module, symbol)`
    讓消費端各自選」那個方向，**不要**只把 `module.name` 加進來就算
    （那會把 ③④ 已量到的 5 個子字串誤紅一起帶進本頁）。
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
