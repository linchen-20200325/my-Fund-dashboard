"""v19.265 D7 + v19.267 D8 F-SCHEMA-1 Tier 2/3 validators。

D7 覆蓋 stooq + CBOE Series 驗證(v19.265)。
D8 #5/#6 加 AAII dict + DefiLlama Series 驗證(v19.267)。

對應 shared/schemas.py:
- validate_stooq_series / validate_cboe_series(D7)
- validate_defillama_series / validate_aaii_sentiment(D8)
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared.schemas import (
    validate_aaii_sentiment,
    validate_cboe_series,
    validate_defillama_series,
    validate_stooq_series,
)


def _make_series(source: str, *, populated: bool = True, with_fetched_at: bool = True):
    if not populated:
        return pd.Series(dtype=float)
    idx = pd.to_datetime(["2026-06-25", "2026-06-26", "2026-06-27"])
    s = pd.Series([18.5, 19.2, 17.8], index=idx, dtype="float64")
    s.attrs["source"] = source
    if with_fetched_at:
        s.attrs["fetched_at"] = "2026-06-30T10:00:00+00:00"
    return s


class TestStooqValidator:
    def test_legal_passes(self):
        s = _make_series("stooq:^vix3m")
        out = validate_stooq_series(s)
        assert out is s

    def test_legal_headerless_passes(self):
        s = _make_series("stooq:^cpc:headerless")
        out = validate_stooq_series(s)
        assert out is s

    def test_empty_passes(self):
        s = _make_series("stooq:dummy", populated=False)
        assert validate_stooq_series(s) is s

    def test_wrong_prefix_raises(self):
        s = _make_series("Yahoo:^GSPC")
        with pytest.raises(ValueError, match="stooq:"):
            validate_stooq_series(s)

    def test_missing_fetched_at_raises(self):
        s = _make_series("stooq:^vix3m", with_fetched_at=False)
        with pytest.raises(ValueError, match="fetched_at"):
            validate_stooq_series(s)

    def test_negative_value_raises_pandera(self):
        idx = pd.to_datetime(["2026-06-25", "2026-06-26"])
        s = pd.Series([18.5, -1.0], index=idx, dtype="float64")
        s.attrs["source"] = "stooq:^vix3m"
        s.attrs["fetched_at"] = "2026-06-30T10:00:00+00:00"
        with pytest.raises(Exception):  # pandera SchemaError
            validate_stooq_series(s)


class TestCboeValidator:
    def test_legal_passes(self):
        s = _make_series("CBOE:cdn:daily_prices:VIX3M_History.csv")
        out = validate_cboe_series(s)
        assert out is s

    def test_empty_passes(self):
        s = _make_series("CBOE:dummy", populated=False)
        assert validate_cboe_series(s) is s

    def test_wrong_prefix_raises(self):
        s = _make_series("stooq:^vix3m")
        with pytest.raises(ValueError, match="CBOE:"):
            validate_cboe_series(s)

    def test_missing_fetched_at_raises(self):
        s = _make_series("CBOE:cdn:daily_prices:VIX3M_History.csv", with_fetched_at=False)
        with pytest.raises(ValueError, match="fetched_at"):
            validate_cboe_series(s)

    def test_non_monotonic_index_raises(self):
        idx = pd.to_datetime(["2026-06-27", "2026-06-25", "2026-06-26"])
        s = pd.Series([18.5, 17.8, 19.2], index=idx, dtype="float64")
        s.attrs["source"] = "CBOE:cdn:daily_prices:VIX3M_History.csv"
        s.attrs["fetched_at"] = "2026-06-30T10:00:00+00:00"
        with pytest.raises(Exception):  # pandera SchemaError
            validate_cboe_series(s)


class TestRiskRadarIntegration:
    def test_safe_wrappers_return_empty_on_violation(self):
        """schema 違反時 _safe_validate_* 應回空 Series 而非 raise。"""
        from services.risk_radar import _safe_validate_cboe, _safe_validate_stooq
        bad = _make_series("Yahoo:^GSPC")  # 錯 prefix
        assert _safe_validate_stooq(bad).empty
        assert _safe_validate_cboe(bad).empty

    def test_safe_wrappers_pass_through_legal(self):
        from services.risk_radar import _safe_validate_cboe, _safe_validate_stooq
        s_stooq = _make_series("stooq:^vix3m")
        s_cboe = _make_series("CBOE:cdn:daily_prices:VIX3M_History.csv")
        assert _safe_validate_stooq(s_stooq) is s_stooq
        assert _safe_validate_cboe(s_cboe) is s_cboe


# ════════════════════════════════════════════════════════════════
# v19.267 D8 #6 — DefiLlama stablecoin mcap
# ════════════════════════════════════════════════════════════════
class TestDefiLlamaValidator:
    def test_legal_passes(self):
        s = _make_series("DefiLlama:stablecoincharts:total_circulating")
        assert validate_defillama_series(s) is s

    def test_empty_passes(self):
        s = _make_series("DefiLlama:dummy", populated=False)
        assert validate_defillama_series(s) is s

    def test_wrong_prefix_raises(self):
        s = _make_series("Yahoo:^GSPC")
        with pytest.raises(ValueError, match="DefiLlama:"):
            validate_defillama_series(s)

    def test_missing_fetched_at_raises(self):
        s = _make_series("DefiLlama:dummy", with_fetched_at=False)
        with pytest.raises(ValueError, match="fetched_at"):
            validate_defillama_series(s)


# ════════════════════════════════════════════════════════════════
# v19.267 D8 #5 — AAII sentiment dict
# ════════════════════════════════════════════════════════════════
def _aaii_success(source="AAII:sentimentsurvey", bull=40.5, bear=25.2,
                  with_fetched_at=True, unit="%"):
    d = {"value": bull - bear, "unit": unit, "bull": bull, "bear": bear,
         "date": "weekly", "url_used": "https://...", "source": source}
    if with_fetched_at:
        d["fetched_at"] = "2026-06-30T10:00:00+00:00"
    return d


def _aaii_failure(err="all fallback failed", source="AAII:sentimentsurvey",
                  with_fetched_at=True):
    d = {"_err": err, "source": source}
    if with_fetched_at:
        d["fetched_at"] = "2026-06-30T10:00:00+00:00"
    return d


class TestAaiiValidator:
    def test_legal_success_passes(self):
        d = _aaii_success()
        assert validate_aaii_sentiment(d) is d

    def test_legal_failure_passes(self):
        d = _aaii_failure()
        assert validate_aaii_sentiment(d) is d

    def test_none_passes(self):
        assert validate_aaii_sentiment(None) is None

    def test_empty_dict_passes(self):
        assert validate_aaii_sentiment({}) == {}

    def test_wrong_source_prefix_raises(self):
        d = _aaii_success(source="Yahoo:^GSPC")
        with pytest.raises(ValueError, match="AAII:"):
            validate_aaii_sentiment(d)

    def test_missing_fetched_at_raises(self):
        d = _aaii_success(with_fetched_at=False)
        with pytest.raises(ValueError, match="fetched_at"):
            validate_aaii_sentiment(d)

    def test_bull_out_of_range_raises(self):
        d = _aaii_success(bull=150)
        with pytest.raises(ValueError, match="bull"):
            validate_aaii_sentiment(d)

    def test_bear_negative_raises(self):
        d = _aaii_success(bear=-5)
        with pytest.raises(ValueError, match="bear"):
            validate_aaii_sentiment(d)

    def test_wrong_unit_raises(self):
        d = _aaii_success(unit="bp")
        with pytest.raises(ValueError, match="unit"):
            validate_aaii_sentiment(d)

    def test_non_string_err_raises(self):
        d = _aaii_failure(err=123)  # type: ignore
        with pytest.raises(ValueError, match="_err"):
            validate_aaii_sentiment(d)

    def test_success_path_missing_bull_raises(self):
        d = {"value": 15.3, "bear": 25, "unit": "%",
             "source": "AAII:sentimentsurvey",
             "fetched_at": "2026-06-30T10:00:00+00:00"}
        with pytest.raises(ValueError, match="value/bull/bear"):
            validate_aaii_sentiment(d)
