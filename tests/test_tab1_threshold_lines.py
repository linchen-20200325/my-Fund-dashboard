"""v19.132 tests — _tp_threshold_lines helper 守 SSOT 對齊."""
from __future__ import annotations

import sys
import types


def _stub_modules():
    """Stub plotly + streamlit so ui.tab1_macro 可 import."""
    if "plotly" not in sys.modules:
        class _F:
            def __getattr__(self, n):
                return lambda *a, **k: None
        sys.modules["plotly"] = _F()
        sys.modules["plotly.graph_objects"] = _F()
        sys.modules["plotly.subplots"] = _F()
    if "streamlit" not in sys.modules:
        class _S:
            def __getattr__(self, n):
                return lambda *a, **k: None
            session_state = {}
        sys.modules["streamlit"] = _S()


# v19.174:module-top stub call 拿掉 — 改由 conftest._switch_streamlit_module_per_test
# fixture per-test 裝(避免 stub 污染後續 collect 的 test,例如 AppTest)。
# _stub_modules()


class TestTpThresholdLines:
    """v19.132 sparkline threshold 對齊 SSOT 守衛"""

    def test_sahm_uses_ssot(self):
        from shared.signal_thresholds import SAHM_RECESSION_THRESHOLD
        from ui.tab1_macro import _tp_threshold_lines
        lines = _tp_threshold_lines("sahm_rule")
        assert len(lines) == 1
        assert lines[0][0] == SAHM_RECESSION_THRESHOLD

    def test_cfnai_uses_ssot(self):
        from shared.signal_thresholds import CFNAI_RECESSION_THRESHOLD
        from ui.tab1_macro import _tp_threshold_lines
        lines = _tp_threshold_lines("lei_cfnai")
        assert len(lines) == 1
        assert lines[0][0] == CFNAI_RECESSION_THRESHOLD

    def test_hy_has_two_levels(self):
        from ui.tab1_macro import _tp_threshold_lines
        lines = _tp_threshold_lines("hy_spread")
        assert len(lines) == 2
        # warn 在 crit 之下
        assert lines[0][0] < lines[1][0]
        # warn = 6%, crit = 8%
        assert lines[0][0] == 6.0
        assert lines[1][0] == 8.0

    def test_pmi_yield_at_zero(self):
        """擴散 / 倒掛指標都用零點"""
        from ui.tab1_macro import _tp_threshold_lines
        assert _tp_threshold_lines("pmi_diff")[0][0] == 0.0
        assert _tp_threshold_lines("yield_curve")[0][0] == 0.0

    def test_unknown_key_returns_empty(self):
        from ui.tab1_macro import _tp_threshold_lines
        assert _tp_threshold_lines("nonexistent") == []

    def test_each_line_has_4_fields(self):
        """確保 tuple 結構 (y, dash, color, annotation) 不被破壞"""
        from ui.tab1_macro import _tp_threshold_lines
        for k in ["pmi_diff", "yield_curve", "hy_spread", "sahm_rule", "lei_cfnai"]:
            for line in _tp_threshold_lines(k):
                assert len(line) == 4
                _y, _dash, _color, _txt = line
                assert isinstance(_y, (int, float))
                assert _dash in ("dot", "dash", "solid")
                assert _color.startswith("#")
                assert _txt


class TestRadarThresholdLines:
    """v19.133 短線雷達 10 燈 sparkline threshold 守衛"""

    def test_vix_level_uses_service_thresholds(self):
        """services/risk_radar.py L103-L105 用 cur >= 30 / 25"""
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("vix_level")
        assert len(lines) == 2
        assert lines[0][0] == 25.0
        assert lines[1][0] == 30.0

    def test_vix_term_struct_uses_service_thresholds(self):
        """services L341-L343 用 1.00 / 1.10"""
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("vix_term_struct")
        assert lines[0][0] == 1.00 and lines[1][0] == 1.10

    def test_move_uses_service_thresholds(self):
        """services L426-L428 用 110 / 130"""
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("move_level")
        assert lines[0][0] == 110.0 and lines[1][0] == 130.0

    def test_sector_rotation_uses_service_thresholds(self):
        """services L532-L534 用 1.00 / 1.20"""
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("sector_rotation")
        assert lines[0][0] == 1.00 and lines[1][0] == 1.20

    def test_hy_radar_matches_tp_thresholds(self):
        """HY 在短線雷達與拐點桶用同一組 threshold(6/8%)避免顯示不一致"""
        from ui.tab1_macro import _radar_threshold_lines, _tp_threshold_lines
        radar_lines = _radar_threshold_lines("hy_oas_delta")
        tp_lines = _tp_threshold_lines("hy_spread")
        assert radar_lines[0][0] == tp_lines[0][0]
        assert radar_lines[1][0] == tp_lines[1][0]

    def test_pcr_thresholds_present(self):
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("put_call_ratio")
        assert lines[0][0] == 1.00 and lines[1][0] == 1.50

    def test_unsupported_radar_keys_empty(self):
        """trend=level 但判斷=delta 的 indicators 不加 hline"""
        from ui.tab1_macro import _radar_threshold_lines
        for k in ("yield_10y_shock", "spx_trend_break", "sox_drop", "asia_overnight"):
            assert _radar_threshold_lines(k) == []

    def test_radar_sparkline_handles_empty_trend(self):
        """空 / 單筆 trend → None,不 raise"""
        from ui.tab1_macro import _make_radar_sparkline
        assert _make_radar_sparkline([], "vix_level", "#ff0000") is None
        assert _make_radar_sparkline(None, "vix_level", "#ff0000") is None
        assert _make_radar_sparkline([1.0], "vix_level", "#ff0000") is None


class TestUsLiquidityCardThresholdLines:
    """v19.188 🌳 長期座標桶 美股流動性卡片 SPEC 線守 SSOT
    (與 services.us_liquidity_engine 各 fetcher 的 color cut-off 同源)。"""

    def test_hy_oas_matches_engine_cutoffs(self):
        from services.us_liquidity_engine import HY_OAS_WARN_PCT, HY_OAS_CRISIS_PCT
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_hy_oas")
        assert [lines[0][0], lines[1][0]] == [HY_OAS_WARN_PCT, HY_OAS_CRISIS_PCT]

    def test_m2_yoy_matches_engine_cutoffs(self):
        from services.us_liquidity_engine import M2_YOY_LOOSE_PCT, M2_YOY_HOT_PCT
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_m2_yoy")
        assert [lines[0][0], lines[1][0]] == [M2_YOY_LOOSE_PCT, M2_YOY_HOT_PCT]

    def test_rrp_matches_engine_cutoff(self):
        from services.us_liquidity_engine import RRP_DRAIN_BN
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_rrp")
        assert len(lines) == 1 and lines[0][0] == RRP_DRAIN_BN

    def test_aaii_matches_engine_cutoffs(self):
        from services.us_liquidity_engine import AAII_EUPHORIA_PCT, AAII_PANIC_PCT
        from ui.tab1_macro import _radar_threshold_lines
        lines = _radar_threshold_lines("us_aaii")
        assert [lines[0][0], lines[1][0]] == [AAII_EUPHORIA_PCT, AAII_PANIC_PCT]

    def test_delta_based_keys_no_lines(self):
        """walcl / hyg_lqd 為 delta-based,無 natural level 線。"""
        from ui.tab1_macro import _radar_threshold_lines
        assert _radar_threshold_lines("us_walcl") == []
        assert _radar_threshold_lines("us_hyg_lqd") == []

    def test_each_us_line_has_4_fields(self):
        from ui.tab1_macro import _radar_threshold_lines
        for k in ("us_hy_oas", "us_m2_yoy", "us_rrp", "us_aaii"):
            for line in _radar_threshold_lines(k):
                assert len(line) == 4
                _y, _dash, _color, _txt = line
                assert isinstance(_y, (int, float))
                assert _dash in ("dot", "dash", "solid")
                assert _color.startswith("#")
                assert _txt
