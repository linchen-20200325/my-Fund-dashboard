"""DEC-2026-10-24-10 A3(客戶裁示):分類未判定時,品質只當資料／證據,不得轉成換／留／加碼等行動。

永久原則:資料／證據 ≠ 投資行動;Missing／Unknown 不得被另一個單軸訊號繞過後重新產生行動。
只驗 `services.health.action.combine_action` 的分類未判定情形;真 Core、真非 Core、NAV 不足
(分類已知)須與 6d3baa19 基線逐鍵相同(下方 `_GOLDEN_6D3BAA19` 由該 commit 實跑產出)。
"""
from __future__ import annotations

import itertools

import pandas as pd
import pytest

from services.health.action import CORE_UNKNOWN_QUALITY_SUFFIX, combine_action
from services.health.grade import compute_4d_health
from services.zscore_engine import rebalance_signal
from shared.colors import (
    MATERIAL_ORANGE,
    TRAFFIC_GREEN,
    TRAFFIC_NEUTRAL,
    TRAFFIC_RED,
    TRAFFIC_YELLOW,
)

_IDX = pd.bdate_range("2023-01-02", periods=300)
_NAVS = {
    "hi": pd.Series([10.0] * 299 + [11.0], index=_IDX),        # 非 Core 會給停利/減碼
    "lo": pd.Series([11.0] * 299 + [10.0], index=_IDX),        # 非 Core 會給加碼/逢低
    "mid": pd.Series([10.0 + 0.01 * ((i % 7) - 3) for i in range(300)], index=_IDX),
    "short": pd.Series([10.0] * 20, index=pd.bdate_range("2023-01-02", periods=20)),  # NAV 不足
}
_HEALTH_ARGS = {
    "good": dict(tr1y_pct=10, adr_pct=4, sharpe=1.0, sigma_pct=8, fund_ccy="TWD"),     # A
    "mid": dict(tr1y_pct=3, adr_pct=4, sharpe=0.5, sigma_pct=10, fund_ccy="TWD"),      # C
    "weak": dict(tr1y_pct=-15, adr_pct=9, sharpe=-0.8, sigma_pct=25, fund_ccy="TWD"),  # F + 吃本金
    "na": {},
}

# 行動詞黑名單(DEC-10 A3)。固定後綴「暫不提供換／留建議」是否定句,比對前先移除。
_ACTION_WORDS = ("考慮換", "換", "留", "加碼", "減碼", "買", "賣", "停利", "續抱", "持有",
                 "安全", "逢低", "追")
_ACTION_EMOJI = ("🟢", "🟡", "🟠", "🔴")
_UNKNOWN_CATS = [None, "", "   ", "其他", "Equity", "固定收益型"]


def _h(k):
    return compute_4d_health(**_HEALTH_ARGS[k])


def _assert_no_action(a):
    """結構欄位＋文字黑名單雙重斷言:分類未判定 → 無任何投資行動語意。"""
    assert a["timing"] == "unknown"
    assert a["color"] == TRAFFIC_NEUTRAL
    assert a["color"] not in (TRAFFIC_GREEN, TRAFFIC_RED, MATERIAL_ORANGE, TRAFFIC_YELLOW)
    assert a["z"] is None
    act = a["action"]
    assert act.endswith(CORE_UNKNOWN_QUALITY_SUFFIX)
    body = act[: -len(CORE_UNKNOWN_QUALITY_SUFFIX)]
    for w in _ACTION_WORDS:
        assert w not in body, (w, act)
        assert w not in a["reason"], (w, a["reason"])
    for e in _ACTION_EMOJI:
        assert e not in act, (e, act)


def _unknown_signal(cat="其他"):
    z = rebalance_signal(_NAVS["hi"], cat, None)
    assert z["core_status"] == "unknown"
    return z


# ── 1. Unknown＋品質弱:品質 evidence 仍在,無行動 ──────────────────────
def test_unknown_weak_quality_evidence_kept_no_action():
    h = _h("weak")
    a = combine_action(h, _unknown_signal())
    _assert_no_action(a)
    assert a["quality"] == "weak" and a["grade"] == h["grade"] and a["grade"] in ("D", "F")
    assert a["action"] == "⬜ 品質偏弱" + CORE_UNKNOWN_QUALITY_SUFFIX
    assert "考慮換" not in a["action"]
    assert "品質桶=weak" in a["reason"]
    assert "🔴 吃本金" in a["flags"]          # 既有 deterministic evidence 照舊揭露


# ── 2. Unknown＋品質佳/中等:不出現留/加碼/安全(含綠色 tone) ──────────────
@pytest.mark.parametrize("qk,label", [("good", "品質佳"), ("mid", "品質中等")])
def test_unknown_good_or_mid_quality_no_hold_add_or_safe(qk, label):
    a = combine_action(_h(qk), _unknown_signal())
    _assert_no_action(a)
    assert a["quality"] == qk
    assert a["action"] == f"⬜ {label}{CORE_UNKNOWN_QUALITY_SUFFIX}"
    assert a["color"] != TRAFFIC_GREEN


# ── 3/4. 真 Core、真非 Core、NAV 不足(分類已知):與 6d3baa19 逐鍵相同 ─────────
@pytest.mark.parametrize("key", list(itertools.product(
    _HEALTH_ARGS, _NAVS, ("科技股票型", "高收益債券型", "平衡型"))))
def test_core_and_non_core_identical_to_baseline(key):
    hk, nk, cat = key
    z = rebalance_signal(_NAVS[nk], cat, None)
    assert z["core_status"] in ("core", "non_core")
    assert combine_action(_h(hk), z) == _GOLDEN_6D3BAA19[key]


# ── 5. 類別空白/查表不到/分類例外:皆 Unknown,行動值不偷偷 fallback ──────────
@pytest.mark.parametrize("cat", _UNKNOWN_CATS)
@pytest.mark.parametrize("qk", ["good", "mid", "weak"])
@pytest.mark.parametrize("nk", ["hi", "lo", "mid", "short"])
def test_unknown_categories_never_action(cat, qk, nk):
    z = rebalance_signal(_NAVS[nk], cat, None)
    assert z["core_status"] == "unknown"
    _assert_no_action(combine_action(_h(qk), z))


def _boom(_c):
    raise RuntimeError("asset_bucket 爆炸(模擬分類例外)")


@pytest.mark.parametrize("qk", ["good", "mid", "weak"])
def test_classification_exception_never_action(monkeypatch, qk):
    import services.regime_fit as rf
    monkeypatch.setattr(rf, "asset_bucket", _boom)
    z = rebalance_signal(_NAVS["lo"], "科技股票型", None)
    assert z["core_status"] == "unknown"
    _assert_no_action(combine_action(_h(qk), z))


@pytest.mark.parametrize("bad_action", ["加碼/逢低", "持有", "停利/減碼"])
def test_unknown_with_stray_action_value_does_not_fallback(bad_action):
    """防禦:即使 z_signal 帶了行動值,只要 core_status='unknown' 就不落 3×3 或品質單軸。"""
    z = {**_unknown_signal(), "action": bad_action, "applies": True, "z": -3.0}
    a = combine_action(_h("good"), z)
    assert a["color"] == TRAFFIC_NEUTRAL and a["timing"] == "unknown"
    body = a["action"][: -len(CORE_UNKNOWN_QUALITY_SUFFIX)]
    assert a["action"].endswith(CORE_UNKNOWN_QUALITY_SUFFIX)
    for w in _ACTION_WORDS:
        assert w not in body


def test_unknown_with_insufficient_quality_still_data_insufficient_branch():
    """品質資料不足(grade —)優先:照舊「資料不足」,不受本批影響(與基線同)。"""
    a = combine_action(_h("na"), _unknown_signal())
    assert a["quality"] == "na" and a["action"] == "⚪ 資料不足,先補歷史淨值再評"
    assert a["color"] == TRAFFIC_NEUTRAL


# 6d3baa19 基線實跑輸出(git archive 6d3baa19 後以同一組輸入呼叫 combine_action 產出,未手改)。
_GOLDEN_6D3BAA19 = {
    ('good', 'hi', '科技股票型'): {'action': '🟠 好標的但位階高 → 續抱別追、可部分停利', 'color': '#ff9800', 'quality': 'good', 'timing': 'high', 'grade': 'A', 'z': 17.263, 'flags': [], 'reason': '品質 A × 位階 high(Z=+17.26,預設門檻)→ 🟠 好標的但位階高 → 續抱別追、可部分停利。'},
    ('good', 'hi', '高收益債券型'): {'action': '🟠 好標的但位階高 → 續抱別追、可部分停利', 'color': '#ff9800', 'quality': 'good', 'timing': 'high', 'grade': 'A', 'z': 17.263, 'flags': [], 'reason': '品質 A × 位階 high(Z=+17.26,預設門檻)→ 🟠 好標的但位階高 → 續抱別追、可部分停利。'},
    ('good', 'hi', '平衡型'): {'action': '🟢 品質佳 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#22c55e', 'quality': 'good', 'timing': 'na', 'grade': 'A', 'z': None, 'flags': [], 'reason': '品質桶=good;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('good', 'lo', '科技股票型'): {'action': '🟢 加碼好時機', 'color': '#22c55e', 'quality': 'good', 'timing': 'low', 'grade': 'A', 'z': -17.263, 'flags': [], 'reason': '品質 A × 位階 low(Z=-17.26,預設門檻)→ 🟢 加碼好時機。'},
    ('good', 'lo', '高收益債券型'): {'action': '🟢 加碼好時機', 'color': '#22c55e', 'quality': 'good', 'timing': 'low', 'grade': 'A', 'z': -17.263, 'flags': [], 'reason': '品質 A × 位階 low(Z=-17.26,預設門檻)→ 🟢 加碼好時機。'},
    ('good', 'lo', '平衡型'): {'action': '🟢 品質佳 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#22c55e', 'quality': 'good', 'timing': 'na', 'grade': 'A', 'z': None, 'flags': [], 'reason': '品質桶=good;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('good', 'mid', '科技股票型'): {'action': '🟡 續抱', 'color': '#eab308', 'quality': 'good', 'timing': 'mid', 'grade': 'A', 'z': 1.005, 'flags': [], 'reason': '品質 A × 位階 mid(Z=+1.00,預設門檻)→ 🟡 續抱。'},
    ('good', 'mid', '高收益債券型'): {'action': '🟡 續抱', 'color': '#eab308', 'quality': 'good', 'timing': 'mid', 'grade': 'A', 'z': 1.005, 'flags': [], 'reason': '品質 A × 位階 mid(Z=+1.00,預設門檻)→ 🟡 續抱。'},
    ('good', 'mid', '平衡型'): {'action': '🟢 品質佳 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#22c55e', 'quality': 'good', 'timing': 'na', 'grade': 'A', 'z': None, 'flags': [], 'reason': '品質桶=good;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('good', 'short', '科技股票型'): {'action': '🟢 品質佳 ·位階未知(NAV 有效點不足,不硬判時機 §1)', 'color': '#22c55e', 'quality': 'good', 'timing': 'unknown', 'grade': 'A', 'z': None, 'flags': [], 'reason': '品質桶=good;位階不可算(insufficient;有效點 20)—— 不硬判(§1)。'},
    ('good', 'short', '高收益債券型'): {'action': '🟢 品質佳 ·位階未知(NAV 有效點不足,不硬判時機 §1)', 'color': '#22c55e', 'quality': 'good', 'timing': 'unknown', 'grade': 'A', 'z': None, 'flags': [], 'reason': '品質桶=good;位階不可算(insufficient;有效點 20)—— 不硬判(§1)。'},
    ('good', 'short', '平衡型'): {'action': '🟢 品質佳 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#22c55e', 'quality': 'good', 'timing': 'na', 'grade': 'A', 'z': None, 'flags': [], 'reason': '品質桶=good;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('mid', 'hi', '科技股票型'): {'action': '🟠 減碼', 'color': '#ff9800', 'quality': 'mid', 'timing': 'high', 'grade': 'C', 'z': 17.263, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質 C × 位階 high(Z=+17.26,預設門檻)→ 🟠 減碼。'},
    ('mid', 'hi', '高收益債券型'): {'action': '🟠 減碼', 'color': '#ff9800', 'quality': 'mid', 'timing': 'high', 'grade': 'C', 'z': 17.263, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質 C × 位階 high(Z=+17.26,預設門檻)→ 🟠 減碼。'},
    ('mid', 'hi', '平衡型'): {'action': '🟡 品質中等 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#eab308', 'quality': 'mid', 'timing': 'na', 'grade': 'C', 'z': None, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質桶=mid;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('mid', 'lo', '科技股票型'): {'action': '🟡 逢低小加 / 觀望', 'color': '#eab308', 'quality': 'mid', 'timing': 'low', 'grade': 'C', 'z': -17.263, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質 C × 位階 low(Z=-17.26,預設門檻)→ 🟡 逢低小加 / 觀望。'},
    ('mid', 'lo', '高收益債券型'): {'action': '🟡 逢低小加 / 觀望', 'color': '#eab308', 'quality': 'mid', 'timing': 'low', 'grade': 'C', 'z': -17.263, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質 C × 位階 low(Z=-17.26,預設門檻)→ 🟡 逢低小加 / 觀望。'},
    ('mid', 'lo', '平衡型'): {'action': '🟡 品質中等 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#eab308', 'quality': 'mid', 'timing': 'na', 'grade': 'C', 'z': None, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質桶=mid;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('mid', 'mid', '科技股票型'): {'action': '⚪ 持有觀察', 'color': '#888888', 'quality': 'mid', 'timing': 'mid', 'grade': 'C', 'z': 1.005, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質 C × 位階 mid(Z=+1.00,預設門檻)→ ⚪ 持有觀察。'},
    ('mid', 'mid', '高收益債券型'): {'action': '⚪ 持有觀察', 'color': '#888888', 'quality': 'mid', 'timing': 'mid', 'grade': 'C', 'z': 1.005, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質 C × 位階 mid(Z=+1.00,預設門檻)→ ⚪ 持有觀察。'},
    ('mid', 'mid', '平衡型'): {'action': '🟡 品質中等 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#eab308', 'quality': 'mid', 'timing': 'na', 'grade': 'C', 'z': None, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質桶=mid;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('mid', 'short', '科技股票型'): {'action': '🟡 品質中等 ·位階未知(NAV 有效點不足,不硬判時機 §1)', 'color': '#eab308', 'quality': 'mid', 'timing': 'unknown', 'grade': 'C', 'z': None, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質桶=mid;位階不可算(insufficient;有效點 20)—— 不硬判(§1)。'},
    ('mid', 'short', '高收益債券型'): {'action': '🟡 品質中等 ·位階未知(NAV 有效點不足,不硬判時機 §1)', 'color': '#eab308', 'quality': 'mid', 'timing': 'unknown', 'grade': 'C', 'z': None, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質桶=mid;位階不可算(insufficient;有效點 20)—— 不硬判(§1)。'},
    ('mid', 'short', '平衡型'): {'action': '🟡 品質中等 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#eab308', 'quality': 'mid', 'timing': 'na', 'grade': 'C', 'z': None, 'flags': ['🔴 吃本金', '⬜ 評分覆蓋 3/4(缺:走勢)'], 'reason': '品質桶=mid;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('weak', 'hi', '科技股票型'): {'action': '🔴 弱且位階高 → 優先減碼 / 換', 'color': '#ef4444', 'quality': 'weak', 'timing': 'high', 'grade': 'F', 'z': 17.263, 'flags': ['🔴 吃本金'], 'reason': '品質 F × 位階 high(Z=+17.26,預設門檻)→ 🔴 弱且位階高 → 優先減碼 / 換。'},
    ('weak', 'hi', '高收益債券型'): {'action': '🔴 弱且位階高 → 優先減碼 / 換', 'color': '#ef4444', 'quality': 'weak', 'timing': 'high', 'grade': 'F', 'z': 17.263, 'flags': ['🔴 吃本金'], 'reason': '品質 F × 位階 high(Z=+17.26,預設門檻)→ 🔴 弱且位階高 → 優先減碼 / 換。'},
    ('weak', 'hi', '平衡型'): {'action': '🔴 品質弱 → 考慮換 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#ef4444', 'quality': 'weak', 'timing': 'na', 'grade': 'F', 'z': None, 'flags': ['🔴 吃本金'], 'reason': '品質桶=weak;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('weak', 'lo', '科技股票型'): {'action': '🟠 別為低基期留弱基金 → 考慮換', 'color': '#ff9800', 'quality': 'weak', 'timing': 'low', 'grade': 'F', 'z': -17.263, 'flags': ['🔴 吃本金'], 'reason': '品質 F × 位階 low(Z=-17.26,預設門檻)→ 🟠 別為低基期留弱基金 → 考慮換。'},
    ('weak', 'lo', '高收益債券型'): {'action': '🟠 別為低基期留弱基金 → 考慮換', 'color': '#ff9800', 'quality': 'weak', 'timing': 'low', 'grade': 'F', 'z': -17.263, 'flags': ['🔴 吃本金'], 'reason': '品質 F × 位階 low(Z=-17.26,預設門檻)→ 🟠 別為低基期留弱基金 → 考慮換。'},
    ('weak', 'lo', '平衡型'): {'action': '🔴 品質弱 → 考慮換 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#ef4444', 'quality': 'weak', 'timing': 'na', 'grade': 'F', 'z': None, 'flags': ['🔴 吃本金'], 'reason': '品質桶=weak;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('weak', 'mid', '科技股票型'): {'action': '🔴 表現弱 → 考慮換', 'color': '#ef4444', 'quality': 'weak', 'timing': 'mid', 'grade': 'F', 'z': 1.005, 'flags': ['🔴 吃本金'], 'reason': '品質 F × 位階 mid(Z=+1.00,預設門檻)→ 🔴 表現弱 → 考慮換。'},
    ('weak', 'mid', '高收益債券型'): {'action': '🔴 表現弱 → 考慮換', 'color': '#ef4444', 'quality': 'weak', 'timing': 'mid', 'grade': 'F', 'z': 1.005, 'flags': ['🔴 吃本金'], 'reason': '品質 F × 位階 mid(Z=+1.00,預設門檻)→ 🔴 表現弱 → 考慮換。'},
    ('weak', 'mid', '平衡型'): {'action': '🔴 品質弱 → 考慮換 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#ef4444', 'quality': 'weak', 'timing': 'na', 'grade': 'F', 'z': None, 'flags': ['🔴 吃本金'], 'reason': '品質桶=weak;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('weak', 'short', '科技股票型'): {'action': '🔴 品質弱 → 考慮換 ·位階未知(NAV 有效點不足,不硬判時機 §1)', 'color': '#ef4444', 'quality': 'weak', 'timing': 'unknown', 'grade': 'F', 'z': None, 'flags': ['🔴 吃本金'], 'reason': '品質桶=weak;位階不可算(insufficient;有效點 20)—— 不硬判(§1)。'},
    ('weak', 'short', '高收益債券型'): {'action': '🔴 品質弱 → 考慮換 ·位階未知(NAV 有效點不足,不硬判時機 §1)', 'color': '#ef4444', 'quality': 'weak', 'timing': 'unknown', 'grade': 'F', 'z': None, 'flags': ['🔴 吃本金'], 'reason': '品質桶=weak;位階不可算(insufficient;有效點 20)—— 不硬判(§1)。'},
    ('weak', 'short', '平衡型'): {'action': '🔴 品質弱 → 考慮換 ·內建配置(平衡/貨幣,不做位階擇時)', 'color': '#ef4444', 'quality': 'weak', 'timing': 'na', 'grade': 'F', 'z': None, 'flags': ['🔴 吃本金'], 'reason': '品質桶=weak;Core(平衡多重 / 貨幣市場)內建股債配置,不做 Z-Score 擇時。'},
    ('na', 'hi', '科技股票型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'high', 'grade': '—', 'z': 17.263, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'hi', '高收益債券型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'high', 'grade': '—', 'z': 17.263, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'hi', '平衡型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'na', 'grade': '—', 'z': None, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'lo', '科技股票型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'low', 'grade': '—', 'z': -17.263, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'lo', '高收益債券型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'low', 'grade': '—', 'z': -17.263, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'lo', '平衡型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'na', 'grade': '—', 'z': None, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'mid', '科技股票型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'mid', 'grade': '—', 'z': 1.005, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'mid', '高收益債券型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'mid', 'grade': '—', 'z': 1.005, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'mid', '平衡型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'na', 'grade': '—', 'z': None, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'short', '科技股票型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'unknown', 'grade': '—', 'z': None, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'short', '高收益債券型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'unknown', 'grade': '—', 'z': None, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
    ('na', 'short', '平衡型'): {'action': '⚪ 資料不足,先補歷史淨值再評', 'color': '#888888', 'quality': 'na', 'timing': 'na', 'grade': '—', 'z': None, 'flags': ['⬜ 吃本金:資料未取得／無法判定', '⬜ 評分覆蓋 0/5(缺:配息健康、匯率風險、風險調整報酬、走勢、波動)'], 'reason': '健診維度不足以評等(grade —)—— 先在管理室補歷史淨值,不在薄資料上硬給行動建議(§1)。'},
}
