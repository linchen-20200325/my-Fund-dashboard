"""v19.119 — Canonical 吃本金核心判定(零 IO 純函式)。

抽出三套 wrapper 散在不同檔的「核心判定」共同邏輯,集中 SSOT。

設計
----
canonical 只負責**核心數學判定** — `is_eating = total_return < dividend_yield`,
不做 3/4/5 級分類(各 wrapper UI 需求不同,合理保留)。
未來若要改判定定義(例如加 tolerance / 加 NAV 趨勢因子),只改本檔 1 處。

對外 API
========
- `EatingPrincipalCore`:dataclass,canonical 判定結果
- `classify_eating_principal(total_return_pct, dividend_yield_pct)`:核心判定函式

委派 wrapper(各自服務不同 UI 需求,output schema 不變):
- `services.portfolio_service.dividend_safety` — 5 級 + nav_warning + 字串 message
- `services.fund_service.calc_health_from_manual` — 4 級 + 自算 NAV/配息 chain
- `services.fund_dividend_calculator.div_health_light_for_pair` — 3 色燈 tuple
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass(frozen=True)
class EatingPrincipalCore:
    """Canonical 吃本金判定結果。

    欄位
    ----
    is_data_missing : bool
        任一 input 為 None / NaN / 非數值 → True(caller 應顯示「資料不足」)
    is_no_dividend : bool
        dividend_yield_pct ≤ 0(無配息基金 → 不適用吃本金概念,is_eating=False)
    is_eating : bool
        核心判定:total_return_pct < dividend_yield_pct(僅當 is_data_missing=False
        且 is_no_dividend=False 時有意義;否則為 False)
    total_return_pct : float | None
        輸入透傳(資料缺失時為 None)
    dividend_yield_pct : float | None
        輸入透傳(資料缺失時為 None)
    coverage_ratio : float | None
        含息報酬 / 配息率(若 div > 0;否則 None)。
        portfolio_service.dividend_safety 用此做 5 級分類。
    gap_pct : float | None
        配息率 - 含息報酬(正數 = 吃本金深度;若任一缺則 None)。
        fund_dividend_calculator.div_health_light_for_pair 用此 vs warn_gap 做 3 級。
    real_return_pct : float | None
        含息報酬 - 配息率(= -gap_pct)。
        fund_service.calc_health_from_manual 用此做 4 級分類。

    §1 fail loud:資料缺失 → is_data_missing=True 而非偽造數值;caller 顯示「資料不足」。
    """
    is_data_missing: bool
    is_no_dividend: bool
    is_eating: bool
    total_return_pct: Optional[float]
    dividend_yield_pct: Optional[float]
    coverage_ratio: Optional[float]
    gap_pct: Optional[float]
    real_return_pct: Optional[float]


def _safe_float(v: Any) -> Optional[float]:
    """輸入 → float 或 None(None / NaN / 非數值都回 None)。"""
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if f != f:  # NaN guard
        return None
    return f


def classify_eating_principal(
    total_return_pct: Any,
    dividend_yield_pct: Any,
) -> EatingPrincipalCore:
    """Canonical 吃本金核心判定 — 純數學,**無分類門檻**。

    Args
    ----
    total_return_pct : 含息報酬率 %(可為 None / NaN / 非數值)
    dividend_yield_pct : 年化配息率 %(可為 None / NaN / 非數值)

    Returns
    -------
    EatingPrincipalCore: 核心判定 + 派生指標。Caller 自行用
    `coverage_ratio` / `gap_pct` / `real_return_pct` 配合自己的 UI 門檻
    做 3/4/5 級分類。

    判定邏輯
    --------
    1. 任一 input 不合法 → is_data_missing=True,其餘欄位全 None / False
    2. dividend_yield ≤ 0(無配息基金)→ is_no_dividend=True, is_eating=False
       (邏輯上「沒配息 → 不存在吃本金」)
    3. 正常 case → is_eating = (total_return < dividend_yield)
       + coverage_ratio / gap_pct / real_return_pct 全部算好供 caller 用
    """
    r = _safe_float(total_return_pct)
    d = _safe_float(dividend_yield_pct)

    # Case 1:資料缺失(§1 fail loud:不偽造數值)
    if r is None or d is None:
        return EatingPrincipalCore(
            is_data_missing=True,
            is_no_dividend=False,
            is_eating=False,
            total_return_pct=r,
            dividend_yield_pct=d,
            coverage_ratio=None,
            gap_pct=None,
            real_return_pct=None,
        )

    # Case 2:無配息基金(div ≤ 0 → 不適用吃本金概念)
    if d <= 0:
        return EatingPrincipalCore(
            is_data_missing=False,
            is_no_dividend=True,
            is_eating=False,
            total_return_pct=r,
            dividend_yield_pct=d,
            coverage_ratio=None,  # 除以 0 / 負數無意義
            gap_pct=d - r,        # gap 仍可算(雖然 caller 多半不用)
            real_return_pct=r - d,
        )

    # Case 3:正常 — 核心判定 + 全派生指標
    is_eating = r < d
    return EatingPrincipalCore(
        is_data_missing=False,
        is_no_dividend=False,
        is_eating=is_eating,
        total_return_pct=r,
        dividend_yield_pct=d,
        coverage_ratio=r / d,
        gap_pct=d - r,
        real_return_pct=r - d,
    )
