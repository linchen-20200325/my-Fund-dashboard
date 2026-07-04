"""v19.305 回歸網 — OAuth callback state 守門判斷。

user 2026-07-04 回報「已登入卻顯示沒登入、一直迴圈」。根因:dff0c41 (v19.301)
收緊 state 檢查為「只要 URL 帶 state 就必須和本 session 的 _oauth_state 完全相符」,
但 Streamlit Cloud 每次 OAuth 整頁導回都會重置 session → _oauth_state 遺失成 None
→ 永遠被判定不符 → 拒絕換 token → 無限迴圈。

本檔鎖住 v19.305 中間解:只有「本 session 確實記得發起過 OAuth(expected 有值)
且回傳 state 不符」才拒絕;expected 為 None(session 遺失)時放行,避免迴圈。
同時保留 session_state 存活時的跨 session 防搶碼保護。
"""
from __future__ import annotations

from ui.helpers.io.oauth_state import _should_reject_oauth_code


class TestOAuthStateGate:
    def test_lost_session_state_allows_exchange(self):
        """核心迴圈修正:Streamlit Cloud 導回後 session 重置 → expected=None,
        URL 帶 state → 放行(不拒),讓後續換 token 得以進行。"""
        assert _should_reject_oauth_code(None, "abc123") is False

    def test_matching_state_allows(self):
        """本 session 記得發起且 state 相符 → 放行。"""
        assert _should_reject_oauth_code("abc123", "abc123") is False

    def test_both_present_mismatch_rejects(self):
        """session_state 存活且回傳 state 不符 → 跨 session 防搶碼,拒。"""
        assert _should_reject_oauth_code("abc123", "xyz999") is True

    def test_no_got_state_allows(self):
        """URL 沒帶 state（got=None）→ 無從比對,不拒(交由後續流程處理)。"""
        assert _should_reject_oauth_code("abc123", None) is False

    def test_both_none_allows(self):
        """兩者皆 None（極端退化）→ 放行,不製造迴圈。"""
        assert _should_reject_oauth_code(None, None) is False

    def test_empty_strings_allow(self):
        """空字串視同無值 → 不拒（bool("") 為 False）。"""
        assert _should_reject_oauth_code("", "abc") is False
        assert _should_reject_oauth_code("abc", "") is False


class TestOAuthCallbackWiring:
    """守門判斷確實接在 handle_oauth_callback 上（避免 helper 存在但沒被呼叫）。"""

    def test_callback_uses_gate_helper(self):
        import inspect

        from ui.helpers.io import oauth_state

        src = inspect.getsource(oauth_state.handle_oauth_callback)
        assert "_should_reject_oauth_code(" in src, (
            "handle_oauth_callback 應改走 _should_reject_oauth_code 守門"
        )
        # v19.301 的舊嚴格寫法不得殘留（否則又會在 Streamlit Cloud 迴圈）
        assert "_got_state and _got_state != _expected_state" not in src
