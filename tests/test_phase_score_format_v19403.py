"""v19.403 Phase 2 DUP-3 — 景氣位階字卡 SSOT `format_phase_score` 回歸測試。

phase score 為 `calc_macro_phase` 的 0-10 循環評分(恆 ≥ 0),**禁帶正負號**。
原 `tab_fund_grp_health.py` 誤用 `{:+.1f}` 顯示「+6.5」,與 hero 的 23 指標淨分
(genuinely signed)撞臉 → 收斂到單一 SSOT 格式 `{phase} {score:.1f}/10`。
"""
from __future__ import annotations

from ui.helpers.macro_helpers import format_phase_score


def test_basic_format_v19403():
    assert format_phase_score({"phase": "擴張", "score": 6.5}) == "擴張 6.5/10"


def test_zero_score_not_signed_v19403():
    """score=0 也不帶 + 號(修原 +0.0 假號)。"""
    out = format_phase_score({"phase": "衰退", "score": 0})
    assert out == "衰退 0.0/10"
    assert "+" not in out


def test_never_signed_v19403():
    """任何 score 都不含 + 號 —— 這是本次修的核心(phase score 恆非負)。"""
    assert "+" not in format_phase_score({"phase": "高峰", "score": 8.0})


def test_missing_score_no_fake_zero_v19403():
    """有 phase 無 score → 只回 phase,不捏造 0.0 分(§1)。"""
    assert format_phase_score({"phase": "轉折", "score": None}) == "轉折"


def test_empty_or_none_v19403():
    assert format_phase_score({}) == ""
    assert format_phase_score(None) == ""
    assert format_phase_score({"phase": ""}) == ""


def test_score_rounds_1dp_v19403():
    assert format_phase_score({"phase": "擴張", "score": 6.53}) == "擴張 6.5/10"
