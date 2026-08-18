"""235 加碼引擎(services/ladder235.py,v19.465)。

precise:_classify 三取一 Max + 停利優先 + 各燈條件(直接餵值)。
integration:ladder_signal 週 resample / 邊界 / deploy / VIX None / 年線暫略。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.ladder235 import _classify, ladder_signal


# ── _classify:精準三取一 Max ─────────────────────────────────
def test_stop_gain_force_over_3sigma():
    assert _classify(110, 100, 100, 100, 3.5, 15)[0] == "強制停利"


def test_stop_gain_batch_2to3sigma():
    assert _classify(108, 100, 100, 100, 2.5, 15)[0] == "分批停利"


def test_stop_gain_priority_over_vix_panic():
    # 超漲(z>2)即使 VIX 恐慌也優先停利,不加碼(超漲不加碼)
    assert _classify(108, 100, 100, 100, 2.5, 35)[0] == "分批停利"


def test_lamp3_by_vix():
    assert _classify(100, 100, 100, 100, 0.0, 32)[0] == "燈三"


def test_lamp3_by_yearline_and_bollinger():
    assert _classify(90, 100, 100, 100, -2.5, 15)[0] == "燈三"   # c<MA52 且 z<-2


def test_lamp3_by_bollinger_minus3():
    assert _classify(80, 100, 100, 100, -3.5, 15)[0] == "燈三"


def test_yearline_break_alone_not_lamp3():
    # 跌破年線但布林未達 -2σ → 不逕觸發燈三(此例落 c<MA13 → 燈二)
    lamp, _ = _classify(95, 100, 98, 100, -1.5, 15)
    assert lamp == "燈二"


def test_lamp2_by_vix_and_quarterline_and_bollinger():
    assert _classify(100, 100, 100, 100, 0.0, 27)[0] == "燈二"          # VIX 25-30
    assert _classify(95, 100, 100, 100, 0.0, 15)[0] == "燈二"           # c<13週季線
    assert _classify(90, 100, 100, None, -2.5, 15)[0] == "燈二"         # 布林<-2、無年線


def test_lamp1_by_vix_and_monthline_and_bollinger():
    assert _classify(100, 100, 100, 100, 0.0, 22)[0] == "燈一"          # VIX 20-25
    assert _classify(99, 100, 98, 95, 0.0, 15)[0] == "燈一"             # c<4週月線(c≥季/年線)
    assert _classify(100, 99, 98, 95, -1.5, 15)[0] == "燈一"            # 布林<-1(c≥月線、z≥-2)


def test_cruise_and_vix_none():
    assert _classify(101, 100, 100, 100, 0.5, 15)[0] == "巡航"
    assert _classify(101, 100, 100, 100, 0.5, None)[0] == "巡航"        # 無 VIX 仍可巡航


def test_three_take_max_most_severe_wins():
    # c 同時 <月線<季線 + VIX 恐慌 → 取最嚴重(燈三)
    assert _classify(80, 100, 100, 200, -2.5, 32)[0] == "燈三"


# ── ladder_signal 整合 ───────────────────────────────────────
def _wk(values) -> pd.Series:
    idx = pd.date_range("2022-01-07", periods=len(values), freq="W-FRI")
    return pd.Series([float(v) for v in values], index=idx)


def _rising(n: int, base: float = 100.0, step: float = 0.1) -> pd.Series:
    return _wk([base + step * i for i in range(n)])


def test_insufficient_lt_20_weeks():
    r = ladder_signal(_rising(10), vix=15)
    assert r["lamp"] is None and r["status"] == "insufficient"


def test_degenerate_zero_sigma():
    r = ladder_signal(_wk([100] * 30), vix=15)            # 全同值 → σ=0
    assert r["lamp"] is None and r["status"] == "degenerate"


def test_cruise_end_to_end():
    r = ladder_signal(_rising(60), vix=15)
    assert r["status"] == "ok" and r["lamp"] == "巡航" and r["deploy_pct"] == 0.0


def test_vix_driven_lamp2_and_deploy():
    r = ladder_signal(_rising(60), vix=27, reserve_twd=100_000)
    assert r["lamp"] == "燈二" and r["deploy_pct"] == 0.30
    assert r["deploy_twd"] == 30_000                      # reserve × 30%


def test_vix_none_notes_reason():
    r = ladder_signal(_rising(60), vix=None)
    assert r["status"] == "ok" and any("無 VIX" in x for x in r["reasons"])


def test_daily_input_resamples_to_weekly():
    idx = pd.date_range("2023-01-01", periods=220, freq="D")
    s = pd.Series(100 + 0.05 * np.arange(220), index=idx)
    r = ladder_signal(s, vix=15)
    assert r["status"] == "ok" and r["weeks"] >= 20       # 日序自動 resample 成週


def test_yearline_omitted_note_under_52_weeks():
    r = ladder_signal(_rising(30), vix=15)                # 20≤週<52 → 年線暫略
    assert r["status"] == "ok" and "年線條件暫略" in r["note"]


def test_stop_gain_end_to_end():
    # 前 19 週平盤 + 末週跳高 → 20 週布林 z 遠大於 +3 → 強制停利
    r = ladder_signal(_wk([100] * 40 + [130]), vix=15)
    assert r["lamp"] == "強制停利" and r["z_bb"] > 3
