"""services/macro 子套件 — v19.199 P1-7 從 macro_service.py 3390 LOC god module 拆出。

結構:
- `_helpers`:module-level imports/constants + 5 utility(_fred / _yf_s / _trend /
  _safe_last / _spread_series / recession_probability)
- `us_indicators`:美國指標 + Phase + Regime + TW TPI + Systemic Risk(主檔大宗)
- `turning_points`:景氣拐點偵測 + 歷史回測
- `causal_sankey`:Sub-cycle + Sankey + Drivers + Cluster signals
- `china`:中國 macro(信貸脈衝 / 五率 / regime / modifier)
- 本 __init__:clear_tab1_macro_caches + re-export 全部公開 fn

30+ caller 透過 services/macro_service.py shim re-export 取得 fn,patch path 不需改。
"""
from __future__ import annotations

# Re-export 全部公開 fn + clear_tab1_macro_caches body 需要的常數
from services.macro._helpers import (  # noqa: F401
    ENGINE_VERSION,
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
    _TAB1_SESSION_KEYS,
    _TAB1_TTL_CACHE_NAMES,
    _fred,
    _spread_series,
    _safe_last,
    _trend,
    _yf_s,
    recession_probability,
)
from services.macro.action_light import macro_action_light  # noqa: F401
from services.macro.us_indicators import (  # noqa: F401
    _build_phase_provenance,
    _detect_inflection,
    _zpct_norm_cdf,
    calc_growth_inflation_axis,
    calc_macro_phase,
    calc_macro_phase_zpct,
    detect_systemic_risk,
    fetch_all_indicators,
    fetch_tw_market_tpi,
    get_market_phase,
    identify_regime,
)
from services.macro.turning_points import (  # noqa: F401
    _find_uninversion_events,
    _forward_return,
    _yoy_pct,
    backtest_turning_points,
    detect_turning_points,
)
from services.macro.causal_sankey import (  # noqa: F401
    INDEPENDENT_CLUSTERS,
    _calc_zscore_safe,
    _series_correlation,
    _to_monthly,
    backtest_sub_cycle_lights,
    build_macro_sankey_data,
    build_macro_sankey_dynamic,
    calc_sub_cycle_lights,
    compute_cluster_signals,
    rank_macro_drivers,
    summarize_cluster_consensus,
)
from services.macro.china import (  # noqa: F401
    CHINA_MODIFIER_FLOOR,
    CHINA_MODIFIER_RANGE,
    _classify_zone,
    _score_cli,
    _score_cpi,
    _score_m2,
    _score_pmi,
    _score_usdcny,
    apply_china_modifier,
    calc_china_credit_impulse_proxy,
    china_macro_snapshot,
    classify_china_regime,
    compute_china_subscore,
    get_china_snapshot,
)



def clear_tab1_macro_caches(session_state=None) -> dict:
    """v19.57 C1：Tab1（總經）強制重抓專用 — 只清 Tab1 owned 快取，不誤殺 Tab2~Tab5。

    清理範圍：
      (1) infra/cache.py `_CACHE_REGISTRY` 中名稱屬於 `_TAB1_TTL_CACHE_NAMES` 的 TTL cache
      (2) hot_money.py 兩個 `@st.cache_data` 函式 (fetch_foreign_flow_series / fetch_usdtwd_series)
      (3) Tab1 session_state 殘留（_radar / _tp / indicators / phase_info ...）

    參數 session_state: 通常傳 `st.session_state`；不傳則跳過 (3)。
    回傳 dict {ttl_cleared, st_cache_cleared, session_keys_popped}。
    """
    _stat = {"ttl_cleared": 0, "st_cache_cleared": 0, "session_keys_popped": 0}
    try:
        from infra.cache import clear_caches_by_names
        _stat["ttl_cleared"] = clear_caches_by_names(_TAB1_TTL_CACHE_NAMES)
    except Exception:
        pass
    try:
        # v19.196 P0-4-A:fetcher 已下沉 repositories.hot_money_repository
        from repositories.hot_money_repository import (
            fetch_foreign_flow_series, fetch_usdtwd_series,
        )
        for _fn in (fetch_foreign_flow_series, fetch_usdtwd_series):
            try:
                _fn.clear()
                _stat["st_cache_cleared"] += 1
            except Exception:
                pass
    except Exception:
        pass
    if session_state is not None:
        for _k in _TAB1_SESSION_KEYS:
            try:
                if _k in session_state:
                    session_state.pop(_k, None)
                    _stat["session_keys_popped"] += 1
            except Exception:
                pass
    return _stat
