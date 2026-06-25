"""v19.123 tests — fund_grp_health_extras P1 個股新聞 + 三率穿透。

驗證:
1. 空 / 無持股 → graceful skip,不抓 API
2. 按鈕未點 → 顯示提示文字,不觸發抓取
3. session_state 命名空間隔離(tab5_grp 前綴,不撞 Tab 2 既有 key)

關鍵設計:lazy fetch — 即使有持股,init 也不應觸發 fetch_stock_news / 三率掃描。
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

    def _button(*a, **k):
        # 預設不點 → 回 False;測試需要點按時透過 monkeypatch 覆寫
        return False

    def _progress(*a, **k):
        class _P:
            def progress(self, *aa, **kk):
                return None
            def empty(self):
                return None
        return _P()

    for _name in (
        "markdown", "caption", "divider", "info", "success", "warning",
        "metric", "dataframe", "plotly_chart", "code", "error",
    ):
        setattr(_mod, _name, _noop)

    def _columns(*a, **k):
        if a:
            spec = a[0]
            n = len(spec) if isinstance(spec, (list, tuple)) else int(spec)
        else:
            n = 1
        return [_ctx() for _ in range(n)]

    _mod.expander = _ctx
    _mod.columns = _columns
    _mod.button = _button
    _mod.progress = _progress
    _mod.spinner = _ctx

    class _SS(dict):
        def get(self, k, default=None):
            return super().get(k, default)
    _mod.session_state = _SS()
    sys.modules["streamlit"] = _mod


_stub_streamlit()


# ════════════════════════════════════════════════════════════════
# _render_per_fund_news_expanders
# ════════════════════════════════════════════════════════════════

class TestPerFundNewsExpanders:
    def test_empty_funds_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_per_fund_news_expanders
        _render_per_fund_news_expanders([])

    def test_fund_without_holdings_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_per_fund_news_expanders
        _render_per_fund_news_expanders([{"code": "A001", "name": "A", "moneydj_raw": {}}])

    def test_fund_with_holdings_does_not_auto_fetch(self, monkeypatch):
        """Lazy 守衛:即使有持股,init 不該呼叫 fetch_stock_news(按鈕沒點)"""
        _called = {"count": 0}

        def _fake_fetch(query, max_items=3):
            _called["count"] += 1
            return []

        monkeypatch.setattr(
            "repositories.news_repository.fetch_stock_news", _fake_fetch,
        )
        from ui.helpers.fund_grp_health_extras import _render_per_fund_news_expanders
        _funds = [
            {
                "code": "A001", "name": "A",
                "moneydj_raw": {"holdings": {
                    "top_holdings": [
                        {"name": "AAPL", "pct": 5.0},
                        {"name": "MSFT", "pct": 4.0},
                    ],
                }},
            },
        ]
        _render_per_fund_news_expanders(_funds)
        assert _called["count"] == 0, (
            f"按鈕未點不該抓 API,實際抓了 {_called['count']} 次"
        )

    def test_multiple_funds_lazy(self, monkeypatch):
        """多檔基金也不該觸發任何抓取"""
        _called = {"count": 0}

        def _fake_fetch(query, max_items=3):
            _called["count"] += 1
            return []

        monkeypatch.setattr(
            "repositories.news_repository.fetch_stock_news", _fake_fetch,
        )
        from ui.helpers.fund_grp_health_extras import _render_per_fund_news_expanders
        _funds = [
            {"code": f"A{i:03d}", "name": f"F{i}",
             "moneydj_raw": {"holdings": {
                 "top_holdings": [{"name": f"S{j}", "pct": 5} for j in range(6)],
             }}}
            for i in range(5)
        ]
        _render_per_fund_news_expanders(_funds)
        assert _called["count"] == 0


# ════════════════════════════════════════════════════════════════
# _render_per_fund_three_ratio_expanders
# ════════════════════════════════════════════════════════════════

class TestPerFundThreeRatioExpanders:
    def test_empty_funds_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_per_fund_three_ratio_expanders
        _render_per_fund_three_ratio_expanders([])

    def test_fund_without_holdings_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_per_fund_three_ratio_expanders
        _render_per_fund_three_ratio_expanders([{"code": "A001", "moneydj_raw": {}}])

    def test_fund_with_holdings_does_not_auto_scan(self, monkeypatch):
        """Lazy 守衛:有持股但按鈕未點,不該呼叫 fetch_stock_three_ratios"""
        _called = {"count": 0}

        # 攔截 PrecisionStrategyEngine.fetch_stock_three_ratios
        from services import precision_service as _ps

        _orig = _ps.PrecisionStrategyEngine.fetch_stock_three_ratios

        def _fake(self, stock_name):
            _called["count"] += 1
            return None

        monkeypatch.setattr(
            _ps.PrecisionStrategyEngine,
            "fetch_stock_three_ratios",
            _fake,
        )
        from ui.helpers.fund_grp_health_extras import _render_per_fund_three_ratio_expanders
        _funds = [
            {
                "code": "A001", "name": "A",
                "moneydj_raw": {"holdings": {
                    "top_holdings": [
                        {"name": "AAPL", "pct": 5.0},
                        {"name": "TSMC", "pct": 8.0},
                    ],
                }},
            },
        ]
        _render_per_fund_three_ratio_expanders(_funds)
        assert _called["count"] == 0, (
            f"按鈕未點不該掃 yfinance,實際掃了 {_called['count']} 次"
        )

    def test_session_state_namespace_isolated(self):
        """命名空間守衛:本 helper 用 _tab5grp_ 前綴,不撞 Tab 2 既有 shield_/_stknews_"""
        import streamlit as st
        st.session_state.clear()
        # 模擬 Tab 2 寫過的 key
        st.session_state["shield_ACCP138"] = ["tab2 cached data"]
        st.session_state["_stknews_ACCP138"] = {"tab2": "cache"}

        from ui.helpers.fund_grp_health_extras import (
            _render_per_fund_news_expanders,
            _render_per_fund_three_ratio_expanders,
        )
        _funds = [
            {
                "code": "ACCP138", "name": "Tab2 Same Code",
                "moneydj_raw": {"holdings": {
                    "top_holdings": [{"name": "AAPL", "pct": 5}],
                }},
            },
        ]
        _render_per_fund_news_expanders(_funds)
        _render_per_fund_three_ratio_expanders(_funds)

        # Tab 2 既有 key 必須完整保留
        assert st.session_state.get("shield_ACCP138") == ["tab2 cached data"]
        assert st.session_state.get("_stknews_ACCP138") == {"tab2": "cache"}


# v19.123 §6 自審「3 個最容易出錯的輸入」:
#   1. 空 funds / 無持股 → graceful skip,不抓 API ✅
#   2. 有持股但按鈕未點 → 不該觸發 fetch(lazy 守衛 monkeypatch 確認 count=0)✅
#   3. 同 code 在 Tab 2 已存 session_state → Tab 5 不該蓋過(namespace 隔離守衛)✅
