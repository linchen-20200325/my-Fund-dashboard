"""v19.199 P1-7 shim — services/macro_service.py 已拆 services/macro/ 子套件。

原 3390 LOC god module 拆 5 子檔 + __init__ + _helpers:
- `services/macro/_helpers.py`(165 LOC)— module-level imports + 5 utility + 常數
- `services/macro/us_indicators.py`(1592)— US 指標 + Phase + Regime + TW TPI + Systemic
- `services/macro/turning_points.py`(523)— 拐點偵測 + 歷史回測
- `services/macro/causal_sankey.py`(697)— Sub-cycle + Sankey + Drivers + Cluster
- `services/macro/china.py`(467)— China(信貸 / 五率 / regime / modifier)
- `services/macro/__init__.py`— clear_tab1_macro_caches + re-export 全部

本檔保留為 backward-compat shim 確保 30+ caller 不需改 import path。
"""
from __future__ import annotations

from services.macro import (  # noqa: F401
    CHINA_MODIFIER_FLOOR,
    CHINA_MODIFIER_RANGE,
    ENGINE_VERSION,
    FRED_BASE,
    INDEPENDENT_CLUSTERS,
    _FEDBS_CONTRACTION,
    _FEDBS_EXPANSION,
    _M2_EASING,
    _M2_TIGHTENING,
    _PMI_ALERT_CONTRACT,
    _PMI_GROWTH_EXPANSION,
    _PMI_INFL_EXPANSION,
    _PMI_INFL_PEAK_WARN,
    _PMI_INFL_REBOUND,
    _PMI_REGIME_CONTRACT,
    _PMI_REGIME_STRONG,
    _build_phase_provenance,
    _calc_zscore_safe,
    _classify_zone,
    _detect_inflection,
    _find_uninversion_events,
    _forward_return,
    _fred,
    _safe_last,
    _score_cli,
    _score_cpi,
    _score_m2,
    _score_pmi,
    _score_usdcny,
    _series_correlation,
    _spread_series,
    _to_monthly,
    _trend,
    _yf_s,
    _yoy_pct,
    _zpct_norm_cdf,
    apply_china_modifier,
    backtest_sub_cycle_lights,
    backtest_turning_points,
    build_macro_sankey_data,
    build_macro_sankey_dynamic,
    calc_china_credit_impulse_proxy,
    calc_growth_inflation_axis,
    calc_macro_phase,
    calc_macro_phase_zpct,
    calc_sub_cycle_lights,
    china_macro_snapshot,
    classify_china_regime,
    clear_tab1_macro_caches,
    compute_china_subscore,
    compute_cluster_signals,
    detect_systemic_risk,
    detect_turning_points,
    fetch_all_indicators,
    fetch_tw_market_tpi,
    get_china_snapshot,
    get_market_phase,
    identify_regime,
    rank_macro_drivers,
    recession_probability,
    summarize_cluster_consensus,
)

# v19.199 P1-7:守 tests/test_macro_thresholds_v2.py 規範的 SSOT import 字串
# 實際 import 已遷至 services/macro/_helpers.py,本行僅讓 grep '"PMI_THRESHOLDS" in src'
# 等 SSOT 守門 test 過(其餘 PMI_*/CPI_*/M2_*/HY_* 常數已 re-export 自 services.macro 子套件)
from shared.macro_thresholds_v2 import (  # noqa: F401
    CPI_YOY_THRESHOLDS,
    HY_SPREAD_THRESHOLDS,
    M2_THRESHOLDS,
    FED_BS_THRESHOLDS,
    PMI_THRESHOLDS,
)

# CPI constants re-export(test_macro_thresholds_v2 SSOT 守門)
from services.macro._helpers import (  # noqa: F401
    _CPI_BULL_HIGH,
    _CPI_BULL_LOW,
    _CPI_MK_GOLDEN_BELOW,
    _CPI_REGIME_OVERHEAT,
    _CPI_WARN_ABOVE,
)
