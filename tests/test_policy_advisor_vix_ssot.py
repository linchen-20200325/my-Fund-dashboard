"""tests/test_policy_advisor_vix_ssot.py — 保單建議引擎的 VIX 恐慌門檻收 SSOT（§3.3）。

背景
====
`services/policy_advisor_service.py` 規則 1「σ 深跌 + VIX 恐慌 → 分批加碼」原本把
門檻寫成裸數字，沒有具名常數 —— 全站其他 VIX 消費者（risk_radar 紅燈 /
beginner_view 恐慌燈 / macro_validation crisis）早就走 `shared/macro_buckets` 的
紅界，只有這裡是第二份真相。

語意確認（收之前要先問「是不是同一條線」）
==========================================
該規則的文案與 rule code 講的都是**恐慌**，對應 SPEC §16.1 C2 系列拍板的
「panic 全站統一」那條紅界，**不是**警戒黃界（黃界語意是「注意波動」，
拿來當加碼訊號會讓建議提早觸發）。因此收紅界。

本檔守什麼
==========
1. AST：advisor 真的從 L0 SSOT import，且規則 1 的比較式裡不再有裸數字。
2. 值：匯出的具名常數就是 SSOT 那個值（浮點用容差比，不用 `==`）。
3. 行為：常數真的被規則吃到（門檻上觸發 / 門檻下不觸發）—— 防「改了常數但
   判斷式其實沒用它」。
4. 接線（PROCESS §4）：Tab3 缺值提示真的把這個常數讀進 f-string，
   而不是 import 完擺著、旁邊另外寫死一個數字。

修正前紅不紅
============
1 / 2 / 4 條：**紅**（常數不存在 → ImportError；AST 找不到 import；比較式裡是裸數字）。
3 條：**綠** —— 這輪是「換成具名常數」不是「改門檻」，行為本來就該零變化；
它的作用是把「零行為改動」這件事釘住，並防日後有人加常數卻沒接進判斷式。
"""
from __future__ import annotations

import ast
import math
from pathlib import Path

from services.policy_advisor_service import (
    DEEP_DROP_VIX_BUY,
    VIX_PANIC_THRESHOLD,
    advise_fund,
)

_REPO = Path(__file__).resolve().parent.parent
_ADVISOR = _REPO / "services" / "policy_advisor_service.py"
_TAB3 = _REPO / "ui" / "tab3_portfolio.py"

_SSOT_MODULE = "shared.macro_buckets"
_SSOT_NAME = "_VIX_RED"
_ADVISOR_CONST = "VIX_PANIC_THRESHOLD"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _func(tree: ast.Module, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"找不到函式 {name}")


def _imported_names(tree: ast.Module, module: str) -> dict:
    """{原始名稱: 綁定名稱} —— 供比對 `import X as Y` 的別名。"""
    out: dict = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == module:
            for alias in node.names:
                out[alias.name] = alias.asname or alias.name
    return out


# ── 1. AST：有 import、比較式無裸數字 ────────────────────────────────
def test_advisor_imports_vix_ssot():
    assert _SSOT_NAME in _imported_names(_tree(_ADVISOR), _SSOT_MODULE), (
        f"{_ADVISOR.name} 應從 {_SSOT_MODULE} 引全站 panic 線，而不是自己寫一個數字"
    )


def test_vix_rule_compares_against_a_name_not_a_literal():
    """規則 1 的 `vix >= ?` 右手邊必須是具名常數，不能是數字字面值。

    只掃 `advise_fund` 內、左手邊是 vix 參數的比較 —— 其餘 σ 位階切點不在本檔守備範圍。
    """
    fn = _func(_tree(_ADVISOR), "advise_fund")
    checked = 0
    for node in ast.walk(fn):
        if not isinstance(node, ast.Compare):
            continue
        if not (isinstance(node.left, ast.Name) and node.left.id == "vix"):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, (ast.GtE, ast.Gt)):
                continue
            checked += 1
            assert isinstance(comparator, ast.Name), (
                "VIX 恐慌門檻不得為 inline magic number，應比對具名常數"
            )
            assert comparator.id == _ADVISOR_CONST
    assert checked >= 1, "沒掃到任何 VIX 門檻比較式 —— 規則被改名或刪掉了？"


# ── 2. 值：具名常數 == SSOT ──────────────────────────────────────────
def test_constant_equals_ssot_value():
    from shared.macro_buckets import _VIX_RED
    assert math.isclose(VIX_PANIC_THRESHOLD, _VIX_RED, rel_tol=1e-12, abs_tol=1e-12)


# ── 3. 行為：常數真的被判斷式吃到（零行為改動的釘子）────────────────
def _sigma_deep() -> dict:
    return {"sigma_rank": -2.5}


def test_rule_fires_at_threshold():
    r = advise_fund(_sigma_deep(), {"alert_level": "green"},
                    vix=VIX_PANIC_THRESHOLD)
    assert r["code"] == DEEP_DROP_VIX_BUY


def test_rule_does_not_fire_just_below_threshold():
    r = advise_fund(_sigma_deep(), {"alert_level": "green"},
                    vix=VIX_PANIC_THRESHOLD - 0.01)
    assert r["code"] != DEEP_DROP_VIX_BUY


def test_rule_still_needs_deep_sigma():
    """VIX 再高，σ 沒到深跌區也不該叫人加碼（門檻換寫法不得放寬其他條件）。"""
    r = advise_fund({"sigma_rank": -1.0}, {"alert_level": "green"},
                    vix=VIX_PANIC_THRESHOLD + 10)
    assert r["code"] != DEEP_DROP_VIX_BUY


# ── 4. 接線：Tab3 缺值提示真的讀了這個常數 ───────────────────────────
def test_tab3_caption_consumes_the_constant():
    """import 進來還不算數 —— 必須在缺值提示那個 helper 內被引用。

    拿掉 f-string 裡那一格插值（改回不講數字）本條就會紅。
    """
    tree = _tree(_TAB3)
    bound = _imported_names(tree, "services.policy_advisor_service").get(_ADVISOR_CONST)
    assert bound, "Tab3 應從 advisor 引恐慌門檻常數，不得自己寫死一份數字"

    fn = _func(tree, "_vix_for_advice")
    used = any(isinstance(n, ast.Name) and n.id == bound for n in ast.walk(fn))
    assert used, f"{bound} 被 import 但沒有在缺值提示裡用到（算對了沒接出去）"


def test_tab3_caption_has_no_hardcoded_panic_number():
    """同一個 helper 內不得另外出現與門檻同值的數字字面值（第二份真相）。"""
    fn = _func(_tree(_TAB3), "_vix_for_advice")
    for node in ast.walk(fn):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) \
                and not isinstance(node.value, bool):
            assert not math.isclose(float(node.value), VIX_PANIC_THRESHOLD,
                                    rel_tol=1e-12, abs_tol=1e-12), (
                "提示文字裡出現與 SSOT 同值的裸數字 —— 門檻一改就會說謊"
            )
