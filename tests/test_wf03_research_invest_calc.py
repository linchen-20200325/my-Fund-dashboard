"""③／⑧ 標的探索 —— **投資試算**那一塊的守衛（2026-09-08 客戶拍板搬進深度區）。

客戶原話（逐字，這是規格）
--------------------------
> 3. **投資試算歸屬：定案搬移至 ⑧（標的探索）的單一基金深度區塊，⑥ 僅保留現有持倉之
>    每月配息推估總額。**
> 4. **逐檔配息明細：確認「不留逐筆」，僅顯示每月推估合計金額與是否吃本金。**

⚠️ 第 4 條是對 **⑥** 的裁決，**本檔不碰 ⑥**；但它決定了 ⑧ 這邊要做多完整 ——
⑥ 不再提供逐筆，使用者要看細節就會來 ⑧，所以 ⑧ 的算式必須把**依據**講出來
（是最近一筆實配、還是年化配息率攤平），不能只丟一個金額。

本檔守什麼（兩層，缺一不可）
----------------------------
=================================== ==========================================
層                                   守的東西
=================================== ==========================================
**算式層** `services/fund_invest_calc.py`  每一種缺料各自的原因代碼、**一個 0 都不填**、
                                     幣別對不上不換算、算法真的走既有 SSOT
**畫面層** `ui/views/page_03_research.py`  一句結論、公式收在 expander、灰不是紅、
                                     指路指到畫面上真的有的欄位、不講內部語言
=================================== ==========================================

⚠️ **每一條盡量寫「機制」而不是「某一顆突變會紅」** —— 「拿掉 X 這一行會轉紅」是
   **一次觀察**；下一個人換個寫法犯同一個錯，那條斷言照樣綠。故缺料那一族一律
   **參數化**，讓所有同類的錯都在射程內。（同一段話寫在
   `tests/test_wf03_research_batch.py` 開頭，本檔照同一個形狀。）

⭐ **本檔末段有真的突變測試** —— 命名一律是 ``test_<拔掉什麼>_turns_the_<誰>_red``
   （四條：`test_removing_the_currency_clash_guard…` / `test_fabricating_a_payout_rate…` /
   `test_pretending_a_missing_rate_is_one…` / `test_reusing_one_sentence_for_every_reason…`）。
   它們**在同一個 process 裡把修復拔掉**（換掉合作者），然後斷言對應的守衛**真的轉紅**、
   還原之後**再驗回綠**。憲法 §-1.5 v3 `03`-1 要的就是這個：
   「突變測試（拔掉修復邏輯必須轉為紅燈）」。

⚠️ **本檔看不見什麼（照實寫，不要讀成「守死了」）**
--------------------------------------------------
1. **不驗真的匯率**。`fx_rate_to_twd()` 會出網，本檔一律傳自己的 `fx_lookup` 替身
   或在渲染層用 `_render(fx=…)`。⇒「四源 fallback 有沒有壞」不在射程內，
   那是 `services/fund_service.py` 那一側的事。
2. **不驗 `monthly_dividend_from_records` 算得對不對** —— 它有自己的守衛
   （`tests/test_monthly_dividend_units.py`）。本檔驗的是「**有沒有真的走它**」。
3. ~~**本地沒有 `streamlit` / `pandas` / `pytest`，本檔從未在真 pytest 下跑過**
   （見 PR 的自陳）。畫面層那幾條是靠 `tests/test_wf03_research_skeleton.py::_render`
   這個既有 harness 跑的，**判定邏輯本地實跑過**，但那不是 pytest。~~

   → **2026-09-08 就地更正（有意識的更正，不是漏刪；由第五輪獨立稽核點名）：
   前半句不成立，本檔已經在真 pytest 下跑過了。**

   * **`pytest` 本地是有的**：`/root/.local/bin/pytest` 9.0.2（uv tool venv）。
     當初只用**系統 `python3`** 試過一次 `import pytest` 就下了「沒有 pytest」這個結論
     —— **一個直譯器的結果被寫成整個環境的事實**。
   * **跑法**：streamlit 最小假件放 `PYTHONPATH`（**不進 repo**）＋ `--noconftest`
     ＋ 系統 `site-packages`。本檔在此組合下**只有一條紅**：
     `test_the_rate_lookup_still_asks_for_the_yf_code`（它要 `pandas`，本地沒有）。
     ⚠️ **刻意不寫「N passed」** —— 那個數字每加一條測試就過期，
     而**這一則正是在更正一句過期的話**；寫一個會漂的數字進來，只是替下一輪製造同樣的錯。
   * **仍然成立的那半邊**：`streamlit` / `pandas` 本地**確實**沒有，
     完整套件（`tests/` 全部）本地**仍然**跑不起來，**全套的真憑據以 CI 為準**。

   ⚠️ **這一則被留下來的原因值得記**：PR 描述裡我已經把這句話撤回了，
   **但沒有回頭改程式碼裡的這一份** —— 而**下一個人是先讀 docstring 才讀 PR 的**。
   「更正只寫在別的地方 ＝ 沒有更正」是本 repo 明文記載過的失效模式。
"""
from __future__ import annotations

import ast
import math
import pathlib
import re
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import services.fund_invest_calc as CALC  # noqa: E402
import ui.views.page_03_research as _PAGE_MOD  # noqa: E402
from services.currency import CCY_NORMALIZE, _CCY_YF_OVERRIDES, normalize_ccy  # noqa: E402
from services.fund_invest_calc import (  # noqa: E402
    ADR_FROM_RECORDS,
    ADR_LOCAL_RATE,
    ADR_OFFICIAL,
    BASIS_ESTIMATE,
    BASIS_RECORDS,
    CCY_CONFLICT,
    DEFAULT_AMOUNT_TWD,
    NO_AMOUNT,
    NO_CURRENCY,
    NO_FX,
    NO_INCOME_BASIS,
    NO_NAV,
    comparable_ccy,
    dividend_currency,
    estimate_monthly_income,
    fund_currency,
)
from services.health.dividend import _resolve_adr_with_fallback  # noqa: E402
from shared.data_quality import reconcile_row_currencies  # noqa: E402
from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.views.page_03_research import (  # noqa: E402
    CCY_UNKNOWN,
    DEEP_DIVE_INVEST,
    DEEP_DIVE_TABLES,
    DIVIDEND_COLS,
    GAP_AMOUNT,
    GAP_AMOUNT_NEG,
    GAP_NO_DATE,
    GAP_NO_ROWS,
    INVEST_SUBMIT_LABEL,
    _ADR_SOURCE_LABELS,
    _INVEST_AMOUNT_KEY,
    _INVEST_BLOCKED_NOTES,
    _INVEST_FORM_KEY,
    _LABEL_INVEST_AMOUNT,
    _SK_INVEST_AMOUNT,
    _declared_currency,
    _dividend_caption,
    _dividend_rows,
    _income_basis_gap,
    _invest_basis_note,
    _invest_compare,
    _invest_note_for,
    _invest_where,
)

# ⚠️ **共用同一個渲染 harness，刻意不另寫第二份** —— 兩份會在「怎麼 patch `st`」
#    這件事上漂移（理由見那一支 `_render()` 開頭那段長註）。
from test_wf03_research_skeleton import (  # noqa: E402
    FAKE_QUERY,
    SELECTED_CODE,
    _BLANK_RESULT,
    _RICH_RESULT,
    _render,
    _segments,
)

_PAGE = pathlib.Path(__file__).resolve().parent.parent / "ui" / "views" / "page_03_research.py"
_CALC_SRC = pathlib.Path(__file__).resolve().parent.parent / "services" / "fund_invest_calc.py"

# ══════════════════════════════════════════════════════════════════
# 假資料 —— **每一個數字都是獨一無二的哨兵**
#
# ⚠️ 理由同骨架守衛那一組：「某一格印出了別格的數字」「某一格印出了 0」
#    在共用數值的 fixture 底下**完全看不出來**。
# ⚠️ 刻意讓「最近一筆實配 × 12 ÷ 本金」**和掛牌配息率對得上** —— 那是 happy path；
#    要驗「對不上」的那條路，用 `_FUND(moneydj_div_yield=…)` 把它推開。
# ══════════════════════════════════════════════════════════════════

#: 哨兵淨值（原幣）。
SENT_NAV: float = 25.0
#: 哨兵最近一筆實配（原幣／單位）。25 × 0.0575 / 12 ⇒ 年化 5.75%。
SENT_DIV: float = 25.0 * 0.0575 / 12.0
#: 哨兵掛牌年化配息率（%）。
SENT_ADR: float = 5.75
#: 哨兵金額（**刻意不是 100 萬** —— 與預設值一樣的話，「有沒有吃到使用者填的值」看不出來）。
SENT_AMOUNT: float = 2_500_000.0
#: 哨兵匯率。
SENT_FX: float = 37.25


def _FUND(**over) -> dict:
    """一份「什麼都有」的 L2 回傳（flat shape）。`over` 用來逐項挖掉東西做突變。"""
    _f = {
        "currency": "USD",
        "metrics": {"nav": SENT_NAV},
        "nav_latest": None,
        "moneydj_div_yield": SENT_ADR,
        "dividends": [
            {"date": "2026/08/15", "amount": SENT_DIV, "currency": "USD"},
            {"date": "2026/07/15", "amount": SENT_DIV, "currency": "USD"},
        ],
    }
    _f.update(over)
    return _f


def _fx(_ccy, **_kw):
    return SENT_FX


def _no_fx(_ccy, **_kw):
    return None


def _explodes(_ccy, **_kw):  # pragma: no cover — 被呼叫就代表測試失敗
    raise AssertionError("台幣計價的基金不該去問匯率")


#: 回傳 dict 裡**所有數值欄位**。缺料時它們必須**全部是 None**（一個 0 都不准填）。
_NUMERIC_FIELDS: tuple[str, ...] = (
    "fx_to_twd", "amount_ccy", "units", "monthly_ccy", "monthly_twd",
    "monthly_units", "annual_twd", "latest_div_per_unit", "adr_pct",
    "implied_annual_pct",
)


# ══════════════════════════════════════════════════════════════════
# 算式層｜有料就算得出來
# ══════════════════════════════════════════════════════════════════

def test_a_real_amount_turns_into_units_and_a_monthly_number():
    """⭐ 核心：投 X 元 → 買得到幾單位、每月大約領多少。**逐項對算式驗，不看字串。**"""
    _f = estimate_monthly_income(_FUND(), SENT_AMOUNT, fx_lookup=_fx)
    assert _f["units_blocked"] == "" and _f["income_blocked"] == "", _f

    _amount_ccy = SENT_AMOUNT / SENT_FX
    _units = _amount_ccy / SENT_NAV
    assert math.isclose(_f["amount_ccy"], _amount_ccy, rel_tol=1e-9)
    assert math.isclose(_f["units"], _units, rel_tol=1e-9)
    assert math.isclose(_f["monthly_ccy"], SENT_DIV * _units, rel_tol=1e-9)
    assert math.isclose(_f["monthly_twd"], SENT_DIV * _units * SENT_FX, rel_tol=1e-9)
    assert math.isclose(_f["annual_twd"], _f["monthly_twd"] * 12.0, rel_tol=1e-9)
    # 這筆錢實際拿到的年化 % —— 本例刻意設計成與掛牌配息率一致。
    assert math.isclose(_f["implied_annual_pct"], SENT_ADR, rel_tol=1e-6)
    assert _f["income_basis"] == BASIS_RECORDS
    assert _f["adr_source"] == "moneydj_wb05", (
        "年化配息率沒有走 `_resolve_adr_with_fallback` 的第一層 —— "
        "`adr_source` 是它回傳的血緣標記，不對代表換了一條路。")


def test_the_default_amount_is_the_repo_wide_one_not_a_second_hundred_thousand():
    """預設金額走既有 SSOT（`dividend_calc.DEFAULT_PRINCIPAL_TWD`），**不另寫一個 100 萬**。

    §2.1：同一個事實只准有一個真相源。這一條擋的是「有人在頁面裡再打一次
    `1_000_000`」—— 那一刻起兩邊會各自漂移，而畫面上看不出來。
    """
    from services.health.dividend_calc import DEFAULT_PRINCIPAL_TWD
    assert DEFAULT_AMOUNT_TWD is DEFAULT_PRINCIPAL_TWD or \
        DEFAULT_AMOUNT_TWD == DEFAULT_PRINCIPAL_TWD, (
            "預設試算金額沒有吃 `dividend_calc.DEFAULT_PRINCIPAL_TWD` 這個既有 SSOT。")


def test_a_twd_fund_never_goes_and_asks_for_a_rate():
    """台幣計價 ⇒ **一次網路都不打**。`fx_lookup` 被呼叫就是紅。

    ⚠️ 這不只是省一次往返：匯率來源掛掉時，台幣基金的試算**不該**跟著失效。
    """
    _f = estimate_monthly_income(
        _FUND(currency="TWD",
              dividends=[{"date": "2026/08/15", "amount": SENT_DIV, "currency": "TWD"}]),
        SENT_AMOUNT, fx_lookup=_explodes)
    assert _f["fx_to_twd"] == 1.0
    assert math.isclose(_f["units"], SENT_AMOUNT / SENT_NAV, rel_tol=1e-9)


# ══════════════════════════════════════════════════════════════════
# 算式層｜缺料一律留白，**一個 0 都不填**
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("kwargs,amount,lookup,reason", [
    (dict(), 0, _fx, NO_AMOUNT),
    (dict(), None, _fx, NO_AMOUNT),
    (dict(), "不是數字", _fx, NO_AMOUNT),
    (dict(currency=""), SENT_AMOUNT, _fx, NO_CURRENCY),
    (dict(currency=None), SENT_AMOUNT, _fx, NO_CURRENCY),
    (dict(metrics={}, nav_latest=None), SENT_AMOUNT, _fx, NO_NAV),
    (dict(metrics={"nav": 0}, nav_latest=None), SENT_AMOUNT, _fx, NO_NAV),
    (dict(), SENT_AMOUNT, _no_fx, NO_FX),
    (dict(), SENT_AMOUNT, None, NO_FX),
])
def test_every_kind_of_missing_input_gets_its_own_reason_and_zero_numbers(
        kwargs, amount, lookup, reason):
    """⭐ 逐種缺料：**原因代碼各自不同，而且每一個數值欄位都是 `None`**。

    §1：`0` 的意思是「算出來剛好是 0」，`None` 的意思是「算不出來」。
    在畫面上這兩者長得幾乎一樣，所以必須在**算式層**就分開，不能靠 UI 記得。
    """
    _f = estimate_monthly_income(_FUND(**kwargs), amount, fx_lookup=lookup)
    assert _f["units_blocked"] == reason, _f
    assert _f["income_blocked"] == reason, (
        "單位數算不出來時，每月配息**必須**帶同一個原因 —— "
        "否則畫面會出現「上面說沒有匯率、下面說沒有配息紀錄」兩句互不相干的話。")
    _filled = {_k: _f[_k] for _k in _NUMERIC_FIELDS if _f[_k] is not None}
    assert not _filled, (
        f"缺料（{reason}）卻填了數字：{_filled} —— "
        "§1：算不出來就留白，填 0 或任何佔位值都是造假。")


def test_a_missing_payout_rate_is_left_blank_not_zeroed():
    """⭐ **客戶點名的那一條**：配息率查不到 → 誠實留白，不是給 0。

    「每月領 0 元」＝「這一檔不配息」；「每月領 —」＝「我們不知道」。
    對使用者是**兩個完全不同的決定**，所以不准合併。

    ⚠️ **單位數不受影響**：買得到幾單位跟配不配息無關，那一半照樣要算出來
    （這一條同時擋「一個缺料就整塊放棄」的反向退化）。
    """
    _f = estimate_monthly_income(
        _FUND(dividends=[], moneydj_div_yield=None), SENT_AMOUNT, fx_lookup=_fx)
    assert _f["income_blocked"] == NO_INCOME_BASIS
    assert _f["monthly_twd"] is None and _f["monthly_ccy"] is None
    assert _f["monthly_units"] is None and _f["annual_twd"] is None
    assert _f["monthly_twd"] != 0, "配息率缺失被填成 0 —— 那是在替使用者編一個結論。"
    # 單位數那一半照樣算得出來。
    assert _f["units_blocked"] == ""
    assert math.isclose(_f["units"], (SENT_AMOUNT / SENT_FX) / SENT_NAV, rel_tol=1e-9)


def test_a_declared_zero_payout_rate_is_not_mistaken_for_a_real_number():
    """配息率 `0` 走的是既有 SSOT 的判定（`> 0` 才算數），本檔不另立一套。

    ⚠️ 這條的價值在於**把現況釘住**：`_resolve_adr_with_fallback` 對 `0` 的處置
    （視為「沒有值」往下一層退）是**它的**決定；哪天它改了，這裡會轉紅，
    到時候要一起想「0% 配息率該怎麼顯示」，而不是靜默跟著變。
    """
    _f = estimate_monthly_income(
        _FUND(dividends=[], moneydj_div_yield=0), SENT_AMOUNT, fx_lookup=_fx)
    assert _f["income_blocked"] == NO_INCOME_BASIS
    assert _f["adr_pct"] is None


def test_a_missing_rate_never_silently_becomes_a_rate_of_one():
    """⭐ 舊 ③ 真的發生過的事故：非台幣基金拿不到匯率時，**把台幣金額當成原幣金額**。

    舊 `ui/tab2_single_fund.py` 就地記著它：「等於把 100 萬台幣當成 100 萬日圓，
    單位數 / 月配息 / 1Y 預估市值三個 metric 照樣印出來（日圓差約 4.8 倍）。
    畫面說不算，實際算了。」

    **正對照在下面第二個斷言** —— 它把「如果真的犯了那個錯會印出什麼」算出來，
    確認守衛擋的是一個**真的會發生**的數字，而不是空氣。
    """
    _f = estimate_monthly_income(_FUND(), SENT_AMOUNT, fx_lookup=_no_fx)
    assert _f["units"] is None and _f["units_blocked"] == NO_FX
    _would_have_been = SENT_AMOUNT / SENT_NAV        # ← 把匯率當 1 的那個結果
    assert _would_have_been > 0, "正對照本身要是一個真的數字，否則這條在對空氣生效。"


# ══════════════════════════════════════════════════════════════════
# 算式層｜幣別衝突：不換算、不挑一邊
# ══════════════════════════════════════════════════════════════════

def test_a_currency_clash_never_gets_converted():
    """⭐ **客戶點名的那一條**：逐筆配息宣告 USD、基金計價 TWD → **不硬換算**。

    本 repo 既有的處置就在同一頁上（`_dividend_caption` 逐字）：
    「本頁**不挑一個**宣告 · 金額照原幣顯示，不合計、不換算」。本塊沿用它。

    **為什麼不能挑一邊**：`monthly_dividend_from_records` 沒有幣別概念 ——
    它會把「最近一筆實配」直接乘上持有單位再乘匯率。若那筆其實是美元卻被當成台幣，
    畫面會印出一個**看起來完全正常、實際差三十倍**的月配息金額（§4.1 量綱）。
    """
    _f = estimate_monthly_income(
        _FUND(currency="TWD"),                       # 基金 TWD、逐筆宣告 USD
        SENT_AMOUNT, fx_lookup=_explodes)            # TWD ⇒ 不該問匯率
    assert _f["income_blocked"] == CCY_CONFLICT, _f
    assert _f["monthly_twd"] is None and _f["monthly_ccy"] is None
    assert _f["monthly_units"] is None and _f["annual_twd"] is None
    # ⭐ 但「買得到幾單位」與配息幣別無關，那一半**必須**照樣給。
    assert _f["units_blocked"] == ""
    assert math.isclose(_f["units"], SENT_AMOUNT / SENT_NAV, rel_tol=1e-9)


@pytest.mark.parametrize("rows", [
    [{"date": "2026/08/15", "amount": SENT_DIV}],                        # 完全沒標
    [{"date": "2026/08/15", "amount": SENT_DIV, "currency": ""}],        # 標了空字串
    [{"date": "2026/08/15", "amount": SENT_DIV, "currency": "USD"},
     {"date": "2026/07/15", "amount": SENT_DIV, "currency": ""}],        # 一列有一列沒有
])
def test_an_undeclared_dividend_currency_is_not_treated_as_a_clash(rows):
    """**不知道 ≠ 不一致。** 逐筆沒標幣別是常態，照算，但畫面要把假設講出來。

    ⛔ 反過來擋掉的話，等於把大多數基金的配息試算一起關掉 —— 那是**過度觸發**，
    §1 要的是不猜，不是什麼都不做。
    """
    _f = estimate_monthly_income(_FUND(dividends=rows), SENT_AMOUNT, fx_lookup=_fx)
    assert _f["income_blocked"] == "", _f
    assert _f["monthly_twd"] is not None
    assert _f["dividend_currency"] == "", (
        "逐筆幣別講不出一個一致的答案時，`dividend_currency` 必須是空字串 —— "
        "畫面靠它決定要不要把「這裡假設同幣別」那句話講出來。")


# ══════════════════════════════════════════════════════════════════
# 算式層｜真的走既有 SSOT，不是自己重寫一份
# ══════════════════════════════════════════════════════════════════

def test_the_monthly_number_really_comes_from_the_shared_calculator():
    """⭐ 每月配息**真的**走 `services.health.dividend_calc.monthly_dividend_from_records`。

    做法：把那支換成哨兵替身，看回傳值有沒有跟著變。
    ⛔ **不用 AST 驗 import** —— import 得到不代表真的呼叫它
    （`ui/views/page_03_research.py` 的模組 docstring 記著同型教訓：
     「錯的 patch 不會報錯，只會讓斷言對著半份畫面生效」）。
    """
    _real = CALC.monthly_dividend_from_records
    _seen = {}

    def _spy(divs, units, nav, fx, adr_pct=None):
        _seen.update(divs=divs, units=units, nav=nav, fx=fx, adr_pct=adr_pct)
        return {"latest_div_per_unit": 1.0, "mon_div_ccy": 11.0,
                "mon_div_twd": 22.0, "mon_div_units": 33.0, "source": BASIS_RECORDS}

    CALC.monthly_dividend_from_records = _spy
    try:
        _f = estimate_monthly_income(_FUND(), SENT_AMOUNT, fx_lookup=_fx)
    finally:
        CALC.monthly_dividend_from_records = _real
    assert _f["monthly_twd"] == 22.0 and _f["monthly_units"] == 33.0, (
        "每月配息不是那支 SSOT 算的 —— 本模組自己又寫了一份。")
    assert math.isclose(_seen["nav"], SENT_NAV) and math.isclose(_seen["fx"], SENT_FX), (
        f"傳給 SSOT 的引數不對：{_seen}")


def test_the_payout_rate_really_comes_from_the_three_layer_resolver():
    """年化配息率**真的**走 `services.health.dividend._resolve_adr_with_fallback`。

    那支同時回傳「**實際命中的是哪一層**」（§2.2 血緣）—— 本模組原封帶出來，
    畫面才有辦法說出這個數字是官方的還是本地算的。
    """
    _real = CALC._resolve_adr_with_fallback
    CALC._resolve_adr_with_fallback = lambda _fund: (9.99, "哨兵來源")
    try:
        _f = estimate_monthly_income(_FUND(), SENT_AMOUNT, fx_lookup=_fx)
    finally:
        CALC._resolve_adr_with_fallback = _real
    assert _f["adr_pct"] == 9.99 and _f["adr_source"] == "哨兵來源", (
        "年化配息率不是那支 SSOT 解出來的，或血緣標記被丟掉了。")


def test_the_agreement_verdict_uses_the_repo_wide_reconciler():
    """「兩個數字對不對得上」走既有的 §4.3 對帳器，**本模組不自訂容差**。

    ⛔ 這一條擋的是「有人在這裡寫 `abs(a - b) < 0.5`」—— 那會變成本 repo
    對同一件事的**第二套判準**，而兩套判準遲早會給出相反的答案。
    """
    _tree = ast.parse(_CALC_SRC.read_text(encoding="utf-8"))
    _names = {_a.name for _n in ast.walk(_tree)
              if isinstance(_n, ast.ImportFrom) for _a in _n.names}
    assert "reconcile_dividend_yield" in _names, (
        "沒有 import §4.3 的對帳器 —— 那代表判定是自己寫的。")
    # 行為面：對得上 / 差很多 兩個方向都要真的分得出來。
    _agree = estimate_monthly_income(_FUND(), SENT_AMOUNT, fx_lookup=_fx)
    assert _agree["income_reconcile"]["agree"] is True, _agree["income_reconcile"]
    _off = estimate_monthly_income(
        _FUND(moneydj_div_yield=SENT_ADR * 3), SENT_AMOUNT, fx_lookup=_fx)
    assert _off["income_reconcile"]["agree"] is False, _off["income_reconcile"]


def test_the_estimate_path_is_labelled_estimate_not_records():
    """沒有逐筆記錄、只有配息率 → `source` 必須是 `estimate`。

    兩者對使用者是**行為上的差別**：真實記錄推的數字，季配基金有 11 個月是 0；
    年化攤平推的數字，**每個月都不會真的長這樣**。標錯就等於把平均值講成實配。
    """
    _f = estimate_monthly_income(_FUND(dividends=[]), SENT_AMOUNT, fx_lookup=_fx)
    assert _f["income_basis"] == BASIS_ESTIMATE
    assert _f["latest_div_per_unit"] is None


# ══════════════════════════════════════════════════════════════════
# 畫面層｜一句結論、公式收在 expander、灰不是紅
# ══════════════════════════════════════════════════════════════════

def _RICH_WITH_NAV(**over) -> dict:
    """骨架守衛那份 `_RICH_RESULT` **加上淨值與配息率** —— 它原本沒有這兩個。

    ⚠️ 刻意在這裡加，而不是去改 `_RICH_RESULT` 本身：那一份是**別的斷言的
    共用 fixture**，動它等於同時改掉一整批測試看到的畫面。
    """
    _r = _RICH_RESULT()
    _r["metrics"]["nav"] = SENT_NAV
    _r["moneydj_div_yield"] = SENT_ADR
    _r["dividends"] = [{"date": "2026/08/15", "amount": SENT_DIV, "currency": "USD"}]
    _r.update(over)
    return _r


def _invest_body(**kw) -> str:
    _seg = _segments(_render(applied=FAKE_QUERY, selected=SELECTED_CODE, **kw))
    return "\n".join(_seg.get(DEEP_DIVE_INVEST, []))


def test_the_block_only_exists_after_a_fund_is_selected():
    """沒選定一檔 → 這一塊**根本不畫**（它住在深度區的 gate 後面）。"""
    _seg = _segments(_render(applied=FAKE_QUERY))
    assert DEEP_DIVE_INVEST not in _seg, (
        f"還沒選定就畫出了「{DEEP_DIVE_INVEST}」—— 線框的「選定後展開」gate 破了。")


def test_the_headline_answers_the_question_in_one_line():
    """⭐ 一句話回答「我投 X 元，每個月大概領多少」——**金額、單位數、月配息三個都要在**。"""
    _body = _invest_body(result=_RICH_WITH_NAV(), fx=SENT_FX)
    _units = (float(DEFAULT_AMOUNT_TWD) / SENT_FX) / SENT_NAV
    _monthly = SENT_DIV * _units * SENT_FX
    for _need in (f"{DEFAULT_AMOUNT_TWD:,.0f}", f"{_units:,.2f}", f"{_monthly:,.0f}"):
        assert _need in _body, f"結論句少了 {_need!r}：\n{_body}"


def test_the_formula_is_folded_away_but_every_conclusion_is_not():
    """公式收進 expander（客戶這次核准）；**結論與比較對象一律留在外面**。

    ⛔ 客戶 2026-06-25 已否決「新手模式／把東西藏起來」，原則是
    「所有資訊一律展開，不藏」。**藏起來的只有推導過程**，不是任何一個結論。
    """
    _parts = _segments(
        _render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                result=_RICH_WITH_NAV(), fx=SENT_FX)).get(DEEP_DIVE_INVEST, [])
    _exp = [_i for _i, _p in enumerate(_parts) if _p.startswith("[expander] ")]
    assert _exp, f"算式沒有被收進 expander：\n{_parts}"
    _code = [_i for _i, _p in enumerate(_parts) if _p.startswith("[code] ")]
    assert _code and min(_code) > _exp[0], (
        f"算式沒有排在 expander 之後（＝沒有真的收起來）：\n{_parts}")
    # 結論句與比較對象**在 expander 之前**。
    _head = [_i for _i, _p in enumerate(_parts) if _p.startswith("[markdown] 投入 ")]
    assert _head and _head[0] < _exp[0], (
        f"結論句跑到 expander 裡面去了（＝被藏起來了）：\n{_parts}")


@pytest.mark.parametrize("kw", [
    dict(result=_RICH_RESULT()),                                   # 沒有淨值
    dict(result=_RICH_WITH_NAV(), fx=None),                        # 匯率查不到
    dict(result=_RICH_WITH_NAV(currency=""), fx=SENT_FX),          # 幣別不明
    dict(result=_RICH_WITH_NAV(dividends=[], moneydj_div_yield=None), fx=SENT_FX),
    dict(result=_RICH_WITH_NAV(currency="TWD"), fx=SENT_FX),       # 幣別對不上
])
def test_a_calculation_that_cannot_run_is_grey_and_never_red(kw):
    """算不出來 ＝ **前提不足（灰）**，不是**系統出錯（紅）**（鐵則 03）。"""
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE, **kw)
    _reds = [_p for _p in _parts if _p.startswith("[error]")]
    assert not _reds, f"算不出來被塗成紅色：{_reds}"
    _body = "\n".join(_segments(_parts).get(DEEP_DIVE_INVEST, []))
    assert NOT_READY_MARK in _body, f"算不出來卻不是灰的：\n{_body}"


def test_each_reason_says_something_different():
    """六種算不出來的處境，**六句不一樣的話**。

    ⛔ 共用一句「資料不足」等於對使用者說謊 —— 他們的下一步完全不同
    （改金額／換一檔／等一下再按／去看配息表）。
    """
    _notes = list(_INVEST_BLOCKED_NOTES.values())
    assert len(_notes) == len(set(_notes)), (
        f"有兩種原因共用同一句話：{sorted(_notes)}")
    assert set(_INVEST_BLOCKED_NOTES) == {
        NO_AMOUNT, NO_CURRENCY, NO_NAV, NO_FX, CCY_CONFLICT, NO_INCOME_BASIS}, (
        "文案表與算式層的原因代碼對不上 —— 會有一種處境印出「拿不到原因」。")


def test_a_currency_clash_still_shows_the_units_it_can_compute():
    """幣別對不上時：**單位數照樣印出來**，只有月配息那一段留白。

    ⛔ 這一條擋的是「一個缺料就整塊放棄」——那會讓使用者連「這筆錢買得到多少」
    都看不到，而那一半其實是完全誠實可用的。
    """
    _body = _invest_body(result=_RICH_WITH_NAV(currency="TWD"), fx=SENT_FX)
    assert f"{DEFAULT_AMOUNT_TWD / SENT_NAV:,.2f}" in _body, (
        f"幣別對不上就連單位數都不給了：\n{_body}")
    assert NOT_READY_MARK in _body and "TWD" in _body and "USD" in _body, (
        f"沒有把兩邊各自宣告的幣別講出來：\n{_body}")


def test_the_pointer_for_a_missing_amount_is_the_amount_box():
    """⭐ 「金額沒填」的指路指到**它自己的金額欄位**，而那個欄位在畫面上真的存在。

    ⚠️ 這一層（指路指到的東西真的在畫面上）通常沒有人守 ——
    `CLAUDE.md §8.3.P` 的 `P-WHERECONTENT-1` 就是登記這個缺口的。
    """
    _where = _invest_where()
    assert _LABEL_INVEST_AMOUNT in _where, f"指路沒有指到金額欄位：{_where}"
    assert DEEP_DIVE_INVEST in _where, f"指路沒有講在哪一塊：{_where}"
    _body = _invest_body(result=_RICH_WITH_NAV(), fx=SENT_FX)
    assert f"[number_input] {_LABEL_INVEST_AMOUNT}" in _body, (
        f"指路指到一個畫面上沒有的欄位：\n{_body}")


def test_nothing_reaches_for_a_rate_before_the_numbers_are_there():
    """⭐ 淨值還沒有 → **匯率一次都不去查**（算不出來的東西不值得一次網路往返）。

    ⚠️ 這條驗的是**呼叫次數**，不是畫面上有沒有字 —— 只驗畫面的話，
    把查詢留著、只是不顯示，照樣會全綠（同深度區那個 gate 的守法）。
    """
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_RICH_RESULT())
    assert not [_p for _p in _parts if _p.startswith("[fx]")], (
        "沒有淨值卻還是去查了匯率：\n" + "\n".join(_parts))
    # 正對照：有淨值的時候**真的**會去查（否則上面那條是對空氣生效）。
    _ok = _render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                  result=_RICH_WITH_NAV(), fx=SENT_FX)
    assert [_p for _p in _ok if _p.startswith("[fx]")], (
        "有淨值卻沒去查匯率 —— 那上面那條斷言是對空氣生效的。")


def test_a_twd_fund_never_reaches_for_a_rate_on_screen_either():
    """台幣計價的基金，整條渲染路徑**一次匯率都不查**。"""
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                     result=_RICH_WITH_NAV(
                         currency="TWD",
                         dividends=[{"date": "2026/08/15", "amount": SENT_DIV,
                                     "currency": "TWD"}]))
    assert not [_p for _p in _parts if _p.startswith("[fx]")], (
        "台幣基金也去查了匯率：\n" + "\n".join(_parts))


def test_the_amount_is_only_remembered_when_the_form_is_submitted():
    """鐵則 02：**按了「試算」才算數**，打字的當下不寫 session。"""
    _tree = ast.parse(_PAGE.read_text(encoding="utf-8"))
    _fn = next(_n for _n in ast.walk(_tree)
               if isinstance(_n, ast.FunctionDef) and _n.name == "_render_invest_calc")
    _writes = [_n for _n in ast.walk(_fn)
               if isinstance(_n, ast.Assign)
               and any(isinstance(_t, ast.Subscript)
                       and "session_state" in ast.unparse(_t) for _t in _n.targets)]
    assert _writes, "投資試算沒有把送出的金額寫回 session —— 那它就沒有 form 可言。"
    _gate_ifs = [_n for _n in ast.walk(_fn) if isinstance(_n, ast.If)]
    _guarded = {id(_w) for _i in _gate_ifs for _w in ast.walk(_i)
                if isinstance(_w, ast.Assign)}
    _naked = [ast.unparse(_w)[:70] for _w in _writes if id(_w) not in _guarded]
    assert not _naked, f"session 寫入沒有被送出閘門包住：{_naked}"

    # 行為面：沒按送出 → session 裡不該多出那個鍵。
    _out: dict = {}
    _render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_RICH_WITH_NAV(),
            fx=SENT_FX, state_out=_out)
    assert _SK_INVEST_AMOUNT not in _out, (
        f"沒按「{INVEST_SUBMIT_LABEL}」就把金額寫進 session 了：{_out.get(_SK_INVEST_AMOUNT)!r}")


def test_the_no_amount_branch_is_unreachable_from_this_screen_today():
    """⭐ **據實釘住一個「今天印不出來」的分支** —— 不是守它有效，是守它的**狀態**。

    ## 為什麼要有這一條

    `CLAUDE.md §-2` 記著一個真的發生過的事故：commit message 宣稱「順帶修掉」某個
    缺資料偵測，**實測在 production 路徑永遠不會觸發**。本批有一個同型的東西：
    :data:`NO_AMOUNT` 的文案與指路都寫好了，但**這個畫面產不出那個狀態** ——
    :func:`_applied_amount` 拿不到正數就退 :data:`DEFAULT_AMOUNT_TWD`，
    加上金額 widget 自己的 `min_value`，送進算式的金額**結構上不可能 ≤ 0**。

    **留著它是刻意的**（理由寫在 :data:`_INVEST_BLOCKED_NOTES` 的 `NO_AMOUNT` 上方）；
    **本條要防的是「它悄悄變成可達、卻沒有人回頭看那段說明」**。

    ## 這條測的是什麼（別讀成「金額驗證有在守」）

    它斷言的是**現況**：任何塞進 session 的髒值，`_applied_amount()` 都回正的 float。
    ⛔ **它不保證金額驗證是對的** —— 算式層那一半由
    :func:`test_every_kind_of_missing_input_gets_its_own_reason_and_zero_numbers` 驗。

    **一旦有人拿掉預設值，本條會轉紅** —— 那時候正解是回去讀那段說明、
    確認灰態與指路真的走得通，**不是**把這條刪掉。
    """
    import ui.views.page_03_research as _P

    _MISSING = object()
    _dirty = (_MISSING, None, 0, 0.0, -1, "", "  ", "abc", "0", float("nan"),
              [], {}, True, False, 1e-9)

    class _FakeSt:
        def __init__(self, value):
            self.session_state = ({} if value is _MISSING
                                  else {_SK_INVEST_AMOUNT: value})

    _real_st = _P.st
    _bad = []
    try:
        for _v in _dirty:
            _P.st = _FakeSt(_v)
            try:
                _got = _P._applied_amount()
            except Exception as _err:  # noqa: BLE001 —— 拋例外也算「狀態變了」
                _bad.append((_v, f"raised {type(_err).__name__}"))
                continue
            if not (isinstance(_got, float) and _got > 0):
                _bad.append((_v, _got))
    finally:
        _P.st = _real_st

    assert not _bad, (
        f"`_applied_amount()` 現在會吐出非正數（或拋例外）：{_bad}\n"
        "⇒ `NO_AMOUNT` 那條灰態**變成可達的**了。\n"
        "這不一定是壞事 —— 但請回去讀 `_INVEST_BLOCKED_NOTES[NO_AMOUNT]` 上方那段說明，"
        "確認它的文案與指路真的走得通，再決定要不要改本條。**不要直接刪掉本條。**")
    # 正對照：算式層**真的**有那個分支（否則上面那句「留著它是刻意的」是空話）。
    assert estimate_monthly_income(_FUND(), 0, fx_lookup=_fx)["units_blocked"] == NO_AMOUNT


def test_the_form_and_the_widget_live_in_this_pages_namespace():
    """新舊 ③ 同時渲染 —— key 撞上就是整個 App 當場崩潰，所以前綴是結構性保證。"""
    for _k in (_INVEST_FORM_KEY, _INVEST_AMOUNT_KEY, _SK_INVEST_AMOUNT):
        assert _k.startswith("v03_"), f"`{_k}` 不在 ⑧ 的命名空間裡。"


#: 客戶三次抱怨點名的**內部語言**。⛔ 畫面上只准有「使用者的處境」。
#: ⚠️ `線框` / `拍板` 刻意也收 —— 它們是**我們**的流程詞，使用者不知道那是什麼。
_INTERNAL_WORDS: tuple[str, ...] = (
    "上游", "取數", "source_trace", "wb01", "§", "線框", "拍板", "灰態", "血緣",
)


def test_this_block_never_speaks_our_internal_language():
    """⭐ 客戶的硬規則：**畫面上只准有使用者的處境，不准有我們的進度**。

    ⚠️ **射程只有這一塊**（本批的檔案邊界）—— 全頁其餘各處還有幾處同類用字，
    已在 PR 描述具名登記交總管另行派工。**不要**把本條讀成「整頁已經清乾淨」。
    """
    _bodies = [
        _invest_body(result=_RICH_WITH_NAV(), fx=SENT_FX),
        _invest_body(result=_RICH_WITH_NAV(), fx=None),
        _invest_body(result=_RICH_RESULT()),
        _invest_body(result=_RICH_WITH_NAV(currency="TWD"), fx=SENT_FX),
        _invest_body(result=_RICH_WITH_NAV(dividends=[], moneydj_div_yield=None),
                     fx=SENT_FX),
    ]
    _hits = sorted({_w for _b in _bodies for _w in _INTERNAL_WORDS if _w in _b})
    assert not _hits, (
        f"投資試算的畫面上出現了內部語言：{_hits}\n"
        "客戶原話：少了很多資訊、看不懂 —— 這幾個詞是我們的流程詞，不是他的處境。\n"
        + "\n\n".join(_bodies))


def test_the_estimate_path_never_claims_to_have_been_double_checked():
    """⭐ 年化攤平那條路，**兩個數字同源**，畫面不得把「一樣」講成「驗證通過」。

    月配 ＝ 掛牌配息率 ÷ 12 ⇒ 反推回去的年化比率必然等於它。
    把這種恆等式講成「對得上，推算站得住」，是造一個**假的第二意見**（§1）。
    """
    _body = _invest_body(result=_RICH_WITH_NAV(dividends=[]), fx=SENT_FX)
    assert "同一個來源" in _body and "不能拿來當第二個驗證" in _body, (
        f"年化攤平那條路把同源的兩個數字講成互相驗證：\n{_body}")
    assert "推算站得住" not in _body, (
        f"年化攤平那條路印出了「站得住」這種驗證用語：\n{_body}")


# ══════════════════════════════════════════════════════════════════
# ⭐ 突變測試 —— **把修復拔掉，上面的守衛必須真的轉紅**
#
# 憲法 §-1.5 v3 `03`-1：「突變測試（拔掉修復邏輯必須轉為紅燈）」。
# 做法：在同一個 process 裡把**合作者**換成「沒有那道防線」的版本，
# 然後斷言對應的那條測試**拋 AssertionError**。
#
# ⚠️ **突變的是合作者，不是被測函式自己** —— 直接改被測函式的原始碼在
#    process 內做不到，而「改了原始碼再跑一次」在 CI 上不可重現。
#    合作者替換能達到同樣的效果：那道防線的**判斷依據**被抽掉了。
# ══════════════════════════════════════════════════════════════════

def test_removing_the_currency_clash_guard_turns_the_guard_red():
    """突變①：讓幣別判定永遠回「一致」（＝拔掉那道閘門）→ 對應守衛必須紅。"""
    _real = CALC.nav_currency_verdict
    CALC.nav_currency_verdict = lambda _a, _b: "match"
    try:
        with pytest.raises(AssertionError):
            test_a_currency_clash_never_gets_converted()
    finally:
        CALC.nav_currency_verdict = _real
    # 還原之後必須回到綠 —— 否則上面那個 `raises` 可能是別的原因造成的。
    test_a_currency_clash_never_gets_converted()


def test_fabricating_a_payout_rate_turns_the_blank_guard_red():
    """突變②：配息率查不到時**編一個 6%**（§1 明禁）→ 對應守衛必須紅。"""
    _real = CALC._resolve_adr_with_fallback
    CALC._resolve_adr_with_fallback = lambda _fund: (6.0, "編的")
    try:
        with pytest.raises(AssertionError):
            test_a_missing_payout_rate_is_left_blank_not_zeroed()
    finally:
        CALC._resolve_adr_with_fallback = _real
    test_a_missing_payout_rate_is_left_blank_not_zeroed()


def test_pretending_a_missing_rate_is_one_turns_the_rate_guard_red():
    """突變③：匯率查不到時**當成 1.0**（＝舊 ③ 那個事故）→ 對應守衛必須紅。

    這裡換掉的是傳進去的 `fx_lookup` —— 它就是「拿不到匯率時怎麼辦」的那個決定點。
    """
    def _pretend(_ccy, **_kw):
        return 1.0

    _f = estimate_monthly_income(_FUND(), SENT_AMOUNT, fx_lookup=_pretend)
    assert _f["units"] is not None, (
        "連『把匯率當 1』都算不出東西 —— 那上面那條守衛在對空氣生效。")
    assert math.isclose(_f["units"], SENT_AMOUNT / SENT_NAV, rel_tol=1e-9), (
        "突變版沒有產生『台幣金額當原幣』那個錯誤數字，這個突變沒有咬到東西。")
    # 正確版必須拒絕算。
    assert estimate_monthly_income(_FUND(), SENT_AMOUNT,
                                   fx_lookup=_no_fx)["units"] is None


def test_reusing_one_sentence_for_every_reason_turns_the_copy_guard_red():
    """突變④：六種原因共用同一句話 → 「每種處境一句話」那條守衛必須紅。"""
    _real = dict(_INVEST_BLOCKED_NOTES)
    try:
        for _k in _INVEST_BLOCKED_NOTES:
            _INVEST_BLOCKED_NOTES[_k] = "資料不足"
        with pytest.raises(AssertionError):
            test_each_reason_says_something_different()
    finally:
        _INVEST_BLOCKED_NOTES.clear()
        _INVEST_BLOCKED_NOTES.update(_real)
    test_each_reason_says_something_different()


# ══════════════════════════════════════════════════════════════════
# ⭐ 2026-09-08 回修｜B1 幣別：**比對用**與**查匯率用**是兩個命名空間
#
# 事故（獨立稽核抓到，本組實測復現）：`fund_currency` 走 ``mode="yf"``
# （人民幣 → **CNH**）、`dividend_currency` 走 L0 `normalize_iso_ccy`
# （**CNY 原樣**），兩個值被丟進同一個比對器 → 一檔人民幣基金、配息紀錄還誠實
# 標了 `CNY`，畫面卻說「兩邊對不上」，並印出使用者從沒見過的 `CNH`；
# 同一個畫面的配息表底下同時寫著「全部以 CNY 計價」。**兩句都是本頁印的。**
#
# ⚠️ **本組刻意不寫「人民幣不得被誤判」這種單點測試** —— 那只釘住今天這一個症狀。
#    病灶是「同一件事被兩個正規化器算了兩次」，下一個雙代碼幣別會再犯一次。
#    故下列守衛一律**從 `services.currency.CCY_NORMALIZE` 自己長出案例**。
# ══════════════════════════════════════════════════════════════════

#: 全 repo 認得的**每一種**幣別寫法（別名 ＋ 別名指向的 ISO 碼 ＋ yf 覆寫碼）。
#: ⛔ **不手寫清單**：手寫的只涵蓋今天想得到的幣別，而這個 bug 的形狀正是
#: 「**下一個**雙代碼幣別」。字表一旦擴充，這些守衛自動跟著擴。
_ALL_CCY_WRITINGS: tuple[str, ...] = tuple(sorted(
    set(CCY_NORMALIZE) | set(CCY_NORMALIZE.values())
    | set(_CCY_YF_OVERRIDES) | set(_CCY_YF_OVERRIDES.values())))


@pytest.mark.parametrize("written", _ALL_CCY_WRITINGS)
def test_both_sides_of_the_currency_check_speak_the_same_language(written):
    """⭐ **這是 B1 的機制測試** —— 同一個宣告，兩邊必須收成同一個字。

    幣別比對只有在**兩邊用同一個正規化器**時才有意義。只要哪一邊自己走一套，
    「同一種幣的兩種寫法」就會被判成衝突 —— 那正是 2026-09-08 修掉的那個 bug。

    ⚠️ 這一條**不看任何特定幣別**，所以它擋的是**整個類別**，
    不是「人民幣」這一個症狀。
    """
    _fund = fund_currency({"currency": written})
    _div = dividend_currency({"dividends": [{"currency": written}]})
    assert _fund == _div, (
        f"同一個幣別宣告 {written!r}，基金側收成 {_fund!r}、配息側收成 {_div!r} —— "
        "兩邊落在不同的命名空間，比對器會把同一種幣判成衝突。\n"
        "⛔ 兩邊都必須走 `services.fund_invest_calc.comparable_ccy`。")


@pytest.mark.parametrize("written", _ALL_CCY_WRITINGS)
def test_the_same_currency_written_two_ways_is_never_a_clash(written):
    """同一種幣的**任意兩種寫法**配起來，都不得被判成「幣別對不上」。

    端到端走 :func:`estimate_monthly_income`，而不是只比兩個字串 ——
    使用者受害的是**那一整段被關掉**，不是那兩個字串。
    """
    _canon = comparable_ccy(written)
    if not _canon:                     # 認不得的寫法 → 本條不適用（那是 NO_CURRENCY 的射程）
        return
    for _other in _ALL_CCY_WRITINGS:
        if comparable_ccy(_other) != _canon:
            continue
        _f = estimate_monthly_income(
            _FUND(currency=written,
                  dividends=[{"date": "2026/08/15", "amount": SENT_DIV,
                              "currency": _other}]),
            SENT_AMOUNT, fx_lookup=_fx)
        assert _f["income_blocked"] != CCY_CONFLICT, (
            f"基金宣告 {written!r}、配息宣告 {_other!r} —— **同一種幣**（都是 "
            f"{_canon}），卻被判成幣別衝突，每月配息整段被關掉。\n"
            f"畫面會印：{_INVEST_BLOCKED_NOTES[CCY_CONFLICT]}")


@pytest.mark.parametrize("fund_ccy, div_ccy", [
    ("TWD", "USD"),          # ⭐ 客戶點名的那一條（既有守衛的案例，不得被放寬）
    ("USD", "TWD"),
    ("CNY", "USD"),
    ("USD", "人民幣"),        # 中文宣告過了 L2 之後**才**看得見的真衝突
    ("HKD", "CNY"),
])
def test_a_real_currency_clash_is_still_blocked(fund_ccy, div_ccy):
    """⛔ **反面守衛**：為了讓人民幣過關而把比對器變成永不擋，是另一種違憲。

    §4.1 量綱：把美元的「最近一筆實配」當成台幣乘上匯率，畫面會印出一個
    **看起來完全正常、實際差三十倍**的月配息金額。
    """
    _f = estimate_monthly_income(
        _FUND(currency=fund_ccy,
              dividends=[{"date": "2026/08/15", "amount": SENT_DIV,
                          "currency": div_ccy}]),
        SENT_AMOUNT, fx_lookup=_fx)
    assert _f["income_blocked"] == CCY_CONFLICT, (
        f"基金 {fund_ccy!r} vs 配息 {div_ccy!r} 是**真的**幣別衝突，必須擋住 —— "
        f"實際卻是 {_f['income_blocked']!r}，月配 {_f['monthly_twd']!r}。")
    assert _f["monthly_twd"] is None
    assert _f["units_blocked"] == "", "衝突只該擋住配息那一半，單位數仍然算得出來。"


@pytest.mark.parametrize("iso, yf_code", sorted(_CCY_YF_OVERRIDES.items()))
def test_the_screen_never_shows_a_rate_lookup_only_code(iso, yf_code):
    """⛔ **拿去打 API 的代碼不准印到畫面上。**

    `fund_currency` 的回傳值會被印進**算式區**（「原幣金額 … CNH」）、
    **配息說明**（「最近一筆實際配息 … CNH／單位」）與**灰態理由**。
    `CNH` 這個代碼基金公司沒用過、使用者在本頁其他地方也沒看過。
    """
    for _written in (iso, yf_code):
        _got = fund_currency({"currency": _written})
        assert _got != yf_code, (
            f"宣告 {_written!r} → 畫面會印出 {_got!r}，那是 yfinance 的報價代碼，"
            f"不是使用者認得的計價幣別。\n"
            f"⛔ 查匯率用 {yf_code!r} 是對的，但那件事屬於 `fx_rate_to_twd`。")


def test_the_rate_lookup_still_asks_for_the_yf_code(monkeypatch):
    """⭐ **反面守衛**：修 B1 不得把「查匯率用 yf 代碼」一起改掉。

    `CNHTWD=X` 在 yfinance 比 `CNYTWD=X` 可靠（`services/currency.py` 就地寫明），
    那半邊**必須原封保留**在 :func:`fx_rate_to_twd`。
    """
    import services.fund_service as _FS
    _asked: list[str] = []

    def _spy(_pair):
        _asked.append(_pair)
        return SENT_FX

    monkeypatch.setattr(_FS, "get_latest_fx", _spy)
    for _written in ("CNY", "人民幣", "CNH"):
        _asked.clear()
        assert CALC.fx_rate_to_twd(_written) == SENT_FX
        assert _asked == ["CNHTWD=X"], (
            f"{_written!r} 的匯率查詢變成 {_asked!r} —— "
            "yf 覆寫（人民幣→CNH）被連帶改掉了，那是**對的**那一半。")
    _asked.clear()
    assert CALC.fx_rate_to_twd("TWD") == 1.0
    assert _asked == [], "台幣計價不該打網路。"


def test_the_two_currency_lines_on_one_screen_never_contradict_each_other():
    """⭐ 事故的**畫面級**復現：配息表說「全部以 CNY 計價」、投資試算說「基金是 CNH」。

    ⚠️ 兩句都是本頁印的 —— 這不是上游的鍋，是本頁自己在同一個畫面上自相矛盾。
    `_dividend_caption` 拿的是 `result["currency"]` 原值，投資試算拿的是
    `fund_currency()`；**兩者對「這檔基金是什麼幣」必須給同一個答案**。
    """
    _rows = [{"date": "2026/08/15", "amount": SENT_DIV, "currency": "CNY"}]
    _res = _FUND(currency="CNY", dividends=_rows)
    _caption_side = reconcile_row_currencies([str(_res.get("currency") or "")])
    _invest_side = fund_currency(_res)
    assert _caption_side == _invest_side, (
        f"配息表底下說 {_caption_side!r}、投資試算說 {_invest_side!r} —— "
        "同一個畫面、同一檔基金，兩句互相矛盾（§1）。")
    assert estimate_monthly_income(_res, SENT_AMOUNT,
                                   fx_lookup=_fx)["income_blocked"] != CCY_CONFLICT


# ══════════════════════════════════════════════════════════════════
# ⭐ 2026-09-08 回修｜B2 「掛牌的年化配息率」有兩條 fallback 其實是本地自算的
#
# 事故：`_invest_compare` **無條件**寫「對照這一檔**掛牌的**年化配息率」，
# 而 `adr_pct` 有三層 fallback，**只有第一層是掛牌值**。實測一檔只有 3 個月
# 配息紀錄的基金：畫面把**自己算的 1.44%** 講成「掛牌的」，還把差異原因講成
# 「最近一筆配息不是常態」—— 而那三筆配息**金額完全相同**，
# 真因是那個 12 個月的分母裡只裝了 3 個月。
# ══════════════════════════════════════════════════════════════════

def _recent_divs(n: int, amount: float = SENT_DIV) -> list[dict]:
    """`n` 筆**落在近一年內**的月配紀錄（金額全部相同 → 排除「配息不規律」這個解釋）。

    ⚠️ 日期**動態算**，不寫死 —— 寫死的日期會在一年後滑出 12 個月窗，
    屆時這幾條測試會**無聲地改測別的東西**（`divs_12m_sum` 那層會退成 `None`）。
    """
    import datetime as _dt
    _today = _dt.date.today()
    return [{"date": (_today - _dt.timedelta(days=30 * (_i + 1))).strftime("%Y/%m/%d"),
             "amount": amount} for _i in range(n)]


@pytest.mark.parametrize("fund, want", [
    ({"moneydj_div_yield": SENT_ADR, "metrics": {"nav": SENT_NAV}}, ADR_OFFICIAL),
    ({"metrics": {"nav": SENT_NAV, "annual_div_rate": SENT_ADR}}, ADR_LOCAL_RATE),
    ({"metrics": {"nav": SENT_NAV}, "dividends": _recent_divs(3)}, ADR_FROM_RECORDS),
])
def test_the_payout_rate_source_labels_match_the_resolver(fund, want):
    """本檔那三個常數，必須**真的**是上游那支 resolver 回傳的字。

    ⛔ 兩邊各自寫死字面值的話，上游改字時**畫面會靜靜退回講官方話** ——
    而那正是 B2 的形狀：一個自算值被講成掛牌值。
    """
    assert _resolve_adr_with_fallback(fund)[1] == want, (
        f"`_resolve_adr_with_fallback` 對 {fund!r} 回的來源標籤不是 {want!r} —— "
        "本檔（與畫面）分辨『這個數字是不是掛牌的』就是靠它。")


def _compare_facts(**over) -> dict:
    """`_invest_compare` 讀得到的最小事實集。**只放它真的會讀的鍵。**"""
    _f = {"annual_twd": 57_600.0, "implied_annual_pct": 5.76,
          "adr_pct": SENT_ADR, "adr_source": ADR_OFFICIAL,
          "income_basis": BASIS_RECORDS, "income_reconcile": {"agree": True}}
    _f.update(over)
    return _f


@pytest.mark.parametrize("src", [ADR_OFFICIAL, ADR_LOCAL_RATE, ADR_FROM_RECORDS,
                                 "某個上游日後才新增的來源"])
def test_only_the_official_rate_is_ever_called_listed(src):
    """⭐ **只有** :data:`ADR_OFFICIAL` 那一層可以被稱為「掛牌」。

    最後一個參數是 **fail-safe**：上游多一層 fallback 時，畫面必須退成**保守**講法，
    **不得**擅自把一個不認得的來源升格成官方值。
    """
    _line = _invest_compare(_compare_facts(adr_source=src))
    assert (_ADR_SOURCE_LABELS[ADR_OFFICIAL] in _line) == (src == ADR_OFFICIAL), (
        f"來源 {src!r} 的比較句用了「掛牌」那一套說法：\n{_line}\n"
        "⛔ 把『我自己算的』講成『官方公布的』，是 §1「錯誤的數字比沒有數字更危險」"
        "最貴的一種。")


@pytest.mark.parametrize("src", [ADR_LOCAL_RATE, ADR_FROM_RECORDS])
def test_a_locally_derived_rate_is_never_sold_as_a_second_opinion(src):
    """⭐ 配息率也是本地推的時候，`agree` **不是**獨立驗證 —— 不得講成「站得住」。

    本頁對**年化攤平**那條路早就有這條規矩（「兩個數字是同一個來源推出來的…
    不能拿來當第二個驗證」）。這兩層 fallback 是**同一個病**：
    對照值與月配都出自**同一批配息紀錄**。原本卻走到了
    「兩個數字對得上 —— 這個推算站得住」，那是一個**假的第二意見**。
    """
    _line = _invest_compare(_compare_facts(adr_source=src,
                                           income_reconcile={"agree": True}))
    assert "互相獨立的驗證" in _line, (
        f"來源 {src!r} 沒有說出「這不是獨立驗證」：\n{_line}")
    assert "站得住" not in _line, (
        f"來源 {src!r} 把同源的兩個數字講成互相驗證：\n{_line}")


def test_an_incomplete_year_of_records_is_not_blamed_on_an_unusual_payout():
    """⭐ **稽核抓到的那一句**：差很多的原因被講成「最近一筆配息不是常態」。

    真因是 :data:`ADR_FROM_RECORDS` 那層拿**近 12 個月**加總當分子、
    卻只有幾個月的紀錄 ⇒ 對照值**系統性偏低**。
    ⚠️ 本例三筆配息**金額完全相同**，「不是常態」這個解釋在此**可證為假**。
    """
    _f = estimate_monthly_income(
        _FUND(currency="TWD", moneydj_div_yield=None,
              metrics={"nav": SENT_NAV}, dividends=_recent_divs(3)),
        SENT_AMOUNT, fx_lookup=_explodes)
    assert _f["adr_source"] == ADR_FROM_RECORDS, _f
    assert _f["income_basis"] == BASIS_RECORDS, _f
    _line = _invest_compare(_f)
    assert "不滿一年" in _line, (
        f"沒有說出真正的原因（紀錄不滿一年）：\n{_line}")
    assert "不是常態" not in _line, (
        f"把「紀錄不滿一年」誤診成「最近一筆配息不是常態」：\n{_line}\n"
        "三筆配息金額完全相同 —— 這個解釋在本例可證為假。")


def test_the_no_rate_sentence_does_not_pretend_only_the_listed_one_is_missing():
    """`adr_pct is None` ＝ **三層全敗**，不是「只有掛牌值沒有」。"""
    _line = _invest_compare(_compare_facts(adr_pct=None))
    assert "沒有任何" in _line, _line


# ══════════════════════════════════════════════════════════════════
# ⭐ 2026-09-08 回修｜B3 全敗時，第六格是唯一不吃共用文案的一格
#
# `_has_anything()` 的 docstring 已經把規矩寫死：「全敗才用共用文案；
# 只要有任何一格有料，其餘空格一律講**自己**的原因。」前五格都照做，
# 第六格**沒有拿到 `_blank`** → 前五格說「在 2 個來源都沒有取到淨值」、
# 第六格說「查不到這一檔是用哪一種幣別計價的」。**同一個原因，兩種故事。**
# ══════════════════════════════════════════════════════════════════

#: 全敗時的共用哨兵句（內容不重要，**是不是同一句**才是重點）。
_SHARED_BLANK: str = "「這是深度區全敗時六格共用的那一句」"


@pytest.mark.parametrize("reason", [NO_CURRENCY, NO_NAV, NO_FX,
                                    CCY_CONFLICT, NO_INCOME_BASIS])
def test_when_nothing_came_back_the_sixth_cell_says_what_the_other_five_say(reason):
    """全敗時，**資料類**的原因一律改說共用那一句 —— 與其餘五格逐字相同。"""
    assert _invest_note_for(reason, {}, _SHARED_BLANK) == _SHARED_BLANK, (
        f"原因 {reason!r} 在全敗時沒有改口說共用那一句 —— "
        "六格會對同一個原因講出兩種故事。")


def test_a_missing_amount_is_never_blamed_on_the_data_sources():
    """⛔ **反面守衛**：「金額沒填」是使用者自己的輸入，跟這次抓到什麼無關。

    對它說「在 N 個來源都沒有取到淨值」一樣是假話。這條線與
    :func:`_invest_where_for` 的兩路分法**刻意用同一個判準**。
    """
    _note = _invest_note_for(NO_AMOUNT, {}, _SHARED_BLANK)
    assert _note != _SHARED_BLANK, (
        "「金額沒填」被歸咎到資料來源身上 —— 那是一句假話。")
    assert _note == _INVEST_BLOCKED_NOTES[NO_AMOUNT]


@pytest.mark.parametrize("reason", [NO_CURRENCY, NO_AMOUNT, NO_NAV])
def test_without_a_shared_note_every_reason_still_speaks_for_itself(reason):
    """⛔ **反面守衛**：沒全敗（`blank == ""`）時，一律講**自己**的原因。

    這是 :func:`_has_anything` 記載那個病的**原始方向** —— 共用文案跑進
    不屬於它的格子。兩個方向都要擋。
    """
    assert _invest_note_for(reason, {}, "") == _INVEST_BLOCKED_NOTES[reason]


def test_the_sixth_cell_is_wired_to_the_same_shared_note_as_the_other_five():
    """⭐ **接線守衛**：production 呼叫點必須真的把 `_blank` 傳進去。

    ⚠️ 上面那幾條驗的是「拿到 `blank` 之後會不會用」，**不是**「有沒有拿到」。
    把參數從呼叫點刪掉，它們**全部照樣綠** —— 那正是 B3 的形狀：
    邏輯是對的，**只是沒有接線**（同 `adr_source` 那個病：算了但沒人讀）。
    """
    _calls = [_n for _n in ast.walk(ast.parse(_PAGE.read_text(encoding="utf-8")))
              if isinstance(_n, ast.Call)
              and getattr(_n.func, "id", "") == "_render_invest_calc"]
    assert _calls, "找不到 `_render_invest_calc` 的呼叫點 —— 這一塊被拔掉了？"
    for _c in _calls:
        assert len(_c.args) + len(_c.keywords) >= 2, (
            f"`_render_invest_calc` 只被傳了 {len(_c.args)} 個位置引數 —— "
            "深度區的共用全敗文案沒有接進第六格，全敗時它會自己講一套。")


# ══════════════════════════════════════════════════════════════════
# ⭐ 2026-09-08 回修｜X4 對帳的**單位約定**沒有守衛
#
# `reconcile_dividend_yield` 的 `abs_tol=0.001` 是照**小數**訂的
# （docstring 自陳「容差:絕對 0.1 個百分點」⇒ 0.001 只有在餵小數時才等於 0.1 個百分點）。
#
# ⚠️ **本組自己重推過，結論與 PR 描述原文不同**（詳見 PR 描述的更正）：
#    `math.isclose` 的判定式是 ``|a-b| <= max(rel_tol*max(|a|,|b|), abs_tol)``。
#    **`rel_tol` 是尺度無關的** —— 兩種用法的相對項完全相同（都是 0.05×max）。
#    有尺度的只有 `abs_tol`：餵小數 ⇒ 地板 ＝ **0.1 個百分點**；
#    餵百分點 ⇒ 地板 ＝ **0.001 個百分點**，也就是**嚴 100 倍**，不是鬆。
#    相對項勝出的門檻：餵小數 max>2%、餵百分點 max>0.02% ⇒
#    **配息率 > 2% 時兩種用法判定相同**，≤ 2% 時餵百分點**比較嚴**。
#    ⇒ 守衛必須用一個**低配息率**的案例，否則它殺不掉這顆突變。
# ══════════════════════════════════════════════════════════════════

#: 低配息率哨兵：`implied ≈ 1.00%` / `adr = 1.09%`。
#: 餵小數 → **agree**（差 0.0009 ≤ 地板 0.001）；餵百分點 → **disagree**（差 0.09 > 0.0545）。
#: ⚠️ 這兩個數字是**挑過的**：用 5.75% 那組哨兵，兩種用法都 agree，突變殺不掉。
_LOW_ADR_PCT: float = 1.09
_LOW_DIV: float = SENT_NAV * 1.00 / (12.0 * 100.0)


def test_the_reconciler_is_fed_decimals_not_percentage_points():
    """⭐ 對帳兩邊必須餵**小數**（`x/100`），因為容差是照小數訂的。

    兩道斷言各擋一種改法：**值本身**（有人把 `/100.0` 拿掉）、
    **判定結果**（有人換一個尺度但湊巧值也對）。
    """
    _f = estimate_monthly_income(
        _FUND(currency="TWD", moneydj_div_yield=_LOW_ADR_PCT,
              metrics={"nav": SENT_NAV},
              dividends=[{"date": "2026/08/15", "amount": _LOW_DIV,
                          "currency": "TWD"}]),
        SENT_AMOUNT, fx_lookup=_explodes)
    _rec = _f["income_reconcile"]
    assert _rec is not None, _f
    assert math.isclose(_rec["value_a"], _f["implied_annual_pct"] / 100.0,
                        rel_tol=1e-12), (
        f"對帳吃到的不是小數：value_a={_rec['value_a']!r}、"
        f"implied={_f['implied_annual_pct']!r}（百分點）。\n"
        "⛔ `abs_tol=0.001` 是照小數訂的（＝0.1 個百分點）；餵百分點會讓那個地板"
        "變成 0.001 個百分點，**嚴 100 倍**，低配息率的基金會被誤判成「差很多」。")
    assert math.isclose(_rec["value_b"], _f["adr_pct"] / 100.0, rel_tol=1e-12)
    assert _rec["agree"] is True, (
        f"implied={_f['implied_annual_pct']:.4f}% vs adr={_f['adr_pct']:.4f}% —— "
        "差 0.09 個百分點，照小數的容差（地板 0.1 個百分點）應當算對得上。\n"
        f"實際 {_rec!r}")


# ══════════════════════════════════════════════════════════════════
# ⭐ 2026-09-08 回修｜Y2 「這裡假設同幣別」那句 §1 揭露沒有守衛
#
# 逐筆配息沒標幣別是**常態**，此時算式**假設**它與基金計價同幣別，
# 而那個假設會直接乘上匯率。揭露句原本存在，但**拿掉它沒有任何測試會紅**。
# ══════════════════════════════════════════════════════════════════

def test_an_unlabelled_dividend_currency_is_declared_as_an_assumption_on_screen():
    """⭐ 沒標幣別 → 畫面**必須**把「這裡是假設」講出來，並指名假設成哪一種幣。"""
    _f = estimate_monthly_income(
        _FUND(dividends=[{"date": "2026/08/15", "amount": SENT_DIV}]),
        SENT_AMOUNT, fx_lookup=_fx)
    assert _f["dividend_currency"] == "" and _f["income_basis"] == BASIS_RECORDS, _f
    _note = _invest_basis_note(_f)
    assert "假設" in _note, (
        f"配息紀錄沒標幣別，畫面卻沒有把這個假設講出來：\n{_note}\n"
        "⚠️ 那個假設會**直接乘上匯率** —— 不講出來，使用者無從判斷這個數字可不可信（§1）。")
    assert _f["currency"] in _note, (
        f"揭露句沒有指名假設成哪一種幣：\n{_note}")


def test_a_declared_dividend_currency_does_not_get_the_assumption_sentence():
    """⛔ **反面守衛**：逐筆有標幣別時**不得**多講一句「這裡是假設」。

    沒有這一條，上面那條可以用「無條件永遠印那句話」通過 —— 那會讓
    **真的有標**的基金也被講成「我們猜的」，同樣是不誠實。
    """
    _note = _invest_basis_note(
        estimate_monthly_income(_FUND(), SENT_AMOUNT, fx_lookup=_fx))
    assert "假設" not in _note, (
        f"逐筆已宣告 USD，畫面卻還說「假設」：\n{_note}")


# ══════════════════════════════════════════════════════════════════
# ⭐ 突變測試（2026-09-08 回修這一批）—— **把修復拔掉，上面的守衛必須真的轉紅**
#
# 憲法 §-1.5 v3 `03`-1：「突變測試（拔掉修復邏輯必須轉為紅燈）」。
# 形狀沿用本檔既有那四條：**換掉合作者**，斷言對應守衛拋 `AssertionError`，
# 還原之後**再驗回綠**（否則那個 `raises` 可能是別的原因造成的）。
#
# ⚠️ **一條殺不掉任何突變的測試，等於沒有測試** —— 下面每一顆突變都對應
#    上面某一條具名守衛，不是「跑一遍看看會不會紅」。
# ══════════════════════════════════════════════════════════════════

def test_normalising_only_one_side_of_the_currency_check_turns_the_guard_red():
    """突變①：把 `fund_currency` 還原成**修復前**的 ``mode="yf"`` → B1 守衛必須紅。

    ## ⚠️ 為什麼刻意只換一側（2026-09-08 就地更正，舊表述寫得比事實強）

    ~~兩側一起換回 yf 反而**不會**紅（兩邊仍在同一個命名空間）。~~
    → **有意識的更正，不是漏刪** —— **這句話是假的，本組自己重跑推翻的。**
    實測（真 pytest，兩側一起改回 ``mode="yf"``）：基線 `1 failed, 182 passed`
    → 突變後 `4 failed, 179 passed`，也就是**多出 3 條紅**：
    `test_the_screen_never_shows_a_rate_lookup_only_code[CNY-CNH]`、
    `test_the_two_currency_lines_on_one_screen_never_contradict_each_other`、
    以及本函式自己。

    **成立的版本（範圍收窄到「哪一條守衛」）**：兩側一起換回 yf 時，
    **幣別衝突那一條**（:func:`test_the_same_currency_written_two_ways_is_never_a_clash`）
    確實**不會**紅 —— 因為兩邊仍落在同一個命名空間，不會產生假衝突。
    **但整份守衛不是沒反應**：`CNH` 會被印到畫面上，於是**顯示層那兩條**照樣轉紅。

    **舊表述的用意仍然成立**（要打中「兩側不一致」這個病灶，就必須只換一側，
    否則那條守衛咬不到）；**被權衡掉的是它的射程** —— 它把「某一條守衛不會紅」
    寫成了「不會紅」，而那是一句**可以被一次 pytest 推翻**的全稱句
    （同 `CLAUDE.md §-1.5.1c 判定 2`：能被一條指令推翻的全稱句就不該那樣寫）。
    """
    _real = CALC.fund_currency
    CALC.fund_currency = lambda _r: normalize_ccy(
        (_r or {}).get("currency"), default="", mode="yf")
    try:
        with pytest.raises(AssertionError):
            test_the_same_currency_written_two_ways_is_never_a_clash("人民幣")
    finally:
        CALC.fund_currency = _real
    test_the_same_currency_written_two_ways_is_never_a_clash("人民幣")


def test_skipping_the_alias_pass_on_the_dividend_side_turns_the_clash_guard_red():
    """突變②：把 `dividend_currency` 還原成**修復前**（不先過 L2）→ 真衝突守衛必須紅。

    修復前逐列的中文宣告會被 L0 當成未知（→ 不比對、**照算**）——
    一檔美元基金、逐列卻寫「人民幣」，會靜靜地算下去。
    """
    _real = CALC.dividend_currency
    CALC.dividend_currency = lambda _r: reconcile_row_currencies(
        [_d.get("currency") for _d in ((_r or {}).get("dividends") or [])
         if isinstance(_d, dict)])
    try:
        with pytest.raises(AssertionError):
            test_a_real_currency_clash_is_still_blocked("USD", "人民幣")
    finally:
        CALC.dividend_currency = _real
    test_a_real_currency_clash_is_still_blocked("USD", "人民幣")


def test_calling_every_payout_rate_listed_turns_the_provenance_guard_red():
    """突變③：讓本地自算的來源也用「掛牌」那一套說法 → B2 守衛必須紅。"""
    _real = dict(_ADR_SOURCE_LABELS)
    try:
        _ADR_SOURCE_LABELS[ADR_FROM_RECORDS] = _real[ADR_OFFICIAL]
        with pytest.raises(AssertionError):
            test_only_the_official_rate_is_ever_called_listed(ADR_FROM_RECORDS)
    finally:
        _ADR_SOURCE_LABELS.clear()
        _ADR_SOURCE_LABELS.update(_real)
    test_only_the_official_rate_is_ever_called_listed(ADR_FROM_RECORDS)


def test_treating_a_same_source_rate_as_a_second_opinion_turns_the_guard_red():
    """突變④：讓「同源」那道分流失效（所有來源都當成官方）→ 假第二意見守衛必須紅。"""
    _page_real = _PAGE_MOD.ADR_OFFICIAL
    try:
        # 把畫面眼中的「官方」指到本地自算那一層 ⇒ 同源分流當場失效。
        _PAGE_MOD.ADR_OFFICIAL = ADR_FROM_RECORDS
        with pytest.raises(AssertionError):
            test_a_locally_derived_rate_is_never_sold_as_a_second_opinion(
                ADR_FROM_RECORDS)
    finally:
        _PAGE_MOD.ADR_OFFICIAL = _page_real
    test_a_locally_derived_rate_is_never_sold_as_a_second_opinion(ADR_FROM_RECORDS)


def test_dropping_the_shared_note_in_the_sixth_cell_turns_the_guard_red():
    """突變⑤：把 `_invest_note_for` 還原成**修復前**（無視 `blank`）→ B3 守衛必須紅。"""
    _real = _PAGE_MOD._invest_note_for
    _PAGE_MOD._invest_note_for = (
        lambda _reason, _facts, _blank: _PAGE_MOD._invest_blocked_note(_reason, _facts))
    try:
        with pytest.raises(AssertionError):
            _mutated_note_for_guard(NO_CURRENCY)
    finally:
        _PAGE_MOD._invest_note_for = _real
    _mutated_note_for_guard(NO_CURRENCY)


def _mutated_note_for_guard(reason: str) -> None:
    """與 :func:`test_when_nothing_came_back_the_sixth_cell_says_what_the_other_five_say`
    同一條斷言，但**在呼叫時**才去模組上取 `_invest_note_for` ——
    這樣突變⑤換掉模組屬性之後才咬得到（直接 import 進來的名字換不掉）。"""
    assert _PAGE_MOD._invest_note_for(reason, {}, _SHARED_BLANK) == _SHARED_BLANK


def test_feeding_percentage_points_to_the_reconciler_turns_the_unit_guard_red():
    """突變⑥：把小數換成**百分點**餵給對帳 → X4 單位守衛必須紅。

    ⚠️ 這顆突變只在**低配息率**時咬得到（見上方推導：>2% 兩種用法判定相同）——
    這正是那條守衛必須用 1.00% / 1.09% 這組哨兵、而不是 5.75% 的原因。
    """
    _real = CALC.reconcile_dividend_yield
    CALC.reconcile_dividend_yield = lambda _a, _b: _real(_a * 100.0, _b * 100.0)
    try:
        with pytest.raises(AssertionError):
            test_the_reconciler_is_fed_decimals_not_percentage_points()
    finally:
        CALC.reconcile_dividend_yield = _real
    test_the_reconciler_is_fed_decimals_not_percentage_points()


def test_hiding_the_same_currency_assumption_turns_the_disclosure_guard_red():
    """突變⑦：讓沒標幣別的配息看起來「有標」→ Y2 揭露守衛必須紅。

    這是**真的會發生**的那種退化：只要 `dividend_currency` 哪天改成
    「沒標就當成跟基金一樣」，那句 §1 揭露就會**靜靜地消失**，
    而畫面上的數字**一個都不會變** —— 沒有這顆突變，沒有人會發現。
    """
    _real = CALC.dividend_currency
    CALC.dividend_currency = lambda _r: CALC.fund_currency(_r)
    try:
        with pytest.raises(AssertionError):
            test_an_unlabelled_dividend_currency_is_declared_as_an_assumption_on_screen()
    finally:
        CALC.dividend_currency = _real
    test_an_unlabelled_dividend_currency_is_declared_as_an_assumption_on_screen()


def test_on_a_total_failure_the_invest_block_prints_the_same_sentence_on_screen():
    """⭐ **B3 的畫面級守衛** —— 前五格與第六格在畫面上印的是**同一句**。

    ⚠️ 上面那幾條驗的是 :func:`_invest_note_for` 這個純函式；**這一條驗的是畫面**。
    兩者都要：純函式那條擋「邏輯寫錯」，這一條擋「邏輯對但沒接線」——
    B3 本身就是後者（`_render_invest_calc` 從來沒拿到 `_blank`）。
    """
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE,
                     result=_BLANK_RESULT())
    _seg = _segments(_parts)
    _invest = "\n".join(_seg.get(DEEP_DIVE_INVEST, []))
    assert _invest, f"深度區沒有畫出「{DEEP_DIVE_INVEST}」：{list(_seg)}"
    # 前五格印的那一句 —— 從**畫面上**取，不自己重算一份（重算就變成第二個真相源）。
    _others = "\n".join(_l for _k, _v in _seg.items() if _k != DEEP_DIVE_INVEST
                        for _l in _v)
    assert "在 2 個來源都沒有取到淨值" in _others, (
        f"前五格沒有印出全敗共用句，這條測試的前提垮了：\n{_others[:400]}")
    assert "在 2 個來源都沒有取到淨值" in _invest, (
        f"全敗時第六格沒有跟其餘五格說同一句：\n{_invest}\n"
        "⛔ 它會改口說「查不到這一檔是用哪一種幣別計價的」—— "
        "同一個原因、兩種故事，而且第二種把使用者導向錯的結論。")
    assert "查不到這一檔是用哪一種幣別計價" not in _invest, (
        f"全敗時第六格仍在講自己的幣別原因：\n{_invest}")


@pytest.mark.parametrize("src", [ADR_OFFICIAL, ADR_LOCAL_RATE, ADR_FROM_RECORDS,
                                 "某個上游日後才新增的來源"])
@pytest.mark.parametrize("agree", [True, False])
def test_none_of_the_three_payout_sources_speaks_our_internal_language(src, agree):
    """⭐ **補上一個本批自己開的缺口**，不是重複既有那條。

    既有的 :func:`test_this_block_never_speaks_our_internal_language` 是用
    :func:`_invest_body` **渲染整塊**驗的，而它的五份 fixture **全部走
    :data:`ADR_OFFICIAL`**（`_RICH_WITH_NAV` 帶 `moneydj_div_yield`）——
    也就是本批新增的**另外兩條** copy 路徑，在那條測試的射程外。

    ⛔ 新增使用者看得到的文案，就要把它拉進同一張字表底下；
    「我人工看過一遍」不是守衛（§-2 規則 6）。
    """
    _line = _invest_compare(_compare_facts(adr_source=src,
                                           income_reconcile={"agree": agree}))
    _hits = sorted({_w for _w in _INTERNAL_WORDS if _w in _line})
    assert not _hits, (
        f"來源 {src!r}（agree={agree}）的比較句出現內部語言：{_hits}\n{_line}")


# ══════════════════════════════════════════════════════════════════
# ⭐ 2026-09-08 第五輪｜同一頁上的**第二對**命名空間（總管放行的兩行）
#
# `_dividend_caption` 走 **L0 only**（`reconcile_row_currencies` → `normalize_iso_ccy`，
# 看不懂中文別名），投資試算走 **L2→L0**（`comparable_ccy`）。於是一檔 `currency`
# 欄寫中文「人民幣」的基金，同一個畫面上會**同時**出現：
#
#     【配息紀錄】2 筆 · 幣別未知或逐筆幣別不一致 …
#     【投資試算】…最近一筆實際配息 0.0500 CNY／單位…
#
# **上面說不知道，下面斬釘截鐵印 CNY，還拿它做了換算。**
# ⚠️ **與 B1 是同一個病的第二對**，藥方也同一帖：兩側都過 `comparable_ccy`。
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("written", _ALL_CCY_WRITINGS)
def test_the_caption_and_the_invest_block_agree_on_what_currency_this_fund_is(written):
    """⭐ **機制測試**：同一個宣告，配息表那一句與投資試算那一格必須收成同一個字。

    ⛔ 這一條**不看任何特定幣別**，所以它擋的是**整個類別** ——
    下一個中文別名（「港幣」「日圓」…）不必再寫一條新測試。
    """
    _caption_side = reconcile_row_currencies([comparable_ccy(written)])
    _invest_side = fund_currency({"currency": written})
    assert _caption_side == _invest_side, (
        f"宣告 {written!r}：配息表那一句收成 {_caption_side!r}、"
        f"投資試算收成 {_invest_side!r} —— 同一個畫面、同一檔基金，兩句會互相矛盾。")


def test_a_chinese_currency_never_makes_the_page_say_unknown_and_a_code_at_once():
    """⭐ **畫面級**：中文計價幣別不得讓同一頁一邊說「不知道」、一邊印出代碼。

    ⚠️ 這一條驗的是**畫面**，上一條驗的是**兩個函式的回傳值** —— 兩者都要：
    上一條擋「邏輯寫錯」，這一條擋「邏輯對但沒接線」
    （B3 就是後者：`_render_invest_calc` 從來沒拿到 `_blank`）。
    """
    _rows = [{"date": "2026/08/15", "amount": SENT_DIV, "currency": "人民幣"}]
    _res = _FUND(currency="人民幣", dividends=_rows)
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_res, fx=SENT_FX)
    _seg = _segments(_parts)
    _caption = "\n".join(_seg.get(DEEP_DIVE_TABLES[1], []))
    _invest = "\n".join(_seg.get(DEEP_DIVE_INVEST, []))
    assert _caption, f"配息紀錄那一塊沒有畫出來：{list(_seg)}"
    assert "CNY" in _invest, (
        f"前提垮了 —— 投資試算沒有印出 CNY，這條測試就沒有在驗矛盾：\n{_invest}")
    assert CCY_UNKNOWN not in _caption, (
        f"同一個畫面：配息表說「{CCY_UNKNOWN}」，投資試算卻印 CNY 並拿它換算。\n"
        f"【配息紀錄】{_caption}\n【投資試算】{_invest}\n"
        "⛔ 兩句都是本頁印的（§1：錯誤的數字比沒有數字更危險）。")
    assert "全部以 CNY 計價" in _caption, (
        f"配息表沒有誠實宣告 CNY：\n{_caption}")


@pytest.mark.parametrize("fund_ccy, div_ccy", [
    ("人民幣", "USD"),      # 中文 vs ISO —— 過了 L2 之後才看得見的真衝突
    ("美元", "TWD"),
    ("TWD", "美元"),
])
def test_the_caption_still_flags_a_real_clash_after_the_alias_pass(fund_ccy, div_ccy):
    """⛔ **反面守衛**：為了讓中文別名過關，不得把比對器變成永不擋。

    `_dividend_caption` 對真衝突的既有處置是**指名道姓**（「⚠️ 資料疑義：逐筆配息宣告 X，
    這檔基金的計價幣別卻是 Y」）。過了 L2 之後**那條路必須還在**。
    """
    _rows = _dividend_rows(_FUND(dividends=[
        {"date": "2026/08/15", "amount": SENT_DIV, "currency": div_ccy}]))
    _cap = _dividend_caption(_rows, fund_ccy)
    assert "資料疑義" in _cap, (
        f"基金 {fund_ccy!r} vs 逐筆 {div_ccy!r} 是**真的**幣別衝突，"
        f"配息表卻沒有標成資料疑義：\n{_cap}")
    assert "全部以" not in _cap, f"真衝突卻宣告了單一幣別：\n{_cap}"


# ══════════════════════════════════════════════════════════════════
# ⛔ 2026-09-08 第六輪｜**第四個同頁矛盾**：表上畫著 N 筆，下面說「沒有紀錄」
#
# `_invest_basis_note` 的 `else` 分支原本**無條件**寫「這一檔沒有逐筆配息紀錄」，
# 但走到那條路的真正條件是「**推不出最近一筆實際配息**」—— 那有四種成因，
# 「沒有紀錄」只是其中**一種**。於是：
#
#     【配息紀錄】2 筆 · 全部以 USD 計價 …          ← 表照畫
#     【投資試算】這一檔沒有逐筆配息紀錄，所以…      ← 同一個畫面說沒有
#
# ⚠️ 這是本 PR 第四次同型（B1 幣別命名空間 → 掛牌 vs 自算 → 幣別未知 vs CNY → 這個）。
# ⛔ 修法**不是把那句話刪掉** —— 使用者需要知道為什麼算不出來；
#    是**講對原因**，而且**四種成因四句話，不准用一句蓋住**。
# ══════════════════════════════════════════════════════════════════

#: 三種「有紀錄、但推不出最近一筆」的觸發。**每一種的成因都不一樣，畫面必須分開講。**
_GAP_TRIGGERS: tuple[tuple[str, str, list[dict]], ...] = (
    ("缺日期", GAP_NO_DATE, [
        {"amount": SENT_DIV, "currency": "USD"},
        {"amount": SENT_DIV, "currency": "USD"}]),
    ("金額全 0", GAP_AMOUNT, [
        {"date": "2026/08/15", "amount": 0.0, "currency": "USD"},
        {"date": "2026/07/15", "amount": 0.0, "currency": "USD"}]),
    ("金額全負", GAP_AMOUNT_NEG, [
        {"date": "2026/08/15", "amount": -SENT_DIV, "currency": "USD"},
        {"date": "2026/07/15", "amount": -SENT_DIV, "currency": "USD"}]),
)


@pytest.mark.parametrize("label, expect_gap, divs", _GAP_TRIGGERS)
def test_the_page_never_says_there_are_no_dividend_records_while_the_table_shows_some(
        label, expect_gap, divs):
    """⭐ **畫面級**：配息表畫得出列的時候，投資試算不得說「這一檔沒有逐筆配息紀錄」。

    ⚠️ 這一條驗的是**同一次渲染的兩塊**（不是兩個函式的回傳值）——
    §1 的違憲點在於「**兩句都是本頁印的，而且互相矛盾**」，
    只驗其中一塊看不出矛盾。
    """
    _res = _RICH_RESULT()
    _res["currency"] = "USD"
    _res["metrics"]["nav"] = SENT_NAV
    _res["nav_latest"] = SENT_NAV
    _res["moneydj_div_yield"] = SENT_ADR
    _res["dividends"] = divs
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_res, fx=SENT_FX)
    _seg = _segments(_parts)
    _table = "\n".join(_seg.get(DEEP_DIVE_TABLES[1], []))
    _invest = "\n".join(_seg.get(DEEP_DIVE_INVEST, []))
    assert "筆 ·" in _table, (
        f"前提垮了 —— {label}：配息表沒有畫出「N 筆」，這條測試就沒有在驗矛盾：\n{_table}")
    assert "沒有逐筆配息紀錄" not in _invest, (
        f"{label}：配息表畫著列，投資試算卻說「沒有逐筆配息紀錄」。\n"
        f"【配息紀錄】{_table}\n【投資試算】{_invest}\n"
        "⛔ 兩句都是本頁印的（§1：錯誤的說明比沒有說明更危險）。")


def test_a_fund_with_truly_no_dividend_records_still_says_so():
    """⛔ **正對照**：真的一列都沒有時，那句話**必須**還在。

    沒有這一條，上一條可以用「把整句話刪掉」通過 —— 而刪掉之後使用者
    **再也不知道為什麼算不出來**，那是另一種不誠實（總管：⛔ 不准刪掉了事）。
    """
    _res = _RICH_RESULT()
    _res["currency"] = "USD"
    _res["metrics"]["nav"] = SENT_NAV
    _res["nav_latest"] = SENT_NAV
    _res["moneydj_div_yield"] = SENT_ADR
    _res["dividends"] = []
    _parts = _render(applied=FAKE_QUERY, selected=SELECTED_CODE, result=_res, fx=SENT_FX)
    _invest = "\n".join(_segments(_parts).get(DEEP_DIVE_INVEST, []))
    assert "沒有逐筆配息紀錄" in _invest, (
        f"真的沒有配息紀錄，畫面卻不講原因了：\n{_invest}")


@pytest.mark.parametrize("label, expect_gap, divs", _GAP_TRIGGERS)
def test_each_trigger_is_diagnosed_as_its_own_cause_not_one_blanket_excuse(
        label, expect_gap, divs):
    """⭐ **三種成因三句話** —— ⛔ 不准用一句藉口蓋住三個不同的原因（本 repo 鐵則）。

    驗兩件事：(a) 判定拿到的是**它自己那一個** `GAP_*`；
    (b) 那句話**指名**了卡住的是金額還是日期 —— 只說「算不出來」不算數。
    """
    _res = {"currency": "USD", "metrics": {"nav": SENT_NAV},
            "moneydj_div_yield": SENT_ADR, "dividends": divs}
    _gap, _n = _income_basis_gap(_res)
    assert _gap == expect_gap, f"{label}：判定成 {_gap!r}，應為 {expect_gap!r}"
    assert _n == len(_dividend_rows(_res)), (
        f"{label}：說 {_n} 筆，配息表卻畫 {len(_dividend_rows(_res))} 筆 —— "
        "兩個數字必須同源，否則就是換一個地方再矛盾一次")
    _facts = estimate_monthly_income(_res, SENT_AMOUNT, fx_lookup=_fx)
    _note = _invest_basis_note(_facts, _res)
    _named = "日期" if expect_gap == GAP_NO_DATE else "金額"
    assert _named in _note, (
        f"{label}：那句話沒有指名卡住的是「{_named}」，等於用一句藉口蓋過去：\n{_note}")
    assert str(_n) in _note, (
        f"{label}：那句話沒有把「表上有 {_n} 筆」講出來 —— "
        f"不講筆數就等於默認「沒有紀錄」：\n{_note}")


def test_the_three_causes_do_not_share_one_sentence():
    """⛔ 三種成因的那句話**必須兩兩不同** —— 一樣就是「一句蓋住三個」。"""
    _notes = {}
    for label, _gap, divs in _GAP_TRIGGERS:
        _res = {"currency": "USD", "metrics": {"nav": SENT_NAV},
                "moneydj_div_yield": SENT_ADR, "dividends": divs}
        _notes[label] = _invest_basis_note(
            estimate_monthly_income(_res, SENT_AMOUNT, fx_lookup=_fx), _res)
    assert len(set(_notes.values())) == len(_notes), (
        "三種成因講出了同一句話：\n" + "\n".join(f"  {k}: {v}" for k, v in _notes.items()))


def test_the_basis_note_is_wired_to_the_actual_result_not_left_at_its_default():
    """⛔ **接線守衛**：production 呼叫點必須把 `result` 傳進去。

    ⚠️ 這是 B3 那個病的同一種形狀：**邏輯對了但沒接線**
    （`_render_invest_calc` 當初就是從來沒拿到 `_blank`）。
    `_invest_basis_note` 的第二個參數有預設值（既有測試逐一呼叫它時不必每次傳），
    **所以少傳不會炸、只會靜靜退回「講不出成因」那一句** —— 正好是最難察覺的失效。
    """
    _src = _PAGE.read_text(encoding="utf-8")
    _call = "_invest_basis_note(_facts, result)"
    assert _call in _src, (
        f"`{_call}` 不在 {_PAGE.name} 裡 —— "
        "少傳 `result` 不會報錯，畫面只會退成「推不出最近一筆實際配息」，"
        "所有成因一律講不出來。")


def test_the_count_in_the_note_comes_from_the_same_rows_the_table_draws():
    """⛔ 筆數必須與配息表**同源**，否則只是換個地方再矛盾一次。

    ⚠️ **這一條是突變測試逼出來的，不是我一開始就想到的**：`_income_basis_gap`
    的 docstring 自陳「筆數取自 `_dividend_rows`，結構上不可能對不上」，
    但把它換成 `len(result["dividends"])` 之後**九條守衛一條都沒紅**
    —— 因為前面三組觸發的 raw 與顯示筆數**剛好一樣**。
    **一個「有揭露、零守衛」的宣稱，和沒有宣稱是一樣的**（本 PR X4/Y2 的同型）。

    這一組刻意讓兩者**不一樣**：第一列 `amount=None` 會被配息表丟掉
    （`_dividend_rows`：「沒有金額的配息列不是資料，是雜訊」），
    但它仍然留在 raw list 裡 ⇒ raw 3 筆、表上 2 筆。
    """
    _divs = [
        {"date": "2026/09/01", "amount": None, "currency": "USD"},   # ← 表上不會出現
        {"amount": SENT_DIV, "currency": "USD"},                     # ← 有金額、無日期
        {"amount": SENT_DIV, "currency": "USD"},
    ]
    _res = {"currency": "USD", "metrics": {"nav": SENT_NAV},
            "moneydj_div_yield": SENT_ADR, "dividends": _divs}
    _shown = len(_dividend_rows(_res))
    assert _shown == 2 and len(_divs) == 3, (
        f"前提垮了 —— 表上 {_shown} 筆 / raw {len(_divs)} 筆，兩者必須不同，"
        "否則這條測試殺不掉「拿 raw 長度來數」那顆突變")
    _gap, _n = _income_basis_gap(_res)
    assert (_gap, _n) == (GAP_NO_DATE, _shown), f"判定 {(_gap, _n)!r}，應為 {(GAP_NO_DATE, _shown)!r}"
    _note = _invest_basis_note(
        estimate_monthly_income(_res, SENT_AMOUNT, fx_lookup=_fx), _res)
    _cap = _dividend_caption(_dividend_rows(_res), "USD")
    assert f"{_shown} 筆" in _note and f"{_shown} 筆" in _cap, (
        f"配息表說的筆數與投資試算說的對不上：\n【配息紀錄】{_cap}\n【投資試算】{_note}")
    assert f"{len(_divs)} 筆" not in _note, (
        f"投資試算報了 raw 的 {len(_divs)} 筆，而表上只畫 {_shown} 筆：\n{_note}")


# ══════════════════════════════════════════════════════════════════
# M3（第五輪稽核）｜`TRACE_UNKNOWN` 是深度區**活著的**內部語言字串
#
# 既有的 `test_this_block_never_speaks_our_internal_language` 只渲染
# **投資試算那一塊**，來源軌跡表在它的射程外 —— 於是「上游沒說」
# 一路印在「結果」欄裡，與「成功」「失敗」並列，**四輪都沒有人看到**。
# ⚠️ 前四個同類用字當初被具名登記交總管另派，**這第五個沒有** —— 漏的是登記本身。
# ══════════════════════════════════════════════════════════════════

def test_the_source_trace_result_column_speaks_the_users_language():
    """⛔ 來源軌跡「結果」欄的三個字面值都會**直接印給使用者看**，不得帶內部語言。

    ⚠️ 這一條與 `test_this_block_never_speaks_our_internal_language` **不重疊**：
    那一條渲染投資試算那一塊，**看不到**來源軌跡表。
    """
    from ui.views.page_03_research import TRACE_FAIL, TRACE_OK, TRACE_UNKNOWN
    _hits = sorted({f"{_v}:{_w}" for _v in (TRACE_OK, TRACE_FAIL, TRACE_UNKNOWN)
                    for _w in _INTERNAL_WORDS if _w in _v})
    assert not _hits, (
        f"來源軌跡的「結果」欄出現內部語言：{_hits}\n"
        "這三個字面值是**直接印在表格裡**的，使用者讀得到。")


def test_the_source_trace_still_tells_three_states_apart():
    """⛔ **正對照**：改用字不得把三態壓成兩態（否則「沒說」會被讀成「失敗」）。"""
    from ui.views.page_03_research import TRACE_FAIL, TRACE_OK, TRACE_UNKNOWN
    _three = (TRACE_OK, TRACE_FAIL, TRACE_UNKNOWN)
    assert len(set(_three)) == 3, f"三態塌成 {set(_three)!r}"
    assert all(_v.strip() for _v in _three), f"有空字面值：{_three!r}"


# ══════════════════════════════════════════════════════════════════
# M1（第五輪稽核）｜那兩行的**副作用**：三組別名由「軟的未知」變成「硬的假指控」
#
# ⚠️ **這一條釘的是「今天長這樣」，不是「這樣是對的」** —— 形狀沿用本檔既有的
# `test_the_no_amount_branch_is_unreachable_from_this_screen_today`：
# 一旦有人把它修好，這條會**轉紅**，逼下一個人回來讀 `P-CNHALIAS-1` / `P-ALIASSHAPE-1`。
#
# **為什麼不直接修**：兩個根因都在 `services/currency.py` 那張**共用表**，
# 它另有三個消費者（含客戶紅線凍結的 `ui/tab2_single_fund.py`）——
# 改表不必編輯那些檔，**但會改變它們的行為**。那是 scope 決定（§8.4 步驟 4），
# 本輪總管放行的範圍寫死在「那個 `else` 分支的原因判斷」。
# ══════════════════════════════════════════════════════════════════

@pytest.mark.parametrize("fund_ccy, div_ccy, ticket", [
    ("人民幣(CNH)", "CNY", "P-CNHALIAS-1"),    # CCY_NORMALIZE 單次查表，停在 CNH
    ("人民幣(CNH)", "人民幣", "P-CNHALIAS-1"),
    ("RMB", "CNY", "P-ALIASSHAPE-1"),          # 不在表裡，被形狀檢查當成合法 ISO 放行
    ("NTD", "TWD", "P-ALIASSHAPE-1"),
])
def test_two_spellings_of_one_currency_are_still_accused_of_clashing_today(
        fund_ccy, div_ccy, ticket):
    """⛔ **釘住已知的假指控**：這幾組是**同一種幣的兩種寫法**，畫面卻說「資料疑義」。

    這一條**故意斷言錯誤的現況**。它存在的理由有兩個：

    1. **不讓它靜默漂移** —— 修好了會轉紅，修壞了（例如再多一組別名）也會被發現；
    2. **把登記單號寫進斷言訊息** —— 下一個人踩到時，直接知道要去讀哪一列。

    ⚠️ **不得把本條讀成「這個行為是對的」。** 它是 §1 的假話：
    對使用者說兩邊不一致，而 `services/currency.py::CCY_NORMALIZE` 自己就寫著
    `CNH → CNY`、`台幣 → TWD`。**同時它還把配息試算整段擋掉。**
    """
    _rows = [{DIVIDEND_COLS[4]: div_ccy, DIVIDEND_COLS[0]: "2026/08/15"}]
    _cap = _dividend_caption(_rows, fund_ccy)
    assert "資料疑義" in _cap, (
        f"{fund_ccy!r} vs {div_ccy!r} 已經不再被誤判成衝突了 —— **這是好事**。\n"
        f"請回頭把 `EXCEPTIONS.md` 的 `{ticket}` 結案，並刪掉這一條釘樁。\n"
        f"目前畫面：{_cap}")


def test_the_currency_table_still_says_these_spellings_mean_the_same_thing():
    """⭐ **正對照**：上一條指控的「兩種寫法」，repo 自己的表確實說它們是同一種幣。

    沒有這一條，上一條只是「有兩個字串不相等」——**證明不了那是假指控**。
    """
    assert CCY_NORMALIZE.get("CNH") == "CNY", CCY_NORMALIZE.get("CNH")
    assert CCY_NORMALIZE.get("人民幣") == "CNY", CCY_NORMALIZE.get("人民幣")
    assert CCY_NORMALIZE.get("人民幣(CNH)") == "CNH", (
        "`人民幣(CNH)` 不再指向 CNH —— P-CNHALIAS-1 可能已被修掉")
    assert CCY_NORMALIZE.get("台幣") == "TWD", CCY_NORMALIZE.get("台幣")
    assert "RMB" not in CCY_NORMALIZE and "NTD" not in CCY_NORMALIZE, (
        "`RMB`／`NTD` 已被補進 CCY_NORMALIZE —— P-ALIASSHAPE-1 可能已被修掉")


# ══════════════════════════════════════════════════════════════════
# ⛔ 2026-09-08 第七輪｜自稱「實跑」的分類矩陣印著**舊值**
#
# `TRACE_UNKNOWN` 由 `"上游沒說"` 改成 `"沒有回報"` 的**同一顆 commit**
# 更新了三處引用，**漏掉矩陣裡的兩格**。於是那張**自稱「實跑」**的表
# 印著一個**程式裡已經不存在的字串**。
#
# ⚠️ **一張自稱實跑的表印著舊值，比沒有那張表更糟** —— 它讓讀者以為那是量出來的。
# ⚠️ 這是本 PR 一路在修的同一個病，**範圍縮到同一個檔案的 30 行之內**。
# ⛔ 之前**零守衛**：那張表是 `#:` 註解，沒有任何東西在讀它。
# ══════════════════════════════════════════════════════════════════

def _trace_matrix_rows() -> list[tuple[str, str, str]]:
    """把 `page_03_research.py` 那張分類矩陣讀出來 → `[(形狀, 結果欄, 計入來源數)]`。

    矩陣是 RST 風格的定寬表，夾在兩條 `=====` 之間、每行以 `#:` 開頭。
    ⚠️ **刻意用「兩條分隔線之間」定位，不用行號** —— 行號在任何一次編輯後就失效。
    """
    _lines = [_l.rstrip("\n") for _l in _PAGE.read_text(encoding="utf-8").split("\n")]
    _sep = [_i for _i, _l in enumerate(_lines)
            if _l.startswith("#: =====") and "============" in _l]
    assert len(_sep) == 3, (
        f"矩陣的分隔線應該恰好 3 條（頭／欄名下／尾），實際 {len(_sep)}：{_sep}\n"
        "⇒ 表被改過形狀了，這支解析器要一起更新（**不要放寬斷言**）。")
    _out: list[tuple[str, str, str]] = []
    for _l in _lines[_sep[1] + 1:_sep[2]]:
        _body = _l[2:].strip()          # 去掉 "#:"
        if not _body:
            continue
        # ⚠️ **刻意不用定寬字元切**：欄位對齊靠的是**顯示寬度**（CJK 佔 2 欄），
        #    而 Python 的字串索引是**字元數** —— 用固定索引切，CJK 多的那幾列會錯位。
        #    （本組第一版就是這樣寫的，當場被自己的斷言擋下來。）
        #    RST 定寬表的欄位之間**至少兩個空白**，以此切最穩。
        _cells = re.split(r"\s{2,}", _body)
        # 第 4 欄**只准**是腳註標記（表尾那一列有 `← **(a)**`）。
        # ⛔ 不是「>= 3 就放行」：多出來的東西必須長成腳註，否則表的形狀變了。
        assert len(_cells) == 3 or (len(_cells) == 4 and _cells[3].startswith("←")), (
            f"這一列切不出「形狀／結果欄／計入來源數（＋選配腳註）」：{_l!r}\n"
            f"切出來的是：{_cells!r}\n"
            "⛔ 不要把這裡放寬成 `>= 2` —— 切不乾淨就表示表的形狀變了，該修的是解析器。")
        _out.append((_cells[0], _cells[1], _cells[2]))
    return _out


def test_the_trace_matrix_never_prints_a_literal_the_code_no_longer_has():
    """⭐ 矩陣「結果欄」的每一格，都必須是**現行三個常數之一**。

    ⛔ 這一條是**漂移守衛**，不看語意：常數改了字、矩陣沒跟上 → 當場轉紅。
    **它擋的正是 2026-09-08 那一顆 commit 漏掉的那兩格。**
    """
    from ui.views.page_03_research import TRACE_FAIL, TRACE_OK, TRACE_UNKNOWN
    _live = {TRACE_OK, TRACE_FAIL, TRACE_UNKNOWN}
    _rows = _trace_matrix_rows()
    assert _rows, "矩陣一列都沒讀到 —— 解析器壞了（0 列的綠燈等於沒檢查）"
    _bad = sorted({_r[1] for _r in _rows if _r[1] not in _live})
    assert not _bad, (
        f"矩陣的「結果欄」印著程式裡已經不存在的字串：{_bad}\n"
        f"現行三個常數：{sorted(_live)}\n"
        "⚠️ 那張表**自稱「實跑」** —— 印著舊值比沒有那張表更糟。")


#: 矩陣四列各自對應的 `source_trace` 形狀。**這份對映是人寫的**，
#: 所以下面那條守衛同時驗「對映還對不對」（形狀描述變了就轉紅）。
_TRACE_SHAPE_FIXTURES: tuple[tuple[str, dict], ...] = (
    ("缺 ``success`` 鍵", {"source": "S1", "note": "ok"}),
    ("``success: None``（說了、值是空）", {"source": "S2", "success": None}),
    ("``success: False``（真的失敗）", {"source": "S3", "success": False}),
    ("有 ``error`` 但**無** ``success`` 鍵", {"source": "S4", "error": "HTTP 500"}),
)


def test_every_cell_of_the_trace_matrix_matches_a_real_run():
    """⭐ **逐格**比對矩陣與真跑 —— 結果欄**與**計入來源數都驗。

    ⛔ **不是只驗被點名的那兩格**：本 PR 反覆發作的病就是
    「更正一個被點名的項目時，沒有把同一把尺對全部同類項目重跑」
    （`CLAUDE.md` §8.2.A 驗證段 ④ 的既有教訓）。
    """
    from ui.views.page_03_research import TRACE_COLS, _failed_source_count, _trace_rows
    _rows = _trace_matrix_rows()
    assert len(_rows) == len(_TRACE_SHAPE_FIXTURES), (
        f"矩陣有 {len(_rows)} 列、對映有 {len(_TRACE_SHAPE_FIXTURES)} 筆 —— "
        "有人加／刪了一列卻沒更新這裡（**不要把對映補成寬鬆的**）。")
    for (_shape_doc, _declared_result, _declared_count), (_shape_fx, _trace) in zip(
            _rows, _TRACE_SHAPE_FIXTURES):
        assert _shape_doc == _shape_fx, (
            f"矩陣第一欄變了：文件寫 {_shape_doc!r}、對映寫 {_shape_fx!r}\n"
            "⇒ 下面那一格的比對會變成拿錯的形狀去驗，先修對映。")
        _res = {"source_trace": [_trace]}
        _actual_result = _trace_rows(_res)[0][TRACE_COLS[1]]
        _actual_count = _failed_source_count(_res)
        assert _declared_result == _actual_result, (
            f"「{_shape_doc}」：矩陣說結果欄是 {_declared_result!r}，"
            f"真跑是 {_actual_result!r}。")
        assert _declared_count == str(_actual_count), (
            f"「{_shape_doc}」：矩陣說計入來源數是 {_declared_count!r}，"
            f"真跑是 {_actual_count!r}。")
