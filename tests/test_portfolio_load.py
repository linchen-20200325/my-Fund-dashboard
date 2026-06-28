"""test_portfolio_load — v18.151 PR B.1 載入 helper 測試

只測 `count_unloaded_funds`（pure function 不涉 streamlit / network）；
`batch_load_unloaded_funds` 牽涉 st.status / fetch_fund_from_moneydj_url，
留 PR D smoke 測試補完。
"""
from __future__ import annotations

import streamlit as st   # type: ignore  # 直接 monkeypatch session_state

import types

from ui.helpers.portfolio_load import (
    count_unloaded_funds,
    reconcile_funds_with_ledgers,
    reuse_fund_info_by_code,
)


def _fake_ledger(code, currency, units, cost_unit, fx_avg, cost_unit_with_div):
    pos = types.SimpleNamespace(units=units, cost_unit=cost_unit, fx_avg=fx_avg,
                                cost_unit_with_div=cost_unit_with_div)
    return types.SimpleNamespace(fund_code=code, currency=currency, position=pos)


def _set_pf(funds: list[dict]) -> None:
    """直接設 session_state.portfolio_funds（streamlit headless 模式 OK）。"""
    # AppTest-free 簡化：直接 monkeypatch st.session_state
    if hasattr(st, "session_state"):
        try:
            st.session_state.portfolio_funds = funds
            return
        except Exception:
            pass
    # fallback：用 dict 模擬
    class _D(dict):
        def __getattr__(self, k): return self[k]
    setattr(st, "session_state", _D({"portfolio_funds": funds}))


def test_count_unloaded_funds_empty():
    _set_pf([])
    assert count_unloaded_funds() == (0, 0)


def test_count_unloaded_funds_all_loaded():
    _set_pf([
        {"code": "A", "loaded": True},
        {"code": "B", "loaded": True},
    ])
    assert count_unloaded_funds() == (0, 0)


def test_count_unloaded_funds_mixed():
    _set_pf([
        {"code": "A", "loaded": True},
        {"code": "B", "loaded": False},
        {"code": "C"},                  # 沒 loaded key = 未載入
    ])
    n_ent, n_uniq = count_unloaded_funds()
    assert n_ent == 2
    assert n_uniq == 2


def test_count_unloaded_funds_dedupes_same_code_across_policies():
    """同 code 跨多保單（不同 policy_id）只算 1 個 unique code。"""
    _set_pf([
        {"code": "FIDXEQI", "policy_id": "P1", "loaded": False},
        {"code": "FIDXEQI", "policy_id": "P2", "loaded": False},
        {"code": "ALLNATEC", "policy_id": "P1", "loaded": False},
    ])
    n_ent, n_uniq = count_unloaded_funds()
    assert n_ent == 3      # 3 entries
    assert n_uniq == 2     # 2 unique codes


def test_count_unloaded_funds_drops_empty_code():
    """空字串 code 不算 unique code。"""
    _set_pf([
        {"code": "", "loaded": False},
        {"code": "  ", "loaded": False},   # 純空白也視為空
        {"code": "OK", "loaded": False},
    ])
    n_ent, n_uniq = count_unloaded_funds()
    assert n_ent == 3
    assert n_uniq == 1


def test_count_unloaded_funds_handles_missing_session_state():
    """session_state 沒 portfolio_funds key → 安全回 (0, 0)。"""
    # 清掉 session_state
    if hasattr(st, "session_state"):
        try:
            st.session_state.pop("portfolio_funds", None)
        except Exception:
            pass
    assert count_unloaded_funds() == (0, 0)


# ── reuse_fund_info_by_code（跨帳本共用基金資訊）──

def test_reuse_hydrates_same_code_across_ledgers():
    """切換帳本：同 code 不同 policy_id，沿用上一本已載入的基金資訊、免重抓。"""
    prev = [{
        "code": "FIDXEQI", "policy_id": "P1", "loaded": True,
        "name": "富達世界", "series": [1, 2, 3], "metrics": {"sharpe": 1.2},
        "moneydj_raw": {"x": 1}, "dividends": [0.1], "risk_metrics": {"v": 2},
        "is_core": True, "currency": "USD",
    }]
    merged = [{
        "code": "FIDXEQI", "policy_id": "P9", "loaded": False,
        "invest_twd": 500, "currency": "",
    }]
    reused = reuse_fund_info_by_code(merged, prev)
    assert reused == ["FIDXEQI"]
    e = merged[0]
    assert e["loaded"] is True and e["load_error"] is None
    assert e["series"] == [1, 2, 3] and e["metrics"] == {"sharpe": 1.2}
    assert e["currency"] == "USD"          # 空 currency 被沿用值補上
    assert e["policy_id"] == "P9" and e["invest_twd"] == 500  # 持倉仍走新帳本


def test_reuse_skips_different_code():
    """新標的（上一本沒載過）維持 loaded=False，留給按鈕抓。"""
    prev = [{"code": "AAA", "loaded": True, "series": [1]}]
    merged = [{"code": "BBB", "loaded": False}]
    reused = reuse_fund_info_by_code(merged, prev)
    assert reused == []
    assert merged[0].get("loaded") is False


def test_reuse_ignores_errored_or_unloaded_source():
    """上一本是 load_error 或未載入 → 不能當資料來源。"""
    prev = [
        {"code": "AAA", "loaded": True, "load_error": "boom", "series": [1]},
        {"code": "BBB", "loaded": False, "series": [2]},
    ]
    merged = [
        {"code": "AAA", "loaded": False},
        {"code": "BBB", "loaded": False},
    ]
    assert reuse_fund_info_by_code(merged, prev) == []
    assert all(not m.get("loaded") for m in merged)


def test_reuse_leaves_already_loaded_untouched():
    """已 loaded 的 merged 條目（kept）不被動到。"""
    prev = [{"code": "AAA", "loaded": True, "series": [9]}]
    merged = [{"code": "AAA", "loaded": True, "series": [1, 2]}]
    assert reuse_fund_info_by_code(merged, prev) == []
    assert merged[0]["series"] == [1, 2]   # 沒被覆蓋


def test_reuse_does_not_blank_currency_with_empty_source():
    """來源 currency 為空時，不可把 merged 既有 currency 洗掉。"""
    prev = [{"code": "AAA", "loaded": True, "series": [1], "currency": ""}]
    merged = [{"code": "AAA", "loaded": False, "currency": "TWD"}]
    reuse_fund_info_by_code(merged, prev)
    assert merged[0]["currency"] == "TWD"


def test_reuse_handles_empty_previous():
    """首次載入（上一本為空）→ 無可沿用，全部維持未載入。"""
    merged = [{"code": "AAA", "loaded": False}]
    assert reuse_fund_info_by_code(merged, None) == []
    assert merged[0].get("loaded") is False


# ── reconcile_funds_with_ledgers（讀取齊全：spine 補齊 + 成本回填）──

def test_reconcile_adds_missing_spine_from_ledger():
    """帳本有、portfolio_funds 沒有的基金 → 補成 spine 條目並帶成本基礎。"""
    funds = []
    tl = {"P1::ACTI71": _fake_ledger("ACTI71", "美元", 1780.94, 8.67, 32.35, 6.9655)}
    out, n_added = reconcile_funds_with_ledgers(funds, tl)
    assert n_added == 1
    e = out[0]
    assert e["code"] == "ACTI71" and e["policy_id"] == "P1"
    assert e["avg_nav"] == 8.67 and e["fx_avg"] == 32.35
    assert e["units"] == 1780.94 and e["avg_nav_with_div"] == 6.9655
    assert e["loaded"] is False


def test_reconcile_backfills_existing_fund_missing_cost():
    """portfolio_funds 已有 spine 但缺成本（avg_nav/fx=None）→ 從帳本回填。"""
    funds = [{"code": "ACTI71", "policy_id": "P1", "invest_twd": 499509,
              "avg_nav": None, "fx_avg": None}]
    tl = {"P1::ACTI71": _fake_ledger("ACTI71", "美元", 1780.94, 8.67, 32.35, 6.9655)}
    out, n_added = reconcile_funds_with_ledgers(funds, tl)
    assert n_added == 0
    assert out[0]["avg_nav"] == 8.67 and out[0]["fx_avg"] == 32.35
    assert out[0]["invest_twd"] == 499509   # 既有設定不動


def test_reconcile_does_not_overwrite_existing_cost():
    """portfolio_funds 已有 avg_nav → 不被帳本覆蓋。"""
    funds = [{"code": "ACTI71", "policy_id": "P1", "avg_nav": 9.99, "fx_avg": 30.0}]
    tl = {"P1::ACTI71": _fake_ledger("ACTI71", "美元", 1.0, 8.67, 32.35, 6.9655)}
    out, n_added = reconcile_funds_with_ledgers(funds, tl)
    assert out[0]["avg_nav"] == 9.99 and out[0]["fx_avg"] == 30.0


def test_reconcile_empty_ledgers_is_noop():
    funds = [{"code": "A", "policy_id": "P1"}]
    out, n_added = reconcile_funds_with_ledgers(funds, {})
    assert n_added == 0 and out == funds


def test_reuse_handles_pandas_series_value():
    """v18.197 回歸：series 是 pandas Series → 不可用 `v not in (None,'')`
    （會回 Series → bool() 觸發 truth-value-ambiguous ValueError）。"""
    import pandas as pd
    s = pd.Series([1.0, 2.0, 3.0])
    prev = [{"code": "AAA", "loaded": True, "name": "X",
             "series": s, "metrics": {"sharpe": 1.0}, "currency": "USD"}]
    merged = [{"code": "AAA", "policy_id": "P2", "loaded": False, "currency": ""}]
    reused = reuse_fund_info_by_code(merged, prev)   # 不應拋 ValueError
    assert reused == ["AAA"]
    assert merged[0]["series"] is s            # series 直接沿用
    assert merged[0]["loaded"] is True
    assert merged[0]["currency"] == "USD"      # 空字串被沿用值補上
