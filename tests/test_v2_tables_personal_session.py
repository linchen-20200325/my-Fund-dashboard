"""services/v2_tables/personal_session.py — 假 OAuth／假 Drive，純 dict state，不連網、不用真 token。"""
from __future__ import annotations

import json
import time

import pytest

import infra.personal_oauth as po
from repositories import personal_drive_repository as drive
from services.v2_tables import personal_session as ps
from shared import active_sheet as asheet
from shared import ui_v2_error_codes as ec
from shared.personal_oauth_keys import KEY_PICKER_IDS, SESSION_KEYS

AT = "fake-access-SECRET-aaa"
RT = "fake-refresh-SECRET-bbb"
S1, S2, S3 = "1AAAAAAAAAAAAAAAAAAAA", "1BBBBBBBBBBBBBBBBBBBB", "1CCCCCCCCCCCCCCCCCCCC"


@pytest.fixture
def env(monkeypatch):
    class Env:
        identity = ("sub-A", "a@example.com")
        sheets = [{"id": S2, "name": "乙"}, {"id": S1, "name": "甲"}]
        revoked = []
        list_exc = None
        verify_result = None  # None -> ok

    e = Env()
    e.revoked = []
    monkeypatch.setattr(po, "load_client_config",
                        lambda: po.ClientConfig("cid", "csecret", "https://x.example/cb"))
    monkeypatch.setattr(po, "exchange_code", lambda code, state, now=None: (
        po.consume_pending(state) and None) or {
        "access_token": AT, "refresh_token": RT, "expires_at": time.time() + 3600,
        "scope": " ".join(po.PERSONAL_OAUTH_SCOPES)})
    monkeypatch.setattr(po, "fetch_verified_identity", lambda tok: e.identity)
    monkeypatch.setattr(po, "_revoke_token", lambda t: (e.revoked.append(t), po.LogoutResult(True, True, None))[1])

    def fake_list(token):
        assert token
        if e.list_exc:
            raise e.list_exc
        return sorted(e.sheets, key=lambda d: (d["name"], d["id"]))

    def fake_verify(token, sid):
        if e.verify_result is not None:
            return e.verify_result
        return asheet.VerifyResult(ok=True, name="驗證名-" + sid[:2])

    monkeypatch.setattr(ps.drive, "list_spreadsheets", fake_list)
    monkeypatch.setattr(ps.drive, "verify_spreadsheet", fake_verify)
    return e


def _login(state, env):
    r = ps.begin_login(state)
    assert r["ok"]
    st = state[po.KEY_AUTH_PENDING_STATE]
    r = ps.complete_login(state, "code123", st)
    assert r == {"ok": True, "pending_login_email": env.identity[1]}
    assert ps.confirm_login(state)["ok"]


def test_登入狀態轉移_未登入到正式登入(env):
    s = {}
    assert ps.status(s)["login_state"] == "logged_out"
    ps.begin_login(s)
    assert ps.status(s)["login_state"] == "logged_out"
    ps.complete_login(s, "c", s[po.KEY_AUTH_PENDING_STATE])
    st = ps.status(s)
    assert st["login_state"] == "pending_login" and st["email"] is None
    assert st["pending_login_email"] == "a@example.com"
    assert ps.confirm_login(s) == {"ok": True, "email": "a@example.com"}
    st = ps.status(s)
    assert st["login_state"] == "logged_in" and st["email"] == "a@example.com"
    assert st["pending_login_email"] is None and st["active_sheet"] is None and st["pending_sheet"] is None


def test_callback失敗回code不丟例外(env):
    s = {}
    assert ps.complete_login(s, "c", "bogus-state") == {"ok": False, "error_code": ec.AUTH_STATE_INVALID}
    assert ps.confirm_login(s) == {"ok": False, "error_code": ec.AUTH_STATE_INVALID}
    assert ps.status(s)["login_state"] == "logged_out"


def test_reject_login不登入(env):
    s = {}
    ps.begin_login(s)
    ps.complete_login(s, "c", s[po.KEY_AUTH_PENDING_STATE])
    assert ps.reject_login(s)["ok"]
    assert ps.status(s)["login_state"] == "logged_out"


def test_status不含token(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    ps.use_pending(s)
    blob = json.dumps(ps.status(s), ensure_ascii=False)
    assert AT not in blob and RT not in blob and "token" not in blob.lower()
    s2 = {}
    ps.begin_login(s2)
    ps.complete_login(s2, "c", s2[po.KEY_AUTH_PENDING_STATE])
    blob = json.dumps(ps.status(s2))
    assert AT not in blob and RT not in blob


def test_picker清單與Pending不等於Active(env):
    s = {}
    _login(s, env)
    r = ps.list_for_picker(s)
    assert r["ok"] and [x["name"] for x in r["sheets"]] == ["乙", "甲"]
    assert ps.select_pending(s, S1)["ok"]
    st = ps.status(s)
    assert st["pending_sheet"]["id"] == S1 and st["active_sheet"] is None  # Pending != Active
    r = ps.use_pending(s)
    assert r["ok"] and r["active_sheet"]["id"] == S1
    st = ps.status(s)
    assert st["active_sheet"]["id"] == S1 and st["pending_sheet"] is None


def test_select_pending拒絕不在最近清單的id(env):
    s = {}
    _login(s, env)
    assert ps.select_pending(s, S1) == {"ok": False, "error_code": ec.SHEET_NOT_FOUND}  # 尚未列清單
    ps.list_for_picker(s)
    assert ps.select_pending(s, S3) == {"ok": False, "error_code": ec.SHEET_NOT_FOUND}
    assert ps.select_pending(s, "") ["ok"] is False and ps.select_pending(s, None)["ok"] is False
    assert ps.status(s)["pending_sheet"] is None
    assert ps.select_pending(s, S2, "自帶的假名")["pending_sheet"]["name"] == "乙"  # 名稱取自清單


def test_picker失敗清掉白名單且不fallback(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    assert KEY_PICKER_IDS in s
    env.list_exc = drive.PersonalDriveError(ec.UPSTREAM_ERROR)
    assert ps.list_for_picker(s) == {"ok": False, "error_code": ec.UPSTREAM_ERROR}
    assert KEY_PICKER_IDS not in s
    assert ps.select_pending(s, S1)["ok"] is False


def test_picker_未登入與過期(env):
    assert ps.list_for_picker({}) == {"ok": False, "error_code": ec.AUTH_REQUIRED}
    s = {}
    _login(s, env)
    s[po.KEY_TOKENS]["expires_at"] = 0
    s[po.KEY_TOKENS].pop("refresh_token")
    assert ps.list_for_picker(s) == {"ok": False, "error_code": ec.AUTH_EXPIRED}
    assert ps.status(s)["login_state"] == "logged_out"  # ensure_fresh 清了 session


def test_picker錯誤碼轉遞(env):
    s = {}
    _login(s, env)
    for code in (ec.NETWORK_ERROR, ec.PERMISSION_DENIED, ec.AUTH_EXPIRED):
        env.list_exc = drive.PersonalDriveError(code)
        assert ps.list_for_picker(s) == {"ok": False, "error_code": code}


def test_驗證失敗保留舊Active與Pending(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    ps.use_pending(s)
    old = ps.status(s)["active_sheet"]
    ps.select_pending(s, S2)
    env.verify_result = asheet.VerifyResult(ok=False, error_code=ec.SCHEMA_INVALID)
    assert ps.use_pending(s) == {"ok": False, "error_code": ec.SCHEMA_INVALID}
    st = ps.status(s)
    assert st["active_sheet"] == old and st["pending_sheet"]["id"] == S2


def test_use_pending沒有pending與未登入(env):
    assert ps.use_pending({}) == {"ok": False, "error_code": ec.AUTH_REQUIRED}
    s = {}
    _login(s, env)
    assert ps.use_pending(s) == {"ok": False, "error_code": ec.UNAVAILABLE}


def test_換帳號丟掉Active與白名單(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    ps.use_pending(s)
    assert ps.status(s)["active_sheet"]
    r = ps.switch_account(s)
    assert r["ok"] and r["authorize_url"].startswith("https://")
    st = ps.status(s)
    assert st["login_state"] == "logged_out" and st["active_sheet"] is None
    assert KEY_PICKER_IDS not in s
    env.identity = ("sub-B", "b@example.com")
    ps.complete_login(s, "c", s[po.KEY_AUTH_PENDING_STATE])
    ps.confirm_login(s)
    st = ps.status(s)
    assert st["email"] == "b@example.com" and st["active_sheet"] is None  # 不沿用


def test_logout清所有namespace(env):
    s = {"other.key": 1}
    _login(s, env)
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    assert ps.logout(s)["ok"]
    assert [k for k in s if k.startswith(po.SESSION_PREFIX)] == [] and s["other.key"] == 1


def test_picker白名單key在SESSION_KEYS():
    assert KEY_PICKER_IDS in SESSION_KEYS and KEY_PICKER_IDS.startswith(po.SESSION_PREFIX)


def test_access_target(env):
    with pytest.raises(ps.PersonalSessionError) as ei:
        ps.access_target({})
    assert ei.value.code == ec.AUTH_REQUIRED
    s = {}
    _login(s, env)
    with pytest.raises(ps.PersonalSessionError) as ei:
        ps.access_target(s)
    assert ei.value.code == ec.UNAVAILABLE  # J-13：沒選就是沒有，不自動選
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    ps.use_pending(s)
    sid, tok, sub = ps.access_target(s)
    assert (sid, tok, sub) == (S1, AT, "sub-A")
    assert AT not in str(ei.value)


def test_access_target_Active帳號不符視為沒有(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    ps.use_pending(s)
    s[po.KEY_ACCOUNT_SUB] = "someone-else"
    with pytest.raises(ps.PersonalSessionError) as ei:
        ps.access_target(s)
    assert ei.value.code == ec.UNAVAILABLE


def test_未設定client時回UNAVAILABLE(monkeypatch):
    def boom():
        raise po.PersonalOAuthError(ec.UNAVAILABLE, "x")
    monkeypatch.setattr(po, "load_client_config", boom)
    assert ps.begin_login({}) == {"ok": False, "error_code": ec.UNAVAILABLE}


def test_picker記錄帳號不符視為不在清單(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    s[KEY_PICKER_IDS]["account_sub"] = "sub-OTHER"
    assert ps.select_pending(s, S1) == {"ok": False, "error_code": ec.SHEET_NOT_FOUND}
    assert ps.status(s)["pending_sheet"] is None


def test_list遇401_AUTH_EXPIRED清session(env):
    s = {}
    _login(s, env)
    env.list_exc = drive.PersonalDriveError(ec.AUTH_EXPIRED)
    assert ps.list_for_picker(s) == {"ok": False, "error_code": ec.AUTH_EXPIRED}
    assert ps.status(s)["login_state"] == "logged_out" and po.get_tokens(s) is None
    assert ps.list_for_picker(s) == {"ok": False, "error_code": ec.AUTH_REQUIRED}  # 不再重用死 token


def test_use_pending遇401_AUTH_EXPIRED清session(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    env.verify_result = asheet.VerifyResult(ok=False, error_code=ec.AUTH_EXPIRED)
    assert ps.use_pending(s) == {"ok": False, "error_code": ec.AUTH_EXPIRED}
    assert po.get_tokens(s) is None and ps.status(s)["login_state"] == "logged_out"


def test_其他錯誤碼不清session(env):
    s = {}
    _login(s, env)
    ps.list_for_picker(s)
    ps.select_pending(s, S1)
    env.verify_result = asheet.VerifyResult(ok=False, error_code=ec.PERMISSION_DENIED)
    ps.use_pending(s)
    env.list_exc = drive.PersonalDriveError(ec.NETWORK_ERROR)
    ps.list_for_picker(s)
    assert ps.status(s)["login_state"] == "logged_in"
