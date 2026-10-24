"""BL-0441(DEC-2026-10-24-08):Missing ≠ 0 / False / 中性 / 安全 / 未觸發。

四項:4D 覆蓋缺口可見;eat_warn 三態;is_core_bucket 分類失敗 ≠ 非 Core;NDC 三態失敗原因可見。
不新增門檻/規則;只驗揭露與不冒充。
"""
from __future__ import annotations

import pandas as pd
import pytest

from services.health.action import combine_action
from services.health.grade import compute_4d_health


# ── 1. 4D 覆蓋缺口 ────────────────────────────────────────────────
def test_4d_full_vs_partial_coverage_visible():
    full = compute_4d_health(tr1y_pct=8, adr_pct=5, sharpe=1.0, sigma_pct=8, ma_dir="up",
                             fund_ccy="TWD")
    part = compute_4d_health(tr1y_pct=8, adr_pct=5, sharpe=1.0, sigma_pct=None, ma_dir=None)
    assert full["coverage"]["missing"] == []
    assert "volatility" in part["coverage"]["missing"]
    assert part["coverage"]["n_scored"] < part["coverage"]["n_applicable"]
    act = combine_action(part, {"applies": True, "z": 0.0, "action": "持有"})
    assert any(f.startswith("⬜ 評分覆蓋") and "波動" in f for f in act["flags"])
    act_full = combine_action(full, {"applies": True, "z": 0.0, "action": "持有"})
    assert not any(f.startswith("⬜ 評分覆蓋") for f in act_full["flags"])


def test_4d_coverage_flag_does_not_change_grade_or_quality():
    part = compute_4d_health(tr1y_pct=8, adr_pct=5, sharpe=1.0, sigma_pct=None)
    a = combine_action(part, {"applies": False})
    b = combine_action({k: v for k, v in part.items() if k != "coverage"}, {"applies": False})
    assert a["quality"] == b["quality"] and a["action"] == b["action"]


# ── 2. eat_warn 三態 ──────────────────────────────────────────────
def test_eat_warn_missing_is_none_not_false():
    h = compute_4d_health(tr1y_pct=None, adr_pct=None, sharpe=1.0, sigma_pct=8)
    assert h["factors"]["coverage"] is None
    assert h["eat_warn"] is None and h["eat_warn"] is not False
    assert h["eat_warn_status"] == "unknown"
    act = combine_action(h, {"applies": False})
    assert "⬜ 吃本金:資料未取得／無法判定" in act["flags"]
    assert "🔴 吃本金" not in act["flags"]


def test_eat_warn_true_and_real_false():
    warn = compute_4d_health(tr1y_pct=-10, adr_pct=12, sharpe=0.2, sigma_pct=8)
    ok = compute_4d_health(tr1y_pct=10, adr_pct=4, sharpe=1.0, sigma_pct=8)
    assert warn["eat_warn"] is True and warn["eat_warn_status"] == "warn"
    assert ok["eat_warn"] is False and ok["eat_warn_status"] == "ok"
    assert "🔴 吃本金" in combine_action(warn, {"applies": False})["flags"]
    flags_ok = combine_action(ok, {"applies": False})["flags"]
    assert "🔴 吃本金" not in flags_ok and not any("吃本金" in f for f in flags_ok)


# ── 3. is_core_bucket 三態 ────────────────────────────────────────
def test_is_core_bucket_valid_and_false():
    from services.zscore_engine import is_core_bucket
    assert is_core_bucket("平衡型") is True or is_core_bucket("多重資產") is True
    assert is_core_bucket("科技股票型") is False


def test_is_core_bucket_exception_is_none(monkeypatch):
    import services.regime_fit as rf
    from services.zscore_engine import is_core_bucket, rebalance_signal

    def _boom(_c):
        raise RuntimeError("x")
    monkeypatch.setattr(rf, "asset_bucket", _boom)
    assert is_core_bucket("任何") is None
    nav = pd.Series(range(100, 900), dtype=float)
    r = rebalance_signal(nav, "任何", None)
    assert r["core_status"] == "unknown"
    assert "是否 Core 未判定" in r["reason"]


def test_rebalance_signal_non_core_marked():
    from services.zscore_engine import rebalance_signal
    nav = pd.Series(range(100, 900), dtype=float)
    r = rebalance_signal(nav, "科技股票型", None)
    assert r["core_status"] == "non_core" and "未判定" not in r["reason"]


# ── 4. NDC 三態 ───────────────────────────────────────────────────
def test_ndc_status_from_result_states():
    from ui.helpers.macro.ndc import ndc_status_from_result
    assert ndc_status_from_result({"score_latest": 25})["status"] == "ok"
    assert ndc_status_from_result({"score_latest": 25})["score"] == 25
    u = ndc_status_from_result({"score_latest": None,
                                "error": "FinMind TaiwanBusinessIndicator 失敗:402"})
    assert u["status"] == "unavailable" and u["score"] is None
    n = ndc_status_from_result({"score_latest": None,
                                "error": "FinMind TaiwanBusinessIndicator 無景氣對策信號資料"})
    assert n["status"] == "no_data" and n["score"] is None
    assert ndc_status_from_result(None)["status"] == "unavailable"


def test_get_ndc_status_fetch_error(monkeypatch):
    import ui.helpers.macro.ndc as ndc

    def _boom():
        raise ConnectionError("down")
    monkeypatch.setattr(ndc, "_cached_ndc_score", _boom)
    st = ndc.get_ndc_status()
    # 有 streamlit(stub 或真)→ fetch_error;無 → unavailable。兩者皆非 ok、score 皆 None
    assert st["status"] in ("fetch_error", "unavailable") and st["score"] is None
    assert ndc.get_ndc_score() is None


@pytest.mark.parametrize("status", ["fetch_error", "unavailable", "no_data"])
def test_ndc_status_text_distinct(status):
    from ui.helpers.macro.ndc import NDC_STATUS_TEXT
    assert NDC_STATUS_TEXT[status] and NDC_STATUS_TEXT[status] != NDC_STATUS_TEXT["ok"]
    assert len({NDC_STATUS_TEXT[k] for k in ("fetch_error", "unavailable", "no_data")}) == 3


# ── 3b. ladder235 分類失敗揭露(燈號與非 Core 相同)───────────────
def _ladder_nav():
    import numpy as np
    idx = pd.date_range("2022-01-03", periods=900, freq="B")
    return pd.Series(100 + np.sin(np.arange(900) / 20) * 8 + np.arange(900) * 0.01, index=idx)


@pytest.mark.parametrize("mode", ["none", "raise"])
def test_ladder235_core_unknown_disclosed_lamp_unchanged(monkeypatch, mode):
    import services.zscore_engine as ze
    from services.ladder235 import ladder_signal
    nav = _ladder_nav()
    base = ladder_signal(nav, vix=20, category="科技股票型")
    assert base["core_status"] == "non_core"

    def _fake(_c):
        if mode == "raise":
            raise RuntimeError("x")
        return None
    monkeypatch.setattr(ze, "is_core_bucket", _fake)
    r = ladder_signal(nav, vix=20, category="科技股票型")
    assert r["core_status"] == "unknown"
    assert "是否 Core 未判定" in r["note"]
    for k in ("lamp", "status", "deploy_pct"):
        assert r.get(k) == base.get(k)
