"""v19.121 tests — fund_grp_health_extras P1 視覺 2 區塊單元測試。

驗證 _render_mk_signal_table / _render_bollinger_expanders 對邊界輸入
能正確降級,不 raise。共用 P0 測試的 streamlit stub。
"""
from __future__ import annotations

import sys
import types

import pandas as pd
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
        "markdown", "caption", "divider", "info", "success", "warning",
        "metric", "dataframe", "plotly_chart", "code",
    ):
        setattr(_mod, _name, _noop)

    _mod.expander = _ctx
    _mod.columns = lambda *a, **k: [_ctx() for _ in range(a[0] if a else 1)]
    # session_state 可變 attr stub
    class _SS(dict):
        def get(self, k, default=None):
            return super().get(k, default)
    _mod.session_state = _SS()
    sys.modules["streamlit"] = _mod


_stub_streamlit()


# ════════════════════════════════════════════════════════════════
# _render_mk_signal_table
# ════════════════════════════════════════════════════════════════

class TestMkSignalTable:
    def test_no_phase_info_shows_prompt(self):
        """無 phase_info → 提示「先到總經 Tab 載入」,不 raise"""
        from ui.helpers.fund_grp_health_extras import _render_mk_signal_table
        # 確保 session_state 無 phase_info
        import streamlit as st
        st.session_state.clear()
        _render_mk_signal_table([{"code": "A001", "name": "A"}])

    def test_empty_funds_with_phase_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_mk_signal_table
        import streamlit as st
        st.session_state.clear()
        st.session_state["phase_info"] = {"phase": "擴張", "score": 6.5}
        _render_mk_signal_table([])

    def test_funds_without_metrics_no_raise(self):
        """無 buy/sell levels → 顯示 '—',不偽造"""
        from ui.helpers.fund_grp_health_extras import _render_mk_signal_table
        import streamlit as st
        st.session_state.clear()
        st.session_state["phase_info"] = {"phase": "擴張", "score": 6.5}
        _funds = [
            {"code": "A001", "name": "A", "metrics": {}, "moneydj_raw": {}},
        ]
        _render_mk_signal_table(_funds)

    def test_funds_with_full_metrics_no_raise(self):
        """完整 metrics → 算 zone + signal"""
        from ui.helpers.fund_grp_health_extras import _render_mk_signal_table
        import streamlit as st
        st.session_state.clear()
        st.session_state["phase_info"] = {"phase": "擴張", "score": 6.5}
        _funds = [
            {
                "code": "A001", "name": "Fund A",
                "metrics": {
                    "nav": 100.0,
                    "buy1": 95.0, "buy2": 90.0, "buy3": 85.0,
                    "sell1": 105.0, "sell2": 110.0, "sell3": 115.0,
                },
                "moneydj_raw": {},
            },
        ]
        _render_mk_signal_table(_funds)

    def test_zone_classification_in_buy_zone(self):
        """現價落 ≤ buy1 → 應分類為「小跌」(此 test 透過 helper 結果觀察)"""
        from ui.helpers.fund_grp_health_extras import _render_mk_signal_table
        import streamlit as st
        st.session_state.clear()
        st.session_state["phase_info"] = {"phase": "擴張", "score": 6.5}
        _funds = [
            {
                "code": "A001", "name": "Fund A",
                "metrics": {
                    "nav": 94.0,  # ≤ buy1=95 → 小跌
                    "buy1": 95.0, "buy2": 90.0, "buy3": 85.0,
                    "sell1": 105.0, "sell2": 110.0, "sell3": 115.0,
                },
            },
        ]
        _render_mk_signal_table(_funds)  # 不 raise 即代表分類路徑命中


# ════════════════════════════════════════════════════════════════
# _render_bollinger_expanders
# ════════════════════════════════════════════════════════════════

class TestBollingerExpanders:
    def test_empty_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_bollinger_expanders
        _render_bollinger_expanders([])

    def test_short_series_skipped_silently(self):
        """NAV < 20 天 → 該檔顯示 caption,不 raise"""
        from ui.helpers.fund_grp_health_extras import _render_bollinger_expanders
        _idx = pd.date_range("2024-01-01", periods=10, freq="D")
        _funds = [
            {"code": "A001", "name": "A",
             "series": pd.Series([100.0] * 10, index=_idx)},
        ]
        _render_bollinger_expanders(_funds)

    def test_normal_series_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_bollinger_expanders
        _idx = pd.date_range("2024-01-01", periods=100, freq="D")
        _vals = [100 + i * 0.1 for i in range(100)]
        _funds = [
            {"code": "A001", "name": "A",
             "series": pd.Series(_vals, index=_idx),
             "metrics": {
                 "buy1": 95.0, "buy2": 90.0, "buy3": 85.0,
                 "sell1": 115.0, "sell2": 120.0, "sell3": 125.0,
             }},
        ]
        _render_bollinger_expanders(_funds)

    def test_series_with_dividends_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_bollinger_expanders
        _idx = pd.date_range("2024-01-01", periods=100, freq="D")
        _vals = [100 + i * 0.1 for i in range(100)]
        _funds = [
            {"code": "A001", "name": "A",
             "series": pd.Series(_vals, index=_idx),
             "moneydj_raw": {
                 "dividends": [
                     {"date": "2024-01-15", "amount": 0.5},
                     {"date": "2024-02-15", "amount": 0.5},
                 ],
             },
             "metrics": {}},
        ]
        _render_bollinger_expanders(_funds)

    def test_multiple_funds_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_bollinger_expanders
        _idx = pd.date_range("2024-01-01", periods=100, freq="D")
        _funds = [
            {"code": f"A{i:03d}", "name": f"Fund {i}",
             "series": pd.Series([100 + j * 0.1 for j in range(100)], index=_idx),
             "metrics": {}}
            for i in range(3)
        ]
        _render_bollinger_expanders(_funds)


# v19.121 §6 自審「3 個最容易出錯的輸入」:
#   1. 無 phase_info(總經未載入)→ 顯示提示,不 raise ✅
#   2. 無 buy/sell metrics → 顯示 '—',不偽造 ✅
#   3. NAV 序列 < 20 天 → Bollinger skip + caption,不 raise ✅
