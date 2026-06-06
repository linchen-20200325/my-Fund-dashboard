"""test_decision_matrix.py — v19.15 純函式決策矩陣單測

涵蓋：
- 5 verdict tier × 核心/衛星 → 預設動作（10 case）
- σ 深跌 / 過熱 / 配息吃本金 個股訊號覆寫（6 case）
- summarize_actions 聚合（3 case）
- 邊界（空 list / 未知 verdict / 缺欄位 / 型別防呆）（5 case）
"""
from __future__ import annotations

from services.decision_matrix import (
    VERDICT_LEVELS,
    ACTION_HOLD, ACTION_ADD, ACTION_REDUCE, ACTION_EXIT,
    ACTIONS,
    verdict_to_actions,
    summarize_actions,
)


# ════════════════════════════════════════════════
# 常量結構守門
# ════════════════════════════════════════════════
def test_verdict_levels_constant_has_5_tiers():
    assert VERDICT_LEVELS == ("極度樂觀", "樂觀", "中性", "悲觀", "極度悲觀")


def test_actions_constant_has_4_values():
    assert ACTIONS == (ACTION_HOLD, ACTION_ADD, ACTION_REDUCE, ACTION_EXIT)
    assert ACTION_HOLD == "持有"
    assert ACTION_ADD == "加碼"
    assert ACTION_REDUCE == "減倉"
    assert ACTION_EXIT == "全撤"


# ════════════════════════════════════════════════
# 5 verdict tier × 核心/衛星 預設動作
# ════════════════════════════════════════════════
def _mk_fund(code="F1", is_core=False, sigma_rank=None, alert=None):
    return {
        "code": code,
        "name": code + " name",
        "is_core": is_core,
        "invest_twd": 100000,
        "sigma_info": {"sigma_rank": sigma_rank} if sigma_rank is not None else None,
        "dividend_info": {"alert_level": alert} if alert else None,
    }


def test_v19_15_extreme_bull_core_hold_satellite_add():
    funds = [_mk_fund("C1", is_core=True), _mk_fund("S1", is_core=False)]
    out = verdict_to_actions("極度樂觀", 12.0, funds)
    assert out[0]["action"] == ACTION_HOLD
    assert out[1]["action"] == ACTION_ADD
    assert out[1]["target_pct"] == 130


def test_v19_15_bull_both_hold():
    funds = [_mk_fund("C1", is_core=True), _mk_fund("S1", is_core=False)]
    out = verdict_to_actions("樂觀", 7.0, funds)
    assert out[0]["action"] == ACTION_HOLD
    assert out[1]["action"] == ACTION_HOLD


def test_v19_15_neutral_both_hold():
    funds = [_mk_fund("C1", is_core=True), _mk_fund("S1", is_core=False)]
    out = verdict_to_actions("中性", 0.0, funds)
    assert out[0]["action"] == ACTION_HOLD
    assert out[1]["action"] == ACTION_HOLD


def test_v19_15_bear_core_hold_satellite_reduce():
    funds = [_mk_fund("C1", is_core=True), _mk_fund("S1", is_core=False)]
    out = verdict_to_actions("悲觀", -7.0, funds)
    assert out[0]["action"] == ACTION_HOLD
    assert out[1]["action"] == ACTION_REDUCE
    assert out[1]["target_pct"] == 50


def test_v19_15_extreme_bear_core_reduce_satellite_exit():
    funds = [_mk_fund("C1", is_core=True), _mk_fund("S1", is_core=False)]
    out = verdict_to_actions("極度悲觀", -12.0, funds)
    assert out[0]["action"] == ACTION_REDUCE
    assert out[1]["action"] == ACTION_EXIT
    assert out[1]["target_pct"] == 0


# ════════════════════════════════════════════════
# 個股訊號覆寫
# ════════════════════════════════════════════════
def test_v19_15_deep_oversold_in_bull_promotes_to_add():
    """σ ≤ -2 + 多頭 → 即使核心也升級為加碼（跌了就買）"""
    funds = [_mk_fund("C1", is_core=True, sigma_rank=-2.5)]
    out = verdict_to_actions("樂觀", 7.0, funds)
    assert out[0]["action"] == ACTION_ADD
    assert "深跌" in out[0]["reason"]


def test_v19_15_deep_oversold_in_extreme_bear_stays_observation():
    """σ ≤ -2 + 極度悲觀 → 不接刀，衛星仍 EXIT"""
    funds = [_mk_fund("S1", is_core=False, sigma_rank=-3.0)]
    out = verdict_to_actions("極度悲觀", -12.0, funds)
    assert out[0]["action"] == ACTION_EXIT
    assert "觀望勿接刀" in out[0]["reason"]


def test_v19_15_overheated_in_bull_satellite_take_profit():
    """σ > +1 + 樂觀 + 衛星 → 分批停利 (REDUCE)"""
    funds = [_mk_fund("S1", is_core=False, sigma_rank=1.5)]
    out = verdict_to_actions("樂觀", 7.0, funds)
    assert out[0]["action"] == ACTION_REDUCE
    assert "過熱" in out[0]["reason"]


def test_v19_15_dividend_eating_principal_bumps_one_tier_conservative():
    """配息吃本金 → 衛星 HOLD 升級為 REDUCE"""
    funds = [_mk_fund("S1", is_core=False, alert="red")]
    out = verdict_to_actions("中性", 0.0, funds)
    assert out[0]["action"] == ACTION_REDUCE
    assert "吃本金" in out[0]["reason"]


def test_v19_15_dividend_red_blocks_add_in_extreme_bull():
    """配息吃本金 → 即使極度樂觀也不加碼，降回 HOLD"""
    funds = [_mk_fund("S1", is_core=False, alert="red")]
    out = verdict_to_actions("極度樂觀", 12.0, funds)
    assert out[0]["action"] == ACTION_HOLD
    assert "吃本金" in out[0]["reason"]


def test_v19_15_deep_oversold_in_neutral_promotes_hold_to_add():
    funds = [_mk_fund("S1", is_core=False, sigma_rank=-2.5)]
    out = verdict_to_actions("中性", 0.0, funds)
    assert out[0]["action"] == ACTION_ADD


# ════════════════════════════════════════════════
# summarize_actions 聚合
# ════════════════════════════════════════════════
def test_v19_15_summarize_empty():
    s = summarize_actions([])
    assert s["n_total"] == 0
    assert s["top_risk_funds"] == []


def test_v19_15_summarize_mixed_actions():
    funds = [
        _mk_fund("C1", is_core=True),
        _mk_fund("C2", is_core=True),
        _mk_fund("S1", is_core=False),
        _mk_fund("S2", is_core=False),
    ]
    out = verdict_to_actions("極度悲觀", -12.0, funds)
    s = summarize_actions(out)
    assert s["n_total"] == 4
    assert s["n_reduce"] == 2  # 2 cores
    assert s["n_exit"] == 2     # 2 satellites
    assert s["core_hold_pct"] == 0.0  # 核心全 REDUCE 沒 HOLD
    assert s["satellite_avg_target_pct"] == 0.0  # 衛星全 EXIT
    assert s["top_risk_funds"] == ["C1", "C2", "S1", "S2"]  # 順序保持


def test_v19_15_summarize_hold_only():
    funds = [_mk_fund("C1", is_core=True), _mk_fund("S1", is_core=False)]
    out = verdict_to_actions("樂觀", 7.0, funds)
    s = summarize_actions(out)
    assert s["n_hold"] == 2
    assert s["n_reduce"] == 0
    assert s["n_exit"] == 0
    assert s["core_hold_pct"] == 100.0
    assert s["top_risk_funds"] == []


# ════════════════════════════════════════════════
# 邊界 / 容錯
# ════════════════════════════════════════════════
def test_v19_15_empty_funds_returns_empty_list():
    assert verdict_to_actions("樂觀", 7.0, []) == []
    assert verdict_to_actions("樂觀", 7.0, None) == []


def test_v19_15_unknown_verdict_defaults_to_hold():
    funds = [_mk_fund("C1", is_core=True)]
    out = verdict_to_actions("foobar", 0.0, funds)
    assert out[0]["action"] == ACTION_HOLD
    assert "未知 verdict" in out[0]["reason"]


def test_v19_15_missing_is_core_treated_as_satellite():
    funds = [{"code": "X1", "name": "X1"}]  # 無 is_core
    out = verdict_to_actions("極度悲觀", -12.0, funds)
    assert out[0]["action"] == ACTION_EXIT  # 衛星 → EXIT


def test_v19_15_invalid_fund_entries_skipped():
    funds = [_mk_fund("C1", is_core=True), "not a dict", None, _mk_fund("S1", is_core=False)]
    out = verdict_to_actions("樂觀", 7.0, funds)
    assert len(out) == 2
    assert out[0]["code"] == "C1"
    assert out[1]["code"] == "S1"


def test_v19_15_sigma_info_with_error_field_skipped():
    funds = [_mk_fund("C1", is_core=False, sigma_rank=-2.5)]
    funds[0]["sigma_info"] = {"error": "NAV 不足"}
    out = verdict_to_actions("樂觀", 7.0, funds)
    # σ 不參與覆寫，衛星樂觀預設 HOLD
    assert out[0]["action"] == ACTION_HOLD


def test_v19_15_output_preserves_input_order():
    funds = [_mk_fund(f"F{i}", is_core=(i % 2 == 0)) for i in range(5)]
    out = verdict_to_actions("樂觀", 7.0, funds)
    assert [a["code"] for a in out] == ["F0", "F1", "F2", "F3", "F4"]


def test_v19_15_target_pct_matches_action():
    """target_pct 與 action 對應表必須穩定"""
    mapping = {ACTION_HOLD: 100, ACTION_ADD: 130, ACTION_REDUCE: 50, ACTION_EXIT: 0}
    funds = [
        _mk_fund("C1", is_core=True),                                           # HOLD
        _mk_fund("S1", is_core=False),                                          # HOLD (樂觀)
        _mk_fund("S2", is_core=False, sigma_rank=-3.0),                         # ADD (深跌+樂觀)
        _mk_fund("S3", is_core=False, sigma_rank=1.5),                          # REDUCE (過熱)
    ]
    out = verdict_to_actions("樂觀", 7.0, funds)
    for a in out:
        assert a["target_pct"] == mapping[a["action"]], f"{a['code']}: {a['action']}"
