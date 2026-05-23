"""portfolio_engine.calc_holdings_overlap 單元測試（v18.2 新增）。

測試 4 組對照：
1. 完全相同 holdings → score = 1.0
2. 完全沒重疊 → score = 0.0
3. 半重疊（5/10 持股 + 部分 sector overlap）→ 介於兩者
4. 缺 holdings 但有 sector → 降級為 sector-only
5. 全空 → 回 method=n/a
"""
from services.portfolio_service import calc_holdings_overlap, calc_correlation_matrix


def assert_close(actual: float, expected: float, tol: float = 0.02, msg: str = "") -> None:
    assert abs(actual - expected) <= tol, (
        f"{msg}: actual={actual:.4f}, expected={expected:.4f}"
    )


def test_overlap_identical() -> None:
    """兩檔 holdings 完全一致 → 重疊度 = 1.0。"""
    holdings = [{"name": f"S{i}", "pct": 10} for i in range(10)]
    sectors = [{"name": "科技", "pct": 60}, {"name": "金融", "pct": 40}]
    funds = [
        {"code": "X", "top_holdings": holdings, "sector_alloc": sectors},
        {"code": "Y", "top_holdings": holdings, "sector_alloc": sectors},
    ]
    res = calc_holdings_overlap(funds)
    v = float(res["matrix"].loc["X", "Y"])
    assert_close(v, 1.0, msg="identical")
    assert ("X", "Y", 1.0) in res["shadow_pairs"], "shadow_pairs 應含 (X, Y)"
    print(f"✅ overlap_identical: score = {v:.4f}, method = {res['method']}")


def test_overlap_zero() -> None:
    """兩檔 holdings 完全不重疊 + sector 不重疊 → 重疊度 ≈ 0。"""
    funds = [
        {"code": "A",
         "top_holdings": [{"name": f"S{i}", "pct": 10} for i in range(10)],
         "sector_alloc": [{"name": "科技", "pct": 100}]},
        {"code": "B",
         "top_holdings": [{"name": f"T{i}", "pct": 10} for i in range(10)],
         "sector_alloc": [{"name": "金融", "pct": 100}]},
    ]
    res = calc_holdings_overlap(funds)
    v = float(res["matrix"].loc["A", "B"])
    assert_close(v, 0.0, msg="zero-overlap")
    assert not res["shadow_pairs"], "shadow_pairs 應為空"
    print(f"✅ overlap_zero: score = {v:.4f}")


def test_overlap_half() -> None:
    """半重疊：5/15 持股共用 + 50% 同 sector → score 介於 0 和 1。"""
    common = [{"name": f"C{i}", "pct": 5} for i in range(5)]
    funds = [
        {"code": "A",
         "top_holdings": common + [{"name": f"X{i}", "pct": 5} for i in range(10)],
         "sector_alloc": [{"name": "科技", "pct": 50}, {"name": "金融", "pct": 50}]},
        {"code": "B",
         "top_holdings": common + [{"name": f"Y{i}", "pct": 5} for i in range(10)],
         "sector_alloc": [{"name": "科技", "pct": 50}, {"name": "醫療", "pct": 50}]},
    ]
    res = calc_holdings_overlap(funds)
    v = float(res["matrix"].loc["A", "B"])
    # Jaccard = 5 / (5+10+10) = 0.20； Cosine on sector ≈ 0.5
    # score = 0.20 × 0.6 + 0.5 × 0.4 = 0.32
    assert 0.20 <= v <= 0.45, f"半重疊 score 應在 0.20~0.45 之間，實得 {v:.4f}"
    assert not res["shadow_pairs"], "score 0.32 < 0.70 → 不應入 shadow"
    print(f"✅ overlap_half: score = {v:.4f}（介於 0.20~0.45）")


def test_overlap_sector_only_fallback() -> None:
    """缺 holdings 但有 sector → 降級為 sector cosine。"""
    funds = [
        {"code": "A", "top_holdings": [],
         "sector_alloc": [{"name": "科技", "pct": 80}, {"name": "金融", "pct": 20}]},
        {"code": "B", "top_holdings": [],
         "sector_alloc": [{"name": "科技", "pct": 80}, {"name": "金融", "pct": 20}]},
    ]
    res = calc_holdings_overlap(funds)
    v = float(res["matrix"].loc["A", "B"])
    assert_close(v, 1.0, msg="sector-cosine 完全相同")
    assert res["method"] == "sector", f"method 應為 sector，實得 {res['method']}"
    print(f"✅ overlap_sector_only_fallback: score = {v:.4f}, method = {res['method']}")


def test_overlap_all_missing() -> None:
    """全部基金都缺持股與產業 → method = n/a，matrix = None。"""
    funds = [
        {"code": "A", "top_holdings": [], "sector_alloc": []},
        {"code": "B", "top_holdings": [], "sector_alloc": []},
    ]
    res = calc_holdings_overlap(funds)
    assert res["method"] == "n/a", f"method 應為 n/a，實得 {res['method']}"
    assert res["matrix"] is None, "matrix 應為 None"
    print(f"✅ overlap_all_missing: method = {res['method']}（fallback 觸發）")


# ════════════════════════════════════════════════════════════
# v18.177 calc_correlation_matrix 自適應頻率（修「短 NAV 相關係數=0」假象）
# ════════════════════════════════════════════════════════════
def _mk_series(start: str, end: str, base: float, market, noise_seed: int):
    """合成一條與 market 因子連動的日頻 NAV series。"""
    import numpy as np
    import pandas as pd
    idx = pd.bdate_range(start, end)
    rng = np.random.RandomState(noise_seed)
    rets = market[: len(idx)] + rng.normal(0, 0.002, len(idx))
    return pd.Series(base * (1 + rets).cumprod(), index=idx)


def test_corr_short_nav_not_zero() -> None:
    """短 NAV（~2 個月，卡 fallback）：月底 resample 只剩 2-3 點 → 退化成 NaN/0；
    自適應降頻（週/日）後，兩檔同市場因子基金應算出高相關（>0.8），非 0 假象。"""
    import numpy as np
    import pandas as pd
    idx = pd.bdate_range("2026-03-20", "2026-05-31")   # ~52 營業日（過 >=30 filter）
    market = np.random.RandomState(1).normal(0, 0.01, len(idx))
    s1 = _mk_series("2026-03-20", "2026-05-31", 100.0, market, 11)   # ACDD19
    s2 = _mk_series("2026-03-20", "2026-05-31", 280.0, market, 22)   # ACDD01
    res = calc_correlation_matrix([
        {"code": "ACDD19", "series": s1},
        {"code": "ACDD01", "series": s2},
    ])
    assert res is not None, "短 NAV 不應回 None"
    assert res["freq"] != "月底", f"短 NAV 應降頻離開月底，實得 {res['freq']}"
    v = float(res["matrix"].loc["ACDD19", "ACDD01"])
    assert v > 0.8, f"同市場因子短 NAV 相關應 >0.8（非 0 假象），實得 {v:.4f}"
    print(f"✅ corr_short_nav: freq={res['freq']}, corr={v:.4f}")


def test_corr_long_nav_keeps_monthly() -> None:
    """長歷史（>1 年）：月底 returns 已 ≥6，應維持月底頻率（保留原行為）。"""
    import numpy as np
    import pandas as pd
    idx = pd.bdate_range("2024-01-01", "2026-01-01")
    market = np.random.RandomState(7).normal(0, 0.01, len(idx))
    s1 = _mk_series("2024-01-01", "2026-01-01", 100.0, market, 3)
    s2 = _mk_series("2024-01-01", "2026-01-01", 50.0, market, 4)
    res = calc_correlation_matrix([
        {"code": "A", "series": s1},
        {"code": "B", "series": s2},
    ])
    assert res is not None
    assert res["freq"] == "月底", f"長歷史應維持月底，實得 {res['freq']}"
    print(f"✅ corr_long_nav: freq={res['freq']}")


def test_corr_too_few_funds_returns_none() -> None:
    """有效基金 <2 → None。"""
    import pandas as pd
    idx = pd.bdate_range("2026-04-23", "2026-05-31")
    s = pd.Series(range(len(idx)), index=idx, dtype=float) + 100
    assert calc_correlation_matrix([{"code": "A", "series": s}]) is None
    print("✅ corr_too_few_funds: None")


if __name__ == "__main__":
    test_overlap_identical()
    test_overlap_zero()
    test_overlap_half()
    test_overlap_sector_only_fallback()
    test_overlap_all_missing()
    test_corr_short_nav_not_zero()
    test_corr_long_nav_keeps_monthly()
    test_corr_too_few_funds_returns_none()
    print("\n🎉 全部 calc_holdings_overlap + calc_correlation_matrix 測試通過")
