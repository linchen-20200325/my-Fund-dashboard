"""基金型態分類 震盪/成長(services/fund_type_classifier.py,v19.428)。

驗:ER 定義 + 邊界(趨勢→成長 / 震盪→震盪 / 灰帶→類別打破 / 短史+全平→None)+ override 優先 + property。
"""
import numpy as np
import pandas as pd

from services.fund_type_classifier import (
    GROWTH,
    RANGE,
    classify_fund_type,
    efficiency_ratio,
)

_D = pd.date_range("2022-01-03", periods=400, freq="B")


def _s(vals):
    return pd.Series([float(v) for v in vals], index=_D[: len(vals)])


# ── ER 定義 ──────────────────────────────────────────────
def test_er_pure_trend_is_one():
    s = _s(np.linspace(100, 180, 200))          # 單調上升 → 路徑=淨移動 → ER=1
    assert abs(efficiency_ratio(s) - 1.0) < 1e-9


def test_er_oscillation_near_zero():
    s = _s(100 + 5 * np.sin(np.arange(200) * 0.5))   # 來回震盪 → 淨移動≈0 → ER→0
    assert efficiency_ratio(s) < 0.10


def test_er_flat_series_none():
    assert efficiency_ratio(_s([50.0] * 100)) is None   # 路徑=0 → None(§4.4)


def test_er_short_history_none():
    assert efficiency_ratio(_s(np.linspace(100, 110, 40))) is None   # <60 點 → None


# ── 分類 ─────────────────────────────────────────────────
def test_classify_growth_trend():
    r = classify_fund_type(_s(np.linspace(100, 200, 200) + np.sin(np.arange(200)) * 0.5))
    assert r["type"] == GROWTH and r["method"] == "er" and r["er"] >= 0.35


def test_classify_range_oscillation():
    r = classify_fund_type(_s(100 + 6 * np.sin(np.arange(220) * 0.4)))
    assert r["type"] == RANGE and r["method"] == "er" and r["er"] <= 0.20


def _sawtooth():
    """+2 / −1 鋸齒 → net=80, path=240 → ER=1/3≈0.333(落灰帶 0.20~0.35)。"""
    seq = [100.0]
    for _ in range(80):
        seq.append(seq[-1] + 2.0)
        seq.append(seq[-1] - 1.0)
    return _s(seq)


def test_gray_zone_equity_to_growth():
    r = classify_fund_type(_sawtooth(), category="股票型-科技")
    assert 0.20 < r["er"] < 0.35 and r["method"] == "er+bucket" and r["type"] == GROWTH


def test_gray_zone_bond_to_range():
    r = classify_fund_type(_sawtooth(), category="全球債券")
    assert r["method"] == "er+bucket" and r["type"] == RANGE   # 非股票 → 震盪


def test_insufficient_history_type_none():
    r = classify_fund_type(_s(np.linspace(100, 110, 30)))
    assert r["type"] is None and r["method"] == "insufficient"


# ── override 優先 ────────────────────────────────────────
def test_override_wins_over_er():
    trend = _s(np.linspace(100, 200, 200))       # ER≈1 本應成長
    r = classify_fund_type(trend, override=RANGE)
    assert r["type"] == RANGE and r["method"] == "override" and r["er"] is not None


def test_invalid_override_ignored():
    r = classify_fund_type(_s(np.linspace(100, 200, 200)), override="亂填")
    assert r["method"] == "er" and r["type"] == GROWTH   # 無效 override 忽略,走 ER


# ── property:ER 恆在 [0,1] ───────────────────────────────
def test_property_er_bounded():
    for seed in range(15):
        rng = np.random.default_rng(seed)
        s = _s(100 * np.exp(np.cumsum(rng.normal(0, 0.01, 200))))
        er = efficiency_ratio(s)
        assert er is None or (0.0 <= er <= 1.0 + 1e-12)
