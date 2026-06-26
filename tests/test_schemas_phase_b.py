"""tests/test_schemas_phase_b.py — Pandera Phase B 守衛(v19.161)

SPEC §18 / CLAUDE.md §3.1 — fetch_yf_close 出口 schema(pd.Series + attrs)。

本檔守:
1. YahooCloseSchema 對合法 fetch_yf_close 輸出 pass
2. 對 illegal data 立擋:
   - index 重複 / 非 monotonic
   - values 含 NaN / 0 / 負值
   - attrs.source 缺前綴 / attrs.fetched_at 缺 'T'
3. validate_yf_close wrapper 空 Series 通行(§1 Fail Loud 由 caller 處理)
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest
from pandera.errors import SchemaError

from shared.schemas import YahooCloseSchema, validate_yf_close


def _good_series(n: int = 5, ticker: str = "^VIX") -> pd.Series:
    """合法 fetch_yf_close 輸出 fixture(Series + attrs)。"""
    base = _dt.datetime(2026, 1, 1)
    idx = pd.DatetimeIndex([base + _dt.timedelta(days=i) for i in range(n)])
    s = pd.Series([18.5 + i * 0.1 for i in range(n)], index=idx, dtype=float, name=ticker)
    s.attrs["source"] = f"Yahoo:{ticker}"
    s.attrs["fetched_at"] = "2026-06-26T12:00:00+00:00"
    return s


# ════════════════════════════════════════════════════════════════
# 1. 合法輸入 pass
# ════════════════════════════════════════════════════════════════
class TestSchemaPassesValidInput:
    def test_basic_pass(self):
        s = _good_series()
        out = validate_yf_close(s)
        assert out is not None
        assert len(out) == 5

    def test_attrs_preserved(self):
        s = _good_series()
        validate_yf_close(s)
        # attrs 不被驗證流程吃掉
        assert s.attrs["source"] == "Yahoo:^VIX"
        assert s.attrs["fetched_at"] == "2026-06-26T12:00:00+00:00"

    def test_empty_series_passes(self):
        """fetch 失敗回空 Series → validate_yf_close 直接 pass。"""
        empty = pd.Series(dtype=float, name="^VIX")
        out = validate_yf_close(empty)
        assert out is empty


# ════════════════════════════════════════════════════════════════
# 2. 違法 values 立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidValues:
    def test_nan_value_rejected(self):
        s = _good_series()
        s.iloc[2] = float("nan")
        with pytest.raises(SchemaError):
            validate_yf_close(s)

    def test_zero_value_rejected(self):
        """close 不應為 0(YahooCloseSchema 強制 > 0)。"""
        s = _good_series()
        s.iloc[1] = 0.0
        with pytest.raises(SchemaError):
            validate_yf_close(s)

    def test_negative_value_rejected(self):
        s = _good_series()
        s.iloc[0] = -1.5
        with pytest.raises(SchemaError):
            validate_yf_close(s)


# ════════════════════════════════════════════════════════════════
# 3. 違法 index 立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidIndex:
    def test_duplicate_index_rejected(self):
        s = _good_series()
        # 強制最後兩筆 index 相同
        idx = list(s.index)
        idx[-1] = idx[-2]
        s.index = pd.DatetimeIndex(idx)
        with pytest.raises(SchemaError):
            validate_yf_close(s)

    def test_non_monotonic_index_rejected(self):
        s = _good_series()
        # reverse index
        s.index = s.index[::-1]
        with pytest.raises(SchemaError):
            validate_yf_close(s)


# ════════════════════════════════════════════════════════════════
# 4. 違法 attrs(provenance)立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidAttrs:
    def test_missing_source_prefix_rejected(self):
        s = _good_series()
        s.attrs["source"] = "Yhoo:typo"  # 非 'Yahoo:' 開頭
        with pytest.raises(ValueError, match="attrs.source"):
            validate_yf_close(s)

    def test_missing_source_entirely_rejected(self):
        s = _good_series()
        del s.attrs["source"]
        with pytest.raises(ValueError, match="attrs.source"):
            validate_yf_close(s)

    def test_non_iso_fetched_at_rejected(self):
        s = _good_series()
        s.attrs["fetched_at"] = "20260626"  # 無 'T'
        with pytest.raises(ValueError, match="attrs.fetched_at"):
            validate_yf_close(s)

    def test_missing_fetched_at_rejected(self):
        s = _good_series()
        del s.attrs["fetched_at"]
        with pytest.raises(ValueError, match="attrs.fetched_at"):
            validate_yf_close(s)
