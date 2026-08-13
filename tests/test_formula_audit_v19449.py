"""v19.449 公式稽核 HIGH 修正 — 回歸測試。

逐條對應 4 隻稽核 agent 的 HIGH finding:
- H1(配息排序):非 MoneyDJ 來源配息可能舊→新,divs[:n] 取到最舊筆 → 年化配息率算錯。
"""
from __future__ import annotations

import pandas as pd

from services.fund_service import calc_metrics


def _flat_nav_series(nav: float = 10.0, days: int = 400) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=days, freq="D")
    return pd.Series([nav] * days, index=idx)


def test_annual_div_rate_uses_newest_dividends_when_list_oldest_first():
    """H1:配息「舊→新」排列時,年化配息率應反映**近期**(調降後)配息,而非最舊筆。

    造一檔月配基金:2024 年每次配 0.60(舊)、2025 年降到 0.30(新),
    以**最舊在前**的順序傳入(模擬 FundClear/Cnyes 未排序來源)。NAV 固定 10。
      - 修正前(取 divs[:12] = 最舊 12 筆 0.60)→ adr = 0.60×12/10×100 = 72%(錯,假吃本金)
      - 修正後(排序後取最新 12 筆 0.30)→ adr = 0.30×12/10×100 = 36%(對)
    """
    divs = []
    for _m in range(24):                                  # 24 個月,最舊在前
        _dt = pd.Timestamp("2024-01-15") + pd.DateOffset(months=_m)
        _amt = 0.60 if _m < 12 else 0.30                  # 前 12 月 0.60、後 12 月 0.30
        divs.append({"date": _dt.strftime("%Y-%m-%d"), "amount": _amt})

    m = calc_metrics(_flat_nav_series(), divs)
    adr = m.get("annual_div_rate")
    assert adr is not None
    # 關鍵:應接近 36(近期),絕不可是 72(最舊)
    assert 30 <= adr <= 42, f"年化配息率應反映近期 0.30 配息(~36%),實際 {adr}(疑取到最舊筆)"


# ── H2:總經 z-pct 反向指標 key 對不上 → 失業率/初領飆高被當偏多 ──

def test_zpct_reverse_keys_use_real_indicator_keys():
    """H2:反向集合必須用真正的 indicator key(JOBLESS/UNEMPLOYMENT),非 FRED ID。"""
    from services.macro.us_indicators import _ZPCT_REVERSE_KEYS
    assert "UNEMPLOYMENT" in _ZPCT_REVERSE_KEYS and "JOBLESS" in _ZPCT_REVERSE_KEYS
    assert "ICSA" not in _ZPCT_REVERSE_KEYS and "UNRATE" not in _ZPCT_REVERSE_KEYS
    # 同屬高=壞、原本漏掉的也補上
    for _k in ("CONT_CLAIMS", "SAHM", "SLOOS", "INFL_EXP_5Y"):
        assert _k in _ZPCT_REVERSE_KEYS, f"{_k} 應在反向集合(高=壞)"


def test_high_unemployment_scored_bearish_in_zpct():
    """H2:失業率飆到遠高於歷史均值(衰退)→ z-pct 貢獻應**偏空**(<0.5),非偏多。"""
    from services.macro.us_indicators import calc_macro_phase_zpct
    idx = pd.date_range("2019-01-31", periods=70, freq="ME")
    s = pd.Series([4.0] * 69 + [8.0], index=idx)          # 長期 4%,近月飆 8%
    res = calc_macro_phase_zpct({"UNEMPLOYMENT": {"value": 8.0, "series": s}})
    assert res["status"] == "ok"
    _sub = res["sub_pcts"]["UNEMPLOYMENT"]
    assert _sub < 0.5, f"高失業應偏空(<0.5),實際 {_sub}(符號未翻轉 = 把衰退當偏多)"


# ── H3:組合績效跨幣別未換匯 → 美元基金匯率損益被漏掉 ──

def test_portfolio_returns_captures_fx_for_usd_fund():
    """H3:USD 基金淨值 +10% 但 USDTWD −10% → TWD basis 實為 −1%。

    無換匯(舊行為):把 USD NAV +10% 全額計入 → 組合 ~+5%(高估)。
    換匯(修正):B 的 TWD basis = 1.1×0.9−1 = −1% → 組合 ~−0.5%。
    """
    from services.portfolio_performance import portfolio_returns
    idx = pd.bdate_range("2025-01-01", periods=11)
    nav = {
        "A": pd.Series([10.0] * 11, index=idx),                        # TWD 基金,0%
        "B": pd.Series([10.0 + 0.1 * i for i in range(11)], index=idx),  # USD 基金,10→11 (+10%)
    }
    fx = pd.Series([30.0 - 0.3 * i for i in range(11)], index=idx)      # USDTWD 30→27 (−10%)
    w = {"A": 1.0, "B": 1.0}

    port_nofx, *_ = portfolio_returns(nav, w)
    ret_nofx = float((1 + port_nofx).prod() - 1) * 100
    port_fx, *_ = portfolio_returns(nav, w, ccy_by_code={"A": "TWD", "B": "USD"}, fx_series=fx)
    ret_fx = float((1 + port_fx).prod() - 1) * 100

    assert ret_nofx > 3, f"無換匯應把 USD NAV +10% 計入(~+5%),實際 {ret_nofx:.2f}"
    assert ret_fx < 1, f"換匯後應反映匯率拖累(~−0.5%),實際 {ret_fx:.2f}"
    assert ret_fx < ret_nofx - 3, f"換匯應顯著降低報酬,nofx={ret_nofx:.2f} fx={ret_fx:.2f}"


# ════════════════════════════════════════════════════════════════
# MEDIUM 修正回歸(M1 影子負相關 / M2 換股排名量綱 / M3 手動含息分母 /
#          M4 score≤weight / M5 benchmark TWD / item6 空幣別排除)
# ════════════════════════════════════════════════════════════════

def test_m1_shadow_flags_only_positive_correlation():
    """M1:強**負**相關(互相避險=分散有效)不該被標影子基金;強正相關才是影子。"""
    import numpy as np

    from services.portfolio_service import calc_correlation_matrix
    idx = pd.bdate_range("2025-01-01", periods=90)
    ra = np.array([0.012, -0.011] * 45)
    navA = pd.Series(100 * np.cumprod(1 + ra), index=idx)
    navB = pd.Series(100 * np.cumprod(1 - ra), index=idx)     # 反向 → corr ≈ −1
    res_neg = calc_correlation_matrix([{"code": "A", "series": navA}, {"code": "B", "series": navB}])
    assert res_neg is not None
    assert not any({p[0], p[1]} == {"A", "B"} for p in res_neg["shadow_pairs"]), "強負相關不該標影子"
    res_pos = calc_correlation_matrix([{"code": "A", "series": navA}, {"code": "C", "series": navA * 1.0}])
    assert any({p[0], p[1]} == {"A", "C"} for p in res_pos["shadow_pairs"]), "強正相關應標影子"


def test_m2_replacement_ranking_not_return_dominated():
    """M2:同類換股「品質」排名不該被報酬項獨大 → 高 Sharpe/Sortino 但報酬略低者應勝出。"""
    from services.switch_strategy import replacement_candidate
    _hi_quality = {"基金類別": "股票", "Sharpe 1Y": 1.5, "1Y 含息 %": 8.0, "Sortino": 2.0,
                   "費用率 %": 1.0, "策略燈號": "🟢", "吃本金燈號 (1Y · MK)": "🟢 健康", "code": "GOOD"}
    _hi_return = {"基金類別": "股票", "Sharpe 1Y": 0.6, "1Y 含息 %": 12.0, "Sortino": 0.8,
                  "費用率 %": 1.0, "策略燈號": "🟢", "吃本金燈號 (1Y · MK)": "🟢 健康", "code": "CHASE"}
    _pick = replacement_candidate("股票", [_hi_return, _hi_quality])
    assert _pick is not None and _pick.get("code") == "GOOD", "風險調整更佳者應勝(非純追報酬)"


def test_m3_manual_total_return_denominator():
    """M3:含息報酬率 = (期末−期初+年配息)/期初(分母一致用期初)。"""
    from services.fund_service import calc_health_from_manual
    out = calc_health_from_manual(nav_current=110.0, nav_1y_ago=100.0, div_per_unit=0.5, div_freq=12)
    # (110−100+6)/100 = 16.0%(舊式分母不一致會得 15.45%)
    assert abs(out["total_return_pct"] - 16.0) < 0.05, out["total_return_pct"]


def test_m5_policy_benchmark_converts_spx_to_twd():
    """M5:非台幣基金 benchmark 應把 SPX(USD)換成 TWD basis 再比。"""
    from services.portfolio_csv import policy_benchmark_1y
    h = [{"policy": "P", "currency": "美元", "invest_twd": 100000}]
    # SPX +10% USD、USDTWD +5% → TWD basis = 1.1×1.05−1 = 15.5%
    r_fx = policy_benchmark_1y(h, spx_1y_pct=10.0, twii_1y_pct=8.0, usdtwd_1y_pct=5.0)
    assert abs(r_fx["P"] - 15.5) < 0.1, r_fx["P"]
    r_nofx = policy_benchmark_1y(h, spx_1y_pct=10.0, twii_1y_pct=8.0)     # 向後相容
    assert abs(r_nofx["P"] - 10.0) < 0.1, r_nofx["P"]


def test_item6_empty_currency_excluded_not_usd():
    """H3 驗證 item6:空/None 幣別 → 排除(回 None),不可矇成 USD 捏造匯率損益。"""
    from services.allocation_backtest import to_twd_total_return_series
    idx = pd.bdate_range("2025-01-01", periods=10)
    nav = pd.Series([10.0 + 0.1 * i for i in range(10)], index=idx)
    fx = pd.Series([30.0] * 10, index=idx)
    assert to_twd_total_return_series(nav, "", fx) is None
    assert to_twd_total_return_series(nav, None, fx) is None
    assert to_twd_total_return_series(nav, "TWD", fx) is not None
    assert to_twd_total_return_series(nav, "USD", fx) is not None
