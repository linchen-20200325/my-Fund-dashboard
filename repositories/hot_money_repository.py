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

# v19.374 B1:向 infra.cache(L0)下行註冊本檔 @st.cache_data fetcher,供 global_refresh_all
# 一併清。取代原 infra.cache 反向 import 本檔的 L0→L1 上行違憲(§8.2 硬規則 3)。
from infra.cache import register_st_cache


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


# ════════════════════════════════════════════════════════════════════
# v3 憲法 §02「只快取成功結果；失敗時退避，不連續轟炸來源」— 內拋外譯
# ════════════════════════════════════════════════════════════════════
# ## 這裡解的是什麼
#
# `@st.cache_data` **對「回傳值」快取、對「拋出的例外」不快取**
# (streamlit 1.59.2 實測:拋例外時上游每次都真的重跑;回空值時上游只跑一次)。
# 而本檔原本的慣例是「失敗 → 回 (空 DataFrame, err 字串)」——於是**一次上游瞬斷
# 會把那個空值鎖滿整個 TTL**(外資 30 分 / 匯率 10 分),使用者看到空白畫面,
# 按「強制重抓」也只是把同一份快取再讀一次。這違反 §2.4「超過 TTL 應重新抓取」,
# 而畫面上一個被鎖住的空值,正是 §1「錯誤的數字比沒有數字更危險」講的東西。
#
# ## 做法:內拋外譯(三層,公開介面一個字不變)
#
#   _fetch_*_uncached()        ← 失敗 raise;它**沒有**被裝飾,例外不會進快取
#          ↑
#   @st.cache_data _cached_*() ← 只有成功結果被存下來,例外直接穿過去
#          ↑
#   公開 fetch_*()             ← 接住例外,翻回既有回傳形狀 (df, err)
#
# 刻意**不**建共用機制:本批只有兩支,抽共用抽象是 §8.1 step 6「用不到的抽象」反例。
#
# ## ⚠️ 為什麼有兩個失敗點刻意**不**改(這段不是漏改,是判斷結果)
#
# `fetch_foreign_flow_series` 有 7 個失敗 return 點,只有 5 個改成 raise。
# 另外兩個 ——「無資料回傳(可能為非交易日區間)」與「FinMind 無 Foreign 類別資料」
# —— **維持原樣、照舊快取**,理由是**空有兩義**:連假 / 週末**真的就是沒有資料**,
# 上游是好的。把它們改成 raise,等於每次 rerun 都去打一次 FinMind,
# 免費額度會被燒到 402 —— **用一個 bug 換一個更貴的 bug**。
# `infra/cache.py` 已論證過「空有兩義,裝飾器沒有資訊分辨,猜錯任一邊都違憲」;
# 差別在於**我們在這一層有資訊**(知道命中的是哪個分支),所以是**逐分支判**,
# 不是讓裝飾器猜。


class _FetchFailed(RuntimeError):
    """本檔內部的取數失敗訊號 —— 只在本檔拋、只在本檔接。

    攜帶的訊息**逐字**就是既有的 `err` 字串,公開 wrapper 原樣翻回 `(空 df, err)`,
    因此公開回傳形狀與訊息內容都不變(caller / 既有測試零改動)。

    ⚠️ 刻意窄型別:schema 契約違反(`validate_foreign_flow` 的 `SchemaError`)
    **不**被接住,照舊往上拋 —— 那是 §1 Fail Loud 要的行為,本次不動。
    """


def _fetch_foreign_flow_series_uncached(
    days: int, token: str = "",
) -> tuple[pd.DataFrame, str]:
    """`fetch_foreign_flow_series` 的真實實作 —— **未被快取裝飾**。

    ⚠️ 取數失敗一律 `raise _FetchFailed(<既有 err 字串>)`,**不**回 (空 df, err);
    例外因此穿過 `@st.cache_data` 不入快取。唯二例外見檔內上方註解(空有兩義的
    兩個分支仍照舊 `return`,會被快取)。
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
        # transport 失敗 = 上游問題,不可快取(下次 rerun 應重試)
        raise _FetchFailed(f"FinMind 抓取失敗：{e}") from e

    if r is None:
        raise _FetchFailed(
            "FinMind 無回應（fetch_url 全部重試失敗；"
            "若為 402 額度用盡，狀態碼見 [proxy] log）")

    try:
        _payload = r.json()
    except Exception as e:
        raise _FetchFailed(f"FinMind JSON 解析失敗：{e}") from e

    # 【額度用盡防偽裝 — 本次稽核母題】FinMind 免費額度用盡回
    # {"msg": "Requests reached the upper limit.", "status": 402}，**不帶 data 欄**。
    # 舊版 `.get("data", [])` 直接吐 [] → 被下面歸類成「無資料回傳（可能為非交易日
    # 區間）」，於是「額度用盡」偽裝成「今天沒開盤」，資料硬停在某一天卻無人察覺。
    # §1 Fail Loud：帶上真實 status 與 msg，不可含糊。
    _api_status = _payload.get("status")
    if _api_status not in (None, 200, "200"):
        _msg = str(_payload.get("msg", ""))[:80]
        print(f"[hot_money] ❌ FinMind {_api_status}: {_msg}")
        raise _FetchFailed(f"FinMind {_api_status}: {_msg}")

    rows = _payload.get("data", []) or []
    if not rows:
        # ⛔ 刻意 return(會被快取),不 raise —— 空有兩義,連假/週末真的就是沒資料。
        #    改成 raise 會讓每次 rerun 都打 FinMind,把免費額度燒到 402。詳見上方註解。
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), "無資料回傳（可能為非交易日區間）"

    df = pd.DataFrame(rows)
    name_col = next((c for c in ("name", "institutional_investors") if c in df.columns), None)
    if name_col is None:
        # schema 壞 = 上游回了預期外的形狀,屬異常,不可快取
        raise _FetchFailed("FinMind 缺類別欄")
    mask = df[name_col].astype(str).str.contains("Foreign|外資", case=False, na=False, regex=True)
    fdf = df.loc[mask].copy()
    if fdf.empty:
        # ⛔ 同上,刻意 return(會被快取):有回資料但沒有 Foreign 類別,同屬「空有兩義」。
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


@register_st_cache
@st.cache_data(ttl=TTL_30MIN, show_spinner=False)
def _cached_foreign_flow_series(days: int, token: str = "") -> tuple[pd.DataFrame, str]:
    """只快取成功結果:`_FetchFailed` 從這一層直接穿過去,不會被存下來。"""
    return _fetch_foreign_flow_series_uncached(days, token)


def fetch_foreign_flow_series(days: int, token: str = "") -> tuple[pd.DataFrame, str]:
    """抓最近 N 天外資買賣超（FinMind，沿用 tw_macro pattern + token kwarg）。

    Returns: (df[date, foreign_net_yi 億元], error_msg or "")

    ⚠️ 回傳形狀與訊息內容與改版前**逐字相同**;變的只有「失敗結果不再進快取」。
    """
    try:
        return _cached_foreign_flow_series(days, token)
    except _FetchFailed as e:
        return pd.DataFrame(columns=["date", "foreign_net_yi"]), str(e)


def _fetch_usdtwd_series_uncached(days: int) -> tuple[pd.DataFrame, str]:
    """`fetch_usdtwd_series` 的真實實作 —— **未被快取裝飾**。

    兩個失敗點都**無二義**(上游拋例外 / Yahoo 回空),一律 `raise _FetchFailed`。
    """
    try:
        from repositories.macro_repository import fetch_yf_close
        # range_ 換算：days ≤365 保持原行為(6mo/1y/2y);>365 才解鎖更長區間
        # (v19.427 配置回測需滿 NAV 重疊期,單向擴充不改既有 caller —— 現有 caller 全 days≤365)
        range_ = ("max" if days > 3650 else "10y" if days > 1825 else "5y" if days > 730
                  else "2y" if days > 365 else "1y" if days > 90 else "6mo")
        series = fetch_yf_close("USDTWD=X", range_=range_, interval="1d")
    except Exception as e:
        raise _FetchFailed(f"USDTWD 抓取失敗：{e}") from e

    df = _yf_series_to_df(series)
    if df.empty:
        # 匯率沒有「非交易日就真的沒有資料」的二義性問題:USDTWD 是連續報價序列,
        # 只要 range_ 蓋到過去數月,空 = 上游失敗或被限流,不是「本來就沒有」。
        raise _FetchFailed("USDTWD 無資料（Yahoo Chart API 失敗或被限流）")
    # 截取最近 days
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    df = df[df["date"] >= cutoff].reset_index(drop=True)
    # v19.226 F-PROV-1 B5:provenance 補洞(§2.2 schema-additive)
    # tuple 第 2 元素是 error_msg 不是 source(audit 之前誤判),改 df.attrs 補
    df.attrs["source"] = "Yahoo:USDTWD=X:fetch_yf_close"
    df.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    return df, ""


@register_st_cache
@st.cache_data(ttl=TTL_10MIN, show_spinner=False)
def _cached_usdtwd_series(days: int) -> tuple[pd.DataFrame, str]:
    """只快取成功結果:`_FetchFailed` 從這一層直接穿過去,不會被存下來。"""
    return _fetch_usdtwd_series_uncached(days)


def fetch_usdtwd_series(days: int) -> tuple[pd.DataFrame, str]:
    """抓 USDTWD=X 時序（複用 macro_repository.fetch_yf_close + NAS proxy）。

    Returns: (df[date, usdtwd], error_msg or "")

    ⚠️ 回傳形狀與訊息內容與改版前**逐字相同**;變的只有「失敗結果不再進快取」。
    """
    try:
        return _cached_usdtwd_series(days)
    except _FetchFailed as e:
        return pd.DataFrame(columns=["date", "usdtwd"]), str(e)


# ── `.clear` 相容性:公開名字必須保有 `.clear()` ────────────────────────
#
# ⚠️ **這段不是可有可無的糖衣,拿掉會靜默壞掉一個按鈕。**
# `services/macro/__init__.py::clear_tab1_macro_caches`(Tab1「強制重抓」)是這樣寫的:
#
#     for _fn in (fetch_foreign_flow_series, fetch_usdtwd_series):
#         try:
#             _fn.clear()
#             _stat["st_cache_cleared"] += 1
#         except Exception:
#             pass
#
# `.clear()` 包在 `except Exception: pass` 裡,而計數只在成功時才 +1。
# 拆函式之後公開名字若失去 `.clear`,會 `AttributeError` → 被 `pass` 吞掉 →
# `st_cache_cleared` 靜默停在 0 →「強制重抓」按鈕默默失效,**沒有任何人會發現**。
# `tests/test_hot_money.py::_patch_finmind` 的 `if hasattr(..., 'clear')` 同理。
#
# ⚠️ 為什麼是 `getattr` 而不是直接 `= _cached_x.clear`:
# `conftest.py::_stub_cache_decorator`(無 streamlit 的測試環境)回傳的是**原函式、
# 沒有 `.clear`** —— 無條件取用會在 **import 期**就 `AttributeError`,連鎖弄紅多個
# 測試檔。無快取 = 無需清,退化成 no-op 才是正確語意
# (與 `pool_repository` / `ui/helpers/macro/ndc.py` 既有的 try/except 降級慣例一致)。
def _bind_clear(public_fn, cached_fn) -> None:
    _c = getattr(cached_fn, "clear", None)
    public_fn.clear = _c if callable(_c) else (lambda: None)


_bind_clear(fetch_foreign_flow_series, _cached_foreign_flow_series)
_bind_clear(fetch_usdtwd_series, _cached_usdtwd_series)

# `__wrapped__`:讓 `inspect.getsource(fetch_*)` / `inspect.signature` 看穿到真實實作。
# `tests/test_provenance_phase2.py` 就是用 `inspect.getsource` 檢查 provenance attrs
# 有沒有被設 —— 指到實作而不是薄 wrapper,那個檢查才量得到它要量的東西。
fetch_foreign_flow_series.__wrapped__ = _fetch_foreign_flow_series_uncached
fetch_usdtwd_series.__wrapped__ = _fetch_usdtwd_series_uncached
