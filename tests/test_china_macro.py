"""test_china_macro.py — v19.113 方向 B China macro 補完

驗證重點:
1. fetch_china_macro 走 fetch_fred_batch(NAS proxy)、回 dict[series_id, DataFrame]
2. china_macro_snapshot 對齊 5 + 1 衍生 key,正確 zone 分級
3. calc_china_credit_impulse_proxy 邊界條件(None / 短資料 / 正常 N+1)
4. _CHINA_FRED_SPECS 與 SSOT 常數對齊(防 ID 漂移)
"""
from __future__ import annotations

from unittest.mock import patch

import pandas as pd

from services.macro import (
    calc_china_credit_impulse_proxy,
    china_macro_snapshot,
)
from shared.fred_series import (
    FRED_CHN_CPI,
    FRED_CHN_M2,
    FRED_CHN_OECD_CLI,
    FRED_CHN_PMI,
    FRED_CNH_USD,
)


# ══════════════════════════════════════════════════════════════
# 1. SSOT 常數對齊(防 ID 漂移)
# ══════════════════════════════════════════════════════════════

def test_china_fred_ids_match_documented():
    assert FRED_CHN_OECD_CLI == "CHNLOLITONOSTSAM"
    assert FRED_CHN_CPI == "CPALTT01CNM659N"
    assert FRED_CHN_M2 == "MABMM301CNM189S"
    assert FRED_CHN_PMI == "BSCICP03CNM665S"
    assert FRED_CNH_USD == "DEXCHUS"


def test_china_fred_specs_uses_ssot():
    from repositories.macro_repository import _CHINA_FRED_SPECS
    ids = {sid for sid, _ in _CHINA_FRED_SPECS}
    expected = {FRED_CNH_USD, FRED_CHN_OECD_CLI, FRED_CHN_CPI,
                FRED_CHN_M2, FRED_CHN_PMI}
    assert ids == expected, f"specs 與 SSOT 不一致: {ids} vs {expected}"


# ══════════════════════════════════════════════════════════════
# 2. fetch_china_macro batch
# ══════════════════════════════════════════════════════════════

def test_fetch_china_macro_no_key_returns_empty():
    from repositories.macro_repository import fetch_china_macro
    assert fetch_china_macro("") == {}


def test_fetch_china_macro_uses_fetch_fred_batch():
    """空 api_key 短路返回;非空時委派給 fetch_fred_batch"""
    from repositories import macro_repository

    captured = {}

    def fake_batch(specs, api_key, max_workers=8):
        captured["specs"] = specs
        captured["api_key"] = api_key
        return {sid: pd.DataFrame() for sid, _ in specs}

    # B1 v19.205: fetch_china_macro 在 china.py 內 `from .fred import fetch_fred_batch`,
    # patch shim attribute 不穿透 sub-module binding,改 patch 子模組 binding。
    with patch("repositories.macro.china.fetch_fred_batch", side_effect=fake_batch):
        out = macro_repository.fetch_china_macro("fake_key")

    assert captured["api_key"] == "fake_key"
    assert len(captured["specs"]) == 5
    # 5 個 ID 全部出現
    sids = {sid for sid, _ in captured["specs"]}
    assert sids == {FRED_CNH_USD, FRED_CHN_OECD_CLI, FRED_CHN_CPI,
                    FRED_CHN_M2, FRED_CHN_PMI}
    assert len(out) == 5


# ══════════════════════════════════════════════════════════════
# 3. china_macro_snapshot
# ══════════════════════════════════════════════════════════════

def _make_df(value: float, date: str = "2025-12-01") -> pd.DataFrame:
    return pd.DataFrame({
        "date": [pd.Timestamp(date)],
        "value": [value],
        "source": [f"FRED:test"],
        "fetched_at": ["2026-06-24T10:00:00Z"],
    })


def test_china_macro_snapshot_empty():
    out = china_macro_snapshot({})
    assert set(out.keys()) == {"cli", "pmi", "cpi_yoy", "m2_yoy",
                               "usdcny", "credit_impulse_proxy"}
    for k in ("cli", "pmi", "cpi_yoy", "m2_yoy", "usdcny"):
        assert out[k]["value"] is None
        assert out[k]["zone"] == "⬜ 無資料"
    assert out["credit_impulse_proxy"] is None


def test_china_macro_snapshot_cli_green():
    """CLI > 100 → 🟢 綠"""
    out = china_macro_snapshot({FRED_CHN_OECD_CLI: _make_df(100.5)})
    assert out["cli"]["value"] == 100.5
    assert "🟢" in out["cli"]["zone"]


def test_china_macro_snapshot_cli_red():
    """CLI < 98 → 🔴 紅(衰退觸發)"""
    out = china_macro_snapshot({FRED_CHN_OECD_CLI: _make_df(97.2)})
    assert "🔴" in out["cli"]["zone"]


def test_china_macro_snapshot_cpi_yellow_above():
    """CPI > 4% → 🟡"""
    out = china_macro_snapshot({FRED_CHN_CPI: _make_df(4.5)})
    assert "🟡" in out["cpi_yoy"]["zone"]


def test_china_macro_snapshot_usdcny_red_at_7p5():
    """USDCNY > 7.4 → 🔴(人民幣大幅貶值)"""
    out = china_macro_snapshot({FRED_CNH_USD: _make_df(7.45)})
    assert "🔴" in out["usdcny"]["zone"]


def test_china_macro_snapshot_m2_red_below_5():
    """M3 level series:13 月後 YoY < 5% → 🔴(信用緊縮)
    v19.115 校正:M3(FRED MABMM301CNM189S)為 level 兆 CNY,
    snapshot 內部 pct_change(12) 轉 YoY 才進 scorer。
    """
    # 13 筆 level:從 250 → 260(漲 4.0%,< 5% 緊縮閾值)
    dates = pd.date_range('2025-01-01', periods=13, freq='ME')
    levels = [250 + i * (10/12) for i in range(13)]  # 12 月漲 10 兆 = 4%
    df = pd.DataFrame({
        "date": dates,
        "value": levels,
        "source": ["FRED:test"] * 13,
        "fetched_at": ["2026-06-24"] * 13,
    })
    out = china_macro_snapshot({FRED_CHN_M2: df})
    assert "🔴" in out["m2_yoy"]["zone"], (
        f"expected 🔴 紅,got zone={out['m2_yoy']['zone']}, value={out['m2_yoy']['value']}"
    )


def test_china_macro_snapshot_m2_short_series_no_yoy():
    """v19.115 校正:M3 level 不足 13 筆 → YoY 不可算 → ⬜ 無資料"""
    out = china_macro_snapshot({FRED_CHN_M2: _make_df(280.0)})
    assert out["m2_yoy"]["zone"] == "⬜ 無資料"
    assert out["m2_yoy"]["value"] is None


def test_china_macro_snapshot_m2_level_to_yoy_green():
    """M3 level 漲 10% YoY → 🟢 綠(寬鬆)"""
    dates = pd.date_range('2025-01-01', periods=13, freq='ME')
    levels = [250 * (1 + 0.10 * i / 12) for i in range(13)]
    df = pd.DataFrame({
        "date": dates, "value": levels,
        "source": ["FRED:test"] * 13, "fetched_at": ["2026-06-24"] * 13,
    })
    out = china_macro_snapshot({FRED_CHN_M2: df})
    assert "🟢" in out["m2_yoy"]["zone"]
    assert 9.0 <= out["m2_yoy"]["value"] <= 11.0


def test_china_macro_snapshot_provenance_passes_through():
    """source 從 fetch_fred 結果中正確 forward"""
    df = _make_df(99.5)
    df["source"] = "FRED:CHNLOLITONOSTSAM"
    out = china_macro_snapshot({FRED_CHN_OECD_CLI: df})
    assert "CHNLOLITONOSTSAM" in out["cli"]["source"]


# ══════════════════════════════════════════════════════════════
# 4. calc_china_credit_impulse_proxy
# ══════════════════════════════════════════════════════════════

def test_credit_impulse_none_input():
    assert calc_china_credit_impulse_proxy(None) is None


def test_credit_impulse_short_series():
    """資料 < 13 筆 → None"""
    s = pd.Series([8.0] * 10)
    assert calc_china_credit_impulse_proxy(s, lag_months=12) is None


def test_credit_impulse_accelerating():
    """近期 M2 YoY 加速 → 正值"""
    s = pd.Series([6.0] * 12 + [10.0])  # 12 月前 6%、最新 10%
    assert calc_china_credit_impulse_proxy(s, lag_months=12) == 4.0


def test_credit_impulse_decelerating():
    """近期 M2 YoY 減速 → 負值"""
    s = pd.Series([10.0] * 12 + [6.0])
    assert calc_china_credit_impulse_proxy(s, lag_months=12) == -4.0


def test_credit_impulse_lag_param():
    s = pd.Series([5.0] * 6 + [9.0])  # 6 月前 5%、最新 9%
    assert calc_china_credit_impulse_proxy(s, lag_months=6) == 4.0
