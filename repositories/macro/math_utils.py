"""repositories/macro/math_utils.py — v19.203 P2-5 純數學 utility(z-score / trend / recession_probability /
spread_series / make_indicator / flatten_snapshot)。"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import pandas as pd

from shared.signal_thresholds import (
    RECESSION_LOGIT_COEF_INTERCEPT, RECESSION_LOGIT_COEF_SPREAD,
)


def zscore(s: pd.Series) -> pd.Series:
    """標準分數 z-score(W5-5 §1:std=0 / NaN 退化時回全 NaN + log)。

    SSOT for zscore — services.macro_service 端 import 此版本(消 DRY)。
    caller 須以 isna() 檢查 NaN,**禁止**把 NaN 視為 0(掩蓋退化情境)。
    """
    if s.empty:
        return s
    std = float(s.std())
    if std == 0 or np.isnan(std):
        print(f"[macro_repository zscore] std=0/NaN 退化:len={len(s)}, mean={s.mean()},回 NaN")
        return pd.Series([np.nan] * len(s), index=s.index)
    return (s - s.mean()) / std


def trend_arrow(vals: list[float]) -> str:
    """
    依最近 N 點走勢給出口語化趨勢標記。
    回傳: '持續上升 ↑' / '持續下降 ↓' / '最近反彈 ↗' / '最近回落 ↘' / ''
    """
    if len(vals) < 3:
        return ""
    diffs = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    # 「持續」描述必須要求最後一點同向，否則該歸類為「最近反彈/回落」
    if pos >= len(diffs) - 1 and diffs[-1] > 0:
        return "持續上升 ↑"
    if neg >= len(diffs) - 1 and diffs[-1] < 0:
        return "持續下降 ↓"
    return "最近反彈 ↗" if diffs[-1] > 0 else "最近回落 ↘"


def recession_probability(spread_10y3m: Optional[float]) -> Optional[float]:
    """
    用 10Y-3M 利差做 logistic 回歸估算未來 12 個月衰退機率(%)。
    spread_10y3m 為 None 時回傳 None。
    """
    if spread_10y3m is None:
        return None
    logit = RECESSION_LOGIT_COEF_SPREAD * spread_10y3m + RECESSION_LOGIT_COEF_INTERCEPT
    return round(1 / (1 + math.exp(-logit)) * 100, 1)


def spread_series(
    df_long: pd.DataFrame,
    df_short: pd.DataFrame,
    n_pts: int = 60,
) -> pd.Series:
    """
    計算兩個 FRED 序列的利差時序。
    優先用月頻對齊;若月頻 inner join 為空(例如 short 序列為日頻 TB3MS)
    則退回 merge_asof 容忍 40 天的回溯對齊。
    """
    if df_long.empty or df_short.empty:
        return pd.Series(dtype=float)

    dl = df_long[["date", "value"]].set_index("date").rename(columns={"value": "v_l"})
    ds = df_short[["date", "value"]].set_index("date").rename(columns={"value": "v_s"})
    # W5-2 §1: resample("ME").last() 取月底值後 ffill 補缺月(macro 月頻指標若某月未發布用前期);
    # 此為 yield spread 計算的業務正確補值(月度差分容忍上期值),加 log 透明化
    dl_m = dl.resample("ME").last()
    ds_m = ds.resample("ME").last()
    _dl_ffill = int(dl_m["v_l"].isna().sum())
    _ds_ffill = int(ds_m["v_s"].isna().sum())
    dl_m = dl_m.ffill()
    ds_m = ds_m.ffill()
    if _dl_ffill or _ds_ffill:
        print(f"[macro_repo _spread_series] ffill v_l={_dl_ffill}, v_s={_ds_ffill} 個月份")
    merged = dl_m.join(ds_m, how="inner").dropna()
    if not merged.empty:
        return (merged["v_l"] - merged["v_s"]).tail(n_pts)

    dl2 = df_long[["date", "value"]].rename(columns={"value": "v_l"}).sort_values("date")
    ds2 = df_short[["date", "value"]].rename(columns={"value": "v_s"}).sort_values("date")
    m = pd.merge_asof(
        dl2, ds2, on="date",
        tolerance=pd.Timedelta("40d"), direction="backward",
    ).dropna().set_index("date")
    return (m["v_l"] - m["v_s"]).tail(n_pts)


# ══════════════════════════════════════════════════════════════
# 統一 snapshot schema 工具
# ══════════════════════════════════════════════════════════════

def make_indicator(
    key: str,
    name: str,
    value: float,
    *,
    prev: Optional[float] = None,
    unit: str = "",
    type_: str = "同時",
    date: str = "",
    series: Optional[pd.Series] = None,
    desc: str = "",
    weight: float = 1.0,
) -> dict:
    """
    建立統一格式的指標 dict。

    fund 端原本就用富 dict(value/prev/trend/series/...),stock 端用扁平 float。
    我們以富 dict 為共同 schema,扁平結構可由 flatten_snapshot() 動態產生。
    """
    trend = ""
    if series is not None and len(series) >= 3:
        trend = trend_arrow([float(x) for x in series.tail(6).tolist()])
    return {
        "key":    key,
        "name":   name,
        "value":  value,
        "prev":   prev,
        "unit":   unit,
        "type":   type_,
        "date":   date,
        "desc":   desc,
        "trend":  trend,
        "series": series,
        "weight": weight,
    }


def flatten_snapshot(rich: dict) -> dict:
    """
    將富 dict snapshot 轉為扁平 dict(key 小寫),方便相容 stock 端
    macro_alert.py / macro_state_locker.py 既有 API。

    rich = {"VIX": {"value": 28.3, ...}, "CPI": {"value": 3.1, ...}}
    →     {"vix": 28.3, "cpi": 3.1}
    """
    out: dict = {}
    for k, v in (rich or {}).items():
        if isinstance(v, dict) and v.get("value") is not None:
            out[k.lower()] = v["value"]
    return out
