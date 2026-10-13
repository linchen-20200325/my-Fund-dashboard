"""repositories/macro/fred_vintage.py — FRED 逐版次觀測（取「首次公布日」用；L1，新增檔）。

依據 docs/v2/49_data_integration_plan.md §6.3 **N-3**「FRED vintage 取數的新 L1 檔（不動
`fetch_fred` 本體）」與 §6.2 **T1**（FRED 的公布日與修正版次）；§1.3 出入 2 與 §4.5。

## 為什麼不能直接用 `fetch_fred` 的 `realtime_start`

`repositories/macro/fred.py::fetch_fred` 呼叫 `fred/series/observations` 時**沒有帶任何
real-time 參數**。依 FRED 官方 API 文件，`realtime_start`／`realtime_end` 未指定時預設皆為
**查詢當天**，回傳的每一筆觀測的 `realtime_start` 因此就是「這個版本在查詢當天有效」——
對有修正的序列，它**不是**首次公布日（49 §1.3 出入 2；本環境無法連到 FRED，未以真實回應實測）。

## 本檔怎麼取

同一個端點（`fred.FRED_BASE`）、同一把金鑰，只多帶三個參數：

- `realtime_start` ＝ 呼叫端給的 `observation_start`（不是 FRED 的 1776-07-04 下界，理由見下）；
- `realtime_end` ＝ `9999-12-31`（FRED 文件訂的「至今」上界）；
- `output_type` ＝ `1`（Observations by Real-Time Period：同一個 `date` 每一段值不同的版次各一列，
  每列帶自己的 `realtime_start`／`realtime_end`）。

於是同一個 `date` 的各列依 `realtime_start` 排序，**最早那一列的 `realtime_start` 就是 FRED 首次
有這個值的日子**，之後各列是修正版次。

**`realtime_start` 下界為什麼取 `observation_start`**：觀測期間的值不可能在觀測期間開始之前公布，
所以 `date ≥ observation_start` 的每一筆，其每一個版次的 `realtime_start` 都 ≥ `observation_start`，
全部落在查詢範圍內、不被截斷；同時把要掃的版次數限在觀察範圍內（FRED 對版次數有上限，
**該上限是否套用到 `output_type=1`，本組無法實測**）。
⚠️ 若某一列的 `realtime_start` 恰好等於查詢下界，分不出是真的那天公布、還是被下界截斷 ——
本層照實交出（`attrs["realtime_floor"]`），由 L2 判斷要不要寫。

## 回傳

`pd.DataFrame`，欄位：
- `date`（Timestamp）：FRED 的 `date`（觀測期間；月頻為期初那一天）；
- `value`（float64）：該版次的值；FRED 缺值記號 `"."` → NaN（**不丟列**：版次序列要完整，
  「某一版把值撤成缺值」由 L2 判斷）；
- `realtime_start`（Timestamp，解析不了為 NaT）：該版次生效日；
- `realtime_end`（字串）：該版次失效日，現行版次為 `"9999-12-31"`（超出 pandas Timestamp 範圍，
  故保留字串，不轉型）。

`attrs`：`source`＝`"FRED:<series_id>:vintages"`、`fetched_at`（UTC ISO）、
`realtime_floor`（查詢下界，`YYYY-MM-DD`）。

## 失敗（與 `fetch_fred` 同一套語意，見其 docstring）

- 缺金鑰、`fetch_url` 回 None、JSON 解析失敗、`observations` 為空 → 回空 DataFrame，
  失敗原文掛在 `attrs["fetch_error"]`（鍵名與旁路掛法沿用 `fred.py`，不另定義第四份），
  公開讀法是 `fetch_fred_vintages_with_error`。
- 只有 `fetch_url` 回 None 且分類屬可重試者掛 `mark_fetch_failed` 標記、不入快取；
  404／407、JSON 壞、回 200 但沒有觀測照常快取（判準見 `infra/proxy.py::mark_fetch_failed_if_retryable`）。
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from infra.cache import FETCH_FAILED_ATTR, _ttl_cache, register_cache
from infra.proxy import fetch_url, mark_fetch_failed_if_retryable
from repositories.macro.fred import FRED_BASE, _FETCH_ERROR_ATTR, _with_fetch_error
from shared.ttls import TTL_30MIN

# FRED API 文件訂的「至今」上界。
REALTIME_END_LATEST = "9999-12-31"
# Observations by Real-Time Period。
OUTPUT_TYPE_REALTIME_PERIOD = "1"
# FRED 的缺值記號。
_MISSING = "."


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=16)
def fetch_fred_vintages(series_id: str, api_key: str, observation_start: str) -> pd.DataFrame:
    """抓 `series_id` 自 `observation_start`（`YYYY-MM-DD`）起每一筆觀測的全部版次。見模組說明。"""
    if not api_key:
        return _with_fetch_error(pd.DataFrame(),
                                 f"FRED:{series_id} api_key 為空(未設定 FRED 金鑰)")
    r = fetch_url(
        FRED_BASE,
        params={
            "series_id": series_id,
            "api_key": api_key,
            "file_type": "json",
            "observation_start": observation_start,
            "realtime_start": observation_start,
            "realtime_end": REALTIME_END_LATEST,
            "output_type": OUTPUT_TYPE_REALTIME_PERIOD,
            "sort_order": "asc",
        },
        timeout=20,
    )
    if r is None:
        _fail = mark_fetch_failed_if_retryable(
            pd.DataFrame(), f"fetch_url returned None: FRED:{series_id} (vintages)")
        _why = _fail.attrs.get(FETCH_FAILED_ATTR)
        if not _why:
            _why = (f"fetch_url returned None: FRED:{series_id} (vintages) "
                    f"(kind ∈ not_found/proxy_auth:404 或 407,不重試、照舊快取;"
                    f"本層無法細分兩者)")
        return _with_fetch_error(_fail, _why)
    try:
        obs = r.json().get("observations", [])
    except Exception as e:  # noqa: BLE001 —— 轉成旁路原文，不是吞（同 fetch_fred 該處）
        print(f"[macro/fred_vintage] {series_id} JSON 解析失敗: {e}")
        return _with_fetch_error(pd.DataFrame(),
                                 f"FRED:{series_id} (vintages) JSON 解析失敗:{type(e).__name__}: {e}")
    if not obs:
        return _with_fetch_error(pd.DataFrame(),
                                 f"FRED:{series_id} (vintages) 回 200,observations 為空(該區間無觀測)")
    raw = pd.DataFrame(obs)
    for column in ("date", "value", "realtime_start", "realtime_end"):
        if column not in raw.columns:
            return _with_fetch_error(pd.DataFrame(),
                                     f"FRED:{series_id} (vintages) 回 200,但缺欄位 {column}")
    out = pd.DataFrame({
        "date": pd.to_datetime(raw["date"], errors="coerce"),
        # "." 與其他無法解析的值 → NaN；**不丟列**（見模組說明）
        "value": pd.to_numeric(raw["value"].where(raw["value"] != _MISSING),
                               errors="coerce").astype("float64"),
        "realtime_start": pd.to_datetime(raw["realtime_start"], errors="coerce"),
        "realtime_end": raw["realtime_end"].astype(str),
    })
    out = out.sort_values(["date", "realtime_start"], kind="mergesort").reset_index(drop=True)
    out.attrs["source"] = f"FRED:{series_id}:vintages"
    out.attrs["fetched_at"] = pd.Timestamp.now("UTC").isoformat()
    out.attrs["realtime_floor"] = observation_start
    return out


def fetch_fred_vintages_with_error(series_id: str, api_key: str,
                                   observation_start: str) -> tuple[pd.DataFrame, Optional[str]]:
    """同 `fetch_fred_vintages`，另外交出失敗原文（`error` 為 None 表示成功）。

    走同一個 `fetch_fred_vintages`（同一層 `_ttl_cache`，不另疊快取）。
    ⚠️ 原文未遮蔽（金鑰走 params、不進訊息；寫進 `fetch_log` 或上畫面前仍由寫出點遮蔽）。
    """
    df = fetch_fred_vintages(series_id, api_key, observation_start)
    return df, df.attrs.get(_FETCH_ERROR_ATTR)
