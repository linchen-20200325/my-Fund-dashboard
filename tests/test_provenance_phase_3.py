"""tests/test_provenance_phase_3.py — F-PROV-1 phase 18 v19.156 守衛

CLAUDE.md §2.2 — provenance 血緣追蹤對齊。本檔守:
1. macro_repository.fetch_ism_pmi 各 stage 命中 / 失敗都帶 source + fetched_at
2. financial_repository.fetch_stock_three_ratios 成功路徑帶 source + fetched_at
"""
from __future__ import annotations

import pandas as pd


# ════════════════════════════════════════════════════════════════
# fetch_ism_pmi — 各段備援都應帶 provenance
#
# 2026-09-01:原方案 1+2(FRED NAPM / ISPMANPMI,2016-08 起停更)已拔除,
#   實際執行段數 7 → 5。本檔守的**性質不變**(每個 return 都要帶 source +
#   fetched_at),改的只是「哪一段被拿來當樣本」與 fail token 的段數字串。
# ════════════════════════════════════════════════════════════════

class TestIsmPmiProvenance:
    """fetch_ism_pmi 5 段備援 + 1 失敗路徑(共 6 個 return)provenance 守衛。"""

    def test_fail_all_stages_carries_provenance(self, monkeypatch):
        """全 5 段失敗 → err token 也須帶 source + fetched_at(便於 audit 哪輪掛)。"""
        from repositories import macro_repository as mr
        # mock 全部 stage 失敗(fred 空 / 網路 503 / DBnomics 空 docs)
        monkeypatch.setattr("repositories.macro.alternate.fetch_fred", lambda *a, **kw: pd.DataFrame())
        monkeypatch.setattr("repositories.macro.alternate.fetch_url", lambda *a, **kw: None)
        out = mr.fetch_ism_pmi(fred_api_key="x" * 32)
        assert "_err_pmi" in out
        assert out.get("value") is None
        # F-PROV-1 v19.156
        assert "source" in out
        assert out["source"] == "ISM-PMI:all_5_stages_failed"
        assert "fetched_at" in out
        # ISO 8601 含 'T'
        assert "T" in out["fetched_at"]

    def test_fred_stage_success_carries_provenance(self, monkeypatch):
        """FRED 段命中 → source='FRED:...' + fetched_at。

        2026-09-01 更新:原本這條驗的是方案 1+2(FRED NAPM / ISPMANPMI),那兩段
        已拔除。**本檔要守的性質沒有變** —— 「FRED 來源的段命中時要帶 provenance」;
        換的只是樣本段:拔除後仍以 FRED 為來源的是方案 6(Phil Fed 轉 PMI 刻度)
        與方案 7(OECD BCI),兩者都是 `is_proxy=True`。
        故 `is_proxy` 斷言由 False 改為 True —— 這是**現況的真實值**,不是為了換綠燈
        放寬斷言:斷言本身仍是精確的 `is True`,只是指向拔除後真正會命中的那一段。
        """
        import datetime as _dt
        from repositories import macro_repository as mr

        # mock fetch_fred 回最新 5 期月頻 PMI
        _today = _dt.date.today()
        _base = _today.replace(day=1) - _dt.timedelta(days=120)
        _df = pd.DataFrame({
            "date": pd.date_range(_base, periods=5, freq="MS"),
            "value": [52.0, 51.5, 50.8, 49.7, 48.5],
            "source": ["FRED:NAPM"] * 5,
            "fetched_at": ["2026-06-26T00:00:00+00:00"] * 5,
        })
        monkeypatch.setattr("repositories.macro.alternate.fetch_fred", lambda *a, **kw: _df)
        # HTML/JSON 三段(方案 3/4/5)斷線 → 落到仍存活的 FRED 段(方案 6 Phil Fed)
        monkeypatch.setattr("repositories.macro.alternate.fetch_url", lambda *a, **kw: None)
        out = mr.fetch_ism_pmi(fred_api_key="x" * 32, max_age_days=99999)
        assert out.get("value") is not None
        assert out["source"].startswith("FRED:")
        assert "fetched_at" in out
        assert "T" in out["fetched_at"]
        # 拔除方案 1+2 後,唯二仍以 FRED 為來源的段都是代理值,必須誠實標 is_proxy
        assert out["is_proxy"] is True


# ════════════════════════════════════════════════════════════════
# fetch_stock_three_ratios — provenance schema-additive
# ════════════════════════════════════════════════════════════════

class TestThreeRatiosProvenance:
    def test_success_carries_provenance(self, monkeypatch):
        """成功取得三率 → source='yfinance:<ticker>:...' + fetched_at。"""
        from repositories import financial_repository as fr

        # mock yfinance.Ticker 回兩季財報
        class _MockTicker:
            def __init__(self, *_):
                pass

            @property
            def quarterly_income_stmt(self):
                # 2 columns(2 季);3 rows(revenue / gross / op / net)
                return pd.DataFrame(
                    {
                        "2026Q1": [1000.0, 600.0, 300.0, 200.0],
                        "2025Q4": [900.0, 500.0, 250.0, 150.0],
                    },
                    index=["Total Revenue", "Gross Profit",
                           "Operating Income", "Net Income"],
                )

            @property
            def quarterly_financials(self):
                return self.quarterly_income_stmt

        class _MockYf:
            Ticker = _MockTicker

        import sys
        monkeypatch.setitem(sys.modules, "yfinance", _MockYf())
        # resolve_ticker 給定一個已知中文名 → 2330.TW
        out = fr.fetch_stock_three_ratios("台積電")
        assert out is not None
        assert "source" in out
        assert out["source"].startswith("yfinance:2330.TW:")
        assert "fetched_at" in out
        assert "T" in out["fetched_at"]
        # 三率欄位仍存在(schema-additive 守衛)
        assert "gross_margin_diff" in out
        assert "op_margin_diff" in out
        assert "net_margin_diff" in out
