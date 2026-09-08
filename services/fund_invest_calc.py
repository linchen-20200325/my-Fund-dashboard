"""投資試算的算式層 —— 回答「我投 X 元台幣，每個月大概領多少？」。

客戶 2026-09-08 拍板：**投資試算定案搬移至 ⑧（標的探索）的單一基金深度區塊**
（⑥ 只留「現有持倉的每月配息推估總額」）。本模組是那一塊的**唯一算式來源**。

⛔ **本模組不發明任何算法。** 四個關鍵值全部沿用既有 SSOT，只是把它們串起來：

===================== ================================================================
要算的東西             走哪一個既有 SSOT
===================== ================================================================
計價幣別正規化         :func:`services.currency.normalize_ccy`（``mode="yf"``，
                      與舊 ③ `ui/tab2_single_fund.py` 及 ②
                      `ui/helpers/fund_grp_health/investment.py` 同一個模式）
年化配息率             :func:`services.health.dividend._resolve_adr_with_fallback`
                      —— 三層 fallback ＋ **回傳實際命中的那一層**（§2.2 血緣）
每月配息               :func:`services.health.dividend_calc.monthly_dividend_from_records`
                      —— 真實記錄優先、年化估算 fallback，全站同源
即期匯率               :func:`services.fund_service.get_latest_fx`（L2 facade）
===================== ================================================================

⚠️ **為什麼不直接把 `ui/helpers/fund_grp_health/investment.py` 搬過來**：那一支是
**②（持倉體檢）**的元件 —— 它的本金**固定吃組合帶進來的 `principal_twd`、不給輸入框**，
而 ③ 的基金**不預設我有持有**，本金只能由使用者自己打。兩邊的本金口徑不同
（同 `ui/views/page_03_research.py::BATCH_PRINCIPAL_NOTE` 記載的 ②/③ 差異），
而且它整支是 Streamlit 渲染碼、驗不了。**共用的是算式（上表四條），不是那支渲染函式。**

分工（這一條決定了本模組長什麼樣）
----------------------------------
**本模組只產出事實與「算不出來的原因代碼」，一句中文都不產出。**
畫面上的字全部在 `ui/views/page_03_research.py` —— 理由有二：

1. 客戶對文案有硬規則（「畫面上只准有使用者的處境，不准有我們的進度」），
   文案散在兩層就會有兩個地方可以偷偷加一句內部語言；
2. 原因**代碼**可以被測試逐一參數化，中文句子只能被 `in` 比對 ——
   前者「所有同類的錯」都在射程內，後者只驗到其中一個示範。

§1 Fail Loud 在本模組的落點（逐條，不是口號）
--------------------------------------------
* 匯率查不到 → :data:`NO_FX`，**不猜一個匯率、也不拿台幣金額當原幣金額**
  （舊 ③ 就地記載過這個事故：日圓差約 4.8 倍，畫面說不算、實際算了）。
* 計價幣別認不得 → :data:`NO_CURRENCY`，**不預設 USD**
  （`repositories/fund/fund_orchestration.py::_ensure_currency` 自陳上游有 USD 死預設）。
* 淨值缺 → :data:`NO_NAV`，**不用序列末值頂替** —— 那會是第二個真相源
  （舊 ③ 與 ② 兩邊都吃 ``metrics["nav"]``，這裡照舊）。
* 配息率與逐筆記錄都沒有 → :data:`NO_INCOME_BASIS`，**不填 0**
  （0 的意思是「這檔不配息」，與「不知道」不是同一件事）。
* **逐筆配息宣告的幣別與基金計價幣別對不上** → :data:`CCY_CONFLICT`，
  **不換算、不挑一個**。理由見 :func:`estimate_monthly_income` 的長註。

⚠️ **本模組零 I/O，除了 :func:`fx_rate_to_twd` 一個函式**（它是唯一會出網的地方，
   而且**不是**預設值：:func:`estimate_monthly_income` 的 ``fx_lookup`` 不傳就當「查不到」）。
   這樣純函式那一半可以在**沒有 streamlit / pandas / 網路**的環境下逐條測。
"""
from __future__ import annotations

import sys
from typing import Any, Callable, Optional

from services.currency import normalize_ccy
from services.health.dividend import _resolve_adr_with_fallback
from services.health.dividend_calc import (
    DEFAULT_PRINCIPAL_TWD,
    monthly_dividend_from_records,
)
from services.reconcile import reconcile_dividend_yield
from shared.converters import safe_float
from shared.data_quality import (
    NAV_CCY_MISMATCH,
    nav_currency_verdict,
    reconcile_row_currencies,
)

__all__ = [
    "BASIS_ESTIMATE",
    "BASIS_RECORDS",
    "CCY_CONFLICT",
    "DEFAULT_AMOUNT_TWD",
    "MAX_AMOUNT_TWD",
    "MIN_AMOUNT_TWD",
    "NO_AMOUNT",
    "NO_CURRENCY",
    "NO_FX",
    "NO_INCOME_BASIS",
    "NO_NAV",
    "TWD",
    "dividend_currency",
    "estimate_monthly_income",
    "fund_currency",
    "fund_nav",
    "fx_rate_to_twd",
]

#: 台幣的 ISO 三碼。具名而不 inline —— 它在本檔出現在四個判斷裡。
TWD: str = "TWD"

# ── 算不出來的原因（機器碼）。⛔ 這些**不是**畫面文案，UI 負責翻成人話。 ──────
#: 使用者給的金額不是一個可以算的正數。
NO_AMOUNT: str = "no_amount"
#: 這檔基金的計價幣別認不得 —— **不預設 USD**。
NO_CURRENCY: str = "no_currency"
#: 沒有最新淨值 —— 沒有它算不出「買得到幾單位」。
NO_NAV: str = "no_nav"
#: 非台幣計價，但換匯率查不到 —— **不拿台幣金額當原幣金額**。
NO_FX: str = "no_fx"
#: 逐筆配息宣告的幣別 ≠ 基金計價幣別。**兩邊都講得出一個 ISO、但講的不是同一個。**
CCY_CONFLICT: str = "currency_conflict"
#: 逐筆配息與年化配息率**都**沒有 —— 沒有任何依據可以推每月領多少。
NO_INCOME_BASIS: str = "no_income_basis"

# ── 每月配息是**怎麼**推出來的（`monthly_dividend_from_records` 的 `source` 原值）──
#: 最近一筆**真實**配息記錄 × 持有單位。
BASIS_RECORDS: str = "records"
#: 年化配息率 ÷ 12 攤平 —— **平均值，不是每個月真的入帳這麼多**。
BASIS_ESTIMATE: str = "estimate"

#: 試算金額的預設值。**走 `dividend_calc.DEFAULT_PRINCIPAL_TWD` 這個既有 SSOT**，
#: 不另寫一個 100 萬 —— 全站「預設本金」只准有一個真相源（§2.1）。
DEFAULT_AMOUNT_TWD: float = DEFAULT_PRINCIPAL_TWD
#: 輸入框的下界／上界。沿用舊 ③ `ui/tab2_single_fund.py` 投資試算那一格的既有值。
#: ⚠️ 具名而不 inline（§3.3）—— 它們一改，畫面上那個輸入框的可填範圍就跟著變。
MIN_AMOUNT_TWD: float = 10_000.0
MAX_AMOUNT_TWD: float = 100_000_000.0


def fund_currency(result: Any) -> str:
    """這檔基金的**計價**幣別（ISO 三碼）；認不得 → `""`。

    ⛔ **`default=""` 不是 `default="USD"`。** `normalize_ccy` 的預設值是 USD
    （對保單場景合理），但在這裡「沒說」必須維持沒說 —— 上游本來就有 USD 死預設的
    前科（`repositories/fund/sources.py::_src_fundclear_div` 缺欄時填 `"USD"`），
    再疊一層預設就徹底分不出「真的是美元」與「沒人講過」。
    """
    if not isinstance(result, dict):
        return ""
    return normalize_ccy(result.get("currency"), default="", mode="yf")


def dividend_currency(result: Any) -> str:
    """**逐筆配息自己宣告**的幣別；逐列不一致、或有任一列未知 → `""`。

    直接委派 `shared.data_quality.reconcile_row_currencies`（**不自己寫一份**）——
    `ui/views/page_03_research.py::_declared_currency` 走的也是它，
    兩邊對「這組配息能不能誠實宣告單一幣別」必須是同一個答案。
    """
    _rows = result.get("dividends") if isinstance(result, dict) else None
    if not isinstance(_rows, list):
        return ""
    return reconcile_row_currencies(
        [_r.get("currency") for _r in _rows if isinstance(_r, dict)])


def fund_nav(result: Any) -> Optional[float]:
    """最新淨值（原幣）；沒有 → `None`。

    取數順序與舊 ③ / ② **逐字相同**：``metrics["nav"]`` → ``result["nav_latest"]``。

    ⚠️ **刻意寫成 `a if a is not None else b`，不是 `a or b`** ——
    `or` 會把**合法的 0** 當成缺值往下一層退。淨值不可能是 0（§3.2 NAV > 0），
    所以這裡改不改結果一樣；**但同一個檔案下面的年化配息率 0 是「這檔不配息」的真值**，
    兩處用同一種寫法，才不會有人照著上面那行把下面那行也改成 `or`
    （`ui/helpers/fund_grp_health/investment.py` 就地寫著同一段理由）。

    ⛔ **不拿 `result["series"]` 的末值頂替。** 那會讓同一個畫面上出現兩個淨值來源，
    而它們可能不相等（序列可能是合併過的長歷史）。
    """
    if not isinstance(result, dict):
        return None
    _m = result.get("metrics")
    _m = _m if isinstance(_m, dict) else {}
    _nav = _m.get("nav") if _m.get("nav") is not None else result.get("nav_latest")
    _v = safe_float(_nav)
    return _v if (_v is not None and _v > 0) else None


def fx_rate_to_twd(ccy: Any) -> Optional[float]:
    """1 單位 `ccy` 換得到多少台幣；查不到 → `None`（**本模組唯一會出網的地方**）。

    * 台幣計價 → `1.0`，**不打網路**。
    * 幣別認不得 → `None`（**不猜**）。
    * 其餘 → `services.fund_service.get_latest_fx`（L2 facade，內含
      Yahoo → FRED → er-api → Frankfurter 四源 fallback 與 positive-only TTL 快取）。

    ⚠️ **這裡的 `try/except` 是刻意的，而且只在這裡有**：呼叫端
    `ui/views/page_03_research.py` **一個 `except` 都不准有**
    （`tests/test_wf03_research_skeleton.py::test_the_page_has_no_exception_handler_of_its_own`），
    而匯率來源掛掉**不該**讓 NAV／績效／風險那三格一起變成紅框。
    失敗一律 **log 到 stderr ＋ 回 `None`**（§1：留痕、不吞、不猜），
    由呼叫端畫成「這一格算不出來，原因是拿不到匯率」。
    """
    _c = normalize_ccy(ccy, default="", mode="yf")
    if not _c:
        return None
    if _c == TWD:
        return 1.0
    try:
        from services.fund_service import get_latest_fx
        _rate = get_latest_fx(f"{_c}{TWD}=X")
    except Exception as _err:  # noqa: BLE001 —— 理由見 docstring；不吞、有 log
        print(f"[fund_invest_calc] {_c}{TWD} 匯率取得失敗："
              f"{type(_err).__name__}: {_err}", file=sys.stderr)
        return None
    _v = safe_float(_rate)
    return _v if (_v is not None and _v > 0) else None


def _blank(amount: Optional[float], ccy: str, div_ccy: str,
           nav: Optional[float], reason: str) -> dict:
    """算不出來時的回傳骨架 —— **每一個數值欄位都是 `None`，一個都不填佔位值。**"""
    return {
        "amount_twd": amount,
        "currency": ccy,
        "dividend_currency": div_ccy,
        "nav": nav,
        "fx_to_twd": None,
        "amount_ccy": None,
        "units": None,
        "monthly_ccy": None,
        "monthly_twd": None,
        "monthly_units": None,
        "annual_twd": None,
        "income_basis": "",
        "latest_div_per_unit": None,
        "adr_pct": None,
        "adr_source": "",
        "implied_annual_pct": None,
        "income_reconcile": None,
        "units_blocked": reason,
        "income_blocked": reason,
    }


def estimate_monthly_income(
    result: Any,
    amount_twd: Any,
    *,
    fx_lookup: Optional[Callable[[str], Optional[float]]] = None,
) -> dict:
    """投入 `amount_twd` 台幣 → 買得到幾單位、每月大約領多少。

    Parameters
    ----------
    result :
        `services.moneydj_fetcher.auto_fetch_moneydj()` 的回傳（**flat shape**：
        `currency` / `metrics` / `dividends` / `moneydj_div_yield` / `nav_latest`）。
    amount_twd :
        使用者打的台幣金額。`None` / 非數字 / ≤ 0 → :data:`NO_AMOUNT`。
    fx_lookup :
        `ccy -> 1 單位該幣別值多少台幣`。**不傳就等於「查不到匯率」** ——
        本函式因此預設是**純函式**，可以在沒有網路的環境下逐條測。
        台幣計價的基金**不會**用到它（見下）。

    Returns
    -------
    dict
        事實 ＋ 兩個原因欄位。**`units_blocked` / `income_blocked` 為 `""` 才代表那一半算得出來。**
        兩者刻意分開：**買得到幾單位**與**每月領多少**是兩件事，
        後者可能單獨失敗（沒有配息依據、或幣別對不上），此時前者仍然是誠實可用的答案。

    ## ⛔ 幣別衝突為什麼要整個擋掉，而不是「挑一個比較可信的」

    上游有兩個**各自獨立**的 USD 死預設：`_src_fundclear_div` 對**逐筆配息**、
    `_ensure_currency` 對**基金計價幣別**（後者已修、前者沒修）。於是真的會出現
    「基金計價 TWD、逐筆配息宣告 USD」這種畫面 —— `ui/views/page_03_research.py::
    _dividend_caption` 就是為它寫的，它的處置逐字是：
    **「本頁不挑一個宣告（不猜值）· 金額照原幣顯示，不合計、不換算」**。

    本函式沿用**同一個處置**：兩邊都講得出 ISO、但講的不是同一個 → :data:`CCY_CONFLICT`，
    **每月配息一律不算**。理由是量綱（§4.1）：`monthly_dividend_from_records` 拿到的
    「最近一筆實配」若其實是美元、卻被當成台幣乘上匯率 1.0，畫面會印出一個
    **看起來完全正常、實際差三十倍**的月配息金額。

    ⚠️ **「有一邊講不出來」不算衝突**（`nav_currency_verdict` 回 `unknown`）：
    逐筆配息沒有標幣別是常態，此時本函式**照算**，並由 `dividend_currency` 回 `""`
    讓呼叫端把「這裡假設逐筆配息與基金計價同幣別」講給使用者聽。
    **不知道 ≠ 不一致** —— 反過來擋掉，等於把大多數基金的配息試算一起關掉。

    ## 順序（刻意的，不要重排）

    金額 → 幣別 → 淨值 → **最後**才問匯率。匯率是本模組唯一會出網的東西，
    而前三關任一不過都算不出單位數 —— **先擋掉，就不會為了一個必然作廢的結果打網路。**
    """
    _amount = safe_float(amount_twd)
    _ccy = fund_currency(result)
    _div_ccy = dividend_currency(result)
    _nav = fund_nav(result)

    if _amount is None or _amount <= 0:
        return _blank(None, _ccy, _div_ccy, _nav, NO_AMOUNT)
    if not _ccy:
        return _blank(_amount, _ccy, _div_ccy, _nav, NO_CURRENCY)
    if _nav is None:
        return _blank(_amount, _ccy, _div_ccy, _nav, NO_NAV)

    # 台幣計價**不查匯率**（也不需要）；其餘才問 `fx_lookup`。
    _fx = 1.0 if _ccy == TWD else (fx_lookup(_ccy) if fx_lookup else None)
    _fx = safe_float(_fx)
    if _fx is None or _fx <= 0:
        return _blank(_amount, _ccy, _div_ccy, _nav, NO_FX)

    _amount_ccy = _amount / _fx
    _units = _amount_ccy / _nav

    _out = _blank(_amount, _ccy, _div_ccy, _nav, "")
    _out.update({
        "fx_to_twd": _fx,
        "amount_ccy": _amount_ccy,
        "units": _units,
        "units_blocked": "",
    })

    # ── 每月配息：從這裡開始有可能單獨失敗 ────────────────────────────────
    if nav_currency_verdict(_ccy, _div_ccy) == NAV_CCY_MISMATCH:
        _out["income_blocked"] = CCY_CONFLICT
        return _out

    _adr, _adr_src = _resolve_adr_with_fallback(result if isinstance(result, dict) else {})
    _out["adr_pct"] = _adr
    _out["adr_source"] = _adr_src or ""

    _mdiv = monthly_dividend_from_records(
        (result.get("dividends") if isinstance(result, dict) else None) or [],
        _units, _nav, _fx, adr_pct=_adr)
    if not _mdiv.get("source"):
        _out["income_blocked"] = NO_INCOME_BASIS
        return _out

    _monthly_twd = safe_float(_mdiv.get("mon_div_twd"))
    _out.update({
        "monthly_ccy": safe_float(_mdiv.get("mon_div_ccy")),
        "monthly_twd": _monthly_twd,
        "monthly_units": safe_float(_mdiv.get("mon_div_units")),
        "latest_div_per_unit": safe_float(_mdiv.get("latest_div_per_unit")),
        "income_basis": _mdiv.get("source") or "",
        "income_blocked": "",
    })
    if _monthly_twd is not None:
        # 年化 ＝ 月配 × 12。**這是「照這個月推一整年」，不是掛牌的年化配息率** ——
        # 兩者可能不同（季配基金尤其），呼叫端要把差異講出來，不得只印一個。
        _out["annual_twd"] = _monthly_twd * 12.0
        # 這筆錢實際拿到的年化比率（％）—— 使用者的**比較對象**。
        _implied = (_monthly_twd * 12.0) / _amount * 100.0
        _out["implied_annual_pct"] = _implied
        # ⭐ **兩種算法對帳，走既有 SSOT，不自己定容差**（§4.3 / F-RECON-1）：
        #    `services.reconcile.reconcile_dividend_yield` 就是本 repo 對
        #    「配息殖利率的兩種算法對不對得上」的唯一判準（絕對 0.1 個百分點／相對 5%）。
        #    ⚠️ **傳小數不傳百分點** —— `services/fund_service.py` 的既有 caller
        #    就是 `/100.0` 之後才傳，容差是照小數訂的；傳百分點會讓容差整整鬆 100 倍。
        # ⛔ **`source="estimate"` 時這個對帳沒有資訊量，而且必然 agree**：
        #    那條路的月配**就是**用 `adr_pct ÷ 12` 算出來的，兩個數字同源，
        #    「對得上」證明不了任何事。呼叫端必須據此改口，**不得**把它講成驗證通過。
        if _adr is not None:
            _out["income_reconcile"] = reconcile_dividend_yield(
                _implied / 100.0, float(_adr) / 100.0)
    return _out
