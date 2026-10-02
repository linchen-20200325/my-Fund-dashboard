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


def test_tw_today_is_utc_plus_8():
    # _tw_today 取台灣日期,與 sources.py 近30日路徑一致
    expect = dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).date()
    assert nav_metrics._tw_today() in (expect, expect + dt.timedelta(days=1))
