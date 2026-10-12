# -*- coding: utf-8 -*-
"""`resolve_tier`：髒值 `policy_tier` 視為未設定，不退回 `is_core`（客戶 2026-10-12 裁示 (c)）。

原則：髒資料 ≠ 缺資料；無法確認就不猜，維持三態語意。

- 合法值（`normalize_tier` 認得）→ 照用。
- 缺資料（缺鍵、`None`、空字串、純空白）→ 退回嚴格布林 `is_core`（正常 fallback，不得被破壞）。
- 髒值（有值、非空白但認不得；含非字串型別）→ `None`，不看 `is_core`。

突變驗證（實跑）：把 `shared/policy_tier.py::resolve_tier` 的
`if not _is_missing_tier(_raw_tier): return None` 拿掉（還原成一律退回 `is_core`）→
`test_dirty_policy_tier_is_unset_not_fallback` 中 is_core 為 True／False 的各列、
以及 `test_decision_matrix_dirty_tier_holds` 轉紅。
NaN／`pandas.NA` 屬空值＝缺資料（總管 2026-10-12 拍板）：把 `_is_missing_tier` 的
`_is_nan_like(raw)` 拿掉 → `test_nan_like_policy_tier_is_missing_and_falls_back`
中 is_core 為 True／False 的各列轉紅（pd.NA 那幾列會在 `normalize_tier` 丟 TypeError）。
另 `ui/tab1_macro.py` 動作對照表補上客戶 2026-10-12 核准的說明文字 (e)，
`test_tab1_unset_tier_note_present` 鎖住逐字內容。
"""
from __future__ import annotations

import pathlib

import pytest

from shared.policy_tier import resolve_tier

ROOT = pathlib.Path(__file__).resolve().parents[1]

_UNSET_NOTE = "配置級別未設定時，系統維持持有，不套用核心／衛星的加減碼與撤出規則。"


# ── 合法值：照用（is_core 不影響） ──────────────────────────────────
@pytest.mark.parametrize("raw, expect", [
    ("core", "core"), ("satellite", "satellite"),
    ("Core", "core"), ("SATELLITE", "satellite"),
    ("  core  ", "core"), (" Satellite\t", "satellite"),
    ("核心", "core"), ("衛星", "satellite"), (" 核心 ", "core"),
])
@pytest.mark.parametrize("is_core", [True, False, None])
def test_valid_policy_tier_is_used(raw, expect, is_core):
    assert resolve_tier({"policy_tier": raw, "is_core": is_core}) == expect


# ── 缺資料：正常 fallback 到嚴格布林 is_core ─────────────────────────
_MISSING = [
    pytest.param({}, id="missing-key"),
    pytest.param({"policy_tier": None}, id="None"),
    pytest.param({"policy_tier": ""}, id="empty"),
    pytest.param({"policy_tier": "  "}, id="blank"),
    pytest.param({"policy_tier": "\t\n"}, id="whitespace"),
]


@pytest.mark.parametrize("base", _MISSING)
@pytest.mark.parametrize("is_core, expect", [
    (True, "core"), (False, "satellite"), (None, None),
])
def test_missing_policy_tier_falls_back_to_is_core(base, is_core, expect):
    assert resolve_tier({**base, "is_core": is_core}) == expect


@pytest.mark.parametrize("base", _MISSING)
def test_missing_policy_tier_without_is_core_is_unset(base):
    assert resolve_tier(dict(base)) is None


# ── 空值（NaN／pandas.NA，pandas 讀空儲存格的產物）＝缺資料，照舊 fallback ──
# 總管 2026-10-12 拍板：NaN／NA 屬空值＝缺資料，不是髒值。
def _nan_like_values():
    vals = [pytest.param(float("nan"), id="float-nan")]
    try:
        import numpy as np
        vals += [pytest.param(np.nan, id="np.nan"),
                 pytest.param(np.float64("nan"), id="np.float64-nan"),
                 pytest.param(np.float32("nan"), id="np.float32-nan")]
    except ImportError:  # pragma: no cover - numpy 不在時只測 float('nan')
        pass
    try:
        import pandas as pd
        vals += [pytest.param(pd.NA, id="pd.NA")]
    except ImportError:  # pragma: no cover
        pass
    return vals


@pytest.mark.parametrize("raw", _nan_like_values())
@pytest.mark.parametrize("is_core, expect", [
    (True, "core"), (False, "satellite"), (None, None),
])
def test_nan_like_policy_tier_is_missing_and_falls_back(raw, is_core, expect):
    assert resolve_tier({"policy_tier": raw, "is_core": is_core}) == expect


# ── 髒值：未設定，不退回 is_core ─────────────────────────────────────
_DIRTY = ["foo", "Satellite?", "core1", 123, "未知", "中性", 0, 1.5, False, True]


@pytest.mark.parametrize("raw", _DIRTY)
@pytest.mark.parametrize("is_core", [True, False, None])
def test_dirty_policy_tier_is_unset_not_fallback(raw, is_core):
    assert resolve_tier({"policy_tier": raw, "is_core": is_core}) is None


# ── 經 decision_matrix 的回歸 ──────────────────────────────────────
@pytest.mark.parametrize("raw", ["foo", "Satellite?", 123])
def test_decision_matrix_dirty_tier_holds(raw):
    """髒 policy_tier + is_core=False：舊行為會被讀成衛星、極度悲觀時「全撤」；
    現在 tier 為 None、動作持有。"""
    from services.decision_matrix import ACTION_HOLD, verdict_to_actions
    out = verdict_to_actions("極度悲觀", -12.0, [
        {"code": "X1", "name": "dirty", "policy_tier": raw, "is_core": False},
    ])
    assert len(out) == 1
    assert out[0]["tier"] is None
    assert out[0]["action"] == ACTION_HOLD


def test_decision_matrix_missing_tier_still_falls_back():
    """缺資料（空字串）+ is_core=False 仍是衛星 —— 正常 fallback 未被破壞。"""
    from services.decision_matrix import ACTION_EXIT, verdict_to_actions
    out = verdict_to_actions("極度悲觀", -12.0, [
        {"code": "X1", "name": "sat", "policy_tier": "", "is_core": False},
    ])
    assert out[0]["tier"] == "satellite"
    assert out[0]["action"] == ACTION_EXIT


# ── (e) tab1 說明文字 ─────────────────────────────────────────────
def test_tab1_unset_tier_note_present():
    src = (ROOT / "ui" / "tab1_macro.py").read_text(encoding="utf-8")
    assert _UNSET_NOTE in src
