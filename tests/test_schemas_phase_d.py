"""v19.265 D7 F-SCHEMA-1 Tier 2/3:test stooq + CBOE Series validators。

驗 4 件事(各 source 2 個):
1. 合法 Series(正值 / 升序 / 唯一 + 對應 source prefix)pass
2. 空 Series pass(fallback chain 合法跳關)
3. 錯誤 source prefix raise ValueError
4. 缺 fetched_at raise ValueError

對應 shared/schemas.py:validate_stooq_series / validate_cboe_series
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from shared.schemas import validate_cboe_series, validate_stooq_series


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
