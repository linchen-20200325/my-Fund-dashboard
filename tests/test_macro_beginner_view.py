"""v19.124 起 / v19.128 縮減 — compute_traffic_lights 邏輯測試。

驗證:
1. compute_traffic_lights 對景氣分數/階段/警訊指標正確分級
2. 缺指標時 graceful(不 raise)
3. SSOT 閾值正確套用(SAHM 0.5 / CFNAI -0.7)

v19.128 刪除:render / 教室 / 章節內容守衛 tests(對應功能已從 production 移除)
"""
from __future__ import annotations

import sys
import types

import pytest


def _stub_streamlit():
    if "streamlit" in sys.modules and getattr(
        sys.modules["streamlit"], "_is_test_stub", False
    ):
        return
    _mod = types.ModuleType("streamlit")
    _mod._is_test_stub = True

    def _noop(*a, **k):
        return None

    def _ctx(*a, **k):
        class _Ctx:
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                return False
        return _Ctx()

    for _name in (
        "markdown", "caption", "divider", "warning", "info", "success",
    ):
        setattr(_mod, _name, _noop)
    _mod.expander = _ctx
    # v19.128 — render_four_horizon_bar 需 st.columns(int) 回傳 N 個 ctx managers
    _mod.columns = lambda spec, **k: [_ctx() for _ in range(spec if isinstance(spec, int) else len(spec))]

    class _SS(dict):
        def get(self, k, default=None):
            return super().get(k, default)
    _mod.session_state = _SS()
    sys.modules["streamlit"] = _mod


_stub_streamlit()


# ════════════════════════════════════════════════════════════════
# compute_traffic_lights
# ════════════════════════════════════════════════════════════════

class TestComputeTrafficLights:
    def test_empty_indicators_no_raise(self):
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights({})
        assert "light1_health" in r
        assert "light2_action" in r
        assert "light3_alert" in r
        # 空 indicators → 預設綜合分 5 → 中性燈
        assert r["light1_health"]["level"] == "yellow"

    def test_none_indicators_no_raise(self):
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(None)
        assert r["light1_health"]["level"] in ("green", "yellow", "red")

    def test_high_score_green(self):
        """phase_info score ≥ 6 → 健康 (green)"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {}, phase_info={"phase": "擴張", "score": 7.5},
        )
        assert r["light1_health"]["level"] == "green"
        assert "健康" in r["light1_health"]["label"]

    def test_low_score_red(self):
        """phase_info score ≤ 3 → 危險 (red)"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {}, phase_info={"phase": "衰退", "score": 2.0},
        )
        assert r["light1_health"]["level"] == "red"
        assert "危險" in r["light1_health"]["label"]

    def test_mid_score_yellow(self):
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {}, phase_info={"phase": "減速", "score": 4.5},
        )
        assert r["light1_health"]["level"] == "yellow"
        assert "轉折" in r["light1_health"]["label"]

    def test_action_light_phase_mapping(self):
        """各景氣階段映到正確操作建議"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        for _phase, _expected in [
            ("復甦", "green"),
            ("擴張", "green"),
            ("高峰", "yellow"),
            ("減速", "yellow"),
            ("衰退", "red"),
        ]:
            r = compute_traffic_lights(
                {}, phase_info={"phase": _phase, "score": 5.0},
            )
            assert r["light2_action"]["level"] == _expected, (
                f"{_phase} 應對應 {_expected},實際 {r['light2_action']['level']}"
            )

    def test_alert_sahm_triggered(self):
        """薩姆 ≥ 0.5 → 緊急警訊 (red)"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {"SAHM": {"value": 0.55}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["light3_alert"]["level"] == "red"
        assert "緊急" in r["light3_alert"]["label"]

    def test_alert_vix_panic(self):
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {"VIX": {"value": 35.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["light3_alert"]["level"] == "red"

    def test_alert_vix_warning_only(self):
        """VIX 20-30 → 黃燈(警戒)"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {"VIX": {"value": 22.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["light3_alert"]["level"] == "yellow"

    def test_alert_yield_curve_inversion(self):
        """10Y-2Y < 0 倒掛 → 黃燈"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {"YIELD_10Y2Y": {"value": -0.5}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["light3_alert"]["level"] == "yellow"

    def test_alert_cfnai_recession(self):
        """CFNAI ≤ -0.7 → 紅燈"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {"CFNAI": {"value": -0.85}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["light3_alert"]["level"] == "red"

    def test_alert_all_green(self):
        """所有指標皆安全 → 綠燈"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {
                "VIX": {"value": 12.0},
                "HY_SPREAD": {"value": 3.0},
                "SAHM": {"value": 0.2},
                "YIELD_10Y2Y": {"value": 1.2},
                "CFNAI": {"value": 0.3},
            },
            phase_info={"phase": "擴張", "score": 6.5},
        )
        assert r["light3_alert"]["level"] == "green"
        assert "平靜" in r["light3_alert"]["label"]

    def test_alert_multiple_triggers_counted(self):
        """多個 trigger 應被計數於 headline"""
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {
                "SAHM": {"value": 0.55},
                "VIX": {"value": 35.0},
                "HY_SPREAD": {"value": 9.0},
            },
            phase_info={"phase": "衰退", "score": 2.0},
        )
        assert r["light3_alert"]["level"] == "red"
        assert "3" in r["light3_alert"]["headline"]


class TestSSOTThresholdsApplied:
    """驗證 SSOT 閾值正確套用,防止本檔出現 inline magic 偏離 §3.3"""

    def test_sahm_threshold_from_ssot(self):
        from shared.signal_thresholds import SAHM_RECESSION_THRESHOLD
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        # 剛好 = SSOT 閾值 → 觸發 red
        r = compute_traffic_lights(
            {"SAHM": {"value": SAHM_RECESSION_THRESHOLD}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["light3_alert"]["level"] == "red"

    def test_cfnai_threshold_from_ssot(self):
        from shared.signal_thresholds import CFNAI_RECESSION_THRESHOLD
        from ui.helpers.macro_beginner_view import compute_traffic_lights
        r = compute_traffic_lights(
            {"CFNAI": {"value": CFNAI_RECESSION_THRESHOLD}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["light3_alert"]["level"] == "red"



# ════════════════════════════════════════════════════════════════
# v19.128 — 四時域 summary 守衛
# ════════════════════════════════════════════════════════════════

class TestComputeFourHorizonSummary:
    """compute_four_horizon_summary 純函式守衛"""

    def test_empty_returns_4_buckets(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary({})
        assert set(r.keys()) == {"long", "mid", "short", "inflection"}
        for _k, _d in r.items():
            assert "level" in _d
            assert "label" in _d
            assert "headline" in _d
            assert "color" in _d
            assert "emoji" in _d

    def test_none_indicators_no_raise(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(None, phase_info={"phase": "復甦", "score": 6.5})
        assert r["long"]["level"] == "green"  # score 6.5 → green

    def test_long_horizon_uses_phase_score(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        # score 高 → green
        r_g = compute_four_horizon_summary({}, phase_info={"phase": "擴張", "score": 7.0})
        assert r_g["long"]["level"] == "green"
        # score 低 → red
        r_r = compute_four_horizon_summary({}, phase_info={"phase": "衰退", "score": 2.0})
        assert r_r["long"]["level"] == "red"
        # score 中 → yellow
        r_y = compute_four_horizon_summary({}, phase_info={"phase": "減速", "score": 4.5})
        assert r_y["long"]["level"] == "yellow"

    def test_short_horizon_vix_panic_red(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"VIX": {"value": 35.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["short"]["level"] == "red"
        assert "VIX" in r["short"]["headline"]

    def test_short_horizon_vix_warning_yellow(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"VIX": {"value": 22.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["short"]["level"] == "yellow"

    def test_inflection_sahm_triggers_red(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"SAHM": {"value": 0.55}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["inflection"]["level"] == "red"
        assert "薩姆" in r["inflection"]["headline"]

    def test_inflection_yield_inversion_yellow(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"YIELD_10Y2Y": {"value": -0.5}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["inflection"]["level"] == "yellow"

    def test_inflection_two_warnings_escalate_to_red(self):
        """≥ 2 個 warning(無 trigger)→ 紅燈(多重警訊)"""
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {
                "YIELD_10Y2Y": {"value": -0.5},
                "YIELD_10Y3M": {"value": -0.3},
            },
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["inflection"]["level"] == "red"

    def test_mid_horizon_pmi_contraction(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {"PMI": {"value": 45.0}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r["mid"]["level"] == "yellow"
        assert "PMI" in r["mid"]["headline"]

    def test_all_healthy_all_green(self):
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        r = compute_four_horizon_summary(
            {
                "VIX": {"value": 14.0},
                "HY_SPREAD": {"value": 3.0},
                "SAHM": {"value": 0.2},
                "YIELD_10Y2Y": {"value": 0.5},
                "PMI": {"value": 52.0},
                "CPI_YOY": {"value": 2.5},
                "UNRATE": {"value": 4.0},
                "CFNAI": {"value": 0.3},
            },
            phase_info={"phase": "擴張", "score": 6.5},
        )
        assert r["long"]["level"] == "green"
        assert r["mid"]["level"] == "green"
        assert r["short"]["level"] == "green"
        assert r["inflection"]["level"] == "green"

    def test_render_no_raise(self):
        """render_four_horizon_bar 餵任何 summary 都不 raise"""
        from ui.helpers.macro_beginner_view import (
            compute_four_horizon_summary,
            render_four_horizon_bar,
        )
        _summary = compute_four_horizon_summary(None)
        render_four_horizon_bar(_summary)

    def test_ssot_thresholds_from_signal_thresholds(self):
        """確認用 SSOT(SAHM_RECESSION_THRESHOLD / CFNAI_RECESSION_THRESHOLD)而非 inline magic"""
        from shared.signal_thresholds import (
            CFNAI_RECESSION_THRESHOLD,
            SAHM_RECESSION_THRESHOLD,
        )
        from ui.helpers.macro_beginner_view import compute_four_horizon_summary
        # 剛好 = SSOT 閾值 → 觸發
        r1 = compute_four_horizon_summary(
            {"SAHM": {"value": SAHM_RECESSION_THRESHOLD}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r1["inflection"]["level"] == "red"
        r2 = compute_four_horizon_summary(
            {"CFNAI": {"value": CFNAI_RECESSION_THRESHOLD}},
            phase_info={"phase": "擴張", "score": 6.0},
        )
        assert r2["inflection"]["level"] == "red"
