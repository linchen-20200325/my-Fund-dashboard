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
- **繞道維（本檔只解掉「字面」那一半，2026-09-05 紅隊更正）**：② 的「手刻
  `st.markdown("⬜ …")` 不走 `not_ready()` 也照樣被認成灰態」——
  :func:`test_the_page_never_hand_rolls_the_grey_mark` 只擋得住**字面** `⬜`。
  ⛔ **兩種寫法照樣全綠**：(a) 從 SSOT `from ui.helpers.render_state import
  NOT_READY_MARK` 再自己拼成一句 caption；(b) `chr(0x2B1C)`。
  ⚠️ **(a) 特別值得記著：那正是本檔自己在教的寫法**（本檔頂部就寫著
  「從那個模組 import，不在這裡抄一份字面值」）——
  **一個照著檔案自己的教誨寫的人，會剛好落在守衛的盲區裡。**
  （總管 2026-09-05 排程裁決：登記，本批不修。）
- ⛔ **語意維（本檔**沒有**解，而且比本檔原本自陳的更寬）**：所有灰態斷言驗的是
  **符號**（⬜）與**常數**（`_PENDING_NOTE`），**不驗那句話的意思**。
  紅隊實測全綠的三種：句尾接「目前一切正常，無異常」／八個單位的灰態理由**互換**／
  **在灰態裡塞一句投資承諾「目前查無風險，此檔可安心買進。」**
  ⚠️ 第三種是本檔原本沒有想到的等級 —— **一句會讓人賠錢的話，本檔一條都不會響。**
- ⛔ **情境維（本檔只覆蓋到一半）**：頁面只被渲染過 **兩種** session 形狀
  （`None` 與一份 `{"term","source"}`）。`_applied_query()` 對**非 dict 髒值**
  （字串／list／舊版 payload）的行為**沒有任何斷言**。
  `_normalise_query()` 本身有直接測（:func:`test_a_blank_search_never_counts_as_applied`），
  但它與 `_render_search_form()` 之間的接線**只由 AST 驗形狀，沒有跑過**。
- ⛔ **指路挑錯 key 沒有守衛**：`_pending_where()` 若把 `where_to_find('research')`
  換成任何一個**別的合法 key**，:func:`test_every_grey_says_where_to_look` 才會紅；
  但職責宣告那一句裡的 `health` / `portfolio` 兩個 key **換成別的合法 key 不會有任何東西轉紅**。
  **這是「走 SSOT」擋不到的那一類**：SSOT 保證名字不過期，**不保證你挑對了 key**。
- ⛔ **其餘已登記、本批不修**（總管 2026-09-05 排程裁決）：
  示意值黑名單只有 10 個字面寫法；**指路挑錯 key 沒有任何守衛**；
  `_applied_query()` 對非 dict 髒值零斷言；`BLOCK_RESULTS` 可以被改成空字串；
  `getattr(st, "columns")(2)` 與 `from streamlit import columns as _c` 繞得過
  :func:`test_the_page_draws_no_grid_or_form_of_its_own`
  —— **但全域 `tests/test_ui_grid_contract.py` 對 alias 同樣失明，
  那是 repo 既有性質，不是本頁造成的。**

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
import sys
import re
from typing import Any

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "ui" / "views" / "page_03_research.py"

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
from ui.views.page_03_research import (  # noqa: E402
    _LABEL_SOURCE,
    _LABEL_TERM,
    CCY_UNKNOWN,
    SYNTHETIC_TRACE_SOURCES,
    TRACE_NAV_SERIES,
    DIVIDEND_COLS,
    HOLDING_COLS,
    NO_REASON,
    PERF_PERIODS,
    RISK_METRICS,
    TRACE_COLS,
    TRACE_FAIL,
    TRACE_OK,
    BLOCK_BATCH,
    BLOCK_DEEP,
    BLOCK_FORM,
    BLOCK_RESULTS,
    DEEP_DIVE_CARDS,
    DEEP_DIVE_PROVENANCE,
    DEEP_DIVE_TABLES,
    SOURCE_OPTIONS,
    SUBMIT_LABEL,
    _BATCH_PENDING_NOTE,
    _RESULTS_PENDING_NOTE,
    _declared_currency,
    _dividend_rows,
    _holdings_rows,
    _nav_facts,
    _normalise_query,
    _pending_where,
    _failed_source_count,
    _fmt,
    _perf_lines,
    _risk_lines,
    _trace_rows,
    render_fund_research,
)

#: `_render(result=…)` 的「沒有傳」哨兵 —— 不能用 `None`，`None` 是合法的假回傳。
_SENTINEL: Any = object()

# ══════════════════════════════════════════════════════════════════
# 假的 L2 回傳（**唯一的資料入口**，本檔所有深度區斷言都吃它）
#
# ⚠️ **每一個數字都是獨一無二的哨兵**，這是刻意的：
#    「某一格印出了別格的數字」與「某一格印出了 0」都是本檔要抓的失效模式，
#    而它們在**共用同一個數值**的 fixture 底下**完全看不出來**。
# ⚠️ **哨兵值必須避開 `_PINNED_FAKE_VALUES`**（它含裸子字串 `"0.81"` / `"0.22"`）——
#    撞到的話會讓另一條守衛誤紅，而且那個紅燈指的方向是錯的。
# ══════════════════════════════════════════════════════════════════

#: 風險指標的哨兵：`metrics 鍵 -> 值`。刻意**每個都不同、且不含 0.81 / 0.22**。
RISK_SENTINELS: dict = {
    "sharpe": 71.11, "sortino": 72.22, "calmar": 73.33,
    "max_drawdown": -74.44, "std_1y": 75.55,
}
#: 績效的哨兵：`perf 鍵 -> 值`。
PERF_SENTINELS: dict = {
    "1M": 61.11, "3M": 62.22, "6M": 63.33,
    "1Y": 64.44, "3Y": 65.55, "5Y": 66.66,
}


class _FakeSeries:
    """夠用的假 `pd.Series` —— 只實作被測檔真的會碰的那幾個介面。

    ⚠️ **刻意不 import pandas**：本檔要驗的是「UI 怎麼讀資料」，
    不是 pandas 的行為；真的 Series 進來會讓失敗訊息指向 pandas 而不是被測檔。
    """

    def __init__(self, values: list, dates: list, attrs: dict | None = None) -> None:
        self._v, self._d = values, dates
        self.attrs = dict(attrs or {})
        self.index = _FakeIndex(dates)
        self.iloc = _FakeILoc(values)

    def __len__(self) -> int:
        return len(self._v)


class _FakeIndex:
    def __init__(self, dates: list) -> None:
        self._d = dates

    def min(self):
        return min(self._d)

    def max(self):
        return max(self._d)


class _ExplodingIndex:
    """索引**有** `min` / `max`，但一碰就拋 —— 模擬「上游契約破了」。

    ⚠️ **刻意讓方法存在**：獨立稽核有一顆突變因為「`BadIndex` 有 `min` 只是會拋」
    而**其實沒生效**，稽核組自己把它撤回了、不列為證據。
    本類別把那個教訓做成 fixture：要驗「壞索引會不會被吞成灰態」，
    就必須讓它**真的走到 `.min()` 才炸**，不能靠 `hasattr` 早退。
    """

    def min(self):
        raise TypeError("哨兵：索引不是時間軸（上游契約被破壞）")

    def max(self):
        raise TypeError("哨兵：索引不是時間軸（上游契約被破壞）")


def _broken_series(n: int = 3):
    """長度正常、`iloc` 正常，**只有索引會炸**的假序列。"""
    _s = _FakeSeries([1.0] * n, ["2024-01-0%d" % (i + 1) for i in range(n)])
    _s.index = _ExplodingIndex()
    return _s


class _FakeILoc:
    def __init__(self, values: list) -> None:
        self._v = values

    def __getitem__(self, i):
        return self._v[i]


def _BLANK_RESULT() -> dict:
    """**全敗**的回傳：淨值一筆都沒有，只有逐源軌跡。

    形狀照 `repositories/fund/fund_orchestration.py` 與
    `services/fund_service.py::finalize_fund_metrics` 實際會 append 的鍵
    （`{source, success, error}` / `{source, success, nav_count}`）——
    **不是憑印象編的**，見被測檔模組 docstring 的實測段。
    """
    return {
        "status": "failed",
        "fund_code": "ZZTEST",
        "series": None, "perf": {}, "metrics": {}, "holdings": {}, "dividends": [],
        "currency": "",
        "source_trace": [
            {"source": "bank_platform", "success": False, "error": "所有平台均無回應"},
            {"source": "morningstar", "success": False, "error": "查無資料"},
            {"source": "nav_series", "success": False, "error": "無淨值序列"},
        ],
    }


def _RICH_RESULT(**over: Any) -> dict:
    """**六格都有料**的回傳。`over` 用來逐格挖掉東西做突變。"""
    _res: dict = {
        "status": "complete",
        "fund_name": "測試用基金甲",
        "fund_code": "ZZTEST",
        "currency": "USD",
        "nav_span_days": 909,
        "_moneydj_fetched_at": "2026-09-06 07:07:07",
        "series": _FakeSeries(
            [50.01, 50.02, 59.99], ["2024-01-02", "2024-06-03", "2026-09-05"],
            attrs={"source": "FundClear:GetFundNAV",
                   "fetched_at": "2026-09-06T07:00:00+00:00"}),
        "perf": dict(PERF_SENTINELS),
        "perf_source": "wb01",
        "metrics": {
            **RISK_SENTINELS,
            "std_source": "wb07",
            "risk_metric_meta": {
                "sharpe": {"source": "wb07", "self_calc_reason": None},
                "sortino": {"source": "self_calc", "reason": None},
                "calmar": {"source": "self_calc", "reason": None},
                "max_drawdown": {"source": "self_calc", "reason": None},
            },
        },
        "holdings": {
            "data_date": "2026/07",
            "source": "MoneyDJ:yp:yp013001",
            "fetched_at": "2026-09-06T07:00:01+00:00",
            "top_holdings": [
                {"name": "哨兵持股甲", "sector": "科技", "pct": 91.11},
                {"name": "哨兵持股乙", "sector": "金融", "pct": 92.22},
            ],
        },
        "dividends": [
            {"date": "2026/08/15", "ex_date": "2026/08/16", "pay_date": "2026/08/20",
             "amount": 81.11, "yield_pct": 83.33, "currency": "USD"},
            {"date": "2026/07/15", "ex_date": "2026/07/16", "pay_date": "2026/07/20",
             "amount": 82.22, "yield_pct": 84.44, "currency": "USD"},
        ],
        "source_trace": [
            {"source": "fundclear", "success": True, "nav_count": 3},
            {"source": "calc_metrics", "success": True},
        ],
    }
    _res.update(over)
    return _res


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


def _render(applied: dict | None = None, result: Any = _SENTINEL,
            raiser: BaseException | None = None) -> list[str]:
    """跑一次整頁，回傳**有序**的渲染紀錄。

    ⚠️ 回傳 list 而不是一整塊字串 —— 順序本身是本檔要驗的東西之一，
    join 成一坨就驗不了「哪一句落在哪一塊底下」。

    ## ⛔ `auto_fetch_moneydj` **一律被換掉，這不是方便，是必要**

    2026-09-06 深度區接上取數之後，本函式若不換掉它，
    **每一條帶 `applied=` 的測試都會真的連外網**。
    本組實測：第一次跑改動後的測試檔，沙箱的 egress proxy 擋下了
    `fund.api.cnyes.com:443`，整份測試**掛在網路逾時上跑不完**（不是紅，是不會結束）。
    → 一份會連外網的守衛，在 CI 上是**不可重現**的；它紅不紅取決於當天上游活著沒有。

    Parameters
    ----------
    result : 假的 L2 回傳。預設 :data:`_BLANK_RESULT`（全敗），
             因為那才是**大多數既有斷言**在骨架時期看到的處境。
    raiser : 給它一個例外物件 → 假的 `auto_fetch_moneydj` 會 `raise` 它。
             用來驗「真的例外走 `safe_section` 的紅框」那條路徑。
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

    # ⛔ **紅燈也要錄得到，否則「不准紅」那一族斷言是空的。**
    #    `render_state.system_error()` 走 **lazy** `from ui.helpers.session import
    #    friendly_error`，而 `friendly_error` 自己又是**函式內** `import streamlit`
    #    —— 兩層都繞過了上面那份 `_targets` 的 module 層 `st` 替換，
    #    紅框因此打在**真的** streamlit 上（bare 模式無聲）。
    #    本組實測：補這一段之前，`assert "[error]" not in _all` 是
    #    **恆真**的（頁面就算真的塗紅它也看不見）；補了之後
    #    `test_a_real_exception_stays_a_real_exception` 才第一次真的驗到東西。
    #    ⚠️ 這正是本檔 `_render()` 開頭那段「錯的 patch 不會報錯，
    #    只會讓斷言對著半份畫面生效」講的同一個陷阱，換一層發作。
    import ui.helpers.session as _sess          # noqa: PLC0415 — 與 _targets 同理由
    _real_friendly = _sess.friendly_error

    def _fake_friendly(_title, _exc, *, hint: str = "", level: str = "warning"):
        _rec.parts.append(f"[{level}] {_title} — {type(_exc).__name__}: {_exc}")

    _sess.friendly_error = _fake_friendly

    _page = sys.modules["ui.views.page_03_research"]
    _real_fetch = _page.auto_fetch_moneydj
    _payload = _BLANK_RESULT() if result is _SENTINEL else result

    def _fake_fetch(_raw, **_kw):
        _rec.parts.append(f"[fetch] {_raw}")
        if raiser is not None:
            raise raiser
        return _payload

    _page.auto_fetch_moneydj = _fake_fetch
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
        _page.auto_fetch_moneydj = _real_fetch
        _sess.friendly_error = _real_friendly
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


def _metric_open(part: str) -> str | None:
    """**OK 狀態**的卡片開頭 —— `state_card()` 走 `st.metric(title, value)`。

    ⚠️ **這一條是 2026-09-06 深度區接上真資料時補的，沒有它整份斷言會靜靜半盲。**
    在此之前 :func:`_units` 只認得灰態卡的 `**標題**`；卡片一旦有值就改走
    `st.metric`，錄下來長成 `[metric] NAV 走勢 59.99 USD` ——
    **三個 opener regex 沒有一個match得到**，於是那張卡的內容會被歸進**前一個單位**。
    症狀是「斷言全綠、但它驗的是別人的字」，正是本檔 `_units` 長註在講的那個病。

    ⚠️ 為什麼比對**已知標題**而不是用 regex 切第一個詞：recorder 把位置引數用空白
    join 起來（`f"[metric] " + " ".join(bits)`），而標題自己就含空白（「NAV 走勢」）
    —— 從字串上**無法**分辨標題到哪裡結束。已知標題集合是唯一不會猜錯的判準。
    """
    if not part.startswith("[metric] "):
        return None
    _rest = part[len("[metric] "):]
    for _t in DEEP_DIVE_CARDS:
        if _rest == _t or _rest.startswith(_t + " "):
            return _t
    return None


def _units(parts: list[str]) -> list[tuple[str, list[str]]]:
    """把紀錄切成**有序**的最小單位：一級／次級段落，或**一張卡**。

    ⚠️ **粒度是「一張卡」，這是被 ② 的一次突變逼出來的，不是設計出來的。**
    `tests/test_wf02_health_skeleton.py::_units` 記著：初版只依 `#### 區塊名` 切段，
    突變「只拿掉其中一塊的灰態」**沒有轉紅** —— 因為同一段裡別張卡的 ⬜ 替它過關了。
    同一個形狀在 ① 被獨立稽核連續打穿兩輪。**答案每次都一樣：把邊界往下降。**

    ⛔ **不要為了讓斷言好寫而把邊界往上收。** 邊界一寬，鄰居的字就會替你通過。

    ## ⚠️ 這個切法**看不到什麼**（2026-09-06 實測補；不要讀成「整頁都被切進單位裡」）

    **第一個 opener 之前的每一行都會被整段丟掉** —— 本函式只在 `if _out:` 成立時
    才把行歸進單位，而 `_out` 在遇到第一個 opener 之前是空的。
    以本頁**送出查詢後**的實際渲染紀錄實測，落在所有單位之外的有 **6 行**：

    ```
    [markdown] ## 🔍 標的探索          ← 頁標題
    [caption]  回答一個問題：…          ← 職責宣告 ＋「這裡不放什麼」的指路
    [caption]  搜尋條件：輸入完按…      ← Form 的說明
    [text_input] 代碼或名稱             ┐
    [selectbox]  來源                   ├ **整個 Form**
    [form_submit_button] 搜尋           ┘
    ```

    ⚠️ **重點不是「頁首看不到」，是「Form 整塊看不到」** —— 而 Form 正是本頁
    唯一真的做完、也是所有灰態指路都指向的那一塊。
    → 任何**針對 Form 的**斷言都必須走**整頁**紀錄（`_text(_render(...))`）
    或直接呼叫純函式，**不能**用 `_segments()` 去拿它（會拿到空字串而**靜靜通過**）。
    本檔既有的 Form 斷言（`test_the_search_form_is_the_first_thing_on_the_page`
    等）**本來就是走整頁的**，所以現況沒有被打穿；這段是寫給**下一個**要加
    Form 斷言的人看的。
    ⚠️ 同型限制在 ①②④⑤ 四頁的骨架守衛都存在（同一套 `_units` 寫法）。
    """
    _out: list[tuple[str, list[str]]] = []
    for _p in parts:
        _metric = _metric_open(_p)
        if _metric is not None:
            # ⚠️ 有值的卡：`st.metric` 那一行**自己也算內容**（值就印在裡面），
            #    所以開新單位之後要把它放回 body，否則「這一格印了什麼數字」驗不到。
            _out.append((_metric, [_p]))
            continue
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

#: 內容還沒接上的單位 → **它自己那一句**灰態理由。
#: ⚠️ ~~舊版是 `PENDING_UNITS: tuple = (BLOCK_RESULTS, BLOCK_BATCH)`，兩個單位共用~~
#:    ~~一個 `_PENDING_NOTE`。~~ → **2026-09-06 改成 dict（狀態變更，不是漏刪）**：
#:    兩塊「為什麼還沒有」的原因**完全不同**（一個缺搜尋、一個缺輸入欄位），
#:    共用一句就等於對使用者說謊。改成 dict 之後，
#:    :func:`test_every_grey_unit_is_grey_until_its_content_lands` 驗的是
#:    「**這個單位有沒有印它自己那一句**」，而不是「頁面上有沒有出現那句共用的話」。
#: ⚠️ **這個粒度差別是有實據的**：舊寫法只要頁面上任一處印了共用那句就通過，
#:    把兩塊的理由對調**不會轉紅**；改 dict 之後對調就轉紅（突變 P2，見該函式）。
PENDING_NOTES: dict[str, str] = {
    BLOCK_RESULTS: _RESULTS_PENDING_NOTE,
    BLOCK_BATCH: _BATCH_PENDING_NOTE,
}
#: 仍然吃「內容還沒接上」灰態的單位 —— **本批只剩這兩個**。
#: ⚠️ 深度區的六格自 2026-09-06 起**不再**吃那一族：它們的灰態理由來自資料本身。
PENDING_UNITS: tuple[str, ...] = tuple(PENDING_NOTES)

#: 深度區的六個單位（三張卡 ＋ 兩張大表 ＋ 來源標註）。
DEEP_UNITS: tuple[str, ...] = (
    DEEP_DIVE_CARDS + DEEP_DIVE_TABLES + (DEEP_DIVE_PROVENANCE,)
)

#: 取數**全敗**時應該是灰的單位。
#: ⛔ **`DEEP_DIVE_PROVENANCE` 刻意不在其中，這是本批的核心設計不是遺漏**：
#:    全敗正是那一格**最該有內容**的時候 —— 它要把逐源軌跡攤開，
#:    讓使用者自己判斷「代碼打錯」還是「來源當下不可用」（L2 分不出來，見被測檔
#:    `_fetch_failed_note()`）。把它一起要求成灰態，等於要求證據在最需要時消失。
#:    它有沒有真的攤開，由
#:    :func:`test_a_total_failure_shows_the_source_trace_and_never_paints_red` 驗。
GREY_ON_BLANK: tuple[str, ...] = PENDING_UNITS + DEEP_DIVE_CARDS + DEEP_DIVE_TABLES

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
    # ⚠️ **驗 recorder 的精確前綴，不是 substring**（2026-09-05 紅隊實測）：
    #    上一版寫的是 `assert "來源" in _all`，而畫面上**永遠**有一句
    #    `##### 資料來源與抓取時間` —— 「來源」兩個字被那個**完全無關的段落標題**滿足了。
    #    紅隊把整個 `st.selectbox(_LABEL_SOURCE, …)` 刪掉 → **零紅燈**；
    #    對照組刪 `text_input` → 1 failed。**也就是兩個欄位只守住了一個。**
    #    現在比對 `[selectbox] 來源` / `[text_input] 代碼或名稱`，順帶把型別釘住。
    # ⚠️ **釘線框的字面值，不是釘模組常數**（2026-09-05 第二輪突變 M02 抓到）：
    #    上一版寫的是 `f"[{_api}] {_label}"`，而 `_label` 是**從被測模組 import 進來的
    #    同一個常數** —— 於是把 `_LABEL_TERM` 從「代碼或名稱」改成「關鍵字」，
    #    斷言跟著一起變，**35 passed 全綠**。那是一條**自我參照的恆真式**，
    #    它守的是「渲染有沒有用到那個常數」，**不是**「那個常數是不是線框寫的字」。
    #    現在兩件事分開驗：字面值對線框（下方 `==`），渲染有沒有用到它（`in _all`）。
    assert (_LABEL_TERM, _LABEL_SOURCE) == ("代碼或名稱", "來源"), (
        f"欄位標籤被改成 {(_LABEL_TERM, _LABEL_SOURCE)!r} —— "
        "線框 Tab 03 的 Form 逐字寫的是「代碼或名稱」與「來源」。")
    for _api, _label in (("text_input", "代碼或名稱"), ("selectbox", "來源")):
        assert f"[{_api}] {_label}" in _all, (
            f"搜尋條件少了「{_label}」這個 `st.{_api}` —— "
            "線框 Tab 03 的 Form 逐字列了兩個欄位。\n" + _all)
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


def test_the_two_block_names_are_the_wireframe_wording_verbatim():
    """這兩塊的名字**逐字對 `ia-wireframe.html` Tab 03**：單一基金深度／批次分析。

    ## 沿革（這條前後被推翻過一次，寫下來免得後人以為它一直長這樣）

    本檔上一版把這兩個名字**釘成必須走 `story_nav.section_label()`**
    （畫面上是「🔍 單檔深掘」「📦 批次掃描」），理由是當時
    `wireframe-fund-research.html`（2026-08-31）與 `ia-wireframe.html`（2026-09-01）
    **兩份都已客戶拍板、對這一頁的說法不同**，而 `docs/wireframes/README.md`
    的「版本關係」段沒有登記後者覆蓋前者 —— **在裁決之前不自行拍板，那個處置是對的。**

    **2026-09-05 客戶已裁決：③ 以 `ia-wireframe.html` Tab 03 為準。**
    裁決一下來，走 SSOT 就從「保守」變成**開放偏離**，故本條**反過來**釘線框字面。

    ## ⚠️ 「批次分析」帶著一個真的代價，不要以為它是免費的

    「📦 批次分析」是**已退役的頂層分頁名**（`story_nav.RETIRED_TAB_LABELS`），
    而 `tests/test_wpf_five_tab_wiring.py::test_no_live_string_hardcodes_a_tab_name`
    的黑名單**含去 emoji 變體** → 直接寫會**當場轉紅**（紅隊與本組都實測過）。
    故依總管裁決在該守衛的 `_LEGIT_EXEMPT` **具名加了一條**，理由逐字寫在那裡：
    它在這裡是 **③ 頁內的區塊標題**，而批次分析**正是被合併進 ③ 的那個功能**，
    所以不會讓使用者去分頁列上找一個不存在的分頁。
    ⛔ **`RETIRED_TAB_LABELS` 本身與 `_KNOWN_DEBT` 一個字都沒動。**

    ⚠️ 本條與那條豁免是**一組的**：有人把這裡改回 `section_label()`，
    那條豁免就會變成**指不到東西的殭屍條目**（`test_exemption_tables_do_not_rot` 會抓）。
    """
    assert BLOCK_DEEP == "單一基金深度", (
        f"`BLOCK_DEEP` 是 {BLOCK_DEEP!r} —— 客戶 2026-09-05 裁決以 "
        "`ia-wireframe.html` Tab 03 為準，該線框那張卡逐字寫的是「單一基金深度」。")
    assert BLOCK_BATCH == "批次分析", (
        f"`BLOCK_BATCH` 是 {BLOCK_BATCH!r} —— 同上，線框逐字是「批次分析」。")
    _t = _tree()
    _lits = {_n.value for _n in _live_strings(_t)}
    assert {"單一基金深度", "批次分析"} <= _lits, (
        "這兩個名字不是本檔的活字串 —— 裁決後它們必須逐字寫在這裡，"
        "不得再委派給 `section_label()`（那會偏離客戶已裁決的線框）。")


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

    ⚠️ **這裡曾寫「自己寫 `st.columns` 會讓 `GRID_EXEMPT_CALL_TOTAL` 轉紅」——
    那是假的，2026-09-05 由獨立紅隊實測推翻**：加 `st.columns(3)`（＝鐵則 01 叫你開的
    那個）→ **全綠**；`st.columns(2)` → 2 failed。那個計數器抓的是「**欄數不是 3**」
    的呼叫，**合規的 3 欄它一動也不動**。
    ⛔ **所以「本頁不得自己開網格」這條，全域沒有任何一道網子，只有本條在守。**
    （`st.form` 那半仍然成立：`FORM_SITE_TOTAL` 是精確 `==`，多一個站點就紅。）
    ⚠️ 同一份 PR 的模組 docstring（本檔開頭「兩個全域守衛的實測盲點」段）**當時就寫對了**，
    是這裡把假話又抄了一遍 —— **一份在講「文件不該說謊」的守衛，自己的描述必須先為真。**

    ⛔ **本條擋得住的只有 `st.columns` / `st.form` 這兩個 attribute 名。**
    `getattr(st, "columns")(2)` 與 `from streamlit import columns as _c` 都繞得過
    —— **但全域 `tests/test_ui_grid_contract.py` 對 alias 同樣失明，
    那是 repo 既有性質，不是本頁造成的**（總管 2026-09-05 排程裁決：登記，本批不修）。
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

    ⚠️ 比對常數本體，**不硬抄字面值**。硬抄的話，常數一改措辭
    這條就永遠是 True —— 它守的 bug 照樣存在、而它不再看得見。
    ⚠️ **2026-09-06：兩塊的理由拆成兩句之後，兩句都要檢查。**
    只檢查其中一句的話，另一塊漏印進空狀態就看不見了。
    """
    _all = _text(_render(applied=None))
    for _unit, _note in PENDING_NOTES.items():
        assert _note not in _all, (
            f"還沒搜尋時不應同時印出「{_unit}」的「內容還沒接上」灰字 —— "
            "兩個下一步會互相抵消。\n" + _all)


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

    ⚠️ ~~**這條分不出真假閘門**（② 的紅隊實測：`if True:` 與 `if not _gate:` 都全綠）——
    它只驗「session 寫入有沒有被某個 `if` 包住」。**登記，本批不補。**~~
    → **2026-09-05 狀態更新，不是漏刪**：**後半已修** —— 不再是「被某個 `if` 包住」，
    改成「被**閘門那個** `if` 包住」（`gate_ifs()`），所以 `if True:` 那一種**現在會轉紅**
    （它不提到 `_gate` ⇒ 不算閘門 ⇒ 底下的寫入判為裸寫入）。
    **前半仍然成立**：`if not _gate:` 照樣被認成閘門，靜態規則分不出語意反轉。
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
    _t = _tree()
    _fns = {_n.name: _n for _n in ast.walk(_t) if isinstance(_n, ast.FunctionDef)}
    for _need in ("_applied_query", "_normalise_query"):
        assert _need in _fns, (
            f"找不到 `{_need}()` —— 「已送出值」這一層被拿掉了，"
            "下游就會直接讀 widget 值，等於沒有 form。")
    _form_fn = _fns["_render_search_form"]
        # ⚠️ 管道 4（widget `key=`）**必須**收窄成「只認守衛在乎的那個 session key」：
    #    widget 一定建在 `with applied_form(...)` 內，而閘門 `if` 一定在 `with` 外
    #    ⇒ 帶 `key=` 的 widget 結構上永遠不可能落在閘門 body 裡，不收窄就是一條
    #    **永遠無法滿足**的守衛（本 repo `ui/**` 有 231 處 `key=`，量測日 2026-09-05）。
    # ⚠️ **自動收齊模組層所有 `_SK_*`，不要列舉** —— 列舉一定會漏下一個新加的鍵。
    #    上一版只餵 `_SK_APPLIED`，於是 `key=_SK_PORTFOLIO`（使用者的 live 持股）
    #    那顆突變從紅掉成綠（2026-09-06 稽核 M-1，②④ × 三序實測）。
    # ⚠️ **本頁（③）沒有 `_SK_PORTFOLIO`，所以這個改動在本 SHA 是字面上的 no-op**
    #    —— 實測新舊回傳**完全相同的集合** `{_SK_APPLIED, 字面值}`。
    #    本頁的線框明訂「不預設我有持有」，另有一條守衛專門禁 `"portfolio_funds"`
    #    出現在本頁，所以那個常數本來就不該在這裡。
    #    **改成掃前綴的價值在本頁是前瞻的**：日後本頁新增任何 `_SK_*`（實測以
    #    `_SK_DRAFT` 驗過）會自動被守到，不必記得回來改這一行。
    _applied_keys = guarded_key_names(_t)
    _writes = session_writes(_form_fn, widget_key_names=_applied_keys)
    assert _writes, "`_render_search_form()` 沒有把送出結果寫回 session。"
    _gate_ifs = gate_ifs(_form_fn)
    assert _gate_ifs, (
        "`_render_search_form()` 裡找不到 `with applied_form(...) as <gate>:` 綁出來的那個閘門 `if` —— "
        "form 沒有 gate 住任何東西（或閘門換了寫法，請同步 `gate_ifs()` 的判準）。")
    # ⚠️ 只算閘門 `if` 的 **body** —— `else:` / `elif` 是閘門為假才跑的路徑，
    #    整棵 `ast.walk(_g)` 會把它們一起算成 guarded（2026-09-05 實測的洞）。
    _guarded = gate_guarded_ids(_form_fn)
    _naked = [_w for _w in _writes if id(_w) not in _guarded]
    assert not _naked, (
        "有 session 寫入**沒有**被送出閘門包住 —— 那代表每次 rerun 都會覆寫已送出值，\n"
        "使用者打字的當下就會觸發下游重算，form 等於白包。\n  "
        + "\n  ".join(f"第 {_w.lineno} 行：{ast.unparse(_w)[:70]}" for _w in _naked))


# ══════════════════════════════════════════════════════════════════
# 灰態：八個單位各自誠實
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("unit", PENDING_UNITS)
def test_every_grey_unit_is_grey_until_its_content_lands(unit: str):
    """送出搜尋、但內容還沒接上 → 每一個單位**各自**要有灰態記號與理由。

    ⚠️ **斷言的單位是「一段」或「一張卡」，不是整頁，也不是整塊。**
    ② 的初版以「一級區塊」為單位，突變「只拿掉其中一塊的灰態」**沒有轉紅**
    （同一段裡別張卡的 ⬜ 替它通過了）—— 粒度因此下降。詳見 :func:`_units` 的長註。

    ⚠️ ~~**下一批把真內容接上時，這條會轉紅 —— 那是預期的。**~~
    → **2026-09-06 已發生，這是狀態更新不是漏刪**：深度區六格接上真取數之後
    本條對它們**全部轉紅**（它們不再印 `_PENDING_NOTE`）。
    **依它自己寫的處置照做了**：參數化由八個單位收成 :data:`PENDING_UNITS` 兩個，
    深度區改由
    :func:`test_a_deep_unit_that_has_data_shows_it_and_one_that_has_none_stays_grey`
    等條**驗真內容**，**不是**把本條放寬成「有東西就好」。
    """
    _seg = _segments(_render(applied=FAKE_QUERY))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」有標題但沒有任何內容 —— 那是空占位。"
    assert NOT_READY_MARK in _body, (
        f"單位「{unit}」沒有灰態記號 {NOT_READY_MARK!r} —— "
        "內容還沒接上就要誠實留灰，不得空著也不得填示意值（§1）。\n" + _body)
    # ⚠️ 驗的是**這個單位自己那一句**，不是「頁面上有出現某句共用的話」。
    #    後者在兩塊理由對調時不會轉紅（突變 P2 實測）。
    assert PENDING_NOTES[unit] in _body, (
        f"單位「{unit}」的灰態沒說**它自己**「為什麼沒有」。\n" + _body)
    _others = [_n for _u, _n in PENDING_NOTES.items() if _u != unit]
    for _other in _others:
        assert _other not in _body, (
            f"單位「{unit}」印的是**別一塊**的理由 —— 兩塊卡住的原因不同，"
            "串到一起會讓使用者以為它們等的是同一件事。\n" + _body)


def test_the_two_pending_reasons_are_not_the_same_sentence():
    """兩塊灰態的理由**必須不一樣** —— 它們卡住的原因根本不同。

    · 「{results}」卡在**沒有可以列出候選的搜尋**（資料面）；
    · 「{batch}」卡在**沒有可以收多個代碼的輸入欄位**（版面決定，不是資料問題）。

    共用一句「本頁分批上線」會把兩件事說成同一件，使用者無從判斷哪一個跟他有關、
    也無從知道哪一個是他等得到的 —— 那是 §1 的失效模式（**看起來有解釋、實際沒有**）。

    ⚠️ **本條不驗那兩句話的「意思」**（測試沒有判讀語意的能力），只驗三件可驗的事：
    (1) 兩句不相等、(2) 兩句都不是空的、(3) 兩句都沒有退回舊的共用措辭。

    ## 突變實驗（2026-09-06 實跑）

    - **P1** 把 `_BATCH_PENDING_NOTE` 改成 `_RESULTS_PENDING_NOTE`（退回共用一句）
      → **本條轉紅**。
    - **P2** 把兩句**對調**（各自都還在，只是掛錯塊）→ 本條**不會**紅（兩句仍不相等），
      但 :func:`test_every_grey_unit_is_grey_until_its_content_lands` **轉紅** ——
      那條驗的是「這個單位有沒有印**它自己**那一句」。**兩條分工，缺一不可。**
    """
    assert _RESULTS_PENDING_NOTE != _BATCH_PENDING_NOTE, (
        "兩塊灰態共用同一句理由 —— 它們卡住的原因不同（一個缺搜尋、一個缺輸入欄位），"
        "共用一句等於對使用者說謊。")
    for _unit, _note in PENDING_NOTES.items():
        assert _note.strip(), f"單位「{_unit}」的灰態理由是空的。"
        assert "本頁分批上線" not in _note, (
            f"單位「{_unit}」退回了舊的共用措辭「本頁分批上線」—— "
            "那句話講的是**這一頁的進度**，不是**這一塊缺什麼**。")


def test_the_pending_pointer_is_a_place_not_a_status_sentence():
    """`_pending_where()` 回傳的必須是一個**地方**，不是一句狀態陳述。

    ## 這條是本輪突變 **R5** 逼出來的（不是設計出來的）

    2026-09-05 修好 `_pending_where()` 之後，本組把它**退回舊寫法**
    （``f"{where_to_find('research')} → 目前只有「{block}」是完整的"``）再跑一次 ——
    **1014 passed，一條都沒紅。** 也就是說：**修好了渲染，卻沒有任何東西在防它退回去。**
    依「沒突變過的守衛不要宣稱它守得住」，補上本條。

    ## 判準用**結構相等**，不用關鍵字黑名單

    黑名單（「不准出現『完整』兩個字」之類）只擋得住上一次那個寫法，換個措辭就繞過。
    本條直接釘住組成：**分頁路徑 ＋ `→` ＋ 區塊名**，中間不得夾任何述語。
    任何「狀態陳述」都會因為多出述語而不相等。

    ⚠️ 本條驗的是「**它是不是一個地方**」，**不驗「去了有沒有用」** ——
    後者做不到（這一塊沒接上，去任何地方都不會讓它出現），
    已就地寫在被測檔 `_pending_where()` 的 docstring 裡，不在這裡假裝有守。
    """
    for _block in (BLOCK_FORM, "任意區塊名"):
        assert _pending_where(_block) == (
            f"{where_to_find('research')} → {_block}"), (
            f"`_pending_where({_block!r})` ＝ {_pending_where(_block)!r}\n"
            "它會被 `render_state.not_ready()` 包成「（請先到：…）」——"
            "所以它必須是一個**地方**（分頁路徑 → 區塊名），不能是一句狀態陳述。\n"
            "舊寫法「…→ 目前只有「X」是完整的」被包起來之後是一句**不可執行的指令**："
            "使用者照著回到搜尋條件再送一次，8 條灰態逐字完全相同（紅隊實跑）。")
    # 組成之後真的長成祈使句該有的樣子（不是只驗回傳值，也驗它進到畫面上的形狀）。
    _seg = _segments(_render(applied=FAKE_QUERY))
    _body = "\n".join(_seg.get(BLOCK_RESULTS, []))
    assert f"（請先到：{where_to_find('research')} → {BLOCK_FORM}）" in _body, (
        "畫面上那句「請先到：…」不是預期的地方字串。\n" + _body)


@pytest.mark.parametrize("unit", GREY_ON_BLANK)
def test_every_grey_unit_says_where_to_look(unit: str):
    """每一個灰態單位**各自**要有「去哪補」，而且不得手抄分頁名。

    ## ⚠️ 這條原本是**整頁一次性檢查**，2026-09-05 被紅隊打穿

    舊寫法是 ``assert where_to_find("research") in _all`` —— **整頁 containment**，
    任何**一條**帶著指路就過。紅隊拿掉三處 `wide_table(empty_where=)` →
    **本檔 27 passed、全域 1007 passed，一條都沒紅**，而畫面上那三塊
    **真的失去了「（請先到：…）」**。

    兩個原因疊在一起，缺一都不會出事：
      1. 全域網子（`tests/test_batch2_top_card_grid.py::_where_sites`）
         **不收 `wide_table(empty_where=)` 這個形狀** —— 它只收
         `not_ready` / `empty_state` / `state_card` / 卡片 dict 四種；
      2. 本條當時的粒度是整頁。

    → **現在粒度降到與 :func:`test_every_grey_unit_is_grey_until_its_content_lands`
       一致（一段或一張卡）**，拿掉任一個單位的指路都會**單獨**轉紅。

    ⚠️ **這條驗的是「有沒有指路」，不驗「照著做有沒有用」。**
    這一族的指路**有效性有限**，理由就地寫在被測檔的 `_pending_where()` 上：
    這一塊沒接上，去任何地方都不會讓它出現。
    ✅ 真的有效的是**空狀態**那一則（另由
    :func:`test_nothing_below_the_form_renders_before_a_search` 驗）。
    """
    _seg = _segments(_render(applied=FAKE_QUERY))
    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"單位「{unit}」不見了。"
    assert where_to_find("research") in _body, (
        f"單位「{unit}」的灰態沒有「去哪補」—— 指路要走 `where_to_find('research')`，"
        "手抄的分頁名在本 repo 已經指錯三次（見 `story_nav.RETIRED_TAB_LABELS`）。\n"
        + _body)
    # ⚠️ **這一條近乎恆真，失敗訊息 2026-09-06 就地改正**（獨立稽核 登記 3）：
    #    `_body` 是灰態自己的文字，而指路是 `_pending_where(BLOCK_FORM)` 組出來的
    #    → 它**必然**包含 `BLOCK_FORM`。**底層性質成立，但它驗不到「畫面上找得到」**
    #    —— 舊訊息寫「在畫面上找不到」，**宣稱的比它驗到的多**。
    #    真正驗「指路指到的東西存不存在」的規則見 `CLAUDE.md §8.3.P` 的
    #    `P-WHERECONTENT-1`（執行期組出來的指路，靜態規則看不到）。
    assert BLOCK_FORM in _body, (
        f"單位「{unit}」的指路沒有提到「{BLOCK_FORM}」—— "
        "本條只驗**指路字串的組成**（它是否由 `_pending_where(BLOCK_FORM)` 產生），"
        "**不驗**那個名字在畫面上是否真的存在。")


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
            # ⚠️ **兩個都要吐**：只吐 `_n.module` 會漏掉「同層 import」這條最自然的寫法 ——
            #    `import ui.tab3_portfolio`                     -> "ui.tab3_portfolio"  ✅
            #    `from ui.tab3_portfolio import render_...`     -> "ui.tab3_portfolio"  ✅
            #    `from ui import tab3_portfolio`                -> "ui"  🔴 舊寫法靜靜通過
            #    而下面的判準是 `startswith("ui.tab")` ⇒ 第三種完全不會被擋。
            #    「不得委派舊分頁」是客戶方針的唯一機械保證，漏掉這條等於沒守。
            # ⚠️ **代價照實寫（2026-09-06 更正：原本這裡寫「多吐無害」，那是假的）**：
            #    `from services.fund_service import single_fund_metrics` 會多吐
            #    "services.fund_service.single_fund_metrics" 這種**不是模組**的字串。
            #
            #    ~~消費端都是 `startswith` 比對，多吐無害~~
            #    → **四個消費端沒有一個是純 `startswith`**（實測，不是推論）：
            #      兩個是 `_m.split(".")[0] in (...)`（多吐的字串首段與模組相同 ⇒ 無影響），
            #      **另外兩個是 `startswith(...) or <子字串> in _m`** ⇒ **會被符號名誤觸發**。
            #
            #    **已量到的誤紅形狀（三序一致；`180fb93` 上皆為綠 ⇒ 這些偽陽性是
            #    「同時吐兩個」這個改動新引入的）**。
            #    ⚠️ **量測形態要講清楚，否則照抄會得到相反的結論**：下列 import
            #    **是放在一個「函式內、永不被呼叫」的 lazy import 裡量的**
            #    （`def _qa_never_called(): from services.batch import ...`）——
            #    這樣模組載入時不會真的去 import，pytest 回 **rc=1（測試真的紅）**。
            #    **若照抄成模組頂層 import，會得到 rc=4（collection error）**，
            #    那是**壞掉的突變、不是守衛的結果**（2026-09-06 兩種形態各實測一次）。
            #    這五個模組多數**並不存在**（`services/batch.py` 等），
            #    lazy import 不需要它們存在 —— **AST 掃描看的是原始碼，不是能不能 import**。
            #      `from services.fund_service import single_fund_metrics`  → 命中 "single_fund"
            #      `from services.batch import batch_analysis_runner`       → 命中 "batch_analysis"
            #      `from services.research import fund_research_helper`     → 命中 "fund_research"
            #      `from services.perf import portfolio_perf_summary`       → 命中 "portfolio_perf"
            #      `from services.health import fund_grp_health_score`      → 命中 "fund_grp_health"
            #    這些 import **本來就合法**（同檔另一條測試只禁 repositories/infra/網路函式庫，
            #    `services/**` 是允許的），現況只是**還沒有人這樣寫**，屬**潛伏**的誤紅。
            #
            #    ⛔ **不要為了消掉誤紅而把這裡收窄** —— 「兩個都要吐」的理由仍然成立
            #    （`from ui import tab3_portfolio` 是同層 import 最自然的寫法，只吐
            #    `_n.module` 會得到 "ui"、被 `startswith("ui.tab")` 靜靜放過）。
            #    ⚠️ ~~**真要修，該動的是那兩個子字串消費端**（讓它們只看模組清單）~~
            #    → **2026-09-06 更正：這個方向被實測推翻，不要照做**（有意識的更正，不是漏刪）。
            #    「只看模組清單」會**重開剛關掉的洞**：`ui/helpers/fund_research/` 是
            #    **真實存在的套件**，`from ui.helpers import fund_research` 在
            #    只看模組清單時是 `["ui.helpers"]` → **綠（漏放）**；
            #    同時吐兩個才是 `["ui.helpers", "ui.helpers.fund_research"]` → **紅**。
            #    **正確方向：讓 `_imported_modules` 回傳結構化的 `(module, symbol)`，
            #    由消費端各自選比對哪一半** —— 兩邊的分辨能力都保住，也不必碰檔案系統。
            #    超出本批邊界，**已登記待裁決**。
            #    **本函式的回傳值自此不是一份「真的 import 到的模組」清單，不要拿去做別的用途。**
            _mods.append(_n.module)
            _mods.extend(f"{_n.module}.{_a.name}" for _a in _n.names)
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


# ══════════════════════════════════════════════════════════════════
# 深度區：一次取數、六格共用、缺值不生數字
#
# ⚠️ **本節的每一條都寫「機制」，不寫「某一顆突變會紅」。**
#    「拿掉 X 這一行會轉紅」是一次觀察；下一個人換個寫法犯同一個錯，
#    那條斷言照樣綠。所以下面一律**逐指標／逐格參數化**，
#    讓「所有同類的錯」都在射程內，而不是其中一個示範。
# ══════════════════════════════════════════════════════════════════

def test_the_deep_dive_fetches_exactly_once():
    """六格由**一次** L2 呼叫供給 —— AST 數 `auto_fetch_moneydj(...)` 的呼叫點。

    ## 機制（為什麼是「恰好 1 個」而不是「至少 1 個」）

    每多一個呼叫點就是**多一次網路往返**；更糟的是六格會拿到**不同時間點**的快照
    （L1 的 `@_ttl_cache` 只擋重複的 HTTP，`finalize_fund_metrics` 每次都重跑），
    於是畫面上可能出現「NAV 是這一秒的、持股是上一分鐘的」而**沒有任何跡象**。

    ⚠️ **AST 不是 grep**：本檔的 docstring 就寫了好幾次 `auto_fetch_moneydj`
    這個字，字串比對會把它們一起算進去。
    ⛔ 這條看不到的：`getattr(mod, "auto_fetch_moneydj")()` 這種間接呼叫，
    以及**別的模組**替本頁去呼叫（本檔只掃這一個檔案）。**登記，不宣稱涵蓋。**
    """
    _calls = [_n for _n in ast.walk(_tree())
              if isinstance(_n, ast.Call)
              and (getattr(_n.func, "id", None) == "auto_fetch_moneydj"
                   or getattr(_n.func, "attr", None) == "auto_fetch_moneydj")]
    assert len(_calls) == 1, (
        f"本頁對 `auto_fetch_moneydj()` 有 {len(_calls)} 個呼叫點（應為 1）："
        + ", ".join(f"第 {_c.lineno} 行" for _c in _calls)
        + "\n六格共用同一次取數；多一個呼叫點 = 多一次往返 + 六格可能不同步。")
    # 渲染路徑上也真的只呼叫一次（AST 數的是「寫了幾處」，這裡數「跑了幾次」）。
    _fetches = [_p for _p in _render(applied=FAKE_QUERY, result=_RICH_RESULT())
                if _p.startswith("[fetch] ")]
    assert len(_fetches) == 1, (
        f"一次渲染實際呼叫了 {len(_fetches)} 次取數：{_fetches}")


@pytest.mark.parametrize("key,label,unit", RISK_METRICS)
def test_a_missing_risk_metric_never_becomes_a_number(key: str, label: str, unit: str):
    """`metrics[<指標>] is None` → **那個指標不得出現任何數字**，且要說出自己的原因。

    ## 機制（三件事一起驗，缺一都能被繞過）

    1. **它自己的哨兵值不得出現** —— 擋「其實有值卻說沒有」以外的反向錯誤；
    2. **不得出現 `<標籤> <數字>` 的形狀** —— 這才是真正在擋的東西：
       `metrics.get(k) or 0` / `or 0.0` / 沿用上一個指標的值 / 填一個「保守估計」，
       全部會在這個形狀上現形；
    3. **其餘四個指標的哨兵必須還在** —— 擋「乾脆整格不畫」這種假修法
       （把一格藏起來，前兩條都會通過）。

    ⚠️ **逐指標參數化**，不是挑一個示範：`sharpe` 的缺值原因鍵是
    `self_calc_reason`、其餘三個是 `reason`、`std_1y` **在 `risk_metric_meta`
    裡根本沒有條目**（實測，見被測檔模組 docstring 第 4 點）——
    只驗其中一個，另外四條路完全沒有守到。
    """
    _metrics = {**RISK_SENTINELS, key: None,
                "risk_metric_meta": {key: {"reason": f"哨兵原因：{label} 樣本不足"}}}
    _seg = _segments(_render(applied=FAKE_QUERY,
                             result=_RICH_RESULT(metrics=_metrics)))
    _body = "\n".join(_seg.get(DEEP_DIVE_CARDS[2], []))
    assert _body.strip(), f"風險指標那一格不見了（{label}）。"

    _own = f"{RISK_SENTINELS[key]:,.2f}"
    assert _own not in _body, (
        f"`metrics[{key!r}]` 是 None，畫面上卻出現了它的哨兵值 {_own}：\n{_body}")
    _leak = re.search(re.escape(label) + r"\s*[-+]?\d", _body)
    assert _leak is None, (
        f"`{label}` 沒有值，畫面上卻出現「{_leak.group(0)}」——"
        "那是憑空生出來的數字（`or 0` / 沿用別的指標 / 自己估一個）。\n" + _body)
    assert f"哨兵原因：{label}" in _body, (
        f"`{label}` 缺值卻沒有說出**它自己的**原因 —— "
        "八格共用一句話會讓「樣本不足」和「來源掛掉」長得一模一樣。\n" + _body)
    _others = [f"{_v:,.2f}" for _k, _v in RISK_SENTINELS.items() if _k != key]
    _gone = [_o for _o in _others if _o not in _body]
    assert not _gone, (
        f"拿掉 `{key}` 之後，其他指標的值也一起消失了：{_gone} —— "
        "整格藏起來不算誠實降級，那是把有的資料也丟掉。\n" + _body)


@pytest.mark.parametrize("key,label", PERF_PERIODS)
def test_a_missing_performance_period_is_named_not_zeroed(key: str, label: str):
    """某個期別沒有值 → **列出它的名字，不得補一個數字**。

    機制同上一條：`perf.get("3Y") or 0` 會讓「近三年沒資料」變成「近三年 0%」，
    而 0% 是一個**看起來完全合理**的報酬率 —— 使用者不可能看出它是編的（§1）。
    """
    _perf = {**PERF_SENTINELS}
    _perf.pop(key)
    _seg = _segments(_render(applied=FAKE_QUERY, result=_RICH_RESULT(perf=_perf)))
    _body = "\n".join(_seg.get(DEEP_DIVE_CARDS[1], []))
    _own = f"{PERF_SENTINELS[key]:,.2f}"
    assert _own not in _body, f"`perf[{key!r}]` 已拿掉，畫面上卻仍有 {_own}：\n{_body}"
    assert re.search(re.escape(label) + r"\s*[-+]?\d", _body) is None, (
        f"「{label}」沒有值，畫面上卻給了它一個數字：\n{_body}")
    assert label in _body, (
        f"「{label}」缺值時應**列出名字**（讓使用者知道少了哪一段），"
        f"不得整個消失：\n{_body}")


def test_a_total_failure_shows_the_source_trace_and_never_paints_red():
    """取數全敗 → **灰態 ＋ 逐源證據**；畫面上**不得**出現系統紅燈。

    ## 機制（總管 2026-09-06 裁決的可執行版本）

    `auto_fetch_moneydj` 對「代碼打錯」與「來源全掛」**回傳完全一樣的 failed**
    （本組實測：兩者都走同一條 `_attempts` 路徑，`error` 是「查無資料」
    「所有平台均無回應」這種泛稱）。所以：
    - 塗紅 → 對打錯代碼的人謊稱系統故障；
    - 寫「查無此檔」→ 對來源掛掉的人謊稱這檔不存在。
    **兩種都是編的**，因此本條同時釘住「不准紅」與「必須攤開證據」兩半。

    ⚠️ **紅燈的判準是 `state_card(state=STATE_ERROR)` 走的 `system_error()`，
    不是「畫面上有沒有紅色」** —— 顏色驗不到，入口驗得到。
    `system_error` 的第一個 render 是 `friendly_error(level="error")`，
    在 recorder 底下會錄成 `[error] …`。
    """
    _parts = _render(applied=FAKE_QUERY, result=_BLANK_RESULT())
    _all = _text(_parts)
    assert "[error]" not in _all, (
        "取數全敗被畫成了系統紅燈 —— 但 L2 分不出「代碼打錯」與「來源當下不可用」，"
        "塗紅等於對打錯代碼的使用者謊稱系統故障。\n" + _all)
    assert "查無此檔" not in _all, (
        "畫面上宣告了「查無此檔」—— 同一份 failed 也可能只是來源當下不可用，"
        "這句話對後者是假的。")
    # 逐源證據必須真的出現在來源標註那一格
    _seg = _segments(_parts)
    _prov = "\n".join(_seg.get(DEEP_DIVE_PROVENANCE, []))
    _rows = _trace_rows(_BLANK_RESULT())
    assert _rows, "fixture 自己就沒有 source_trace，這條測試會空轉。"
    assert "[dataframe]" in _prov, (
        f"全敗時「{DEEP_DIVE_PROVENANCE}」沒有攤開逐源軌跡 —— "
        "那是使用者唯一能自己判斷「打錯還是掛掉」的依據。\n" + _prov)
    # 三個 grey 卡片必須說出「兩種可能」而不是二選一
    _nav = "\n".join(_seg.get(DEEP_DIVE_CARDS[0], []))
    assert "不是本頁查得到的基金代碼" in _nav and "當下不可用" in _nav, (
        "全敗時的說明沒有同時給出兩種可能 —— 挑一種講就是編的。\n" + _nav)
    # ⚠️ 2026-09-06 獨立稽核 應修 1：**不得把責任推給使用者**。
    #    舊文案「可能是代碼打錯」對一個打對了 secId 的人是假的 ——
    #    不能用的是本頁自己宣告的輸入格式，不是他的手指。
    assert "打錯" not in _all, (
        "失敗文案把責任推給使用者（「打錯」）—— 但 secId 與名稱查不到是"
        "**本頁自己的限制**，help 已據實改口，這裡不得再指著使用者。\n" + _all)


def test_a_real_exception_stays_a_real_exception():
    """取數**真的拋例外** → 走 `safe_section()` 的紅框；**不得**被降級成灰態。

    ## 機制

    `auto_fetch_moneydj` 的 **URL 直傳分支沒有 try/except**（本組實測：patch 掉
    下游使其拋 `RuntimeError`，URL 分支原封拋出、純代碼分支才回 `{'error': …}`）。
    那條路徑是**真的系統故障**，必須紅。

    ⛔ 反向也要擋（下一條）：**不得為了塗紅而自己造一個例外**。
    """
    _all = _text(_render(applied=FAKE_QUERY,
                         raiser=RuntimeError("哨兵：上游炸了")))
    assert "[error]" in _all, (
        "取數拋出的真例外沒有被畫成紅燈 —— 它被吞了或被降級成灰態（§1）。\n" + _all)
    assert BLOCK_DEEP in _all, (
        f"紅框沒有標明是「{BLOCK_DEEP}」出事，使用者不知道哪一塊壞了。\n" + _all)
    # 其餘區塊照常渲染（區塊級隔離，不是整頁陪葬）
    assert BLOCK_BATCH in _all, "深度區炸掉不該帶走批次分析那一塊。"


def test_the_page_never_fabricates_an_exception_to_paint_red():
    """⛔ 本頁**不得**自己 `raise` 一個由 `result["error"]` / 字串組出來的例外。

    ## 機制

    `state_card(state=STATE_ERROR)` 對非 `BaseException` 直接 `TypeError`，
    所以「想塗紅」最順手的寫法就是 `raise Exception(result["error"])` ——
    那是**捏造的故障**：手上根本沒有例外，只有一句上游的錯誤字串。

    本條掃所有 `raise`：**只准 raise 型別錯誤這種「契約被破壞」的真斷言**，
    不准把 `result[...]` / `.get(...)` 的內容包成例外丟出去。
    """
    _bad: list[str] = []
    for _n in ast.walk(_tree()):
        if not isinstance(_n, ast.Raise) or _n.exc is None:
            continue
        _txt = ast.unparse(_n)
        if "error" in _txt or "source_trace" in _txt:
            _bad.append(f"第 {_n.lineno} 行 {_txt[:90]}")
    assert not _bad, (
        "本頁把上游的錯誤字串包成例外丟出去，好讓它被畫成紅框：\n  "
        + "\n  ".join(_bad)
        + "\n手上沒有例外就不是系統故障 —— 那一格該是灰的，技術細節交給"
          " `safe_section()` 去接真的例外。")


def test_a_grey_reason_is_never_an_exception_object():
    """⛔ `result["error"]` 不得出現在畫面上的任何一個字裡。

    ## ⚠️ 本條原本是**純 AST**，突變實測後改寫 —— 記下來免得有人改回去

    初版只掃 `not_ready(...)` / `empty_state(...)` 的**直接呼叫引數**。
    突變 **M9**（把 `result["error"]` 當成卡片 `note` 傳給 `_risk_card()`，
    再由 `state_card()` 轉交 `not_ready()`）→ **全綠**。
    也就是說：它擋得住最笨的那個寫法，擋不住本檔**實際在用**的那個寫法
    （卡片一律走 dict → `render_cards()` → `state_card()`）。
    **拔不紅的守衛是裝飾品**，故改為「**執行期哨兵**：把 `error` 換成一個
    絕不會自然出現的字串，然後要求它在整份渲染紀錄裡一次都不出現」——
    這樣**不管經過幾層轉交**都攔得到。

    ## 兩個獨立的理由，都不是理論

    1. **型別**：`not_ready()` / `empty_state()` 對 `BaseException` **直接 `TypeError`**
       （就地防呆），所以這種寫法在 production 是一顆會炸的地雷。
    2. **版面注入**：`empty_state()` 的 `title` 走 **`unsafe_allow_html=True`**
       （實測其實作）。上游是 HTML 爬蟲，`error` 可能含 `<` `>`。

    ## 這條**允許**什麼（分清楚，否則會被讀成「所有上游文字都不准顯示」）

    `source_trace[i]["error"]`（逐源診斷，如「查無資料」）**照樣要顯示** ——
    那是使用者判斷「代碼打錯 vs 來源掛掉」的唯一依據，而且它走
    `st.caption` / `st.dataframe`（兩者都不開 `unsafe_allow_html`）。
    本條釘的是**頂層那個 `result["error"]`**，它可能是 `f"{type(e).__name__}: {e}"`
    這種原始例外字面（見 `services/moneydj_fetcher.py` 的 `_attempts` 分支）。
    """
    _poison = "<b>哨兵毒藥XYZ</b>"
    for _base in (_BLANK_RESULT(), _RICH_RESULT()):
        _base["error"] = _poison
        _all = _text(_render(applied=FAKE_QUERY, result=_base))
        assert _poison not in _all, (
            f'`result["error"]` 的內容被畫到畫面上了（狀態={_base.get("status")!r}）：\n'
            + _all)
        assert "哨兵毒藥XYZ" not in _all, (
            "錯誤字串經過改寫後仍然流到畫面上 —— 逃逸的是內容不是標籤。")

    # AST 那一半保留：直接呼叫的寫法要在**讀 code 時**就看得出來，
    # 不必等到有人跑測試（兩層一起才叫縱深，不是重複）。
    _bad: list[str] = []
    for _n in ast.walk(_tree()):
        if not (isinstance(_n, ast.Call)
                and getattr(_n.func, "id", None) in ("not_ready", "empty_state")):
            continue
        for _a in list(_n.args) + [_k.value for _k in _n.keywords]:
            _txt = ast.unparse(_a)
            if ("error" in _txt or "exc" in _txt) and "empty_" not in _txt:
                _bad.append(f"第 {_n.lineno} 行 {ast.unparse(_n.func)}(… {_txt[:60]} …)")
    assert not _bad, (
        "灰態的文案吃到了錯誤字串 / 例外物件：\n  " + "\n  ".join(_bad))


def test_the_empty_state_title_never_carries_upstream_text():
    """⛔ `empty_state()` 的**標題**只准是本檔自己的字面值。

    ## 機制（這一條與上一條守的不是同一件事）

    上一條守「錯誤字串不要外流」；本條守的是**注入面本身**：
    `empty_state()` 的 title 是本頁唯一走 **`unsafe_allow_html=True`** 的參數
    （實測 `ui/helpers/ia/empty_state.py`）。**只要那個位置永遠是常數，
    這個注入面就結構性地不存在** —— 不必逐一去猜哪個上游欄位可能含 `<`。

    ⚠️ `wide_table(empty_title=…)` 也算，它會原封轉交給 `empty_state()`。
    ⚠️ 允許 f-string，但**內插的每一段都必須是本檔的模組層常數**
    （`DEEP_DIVE_TABLES[0]` 這種），不得是 `result` / 參數 / 區域變數。
    """
    _allowed = {"DEEP_DIVE_CARDS", "DEEP_DIVE_TABLES", "DEEP_DIVE_PROVENANCE",
                "BLOCK_RESULTS", "BLOCK_DEEP", "BLOCK_BATCH", "BLOCK_FORM"}
    _bad: list[str] = []
    for _n in ast.walk(_tree()):
        if not isinstance(_n, ast.Call):
            continue
        _fn = getattr(_n.func, "id", None)
        if _fn not in ("empty_state", "wide_table"):
            continue
        _title = None
        if _fn == "empty_state" and _n.args:
            _title = _n.args[0]
        for _k in _n.keywords:
            if _k.arg in ("title", "empty_title"):
                _title = _k.value
        if _title is None:
            continue
        for _sub in ast.walk(_title):
            if isinstance(_sub, ast.Name) and _sub.id not in _allowed:
                _bad.append(f"第 {_n.lineno} 行 {_fn}(…) 標題內插了 `{_sub.id}`")
            if isinstance(_sub, ast.Attribute):
                _bad.append(f"第 {_n.lineno} 行 {_fn}(…) 標題內插了 "
                            f"`{ast.unparse(_sub)[:40]}`")
    assert not _bad, (
        "空狀態標題吃到了非常數的東西：\n  " + "\n  ".join(_bad)
        + "\n那個位置走 `unsafe_allow_html=True`，上游是 HTML 爬蟲 —— "
          "任何含 `<` 的字串都會直接打壞版面，而且畫面上沒有任何跡象。")


def test_the_page_has_no_exception_handler_of_its_own():
    """本頁**只准**有一個 `except`，而且它不准印任何東西。

    ## 為什麼是「幾乎不准有」而不是「不准吞」

    區塊級隔離已經由 `safe_section()` 提供（它走 `system_error()` ＋ traceback）。
    本頁自己再接一層，只會有兩種結果：**吞掉**（違 §1），
    或**用錯顏色重印一次**（踩 `tests/test_render_state_color_separation.py`
    的方向 A ratchet —— 那條規則掃 `ui/**` 全部，本檔在射程內）。

    ⚠️ **本條的門檻 2026-09-06 由「≤1」收成「0」**（本組自己拆掉了那一個）：
    初稿在 `_nav_facts()` 有一個 `except`，把「序列的索引讀不出來」收斂成
    `return None` → 呼叫端走灰態、文案是「這次沒有帶回淨值序列」——
    **但序列帶回來了，只是讀不出來，那句話是假的。**
    索引不是時間軸 ＝ 上游契約被破壞（`CLAUDE.md §3.1`），§1 要求炸掉。
    **一個 `except` 都沒有，這條規則才不必再判斷「這個 handler 乖不乖」。**
    """
    _handlers = [_n for _n in ast.walk(_tree()) if isinstance(_n, ast.ExceptHandler)]
    assert not _handlers, (
        f"本頁有 {len(_handlers)} 個 except（應為 0） —— 區塊級隔離已由 `safe_section()` 提供，"
        "自己再接一層不是吞掉就是用錯顏色重印一次。\n  "
        + "\n  ".join(f"第 {_h.lineno} 行" for _h in _handlers))
    for _h in _handlers:
        _printed = [ast.unparse(_c)[:60] for _c in ast.walk(_h)
                    if isinstance(_c, ast.Call)
                    and (getattr(_c.func, "attr", None) or "") in _TEXT_APIS]
        assert not _printed, (
            f"第 {_h.lineno} 行的 except 裡印了東西：{_printed} —— "
            "在 handler 裡印例外是「把系統故障畫成別的顏色」，"
            "而且會撞上 `test_render_state_color_separation.py` 的方向 A ratchet。")


@pytest.mark.parametrize("unit", DEEP_UNITS)
def test_a_deep_unit_that_has_data_shows_it_and_one_that_has_none_stays_grey(unit: str):
    """**逐格**：有料就把料畫出來、沒料就灰 —— 兩個方向同時驗。

    ⚠️ 這條取代了骨架時期
    :func:`test_every_grey_unit_is_grey_until_its_content_lands` 對深度區那六格的涵蓋。
    **它不是「有東西就好」**：正向要求那一格**真的出現自己的哨兵字**，
    反向要求全敗時它**不得**印出任何哨兵字。
    """
    _need = {
        DEEP_DIVE_CARDS[0]: "59.99",                    # 最新淨值
        DEEP_DIVE_CARDS[1]: f"{PERF_SENTINELS['1Y']:,.2f}",
        DEEP_DIVE_CARDS[2]: f"{RISK_SENTINELS['sharpe']:,.2f}",
        DEEP_DIVE_TABLES[0]: "[dataframe]",
        DEEP_DIVE_TABLES[1]: "[dataframe]",
        DEEP_DIVE_PROVENANCE: "[dataframe]",
    }[unit]
    _rich = _segments(_render(applied=FAKE_QUERY, result=_RICH_RESULT()))
    _body = "\n".join(_rich.get(unit, []))
    assert _body.strip(), f"有料的時候「{unit}」這一格不見了。現有單位：{list(_rich)}"
    assert _need in _body, (
        f"「{unit}」有資料卻沒有把它畫出來（找不到 {_need!r}）：\n{_body}")

    _blank = _segments(_render(applied=FAKE_QUERY, result=_BLANK_RESULT()))
    _bbody = "\n".join(_blank.get(unit, []))
    assert _bbody.strip(), f"沒料的時候「{unit}」這一格整個消失了 —— 應該留灰態。"
    if unit != DEEP_DIVE_PROVENANCE:      # 來源標註在全敗時要攤開證據，見 GREY_ON_BLANK
        assert NOT_READY_MARK in _bbody, (
            f"「{unit}」沒料卻不是灰的：\n{_bbody}")
        assert _need not in _bbody, (
            f"「{unit}」沒料卻印出了 {_need!r} —— 那是憑空生出來的：\n{_bbody}")


def test_the_page_only_talks_to_the_service_layer():
    """本頁的 import 清單：**不得**碰資料層 / 網路函式庫，也不得委派舊三頁。

    ⚠️ **AST 掃 import 節點，不是字串 grep** —— 本檔與被測檔的 docstring 都反覆
    提到 `repositories.fund.tdcc_search_fund`、`fund_research`、`single_fund`
    這些名字（那是在說明「為什麼不能用」），grep 會把說明文字當成違規。
    ⚠️ 本條與既有的
    :func:`test_the_page_never_reaches_into_the_data_layer` /
    :func:`test_the_page_does_not_delegate_to_the_old_tabs` **是同一組規則的合驗**，
    多一條的價值在於：它同時釘住「**該有的那一個** L2 入口真的在」——
    只有反向禁令的話，把整段取數刪掉也會全綠。
    """
    _mods = _imported_modules(_tree())
    _bad_layer = [_m for _m in _mods
                  if _m.split(".")[0] in ("repositories", "infra", "requests",
                                          "httpx", "yfinance", "gspread",
                                          "urllib", "bs4", "feedparser")]
    assert not _bad_layer, f"本頁 import 了資料層 / 網路函式庫：{_bad_layer}"
    _bad_old = [_m for _m in _mods
                if _m.startswith("ui.tab") or "fund_research" in _m
                or "batch_analysis" in _m or "single_fund" in _m]
    assert not _bad_old, f"本頁委派了舊 ③ 的來源分頁：{_bad_old}"
    assert "services.moneydj_fetcher" in _mods, (
        "本頁沒有 import L2 取數入口 —— 只有反向禁令的話，"
        "把整段取數刪掉也會全綠，那是一份守不到東西的規則。")


def test_the_dividend_currency_is_reconciled_not_guessed():
    """配息幣別：**逐列一致才敢宣告**，不一致就明說不知道，**絕不挑一個**。

    委派 `shared.data_quality.reconcile_row_currencies`（本組實測
    `['TWD','USD'] → ''`、`['USD','USD'] → 'USD'`）。
    ⚠️ 這一格是**線框第三張示意卡在示範的處境**（「幣別未知／此來源未提供計價幣別」
    ＋ chip「不猜值」），所以它不是邊角，是線框點名要做對的地方。
    """
    _mixed = _RICH_RESULT()
    _mixed["dividends"][0]["currency"] = "TWD"          # 兩列幣別不一致
    _seg = _segments(_render(applied=FAKE_QUERY, result=_mixed))
    _body = "\n".join(_seg.get(DEEP_DIVE_TABLES[1], []))
    assert CCY_UNKNOWN in _body, (
        "逐列幣別不一致，畫面卻沒有標示幣別無法宣告：\n" + _body)
    # 純函式層再驗一次（渲染層可能被別的字串蒙混過去）
    assert _declared_currency(_dividend_rows(_mixed)) == "", (
        "`_declared_currency()` 對混幣別的配息挑了一個幣別出來 —— "
        "那正是 `reconcile_row_currencies` 的 docstring 明禁的事。")
    assert _declared_currency(_dividend_rows(_RICH_RESULT())) == "USD", (
        "逐列一致時反而不敢宣告幣別 —— 那會讓「不知道」與「知道」長得一樣。")


def test_missing_upstream_reason_is_admitted_not_invented():
    """上游**沒有**給缺值原因時，畫面要說「上游沒給」，**不准自己編一個**。

    ⚠️ 這條擋的是最容易被當成「貼心」的退化：缺 `reason` 就補一句
    「資料不足」——那是**我們猜的**，而使用者無從分辨它是上游說的還是我們編的。
    """
    _metrics = {_k: None for _k in RISK_SENTINELS}       # 五個全缺、且沒有任何 meta

    # (a) 純函式層：**每一個**缺值指標都要據實承認「上游沒給原因」。
    #     ⚠️ 這一半是本條真正在守的東西 —— 渲染層看不到它
    #     （`_risk_card()` 會在「每一條原因都是 NO_REASON」時改用區塊層級的
    #      處境描述，那是刻意的，見該函式）。只驗渲染層等於沒驗到這條規則。
    _shown, _missing = _risk_lines({"metrics": _metrics})
    assert not _shown, f"五個指標都是 None，卻有東西被當成有值：{_shown}"
    _invented = [_m for _m in _missing if not _m.endswith(NO_REASON)]
    assert not _invented, (
        "上游沒有給缺值原因，本頁卻自己編了一個：\n  " + "\n  ".join(_invented)
        + f"\n沒有原因就據實寫 {NO_REASON!r} —— 使用者無從分辨"
          "「上游說的」與「我們猜的」，猜的那一種比沒有更危險（§1）。")
    assert len(_missing) == len(RISK_METRICS), (
        f"缺值清單少了指標：{_missing} —— 缺一個就整個不提，等於靜默丟掉。")

    # (b) 渲染層：不得因此生出任何數字。
    _seg = _segments(_render(applied=FAKE_QUERY,
                             result=_RICH_RESULT(metrics=_metrics)))
    _body = "\n".join(_seg.get(DEEP_DIVE_CARDS[2], []))
    assert NOT_READY_MARK in _body, "五個指標全缺卻不是灰態：\n" + _body
    for _key, _label, _unit in RISK_METRICS:
        assert re.search(re.escape(_label) + r"\s*[-+]?\d", _body) is None, (
            f"「{_label}」沒有值，畫面上卻出現了數字：\n{_body}")


@pytest.mark.parametrize("unit,ccy_field", [
    (DEEP_DIVE_CARDS[0], "currency"),        # NAV 卡：`result["currency"]`
    (DEEP_DIVE_TABLES[1], "dividends"),      # 配息表：逐列 `currency`
])
def test_an_unknown_currency_is_declared_unknown_not_filled_in(unit: str, ccy_field: str):
    """幣別取不到 → **明說不知道**，不得填一個 ISO 三碼上去。

    ## 這條是突變 **M18** 逼出來的，不是設計出來的

    上一輪把 `nav["currency"] or CCY_UNKNOWN` 改成 `nav["currency"] or "USD"`
    → **全套 55 條一條都沒紅**。也就是說：本檔當時**只守了配息那一格的幣別**
    （`test_the_dividend_currency_is_reconciled_not_guessed`），
    NAV 卡那一格的幣別**完全沒有守**，而它就印在最顯眼的位置（`st.metric` 的值旁邊）。

    ⚠️ **`"USD"` 是本 repo 反覆出現的死預設**（`repositories/fund/` 至少三處
    `.get("計價幣別", "USD")` / `result.get("currency", "USD")`，L1 自己的註解就寫著
    「v19.505:不矇 USD」是為了修這個病）。所以這不是假想的突變 ——
    **它是這份 codebase 已經犯過的那一種錯**，只是換到 UI 層再犯一次。

    ⚠️ 一個台幣基金被標成 USD，使用者看到的是「淨值 59.99 美元」——
    數字是真的、單位是編的，而畫面上沒有任何跡象（`CLAUDE.md §4.1` 量綱陷阱）。
    """
    _res = _RICH_RESULT()
    if ccy_field == "currency":
        _res["currency"] = ""                      # 上游沒給計價幣別
    else:
        for _d in _res["dividends"]:
            _d["currency"] = ""
    _body = "\n".join(_segments(_render(applied=FAKE_QUERY, result=_res)).get(unit, []))
    assert _body.strip(), f"「{unit}」這一格不見了。"
    assert CCY_UNKNOWN in _body, (
        f"「{unit}」的幣別取不到，畫面卻沒有標示 {CCY_UNKNOWN!r}：\n{_body}")
    for _iso in ("USD", "TWD", "EUR", "JPY", "AUD"):
        assert _iso not in _body, (
            f"「{unit}」的幣別取不到，畫面上卻出現了 {_iso!r} —— "
            "那是憑空填上去的計價幣別。數字是真的、單位是編的，"
            "使用者看不出任何異狀（§4.1 量綱陷阱）。\n" + _body)


def test_holdings_keep_the_upstream_ranking_and_do_not_drop_weightless_rows():
    """持股表：**沒有權重照樣列、沒有名稱才跳過，而且排名用上游的原始位置**。

    ## 三個失效模式，一條各守一個

    1. **過濾掉沒有權重的持股** → 「前十大」悄悄變成「我算得出權重的那幾大」，
       使用者看到的排名不再是上游給的排名。
    2. **跳過之後重新編號** → 「上游第 2 檔沒有名字」這件事被抹掉，
       畫面上是一份看起來完整、實際上少一檔的前 N 大（§1：比缺資料更危險）。
    3. **權重缺值補 0** → 「沒揭露權重」與「權重是 0%」長得一樣。
    """
    _res = _RICH_RESULT()
    _res["holdings"]["top_holdings"] = [
        {"name": "哨兵持股甲", "sector": "科技", "pct": 91.11},
        {"name": "", "sector": "金融", "pct": 92.22},          # 無名 → 應跳過
        {"name": "哨兵持股丙", "sector": "能源", "pct": None},  # 無權重 → 應保留
    ]
    _rows = _holdings_rows(_res)
    _names = [_r[HOLDING_COLS[1]] for _r in _rows]
    assert _names == ["哨兵持股甲", "哨兵持股丙"], (
        f"無名列沒被跳過，或有權重的列被丟掉了：{_names}")
    assert [_r[HOLDING_COLS[0]] for _r in _rows] == [1, 3], (
        "排名被重新編號了 —— 上游第 2 檔沒有名字這件事因此被抹掉，"
        "畫面上會是一份看起來完整、實際上少一檔的前 N 大。"
        f"實際排名：{[_r[HOLDING_COLS[0]] for _r in _rows]}")
    _weightless = [_r for _r in _rows if _r[HOLDING_COLS[1]] == "哨兵持股丙"][0]
    assert _weightless[HOLDING_COLS[3]] == "", (
        f"沒有權重的持股被補了一個值 {_weightless[HOLDING_COLS[3]]!r} —— "
        "「沒揭露」與「是 0%」不是同一件事（§1）。")


# ══════════════════════════════════════════════════════════════════
# 2026-09-06 獨立稽核回修 —— 三項必修 ＋ 兩項應修
#
# ⚠️ **通則（本節存在的理由，比任何一條斷言重要）**：
#    **修完一個 bug，第一顆該試的突變就是「把那個修復拔掉」。**
#    上一輪的 24 顆突變對它們自己為真，但**沒有一顆是「拔掉我剛修好的東西」** ——
#    於是 `_has_anything()` 這個 fix（它的 docstring 自己寫「存在的唯一理由是
#    不要讓一句話跑到不屬於它的格子裡」）**零守衛**，稽核組三顆突變全部存活。
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("hollow,unit,keep", [
    # (把哪一格挖空, 該格單位名, 其餘哪一格必須仍有料 —— 證明「有料」這個前提成立)
    ("dividends", DEEP_DIVE_TABLES[1], DEEP_DIVE_CARDS[0]),
    ("holdings", DEEP_DIVE_TABLES[0], DEEP_DIVE_CARDS[0]),
    ("perf", DEEP_DIVE_CARDS[1], DEEP_DIVE_CARDS[0]),
    ("metrics", DEEP_DIVE_CARDS[2], DEEP_DIVE_CARDS[0]),
])
def test_the_all_sources_failed_note_never_leaks_into_a_unit_whose_neighbours_have_data(
        hollow: str, unit: str, keep: str):
    """⛔ 只有**一格都沒有**時才准講「N 個來源都沒有取到淨值」。

    ## 這條守的是 `_has_anything()`，而它上一輪**零守衛**（獨立稽核 必修 1）

    稽核組三顆突變**全部存活 58/58 × 3 序**：配息格 `empty_missing` 退回共用文案、
    持股格同樣退回、以及 **`_has_anything()` 整個改成 `return False`**
    （＝本組初稿的 bug 完整復辟）。

    **失效模式長這樣**（稽核組實測的畫面）：淨值 3 筆、績效有、持股有、**就是沒配息**
    → 配息格印出「這次取數沒有帶回任何淨值」，
    **而同一個畫面上 NAV 卡正印著「59.99 USD · 3 筆」**。
    兩句都是本頁印的，其中一句是假的。

    ## 判準：**指名道姓**，不是「有沒有灰態」

    只驗「這一格是灰的」擋不住任何東西（兩種文案都是灰的）。
    本條驗的是**那一格說的理由對不對** —— 全敗文案的特徵句不得出現在
    「鄰居有料」的畫面上，而且該格必須換上**它自己**的理由。
    """
    _res = _RICH_RESULT()
    _res[hollow] = {} if hollow in ("holdings", "perf", "metrics") else []
    _seg = _segments(_render(applied=FAKE_QUERY, result=_res))

    # 前提：鄰居真的有料（否則這條測試會空轉，稽核組要求的「排除突變沒生效」）
    _keep_body = "\n".join(_seg.get(keep, []))
    assert "59.99" in _keep_body, (
        f"前提不成立：挖空 {hollow!r} 之後鄰居「{keep}」也沒有料了，"
        f"本條會空轉。\n{_keep_body}")

    _body = "\n".join(_seg.get(unit, []))
    assert _body.strip(), f"挖空 {hollow!r} 之後「{unit}」整格消失了。"
    assert NOT_READY_MARK in _body, f"「{unit}」沒料卻不是灰的：\n{_body}"
    for _leak in ("都沒有取到淨值", "沒有帶回任何淨值"):
        assert _leak not in _body, (
            f"「{unit}」沒料，卻印出了**全敗**才該講的話（{_leak!r}）——\n"
            f"但同一個畫面上「{keep}」正印著淨值。**那句話是假的。**\n"
            f"共用文案只准在「一格都沒有」時使用（見 `_has_anything()`）。\n{_body}")


def test_the_dividend_currency_never_contradicts_the_fund_currency():
    """⛔ 配息幣別與基金計價幣別不一致時，**不得宣告任何一個**（獨立稽核 必修 2）。

    ## 這是活的缺陷，不是突變 —— HEAD 未突變時就會發生

    稽核組實測畫面：

    ```
    NAV 走勢     [metric]  59.99 TWD
    配息紀錄     [caption] 2 筆 · 全部以 USD 計價
    ```

    成因在上游、**但本頁是第一個把它端上畫面的**：`_src_fundclear_div` 缺欄時
    逐列填 `"USD"` 死預設，而 `_ensure_currency` 已經為了同一個死預設修好了
    `result["currency"]` —— **只修了一半，本頁端出沒修的那一半，還加了一句
    斬釘截鐵的「全部以 USD 計價」。數字真、單位編（§4.1）。**

    ⛔ **答案不是「相信 `result` 那一邊」**：它只是**比較可信**，不是**確定對**。
    §1 的答案是**不宣稱**。
    """
    _res = _RICH_RESULT()
    _res["currency"] = "TWD"                     # 基金計價幣別（已被 _ensure_currency 修正）
    for _d in _res["dividends"]:
        _d["currency"] = "USD"                   # 逐列死預設
    _all = _text(_render(applied=FAKE_QUERY, result=_res))
    assert "全部以 USD 計價" not in _all and "全部以 TWD 計價" not in _all, (
        "兩邊幣別不一致，本頁卻還是挑了一個宣告：\n" + _all)
    assert "資料疑義" in _all, (
        "幣別矛盾沒有被標成資料疑義 —— 使用者看不出這一頁自己在打架。\n" + _all)

    # 反向：兩邊一致時**要**敢宣告（否則「不知道」與「知道」又長得一樣了）
    _ok = _RICH_RESULT()                          # currency=USD、逐列 USD
    assert "全部以 USD 計價" in _text(_render(applied=FAKE_QUERY, result=_ok)), (
        "兩邊都說 USD，本頁卻不敢宣告 —— 那會讓「不知道」與「知道」長得一樣。")


def test_a_broken_series_index_is_red_not_grey():
    """壞掉的索引 ＝ 上游契約破了 → **紅框**，不得被吞成灰態（獨立稽核 必修 3）。

    ## 為什麼純 AST 的「0 個 except」不夠

    稽核組用 `contextlib.suppress` 把本組**自陳拆掉**的那個「會說謊的 except」
    **原樣復辟**：零 `except` 節點、**58 passed × 3 序**。畫面：

    ```
    HEAD → NAV 格空，紅框 + traceback                     ← 正確（§1）
    突變 → ⬜ 這次沒有帶回淨值序列，上游也沒有說明原因      ← 序列明明帶回來了，3 筆
    ```

    **形狀檢查擋不住換一個形狀。** 本條改驗**行為**；
    純 AST 那條（`test_the_page_has_no_exception_handler_of_its_own`）
    **留著當第二層**，不是被取代。

    ⚠️ fixture 刻意讓 `min` / `max` **存在但會拋**（見 :class:`_ExplodingIndex`）——
    稽核組有一顆突變就是因為「方法存在、只是會拋」而其實沒生效，它自己撤回了。
    """
    _res = _RICH_RESULT(series=_broken_series())
    _all = _text(_render(applied=FAKE_QUERY, result=_res))
    assert "[error]" in _all, (
        "索引壞掉（上游契約被破壞）被畫成灰態或被吞掉了 —— "
        "序列**有**帶回來，只是讀不出來，說「沒有帶回序列」是假的（§1 要求炸掉）。\n"
        + _all)
    assert "哨兵：索引不是時間軸" in _all, (
        "紅框沒有帶出真正的例外訊息 —— 那就只是一個紅色的猜測。\n" + _all)
    assert "這次沒有帶回淨值序列" not in _all, (
        "壞索引被說成「沒有帶回淨值序列」—— 序列帶回來了，那句話是假的。\n" + _all)


def test_the_failed_source_count_excludes_synthetic_markers():
    """「N 個來源」只能數**真的來源**（獨立稽核 應修 2）。

    `nav_series` 是 `finalize_fund_metrics` 追加的**合成標記**（意思是「沒有淨值序列」），
    不是一個被試過的來源。畫面曾印「這個代碼在 **3** 個來源都沒有取到淨值」，
    **實際只試了 2 個** —— 而 `_nav_reason()` 正是靠這個名字把它挑出來當缺值原因用。
    **同一個東西一邊當標記、一邊當來源數**，那個數字是編出來的證據。

    ⚠️ 本條也守**去重**：同一個來源被 append 兩次不得算成兩個。
    """
    assert TRACE_NAV_SERIES in SYNTHETIC_TRACE_SOURCES, (
        "`nav_series` 沒有被列為合成標記 —— 它會被算進來源數。")
    _blank = _BLANK_RESULT()
    assert _failed_source_count(_blank) == 2, (
        "來源數把合成標記也算進去了。fixture 的 source_trace 是 "
        "bank_platform（失敗）／morningstar（失敗）／nav_series（合成標記）"
        f"→ 應為 2，實得 {_failed_source_count(_blank)}。")
    assert "在 2 個來源" in _text(_render(applied=FAKE_QUERY, result=_blank)), (
        "畫面上的來源數與 `_failed_source_count()` 不一致。")
    # 去重
    _dupe = _BLANK_RESULT()
    _dupe["source_trace"].append(
        {"source": "bank_platform", "success": False, "error": "短窗重試也失敗"})
    assert _failed_source_count(_dupe) == 2, (
        "同一個來源被追加兩次就被算成兩個 —— 那同樣是虛報。")
    # 合成標記全員：逐一確認每一個都不會把數字撐大
    for _syn in SYNTHETIC_TRACE_SOURCES:
        _r = _BLANK_RESULT()
        _r["source_trace"].append({"source": _syn, "success": False, "error": "x"})
        assert _failed_source_count(_r) == 2, (
            f"合成標記 {_syn!r} 把來源數撐大了。")


# ══════════════════════════════════════════════════════════════════════════
# `nav_history_merge` —— 2026-09-06 補的合成標記，以及它的「不要再漏第二個」守衛
# ══════════════════════════════════════════════════════════════════════════
#: 上游**確實會**以 falsy `success` 出現、而且**經人工裁決要計入**「試過的來源數」的名字。
#: ⚠️ 這不是「所有真來源」的清單 —— 只收**會失敗**的那些（成功的不影響計數）。
#: ⛔ 往這裡加名字**等於裁決「它算一次試過的來源」**，請附理由，不要為了消紅而加。
COUNTED_REAL_SOURCES: frozenset = frozenset({
    "alphavantage", "bank_platform", "morningstar", "taiwanlife_direct", "yahoo_finance",
    # ⚠️ `multi_source` 是「多來源流程**本身**拋例外」的紀錄（`fund_orchestration.py:1013`）。
    #    **算不算一次「試過的來源」有兩種讀法**，2026-09-06 本組**不裁決**、維持現況（計入），
    #    只把它具名登記在這裡 —— 具名之後它至少不會再是「沒有人看過的漏網」。
    "multi_source",
})

#: 上游那兩個檔裡**帶 `source` 鍵、但根本不是 `source_trace` 條目**的 dict。
#: ⛔ **這份清單是本組先前一句錯話的產物，理由寫在這裡免得有人再犯**：
#:    本組曾報「`fetch_holdings:exception` 也會把來源數撐大」——**那是假的**。
#:    它是 `result["holdings"]["source"]`（`fund_orchestration.py:791`），
#:    **從來沒有進過 `source_trace`**。當時是拿一個手寫的 dict 當成程式會產生的情境。
#:    ⚠️ **同一個坑，本條守衛自己上線第一次跑就又抓到三個**（2026-09-06）：
#:    ``fundclear`` / ``moneydj_menu`` / ``mj_search`` 是
#:    `search_fundclear()` 與 `search_moneydj_by_name()` **搜尋結果的每一列**
#:    （形狀 `{full_key, name, portal, nav, source}`，append 進區域變數 `results`
#:    後由函式回傳），**不是** `source_trace`。
#:    → 本組先前用「只掃 `.append()` 的引數」那種掃法**看不到它們**；
#:      改成「掃所有帶 `source` 鍵的 dict」才看得到，代價是要像這樣逐一 triage。
#:      **寧可多抓再人工判，也不要用一份剛好掃不到的字表下結論。**
NOT_TRACE_ENTRIES: frozenset = frozenset({
    "fetch_holdings:exception",
    "fundclear", "moneydj_menu", "mj_search",
})

#: 會 `append` 進 `source_trace` 的上游檔（**恰好這兩個**，AST 實測）。
#: 第三個檔開始 append → 下面的守衛轉紅，因為那表示本檔的掃描範圍不再完整。
TRACE_PRODUCERS: tuple[str, ...] = (
    "services/fund_service.py",
    "repositories/fund/fund_orchestration.py",
)


def _trace_marker_shapes() -> list[tuple[str, str, int, object]]:
    """AST 掃上游兩個檔裡**所有帶字面 `source` 鍵的 dict**，連同其 `success` 字面值。

    回傳 `(檔, source 名, 行號, success)`；`success` 缺鍵時回 `KeyError` 這個哨兵物件。

    ⚠️ **為什麼掃 dict 而不是掃 `.append()`**：`services/fund_service.py:1203` append 的是
    一個**變數**（`_hist_trace`，由 `_merge_nav_history_series` 回傳）——
    只掃 append 的引數，`nav_history_merge` 這一族**一個都看不到**。
    **這正是它當初被漏掉的機制**：用錯的形狀去掃，跑一百次也掃不到。
    """
    out: list[tuple[str, str, int, object]] = []
    for _rel in TRACE_PRODUCERS:
        _tree = ast.parse((ROOT / _rel).read_text(encoding="utf-8"))
        for _n in ast.walk(_tree):
            if not isinstance(_n, ast.Dict):
                continue
            _src = _succ = KeyError
            for _k, _v in zip(_n.keys, _n.values):
                if not (isinstance(_k, ast.Constant) and isinstance(_k.value, str)):
                    continue
                if _k.value == "source":
                    _src = _v.value if isinstance(_v, ast.Constant) else None
                elif _k.value == "success":
                    _succ = _v.value if isinstance(_v, ast.Constant) else None
            if isinstance(_src, str):
                out.append((_rel, _src, _n.lineno, _succ))
    return out


def test_the_nav_history_merge_marker_never_counts_as_a_failed_source():
    """`nav_history_merge` 是**我方併資料的步驟**，不是一次對外取數 —— 不得計入來源數。

    ## 兩種形狀都要驗，因為第二種才是最容易漏的

    1. ``{"source": …, "success": False, "error": …}`` —— 讀 Google Sheet 失敗
       （`services/fund_service.py:1098`）。
    2. ``{"source": …, "merged": False, "hist_points": …}`` —— **完全沒有 `success` 鍵**
       （同檔 `:1131`）。語意是「讀成功了，只是累積點還沒產生淨增益」＝ **一切正常**，
       而 `_trace_rows()` 的 ``bool(_t.get("success"))`` 會把缺鍵判成失敗。
       **第 2 種在什麼都沒出錯的時候虛報**，比第 1 種更該有測試。

    ## 突變實驗（2026-09-06 實跑，拿掉修復必須轉紅）

    - **M1**：把 `"nav_history_merge"` 從 :data:`SYNTHETIC_TRACE_SOURCES` 拿掉 →
      **本條兩個 case 都轉紅**（來源數 2 → 3，畫面字串跟著變）。✅

    ⚠️ **一個「沒有轉紅」的突變，據實記下來，不要讓後人以為本條守得比實際多**：

    - **M5**：把 :func:`~ui.views.page_03_research._trace_rows` 的
      ``_ok = bool(_t.get("success"))`` 改成 ``_ok = _t.get("success") is not False``
      → **本條仍然全綠**。

      **為什麼綠得有道理**：那個改動讓「缺 `success` 鍵」被判成**成功**，
      症狀（虛報）一樣消失了 —— 本條驗的是**結果**（不得計入），不是**手段**。
      **為什麼仍要寫下來**：本條因此**不釘住**「排除是靠 source 名字做的」這件事。
      若日後有人動 `_trace_rows` 的 falsy 判定，本條**不會**知道
      —— 那時要看的是 `test_a_total_failure_shows_the_source_trace_and_never_paints_red`。
      ⛔ 不要把 M5 讀成「這條測試很弱」，也不要讀成「怎麼改都行」：
      M5 同時把**所有**缺鍵的 trace 條目都改判成成功，那是另一個範圍大得多的行為變更。
    """
    assert "nav_history_merge" in SYNTHETIC_TRACE_SOURCES, (
        "`nav_history_merge` 不在合成標記清單裡 —— 它會被算成一個「取不到淨值的來源」。")

    _shapes = {
        "讀 sheet 失敗（success=False）":
            {"source": "nav_history_merge", "success": False,
             "error": "NavHistoryError: 開不了 NAV sheet"},
        "讀成功但無淨增益（**沒有 success 鍵**）":
            {"source": "nav_history_merge", "merged": False, "hist_points": 56,
             "hist_first": "2026-06-01", "hist_last": "2026-08-30", "added": 0,
             "note": "累積 56 點目前全部落在本次 live 序列的日期範圍內 → 尚未產生淨增益。"},
    }
    for _why, _entry in _shapes.items():
        _r = _BLANK_RESULT()
        _r["source_trace"].append(_entry)
        assert _failed_source_count(_r) == 2, (
            f"{_why}：`nav_history_merge` 被算進來源數了 —— "
            f"實際試過的取數來源仍是 2 個（bank_platform／morningstar），"
            f"實得 {_failed_source_count(_r)}。")
        assert "在 2 個來源" in _text(_render(applied=FAKE_QUERY, result=_r)), (
            f"{_why}：畫面上的來源數被撐大了。")


def test_every_upstream_failure_marker_has_been_triaged():
    """上游**每一個**會以 falsy `success` 出現的標記，都必須被裁決過 —— 沒有漏網。

    ## 這條在守什麼（它不是在守某一個名字）

    `SYNTHETIC_TRACE_SOURCES` 是**黑名單**，被測檔自己就寫著「會腐化」。
    但 2026-09-06 查出來的事實比「腐化」更難堪：**它寫下的那一天就不完整**
    —— `nav_history_merge` 在加黑名單的那個 commit（`b83c29f`）當下，
    `services/fund_service.py` 裡已經有 4 處。

    → **靠人記得去對是不會發生的。** 本條把「對一遍」變成機器做的事：
    上游每一個可能被畫成「失敗」的 `source` 名字，**要嘛在黑名單裡（不計入）、
    要嘛在 :data:`COUNTED_REAL_SOURCES` 裡（已裁決要計入）**，兩邊都不在就轉紅。

    ⚠️ **它不會替你決定**新標記該歸哪一邊 —— 它只保證你**知道有這件事**。
    ⛔ 轉紅時**不要**為了消紅隨手往某一邊加：加進 `COUNTED_REAL_SOURCES` 等於
    宣告「它是一次真的取數嘗試」，那是會被印在使用者眼前的數字。

    ## 突變實驗（2026-09-06 實跑，逐條確認會轉紅）

    - 把 `"nav_history_merge"` 從黑名單拿掉、也不加進 `COUNTED_REAL_SOURCES` → **轉紅**。
    - 把 `"multi_source"` 從 `COUNTED_REAL_SOURCES` 拿掉 → **轉紅**。
    - 在 `TRACE_PRODUCERS` 裡刪掉 `fund_service.py`（模擬掃描範圍縮水）→ **轉紅**
      （第一個斷言：實際 append 的檔不只清單裡那些）。
    """
    # ① 掃描範圍本身要正確：只有這兩個檔會 append 進 source_trace。
    _appenders: set[str] = set()
    for _p in sorted(ROOT.glob("**/*.py")):
        _rel = str(_p.relative_to(ROOT))
        if _rel.startswith((".git", "tests/", "_recon/")):
            continue
        try:
            _t = ast.parse(_p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        for _n in ast.walk(_t):
            if (isinstance(_n, ast.Call) and isinstance(_n.func, ast.Attribute)
                    and _n.func.attr == "append"
                    and "source_trace" in ast.unparse(_n.func.value)):
                _appenders.add(_rel)
    assert _appenders == set(TRACE_PRODUCERS), (
        f"會 append 進 source_trace 的檔變了：{sorted(_appenders)}\n"
        f"本檔的掃描範圍 `TRACE_PRODUCERS` 是 {list(TRACE_PRODUCERS)} —— "
        "範圍不對的話，下面那一段 triage 是在一份不完整的清單上做的（本 bug 的原始成因）。")

    # ② 每一個可能被畫成「失敗」的 source 名字都要被裁決過。
    _untriaged: dict[str, list[str]] = {}
    for _rel, _src, _lineno, _succ in _trace_marker_shapes():
        if _succ is True:                       # 只在成功時 append → 不影響失敗計數
            continue
        if _src in NOT_TRACE_ENTRIES:           # 帶 source 鍵但不是 trace 條目
            continue
        if _src in SYNTHETIC_TRACE_SOURCES or _src in COUNTED_REAL_SOURCES:
            continue
        _untriaged.setdefault(_src, []).append(f"{_rel}:{_lineno}")

    assert not _untriaged, (
        "上游有還沒被裁決過的失敗標記：\n"
        + "\n".join(f"  {_s!r}  ({', '.join(_w)})" for _s, _w in sorted(_untriaged.items()))
        + "\n\n它現在會被算進畫面上那句「在 N 個來源都沒有取到淨值」。請逐一裁決：\n"
          "  · 它是我方 pipeline 對自己下的結論 → 加進 `SYNTHETIC_TRACE_SOURCES`；\n"
          "  · 它是一次真的對外取數嘗試       → 加進 `COUNTED_REAL_SOURCES`；\n"
          "  · 它根本不進 source_trace        → 加進 `NOT_TRACE_ENTRIES`。\n"
          "⛔ 三個都要附理由。隨手加一邊就是把一個沒查過的判斷印給使用者看。")


@pytest.mark.parametrize("key,label,unit", RISK_METRICS)
def test_a_nan_metric_is_treated_as_missing_not_as_a_value(key: str, label: str, unit: str):
    """`NaN` ＝ 缺值，**不得**被畫成一個有值的指標（獨立稽核 應修 3）。

    拿掉 `_fmt()` 的 `if value != value: return None` → 稽核組實測 58 passed，
    而行為**確實變了**：`Sharpe nan` 從「未提供」變成一個有值的 metric。
    **缺值被重新分類成有值** —— 使用者失去「未提供」那個誠實訊號，
    而 `nan` 在畫面上看起來只像是一個沒見過的格式，不像是「這個算不出來」。

    ⚠️ 純函式層也驗一次：`_fmt(float("nan"))` 必須是 `None`，
    不是「渲染時剛好看不出來」。
    """
    assert _fmt(float("nan")) is None, "`_fmt()` 把 NaN 當成一個可顯示的數值。"
    assert _fmt(float("nan"), "%") is None, "帶單位時 NaN 的防線失效。"
    _metrics = {**RISK_SENTINELS, key: float("nan")}
    _body = "\n".join(_segments(_render(applied=FAKE_QUERY,
                                        result=_RICH_RESULT(metrics=_metrics))
                                ).get(DEEP_DIVE_CARDS[2], []))
    assert "nan" not in _body.lower(), (
        f"`metrics[{key!r}]` 是 NaN，卻被畫成一個值：\n{_body}")
    assert re.search(re.escape(label) + r"\s*[-+]?\d", _body) is None, (
        f"「{label}」是 NaN（＝算不出來），畫面上卻給了它一個數字：\n{_body}")
