"""v19.35 Screener v2 純函式單元測試（不打網路）。"""
from __future__ import annotations

import pytest

from services.screener_v2 import (
    FundETFRow,
    _coerce_pct,
    collect_countries,
    collect_currencies,
    filter_rows,
    normalize_row,
)


# ════════════════════════════════════════════════════════════════
# _coerce_pct
# ════════════════════════════════════════════════════════════════
class TestCoercePct:
    def test_string_percent_sign(self):
        assert _coerce_pct("8.5%") == 8.5

    def test_string_plain_number(self):
        assert _coerce_pct("8.5") == 8.5

    def test_string_with_comma(self):
        assert _coerce_pct("1,234.5") == 1234.5

    def test_ratio_auto_scale(self):
        assert _coerce_pct(0.085) == pytest.approx(8.5)

    def test_already_percent(self):
        assert _coerce_pct(8.5) == 8.5

    def test_zero(self):
        assert _coerce_pct(0) == 0.0

    def test_none(self):
        assert _coerce_pct(None) is None

    def test_invalid_string(self):
        assert _coerce_pct("abc") is None

    def test_empty_string(self):
        assert _coerce_pct("") is None

    def test_nan(self):
        assert _coerce_pct(float("nan")) is None

    def test_negative(self):
        assert _coerce_pct(-3.5) == -3.5


# ════════════════════════════════════════════════════════════════
# normalize_row
# ════════════════════════════════════════════════════════════════
class TestNormalizeRow:
    def test_basic(self):
        r = normalize_row(
            raw_id="0050", raw_name="元大台灣50",
            raw_currency="TWD", raw_country="Taiwan",
            raw_total_return=12.5, raw_dividend_rate=3.0,
            source="twse",
        )
        assert r is not None
        assert r.id == "0050"
        assert r.name == "元大台灣50"
        assert r.currency == "TWD"
        assert r.total_return == 12.5
        assert r.dividend_rate == 3.0
        assert r.source == "twse"

    def test_missing_id_returns_none(self):
        assert normalize_row(raw_id=None, raw_name="X") is None

    def test_missing_name_returns_none(self):
        assert normalize_row(raw_id="X", raw_name=None) is None

    def test_empty_id_string_returns_none(self):
        assert normalize_row(raw_id="  ", raw_name="X") is None

    def test_empty_name_string_returns_none(self):
        assert normalize_row(raw_id="X", raw_name="  ") is None

    def test_currency_uppercased(self):
        r = normalize_row(raw_id="X", raw_name="Y", raw_currency="usd")
        assert r.currency == "USD"

    def test_missing_returns_default_to_zero(self):
        r = normalize_row(raw_id="X", raw_name="Y")
        assert r.total_return == 0.0
        assert r.dividend_rate == 0.0

    def test_pct_strings(self):
        r = normalize_row(
            raw_id="X", raw_name="Y",
            raw_total_return="12.5%", raw_dividend_rate="3%",
        )
        assert r.total_return == 12.5
        assert r.dividend_rate == 3.0

    def test_to_dict(self):
        r = normalize_row(raw_id="X", raw_name="Y", raw_total_return=10)
        d = r.to_dict()
        assert d["id"] == "X"
        assert d["total_return"] == 10.0


# ════════════════════════════════════════════════════════════════
# filter_rows
# ════════════════════════════════════════════════════════════════
def _mk_row(**kw):
    base = dict(
        id="X", name="Y", currency="TWD", country="Taiwan",
        total_return=10.0, dividend_rate=5.0, source="twse",
    )
    base.update(kw)
    return FundETFRow(**base)


class TestFilterRows:
    def test_empty_input(self):
        assert filter_rows([]) == []

    def test_no_filter_default_passes_when_covered(self):
        rows = [_mk_row(), _mk_row(id="Z")]
        out = filter_rows(rows, require_return_cover_div=False)
        assert len(out) == 2

    def test_currency_filter_exact(self):
        rows = [_mk_row(currency="USD"), _mk_row(currency="TWD")]
        out = filter_rows(rows, currency="USD", require_return_cover_div=False)
        assert len(out) == 1
        assert out[0].currency == "USD"

    def test_currency_filter_case_insensitive(self):
        rows = [_mk_row(currency="USD")]
        out = filter_rows(rows, currency="usd", require_return_cover_div=False)
        assert len(out) == 1

    def test_country_filter(self):
        rows = [_mk_row(country="USA"), _mk_row(country="Taiwan")]
        out = filter_rows(rows, country="USA", require_return_cover_div=False)
        assert len(out) == 1

    def test_all_keyword_skips_filter(self):
        rows = [_mk_row(currency="USD"), _mk_row(currency="TWD")]
        out = filter_rows(rows, currency="全部", require_return_cover_div=False)
        assert len(out) == 2

    def test_none_skips_filter(self):
        rows = [_mk_row(currency="USD"), _mk_row(currency="TWD")]
        out = filter_rows(rows, currency=None, require_return_cover_div=False)
        assert len(out) == 2

    def test_return_cover_div_pass(self):
        rows = [_mk_row(total_return=10.0, dividend_rate=5.0)]
        assert len(filter_rows(rows, require_return_cover_div=True)) == 1

    def test_return_cover_div_fail(self):
        rows = [_mk_row(total_return=3.0, dividend_rate=5.0)]
        assert len(filter_rows(rows, require_return_cover_div=True)) == 0

    def test_return_cover_div_equal(self):
        rows = [_mk_row(total_return=5.0, dividend_rate=5.0)]
        assert len(filter_rows(rows, require_return_cover_div=True)) == 1

    def test_combined_filters(self):
        rows = [
            _mk_row(currency="USD", country="USA", total_return=10, dividend_rate=3),
            _mk_row(currency="USD", country="USA", total_return=1, dividend_rate=3),
            _mk_row(currency="TWD", country="Taiwan", total_return=10, dividend_rate=3),
        ]
        out = filter_rows(
            rows, currency="USD", country="USA",
            require_return_cover_div=True,
        )
        assert len(out) == 1
        assert out[0].country == "USA"


# ════════════════════════════════════════════════════════════════
# collect_* helpers
# ════════════════════════════════════════════════════════════════
class TestCollectHelpers:
    def test_currencies_sorted_unique(self):
        rows = [
            _mk_row(currency="USD"),
            _mk_row(currency="TWD"),
            _mk_row(currency="USD"),
        ]
        assert collect_currencies(rows) == ["TWD", "USD"]

    def test_countries_sorted_unique(self):
        rows = [_mk_row(country="Taiwan"), _mk_row(country="USA")]
        assert collect_countries(rows) == ["Taiwan", "USA"]

    def test_empty_input(self):
        assert collect_currencies([]) == []
        assert collect_countries([]) == []
