"""services/backtest_service.py — 回測引擎 Service Layer
（v11.0 C-16 從 backtest_engine.py 搬入）

功能：
  - 模擬策略歷史績效 (backtest_portfolio)
  - 與 Benchmark 比較 (compare_with_benchmark)
  - 計算 Sharpe / Sortino / MaxDD / Calmar (calc_performance_metrics)
  - 單基金快回測 (quick_backtest)

v18.17（2026-05-12）：
  - 移除 backtest_portfolio 內無效的 iterrows 死碼（與向量化等價）
  - weights.sum()==0 防護
  - compare_with_benchmark 加 freq 參數（預設 12 維持後相容）
  - docstring 對齊實際行為（承認 ME 在月頻輸入時等同 buy-and-hold；
    TODO：日頻輸入下真正的月底再平衡）

v18.110（2026-05-16）：
  - calc_performance_metrics 改階梯式門檻：
    n<2 回 {}；n>=2 至少回 total/ann/MDD + is_partial 旗標；n>=3 加 σ-based 指標
  - 修 Tab4「3 期月底 → KPI 全 —%」user-visible bug

v11.0 分層歸位：本檔屬於 Service Layer，純業務計算（純 numpy/pandas，零 I/O）。
向後相容：根目錄 backtest_engine.py 保留 shim re-export，既有 caller 零修改。
"""
import pandas as pd
import numpy as np
from typing import Dict


# ── 基礎回測 ──────────────────────────────────────────────────────────────
def backtest_portfolio(nav_df: pd.DataFrame,
                       weights: pd.Series,
                       rebalance: str = "ME") -> pd.DataFrame:
    """
    參數：
        nav_df    : NAV DataFrame（columns=基金代碼；index=DatetimeIndex）
        weights   : 各基金目標權重（Series；自動歸一化；全 0 視為均等分配）
        rebalance : 'ME' / 'QE' / None
                    ⚠️ 當前實作下三者等價於「買入持有 + (選擇性) 期末聚合」。
                    若 nav_df 為月頻（Tab4 預設），ME = 月聚合 = no-op；
                    真正的再平衡（每期重置權重）為 TODO。
    回傳：
        DataFrame: equity_curve / portfolio_return / drawdown
    """
    # 權重歸一化（防 sum==0）
    w_sum = float(weights.sum())
    if w_sum == 0:
        w = pd.Series([1.0 / len(weights)] * len(weights), index=weights.index)
    else:
        w = weights / w_sum

    returns = nav_df.pct_change().dropna()

    # 向量化（與原 iterrows loop 等價、100x 更快）
    port_ret = (returns * w).sum(axis=1)

    # 月聚合（注意：這只是日頻 → 月頻的聚合，並非真正再平衡）
    if rebalance == "ME":
        port_ret = port_ret.resample("ME").apply(lambda x: (1 + x).prod() - 1)
    elif rebalance == "QE":
        port_ret = port_ret.resample("QE").apply(lambda x: (1 + x).prod() - 1)

    equity_curve = (1 + port_ret).cumprod()
    rolling_max  = equity_curve.cummax()
    drawdown     = (equity_curve - rolling_max) / rolling_max

    return pd.DataFrame({
        "equity_curve":     equity_curve,
        "portfolio_return": port_ret,
        "drawdown":         drawdown,
    })


# ── 績效指標計算 ───────────────────────────────────────────────────────────
def calc_performance_metrics(equity_curve: pd.Series,
                             returns: pd.Series,
                             rf: float = 0.02,
                             freq: int = 12) -> Dict:
    """
    計算投資組合績效指標。
    freq=12 代表月頻，freq=252 代表日頻。

    v18.110 階梯式門檻（修 Tab4「3 期月底 → KPI 全 —%」的 user-visible bug）：
      - returns < 2 期 → 回 {}（樣本太少完全不可信）
      - returns >= 2 期 → 至少回 total_return + ann_return + max_drawdown + periods
      - returns >= 3 期 → 加上 ann_vol / sharpe / sortino / calmar（σ-based 指標）

    metrics 內含 `is_partial` 旗標標明是否為短樣本（UI 可據此顯 warning）。
    """
    n = len(returns)
    if n < 2:
        return {}

    total_return  = float(equity_curve.iloc[-1] - 1)
    ann_return    = float((1 + total_return) ** (freq / n) - 1)

    # Max Drawdown 對 >=2 期就能算（只看 cummax 軌跡）
    rolling_max = equity_curve.cummax()
    drawdown    = (equity_curve - rolling_max) / rolling_max
    max_dd      = round(float(drawdown.min()), 4)

    out = {
        "total_return":  round(total_return * 100, 2),
        "ann_return":    round(ann_return * 100, 2),
        "max_drawdown":  round(max_dd * 100, 2),
        "periods":       n,
        "is_partial":    n < 3,
    }

    if n < 3:
        # 短樣本：σ 為 0/不穩 → 不算 Sharpe/Sortino/Calmar，保持 key 缺席讓 UI 顯 —
        return out

    ann_vol       = float(returns.std() * np.sqrt(freq))
    sharpe        = round((ann_return - rf) / ann_vol, 4) if ann_vol > 0 else 0.0

    # Sortino（下行標準差）
    downside = returns[returns < 0]
    ann_downside = float(downside.std() * np.sqrt(freq)) if len(downside) > 0 else 0.0
    sortino  = round((ann_return - rf) / ann_downside, 4) if ann_downside > 0 else 0.0

    # Calmar
    calmar = round(ann_return / abs(max_dd), 4) if max_dd != 0 else 0.0

    out.update({
        "ann_vol":  round(ann_vol * 100, 2),
        "sharpe":   sharpe,
        "sortino":  sortino,
        "calmar":   calmar,
    })
    return out


# ── Benchmark 比較 ─────────────────────────────────────────────────────────
def compare_with_benchmark(port_curve: pd.Series,
                           bench_curve: pd.Series,
                           freq: int = 12) -> Dict:
    """
    比較策略 vs Benchmark
    freq=12 月頻、freq=252 日頻。
    回傳：超額報酬 / Tracking Error / Information Ratio
    """
    # 對齊時間軸
    common = port_curve.index.intersection(bench_curve.index)
    if len(common) < 3:
        return {"error": "資料不足，無法比較"}

    p = port_curve.loc[common]
    b = bench_curve.loc[common]

    p_ret = p.pct_change().dropna()
    b_ret = b.pct_change().dropna()

    excess      = p_ret - b_ret
    alpha       = round(float(excess.mean() * freq) * 100, 2)
    tracking_err= round(float(excess.std() * np.sqrt(freq)) * 100, 2)
    info_ratio  = round(alpha / tracking_err, 4) if tracking_err > 0 else 0.0

    p_total = round(float(p.iloc[-1] / p.iloc[0] - 1) * 100, 2)
    b_total = round(float(b.iloc[-1] / b.iloc[0] - 1) * 100, 2)

    return {
        "port_total_return":   p_total,
        "bench_total_return":  b_total,
        "alpha_ann":           alpha,
        "tracking_error":      tracking_err,
        "information_ratio":   info_ratio,
    }


# ── 快速單基金回測包裝 ─────────────────────────────────────────────────────
def quick_backtest(nav_series: pd.Series, freq: int = 12) -> Dict:
    """
    對單一基金淨值序列做快速回測，回傳績效指標。
    nav_series：每月（或每日）淨值序列。少於 4 期回 error。
    """
    if len(nav_series) < 4:
        return {"error": "淨值資料不足（需至少 4 期）"}

    returns     = nav_series.pct_change().dropna()
    equity      = (1 + returns).cumprod()
    metrics     = calc_performance_metrics(equity, returns, rf=0.02, freq=freq)
    metrics["periods"] = len(returns)
    return metrics
