"""tests/test_benchmark_compare.py — 基金 vs 大盤(純價格差 + 疊圖)v19.420。

驗:跑贏→正、跑輸→負、近1Y窗口、不足1Y→全期標記、缺料→None、疊圖兩條起點=100。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.benchmark_compare import excess_return, rebased_pair

_DATES_2Y = pd.date_range("2022-01-31", periods=25, freq="ME")   # 2 年月頻


def _nav(monthly_step, dates=_DATES_2Y):
    return pd.Series(100 * np.cumprod([1.0] + [1 + monthly_step] * (len(dates) - 1)), index=dates)


def test_fund_beats_market_positive_excess():
    fund = _nav(0.01)     # 月 +1%
    bench = _nav(0.005)   # 月 +0.5%
    r = excess_return(fund, bench)
    assert r["excess_pct"] is not None
    assert r["fund_pct"] > r["bench_pct"] > 0
    assert r["excess_pct"] > 0
    assert r["excess_pct"] == round(r["fund_pct"] - r["bench_pct"], 1)   # 顯示對得起來(F-BM-3)
    assert r["full_period"] is False        # 2 年資料 → 用近 1 年,非全期


def test_different_grid_still_fair():
    """基金(疏,月頻子集)與大盤(密,交易日)在**共同日期上完全相同** → excess ≈ 0。

    這是核心公平性測試:修前(各自 forward-slice grid)一檔等於大盤的基金會被算出假超額;
    修後(以共同交易日為錨,同一組日期量兩邊)→ 幾乎 0。
    """
    dates_b = pd.date_range("2022-01-03", periods=520, freq="B")     # 2 年交易日大盤
    bench = pd.Series(100 * np.cumprod([1.0] + [1.0004] * (len(dates_b) - 1)), index=dates_b)
    fund = bench.iloc[::21].copy()      # 每 ~21 交易日取一點;值與大盤在這些日期完全相同
    r = excess_return(fund, bench)
    assert r["excess_pct"] is not None
    assert abs(r["excess_pct"]) < 0.05                      # 共同日值相同 → 幾乎 0


def test_tz_aware_vs_naive_no_crash():
    """基金 tz-aware(TW UTC+8)、大盤 tz-naive → 不 TypeError;同值同日 → excess ≈ 0。"""
    f = _nav(0.01)
    f.index = f.index.tz_localize("Asia/Taipei")
    r = excess_return(f, _nav(0.01))
    assert r["excess_pct"] is not None                     # 不 crash
    assert abs(r["excess_pct"]) < 0.05


def test_excess_ties_out_exactly():
    r = excess_return(_nav(0.012), _nav(0.006))
    assert r["excess_pct"] == round(r["fund_pct"] - r["bench_pct"], 1)


def test_duplicate_dates_deduped():
    idx = pd.to_datetime(["2022-01-31", "2022-01-31", "2022-02-28", "2022-03-31"])
    r = excess_return(pd.Series([100.0, 101.0, 102.0, 103.0], index=idx),
                      pd.Series([100.0, 100.0, 101.0, 102.0], index=idx))
    assert r["excess_pct"] is not None                     # 重複日取最後,不 crash / 不重複計


def test_fund_lags_market_negative_excess():
    fund = _nav(0.002)
    bench = _nav(0.01)
    r = excess_return(fund, bench)
    assert r["excess_pct"] < 0


def test_short_history_flags_full_period():
    _d = pd.date_range("2023-08-31", periods=6, freq="ME")   # 僅 5 個月 < 1 年
    r = excess_return(_nav(0.01, _d), _nav(0.005, _d))
    assert r["excess_pct"] is not None
    assert r["full_period"] is True         # 共同歷史不足 1 年 → 全期並標記


def test_none_or_too_short_returns_blank():
    assert excess_return(None, _nav(0.01))["excess_pct"] is None
    assert excess_return(_nav(0.01), None)["excess_pct"] is None
    one = pd.Series([100.0], index=_DATES_2Y[:1])
    assert excess_return(one, _nav(0.01))["excess_pct"] is None


def test_nav_zero_negative_excluded():
    """NAV 含 0/負(清算)→ _prep 過濾;仍有 ≥2 正點則可算。"""
    s = _nav(0.01).copy()
    s.iloc[0] = 0.0
    r = excess_return(s, _nav(0.005))
    assert r["excess_pct"] is not None      # 去掉 0 後仍足夠


def test_rebased_pair_starts_at_100():
    df = rebased_pair(_nav(0.01), _nav(0.005))
    assert df is not None
    assert list(df.columns) == ["基金", "大盤"]
    assert abs(df["基金"].dropna().iloc[0] - 100.0) < 1e-6
    assert abs(df["大盤"].dropna().iloc[0] - 100.0) < 1e-6
    assert df["基金"].dropna().iloc[-1] > df["大盤"].dropna().iloc[-1]   # 基金漲更多


def test_rebased_pair_none_on_missing():
    assert rebased_pair(None, _nav(0.01)) is None
