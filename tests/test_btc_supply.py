"""回歸網 — v19.320:BTC 流通量改「時變（減半發行時程）」取代原「~固定」常數 19_800_000。

user 檢查 `services/liquidity_engine.py` BTC 供給量常數 → 選 B(改真實供給)。
以 Bitcoin 減半時程純函式推算(無 I/O、可重現 §5),取代 stale 常數。
"""
from __future__ import annotations

import pandas as pd

from services.liquidity_engine import _btc_circulating_supply


def test_supply_monotonic_and_under_cap():
    """供給隨時間單調不減,且永不超過 21M 協定上限。"""
    idx = pd.date_range("2021-01-01", "2026-07-05", freq="MS")
    s = _btc_circulating_supply(idx)
    assert len(s) == len(idx)
    assert s.is_monotonic_increasing
    assert (s <= 21_000_000).all(), f"供給不可超過 21M,max={s.max()}"
    assert (s > 18_000_000).all()


def test_supply_at_halving_anchors():
    """減半錨點供給值正確(協定事實)。"""
    s = _btc_circulating_supply(pd.DatetimeIndex(["2020-05-11", "2024-04-20"]))
    assert abs(s.iloc[0] - 18_375_000) < 1.0, f"3rd halving 應≈18.375M,實得 {s.iloc[0]}"
    assert abs(s.iloc[1] - 19_687_500) < 1.0, f"4th halving 應≈19.6875M,實得 {s.iloc[1]}"


def test_supply_post_halving_daily_rate():
    """第 4 次減半後日發行 450 BTC/日(3.125×144):+100 天 = +45,000 BTC。"""
    s = _btc_circulating_supply(pd.DatetimeIndex(["2024-04-20", "2024-07-29"]))  # +100 天
    assert abs((s.iloc[1] - s.iloc[0]) - 100 * 450.0) < 1.0


def test_supply_recent_in_sane_range():
    """2026 中的流通量應落在 ~19.9M–20.2M(比舊常數 19.8M 更貼近實況)。"""
    s = _btc_circulating_supply(pd.DatetimeIndex(["2026-07-05"]))
    assert 19_900_000 <= s.iloc[0] <= 20_200_000, f"2026 供給異常:{s.iloc[0]}"


def test_supply_handles_tz_aware_index():
    """tz-aware index(yfinance 有時帶時區)不可炸,長度對齊。"""
    idx = pd.date_range("2025-01-01", periods=5, freq="D", tz="UTC")
    s = _btc_circulating_supply(idx)
    assert len(s) == 5 and s.notna().all()
