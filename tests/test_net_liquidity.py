"""v19.192 — 美股淨流動性（Fed資產 − RRP − TGA）單測。

user 2026-06-27:基金總經是美股/全球視角,補「淨流動性」做拐點確認的流動性面。
重點驗證:
  1. 單位陷阱(§4.1):WALCL/TGA = 百萬美元、RRP = 十億美元 → 換算 T 係數不同。
  2. Δ13週 燈號(綠/紅/黃)。
  3. §1 Fail Loud:任一 series 缺 → _err,不捏造。
"""
from __future__ import annotations

import math

import pandas as pd

import services.us_liquidity_engine as ule


def _mk_df(dates, values):
    return pd.DataFrame({"date": list(dates), "value": list(values)})


def _patch_fred(monkeypatch, walcl_vals, tga_vals, rrp_const=400.0):
    """注入合成 FRED 序列:WALCL/TGA 週頻、RRP 日頻覆蓋整段。"""
    wk = pd.date_range("2026-01-07", periods=len(walcl_vals), freq="7D")
    tk = pd.date_range("2026-01-07", periods=len(tga_vals), freq="7D")
    daily = pd.date_range("2025-10-01", periods=300, freq="D")

    def _fake_fetch_fred(series, api_key, n=60):
        if series == ule.FRED_FED_BS:
            return _mk_df(wk, walcl_vals)
        if series == ule.FRED_TGA:
            return _mk_df(tk, tga_vals)
        if series == ule.FRED_RRP:
            return _mk_df(daily, [rrp_const] * len(daily))
        return pd.DataFrame(columns=["date", "value"])

    monkeypatch.setattr(ule, "fetch_fred", _fake_fetch_fred)


class TestNetLiquidity:
    def test_unit_trap_correct_trillions(self, monkeypatch):
        # WALCL 6,700,000 mn / TGA 700,000 mn / RRP 400 bn → 6.7 − 0.4 − 0.7 = 5.6 T
        _patch_fred(monkeypatch, [6_700_000] * 20, [700_000] * 20, rrp_const=400.0)
        out = ule._net_liquidity("KEY")
        assert "_err" not in out
        assert out["unit"] == "T"
        assert math.isclose(out["value"], 5.6, abs_tol=1e-6), out["value"]

    def test_delta_expand_green(self, monkeypatch):
        # WALCL 每週 +30,000 mn → 13 週 Δ ≈ +0.39 T > 0.2 → 綠
        walcl = [6_700_000 + i * 30_000 for i in range(20)]
        _patch_fred(monkeypatch, walcl, [700_000] * 20)
        out = ule._net_liquidity("KEY")
        assert out["delta"] > ule.NET_LIQ_EXPAND_TN
        assert out["color"] == "#3fb950"

    def test_delta_drain_red(self, monkeypatch):
        walcl = [6_700_000 - i * 30_000 for i in range(20)]
        _patch_fred(monkeypatch, walcl, [700_000] * 20)
        out = ule._net_liquidity("KEY")
        assert out["delta"] < ule.NET_LIQ_DRAIN_TN
        assert out["color"] == "#f85149"

    def test_neutral_yellow(self, monkeypatch):
        _patch_fred(monkeypatch, [6_700_000] * 20, [700_000] * 20)
        out = ule._net_liquidity("KEY")
        assert abs(out["delta"]) <= ule.NET_LIQ_EXPAND_TN
        assert out["color"] == "#d29922"

    def test_missing_tga_fail_loud(self, monkeypatch):
        # TGA 回空 → §1 不捏造,回 _err（不回 value）
        def _fake(series, api_key, n=60):
            if series == ule.FRED_TGA:
                return pd.DataFrame(columns=["date", "value"])
            wk = pd.date_range("2026-01-07", periods=20, freq="7D")
            return _mk_df(wk, [1.0] * 20)
        monkeypatch.setattr(ule, "fetch_fred", _fake)
        out = ule._net_liquidity("KEY")
        assert "_err" in out
        assert "value" not in out

    def test_series_capped_30(self, monkeypatch):
        _patch_fred(monkeypatch, [6_700_000] * 20, [700_000] * 20)
        out = ule._net_liquidity("KEY")
        assert isinstance(out["series"], list)
        assert 0 < len(out["series"]) <= 30
        assert all(isinstance(x, float) for x in out["series"])

    def test_source_provenance(self, monkeypatch):
        _patch_fred(monkeypatch, [6_700_000] * 20, [700_000] * 20)
        out = ule._net_liquidity("KEY")
        assert out["source"] == f"FRED:{ule.FRED_FED_BS}-{ule.FRED_RRP}-{ule.FRED_TGA}"


class TestWiring:
    def test_engine_orchestrator_includes_net_liq(self):
        src = open("services/us_liquidity_engine.py", encoding="utf-8").read()
        assert '"net_liq"' in src, "orchestrator 應掛 net_liq job"
        assert "max_workers=7" in src, "worker 應 6→7"

    def test_tab1_renders_net_liq_card(self):
        src = open("ui/tab1_macro.py", encoding="utf-8").read()
        assert '"net_liq"' in src and "us_net_liq" in src, "tab1 應有 net_liq 卡 + spark_key"

    def test_fred_tga_is_ssot(self):
        src = open("shared/fred_series.py", encoding="utf-8").read()
        assert 'FRED_TGA: str = "WTREGEN"' in src, "FRED_TGA 須在 SSOT (fred_series.py)"
