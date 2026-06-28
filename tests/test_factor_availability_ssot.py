"""v19.193 SSOT 對齊 regression — get_factor_availability() vs calc_fund_factor_score。

歷史病灶(v19.191 Tab2 進階指標面板用 inline 邏輯):
- `mgmt_fee="N/A"` → UI ✅ 但 SSOT float 失敗 ❌(走岔)
- `metrics.expense_ratio=0` → UI 走 fallback(0 是 falsy)但 SSOT 視為合法 ✅
- `tr1y="abc"` → UI ✅(只看 is not None)但 SSOT float 失敗 ❌
- `annual_div_rate=None` 但 tr1y=5.2 → UI ❌(雙條件)但 SSOT adr 預設 0 → ✅

守住:get_factor_availability(fd)[F] == True ↔ calc_fund_factor_score(fd).factors 含 F
"""
from __future__ import annotations

import pytest

from services.portfolio_service import (
    calc_fund_factor_score,
    get_factor_availability,
)


def _factor_in_score(fund_data: dict, factor: str, **kwargs) -> bool:
    """SSOT 寫入端是否真的把 factor 納入 calc_fund_factor_score 結果。"""
    out = calc_fund_factor_score(fund_data, **kwargs)
    return factor in (out.get("factors") or {})


class TestExpenseRatioEdgeCasesV193:
    def test_mgmt_fee_NA_string_not_parsable(self):
        """mgmt_fee='N/A' 不可解析為 float → 兩端都 ❌(歷史 UI ✅ 漂移)。"""
        fd = {
            "metrics": {"expense_ratio": None},
            "moneydj_raw": {"mgmt_fee": "N/A"},
        }
        avail = get_factor_availability(fd)
        assert avail["ExpenseRatio"] is False, (
            "mgmt_fee='N/A' float 解析失敗 → factor 不應納入,SSOT 對齊"
        )
        assert _factor_in_score(fd, "ExpenseRatio") is False, (
            "calc_fund_factor_score 也不應納入 N/A,確保 SSOT 一致"
        )

    def test_expense_ratio_zero_is_valid(self):
        """metrics.expense_ratio=0(免管理費基金)是合法值 → 應納入(歷史 UI ❌ 漂移)。"""
        fd = {
            "metrics": {"expense_ratio": 0},
            "moneydj_raw": {"mgmt_fee": "N/A"},
        }
        avail = get_factor_availability(fd)
        assert avail["ExpenseRatio"] is True, (
            "expense_ratio=0(免費)應視為合法 factor,而非 falsy 略過"
        )
        assert _factor_in_score(fd, "ExpenseRatio") is True

    def test_mgmt_fee_fallback_with_percent(self):
        """metrics.expense_ratio=None,mgmt_fee='1.5%' 走 fallback → ✅。"""
        fd = {
            "metrics": {"expense_ratio": None},
            "moneydj_raw": {"mgmt_fee": "1.5%"},
        }
        avail = get_factor_availability(fd)
        assert avail["ExpenseRatio"] is True
        assert _factor_in_score(fd, "ExpenseRatio") is True

    def test_expense_ratio_arg_priority(self):
        """expense_ratio 參數優先於 metrics.expense_ratio。"""
        fd = {"metrics": {"expense_ratio": None}, "moneydj_raw": {}}
        avail = get_factor_availability(fd, expense_ratio=2.0)
        assert avail["ExpenseRatio"] is True


class TestAlphaEdgeCasesV193:
    def test_alpha_with_adr_none_only_needs_tr1y(self):
        """adr=None 但 tr1y 合法 → adr 預設 0,factor 應納入(歷史 UI ❌ 漂移)。"""
        fd = {
            "perf": {"1Y": 5.2},
            "metrics": {"annual_div_rate": None},
            "moneydj_raw": {},
        }
        avail = get_factor_availability(fd)
        assert avail["Alpha"] is True, (
            "Alpha SSOT 只需 tr1y 可解析,adr 預設 0;UI 不應強求 annual_div_rate"
        )
        assert _factor_in_score(fd, "Alpha") is True

    def test_alpha_with_non_numeric_tr1y(self):
        """tr1y='abc' 不可解析 → factor 不應納入(歷史 UI ✅ 漂移)。"""
        fd = {
            "perf": {"1Y": "abc"},
            "metrics": {"annual_div_rate": 3.0},
            "moneydj_raw": {},
        }
        avail = get_factor_availability(fd)
        assert avail["Alpha"] is False, (
            "tr1y='abc' float 失敗 → 不應 ✅,即使 is not None 為 True"
        )
        assert _factor_in_score(fd, "Alpha") is False

    def test_alpha_with_no_tr1y(self):
        fd = {"perf": {}, "metrics": {"annual_div_rate": 3.0}, "moneydj_raw": {}}
        avail = get_factor_availability(fd)
        assert avail["Alpha"] is False


class TestSortinoCalmarV193:
    def test_sortino_present(self):
        fd = {"metrics": {"sortino": 1.2}}
        avail = get_factor_availability(fd)
        assert avail["Sortino"] is True
        assert _factor_in_score(fd, "Sortino") is True

    def test_sortino_missing(self):
        fd = {"metrics": {}}
        avail = get_factor_availability(fd)
        assert avail["Sortino"] is False
        assert _factor_in_score(fd, "Sortino") is False

    def test_calmar_non_numeric(self):
        fd = {"metrics": {"calmar": "—"}}
        avail = get_factor_availability(fd)
        assert avail["Calmar"] is False


class TestSharpeMaxDDDefaultsV193:
    """SSOT 中 Sharpe / MaxDD 走 `or 0` 預設 → availability 永遠 True(除非源是 non-numeric string)。

    本組 test 鎖定這個「`or 0` 預設行為」的 SSOT 對齊,避免未來重構時走岔。"""

    def test_sharpe_defaults_to_zero(self):
        fd = {"metrics": {}}
        avail = get_factor_availability(fd)
        assert avail["Sharpe"] is True, "Sharpe SSOT 用 `or 0` → 永遠可納入"
        assert _factor_in_score(fd, "Sharpe") is True

    def test_sharpe_non_numeric_string_fails(self):
        fd = {"metrics": {"sharpe": "abc"}}
        avail = get_factor_availability(fd)
        assert avail["Sharpe"] is False
        assert _factor_in_score(fd, "Sharpe") is False

    def test_maxdd_defaults_via_zero_string(self):
        fd = {"metrics": {}}
        avail = get_factor_availability(fd)
        assert avail["MaxDrawdown"] is True


class TestSSotConsistencyV193:
    """跨 factor 整體對齊 — 任何 fund_data:availability 集合 == calc factor 集合。"""

    @pytest.mark.parametrize("fd", [
        {"metrics": {"sortino": 1.0, "calmar": 0.5, "max_drawdown": -8.0},
         "perf": {"1Y": 7.5}, "moneydj_raw": {"mgmt_fee": "0.8%"}},
        {"metrics": {"sharpe": 1.5}, "perf": {}, "moneydj_raw": {}},
        {"metrics": {"sharpe": "abc"}, "perf": {"1Y": "abc"},
         "moneydj_raw": {"mgmt_fee": "N/A"}},
        {"metrics": {"expense_ratio": 0, "sortino": None}, "perf": {"1Y": 3.2},
         "moneydj_raw": {}},
    ])
    def test_availability_matches_calc_factors(self, fd):
        avail = get_factor_availability(fd)
        out = calc_fund_factor_score(fd)
        calc_factors = set(out.get("factors") or {})
        avail_factors = {k for k, v in avail.items() if v}
        assert avail_factors == calc_factors, (
            f"SSOT 漂移:availability={avail_factors} vs calc={calc_factors}, fd={fd}"
        )
