"""v19.270 D8 #8 F-PROV-1 — calculate_composite_score opt-in provenance side-car。

驗 3 件事:
1. 既有 caller(不傳 provenance_out)行為 100% 不變 — 回 float
2. 新 caller 傳 dict — dict 被填入 sources / fetched_at_latest / contributions / n
3. provenance dict 內 contributions 對應每個 indicator 的 weighted 貢獻
"""
from __future__ import annotations

from services.macro.composite_score import calculate_composite_score


def _make_ind():
    """5 項指標 + provenance attrs。"""
    return {
        "PMI":     {"score": 2.0, "weight": 2.0,
                    "source": "FRED:NAPM",
                    "fetched_at": "2026-06-30T08:00:00+00:00"},
        "VIX":     {"score": -1.0, "weight": 1.0,
                    "source": "Yahoo:^VIX",
                    "fetched_at": "2026-06-30T09:00:00+00:00"},
        "HY_SPREAD": {"score": 0.5, "weight": 2.0,
                      "source": "FRED:BAMLH0A0HYM2",
                      "fetched_at": "2026-06-30T08:30:00+00:00"},
        "CPI":     {"score": 1.0, "weight": 0.5,
                    "source": "FRED:CPIAUCSL",
                    "fetched_at": "2026-06-30T10:00:00+00:00"},
        "BREADTH": {"score": 1.0, "weight": 1.0,
                    "source": "Yahoo:RSP+SPY",
                    "fetched_at": "2026-06-30T09:30:00+00:00"},
    }


class TestBackwardCompatibility:
    def test_no_provenance_param_returns_float(self):
        ind = _make_ind()
        score = calculate_composite_score(ind)
        assert isinstance(score, float)
        # 2*2 + (-1)*1 + 0.5*2 + 1*0.5 + 1*1 = 4 - 1 + 1 + 0.5 + 1 = 5.5
        assert score == 5.5

    def test_explicit_none_returns_float(self):
        ind = _make_ind()
        score = calculate_composite_score(ind, provenance_out=None)
        assert isinstance(score, float)
        assert score == 5.5


class TestProvenanceOptIn:
    def test_provenance_dict_filled_with_sources(self):
        ind = _make_ind()
        prov = {}
        score = calculate_composite_score(ind, provenance_out=prov)
        assert score == 5.5  # 同上,score 不受 provenance 影響
        assert prov["sources"] == [
            "FRED:BAMLH0A0HYM2",
            "FRED:CPIAUCSL",
            "FRED:NAPM",
            "Yahoo:RSP+SPY",
            "Yahoo:^VIX",
        ]

    def test_fetched_at_latest_is_max(self):
        ind = _make_ind()
        prov = {}
        calculate_composite_score(ind, provenance_out=prov)
        # CPI 是 10:00 最新
        assert prov["fetched_at_latest"] == "2026-06-30T10:00:00+00:00"

    def test_contributions_per_indicator(self):
        ind = _make_ind()
        prov = {}
        calculate_composite_score(ind, provenance_out=prov)
        contribs = prov["contributions"]
        assert "PMI" in contribs and contribs["PMI"]["weighted"] == 4.0
        assert contribs["VIX"]["weighted"] == -1.0
        assert contribs["HY_SPREAD"]["weighted"] == 1.0
        assert contribs["CPI"]["weighted"] == 0.5
        assert contribs["BREADTH"]["weighted"] == 1.0

    def test_n_indicators(self):
        ind = _make_ind()
        prov = {}
        calculate_composite_score(ind, provenance_out=prov)
        assert prov["n_indicators"] == 5

    def test_missing_source_skipped_from_sources(self):
        ind = {
            "PMI": {"score": 2, "weight": 1, "source": "FRED:NAPM",
                    "fetched_at": "2026-06-30T08:00:00+00:00"},
            "X": {"score": 1, "weight": 1},  # 無 source/fetched_at
        }
        prov = {}
        calculate_composite_score(ind, provenance_out=prov)
        assert prov["sources"] == ["FRED:NAPM"]
        assert prov["n_indicators"] == 2

    def test_dedup_sources(self):
        ind = {
            "PMI": {"score": 1, "weight": 1, "source": "FRED:NAPM",
                    "fetched_at": "2026-06-30T08:00:00+00:00"},
            "PMI_BACKUP": {"score": 1, "weight": 1, "source": "FRED:NAPM",
                           "fetched_at": "2026-06-30T08:00:00+00:00"},
        }
        prov = {}
        calculate_composite_score(ind, provenance_out=prov)
        assert prov["sources"] == ["FRED:NAPM"]  # 去重

    def test_empty_ind(self):
        prov = {}
        score = calculate_composite_score({}, provenance_out=prov)
        assert score == 0.0
        assert prov["sources"] == []
        assert prov["n_indicators"] == 0
