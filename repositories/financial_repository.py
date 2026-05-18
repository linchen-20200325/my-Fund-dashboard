"""repositories/financial_repository.py — 個股財報 I/O（yfinance 中繼）

職責：個股 ticker 解析 + yfinance 季財報抓取與三率計算（毛利率/營益率/淨利率）。
這層只負責「拿資料」，不做業務評分（評分留 services/precision_service.py 內的
PrecisionStrategyEngine.evaluate_fund_three_ratios，吃本層輸出）。

v11.0 B-B（v18.116）：從 services/precision_service.py 抽出，去除原 docstring
警示的「fetch_stock_three_ratios 違反 service 純度」技術債。

公開 API：
- _TW_NAME_MAP / _US_NAME_MAP — 持倉名稱對照表
- resolve_ticker(name) -> str|None — 名稱 → ticker symbol
- fetch_stock_three_ratios(holding_name) -> dict|None — yfinance 抓兩季 + 計算三率 QoQ
"""
from __future__ import annotations

import logging
import re


logger = logging.getLogger("financial_repository")


# ── 常見持倉名稱 → Ticker 對照表 ─────────────────────────────────────
_TW_NAME_MAP: dict[str, str] = {
    "台積電": "2330.TW", "聯發科": "2454.TW", "鴻海":   "2317.TW",
    "聯電":   "2303.TW", "日月光": "3711.TW", "瑞昱":   "2379.TW",
    "力積電": "6770.TW", "南亞科": "2408.TW", "威剛":   "4967.TW",
    "富邦金": "2881.TW", "國泰金": "2882.TW", "中信金": "2891.TW",
    "兆豐金": "2886.TW", "台新金": "2887.TW", "玉山金": "2884.TW",
    "台達電": "2308.TW", "廣達":   "2382.TW", "緯創":   "3231.TW",
    "群聯":   "8299.TW", "旺宏":   "2337.TW", "大立光": "3008.TW",
}
_US_NAME_MAP: dict[str, str] = {
    "NVIDIA": "NVDA", "APPLE": "AAPL", "MICROSOFT": "MSFT",
    "ALPHABET": "GOOGL", "GOOGLE": "GOOGL", "AMAZON": "AMZN",
    "META": "META", "TESLA": "TSLA", "BROADCOM": "AVGO",
    "QUALCOMM": "QCOM", "TSMC": "TSM", "SAMSUNG": "005930.KS",
    "ASML": "ASML", "AMD": "AMD", "INTEL": "INTC",
    "JPMORGAN": "JPM", "BERKSHIRE": "BRK-B", "VISA": "V",
    "MASTERCARD": "MA", "EXXON": "XOM", "UNITEDHEALTH": "UNH",
    "JOHNSON": "JNJ", "ABBVIE": "ABBV", "ELI LILLY": "LLY",
    "NOVO NORDISK": "NVO", "NETFLIX": "NFLX", "SALESFORCE": "CRM",
}


def resolve_ticker(name: str) -> str | None:
    """從持倉名稱解析 ticker symbol。

    優先順序：
      1. 台股 4 碼數字 → "{code}.TW"
      2. 中文名稱對照（_TW_NAME_MAP）
      3. 英文公司名對照（_US_NAME_MAP，部分匹配）
      4. 2~5 大寫字母直接當 Ticker（如 NVDA / AAPL）
      5. 都不命中 → None
    """
    if not name:
        return None
    name_up = name.upper().strip()

    # 1. 台股 4 碼
    tw_match = re.search(r"\b(\d{4})\b", name)
    if tw_match:
        return tw_match.group(1) + ".TW"

    # 2. 中文名稱對照
    for cn_key, sym in _TW_NAME_MAP.items():
        if cn_key in name:
            return sym

    # 3. 英文公司名對照（部分匹配）
    for en_key, sym in _US_NAME_MAP.items():
        if en_key in name_up:
            return sym

    # 4. 純大寫短代碼
    if re.fullmatch(r"[A-Z]{2,5}", name_up):
        return name_up

    return None


def fetch_stock_three_ratios(holding_name: str) -> dict | None:
    """yfinance 抓兩季財報，計算三率（毛利率/營益率/淨利率）QoQ 差值。

    Args:
        holding_name: 持倉名稱（中英文皆可，內部會經 resolve_ticker 轉 ticker）

    Returns:
        成功 → {"stock", "ticker", "q_new", "q_old",
                "gross_margin_new/old/diff",
                "op_margin_new/old/diff",
                "net_margin_new/old/diff"}
        無法解析 / 財報資料不足 / yfinance 失敗 → None
    """
    ticker_sym = resolve_ticker(holding_name)
    if not ticker_sym:
        logger.debug("無法解析 Ticker: %s", holding_name)
        return None
    try:
        import yfinance as yf
        tkr = yf.Ticker(ticker_sym)
        # 相容新舊 yfinance API
        qf = getattr(tkr, "quarterly_income_stmt", None)
        if qf is None or (hasattr(qf, "empty") and qf.empty):
            qf = getattr(tkr, "quarterly_financials", None)
        if qf is None or (hasattr(qf, "empty") and qf.empty) or qf.shape[1] < 2:
            return None

        def _find_row(keywords: list):
            """不分大小寫、忽略空格，匹配第一個命中的財報列。"""
            for kw in keywords:
                matches = [i for i in qf.index
                           if kw.lower() in str(i).lower().replace(" ", "")]
                if matches:
                    return qf.loc[matches[0]]
            return None

        rev = _find_row(["totalrevenue", "revenue"])
        gp  = _find_row(["grossprofit"])
        op  = _find_row(["operatingincome", "ebit"])
        ni  = _find_row(["netincome"])
        if rev is None:
            return None

        quarters = []
        for i in range(min(2, qf.shape[1])):
            r = float(rev.iloc[i])
            if not r:
                continue
            quarters.append({
                "quarter":      str(qf.columns[i])[:10],
                "gross_margin": round(float(gp.iloc[i]) / r * 100, 2) if gp is not None else None,
                "op_margin":    round(float(op.iloc[i]) / r * 100, 2) if op is not None else None,
                "net_margin":   round(float(ni.iloc[i]) / r * 100, 2) if ni is not None else None,
            })
        if len(quarters) < 2:
            return None

        def _diff(key: str) -> float:
            v0, v1 = quarters[0].get(key), quarters[1].get(key)
            return round(v0 - v1, 2) if (v0 is not None and v1 is not None) else 0.0

        return {
            "stock":             holding_name,
            "ticker":            ticker_sym,
            "q_new":             quarters[0]["quarter"],
            "q_old":             quarters[1]["quarter"],
            "gross_margin_new":  quarters[0].get("gross_margin"),
            "gross_margin_old":  quarters[1].get("gross_margin"),
            "op_margin_new":     quarters[0].get("op_margin"),
            "op_margin_old":     quarters[1].get("op_margin"),
            "net_margin_new":    quarters[0].get("net_margin"),
            "net_margin_old":    quarters[1].get("net_margin"),
            "gross_margin_diff": _diff("gross_margin"),
            "op_margin_diff":    _diff("op_margin"),
            "net_margin_diff":   _diff("net_margin"),
        }
    except Exception as e:
        logger.warning("三率抓取失敗 %s(%s): %s", holding_name, ticker_sym, e)
        return None
