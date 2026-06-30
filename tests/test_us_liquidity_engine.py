"""v19.47 美股流動性 × 熱錢監測 測試套件 — 6 fetcher + snapshot orchestrator."""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd
import pytest

from services import us_liquidity_engine as ule
from shared.colors import TRAFFIC_GREEN, TRAFFIC_RED


def _mk_fred_df(values: list[float], dates: list[str]) -> pd.DataFrame:
    return pd.DataFrame({"date": pd.to_datetime(dates), "value": values})


# ── _hy_oas ──────────────────────────────────────────────────────────────────

def test_hy_oas_normal_range_green():
    df = _mk_fred_df([3.5] * 25, [f"2026-01-{i+1:02d}" for i in range(25)])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._hy_oas("key")
        assert r["value"] == 3.5
        assert r["color"] == TRAFFIC_GREEN  # v19.252 Phase 4A SSOT
        assert "寬鬆" in r["label"]


def test_hy_oas_high_red():
    df = _mk_fred_df([6.0] * 25, [f"2026-01-{i+1:02d}" for i in range(25)])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._hy_oas("key")
        assert r["color"] == TRAFFIC_RED  # v19.252 Phase 4A SSOT
        assert "緊縮" in r["label"]


def test_hy_oas_empty():
    with patch.object(ule, "fetch_fred", return_value=pd.DataFrame()):
        r = ule._hy_oas("key")
        assert "_err" in r


def test_hy_oas_exception_graceful():
    with patch.object(ule, "fetch_fred", side_effect=RuntimeError("boom")):
        r = ule._hy_oas("key")
        assert "_err" in r
        assert "RuntimeError" in r["_err"]


# ── _rrp ─────────────────────────────────────────────────────────────────────

def test_rrp_normal():
    df = _mk_fred_df([500.0] * 25, [f"2026-01-{i+1:02d}" for i in range(25)])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._rrp("key")
        assert r["value"] == 500.0
        assert r["unit"] == "B"
        assert "正常" in r["label"]


def test_rrp_drained_warning():
    df = _mk_fred_df([50.0] * 25, [f"2026-01-{i+1:02d}" for i in range(25)])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._rrp("key")
        assert "枯竭" in r["label"]


def test_rrp_excess():
    df = _mk_fred_df([1500.0] * 25, [f"2026-01-{i+1:02d}" for i in range(25)])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._rrp("key")
        assert "過剩" in r["label"] or "QE" in r["label"]


# ── _m2_yoy ──────────────────────────────────────────────────────────────────

def test_m2_yoy_growth():
    vals = [100.0] * 12 + [108.0]  # iloc[-1]=108, iloc[-13]=100 → +8% YoY
    dates = pd.date_range("2025-01-01", periods=13, freq="MS").strftime("%Y-%m-%d").tolist()
    df = _mk_fred_df(vals, dates)
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._m2_yoy("key")
        assert r["value"] == pytest.approx(8.0, abs=0.01)
        assert "✅" in r["label"]


def test_m2_yoy_insufficient_data():
    df = _mk_fred_df([100.0] * 5, [f"2026-01-{i+1:02d}" for i in range(5)])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._m2_yoy("key")
        assert "_err" in r


def test_m2_yoy_contraction():
    vals = [100.0] * 12 + [98.0]  # iloc[-1]=98, iloc[-13]=100 → -2% YoY
    dates = pd.date_range("2025-01-01", periods=13, freq="MS").strftime("%Y-%m-%d").tolist()
    df = _mk_fred_df(vals, dates)
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._m2_yoy("key")
        assert r["value"] == pytest.approx(-2.0, abs=0.01)
        assert "緊縮" in r["label"] or "🔵" in r["label"]


# ── _walcl ───────────────────────────────────────────────────────────────────

def test_walcl_qe_expansion():
    vals = [7.0e6] + [7.5e6] * 12  # iloc[-13]=7.0e6, iloc[-1]=7.5e6 → +0.5T
    dates = pd.date_range("2026-01-01", periods=13, freq="W").strftime("%Y-%m-%d").tolist()
    df = _mk_fred_df(vals, dates)
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._walcl("key")
        assert r["unit"] == "T"
        assert r["delta"] > 0.1
        assert "QE" in r["label"]


def test_walcl_qt_contraction():
    vals = [8.0e6] + [7.5e6] * 12  # iloc[-13]=8.0e6, iloc[-1]=7.5e6 → -0.5T
    dates = pd.date_range("2026-01-01", periods=13, freq="W").strftime("%Y-%m-%d").tolist()
    df = _mk_fred_df(vals, dates)
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._walcl("key")
        assert r["delta"] < -0.1
        assert "QT" in r["label"]


def test_walcl_empty():
    with patch.object(ule, "fetch_fred", return_value=pd.DataFrame()):
        r = ule._walcl("key")
        assert "_err" in r


# ── _hyg_lqd_ratio ───────────────────────────────────────────────────────────

def test_hyg_lqd_risk_on():
    idx = pd.date_range("2026-01-01", periods=25)
    hyg = pd.Series([80.0] * 22 + [82.0, 82.0, 82.0], index=idx)
    lqd = pd.Series([100.0] * 25, index=idx)
    with patch.object(ule, "fetch_yf_close", side_effect=[hyg, lqd]):
        r = ule._hyg_lqd_ratio()
        assert r["delta_pct"] > 1
        assert "上升" in r["label"] or "✅" in r["label"]


def test_hyg_lqd_risk_off():
    idx = pd.date_range("2026-01-01", periods=25)
    hyg = pd.Series([80.0] * 22 + [78.0, 78.0, 78.0], index=idx)
    lqd = pd.Series([100.0] * 25, index=idx)
    with patch.object(ule, "fetch_yf_close", side_effect=[hyg, lqd]):
        r = ule._hyg_lqd_ratio()
        assert r["delta_pct"] < -1
        assert "撤離" in r["label"] or "🔴" in r["label"]


def test_hyg_lqd_empty():
    with patch.object(ule, "fetch_yf_close", return_value=pd.Series(dtype=float)):
        r = ule._hyg_lqd_ratio()
        assert "_err" in r


# ── AAII sentiment(F-H1 v19.77:L1 fetch_aaii_sentiment + L2 _aaii_with_judgment) ──

class _MockResp:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code = status_code
        self.text = text


def test_aaii_neutral():
    """中性 spread(5%)→ ➖ 情緒中性 label。"""
    html = "<p>Bullish 35.0%</p><p>Bearish 30.0%</p>"
    with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, html)):
        ule.fetch_aaii_sentiment.cache_clear()
        r = ule._aaii_with_judgment()
        assert r["value"] == pytest.approx(5.0, abs=0.1)
        assert r["bull"] == 35.0
        assert r["bear"] == 30.0
        assert "中性" in r["label"]


def test_aaii_extreme_bull_inverse():
    """spread > 20 → 反指標賣訊號。"""
    html = "Bullish 55.0% ... Bearish 25.0%"
    with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, html)):
        ule.fetch_aaii_sentiment.cache_clear()
        r = ule._aaii_with_judgment()
        assert r["value"] > 20
        assert "賣訊號" in r["label"]


def test_aaii_extreme_bear_inverse():
    """spread < -20 → 反指標買訊號。"""
    html = "Bullish 20.0% xxx Bearish 50.0%"
    with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, html)):
        ule.fetch_aaii_sentiment.cache_clear()
        r = ule._aaii_with_judgment()
        assert r["value"] < -20
        assert "買訊號" in r["label"]


def test_aaii_http_error():
    """非 200 → _err 透傳,無 color/label。"""
    with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(500)):
        ule.fetch_aaii_sentiment.cache_clear()
        r = ule._aaii_with_judgment()
        assert "_err" in r
        assert "500" in r["_err"]
        assert "color" not in r


def test_aaii_regex_no_match():
    """頁面格式變更 → _err 含 regex 字樣。"""
    with patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(200, "<html>no data</html>")):
        ule.fetch_aaii_sentiment.cache_clear()
        r = ule._aaii_with_judgment()
        assert "_err" in r
        assert "regex" in r["_err"]


def test_aaii_proxy_failure():
    """fetch_url 回 None(proxy 失敗)→ _err 透傳。"""
    with patch("repositories.macro.alternate.fetch_url", return_value=None):
        ule.fetch_aaii_sentiment.cache_clear()
        r = ule._aaii_with_judgment()
        assert "_err" in r


# ── v19.188 sparkline series 欄(長期座標桶卡片用,與 value 同尺) ────────────────

def test_hy_oas_series_matches_value_unit():
    df = _mk_fred_df([3.5, 3.6, 3.7, 3.8], ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._hy_oas("key")
        assert isinstance(r["series"], list)
        assert all(isinstance(x, float) for x in r["series"])
        # series 尾值 == value(同尺 % level)
        assert r["series"][-1] == pytest.approx(r["value"])


def test_rrp_series_matches_value_unit():
    df = _mk_fred_df([400.0, 450.0, 500.0], ["2026-01-01", "2026-01-02", "2026-01-03"])
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._rrp("key")
        assert r["series"][-1] == pytest.approx(r["value"])  # 同尺 USD bn


def test_m2_yoy_series_is_yoy_not_level():
    vals = [100.0] * 12 + [108.0]
    dates = pd.date_range("2025-01-01", periods=13, freq="MS").strftime("%Y-%m-%d").tolist()
    df = _mk_fred_df(vals, dates)
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._m2_yoy("key")
        # series 應為 YoY %(非 level 100/108),尾值 == value(8.0)
        assert r["series"][-1] == pytest.approx(r["value"], abs=0.01)
        assert r["series"][-1] == pytest.approx(8.0, abs=0.01)


def test_walcl_series_in_trillions():
    vals = [7.0e6] + [7.5e6] * 12
    dates = pd.date_range("2026-01-01", periods=13, freq="W").strftime("%Y-%m-%d").tolist()
    df = _mk_fred_df(vals, dates)
    with patch.object(ule, "fetch_fred", return_value=df):
        r = ule._walcl("key")
        # series 換算兆美元(/1e6),尾值 == value(cur_tn)
        assert r["series"][-1] == pytest.approx(r["value"])
        assert r["series"][-1] == pytest.approx(7.5)


def test_hyg_lqd_series_matches_ratio():
    idx = pd.date_range("2026-01-01", periods=25)
    hyg = pd.Series([80.0] * 22 + [82.0, 82.0, 82.0], index=idx)
    lqd = pd.Series([100.0] * 25, index=idx)
    with patch.object(ule, "fetch_yf_close", side_effect=[hyg, lqd]):
        r = ule._hyg_lqd_ratio()
        assert r["series"][-1] == pytest.approx(r["value"])  # 同尺 ratio


# ── fetch_us_liquidity_snapshot orchestrator ─────────────────────────────────

def test_snapshot_all_keys_present():
    """所有 7 指標都失敗時仍回完整 dict（每個都有 _err）."""
    with patch.object(ule, "fetch_fred", return_value=pd.DataFrame()), \
         patch.object(ule, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
         patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(500)):
        ule.fetch_aaii_sentiment.cache_clear()
        snap = ule.fetch_us_liquidity_snapshot("key")
        # F-PROV-1 phase 19: _provenance 為 schema-additive 後設,僅在有成功子指標時出現;
        # 此測試全失敗 → 不會有 _provenance,7 個指標 key 須齊全（v19.192 加 net_liq）
        indicator_keys = {k for k in snap.keys() if not k.startswith("_")}
        assert indicator_keys == {"hy_oas", "rrp", "m2_yoy", "walcl", "net_liq", "hyg_lqd", "aaii"}
        for k, v in snap.items():
            if k.startswith("_"):
                continue
            assert "_err" in v, f"{k} should have _err"


def test_snapshot_mixed_success_failure():
    """部分成功部分失敗 — partial result preserved."""
    good_df = _mk_fred_df([3.5] * 25, [f"2026-01-{i+1:02d}" for i in range(25)])

    def _fake_fred(sid, key, n=250):
        return good_df if sid == "BAMLH0A0HYM2" else pd.DataFrame()

    with patch.object(ule, "fetch_fred", side_effect=_fake_fred), \
         patch.object(ule, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
         patch("repositories.macro.alternate.fetch_url", return_value=_MockResp(500)):
        ule.fetch_aaii_sentiment.cache_clear()
        snap = ule.fetch_us_liquidity_snapshot("key")
        assert "_err" not in snap["hy_oas"]
        assert "_err" in snap["rrp"]
        assert "_err" in snap["m2_yoy"]
