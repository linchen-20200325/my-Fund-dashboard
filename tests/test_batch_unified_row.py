"""tests/test_batch_unified_row.py — 批次「組合健診 40 欄大表」單檔列(v19.413)。

驗 build_batch_unified_row:成功檔產出完整欄(①②③+σ/風險/MK)、JSON-safe(可存
checkpoint)、失敗檔回狀態!=成功且欄位對齊、空碼→無效代號。不打網路(mock 抓取 + fx)。
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ui.helpers.fund_grp_health.unified import (
    BATCH_UNIFIED_COLUMNS,
    build_batch_unified_row,
)


def _fd():
    idx = pd.date_range("2022-01-01", periods=900, freq="D")
    return {
        "series": pd.Series([10 + (i % 50) * 0.02 for i in range(900)], index=idx),
        "dividends": [{"date": "2026-06-01", "amount": 0.05}],
        "currency": "USD", "fund_name": "測試基金X", "data_source": "moneydj",
        "mgmt_fee": "1.5%",
        "metrics": {"nav": 11.0, "sharpe": 1.1, "std_1y": 12.0, "max_drawdown": -15.0,
                    "div_freq_n": 12, "ret_3y_ann": 6.5, "annual_div_rate": 5.0,
                    "buy1": 10, "buy3": 9, "sell1": 12, "sell3": 13},
        "perf": {"1Y": 8.0, "3Y": 20.0},
    }


@pytest.fixture
def _mock(monkeypatch):
    monkeypatch.setattr("services.moneydj_fetcher.auto_fetch_moneydj",
                        lambda c, *a, **k: _fd(), raising=True)
    monkeypatch.setattr("services.fund_service.get_latest_fx",
                        lambda *a, **k: 32.0, raising=True)
    # 種入基準快取 → capture_by_code 不打網路(否則逾時拖慢)
    import ui.helpers.fund_grp_health.capture as _cap
    _d = pd.date_range("2020-01-31", periods=60, freq="ME")
    _b = pd.Series(100 * np.cumprod([1.0] + [1.005] * 59), index=_d)
    monkeypatch.setitem(_cap._BENCH_CACHE, "SPX", _b)
    monkeypatch.setitem(_cap._BENCH_CACHE, "TWII", _b)
    # stub USDTWD 抓取 → fx_regime_by_ccy 不打網路(v19.426 稽核 Finding2)
    import ui.helpers.fund_grp_health.fx_regime as _fr
    _fr._FX_REGIME_CACHE.clear()
    _fxd = pd.DataFrame({"date": pd.date_range("2023-01-02", periods=250, freq="B"),
                         "usdtwd": np.linspace(30.0, 33.0, 250)})
    monkeypatch.setattr("services.hot_money_service.fetch_usdtwd_frame",
                        lambda days: (_fxd, ""), raising=True)


def test_ok_row_full_columns_and_json_safe(_mock):
    r = build_batch_unified_row("ACCP138")
    assert set(r.keys()) == set(BATCH_UNIFIED_COLUMNS)      # 欄位完整對齊
    assert r["狀態"] == "✅ 成功"
    assert r["code"] == "ACCP138"
    # ①②③+extra 各有代表欄(至少能算出來)
    assert "4D Grade" in r and "每月配息 (TWD)" in r and "現價" in r and "含息% (全期實際)" in r
    json.dumps(r)                                           # JSON-safe → checkpoint 可存


def test_nav_fx_columns_wired_real_path(_mock):
    """稽核 Finding2:走真實 build 路徑驗 ccy/σ rank 欄名契約 —— 斷了會變 ⬜,此測會抓到。"""
    r = build_batch_unified_row("ACCP138")
    # spot 32 vs series 30~33(mean≈31.5)→ |z|<0.7 → 中性(非 ⬜ = ccy/FX 有接上)
    assert r["匯率位階"] == "中性"
    assert r["淨值×匯率"] in ("🟢 雙便宜(進場佳)", "🔴 雙貴(出場佳)", "⚪ 觀望", "⬜ 無法判定")


def test_empty_code_is_invalid(_mock):
    r = build_batch_unified_row("")
    assert r["狀態"] == "⚠️ 無效代號"
    assert set(r.keys()) == set(BATCH_UNIFIED_COLUMNS)


def test_fetch_fail_row(monkeypatch):
    monkeypatch.setattr("services.moneydj_fetcher.auto_fetch_moneydj",
                        lambda c, *a, **k: {"error": "子網域 403", "series": None}, raising=True)
    r = build_batch_unified_row("ACCP138")
    assert r["狀態"] == "❌ 抓取失敗" and "403" in (r["備註"] or "")
    assert set(r.keys()) == set(BATCH_UNIFIED_COLUMNS)


def test_batch_base_keys_covers_process_one_fund(_mock):
    """漂移鎖:process_one_fund 若新增顯示欄卻沒同步 _BATCH_BASE_KEYS,批次表會靜默漏欄。"""
    from services.fund_row import process_one_fund

    from ui.helpers.fund_grp_health.unified import _BATCH_BASE_KEYS
    base = process_one_fund("ACCP138", 1_000_000.0)
    assert base.get("ok")
    actual = {k for k in base if not str(k).startswith("_") and k != "ok"}
    missing = actual - set(_BATCH_BASE_KEYS)
    assert not missing, f"process_one_fund 新增欄未同步 _BATCH_BASE_KEYS: {missing}"


def test_columns_have_key_groups():
    # 欄序:身分/狀態 → ① 評分 → ② 配息 → extra σ/MK → base ③ 末段
    cols = BATCH_UNIFIED_COLUMNS
    assert cols[:4] == ["code", "基金名", "狀態", "備註"]
    assert "4D Grade" in cols and "每月配息 (TWD)" in cols and "現價" in cols
    assert "累積 TWD 配息 🧮" in cols        # ③ base 欄保留
    assert len(cols) == len(set(cols))       # 無重複
