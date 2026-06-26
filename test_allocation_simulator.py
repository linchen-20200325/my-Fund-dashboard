"""test_allocation_simulator.py — services/allocation_simulator.py 測試 (Phase 6b)."""
from __future__ import annotations

from pathlib import Path

import pytest

from services.allocation_simulator import (
    DEFAULT_PHASE_SCRIPT,
    SimulationParams,
    run_monte_carlo,
    run_single_simulation,
    summarize_simulation,
    validate_and_normalize,
)


def _params(**kwargs) -> SimulationParams:
    base = dict(
        amount_twd=1_000_000.0,
        annual_yield_pct=6.0,
        initial_nav=10.0,
        initial_fx=32.0,
        phase_script=list(DEFAULT_PHASE_SCRIPT),
        drip_pct=70.0,
        cash_pct=20.0,
        stay_pct=10.0,
        stay_yield_pct=1.5,
        fx_model="fixed",
    )
    base.update(kwargs)
    return SimulationParams(**base)


# ──────────────────────────────────────────────────────────────
# 預設 phase_script 結構驗證
# ──────────────────────────────────────────────────────────────
def test_default_phase_script_4_segments_user_spec():
    """User 指定預設 4 段：復甦 / 擴張 / 放緩 / 衰退（含放緩，非高峰）。"""
    assert len(DEFAULT_PHASE_SCRIPT) == 4
    names = [seg["phase"] for seg in DEFAULT_PHASE_SCRIPT]
    assert names == ["復甦", "擴張", "放緩", "衰退"]


def test_default_phase_script_all_have_required_keys():
    for seg in DEFAULT_PHASE_SCRIPT:
        assert "months" in seg
        assert "phase" in seg
        assert "monthly_nav_change_pct" in seg


# ──────────────────────────────────────────────────────────────
# validate_and_normalize
# ──────────────────────────────────────────────────────────────
def test_validate_sum_already_100():
    p = _params(drip_pct=70, cash_pct=20, stay_pct=10)
    p2 = validate_and_normalize(p)
    assert abs(p2.drip_pct - 70.0) < 1e-9
    assert abs(p2.cash_pct - 20.0) < 1e-9
    assert abs(p2.stay_pct - 10.0) < 1e-9


def test_validate_off_sum_normalized():
    """sum=200 應被 normalize 回 100%."""
    p = _params(drip_pct=140, cash_pct=40, stay_pct=20)
    p2 = validate_and_normalize(p)
    assert abs(p2.drip_pct + p2.cash_pct + p2.stay_pct - 100.0) < 1e-9
    assert abs(p2.drip_pct - 70.0) < 1e-9


def test_validate_zero_sum_raises():
    p = _params(drip_pct=0, cash_pct=0, stay_pct=0)
    with pytest.raises(ValueError):
        validate_and_normalize(p)


def test_validate_negative_amount_raises():
    p = _params(amount_twd=-100.0)
    with pytest.raises(ValueError):
        validate_and_normalize(p)


def test_validate_unknown_fx_model_raises():
    p = _params(fx_model="garbage")
    with pytest.raises(ValueError):
        validate_and_normalize(p)


# ──────────────────────────────────────────────────────────────
# 三桶策略單獨驗證
# ──────────────────────────────────────────────────────────────
def test_drip_only_units_strictly_increasing():
    """DRIP=100% + NAV 零變化 → units 嚴格遞增（複利效果）."""
    p = _params(
        drip_pct=100, cash_pct=0, stay_pct=0,
        phase_script=[{"months": 12, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    df = run_single_simulation(p)
    diffs = df["units"].diff().dropna()
    assert (diffs > 0).all(), "DRIP=100% 時 units 月月遞增"
    assert df["cash_local"].iloc[-1] == 0
    assert df["stay_twd"].iloc[-1] == 0


def test_cash_only_units_constant():
    """CASH=100% → units 恆定 + cash_local 累積."""
    p = _params(
        drip_pct=0, cash_pct=100, stay_pct=0,
        phase_script=[{"months": 12, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    df = run_single_simulation(p)
    assert df["units"].nunique() == 1, "CASH=100% units 應恆定"
    assert df["cash_local"].iloc[-1] > 0
    assert df["stay_twd"].iloc[-1] == 0


def test_stay_only_zero_rate_linear():
    """STAY=100% + 利率 0% → stay_twd 線性累積（每月增量相同）."""
    p = _params(
        drip_pct=0, cash_pct=0, stay_pct=100,
        stay_yield_pct=0.0,
        phase_script=[{"months": 12, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    df = run_single_simulation(p)
    diffs = df.loc[df.index >= 2, "stay_twd"].diff().dropna()
    # 月增量標準差應極小（NAV 0 變化 → 月配息恆定 → 月增量恆定）
    assert diffs.std() < 0.5, f"利率 0% 時月增量應恆定，得 std={diffs.std():.4f}"


def test_stay_only_with_interest_compounds():
    """STAY=100% + 5% 年利率 → 後期月增量 > 前期（複利）."""
    p = _params(
        drip_pct=0, cash_pct=0, stay_pct=100,
        stay_yield_pct=5.0,
        phase_script=[{"months": 24, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    df = run_single_simulation(p)
    diffs = df["stay_twd"].diff().dropna()
    first_half = diffs[(diffs.index >= 2) & (diffs.index <= 12)].mean()
    second_half = diffs[(diffs.index >= 13) & (diffs.index <= 24)].mean()
    assert second_half > first_half, "複利應使後期月增量大於前期"


# ──────────────────────────────────────────────────────────────
# phase NAV 變化邏輯
# ──────────────────────────────────────────────────────────────
def test_phase_nav_changes_applied_correctly():
    """phase 切換 → NAV 變化率正確套用 + 切換瞬間 phase label 對齊."""
    p = _params(
        drip_pct=100, cash_pct=0, stay_pct=0,
        phase_script=[
            {"months": 2, "phase": "復甦", "monthly_nav_change_pct": 1.0},
            {"months": 2, "phase": "衰退", "monthly_nav_change_pct": -2.0},
        ],
    )
    df = run_single_simulation(p)
    # NAV: 10 → 10.10 → 10.201 → 9.99698 → 9.797
    nav_series = df["nav"].tolist()
    assert abs(nav_series[0] - 10.0) < 1e-3   # initial
    assert abs(nav_series[1] - 10.10) < 1e-3
    assert abs(nav_series[2] - 10.201) < 1e-3
    assert abs(nav_series[3] - 9.997) < 1e-2
    assert abs(nav_series[4] - 9.797) < 1e-2

    # phase label 對齊
    assert df.loc[1, "phase"] == "復甦"
    assert df.loc[2, "phase"] == "復甦"
    assert df.loc[3, "phase"] == "衰退"
    assert df.loc[4, "phase"] == "衰退"


# ──────────────────────────────────────────────────────────────
# FX 模型
# ──────────────────────────────────────────────────────────────
def test_fx_fixed_path_constant():
    p = _params(fx_model="fixed", initial_fx=32.0,
                phase_script=[{"months": 5, "phase": "擴張", "monthly_nav_change_pct": 0.0}])
    df = run_single_simulation(p)
    assert df["fx"].nunique() == 1
    assert abs(df["fx"].iloc[0] - 32.0) < 1e-6
    assert abs(df["fx"].iloc[-1] - 32.0) < 1e-6


def test_fx_linear_endpoints_correct():
    """linear 模型：第 0 月 = initial_fx；第 n_months 月 = fx_end_value."""
    p = _params(
        fx_model="linear",
        initial_fx=32.0,
        fx_end_value=35.0,
        phase_script=[{"months": 10, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    df = run_single_simulation(p)
    assert abs(df["fx"].iloc[0] - 32.0) < 1e-6
    assert abs(df["fx"].iloc[-1] - 35.0) < 1e-6
    # 中段線性：month 5 → 32 + 3 * 5/10 = 33.5
    assert abs(df.loc[5, "fx"] - 33.5) < 1e-6


def test_fx_random_runs_diverge_across_runs():
    """random 模型不同 seed 應產生不同 FX 路徑."""
    p = _params(
        fx_model="random",
        fx_volatility_pct=5.0,
        phase_script=[{"months": 12, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    df1 = run_single_simulation(p, seed=1)
    df2 = run_single_simulation(p, seed=2)
    assert df1["fx"].iloc[-1] != df2["fx"].iloc[-1]


# ──────────────────────────────────────────────────────────────
# Monte Carlo
# ──────────────────────────────────────────────────────────────
def test_monte_carlo_quantiles_p5_le_p50_le_p95():
    p = _params(
        fx_model="random",
        fx_volatility_pct=5.0,
        phase_script=[{"months": 12, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    result = run_monte_carlo(p, n_runs=100, seed=42)
    assert result["n_runs"] == 100
    assert result["terminal_quantiles"] is not None
    q = result["terminal_quantiles"]["total_twd"]
    assert q["p5"] <= q["p50"] <= q["p95"]
    assert q["std"] > 0  # random 模型應有變異


def test_monte_carlo_fixed_falls_back_single_run():
    """fx_model='fixed' 應退回單次模擬，terminal_quantiles=None."""
    p = _params(fx_model="fixed",
                phase_script=[{"months": 6, "phase": "擴張", "monthly_nav_change_pct": 0.0}])
    result = run_monte_carlo(p, n_runs=100)  # n_runs 應被忽略
    assert result["n_runs"] == 1
    assert result["terminal_quantiles"] is None
    assert len(result["paths_sample"]) == 1


def test_monte_carlo_paths_sample_capped_at_50():
    p = _params(
        fx_model="random",
        fx_volatility_pct=3.0,
        phase_script=[{"months": 6, "phase": "擴張", "monthly_nav_change_pct": 0.0}],
    )
    result = run_monte_carlo(p, n_runs=200, seed=7)
    assert len(result["paths_sample"]) <= 50, "paths_sample 應 ≤ 50 條（記憶體保護）"


# ──────────────────────────────────────────────────────────────
# summarize + 完整流程
# ──────────────────────────────────────────────────────────────
def test_summarize_returns_expected_keys():
    p = _params()
    df = run_single_simulation(p)
    s = summarize_simulation(df)
    expected = {"n_months", "amount_twd", "fund_value_twd", "cash_value_twd",
                "stay_twd", "total_twd", "total_return_pct", "cum_div_twd",
                "monthly_div_avg_twd", "fx_end"}
    assert expected.issubset(s.keys())


def test_full_default_4phase_simulation_runs():
    """跑預設 4 段 phase_script 完整流程 + 終值合理."""
    p = _params()
    df = run_single_simulation(p)
    total_months = sum(seg["months"] for seg in DEFAULT_PHASE_SCRIPT)
    assert df.index.max() == total_months
    assert df["total_twd"].iloc[-1] > 0
    # phase label 全 4 個都出現過
    phases_seen = set(df["phase"].unique())
    assert {"復甦", "擴張", "放緩", "衰退"}.issubset(phases_seen)


def test_total_twd_equals_sum_of_three_buckets():
    """每月 total_twd = fund_value_twd + cash_value_twd + stay_twd."""
    p = _params()
    df = run_single_simulation(p)
    diff = df["total_twd"] - (df["fund_value_twd"] + df["cash_value_twd"] + df["stay_twd"])
    # rounding tolerance: 各欄都 round 2 位 → 累計誤差 ≤ 1.0
    assert diff.abs().max() < 1.0


# ──────────────────────────────────────────────────────────────
# UI source-level（app.py + tab file）
# ──────────────────────────────────────────────────────────────
@pytest.mark.skip(
    reason="v19.130:配置模擬器 tab 已從 UI 移除(app.py:32 ARCHIVED 註解)。"
           "模組檔 ui/tab_allocation_simulator.py 保留作 orphan,業務邏輯仍在 services,"
           "但 app.py 不再 register tab_sim — 此 test 契約已失效。"
)
def test_app_py_registers_allocation_simulator_tab():
    src = (Path(__file__).parent / "app.py").read_text(encoding="utf-8")
    assert "render_allocation_simulator_tab" in src, "app.py 必須 import render"
    assert "💼 配置模擬器" in src, "app.py 必須含新 Tab label"
    assert "tab_sim" in src, "app.py 必須註冊 tab_sim 變數"


def test_tab_file_has_all_4_sections():
    src = (Path(__file__).parent / "ui" / "tab_allocation_simulator.py").read_text(encoding="utf-8")
    for sec in ("1️⃣ 基本設定", "2️⃣ 景氣劇本", "3️⃣ 配息分配", "4️⃣ FX 匯率模型"):
        assert sec in src, f"UI 缺少 section: {sec}"


def test_tab_file_imports_simulator_service():
    src = (Path(__file__).parent / "ui" / "tab_allocation_simulator.py").read_text(encoding="utf-8")
    assert "from services.allocation_simulator import" in src
    for sym in ("SimulationParams", "run_monte_carlo", "DEFAULT_PHASE_SCRIPT"):
        assert sym in src, f"UI 缺少 {sym} 引用"
