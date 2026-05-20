"""test_portfolio_load — v18.151 PR B.1 載入 helper 測試

只測 `count_unloaded_funds`（pure function 不涉 streamlit / network）；
`batch_load_unloaded_funds` 牽涉 st.status / fetch_fund_from_moneydj_url，
留 PR D smoke 測試補完。
"""
from __future__ import annotations

from unittest.mock import patch

import streamlit as st   # type: ignore  # 為了 patch session_state

from ui.helpers.portfolio_load import count_unloaded_funds


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
