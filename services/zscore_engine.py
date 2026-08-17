"""services/zscore_engine.py — L2 深度強化②:基金 Z-Score 位階 + 動態再平衡引擎。

Z-Score 統計位階:``Z = (NAV_last − 3年均線) / 3年標準差``(§4.1 用原幣 NAV,位階是價格自身行為)。
依景氣對策信號燈號動態調整門檻(綠燈放寬停利 Z>+2.0 避免太早下車;過熱紅燈收緊加碼)。
資產屬性分流:Core(平衡多重 / 貨幣市場,內建配置)**不進 Z-Score**;其餘(股票/債/資源/不動產,
對應 Income/Growth)進入。純函式・零 IO;NAV 序列與景氣分數由呼叫端傳入。

Fail-Loud(§1):有效點不足 / std=0 → z=None(位階不可信,不硬算);Core → applies=False 誠實標明。
常數集中 `shared.signal_thresholds`(§3.3)。
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from shared.signal_thresholds import (
    ZSCORE_CORE_BUCKETS,
    ZSCORE_MIN_OBS,
    ZSCORE_WINDOW_DAYS,
)

_BLANK_Z = {"z": None, "ma": None, "std": None, "last_nav": None,
            "n": 0, "status": "insufficient"}


def _clean_nav(nav_series) -> "pd.Series | None":
    """→ 乾淨升冪 NAV Series(dropna, >0, 唯一日期);<2 點 → None。與 portfolio 慣例一致。"""
    if nav_series is None:
        return None
    s = pd.Series(nav_series).dropna()
    if len(s) < 2:
        return None
    idx = pd.to_datetime(s.index, errors="coerce")
    s = s[idx.notna()]
    s.index = idx[idx.notna()]
    s = s.sort_index()
    s = s[~s.index.duplicated(keep="last")]
    s = s[s > 0]
    return s if len(s) >= 2 else None


def nav_zscore(nav_series, window: int = ZSCORE_WINDOW_DAYS,
               min_obs: int = ZSCORE_MIN_OBS) -> dict:
    """NAV 序列 → Z-Score 位階 dict {z, ma, std, last_nav, n, status}。

    取最近 ``window`` 個交易日算 μ/σ(§4.1 交易日,非日曆日);有效點 < min_obs 或 σ=0 → z=None(§1)。
    向量化(pandas tail + mean/std),無逐列迴圈(NFR-2)。
    """
    s = _clean_nav(nav_series)
    if s is None or len(s) < min_obs:
        return {**_BLANK_Z, "n": (0 if s is None else len(s))}
    _win = s.tail(window)
    _ma = float(_win.mean())
    _std = float(_win.std(ddof=1))
    _last = float(s.iloc[-1])
    if not np.isfinite(_std) or _std <= 0:               # σ=0(全同值)→ 位階無意義(§1)
        return {**_BLANK_Z, "n": len(_win), "status": "degenerate", "ma": round(_ma, 6),
                "std": 0.0, "last_nav": round(_last, 6)}
    _z = (_last - _ma) / _std
    return {"z": round(float(_z), 3), "ma": round(_ma, 6), "std": round(_std, 6),
            "last_nav": round(_last, 6), "n": len(_win), "status": "ok"}


def is_core_bucket(category) -> bool:
    """資產類別 → 是否為 Core(平衡多重 / 貨幣市場)→ 不做 Z-Score 擇時。無法對應 → False。"""
    try:
        from services.regime_fit import asset_bucket
        _bucket, _ = asset_bucket(category)
    except Exception:  # noqa: BLE001 — 分類失敗當非 Core(仍做 Z-Score,較保守不漏訊號)
        return False
    return _bucket in ZSCORE_CORE_BUCKETS


def rebalance_signal(nav_series, category=None, ndc_score: Optional[float] = None,
                     override: Optional[str] = None) -> dict:
    """Z-Score 動態再平衡訊號。

    回 {applies, action, z, stop_gain_z, add_z, light, fund_type, reason}。
    - Core(平衡/貨幣)→ applies=False(內建配置,不擇時,§1)。
    - 位階不可算 → action=None + reason。
    - z ≥ stop_gain_z → 停利/減碼;z ≤ add_z → 加碼/逢低;之間 → 持有。門檻依景氣燈號動態。
    """
    from services.allocation_ladder import dynamic_zscore_gates

    if is_core_bucket(category):
        return {"applies": False, "action": None, "z": None,
                "reason": "Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。"}

    _zi = nav_zscore(nav_series)
    _gates = dynamic_zscore_gates(ndc_score)
    _ft = None
    try:
        from services.fund_type_classifier import classify_fund_type
        _ft = classify_fund_type(nav_series, category=category, override=override).get("type")
    except Exception:  # noqa: BLE001 — 型態判定失敗不阻斷 Z-Score 訊號
        _ft = None

    _base = {"applies": True, "stop_gain_z": _gates["stop_gain_z"], "add_z": _gates["add_z"],
             "light": _gates["light"], "fund_type": _ft, "z": _zi["z"]}
    if _zi["z"] is None:
        return {**_base, "action": None,
                "reason": f"位階不可算({_zi['status']};有效點 {_zi['n']})—— 不硬判(§1)。"}
    _z = _zi["z"]
    if _z >= _gates["stop_gain_z"]:
        _action, _why = "停利/減碼", f"Z={_z:+.2f} ≥ 停利門檻 {_gates['stop_gain_z']:+.2f}(位階偏高)"
    elif _z <= _gates["add_z"]:
        _action, _why = "加碼/逢低", f"Z={_z:+.2f} ≤ 加碼門檻 {_gates['add_z']:+.2f}(位階偏低)"
    else:
        _action, _why = "持有", f"Z={_z:+.2f} 落 [{_gates['add_z']:+.2f}, {_gates['stop_gain_z']:+.2f}] 中性"
    _lt = f"(景氣{_gates['light']}燈)" if _gates["light"] else "(無景氣燈號,用預設門檻)"
    return {**_base, "action": _action, "reason": f"{_why} {_lt}。"}


__all__ = ["nav_zscore", "is_core_bucket", "rebalance_signal"]
