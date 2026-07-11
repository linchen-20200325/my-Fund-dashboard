# -*- coding: utf-8 -*-
"""v19.344 — A~E backlog 批次3(c) 行為改善型:基金 MA60 圖表 min_periods。

第八份 review §2.1:新基金 <60 NAV 點時 tab2 `s.rolling(60).mean()` 全 NaN →
dropna 後 trace 空 = MA60 靜默消失、無提示。修:對齊同檔 MA20/布林既有 §1
Fail-Loud 模式,<60 點時明講「資料不足」caption 而非默默省略。

註:金融股判定(股票端)第八份說「用前綴猜」為誤判 — data_loader._is_financial_stock
已是「taiwan_stock_info 產業別欄優先 → 28/58 前綴 fallback」(v19.80 N5 補強),
無須改,故 3(c) 僅基金 MA60 一項。
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestMa60ChartGuard:
    def test_ma60_guarded_by_length_in_tab2(self):
        """tab2 MA60 trace 必須被 len(s) >= 60 閘門守住(不再無條件 rolling+dropna)。"""
        src = (REPO / "ui/tab2_single_fund.py").read_text(encoding="utf-8")
        assert "if len(s) >= 60:" in src
        assert "MA60 均線未繪製" in src, "須有資料不足 caption(§1 Fail-Loud)"

    def test_calc_metrics_ma60_already_none_for_short(self):
        """回歸保護:calc_metrics 的 MA60 對 <60 點本就回 None(既有正確行為)。"""
        import fund_fetcher  # noqa: F401  解 circular
        import pandas as pd
        from services.fund_service import calc_metrics
        idx = pd.date_range(end="2026-07-10", periods=30, freq="B")
        s = pd.Series([10.0 + i * 0.01 for i in range(30)], index=idx, name="nav")
        m = calc_metrics(s, [])
        assert m.get("ma60") is None, "30 點時 MA60 應為 None"
        assert m.get("ma20") is not None, "30 點時 MA20 應可算"

    def test_calc_metrics_ma60_present_for_long(self):
        import fund_fetcher  # noqa: F401
        import pandas as pd
        from services.fund_service import calc_metrics
        idx = pd.date_range(end="2026-07-10", periods=80, freq="B")
        s = pd.Series([10.0 + i * 0.01 for i in range(80)], index=idx, name="nav")
        m = calc_metrics(s, [])
        assert isinstance(m.get("ma60"), float), "80 點時 MA60 應為 float"
