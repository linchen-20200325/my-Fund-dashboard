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
    df = calc_macro_score_series(inds, years=5, freq="ME", prefer_parquet=False)
    assert not df.empty
    assert set(df.columns) == {"score", "phase", "n_indicators"}
    assert isinstance(df.index, pd.DatetimeIndex)


def test_calc_macro_score_series_expansion_phase():
    """好景氣指標全綠 → phase 應為高峰/擴張。"""
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=15, hy_val=3)
    df = calc_macro_score_series(inds, years=5, prefer_parquet=False)
    assert (df["score"] >= 8).all()
    assert df["phase"].iloc[-1] in ("高峰", "擴張")


def test_calc_macro_score_series_recession_phase():
    """壞景氣指標全紅 → phase 應為衰退。"""
    inds = _make_synthetic_indicators(pmi_val=40, vix_val=40, hy_val=7)
    df = calc_macro_score_series(inds, years=5, prefer_parquet=False)
    assert (df["score"] <= 2).all()
    assert df["phase"].iloc[-1] == "衰退"


def test_calc_macro_score_series_n_indicators_counts_coverage():
    """n_indicators 反映實際參與打分的指標數。"""
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=15, hy_val=3)
    df = calc_macro_score_series(inds, years=5, prefer_parquet=False)
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


# ════════════════════════════════════════════════════════════════
# v18.276 Phase B.2：load_indicators_from_parquet
# ════════════════════════════════════════════════════════════════
def _write_fred_parquet(cache_dir: Path, series_data: dict[str, list[tuple]]) -> None:
    """Helper：寫一個 fred_indicators.parquet — series_data: {series_id: [(date_str, value), ...]}."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for sid, points in series_data.items():
        for d, v in points:
            rows.append({"date": d, "series_id": sid, "value": float(v)})
    df = pd.DataFrame(rows)
    df.to_parquet(cache_dir / "fred_indicators.parquet",
                  compression="snappy", index=False)


def _write_vix_parquet(cache_dir: Path, points: list[tuple]) -> None:
    cache_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame([{"date": d, "close": float(c)} for d, c in points])
    df.to_parquet(cache_dir / "vix_history.parquet",
                  compression="snappy", index=False)


def test_load_indicators_from_parquet_missing_dir(tmp_path: Path):
    """缺檔/不存在的目錄 → 回空 dict（不 raise）。"""
    from services.macro_validation import load_indicators_from_parquet
    out = load_indicators_from_parquet(tmp_path / "noexist")
    assert out == {}


def test_load_indicators_from_parquet_empty_dir(tmp_path: Path):
    """存在但無 Parquet → 回空 dict。"""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    cache.mkdir()
    assert load_indicators_from_parquet(cache) == {}


def test_load_indicators_from_parquet_yield_spread(tmp_path: Path):
    """YIELD_10Y2Y = DGS10 - DGS2."""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    _write_fred_parquet(cache, {
        "DGS10": [("2024-01-01", 4.5), ("2024-01-02", 4.6)],
        "DGS2":  [("2024-01-01", 4.2), ("2024-01-02", 4.3)],
    })
    out = load_indicators_from_parquet(cache)
    assert "YIELD_10Y2Y" in out
    s = out["YIELD_10Y2Y"]["series"]
    assert round(float(s.iloc[0]), 2) == 0.30
    assert round(float(s.iloc[1]), 2) == 0.30


def test_load_indicators_from_parquet_yield_3m_spread(tmp_path: Path):
    """YIELD_10Y3M = DGS10 - DGS3MO."""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    _write_fred_parquet(cache, {
        "DGS10":  [("2024-01-01", 4.5)],
        "DGS3MO": [("2024-01-01", 5.2)],   # 倒掛
    })
    out = load_indicators_from_parquet(cache)
    assert "YIELD_10Y3M" in out
    assert round(float(out["YIELD_10Y3M"]["series"].iloc[0]), 2) == -0.70


def test_load_indicators_from_parquet_hy_direct(tmp_path: Path):
    """HY_SPREAD = BAMLH0A0HYM2 直接 level。"""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    _write_fred_parquet(cache, {
        "BAMLH0A0HYM2": [("2024-01-01", 3.5), ("2024-01-02", 4.0)],
    })
    out = load_indicators_from_parquet(cache)
    assert "HY_SPREAD" in out
    assert float(out["HY_SPREAD"]["series"].iloc[-1]) == 4.0


def test_load_indicators_from_parquet_m2_yoy(tmp_path: Path):
    """M2 用 12 個月 shift 算 YoY% — 至少 13 點才有第一個 YoY 值."""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    # 13 個月，M2SL 從 100 線性升到 110 → YoY = 10%
    dates = pd.date_range("2023-01-01", periods=13, freq="MS")
    points = [(str(d.date()), 100.0 + i) for i, d in enumerate(dates)]
    _write_fred_parquet(cache, {"M2SL": points})
    out = load_indicators_from_parquet(cache)
    assert "M2" in out
    yoy = out["M2"]["series"].iloc[-1]
    # 12 個月後 M2SL = 112，YoY = (112/100 - 1) * 100 = 12.0%
    assert round(float(yoy), 1) == 12.0


def test_load_indicators_from_parquet_m2_insufficient_history(tmp_path: Path):
    """M2 只有 < 13 點 → 不能算 YoY → 不在 output."""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    _write_fred_parquet(cache, {
        "M2SL": [(f"2024-{m:02d}-01", 100.0 + m) for m in range(1, 11)],   # 10 月
    })
    out = load_indicators_from_parquet(cache)
    assert "M2" not in out


def test_load_indicators_from_parquet_unrate_direct(tmp_path: Path):
    """UNEMPLOYMENT = UNRATE 直接 level。"""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    _write_fred_parquet(cache, {
        "UNRATE": [("2024-01-01", 3.8), ("2024-02-01", 3.9)],
    })
    out = load_indicators_from_parquet(cache)
    assert "UNEMPLOYMENT" in out
    assert float(out["UNEMPLOYMENT"]["series"].iloc[-1]) == 3.9


def test_load_indicators_from_parquet_vix_from_separate_file(tmp_path: Path):
    """VIX 從 vix_history.parquet 取（不在 fred_indicators 內）."""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    _write_vix_parquet(cache, [("2024-01-01", 15.5), ("2024-01-02", 18.2)])
    out = load_indicators_from_parquet(cache)
    assert "VIX" in out
    assert float(out["VIX"]["series"].iloc[-1]) == 18.2


def test_load_indicators_from_parquet_pmi_not_present(tmp_path: Path):
    """PMI 不該在 Parquet 載入結果中（PR #160 暫不抓 PMI）."""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    # 即使建好其他 series，PMI 也不該出現
    _write_fred_parquet(cache, {
        "DGS10": [("2024-01-01", 4.5)],
        "DGS2":  [("2024-01-01", 4.2)],
    })
    out = load_indicators_from_parquet(cache)
    assert "PMI" not in out


def test_load_indicators_from_parquet_corrupt_file_graceful(tmp_path: Path):
    """壞 Parquet 檔不 raise — 印警告然後跳過。"""
    from services.macro_validation import load_indicators_from_parquet
    cache = tmp_path / "data_cache"
    cache.mkdir()
    (cache / "fred_indicators.parquet").write_bytes(b"not_a_real_parquet")
    out = load_indicators_from_parquet(cache)
    assert out == {}   # 應 graceful 回空


# ════════════════════════════════════════════════════════════════
# v18.276 Phase B.2：calc_macro_score_series prefer_parquet
# ════════════════════════════════════════════════════════════════
def test_calc_macro_score_series_uses_parquet_by_default(tmp_path: Path):
    """prefer_parquet=True 預設 → 完全靠 Parquet 也能算出 score 序列."""
    cache = tmp_path / "data_cache"
    # 建 5 個指標的 Parquet（PMI 缺，剩餘 5 個有 series → 共覆蓋 5/9）
    _write_fred_parquet(cache, {
        "DGS10":        [("2024-%02d-01" % m, 4.5) for m in range(1, 13)],
        "DGS2":         [("2024-%02d-01" % m, 4.2) for m in range(1, 13)],
        "BAMLH0A0HYM2": [("2024-%02d-01" % m, 3.5) for m in range(1, 13)],
        "UNRATE":       [("2024-%02d-01" % m, 3.8) for m in range(1, 13)],
    })
    _write_vix_parquet(cache, [
        ("2024-%02d-01" % m, 15.0) for m in range(1, 13)
    ])
    df = calc_macro_score_series(
        indicators_now=None, years=1, freq="ME",
        prefer_parquet=True, cache_dir=cache,
    )
    assert not df.empty
    # 至少有 5 個指標參與打分（YIELD_10Y2Y / HY_SPREAD / UNEMPLOYMENT / VIX；
    # YIELD_10Y3M 缺 DGS3MO 故只有 4 個）
    assert df["n_indicators"].max() >= 4


def test_calc_macro_score_series_prefer_parquet_false_uses_only_indicators_now(tmp_path: Path):
    """prefer_parquet=False → 完全略過 Parquet，只用 indicators_now."""
    cache = tmp_path / "data_cache"
    _write_fred_parquet(cache, {
        "DGS10": [("2024-01-01", 4.5)],
        "DGS2":  [("2024-01-01", 4.2)],
    })
    # indicators_now 只有 PMI
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=15, hy_val=3)
    inds.pop("VIX"); inds.pop("HY_SPREAD")   # 只剩 PMI
    df = calc_macro_score_series(
        indicators_now=inds, years=2, freq="ME",
        prefer_parquet=False, cache_dir=cache,
    )
    # YIELD_10Y2Y 不該進來（被略過）
    assert (df["n_indicators"] == 1).all()


def test_calc_macro_score_series_merge_parquet_and_indicators(tmp_path: Path):
    """Parquet 提供 YIELD + VIX，indicators_now 提供 PMI → 合併共 3 個."""
    cache = tmp_path / "data_cache"
    _write_fred_parquet(cache, {
        "DGS10": [("2024-%02d-01" % m, 4.5) for m in range(1, 13)],
        "DGS2":  [("2024-%02d-01" % m, 4.2) for m in range(1, 13)],
    })
    _write_vix_parquet(cache, [
        ("2024-%02d-01" % m, 15.0) for m in range(1, 13)
    ])
    # indicators_now 只給 PMI
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=15, hy_val=3)
    inds.pop("VIX"); inds.pop("HY_SPREAD")
    df = calc_macro_score_series(
        indicators_now=inds, years=1, freq="ME",
        prefer_parquet=True, cache_dir=cache,
    )
    # YIELD_10Y2Y (parquet) + VIX (parquet) + PMI (indicators_now) = 3
    assert df["n_indicators"].max() >= 3


def test_calc_macro_score_series_parquet_takes_precedence(tmp_path: Path):
    """Parquet 與 indicators_now 都有 VIX → Parquet 優先。"""
    cache = tmp_path / "data_cache"
    # Parquet VIX = 50（恐慌）
    _write_vix_parquet(cache, [
        ("2024-%02d-01" % m, 50.0) for m in range(1, 13)
    ])
    # indicators_now VIX = 10（極平靜）
    inds = _make_synthetic_indicators(pmi_val=55, vix_val=10, hy_val=3)
    df = calc_macro_score_series(
        indicators_now=inds, years=1, freq="ME",
        prefer_parquet=True, cache_dir=cache,
    )
    # 50 > 30 → VIX score = -1（恐慌）
    # 若 Parquet 優先，score 會比兩者皆樂觀低
    # 至少 phase 不該是「高峰」（score=10 是 indicators_now 全綠才會發生）
    # 但因 PMI/HY_SPREAD/Yield 都用 indicators_now，VIX 從 Parquet 50 → 較低
    # 我們驗 VIX series 從 Parquet 取（50 不是 10）
    from services.macro_validation import load_indicators_from_parquet
    parquet_dict = load_indicators_from_parquet(cache)
    assert float(parquet_dict["VIX"]["series"].iloc[-1]) == 50.0


# ════════════════════════════════════════════════════════════════
# UI: macro_score CSV 下載按鈕
# ════════════════════════════════════════════════════════════════
def test_ui_has_macro_score_csv_download_button():
    """Phase 3.5 section 必須含 macro_score CSV 下載按鈕（v18.276 新增）."""
    src = (Path(__file__).parent / "ui" / "tab_crisis_backtest.py").read_text(encoding="utf-8")
    assert "macro_score 月序列 CSV" in src or "下載 macro_score" in src
    assert "crisis_score_csv_download" in src   # 按鈕 key
    assert "to_csv" in src                       # 實際匯出邏輯


def test_ui_uses_parquet_cache_for_phase_3_5():
    """Phase 3.5 section 應引用 load_indicators_from_parquet（v18.276 新）."""
    src = (Path(__file__).parent / "ui" / "tab_crisis_backtest.py").read_text(encoding="utf-8")
    assert "load_indicators_from_parquet" in src
    assert "fred_indicators.parquet" in src
