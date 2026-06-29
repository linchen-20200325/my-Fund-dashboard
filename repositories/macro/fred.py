"""repositories/macro/fred.py — FRED series 抓取(B1 拆自 macro_repository v19.205).

從原 1078 LOC god module 拆出:
- FRED URL 常數 + 本地 cache helpers
- fred_get_next_release_date(查下次發布日)
- fetch_fred / fetch_fred_batch
"""
from __future__ import annotations

import datetime as _dt
import json as _json
import os as _os
from typing import Optional

import pandas as pd

from infra.proxy import fetch_url
from fund_fetcher import _ttl_cache, register_cache
from shared.macro_thresholds_v2 import (
    CPI_YOY_THRESHOLDS as _CPI_THR,
    HY_SPREAD_THRESHOLDS as _HY_THR,
)
from shared.ttls import TTL_30MIN

_HY_SPREAD_STOPLIGHT = _HY_THR["stoplight"]
_CPI_STOPLIGHT = _CPI_THR["stoplight"]

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_RELEASE_BASE = "https://api.stlouisfed.org/fred/series/release"
FRED_RELEASE_DATES_BASE = "https://api.stlouisfed.org/fred/release/dates"

_FRED_RELEASE_CACHE_DIR = _os.path.join("cache", "fred_release")
_FRED_RELEASE_CACHE_TTL_DAYS = 30


def _fred_release_cache_path(series_id: str) -> str:
    return _os.path.join(_FRED_RELEASE_CACHE_DIR, f"{series_id}.json")


def _fred_release_cache_load(series_id: str) -> Optional[dict]:
    path = _fred_release_cache_path(series_id)
    if not _os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = _json.load(fh)
        ts = _dt.datetime.fromisoformat(data["cached_at"])
        if (_dt.datetime.now() - ts).days >= _FRED_RELEASE_CACHE_TTL_DAYS:
            return None
        return data
    except Exception:
        return None


def _fred_release_cache_save(series_id: str, payload: dict) -> None:
    try:
        _os.makedirs(_FRED_RELEASE_CACHE_DIR, exist_ok=True)
        payload = dict(payload)
        payload["cached_at"] = _dt.datetime.now().isoformat()
        with open(_fred_release_cache_path(series_id), "w", encoding="utf-8") as fh:
            _json.dump(payload, fh, ensure_ascii=False)
    except Exception as e:
        print(f"[macro_core/fred_release] cache save 失敗 {series_id}: {e}")


def fred_get_next_release_date(series_id: str, api_key: str) -> Optional[_dt.date]:
    """查詢指定 FRED series 的下次預定 release 日。

    流程：
      1. 先讀本地 cache（30 天 TTL，避免每次 rerun 都打 API）
      2. 呼叫 /fred/series/release 取 release_id
      3. 呼叫 /fred/release/dates 取「今日起」未來最近一筆 release date

    Returns
    -------
    datetime.date | None
        下次 release 日；任一步驟失敗回 None（呼叫端應 fallback 到舊閾值）。
    """
    if not series_id or not api_key:
        return None

    cached = _fred_release_cache_load(series_id)
    today = _dt.date.today()
    if cached:
        try:
            nrd = _dt.date.fromisoformat(cached.get("next_release_date", ""))
            # cache 日已過 → 視為失效，重抓
            if nrd >= today:
                return nrd
        except Exception:
            pass

    # 1. 取 release_id
    try:
        r1 = fetch_url(
            FRED_RELEASE_BASE,
            params={"series_id": series_id, "api_key": api_key, "file_type": "json"},
            timeout=15,
        )
        if r1 is None:
            return None
        releases = r1.json().get("releases", [])
        if not releases:
            return None
        release_id = releases[0].get("id")
        if not release_id:
            return None
    except Exception as e:
        print(f"[macro_core/fred_release] {series_id} release_id 解析失敗: {e}")
        return None

    # 2. 取未來 release dates
    try:
        r2 = fetch_url(
            FRED_RELEASE_DATES_BASE,
            params={
                "release_id": release_id,
                "api_key":    api_key,
                "file_type":  "json",
                "include_release_dates_with_no_data": "true",
                "realtime_start": today.isoformat(),
                "realtime_end": (today + _dt.timedelta(days=120)).isoformat(),
                "sort_order": "asc",
                "limit":      20,
            },
            timeout=15,
        )
        if r2 is None:
            return None
        dates = r2.json().get("release_dates", [])
        for d in dates:
            try:
                cand = _dt.date.fromisoformat(d.get("date", ""))
                if cand >= today:
                    _fred_release_cache_save(series_id, {
                        "release_id": release_id,
                        "next_release_date": cand.isoformat(),
                    })
                    return cand
            except Exception:
                continue
    except Exception as e:
        print(f"[macro_core/fred_release] {series_id} release_dates 解析失敗: {e}")
        return None

    return None


# ══════════════════════════════════════════════════════════════
# 統一閾值表 — 僅限「全球/美國」指標
#   兩邊共用一份標準,避免同一個 VIX 在兩個系統有兩套判讀。
#   台灣獨有指標(PCR / 外資期貨 / BIAS240 等)請放在 stock 端自有模組,
#   不要混進這張表,以免污染 fund 端的全球視角。
# ══════════════════════════════════════════════════════════════
MACRO_THRESHOLDS: dict = {
    "VIX":         {"green_below": 18, "yellow_above": 22, "red_above": 30},
    # F-GRAY-4 v19.183: CPI stoplight 由 shared/macro_thresholds_v2.py SSOT 提供
    # 既有值 {1.5/2.5/3.5/4.0} 不變,只把 dict literal 替換成 SSOT import。
    "CPI":         _CPI_STOPLIGHT,
    "US10Y":       {"yellow_above": 4.5, "red_above": 5.0},
    "DXY":         {"yellow_above": 105, "red_above": 110},
    "PMI":         {"red_below": 46, "yellow_below": 50, "green_above": 52},
    # F-GRAY-4 v19.169: HY_SPREAD stoplight 閾值由 shared/macro_thresholds_v2.py SSOT 提供
    "HY_SPREAD":   _HY_SPREAD_STOPLIGHT,
    "YIELD_10Y2Y": {"red_below": 0.0, "yellow_below": 0.5},
    "YIELD_10Y3M": {"red_below": 0.0, "yellow_below": 0.5},
    "M2_YOY":      {"red_below": 0.0, "green_above": 5.0},
    "FED_BS_YOY":  {"red_below": -5.0, "green_above": 5.0},
    # v18.107 跨幣別
    "EURUSD":      {"green_above": 1.15, "yellow_below": 1.10, "red_below": 1.05},
    "USDJPY":      {"green_below": 140.0, "yellow_above": 150.0, "red_above": 155.0},
    "USDCNH":      {"green_below": 7.0, "yellow_above": 7.15, "red_above": 7.3},
    # v19.71 SSOT 補完：以下 13 個閾值為**文件參考用**,目前 production 仍用 inline conditional。
    #
    # ⚠️ F-GRAY-4 v19.80 audit 釐清(2026-06-23):原 v19.71 註解稱「完全等價」過度承諾,
    # 實際 inline 與本 dict **語意不同源**:
    #   - inline 服務多種用途(signal classification / score function / regime ID /
    #     inflection detection),同一指標在不同 site 有不同閾值
    #   - 本 dict 為單一「stoplight 紅黃綠燈」schema,無法表達多用途閾值
    #   - 範例:
    #     * VIX dict red_above=30 vs inline `> 25`(macro_service.py:1119,其他 site `> 30`)
    #     * PMI dict green_above=52 vs inline `>= 50`(:324, score function 用)
    #     * (CPI 已於 v19.183 完整 v2 SSOT 化:dict 走 _CPI_THR["stoplight"],
    #        inflection / regime / score / beginner_panic 各走 v2 對應子 dict)
    #   - 結論:**不應**機械式 swap inline → dict,需逐 site 評估語意才能 harmonize
    #
    # 動態閾值(FED_RATE 的 v<prev / NEW_HOME 的 v>prev / ADL 的 chg)與多階分數
    # (NFP 5 級評分)schema 不相容,暫不收錄。
    "FED_RATE":       {"red_above": 5.0},                                  # green 為 v<prev 動態，dict 僅靜態 red
    "UNEMPLOYMENT":   {"green_below": 4.5, "red_above": 6.0},
    "PPI":            {"green_low": 0.0, "green_high": 3.0, "red_above": 5.0, "red_below": -1.0},
    "COPPER":         {"green_above": 2.0, "red_below": -5.0},             # 月變動 %
    "CONSUMER_CONF":  {"green_above": 80.0, "red_below": 60.0},
    "JOBLESS":        {"green_below": 230000, "red_above": 300000},        # 人數（週頻）
    "SAHM":           {"yellow_above": 0.3, "red_above": 0.5},
    "SLOOS":          {"yellow_above": 0.0, "red_above": 20.0},            # 銀行緊縮放貸 %
    "LEI":            {"green_above": 0.0, "red_below": -0.7},             # CFNAI z-score
    "CONT_CLAIMS":    {"green_below": 1700000, "red_above": 1900000},      # 人數
    "M2_WEEKLY":      {"red_below": 0.0, "green_above": 5.0},              # 與 M2_YOY 同 YoY 規則
    "INFL_EXP_5Y":    {"green_low": 1.5, "green_high": 2.8, "red_above": 3.5},
    "PERMIT_HOUSING": {"green_above": 1500, "red_below": 1200},            # 千戶
}


# ══════════════════════════════════════════════════════════════
# 資料抓取(全部走 NAS proxy)
# ══════════════════════════════════════════════════════════════

@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=32)   # v18.58: FRED 日頻
def fetch_fred(series_id: str, api_key: str, n: int = 250) -> pd.DataFrame:
    """
    抓取 FRED 經濟序列(透過 NAS proxy)。

    Returns
    -------
    pd.DataFrame  欄位:
        - `date` (Timestamp):資料歸屬日(observation_date)
        - `value` (float):指標數值
        - `realtime_start` (Timestamp):FRED 該筆觀測首次發布日(v19.60 D1)
        - `source` (str):血緣標識,"FRED:<series_id>"(F-PROV-1 v19.82 新增)
        - `fetched_at` (str):本次抓取的 UTC ISO 時間(F-PROV-1 v19.82 新增)

    失敗時回傳空 DataFrame(無欄位,caller 須先 `df.empty` 判斷)。

    v19.60 D1:`realtime_start` ≈ BLS/FED 真實 publish 時間,用於 UI chip
    區分「資料月份」與「真實發布日」(PIT 對齊鍵)。

    v19.82 F-PROV-1(§2.2 provenance):新增 `source` + `fetched_at` 兩欄,
    schema-additive;既有 caller(讀 date/value/realtime_start)無需修改。
    """
    if not api_key:
        return pd.DataFrame()
    r = fetch_url(
        FRED_BASE,
        params={
            "series_id":  series_id,
            "api_key":    api_key,
            "file_type":  "json",
            "sort_order": "desc",
            "limit":      n,
        },
        timeout=20,
    )
    if r is None:
        return pd.DataFrame()
    try:
        obs = r.json().get("observations", [])
    except Exception as e:
        print(f"[macro_core/fred] {series_id} JSON 解析失敗: {e}")
        return pd.DataFrame()
    if not obs:
        return pd.DataFrame()
    df = pd.DataFrame(obs)
    df = df[df["value"] != "."].copy()
    # v19.172:強制轉 float64(不可只用 pd.to_numeric 後 dtype inference)。
    # FRED 部分 series 全為整數(PAYEMS / HSN1F / ICSA 等就業/住宅啟動數),
    # to_numeric 對「全整數」會回 int64,違反 MacroFredSchema "float64" 契約
    # → pandera SchemaError → 整個 fetch_all_indicators 炸(v19.171 修了
    # catastrophic propagation,但根因仍在此)。
    df["value"] = pd.to_numeric(df["value"], errors="coerce").astype("float64")
    df["date"]  = pd.to_datetime(df["date"])
    # v19.60 D1：FRED API observations 已含 realtime_start 欄位（YYYY-MM-DD 字串）。
    # 缺欄或解析失敗回 NaT，呼叫端用 .get/.dropna 容錯。
    if "realtime_start" in df.columns:
        df["realtime_start"] = pd.to_datetime(df["realtime_start"], errors="coerce")
    else:
        df["realtime_start"] = pd.NaT
    out = df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)
    # v19.82 F-PROV-1:provenance schema(§2.2)— source 標識 + 抓取時間
    # 用 Timestamp.now('UTC') 避 pandas 4 deprecation(原 Timestamp.utcnow())
    out["source"] = f"FRED:{series_id}"
    out["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    # v19.155 Pandera Phase A pilot:fetch_fred 出口 schema validation。
    # 契約違反 → raise SchemaError(§1 Fail Loud,上游 fix);環境問題 → silent fallback。
    try:
        from shared.schemas import validate_fred
        validate_fred(out)
    except ImportError:
        pass  # pandera 不可用(極罕見 — requirements.txt pin >=0.20)
    return out


# v19.65 P1-F1：FRED 批次預熱器
# fetch_all_indicators 內 21 條 FRED 中 16 條原為 sequential 呼叫（首次 cache miss
# 各等 0.2~0.5s × 16 ≈ 3~8s）。此 batch 並行調用既有 fetch_fred（已有 30min TTL）
# 預熱所有 series_id 進 cache，後續所有呼叫點自然 hit @_ttl_cache，0 改動現有邏輯。
# 不加自己的 cache：避免與 fetch_fred 的 @_ttl_cache 雙層失準。
def fetch_fred_batch(
    specs: list[tuple[str, int]],
    api_key: str,
    max_workers: int = 8,
) -> dict[str, pd.DataFrame]:
    """並行預熱多條 FRED series。

    Provenance(C2 v19.208 F-PROV-1):每個回傳 df 已含 `source='FRED:<sid>'` +
    `fetched_at` 欄(§2.2 schema-additive),inheritance 自 fetch_fred。
    本 fn 為 batch dispatcher,無 batch-level provenance 需求。

    Parameters
    ----------
    specs : list of (series_id, n) — 例如 [("DGS10", 2600), ("CPIAUCSL", 144)]
    api_key : FRED API key
    max_workers : ThreadPool 並行度（預設 8，FRED 公開 API rate limit 約 120 req/min 安全）

    Returns
    -------
    dict[series_id, DataFrame]
        每個 series_id 對應其 fetch_fred 結果；失敗則為空 DataFrame。
        副作用：所有 (series_id, api_key, n) 進入 fetch_fred 的 @_ttl_cache。
    """
    if not specs or not api_key:
        return {}
    from concurrent.futures import ThreadPoolExecutor
    result: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futs = {pool.submit(fetch_fred, sid, api_key, n): sid for sid, n in specs}
        for fut in futs:
            sid = futs[fut]
            try:
                result[sid] = fut.result()
            except Exception as e:
                print(f"[macro_core/fred_batch] {sid} 失敗: {e}")
                result[sid] = pd.DataFrame()
    return result
