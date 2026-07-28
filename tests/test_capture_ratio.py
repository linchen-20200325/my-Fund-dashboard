"""tests/test_capture_ratio.py — 上/下檔捕捉率 + 操盤評分(v19.414)。

驗 user 的直覺例子:抗跌 → 高分、比大盤慘 → 低分、月數不足 → None、幣別選基準。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.capture_ratio import benchmark_for_currency, compute_capture

_DATES = pd.date_range("2022-01-31", periods=25, freq="ME")


def _nav(returns):
    return pd.Series(100 * np.cumprod([1 + r for r in returns]), index=_DATES)


_BENCH = _nav([0] + [0.03] * 12 + [-0.04] * 12)   # 12 漲月 + 12 跌月


def test_downside_protector_high_score():
    """大盤跌時只跌 1/5、漲時跟上 → 下檔捕捉低、評分高。"""
    fund = _nav([0] + [0.03] * 12 + [-0.008] * 12)
    r = compute_capture(fund, _BENCH)
    assert r["upside"] == 100.0
    assert 0 < r["downside"] < 40         # 超抗跌
    assert r["score"] >= 80


def test_underperformer_low_score():
    """漲跟不上 + 跌比大盤還多 → 下檔捕捉 >100、評分低。"""
    fund = _nav([0] + [0.02] * 12 + [-0.05] * 12)
    r = compute_capture(fund, _BENCH)
    assert r["downside"] > 100
    assert r["score"] < 50


def test_user_example_50pct_crash():
    """user 例子:大盤跌 ~50%、基金只跌 ~10% → 下檔捕捉 ~20%。"""
    dr_b = 0.5 ** (1 / 6) - 1            # 6 月複利 = -50%
    dr_f = 0.9 ** (1 / 6) - 1            # 6 月複利 = -10%
    dates = pd.date_range("2022-01-31", periods=13, freq="ME")
    bench = pd.Series(100 * np.cumprod([1 + x for x in [0] + [0.05] * 6 + [dr_b] * 6]), index=dates)
    fund = pd.Series(100 * np.cumprod([1 + x for x in [0] + [0.05] * 6 + [dr_f] * 6]), index=dates)
    r = compute_capture(fund, bench)
    assert abs(r["downside"] - 20.0) < 1.0     # -10 / -50 = 20%
    assert r["score"] > 60


def test_insufficient_months_returns_none():
    fund = _nav([0] + [0.03] * 12 + [-0.008] * 12)
    r = compute_capture(fund.head(8), _BENCH.head(8))
    assert r["upside"] is None and r["downside"] is None and r["score"] is None


def test_none_inputs():
    assert compute_capture(None, _BENCH)["score"] is None
    assert compute_capture(_BENCH, None)["score"] is None


def test_benchmark_for_currency():
    assert benchmark_for_currency("USD") == "SPX"
    assert benchmark_for_currency("EUR") == "SPX"
    assert benchmark_for_currency("美元") == "SPX"
    assert benchmark_for_currency("TWD") == "TWII"
    assert benchmark_for_currency("台幣") == "TWII"


def test_gap_month_return_dropped():
    """F-CAP-2:NAV 缺月(停售/新基金)→ 跨缺口的假單月報酬須丟棄,不當 1 個月算。"""
    from services.capture_ratio import _monthly_returns
    idx = pd.to_datetime(["2022-01-31", "2022-03-31", "2022-04-30", "2022-05-31"])
    r = _monthly_returns(pd.Series([100, 90, 91, 92], index=idx))
    months = [str(d)[:7] for d in r.index]
    assert "2022-03" not in months            # 橫跨 Feb 缺口 → 丟(否則會被當 -10% 單月)
    assert "2022-04" in months and "2022-05" in months


def test_score_clamped_0_100():
    """極端抗跌(下跌月反而賺)→ 評分不超過 100。"""
    fund = _nav([0] + [0.05] * 12 + [0.01] * 12)   # 大盤跌月基金還漲
    r = compute_capture(fund, _BENCH)
    assert 0 <= r["score"] <= 100
