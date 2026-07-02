"""infra/oauth.py — Google OAuth 2.0 for in-app Google Sheets 連線（v11.0 從 oauth_helper.py 搬入）

設計原則（與 CLAUDE.md §2 §4 一致）：
- 純資料層：不直接 import streamlit；UI 整合由 app.py / ui/ 負責
- 例外統一包成 OAuthError，呼叫端只接這個
- 三函式覆蓋整個 flow：build_oauth_flow / fetch_token / build_credentials_from_token
- 含 refresh_token 自動續期：access_token 過期前 60s 主動 refresh

GCP 配置（一次性，由使用者完成，見 docs/OAUTH_SETUP.md）：
  1. GCP console → APIs & Services → Credentials → Create OAuth Client ID
  2. Application type: Web application
  3. Authorized redirect URIs 加入 Streamlit Cloud app URL（e.g.
     https://<app>.streamlit.app/）與本地開發 URL（e.g. http://localhost:8501/）
  4. 下載 client_secret.json，把 client_id / client_secret 放 secrets.toml：
     [google_oauth]
     client_id     = "..."
     client_secret = "..."
     redirect_uri  = "https://<app>.streamlit.app/"

v11.0 分層歸位：本檔屬於 Infrastructure Layer，純 HTTP OAuth flow，零業務邏輯。
向後相容：根目錄 oauth_helper.py 保留 `from infra.oauth import *` shim，
        E 階段收尾後 shim 刪除。
"""
from __future__ import annotations

from typing import Any
import time


# Scopes：Sheets 讀寫 + Drive 列檔 + Drive metadata（讓使用者能瀏覽既有 Sheet）
# v18.45 補 drive.metadata.readonly 讓 list_user_sheets 能列出 Drive 內所有試算表。
GOOGLE_OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"


class OAuthError(Exception):
    """所有 oauth flow 對外丟出的錯誤都用這個 class。"""


# ──────────────────────────────────────────────────────────────────────
# Step 1: 產生 authorize URL，給使用者按下登入按鈕跳轉
# ──────────────────────────────────────────────────────────────────────
def build_authorize_url(
    client_id: str,
    redirect_uri: str,
    state: str = "",
    scopes: list[str] | None = None,
) -> str:
    """組 Google OAuth authorize URL（離線存取 + 強制 consent，確保拿到 refresh_token）。"""
    import urllib.parse as _up
    if not client_id or not redirect_uri:
        raise OAuthError("client_id / redirect_uri 不可為空")
    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         " ".join(scopes or GOOGLE_OAUTH_SCOPES),
        "access_type":   "offline",      # 拿 refresh_token
        "prompt":        "select_account consent",  # v19.293: 強制帳號選擇器 + consent → 避免 Chrome 已登入帳號被自動套用導致帳號錯誤
        "include_granted_scopes": "true",
    }
    if state:
        params["state"] = state
    return f"{GOOGLE_AUTH_URL}?{_up.urlencode(params)}"


# ──────────────────────────────────────────────────────────────────────
# Step 2: 把 authorization code 換成 access_token + refresh_token
# ──────────────────────────────────────────────────────────────────────
def exchange_code_for_tokens(
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    """
    用 callback 回來的 code 換 token bundle。
    回傳：{access_token, refresh_token, expires_in, expires_at, scope, token_type}
    """
    import requests
    if not code:
        raise OAuthError("authorization code 不可為空")
    try:
        r = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     client_id,
                "client_secret": client_secret,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            },
            timeout=15,
        )
    except Exception as e:
        raise OAuthError(f"token exchange 網路失敗：{e}") from e

    if r.status_code != 200:
        raise OAuthError(f"token exchange 失敗 ({r.status_code})：{r.text[:200]}")

    tokens = r.json()
    if "access_token" not in tokens:
        raise OAuthError(f"token response 缺 access_token：{tokens}")
    tokens["expires_at"] = int(time.time()) + int(tokens.get("expires_in", 3600))
    return tokens


# ──────────────────────────────────────────────────────────────────────
# Step 3: 用 refresh_token 換新的 access_token（access_token 過期前呼叫）
# ──────────────────────────────────────────────────────────────────────
def refresh_access_token(
    refresh_token: str,
    client_id: str,
    client_secret: str,
) -> dict:
    """回傳新 token bundle（含 expires_at）。refresh_token 通常會被 Google 保留不換。"""
    import requests
    if not refresh_token:
        raise OAuthError("refresh_token 不可為空")
    try:
        r = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "refresh_token": refresh_token,
                "client_id":     client_id,
                "client_secret": client_secret,
                "grant_type":    "refresh_token",
            },
            timeout=15,
        )
    except Exception as e:
        raise OAuthError(f"refresh token 網路失敗：{e}") from e

    if r.status_code != 200:
        raise OAuthError(f"refresh token 失敗 ({r.status_code})：{r.text[:200]}")

    tokens = r.json()
    if "access_token" not in tokens:
        raise OAuthError(f"refresh response 缺 access_token：{tokens}")
    tokens["expires_at"]   = int(time.time()) + int(tokens.get("expires_in", 3600))
    tokens["refresh_token"] = tokens.get("refresh_token", refresh_token)  # Google 通常不換
    return tokens


# ──────────────────────────────────────────────────────────────────────
# Step 4: 把 tokens 變成 google.oauth2.credentials.Credentials 物件，給 gspread 用
# ──────────────────────────────────────────────────────────────────────
def build_credentials_from_tokens(
    tokens: dict,
    client_id: str,
    client_secret: str,
    scopes: list[str] | None = None,
) -> Any:
    """把 token dict 轉成 google.oauth2.credentials.Credentials（與 gspread.authorize 相容）。"""
    try:
        from google.oauth2.credentials import Credentials  # type: ignore
    except ImportError as e:
        raise OAuthError(
            f"google-auth 未安裝：{e}；請 `pip install google-auth google-auth-oauthlib`"
        ) from e

    if not tokens.get("access_token"):
        raise OAuthError("tokens 缺 access_token")

    return Credentials(
        token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=client_id,
        client_secret=client_secret,
        scopes=scopes or GOOGLE_OAUTH_SCOPES,
    )


def is_token_expired(tokens: dict, leeway_sec: int = 60) -> bool:
    """token 是否快過期（預設 60s 安全墊）。沒 expires_at 視為已過期。"""
    exp = tokens.get("expires_at")
    if not exp:
        return True
    return time.time() + leeway_sec >= exp


def ensure_fresh_tokens(
    tokens: dict,
    client_id: str,
    client_secret: str,
) -> dict:
    """若 access_token 快過期，自動 refresh；否則原樣回傳。"""
    if not is_token_expired(tokens):
        return tokens
    rt = tokens.get("refresh_token")
    if not rt:
        raise OAuthError("token 已過期且沒有 refresh_token，需要重新授權")
    return refresh_access_token(rt, client_id, client_secret)
