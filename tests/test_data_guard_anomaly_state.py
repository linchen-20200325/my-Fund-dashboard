"""tests/test_data_guard_anomaly_state.py — 資料診斷 Section ⑥ 三態決策。

守的是 2026-08 稽核「必修 1」：`data_registry` 為空 dict 時，異常清單原本會落入
「沒有異常項」分支，直接印一個大綠燈「✅ 全數資料源狀態正常」——
使用者是因為別的 Tab 數字怪才來這頁，看到綠燈就回頭懷疑自己的判讀。
空 registry 代表「還沒量」，不是「量過都正常」（CLAUDE.md §1）。

紅燈型態：
- `test_empty_registry_*` 系列在修正前為 **ImportError 紅**
  （`anomaly_view_state` 當時不存在，邏輯 inline 在 render 裡）。
"""
from __future__ import annotations

import pytest

from ui.tab5_data_guard import anomaly_view_state


def _meta(icon: str, label: str = "", name: str = "X") -> dict:
    return {"fresh_icon": icon, "fresh_label": label, "label": name}


# ── 空 registry 必須是獨立的第三態 ────────────────────────────────────
@pytest.mark.parametrize("empty", [{}, None])
def test_empty_registry_is_not_clean(empty):
    state, items = anomaly_view_state(empty)
    assert state == "empty"
    assert state != "clean"
    assert items == []


def test_clean_requires_at_least_one_registered_source():
    state, items = anomaly_view_state({"A": _meta("🟢")})
    assert state == "clean"
    assert items == []


# ── 異常判定 ──────────────────────────────────────────────────────────
def test_red_is_anomaly():
    state, items = anomaly_view_state({"A": _meta("🔴", "延遲 30 天")})
    assert state == "anomaly"
    assert [k for k, _ in items] == ["A"]


def test_yellow_within_release_window_is_not_anomaly():
    """🟡 但屬 FRED release window 內 → 正常，不列入異常。"""
    reg = {"A": _meta("🟡", "release 期已到 +2 天")}
    state, items = anomaly_view_state(reg)
    assert state == "clean"
    assert items == []


def test_yellow_true_delay_is_anomaly():
    state, items = anomaly_view_state({"A": _meta("🟡", "延遲 9 天")})
    assert state == "anomaly"
    assert len(items) == 1


def test_yellow_missing_label_is_treated_as_anomaly():
    """fresh_label 缺失時保守視為異常（寧可多提醒，不可漏報）。"""
    state, _ = anomaly_view_state({"A": {"fresh_icon": "🟡"}})
    assert state == "anomaly"


def test_white_square_is_not_anomaly():
    state, _ = anomaly_view_state({"A": _meta("⬜", "尚未觸發")})
    assert state == "clean"


# ── 排序：🔴 先於 🟡，同色依 label ────────────────────────────────────
def test_sort_red_before_yellow_then_by_label():
    reg = {
        "y1": _meta("🟡", "延遲", "乙"),
        "r2": _meta("🔴", "延遲", "B"),
        "r1": _meta("🔴", "延遲", "A"),
    }
    state, items = anomaly_view_state(reg)
    assert state == "anomaly"
    assert [k for k, _ in items] == ["r1", "r2", "y1"]


def test_mixed_registry_keeps_only_anomalies():
    reg = {
        "ok": _meta("🟢"),
        "win": _meta("🟡", "release 期已到 +1 天"),
        "bad": _meta("🔴", "延遲 40 天"),
    }
    state, items = anomaly_view_state(reg)
    assert state == "anomaly"
    assert [k for k, _ in items] == ["bad"]
