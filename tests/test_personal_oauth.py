"""tests/test_personal_oauth.py — 新 B UI Personal OAuth 安全基礎（infra/personal_oauth.py）。

規格：客戶 2026-10-26 裁示第 1～4、9、10 節。fast lane，不碰網路：
`requests.post` 與 `get_secret` 一律 monkeypatch。
"""
from __future__ import annotations

import ast
import base64
import hashlib
import json
import urllib.parse
from pathlib import Path

import pytest
import requests

import infra.personal_oauth as po
from shared import ui_v2_error_codes as ec

REPO = Path(__file__).resolve().parent.parent
MOD_PATH = REPO / "infra" / "personal_oauth.py"

CFG = {"client_id": "cid", "client_secret": "csecret", "redirect_uri": "https://app.example/"}
OLD_KEYS = {"gsheet_tokens": {"access_token": "OLD"}, "gsheet_email": "old@x", "_oauth_state": "s"}


class FakeResp:
    def __init__(self, status: int, payload=None, raise_json: bool = False):
        self.status_code = status
        self._payload = payload
        self._raise_json = raise_json

    def json(self):
        if self._raise_json:
            raise ValueError("not json")
        return self._payload


@pytest.fixture(autouse=True)
def _iso(monkeypatch):
    monkeypatch.setattr(po, "_PENDING", {})
    monkeypatch.setattr(po, "get_secret", lambda key, default=None: CFG if key == "google_oauth" else default)

    def _no_net(*a, **k):
        raise AssertionError("unexpected network call")

    monkeypatch.setattr(po.requests, "post", _no_net)
    monkeypatch.setattr(po.requests, "get", _no_net)


GOOD_ID = {"sub": "1234", "email": "a@example.com", "email_verified": True}


def _set_get(monkeypatch, fn):
    calls = []

    def _g(url, **kw):
        calls.append((url, kw))
        return fn(url, **kw)

    monkeypatch.setattr(po.requests, "get", _g)
    return calls


def _set_post(monkeypatch, fn):
    calls = []

    def _p(url, **kw):
        calls.append((url, kw))
        return fn(url, **kw)

    monkeypatch.setattr(po.requests, "post", _p)
    return calls


def _ok_token(**extra):
    p = {"access_token": "AT", "expires_in": 3600, "refresh_token": "RT", "scope": " ".join(po.PERSONAL_OAUTH_SCOPES)}
    p.update(extra)
    return p


# ── 錯誤碼 ─────────────────────────────────────────────────────────────
def test_error_code_set_exactly_nine():
    assert ec.ALL_ERROR_CODES == {
        "AUTH_REQUIRED", "AUTH_EXPIRED", "AUTH_STATE_INVALID", "PERMISSION_DENIED",
        "SHEET_NOT_FOUND", "SCHEMA_INVALID", "NETWORK_ERROR", "UPSTREAM_ERROR", "UNAVAILABLE",
    }
    assert len(ec.ALL_ERROR_CODES) == 9


def test_unknown_code_rejected():
    with pytest.raises(ValueError):
        po.PersonalOAuthError("SOMETHING_ELSE", "x")
    e = po.PersonalOAuthError(ec.AUTH_REQUIRED, "msg")
    assert e.code == ec.AUTH_REQUIRED


# ── Scope／authorize URL ───────────────────────────────────────────────
def test_scopes_exactly_four_readonly():
    s = po.PERSONAL_OAUTH_SCOPES
    assert set(s) == {
        "https://www.googleapis.com/auth/spreadsheets.readonly",
        "https://www.googleapis.com/auth/drive.metadata.readonly",
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    }
    assert len(s) == 4
    assert "https://www.googleapis.com/auth/spreadsheets" not in s
    assert "https://www.googleapis.com/auth/drive.file" not in s


def test_authorize_url_params_and_pkce():
    start = po.begin_authorization({}, now=1000)
    q = urllib.parse.parse_qs(urllib.parse.urlparse(start["authorize_url"]).query)
    assert "include_granted_scopes" not in q
    assert q["code_challenge_method"] == ["S256"]
    assert q["access_type"] == ["offline"]
    assert q["prompt"] == ["select_account consent"]
    assert q["response_type"] == ["code"]
    assert q["state"] == [start["state"]]
    assert set(q["scope"][0].split()) == set(po.PERSONAL_OAUTH_SCOPES)
    verifier = po._PENDING[start["state"]][0]
    expect = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    assert q["code_challenge"] == [expect]
    assert "=" not in q["code_challenge"][0]
    assert verifier not in start["authorize_url"]


def test_verifier_rfc7636():
    for _ in range(20):
        v = po.generate_code_verifier()
        assert 43 <= len(v) <= 128
        assert set(v) <= po.PKCE_ALLOWED_CHARS


# ── State fail-closed ──────────────────────────────────────────────────
@pytest.mark.parametrize("bad", [None, "", 123])
def test_state_missing_or_none(bad):
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.consume_pending(bad)
    assert ei.value.code == ec.AUTH_STATE_INVALID


def test_state_unknown():
    po.register_pending(now=0)
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.consume_pending("not-registered", now=1)
    assert ei.value.code == ec.AUTH_STATE_INVALID


def test_state_expired():
    s, _ = po.register_pending(now=0)
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.consume_pending(s, now=po.PENDING_TTL_SEC + 1)
    assert ei.value.code == ec.AUTH_STATE_INVALID
    assert s not in po._PENDING


def test_state_replay_rejected():
    s, v = po.register_pending(now=0)
    assert po.consume_pending(s, now=1) == v
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.consume_pending(s, now=2)
    assert ei.value.code == ec.AUTH_STATE_INVALID


def test_store_cap(monkeypatch):
    monkeypatch.setattr(po, "PENDING_MAX", 3)
    states = [po.register_pending(now=0)[0] for _ in range(3)]
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.register_pending(now=1)
    assert ei.value.code == ec.UNAVAILABLE
    assert set(po._PENDING) == set(states)  # 不淘汰任何有效 state
    # 過期後可再登記（先清過期）
    po.register_pending(now=po.PENDING_TTL_SEC + 5)
    assert po.pending_count() == 1


# ── Client 設定只來自 secrets ──────────────────────────────────────────
def test_client_config_from_secrets_only(monkeypatch):
    seen = []
    monkeypatch.setattr(po, "get_secret", lambda key, default=None: (seen.append(key), None)[1])
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.begin_authorization({})
    assert ei.value.code == ec.UNAVAILABLE
    assert seen == ["google_oauth"]
    assert po.pending_count() == 0


def test_session_custom_cfg_ignored(monkeypatch):
    monkeypatch.setattr(po, "get_secret", lambda key, default=None: {"client_id": "cid"})
    sess = {"custom_oauth_cfg": dict(CFG), "b_oauth.client": dict(CFG)}
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.load_client_config()
    assert ei.value.code == ec.UNAVAILABLE
    assert "csecret" not in str(ei.value)
    src = MOD_PATH.read_text(encoding="utf-8")
    assert "custom_oauth_cfg" not in src
    assert sess["custom_oauth_cfg"] == CFG


# ── Exchange ───────────────────────────────────────────────────────────
def test_exchange_success_sends_verifier(monkeypatch):
    s, v = po.register_pending(now=100)
    calls = _set_post(monkeypatch, lambda url, **kw: FakeResp(200, _ok_token()))
    gcalls = _set_get(monkeypatch, lambda url, **kw: FakeResp(200, dict(GOOD_ID)))
    sess = dict(OLD_KEYS)
    out = po.complete_authorization(sess, code="C", state=s, now=100)
    assert out == {"sub": "1234", "email": "a@example.com"}  # 只回身分，不回 token
    assert po.get_tokens(sess) is None  # 待確認登入不可用（A1）
    assert po.get_pending_login(sess, now=100)["email"] == "a@example.com"
    assert "tokens" not in po.get_pending_login(sess, now=100)
    po.confirm_pending_login(sess, now=101)
    assert gcalls[0][0] == po.GOOGLE_USERINFO_URL == "https://openidconnect.googleapis.com/v1/userinfo"
    assert gcalls[0][1]["headers"]["Authorization"] == "Bearer AT"
    assert gcalls[0][1]["timeout"] == po.HTTP_TIMEOUT_SEC
    assert sess[po.KEY_ACCOUNT_SUB] == "1234" and sess[po.KEY_ACCOUNT_EMAIL] == "a@example.com"
    url, kw = calls[0]
    assert url == po.GOOGLE_TOKEN_URL == "https://oauth2.googleapis.com/token"
    assert kw["data"]["code_verifier"] == v
    assert kw["data"]["grant_type"] == "authorization_code"
    assert kw["timeout"] == po.HTTP_TIMEOUT_SEC
    assert sess[po.KEY_TOKENS]["expires_at"] == 3700
    assert sess[po.KEY_TOKENS]["access_token"] == "AT"
    for k, val in OLD_KEYS.items():
        assert sess[k] == val


def test_exchange_invalid_grant(monkeypatch):
    s, _ = po.register_pending(now=0)
    _set_post(monkeypatch, lambda url, **kw: FakeResp(400, {"error": "invalid_grant"}))
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.exchange_code("C", s, now=0)
    assert ei.value.code == ec.AUTH_STATE_INVALID


def test_exchange_timeout(monkeypatch):
    s, _ = po.register_pending(now=0)

    def _t(url, **kw):
        raise requests.exceptions.Timeout("slow")

    _set_post(monkeypatch, _t)
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.exchange_code("C", s, now=0)
    assert ei.value.code == ec.NETWORK_ERROR


def test_exchange_5xx(monkeypatch):
    s, _ = po.register_pending(now=0)
    _set_post(monkeypatch, lambda url, **kw: FakeResp(503, None, raise_json=True))
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.exchange_code("C", s, now=0)
    assert ei.value.code == ec.UPSTREAM_ERROR


def test_exchange_missing_access_token(monkeypatch):
    s, _ = po.register_pending(now=0)
    _set_post(monkeypatch, lambda url, **kw: FakeResp(200, {"expires_in": 3600}))
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.exchange_code("C", s, now=0)
    assert ei.value.code == ec.UPSTREAM_ERROR


def test_exchange_bad_state_no_network(monkeypatch):
    # _iso 預設 requests.post 會 AssertionError：state 不合法時必須在發請求前就失敗
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.exchange_code("C", None)
    assert ei.value.code == ec.AUTH_STATE_INVALID


@pytest.mark.parametrize("state", ["forged", None, ""])
def test_forged_state_does_not_touch_session(state):
    """A2：偽造 state 不得改動 session（不能被拿來強制登出），也不發任何請求。"""
    sess = {po.KEY_TOKENS: {"access_token": "PREV", "expires_at": 9e9}, po.KEY_ACTIVE_SHEET: "S"}
    before = {k: (dict(v) if isinstance(v, dict) else v) for k, v in sess.items()}
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.complete_authorization(sess, code="C", state=state)
    assert ei.value.code == ec.AUTH_STATE_INVALID
    assert sess == before


def test_exchange_400_not_invalid_grant_is_upstream(monkeypatch):
    s, _ = po.register_pending(now=0)
    _set_post(monkeypatch, lambda url, **kw: FakeResp(400, {"error": "invalid_request"}))
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.exchange_code("C", s, now=0)
    assert ei.value.code == ec.UPSTREAM_ERROR


def test_pkce_rfc7636_appendix_b_vector():
    assert po.code_challenge_s256("dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk") \
        == "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM"


# ── Logout ─────────────────────────────────────────────────────────────
def _logged_in():
    s = dict(OLD_KEYS)
    s[po.KEY_TOKENS] = {"access_token": "AT", "refresh_token": "RT", "expires_at": 9e9}
    s[po.KEY_ACCOUNT_EMAIL] = "a@x"
    s[po.KEY_ACCOUNT_SUB] = "sub-A"
    s[po.KEY_ACTIVE_SHEET] = "sheet-A"
    s[po.KEY_PENDING_SHEET] = "sheet-B"
    return s


def _assert_cleared(s):
    assert not [k for k in s if str(k).startswith(po.SESSION_PREFIX)]
    for k, val in OLD_KEYS.items():
        assert s[k] == val


def test_logout_revoke_success(monkeypatch):
    calls = _set_post(monkeypatch, lambda url, **kw: FakeResp(200, {}))
    s = _logged_in()
    r = po.logout(s)
    assert r.revoke_attempted and r.revoke_confirmed
    assert calls[0][0] == po.GOOGLE_REVOKE_URL
    assert calls[0][1]["data"] == {"token": "RT"}
    assert calls[0][1]["timeout"] == po.REVOKE_TIMEOUT_SEC
    _assert_cleared(s)


def test_logout_revoke_http_fail(monkeypatch):
    _set_post(monkeypatch, lambda url, **kw: FakeResp(400, {"error": "invalid_token"}))
    s = _logged_in()
    r = po.logout(s)
    assert r.revoke_attempted and not r.revoke_confirmed and r.error_code == ec.UPSTREAM_ERROR
    _assert_cleared(s)


@pytest.mark.parametrize("exc,code", [
    (requests.exceptions.ConnectionError("down"), ec.NETWORK_ERROR),
    (RuntimeError("boom"), ec.UPSTREAM_ERROR),
])
def test_logout_revoke_raises(monkeypatch, exc, code):
    def _r(url, **kw):
        raise exc

    _set_post(monkeypatch, _r)
    s = _logged_in()
    r = po.logout(s)
    assert r.revoke_attempted and not r.revoke_confirmed and r.error_code == code
    _assert_cleared(s)


def test_logout_access_token_fallback(monkeypatch):
    calls = _set_post(monkeypatch, lambda url, **kw: FakeResp(200, {}))
    s = {po.KEY_TOKENS: {"access_token": "AT", "expires_at": 9e9}}
    po.logout(s)
    assert calls[0][1]["data"] == {"token": "AT"}


def test_account_switch_drops_old_token(monkeypatch):
    _set_post(monkeypatch, lambda url, **kw: FakeResp(200, {}))
    s = _logged_in()
    out = po.begin_account_switch(s, now=0)
    assert po.get_tokens(s) is None
    assert [k for k in s if k.startswith(po.SESSION_PREFIX)] == [
        po.KEY_AUTH_PENDING_STATE, po.KEY_AUTH_PENDING_EXPIRES]
    assert s[po.KEY_AUTH_PENDING_STATE] == out["state"]
    assert out["state"] in po._PENDING
    assert "authorize_url" in out and out["logout"].revoke_confirmed


# ── Refresh ────────────────────────────────────────────────────────────
def test_ensure_fresh_not_due():
    s = {po.KEY_TOKENS: {"access_token": "AT", "refresh_token": "RT", "expires_at": 1000}}
    assert po.ensure_fresh(s, now=900)["access_token"] == "AT"


def test_ensure_fresh_refreshes(monkeypatch):
    calls = _set_post(monkeypatch, lambda url, **kw: FakeResp(200, {"access_token": "AT2", "expires_in": 3600}))
    s = {po.KEY_TOKENS: {"access_token": "AT", "refresh_token": "RT", "expires_at": 1000,
                         "scope": " ".join(po.PERSONAL_OAUTH_SCOPES)}}
    t = po.ensure_fresh(s, now=950)
    assert t["access_token"] == "AT2" and t["refresh_token"] == "RT"
    assert s[po.KEY_TOKENS]["access_token"] == "AT2"
    assert calls[0][1]["data"]["grant_type"] == "refresh_token"


@pytest.mark.parametrize("resp", [
    lambda url, **kw: FakeResp(400, {"error": "invalid_grant"}),
    lambda url, **kw: FakeResp(401, {"error": "unauthorized_client"}),
])
def test_ensure_fresh_rejected_clears(monkeypatch, resp):
    _set_post(monkeypatch, resp)
    s = _logged_in()
    s[po.KEY_TOKENS]["expires_at"] = 1000
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.ensure_fresh(s, now=990)
    assert ei.value.code == ec.AUTH_EXPIRED
    _assert_cleared(s)


def _raise(exc):
    def _f(url, **kw):
        raise exc
    return _f


@pytest.mark.parametrize("resp,code", [
    (_raise(requests.exceptions.Timeout("slow")), ec.NETWORK_ERROR),
    (_raise(requests.exceptions.ConnectionError("down")), ec.NETWORK_ERROR),
    (lambda url, **kw: FakeResp(503, None, raise_json=True), ec.UPSTREAM_ERROR),
    (lambda url, **kw: FakeResp(500, {"error": "internal"}), ec.UPSTREAM_ERROR),
])
def test_ensure_fresh_transient_keeps_session(monkeypatch, resp, code):
    _set_post(monkeypatch, resp)
    s = _logged_in()
    s[po.KEY_TOKENS]["expires_at"] = 1000
    before = {k: (dict(v) if isinstance(v, dict) else v) for k, v in s.items()}
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.ensure_fresh(s, now=990)
    assert ei.value.code == code
    assert s == before


def test_ensure_fresh_excess_scope_rejected(monkeypatch):
    calls = _set_post(monkeypatch, lambda url, **kw: (
        FakeResp(200, {"access_token": "AT2", "expires_in": 3600,
                       "scope": "openid https://www.googleapis.com/auth/drive"})
        if url == po.GOOGLE_TOKEN_URL else FakeResp(200, {})))
    s = _logged_in()
    s[po.KEY_TOKENS]["expires_at"] = 1000
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.ensure_fresh(s, now=990)
    assert ei.value.code == ec.PERMISSION_DENIED
    assert calls[-1][0] == po.GOOGLE_REVOKE_URL
    _assert_cleared(s)


def test_ensure_fresh_no_refresh_token_clears():
    s = {po.KEY_TOKENS: {"access_token": "AT", "expires_at": 0}, "gsheet_tokens": {"access_token": "OLD"}}
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.ensure_fresh(s, now=10)
    assert ei.value.code == ec.AUTH_EXPIRED
    assert po.get_tokens(s) is None and s["gsheet_tokens"] == {"access_token": "OLD"}


def test_ensure_fresh_not_logged_in():
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.ensure_fresh({"gsheet_tokens": {"access_token": "OLD", "expires_at": 9e9}})
    assert ei.value.code == ec.AUTH_REQUIRED


# ── 靜態：namespace、模組全域、分層 ─────────────────────────────────────
def test_session_keys_namespaced():
    for k in po.SESSION_KEYS:
        assert k.startswith(po.SESSION_PREFIX)
    src = MOD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    for old in ("gsheet_tokens", "gsheet_email", "_oauth_state"):
        assert old not in literals


def test_no_token_written_to_module_globals():
    tree = ast.parse(MOD_PATH.read_text(encoding="utf-8"))
    module_names = set()
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name):
                    module_names.add(t.id)
                    if "token" in t.id.lower():
                        # 只准是字串／數字常數（URL、key 名、秒數），不得是容器
                        assert all(isinstance(x, (ast.Constant, ast.BinOp, ast.Name, ast.Add, ast.Load))
                                   for x in ast.walk(node.value)), t.id
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.Global, ast.Nonlocal)), "不得以 global 寫模組全域"
    subscript_stores = []
    for fn in [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]:
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Subscript) and isinstance(t.value, ast.Name) and t.value.id in module_names:
                        subscript_stores.append((t.value.id, node.value))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) and node.func.value.id in module_names \
                    and node.func.attr in {"update", "setdefault", "append", "__setitem__"}:
                subscript_stores.append((node.func.value.id, node))
    assert len(subscript_stores) == 1
    name, value = subscript_stores[0]
    assert name == "_PENDING"
    assert isinstance(value, ast.Tuple)
    assert [e.id for e in value.elts] == ["verifier", "expires_at"]


def test_layering_imports():
    def _imports(path):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        out = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                out |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom) and n.module:
                out.add(n.module.split(".")[0])
        return out

    forbidden_upper = {"repositories", "services", "ui", "ui_v2", "app", "fund_fetcher", "streamlit"}
    assert not (_imports(MOD_PATH) & forbidden_upper)
    shared_imports = _imports(REPO / "shared" / "ui_v2_error_codes.py")
    assert not (shared_imports & (forbidden_upper | {"infra", "requests"}))
    full_mods = set()
    for n in ast.walk(ast.parse(MOD_PATH.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            full_mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            full_mods.add(n.module)
            full_mods |= {f"{n.module}.{a.name}" for a in n.names}
    assert not any(m == "infra.oauth" or m.endswith("oauth_state") for m in full_mods)


def test_error_messages_do_not_leak_secret(monkeypatch):
    s, v = po.register_pending(now=0)
    _set_post(monkeypatch, lambda url, **kw: FakeResp(401, {"error": "invalid_client", "error_description": "csecret"}))
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.exchange_code("CODE123", s, now=0)
    msg = str(ei.value)
    for secret in ("csecret", v, "CODE123"):
        assert secret not in msg
    assert "csecret" not in repr(po.load_client_config())
    json.dumps(msg)


# ── 授權範圍檢查（總管裁定 3）──────────────────────────────────────────
@pytest.mark.parametrize("scope", [
    " ".join(po.PERSONAL_OAUTH_SCOPES) + " https://www.googleapis.com/auth/spreadsheets",
    " ".join(po.PERSONAL_OAUTH_SCOPES) + " https://www.googleapis.com/auth/drive",
    " ".join(po.PERSONAL_OAUTH_SCOPES) + " https://www.googleapis.com/auth/drive.file",
    None,
    "",
    "openid https://www.googleapis.com/auth/userinfo.email",
    " ".join(x for x in po.PERSONAL_OAUTH_SCOPES if "spreadsheets" not in x),
])
def test_excess_or_missing_scope_rejected(monkeypatch, scope):
    s, _ = po.register_pending(now=0)
    tok = _ok_token()
    if scope is None:
        tok.pop("scope")
    else:
        tok["scope"] = scope
    calls = _set_post(monkeypatch, lambda url, **kw: FakeResp(200, tok) if url == po.GOOGLE_TOKEN_URL else FakeResp(200, {}))
    sess = dict(OLD_KEYS)
    sess[po.KEY_PENDING_LOGIN] = {"tokens": {"access_token": "OLDPENDING"}, "sub": "x", "email": "x", "expires_at": 9e9}
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.complete_authorization(sess, code="C", state=s, now=0)
    assert ei.value.code == ec.PERMISSION_DENIED
    assert "唯讀" in ei.value.message
    revoked = [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL]
    assert "RT" in revoked and "OLDPENDING" in revoked
    _assert_cleared(sess)


def test_missing_scope_message_names_it(monkeypatch):
    s, _ = po.register_pending(now=0)
    tok = _ok_token(scope="openid https://www.googleapis.com/auth/userinfo.email "
                          "https://www.googleapis.com/auth/drive.metadata.readonly")
    _set_post(monkeypatch, lambda url, **kw: FakeResp(200, tok) if url == po.GOOGLE_TOKEN_URL else FakeResp(200, {}))
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.complete_authorization({}, code="C", state=s, now=0)
    assert ei.value.code == ec.PERMISSION_DENIED
    assert "spreadsheets.readonly" in ei.value.message


def test_rejected_new_login_keeps_formal_login(monkeypatch):
    """新登入被拒（scope）只 revoke 新 token，不動既有正式登入（A2：不可被拿來強制登出）。"""
    s, _ = po.register_pending(now=0)
    tok = _ok_token(scope="openid")
    calls = _set_post(monkeypatch, lambda url, **kw: FakeResp(200, tok) if url == po.GOOGLE_TOKEN_URL else FakeResp(200, {}))
    sess = _logged_in()
    with pytest.raises(po.PersonalOAuthError):
        po.complete_authorization(sess, code="C", state=s, now=0)
    assert po.get_tokens(sess)["access_token"] == "AT"
    assert sess[po.KEY_ACTIVE_SHEET] == "sheet-A"
    assert [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL] == ["RT"]


# ── 待確認登入（A1）────────────────────────────────────────────────────
def _pending(monkeypatch, sess, now=0):
    s, _ = po.register_pending(now=now)
    calls = _set_post(monkeypatch, lambda url, **kw: FakeResp(200, _ok_token(access_token="NEWAT", refresh_token="NEWRT"))
                      if url == po.GOOGLE_TOKEN_URL else FakeResp(200, {}))
    _set_get(monkeypatch, lambda url, **kw: FakeResp(200, dict(GOOD_ID)))
    po.complete_authorization(sess, code="C", state=s, now=now)
    return calls


def test_pending_login_not_usable_until_confirm(monkeypatch):
    sess = {}
    _pending(monkeypatch, sess)
    assert po.get_tokens(sess) is None
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.ensure_fresh(sess, now=1)
    assert ei.value.code == ec.AUTH_REQUIRED
    assert po.confirm_pending_login(sess, now=10) == {"sub": "1234", "email": "a@example.com"}
    assert po.get_tokens(sess)["access_token"] == "NEWAT"
    assert po.KEY_PENDING_LOGIN not in sess
    assert sess[po.KEY_ACCOUNT_SUB] == "1234"


def test_confirm_replaces_old_login_with_revoke(monkeypatch):
    sess = _logged_in()
    calls = _pending(monkeypatch, sess)
    assert po.get_tokens(sess)["access_token"] == "AT"  # 確認前舊登入不變
    po.confirm_pending_login(sess, now=10)
    revoked = [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL]
    assert revoked == ["RT"]
    assert po.get_tokens(sess)["access_token"] == "NEWAT"
    assert po.KEY_ACTIVE_SHEET not in sess and po.KEY_PENDING_SHEET not in sess


def test_reject_pending_login_revokes(monkeypatch):
    sess = _logged_in()
    calls = _pending(monkeypatch, sess)
    r = po.reject_pending_login(sess)
    assert r.revoke_confirmed
    assert [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL] == ["NEWRT"]
    assert po.KEY_PENDING_LOGIN not in sess
    assert po.get_tokens(sess)["access_token"] == "AT"


def test_pending_login_expiry_revokes(monkeypatch):
    sess = {}
    calls = _pending(monkeypatch, sess, now=0)
    assert po.get_pending_login(sess, now=po.PENDING_LOGIN_TTL_SEC + 1) is None
    assert po.KEY_PENDING_LOGIN not in sess
    assert [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL] == ["NEWRT"]


def test_confirm_after_expiry_rejected(monkeypatch):
    sess = {}
    calls = _pending(monkeypatch, sess, now=0)
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.confirm_pending_login(sess, now=po.PENDING_LOGIN_TTL_SEC + 1)
    assert ei.value.code == ec.AUTH_STATE_INVALID
    assert po.get_tokens(sess) is None and po.KEY_PENDING_LOGIN not in sess
    assert [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL] == ["NEWRT"]


def test_confirm_without_pending():
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.confirm_pending_login({})
    assert ei.value.code == ec.AUTH_STATE_INVALID


def test_logout_revokes_pending_login(monkeypatch):
    sess = _logged_in()
    calls = _pending(monkeypatch, sess)
    po.logout(sess)
    revoked = [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL]
    assert set(revoked) == {"NEWRT", "RT"}
    _assert_cleared(sess)


# ── per-session pending state（B1）─────────────────────────────────────
def test_begin_reuses_session_state():
    sess = {}
    a = po.begin_authorization(sess, now=0)
    b = po.begin_authorization(sess, now=10)
    assert a == b and po.pending_count() == 1
    po.begin_authorization({}, now=10)  # 另一個 session 另登記
    assert po.pending_count() == 2


def test_begin_new_state_when_consumed_or_expired():
    sess = {}
    a = po.begin_authorization(sess, now=0)
    po.consume_pending(a["state"], now=1)
    b = po.begin_authorization(sess, now=2)
    assert b["state"] != a["state"]
    c = po.begin_authorization(sess, now=2 + po.PENDING_TTL_SEC + 1)
    assert c["state"] != b["state"]


def test_begin_reuse_and_cap(monkeypatch):
    monkeypatch.setattr(po, "PENDING_MAX", 2)
    sess = {}
    po.begin_authorization(sess, now=0)
    po.begin_authorization({}, now=0)
    po.begin_authorization(sess, now=1)  # 重用，不受滿額影響
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.begin_authorization({}, now=1)
    assert ei.value.code == ec.UNAVAILABLE
    assert po.pending_count() == 2


# ── 帳號身分（總管裁定 4）──────────────────────────────────────────────
@pytest.mark.parametrize("get_fn,code", [
    (lambda url, **kw: FakeResp(200, {"email": "a@x", "email_verified": True}), ec.AUTH_STATE_INVALID),
    (lambda url, **kw: FakeResp(200, {"sub": "1", "email_verified": True}), ec.AUTH_STATE_INVALID),
    (lambda url, **kw: FakeResp(200, {"sub": "1", "email": "a@x", "email_verified": False}), ec.AUTH_STATE_INVALID),
    (lambda url, **kw: FakeResp(200, {"sub": "1", "email": "a@x", "email_verified": "true"}), ec.AUTH_STATE_INVALID),
    (lambda url, **kw: FakeResp(200, {"sub": "1", "email": "a@x"}), ec.AUTH_STATE_INVALID),
    (lambda url, **kw: FakeResp(401, {}), ec.AUTH_STATE_INVALID),
    (lambda url, **kw: FakeResp(502, None, raise_json=True), ec.UPSTREAM_ERROR),
    (lambda url, **kw: FakeResp(200, None, raise_json=True), ec.UPSTREAM_ERROR),
    (_raise(requests.exceptions.Timeout("slow")), ec.NETWORK_ERROR),
])
def test_identity_required(monkeypatch, get_fn, code):
    s, _ = po.register_pending(now=0)
    _set_get(monkeypatch, get_fn)
    calls = []
    monkeypatch.setattr(po.requests, "post", lambda url, **kw: (
        calls.append((url, kw)) or (FakeResp(200, _ok_token()) if url == po.GOOGLE_TOKEN_URL else FakeResp(200, {}))))
    sess = dict(OLD_KEYS)
    sess[po.KEY_TOKENS] = {"access_token": "PREV", "expires_at": 9e9}
    with pytest.raises(po.PersonalOAuthError) as ei:
        po.complete_authorization(sess, code="C", state=s, now=0)
    assert ei.value.code == code
    assert [c[1]["data"]["token"] for c in calls if c[0] == po.GOOGLE_REVOKE_URL] == ["RT"]
    assert po.KEY_PENDING_LOGIN not in sess
    assert po.get_tokens(sess)["access_token"] == "PREV"  # 既有正式登入不動


def test_no_id_token_parsing():
    src = MOD_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert not any("id_token" in n for n in names)
    literals = {n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert "id_token" not in literals
    assert "b64decode" not in src and "urlsafe_b64decode" not in src
