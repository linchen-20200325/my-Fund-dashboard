"""tests/test_fund_batch.py — 批次基金分析 L2 攤平器測試。

涵蓋 §6「3 個最容易出錯的輸入」+ §1 fail-loud + 欄位不變量:
1. 未知/空白代號          → status=unknown_code(不抓、不炸)
2. 全來源失敗(fd 空/error/拋)→ status=fetch_fail(§1 不回半空假列)
3. NaN 指標               → 攤平後一律 None(§1 絕不偽造成 0)

外加:happy path 欄位對映正確;無 NAV → no_nav;指標空 → partial;稀疏 → note;
**不變量**:任何 status 回傳列的 key 集合恆等於 ROW_COLUMNS。

不打網路:monkeypatch `services.moneydj_fetcher.auto_fetch_moneydj`(analyze_fund_row
內部 lazy import,故 patch 源模組屬性即生效)。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from services.fund_batch import (
    ROW_COLUMNS,
    STATUS_FETCH_FAIL,
    STATUS_NO_NAV,
    STATUS_OK,
    STATUS_PARTIAL,
    STATUS_UNKNOWN_CODE,
    analyze_fund_row,
)


def _series(n=400, start=100.0):
    """造一段 DatetimeIndex 的 NAV 序列(遞增日期,正值)。"""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    return pd.Series([start + i * 0.01 for i in range(n)], index=idx)


def _fd(**over):
    """一份成功的 auto_fetch_moneydj 回傳骨架,可覆寫。"""
    fd = {
        "series": _series(),
        "dividends": [],
        "currency": "USD",
        "fund_name": "測試基金 A",
        "data_source": "moneydj",
        "mgmt_fee": "1.50%",
        "metrics": {
            "nav": 104.0, "ret_1m": 1.2, "ret_3m": 3.4, "ret_6m": 5.6,
            "ret_1y": 8.8, "ret_1y_total": 10.1, "ret_3y_ann": 6.5, "ret_5y_ann": 7.2,
            "sharpe": 1.3, "sortino": 1.6, "calmar": 0.9, "std_1y": 12.5,
            "max_drawdown": -18.0, "annual_div_rate": 6.0, "div_freq_n": 12,
        },
    }
    fd.update(over)
    return fd


def _patch(monkeypatch, fd_or_exc):
    """monkeypatch auto_fetch_moneydj。analyze_fund_row 內 lazy import,故 patch 源模組。"""
    def _fn(code, *a, **k):
        if isinstance(fd_or_exc, Exception):
            raise fd_or_exc
        return fd_or_exc
    monkeypatch.setattr("services.moneydj_fetcher.auto_fetch_moneydj", _fn, raising=True)


# ───────────────────── 不變量:key 集合恆完整 ─────────────────────
def _assert_full_keys(row):
    assert set(row.keys()) == set(ROW_COLUMNS)


# ───────────────────── 輸入#1:未知/空白代號 ─────────────────────
def test_empty_code_unknown_no_fetch(monkeypatch):
    # 就算 fetcher 會炸,空碼也不該呼叫它
    _patch(monkeypatch, RuntimeError("不該被呼叫"))
    row = analyze_fund_row("   ")
    assert row["status"] == STATUS_UNKNOWN_CODE
    _assert_full_keys(row)
    # 數值欄全 None(§1)
    for c in ROW_COLUMNS:
        if c not in ("code", "name", "status", "note"):
            assert row[c] is None


# ───────────────────── 輸入#2:全來源失敗 ─────────────────────
def test_fetch_empty_dict_is_fetch_fail(monkeypatch):
    _patch(monkeypatch, {})
    row = analyze_fund_row("ACCP138")
    assert row["status"] == STATUS_FETCH_FAIL
    assert row["nav"] is None
    _assert_full_keys(row)


def test_fetch_error_without_series_is_fetch_fail(monkeypatch):
    _patch(monkeypatch, {"error": "子網域 403", "series": None})
    row = analyze_fund_row("ACCP138")
    assert row["status"] == STATUS_FETCH_FAIL
    assert "403" in row["note"]
    _assert_full_keys(row)


def test_fetch_raises_is_caught_as_fetch_fail(monkeypatch):
    """單檔 fetcher 拋例外 → 收成失敗列,不可外拋拖垮整批。"""
    _patch(monkeypatch, ValueError("timeout"))
    row = analyze_fund_row("ACCP138")
    assert row["status"] == STATUS_FETCH_FAIL
    assert "ValueError" in row["note"]
    _assert_full_keys(row)


def test_no_nav_series_is_no_nav(monkeypatch):
    _patch(monkeypatch, _fd(series=None, error=None))
    row = analyze_fund_row("ACCP138")
    assert row["status"] == STATUS_NO_NAV
    assert row["name"] == "測試基金 A"   # 名稱仍保留
    _assert_full_keys(row)


# ───────────────────── 輸入#3:NaN 指標 → None ─────────────────────
def test_nan_metrics_become_none(monkeypatch):
    """§1:NaN / inf 指標一律 None,絕不偽造成 0。"""
    _patch(monkeypatch, _fd(metrics={
        "nav": float("nan"), "ret_1y": np.nan, "sharpe": float("inf"),
        "std_1y": np.float64("nan"), "max_drawdown": None, "div_freq_n": 12,
    }))
    row = analyze_fund_row("ACCP138")
    assert row["status"] == STATUS_OK      # 有 metrics dict
    assert row["nav"] is None              # NaN → None
    assert row["ret_1y_pct"] is None
    assert row["sharpe"] is None           # inf → None
    assert row["vol_1y_pct"] is None
    _assert_full_keys(row)


# ───────────────────── happy path 欄位對映 ─────────────────────
def test_happy_path_flatten(monkeypatch):
    _patch(monkeypatch, _fd())
    row = analyze_fund_row("accp138")       # 小寫 → 應 upper
    assert row["code"] == "ACCP138"
    assert row["status"] == STATUS_OK
    assert row["currency"] == "USD"
    assert row["nav"] == 104.0
    assert row["ret_1y_pct"] == 8.8
    assert row["ret_1y_total_pct"] == 10.1
    assert row["sharpe"] == 1.3
    assert row["vol_1y_pct"] == 12.5
    assert row["max_drawdown_pct"] == -18.0
    assert row["div_yield_pct"] == 6.0
    assert row["div_freq"] == "月配"        # 12 → 月配
    assert row["mgmt_fee"] == "1.50%"
    assert row["data_source"] == "moneydj"
    assert row["nav_points"] == 400
    assert row["nav_date"] == "2025-02-03"  # date_range 2024-01-01 + 399 天
    _assert_full_keys(row)


def test_empty_metrics_is_partial(monkeypatch):
    """有 NAV 序列但 metrics 空(序列過短未計算)→ partial,非 ok。"""
    _patch(monkeypatch, _fd(metrics={}))
    row = analyze_fund_row("ACCP138")
    assert row["status"] == STATUS_PARTIAL
    assert row["nav"] is None
    _assert_full_keys(row)


def test_sparse_flag_writes_note(monkeypatch):
    _patch(monkeypatch, _fd(metrics={
        "nav": 104.0, "div_freq_n": 4, "is_sparse": True,
        "sparse_reason": "累積序列稀疏(覆蓋 40%)→ 年化指標不給假精確",
    }))
    row = analyze_fund_row("ACCP138")
    assert row["is_sparse"] is True
    assert "稀疏" in row["note"]
    assert row["div_freq"] == "季配"        # 4 → 季配
    _assert_full_keys(row)


def test_div_freq_unknown_is_none(monkeypatch):
    _patch(monkeypatch, _fd(metrics={"nav": 100.0, "div_freq_n": 7}))
    row = analyze_fund_row("ACCP138")
    assert row["div_freq"] is None          # 非 12/4/2/1 → None,不腦補
    _assert_full_keys(row)


def test_zh_labels_cover_all_columns_and_statuses():
    """中文標題 / 狀態標籤必須覆蓋所有欄位與 status(新增欄漏標題會被此測抓到)。"""
    from services import fund_batch as fb
    assert set(fb.COLUMN_LABELS_ZH) == set(fb.ROW_COLUMNS)   # 無漏、無多
    statuses = {fb.STATUS_OK, fb.STATUS_PARTIAL, fb.STATUS_NO_NAV,
                fb.STATUS_FETCH_FAIL, fb.STATUS_UNKNOWN_CODE}
    assert statuses <= set(fb.STATUS_LABELS_ZH)
