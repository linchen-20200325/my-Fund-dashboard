"""衛星停利自動化(services/satellite.py,v19.466)。

鎖住:5 態(強制/分批/續抱/核心/未填成本)+ 門檻邊界 + §1 誠實(None ≠ 0%)。
"""
from __future__ import annotations

from services.satellite import satellite_stop_gain
from shared.colors import MATERIAL_ORANGE, TRAFFIC_RED


def test_force_stop_gain_at_20():
    r = satellite_stop_gain(20.0, is_satellite=True)
    assert r["lamp"] == "強制停利" and r["status"] == "force" and r["color"] == TRAFFIC_RED


def test_force_stop_gain_above_20():
    assert satellite_stop_gain(35.5, is_satellite=True)["lamp"] == "強制停利"


def test_batch_stop_gain_at_15():
    r = satellite_stop_gain(15.0, is_satellite=True)
    assert r["lamp"] == "分批停利" and r["status"] == "batch" and r["color"] == MATERIAL_ORANGE


def test_batch_between_15_and_20():
    assert satellite_stop_gain(18.7, is_satellite=True)["lamp"] == "分批停利"


def test_hold_below_15():
    r = satellite_stop_gain(9.9, is_satellite=True)
    assert r["lamp"] is None and r["status"] == "hold" and "續抱" in r["note"]


def test_hold_at_boundary_just_below_15():
    assert satellite_stop_gain(14.99, is_satellite=True)["status"] == "hold"


def test_loss_is_hold_not_lamp():
    r = satellite_stop_gain(-12.0, is_satellite=True)
    assert r["lamp"] is None and r["status"] == "hold"


def test_core_not_judged():
    r = satellite_stop_gain(30.0, is_satellite=False)     # 核心即使獲利 30% 也不停利
    assert r["lamp"] is None and r["status"] == "core" and "核心" in r["note"]


def test_no_cost_none_not_zero():
    # 衛星但未填成本 → 誠實「無法判」,不當 0%(§1)
    r = satellite_stop_gain(None, is_satellite=True)
    assert r["lamp"] is None and r["status"] == "no_cost" and r["pct"] is None
    assert "未填平均成本" in r["note"]


def test_no_cost_core_prioritises_core():
    # 核心 + 未填成本 → 核心優先(核心根本不判,不必談成本)
    r = satellite_stop_gain(None, is_satellite=False)
    assert r["status"] == "core"
