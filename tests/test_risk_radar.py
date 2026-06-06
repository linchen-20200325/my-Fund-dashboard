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
