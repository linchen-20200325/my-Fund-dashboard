"""infra/personal_oauth.py — 新 B UI 專用的 Google Personal OAuth 安全基礎（L0 Infra）。

規格來源：客戶 2026-10-26 正式裁示
`docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md`
第 1～4、9、10 節（J-1 最小 scope、J-2 state／PKCE fail closed、J-3 token／logout／
切換帳號、J-10 namespace 分離、J-7 不 fallback、J-9 error taxonomy）。

與舊 `infra/oauth.py` 的關係：
- **刻意不 import、也不修改** `infra/oauth.py` 與 `ui/helpers/io/oauth_state.py`。
  舊模組供舊 UI（app.py／ui/）使用，舊 UI 退役前維持現狀；本模組只給新 B UI。
- Google endpoint 值與舊模組一致（authorize／token），另加 revoke endpoint。
- 舊模組的 scope 含讀寫 `spreadsheets` 與 `drive.file`、授權網址帶
  `include_granted_scopes=true`、state 在 session 遺失時放行、無 PKCE、登出不 revoke
  —— 本模組全部反過來（見下方各段）。

本模組不 import streamlit；session_state 一律由呼叫端注入（任何 MutableMapping 皆可）。

────────────────────────────────────────────────────────────────────────
為什麼 pending store 放在 server runtime（模組層 dict），不放 session_state
────────────────────────────────────────────────────────────────────────
Streamlit 的 OAuth 整頁導回（Google → redirect_uri）會建立**新的** session，
導回前寫在 `st.session_state` 的 state／code_verifier 會遺失。舊 UI 因此在 session
遺失時放行 state 檢查（fail open）—— 裁示 J-2 明文禁止。

本模組把 **pending 的 code_verifier** 放在 server runtime 的一次性 store：
- key ＝ 高熵隨機 state（`secrets.token_urlsafe(32)`），value ＝ (code_verifier, expires_at)。
- TTL 600 秒；`consume_pending` 一律 pop（一次性，重放必失敗）。
- 找不到／過期／state 為空或 None → `AUTH_STATE_INVALID`（fail closed）。
- 上限 `PENDING_MAX` 筆：新增前先清過期；仍滿則拒絕新增並拋錯，不淘汰任何有效 state。
- **只存 pending 的 verifier，絕不存 token 或使用者身分。** token 只存呼叫端注入的
  session_state（namespace `b_oauth.`）。

這符合裁示第 2 節「`code_verifier` 只短期存在 server/session runtime」：短期（600 秒）、
一次性、只在記憶體、不寫 log／Sheet／repo／檔案。
⚠️ **單 process 假設**：pending store 只存在單一 process 的記憶體。多 process（多 worker／
多 replica）時，導回落到別的 process 會要求重新登入（`AUTH_STATE_INVALID`），**不放行**。

────────────────────────────────────────────────────────────────────────
授權範圍與帳號身分（總管 2026-10-26 依裁示第 1～4 節推導）
────────────────────────────────────────────────────────────────────────
- Google 回傳的 granted scope 只要含四項最小 scope 以外的任何權限，或回應根本沒帶
  scope 欄位（無法確認）→ 拒絕登入：嘗試 revoke 該 token、清 session、拋 `PERMISSION_DENIED`。
- 帳號身分不用未驗簽的 id_token；exchange 成功後以 access token 呼叫 Google OpenID
  userinfo endpoint，要求 `sub`、`email`、`email_verified is True`，否則 revoke 新 token 並拋錯。
- 缺少四項中任何一項必要 scope 同樣拒絕（revoke＋`PERMISSION_DENIED`）。

────────────────────────────────────────────────────────────────────────
待確認登入（資安稽核 A1／A2／B1，總管 2026-10-26 裁定）
────────────────────────────────────────────────────────────────────────
pending store 必須跨 session（導回會建立新 session），所以「持有效 state＋code 的人」
可以在別人的 session 完成 callback（login CSRF／授權碼注入）。緩解：
- callback 成功**不直接啟用**：tokens 與 userinfo 身分先存成「待確認登入」
  （`KEY_PENDING_LOGIN`，TTL `PENDING_LOGIN_TTL_SEC`）。`get_tokens`／`ensure_fresh`
  一律看不到待確認的 token。
- `confirm_pending_login` 才升為正式登入（若有舊正式登入，先 revoke 舊 token 再替換）；
  `reject_pending_login` revoke 並清除；過期自動 revoke＋清除。
- callback 先驗 state，失敗即拋、**不碰 session**；新登入被拒（scope／身分）時只 revoke
  新 token、清掉待確認登入，不動既有正式登入（不能被拿來強制登出）。
- 同一 session 重複 `begin_authorization` 會重用尚未過期的 pending state（per-session 上限 1）。
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.parse
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass
from typing import Any

import requests

from infra.config import get_secret
from shared import ui_v2_error_codes as ec

# ──────────────────────────────────────────────────────────────────────
# 常數
# ──────────────────────────────────────────────────────────────────────
#: 第一階段最小權限 scope（裁示第 1 節 J-1）。不含讀寫 `spreadsheets`、不含 `drive.file`。
PERSONAL_OAUTH_SCOPES: tuple[str, ...] = (
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
)

#: 與 `infra/oauth.py` 同值（刻意不 import 舊模組）。
GOOGLE_AUTH_URL: str = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL: str = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE_URL: str = "https://oauth2.googleapis.com/revoke"
GOOGLE_USERINFO_URL: str = "https://openidconnect.googleapis.com/v1/userinfo"

#: 部署 secrets 內的 OAuth client 區塊名（與舊模組 docs/OAUTH_SETUP.md 同一區塊）。
SECRETS_SECTION: str = "google_oauth"

PENDING_TTL_SEC: int = 600
PENDING_MAX: int = 1000
TOKEN_REFRESH_LEEWAY_SEC: int = 60
PENDING_LOGIN_TTL_SEC: int = 300

HTTP_TIMEOUT_SEC: int = 15
REVOKE_TIMEOUT_SEC: int = 10

#: RFC 7636 §4.1：code_verifier 長度 43～128，字元集 [A-Z] / [a-z] / [0-9] / "-" / "." / "_" / "~"。
PKCE_VERIFIER_MIN_LEN: int = 43
PKCE_VERIFIER_MAX_LEN: int = 128
PKCE_ALLOWED_CHARS: frozenset[str] = frozenset(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)

# ── session_state key（裁示第 4 節 J-10：專屬 namespace，不重用舊 key）────────
#: 舊 UI 使用的 `gsheet_tokens`／`gsheet_email`／`_oauth_state` 本模組一律不碰。
SESSION_PREFIX: str = "b_oauth."
KEY_TOKENS: str = SESSION_PREFIX + "tokens"
KEY_ACCOUNT_SUB: str = SESSION_PREFIX + "account_sub"
KEY_ACCOUNT_EMAIL: str = SESSION_PREFIX + "account_email"
KEY_GRANTED_SCOPES: str = SESSION_PREFIX + "granted_scopes"
#: Active／Pending Sheet（裁示第 8 節 J-5）。本批只定義常數並在登出／切換帳號時清除，
#: Active 邏輯由後續批次實作。
KEY_ACTIVE_SHEET: str = SESSION_PREFIX + "active_sheet"
KEY_PENDING_SHEET: str = SESSION_PREFIX + "pending_sheet"
#: 本 session 已登記、尚未用掉的 OAuth state（B1：per-session 重用，不重複登記）。
KEY_AUTH_PENDING_STATE: str = SESSION_PREFIX + "pending_state"
KEY_AUTH_PENDING_EXPIRES: str = SESSION_PREFIX + "pending_state_expires_at"
#: 待確認登入（A1）：{"tokens", "sub", "email", "expires_at"}。get_tokens 不讀這個 key。
KEY_PENDING_LOGIN: str = SESSION_PREFIX + "pending_login"

SESSION_KEYS: tuple[str, ...] = (
    KEY_TOKENS,
    KEY_ACCOUNT_SUB,
    KEY_ACCOUNT_EMAIL,
    KEY_GRANTED_SCOPES,
    KEY_ACTIVE_SHEET,
    KEY_PENDING_SHEET,
    KEY_AUTH_PENDING_STATE,
    KEY_AUTH_PENDING_EXPIRES,
    KEY_PENDING_LOGIN,
)


# ──────────────────────────────────────────────────────────────────────
# 錯誤
# ──────────────────────────────────────────────────────────────────────
class PersonalOAuthError(Exception):
    """本模組對外唯一的例外。`code` 必屬 `shared.ui_v2_error_codes.ALL_ERROR_CODES`。

    message 只放人類可讀說明，不得含 token、client secret、code_verifier、授權碼。
    """

    def __init__(self, code: str, message: str = "") -> None:
        if code not in ec.ALL_ERROR_CODES:
            raise ValueError(f"unknown ui_v2 error code: {code!r}")
        super().__init__(message or code)
        self.code = code
        self.message = message or code

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"


# ──────────────────────────────────────────────────────────────────────
# PKCE（S256）
# ──────────────────────────────────────────────────────────────────────
def generate_code_verifier() -> str:
    """產生 RFC 7636 code_verifier（86 字元，base64url 字元集為 RFC 允許字元的子集）。"""
    verifier = secrets.token_urlsafe(64)
    if not (PKCE_VERIFIER_MIN_LEN <= len(verifier) <= PKCE_VERIFIER_MAX_LEN):
        raise PersonalOAuthError(ec.UNAVAILABLE, "PKCE verifier 長度異常")
    if not set(verifier) <= PKCE_ALLOWED_CHARS:
        raise PersonalOAuthError(ec.UNAVAILABLE, "PKCE verifier 字元集異常")
    return verifier


def code_challenge_s256(verifier: str) -> str:
    """challenge ＝ base64url(sha256(ascii(verifier)))，去掉 padding。"""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


# ──────────────────────────────────────────────────────────────────────
# Pending store（server runtime，一次性；理由見檔頭）
# ──────────────────────────────────────────────────────────────────────
#: state -> (code_verifier, expires_at_epoch_sec)。只存 pending verifier，不存 token／身分。
_PENDING: dict[str, tuple[str, float]] = {}
_PENDING_LOCK = threading.Lock()


def _now(now: float | None) -> float:
    return time.time() if now is None else float(now)


def _purge_expired_locked(ts: float) -> None:
    expired = [s for s, (_v, exp) in _PENDING.items() if exp <= ts]
    for s in expired:
        del _PENDING[s]


def register_pending(now: float | None = None) -> tuple[str, str]:
    """登記一筆 pending 授權，回傳 (state, code_verifier)。

    滿額（清掉過期後仍 ≥ PENDING_MAX）→ 拒絕新增，拋 `UNAVAILABLE`；不淘汰任何有效 state。
    """
    ts = _now(now)
    verifier = generate_code_verifier()
    state = secrets.token_urlsafe(32)
    expires_at = ts + PENDING_TTL_SEC
    with _PENDING_LOCK:
        _purge_expired_locked(ts)
        if len(_PENDING) >= PENDING_MAX:
            raise PersonalOAuthError(
                ec.UNAVAILABLE, "目前登入請求過多，請稍後再試"
            )
        if state in _PENDING:  # 機率可忽略；仍 fail closed，不覆蓋
            raise PersonalOAuthError(ec.UNAVAILABLE, "登入請求產生失敗，請重試")
        _PENDING[state] = (verifier, expires_at)
    return state, verifier


def consume_pending(state: Any, now: float | None = None) -> str:
    """一次性取出 state 對應的 code_verifier（一律 pop）。

    state 為 None／空字串／非字串／未知／已過期 → `AUTH_STATE_INVALID`（fail closed）。
    """
    if not isinstance(state, str) or not state:
        raise PersonalOAuthError(ec.AUTH_STATE_INVALID, "登入驗證資訊缺失，請重新登入")
    ts = _now(now)
    with _PENDING_LOCK:
        entry = _PENDING.pop(state, None)
        _purge_expired_locked(ts)
    if entry is None:
        raise PersonalOAuthError(ec.AUTH_STATE_INVALID, "登入驗證資訊不符或已使用，請重新登入")
    verifier, expires_at = entry
    if expires_at <= ts:
        raise PersonalOAuthError(ec.AUTH_STATE_INVALID, "登入驗證已逾時，請重新登入")
    return verifier


def _peek_pending(state: str, ts: float) -> str | None:
    """不消耗地讀出仍有效的 verifier（僅供同 session 重用授權網址）。"""
    with _PENDING_LOCK:
        entry = _PENDING.get(state)
    if entry is None or entry[1] <= ts:
        return None
    return entry[0]


def _discard_pending(state: Any) -> None:
    if isinstance(state, str) and state:
        with _PENDING_LOCK:
            _PENDING.pop(state, None)


def pending_count() -> int:
    """目前 pending 筆數（診斷／測試用；不揭露內容）。"""
    with _PENDING_LOCK:
        return len(_PENDING)


# ──────────────────────────────────────────────────────────────────────
# Client 設定：只准來自部署 secrets（裁示第 2 節；不讀 session 內使用者貼入的設定）
# ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class ClientConfig:
    client_id: str
    client_secret: str
    redirect_uri: str

    def __repr__(self) -> str:  # 避免 client_secret 出現在 log／例外訊息
        return f"ClientConfig(client_id={self.client_id!r}, redirect_uri={self.redirect_uri!r})"


def load_client_config() -> ClientConfig:
    """讀部署 secrets 的 `[google_oauth]`；任一欄缺 → `UNAVAILABLE`（部署未設定 Google 登入）。"""
    section = get_secret(SECRETS_SECTION, None)
    if not isinstance(section, Mapping):
        raise PersonalOAuthError(ec.UNAVAILABLE, "部署端尚未設定 Google 登入")
    vals: dict[str, str] = {}
    missing: list[str] = []
    for field in ("client_id", "client_secret", "redirect_uri"):
        v = section.get(field)
        if isinstance(v, str) and v.strip():
            vals[field] = v.strip()
        else:
            missing.append(field)
    if missing:
        raise PersonalOAuthError(
            ec.UNAVAILABLE, f"部署端 Google 登入設定缺欄位：{', '.join(missing)}"
        )
    return ClientConfig(**vals)


# ──────────────────────────────────────────────────────────────────────
# Authorize
# ──────────────────────────────────────────────────────────────────────
def build_authorize_url(cfg: ClientConfig, state: str, code_challenge: str) -> str:
    """組授權網址。不帶 `include_granted_scopes`（裁示第 1 節）。"""
    params = {
        "client_id": cfg.client_id,
        "redirect_uri": cfg.redirect_uri,
        "response_type": "code",
        "scope": " ".join(PERSONAL_OAUTH_SCOPES),
        "access_type": "offline",
        "prompt": "select_account consent",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    return f"{GOOGLE_AUTH_URL}?{urllib.parse.urlencode(params)}"


def begin_authorization(
    session_state: MutableMapping, now: float | None = None
) -> dict[str, str]:
    """開始一次登入：讀 client 設定 → 登記（或重用）pending → 回傳 {authorize_url, state}。

    同一 session 若已有未過期、且仍在 store 內的 pending state → 重用，不新登記（B1）。
    code_verifier 不回傳給呼叫端（只留在 pending store）。
    """
    ts = _now(now)
    cfg = load_client_config()
    prev_state = session_state.get(KEY_AUTH_PENDING_STATE)
    prev_exp = session_state.get(KEY_AUTH_PENDING_EXPIRES)
    if (isinstance(prev_state, str) and prev_state
            and isinstance(prev_exp, (int, float)) and ts < prev_exp):
        verifier = _peek_pending(prev_state, ts)
        if verifier is not None:
            return {
                "authorize_url": build_authorize_url(cfg, prev_state, code_challenge_s256(verifier)),
                "state": prev_state,
            }
    state, verifier = register_pending(ts)
    session_state[KEY_AUTH_PENDING_STATE] = state
    session_state[KEY_AUTH_PENDING_EXPIRES] = ts + PENDING_TTL_SEC
    return {
        "authorize_url": build_authorize_url(cfg, state, code_challenge_s256(verifier)),
        "state": state,
    }


# ──────────────────────────────────────────────────────────────────────
# Token endpoint 共用
# ──────────────────────────────────────────────────────────────────────
def _post_token_endpoint(
    data: dict[str, str],
    *,
    rejected_code: str = ec.AUTH_STATE_INVALID,
    reject_any_401: bool = False,
) -> dict[str, Any]:
    """POST token endpoint 並分類錯誤；不吞例外（§1）。訊息不含回應 body（可能含敏感值）。

    Google 明確拒絕（400/401 + `invalid_grant`；`reject_any_401` 時任何 401）→ `rejected_code`；
    網路失敗 → `NETWORK_ERROR`；其他非 200（含 5xx）→ `UPSTREAM_ERROR`。
    """
    try:
        r = requests.post(GOOGLE_TOKEN_URL, data=data, timeout=HTTP_TIMEOUT_SEC)
    except requests.exceptions.RequestException as e:
        raise PersonalOAuthError(
            ec.NETWORK_ERROR, f"連線 Google 失敗（{type(e).__name__}）"
        ) from e

    status = int(getattr(r, "status_code", 0) or 0)
    try:
        payload = r.json()
    except (ValueError, json.JSONDecodeError):
        payload = None

    if status != 200:
        err = payload.get("error") if isinstance(payload, dict) else None
        err = err if isinstance(err, str) else ""
        if (status in (400, 401) and err == "invalid_grant") or (reject_any_401 and status == 401):
            raise PersonalOAuthError(
                rejected_code, "Google 拒絕這組授權（無效、已使用或已撤銷），請重新登入"
            )
        safe_err = err if err.replace("_", "").isalnum() else ""
        raise PersonalOAuthError(
            ec.UPSTREAM_ERROR,
            f"Google token endpoint 回應異常（HTTP {status}{', ' + safe_err if safe_err else ''}）",
        )

    if not isinstance(payload, dict):
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "Google token 回應不是 JSON 物件")
    return payload


def _normalize_token_payload(payload: dict[str, Any], now: float) -> dict[str, Any]:
    access_token = payload.get("access_token")
    if not isinstance(access_token, str) or not access_token:
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "Google token 回應缺 access_token")
    expires_in = payload.get("expires_in")
    try:
        expires_in_sec = int(expires_in)
    except (TypeError, ValueError):
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "Google token 回應缺 expires_in") from None
    if expires_in_sec <= 0:
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "Google token 回應 expires_in 非正數")
    tokens: dict[str, Any] = {
        "access_token": access_token,
        "expires_at": int(now) + expires_in_sec,
        "token_type": payload.get("token_type", ""),
        "scope": payload.get("scope", ""),
    }
    rt = payload.get("refresh_token")
    if isinstance(rt, str) and rt:
        tokens["refresh_token"] = rt
    return tokens


_ALLOWED_SCOPES: frozenset[str] = frozenset(PERSONAL_OAUTH_SCOPES)


def _scope_problem(tokens: Mapping[str, Any]) -> str | None:
    """回傳拒絕理由；授權範圍恰為四項最小 scope 時回 None。

    scope 欄位缺失／非字串／空 → 無法確認（拒絕）；多出任何權限 → 拒絕；缺任何一項 → 拒絕。
    """
    scope = tokens.get("scope")
    if not isinstance(scope, str) or not scope.strip():
        return "無法確認 Google 授權範圍，為確保唯讀已拒絕登入"
    granted = set(scope.split())
    excess = sorted(granted - _ALLOWED_SCOPES)
    if excess:
        return "Google 授權範圍超出唯讀（多了：" + "、".join(excess) + "），已拒絕登入"
    missing = sorted(_ALLOWED_SCOPES - granted)
    if missing:
        return "Google 授權範圍缺少必要的唯讀權限（缺：" + "、".join(missing) + "），已拒絕登入"
    return None


def _token_to_revoke(tokens: Mapping[str, Any]) -> str | None:
    t = tokens.get("refresh_token") or tokens.get("access_token")
    return t if isinstance(t, str) and t else None


def _revoke_token(token: str) -> LogoutResult:
    """POST revoke endpoint；失敗只回報，不拋例外。"""
    try:
        r = requests.post(
            GOOGLE_REVOKE_URL,
            data={"token": token},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=REVOKE_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException:
        return LogoutResult(True, False, ec.NETWORK_ERROR)
    except Exception:  # noqa: BLE001 — 撤銷失敗只回報，呼叫端仍須完成本機清除
        return LogoutResult(True, False, ec.UPSTREAM_ERROR)
    if int(getattr(r, "status_code", 0) or 0) == 200:
        return LogoutResult(True, True, None)
    return LogoutResult(True, False, ec.UPSTREAM_ERROR)


def _revoke_tokens(tokens: Mapping[str, Any]) -> LogoutResult:
    token = _token_to_revoke(tokens)
    if token is None:
        return LogoutResult(revoke_attempted=False, revoke_confirmed=False)
    return _revoke_token(token)


def fetch_verified_identity(access_token: str) -> tuple[str, str]:
    """以 access token 呼叫 OpenID userinfo；回傳 (sub, email)。

    要求 `sub`、`email` 為非空字串且 `email_verified is True`，否則 `AUTH_STATE_INVALID`；
    網路失敗 `NETWORK_ERROR`；401／403 `AUTH_STATE_INVALID`；其他非 200 或非 JSON `UPSTREAM_ERROR`。
    """
    try:
        r = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=HTTP_TIMEOUT_SEC,
        )
    except requests.exceptions.RequestException as e:
        raise PersonalOAuthError(
            ec.NETWORK_ERROR, f"連線 Google 帳號資訊失敗（{type(e).__name__}）"
        ) from e
    status = int(getattr(r, "status_code", 0) or 0)
    if status in (401, 403):
        raise PersonalOAuthError(ec.AUTH_STATE_INVALID, "Google 拒絕提供帳號資訊，請重新登入")
    if status != 200:
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, f"Google 帳號資訊回應異常（HTTP {status}）")
    try:
        data = r.json()
    except (ValueError, json.JSONDecodeError):
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "Google 帳號資訊回應不是 JSON") from None
    if not isinstance(data, dict):
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "Google 帳號資訊回應不是 JSON 物件")
    sub, email = data.get("sub"), data.get("email")
    if not (isinstance(sub, str) and sub and isinstance(email, str) and email
            and data.get("email_verified") is True):
        raise PersonalOAuthError(ec.AUTH_STATE_INVALID, "Google 帳號身分無法確認，請重新登入")
    return sub, email


# ──────────────────────────────────────────────────────────────────────
# Callback：一次性 state → PKCE token exchange
# ──────────────────────────────────────────────────────────────────────
def exchange_code(code: Any, state: Any, now: float | None = None) -> dict[str, Any]:
    """先 consume state（fail closed），再以對應 verifier 換 token。

    state 檢查一定先做 —— 即使 code 缺失也會先把 state 消耗掉，避免被重放。
    """
    ts = _now(now)
    verifier = consume_pending(state, ts)
    if not isinstance(code, str) or not code:
        raise PersonalOAuthError(ec.AUTH_REQUIRED, "Google 沒有回傳授權碼，請重新登入")
    cfg = load_client_config()
    payload = _post_token_endpoint({
        "code": code,
        "client_id": cfg.client_id,
        "client_secret": cfg.client_secret,
        "redirect_uri": cfg.redirect_uri,
        "grant_type": "authorization_code",
        "code_verifier": verifier,
    })
    return _normalize_token_payload(payload, ts)


def complete_authorization(
    session_state: MutableMapping, code: Any, state: Any, now: float | None = None
) -> dict[str, str]:
    """callback：驗 state → exchange → scope 檢查 → userinfo 身分 → 存成「待確認登入」。

    - state 不合法／exchange 失敗 → 直接拋錯，**不碰 session**（A2）。
    - scope 不合（多、缺、無法確認）→ revoke 新 token、清掉待確認登入、拋 `PERMISSION_DENIED`。
    - 身分驗證失敗 → revoke 新 token、清掉待確認登入、拋對應錯誤。
    - 上述拒絕都**不動既有正式登入**（不能被拿來強制登出）。
    - 成功 → **不啟用**，只存待確認登入（TTL `PENDING_LOGIN_TTL_SEC`），回傳 {"sub", "email"}；
      不回傳 token。須由 `confirm_pending_login` 確認後才成為正式登入（A1）。
    """
    ts = _now(now)
    tokens = exchange_code(code, state, ts)
    problem = _scope_problem(tokens)
    if problem is not None:
        _revoke_tokens(tokens)
        _drop_pending_login(session_state)
        raise PersonalOAuthError(ec.PERMISSION_DENIED, problem)
    try:
        sub, email = fetch_verified_identity(tokens["access_token"])
    except PersonalOAuthError:
        _revoke_tokens(tokens)
        _drop_pending_login(session_state)
        raise
    _drop_pending_login(session_state)  # 取代舊的待確認登入時一律 revoke
    session_state[KEY_PENDING_LOGIN] = {
        "tokens": dict(tokens),
        "sub": sub,
        "email": email,
        "expires_at": ts + PENDING_LOGIN_TTL_SEC,
    }
    return {"sub": sub, "email": email}


def _drop_pending_login(session_state: MutableMapping) -> LogoutResult:
    """revoke 待確認登入的 token 並移除該 key；沒有待確認登入時不做事。"""
    pending = session_state.get(KEY_PENDING_LOGIN)
    if KEY_PENDING_LOGIN in session_state:
        del session_state[KEY_PENDING_LOGIN]
    if isinstance(pending, Mapping) and isinstance(pending.get("tokens"), Mapping):
        return _revoke_tokens(pending["tokens"])
    return LogoutResult(revoke_attempted=False, revoke_confirmed=False)


def get_pending_login(session_state: MutableMapping, now: float | None = None) -> dict[str, Any] | None:
    """待確認登入的身分資訊（{"sub", "email", "expires_at"}，不含 token）。

    已過期 → 自動 revoke＋清除並回 None。
    """
    pending = session_state.get(KEY_PENDING_LOGIN)
    if not isinstance(pending, Mapping):
        return None
    exp = pending.get("expires_at")
    if not isinstance(exp, (int, float)) or exp <= _now(now):
        _drop_pending_login(session_state)
        return None
    return {"sub": pending.get("sub"), "email": pending.get("email"), "expires_at": exp}


def confirm_pending_login(session_state: MutableMapping, now: float | None = None) -> dict[str, str]:
    """把待確認登入升為正式登入，回傳 {"sub", "email"}。

    ⚠️ UI 契約：呼叫前，Settings UI **必須**讓使用者看見待確認的 email
    （例如「以 <email> 登入？［確認］［取消］」），並由使用者**明確按下確認**才可呼叫。
    不得自動呼叫 —— 這是抵擋 login CSRF／授權碼注入的唯一關卡（A1）。

    沒有待確認登入或已過期 → `AUTH_STATE_INVALID`（過期者先 revoke＋清除）。
    若本 session 已有正式登入 → 先 revoke 舊 token，再清除本 namespace（含 Active／Pending
    Sheet）並換上新登入；不沿用舊 Active 驗證狀態。
    """
    ts = _now(now)
    pending = session_state.get(KEY_PENDING_LOGIN)
    if not isinstance(pending, Mapping) or not isinstance(pending.get("tokens"), Mapping):
        raise PersonalOAuthError(ec.AUTH_STATE_INVALID, "沒有待確認的登入，請重新登入")
    exp = pending.get("expires_at")
    if not isinstance(exp, (int, float)) or exp <= ts:
        _drop_pending_login(session_state)
        raise PersonalOAuthError(ec.AUTH_STATE_INVALID, "登入確認已逾時，請重新登入")
    tokens = dict(pending["tokens"])
    sub, email = pending.get("sub"), pending.get("email")
    del session_state[KEY_PENDING_LOGIN]
    old = get_tokens(session_state)
    if old is not None:
        _revoke_tokens(old)
    clear_session(session_state)
    store_tokens(session_state, tokens)
    session_state[KEY_ACCOUNT_SUB] = sub
    session_state[KEY_ACCOUNT_EMAIL] = email
    return {"sub": sub, "email": email}


def reject_pending_login(session_state: MutableMapping) -> LogoutResult:
    """使用者取消：revoke 待確認登入的 token 並清除；不動既有正式登入。"""
    return _drop_pending_login(session_state)


# ──────────────────────────────────────────────────────────────────────
# Session（只存在注入的 session_state；不寫檔／log／cache／模組全域）
# ──────────────────────────────────────────────────────────────────────
def store_tokens(session_state: MutableMapping, tokens: Mapping[str, Any]) -> None:
    access_token = tokens.get("access_token")
    expires_at = tokens.get("expires_at")
    if not isinstance(access_token, str) or not access_token:
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "token 缺 access_token")
    if not isinstance(expires_at, (int, float)):
        raise PersonalOAuthError(ec.UPSTREAM_ERROR, "token 缺 expires_at")
    session_state[KEY_TOKENS] = dict(tokens)
    scope = tokens.get("scope")
    session_state[KEY_GRANTED_SCOPES] = tuple(scope.split()) if isinstance(scope, str) else ()


def get_tokens(session_state: Mapping) -> dict[str, Any] | None:
    tokens = session_state.get(KEY_TOKENS)
    return dict(tokens) if isinstance(tokens, Mapping) else None


def clear_session(session_state: MutableMapping) -> None:
    """清掉本模組 namespace 下的所有 key（含 Active／Pending Sheet）。不碰舊 UI key。"""
    for k in list(session_state.keys()):
        if isinstance(k, str) and k.startswith(SESSION_PREFIX):
            del session_state[k]


# ──────────────────────────────────────────────────────────────────────
# Refresh
# ──────────────────────────────────────────────────────────────────────
def ensure_fresh(session_state: MutableMapping, now: float | None = None) -> dict[str, Any]:
    """access_token 在 `TOKEN_REFRESH_LEEWAY_SEC` 內到期 → 用 refresh_token 換新並寫回。

    未登入 → `AUTH_REQUIRED`。Google 明確拒絕 refresh（invalid_grant／401）或沒有
    refresh_token → 清 session 並拋 `AUTH_EXPIRED`。網路失敗 → `NETWORK_ERROR`、5xx 等 →
    `UPSTREAM_ERROR`，兩者**不清 session**。續期後授權範圍超出唯讀 → `PERMISSION_DENIED`
    （revoke＋清 session）。任何情況都不 fallback 到其他憑證。
    """
    ts = _now(now)
    tokens = get_tokens(session_state)
    if tokens is None:
        raise PersonalOAuthError(ec.AUTH_REQUIRED, "尚未登入 Google")
    expires_at = tokens.get("expires_at")
    if isinstance(expires_at, (int, float)) and ts + TOKEN_REFRESH_LEEWAY_SEC < expires_at:
        return tokens

    rt = tokens.get("refresh_token")
    if not isinstance(rt, str) or not rt:
        clear_session(session_state)
        raise PersonalOAuthError(ec.AUTH_EXPIRED, "登入已過期，需要重新登入")
    cfg = load_client_config()
    try:
        payload = _post_token_endpoint(
            {
                "refresh_token": rt,
                "client_id": cfg.client_id,
                "client_secret": cfg.client_secret,
                "grant_type": "refresh_token",
            },
            rejected_code=ec.AUTH_EXPIRED,
            reject_any_401=True,
        )
    except PersonalOAuthError as e:
        if e.code == ec.AUTH_EXPIRED:
            clear_session(session_state)
        raise
    new_tokens = _normalize_token_payload(payload, ts)
    new_tokens.setdefault("refresh_token", rt)  # Google 續期通常不回新的 refresh_token
    if not (isinstance(new_tokens.get("scope"), str) and new_tokens["scope"].strip()):
        new_tokens["scope"] = tokens.get("scope", "")  # 續期回應未帶 scope → 沿用登入時已驗過的
    problem = _scope_problem(new_tokens)
    if problem is not None:
        _revoke_tokens(new_tokens)
        clear_session(session_state)
        raise PersonalOAuthError(ec.PERMISSION_DENIED, problem)
    store_tokens(session_state, new_tokens)
    return new_tokens


# ──────────────────────────────────────────────────────────────────────
# Logout／切換帳號
# ──────────────────────────────────────────────────────────────────────
@dataclass(frozen=True)
class LogoutResult:
    """登出結果。本機 session 一律已清除；`revoke_confirmed` 只說 Google 端撤銷是否確認。"""

    revoke_attempted: bool
    revoke_confirmed: bool
    error_code: str | None = None  # 撤銷未確認時的分類（NETWORK_ERROR／UPSTREAM_ERROR）


def logout(session_state: MutableMapping) -> LogoutResult:
    """先嘗試 revoke（refresh_token 優先，否則 access_token），**不論成敗**都清 session。

    同時 revoke 待確認登入（若有）、作廢本 session 尚未使用的 pending state。

    revoke 失敗不拋例外，只回傳結果，讓 UI 顯示「已在本機登出，Google 端撤銷未確認」。
    """
    try:
        _discard_pending(session_state.get(KEY_AUTH_PENDING_STATE))
        _drop_pending_login(session_state)  # _revoke_token 不拋例外；本機清除由 finally 保證
        return _revoke_tokens(get_tokens(session_state) or {})
    finally:
        clear_session(session_state)


def begin_account_switch(
    session_state: MutableMapping, now: float | None = None
) -> dict[str, Any]:
    """切換帳號 ＝ logout（含清 Active／Pending）→ 開始新的授權。不沿用舊 token。"""
    result = logout(session_state)
    start = begin_authorization(session_state, now)
    return {"logout": result, **start}
