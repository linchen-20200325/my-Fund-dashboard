"""tests/test_real_ter_fundclear.py — v19.370:真實 TER(FundClear fetcher)。

背景:v19.368 只有「經理費+保管費」估計(mgmt+custody_est)。本輪補抽官方揭露的
年度總費用率(TER / 經常性費用 / OCF)——FundClear GetFundBasicInfo top-level
`expense_ratio` 或 MoneyDJ 基本頁 `total_expense_ratio` —— 作為真值,依 §2.1 分級
精神優先於估計。

守:
- 揭露 TER(top-level)> 估計:source="disclosed_ter"
- 揭露 TER(moneydj_raw.total_expense_ratio)> 估計:source="disclosed_ter"
- metrics.expense_ratio 仍為最高優先(真值中的真值,不被 disclosed 蓋)
- 越界(>10% 或 <=0)→ §3.2 顯式剔除 → 退回估計(不炸,§1)
- 髒值("N/A"/空)→ 退回估計
- 無任何揭露 → v19.368 mgmt+custody_est 行為不變(零回歸)
- 單位:百分比(1.76% → 1.76,不可存 ratio 0.0176)
- 可用性 helper 與評分器同源(✅/❌ ↔ 納入 1-1)
- L1 source-lock:5 抽取點不被未來重構掉線
"""
from __future__ import annotations

import pytest

from services.portfolio_service import calc_fund_factor_score, get_factor_availability


def _fd(*, top_ter=None, mj_ter=None, mgmt=None, custody=None, metrics_er=None):
    mj = {}
    if mj_ter is not None:
        mj["total_expense_ratio"] = mj_ter
    if mgmt is not None:
        mj["mgmt_fee"] = mgmt
    if custody is not None:
        mj["custody_fee"] = custody
    fd = {"metrics": {}, "moneydj_raw": mj}
    if top_ter is not None:
        fd["expense_ratio"] = top_ter
    if metrics_er is not None:
        fd["metrics"]["expense_ratio"] = metrics_er
    return fd


def _er(fd, **kw):
    return (calc_fund_factor_score(fd, **kw).get("factors") or {}).get("ExpenseRatio")


# ── 揭露 TER 優先於估計 ────────────────────────────────────────────────
def test_toplevel_disclosed_ter_beats_estimate():
    # 有 mgmt+custody 估計(=1.76),但 FundClear 揭露真 TER 0.95 → 用真值
    f = _er(_fd(top_ter=0.95, mgmt="1.5", custody="0.26"))
    assert f["value"] == pytest.approx(0.95)
    assert f["source"] == "disclosed_ter"


def test_moneydj_total_expense_ratio_beats_estimate():
    f = _er(_fd(mj_ter="0.90%", mgmt="1.5", custody="0.26"))
    assert f["value"] == pytest.approx(0.90)
    assert f["source"] == "disclosed_ter"


def test_metrics_expense_ratio_still_highest():
    # metrics 真值(source="metrics")不被 disclosed 蓋
    f = _er(_fd(metrics_er=0.80, top_ter=0.95, mgmt="1.5", custody="0.26"))
    assert f["value"] == pytest.approx(0.80)
    assert f["source"] == "metrics"


# ── 邊界:越界 / 髒值 → 退回估計(§1 不炸)────────────────────────────
def test_out_of_range_disclosed_falls_back_to_estimate():
    f = _er(_fd(top_ter=15.0, mgmt="1.5", custody="0.26"))   # 15% 不合理 → 剔除
    assert f["value"] == pytest.approx(1.76)
    assert f["source"] == "mgmt+custody_est"


def test_zero_disclosed_falls_back():
    f = _er(_fd(top_ter=0, mgmt="1.2"))                       # 0% 不合理 → 剔除
    assert f["value"] == pytest.approx(1.2)
    assert f["source"] == "mgmt_only_est"


def test_garbage_disclosed_falls_back():
    f = _er(_fd(top_ter="N/A", mj_ter="", mgmt="1.5", custody="0.26"))
    assert f["value"] == pytest.approx(1.76)
    assert f["source"] == "mgmt+custody_est"


def test_no_disclosure_v19_368_behavior_unchanged():
    f = _er(_fd(mgmt="1.5", custody="0.26"))
    assert f["value"] == pytest.approx(1.76)
    assert f["source"] == "mgmt+custody_est"


# ── 單位陷阱:百分比,非 ratio ─────────────────────────────────────────
def test_percent_unit_not_ratio():
    f = _er(_fd(top_ter="1.76%"))
    assert f["value"] == pytest.approx(1.76)          # 1.76(%),不是 0.0176
    assert 0 < f["value"] <= 10


# ── 可用性 helper 與評分器同源 ─────────────────────────────────────────
def test_availability_mirrors_disclosed_source():
    assert get_factor_availability(_fd(top_ter=0.95))["ExpenseRatio"] is True
    assert get_factor_availability(_fd(mj_ter="0.9%"))["ExpenseRatio"] is True
    # 越界揭露 + 無 fallback → 不可用(與評分器一致)
    assert get_factor_availability(_fd(top_ter=15.0))["ExpenseRatio"] is False


# ── L1 source-lock:抽取點不被未來重構掉線 ────────────────────────────
def test_l1_extraction_points_wired():
    src = open("repositories/fund/sources.py", encoding="utf-8").read()
    # 3 rows_map 站點 + FundClear JSON expense_ratio
    assert src.count("total_expense_ratio") >= 3
    assert 'meta["expense_ratio"]' in src              # FundClear GetFundBasicInfo
    orch = open("repositories/fund/fund_orchestration.py", encoding="utf-8").read()
    assert "total_expense_ratio" in orch              # orchestration rows_map 站點
