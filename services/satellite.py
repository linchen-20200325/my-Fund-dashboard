"""services/satellite.py — L2 深度強化:衛星部位停利自動化(v19.466)。

補郭俊宏 80/20「衛星獲利達 15-20% 嚴格停利、滾回核心」那一格(user 2026-08-18 核准規格)。
把「衛星判定 + 未實現獲利% → 停利燈」的**判燈邏輯**抽成純函式;衛星判定(is_satellite)與
未實現獲利%(從成本算)由呼叫端(T7 帳本,唯一同時握有兩者的 UI)算好後傳入。

§8.2:純函式・零 IO;不 import L3 的 `resolve_core_flag`(改由 UI 傳 bool,避免上行依賴)。
§3.3:門檻走 `shared.signal_thresholds`(15% 分批 / 20% 強制)。
§1 Fail-Loud:非衛星 → 不判(核心長期領息);未填成本(pct=None)→ 誠實「無法判停利」不當 0%。
"""
from __future__ import annotations

from typing import Optional

from shared.colors import MATERIAL_ORANGE, TRAFFIC_NEUTRAL, TRAFFIC_RED
from shared.signal_thresholds import (
    SATELLITE_STOP_GAIN_BATCH_PCT,
    SATELLITE_STOP_GAIN_FORCE_PCT,
)


def satellite_stop_gain(unrealized_pct: Optional[float], is_satellite: bool) -> dict:
    """衛星停利燈。純函式,離線可驗。

    Args:
        unrealized_pct: 未實現獲利 %(從**成本**算,不含息;T7 帳本 `_pl_pct`)。None = 未填成本。
        is_satellite: 是否衛星部位(呼叫端以 `resolve_core_flag` 反推;核心=False)。

    Returns: {lamp, emoji, color, status, pct, note}
        - lamp: "強制停利" / "分批停利" / None
        - status: "force" / "batch" / "hold" / "core" / "no_cost"
    """
    if not is_satellite:
        return {"lamp": None, "emoji": "", "color": TRAFFIC_NEUTRAL, "status": "core",
                "pct": None, "note": "核心部位(長期領息,不做停利)"}
    if not isinstance(unrealized_pct, (int, float)):
        return {"lamp": None, "emoji": "⬜", "color": TRAFFIC_NEUTRAL, "status": "no_cost",
                "pct": None, "note": "未填平均成本 → 無法判停利(§1 不當 0%)"}

    pct = float(unrealized_pct)
    if pct >= SATELLITE_STOP_GAIN_FORCE_PCT:
        return {"lamp": "強制停利", "emoji": "🔴", "color": TRAFFIC_RED, "status": "force",
                "pct": round(pct, 2),
                "note": f"衛星獲利 {pct:+.1f}% ≥ {SATELLITE_STOP_GAIN_FORCE_PCT:.0f}% "
                        "→ 獲利了結、資金轉回核心"}
    if pct >= SATELLITE_STOP_GAIN_BATCH_PCT:
        return {"lamp": "分批停利", "emoji": "💰", "color": MATERIAL_ORANGE, "status": "batch",
                "pct": round(pct, 2),
                "note": f"衛星獲利 {pct:+.1f}% ≥ {SATELLITE_STOP_GAIN_BATCH_PCT:.0f}% → 分批停利"}
    return {"lamp": None, "emoji": "", "color": TRAFFIC_NEUTRAL, "status": "hold",
            "pct": round(pct, 2),
            "note": f"衛星獲利 {pct:+.1f}%,未達 {SATELLITE_STOP_GAIN_BATCH_PCT:.0f}% 停利門檻,續抱"}


__all__ = ["satellite_stop_gain"]
