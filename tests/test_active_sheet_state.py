"""shared/active_sheet.py — Active／Pending Sheet runtime 狀態機（裁示第 8 節 J-5；fast lane，純邏輯）。

不需要 streamlit、不連網：state 用 dict，verify 用替身。
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from infra import personal_oauth as po
from shared import active_sheet as A
from shared import personal_oauth_keys as K
from shared import ui_v2_error_codes as ec

REPO = pathlib.Path(__file__).resolve().parents[1]
MOD_PATH = REPO / "shared" / "active_sheet.py"
KEYS_PATH = REPO / "shared" / "personal_oauth_keys.py"


def _logged_in(sub: str = "sub-A") -> dict:
    return {K.KEY_TOKENS: {"access_token": "AT", "expires_at": 9e9}, K.KEY_ACCOUNT_SUB: sub}


def _ok(name=None):
    calls = []

    def verify(sheet_id):
        calls.append(sheet_id)
        return A.VerifyResult(ok=True, name=name)

    return verify, calls


def _fail(code):
    calls = []

    def verify(sheet_id):
        calls.append(sheet_id)
        return A.VerifyResult(ok=False, error_code=code, message="x")

    return verify, calls


def _activate(state, sheet_id="SHEET-1", name="持倉一", sub_now=100.0):
    A.set_pending(state, sheet_id, name)
    verify, _ = _ok()
    res = A.activate_pending(state, verify, now=sub_now)
    assert res.ok
    return res


# ── 鍵名 SSOT：personal_oauth 與 shared 是同一組 ─────────────────────────
def test_keys_are_shared_with_personal_oauth():
    for name in ("SESSION_PREFIX", "KEY_TOKENS", "KEY_ACCOUNT_SUB", "KEY_ACTIVE_SHEET",
                 "KEY_PENDING_SHEET", "SESSION_KEYS"):
        assert getattr(po, name) is getattr(K, name), name
    assert K.KEY_ACTIVE_SHEET.startswith(K.SESSION_PREFIX)
    assert K.KEY_PENDING_SHEET.startswith(K.SESSION_PREFIX)
    assert K.KEY_ACTIVE_SHEET != K.KEY_PENDING_SHEET


# ── Pending ≠ Active ──────────────────────────────────────────────────────
def test_set_pending_does_not_touch_active():
    s = _logged_in()
    _activate(s, "OLD", "舊本")
    before = dict(s[K.KEY_ACTIVE_SHEET])
    p = A.set_pending(s, "  NEW  ", " 新本 ")
    assert p == A.PendingSheet(sheet_id="NEW", name="新本")
    assert A.get_pending(s) == p
    assert s[K.KEY_ACTIVE_SHEET] == before
    assert A.get_active(s).sheet_id == "OLD"


def test_pending_alone_is_not_active():
    s = _logged_in()
    A.set_pending(s, "SHEET-1", "持倉一")
    assert A.get_active(s) is None
    assert A.get_pending(s).sheet_id == "SHEET-1"


@pytest.mark.parametrize("sid", ["", "   ", None, 123])
def test_set_pending_rejects_blank_id(sid):
    s = _logged_in()
    with pytest.raises(ValueError):
        A.set_pending(s, sid, "x")
    assert K.KEY_PENDING_SHEET not in s


def test_set_pending_rejects_non_str_name():
    with pytest.raises(ValueError):
        A.set_pending(_logged_in(), "S", None)


def test_clear_pending_keeps_active():
    s = _logged_in()
    _activate(s, "OLD", "舊本")
    A.set_pending(s, "NEW", "新本")
    A.clear_pending(s)
    assert A.get_pending(s) is None
    assert A.get_active(s).sheet_id == "OLD"
    A.clear_pending(s)  # 沒有也不炸


# ── 驗證成功才切換 ────────────────────────────────────────────────────────
def test_activate_success_switches_and_clears_pending():
    s = _logged_in("sub-A")
    A.set_pending(s, "SHEET-1", "持倉一")
    verify, calls = _ok()
    res = A.activate_pending(s, verify, now=1234.5)
    assert calls == ["SHEET-1"]
    assert res.ok and res.error_code is None
    assert res.active == A.ActiveSheet("SHEET-1", "持倉一", 1234.5, "sub-A")
    assert A.get_active(s) == res.active
    assert A.get_pending(s) is None
    assert s[K.KEY_ACTIVE_SHEET] == {"sheet_id": "SHEET-1", "name": "持倉一",
                                     "verified_at": 1234.5, "account_sub": "sub-A"}


def test_activate_uses_verified_name_when_given():
    s = _logged_in()
    A.set_pending(s, "SHEET-1", "使用者打的")
    verify, _ = _ok(name="  試算表真名 ")
    assert A.activate_pending(s, verify, now=1).active.name == "試算表真名"


# ── 驗證失敗保留舊 Active，Pending 保留 ───────────────────────────────────
@pytest.mark.parametrize("code", sorted(ec.ALL_ERROR_CODES))
def test_activate_failure_keeps_old_active_and_pending(code):
    s = _logged_in()
    _activate(s, "OLD", "舊本", sub_now=10)
    old_rec = dict(s[K.KEY_ACTIVE_SHEET])
    A.set_pending(s, "NEW", "新本")
    verify, calls = _fail(code)
    res = A.activate_pending(s, verify, now=20)
    assert calls == ["NEW"]
    assert not res.ok and res.error_code == code and res.active is None
    assert s[K.KEY_ACTIVE_SHEET] == old_rec
    assert A.get_active(s).sheet_id == "OLD"
    assert A.get_pending(s) == A.PendingSheet("NEW", "新本")


def test_activate_failure_without_prior_active_stays_none():
    s = _logged_in()
    A.set_pending(s, "NEW", "新本")
    res = A.activate_pending(s, _fail(ec.SHEET_NOT_FOUND)[0])
    assert res.error_code == ec.SHEET_NOT_FOUND
    assert A.get_active(s) is None and K.KEY_ACTIVE_SHEET not in s


def test_verify_exception_propagates_and_changes_nothing():
    s = _logged_in()
    _activate(s, "OLD", "舊本")
    A.set_pending(s, "NEW", "新本")
    snapshot = {k: (dict(v) if isinstance(v, dict) else v) for k, v in s.items()}

    def boom(_):
        raise RuntimeError("驗證爆了")

    with pytest.raises(RuntimeError):
        A.activate_pending(s, boom)
    assert s == snapshot


def test_verify_must_return_verifyresult():
    s = _logged_in()
    A.set_pending(s, "NEW", "新本")
    with pytest.raises(TypeError):
        A.activate_pending(s, lambda _: True)
    assert A.get_pending(s) is not None and A.get_active(s) is None


def test_no_pending_is_unavailable_and_verify_not_called():
    s = _logged_in()
    _activate(s, "OLD", "舊本")
    verify, calls = _ok()
    res = A.activate_pending(s, verify)
    assert calls == [] and res.error_code == ec.UNAVAILABLE
    assert A.get_active(s).sheet_id == "OLD"


def test_not_logged_in_activation_is_auth_required_and_verify_not_called():
    s = {}
    A.set_pending(s, "NEW", "新本")
    verify, calls = _ok()
    res = A.activate_pending(s, verify)
    assert calls == [] and res.error_code == ec.AUTH_REQUIRED
    assert A.get_pending(s) is not None and K.KEY_ACTIVE_SHEET not in s


def test_account_changed_during_verify_does_not_activate():
    s = _logged_in("sub-A")
    A.set_pending(s, "NEW", "新本")

    def verify(_):
        s[K.KEY_ACCOUNT_SUB] = "sub-B"   # 驗證期間換了人
        return A.VerifyResult(ok=True)

    res = A.activate_pending(s, verify)
    assert res.error_code == ec.AUTH_REQUIRED
    assert K.KEY_ACTIVE_SHEET not in s and A.get_pending(s) is not None


def test_pending_changed_during_verify_does_not_activate():
    s = _logged_in()
    A.set_pending(s, "NEW", "新本")

    def verify(_):
        A.set_pending(s, "OTHER", "別本")
        return A.VerifyResult(ok=True)

    res = A.activate_pending(s, verify)
    assert res.error_code == ec.UNAVAILABLE
    assert K.KEY_ACTIVE_SHEET not in s
    assert A.get_pending(s).sheet_id == "OTHER"


# ── 帳號切換後舊 Active 失效；未登入 None ─────────────────────────────────
def test_account_switch_invalidates_old_active():
    s = _logged_in("sub-A")
    _activate(s, "A-BOOK", "A 的本")
    s[K.KEY_ACCOUNT_SUB] = "sub-B"
    assert A.get_active(s) is None
    s[K.KEY_ACCOUNT_SUB] = "sub-A"   # 換回來仍是同一個驗證紀錄（get_active 讀取無副作用）
    assert A.get_active(s).sheet_id == "A-BOOK"


@pytest.mark.parametrize("state", [
    {},
    {K.KEY_ACCOUNT_SUB: "sub-A"},                                   # 有 sub 沒 token
    {K.KEY_TOKENS: {"access_token": "AT"}},                         # 有 token 沒 sub
    {K.KEY_TOKENS: {"access_token": "AT"}, K.KEY_ACCOUNT_SUB: "  "},
    {K.KEY_TOKENS: "not-a-mapping", K.KEY_ACCOUNT_SUB: "sub-A"},
])
def test_not_logged_in_get_active_is_none(state):
    state[K.KEY_ACTIVE_SHEET] = {"sheet_id": "S", "name": "n", "verified_at": 1.0, "account_sub": "sub-A"}
    assert A.get_active(state) is None


def test_pending_login_does_not_count_as_logged_in():
    s = {K.KEY_PENDING_LOGIN: {"tokens": {"access_token": "X"}, "sub": "sub-A", "email": "e", "expires_at": 9e9},
         K.KEY_ACTIVE_SHEET: {"sheet_id": "S", "name": "n", "verified_at": 1.0, "account_sub": "sub-A"}}
    assert A.current_account_sub(s) is None and A.get_active(s) is None


@pytest.mark.parametrize("rec", [
    "S",
    {"sheet_id": "", "name": "n", "verified_at": 1.0, "account_sub": "sub-A"},
    {"sheet_id": "S", "name": None, "verified_at": 1.0, "account_sub": "sub-A"},
    {"sheet_id": "S", "name": "n", "verified_at": "1", "account_sub": "sub-A"},
    {"sheet_id": "S", "name": "n", "verified_at": True, "account_sub": "sub-A"},
    {"sheet_id": "S", "name": "n", "verified_at": 1.0},
])
def test_malformed_active_record_is_none(rec):
    s = _logged_in("sub-A")
    s[K.KEY_ACTIVE_SHEET] = rec
    assert A.get_active(s) is None


# ── personal_oauth.clear_session／logout 後兩者皆清 ───────────────────────
def test_clear_session_clears_active_and_pending():
    s = _logged_in()
    _activate(s, "OLD", "舊本")
    A.set_pending(s, "NEW", "新本")
    s["gsheet_tokens"] = {"access_token": "LEGACY"}   # 舊 UI key 不碰
    po.clear_session(s)
    assert A.get_active(s) is None and A.get_pending(s) is None
    assert K.KEY_ACTIVE_SHEET not in s and K.KEY_PENDING_SHEET not in s
    assert s == {"gsheet_tokens": {"access_token": "LEGACY"}}


# ── 錯誤碼必在全集 ────────────────────────────────────────────────────────
@pytest.mark.parametrize("bad", [None, "", "SOMETHING_ELSE", "auth_required"])
def test_verify_failure_requires_known_error_code(bad):
    with pytest.raises(ValueError):
        A.VerifyResult(ok=False, error_code=bad)


def test_verify_success_rejects_error_code():
    with pytest.raises(ValueError):
        A.VerifyResult(ok=True, error_code=ec.UNAVAILABLE)


def test_all_codes_used_by_module_are_in_taxonomy():
    tree = ast.parse(MOD_PATH.read_text(encoding="utf-8"))
    used = {n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "ec"}
    used.discard("ALL_ERROR_CODES")
    assert used and used <= ec.ALL_ERROR_CODES


def test_every_failure_path_returns_code_in_taxonomy():
    results = []
    results.append(A.activate_pending({}, _ok()[0]))
    results.append(A.activate_pending(_logged_in(), _ok()[0]))
    for code in ec.ALL_ERROR_CODES:
        s = _logged_in()
        A.set_pending(s, "S", "n")
        results.append(A.activate_pending(s, _fail(code)[0]))
    for r in results:
        assert not r.ok and r.error_code in ec.ALL_ERROR_CODES


# ── 靜態：不 fallback、不讀 secret、不碰舊樹 ────────────────────────────
def _non_docstring_strings(tree):
    doc_nodes = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                doc_nodes.add(id(first.value))
    return [n.value for n in ast.walk(tree)
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in doc_nodes]


@pytest.mark.parametrize("path", [MOD_PATH, KEYS_PATH])
def test_module_has_no_secret_or_fallback_access(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module)
    tops = {m.split(".")[0] for m in mods}
    assert not tops & {"infra", "repositories", "services", "ui", "ui_v2", "streamlit", "os",
                       "requests", "gspread", "importlib", "app", "fund_fetcher"}, tops
    assert tops <= {"__future__", "time", "collections", "dataclasses", "shared"}, tops
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"get_secret", "require_secret", "environ", "getenv", "secrets"}, names
    for text in _non_docstring_strings(tree):
        # secret 鍵名（POLICY_SHEET_ID／POOL_SHEET_ID／SETTINGS_SHEET_ID…）一律大寫；小寫欄名 sheet_id 不算
        assert "SHEET_ID" not in text, text
        assert "POLICY" not in text.upper(), text


def test_keys_module_is_pure_constants():
    tree = ast.parse(KEYS_PATH.read_text(encoding="utf-8"))
    assert not [n for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef, ast.Call))]
    for k in K.SESSION_KEYS:
        assert k.startswith(K.SESSION_PREFIX)
