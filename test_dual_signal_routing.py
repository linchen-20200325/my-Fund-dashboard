"""test_dual_signal_routing.py — v19.13 雙軌 AutoSearch apply routing 單測.

只測純函式 routing helpers，不涉及 Streamlit session_state。
v19.13.1：新增 mode_forward_days 測試（防 lead_days wiring 漏接退化 bug）。
v19.13.5：新增 _autosearch_winners_to_candidates 測試（AI 高原 vs peak adapter）。
v19.13.7：新增 dual-mode cache key + _mode_from_max_lead 測試（防 single cache
覆蓋 bug —「只看得到一種 mode」根因）。
v19.13.8：新增 _pick_latest_job_per_mode 測試（防 reboot / refresh 後 winners +
AI + Apply 按鈕集體消失 — session_state cache 失效時的 disk fallback）。
v19.13.9：新增 pending_factor_apply_key 測試（防 Apply Top 1 → 直接寫 widget
key 撞 StreamlitAPIException 整頁炸 — Phase 3 / AutoSearch 同 run render order）。
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from ui.tab_crisis_backtest import (
    MULTIFACTOR_MODE_LEAD_DAYS,
    MULTIFACTOR_MODES,
    _autosearch_winners_to_candidates,
    _mode_from_max_lead,
    _pick_latest_job_per_mode,
    autosearch_cache_key_for_mode,
    mode_forward_days,
    multifactor_keys_state_key,
    multifactor_result_state_key,
    pending_factor_apply_key,
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


# ─── v19.13.5: _autosearch_winners_to_candidates ──────────────────
def _fake_winner(weights, plateau, f1, sharpe, n_cross):
    return SimpleNamespace(
        weights=weights, plateau_score=plateau,
        oos_f1=f1, oos_sharpe=sharpe, n_crossings=n_cross,
    )


def test_winners_to_candidates_empty_input_returns_empty_list():
    assert _autosearch_winners_to_candidates([]) == []


def test_winners_to_candidates_maps_fields_one_to_one():
    winners = [
        _fake_winner({"VIX": 0.6, "DXY": 0.4}, 0.020, 0.727, 1.23, 43),
    ]
    out = _autosearch_winners_to_candidates(winners)
    assert len(out) == 1
    c = out[0]
    assert c["weights"] == {"VIX": 0.6, "DXY": 0.4}
    assert c["plateau_score"] == pytest.approx(0.020)
    assert c["f1"] == pytest.approx(0.727)
    assert c["sharpe"] == pytest.approx(1.23)
    assert c["n_crossings"] == 43


def test_winners_to_candidates_preserves_order():
    winners = [
        _fake_winner({"A": 1.0}, 0.05, 0.7, 1.0, 50),
        _fake_winner({"B": 1.0}, 0.04, 0.6, 0.8, 40),
        _fake_winner({"C": 1.0}, 0.03, 0.5, 0.6, 30),
    ]
    out = _autosearch_winners_to_candidates(winners)
    assert [list(c["weights"].keys())[0] for c in out] == ["A", "B", "C"]


def test_winners_to_candidates_defensive_copy_of_weights():
    # 防止 caller mutate adapter 內部結果 → 影響原始 SearchResult.weights
    original = {"VIX": 0.5, "DXY": 0.5}
    winners = [_fake_winner(original, 0.01, 0.3, 0.0, 10)]
    out = _autosearch_winners_to_candidates(winners)
    out[0]["weights"]["VIX"] = 999.0
    assert original == {"VIX": 0.5, "DXY": 0.5}, "adapter 應該深拷 weights"


def test_winners_to_candidates_none_weights_falls_back_to_empty_dict():
    # SearchResult.weights 可能為 None（極端 fallback case）
    winners = [_fake_winner(None, 0.0, 0.0, 0.0, 0)]
    out = _autosearch_winners_to_candidates(winners)
    assert out[0]["weights"] == {}


# ─── v19.13.7: dual-mode cache + _mode_from_max_lead ──────────────
def test_mode_from_max_lead_threshold_matches_route():
    # _mode_from_max_lead 與 route_apply_key_by_lead 在 boundary 上必須同步
    assert _mode_from_max_lead(5) == "pullback"
    assert _mode_from_max_lead(30) == "pullback"
    assert _mode_from_max_lead(31) == "macro"
    assert _mode_from_max_lead(90) == "macro"
    assert _mode_from_max_lead(365) == "macro"


def test_mode_from_max_lead_accepts_float():
    # slider 偶爾回 float — boundary 行為要一致
    assert _mode_from_max_lead(30.0) == "pullback"
    assert _mode_from_max_lead(30.5) == "macro"


def test_autosearch_cache_key_distinct_per_mode():
    # 雙 mode cache 槽必須不同，這是「不互相覆蓋」的根本保證
    assert (
        autosearch_cache_key_for_mode("pullback")
        != autosearch_cache_key_for_mode("macro")
    )


def test_autosearch_cache_key_covers_all_modes():
    # 所有 MULTIFACTOR_MODES 都要有對應 cache key
    keys = {autosearch_cache_key_for_mode(m) for m in MULTIFACTOR_MODES}
    assert len(keys) == len(MULTIFACTOR_MODES)


def test_autosearch_cache_key_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unknown mode"):
        autosearch_cache_key_for_mode("daily")
    with pytest.raises(ValueError, match="unknown mode"):
        autosearch_cache_key_for_mode("intraday")


# ─── v19.13.8: _pick_latest_job_per_mode (reboot recovery) ─────────
def _fake_job(run_id, lead_time_max, last_update):
    return SimpleNamespace(
        run_id=run_id, lead_time_max=lead_time_max, last_update=last_update,
    )


def test_pick_latest_job_per_mode_empty_returns_empty_dict():
    assert _pick_latest_job_per_mode([]) == {}


def test_pick_latest_job_per_mode_picks_latest_per_mode():
    # 兩 mode 各 2 個 job，各挑 last_update 最新
    jobs = [
        _fake_job("p_old", 30, "2026-06-04T10:00:00"),
        _fake_job("p_new", 30, "2026-06-05T13:15:00"),
        _fake_job("m_old", 90, "2026-06-03T10:00:00"),
        _fake_job("m_new", 90, "2026-06-05T13:16:00"),
    ]
    result = _pick_latest_job_per_mode(jobs)
    assert result == {"pullback": "p_new", "macro": "m_new"}


def test_pick_latest_job_per_mode_only_one_mode():
    # 只 pullback 有 job → macro 不出現
    jobs = [_fake_job("p1", 30, "2026-06-05")]
    result = _pick_latest_job_per_mode(jobs)
    assert result == {"pullback": "p1"}
    assert "macro" not in result


def test_pick_latest_job_per_mode_boundary_30_is_pullback():
    # lead_time_max=30 → pullback；lead_time_max=31 → macro（與 _mode_from_max_lead 同步）
    jobs = [
        _fake_job("p30", 30, "2026-06-05"),
        _fake_job("m31", 31, "2026-06-05"),
    ]
    result = _pick_latest_job_per_mode(jobs)
    assert result == {"pullback": "p30", "macro": "m31"}


def test_pick_latest_job_per_mode_skips_missing_run_id():
    # run_id 空字串的 job 跳過（防呆）
    jobs = [
        _fake_job("", 30, "2026-06-05"),
        _fake_job("p1", 30, "2026-06-04"),
    ]
    result = _pick_latest_job_per_mode(jobs)
    assert result == {"pullback": "p1"}


# ─── v19.13.9: pending_factor_apply_key (widget collision fix) ─────
def test_pending_factor_apply_key_distinct_per_mode():
    # 雙 mode pending slot 必須不同 — 不會跨 mode 互覆蓋
    assert (
        pending_factor_apply_key("pullback")
        != pending_factor_apply_key("macro")
    )


def test_pending_factor_apply_key_covers_all_modes():
    keys = {pending_factor_apply_key(m) for m in MULTIFACTOR_MODES}
    assert len(keys) == len(MULTIFACTOR_MODES)


def test_pending_factor_apply_key_rejects_unknown_mode():
    with pytest.raises(ValueError, match="unknown mode"):
        pending_factor_apply_key("daily")
    with pytest.raises(ValueError, match="unknown mode"):
        pending_factor_apply_key("intraday")


def test_pending_factor_apply_key_not_same_as_widget_key():
    # pending slot 必須 != widget key — 否則回到撞 widget key 的原 bug
    for mode in MULTIFACTOR_MODES:
        assert pending_factor_apply_key(mode) != multifactor_keys_state_key(mode)


def test_pending_factor_apply_key_not_same_as_autosearch_cache():
    # pending slot 也必須 != autosearch cache key — 三類 key 都要分離
    for mode in MULTIFACTOR_MODES:
        assert pending_factor_apply_key(mode) != autosearch_cache_key_for_mode(mode)
