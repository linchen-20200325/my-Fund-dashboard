"""test_cross_site_cutoffs.py — Phase D SSOT 統一進度守衛 (v19.157)

C2 series(user 拍板):全站 VIX yellow 統一到 SSOT 22(macro_buckets._VIX_YELLOW)。
- ✅ C2-A v19.157:risk_radar 25 → 22
- ✅ C2-B v19.158:macro_beginner_view 20 → 22(本 PR)
- ⏳ C2-C:macro_validation 18 → 22 + calibration JSON bounds
- ⏳ C2-D:結案 cross-site cutoffs + SPEC §16.1 結案

歷史脈絡(v19.147 multi-cutoff design,已被 C2 series 撤銷):
原本 4 個 yellow 點(18 / 20 / 22 / 25)刻意散落代表不同 cadence/校準層;
user 改變主意,接受「日均閃黃」trade-off 換 SSOT 收斂單一值。

本檔測試:
1. risk_radar 已對齊 SSOT 22(C2-A 完成)
2. 剩餘 sites(macro_validation 18 / macro_beginner_view 20)逐步收斂(C2-B/C 進行中)
3. **universal panic=30 必須一致**(真 SSOT,任一處改 → CI 立擋)
"""
import pytest


# ──────────────────────────────────────────────────────────
# 1. C2 series 收斂進度守衛
# ──────────────────────────────────────────────────────────
def test_vix_yellow_c2_progress():
    """C2-A/B 完成:risk_radar + macro_beginner_view 都對齊 SSOT 22。
    剩餘 macro_validation 18 待 C2-C 收斂。"""
    from services.macro_validation import DEFAULT_VIX_WARNING
    from shared.macro_buckets import _VIX_YELLOW
    from ui.helpers.macro_beginner_view import _VIX_WARNING_THRESHOLD

    # SSOT 22(永遠 22,五桶 bar / SPEC §16 用)
    assert _VIX_YELLOW == 22.0, (
        f"macro_buckets._VIX_YELLOW(SSOT)應 22,實際 {_VIX_YELLOW}"
    )
    # macro_beginner_view 已對齊(C2-B v19.158 完成)
    assert _VIX_WARNING_THRESHOLD == 22.0, (
        f"macro_beginner_view._VIX_WARNING_THRESHOLD 應對齊 SSOT 22"
        f"(C2-B v19.158),實際 {_VIX_WARNING_THRESHOLD}"
    )
    # macro_validation 18(C2-C 待收 22)
    assert DEFAULT_VIX_WARNING == 18.0, (
        f"macro_validation.DEFAULT_VIX_WARNING 目前 18,C2-C 後將收 22。"
        f" 實際 {DEFAULT_VIX_WARNING}"
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


def test_risk_radar_vix_source_uses_ssot():
    """C2-A v19.157:risk_radar._signal_vix_level 直接 import _VIX_YELLOW / _VIX_RED
    SSOT,不再寫 inline magic 25 / 30。"""
    import inspect
    from services import risk_radar
    src = inspect.getsource(risk_radar._signal_vix_level)
    assert "_VIX_RED" in src, (
        "risk_radar._signal_vix_level 應從 shared.macro_buckets 引 _VIX_RED 為 panic 閾值"
    )
    assert "_VIX_YELLOW" in src, (
        "risk_radar._signal_vix_level 應從 shared.macro_buckets 引 _VIX_YELLOW 為 warning 閾值"
        "(C2-A v19.157 從 inline 25 收斂)"
    )
    # 守:不可重新 inline magic 25 或 30
    assert "cur >= 25" not in src, (
        "C2-A v19.157 後不可 inline VIX yellow=25,須走 _VIX_YELLOW SSOT"
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
