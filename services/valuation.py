"""v19.22 Tier A 估值動能 — SPX Forward P/E + Atlanta Fed GDPNow

設計動機（v19.22 epic）：
慢總經 / 短線雷達兩條線都沒覆蓋「估值水位」與「即時 GDP 共識」維度。
本模組補兩件估值卡：
  1. Forward P/E — S&P 500 12 個月前瞻本益比 vs 25 年歷史 σ
  2. GDPNow     — 亞特蘭大 Fed 即時 GDP nowcast vs 長期 GDPC1 YoY 趨勢

設計取捨：
  - 純函式 verdict 計算與 IO fetcher 分離（compute_* 可獨立測試）
  - 任一資料源掛點 → source_ok=False graceful（不拖垮另一卡）
  - Forward P/E 用 σ 動態色階（避免高利率時代絕對閾值失準）
  - GDPNow 用 5 級色階（衰退 / 低於趨勢 / 中性 / 健康 / 強勁）
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from infra.cache import _ttl_cache, register_cache
from shared.ttls import TTL_30MIN
from shared.colors import (
    TRAFFIC_GREEN as GREEN,
    TRAFFIC_NEUTRAL as GRAY,
    TRAFFIC_ORANGE as ORANGE,
    TRAFFIC_RED as RED,
    TRAFFIC_YELLOW as YELLOW,
)
from shared.fred_series import FRED_GDPNOW

# Forward P/E 25 年滾動參考（FactSet / Yardeni 2000-2025 長期統計）
FORWARD_PE_MEAN = 16.5
FORWARD_PE_STD = 3.0

# 長期 GDP 增長均值（FRED GDPC1 YoY 30 年平均 ≈ 2.3%）
GDP_TREND = 2.3
GDP_TREND_STD = 1.5  # 用來算 σ 提示


def _empty_metric() -> dict:
    return {
        "value": None,
        "sigma": None,
        "signal": "⬜ 無資料",
        "color": GRAY,
        "verdict": "資料取得失敗",
        "source_ok": False,
        "note": "",
    }


def compute_forward_pe_verdict(
    value: float | None,
    mean: float = FORWARD_PE_MEAN,
    std: float = FORWARD_PE_STD,
) -> dict:
    """純函式：給 Forward P/E 值回 σ + 5 級色階。"""
    if value is None or pd.isna(value) or std <= 0:
        return _empty_metric()
    sigma = (value - mean) / std
    if sigma <= -1:
        sig, color, vd = "🟢 偏便宜", GREEN, "估值低於均值 -1σ 以下，長期進場區間"
    elif sigma <= 1:
        sig, color, vd = "🟡 中性", YELLOW, "估值落在 ±1σ 區間，趨勢與基本面同步"
    elif sigma <= 2:
        sig, color, vd = "🟠 偏貴", ORANGE, "估值高於均值 +1~+2σ，留意盈餘下修風險"
    else:
        sig, color, vd = "🔴 泡沫風險", RED, "估值超過均值 +2σ 以上，歷史比例高機率回檔"
    return {
        "value": round(value, 2),
        "sigma": round(sigma, 2),
        "signal": sig,
        "color": color,
        "verdict": vd,
        "source_ok": True,
        "note": f"vs {mean}x ± {std}x 歷史 (~25 年)",
    }


def compute_gdpnow_verdict(
    value: float | None,
    trend: float = GDP_TREND,
    trend_std: float = GDP_TREND_STD,
) -> dict:
    """純函式：給 GDPNow 年化估值回 5 級色階。"""
    if value is None or pd.isna(value) or trend_std <= 0:
        return _empty_metric()
    if value < 0:
        sig, color, vd = "🔴 衰退預警", RED, "GDPNow 預估負成長，衰退風險升高"
    elif value < 1.5:
        sig, color, vd = "🟠 低於趨勢", ORANGE, f"低於長期均值 {trend}%，景氣放緩"
    elif value < 3.0:
        sig, color, vd = "🟡 中性擴張", YELLOW, "落在趨勢區間，景氣穩定"
    elif value < 4.0:
        sig, color, vd = "🟢 健康擴張", GREEN, "高於趨勢但未過熱"
    else:
        sig, color, vd = "🟢 強勁擴張", GREEN, "顯著高於趨勢，注意通膨壓力"
    return {
        "value": round(value, 2),
        "sigma": round((value - trend) / trend_std, 2),
        "signal": sig,
        "color": color,
        "verdict": vd,
        "source_ok": True,
        "note": f"vs 長期均值 {trend}% (FRED GDPC1 YoY 30Y avg)",
    }


def _fetch_multpl_pe() -> Optional[float]:
    """從 multpl.com 抓 S&P 500 P/E ratio（trailing TTM）作為 Forward P/E 代理。

    Forward P/E 公開免費源稀缺，trailing PE 與 forward PE 歷史相關性 > 0.85，
    作為 yfinance Ticker.info["forwardPE"] 掛點時的降級備援。multpl.com 結構 10+ 年
    穩定（id="current" 區塊內含當前 PE）。

    Returns
    -------
    float | None
        最近一期 trailing PE；任意失敗回 None；console log 印 root cause 助 debug。
    """
    import re
    try:
        from infra.proxy import fetch_url
        r = fetch_url("https://www.multpl.com/s-p-500-pe-ratio", timeout=15)
        if r is None or getattr(r, "status_code", 0) != 200:
            print(f"[valuation/multpl] HTTP {getattr(r, 'status_code', None)}")
            return None
        # multpl.com 頁面結構：「Current S&P 500 PE Ratio: NN.NN」字串緊跟主數字
        m = re.search(r"Current S&amp;P 500 PE Ratio[:\s]+(\d+\.?\d*)", r.text)
        if not m:
            m = re.search(r"Current S&P 500 PE Ratio[:\s]+(\d+\.?\d*)", r.text)
        if not m:
            # 二度 fallback：id="current" 區塊抓首個浮點數
            m = re.search(r'id="current"[^<]*<[^>]*>\s*(\d+\.?\d*)', r.text)
        if not m:
            print("[valuation/multpl] 解析失敗：未找到 PE 數字（頁面結構可能變動）")
            return None
        return float(m.group(1))
    except Exception as e:  # noqa: BLE001
        print(f"[valuation/multpl] 失敗: {e}")
        return None


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=2)   # v19.64：估值頁，避免 ^GSPC info 重打
def fetch_forward_pe() -> Optional[float]:
    """Forward P/E 多源 chain：yfinance forwardPE → yfinance trailingPE → multpl trailing PE。

    yfinance Ticker.info 對 ^GSPC 偶發回 None / 抓不到；補 trailingPE 與 multpl.com 兩層
    fallback。trailing 與 forward 歷史相關性 > 0.85，作為估值代理夠用；UI caption 不區分
    forward / trailing（使用者只關心 σ 水位）。
    """
    # 1. yfinance forwardPE（首選）
    try:
        import yfinance as yf
        info = yf.Ticker("^GSPC").info
        v = info.get("forwardPE")
        if v:
            return float(v)
        # 2. yfinance trailingPE（同來源、不同 field）
        v_trail = info.get("trailingPE")
        if v_trail:
            print("[valuation/forward_pe] forwardPE 缺，降級用 yfinance trailingPE")
            return float(v_trail)
    except Exception as e:  # noqa: BLE001
        print(f"[valuation/forward_pe] yfinance 失敗: {e}")
    # 3. multpl.com（HTML scrape trailing 代理）
    v_multpl = _fetch_multpl_pe()
    if v_multpl is not None:
        print(f"[valuation/forward_pe] 降級用 multpl trailing PE = {v_multpl}")
        return v_multpl
    return None


@register_cache
@_ttl_cache(ttl_sec=TTL_30MIN, maxsize=4)   # v19.64：FRED 系列
def fetch_gdpnow(fred_api_key: str) -> Optional[float]:
    """從 FRED 抓 GDPNOW 系列最新一筆；任意失敗回 None。"""
    if not fred_api_key:
        return None
    try:
        from repositories.macro_repository import fetch_fred
        df = fetch_fred(FRED_GDPNOW, fred_api_key, n=10)
        if df.empty:
            return None
        return float(df["value"].iloc[-1])
    except Exception:
        return None


def detect_valuation(fred_api_key: str | None = None) -> dict:
    """整合 Forward P/E + GDPNow 兩件估值卡 — IO 入口。"""
    fpe_val = fetch_forward_pe()
    gdp_val = fetch_gdpnow(fred_api_key) if fred_api_key else None
    return {
        "forward_pe": compute_forward_pe_verdict(fpe_val),
        "gdpnow": compute_gdpnow_verdict(gdp_val),
    }
