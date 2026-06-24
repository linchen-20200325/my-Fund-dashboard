"""services/reconcile.py — 雙演算法對帳工具(F-RECON-1 v19.87)

§4.3 重算對帳:關鍵指標應有第二種演算法/源頭做交叉驗證,降低單源偏差風險。

範疇(per CLAUDE.md §4.3):
- 殖利率:FRED DGS10 vs Yahoo ^TNX(TNX = 10Y treasury × 10)
- 基金 1Y 報酬:`(nav[-1]/nav[-252])-1` 自算 vs MoneyDJ wb01 顯示值
- Sharpe:`mean/std * sqrt(252)` 自算 vs MoneyDJ wb07 顯示值
- 配息殖利率:`sum(12M div)/current_nav` 自算 vs MoneyDJ 顯示值
- macro health score:單一 path,缺對照演算法(待 audit)

本模組為 L2 Service 純函式,無 I/O。caller 傳入兩個源頭的數據,本模組做比對 +
回 reconcile 結果 dict。

對外 API:
- reconcile_pair(name, value_a, value_b, *, source_a, source_b, abs_tol, rel_tol) -> dict
- reconcile_us10y_yield(fred_value, yahoo_tnx_value) -> dict
- reconcile_fund_annual_return(self_calc_ret, moneydj_ret) -> dict
- reconcile_sharpe(self_calc_sharpe, moneydj_sharpe) -> dict
- reconcile_dividend_yield(self_calc_yield, moneydj_yield) -> dict

對照 Stock 端 `reconcile.py`(S-RECON-1 v18.252),容差為 fund 場景特化。
"""
from __future__ import annotations

import math
from typing import Optional


def reconcile_pair(
    name: str,
    value_a: Optional[float],
    value_b: Optional[float],
    *,
    source_a: str,
    source_b: str,
    abs_tol: float = 1e-4,
    rel_tol: float = 1e-3,
) -> dict:
    """通用雙源對帳工具。

    Returns
    -------
    dict
        {
            'name': str,
            'value_a': float | None,
            'value_b': float | None,
            'source_a': str,
            'source_b': str,
            'delta_abs': float | None,
            'delta_rel': float | None,
            'agree':     bool,
            'status':    'agree' | 'disagree' | 'a_missing' | 'b_missing' | 'both_missing',
        }
    """
    if value_a is None and value_b is None:
        return {
            'name': name, 'value_a': None, 'value_b': None,
            'source_a': source_a, 'source_b': source_b,
            'delta_abs': None, 'delta_rel': None,
            'agree': False, 'status': 'both_missing',
        }
    if value_a is None:
        return {
            'name': name, 'value_a': None, 'value_b': value_b,
            'source_a': source_a, 'source_b': source_b,
            'delta_abs': None, 'delta_rel': None,
            'agree': False, 'status': 'a_missing',
        }
    if value_b is None:
        return {
            'name': name, 'value_a': value_a, 'value_b': None,
            'source_a': source_a, 'source_b': source_b,
            'delta_abs': None, 'delta_rel': None,
            'agree': False, 'status': 'b_missing',
        }
    delta_abs = abs(value_a - value_b)
    _denom = max(abs(value_a), abs(value_b))
    delta_rel = delta_abs / _denom if _denom > 0 else 0.0
    agree = math.isclose(value_a, value_b, abs_tol=abs_tol, rel_tol=rel_tol)
    return {
        'name': name, 'value_a': value_a, 'value_b': value_b,
        'source_a': source_a, 'source_b': source_b,
        'delta_abs': delta_abs, 'delta_rel': delta_rel,
        'agree': agree, 'status': 'agree' if agree else 'disagree',
    }


def reconcile_us10y_yield(
    fred_dgs10: Optional[float],
    yahoo_tnx: Optional[float],
) -> dict:
    """美 10 年期殖利率雙源對帳。

    Parameters
    ----------
    fred_dgs10 : float | None  FRED DGS10 直接報率(% 單位,例如 4.25)。
    yahoo_tnx : float | None   Yahoo ^TNX 報價(=殖利率 × 10,需除 10 才是 %)。

    容差:5bp(0.05 個百分點)內視為一致。
    """
    converted_yahoo = (yahoo_tnx / 10.0) if yahoo_tnx is not None else None
    return reconcile_pair(
        name="US10Y_YIELD",
        value_a=fred_dgs10,
        value_b=converted_yahoo,
        source_a="FRED:DGS10",
        source_b="Yahoo:^TNX/10",
        abs_tol=0.05,
        rel_tol=0.02,
    )


def reconcile_fund_annual_return(
    self_calc_ret: Optional[float],
    moneydj_ret: Optional[float],
) -> dict:
    """基金 1Y 報酬率雙演算法對帳。

    對照:`(nav[-1]/nav[-252])-1` 自算 vs MoneyDJ wb01 顯示值。
    容差:絕對 0.5 個百分點(NAV 截斷小數 / 交易日定義差異容許)。

    Parameters
    ----------
    self_calc_ret : float | None  自算 1Y 報酬率(小數,0.15 = 15%)。
    moneydj_ret : float | None    MoneyDJ wb01 顯示 1Y 報酬率(小數)。
    """
    return reconcile_pair(
        name="FUND_1Y_RETURN",
        value_a=self_calc_ret,
        value_b=moneydj_ret,
        source_a="self_calc:nav[-1]/nav[-252]-1",
        source_b="MoneyDJ:wb01:1Y",
        abs_tol=0.005,
        rel_tol=0.05,
    )


def reconcile_sharpe(
    self_calc_sharpe: Optional[float],
    moneydj_sharpe: Optional[float],
) -> dict:
    """Sharpe 比率雙演算法對帳。

    對照:`mean/std * sqrt(252)` 自算 vs MoneyDJ wb07 顯示值。
    容差:絕對 0.1(Sharpe 為小數值,常落 0.3~2.5 區間)。
    """
    return reconcile_pair(
        name="FUND_SHARPE",
        value_a=self_calc_sharpe,
        value_b=moneydj_sharpe,
        source_a="self_calc:mean/std*sqrt(252)",
        source_b="MoneyDJ:wb07:Sharpe",
        abs_tol=0.1,
        rel_tol=0.1,
    )


def reconcile_dividend_yield(
    self_calc_yield: Optional[float],
    moneydj_yield: Optional[float],
) -> dict:
    """配息殖利率雙演算法對帳。

    對照:`sum(12M div)/current_nav` 自算 vs MoneyDJ 顯示值。
    容差:絕對 0.1 個百分點(配息計算定義差容許)。
    """
    return reconcile_pair(
        name="DIVIDEND_YIELD",
        value_a=self_calc_yield,
        value_b=moneydj_yield,
        source_a="self_calc:sum(12M_div)/current_nav",
        source_b="MoneyDJ:dividend_yield",
        abs_tol=0.001,
        rel_tol=0.05,
    )


def reconcile_macro_health(
    main_score: Optional[float],
    zpct_score: Optional[float],
    *,
    main_phase: Optional[str] = None,
    zpct_phase: Optional[str] = None,
) -> dict:
    """F-RECON-1 v19.108 — macro health composite score 雙演算法對帳。

    對照:
    - 主路徑:`calc_macro_phase`(weighted_sum/total/2*10,0..10 + phase 4 級分類)
    - 對照演算法:`calc_macro_phase_zpct`(Z-score 百分位平均 × 10,0..10 + 同門檻分類)

    容差設計:
    - score 絕對差 ≤ 1.5(0..10 量尺;兩種完全不同算法 ±1.5 內視為一致)
    - 若 phase 一致(衰退/復甦/擴張/高峰),即便 score 差 > 1.5 仍視為「phase_agree」
    - 兩個都缺資料 → both_missing

    額外欄位:
    - phase_agree:bool,兩個 phase 字串是否完全相同
    - main_phase / zpct_phase:caller 渲染用

    Parameters
    ----------
    main_score : float | None
        主路徑 calc_macro_phase 回傳的 `score`(0..10)
    zpct_score : float | None
        對照 calc_macro_phase_zpct 回傳的 `score`(0..10)
    main_phase : str | None
        主路徑 `phase`(衰退/復甦/擴張/高峰)
    zpct_phase : str | None
        對照 `phase`
    """
    base = reconcile_pair(
        name="MACRO_HEALTH",
        value_a=main_score,
        value_b=zpct_score,
        source_a="self_calc:weighted_sum/calc_macro_phase",
        source_b="self_calc:zpct_mean/calc_macro_phase_zpct",
        abs_tol=1.5,
        rel_tol=0.3,
    )
    # phase-level 對帳:即便 score 差較大,phase 一致仍視為通過(粒度更穩)
    phase_agree = bool(
        main_phase is not None
        and zpct_phase is not None
        and str(main_phase) == str(zpct_phase)
    )
    base["phase_agree"] = phase_agree
    base["main_phase"] = main_phase
    base["zpct_phase"] = zpct_phase
    # 若 score-level disagree 但 phase 一致,降級為 phase_agree(語意更準確)
    if base["status"] == "disagree" and phase_agree:
        base["status"] = "phase_agree"
        base["agree"] = True
    return base
