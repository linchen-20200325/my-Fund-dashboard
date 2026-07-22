"""tests/test_market_series_validation.py — v19.369 8/8:F-SCHEMA-1 餘量輕量驗證。

守:
- _validate_market_series:空放行 / 合法原樣回 / 重複日 raise / 未排序 raise / inf raise(§4.2)
- 三 fetcher(stooq×2 回傳點 / cboe / defillama)已接線(source lock,防未來重構掉線)
"""
from __future__ import annotations

import pandas as pd
import pytest

from repositories.external_market_repository import _validate_market_series


def _s(dates, vals):
    return pd.Series(vals, index=pd.to_datetime(dates), dtype=float)


def test_empty_passes_through():
    s = pd.Series(dtype=float)
    assert _validate_market_series(s, "x") is s
    assert _validate_market_series(None, "x") is None


def test_valid_series_returned_as_is():
    s = _s(["2026-07-20", "2026-07-21", "2026-07-22"], [1.0, 1.1, 1.2])
    assert _validate_market_series(s, "x") is s


def test_duplicate_dates_raise():
    s = _s(["2026-07-21", "2026-07-21"], [1.0, 1.1])
    with pytest.raises(AssertionError, match="日期重複"):
        _validate_market_series(s, "x")


def test_unsorted_raises():
    s = _s(["2026-07-22", "2026-07-21"], [1.0, 1.1])
    with pytest.raises(AssertionError, match="未排序"):
        _validate_market_series(s, "x")


def test_inf_raises():
    s = _s(["2026-07-21", "2026-07-22"], [1.0, float("inf")])
    with pytest.raises(AssertionError, match="非有限值"):
        _validate_market_series(s, "x")


def test_non_datetime_index_raises():
    s = pd.Series([1.0, 2.0], index=[1, 2])
    with pytest.raises(AssertionError, match="DatetimeIndex"):
        _validate_market_series(s, "x")


# ── source lock:三 fetcher 接線不被未來重構掉線 ─────────────
def test_fetchers_wired_to_validator():
    src = open("repositories/external_market_repository.py", encoding="utf-8").read()
    assert src.count("_validate_market_series(") >= 4      # def + stooq×2 + cboe
    alt = open("repositories/macro/alternate.py", encoding="utf-8").read()
    assert "_validate_market_series" in alt                # defillama
