"""test_macro_validation.py — services/macro_validation.py 單元測試 (v18.260 Phase 6a)."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from services.macro_validation import (
    SCORE_RULES,
    aggregate_score,
    calc_macro_score_series,
    compute_period_stats,
    verify_score_vs_crises,
)


# ──────────────────────────────────────────────────────────────
# SCORE_RULES 結構驗證
# ──────────────────────────────────────────────────────────────
def test_score_rules_contains_core_indicators():
    """核心 9 指標必須在 SCORE_RULES 內（鏡像 fetch_all_indicators 的 score 邏輯）。"""
    required = {"PMI", "YIELD_10Y2Y", "YIELD_10Y3M", "HY_SPREAD",
                "M2", "FED_BS", "VIX", "CPI", "UNEMPLOYMENT"}
    assert required.issubset(SCORE_RULES.keys())


def test_score_rules_weights_match_calc_macro_phase_docstring():
    """SCORE_RULES weights 必須與 calc_macro_phase docstring 標示一致。"""
    expected = {
        "PMI": 2.0, "YIELD_10Y2Y": 2.0, "YIELD_10Y3M": 2.0, "HY_SPREAD": 2.0,
        "M2": 1.0, "FED_BS": 1.0, "VIX": 1.0,
        "CPI": 0.5, "UNEMPLOYMENT": 0.5,
    }
    for k, w in expected.items():
        assert SCORE_RULES[k][0] == w, f"{k} weight should be {w}, got {SCORE_RULES[k][0]}"


def test_score_rules_threshold_boundary():
    """SCORE_RULES 閾值邊界驗證。"""
    pmi_fn = SCORE_RULES["PMI"][1]
    assert pmi_fn(55) == 2.0          # 擴張
    assert pmi_fn(50) == 2.0          # 榮枯線剛好
    assert pmi_fn(47) == -1.0         # 50→45 中間
    assert pmi_fn(40) == -2.0         # 衰退

    vix_fn = SCORE_RULES["VIX"][1]
    assert vix_fn(15) == 1.0
    assert vix_fn(20) == 0.0
    assert vix_fn(35) == -1.0

    hy_fn = SCORE_RULES["HY_SPREAD"][1]
    assert hy_fn(3) == 2.0
    assert hy_fn(5) == 0.0
    assert hy_fn(7) == -2.0


# ──────────────────────────────────────────────────────────────
# aggregate_score
# ──────────────────────────────────────────────────────────────
def test_aggregate_score_all_positive():
    """全綠 → 接近 10 分 → phase 高峰。"""
    scored = {"PMI": (2.0, 2.0), "VIX": (1.0, 1.0), "HY_SPREAD": (2.0, 2.0)}
    score, phase = aggregate_score(scored)
    assert score == 10.0
    assert phase == "高峰"


def test_aggregate_score_all_negative():
    """全紅 → 0 分 → phase 衰退。"""
    scored = {"PMI": (2.0, -2.0), "VIX": (1.0, -1.0), "HY_SPREAD": (2.0, -2.0)}
    score, phase = aggregate_score(scored)
    assert score == 0.0
    assert phase == "衰退"


def test_aggregate_score_neutral():
    """全 0 → 5 分 → phase 擴張（5 為下限）。"""
    scored = {"PMI": (2.0, 0.0), "VIX": (1.0, 0.0)}
    score, phase = aggregate_score(scored)
    assert score == 5.0
    assert phase == "擴張"


def test_aggregate_score_empty_dict():
    """空字典 → 預設 5 / 復甦（避免崩潰）。"""
    score, phase = aggregate_score({})
    assert score == 5.0


# ──────────────────────────────────────────────────────────────
# calc_macro_score_series
# ──────────────────────────────────────────────────────────────
def _make_synthetic_indicators(pmi_val: float, vix_val: float, hy_val: float) -> dict:
    """建合成 indicators dict — 25 年月頻 series 確保涵蓋任何 ≤20 年 date_range。"""
    n = 25 * 12
    idx = pd.date_range(end=pd.Timestamp.today(), periods=n, freq="ME")
    return {
        "PMI":       {"value": pmi_val, "weight": 2, "series": pd.Series([pmi_val] * n, index=idx)},
        "VIX":       {"value": vix_val, "weight": 1, "series": pd.Series([vix_val] * n, index=idx)},
        "HY_SPREAD": {"value": hy_val,  "weight": 2, "series": pd.Series([hy_val]  * n, index=idx)},
    }


def test_calc_macro_score_series_returns_expected_columns():
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=15, hy_val=3)
    df = calc_macro_score_series(inds, years=5, freq="ME")
    assert not df.empty
    assert set(df.columns) == {"score", "phase", "n_indicators"}
    assert isinstance(df.index, pd.DatetimeIndex)


def test_calc_macro_score_series_expansion_phase():
    """好景氣指標全綠 → phase 應為高峰/擴張。"""
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=15, hy_val=3)
    df = calc_macro_score_series(inds, years=5)
    assert (df["score"] >= 8).all()
    assert df["phase"].iloc[-1] in ("高峰", "擴張")


def test_calc_macro_score_series_recession_phase():
    """壞景氣指標全紅 → phase 應為衰退。"""
    inds = _make_synthetic_indicators(pmi_val=40, vix_val=40, hy_val=7)
    df = calc_macro_score_series(inds, years=5)
    assert (df["score"] <= 2).all()
    assert df["phase"].iloc[-1] == "衰退"


def test_calc_macro_score_series_n_indicators_counts_coverage():
    """n_indicators 反映實際參與打分的指標數。"""
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=15, hy_val=3)
    df = calc_macro_score_series(inds, years=5)
    assert (df["n_indicators"] == 3).all()


# ──────────────────────────────────────────────────────────────
# verify_score_vs_crises
# ──────────────────────────────────────────────────────────────
class _FakeEvent:
    def __init__(self, peak_date, trough_date):
        self.peak_date = pd.Timestamp(peak_date)
        self.trough_date = pd.Timestamp(trough_date)


def test_verify_score_drop_hit():
    """模擬 peak 前 6 月 score=7、peak 月 score=3 → 降幅 -57% → 命中。"""
    # idx = 2019-01-31 月底起 36 個月（→2021-12-31）
    idx = pd.date_range("2019-01-01", periods=36, freq="ME")
    # 前 12 月(2019)=7.0，後 24 月(2020-2021)=3.0
    # lead (Jun 2020 - 6m = Dec 2019) → 7.0；peak (Jun 2020) → 3.0
    scores = [7.0] * 12 + [3.0] * 24
    df = pd.DataFrame({"score": scores, "phase": ["x"] * 36, "n_indicators": [3] * 36}, index=idx)
    events = [_FakeEvent("2020-06-30", "2020-12-31")]
    results = verify_score_vs_crises(df, events, lead_months=6, drop_threshold=0.20)
    assert len(results) == 1
    r = results[0]
    assert r.score_lead == 7.0
    assert r.score_peak == 3.0
    assert r.score_drop_pct is not None
    assert r.score_drop_pct < -0.20
    assert r.hit is True


def test_verify_score_flat_miss():
    """模擬 score 全 5 → 無降幅 → 不命中。"""
    idx = pd.date_range("2019-01-01", periods=36, freq="ME")
    df = pd.DataFrame({"score": [5.0] * 36, "phase": ["x"] * 36, "n_indicators": [3] * 36}, index=idx)
    events = [_FakeEvent("2020-06-30", "2020-12-31")]
    results = verify_score_vs_crises(df, events, lead_months=6, drop_threshold=0.20)
    assert results[0].hit is False


def test_verify_empty_events_returns_empty():
    idx = pd.date_range("2019-01-01", periods=12, freq="ME")
    df = pd.DataFrame({"score": [5.0] * 12, "phase": ["x"] * 12, "n_indicators": [3] * 12}, index=idx)
    assert verify_score_vs_crises(df, [], lead_months=6) == []


# ──────────────────────────────────────────────────────────────
# compute_period_stats
# ──────────────────────────────────────────────────────────────
def test_compute_period_stats_distinguishes_crisis_vs_normal():
    """crisis 期 score 都低、平時 score 都高 → p < 0.05 + 平均明顯有別。"""
    pytest.importorskip("scipy")
    import numpy as np
    rng = np.random.default_rng(42)
    idx = pd.date_range("2019-01-01", periods=48, freq="ME")
    # 設計：2020-03 ~ 2020-12 為 crisis（10 個月）→ score≈2±0.3；其餘 38 個月 → score≈7±0.3
    # 加微噪避免 variance=0 導致 scipy t-test 回 NaN
    scores = []
    for d in idx:
        if pd.Timestamp("2020-03-01") <= d <= pd.Timestamp("2020-12-31"):
            scores.append(2.0 + rng.normal(0, 0.3))
        else:
            scores.append(7.0 + rng.normal(0, 0.3))
    df = pd.DataFrame({"score": scores, "phase": ["x"] * 48, "n_indicators": [3] * 48}, index=idx)
    events = [_FakeEvent("2020-03-31", "2020-12-31")]
    stats = compute_period_stats(df, events)
    assert stats["crisis_mean"] is not None and stats["crisis_mean"] < 3.0
    assert stats["normal_mean"] is not None and stats["normal_mean"] > 6.0
    assert stats["n_crisis"] >= 5
    assert stats["n_normal"] >= 5
    # scipy 在 requirements → p_value 必須有 + 顯著
    assert stats["p_value"] is not None
    assert stats["p_value"] < 0.05


def test_compute_period_stats_empty_input():
    df = pd.DataFrame(columns=["score", "phase", "n_indicators"])
    stats = compute_period_stats(df, [])
    assert stats["crisis_mean"] is None
    assert stats["p_value"] is None


# ──────────────────────────────────────────────────────────────
# UI source-level（不 mock-render，僅驗結構）
# ──────────────────────────────────────────────────────────────
def test_phase_3_5_section_in_ui_source():
    """ui/tab_crisis_backtest.py 必須含 Phase 3.5 section 函式 + 呼叫。"""
    src = (Path(__file__).parent / "ui" / "tab_crisis_backtest.py").read_text(encoding="utf-8")
    assert "_render_score_validation_section" in src
    assert "Phase 3.5" in src
    assert "Tab1 Macro Score 預測力驗證" in src


def test_phase_3_5_called_between_phase_3_and_phase_4():
    """Phase 3.5 必須在 Phase 3 後、Phase 4 前。"""
    src = (Path(__file__).parent / "ui" / "tab_crisis_backtest.py").read_text(encoding="utf-8")
    # v18.261 後 render 主流程改用 years_disp（自 session_state cache 取出）
    idx_3 = src.find("_render_signal_lookback_section(events,")
    idx_35 = src.find("_render_score_validation_section(events,")
    idx_4 = src.find("_render_strategy_grid_section(mkt_series")
    assert idx_3 > 0 and idx_35 > 0 and idx_4 > 0
    assert idx_3 < idx_35 < idx_4, "Phase 3.5 必須夾在 Phase 3 與 Phase 4 之間"


def test_phase_3_5_imports_macro_validation_service():
    """Phase 3.5 必須從 services.macro_validation 拉 3 個核心函式。"""
    src = (Path(__file__).parent / "ui" / "tab_crisis_backtest.py").read_text(encoding="utf-8")
    assert "from services.macro_validation import" in src
    for fn in ("calc_macro_score_series", "verify_score_vs_crises", "compute_period_stats"):
        assert fn in src, f"UI 缺少 {fn} import / 使用"
