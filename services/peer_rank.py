"""services/peer_rank.py — L2 深度強化:同類基金四分位排名(v19.464,架構缺口 #2)。

補目標架構圖「策略選股引擎:1Y/3Y 四分位排名(Q1)」那一格。原 `services/fund_screening.py`
C3 的同儕排名邏輯**耦在 screen_funds 內、且無 caller 餵 peer_series_map** → 等於休眠。本檔把
「同類年化報酬 → 排名 → 四分位」抽成獨立純函式,供 UI 用「持倉 ∪ 選股池」的同類小 universe 呼叫。

§1 Fail-Loud —— **樣本量誠實**(本檔最重要的守則):
- 同類 < 2 檔 → 無從比較(不硬給名次)。
- 2~3 檔 → 只給相對排名 X/n,**不分四分位**(3 檔捏不出 Q1~Q4,硬分就是造假)。
- ≥ PEER_QUARTILE_MIN_N 檔 → 真四分位 + 揭露「同類 n 檔」分母。
§2.3 PIT:窗起用**序列自身最後日期**回推,不用系統「今天」(避免用未來對齊過去)。
§4.1 交易日/年:年化用實際跨越年數(日曆日 / 365.25)。純函式・零 IO・離線可驗(§8.2 L2)。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

# 本模組自有語意常數(非 inline magic;集中此處供測試/調參)
PEER_MIN_OBS: int = 50           # 一檔要參與排名的最低有效 NAV 點數
PEER_QUARTILE_MIN_N: int = 4     # 能分「四分位」的最低同類檔數(< 此只給相對排名)
PEER_MIN_SPAN_RATIO: float = 0.6  # 實際跨越年數 ≥ window × 此比例,才認定夠長


def _clean(series) -> "pd.Series | None":
    """→ 乾淨升冪、日期索引、>0 的 NAV Series;< 2 點或無法轉日期 → None。"""
    if series is None:
        return None
    s = pd.Series(series).dropna()
    if len(s) < 2:
        return None
    idx = pd.to_datetime(s.index, errors="coerce")
    s = s[idx.notna()]
    s.index = idx[idx.notna()]
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s = s[s > 0]
    return s if len(s) >= 2 else None


def annualized_return(series, window_years: float,
                      min_obs: int = PEER_MIN_OBS) -> Optional[float]:
    """窗內年化報酬 `(NAV_末 / NAV_窗起)^(1/實際年) − 1`。資料不足 → None(§1)。

    PIT(§2.3):窗起 = 序列**自身最後日期**回推 window_years,不用系統今天。
    實際跨越年數 < window_years × PEER_MIN_SPAN_RATIO → None(窗太短不硬算)。
    """
    s = _clean(series)
    if s is None or len(s) < min_obs:
        return None
    end_ts = s.index[-1]
    ref = end_ts - pd.Timedelta(days=window_years * 365.25)
    li = int(s.index.searchsorted(ref, side="left"))
    li = min(li, len(s) - 1)
    start_p = float(s.iloc[li])
    end_p = float(s.iloc[-1])
    years = (end_ts - s.index[li]).days / 365.25
    if years < window_years * PEER_MIN_SPAN_RATIO or start_p <= 0 or end_p <= 0 or years <= 0:
        return None
    return (end_p / start_p) ** (1.0 / years) - 1.0


def peer_annualized_returns(series_map: dict, window_years: float,
                            min_obs: int = PEER_MIN_OBS) -> dict:
    """{code → NAV series} → {code → 年化報酬}(只留算得出來的;§1 不補值)。"""
    out: dict = {}
    for code, ser in (series_map or {}).items():
        r = annualized_return(ser, window_years, min_obs=min_obs)
        if r is not None:
            out[str(code)] = r
    return out


def quartile_rank(code, returns: dict) -> dict:
    """目標 code 在同類 `returns`({code→年化報酬})中的名次 + 四分位。

    回 {rank, n, percentile, quartile, label, enough_sample}:
    - rank : 1 = 最佳(報酬最高);None = 無法排。
    - percentile : 0=最佳 ~ 1=最差(n>1);None = 無法算。
    - quartile : 'Q1'~'Q4';**樣本 < PEER_QUARTILE_MIN_N → None**(不硬分,§1)。
    - enough_sample : 是否 ≥ PEER_QUARTILE_MIN_N。
    """
    code = str(code)
    vals = {str(c): r for c, r in (returns or {}).items() if isinstance(r, (int, float))}
    n = len(vals)
    if code not in vals or n < 2:
        _lbl = "無同類可比(同類 < 2 檔)" if n < 2 else "自身無有效年化報酬"
        return {"rank": None, "n": n, "percentile": None, "quartile": None,
                "label": _lbl, "enough_sample": False}

    # 由高到低排;名次 1 = 報酬最高。並列時 sorted 穩定,以 code 次序打破(可重現,§5)。
    ordered = sorted(vals, key=lambda c: (-vals[c], c))
    rank_1 = ordered.index(code) + 1
    percentile = round((rank_1 - 1) / (n - 1), 3)

    if n >= PEER_QUARTILE_MIN_N:
        q = min(int((rank_1 - 1) / n * 4) + 1, 4)
        return {"rank": rank_1, "n": n, "percentile": percentile,
                "quartile": f"Q{q}", "enough_sample": True,
                "label": f"同類 {n} 檔中第 {rank_1} 名 · Q{q}"}
    return {"rank": rank_1, "n": n, "percentile": percentile,
            "quartile": None, "enough_sample": False,
            "label": f"同類僅 {n} 檔(樣本少)· 第 {rank_1}/{n} 名,不分四分位"}


def peer_quartile(code, series_map: dict, window_years: float,
                  min_obs: int = PEER_MIN_OBS) -> dict:
    """便捷入口:同類 {code→NAV} + 窗 → 目標的四分位 dict(組 returns → 排名一步到位)。"""
    returns = peer_annualized_returns(series_map, window_years, min_obs=min_obs)
    out = quartile_rank(code, returns)
    out["window_years"] = window_years
    return out


__all__ = ["annualized_return", "peer_annualized_returns", "quartile_rank", "peer_quartile"]
