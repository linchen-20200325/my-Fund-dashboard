"""投資試算的算式層 —— 回答「我投 X 元台幣，每個月大概領多少？」。

客戶 2026-09-08 拍板：**投資試算定案搬移至 ⑧（標的探索）的單一基金深度區塊**
（⑥ 只留「現有持倉的每月配息推估總額」）。本模組是那一塊的**唯一算式來源**。

⛔ **本模組不發明任何算法。** 四個關鍵值全部沿用既有 SSOT，只是把它們串起來：

===================== ================================================================
要算的東西             走哪一個既有 SSOT
===================== ================================================================
計價幣別正規化         :func:`services.currency.normalize_ccy` ＋
                      :func:`shared.data_quality.normalize_iso_ccy`
                      —— L2 解別名、L0 收 ISO，見 :func:`comparable_ccy`
                      ⚠️ ~~``mode="yf"``，與舊 ③ `ui/tab2_single_fund.py` 及 ②
                      `ui/helpers/fund_grp_health/investment.py` 同一個模式~~
                      → **2026-09-08 更正（有意識的更正，不是漏刪）**：
                      那個模式**只適合拿去查匯率**，不適合拿去比對或顯示。
                      舊表述的理由仍然成立（`CNHTWD=X` 確實比 `CNYTWD=X` 可靠，
                      而那半邊**原封保留在** :func:`fx_rate_to_twd`）；
                      **被權衡掉的是它的射程** —— 它被同時當成
                      「比對用」與「畫面顯示用」的幣別，於是人民幣基金
                      被自己誣告「幣別對不上」。事故經過見 :func:`comparable_ccy`。
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
    normalize_iso_ccy,
    reconcile_row_currencies,
)

__all__ = [
    "ADR_FROM_RECORDS",
    "ADR_LOCAL_RATE",
    "ADR_OFFICIAL",
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
    "comparable_ccy",
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

# ── 年化配息率**是哪裡來的**（`_resolve_adr_with_fallback` 的 source label 原值）──
#
# ⭐ **這三個常數是 2026-09-08 補的，補的是一個真實的假話。**
# `adr_pct` 有三層 fallback，**只有第一層是「掛牌的」**，另外兩層是本地拿
# **同一批配息紀錄**回推出來的。畫面（`ui/views/page_03_research.py::_invest_compare`）
# 卻**無條件**寫「對照這一檔**掛牌的**年化配息率」——
# 於是一個自算的 1.44% 被講成官方公布值，而且差異原因被講成
# 「最近一筆配息不是常態」，**真因是那個 12 個月的分母裡只裝了 3 個月的資料**。
# §1：**錯誤的數字比沒有數字更危險**；把「我自己算的」講成「官方公布的」是其中最貴的一種。
#
# ⚠️ **具名而不 inline**（§3.3）：這三個字串是 `services/health/dividend.py::
# _resolve_adr_with_fallback` 的回傳值，本檔與 UI 都要靠它們分辨來源。
# 兩邊若各自寫死字面值，上游改字時**畫面會靜靜地退回講官方話**。
# 它們與上游必須一致這件事由
# `tests/test_wf03_research_invest_calc.py::test_the_payout_rate_source_labels_match_the_resolver` 釘住。
#: MoneyDJ wb05 **官方掛牌**值 —— 三層裡**唯一**真的是「掛牌的」那一層。
ADR_OFFICIAL: str = "moneydj_wb05"
#: 上游 `metrics.annual_div_rate` —— **本地自算**（`calc_metrics` 拿配息紀錄推的），
#: 不是掛牌值。`services/fund_service.py` 就地自陳「本算 fallback；主源 moneydj_div_yield wb05」。
ADR_LOCAL_RATE: str = "metrics_annual_div_rate"
#: 把**同一批**逐筆配息近 12 個月加總 ÷ 淨值回推 —— **本地自算，而且與月配同源**。
#: ⚠️ 它有一個**畫面上看不出來的**失效模式：配息紀錄不滿一年時，
#: 分母是 12 個月、分子只有實際有紀錄的那幾個月 ⇒ 這個率**系統性偏低**。
ADR_FROM_RECORDS: str = "divs_12m_sum"

#: 試算金額的預設值。**走 `dividend_calc.DEFAULT_PRINCIPAL_TWD` 這個既有 SSOT**，
#: 不另寫一個 100 萬 —— 全站「預設本金」只准有一個真相源（§2.1）。
DEFAULT_AMOUNT_TWD: float = DEFAULT_PRINCIPAL_TWD
#: 輸入框的下界／上界。沿用舊 ③ `ui/tab2_single_fund.py` 投資試算那一格的既有值。
#: ⚠️ 具名而不 inline（§3.3）—— 它們一改，畫面上那個輸入框的可填範圍就跟著變。
MIN_AMOUNT_TWD: float = 10_000.0
MAX_AMOUNT_TWD: float = 100_000_000.0


def comparable_ccy(raw: Any) -> str:
    """任何一種幣別宣告 → **比對／顯示用**的 ISO 三碼；認不得 → `""`。

    ⭐ **本模組裡「拿來比對」與「拿來給人看」的幣別，一律只准經過這一個函式。**
    拿去**查匯率**的那個代碼是另一回事 —— 它住在 :func:`fx_rate_to_twd`，
    那裡才用 ``mode="yf"``。**兩者不必相同，而且刻意不同**：
    `CNHTWD=X` 在 yfinance 比 `CNYTWD=X` 可靠（`services/currency.py` 就地寫明），
    但 `CNH` 這個代碼**基金公司沒用過、使用者也沒在本頁其他地方看過**，
    不該印到畫面上、更不該拿去跟配息紀錄比對。

    ## ⛔ 這個函式是 2026-09-08 修一個真實 bug 加的 —— 別再繞過它

    在此之前 :func:`fund_currency` 走 ``mode="yf"``（人民幣 → **CNH**），
    而 :func:`dividend_currency` 經 `reconcile_row_currencies` 走 L0
    `normalize_iso_ccy`（**CNY 原樣保留**）。**兩個不同命名空間的值被丟進同一個比對器**：
    一檔人民幣基金、配息紀錄還誠實標了 `CNY` → ``nav_currency_verdict("CNH", "CNY")``
    → **mismatch** → 每月配息整段被關掉，理由是一句**假的**「兩邊對不上」。
    同一個畫面上，配息表底下卻寫著「全部以 CNY 計價」——
    **兩句都是本頁印的，而且互相矛盾**（§1：錯誤的數字比沒有數字更危險）。

    ⛔ **這不是「人民幣特例」，所以修法也不是特例。** 病灶是
    **同一件事被兩個不同的正規化器算了兩次**；在比對器裡放行人民幣，
    只會讓下一個雙代碼幣別再犯一次。**修的是命名空間本身。**

    寫法**沿用本 repo 既有慣例，不發明第三種**：L2 先解別名 → L0 再收 ISO。
    `services/nav_history_store.py` 逐字就是
    ``normalize_iso_ccy(normalize_ccy(_raw, default=""))``；而 L0 `normalize_iso_ccy`
    自己的 docstring 也寫著「中文別名的正規化是 L2 `services.currency.normalize_ccy`
    的職責…**呼叫端能拿到 L2 時請先過那一層**」—— 本模組是 L2，拿得到。

    ⛔ **`default=""` 不是 `default="USD"`。** `normalize_ccy` 的預設值是 USD
    （對保單場景合理），但在這裡「沒說」必須維持沒說 —— 上游本來就有 USD 死預設的
    前科（`repositories/fund/sources.py::_src_fundclear_div` 缺欄時填 `"USD"`），
    再疊一層預設就徹底分不出「真的是美元」與「沒人講過」。
    """
    return normalize_iso_ccy(normalize_ccy(raw, default=""))


def fund_currency(result: Any) -> str:
    """這檔基金的**計價**幣別（ISO 三碼）；認不得 → `""`。

    ⚠️ 走 :func:`comparable_ccy` —— 它同時是**畫面上印的那個代碼**
    （算式區、配息說明、灰態理由都讀這個值），所以它必須是使用者認得的 ISO，
    不是 yfinance 的報價代碼。理由與事故經過見該函式。
    """
    if not isinstance(result, dict):
        return ""
    return comparable_ccy(result.get("currency"))


def dividend_currency(result: Any) -> str:
    """**逐筆配息自己宣告**的幣別；逐列不一致、或有任一列未知 → `""`。

    一致性判定**仍然委派** `shared.data_quality.reconcile_row_currencies`
    （**不自己寫一份**）—— `ui/views/page_03_research.py::_declared_currency`
    走的也是它，兩邊對「這組配息能不能誠實宣告單一幣別」必須是同一個答案。

    ⭐ **改變的只有「餵進去之前先過 L2」**（2026-09-08）：逐列先過
    :func:`comparable_ccy`，讓它與 :func:`fund_currency` **落在同一個命名空間**。
    事故經過見 :func:`comparable_ccy` —— 兩邊各自正規化，是那個 bug 的成因本身。

    ⚠️ **這一步順帶讓「中文宣告」變成看得見的**：逐列寫「人民幣」以前會被 L0
    當成未知（→ `""` → 不比對、照算），現在收成 `CNY` 會**真的參與比對**。
    方向是**變嚴**：一檔美元基金、逐列卻寫「人民幣」，以前靜靜算下去，現在擋住。
    """
    _rows = result.get("dividends") if isinstance(result, dict) else None
    if not isinstance(_rows, list):
        return ""
    return reconcile_row_currencies(
        [comparable_ccy(_r.get("currency")) for _r in _rows if isinstance(_r, dict)])


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

    # ⚠️ **不變式（呼叫端靠它，改動前先讀）**：走到這一行時 `_fx > 0` 已經確定
    #    （上面那道 :data:`NO_FX` 閘門擋掉了 `None` 與 `<= 0`），而
    #    `monthly_dividend_from_records` 只在 `fx > 0` 時才填 `mon_div_twd`
    #    —— 所以 `income_blocked == ""` ⇒ `monthly_twd is not None`。
    # ⛔ 若哪天有人放寬那道閘門，這裡會變成「宣告成功卻沒有金額」，
    #    畫面上會是 `None` 進格式化字串**當場炸掉** —— 那是**對的**（§1：
    #    契約破了要炸給 `safe_section()` 畫紅框），**不要**在這裡補一個 `or 0`。
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
