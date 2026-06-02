#!/usr/bin/env python3
"""scripts/update_macro_history.py — Fund-dashboard 全球總經 FRED 歷史資料快取.

User 需求：「兩邊都可以做回測來驗證台股的總經 tab 與基金（全球的）總經 tab」+
「直接抓取資料放在資料庫，之後每周定期更新」。Sister repo my-stock-dashboard
已用 Parquet 模式做台灣指標歷史 → 本 repo 鏡像對全球 FRED.

資料流（與 stock-dashboard/update_macro_history.py 同模式）
=========================================================
data_cache/fred_indicators.parquet   ← FRED 8 series 長格式 (date, series_id, value)
data_cache/vix_history.parquet       ← VIX 日線（Yahoo ^VIX）
data_cache/spx_history.parquet       ← S&P 500 日線（^GSPC，crisis 偵測對齊用）
data_cache/metadata.json             ← 各表 last_updated + row_count

FRED 8 series（鏡像 services/macro_validation.py SCORE_RULES 直接對應）
======================================================================
- DGS10 / DGS2 / DGS3MO     殖利率（日頻；YIELD_10Y2Y / YIELD_10Y3M 由分析端 spread）
- BAMLH0A0HYM2              HY 信用利差（日頻）
- M2SL                      M2 貨幣供給（月頻；YoY 由分析端算）
- WALCL                     Fed 資產負債表（週頻；變化率由分析端算）
- CPIAUCSL                  CPI（月頻；YoY 由分析端算）
- UNRATE                    失業率（月頻）
- (PMI 暫不抓——需 OECD/Phil Fed 多源 proxy，邏輯複雜留 Phase B.2)

每週跑一次（與 fetch_nav_cache.py daily 錯開）
- 對每個 Parquet：讀取 last_date → 抓 [last_date+1, today] → append + dedupe → 寫回
- FRED 全球可達不需 proxy；VIX/SPX 走 proxy_helper 解海外 IP 封鎖（如可用）
- 任一資料源失敗：log 警告但不中止；metadata 記 last_error 供後續排查

CLI
===
    python scripts/update_macro_history.py             # 增量更新
    python scripts/update_macro_history.py --bootstrap # 砍掉重抓全部 15 年（初次部署用）
    python scripts/update_macro_history.py --years 10  # 自訂歷史長度（預設 15）
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import sys
from pathlib import Path

# v18.222 風格：scripts/ 下執行也能 import repositories.*
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import requests

CACHE_DIR = Path("data_cache")
META_PATH = CACHE_DIR / "metadata.json"

FRED_URL = "https://api.stlouisfed.org/fred/series/observations"
YF_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

# FRED series：series_id 全部走同一個抓取邏輯
FRED_SERIES_IDS: tuple = (
    "DGS10", "DGS2", "DGS3MO",
    "BAMLH0A0HYM2",
    "M2SL", "WALCL",
    "CPIAUCSL", "UNRATE",
)

DATASETS = ["fred_indicators", "vix_history", "spx_history"]


# ════════════════════════════════════════════════════════════════
# I/O Helpers
# ════════════════════════════════════════════════════════════════
def _load_existing(name: str) -> pd.DataFrame | None:
    path = CACHE_DIR / f"{name}.parquet"
    if not path.exists():
        return None
    try:
        return pd.read_parquet(path)
    except Exception as e:
        print(f"[{name}] 讀現有 Parquet 失敗：{type(e).__name__}: {e}")
        return None


def _write_parquet(name: str, df: pd.DataFrame) -> None:
    path = CACHE_DIR / f"{name}.parquet"
    df.to_parquet(path, compression="snappy", index=False)
    print(f"[{name}] ✅ 寫入 {len(df)} rows → {path}")


def _last_date(df: pd.DataFrame | None, col: str = "date") -> _dt.date | None:
    if df is None or df.empty or col not in df.columns:
        return None
    try:
        return pd.to_datetime(df[col]).max().date()
    except Exception:
        return None


def _merge_dedupe(old: pd.DataFrame | None, new: pd.DataFrame,
                  key: list[str]) -> pd.DataFrame:
    """合併 old + new，按 key（單欄或複合欄）去重保留最新；按第一個 key 排序。"""
    if old is None or old.empty:
        out = new
    else:
        out = pd.concat([old, new], ignore_index=True)
    out = (out.drop_duplicates(subset=key, keep="last")
              .sort_values(key)
              .reset_index(drop=True))
    return out


def _fetch_url_via_proxy(url: str, params: dict | None = None,
                        timeout: int = 25) -> requests.Response | None:
    """走 infra/proxy fetch_url；缺 helper 時 fallback 直連。

    fund-dashboard 的 NAS proxy 模組位置與 stock-dashboard 不同，
    這裡用 try/except 兩條路徑：infra.proxy → 直連。
    """
    try:
        from infra.proxy_helper import fetch_url  # type: ignore
        return fetch_url(url, params=params, timeout=timeout, attempts=2)
    except Exception:
        pass
    try:
        from repositories.macro_repository import fetch_url as _fu  # type: ignore
        return _fu(url, params=params, timeout=timeout)
    except Exception:
        pass
    try:
        return requests.get(url, params=params, timeout=timeout,
                            headers={"User-Agent": "Mozilla/5.0"})
    except Exception as e:
        print(f"[fetch fallback] {url[:60]} ❌ {type(e).__name__}: {e}")
        return None


# ════════════════════════════════════════════════════════════════
# FRED 抓取
# ════════════════════════════════════════════════════════════════
def _fred_get_single(series_id: str, start: _dt.date, end: _dt.date,
                     api_key: str) -> pd.DataFrame:
    """抓 FRED 單一 series，回 [date, value]；空資料/錯誤回空 DataFrame。

    FRED API 全球可達不需 proxy（直連）；印 HTTP status 方便 debug。
    """
    if not api_key:
        return pd.DataFrame()
    try:
        r = requests.get(
            FRED_URL,
            params={
                "series_id": series_id,
                "api_key": api_key,
                "file_type": "json",
                "observation_start": start.strftime("%Y-%m-%d"),
                "observation_end": end.strftime("%Y-%m-%d"),
            },
            timeout=30,
            headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        )
        if r.status_code != 200:
            print(f"[FRED/{series_id}] HTTP={r.status_code} body={r.text[:200]}")
            return pd.DataFrame()
        obs = r.json().get("observations", [])
        if not obs:
            print(f"[FRED/{series_id}] 無 observations")
            return pd.DataFrame()
        df = pd.DataFrame(obs)
        df = df[df["value"] != "."].copy()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df.dropna(subset=["value"]).reset_index(drop=True)
        print(f"[FRED/{series_id}] ✅ {len(df)} rows ({start}~{end})")
        return df[["date", "value"]]
    except Exception as e:
        print(f"[FRED/{series_id}] ❌ {type(e).__name__}: {e}")
        return pd.DataFrame()


def fetch_fred_indicators(start: _dt.date, end: _dt.date,
                          api_key: str) -> pd.DataFrame:
    """抓所有 FRED series → 長格式 (date, series_id, value).

    任一 series 失敗：log 警告，跳過該 series 但不中止其他 series。
    """
    frames = []
    for sid in FRED_SERIES_IDS:
        df = _fred_get_single(sid, start, end, api_key)
        if df.empty:
            continue
        df = df.copy()
        df["series_id"] = sid
        frames.append(df[["date", "series_id", "value"]])
    if not frames:
        return pd.DataFrame(columns=["date", "series_id", "value"])
    return pd.concat(frames, ignore_index=True)


# ════════════════════════════════════════════════════════════════
# Yahoo Finance 抓取（VIX / SPX 日線）
# ════════════════════════════════════════════════════════════════
def _yf_fetch_close(ticker: str, start: _dt.date, end: _dt.date) -> pd.DataFrame:
    """Yahoo Chart API；回 [date, close]，空資料/錯誤回空 DataFrame."""
    period1 = int(_dt.datetime.combine(start, _dt.time(0, 0)).timestamp())
    period2 = int(_dt.datetime.combine(end + _dt.timedelta(days=1),
                                       _dt.time(0, 0)).timestamp())
    url = f"{YF_CHART_BASE}/{ticker}"
    params = {"period1": period1, "period2": period2,
              "interval": "1d", "events": "history"}
    r = _fetch_url_via_proxy(url, params=params, timeout=25)
    if r is None or getattr(r, "status_code", None) != 200:
        print(f"[yf/{ticker}] HTTP={getattr(r, 'status_code', 'None')}")
        return pd.DataFrame()
    try:
        j = r.json()
        result = j["chart"]["result"][0]
        ts = result["timestamp"]
        close = result["indicators"]["quote"][0]["close"]
        df = pd.DataFrame({
            "date": [_dt.datetime.fromtimestamp(t).date() for t in ts],
            "close": close,
        })
        df = df.dropna(subset=["close"]).reset_index(drop=True)
        print(f"[yf/{ticker}] ✅ {len(df)} rows ({start}~{end})")
        return df
    except Exception as e:
        print(f"[yf/{ticker}] parse error: {type(e).__name__}: {e}")
        return pd.DataFrame()


def fetch_vix_history(start: _dt.date, end: _dt.date,
                      api_key: str = "") -> pd.DataFrame:
    """VIX 日線（^VIX）。api_key 簽名為一致性保留，VIX 不需要。"""
    _ = api_key
    return _yf_fetch_close("%5EVIX", start, end)


def fetch_spx_history(start: _dt.date, end: _dt.date,
                      api_key: str = "") -> pd.DataFrame:
    """S&P 500 日線（^GSPC，用於 crisis 對齊）."""
    _ = api_key
    return _yf_fetch_close("%5EGSPC", start, end)


FETCHERS = {
    # name: (fn, needs_fred_key, dedupe_keys)
    "fred_indicators": (fetch_fred_indicators, True, ["date", "series_id"]),
    "vix_history":     (fetch_vix_history,     False, ["date"]),
    "spx_history":     (fetch_spx_history,     False, ["date"]),
}


# ════════════════════════════════════════════════════════════════
# 主流程
# ════════════════════════════════════════════════════════════════
def update_one(name: str, today: _dt.date, bootstrap: bool, years: int,
               api_key: str) -> dict:
    """單一 dataset 增量更新；回傳 metadata 片段。"""
    fn, needs_key, dedupe_keys = FETCHERS[name]
    meta = {"name": name, "last_updated": None, "row_count": 0, "last_error": None}

    if needs_key and not api_key:
        meta["last_error"] = "FRED_API_KEY 未設定"
        print(f"[{name}] ⏭ 跳過：{meta['last_error']}")
        return meta

    existing = None if bootstrap else _load_existing(name)
    last = _last_date(existing)
    if last is None or bootstrap:
        start = today - _dt.timedelta(days=years * 365)
    else:
        start = last + _dt.timedelta(days=1)
        if start > today:
            print(f"[{name}] 已是最新（last={last}），跳過抓取")
            meta["last_updated"] = last.isoformat()
            meta["row_count"] = len(existing) if existing is not None else 0
            return meta

    print(f"[{name}] 抓 {start} ~ {today} ...")
    try:
        new = fn(start, today, api_key)
    except Exception as e:
        meta["last_error"] = f"{type(e).__name__}: {e}"
        print(f"[{name}] ❌ {meta['last_error']}")
        return meta

    if new.empty:
        meta["last_error"] = "抓取結果為空"
        print(f"[{name}] ⚠️ 抓取結果為空，保留現有資料")
        if existing is not None and not existing.empty:
            meta["last_updated"] = _last_date(existing).isoformat()
            meta["row_count"] = len(existing)
        return meta

    merged = _merge_dedupe(existing, new, key=dedupe_keys)
    _write_parquet(name, merged)
    meta["last_updated"] = _last_date(merged).isoformat()
    meta["row_count"] = len(merged)
    return meta


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--bootstrap", action="store_true",
                   help="砍掉重抓全部歷史（初次部署用）")
    p.add_argument("--years", type=int, default=15,
                   help="歷史長度（bootstrap / 缺檔時用，預設 15）")
    p.add_argument("--only", default=None,
                   help="只更新指定 dataset（debug 用，逗號分隔）")
    args = p.parse_args()

    CACHE_DIR.mkdir(exist_ok=True)
    today = _dt.date.today()
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        print("⚠️ FRED_API_KEY 未設定，fred_indicators 跳過（僅 VIX/SPX）")

    datasets = args.only.split(",") if args.only else DATASETS

    print(f"\n📊 update_macro_history.py 起跑（today={today}, bootstrap={args.bootstrap}）\n")
    metadata = {}
    for name in datasets:
        if name not in FETCHERS:
            print(f"[main] 未知 dataset: {name}")
            continue
        print(f"\n── {name} ──")
        metadata[name] = update_one(name, today, args.bootstrap, args.years, api_key)

    # 寫 metadata.json
    payload = {
        "updated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(),
        "datasets": metadata,
    }
    META_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                         encoding="utf-8")
    print(f"\n✅ metadata 寫入 → {META_PATH}")

    err_count = sum(1 for m in metadata.values() if m.get("last_error"))
    if err_count:
        print(f"⚠️ {err_count}/{len(metadata)} dataset 有錯誤，請查上方 log")
    return 0


if __name__ == "__main__":
    sys.exit(main())
