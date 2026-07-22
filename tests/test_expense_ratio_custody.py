"""tests/test_expense_ratio_custody.py — v19.368 7/8:費用率升級(經理+保管 TER 估計)。

守:
- 兩費齊 → er = mgmt+custody,source="mgmt+custody_est"(比單經理費更接近真 TER)
- 僅經理費 → 原 v19.191 行為不變,source="mgmt_only_est"
- 顯式 expense_ratio / metrics.expense_ratio 優先(真值 > 估計,§2.1 分級精神)
- 壞值("N/A"/空)→ 顯式跳過不炸(§1)
- factors 加 source key 為 schema-additive(不影響既有 value/score/weight)
"""
from __future__ import annotations

import pytest

from services.portfolio_service import calc_fund_factor_score


def _fd(mgmt=None, custody=None):
    mj = {}
    if mgmt is not None:
        mj["mgmt_fee"] = mgmt
    if custody is not None:
        mj["custody_fee"] = custody
    return {"metrics": {}, "moneydj_raw": mj}


def _er_factor(fd, **kw):
    res = calc_fund_factor_score(fd, **kw)
    return (res.get("factors") or {}).get("ExpenseRatio")


def test_mgmt_plus_custody_estimate():
    f = _er_factor(_fd(mgmt="1.5%", custody="0.26%"))
    assert f is not None
    assert f["value"] == pytest.approx(1.76)
    assert f["source"] == "mgmt+custody_est"


def test_mgmt_only_unchanged_behavior():
    f = _er_factor(_fd(mgmt="1.5"))
    assert f is not None
    assert f["value"] == pytest.approx(1.5)
    assert f["source"] == "mgmt_only_est"


def test_explicit_expense_ratio_wins_over_estimate():
    f = _er_factor(_fd(mgmt="1.5", custody="0.3"), expense_ratio=0.85)
    assert f["value"] == pytest.approx(0.85)
    assert f["source"] == "metrics"


def test_bad_values_skipped_explicitly():
    assert _er_factor(_fd(mgmt="N/A", custody="abc")) is None   # 全壞 → 無因子,不炸
    f = _er_factor(_fd(mgmt="1.2", custody="N/A"))              # 保管壞 → 退單經理
    assert f["value"] == pytest.approx(1.2) and f["source"] == "mgmt_only_est"


def test_schema_additive_keys_present():
    f = _er_factor(_fd(mgmt="1.0", custody="0.2"))
    assert set(f.keys()) >= {"value", "score", "weight", "source"}
    assert f["weight"] == 10
