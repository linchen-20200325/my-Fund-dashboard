"""Regression tests for ui.components.mk_clock.classify_phase.

User reported case: PMI=49.9 trend=flat, CPI/FED missing → 誤判 recession.
這些測試鎖死「缺資料 → unknown」與「PMI 邊界容忍」契約。
"""
from __future__ import annotations

import pytest

from ui.components.mk_clock import classify_phase


def _ind(**kw):
    """Build an indicators dict; pass PMI=(value, trend) etc. as tuples."""
    out = {}
    for key, val in kw.items():
        if val is None:
            continue
        v, t = val
        out[key] = {"value": v, "trend": t}
    return out


# ── 缺資料 → unknown ─────────────────────────────────────────────────
def test_missing_cpi_and_fed_returns_unknown_not_recession():
    """User 的原始 case：PMI=49.9 trend=flat、CPI/FED 全缺 → 必須 unknown，不可衰退。"""
    ind = _ind(PMI=(49.9, "flat"))
    phase, meta = classify_phase(ind)
    assert phase == "unknown"
    assert "CPI" in meta["missing"]
    assert meta["pmi"] == 49.9


def test_missing_cpi_only_returns_unknown():
    ind = _ind(PMI=(52.0, "up"), FED_RATE=(4.5, "down"))
    phase, meta = classify_phase(ind)
    assert phase == "unknown"
    assert meta["missing"] == ["CPI"]


def test_missing_pmi_only_returns_unknown():
    ind = _ind(CPI=(2.5, "down"), FED_RATE=(4.5, "down"))
    phase, meta = classify_phase(ind)
    assert phase == "unknown"
    assert meta["missing"] == ["PMI"]


def test_empty_indicators_returns_unknown():
    phase, meta = classify_phase({})
    assert phase == "unknown"
    assert set(meta["missing"]) == {"PMI", "CPI"}


def test_none_indicators_returns_unknown():
    phase, meta = classify_phase(None)
    assert phase == "unknown"


# ── PMI 邊界容忍（±0.5） ─────────────────────────────────────────────
def test_pmi_49_9_flat_with_cpi_down_is_recovery_not_recession():
    """PMI 49.9 在 ±0.5 緩衝區、CPI 趨勢下降 → 復甦（不是衰退）。"""
    ind = _ind(PMI=(49.9, "flat"), CPI=(2.5, "down"), FED_RATE=(4.5, "down"))
    phase, _ = classify_phase(ind)
    assert phase == "recovery"


def test_pmi_50_5_with_cpi_down_is_recovery():
    ind = _ind(PMI=(50.5, "flat"), CPI=(2.5, "down"), FED_RATE=(4.5, "down"))
    phase, _ = classify_phase(ind)
    assert phase == "recovery"


def test_pmi_48_with_flat_cpi_down_remains_recession():
    """PMI 48（深度收縮）+ trend flat + CPI down → 衰退（econ_up=False, infl_up=False）。"""
    ind = _ind(PMI=(48.0, "flat"), CPI=(2.0, "down"), FED_RATE=(4.0, "down"))
    phase, _ = classify_phase(ind)
    assert phase == "recession"


def test_pmi_48_trend_up_with_cpi_down_is_recovery():
    """PMI 雖收縮但趨勢上揚 + CPI 降 → 復甦（趨勢補強生效）。"""
    ind = _ind(PMI=(48.0, "up"), CPI=(2.0, "down"), FED_RATE=(4.0, "down"))
    phase, _ = classify_phase(ind)
    assert phase == "recovery"


# ── 四象限正常判定 ─────────────────────────────────────────────────────
@pytest.mark.parametrize("pmi,pmi_t,cpi_t,expected", [
    (53.0, "up",   "down", "recovery"),    # 經濟升 + 通膨降
    (55.0, "up",   "up",   "expansion"),   # 經濟升 + 通膨升
    (47.0, "down", "up",   "slowdown"),    # 經濟降 + 通膨升（停滯性通膨）
    (45.0, "down", "down", "recession"),   # 經濟降 + 通膨降
])
def test_four_quadrants_with_full_data(pmi, pmi_t, cpi_t, expected):
    ind = _ind(PMI=(pmi, pmi_t), CPI=(2.5, cpi_t), FED_RATE=(4.5, "down"))
    phase, _ = classify_phase(ind)
    assert phase == expected


# ── meta 完整性 ───────────────────────────────────────────────────────
def test_meta_includes_all_required_fields():
    ind = _ind(PMI=(52.0, "up"), CPI=(2.5, "down"), FED_RATE=(4.5, "down"))
    _, meta = classify_phase(ind)
    for k in ("zh", "icon", "desc", "alloc_eq", "alloc_bd", "color", "advice",
              "pmi", "cpi", "fed", "pmi_t", "cpi_t", "fed_t", "rate_down", "missing"):
        assert k in meta, f"meta missing key: {k}"
    assert meta["missing"] == []
    assert meta["rate_down"] is True


def test_unknown_meta_carries_partial_values():
    """unknown phase 仍要把已抓到的欄位回填 meta 供 UI 顯示。"""
    ind = _ind(PMI=(49.9, "flat"))  # CPI/FED 缺
    _, meta = classify_phase(ind)
    assert meta["pmi"] == 49.9
    assert meta["cpi"] is None
    assert meta["fed"] is None
    assert meta["zh"] == "資料不足"
