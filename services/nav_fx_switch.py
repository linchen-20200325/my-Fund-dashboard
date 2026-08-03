"""services/nav_fx_switch.py — 淨值位階 × 匯率位階 二維買賣切換(v19.426)。L2 純函式,零 IO。

外幣基金的台幣總報酬 ≈ 淨值變動 × 匯率變動 → 最佳進出是「兩個都便宜/都貴」:
- 進場佳:淨值低基期 **且** 台幣強(USDTWD 低,TWD→USD 換匯便宜)
- 出場佳:淨值高基期 **且** 台幣弱(USDTWD 高,換回 TWD 划算)

§1 fail-loud:缺料 / σ=0 / 短史 → None(不臆測)。§4.1 sign convention:z 負=台幣強=進場有利,
與 NAV σ rank 同向(愈負愈進場有利)。§4.4 除零 guard。常數走 shared.signal_thresholds SSOT。
匯率位階用 **z-score vs 近一年均值**(非 HWM)—— 匯率對稱、均值回歸,買低賣高兩向都要衡量。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    FX_REGIME_MIN_OBS,
    FX_REGIME_ROBUST_OBS,
    FX_STRONG_TWD_SIGMA,
    FX_WEAK_TWD_SIGMA,
)

_NA = "⬜ 無法判定"
_TWD = "➖ 台幣計價"
_BUY = "🟢 雙便宜(進場佳)"
_SELL = "🔴 雙貴(出場佳)"
_WATCH = "⚪ 觀望"


def fx_regime(fx_series, spot=None) -> dict:
    """USDTWD 位階(z-score vs 近期均值)。fx_series 由 L3 抓好傳入(窗口 = FX_REGIME_WINDOW_DAYS)。

    → {regime: strong_twd|neutral|weak_twd|None, z, cur, mean, std, n, robust, error}。
    spot None/≤0 → 用序列末值(§4.6);有效點<MIN 或 σ=0 → regime None(§1)。
    """
    import pandas as pd

    _blank = {"regime": None, "z": None, "cur": None, "mean": None, "std": None,
              "n": 0, "robust": False, "error": None}
    if fx_series is None:
        return {**_blank, "error": "無 FX 序列"}
    _s = pd.Series(fx_series).dropna()
    _s = _s[_s > 0]                                   # 匯率恆正
    _n = len(_s)
    if _n < FX_REGIME_MIN_OBS:
        return {**_blank, "n": _n, "error": f"FX 歷史不足(<{FX_REGIME_MIN_OBS})"}
    _mean = float(_s.mean())
    _std = float(_s.std())                            # ddof=1
    if _std <= 0:
        return {**_blank, "n": _n, "error": "FX σ=0(序列退化)"}
    _cur = float(spot) if (spot is not None and float(spot) > 0) else float(_s.iloc[-1])
    _z = (_cur - _mean) / _std
    if _z <= FX_STRONG_TWD_SIGMA:
        _reg = "strong_twd"
    elif _z >= FX_WEAK_TWD_SIGMA:
        _reg = "weak_twd"
    else:
        _reg = "neutral"
    return {"regime": _reg, "z": round(_z, 3), "cur": round(_cur, 4),
            "mean": round(_mean, 4), "std": round(_std, 4), "n": _n,
            "robust": _n >= FX_REGIME_ROBUST_OBS, "error": None}


def nav_fx_signal(nav_level, fx_regime_label) -> dict:
    """2D 買賣訊號。nav_level = classify_base 輸出(high/mid/low/unknown/None);
    fx_regime_label = strong_twd/neutral/weak_twd/None。

    → {signal, tier(buy/sell/watch/na), rationale}。只有兩純角有向(低+強=進場 / 高+弱=出場),
    其餘皆 ⚪ 觀望(細節放 rationale,不遺失資訊)。
    """
    if nav_level in (None, "unknown") or fx_regime_label is None:
        _why = ("缺淨值基期" if nav_level in (None, "unknown") else "") \
            + ("、" if (nav_level in (None, "unknown") and fx_regime_label is None) else "") \
            + ("缺匯率位階" if fx_regime_label is None else "")
        return {"signal": _NA, "tier": "na", "rationale": f"{_why} → 無法判定。"}

    if nav_level == "low" and fx_regime_label == "strong_twd":
        return {"signal": _BUY, "tier": "buy",
                "rationale": "淨值低基期 + 台幣強(換匯便宜)→ 雙重便宜,進場條件較佳。"}
    if nav_level == "high" and fx_regime_label == "weak_twd":
        return {"signal": _SELL, "tier": "sell",
                "rationale": "淨值高基期 + 台幣弱(換回台幣划算)→ 雙重划算,出場條件較佳。"}

    _nav_zh = {"low": "淨值低基期", "mid": "淨值中性", "high": "淨值高基期"}.get(nav_level, nav_level)
    _fx_zh = {"strong_twd": "台幣強", "neutral": "匯率中性", "weak_twd": "台幣弱"}[fx_regime_label]
    return {"signal": _WATCH, "tier": "watch",
            "rationale": f"{_nav_zh} + {_fx_zh}(一好一壞或中性)→ 觀望(參考傾向,非擇時保證)。"}
