# -*- coding: utf-8 -*-
"""repositories/macro/fred_vintage.py（49 §6.3 N-3、§6.2 T1）的單元測試（fast lane；不打網路）。

`fetch_url` 一律以替身注入。測的是：
1. 打的是同一個 FRED 端點、同一把金鑰，多帶的參數就是取「首次公布日」要的那三個；
2. 回傳保留每一個版次（含缺值記號那一版），不丟列、不改值；
3. 失敗旁路與 `fetch_fred` 同一套語意（同鍵名、同快取判準）；
4. `fetch_fred` 本體一個字都沒有被改（49 N-3「不動 `fetch_fred` 本體」）—— 以它的舊參數集釘住。
"""
from __future__ import annotations

import pandas as pd
import pytest

from repositories.macro import fred as fred_mod
from repositories.macro import fred_vintage as fv


class _Resp:
    def __init__(self, payload=None, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        return self._payload


def _set_fail_kind(kind: str) -> None:
    from infra import proxy as _px
    _px._TLS_FAIL.kind = kind


@pytest.fixture(autouse=True)
def _clean():
    fv.fetch_fred_vintages.cache_clear()
    _set_fail_kind("")
    yield
    fv.fetch_fred_vintages.cache_clear()
    _set_fail_kind("")


# FRED output_type=1 回應的形狀：同一個 date，值不同的每段版次各一列。
_PAYLOAD = {"observations": [
    {"realtime_start": "2026-08-01", "realtime_end": "2026-08-31", "date": "2026-07-01", "value": "4.33"},
    {"realtime_start": "2026-09-01", "realtime_end": "9999-12-31", "date": "2026-07-01", "value": "4.32"},
    {"realtime_start": "2026-09-02", "realtime_end": "9999-12-31", "date": "2026-08-01", "value": "."},
]}


def test_同一端點同一金鑰_多帶的就是取首次公布日的三個參數(monkeypatch):
    seen = {}

    def fake(url, params=None, **kw):
        seen["url"], seen["params"] = url, dict(params)
        return _Resp(_PAYLOAD)

    monkeypatch.setattr(fv, "fetch_url", fake)
    fv.fetch_fred_vintages("FEDFUNDS", "KEY", "2024-10-13")
    assert seen["url"] == fred_mod.FRED_BASE
    p = seen["params"]
    assert p["series_id"] == "FEDFUNDS" and p["api_key"] == "KEY" and p["file_type"] == "json"
    assert p["observation_start"] == "2024-10-13"
    assert p["realtime_start"] == "2024-10-13"           # 下界＝觀測起點（見模組說明）
    assert p["realtime_end"] == "9999-12-31"
    assert p["output_type"] == "1"
    assert "limit" not in p                              # 不截斷：截掉會切斷某期間的版次序列


def test_每個版次各一列_值與公布日照原樣_缺值記號成NaN不丟列(monkeypatch):
    monkeypatch.setattr(fv, "fetch_url", lambda *a, **k: _Resp(_PAYLOAD))
    df, err = fv.fetch_fred_vintages_with_error("FEDFUNDS", "KEY", "2024-10-13")
    assert err is None
    assert list(df.columns) == ["date", "value", "realtime_start", "realtime_end"]
    assert len(df) == 3
    assert [d.date().isoformat() for d in df["date"]] == ["2026-07-01", "2026-07-01", "2026-08-01"]
    assert [d.date().isoformat() for d in df["realtime_start"]] == ["2026-08-01", "2026-09-01", "2026-09-02"]
    assert df["value"].iloc[0] == 4.33 and df["value"].iloc[1] == 4.32
    assert pd.isna(df["value"].iloc[2])
    assert list(df["realtime_end"]) == ["2026-08-31", "9999-12-31", "9999-12-31"]
    assert df.attrs["source"] == "FRED:FEDFUNDS:vintages"
    assert df.attrs["realtime_floor"] == "2024-10-13"
    ts = pd.Timestamp(df.attrs["fetched_at"])
    assert ts.tzinfo is not None and ts.utcoffset().total_seconds() == 0


def test_缺金鑰_不打網路_原文交出(monkeypatch):
    monkeypatch.setattr(fv, "fetch_url", lambda *a, **k: pytest.fail("缺金鑰不得打網路"))
    df, err = fv.fetch_fred_vintages_with_error("FEDFUNDS", "", "2024-10-13")
    assert df.empty and "api_key 為空" in err


def test_連線失敗_可重試者不入快取_原文帶失敗分類(monkeypatch):
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            _set_fail_kind("server_error")
            return None
        return _Resp(_PAYLOAD)

    monkeypatch.setattr(fv, "fetch_url", fake)
    df1, err1 = fv.fetch_fred_vintages_with_error("FEDFUNDS", "KEY", "2024-10-13")
    assert df1.empty and "fetch_url returned None" in err1 and "server_error" in err1
    df2, err2 = fv.fetch_fred_vintages_with_error("FEDFUNDS", "KEY", "2024-10-13")
    assert err2 is None and len(df2) == 3 and calls["n"] == 2


def test_404不標記_照舊快取_與fetch_fred同一判準(monkeypatch):
    calls = {"n": 0}

    def fake(*a, **k):
        calls["n"] += 1
        _set_fail_kind("not_found")
        return None

    monkeypatch.setattr(fv, "fetch_url", fake)
    _df, err = fv.fetch_fred_vintages_with_error("NOPE", "KEY", "2024-10-13")
    assert "404 或 407" in err
    fv.fetch_fred_vintages_with_error("NOPE", "KEY", "2024-10-13")
    assert calls["n"] == 1


@pytest.mark.parametrize("payload, needle", [
    ({"observations": []}, "observations 為空"),
    (ValueError("bad json"), "JSON 解析失敗"),
    ({"observations": [{"date": "2026-07-01", "value": "1"}]}, "缺欄位 realtime_start"),
])
def test_回200但不能用_原文交出_不丟例外(monkeypatch, payload, needle):
    monkeypatch.setattr(fv, "fetch_url", lambda *a, **k: _Resp(payload))
    df, err = fv.fetch_fred_vintages_with_error("FEDFUNDS", "KEY", "2024-10-13")
    assert df.empty and needle in err


def test_旁路鍵名沿用fred_py_不另定義第四份():
    assert fv._FETCH_ERROR_ATTR is fred_mod._FETCH_ERROR_ATTR


def test_fetch_fred本體未動_仍不帶任何real_time參數(monkeypatch):
    """49 N-3「不動 `fetch_fred` 本體」：它的查詢參數照舊只有五個，現有呼叫端行為不變。"""
    seen = {}

    def fake(url, params=None, **kw):
        seen["params"] = dict(params)
        return _Resp({"observations": [
            {"realtime_start": "2026-10-13", "realtime_end": "2026-10-13", "date": "2026-07-01", "value": "4.33"}]})

    fred_mod.fetch_fred.cache_clear()
    monkeypatch.setattr(fred_mod, "fetch_url", fake)
    try:
        fred_mod.fetch_fred("FEDFUNDS", "KEY", 5)
    finally:
        fred_mod.fetch_fred.cache_clear()
    assert set(seen["params"]) == {"series_id", "api_key", "file_type", "sort_order", "limit"}
