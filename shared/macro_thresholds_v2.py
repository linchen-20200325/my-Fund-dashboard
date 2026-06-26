"""v19.169 Multi-purpose macro threshold SSOT — F-GRAY-4 (SPEC §16.2).

問題:單一 stoplight dict (`MACRO_THRESHOLDS`) 無法表達同一指標在不同 site
的多種用途 (signal classification / score function / portfolio advisor /
beginner panic etc.) — 機械式 swap 會把 4 種語意不同的 path 強塞同一 schema。

設計:per-indicator multi sub-dict by use case，各 site 改 import 對應子
dict，**不**強制統一閾值,但所有閾值集中在本檔 SSOT。

優先順序 (per SPEC §16.2 ROI 表):HY_SPREAD (最少語意,最低風險) → CPI → PMI。

NOT meant to unify thresholds across sites — only to colocate them.
"""
from __future__ import annotations


# ── HY_SPREAD (BAMLH0A0HYM2) — High Yield OAS, % ─────────────────────────
HY_SPREAD_THRESHOLDS = {
    "stoplight": {
        # repositories/macro_repository.py:198 MACRO_THRESHOLDS
        # macro_service.py:1116 inline > 6 check
        # ui/tab1_macro.py:60 _HY_WARN_THRESHOLD
        # ui/tab6_manual.py:1246 教學表 (4, 6)
        "green_below": 4.0,
        "yellow_below": 6.0,
        "red_above": 6.0,
    },
    "score_function": {
        # services/macro_validation.py:78 SCORE_RULES lambda
        # services/macro_score_calibration.py:54 _s_hy_spread
        "tight_below": 4.0,    # v < 4 → +2 (信用利差收斂,利多)
        "wide_above": 6.0,     # v > 6 → -2 (信用利差走闊,利空)
    },
    "portfolio_advisor": {
        # services/portfolio_service.py:342,345 投組風險建議
        # 注意:warn 閾值與 stoplight (4.0) 不同 — 投組建議更寬容
        "warn_above": 4.5,     # > 4.5 → 🟡 信用風險升高
        "risk_above": 6.0,     # > 6.0 → 🔴 避險情緒高
    },
    "beginner_panic": {
        # ui/helpers/macro_beginner_view.py:52-53
        # 注意:閾值與 stoplight 不同 — 新手介面更保守 (避免過早警示)
        "warn_above": 5.0,
        "panic_above": 8.0,
    },
}
