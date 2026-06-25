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


_stub_modules()


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
