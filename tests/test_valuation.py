"""v19.22 Tier A — valuation.py 單元測試。"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from services import valuation as vl


class TestConstants:
    def test_palette_is_hex(self):
        for c in (vl.GREEN, vl.YELLOW, vl.ORANGE, vl.RED, vl.GRAY):
            assert c.startswith("#")

    def test_reference_means_positive(self):
        assert vl.FORWARD_PE_MEAN > 0
        assert vl.FORWARD_PE_STD > 0
        assert vl.GDP_TREND > 0
        assert vl.GDP_TREND_STD > 0


class TestForwardPeVerdict:
    def test_cheap_below_minus_1_sigma(self):
        out = vl.compute_forward_pe_verdict(12.0)
        assert "🟢" in out["signal"]
        assert out["sigma"] <= -1
        assert out["source_ok"] is True

    def test_neutral_within_pm_1_sigma(self):
        out = vl.compute_forward_pe_verdict(16.5)
        assert "🟡" in out["signal"]
        assert abs(out["sigma"]) <= 1

    def test_expensive_plus_1_to_2_sigma(self):
        out = vl.compute_forward_pe_verdict(21.0)
        assert "🟠" in out["signal"]
        assert 1 < out["sigma"] <= 2

    def test_bubble_above_plus_2_sigma(self):
        out = vl.compute_forward_pe_verdict(25.0)
        assert "🔴" in out["signal"]
        assert out["sigma"] > 2

    def test_none_returns_empty_metric(self):
        out = vl.compute_forward_pe_verdict(None)
        assert out["source_ok"] is False
        assert "⬜" in out["signal"]

    def test_nan_returns_empty(self):
        out = vl.compute_forward_pe_verdict(float("nan"))
        assert out["source_ok"] is False

    def test_zero_std_degrades_gracefully(self):
        out = vl.compute_forward_pe_verdict(18.0, std=0.0)
        assert out["source_ok"] is False

    def test_custom_mean_std(self):
        # 高利率時代假設 mean=15 / std=2
        out = vl.compute_forward_pe_verdict(20.0, mean=15.0, std=2.0)
        assert out["sigma"] == 2.5
        assert "🔴" in out["signal"]


class TestGdpnowVerdict:
    def test_recession_negative(self):
        out = vl.compute_gdpnow_verdict(-1.0)
        assert "🔴" in out["signal"]
        assert "衰退" in out["verdict"]
        assert out["source_ok"] is True

    def test_below_trend(self):
        out = vl.compute_gdpnow_verdict(1.0)
        assert "🟠" in out["signal"]

    def test_neutral_in_range(self):
        out = vl.compute_gdpnow_verdict(2.5)
        assert "🟡" in out["signal"]

    def test_healthy_above_trend(self):
        out = vl.compute_gdpnow_verdict(3.5)
        assert "🟢" in out["signal"]
        assert "健康" in out["signal"]

    def test_strong_growth(self):
        out = vl.compute_gdpnow_verdict(5.0)
        assert "🟢" in out["signal"]
        assert "強勁" in out["signal"]

    def test_boundary_zero(self):
        out = vl.compute_gdpnow_verdict(0.0)
        assert "🟠" in out["signal"]  # 0 >= 0 but < 1.5 → below_trend

    def test_none_empty(self):
        out = vl.compute_gdpnow_verdict(None)
        assert out["source_ok"] is False

    def test_nan_empty(self):
        out = vl.compute_gdpnow_verdict(float("nan"))
        assert out["source_ok"] is False


class TestFetchers:
    def test_fetch_forward_pe_exception_returns_none(self):
        # yfinance import 成功但 Ticker 拋例外
        with patch("yfinance.Ticker", side_effect=RuntimeError("network")):
            assert vl.fetch_forward_pe() is None

    def test_fetch_gdpnow_empty_key_returns_none(self):
        assert vl.fetch_gdpnow("") is None

    def test_fetch_gdpnow_fetch_fred_exception_returns_none(self):
        with patch("repositories.macro_repository.fetch_fred",
                   side_effect=RuntimeError("no key")):
            assert vl.fetch_gdpnow("dummy-key-32-char-aaaaaaaaaaaaaaaa") is None

    def test_fetch_gdpnow_empty_df_returns_none(self):
        with patch("repositories.macro_repository.fetch_fred",
                   return_value=pd.DataFrame(columns=["date", "value"])):
            assert vl.fetch_gdpnow("dummy-key-32-char-aaaaaaaaaaaaaaaa") is None


class TestDetectValuation:
    def test_all_offline_returns_two_empty_metrics(self):
        with patch.object(vl, "fetch_forward_pe", return_value=None), \
             patch.object(vl, "fetch_gdpnow", return_value=None):
            out = vl.detect_valuation(None)
        # F-PROV-1 phase 19:_provenance 為 schema-additive 後設;指標 key 須 2 個
        indicator_keys = {k for k in out.keys() if not k.startswith("_")}
        assert indicator_keys == {"forward_pe", "gdpnow"}
        assert out["forward_pe"]["source_ok"] is False
        assert out["gdpnow"]["source_ok"] is False

    def test_partial_data_independent(self):
        with patch.object(vl, "fetch_forward_pe", return_value=20.0), \
             patch.object(vl, "fetch_gdpnow", return_value=None):
            out = vl.detect_valuation("dummy-key-32-char-aaaaaaaaaaaaaaaa")
        assert out["forward_pe"]["source_ok"] is True
        assert out["gdpnow"]["source_ok"] is False

    def test_both_data_present(self):
        with patch.object(vl, "fetch_forward_pe", return_value=17.0), \
             patch.object(vl, "fetch_gdpnow", return_value=2.5):
            out = vl.detect_valuation("dummy-key-32-char-aaaaaaaaaaaaaaaa")
        assert out["forward_pe"]["source_ok"] is True
        assert out["gdpnow"]["source_ok"] is True
        assert "🟡" in out["forward_pe"]["signal"]
        assert "🟡" in out["gdpnow"]["signal"]

    def test_no_fred_key_skips_gdpnow(self):
        with patch.object(vl, "fetch_forward_pe", return_value=17.0):
            # 不 patch fetch_gdpnow → 因 fred_api_key=None 不應呼叫 → 不會踩網路
            out = vl.detect_valuation(None)
        assert out["forward_pe"]["source_ok"] is True
        assert out["gdpnow"]["source_ok"] is False
