"""回歸網 — v19.318:MK 買賣點 σ v3.2「回歸中樞 ± kσ,σ=近1年淨值統計標準差」。

沿革:
- v3.0 用 wb07 年化波動率 → 3σ 常超出區間、買賣點永遠觸不到(user「怎麼可能差異那麼大」)。
- v3.1(v19.313)改區間基準 (年高-年低)/3,但「買錨年高、賣錨年低」使 買1=賣2、買2=賣1
  數學重疊,6 條線塌成 4 條(user「標準差的圖還沒有修好」)。
- v3.2(user 選 A+B):B=σ 改「近1年淨值統計標準差」(真 standard deviation,隨實際波動縮放);
  A=以「回歸中樞(近1年均值)」為中心 ± kσ 對稱佈局 → 6 條線天然不重疊、對稱。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fund_fetcher import calc_metrics  # 走 root shim,避開 services.fund_service 直接 import 的循環

TRADING_DAYS = 252


def _make_series(n: int = 504) -> pd.Series:
    """造 2 年正弦振盪序列(中樞 90 ± 10),σ 明確非零、非退化。"""
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    vals = 90.0 + 10.0 * np.sin(np.linspace(0, 8 * np.pi, n))
    return pd.Series(vals, index=idx)


def _expected_center_sigma(s: pd.Series) -> tuple[float, float]:
    win = s.dropna()
    if len(win) > TRADING_DAYS:
        win = win.tail(TRADING_DAYS)
    return round(float(win.mean()), 4), round(float(win.std(ddof=1)), 4)


def test_sigma_is_real_statistical_std():
    """σ = 近1年淨值統計標準差;買/賣點 = 中樞 ∓ kσ。"""
    s = _make_series()
    m = calc_metrics(s, [])
    center, sigma = _expected_center_sigma(s)
    assert sigma > 0
    assert abs(m["buy1"] - (center - sigma)) < 0.02, f"買1 應=中樞-1σ={center - sigma}, 實得 {m['buy1']}"
    assert abs(m["sell1"] - (center + sigma)) < 0.02
    assert abs(m["buy3"] - (center - 3 * sigma)) < 0.05
    assert abs(m["sell3"] - (center + 3 * sigma)) < 0.05


def test_bands_no_overlap_and_symmetric():
    """v19.318 核心回歸:修 v3.1 的買賣重疊 bug(買1=賣2、買2=賣1 → 塌成 4 條)。"""
    s = _make_series()
    m = calc_metrics(s, [])
    vals = [m["buy3"], m["buy2"], m["buy1"], m["sell1"], m["sell2"], m["sell3"]]
    # 6 條線必須相異(v3.1 會塌成 4 個相異值)
    assert len(set(vals)) == 6, f"6 條買賣線應相異,實得 {sorted(set(vals))}"
    # 嚴格單調遞增
    assert vals == sorted(vals), f"買賣線非單調遞增:{vals}"
    # v3.1 的兩個重疊點:買1≠賣2、買2≠賣1
    assert m["buy1"] != m["sell2"] and m["buy2"] != m["sell1"]
    # 對稱:買k + 賣k = 2×中樞
    center, _ = _expected_center_sigma(s)
    for bk, sk in [("buy1", "sell1"), ("buy2", "sell2"), ("buy3", "sell3")]:
        assert abs((m[bk] + m[sk]) / 2 - center) < 0.02, f"{bk}/{sk} 未對稱於中樞 {center}"


def test_tiers_equal_spacing():
    """三檔等距 = σ。"""
    s = _make_series()
    m = calc_metrics(s, [])
    _, sigma = _expected_center_sigma(s)
    assert abs((m["buy1"] - m["buy2"]) - sigma) < 0.02
    assert abs((m["sell2"] - m["sell1"]) - sigma) < 0.02
