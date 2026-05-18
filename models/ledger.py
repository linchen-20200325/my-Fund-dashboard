"""models/ledger.py — 基金帳務 dataclass / DTO 集合（v11.0 從 fund_ledger.py 抽出）

v11.0 分層歸位：純資料型別 + 純計算 method 屬於 Models / DTO Layer。
業務邏輯類別（Ledger / GhostPortfolio / Switch / calculate_xirr）仍在 fund_ledger.py，
未來 C-13 步驟才搬至 services/ledger_service.py。

本檔內容（5 個符號）：
  - _TXN_TYPES         : Transaction.txn_type 合法值 tuple（內部使用）
  - Transaction        : Append-only 事件流水帳（frozen dataclass）
  - FundPosition       : 單一基金持倉狀態（CHUBB 11 欄位 1/2/3/10 + 純計算 method）
  - GhostComparison    : 影子投組對比結果 DTO
  - SwitchResult       : 基金轉換結果 DTO

向後相容：fund_ledger.py 仍 re-export 此 5 個符號，既有 caller
        `from fund_ledger import FundPosition, ...` 零修改。
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date as _date
from typing import Optional


_TXN_TYPES = (
    "subscribe",
    "dividend_cash",
    "dividend_reinvest",
    "switch_out",
    "switch_in",
)


@dataclass(frozen=True)
class Transaction:
    """Append-only 事件流水帳。所有狀態變更皆先記事件，再 update FundPosition。

    `amount_twd` 語意（依 `txn_type` 而定）：
      - subscribe         : 投入 TWD 本金（>0，XIRR 視為流出 = 負現金流）
      - dividend_cash     : 配息實際 TWD 流入（>0，XIRR 視為流入 = 正現金流）
      - dividend_reinvest : None（內部再投資，無現金流）
      - switch_out / switch_in : 移轉的 TWD 歷史成本基底（內部移轉，XIRR 不計入）
    """

    txn_type: str
    txn_date: _date
    amount_twd: Optional[float] = None
    fx_rate: Optional[float] = None
    nav: Optional[float] = None
    div_per_unit: Optional[float] = None
    new_units: Optional[float] = None
    note: str = ""

    def __post_init__(self) -> None:
        if self.txn_type not in _TXN_TYPES:
            raise ValueError(f"unknown txn_type={self.txn_type!r}, expected {_TXN_TYPES}")


@dataclass
class FundPosition:
    """單一基金持倉狀態（CHUBB 11 欄位中的 1/2/3/10 + 累計 TWD 配息）。"""

    fund_code: str
    currency: str = "USD"
    units: float = 0.0
    cost_unit: float = 0.0
    fx_avg: float = 0.0
    cost_unit_with_div: float = 0.0
    dividends_received_twd: float = 0.0

    @property
    def net_investment_twd(self) -> float:
        """(4) 淨投資金額 = cost_unit × units × fx_avg"""
        return self.cost_unit * self.units * self.fx_avg

    def value_orig(self, nav: float) -> float:
        """(6) 參考現值（原幣）= units × nav"""
        return self.units * nav

    def value_twd(self, nav: float, fx: float) -> float:
        """(8) 帳戶價值（TWD）= units × nav × fx"""
        return self.units * nav * fx

    def roi_price(self, nav: float, fx: float) -> float:
        """(9) 帳面報酬率（不含息）= value_twd / net_investment_twd − 1"""
        inv = self.net_investment_twd
        if inv <= 0 or inv != inv:
            return 0.0
        return self.value_twd(nav, fx) / inv - 1

    def roi_total_chubb(self, nav: float, fx: float) -> float:
        """(11) CHUBB 公式版含息報酬率 = value_twd / (units × fx_avg × cost_unit_with_div) − 1"""
        denom = self.units * self.fx_avg * self.cost_unit_with_div
        if denom <= 0 or denom != denom:
            return 0.0
        return self.value_twd(nav, fx) / denom - 1

    def roi_total_cashflow(self, nav: float, fx: float) -> float:
        """含息報酬率（現金流版）= (value_twd + 累計 TWD 配息) / net_investment_twd − 1

        與 CHUBB 公式版差異：本式以實際領到的 TWD 配息為準（含 FX 損益），
        當保單期間 USD/TWD 大幅波動時可能與 CHUBB 公式版有細微差距。
        """
        inv = self.net_investment_twd
        if inv <= 0 or inv != inv:
            return 0.0
        return (self.value_twd(nav, fx) + self.dividends_received_twd) / inv - 1


@dataclass
class GhostComparison:
    """影子投組對比輸出。"""

    value_actual_twd: float
    value_ghost_twd: float
    excess_twd: float
    excess_pct: float
    verdict: str
    action: str


@dataclass
class SwitchResult:
    """基金轉換結果。"""

    units_redeemed_from: float           # A 端贖回單位數
    redeem_amount_orig: float             # 贖回金額（A 幣，扣費前）
    fee_orig: float                       # 轉換費（A 幣計）
    proceeds_after_fee_orig: float        # 扣費後（A 幣）
    proceeds_in_to_currency: float        # 換到 B 幣後（同幣別 = 上式）
    units_added_to: float                 # B 端新增單位數
    fx_avg_inherited: float               # B 端新單位的 fx_avg（同幣別 = A.fx_avg；跨幣別 = 當日 B 對 TWD）
    cost_unit_to_basis: float             # B 端新單位的 cost_unit（TWD 守恆反推）
    cost_unit_with_div_to_basis: float    # B 端新單位的 cost_unit_with_div（保留 A 含息折扣比例）
    twd_cost_basis_transferred: float     # 移轉的 TWD 歷史成本基底（守恆量）
    cross_rate: float                     # 交叉匯率（同幣別 = 1.0）
