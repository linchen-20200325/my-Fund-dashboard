"""v19.37 tests — services.health.dividend_calc 純函式單元測試。"""
from __future__ import annotations

import pytest

from services.health.dividend_calc import (
    DEFAULT_PRINCIPAL_TWD,
    compute_dividend_twd_series,
    div_health_light_for_pair,
)


# ════════════════════════════════════════════════════════════════
# div_health_light_for_pair
# ════════════════════════════════════════════════════════════════
class TestDivHealthLight:
    def test_none_returns_data_missing(self):
        assert div_health_light_for_pair(None, 5.0) == ("資料不足", "⚪")
        assert div_health_light_for_pair(5.0, None) == ("資料不足", "⚪")
        assert div_health_light_for_pair(None, None) == ("資料不足", "⚪")

    def test_nan_returns_data_missing(self):
        assert div_health_light_for_pair(float("nan"), 5.0) == ("資料不足", "⚪")

    def test_string_garbage_returns_data_missing(self):
        assert div_health_light_for_pair("abc", 5.0) == ("資料不足", "⚪")

    def test_zero_div_is_healthy(self):
        assert div_health_light_for_pair(-10.0, 0.0) == ("健康", "🟢")

    def test_negative_div_is_healthy(self):
        assert div_health_light_for_pair(0.0, -1.0) == ("健康", "🟢")

    def test_ret_ge_div_is_healthy(self):
        assert div_health_light_for_pair(10.0, 5.0) == ("健康", "🟢")
        assert div_health_light_for_pair(5.0, 5.0) == ("健康", "🟢")

    def test_small_gap_warns(self):
        assert div_health_light_for_pair(3.0, 4.0) == ("警示", "🟡")

    def test_gap_at_threshold_warns(self):
        assert div_health_light_for_pair(3.0, 5.0, warn_gap=2.0) == ("警示", "🟡")

    def test_big_gap_eats_principal(self):
        assert div_health_light_for_pair(1.0, 5.0) == ("吃本金", "🔴")

    def test_custom_warn_gap(self):
        assert div_health_light_for_pair(3.0, 5.0, warn_gap=1.0) == ("吃本金", "🔴")


# ════════════════════════════════════════════════════════════════
# compute_dividend_twd_series — 邊界/失敗路徑
# ════════════════════════════════════════════════════════════════
class TestComputeDividendBoundaries:
    def test_zero_principal_returns_error(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0}, dividend_events=[],
            fx_rate_default=30.0, principal_twd=0,
        )
        assert r["ok"] is False
        assert "principal" in r["error"]

    def test_negative_principal_returns_error(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0}, dividend_events=[],
            fx_rate_default=30.0, principal_twd=-1000,
        )
        assert r["ok"] is False

    def test_zero_fx_returns_error(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0}, dividend_events=[],
            fx_rate_default=0,
        )
        assert r["ok"] is False
        assert "fx_rate_default" in r["error"]

    def test_empty_nav_returns_error(self):
        r = compute_dividend_twd_series(
            nav_series={}, dividend_events=[], fx_rate_default=30.0,
        )
        assert r["ok"] is False
        assert "nav" in r["error"].lower()

    def test_non_dict_nav_returns_error(self):
        r = compute_dividend_twd_series(
            nav_series="not a dict",  # type: ignore[arg-type]
            dividend_events=[], fx_rate_default=30.0,
        )
        assert r["ok"] is False

    def test_all_nan_nav_returns_error(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": float("nan"), "2024-01-02": None},
            dividend_events=[], fx_rate_default=30.0,
        )
        assert r["ok"] is False

    def test_negative_nav_filtered_out(self):
        # 全為非正 NAV → 無有效資料
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": -1.0, "2024-01-02": 0.0},
            dividend_events=[], fx_rate_default=30.0,
        )
        assert r["ok"] is False


# ════════════════════════════════════════════════════════════════
# compute_dividend_twd_series — 正向流程
# ════════════════════════════════════════════════════════════════
class TestComputeDividendHappyPath:
    def test_no_dividends_healthy_with_nav_growth(self):
        # NAV 10 → 11，無配息 → 健康
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2025-01-01": 11.0},
            dividend_events=[],
            fx_rate_default=30.0,
        )
        assert r["ok"] is True
        assert r["n_events"] == 0
        assert r["events"] == []
        assert r["summary"]["div_health_light_🧮"] == "健康"

    def test_principal_ccy_conversion(self):
        # 100 萬 TWD / FX 30 = 3.33 萬 USD
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[], fx_rate_default=30.0,
            principal_twd=1_000_000.0,
        )
        assert r["principal_ccy_🧮"] == pytest.approx(33333.33, abs=0.01)
        # units = 33333.33 / 10 = 3333.33
        assert r["units_held_🧮"] == pytest.approx(3333.33, abs=0.01)

    def test_buy_fx_uses_historical_when_available(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[], fx_rate_default=30.0,
            fx_rate_by_date={"2024-01-01": 31.5},
        )
        assert r["buy_fx"] == 31.5
        assert r["buy_fx_source"] == "historical"

    def test_buy_fx_fallback_to_spot(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[], fx_rate_default=30.0,
        )
        assert r["buy_fx"] == 30.0
        assert r["buy_fx_source"] == "spot"

    def test_one_dividend_event_twd_amount(self):
        # 100 萬 TWD / FX30 → 33333.33 USD / NAV10 → 3333.33 units
        # 配息 0.5/unit → 1666.66 USD × FX30 → 49999.95 TWD ≈ 50000
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-06-30": 10.0, "2024-12-31": 10.0},
            dividend_events=[{"date": "2024-06-30", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        assert r["n_events"] == 1
        ev = r["events"][0]
        assert ev["ex_date"] == "2024-06-30"
        assert ev["ccy_div_per_unit"] == 0.5
        assert ev["twd_div_🧮"] == pytest.approx(50000.0, abs=1.0)

    def test_div_before_buy_date_skipped(self):
        # 配息發生於買進前 → 不計
        r = compute_dividend_twd_series(
            nav_series={"2024-06-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[{"date": "2024-01-01", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        assert r["n_events"] == 0

    def test_zero_div_amount_skipped(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[
                {"date": "2024-06-30", "amount": 0.0},
                {"date": "2024-07-31", "amount": -0.5},
            ],
            fx_rate_default=30.0,
        )
        assert r["n_events"] == 0

    def test_missing_div_amount_skipped(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[{"date": "2024-06-30"}],
            fx_rate_default=30.0,
        )
        assert r["n_events"] == 0

    def test_missing_div_date_skipped(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[{"amount": 0.5}],
            fx_rate_default=30.0,
        )
        assert r["n_events"] == 0

    def test_div_sorted_by_date(self):
        # 亂序輸入 → 結果照 ex_date 升序
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[
                {"date": "2024-08-31", "amount": 0.3},
                {"date": "2024-03-31", "amount": 0.4},
                {"date": "2024-06-30", "amount": 0.5},
            ],
            fx_rate_default=30.0,
        )
        dates = [e["ex_date"] for e in r["events"]]
        assert dates == ["2024-03-31", "2024-06-30", "2024-08-31"]

    def test_nav_fallback_when_exact_date_missing(self):
        # ex_date NAV 不存在 → 用 ≤ ex_date 最近 NAV
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 12.0},
            dividend_events=[{"date": "2024-06-30", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        ev = r["events"][0]
        # ≤ 2024-06-30 最近 = 2024-01-01 NAV=10
        assert ev["nav_at_ex"] == 10.0
        # single_event_div_pct = 0.5/10 = 5%
        assert ev["single_event_div_pct_🧮"] == pytest.approx(5.0, abs=0.01)


# ════════════════════════════════════════════════════════════════
# compute_dividend_twd_series — 吃本金判定
# ════════════════════════════════════════════════════════════════
class TestEatingPrincipalDetection:
    def test_high_div_low_return_flagged_red(self):
        # NAV 10 → 9（一年 -10%）+ 大配息 → 吃本金
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2025-01-01": 9.0},
            dividend_events=[
                {"date": "2024-06-30", "amount": 0.5},
                {"date": "2024-12-31", "amount": 0.5},
            ],
            fx_rate_default=30.0,
        )
        # 年化 NAV return = -10%, annual div rate ≈ 10%, sum ≈ 0%
        # gap = 10 - 0 = 10 > warn_gap(2) → 吃本金
        assert r["summary"]["div_health_light_🧮"] == "吃本金"

    def test_balanced_growth_offsetting_div_healthy(self):
        # NAV 10 → 11（+10%）+ 配息 5% → ret_total ≈ 15% > div 5% → 健康
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2025-01-01": 11.0},
            dividend_events=[{"date": "2024-12-31", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        assert r["summary"]["div_health_light_🧮"] == "健康"

    def test_warn_zone_yellow(self):
        # NAV slight decline + moderate div → 警示區
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2025-01-01": 9.95},
            dividend_events=[{"date": "2024-12-31", "amount": 0.5}],
            fx_rate_default=30.0,
            warn_gap_pct=2.0,
        )
        # nav_ret -0.5%, div ≈ 5%, ret_total ≈ 4.5%, gap = div-ret_total = 0.5 ≤ 2
        assert r["summary"]["div_health_light_🧮"] == "警示"


# ════════════════════════════════════════════════════════════════
# compute_dividend_twd_series — FX 歷史 / spot 標示
# ════════════════════════════════════════════════════════════════
class TestFxSourcing:
    def test_fx_historical_used_when_available(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[{"date": "2024-06-30", "amount": 0.5}],
            fx_rate_default=30.0,
            fx_rate_by_date={"2024-06-30": 32.0},
        )
        ev = r["events"][0]
        assert ev["fx_at_ex"] == 32.0
        assert ev["fx_source"] == "historical"

    def test_fx_spot_fallback(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[{"date": "2024-06-30", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        ev = r["events"][0]
        assert ev["fx_at_ex"] == 30.0
        assert ev["fx_source"] == "spot"

    def test_mixed_fx_some_historical_some_spot(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[
                {"date": "2024-03-31", "amount": 0.5},
                {"date": "2024-06-30", "amount": 0.5},
            ],
            fx_rate_default=30.0,
            fx_rate_by_date={"2024-03-31": 31.5},
        )
        assert r["events"][0]["fx_source"] == "historical"
        assert r["events"][0]["fx_at_ex"] == 31.5
        assert r["events"][1]["fx_source"] == "spot"
        assert r["events"][1]["fx_at_ex"] == 30.0


# ════════════════════════════════════════════════════════════════
# 自行計算欄位清單與 default 常數
# ════════════════════════════════════════════════════════════════
class TestSelfCalcMetadata:
    def test_default_principal_constant(self):
        assert DEFAULT_PRINCIPAL_TWD == 1_000_000.0

    def test_self_calc_fields_present(self):
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[],
            fx_rate_default=30.0,
        )
        assert "_self_calc_fields" in r
        fields = r["_self_calc_fields"]
        assert "principal_ccy" in fields
        assert "units_held" in fields
        assert "summary.div_health_light" in fields

    def test_self_calc_emoji_in_event_keys(self):
        # 🧮 icon 嵌在自行計算欄位 key 中（UI 直接拿即可染色）
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[{"date": "2024-06-30", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        ev = r["events"][0]
        assert "twd_div_🧮" in ev
        assert "units_at_event_🧮" in ev
        assert "ccy_div_total_🧮" in ev
        # MoneyDJ 原欄位不標
        assert "ccy_div_per_unit" in ev and "_🧮" not in "ccy_div_per_unit"
        assert "ex_date" in ev
        assert "nav_at_ex" in ev


# ════════════════════════════════════════════════════════════════
# v19.180 — 全期實際 3 軸並陳(修截圖反饋:短歷史顯示 None 問題)
# ════════════════════════════════════════════════════════════════
class TestCumulativeActualFields:
    """v19.180 守:全期實際 3 軸永遠算出(不受 0.5 年 guard 影響)。

    修截圖反饋「配息率% / 淨值% / 含息% (全期自算) 全 None」根因:
    v19.175 的 0.5 年 guard 把年化值設 None,但欄名「(全期自算)」字面是
    持有期實際累計,跟 user 預期不符。改加「全期實際」3 軸並陳。
    """

    def test_short_history_cumulative_still_present(self):
        """持有 0.1 年(< 0.5 年 guard)— 年化欄 None,但全期實際 3 欄仍有值。"""
        # NAV 10 → 10.5 (持有 ~36 天 ≈ 0.1 年)
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-02-06": 10.5},
            dividend_events=[{"date": "2024-01-15", "amount": 0.1}],
            fx_rate_default=30.0,
        )
        s = r["summary"]
        assert s["holding_years_🧮"] < 0.5, "前提:持有 < 0.5 年觸發 guard"
        # 年化欄 v19.175 設計 → None
        assert s["annual_div_rate_pct_🧮"] is None
        assert s["annual_nav_return_pct_🧮"] is None
        assert s["ret_1y_total_pct_🧮"] is None
        # 全期實際 3 欄 v19.180 → 必須有值(非 None)
        assert s["cum_div_rate_pct_🧮"] is not None, "全期實際配息率短歷史也該算"
        assert s["cum_nav_return_pct_🧮"] is not None, "全期實際淨值%短歷史也該算"
        assert s["cum_total_return_pct_🧮"] is not None, "全期實際含息%短歷史也該算"

    def test_cumulative_div_rate_no_annualization(self):
        """全期實際配息率 = 累計配息 / 本金 × 100(不除年數)。"""
        # 本金 100 萬 TWD / FX 30 = 33333.33 USD / NAV 10 = 3333.33 units
        # 配息 0.5/unit → 1666.67 USD 累計配息
        # 全期實際配息率 = 1666.67 / 33333.33 × 100 = 5.00%
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-03-01": 10.0},  # ~0.16 年
            dividend_events=[{"date": "2024-02-01", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        s = r["summary"]
        assert s["cum_div_rate_pct_🧮"] == pytest.approx(5.0, abs=0.01), (
            f"5.00% 預期(0.5 USD/unit × 3333 units / 33333 USD),實際 "
            f"{s['cum_div_rate_pct_🧮']}"
        )

    def test_cumulative_nav_return_no_annualization(self):
        """全期實際淨值% = (last_nav / buy_nav − 1) × 100,不除年數。"""
        # NAV 10 → 11 = +10% (持有 0.3 年)
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-04-15": 11.0},
            dividend_events=[],
            fx_rate_default=30.0,
        )
        s = r["summary"]
        assert s["cum_nav_return_pct_🧮"] == pytest.approx(10.0, abs=0.01), (
            f"+10% 預期(不年化),實際 {s['cum_nav_return_pct_🧮']}"
        )
        # 年化會放大 → 與全期實際必不同
        assert s["annual_nav_return_pct_🧮"] is None, "短歷史年化應為 None"

    def test_cumulative_total_equals_div_plus_nav(self):
        """全期實際含息% = 全期實際配息% + 全期實際淨值%(加總一致性)。"""
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-06-01": 10.5},
            dividend_events=[{"date": "2024-03-01", "amount": 0.3}],
            fx_rate_default=30.0,
        )
        s = r["summary"]
        expected_total = s["cum_div_rate_pct_🧮"] + s["cum_nav_return_pct_🧮"]
        assert s["cum_total_return_pct_🧮"] == pytest.approx(expected_total, abs=0.01)

    def test_long_history_cumulative_and_annual_coexist(self):
        """持有 ≥ 0.5 年:全期實際 + 年化 兩軸都該有值。"""
        # NAV 10 → 11 持有 ~1 年,1 次配息 0.5
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2025-01-01": 11.0},
            dividend_events=[{"date": "2024-06-30", "amount": 0.5}],
            fx_rate_default=30.0,
        )
        s = r["summary"]
        assert s["holding_years_🧮"] >= 0.5, "前提:持有 ≥ 0.5 年"
        # 兩軸並陳:都該有值
        assert s["cum_div_rate_pct_🧮"] is not None
        assert s["annual_div_rate_pct_🧮"] is not None
        # 持有約 1 年時,全期實際 ≈ 年化(差距小)
        assert abs(s["cum_div_rate_pct_🧮"] - s["annual_div_rate_pct_🧮"]) < 1.0

    def test_self_calc_fields_includes_cumulative(self):
        """v19.180 新欄位登錄於 _self_calc_fields(UI 染色用)。"""
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-12-31": 10.0},
            dividend_events=[],
            fx_rate_default=30.0,
        )
        fields = r["_self_calc_fields"]
        assert "summary.cum_div_rate_pct" in fields
        assert "summary.cum_nav_return_pct" in fields
        assert "summary.cum_total_return_pct" in fields

    def test_zero_dividends_cumulative_div_rate_is_zero(self):
        """無配息事件 → 全期實際配息率 = 0(非 None)。"""
        r = compute_dividend_twd_series(
            nav_series={"2024-01-01": 10.0, "2024-03-01": 10.5},
            dividend_events=[],
            fx_rate_default=30.0,
        )
        s = r["summary"]
        assert s["cum_div_rate_pct_🧮"] == 0.0
        assert s["cum_nav_return_pct_🧮"] == pytest.approx(5.0, abs=0.01)
        assert s["cum_total_return_pct_🧮"] == pytest.approx(5.0, abs=0.01)
