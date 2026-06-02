"""test_fetch_nav_history_long.py — v18.283 長期 NAV 爬蟲單元測試

驗 user 反饋「回測看不到基金的軌跡」根因 fix：fetch_nav 只給 30 筆短期 NAV，
危機回測（2018/2020/2022）涵蓋不到 → 改用 fetch_nav_history_long 多年歷史。
"""
from __future__ import annotations

import time

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _isolate_disk_cache(tmp_path, monkeypatch):
    """每個 test 用 tmp_path 取代 cache/nav_history/ 避免污染。"""
    from repositories import fund_repository
    monkeypatch.setattr(
        fund_repository, "_NAV_HISTORY_CACHE_DIR", tmp_path / "nav_history"
    )
    yield


def test_empty_code_returns_empty():
    from repositories.fund_repository import fetch_nav_history_long
    assert fetch_nav_history_long("").empty
    assert fetch_nav_history_long("   ").empty
    assert fetch_nav_history_long(None).empty  # type: ignore


def test_walk_finds_nested_nav_items():
    """_walk_for_nav_items 應在 nested JSON 中找到 NAV list。"""
    from repositories.fund_repository import _walk_for_nav_items
    data = {
        "ok": True,
        "data": {
            "fund": "ACTI94",
            "items": [
                {"date": "2024-01-01", "nav": 10.5},
                {"date": "2024-01-02", "nav": 10.6},
            ],
        },
    }
    items = _walk_for_nav_items(data)
    assert len(items) == 2


def test_walk_handles_various_key_names():
    """欄位名 nav_date / publishDate / Nav / Price 等都應認得。"""
    from repositories.fund_repository import _walk_for_nav_items
    data = {"records": [
        {"publishDate": "2024-01-01", "Price": 9.5},
        {"publishDate": "2024-01-02", "Price": 9.6},
    ]}
    items = _walk_for_nav_items(data)
    assert len(items) == 2


def test_parse_nav_json_items_skips_invalid():
    """壞 row（缺 date / nav 為負）應跳過，不該整批失敗。"""
    from repositories.fund_repository import _parse_nav_json_items
    items = [
        {"date": "2024-01-01", "nav": 10.5},
        {"date": "bad-date", "nav": 11.0},
        {"date": "2024-01-03", "nav": -5.0},  # 負值
        {"date": "2024-01-04", "nav": 12.5},
    ]
    s = _parse_nav_json_items(items)
    assert len(s) == 2  # 第 1、4 筆
    assert s.iloc[0] == pytest.approx(10.5)


def test_parse_nav_json_items_dedupes_dates():
    """同日多筆 → 後者勝（keep="last"）。"""
    from repositories.fund_repository import _parse_nav_json_items
    items = [
        {"date": "2024-01-01", "nav": 10.0},
        {"date": "2024-01-01", "nav": 10.5},  # dup
    ]
    s = _parse_nav_json_items(items)
    assert len(s) == 1
    assert s.iloc[0] == pytest.approx(10.5)


def test_cache_save_and_load_roundtrip():
    """寫入 + 讀回 cache 應一致。"""
    from repositories.fund_repository import (
        _nav_history_cache_load,
        _nav_history_cache_save,
    )
    s = pd.Series(
        [10.5, 10.6, 10.7],
        index=pd.to_datetime(["2024-01-01", "2024-01-02", "2024-01-03"]),
    )
    _nav_history_cache_save("ACTI94", s)
    loaded = _nav_history_cache_load("ACTI94")
    assert loaded is not None
    assert len(loaded) == 3
    assert loaded.iloc[-1] == pytest.approx(10.7)


def test_cache_expires_after_ttl(monkeypatch):
    """24 小時後 cache 失效回 None。"""
    from repositories import fund_repository
    monkeypatch.setattr(fund_repository, "_NAV_HISTORY_CACHE_TTL_SEC", 1)
    s = pd.Series([10.0], index=pd.to_datetime(["2024-01-01"]))
    fund_repository._nav_history_cache_save("XYZ", s)
    time.sleep(1.5)
    assert fund_repository._nav_history_cache_load("XYZ") is None


def test_cache_load_returns_none_when_missing():
    from repositories.fund_repository import _nav_history_cache_load
    assert _nav_history_cache_load("NEVERSAVED") is None


def test_fetch_long_returns_cache_hit_without_http():
    """有 cache hit (≥100 筆) 時不打 HTTP，直接返回。"""
    from repositories.fund_repository import (
        _nav_history_cache_save,
        fetch_nav_history_long,
    )
    s = pd.Series(
        list(range(1, 121)),
        index=pd.date_range("2023-01-01", periods=120, freq="D"),
        dtype=float,
    )
    _nav_history_cache_save("CACHED01", s)
    # 不 monkeypatch requests → 真的打 HTTP 會 fail
    out = fetch_nav_history_long("CACHED01")
    assert len(out) == 120


def test_fetch_long_normalizes_code_to_upper():
    """code 自動 .upper() + strip。"""
    from repositories.fund_repository import (
        _nav_history_cache_save,
        fetch_nav_history_long,
    )
    s = pd.Series(
        list(range(1, 121)),
        index=pd.date_range("2023-01-01", periods=120, freq="D"),
        dtype=float,
    )
    _nav_history_cache_save("ACTI94", s)
    out = fetch_nav_history_long("  acti94  ")
    assert len(out) == 120


# ─────────────────────────────────────────────────────────────────────
# v18.284：user 提供正確資料源後新增的測試
# ─────────────────────────────────────────────────────────────────────
def test_parse_unix_timestamp_milliseconds():
    """CnYES 等 API 可能用 13 位 ms epoch — 應正確轉日期。"""
    from repositories.fund_repository import _parse_nav_json_items
    items = [
        {"date": 1704067200000, "nav": 10.5},  # 2024-01-01 00:00:00 UTC
        {"date": 1704153600000, "nav": 10.6},  # 2024-01-02
    ]
    s = _parse_nav_json_items(items)
    assert len(s) == 2
    assert s.index[0] == pd.Timestamp("2024-01-01")


def test_parse_unix_timestamp_seconds():
    """10 位 sec epoch 也應正確處理。"""
    from repositories.fund_repository import _parse_nav_json_items
    items = [{"date": 1704067200, "nav": 10.5}]
    s = _parse_nav_json_items(items)
    assert len(s) == 1
    assert s.index[0] == pd.Timestamp("2024-01-01")


def test_parse_cnyes_native_field_name():
    """CnYES 用 `netAssetValue` 作為淨值欄位 — 應被認得。"""
    from repositories.fund_repository import _parse_nav_json_items, _walk_for_nav_items
    data = {"data": {"items": [
        {"date": "2024-01-01", "netAssetValue": 12.34},
        {"date": "2024-01-02", "netAssetValue": 12.45},
    ]}}
    items = _walk_for_nav_items(data)
    s = _parse_nav_json_items(items)
    assert len(s) == 2
    assert s.iloc[-1] == pytest.approx(12.45)


def test_parse_time_field_name():
    """有些 API 用 `time` 作為日期欄 — 應被 walk 認得。"""
    from repositories.fund_repository import _walk_for_nav_items
    data = [{"time": 1704067200000, "value": 10.5}]
    items = _walk_for_nav_items(data)
    assert len(items) == 1
