"""test_mk_dashboard — v18.158 helper 單元測試。

只測 `_fund_age_years`（pure function 不涉 streamlit / network）；
其它 tag_* 與 build_mk_dataframe 已由 test_app_smoke / AppTest 覆蓋。
"""
from __future__ import annotations

import pandas as pd

from ui.components.mk_dashboard import _fund_age_years


def _mk_series(start: str, n: int = 10) -> pd.Series:
    """從 start 開始往後 n 個工作日的 NAV series。"""
    idx = pd.date_range(start=start, periods=n, freq="B")
    return pd.Series([10.0 + i * 0.01 for i in range(n)], index=idx)


def test_fund_age_years_none_series():
    assert _fund_age_years(None) is None


def test_fund_age_years_empty_series():
    assert _fund_age_years(pd.Series([], dtype=float)) is None


def test_fund_age_years_recent_about_1y():
    """1 年前起始 → 約 1 年。"""
    today = pd.Timestamp.now()
    start = (today - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    age = _fund_age_years(_mk_series(start, n=20))
    assert age is not None
    assert 0.95 < age < 1.05


def test_fund_age_years_5y_old():
    """5 年前起始 → 約 5 年。"""
    today = pd.Timestamp.now()
    start = (today - pd.Timedelta(days=365 * 5)).strftime("%Y-%m-%d")
    age = _fund_age_years(_mk_series(start, n=20))
    assert age is not None
    assert 4.9 < age < 5.1


def test_fund_age_years_low_freq_still_works():
    """低頻 NAV（只 12 點但跨 3+ 年）— 取代 ret_3y 的脆弱判斷。"""
    today = pd.Timestamp.now()
    start = (today - pd.Timedelta(days=365 * 3 + 30)).strftime("%Y-%m-%d")
    # 只 12 個月線數據，遠不到 _ret(756) 的門檻
    idx = pd.date_range(start=start, periods=12, freq="ME")
    s = pd.Series([10.0 + i * 0.1 for i in range(12)], index=idx)
    age = _fund_age_years(s)
    assert age is not None
    assert age >= 3.0   # 關鍵：≥3 年該回 True
