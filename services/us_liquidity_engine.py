"""v19.47 美股流動性 × 熱錢監測引擎.

對應 user 反饋：「Fund 應放美股熱錢（非台股），美股熱錢 != FED 升降息」
7 指標三角架構：
  - 流動性：M2 YoY / WALCL (Fed BS) / RRP / 淨流動性(WALCL−RRP−TGA, v19.192)
  - 信用：HY OAS / HYG-LQD 比
  - 情緒：AAII bull-bear spread（best-effort scrape）

對外 API:
  fetch_us_liquidity_snapshot(fred_api_key) -> dict[name, result_dict]
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from infra.cache import _ttl_cache, register_cache
from shared.colors import INFO_BLUE, TRAFFIC_GREEN, TRAFFIC_RED, TRAFFIC_YELLOW
from shared.ttls import TTL_30MIN
from shared.fred_series import (
    FRED_FED_BS,
    FRED_HY_SPREAD,
    FRED_M2,
    FRED_RRP,
    FRED_TGA,
)
from repositories.macro_repository import (
    fetch_aaii_sentiment,
    fetch_fred,
    fetch_yf_close,
)

# ════════════════════════════════════════════════════════════════
# v19.188 — 美股流動性 6 指標判讀 cut-off（SSOT）
# 同時供 ① 各 fetcher 的 color/label 判讀、② Tab1 卡片 sparkline 的 SPEC 線。
# 兩處共用同一常數 → 卡片燈色與 SPEC 線永遠同源（§3.3 反捏造：禁止 inline magic）。
# ════════════════════════════════════════════════════════════════
HY_OAS_WARN_PCT: float = 4.0       # HY OAS ≥ → 風險偏好下滑（黃）
HY_OAS_CRISIS_PCT: float = 5.5     # HY OAS ≥ → 信用緊縮 / 熱錢撤離（紅）
M2_YOY_HOT_PCT: float = 10.0       # M2 YoY > → 貨幣供給過熱（紅）
M2_YOY_LOOSE_PCT: float = 4.0      # M2 YoY > → 寬鬆 / 熱錢充裕（綠）
RRP_DRAIN_BN: float = 100.0        # RRP < → 流動性枯竭警示（黃）
RRP_GLUT_BN: float = 1000.0        # RRP ≥ → 流動性過剩 / QE 蓄水（藍）
AAII_EUPHORIA_PCT: float = 20.0    # AAII spread > → 散戶過度樂觀（反指標賣訊）
AAII_PANIC_PCT: float = -20.0      # AAII spread < → 散戶過度悲觀（反指標買訊）
# v19.192 — 淨流動性 Δ13週 cut-off（兆美元 T）。淨流動性 = Fed資產 − RRP − TGA。
# 較 WALCL 單卡的 ±0.1T 寬，因 TGA/RRP 波動大（債限/繳稅季），避免雜訊亂跳。
NET_LIQ_EXPAND_TN: float = 0.2     # Δ13週 > → 淨流動性擴張 / 股市燃料增（綠）
NET_LIQ_DRAIN_TN: float = -0.2     # Δ13週 < → 淨流動性收縮 / 股市缺燃料（紅）


def _hy_oas(api_key: str) -> dict:
    """HY 信用利差 OAS (BAMLH0A0HYM2, % OAS)."""
    try:
        df = fetch_fred(FRED_HY_SPREAD, api_key, n=60)
        if df.empty:
            return {"_err": "FRED empty"}
        cur = float(df["value"].iloc[-1])
        m1 = float(df["value"].iloc[-22]) if len(df) >= 22 else cur
        delta_bp = (cur - m1) * 100
        if cur >= HY_OAS_CRISIS_PCT:
            color, label = TRAFFIC_RED, "🔴 信用緊縮 / 熱錢撤離"
        elif cur >= HY_OAS_WARN_PCT:
            color, label = TRAFFIC_YELLOW, "⚠️ 風險偏好下滑"
        else:
            color, label = TRAFFIC_GREEN, "✅ 信用寬鬆 / 風險偏好強"
        return {
            "value": cur,
            "unit": "%",
            "delta_bp": delta_bp,
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
            "source": f"FRED:{FRED_HY_SPREAD}",
            # v19.188 sparkline:近 30 期 OAS level（% 單位，與卡片 SPEC 線同尺）
            "series": [float(x) for x in df["value"].dropna().tail(30).tolist()],
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
        if cur < RRP_DRAIN_BN:
            color, label = TRAFFIC_YELLOW, "💧 流動性枯竭警示"
        elif cur < RRP_GLUT_BN:
            color, label = TRAFFIC_GREEN, "✅ 流動性正常"
        else:
            color, label = INFO_BLUE, "🌊 流動性過剩 / QE 蓄水"
        return {
            "value": cur,
            "unit": "B",
            "delta": delta,
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
            "source": f"FRED:{FRED_RRP}",
            # v19.188 sparkline:近 30 期 RRP level（USD bn）
            "series": [float(x) for x in df["value"].dropna().tail(30).tolist()],
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
        if yoy > M2_YOY_HOT_PCT:
            color, label = TRAFFIC_RED, "🔴 貨幣供給過熱（通膨壓力）"
        elif yoy > M2_YOY_LOOSE_PCT:
            color, label = TRAFFIC_GREEN, "✅ 寬鬆 / 熱錢充裕"
        elif yoy > 0:
            color, label = TRAFFIC_YELLOW, "⚠️ 中性偏緊"
        else:
            color, label = INFO_BLUE, "🔵 貨幣緊縮 / 衰退警示"
        # v19.188 sparkline:YoY 序列（與 value 同尺，非 level），近 12 期
        _yoy_ser = (df["value"] / df["value"].shift(12) - 1) * 100
        return {
            "value": yoy,
            "unit": "%",
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
            "source": f"FRED:{FRED_M2}",
            "series": [float(x) for x in _yoy_ser.dropna().tail(12).tolist()],
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
            color, label = TRAFFIC_GREEN, "💧 QE 擴表（流動性釋放）"
        elif delta_tn > -0.1:
            color, label = TRAFFIC_YELLOW, "➖ 觀望 / 中性"
        else:
            color, label = TRAFFIC_RED, "🔴 QT 縮表（流動性回收）"
        return {
            "value": cur_tn,
            "unit": "T",
            "delta": delta_tn,
            "color": color,
            "label": label,
            "date": str(df["date"].iloc[-1])[:10],
            "source": f"FRED:{FRED_FED_BS}",
            # v19.188 sparkline:WALCL level 換算兆美元（與 value 同尺 T）
            "series": [float(x) / 1e6 for x in df["value"].dropna().tail(30).tolist()],
        }
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def net_liquidity_series(df_walcl, df_rrp, df_tga):
    """純函式：Fed資產(WALCL) − RRP − TGA → 週頻淨流動性序列（兆美元 T，DatetimeIndex）。

    SSOT：顯示卡(_net_liquidity)與評分(macro_service FED_BS 槽)共用同一份計算，
    避免兩處各算一次導致數字不一致（user 2026-06-27 要求資料 SSOT）。
    單位陷阱(§4.1)：WALCL/TGA = 百萬、RRP = 十億 → 換 T 前係數不同。
    時序(§4.5)：WALCL/TGA 週頻、RRP 日頻 → merge_asof backward(tol 7d)對齊週三格，不吃未來。
    缺資料 / 無重疊 → 回空 Series（呼叫端依 §1 Fail Loud 決定降級）。
    """
    _MN_TO_TN = 1e6   # 百萬美元 → 兆美元
    _BN_TO_TN = 1e3   # 十億美元 → 兆美元
    if df_walcl is None or df_rrp is None or df_tga is None:
        return pd.Series(dtype=float)
    if df_walcl.empty or df_rrp.empty or df_tga.empty:
        return pd.Series(dtype=float)
    w = df_walcl[["date", "value"]].copy(); w["w_tn"] = w["value"] / _MN_TO_TN
    t = df_tga[["date", "value"]].copy(); t["t_tn"] = t["value"] / _MN_TO_TN
    r = df_rrp[["date", "value"]].copy(); r["r_tn"] = r["value"] / _BN_TO_TN
    for _d in (w, t, r):
        _d["date"] = pd.to_datetime(_d["date"])
        _d.sort_values("date", inplace=True)
    m = pd.merge_asof(w[["date", "w_tn"]], t[["date", "t_tn"]], on="date",
                      direction="backward", tolerance=pd.Timedelta("7D"))
    m = pd.merge_asof(m, r[["date", "r_tn"]], on="date",
                      direction="backward", tolerance=pd.Timedelta("7D"))
    m = m.dropna(subset=["w_tn", "t_tn", "r_tn"])
    if m.empty:
        return pd.Series(dtype=float)
    return pd.Series(
        (m["w_tn"] - m["r_tn"] - m["t_tn"]).to_numpy(),
        index=pd.DatetimeIndex(m["date"]), name="net_liq_tn",
    )


def _net_liquidity(api_key: str) -> dict:
    """淨流動性 = Fed資產(WALCL) − 隔夜逆回購(RRP) − 政府帳戶(TGA)，全部換算兆美元(T)。

    白話：市場上「真正能流進股市的錢」。Fed 放的水(WALCL)扣掉停在央行的閒錢(RRP)
    與卡在政府帳戶的錢(TGA)，剩下的才是股市的燃料。

    單位陷阱（§4.1）：WALCL/TGA = 百萬美元、RRP = 十億美元 → 換算 T 前係數**不同**：
        WALCL(mn)/1e6 = T ; TGA(mn)/1e6 = T ; RRP(bn)/1e3 = T
    時序對齊（§4.5）：WALCL/TGA 週頻(週三)、RRP 日頻 → merge_asof backward(tol 7d)
        對齊到週三格，不 lookahead、不偽造每日值。
    Δ13週(≈1季)對齊 WALCL QE/QT pace。§1 Fail Loud：任一 series 缺 → _err 不捏造。
    """
    try:
        df_w = fetch_fred(FRED_FED_BS, api_key, n=40)    # WALCL 百萬,週頻
        df_t = fetch_fred(FRED_TGA, api_key, n=40)       # TGA   百萬,週頻
        df_r = fetch_fred(FRED_RRP, api_key, n=260)      # RRP   十億,日頻(多抓供對齊週三格)
        if df_w.empty or df_t.empty or df_r.empty:
            return {"_err": "FRED empty (WALCL/RRP/TGA 任一缺)"}
        s = net_liquidity_series(df_w, df_r, df_t)   # SSOT 共用序列(兆美元 T)
        if s.empty:
            return {"_err": "net-liq 對齊後無有效列"}
        cur = float(s.iloc[-1])
        delta_tn = 0.0
        if len(s) >= 13:
            delta_tn = cur - float(s.iloc[-13])
        if delta_tn > NET_LIQ_EXPAND_TN:
            color, label = TRAFFIC_GREEN, "💧 淨流動性擴張（股市燃料增）"
        elif delta_tn < NET_LIQ_DRAIN_TN:
            color, label = TRAFFIC_RED, "🔴 淨流動性收縮（股市缺燃料）"
        else:
            color, label = TRAFFIC_YELLOW, "➖ 淨流動性中性"
        return {
            "value": cur,
            "unit": "T",
            "delta": delta_tn,
            "color": color,
            "label": label,
            "date": str(s.index[-1])[:10],
            "source": f"FRED:{FRED_FED_BS}-{FRED_RRP}-{FRED_TGA}",
            # sparkline:淨流動性 level（兆美元 T；delta-based 判讀,無單一 SPEC 線）
            "series": [round(float(x), 3) for x in s.tail(30).tolist()],
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
            color, label = TRAFFIC_GREEN, "✅ 風險偏好上升 / 熱錢進股"
        elif delta_pct > -1:
            color, label = TRAFFIC_YELLOW, "➖ 持平"
        else:
            color, label = TRAFFIC_RED, "🔴 risk-off / 熱錢撤離"
        return {
            "value": cur,
            "unit": "",
            "delta_pct": delta_pct,
            "color": color,
            "label": label,
            "date": str(align.index[-1])[:10],
            "source": "Yahoo:fetch_yf_close:HYG/LQD:ratio",
            # v19.188 sparkline:HYG/LQD 比序列（近 30 交易日）
            "series": [float(x) for x in ratio.dropna().tail(30).tolist()],
        }
    except Exception as e:
        return {"_err": f"{type(e).__name__}: {e}"}


def _aaii_with_judgment() -> dict:
    """AAII 散戶情緒 + 業務判讀（color/label）.

    F-H1 v19.77：raw I/O 已下沉 `repositories.macro_repository.fetch_aaii_sentiment`,
    本函式專責 spread → color/label 的 business judgment(L2 純函式)。

    v19.267 D8 #5:加 schema 驗證(graceful — 驗失敗回 _err token,L2 流程不中斷)。
    """
    raw = fetch_aaii_sentiment()
    # F-SCHEMA-1 v19.267 D8 #5:出口 schema 驗證(失敗 graceful 轉 _err token)
    try:
        from shared.schemas import validate_aaii_sentiment
        raw = validate_aaii_sentiment(raw)
    except ValueError as _ve:
        print(f"[us_liquidity/aaii/schema] 驗證失敗:{_ve}")
        raw = {"_err": f"AAII schema 驗證失敗:{str(_ve)[:120]}",
               "source": raw.get("source", "AAII:scrape:sentiment_spread"),
               "fetched_at": raw.get("fetched_at", "")}
    if "_err" in raw:
        return raw
    spread = raw["value"]
    if spread > AAII_EUPHORIA_PCT:
        color, label = TRAFFIC_RED, "🔴 散戶過度樂觀（反指標：賣訊號）"
    elif spread < AAII_PANIC_PCT:
        color, label = TRAFFIC_GREEN, "✅ 散戶過度悲觀（反指標：買訊號）"
    else:
        color, label = TRAFFIC_YELLOW, "➖ 情緒中性"
    # F-PROV-1 phase 19 v19.105 — provenance(若上游 fetch_aaii_sentiment 已寫入 source 則保留)
    out = {**raw, "color": color, "label": label}
    out.setdefault("source", "AAII:scrape:sentiment_spread")
    return out


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)   # P1：美股流動性 6 指標，rerun 免重打 FRED
def fetch_us_liquidity_snapshot(fred_api_key: str) -> dict:
    """6 指標 ThreadPoolExecutor 並行抓取，每 task 20s timeout."""
    jobs = {
        "hy_oas": lambda: _hy_oas(fred_api_key),
        "rrp": lambda: _rrp(fred_api_key),
        "m2_yoy": lambda: _m2_yoy(fred_api_key),
        "walcl": lambda: _walcl(fred_api_key),
        "net_liq": lambda: _net_liquidity(fred_api_key),   # v19.192 淨流動性 = WALCL−RRP−TGA
        "hyg_lqd": _hyg_lqd_ratio,
        "aaii": _aaii_with_judgment,
    }
    out: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=7) as ex:
        futs = {ex.submit(fn): name for name, fn in jobs.items()}
        for fut in futs:
            name = futs[fut]
            try:
                out[name] = fut.result(timeout=20)
            except Exception as e:
                out[name] = {"_err": f"{type(e).__name__}: {str(e)[:60]}"}
    # F-PROV-1 phase 19 v19.105 — orchestrator-level provenance(每個子指標的來源 + fetched_at)
    sources = {n: r.get("source") for n, r in out.items() if isinstance(r, dict) and "source" in r}
    if sources:
        out["_provenance"] = {
            "sources": sources,
            "fetched_at": pd.Timestamp.now('UTC').isoformat(),
            "orchestrator": "us_liquidity_engine.fetch_us_liquidity_snapshot",
        }
    return out
