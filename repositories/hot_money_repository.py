# -*- coding: utf-8 -*-
"""repositories/hot_money_repository.py — 熱錢監測資料層(L1)

v19.196 P0-4-A 從根目錄 hot_money.py 拆出:
- `fetch_foreign_flow_series` — FinMind 外資買賣超 fetcher
- `fetch_usdtwd_series` — Yahoo USDTWD spot fetcher
- `_yf_series_to_df` — yfinance Series → 標準 DataFrame helper

純 I/O,無 UI 呼叫。EX-CACHE-1 例外:用 `@st.cache_data` 走 Streamlit Cloud 跨 session
cache,decorator-only,不做真 UI 呼叫(st.warning / st.markdown / st.session_state 等)。

UI 渲染(`render_hot_money_section`) + 純函式信號分類(`build_signals`)留在
`ui/hot_money.py`,本檔僅負責資料抓取與 schema 出口契約。
"""
from __future__ import annotations

import datetime as _dt

import pandas as pd
import streamlit as st  # EX-CACHE-1:僅 @st.cache_data decorator,無真 UI 呼叫

from shared.ttls import TTL_10MIN, TTL_30MIN


# v19.223 P1-2:FinMind URL 收口至 shared/api_endpoints.py SSOT
from shared.api_endpoints import FINMIND_BASE as _FINMIND_BASE


def _yf_series_to_df(series: pd.Series) -> pd.DataFrame:
    """`fetch_yf_close` 回傳的 pd.Series → 標準 [date, usdtwd] DataFrame。

    空 series / 壞輸入 → 空 df。
    """
    if series is None or len(series) == 0:
        return pd.DataFrame(columns=["date", "usdtwd"])
    out = pd.DataFrame({
        "date": pd.to_datetime(series.index).tz_localize(None) if (
            getattr(series.index, "tz", None) is not None
        ) else pd.to_datetime(series.index),
        "usdtwd": pd.to_numeric(series.values, errors="coerce"),
    }).dropna(subset=["usdtwd"])
    out = out[out["usdtwd"] > 0]
    return out.sort_values("date").reset_index(drop=True)


@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def fetch_foreign_flow_series(days: int, token: str = "") -> tuple[pd.DataFrame, str]:
    """抓最近 N 天外資買賣超（FinMind，沿用 tw_macro pattern + token kwarg）。

    Returns: (df[date, foreign_net_yi 億元], error_msg or "")
    """
    try:
        from fund_fetcher import fetch_url_with_retry
        end_d = _dt.date.today()
        start_d = end_d - _dt.timedelta(days=days + 14)
        params = {
            "dataset": "TaiwanStockTotalInstitutionalInvestors",
            "start_date": start_d.strftime("%Y-%m-%d"),
            "end_date":   end_d.strftime("%Y-%m-%d"),
        }
        if token:
            params["token"] = token
        r = fetch_url_with_retry(_FINMIND_BASE, params=params, timeout=15, retries=2)
    except Exception as e:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind 抓取失敗：{e}"

    if r is None:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "FinMind 無回應"

    try:
        rows = r.json().get("data", []) or []
    except Exception as e:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind JSON 解析失敗：{e}"

    if not rows:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "無資料回傳（可能為非交易日區間）"

    df = pd.DataFrame(rows)
    name_col = next((c for c in ("name", "institutional_investors") if c in df.columns), None)
    if name_col is None:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), f"FinMind 缺類別欄"
    mask = df[name_col].astype(str).str.contains("Foreign|外資", case=False, na=False, regex=True)
    fdf = df.loc[mask].copy()
    if fdf.empty:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "FinMind 無 Foreign 類別資料"

    fdf["net"] = pd.to_numeric(fdf["buy"], errors="coerce") - pd.to_numeric(fdf["sell"], errors="coerce")
    out = (fdf.groupby("date", as_index=False)["net"].sum()
              .assign(foreign_net_yi=lambda d: d["net"] / 1e8)
              .loc[:, ["date", "foreign_net_yi"]])
    out["date"] = pd.to_datetime(out["date"])
    out = out.sort_values("date").reset_index(drop=True)
    # v19.151 F-PROV-1 phase 2:DataFrame.attrs 承載血緣(對齊 fetch_yf_close v19.83)
    out.attrs["source"] = "FinMind:TaiwanStockTotalInstitutionalInvestors"
    out.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    # v19.186 Pandera Phase B:出口 schema 驗證(date 升序唯一 / net 無 NaN / 單位合理)
    # 契約違反 = 上游資料異常,§1 Fail Loud 直接拋(不靜默回髒資料)
    try:
        from shared.schemas import validate_foreign_flow
        out = validate_foreign_flow(out)
    except ImportError:
        pass  # pandera 不在環境(極罕見,requirements 已 pin)→ 降級不驗
    return out, ""


@st.cache_data(ttl=TTL_10MIN, show_spinner=False)
def fetch_usdtwd_series(days: int) -> tuple[pd.DataFrame, str]:
    """抓 USDTWD=X 時序（複用 macro_repository.fetch_yf_close + NAS proxy）。

    Returns: (df[date, usdtwd], error_msg or "")
    """
    try:
        from repositories.macro_repository import fetch_yf_close
        # range_ 換算：days 60-180 → 1y / 365 → 2y
        range_ = "2y" if days > 365 else "1y" if days > 90 else "6mo"
        series = fetch_yf_close("USDTWD=X", range_=range_, interval="1d")
    except Exception as e:
        return pd.DataFrame(columns=["date", "usdtwd"]), f"USDTWD 抓取失敗：{e}"

    df = _yf_series_to_df(series)
    if df.empty:
        return df, "USDTWD 無資料（Yahoo Chart API 失敗或被限流）"
    # 截取最近 days
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    df = df[df["date"] >= cutoff].reset_index(drop=True)
    return df, ""
