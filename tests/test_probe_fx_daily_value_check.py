"""tests/test_probe_fx_daily_value_check.py — `scripts/probe_fx_obs_date.py` 的「日 K 值對應哪個時刻」演算法（不連網）。

以**已知對應時刻**的合成日 K 與小時 K 確認演算法找得到。合成小時 K 照「時間戳＝區間起點」的慣例造
（#960 稽核：Yahoo 小時 K 的慣例未實證，腳本以此為前提並兩種時刻都輸出）：
先定一條每個整點一個值的價格路徑 p(T)（逐點遞增、彼此不同），起點 s 的小時 K 是 open＝p(s)、close＝p(s＋1h)。
日 K close 設成 p(目標時刻) ⇒ close 對應應為「終點＝目標時刻」那一根、open 對應應為「起點＝目標時刻」那一根。
小時 K 只造倫敦當地平日（週末缺口與真實匯率相同）。時間戳都由 zoneinfo 換算，不手寫 Unix 秒。
"""
from __future__ import annotations

import importlib.util
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "probe_fx_obs_date.py"
_spec = importlib.util.spec_from_file_location("probe_fx_obs_date_dvc", _SCRIPT)
probe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(probe)

LONDON = "Europe/London"
_LZ = ZoneInfo(LONDON)
_T0 = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())


def _sec(dt: datetime) -> int:
    """不帶時區的 datetime 視為 UTC。"""
    return int(dt.replace(tzinfo=timezone.utc).timestamp())


def _lon(y, m, d, hh=0) -> int:
    """倫敦當地時刻 → Unix 秒。"""
    return int(datetime(y, m, d, hh, tzinfo=_LZ).timestamp())


def _p(sec: int) -> float:
    """價格路徑：每個整點一個值，逐點遞增、彼此不同。"""
    return round(30.0 + (sec - _T0) / 3600 * 0.001, 6)


def _hourly(first: date, last: date):
    """first～last（倫敦當地日，含）之間的平日，每個倫敦整點一根：open＝p(s)、close＝p(s＋1h)。"""
    t, o, h, lo, c = [], [], [], [], []
    d = first
    while d <= last:
        if d.weekday() < 5:
            for hh in range(24):
                s = _lon(d.year, d.month, d.day, hh)
                op, cl = _p(s), _p(s + 3600)
                t.append(s), o.append(op), c.append(cl), h.append(max(op, cl) + 0.0005), lo.append(min(op, cl) - 0.0005)
        d += timedelta(days=1)
    return {"meta": {"exchangeTimezoneName": LONDON}, "t": t, "open": o, "high": h, "low": lo, "close": c,
            "missing_fields": []}


def _daily(stamps_and_closes):
    t = [s for s, _c in stamps_and_closes]
    c = [v for _s, v in stamps_and_closes]
    return {"meta": {"exchangeTimezoneName": LONDON}, "t": t, "open": list(c), "high": list(c), "low": list(c),
            "close": c, "missing_fields": []}


# 冬令（倫敦＝UTC）：2026-01-05（一）～ 01-23（五）三週平日
_WINTER = _hourly(date(2026, 1, 5), date(2026, 1, 23))
_MID = [date(2026, 1, d) for d in (13, 14, 15)]   # 第二週週二～週四：前後各有足夠的交易所日


def _run(daily, hourly=_WINTER, cutoff="2026-01-25", **kw):
    return probe.match_daily_to_hourly(daily, hourly, LONDON, cutoff, **kw)


def test_標D的close等於前一日21點_終點與起點都找得到():
    daily = _daily([(_lon(d.year, d.month, d.day), _p(_lon(d.year, d.month, d.day) - 3 * 3600)) for d in _MID])
    out = _run(daily)
    assert out["compared"] == 3
    for rec in out["bars"]:
        bc, bo = rec["best_close_match"], rec["best_open_match"]
        assert rec["partial_coverage"] is False and rec["duplicate_obs_date"] is False
        assert bc["timed_by"] == "end" and bc["exchange_day_offset"] == -1 and bc["exchange_hhmm"] == "21:00"
        assert bc["start_exchange_hhmm"] == "20:00" and bc["abs_diff"] == 0 and bc["ties"] == 1 and bc["within_tol"]
        assert bc["end"]["Europe/London"].endswith("21:00") and bc["end"]["utc"].endswith("21:00")
        assert bc["end"]["America/New_York"].endswith("16:00") and bc["end"]["Asia/Taipei"].endswith("05:00")
        assert bc["start"]["Europe/London"].endswith("20:00")
        assert bo["timed_by"] == "start" and bo["exchange_day_offset"] == -1 and bo["exchange_hhmm"] == "21:00"
    assert out["best_close_match_distribution"] == {"-1 21:00": 3}
    assert out["best_close_match_distribution_by_start"] == {"-1 20:00": 3}
    assert out["best_close_match_utc_distribution"] == {"21:00": 3}
    assert out["best_open_match_distribution"] == {"-1 21:00": 3}
    assert out["match_precision"]["in_distribution"] == 3 and out["match_precision"]["max_abs_diff"] == 0


def test_標D的close等於當日最後一根的close_終點在隔日00點_計入等於當日():
    daily = _daily([(_lon(d.year, d.month, d.day), _p(_lon(d.year, d.month, d.day) + 24 * 3600)) for d in _MID])
    out = _run(daily)
    assert out["best_close_match_distribution"] == {"+1 00:00": 3}       # 終點＝隔日 00:00
    assert out["best_close_match_distribution_by_start"] == {"+0 23:00": 3}
    assert out["close_equals_same_day_last_hourly_close"] == 3
    assert all(r["close_vs_day_last_hourly_close"]["-1"] > 0 for r in out["bars"])   # 路徑遞增


def test_標D的close等於前一日最後一根的close_計入等於前一日():
    daily = _daily([(_lon(d.year, d.month, d.day), _p(_lon(d.year, d.month, d.day))) for d in _MID])
    out = _run(daily)
    assert out["best_close_match_distribution"] == {"+0 00:00": 3}
    assert out["close_equals_prev_day_last_hourly_close"] == 3
    assert out["close_equals_same_day_last_hourly_close"] == 0


def test_週一的值等於週五紐約17點_跨週末缺口找得到_前一日取週五():
    """週一 01-19 的日 K close＝週五 01-16 紐約 17:00（冬令＝倫敦 22:00）的價格。以日曆日 ±2 計時週五在範圍外；
    以「有小時 K 的交易所日」計，前兩個交易所日是週四、週五（#960 稽核）。"""
    mon = _lon(2026, 1, 19)
    target = int(datetime(2026, 1, 16, 17, tzinfo=ZoneInfo("America/New_York")).timestamp())
    out = _run(_daily([(mon, _p(target))]))
    (rec,) = out["bars"]
    bc = rec["best_close_match"]
    assert rec["scope_exchange_days"] == ["2026-01-15", "2026-01-16", "2026-01-19", "2026-01-20", "2026-01-21"]
    assert bc["exchange_day_offset"] == -3 and bc["exchange_hhmm"] == "22:00"
    assert bc["end"]["America/New_York"] == "2026-01-16 17:00"
    assert rec["close_vs_day_last_hourly_close_days"]["-1"] == "2026-01-16"
    assert out["best_close_match_distribution"] == {"-3 22:00": 1}


def test_夏令時倫敦_日K在UTC前一天23點_日差以交易所當地日計():
    summer = _hourly(date(2026, 7, 1), date(2026, 7, 17))
    d_stamp = _lon(2026, 7, 8)                          # 倫敦 07-08（三）00:00 ＝ UTC 07-07 23:00
    target = _lon(2026, 7, 7, 21)                       # 倫敦 07-07 21:00 ＝ UTC 20:00
    (rec,) = _run(_daily([(d_stamp, _p(target))]), summer, "2026-07-20")["bars"]
    bc = rec["best_close_match"]
    assert rec["obs_date"] == "2026-07-08"
    assert bc["exchange_day_offset"] == -1 and bc["exchange_hhmm"] == "21:00" and bc["end"]["utc"].endswith("20:00")


def test_夏令時倫敦_終點在UTC前一天23點_日差仍以交易所當地日計為0():
    """終點 UTC 07-07 23:00 ＝ 倫敦 07-08 00:00：交易所日差是 0，不是以 UTC 日期算出的 −1。"""
    summer = _hourly(date(2026, 7, 1), date(2026, 7, 17))
    d_stamp = _lon(2026, 7, 8)
    (rec,) = _run(_daily([(d_stamp, _p(d_stamp))]), summer, "2026-07-20")["bars"]
    bc = rec["best_close_match"]
    assert bc["exchange_day_offset"] == 0 and bc["exchange_hhmm"] == "00:00" and bc["end"]["utc"] == "2026-07-07 23:00"


def test_同一交易所日的OHLC彙總與區間判斷_高低缺時回None():
    agg = probe.hourly_day_aggregate(_WINTER, LONDON)["2026-01-13"]
    i0 = _WINTER["t"].index(_lon(2026, 1, 13))
    i1 = _WINTER["t"].index(_lon(2026, 1, 13, 23))
    assert agg["bars"] == 24 and agg["open"] == _WINTER["open"][i0] and agg["close"] == _WINTER["close"][i1]
    assert agg["high"] == max(_WINTER["high"][i0:i1 + 1]) and agg["low"] == min(_WINTER["low"][i0:i1 + 1])
    day = _lon(2026, 1, 13)
    out = _run(_daily([(day, _p(day + 12 * 3600)), (_lon(2026, 1, 14), agg["high"] + 1.0)]))
    r_in, r_out = out["bars"]
    assert r_in["vs_same_exchange_day"]["close_within_hourly_range"] is True
    assert r_out["vs_same_exchange_day"]["close_within_hourly_range"] is False
    no_hl = dict(_WINTER, high=[None] * len(_WINTER["t"]), low=[None] * len(_WINTER["t"]))
    (r_none,) = _run(_daily([(day, _p(day + 12 * 3600))]), no_hl)["bars"]
    assert r_none["vs_same_exchange_day"]["close_within_hourly_range"] is None   # 不是 False


def test_觀測窗下界_邊界那根要比_早一天的不比_窗外null不計():
    """window_days＝3、cutoff＝01-16 ⇒ 觀測窗 [01-13, 01-16)：01-13 這根（非 null）要比，01-12 不比；
    01-12 的 null 在窗外不計入 daily_close_null，01-14 的 null 在窗內才計；01-16 未收盤。"""
    rows = [(_lon(2026, 1, 12), None), (_lon(2026, 1, 13), _p(_lon(2026, 1, 13))),
            (_lon(2026, 1, 14), None), (_lon(2026, 1, 15), _p(_lon(2026, 1, 15))),
            (_lon(2026, 1, 16), _p(_lon(2026, 1, 16)))]
    out = _run(_daily(rows), cutoff="2026-01-16", window_days=3)
    assert [r["obs_date"] for r in out["bars"]] == ["2026-01-13", "2026-01-15"]
    assert out["skipped"] == {"daily_close_null": 1, "not_closed": 1}


def test_容差外的近似對應_逐根照列但不入分布_精度統計照實():
    day = _lon(2026, 1, 13)
    exact = _p(day - 3 * 3600)
    approx = exact + 0.0003                              # 落在兩個整點值之間（步長 0.001），最近那根差 0.0003
    out = _run(_daily([(day, approx), (_lon(2026, 1, 14), _p(_lon(2026, 1, 14) - 3 * 3600))]))
    r_approx, r_exact = out["bars"]
    assert r_approx["best_close_match"]["within_tol"] is False and r_exact["best_close_match"]["within_tol"]
    assert out["best_close_match_distribution"] == {"-1 21:00": 1}
    prec = out["match_precision"]
    assert prec["within_tol"] == 1 and prec["in_distribution"] == 1
    assert prec["max_abs_diff"] == pytest.approx(0.0003, abs=1e-9)
    assert prec["median_abs_diff"] == pytest.approx(0.00015, abs=1e-9)   # (0.0003 ＋ 0) / 2


def test_同差距多根_ties大於1不入分布_null小時值不參與_小時序列以外的根標partial():
    hourly = _hourly(date(2026, 1, 5), date(2026, 1, 23))
    i_a = hourly["t"].index(_lon(2026, 1, 13, 5))
    i_b = hourly["t"].index(_lon(2026, 1, 13, 9))
    hourly["close"][i_a] = hourly["close"][i_b]        # 兩根同值
    hourly["close"][hourly["t"].index(_lon(2026, 1, 13, 1))] = None
    day = _lon(2026, 1, 13)
    out = _run(_daily([(day, hourly["close"][i_b]), (_lon(2026, 2, 20), 31.0)]), hourly, cutoff="2026-02-25",
               window_days=60)
    tied, away = out["bars"]
    assert tied["best_close_match"]["ties"] == 2 and tied["best_close_match"]["t"] == hourly["t"][i_a]
    assert out["best_close_match_distribution"] == {} and out["match_precision"]["ties_gt_1"] == 1
    # 02-20 在小時序列（到 01-23）之外：前兩個有小時 K 的交易所日是 01-22、01-23，之後沒有 ⇒ partial_coverage，不入分布
    assert away["partial_coverage"] is True and away["scope_exchange_days"] == ["2026-01-22", "2026-01-23"]
    empty = dict(hourly, t=[], open=[], high=[], low=[], close=[])
    (none,) = _run(_daily([(day, 30.0)]), empty, cutoff="2026-01-25")["bars"]
    assert none["status"] == "no_hourly_in_scope"


def test_小時序列頭尾_前後不足N個交易所日_partial_coverage且不入分布():
    first = _lon(2026, 1, 6)                             # 小時序列從 01-05 起：01-06 之前只有 1 個交易所日
    out = _run(_daily([(first, _p(first - 3 * 3600)), (_lon(2026, 1, 14), _p(_lon(2026, 1, 14) - 3 * 3600))]))
    r_head, r_mid = out["bars"]
    assert r_head["partial_coverage"] is True and r_mid["partial_coverage"] is False
    assert r_head["best_close_match"]["within_tol"]     # 仍逐根照列
    assert out["best_close_match_distribution"] == {"-1 21:00": 1}
    assert out["match_precision"]["partial_coverage"] == 1


def test_同一觀測日重複的日K_標記且不入分布():
    day = _lon(2026, 1, 14)
    out = _run(_daily([(day, _p(day - 3 * 3600)), (day + 3600, _p(day - 2 * 3600))]))
    assert all(r["duplicate_obs_date"] for r in out["bars"])
    assert out["best_close_match_distribution"] == {} and out["match_precision"]["duplicate_obs_date"] == 2


def test_raw_series與報告為嚴格JSON_NaN轉null(tmp_path):
    nan = float("nan")
    ohlc = {"t": [1, 2], "open": [1.0, nan], "high": [float("inf"), 2.0], "low": [None, 1.0], "close": [nan, 2.0],
            "missing_fields": []}
    raw = probe.raw_series(ohlc)
    assert raw["open"] == [1.0, None] and raw["high"] == [None, 2.0] and raw["close"] == [None, 2.0]
    json.dumps(raw, allow_nan=False)
    assert probe.to_strict_json({"a": [nan, 1.0, {"b": float("-inf")}]}) == {"a": [None, 1.0, {"b": None}]}


def test_main寫出的報告是嚴格JSON(tmp_path):
    ts = [_lon(2026, 1, d) for d in (12, 13, 14)]
    payload = {"chart": {"result": [{"meta": {"exchangeTimezoneName": LONDON, "regularMarketTime": ts[-1]},
                                     "timestamp": ts, "indicators": {"quote": [{"close": [30.0, float("nan"), 30.2]}]}}],
                         "error": None}}

    class _R:
        content = b""

        def json(self):
            return payload

    out = tmp_path / "r.json"
    probe.main(["--tickers", "USDTWD=X", "--out", str(out)], fetcher=lambda *a, **k: _R(),
               pop_fail_kind=lambda: "", backoff_check=lambda u: (False, 0.0, ""))
    text = out.read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    json.loads(text, parse_constant=lambda c: pytest.fail(f"報告含非標準常數 {c}"))


# ═══════════════════════ #960 稽核：守衛（突變存活的那幾條） ═══════════════════════


def _payload(ts, closes):
    return {"chart": {"result": [{"meta": {"exchangeTimezoneName": LONDON, "regularMarketTime": ts[-1]},
                                  "timestamp": ts, "indicators": {"quote": [{"close": closes}]}}], "error": None}}


class _Resp:
    def __init__(self, payload):
        self._p = payload
        self.content = b""

    def json(self):
        return self._p


def test_日K失敗時不打小時K():
    calls = []

    def fetch(url, params=None, **_k):
        calls.append((url.rsplit("/", 1)[1], params["interval"]))
        if url.endswith("/USDTWD=X") and params["interval"] == "1d":
            return None
        return _Resp(_payload([_lon(2026, 1, 13), _lon(2026, 1, 14)], [30.0, 30.1]))

    rep = probe.run(["USDTWD=X", "EURTWD=X"], fetcher=fetch, pop_fail_kind=lambda: "x",
                    backoff_check=lambda u: (False, 0.0, ""))
    assert ("USDTWD=X", "60m") not in calls and ("EURTWD=X", "60m") in calls
    assert "hourly" not in rep["tickers"]["USDTWD=X"]


def test_小時K分析失敗時_hourly_error記原文():
    def fetch(url, params=None, **_k):
        if params["interval"] == "60m":
            return _Resp({"chart": {"result": None, "error": None}})      # 結構不符 ⇒ extract_chart 拋 ValueError
        return _Resp(_payload([_lon(2026, 1, 13), _lon(2026, 1, 14)], [30.0, 30.1]))

    rep = probe.run(["USDTWD=X"], fetcher=fetch, pop_fail_kind=lambda: "", backoff_check=lambda u: (False, 0.0, ""))
    h = rep["tickers"]["USDTWD=X"]["hourly"]
    assert h["status"] == probe.STATUS_ANALYSIS_FAILED
    assert h["error"].startswith("小時 K 分析失敗：ValueError: chart.result 為空")
    assert rep["tickers"]["USDTWD=X"]["daily_value_check"] is None


def test_未收盤界線走正式not_closed_cutoff_day(monkeypatch):
    """以替身記錄呼叫並回一個與 UTC 日、倫敦日都不同的日子，確認結果的 cutoff_day 就是它（不另寫一份）。"""
    from services.v2_tables import market_indicator as mi
    seen = []

    def spy(fetched_at, zone):
        seen.append((fetched_at, str(zone)))
        return "2026-01-14"

    monkeypatch.setattr(mi, "not_closed_cutoff_day", spy)
    ts = [_lon(2026, 1, d) for d in (12, 13, 14, 15)]
    daily = _payload(ts, [30.0, 30.1, 30.2, 30.3])
    hourly = {"chart": {"result": [{"meta": {"exchangeTimezoneName": LONDON}, "timestamp": _WINTER["t"],
                                    "indicators": {"quote": [{k: _WINTER[k] for k in ("open", "high", "low", "close")}]}}],
                        "error": None}}
    out = probe.daily_value_check(daily, hourly, "2026-01-20T12:00:00+00:00")
    assert seen == [("2026-01-20T12:00:00+00:00", LONDON)]
    assert out["cutoff_day"] == "2026-01-14"
    assert [r["obs_date"] for r in out["bars"]] == ["2026-01-12", "2026-01-13"]
    assert out["skipped"]["not_closed"] == 2


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


# ═══════════════════════ #960 稽核 B1：小時 K 失敗不得讓後續代號的日 K 因同主機冷卻被跳過 ═══════════════════════


def _daily_payload_oct():
    ts = [_sec(datetime(2026, 10, d, 23)) for d in (5, 6, 7, 8, 9, 12)]
    return {"chart": {"result": [{"meta": {"exchangeTimezoneName": LONDON, "regularMarketTime": ts[-1]},
                                  "timestamp": ts,
                                  "indicators": {"quote": [{"open": [32.0] * 6, "high": [32.1] * 6,
                                                            "low": [31.9] * 6, "close": [32.0] * 6}]}}],
                      "error": None}}


@pytest.mark.parametrize("status", [403, 429, 422])
def test_B1_小時K失敗_所有代號日K仍是ok_用真的source_backoff(monkeypatch, status):
    """用真的 `infra.proxy.fetch_url` 與 `infra.source_backoff`（只換 session、關代理、不真的 sleep）：
    小時 K 回 403／429／422 會讓 `fetch_url` 以主機為鍵記冷卻；若「日 K → 立即小時 K」逐代號交錯，
    後面代號（含必取的 ^VIX）的日 K 會變成 skipped_backoff_no_request（稽核 P、Q 重現）。"""
    import json as _json
    import time

    import infra.proxy as px

    daily = _daily_payload_oct()

    class _R:
        def __init__(self, code, body):
            self.status_code, self._b = code, body
            self.content = _json.dumps(body).encode()
            self.text = self.content.decode()
            self.headers = {}

        def json(self):
            return self._b

    calls = []

    class _Sess:
        def get(self, url, params=None, **_k):
            calls.append((url.rsplit("/", 1)[1], params["interval"]))
            if params["interval"] == "60m":
                return _R(status, {"chart": {"result": None, "error": {"code": "x"}}})
            return _R(200, daily)

    monkeypatch.setattr(px, "get_proxy_config", lambda: None)
    monkeypatch.setattr(px, "_get_thread_session", lambda: _Sess())
    monkeypatch.setattr(time, "sleep", lambda _s: None)
    rep = probe.run(["USDTWD=X", "^VIX", "EURTWD=X", "JPYTWD=X"])
    assert {tk: e["status"] for tk, e in rep["tickers"].items()} == {
        "USDTWD=X": "ok", "^VIX": "ok", "EURTWD=X": "ok", "JPYTWD=X": "ok"}
    assert [tk for tk, iv in calls[:4]] == ["USDTWD=X", "^VIX", "EURTWD=X", "JPYTWD=X"]   # 日 K 全部先取完
    assert all(iv == "1d" for _tk, iv in calls[:4]) and all(iv == "60m" for _tk, iv in calls[4:])
    assert rep["tickers"]["USDTWD=X"]["hourly"]["status"] == probe.STATUS_REQUEST_FAILED


# ═══════════════════════ #960 複驗：週末的前一日、寬鬆容差、嚴格 JSON 保底 ═══════════════════════


def test_前一日對照跳過週日_週日傍晚有小時K時週一的負1仍是週五():
    """合成資料加上倫敦週日 22:00、23:00 兩根（真實匯率週日傍晚就開盤）。週一 01-19 的日 K close＝週五 01-16 最後一根
    小時 close：前一日對照必須取週五（不是週日），且計入「等於前一日最後一根」。最佳對應的候選範圍照舊含週日。"""
    hourly = _hourly(date(2026, 1, 5), date(2026, 1, 23))
    for hh in (22, 23):                                  # 週日 01-18 倫敦 22:00、23:00
        s = _lon(2026, 1, 18, hh)
        i = next(k for k, t in enumerate(hourly["t"]) if t > s)
        for f, v in (("t", s), ("open", _p(s)), ("close", _p(s + 3600)), ("high", _p(s + 3600) + 0.0005),
                     ("low", _p(s) - 0.0005)):
            hourly[f].insert(i, v)
    mon = _lon(2026, 1, 19)
    fri_last = _p(_lon(2026, 1, 17))                     # 週五 23:00 那根的 close＝p(週六 00:00)
    out = _run(_daily([(mon, fri_last)]), hourly)
    (rec,) = out["bars"]
    assert rec["close_vs_day_last_hourly_close_days"]["-1"] == "2026-01-16"
    assert abs(rec["close_vs_day_last_hourly_close"]["-1"]) < 1e-9
    assert out["close_equals_prev_day_last_hourly_close"] == 1
    assert "2026-01-18" in rec["scope_exchange_days"]    # 候選範圍仍含週日


def test_寬鬆容差兩級_各級只收ties等於1_主分布仍以1e6為準():
    """日 K close＝前一日 21:00 的價格 ×(1＋5e-6)：1e-6 級不在容差內（主分布空），1e-5 級在容差內且 ties＝1（入分布），
    1e-4 級雖在容差內，但前後幾根也落在 best＋1e-4 內 ⇒ ties＞1，不入該級分布。"""
    day = _lon(2026, 1, 14)
    close = _p(day - 3 * 3600) * (1 + 5e-6)
    out = _run(_daily([(day, close)]))
    (rec,) = out["bars"]
    bc = rec["best_close_match"]
    assert bc["within_tol"] is False and bc["loose"]["1e-05"] == {"within_tol": True, "ties": 1}
    assert bc["loose"]["0.0001"]["within_tol"] is True and bc["loose"]["0.0001"]["ties"] > 1
    loose = out["match_precision"]["loose"]
    assert out["best_close_match_distribution"] == {}
    assert loose["1e-05"] == {"tolerance_rel": 1e-05, "within_tol": 1, "distribution": {"-1 21:00": 1}}
    assert loose["0.0001"]["within_tol"] == 1 and loose["0.0001"]["distribution"] == {}


@pytest.mark.parametrize("bad", [{float("nan"): 1}, {"v": __import__("decimal").Decimal("1.5")}])
def test_嚴格JSON寫不出時_改以寬鬆格式保底_記錯誤原文且退出碼非0(tmp_path, monkeypatch, bad):
    report = {"proxy_env_set": False, "proxy_used_by_infra": None, "rejected_tickers": [],
              "tickers": {"USDTWD=X": {"ok": True, "status": "ok", "daily": {"close": 31.9}}}, "extra": bad}
    monkeypatch.setattr(probe, "run", lambda *a, **k: report)
    monkeypatch.setattr(probe, "_summary_lines", lambda rep: [])
    out = tmp_path / "r.json"
    rc = probe.main(["--out", str(out)])
    text = out.read_text(encoding="utf-8")
    loaded = json.loads(text)                            # 寬鬆格式照樣讀得回來
    assert rc != 0
    assert loaded["strict_json_error"].split(":")[0] in ("ValueError", "TypeError")
    assert loaded["tickers"]["USDTWD=X"]["daily"] == {"close": 31.9}   # 日 K 結果不丟


def test_嚴格JSON寫得出時_不加strict_json_error_退出碼照主要代號(tmp_path, monkeypatch):
    report = {"proxy_env_set": False, "proxy_used_by_infra": None, "rejected_tickers": [],
              "tickers": {"USDTWD=X": {"ok": True, "status": "ok"}}}
    monkeypatch.setattr(probe, "run", lambda *a, **k: report)
    monkeypatch.setattr(probe, "_summary_lines", lambda rep: [])
    out = tmp_path / "r.json"
    assert probe.main(["--out", str(out)]) == 0
    assert "strict_json_error" not in json.loads(out.read_text(encoding="utf-8"))


# ═══════════════════════ 2026-10-14 開閘前小項（#960 延後項） ═══════════════════════


def test_寬鬆級分布_不收partial():
    """稽核 P 突變 L4 存活項：寬鬆級分布須與主分布同樣排除 partial_coverage 的根。
    01-06（小時序列從 01-05 起，前面不足 2 個交易所日 ⇒ partial）與 01-14 兩根都只在 1e-5 級容差內。"""
    head, mid = _lon(2026, 1, 6), _lon(2026, 1, 14)
    out = _run(_daily([(head, _p(head - 3 * 3600) * (1 + 5e-6)), (mid, _p(mid - 3 * 3600) * (1 + 5e-6))]))
    r_head, r_mid = out["bars"]
    assert r_head["partial_coverage"] is True and r_mid["partial_coverage"] is False
    assert r_head["best_close_match"]["loose"]["1e-05"] == {"within_tol": True, "ties": 1}
    loose = out["match_precision"]["loose"]["1e-05"]
    assert loose["within_tol"] == 2                                  # 容差內計數兩根都算
    assert loose["distribution"] == {"-1 21:00": 1}                  # 分布只收非 partial 那一根


def test_寬鬆級分布_不收觀測日重複的根():
    """同一倫敦日兩根日 K（00:00 與 01:00），各自在 1e-5 級容差內、ties＝1 ⇒ 計入容差內，但不入寬鬆級分布。"""
    day = _lon(2026, 1, 14)
    out = _run(_daily([(day, _p(day - 3 * 3600) * (1 + 5e-6)), (day + 3600, _p(day - 2 * 3600) * (1 + 5e-6))]))
    assert all(r["duplicate_obs_date"] for r in out["bars"])
    assert all(r["best_close_match"]["loose"]["1e-05"] == {"within_tol": True, "ties": 1} for r in out["bars"])
    loose = out["match_precision"]["loose"]["1e-05"]
    assert loose["within_tol"] == 2 and loose["distribution"] == {}


def test_寬鬆容差邊界_差距恰等於容差算在內_多一點就不算(monkeypatch):
    """稽核 P 突變 L7 存活項（`<=` 改 `<`）。以二進位精確值構造：容差 2⁻¹⁰、日 K close 32 ⇒ 容差絕對值 2⁻⁵；
    小時 close 32 ＋ 2⁻⁵ 差距恰為 2⁻⁵（浮點精確）⇒ 在容差內；再加 2⁻²⁰ ⇒ 不在。其餘小時值約 30，遠在容差外。"""
    monkeypatch.setattr(probe, "MATCH_LOOSE_RELS", (2 ** -10,))
    lvl = f"{2 ** -10:g}"
    day = _lon(2026, 1, 14)
    i = _WINTER["t"].index(day - 4 * 3600)                           # 起點 01-13 20:00 ⇒ 終點 21:00
    for extra, inside in ((0.0, True), (2 ** -20, False)):
        hourly = dict(_WINTER, close=list(_WINTER["close"]))
        hourly["close"][i] = 32.0 + 2 ** -5 + extra
        out = _run(_daily([(day, 32.0)]), hourly)
        (rec,) = out["bars"]
        assert rec["best_close_match"]["abs_diff"] == 2 ** -5 + extra
        assert rec["best_close_match"]["loose"][lvl]["within_tol"] is inside
        assert out["match_precision"]["loose"][lvl]["within_tol"] == int(inside)
        assert out["match_precision"]["loose"][lvl]["distribution"] == ({"-1 21:00": 1} if inside else {})


def test_固定位移掃描_close等於D日00點價格_終點版k0與起點版k0中位差為0():
    """日 K close＝p(倫敦 D 日 00:00)：終點落在 00:00 的那根（起點 23:00）close＝p(00:00)；起點落在 00:00 的那根 open＝p(00:00)。"""
    daily = _daily([(_lon(d.year, d.month, d.day), _p(_lon(d.year, d.month, d.day))) for d in _MID])
    scan = _run(daily)["fixed_offset_scan"]
    assert scan["k_hours"] == [-6, 26] and scan["daily_bars"] == 3 and scan["exchange_tz"] == LONDON
    assert set(scan["by_end"]) == {f"{k:+d}" for k in range(-6, 27)} == set(scan["by_start"])
    assert scan["by_end"]["+0"] == {"n": 3, "median_pct_diff": 0.0, "median_abs_pct_diff": 0.0}
    assert scan["by_start"]["+0"] == {"n": 3, "median_pct_diff": 0.0, "median_abs_pct_diff": 0.0}
    # 價格路徑遞增：k＞0 的小時價高於 close、k＜0 低於；離 0 越遠差越大
    assert scan["by_end"]["+1"]["median_pct_diff"] > 0 > scan["by_end"]["-1"]["median_pct_diff"]
    assert scan["by_end"]["+5"]["median_abs_pct_diff"] > scan["by_end"]["+1"]["median_abs_pct_diff"]


def test_固定位移掃描_close等於前一日21點_終點版與起點版都在k負3():
    daily = _daily([(_lon(d.year, d.month, d.day), _p(_lon(d.year, d.month, d.day) - 3 * 3600)) for d in _MID])
    scan = _run(daily)["fixed_offset_scan"]
    assert scan["by_end"]["-3"]["median_abs_pct_diff"] == 0.0 and scan["by_start"]["-3"]["median_abs_pct_diff"] == 0.0
    assert min(v["median_abs_pct_diff"] for k, v in scan["by_end"].items() if k != "-3") > 0


def test_固定位移掃描_夏令以當地00點為錨_小時K缺那一刻不計_重複觀測日不入():
    """夏令（倫敦＝UTC＋1）：D 日 00:00 ＝ UTC D−1 23:00；錨點以 zoneinfo 換算。
    週一 07-13 的終點版 k＝0 要的是起點週日 23:00 那根 —— 合成小時 K 沒有週日 ⇒ 該根在終點版 k＝0 不計（起點版有）。
    同一倫敦日兩根（07-07 的 00:00 與 01:00，重複）不入掃描。"""
    summer = _hourly(date(2026, 7, 1), date(2026, 7, 17))
    tue, wed, thu, mon = (_lon(2026, 7, d) for d in (7, 8, 9, 13))
    out = _run(_daily([(tue, _p(tue)), (tue + 3600, 1.0), (wed, _p(wed)), (thu, _p(thu)), (mon, _p(mon))]),
               summer, "2026-07-20")
    scan = out["fixed_offset_scan"]
    assert scan["daily_bars"] == 3                                    # 07-08、07-09、07-13；07-07 兩根重複不入
    assert scan["by_end"]["+0"] == {"n": 2, "median_pct_diff": 0.0, "median_abs_pct_diff": 0.0}
    assert scan["by_start"]["+0"] == {"n": 3, "median_pct_diff": 0.0, "median_abs_pct_diff": 0.0}
    assert summer["t"][0] == _lon(2026, 7, 1)                          # 錨點換算：倫敦 00:00 ＝ UTC 前一天 23:00
    assert datetime.fromtimestamp(wed, timezone.utc).hour == 23


def test_摘要行列出固定位移掃描最小的k():
    scan = {"by_end": {"-1": {"n": 3, "median_pct_diff": -0.1, "median_abs_pct_diff": 0.1},
                       "+0": {"n": 3, "median_pct_diff": 0.0, "median_abs_pct_diff": 0.0},
                       "+1": {"n": 0, "median_pct_diff": None, "median_abs_pct_diff": None}}}
    assert probe._scan_best(scan, "by_end") == "k=+0 0.0000% n=3"
    assert probe._scan_best(scan, "by_start") is None and probe._scan_best(None, "by_end") is None


def test_寬鬆格式保底_tuple鍵以skipkeys略過該鍵_其餘照寫(tmp_path, monkeypatch):
    report = {"proxy_env_set": False, "proxy_used_by_infra": None, "rejected_tickers": [],
              "tickers": {"USDTWD=X": {"ok": True, "status": "ok", "daily": {"close": 31.9}}},
              "extra": {("a", "b"): 1, "kept": 2}}
    monkeypatch.setattr(probe, "run", lambda *a, **k: report)
    monkeypatch.setattr(probe, "_summary_lines", lambda rep: [])
    out = tmp_path / "r.json"
    assert probe.main(["--out", str(out)]) == 1
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["strict_json_error"].startswith("TypeError")
    assert loaded["extra"] == {"kept": 2}                            # tuple 鍵（連同內容）被略過
    assert loaded["tickers"]["USDTWD=X"]["daily"] == {"close": 31.9}


def test_寬鬆格式也寫不出_循環參照_寫最小報告_退出碼1(tmp_path, monkeypatch):
    loop: dict = {}
    loop["self"] = loop
    report = {"proxy_env_set": False, "proxy_used_by_infra": None, "rejected_tickers": [],
              "tickers": {"USDTWD=X": {"ok": True, "status": "ok"}, "^VIX": {"ok": False, "status": "request_failed"}},
              "extra": loop}
    monkeypatch.setattr(probe, "run", lambda *a, **k: report)
    monkeypatch.setattr(probe, "_summary_lines", lambda rep: [])
    out = tmp_path / "r.json"
    assert probe.main(["--out", str(out)]) == 1
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["report_written"] == "minimal"
    assert loaded["strict_json_error"].startswith("RecursionError")
    assert loaded["fallback_json_error"].startswith("ValueError")
    assert loaded["tickers_status"] == {"USDTWD=X": {"ok": True, "status": "ok"},
                                        "^VIX": {"ok": False, "status": "request_failed"}}
