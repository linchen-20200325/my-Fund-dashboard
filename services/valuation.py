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

GREEN = "#22c55e"
YELLOW = "#eab308"
ORANGE = "#fb923c"
RED = "#ef4444"
GRAY = "#888888"

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


def fetch_forward_pe() -> Optional[float]:
    """從 yfinance Ticker.info 抓 ^GSPC forwardPE；任意失敗回 None。"""
    try:
        import yfinance as yf
        info = yf.Ticker("^GSPC").info
        v = info.get("forwardPE")
        return float(v) if v else None
    except Exception:
        return None


def fetch_gdpnow(fred_api_key: str) -> Optional[float]:
    """從 FRED 抓 GDPNOW 系列最新一筆；任意失敗回 None。"""
    if not fred_api_key:
        return None
    try:
        from repositories.macro_repository import fetch_fred
        df = fetch_fred("GDPNOW", fred_api_key, n=10)
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
