"""test_compute_1y_total_return.py — 1Y 含息報酬 SSOT 測試(2026-10-23 裁示 1B 改寫)

歷史:v18.134 抽共用 helper 修「Tab2 vs Tab3 同基金 1Y 報酬不同」;2026-08-10 來源標籤改白話。
2026-10-23 客戶裁示 1B 後 **唯一算法 = 本地配息還原淨值法**(`metrics.ret_1y_total`,
窗口 ≥ `RET_1Y_RESTORED_MIN_WINDOW_DAYS`),舊的四層 fallback(官方 perf["1Y"] / 短窗累積 /
純淨值 / NAV 外推)一律改回「⬜ 資料未備／無法判定」+ 白話原因,**不給值**。
本檔原本守的是那四層的優先序;現在守的是「**那四層都不能再給值**」—— 方向相反、
嚴格度只增不減:改回任何一層舊 fallback 都會讓這裡轉紅。
"""
from __future__ import annotations

import pandas as pd
import pytest

from services.fund_total_return import (
    SRC_IMPLAUSIBLE_SUFFIX,
    SRC_NONE,
    SRC_SELF_RESTORED,
    SRC_UNAVAILABLE_PREFIX,
    compute_1y_total_return,
    is_dividend_fund,
    is_too_short_1y_source,
    resolve_1y_total_return,
)
from shared.signal_thresholds import RET_1Y_RESTORED_MIN_WINDOW_DAYS


def _ok_metrics(v: float = 5.0, wd: int = 365, div_count=None) -> dict:
    m = {"ret_1y_total": v, "ret_1y_window_days": wd}
    if div_count is not None:
        m["ret_1y_div_count"] = div_count
    return m


# ── 唯一算法:本地還原淨值法 ─────────────────────────────────────────────
def test_restored_value_is_the_only_source():
    r = resolve_1y_total_return({"metrics": _ok_metrics(5.0, 365), "moneydj_raw": {}})
    assert r["status"] == "ok" and r["value_pct"] == 5.0
    assert r["source"] == SRC_SELF_RESTORED and r["label"] == SRC_SELF_RESTORED
    assert r["reason"] is None and r["window_days"] == 365
    assert compute_1y_total_return({"metrics": _ok_metrics(5.0, 365)}) == (5.0, SRC_SELF_RESTORED)


def test_official_perf_1y_never_used_as_value_even_when_present():
    """官方 wb01 perf["1Y"] 只能進 `official_1y_pct`(對帳用),**絕不**當主值。"""
    obj = {
        "metrics": {"ret_1y_total": 37.6, "ret_1y_window_days": 365, "ret_1y": 10.0},
        "moneydj_raw": {"perf": {"1Y": 9.09}, "perf_source": "wb01"},
    }
    r = resolve_1y_total_return(obj)
    assert r["value_pct"] == 37.6, "主值必須是本地還原值,不是官方 perf['1Y']"
    assert r["official_1y_pct"] == 9.09


def test_official_only_without_restored_value_is_unavailable():
    """只有 perf['1Y'](wb01)、沒有還原值 → unavailable;官方值只在 official_1y_pct。"""
    for obj in (
        {"moneydj_raw": {"perf": {"1Y": 9.09}}, "perf_source": "wb01", "metrics": {}},
        {"perf": {"1Y": 9.09}, "perf_source": "wb01", "metrics": {}},   # flat shape
        {"moneydj_raw": {"perf": {"1Y": 9.09}}, "metrics": {}},         # 來源未標註
    ):
        r = resolve_1y_total_return(obj)
        assert r["status"] == "unavailable" and r["value_pct"] is None, obj
        assert r["reason"] == "no_series" and r["source"] == SRC_NONE
        assert r["label"].startswith(SRC_UNAVAILABLE_PREFIX)
        v, src = compute_1y_total_return(obj)
        assert v is None and src == r["label"]
    # 只有 perf_source == "wb01" 才認官方值
    assert resolve_1y_total_return(
        {"moneydj_raw": {"perf": {"1Y": 9.09}}, "metrics": {}})["official_1y_pct"] is None
    assert resolve_1y_total_return(
        {"moneydj_raw": {"perf": {"1Y": 9.09}}, "perf_source": "wb01",
         "metrics": {}})["official_1y_pct"] == 9.09


def test_local_calc_perf_source_no_longer_exists_as_a_value_path():
    """舊 `perf_source == "local_calc"` 注入路徑已移除:有 perf 但無 ret_1y_total → unavailable。"""
    obj = {"moneydj_raw": {"perf": {"1Y": 12.5}}, "perf_source": "local_calc", "metrics": {}}
    v, src = compute_1y_total_return(obj)
    assert v is None and src.startswith(SRC_UNAVAILABLE_PREFIX)


# ── 四種 unavailable 原因 ────────────────────────────────────────────────
def test_short_window_is_unavailable_not_a_partial_value():
    """窗口 < RET_1Y_RESTORED_MIN_WINDOW_DAYS → 不給「N 天累積」值,誠實 window_short。"""
    obj = {"metrics": {"ret_1y_total": 25.0, "ret_1y_window_days": 90}, "moneydj_raw": {}}
    r = resolve_1y_total_return(obj)
    assert r["status"] == "unavailable" and r["value_pct"] is None
    assert r["reason"] == "window_short" and r["window_days"] == 90
    assert "90" in r["label"] and r["label"].startswith(SRC_UNAVAILABLE_PREFIX)
    assert is_too_short_1y_source(r["label"]) is True
    # 門檻邊界:剛好等於 SSOT 值 → ok;少 1 天 → unavailable
    assert resolve_1y_total_return(
        {"metrics": _ok_metrics(1.0, RET_1Y_RESTORED_MIN_WINDOW_DAYS)})["status"] == "ok"
    assert resolve_1y_total_return(
        {"metrics": _ok_metrics(1.0, RET_1Y_RESTORED_MIN_WINDOW_DAYS - 1)})["reason"] == "window_short"


def test_pure_nav_ret_1y_is_never_used():
    """純淨值 `metrics.ret_1y`(不含配息)**絕不**當 1Y 含息報酬。"""
    obj = {"metrics": {"ret_1y": 8.5}, "moneydj_raw": {}}
    r = resolve_1y_total_return(obj)
    assert r["status"] == "unavailable" and r["value_pct"] is None
    assert r["reason"] == "no_series"


def test_nav_series_is_never_annualized_or_extrapolated():
    """有 series、但 calc_metrics 沒算出還原值 → `no_restored_value`,**不**自己外推年化。"""
    idx = pd.date_range("2024-01-01", "2025-01-01", freq="D")
    s = pd.Series([100.0] * (len(idx) - 1) + [110.0], index=idx)
    obj = {"metrics": {}, "moneydj_raw": {}, "series": s}
    r = resolve_1y_total_return(obj)
    assert r["status"] == "unavailable" and r["value_pct"] is None
    assert r["reason"] == "no_restored_value"
    assert "外推" not in r["label"]
    assert is_too_short_1y_source(r["label"]) is False


def test_all_missing_is_no_series():
    obj = {"metrics": {}, "moneydj_raw": {}}
    r = resolve_1y_total_return(obj)
    assert r["status"] == "unavailable" and r["reason"] == "no_series"
    assert r["source"] == SRC_NONE
    assert is_too_short_1y_source(r["label"]) is True
    v, src = compute_1y_total_return(obj)
    assert v is None and src.startswith(SRC_UNAVAILABLE_PREFIX)


def test_dividend_fund_with_zero_dividends_in_window_is_unavailable():
    """配息基金(wb05 > 0 或有配息紀錄)但還原窗口內 0 筆 → dividend_data_missing。"""
    obj = {"metrics": _ok_metrics(3.0, 365, div_count=0),
           "moneydj_raw": {"moneydj_div_yield": 5.0}}
    r = resolve_1y_total_return(obj)
    assert r["status"] == "unavailable" and r["reason"] == "dividend_data_missing"
    assert r["div_count_in_window"] == 0
    # 同樣的 metrics、但不是配息基金 → ok(累積型基金本來就 0 筆)
    r2 = resolve_1y_total_return({"metrics": _ok_metrics(3.0, 365, div_count=0),
                                  "moneydj_raw": {}})
    assert r2["status"] == "ok" and r2["value_pct"] == 3.0
    # 窗內有配息 → ok
    r3 = resolve_1y_total_return({"metrics": _ok_metrics(3.0, 365, div_count=12),
                                  "moneydj_raw": {"moneydj_div_yield": 5.0}})
    assert r3["status"] == "ok" and r3["div_count_in_window"] == 12


def test_window_short_takes_precedence_over_dividend_gate():
    obj = {"metrics": _ok_metrics(3.0, 200, div_count=0),
           "moneydj_raw": {"moneydj_div_yield": 5.0}}
    assert resolve_1y_total_return(obj)["reason"] == "window_short"


# ── is_dividend_fund ─────────────────────────────────────────────────────
def test_is_dividend_fund_uses_only_existing_data():
    assert is_dividend_fund({"moneydj_raw": {"moneydj_div_yield": 5.0}}) is True
    assert is_dividend_fund({"moneydj_div_yield": "5.0"}) is True
    assert is_dividend_fund({"dividends": [{"date": "2026-01-01", "amount": 0.1}]}) is True
    assert is_dividend_fund({"moneydj_raw": {"dividends": [("2026-01-01", 0.1)]}}) is True
    assert is_dividend_fund({"dividends": [{"date": "2026-01-01", "amount": 0}]}) is False
    assert is_dividend_fund({"moneydj_raw": {"moneydj_div_yield": 0}}) is False
    assert is_dividend_fund({"moneydj_raw": {"moneydj_div_yield": "N/A"}}) is False
    assert is_dividend_fund({}) is False


# ── 合理帶警語照舊黏在 label(只標記,不改值) ─────────────────────────────
@pytest.mark.parametrize("bad", [201.65, 190.64, -99.0])
def test_implausible_restored_value_is_flagged_not_dropped(bad):
    r = resolve_1y_total_return({"metrics": _ok_metrics(bad, 365), "moneydj_raw": {}})
    assert r["status"] == "ok" and r["value_pct"] == pytest.approx(bad)
    assert r["label"].startswith(SRC_SELF_RESTORED) and SRC_IMPLAUSIBLE_SUFFIX in r["label"]


def test_non_numeric_restored_value_is_unavailable_not_ok():
    r = resolve_1y_total_return({"metrics": {"ret_1y_total": "abc", "ret_1y_window_days": 365},
                                 "series": pd.Series([1.0, 2.0])})
    assert r["status"] == "unavailable" and r["reason"] == "no_restored_value"


# ── shape normalize(flat / nested 同結果) ────────────────────────────────
class TestFlatFdShapeNormalize:
    def test_flat_fd_vs_nested_same_result(self):
        flat_fd = {"perf": {"1Y": 12.35}, "perf_source": "wb01",
                   "metrics": _ok_metrics(7.0, 365)}
        nested_fd = {"moneydj_raw": {"perf": {"1Y": 12.35}}, "perf_source": "wb01",
                     "metrics": _ok_metrics(7.0, 365)}
        r_flat, r_nested = resolve_1y_total_return(flat_fd), resolve_1y_total_return(nested_fd)
        assert r_flat == r_nested
        assert r_flat["value_pct"] == 7.0 and r_flat["official_1y_pct"] == 12.35

    def test_flat_fd_without_perf_resolves_normally(self):
        flat_fd = {"perf": {}, "series": None, "metrics": _ok_metrics(8.0, 365), "dividends": []}
        assert compute_1y_total_return(flat_fd) == (8.0, SRC_SELF_RESTORED)

    def test_flat_fd_dividends_feed_the_dividend_gate(self):
        """flat shape 的 top-level `dividends` 也要進配息閘門(normalize 不能把它弄丟)。"""
        flat_fd = {"perf": {}, "metrics": _ok_metrics(8.0, 365, div_count=0),
                   "dividends": [{"date": "2025-01-01", "amount": 0.3}]}
        assert resolve_1y_total_return(flat_fd)["reason"] == "dividend_data_missing"
