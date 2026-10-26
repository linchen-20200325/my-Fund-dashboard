# -*- coding: utf-8 -*-
"""設定與診斷頁「試算表連線」卡（Sheet Picker）的畫面測試（批 3b-3；slow lane，需要 streamlit）。

⚠️ 本檔撰寫時本機沒有 streamlit：只能在 CI 驗證（純邏輯與來源層另有 fast lane 測試：
`test_set_picker_logic.py`、`test_set_picker_source.py`）。AppTest 跑真 L2＋真 L1＋假 gspread 的設定頁腳本
（同 `_plain_scan._set`），只把 `picker_live`（與 `login_live`）換成替身，驗：未登入不畫、登入後畫下拉與鈕、
待確認／使用中字樣、失敗時舊使用中、沒有「清除」控制項、示範模式傳 picker_live 當場炸、第一階段唯讀不變。
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

A = "1AAAAAAAAAAAAAAAAAAAA"
B = "1BBBBBBBBBBBBBBBBBBBB"
LIST_OK = {"ok": True, "sheets": [{"id": A, "name": "甲"}, {"id": B, "name": "乙"}]}


def _script(*, with_picker=True):
    script = SCAN._set()
    needle = "page.render(load_live=source.load_live, save_live=source.save_setting, refetch_live=source.refetch)"
    assert needle in script
    if with_picker:
        script = script.replace(needle, "import _set_live_harness as _H\n    "
                                "page.render(load_live=source.load_live, save_live=source.save_setting, "
                                "refetch_live=source.refetch, picker_live=_H.PICKER)")
    return script


def _status(login_state="logged_in", **kw):
    base = {"login_state": login_state, "email": "me@example.com", "pending_login_email": None,
            "pending_sheet": None, "active_sheet": None}
    base.update(kw)
    return base


def _install(status, listing=LIST_OK, notice=None):
    calls = []
    H.PICKER.clear()
    H.PICKER.update(
        load=lambda: {"status": status, "list": listing, "notice": notice},
        act=lambda action, *arg: calls.append((action, arg)),
    )
    return calls


@pytest.fixture(autouse=True)
def _clean():
    yield
    H.PICKER.clear()


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


def _picker_buttons(at):
    return {b.key: b for b in at.button if b.key and b.key.startswith("set_picker_")}


def test_未登入_整張卡不畫():
    for status in (_status("logged_out"), _status("pending_login", pending_login_email="n@example.com"), None):
        _install(status)
        at = _run(_script())
        assert live.PICKER_CARD_TITLE not in [e.label for e in at.expander]
        assert _picker_buttons(at) == {} and not at.selectbox


def test_已登入_畫下拉_選項只有清單內的_沒有預選():
    _install(_status())
    at = _run(_script())
    assert live.PICKER_CARD_TITLE in [e.label for e in at.expander]
    box = at.selectbox(key="set_picker_select")
    assert list(box.options) and len(box.options) == 2
    assert box.value is None   # 不猜、不預選
    assert live.TEXT_PICKER_NO_ACTIVE in _text(at)
    assert set(_picker_buttons(at)) == {"set_picker_relist"}   # 沒有待確認 → 沒有［使用這一本］


def test_選下拉_動作收到的是選項的id_且只是select():
    calls = _install(_status())
    at = _run(_script())
    at.selectbox(key="set_picker_select").select(B).run()
    assert calls == [("select", (B,))]
    assert not any(c[0] == "use" for c in calls)   # 選了不會自己驗證


def test_待確認_顯示待確認尚未使用_與使用這一本_綁定顯示的id():
    calls = _install(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0},
                             pending_sheet={"id": B, "name": "乙"}))
    at = _run(_script())
    text = _text(at)
    assert "待確認（尚未使用）：乙" in text and f"使用中：甲（{A}）" in text and "帳號：me@example.com" in text
    at.run()
    assert calls == []   # 重畫幾次都不會自己使用
    _picker_buttons(at)["set_picker_use"].click().run()
    assert calls == [("use", (B,))]


def test_使用失敗_畫失敗與舊使用中仍是_沒有已切換():
    _install(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0}, pending_sheet={"id": B, "name": "乙"}),
             notice={"kind": "use_fail", "code": "PERMISSION_DENIED", "name": "乙"})
    at = _run(_script())
    text = _text(at)
    assert "⛔ 無權限：切換沒有完成。" in text and "目前使用中仍是：甲（未變更）" in text and "已切換" not in text


def test_使用成功_畫已切換():
    _install(_status(active_sheet={"id": B, "name": "乙", "verified_at": 1.0}), notice={"kind": "use_ok", "name": "乙"})
    assert "◆ 已切換為：乙" in _text(_run(_script()))


def test_空清單_照實說沒有可選的_沒有下拉():
    _install(_status(), listing={"ok": True, "sheets": []})
    at = _run(_script())
    text = _text(at)
    assert live.TEXT_PICKER_EMPTY in text and live.TEXT_PICKER_EMPTY_NOTE in text
    assert not at.selectbox and set(_picker_buttons(at)) == {"set_picker_relist"}


def test_清單失敗_不畫下拉_給重新列出():
    calls = _install(_status(), listing={"ok": False, "error_code": "NETWORK_ERROR"})
    at = _run(_script())
    assert live.TEXT_PICKER_LIST_FAILED in _text(at) and not at.selectbox
    _picker_buttons(at)["set_picker_relist"].click().run()
    assert calls == [("relist", ())]


def test_沒有任何清除使用中的鈕():
    _install(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0}, pending_sheet={"id": B, "name": "乙"}))
    at = _run(_script())
    assert not any("清除" in b.label for b in at.button)
    assert set(_picker_buttons(at)) == {"set_picker_use", "set_picker_relist"}


def test_正式模式沒傳picker_live_不畫():
    _install(_status())
    at = _run(_script(with_picker=False))
    assert live.PICKER_CARD_TITLE not in [e.label for e in at.expander] and not at.selectbox


def test_示範模式傳picker_live_當場炸_不傳則畫面照舊():
    from streamlit.testing.v1 import AppTest

    _install(_status())
    script = (f"import sys\nsys.path.insert(0, {str(_ROOT)!r})\nsys.path.insert(0, {str(_HERE)!r})\n"
              "import _set_live_harness as H\nfrom ui_v2.set import page\npage.render(picker_live=H.PICKER)\n")
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert at.exception and "picker_live" in at.exception[0].value
    demo = f"import sys\nsys.path.insert(0, {str(_ROOT)!r})\nfrom ui_v2.set import page\npage.render()\n"
    at = AppTest.from_string(demo, default_timeout=60)
    at.run()
    assert not at.exception
    assert live.PICKER_CARD_TITLE not in [e.label for e in at.expander]


def test_第一階段唯讀不變_SET4不畫_沒有存檔鈕():
    _install(_status(pending_sheet={"id": B, "name": "乙"}))
    at = _run(_script())
    assert not [e for e in at.expander if e.label.startswith("參數編輯")]
    assert "存檔" not in [b.label for b in at.button if not (b.key or "").startswith("set_picker_")]


_URL = "https://accounts.google.com/o/oauth2/v2/auth?state=s&code_challenge=c"


def _script_both():
    script = SCAN._set()
    needle = "page.render(load_live=source.load_live, save_live=source.save_setting, refetch_live=source.refetch)"
    assert needle in script
    return script.replace(needle, "import _set_live_harness as _H\n    "
                          "page.render(load_live=source.load_live, save_live=source.save_setting, "
                          "refetch_live=source.refetch, login_live=_H.LOGIN, picker_live=_H.PICKER)")


def test_回修A_選本讀到登入失效後_同一次畫面的登入卡不再說已登入():
    """選本資料先讀：它把「session 已清掉」記下來；登入卡晚於它讀，必須如實顯示已過期、不能還是已登入。
    （替身以共用旗標模擬「選本先清 session、登入卡後讀」；若頁面改回先畫登入卡，旗標還沒設、登入卡會說已登入 → 紅燈。）"""
    flag = {"cleared": False}

    def picker_load():
        flag["cleared"] = True
        return {"status": _status("logged_out"), "list": None, "notice": None}

    def login_load():
        if flag["cleared"]:
            return {"status": _status("logged_out"), "begin": {"ok": True, "authorize_url": _URL},
                    "notice": "AUTH_EXPIRED", "switch_confirm": False}
        return {"status": _status("logged_in"), "begin": None, "notice": None, "switch_confirm": False}

    H.PICKER.clear()
    H.PICKER.update(load=picker_load, act=lambda *a: None)
    H.LOGIN.clear()
    H.LOGIN.update(load=login_load, act=lambda *a: None)
    try:
        at = _run(_script_both())
    finally:
        H.LOGIN.clear()
    text = _text(at)
    assert live.TEXT_LOGIN_EXPIRED in text and "已登入" not in text
    assert live.PICKER_CARD_TITLE not in [e.label for e in at.expander]


def test_回修D_待確認不在清單_畫面沒有使用這一本():
    _install(_status(pending_sheet={"id": B, "name": "乙"}), listing={"ok": True, "sheets": [{"id": A, "name": "甲"}]})
    at = _run(_script())
    assert "set_picker_use" not in _picker_buttons(at) and "待確認" not in _text(at)


def test_回修B_使用失敗未知代號_畫面不說讀不到試算表清單():
    _install(_status(active_sheet={"id": A, "name": "甲", "verified_at": 1.0}, pending_sheet={"id": B, "name": "乙"}),
             notice={"kind": "use_fail", "code": "UNAVAILABLE", "name": "乙"})
    text = _text(_run(_script()))
    assert "切換沒有完成，原因讀不到" in text and "讀不到試算表清單" not in text
