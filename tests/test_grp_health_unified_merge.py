"""tests/test_grp_health_unified_merge.py — 健診總表 3 表合併器測試(v19.408)。

驗 build_merged_extra_columns:HWM σ / 風險 / MK 三組 by-code 欄位 join 成寬表,
「現價」去重、缺料檔填 '—'、無 phase 時 MK 訊號欄 '—'、空清單不炸。
"""
from __future__ import annotations

import pandas as pd

from ui.helpers.fund_grp_health.unified import build_merged_extra_columns


def _fund(code, *, series=True, metrics=None):
    s = None
    if series:
        idx = pd.date_range("2024-01-01", periods=300, freq="D")
        s = pd.Series([100 + (i % 20) for i in range(300)], index=idx)
    return {"code": code, "name": f"基金{code}", "series": s,
            "metrics": metrics or {}, "risk_metrics": {}, "moneydj_raw": {}}


def test_empty_funds():
    cols, combined = build_merged_extra_columns([], phase="擴張", score=6.0)
    assert cols == [] or isinstance(cols, list)
    assert combined == {}


def test_column_order_and_dedup_price():
    f = _fund("A001", metrics={"std_1y": 12.0, "sharpe": 1.1, "nav": 110.0,
                               "buy1": 95, "buy3": 90, "sell1": 115, "sell3": 120})
    cols, combined = build_merged_extra_columns([f], phase="擴張", score=6.0)
    # 現價只出現一次(HWM 版優先,MK 版略過)
    assert cols.count("現價") == 1
    # 三組欄位都在
    for _c in ("HWM", "σ rank", "Sharpe", "Beta", "操作訊號", "現價位階"):
        assert _c in cols
    assert combined["A001"]["Sharpe"] == "1.10"


def test_missing_series_gets_dash():
    f = _fund("B002", series=False)
    cols, combined = build_merged_extra_columns([f], phase="擴張", score=6.0)
    assert combined["B002"]["現價"] == "—"
    assert "NAV 不足" in combined["B002"]["HWM 位階"]


def test_no_phase_signal_is_dash_but_levels_present():
    f = _fund("C003", metrics={"nav": 110.0, "buy1": 95, "buy3": 90})
    cols, combined = build_merged_extra_columns([f], phase="", score=None)
    assert combined["C003"]["操作訊號"] == "—"        # 無 phase → 訊號 —
    # 但買賣水平線不依景氣,仍計算(買1 來自 metrics.buy1,MK-sourced)
    assert combined["C003"]["買 1 (小跌)"] == "95.00"
