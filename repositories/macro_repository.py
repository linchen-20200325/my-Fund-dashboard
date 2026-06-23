"""
repositories/macro_repository.py — 總經 I/O Repository（v11.0 從 macro_core.py 搬入）

設計目標
========
1. 兩個 repo (my-stock-dashboard / my-fund-dashboard) 共用同一份檔案,
   消除指標重複實作與閾值不一致的維護成本。
2. **所有外部 HTTP 抓取統一透過 infra.proxy.fetch_url(),確保走家用 NAS
   中繼站**,避免雲端 IP 被台灣金融網站封鎖,且 yfinance 在境外節點
   常被限流的問題。

範圍邊界(v1.0 已釐清)
=====================
✅ 收錄:全球/美國總經指標(VIX / DXY / US10Y / CPI / Fed Rate / PMI /
        HY OAS / M2 / Fed BS / 殖利率利差),資料源 = FRED + Yahoo Chart
✅ 收錄:純數學工具(zscore / trend / recession_probability / spread_series)
✅ 收錄:統一 schema(make_indicator / flatten_snapshot)
❌ 不收錄:台灣獨有指標 → 留在 tw_macro.py / leading_indicators.py
❌ 不收錄:下游決策(台股曝險上限、基金資產配置)→ 留在各自 service 引擎

依賴限制
========
- 不依賴 streamlit(可在 CLI / pytest 環境直接 import)
- 不依賴 yfinance(改打 Yahoo Finance Chart API,走 proxy)

v11.0 分層歸位：本檔屬於 Repository Layer，純 I/O + 純數學工具。
向後相容：根目錄 macro_core.py 保留 `from repositories.macro_repository import *` shim，
        E 階段收尾後 shim 刪除。
"""
from __future__ import annotations

import datetime as _dt
import json as _json
import math
import os as _os
from typing import Optional

import numpy as np
import pandas as pd

# v11.0 A-1 後 infra/proxy.py 為 fetch_url 主位置；proxy_helper.py 走 shim 也可，
# 但 Repository Layer 直接依新路徑，少一跳 import 並示範新分層
from infra.proxy import fetch_url

# v18.58: 借用 fund_fetcher 的 TTL 快取裝飾器（同樣模組層共享、可 clear_all_caches 統一清空）
from fund_fetcher import _ttl_cache, register_cache
from shared.fred_series import FRED_BSCICP02, FRED_PHILLY_FED
from shared.signal_thresholds import (  # v19.74 W3a SSOT consume
    RECESSION_LOGIT_COEF_INTERCEPT,
    RECESSION_LOGIT_COEF_SPREAD,
)
from shared.ttls import TTL_5MIN, TTL_10MIN, TTL_30MIN

__version__ = "1.0.0"

FRED_BASE = "https://api.stlouisfed.org/fred/series/observations"
FRED_RELEASE_BASE = "https://api.stlouisfed.org/fred/series/release"
FRED_RELEASE_DATES_BASE = "https://api.stlouisfed.org/fred/release/dates"
YF_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"

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
    "CPI":         {"green_low": 1.5, "green_high": 2.5, "yellow_above": 3.5, "red_above": 4.0},
    "US10Y":       {"yellow_above": 4.5, "red_above": 5.0},
    "DXY":         {"yellow_above": 105, "red_above": 110},
    "PMI":         {"red_below": 46, "yellow_below": 50, "green_above": 52},
    "HY_SPREAD":   {"green_below": 4.0, "yellow_below": 6.0, "red_above": 6.0},
    "YIELD_10Y2Y": {"red_below": 0.0, "yellow_below": 0.5},
    "YIELD_10Y3M": {"red_below": 0.0, "yellow_below": 0.5},
    "M2_YOY":      {"red_below": 0.0, "green_above": 5.0},
    "FED_BS_YOY":  {"red_below": -5.0, "green_above": 5.0},
    # v18.107 跨幣別
    "EURUSD":      {"green_above": 1.15, "yellow_below": 1.10, "red_below": 1.05},
    "USDJPY":      {"green_below": 140.0, "yellow_above": 150.0, "red_above": 155.0},
    "USDCNH":      {"green_below": 7.0, "yellow_above": 7.15, "red_above": 7.3},
    # v19.71 SSOT 補完：以下 13 個閾值與 services/macro_service.py inline 判斷邏輯
    # 完全等價（值對值同步），目前 production 仍用 inline conditional，本 dict 作為
    # SSOT 文件來源 + 未來 refactor consume 的 single source of truth。
    # 動態閾值（FED_RATE 的 v<prev / NEW_HOME 的 v>prev / ADL 的 chg）與多階分數
    # （NFP 5 級評分）schema 不相容，暫不收錄。
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
    pd.DataFrame  欄位: ['date' (Timestamp), 'value' (float),
                          'realtime_start' (Timestamp)],已排序去除空值。
                  v19.60 D1：補上 realtime_start（FRED API 該筆觀測首次發布日，
                  ≈ BLS/FED 真實 publish 時間），用於 UI chip 區分「資料月份」
                  與「真實發布日」。失敗時回傳空 DataFrame。
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
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df["date"]  = pd.to_datetime(df["date"])
    # v19.60 D1：FRED API observations 已含 realtime_start 欄位（YYYY-MM-DD 字串）。
    # 缺欄或解析失敗回 NaT，呼叫端用 .get/.dropna 容錯。
    if "realtime_start" in df.columns:
        df["realtime_start"] = pd.to_datetime(df["realtime_start"], errors="coerce")
    else:
        df["realtime_start"] = pd.NaT
    return df.dropna(subset=["value"]).sort_values("date").reset_index(drop=True)


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


@register_cache
@_ttl_cache(ttl_sec=TTL_10MIN, maxsize=64)   # v18.58: Yahoo Chart，渲染同一 ticker 多次免重抓
def fetch_yf_close(ticker: str, range_: str = "2y", interval: str = "1d") -> pd.Series:
    """
    抓取 Yahoo Finance 收盤價序列(透過 NAS proxy 直打 Chart API)。

    為何不用 yfinance:yfinance 預設不走 proxy,且常因雲端節點 IP
    被 Yahoo 限流(429)而失敗。直接呼叫 Chart REST API + NAS 中繼,
    取得台灣 IP 出口,穩定許多。

    Returns
    -------
    pd.Series  index 為 DatetimeIndex,value 為收盤價。失敗時回傳空 Series。
    """
    url = f"{YF_CHART_BASE}/{ticker}"
    r = fetch_url(
        url,
        params={"interval": interval, "range": range_},
        timeout=15,
    )
    if r is None:
        return pd.Series(dtype=float, name=ticker)
    try:
        d = r.json()
        result = d["chart"]["result"][0]
        ts = result["timestamp"]
        close = result["indicators"]["quote"][0]["close"]
        s = pd.Series(close, index=pd.to_datetime(ts, unit="s"), dtype=float).dropna()
        s.name = ticker
        return s
    except Exception as e:
        print(f"[macro_core/yf] {ticker} 解析失敗: {e}")
        return pd.Series(dtype=float, name=ticker)


@register_cache
@_ttl_cache(ttl_sec=TTL_5MIN, maxsize=16)   # v19.64：盤中 ticker rerun dedupe
def fetch_yf_latest(tickers: tuple[str, ...]) -> dict[str, Optional[float]]:
    """批次抓多個 ticker 最新收盤(空值代表抓不到)。"""
    out: dict[str, Optional[float]] = {}
    for t in tickers:
        s = fetch_yf_close(t, range_="5d")
        out[t] = round(float(s.iloc[-1]), 4) if not s.empty else None
    return out


# ══════════════════════════════════════════════════════════════
# DefiLlama 穩定幣總市值（影子/數位流動性因子用）— 免 API key，走 NAS proxy
# ══════════════════════════════════════════════════════════════
DEFILLAMA_STABLECOIN_URL = "https://stablecoins.llama.fi/stablecoincharts/all"


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)   # 穩定幣市值日頻
def fetch_defillama_stablecoin_mcap() -> pd.Series:
    """抓 DefiLlama 全市場穩定幣「總流通市值」歷史（USD，日頻）。

    Returns
    -------
    pd.Series  index=DatetimeIndex, value=總流通市值(USD)。失敗回空 Series。
    """
    r = fetch_url(DEFILLAMA_STABLECOIN_URL, timeout=20)
    if r is None:
        return pd.Series(dtype=float, name="stablecoin_mcap")
    try:
        data = r.json()
    except Exception as e:
        print(f"[defillama] 穩定幣 JSON 解析失敗: {e}")
        return pd.Series(dtype=float, name="stablecoin_mcap")
    rows: dict = {}
    for item in (data or []):
        try:
            ts = int(item["date"])
            tc = item.get("totalCirculatingUSD") or item.get("totalCirculating") or {}
            # totalCirculatingUSD 為 {peg類型: 金額} → 加總所有數值欄；或本身即數值
            if isinstance(tc, dict):
                val = float(sum(v for v in tc.values() if isinstance(v, (int, float))))
            else:
                val = float(tc)
            if val > 0:
                rows[pd.Timestamp(ts, unit="s").normalize()] = val
        except (KeyError, ValueError, TypeError):
            continue
    if not rows:
        return pd.Series(dtype=float, name="stablecoin_mcap")
    return pd.Series(rows, name="stablecoin_mcap").sort_index()


# ══════════════════════════════════════════════════════════════
# ISM 製造業 PMI — 5 段備援共用函式（v1.1 兩端統一）
#
# 為什麼 5 段？
#   FRED NAPM / ISPMANPMI 自 2016-08 ISM 收回授權後停更，但保留以防重啟；
#   MacroMicro / ISM World 為主存活源但 HTML 結構易變動；
#   DBnomics 為 ISM JSON 鏡像（無需 key）；
#   OECD US Business Confidence 在 FRED 上仍持續更新，作為「概念替代指標」，
#   值約 98–102（非 PMI 的 30–70 區間），與 ISM PMI 相關性 ~0.7。
# ══════════════════════════════════════════════════════════════

def fetch_ism_pmi(fred_api_key: str = "", *, max_age_days: int = 90) -> dict:
    """抓取 ISM 製造業 PMI（5 段備援，月頻）。

    Returns
    -------
    dict
      命中：{'value': float, 'date': 'YYYY-MM-DD', 'label': str,
             'source': str, 'is_proxy': bool, 'series_id': str,
             'dates': [...], 'values': [...], 'proxy_note'?: str}
      失敗：{'_err_pmi': str, 'value': None}
    """
    import datetime as _dt
    import re as _re
    today = _dt.date.today()
    errs: list[str] = []

    # ── 方案 1+2: FRED NAPM / ISPMANPMI（max_age_days 時效檢查）──
    if fred_api_key:
        for sid, lbl in [('NAPM', 'FRED NAPM'), ('ISPMANPMI', 'FRED ISPMANPMI')]:
            try:
                # v18.119 issue 1 真正修法：n=144 + tail(120) 拉滿 10 年月頻
                # 原 n=36 + tail(24) 只 24 期 → Phase 4 min_overlap=24 + lag=3
                # → .shift(-3).dropna() = 21 < 24 → return out_empty
                df = fetch_fred(sid, fred_api_key, n=144)
                if df.empty or len(df) < 5:
                    continue
                df = df.tail(120)
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age > max_age_days:
                    print(f'[macro_core/PMI/FRED] ⚠️ {sid} 最新={last_date} '
                          f'已停更 {age} 天 > {max_age_days}，跳過')
                    continue
                v = round(float(df['value'].iloc[-1]), 1)
                print(f'[macro_core/PMI/FRED] ✅ {sid}={v} date={last_date} '
                      f'series={len(df)} 期')
                return {
                    'value': v, 'date': str(last_date), 'label': lbl,
                    'source': 'FRED', 'is_proxy': False, 'series_id': sid,
                    'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                    'values': [round(float(x), 1) for x in df['value']],
                }
            except Exception as e:
                errs.append(f'FRED.{sid}:{type(e).__name__}')
                print(f'[macro_core/PMI/FRED/{sid}] ❌ {e}')

    # ── 方案 3: MacroMicro 財經 M 平方（中文 HTML）──
    try:
        from bs4 import BeautifulSoup
        for url in ('https://www.macromicro.me/charts/950/us-ism-mfg-pmi',
                    'https://www.macromicro.me/charts/2/economic-monitor-pmi'):
            r = fetch_url(url, timeout=12)
            if r is None:
                continue
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(?:ISM[^。]{0,40}?PMI|製造業\s*PMI)[^。]{0,200}?'
                r'(\d{2}\.\d)[^。]{0,80}?(20\d{2})[\s/年-]+(\d{1,2})',
                txt)
            if m:
                v = float(m.group(1)); yr = m.group(2); mo = int(m.group(3))
                if 30 <= v <= 70 and 1 <= mo <= 12:
                    date = f'{yr}-{mo:02d}-01'
                    print(f'[macro_core/PMI/MacroMicro] ✅ {v} date={date}')
                    return {'value': v, 'date': date,
                            'label': 'MacroMicro ISM PMI',
                            'source': 'MacroMicro', 'is_proxy': False,
                            'series_id': '950'}
    except Exception as e:
        errs.append(f'MacroMicro:{type(e).__name__}')
        print(f'[macro_core/PMI/MacroMicro] ❌ {e}')

    # ── 方案 4: ISM World 官方月報（英文 HTML，最一手）──
    try:
        from bs4 import BeautifulSoup
        url = ('https://www.ismworld.org/supply-management-news-and-reports/'
               'reports/ism-report-on-business/pmi/')
        r = fetch_url(url, timeout=12)
        if r is not None:
            r.encoding = 'utf-8'
            txt = BeautifulSoup(r.text, 'html.parser').get_text(' ', strip=True)
            m = _re.search(
                r'(?:Manufacturing\s+PMI[^.]{0,40}?(?:at|registered)|'
                r'PMI[^.]{0,15}?registered)[^\d]{0,15}(\d{2}\.\d)\s*(?:%|percent)',
                txt, _re.IGNORECASE)
            if m:
                v = float(m.group(1))
                if 30 <= v <= 70:
                    m_dt = _re.search(
                        r'(January|February|March|April|May|June|July|August|'
                        r'September|October|November|December)\s+(20\d{2})', txt)
                    date = ''
                    if m_dt:
                        MO = {'January':1,'February':2,'March':3,'April':4,
                              'May':5,'June':6,'July':7,'August':8,
                              'September':9,'October':10,'November':11,'December':12}
                        date = f'{m_dt.group(2)}-{MO[m_dt.group(1)]:02d}-01'
                    print(f'[macro_core/PMI/ISM] ✅ {v} date={date or "?"}')
                    return {'value': v, 'date': date,
                            'label': 'ISM World Official',
                            'source': 'ISM', 'is_proxy': False,
                            'series_id': 'ismworld.org'}
    except Exception as e:
        errs.append(f'ISM:{type(e).__name__}')
        print(f'[macro_core/PMI/ISM] ❌ {e}')

    # ── 方案 5: DBnomics（純 JSON，ISM 鏡像，無需 key）──
    try:
        url = 'https://api.db.nomics.world/v22/series/ISM/pmi/pm'
        r = fetch_url(url, params={'observations': '1', 'limit': '24'}, timeout=15)
        if r is not None:
            d = r.json()
            docs = d.get('series', {}).get('docs', []) or []
            if docs:
                periods = docs[0].get('period', []) or []
                values  = docs[0].get('value',  []) or []
                last_idx = -1
                for i in range(len(values) - 1, -1, -1):
                    vi = values[i]
                    if vi is None: continue
                    try:
                        if isinstance(vi, float) and (vi != vi):  # NaN
                            continue
                    except Exception:
                        pass
                    last_idx = i; break
                if last_idx >= 0:
                    v = round(float(values[last_idx]), 1)
                    period_str = str(periods[last_idx])
                    last_date = _dt.datetime.strptime(period_str[:7], '%Y-%m').date()
                    age = (today - last_date).days
                    if age <= max_age_days and 30 <= v <= 70:
                        date = f'{period_str[:7]}-01'
                        print(f'[macro_core/PMI/DBnomics] ✅ {v} date={date}')
                        return {'value': v, 'date': date,
                                'label': 'DBnomics ISM/pmi/pm',
                                'source': 'DBnomics', 'is_proxy': False,
                                'series_id': 'ISM/pmi/pm'}
                    else:
                        print(f'[macro_core/PMI/DBnomics] ⚠️ '
                              f'最新={period_str} v={v} age={age}d 不通過防呆')
    except Exception as e:
        errs.append(f'DBnomics:{type(e).__name__}')
        print(f'[macro_core/PMI/DBnomics] ❌ {e}')

    # ── 方案 6: Phil Fed 製造業擴散指數（FRED GACDFSA066MSFRBPHI）──
    #   FRED 上仍持續更新；範圍 -50~+50；數學轉換為 PMI 等價刻度：
    #   PMI_eq = 50 + diffusion / 3 → 區間 33~67，與 ISM PMI 歷史相關性 ~0.85。
    #   標 is_proxy=True，UI 顯示「Phil Fed 替代計」。
    if fred_api_key:
        try:
            # v18.119 issue 1: 拉滿月頻 series 供 Phase 4/3-B 使用
            df = fetch_fred(FRED_PHILLY_FED, fred_api_key, n=144)
            if not df.empty and len(df) >= 5:
                df = df.tail(120).copy()
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age <= max_age_days:
                    # 轉換為 PMI 等價刻度
                    df['value'] = 50.0 + df['value'] / 3.0
                    v = round(float(df['value'].iloc[-1]), 1)
                    print(f'[macro_core/PMI/PhilFed] ⚠️ 採用替代計 '
                          f'PMI_eq={v} (Phil Fed Diffusion 轉換) date={last_date}')
                    return {
                        'value': v, 'date': str(last_date),
                        'label': 'Phil Fed 製造業擴散（轉 PMI 刻度）',
                        'source': 'PhilFed-Proxy', 'is_proxy': True,
                        'series_id': 'GACDFSA066MSFRBPHI',
                        'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                        'values': [round(float(x), 1) for x in df['value']],
                        'proxy_note': '⚠️ 替代指標：Phil Fed 製造業擴散指數，'
                                      '已用 PMI_eq = 50 + diffusion/3 轉換為 PMI 刻度。'
                                      '與 ISM PMI 歷史相關性 ~0.85。',
                    }
        except Exception as e:
            errs.append(f'PhilFed-Proxy:{type(e).__name__}')
            print(f'[macro_core/PMI/PhilFed] ❌ {e}')

    # ── 方案 7: OECD US Business Confidence（FRED BSCICP02USM460S, Proxy）──
    #   最後手段；非 ISM PMI；月頻；值 ~98–102（非 30–70）；與 ISM PMI 相關性 ~0.7。
    #   UI 必須以 is_proxy=True 標註，且分數刻度與 PMI 不同。
    if fred_api_key:
        try:
            # v18.119 issue 1: 拉滿月頻 series
            df = fetch_fred(FRED_BSCICP02, fred_api_key, n=144)
            if not df.empty and len(df) >= 5:
                df = df.tail(120)
                last_date = pd.to_datetime(df['date'].iloc[-1]).date()
                age = (today - last_date).days
                if age <= max_age_days:
                    v = round(float(df['value'].iloc[-1]), 2)
                    print(f'[macro_core/PMI/OECD-Proxy] ⚠️ 採用替代指標 '
                          f'BSCICP02USM460S={v} date={last_date}')
                    return {
                        'value': v, 'date': str(last_date),
                        'label': 'OECD US Business Confidence (Proxy)',
                        'source': 'OECD-Proxy', 'is_proxy': True,
                        'series_id': 'BSCICP02USM460S',
                        'dates':  [str(pd.to_datetime(d).date()) for d in df['date']],
                        'values': [round(float(x), 2) for x in df['value']],
                        'proxy_note': '⚠️ 替代指標：OECD 美國商業信心指數。'
                                      '值域 ~98–102（100 為長期平均，非 50 榮枯線）。'
                                      '與 ISM PMI 相關性 ~0.7，請參考趨勢方向而非絕對位階。',
                    }
                else:
                    errs.append(f'OECD-Proxy:過時 {age} 天')
        except Exception as e:
            errs.append(f'OECD-Proxy:{type(e).__name__}')
            print(f'[macro_core/PMI/OECD-Proxy] ❌ {e}')

    err_msg = ' | '.join(errs) or 'all 7 stages failed'
    print(f'[macro_core/PMI] ❌ 7 段備援全失敗：{err_msg}')
    return {'_err_pmi': err_msg, 'value': None}


# ══════════════════════════════════════════════════════════════
# 總經指南針 (Top-Down Macro Compass) — Phase 1 規格三大指標
#   VIX / TNX / GSPC + 60MA，固定於頁面頂部供新人秒懂市場大環境。
#   呼叫端：app.py 的 render_macro_compass()（在 st.tabs() 之前渲染）。
# ══════════════════════════════════════════════════════════════

@register_cache
@_ttl_cache(ttl_sec=TTL_5MIN, maxsize=8)   # v18.58: 每次 rerun 都觸發 — 避免 widget 互動連環抓
def fetch_macro_compass(range_: str = "6mo") -> dict:
    """Phase 1 — 一次抓 ^VIX / ^TNX / ^GSPC 三大美股指標 + GSPC 60MA。

    所有抓取都走 macro_core.fetch_yf_close()（NAS proxy → Yahoo Chart REST API），
    避開 yfinance 直連被 Streamlit Cloud IP 限流。失敗欄位填 None，UI 端優雅降級。

    Returns dict:
      vix  : {'value', 'series', 'dates', 'signal':(light, label, color)} | None
      tnx  : 同上                                                          | None
      gspc : 同上 + {'ma60', 'ma60_series'}                                | None
    """
    out: dict = {'vix': None, 'tnx': None, 'gspc': None}

    def _sig_vix(v):
        # Phase 1 規格：>25 黃 / >30 綠（恐慌貪婪區=逢低加碼時機）
        if v > 30: return ('🟢', '恐慌貪婪區（準備跌深就買）', '#3fb950')
        if v > 25: return ('🟡', '波動加劇', '#d29922')
        return ('🟢', '市場平靜', '#3fb950')

    def _sig_tnx(t):
        # 估值壓力：≥4.5% 紅 / 3.5–4.5 黃 / <3.5 綠（寬鬆）
        if t >= 4.5: return ('🔴', '估值壓力（科技股不利）', '#f85149')
        if t >= 3.5: return ('🟡', '中性區', '#d29922')
        return ('🟢', '寬鬆有利', '#3fb950')

    def _sig_gspc(g, ma):
        # Phase 1 規格：站上 60MA=多頭、跌破=趨勢轉弱
        if ma is None or g is None:
            return ('⚪', '60MA 計算中', '#8b949e')
        if g >= ma: return ('🟢', '多頭格局（股優於債）', '#3fb950')
        return ('🔴', '趨勢轉弱（提高防禦）', '#f85149')

    # ── ^VIX ────────────────────────────────────────────────
    try:
        s = fetch_yf_close('^VIX', range_=range_)
        if not s.empty:
            v = round(float(s.iloc[-1]), 2)
            tail = s.tail(90)
            out['vix'] = {
                'value': v,
                'series': [round(float(x), 2) for x in tail.tolist()],
                'dates':  [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_vix(v),
            }
    except Exception as e:
        print(f'[macro_compass] VIX fetch failed: {e}')

    # ── ^TNX ────────────────────────────────────────────────
    try:
        s = fetch_yf_close('^TNX', range_=range_)
        if not s.empty:
            t = round(float(s.iloc[-1]), 3)
            tail = s.tail(90)
            out['tnx'] = {
                'value': t,
                'series': [round(float(x), 3) for x in tail.tolist()],
                'dates':  [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_tnx(t),
            }
    except Exception as e:
        print(f'[macro_compass] TNX fetch failed: {e}')

    # ── ^GSPC + 60MA ────────────────────────────────────────
    try:
        s = fetch_yf_close('^GSPC', range_=range_)
        if not s.empty:
            g = round(float(s.iloc[-1]), 2)
            ma60_ser = s.rolling(60).mean()
            ma60_last = ma60_ser.dropna()
            ma60 = round(float(ma60_last.iloc[-1]), 2) if not ma60_last.empty else None
            tail = s.tail(90)
            ma_tail = ma60_ser.tail(90)
            out['gspc'] = {
                'value': g,
                'ma60': ma60,
                'series': [round(float(x), 2) for x in tail.tolist()],
                'ma60_series': [None if pd.isna(x) else round(float(x), 2) for x in ma_tail.tolist()],
                'dates': [d.strftime('%Y-%m-%d') for d in tail.index],
                'signal': _sig_gspc(g, ma60),
            }
    except Exception as e:
        print(f'[macro_compass] GSPC fetch failed: {e}')

    return out


# ══════════════════════════════════════════════════════════════
# 純數學工具(不需要網路,兩邊共用)
# ══════════════════════════════════════════════════════════════

def zscore(s: pd.Series) -> pd.Series:
    """標準分數(std=0 時回傳全 0,避免除零)。"""
    if s.empty:
        return s
    std = float(s.std())
    if std == 0 or np.isnan(std):
        return pd.Series([0.0] * len(s), index=s.index)
    return (s - s.mean()) / std


def trend_arrow(vals: list[float]) -> str:
    """
    依最近 N 點走勢給出口語化趨勢標記。
    回傳: '持續上升 ↑' / '持續下降 ↓' / '最近反彈 ↗' / '最近回落 ↘' / ''
    """
    if len(vals) < 3:
        return ""
    diffs = [vals[i] - vals[i - 1] for i in range(1, len(vals))]
    pos = sum(1 for d in diffs if d > 0)
    neg = sum(1 for d in diffs if d < 0)
    # 「持續」描述必須要求最後一點同向，否則該歸類為「最近反彈/回落」
    if pos >= len(diffs) - 1 and diffs[-1] > 0:
        return "持續上升 ↑"
    if neg >= len(diffs) - 1 and diffs[-1] < 0:
        return "持續下降 ↓"
    return "最近反彈 ↗" if diffs[-1] > 0 else "最近回落 ↘"


def recession_probability(spread_10y3m: Optional[float]) -> Optional[float]:
    """
    用 10Y-3M 利差做 logistic 回歸估算未來 12 個月衰退機率(%)。
    spread_10y3m 為 None 時回傳 None。
    """
    if spread_10y3m is None:
        return None
    logit = RECESSION_LOGIT_COEF_SPREAD * spread_10y3m + RECESSION_LOGIT_COEF_INTERCEPT
    return round(1 / (1 + math.exp(-logit)) * 100, 1)


def spread_series(
    df_long: pd.DataFrame,
    df_short: pd.DataFrame,
    n_pts: int = 60,
) -> pd.Series:
    """
    計算兩個 FRED 序列的利差時序。
    優先用月頻對齊;若月頻 inner join 為空(例如 short 序列為日頻 TB3MS)
    則退回 merge_asof 容忍 40 天的回溯對齊。
    """
    if df_long.empty or df_short.empty:
        return pd.Series(dtype=float)

    dl = df_long[["date", "value"]].set_index("date").rename(columns={"value": "v_l"})
    ds = df_short[["date", "value"]].set_index("date").rename(columns={"value": "v_s"})
    # W5-2 §1: resample("ME").last() 取月底值後 ffill 補缺月(macro 月頻指標若某月未發布用前期);
    # 此為 yield spread 計算的業務正確補值(月度差分容忍上期值),加 log 透明化
    dl_m = dl.resample("ME").last()
    ds_m = ds.resample("ME").last()
    _dl_ffill = int(dl_m["v_l"].isna().sum())
    _ds_ffill = int(ds_m["v_s"].isna().sum())
    dl_m = dl_m.ffill()
    ds_m = ds_m.ffill()
    if _dl_ffill or _ds_ffill:
        print(f"[macro_repo _spread_series] ffill v_l={_dl_ffill}, v_s={_ds_ffill} 個月份")
    merged = dl_m.join(ds_m, how="inner").dropna()
    if not merged.empty:
        return (merged["v_l"] - merged["v_s"]).tail(n_pts)

    dl2 = df_long[["date", "value"]].rename(columns={"value": "v_l"}).sort_values("date")
    ds2 = df_short[["date", "value"]].rename(columns={"value": "v_s"}).sort_values("date")
    m = pd.merge_asof(
        dl2, ds2, on="date",
        tolerance=pd.Timedelta("40d"), direction="backward",
    ).dropna().set_index("date")
    return (m["v_l"] - m["v_s"]).tail(n_pts)


# ══════════════════════════════════════════════════════════════
# 統一 snapshot schema 工具
# ══════════════════════════════════════════════════════════════

def make_indicator(
    key: str,
    name: str,
    value: float,
    *,
    prev: Optional[float] = None,
    unit: str = "",
    type_: str = "同時",
    date: str = "",
    series: Optional[pd.Series] = None,
    desc: str = "",
    weight: float = 1.0,
) -> dict:
    """
    建立統一格式的指標 dict。

    fund 端原本就用富 dict(value/prev/trend/series/...),stock 端用扁平 float。
    我們以富 dict 為共同 schema,扁平結構可由 flatten_snapshot() 動態產生。
    """
    trend = ""
    if series is not None and len(series) >= 3:
        trend = trend_arrow([float(x) for x in series.tail(6).tolist()])
    return {
        "key":    key,
        "name":   name,
        "value":  value,
        "prev":   prev,
        "unit":   unit,
        "type":   type_,
        "date":   date,
        "desc":   desc,
        "trend":  trend,
        "series": series,
        "weight": weight,
    }


def flatten_snapshot(rich: dict) -> dict:
    """
    將富 dict snapshot 轉為扁平 dict(key 小寫),方便相容 stock 端
    macro_alert.py / macro_state_locker.py 既有 API。

    rich = {"VIX": {"value": 28.3, ...}, "CPI": {"value": 3.1, ...}}
    →     {"vix": 28.3, "cpi": 3.1}
    """
    out: dict = {}
    for k, v in (rich or {}).items():
        if isinstance(v, dict) and v.get("value") is not None:
            out[k.lower()] = v["value"]
    return out
