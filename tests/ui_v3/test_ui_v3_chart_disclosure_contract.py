# -*- coding: utf-8 -*-
"""BL-0536-H3：歸一化揭露（`ui_v3/viewmodels/chart_disclosure.py`）與 `ChartCard` 歸一化不變量的契約測試。

客戶 `DEC-2026-11-03-04`：至少揭露 基準日、基準值 100、資料頻率、缺值／缺序列處理（`docs/v2/81` 第 2.3 節 G4）。
本檔另鎖 view model 代碼與 L2（`services.v2_domain.normalization`）同值 —— view model 不得 import services，
所以常數各存一份，一致性只能靠這裡。不依賴 conftest fixture、不 import streamlit。
"""
from __future__ import annotations

import dataclasses
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # 本機以 `--noconftest` 跑
    sys.path.insert(0, str(_ROOT))

from services.v2_domain import normalization as nz  # noqa: E402
from services.v2_domain import periods  # noqa: E402
from ui_v3.viewmodels import (  # noqa: E402
    CHART_PERIODS,
    NORMALIZATION_BASE_VALUE,
    NORMALIZATION_MODES,
    ChartCard,
    ChartPoint,
    ChartSeries,
    FactMeta,
    NormalizationDisclosure,
    SeriesIssue,
)
from ui_v3.viewmodels import chart_disclosure as cd  # noqa: E402

BASE = "2026-01-14"


def D(**kw):
    args = dict(mode="pair", status="ok", base_date=BASE, window_start="2026-01-13", base_value=100)
    args.update(kw)
    return NormalizationDisclosure(**args)


def drawn(label="a", first=BASE, first_value=100.0):
    pts = (ChartPoint(first, first_value), ChartPoint("2026-01-15", None), ChartPoint("2026-04-10", 150.0))
    return ChartSeries(label, FactMeta(status="ok", source="S", as_of="2026-04-10"), pts)


def undrawn(label="b", status="missing", reason="missing"):
    return ChartSeries(label, FactMeta(status=status, reason_code=reason), ())


# ───────── 與 L2 同值（view model 不 import services，一致性由此鎖） ─────────
def test_base_value_equals_services_constant_and_is_100():
    assert NORMALIZATION_BASE_VALUE == nz.BASE_VALUE == 100


def test_mode_codes_equal_services_modes():
    assert NORMALIZATION_MODES == (nz.MODE_PAIR, nz.MODE_SINGLE, nz.MODE_FALLBACK, nz.MODE_NONE)
    assert (cd.MODE_PAIR, cd.MODE_SINGLE, cd.MODE_FALLBACK, cd.MODE_NONE) == NORMALIZATION_MODES


def test_comparison_status_codes_equal_services_statuses():
    services_statuses = {nz.STATUS_OK, nz.STATUS_INSUFFICIENT, nz.STATUS_NO_COMMON_BASE,
                         nz.STATUS_TOO_FEW_COMMON_DAYS, nz.STATUS_TOO_FEW_POINTS, nz.STATUS_BOTH_MISSING}
    assert set(cd.COMPARISON_STATUSES) == services_statuses
    assert cd.COMPARISON_STATUS_OK == nz.STATUS_OK and cd.COMPARISON_STATUS_BOTH_MISSING == nz.STATUS_BOTH_MISSING


def test_chart_periods_equal_services_periods():
    assert CHART_PERIODS == periods.PERIODS


def test_frequency_and_gap_policy_are_neutral_codes_single_valued():
    assert cd.FREQUENCIES == ("daily",) and cd.GAP_POLICIES == ("no_fill",)


def test_disclosure_carries_the_four_client_required_items():
    names = {f.name for f in dataclasses.fields(NormalizationDisclosure)}
    # 基準日、基準值、頻率、缺值處理、缺序列處理（mode＋series_issues＋fallback_reason）
    assert {"base_date", "base_value", "frequency", "gap_policy", "mode", "series_issues", "fallback_reason"} <= names
    d = D()
    assert (d.base_date, d.base_value, d.frequency, d.gap_policy) == (BASE, 100, "daily", "no_fill")


# ───────── 揭露本身的不變量 ─────────
def test_base_date_present_iff_status_ok():
    with pytest.raises(ValueError):
        D(base_date=None)                                  # ok 卻沒基準日
    with pytest.raises(ValueError):
        D(status="insufficient", series_issues=(SeriesIssue("a", "insufficient"),))   # 不 ok 卻有基準日
    d = D(status="insufficient", base_date=None, base_value=None, series_issues=(SeriesIssue("a", "insufficient"),))
    assert d.base_date is None and d.base_value is None and not d.comparable


@pytest.mark.parametrize("bad", [None, 0, 1, 99, 100.5, True, "100"])
def test_base_value_must_be_exactly_100_when_drawn(bad):
    with pytest.raises(ValueError):
        D(base_value=bad)


def test_base_value_must_be_none_without_base_date():
    with pytest.raises(ValueError):
        D(status="insufficient", base_date=None, base_value=100, series_issues=(SeriesIssue("a", "insufficient"),))


@pytest.mark.parametrize("field,bad", [
    ("mode", "compare"), ("status", "bad"), ("frequency", "weekly"), ("gap_policy", "ffill"),
    ("base_date", "2026/01/14"), ("base_date", "2026-1-14"), ("window_start", "x"),
])
def test_unknown_codes_and_non_iso_dates_rejected(field, bad):
    with pytest.raises(ValueError):
        D(**{field: bad})


def test_base_date_not_before_window_start():
    with pytest.raises(ValueError):
        D(window_start="2026-01-15")


def test_pair_ok_has_no_issues_and_is_comparable():
    assert D().comparable
    with pytest.raises(ValueError):
        D(series_issues=(SeriesIssue("a", "missing"),))


@pytest.mark.parametrize("mode", ["single", "fallback"])
def test_single_and_fallback_must_list_issues_and_are_never_comparable(mode):
    extra = {"fallback_reason": "insufficient"} if mode == "fallback" else {}
    with pytest.raises(ValueError):
        D(mode=mode, **extra)
    d = D(mode=mode, series_issues=(SeriesIssue("b", "insufficient" if mode == "fallback" else "missing"),), **extra)
    assert not d.comparable


def test_fallback_reason_rules():
    issue = (SeriesIssue("b", "insufficient"),)
    with pytest.raises(ValueError):
        D(mode="fallback", series_issues=issue)                       # fallback 缺 reason
    with pytest.raises(ValueError):
        D(mode="fallback", series_issues=issue, fallback_reason="no_common_base")  # reason 不屬任何被排除序列
    with pytest.raises(ValueError):
        D(mode="single", series_issues=issue, fallback_reason="insufficient")      # 非 fallback 不得帶
    assert D(mode="fallback", series_issues=issue, fallback_reason="insufficient").fallback_reason == "insufficient"


def test_mode_none_iff_both_missing():
    issues = (SeriesIssue("a", "missing"), SeriesIssue("b", "missing"))
    d = D(mode="none", status="both_missing", base_date=None, window_start=None, base_value=None, series_issues=issues)
    assert not d.comparable
    with pytest.raises(ValueError):
        D(mode="none", status="insufficient", base_date=None, base_value=None, series_issues=issues)
    with pytest.raises(ValueError):
        D(mode="pair", status="both_missing", base_date=None, base_value=None, series_issues=issues)


def test_series_issue_keys_only_and_unique():
    with pytest.raises(ValueError):
        SeriesIssue("台股", "missing")
    with pytest.raises(ValueError):
        SeriesIssue("a", "資料未備")
    dup = (SeriesIssue("a", "missing"), SeriesIssue("a", "insufficient"))
    with pytest.raises(ValueError):
        D(status="insufficient", base_date=None, base_value=None, series_issues=dup)


def test_disclosure_is_frozen():
    with pytest.raises(dataclasses.FrozenInstanceError):
        D().base_value = 101


# ───────── ChartCard 的歸一化不變量 ─────────
def test_disclosure_required_iff_normalized():
    ChartCard("t", (drawn(),))                              # 一般圖卡不受影響
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), drawn("b")), normalized=True)   # 歸一化卻沒揭露
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), drawn("b")), disclosure=D())    # 有揭露卻沒標歸一化
    card = ChartCard("t", (drawn("a"), drawn("b")), normalized=True, disclosure=D())
    assert card.disclosure.comparable


def test_pair_needs_two_lines_and_fallback_exactly_one():
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), undrawn()), normalized=True, disclosure=D())
    fb = D(mode="fallback", series_issues=(SeriesIssue("b", "insufficient"),), fallback_reason="insufficient")
    ChartCard("t", (drawn("a"), undrawn(status="undetermined", reason="insufficient")), normalized=True, disclosure=fb)
    with pytest.raises(ValueError):   # 退回單序列不得畫成兩條（看起來像比較）
        ChartCard("t", (drawn("a"), drawn("b")), normalized=True, disclosure=fb)
    # 線數由 mode 決定，不是「每條沒線的有原因」就夠（多出一條畫線序列、原因數照樣對得上時也要擋）
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), drawn("b"), drawn("c")), normalized=True, disclosure=D())
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), drawn("c"), undrawn(status="undetermined", reason="insufficient")),
                  normalized=True, disclosure=fb)


def test_never_two_base_dates_each_line_starts_at_base_date_with_100():
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), drawn("b", first="2026-01-13")), normalized=True, disclosure=D())
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), drawn("b", first_value=101.0)), normalized=True, disclosure=D())


def test_no_base_date_means_no_numeric_points():
    d = D(status="insufficient", base_date=None, base_value=None,
          series_issues=(SeriesIssue("a", "insufficient"), SeriesIssue("b", "insufficient")))
    ChartCard("t", (undrawn("a", "undetermined", "insufficient"), undrawn("b", "undetermined", "insufficient")),
              normalized=True, disclosure=d)
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), undrawn("b", "undetermined", "insufficient")), normalized=True, disclosure=d)


def test_every_undrawn_series_has_an_issue():
    single = D(mode="single", series_issues=(SeriesIssue("b", "missing"),))
    ChartCard("t", (drawn("a"), undrawn()), normalized=True, disclosure=single)
    with pytest.raises(ValueError):
        ChartCard("t", (drawn("a"), undrawn(), undrawn("c")), normalized=True, disclosure=single)


def test_missing_series_cannot_carry_points_even_in_normalized_card():
    with pytest.raises(ValueError):
        ChartSeries("b", FactMeta(status="missing", reason_code="missing"), (ChartPoint(BASE, 100.0),))
