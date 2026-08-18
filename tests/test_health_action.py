"""品質 × 位階 行動建議合成器(services/health/action.py,v19.463)。

鎖住:3×3 矩陣九格、§1 退場(資料不足 / Core / 位階不可算)、吃本金旗標、邊界(空/非 dict)。
"""
from __future__ import annotations

from services.health.action import combine_action
from shared.colors import (
    MATERIAL_ORANGE,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)


def _h(grade="A", score=85, eat_warn=False):
    return {"grade": grade, "score": score, "eat_warn": eat_warn}


def _z(action="持有", z=0.1, applies=True, light="綠"):
    return {"applies": applies, "action": action, "z": z, "light": light,
            "reason": "test"}


# ── 3×3 矩陣九格 ─────────────────────────────────────────────
def test_good_low_is_add_green():
    r = combine_action(_h("A", 85), _z("加碼/逢低", -1.8))
    assert r["quality"] == "good" and r["timing"] == "low"
    assert "加碼好時機" in r["action"] and r["color"] == TRAFFIC_GREEN


def test_good_mid_is_hold():
    r = combine_action(_h("B", 70), _z("持有", 0.2))
    assert r["quality"] == "good" and r["timing"] == "mid"
    assert "續抱" in r["action"] and r["color"] == TRAFFIC_YELLOW


def test_good_high_is_dont_chase_orange():
    r = combine_action(_h("A", 82), _z("停利/減碼", 2.3))
    assert r["quality"] == "good" and r["timing"] == "high"
    assert "位階高" in r["action"] and r["color"] == MATERIAL_ORANGE


def test_mid_low_small_add():
    r = combine_action(_h("C", 55), _z("加碼/逢低", -1.6))
    assert r["quality"] == "mid" and r["timing"] == "low"
    assert "逢低" in r["action"] and r["color"] == TRAFFIC_YELLOW


def test_mid_mid_watch_neutral():
    r = combine_action(_h("C", 52), _z("持有", 0.0))
    assert r["quality"] == "mid" and r["timing"] == "mid"
    assert "持有觀察" in r["action"] and r["color"] == TRAFFIC_NEUTRAL


def test_mid_high_reduce():
    r = combine_action(_h("C", 51), _z("停利/減碼", 2.1))
    assert r["quality"] == "mid" and r["timing"] == "high"
    assert "減碼" in r["action"] and r["color"] == MATERIAL_ORANGE


def test_weak_low_dont_keep_orange():
    r = combine_action(_h("D", 40), _z("加碼/逢低", -1.9))
    assert r["quality"] == "weak" and r["timing"] == "low"
    assert "考慮換" in r["action"] and r["color"] == MATERIAL_ORANGE


def test_weak_mid_switch_red():
    r = combine_action(_h("F", 20), _z("持有", 0.1))
    assert r["quality"] == "weak" and r["timing"] == "mid"
    assert "考慮換" in r["action"] and r["color"] == TRAFFIC_RED


def test_weak_high_reduce_or_switch_red():
    r = combine_action(_h("F", 18), _z("停利/減碼", 2.5))
    assert r["quality"] == "weak" and r["timing"] == "high"
    assert "優先減碼" in r["action"] and r["color"] == TRAFFIC_RED


# ── §1 退場 ─────────────────────────────────────────────────
def test_quality_na_no_recommendation():
    """grade — / score None → 不建議,先補歷史淨值(最高優先,即使有時機訊號)。"""
    r = combine_action({"grade": "—", "score": None}, _z("加碼/逢低", -2.0))
    assert r["quality"] == "na"
    assert "資料不足" in r["action"] and r["color"] == TRAFFIC_NEUTRAL


def test_core_bucket_falls_back_to_quality_only():
    """Core(applies=False)→ 依品質,不擇時。"""
    r = combine_action(_h("A", 85), {"applies": False, "action": None, "z": None,
                                     "reason": "Core 內建配置"})
    assert r["timing"] == "na"
    assert "品質佳" in r["action"] and "內建配置" in r["action"]
    assert r["color"] == TRAFFIC_GREEN


def test_zscore_unknown_falls_back_to_quality_only():
    """位階不可算(applies=True 但 action None)→ 依品質 + 位階未知註。"""
    r = combine_action(_h("C", 50), {"applies": True, "action": None, "z": None,
                                     "reason": "位階不可算(insufficient)"})
    assert r["timing"] == "unknown"
    assert "品質中等" in r["action"] and "位階未知" in r["action"]


# ── 吃本金旗標 ───────────────────────────────────────────────
def test_eat_warn_surfaces_as_flag():
    r = combine_action(_h("D", 33, eat_warn=True), _z("持有", 0.1))
    assert "🔴 吃本金" in r["flags"]


def test_eat_warn_flag_even_when_quality_na():
    r = combine_action({"grade": "—", "score": None, "eat_warn": True},
                       _z("持有", 0.1))
    assert "🔴 吃本金" in r["flags"] and r["quality"] == "na"


# ── 邊界 ─────────────────────────────────────────────────────
def test_empty_dicts_degrade_not_crash():
    r = combine_action({}, {})
    assert r["quality"] == "na"          # 無 score → 資料不足
    assert isinstance(r["action"], str) and r["color"]


def test_non_dict_inputs_degrade_not_crash():
    r = combine_action(None, None)
    assert r["quality"] == "na" and isinstance(r["reason"], str)


def test_z_passthrough_and_reason_mentions_light():
    r = combine_action(_h("A", 85), _z("加碼/逢低", -1.75, light="綠"))
    assert r["z"] == -1.75
    assert "綠" in r["reason"] and "Z=-1.75" in r["reason"]
