"""tests/test_data_guard_anomaly_state.py — 資料診斷 Section ⑥ 三態決策。

守的是 2026-08 稽核「必修 1」：`data_registry` 為空 dict 時，異常清單原本會落入
「沒有異常項」分支，直接印一個大綠燈「✅ 全數資料源狀態正常」——
使用者是因為別的 Tab 數字怪才來這頁，看到綠燈就回頭懷疑自己的判讀。
空 registry 代表「還沒量」，不是「量過都正常」（CLAUDE.md §1）。

紅燈型態：
- `test_empty_registry_*` 系列在修正前為 **ImportError 紅**
  （`anomaly_view_state` 當時不存在，邏輯 inline 在 render 裡）。

紅燈型態（2026-08-14 稽核 C1 新增）：
- 本檔原本用 `"release 期已到 +2 天"` 當 release-window 的 fixture，但**生產端
  從不產生這個字串** —— `data_registry._freshness` 實際產出的是
  `"release lag N 天（預期 …）"`。於是這兩個測試長綠、卻守著一份幻覺契約，
  正是 `anomaly_view_state` 的排除條件恆真（每月誤報一批正常 🟡）能存活至今
  的直接原因。fixture 已改吃 `RELEASE_WINDOW_LABEL_PREFIX` SSOT，
  並新增 `test_freshness_actually_emits_the_prefix` 守真正的漂移點。
"""
from __future__ import annotations

import pytest

from ui.helpers.io.data_registry import RELEASE_WINDOW_LABEL_PREFIX
from ui.tab5_data_guard import anomaly_view_state


def _meta(icon: str, label: str = "", name: str = "X") -> dict:
    return {"fresh_icon": icon, "fresh_label": label, "label": name}


def _release_window_label(days: int = 2, date: str = "2026-08-13") -> str:
    """複製 `_freshness` 的 🟡 release-window label 格式（前綴走 SSOT）。

    這裡刻意**不**手打前綴字串 —— 手打就是上面那個 bug 的成因。
    """
    return f"{RELEASE_WINDOW_LABEL_PREFIX} {days} 天（預期 {date}）"


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
    reg = {"A": _meta("🟡", _release_window_label(days=2))}
    state, items = anomaly_view_state(reg)
    assert state == "clean", (
        f"release window 內的 🟡 被誤判為異常；label={reg['A']['fresh_label']!r}"
    )
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
        "win": _meta("🟡", _release_window_label(days=1)),
        "bad": _meta("🔴", "延遲 40 天"),
    }
    state, items = anomaly_view_state(reg)
    assert state == "anomaly"
    assert [k for k, _ in items] == ["bad"]


# ── 稽核 C1：守真正的漂移點（產生端是否還在用同一個前綴）─────────────────
def test_freshness_actually_emits_the_prefix():
    """`_freshness` 的 release-window 🟡 分支必須使用 SSOT 前綴。

    直接讀原始碼比對 —— 這條的目的是「有人把 `_freshness` 的字串改回手打」
    時要變紅。用 mock 去跑 FRED API 反而測不到這件事（而且會打網路）。
    """
    import inspect

    from ui.helpers.io import data_registry as _dr

    _src = inspect.getsource(_dr._update_data_registry)
    # 排除註解行：說明修正理由的註解也會提到這個常數名（半假綠）
    _code_hits = [ln for ln in _src.splitlines()
                  if "RELEASE_WINDOW_LABEL_PREFIX" in ln
                  and not ln.strip().startswith("#")]
    assert _code_hits, (
        "_freshness 的 release-window 🟡 分支沒有使用 SSOT 常數 —— "
        "字串會再度與 anomaly_view_state 脫鉤（這正是 2026-08 的原始 bug）"
    )


def test_anomaly_view_state_uses_ssot_prefix_not_literal():
    """判定端同樣不可手打字串（雙向鎖）。"""
    import inspect

    from ui import tab5_data_guard as _t5

    _src = inspect.getsource(_t5.anomaly_view_state)
    assert "RELEASE_WINDOW_LABEL_PREFIX" in _src
    assert "release 期已到" not in _src.split('"""')[-1], (
        "判定端仍殘留舊的手打字串（生產端從不產生它）"
    )
