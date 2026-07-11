"""test_mk_dashboard — v18.158 helper 單元測試。

只測 `_fund_age_years`（pure function 不涉 streamlit / network）；
其它 tag_* 與 build_mk_dataframe 已由 test_app_smoke / AppTest 覆蓋。
"""
from __future__ import annotations

import pandas as pd

from ui.components.mk_dashboard import _fund_age_years, build_mk_dataframe


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


# ── v19.345: 含息總報酬(1Y%) 走 SSOT fallback，不再讀 strict-252 的 m['ret_1y'] ──
def _short_nav(days_back: int = 120, n: int = 60) -> pd.Series:
    start = (pd.Timestamp.now() - pd.Timedelta(days=days_back)).strftime("%Y-%m-%d")
    idx = pd.date_range(start=start, periods=n, freq="B")
    return pd.Series([10.0 + i * 0.02 for i in range(n)], index=idx)


def test_total_return_1y_uses_perf_when_local_ret_1y_none():
    """<252 日 NAV → m['ret_1y']=None，但 MoneyDJ perf['1Y'] 有值 → 顯示 perf（非 None）。

    這正是 user 回報「5 檔全 None」的場景：舊碼直讀 m['ret_1y'] 恆 None。
    """
    f = {
        "loaded": True, "code": "TEST1", "name": "測試多重收益B配息",
        "metrics": {"nav": 10.0, "ret_1y": None, "annual_div_rate": 8.0,
                    "sharpe": 0.5, "std_1y": 5.0},
        "moneydj_raw": {"perf": {"1Y": 7.5}},
        "series": _short_nav(),
        "perf_source": "wb01",
    }
    df = build_mk_dataframe([f])
    assert len(df) == 1
    assert df.iloc[0]["含息總報酬(1Y%)"] == 7.5   # 舊行為=None；新行為取 perf['1Y']


def test_total_return_1y_annualizes_when_short_history_no_perf():
    """無 perf + ret_1y=None + 短序列(>30d) → 走 NAV 年化 fallback，非 None。"""
    f = {
        "loaded": True, "code": "TEST2", "name": "新基金",
        "metrics": {"nav": 11.0, "ret_1y": None},
        "series": _short_nav(days_back=150, n=80),
    }
    df = build_mk_dataframe([f])
    assert len(df) == 1
    assert pd.notna(df.iloc[0]["含息總報酬(1Y%)"])   # 年化 fallback → 有值


def test_total_return_1y_still_none_when_truly_insufficient():
    """真的無任何來源(無 perf / ret_1y_total / ret_1y / 序列<3) → 仍誠實 None（§1）。"""
    f = {
        "loaded": True, "code": "TEST3", "name": "無資料基金",
        "metrics": {"nav": 10.0, "ret_1y": None},
        "series": None,
    }
    df = build_mk_dataframe([f])
    assert len(df) == 1
    assert pd.isna(df.iloc[0]["含息總報酬(1Y%)"])
