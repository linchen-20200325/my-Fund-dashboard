"""portfolio_engine.calc_holdings_overlap 單元測試（v18.2 新增）。

測試 4 組對照：
1. 完全相同 holdings → score = 1.0
2. 完全沒重疊 → score = 0.0
3. 半重疊（5/10 持股 + 部分 sector overlap）→ 介於兩者
4. 缺 holdings 但有 sector → 降級為 sector-only
5. 全空 → 回 method=n/a
"""
from services.portfolio_service import calc_holdings_overlap


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


if __name__ == "__main__":
    test_overlap_identical()
    test_overlap_zero()
    test_overlap_half()
    test_overlap_sector_only_fallback()
    test_overlap_all_missing()
    print("\n🎉 全部 5 項 calc_holdings_overlap 測試通過")
