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

    def _fetch_url_none(url, params=None, timeout=10, **kw):
        return None  # Frankfurter 也擋掉

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_should_not_call)
    monkeypatch.setattr("requests.get", _fetch_url_none)

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
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def json(self):
        return self._payload


def _build_requests_get_mock(handlers: dict):
    """傳 {url_substring: payload_or_callable} 建 requests.get mock。
    payload_or_callable 可為 dict (回 200 _FakeResp(payload))、
    或 callable (params, kwargs) → _FakeResp。
    未命中任何 substring → status_code=503。
    """
    def _mock(url, params=None, proxies=None, timeout=10, verify=True, **kw):
        for sub, handler in handlers.items():
            if sub in url:
                if callable(handler):
                    return handler(params=params, **kw)
                return _FakeResp(handler) if isinstance(handler, dict) else handler
        return _FakeResp({}, status_code=503)
    return _mock


def test_yahoo_fails_fred_empty_frankfurter_succeeds(monkeypatch):
    """非 TWD pair 場景：Yahoo / FRED 失敗、er-api 不存在這幣別、Frankfurter 救場（EUR/JPY）。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    _captured_url = []

    def _fake_fetch_url(url, params=None, timeout=10, **kw):
        _captured_url.append(url)
        if "frankfurter" in url:
            assert params == {"from": "EUR", "to": "JPY"}
            return _FakeResp({"rates": {"JPY": 165.5}, "base": "EUR"})
        if "er-api" in url:
            # er-api 也有 EUR/JPY 但這 case 模擬它失敗讓 Frankfurter 接手
            return None
        return None

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("requests.get", _fake_fetch_url)

    v = fund_repository.get_latest_fx("EURJPY=X", fred_api_key="dummy")
    assert v == pytest.approx(165.5)


def test_er_api_no_fred_key_still_tries(monkeypatch):
    """沒給 FRED key 也應該嘗試 er-api（公開無 auth），TWD pair 從這裡拿到值。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fake_fetch_url(url, params=None, timeout=10, **kw):
        if "er-api" in url:
            return _FakeResp({
                "result": "success",
                "rates": {"TWD": 32.55},
            })
        return None

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("requests.get", _fake_fetch_url)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="")
    assert v == pytest.approx(32.55)


def test_frankfurter_all_fail_returns_none(monkeypatch):
    """三層都掛 → None，UI 才能正確跳手動。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    def _fetch_none(url, params=None, timeout=10, **kw):
        return None

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("requests.get", _fetch_none)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v is None


def test_frankfurter_zero_or_negative_rate_returns_none(monkeypatch):
    """Frankfurter 回 rate=0 應被當失敗。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    def _fake_fetch_url(url, params=None, timeout=10, **kw):
        return _FakeResp({"rates": {"TWD": 0}})

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("requests.get", _fake_fetch_url)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v is None


def test_frankfurter_jpy_twd_supported(monkeypatch):
    """JPY/TWD：v18.268 後 er_api 先試（也是空），Frankfurter 跳過 TWD pair，這 case 應回 None。

    註：原 v18.266 假設 Frankfurter 支援 TWD（錯）。v18.268 後 Frankfurter 直接跳過
    含 TWD 的 pair。要測 Frankfurter 命中改用 EUR/USD（非 TWD pair）。
    """
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()  # 全空

    _calls = []

    def _fake_fetch_url(url, params=None, timeout=10, **kw):
        _calls.append((url, params))
        return None  # er_api / Frankfurter 都失敗

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("requests.get", _fake_fetch_url)

    v = fund_repository.get_latest_fx("JPYTWD=X", fred_api_key="dummy")
    assert v is None
    # er_api 應被嘗試，Frankfurter 因 pair 含 TWD 被跳過
    urls = [c[0] for c in _calls]
    assert any("er-api" in u for u in urls), "er-api 應被嘗試"
    assert not any("frankfurter" in u for u in urls), "TWD pair 不該打 Frankfurter（ECB 不支援）"


# ──────────────────────────────────────────────────────────────────────
# v18.268 — open.er-api.com 第三來源 + Frankfurter 排除 TWD
# ──────────────────────────────────────────────────────────────────────
def test_er_api_succeeds_when_yahoo_fred_fail(monkeypatch):
    """重現 user 場景升級版：Yahoo + FRED + Frankfurter 都掛，er-api 救場給 USD/TWD。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    _called_urls = []

    def _fake_fetch_url(url, params=None, timeout=10, **kw):
        _called_urls.append(url)
        if "er-api" in url:
            return _FakeResp({
                "result": "success",
                "base_code": "USD",
                "rates": {"TWD": 32.18, "JPY": 150.5, "EUR": 0.92},
            })
        return None  # 其他來源都失敗

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("requests.get", _fake_fetch_url)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v == pytest.approx(32.18)
    assert any("er-api" in u for u in _called_urls)


def test_er_api_failure_result_field(monkeypatch):
    """er-api 回 result != 'success' → 應視為失敗繼續。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    def _fake_fetch_url(url, params=None, timeout=10, **kw):
        if "er-api" in url:
            return _FakeResp({"result": "error", "error-type": "unsupported-code"})
        return None

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("requests.get", _fake_fetch_url)

    v = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert v is None


def test_frankfurter_skipped_for_twd_pair(monkeypatch):
    """ECB 沒 TWD reference rate → 任何含 TWD 的 pair 不該打 Frankfurter（節省 1 次 HTTP）。"""
    from repositories import fund_repository

    def _yf_empty(pair, range_="5d", interval="1d"):
        return pd.Series(dtype=float)

    def _fred_empty(series_id, key, n=10):
        return pd.DataFrame()

    _called = []

    def _fake_fetch_url(url, params=None, timeout=10, **kw):
        _called.append(url)
        return None

    monkeypatch.setattr("repositories.macro_repository.fetch_yf_close", _yf_empty)
    monkeypatch.setattr("repositories.macro_repository.fetch_fred", _fred_empty)
    monkeypatch.setattr("requests.get", _fake_fetch_url)

    _ = fund_repository.get_latest_fx("USDTWD=X", fred_api_key="dummy")
    assert any("er-api" in u for u in _called)
    assert not any("frankfurter" in u for u in _called)


def test_diagnose_fx_sources_returns_4_keys(monkeypatch):
    """diagnose_fx_sources 必須回 4 個 key 給 Tab5 渲染。"""
    from repositories.fund_repository import diagnose_fx_sources

    monkeypatch.setattr(
        "repositories.macro_repository.fetch_yf_close",
        lambda pair, range_="5d", interval="1d": pd.Series(dtype=float),
    )
    monkeypatch.setattr(
        "repositories.macro_repository.fetch_fred",
        lambda series_id, key, n=10: pd.DataFrame(),
    )
    monkeypatch.setattr("requests.get", lambda url, params=None, timeout=10, **kw: None)

    out = diagnose_fx_sources("USDTWD=X", fred_api_key="dummy")
    assert set(out.keys()) == {"yahoo", "fred", "er_api", "frankfurter"}
    for src in out.values():
        assert "ok" in src and "rate" in src and "error" in src and "note" in src


def test_diagnose_fx_yahoo_success_marked(monkeypatch):
    """diagnose 對成功的來源應標 ok=True + 給 rate 值。"""
    from repositories.fund_repository import diagnose_fx_sources

    monkeypatch.setattr(
        "repositories.macro_repository.fetch_yf_close",
        lambda pair, range_="5d", interval="1d":
            pd.Series([32.1], index=pd.date_range("2026-05-30", periods=1)),
    )
    monkeypatch.setattr(
        "repositories.macro_repository.fetch_fred",
        lambda series_id, key, n=10: pd.DataFrame(),
    )
    monkeypatch.setattr("requests.get", lambda url, params=None, timeout=10, **kw: None)

    out = diagnose_fx_sources("USDTWD=X", fred_api_key="dummy")
    assert out["yahoo"]["ok"] is True
    assert out["yahoo"]["rate"] == pytest.approx(32.1)


def test_diagnose_fx_frankfurter_skipped_for_twd():
    """TWD pair 的診斷必須把 Frankfurter 標為「不支援 TWD」而非「未嘗試」。"""
    from repositories.fund_repository import diagnose_fx_sources

    out = diagnose_fx_sources("USDTWD=X", fred_api_key="")
    assert out["frankfurter"]["ok"] is False
    assert "TWD" in (out["frankfurter"]["error"] or "")
