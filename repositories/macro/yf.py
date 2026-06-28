"""repositories/macro/yf.py — v19.203 P2-5 Yahoo Finance Chart fetcher。"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from infra.proxy import fetch_url
from fund_fetcher import _ttl_cache, register_cache
from shared.ttls import TTL_5MIN, TTL_10MIN

from repositories.macro._helpers import YF_CHART_BASE  # noqa: F401


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


