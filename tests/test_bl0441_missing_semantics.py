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


_UNKNOWN_CATS = [None, "", "   ", "任何", "無法對應的類別XYZ"]


@pytest.mark.parametrize("cat", _UNKNOWN_CATS)
def test_is_core_bucket_blank_or_unmapped_is_none(cat):
    """DEC-2026-10-24-09 第 2 點:類別空白／缺值／無法對應 → 未判定(None),不默認非 Core。"""
    from services.zscore_engine import is_core_bucket
    assert is_core_bucket(cat) is None


def _boom(_c):
    raise RuntimeError("x")


def test_is_core_bucket_exception_is_none(monkeypatch):
    import services.regime_fit as rf
    from services.zscore_engine import is_core_bucket
    monkeypatch.setattr(rf, "asset_bucket", _boom)
    assert is_core_bucket("科技股票型") is None


def _nav_hi():
    """非 Core 時會給「停利/減碼」的序列(末點拉高),用來證明未判定時**不再**產生該行動。"""
    return pd.Series([10.0] * 299 + [11.0], index=pd.bdate_range("2023-01-02", periods=300))


def _assert_rebalance_unknown(r):
    from services.zscore_engine import CORE_UNKNOWN_TEXT
    assert r["core_status"] == "unknown" and r["status"] == "core_unknown"
    assert r["applies"] is None                 # 不是 False(Core)也不是 True(可擇時)
    assert r["action"] is None and r["z"] is None
    assert CORE_UNKNOWN_TEXT in r["reason"]
    assert "stop_gain_z" not in r and "add_z" not in r   # 沒有拿非 Core 門檻去算


@pytest.mark.parametrize("cat", _UNKNOWN_CATS)
def test_rebalance_signal_unknown_category_no_action(cat):
    from services.zscore_engine import rebalance_signal
    _assert_rebalance_unknown(rebalance_signal(_nav_hi(), cat, None))


def test_rebalance_signal_classification_exception_no_action(monkeypatch):
    import services.regime_fit as rf
    from services.zscore_engine import rebalance_signal
    monkeypatch.setattr(rf, "asset_bucket", _boom)
    _assert_rebalance_unknown(rebalance_signal(_nav_hi(), "科技股票型", None))


def test_rebalance_signal_real_non_core_and_core_unchanged():
    """真非 Core 照舊給行動;真 Core 照舊 applies=False(與 d266bcf6 基線同值,見回報基線比對)。"""
    from services.zscore_engine import rebalance_signal
    r = rebalance_signal(_nav_hi(), "科技股票型", None)
    assert r["core_status"] == "non_core" and r["applies"] is True
    assert r["action"] == "停利/減碼" and r["z"] is not None and "未判定" not in r["reason"]
    lo = rebalance_signal(pd.Series([11.0] * 299 + [10.0],
                                    index=pd.bdate_range("2023-01-02", periods=300)), "科技股票型")
    assert lo["action"] == "加碼/逢低"
    c = rebalance_signal(_nav_hi(), "平衡型", None)
    assert c["applies"] is False and c["action"] is None and c["core_status"] == "core"


@pytest.mark.parametrize("cat", [None, "", "任何"])
def test_combine_action_unknown_never_hold_or_matrix_action(cat):
    """未判定 → combine_action 走既有「Z 不可用」分支(timing 'unknown'),不落 3×3 任一格、不是持有。"""
    from services.health.action import _MATRIX
    from services.zscore_engine import rebalance_signal
    h = compute_4d_health(tr1y_pct=10, adr_pct=4, sharpe=1.0, sigma_pct=8, fund_ccy="TWD")
    a = combine_action(h, rebalance_signal(_nav_hi(), cat, None))
    assert a["timing"] == "unknown" and a["timing"] not in ("na", "low", "mid", "high")
    assert a["action"] not in {v[0] for v in _MATRIX.values()}
    assert "分類未判定" in a["action"] and "NAV 有效點不足" not in a["action"]
    assert "持有" not in a["action"] and "加碼" not in a["action"] and "減碼" not in a["action"]
    # 對照:真 Core 仍是「內建配置」那一支(既有行為不變)
    core = combine_action(h, rebalance_signal(_nav_hi(), "平衡型", None))
    assert core["timing"] == "na" and "內建配置" in core["action"]


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


# ── 3b. ladder235 分類未判定 → 不給燈、不給加碼比例(DEC-2026-10-24-09)───────
def _ladder_nav():
    import numpy as np
    idx = pd.date_range("2022-01-03", periods=900, freq="B")
    return pd.Series(100 + np.sin(np.arange(900) / 20) * 8 + np.arange(900) * 0.01, index=idx)


def _ladder_nav_deep():
    """非 Core 時會亮加碼燈(燈三)的序列:末段急跌。"""
    import numpy as np
    idx = pd.date_range("2022-01-03", periods=600, freq="B")
    v = np.r_[np.linspace(100, 110, 560), np.linspace(110, 80, 40)]
    return pd.Series(v, index=idx)


def _assert_ladder_unknown(r):
    from services.zscore_engine import CORE_UNKNOWN_TEXT
    assert r["core_status"] == "unknown" and r["status"] == "core_unknown"
    assert r["lamp"] is None and r["emoji"] == "⬜"
    assert r["deploy_pct"] is None and r["deploy_pct"] != 0.0   # 未判定 ≠ 0% ≠ 巡航
    assert r["deploy_twd"] is None and r["z_bb"] is None and r["reasons"] == []
    assert CORE_UNKNOWN_TEXT in r["note"]


@pytest.mark.parametrize("cat", _UNKNOWN_CATS)
def test_ladder235_unknown_category_no_lamp(cat):
    from services.ladder235 import ladder_signal
    nav = _ladder_nav_deep()
    base = ladder_signal(nav, vix=32, reserve_twd=100_000, category="科技股票型")
    assert base["lamp"] == "燈三" and base["deploy_pct"] > 0 and base["deploy_twd"] > 0
    _assert_ladder_unknown(ladder_signal(nav, vix=32, reserve_twd=100_000, category=cat))


@pytest.mark.parametrize("mode", ["none", "raise", "bucket_raise"])
def test_ladder235_classification_failure_no_lamp(monkeypatch, mode):
    import services.regime_fit as rf
    import services.zscore_engine as ze
    from services.ladder235 import ladder_signal
    if mode == "bucket_raise":
        monkeypatch.setattr(rf, "asset_bucket", _boom)
    else:
        monkeypatch.setattr(ze, "is_core_bucket", (lambda _c: None) if mode == "none" else _boom)
    _assert_ladder_unknown(ladder_signal(_ladder_nav_deep(), vix=32, reserve_twd=100_000,
                                         category="科技股票型"))


def test_ladder235_real_non_core_and_core_unchanged():
    from services.ladder235 import ladder_signal
    nav = _ladder_nav()
    r = ladder_signal(nav, vix=20, category="科技股票型")
    assert r["core_status"] == "non_core" and r["status"] == "ok" and r["lamp"] is not None
    assert "未判定" not in (r.get("note") or "")
    c = ladder_signal(nav, vix=20, category="貨幣市場基金")
    assert c["status"] == "core" and c["core_status"] == "core" and c["lamp"] is None


def _grp_health_label_fn():
    import ast
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "ui/tab_fund_grp_health.py").read_text(encoding="utf-8")
    hits = [n for n in ast.walk(ast.parse(src))
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get" and isinstance(n.func.value, ast.Dict)
            and "lowvol" in [ast.literal_eval(k) for k in n.func.value.keys]]
    assert len(hits) == 1
    mapping = ast.literal_eval(hits[0].func.value)
    fallback = ast.literal_eval(hits[0].args[1])
    return lambda status: mapping.get(status, fallback)


def test_grp_health_column_shows_unknown_not_insufficient():
    from services.ladder235 import ladder_signal
    from services.zscore_engine import CORE_UNKNOWN_TEXT
    label = _grp_health_label_fn()
    r = ladder_signal(_ladder_nav_deep(), vix=32, category="")
    assert label(r["status"]) == CORE_UNKNOWN_TEXT
    assert label(r["status"]) not in (label("insufficient"), label("core"))


# ── 5. Tab2 健康總覽卡匯率維 wiring(DEC-2026-10-24-09 第 3 點)───────────────
def _tab2_src():
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / "ui/tab2_single_fund.py").read_text(encoding="utf-8")


def test_tab2_card_passes_fund_ccy_and_fx_cv():
    import ast
    tree = ast.parse(_tab2_src())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "compute_4d_health"]
    assert len(calls) == 1
    kws = {k.arg for k in calls[0].keywords}
    assert {"fund_ccy", "fx_cv_pct"} <= kws
    src = _tab2_src()
    # 幣別來源 = 同頁進階指標的既有資料流(moneydj_raw currency);不推估、不另設預設幣別
    assert '_g_ccy = str(mj_raw.get("currency") or "").strip()' in src
    assert "fx_regime_by_ccy as _fxr_card" in src


def test_tab2_card_fx_dimension_with_and_without_ccy():
    """有幣別(TWD)→ 匯率維 n/a 不進缺口;無幣別 → 誠實列為缺口(不推估);外幣+CV → 計分。"""
    kw = dict(tr1y_pct=8, adr_pct=5, sharpe=1.0, sigma_pct=8, ma_dir=None)
    twd = compute_4d_health(**kw, fund_ccy="TWD", fx_cv_pct=None)
    none_ccy = compute_4d_health(**kw, fund_ccy="", fx_cv_pct=None)
    usd = compute_4d_health(**kw, fund_ccy="USD", fx_cv_pct=1.0)
    assert twd["fx_risk_status"] == "n/a" and "fx_risk" not in twd["coverage"]["missing"]
    assert none_ccy["fx_risk_status"] == "missing" and "fx_risk" in none_ccy["coverage"]["missing"]
    assert usd["fx_risk_status"] == "scored" and usd["factors"]["fx_risk"] is not None


def test_tab2_unknown_branch_before_core_branch():
    src = _tab2_src()
    i_unk = src.index('if _rb.get("core_status") == "unknown":')
    i_core = src.index('elif not _rb.get("applies", True):')
    assert i_unk < i_core
