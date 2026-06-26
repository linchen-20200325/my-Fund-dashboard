"""test_cross_site_cutoffs.py — multi-cutoff design 守衛 (v19.147)

CLAUDE.md §8.3 F-GRAY-4 audit 釐清:Fund 端 VIX/HY/MOVE/PCR 等指標的 yellow 線
在不同模組刻意取不同值,語意不同**非 bug**:
- macro_validation(長期評分,JSON 可校準):VIX warning=18
- macro_buckets.py(SSOT/SPEC 顯示):VIX yellow=22
- macro_beginner_view(四時域教學前置):VIX warning=20
- risk_radar(1-day 雷達保守):VIX yellow=25
- 全員一致:VIX panic = 30(crisis)

本檔測試:
1. 各 yellow 值維持各自設計(防有人路過順手「統一」破壞語意)
2. **universal panic=30 必須一致**(這條是真 SSOT,任一處改 30 → CI 立擋)

如果未來真要做 Phase D 全面 SSOT 統一,先看完 CLAUDE.md §8.3 F-GRAY-4 + SPEC §16
multi-cutoff design 說明,確認是 user 指示的架構改造。
"""
import pytest


# ──────────────────────────────────────────────────────────
# 1. yellow 各自設計(intentional spread,語意各自正確)
# ──────────────────────────────────────────────────────────
def test_vix_yellow_intentional_spread():
    """VIX yellow 4 個值刻意散落:18(長期校準)/ 20(教學前置)/ 22(SSOT)/ 25(1-day 保守)。
    若有人未經 user 同意改成統一值 → CI 立擋,要求看 SPEC §16 multi-cutoff 說明。"""
    from services.macro_validation import DEFAULT_VIX_WARNING
    from shared.macro_buckets import _VIX_YELLOW
    from ui.helpers.macro_beginner_view import _VIX_WARNING_THRESHOLD

    assert DEFAULT_VIX_WARNING == 18.0, (
        f"macro_validation.DEFAULT_VIX_WARNING 應 18(長期校準),實際 {DEFAULT_VIX_WARNING}"
    )
    assert _VIX_YELLOW == 22.0, (
        f"macro_buckets._VIX_YELLOW 應 22(SSOT/MACRO_THRESHOLDS),實際 {_VIX_YELLOW}"
    )
    assert _VIX_WARNING_THRESHOLD == 20.0, (
        f"macro_beginner_view._VIX_WARNING_THRESHOLD 應 20(教學前置),"
        f"實際 {_VIX_WARNING_THRESHOLD}"
    )

    # 4 個值應該全部不同(intentional spread)
    yellows = {DEFAULT_VIX_WARNING, _VIX_YELLOW, _VIX_WARNING_THRESHOLD}
    assert len(yellows) >= 3, (
        f"4 個 yellow 點應 intentional spread 至少 3 個不同值,實際 {sorted(yellows)}。"
        " 若改至統一,先讀 SPEC §16 F-GRAY-4 multi-cutoff 說明確認。"
    )


def test_hy_yellow_intentional_spread():
    """HY spread yellow 也是刻意散落:4(SSOT)/ 5(教學保守)。"""
    from shared.macro_buckets import _HY_YELLOW
    from ui.helpers.macro_beginner_view import _HY_SPREAD_WARN_THRESHOLD
    assert _HY_YELLOW == 4.0
    assert _HY_SPREAD_WARN_THRESHOLD == 5.0
    assert _HY_YELLOW != _HY_SPREAD_WARN_THRESHOLD


# ──────────────────────────────────────────────────────────
# 2. universal panic=30 必須一致(這是真 SSOT)
# ──────────────────────────────────────────────────────────
def test_vix_panic_universal_30():
    """VIX panic=30 是真 SSOT,所有 3 個模組必須一致。任一處改 30 → CI 立擋。"""
    from services.macro_validation import DEFAULT_VIX_CRISIS
    from shared.macro_buckets import _VIX_RED
    from ui.helpers.macro_beginner_view import _VIX_PANIC_THRESHOLD

    assert DEFAULT_VIX_CRISIS == 30.0
    assert _VIX_RED == 30.0
    assert _VIX_PANIC_THRESHOLD == 30.0
    # 全員一致
    panics = {DEFAULT_VIX_CRISIS, _VIX_RED, _VIX_PANIC_THRESHOLD}
    assert panics == {30.0}, (
        f"VIX panic 必須全員 30.0(真 SSOT),實際 {panics}。"
        " 若需改,先讀 SPEC §16 F-GRAY-4 multi-cutoff 說明 + 確認全部 4 site 同步。"
    )


def test_risk_radar_vix_panic_source_check():
    """risk_radar.py:103 source 字串守 30(避免有人手改 25 之類)。"""
    import inspect
    from services import risk_radar
    src = inspect.getsource(risk_radar._signal_vix_level)
    assert "cur >= 30" in src, (
        "risk_radar._signal_vix_level VIX panic 必須是 30 (multi-cutoff F-GRAY-4 一致點)"
    )
    # yellow 25 也是刻意設計,守住
    assert "cur >= 25" in src, (
        "risk_radar._signal_vix_level VIX yellow 應為 25 (1-day 保守化,SPEC §16 設計)"
    )


# ──────────────────────────────────────────────────────────
# 3. F-GRAY-4 結案文件存在性(防有人改 SPEC 卻忘了)
# ──────────────────────────────────────────────────────────
def test_spec_documents_multi_cutoff():
    """SPEC.md §16 必須含 multi-cutoff 結案說明 + F-GRAY-4 reference。"""
    from pathlib import Path
    spec_path = Path(__file__).parent.parent / "SPEC.md"
    assert spec_path.exists()
    spec_text = spec_path.read_text(encoding="utf-8")
    assert "multi-cutoff" in spec_text.lower() or "Multi-cutoff" in spec_text, (
        "SPEC.md 應有 multi-cutoff 段(v19.147 D3 結案)"
    )
    assert "F-GRAY-4" in spec_text, (
        "SPEC.md 應引用 F-GRAY-4 結案說明"
    )
