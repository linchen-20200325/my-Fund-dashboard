"""tests — `compute_dividend_twd_series` 買進日過濾 + 日期格式正規化守衛。

**修的 P0 bug**:`services/health/dividend_calc.py` 原 `:273` 寫
``ex_date = str(ev.get("date") or "")[:10]``(**沒有** `.replace("/", "-")`),
而 `buy_date` 來自 pandas DatetimeIndex → 恆為 ISO。MoneyDJ 配息日期是斜線格式
(`repositories/fund/sources.py:2611` / `fund_orchestration.py:973` 直接吃 HTML cell)。
ASCII `'/'`=0x2F > `'-'`=0x2D,故 `"2026/01/30" < "2026-06-22"` 回 **False**
→ `continue` 不執行 → **買進日之前的配息被算進累積配息**。

失效條件:**ex 年 ≥ buy 年時必失效**(同年 100% 失效);ex 年 < buy 年時仍會正確過濾
(因為第 1~4 字元的年份就分出勝負,輪不到第 5 字元的分隔符)。兩種情境本檔都有守。

fixture 說明(§3.3 反捏造):本檔所有數值皆為**測試 fixture**,不流入 production
路徑;`TestGoldenACCP138` 的輸入取自線上實測觀察到的真實參數,用來把「正確答案」
釘死成回歸測試。
"""
from __future__ import annotations

import pytest

from services.health.dividend_calc import (
    _norm_date,
    compute_dividend_twd_series,
)


# ════════════════════════════════════════════════════════════════
# 0. _norm_date SSOT 本身
# ════════════════════════════════════════════════════════════════
class TestNormDate:
    def test_slash_to_dash(self):
        assert _norm_date("2026/01/30") == "2026-01-30"

    def test_iso_passthrough(self):
        assert _norm_date("2026-06-22") == "2026-06-22"

    def test_truncates_to_10_chars(self):
        assert _norm_date("2026/01/30 00:00:00") == "2026-01-30"
        assert _norm_date("2026-01-30T08:00:00+08:00") == "2026-01-30"

    def test_empty_and_none(self):
        assert _norm_date(None) == ""
        assert _norm_date("") == ""

    def test_normalized_slash_now_compares_correctly(self):
        """bug 的數學本體:未正規化時字串比較方向是反的。"""
        # 修前(raw 比較)—— 這正是 bug
        assert not ("2026/01/30" < "2026-06-22")
        # 修後(過 _norm_date)
        assert _norm_date("2026/01/30") < _norm_date("2026-06-22")


# ════════════════════════════════════════════════════════════════
# 1. P0 核心:斜線 ex_date vs ISO buy_date
# ════════════════════════════════════════════════════════════════
class TestSlashExDateFiltering:
    """MoneyDJ 斜線日期 + ISO buy_date 的過濾正確性。"""

    def test_same_year_slash_before_buy_is_filtered(self):
        """ex 年 == buy 年 → 修前 100% 失效的情境,必須被濾掉。"""
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[{"date": "2026/01/30", "amount": 0.5}],
            fx_rate_default=32.0,
        )
        assert r["ok"] is True
        assert r["n_events"] == 0, "買進日前的斜線配息仍被計入(P0 bug 復發)"
        assert r["summary"]["total_twd_div_🧮"] == 0

    def test_same_year_slash_after_buy_is_kept(self):
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[{"date": "2026/06/30", "amount": 0.5}],
            fx_rate_default=32.0,
        )
        assert r["n_events"] == 1
        assert r["events"][0]["ex_date"] == "2026-06-30", "輸出應為正規化 ISO"

    def test_cross_year_slash_before_buy_is_filtered(self):
        """跨年:舊 code 碰巧會對(年份先分勝負),新 code 也必須對。"""
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[{"date": "2025/12/30", "amount": 0.5}],
            fx_rate_default=32.0,
        )
        assert r["n_events"] == 0

    def test_mixed_slash_and_iso_events_all_correct(self):
        """同一批混格式(MoneyDJ 斜線 + FundClear ISO)—— 過濾與排序都要對。"""
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[
                {"date": "2026/07/31", "amount": 0.1},   # 後,斜線
                {"date": "2026-01-15", "amount": 0.1},   # 前,ISO
                {"date": "2026/06/30", "amount": 0.1},   # 後,斜線
                {"date": "2026-07-15", "amount": 0.1},   # 後,ISO
                {"date": "2025/11/30", "amount": 0.1},   # 前(跨年),斜線
            ],
            fx_rate_default=32.0,
        )
        assert r["n_events"] == 3
        assert [e["ex_date"] for e in r["events"]] == [
            "2026-06-30", "2026-07-15", "2026-07-31",
        ], "混格式排序必須落在同一個正規化字串空間"

    def test_nav_series_slash_keys_also_normalized(self):
        """nav_series key 若也是斜線 → 與 ex_date 同空間,過濾仍正確。"""
        r = compute_dividend_twd_series(
            nav_series={"2026/06/22": 10.0, "2026/08/03": 10.0},
            dividend_events=[
                {"date": "2026/01/30", "amount": 0.5},   # 買進前
                {"date": "2026/06/30", "amount": 0.5},   # 買進後
            ],
            fx_rate_default=32.0,
        )
        assert r["buy_date"] == "2026-06-22"
        assert r["n_events"] == 1
        assert r["events"][0]["ex_date"] == "2026-06-30"


# ════════════════════════════════════════════════════════════════
# 2. 邊界
# ════════════════════════════════════════════════════════════════
class TestBuyDateBoundaries:
    def test_ex_date_equals_buy_date_is_included(self):
        """**買進當日除息 → 目前計入**(`ex_date < buy_date` 才 skip)。

        本 test 是「釘住現況契約」而非「宣告業務正確」:嚴格的除息權益規則是
        「除息日當天買進**不**享有該次配息」(當日 NAV 已是除息後價),因此業務上
        傾向應改成 `<=` 排除。但這會改變既有判定語意,超出本次 P0 修補範圍,
        已列入報告請 user 裁決;在裁決前先用測試把行為釘死,避免無聲飄移。
        """
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[{"date": "2026/06/22", "amount": 0.5}],
            fx_rate_default=32.0,
        )
        assert r["n_events"] == 1
        assert r["events"][0]["ex_date"] == r["buy_date"] == "2026-06-22"

    def test_empty_dividends(self):
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[],
            fx_rate_default=32.0,
        )
        assert r["ok"] is True
        assert r["n_events"] == 0
        assert r["summary"]["total_ccy_div_🧮"] == 0
        assert r["summary"]["cum_div_rate_pct_🧮"] == 0.0

    def test_none_dividends(self):
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=None,  # type: ignore[arg-type]
            fx_rate_default=32.0,
        )
        assert r["ok"] is True
        assert r["n_events"] == 0

    def test_all_events_before_buy_date(self):
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[
                {"date": "2026/01/30", "amount": 0.07},
                {"date": "2026/02/26", "amount": 0.07},
                {"date": "2025/12/31", "amount": 0.07},
            ],
            fx_rate_default=32.0,
        )
        assert r["n_events"] == 0
        assert r["summary"]["total_twd_div_🧮"] == 0
        assert r["summary"]["cum_div_rate_pct_🧮"] == 0.0

    def test_all_events_after_buy_date(self):
        r = compute_dividend_twd_series(
            nav_series={"2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[
                {"date": "2026/06/30", "amount": 0.07},
                {"date": "2026/07/31", "amount": 0.07},
            ],
            fx_rate_default=32.0,
        )
        assert r["n_events"] == 2

    def test_blank_nav_key_does_not_defeat_filter(self):
        """空字串 NAV key 若被當 buy_date → `ex < ""` 恆 False,過濾整條失效。"""
        r = compute_dividend_twd_series(
            nav_series={"": 10.0, "2026-06-22": 10.0, "2026-08-03": 10.0},
            dividend_events=[{"date": "2026/01/30", "amount": 0.5}],
            fx_rate_default=32.0,
        )
        assert r["buy_date"] == "2026-06-22"
        assert r["n_events"] == 0


# ════════════════════════════════════════════════════════════════
# 3. golden test — ACCP138 線上實測數字
# ════════════════════════════════════════════════════════════════
class TestGoldenACCP138:
    """線上實測損害場景(fixture,非 production 資料)。

    觀察到的輸入:買進日 2026-06-22、買進 FX 32.379、持有單位 3,607.9689、
    本金 100 萬 TWD、6 筆月配 0.07/單位(2026/01/30 ~ 2026/06/30)。
      principal_ccy = 1,000,000 / 32.379          = 30,884.21
      units         = 30,884.21 / buy_nav(8.56)   =  3,607.9689  ✅ 對得上
      單筆 twd_div  = 0.07 × 3,607.9689 × 32.379  =  8,177.6 → round 8,178

    修前畫面「累積 TWD 配息」= 49,065 = 8,177.6 × 6(6 筆全被算進去);
    正解只有 2026/06/30 在買進日之後 → 8,178。高估 40,888 TWD。
    """

    BUY_FX = 32.379
    BUY_NAV = 8.56
    PRINCIPAL_TWD = 1_000_000.0
    DIV_PER_UNIT = 0.07
    # MoneyDJ raw 斜線格式(fixture)
    DIV_DATES = ["2026/01/30", "2026/02/26", "2026/03/31",
                 "2026/04/30", "2026/05/29", "2026/06/30"]

    def _run(self):
        return compute_dividend_twd_series(
            nav_series={
                "2026-06-22": self.BUY_NAV,   # 買進日
                "2026-06-30": 8.26,           # 除息日 NAV
                "2026-08-03": 8.26,           # 末日(持有 42 天)
            },
            dividend_events=[
                {"date": d, "amount": self.DIV_PER_UNIT} for d in self.DIV_DATES
            ],
            fx_rate_default=self.BUY_FX,
            principal_twd=self.PRINCIPAL_TWD,
        )

    def test_fixture_reproduces_observed_units(self):
        """前提檢查:fixture 的 units 必須重現線上觀察值 3,607.9689。"""
        r = self._run()
        assert r["units_held_🧮"] == pytest.approx(3607.9689, abs=0.01)
        assert r["buy_fx"] == pytest.approx(32.379, abs=1e-4)
        assert r["buy_date"] == "2026-06-22"

    def test_only_one_event_survives_filter(self):
        r = self._run()
        assert r["n_events"] == 1, (
            f"只有 2026/06/30 在買進日之後,實得 {r['n_events']} 筆:"
            f"{[e['ex_date'] for e in r['events']]}"
        )
        assert r["events"][0]["ex_date"] == "2026-06-30"

    def test_total_twd_dividend_is_8178_not_49065(self):
        """golden:累積 TWD 配息 = 8,178(修前 49,065,6 倍高估)。"""
        r = self._run()
        total = r["summary"]["total_twd_div_🧮"]
        assert total == pytest.approx(8178, abs=1), (
            f"預期 8,178,實得 {total}"
        )
        assert total != pytest.approx(49065, abs=2), "6 倍高估的 bug 復發"

    def test_single_event_div_pct_matches_observed(self):
        """單筆配息率 = 0.07 / 8.26 = 0.847%(線上畫面同值)。"""
        r = self._run()
        assert r["events"][0]["single_event_div_pct_🧮"] == pytest.approx(
            0.847, abs=0.001)

    def test_short_holding_annual_fields_are_none(self):
        """持有 42 天(0.115 年)< 0.5 年 → 年化欄誠實 None + ⬜ 歷史不足(§1)。"""
        r = self._run()
        s = r["summary"]
        assert s["holding_years_🧮"] < 0.5
        assert s["annual_div_rate_pct_🧮"] is None
        assert s["annual_nav_return_pct_🧮"] is None
        assert s["ret_1y_total_pct_🧮"] is None
        assert s["div_health_light_🧮"] == "歷史不足"
        assert s["div_health_emoji_🧮"] == "⬜"

    def test_cumulative_rates_use_single_surviving_event(self):
        """全期實際配息率 = 單筆配息(原幣)/ 原幣本金 —— 不含被濾掉的 5 筆。"""
        r = self._run()
        s = r["summary"]
        expected_ccy = self.DIV_PER_UNIT * r["units_held_🧮"]
        assert s["total_ccy_div_🧮"] == pytest.approx(expected_ccy, abs=0.05)
        expected_pct = expected_ccy / r["principal_ccy_🧮"] * 100.0
        assert s["cum_div_rate_pct_🧮"] == pytest.approx(expected_pct, abs=0.01)


# ════════════════════════════════════════════════════════════════
# §6 自審「3 個最容易讓這段程式出錯的輸入」
#   1. 斜線 ex_date + ISO buy_date 且**同年** → TestSlashExDateFiltering
#      .test_same_year_slash_before_buy_is_filtered(修前 100% 失效)
#   2. 同一批 dividend_events **混格式** → test_mixed_slash_and_iso_events_all_correct
#      (排序鍵若沒正規化,`/` > `-` 會把 list 切成兩段,events 順序錯亂)
#   3. nav_series 含**空字串 / 斜線 key** → test_blank_nav_key_does_not_defeat_filter
#      + test_nav_series_slash_keys_also_normalized(buy_date 落在錯誤比較空間 →
#      過濾整條失效,與 bug 本體同源)
# ════════════════════════════════════════════════════════════════
