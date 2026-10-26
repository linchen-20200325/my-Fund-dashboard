# -*- coding: utf-8 -*-
"""設定與診斷頁「Google 帳號」卡的來源層與畫面測試（批 3b-2；slow lane，需要 streamlit）。

⚠️ 本檔撰寫時本機沒有 streamlit：只能在 CI 驗證（來源層測試以替身 `st` 驗，仍需 import `ui_v2.set.source`）。
兩層：
(甲) 來源層 —— `source.login_load`／`login_act`／`_handle_oauth_callback` 以替身 `st`（session_state＋query_params）
     與替身橋接驗：callback 只處理一次、網址參數先拿掉、失敗只留錯誤代號、絕不自動確認、動作白名單。
(乙) 畫面層 —— AppTest 跑真 L2＋真 L1＋假 gspread 的設定頁腳本（同 `_plain_scan._set`），只把 `login_live` 換成替身，
     驗登入卡各狀態的元素、示範模式與「沒傳 login_live」的正式模式不畫、SET-4 與存檔鈕仍不出現。
"""
from __future__ import annotations

import html as _html
import pathlib
import sys
import types

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402
import _set_live_harness as H  # noqa: E402

from ui_v2.set import live, source  # noqa: E402

_URL = "https://accounts.google.com/o/oauth2/v2/auth?state=s&code_challenge=c"


# ═══════════════════════ (甲) 來源層 ═══════════════════════


class _Bridge:
    """替身橋接：記錄呼叫，回預先排好的結果。"""

    def __init__(self, status=None, begin=None):
        self.calls = []
        self._status = status if status is not None else {"login_state": "logged_out"}
        self._begin = begin if begin is not None else {"ok": True, "authorize_url": _URL}
        self.complete = {"ok": True, "pending_login_email": "new@example.com"}
        self.result = {"ok": True}

    def status(self, state):
        self.calls.append(("status",))
        if isinstance(self._status, Exception):
            raise self._status
        return self._status

    def begin_login(self, state):
        self.calls.append(("begin_login",))
        return self._begin

    def complete_login(self, state, code, state_param):
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
    monkeypatch.setattr(source, "st", st)
    monkeypatch.setattr(source, "personal_session", bridge)
    return types.SimpleNamespace(st=st, bridge=bridge)


def _names(env):
    return [c[0] for c in env.bridge.calls]


def test_callback_有code與state_網址參數先拿掉再處理一次_其他參數不動(env):
    env.st.query_params.update({"code": "C1", "state": "S1", "scope": "x", "authuser": "0", "scenario": "ok"})
    out = source.login_load()
    assert ("complete_login", "C1", "S1") in env.bridge.calls
    assert env.st.query_params == {"scenario": "ok"}
    assert out["notice"] is None


def test_callback_重跑時同一個state不再送第二次(env):
    env.st.query_params.update({"code": "C1", "state": "S1"})
    source.login_load()
    env.st.query_params.update({"code": "C1", "state": "S1"})   # 瀏覽器重送同一個網址
    source.login_load()
    assert _names(env).count("complete_login") == 1
    assert env.st.query_params == {}   # 第二次也把參數拿掉


def test_callback_新的state照常處理(env):
    env.st.query_params.update({"code": "C1", "state": "S1"})
    source.login_load()
    env.st.query_params.update({"code": "C2", "state": "S2"})
    source.login_load()
    assert _names(env).count("complete_login") == 2


def test_callback_只有code或只有state_不處理也不動網址(env):
    env.st.query_params.update({"code": "C1"})
    source.login_load()
    env.st.query_params.clear()
    env.st.query_params.update({"state": "S1"})
    source.login_load()
    assert "complete_login" not in _names(env)
    assert env.st.query_params == {"state": "S1"}


def test_callback失敗_只留錯誤代號_畫面讀一次就清(env):
    env.bridge.complete = {"ok": False, "error_code": "AUTH_STATE_INVALID"}
    env.st.query_params.update({"code": "C1", "state": "S1"})
    first = source.login_load()
    assert first["notice"] == "AUTH_STATE_INVALID"
    assert source.login_load()["notice"] is None
    assert "C1" not in repr(first) and "S1" not in repr(first)   # 授權碼與 state 不進畫面輸入


def test_callback處理本身炸了_落無法判定_不往上拋(env):
    def boom(*_a):
        raise RuntimeError("x")
    env.bridge.complete_login = boom
    env.st.query_params.update({"code": "C1", "state": "S1"})
    assert source.login_load()["notice"] == "UNAVAILABLE"


def test_狀態讀取炸了_status給None_不呼叫begin(env):
    env.bridge._status = RuntimeError("x")
    out = source.login_load()
    assert out["status"] is None and out["begin"] is None
    assert "begin_login" not in _names(env)


def test_只有未登入才取授權網址(env):
    for state in ("logged_in", "pending_login"):
        env.bridge.calls.clear()
        env.bridge._status = {"login_state": state}
        source.login_load()
        assert "begin_login" not in _names(env)
    env.bridge.calls.clear()
    env.bridge._status = {"login_state": "logged_out"}
    assert source.login_load()["begin"]["authorize_url"] == _URL


def test_待確認登入_載入絕不自動確認(env):
    env.bridge._status = {"login_state": "pending_login", "pending_login_email": "new@example.com"}
    env.st.query_params.update({"code": "C1", "state": "S1"})
    for _ in range(3):
        source.login_load()
    assert "confirm_login" not in _names(env)


@pytest.mark.parametrize("action, expected", [
    ("confirm", "confirm_login"), ("reject", "reject_login"), ("logout", "logout"), ("switch_go", "switch_account"),
])
def test_動作對到橋接的身分動作(env, action, expected):
    source.login_act(action)
    assert _names(env) == [expected]


def test_未知動作一律忽略(env):
    for bad in ("login", "use_pending", "select", "", None, 3, "CONFIRM"):
        source.login_act(bad)
    assert env.bridge.calls == []


def test_動作失敗_只留錯誤代號(env):
    env.bridge.result = {"ok": False, "error_code": "AUTH_STATE_INVALID"}
    source.login_act("confirm")
    assert source.login_load()["notice"] == "AUTH_STATE_INVALID"


def test_切換帳號_先問再切_取消就不切(env):
    env.bridge._status = {"login_state": "logged_in", "email": "me@example.com"}
    source.login_act("switch_ask")
    assert source.login_load()["switch_confirm"] is True
    assert env.bridge.calls.count(("switch_account",)) == 0
    source.login_act("switch_cancel")
    assert source.login_load()["switch_confirm"] is False
    source.login_act("switch_ask")
    source.login_act("switch_go")
    assert ("switch_account",) in env.bridge.calls
    env.bridge._status = {"login_state": "logged_out"}
    assert source.login_load()["switch_confirm"] is False


def test_切換確認旗標在不是已登入時被清掉(env):
    source.login_act("switch_ask")
    env.bridge._status = {"login_state": "logged_out"}
    assert source.login_load()["switch_confirm"] is False
    env.bridge._status = {"login_state": "logged_in", "email": "me@example.com"}
    assert source.login_load()["switch_confirm"] is False   # 旗標已清，不會因為之後又登入而復活


def test_login_live_是load與act兩個函式():
    assert set(source.login_live) == {"load", "act"}
    assert source.login_live["load"] is source.login_load and source.login_live["act"] is source.login_act


# ═══════════════════════ (乙) 畫面層（AppTest） ═══════════════════════


def _script(*, with_login=True):
    script = SCAN._set()
    needle = "page.render(load_live=source.load_live, save_live=source.save_setting, refetch_live=source.refetch)"
    assert needle in script
    if with_login:
        script = script.replace(needle, "import _set_live_harness as _H\n    "
                                "page.render(load_live=source.load_live, save_live=source.save_setting, "
                                "refetch_live=source.refetch, login_live=_H.LOGIN)")
    return script


def _install(status, begin=None, notice=None, switch=False):
    calls = []
    H.LOGIN.clear()
    H.LOGIN.update(
        load=lambda: {"status": status, "begin": begin, "notice": notice, "switch_confirm": switch},
        act=lambda action: calls.append(action),
    )
    return calls


@pytest.fixture(autouse=True)
def _clean_login():
    yield
    H.LOGIN.clear()


def _run(script):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(script, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _text(at):
    out = [_html.unescape(e.value) for e in at.markdown] + [e.value for e in at.caption]
    out += [b.label for b in at.button] + [e.label for e in at.expander]
    return "\n".join(out)


def _login_buttons(at):
    return {b.key: b for b in at.button if b.key and b.key.startswith("set_login_")}


def test_未登入_畫登入連結_不畫其他登入鈕():
    _install({"login_state": "logged_out"}, {"ok": True, "authorize_url": _URL})
    at = _run(_script())
    assert [e.label for e in at.expander if e.label == live.LOGIN_CARD_TITLE]
    text = _text(at)
    assert live.TEXT_LOGIN_LOGGED_OUT in text and live.TEXT_LOGIN_LOGGED_OUT_NOTE in text
    links = at.get("link_button")
    assert len(links) == 1 and links[0].proto.url == _URL and links[0].proto.label == live.LOGIN_BUTTON_LOGIN
    assert _login_buttons(at) == {}


def test_未設定Google登入_不畫登入連結():
    _install({"login_state": "logged_out"}, {"ok": False, "error_code": "UNAVAILABLE"})
    at = _run(_script())
    assert live.TEXT_LOGIN_NOT_CONFIGURED in _text(at)
    assert at.get("link_button") == [] and _login_buttons(at) == {}


def test_待確認登入_顯示帳號_沒按就不確認_按了才確認():
    calls = _install({"login_state": "pending_login", "pending_login_email": "new@example.com"})
    at = _run(_script())
    assert "以 new@example.com 登入？" in _text(at)
    assert set(_login_buttons(at)) == {"set_login_confirm", "set_login_reject"}
    at.run()
    assert calls == []   # 重畫幾次都不會自己確認
    _login_buttons(at)["set_login_confirm"].click().run()
    assert calls == ["confirm"]


def test_待確認登入_取消():
    calls = _install({"login_state": "pending_login", "pending_login_email": "new@example.com"})
    at = _run(_script())
    _login_buttons(at)["set_login_reject"].click().run()
    assert calls == ["reject"]


def test_已登入_顯示帳號_有登出與切換_沒有清除Active鈕():
    calls = _install({"login_state": "logged_in", "email": "me@example.com"})
    at = _run(_script())
    text = _text(at)
    assert "已登入 me@example.com" in text
    assert set(_login_buttons(at)) == {"set_login_switch_ask", "set_login_logout"}
    assert not any("清除" in b.label for b in _login_buttons(at).values())
    _login_buttons(at)["set_login_logout"].click().run()
    assert calls == ["logout"]


def test_切換帳號確認_畫出D2那一句():
    _install({"login_state": "logged_in", "email": "me@example.com"}, switch=True)
    at = _run(_script())
    assert live.TEXT_LOGIN_SWITCH_NOTE in _text(at)
    assert set(_login_buttons(at)) == {"set_login_switch_go", "set_login_switch_cancel"}


def test_讀不到登入狀態_畫無法判定():
    _install(None)
    at = _run(_script())
    text = _text(at)
    assert live.TEXT_LOGIN_UNKNOWN in text and live.TEXT_LOGIN_UNKNOWN_NOTE in text
    assert _login_buttons(at) == {} and at.get("link_button") == []


def test_正式模式沒傳login_live_不畫登入卡():
    _install({"login_state": "logged_in", "email": "me@example.com"})
    at = _run(_script(with_login=False))
    assert live.LOGIN_CARD_TITLE not in [e.label for e in at.expander]
    assert "me@example.com" not in _text(at)


def test_示範模式傳login_live_當場炸_不傳則畫面照舊():
    from streamlit.testing.v1 import AppTest

    _install({"login_state": "logged_out"}, {"ok": True, "authorize_url": _URL})
    script = (f"import sys\nsys.path.insert(0, {str(_ROOT)!r})\nsys.path.insert(0, {str(_HERE)!r})\n"
              "import _set_live_harness as H\nfrom ui_v2.set import page\npage.render(login_live=H.LOGIN)\n")
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert at.exception and "login_live" in at.exception[0].value
    demo = f"import sys\nsys.path.insert(0, {str(_ROOT)!r})\nfrom ui_v2.set import page\npage.render()\n"
    at = AppTest.from_string(demo, default_timeout=60)
    at.run()
    assert not at.exception
    assert live.LOGIN_CARD_TITLE not in [e.label for e in at.expander]


def test_登入卡存在時_第一階段唯讀不變_SET4不畫_沒有存檔鈕():
    _install({"login_state": "logged_in", "email": "me@example.com"})
    at = _run(_script())
    assert not [e for e in at.expander if e.label.startswith("參數編輯")]
    non_login = [b.label for b in at.button if not (b.key or "").startswith("set_login_")]
    assert "存檔" not in non_login
