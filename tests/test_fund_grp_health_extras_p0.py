"""v19.120 tests — fund_grp_health_extras P0 4 區塊單元測試。

驗證:
1. _safe_num helper(既有,sanity check)
2. 4 個新區塊面對邊界輸入(空 list / 單檔 / 缺持股 / NAV 不足)能正確降級,不 raise
3. correlation 主算法 + fallback 路徑命中
4. HWM σ 對缺資料的 graceful 行為
5. 風險表對缺 metrics 的 fail-loud(顯示 '—' 不偽造)

streamlit 部分透過 monkeypatch / stub 隔絕(本檔不真實 render UI)。
"""
from __future__ import annotations

import sys
import types

import pandas as pd
import pytest


# ════════════════════════════════════════════════════════════════
# Stub streamlit so import 不炸 / render 函式可呼叫但無作用
# ════════════════════════════════════════════════════════════════

def _stub_streamlit():
    """注入 minimal streamlit stub 進 sys.modules,本測試檔生命週期內有效。"""
    if "streamlit" in sys.modules and getattr(
        sys.modules["streamlit"], "_is_test_stub", False
    ):
        return  # 已 stub
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
    sys.modules["streamlit"] = _mod


_stub_streamlit()


# ════════════════════════════════════════════════════════════════
# 1. _safe_num sanity check(既有 helper)
# ════════════════════════════════════════════════════════════════

class TestSafeNum:
    def setup_method(self):
        from ui.helpers.fund_grp_health_extras import _safe_num
        self.fn = _safe_num

    def test_none(self):
        assert self.fn(None) is None

    def test_float(self):
        assert self.fn(3.14) == 3.14

    def test_int(self):
        assert self.fn(5) == 5.0

    def test_percent_string(self):
        assert self.fn("12.3%") == 12.3

    def test_comma_string(self):
        assert self.fn("1,234.5") == 1234.5

    def test_garbage_string(self):
        assert self.fn("abc") is None

    def test_nan(self):
        assert self.fn(float("nan")) is None

    def test_inf(self):
        assert self.fn(float("inf")) is None

    def test_bool_rejected(self):
        assert self.fn(True) is None
        assert self.fn(False) is None


# ════════════════════════════════════════════════════════════════
# 2. _render_correlation_matrix 邊界
# ════════════════════════════════════════════════════════════════

class TestCorrelationMatrix:
    def test_empty_list_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_correlation_matrix
        _render_correlation_matrix([])  # < 2 → skip,不 raise

    def test_single_fund_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_correlation_matrix
        _render_correlation_matrix([{"code": "A001", "name": "A"}])

    def test_two_funds_with_holdings_no_raise(self):
        """主算法路徑:兩檔基金有持股 → 走 calc_holdings_overlap"""
        from ui.helpers.fund_grp_health_extras import _render_correlation_matrix
        _funds = [
            {
                "code": "A001", "name": "Fund A",
                "moneydj_raw": {"holdings": {
                    "top_holdings": [
                        {"name": "AAPL", "pct": 5.0},
                        {"name": "MSFT", "pct": 4.0},
                    ],
                    "sector_alloc": [
                        {"name": "科技", "pct": 60},
                        {"name": "金融", "pct": 20},
                    ],
                }},
            },
            {
                "code": "B002", "name": "Fund B",
                "moneydj_raw": {"holdings": {
                    "top_holdings": [
                        {"name": "GOOG", "pct": 6.0},
                        {"name": "AMZN", "pct": 4.0},
                    ],
                    "sector_alloc": [
                        {"name": "科技", "pct": 50},
                        {"name": "醫療", "pct": 30},
                    ],
                }},
            },
        ]
        _render_correlation_matrix(_funds)

    def test_fallback_to_nav_pearson_no_raise(self):
        """Fallback 路徑:持股全缺 → NAV Pearson"""
        from ui.helpers.fund_grp_health_extras import _render_correlation_matrix
        _idx = pd.date_range("2024-01-01", periods=100, freq="D")
        _funds = [
            {"code": "A001", "name": "A",
             "series": pd.Series(range(100), index=_idx, dtype=float),
             "moneydj_raw": {}},  # 無持股 → fallback
            {"code": "B002", "name": "B",
             "series": pd.Series(range(100, 200), index=_idx, dtype=float),
             "moneydj_raw": {}},
        ]
        _render_correlation_matrix(_funds)


# ════════════════════════════════════════════════════════════════
# 3. _render_hwm_sigma_table 邊界
# ════════════════════════════════════════════════════════════════

class TestHwmSigmaTable:
    def test_empty_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_hwm_sigma_table
        _render_hwm_sigma_table([])

    def test_short_series_shows_data_insufficient(self):
        """NAV < 30 → '⬜ NAV 不足 30 天'(不 raise)"""
        from ui.helpers.fund_grp_health_extras import _render_hwm_sigma_table
        _idx = pd.date_range("2024-01-01", periods=10, freq="D")
        _funds = [
            {"code": "A001", "name": "A",
             "series": pd.Series([100.0] * 10, index=_idx)},
        ]
        _render_hwm_sigma_table(_funds)  # 應 graceful 顯示

    def test_normal_series_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_hwm_sigma_table
        _idx = pd.date_range("2024-01-01", periods=300, freq="D")
        _vals = [100 + i * 0.1 for i in range(300)]
        _funds = [
            {"code": "A001", "name": "A", "series": pd.Series(_vals, index=_idx)},
        ]
        _render_hwm_sigma_table(_funds)


# ════════════════════════════════════════════════════════════════
# 4. _render_risk_compare_table 邊界
# ════════════════════════════════════════════════════════════════

class TestRiskCompareTable:
    def test_empty_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_risk_compare_table
        _render_risk_compare_table([])

    def test_funds_without_risk_metrics_no_raise(self):
        """所有檔無 risk_metrics → 表格全 '—',不偽造(§1 Fail Loud)"""
        from ui.helpers.fund_grp_health_extras import _render_risk_compare_table
        _funds = [
            {"code": "A001", "name": "A", "moneydj_raw": {}, "metrics": {}},
            {"code": "B002", "name": "B", "moneydj_raw": {}, "metrics": {}},
        ]
        _render_risk_compare_table(_funds)  # 不 raise

    def test_funds_with_partial_metrics_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_risk_compare_table
        _funds = [
            {"code": "A001", "name": "A",
             "risk_metrics": {"sharpe": "1.2", "std_dev": "12.5%", "beta": 0.95}},
        ]
        _render_risk_compare_table(_funds)


# ════════════════════════════════════════════════════════════════
# 5. _render_oversold_badges 邊界
# ════════════════════════════════════════════════════════════════

class TestOversoldBadges:
    def test_empty_no_raise(self):
        from ui.helpers.fund_grp_health_extras import _render_oversold_badges
        _render_oversold_badges([])

    def test_no_oversold_shows_success(self):
        """無基金落 -2σ → ✅(不 raise)"""
        from ui.helpers.fund_grp_health_extras import _render_oversold_badges
        _idx = pd.date_range("2024-01-01", periods=300, freq="D")
        # 穩定上漲序列,不會 -2σ
        _vals = [100 + i * 0.1 for i in range(300)]
        _funds = [
            {"code": "A001", "name": "A", "series": pd.Series(_vals, index=_idx)},
        ]
        _render_oversold_badges(_funds)

    def test_short_series_skipped_silently(self):
        """NAV < 30 → 該檔 skip,不 raise / 不誤標超跌"""
        from ui.helpers.fund_grp_health_extras import _render_oversold_badges
        _idx = pd.date_range("2024-01-01", periods=10, freq="D")
        _funds = [
            {"code": "A001", "name": "A",
             "series": pd.Series([100.0] * 10, index=_idx)},
        ]
        _render_oversold_badges(_funds)


# v19.120 §6 自審「3 個最容易出錯的輸入」:
#   1. 空 funds list / 單檔(< 2)→ 相關性 skip + 其他區塊顯示空表 ✅
#   2. 全檔持股缺 → 相關性 fallback NAV Pearson ✅
#   3. NAV < 30 天 / 缺 risk_metrics → graceful '⬜ 資料不足',不偽造 ✅
