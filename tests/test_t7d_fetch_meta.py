"""test_t7d_fetch_meta — v18.239 D 模式 fetch helper 防呆測試

針對 v18.234 原本「'NoneType' object is not subscriptable」bug 做完整覆蓋：
- 任何 fetcher 異常 / 非 dict / 缺欄都不能拋例外
- series=None / 空 series / 壞 series → 安全降級 ok=False
- 全綠 path 帶 currency=TWD → fx=1.0；其他 currency → 查 FX

走 DI（測試時注入 fake fetcher）避免 sandbox 缺 bs4 卡 module load。
"""
from __future__ import annotations

import pandas as pd

from ui.helpers.d_mode import fetch_fund_meta_safe


def _fake_fetch(result):
    """產生回固定 result 的 fake fetcher。"""
    def _f(code):
        return result
    return _f


def _fake_fetch_raises(exc):
    def _f(code):
        raise exc
    return _f


# ────────────────────────────────────────────────────────────────────
# 防呆 path — 任何異常都應安全降級成 ok=False
# ────────────────────────────────────────────────────────────────────
def test_empty_code_returns_not_ok():
    out = fetch_fund_meta_safe("")
    assert out["ok"] is False
    assert "代碼為空" in out["error"]


def test_whitespace_code_returns_not_ok():
    out = fetch_fund_meta_safe("   ")
    assert out["ok"] is False


def test_none_code_returns_not_ok():
    out = fetch_fund_meta_safe(None)   # type: ignore[arg-type]
    assert out["ok"] is False


def test_fetch_raises_returns_not_ok_with_error():
    out = fetch_fund_meta_safe("ANY", _fetch=_fake_fetch_raises(RuntimeError("boom")))
    assert out["ok"] is False
    assert "boom" in out["error"]


def test_fetch_returns_non_dict_safe():
    out = fetch_fund_meta_safe("ANY", _fetch=_fake_fetch(None))
    assert out["ok"] is False
    assert "非 dict" in out["error"]


def test_fetch_returns_unexpected_type_safe():
    """fetch 回 list / str / int 都安全降級。"""
    for bad in [42, "string", [1, 2, 3]]:
        out = fetch_fund_meta_safe("X", _fetch=_fake_fetch(bad))
        assert out["ok"] is False


def test_series_none_returns_not_ok():
    """v18.234 原 bug：series=None → 之前 `_series.dropna()` 拋 NoneType；
    重建版要安全降級。"""
    out = fetch_fund_meta_safe("X", _fetch=_fake_fetch({
        "fund_name": "X", "currency": "USD",
        "series": None, "dividends": [],
    }))
    assert out["ok"] is False
    assert "NAV 序列" in out["error"]


def test_series_empty_returns_not_ok():
    out = fetch_fund_meta_safe("X", _fetch=_fake_fetch({
        "fund_name": "X", "currency": "USD",
        "series": pd.Series(dtype=float),
        "dividends": [],
    }))
    assert out["ok"] is False


def test_series_all_nan_returns_not_ok():
    """dropna 後 series 變空 → 同樣不 ok。"""
    out = fetch_fund_meta_safe("X", _fetch=_fake_fetch({
        "fund_name": "X", "currency": "USD",
        "series": pd.Series([float("nan"), float("nan")]),
        "dividends": [],
    }))
    assert out["ok"] is False


def test_series_as_list_normalizes_to_series():
    """fetch 回 list 而非 Series → 自動轉 Series。"""
    out = fetch_fund_meta_safe("X",
        _fetch=_fake_fetch({
            "fund_name": "X", "currency": "USD",
            "series": [10.0, 11.0, 12.5], "dividends": [],
        }),
        _fx_lookup=lambda _pair: 31.5)
    assert out["ok"] is True
    assert isinstance(out["series"], pd.Series)
    assert len(out["series"]) == 3
    assert out["nav"] == 12.5


# ────────────────────────────────────────────────────────────────────
# 全綠 path
# ────────────────────────────────────────────────────────────────────
def test_happy_path_usd_fetches_fx():
    s = pd.Series([10.0, 11.0, 11.5],
                   index=pd.date_range("2026-01-01", periods=3))
    out = fetch_fund_meta_safe("FIDXEQI",
        _fetch=_fake_fetch({
            "fund_name": "Fidelity World", "currency": "usd",
            "series": s,
            "dividends": [{"date": "2026-01-15", "amount": 0.5}],
        }),
        _fx_lookup=lambda _pair: 32.1)
    assert out["ok"] is True
    assert out["fund_name"] == "Fidelity World"
    assert out["currency"] == "USD"          # auto upper
    assert out["nav"] == 11.5                 # series.iloc[-1]
    assert out["fx"] == 32.1
    assert len(out["dividends"]) == 1


def test_happy_path_twd_skips_fx_lookup():
    """currency=TWD → fx 固定 1.0，不查 fx_lookup。"""
    called = []
    def _no_fx_call(pair):
        called.append(pair)
        return 99.0
    out = fetch_fund_meta_safe("0050",
        _fetch=_fake_fetch({
            "fund_name": "Cathay 台灣 50", "currency": "TWD",
            "series": pd.Series([100.0, 105.0]), "dividends": [],
        }),
        _fx_lookup=_no_fx_call)
    assert out["ok"] is True
    assert out["currency"] == "TWD"
    assert out["fx"] == 1.0
    assert called == []                       # 沒被呼叫
    assert out["nav"] == 105.0


def test_fx_lookup_fails_falls_back_to_default():
    """fx_lookup 拋例外 → fx 回 31.0 預設，仍 ok=True。"""
    def _bad_fx(pair):
        raise Exception("net")
    out = fetch_fund_meta_safe("X",
        _fetch=_fake_fetch({
            "fund_name": "X", "currency": "USD",
            "series": pd.Series([10.0]), "dividends": [],
        }),
        _fx_lookup=_bad_fx)
    assert out["ok"] is True
    assert out["fx"] == 31.0


def test_fx_lookup_returns_zero_falls_back_to_default():
    """fx_lookup 回 0 / 負 → fallback 預設。"""
    out = fetch_fund_meta_safe("X",
        _fetch=_fake_fetch({
            "fund_name": "X", "currency": "EUR",
            "series": pd.Series([10.0]), "dividends": [],
        }),
        _fx_lookup=lambda _pair: 0)
    assert out["ok"] is True
    assert out["fx"] == 31.0


def test_fund_name_fallback_to_code_when_missing():
    """fetch 回的 dict 缺 fund_name → 用 code 當顯示名。"""
    out = fetch_fund_meta_safe("MYSTERY",
        _fetch=_fake_fetch({
            "currency": "USD",
            "series": pd.Series([10.0]), "dividends": [],
        }),
        _fx_lookup=lambda _pair: 31.0)
    assert out["ok"] is True
    assert out["fund_name"] == "MYSTERY"


def test_currency_missing_defaults_to_usd():
    """缺 currency → 預設 USD（會走 FX 查詢）。"""
    out = fetch_fund_meta_safe("X",
        _fetch=_fake_fetch({
            "fund_name": "X",
            "series": pd.Series([10.0]), "dividends": [],
        }),
        _fx_lookup=lambda _pair: 31.5)
    assert out["ok"] is True
    assert out["currency"] == "USD"


def test_dividends_missing_returns_empty_list():
    out = fetch_fund_meta_safe("X",
        _fetch=_fake_fetch({
            "fund_name": "X", "currency": "TWD",
            "series": pd.Series([10.0]),
        }))
    assert out["ok"] is True
    assert out["dividends"] == []


def test_dividends_none_returns_empty_list():
    out = fetch_fund_meta_safe("X",
        _fetch=_fake_fetch({
            "fund_name": "X", "currency": "TWD",
            "series": pd.Series([10.0]), "dividends": None,
        }))
    assert out["ok"] is True
    assert out["dividends"] == []


# ════════════════════════════════════════════════════
# v18.242: in-session cache (existing) 命中秒回不再呼叫 fetcher
# ════════════════════════════════════════════════════
def test_existing_hit_short_circuits_fetch():
    """existing 命中且 series 有效 → ok=True + from_cache=True，_fetch 不被呼叫"""
    _fetch_called = []
    def _fake_fetch(_c):
        _fetch_called.append(_c)
        return {}
    existing = {
        "ACCP138": {
            "code": "ACCP138", "name": "翰亞 ABC", "currency": "TWD",
            "series": pd.Series([12.34, 12.40, 12.45]), "dividends": [],
            "fx_avg": 1.0, "policy_id": "PID-1",
        },
    }
    out = fetch_fund_meta_safe("accp138", _fetch=_fake_fetch,
                                _fx_lookup=lambda _: 1.0, _existing=existing)
    assert out["ok"] is True
    assert out["from_cache"] is True
    assert out["cache_pid"] == "PID-1"
    assert out["fund_name"] == "翰亞 ABC"
    assert out["currency"] == "TWD"
    assert out["nav"] == 12.45
    assert _fetch_called == []  # fetcher 不被呼叫


def test_existing_miss_falls_back_to_fetch():
    """existing 不命中 → 走 fetch path（既有行為不變）"""
    existing = {"OTHER": {"series": pd.Series([1.0]), "name": "X"}}
    out = fetch_fund_meta_safe(
        "NEW001",
        _fetch=lambda _c: {
            "fund_name": "New Fund", "currency": "USD",
            "series": pd.Series([10.0, 10.5]), "dividends": [],
        },
        _fx_lookup=lambda _: 31.5, _existing=existing,
    )
    assert out["ok"] is True
    assert out.get("from_cache", False) is False
    assert out["fund_name"] == "New Fund"


def test_existing_invalid_series_falls_back_to_fetch():
    """existing 命中但 series 是 None / 空 → fallback 到 fetch"""
    existing = {"X": {"name": "X", "series": None}}
    out = fetch_fund_meta_safe(
        "X",
        _fetch=lambda _c: {
            "fund_name": "X-via-fetch", "currency": "USD",
            "series": pd.Series([10.0]), "dividends": [],
        },
        _fx_lookup=lambda _: 31.0, _existing=existing,
    )
    assert out["ok"] is True
    assert out.get("from_cache", False) is False
    assert out["fund_name"] == "X-via-fetch"
