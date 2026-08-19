"""v19.480 稽核 PR-1:吃本金判定拒收「不可信報酬基準」→ ⚪ 資料不足(不報假 🔴)。

- B1 短窗**累積**含息(N 天窗口,非年化)vs 年化配息率 = 期間不對齊 → 拒判。
- B2 純 NAV(不含配息)被低估 → 拒判。
- 官方 wb01 / 還原含息 ≥300 天 → 照常判定(不受影響)。
"""
import pytest

from services.fund_total_return import (
    is_nav_only_1y_source,
    is_partial_window_1y_source,
    is_too_short_1y_source,
)
from services.health.dividend import check_eating_principal_1y_mk


# ── 來源辨識 helper ─────────────────────────────────────────────────────
def test_is_partial_window_matches_only_window_label():
    assert is_partial_window_1y_source("自算含息（僅 200 天窗口）") is True
    assert is_partial_window_1y_source("自算含息") is False           # 完整窗口 → 非短窗
    assert is_partial_window_1y_source("—（僅 90 天資料，不足以推算一年）") is False  # too-short 回 None,另處理
    assert is_partial_window_1y_source("MoneyDJ 官方") is False
    assert is_partial_window_1y_source("") is False


def test_is_nav_only_matches_no_dividend_label():
    assert is_nav_only_1y_source("自算（僅淨值，不含配息）") is True
    assert is_nav_only_1y_source("自算含息") is False
    assert is_nav_only_1y_source("MoneyDJ 官方") is False


def test_too_short_and_partial_window_are_distinct():
    # 兩種「短」要分得開:too-short 回 None(既有契約),partial-window 有值但期間不對齊
    assert is_too_short_1y_source("—（僅 90 天資料，不足以推算一年）") is True
    assert is_partial_window_1y_source("—（僅 90 天資料，不足以推算一年）") is False


# ── 端到端:check_eating_principal_1y_mk 拒判不可信基準 ──────────────────
def _grey(res):
    return res is not None and res.get("alert_level") == "grey" and not res.get("eating_principal")


def test_nav_only_source_refuses_verdict_not_red():
    """純 NAV +2% vs 配息 6% —— 修前會 2<6 → 🔴;修後應拒判 ⚪(不含配息不可信)。"""
    fund = {"metrics": {"ret_1y": 2.0, "annual_div_rate": 6.0}}   # 無 perf/ret_1y_total → 走 source#3
    res = check_eating_principal_1y_mk(fund)
    assert _grey(res), res
    assert "不含配息" in (res.get("_tr1y_method") or "")


def test_partial_window_source_refuses_verdict_not_red():
    """短窗累積含息(200 天)vs 年化配息 —— 期間不對齊 → 拒判 ⚪(無 ≥300 天還原可替補時)。"""
    fund = {"metrics": {"ret_1y_total": 3.0, "ret_1y_window_days": 200,
                        "annual_div_rate": 6.0}}
    res = check_eating_principal_1y_mk(fund)
    assert _grey(res), res
    assert "天窗口" in (res.get("_tr1y_method") or "")


def test_official_wb01_source_still_judges_normally():
    """官方 wb01 含息 8% vs 配息 6% → 不吃本金(綠),不受新 gate 影響。"""
    fund = {"perf": {"1Y": 8.0}, "perf_source": "wb01",
            "metrics": {"annual_div_rate": 6.0}, "moneydj_div_yield": 6.0}
    res = check_eating_principal_1y_mk(fund)
    assert res is not None and res.get("alert_level") in ("green", "yellow")
    assert res.get("eating_principal") is False


def test_official_wb01_genuine_eating_still_red():
    """官方 wb01 含息 1% vs 配息 8% → 真吃本金 → 仍 🔴(gate 不誤殺真紅燈)。"""
    fund = {"perf": {"1Y": 1.0}, "perf_source": "wb01",
            "metrics": {"annual_div_rate": 8.0}, "moneydj_div_yield": 8.0}
    res = check_eating_principal_1y_mk(fund)
    assert res is not None and res.get("eating_principal") is True
    assert res.get("alert_level") == "red"
