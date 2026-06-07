"""v19.22 Tier A — event_calendar.py 單元測試。"""
from __future__ import annotations

from datetime import date

from services import event_calendar as ec


class TestConstants:
    def test_event_keys(self):
        assert ec.EVENT_KEYS == ("FOMC", "NFP", "CPI")

    def test_palette_is_hex(self):
        for c in (ec.GREEN, ec.YELLOW, ec.ORANGE, ec.RED, ec.GRAY):
            assert c.startswith("#")

    def test_fomc_2026_count(self):
        in_2026 = [d for d in ec._FOMC_DATES if d.year == 2026]
        assert len(in_2026) == 8

    def test_fomc_2027_count(self):
        in_2027 = [d for d in ec._FOMC_DATES if d.year == 2027]
        assert len(in_2027) == 8

    def test_fomc_dates_sorted(self):
        prev = None
        for d in ec._FOMC_DATES:
            if prev is not None:
                assert d > prev
            prev = d


class TestBadgeFor:
    def test_red_imminent(self):
        sig, color = ec._badge_for(0)
        assert "🔴" in sig and color == ec.RED

    def test_orange_near(self):
        sig, color = ec._badge_for(5)
        assert "🟠" in sig and color == ec.ORANGE

    def test_yellow_watch(self):
        sig, color = ec._badge_for(10)
        assert "🟡" in sig and color == ec.YELLOW

    def test_green_calm(self):
        sig, color = ec._badge_for(30)
        assert "🟢" in sig and color == ec.GREEN

    def test_boundary_3_vs_4(self):
        assert "🔴" in ec._badge_for(3)[0]
        assert "🟠" in ec._badge_for(4)[0]

    def test_boundary_7_vs_8(self):
        assert "🟠" in ec._badge_for(7)[0]
        assert "🟡" in ec._badge_for(8)[0]

    def test_boundary_14_vs_15(self):
        assert "🟡" in ec._badge_for(14)[0]
        assert "🟢" in ec._badge_for(15)[0]


class TestFirstFridayHelper:
    def test_jan_2026(self):
        # 2026-01-02 是週五（first Friday）
        assert ec._first_friday_of(2026, 1) == date(2026, 1, 2)

    def test_jun_2026(self):
        # 2026-06-05 是週五
        assert ec._first_friday_of(2026, 6) == date(2026, 6, 5)

    def test_jan_2027(self):
        # 2027-01-01 是週五
        assert ec._first_friday_of(2027, 1) == date(2027, 1, 1)


class TestAdjustWorkday:
    def test_weekday_unchanged(self):
        # 2026-06-10 週三
        assert ec._adjust_workday(date(2026, 6, 10)) == date(2026, 6, 10)

    def test_saturday_pushes_to_monday(self):
        # 2026-01-10 週六 → 1/12 週一
        assert ec._adjust_workday(date(2026, 1, 10)) == date(2026, 1, 12)

    def test_sunday_pushes_to_monday(self):
        # 2026-01-11 週日 → 1/12 週一
        assert ec._adjust_workday(date(2026, 1, 11)) == date(2026, 1, 12)


class TestNextFomcDate:
    def test_before_first_2026_meeting(self):
        assert ec.next_fomc_date(date(2026, 1, 1)) == date(2026, 1, 28)

    def test_same_day_as_meeting_returns_today(self):
        assert ec.next_fomc_date(date(2026, 6, 17)) == date(2026, 6, 17)

    def test_after_last_known_returns_none(self):
        assert ec.next_fomc_date(date(2030, 1, 1)) is None

    def test_between_meetings(self):
        # 6/18 → 下次 7/29
        assert ec.next_fomc_date(date(2026, 6, 18)) == date(2026, 7, 29)


class TestNextNfpDate:
    def test_first_friday_jun_2026(self):
        assert ec.next_nfp_date(date(2026, 6, 1)) == date(2026, 6, 5)

    def test_after_release_jumps_to_next_month(self):
        # 6/8 之後 → 7 月第一個週五（7/3）
        assert ec.next_nfp_date(date(2026, 6, 8)) == date(2026, 7, 3)

    def test_year_wrap(self):
        # 2026-12-31 → 2027-01-01（週五）
        assert ec.next_nfp_date(date(2026, 12, 31)) == date(2027, 1, 1)


class TestNextCpiDate:
    def test_cpi_jun_10_weekday(self):
        # 2026-06-10 是週三 → 不延後
        assert ec.next_cpi_date(date(2026, 6, 1)) == date(2026, 6, 10)

    def test_cpi_after_release(self):
        # 6/11 之後 → 7 月 10 號（週五）
        assert ec.next_cpi_date(date(2026, 6, 11)) == date(2026, 7, 10)

    def test_cpi_weekend_adjustment(self):
        # 2026-01-10 週六 → 1/12 週一
        assert ec.next_cpi_date(date(2026, 1, 1)) == date(2026, 1, 12)


class TestEventPayload:
    def test_payload_basic(self):
        p = ec.event_payload("FOMC", date(2026, 7, 29), date(2026, 6, 7))
        assert p["event"] == "FOMC"
        assert p["days_until"] == 52
        assert p["date"] == date(2026, 7, 29)
        assert "🟢" in p["signal"]

    def test_payload_none_target(self):
        p = ec.event_payload("FOMC", None, date(2030, 1, 1))
        assert p["date"] is None
        assert p["days_until"] is None
        assert "⬜" in p["signal"]
        assert p["color"] == ec.GRAY

    def test_payload_imminent(self):
        p = ec.event_payload("CPI", date(2026, 6, 10), date(2026, 6, 8))
        assert p["days_until"] == 2
        assert "🔴" in p["signal"]


class TestDetectEventCalendar:
    def test_returns_all_three(self):
        out = ec.detect_event_calendar(date(2026, 6, 7))
        assert set(out.keys()) == {"FOMC", "NFP", "CPI"}

    def test_default_today_does_not_crash(self):
        out = ec.detect_event_calendar()
        for k in ec.EVENT_KEYS:
            assert k in out
            assert "signal" in out[k]


class TestSummarizeCalendar:
    def test_nearest_event_dominates(self):
        # 6/7 距 6/10 CPI 最近 3 天
        payload = ec.detect_event_calendar(date(2026, 6, 7))
        s = ec.summarize_calendar(payload)
        assert s["min_days"] == 3
        assert s["nearest"] == "CPI"
        assert "🔴" in s["level"]

    def test_all_none_returns_empty(self):
        empty_payload = {
            "FOMC": {"event": "FOMC", "days_until": None, "signal": "⬜", "color": "#888"},
            "NFP": {"event": "NFP", "days_until": None, "signal": "⬜", "color": "#888"},
            "CPI": {"event": "CPI", "days_until": None, "signal": "⬜", "color": "#888"},
        }
        s = ec.summarize_calendar(empty_payload)
        assert s["min_days"] is None
        assert s["nearest"] is None

    def test_partial_none(self):
        partial = {
            "FOMC": {"event": "FOMC", "days_until": None, "signal": "⬜", "color": "#888"},
            "NFP": {"event": "NFP", "days_until": 20, "signal": "🟢", "color": "#22c55e"},
            "CPI": {"event": "CPI", "days_until": 5, "signal": "🟠", "color": "#fb923c"},
        }
        s = ec.summarize_calendar(partial)
        assert s["min_days"] == 5
        assert s["nearest"] == "CPI"
