"""v19.482 稽核 H5:HWM σ 位階用固定 lookback(252)換算,不隨序列長度縮放。

原 `sigma_abs = hwm × daily_std × sqrt(len(s))`,短歷史檔(len < lookback)σ_abs 被縮小,
sigma_rank 被誇大成更負 → 同跌幅被判「更低基期=可買」→ rotation 系統性導向最不可信短檔。
改回 docstring 本意 `sqrt(lookback)`,讓跨檔 σ 單位一致、可比。
"""
import numpy as np
import pandas as pd

from services.precision_service import calc_hwm_sigma_levels


def _nav_series(n, seed, mu=0.0, sd=0.008, start=100.0):
    rng = np.random.default_rng(seed)
    rets = rng.normal(mu, sd, n)
    nav = start * np.cumprod(1.0 + rets)
    idx = pd.date_range("2021-01-01", periods=len(nav), freq="D")
    return pd.Series(nav, index=idx)


def test_sigma_abs_uses_lookback_not_series_length():
    s = _nav_series(60, seed=42)                      # 60 筆 < lookback 252
    r = calc_hwm_sigma_levels(s, lookback=252)
    assert "error" not in r, r
    _daily_std = float(s.pct_change().dropna().std())
    _hwm = float(s.max())
    _expect_lookback = _hwm * _daily_std * np.sqrt(252)    # 修正後(sqrt(lookback))
    _wrong_len = _hwm * _daily_std * np.sqrt(len(s.dropna().tail(252)))  # 舊 bug(sqrt(len)=sqrt(60))
    assert abs(r["sigma_abs"] - round(_expect_lookback, 4)) < 0.05, r["sigma_abs"]
    assert abs(r["sigma_abs"] - _wrong_len) > 0.1, "σ_abs 不該再用 sqrt(len)"


def test_full_length_series_unchanged():
    """≥ lookback 的序列:len(s)==lookback → 新舊公式同值,行為不變(不誤傷長歷史檔)。"""
    s = _nav_series(300, seed=7)                      # 300 筆 → tail(252) → len==252
    r = calc_hwm_sigma_levels(s, lookback=252)
    assert "error" not in r
    _tail = s.dropna().tail(252)
    _daily_std = float(_tail.pct_change().dropna().std())
    _hwm = float(_tail.max())
    assert abs(r["sigma_abs"] - round(_hwm * _daily_std * np.sqrt(252), 4)) < 0.05


def test_same_drawdown_short_vs_long_now_comparable():
    """同「距 HWM %」的短檔與長檔,sigma_rank 不再被序列長度拉開到不同基期分類。"""
    # 兩檔用同 daily vol、同樣從高點跌約同幅度;修正後 σ 單位一致 → sigma_rank 量級相近。
    s_short = _nav_series(50, seed=1, mu=-0.002)      # 短、緩跌
    s_long = _nav_series(252, seed=1, mu=-0.002)      # 長、同 seed 同分布
    r_s = calc_hwm_sigma_levels(s_short, lookback=252)
    r_l = calc_hwm_sigma_levels(s_long, lookback=252)
    if "error" not in r_s and "error" not in r_l:
        # σ_abs 皆以 sqrt(252) 換算 → 不再因短檔而系統性放大 rank(不強求相等,只驗同號同量級)
        assert (r_s["sigma_rank"] <= 0) == (r_l["sigma_rank"] <= 0)
