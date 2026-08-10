"""tests/test_grp_health_unified_merge.py — 健診總表 3 表合併器測試(v19.408)。

驗 build_merged_extra_columns:HWM σ / 風險 / MK 三組 by-code 欄位 join 成寬表,
「現價」去重、缺料檔填 '—'、無 phase 時 MK 訊號欄 '—'、空清單不炸。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from ui.helpers.fund_grp_health.unified import build_merged_extra_columns


@pytest.fixture(autouse=True)
def _seed_benchmark(monkeypatch):
    """種入基準快取 → capture_by_code 不打網路(v19.414)。

    快取值形狀 = `(抓到的時間 monotonic 秒, series)`(TTL 化後)——
    種入「現在」的時間戳,確保在 TTL 內、不會被判過期而去打網路。
    """
    import time as _t
    import ui.helpers.fund_grp_health.capture as _cap
    _d = pd.date_range("2020-01-31", periods=60, freq="ME")
    _b = pd.Series(100 * np.cumprod([1.0] + [1.005] * 59), index=_d)
    _now = _t.monotonic()
    monkeypatch.setitem(_cap._BENCH_CACHE, "SPX", (_now, _b))
    monkeypatch.setitem(_cap._BENCH_CACHE, "TWII", (_now, _b))


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


def test_build_unified_health_df_join_dedup_order():
    """①②③+extra 依 code join 成一張:去重、缺欄 None、末段接 base ③ 欄。"""
    import pandas as pd

    from ui.helpers.fund_grp_health.unified import build_unified_health_df

    base = pd.DataFrame([
        {"code": "A1", "基金名": "甲", "ccy": "USD", "配息率% (全期實際)": 4.3,
         "吃本金燈號 (1Y · MK)": "🟢 健康", "MK 3-3-3 篩": "✅ 通過"},
        {"code": "A2", "基金名": "乙", "ccy": "USD", "配息率% (全期實際)": 4.7,
         "吃本金燈號 (1Y · MK)": "🟢 健康", "MK 3-3-3 篩": "✅ 通過"},
    ])
    health = {"A1": {"4D Grade": "B", "4D Score": 66.3, "Sharpe 1Y": 0.2, "基金類別": "平衡型"}}
    div = {"A1": {"1Y 含息 %": 8.78, "每月配息 (TWD)": 6206, "換標的建議": "🟢 保留"}}
    extra = {"A1": {"現價": "12.47", "σ (年化%)": "12.0", "操作訊號": "🟡 持有"}}

    df = build_unified_health_df(base, health, div, extra)
    cols = list(df.columns)
    # 無重複欄名
    assert len(cols) == len(set(cols))
    # 順序:身分 → ① → ② → extra → base ③ 末段
    assert cols[0] == "code" and cols[1] == "基金名"
    assert cols.index("4D Grade") < cols.index("1Y 含息 %") < cols.index("現價")
    assert cols.index("現價") < cols.index("配息率% (全期實際)")   # base 末段
    r1 = df[df["code"] == "A1"].iloc[0]
    assert r1["4D Grade"] == "B" and r1["每月配息 (TWD)"] == 6206 and r1["現價"] == "12.47"
    # 缺料檔 A2:①②extra 皆缺(None/NaN,渲染為空白),但 base 欄仍在
    r2 = df[df["code"] == "A2"].iloc[0]
    assert pd.isna(r2["4D Grade"]) and r2["配息率% (全期實際)"] == 4.7


def test_empty_source_group_is_dropped():
    """來源整組空(如 Tab3 不傳 extra)→ 該組欄整批不出現(避免一排空白欄)。"""
    import pandas as pd

    from ui.helpers.fund_grp_health.unified import build_unified_health_df

    base = pd.DataFrame([{"code": "A1", "基金名": "甲", "ccy": "USD"}])
    df = build_unified_health_df(base, {"A1": {"4D Grade": "B"}}, {}, {})  # div+extra 空
    cols = list(df.columns)
    assert "4D Grade" in cols                              # health 有 → 在
    assert "現價" not in cols and "σ (年化%)" not in cols   # extra 空 → 整組不出現
    assert "每月配息 (TWD)" not in cols                     # div 空 → 整組不出現


def test_no_phase_signal_is_dash_but_levels_present():
    f = _fund("C003", metrics={"nav": 110.0, "buy1": 95, "buy3": 90})
    cols, combined = build_merged_extra_columns([f], phase="", score=None)
    assert combined["C003"]["操作訊號"] == "—"        # 無 phase → 訊號 —
    # 但買賣水平線不依景氣,仍計算(買1 來自 metrics.buy1,MK-sourced)
    assert combined["C003"]["買 1 (小跌)"] == "95.00"
