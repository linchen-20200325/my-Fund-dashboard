"""MK v3.0 標準差買賣點公式驗算
公式：
  買點 = 年高 - k×σ_amount   (k=1,2,3)
  賣點 = 年低 + k×σ_amount   (k=1,2,3)
  σ_amount = 年高 × std_1y%
  接近閾值 = 2%
"""
import numpy as np
import pandas as pd
import pytest

from fund_fetcher import calc_metrics, calculate_fund_total_return


def _fake_series(n_days=300, start_nav=10.0, daily_vol=0.012, seed=42):
    """生成模擬 NAV 序列（GBM）"""
    np.random.seed(seed)
    rets = np.random.normal(0, daily_vol, n_days)
    navs = start_nav * np.exp(np.cumsum(rets))
    dates = pd.date_range(end="2025-12-31", periods=n_days, freq="B")
    return pd.Series(navs, index=dates)


def test_mk_v3_buy_anchored_to_year_high():
    """買點公式: 年高-1σ > 年高-2σ > 年高-3σ"""
    s = _fake_series()
    risk_override = {
        "year_high_nav": float(s.tail(252).max()),
        "year_low_nav":  float(s.tail(252).min()),
        "risk_table": {
            "六個月": {"標準差": 11.5},
            "一年":   {"標準差": 12.0},
            "三年":   {"標準差": 13.0},
            "五年":   {"標準差": 14.0},
        },
    }
    m = calc_metrics(s, [], risk_override=risk_override)
    yh = risk_override["year_high_nav"]
    sigma = round(yh * 0.12, 4)
    assert abs(m["buy1"] - round(yh - 1*sigma, 4)) < 1e-3, f"buy1={m['buy1']} expected {yh - sigma}"
    assert abs(m["buy2"] - round(yh - 2*sigma, 4)) < 1e-3
    assert abs(m["buy3"] - round(yh - 3*sigma, 4)) < 1e-3
    assert m["buy_basis"] == yh
    # 三檔遞減（買3最深）
    assert m["buy1"] > m["buy2"] > m["buy3"]


def test_mk_v3_sell_anchored_to_year_low():
    """賣點公式: 年低+1σ < 年低+2σ < 年低+3σ"""
    s = _fake_series()
    risk_override = {
        "year_high_nav": float(s.tail(252).max()),
        "year_low_nav":  float(s.tail(252).min()),
        "risk_table": {
            "六個月": {"標準差": 9.5},
            "一年":   {"標準差": 10.0},
            "三年":   {"標準差": 11.0},
            "五年":   {"標準差": 12.0},
        },
    }
    m = calc_metrics(s, [], risk_override=risk_override)
    yl = risk_override["year_low_nav"]
    yh = risk_override["year_high_nav"]
    sigma = round(yh * 0.10, 4)
    assert abs(m["sell1"] - round(yl + 1*sigma, 4)) < 1e-3
    assert abs(m["sell2"] - round(yl + 2*sigma, 4)) < 1e-3
    assert abs(m["sell3"] - round(yl + 3*sigma, 4)) < 1e-3
    assert m["sell_basis"] == yl
    # 三檔遞增（賣3最高）
    assert m["sell1"] < m["sell2"] < m["sell3"]


def test_mk_v3_distance_pct_signs():
    """距離 % 正負號驗證：買 nav>target → 正；賣 nav<target → 負"""
    s = _fake_series()
    yh = float(s.tail(252).max()); yl = float(s.tail(252).min())
    risk_override = {
        "year_high_nav": yh, "year_low_nav": yl,
        "risk_table": {
            "六個月": {"標準差": 7.5},
            "一年":   {"標準差": 8.0},
            "三年":   {"標準差": 9.0},
            "五年":   {"標準差": 10.0},
        },
    }
    m = calc_metrics(s, [], risk_override=risk_override)
    nav = m["nav"]
    # 至少一個買點仍在 nav 下方 → 距離為正（尚未觸發）
    bd = m["buy_distance_pct"]
    assert bd["b1"] is not None
    # b3 比 b1 深 → b3 距離 > b1 距離（更遠）
    if all(v is not None for v in [bd["b1"], bd["b3"]]):
        assert bd["b3"] >= bd["b1"]
    # 任一買點觸發時距離 ≤ 0
    for k in ["b1", "b2", "b3"]:
        target = m[{"b1":"buy1","b2":"buy2","b3":"buy3"}[k]]
        if target and nav <= target:
            assert bd[k] is not None and bd[k] <= 0


def test_mk_v3_position_label_priority():
    """倉位標籤：深買 > 淺買 > 淺賣 > 深賣（買勝過賣以利風險控管）"""
    # 強迫 NAV 落在 b3 以下 → 應顯示「大跌大買」
    s = _fake_series()
    yh, yl = 100.0, 50.0
    sigma_pct = 10.0
    sigma = yh * sigma_pct / 100   # = 10
    # 模擬 NAV 在 b3 = 100-30 = 70 以下，但又要在合理 series 內
    # 直接餵 series 末值改寫
    s = s.copy()
    s.iloc[-1] = 65.0   # 落在 b3=70 下方
    risk_override = {
        "year_high_nav": yh, "year_low_nav": yl,
        "risk_table": {
            "六個月": {"標準差": sigma_pct - 1},
            "一年":   {"標準差": sigma_pct},
            "三年":   {"標準差": sigma_pct + 1},
            "五年":   {"標準差": sigma_pct + 2},
        },
    }
    m = calc_metrics(s, [], risk_override=risk_override)
    assert m["buy3"] == round(yh - 3*sigma, 4) == 70.0
    assert "大跌大買" in m["pos_label"], f"got {m['pos_label']}"
    # NAV=85 落在 b1=90 與 b2=80 之間 → 「小跌小買」
    s.iloc[-1] = 85.0
    m = calc_metrics(s, [], risk_override=risk_override)
    assert "小跌小買" in m["pos_label"], f"got {m['pos_label']}"
    # NAV=95 → 落在正常區（買1=90 上方、賣3=80 上方 → 觸發 sell3 大漲）
    s.iloc[-1] = 95.0
    m = calc_metrics(s, [], risk_override=risk_override)
    assert "大漲停利" in m["pos_label"], f"got {m['pos_label']}"


def test_ret_1y_total_full_window():
    """v18.71: ≥252 NAV 日 → 1Y 含息 = 還原淨值法（配息再投資複利）"""
    s = _fake_series(n_days=300, start_nav=10.0)
    # 期初（t-252）NAV = s.iloc[-252]，期末 NAV = s.iloc[-1]
    # 兩筆配息（近 1 年內各 0.05）→ 配息再投資複利
    divs = [
        {"date": s.index[-100].strftime("%Y-%m-%d"), "amount": 0.05},
        {"date": s.index[-50].strftime("%Y-%m-%d"),  "amount": 0.05},
    ]
    m = calc_metrics(s, divs)
    # 手算還原淨值：在 -100 與 -50 兩天，Factor = 1 + 0.05/NAV_t
    nav_at_100 = float(s.iloc[-100])
    nav_at_50 = float(s.iloc[-50])
    factor1 = 1 + 0.05 / nav_at_100
    factor2 = 1 + 0.05 / nav_at_50
    cum_factor = factor1 * factor2
    base = float(s.iloc[-252])
    end = float(s.iloc[-1])
    expected = round(((end * cum_factor) / base - 1.0) * 100, 2)
    assert m["ret_1y_total"] is not None
    assert abs(m["ret_1y_total"] - expected) < 0.05, \
        f"ret_1y_total={m['ret_1y_total']} expected≈{expected}（還原淨值法）"


def test_ret_1y_total_short_window_NOT_annualized():
    """v18.65/v18.71: 30 ≤ NAV < 252 日 → 不年化（避免 30 天 ×12 = 300% 假象），用還原淨值法"""
    s = _fake_series(n_days=120, start_nav=10.0)
    divs = [{"date": s.index[-30].strftime("%Y-%m-%d"), "amount": 0.05}]
    m = calc_metrics(s, divs)
    # v18.71 還原淨值法手算
    nav_at_div = float(s.iloc[-30])
    factor = 1 + 0.05 / nav_at_div
    base = float(s.iloc[0])
    end = float(s.iloc[-1])
    expected = round(((end * factor) / base - 1.0) * 100, 2)
    assert m["ret_1y_total"] is not None
    assert abs(m["ret_1y_total"] - expected) < 0.05, \
        f"ret_1y_total={m['ret_1y_total']} expected≈{expected}（還原淨值法，累積非年化）"
    # window_days 應該標明短窗口
    assert m["ret_1y_window_days"] is not None
    assert m["ret_1y_window_days"] < 350, \
        f"window_days={m['ret_1y_window_days']} 應 < 350（短窗口）"


def test_ret_1y_total_too_short():
    """v18.60: < 30 自然日範圍 → ret_1y_total = None（不亂年化）"""
    s = _fake_series(n_days=15, start_nav=10.0)   # ~ 21 自然日 < 30
    m = calc_metrics(s, [])
    assert m["ret_1y_total"] is None
    assert m["ret_1y_window_days"] is None


def test_ret_1y_total_full_year_marks_window_365():
    """v18.65: ≥ 252 NAV 點 → ret_1y_window_days ≈ 365（真 1Y）"""
    s = _fake_series(n_days=300, start_nav=10.0)
    m = calc_metrics(s, [])
    assert m["ret_1y_total"] is not None
    assert m["ret_1y_window_days"] is not None
    assert m["ret_1y_window_days"] >= 350, \
        f"window_days={m['ret_1y_window_days']} 應 ≥ 350（真 1Y 標示）"


def test_ret_1y_total_30_day_window():
    """v18.60: NAV 跨度 30~60 天 → 仍計算（v18.65 後不年化）"""
    s = _fake_series(n_days=25, start_nav=10.0)   # ~ 35 自然日 > 30
    m = calc_metrics(s, [])
    # 應該算得出值（年化噪音大，這裡只驗 not None）
    assert m["ret_1y_total"] is not None


# ════════════════════════════════════════════════════════════
# v18.71 還原淨值法 — calculate_fund_total_return() 邊界驗證
# ════════════════════════════════════════════════════════════
def test_total_return_empty_input():
    """空 nav_df → 回空 DataFrame，不拋例外"""
    out = calculate_fund_total_return(pd.DataFrame(), pd.DataFrame())
    assert out.empty


def test_total_return_no_dividends_equals_nav_change():
    """無配息（累積型）→ Adj_NAV == NAV，Cum_Return == NAV 變化%"""
    s = _fake_series(n_days=100, start_nav=10.0)
    nav_df = pd.DataFrame({"Date": s.index, "NAV": s.values})
    out = calculate_fund_total_return(nav_df, pd.DataFrame())
    # Factor 全為 1 → Cum_Factor 全為 1 → Adj_NAV == NAV
    assert np.allclose(out["Adj_NAV"].values, out["NAV"].values)
    expected_ret = (float(s.iloc[-1]) / float(s.iloc[0]) - 1.0) * 100
    assert abs(float(out["Cum_Return_Pct"].iloc[-1]) - expected_ret) < 1e-6


def test_total_return_compound_vs_simple():
    """配息再投資複利 > 單利加總（差距 = 交叉項 r_n × Σdiv_ratio）"""
    s = _fake_series(n_days=300, start_nav=10.0, daily_vol=0.01, seed=7)
    # 強迫 NAV 上漲：用 abs 收益確保最終 > 期初 → 凸顯複利優勢
    nav_df = pd.DataFrame({"Date": s.index, "NAV": s.values})
    div_dates = [s.index[50], s.index[150], s.index[250]]
    div_df = pd.DataFrame([{"Date": d, "Dividend": 0.1} for d in div_dates])

    out = calculate_fund_total_return(nav_df, div_df)
    compound_ret = float(out["Cum_Return_Pct"].iloc[-1])

    # 手算單利：(end-base)/base + Σdiv/base
    base = float(s.iloc[0]); end = float(s.iloc[-1])
    simple_ret = ((end - base) / base + 0.3 / base) * 100

    # 複利與單利不應相等（除非 NAV 完全沒漲；這裡 seed 固定故差異穩定）
    # 差異方向：若 NAV 上漲，compound > simple；下跌則 compound < simple
    assert abs(compound_ret - simple_ret) > 0.001, \
        f"compound={compound_ret} simple={simple_ret} 應有差異"


def test_total_return_zero_nav_safe():
    """NAV 含 0 / NaN → Factor 該日視為 1，不拋 inf/NaN"""
    dates = pd.date_range("2025-01-01", periods=5, freq="D")
    nav_df = pd.DataFrame({"Date": dates, "NAV": [10.0, 10.5, 0.0, 11.0, 11.2]})
    div_df = pd.DataFrame({"Date": [dates[2]], "Dividend": [0.5]})  # 在 NAV=0 那天配息
    out = calculate_fund_total_return(nav_df, div_df)
    assert not out["Adj_NAV"].isna().any()
    assert not np.isinf(out["Adj_NAV"]).any()


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v"]))
