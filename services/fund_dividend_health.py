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


# ════════════════════════════════════════════════════════════════
# v19.148 — MK 老師 1Y 吃本金檢查 SSOT 入口
#   方法論:近一年含息報酬率 vs 年化配息率(郭俊宏 MK 老師體檢邏輯)
#   - 跨 tab SSOT:單一基金 / 組合基金健診 / 組合配置 共用此入口
#   - 同步呼叫 dividend_safety canonical wrapper(5-level)
#   - 同基金不論在哪個 tab 看,verdict 必須一致
# ════════════════════════════════════════════════════════════════
def check_eating_principal_1y_mk(fund: dict) -> Optional[dict]:
    """MK 老師 1Y 吃本金檢查 SSOT 入口。

    依郭俊宏(MK)老師體檢邏輯:
        近一年含息總報酬率 < 年化配息率 → 🔴 吃本金

    支援兩種 fund dict shape:
    - **Nested**(tab3_portfolio / fund_checkup):`{moneydj_raw: {...}, metrics: {...}}`
    - **Flat**(`_auto_fetch_moneydj` 直回):`{moneydj_div_yield: ..., metrics: {...}}`

    年化配息率(adr)precedence:
        moneydj_div_yield(MoneyDJ wb05 官方,優先)→ metrics.annual_div_rate(fallback)

    含息報酬(tr1y):metrics.ret_1y

    Args
    ----
    fund: 基金 dict(任一支援 shape)

    Returns
    -------
    dividend_safety 5-level 結果 dict(含 status / alert_level / coverage / message)
    或 None(資料不足:adr 缺/ret_1y 缺/adr ≤ 0)

    SSOT 守則(v19.148 audit):
    - 與 ui.helpers.fund_checkup._compute_fund_health_kpis 同源(同 adr + tr1y 出口)
    - 與 ui.tab_fund_grp_health 新「吃本金燈號 (1Y · MK)」column 同源
    - tests/test_mk_ssot_unification.py 守同 fund dict input → 同 verdict
    """
    # 解析兩種 shape
    if "moneydj_raw" in fund:
        _mj = fund.get("moneydj_raw") or {}
        _mj_dy = _safe_float(_mj.get("moneydj_div_yield"))
    else:
        _mj_dy = _safe_float(fund.get("moneydj_div_yield"))

    _metrics = fund.get("metrics") or {}

    # adr:MoneyDJ wb05 優先,fallback metrics.annual_div_rate
    adr = _mj_dy if (_mj_dy and _mj_dy > 0) else _safe_float(_metrics.get("annual_div_rate"))
    if adr is None or adr <= 0:
        return None

    # tr1y:metrics.ret_1y
    tr1y = _safe_float(_metrics.get("ret_1y"))
    if tr1y is None:
        return None

    from services.portfolio_service import dividend_safety
    return dividend_safety(total_return=tr1y, dividend_yield=adr, nav_change=tr1y)


# v19.148 — 3-3-3 原則(MK 老師長線核心資產挑選輔助,非吃本金主判定)
#   成立滿 3 年 + 過去 3 年平均年化報酬 > 7% → 通過長線核心資產篩
THREE_THREE_THREE_MIN_YEARS = 3
THREE_THREE_THREE_MIN_ANN_RETURN_PCT = 7.0


def check_333_principle(years_since_inception: Optional[float],
                        ann_return_3y_pct: Optional[float]) -> dict:
    """MK 老師 3-3-3 原則 — 長線核心資產挑選輔助判定(輔助,非主吃本金).

    通過條件:
    - 成立 ≥ 3 年
    - 近 3 年平均年化報酬 > 7%

    Returns
    -------
    {
      "passed": bool | None(None = 資料不足),
      "years_ok": bool | None,
      "return_ok": bool | None,
      "message": str,
    }

    這是**長線核心資產篩選**輔助,不是吃本金判定。
    短線吃本金以 check_eating_principal_1y_mk 為準。
    """
    _yrs = _safe_float(years_since_inception)
    _ret = _safe_float(ann_return_3y_pct)
    if _yrs is None and _ret is None:
        return {"passed": None, "years_ok": None, "return_ok": None,
                "message": "資料不足(缺成立年數 + 3 年平均年化)"}
    _y_ok = (_yrs is not None and _yrs >= THREE_THREE_THREE_MIN_YEARS)
    _r_ok = (_ret is not None and _ret > THREE_THREE_THREE_MIN_ANN_RETURN_PCT)
    _passed = _y_ok and _r_ok
    if _passed:
        _msg = f"通過 3-3-3 ✅({_yrs:.1f} 年成立、3 年平均年化 {_ret:.1f}%)"
    elif not _y_ok and _yrs is not None:
        _msg = f"成立 {_yrs:.1f} 年 < 3 年(MK 3-3-3 要求 ≥ 3 年)"
    elif not _r_ok and _ret is not None:
        _msg = f"3 年平均年化 {_ret:.1f}% ≤ 7%(MK 3-3-3 要求 > 7%)"
    else:
        _msg = "資料不足(部分缺)"
    return {"passed": _passed, "years_ok": _y_ok, "return_ok": _r_ok, "message": _msg}
