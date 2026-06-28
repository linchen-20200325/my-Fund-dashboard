"""services/health — Fund Health 模組 discoverability facade(v19.231)。

**最小可行 facade 模式**:本檔僅 re-export 既有 4 個 services/fund_*.py 模組
的公開 fn,**不搬移源檔**(留 services/ root 作 source-local SSOT)。

設計理由
========
- 5 個 fund health 模組(`fund_dividend_calculator` / `fund_dividend_health` /
  `fund_health` / `fund_health_report` / `fund_replacement_verdict`)散落
  services/ root,16 個 caller 各自 import 細模組路徑,新 caller 難發現
  「fund health 相關 API 集合在哪」
- 16 caller 大改造為純 cosmetic 移檔(對齊 F-GRAY-1 v19.81 fund_fetcher.py
  459 LOC + 57 caller 決策:保根目錄,不為 cosmetic 動),違反 §8.1 step 6
  「用不到的抽象先不做」
- **折衷**:0 caller 變更 + 新 facade 入口,新 code 可選用
  `from services.health import compute_4d_health, check_replacement_recommendation`
  vs 既有 `from services.fund_health import compute_4d_health` 都可用

未來升級觸發
============
若以下任一觸發,則升級為真正搬檔的 subpackage:
1. services/ root 因新增 fund_* 而爆滿到難 scan
2. 4 個模組演化出共用 helper 需要 _helpers.py(私有 module)
3. user 主動指派全面搬檔

對應 EX-* 例外:本模式對齊 EX-CRUD-1 / EX-PASSTHRU-1「shim 無維護負擔」
思路(本 facade 為純 re-export,無業務邏輯),不需新增 EX-* 編號。
"""
from __future__ import annotations

# ── grade(總體健診評分) ──────────────────────────────────────
from services.fund_health import (
    compute_4d_health,
)

# ── dividend(配息計算 + 健診) ───────────────────────────────
from services.fund_dividend_calculator import (
    compute_dividend_twd_series,
    div_health_light_for_pair,
)
from services.fund_dividend_health import (
    EatingPrincipalCore,
    check_333_principle,
    check_eating_principal_1y_mk,
    classify_eating_principal,
    compute_1y_total_return_mk_simple,
)

# ── replacement(替換建議) ──────────────────────────────────
from services.fund_replacement_verdict import (
    check_replacement_recommendation,
)

# ── report(健診表 row builder) ──────────────────────────────
from services.fund_health_report import (
    build_dividend_summary_row,
    build_health_analysis_row,
)

__all__ = [
    # grade
    "compute_4d_health",
    # dividend
    "EatingPrincipalCore",
    "check_333_principle",
    "check_eating_principal_1y_mk",
    "classify_eating_principal",
    "compute_1y_total_return_mk_simple",
    "compute_dividend_twd_series",
    "div_health_light_for_pair",
    # replacement
    "check_replacement_recommendation",
    # report
    "build_dividend_summary_row",
    "build_health_analysis_row",
]
