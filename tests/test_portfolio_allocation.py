"""tests/test_portfolio_allocation.py — 核心/衛星配置 SSOT（金額加權）單元測試。

守的是 2026-08 稽核「必修 4」：同一頁 4 處各算各的核心/衛星，3 種定義、
2 種目標值。收斂後全部走 ui/helpers/portfolio/allocation.py。

本檔全部測試在修正前為 **ImportError 紅**（allocation.py 當時不存在）。
"""
from __future__ import annotations

import pytest

from ui.helpers.portfolio.allocation import (
    CORE_TARGET_SESSION_KEY,
    format_core_satellite_caption,
    get_core_target_pct,
    resolve_core_flag,
    summarize_core_satellite,
)


# ── resolve_core_flag：policy_tier 優先 ────────────────────────────────
def test_resolve_core_flag_policy_tier_beats_is_core():
    """Sheet 明示 policy_tier 時，一律蓋過名稱關鍵字推得的 is_core。"""
    assert resolve_core_flag({"policy_tier": "core", "is_core": False}) is True
    assert resolve_core_flag({"policy_tier": "satellite", "is_core": True}) is False


def test_resolve_core_flag_case_and_whitespace_insensitive():
    assert resolve_core_flag({"policy_tier": "  Core "}) is True
    assert resolve_core_flag({"policy_tier": "SATELLITE"}) is False


def test_resolve_core_flag_falls_back_to_is_core():
    assert resolve_core_flag({"policy_tier": "", "is_core": True}) is True
    assert resolve_core_flag({"is_core": True}) is True
    assert resolve_core_flag({}) is False
    assert resolve_core_flag(None) is False


def test_resolve_core_flag_unknown_tier_falls_back():
    """policy_tier 填了看不懂的值 → 不猜，退回 is_core。"""
    assert resolve_core_flag({"policy_tier": "中性", "is_core": True}) is True
    assert resolve_core_flag({"policy_tier": "中性", "is_core": False}) is False


# ── summarize_core_satellite：金額加權 ─────────────────────────────────
def test_summarize_is_amount_weighted_not_fund_count():
    """3 檔核心 / 5 檔總計 = 檔數 60%，但核心持有 90% 的錢 → 金額比例 90%。

    這正是稽核指出的「同頁同時出現核心 60% 與核心 90%」的成因。
    """
    funds = [
        {"code": "C1", "is_core": True,  "invest_twd": 300_000},
        {"code": "C2", "is_core": True,  "invest_twd": 300_000},
        {"code": "C3", "is_core": True,  "invest_twd": 300_000},
        {"code": "S1", "is_core": False, "invest_twd": 50_000},
        {"code": "S2", "is_core": False, "invest_twd": 50_000},
    ]
    out = summarize_core_satellite(funds)
    assert out["n_core"] == 3
    assert out["n_sat"] == 2
    assert out["total_twd"] == pytest.approx(1_000_000.0)
    assert out["core_pct"] == pytest.approx(90.0)
    assert out["sat_pct"] == pytest.approx(10.0)
    assert out["is_amount_weighted"] is True


def test_summarize_uses_policy_tier_over_is_core():
    """金額歸屬也要吃 policy_tier 優先（否則保單分組與總覽仍會不一致）。"""
    funds = [
        {"code": "A", "is_core": False, "policy_tier": "core", "invest_twd": 700_000},
        {"code": "B", "is_core": True,  "policy_tier": "satellite", "invest_twd": 300_000},
    ]
    out = summarize_core_satellite(funds)
    assert out["core_twd"] == pytest.approx(700_000.0)
    assert out["sat_twd"] == pytest.approx(300_000.0)
    assert out["n_tier_from_sheet"] == 2


def test_summarize_target_and_diff():
    funds = [
        {"code": "C", "is_core": True,  "invest_twd": 600_000},
        {"code": "S", "is_core": False, "invest_twd": 400_000},
    ]
    out = summarize_core_satellite(funds, target_pct=75)
    assert out["core_pct"] == pytest.approx(60.0)
    assert out["target_pct"] == 75
    assert out["diff_pct"] == pytest.approx(-15.0)


def test_summarize_no_target_means_no_diff():
    funds = [{"code": "C", "is_core": True, "invest_twd": 1}]
    out = summarize_core_satellite(funds)
    assert out["target_pct"] is None
    assert out["diff_pct"] is None


# ── 邊界：空集 / 全 0 本金 / 負值 / 非數值 ─────────────────────────────
def test_summarize_empty_and_none():
    for _in in ([], None):
        out = summarize_core_satellite(_in)
        assert out["n_funds"] == 0
        assert out["core_pct"] is None
        assert out["is_amount_weighted"] is False


def test_summarize_all_zero_amount_is_honest_none_not_zero_pct():
    """全部沒填本金 → core_pct 回 None（§1：不捏造 0%，0% 會被讀成「沒有核心」）。"""
    funds = [
        {"code": "A", "is_core": True,  "invest_twd": 0},
        {"code": "B", "is_core": False, "invest_twd": None},
    ]
    out = summarize_core_satellite(funds, target_pct=75)
    assert out["core_pct"] is None
    assert out["diff_pct"] is None
    assert out["is_amount_weighted"] is False
    assert out["n_missing_amount"] == 2
    assert out["n_core"] == 1 and out["n_sat"] == 1


def test_summarize_partial_missing_amount_is_reported():
    funds = [
        {"code": "A", "is_core": True,  "invest_twd": 100},
        {"code": "B", "is_core": False, "invest_twd": 0},
    ]
    out = summarize_core_satellite(funds)
    assert out["n_missing_amount"] == 1
    assert out["core_pct"] == pytest.approx(100.0)


def test_summarize_negative_and_garbage_amount_do_not_blow_up():
    funds = [
        {"code": "A", "is_core": True,  "invest_twd": -50},     # 負值 → 視為 0
        {"code": "B", "is_core": True,  "invest_twd": "abc"},   # 非數值 → 視為 0
        {"code": "C", "is_core": False, "invest_twd": "1000"},  # 字串數字仍可解
    ]
    out = summarize_core_satellite(funds)
    assert out["core_twd"] == pytest.approx(0.0)
    assert out["sat_twd"] == pytest.approx(1000.0)
    assert out["core_pct"] == pytest.approx(0.0)


def test_summarize_single_fund():
    out = summarize_core_satellite([{"code": "X", "is_core": True, "invest_twd": 1}])
    assert out["core_pct"] == pytest.approx(100.0)
    assert out["sat_pct"] == pytest.approx(0.0)


# ── 目標值取法：不得寫死 ──────────────────────────────────────────────
def test_get_core_target_pct_uses_session_value():
    assert get_core_target_pct({CORE_TARGET_SESSION_KEY: 62}) == pytest.approx(62.0)


def test_get_core_target_pct_falls_back_to_session_default_not_literal():
    """session 沒設時退 INITIAL_SESSION_STATE 的預設，而非在呼叫端寫死數字。"""
    from ui.helpers.session import INITIAL_SESSION_STATE
    _expected = float(INITIAL_SESSION_STATE[CORE_TARGET_SESSION_KEY])
    assert get_core_target_pct({}) == pytest.approx(_expected)


def test_get_core_target_pct_garbage_value_falls_back():
    from ui.helpers.session import INITIAL_SESSION_STATE
    _expected = float(INITIAL_SESSION_STATE[CORE_TARGET_SESSION_KEY])
    assert get_core_target_pct({CORE_TARGET_SESSION_KEY: "n/a"}) == pytest.approx(_expected)


# ── 說明字串（原則 4「多做說明」）─────────────────────────────────────
def test_caption_states_amount_denominator_and_tier_source():
    funds = [
        {"code": "A", "is_core": True,  "policy_tier": "core", "invest_twd": 100},
        {"code": "B", "is_core": False, "invest_twd": 100},
    ]
    cap = format_core_satellite_caption(summarize_core_satellite(funds))
    assert "金額" in cap
    assert "policy_tier" in cap


def test_caption_warns_when_no_amount_filled():
    funds = [{"code": "A", "is_core": True, "invest_twd": 0}]
    cap = format_core_satellite_caption(summarize_core_satellite(funds))
    assert "無法算金額比例" in cap
