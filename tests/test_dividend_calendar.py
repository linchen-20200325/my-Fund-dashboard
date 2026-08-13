"""L2 除息/配息行事曆推估(services/dividend_calendar,v19.443)。

守:頻率判定(月/季/年)、除息日推估(固定幾號 + 月底夾擠)、入帳日推估(除息+間隔)、
confidence 分級、季配空月不列、無配息落排除、容錯(ex_date 退 date / pay 缺)、§1 不硬給。
"""
from __future__ import annotations

import datetime as _dt

from services.dividend_calendar import (
    build_month_calendar,
    build_summary_text,
    detect_house,
    infer_schedule,
    predict_ex_for_month,
)


def _monthly_divs(day=14, start=(2025, 8), n=12, amount=0.05, pay_gap=30):
    """產 n 筆每月配息(除息日固定 day 號),含 pay_date = ex + pay_gap。"""
    y, m = start
    out = []
    for _ in range(n):
        ex = _dt.date(y, m, day)
        pay = ex + _dt.timedelta(days=pay_gap)
        out.append({"ex_date": ex.isoformat(), "pay_date": pay.isoformat(),
                    "amount": amount, "yield_pct": 6.0})
        m += 1
        if m > 12:
            m = 1
            y += 1
    return out


# ── infer_schedule ─────────────────────────────────────────
def test_monthly_cadence_high_confidence():
    s = infer_schedule(_monthly_divs(day=14, n=12))
    assert s["cadence"] == "monthly" and s["ex_day"] == 14
    assert s["confidence"] == "high" and s["n"] == 12
    assert s["pay_gap_days"] == 30


def test_quarterly_cadence():
    divs = [{"ex_date": f"2025-{m:02d}-15"} for m in (2, 5, 8, 11)] + [{"ex_date": "2026-02-15"}]
    s = infer_schedule(divs)
    assert s["cadence"] == "quarterly" and s["confidence"] == "medium"


def test_single_record_is_low_confidence():
    s = infer_schedule([{"ex_date": "2026-01-10"}])
    assert s["cadence"] == "single" and s["confidence"] == "low" and s["n"] == 1


def test_none_when_no_dividends():
    s = infer_schedule([])
    assert s["cadence"] == "none" and s["confidence"] == "none"


def test_ex_date_falls_back_to_date_and_pay_optional():
    """只有 date(cnyes 型)→ 當除息日;無 pay_date → pay_gap None(不硬編)。"""
    divs = [{"date": f"2025-{m:02d}-20", "amount": 0.03} for m in range(1, 8)]
    s = infer_schedule(divs)
    assert s["cadence"] == "monthly" and s["ex_day"] == 20 and s["pay_gap_days"] is None


def test_bad_dates_skipped():
    divs = [{"ex_date": "2026-01-14"}, {"ex_date": "not-a-date"}, {"ex_date": "2026-02-14"}]
    s = infer_schedule(divs)
    assert s["n"] == 2                     # 壞日期被丟,不炸


# ── predict_ex_for_month ───────────────────────────────────
def test_predict_monthly_target_month():
    s = infer_schedule(_monthly_divs(day=14, n=12, pay_gap=30))
    p = predict_ex_for_month(s, 2026, 8)
    assert p["ex_date"] == _dt.date(2026, 8, 14)
    assert p["pay_date_est"] == _dt.date(2026, 8, 14) + _dt.timedelta(days=30)


def test_predict_clamps_to_month_end():
    """除息日 30 號 → 2 月只有 28 天 → 夾到 28(不溢位)。"""
    s = infer_schedule(_monthly_divs(day=30, start=(2025, 4), n=8))
    p = predict_ex_for_month(s, 2026, 2)   # 2026 非閏年 → 28 天
    assert p["ex_date"] == _dt.date(2026, 2, 28)


def test_predict_quarterly_lands_in_month():
    divs = [{"ex_date": d} for d in ("2025-05-15", "2025-08-15", "2025-11-15", "2026-05-15")]
    s = infer_schedule(divs)
    assert predict_ex_for_month(s, 2026, 8) is not None      # 5/15 + 91 ≈ 8 月 → 有
    assert predict_ex_for_month(s, 2026, 9) is None          # 9 月無配息 → 不列


def test_predict_single_returns_none():
    s = infer_schedule([{"ex_date": "2026-01-10"}])
    assert predict_ex_for_month(s, 2026, 8) is None          # 節奏不明 → 不猜(§1)


# ── build_month_calendar ───────────────────────────────────
def test_build_calendar_groups_and_excludes():
    funds = [
        {"code": "TLZF9", "name": "安聯收益成長", "house": "安聯",
         "dividends": _monthly_divs(day=14, n=12)},
        {"code": "ACDD01", "name": "安聯台灣大壩累積", "house": "安聯",
         "dividends": []},                                   # 累積型 → 排除
        {"code": "JFZN3", "name": "摩根多重收益", "house": "摩根",
         "dividends": _monthly_divs(day=7, n=10)},
    ]
    cal = build_month_calendar(funds, 2026, 8)
    assert cal["counts"] == {"events": 2, "excluded": 1}
    assert set(cal["by_day"].keys()) == {7, 14}
    assert cal["by_day"][14][0]["code"] == "TLZF9"
    assert cal["excluded"][0]["code"] == "ACDD01"
    # 事件依除息日排序:7 號(JFZN3)在 14 號(TLZF9)之前
    assert [e["code"] for e in cal["events"]] == ["JFZN3", "TLZF9"]


def test_build_calendar_quarterly_offmonth_not_listed_not_excluded():
    funds = [{"code": "Q1", "name": "季配基金", "dividends":
              [{"ex_date": d} for d in ("2025-05-15", "2025-08-15", "2025-11-15", "2026-05-15")]}]
    cal = build_month_calendar(funds, 2026, 9)               # 9 月無配息
    assert cal["counts"] == {"events": 0, "excluded": 0}     # 不列也不排除(誠實)


# ── detect_house ───────────────────────────────────────────
def test_detect_house_keywords():
    assert detect_house("聯博多元資產收益組合基金AI配息(美元)") == "聯博"
    assert detect_house("安聯收益成長基金-AMg7") == "安聯"
    assert detect_house("摩根投資基金-多重收益基金A股") == "摩根"
    assert detect_house("施羅德環球基金系列-環球收益成長") == "施羅德"
    assert detect_house("某某不知名基金") == ""             # 判不出 → 空(§1 不亂猜)


# ── build_summary_text(LINE 方式 C）─────────────────────────
def test_summary_text_lists_events_and_excluded():
    funds = [
        {"code": "TLZF9", "name": "安聯收益成長", "dividends": _monthly_divs(day=14, n=12)},
        {"code": "ACDD01", "name": "安聯台灣大壩累積", "dividends": []},
    ]
    # 補上 house(build_month_calendar 不自動偵測 house;caller 組裝時填,此處手動)
    for f in funds:
        f["house"] = detect_house(f["name"])
    cal = build_month_calendar(funds, 2026, 8)
    txt = build_summary_text(cal)
    assert "民國115年8月" in txt
    assert "8/14" in txt and "TLZF9" in txt
    assert "1 檔累積型/無配息未列" in txt
    assert "推估非官方" in txt


def test_summary_text_empty_is_honest():
    cal = build_month_calendar([], 2026, 8)
    assert "無推估除息日" in build_summary_text(cal)
