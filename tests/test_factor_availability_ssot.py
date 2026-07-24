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
    """Sharpe 與 MaxDrawdown 缺資料時皆**誠實不可用**(對齊其餘 4 因子)。

    v19.381 §1 除假:MaxDrawdown 原 `or "0"` 捏造 0% 回撤 = 假滿分,改 SSOT safe_num → 缺回 None。
    v19.397 §1 除假:Sharpe 原 `or 0` 捏造 Sharpe=0 → 假中性 50 分仍計入權重 25(§1 造假:
    「Sharpe 未知」被當成「Sharpe=0」納入評分)。已改 None-honest → 缺資料誠實跳過、不納入評分,
    calc 與 availability 兩端一致;真值(含 0.0)照常有效。故兩因子語意收斂一致,見下方 test。"""

    def test_sharpe_missing_not_available_v19397(self):
        # v19.397 §1:缺 Sharpe → 誠實不可用、不納入評分(原 `or 0` 捏造 0 = 假中性 50 分)。
        fd = {"metrics": {}}
        avail = get_factor_availability(fd)
        assert avail["Sharpe"] is False
        assert _factor_in_score(fd, "Sharpe") is False
        # 有真值時照常可用 + 納入評分;真值 0.0 亦為有效(不再被 `or` 誤判為缺而跳過)
        fd2 = {"metrics": {"sharpe": 1.5}}
        assert get_factor_availability(fd2)["Sharpe"] is True
        assert _factor_in_score(fd2, "Sharpe") is True
        fd3 = {"metrics": {"sharpe": 0.0}}
        assert get_factor_availability(fd3)["Sharpe"] is True
        assert _factor_in_score(fd3, "Sharpe") is True

    def test_sharpe_non_numeric_string_fails(self):
        fd = {"metrics": {"sharpe": "abc"}}
        avail = get_factor_availability(fd)
        assert avail["Sharpe"] is False
        assert _factor_in_score(fd, "Sharpe") is False

    def test_maxdd_missing_not_available_v19381(self):
        # v19.381 §1 除假:缺資料不再捏造 0% 回撤(原 `or "0"` = 假滿分)→ MaxDrawdown 誠實不可用。
        fd = {"metrics": {}}
        avail = get_factor_availability(fd)
        assert avail["MaxDrawdown"] is False
        assert _factor_in_score(fd, "MaxDrawdown") is False
        # 有真值時照常可用 + 納入評分
        fd2 = {"metrics": {"max_drawdown": -12.0}}
        assert get_factor_availability(fd2)["MaxDrawdown"] is True
        assert _factor_in_score(fd2, "MaxDrawdown") is True


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
