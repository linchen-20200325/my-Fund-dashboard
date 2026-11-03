# -*- coding: utf-8 -*-
"""BL-0536-H3：`ui_v3/adapters/market_chart.py::build_comparison_card` 的 golden 與契約測試。

輸入一律是真的 `normalize_pair` 輸出（同 `tests/test_v2_domain_normalization.py` 的手算小序列），
涵蓋 pair／single／fallback（B2、C2）／none 與 pair 不畫（insufficient／withheld）。
不依賴 conftest fixture、不 import streamlit。
"""
from __future__ import annotations

import ast
import dataclasses
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:  # 本機以 `--noconftest` 跑
    sys.path.insert(0, str(_ROOT))

from services.v2_domain import normalization as nz  # noqa: E402
from shared.ui_semantics import rules  # noqa: E402
from ui_v3.adapters import market_chart as mc  # noqa: E402
from ui_v3.viewmodels import CHART_PERIODS, MISSING_TEXT, ChartCard, MissingItem  # noqa: E402

LABELS = {"taiex": "LABEL_T", "sp500": "LABEL_S"}
SOURCES = {"taiex": "SRC_T", "sp500": "SRC_S"}


def P(day, value):
    return {"obs_date": day, "value_num": value}


# 同 tests/test_v2_domain_normalization.py 的 golden（算式見該檔註解）。
TAIEX = [
    P("2026-01-09", 80.0), P("2026-01-12", 100.0), P("2026-01-13", None),
    P("2026-01-14", 200.0), P("2026-01-15", 250.0), P("2026-01-16", 150.0), P("2026-04-10", 300.0),
]
SP500 = [
    P("2026-01-12", 999.0), P("2026-01-13", 40.0), P("2026-01-14", 40.0),
    P("2026-01-15", None), P("2026-01-16", 30.0), P("2026-04-13", 50.0),
]


def card_for(taiex, sp500, period="3M", **kw):
    comparison = nz.normalize_pair({"taiex": taiex, "sp500": sp500}, period)
    return comparison, mc.build_comparison_card(comparison, title="TITLE", labels=LABELS, sources=SOURCES, **kw)


def pts(series):
    return [(p.date, p.value) for p in series.points]


def summary(card):
    return [(s.label, s.meta.status, s.meta.reason_code, s.meta.as_of, len(s.points)) for s in card.series]


# ═══════════ golden ═══════════
def test_golden_pair():
    c, card = card_for(TAIEX, SP500)
    d = card.disclosure
    assert card.normalized and d.comparable
    assert (d.mode, d.status, d.base_date, d.base_value, d.window_start, d.frequency, d.gap_policy) == (
        "pair", "ok", "2026-01-14", 100, "2026-01-13", "daily", "no_fill")
    assert d.series_issues == () and d.fallback_reason is None
    assert card.period == "3M" and card.title == "TITLE" and card.detail == () and card.chips == ()
    t, s = card.series
    assert pts(t) == [("2026-01-14", 100.0), ("2026-01-15", 125.0), ("2026-01-16", 75.0), ("2026-04-10", 150.0)]
    assert pts(s) == [("2026-01-14", 100.0), ("2026-01-15", None), ("2026-01-16", 75.0), ("2026-04-13", 125.0)]
    # 圖下資料日：各序列自己的最後觀測日（Q2-b A），不是共同終點
    assert (t.meta.as_of, s.meta.as_of) == ("2026-04-10", "2026-04-13")
    assert (t.meta.source, s.meta.source) == ("SRC_T", "SRC_S")
    assert {t.meta.freshness_state, s.meta.freshness_state} == {"undetermined"}


def test_golden_single_sp500_missing():
    c, card = card_for(TAIEX, None)
    d = card.disclosure
    assert (d.mode, d.status, d.base_date, d.base_value, d.window_start) == ("single", "ok", "2026-01-12", 100, "2026-01-10")
    assert not d.comparable
    assert [(i.series_key, i.reason_code) for i in d.series_issues] == [("sp500", "missing")]
    assert summary(card) == [("LABEL_T", "ok", None, "2026-04-10", 6), ("LABEL_S", "missing", "missing", None, 0)]
    assert card.detail == (MissingItem("LABEL_S", "missing"),)
    assert card.detail[0].PRESENTATION == MISSING_TEXT


def test_golden_single_fetch_failed_is_not_missing():
    _, card = card_for(TAIEX, None, failed_keys={"sp500"})
    assert summary(card)[1] == ("LABEL_S", "failed", "fetch_failed", None, 0)
    assert [(i.series_key, i.reason_code) for i in card.disclosure.series_issues] == [("sp500", "fetch_failed")]
    assert card.detail == (MissingItem("LABEL_S", "fetch_failed"),)
    assert mc.REASON_FETCH_FAILED == rules.STATUS_TO_KEY["failed"] == "fetch_failed"


def test_golden_fallback_B2_excluded_series_listed_with_reason():
    short = [P("2026-02-02", 1.0), P("2026-04-10", 2.0)]
    c, card = card_for(short, SP500)
    d = card.disclosure
    assert (d.mode, d.status, d.fallback_reason, d.base_date, d.window_start) == (
        "fallback", "ok", "insufficient", "2026-01-13", "2026-01-13")
    assert not d.comparable
    assert [(i.series_key, i.reason_code) for i in d.series_issues] == [("taiex", "insufficient")]
    # 被排除那條有資料：undetermined＋原因、不出線、仍帶自己的資料日；不是缺資料 → 不放 MissingItem
    assert summary(card) == [("LABEL_T", "undetermined", "insufficient", "2026-04-10", 0),
                             ("LABEL_S", "ok", None, "2026-04-13", 5)]
    assert card.detail == ()
    assert pts(card.series[1])[0] == ("2026-01-13", 100.0)


def test_golden_fallback_C2_stale_series():
    stale = [P("2025-08-01", 1.0), P("2025-10-01", 2.0), P("2025-12-01", 3.0)]
    _, card = card_for(stale, SP500)
    d = card.disclosure
    assert (d.mode, d.fallback_reason, d.base_date) == ("fallback", "no_common_base", "2026-01-13")
    assert summary(card)[0] == ("LABEL_T", "undetermined", "no_common_base", "2025-12-01", 0)


def test_golden_fallback_both_not_drawn():
    a = [P("2026-03-02", 1.0), P("2026-04-13", 2.0)]
    b = [P("2026-01-12", 1.0), P("2026-01-13", 2.0), P("2026-04-10", 3.0)]
    _, card = card_for(b, a)
    d = card.disclosure
    assert (d.mode, d.status, d.fallback_reason, d.base_date, d.base_value) == (
        "fallback", "insufficient", "insufficient", None, None)
    assert len(d.series_issues) == 2 and all(len(s.points) == 0 for s in card.series)


def test_golden_pair_withheld_no_lines_real_reason_in_status():
    a = [P("2026-01-09", 1.0), P("2026-01-12", 2.0), P("2026-04-10", 3.0)]
    b = [P("2026-01-09", 1.0), P("2026-01-13", 2.0), P("2026-04-09", 3.0), P("2026-04-10", None)]
    _, card = card_for(a, b)
    d = card.disclosure
    assert (d.mode, d.status, d.base_date, d.base_value) == ("pair", "no_common_base", None, None)
    assert [(i.series_key, i.reason_code) for i in d.series_issues] == [("taiex", "withheld"), ("sp500", "withheld")]
    assert summary(card) == [("LABEL_T", "undetermined", "withheld", "2026-04-10", 0),
                             ("LABEL_S", "undetermined", "withheld", "2026-04-09", 0)]


def test_golden_none_both_missing():
    _, card = card_for(None, None, failed_keys={"taiex"})
    d = card.disclosure
    assert (d.mode, d.status, d.base_date, d.base_value, d.window_start) == ("none", "both_missing", None, None, None)
    assert summary(card) == [("LABEL_T", "failed", "fetch_failed", None, 0), ("LABEL_S", "missing", "missing", None, 0)]
    assert card.detail == (MissingItem("LABEL_T", "fetch_failed"), MissingItem("LABEL_S", "missing"))


# ═══════════ 契約 ═══════════
CASES = [
    (TAIEX, SP500), (TAIEX, None), (None, SP500), (None, None),
    ([P("2026-02-02", 1.0), P("2026-04-10", 2.0)], SP500),
    ([P("2025-08-01", 1.0), P("2025-10-01", 2.0), P("2025-12-01", 3.0)], SP500),
    ([P("2026-01-09", 1.0), P("2026-01-12", 2.0), P("2026-04-10", 3.0)],
     [P("2026-01-09", 1.0), P("2026-01-13", 2.0), P("2026-04-09", 3.0)]),
]


@pytest.mark.parametrize("taiex,sp500", CASES)
@pytest.mark.parametrize("period", ["3M", "1Y"])
def test_contract_card_mirrors_l2_exactly(taiex, sp500, period):
    c, card = card_for(taiex, sp500, period)
    assert isinstance(card, ChartCard) and card.normalized and card.disclosure is not None
    d = card.disclosure
    assert (d.mode, d.status, d.base_date, d.base_value, d.window_start, d.fallback_reason) == (
        c.mode, c.status, c.base_date, c.base_value, c.window_start, c.fallback_reason)
    assert d.comparable == (c.mode == nz.MODE_PAIR and c.status == nz.STATUS_OK)
    assert len(card.series) == len(c.series)
    base_dates = set()
    for result, series in zip(c.series, card.series):
        assert series.label == LABELS[result.key]
        assert series.meta.as_of == result.last_obs_date          # 自己的最後觀測日
        if result.status == nz.STATUS_OK:
            assert [(p.date, p.value) for p in series.points] == [(p.obs_date, p.value) for p in result.points]
            base_dates.add(series.points[0].date)
        else:
            assert series.points == ()                           # 沒線 → 沒有任何數值點
            assert result.key in {i.series_key for i in d.series_issues}
    assert len(base_dates) <= 1 and (base_dates == {c.base_date} if base_dates else c.base_date is None)


@pytest.mark.parametrize("taiex,sp500", CASES)
def test_no_invented_display_text_in_output(taiex, sp500):
    """輸出的每個字串只能是：呼叫端提供的字（title／labels／sources）、期間代碼、ISO 日期、或小寫代碼。"""
    _, card = card_for(taiex, sp500)
    supplied = {"TITLE"} | set(LABELS.values()) | set(SOURCES.values()) | set(CHART_PERIODS)
    key = re.compile(r"^[a-z][a-z0-9_.]*$")
    iso = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def walk(obj):
        if isinstance(obj, str):
            yield obj
        elif dataclasses.is_dataclass(obj):
            for f in dataclasses.fields(obj):
                yield from walk(getattr(obj, f.name))
        elif isinstance(obj, tuple):
            for x in obj:
                yield from walk(x)

    for text in walk(card):
        assert text in supplied or key.match(text) or iso.match(text), text


def test_adapter_has_no_cjk_string_constants_outside_docstrings():
    tree = ast.parse((_ROOT / "ui_v3" / "adapters" / "market_chart.py").read_text(encoding="utf-8"))
    docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                  if isinstance(n, (ast.Module, ast.FunctionDef)) and n.body and isinstance(n.body[0], ast.Expr)}
    cjk = re.compile(r"[　-鿿＀-￯]")
    hits = [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)
            and id(n) not in docstrings and cjk.search(n.value)]
    assert not hits, hits


def test_failed_keys_must_point_at_missing_series():
    with pytest.raises(ValueError):
        card_for(TAIEX, SP500, failed_keys={"sp500"})     # 有資料的序列不得標取數失敗
    with pytest.raises(ValueError):
        card_for(TAIEX, None, failed_keys={"vix"})        # 不存在的序列鍵


def test_labels_and_sources_required_for_every_series():
    c = nz.normalize_pair({"taiex": TAIEX, "sp500": SP500}, "3M")
    with pytest.raises(KeyError):
        mc.build_comparison_card(c, title="TITLE", labels={"taiex": "x"}, sources=SOURCES)
    with pytest.raises(TypeError):
        mc.build_comparison_card({"status": "ok"}, title="TITLE", labels=LABELS, sources=SOURCES)


def test_adapter_is_pure_no_streamlit_import():
    tree = ast.parse((_ROOT / "ui_v3" / "adapters" / "market_chart.py").read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            mods.add((n.module or "").split(".")[0])
    assert mods <= {"__future__", "services", "ui_v3"}, mods
