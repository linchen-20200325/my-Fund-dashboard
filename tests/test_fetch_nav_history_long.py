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
    """每個 test 用 tmp_path 取代 cache/nav_history/ 避免污染。

    v19.235 R1:shim repositories/fund_repository.py 已刪,改 patch 真正的
    sub-module repositories.fund.nav_metrics(P2-7 shim 不穿透模式同源)。
    """
    from repositories.fund import nav_metrics as _nav
    monkeypatch.setattr(_nav, "_NAV_HISTORY_CACHE_DIR", tmp_path / "nav_history")
    yield


def test_empty_code_returns_empty():
    from repositories.fund import fetch_nav_history_long
    assert fetch_nav_history_long("").empty
    assert fetch_nav_history_long("   ").empty
    assert fetch_nav_history_long(None).empty  # type: ignore


def test_walk_finds_nested_nav_items():
    """_walk_for_nav_items 應在 nested JSON 中找到 NAV list。"""
    from repositories.fund import _walk_for_nav_items
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
    from repositories.fund import _walk_for_nav_items
    data = {"records": [
        {"publishDate": "2024-01-01", "Price": 9.5},
        {"publishDate": "2024-01-02", "Price": 9.6},
    ]}
    items = _walk_for_nav_items(data)
    assert len(items) == 2


def test_parse_nav_json_items_skips_invalid():
    """壞 row（缺 date / nav 為負）應跳過，不該整批失敗。"""
    from repositories.fund import _parse_nav_json_items
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
    from repositories.fund import _parse_nav_json_items
    items = [
        {"date": "2024-01-01", "nav": 10.0},
        {"date": "2024-01-01", "nav": 10.5},  # dup
    ]
    s = _parse_nav_json_items(items)
    assert len(s) == 1
    assert s.iloc[0] == pytest.approx(10.5)


def test_cache_save_and_load_roundtrip():
    """寫入 + 讀回 cache 應一致。"""
    from repositories.fund import (
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
    """24 小時後 cache 失效回 None。

    v19.234 P2 fix:原寫法 patch shim `fund_repository` 不穿透 sub-module(P2-7
    模式),且 `time.sleep(1.5)` 依賴實際時鐘易產生 timing-flaky。改 patch
    sub-module `fund/nav_metrics` 真正 TTL const + mock `time.time` 跳到 TTL 之後。
    """
    from repositories.fund import nav_metrics
    # patch sub-module 真正 const(避免 P2-7 shim 不穿透)
    monkeypatch.setattr(nav_metrics, "_NAV_HISTORY_CACHE_TTL_SEC", 1)
    s = pd.Series([10.0], index=pd.to_datetime(["2024-01-01"]))
    nav_metrics._nav_history_cache_save("XYZ", s)
    # mock time.time 跳到 TTL 之後(避免實際 sleep,消除 timing 敏感)
    import time as _time_mod
    _real_time = _time_mod.time()
    monkeypatch.setattr(_time_mod, "time", lambda: _real_time + 10)
    assert nav_metrics._nav_history_cache_load("XYZ") is None


def test_cache_load_returns_none_when_missing():
    from repositories.fund import _nav_history_cache_load
    assert _nav_history_cache_load("NEVERSAVED") is None


def test_fetch_long_returns_cache_hit_without_http():
    """有 cache hit (≥100 筆) 時不打 HTTP，直接返回。"""
    from repositories.fund import (
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
    from repositories.fund import (
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
    from repositories.fund import _parse_nav_json_items
    items = [
        {"date": 1704067200000, "nav": 10.5},  # 2024-01-01 00:00:00 UTC
        {"date": 1704153600000, "nav": 10.6},  # 2024-01-02
    ]
    s = _parse_nav_json_items(items)
    assert len(s) == 2
    assert s.index[0] == pd.Timestamp("2024-01-01")


def test_parse_unix_timestamp_seconds():
    """10 位 sec epoch 也應正確處理。"""
    from repositories.fund import _parse_nav_json_items
    items = [{"date": 1704067200, "nav": 10.5}]
    s = _parse_nav_json_items(items)
    assert len(s) == 1
    assert s.index[0] == pd.Timestamp("2024-01-01")


def test_parse_cnyes_native_field_name():
    """CnYES 用 `netAssetValue` 作為淨值欄位 — 應被認得。"""
    from repositories.fund import _parse_nav_json_items, _walk_for_nav_items
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
    from repositories.fund import _walk_for_nav_items
    data = [{"time": 1704067200000, "value": 10.5}]
    items = _walk_for_nav_items(data)
    assert len(items) == 1
