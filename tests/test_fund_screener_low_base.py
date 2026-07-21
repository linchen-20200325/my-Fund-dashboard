"""v19.347 — 「選基金清單」低基期進場點篩選 L2 純函式測試。

守住:
1. compute_low_base 數學式（高點−N×std）+ §1 Fail Loud 邊界:
   - std≈0（NAV 幾乎不動）→ 不判定回 None（不誤判全部低基期）
   - 短樣本 → reliable=False 但仍給值
   - 空 / None / DataFrame 容錯
   - N=2 比 N=1 嚴（門檻更低）
2. screen_funds 濾鏡:低基期 / 不吃本金 / 幣別 / 類別 + 去重 + σ 排序。
"""
from __future__ import annotations

import pandas as pd

from services.fund_screening import (
    LOW_BASE_MIN_POINTS,
    compute_low_base,
    screen_funds,
)


def _series(values: list[float]) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=len(values), freq="D")
    return pd.Series([float(v) for v in values], index=idx)


# 明顯低基期:9 個 100 + 1 個 50 → high=100, std=15.81, cur=50
_LOW_BASE_VALS = [100.0] * 9 + [50.0]
# 在高點:單調上升,cur=high → 非低基期
_AT_HIGH_VALS = [50, 60, 70, 80, 90, 100]


# ── compute_low_base ─────────────────────────────────────
def test_low_base_true_when_current_far_below_peak():
    r = compute_low_base(_series(_LOW_BASE_VALS), n_sigma=1.0, min_points=5)
    assert r["is_low_base"] is True
    assert r["high"] == 100.0 and r["current"] == 50.0
    # σ 深度 = (100-50)/15.8114 = 3.16
    assert r["sigma_below_high"] == 3.16
    assert r["threshold"] is not None and r["current"] <= r["threshold"]


def test_not_low_base_at_peak():
    r = compute_low_base(_series(_AT_HIGH_VALS), n_sigma=1.0, min_points=3)
    assert r["is_low_base"] is False
    assert r["sigma_below_high"] == 0.0  # cur == high


def test_constant_nav_std_zero_is_undetermined_not_fabricated():
    """§1:NAV 幾乎不動 → std≈0 → 不判定（None）,不可誤判成低基期。"""
    r = compute_low_base(_series([10.0] * 100), n_sigma=1.0)
    assert r["is_low_base"] is None
    assert r["threshold"] is None
    assert r["sigma_below_high"] is None
    assert "std" in r["note"] and "無法判定" in r["note"]


def test_short_series_flagged_unreliable_but_still_computes():
    vals = [100.0] * 14 + [50.0]  # n=15 < 60
    r = compute_low_base(_series(vals), n_sigma=1.0, min_points=LOW_BASE_MIN_POINTS)
    assert r["reliable"] is False
    assert r["is_low_base"] is True           # 仍算,只是標可信度低
    assert "可信度低" in r["note"]


def test_empty_and_none_and_bad_type():
    assert compute_low_base(None)["note"] == "無 NAV"
    empty = compute_low_base(pd.Series(dtype=float))
    assert empty["is_low_base"] is None and empty["note"] == "NAV 全空"
    assert compute_low_base(123)["note"] == "NAV 型別非序列"


def test_dataframe_input_squeezed():
    df = pd.DataFrame({"nav": _LOW_BASE_VALS},
                      index=pd.date_range("2024-01-01", periods=len(_LOW_BASE_VALS)))
    r = compute_low_base(df, n_sigma=1.0, min_points=5)
    assert r["is_low_base"] is True and r["current"] == 50.0


def test_n2_is_stricter_than_n1():
    """N=2 門檻 = high−2std < N=1 門檻 = high−1std（更難成立）。"""
    s = _series([100, 90, 80, 95, 88, 92, 85, 91, 60])
    r1 = compute_low_base(s, n_sigma=1.0, min_points=5)
    r2 = compute_low_base(s, n_sigma=2.0, min_points=5)
    assert r2["threshold"] < r1["threshold"]
    # σ 深度與 N 無關
    assert r1["sigma_below_high"] == r2["sigma_below_high"]


def test_lookback_trims_to_window():
    """只看回看窗內:視窗外的舊高點不算。"""
    # 前段超高（1000）+ 後段窗內低變化 → 若吃到舊高會誤判
    vals = [1000.0] * 5 + [100.0] * 9 + [50.0]
    r = compute_low_base(_series(vals), n_sigma=1.0, lookback=10, min_points=5)
    assert r["high"] == 100.0  # 舊 1000 在窗外,未被採計


# ── screen_funds ─────────────────────────────────────────
def _item(code, ccy, cat, eats, vals):
    return {"code": code, "name": f"fund-{code}", "series": _series(vals),
            "currency": ccy, "category": cat, "eats_principal": eats}


def _base_items():
    return [
        _item("F1", "USD", "平衡型", False, _LOW_BASE_VALS),   # 低基期+不吃 → 入選
        _item("F2", "USD", "平衡型", False, _AT_HIGH_VALS),    # 非低基期 → 剔除
        _item("F3", "TWD", "股票型", True, _LOW_BASE_VALS),    # 吃本金 → 剔除
        _item("F4", "USD", "平衡型", None, _LOW_BASE_VALS),    # 不吃狀態未知 → 剔除
    ]


def test_screen_default_keeps_only_low_base_and_no_eat():
    rows = screen_funds(_base_items(), n_sigma=1.0, min_points=5)
    codes = [r["code"] for r in rows]
    assert codes == ["F1"]


def test_screen_only_no_eat_false_includes_unknown_and_eaters():
    rows = screen_funds(_base_items(), n_sigma=1.0, min_points=5, only_no_eat=False)
    codes = {r["code"] for r in rows}
    assert codes == {"F1", "F3", "F4"}  # 全部低基期,不再濾吃本金


def test_screen_currency_filter():
    rows = screen_funds(_base_items(), n_sigma=1.0, min_points=5,
                        only_no_eat=False, currencies={"USD"})
    assert {r["code"] for r in rows} == {"F1", "F4"}  # F3 是 TWD 被濾


def test_screen_category_filter():
    rows = screen_funds(_base_items(), n_sigma=1.0, min_points=5,
                        only_no_eat=False, categories={"平衡型"})
    assert {r["code"] for r in rows} == {"F1", "F4"}  # F3 股票型被濾


def test_screen_dedup_same_code():
    items = _base_items() + [_item("F1", "USD", "平衡型", False, _LOW_BASE_VALS)]
    rows = screen_funds(items, n_sigma=1.0, min_points=5)
    assert [r["code"] for r in rows] == ["F1"]  # 同 code 一列


def test_screen_sorted_by_sigma_depth_desc():
    # σ 深度 = (high-cur)/std,與「跌幅大小」無關（單一離群值標準化距離只看樣本數）,
    # 要更深需「多數貼近高點、cur 只略降」→ std 小、相對距離大。
    # F5:19 個 100 + 1 個 90 → σ≈4.47 > F1(9 個 100+1 個 50)的 σ≈3.16。
    deep = _item("F5", "USD", "平衡型", False, [100.0] * 19 + [90.0])
    rows = screen_funds([_base_items()[0], deep], n_sigma=1.0, min_points=5)
    assert [r["code"] for r in rows] == ["F5", "F1"]
    assert rows[0]["sigma_below_high"] > rows[1]["sigma_below_high"]
