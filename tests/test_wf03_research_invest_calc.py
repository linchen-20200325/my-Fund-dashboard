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

⭐ **本檔末段有真的突變測試**（`tests/test_wf03_research_invest_calc.py::
   test_removing_*`）—— 它們**在同一個 process 裡把修復拔掉**（monkeypatch 合作者），
   然後斷言對應的守衛**真的轉紅**。憲法 §-1.5 v3 `03`-1 要的就是這個：
   「突變測試（拔掉修復邏輯必須轉為紅燈）」。

⚠️ **本檔看不見什麼（照實寫，不要讀成「守死了」）**
--------------------------------------------------
1. **不驗真的匯率**。`fx_rate_to_twd()` 會出網，本檔一律傳自己的 `fx_lookup` 替身
   或在渲染層用 `_render(fx=…)`。⇒「四源 fallback 有沒有壞」不在射程內，
   那是 `services/fund_service.py` 那一側的事。
2. **不驗 `monthly_dividend_from_records` 算得對不對** —— 它有自己的守衛
   （`tests/test_monthly_dividend_units.py`）。本檔驗的是「**有沒有真的走它**」。
3. **本地沒有 `streamlit` / `pandas` / `pytest`，本檔從未在真 pytest 下跑過**
   （見 PR 的自陳）。畫面層那幾條是靠 `tests/test_wf03_research_skeleton.py::_render`
   這個既有 harness 跑的，**判定邏輯本地實跑過**，但那不是 pytest。
"""
from __future__ import annotations

import ast
import math
import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

import services.fund_invest_calc as CALC  # noqa: E402
from services.fund_invest_calc import (  # noqa: E402
    BASIS_ESTIMATE,
    BASIS_RECORDS,
    CCY_CONFLICT,
    DEFAULT_AMOUNT_TWD,
    NO_AMOUNT,
    NO_CURRENCY,
    NO_FX,
    NO_INCOME_BASIS,
    NO_NAV,
    estimate_monthly_income,
)
from ui.helpers.render_state import NOT_READY_MARK  # noqa: E402
from ui.views.page_03_research import (  # noqa: E402
    DEEP_DIVE_INVEST,
    INVEST_SUBMIT_LABEL,
    _INVEST_AMOUNT_KEY,
    _INVEST_BLOCKED_NOTES,
    _INVEST_FORM_KEY,
    _LABEL_INVEST_AMOUNT,
    _SK_INVEST_AMOUNT,
    _invest_where,
)

# ⚠️ **共用同一個渲染 harness，刻意不另寫第二份** —— 兩份會在「怎麼 patch `st`」
#    這件事上漂移（理由見那一支 `_render()` 開頭那段長註）。
from test_wf03_research_skeleton import (  # noqa: E402
    FAKE_QUERY,
    SELECTED_CODE,
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
