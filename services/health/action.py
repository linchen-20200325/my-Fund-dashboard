"""services/health/action.py — L2 深度強化:品質 × 位階 → 行動建議合成器(v19.463)。

補目標架構圖「Health Score × Z-Score 紅綠燈」那一格(user 2026-08-17 拍板「行動建議合成器」)。
把兩個**既有純函式**的輸出合成成一句可執行的行動建議:

- **品質軸**:`services.health.grade.compute_4d_health` 的 grade(A/B/C/D/F/—)—— 基金好不好。
- **時機/位階軸**:`services.zscore_engine.rebalance_signal` 的 action(加碼/持有/停利 + 紅綠燈)
  —— 現在貴不貴。

設計選擇(user 拍板,§4.1 量綱分離):**不把 Z 平均進 0-100 品質分**(漲多的好基金會被
誤判成不健康 → 產生誤導數字,違 §1),改用 **3×3 合成矩陣** → 一個「該怎麼做」的動作 +
顏色 + 依據。純函式・零 IO・離線可驗(§8.2 L2;顏色走 shared.colors SSOT,§3.3)。

§1 Fail-Loud:
- 品質「資料不足(—/score None)」→ **不給行動建議**(先補歷史淨值再評),最高優先。
- 位階不可算(z=None)或 Core 不擇時(applies=False)→ 誠實退回「依品質」建議,不硬湊時機。
- 吃本金(eat_warn)→ 另出旗標浮到最上層,不被時機蓋掉。
"""
from __future__ import annotations

from typing import Optional

from shared.colors import (
    MATERIAL_ORANGE,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)


def _quality_bucket(grade: Optional[str], score) -> str:
    """健診 grade → 品質桶。'—' / score None → 'na'(資料不足)。"""
    if score is None:
        return "na"
    g = str(grade or "").strip().upper()
    if g in ("A", "B"):
        return "good"
    if g == "C":
        return "mid"
    if g in ("D", "F"):
        return "weak"
    return "na"


def _timing_bucket(z_signal: dict) -> str:
    """Z-Score 訊號 → 時機桶。

    - Core(applies=False)→ 'na'(內建配置,不擇時)。
    - z 不可算(action None)→ 'unknown'。
    - 加碼/逢低 → 'low';持有 → 'mid';停利/減碼 → 'high'。
    """
    if not isinstance(z_signal, dict):
        return "unknown"
    if z_signal.get("applies") is False:
        return "na"
    action = z_signal.get("action")
    if action == "加碼/逢低":
        return "low"
    if action == "持有":
        return "mid"
    if action == "停利/減碼":
        return "high"
    return "unknown"


# 3×3 合成矩陣(品質桶, 時機桶)→ (動作短語, 顏色)。SSOT for 本合成器邏輯。
_MATRIX: dict = {
    ("good", "low"):  ("🟢 加碼好時機", TRAFFIC_GREEN),
    ("good", "mid"):  ("🟡 續抱", TRAFFIC_YELLOW),
    ("good", "high"): ("🟠 好標的但位階高 → 續抱別追、可部分停利", MATERIAL_ORANGE),
    ("mid", "low"):   ("🟡 逢低小加 / 觀望", TRAFFIC_YELLOW),
    ("mid", "mid"):   ("⚪ 持有觀察", TRAFFIC_NEUTRAL),
    ("mid", "high"):  ("🟠 減碼", MATERIAL_ORANGE),
    ("weak", "low"):  ("🟠 別為低基期留弱基金 → 考慮換", MATERIAL_ORANGE),
    ("weak", "mid"):  ("🔴 表現弱 → 考慮換", TRAFFIC_RED),
    ("weak", "high"): ("🔴 弱且位階高 → 優先減碼 / 換", TRAFFIC_RED),
}

# 位階不可算 / Core → 只依品質的退場建議(動作短語, 顏色)。
_QUALITY_ONLY: dict = {
    "good": ("🟢 品質佳", TRAFFIC_GREEN),
    "mid":  ("🟡 品質中等", TRAFFIC_YELLOW),
    "weak": ("🔴 品質弱 → 考慮換", TRAFFIC_RED),
}


def combine_action(health: dict, z_signal: dict) -> dict:
    """品質(health)× 位階(z_signal)→ 行動建議 dict。純函式,離線可驗。

    Args
    ----
    health : compute_4d_health 輸出(用 grade / score / eat_warn)。
    z_signal : rebalance_signal 輸出(用 applies / action / z / light)。

    Returns
    -------
    {
        "action": str,           # 主建議短語(帶 emoji 燈號)
        "color": str,            # hex(shared.colors SSOT)
        "quality": str,          # good / mid / weak / na
        "timing": str,           # low / mid / high / na / unknown
        "grade": str | None,     # 原 grade 透傳
        "z": float | None,       # 原 z 透傳
        "flags": list[str],      # 如 ["🔴 吃本金"]
        "reason": str,           # 一句話依據
    }
    """
    health = health if isinstance(health, dict) else {}
    z_signal = z_signal if isinstance(z_signal, dict) else {}

    grade = health.get("grade")
    score = health.get("score")
    q = _quality_bucket(grade, score)
    t = _timing_bucket(z_signal)
    z = z_signal.get("z")

    flags: list[str] = []
    if health.get("eat_warn"):
        flags.append("🔴 吃本金")

    # ① 品質資料不足 → 不建議(§1,最高優先:別在薄資料上給行動)
    if q == "na":
        return {
            "action": "⚪ 資料不足,先補歷史淨值再評",
            "color": TRAFFIC_NEUTRAL, "quality": q, "timing": t,
            "grade": grade, "z": z, "flags": flags,
            "reason": "健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。",
        }

    # ② 位階不可算 / Core 不擇時 → 只依品質(誠實退場)
    if t in ("na", "unknown"):
        _lbl, _col = _QUALITY_ONLY[q]
        if t == "na":
            _tail = "·內建配置(平衡/貨幣,不做位階擇時)"
        else:
            _tail = "·位階未知(NAV 有效點不足,不硬判時機 §1)"
        return {
            "action": f"{_lbl} {_tail}",
            "color": _col, "quality": q, "timing": t,
            "grade": grade, "z": z, "flags": flags,
            "reason": f"品質桶={q};{z_signal.get('reason') or '無 Z-Score 位階'}",
        }

    # ③ 品質 × 位階 → 合成矩陣
    _lbl, _col = _MATRIX[(q, t)]
    _zstr = f"Z={z:+.2f}" if isinstance(z, (int, float)) else "Z=—"
    _light = z_signal.get("light")
    _ltxt = f"景氣{_light}燈" if _light else "預設門檻"
    return {
        "action": _lbl, "color": _col, "quality": q, "timing": t,
        "grade": grade, "z": z, "flags": flags,
        "reason": f"品質 {grade} × 位階 {t}({_zstr},{_ltxt})→ {_lbl}。",
    }


__all__ = ["combine_action"]
