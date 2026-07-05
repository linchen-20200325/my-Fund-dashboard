"""services/macro/action_light.py — 總經「現在能不能買」總結燈(L2 純函式,zero-IO)。

v19.316 功能盤點改進 #4-①:總經頁子視圖多(即時/中期/短線/長期/拐點),缺一個「一句話結論」。
本函式把既有訊號融成 🟢 可加碼 / 🟡 持有 / 🔴 減碼,附觸發理由,供 UI 提到最上面。

設計(user 2026-07-05 批准的草案):
  1. **硬衰退/恐慌訊號 override**(任一亮 → 🔴,不管景氣位階多高 —— 安全層):
     - 殖利率曲線倒掛(10Y-2Y 或 10Y-3M < 0)
     - Sahm 規則 ≥ 0.5(衰退警報)
     - VIX ≥ 30(市場恐慌 / 高波動)
  2. 無 override → 依景氣位階(calc_macro_phase 的 0-10 score,即畫面「N/10」):
     - ≥ 6.5 → 🟢 可加碼；4.0~6.5 → 🟡 持有;< 4.0 → 🔴 減碼
  3. 位階缺 → 🟡 資料不足,不下假綠燈(§1 Fail-Loud)。

**這是「位階/機率」不是「擇時」**:override 是保守安全層(寧可少賺不要住套房),
非精準買賣點。所有燈都附「為什麼」讓 user 自行判斷。
"""
from __future__ import annotations

from shared.signal_thresholds import SAHM_RECESSION_THRESHOLD

# ── 門檻(self-contained mini-SSOT;provenance 註明來源)──────────────
_YIELD_INVERT_PCT: float = 0.0    # 殖利率利差 < 0 = 倒掛(古典衰退領先訊號)
_VIX_PANIC: float = 30.0          # C2 v19.160 全站 universal panic = 30(對稱 tests/test_cross_site_cutoffs)
_BUY_SCORE_10: float = 6.5        # 景氣位階 ≥ 此 → 🟢 可加碼(0-10 scale;可調)
_HOLD_SCORE_10: float = 4.0       # 景氣位階 ≥ 此 → 🟡 持有;< 此 → 🔴 減碼


def _val(indicators: dict, key: str) -> "float | None":
    """從 indicators dict 取某指標的 value(缺 / 型別錯 → None)。"""
    if not isinstance(indicators, dict):
        return None
    node = indicators.get(key)
    if not isinstance(node, dict):
        return None
    v = node.get("value")
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def macro_action_light(indicators: dict,
                       phase_score_10: "float | None" = None) -> dict:
    """總經買/賣總結燈。

    Args:
        indicators: fetch_all_indicators 的 dict(需含 YIELD_10Y2Y / YIELD_10Y3M /
                    VIX / SAHM 的 {"value": ...})。
        phase_score_10: 景氣位階 0-10(calc_macro_phase 的 score);None → 資料不足。

    Returns:
        {"light": "🟢"/"🟡"/"🔴", "action": str, "reasons": list[str], "override": bool}
    """
    # ── 1. 硬衰退 / 恐慌 override → 🔴 ───────────────────────────
    reasons_red: list[str] = []
    y22 = _val(indicators, "YIELD_10Y2Y")
    y3m = _val(indicators, "YIELD_10Y3M")
    vix = _val(indicators, "VIX")
    sahm = _val(indicators, "SAHM")

    if y22 is not None and y22 < _YIELD_INVERT_PCT:
        reasons_red.append(f"殖利率曲線倒掛（10Y-2Y {y22:+.2f}%）— 衰退領先訊號")
    if y3m is not None and y3m < _YIELD_INVERT_PCT:
        reasons_red.append(f"殖利率曲線倒掛（10Y-3M {y3m:+.2f}%）— 衰退領先訊號")
    if sahm is not None and sahm >= SAHM_RECESSION_THRESHOLD:
        reasons_red.append(f"Sahm 規則 {sahm:.2f} ≥ {SAHM_RECESSION_THRESHOLD}（衰退警報中）")
    if vix is not None and vix >= _VIX_PANIC:
        reasons_red.append(f"VIX {vix:.0f} ≥ {_VIX_PANIC:.0f}（市場恐慌 / 高波動）")

    if reasons_red:
        return {
            "light": "🔴",
            "action": "減碼 / 保守 —— 拉高現金、核心轉防守，等企穩再進",
            "reasons": reasons_red,
            "override": True,
        }

    # ── 2. 無 override → 依景氣位階 ─────────────────────────────
    if phase_score_10 is None:
        return {
            "light": "🟡",
            "action": "資料不足 —— 景氣位階缺,先持有觀望",
            "reasons": ["景氣位階(0-10)未取得,無法定位階"],
            "override": False,
        }

    if phase_score_10 >= _BUY_SCORE_10:
        light, action = "🟢", "可加碼 —— 核心持有不動 + 衛星積極佈局，定期收息再投"
    elif phase_score_10 >= _HOLD_SCORE_10:
        light, action = "🟡", "持有 —— 分批進場、避免重押單一題材"
    else:
        light, action = "🔴", "減碼 —— 景氣位階偏弱,拉高現金水位"

    return {
        "light": light,
        "action": action,
        "reasons": [
            f"景氣位階 {phase_score_10:.1f}/10",
            "無硬衰退/恐慌訊號（殖利率曲線、Sahm、VIX 均未觸發）",
        ],
        "override": False,
    }
