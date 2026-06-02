"""test_tab_crisis_backtest_gating.py — v18.261 Phase 1/3/4 cache 化單元測試

驗 user 反饋「壓跑訊號回看、跑網格 就沒反應了」的根因 fix：Phase 1 主按鈕原本
click-only 一次性 gating，按 Phase 3/4 button 觸發 rerun 後 Phase 1 button → False
→ 提前 return → Phase 3/4 section 不再渲染。fix 用 session_state cache。
"""
from __future__ import annotations


# AppTest 不在這支，直接驗 helper purity + invalidation 副作用
from ui.tab_crisis_backtest import (
    _PHASE1_CACHE_KEY,
    _PHASE3_CACHE_KEY,
    _GRID_CACHE_KEY,
    _phase1_params_signature,
    _invalidate_phase1_chain,
)


def test_params_signature_deterministic():
    sig1 = _phase1_params_signature("SPX", -10, 10, "00940")
    sig2 = _phase1_params_signature("SPX", -10, 10, "00940")
    assert sig1 == sig2


def test_params_signature_changes_on_any_field():
    base = _phase1_params_signature("SPX", -10, 10, "00940")
    assert base != _phase1_params_signature("TWII", -10, 10, "00940")
    assert base != _phase1_params_signature("SPX", -15, 10, "00940")
    assert base != _phase1_params_signature("SPX", -10, 5, "00940")
    assert base != _phase1_params_signature("SPX", -10, 10, "00657")


def test_params_signature_strips_fund_key_whitespace():
    """user 在 text_input 前後多打空格不該被視為新參數。"""
    assert _phase1_params_signature("SPX", -10, 10, "  00940  ") == \
           _phase1_params_signature("SPX", -10, 10, "00940")


def test_params_signature_empty_fund_key_normalizes_to_blank():
    """fund_key = None / "" / "  " 應視為同一狀態。"""
    a = _phase1_params_signature("SPX", -10, 10, "")
    b = _phase1_params_signature("SPX", -10, 10, "   ")
    c = _phase1_params_signature("SPX", -10, 10, None)
    assert a == b == c


def test_invalidate_clears_all_three_cache_keys(monkeypatch):
    """Phase 1 參數變動 → 連帶清掉 Phase 3 / Phase 4 cache。"""
    import streamlit as st

    class _FakeSS(dict):
        def pop(self, key, default=None):
            return dict.pop(self, key, default)

    fake_ss = _FakeSS({
        _PHASE1_CACHE_KEY: {"some": "data"},
        _PHASE3_CACHE_KEY: {"more": "data"},
        _GRID_CACHE_KEY: {"grid": "stuff"},
        "_unrelated": "should remain",
    })
    monkeypatch.setattr(st, "session_state", fake_ss)

    _invalidate_phase1_chain()

    assert _PHASE1_CACHE_KEY not in fake_ss
    assert _PHASE3_CACHE_KEY not in fake_ss
    assert _GRID_CACHE_KEY not in fake_ss
    assert fake_ss.get("_unrelated") == "should remain"


def test_invalidate_safe_on_empty_state(monkeypatch):
    """state 已是空時 invalidate 不該 raise。"""
    import streamlit as st

    class _FakeSS(dict):
        def pop(self, key, default=None):
            return dict.pop(self, key, default)

    fake_ss = _FakeSS()
    monkeypatch.setattr(st, "session_state", fake_ss)
    _invalidate_phase1_chain()  # 不該 raise
    assert len(fake_ss) == 0


def test_cache_keys_are_distinct_strings():
    """三個 cache key 必須互不相同，否則會互相覆蓋。"""
    keys = {_PHASE1_CACHE_KEY, _PHASE3_CACHE_KEY, _GRID_CACHE_KEY}
    assert len(keys) == 3
    for k in keys:
        assert isinstance(k, str) and k.startswith("_crisis_")
