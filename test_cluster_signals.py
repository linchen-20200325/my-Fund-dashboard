"""test_cluster_signals.py — v18.291 7 維獨立合議 cluster signal"""
from __future__ import annotations

import pytest


# ─── compute_cluster_signals ─────────────────────────
def test_all_bullish_indicators_give_green():
    """所有 cluster 內 indicator 都 score = +weight → 全部 🟢。"""
    from services.macro_service import compute_cluster_signals
    ind = {
        "YIELD_10Y2Y": {"score": 2, "weight": 2, "name": "10Y-2Y", "value": 0.8},
        "YIELD_10Y3M": {"score": 2, "weight": 2, "name": "10Y-3M", "value": 0.6},
        "HY_SPREAD":   {"score": 2, "weight": 2, "name": "HY",     "value": 3.0},
        "VIX":         {"score": 1, "weight": 1, "name": "VIX",    "value": 14},
        "PMI":         {"score": 2, "weight": 2, "name": "PMI",    "value": 53},
        "CPI":         {"score": 1, "weight": 1, "name": "CPI",    "value": 2.5},
        "M2":          {"score": 1, "weight": 1, "name": "M2",     "value": 5},
        "DXY":         {"score": 1, "weight": 1, "name": "DXY",    "value": 100},
        "UNEMPLOYMENT": {"score": 0.5, "weight": 0.5, "name": "UE", "value": 3.5},
    }
    out = compute_cluster_signals(ind)
    assert len(out) == 7
    for c in out:
        if c["members"]:  # 有資料才檢
            assert c["signal"].startswith("🟢"), f"{c['name']} not green: {c}"


def test_all_bearish_indicators_give_red():
    """所有 score = -weight → 🔴。"""
    from services.macro_service import compute_cluster_signals
    ind = {
        "YIELD_10Y2Y": {"score": -2, "weight": 2, "name": "10Y-2Y", "value": -0.5},
        "HY_SPREAD":   {"score": -2, "weight": 2, "name": "HY",     "value": 8.0},
        "VIX":         {"score": -1, "weight": 1, "name": "VIX",    "value": 35},
        "PMI":         {"score": -2, "weight": 2, "name": "PMI",    "value": 45},
        "CPI":         {"score": -1, "weight": 1, "name": "CPI",    "value": 5.0},
        "M2":          {"score": -1, "weight": 1, "name": "M2",     "value": -1},
        "DXY":         {"score": -1, "weight": 1, "name": "DXY",    "value": 110},
        "UNEMPLOYMENT": {"score": -0.5, "weight": 0.5, "name": "UE", "value": 6.0},
    }
    out = compute_cluster_signals(ind)
    for c in out:
        if c["members"]:
            assert c["signal"].startswith("🔴"), f"{c['name']} not red: {c}"


def test_zero_score_indicators_give_yellow():
    """所有 score = 0 → 🟡 警戒。"""
    from services.macro_service import compute_cluster_signals
    ind = {
        "PMI": {"score": 0, "weight": 2, "name": "PMI", "value": 50},
        "VIX": {"score": 0, "weight": 1, "name": "VIX", "value": 20},
        "HY_SPREAD": {"score": 0, "weight": 2, "name": "HY", "value": 4},
    }
    out = compute_cluster_signals(ind)
    for c in out:
        if c["members"]:
            assert c["signal"].startswith("🟡"), f"{c['name']} not yellow: {c}"


def test_missing_indicators_zero_members():
    """完全沒提供 indicator → 所有 cluster members 為空、norm = 0。"""
    from services.macro_service import compute_cluster_signals
    out = compute_cluster_signals({})
    assert len(out) == 7
    for c in out:
        assert c["members"] == []
        assert c["score_norm"] == 0.0
        assert c["signal"].startswith("🟡")


def test_partial_cluster_uses_available():
    """cluster 內某些 key 缺資料 → 只用有的算。"""
    from services.macro_service import compute_cluster_signals
    ind = {
        "PMI": {"score": -2, "weight": 2, "name": "PMI", "value": 45},
        # COPPER, ADL 不給 → cluster 只看 PMI
    }
    out = compute_cluster_signals(ind)
    manuf = next(c for c in out if c["name"] == "製造業景氣")
    assert len(manuf["members"]) == 1
    assert manuf["signal"].startswith("🔴")  # PMI 滿 bearish


def test_top_contributor_picks_largest_abs():
    """top_contributor 抓出 abs(score) 最大那一個 indicator。"""
    from services.macro_service import compute_cluster_signals
    ind = {
        "YIELD_10Y2Y": {"score": -2, "weight": 2, "name": "10Y-2Y 倒掛", "value": -0.5},
        "YIELD_10Y3M": {"score": -0.5, "weight": 2, "name": "10Y-3M", "value": 0.1},
        "FED_RATE": {"score": 0, "weight": 0.5, "name": "FED", "value": 5.5},
    }
    out = compute_cluster_signals(ind)
    rate = next(c for c in out if c["name"] == "利率曲線")
    assert "10Y-2Y 倒掛" in rate["top_contributor"]


def test_score_clamped_to_weight():
    """score 超過 weight → 自動 clamp 到 [-w, +w]，不會給超過範圍的 norm。"""
    from services.macro_service import compute_cluster_signals
    ind = {
        "DXY": {"score": 99, "weight": 1, "name": "DXY", "value": 100},  # 超過 w
    }
    out = compute_cluster_signals(ind)
    fx = next(c for c in out if c["name"] == "匯率")
    assert -1 <= fx["score_norm"] <= 1


# ─── summarize_cluster_consensus ─────────────────────
def test_consensus_counts():
    from services.macro_service import summarize_cluster_consensus
    clusters = [
        {"signal": "🟢 安全"}, {"signal": "🟢 安全"}, {"signal": "🟢 安全"},
        {"signal": "🟡 警戒"}, {"signal": "🟡 警戒"},
        {"signal": "🔴 危險"}, {"signal": "🔴 危險"},
    ]
    out = summarize_cluster_consensus(clusters)
    assert out["n_green"] == 3
    assert out["n_yellow"] == 2
    assert out["n_red"] == 2
    assert out["total"] == 7


def test_consensus_verdict_red_alert():
    """≥4 紅燈 → 高度警戒。"""
    from services.macro_service import summarize_cluster_consensus
    clusters = [{"signal": "🔴 危險"}] * 4 + [{"signal": "🟢 安全"}] * 3
    out = summarize_cluster_consensus(clusters)
    assert "高度警戒" in out["verdict"]


def test_consensus_verdict_majority_green():
    """≥5 綠燈 → 環境偏好。"""
    from services.macro_service import summarize_cluster_consensus
    clusters = [{"signal": "🟢 安全"}] * 5 + [{"signal": "🟡 警戒"}] * 2
    out = summarize_cluster_consensus(clusters)
    assert "環境偏好" in out["verdict"]


def test_consensus_verdict_two_red_warn():
    """2-3 紅燈 → 注意風險。"""
    from services.macro_service import summarize_cluster_consensus
    clusters = (
        [{"signal": "🔴 危險"}] * 2 + [{"signal": "🟡 警戒"}] * 3
        + [{"signal": "🟢 安全"}] * 2
    )
    out = summarize_cluster_consensus(clusters)
    assert "注意風險" in out["verdict"]


def test_clusters_define_7():
    """INDEPENDENT_CLUSTERS 必須有正好 7 個 cluster。"""
    from services.macro_service import INDEPENDENT_CLUSTERS
    assert len(INDEPENDENT_CLUSTERS) == 7
    for c in INDEPENDENT_CLUSTERS:
        assert "name" in c and "icon" in c and "keys" in c
        assert len(c["keys"]) >= 1


def test_clusters_no_overlap():
    """7 個 cluster 的 indicator key 應不重複（真獨立）。"""
    from services.macro_service import INDEPENDENT_CLUSTERS
    all_keys = []
    for c in INDEPENDENT_CLUSTERS:
        all_keys.extend(c["keys"])
    assert len(all_keys) == len(set(all_keys)), \
        f"Duplicate keys across clusters: {all_keys}"
