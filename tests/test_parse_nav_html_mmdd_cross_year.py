# -*- coding: utf-8 -*-
"""`_parse_nav_html` 的 MM/DD 補年份:最近候選年規則。

以台灣今天的前一年／今年／下一年組三個候選,取離今天最近者;
最近者晚於今天 → 此筆不寫、計數於 `attrs["mmdd_rejected"]`。
原 bug:一律補今年 → 1 月時 12 月條目變成未來日期;改用「晚於今天推回去年」
又會把近期未來條目變成去年的假歷史值。本檔兩種都守。
不連網;today 以 monkeypatch `nav_metrics._tw_today`(或 `_dt_mod`)固定。
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


def _dates(s):
    return [d.date() for d in s.index]


def _mmdd(d):
    return f"{d.month:02d}/{d.day:02d}"


# ── 跨年正控:1/5 讀到 12 月條目 → 去年,照收 ─────────────────────────

CROSS_ROWS = [("12/22", "10.10"), ("12/23", "10.11"), ("12/24", "10.12"), ("12/26", "10.13"),
              ("12/29", "10.14"), ("12/30", "10.15"), ("12/31", "10.16"),
              ("01/02", "10.20"), ("01/04", "10.21"), ("01/05", "10.22")]


def test_jan5_cross_year_dec_goes_to_last_year(monkeypatch):
    today = dt.date(2027, 1, 5)
    s = _parse(monkeypatch, today, CROSS_ROWS)
    dates = _dates(s)
    assert len(s) == 10
    assert [d for d in dates if d.month == 12] == [
        dt.date(2026, 12, x) for x in (22, 23, 24, 26, 29, 30, 31)]
    assert [d for d in dates if d.month == 1] == [dt.date(2027, 1, x) for x in (2, 4, 5)]
    assert s.index[-1].date() == today
    assert s.iloc[-1] == pytest.approx(10.22)
    assert s.attrs["mmdd_rejected"] == 0


# ── 未來條目:不寫(紅隊三例 + 規格組例 + 上一輪兩例)────────────────

@pytest.mark.parametrize("today, page, wrong", [
    (dt.date(2026, 12, 30), "01/02", dt.date(2026, 1, 2)),   # 紅隊
    (dt.date(2026, 12, 31), "01/01", dt.date(2026, 1, 1)),   # 紅隊
    (dt.date(2026, 12, 15), "01/10", dt.date(2026, 1, 10)),  # 紅隊
    (dt.date(2026, 10, 2), "11/03", dt.date(2025, 11, 3)),   # 規格組(晚 32 天)
    (dt.date(2027, 1, 5), "01/06", dt.date(2026, 1, 6)),
    (dt.date(2026, 7, 1), "07/02", dt.date(2025, 7, 2)),
])
def test_future_entry_not_written(monkeypatch, capsys, today, page, wrong):
    ok = _mmdd(today)
    s = _parse(monkeypatch, today, [(ok, "10.0"), (page, "10.5")])
    assert _dates(s) == [today], f"{page} 不應被寫成 {wrong} 或任何日期"
    assert wrong not in _dates(s)
    assert s.attrs["mmdd_rejected"] == 1
    assert page in capsys.readouterr().out


# ── 正控:T+1 頁面前 1～30 天全收(年中/跨年/閏年)──────────────────

@pytest.mark.parametrize("today", [
    dt.date(2026, 7, 15),   # 年中
    dt.date(2027, 1, 10),   # 跨年:前 30 天跨進去年 12 月
    dt.date(2028, 3, 15),   # 閏年:前 30 天含 2028-02-29
])
def test_past_1_to_30_days_all_written(monkeypatch, today):
    past = [today - dt.timedelta(days=k) for k in range(30, 0, -1)]
    s = _parse(monkeypatch, today, [(_mmdd(d), f"{10 + i / 100:.2f}") for i, d in enumerate(past)])
    assert _dates(s) == past
    assert s.attrs["mmdd_rejected"] == 0
    if today.year == 2028:
        assert dt.date(2028, 2, 29) in _dates(s)


def test_today_itself_written(monkeypatch):
    today = dt.date(2026, 12, 31)
    s = _parse(monkeypatch, today, [("12/30", "9.9"), ("12/31", "10.0")])
    assert _dates(s) == [dt.date(2026, 12, 30), today]


def test_yyyy_mm_dd_unaffected(monkeypatch):
    # 完整年份不經推斷:即使晚於 today 也照原樣(行為不變),不計入拒收
    today = dt.date(2027, 1, 5)
    rows = [("2026/12/30", "10.0"), ("2027/01/04", "10.1"), ("2027/12/30", "10.2")]
    s = _parse(monkeypatch, today, rows)
    assert _dates(s) == [dt.date(2026, 12, 30), dt.date(2027, 1, 4), dt.date(2027, 12, 30)]
    assert s.attrs["mmdd_rejected"] == 0


def test_tie_picks_earlier_candidate(monkeypatch):
    # today 2027-08-31:03/01 的候選 2027-03-01(早 183 天)與 2028-03-01(晚 183 天)平手
    # → 取較早者,照收為 2027-03-01
    today = dt.date(2027, 8, 31)
    assert (today - dt.date(2027, 3, 1)).days == (dt.date(2028, 3, 1) - today).days
    s = _parse(monkeypatch, today, [("03/01", "10.0"), ("08/31", "10.1")])
    assert _dates(s) == [dt.date(2027, 3, 1), today]
    assert s.attrs["mmdd_rejected"] == 0


def test_feb29_without_leap_candidate_is_counted(monkeypatch, capsys):
    # today 2026-06-01:2025/2026/2027 皆非閏年 → 02/29 不寫、計數 1、有 print
    today = dt.date(2026, 6, 1)
    s = _parse(monkeypatch, today, [("02/29", "10.0"), ("06/01", "10.1")])
    assert _dates(s) == [today]
    assert s.attrs["mmdd_rejected"] == 1
    assert "02/29" in capsys.readouterr().out


def test_invalid_mmdd_not_counted(monkeypatch):
    # 非 02/29 的不合法 MM/DD(如 13/45)仍照原本略過,不算進「拒收」
    today = dt.date(2026, 6, 1)
    s = _parse(monkeypatch, today, [("13/45", "10.0"), ("06/01", "10.1")])
    assert _dates(s) == [today]
    assert s.attrs["mmdd_rejected"] == 0


def test_attrs_count_multiple_and_empty(monkeypatch):
    today = dt.date(2026, 12, 30)
    s = _parse(monkeypatch, today, [("01/01", "1.0"), ("01/02", "1.1"), ("01/03", "1.2")])
    assert s.empty
    assert s.attrs["mmdd_rejected"] == 3


# ── 台灣日期守衛:固定 UTC 16:30 ─────────────────────────────────────

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
    monkeypatch.setattr(nav_metrics, "_dt_mod", _FixedUtcClock(_UTC_1630_NYE))
    assert nav_metrics._tw_today() == dt.date(2027, 1, 1)


def test_end_to_end_utc_1630_new_year_page_0101(monkeypatch):
    monkeypatch.setattr(nav_metrics, "_dt_mod", _FixedUtcClock(_UTC_1630_NYE))
    s = nav_metrics._parse_nav_html(_html([("12/30", "10.0"), ("12/31", "10.1"), ("01/01", "10.2")]))
    assert _dates(s) == [dt.date(2026, 12, 30), dt.date(2026, 12, 31), dt.date(2027, 1, 1)]
    assert s.attrs["mmdd_rejected"] == 0


# ── fetch_nav:拒收筆數帶進 _attempts / attrs(stub L1 HTTP,繞過快取)──

class _FakeResp:
    def __init__(self, text):
        self.text = text
        self.status_code = 200


def _stub_fetch(monkeypatch, today, rows):
    monkeypatch.setattr(nav_metrics, "_tw_today", lambda: today)
    page = _html(rows)
    monkeypatch.setattr(nav_metrics, "fetch_url_with_retry", lambda *a, **k: _FakeResp(page))
    monkeypatch.setattr(nav_metrics, "_src_cache_files", lambda code: None)


def test_fetch_nav_attempts_carry_rejected_count(monkeypatch):
    today = dt.date(2026, 12, 30)
    _stub_fetch(monkeypatch, today,
                [("12/28", "10.0"), ("12/29", "10.1"), ("01/01", "10.2"), ("01/02", "10.3")])
    # __wrapped__:繞過 @_daily_cache — 測試資料不得流入 production cache
    s = nav_metrics.fetch_nav.__wrapped__("TEST99")
    assert s.empty
    err = s.attrs[nav_metrics._FETCH_ERROR_ATTR]
    assert "拒收 2 筆" in err


def test_fetch_nav_success_keeps_rejected_attr(monkeypatch):
    today = dt.date(2026, 12, 30)
    past = [today - dt.timedelta(days=k) for k in range(12, -1, -1)]
    rows = [(_mmdd(d), "10.0") for d in past] + [("01/02", "10.3")]
    _stub_fetch(monkeypatch, today, rows)
    s = nav_metrics.fetch_nav.__wrapped__("TEST99")
    assert _dates(s) == past
    assert s.attrs["mmdd_rejected"] == 1
