"""services/macro 子套件 — v19.199 P1-7 從 macro_service.py 3390 LOC god module 拆出。

結構:
- `_helpers`:module-level imports/constants + 5 utility(_fred / _yf_s / _trend /
  _safe_last / _spread_series / recession_probability)
- `us_indicators`:美國指標 + Phase + Regime + Systemic Risk(主檔大宗)
- `turning_points`:景氣拐點偵測 + 歷史回測
- `causal_sankey`:Sub-cycle + Sankey + Drivers + Cluster signals
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


def clear_tab1_macro_caches(session_state=None) -> dict:
    """v19.57 C1：Tab1（總經）強制重抓專用 — 只清 Tab1 owned 快取，不誤殺 Tab2~Tab5。

    清理範圍：
      (1) infra/cache.py `_CACHE_REGISTRY` 中名稱屬於 `_TAB1_TTL_CACHE_NAMES` 的 TTL cache
      (2) `repositories/hot_money_repository.py` 兩支公開 fetcher 背後的 `@st.cache_data`
          （`fetch_foreign_flow_series` / `fetch_usdtwd_series` —— 2026-09-01 拆成
          `_cached_*` 之後，公開名字上的 `.clear` 由該檔的 `_bind_clear` 綁回去，
          故這裡的呼叫方式一字未改；⚠️ 舊表述寫「hot_money.py」，該 fetcher 早已
          於 v19.196 P0-4-A 下沉 repositories，**只更正檔名，語意未改**）
      (3) Tab1 session_state 殘留（_radar / _tp / indicators / phase_info ...）
      (4) **本檔登記的來源退避冷卻**（2026-09-01 新增，見下方「為什麼要有 (4)」）

    參數 session_state: 通常傳 `st.session_state`；不傳則跳過 (3)。
    回傳 dict {ttl_cleared, st_cache_cleared, session_keys_popped, backoff_cleared}。
    ⚠️ `backoff_cleared` 是新增鍵。現行三個 UI 消費者
    （`ui/tab1_macro.py` / `ui/tab1_macro_longterm.py` / `ui/hot_money.py`）
    **都以字面 key 取值、沒有任何 `len()` 或迭代**，故新增鍵不影響它們；
    **本輪刻意不把它加進 `ui/tab1_macro.py` 的 toast 文字** —— 那是畫面上的
    欄位增減，依 §-1.5.4 / v3 §03-2 ① 須先出線框給客戶審，屬另一批。

    ## 為什麼要有 (4)（2026-09-01 第六輪；這是一個被實測出來的迴歸）

    2026-09-01 那批「熱錢失敗不入快取 + 來源退避」的改動，讓
    `repositories/hot_money_repository.py` 在**應用層失敗**時登記一個
    **dataset 粒度**的冷卻。那個冷卻**不在** `_TAB1_TTL_CACHE_NAMES` 裡
    （`_SOURCE_BACKOFF` 是 `_CACHE_REGISTRY` 的成員，不是 TTL cache 名），
    於是 (1)(2)(3) 全部清完之後，下一次呼叫仍然在
    `_fetch_foreign_flow_series_uncached` 進場處被 `should_skip` 擋下 ——
    **「強制重抓」一個封包都不發**，訊息還從「FinMind 402: quota」這種具體原因
    退化成「退避冷卻中」。

    **實測（402 持續失敗，同一支探針數上游 `sess.get`）**：
    按下按鈕後的上游請求數 base `b5b0464` = 1 ／ `98dcfd4` = **0** ⛔ ／ 本輪 = 1 ✅。
    對照組：sidebar「全域刷新」走 `global_refresh_all()` → `clear_all_caches()`
    → 整個 `_CACHE_REGISTRY`（含 `_SOURCE_BACKOFF`）→ **它一直是好的**。
    也就是「只有全域刷新逃得掉冷卻，Tab1 那顆按鈕逃不掉」。

    ⚠️ **(4) 的射程刻意很窄**：它呼叫的
    `repositories.hot_money_repository.clear_source_backoff()` **只解那一個
    dataset 鍵**，不碰 host 鍵、不碰別的來源 —— 「不誤殺 Tab2~Tab5」這個承諾
    因此延伸到退避狀態，而不是被它破壞。連按繞過退避的風險與其三條界線，
    完整寫在該函式的 docstring，**此處不重述（§2 SSOT）**。
    """
    _stat = {"ttl_cleared": 0, "st_cache_cleared": 0, "session_keys_popped": 0,
             "backoff_cleared": 0}
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
    # (4) 本檔登記的來源退避冷卻 —— 少了這一段，(1)(2) 清得再乾淨也發不出封包。
    #     ⚠️ 與 (2) 分開一個 try：(2) 失敗時 (4) 仍應執行，反之亦然
    #     （既有各層 try 互不牽連的慣例，同 infra/cache.py::global_refresh_all）。
    try:
        from repositories.hot_money_repository import clear_source_backoff
        _stat["backoff_cleared"] = clear_source_backoff()
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
