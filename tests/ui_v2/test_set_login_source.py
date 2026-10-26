# -*- coding: utf-8 -*-
"""設定頁登入來源層的行為測試（批 3b-2；fast lane，不需要 streamlit）。

`ui_v2/set/source.py` 只在 import 時需要一個叫 `streamlit` 的模組；本檔在 import 當下放進替身模組、import 完立刻換回
（本機沒有 streamlit 時移除替身，免得別的檔的 `importorskip("streamlit")` 誤判成有），執行時再以替身 `st`
（session_state＋query_params 兩個 dict）與替身橋接取代 `source.st`、`source.personal_session`。
驗：載入絕不呼叫確認（即使待確認登入）、同 state 重放只處理一次、網址參數在處理之前先拿掉、動作白名單、
確認綁定「畫面上顯示的帳號」、切換要有 switch_ask 標記。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

_MISSING = object()


def _load_source_under_test():
    """以私有名字載入 `ui_v2/set/source.py`：不經 `import ui_v2.set.source`，所以 `ui_v2.set` 套件的 `source` 屬性與
    `sys.modules["ui_v2.set.source"]` 完全不被建立或改動；替身 `streamlit` 只在執行該檔的期間放在 `sys.modules`。
    名字掛在 `ui_v2.set` 底下（私有名，不是 `source`），檔內的相對 import（`from . import spec`）照常解析到真模組。
    執行期間新載入、而且握著替身的模組一併移除（只移這些，不動其他真模組）。"""
    stub = types.ModuleType("streamlit")
    saved = sys.modules.get("streamlit", _MISSING)
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("ui_v2.set._source_under_test", _ROOT / "ui_v2" / "set" / "source.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["streamlit"] = stub
    sys.modules["ui_v2.set._source_under_test"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if saved is _MISSING:
            sys.modules.pop("streamlit", None)
        else:
            sys.modules["streamlit"] = saved
        for name in set(sys.modules) - before:
            held = sys.modules.get(name)
            if name != "ui_v2.set._source_under_test" and held is not None and any(
                    v is stub for v in vars(held).values()):
                del sys.modules[name]
    return module, stub, saved


_STREAMLIT_BEFORE = sys.modules.get("streamlit", _MISSING)
source, _STUB, _SAVED = _load_source_under_test()


def test_載入不污染真的import圖_套件屬性與sys_modules不變():
    pkg = sys.modules.get("ui_v2.set")
    assert getattr(pkg, "source", None) is not source
    assert sys.modules.get("ui_v2.set.source") is not source
    now = sys.modules.get("streamlit", _MISSING)
    assert now is _STREAMLIT_BEFORE and now is not _STUB
    assert source.st is _STUB   # 被測模組握的是替身（執行時再換成測試用的 `st`）


_URL = "https://accounts.google.com/o/oauth2/v2/auth?state=s&code_challenge=c"
_ALL_PARAMS = ("code", "state", "scope", "authuser", "prompt", "hd", "error", "error_description", "iss")


class _Bridge:
    def __init__(self):
        self.calls = []
        self.status_value = {"login_state": "logged_out"}
        self.begin_value = {"ok": True, "authorize_url": _URL}
        self.complete = {"ok": True, "pending_login_email": "new@example.com"}
        self.result = {"ok": True}
        self.params_at_complete = None
        self.st = None

    def status(self, state):
        self.calls.append(("status",))
        if isinstance(self.status_value, Exception):
            raise self.status_value
        return self.status_value

    def begin_login(self, state):
        self.calls.append(("begin_login",))
        return self.begin_value

    def complete_login(self, state, code, state_param):
        self.params_at_complete = dict(self.st.query_params)   # 呼叫當下網址上還剩什麼
        self.calls.append(("complete_login", code, state_param))
        return self.complete

    def confirm_login(self, state):
        self.calls.append(("confirm_login",))
        return self.result

    def reject_login(self, state):
        self.calls.append(("reject_login",))
        return self.result

    def logout(self, state):
        self.calls.append(("logout",))
        return self.result

    def switch_account(self, state):
        self.calls.append(("switch_account",))
        return self.result


@pytest.fixture
def env(monkeypatch):
    bridge = _Bridge()
    st = types.SimpleNamespace(session_state={}, query_params={})
    bridge.st = st
    monkeypatch.setattr(source, "st", st)
    monkeypatch.setattr(source, "personal_session", bridge)
    return types.SimpleNamespace(st=st, bridge=bridge)


def _names(env):
    return [c[0] for c in env.bridge.calls]


# ───────────── callback ─────────────


def test_網址參數在complete_login之前就已拿掉_其他參數不動(env):
    env.st.query_params.update({p: "v" for p in _ALL_PARAMS})
    env.st.query_params.update({"code": "C1", "state": "S1", "scenario": "ok"})
    out = source.login_load()
    assert ("complete_login", "C1", "S1") in env.bridge.calls
    assert env.bridge.params_at_complete == {"scenario": "ok"}   # 呼叫當下九個參數都已不在網址上
    assert env.st.query_params == {"scenario": "ok"}
    assert out["notice"] is None


def test_同一個state重放_同一工作階段只處理一次(env):
    env.st.query_params.update({"code": "C1", "state": "S1"})
    source.login_load()
    env.st.query_params.update({"code": "C1", "state": "S1"})
    source.login_load()
    assert _names(env).count("complete_login") == 1
    assert env.st.query_params == {}


def test_新的state照常處理(env):
    for code, state in (("C1", "S1"), ("C2", "S2")):
        env.st.query_params.update({"code": code, "state": state})
        source.login_load()
    assert _names(env).count("complete_login") == 2


@pytest.mark.parametrize("params", [{"code": "C1"}, {"state": "S1"}])
def test_單獨的code或state_不處理_但從網址拿掉(env, params):
    env.st.query_params.update(params)
    out = source.login_load()
    assert "complete_login" not in _names(env)
    assert env.st.query_params == {}
    assert out["notice"] is None


def test_授權頁導回帶error_沒有code_記AUTH_REQUIRED_並拿掉參數(env):
    env.st.query_params.update({"error": "access_denied", "state": "S1", "error_description": "x", "iss": "y"})
    out = source.login_load()
    assert "complete_login" not in _names(env)
    assert env.st.query_params == {}
    assert out["notice"] == "AUTH_REQUIRED"
    assert source.login_load()["notice"] is None


def test_callback失敗_只留錯誤代號_畫面讀一次就清(env):
    env.bridge.complete = {"ok": False, "error_code": "AUTH_STATE_INVALID"}
    env.st.query_params.update({"code": "C1", "state": "S1"})
    first = source.login_load()
    assert first["notice"] == "AUTH_STATE_INVALID"
    assert source.login_load()["notice"] is None
    assert "C1" not in repr(first) and "S1" not in repr(first)


def test_callback處理本身炸了_落無法判定_不往上拋_只記例外類型(env, caplog):
    def boom(*_a):
        raise RuntimeError("secret-message-xyz")
    env.bridge.complete_login = boom
    env.st.query_params.update({"code": "C1", "state": "S1"})
    with caplog.at_level("WARNING"):
        assert source.login_load()["notice"] == "UNAVAILABLE"
    assert "RuntimeError" in caplog.text and "secret-message-xyz" not in caplog.text


def test_狀態讀取炸了_status給None_不呼叫begin(env, caplog):
    env.bridge.status_value = RuntimeError("secret-message-xyz")
    with caplog.at_level("WARNING"):
        out = source.login_load()
    assert out["status"] is None and out["begin"] is None
    assert "begin_login" not in _names(env)
    assert "secret-message-xyz" not in caplog.text


def test_只有未登入才取授權網址(env):
    for state in ("logged_in", "pending_login"):
        env.bridge.calls.clear()
        env.bridge.status_value = {"login_state": state}
        source.login_load()
        assert "begin_login" not in _names(env)
    env.bridge.calls.clear()
    env.bridge.status_value = {"login_state": "logged_out"}
    assert source.login_load()["begin"]["authorize_url"] == _URL


def test_載入絕不確認_即使待確認登入且網址帶callback(env):
    env.bridge.status_value = {"login_state": "pending_login", "pending_login_email": "new@example.com"}
    env.st.query_params.update({"code": "C1", "state": "S1"})
    for _ in range(3):
        source.login_load()
    assert "confirm_login" not in _names(env)


# ───────────── 動作 ─────────────


@pytest.mark.parametrize("action, expected", [("reject", "reject_login"), ("logout", "logout")])
def test_動作對到橋接的身分動作(env, action, expected):
    source.login_act(action)
    assert _names(env) == [expected]


def test_未知動作一律忽略(env):
    for bad in ("login", "use_pending", "select", "", None, 3, "CONFIRM"):
        source.login_act(bad)
        source.login_act(bad, "a@b.c")
    assert env.bridge.calls == []


def test_確認綁定畫面上顯示的帳號(env):
    env.bridge.status_value = {"login_state": "pending_login", "pending_login_email": "new@example.com"}
    source.login_act("confirm", "new@example.com")
    assert _names(env) == ["status", "confirm_login"]


@pytest.mark.parametrize("shown", ["old@example.com", "", None, 3, "NEW@example.com"])
def test_畫面上的帳號與目前待確認的不同_不確認(env, shown):
    env.bridge.status_value = {"login_state": "pending_login", "pending_login_email": "new@example.com"}
    source.login_act("confirm", shown)
    assert "confirm_login" not in _names(env)


@pytest.mark.parametrize("status", [
    {"login_state": "logged_in", "email": "new@example.com", "pending_login_email": "new@example.com"},
    {"login_state": "logged_out"}, None, RuntimeError("x")])
def test_目前不是待確認登入或讀不到_不確認(env, status):
    env.bridge.status_value = status
    source.login_act("confirm", "new@example.com")
    assert "confirm_login" not in _names(env)


def test_確認不帶帳號參數_不確認(env):
    env.bridge.status_value = {"login_state": "pending_login", "pending_login_email": "new@example.com"}
    source.login_act("confirm")
    assert "confirm_login" not in _names(env)


def test_動作失敗_只留錯誤代號(env):
    env.bridge.status_value = {"login_state": "pending_login", "pending_login_email": "new@example.com"}
    env.bridge.result = {"ok": False, "error_code": "AUTH_STATE_INVALID"}
    source.login_act("confirm", "new@example.com")
    assert source.login_load()["notice"] == "AUTH_STATE_INVALID"


def test_切換帳號_先問再切_取消就不切(env):
    env.bridge.status_value = {"login_state": "logged_in", "email": "me@example.com"}
    source.login_act("switch_ask")
    assert source.login_load()["switch_confirm"] is True
    assert ("switch_account",) not in env.bridge.calls
    source.login_act("switch_cancel")
    assert source.login_load()["switch_confirm"] is False
    source.login_act("switch_ask")
    source.login_act("switch_go")
    assert ("switch_account",) in env.bridge.calls


def test_switch_go沒有switch_ask標記_不切換(env):
    source.login_act("switch_go")
    assert "switch_account" not in _names(env)
    source.login_act("switch_ask")
    source.login_act("switch_cancel")
    source.login_act("switch_go")
    assert "switch_account" not in _names(env)


def test_switch_go的標記只能用一次(env):
    source.login_act("switch_ask")
    source.login_act("switch_go")
    source.login_act("switch_go")
    assert _names(env).count("switch_account") == 1


def test_切換確認旗標在不是已登入時被清掉(env):
    source.login_act("switch_ask")
    env.bridge.status_value = {"login_state": "logged_out"}
    assert source.login_load()["switch_confirm"] is False
    env.bridge.status_value = {"login_state": "logged_in", "email": "me@example.com"}
    assert source.login_load()["switch_confirm"] is False


def test_login_live是load與act兩個函式():
    assert set(source.login_live) == {"load", "act"}
    assert source.login_live["load"] is source.login_load and source.login_live["act"] is source.login_act
