"""L2 組合績效追蹤(services/portfolio_tracking,v19.430)。

守:走勢重建(共同日對齊)、§A.7 年化閘門(<60 抹年化留累積 / <252 low_confidence)、
誠實 ok=False(空/無共同日)、權重指紋順序無關、快照列欄位對齊 PerfSnapshot + 閘門一致。
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from services.portfolio_tracking import (
    build_snapshot_row,
    reconstruct_trend,
    weights_fingerprint,
)


def _nav(n, start="2020-01-01", daily=0.001, base=10.0):
    idx = pd.bdate_range(start, periods=n)
    return pd.Series(base * (1.0 + daily) ** np.arange(n), index=idx)


# ── 走勢重建 ────────────────────────────────
def test_reconstruct_full_history_has_annualized_metrics():
    navs = {"A": _nav(300, daily=0.001), "B": _nav(300, daily=0.0005)}
    t = reconstruct_trend(navs, {"A": 0.6, "B": 0.4})
    assert t["ok"] and t["n_days"] == 299
    assert t["metrics"]["cagr_pct"] is not None
    assert t["annualized_suppressed"] is False and t["low_confidence"] is False
    assert t["curve"].iloc[-1] > 1.0                 # 上漲組合 → 累積 > 1
    assert t["metrics"]["period_return_pct"] is not None


def test_annualization_gate_suppresses_below_min_days():
    navs = {"A": _nav(40, daily=0.002), "B": _nav(40, daily=0.001)}   # n_days=39 < 60
    t = reconstruct_trend(navs, {"A": 0.5, "B": 0.5})
    assert t["ok"] and t["annualized_suppressed"] is True
    assert t["metrics"]["cagr_pct"] is None          # 年化抹掉
    assert t["metrics"]["ann_vol_pct"] is None and t["metrics"]["sharpe"] is None
    assert t["metrics"]["period_return_pct"] is not None   # 累積報酬仍在(不依賴年化)


def test_low_confidence_band_keeps_metrics():
    navs = {"A": _nav(150, daily=0.001), "B": _nav(150, daily=0.001)}  # n_days=149 ∈ [60,252)
    t = reconstruct_trend(navs, {"A": 0.5, "B": 0.5})
    assert t["ok"] and t["annualized_suppressed"] is False
    assert t["low_confidence"] is True
    assert t["metrics"]["cagr_pct"] is not None       # 仍算,只標「參考」


def test_empty_navs_ok_false_honest():
    t = reconstruct_trend({}, {})
    assert t["ok"] is False and t["reason"]           # §1 誠實原因
    assert t["curve"] is None


def test_no_common_days_ok_false():
    navs = {"A": _nav(100, start="2020-01-01"), "B": _nav(100, start="2022-01-01")}  # 無交集
    t = reconstruct_trend(navs, {"A": 0.5, "B": 0.5})
    assert t["ok"] is False


def test_single_holding_uses_own_series():
    navs = {"A": _nav(300, daily=0.001)}
    t = reconstruct_trend(navs, {"A": 999999})        # 單檔 → 歸一成 1.0
    assert t["ok"] and t["weights_norm"] == {"A": 1.0}


# ── 權重指紋 ────────────────────────────────
def test_weights_fingerprint_order_independent():
    h1, _ = weights_fingerprint({"A": 0.6, "B": 0.4})
    h2, _ = weights_fingerprint({"B": 0.4, "A": 0.6})
    assert h1 == h2                                   # 排序後算 → 順序無關


def test_weights_fingerprint_changes_on_weight_change():
    h1, _ = weights_fingerprint({"A": 0.6, "B": 0.4})
    h2, _ = weights_fingerprint({"A": 0.7, "B": 0.3})
    assert h1 != h2


# ── 快照列 ────────────────────────────────
def test_snapshot_row_fields_align_perfsnapshot():
    from repositories.portfolio_perf_repository import PerfSnapshot, _HEADERS

    navs = {"A": _nav(300, daily=0.001), "B": _nav(300, daily=0.0008)}
    row = build_snapshot_row(navs, {"A": 0.6, "B": 0.4}, total_cost_twd=500000.0,
                             today="2026-08-11", recorded_at="2026-08-11T00:00:00+00:00")
    assert set(row.keys()) == set(_HEADERS)           # 欄位完全對齊
    snap = PerfSnapshot(**row)                        # 可直接構造(不炸)
    assert snap.date == "2026-08-11" and snap.n_funds == 2
    assert snap.total_cost_twd == 500000.0


def test_snapshot_row_none_when_insufficient():
    assert build_snapshot_row({}, {}) is None          # §1 資料不足 → 不寫快照


def test_snapshot_row_respects_annualization_gate():
    navs = {"A": _nav(40, daily=0.002), "B": _nav(40, daily=0.001)}   # < 60 交易日
    row = build_snapshot_row(navs, {"A": 0.5, "B": 0.5}, today="2026-08-11")
    assert row is not None
    assert row["cagr_pct"] is None                     # 閘門一致:快照也不存誤導年化
    assert row["period_return_pct"] is not None


def test_snapshot_row_total_cost_none_ok():
    navs = {"A": _nav(300, daily=0.001), "B": _nav(300, daily=0.001)}
    row = build_snapshot_row(navs, {"A": 0.5, "B": 0.5}, total_cost_twd=None, today="2026-08-11")
    assert row["total_cost_twd"] is None               # §1 缺成本 → None 不填 0
