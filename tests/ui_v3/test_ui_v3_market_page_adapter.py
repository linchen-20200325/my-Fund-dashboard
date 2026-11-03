# -*- coding: utf-8 -*-
"""🌍 頁 adapter 契約（BL-0536 rendering 批；BACKLOG BL-0536-H2／H3 的 rendering-batch adapter 要求逐條有測試）。

取數替身只在測試端（`market_stubs.py`）；adapter 吃的是真的 `market_view.build_market_view` 輸出形狀。⚠️ 數值是人造的。
"""
from __future__ import annotations

import copy
import decimal
import math
import re
from datetime import date

import numpy as np
import pytest

import market_stubs as ms
from services.v2_domain import periods
from services.v2_tables import market_indicator as mi
from services.v2_tables import market_view as mv
from shared.ui_semantics import rules
from ui_v3.adapters import market_page as a
from ui_v3.viewmodels import market_page as vm
from ui_v3.viewmodels.common import STATUS_FAILED, STATUS_MISSING, STATUS_OK, STATUS_UNDETERMINED


def build(v=None, t=None, **kw):
    kw.setdefault("period", "1Y")
    return a.build_market_page(v or ms.view(), t or ms.table(), **kw)


# ───────── 取數緩衝（A2 週末／休市起點；不改 normalize_pair） ─────────

def _months(range_text: str) -> int:
    m = re.fullmatch(r"(\d+)y", range_text)
    assert m, range_text
    return int(m.group(1)) * 12


def test_fetch_range_covers_longest_period_plus_margin():
    """取數範圍（market_view 常數）＞ 最長期間 3Y 至少 12 個月 → 視窗起點前一定還有歷史（A2 的前提）。"""
    longest = max(periods.PERIOD_MONTHS.values())
    for range_ in (mv.TAIEX_RANGE, mv.SP500_RANGE, mv.VIX_RANGE):
        assert _months(range_) >= longest + 12, range_
    # FRED：日頻約每年 260 筆；1500 筆 ≥ (3Y＋1Y 緩衝) × 260
    assert mv.FRED_VIEW_OBSERVATION_LIMIT >= (longest // 12 + 1) * 260


def test_yahoo_is_fetched_with_daily_interval_default(monkeypatch):
    """日頻保證：market_view 只傳 (ticker, range)，沒有改 interval（L1 預設 1d）；本頁不吃非日頻序列進歸一化。"""
    calls = []

    def fetch(*args, **kwargs):
        calls.append((args, kwargs))
        return None, "stub"
    mv.build_market_view(fetch_vix=fetch, fetch_taiex=fetch, fetch_sp500=fetch, fred_api_key="")
    assert [(args, kwargs) for args, kwargs in calls] == [(("^VIX", "5y"), {}), (("^TWII", "5y"), {}), (("^GSPC", "5y"), {})]


@pytest.mark.parametrize("period", ["3M", "6M", "1Y", "3Y"])
def test_weekend_window_start_is_ok_not_insufficient_when_margin_is_present(period):
    """視窗起點落在週末（最後觀測日 2026-11-02：3M→08-02 日、6M→05-02 六）：餵足 margin → ok，基準日＝起點後第一個共同有效日。"""
    model = build(period=period)
    d = model.primary_card.disclosure
    assert d.status == "ok" and d.mode == "pair" and d.comparable, (period, d)
    assert date.fromisoformat(d.base_date) >= date.fromisoformat(d.window_start)
    assert model.evidence_comparable and all(c.status == STATUS_OK for c in model.evidence_changes)
    if period in ("3M", "6M"):
        assert date.fromisoformat(d.window_start).weekday() >= 5, "此案例要的就是週末起點"
        assert date.fromisoformat(d.base_date).weekday() < 5


def test_negative_control_without_margin_weekend_start_is_insufficient():
    """負控（記錄殘留邊界、不是要它發生）：若取數只給剛好 3 個月、第一筆在週末視窗起點之後的下一個交易日 → insufficient。"""
    dates_us = ms.weekdays("2026-08-03", ms.LAST_US)
    dates_tw = ms.weekdays("2026-08-03", ms.LAST_US)
    v = ms.view(tw_dates=dates_tw, us_dates=dates_us)
    model = build(v, period="3M")
    assert model.primary_card.disclosure.status != "ok" or model.primary_card.disclosure.mode != "pair"
    assert not model.evidence_comparable


# ───────── 收盤值轉 float／台北時區／負經過天數 ─────────

@pytest.mark.parametrize("raw,expected", [
    (np.int64(5), 5.0), (np.float32(1.5), 1.5), (decimal.Decimal("2.5"), 2.5), (7, 7.0), ("3.25", 3.25),
    (True, None), (False, None), (None, None), (float("nan"), None), (float("inf"), None), ("x", None), (object(), None),
])
def test_to_float(raw, expected):
    got = a.to_float(raw)
    assert got == expected and (got is None or type(got) is float)


def test_numpy_and_decimal_closes_are_not_dropped_as_gaps():
    """H1b／H2 要求：numpy.int64／Decimal 會被 periods.is_number 當缺口；經 adapter 後仍是有效值。"""
    v = ms.view()
    for d in v["domains"]:
        if d["domain"] in ("taiex", "sp500"):
            d["points"] = [{"obs_date": p["obs_date"],
                            "value_num": np.int64(round(p["value_num"])) if i % 2 else decimal.Decimal(str(p["value_num"]))}
                           for i, p in enumerate(d["points"])]
    model = build(v, period="1Y")
    assert model.primary_card.disclosure.status == "ok"
    assert all(len([p for p in s.points if p.value is not None]) > 200 for s in model.primary_card.series)


def test_elapsed_days_use_taipei_date_not_utc():
    """fetched_at＝UTC 2026-11-02 20:00＝台北 2026-11-03 04:00；資料日 11-02 → 台北經過 1 日（UTC 日期口徑會是 0）。"""
    v = ms.view()
    for d in v["domains"]:
        if d["domain"] in ("taiex", "sp500"):
            d["fetched_at"] = "2026-11-02T20:00:00+00:00"
    notes = {n.key: n for n in build(v, period="1Y").primary_notes}
    assert notes["taiex"].elapsed_days == 1 and notes["sp500"].elapsed_days == 1
    utc = {n.key: n for n in build(v, period="1Y", tz=None).primary_notes}   # 對照：tz=None 取字串前 10 碼
    assert utc["taiex"].elapsed_days == 0


def test_negative_elapsed_days_are_kept_not_zeroed():
    v = ms.view()
    for d in v["domains"]:
        if d["domain"] == "taiex":
            d["fetched_at"] = "2026-10-30T02:00:00+00:00"   # 取得時間早於資料日 11-02
    note = {n.key: n for n in build(v).primary_notes}["taiex"]
    assert note.as_of == "2026-11-02" and note.elapsed_days == -3


# ───────── 取數失敗與缺資料分開；原文不進 view model ─────────

def test_failed_and_missing_are_separate_states():
    failed = build(ms.view(us="error"))
    assert failed.comparison_mode == "single" and not failed.evidence_comparable
    states = {c.key: (c.status, c.reason_code) for c in failed.evidence_changes}
    assert states == {"taiex": (STATUS_OK, None), "sp500": (STATUS_FAILED, "fetch_failed")}
    sp = failed.primary_card.series[1]
    assert sp.meta.status == STATUS_FAILED and sp.points == () and failed.primary_card.detail == ()   # 不放 MissingItem

    missing = build(ms.view(us="missing"))
    states = {c.key: (c.status, c.reason_code) for c in missing.evidence_changes}
    assert states["sp500"] == (STATUS_MISSING, "missing")
    assert [d.what for d in missing.primary_card.detail] == ["S&P 500"]   # 缺資料才放 MissingItem（呈現 ◇ 資料未備）


def test_failure_original_text_never_enters_the_view_model():
    model = build(ms.view(us="error", vx="error"))
    assert "secret-token-abc123" not in repr(model)


def test_missing_fred_key_is_not_configured_not_fetch_failed():
    """缺 FRED 金鑰 → failed＋not_configured（呈現 `⛔ 尚未設定`，不寫成取數失敗；44 之十二其二第 1 條）。"""
    v = ms.view(key="")
    t = ms.table(errors={"credit_spread_pct": mi.MISSING_FRED_API_KEY, "term_spread_pct": "HTTP 500"}, drop=("credit_spread_pct", "term_spread_pct"))
    model = build(v, t, primary_view="us10y")
    note = model.primary_notes[0]
    assert (note.status, note.reason_code) == (STATUS_FAILED, "not_configured")
    credit = build(v, t, rates_key="credit_spread_pct").secondary[-1]
    assert (credit.status, credit.reason_code) == (STATUS_FAILED, "not_configured")
    term = build(v, t, rates_key="term_spread_pct").secondary[-1]
    assert (term.status, term.reason_code) == (STATUS_FAILED, "fetch_failed")


# ───────── 部分資料（B2／C2／withheld） ─────────

def test_insufficient_history_falls_back_to_single_and_names_the_reason():
    """3Y 而 S&P 只有約 2 年歷史 → B2：fallback、S&P insufficient、台股仍畫（單序列，不是比較）。"""
    v = ms.view(us_dates=ms.weekdays("2024-11-01", ms.LAST_US))
    model = build(v, period="3Y")
    d = model.primary_card.disclosure
    assert d.mode == "fallback" and d.fallback_reason == "insufficient" and not d.comparable
    states = {c.key: (c.status, c.reason_code) for c in model.evidence_changes}
    assert states == {"taiex": (STATUS_OK, None), "sp500": (STATUS_UNDETERMINED, "insufficient")}
    assert not model.evidence_comparable and model.comparison_mode == "fallback"


def test_withheld_series_reports_the_comparison_status_as_reason():
    """兩條都夠點數但沒有任何共同有效日（一條只有週一、一條只有週二）→ 兩條 withheld；真正原因 no_common_base 取自比較層狀態。"""
    mondays = [d for d in ms.long_us_dates() if date.fromisoformat(d).weekday() == 0]
    tuesdays = [d for d in ms.long_us_dates() if date.fromisoformat(d).weekday() == 1]
    v = ms.view(tw_dates=mondays, us_dates=tuesdays)
    model = build(v, period="1Y")
    assert model.primary_card.disclosure.status == "no_common_base"
    reasons = {c.key: c.reason_code for c in model.evidence_changes}
    assert reasons == {"taiex": "no_common_base", "sp500": "no_common_base"}
    assert all(s.points == () for s in model.primary_card.series)


# ───────── Primary 檢視、Secondary 讓位、依據卡 ─────────

def test_primary_vix_hides_secondary_vix_card_and_primary_is_single_series():
    model = build(primary_view="vix")
    assert [c.key for c in model.secondary] == ["term_spread_pct"]
    assert not model.primary_card.normalized and len(model.primary_card.series) == 1
    assert model.primary_unit == "index"
    # 首屏依據仍是 TAIEX／S&P 比較（與 Primary 檢視無關）
    assert [c.key for c in model.evidence_changes] == ["taiex", "sp500"] and model.evidence_comparable


def test_vix_yield_ruling_secondary_count_follows_primary_view_and_never_backfills():
    """客戶裁示 DEC-2026-11-03-06：Primary＝VIX 時 VIX 卡讓位；切回比較／美10Y／美2Y 恢復；不補卡、張數隨檢視變。"""
    by_view = {v: [c.key for c in build(primary_view=v).secondary] for v in ("compare", "vix", "us10y", "us2y")}
    assert by_view["vix"] == ["term_spread_pct"]                                   # 讓位後只剩利率與信用，沒有補入其他卡
    for v in ("compare", "us10y", "us2y"):
        assert by_view[v] == ["vix", "term_spread_pct"]                            # 恢復顯示
    assert len(by_view["vix"]) < len(by_view["compare"])                           # 張數可隨檢視變化
    assert "sp500" not in {k for ks in by_view.values() for k in ks}               # 也沒有補回已移除的 S&P 卡


@pytest.mark.parametrize("view_key,unit", [("us10y", "%"), ("us2y", "%")])
def test_yield_views_are_single_series_in_percent(view_key, unit):
    model = build(primary_view=view_key)
    assert [c.key for c in model.secondary] == ["vix", "term_spread_pct"]
    assert model.primary_unit == unit
    s = model.primary_card.series[0]
    assert s.meta.status == STATUS_OK and s.meta.as_of == model.primary_notes[0].as_of


def test_single_view_period_longer_than_history_is_insufficient_not_shortened():
    v = ms.view()
    model = build(v, period="3Y", primary_view="vix")
    assert model.primary_card.series[0].meta.status == STATUS_OK
    short_dates = ms.weekdays("2025-11-01", ms.LAST_US)
    short = ms.view(vx=(ms.vix(short_dates, ms.wave(len(short_dates), 18, 0, 3)), None))
    model = build(short, period="3Y", primary_view="vix")
    s = model.primary_card.series[0]
    assert s.meta.status == STATUS_UNDETERMINED and s.meta.reason_code == "insufficient" and s.points == ()
    assert model.primary_notes[0].as_of == ms.LAST_US   # 資料日照實


def test_evidence_changes_equal_chart_end_values_minus_base():
    """首屏漲跌與圖同一個基準：＝圖上該序列末點歸一化值減 100（同一個 NormalizedComparison，不另算）。"""
    for period in ("3M", "1Y", "3Y"):
        model = build(period=period)
        by_key = {c.key: c.period_change for c in model.evidence_changes}
        for label, series in zip(("taiex", "sp500"), model.primary_card.series):
            last = [p.value for p in series.points if p.value is not None][-1]
            assert math.isclose(by_key[label], last - 100)
            assert series.points[0].value == 100


def test_each_series_is_drawn_to_its_own_last_observation_date():
    model = build(ms.view(us_dates=ms.weekdays("2021-06-01", "2026-10-30")), period="1Y")
    dates = {n.key: n.as_of for n in model.primary_notes}
    assert dates == {"taiex": "2026-11-02", "sp500": "2026-10-30"}
    ends = {s.label: s.points[-1].date for s in model.primary_card.series}
    assert ends == {"台股": "2026-11-02", "S&P 500": "2026-10-30"}


def test_evidence_cards_state_facts_without_judgement_and_stay_missing_when_no_source():
    model = build()
    assert [c.code for c in model.evidence_cards] == ["MKT-1", "MKT-2", "MKT-3"]
    mkt2 = model.evidence_cards[1].facts[0]
    assert (mkt2.status, mkt2.reason_code, mkt2.value) == (STATUS_MISSING, "ndc_no_release_date", None)
    fx = model.evidence_cards[2].facts[1]
    assert (fx.status, fx.reason_code, fx.value) == (STATUS_MISSING, "fx_obs_date_rule", None)   # 匯率維持資料未備（閘門關）
    assert all(f.status == STATUS_OK for f in model.evidence_cards[0].facts)
    # 沒有 rule_ref、沒有判斷欄位
    assert not any(hasattr(f, "rule_ref") for c in model.evidence_cards for f in c.facts)


def test_missing_group_lists_the_seven_sources_without_formal_data():
    model = build()
    assert [m.key for m in model.missing] == ["taiex_volume", "market_stats", "nasdaq", "msci_world", "msci_em",
                                              "eps_pe_scenario", "implied_trailing_index_earnings"]
    assert all(m.status == STATUS_MISSING and m.reason_code for m in model.missing)


# ───────── 常數與 L2 鎖、輸入驗證 ─────────

def test_literals_copied_from_lower_layers_match_them():
    assert (a._STATE_OK, a._STATE_MISSING, a._STATE_BIZ, a._STATE_ERROR) == (mv.STATE_OK, mv.STATE_MISSING, mv.STATE_BIZ, mv.STATE_ERROR)
    assert a.MISSING_FRED_API_KEY_TEXT == mi.MISSING_FRED_API_KEY
    assert a.REASON_NOT_CONFIGURED == rules.REASON_NOT_CONFIGURED
    for key in vm.RATES_KEYS:
        spec = mi.INDICATOR_SPECS[key]
        assert a._RATES_UNIT[key] == spec["value_unit"]
        assert a._RATES_SOURCE[key] == f"{spec['source'][0]} ({spec['source'][1]})"
    assert [k for k, _ in a._MISSING_DOMAINS] == [k for k in mv._MISSING_DOMAINS]
    assert a.TAIPEI.key == "Asia/Taipei"


def test_unknown_domain_status_and_bad_arguments_fail_loud():
    with pytest.raises(ValueError):
        a.domain_state({"status": mv.STATE_BIZ})
    with pytest.raises(ValueError):
        build(period="2Y")
    with pytest.raises(ValueError):
        build(primary_view="sp500")
    with pytest.raises(ValueError):
        build(rates_key="nope")


def test_adapter_does_not_mutate_inputs():
    v, t = ms.view(), ms.table()
    before = (copy.deepcopy(v), copy.deepcopy(t))
    build(v, t, period="6M", primary_view="us2y", rates_key="policy_rate_pct")
    assert (v, t) == before


def test_load_orders_b_line_before_market_view_and_passes_the_key_only_to_l2(monkeypatch):
    """load()：B 線先、market_view 後；金鑰只交給 L2。L1 全替身（不打網路）。"""
    order = []
    monkeypatch.setattr(mi, "build_market_indicator_table",
                        lambda *, fred_api_key=None, sink=None: order.append(("table", fred_api_key)) or {"rows": [], "errors": {}, "pending": {}})
    monkeypatch.setattr(mv, "build_market_view",
                        lambda *, fred_api_key=None, **kw: order.append(("view", fred_api_key)) or {"domains": []})
    view, table = a.load([{"FRED_API_KEY": "abc"}, {"FRED_API_KEY": "zzz"}])
    assert order == [("table", "abc"), ("view", "abc")] and view == {"domains": []} and table["rows"] == []
    order.clear()
    a.load([None, {}])
    assert order == [("table", ""), ("view", "")]
