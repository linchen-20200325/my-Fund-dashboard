"""v19.119 tests — services.health.dividend canonical 吃本金判定。

含:
1. canonical 函式 `classify_eating_principal` 邊界 + 派生指標
2. 3 套 wrapper 的 golden tests(refactor 前後 output schema 100% 不變守衛)
   - portfolio_service.dividend_safety
   - fund_service.calc_health_from_manual
   - fund_dividend_calculator.div_health_light_for_pair
"""
from __future__ import annotations

import math

import pytest

from services.health.dividend import (
    EatingPrincipalCore,
    classify_eating_principal,
)


# ════════════════════════════════════════════════════════════════
# 1. canonical classify_eating_principal — 核心邊界
# ════════════════════════════════════════════════════════════════

class TestCanonicalDataMissing:
    """資料缺失 → is_data_missing=True,其餘 None/False(§1 fail loud)"""

    def test_total_return_none(self):
        c = classify_eating_principal(None, 5.0)
        assert c.is_data_missing is True
        assert c.is_no_dividend is False
        assert c.is_eating is False
        assert c.coverage_ratio is None
        assert c.gap_pct is None
        assert c.real_return_pct is None

    def test_dividend_yield_none(self):
        c = classify_eating_principal(3.0, None)
        assert c.is_data_missing is True
        assert c.is_eating is False

    def test_both_none(self):
        c = classify_eating_principal(None, None)
        assert c.is_data_missing is True

    def test_nan_treated_as_missing(self):
        assert classify_eating_principal(float("nan"), 5.0).is_data_missing is True
        assert classify_eating_principal(5.0, float("nan")).is_data_missing is True

    def test_string_garbage_treated_as_missing(self):
        assert classify_eating_principal("abc", 5.0).is_data_missing is True
        assert classify_eating_principal(5.0, "xyz").is_data_missing is True


class TestCanonicalNoDividend:
    """div ≤ 0 → is_no_dividend=True, is_eating=False(不存在吃本金概念)"""

    def test_zero_dividend(self):
        c = classify_eating_principal(10.0, 0.0)
        assert c.is_no_dividend is True
        assert c.is_eating is False
        assert c.coverage_ratio is None  # 不適用
        assert c.gap_pct == -10.0        # 仍可算
        assert c.real_return_pct == 10.0

    def test_negative_dividend_treated_as_no_dividend(self):
        c = classify_eating_principal(5.0, -1.0)
        assert c.is_no_dividend is True
        assert c.is_eating is False


class TestCanonicalNormal:
    """正常 case:核心判定 + 全派生指標"""

    @pytest.mark.parametrize("r,d,expect_eating", [
        (5.0, 3.0, False),    # 報酬 > 配息 → 健康
        (3.0, 5.0, True),     # 報酬 < 配息 → 吃本金
        (5.0, 5.0, False),    # 相等 → 不算吃本金(嚴格小於)
        (-2.0, 3.0, True),    # 報酬負 → 必吃本金
        (10.0, 8.0, False),   # 健康
    ])
    def test_is_eating_strict_less_than(self, r, d, expect_eating):
        c = classify_eating_principal(r, d)
        assert c.is_eating is expect_eating

    def test_derived_indicators_consistent(self):
        c = classify_eating_principal(3.0, 5.0)
        assert c.is_data_missing is False
        assert c.is_no_dividend is False
        assert c.is_eating is True
        assert math.isclose(c.coverage_ratio, 0.6, abs_tol=1e-9)
        assert math.isclose(c.gap_pct, 2.0, abs_tol=1e-9)         # 5 - 3
        assert math.isclose(c.real_return_pct, -2.0, abs_tol=1e-9) # 3 - 5

    def test_real_return_is_negative_gap(self):
        """不變量:real_return_pct = -gap_pct"""
        for r, d in [(3.0, 5.0), (8.0, 4.0), (-2.0, 1.0), (0.5, 0.5)]:
            c = classify_eating_principal(r, d)
            if c.gap_pct is not None and c.real_return_pct is not None:
                assert math.isclose(
                    c.real_return_pct, -c.gap_pct, abs_tol=1e-9,
                ), f"real_return + gap ≠ 0 for r={r} d={d}"

    def test_coverage_consistent_with_eating(self):
        """不變量:coverage < 1 ⟺ is_eating(在 div > 0 且資料齊全 case)"""
        for r, d in [(2.0, 5.0), (5.0, 2.0), (3.0, 3.0001), (10.0, 1.0)]:
            c = classify_eating_principal(r, d)
            if c.coverage_ratio is not None:
                # 嚴格 < 對 < 1.0(浮點容差)
                if c.is_eating:
                    assert c.coverage_ratio < 1.0
                else:
                    assert c.coverage_ratio >= 1.0 - 1e-9


# ════════════════════════════════════════════════════════════════
# 2. portfolio_service.dividend_safety — golden tests
#    refactor 前後 output dict 100% 不變
# ════════════════════════════════════════════════════════════════

class TestDividendSafetyGolden:
    """v19.119 refactor 後 output schema 守衛 — 5 級分類 + grey 邊界完整"""

    def test_no_dividend_data(self):
        out = _ds(None, 0)
        assert out["status"] == "N/A"
        assert out["alert_level"] == "grey"
        assert out["message"] == "無配息資料"
        assert out["coverage"] is None
        assert out["eating_principal"] is False

    def test_no_total_return(self):
        out = _ds(None, 5.0)
        assert out["status"] == "無報酬資料"
        assert out["alert_level"] == "grey"
        assert out["coverage"] is None
        assert out["eating_principal"] is False

    def test_serious_eating_negative_return(self):
        # v19.175:gap = 5-(-2) = 7pp > 2pp + ret < 0 → 嚴重吃本金(報酬為負)
        out = _ds(-2.0, 5.0)
        assert "嚴重吃本金" in out["status"]
        assert out["alert_level"] == "red"
        assert out["eating_principal"] is True
        assert out["coverage"] == -0.4
        assert out["gap_pct"] == 7.0  # v19.175 新增欄位

    def test_eating_principal_red(self):
        # v19.175:gap = 5-1 = 4pp > 2pp → 🔴 吃本金(3 色制)
        out = _ds(1.0, 5.0)
        assert out["status"] == "🔴 吃本金"
        assert out["alert_level"] == "red"
        assert out["eating_principal"] is True
        assert out["coverage"] == 0.2
        assert out["gap_pct"] == 4.0

    def test_edge_yellow_within_warn_gap(self):
        # v19.175:gap = 5-4 = 1pp ∈ (0, 2pp] → 🟡 警示
        out = _ds(4.0, 5.0)
        assert "警示" in out["status"]
        assert out["alert_level"] == "yellow"
        # gap > 0 → 技術上吃本金,但在警戒線內
        assert out["eating_principal"] is True
        assert out["gap_pct"] == 1.0

    def test_boundary_gap_equals_warn_threshold(self):
        # v19.175 邊界 case:gap = 2.0pp 剛好等於警戒線 → 仍歸黃(<=)
        out = _ds(3.0, 5.0)
        assert "警示" in out["status"]
        assert out["alert_level"] == "yellow"
        assert out["gap_pct"] == 2.0

    def test_healthy_green_full_coverage(self):
        # v19.175:gap = 5-8 = -3pp ≤ 0 → 🟢 健康
        out = _ds(8.0, 5.0)
        assert out["status"] == "🟢 健康"
        assert out["alert_level"] == "green"
        assert out["eating_principal"] is False
        assert out["coverage"] == 1.6
        assert out["gap_pct"] == -3.0

    def test_healthy_green_break_even(self):
        # v19.175:gap = 5-5 = 0 → 🟢 健康(持平視同覆蓋)
        out = _ds(5.0, 5.0)
        assert out["status"] == "🟢 健康"
        assert out["alert_level"] == "green"
        assert out["gap_pct"] == 0.0

    def test_nav_cross_check_warning(self):
        out = _ds(3.0, 5.0, nav_change=-7.0)
        assert out["nav_warning"] is not None
        assert "淨值下跌" in out["nav_warning"]

    def test_nav_no_warning_when_change_above_threshold(self):
        out = _ds(3.0, 5.0, nav_change=-3.0)  # > -5%
        assert out["nav_warning"] is None


def _ds(total_return, dividend_yield, nav_change=None):
    """shortcut helper"""
    from services.portfolio_service import dividend_safety
    return dividend_safety(total_return, dividend_yield, nav_change)


# ════════════════════════════════════════════════════════════════
# 3. fund_service.calc_health_from_manual — golden tests
#    refactor 前後 4 級 + 完整 NAV 計算 chain 不變
# ════════════════════════════════════════════════════════════════

class TestCalcHealthFromManualGolden:
    """4 級健康分類 + 自算 NAV/配息 chain 守衛"""

    def test_invalid_nav_returns_error(self):
        from services.fund_service import calc_health_from_manual
        assert "error" in calc_health_from_manual(0, 100, 1.0)
        assert "error" in calc_health_from_manual(100, 0, 1.0)
        assert "error" in calc_health_from_manual(-5, 100, 1.0)

    def test_eating_principal_red(self):
        from services.fund_service import calc_health_from_manual
        # NAV 跌 5%,月配 0.5(年化 6 → div 6%),總報酬 = -5% + 6% = 1%
        # 真實收益 = 1% - 6% = -5% → 含息 1% < 配息 6% → 🔴 吃本金
        out = calc_health_from_manual(
            nav_current=95.0, nav_1y_ago=100.0,
            div_per_unit=0.5, div_freq=12,
        )
        assert "吃本金" in out["health"]
        assert out["eating_principal"] is True
        assert out["calc_mode"] == "manual"

    def test_healthy_growth_green(self):
        from services.fund_service import calc_health_from_manual
        # NAV 漲 10%,月配 0.1(年化 1.09% ≈),總報酬 ≈ 11.09%
        # 真實收益 = 11.09 - 1.09 = 10 > 3 → 🟢 健康成長
        out = calc_health_from_manual(
            nav_current=110.0, nav_1y_ago=100.0,
            div_per_unit=0.1, div_freq=12,
        )
        assert "健康成長" in out["health"]
        assert out["eating_principal"] is False
        assert out["real_return_pct"] >= 3

    def test_edge_yellow(self):
        from services.fund_service import calc_health_from_manual
        # NAV 漲 1%,月配 0.175 → 年化配息 2.1%,含息 3.1%,真實 = 1% ∈ [0,3) → 🟡 邊緣
        out = calc_health_from_manual(
            nav_current=101.0, nav_1y_ago=100.0,
            div_per_unit=0.175, div_freq=12,
        )
        assert "邊緣健康" in out["health"], (
            f"預期邊緣,實得 {out['health']} "
            f"(real={out['real_return_pct']}, total={out['total_return_pct']}, "
            f"div={out['div_yield_pct']})"
        )
        assert out["eating_principal"] is False
        assert 0 <= out["real_return_pct"] < 3

    def test_output_schema_complete(self):
        """守衛:所有既有欄位齊全(v19.119 refactor 不掉欄位)"""
        from services.fund_service import calc_health_from_manual
        out = calc_health_from_manual(
            nav_current=100.0, nav_1y_ago=95.0,
            div_per_unit=0.5, div_freq=12, fund_name="TEST",
        )
        expected_keys = {
            "fund_name", "nav_current", "nav_1y_ago", "nav_change_pct",
            "div_per_unit", "div_freq", "annual_div", "div_yield_pct",
            "total_return_pct", "real_return_pct", "eating_principal",
            "health", "health_color", "advice", "calc_mode",
        }
        assert set(out.keys()) == expected_keys, (
            f"refactor 漏欄位 / 多欄位: missing={expected_keys - set(out.keys())} "
            f"extra={set(out.keys()) - expected_keys}"
        )

    def test_advice_strings_preserve_format(self):
        """守衛:既有 advice 字串格式不變(UI 直接顯示)"""
        from services.fund_service import calc_health_from_manual
        out = calc_health_from_manual(
            nav_current=95.0, nav_1y_ago=100.0, div_per_unit=0.5, div_freq=12,
        )
        # 吃本金 advice 含「< 配息率」字串
        assert "<" in out["advice"] and "配息率" in out["advice"]


# ════════════════════════════════════════════════════════════════
# 4. fund_dividend_calculator.div_health_light_for_pair — extra
#    既有 test_fund_dividend_calculator.py 已守衛 base case,
#    此處加 canonical 委派一致性 test
# ════════════════════════════════════════════════════════════════

class TestDivHealthLightDelegation:
    """確認 v19.119 委派後行為與 canonical 一致"""

    def test_consistent_with_canonical_eating(self):
        from services.health.dividend_calc import div_health_light_for_pair
        # canonical 說 is_eating=True 時 → tuple 結果應為 警示 or 吃本金
        for r, d in [(3.0, 5.0), (-1.0, 4.0), (1.0, 8.0)]:
            core = classify_eating_principal(r, d)
            if core.is_eating:
                label, emoji = div_health_light_for_pair(r, d)
                assert label in ("警示", "吃本金"), (
                    f"is_eating=True 但燈號={label}(r={r},d={d})"
                )

    def test_consistent_with_canonical_healthy(self):
        from services.health.dividend_calc import div_health_light_for_pair
        # canonical 說 is_eating=False 且 div > 0 時 → 健康 or 警示 or 吃本金
        # (因為 warn_gap 細分,is_eating=False 也可能是「打平,gap=0,green」)
        # 嚴格 case:gap < 0 必綠
        for r, d in [(10.0, 5.0), (5.0, 4.0)]:
            label, _ = div_health_light_for_pair(r, d)
            assert label == "健康"


# v19.119 §6 自審「3 個最容易出錯的輸入」:
#   1. 資料缺失(None/NaN/字串)→ is_data_missing=True ✅ TestCanonicalDataMissing
#   2. 無配息基金(div=0/負)→ is_no_dividend=True, is_eating=False ✅ TestCanonicalNoDividend
#   3. 報酬 = 配息(打平 edge case)→ is_eating=False(嚴格小於)✅ test_is_eating_strict_less_than


# ════════════════════════════════════════════════════════════════
# v19.181 Bug 4 regression — check_eating_principal_1y_mk 接受 pd.Series
# ════════════════════════════════════════════════════════════════

class TestCheckEatingPrincipal1YmkAcceptsPdSeries:
    """v19.181 Bug 4 regression:fund["series"] 為 pd.Series 時不可 ambiguous truth value.

    過去 `fund.get("series") or X` 對多元素 pd.Series 觸發
    `ValueError: The truth value of a Series is ambiguous.` 導致組合基金
    健診摘要表 10/10 ValueError 全炸,改顯式 None 檢查後解決。
    """

    def _build_fund(self, series_obj, divs_obj):
        return {
            "series": series_obj,
            "dividends": divs_obj,
            "moneydj_raw": {"moneydj_div_yield": 7.49},
            "metrics": {"ret_1y_total": 14.5},
        }

    def test_pd_series_nav_no_value_error(self):
        # v19.175 後主源改 compute_1y_total_return(業界複利優先,perf['1Y'] >
        # ret_1y_total > ret_1y > NAV 外推),Bug 4 fix 核心 assertion 仍守
        # 「pd.Series 進去不 raise」+ 回 dict;_tr1y_method 期待業界路徑。
        import pandas as pd
        from services.health.dividend import check_eating_principal_1y_mk
        nav = {f"2024-{m:02d}-01": 8.0 + 0.01 * m for m in range(1, 13)}
        nav["2025-06-01"] = 9.10
        s = pd.Series(nav, name="nav")
        divs = [{"date": "2024-12-15", "amount": 0.05}]
        fund = self._build_fund(s, divs)
        out = check_eating_principal_1y_mk(fund)  # 不可 raise(Bug 4 核心)
        assert isinstance(out, dict)
        # v19.175:走業界 ret_1y_total 路徑;mk_simple 退居對照欄(_tr1y_meta)
        assert "ret_1y_total" in (out.get("_tr1y_method") or "")
        # 對照欄仍可算出 mk_simple_value
        assert out.get("_tr1y_meta") is not None
        assert "mk_simple_value" in out["_tr1y_meta"]

    def test_dict_nav_still_works(self):
        """confirm refactor 不破壞 dict 入口."""
        from services.health.dividend import check_eating_principal_1y_mk
        nav = {f"2024-{m:02d}-01": 8.0 + 0.01 * m for m in range(1, 13)}
        nav["2025-06-01"] = 9.10
        divs = [{"date": "2024-12-15", "amount": 0.05}]
        fund = self._build_fund(nav, divs)
        out = check_eating_principal_1y_mk(fund)
        assert isinstance(out, dict)
        # v19.175 業界路徑(metrics.ret_1y_total = 14.5 走 ret_1y_total)
        assert "ret_1y_total" in (out.get("_tr1y_method") or "")

    def test_falls_back_to_moneydj_series_when_top_none(self):
        """top-level None → 走 moneydj_raw["series"] fallback。

        v19.175:此 test 守的核心仍是「不 raise + 回 dict」(Bug 4 fix 行為)。
        主源走業界 ret_1y_total(metrics.ret_1y_total=14.5),mk_simple 退對照欄。
        """
        import pandas as pd
        from services.health.dividend import check_eating_principal_1y_mk
        nav = {f"2024-{m:02d}-01": 8.0 + 0.01 * m for m in range(1, 13)}
        nav["2025-06-01"] = 9.10
        s = pd.Series(nav, name="nav")
        fund = {
            "series": None,  # top-level missing
            "dividends": None,
            "moneydj_raw": {
                "moneydj_div_yield": 7.49,
                "series": s,
                "dividends": [{"date": "2024-12-15", "amount": 0.05}],
            },
            "metrics": {"ret_1y_total": 14.5},
        }
        out = check_eating_principal_1y_mk(fund)
        assert isinstance(out, dict)
        # mk_simple 對照欄仍能從 moneydj_raw.series + dividends fallback 算出
        assert out.get("_tr1y_meta") is not None
        assert "mk_simple_value" in out["_tr1y_meta"]
