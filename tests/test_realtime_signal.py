"""test_realtime_signal.py — v19.15 即時訊號儀表板 composer 單測

涵蓋：
- empty / None indicators → ready=False 安全 fallback
- 有 indicators 但 funds 空 → ready=True, fund_actions=[]
- 完整 e2e（mock 各層） → 串接成功
- output dict 必有欄位 schema 守門
"""
from __future__ import annotations

from unittest.mock import patch

from services.realtime_signal import compute_realtime_dashboard


# ════════════════════════════════════════════════
# Empty / 邊界
# ════════════════════════════════════════════════
def test_v19_15_dashboard_none_indicators_returns_not_ready():
    d = compute_realtime_dashboard(None)
    assert d["ready"] is False
    assert d["fund_actions"] == []
    assert d["score"] == 0.0
    assert "請先按 sidebar" in d["verdict_action_text"]


def test_v19_15_dashboard_empty_dict_indicators_returns_not_ready():
    d = compute_realtime_dashboard({})
    assert d["ready"] is False


def test_v19_15_dashboard_invalid_type_indicators_returns_not_ready():
    d = compute_realtime_dashboard("not a dict")  # type: ignore[arg-type]
    assert d["ready"] is False


# ════════════════════════════════════════════════
# 完整 schema 守門
# ════════════════════════════════════════════════
_REQUIRED_KEYS = {
    "ready", "score", "verdict_icon", "verdict_level", "verdict_color",
    "verdict_action_text", "cluster_signals", "cluster_consensus",
    "fund_actions", "actions_summary",
}


def test_v19_15_dashboard_empty_path_has_all_required_keys():
    d = compute_realtime_dashboard(None)
    assert _REQUIRED_KEYS.issubset(set(d.keys()))


# ════════════════════════════════════════════════
# 完整 e2e（mock 各層）
# ════════════════════════════════════════════════
@patch("services.macro_weights_store.apply_weight_overrides")
@patch("services.macro_composite_score.calculate_composite_score")
@patch("services.macro_composite_score.composite_verdict")
@patch("services.macro.compute_cluster_signals")
@patch("services.macro.summarize_cluster_consensus")
def test_v19_15_dashboard_full_path_with_funds(
    mock_consensus, mock_clusters, mock_verdict, mock_score, mock_apply
):
    mock_apply.side_effect = lambda x: x
    mock_score.return_value = 8.5
    mock_verdict.return_value = ("🟢", "樂觀", "#69f0ae", "持續穩健")
    mock_clusters.return_value = [
        {"name": "流動性", "signal": "🟢 安全", "score_norm": 0.5},
        {"name": "金融壓力", "signal": "🟢 安全", "score_norm": 0.4},
    ]
    mock_consensus.return_value = {
        "n_green": 2, "n_yellow": 0, "n_red": 0, "total": 2,
        "verdict": "🟢 多數綠燈"
    }

    indicators = {"VIX": {"score": 1.0, "weight": 1.0}}
    funds = [
        {"code": "C1", "is_core": True},
        {"code": "S1", "is_core": False},
    ]

    d = compute_realtime_dashboard(indicators, funds)
    assert d["ready"] is True
    assert d["score"] == 8.5
    assert d["verdict_level"] == "樂觀"
    assert d["verdict_icon"] == "🟢"
    assert len(d["cluster_signals"]) == 2
    assert d["cluster_consensus"]["n_green"] == 2
    assert len(d["fund_actions"]) == 2
    assert d["actions_summary"]["n_total"] == 2
    # 樂觀 → 核心+衛星都 HOLD
    assert d["actions_summary"]["n_hold"] == 2


@patch("services.macro_weights_store.apply_weight_overrides")
@patch("services.macro_composite_score.calculate_composite_score")
@patch("services.macro_composite_score.composite_verdict")
@patch("services.macro.compute_cluster_signals")
@patch("services.macro.summarize_cluster_consensus")
def test_v19_15_dashboard_extreme_bear_triggers_satellite_exit(
    mock_consensus, mock_clusters, mock_verdict, mock_score, mock_apply
):
    mock_apply.side_effect = lambda x: x
    mock_score.return_value = -12.0
    mock_verdict.return_value = ("🔴", "極度悲觀", "#f44336", "現金 30%+")
    mock_clusters.return_value = []
    mock_consensus.return_value = {
        "n_green": 0, "n_yellow": 0, "n_red": 5, "total": 5,
        "verdict": "🔴 多數紅燈"
    }

    indicators = {"VIX": {"score": -2.0, "weight": 1.0}}
    funds = [
        {"code": "C1", "is_core": True},
        {"code": "S1", "is_core": False},
        {"code": "S2", "is_core": False},
    ]
    d = compute_realtime_dashboard(indicators, funds)
    assert d["actions_summary"]["n_reduce"] == 1  # core
    assert d["actions_summary"]["n_exit"] == 2     # 2 satellites
    assert "S1" in d["actions_summary"]["top_risk_funds"]
    assert "S2" in d["actions_summary"]["top_risk_funds"]


@patch("services.macro_weights_store.apply_weight_overrides")
@patch("services.macro_composite_score.calculate_composite_score")
@patch("services.macro_composite_score.composite_verdict")
@patch("services.macro.compute_cluster_signals")
@patch("services.macro.summarize_cluster_consensus")
def test_v19_15_dashboard_no_funds_returns_ready_with_empty_actions(
    mock_consensus, mock_clusters, mock_verdict, mock_score, mock_apply
):
    mock_apply.side_effect = lambda x: x
    mock_score.return_value = 0.0
    mock_verdict.return_value = ("🟡", "中性", "#ffd54f", "分批進場")
    mock_clusters.return_value = []
    mock_consensus.return_value = {
        "n_green": 0, "n_yellow": 0, "n_red": 0, "total": 0, "verdict": ""
    }

    d = compute_realtime_dashboard({"VIX": {"score": 0, "weight": 1.0}}, funds=None)
    assert d["ready"] is True
    assert d["fund_actions"] == []
    assert d["actions_summary"]["n_total"] == 0
