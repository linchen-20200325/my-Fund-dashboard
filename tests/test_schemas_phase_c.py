"""tests/test_schemas_phase_c.py — A1 Phase C 服務層 validators 守衛(v19.164)

服務層 data-only validators 對比出口完整 validators:
- 不驗 provenance attrs(service caller 可能來自 cache / test fixture)
- dividends 不卡 amount < 100 上限(機構基金 / 反向 ETF 可能高配息)

本檔守:
1. validate_fund_nav_data_only 通過無 attrs 的 Series
2. validate_fund_nav_data_only 仍守 values + index 業務契約
3. validate_fund_dividends_data_only 通過 amount > 100 的高配息
4. validate_fund_dividends_data_only 仍守 amount > 0 + date unique
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import pytest
from pandera.errors import SchemaError

from shared.schemas import (
    validate_fund_nav_data_only,
    validate_fund_dividends_data_only,
)


def _nav(n: int = 5, with_attrs: bool = False) -> pd.Series:
    base = _dt.datetime(2026, 1, 1)
    idx = pd.DatetimeIndex([base + _dt.timedelta(days=i) for i in range(n)])
    s = pd.Series([10.5 + i * 0.02 for i in range(n)], index=idx, dtype=float, name="NAV")
    if with_attrs:
        s.attrs["source"] = "MoneyDJ:test:fetch_nav"
        s.attrs["fetched_at"] = "2026-06-26T12:00:00+00:00"
    return s


# ════════════════════════════════════════════════════════════════
# 1. NAV data-only — 通過無 attrs
# ════════════════════════════════════════════════════════════════
class TestNavDataOnlyAcceptsNoAttrs:
    def test_no_attrs_passes(self):
        """服務入口接 NAV 無 attrs(來自 cache 反序列化)→ 通過。"""
        s = _nav(with_attrs=False)
        out = validate_fund_nav_data_only(s)
        assert out is s

    def test_with_attrs_also_passes(self):
        """有 attrs 也通過(不重複驗,信任 fetcher 出口層已驗)。"""
        s = _nav(with_attrs=True)
        validate_fund_nav_data_only(s)

    def test_empty_passes(self):
        assert validate_fund_nav_data_only(pd.Series(dtype=float)) is not None


# ════════════════════════════════════════════════════════════════
# 2. NAV data-only — 仍守業務契約
# ════════════════════════════════════════════════════════════════
class TestNavDataOnlyRejectsInvalidBusinessData:
    def test_zero_nav_rejected(self):
        s = _nav()
        s.iloc[1] = 0.0
        with pytest.raises(SchemaError):
            validate_fund_nav_data_only(s)

    def test_negative_nav_rejected(self):
        s = _nav()
        s.iloc[1] = -1.0
        with pytest.raises(SchemaError):
            validate_fund_nav_data_only(s)

    def test_nan_nav_rejected(self):
        s = _nav()
        s.iloc[2] = float("nan")
        with pytest.raises(SchemaError):
            validate_fund_nav_data_only(s)

    def test_duplicate_index_rejected(self):
        s = _nav()
        idx = list(s.index)
        idx[-1] = idx[-2]
        s.index = pd.DatetimeIndex(idx)
        with pytest.raises(SchemaError):
            validate_fund_nav_data_only(s)


# ════════════════════════════════════════════════════════════════
# 3. Dividends data-only — 通過高配息
# ════════════════════════════════════════════════════════════════
class TestDividendsDataOnlyAcceptsHighAmount:
    def test_high_amount_passes(self):
        """機構基金可能單次配息 > 100,出口層卡 < 100,服務層放寬。"""
        divs = [
            {"date": "2026-06-15", "amount": 150.0},
            {"date": "2026-05-15", "amount": 200.0},
        ]
        out = validate_fund_dividends_data_only(divs)
        assert out is divs

    def test_normal_amount_also_passes(self):
        divs = [{"date": "2026-06-15", "amount": 0.32}]
        validate_fund_dividends_data_only(divs)

    def test_empty_passes(self):
        assert validate_fund_dividends_data_only([]) == []

    def test_none_passes(self):
        assert validate_fund_dividends_data_only(None) is None

    def test_no_24_row_limit(self):
        """服務層不卡 24 上限(可能 backtest 跨多年資料)。"""
        divs = [
            {"date": f"2024-01-{(i + 1):02d}", "amount": 0.30}
            for i in range(28)
        ]
        validate_fund_dividends_data_only(divs)  # 不 raise


# ════════════════════════════════════════════════════════════════
# 4. Dividends data-only — 仍守 amount > 0 + date unique
# ════════════════════════════════════════════════════════════════
class TestDividendsDataOnlyRejectsInvalidBusinessData:
    def test_zero_amount_rejected(self):
        divs = [{"date": "2026-06-15", "amount": 0.0}]
        with pytest.raises(SchemaError):
            validate_fund_dividends_data_only(divs)

    def test_negative_amount_rejected(self):
        divs = [{"date": "2026-06-15", "amount": -0.1}]
        with pytest.raises(SchemaError):
            validate_fund_dividends_data_only(divs)

    def test_duplicate_date_rejected(self):
        divs = [
            {"date": "2026-06-15", "amount": 0.32},
            {"date": "2026-06-15", "amount": 0.40},
        ]
        with pytest.raises(SchemaError):
            validate_fund_dividends_data_only(divs)

    def test_missing_keys_rejected(self):
        with pytest.raises(ValueError):
            validate_fund_dividends_data_only([{"date": "2026-06-15"}])
        with pytest.raises(ValueError):
            validate_fund_dividends_data_only([{"amount": 0.3}])
