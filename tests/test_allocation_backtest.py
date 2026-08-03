"""配置回測引擎(services/allocation_backtest.py,v19.427)。

驗:①原幣→台幣換算(USD/TWD/未知)②tiers→權重歸一 ③再平衡日(月底不引未來)
④指標 golden ⑤3 個最兇輸入(不重疊史 / 停售基金 / S1↔S2 極性)⑥反 lookahead(餵未來不改過去權重)
⑦property 掃描(權重和=1 / 成本單調 / S0 cost0 = 買進持有)。§1 誠實 + §2.3 PIT。
"""
import numpy as np
import pandas as pd

from services.allocation_backtest import (
    _sigma_rank_at,
    backtest_allocations,
    build_aligned_matrices,
    rebalance_dates,
    strategy_weights_at,
    tiers_to_weights,
    to_twd_total_return_series,
)
from services.portfolio_performance import metrics_from_return_series, performance_metrics

_D = pd.date_range("2021-01-04", periods=520, freq="B")


def _gbm(mu, sig, n, seed):
    rng = np.random.default_rng(seed)
    return 100.0 * np.exp(np.cumsum(rng.normal(mu, sig, n)))


def _series(mu, sig, seed, n=520):
    return pd.Series(_gbm(mu, sig, n, seed), index=_D[:n])


def _fx(base=30.0, drift=0.0, sig=0.03, n=520, seed=7):
    rng = np.random.default_rng(seed)
    return pd.Series(base + np.cumsum(rng.normal(drift, sig, n)), index=_D[:n]).clip(lower=1.0)


# ── ① 原幣 → 台幣換算 ─────────────────────────────────────
def test_to_twd_usd_multiplies_fx():
    nav = _series(0.0003, 0.01, seed=1, n=300)
    fx = _fx(n=300)
    out = to_twd_total_return_series(nav, "USD", fx)
    assert out is not None and len(out) >= 2
    # 每點 ≈ nav × 對齊匯率(backward);抽末點驗證量綱(TWD = 原幣×TWD/USD)
    last_fx = float(fx.loc[:out.index[-1]].iloc[-1])
    assert abs(float(out.iloc[-1]) - float(nav.loc[out.index[-1]]) * last_fx) < 1e-6


def test_to_twd_twd_passthrough():
    nav = _series(0.0003, 0.01, seed=2, n=200)
    out = to_twd_total_return_series(nav, "台幣", None)   # 中文幣別 → 正規化 TWD
    assert out is not None
    pd.testing.assert_series_equal(out, nav.astype(float), check_names=False)


def test_to_twd_unknown_ccy_none():
    nav = _series(0.0003, 0.01, seed=3, n=200)
    assert to_twd_total_return_series(nav, "EUR", _fx(n=200)) is None   # 非 USD/TWD → None(§1)
    assert to_twd_total_return_series(nav, "USD", None) is None          # USD 但無 FX → None


# ── ② tiers → 權重 ───────────────────────────────────────
def test_tiers_to_weights_sum1_and_tilt():
    w = tiers_to_weights({"A": "buy", "B": "sell", "C": "watch"}, 1 / 3)
    assert abs(sum(w.values()) - 1.0) < 1e-12
    assert w["A"] > w["C"] > w["B"] > 0                     # buy > watch > sell,皆 >0


def test_tiers_all_sell_still_valid():
    w = tiers_to_weights({"A": "sell", "B": "sell"}, 0.5)   # 全賣仍歸一(不歸零→有效組合)
    assert abs(sum(w.values()) - 1.0) < 1e-12 and all(v > 0 for v in w.values())


def test_tiers_empty_none():
    assert tiers_to_weights({}, 0.5) is None


# ── ③ 再平衡日 ───────────────────────────────────────────
def test_rebalance_dates_month_ends_no_future():
    rd = rebalance_dates(_D[:120])
    assert rd[0] == _D[0]                                   # 首日納入為初始配置
    assert all(d in set(_D) for d in rd)                   # 全為實際交易日(不引入未來/假日)
    assert rd == sorted(set(rd))                           # 升冪去重
    # 每月僅一個再平衡日(月底最後交易日)
    months = pd.DatetimeIndex(rd).to_period("M")
    assert len(months) == len(set(months)) or rd[0].to_period("M") == rd[1].to_period("M")


# ── ④ 指標 golden ────────────────────────────────────────
def test_metrics_from_return_series_golden_constant():
    r = pd.Series([0.001] * 252, index=_D[:252])
    m = metrics_from_return_series(r)
    exp_cagr = (1.001 ** 252 - 1.0) * 100.0                # n=252 → 幾何年化 = 1.001^252 − 1
    assert abs(m["cagr_pct"] - round(exp_cagr, 2)) < 0.02
    assert m["max_drawdown_pct"] == 0.0 and m["calmar"] is None   # 無回撤 → Calmar None(不除零)
    assert m["ann_vol_pct"] == 0.0                          # 常數報酬 → σ=0


def test_metrics_short_series_blank():
    m = metrics_from_return_series(pd.Series([0.01]))
    assert m["cagr_pct"] is None and m["sharpe"] is None and m["n_days"] == 1


# ── ⑤ 最兇輸入 1:不重疊歷史 ──────────────────────────────
def test_nonoverlapping_histories_not_ok():
    a = pd.Series(_gbm(0.0003, 0.01, 200, 11), index=pd.date_range("2021-01-04", periods=200, freq="B"))
    b = pd.Series(_gbm(0.0003, 0.01, 200, 12), index=pd.date_range("2023-06-01", periods=200, freq="B"))
    _fxidx = pd.date_range("2021-01-04", periods=900, freq="B")
    fx = pd.Series(30.0 + np.cumsum(np.random.default_rng(7).normal(0, 0.03, 900)), index=_fxidx).clip(lower=1.0)
    res = backtest_allocations({"A": a, "B": b}, {"A": "USD", "B": "USD"}, fx_series=fx)
    # 共同交易日空 → twd 矩陣 None → 誠實不回測(§1);理由為「無足夠可回測基金/樣本太少」任一
    assert res["ok"] is False and res["reason"] and ("樣本" in res["reason"] or "可回測" in res["reason"])


# ── ⑤ 最兇輸入 2:停售(NAV 走平後留白)基金不崩潰 ───────────
def test_halted_fund_no_crash_finite():
    live = _series(0.0004, 0.012, seed=21, n=400)
    halted = _series(0.0004, 0.012, seed=22, n=400).copy()
    halted.iloc[200:] = float(halted.iloc[200])            # 後半走平(停更)
    fx = _fx(n=400)
    res = backtest_allocations({"L": live, "H": halted}, {"L": "USD", "H": "USD"}, fx_series=fx)
    assert res["ok"] is True
    for sid in res["ranking"]:
        m = res["results"][sid]["metrics"]
        assert m["n_days"] > 0 and np.isfinite(m["max_drawdown_pct"])   # 有限,不 NaN 爆掉


# ── ⑤ 最兇輸入 2b:σ=0 走平基金 → 誠實 None,不捏造 SELL(稽核 v19.427 HIGH)──
def test_sigma_zero_flat_fund_not_fabricated_sell():
    flat = pd.Series([50.0] * 300, index=_D[:300])       # 完全走平(停售/清算)→ σ_abs=0
    assert _sigma_rank_at(flat, _D[299]) is None          # §1:σ=0 → None,不回未定義的 0.0
    twd_df = pd.DataFrame({"F": flat})
    _, sig = strategy_weights_at("S3", _D[299], {"F": flat}, twd_df, None)
    assert sig["F"]["nav_level"] == "unknown" and sig["F"]["tier"] == "watch"   # 不得判 sell


# ── ⑤ 最兇輸入 3:S1 ↔ S2 是真極性翻轉(非 no-op)───────────
def test_s1_s2_polarity_is_true_flip():
    # L 深跌(低基期)、H 走高(高基期);FX 近期走低 → 台幣強(strong_twd)
    L = pd.Series(np.linspace(100, 62, 320) + np.sin(np.arange(320)) * 0.4, index=_D[:320])
    H = pd.Series(np.linspace(100, 150, 320) + np.sin(np.arange(320)) * 0.4, index=_D[:320])
    fx = pd.Series(np.linspace(33, 29, 320) + np.sin(np.arange(320)) * 0.05, index=_D[:320])
    orig = {"L": L, "H": H}
    twd_df = pd.DataFrame({"L": L, "H": H})                 # 僅用 .columns
    t = _D[319]
    _, s1 = strategy_weights_at("S1", t, orig, twd_df, fx)
    _, s2 = strategy_weights_at("S2", t, orig, twd_df, fx)
    # 匯率位階:S1 = strong_twd,S2 = 反向 weak_twd(真翻轉)
    assert s1["L"]["fx_label"] == "strong_twd"
    assert s2["L"]["fx_label"] == "weak_twd"
    # L 低基期:S1(低+台幣強)→ buy;S2(低+台幣弱)→ 非 buy
    assert s1["L"]["nav_level"] == "low"
    assert s1["L"]["tier"] == "buy" and s2["L"]["tier"] != "buy"


# ── ⑥ 反 lookahead:餵更長(含未來)序列不改過去某日權重 ───────
def test_pit_future_data_does_not_change_past_weight():
    full = _series(0.0002, 0.011, seed=31, n=400)
    fx_full = _fx(n=400)
    t = _D[250]                                            # 過去某再平衡日
    twd_df = pd.DataFrame({"X": full})
    # 只餵到 t 的序列 vs 餵完整序列(含 t 之後)—— 同一 t 的權重/訊號須相同
    _, sig_short = strategy_weights_at("S1", t, {"X": full.loc[:t]}, twd_df, fx_full.loc[:t])
    _, sig_long = strategy_weights_at("S1", t, {"X": full}, twd_df, fx_full)
    assert sig_short["X"]["sigma_rank"] == sig_long["X"]["sigma_rank"]
    assert sig_short["X"]["fx_label"] == sig_long["X"]["fx_label"]
    assert sig_short["X"]["tier"] == sig_long["X"]["tier"]


# ── ⑦ property 掃描:strategy_weights_at 權重恆歸一且非負 ────
def test_property_strategy_weights_sum_to_one():
    for seed in range(12):
        rng = np.random.default_rng(seed)
        codes = ["A", "B", "C", "D"]
        orig = {c: pd.Series(_gbm(rng.normal(0, 3e-4), abs(rng.normal(0.01, 3e-3)) + 1e-3,
                                   360, seed * 10 + i), index=_D[:360])
                for i, c in enumerate(codes)}
        twd_df = pd.DataFrame({c: orig[c] for c in codes})
        fx = _fx(drift=rng.normal(0, 0.01), seed=seed + 100, n=360)
        for sid in ("S0", "S1", "S2", "S3"):
            w, _ = strategy_weights_at(sid, _D[359], orig, twd_df, fx)
            assert abs(sum(w.values()) - 1.0) < 1e-9
            assert all(v >= 0 for v in w.values())


# ── ⑦ property:換手成本單調(成本↑ → 切換策略 CAGR 不增)────
def test_property_cost_monotonic():
    nav = {c: _series(0.0003 + i * 1e-4, 0.011 + i * 1e-3, seed=40 + i, n=460)
           for i, c in enumerate(["A", "B", "C", "D"])}
    ccy = {"A": "USD", "B": "USD", "C": "USD", "D": "TWD"}
    fx = _fx(n=460)
    cheap = backtest_allocations(nav, ccy, fx_series=fx, cost_bps=0.0, fx_spread_bps=0.0)
    dear = backtest_allocations(nav, ccy, fx_series=fx, cost_bps=200.0, fx_spread_bps=200.0)
    for sid in ("S1", "S2", "S3"):                          # 切換策略:成本高 → CAGR ≤(不增)
        c0 = cheap["results"][sid]["metrics"]["cagr_pct"]
        c1 = dear["results"][sid]["metrics"]["cagr_pct"]
        if c0 is not None and c1 is not None:
            assert c1 <= c0 + 1e-6


# ── ⑦ property:S0(cost0)= 等權買進持有(對帳 performance_metrics)──
def test_s0_zero_cost_equals_equal_weight_buyhold():
    nav = {c: _series(0.0003, 0.011, seed=50 + i, n=430) for i, c in enumerate(["A", "B", "C"])}
    ccy = {c: "TWD" for c in nav}                           # 台幣計價 → twd 序列 = 原幣,單純對帳
    res = backtest_allocations(nav, ccy, fx_series=None, cost_bps=0.0, fx_spread_bps=0.0)
    s0 = res["results"]["S0"]["metrics"]
    ref = performance_metrics(nav, {c: 1.0 for c in nav})   # 等權固定權重日再平衡
    assert abs(s0["cagr_pct"] - ref["ann_return_pct"]) < 0.05
    assert abs(s0["max_drawdown_pct"] - ref["max_drawdown_pct"]) < 0.05


# ── 對齊 / 排除誠實 ──────────────────────────────────────
def test_build_matrices_excludes_non_usd_twd_loudly():
    nav = {"A": _series(0.0003, 0.01, 61, 300), "B": _series(0.0003, 0.01, 62, 300)}
    _, twd_df, included, excluded, _flags, foreign = build_aligned_matrices(
        nav, {"A": "USD", "B": "EUR"}, _fx(n=300))
    assert "A" in included and "B" not in included
    assert any(e["code"] == "B" and "匯率" in e["reason"] for e in excluded)   # 誠實排除 + 理由


def test_full_backtest_actions_and_verdict_shape():
    nav = {c: _series(0.0003, 0.011, seed=70 + i, n=440) for i, c in enumerate(["A", "B", "C", "D"])}
    ccy = {"A": "USD", "B": "USD", "C": "美元", "D": "TWD"}
    res = backtest_allocations(nav, ccy, fx_series=_fx(n=440))
    assert res["ok"] and set(res["ranking"]) == {"S0", "S1", "S2", "S3", "S4"}
    assert res["winner"] == res["ranking"][0]
    assert abs(sum(res["actions"]["target_weights_pct"].values()) - 100.0) < 0.1
    assert "current_signal_snapshot" in res and set(res["current_signal_snapshot"]) <= set(nav)
    assert "s1_sharpe" in res["verdict_s1_vs_s2"]
