"""tests/test_schemas_phase_b3_dividends.py — A1 Phase B 後續 part 2 守衛(v19.163)

SPEC §18 / CLAUDE.md §3.1 — 基金配息序列出口 schema(list[dict] interface)。

本檔守:
1. FundDividendSchema 對合法 fetch_div 輸出 pass
2. 對 illegal data 立擋:
   - 非 list / 長度超 24 / 缺 key
   - date 重複 / 不可 parse
   - amount <= 0 / >= 100 / 缺 key
"""
from __future__ import annotations

import pytest
from pandera.errors import SchemaError

from shared.schemas import (
    FundDividendSchema,
    validate_fund_dividends,
    _FUND_DIVIDEND_MAX_ROWS,
)


def _good_divs(n: int = 3) -> list[dict]:
    """合法 fetch_div 輸出 fixture(list[dict],desc by date)。"""
    return [
        {"date": "2026-06-15", "amount": 0.32},
        {"date": "2026-05-15", "amount": 0.30},
        {"date": "2026-04-15", "amount": 0.28},
    ][:n]


# ════════════════════════════════════════════════════════════════
# 1. 合法輸入 pass
# ════════════════════════════════════════════════════════════════
class TestSchemaPassesValidInput:
    def test_basic_pass(self):
        divs = _good_divs()
        out = validate_fund_dividends(divs)
        assert out is divs  # 不複製

    def test_empty_list_passes(self):
        """fetch 失敗回 [] → validate_fund_dividends 直接 pass。"""
        out = validate_fund_dividends([])
        assert out == []

    def test_none_passes(self):
        out = validate_fund_dividends(None)
        assert out is None

    def test_max_length_24_passes(self):
        divs = [
            {"date": f"2025-{m:02d}-15", "amount": 0.30}
            for m in range(1, 13)
        ] + [
            {"date": f"2024-{m:02d}-15", "amount": 0.30}
            for m in range(1, 13)
        ]
        assert len(divs) == 24
        validate_fund_dividends(divs)  # 不 raise


# ════════════════════════════════════════════════════════════════
# 2. 違法結構立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidStructure:
    def test_not_a_list_rejected(self):
        with pytest.raises(ValueError, match="必須為 list"):
            validate_fund_dividends({"date": "2026-06-15", "amount": 0.3})

    def test_too_many_rows_rejected(self):
        divs = [
            {"date": f"2025-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}", "amount": 0.30}
            for i in range(25)
        ]
        # 製造 unique date
        divs = [
            {"date": f"2024-01-{(i + 1):02d}", "amount": 0.30}
            for i in range(25)
        ]
        with pytest.raises(ValueError, match="超過上限"):
            validate_fund_dividends(divs)

    def test_missing_date_key_rejected(self):
        divs = [{"amount": 0.3}]
        with pytest.raises(ValueError, match="'date'"):
            validate_fund_dividends(divs)

    def test_missing_amount_key_rejected(self):
        divs = [{"date": "2026-06-15"}]
        with pytest.raises(ValueError, match="'amount'"):
            validate_fund_dividends(divs)

    def test_unparseable_date_rejected(self):
        divs = [{"date": "Not-A-Date", "amount": 0.3}]
        with pytest.raises(ValueError, match="date"):
            validate_fund_dividends(divs)


# ════════════════════════════════════════════════════════════════
# 3. 違法 amount 立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidAmount:
    def test_zero_amount_rejected(self):
        divs = [{"date": "2026-06-15", "amount": 0.0}]
        with pytest.raises(SchemaError):
            validate_fund_dividends(divs)

    def test_negative_amount_rejected(self):
        divs = [{"date": "2026-06-15", "amount": -0.5}]
        with pytest.raises(SchemaError):
            validate_fund_dividends(divs)

    def test_amount_over_100_rejected(self):
        """fetch_div HTML 解析錯誤可能誤抓股價當配息(> 100)。"""
        divs = [{"date": "2026-06-15", "amount": 150.0}]
        with pytest.raises(SchemaError):
            validate_fund_dividends(divs)


# ════════════════════════════════════════════════════════════════
# 4. 違法 date 立擋
# ════════════════════════════════════════════════════════════════
class TestSchemaRejectsInvalidDate:
    def test_duplicate_date_rejected(self):
        """fetch_div 已 dedup(line 4101 seen),schema 守確認契約。"""
        divs = [
            {"date": "2026-06-15", "amount": 0.32},
            {"date": "2026-06-15", "amount": 0.30},
        ]
        with pytest.raises(SchemaError):
            validate_fund_dividends(divs)


# ════════════════════════════════════════════════════════════════
# 5. _FUND_DIVIDEND_MAX_ROWS 契約守
# ════════════════════════════════════════════════════════════════
class TestMaxRowsContract:
    def test_max_rows_is_24(self):
        """fetch_div :24 截斷契約(line 4102),schema MAX_ROWS 必須對齊。"""
        assert _FUND_DIVIDEND_MAX_ROWS == 24
