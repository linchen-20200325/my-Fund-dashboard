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


def test_missing_is_core_is_unset_not_satellite():
    """客戶 2026-10-12 裁示：未設定 ≠ 衛星。極度悲觀下衛星會 EXIT，未設定必須 HOLD。"""
    funds = [{"code": "X1", "name": "X1"}]  # 無 is_core / policy_tier
    out = verdict_to_actions("極度悲觀", -12.0, funds)
    assert out[0]["action"] == ACTION_HOLD
    assert "未設定" in out[0]["reason"]
    assert "衛星" not in out[0]["reason"]
    assert out[0]["tier"] is None
    assert out[0]["is_core"] is False
    assert out[0]["target_pct"] == 100


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


# ════════════════════════════════════════════════
# 三態 core / satellite / unset（客戶 2026-10-12 裁示）
# ════════════════════════════════════════════════
import ast
import pathlib

import pytest

_CORE = {"code": "C", "policy_tier": "core"}
_SAT = {"code": "S", "policy_tier": "satellite"}
_UNSET = {"code": "U"}

_EXPECT_DEFAULT = {
    # level: (core, satellite)；unset 一律 HOLD
    "極度樂觀": (ACTION_HOLD, ACTION_ADD),
    "樂觀": (ACTION_HOLD, ACTION_HOLD),
    "中性": (ACTION_HOLD, ACTION_HOLD),
    "悲觀": (ACTION_HOLD, ACTION_REDUCE),
    "極度悲觀": (ACTION_REDUCE, ACTION_EXIT),
}


@pytest.mark.parametrize("level", VERDICT_LEVELS)
def test_three_state_default_action_per_level(level):
    c, s_ = _EXPECT_DEFAULT[level]
    out = verdict_to_actions(level, 0.0, [_CORE, _SAT, _UNSET])
    assert [o["action"] for o in out] == [c, s_, ACTION_HOLD]
    assert [o["tier"] for o in out] == ["core", "satellite", None]


@pytest.mark.parametrize("unset", [
    {"code": "U"},
    {"code": "U", "is_core": None},
    {"code": "U", "policy_tier": ""},
    {"code": "U", "policy_tier": None, "is_core": None},
    {"code": "U", "is_core": "yes"},
])
def test_unset_variants(unset):
    out = verdict_to_actions("極度悲觀", 0.0, [unset])
    assert out[0]["tier"] is None and out[0]["action"] == ACTION_HOLD


def test_explicit_bool_is_core_still_core_or_satellite():
    out = verdict_to_actions("極度悲觀", 0.0, [{"code": "a", "is_core": True}, {"code": "b", "is_core": False}])
    assert [o["tier"] for o in out] == ["core", "satellite"]
    assert [o["action"] for o in out] == [ACTION_REDUCE, ACTION_EXIT]


def test_policy_tier_beats_is_core():
    out = verdict_to_actions("極度悲觀", 0.0, [{"code": "a", "policy_tier": "satellite", "is_core": True}])
    assert out[0]["tier"] == "satellite" and out[0]["action"] == ACTION_EXIT


def test_unset_skips_satellite_only_branches():
    # 樂觀 + σ>1：衛星 → 停利 REDUCE；未設定不吃
    sig = {"sigma_rank": 1.5}
    out = verdict_to_actions("樂觀", 0.0, [{**_SAT, "sigma_info": sig}, {**_UNSET, "sigma_info": sig}])
    assert out[0]["action"] == ACTION_REDUCE and out[1]["action"] == ACTION_HOLD
    # div red：衛星 HOLD→REDUCE；未設定仍 HOLD
    div = {"alert_level": "red"}
    out = verdict_to_actions("中性", 0.0, [{**_SAT, "dividend_info": div}, {**_UNSET, "dividend_info": div}])
    assert out[0]["action"] == ACTION_REDUCE and out[1]["action"] == ACTION_HOLD
    # 悲觀 + div red：衛星 REDUCE→EXIT；未設定 HOLD 不升
    out = verdict_to_actions("悲觀", 0.0, [{**_SAT, "dividend_info": div}, {**_UNSET, "dividend_info": div}])
    assert out[0]["action"] == ACTION_EXIT and out[1]["action"] == ACTION_HOLD


def test_summarize_excludes_unset_from_satellite():
    acts = verdict_to_actions("極度悲觀", 0.0, [_CORE, _SAT, _UNSET])
    sm = summarize_actions(acts)
    assert sm["n_unset"] == 1
    assert sm["satellite_avg_target_pct"] == 0.0  # 只有 S（EXIT=0），U（100）不併入
    # 舊輸出沒有 tier 鍵：退回 is_core（True→core，其餘→satellite）
    legacy = [
        {"code": "a", "action": ACTION_HOLD, "target_pct": 100, "is_core": True},
        {"code": "b", "action": ACTION_EXIT, "target_pct": 0, "is_core": False},
    ]
    sm2 = summarize_actions(legacy)
    assert sm2["core_hold_pct"] == 100.0 and sm2["satellite_avg_target_pct"] == 0.0 and sm2["n_unset"] == 0


def test_decision_matrix_source_has_no_bool_squash():
    path = pathlib.Path(__file__).resolve().parent.parent / "services" / "decision_matrix.py"
    src = path.read_text(encoding="utf-8")
    assert 'bool(f.get("is_core"' not in src
    assert '.get("is_core", False)' not in src
    # AST 層：不得有 bool(<含 is_core 的呼叫>)
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "bool":
            assert "is_core" not in ast.unparse(node)
