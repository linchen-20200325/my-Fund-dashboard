"""v19.20 短線風險雷達 — risk_radar.py 單元測試（50+ case）"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from services import risk_radar as rr


# ──────────────────────────────────────────────────────────────
# Helper: 假資料工廠
# ──────────────────────────────────────────────────────────────
def _yf(vals: list[float], base_date: str = "2026-06-01") -> pd.Series:
    n = len(vals)
    return pd.Series(vals, index=pd.date_range(base_date, periods=n, freq="D"),
                     dtype=float)


def _fred(vals: list[float], base_date: str = "2026-06-01") -> pd.DataFrame:
    n = len(vals)
    dates = pd.date_range(base_date, periods=n, freq="D")
    return pd.DataFrame({"date": dates, "value": vals})


# ──────────────────────────────────────────────────────────────
# 常量與工具函式
# ──────────────────────────────────────────────────────────────
class TestConstants:
    def test_palette(self):
        assert rr.GREEN.startswith("#")
        assert rr.YELLOW.startswith("#")
        assert rr.RED.startswith("#")
        assert rr.GRAY.startswith("#")

    def test_color_from(self):
        assert rr._color_from(0) == rr.GREEN
        assert rr._color_from(1) == rr.YELLOW
        assert rr._color_from(2) == rr.RED
        assert rr._color_from(99) == rr.GRAY

    def test_signal_from(self):
        assert "🟢" in rr._signal_from(0)
        assert "🟡" in rr._signal_from(1)
        assert "🔴" in rr._signal_from(2)
        assert "⬜" in rr._signal_from(99)

    def test_empty_shape(self):
        d = rr._empty()
        assert set(d.keys()) == {"signal", "color", "value", "prev",
                                 "note", "label", "trend"}
        assert "⬜" in d["signal"]
        assert d["value"] is None


# ──────────────────────────────────────────────────────────────
# 1. VIX level
# ──────────────────────────────────────────────────────────────
class TestVixLevel:
    def test_calm(self):
        with patch.object(rr, "fetch_yf_close", return_value=_yf([14.0] * 8)):
            d = rr._signal_vix_level()
        assert "🟢" in d["signal"]

    def test_yellow_at_25(self):
        # prev=24 → cur=25.5：+6.25% 不觸 spike 規則，僅靠絕對值 ≥25 → 🟡
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([20.0] * 6 + [24.0, 25.5])):
            d = rr._signal_vix_level()
        assert "🟡" in d["signal"]

    def test_red_above_30(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([22.0] * 7 + [32.0])):
            d = rr._signal_vix_level()
        assert "🔴" in d["signal"]

    def test_red_via_20pct_spike(self):
        # 18 → 22.5 = +25%
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([18.0] * 7 + [22.5])):
            d = rr._signal_vix_level()
        assert "🔴" in d["signal"]

    def test_empty_safe(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=pd.Series(dtype=float)):
            d = rr._signal_vix_level()
        assert "⬜" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 2. VIX term structure
# ──────────────────────────────────────────────────────────────
class TestVixTermStruct:
    def test_normal_contango(self):
        with patch.object(rr, "fetch_yf_close",
                          side_effect=[_yf([15.0] * 8), _yf([18.0] * 8)]):
            d = rr._signal_vix_term_struct()
        assert "🟢" in d["signal"]

    def test_yellow_inversion(self):
        with patch.object(rr, "fetch_yf_close",
                          side_effect=[_yf([20.0] * 8), _yf([19.5] * 8)]):
            d = rr._signal_vix_term_struct()
        assert "🟡" in d["signal"]

    def test_red_extreme_inversion(self):
        with patch.object(rr, "fetch_yf_close",
                          side_effect=[_yf([25.0] * 8), _yf([22.0] * 8)]):
            d = rr._signal_vix_term_struct()
        assert "🔴" in d["signal"]

    def test_one_empty_safe(self):
        with patch.object(rr, "fetch_yf_close",
                          side_effect=[pd.Series(dtype=float), _yf([18.0] * 8)]):
            d = rr._signal_vix_term_struct()
        assert "⬜" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 3. HY OAS Δ
# ──────────────────────────────────────────────────────────────
class TestHyOasDelta:
    def test_calm(self):
        # 3.50 → 3.55 = +5bp
        with patch.object(rr, "fetch_fred", return_value=_fred([3.50, 3.55])):
            d = rr._signal_hy_oas_delta("KEY")
        assert "🟢" in d["signal"]

    def test_yellow_20bp(self):
        with patch.object(rr, "fetch_fred", return_value=_fred([3.50, 3.72])):
            d = rr._signal_hy_oas_delta("KEY")
        assert "🟡" in d["signal"]

    def test_red_30bp(self):
        with patch.object(rr, "fetch_fred", return_value=_fred([3.50, 3.82])):
            d = rr._signal_hy_oas_delta("KEY")
        assert "🔴" in d["signal"]

    def test_empty_safe(self):
        with patch.object(rr, "fetch_fred", return_value=pd.DataFrame()):
            d = rr._signal_hy_oas_delta("KEY")
        assert "⬜" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 4. 10Y yield shock
# ──────────────────────────────────────────────────────────────
class TestYield10yShock:
    def test_calm(self):
        with patch.object(rr, "fetch_fred", return_value=_fred([4.50, 4.52])):
            d = rr._signal_yield_10y_shock("KEY")
        assert "🟢" in d["signal"]

    def test_yellow_7bp(self):
        with patch.object(rr, "fetch_fred", return_value=_fred([4.50, 4.58])):
            d = rr._signal_yield_10y_shock("KEY")
        assert "🟡" in d["signal"]

    def test_red_10bp_plus(self):
        with patch.object(rr, "fetch_fred", return_value=_fred([4.40, 4.54])):
            d = rr._signal_yield_10y_shock("KEY")
        assert "🔴" in d["signal"]

    # F-RECON-1 phase 2 v19.87 — 雙源對帳 FRED DGS10 vs Yahoo ^TNX
    def test_reconcile_agree(self):
        with patch.object(rr, "fetch_fred", return_value=_fred([4.50, 4.52])), \
             patch.object(rr, "fetch_yf_close", return_value=_yf([45.3])):
            d = rr._signal_yield_10y_shock("KEY")
        assert "reconcile" in d
        assert d["reconcile"]["status"] == "agree"
        assert d["reconcile"]["agree"] is True

    def test_reconcile_disagree(self):
        with patch.object(rr, "fetch_fred", return_value=_fred([4.50, 4.52])), \
             patch.object(rr, "fetch_yf_close", return_value=_yf([50.0])):
            d = rr._signal_yield_10y_shock("KEY")
        assert d["reconcile"]["status"] == "disagree"
        assert d["reconcile"]["agree"] is False

    def test_reconcile_tnx_missing(self):
        import pandas as _pd
        with patch.object(rr, "fetch_fred", return_value=_fred([4.50, 4.52])), \
             patch.object(rr, "fetch_yf_close", return_value=_pd.Series(dtype=float)):
            d = rr._signal_yield_10y_shock("KEY")
        assert d["reconcile"]["status"] == "b_missing"


# ──────────────────────────────────────────────────────────────
# 5. MOVE level
# ──────────────────────────────────────────────────────────────
class TestMoveLevel:
    def test_calm(self):
        with patch.object(rr, "fetch_yf_close", return_value=_yf([85.0] * 8)):
            d = rr._signal_move_level()
        assert "🟢" in d["signal"]

    def test_yellow_110(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([95.0] * 7 + [115.0])):
            d = rr._signal_move_level()
        assert "🟡" in d["signal"]

    def test_red_130(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([105.0] * 7 + [135.0])):
            d = rr._signal_move_level()
        assert "🔴" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 6. SPX trend break
# ──────────────────────────────────────────────────────────────
class TestSpxTrendBreak:
    def test_above_both_dma(self):
        # 200 個 4000 → cur 4200 > sma50(4000) > sma200(4000)
        vals = [4000.0] * 200 + [4200.0]
        with patch.object(rr, "fetch_yf_close", return_value=_yf(vals)):
            d = rr._signal_spx_trend_break()
        assert "🟢" in d["signal"]

    def test_break_50dma_only(self):
        # 200 個 4000 + 49 個 4200 + 1 個 4050
        # last 50: 49 * 4200 + 4050; last 200: 包含 4000s + 4200s + 4050
        # cur=4050, sma50 ≈ 4197, sma200 ≈ 比 cur 高也可能比 cur 低
        # 簡化：用 100×4000 + 100×4200 + cur=4150
        # last 50: 50×4200=4200 sma50; last 200: 50×4000+150×4200... 太麻煩
        # 改用：階梯式 — 199 個 4100, 1 個 cur=4090
        # last 50 = 199 截尾49個4100 + 4090 → mean ≈ 4099.8
        # last 200 = 199個4100+ 4090 → mean ≈ 4099.95
        # cur=4090 < sma50 也 < sma200 → 🔴
        # 試另策略：sma50 > sma200，cur 介於兩者
        vals = [3900.0] * 150 + [4200.0] * 50 + [4100.0]
        # last 50 = 49×4200 + 4100 = 210000-100 = 209900/50 = 4198
        # last 200 = 50×3900 + 49×4200 + 4100 = 195000+205800+4100=404900/199... wait
        # 取 tail(200) of len 201 series = indices 1..200 = 149×3900+50×4200+1×4100
        # = 581100+210000+4100=795200/200=3976
        # cur=4100, sma50=4198, sma200=3976 → cur < sma50 but > sma200 → 🟡
        with patch.object(rr, "fetch_yf_close", return_value=_yf(vals)):
            d = rr._signal_spx_trend_break()
        assert "🟡" in d["signal"]

    def test_break_200dma_red(self):
        # cur 跌破 200DMA
        vals = [4200.0] * 200 + [3900.0]
        with patch.object(rr, "fetch_yf_close", return_value=_yf(vals)):
            d = rr._signal_spx_trend_break()
        assert "🔴" in d["signal"]

    def test_insufficient_data(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([4000.0] * 100)):
            d = rr._signal_spx_trend_break()
        assert "⬜" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 7. SOX drop
# ──────────────────────────────────────────────────────────────
class TestSoxDrop:
    def test_calm(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([5500.0] * 7 + [5510.0])):
            d = rr._signal_sox_drop()
        assert "🟢" in d["signal"]

    def test_yellow_2pct(self):
        # 5500 → 5390 = -2%
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([5500.0] * 7 + [5390.0])):
            d = rr._signal_sox_drop()
        assert "🟡" in d["signal"]

    def test_red_3pct(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([5500.0] * 7 + [5280.0])):
            d = rr._signal_sox_drop()
        assert "🔴" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 8. Sector rotation
# ──────────────────────────────────────────────────────────────
class TestSectorRotation:
    def test_calm(self):
        def _mock(t, **kw):
            return _yf([100.0] * 30)
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            d = rr._signal_sector_rotation()
        assert "🟢" in d["signal"]

    def test_yellow_defensive_outperform_2pp(self):
        defensive = {"XLP", "XLU", "XLV"}

        def _mock(t, **kw):
            if t in defensive:
                # 30 樣本，22 天前 = idx[-22] = 100，cur = 102 → +2%
                return _yf([100.0] * 22 + [101.0] * 7 + [102.0])
            return _yf([100.0] * 30)  # offensive 0%
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            d = rr._signal_sector_rotation()
        assert "🟡" in d["signal"]

    def test_red_defensive_outperform_4pp(self):
        defensive = {"XLP", "XLU", "XLV"}

        def _mock(t, **kw):
            if t in defensive:
                return _yf([100.0] * 22 + [102.0] * 7 + [104.5])
            return _yf([100.0] * 22 + [99.5] * 7 + [99.0])
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            d = rr._signal_sector_rotation()
        assert "🔴" in d["signal"]

    def test_all_missing_safe(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=pd.Series(dtype=float)):
            d = rr._signal_sector_rotation()
        assert "⬜" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 9. Put/Call ratio
# ──────────────────────────────────────────────────────────────
class TestPutCallRatio:
    def test_calm(self):
        with patch.object(rr, "fetch_yf_close", return_value=_yf([0.7] * 8)):
            d = rr._signal_put_call_ratio()
        assert "🟢" in d["signal"]

    def test_yellow_1_0(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([0.85] * 7 + [1.05])):
            d = rr._signal_put_call_ratio()
        assert "🟡" in d["signal"]

    def test_red_extreme(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=_yf([0.9] * 7 + [1.25])):
            d = rr._signal_put_call_ratio()
        assert "🔴" in d["signal"]


# ──────────────────────────────────────────────────────────────
# 9b. v19.30 多源 fallback chain（VIX3M + Put/Call CBOE CSV 救援，
#     鏡像 stock v18.181 PR #185）
# ──────────────────────────────────────────────────────────────
class TestCboeCsvHelper:
    def _mk_resp(self, text: str, status: int = 200):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = status
        r.text = text
        return r

    def test_parses_cboe_csv(self):
        csv = "DATE,OPEN,HIGH,LOW,CLOSE\n2026-01-02,15.0,16.0,14.5,15.5\n2026-01-03,15.5,16.5,15.0,16.0\n"
        with patch("infra.proxy.fetch_url", return_value=self._mk_resp(csv)):
            s = rr._fetch_cboe_csv("VIX3M")
        assert len(s) == 2
        assert abs(float(s.iloc[-1]) - 16.0) < 1e-6

    def test_http_failure_returns_empty(self):
        with patch("infra.proxy.fetch_url", return_value=None):
            s = rr._fetch_cboe_csv("CPC")
        assert s.empty

    def test_status_500_returns_empty(self):
        with patch("infra.proxy.fetch_url",
                   return_value=self._mk_resp("Server Error", status=500)):
            s = rr._fetch_cboe_csv("CPC")
        assert s.empty

    def test_missing_close_column_returns_empty(self):
        with patch("infra.proxy.fetch_url",
                   return_value=self._mk_resp("DATE,OPEN\n2026-01-02,15.0\n")):
            s = rr._fetch_cboe_csv("VIX3M")
        assert s.empty


class TestResolveVix3m:
    def test_yahoo_primary_wins(self):
        with patch.object(rr, "fetch_yf_close", return_value=_yf([15.0] * 8)):
            s, src, trace = rr._resolve_vix3m()
        assert "Yahoo ^VIX3M" in src
        assert not s.empty
        assert trace == []

    def test_falls_through_to_vxv(self):
        def _mock(t, **kw):
            if t == "^VIX3M":
                return pd.Series(dtype=float)
            return _yf([16.0] * 8)
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            s, src, trace = rr._resolve_vix3m()
        assert "Yahoo ^VXV" in src
        assert any("^VIX3M" in t for t in trace)

    def test_falls_through_to_cboe(self):
        from unittest.mock import MagicMock
        csv = "DATE,CLOSE\n2026-01-02,15.0\n2026-01-03,16.0\n"
        cboe_resp = MagicMock()
        cboe_resp.status_code = 200
        cboe_resp.text = csv
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=cboe_resp):
            s, src, _ = rr._resolve_vix3m()
        assert "CBOE VIX3M_History.csv" in src
        assert not s.empty

    def test_all_sources_fail_returns_empty(self):
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=None):
            s, src, trace = rr._resolve_vix3m()
        assert s.empty
        assert src == ""
        # v19.43：應收集 4 層失敗（2 Yahoo + 1 CBOE + 2 stooq = 5 條）
        assert len(trace) >= 4


class TestResolvePutCall:
    def test_yahoo_cpc_primary_wins(self):
        with patch.object(rr, "fetch_yf_close", return_value=_yf([0.8] * 8)):
            s, src, trace = rr._resolve_put_call()
        assert "Yahoo ^CPC" in src
        assert not s.empty
        assert trace == []

    def test_falls_through_to_cpce(self):
        def _mock(t, **kw):
            if t == "^CPC":
                return pd.Series(dtype=float)
            return _yf([0.9] * 8)
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            s, src, trace = rr._resolve_put_call()
        assert "Yahoo ^CPCE" in src
        assert any("^CPC" in t for t in trace)

    def test_falls_through_to_cboe_csv(self):
        from unittest.mock import MagicMock
        csv = "DATE,CLOSE\n2026-01-02,0.85\n2026-01-03,0.90\n"
        cboe_resp = MagicMock()
        cboe_resp.status_code = 200
        cboe_resp.text = csv
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=cboe_resp):
            s, src, _ = rr._resolve_put_call()
        assert "CBOE CPC_History.csv" in src
        assert not s.empty

    def test_all_sources_fail(self):
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=None):
            s, src, trace = rr._resolve_put_call()
        assert s.empty
        assert src == ""
        assert len(trace) >= 4


class TestFailTraceSurfacedInNote:
    """v19.43：全源失敗時 note 應包含逐層失敗痕跡，user 可從 UI 直接看根因。"""

    def test_vix_term_struct_note_contains_trace(self):
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=None):
            d = rr._signal_vix_term_struct()
        assert "⬜" in d["signal"]
        assert "全源失敗" in d["note"]
        assert ("Yahoo" in d["note"] or "CBOE" in d["note"]
                or "stooq" in d["note"])

    def test_put_call_note_contains_trace(self):
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=None):
            d = rr._signal_put_call_ratio()
        assert "⬜" in d["signal"]
        assert "全源失敗" in d["note"]
        assert ("Yahoo" in d["note"] or "CBOE" in d["note"]
                or "stooq" in d["note"])


class TestVixTermStructCboeFallback:
    def test_uses_cboe_label_when_yahoo_dead(self):
        """v19.30 VIX3M Yahoo 全失敗 → CBOE CSV 救援 + label 反映實際源。"""
        from unittest.mock import MagicMock
        csv = "DATE,CLOSE\n2026-01-02,16.0\n2026-01-03,17.0\n"
        cboe_resp = MagicMock()
        cboe_resp.status_code = 200
        cboe_resp.text = csv

        def _yf_mock(t, **kw):
            if t == "^VIX":
                return pd.Series([15.0, 16.0],
                                 index=pd.to_datetime(["2026-01-02", "2026-01-03"]))
            return pd.Series(dtype=float)  # ^VIX3M / ^VXV 都空
        with patch.object(rr, "fetch_yf_close", side_effect=_yf_mock), \
             patch("infra.proxy.fetch_url", return_value=cboe_resp):
            d = rr._signal_vix_term_struct()
        assert "CBOE VIX3M_History.csv" in d["label"]
        assert "🟢" in d["signal"]


class TestPutCallCboeFallback:
    def test_uses_cboe_label_when_yahoo_dead(self):
        """v19.30 ^CPC/^CPCE Yahoo 全失敗 → CBOE CSV 救援。"""
        from unittest.mock import MagicMock
        csv = "DATE,CLOSE\n2026-01-02,0.85\n2026-01-03,1.25\n"
        cboe_resp = MagicMock()
        cboe_resp.status_code = 200
        cboe_resp.text = csv
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=cboe_resp):
            d = rr._signal_put_call_ratio()
        assert "CBOE CPC_History.csv" in d["label"]
        assert "🔴" in d["signal"]


# ──────────────────────────────────────────────────────────────
# v19.65 P0：FRED VXVCLS + CBOE JSON 第 6/7 層備援
# ──────────────────────────────────────────────────────────────
class TestFredVxvclsFallback:
    """v19.65 P0：所有前 5 層失敗後，FRED VXVCLS 作 VIX3M 最終救援。"""

    def test_fred_vxvcls_rescues_when_all_others_fail(self):
        """Yahoo + CBOE + stooq 全空 → _resolve_vix3m 走 FRED VXVCLS。"""
        vxvcls_df = _fred([16.0, 17.0, 16.5, 17.2, 16.8, 17.5, 16.9, 17.1])
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=None), \
             patch.object(rr, "fetch_fred", return_value=vxvcls_df):
            s, src, trace = rr._resolve_vix3m(fred_api_key="test_key")
        assert "FRED VXVCLS" in src
        assert not s.empty
        assert len(s) >= 2

    def test_fred_vxvcls_skipped_when_no_api_key(self):
        """fred_api_key=None 時不嘗試 FRED（不應加 FRED 失敗到 trace）。"""
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=None):
            s, src, trace = rr._resolve_vix3m(fred_api_key=None)
        assert s.empty
        assert src == ""
        assert not any("FRED" in t for t in trace)

    def test_fred_vxvcls_empty_falls_through(self):
        """FRED 也回空 → 最終仍回空 series，trace 包含 FRED 失敗訊息。"""
        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", return_value=None), \
             patch.object(rr, "fetch_fred", return_value=pd.DataFrame()):
            s, src, trace = rr._resolve_vix3m(fred_api_key="test_key")
        assert s.empty
        assert src == ""
        assert any("FRED VXVCLS" in t for t in trace)

    def test_signal_vix_term_struct_passes_api_key(self):
        """_signal_vix_term_struct(fred_api_key=...) 正確傳遞 key 到 _resolve_vix3m。"""
        vxvcls_df = _fred([16.0, 17.0, 16.5, 17.2, 16.8, 17.5, 16.9, 17.1])
        vix_s = _yf([15.0, 14.5, 15.2, 14.8, 15.5, 14.9, 15.3, 15.1])

        def _yf_mock(t, **kw):
            if t == "^VIX":
                return vix_s
            return pd.Series(dtype=float)  # ^VIX3M / ^VXV 都空

        with patch.object(rr, "fetch_yf_close", side_effect=_yf_mock), \
             patch("infra.proxy.fetch_url", return_value=None), \
             patch.object(rr, "fetch_fred", return_value=vxvcls_df):
            d = rr._signal_vix_term_struct(fred_api_key="test_key")
        assert "⬜" not in d["signal"]  # 不是無資料
        assert "FRED VXVCLS" in d["label"]


class TestCboeJsonFallback:
    """v19.65 P0：CBOE JSON API 作 Put/Call 第 7 層備援。"""

    def _mk_resp(self, text: str, status: int = 200):
        from unittest.mock import MagicMock
        r = MagicMock()
        r.status_code = status
        r.text = text
        return r

    def test_parses_cboe_json(self):
        import json
        payload = json.dumps({"data": [
            {"date": "2026-01-02", "close": 0.85},
            {"date": "2026-01-03", "close": 0.90},
        ]})
        with patch("infra.proxy.fetch_url", return_value=self._mk_resp(payload)):
            s = rr._fetch_cboe_json("^CPC")
        assert len(s) == 2
        assert abs(float(s.iloc[-1]) - 0.90) < 1e-6

    def test_http_failure_returns_empty(self):
        with patch("infra.proxy.fetch_url", return_value=None):
            s = rr._fetch_cboe_json("^CPC")
        assert s.empty

    def test_empty_data_array_returns_empty(self):
        import json
        payload = json.dumps({"data": []})
        with patch("infra.proxy.fetch_url", return_value=self._mk_resp(payload)):
            s = rr._fetch_cboe_json("^CPC")
        assert s.empty

    def test_json_fallback_rescues_put_call(self):
        """Yahoo + CBOE CSV + stooq 全失敗 → _resolve_put_call 走 CBOE JSON。"""
        import json
        payload = json.dumps({"data": [
            {"date": "2026-01-02", "close": 0.85},
            {"date": "2026-01-03", "close": 0.88},
            {"date": "2026-01-04", "close": 0.90},
        ]})

        call_count = [0]

        def _fetch_url_side_effect(url, **kw):
            # CSV endpoints → None；JSON endpoint → 回 payload
            call_count[0] += 1
            if ".json" in url:
                return self._mk_resp(payload)
            return None  # CSV 全失敗

        with patch.object(rr, "fetch_yf_close", return_value=pd.Series(dtype=float)), \
             patch("infra.proxy.fetch_url", side_effect=_fetch_url_side_effect):
            s, src, trace = rr._resolve_put_call()
        assert "CBOE JSON" in src
        assert not s.empty


# ──────────────────────────────────────────────────────────────
# 10. Asia overnight
# ──────────────────────────────────────────────────────────────
class TestAsiaOvernight:
    def test_calm(self):
        def _mock(t, **kw):
            return _yf([100.0] * 20 + [100.5])
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            d = rr._signal_asia_overnight()
        assert "🟢" in d["signal"]

    def test_yellow_minus_1_5(self):
        def _mock(t, **kw):
            return _yf([100.0] * 20 + [98.3])  # -1.7%
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            d = rr._signal_asia_overnight()
        assert "🟡" in d["signal"]

    def test_red_minus_2_5(self):
        def _mock(t, **kw):
            return _yf([100.0] * 20 + [97.0])  # -3%
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            d = rr._signal_asia_overnight()
        assert "🔴" in d["signal"]

    def test_one_missing_ok(self):
        def _mock(t, **kw):
            if t == "^N225":
                return _yf([100.0] * 20 + [97.0])
            return pd.Series(dtype=float)
        with patch.object(rr, "fetch_yf_close", side_effect=_mock):
            d = rr._signal_asia_overnight()
        assert "🔴" in d["signal"]


# ──────────────────────────────────────────────────────────────
# Integration: detect_risk_radar
# ──────────────────────────────────────────────────────────────
class TestDetectRiskRadar:
    EXPECTED_KEYS = {
        "vix_level", "vix_term_struct", "hy_oas_delta", "yield_10y_shock",
        "move_level", "spx_trend_break", "sox_drop", "sector_rotation",
        "put_call_ratio", "asia_overnight",
    }
    EXPECTED_FIELDS = {"signal", "color", "value", "prev", "note", "label", "trend"}

    def test_all_keys_present(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=pd.Series(dtype=float)), \
             patch.object(rr, "fetch_fred", return_value=pd.DataFrame()):
            radar = rr.detect_risk_radar("KEY")
        assert set(radar.keys()) == self.EXPECTED_KEYS

    def test_each_value_shape(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=pd.Series(dtype=float)), \
             patch.object(rr, "fetch_fred", return_value=pd.DataFrame()):
            radar = rr.detect_risk_radar("KEY")
        for v in radar.values():
            assert set(v.keys()) == self.EXPECTED_FIELDS

    def test_all_empty_safe_degrade(self):
        with patch.object(rr, "fetch_yf_close",
                          return_value=pd.Series(dtype=float)), \
             patch.object(rr, "fetch_fred", return_value=pd.DataFrame()):
            radar = rr.detect_risk_radar("")
        for v in radar.values():
            assert "⬜" in v["signal"]
            assert v["value"] is None

    def test_radar_keys_constant(self):
        assert set(rr._RADAR_KEYS) == self.EXPECTED_KEYS

    def test_single_failure_does_not_break_others(self):
        # FRED 全空但 yfinance 正常 → FRED 兩燈⬜，yfinance 八燈非⬜
        def _yf_mock(t, **kw):
            if t == "^GSPC":
                return _yf([4000.0] * 200 + [4200.0])
            return _yf([100.0] * 30)
        with patch.object(rr, "fetch_yf_close", side_effect=_yf_mock), \
             patch.object(rr, "fetch_fred", return_value=pd.DataFrame()):
            radar = rr.detect_risk_radar("KEY")
        assert "⬜" in radar["hy_oas_delta"]["signal"]
        assert "⬜" in radar["yield_10y_shock"]["signal"]
        assert "🟢" in radar["spx_trend_break"]["signal"]


# ──────────────────────────────────────────────────────────────
# summarize_radar
# ──────────────────────────────────────────────────────────────
class TestSummarizeRadar:
    def test_calm_all_green(self):
        radar = {f"k{i}": {"signal": "🟢 平靜"} for i in range(10)}
        s = rr.summarize_radar(radar)
        assert s["level"] == "平靜"
        assert s["green"] == 10
        assert s["color"] == rr.GREEN

    def test_warning_4_yellow(self):
        radar = {
            **{f"y{i}": {"signal": "🟡 警戒"} for i in range(4)},
            **{f"g{i}": {"signal": "🟢 平靜"} for i in range(6)},
        }
        s = rr.summarize_radar(radar)
        assert s["level"] == "警戒"
        assert s["yellow"] == 4
        assert s["color"] == rr.YELLOW

    def test_alert_2_red(self):
        radar = {
            "r1": {"signal": "🔴 警報"}, "r2": {"signal": "🔴 警報"},
            "g1": {"signal": "🟢 平靜"}, "g2": {"signal": "🟢 平靜"},
        }
        s = rr.summarize_radar(radar)
        assert s["level"] == "警報"
        assert s["red"] == 2

    def test_extreme_4_red(self):
        radar = {f"r{i}": {"signal": "🔴 警報"} for i in range(5)}
        s = rr.summarize_radar(radar)
        assert s["level"] == "極端警報"
        assert s["red"] == 5

    def test_gray_counted(self):
        radar = {
            "a": {"signal": "⬜ 無資料"},
            "b": {"signal": "⬜ 無資料"},
            "c": {"signal": "🟢 平靜"},
        }
        s = rr.summarize_radar(radar)
        assert s["gray"] == 2
        assert s["green"] == 1

    def test_empty_radar(self):
        s = rr.summarize_radar({})
        assert s["level"] == "平靜"
        assert s["red"] == 0 and s["yellow"] == 0 and s["green"] == 0

    def test_non_dict_value_safe(self):
        # 防呆：傳入畸形資料不爆
        radar = {"weird": None, "ok": {"signal": "🟢 平靜"}}
        s = rr.summarize_radar(radar)
        assert s["green"] == 1
        assert s["gray"] == 1


# ════════════════════════════════════════════════════════════════════
# v19.21 雙速合議 — synthesize_dual_verdict
# ════════════════════════════════════════════════════════════════════
class TestSynthesizeDualVerdict:
    """雙速合議規則 — 慢總經 verdict × 短線雷達 level → 單一行動建議。"""

    SLOW_BULL = ("極度樂觀", 10.5, "#00c853", "🟢", "多頭市場強勁：可滿倉持有")
    SLOW_OK = ("樂觀", 6.0, "#69f0ae", "🟢", "景氣穩定擴張：核心持有不動")
    SLOW_NEU = ("中性", 0.0, "#ffd54f", "🟡", "市場震盪整理：分批進場")
    SLOW_BEAR = ("悲觀", -7.0, "#ff8a80", "🔴", "風險正在集結")
    SLOW_VERY_BEAR = ("極度悲觀", -12.0, "#f44336", "🔴", "避險情緒高漲")

    def test_radar_none_adopts_slow(self):
        s = rr.synthesize_dual_verdict(*self.SLOW_BULL, None)
        assert s["mode"] == "adopt_slow"
        assert s["level"] == "極度樂觀"  # 無 suffix
        assert s["icon"] == "🟢"
        assert s["color"] == "#00c853"
        assert s["action"] == "多頭市場強勁：可滿倉持有"

    def test_radar_calm_adopts_slow_with_suffix(self):
        s = rr.synthesize_dual_verdict(*self.SLOW_BULL, "平靜")
        assert s["mode"] == "adopt_slow"
        assert "平靜確認" in s["level"]
        assert s["icon"] == "🟢"
        assert s["action"] == "多頭市場強勁：可滿倉持有"

    def test_radar_warning_with_bull_slow_observes(self):
        s = rr.synthesize_dual_verdict(*self.SLOW_BULL, "警戒")
        assert s["mode"] == "downgrade_1"
        assert "警戒觀察" in s["level"]
        assert "暫緩單筆加碼" in s["action"]
        assert s["color"] == "#fbc02d"

    def test_radar_warning_with_neutral_slow_goes_neutral(self):
        s = rr.synthesize_dual_verdict(*self.SLOW_NEU, "警戒")
        assert s["mode"] == "downgrade_1"
        assert s["level"] == "中性觀察"
        assert "定期定額減半" in s["action"]
        assert s["icon"] == "🟡"

    def test_radar_alert_with_bull_slow_diverges(self):
        # 6/5/2026 真實情境：慢總經樂觀 +10.5 + 雷達警報 → 降槓桿
        s = rr.synthesize_dual_verdict(*self.SLOW_BULL, "警報")
        assert s["mode"] == "downgrade_2"
        assert "雙速分歧" in s["level"]
        assert "降槓桿" in s["level"]
        assert "50-60%" in s["action"]
        assert s["icon"] == "🟠"
        assert s["color"] == "#ef6c00"

    def test_radar_alert_with_neutral_slow_goes_short(self):
        s = rr.synthesize_dual_verdict(*self.SLOW_NEU, "警報")
        assert s["mode"] == "downgrade_2"
        assert "偏空" in s["level"]
        assert "25-30%" in s["action"]

    def test_radar_alert_with_bear_slow_full_defense(self):
        s = rr.synthesize_dual_verdict(*self.SLOW_BEAR, "警報")
        assert s["mode"] == "downgrade_2"
        assert s["level"] == "全面防守"
        assert "35%+" in s["action"]
        assert s["color"] == "#b71c1c"

    def test_radar_extreme_overrides_any_slow(self):
        # 即使慢總經極度樂觀，雷達極端警報直接覆蓋
        s = rr.synthesize_dual_verdict(*self.SLOW_BULL, "極端警報")
        assert s["mode"] == "override_defense"
        assert s["level"] == "立即減倉防守"
        assert "暫不採信" in s["action"]
        assert s["icon"] == "🔴"
        assert s["color"] == "#d32f2f"

    def test_radar_extreme_with_already_bear_still_overrides(self):
        s = rr.synthesize_dual_verdict(*self.SLOW_VERY_BEAR, "極端警報")
        assert s["mode"] == "override_defense"
        assert s["level"] == "立即減倉防守"

    def test_unknown_radar_level_falls_back_to_slow(self):
        # 防呆：未知 level 不爆，靜默 fallback
        s = rr.synthesize_dual_verdict(*self.SLOW_OK, "外星訊號")
        assert s["mode"] == "adopt_slow"
        assert s["level"] == "樂觀"
        assert s["icon"] == "🟢"
