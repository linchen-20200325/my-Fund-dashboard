"""repositories/macro/yf.py — Yahoo Finance Chart API 抓取(B1 拆自 macro_repository v19.205).

從原 1078 LOC god module 拆出:
- YF_CHART_BASE 常數
- fetch_yf_close(單 ticker DatetimeIndex Series)
- fetch_yf_latest(多 ticker 最新值 dict)
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from infra.proxy import fetch_url
from fund_fetcher import _ttl_cache, register_cache
from shared.ttls import TTL_5MIN, TTL_10MIN

YF_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"


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
               provenance(F-PROV-1 v19.83):成功時 `s.attrs` 含
               `source="Yahoo:<ticker>"` + `fetched_at=UTC ISO`。
    """
    url = f"{YF_CHART_BASE}/{ticker}"
    r = fetch_url(
        url,
        params={"interval": interval, "range": range_},
        timeout=15,
        backoff_on_429=False,   # v19.507:Yahoo 限流不會在 2/4/8s 內解除,重試純白等
                                # ~14s/標的 → 總經載入 8 標的爆 75s 逾時。遇 429 直接留空(§1)。
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
        # v19.83 F-PROV-1 phase 2:provenance via Series.attrs(§2.2)
        # Series 無 column 概念,改用 pandas 內建 attrs dict 承載血緣。
        # caller 不存取 attrs 時無感;需要追溯時 s.attrs["source"] / s.attrs["fetched_at"]。
        s.attrs["source"] = f"Yahoo:{ticker}"
        s.attrs["fetched_at"] = pd.Timestamp.now('UTC').isoformat()
    except Exception as e:
        print(f"[macro_core/yf] {ticker} 解析失敗: {e}")
        return pd.Series(dtype=float, name=ticker)
    # v19.161 A1 Phase B:pandera schema 驗 final contract(values+index+attrs)
    # 此驗證**故意放在 parse try-except 之外**,schema 違反(values=NaN /
    # close<=0 / source 缺前綴等)為上游 bug,須當場 raise,**不**靜默返回空 Series。
    from shared.schemas import validate_yf_close
    validate_yf_close(s)
    return s


@register_cache
@_ttl_cache(ttl_sec=TTL_5MIN, maxsize=16)   # v19.64：盤中 ticker rerun dedupe
def fetch_yf_latest(tickers: tuple[str, ...]) -> dict[str, Optional[float]]:
    """批次抓多個 ticker 最新收盤(空值代表抓不到)。

    v19.233 F-PROV-1 cluster C 補洞:加 `_provenance` key(schema-additive,既有
    caller 用 `out[ticker]` 直接 key access 不會踩到 _provenance)。
    """
    out: dict[str, Optional[float]] = {}
    _success_tickers: list[str] = []
    for t in tickers:
        s = fetch_yf_close(t, range_="5d")
        out[t] = round(float(s.iloc[-1]), 4) if not s.empty else None
        if out[t] is not None:
            _success_tickers.append(t)
    out["_provenance"] = {
        "sources": [f"Yahoo:{t}:5d_latest" for t in _success_tickers],
        "fetched_at": pd.Timestamp.now('UTC').isoformat(),
    }
    return out


# ════════════════════════════════════════════════════════════
# 投資組合基準對比序列(v19.531 Phase 1.2 — P-UIHTTP-1 取數下沉)
# ════════════════════════════════════════════════════════════
# 搬遷來源:ui/components/mk_dashboard.py::_get_benchmark_series
# 原實作在 **L3 UI 層**直接 `import yfinance` 抓 SPY/QQQ,並用
# `st.session_state["mk_bench_cache"]` 自建快取 —— 同時命中 CLAUDE.md
# §-1.5.1c v3 §01 三層圖 UI 框那句的兩個動詞:「嚴禁在 UI 層私自
# **存放**或**抓取**原始資料」,且與本檔 `fetch_yf_close` 構成
# v3 §01-2 明禁的「同一資料來源兩套取數實作」(都是 Yahoo 日線收盤)。
#
# 為什麼放這個檔而不是新開一個 repository:
#   本 repo 對「Yahoo 日線收盤」的唯一取數實作就是本檔 `fetch_yf_close`
#   (services/risk_radar、liquidity_engine、crisis_backtest、macro/* 全走它)。
#   基準序列要的正是同一個來源、同一個欄位,只是窗口與 index 表示法不同 ——
#   在本檔加一層薄轉接,SSOT 才會**字面上**留在同一個檔;另開
#   repositories/benchmark_repository.py 只為一個轉接函式,是 §8.1 step 6
#   「用不到的抽象」的反例,且會讓「Yahoo 取數在哪裡」變成兩個答案。
#
# ⚠️ 本函式由 L3 UI(`ui/components/mk_dashboard.py::_get_benchmark_series`)**直呼**,
#   已登錄 CLAUDE.md §8.2.A **EX-PASSTHRU-1**(第 9 組成員)。升級觸發條件見該表 ——
#   其中一條是「本 fetcher 出現第二個 UI caller」,屆時應比照 v19.247 R16 上提 L2。

# Yahoo Chart API 的 `range` 只吃固定枚舉(1d/5d/1mo/3mo/6mo/1y/2y/5y/10y/ytd/max),
# **沒有 "9mo"**。搬遷前 yfinance 用的是 period="9mo",故這裡取 1y 再依日期裁到
# 9 個月,窗口語意與搬遷前一致(不是改成 1y —— 那會讓對比圖的歸一化起點跟著變)。
_BENCHMARK_FETCH_RANGE = "1y"
_BENCHMARK_WINDOW_MONTHS = 9


def fetch_benchmark_close(ticker: str = "SPY") -> Optional[pd.Series]:
    """抓投資組合對比基準(SPY / QQQ 等)近 9 個月日線收盤序列。

    快取:**不自建第二層** —— 直接吃上游 `fetch_yf_close` 的
    `@_ttl_cache(ttl_sec=TTL_10MIN)`(TTL 走 `shared/ttls.py` SSOT,§3.3)。
    同一份資料疊兩層 TTL 會讓失效語意無法推理,故本函式刻意無裝飾器。

    Returns
    -------
    pd.Series | None
        DatetimeIndex(已 normalize 成當日 00:00,與搬遷前 yfinance
        `.history()` + `tz_localize(None)` 的日期表示法一致),value 為收盤價。
        **取不到時回 None**,不回空 Series、更不回假序列(§1 Fail Loud)——
        呼叫端據此顯示「基準目前無法取得」,而不是畫一張空圖假裝正常。
        失敗原因由上游 `fetch_yf_close` 印出。

    Raises
    ------
    AssertionError
        normalize 後索引重複或非遞增(§4.2 不變量;上游 schema 已驗過原始索引,
        這裡守的是本函式自己的後處理)。壞索引會讓「連續兩季落後」比錯期別,
        屬「錯誤的數字比沒有數字更危險」,一律當場炸掉,不靜默修補。
    """
    s = fetch_yf_close(ticker, range_=_BENCHMARK_FETCH_RANGE, interval="1d")
    if s is None or s.empty:
        return None
    _attrs = dict(getattr(s, "attrs", {}) or {})
    out = s.copy()
    # yfinance `.history()` 的日線 index 是「交易所當地午夜」,tz_localize(None)
    # 後即為純日期;Chart API 回的是開盤時刻 epoch(如 13:30Z)。normalize 到當日
    # 00:00 才能與搬遷前的 index 完全對齊(對比圖 x 軸、與基金 NAV 的日期比對)。
    out.index = pd.DatetimeIndex(out.index).normalize()
    cutoff = pd.Timestamp.now("UTC").tz_localize(None).normalize() \
        - pd.DateOffset(months=_BENCHMARK_WINDOW_MONTHS)
    out = out[out.index >= cutoff]
    if out.empty:
        return None
    assert out.index.is_unique, f"fetch_benchmark_close({ticker}): normalize 後日期重複"
    assert out.index.is_monotonic_increasing, \
        f"fetch_benchmark_close({ticker}): 時序未排序"
    out.name = ticker
    # provenance(§2.2):保留上游血緣,補記本函式做過的窗口裁切。
    out.attrs.update(_attrs)
    out.attrs["source"] = _attrs.get("source") or f"Yahoo:{ticker}"
    out.attrs["window"] = f"{_BENCHMARK_WINDOW_MONTHS}mo(from {_BENCHMARK_FETCH_RANGE})"
    return out
