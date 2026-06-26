"""tests/test_schemas_phase_b2_fund_nav.py — A1 Phase B 後續守衛(v19.162)

SPEC §18 / CLAUDE.md §3.1 — fund NAV fetcher 出口 schema(pd.Series + attrs)。

本檔守:
1. FundNavSchema 對合法 fetch_nav 輸出 pass
2. 對 illegal data 立擋:
   - NAV 含 NaN / 0 / 負值
   - index 重複 / 非 monotonic
3. attrs.source 必須以多源 prefix 之一開頭(MoneyDJ/FundClear/TDCC/...)
4. attrs.fetched_at 必須是 ISO
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest
from pandera.errors import SchemaError

from shared.schemas import FundNavSchema, validate_fund_nav, _FUND_NAV_SOURCE_PREFIXES


def _good_nav(n: int = 5, source_prefix: str = "MoneyDJ:tcbbankfund:wf01:fetch_nav") -> pd.Series:
    """合法 fund NAV 輸出 fixture(Series + attrs)。"""
    base = _dt.datetime(2026, 1, 1)
    idx = pd.DatetimeIndex([base + _dt.timedelta(days=i) for i in range(n)])
    s = pd.Series([10.5 + i * 0.02 for i in range(n)], index=idx, dtype=float, name="NAV")
    s.attrs["source"] = source_prefix
    s.attrs["fetched_at"] = "2026-06-26T12:00:00+00:00"
    return s


# ════════════════════════════════════════════════════════════════
# 1. 合法輸入 pass
# ════════════════════════════════════════════════════════════════
class TestSchemaPassesValidInput:
    def test_basic_pass(self):
        s = _good_nav()
        out = validate_fund_nav(s)
        assert out is not None
        assert len(out) == 5

    def test_empty_series_passes(self):
        """fetch 失敗回空 Series → validate_fund_nav 直接 pass(對齊 caller fallback)。"""
        empty = pd.Series(dtype=float, name="NAV")
        out = validate_fund_nav(empty)
        assert out is empty

    @pytest.mark.parametrize("source_prefix", [
        "MoneyDJ:tcbbankfund:wf01:fetch_nav",
        "FundClear:GetFundNAV",
        "TDCC:nav_history",
        "Cnyes:fund_nav_api",
        "Morningstar:UK:timeseries:abc",
        "AllianzGI:host1",
        "JPMorgan:am.jpmorgan.com/tw:nav_direct",
        "Franklin:franklintempleton.com.tw:nav_direct",
        "FundRich:api:v1/funds:host2",
        "SITCA:IN2213.aspx",
        "InsuranceSubdomain:tl.moneydj.com:yp004002:1",
        "BankPlatform:domain:taiwanlife_mobile",
        "GitHubActions:cache/nav/123.json",
        "Yahoo:5y00",
    ])
    def test_all_allowed_source_prefixes_pass(self, source_prefix):
        s = _good_nav(source_prefix=source_prefix)
        validate_fund_nav(s)  # no raise


# ════════════════════════════════════════════════════════════════
# 2. 違法 values 立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidValues:
    def test_nan_value_rejected(self):
        s = _good_nav()
        s.iloc[2] = float("nan")
        with pytest.raises(SchemaError):
            validate_fund_nav(s)

    def test_zero_value_rejected(self):
        """NAV 不應為 0(停售/清算應為 NaN 而非 0)。"""
        s = _good_nav()
        s.iloc[1] = 0.0
        with pytest.raises(SchemaError):
            validate_fund_nav(s)

    def test_negative_value_rejected(self):
        s = _good_nav()
        s.iloc[0] = -1.5
        with pytest.raises(SchemaError):
            validate_fund_nav(s)


# ════════════════════════════════════════════════════════════════
# 3. 違法 index 立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidIndex:
    def test_duplicate_index_rejected(self):
        s = _good_nav()
        idx = list(s.index)
        idx[-1] = idx[-2]
        s.index = pd.DatetimeIndex(idx)
        with pytest.raises(SchemaError):
            validate_fund_nav(s)

    def test_non_monotonic_index_rejected(self):
        s = _good_nav()
        s.index = s.index[::-1]
        with pytest.raises(SchemaError):
            validate_fund_nav(s)


# ════════════════════════════════════════════════════════════════
# 4. 違法 attrs(provenance)立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidAttrs:
    def test_unknown_source_prefix_rejected(self):
        """source 非允許清單(SSOT 命名約定外)→ ValueError。"""
        s = _good_nav(source_prefix="UnknownVendor:foo")
        with pytest.raises(ValueError, match="attrs.source"):
            validate_fund_nav(s)

    def test_missing_source_entirely_rejected(self):
        s = _good_nav()
        del s.attrs["source"]
        with pytest.raises(ValueError, match="attrs.source"):
            validate_fund_nav(s)

    def test_non_iso_fetched_at_rejected(self):
        s = _good_nav()
        s.attrs["fetched_at"] = "20260626"  # 無 'T'
        with pytest.raises(ValueError, match="attrs.fetched_at"):
            validate_fund_nav(s)

    def test_missing_fetched_at_rejected(self):
        s = _good_nav()
        del s.attrs["fetched_at"]
        with pytest.raises(ValueError, match="attrs.fetched_at"):
            validate_fund_nav(s)


# ════════════════════════════════════════════════════════════════
# 5. allowed prefixes 清單契約守
# ════════════════════════════════════════════════════════════════
class TestAllowedPrefixesContract:
    def test_prefix_list_is_non_empty(self):
        assert len(_FUND_NAV_SOURCE_PREFIXES) >= 5

    def test_each_prefix_ends_with_colon(self):
        for p in _FUND_NAV_SOURCE_PREFIXES:
            assert p.endswith(":"), f"prefix '{p}' 須以 ':' 結尾"

    def test_no_duplicate_prefixes(self):
        assert len(set(_FUND_NAV_SOURCE_PREFIXES)) == len(_FUND_NAV_SOURCE_PREFIXES)
