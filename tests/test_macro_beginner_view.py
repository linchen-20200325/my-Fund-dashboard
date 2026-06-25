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


class TestChapterDepthEnhancement:
    """v19.126 — 每章必須含 白話 + 📐 公式 + 📜 案例 三層深度"""

    def test_every_chapter_has_formula_section(self):
        """每章必須含 📐 數學定義 / 數學公式 / 公式 段"""
        from ui.helpers.macro_beginner_view import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert "📐" in _b, (
                f"第 {_i+1} 章 ({_t[:20]}) 缺 📐 數學定義段"
            )

    def test_every_chapter_has_history_case_section(self):
        """每章必須含 📜 歷史案例 段"""
        from ui.helpers.macro_beginner_view import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert "📜" in _b, (
                f"第 {_i+1} 章 ({_t[:20]}) 缺 📜 歷史案例段"
            )

    def test_chapters_substantially_longer(self):
        """深化後每章內文 > 400 字(原本 > 100,代表深度確實補足)"""
        from ui.helpers.macro_beginner_view import _PRINCIPLE_CHAPTERS
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            assert len(_b.strip()) > 400, (
                f"第 {_i+1} 章 ({_t[:20]}) body {len(_b.strip())} 字,< 400(深化未達標)"
            )

    def test_chapters_have_numeric_dates_in_cases(self):
        """歷史案例段須含真實數據(年份 + 數字),不可只有空話"""
        from ui.helpers.macro_beginner_view import _PRINCIPLE_CHAPTERS
        import re
        for _i, (_t, _b) in enumerate(_PRINCIPLE_CHAPTERS):
            # 📜 段下方應有 ≥ 3 個 4 位數年份(1990-2024)
            _hist_idx = _b.find("📜")
            assert _hist_idx > 0, f"第 {_i+1} 章缺 📜 段"
            _hist_section = _b[_hist_idx:]
            _years = re.findall(r"(?:19[89]\d|20[012]\d)", _hist_section)
            assert len(_years) >= 3, (
                f"第 {_i+1} 章 ({_t[:20]}) 案例段年份數據 < 3 個(實際 {len(_years)}個)"
            )


# v19.124 §6 自審「3 個最容易出錯的輸入」:
#   1. 空 / None indicators → 預設 score 5(中性燈),全綠燈 3 個 → 不 raise ✅
#   2. SSOT 閾值漂移 → TestSSOTThresholdsApplied 強制以 SSOT 常數驗證觸發 ✅
#   3. 未知 phase(復甦/擴張/...以外)→ default ("觀望", yellow) ✅


class TestFactCorrectionsV19127:
    """v19.127 — 查證後事實修正回歸守衛(防數字被改回錯誤版本)。

    來源:2026-06-25 四路平行查證(FRED / BEA / ISM / CBOE / Wikipedia 交叉)。
    """

    def _all_text(self):
        from ui.helpers.macro_beginner_view import _PRINCIPLE_CHAPTERS
        return "\n".join(b for _, b in _PRINCIPLE_CHAPTERS)

    def test_ism_2022_first_sub50_is_november(self):
        """ISM 首次跌破 50 是 2022/11(非 10 月,10 月仍 50.2 擴張)"""
        t = self._all_text()
        assert "2022/11" in t and "首次跌破 50" in t
        # 不可再出現「2022/10 ... 49.0(跌破 50)」的錯誤組合
        assert "| 2022/10 | **49.0**(跌破 50)" not in t

    def test_yield_inversion_not_all_time_deepest(self):
        """2022-23 倒掛是『1981 年來最深』,非『史上最深』(Volcker 期更深)"""
        t = self._all_text()
        assert "1981 年來最深" in t
        assert "-1.1%**(史上最深)" not in t

    def test_merrill_clock_has_citation_disclaimer(self):
        """美林矩陣須帶『各方引用略有出入』免責(原報告各版數字不一)"""
        t = self._all_text()
        assert "各方引用略有出入" in t
        # 修正後高峰(Stagflation)商品應為 +28%,非捏造的 現金 +5.7%
        assert "+5.7%" not in t

    def test_2008_gdp_is_peak_trough_not_quarterly(self):
        """2008 GDP 谷底用峰谷 -4.3%,非誤用單季年化 -8.4%"""
        t = self._all_text()
        assert "-4.3%(峰谷)" in t
        assert "**-8.4%**" not in t

    def test_vix_intraday_vs_close_distinguished(self):
        """VIX 89.5(盤中)vs 82.7(收盤)須標明口徑"""
        t = self._all_text()
        assert "盤中史上最高" in t and "收盤史上最高" in t
