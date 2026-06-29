"""v19.253 R23 regression — _daily_cache 不 cache 失敗結果(防鎖死)。

R20 原版無條件 cache 結果,當日第一次呼叫遇上游 transient error 回 empty / failure
dict → 整天 caller 都拿到該 cached failure → user 看見「cache 鎖死」現象。
本 R23 加 cache_if predicate,失敗 / 空結果不入 cache 讓下次重試。
"""
from __future__ import annotations

import pandas as pd

from infra.cache import _daily_cache


def test_empty_dict_not_cached_retries_next_call():
    """fetcher 第 1 次回 {} → 不 cache;第 2 次回有資料 → 入 cache。"""
    _calls = [0]
    _results = [{}, {"sector_alloc": [{"name": "AAA", "pct": 50.0}]}]

    @_daily_cache
    def _f(code):
        _calls[0] += 1
        return _results[min(_calls[0] - 1, 1)]

    r1 = _f("X")
    assert r1 == {}, f"第 1 call 回 empty,實際 {r1}"
    r2 = _f("X")
    assert r2.get("sector_alloc"), f"第 2 call 應重抓拿到資料,實際 {r2}"
    assert _calls[0] == 2, f"empty 不入 cache,應呼叫 2 次,實際 {_calls[0]}"


def test_all_failed_marker_not_cached():
    """source 含 'all_failed' marker → 不 cache(R21 失敗 dict)。"""
    _calls = [0]
    _results = [
        {"source": "MoneyDJ:all_failed", "attempts": [], "fetched_at": "2026-06-29"},
        {"sector_alloc": [{"name": "BBB", "pct": 60.0}], "source": "MoneyDJ:yp013001"},
    ]

    @_daily_cache
    def _f(code):
        _calls[0] += 1
        return _results[min(_calls[0] - 1, 1)]

    r1 = _f("Y")
    assert "all_failed" in r1.get("source", ""), f"第 1 call 應拿 failure,實際 {r1}"
    r2 = _f("Y")
    assert r2.get("sector_alloc"), f"第 2 call 應重抓成功,實際 {r2}"
    assert _calls[0] == 2, f"failure 不入 cache,應呼叫 2 次,實際 {_calls[0]}"


def test_success_dict_cached_same_day():
    """有真實資料的 dict → 同日 cache hit,只呼叫 1 次。"""
    _calls = [0]

    @_daily_cache
    def _f(code):
        _calls[0] += 1
        return {"sector_alloc": [{"name": "CCC", "pct": 70.0}]}

    _f("Z")
    _f("Z")
    _f("Z")
    assert _calls[0] == 1, f"成功 cache 同日只應呼叫 1 次,實際 {_calls[0]}"


def test_none_result_not_cached():
    """None return → 不 cache(防 fetcher 回 None 鎖死)。"""
    _calls = [0]
    _results = [None, {"data": "ok"}]

    @_daily_cache
    def _f(code):
        _calls[0] += 1
        return _results[min(_calls[0] - 1, 1)]

    r1 = _f("W")
    assert r1 is None
    r2 = _f("W")
    assert r2 == {"data": "ok"}, f"第 2 call 應重抓,實際 {r2}"
    assert _calls[0] == 2


def test_empty_series_not_cached():
    """空 pandas Series → 不 cache(NAV fetcher 慣例失敗回 empty Series)。"""
    _calls = [0]
    _results = [
        pd.Series(dtype=float),
        pd.Series({pd.Timestamp("2026-01-01"): 10.5}),
    ]

    @_daily_cache
    def _f(code):
        _calls[0] += 1
        return _results[min(_calls[0] - 1, 1)]

    r1 = _f("V")
    assert len(r1) == 0
    r2 = _f("V")
    assert len(r2) == 1, f"第 2 call 應重抓拿到 NAV,實際 {r2}"
    assert _calls[0] == 2


def test_cache_info_tracks_uncached_failures():
    """cache_info 應暴露 uncached_fail 計數,讓 audit 可見鎖死現象消解。"""
    @_daily_cache
    def _f(code):
        return {}  # 永遠失敗

    _f("A")
    _f("B")
    _f("C")
    info = _f.cache_info()
    assert info["currsize"] == 0, f"全失敗 cache 應空,實際 {info}"
    assert info["uncached_fail"] == 3, \
        f"3 次 fail 應計入 uncached_fail,實際 {info}"


def test_custom_cache_if_predicate():
    """自訂 cache_if 應 override 預設過濾(extensibility)。"""
    _calls = [0]

    # 自訂規則:只 cache > 100 的結果
    @_daily_cache(cache_if=lambda r: isinstance(r, int) and r > 100)
    def _f(code):
        _calls[0] += 1
        return 50  # 不滿足 cache_if

    _f("X")
    _f("X")
    assert _calls[0] == 2, f"50 < 100 不入 cache,應呼叫 2 次,實際 {_calls[0]}"
