"""v19.124 tests — macro_beginner_view 三大紅綠燈邏輯 + render 邊界。

驗證:
1. compute_traffic_lights 對景氣分數/階段/警訊指標正確分級
2. 缺指標時 graceful(不 raise)
3. SSOT 閾值正確套用(SAHM 0.5 / CFNAI -0.7)
4. render_beginner_view + render_principle_classroom 不 raise
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
# render 函式邊界(streamlit stubbed)
# ════════════════════════════════════════════════════════════════

class TestRenderFunctions:
    def test_render_beginner_view_empty_no_raise(self):
        from ui.helpers.macro_beginner_view import render_beginner_view
        render_beginner_view({})  # 顯示 warning,不 raise
        render_beginner_view(None)

    def test_render_beginner_view_with_data_no_raise(self):
        from ui.helpers.macro_beginner_view import render_beginner_view
        render_beginner_view(
            {"VIX": {"value": 18.0}, "SAHM": {"value": 0.2}},
            phase_info={"phase": "擴張", "score": 6.5},
        )

    def test_render_principle_classroom_no_raise(self):
        from ui.helpers.macro_beginner_view import render_principle_classroom
        render_principle_classroom()


class TestPrincipleChaptersIntegrity:
    """確保教室內容不為空且段數足夠"""

    def test_at_least_10_chapters(self):
        from ui.helpers.macro_beginner_view import _PRINCIPLE_CHAPTERS
        assert len(_PRINCIPLE_CHAPTERS) >= 10, (
            f"原理小教室應至少 10 段,實際 {len(_PRINCIPLE_CHAPTERS)} 段"
        )

    def test_all_chapters_have_title_and_body(self):
        from ui.helpers.macro_beginner_view import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert _t and _t.strip(), f"第 {_i+1} 章 title 為空"
            assert _b and len(_b.strip()) > 100, (
                f"第 {_i+1} 章 body 過短(< 100 字)"
            )


# v19.124 §6 自審「3 個最容易出錯的輸入」:
#   1. 空 / None indicators → 預設 score 5(中性燈),全綠燈 3 個 → 不 raise ✅
#   2. SSOT 閾值漂移 → TestSSOTThresholdsApplied 強制以 SSOT 常數驗證觸發 ✅
#   3. 未知 phase(復甦/擴張/...以外)→ default ("觀望", yellow) ✅
