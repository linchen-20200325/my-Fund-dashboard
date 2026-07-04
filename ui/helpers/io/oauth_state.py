"""ui/helpers/oauth_state.py — OAuth 設定解析 + Google client（v18.136 從 app.py 搬入）

來自 app.py:912-963。包含：
- _gsa_secret / _sheet_id_secret  (secrets 讀取)
- _resolve_oauth_cfg()             (config 優先序)
- _oauth_cfg / _oauth_configured   (module-level 計算)
- _get_oauth_client()              (建 gspread client)
- OAuth callback handler           (URL ?code= 換 token)

Tab3 透過 `from ui.helpers.oauth_state import ...` 取，不再走 sys.modules hack。
"""
from __future__ import annotations

import streamlit as st

from infra.oauth import (
    OAuthError,
    build_credentials_from_tokens,
    decode_id_token_email,
    ensure_fresh_tokens,
    exchange_code_for_tokens,
    generate_state,
)
from repositories.policy_repository import get_gspread_client_from_oauth


def _safe_secret(key: str, default=None):
    """v18.136: Streamlit 1.45+ secrets 缺失時 st.secrets.get() raise
    StreamlitSecretNotFoundError；try/except 包住避免 module load 即崩
    （影響 test_app_module_level_imports_resolvable 等 smoke tests）。"""
    try:
        if hasattr(st, "secrets"):
            return st.secrets.get(key, default)
    except Exception:
        pass
    return default


_gsa_secret      = _safe_secret("google_service_account")
_sheet_id_secret = _safe_secret("POLICY_SHEET_ID", "")


def _resolve_oauth_cfg() -> "dict | None":
    """OAuth Client 配置取得：secrets 優先；缺則用 session_state 的 in-app 設定。"""
    _from_secrets = _safe_secret("google_oauth")
    if _from_secrets and _from_secrets.get("client_id") \
            and _from_secrets.get("client_secret") \
            and _from_secrets.get("redirect_uri"):
        return dict(_from_secrets)
    try:
        _from_session = st.session_state.get("custom_oauth_cfg")
    except Exception:
        _from_session = None
    if _from_session and _from_session.get("client_id") \
            and _from_session.get("client_secret") \
            and _from_session.get("redirect_uri"):
        return dict(_from_session)
    return None


_oauth_cfg = _resolve_oauth_cfg()
_oauth_configured = _oauth_cfg is not None


def refresh_oauth_state() -> bool:
    """v18.148: 重算 module-level _oauth_cfg / _oauth_configured。

    修 wizard 套用設定 no-op bug：原本兩者在 module import 時 snapshot 一次，
    使用者透過 in-app wizard 寫 `st.session_state["custom_oauth_cfg"]` 後
    `st.rerun()` 不會重 run module body → snapshot 永遠 stale → UI 永遠
    走 wizard 分支、登入按鈕永遠不亮。Caller（tab3 render 開頭 / app.py
    sidebar 渲染前）呼叫本函式可強制 re-resolve；之後 caller 自己
    `from ui.helpers.oauth_state import _oauth_configured, _oauth_cfg`
    重新拿 fresh 值即可。
    """
    global _oauth_cfg, _oauth_configured
    _oauth_cfg = _resolve_oauth_cfg()
    _oauth_configured = _oauth_cfg is not None
    return _oauth_configured


def get_login_state() -> str:
    """回傳本 session 專屬的 OAuth state（沒有就產生一個並存進 session_state）。

    修「登入互相踢掉」核心：每個瀏覽器 session 各有一組隨機 state，寫進 authorize URL；
    Google 回呼帶回同一 state，`handle_oauth_callback()` 只認 state 相符者 →
    別的 session / 分頁發起的授權碼不會被本 session 吞掉，反之亦然。
    產一次後在本 session 內固定（跨 rerun 穩定），登入成功後清除。
    """
    _s = st.session_state.get("_oauth_state")
    if not _s:
        _s = generate_state()
        st.session_state["_oauth_state"] = _s
    return _s


def _get_oauth_client():
    """從 session_state 的 tokens 建一個 gspread client，順便 ensure 過期前 refresh。"""
    toks = st.session_state.get("gsheet_tokens")
    if not toks or not _oauth_cfg:
        return None
    toks = ensure_fresh_tokens(dict(toks),
        _oauth_cfg["client_id"], _oauth_cfg["client_secret"])
    st.session_state["gsheet_tokens"] = toks
    creds = build_credentials_from_tokens(toks,
        _oauth_cfg["client_id"], _oauth_cfg["client_secret"])
    return get_gspread_client_from_oauth(creds)


def _should_reject_oauth_code(expected_state, got_state) -> bool:
    """v19.305 OAuth callback state 守門判斷（純函式，可單元測試）。

    user 2026-07-04 回報「登入了卻顯示沒登入、一直迴圈」。根因為 dff0c41
    (v19.301) 收緊的 state 檢查：「只要 URL 帶 state 就必須和本 session 的
    _oauth_state 完全相符」。但 Streamlit Cloud 在「整頁導去 Google 再導回」
    的過程會把本 session 重置成全新 session → _oauth_state 遺失成 None →
    每次導回都被判定不符 → 永遠拒絕換 token → 無限迴圈。
    （本檔 852cfb1 建檔時無此檢查、可正常登入；v19.301 後才壞 = regression。）

    修法（可用性優先，user 明確選擇）：只有「本 session 確實記得自己發起過
    OAuth（expected_state 有值）且回傳 state 不符」才拒絕——這仍保有
    session_state 存活時的跨 session 防搶碼保護。當 expected_state 為 None
    （session 於導回時遺失）→ 放行。

    取捨：放行 None 會重新打開「殘留/多分頁互相搶授權碼」窗口（v19.301 的
    修補對象）。但單一使用者情境下最壞只是自我踢除、可重按，遠優於「永遠
    登不進去」。
    """
    return bool(got_state and expected_state and got_state != expected_state)


def handle_oauth_callback() -> None:
    """OAuth callback：URL 帶 ?code=... 時自動換 token。

    app.py module body 在 sidebar 渲染前呼叫一次。
    """
    if not _oauth_configured:
        return
    _qp = st.query_params
    if "code" in _qp and "gsheet_tokens" not in st.session_state:
        # v19.305（user 2026-07-04「登入了卻顯示沒登入、一直迴圈」）：state 守門
        # 判斷抽成純函式 _should_reject_oauth_code（見其 docstring 完整取捨說明）。
        # 只在「本 session 記得發起過 OAuth 且回傳 state 不符」時拒；session_state
        # 於 Streamlit Cloud 導回遺失（_expected_state=None）時放行，避免無限迴圈。
        _expected_state = st.session_state.get("_oauth_state")
        _got_state = _qp.get("state")
        if _should_reject_oauth_code(_expected_state, _got_state):
            return  # 跨 session 保護（session_state 存活時照樣防搶碼）
        try:
            _tokens = exchange_code_for_tokens(
                _qp["code"], _oauth_cfg["client_id"],
                _oauth_cfg["client_secret"], _oauth_cfg["redirect_uri"])
            st.session_state["gsheet_tokens"] = _tokens
            st.session_state["gsheet_email"] = decode_id_token_email(_tokens)
            st.session_state.pop("_oauth_state", None)  # 用完即棄，下次登入重新產
            st.query_params.clear()
            _email = st.session_state.get("gsheet_email", "")
            st.success(f"✅ Google 登入成功{('：' + _email) if _email else ''}")
            st.rerun()
        except OAuthError as _oe:
            st.error(f"❌ OAuth 失敗：{_oe}")
