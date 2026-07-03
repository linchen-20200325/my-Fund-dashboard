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


# v19.174:module-top stub call 拿掉 — 改由 conftest._switch_streamlit_module_per_test
# fixture per-test 裝(避免 stub 污染後續 collect 的 test,例如 AppTest)。
# _stub_streamlit()


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


class TestThreeRatioScanBoundedTime:
    """v19.301 回歸網:掃描不因單一 yfinance hang 卡死整個畫面。

    根因(user 2026-07-03「壓一下畫面會整個不見」):舊版按鈕會逐檔**同步**
    連打 N 檔 yfinance,每檔無 timeout → 10 檔 × 5-10s(或 hang)卡死主執行緒
    → Streamlit websocket 斷線、整頁空白。修法:並行 + as_completed(timeout=
    deadline) + shutdown(wait=False),逾時用已完成部分,不等 hang 的執行緒。

    本測試把每檔 fetch 故意 sleep 到遠超 deadline,驗證整個 render **總耗時被
    deadline 約束**(而非 N × sleep 的線性累加),且不拋例外。
    """

    def test_hanging_fetch_does_not_block_whole_scan(self, monkeypatch):
        import time as _time

        import streamlit as _st

        # 觸發掃描:按鈕回 True
        monkeypatch.setattr(_st, "button", lambda *a, **k: True)

        # 提供有 .progress()/.empty() 的 progress 替身(conftest 預設 stub 沒有)
        class _FakeProg:
            def progress(self, *a, **k):
                return None

            def empty(self):
                return None

        monkeypatch.setattr(_st, "progress", lambda *a, **k: _FakeProg())

        # 把 deadline 壓低,fetch 故意 hang 遠超 deadline
        import ui.helpers.fund_grp_health.ai as _ai_mod
        monkeypatch.setattr(_ai_mod, "_THREE_RATIO_SCAN_DEADLINE_SEC", 0.6)

        _HANG_SEC = 3.0

        from services import precision_service as _ps

        def _hang(self, stock_name):
            _time.sleep(_HANG_SEC)
            return None

        monkeypatch.setattr(
            _ps.PrecisionStrategyEngine, "fetch_stock_three_ratios", _hang,
        )

        _funds = [
            {
                "code": "H001", "name": "Hang Fund",
                "moneydj_raw": {"holdings": {
                    "top_holdings": [
                        {"name": "AAPL", "pct": 5.0},
                        {"name": "MSFT", "pct": 4.0},
                        {"name": "TSMC", "pct": 8.0},
                    ],
                }},
            },
        ]

        from ui.helpers.fund_grp_health_extras import (
            _render_per_fund_three_ratio_expanders,
        )

        _t0 = _time.monotonic()
        # 不該拋例外(§1 Fail Loud — 部分/零結果照顯示,不炸整個 tab)
        _render_per_fund_three_ratio_expanders(_funds)
        _elapsed = _time.monotonic() - _t0

        # 舊版逐檔同步 = 3 × 3.0s = 9s;新版被 deadline(0.6s)約束 → 應 < 2.5s
        assert _elapsed < 2.5, (
            f"掃描應被 deadline 約束(~0.6s),實際耗時 {_elapsed:.2f}s —— "
            f"疑似退回逐檔同步阻塞(舊版會卡 ~9s,正是整頁空白根因)"
        )


# v19.123 §6 自審「3 個最容易出錯的輸入」:
#   1. 空 funds / 無持股 → graceful skip,不抓 API ✅
#   2. 有持股但按鈕未點 → 不該觸發 fetch(lazy 守衛 monkeypatch 確認 count=0)✅
#   3. 同 code 在 Tab 2 已存 session_state → Tab 5 不該蓋過(namespace 隔離守衛)✅
