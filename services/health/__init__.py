"""services/health — Fund Health subpackage(v19.231 完整 subpackage 化)。

User 重申「#7-#9」+「檔案太大則分階段」→ 從最小可行 facade 升級為真正搬檔
的 subpackage(5 子模組 + facade re-export)。

子模組對應(原 services/fund_*.py → services/health/*.py)
========================================================
- fund_health.py             → grade.py(4D 健診評分)
- fund_dividend_calculator.py → dividend_calc.py(配息計算純機械邏輯)
- fund_dividend_health.py    → dividend.py(配息健診業務:EatingPrincipal / 333 / MK 規則)
- fund_replacement_verdict.py → replacement.py(替換建議 MK 4 規則)
- fund_health_report.py      → report.py(健診表 row builder)

caller 變更
===========
~25 處 caller(production / test)從 `from services.fund_X import Y` 改成
`from services.health.X import Y` 或 `from services.health import Y`。

Backward compatibility
======================
原 services/fund_*.py 5 檔已 git mv 至 services/health/,**不留 shim**
(P2-7 shim 不穿透 sub-module 風險,且全 caller 已同步更新,
shim 純多餘負擔)。

未來重啟觸發
============
新增 fund health 相關模組時:
1. 加在 services/health/ 內(不要回到 services/ root)
2. 在本 __init__.py 加 re-export
"""
from __future__ import annotations

# ── grade(總體健診評分) ──────────────────────────────────────
from services.health.grade import (
    compute_4d_health,
)

# ── dividend_calc(配息計算純機械) ───────────────────────────
from services.health.dividend_calc import (
    compute_dividend_twd_series,
    div_health_light_for_pair,
)

# ── dividend(配息健診業務) ──────────────────────────────────
from services.health.dividend import (
    EatingPrincipalCore,
    check_333_principle,
    check_eating_principal_1y_mk,
    classify_eating_principal,
    compute_1y_total_return_mk_simple,
)

# ── replacement(替換建議) ──────────────────────────────────
from services.health.replacement import (
    check_replacement_recommendation,
)

# ── report(健診表 row builder) ──────────────────────────────
from services.health.report import (
    build_dividend_summary_row,
    build_health_analysis_row,
)

__all__ = [
    # grade
    "compute_4d_health",
    # dividend_calc
    "compute_dividend_twd_series",
    "div_health_light_for_pair",
    # dividend
    "EatingPrincipalCore",
    "check_333_principle",
    "check_eating_principal_1y_mk",
    "classify_eating_principal",
    "compute_1y_total_return_mk_simple",
    # replacement
    "check_replacement_recommendation",
    # report
    "build_dividend_summary_row",
    "build_health_analysis_row",
]
