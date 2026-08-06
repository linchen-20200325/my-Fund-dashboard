"""換股池顧問編排器(services/switch_advisor.py,v19.428)。

驗型態分流:震盪(高→池中低配對 / 無配對誠實持有)、成長(雙確認賣出 / 警示 / 缺料不觸發)、無法判定。
"""
import numpy as np
import pandas as pd

from services.switch_advisor import (
    HOLD,
    INSUFFICIENT,
    SELL_CASH,
    SWITCH,
    WARN,
    advise_holding,
    advise_switches,
)

_D = pd.date_range("2022-01-03", periods=400, freq="B")


def _nav(vals):
    return pd.Series([float(v) for v in vals], index=_D[: len(vals)])


def _healthy_low_candidate(code="B"):
    """池中一支:低基期 + 通過健康過濾(4D A / 🟢 健康 / 操盤 80)。"""
    return {"code": code, "name": f"{code}基金", "type_override": "震盪",
            "σ rank": "-2.00σ", "4D Grade": "A", "吃本金燈號": "🟢 健康",
            "操盤評分": 80, "距 HWM %": -15.0, "nav_series": _nav(np.linspace(120, 90, 200))}


# ── 震盪型 ───────────────────────────────────────────────
def test_range_high_base_switches_to_pool_low():
    held = {"code": "A", "name": "A基金", "type_override": "震盪", "σ rank": "-0.20σ",
            "nav_series": _nav(np.linspace(100, 130, 200))}
    r = advise_holding(held, [_healthy_low_candidate("B")], fx_label="strong_twd")
    assert r["action"] == SWITCH and r["switch_to"]["code"] == "B"


def test_range_high_base_no_candidate_holds_honestly():
    held = {"code": "A", "type_override": "震盪", "σ rank": "-0.20σ",
            "nav_series": _nav(np.linspace(100, 130, 200))}
    r = advise_holding(held, [], fx_label="strong_twd")     # 空池
    assert r["action"] == HOLD and "無" in r["reason"]


def test_range_unhealthy_candidate_not_picked():
    held = {"code": "A", "type_override": "震盪", "σ rank": "-0.20σ",
            "nav_series": _nav(np.linspace(100, 130, 200))}
    bad = _healthy_low_candidate("B")
    bad["4D Grade"] = "F"                                     # 接刀 → 不健康
    r = advise_holding(held, [bad])
    assert r["action"] == HOLD                                # 池中無健康低基期 → 誠實持有


def test_range_low_base_holds():
    held = {"code": "A", "type_override": "震盪", "σ rank": "-2.00σ",
            "nav_series": _nav(np.linspace(100, 130, 200))}
    r = advise_holding(held, [_healthy_low_candidate()])
    assert r["action"] == HOLD and "續抱" in r["reason"]


# ── 成長型 ───────────────────────────────────────────────
def test_growth_bearish_and_breakdown_sells():
    held = {"code": "G", "type_override": "成長", "σ rank": "-0.20σ",
            "nav_series": _nav(np.linspace(200, 100, 150))}   # 下跌 → 末值 < 120SMA
    r = advise_holding(held, [], macro_composite=-8.0)
    assert r["action"] == SELL_CASH and r["signals"]["breakdown"] is True


def test_growth_bearish_no_breakdown_warns():
    held = {"code": "G", "type_override": "成長", "σ rank": "-0.20σ",
            "nav_series": _nav(np.linspace(100, 200, 150))}   # 上升 → 未跌破
    r = advise_holding(held, [], macro_composite=-8.0)
    assert r["action"] == WARN


def test_growth_macro_none_no_trigger():
    held = {"code": "G", "type_override": "成長", "σ rank": "-0.20σ",
            "nav_series": _nav(np.linspace(200, 100, 150))}
    r = advise_holding(held, [], macro_composite=None)
    assert r["action"] == HOLD and "暫不觸發" in r["reason"]


def test_growth_not_bearish_holds():
    held = {"code": "G", "type_override": "成長", "σ rank": "-0.20σ",
            "nav_series": _nav(np.linspace(200, 100, 150))}
    r = advise_holding(held, [], macro_composite=+3.0)
    assert r["action"] == HOLD and "未看衰" in r["reason"]


# ── 無法判定 ─────────────────────────────────────────────
def test_type_insufficient_history():
    held = {"code": "S", "σ rank": "-0.20σ", "nav_series": _nav(np.linspace(100, 110, 30))}
    r = advise_holding(held, [], macro_composite=-8.0)
    assert r["action"] == INSUFFICIENT and r["type"] is None


# ── 彙總 ─────────────────────────────────────────────────
def test_advise_switches_summary_counts():
    held_rows = [
        {"code": "A", "type_override": "震盪", "σ rank": "-0.20σ", "nav_series": _nav(np.linspace(100, 130, 200))},
        {"code": "G", "type_override": "成長", "σ rank": "-0.20σ", "nav_series": _nav(np.linspace(200, 100, 150))},
    ]
    res = advise_switches(held_rows, [_healthy_low_candidate("B")], fx_label="strong_twd", macro_composite=-8.0)
    s = res["summary"]
    assert s["n_holdings"] == 2 and s["n_switch"] == 1 and s["n_sell_cash"] == 1
    assert "非獲利保證" in res["caveat"]
