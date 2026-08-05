"""v19.191 regression — calc_metrics 必須產出 sortino / calmar SSOT。

根因(user 螢幕截圖回報):進階指標面板 Sortino / Calmar / 費用率 全顯示「—」。
追查發現 `services/fund_service.py:calc_metrics` 從沒寫過這三欄,
caller `services/portfolio_service.py:calc_fund_factor_score` 永遠拿不到。

守住:
- calc_metrics 對足夠長的 NAV 序列必算 sortino + calmar
- 短歷史 → 兩者 None(§1 Fail Loud,不偽造)
- expense_ratio 走 portfolio_service 的 mgmt_fee 第 3 fallback

**P0-3 樣本門檻更新**(原門檻 60 筆 = ≈3 個月,卻掛在「1Y」欄位旁):
- sharpe / sortino:≥ MIN_OBS_SHARPE_SORTINO(250 交易日)
- max_drawdown    :≥ MIN_OBS_MAX_DRAWDOWN(125)
- calmar          :≥ MIN_OBS_CALMAR(756 = Young 1991 的 36 個月),**取消 1Y fallback**
不足一律 None + `risk_metric_meta[<指標>]["reason"]` 原因字串。
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

    def test_calmar_computed_when_full_3y_present(self):
        """P0-4:Calmar 需滿 3Y(756 交易日,Young 1991)。800 筆 → 算得出。"""
        from services.fund_service import calc_metrics, MIN_OBS_CALMAR
        s = _make_nav_series(MIN_OBS_CALMAR + 50)
        m = calc_metrics(s, divs=[])
        assert m.get("max_drawdown") is not None
        assert m.get("calmar") is not None, "滿 3Y 應算得 calmar"
        _meta = m["risk_metric_meta"]["calmar"]
        assert _meta["source"] == "self_calc"
        assert _meta["period_days"] == MIN_OBS_CALMAR
        assert _meta["max_dd_3y_pct"] is not None

    def test_calmar_none_without_3y_history_no_1y_fallback(self):
        """P0-4 核心:不足 3Y **不得**走 1Y fallback(Calmar_1Y ≥ Calmar_3Y 恆成立,
        同表混排不可比)→ None + 樣本不足原因字串。"""
        from services.fund_service import calc_metrics, MIN_OBS_CALMAR
        s = _make_nav_series(300)          # 1Y+ 但 << 3Y
        m = calc_metrics(s, divs=[])
        assert m.get("calmar") is None, "不足 3Y 不可用 1Y fallback 硬算 Calmar"
        assert m.get("calmar_source") is None
        _r = m["risk_metric_meta"]["calmar"]["reason"]
        assert _r and "樣本不足" in _r and f"/{MIN_OBS_CALMAR}" in _r, _r

    def test_short_series_sortino_calmar_none(self):
        """遠低於門檻 → sortino / calmar / max_drawdown 全 None + 原因字串。"""
        from services.fund_service import calc_metrics
        s = _make_nav_series(40)
        m = calc_metrics(s, divs=[])
        assert m.get("sortino") is None, "樣本不足 sortino 必須 None(不可偽造)"
        assert m.get("calmar") is None
        assert m.get("max_drawdown") is None, "40 筆 < 125 → MaxDD 也不給"
        _meta = m["risk_metric_meta"]
        for _k in ("sortino", "max_drawdown", "calmar"):
            assert "樣本不足" in (_meta[_k]["reason"] or ""), (_k, _meta[_k])

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
        from services.fund_service import calc_metrics, MIN_OBS_CALMAR
        # P0-4:Calmar 需滿 3Y → e2e 樣本從 300 調到 756+(原 300 走的是已取消的
        # 1Y fallback 路徑,不是真 Calmar)。
        s = _make_nav_series(MIN_OBS_CALMAR + 50)
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
