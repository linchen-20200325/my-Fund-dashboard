"""三引擎核心單元測試 — fund_fetcher / ai_engine / precision_engine（v18.98）

策略：純函式優先，副作用以 monkeypatch / 不打網路為原則。
PR #56 標記的「三引擎技債」遲未補；本檔補上 baseline cases，
覆蓋對外承諾的 type / shape / 邊界，未來重構不會悄悄破壞契約。
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest


# ════════════════════════════════════════════════════════════
# §1 precision_engine — 純函式（無 I/O）
# ════════════════════════════════════════════════════════════
from services.precision_service import PrecisionStrategyEngine


@pytest.fixture(scope="module")
def pse() -> PrecisionStrategyEngine:
    return PrecisionStrategyEngine()


@pytest.mark.parametrize("score,expected_level,expected_cash_pct", [
    (2.0,   "極高風險",     50),
    (1.0,   "風險偏高",     30),
    (0.4,   "中性偏高",     15),
    (-0.2,  "中性偏低",     10),
    (-1.0,  "風險極低",     5),
])
def test_risk_score_strategy_thresholds(pse, score, expected_level, expected_cash_pct):
    r = pse.risk_score_strategy(score)
    assert r["level"] == expected_level
    assert r["cash_pct"] == expected_cash_pct
    assert isinstance(r["color"], str) and r["color"].startswith("#")


def test_calculate_composite_risk_insufficient_rows(pse):
    """<20 列 → 0.0 中性值不爆。"""
    df = pd.DataFrame({
        "VIX": [15, 16, 17],
        "HY_Spread": [3.0, 3.1, 3.2],
        "Yield_Curve_10Y_2Y": [0.5, 0.4, 0.3],
    })
    assert pse.calculate_composite_risk(df) == 0.0


def test_calculate_composite_risk_normal(pse):
    """30 列合成資料 → 回 float，最後一列接近平均 → score 接近 0。"""
    rng = np.random.default_rng(seed=42)
    n = 30
    df = pd.DataFrame({
        "VIX": 20 + rng.normal(0, 2, n),
        "HY_Spread": 4.0 + rng.normal(0, 0.3, n),
        "Yield_Curve_10Y_2Y": rng.normal(0, 0.2, n),
    })
    score = pse.calculate_composite_risk(df)
    assert isinstance(score, float)
    assert -3.0 < score < 3.0   # 隨機資料 Z 不會極端


def test_calculate_composite_risk_missing_column(pse):
    """缺欄位 → 0.0（KeyError 內部 swallow）。"""
    df = pd.DataFrame({
        "VIX": list(range(25)),
        # 缺 HY_Spread / Yield_Curve_10Y_2Y
    })
    assert pse.calculate_composite_risk(df) == 0.0


def test_build_macro_df_missing_series(pse):
    """indicators 缺任一序列 → 回 empty DataFrame。"""
    out = pse.build_macro_df({"VIX": {"series": pd.Series([15, 16])}})
    assert isinstance(out, pd.DataFrame) and out.empty


# ════════════════════════════════════════════════════════════
# §2 ai_engine — assign_asset_role 純字串，_gemini 不打網路
# ════════════════════════════════════════════════════════════
from services.ai_service import assign_asset_role, _gemini


def test_assign_asset_role_manual_override_wins():
    """manual_override 優先級高於名稱關鍵字。"""
    # 名稱含「科技」（衛星 KW），但 override = core → 回 core
    assert assign_asset_role("AI 科技基金", manual_override="core") == "core"
    # 名稱含「債」（核心 KW），但 override = satellite → 回 satellite
    assert assign_asset_role("全球債券基金", manual_override="satellite") == "satellite"


@pytest.mark.parametrize("name,expected_role", [
    ("聯博全球高收益債券基金", "core"),       # 含「債」「高息」
    ("摩根多元收益基金", "core"),             # 含「收益」「多元」
    ("富達世界平衡基金", "core"),             # 含「平衡」
    ("Schroder Income Fund", "core"),         # 含 income
    ("元大高息特別股基金", "core"),           # 含「高息」（連續字串）
    ("摩根 AI 科技基金", "satellite"),         # 含「ai」「科技」
    ("富蘭克林印度成長基金", "satellite"),     # 含「印度」「成長」
    ("聯博生技基金", "satellite"),             # 含「生技」
    ("某未知主題基金", "satellite"),           # 含「主題」 → satellite
    ("XYZ 完全沒關鍵字的基金", "satellite"),   # 預設 satellite（保守）
    ("", "satellite"),                         # 空字串 → satellite
])
def test_assign_asset_role_keyword_routing(name, expected_role):
    assert assign_asset_role(name) == expected_role


def test_gemini_empty_api_key_returns_degraded_message():
    """空 api_key → 立即回降級訊息，不打網路。"""
    result = _gemini("", "test prompt")
    assert isinstance(result, str)
    assert "Gemini API Key" in result or "請先填入" in result


def test_gemini_http_error_returns_string(monkeypatch):
    """monkeypatch requests.post 回 503 → 函式不抛例外，回字串。"""
    import services.ai_service as ai_engine

    class _FakeResp:
        status_code = 503
        text = "Service Unavailable"

        def json(self):
            return {}

    def _fake_post(*_args, **_kwargs):
        return _FakeResp()

    monkeypatch.setattr(ai_engine.requests, "post", _fake_post)
    # retry=0 加速測試
    out = _gemini("fake-key", "test prompt", retry=0)
    assert isinstance(out, str)
    assert "503" in out or "❌" in out


# ════════════════════════════════════════════════════════════
# §3 fund_fetcher.calc_metrics — 純計算（無 I/O）
# ════════════════════════════════════════════════════════════
from fund_fetcher import calc_metrics


def test_calc_metrics_empty_series_returns_empty_dict():
    assert calc_metrics(pd.Series(dtype=float), []) == {}


def test_calc_metrics_too_short_returns_empty_dict():
    """<5 筆 → 直接 return {}。"""
    s = pd.Series([100.0, 100.5, 101.0, 100.8])
    assert calc_metrics(s, []) == {}


def test_calc_metrics_basic_shape():
    """300 個交易日 synthetic NAV → 回傳 dict 含關鍵欄位 + 數值合理。"""
    rng = np.random.default_rng(seed=42)
    n = 300
    idx = pd.date_range(end=pd.Timestamp("2026-05-01"), periods=n, freq="B")
    rets = rng.normal(0.0005, 0.012, n)
    nav = 100.0 * (1 + rets).cumprod()
    s = pd.Series(nav, index=idx)

    m = calc_metrics(s, [])
    # 必備欄位（calc_metrics 對外契約）
    for key in ("nav", "std_1y", "high_1y", "low_1y",
                "buy1", "buy2", "buy3", "sell1", "sell2", "sell3",
                "ma20", "ma60", "ret_1m", "ret_3m"):
        assert key in m, f"calc_metrics 缺欄位 {key}"

    assert isinstance(m["nav"], float) and m["nav"] > 0
    # 年化 σ 介於 5% ~ 50%（合理）
    assert 5.0 <= m["std_1y"] <= 50.0
    # buy3 <= buy2 <= buy1 <= nav <= sell1 <= sell2 <= sell3 順序合理
    assert m["buy3"] <= m["buy2"] <= m["buy1"]
    assert m["sell1"] <= m["sell2"] <= m["sell3"]


def test_calc_metrics_with_dividends():
    """配息 4 筆（季配模式）→ div_freq_n=4 + annual_div 為 4×單次配息。"""
    rng = np.random.default_rng(seed=1)
    n = 300
    idx = pd.date_range(end=pd.Timestamp("2026-05-01"), periods=n, freq="B")
    nav = 100.0 * (1 + rng.normal(0.0003, 0.01, n)).cumprod()
    s = pd.Series(nav, index=idx)
    # 4 筆季配（90 天間隔）
    divs = [
        {"date": "2026-04-15", "amount": 1.2},
        {"date": "2026-01-15", "amount": 1.1},
        {"date": "2025-10-15", "amount": 1.0},
        {"date": "2025-07-15", "amount": 1.0},
    ]
    m = calc_metrics(s, divs)
    assert m["annual_div"] > 0
    # 季配 → annual_div ≈ avg(1.2,1.1,1.0,1.0) × 4 = 4.3
    assert 3.5 <= m["annual_div"] <= 5.0
