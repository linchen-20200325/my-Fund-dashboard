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


# ════════════════════════════════════════════════════════════════
# 5. CPI_YOY_THRESHOLDS (F-GRAY-4 v19.178)
# ════════════════════════════════════════════════════════════════

def test_cpi_yoy_schema_complete():
    """CPI_YOY_THRESHOLDS 含 5 個 use-case sub-dict."""
    from shared.macro_thresholds_v2 import CPI_YOY_THRESHOLDS as CT
    assert set(CT.keys()) == {
        "stoplight",
        "score_function",
        "inflection_detection",
        "regime_classification",
        "beginner_panic",
    }


def test_cpi_yoy_stoplight_values():
    """stoplight 與原 macro_repository.MACRO_THRESHOLDS['CPI'] band 等價."""
    from shared.macro_thresholds_v2 import CPI_YOY_THRESHOLDS as CT
    s = CT["stoplight"]
    assert s["green_low"] == 1.5
    assert s["green_high"] == 2.5
    assert s["yellow_above"] == 3.5
    assert s["red_above"] == 4.0


def test_cpi_yoy_score_function_values():
    """score_function 與原 macro_validation.py:101 SCORE_RULES lambda 等價."""
    from shared.macro_thresholds_v2 import CPI_YOY_THRESHOLDS as CT
    sf = CT["score_function"]
    assert sf["ideal_low"] == 1.0
    assert sf["ideal_high"] == 2.5
    assert sf["elevated_above"] == 4.0


def test_cpi_yoy_inflection_detection_values():
    """inflection_detection 與原 macro_service.py:208-210,253 等價."""
    from shared.macro_thresholds_v2 import CPI_YOY_THRESHOLDS as CT
    inf = CT["inflection_detection"]
    assert inf["warn_above"] == 4.0
    assert inf["bull_low"] == 1.5
    assert inf["bull_high"] == 3.0
    assert inf["mk_golden_below"] == 3.5


def test_cpi_yoy_regime_classification_values():
    """regime_classification 與原 macro_service.py:1447-1449 等價."""
    from shared.macro_thresholds_v2 import CPI_YOY_THRESHOLDS as CT
    rc = CT["regime_classification"]
    assert rc["overheat_above"] == 3.5


def test_cpi_yoy_beginner_panic_values():
    """beginner_panic 與原 macro_beginner_view.py:315 等價."""
    from shared.macro_thresholds_v2 import CPI_YOY_THRESHOLDS as CT
    bp = CT["beginner_panic"]
    assert bp["overheat_above"] == 4.0


def test_cpi_score_function_behavior_equivalence():
    """v19.178 後 SCORE_RULES["CPI"] lambda 與原 inline (1<v<2.5 → 1.0, v>4 → -1.0) 等價."""
    from services.macro_validation import SCORE_RULES
    _, fn = SCORE_RULES["CPI"]
    assert fn(2.0) == 1.0           # ideal
    assert fn(5.0) == -1.0          # elevated
    assert fn(3.0) == 0.0           # neutral
    assert fn(1.0) == 0.0           # boundary low (= 1, not > 1)
    assert fn(2.5) == 0.0           # boundary high (= 2.5, not < 2.5)
    assert fn(4.0) == 0.0           # boundary elevated (= 4, not > 4)


def test_cpi_beginner_view_imports_ssot():
    """macro_beginner_view 必須 import CPI_YOY_THRESHOLDS."""
    import ui.helpers.macro_beginner_view as mbv
    src = open(mbv.__file__, encoding="utf-8").read()
    assert "CPI_YOY_THRESHOLDS" in src
    assert "_CPI_THR_V2" in src or 'CPI_YOY_THRESHOLDS as' in src


def test_cpi_macro_service_imports_ssot():
    """macro_service 必須 import CPI_YOY_THRESHOLDS."""
    import services.macro_service as ms
    src = open(ms.__file__, encoding="utf-8").read()
    assert "CPI_YOY_THRESHOLDS" in src
    assert "_CPI_WARN_ABOVE" in src
    assert "_CPI_REGIME_OVERHEAT" in src


def test_cpi_macro_validation_imports_ssot():
    """macro_validation 必須 import CPI_YOY_THRESHOLDS."""
    import services.macro_validation as mv
    src = open(mv.__file__, encoding="utf-8").read()
    assert "CPI_YOY_THRESHOLDS" in src
    assert "_CPI_IDEAL_LOW" in src
    assert "_CPI_ELEVATED" in src


# ════════════════════════════════════════════════════════════════
# 6. PMI_THRESHOLDS (F-GRAY-4 v19.179 PR-1 SSOT only)
# ════════════════════════════════════════════════════════════════

def test_pmi_schema_complete():
    """PMI_THRESHOLDS 含 8 個 use-case sub-dict."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    assert set(PT.keys()) == {
        "stoplight",
        "score_function",
        "regime_classification",
        "inflection_detection",
        "growth_signal",
        "alert_generation",
        "beginner_panic",
        "mk_tolerance",
    }


def test_pmi_stoplight_values():
    """stoplight 與原 macro_buckets.py:58-59 等價."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    s = PT["stoplight"]
    assert s["green_above"] == 50.0
    assert s["yellow_below"] == 50.0
    assert s["red_below"] == 46.0


def test_pmi_score_function_values():
    """score_function 與 macro_validation.py:102 / macro_score_calibration.py:58 等價."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    sf = PT["score_function"]
    assert sf["expansion_above"] == 50.0
    assert sf["recession_below"] == 45.0


def test_pmi_regime_classification_values():
    """regime_classification 與 macro_service.py:1457-1461 等價;52=新觀念真正枯榮線."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    rc = PT["regime_classification"]
    assert rc["strong_growth_above"] == 52.0
    assert rc["contraction_below"] == 50.0


def test_pmi_inflection_detection_values():
    """inflection_detection 與 macro_service.py:194-198 等價."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    inf = PT["inflection_detection"]
    assert inf["peak_warning_above"] == 55.0
    assert inf["expansion_above"] == 50.0
    assert inf["rebound_below"] == 50.0


def test_pmi_growth_signal_values():
    """growth_signal 與 macro_service.py:986 等價."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    assert PT["growth_signal"]["expansion_above"] == 50.0


def test_pmi_alert_generation_values():
    """alert_generation 與 macro_service.py:1145 等價."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    assert PT["alert_generation"]["contraction_below"] == 50.0


def test_pmi_beginner_panic_values():
    """beginner_panic 與 macro_beginner_view.py:314 等價."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    assert PT["beginner_panic"]["contraction_below"] == 50.0


def test_pmi_mk_tolerance_values():
    """mk_tolerance 與 mk_clock.py:76-81,106-107 等價."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS as PT
    mk = PT["mk_tolerance"]
    assert mk["expansion_above"] == 50.5
    assert mk["contraction_below"] == 49.5


def test_tw_pmi_schema_complete():
    """TW_PMI_THRESHOLDS 結構."""
    from shared.macro_thresholds_v2 import TW_PMI_THRESHOLDS as TPT
    assert set(TPT.keys()) == {"tw_pmi_score"}


def test_tw_pmi_score_values():
    """TW PMI 5 級評分閾值與 macro_tw_local.py:205-214 / 323-332 等價."""
    from shared.macro_thresholds_v2 import TW_PMI_THRESHOLDS as TPT
    s = TPT["tw_pmi_score"]
    assert s["strong_above"] == 55.0
    assert s["expansion_above"] == 52.0
    assert s["neutral_above"] == 50.0
    assert s["weak_above"] == 48.0


def test_pmi_thresholds_independent_from_tw():
    """US PMI 與 TW PMI 為兩個獨立 dict,不可合併."""
    from shared.macro_thresholds_v2 import PMI_THRESHOLDS, TW_PMI_THRESHOLDS
    assert PMI_THRESHOLDS is not TW_PMI_THRESHOLDS
    # 兩者 keys 無重疊(語意獨立)
    assert set(PMI_THRESHOLDS.keys()) & set(TW_PMI_THRESHOLDS.keys()) == set()


# ════════════════════════════════════════════════════════════════
# 7. PR-2 macro_service.py 行為等價 + import 守(v19.179 PR-2)
# ════════════════════════════════════════════════════════════════

def test_pmi_macro_service_imports_ssot():
    """macro_service 必須 import PMI_THRESHOLDS + 6 個 module-level 常數."""
    import services.macro_service as ms
    src = open(ms.__file__, encoding="utf-8").read()
    assert "PMI_THRESHOLDS" in src
    assert "_PMI_INFL_REBOUND" in src
    assert "_PMI_INFL_PEAK_WARN" in src
    assert "_PMI_GROWTH_EXPANSION" in src
    assert "_PMI_ALERT_CONTRACT" in src
    assert "_PMI_REGIME_STRONG" in src
    assert "_PMI_REGIME_CONTRACT" in src


def test_pmi_macro_service_constants_values():
    """6 個 PMI module-level 常數值對齊 SSOT."""
    from services.macro_service import (
        _PMI_INFL_REBOUND, _PMI_INFL_EXPANSION, _PMI_INFL_PEAK_WARN,
        _PMI_GROWTH_EXPANSION, _PMI_ALERT_CONTRACT,
        _PMI_REGIME_STRONG, _PMI_REGIME_CONTRACT,
    )
    assert _PMI_INFL_REBOUND == 50.0
    assert _PMI_INFL_EXPANSION == 50.0
    assert _PMI_INFL_PEAK_WARN == 55.0
    assert _PMI_GROWTH_EXPANSION == 50.0
    assert _PMI_ALERT_CONTRACT == 50.0
    assert _PMI_REGIME_STRONG == 52.0    # 新觀念真正枯榮線
    assert _PMI_REGIME_CONTRACT == 50.0


def test_pmi_macro_service_no_inline_pmi_literals():
    """macro_service.py 不應再有 inline `>= 50` / `>= 52` / `>= 55` / `< 50` 圍繞 PMI 變數的字面值.

    用 regex 抓「pmi_v >= 50」 / 「pmi_v < 50」等 pattern,確保已 SSOT 化.
    """
    import re
    import services.macro_service as ms
    src = open(ms.__file__, encoding="utf-8").read()
    # PMI inline patterns(if any survived migration)
    inline_patterns = [
        r"pmi_v\s*<\s*50\b",           # < 50 literal
        r"pmi_v\s*>=\s*5[0-9]\b",      # >= 50/52/55 literal
        r"pmi_v\s*<\s*5[0-9]\b",       # < 50/52/55 literal
        r"PMI\b[^=]*\)\s*<\s*50\b",    # indicators.get('PMI'...) < 50
    ]
    for pat in inline_patterns:
        matches = re.findall(pat, src)
        assert not matches, f"macro_service.py 仍有 inline PMI literal: pattern={pat} matches={matches}"
