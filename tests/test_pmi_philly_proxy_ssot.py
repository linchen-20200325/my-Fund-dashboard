"""ISM PMI 第 6 段 Phil Fed 替代計 — 換算常數 SSOT + 誠實揭露(2026-08-05 稽核)。

背景
----
畫面顯示「ISM 製造業 PMI 63.8」。逐段實測後定案:命中的是第 6 段 Phil Fed 替代計 ——
FRED `GACDFSA066MSFRBPHI` 2026-07 = 41.4,`50 + 41.4/3 = 63.8`,與畫面分毫不差。
官方 ISM 製造業 PMI 2026-07 實際為 55.6;63.8 若為真將是 1983 年以來最高讀數。

本檔守兩件事:
  1. `50` 與 `/3` 兩個憑空常數必須來自 SSOT(`shared/fred_series.py`),
     而且 production 程式**真的讀得到**(改 SSOT 值 → 輸出跟著變);
  2. `proxy_note` 不得再宣稱「與 ISM PMI 歷史相關性 ~0.85」(實證反例:2026-07
     Phil Fed +31.1 vs ISM +2.3),必須誠實說明母體差異與「只可看方向」。

每條測試都標注「修正前會不會紅」。
"""
from __future__ import annotations

import datetime as _dt
from unittest.mock import patch

import pandas as pd
import pytest

from shared.fred_series import (
    FRED_PHILLY_FED,
    PHILLY_FED_PMI_BASE,
    PHILLY_FED_TO_PMI_DIVISOR,
)

# FRED GACDFSA066MSFRBPHI 2026-07 實際值(稽核查證)
_PHILLY_JUL_2026 = 41.4
_PHILLY_JUN_2026 = 10.3


def _philly_df() -> pd.DataFrame:
    """8 期月頻 Phil Fed 擴散指數,末筆 = 2026-07 的 41.4(時效內)。"""
    idx = pd.date_range(end=pd.Timestamp(_dt.date.today()), periods=8, freq="ME")
    vals = [5.0, -2.0, 8.1, 3.4, -1.2, 6.6, _PHILLY_JUN_2026, _PHILLY_JUL_2026]
    return pd.DataFrame({"date": idx, "value": vals})


def _stub_fred(series_id: str, api_key: str, n: int = 250) -> pd.DataFrame:
    """只有 Phil Fed 有資料;其餘 series 回空。

    2026-09-01:原註寫「NAPM / ISPMANPMI(2016 停更)回空 → 前段自然落空」——
    那兩段已整段拔除,現在根本不會有人拿這兩個 sid 來問。註解照實更新;
    本 stub 的行為與各條測試的斷言**一字未改**(Phil Fed 路徑不受影響)。
    """
    if series_id == FRED_PHILLY_FED:
        return _philly_df()
    return pd.DataFrame(columns=["date", "value"])


def _run_pmi() -> dict:
    """跑 fetch_ism_pmi 並讓它落到第 6 段(HTML/JSON 三段全部斷線)。"""
    from repositories.macro import alternate as alt
    with patch.object(alt, "fetch_fred", side_effect=_stub_fred), \
         patch.object(alt, "fetch_url", return_value=None):
        return alt.fetch_ism_pmi("dummy-key")


class TestPhillyProxyHitsStage6:
    def test_baseline_reproduces_the_63_8_on_screen(self):
        """先釘住現況:41.4 → 63.8,證明畫面數字確實出自這段(修正前後皆綠)。"""
        out = _run_pmi()
        assert out["is_proxy"] is True
        assert out["series_id"] == FRED_PHILLY_FED
        assert out["value"] == pytest.approx(63.8, abs=0.05)


class TestTransformConstantsAreSSOT:
    """修正前:**全紅** —— `50.0` / `3.0` 是 inline literal,模組上沒有這兩個名字,
    patch.object 會直接 AttributeError。"""

    def test_divisor_is_read_from_ssot(self):
        from repositories.macro import alternate as alt
        with patch.object(alt, "PHILLY_FED_TO_PMI_DIVISOR", 2.0):
            out = _run_pmi()
        expected = PHILLY_FED_PMI_BASE + _PHILLY_JUL_2026 / 2.0
        assert out["value"] == pytest.approx(round(expected, 1), abs=0.05), (
            "改 SSOT 除數但輸出沒變 = 程式仍吃 inline literal(SSOT 未接線)")

    def test_base_is_read_from_ssot(self):
        from repositories.macro import alternate as alt
        with patch.object(alt, "PHILLY_FED_PMI_BASE", 0.0):
            out = _run_pmi()
        expected = 0.0 + _PHILLY_JUL_2026 / PHILLY_FED_TO_PMI_DIVISOR
        assert out["value"] == pytest.approx(round(expected, 1), abs=0.05)

    def test_formula_matches_ssot_values(self):
        """漂移鎖(修正前為綠,值相同):日後有人只改 SSOT 或只改公式就會紅。"""
        out = _run_pmi()
        expected = PHILLY_FED_PMI_BASE + _PHILLY_JUL_2026 / PHILLY_FED_TO_PMI_DIVISOR
        assert out["value"] == pytest.approx(round(expected, 1), abs=0.05)

    def test_whole_series_uses_same_transform(self):
        """`values` 整條序列(餵 Z-Score / lag-corr)也必須走同一個換算式。"""
        out = _run_pmi()
        expected_prev = PHILLY_FED_PMI_BASE + _PHILLY_JUN_2026 / PHILLY_FED_TO_PMI_DIVISOR
        assert out["values"][-2] == pytest.approx(round(expected_prev, 1), abs=0.05)


class TestProxyNoteIsHonest:
    """修正前:**全紅** —— 原 note 寫「與 ISM PMI 歷史相關性 ~0.85」。"""

    def test_no_longer_claims_085_correlation(self):
        note = _run_pmi()["proxy_note"]
        assert "0.85" not in note, (
            "0.85 為過度宣稱:Phil Fed 是單一聯準區約 250 家廠商的月變化擴散指數,"
            "ISM 是全國 16 大產業複合指數;2026-07 Phil Fed +31.1 而 ISM 僅 +2.3")

    def test_states_it_is_not_ism_pmi(self):
        note = _run_pmi()["proxy_note"]
        assert "不是 ISM PMI" in note

    def test_states_direction_only_limitation(self):
        note = _run_pmi()["proxy_note"]
        assert "方向" in note and "水準值" in note

    def test_note_carries_the_actual_formula(self):
        """note 內的公式必須跟著 SSOT 走(避免文案與程式各說各話)。"""
        note = _run_pmi()["proxy_note"]
        assert f"diffusion/{PHILLY_FED_TO_PMI_DIVISOR:.0f}" in note


class TestProxyFlagIsSetAtSource:
    """L2(services/macro/us_indicators.py:377)靠 `is_proxy` 決定要不要加
    「(Phil Fed 替代)」後綴 —— 本檔只能守到 L1 出口這一段(us_indicators.py
    不在本次所有權內),旗標鏈的查證結果寫在交付報告。"""

    def test_is_proxy_true_and_label_marks_substitute(self):
        out = _run_pmi()
        assert out["is_proxy"] is True
        assert "Phil Fed" in out["label"]
        assert out["source"].endswith(":proxy")
