"""第一波 資料真實性：有疑義的歷史資料必須加註警示（§1 Fail Loud, Never Fake）。

守的行為
--------
1. `shared.data_quality.assess_window_coverage` 的契約（涵蓋足 / 不足 / 未知跨度）。
2. `calc_metrics` 在序列不足「近 N 交易日」時,**值原樣保留**（不偷偷改數字）,
   但 `risk_metric_meta["hl_windows"]` 必須據實揭露涵蓋不足 + 原因 + 誠實標籤。
3. 迴歸實例：`cache/nav/TLZF9.json`（10 筆橫跨 14.4 年）—— 修補前「年高」會回報
   2015 年的 16.75,而近 12 個月真實區間只有 8.78~8.80。
"""
import json
from pathlib import Path

import pandas as pd
import pytest

from services.fund_service import calc_metrics
from shared.data_quality import (
    QUALITY_OK,
    QUALITY_WINDOW_SHORTFALL,
    assess_window_coverage,
)
from shared.signal_thresholds import TRADING_DAYS_PER_YEAR

_REPO = Path(__file__).resolve().parent.parent


# ── 1. SSOT 契約 ──────────────────────────────────────────────────
def test_coverage_ok_keeps_original_label():
    r = assess_window_coverage(n_points=300, requested_days=252,
                               span_days=400.0, window_label="年")
    assert r["covers_window"] is True
    assert r["code"] == QUALITY_OK
    assert r["reason"] is None
    assert r["honest_label"] == "年", "涵蓋足夠時不得竄改標籤"


def test_coverage_shortfall_flags_and_relabels():
    r = assess_window_coverage(n_points=10, requested_days=252,
                               span_days=5270.0, window_label="年")
    assert r["covers_window"] is False
    assert r["code"] == QUALITY_WINDOW_SHORTFALL
    assert "10/252" in r["reason"], "原因必須寫出實際/需求筆數"
    assert "14.4年" in r["reason"], "原因必須寫出實際涵蓋跨度"
    # 誠實標籤必須帶警示且不得再自稱「年」
    assert r["honest_label"].startswith("⚠️")
    assert r["honest_label"] != "年"


def test_coverage_boundary_exactly_enough():
    """邊界：剛好等於視窗長度 → 算涵蓋足夠（沿用既有 len(s) >= n 分支,不新增門檻）。"""
    assert assess_window_coverage(252, 252, 400.0, "年")["covers_window"] is True
    assert assess_window_coverage(251, 252, 400.0, "年")["covers_window"] is False


def test_coverage_unknown_span_still_flags():
    r = assess_window_coverage(n_points=1, requested_days=252,
                               span_days=None, window_label="年")
    assert r["covers_window"] is False
    assert r["actual_span_days"] is None
    assert r["honest_label"].startswith("⚠️")


# ── 2. calc_metrics 接線 ──────────────────────────────────────────
def _dense_series(n: int) -> pd.Series:
    idx = pd.bdate_range("2020-01-01", periods=n)
    return pd.Series([10.0 + (i % 7) * 0.1 for i in range(n)], index=idx)


def test_dense_series_reports_covered():
    m = calc_metrics(_dense_series(TRADING_DAYS_PER_YEAR + 10), [])
    w = m["risk_metric_meta"]["hl_windows"]
    assert w["1y"]["covers_window"] is True
    assert w["1y"]["reason"] is None
    assert w["1y"]["honest_label"] == "年"


def test_sparse_series_flags_shortfall_without_changing_values():
    s = _dense_series(30)
    m = calc_metrics(s, [])
    w = m["risk_metric_meta"]["hl_windows"]
    assert w["1y"]["covers_window"] is False
    assert w["1y"]["reason"], "涵蓋不足必須有原因字串（§1 不可靜默）"
    # §1：不偷偷修數字 —— 值仍等於全序列 max/min
    assert m["high_1y"] == pytest.approx(round(float(s.max()), 4))
    assert m["low_1y"] == pytest.approx(round(float(s.min()), 4))


def test_all_three_windows_annotated():
    m = calc_metrics(_dense_series(30), [])
    w = m["risk_metric_meta"]["hl_windows"]
    assert set(w) == {"1y", "2y", "3y"}
    for k in ("1y", "2y", "3y"):
        assert w[k]["requested_days"] > 0
        assert w[k]["covers_window"] is False


# ── 3. 迴歸實例：repo 內真實的稀疏快取 ────────────────────────────
def test_real_sparse_nav_cache_is_flagged():
    f = _REPO / "cache" / "nav" / "TLZF9.json"
    if not f.exists():
        pytest.skip("cache/nav/TLZF9.json 不在 —— 此為迴歸實例,非必要檔")
    hist = json.loads(f.read_text(encoding="utf-8"))["history"]
    s = pd.Series({pd.Timestamp(r["date"]): float(r["nav"]) for r in hist}).sort_index()
    m = calc_metrics(s, [])
    w1 = m["risk_metric_meta"]["hl_windows"]["1y"]
    assert w1["covers_window"] is False
    assert w1["n_points"] == len(s)
    # 這正是修補要擋的誤讀：「年高」其實是 11 年前的價
    assert m["high_date_1y"] < "2016", "迴歸實例前提改變,請重新確認此測試"
    assert w1["actual_span_days"] > 5000
    assert "⚠️" in w1["honest_label"]
