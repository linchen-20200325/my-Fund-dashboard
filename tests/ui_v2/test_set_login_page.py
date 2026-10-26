# -*- coding: utf-8 -*-
"""設定與診斷頁「Google 帳號」卡的來源層與畫面測試（批 3b-2；slow lane，需要 streamlit）。

⚠️ 本檔撰寫時本機沒有 streamlit：只能在 CI 驗證。
來源層測試已搬到不需要 streamlit 的 `test_set_login_source.py`（fast lane）。本檔只剩畫面層 ——
AppTest 跑真 L2＋真 L1＋假 gspread 的設定頁腳本（同 `_plain_scan._set`），只把 `login_live` 換成替身，
     驗登入卡各狀態的元素、示範模式與「沒傳 login_live」的正式模式不畫、SET-4 與存檔鈕仍不出現。
"""
from __future__ import annotations

import html as _html
import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402
import _set_live_harness as H  # noqa: E402

from ui_v2.set import live  # noqa: E402

_URL = "https://accounts.google.com/o/oauth2/v2/auth?state=s&code_challenge=c"


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
        act=lambda action, *_arg: calls.append(action),
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


def test_橋接回UNAVAILABLE_畫無法判定_不畫登入連結_也不印尚未設定():
    """UNAVAILABLE 無法證明是「部署沒設定 Google 登入」（回修一：不再印「尚未設定」）。"""
    _install({"login_state": "logged_out"}, {"ok": False, "error_code": "UNAVAILABLE"})
    at = _run(_script())
    text = _text(at)
    assert live.TEXT_LOGIN_UNKNOWN in text and live.TEXT_LOGIN_NOT_CONFIGURED not in text
    assert at.get("link_button") == [] and _login_buttons(at) == {}


def test_待確認登入_確認鈕把畫面上顯示的帳號一起交給動作():
    got = []
    _install({"login_state": "pending_login", "pending_login_email": "new@example.com"})
    H.LOGIN["act"] = lambda action, *arg: got.append((action, arg))
    at = _run(_script())
    _login_buttons(at)["set_login_confirm"].click().run()
    assert got == [("confirm", ("new@example.com",))]


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
