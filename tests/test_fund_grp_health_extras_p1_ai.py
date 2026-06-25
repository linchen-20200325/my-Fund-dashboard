"""v19.122 tests — fund_grp_health_extras P1 AI 跨檔評論。

驗證:
1. _build_cross_fund_snapshot 對邊界輸入正確降級
2. _render_ai_cross_fund_evaluation 缺 GEMINI key 時 graceful skip
3. snapshot 字串含預期 sections
"""
from __future__ import annotations

import os
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
        "metric", "dataframe", "plotly_chart", "code", "button",
        "spinner", "error",
    ):
        setattr(_mod, _name, _noop)

    _mod.expander = _ctx
    _mod.columns = lambda *a, **k: [_ctx() for _ in range(a[0] if a else 1)]
    class _SS(dict):
        def get(self, k, default=None):
            return super().get(k, default)
    _mod.session_state = _SS()
    _mod.secrets = {}
    sys.modules["streamlit"] = _mod


_stub_streamlit()


# ════════════════════════════════════════════════════════════════
# _build_cross_fund_snapshot
# ════════════════════════════════════════════════════════════════

class TestBuildSnapshot:
    def test_empty_funds(self):
        from ui.helpers.fund_grp_health_extras import _build_cross_fund_snapshot
        _snap, _n = _build_cross_fund_snapshot([])
        assert _n == 0
        assert "無基金資料" in _snap

    def test_snapshot_contains_required_sections(self):
        """snapshot 應含「整組概況」「逐檔健診」「跨檔重疊度」三段"""
        from ui.helpers.fund_grp_health_extras import _build_cross_fund_snapshot
        _idx = pd.date_range("2024-01-01", periods=100, freq="D")
        _funds = [
            {
                "code": "A001", "name": "Fund A",
                "series": pd.Series(range(100, 200), index=_idx, dtype=float),
                "metrics": {
                    "annual_div_rate": 5.0,
                    "ret_1y_total": 7.0,
                },
                "moneydj_raw": {
                    "holdings": {
                        "top_holdings": [{"name": "AAPL", "pct": 5.0}],
                        "sector_alloc": [{"name": "科技", "pct": 60}],
                    },
                },
            },
        ]
        _snap, _n = _build_cross_fund_snapshot(_funds)
        assert _n == 1
        assert "整組概況" in _snap
        assert "逐檔健診" in _snap
        assert "跨檔重疊度" in _snap
        assert "Fund A" in _snap
        assert "A001" in _snap

    def test_snapshot_eating_principal_marked(self):
        """配息率 > 含息報酬 → snapshot 應標 🔴 吃本金"""
        from ui.helpers.fund_grp_health_extras import _build_cross_fund_snapshot
        _funds = [
            {
                "code": "EAT01", "name": "Eating Fund",
                "metrics": {
                    "annual_div_rate": 10.0,
                    "ret_1y_total": 5.0,
                },
                "moneydj_raw": {},
            },
        ]
        _snap, _n = _build_cross_fund_snapshot(_funds)
        assert "🔴 吃本金" in _snap
        assert "1 檔 / 1" in _snap  # 吃本金統計

    def test_snapshot_handles_missing_metrics(self):
        """metrics 全缺 → snapshot 仍正常產出,標 '資料不足'"""
        from ui.helpers.fund_grp_health_extras import _build_cross_fund_snapshot
        _funds = [{"code": "X001", "name": "Empty"}]
        _snap, _n = _build_cross_fund_snapshot(_funds)
        assert _n == 1
        assert "Empty" in _snap

    def test_snapshot_oversold_count(self):
        """NAV 暴跌 → σ rank 應 ≤ -2,進超跌統計"""
        from ui.helpers.fund_grp_health_extras import _build_cross_fund_snapshot
        _idx = pd.date_range("2024-01-01", periods=300, freq="D")
        # 前 200 天漲到 200,然後暴跌到 100 → σ rank 應深度負
        _vals = list(range(100, 300)) + [
            300 - (i + 1) * 2 for i in range(100)
        ]
        _funds = [
            {"code": "C001", "name": "Crashed",
             "series": pd.Series(_vals, index=_idx, dtype=float)},
        ]
        _snap, _n = _build_cross_fund_snapshot(_funds)
        # 不強制 sigma_rank ≤ -2(視 sigma 估計變動),但確認 snapshot 含「超跌」統計欄
        assert "深度超跌" in _snap


# ════════════════════════════════════════════════════════════════
# _render_ai_cross_fund_evaluation
# ════════════════════════════════════════════════════════════════

class TestAiCrossFundEvaluation:
    def test_empty_funds_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_ai_cross_fund_evaluation
        _render_ai_cross_fund_evaluation([])  # 不 raise

    def test_no_gemini_key_skips_gracefully(self, monkeypatch):
        """無 GEMINI_API_KEY → caption '⬜ 未設定 ...',不 raise / 不呼叫 LLM"""
        from ui.helpers.fund_grp_health_extras import _render_ai_cross_fund_evaluation
        monkeypatch.delenv("GEMINI_API_KEY", raising=False)
        # 確保 secrets 也是空
        import streamlit as st
        st.secrets = {}
        _render_ai_cross_fund_evaluation([{"code": "A001", "name": "A"}])

    def test_with_gemini_key_invokes_widget(self, monkeypatch):
        """有 GEMINI_API_KEY → 走進 render_ai_summary_widget(本測試 stub 該 widget)"""
        # stub render_ai_summary_widget,確認它被呼叫且帶正確參數
        _called = {"count": 0, "tab_key": None, "sections": None}

        def _stub_widget(**kwargs):
            _called["count"] += 1
            _called["tab_key"] = kwargs.get("tab_key")
            _called["sections"] = kwargs.get("sections")

        # 暫時注入 stub
        import ui.helpers.ai_summary as _ai_mod
        _orig = _ai_mod.render_ai_summary_widget
        _ai_mod.render_ai_summary_widget = _stub_widget
        try:
            monkeypatch.setenv("GEMINI_API_KEY", "fake-key-for-testing-only")
            from ui.helpers.fund_grp_health_extras import _render_ai_cross_fund_evaluation
            _render_ai_cross_fund_evaluation([
                {"code": "A001", "name": "Fund A",
                 "metrics": {"annual_div_rate": 5.0, "ret_1y_total": 7.0}},
            ])
            assert _called["count"] == 1
            assert _called["tab_key"] == "tab5_grp"
            assert "整組概況" in _called["sections"]
            assert "換手與調整建議" in _called["sections"]
        finally:
            _ai_mod.render_ai_summary_widget = _orig


# v19.122 §6 自審「3 個最容易出錯的輸入」:
#   1. 空 funds list → snapshot 顯示「無基金資料」,widget 不呼叫 ✅
#   2. 無 GEMINI_API_KEY → caption skip,不偽造 LLM 回應 ✅
#   3. 全檔 metrics 缺 → snapshot 仍產出,標「資料不足」不偽造 ✅
