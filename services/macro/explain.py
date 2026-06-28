"""services/macro_explain.py — v19.17 新手友善總經解釋層

把面板 indicators dict（macro_service.fetch_all_indicators 抓的 23 keys）
+ active.json weight override + MACRO_EDU 教學語料
聚合成「新手友善面板」需要的單一 payload dict。

設計原則：
- 純函式（zero IO）；indicators 由呼叫端從 session_state 注入
- 不重抓資料：完全沿用 sidebar 已抓的 indicators dict + active.json
- key 系統採「面板 indicators key」（YIELD_10Y2Y / UNEMPLOYMENT / M2 …），
  不採 FACTOR_POOL 學術名（T10Y2Y / UNRATE / M2_YOY）— 與 MACRO_EDU 對齊
- 「回測核可」概念由 active.json.indicators 的 weight 體現
  （v19.0 C-1 → C-2 路徑已經把 walk-forward OOS 結果寫進 active.json）

公開 API：
  - build_beginner_payload(indicators, macro_edu, top_n=8) -> dict
  - INDICATOR_FREQ_MAP / FREQ_LABEL — 對外常量
"""
from __future__ import annotations

import math
from typing import Any

from shared.colors import MATERIAL_GREEN, MATERIAL_RED
from shared.signal_thresholds import (  # v19.74 W2 SSOT
    SIGMA_VERY_HIGH_CUTOFF,
    SIGMA_HIGH_CUTOFF,
    SIGMA_LOW_CUTOFF,
)

# ════════════════════════════════════════════════
# 常量：indicators key → 頻率（高頻 daily / 中頻 weekly / 低頻 monthly）
# ════════════════════════════════════════════════
INDICATOR_FREQ_MAP: dict[str, str] = {
    # 日頻（市場即時觀察）
    "VIX": "daily", "HY_SPREAD": "daily", "DXY": "daily",
    "YIELD_10Y2Y": "daily", "YIELD_10Y3M": "daily",
    "INFL_EXP_5Y": "daily", "COPPER": "daily", "ADL": "daily",
    # 週頻
    "M2_WEEKLY": "weekly", "JOBLESS": "weekly",
    "CONT_CLAIMS": "weekly", "FED_BS": "weekly",
    # 月頻
    "PMI": "monthly", "CPI": "monthly", "PPI": "monthly",
    "FED_RATE": "monthly", "UNEMPLOYMENT": "monthly",
    "M2": "monthly", "SAHM": "monthly", "SLOOS": "monthly",
    "LEI": "monthly", "CONSUMER_CONF": "monthly",
    "PERMIT_HOUSING": "monthly", "NEW_HOME": "monthly",
    "NFP": "monthly",  # v19.17 新增非農新增就業
}

FREQ_LABEL: dict[str, str] = {
    "daily":   "🔥 高頻 (日)",
    "weekly":  "📊 中頻 (週)",
    "monthly": "🐌 低頻 (月)",
    "unknown": "—",
}

# Verdict cutoffs fallback（C-2 之前的硬編碼，與 macro_helpers.composite_verdict 對齊）
_DEFAULT_CUTOFFS = (10.0, 5.0, -5.0, -10.0)


# ════════════════════════════════════════════════
# 純函式：自動判讀單一指標
# ════════════════════════════════════════════════
def _interpret_indicator(score: float) -> str:
    """根據標準化 score 給一句白話判讀。

    score 約定：正 = 偏空頭/風險升高、負 = 偏多頭/寬鬆環境（fund 端慣例）
    """
    if score >= SIGMA_VERY_HIGH_CUTOFF:
        return f"🔴 訊號**強烈偏空**（標準化超過 +{SIGMA_VERY_HIGH_CUTOFF}σ）"
    if score >= SIGMA_HIGH_CUTOFF:
        return f"🟠 訊號**偏空**（標準化 +{SIGMA_HIGH_CUTOFF} ~ +{SIGMA_VERY_HIGH_CUTOFF}σ）"
    if score >= SIGMA_LOW_CUTOFF:
        return f"🟡 訊號**輕度偏空**（標準化 +{SIGMA_LOW_CUTOFF} ~ +{SIGMA_HIGH_CUTOFF}σ）"
    if score >= -SIGMA_LOW_CUTOFF:
        return f"⚪ 訊號**接近中性**（標準化 ±{SIGMA_LOW_CUTOFF}σ 內）"
    if score >= -SIGMA_HIGH_CUTOFF:
        return f"🟢 訊號**輕度偏多**（標準化 -{SIGMA_LOW_CUTOFF} ~ -{SIGMA_HIGH_CUTOFF}σ）"
    if score >= -SIGMA_VERY_HIGH_CUTOFF:
        return f"🟢 訊號**偏多**（標準化 -{SIGMA_HIGH_CUTOFF} ~ -{SIGMA_VERY_HIGH_CUTOFF}σ）"
    return f"🟢 訊號**強烈偏多**（標準化超過 -{SIGMA_VERY_HIGH_CUTOFF}σ）"


# v19.222 P1-1:_safe_float 收口至 shared/converters.py SSOT
from shared.converters import safe_float as _safe_float  # noqa: E402



# ════════════════════════════════════════════════
# 主 API：build_beginner_payload
# ════════════════════════════════════════════════
def build_beginner_payload(
    indicators: dict | None,
    macro_edu: dict | None,
    top_n: int = 8,
) -> dict:
    """組裝新手面板所需的單一 payload dict。

    指標來源：indicators dict（面板 fetch_all_indicators 抓的 23 keys），
    weight 已由 calculate_composite_score 內部 apply_weight_overrides 處理。
    本函式只負責「呈現 + 教學」聚合，不重算 score。

    指標排序：按 |contribution| = |score × weight| 降序，取前 top_n 個。
    這實現「動態：讀回測核可組合」需求 —
    active.json 高權重指標自然排前面。

    Returns:
        {
          "ready":            bool — indicators 是否就緒
          "score":            float — 綜合分數 Σ(score × weight)
          "verdict_icon":     str — 🟢/🟡/🔴
          "verdict_level":    str — 極度樂觀/樂觀/中性/悲觀/極度悲觀
          "verdict_color":    str — hex 顏色
          "verdict_action_text": str — 行動建議短句
          "verdict_oneline":  str — 一句話結論
          "why_bullets":      list[str] — 3 條為什麼 bullet（top 3 driver 教學）
          "active_factors":   list[dict] — top_n 個指標卡資料
              每 row = {
                key, name, value, unit, type, score, weight, contribution,
                freq, freq_label,
                edu_meaning, edu_how_to_read, edu_pair_with,
                edu_historical_anchor, edu_upstream, edu_downstream,
                interpretation,
              }
          "n_total":          int — indicators 有效總數
          "n_displayed":      int — 實際取到的數
        }
    """
    macro_edu = macro_edu or {}

    if not isinstance(indicators, dict) or not indicators:
        return _empty_payload()

    # ── 1. 過濾 + 計算每個 indicator 的 contribution ──
    rows: list[dict] = []
    for key, v in indicators.items():
        if not isinstance(v, dict):
            continue
        score = _safe_float(v.get("score"), 0.0)
        weight = _safe_float(v.get("weight"), 1.0)
        if math.isclose(score, 0.0, abs_tol=1e-9) and "score" not in v:  # v19.74 W1-E (§4.3): float ==
            continue  # 無 score 鍵（不是 0 而是真缺）→ 跳過
        contribution = score * weight
        edu = macro_edu.get(key) or {}
        freq = INDICATOR_FREQ_MAP.get(key, "unknown")
        rows.append({
            "key":          key,
            "name":         str(v.get("name") or key),
            "value":        v.get("value"),
            "unit":         str(v.get("unit") or ""),
            "type":         str(v.get("type") or ""),
            "score":        score,
            "weight":       weight,
            "contribution": contribution,
            "freq":         freq,
            "freq_label":   FREQ_LABEL.get(freq, FREQ_LABEL["unknown"]),
            "edu_meaning":          str(edu.get("meaning") or "（暫無教學內容）"),
            "edu_how_to_read":      list(edu.get("how_to_read") or []),
            "edu_pair_with":        str(edu.get("pair_with") or ""),
            "edu_historical_anchor": str(edu.get("historical_anchor") or ""),
            "edu_upstream":         str(edu.get("upstream") or ""),
            "edu_downstream":       str(edu.get("downstream") or ""),
            "interpretation":       _interpret_indicator(score),
        })

    if not rows:
        return _empty_payload()

    # ── 2. 排序 + 取 top_n ──
    rows.sort(key=lambda r: abs(r["contribution"]), reverse=True)
    if top_n is None or top_n <= 0:
        active_factors = rows
    else:
        active_factors = rows[:top_n]

    # ── 3. 綜合分數 + verdict ──
    total_score = round(sum(r["contribution"] for r in rows), 2)
    icon, level, color, action_text = _verdict_for(total_score)

    # ── 4. 一句話結論 ──
    verdict_oneline = (
        f"目前綜合分數 **{total_score:+.2f}** → **{level}** {icon}  ｜  {action_text}"
    )

    # ── 5. why_bullets（top 3 driver 教學） ──
    why_bullets = []
    for i, r in enumerate(active_factors[:3]):
        medal = ["🥇", "🥈", "🥉"][i]
        edu_short = r["edu_meaning"][:80] + ("…" if len(r["edu_meaning"]) > 80 else "")
        why_bullets.append(
            f"{medal} **{r['name']}**（{r['freq_label']}）"
            f"貢獻 **{r['contribution']:+.2f}**"
            f"（score {r['score']:+.2f} × 權重 {r['weight']:.2f}）"
            f" — {edu_short}"
        )
    if not why_bullets:
        why_bullets = ["（指標資料不足，無法產生 driver 分析）"]

    return {
        "ready":               True,
        "score":               total_score,
        "verdict_icon":        icon,
        "verdict_level":       level,
        "verdict_color":       color,
        "verdict_action_text": action_text,
        "verdict_oneline":     verdict_oneline,
        "why_bullets":         why_bullets,
        "active_factors":      active_factors,
        "n_total":             len(rows),
        "n_displayed":         len(active_factors),
    }


# ════════════════════════════════════════════════
# 私函式
# ════════════════════════════════════════════════
def _empty_payload() -> dict:
    return {
        "ready":               False,
        "score":               0.0,
        "verdict_icon":        "⏳",
        "verdict_level":       "未載入",
        "verdict_color":       "#888888",
        "verdict_action_text": "請先按 sidebar「📡 載入總經資料」",
        "verdict_oneline":     "⏳ 尚未載入總經資料",
        "why_bullets":         [],
        "active_factors":      [],
        "n_total":             0,
        "n_displayed":         0,
    }


def _verdict_for(total_score: float) -> tuple[str, str, str, str]:
    """同 macro_helpers.composite_verdict 但避免循環 import — 本檔不依賴 UI 層。"""
    try:
        from services.macro_weights_store import get_verdict_cutoffs
        c1, c2, c3, c4 = get_verdict_cutoffs()
    except Exception:
        c1, c2, c3, c4 = _DEFAULT_CUTOFFS
    if total_score > c1:
        return ("🟢", "極度樂觀", MATERIAL_GREEN,
                "多頭市場強勁：可滿倉持有，衛星部位積極佈局成長題材")
    if total_score > c2:
        return ("🟢", "樂觀", "#69f0ae",
                "景氣穩定擴張：核心持有不動，定期定額正常進行")
    if total_score >= c3:
        return ("🟡", "中性", "#ffd54f",
                "市場震盪整理：分批進場，避免重押單一題材")
    if total_score >= c4:
        return ("🔴", "悲觀", "#ff8a80",
                "風險正在集結：拉高現金水位至 15-25%，衛星部位設停利")
    return ("🔴", "極度悲觀", MATERIAL_RED,
            "避險情緒高漲：現金 30%+，核心轉防守型（投資等級債/全球均衡）")


__all__ = [
    "INDICATOR_FREQ_MAP",
    "FREQ_LABEL",
    "build_beginner_payload",
]
