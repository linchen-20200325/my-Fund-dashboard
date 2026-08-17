"""services/allocation_ladder.py — L2 深度強化①:總經風控分顯性化 → 資產水位 + 動態門檻。

把既有 `services.macro.composite_score.composite_verdict()` 的 5 級評價**顯性化**成
「動態持股 / 債券 / 貨幣基金配置水位」+ 結合**景氣對策信號燈號**動態調整停利 / 加碼的
Z-Score 門檻。純函式・零 IO(composite 分數與 NDC 分數由呼叫端傳入)。

- 不推翻既有:water level 建立在 `composite_verdict` 的 level 上(cutoffs 仍走其 SSOT)。
- Fail-Loud(§1):composite 缺 → 回 status="unknown" 不猜;NDC 缺 → 用預設門檻並標明。
- 所有水位 / 門檻常數集中 `shared.signal_thresholds`(§3.3 反捏造)。
"""
from __future__ import annotations

from typing import Optional

from shared.signal_thresholds import (
    ALLOCATION_LADDER,
    NDC_LIGHT_BANDS,
    ZSCORE_ADD_BY_LIGHT,
    ZSCORE_ADD_DEFAULT,
    ZSCORE_STOP_GAIN_BY_LIGHT,
    ZSCORE_STOP_GAIN_DEFAULT,
)


def ndc_light(ndc_score: Optional[float]) -> tuple:
    """NDC 景氣對策信號綜合分數(9~45)→ (燈號, 描述)。非數/超域 → (None, None)(§1 不硬歸)。"""
    try:
        _s = float(ndc_score)
    except (TypeError, ValueError):
        return (None, None)
    if _s < 9 or _s > 45:
        return (None, None)
    for _hi, _light, _desc in NDC_LIGHT_BANDS:
        if _s <= _hi:
            return (_light, _desc)
    return (None, None)


def dynamic_zscore_gates(ndc_score: Optional[float]) -> dict:
    """依景氣燈號回動態 Z-Score 門檻:{stop_gain_z, add_z, light, source}。

    綠燈放寬停利(Z>+2.0 才停,避免太早下車);過熱紅燈收緊加碼(要更低才加)。
    無景氣燈號 → 用預設門檻,source='default'(誠實標明非動態)。
    """
    _light, _ = ndc_light(ndc_score)
    if _light is None:
        return {"stop_gain_z": ZSCORE_STOP_GAIN_DEFAULT, "add_z": ZSCORE_ADD_DEFAULT,
                "light": None, "source": "default"}
    return {
        "stop_gain_z": ZSCORE_STOP_GAIN_BY_LIGHT[_light],
        "add_z": ZSCORE_ADD_BY_LIGHT[_light],
        "light": _light,
        "source": "ndc",
    }


def allocation_from_composite(composite_score: Optional[float],
                              ndc_score: Optional[float] = None) -> dict:
    """總經 composite 分數 → 資產配置水位 + 動態門檻。

    回 {status, level, icon, allocation:{equity,bond,cash}, stop_gain_z, add_z,
        light, action_text, provenance}。
    composite 缺/非數 → status='unknown'(§1 不給假水位)。
    """
    _prov = {"composite_score": composite_score, "ndc_score": ndc_score,
             "module": "allocation_ladder", "ladder": "DESIGN@signal_thresholds"}
    try:
        _cs = float(composite_score)
    except (TypeError, ValueError):
        return {"status": "unknown", "level": None, "allocation": None,
                "reason": "composite 分數不可用(§1 不猜水位)", "provenance": _prov}

    from services.macro.composite_score import composite_verdict
    _icon, _level, _color, _action = composite_verdict(_cs)
    _alloc = ALLOCATION_LADDER.get(_level)
    if _alloc is None:                                   # verdict level 非預期 → 誠實回報
        return {"status": "unknown", "level": _level, "allocation": None,
                "reason": f"未知 verdict level「{_level}」", "provenance": _prov}

    _gates = dynamic_zscore_gates(ndc_score)
    return {
        "status": "ok",
        "level": _level,
        "icon": _icon,
        "allocation": dict(_alloc),                     # copy,避免呼叫端改到 SSOT
        "stop_gain_z": _gates["stop_gain_z"],
        "add_z": _gates["add_z"],
        "light": _gates["light"],
        "action_text": _action,                         # 沿用 verdict 既有白話(現金水位一致)
        "provenance": _prov,
    }


__all__ = ["ndc_light", "dynamic_zscore_gates", "allocation_from_composite"]
