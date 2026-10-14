"""tests/test_probe_fx_daily_value_check.py — `scripts/probe_fx_obs_date.py` 的「日 K 值對應哪個時刻」演算法（不連網）。

以**已知對應時刻**的合成日 K 與小時 K 確認演算法找得到：
- 標 D 的日 K close ＝ 倫敦 D−1 21:00 那根小時 close（模擬「前一天某固定時刻的快照」）→ 交易所日差 −1、21:00；
- 標 D 的日 K close ＝ 倫敦 D 當日最後一根小時 close → 交易所日差 0、23:00，且計入「等於當日最後一根」；
- 夏令時倫敦（日 K 時間戳在 UTC 前一天 23:00）照樣以交易所當地日計日差；
- OHLC 對同一交易所日的小時彙總、未收盤與觀測窗外的根不比、null 小時值不參與、同差距計 ties。
時間戳都由 `datetime(..., tzinfo=UTC)` 算出，不手寫 Unix 秒。
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_fx_obs_date.py"
_spec = importlib.util.spec_from_file_location("probe_fx_obs_date_dvc", _SCRIPT)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

LONDON = "Europe/London"


def _sec(dt: datetime) -> int:
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def _hourly(start: datetime, hours: int, *, base=30.0, step=0.001):
    """每小時一根；close＝base＋i×step（每根唯一），open＝close−step/2，high／low＝close±step。"""
    t, o, h, lo, c = [], [], [], [], []
    for i in range(hours):
        t.append(_sec(start + timedelta(hours=i)))
        close = round(base + i * step, 6)
        c.append(close)
        o.append(round(close - step / 2, 6))
        h.append(round(close + step, 6))
        lo.append(round(close - step, 6))
    return {"meta": {"exchangeTimezoneName": LONDON}, "t": t, "open": o, "high": h, "low": lo, "close": c,
            "missing_fields": []}


def _close_at(hourly, dt: datetime):
    return hourly["close"][hourly["t"].index(_sec(dt))]


def _daily(stamps_and_closes):
    t = [_sec(d) for d, _c in stamps_and_closes]
    c = [v for _d, v in stamps_and_closes]
    return {"meta": {"exchangeTimezoneName": LONDON}, "t": t, "open": list(c), "high": list(c), "low": list(c),
            "close": c, "missing_fields": []}


# 倫敦冬令（＝UTC）：2026-01-05（一）00:00 起 5 天的小時 K
_H0 = datetime(2026, 1, 5, 0, 0)
_HOURLY = _hourly(_H0, 24 * 5)


def test_標D的close等於前一日21點_找得到_交易所日差負1():
    days = [datetime(2026, 1, d) for d in (6, 7, 8)]
    daily = _daily([(d, _close_at(_HOURLY, d - timedelta(hours=3))) for d in days])   # D−1 21:00
    out = probe.match_daily_to_hourly(daily, _HOURLY, LONDON, "2026-01-10")
    assert out["compared"] == 3
    for rec in out["bars"]:
        bc = rec["best_close_match"]
        assert bc["exchange_day_offset"] == -1 and bc["exchange_hhmm"] == "21:00"
        assert bc["abs_diff"] == 0 and bc["ties"] == 1
        assert bc["Europe/London"].endswith("21:00") and bc["utc"].endswith("21:00")
        assert bc["America/New_York"].endswith("16:00") and bc["Asia/Taipei"].endswith("05:00")
    assert out["best_close_match_distribution"] == {"-1 21:00": 3}
    assert out["best_close_match_utc_distribution"] == {"21:00": 3}
    assert out["close_equals_same_day_last_hourly_close"] == 0
    assert out["close_equals_prev_day_last_hourly_close"] == 0      # 前一日最後一根是 23:00，不是 21:00


def test_標D的close等於當日最後一根小時close_計入等於當日():
    days = [datetime(2026, 1, d) for d in (6, 7)]
    daily = _daily([(d, _close_at(_HOURLY, d + timedelta(hours=23))) for d in days])
    out = probe.match_daily_to_hourly(daily, _HOURLY, LONDON, "2026-01-10")
    assert out["best_close_match_distribution"] == {"+0 23:00": 2}
    assert out["close_equals_same_day_last_hourly_close"] == 2
    assert all(abs(r["close_vs_day_last_hourly_close"]["+0"]) < 1e-9 for r in out["bars"])
    assert all(r["close_vs_day_last_hourly_close"]["-1"] > 0 for r in out["bars"])   # 序列遞增：前一日較低 ⇒ 日 K close 高於它


def test_標D的close等於前一日最後一根小時close_計入等於前一日():
    days = [datetime(2026, 1, d) for d in (6, 7)]
    daily = _daily([(d, _close_at(_HOURLY, d - timedelta(hours=1))) for d in days])
    out = probe.match_daily_to_hourly(daily, _HOURLY, LONDON, "2026-01-10")
    assert out["best_close_match_distribution"] == {"-1 23:00": 2}
    assert out["close_equals_prev_day_last_hourly_close"] == 2
    assert out["close_equals_same_day_last_hourly_close"] == 0


def test_夏令時倫敦_日K在UTC前一天23點_日差以交易所當地日計():
    hourly = _hourly(datetime(2026, 7, 5, 23, 0), 24 * 4)            # UTC 07-05 23:00 ＝ 倫敦 07-06 00:00 起
    d_stamp = datetime(2026, 7, 7, 23, 0)                            # 倫敦 07-08（三）00:00
    target = datetime(2026, 7, 7, 20, 0)                             # UTC 20:00 ＝ 倫敦 07-07 21:00
    daily = _daily([(d_stamp, _close_at(hourly, target))])
    out = probe.match_daily_to_hourly(daily, hourly, LONDON, "2026-07-12")
    (rec,) = out["bars"]
    assert rec["obs_date"] == "2026-07-08"
    bc = rec["best_close_match"]
    assert bc["exchange_day_offset"] == -1 and bc["exchange_hhmm"] == "21:00" and bc["utc"].endswith("20:00")


def test_同一交易所日的OHLC彙總與區間判斷():
    day = datetime(2026, 1, 6)
    agg = probe.hourly_day_aggregate(_HOURLY, LONDON)["2026-01-06"]
    first, last = 24, 47                                             # 01-06 的第 1 根與最後一根索引
    assert agg["bars"] == 24
    assert agg["open"] == _HOURLY["open"][first] and agg["close"] == _HOURLY["close"][last]
    assert agg["high"] == max(_HOURLY["high"][first:last + 1]) and agg["low"] == min(_HOURLY["low"][first:last + 1])
    inside = _close_at(_HOURLY, day + timedelta(hours=12))
    outside = agg["high"] + 1.0
    out = probe.match_daily_to_hourly(_daily([(day, inside), (day + timedelta(days=1), outside)]),
                                      _HOURLY, LONDON, "2026-01-10")
    r_in, r_out = out["bars"]
    assert r_in["vs_same_exchange_day"]["close_within_hourly_range"] is True
    assert r_out["vs_same_exchange_day"]["close_within_hourly_range"] is False
    assert r_in["vs_same_exchange_day"]["hourly"]["bars"] == 24


def test_未收盤與觀測窗外的根不比_null日K跳過並計數():
    days = [datetime(2026, 1, d) for d in (6, 7, 8, 9)]
    closes = [_close_at(_HOURLY, d) for d in days]
    closes[1] = None
    out = probe.match_daily_to_hourly(_daily(list(zip(days, closes))), _HOURLY, LONDON, "2026-01-09",
                                      window_days=2)
    assert [r["obs_date"] for r in out["bars"]] == ["2026-01-08"]   # 01-06 在窗外、01-07 null、01-09 未收盤
    assert out["skipped"] == {"daily_close_null": 1, "not_closed": 1}


def test_null小時值不參與_同差距計ties_範圍內沒有小時K記狀態():
    hourly = _hourly(_H0, 24 * 2)
    hourly["close"][10] = None
    hourly["close"][20] = hourly["close"][30]                         # 兩根同值 ⇒ ties 2，回較早的一根
    day = datetime(2026, 1, 6)
    far = datetime(2026, 1, 20)
    out = probe.match_daily_to_hourly(_daily([(day, hourly["close"][30]), (far, 31.0)]), hourly, LONDON,
                                      "2026-01-25", window_days=30)
    near, away = out["bars"]
    assert near["best_close_match"]["ties"] == 2 and near["best_close_match"]["t"] == hourly["t"][20]
    assert away["status"] == "no_hourly_in_scope" and out["skipped"]["no_hourly_in_scope"] == 1


def test_daily_value_check_交易所時區認不得就不比():
    payload = {"chart": {"result": [{"meta": {"exchangeTimezoneName": "UTC"}, "timestamp": [1],
                                     "indicators": {"quote": [{"close": [1.0]}]}}], "error": None}}
    assert probe.daily_value_check(payload, payload, "2026-01-10T00:00:00+00:00")["status"] == "exchange_tz_unknown"


def test_extract_ohlc_缺欄整列為None並記錄_raw_series存完整序列():
    ts = [_sec(datetime(2026, 1, 5) + timedelta(days=i)) for i in range(100)]
    payload = {"chart": {"result": [{"meta": {"exchangeTimezoneName": LONDON}, "timestamp": ts,
                                     "indicators": {"quote": [{"close": [30.0 + i for i in range(99)] + [None],
                                                               "high": [31.0] * 100}]}}], "error": None}}
    ohlc = probe.extract_ohlc(payload)
    assert ohlc["missing_fields"] == ["open", "low"] and ohlc["open"] == [None] * 100
    raw = probe.raw_series(ohlc)
    assert raw["count"] == 100 and raw["t"] == ts and raw["close"][-1] is None   # 完整、null 原樣
    assert raw["missing_fields"] == ["open", "low"]


def test_meta_snapshot_逐字照錄_缺的列進absent():
    snap = probe.meta_snapshot({"regularMarketPrice": 32.164, "chartPreviousClose": 32.13, "other": 1})
    assert snap["values"] == {"regularMarketPrice": 32.164, "chartPreviousClose": 32.13}
    assert "previousClose" in snap["absent"] and "regularMarketDayHigh" in snap["absent"]


@pytest.mark.parametrize("bad", [None, float("nan"), "x", True])
def test_num_缺值一律None(bad):
    assert probe._num(bad) is None


def test_夏令時倫敦_對應根在UTC前一天23點_日差仍以交易所當地日計為0():
    """對應的小時 K 在 UTC 07-07 23:00 ＝ 倫敦 07-08 00:00：交易所日差是 0，不是以 UTC 日期算出的 −1。"""
    hourly = _hourly(datetime(2026, 7, 5, 23, 0), 24 * 4)
    d_stamp = datetime(2026, 7, 7, 23, 0)                            # 日 K：倫敦 07-08 00:00
    daily = _daily([(d_stamp, _close_at(hourly, datetime(2026, 7, 7, 23, 0)))])
    (rec,) = probe.match_daily_to_hourly(daily, hourly, LONDON, "2026-07-12")["bars"]
    bc = rec["best_close_match"]
    assert bc["exchange_day_offset"] == 0 and bc["exchange_hhmm"] == "00:00" and bc["utc"] == "2026-07-07 23:00"
