"""v19.47 美股流動性 × 熱錢監測引擎.

對應 user 反饋：「Fund 應放美股熱錢（非台股），美股熱錢 != FED 升降息」
6 指標三角架構：
  - 流動性：M2 YoY / WALCL (Fed BS) / RRP
  - 信用：HY OAS / HYG-LQD 比
  - 情緒：AAII bull-bear spread（best-effort scrape）

對外 API:
  fetch_us_liquidity_snapshot(fred_api_key) -> dict[name, result_dict]
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from infra.cache import _ttl_cache, register_cache
from shared.ttls import TTL_30MIN
from shared.fred_series import (
    FRED_FED_BS,
    FRED_HY_SPREAD,
    FRED_M2,
    FRED_RRP,
)
from repositories.macro_repository import (
    fetch_aaii_sentiment,
    fetch_fred,
    fetch_yf_close,
)


def _hy_oas(api_key: str) -> dict:
    """HY 信用利差 OAS (BAMLH0A0HYM2, % OAS)."""
    try:
        df = fetch_fred(FRED_HY_SPREAD, api_key, n=60)
        if df.empty:
            return {"_err": "FRED empty"}
        cur = float(df["value"].iloc[-1])
        m1 = float(df["value"].iloc[-22]) if len(df) >= 22 else cur
        delta_bp = (cur - m1) * 100
        if cur >= 5.5:
            color, label = "#f85149", "🔴 信用緊縮 / 熱錢撤離"
        elif cur >= 4.0:
            color, label = "#d29922", "⚠️ 風險偏好下滑"
        else:
            color, label = "#3fb950", "✅ 信用寬鬆 / 風險偏好強"
        return {
            "value": cur,
            "unit": "%",
            "delta_bp": delta_bp,
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
        }
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def _rrp(api_key: str) -> dict:
    """隔夜逆回購 RRP (RRPONTSYD, USD bn) — 流動性蓄水池."""
    try:
        df = fetch_fred(FRED_RRP, api_key, n=60)
        if df.empty:
            return {"_err": "FRED empty"}
        cur = float(df["value"].iloc[-1])
        m1 = float(df["value"].iloc[-22]) if len(df) >= 22 else cur
        delta = cur - m1
        if cur < 100:
            color, label = "#d29922", "💧 流動性枯竭警示"
        elif cur < 1000:
            color, label = "#3fb950", "✅ 流動性正常"
        else:
            color, label = "#58a6ff", "🌊 流動性過剩 / QE 蓄水"
        return {
            "value": cur,
            "unit": "B",
            "delta": delta,
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
        }
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def _m2_yoy(api_key: str) -> dict:
    """M2 廣義貨幣供給 YoY (M2SL)."""
    try:
        df = fetch_fred(FRED_M2, api_key, n=24)
        if df.empty or len(df) < 13:
            return {"_err": "FRED insufficient data"}
        cur = float(df["value"].iloc[-1])
        yr_ago = float(df["value"].iloc[-13])
        yoy = (cur / yr_ago - 1) * 100
        if yoy > 10:
            color, label = "#f85149", "🔴 貨幣供給過熱（通膨壓力）"
        elif yoy > 4:
            color, label = "#3fb950", "✅ 寬鬆 / 熱錢充裕"
        elif yoy > 0:
            color, label = "#d29922", "⚠️ 中性偏緊"
        else:
            color, label = "#58a6ff", "🔵 貨幣緊縮 / 衰退警示"
        return {
            "value": yoy,
            "unit": "%",
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
        }
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def _walcl(api_key: str) -> dict:
    """Fed 資產負債表 WALCL (USD mn) — QE/QT pace (13 週 = ~3 月)."""
    try:
        df = fetch_fred(FRED_FED_BS, api_key, n=60)
        if df.empty:
            return {"_err": "FRED empty"}
        cur_mn = float(df["value"].iloc[-1])
        cur_tn = cur_mn / 1e6
        delta_tn = 0.0
        if len(df) >= 13:
            prev_mn = float(df["value"].iloc[-13])
            delta_tn = (cur_mn - prev_mn) / 1e6
        if delta_tn > 0.1:
            color, label = "#3fb950", "💧 QE 擴表（流動性釋放）"
        elif delta_tn > -0.1:
            color, label = "#d29922", "➖ 觀望 / 中性"
        else:
            color, label = "#f85149", "🔴 QT 縮表（流動性回收）"
        return {
            "value": cur_tn,
            "unit": "T",
            "delta": delta_tn,
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
        }
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def _hyg_lqd_ratio() -> dict:
    """HYG (高收益債 ETF) / LQD (投等債 ETF) — 風險偏好."""
    try:
        hyg = fetch_yf_close("HYG", range_="3mo", interval="1d")
        lqd = fetch_yf_close("LQD", range_="3mo", interval="1d")
        if hyg.empty or lqd.empty:
            return {"_err": "Yahoo empty"}
        align = pd.concat([hyg, lqd], axis=1, join="inner").dropna()
        if align.empty:
            return {"_err": "no overlap"}
        align.columns = ["hyg", "lqd"]
        ratio = align["hyg"] / align["lqd"]
        cur = float(ratio.iloc[-1])
        m1 = float(ratio.iloc[-22]) if len(ratio) >= 22 else cur
        delta_pct = (cur / m1 - 1) * 100 if m1 != 0 else 0.0
        if delta_pct > 1:
            color, label = "#3fb950", "✅ 風險偏好上升 / 熱錢進股"
        elif delta_pct > -1:
            color, label = "#d29922", "➖ 持平"
        else:
            color, label = "#f85149", "🔴 risk-off / 熱錢撤離"
        return {
            "value": cur,
            "unit": "",
            "delta_pct": delta_pct,
            "color": color,
            "label": label,
            "date": str(align.index[-1])[:10],
        }
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def _aaii_with_judgment() -> dict:
    """AAII 散戶情緒 + 業務判讀（color/label）.

    F-H1 v19.77：raw I/O 已下沉 `repositories.macro_repository.fetch_aaii_sentiment`,
    本函式專責 spread → color/label 的 business judgment(L2 純函式)。
    """
    raw = fetch_aaii_sentiment()
    if "_err" in raw:
        return raw
    spread = raw["value"]
    if spread > 20:
        color, label = "#f85149", "🔴 散戶過度樂觀（反指標：賣訊號）"
    elif spread < -20:
        color, label = "#3fb950", "✅ 散戶過度悲觀（反指標：買訊號）"
    else:
        color, label = "#d29922", "➖ 情緒中性"
    return {**raw, "color": color, "label": label}


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)   # P1：美股流動性 6 指標，rerun 免重打 FRED
def fetch_us_liquidity_snapshot(fred_api_key: str) -> dict:
    """6 指標 ThreadPoolExecutor 並行抓取，每 task 20s timeout."""
    jobs = {
        "hy_oas": lambda: _hy_oas(fred_api_key),
        "rrp": lambda: _rrp(fred_api_key),
        "m2_yoy": lambda: _m2_yoy(fred_api_key),
        "walcl": lambda: _walcl(fred_api_key),
        "hyg_lqd": _hyg_lqd_ratio,
        "aaii": _aaii_with_judgment,
    }
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=6) as ex:
        futs = {ex.submit(fn): name for name, fn in jobs.items()}
        for fut in futs:
            name = futs[fut]
            try:
                out[name] = fut.result(timeout=20)
            except Exception as e:
                out[name] = {"_err": f"{type(e).__name__}: {str(e)[:60]}"}
    return out
