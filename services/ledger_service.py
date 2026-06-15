"""services/ledger_service.py — 基金帳務業務 Service Layer
（v11.0 C-13 從 fund_ledger.py 搬入；dataclass 已先 A-4 搬至 models/ledger.py）

對齊 CHUBB 安達人壽 11 欄位公式（圖片實證）：
  (1)  cost_unit             平均買入單位成本（原幣）
  (2)  units                 持有單位數
  (3)  fx_avg                平均買入匯率（如 USD→TWD）
  (4)  net_investment_twd    淨投資金額 = (1) × (2) × (3)
  (5)  nav_current           原幣淨值（呼叫端從快照傳入）
  (6)  value_orig            參考現值（原幣）= (2) × (5)
  (7)  fx_current            參考匯率（呼叫端從快照傳入）
  (8)  value_twd             帳戶價值（TWD）= (6) × (7)
  (9)  roi_price             帳面報酬率（不含息）= (8) / (4) − 1
  (10) cost_unit_with_div    平均買入含息單位成本（每筆現金配息後依虛擬再投資下調）
  (11) roi_total             含息報酬率 = (8) / ((2) × (3) × (10)) − 1

§0 全面排除 ETF。§4 零快取（無 @st.cache_data）。
Phase 1：FundPosition / Ledger / GhostPortfolio + subscribe / dividend_cash / dividend_reinvest。
Phase 2：Switch（同幣別繼承 fx_avg / 跨幣別記交叉匯率）+ XIRR（scipy.optimize.brentq）。

v11.0 分層歸位：本檔屬於 Service Layer，業務類別（狀態變更 / 編排）。
資料型別 dataclass（Transaction / FundPosition / GhostComparison / SwitchResult）在 models/ledger.py。
向後相容：根目錄 fund_ledger.py 保留 shim re-export，既有 caller 零修改。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as _date
from typing import Optional

# 從 models 層取資料型別（dataclass / DTO）
from models.ledger import (  # noqa: F401  re-export so callers can `from services.ledger_service import Transaction, ...`
    _TXN_TYPES,
    Transaction,
    FundPosition,
    GhostComparison,
    SwitchResult,
)


# v19.71: 抽到 services/currency 共用（user 反映「重複造輪子」實證 — 3 個 Tab 各寫一份
# 同款字典導致組合健診漏接 → 截圖 bug「FX 美元TWD 抓不到」）。本檔保留向後相容 alias。
from services.currency import CCY_NORMALIZE as _CCY_NORMALIZE, normalize_ccy as _norm_ccy_pure  # noqa: F401


@dataclass
class Ledger:
    """事件流水帳：append-only Transaction list + 即時持倉快照。

    使用方式：
        led = Ledger(fund_code="BGUPC029", currency="USD")
        led.subscribe(amount_twd=300000, fx_rate=30.0, nav=10.0, txn_date=date(2026,1,15))
        led.dividend_cash(div_per_unit=0.5, fx_rate=31.0, txn_date=date(2026,3,15), nav_at_div=11.0)
        print(led.position.roi_total_chubb(nav=12.0, fx=31.5))
    """

    fund_code: str
    currency: str = "USD"
    transactions: list[Transaction] = field(default_factory=list)
    position: FundPosition = field(init=False)

    def __post_init__(self) -> None:
        self.position = FundPosition(fund_code=self.fund_code, currency=self.currency)

    def subscribe(self, amount_twd: float, fx_rate: float, nav: float, txn_date: _date) -> float:
        """買入 / 追加投入。回傳本次取得單位數。

        加權平均：cost_unit、fx_avg、cost_unit_with_div 三者皆以單位數加權
        （新單位 cost_unit_with_div 採當日 nav，與 cost_unit 相同——首次買入時兩者必相等）。
        """
        if amount_twd <= 0 or fx_rate <= 0 or nav <= 0:
            raise ValueError("subscribe: amount_twd / fx_rate / nav must all be positive")
        new_units = (amount_twd / fx_rate) / nav
        old_units = self.position.units
        if old_units <= 0:
            self.position.cost_unit = nav
            self.position.fx_avg = fx_rate
            self.position.cost_unit_with_div = nav
        else:
            tot = old_units + new_units
            self.position.cost_unit = (
                old_units * self.position.cost_unit + new_units * nav
            ) / tot
            self.position.fx_avg = (
                old_units * self.position.fx_avg + new_units * fx_rate
            ) / tot
            self.position.cost_unit_with_div = (
                old_units * self.position.cost_unit_with_div + new_units * nav
            ) / tot
        self.position.units = old_units + new_units
        self.transactions.append(Transaction(
            txn_type="subscribe", txn_date=txn_date,
            amount_twd=amount_twd, fx_rate=fx_rate, nav=nav,
        ))
        return new_units

    def dividend_cash(
        self,
        div_per_unit: float,
        fx_rate: float,
        txn_date: _date,
        nav_at_div: Optional[float] = None,
    ) -> float:
        """配現金。回傳本次 TWD 配息金額。

        cost_unit_with_div 下調公式（CHUBB 規範）：
            virtual_units = units × div_per_unit / nav_at_div
            new_cost_with_div = old_cost_with_div × units / (units + virtual_units)

        虛擬再投資單位「成本 = 0」（因配息來自我們自己的錢，不算新投入）。
        若 nav_at_div 為 None，僅累計 TWD 配息、不下調 cost_unit_with_div。
        """
        if self.position.units <= 0:
            raise ValueError("dividend_cash: no holdings to receive dividend")
        if div_per_unit <= 0 or fx_rate <= 0:
            raise ValueError("dividend_cash: div_per_unit / fx_rate must be positive")
        cash_orig = self.position.units * div_per_unit
        cash_twd = cash_orig * fx_rate
        self.position.dividends_received_twd += cash_twd
        if nav_at_div is not None and nav_at_div > 0:
            virtual_units = self.position.units * div_per_unit / nav_at_div
            denom = self.position.units + virtual_units
            if denom > 0:
                self.position.cost_unit_with_div = (
                    self.position.cost_unit_with_div * self.position.units / denom
                )
        self.transactions.append(Transaction(
            txn_type="dividend_cash", txn_date=txn_date,
            amount_twd=cash_twd,
            div_per_unit=div_per_unit, fx_rate=fx_rate, nav=nav_at_div,
        ))
        return cash_twd

    def dividend_reinvest(self, new_units: float, nav_at_div: float, txn_date: _date) -> None:
        """配單位（再投資）。units 增加，cost_unit / cost_unit_with_div 加權平均，fx_avg 不變。

        實務上保單以「除息日淨值」作為新單位成本依據，本實作採此嚴格作法。
        """
        if new_units <= 0 or nav_at_div <= 0:
            raise ValueError("dividend_reinvest: new_units / nav_at_div must be positive")
        old_units = self.position.units
        if old_units <= 0:
            raise ValueError("dividend_reinvest: no holdings")
        tot = old_units + new_units
        self.position.cost_unit = (
            old_units * self.position.cost_unit + new_units * nav_at_div
        ) / tot
        self.position.cost_unit_with_div = (
            old_units * self.position.cost_unit_with_div + new_units * nav_at_div
        ) / tot
        self.position.units = tot
        self.transactions.append(Transaction(
            txn_type="dividend_reinvest", txn_date=txn_date,
            new_units=new_units, nav=nav_at_div,
        ))

    # ── Phase 3: JSON round-trip ──────────────────────────────────────
    def to_dict(self) -> dict:
        """序列化為 JSON-safe dict。日期轉 ISO 字串，None 保留。"""
        return {
            "fund_code": self.fund_code,
            "currency": self.currency,
            "transactions": [
                {
                    "txn_type": t.txn_type,
                    "txn_date": t.txn_date.isoformat(),
                    "amount_twd": t.amount_twd,
                    "fx_rate": t.fx_rate,
                    "nav": t.nav,
                    "div_per_unit": t.div_per_unit,
                    "new_units": t.new_units,
                    "note": t.note,
                }
                for t in self.transactions
            ],
            "position": {
                "units": self.position.units,
                "cost_unit": self.position.cost_unit,
                "fx_avg": self.position.fx_avg,
                "cost_unit_with_div": self.position.cost_unit_with_div,
                "dividends_received_twd": self.position.dividends_received_twd,
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Ledger":
        """從 to_dict() 輸出反向組回 Ledger（含 Transactions + Position state）。

        注意：不重 replay 計算，直接還原 position 快照（避免浮點累積誤差）。
        """
        led = cls(fund_code=data["fund_code"], currency=data.get("currency", "USD"))
        for raw in data.get("transactions", []):
            led.transactions.append(Transaction(
                txn_type=raw["txn_type"],
                txn_date=_date.fromisoformat(raw["txn_date"]),
                amount_twd=raw.get("amount_twd"),
                fx_rate=raw.get("fx_rate"),
                nav=raw.get("nav"),
                div_per_unit=raw.get("div_per_unit"),
                new_units=raw.get("new_units"),
                note=raw.get("note", ""),
            ))
        pos = data.get("position", {})
        led.position.units = float(pos.get("units", 0.0))
        led.position.cost_unit = float(pos.get("cost_unit", 0.0))
        led.position.fx_avg = float(pos.get("fx_avg", 0.0))
        led.position.cost_unit_with_div = float(pos.get("cost_unit_with_div", 0.0))
        led.position.dividends_received_twd = float(pos.get("dividends_received_twd", 0.0))
        return led


# GhostComparison 已搬至 models/ledger.py (v11.0 A-4)，由本檔頂部 re-export
class GhostPortfolio:
    """影子投組對比：「如果當初沒賣 A、那筆錢繼續留 A、會比現在 B 好還是差？」

    使用方式：
        actual_b = led_b.position
        ghost_a  = ledger_replay_if_kept_A(...)  # 由呼叫端事先建立
        result = GhostPortfolio.compare(actual_b, nav_b, fx_b, ghost_a, nav_a, fx_a)
    """

    @staticmethod
    def compare(
        actual_b: FundPosition, nav_b: float, fx_b: float,
        ghost_a: FundPosition, nav_a: float, fx_a: float,
    ) -> GhostComparison:
        v_b = actual_b.value_twd(nav_b, fx_b) + actual_b.dividends_received_twd
        v_a = ghost_a.value_twd(nav_a, fx_a) + ghost_a.dividends_received_twd
        diff = v_b - v_a
        pct = (diff / v_a) if v_a > 0 else 0.0
        if pct > 0.005:
            verdict = "✅ 此次轉換創造超額報酬"
            action = f"轉換 B 跑贏 A {pct:+.2%}，可繼續持有"
        elif pct < -0.005:
            verdict = "❌ 機會成本損失"
            action = f"轉換 B 落後 A {pct:+.2%}，下次轉換前重新評估決策依據"
        else:
            verdict = "≈ 持平"
            action = f"兩組績效接近（{pct:+.2%}），難以判定優劣，繼續觀察"
        return GhostComparison(
            value_actual_twd=v_b,
            value_ghost_twd=v_a,
            excess_twd=diff,
            excess_pct=pct,
            verdict=verdict,
            action=action,
        )


# ─── Phase 2: Switching ────────────────────────────────────────────────────
# SwitchResult 已搬至 models/ledger.py (v11.0 A-4)，由本檔頂部 re-export


class Switch:
    """基金轉換（A → B）。

    同幣別（如 USD → USD）：
        Switch.switch_same_currency(led_a, led_b, units_to_redeem,
                                     nav_a_redeem, nav_b_buy, fee_orig=…, txn_date=…)
        → B 的 fx_avg 嚴格繼承 A 的 fx_avg，TWD 視角損益不失真。

    跨幣別（如 USD → EUR）：
        Switch.switch_cross_currency(led_a, led_b, units_to_redeem,
                                      nav_a_redeem, nav_b_buy,
                                      cross_rate=USD_per_EUR, fx_to_at_switch_twd=EUR_TWD,
                                      fee_orig=…, txn_date=…)
        → B 的 fx_avg 採當日 B 幣對 TWD 即期，記錄交叉匯率。

    通用會計規則（兩種模式皆適用）：
      - A 端：cost_unit / fx_avg / cost_unit_with_div 皆**不變**（加權平均按比例贖回保持），units 減少
      - 費用以 A 幣計、不影響歷史 TWD 成本 → 費用造成 B 端 units 變少 → ROI 自動反映費用
      - B 端 cost_unit 反推：使 net_investment_twd 守恆
            cost_unit_b = (n_redeem × cost_unit_a × fx_avg_a) / (n_added × fx_avg_b)
      - B 端 cost_unit_with_div 保留 A 的含息折扣比例：
            ratio = cost_unit_with_div_a / cost_unit_a
            cost_unit_with_div_b = cost_unit_b × ratio
    """

    @staticmethod
    def switch_same_currency(
        ledger_from: Ledger,
        ledger_to: Ledger,
        units_to_redeem: Optional[float],
        nav_from_redeem: float,
        nav_to_buy: float,
        fee_orig: float,
        txn_date: _date,
    ) -> SwitchResult:
        # v18.245: 引擎層自己 normalize 後比對，UI/caller 任何漏網（舊 ledger
        # 殘留中文「美元」/ hydration 漏 mutate）到這裡都被攔住。同步寫回
        # ledger.currency + position.currency 避免後續 transactions 殘留舊值。
        _a = _norm_ccy_pure(ledger_from.currency)
        _b = _norm_ccy_pure(ledger_to.currency)
        if _a != _b:
            raise ValueError(
                f"switch_same_currency: 幣別不符 "
                f"({ledger_from.currency}→{_a} vs {ledger_to.currency}→{_b})；"
                f"請改用 switch_cross_currency()"
            )
        ledger_from.currency = _a
        ledger_to.currency = _b
        if getattr(ledger_from, "position", None) is not None:
            ledger_from.position.currency = _a
        if getattr(ledger_to, "position", None) is not None:
            ledger_to.position.currency = _b
        return Switch._do_switch(
            ledger_from=ledger_from, ledger_to=ledger_to,
            units_to_redeem=units_to_redeem,
            nav_from_redeem=nav_from_redeem, nav_to_buy=nav_to_buy,
            cross_rate=1.0, fx_to_at_switch_twd=None,
            fee_orig=fee_orig, txn_date=txn_date,
        )

    @staticmethod
    def switch_cross_currency(
        ledger_from: Ledger,
        ledger_to: Ledger,
        units_to_redeem: Optional[float],
        nav_from_redeem: float,
        nav_to_buy: float,
        cross_rate: float,
        fx_to_at_switch_twd: float,
        fee_orig: float,
        txn_date: _date,
    ) -> SwitchResult:
        # v18.245: 對稱對待 — normalize 後再比對 + 同步寫回
        _a = _norm_ccy_pure(ledger_from.currency)
        _b = _norm_ccy_pure(ledger_to.currency)
        if _a == _b:
            raise ValueError(
                f"switch_cross_currency: 幣別相同 "
                f"({ledger_from.currency}→{_a})；"
                f"請改用 switch_same_currency()"
            )
        ledger_from.currency = _a
        ledger_to.currency = _b
        if getattr(ledger_from, "position", None) is not None:
            ledger_from.position.currency = _a
        if getattr(ledger_to, "position", None) is not None:
            ledger_to.position.currency = _b
        if cross_rate <= 0 or fx_to_at_switch_twd <= 0:
            raise ValueError("switch_cross_currency: cross_rate / fx_to_at_switch_twd 必須為正")
        return Switch._do_switch(
            ledger_from=ledger_from, ledger_to=ledger_to,
            units_to_redeem=units_to_redeem,
            nav_from_redeem=nav_from_redeem, nav_to_buy=nav_to_buy,
            cross_rate=cross_rate, fx_to_at_switch_twd=fx_to_at_switch_twd,
            fee_orig=fee_orig, txn_date=txn_date,
        )

    @staticmethod
    def _do_switch(
        ledger_from: Ledger,
        ledger_to: Ledger,
        units_to_redeem: Optional[float],
        nav_from_redeem: float,
        nav_to_buy: float,
        cross_rate: float,
        fx_to_at_switch_twd: Optional[float],
        fee_orig: float,
        txn_date: _date,
    ) -> SwitchResult:
        if ledger_from.position.units <= 0:
            raise ValueError("switch: 來源 ledger 無持倉")
        if nav_from_redeem <= 0 or nav_to_buy <= 0:
            raise ValueError("switch: NAV 必須為正")
        if fee_orig < 0:
            raise ValueError("switch: fee_orig 必須 ≥ 0")

        max_units = ledger_from.position.units
        if units_to_redeem is None:
            n_redeem = max_units
        else:
            if units_to_redeem <= 0 or units_to_redeem > max_units + 1e-9:
                raise ValueError(
                    f"switch: units_to_redeem={units_to_redeem} 超出範圍 (max={max_units})"
                )
            n_redeem = min(units_to_redeem, max_units)

        redeem_amount_orig = n_redeem * nav_from_redeem
        proceeds_after_fee_orig = redeem_amount_orig - fee_orig
        if proceeds_after_fee_orig <= 0:
            raise ValueError(
                f"switch: 費用 {fee_orig} 超過贖回金額 {redeem_amount_orig}"
            )

        proceeds_in_to_currency = proceeds_after_fee_orig * cross_rate
        n_added = proceeds_in_to_currency / nav_to_buy

        cost_unit_a = ledger_from.position.cost_unit
        fx_avg_a = ledger_from.position.fx_avg
        cost_unit_with_div_a = ledger_from.position.cost_unit_with_div
        twd_cost_basis = n_redeem * cost_unit_a * fx_avg_a

        # B 端 fx_avg：同幣別繼承 A，跨幣別採當日即期
        fx_avg_b_new = fx_avg_a if fx_to_at_switch_twd is None else fx_to_at_switch_twd

        # B 端 cost_unit：TWD 成本守恆反推
        if n_added > 0 and fx_avg_b_new > 0:
            cost_unit_b_new = twd_cost_basis / (n_added * fx_avg_b_new)
        else:
            cost_unit_b_new = nav_to_buy

        # B 端 cost_unit_with_div：保留 A 的含息折扣比例
        ratio_with_div = (
            cost_unit_with_div_a / cost_unit_a if cost_unit_a > 0 else 1.0
        )
        cost_unit_with_div_b_new = cost_unit_b_new * ratio_with_div

        # 更新 A 端：units 減少；cost_unit / fx_avg / cost_unit_with_div 不變
        ledger_from.position.units -= n_redeem
        if ledger_from.position.units < 1e-9:
            ledger_from.position.units = 0.0
        ledger_from.transactions.append(Transaction(
            txn_type="switch_out", txn_date=txn_date,
            new_units=-n_redeem, nav=nav_from_redeem,
            amount_twd=twd_cost_basis,
            note=f"switch to {ledger_to.fund_code}",
        ))

        # 更新 B 端：加權平均合併
        old_units_b = ledger_to.position.units
        if old_units_b <= 0:
            ledger_to.position.cost_unit = cost_unit_b_new
            ledger_to.position.fx_avg = fx_avg_b_new
            ledger_to.position.cost_unit_with_div = cost_unit_with_div_b_new
        else:
            tot = old_units_b + n_added
            ledger_to.position.cost_unit = (
                old_units_b * ledger_to.position.cost_unit + n_added * cost_unit_b_new
            ) / tot
            ledger_to.position.fx_avg = (
                old_units_b * ledger_to.position.fx_avg + n_added * fx_avg_b_new
            ) / tot
            ledger_to.position.cost_unit_with_div = (
                old_units_b * ledger_to.position.cost_unit_with_div
                + n_added * cost_unit_with_div_b_new
            ) / tot
        ledger_to.position.units = old_units_b + n_added
        ledger_to.transactions.append(Transaction(
            txn_type="switch_in", txn_date=txn_date,
            new_units=n_added, nav=nav_to_buy,
            amount_twd=twd_cost_basis,
            note=f"switch from {ledger_from.fund_code} (cross_rate={cross_rate})",
        ))

        return SwitchResult(
            units_redeemed_from=n_redeem,
            redeem_amount_orig=redeem_amount_orig,
            fee_orig=fee_orig,
            proceeds_after_fee_orig=proceeds_after_fee_orig,
            proceeds_in_to_currency=proceeds_in_to_currency,
            units_added_to=n_added,
            fx_avg_inherited=fx_avg_b_new,
            cost_unit_to_basis=cost_unit_b_new,
            cost_unit_with_div_to_basis=cost_unit_with_div_b_new,
            twd_cost_basis_transferred=twd_cost_basis,
            cross_rate=cross_rate,
        )


# ─── Phase 2: XIRR（資金內部報酬率）────────────────────────────────────────


def calculate_xirr(
    transactions: list[Transaction],
    current_value_twd: float,
    today: _date,
    *,
    guess_low: float = -0.99,
    guess_high: float = 10.0,
) -> float:
    """從 ledger 交易史 + 終值計算 XIRR（年化內部報酬率，TWD 視角）。

    現金流定義（與帳面報酬率不同，反映時間價值）：
      - subscribe         : −amount_twd（流出使用者口袋）
      - dividend_cash     : +amount_twd（流入使用者口袋）
      - dividend_reinvest : 0（內部再投資，無外部現金流）
      - switch_*          : 0（內部移轉，不產生外部現金流）
      - 終值              : +current_value_twd（觀念上 t=today 全部贖回）

    回傳：年化 XIRR（小數，0.05 = 5%）；無解（單向現金流 / scipy 缺失 / 無法 bracket）回傳 NaN 或 0.0。
    """
    cash_flows: list[tuple[float, _date]] = []
    for t in transactions:
        if t.amount_twd is None:
            continue
        if t.txn_type == "subscribe":
            cash_flows.append((-float(t.amount_twd), t.txn_date))
        elif t.txn_type == "dividend_cash":
            cash_flows.append((float(t.amount_twd), t.txn_date))

    if current_value_twd > 0:
        cash_flows.append((float(current_value_twd), today))

    if len(cash_flows) < 2:
        return 0.0
    if not (any(cf[0] > 0 for cf in cash_flows) and any(cf[0] < 0 for cf in cash_flows)):
        return 0.0

    d0 = min(cf[1] for cf in cash_flows)

    def _npv(r: float) -> float:
        s = 0.0
        for amt, d in cash_flows:
            yrs = (d - d0).days / 365.0
            s += amt / ((1.0 + r) ** yrs)
        return s

    try:
        from scipy.optimize import brentq
        return float(brentq(_npv, guess_low, guess_high, xtol=1e-7, maxiter=200))
    except ImportError:
        pass  # 改走純 Python bisection
    except (ValueError, RuntimeError):
        return float("nan")

    # Bisection fallback（scipy 缺席時備援）
    fa, fb = _npv(guess_low), _npv(guess_high)
    if fa * fb > 0:
        return float("nan")
    a, b = guess_low, guess_high
    for _ in range(200):
        c = (a + b) / 2.0
        fc = _npv(c)
        if abs(fc) < 1e-7 or (b - a) / 2.0 < 1e-9:
            return float(c)
        if fc * fa < 0:
            b, fb = c, fc
        else:
            a, fa = c, fc
    return float((a + b) / 2.0)
