"""services/fund_type_classifier.py — 基金型態分類:震盪型 vs 成長型(v19.428)。L2 純函式,零 IO。

用 **Efficiency Ratio(Kaufman ER)** 量「趨勢 vs 來回震盪」:
    ER = |NAV[末] − NAV[首]| / Σ|NAV[i] − NAV[i−1]|   ∈ [0,1]
- ER 高 → 走勢有方向 = **成長型**(順勢、看總經出場)
- ER 低 → 來回磨 = **震盪型**(適合「高基期 → 低基期」輪動賺回歸)
- 灰帶(之間)→ 用資產類別打破平手(股票→成長 / 其餘→震盪)

§1 誠實:有效點 < TYPE_MIN_OBS / 路徑長度=0(退化)→ **None(無法判定)**,不硬判;
**使用者手動 override 永遠優先**(存在選股池)。ER 用**原幣** NAV(型態是價格自身行為,與匯率無關)。
常數走 shared.signal_thresholds SSOT(§3.3)。
"""
from __future__ import annotations

from shared.signal_thresholds import (
    TYPE_ER_GROWTH_MIN,
    TYPE_ER_RANGE_MAX,
    TYPE_LOOKBACK_DAYS,
    TYPE_MIN_OBS,
)

RANGE = "震盪"      # 震盪型
GROWTH = "成長"     # 成長型
_VALID_OVERRIDES = (RANGE, GROWTH)


def efficiency_ratio(nav_series, lookback: int = TYPE_LOOKBACK_DAYS) -> "float | None":
    """原幣 NAV → Efficiency Ratio ∈ [0,1](取最近 lookback 個有效點)。

    §1:有效點 < TYPE_MIN_OBS → None;路徑總長度 ≤ 0(全平/退化)→ None(§4.4 除零 guard)。
    """
    from services.portfolio_performance import _clean_nav
    _s = _clean_nav(nav_series)
    if _s is None or len(_s) < TYPE_MIN_OBS:
        return None
    _w = _s.tail(int(lookback)) if lookback and lookback > 0 else _s
    if len(_w) < TYPE_MIN_OBS:
        return None
    _diffs = _w.diff().dropna()
    _path = float(_diffs.abs().sum())               # 路徑總長度
    if _path <= 0:
        return None
    _net = abs(float(_w.iloc[-1]) - float(_w.iloc[0]))
    return _net / _path


def classify_fund_type(nav_series, category=None, override=None,
                       lookback: int = TYPE_LOOKBACK_DAYS) -> dict:
    """基金型態分類 → {type, er, method, rationale}。

    type ∈ {"震盪","成長",None};override(使用者手動,存選股池)優先;
    ER ≥ GROWTH_MIN → 成長 / ≤ RANGE_MAX → 震盪 / 灰帶 → asset_bucket 打破平手;
    有效點不足 → type None(§1 誠實回「無法判定」,不硬判)。
    """
    _ov = str(override).strip() if override is not None else ""
    _er = efficiency_ratio(nav_series, lookback)

    if _ov in _VALID_OVERRIDES:                     # 手動 override 優先(即使 ER 可算)
        return {"type": _ov, "er": (round(_er, 3) if _er is not None else None),
                "method": "override",
                "rationale": f"使用者手動指定「{_ov}型」(優先於自動判定)。"}

    if _er is None:
        return {"type": None, "er": None, "method": "insufficient",
                "rationale": f"NAV 有效點 < {TYPE_MIN_OBS} 或走勢退化 → 無法判定型態(§1 不硬判)。"}

    if _er >= TYPE_ER_GROWTH_MIN:
        return {"type": GROWTH, "er": round(_er, 3), "method": "er",
                "rationale": f"ER={_er:.2f} ≥ {TYPE_ER_GROWTH_MIN}(走勢有方向)→ 成長型。"}
    if _er <= TYPE_ER_RANGE_MAX:
        return {"type": RANGE, "er": round(_er, 3), "method": "er",
                "rationale": f"ER={_er:.2f} ≤ {TYPE_ER_RANGE_MAX}(來回震盪)→ 震盪型。"}

    # 灰帶:資產類別打破平手(股票 → 成長傾向;其餘 → 震盪傾向)
    from services.regime_fit import asset_bucket
    _bucket, _ = asset_bucket(category)
    _type = GROWTH if _bucket == "股票" else RANGE
    return {"type": _type, "er": round(_er, 3), "method": "er+bucket",
            "rationale": (f"ER={_er:.2f} 落灰帶({TYPE_ER_RANGE_MAX}~{TYPE_ER_GROWTH_MIN}),"
                          f"依資產類別「{_bucket or '未知'}」判為 {_type}型。")}
