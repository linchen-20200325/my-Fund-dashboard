"""services/macro/_helpers.py — v19.199 P1-7 共用 helper + module-level imports/constants。

從 macro_service 主檔抽出,供 us_indicators / turning_points / causal_sankey / china 子檔複用。
"""
from __future__ import annotations

import pandas as pd, numpy as np, math
from typing import Optional
from concurrent.futures import ThreadPoolExecutor as _TPE_macro
from repositories.macro_repository import fetch_fred, fetch_yf_close, fetch_ism_pmi, fetch_fred_batch
from shared.signal_thresholds import (  # v19.74 W2 SSOT
    SAHM_RECESSION_THRESHOLD,
    CFNAI_RECESSION_THRESHOLD,
    RECESSION_LOGIT_COEF_SPREAD,
    RECESSION_LOGIT_COEF_INTERCEPT,
    TPI_BUSINESS_WEIGHT_RATIO,
    TPI_FINANCIAL_WEIGHT_RATIO,
    TPI_MONETARY_WEIGHT_RATIO,
)
# C2-D v19.160 — alert 也對齊 SSOT(全站 22/30 收尾)
from shared.macro_buckets import _VIX_RED as _MB_VIX_RED, _VIX_YELLOW as _MB_VIX_YELLOW
from shared.fred_series import (
    FRED_AMTMNO,
    FRED_CCSA,
    FRED_CFNAI,
    FRED_CHF_USD,
    FRED_CPI,
    FRED_DGS10,
    FRED_DGS2,
    FRED_DGS3MO,
    FRED_DRTSCILM,
    FRED_DXY,
    FRED_FED_BS,
    FRED_FED_FUNDS,
    FRED_HSN1F,
    FRED_HY_SPREAD,
    FRED_ICSA,
    FRED_ISM_PMI,
    FRED_JPY_USD,
    FRED_M2,
    FRED_M2_WEEKLY,
    FRED_MNFCTRIRSA,
    FRED_PAYEMS,
    FRED_PERMIT,
    FRED_PPI,
    FRED_RRP,
    FRED_SAHM,
    FRED_T10Y2Y,
    FRED_T5YIE,
    FRED_TGA,
    FRED_UMCSENT,
    FRED_UNRATE,
)
from shared.colors import MATERIAL_GREEN, MATERIAL_ORANGE, MATERIAL_RED
from shared.macro_thresholds_v2 import (  # F-GRAY-4 v19.169 CPI/HY + v19.179 PMI + v19.184 M2/FedBS
    CPI_YOY_THRESHOLDS as _CPI_THR,
    HY_SPREAD_THRESHOLDS as _HY_THR,
    PMI_THRESHOLDS as _PMI_THR,
    M2_THRESHOLDS as _M2_THR,
    FED_BS_THRESHOLDS as _FEDBS_THR,
)

# F-GRAY-4 v19.178: CPI_YOY inflection + regime SSOT (SPEC §16.2)
_CPI_WARN_ABOVE = _CPI_THR["inflection_detection"]["warn_above"]
_CPI_BULL_LOW = _CPI_THR["inflection_detection"]["bull_low"]
_CPI_BULL_HIGH = _CPI_THR["inflection_detection"]["bull_high"]
_CPI_MK_GOLDEN_BELOW = _CPI_THR["inflection_detection"]["mk_golden_below"]
_CPI_REGIME_OVERHEAT = _CPI_THR["regime_classification"]["overheat_above"]

# F-GRAY-4 v19.179: PMI inflection + growth + alert + regime SSOT (SPEC §16.2)
_PMI_INFL_REBOUND = _PMI_THR["inflection_detection"]["rebound_below"]       # 50.0
_PMI_INFL_EXPANSION = _PMI_THR["inflection_detection"]["expansion_above"]   # 50.0
_PMI_INFL_PEAK_WARN = _PMI_THR["inflection_detection"]["peak_warning_above"]  # 55.0
_PMI_GROWTH_EXPANSION = _PMI_THR["growth_signal"]["expansion_above"]        # 50.0
_PMI_ALERT_CONTRACT = _PMI_THR["alert_generation"]["contraction_below"]     # 50.0
_PMI_REGIME_STRONG = _PMI_THR["regime_classification"]["strong_growth_above"]  # 52.0(新觀念真正枯榮線)
_PMI_REGIME_CONTRACT = _PMI_THR["regime_classification"]["contraction_below"]  # 50.0

# F-GRAY-4 v19.184: M2 / Fed BS score_function SSOT (SPEC §16.2)
_M2_EASING = _M2_THR["score_function"]["easing_above"]            # 5.0
_M2_TIGHTENING = _M2_THR["score_function"]["tightening_below"]    # 0.0
_FEDBS_EXPANSION = _FEDBS_THR["score_function"]["expansion_above"]    # 5.0
_FEDBS_CONTRACTION = _FEDBS_THR["score_function"]["contraction_below"]  # -5.0

# F-GRAY-4 v19.169: HY_SPREAD stoplight SSOT (SPEC §16.2)
_HY_YELLOW = _HY_THR["stoplight"]["yellow_below"]    # 6.0 — alert 觸發點

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
ENGINE_VERSION = "v18.2_tw_macro"
_INDICATOR_SNAPSHOT: dict = {}

# v19.57 C1：Tab1（總經 + 熱錢 + 流動性）獨占的 cached 函式名單
# 不含 Tab2~Tab5 共用（fetch_fund_from_moneydj_url / get_latest_nav / Tab3 GSheet policy 等）
_TAB1_TTL_CACHE_NAMES = frozenset({
    "fetch_fred",                          # repositories/macro_repository.py
    "fetch_yf_close",                      # repositories/macro_repository.py
    "fetch_defillama_stablecoin_mcap",     # repositories/macro_repository.py
    "fetch_macro_compass",                 # repositories/macro_repository.py
    "fetch_ndc_signal_history",            # services/macro_tw_local_fetch.py
    "fetch_tw_pmi_local",                  # services/macro_tw_local_fetch.py
    "fetch_tw_export_yoy",                 # services/macro_tw_local_fetch.py
    "fetch_foreign_consecutive_days",      # services/macro_tw_local_fetch.py
})

# v19.57 C1：Tab1 自有 session_state cache 鍵（強制重抓時連帶 pop）
_TAB1_SESSION_KEYS = (
    "_radar_v1921_top", "_tp_v1948_top", "indicators",
    "phase_info", "news_items", "systemic_risk_data",
    "_fred_sources",
)


def _fred(sid, key, n=250):
    """[NAS Proxy 遷移] 薄殼委派給 macro_core.fetch_fred()。
    原 requests.get 直連已改為 proxy_helper.fetch_url,確保走 NAS 中繼站。
    保留同名同 signature,呼叫端無需變更。"""
    return fetch_fred(sid, key, n=n)

def _yf_s(ticker, period="2y"):
    """[NAS Proxy 遷移] 薄殼委派給 macro_core.fetch_yf_close()。
    原 yfinance .history() 不走 proxy,易遭 Yahoo 限流;改打 Chart REST API
    透過 NAS 中繼,取得台灣 IP 出口。"""
    return fetch_yf_close(ticker, range_=period)

def _trend(vals):
    if len(vals) < 3: return ""
    diffs = [vals[i]-vals[i-1] for i in range(1, len(vals))]
    pos = sum(1 for d in diffs if d > 0); neg = sum(1 for d in diffs if d < 0)
    if pos >= len(diffs)-1: return "持續上升 ↑"
    if neg >= len(diffs)-1: return "持續下降 ↓"
    return "最近反彈 ↗" if diffs[-1] > 0 else "最近回落 ↘"

def _safe_last(df, n=2):
    if df.empty or len(df) < n: return [None]*n
    v = df["value"].tolist()
    return [v[-i] for i in range(1, n+1)]

def _spread_series(df_long, df_short, n_pts=60):
    if df_long.empty or df_short.empty: return pd.Series(dtype=float)
    dl = df_long[["date","value"]].set_index("date").rename(columns={"value":"v_l"}).copy()
    ds = df_short[["date","value"]].set_index("date").rename(columns={"value":"v_s"}).copy()
    # W5-2 §1: 月底重採後 ffill 補缺月(同 macro_repository._spread_series 註解),加 log
    dl_m = dl.resample("ME").last()
    ds_m = ds.resample("ME").last()
    _dl_ffill = int(dl_m["v_l"].isna().sum())
    _ds_ffill = int(ds_m["v_s"].isna().sum())
    dl_m = dl_m.ffill()
    ds_m = ds_m.ffill()
    if _dl_ffill or _ds_ffill:
        print(f"[macro_service _spread_series] ffill v_l={_dl_ffill}, v_s={_ds_ffill} 個月份")
    merged = dl_m.join(ds_m, how="inner").dropna()
    if merged.empty:
        dl2 = df_long[["date","value"]].rename(columns={"value":"v_l"}).sort_values("date")
        ds2 = df_short[["date","value"]].rename(columns={"value":"v_s"}).sort_values("date")
        m = pd.merge_asof(dl2, ds2, on="date", tolerance=pd.Timedelta("40d"), direction="backward").dropna()
        m = m.set_index("date")
        return (m["v_l"] - m["v_s"]).tail(n_pts)
    return (merged["v_l"] - merged["v_s"]).tail(n_pts)

def recession_probability(spread_10y3m):
    """用 10Y-3M 利差做 logistic 回歸估算衰退機率"""
    if spread_10y3m is None: return None
    logit = RECESSION_LOGIT_COEF_SPREAD * spread_10y3m + RECESSION_LOGIT_COEF_INTERCEPT
    return round(1 / (1 + math.exp(-logit)) * 100, 1)

