"""test_financial_repository.py — repositories/financial_repository.py 測試
（v18.116 B-B）

涵蓋：
- resolve_ticker 5 條優先序分支（台股 4 碼 / 中文名 / 英文名 / 純大寫短代碼 / None）
- fetch_stock_three_ratios mock yfinance：happy path / 無資料 / 季數不足 / 解析失敗
- 與 services.precision_service 的 proxy 對齊（thin shell delegate）
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd

from repositories import financial_repository as fr


# ════════════════════════════════════════════════════════════
# resolve_ticker — 5 條優先序分支
# ════════════════════════════════════════════════════════════
def test_resolve_ticker_tw_4digit():
    """台股 4 碼數字 → '{code}.TW'。"""
    assert fr.resolve_ticker("台積電 2330") == "2330.TW"
    assert fr.resolve_ticker("0050") == "0050.TW"
    assert fr.resolve_ticker("某基金 6770 持有") == "6770.TW"


def test_resolve_ticker_chinese_name():
    """中文名對照命中（_TW_NAME_MAP）。"""
    assert fr.resolve_ticker("台積電") == "2330.TW"
    assert fr.resolve_ticker("聯發科") == "2454.TW"
    assert fr.resolve_ticker("國泰金") == "2882.TW"


def test_resolve_ticker_english_partial_match():
    """英文名稱部分匹配（_US_NAME_MAP）。"""
    assert fr.resolve_ticker("NVIDIA Corp") == "NVDA"
    assert fr.resolve_ticker("nvidia") == "NVDA"  # 大小寫不敏感
    assert fr.resolve_ticker("APPLE INC.") == "AAPL"


def test_resolve_ticker_pure_uppercase_short_code():
    """2~5 大寫字母 → 直接當 ticker。"""
    assert fr.resolve_ticker("NVDA") == "NVDA"
    assert fr.resolve_ticker("AAPL") == "AAPL"
    assert fr.resolve_ticker("AMD") == "AMD"


def test_resolve_ticker_none_cases():
    """都不命中 → None。"""
    assert fr.resolve_ticker(None) is None
    assert fr.resolve_ticker("") is None
    assert fr.resolve_ticker("某不知名持倉") is None
    # 太長字母 (>5) 不被當 ticker
    assert fr.resolve_ticker("LONGCOMPANY") is None
    # 小寫不被當 ticker
    assert fr.resolve_ticker("nvda") == "NVDA"   # 經過 .upper() 後命中規則 4


def test_resolve_ticker_tw_takes_priority_over_chinese_name():
    """規則 1 (台股 4 碼) 優先於規則 2 (中文名)。"""
    # 如果同時含 4 碼數字與中文名，4 碼優先
    assert fr.resolve_ticker("台積電 1234") == "1234.TW"


# ════════════════════════════════════════════════════════════
# fetch_stock_three_ratios — mock yfinance
# ════════════════════════════════════════════════════════════
def _make_qf(rev=(1000.0, 800.0), gp=(400.0, 300.0),
             op=(250.0, 180.0), ni=(180.0, 120.0)) -> pd.DataFrame:
    """造一份 yfinance quarterly_income_stmt 風格 DataFrame（兩季）。"""
    return pd.DataFrame(
        {
            pd.Timestamp("2025-09-30"): [rev[0], gp[0], op[0], ni[0]],
            pd.Timestamp("2025-06-30"): [rev[1], gp[1], op[1], ni[1]],
        },
        index=["Total Revenue", "Gross Profit", "Operating Income", "Net Income"],
    )


def test_fetch_three_ratios_happy_path():
    """yfinance 有兩季完整資料 → 算出三率 + diff。"""
    fake_tkr = MagicMock()
    fake_tkr.quarterly_income_stmt = _make_qf()
    with patch("yfinance.Ticker", return_value=fake_tkr):
        out = fr.fetch_stock_three_ratios("NVDA")
    assert out is not None
    assert out["stock"] == "NVDA"
    assert out["ticker"] == "NVDA"
    assert out["q_new"] == "2025-09-30"
    assert out["q_old"] == "2025-06-30"
    # 毛利率 new = 400/1000 = 40.0%；old = 300/800 = 37.5%
    assert out["gross_margin_new"] == 40.0
    assert out["gross_margin_old"] == 37.5
    assert out["gross_margin_diff"] == 2.5
    # 營益率 new = 250/1000 = 25.0%；old = 180/800 = 22.5%
    assert out["op_margin_new"] == 25.0
    assert out["op_margin_old"] == 22.5
    assert out["op_margin_diff"] == 2.5
    # 淨利率 new = 180/1000 = 18.0%；old = 120/800 = 15.0%
    assert out["net_margin_diff"] == 3.0


def test_fetch_three_ratios_unresolvable_ticker():
    """名稱無法解析成 ticker → 直接回 None，不呼叫 yfinance。"""
    with patch("yfinance.Ticker") as mock_yf:
        out = fr.fetch_stock_three_ratios("某不知名公司")
    assert out is None
    assert mock_yf.call_count == 0


def test_fetch_three_ratios_yfinance_empty():
    """yfinance 回空 DataFrame → None。"""
    fake_tkr = MagicMock()
    fake_tkr.quarterly_income_stmt = pd.DataFrame()
    fake_tkr.quarterly_financials  = pd.DataFrame()
    with patch("yfinance.Ticker", return_value=fake_tkr):
        out = fr.fetch_stock_three_ratios("NVDA")
    assert out is None


def test_fetch_three_ratios_only_one_quarter():
    """只有一季財報 → None（不足以算 QoQ）。"""
    qf_one = pd.DataFrame(
        {pd.Timestamp("2025-09-30"): [1000.0, 400.0]},
        index=["Total Revenue", "Gross Profit"],
    )
    fake_tkr = MagicMock()
    fake_tkr.quarterly_income_stmt = qf_one
    with patch("yfinance.Ticker", return_value=fake_tkr):
        out = fr.fetch_stock_three_ratios("NVDA")
    assert out is None


def test_fetch_three_ratios_missing_revenue_row():
    """財報沒 Revenue 列 → None（無分母無法算）。"""
    qf_no_rev = pd.DataFrame(
        {
            pd.Timestamp("2025-09-30"): [400.0, 250.0],
            pd.Timestamp("2025-06-30"): [300.0, 180.0],
        },
        index=["Gross Profit", "Operating Income"],
    )
    fake_tkr = MagicMock()
    fake_tkr.quarterly_income_stmt = qf_no_rev
    with patch("yfinance.Ticker", return_value=fake_tkr):
        out = fr.fetch_stock_three_ratios("NVDA")
    assert out is None


def test_fetch_three_ratios_fallback_to_quarterly_financials():
    """quarterly_income_stmt 空 → fallback 用 quarterly_financials（舊版 yfinance）。"""
    fake_tkr = MagicMock()
    fake_tkr.quarterly_income_stmt = pd.DataFrame()   # 空
    fake_tkr.quarterly_financials  = _make_qf()
    with patch("yfinance.Ticker", return_value=fake_tkr):
        out = fr.fetch_stock_three_ratios("NVDA")
    assert out is not None
    assert out["gross_margin_new"] == 40.0


def test_fetch_three_ratios_yfinance_raises():
    """yfinance 拋例外 → 接住回 None，不破壞 caller。"""
    with patch("yfinance.Ticker", side_effect=ConnectionError("no network")):
        out = fr.fetch_stock_three_ratios("NVDA")
    assert out is None


# ════════════════════════════════════════════════════════════
# services/precision_service.py thin proxy 對齊
# ════════════════════════════════════════════════════════════
def test_precision_service_proxy_delegates_to_repo():
    """PrecisionStrategyEngine.fetch_stock_three_ratios / _resolve_ticker
    應該呼叫到 repo 函式（薄殼）。

    Note: precision_service 用 `from ... import ... as _repo_fetch_...` 綁定，
    patch 要打 precision_service 模組內的 binding 而非 repo 來源。"""
    import services.precision_service as ps_mod
    from services.precision_service import PrecisionStrategyEngine
    pse = PrecisionStrategyEngine()
    with patch.object(ps_mod, "_repo_fetch_stock_three_ratios",
                      return_value={"stock": "DELEGATED"}) as mock_fetch:
        out = pse.fetch_stock_three_ratios("NVDA")
    assert mock_fetch.call_count == 1
    assert out == {"stock": "DELEGATED"}

    with patch.object(ps_mod, "_repo_resolve_ticker",
                      return_value="DELEGATED.TW") as mock_resolve:
        sym = pse._resolve_ticker("NVDA")
    assert mock_resolve.call_count == 1
    assert sym == "DELEGATED.TW"


def test_precision_service_reexports_name_maps():
    """precision_service 為向後相容 re-export _TW/US_NAME_MAP，跟 repo 是同一物件。"""
    import services.precision_service as ps
    assert ps._TW_NAME_MAP is fr._TW_NAME_MAP
    assert ps._US_NAME_MAP is fr._US_NAME_MAP
