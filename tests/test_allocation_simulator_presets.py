"""test_allocation_simulator_presets.py — v18.280 4 風格 preset 矩陣驗收."""
from __future__ import annotations

import pytest

from services.allocation_simulator import (
    DEFAULT_PHASE_SCRIPT,
    STRATEGY_PRESETS,
    get_preset_phase_script,
)

EXPECTED_PHASES = ["復甦", "擴張", "放緩", "衰退"]
EXPECTED_PRESETS = ["balanced", "aggressive_growth", "income_first", "defensive"]


class TestStrategyPresetsStructure:
    def test_four_presets_exist(self):
        assert set(STRATEGY_PRESETS.keys()) == set(EXPECTED_PRESETS)

    def test_each_preset_has_label_desc_allocations(self):
        for key, preset in STRATEGY_PRESETS.items():
            assert "label" in preset, f"{key} 缺 label"
            assert "desc" in preset, f"{key} 缺 desc"
            assert "allocations" in preset, f"{key} 缺 allocations"
            assert isinstance(preset["label"], str) and preset["label"]
            assert isinstance(preset["desc"], str) and preset["desc"]

    def test_each_preset_covers_four_phases(self):
        for key, preset in STRATEGY_PRESETS.items():
            assert set(preset["allocations"].keys()) == set(EXPECTED_PHASES), (
                f"{key} 階段不齊：{list(preset['allocations'])}"
            )

    def test_labels_are_unique(self):
        labels = [p["label"] for p in STRATEGY_PRESETS.values()]
        assert len(labels) == len(set(labels)), "preset label 重複"


class TestAllocationsSumTo100:
    @pytest.mark.parametrize("preset_key", EXPECTED_PRESETS)
    @pytest.mark.parametrize("phase", EXPECTED_PHASES)
    def test_drip_cash_stay_sum_100(self, preset_key, phase):
        alloc = STRATEGY_PRESETS[preset_key]["allocations"][phase]
        total = alloc["drip_pct"] + alloc["cash_pct"] + alloc["stay_pct"]
        assert total == 100, (
            f"{preset_key} / {phase} 三桶和 = {total} ≠ 100"
        )

    @pytest.mark.parametrize("preset_key", EXPECTED_PRESETS)
    @pytest.mark.parametrize("phase", EXPECTED_PHASES)
    def test_all_pcts_non_negative(self, preset_key, phase):
        alloc = STRATEGY_PRESETS[preset_key]["allocations"][phase]
        for bucket in ("drip_pct", "cash_pct", "stay_pct"):
            assert alloc[bucket] >= 0, (
                f"{preset_key} / {phase} / {bucket} = {alloc[bucket]} < 0"
            )


class TestStrategyDifferentiation:
    """確保 4 風格不是雷同 — 在不同階段有可觀察的差異化。"""

    def test_aggressive_復甦_drip_higher_than_defensive(self):
        agg = STRATEGY_PRESETS["aggressive_growth"]["allocations"]["復甦"]
        defn = STRATEGY_PRESETS["defensive"]["allocations"]["復甦"]
        assert agg["drip_pct"] > defn["drip_pct"], "積極復甦 DRIP 應 > 防禦復甦"

    def test_defensive_衰退_stay_dominates(self):
        defn = STRATEGY_PRESETS["defensive"]["allocations"]["衰退"]
        assert defn["stay_pct"] >= 80, f"防禦衰退 STAY 應 ≥ 80（現 {defn['stay_pct']}）"

    def test_income_first_high_cash_in_expansion(self):
        inc = STRATEGY_PRESETS["income_first"]["allocations"]["擴張"]
        assert inc["cash_pct"] >= 50, f"收益優先擴張 CASH 應 ≥ 50（現 {inc['cash_pct']}）"

    def test_balanced_matches_default_phase_script(self):
        """balanced preset 必須 = 現有 DEFAULT_PHASE_SCRIPT 兼容性"""
        bal = STRATEGY_PRESETS["balanced"]["allocations"]
        for seg in DEFAULT_PHASE_SCRIPT:
            phase = seg["phase"]
            assert bal[phase]["drip_pct"] == seg["drip_pct"], (
                f"balanced / {phase} DRIP 應 = DEFAULT_PHASE_SCRIPT"
            )
            assert bal[phase]["cash_pct"] == seg["cash_pct"]
            assert bal[phase]["stay_pct"] == seg["stay_pct"]


class TestGetPresetPhaseScript:
    @pytest.mark.parametrize("preset_key", EXPECTED_PRESETS)
    def test_returns_four_segments_in_order(self, preset_key):
        script = get_preset_phase_script(preset_key)
        assert len(script) == 4
        assert [s["phase"] for s in script] == EXPECTED_PHASES

    @pytest.mark.parametrize("preset_key", EXPECTED_PRESETS)
    def test_preserves_months_and_nav_change(self, preset_key):
        script = get_preset_phase_script(preset_key)
        for orig, new in zip(DEFAULT_PHASE_SCRIPT, script):
            assert orig["months"] == new["months"]
            assert orig["monthly_nav_change_pct"] == new["monthly_nav_change_pct"]

    @pytest.mark.parametrize("preset_key", EXPECTED_PRESETS)
    def test_applies_preset_allocations(self, preset_key):
        script = get_preset_phase_script(preset_key)
        expected_alloc = STRATEGY_PRESETS[preset_key]["allocations"]
        for seg in script:
            exp = expected_alloc[seg["phase"]]
            assert seg["drip_pct"] == exp["drip_pct"]
            assert seg["cash_pct"] == exp["cash_pct"]
            assert seg["stay_pct"] == exp["stay_pct"]

    def test_unknown_preset_raises_keyerror(self):
        with pytest.raises(KeyError, match="未知 preset_key"):
            get_preset_phase_script("nonexistent_preset")

    def test_returned_script_doesnt_mutate_default(self):
        """確保回傳 dict 是 deep copy，不會污染 DEFAULT_PHASE_SCRIPT。"""
        before = [dict(s) for s in DEFAULT_PHASE_SCRIPT]
        script = get_preset_phase_script("aggressive_growth")
        script[0]["drip_pct"] = 999  # 污染
        # DEFAULT_PHASE_SCRIPT 應原封不動
        for orig, expected in zip(DEFAULT_PHASE_SCRIPT, before):
            assert orig == expected
