"""v19.458 深度強化 4 模組 —— 回歸測試(邏輯 + 邊界)。

① allocation_ladder(composite→水位+景氣門檻)② zscore_engine(Z 位階+分流)
③ switch_state_machine(狀態機+Alpha/勝率)④ lookthrough_coverage(穿透時效+覆蓋率)。
全為純函式,離線可測。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _nav(vals) -> pd.Series:
    idx = pd.bdate_range("2019-01-01", periods=len(vals))
    return pd.Series([float(v) for v in vals], index=idx)


# ════════════════════════ ① allocation_ladder ════════════════════════
def test_ndc_light_bands():
    from services.allocation_ladder import ndc_light
    assert ndc_light(12)[0] == "藍"
    assert ndc_light(25)[0] == "綠"
    assert ndc_light(40)[0] == "紅"
    assert ndc_light(None) == (None, None)
    assert ndc_light(100) == (None, None)          # 超域 → 不硬歸(§1)


def test_dynamic_zscore_gates_by_light():
    from services.allocation_ladder import dynamic_zscore_gates
    assert dynamic_zscore_gates(25)["stop_gain_z"] == 2.0     # 綠燈放寬停利
    assert dynamic_zscore_gates(40)["add_z"] == -1.5          # 紅燈收緊加碼
    _d = dynamic_zscore_gates(None)
    assert _d["source"] == "default" and _d["light"] is None  # 無燈號誠實標明


def test_allocation_from_composite_levels():
    from services.allocation_ladder import allocation_from_composite
    _hi = allocation_from_composite(15.0, ndc_score=25)       # 極度樂觀 + 綠燈
    assert _hi["status"] == "ok" and _hi["level"] == "極度樂觀"
    assert _hi["allocation"]["equity"] == 85 and _hi["stop_gain_z"] == 2.0
    _lo = allocation_from_composite(-15.0)                    # 極度悲觀
    assert _lo["level"] == "極度悲觀" and _lo["allocation"]["cash"] == 35
    assert allocation_from_composite(None)["status"] == "unknown"   # 缺分 → 不猜(§1)


def test_allocation_does_not_mutate_ssot():
    from shared.signal_thresholds import ALLOCATION_LADDER
    from services.allocation_ladder import allocation_from_composite
    _r = allocation_from_composite(15.0)
    _r["allocation"]["equity"] = 999
    assert ALLOCATION_LADDER["極度樂觀"]["equity"] == 85     # copy,未污染 SSOT


# ════════════════════════ ② zscore_engine ════════════════════════
def test_nav_zscore_basic_and_edges():
    from services.zscore_engine import nav_zscore
    _r = nav_zscore(_nav([10.0] * 299 + [11.0]))             # 末點高於均線
    assert _r["status"] == "ok" and _r["z"] > 5 and _r["n"] == 300
    assert nav_zscore(_nav([10.0] * 300))["status"] == "degenerate"   # σ=0 → z None
    assert nav_zscore(_nav([10.0] * 300))["z"] is None
    assert nav_zscore(_nav([10.0] * 100))["status"] == "insufficient"  # <252 → None
    assert nav_zscore(_nav([10.0]))["z"] is None                       # 太短


def test_is_core_bucket():
    from services.zscore_engine import is_core_bucket
    assert is_core_bucket("平衡型基金") is True              # 平衡多重 = Core
    assert is_core_bucket("貨幣市場基金") is True
    assert is_core_bucket("科技類股基金") is False           # 股票 → 非 Core


def test_rebalance_signal_flow():
    from services.zscore_engine import rebalance_signal
    # Core → 不做 Z-Score 擇時
    _c = rebalance_signal(_nav([10.0] * 300), category="平衡型")
    assert _c["applies"] is False
    # 非 Core + 位階高 → 停利(無燈號用預設門檻 1.75)
    _hi = rebalance_signal(_nav([10.0] * 299 + [11.0]), category="科技股票")
    assert _hi["applies"] is True and _hi["action"] == "停利/減碼"
    # 非 Core + 位階低 → 加碼
    _lo = rebalance_signal(_nav([11.0] * 299 + [10.0]), category="科技股票")
    assert _lo["action"] == "加碼/逢低"
    # 綠燈放寬停利:同一序列 z 不變,但綠燈門檻 2.0 vs 預設 1.75(此處 z 很大兩者都觸發,測門檻帶入)
    _g = rebalance_signal(_nav([10.0] * 299 + [11.0]), category="科技股票", ndc_score=25)
    assert _g["stop_gain_z"] == 2.0 and _g["light"] == "綠"


# ════════════════════════ ③ switch_state_machine ════════════════════════
def test_state_machine_transitions():
    from services.switch_state_machine import next_status
    assert next_status("WATCHING", "trigger")["status"] == "TRIGGERED"
    assert next_status("TRIGGERED", "execute")["status"] == "HOLDING"
    assert next_status("HOLDING", "close")["status"] == "CLOSED"
    assert next_status("TRIGGERED", "cancel")["status"] == "WATCHING"
    _bad = next_status("WATCHING", "execute")                # 非法轉移
    assert _bad["valid"] is False and _bad["status"] == "WATCHING"   # 維持現狀(§1)
    assert next_status("HOLDING", "hold")["changed"] is False        # 合法 no-op


def test_transition_result_alpha_and_win():
    from services.switch_state_machine import aggregate_winrate, transition_result
    _r = transition_result(10.0, 12.0, benchmark_entry=100.0, benchmark_exit=105.0)
    assert _r["fund_return_pct"] == 20.0 and _r["benchmark_return_pct"] == 5.0
    assert _r["alpha_pct"] == 15.0 and _r["win"] is True
    assert transition_result(0.0, 12.0)["fund_return_pct"] is None    # 起點0 不除零(§4.4)
    _nb = transition_result(10.0, 12.0)                               # 無基準 → alpha None
    assert _nb["alpha_pct"] is None and _nb["win"] is None
    _agg = aggregate_winrate([_r, transition_result(10.0, 9.0, 100.0, 105.0), _nb])
    assert _agg["n"] == 3 and _agg["n_scored"] == 2 and _agg["wins"] == 1
    assert _agg["winrate"] == 0.5                                     # 缺基準的不灌水(§1)


def test_pool_entry_status_backward_compat():
    from repositories.pool_repository import PoolEntry
    # 舊 6 欄列(無 status)→ pad → 預設 WATCHING(向後相容)
    _old = PoolEntry.from_row(["ACTI71", "聯博", "股票", "", "", "2026-01-01"])
    assert _old.status == "WATCHING"
    # v19.472:選股池併入對照表 → 再 +isin/currency/morningstar_secid,共 10 欄(仍 additive 向後相容)
    assert len(_old.to_row()) == 10
    assert _old.isin == "" and _old.currency == "" and _old.morningstar_secid == ""
    # 有 status 列
    _new = PoolEntry.from_row(["X", "n", "c", "", "", "d", "holding"])
    assert _new.status == "HOLDING"                                   # 正規化大寫
    assert PoolEntry(code="Y", status="bogus").status == "WATCHING"   # 非法 → 預設


# ════════════════════════ ④ lookthrough_coverage ════════════════════════
def _fund(code, invest, tops_pcts, fetched_at):
    return {"code": code, "invest_twd": invest, "loaded": True,   # usable_funds 需 loaded
            "series": _nav([10.0, 10.1, 10.2]),
            "moneydj_raw": {"holdings": {
                "top_holdings": [{"name": f"S{i}", "pct": p} for i, p in enumerate(tops_pcts)],
                "fetched_at": fetched_at}}}


def test_lookthrough_coverage_weighted_and_stale():
    from ui.helpers.portfolio.concentration import lookthrough_coverage
    _recent = (pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=5)).isoformat()
    # 覆蓋 40%(投 10 萬)+ 80%(投 30 萬)→ 加權 = (10×0.4+30×0.8)/40 = 70%
    _funds = [_fund("A", 100000, [20, 20], _recent), _fund("B", 300000, [40, 40], _recent)]
    _r = lookthrough_coverage(_funds)
    assert _r["coverage_pct"] == 70.0 and _r["is_stale"] is False and _r["n_with_holdings"] == 2

    # 過期成分 → 落後推估下限
    _stale = lookthrough_coverage([_fund("A", 100000, [30, 30], "2020-01-01T00:00:00+00:00")])
    assert _stale["is_stale"] is True and "落後推估下限" in (_stale["note"] or "")

    # 無成分 → coverage None(不假裝完整,§1)
    _none = lookthrough_coverage([{"code": "Z", "invest_twd": 100, "loaded": True,
                                   "series": _nav([10, 10, 10]), "moneydj_raw": {}}])
    assert _none["coverage_pct"] is None


def test_ndc_score_from_result():
    """v19.459:NDC fetcher 結果取 score_latest(9~45);超域/非數/非dict → None(§1)。"""
    from ui.helpers.macro.ndc import ndc_score_from_result
    assert ndc_score_from_result({"score_latest": 25}) == 25
    assert ndc_score_from_result({"score_latest": "23"}) == 23     # 字串數字 → int
    assert ndc_score_from_result({"score_latest": None}) is None
    assert ndc_score_from_result({"score_latest": 5}) is None       # <9 超域
    assert ndc_score_from_result({"score_latest": 99}) is None      # >45 超域
    assert ndc_score_from_result({}) is None                        # 無 key
    assert ndc_score_from_result(None) is None                      # 非 dict
