"""test_export_fund_db.py — fund.db 匯出：離線層讀真 parquet + live 轉換/gating（不打網路）。"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import export_fund_db as E  # noqa: E402


def test_durable_export_from_real_parquet(tmp_path):
    """離線 3 表讀 data_cache 真 parquet；live=False 不碰網路。"""
    db = tmp_path / "fund.db"
    res = E.export_all(db, live=False)
    for t in ("global_index", "fred_macro", "fund_universe"):
        assert res[t] > 0, f"{t} 應有列"

    conn = sqlite3.connect(str(db))
    cols = [d[1] for d in conn.execute("PRAGMA table_info(global_index)")]
    assert cols == ["date", "symbol", "close"]
    syms = {r[0] for r in conn.execute("SELECT DISTINCT symbol FROM global_index")}
    assert syms == {"SPX", "VIX", "TWII"}
    fcols = [d[1] for d in conn.execute("PRAGMA table_info(fred_macro)")]
    assert fcols == ["date", "series_id", "value"]
    # live 未跑 → us_market/fx 不存在
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "us_market" not in tables and "fx" not in tables
    conn.close()


def test_us_market_rows_aligns_downstream_schema():
    idx = pd.to_datetime(["2026-06-01", "2026-06-02", "2026-06-03", "2026-06-04"])
    s = pd.Series([100.0, 101.0, None, 103.0], index=idx)
    rows = E._us_market_rows(s, "NVDA")
    assert list(rows.columns) == ["date", "us_stock_id", "close"]   # 對齊 2026 消費端
    assert len(rows) == 3                                           # None 顯式剔除
    assert rows["us_stock_id"].iloc[0] == "NVDA"
    assert rows["date"].iloc[0] == "2026-06-01"


def test_us_market_rows_empty_returns_none():
    assert E._us_market_rows(pd.Series(dtype=float), "NVDA") is None
    assert E._us_market_rows(None, "NVDA") is None


def test_fx_rows_drops_na_and_requires_cols():
    df = pd.DataFrame({"date": pd.to_datetime(["2026-06-01", "2026-06-02"]),
                       "usdtwd": [32.1, None]})
    out = E._fx_rows(df)
    assert list(out.columns) == ["date", "usdtwd"]
    assert len(out) == 1                                           # None 剔除,不填 0
    with pytest.raises(RuntimeError):
        E._fx_rows(pd.DataFrame({"x": [1]}))                       # 欄位不齊 → raise


def test_us_market_gating_no_ids_skips(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "f.db"))
    try:
        assert E.write_us_market(conn, []) == -1                   # 無 ids → 略過（不造假）
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "us_market" not in tables
    finally:
        conn.close()


def test_us_market_gating_on_fetch_failure(tmp_path, monkeypatch):
    import repositories.macro.yf as yf

    def boom(ticker, range_="1y", interval="1d"):
        raise RuntimeError("模擬 proxy 不通")

    monkeypatch.setattr(yf, "fetch_yf_close", boom)
    conn = sqlite3.connect(str(tmp_path / "g.db"))
    try:
        assert E.write_us_market(conn, ["NVDA", "AMD"]) == -1       # 全抓失敗 → 略過
    finally:
        conn.close()
