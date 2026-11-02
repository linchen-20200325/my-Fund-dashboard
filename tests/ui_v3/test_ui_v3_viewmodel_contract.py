# -*- coding: utf-8 -*-
"""View Model Contract 測試（80 第 6 節）：Missing 語意、ActionSlot 詞彙、ProvenanceTag、圖卡與 chip 規則。

不依賴 conftest fixture、不 import streamlit／services。
"""
from __future__ import annotations

import dataclasses
import math

import pytest

from ui_v3.viewmodels import (
    ACTION_SLOT_SOURCES_ENABLED,
    ACTION_VOCABULARY,
    CHART_PERIODS,
    CHIP_KINDS,
    MISSING_TEXT,
    ActionSlot,
    ChartCard,
    ChartPoint,
    ChartSeries,
    EvidenceItem,
    FactMeta,
    MetricCard,
    MissingItem,
    ProvenanceTag,
    StatusChip,
    ValueFacts,
)

OK = dict(source="S", as_of="2000-01-03")


def ok_facts(v=1.0):
    return ValueFacts(v, FactMeta(status="ok", **OK))


# ───────── Missing 語意 ─────────
def test_missing_text_is_the_formal_string():
    assert MISSING_TEXT == "◇ 資料未備"
    assert MissingItem.PRESENTATION == MISSING_TEXT


@pytest.mark.parametrize("status", ["missing", "failed"])
@pytest.mark.parametrize("bad", [0, 0.0, 1.5, -1])
def test_missing_or_failed_cannot_carry_a_numeric_value(status, bad):
    with pytest.raises(ValueError):
        ValueFacts(bad, FactMeta(status=status, reason_code="r"))


@pytest.mark.parametrize("status", ["missing", "failed"])
def test_missing_or_failed_requires_reason_code(status):
    with pytest.raises(ValueError):
        FactMeta(status=status)


def test_ok_requires_value_source_and_as_of():
    with pytest.raises(ValueError):
        ValueFacts(None, FactMeta(status="ok", **OK))
    with pytest.raises(ValueError):
        FactMeta(status="ok", source="S")  # 缺 as_of
    with pytest.raises(ValueError):
        FactMeta(status="ok", as_of="2000-01-03")  # 缺 source
    with pytest.raises(ValueError):
        FactMeta(status="stale", source="S")  # stale 也要 provenance


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), True, False, "1.0", [1]])
def test_value_rejects_nan_inf_bool_and_non_numbers(bad):
    with pytest.raises((ValueError, TypeError)):
        ValueFacts(bad, FactMeta(status="ok", **OK))


def test_unknown_status_and_freshness_rejected():
    with pytest.raises(ValueError):
        FactMeta(status="neutral")
    with pytest.raises(ValueError):
        FactMeta(status="ok", freshness_state="fresh-ish", **OK)


def test_undetermined_may_have_no_value_and_no_source():
    v = ValueFacts(None, FactMeta(status="undetermined"))
    assert not v.has_value and v.meta.freshness_state == "undetermined"


def test_stale_value_is_kept_not_zeroed():
    v = ValueFacts(98.5, FactMeta(status="stale", freshness_state="stale", **OK))
    assert v.value == 98.5


def test_metric_card_none_value_must_display_missing_text_never_zero():
    missing = ValueFacts(None, FactMeta(status="missing", reason_code="r"))
    assert MetricCard("t", missing, MISSING_TEXT).display_value == MISSING_TEXT
    for bad in ("0", "0.0", "—", "N/A", "中性"):
        with pytest.raises(ValueError):
            MetricCard("t", missing, bad)
    with pytest.raises(ValueError):  # 有值卻顯示缺值字樣
        MetricCard("t", ok_facts(), MISSING_TEXT)
    assert MetricCard("t", ok_facts(3.0), "3.0").facts.value == 3.0


def test_missing_item_requires_key_style_reason_code():
    assert MissingItem("缺什麼", "fetch_failed").reason_code == "fetch_failed"
    for bad in ("取數失敗", "", "Has Space", "UPPER"):
        with pytest.raises(ValueError):
            MissingItem("缺什麼", bad)


# ───────── ActionSlot ─────────
def test_action_vocabulary_is_exactly_the_six_words_of_67():
    assert ACTION_VOCABULARY == ("續抱", "觀察", "降低曝險", "減碼", "替代比較", "無法判定")


def test_phase7_gate_is_closed_in_batch1():
    assert ACTION_SLOT_SOURCES_ENABLED is False


def test_action_slot_absent_or_undetermined_only_before_phase7():
    assert not ActionSlot().visible
    s = ActionSlot("無法判定", reason="rules_not_defined")
    assert s.visible and s.state == "無法判定"
    for word in ACTION_VOCABULARY[:-1]:  # 其餘五個詞：Phase 7 前一律拒絕（含帶 source_ref 的組合）
        with pytest.raises(ValueError):
            ActionSlot(word)
        with pytest.raises(ValueError):
            ActionSlot(word, source_ref="system_action_state:x")


@pytest.mark.parametrize("bad", ["HOLD", "buy", "加碼", "續抱 ", "neutral", "安全", "中性", ""])
def test_action_slot_rejects_words_outside_vocabulary(bad):
    with pytest.raises(ValueError):
        ActionSlot(bad, reason="r")


def test_action_slot_undetermined_must_explain_and_cannot_cite_a_source():
    with pytest.raises(ValueError):
        ActionSlot("無法判定")
    with pytest.raises(ValueError):
        ActionSlot("無法判定", reason="r", source_ref="x")
    with pytest.raises(ValueError):
        ActionSlot(None, reason="r")


def test_action_slot_vocab_rules_when_gate_opens(monkeypatch):
    """日後 Phase 7：模擬把 gate 打開（只在本測試記憶體內），詞彙與來源規則仍成立。"""
    import ui_v3.viewmodels.action_slot as mod
    monkeypatch.setattr(mod, "ACTION_SLOT_SOURCES_ENABLED", True)
    assert mod.ActionSlot("續抱", source_ref="sas:1").state == "續抱"
    with pytest.raises(ValueError):
        mod.ActionSlot("續抱")  # 行動詞必須帶來源
    with pytest.raises(ValueError):
        mod.ActionSlot("HOLD", source_ref="sas:1")


# ───────── ProvenanceTag ─────────
def test_provenance_tag_requires_source_and_as_of_or_explicit_missing():
    assert ProvenanceTag("S", "2000-01-03").fallback_used is False
    assert ProvenanceTag("S", "2000-01-03", fallback_used=True).fallback_used
    assert ProvenanceTag(missing_reason_code="no_source").missing_reason_code == "no_source"
    for kwargs in ({}, {"source": "S"}, {"as_of": "2000-01-03"}, {"source": "", "as_of": "2000-01-03"}):
        with pytest.raises(ValueError):
            ProvenanceTag(**kwargs)


def test_provenance_tag_missing_and_complete_are_mutually_exclusive():
    with pytest.raises(ValueError):
        ProvenanceTag("S", "2000-01-03", missing_reason_code="r")
    with pytest.raises(ValueError):
        ProvenanceTag(source="S", missing_reason_code="r", fallback_used=True)
    with pytest.raises(TypeError):
        ProvenanceTag("S", "2000-01-03", fallback_used="yes")


# ───────── StatusChip／Evidence／Chart ─────────
def test_status_chip_accepts_only_rule_kinds_and_key_labels():
    assert CHIP_KINDS == ("attention", "missing", "undetermined", "failed", "stale", "neutral")
    assert StatusChip("stale", "not_latest").kind == "stale"
    for kind in ("good", "bad", "red", "buy", ""):
        with pytest.raises(ValueError):
            StatusChip(kind, "k")
    for label in ("需要注意", "Free Text", ""):
        with pytest.raises(ValueError):
            StatusChip("attention", label)


def test_evidence_item_requires_label_and_never_invents_rule_ref():
    assert EvidenceItem("依據").rule_ref is None
    with pytest.raises(ValueError):
        EvidenceItem("")
    with pytest.raises(ValueError):
        EvidenceItem("x", rule_ref="  ")


def _series(label="s", values=(1.0, 2.0)):
    pts = tuple(ChartPoint(f"2000-01-{i + 3:02d}", v) for i, v in enumerate(values))
    return ChartSeries(label, FactMeta(status="ok", source="S", as_of=pts[-1].date), pts)


def test_chart_card_limits_and_defaults():
    card = ChartCard("t", (_series("a"),))
    assert card.period == "1Y" and CHART_PERIODS == ("3M", "6M", "1Y", "3Y")
    assert ChartCard("t", tuple(_series(c) for c in "abc")).series[2].label == "c"
    with pytest.raises(ValueError):
        ChartCard("t", tuple(_series(c) for c in "abcd"))
    chip = StatusChip("neutral", "k")
    with pytest.raises(ValueError):
        ChartCard("t", (_series(),), chips=(chip,) * 4)
    with pytest.raises(ValueError):
        ChartCard("t", (_series(),), period="5Y")
    with pytest.raises(TypeError):
        ChartCard("t", (_series(),), detail=("free text",))
    ChartCard("t", (_series(),), detail=(EvidenceItem("e"), MissingItem("m", "r"), ProvenanceTag("S", "2000-01-03")))


def test_chart_series_gaps_stay_none_and_missing_series_has_no_numbers():
    s = _series(values=(1.0, None, 3.0))
    assert [p.value for p in s.points] == [1.0, None, 3.0]  # 斷線不補、不畫零
    with pytest.raises(ValueError):
        ChartSeries("s", FactMeta(status="missing", reason_code="r"), (ChartPoint("2000-01-03", 0.0),))
    with pytest.raises(ValueError):
        ChartSeries("s", FactMeta(status="ok", **OK), (ChartPoint("2000-01-03", None),))
    with pytest.raises(ValueError):  # 日期亂序／重複
        ChartSeries("s", FactMeta(status="ok", **OK), (ChartPoint("2000-01-04", 1.0), ChartPoint("2000-01-03", 1.0)))
    with pytest.raises(ValueError):
        ChartSeries("s", FactMeta(status="ok", **OK), (ChartPoint("2000-01-03", 1.0), ChartPoint("2000-01-03", 2.0)))
    with pytest.raises(ValueError):
        ChartPoint("2000-01-03", math.nan)


def test_view_models_are_frozen():
    card = MetricCard("t", ok_facts(), "1.0")
    with pytest.raises(dataclasses.FrozenInstanceError):
        card.display_value = "2"  # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        ActionSlot().state = "續抱"  # type: ignore[misc]


def test_view_models_are_deterministic_and_comparable():
    assert MetricCard("t", ok_facts(), "1.0") == MetricCard("t", ok_facts(), "1.0")
