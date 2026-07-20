#!/usr/bin/env python3
"""export_fund_db.py — 把 my-Fund 的重點分析資料落地成 SQLite fund.db。

供下游 2026_strategy_0719 多智能體系統讀取。「各源專案各自 export」架構(my-Fund 段)。
抽取只**呼叫既有函式或讀既有 parquet,不重算**(SSOT)。

資料分兩層(對照盤點):
* 🟢 離線層（讀 `data_cache/` parquet + `config/` json,**免 API key、免網路**）
    - `global_index`   SPX / VIX / TWII 收盤（3 個 parquet union;schema date/symbol/close）
    - `fred_macro`     FRED 9 series 長格式（date/series_id/value:DGS10/2/3MO/CPI/M2/…）
    - `fund_universe`  預設基金清單（preset_funds.json:code/name）
* 🔴 live 層（需網路 / NAS proxy;**抓不到 → Fail-Loud 略過該表 + 警告,不造假**）
    - `us_market`      連動美股收盤（fetch_yf_close;**下游 2026 讀的對齊表** date/us_stock_id/close）
    - `fx`             USDTWD 匯率（fetch_usdtwd_series;單位 rate_twd_per_usd）

（`fund_metrics`（Sharpe/回撤/NAV,calc_metrics 逐檔）為下一增量,需逐檔 NAV 抓取管線,另接。）

用法:
    FUND_DB=/volume1/data/fund.db python scripts/export_fund_db.py
    US_STOCK_IDS="NVDA,AMD,TSM" 指定要落地的連動美股。

單位鐵則(對照 CLAUDE.md §4.1):指數=點數、FRED 各異、FX 一律 rate_twd_per_usd(禁倒數)。
Fail-Loud:離線層任一表讀不到 → raise;live 層抓不到 → 略過該表 + 警告(不寫假值)。
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

import pandas as pd

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT))
_DATA_CACHE = _ROOT / "data_cache"

# 連動美股預設清單（下游 TW 標的所連動的美股;可用 env US_STOCK_IDS 覆蓋）。
_DEFAULT_US_IDS = ["NVDA", "AMD", "TSM", "AAPL", "MSFT", "SPY", "QQQ"]


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _read_parquet(name: str, cols: list[str]) -> pd.DataFrame:
    path = _DATA_CACHE / f"{name}.parquet"
    if not path.exists():
        raise RuntimeError(f"離線快取不存在:{path}（請先在 my-Fund 跑 update_macro_history）")
    df = pd.read_parquet(path)
    return df[[c for c in cols if c in df.columns]].copy()


# ── 🟢 離線層 ────────────────────────────────────────────────────────────────
def write_global_index(conn: sqlite3.Connection) -> int:
    frames = []
    for symbol, name in (("SPX", "spx_history"), ("VIX", "vix_history"), ("TWII", "twii_history")):
        df = _read_parquet(name, ["date", "close"])
        df["symbol"] = symbol
        frames.append(df[["date", "symbol", "close"]])
    out = pd.concat(frames, ignore_index=True)
    out.to_sql("global_index", conn, if_exists="replace", index=False)
    return len(out)


def write_fred_macro(conn: sqlite3.Connection) -> int:
    df = _read_parquet("fred_indicators", ["date", "series_id", "value"])
    df.to_sql("fred_macro", conn, if_exists="replace", index=False)
    return len(df)


def write_fund_universe(conn: sqlite3.Connection) -> int:
    path = _ROOT / "config" / "preset_funds.json"
    if not path.exists():
        raise RuntimeError(f"基金清單不存在:{path}")
    funds = json.loads(path.read_text(encoding="utf-8")).get("funds", [])
    rows = [{"code": f["code"], "name": f.get("name", "")} for f in funds if f.get("code")]
    if not rows:
        raise RuntimeError("基金清單為空 → 拒絕寫空表")
    pd.DataFrame(rows).to_sql("fund_universe", conn, if_exists="replace", index=False)
    return len(rows)


# ── 🔴 live 層（pure transform 抽出以利單測；抓取失敗 → 略過 + 警告） ─────────────
def _us_market_rows(s, us_stock_id: str):
    """fetch_yf_close 的 Series（date index, close）→ (date, us_stock_id, close)。"""
    if s is None or len(s) == 0:
        return None
    ser = s.dropna()
    if ser.empty:
        return None
    return pd.DataFrame({
        "date": [str(d)[:10] for d in ser.index],
        "us_stock_id": us_stock_id,
        "close": [float(v) for v in ser.values],
    })


def write_us_market(conn: sqlite3.Connection, us_ids: list[str]) -> int:
    """連動美股收盤 → us_market（下游對齊表;抓不到 → 略過 + 警告）。"""
    from repositories.macro.yf import fetch_yf_close

    frames = []
    for tk in us_ids:
        try:
            s = fetch_yf_close(tk, range_="1y")
        except Exception as exc:  # noqa: BLE001 — 單檔抓取失敗不拖垮其他（網路/proxy）
            _log(f"  us_market：{tk} 抓取失敗（{exc}）跳過")
            continue
        part = _us_market_rows(s, tk)
        if part is not None and not part.empty:
            frames.append(part)
    if not frames:
        _log("⚠️ 略過 us_market：所有連動美股皆無資料（網路 / NAS proxy?）不造假")
        return -1
    out = pd.concat(frames, ignore_index=True)
    out.to_sql("us_market", conn, if_exists="replace", index=False)
    return len(out)


def _fx_rows(df: pd.DataFrame) -> pd.DataFrame:
    """fetch_usdtwd_series 的 df → (date, usdtwd)。單位 rate_twd_per_usd。"""
    if df is None or df.empty:
        raise RuntimeError("USDTWD 序列為空")
    d = df.copy()
    d.columns = [str(c).lower() for c in d.columns]
    if "date" not in d.columns or "usdtwd" not in d.columns:
        raise RuntimeError(f"USDTWD 欄位不齊:{list(d.columns)}")
    d = d[d["usdtwd"].notna()]
    d["date"] = d["date"].astype(str).str[:10]
    return d[["date", "usdtwd"]]


def write_fx(conn: sqlite3.Connection, days: int = 180) -> int:
    """USDTWD 匯率 → fx（抓不到 → 略過 + 警告）。"""
    from repositories.hot_money_repository import fetch_usdtwd_series

    try:
        df, err = fetch_usdtwd_series(days)
    except Exception as exc:  # noqa: BLE001
        _log(f"⚠️ 略過 fx：USDTWD 抓取失敗（{exc}）")
        return -1
    if df is None or df.empty:
        _log(f"⚠️ 略過 fx：{err or '空序列'}")
        return -1
    out = _fx_rows(df)
    out.to_sql("fx", conn, if_exists="replace", index=False)
    return len(out)


# ── 主流程 ───────────────────────────────────────────────────────────────────
_DURABLE = [
    ("global_index", write_global_index),
    ("fred_macro", write_fred_macro),
    ("fund_universe", write_fund_universe),
]


def export_all(db_path: Path, *, live: bool = True, us_ids: list[str] | None = None) -> dict[str, int]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    result: dict[str, int] = {}
    try:
        for name, fn in _DURABLE:                 # 離線層：任一失敗即 raise（Fail-Loud）
            result[name] = fn(conn)
        if live:
            result["us_market"] = write_us_market(conn, us_ids or _DEFAULT_US_IDS)
            result["fx"] = write_fx(conn)
        conn.commit()
    finally:
        conn.close()
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="產生 fund.db 供多智能體系統讀取")
    parser.add_argument("--output", help="fund.db 路徑（預設 env FUND_DB 或 ./fund.db）")
    parser.add_argument("--no-live", action="store_true", help="只產離線層（不抓美股 / 匯率）")
    args = parser.parse_args(argv)

    out = Path(args.output or os.environ.get("FUND_DB") or "fund.db")
    ids = [s.strip().upper() for s in os.environ.get("US_STOCK_IDS", "").split(",") if s.strip()]
    result = export_all(out, live=not args.no_live, us_ids=ids or None)

    print(f"✅ fund.db 已更新 → {out}")
    for name, n in result.items():
        print(f"   {name}: {'略過(抓不到/離線)' if n < 0 else f'{n} 列'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
