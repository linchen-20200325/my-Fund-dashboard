"""test_get_latest_fx_fred_fallback.py — v18.264 FRED 第二來源 fallback 單元測試

驗 user 反饋「我要即時匯率」根因：原本只有 Yahoo 單一來源，Yahoo / NAS proxy
任一掛掉就 fallback 到手動。新增 FRED 第二來源（DEXTWUS 等 DEX* series）。
"""
from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture(autouse=True)
def _clear_fx_cache():
    """每個 test 前清掉 5min TTL cache，避免上個 test 污染。"""
    from repositories.fund_repository import get_latest_fx
    if hasattr(get_latest_fx, "cache_clear"):
        get_latest_fx.cache_clear()
    yield


def test_yahoo_success_returns_yahoo_value(monkeypatch):
    """Yahoo 成功 → 直接回 Yahoo 值，不打 FRED。"""
    from repositories import fund_repository

    _fred_calls = []

    def _fake_yf_close(pair, range_="5d", interval="1d"):
        return pd.Series([31.5, 32.0, 32.10], index=pd.date_range("2026-05-29", periods=3))

    def _fake_fred(series_id, key, n=10):
        _fred_calls.append(series_id)
        return pd.DataFrame()

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _fake_yf_close)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fake_fred)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="any")
    assert v == pytest.approx(32.10)
    assert _fred_calls == []  # 沒打 FRED


def test_yahoo_fails_fred_dextwus_fallback(monkeypatch):
    """Yahoo 空 → FRED DEXTWUS 命中 → 回 FRED 值。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_dextwus(series_id, key, n=10):
        assert series_id == "DEXTWUS"
        return pd.DataFrame([{"date": pd.Timestamp("2026-05-30"), "value": 32.45}])

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_dextwus)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v == pytest.approx(32.45)


def test_yahoo_fails_no_fred_key_skips_fred(monkeypatch):
    """Yahoo 空 + 沒給 FRED key → 跳過 FRED（v18.266 後仍會試 Frankfurter）。

    本 case 把 Frankfurter 也擋掉確保 None。
    """
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    _fred_calls = []

    def _fred_should_not_call(series_id, key, n=10):
        _fred_calls.append(series_id)
        return pd.DataFrame()

    def _fetch_url_none(url, params=None, timeout=10):
        return None  # Frankfurter 也擋掉

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_should_not_call)
    monkeypatch.setattr("infra.proxy.fetch_url", _fetch_url_none)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="")
    assert v is None
    assert _fred_calls == []  # 沒 key 不打 FRED


def test_yahoo_fails_fred_jpytwd_via_usd(monkeypatch):
    """JPY/TWD：FRED 沒直接 series，要走 DEXJPUS (JPY per USD) → 反推 USD/JPY → × USDTWD。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_two_series(series_id, key, n=10):
        if series_id == "DEXJPUS":
            # 150 JPY per USD
            return pd.DataFrame([{"date": pd.Timestamp("2026-05-30"), "value": 150.0}])
        if series_id == "DEXTWUS":
            return pd.DataFrame([{"date": pd.Timestamp("2026-05-30"), "value": 32.0}])
        return pd.DataFrame()

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_two_series)

    v = fund_repository.get_latest_fx("JPYTWD=X", fred_api_key="dummy")
    # 1 JPY = (1/150) USD = 32/150 = 0.2133 TWD
    assert v == pytest.approx(32.0 / 150.0)


def test_yahoo_fails_fred_eurtwd_via_usd_inv(monkeypatch):
    """EUR/TWD：FRED DEXUSEU 是 USD per EUR → × USDTWD。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_two_series(series_id, key, n=10):
        if series_id == "DEXUSEU":
            return pd.DataFrame([{"date": pd.Timestamp("2026-05-30"), "value": 1.08}])
        if series_id == "DEXTWUS":
            return pd.DataFrame([{"date": pd.Timestamp("2026-05-30"), "value": 32.0}])
        return pd.DataFrame()

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_two_series)

    v = fund_repository.get_latest_fx("EURTWD=X", fred_api_key="dummy")
    # 1 EUR = 1.08 USD = 1.08 × 32 = 34.56 TWD
    assert v == pytest.approx(1.08 * 32.0)


def test_unknown_pair_returns_none(monkeypatch):
    """非預設對（如 NZDTWD）→ FRED 沒 map → 直接 None，不嘗試。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    _fred_calls = []

    def _fred(series_id, key, n=10):
        _fred_calls.append(series_id)
        return pd.DataFrame()

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred)

    v = fund_repository.get_latest_fx("NZDTWD=X", fred_api_key="dummy")
    assert v is None
    assert _fred_calls == []  # 未命中 map 不打 FRED


def test_pair_normalizes_missing_eq_x_suffix(monkeypatch):
    """傳 "USDTWD" 不帶 =X 應自動補。"""
    from repositories import fund_repository

    def _yf(pair, range_="5d", interval="1d"):
        assert pair == "USDTWD=X"
        return pd.Series([32.1], index=pd.date_range("2026-05-30", periods=1))

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf)
    v = fund_repository.get_latest_fx("USDTWD")
    assert v == pytest.approx(32.1)


def test_empty_input_returns_none():
    from repositories import fund_repository
    assert fund_repository.get_latest_fx("") is None
    assert fund_repository.get_latest_fx(None) is None  # type: ignore


def test_signature_back_compat_without_fred_key(monkeypatch):
    """既有 caller 不傳 fred_api_key（位置或 kwarg）也不破。"""
    from repositories import fund_repository

    def _yf(pair, range_="5d", interval="1d"):
        return pd.Series([32.5], index=pd.date_range("2026-05-30", periods=1))

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf)
    # 不傳 fred_api_key（既有調用方式）
    v = fund_repository.get_latest_fx("USDTWD=X")
    assert v == pytest.approx(32.5)


# ──────────────────────────────────────────────────────────────────────
# v18.266 — Frankfurter (ECB) 第三來源 fallback
# 涵蓋 FRED DEXTWUS 在 2021-12-31 停發後的 USD/TWD 真實場景
# ──────────────────────────────────────────────────────────────────────
class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


def test_yahoo_fails_fred_empty_frankfurter_succeeds(monkeypatch):
    """重現 user 場景：Yahoo 掛、FRED DEXTWUS 停發回空、Frankfurter 救場。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()  # 模擬 DEXTWUS 停發

    _captured_url = []

    def _fake_fetch_url(url, params=None, timeout=10):
        _captured_url.append((url, params))
        assert "frankfurter" in url
        assert params == {"from": "USD", "to": "TWD"}
        return _FakeResp({"rates": {"TWD": 32.48}, "base": "USD"})

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("infra.proxy.fetch_url", _fake_fetch_url)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v == pytest.approx(32.48)
    assert len(_captured_url) == 1  # 只打了一次 Frankfurter


def test_frankfurter_no_fred_key_still_tries(monkeypatch):
    """沒給 FRED key 也應該嘗試 Frankfurter（公開無 auth）。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fake_fetch_url(url, params=None, timeout=10):
        return _FakeResp({"rates": {"TWD": 32.55}})

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("infra.proxy.fetch_url", _fake_fetch_url)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="")
    assert v == pytest.approx(32.55)


def test_frankfurter_all_fail_returns_none(monkeypatch):
    """三層都掛 → None，UI 才能正確跳手動。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    def _fetch_none(url, params=None, timeout=10):
        return None

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("infra.proxy.fetch_url", _fetch_none)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v is None


def test_frankfurter_zero_or_negative_rate_returns_none(monkeypatch):
    """Frankfurter 回 rate=0 應被當失敗。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    def _fake_fetch_url(url, params=None, timeout=10):
        return _FakeResp({"rates": {"TWD": 0}})

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("infra.proxy.fetch_url", _fake_fetch_url)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v is None


def test_frankfurter_jpy_twd_supported(monkeypatch):
    """JPY/TWD（Frankfurter 支援的對）— FRED 也命中時 FRED 優先，FRED 空才用 Frankfurter。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()  # 全空，落 Frankfurter

    def _fake_fetch_url(url, params=None, timeout=10):
        assert params == {"from": "JPY", "to": "TWD"}
        return _FakeResp({"rates": {"TWD": 0.213}})

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("infra.proxy.fetch_url", _fake_fetch_url)

    v = fund_repository.get_latest_fx("JPYTWD=X", fred_api_key="dummy")
    assert v == pytest.approx(0.213)
