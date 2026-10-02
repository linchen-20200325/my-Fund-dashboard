# -*- coding: utf-8 -*-
"""`_parse_nav_html` 的 MM/DD 補年份必須跨年判斷(重用 SSOT `_infer_year_for_mmdd`)。

原 bug:一律補今年 → today 為 1 月時,12 月條目被補成今年 12 月(未來日期),
排序後最後一筆變成假的 12 月值,轉換層再把這些列當未來日期拒收。
不連網;today 以 monkeypatch `nav_metrics._tw_today` 固定。
"""
import datetime as dt

import pytest

from repositories.fund import nav_metrics


def _html(rows):
    trs = "".join(f"<tr><td>{d}</td><td>{v}</td></tr>" for d, v in rows)
    return f"<html><body><table><tr><th>日期</th><th>淨值</th></tr>{trs}</table></body></html>"


def _parse(monkeypatch, today, rows):
    monkeypatch.setattr(nav_metrics, "_tw_today", lambda: today)
    return nav_metrics._parse_nav_html(_html(rows))


CROSS_ROWS = [("12/22", "10.10"), ("12/23", "10.11"), ("12/24", "10.12"), ("12/26", "10.13"),
              ("12/29", "10.14"), ("12/30", "10.15"), ("12/31", "10.16"),
              ("01/02", "10.20"), ("01/04", "10.21"), ("01/05", "10.22")]


def test_jan5_cross_year_dec_goes_to_last_year(monkeypatch):
    today = dt.date(2027, 1, 5)
    s = _parse(monkeypatch, today, CROSS_ROWS)
    dates = [d.date() for d in s.index]
    assert len(s) == 10
    assert all(d <= today for d in dates), dates
    assert [d for d in dates if d.month == 12] == [
        dt.date(2026, 12, x) for x in (22, 23, 24, 26, 29, 30, 31)]
    assert [d for d in dates if d.month == 1] == [
        dt.date(2027, 1, x) for x in (2, 4, 5)]
    assert s.index[-1].date() == dt.date(2027, 1, 5)
    assert s.iloc[-1] == pytest.approx(10.22)
    assert s.index.is_monotonic_increasing and s.index.is_unique


def test_midyear_positive_control_same_year(monkeypatch):
    # 正控:年中、條目皆不晚於今天 → 與修改前相同(全部補今年)
    today = dt.date(2027, 7, 15)
    rows = [("06/20", "9.9"), ("07/01", "10.0"), ("07/14", "10.1"), ("07/15", "10.2")]
    s = _parse(monkeypatch, today, rows)
    assert [d.date() for d in s.index] == [
        dt.date(2027, 6, 20), dt.date(2027, 7, 1), dt.date(2027, 7, 14), dt.date(2027, 7, 15)]


def test_boundary_today_dec31(monkeypatch):
    # today = 12/31:12/31 是今天 → 今年;12/01 → 今年
    today = dt.date(2026, 12, 31)
    s = _parse(monkeypatch, today, [("12/01", "9.5"), ("12/31", "10.0")])
    assert [d.date() for d in s.index] == [dt.date(2026, 12, 1), dt.date(2026, 12, 31)]


def test_boundary_today_jan1(monkeypatch):
    # today = 01/01:12/31 晚於今天 → 去年;01/01 → 今年;最後一筆為 01/01
    today = dt.date(2027, 1, 1)
    s = _parse(monkeypatch, today, [("12/31", "10.0"), ("01/01", "10.5")])
    assert [d.date() for d in s.index] == [dt.date(2026, 12, 31), dt.date(2027, 1, 1)]
    assert s.iloc[-1] == pytest.approx(10.5)


def test_yyyy_mm_dd_unaffected(monkeypatch):
    # 完整年份不經推斷:即使晚於 today 也照原樣(行為不變)
    today = dt.date(2027, 1, 5)
    rows = [("2026/12/30", "10.0"), ("2027/01/04", "10.1"), ("2027/12/30", "10.2")]
    s = _parse(monkeypatch, today, rows)
    assert [d.date() for d in s.index] == [
        dt.date(2026, 12, 30), dt.date(2027, 1, 4), dt.date(2027, 12, 30)]


class _FixedUtcClock:
    """把 `nav_metrics._dt_mod` 換成固定 UTC 時刻的假 datetime 模組。"""

    def __init__(self, utc_instant):
        real = dt
        fixed = utc_instant

        class _FakeDT(real.datetime):
            @classmethod
            def now(cls, tz=None):
                return fixed if tz is None else fixed.astimezone(tz)

            @classmethod
            def utcnow(cls):
                return fixed.replace(tzinfo=None)

        class _FakeDate(real.date):
            @classmethod
            def today(cls):
                return fixed.date()  # 刻意回 UTC 日期:誤用 date.today() 的突變會轉紅

        self.datetime = _FakeDT
        self.date = _FakeDate
        self.timezone = real.timezone
        self.timedelta = real.timedelta


_UTC_1630_NYE = dt.datetime(2026, 12, 31, 16, 30, tzinfo=dt.timezone.utc)  # 台灣 2027-01-01 00:30


def test_tw_today_is_next_day_at_utc_1630(monkeypatch):
    # UTC 16:30 = 台灣隔天 00:30 → `_tw_today()` 必須回隔天(UTC 或 date.today() 會回當天)
    monkeypatch.setattr(nav_metrics, "_dt_mod", _FixedUtcClock(_UTC_1630_NYE))
    assert nav_metrics._tw_today() == dt.date(2027, 1, 1)


def test_end_to_end_utc_1630_new_year_page_0101(monkeypatch):
    # 端到端:UTC 2026-12-31 16:30,頁面 01/01 → 2027-01-01(不是被擋、也不是 2026-01-01)
    monkeypatch.setattr(nav_metrics, "_dt_mod", _FixedUtcClock(_UTC_1630_NYE))
    s = nav_metrics._parse_nav_html(_html([("12/30", "10.0"), ("12/31", "10.1"), ("01/01", "10.2")]))
    assert [d.date() for d in s.index] == [
        dt.date(2026, 12, 30), dt.date(2026, 12, 31), dt.date(2027, 1, 1)]


# ── 近期未來日期(晚 1～31 天)→ 不寫,不推回去年 ───────────────────────

def test_near_future_jan6_on_jan5_not_written(monkeypatch, capsys):
    today = dt.date(2027, 1, 5)
    s = _parse(monkeypatch, today, [("01/04", "10.0"), ("01/05", "10.1"), ("01/06", "10.2")])
    assert [d.date() for d in s.index] == [dt.date(2027, 1, 4), dt.date(2027, 1, 5)]
    assert dt.date(2026, 1, 6) not in [d.date() for d in s.index]
    assert "01/06" in capsys.readouterr().out


def test_near_future_jul2_on_jul1_not_written(monkeypatch):
    today = dt.date(2026, 7, 1)
    s = _parse(monkeypatch, today, [("06/30", "10.0"), ("07/01", "10.1"), ("07/02", "10.2")])
    assert [d.date() for d in s.index] == [dt.date(2026, 6, 30), dt.date(2026, 7, 1)]


def test_near_future_31_days_boundary_not_written(monkeypatch):
    today = dt.date(2026, 7, 1)  # 08/01 晚 31 天 → 仍在拒收區
    s = _parse(monkeypatch, today, [("07/01", "10.1"), ("08/01", "10.2")])
    assert [d.date() for d in s.index] == [dt.date(2026, 7, 1)]


def test_32_days_ahead_goes_to_last_year(monkeypatch):
    # 正控:晚 32 天 → 視為跨年,推回去年
    today = dt.date(2026, 7, 1)  # 08/02 晚 32 天
    s = _parse(monkeypatch, today, [("07/01", "10.1"), ("08/02", "10.2")])
    assert [d.date() for d in s.index] == [dt.date(2025, 8, 2), dt.date(2026, 7, 1)]
