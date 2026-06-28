"""test_update_macro_history.py — Fund-dashboard 全球總經 FRED 歷史 cache.

Smoke + edge-case tests (no network)：
- _merge_dedupe 行為（單欄 + 複合欄 key）
- Parquet 讀寫 roundtrip 保型別
- _last_date 邊界
- update_one 已是最新時跳過 fetch
- FRED 缺 API key 時 graceful 跳過
- FRED series 抓取 (mocked) — 全表長格式 (date, series_id, value)
- _yf_fetch_close 解析 (mocked) Yahoo Chart JSON
- 任一 FRED series 失敗其他 series 不中止
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest

# scripts/ 不在 default sys.path —— 顯式加入 repo root 才能 `import scripts.update_macro_history`
sys.path.insert(0, str(Path(__file__).parents[1]))


# ════════════════════════════════════════════════════════════════
# _merge_dedupe
# ════════════════════════════════════════════════════════════════
def test_merge_dedupe_single_key():
    """單一 date key 同日衝突 → 保留 new."""
    from scripts.update_macro_history import _merge_dedupe
    old = pd.DataFrame({
        "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
        "close": [4500.0, 4550.0],
    })
    new = pd.DataFrame({
        "date": [dt.date(2026, 1, 2), dt.date(2026, 1, 3)],
        "close": [4555.0, 4600.0],
    })
    out = _merge_dedupe(old, new, key=["date"])
    assert len(out) == 3
    val = float(out.loc[out["date"] == dt.date(2026, 1, 2), "close"].iloc[0])
    assert val == 4555.0


def test_merge_dedupe_compound_key():
    """複合 (date, series_id) key — fred_indicators 用."""
    from scripts.update_macro_history import _merge_dedupe
    old = pd.DataFrame({
        "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 1)],
        "series_id": ["DGS10", "DGS2"],
        "value": [4.3, 4.6],
    })
    new = pd.DataFrame({
        "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
        "series_id": ["DGS10", "DGS10"],  # 同 (1/1, DGS10) 衝突 → 取 new
        "value": [4.35, 4.40],
    })
    out = _merge_dedupe(old, new, key=["date", "series_id"])
    assert len(out) == 3
    dgs10_11 = out[(out["date"] == dt.date(2026, 1, 1))
                   & (out["series_id"] == "DGS10")]
    assert float(dgs10_11["value"].iloc[0]) == 4.35
    # DGS2 1/1 應保留
    dgs2_11 = out[(out["date"] == dt.date(2026, 1, 1))
                  & (out["series_id"] == "DGS2")]
    assert len(dgs2_11) == 1


def test_merge_dedupe_old_empty():
    """空 old → 直接回 new."""
    from scripts.update_macro_history import _merge_dedupe
    new = pd.DataFrame({"date": [dt.date(2026, 1, 1)], "close": [4500.0]})
    out = _merge_dedupe(None, new, key=["date"])
    assert len(out) == 1
    out2 = _merge_dedupe(pd.DataFrame(), new, key=["date"])
    assert len(out2) == 1


# ════════════════════════════════════════════════════════════════
# Parquet I/O
# ════════════════════════════════════════════════════════════════
def test_parquet_roundtrip_preserves_long_format():
    """Parquet 寫入 + 讀回必須維持 date / series_id / value 三欄型別."""
    import scripts.update_macro_history as umh
    with tempfile.TemporaryDirectory() as tmpdir:
        original = umh.CACHE_DIR
        try:
            umh.CACHE_DIR = Path(tmpdir)
            df = pd.DataFrame({
                "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 2)],
                "series_id": ["DGS10", "DGS10"],
                "value": [4.3, 4.35],
            })
            umh._write_parquet("test_roundtrip", df)
            out = umh._load_existing("test_roundtrip")
            assert out is not None
            assert len(out) == 2
            assert pd.api.types.is_numeric_dtype(out["value"])
            assert "series_id" in out.columns
        finally:
            umh.CACHE_DIR = original


def test_load_existing_missing_file():
    """檔案不存在 → 回 None（不 raise）."""
    import scripts.update_macro_history as umh
    with tempfile.TemporaryDirectory() as tmpdir:
        umh.CACHE_DIR = Path(tmpdir)
        assert umh._load_existing("noexist") is None


# ════════════════════════════════════════════════════════════════
# _last_date
# ════════════════════════════════════════════════════════════════
def test_last_date_handles_empty_and_missing():
    from scripts.update_macro_history import _last_date
    assert _last_date(None) is None
    assert _last_date(pd.DataFrame()) is None
    assert _last_date(pd.DataFrame({"other": [1, 2]})) is None


def test_last_date_returns_max_across_series():
    """fred_indicators 長格式：_last_date 取所有 series 中最新一筆。"""
    from scripts.update_macro_history import _last_date
    df = pd.DataFrame({
        "date": [dt.date(2026, 1, 1), dt.date(2026, 1, 5),
                 dt.date(2026, 1, 3)],
        "series_id": ["DGS10", "DGS2", "DGS10"],
        "value": [4.3, 4.6, 4.35],
    })
    assert _last_date(df) == dt.date(2026, 1, 5)


# ════════════════════════════════════════════════════════════════
# DATASETS / FETCHERS 註冊驗證
# ════════════════════════════════════════════════════════════════
def test_datasets_registered():
    """4 dataset 都註冊在 DATASETS 與 FETCHERS。"""
    import scripts.update_macro_history as umh
    assert set(umh.DATASETS) == {
        "fred_indicators", "vix_history", "spx_history", "twii_history"}
    assert "fred_indicators" in umh.FETCHERS
    assert "vix_history" in umh.FETCHERS
    assert "spx_history" in umh.FETCHERS
    assert "twii_history" in umh.FETCHERS
    # fred_indicators 需要 FRED_API_KEY，VIX/SPX/TWII 不需要
    assert umh.FETCHERS["fred_indicators"][1] is True
    assert umh.FETCHERS["vix_history"][1] is False
    assert umh.FETCHERS["spx_history"][1] is False
    assert umh.FETCHERS["twii_history"][1] is False
    # dedupe_keys
    assert umh.FETCHERS["fred_indicators"][2] == ["date", "series_id"]
    assert umh.FETCHERS["vix_history"][2] == ["date"]
    assert umh.FETCHERS["twii_history"][2] == ["date"]


def test_fred_series_ids_match_score_rules():
    """FRED_SERIES_IDS 應覆蓋 services.macro_validation.SCORE_RULES 8 個 FRED key."""
    import scripts.update_macro_history as umh
    # 至少包含這 8 個（PMI 暫不抓 → 不在這裡）
    expected = {"DGS10", "DGS2", "DGS3MO", "BAMLH0A0HYM2",
                "M2SL", "WALCL", "CPIAUCSL", "UNRATE"}
    assert set(umh.FRED_SERIES_IDS) >= expected


# ════════════════════════════════════════════════════════════════
# update_one — 已是最新 / 缺 key
# ════════════════════════════════════════════════════════════════
def test_update_one_skips_when_up_to_date(monkeypatch):
    """existing 最後日期 ≥ today → 跳過抓取（不打 API）。"""
    import scripts.update_macro_history as umh
    with tempfile.TemporaryDirectory() as tmpdir:
        umh.CACHE_DIR = Path(tmpdir)
        today = dt.date.today()
        df_old = pd.DataFrame({"date": [today], "close": [4500.0]})
        umh._write_parquet("vix_history", df_old)

        call_count = {"n": 0}
        def _fake_fetch(start, end, api_key=""):
            call_count["n"] += 1
            return pd.DataFrame()
        monkeypatch.setitem(
            umh.FETCHERS, "vix_history",
            (_fake_fetch, False, ["date"]))
        meta = umh.update_one("vix_history", today, bootstrap=False, years=15,
                              api_key="")
        assert call_count["n"] == 0
        assert meta["last_updated"] == today.isoformat()


def test_update_one_missing_fred_key():
    """fred_indicators 缺 FRED_API_KEY → graceful 跳過、不 raise."""
    import scripts.update_macro_history as umh
    with tempfile.TemporaryDirectory() as tmpdir:
        umh.CACHE_DIR = Path(tmpdir)
        today = dt.date.today()
        meta = umh.update_one("fred_indicators", today,
                              bootstrap=False, years=15, api_key="")
        assert meta["last_error"] is not None
        assert "FRED_API_KEY" in meta["last_error"]


def test_update_one_fetch_returns_empty(monkeypatch):
    """fetcher 回空 + 有 existing → 保留 existing、報 error 但不刪檔."""
    import scripts.update_macro_history as umh
    with tempfile.TemporaryDirectory() as tmpdir:
        umh.CACHE_DIR = Path(tmpdir)
        today = dt.date.today()
        df_old = pd.DataFrame({"date": [today - dt.timedelta(days=5)],
                               "close": [4500.0]})
        umh._write_parquet("vix_history", df_old)

        monkeypatch.setitem(
            umh.FETCHERS, "vix_history",
            (lambda s, e, k="": pd.DataFrame(), False, ["date"]))
        meta = umh.update_one("vix_history", today, bootstrap=False, years=15,
                              api_key="")
        assert meta["last_error"] == "抓取結果為空"
        # existing 仍在
        assert umh._load_existing("vix_history") is not None


# ════════════════════════════════════════════════════════════════
# _fred_get_single + fetch_fred_indicators (mocked HTTP)
# ════════════════════════════════════════════════════════════════
def _make_fake_response(json_data: dict, status_code: int = 200) -> MagicMock:
    m = MagicMock()
    m.status_code = status_code
    m.json.return_value = json_data
    m.text = json.dumps(json_data)
    return m


def test_fred_get_single_parses_observations(monkeypatch):
    import scripts.update_macro_history as umh
    fake = _make_fake_response({
        "observations": [
            {"date": "2024-01-01", "value": "4.3"},
            {"date": "2024-01-02", "value": "."},   # 應被剔除
            {"date": "2024-01-03", "value": "4.35"},
        ]
    })
    monkeypatch.setattr(umh.requests, "get", lambda *a, **kw: fake)
    df = umh._fred_get_single("DGS10", dt.date(2024, 1, 1),
                              dt.date(2024, 1, 5), "fakekey")
    assert len(df) == 2
    assert list(df.columns) == ["date", "value"]
    assert float(df["value"].iloc[0]) == 4.3
    assert float(df["value"].iloc[1]) == 4.35


def test_fred_get_single_handles_http_error(monkeypatch):
    import scripts.update_macro_history as umh
    fake = _make_fake_response({}, status_code=500)
    monkeypatch.setattr(umh.requests, "get", lambda *a, **kw: fake)
    df = umh._fred_get_single("DGS10", dt.date(2024, 1, 1),
                              dt.date(2024, 1, 5), "fakekey")
    assert df.empty


def test_fred_get_single_no_api_key():
    """無 api_key → 直接回空 DataFrame（不打 API）."""
    import scripts.update_macro_history as umh
    df = umh._fred_get_single("DGS10", dt.date(2024, 1, 1),
                              dt.date(2024, 1, 5), "")
    assert df.empty


def test_fred_get_single_429_retry_then_success(monkeypatch):
    """連 2 次 429 後第 3 次回 200 → 重試成功取到資料；time.sleep 應被呼叫 2 次。"""
    import scripts.update_macro_history as umh
    fake_429 = _make_fake_response({"error_code": 429}, status_code=429)
    fake_200 = _make_fake_response({
        "observations": [{"date": "2024-01-01", "value": "4.3"}],
    })
    seq = iter([fake_429, fake_429, fake_200])
    monkeypatch.setattr(umh.requests, "get", lambda *a, **kw: next(seq))
    sleeps: list[float] = []
    monkeypatch.setattr(umh.time, "sleep", lambda s: sleeps.append(s))
    df = umh._fred_get_single("DGS10", dt.date(2024, 1, 1),
                              dt.date(2024, 1, 5), "fakekey")
    assert len(df) == 1
    assert sleeps == [2.0, 4.0]  # exp backoff 前 2 次


def test_fred_get_single_429_exhausts_retries(monkeypatch):
    """4 次 (1 初試 + 3 retry) 全 429 → 回空 DataFrame 不 raise；sleep 3 次。"""
    import scripts.update_macro_history as umh
    fake_429 = _make_fake_response({"error_code": 429}, status_code=429)
    monkeypatch.setattr(umh.requests, "get", lambda *a, **kw: fake_429)
    sleeps: list[float] = []
    monkeypatch.setattr(umh.time, "sleep", lambda s: sleeps.append(s))
    df = umh._fred_get_single("DGS10", dt.date(2024, 1, 1),
                              dt.date(2024, 1, 5), "fakekey")
    assert df.empty
    assert sleeps == list(umh._FRED_429_BACKOFF_SEC)  # 2 + 4 + 8


def test_fetch_fred_indicators_inserts_inter_call_sleep(monkeypatch):
    """fetch_fred_indicators 在 series 間插 _FRED_INTER_CALL_SLEEP_SEC 秒 sleep。"""
    import scripts.update_macro_history as umh
    monkeypatch.setattr(
        umh, "_fred_get_single",
        lambda sid, s, e, k: pd.DataFrame({"date": [dt.date(2024, 1, 1)], "value": [1.0]}),
    )
    sleeps: list[float] = []
    monkeypatch.setattr(umh.time, "sleep", lambda s: sleeps.append(s))
    umh.fetch_fred_indicators(dt.date(2024, 1, 1), dt.date(2024, 1, 5), "fakekey")
    # N series 之間應插 N-1 次 sleep
    assert sleeps == [umh._FRED_INTER_CALL_SLEEP_SEC] * (len(umh.FRED_SERIES_IDS) - 1)


def test_fetch_fred_indicators_long_format(monkeypatch):
    """fetch_fred_indicators 8 series 各回 1 列 → 8 列長格式 (date, series_id, value)."""
    import scripts.update_macro_history as umh
    call_log = {"n": 0}

    def _fake(series_id, start, end, api_key):
        call_log["n"] += 1
        return pd.DataFrame({
            "date": [dt.date(2024, 1, 1)],
            "value": [4.0 + call_log["n"] * 0.1],
        })

    monkeypatch.setattr(umh, "_fred_get_single", _fake)
    monkeypatch.setattr(umh.time, "sleep", lambda s: None)
    df = umh.fetch_fred_indicators(dt.date(2024, 1, 1), dt.date(2024, 1, 5),
                                    "fakekey")
    assert list(df.columns) == ["date", "series_id", "value"]
    assert len(df) == len(umh.FRED_SERIES_IDS)
    # 每個 series_id 出現一次
    assert set(df["series_id"]) == set(umh.FRED_SERIES_IDS)


def test_fetch_fred_one_series_fails_others_continue(monkeypatch):
    """任一 series 失敗其他 series 仍應抓進來."""
    import scripts.update_macro_history as umh
    def _fake(series_id, start, end, api_key):
        if series_id == "DGS10":
            return pd.DataFrame()   # 模擬失敗
        return pd.DataFrame({
            "date": [dt.date(2024, 1, 1)],
            "value": [4.0],
        })

    monkeypatch.setattr(umh, "_fred_get_single", _fake)
    monkeypatch.setattr(umh.time, "sleep", lambda s: None)
    df = umh.fetch_fred_indicators(dt.date(2024, 1, 1), dt.date(2024, 1, 5),
                                    "fakekey")
    # 應有 7 列（缺 DGS10）
    assert len(df) == len(umh.FRED_SERIES_IDS) - 1
    assert "DGS10" not in set(df["series_id"])


# ════════════════════════════════════════════════════════════════
# _yf_fetch_close (mocked Yahoo Chart)
# ════════════════════════════════════════════════════════════════
def test_yf_fetch_close_parses(monkeypatch):
    import scripts.update_macro_history as umh
    # Yahoo Chart 格式
    fake_payload = {
        "chart": {
            "result": [{
                "timestamp": [1704067200, 1704153600],   # 2024-01-01, 2024-01-02 UTC
                "indicators": {
                    "quote": [{"close": [4700.5, 4720.3]}]
                }
            }]
        }
    }
    fake_response = _make_fake_response(fake_payload)
    monkeypatch.setattr(umh, "_fetch_url_via_proxy",
                        lambda *a, **kw: fake_response)
    df = umh._yf_fetch_close("%5EVIX", dt.date(2024, 1, 1), dt.date(2024, 1, 5))
    assert len(df) == 2
    assert list(df.columns) == ["date", "close"]
    assert float(df["close"].iloc[0]) == 4700.5


def test_yf_fetch_close_handles_none_response(monkeypatch):
    """proxy 抓不到 (None) → 回空 DataFrame、不 raise."""
    import scripts.update_macro_history as umh
    monkeypatch.setattr(umh, "_fetch_url_via_proxy", lambda *a, **kw: None)
    df = umh._yf_fetch_close("%5EVIX", dt.date(2024, 1, 1), dt.date(2024, 1, 5))
    assert df.empty


def test_fetch_vix_and_spx_signatures():
    """fetch_vix_history / fetch_spx_history / fetch_twii_history 須接受 api_key 參數（一致性，不使用）."""
    import scripts.update_macro_history as umh
    # 簽名校驗：不會因有 api_key 參數而 raise
    import inspect
    sig_vix = inspect.signature(umh.fetch_vix_history)
    sig_spx = inspect.signature(umh.fetch_spx_history)
    sig_twii = inspect.signature(umh.fetch_twii_history)
    assert "api_key" in sig_vix.parameters
    assert "api_key" in sig_spx.parameters
    assert "api_key" in sig_twii.parameters


def test_fetch_twii_history_calls_yf_chart(monkeypatch):
    """fetch_twii_history 應委派給 _yf_fetch_close 帶 %5ETWII ticker。"""
    import scripts.update_macro_history as umh
    called = {"ticker": None}

    def _fake_yf(ticker, start, end):
        called["ticker"] = ticker
        return pd.DataFrame({"date": [dt.date(2024, 1, 1)], "close": [17500.0]})

    monkeypatch.setattr(umh, "_yf_fetch_close", _fake_yf)
    df = umh.fetch_twii_history(dt.date(2024, 1, 1), dt.date(2024, 1, 5))
    assert called["ticker"] == "%5ETWII"
    assert len(df) == 1
    assert float(df["close"].iloc[0]) == 17500.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
