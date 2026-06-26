"""F-GRAY-4 v19.169 守護 — shared/macro_thresholds_v2.py SSOT 完整性。

驗證:
1. SSOT schema 完整(stoplight / score_function / portfolio_advisor / beginner_panic)
2. 數值與原 inline 完全等價(行為 0 改保證)
3. 各 site 確實 import SSOT 而非 inline magic

對應 SPEC §16.2 multi-purpose threshold dict architecture。
"""
from __future__ import annotations

import importlib

import pytest


# ════════════════════════════════════════════════════════════════
# 1. SSOT schema 完整性
# ════════════════════════════════════════════════════════════════

def test_hy_spread_schema_complete():
    from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as HT

    assert set(HT.keys()) == {
        "stoplight", "score_function", "portfolio_advisor", "beginner_panic"
    }


def test_hy_spread_stoplight_values():
    """stoplight 與原 macro_repository.MACRO_THRESHOLDS 字面值等價."""
    from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as HT
    s = HT["stoplight"]
    assert s["green_below"] == 4.0
    assert s["yellow_below"] == 6.0
    assert s["red_above"] == 6.0


def test_hy_spread_score_function_values():
    from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as HT
    sf = HT["score_function"]
    assert sf["tight_below"] == 4.0
    assert sf["wide_above"] == 6.0


def test_hy_spread_portfolio_advisor_values():
    """portfolio_advisor 與原 portfolio_service.py:342,345 等價."""
    from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as HT
    pa = HT["portfolio_advisor"]
    assert pa["warn_above"] == 4.5
    assert pa["risk_above"] == 6.0


def test_hy_spread_beginner_panic_values():
    """beginner_panic 與原 macro_beginner_view.py:52-53 等價."""
    from shared.macro_thresholds_v2 import HY_SPREAD_THRESHOLDS as HT
    bp = HT["beginner_panic"]
    assert bp["warn_above"] == 5.0
    assert bp["panic_above"] == 8.0


# ════════════════════════════════════════════════════════════════
# 2. 行為等價 — score function lambda
# ════════════════════════════════════════════════════════════════

def test_score_function_behavior_equivalence():
    """v19.169 後 SCORE_RULES["HY_SPREAD"] lambda 與原 inline (v<4 → 2.0, v>6 → -2.0) 等價."""
    from services.macro_validation import SCORE_RULES
    _, fn = SCORE_RULES["HY_SPREAD"]
    assert fn(3.5) == 2.0           # tight
    assert fn(7.0) == -2.0          # wide
    assert fn(5.0) == 0.0           # neutral
    assert fn(4.0) == 0.0           # boundary tight (= 4, not < 4)
    assert fn(6.0) == 0.0           # boundary wide (= 6, not > 6)


def test_score_calibration_function_behavior_equivalence():
    """v19.169 後 _s_hy_spread 與原 inline 等價."""
    from services.macro_score_calibration import _s_hy_spread
    assert _s_hy_spread(3.5) == 2
    assert _s_hy_spread(7.0) == -2
    assert _s_hy_spread(5.0) == 0
    assert _s_hy_spread(4.0) == 0
    assert _s_hy_spread(6.0) == 0


# ════════════════════════════════════════════════════════════════
# 3. MACRO_THRESHOLDS dict 仍然提供 HY_SPREAD stoplight 三鍵
# ════════════════════════════════════════════════════════════════

def test_macro_repository_hy_spread_unchanged_shape():
    """v19.169 後 MACRO_THRESHOLDS["HY_SPREAD"] dict shape 與原版完全等價."""
    from repositories.macro_repository import MACRO_THRESHOLDS
    hy = MACRO_THRESHOLDS["HY_SPREAD"]
    assert hy["green_below"] == 4.0
    assert hy["yellow_below"] == 6.0
    assert hy["red_above"] == 6.0


# ════════════════════════════════════════════════════════════════
# 4. 反退化 — production 檔禁止 inline 字面值 4.0/6.0/4.5/5.0/8.0 用作 HY 閾值
#    (字面值出現在註解 / docstring / 測試 fixture 不算)
# ════════════════════════════════════════════════════════════════

def test_macro_beginner_view_uses_ssot():
    """macro_beginner_view 必須 import HY_SPREAD_THRESHOLDS."""
    import ui.helpers.macro_beginner_view as mbv
    src = open(mbv.__file__, encoding="utf-8").read()
    assert "from shared.macro_thresholds_v2 import" in src
    assert 'HY_SPREAD_THRESHOLDS' in src


def test_portfolio_service_uses_ssot():
    import services.portfolio_service as ps
    src = open(ps.__file__, encoding="utf-8").read()
    assert "from shared.macro_thresholds_v2 import" in src
    assert "_HY_PORTFOLIO_RISK" in src
    assert "_HY_PORTFOLIO_WARN" in src


def test_macro_validation_uses_ssot():
    import services.macro_validation as mv
    src = open(mv.__file__, encoding="utf-8").read()
    assert "from shared.macro_thresholds_v2 import" in src
    assert "_HY_TIGHT" in src
    assert "_HY_WIDE" in src


def test_macro_score_calibration_uses_ssot():
    import services.macro_score_calibration as msc
    src = open(msc.__file__, encoding="utf-8").read()
    assert "from shared.macro_thresholds_v2 import" in src


def test_tab1_macro_uses_ssot():
    import ui.tab1_macro as tm
    src = open(tm.__file__, encoding="utf-8").read()
    assert "from shared.macro_thresholds_v2 import" in src
