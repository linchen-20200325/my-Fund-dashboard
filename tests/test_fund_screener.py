"""v19.26 Fund Screener — 純函式層測試 (≥20 case)。

驗證重點：
1. div_health_light 三色燈 + 邊界 + 缺資料 graceful
2. apply_filters 11 條件 + 多條 AND + 空輸入 + 缺欄位 graceful
3. collect_distinct_values UI 選項抽取
"""
from __future__ import annotations

import math

import pytest

from services.fund_screener import (
    DEFAULT_WARN_GAP,
    DIV_HEALTH_EMOJI,
    DIV_HEALTH_LIGHTS,
    FILTER_KEYS,
    apply_filters,
    collect_distinct_values,
    div_health_light,
)


# ════════════════════════════════════════════════════════════════
# §1 常量結構
# ════════════════════════════════════════════════════════════════
class TestConstants:
    def test_filter_keys_count(self):
        assert len(FILTER_KEYS) == 11

    def test_div_health_lights(self):
        assert set(DIV_HEALTH_LIGHTS) == {"健康", "警示", "吃本金", "資料不足"}
        for label in DIV_HEALTH_LIGHTS:
            assert label in DIV_HEALTH_EMOJI

    def test_default_warn_gap(self):
        assert DEFAULT_WARN_GAP == 2.0


# ════════════════════════════════════════════════════════════════
# §2 div_health_light 三色燈
# ════════════════════════════════════════════════════════════════
class TestDivHealthLight:
    def test_healthy_ret_above_div(self):
        # 含息 8% ≥ 配息 5% → 🟢
        label, emoji = div_health_light(8.0, 5.0)
        assert label == "健康"
        assert emoji == "🟢"

    def test_warn_small_gap(self):
        # 含息 4.5% 配息 5% → 差距 0.5% ≤ 2% → 🟡
        label, _ = div_health_light(4.5, 5.0)
        assert label == "警示"

    def test_eat_principal_large_gap(self):
        # 含息 2% 配息 5% → 差距 3% > 2% → 🔴
        label, emoji = div_health_light(2.0, 5.0)
        assert label == "吃本金"
        assert emoji == "🔴"

    def test_user_example_5_2_minus_9_6(self):
        """圖二實例：安聯收益成長 含息 1Y=+5.2%，配息率=9.6% → 差距 -4.4% → 🔴。"""
        label, _ = div_health_light(5.2, 9.6)
        assert label == "吃本金"

    def test_zero_div_no_dividend_fund(self):
        # 不配息基金 → 永遠健康（無侵蝕本金疑慮）
        label, _ = div_health_light(8.0, 0.0)
        assert label == "健康"

    def test_negative_ret(self):
        # 含息 -3% 配息 5% → 差距 8% → 🔴
        label, _ = div_health_light(-3.0, 5.0)
        assert label == "吃本金"

    def test_none_ret(self):
        label, emoji = div_health_light(None, 5.0)
        assert label == "資料不足"
        assert emoji == "⚪"

    def test_none_div(self):
        label, _ = div_health_light(5.0, None)
        assert label == "資料不足"

    def test_nan_inputs(self):
        label, _ = div_health_light(float("nan"), 5.0)
        assert label == "資料不足"
        label, _ = div_health_light(5.0, float("nan"))
        assert label == "資料不足"

    def test_string_inputs_graceful(self):
        # 非數值字串 → 資料不足
        label, _ = div_health_light("abc", 5.0)
        assert label == "資料不足"

    def test_string_numeric_inputs(self):
        # 字串數值 → 解析後正常判定
        label, _ = div_health_light("8.0", "5.0")
        assert label == "健康"

    def test_boundary_exact_warn_gap(self):
        # 差距正好 2.0% → ≤ 邊界仍是 🟡
        label, _ = div_health_light(3.0, 5.0)
        assert label == "警示"

    def test_boundary_just_over_warn_gap(self):
        # 差距 2.01% → > 邊界 → 🔴
        label, _ = div_health_light(2.99, 5.0)
        assert label == "吃本金"

    def test_custom_warn_gap_strict(self):
        # 嚴格門檻 1%：差距 1.5% → 🔴
        label, _ = div_health_light(3.5, 5.0, warn_gap=1.0)
        assert label == "吃本金"

    def test_custom_warn_gap_lax(self):
        # 寬鬆門檻 3%：差距 2.5% → 🟡
        label, _ = div_health_light(2.5, 5.0, warn_gap=3.0)
        assert label == "警示"

    def test_exact_equal_ret_div(self):
        # 完全相等 → 健康（gap=0，落在 ≥）
        label, _ = div_health_light(5.0, 5.0)
        assert label == "健康"


# ════════════════════════════════════════════════════════════════
# §3 apply_filters — 11 條件
# ════════════════════════════════════════════════════════════════
def _make_fund(**kwargs) -> dict:
    """工廠：產生一個 fund dict 含 default 欄位。"""
    base = {
        "fund_code": "TEST001",
        "fund_name": "測試基金",
        "domestic_overseas": "境外",
        "fund_type": "股票型",
        "currency": "USD",
        "brand": "安聯",
        "fund_region": "全球",
        "fund_group": "環球股票",
        "dividend_freq": "月配",
        "lipper_score": 4,
        "risk_level": "RR4",
        "esg_score": 50.0,
        "metrics": {
            "ret_1y_total": 8.0,
            "annual_div_rate": 5.0,
        },
    }
    # 允許 kwargs override 任何欄
    for k, v in kwargs.items():
        if k in ("ret_1y_total", "annual_div_rate"):
            base["metrics"][k] = v
        else:
            base[k] = v
    return base


class TestApplyFiltersEdgeCases:
    def test_empty_funds(self):
        filtered, stats = apply_filters([], {})
        assert filtered == []
        assert stats["n_input"] == 0
        assert stats["n_output"] == 0

    def test_no_filters_all_pass(self):
        funds = [_make_fund(fund_code="A"), _make_fund(fund_code="B")]
        filtered, stats = apply_filters(funds, {})
        assert len(filtered) == 2
        assert stats["n_filtered_out"] == 0

    def test_none_filters_dict(self):
        funds = [_make_fund()]
        filtered, _ = apply_filters(funds, None)
        assert len(filtered) == 1

    def test_skip_non_dict_entries(self):
        funds = [_make_fund(), "not a dict", None, 42]  # type: ignore[list-item]
        filtered, stats = apply_filters(funds, {})
        assert len(filtered) == 1
        assert stats["n_input"] == 4

    def test_injects_div_health_fields(self):
        filtered, _ = apply_filters([_make_fund()], {})
        assert filtered[0]["_div_health_light"] in DIV_HEALTH_LIGHTS
        assert filtered[0]["_div_health_emoji"] in DIV_HEALTH_EMOJI.values()


class TestApplyFiltersStringFields:
    def test_domestic_overseas(self):
        funds = [
            _make_fund(fund_code="A", domestic_overseas="境內"),
            _make_fund(fund_code="B", domestic_overseas="境外"),
        ]
        filtered, _ = apply_filters(funds, {"domestic_overseas": ["境外"]})
        assert len(filtered) == 1
        assert filtered[0]["fund_code"] == "B"

    def test_currency(self):
        funds = [
            _make_fund(fund_code="A", currency="TWD"),
            _make_fund(fund_code="B", currency="USD"),
            _make_fund(fund_code="C", currency="EUR"),
        ]
        filtered, _ = apply_filters(funds, {"currency": ["TWD", "USD"]})
        assert {f["fund_code"] for f in filtered} == {"A", "B"}

    def test_brand_substring_match(self):
        # _str_in 容許 substring：「安聯收益成長」應命中 "安聯"
        funds = [
            _make_fund(fund_code="A", brand="安聯收益成長"),
            _make_fund(fund_code="B", brand="貝萊德世界科技"),
        ]
        filtered, _ = apply_filters(funds, {"brand": ["安聯"]})
        assert len(filtered) == 1
        assert filtered[0]["fund_code"] == "A"

    def test_dividend_freq(self):
        funds = [
            _make_fund(fund_code="A", dividend_freq="月配"),
            _make_fund(fund_code="B", dividend_freq="不配息"),
        ]
        filtered, _ = apply_filters(funds, {"dividend_freq": ["不配息"]})
        assert len(filtered) == 1
        assert filtered[0]["fund_code"] == "B"

    def test_risk_level(self):
        funds = [
            _make_fund(fund_code="A", risk_level="RR1"),
            _make_fund(fund_code="B", risk_level="RR5"),
        ]
        filtered, _ = apply_filters(funds, {"risk_level": ["RR1", "RR2"]})
        assert len(filtered) == 1
        assert filtered[0]["fund_code"] == "A"

    def test_missing_field_graceful_pass(self):
        # 缺欄位視為 pass（不剔除），UI 端用「請補抓詳情」hint 提示
        # NOTE: fund_name 也要清才測得到「真的全缺」— _get_field 會 fallback fund_name
        funds = [_make_fund(fund_code="A", brand=None, fund_name=None)]
        filtered, _ = apply_filters(funds, {"brand": ["安聯"]})
        assert len(filtered) == 1


class TestApplyFiltersNumericThresholds:
    def test_lipper_min(self):
        funds = [
            _make_fund(fund_code="A", lipper_score=2),
            _make_fund(fund_code="B", lipper_score=4),
            _make_fund(fund_code="C", lipper_score=5),
        ]
        filtered, _ = apply_filters(funds, {"lipper_min": 4})
        assert {f["fund_code"] for f in filtered} == {"B", "C"}

    def test_esg_min(self):
        funds = [
            _make_fund(fund_code="A", esg_score=25),
            _make_fund(fund_code="B", esg_score=45),
        ]
        filtered, _ = apply_filters(funds, {"esg_min": 40})
        assert len(filtered) == 1
        assert filtered[0]["fund_code"] == "B"

    def test_nan_numeric_graceful(self):
        funds = [_make_fund(fund_code="A", esg_score=float("nan"))]
        filtered, _ = apply_filters(funds, {"esg_min": 40})
        # NaN → pass（graceful，UI 端再決定要不要列「待補資料」）
        assert len(filtered) == 1


class TestDivHealthFilter:
    def test_healthy_only_filters_eat_principal(self):
        funds = [
            _make_fund(fund_code="A", ret_1y_total=8.0, annual_div_rate=5.0),  # 健康
            _make_fund(fund_code="B", ret_1y_total=2.0, annual_div_rate=5.0),  # 吃本金
            _make_fund(fund_code="C", ret_1y_total=4.5, annual_div_rate=5.0),  # 警示
        ]
        filtered, stats = apply_filters(
            funds, {"div_health_healthy_only": True}
        )
        assert len(filtered) == 1
        assert filtered[0]["fund_code"] == "A"
        assert stats["lights"]["健康"] == 1

    def test_off_keeps_all_but_counts_lights(self):
        funds = [
            _make_fund(fund_code="A", ret_1y_total=8.0, annual_div_rate=5.0),  # 健康
            _make_fund(fund_code="B", ret_1y_total=2.0, annual_div_rate=5.0),  # 吃本金
            _make_fund(fund_code="C", ret_1y_total=4.5, annual_div_rate=5.0),  # 警示
            _make_fund(fund_code="D", ret_1y_total=None, annual_div_rate=5.0),  # 資料不足
        ]
        filtered, stats = apply_filters(funds, {})
        assert len(filtered) == 4
        assert stats["lights"] == {
            "健康": 1, "警示": 1, "吃本金": 1, "資料不足": 1,
        }


class TestApplyFiltersCombined:
    def test_multi_filter_AND(self):
        funds = [
            _make_fund(fund_code="A", brand="安聯", currency="TWD"),
            _make_fund(fund_code="B", brand="安聯", currency="USD"),
            _make_fund(fund_code="C", brand="貝萊德", currency="TWD"),
        ]
        filtered, _ = apply_filters(
            funds,
            {"brand": ["安聯"], "currency": ["TWD"]},
        )
        assert len(filtered) == 1
        assert filtered[0]["fund_code"] == "A"

    def test_filter_field_lookup_in_metrics_subdict(self):
        # ret_1y_total / annual_div_rate 在 metrics 子 dict 內，_get_field 應能找到
        f = _make_fund()
        filtered, stats = apply_filters([f], {"div_health_healthy_only": True})
        assert len(filtered) == 1  # 預設 ret=8 div=5 → 健康


# ════════════════════════════════════════════════════════════════
# §4 collect_distinct_values
# ════════════════════════════════════════════════════════════════
class TestCollectDistinctValues:
    def test_collects_top_level(self):
        funds = [
            _make_fund(currency="TWD"),
            _make_fund(currency="USD"),
            _make_fund(currency="TWD"),
        ]
        vals = collect_distinct_values(funds, "currency")
        # 出現次數降序：TWD(2) > USD(1)
        assert vals == ["TWD", "USD"]

    def test_filters_none_and_nan_strings(self):
        funds = [
            _make_fund(currency="USD"),
            _make_fund(currency=None),
            _make_fund(currency=""),
            {"currency": "nan"},
            {"currency": math.nan},
        ]
        vals = collect_distinct_values(funds, "currency")
        assert vals == ["USD"]

    def test_skips_non_dict_input(self):
        vals = collect_distinct_values(
            ["bad", _make_fund(currency="USD")],  # type: ignore[list-item]
            "currency",
        )
        assert vals == ["USD"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
