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
    ensure_fresh_tokens,
    exchange_code_for_tokens,
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


def handle_oauth_callback() -> None:
    """OAuth callback：URL 帶 ?code=... 時自動換 token。

    app.py module body 在 sidebar 渲染前呼叫一次。
    """
    if not _oauth_configured:
        return
    _qp = st.query_params
    if "code" in _qp and "gsheet_tokens" not in st.session_state:
        try:
            _tokens = exchange_code_for_tokens(
                _qp["code"], _oauth_cfg["client_id"],
                _oauth_cfg["client_secret"], _oauth_cfg["redirect_uri"])
            st.session_state["gsheet_tokens"] = _tokens
            st.query_params.clear()
            st.success("✅ Google 登入成功")
            st.rerun()
        except OAuthError as _oe:
            st.error(f"❌ OAuth 失敗：{_oe}")
