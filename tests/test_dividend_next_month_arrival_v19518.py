"""v19.518→525:配息月曆推播 —— 推「下個月」+ 到帳區間 + 營業日校正。

user 2026-08-24:每月推下個月預估配息月曆;到帳 = 除息 + 5~7 個**營業日**(區間);
除息日遇六日**或國定假日**一律順延至營業日(v19.525 接 `holidays` 台灣行事曆,含農曆假日 + 補假)。
- add_business_days / roll_to_business_day:純函式,跳週末 + 國定假日。
- build_summary_text:到帳時間改清單「上方」單行「約 +5~7 個營業日左右」(不再逐檔列 M/D 到帳)。
- dividend_calendar_notify.main:目標月改「下個月」(12 月 → 隔年 1 月)。
"""
from __future__ import annotations

import datetime as _dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.dividend_calendar import add_business_days, build_summary_text  # noqa: E402


# ── add_business_days:跳週末 + 國定假日 ─────────────────────────────────────
def _first_weekday_on_or_after(d, wd):
    while d.weekday() != wd:
        d += _dt.timedelta(days=1)
    return d


def test_add_business_days_friday_plus1_is_monday():
    fri = _first_weekday_on_or_after(_dt.date(2026, 1, 1), 4)   # 星期五
    got = add_business_days(fri, 1)
    assert got == fri + _dt.timedelta(days=3) and got.weekday() == 0   # → 週一(跳六日)


def test_add_business_days_friday_plus5_is_next_friday():
    fri = _first_weekday_on_or_after(_dt.date(2026, 1, 1), 4)
    got = add_business_days(fri, 5)
    assert got == fri + _dt.timedelta(days=7) and got.weekday() == 4   # 5 營業日 = 下週五(該週無假日)


def test_add_business_days_from_saturday():
    sat = _first_weekday_on_or_after(_dt.date(2026, 1, 1), 5)   # 星期六
    got = add_business_days(sat, 1)
    assert got == sat + _dt.timedelta(days=2) and got.weekday() == 0   # 六 → 下週一


def test_add_business_days_all_results_are_weekdays():
    d = _dt.date(2026, 3, 26)
    for n in range(1, 12):
        assert add_business_days(d, n).weekday() < 5      # 結果恆為工作日


def test_add_business_days_noop_paths():
    d = _dt.date(2026, 1, 2)
    assert add_business_days(d, 0) == d                   # n=0 不調整
    assert add_business_days(d, -3) == d                  # 負數不調整
    assert add_business_days(None, 5) is None             # None 原樣


def test_add_business_days_year_boundary():
    d = _dt.date(2026, 12, 30)
    got = add_business_days(d, 4)
    assert got > d and got.weekday() < 5                  # timedelta 跨年無縫、結果為工作日


# ── roll_to_business_day:除息日遇六日**或國定假日** → 順延至營業日(user 2026-08-24)──────
def test_roll_weekend_to_next_business_day():
    from services.dividend_calendar import roll_to_business_day as R
    assert R(_dt.date(2026, 8, 2)) == _dt.date(2026, 8, 3)     # 日 → 一
    assert R(_dt.date(2026, 8, 15)) == _dt.date(2026, 8, 17)   # 六 → 一(跳兩天)


def test_roll_weekday_unchanged():
    from services.dividend_calendar import roll_to_business_day as R
    for d in (_dt.date(2026, 8, 27), _dt.date(2026, 8, 31)):   # 8 月無國定假日
        assert R(d) == d and d.weekday() < 5                   # 平日不動


def test_roll_result_always_business_day():
    from services.dividend_calendar import is_business_day, roll_to_business_day as R
    d = _dt.date(2026, 1, 1)
    for _ in range(400):
        assert is_business_day(R(d)), (d, R(d))                # 任一天校正後恆為營業日
        d += _dt.timedelta(days=1)


def test_roll_keeps_month_when_forward_would_spill():
    # 月底遇週日:順延會跨到下月 → 改往前抓上一個營業日,留在本月(否則事件掉到別月格子)
    from services.dividend_calendar import roll_to_business_day as R
    _last = _dt.date(2026, 5, 31)                              # 週日
    assert _last.weekday() >= 5
    got = R(_last)
    assert got == _dt.date(2026, 5, 29) and got.month == 5      # 往前抓週五,仍在 5 月


def test_roll_bad_input_passthrough():
    from services.dividend_calendar import roll_to_business_day as R
    assert R(None) is None                                     # §1 不捏造
    assert R("2026-08-02") == "2026-08-02"                     # 非 date → 原樣


# ── 國定假日(含農曆假日 + 補假)──────────────────────────────────────────────
def test_national_holidays_are_not_business_days():
    from services.dividend_calendar import has_holiday_calendar, is_business_day
    if not has_holiday_calendar():
        import pytest
        pytest.skip("holidays 套件不可用,退化為只跳週末")
    for d in (_dt.date(2026, 1, 1),      # 元旦(週四 —— 非週末,只有假日表抓得到)
              _dt.date(2026, 2, 17),     # 春節(週二,農曆)
              _dt.date(2026, 6, 19),     # 端午(週五,農曆)
              _dt.date(2026, 9, 25),     # 中秋(週五,農曆)
              _dt.date(2026, 2, 27)):    # 和平紀念日補假(週五)
        assert d.weekday() < 5, f"{d} 應為平日才測得出假日表效果"
        assert not is_business_day(d), f"{d} 是國定假日,不應算營業日"


def test_roll_skips_lunar_new_year_block():
    from services.dividend_calendar import has_holiday_calendar, is_business_day
    from services.dividend_calendar import roll_to_business_day as R
    if not has_holiday_calendar():
        import pytest
        pytest.skip("holidays 套件不可用")
    got = R(_dt.date(2026, 2, 17))                    # 春節當天
    assert got > _dt.date(2026, 2, 20) and is_business_day(got)   # 整段連假跳過


def test_pay_window_skips_holidays():
    from services.dividend_calendar import has_holiday_calendar, is_business_day, pay_window
    if not has_holiday_calendar():
        import pytest
        pytest.skip("holidays 套件不可用")
    lo, hi = pay_window(_dt.date(2026, 2, 13))        # 春節前最後一個營業日除息
    assert is_business_day(lo) and is_business_day(hi)
    assert lo > _dt.date(2026, 2, 20)                 # 到帳日必須跨過整個春節連假


def test_pay_note_describes_actual_capability():
    # §1:文案須與實際能力一致 —— 有假日表就不可再說「未扣國定假日」
    from services.dividend_calendar import _pay_note, has_holiday_calendar
    note = _pay_note()
    if has_holiday_calendar():
        assert "已跳過週末與國定假日" in note and "未扣國定假日" not in note
    else:
        assert "未扣國定假日" in note


def test_predicted_ex_date_never_on_non_business_day():
    from services.dividend_calendar import is_business_day, predict_ex_for_month
    # 「幾號」逐一套 12 個月,推估出的除息日都不可落在週末/國定假日,且須留在目標月
    for _day in range(1, 29):
        for _m in range(1, 13):
            pred = predict_ex_for_month(_sched(_dt.date(2026, 1, _day), ex_day=_day),
                                        2026, _m, ref_year=2026, ref_month=_m)
            if pred:
                assert is_business_day(pred["ex_date"]), (_day, _m, pred["ex_date"])
                assert pred["ex_date"].month == _m          # 校正後仍留在目標月


# ── dedupe_events:同日同投信只留一筆(user 2026-08-24「這邊重複也移除」)─────────────
def _dev(house, code, day, conf="high"):
    return {"house": house, "code": code, "ex_date": _dt.date(2026, 8, day), "confidence": conf}


def test_dedupe_same_house_same_day():
    from services.dividend_calendar import dedupe_events
    out = dedupe_events([_dev("安聯", "TLZF9", 15), _dev("安聯", "TLZM7", 15)])
    assert len(out) == 1 and out[0]["house"] == "安聯"


def test_dedupe_keeps_same_house_different_days():
    from services.dividend_calendar import dedupe_events
    out = dedupe_events([_dev("安聯", "A", 15), _dev("安聯", "B", 20)])
    assert len(out) == 2                                  # 不同日不可合併(會漏掉一天的除息)


def test_dedupe_confidence_takes_most_conservative():
    from services.dividend_calendar import dedupe_events
    for order in ([_dev("安聯", "A", 15, "high"), _dev("安聯", "B", 15, "low")],
                  [_dev("安聯", "B", 15, "low"), _dev("安聯", "A", 15, "high")]):
        out = dedupe_events(order)
        assert len(out) == 1 and out[0]["confidence"] == "low"   # §1 不把低信心洗成高


def test_dedupe_unknown_house_not_merged():
    from services.dividend_calendar import dedupe_events
    out = dedupe_events([_dev("", "AAA", 15), _dev("", "BBB", 15)])
    assert len(out) == 2                                  # 判不出投信 → 退代號,兩檔各自保留


def test_dedupe_does_not_mutate_input():
    from services.dividend_calendar import dedupe_events
    evs = [_dev("安聯", "A", 15, "high"), _dev("安聯", "B", 15, "low")]
    dedupe_events(evs)
    assert evs[0]["confidence"] == "high"                 # 原始 events 不被就地改動


# ── pay_window:到帳推估「區間」= 除息 +5~7 工作天(user 2026-08-24 經驗值)──────────
def test_pay_window_is_5_to_7_business_days():
    from services.dividend_calendar import (
        _PAY_BIZ_DAYS_MAX,
        _PAY_BIZ_DAYS_MIN,
        pay_window,
    )
    assert (_PAY_BIZ_DAYS_MIN, _PAY_BIZ_DAYS_MAX) == (5, 7)
    ex = _dt.date(2026, 9, 14)                            # 週一
    lo, hi = pay_window(ex)
    assert lo == add_business_days(ex, 5) and hi == add_business_days(ex, 7)
    assert lo < hi                                        # 區間下界早於上界
    assert lo.weekday() < 5 and hi.weekday() < 5          # 兩端皆落在工作日(跳週末)


def test_pay_window_bad_date_returns_none():
    from services.dividend_calendar import pay_window
    assert pay_window(None) is None                       # §1 不捏造日期
    assert pay_window("2026-09-14") is None               # 非 date 物件 → None


# ── 陳舊度相對「現在」量,推未來月不誤降信心(v19.518 稽核 #3 修)──────────────────
def _sched(last_ex, cad="monthly", ex_day=14, conf="high"):
    return {"cadence": cad, "ex_day": ex_day, "last_ex": last_ex,
            "confidence": conf, "pay_gap_days": 7}


def test_confidence_not_downgraded_predicting_next_month():
    from services.dividend_calendar import predict_ex_for_month
    # 目標=10 月(下月)、ref=9 月(現在)、last_ex=8 月(上月)→ 陳舊 1 週期 → 信心**保留 high**
    #(修前:距目標=2 週期 → 被強制 low,幾乎每檔正常月配都中招)
    pred = predict_ex_for_month(_sched(_dt.date(2026, 8, 14)), 2026, 10, ref_year=2026, ref_month=9)
    assert pred is not None and pred["confidence"] == "high"
    assert pred["ex_date"] == _dt.date(2026, 10, 14)


def test_confidence_low_when_genuinely_stale():
    from services.dividend_calendar import predict_ex_for_month
    # last_ex=6 月、ref=8 月 → 陳舊 2 週期 → low(真的舊才降)
    pred = predict_ex_for_month(_sched(_dt.date(2026, 6, 14)), 2026, 9, ref_year=2026, ref_month=8)
    assert pred is not None and pred["confidence"] == "low"


def test_dropped_when_too_stale():
    from services.dividend_calendar import predict_ex_for_month
    # last_ex=2 月、ref=8 月 → 陳舊 6 週期(>3)→ None(疑停配/過舊,§1 不硬給)
    assert predict_ex_for_month(_sched(_dt.date(2026, 2, 14)), 2026, 9,
                                ref_year=2026, ref_month=8) is None


def test_backward_compat_no_ref_uses_target():
    from services.dividend_calendar import predict_ex_for_month
    # App 路徑:不傳 ref → ref=目標月。last_ex=上月、目標=本月 → 陳舊 1 → 信心保留(舊行為零變化)
    pred = predict_ex_for_month(_sched(_dt.date(2026, 7, 14)), 2026, 8)
    assert pred is not None and pred["confidence"] == "high"


# ── build_summary_text:到帳註記 ───────────────────────────────────────────
def _cal_one(ex, month=9, year=2026):
    return {"year": year, "month": month,
            "events": [{"code": "TLZF9", "name": "安聯", "house": "安聯", "ex_date": ex,
                        "pay_date_est": None, "confidence": "high",
                        "last_amount": 0.05, "last_yield": 6.0, "n": 12}],
            "excluded": [], "unpredictable": [], "counts": {}}


def test_summary_arrival_note_above_list_not_per_item():
    # user 2026-08-24:到帳時間不逐檔列,改在清單「上方」一句「約 +5 個工作天左右」。
    ex = _dt.date(2026, 9, 14)
    txt = build_summary_text(_cal_one(ex))
    assert "除息" in txt
    assert "9/14 除息" in txt                             # 逐檔只列除息日 + 名稱
    arr = add_business_days(ex, 5)
    assert f"{arr.month}/{arr.day} 到帳" not in txt       # 不再逐檔列到帳日期
    assert "營業日左右" in txt                            # 清單上方單行到帳說明
    assert "基金公司作業為準" in txt                      # 誠實旗標(仍是推估)
    # 到帳說明必須在第一檔清單列「之上」
    lines = txt.splitlines()
    _note_i = next(i for i, ln in enumerate(lines) if "營業日左右" in ln)
    _list_i = next(i for i, ln in enumerate(lines) if ln.startswith("•"))
    assert _note_i < _list_i


def test_summary_title_shows_target_month_roc():
    txt = build_summary_text(_cal_one(_dt.date(2026, 9, 14)))
    assert "民國115年9月" in txt                          # 2026-1911=115;標題顯示目標(下)月


def test_summary_no_events_omits_arrival():
    cal = {"year": 2026, "month": 9, "events": [], "excluded": [], "unpredictable": [], "counts": {}}
    txt = build_summary_text(cal)
    assert "無推估除息" in txt and "到帳" not in txt       # 無事件 → 不列到帳說明


# ── notify main:目標月 = 下個月 ────────────────────────────────────────────
from scripts import dividend_calendar_notify as M  # noqa: E402


def test_main_targets_next_month(monkeypatch):
    import scripts.weekly_switch_notify as W
    monkeypatch.setattr(W, "_load_client_and_sheet", lambda: ("client", "sid"))
    monkeypatch.setattr(W, "_read_holdings", lambda c, s: ["AAA"])
    monkeypatch.setattr(W, "_read_watchlist", lambda: [])
    # 抓成功(dividends 為 list,累積型空 list 也算 fetched)
    monkeypatch.setattr(M, "_fetch_divs",
                        lambda codes: [{"code": "AAA", "name": "AAA", "house": "", "dividends": []}])
    _cap = {}
    # main() 內以 `from services.dividend_calendar import build_month_calendar` lazy import,
    # 故 patch 來源模組(呼叫時才綁定 → 取到 patched 版)。
    import services.dividend_calendar as DC
    _orig = DC.build_month_calendar

    def _spy(funds, year, month, **kw):
        _cap["ym"] = (year, month)
        _cap["ref"] = (kw.get("ref_year"), kw.get("ref_month"))
        return _orig(funds, year, month, **kw)
    monkeypatch.setattr(DC, "build_month_calendar", _spy)

    assert M.main(["--dry-run"]) == 0
    _now = _dt.datetime.now(_dt.timezone(_dt.timedelta(hours=8)))
    assert _cap["ym"] != (_now.year, _now.month)          # 不是本月
    assert _cap["ym"][1] == (_now.month % 12) + 1         # 月份=下月(獨立算式,非沿用程式判斷)
    assert _cap["ref"] == (_now.year, _now.month)         # 陳舊度 ref = 本月(現在)
