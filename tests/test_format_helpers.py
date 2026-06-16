"""v19.79 K6：services/format_helpers.fmt_twd SSOT 行為驗證。"""
from __future__ import annotations

import math

from services.format_helpers import fmt_twd


def test_fmt_twd_integer_default():
    assert fmt_twd(1234) == "NT$1,234"
    assert fmt_twd(0) == "NT$0"
    assert fmt_twd(1234567) == "NT$1,234,567"


def test_fmt_twd_float_default_zero_precision():
    assert fmt_twd(1234.56) == "NT$1,235"  # round half-to-even / banker's
    assert fmt_twd(1234.4) == "NT$1,234"


def test_fmt_twd_negative():
    assert fmt_twd(-1234) == "NT$-1,234"


def test_fmt_twd_none_returns_dash():
    assert fmt_twd(None) == "—"


def test_fmt_twd_nan_returns_dash():
    assert fmt_twd(float("nan")) == "—"
    assert fmt_twd(math.inf) == "—"
    assert fmt_twd(-math.inf) == "—"


def test_fmt_twd_invalid_type_returns_dash():
    assert fmt_twd("abc") == "—"


def test_fmt_twd_sign_force_plus():
    assert fmt_twd(1234, sign=True) == "NT$+1,234"
    assert fmt_twd(-1234, sign=True) == "NT$-1,234"
    assert fmt_twd(0, sign=True) == "NT$+0"


def test_fmt_twd_precision_two():
    assert fmt_twd(1234.567, precision=2) == "NT$1,234.57"
    assert fmt_twd(0.5, precision=2) == "NT$0.50"


def test_fmt_twd_no_prefix():
    assert fmt_twd(1234, prefix="") == "1,234"
    assert fmt_twd(None, prefix="") == "—"


def test_fmt_twd_sign_and_precision_combo():
    assert fmt_twd(1234.56, sign=True, precision=1) == "NT$+1,234.6"
    assert fmt_twd(-1234.56, sign=True, precision=1) == "NT$-1,234.6"
