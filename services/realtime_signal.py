"""services/realtime_signal.py — v19.15 即時訊號儀表板 composer

把既有單元串成「即時 verdict → 7 cluster 燈 → 逐檔決策」單一 dict 輸出，給
ui.tab1_macro 一次渲染。**純函式、零 IO、零快取、零 streamlit**。

設計：
- 使用呼叫端已抓好的 indicators dict（從 sidebar `macro_done` 來），**不額外戳
  yfinance/FRED quota**；用戶想刷新就按既有 sidebar「📡 載入總經」入口
- 自動套用 active 權重覆蓋（C-2 閉環）：apply_weight_overrides 內建 None-safe
- composite_verdict 自動讀 active.json.verdict_cutoffs（C-2）
- cluster signals 同樣吃覆蓋後 indicators
- 逐檔決策從 verdict_level 而非 raw score，避免 cutoffs 漂移時行為錯亂
"""
from __future__ import annotations

from typing import Iterable, Optional

from services.decision_matrix import verdict_to_actions, summarize_actions


def compute_realtime_dashboard(
    indicators: Optional[dict],
    funds: Optional[Iterable[dict]] = None,
) -> dict:
    """組裝即時訊號儀表板 dict。

    Args:
        indicators: 已抓好的指標 dict（從 sidebar macro_done 來）；None → 回 empty
        funds: 逐檔 fund dict（同 verdict_to_actions 第三參數）；None → 跳過決策矩陣

    Returns:
        {
            "ready": bool,                     # indicators 是否可用
            "score": float,                    # composite_score（已套 active 權重）
            "verdict_icon": str,               # "🟢" / "🟡" / "🔴"
            "verdict_level": str,              # "極度樂觀" / ... / "極度悲觀"
            "verdict_color": str,              # hex color
            "verdict_action_text": str,        # 整體配置建議白話
            "cluster_signals": list[dict],     # compute_cluster_signals 輸出
            "cluster_consensus": dict,         # summarize_cluster_consensus 輸出
            "fund_actions": list[dict],        # verdict_to_actions 輸出（funds 為空 → []）
            "actions_summary": dict,           # summarize_actions 輸出
        }

    邊界：
        - indicators 為 None / 空 → ready=False，其餘欄位給安全空值
        - 模組依賴 import 失敗 → ready=False，error 欄位記錄
    """
    empty_dashboard = {
        "ready": False,
        "score": 0.0,
        "verdict_icon": "⏳",
        "verdict_level": "資料不足",
        "verdict_color": "#888888",
        "verdict_action_text": "請先按 sidebar「📡 載入總經」抓取指標",
        "cluster_signals": [],
        "cluster_consensus": {"n_green": 0, "n_yellow": 0, "n_red": 0, "total": 0, "verdict": ""},
        "fund_actions": [],
        "actions_summary": summarize_actions([]),
    }

    if not indicators or not isinstance(indicators, dict):
        return empty_dashboard

    try:
        from services.macro_weights_store import apply_weight_overrides
        from ui.helpers.macro_helpers import calculate_composite_score, composite_verdict
        from services.macro_service import compute_cluster_signals, summarize_cluster_consensus
    except ImportError as e:
        empty_dashboard["verdict_action_text"] = f"⚠️ 模組依賴未就緒：{e}"
        return empty_dashboard

    ind_after = apply_weight_overrides(indicators)

    score = float(calculate_composite_score(ind_after) or 0.0)
    icon, level, color, action_text = composite_verdict(score)

    clusters = compute_cluster_signals(ind_after) or []
    consensus = summarize_cluster_consensus(clusters) if clusters else \
        {"n_green": 0, "n_yellow": 0, "n_red": 0, "total": 0, "verdict": ""}

    fund_list = list(funds) if funds else []
    actions = verdict_to_actions(level, score, fund_list)
    actions_summary = summarize_actions(actions)

    return {
        "ready": True,
        "score": round(score, 2),
        "verdict_icon": icon,
        "verdict_level": level,
        "verdict_color": color,
        "verdict_action_text": action_text,
        "cluster_signals": clusters,
        "cluster_consensus": consensus,
        "fund_actions": actions,
        "actions_summary": actions_summary,
    }


__all__ = ["compute_realtime_dashboard"]
