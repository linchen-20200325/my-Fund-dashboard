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
    # 2026-10-30 修正（與 BL-0525 無關；有意識的更正，不是漏刪）：舊值 `365 * 3 + 30` 只留 30 天餘裕，但 `freq="ME"` 會把第一個點
    # 推到「起點之後的月底」，最多晚 30 天；起點落在月初那幾天（例：2023-10-01）時年資 2.998 < 3.0，測試隨日期紅。
    # 餘裕放到 60 天，涵蓋月底對齊最多 30 天的位移；測試意圖（低頻、點數遠少於 756、跨 3+ 年仍判 ≥3 年）不變。
    start = (today - pd.Timedelta(days=365 * 3 + 60)).strftime("%Y-%m-%d")
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


def test_total_return_1y_uses_restored_value_not_perf():
    """2026-10-23 裁示 1B:含息總報酬(1Y%) 讀本地還原值 `metrics.ret_1y_total`(窗口 ≥ 350 天),
    **不再**讀 MoneyDJ perf['1Y'](官方值只對帳)。"""
    f = {
        "loaded": True, "code": "TEST1", "name": "測試多重收益B配息",
        "metrics": {"nav": 10.0, "ret_1y": None, "annual_div_rate": 8.0,
                    "ret_1y_total": 6.0, "ret_1y_window_days": 365, "ret_1y_div_count": 12,
                    "sharpe": 0.5, "std_1y": 5.0},
        "moneydj_raw": {"perf": {"1Y": 7.5}},
        "series": _short_nav(),
        "perf_source": "wb01",
    }
    df = build_mk_dataframe([f])
    assert len(df) == 1
    assert df.iloc[0]["含息總報酬(1Y%)"] == 6.0   # 還原值,不是 perf['1Y'] 的 7.5


def test_total_return_1y_blank_when_only_perf_available():
    """只有官方 perf['1Y']、沒有本地還原值 → 誠實留白(None),不拿官方值頂替。"""
    f = {
        "loaded": True, "code": "TEST1B", "name": "只有官方值",
        "metrics": {"nav": 10.0, "ret_1y": None, "annual_div_rate": 8.0},
        "moneydj_raw": {"perf": {"1Y": 7.5}},
        "series": _short_nav(),
        "perf_source": "wb01",
    }
    df = build_mk_dataframe([f])
    assert len(df) == 1
    assert df.iloc[0]["含息總報酬(1Y%)"] is None


def test_total_return_1y_never_annualizes_from_series():
    """無 perf + ret_1y=None + 序列跨度達舊外推門檻 → 裁示 1B 後**不再**走 NAV 年化外推,
    沒有還原值就誠實 None(乘出來的「一年報酬」不是量出來的,大表 +201% 就是這條路)。
    """
    from shared.signal_thresholds import RET_1Y_EXTRAPOLATE_MIN_DAYS
    # ⚠️ `_short_nav` 的**跨度由 n(營業日)決定**,days_back 只是起點位置。
    # 營業日 ≈ 日曆日 × 5/7,故取門檻的 1.5 倍再換算,留足餘裕。
    _n_bd = int(RET_1Y_EXTRAPOLATE_MIN_DAYS * 1.5 * 5 / 7) + 5
    f = {
        "loaded": True, "code": "TEST2", "name": "新基金",
        "metrics": {"nav": 11.0, "ret_1y": None},
        "series": _short_nav(days_back=RET_1Y_EXTRAPOLATE_MIN_DAYS * 2, n=_n_bd),
    }
    _span = (f["series"].index[-1] - f["series"].index[0]).days
    assert _span > RET_1Y_EXTRAPOLATE_MIN_DAYS, (
        f"fixture 自檢失敗:跨度只有 {_span} 天,測不到要測的分支")
    df = build_mk_dataframe([f])
    assert len(df) == 1
    assert df.iloc[0]["含息總報酬(1Y%)"] is None      # 外推層已退役 → 留白


def test_total_return_1y_blank_when_history_too_short():
    """稽核 E1 —— 跨度未達外推門檻時必須留白，不可乘出一個假的一年報酬。

    **改回舊門檻(30 天)必紅**:舊碼會用 `min(365/天數, 12)` 放大，
    150 天放大 2.4 倍、30 天放大 12 倍，兩者都會在畫面上變成一個
    看起來完全正常、還會因為數值大而排到最前面的數字。
    """
    from shared.signal_thresholds import RET_1Y_EXTRAPOLATE_MIN_DAYS
    # 同上:跨度看 n。取門檻的一半換算成營業日 → 跨度必然遠低於門檻。
    _n_bd = int(RET_1Y_EXTRAPOLATE_MIN_DAYS * 0.5 * 5 / 7)
    f = {
        "loaded": True, "code": "TEST2B", "name": "剛成立的新基金",
        "metrics": {"nav": 11.0, "ret_1y": None},
        "series": _short_nav(days_back=RET_1Y_EXTRAPOLATE_MIN_DAYS, n=_n_bd),
    }
    _span = (f["series"].index[-1] - f["series"].index[0]).days
    assert _span < RET_1Y_EXTRAPOLATE_MIN_DAYS, (
        f"fixture 自檢失敗:跨度 {_span} 天已達門檻,測不到要測的分支")
    df = build_mk_dataframe([f])
    assert len(df) == 1
    assert pd.isna(df.iloc[0]["含息總報酬(1Y%)"]), (
        "跨度不足半年仍給出一年報酬 —— 那是外推出來的，不是量出來的")


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
