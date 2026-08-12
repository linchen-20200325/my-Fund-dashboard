"""L2 switch_advisor 表現差觸發 + 選股池 overlay(v19.430)。

守:assess_underperformance(跑輸大盤門檻/紅燈/OR/缺料誠實)、advise_holding overlay
(HOLD→補選股池標的、池空誠實、SELL_CASH 不叫買、非表現差不動)、advise_switches n_underperforming。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import services.switch_advisor as sa
from services.switch_advisor import (
    assess_underperformance,
    advise_holding,
    advise_switches,
)


def _lin(v0, v1, n=20, start="2020-06-01"):
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(np.linspace(v0, v1, n), index=idx)


# ── assess_underperformance:跑輸大盤 ────────────────────────
def test_lags_benchmark_triggers_beyond_threshold():
    fund = _lin(10, 10.2)          # +2%
    bench = _lin(100, 110)         # +10% → excess = −8pp < −5
    r = assess_underperformance(fund_nav=fund, benchmark_nav=bench, benchmark_label="TWII")
    assert r["is_underperforming"] is True
    assert "跑輸大盤" in r["reasons"] and r["excess_pct"] == -8.0
    assert r["benchmark_used"] == "TWII"


def test_lag_boundary_exactly_threshold_not_triggered():
    fund = _lin(10, 10)            # 0%
    bench = _lin(100, 105)         # +5% → excess = −5.0,**非** < −5 → 不觸發(嚴格 <)
    r = assess_underperformance(fund_nav=fund, benchmark_nav=bench, benchmark_label="TWII")
    assert r["lags_benchmark"] is False and r["is_underperforming"] is False
    assert r["excess_pct"] == -5.0


def test_no_benchmark_skips_lag_honestly():
    fund = _lin(10, 9)             # 跌但沒大盤可比
    r = assess_underperformance(fund_nav=fund, benchmark_nav=None, benchmark_label=None)
    assert r["lags_benchmark"] is False and r["excess_pct"] is None
    assert r["is_underperforming"] is False        # §1 無可比 → 不臆測


# ── assess_underperformance:絕對虧損(紅燈)────────────────────
def test_absolute_loss_via_explicit_redlight():
    r = assess_underperformance(redlight=True)
    assert r["is_underperforming"] is True and "絕對虧損" in r["reasons"]
    assert r["redlight"] is True


def test_absolute_loss_via_switch_signal_severe_eat():
    r = assess_underperformance(eat_status="🔴 嚴重吃本金(報酬為負)")   # switch_signal → RED
    assert r["is_underperforming"] is True and r["redlight"] is True
    assert "🔴 嚴重吃本金" in r["reasons"]        # 講白吃本金,不籠統「絕對虧損」


def test_redlight_without_severe_eat_labels_generic_loss():
    """紅燈但非吃本金(含息<0且Sharpe<0)→ reason 仍籠統「絕對虧損」。"""
    r = assess_underperformance(tr1y_pct=-2.0, sharpe=-0.3, eat_status="", switch_score=50.0)
    assert "絕對虧損" in r["reasons"] and "嚴重吃本金" not in "".join(r["reasons"])


def test_plain_eating_red_positive_return_triggers_and_labels():
    """plain 🔴 吃本金(正報酬但配息>報酬,無「嚴重」)→ 仍紅燈,reason 標「吃本金(配息侵蝕本金)」。"""
    r = assess_underperformance(eat_status="🔴 吃本金")     # switch_signal 不認,eat_is_red 補
    assert r["is_underperforming"] is True and r["redlight"] is True
    assert "🔴 吃本金(配息侵蝕本金)" in r["reasons"]
    assert "嚴重" not in "".join(r["reasons"])


def test_absolute_loss_via_neg_return_neg_sharpe():
    r = assess_underperformance(tr1y_pct=-2.0, sharpe=-0.3, eat_status="", switch_score=50.0)
    assert r["redlight"] is True and r["is_underperforming"] is True


def test_no_inputs_not_underperforming():
    r = assess_underperformance()
    assert r["is_underperforming"] is False and r["redlight"] is None


def test_or_logic_lag_only():
    fund = _lin(10, 10.1)          # +1%
    bench = _lin(100, 110)         # +10% → excess −9 → lag
    r = assess_underperformance(fund_nav=fund, benchmark_nav=bench,
                                tr1y_pct=8.0, sharpe=1.0, eat_status="🟢 健康", switch_score=80.0)
    assert r["lags_benchmark"] is True and r["redlight"] is False
    assert r["is_underperforming"] is True         # OR:跑輸即成立


# ── advise_holding overlay ────────────────────────
_UNDER = {"is_underperforming": True, "reasons": ["跑輸大盤"], "excess_pct": -8.0,
          "benchmark_used": "TWII", "full_period": False, "redlight": None, "lags_benchmark": True}


def _hold_row(**kw):
    base = {"code": "AAA", "name": "持倉A", "type_override": "震盪",
            "σ rank": -1.0, "nav_series": None}          # σ=-1.0 → mid → HOLD
    base.update(kw)
    return base


def test_overlay_hold_attaches_pool_candidate(monkeypatch):
    monkeypatch.setattr(sa, "_best_candidate",
                        lambda code, pool: {"code": "BBB", "name": "替代B", "type": "震盪",
                                            "buy_sigma": -1.8, "potential_pct": 10.0})
    out = advise_holding(_hold_row(), pool_rows=[{"code": "BBB"}], underperformance=_UNDER)
    assert out["action"] == sa.HOLD                       # 型態動作不被覆蓋
    assert out["underperf_candidate"]["code"] == "BBB"
    assert "表現差" in out["reason"] and "替代B" in out["reason"]


def test_overlay_hold_empty_pool_is_honest(monkeypatch):
    monkeypatch.setattr(sa, "_best_candidate", lambda code, pool: None)
    out = advise_holding(_hold_row(), pool_rows=[], underperformance=_UNDER)
    assert out["underperf_candidate"] is None
    assert "無合適替代標的" in out["reason"]                # §1 不硬湊


def test_not_underperforming_no_overlay():
    out = advise_holding(_hold_row(), pool_rows=[])       # 無 underperformance 傳入
    assert out["underperformance"]["is_underperforming"] is False
    assert out["underperf_candidate"] is None
    assert "表現差" not in out["reason"]


def test_overlay_sell_cash_does_not_suggest_buy(monkeypatch):
    # 成長型 + 總經看衰 + 跌破均線 → SELL_CASH;表現差 overlay 不應叫買
    monkeypatch.setattr(sa, "_best_candidate",
                        lambda code, pool: {"code": "X", "name": "不該出現", "type": "震盪",
                                            "buy_sigma": -2.0, "potential_pct": 5.0})
    nav = _lin(20, 10, n=130)                             # 130 點下跌 → 末值 < 120日均線 → 跌破
    row = {"code": "G1", "name": "成長股", "type_override": "成長", "nav_series": nav}
    out = advise_holding(row, pool_rows=[{"code": "X"}], macro_composite=-10.0,
                         underperformance=_UNDER)
    assert out["action"] == sa.SELL_CASH
    assert out["underperf_candidate"] is None             # 已轉現金 → 不新進場
    assert "轉現金" in out["reason"]


# ── advise_switches summary ────────────────────────
def test_advise_switches_counts_underperforming(monkeypatch):
    monkeypatch.setattr(sa, "_best_candidate", lambda code, pool: None)
    rows = [_hold_row(code="AAA"), _hold_row(code="CCC")]
    ubc = {"AAA": _UNDER}                                 # 只有 AAA 表現差
    res = advise_switches(rows, pool_rows=[], underperformance_by_code=ubc)
    assert res["summary"]["n_underperforming"] == 1
    assert res["summary"]["n_holdings"] == 2
