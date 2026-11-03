# -*- coding: utf-8 -*-
"""🌍 頁測試用的**測試端**資料替身（BL-0536 rendering 批）。只在 `tests/` 內；`ui_v3/` 不含任何 fake 資料、不 import `ui_v3.fixtures`。

做法：用真的 `market_view.build_market_view`／`market_indicator` 資料形狀（L1 替身只在 `fetch_*` 參數，不改 L2），
所以 adapter 吃到的是「真實形狀、假數值」的結果。⚠️ 數值是人造的；截圖與測試都不代表真實行情。
"""
from __future__ import annotations

import math

import pandas as pd

from services.v2_tables import market_view as mv

FETCHED = "2026-11-03T06:00:00+00:00"   # 台北 2026-11-03 14:00
LAST_US = "2026-11-02"                  # 週一
KEY = "stub-key"


def weekdays(start, end):
    return [d.strftime("%Y-%m-%d") for d in pd.bdate_range(start, end)]


def _yahoo(dates, values, *, name, source_tz, hour, minute=0, fetched_at=FETCHED):
    idx = pd.to_datetime(dates) + pd.Timedelta(hours=hour, minutes=minute) if len(dates) else pd.DatetimeIndex([])
    s = pd.Series(values, index=idx, dtype=float, name=name)
    if fetched_at is not None:
        s.attrs["fetched_at"] = fetched_at
    s.attrs["source"] = f"Yahoo:{name}"
    s.attrs["exchange_tz"] = source_tz
    return s


def taiex(dates, values, **kw):
    return _yahoo(dates, values, name="^TWII", source_tz="Asia/Taipei", hour=1, **kw)


def sp500(dates, values, *, fetched_at=FETCHED):
    """^GSPC：時間戳＝紐約 09:30（冬夏令各自換算成 UTC，所以交易所當地時刻恆為 09:30）。"""
    idx = (pd.to_datetime(dates) + pd.Timedelta(hours=9, minutes=30)).tz_localize("America/New_York").tz_convert("UTC") \
        if len(dates) else pd.DatetimeIndex([])
    s = pd.Series(values, index=idx.tz_localize(None) if len(dates) else idx, dtype=float, name="^GSPC")
    s.attrs["fetched_at"] = fetched_at
    s.attrs["source"] = "Yahoo:^GSPC"
    s.attrs["exchange_tz"] = "America/New_York"
    return s


def vix(dates, values, **kw):
    return _yahoo(dates, values, name="^VIX", source_tz="Etc/UTC", hour=0, **kw)


def fred_frame(dates, values, *, series, fetched_at=FETCHED):
    rows = [{"date": pd.Timestamp(d), "value": v, "realtime_start": pd.Timestamp("2026-11-03"),
             "source": f"FRED:{series}", "fetched_at": fetched_at} for d, v in zip(dates, values)]
    return pd.DataFrame(rows, columns=["date", "value", "realtime_start", "source", "fetched_at"])


def wave(n, base, step, amp=0.0):
    return [base + i * step + amp * math.sin(i / 7.0) for i in range(n)]


class Fetch:
    def __init__(self, result):
        self.result = result

    def __call__(self, *a, **k):
        if isinstance(self.result, Exception):
            raise self.result
        return self.result


def long_us_dates():
    return weekdays("2021-06-01", LAST_US)


def long_tw_dates():
    return [d for d in long_us_dates() if d not in ("2026-10-26",)]   # 少一天：兩市場休市日不同


def view(*, tw="ok", us="ok", vx="ok", key=KEY, tw_dates=None, us_dates=None):
    """`tw`／`us`／`vx`：`ok`、`error`（L1 回 error）、`missing`（空序列且有收盤規則全略過→資料未備）、或直接給 (series, error)。"""
    tdates = tw_dates or long_tw_dates()
    udates = us_dates or long_us_dates()

    def pick(spec, ok_series):
        if spec == "ok":
            return ok_series, None
        if spec == "error":
            return None, "HTTP 429 secret-token-abc123"
        if spec == "missing":   # 來源有回、但每一筆都是非有限值 → L2 判「資料未備」（不是取數失敗）
            return ok_series * float("nan"), None
        return spec
    t = pick(tw, taiex(tdates, wave(len(tdates), 15000, 3.0, 400)))
    s = pick(us, sp500(udates, wave(len(udates), 4000, 1.5, 150)))
    v = pick(vx, vix(udates, wave(len(udates), 18, 0.0, 4)))
    fdates = udates[-1500:]
    fred = Fetch_FRED({"DGS10": (fred_frame(fdates, wave(len(fdates), 3.5, 0.0005, 0.3), series="DGS10"), None),
                       "DGS2": (fred_frame(fdates, wave(len(fdates), 3.0, 0.0005, 0.4), series="DGS2"), None)})
    return mv.build_market_view(fetch_vix=Fetch(v), fetch_taiex=Fetch(t), fetch_sp500=Fetch(s), fetch_fred=fred,
                                fred_api_key=key)


class Fetch_FRED:
    def __init__(self, by_series):
        self.by_series = by_series

    def __call__(self, series_id, api_key, n):
        result = self.by_series[series_id]
        if isinstance(result, Exception):
            raise result
        return result


def _rows(key, dates, values, unit):
    return [{"indicator_key": key, "obs_date": d, "release_date": d, "value_num": v, "value_unit": unit,
             "source_tier": "T1", "is_revised": False, "fetched_at": FETCHED} for d, v in zip(dates, values)]


def table(*, errors=None, drop=()):
    """B 線 `build_market_indicator_table` 形狀的替身。`drop`：不給列的鍵；`errors`：{鍵: 原文}。"""
    dates = weekdays("2025-06-02", LAST_US)
    rows = []
    for key, base, unit in (("vol_index", 18.0, "index"), ("credit_spread_pct", 3.2, "pp"),
                            ("term_spread_pct", 0.4, "pp"), ("policy_rate_pct", 4.1, "%")):
        if key not in drop:
            rows += _rows(key, dates, wave(len(dates), base, 0.001, 0.2), unit)
    return {"rows": rows, "errors": dict(errors or {}),
            "pending": {"leading_index": "ndc_no_release_date", "coincident_index": "ndc_no_release_date",
                        "fx_twd_per_usd": "fx_obs_date_rule"}}
