"""tab1_macro._render_tw_local_dashboard 單元測試 — Phase v19.25。

A+B Step 2b：驗證 v19.25 新 UI 函式：
- 4 fetcher mock → v19.23 純函式 → 雙欄渲染
- 任一 fetcher 失敗仍 graceful 不爆
- indicators 為 None / 空 dict → early return 不渲染
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ui import tab1_macro


# ────────────────────────────────────────────────────────────────────────
# Helpers — mock fetcher 回傳 schema 與 mock streamlit 元件
# ────────────────────────────────────────────────────────────────────────
def _ok_ndc(score: float = 26.0, prev: float = 24.0):
    return {'score_latest': score, 'score_prev': prev, 'score_prev2': 22.0,
            'trend': [20, 22, 24, 24, prev, score],
            'inflection': '🟢 連3月升',
            'date_latest': '2026-05-01', 'source': 'FinMind', 'error': None}


def _ok_pmi(val: float = 52.5, prev: float = 50.8):
    return {'value': val, 'prev': prev, 'trend': [49, 50, 51, 51, prev, val],
            'inflection': '🟢 擴張加速',
            'date_latest': '2026-05-01', 'source': 'FinMind', 'error': None}


def _ok_export(val: float = 8.2, prev: float = 6.5):
    return {'value': val, 'prev': prev, 'trend': [-2, 0, 3, 5, prev, val],
            'inflection': '🟢 正成長加速',
            'date_latest': '2026-05-01', 'source': 'FinMind', 'error': None}


def _ok_fii(consec: int = 4, prev_streak: int = -3):
    return {'consec_days': consec, 'prev_streak': prev_streak, 'reversed': True,
            'inflection': '🚀 連3賣→買（拐點）',
            'date_latest': '2026-06-05', 'source': 'FinMind', 'error': None}


def _err_block(msg: str = 'FinMind 抓取失敗'):
    return {'value': None, 'prev': None, 'trend': [], 'inflection': '—',
            'date_latest': None, 'source': None, 'error': msg,
            'score_latest': None, 'score_prev': None, 'score_prev2': None,
            'consec_days': None, 'prev_streak': None, 'reversed': False}


@pytest.fixture
def stub_st(monkeypatch):
    """把 tab1_macro 內 st.* 替換成 MagicMock，避免真的呼叫 Streamlit runtime。"""
    fake = MagicMock()
    fake.columns.return_value = (MagicMock(), MagicMock())
    fake.container.return_value.__enter__ = lambda *_a, **_k: MagicMock()
    fake.container.return_value.__exit__  = lambda *_a, **_k: False
    fake.expander.return_value.__enter__  = lambda *_a, **_k: MagicMock()
    fake.expander.return_value.__exit__   = lambda *_a, **_k: False
    monkeypatch.setattr(tab1_macro, 'st', fake)
    return fake


_FAKE_INDICATORS = {
    'CPI':      {'value': 2.4, 'prev': 2.6},
    'FED_RATE': {'value': 4.25, 'prev': 4.50},
    'VIX':      {'value': 18.5},
}

# 32 字元假 FRED key（≥30 字元才會通過 AppTest 保護門）
_FAKE_FRED_KEY = 'a' * 32


# ════════════════════════════════════════════════════════════════════════════
# §1 Early return guard
# ════════════════════════════════════════════════════════════════════════════
class TestEarlyReturn:
    def test_none_indicators_returns_silently(self, stub_st):
        tab1_macro._render_tw_local_dashboard(None)
        # 無 indicators → 應該完全不呼叫 markdown / columns
        stub_st.markdown.assert_not_called()
        stub_st.columns.assert_not_called()

    def test_empty_dict_returns_silently(self, stub_st):
        tab1_macro._render_tw_local_dashboard({})
        stub_st.markdown.assert_not_called()


# ════════════════════════════════════════════════════════════════════════════
# §2 Happy path — 4 fetcher 全成功
# ════════════════════════════════════════════════════════════════════════════
class TestHappyPath:
    def test_renders_section_heading_and_dual_columns(self, stub_st):
        with patch('repositories.macro_tw_local_repository.fetch_ndc_signal_history',
                   return_value=_ok_ndc()), \
             patch('repositories.macro_tw_local_repository.fetch_tw_pmi_local',
                   return_value=_ok_pmi()), \
             patch('repositories.macro_tw_local_repository.fetch_tw_export_yoy',
                   return_value=_ok_export()), \
             patch('repositories.macro_tw_local_repository.fetch_foreign_consecutive_days',
                   return_value=_ok_fii()):
            tab1_macro._render_tw_local_dashboard(_FAKE_INDICATORS, _FAKE_FRED_KEY)

        # 必須呼叫 columns(2) 雙欄
        stub_st.columns.assert_called_with(2)
        # heading 必須包含關鍵字「台股本地視角」
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '台股本地視角' in joined
        assert '12M' in joined
        assert '1Q' in joined


# ════════════════════════════════════════════════════════════════════════════
# §3 Graceful degrade — fetcher 全 error 仍渲染不爆
# ════════════════════════════════════════════════════════════════════════════
class TestGracefulDegrade:
    def test_all_fetchers_error_still_renders(self, stub_st):
        with patch('repositories.macro_tw_local_repository.fetch_ndc_signal_history',
                   return_value=_err_block('NDC fail')), \
             patch('repositories.macro_tw_local_repository.fetch_tw_pmi_local',
                   return_value=_err_block('PMI fail')), \
             patch('repositories.macro_tw_local_repository.fetch_tw_export_yoy',
                   return_value=_err_block('Export fail')), \
             patch('repositories.macro_tw_local_repository.fetch_foreign_consecutive_days',
                   return_value=_err_block('FII fail')):
            tab1_macro._render_tw_local_dashboard(_FAKE_INDICATORS, _FAKE_FRED_KEY)

        # 仍應 render heading（v19.23 純函式對全 None 會回 ⚪ 資料不足）
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '台股本地視角' in joined

    def test_fetcher_exception_warns_and_returns(self, stub_st):
        """fetcher 直接 raise 例外（極端情境）→ st.warning + 結束。"""
        with patch('repositories.macro_tw_local_repository.fetch_ndc_signal_history',
                   side_effect=RuntimeError('boom')):
            tab1_macro._render_tw_local_dashboard(_FAKE_INDICATORS, _FAKE_FRED_KEY)
        stub_st.warning.assert_called_once()
        # 不應該繼續渲染 heading
        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '台股本地視角' not in joined


# ════════════════════════════════════════════════════════════════════════════
# §4 Missing CPI/Fed → MK signal None, classify 仍能跑
# ════════════════════════════════════════════════════════════════════════════
class TestPartialIndicators:
    def test_missing_cpi_fed_still_works(self, stub_st):
        partial = {'VIX': {'value': 18.5}}  # 無 CPI / FED_RATE
        with patch('repositories.macro_tw_local_repository.fetch_ndc_signal_history',
                   return_value=_ok_ndc()), \
             patch('repositories.macro_tw_local_repository.fetch_tw_pmi_local',
                   return_value=_ok_pmi()), \
             patch('repositories.macro_tw_local_repository.fetch_tw_export_yoy',
                   return_value=_ok_export()), \
             patch('repositories.macro_tw_local_repository.fetch_foreign_consecutive_days',
                   return_value=_ok_fii()):
            tab1_macro._render_tw_local_dashboard(partial, _FAKE_FRED_KEY)

        md_calls = [c.args[0] for c in stub_st.markdown.call_args_list
                    if c.args and isinstance(c.args[0], str)]
        joined = ' '.join(md_calls)
        assert '台股本地視角' in joined  # 仍能渲染（NDC + PMI 撐住 regime）


# ════════════════════════════════════════════════════════════════════════════
# §5 AppTest 環境保護門
# ════════════════════════════════════════════════════════════════════════════
class TestAppTestGuard:
    def test_short_fred_key_skips_rendering(self, stub_st):
        """fred_api_key < 30 字元（AppTest 場景）→ 完全跳過渲染與 fetcher。"""
        with patch('repositories.macro_tw_local_repository.fetch_ndc_signal_history') as _m:
            tab1_macro._render_tw_local_dashboard(_FAKE_INDICATORS, 'short-key')
            _m.assert_not_called()
        stub_st.markdown.assert_not_called()

    def test_empty_fred_key_skips_rendering(self, stub_st):
        with patch('repositories.macro_tw_local_repository.fetch_ndc_signal_history') as _m:
            tab1_macro._render_tw_local_dashboard(_FAKE_INDICATORS, '')
            _m.assert_not_called()
        stub_st.markdown.assert_not_called()
