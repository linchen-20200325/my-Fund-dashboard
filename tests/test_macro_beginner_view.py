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


# ════════════════════════════════════════════════════════════════
# v19.146 — 五桶 summary 擴充(4-horizon + 📰 新聞)
# 守 SSOT 對齊 + 向下相容(4-horizon 仍可運作 + render fallback)
# ════════════════════════════════════════════════════════════════
class TestFiveBucketSummary:
    """compute_five_bucket_summary / render_five_bucket_bar 守衛"""

    def test_news_gray_when_news_items_none(self):
        """news_items=None → 第 5 桶 ⬜「未掃描」(對齊 Stock 未抓 RSS 狀態)。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        r = compute_five_bucket_summary({}, phase_info={}, news_items=None)
        assert "news" in r
        assert r["news"]["level"] == "gray"
        assert "⬜" in r["news"]["emoji"]

    def test_news_green_when_no_systemic_hit(self):
        """news_items 有資料但無 systemic → 🟢 無系統風險。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        items = [
            {"title": "Fed signals patience", "is_systemic": False},
            {"title": "Earnings beat", "is_systemic": False},
        ]
        r = compute_five_bucket_summary({}, phase_info={}, news_items=items)
        assert r["news"]["level"] == "green"
        assert "🟢" in r["news"]["emoji"]
        assert "2 則" in r["news"]["headline"]

    def test_news_yellow_on_one_systemic(self):
        """1 則 systemic → 🟡(對齊 SSOT NEWS_SYSTEMIC_YELLOW_COUNT=1)。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        items = [
            {"title": "Bank run risk warning", "is_systemic": True},
            {"title": "Earnings beat", "is_systemic": False},
        ]
        r = compute_five_bucket_summary({}, phase_info={}, news_items=items)
        assert r["news"]["level"] == "yellow"
        assert "🟡" in r["news"]["emoji"]
        assert "🚨" in r["news"]["headline"]

    def test_news_red_on_two_or_more_systemic(self):
        """≥2 則 systemic → 🔴(對齊 SSOT NEWS_SYSTEMIC_RED_COUNT=2)。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        items = [
            {"title": "War escalates", "is_systemic": True},
            {"title": "Major bank fails", "is_systemic": True},
            {"title": "VIX spikes", "is_systemic": True},
        ]
        r = compute_five_bucket_summary({}, phase_info={}, news_items=items)
        assert r["news"]["level"] == "red"
        assert "🔴" in r["news"]["emoji"]
        assert "系統性警報" in r["news"]["label"]

    def test_preserves_four_horizons(self):
        """v19.146 不破壞既有 4-horizon — 應仍含 long/mid/short/inflection 完整 dict。"""
        from ui.helpers.macro_beginner_view import compute_five_bucket_summary
        r = compute_five_bucket_summary(
            {"PMI": {"value": 45.0}},
            phase_info={"phase": "減速", "score": 4.0},
            news_items=None,
        )
        for k in ("long", "mid", "short", "inflection", "news"):
            assert k in r
            assert "level" in r[k]
            assert "label" in r[k]
            assert "emoji" in r[k]
            assert "color" in r[k]

    def test_ssot_thresholds_imported_not_hardcoded(self):
        """v19.146 應 import SSOT NEWS_SYSTEMIC_*_COUNT,非 inline 寫死。"""
        from shared.macro_buckets import (
            NEWS_SYSTEMIC_YELLOW_COUNT, NEWS_SYSTEMIC_RED_COUNT,
        )
        assert NEWS_SYSTEMIC_YELLOW_COUNT == 1
        assert NEWS_SYSTEMIC_RED_COUNT == 2


class TestFiveBucketBarRender:
    """render_five_bucket_bar 守衛(streamlit stub mock)"""

    def test_renders_5_cols_with_news(self, monkeypatch):
        """summary 含 news → 5 columns。"""
        import ui.helpers.macro_beginner_view as mbv
        col_counts = []

        class _FakeCol:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def _fake_columns(n):
            col_counts.append(n)
            return [_FakeCol() for _ in range(n)]

        def _fake_markdown(*a, **k):
            return None

        monkeypatch.setattr(mbv.st, "columns", _fake_columns)
        monkeypatch.setattr(mbv.st, "markdown", _fake_markdown)
        summary = {
            "long": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
            "mid": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
            "short": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
            "inflection": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
            "news": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
        }
        mbv.render_five_bucket_bar(summary)
        assert col_counts == [5], f"應 5 columns,實際 {col_counts}"

    def test_fallback_to_4_cols_when_no_news_key(self, monkeypatch):
        """summary 無 news key(舊 4-horizon 結構)→ fallback 4 columns,不留空白。"""
        import ui.helpers.macro_beginner_view as mbv
        col_counts = []

        class _FakeCol:
            def __enter__(self): return self
            def __exit__(self, *a): return False

        def _fake_columns(n):
            col_counts.append(n)
            return [_FakeCol() for _ in range(n)]

        def _fake_markdown(*a, **k):
            return None

        monkeypatch.setattr(mbv.st, "columns", _fake_columns)
        monkeypatch.setattr(mbv.st, "markdown", _fake_markdown)
        summary = {
            "long": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
            "mid": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
            "short": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
            "inflection": {"color": "#3fb950", "emoji": "🟢", "label": "綠", "headline": ""},
        }
        mbv.render_five_bucket_bar(summary)
        assert col_counts == [4], f"無 news 應 fallback 4 columns,實際 {col_counts}"
