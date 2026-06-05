"""test_dual_signal_routing.py — v19.13 雙軌 AutoSearch apply routing 單測.

只測純函式 routing helpers，不涉及 Streamlit session_state。
v19.13.1：新增 mode_forward_days 測試（防 lead_days wiring 漏接退化 bug）。
"""
from __future__ import annotations

import pytest

from ui.tab_crisis_backtest import (
    MULTIFACTOR_MODE_LEAD_DAYS,
    MULTIFACTOR_MODES,
    mode_forward_days,
    multifactor_keys_state_key,
    multifactor_result_state_key,
    route_apply_key_by_lead,
)


# ─── route_apply_key_by_lead ──────────────────────────────────────
def test_route_short_lead_goes_to_pullback():
    # 短期 mode 預設 max_lead = 30 → pullback
    assert route_apply_key_by_lead(30) == "multifactor_keys_pullback"
    assert route_apply_key_by_lead(5) == "multifactor_keys_pullback"
    assert route_apply_key_by_lead(15) == "multifactor_keys_pullback"


def test_route_long_lead_goes_to_macro():
    # 長期 mode 預設 max_lead = 90 → macro
    assert route_apply_key_by_lead(90) == "multifactor_keys_macro"
    assert route_apply_key_by_lead(31) == "multifactor_keys_macro"
    assert route_apply_key_by_lead(365) == "multifactor_keys_macro"


def test_route_accepts_float_lead():
    # slider 偶爾回 float
    assert route_apply_key_by_lead(30.0) == "multifactor_keys_pullback"
    assert route_apply_key_by_lead(30.5) == "multifactor_keys_macro"


def test_route_boundary_30_is_pullback():
    # 邊界值 30 含在短期區間（≤ 30 → pullback）
    assert route_apply_key_by_lead(30) == "multifactor_keys_pullback"


# ─── multifactor_keys_state_key / multifactor_result_state_key ────
def test_state_key_helpers_match_routing():
    # routing 結果應與 multifactor_keys_state_key 一致
    for lead, expected_mode in [(5, "pullback"), (90, "macro")]:
        assert route_apply_key_by_lead(lead) == multifactor_keys_state_key(expected_mode)


def test_state_key_helpers_reject_unknown_mode():
    with pytest.raises(ValueError, match="unknown mode"):
        multifactor_keys_state_key("daily")
    with pytest.raises(ValueError, match="unknown mode"):
        multifactor_result_state_key("intraday")


def test_state_key_helpers_distinct_per_mode():
    # macro / pullback 兩 mode 的 key 必須不同（不互覆蓋的根本保證）
    assert multifactor_keys_state_key("macro") != multifactor_keys_state_key("pullback")
    assert multifactor_result_state_key("macro") != multifactor_result_state_key("pullback")


def test_modes_constant_only_has_macro_and_pullback():
    # 防止未來 typo 加進不支援的 mode
    assert set(MULTIFACTOR_MODES) == {"macro", "pullback"}


# ─── v19.13.1: mode_forward_days ──────────────────────────────────
def test_mode_forward_days_pullback_is_short():
    # 短期 mode 評估窗口必須是 (5, 30)
    assert mode_forward_days("pullback") == (5, 30)


def test_mode_forward_days_macro_is_long():
    # 長期 mode 評估窗口必須是 (30, 90)
    assert mode_forward_days("macro") == (30, 90)


def test_mode_forward_days_rejects_unknown():
    with pytest.raises(ValueError, match="unknown mode"):
        mode_forward_days("daily")
    with pytest.raises(ValueError, match="unknown mode"):
        mode_forward_days("intraday")


def test_mode_forward_days_returns_distinct_per_mode():
    # 兩 mode 的窗口必須不同（不然就退化回 v19.13 bug）
    assert mode_forward_days("macro") != mode_forward_days("pullback")


def test_mode_forward_days_max_never_exceeds_default_365():
    # 防止哪天有人手抖把 max 設超過 default 365 → 反而比 default 還寬
    for mode in MULTIFACTOR_MODES:
        _, max_fwd = mode_forward_days(mode)
        assert max_fwd <= 365


def test_mode_forward_days_min_lt_max():
    # min < max 永遠成立（不然 evaluate_f1 窗口會 degenerate）
    for mode in MULTIFACTOR_MODES:
        min_fwd, max_fwd = mode_forward_days(mode)
        assert min_fwd < max_fwd


def test_mode_lead_days_dict_matches_modes():
    # MULTIFACTOR_MODE_LEAD_DAYS 必須涵蓋所有 MULTIFACTOR_MODES
    assert set(MULTIFACTOR_MODE_LEAD_DAYS.keys()) == set(MULTIFACTOR_MODES)
