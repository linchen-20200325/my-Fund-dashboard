"""v19.191 regression — calc_metrics 必須產出 sortino / calmar SSOT。

根因(user 螢幕截圖回報):進階指標面板 Sortino / Calmar / 費用率 全顯示「—」。
追查發現 `services/fund_service.py:calc_metrics` 從沒寫過這三欄,
caller `services/portfolio_service.py:calc_fund_factor_score` 永遠拿不到。

守住:
- calc_metrics 對 ≥60 筆 NAV 序列必算 sortino + calmar
- 短歷史(< 60 筆)→ 兩者 None(§1 Fail Loud,不偽造)
- expense_ratio 走 portfolio_service 的 mgmt_fee 第 3 fallback
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


def _make_nav_series(n_days: int, seed: int = 42, mu: float = 0.0003, sigma: float = 0.01):
    """合成 NAV 序列(常態 log return,複利)。"""
    rng = np.random.default_rng(seed)
    log_r = rng.normal(mu, sigma, n_days)
    nav = 10.0 * np.exp(np.cumsum(log_r))
    idx = pd.date_range("2020-01-01", periods=n_days, freq="B")
    return pd.Series(nav, index=idx)


class TestSortinoCalmarSSOTV191:
    def test_sortino_computed_for_long_series(self):
        from services.fund_service import calc_metrics
        s = _make_nav_series(300)
        m = calc_metrics(s, divs=[])
        assert m.get("sortino") is not None, (
            "v19.191: NAV ≥ 60 筆 + 含負報酬 應算得 sortino"
        )
        assert isinstance(m["sortino"], float)

    def test_calmar_computed_when_3y_or_1y_present(self):
        from services.fund_service import calc_metrics
        s = _make_nav_series(300)
        m = calc_metrics(s, divs=[])
        # max_dd 永遠存在(非零波動);1Y 報酬也應存在
        assert m.get("max_drawdown") is not None
        assert m.get("calmar") is not None, (
            "v19.191: 1Y 報酬 + max_dd 都有 應算得 calmar"
        )

    def test_short_series_sortino_calmar_none(self):
        """< 60 筆 → sortino None;若 sharpe 也算不出 → calmar 也 None 為合理。"""
        from services.fund_service import calc_metrics
        s = _make_nav_series(40)
        m = calc_metrics(s, divs=[])
        assert m.get("sortino") is None, (
            "v19.191: < 60 筆 sortino 必須 None(不可偽造)"
        )

    def test_sortino_calmar_in_return_schema(self):
        """schema 守:return dict 必須有 sortino + calmar key(即使值 None)。"""
        from services.fund_service import calc_metrics
        s = _make_nav_series(80)
        m = calc_metrics(s, divs=[])
        assert "sortino" in m, "v19.191 SSOT: calc_metrics 必須 expose sortino 欄位"
        assert "calmar" in m, "v19.191 SSOT: calc_metrics 必須 expose calmar 欄位"


class TestExpenseRatioMgmtFeeFallbackV191:
    """v19.191 portfolio_service.calc_fund_factor_score 第 3 fallback。"""

    def test_mgmt_fee_string_fallback(self):
        from services.portfolio_service import calc_fund_factor_score
        # metrics 無 expense_ratio,但 moneydj_raw.mgmt_fee 有
        fund_data = {
            "metrics": {"sharpe": 1.0, "max_drawdown": -10.0},
            "perf": {"1Y": 8.0},
            "moneydj_raw": {"mgmt_fee": "1.50"},
        }
        result = calc_fund_factor_score(fund_data)
        factors = result["factors"]
        assert "ExpenseRatio" in factors, (
            "v19.191: mgmt_fee 字串應 fallback parse 出 expense_ratio"
        )
        assert factors["ExpenseRatio"]["value"] == 1.5

    def test_mgmt_fee_with_percent_sign_parsed(self):
        from services.portfolio_service import calc_fund_factor_score
        fund_data = {
            "metrics": {"sharpe": 1.0, "max_drawdown": -10.0},
            "perf": {"1Y": 8.0},
            "moneydj_raw": {"mgmt_fee": "0.80%"},
        }
        result = calc_fund_factor_score(fund_data)
        assert result["factors"]["ExpenseRatio"]["value"] == 0.8

    def test_explicit_expense_ratio_wins_over_mgmt_fee(self):
        """SSOT 優先序:expense_ratio (arg) > metrics.expense_ratio > mgmt_fee。"""
        from services.portfolio_service import calc_fund_factor_score
        fund_data = {
            "metrics": {"sharpe": 1.0, "max_drawdown": -10.0, "expense_ratio": 0.5},
            "perf": {"1Y": 8.0},
            "moneydj_raw": {"mgmt_fee": "2.00"},  # 應被 metrics.expense_ratio 蓋掉
        }
        result = calc_fund_factor_score(fund_data)
        assert result["factors"]["ExpenseRatio"]["value"] == 0.5, (
            "metrics.expense_ratio 應贏過 mgmt_fee"
        )

    def test_mgmt_fee_invalid_falls_through_to_none(self):
        from services.portfolio_service import calc_fund_factor_score
        fund_data = {
            "metrics": {"sharpe": 1.0, "max_drawdown": -10.0},
            "perf": {"1Y": 8.0},
            "moneydj_raw": {"mgmt_fee": "N/A"},
        }
        result = calc_fund_factor_score(fund_data)
        # mgmt_fee parse 失敗 → ExpenseRatio 不出現(Fail Loud,不偽造 0)
        assert "ExpenseRatio" not in result["factors"]


class TestEndToEndAdvancedIndicatorsV191:
    """v19.191 e2e:fund_service 算出 sortino/calmar → fund_health_report 抓得到。"""

    def test_advanced_indicators_flow_into_health_row(self):
        from services.health.report import build_health_analysis_row
        from services.fund_service import calc_metrics
        s = _make_nav_series(300)
        m = calc_metrics(s, divs=[])
        fd = {
            "moneydj_raw": {"perf": {"1Y": 8.0}, "mgmt_fee": "1.20"},
            "metrics": m,
            "series": s,
        }
        row = build_health_analysis_row(fd, "TESTFUND")
        # v19.191 三 SSOT 補洞應一起讓 row 拿得到值
        assert row["Sortino"] is not None, "v19.191 e2e: sortino 應流到 health row"
        assert row["Calmar"] is not None, "v19.191 e2e: calmar 應流到 health row"
        assert row["費用率 %"] == 1.2, "v19.191 e2e: mgmt_fee → 費用率 應流到 health row"


class TestComputeHoldingYearsSeriesTruthValueBugV191:
    """v19.191 bug fix:`fd.get("series") or fallback` 觸發 Series.__bool__ ValueError。

    根因:pandas Series 在 boolean context 會 raise
    『The truth value of a Series is ambiguous』。
    `fd.get("series") or other` 在 series 是非空 Series 時就會炸,
    except 吞掉 → _compute_holding_years 永遠回 None → MK 3-3-3 全站「資料不足」。
    """

    def test_non_empty_series_does_not_raise(self):
        """非空 Series 應正常算 holding_years,不可走 except 吞掉。"""
        from services.health.report import _compute_holding_years
        s = _make_nav_series(800)  # ~3.2 年
        fd = {"series": s}
        y = _compute_holding_years(fd)
        assert y is not None, "v19.191: 非空 Series 應算得 holding_years"
        assert y > 3.0, f"800 個交易日應 > 3 年,實際 {y}"

    def test_none_series_returns_none_not_raise(self):
        from services.health.report import _compute_holding_years
        assert _compute_holding_years({}) is None
        assert _compute_holding_years({"series": None}) is None

    def test_moneydj_raw_series_fallback_works(self):
        """series 在 moneydj_raw 內也應 fallback。"""
        from services.health.report import _compute_holding_years
        s = _make_nav_series(400)
        fd = {"moneydj_raw": {"series": s}}
        y = _compute_holding_years(fd)
        assert y is not None, "v19.191: moneydj_raw.series fallback 應動"
