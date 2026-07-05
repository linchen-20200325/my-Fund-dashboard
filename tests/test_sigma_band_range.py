"""回歸網 — v19.313:MK 買賣點 σ 改「區間基準」(年高-年低)/3。

真 bug(user 回報「怎麼可能差異那麼大」):原 v3.0 用 wb07「一年標準差」= 年化波動率,
`std_amt = 年高 × 年化σ%`,3σ 可達 ~18%,常「超出」2 年高低區間 → 買3/賣3 掉出真實區間
(買3 比史低還低,永遠觸不到)。改 (年高-年低)/3 後:買3=年低、賣3=年高,3 檔均分區間,
band 必落在真實區間內、訊號一定觸得到。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fund_fetcher import calc_metrics  # 走 root shim,避開 services.fund_service 直接 import 的循環


def _make_series(hi: float = 100.0, lo: float = 80.0, n: int = 504):
    """造 2 年(504 交易日)序列,明確 max=hi / min=lo(lo→hi→lo)。"""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    half = n // 2
    vals = np.concatenate([np.linspace(lo, hi, half), np.linspace(hi, lo, n - half)])
    return pd.Series(vals, index=idx), float(max(vals)), float(min(vals))


def test_sigma_band_within_year_range():
    s, hi, lo = _make_series()
    m = calc_metrics(s, [])
    assert m.get("buy3") is not None and m.get("sell3") is not None
    # 買3 ≈ 年低、賣3 ≈ 年高(區間兩端)
    assert abs(m["buy3"] - lo) < 0.5, f"買3 應≈年低 {lo}, 實得 {m['buy3']}"
    assert abs(m["sell3"] - hi) < 0.5, f"賣3 應≈年高 {hi}, 實得 {m['sell3']}"
    # 關鍵回歸:買3 不可低於史低、賣3 不可高於史高(原 annualized σ bug 會掉出去)
    assert m["buy3"] >= lo - 0.01, f"買3 {m['buy3']} 掉出區間下緣 {lo}"
    assert m["sell3"] <= hi + 0.01, f"賣3 {m['sell3']} 掉出區間上緣 {hi}"


def test_sigma_band_tiers_equal_spacing():
    s, hi, lo = _make_series()
    m = calc_metrics(s, [])
    sigma = (hi - lo) / 3.0
    # 每檔間距 = σ = (年高-年低)/3
    assert abs((m["buy1"] - m["buy2"]) - sigma) < 0.02
    assert abs((m["sell2"] - m["sell1"]) - sigma) < 0.02
