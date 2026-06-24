"""F-RECON-1 macro_health 雙演算法 — 對照 + 對帳測試(v19.108).

calc_macro_phase_zpct 與 reconcile_macro_health 的契約測試。
"""
from __future__ import annotations

import math
import pandas as pd

from services.macro_service import calc_macro_phase_zpct
from services.reconcile import reconcile_macro_health


# ── fixtures ────────────────────────────────────────────────────────────
def _make_ind(value: float, series_vals: list[float], source: str = "test:src",
              score: float = 0, weight: float = 1):
    """製造單一 indicator dict(模擬 fetch_all_indicators 子項)。"""
    s = pd.Series(series_vals, index=pd.date_range("2020-01-01", periods=len(series_vals), freq="ME"))
    return {"value": value, "series": s, "source": source, "score": score, "weight": weight}


# ── calc_macro_phase_zpct 基本契約 ──────────────────────────────────────
def test_zpct_all_at_median_returns_5():
    """所有指標都在歷史均值 → percentile = 0.5 → score = 5.0(中性擴張下緣)。"""
    series = list(range(40, 60))  # mean=49.5
    indicators = {
        f"IND_{i}": _make_ind(value=49.5, series_vals=series * 4)  # 80 期
        for i in range(3)
    }
    r = calc_macro_phase_zpct(indicators)
    assert r["status"] == "ok"
    assert r["contributing"] == 3
    assert math.isclose(r["score"], 5.0, abs_tol=0.5)
    assert r["phase"] in ("擴張", "復甦")


def test_zpct_strong_bull_returns_high_score():
    """所有指標值都 >> 歷史 mean → percentile 接近 1 → score 接近 10。"""
    series = list(range(40, 60))  # mean=49.5, sd≈6
    indicators = {
        f"IND_{i}": _make_ind(value=80.0, series_vals=series * 4)
        for i in range(3)
    }
    r = calc_macro_phase_zpct(indicators)
    assert r["status"] == "ok"
    assert r["score"] >= 8.0
    assert r["phase"] == "高峰"


def test_zpct_strong_bear_returns_low_score():
    """所有指標值都 << 歷史 mean → percentile 接近 0 → score 接近 0。"""
    series = list(range(40, 60))
    indicators = {
        f"IND_{i}": _make_ind(value=20.0, series_vals=series * 4)
        for i in range(3)
    }
    r = calc_macro_phase_zpct(indicators)
    assert r["status"] == "ok"
    assert r["score"] <= 3.0
    assert r["phase"] == "衰退"


def test_zpct_reverse_indicator_flipped():
    """反向指標(HY_SPREAD/VIX 等):高值應降低 score(風險偏好倒過來)。"""
    series = list(range(40, 60))
    # HY_SPREAD 高 → 信用緊縮 → 風險偏好低 → percentile 應該翻轉
    indicators = {
        "HY_SPREAD": _make_ind(value=80.0, series_vals=series * 4),
    }
    r = calc_macro_phase_zpct(indicators)
    assert r["status"] == "ok"
    # 反向:高值反而 score 低
    assert r["score"] <= 3.0, f"反向指標未被翻轉, score={r['score']}"


def test_zpct_insufficient_samples_skipped():
    """series < 60 期 → 該指標被跳過,不偽造 Z-score。"""
    indicators = {
        "PMI": _make_ind(value=50, series_vals=[50] * 30),  # 只 30 期
    }
    r = calc_macro_phase_zpct(indicators)
    assert r["status"] == "insufficient_data"
    assert r["contributing"] == 0
    assert r["score"] is None
    assert any("samples=30" in s for s in r["skipped"])


def test_zpct_std_zero_skipped():
    """series std=0 → 該指標被跳過(§1 Fail Loud,不偽造 z)。"""
    indicators = {
        "PMI": _make_ind(value=50, series_vals=[50] * 80),  # 全部相同 → std=0
    }
    r = calc_macro_phase_zpct(indicators)
    assert r["status"] == "insufficient_data"
    assert any("std=0" in s for s in r["skipped"])


def test_zpct_missing_series_skipped():
    """ind 缺 series 欄 → 跳過 + 寫入 skipped 清單。"""
    indicators = {
        "PMI": {"value": 50, "score": 1, "weight": 2, "source": "x"},  # 無 series
    }
    r = calc_macro_phase_zpct(indicators)
    assert r["status"] == "insufficient_data"
    assert any("missing_value_or_series" in s for s in r["skipped"])


def test_zpct_provenance_present():
    """回傳 dict 須帶 _provenance(F-PROV-1 一致命名)。"""
    series = list(range(40, 60))
    indicators = {"PMI": _make_ind(value=49.5, series_vals=series * 4)}
    r = calc_macro_phase_zpct(indicators)
    assert "_provenance" in r
    assert r["_provenance"]["aggregator"] == "macro_service.calc_macro_phase_zpct"
    assert "fetched_at" in r["_provenance"]
    assert r["_provenance"]["min_samples"] == 60


# ── reconcile_macro_health 對帳契約 ────────────────────────────────────
def test_reconcile_score_within_tolerance_agrees():
    """主路徑 6.0 vs 對照 6.5 → 差 0.5 < 1.5 → agree。"""
    r = reconcile_macro_health(6.0, 6.5, main_phase="擴張", zpct_phase="擴張")
    assert r["agree"] is True
    assert r["status"] == "agree"


def test_reconcile_phase_agree_overrides_score_disagree():
    """score 差 > 1.5 但 phase 一致 → 降級 phase_agree(語意更準確)。"""
    r = reconcile_macro_health(5.1, 7.9, main_phase="擴張", zpct_phase="擴張")
    assert r["phase_agree"] is True
    assert r["status"] == "phase_agree"
    assert r["agree"] is True


def test_reconcile_phase_disagree_stays_disagree():
    """score 差 > 1.5 且 phase 不一致 → 保持 disagree(真警示)。"""
    r = reconcile_macro_health(2.5, 6.5, main_phase="衰退", zpct_phase="擴張")
    assert r["phase_agree"] is False
    assert r["status"] == "disagree"
    assert r["agree"] is False


def test_reconcile_one_missing():
    """一邊缺資料 → a_missing / b_missing。"""
    r = reconcile_macro_health(None, 5.0, main_phase=None, zpct_phase="擴張")
    assert r["status"] == "a_missing"
    r = reconcile_macro_health(5.0, None, main_phase="擴張", zpct_phase=None)
    assert r["status"] == "b_missing"


def test_reconcile_both_missing():
    """兩邊都缺 → both_missing。"""
    r = reconcile_macro_health(None, None)
    assert r["status"] == "both_missing"


def test_reconcile_carries_source_labels():
    """確保 source_a / source_b 帶 algorithm 標籤,UI 可區別兩條路。"""
    r = reconcile_macro_health(6.0, 6.5, main_phase="擴張", zpct_phase="擴張")
    assert "calc_macro_phase" in r["source_a"]
    assert "calc_macro_phase_zpct" in r["source_b"]
