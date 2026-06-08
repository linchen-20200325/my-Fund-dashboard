"""v19.27 Dividend Health Discoverer — 純函式單測。

驗證重點：
1. KNOWN_OVERSEAS_FUNDS 結構合法
2. rank_by_health 4 桶分發 + 桶內排序
3. summarize_ranking 健康占比
4. flatten_ranking 順序
"""
from __future__ import annotations

import pytest

from services.dividend_health_discoverer import (
    KNOWN_OVERSEAS_FUNDS,
    flatten_ranking,
    known_fund_codes,
    known_fund_meta,
    rank_by_health,
    summarize_ranking,
)


# ════════════════════════════════════════════════════════════════
# §1 KNOWN_OVERSEAS_FUNDS 結構
# ════════════════════════════════════════════════════════════════
class TestKnownOverseasFunds:
    def test_non_empty(self):
        assert len(KNOWN_OVERSEAS_FUNDS) >= 5

    def test_each_entry_has_required_fields(self):
        required = {"code", "name", "brand", "region", "dividend_freq"}
        for f in KNOWN_OVERSEAS_FUNDS:
            assert required.issubset(set(f.keys())), f"缺欄位：{f}"
            assert all(isinstance(f[k], str) and f[k] for k in required)

    def test_codes_unique(self):
        codes = [f["code"] for f in KNOWN_OVERSEAS_FUNDS]
        assert len(codes) == len(set(codes)), "code 重複"

    def test_known_fund_codes_helper(self):
        codes = known_fund_codes()
        assert isinstance(codes, list)
        assert len(codes) == len(KNOWN_OVERSEAS_FUNDS)
        assert "TLZF9" in codes

    def test_known_fund_meta_lookup(self):
        meta = known_fund_meta("TLZF9")
        assert meta is not None
        assert "安聯" in meta["name"]

    def test_known_fund_meta_case_insensitive(self):
        # code 應大小寫不敏感
        assert known_fund_meta("tlzf9") is not None
        assert known_fund_meta(" TLZF9 ") is not None

    def test_known_fund_meta_unknown_returns_none(self):
        assert known_fund_meta("NOPE999") is None
        assert known_fund_meta("") is None


# ════════════════════════════════════════════════════════════════
# §2 rank_by_health 4 桶分發
# ════════════════════════════════════════════════════════════════
def _enriched(code: str, ret_1y_total: float | None, annual_div_rate: float | None,
              **extra) -> dict:
    """工廠：模擬 fetch_fund_multi_source 後 enriched fund dict。"""
    f = {
        "fund_code": code,
        "fund_name": f"Test {code}",
        "metrics": {
            "ret_1y_total": ret_1y_total,
            "annual_div_rate": annual_div_rate,
        },
    }
    f.update(extra)
    return f


class TestRankByHealth:
    def test_buckets_have_all_4_keys(self):
        buckets = rank_by_health([])
        assert set(buckets.keys()) == {"健康", "警示", "吃本金", "資料不足"}

    def test_classifies_correctly(self):
        funds = [
            _enriched("A", 8.0, 5.0),    # 健康
            _enriched("B", 4.5, 5.0),    # 警示（差距 0.5%）
            _enriched("C", 1.0, 5.0),    # 吃本金（差距 4%）
            _enriched("D", None, 5.0),   # 資料不足
        ]
        buckets = rank_by_health(funds)
        assert [f["fund_code"] for f in buckets["健康"]] == ["A"]
        assert [f["fund_code"] for f in buckets["警示"]] == ["B"]
        assert [f["fund_code"] for f in buckets["吃本金"]] == ["C"]
        assert [f["fund_code"] for f in buckets["資料不足"]] == ["D"]

    def test_sort_by_ret_within_bucket(self):
        funds = [
            _enriched("Low", 6.0, 4.0),     # 健康，含息 6
            _enriched("High", 12.0, 4.0),   # 健康，含息 12
            _enriched("Mid", 9.0, 4.0),     # 健康，含息 9
        ]
        buckets = rank_by_health(funds)
        codes = [f["fund_code"] for f in buckets["健康"]]
        assert codes == ["High", "Mid", "Low"]

    def test_injects_emoji_fields(self):
        f = _enriched("A", 8.0, 5.0)
        buckets = rank_by_health([f])
        out = buckets["健康"][0]
        assert out["_div_health_light"] == "健康"
        assert out["_div_health_emoji"] == "🟢"

    def test_skips_non_dict(self):
        buckets = rank_by_health(["bad", None, _enriched("A", 8.0, 5.0)])  # type: ignore[list-item]
        assert len(buckets["健康"]) == 1

    def test_warn_gap_override(self):
        # 差距 1.5% — warn_gap=2 → 🟡，warn_gap=1 → 🔴
        f = _enriched("X", 3.5, 5.0)
        b1 = rank_by_health([f], warn_gap=2.0)
        assert b1["警示"] and not b1["吃本金"]
        b2 = rank_by_health([f], warn_gap=1.0)
        assert b2["吃本金"] and not b2["警示"]


# ════════════════════════════════════════════════════════════════
# §3 summarize_ranking
# ════════════════════════════════════════════════════════════════
class TestSummarizeRanking:
    def test_counts_and_healthy_pct(self):
        buckets = rank_by_health([
            _enriched("A", 8.0, 5.0),    # 健康
            _enriched("B", 8.0, 5.0),    # 健康
            _enriched("C", 1.0, 5.0),    # 吃本金
            _enriched("D", None, 5.0),   # 資料不足
        ])
        summary = summarize_ranking(buckets)
        assert summary["n_total"] == 4
        assert summary["counts"]["健康"] == 2
        assert summary["counts"]["吃本金"] == 1
        assert summary["counts"]["資料不足"] == 1
        assert summary["healthy_pct"] == 50.0

    def test_zero_total_safe(self):
        buckets = rank_by_health([])
        summary = summarize_ranking(buckets)
        assert summary["n_total"] == 0
        assert summary["healthy_pct"] == 0.0

    def test_emoji_complete(self):
        buckets = rank_by_health([])
        summary = summarize_ranking(buckets)
        assert summary["emoji"]["健康"] == "🟢"
        assert summary["emoji"]["吃本金"] == "🔴"


# ════════════════════════════════════════════════════════════════
# §4 flatten_ranking 順序
# ════════════════════════════════════════════════════════════════
class TestFlattenRanking:
    def test_order_healthy_first(self):
        buckets = rank_by_health([
            _enriched("Eat", 1.0, 5.0),   # 吃本金
            _enriched("Heal", 8.0, 5.0),  # 健康
            _enriched("Warn", 4.5, 5.0),  # 警示
            _enriched("Na",   None, 5.0), # 資料不足
        ])
        flat = flatten_ranking(buckets)
        codes = [f["fund_code"] for f in flat]
        assert codes == ["Heal", "Warn", "Eat", "Na"]

    def test_empty_buckets(self):
        buckets = rank_by_health([])
        assert flatten_ranking(buckets) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
