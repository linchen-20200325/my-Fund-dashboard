# -*- coding: utf-8 -*-
"""設定與診斷頁「Google 帳號」卡的純邏輯測試（批 3b-2；不需要 streamlit）。

依據：`docs/v2/65_set_wireframe_and_cap_gate_01_02.md` 第 B、C、D 節；
`docs/evidence/decisions/2026-10-26_ui_v2_implementation_security_gate_decisions.md` J-2／J-3／J-9／J-10。
驗：讀模型（`ui_v2/set/live.py::login_view`）各狀態與各錯誤代號、待確認登入的優先序與「沒有帳號就沒有確認鈕」、
畫面字零權杖零指示句、這幾枚鈕不是寫入控制；以及原始碼層的結構守衛（不讀平台登入身分、只呼叫橋接的身分動作）。
"""
from __future__ import annotations

import ast
import pathlib
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

from shared import ui_v2_error_codes as ec  # noqa: E402
from ui_v2.set import live, logic  # noqa: E402

_SET_DIR = _ROOT / "ui_v2" / "set"
_URL = "https://accounts.google.com/o/oauth2/v2/auth?state=s&code_challenge=c"


def _status(login_state, **kw):
    base = {"login_state": login_state, "email": None, "pending_login_email": None,
            "pending_sheet": None, "active_sheet": None}
    base.update(kw)
    return base


def _view(status, begin=None, notice=None, switch_confirm=False):
    return live.login_view({"status": status, "begin": begin, "notice": notice, "switch_confirm": switch_confirm})


def _labels(view):
    return [b["label"] for b in view["buttons"]]


def _actions(view):
    return [b["action"] for b in view["buttons"]]


# ───────────── 各狀態 ─────────────


def test_未登入_有授權網址_畫登入鈕且帶網址():
    v = _view(_status("logged_out"), {"ok": True, "authorize_url": _URL})
    assert v["state"] == "logged_out"
    assert v["lines"] == [live.TEXT_LOGIN_LOGGED_OUT, live.TEXT_LOGIN_LOGGED_OUT_NOTE]
    assert v["buttons"] == [{"action": "login", "label": live.LOGIN_BUTTON_LOGIN, "url": _URL}]


def test_未登入_授權網址不是Google端點_不畫連結():
    for bad in ("http://evil.example/x", "https://accounts.google.com.evil.example/x", "", None, 3):
        v = _view(_status("logged_out"), {"ok": True, "authorize_url": bad})
        assert v["state"] == "unknown" and v["buttons"] == [], bad


def test_橋接回UNAVAILABLE_不印尚未設定_落無法判定_不畫登入鈕():
    """UNAVAILABLE 也代表暫時或內部失敗，無法證明是「部署沒設定 Google 登入」→ 不得印 B-1 那句。"""
    v = _view(_status("logged_out"), {"ok": False, "error_code": ec.UNAVAILABLE})
    assert v["state"] == "unknown" and v["buttons"] == []
    assert v["lines"] == [live.TEXT_LOGIN_UNKNOWN, live.TEXT_LOGIN_UNKNOWN_NOTE]
    for every in _every_view():
        assert live.TEXT_LOGIN_NOT_CONFIGURED not in every["lines"]


@pytest.mark.parametrize("begin", [None, "x", 3, [], {"ok": True}, {"ok": False}, {"ok": False, "error_code": "WAT"}])
def test_未登入_橋接回不出可用結果_落無法判定_不畫登入鈕(begin):
    v = _view(_status("logged_out"), begin)
    assert v["state"] == "unknown" and v["buttons"] == []
    assert live.TEXT_LOGIN_UNKNOWN in v["lines"]


@pytest.mark.parametrize("status", [None, {}, [], "x", {"login_state": "logged_in_maybe"}, {"login_state": None}])
def test_讀不到登入狀態_B5_絕不當成已登入(status):
    v = _view(status, {"ok": True, "authorize_url": _URL})
    assert v["state"] == "unknown" and v["buttons"] == []
    assert v["lines"] == [live.TEXT_LOGIN_UNKNOWN, live.TEXT_LOGIN_UNKNOWN_NOTE]


def test_輸入本身不是dict_也不拋():
    for bad in (None, 3, "x", []):
        assert live.login_view(bad)["state"] == "unknown"


def test_已登入_清楚顯示目前帳號_有切換與登出_沒有任何清除Active鈕():
    v = _view(_status("logged_in", email="me@example.com"))
    assert v["state"] == "logged_in"
    assert v["lines"][0] == "已登入 me@example.com"
    assert live.LOGIN_METHOD_LINE in v["lines"] and live.LOGIN_SCOPE_LINE in v["lines"]
    assert _actions(v) == ["switch_ask", "logout"]
    assert _labels(v) == [live.LOGIN_BUTTON_SWITCH, live.LOGIN_BUTTON_LOGOUT]
    assert not any("清除" in label or "清空" in label for label in _labels(v))


@pytest.mark.parametrize("email", [None, "", "   ", 3])
def test_已登入但帳號讀不到_不留空_不猜(email):
    v = _view(_status("logged_in", email=email))
    assert v["lines"][0] == live.TEXT_LOGIN_LOGGED_IN_NO_EMAIL


def test_待確認登入_顯示帳號_要使用者明確按確認_也能取消():
    v = _view(_status("pending_login", pending_login_email="new@example.com"))
    assert v["state"] == "pending_login"
    assert v["lines"] == ["以 new@example.com 登入？"]
    assert _actions(v) == ["confirm", "reject"]
    assert _labels(v) == [live.LOGIN_BUTTON_CONFIRM, live.LOGIN_BUTTON_CANCEL]


def test_待確認登入優先於已登入_且畫的是待確認的帳號不是舊帳號():
    # `personal_session.status` 在有待確認登入時把 login_state 給成 pending_login（即使同時有正式登入）。
    v = _view(_status("pending_login", email="old@example.com", pending_login_email="new@example.com"))
    assert v["state"] == "pending_login"
    text = "\n".join(v["lines"])
    assert "new@example.com" in text and "old@example.com" not in text
    assert "confirm" in _actions(v) and "logout" not in _actions(v)


@pytest.mark.parametrize("email", [None, "", "  ", 5])
def test_待確認登入_看不到帳號就不給確認鈕(email):
    v = _view(_status("pending_login", pending_login_email=email))
    assert "confirm" not in _actions(v)
    assert _actions(v) == ["reject"]
    assert live.TEXT_LOGIN_UNKNOWN in v["lines"]


def test_切換帳號先確認_D2_可取消():
    v = _view(_status("logged_in", email="me@example.com"), switch_confirm=True)
    assert live.TEXT_LOGIN_SWITCH_NOTE in v["lines"]
    assert _actions(v) == ["switch_go", "switch_cancel"]


def test_切換確認旗標只在已登入時有效():
    for st in (_status("logged_out"), _status("pending_login", pending_login_email="a@b.c")):
        v = _view(st, {"ok": True, "authorize_url": _URL}, switch_confirm=True)
        assert "switch_go" not in _actions(v)


# ───────────── 錯誤代號 ─────────────


@pytest.mark.parametrize("code", sorted(ec.ALL_ERROR_CODES))
def test_九個錯誤代號都有非空畫面字_而且絕不呈現成已登入或成功(code):
    lines = live.login_error_lines(code)
    assert lines and all(isinstance(x, str) and x for x in lines)
    for line in lines:
        assert "已登入" not in line and "成功" not in line
    # 每一行狀態都帶符號或文字原因，不是只有顏色（58 U-21）
    assert lines[0][0] in "⛔◷⬜"


def test_未知代號與非字串_落無法判定():
    for code in ("NOPE", None, 5, ""):
        assert live.login_error_lines(code) == [live.TEXT_LOGIN_UNKNOWN, live.TEXT_LOGIN_UNKNOWN_NOTE]


def test_錯誤分類字句():
    assert live.login_error_lines(ec.AUTH_EXPIRED) == [live.TEXT_LOGIN_EXPIRED, live.TEXT_LOGIN_EXPIRED_NOTE]
    assert live.login_error_lines(ec.AUTH_STATE_INVALID)[0] == live.TEXT_LOGIN_FAILED
    assert live.login_error_lines(ec.PERMISSION_DENIED)[0] == live.TEXT_LOGIN_FAILED
    assert live.login_error_lines(ec.NETWORK_ERROR) == live.login_error_lines(ec.UPSTREAM_ERROR)


@pytest.mark.parametrize("code", sorted(ec.ALL_ERROR_CODES - {ec.UNAVAILABLE}))
def test_callback失敗後_未登入畫面給重新登入_同一位置(code):
    v = _view(_status("logged_out"), {"ok": True, "authorize_url": _URL}, notice=code)
    assert v["state"] == "logged_out" and v["error_code"] == code
    assert v["buttons"] == [{"action": "login", "label": live.LOGIN_BUTTON_RELOGIN, "url": _URL}]
    assert live.TEXT_LOGIN_LOGGED_OUT not in v["lines"]   # 錯誤取代「未登入」那句，不並列


def test_動作失敗的錯誤字畫在目前狀態之上_不改變目前狀態():
    v = _view(_status("pending_login", pending_login_email="a@b.c"), notice=ec.AUTH_STATE_INVALID)
    assert v["lines"][0] == live.TEXT_LOGIN_FAILED and v["lines"][-1] == "以 a@b.c 登入？"
    v = _view(_status("logged_in", email="a@b.c"), notice=ec.NETWORK_ERROR)
    assert v["state"] == "logged_in" and v["lines"][0] == live.TEXT_LOGIN_FAILED


def test_授權頁導回帶error_AUTH_REQUIRED_畫登入沒有完成_不是讀不到登入狀態():
    v = _view(_status("logged_out"), {"ok": True, "authorize_url": _URL}, notice=ec.AUTH_REQUIRED)
    assert v["lines"] == [live.TEXT_LOGIN_FAILED, live.TEXT_LOGIN_REASON_CANCELLED]
    assert live.TEXT_LOGIN_UNKNOWN_NOTE not in v["lines"]
    assert v["buttons"][0]["label"] == live.LOGIN_BUTTON_RELOGIN


def test_確認鈕帶畫面上顯示的帳號():
    v = _view(_status("pending_login", pending_login_email="new@example.com"))
    confirm = next(b for b in v["buttons"] if b["action"] == "confirm")
    assert confirm["arg"] == "new@example.com"
    assert all("arg" not in b for b in v["buttons"] if b["action"] != "confirm")


# ───────────── 不變式：零權杖、零指示句、零禁詞、不是寫入控制 ─────────────

_SECRET_STATUS = {"access_token": "tok-SECRET-1", "refresh_token": "rt-SECRET-2", "code_verifier": "ver-SECRET-3",
                  "code": "auth-SECRET-4"}


def _every_view():
    out = []
    url = _URL
    for st in (_status("logged_out"), _status("logged_in", email="me@example.com"),
               _status("pending_login", pending_login_email="new@example.com"), None):
        st = None if st is None else {**st, **_SECRET_STATUS}
        for begin in (None, {"ok": True, "authorize_url": url}, {"ok": False, "error_code": ec.UNAVAILABLE}):
            for notice in (None, *sorted(ec.ALL_ERROR_CODES)):
                for switch in (False, True):
                    out.append(_view(st, begin, notice, switch))
    return out


def test_任何狀態的讀模型都不含權杖或授權碼():
    for v in _every_view():
        blob = repr(v)
        for secret in _SECRET_STATUS.values():
            assert secret not in blob
        for word in ("access_token", "refresh_token", "code_verifier", "client_secret"):
            assert word not in blob


def test_畫面字零指示句_零方向詞_零禁詞():
    lines = [line for v in _every_view() for line in v["lines"]]
    assert lines
    assert all("請" not in line for line in lines)            # 58 U-32：原因只描述狀態
    assert logic.scan_forbidden(lines) == {}
    labels = [b["label"] for v in _every_view() for b in v["buttons"]]
    for label in labels:
        for word in logic.FORBIDDEN_BUTTON_WORDS:
            assert word not in label


def test_按鈕只在白名單動作內_不是寫入控制():
    allowed = set(live.LOGIN_ACTIONS) | {"login"}
    for v in _every_view():
        for b in v["buttons"]:
            assert b["action"] in allowed
            assert "_writes" not in b and "_action_kind" not in b   # 不在 `logic` 的按鈕表裡，不經 readonly.strip
            assert ("url" in b) == (b["action"] == "login")
            assert ("arg" in b) == (b["action"] == "confirm")


def test_ui_v2_set_只有登入動作_沒有任何寫入動作代號():
    assert set(live.LOGIN_ACTIONS) == {"confirm", "reject", "logout", "switch_ask", "switch_cancel", "switch_go"}


# ───────────── 原始碼結構守衛 ─────────────


def _set_py_files():
    return sorted(_SET_DIR.glob("*.py"))


_BANNED_ST_ATTRS = {"user", "experimental_user", "login", "logout", "context"}


def _identity_hits(tree, label="x"):
    """找：`st.<平台登入身分相關名>`（含別名）、`getattr(st, …)`、`from streamlit import …`、`import streamlit.<子模組>`。"""
    aliases = {"st", "streamlit"}
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "streamlit" and a.asname:
                    aliases.add(a.asname)
                elif a.name.startswith("streamlit."):
                    hits.append(f"{label}:{node.lineno} import {a.name}")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "streamlit":
            hits.append(f"{label}:{node.lineno} from streamlit import …")
        if isinstance(node, ast.Attribute) and node.attr in _BANNED_ST_ATTRS:
            if isinstance(node.value, ast.Name) and node.value.id in aliases:
                hits.append(f"{label}:{node.lineno} st.{node.attr}")
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "getattr"
                and node.args and isinstance(node.args[0], ast.Name) and node.args[0].id in aliases):
            hits.append(f"{label}:{node.lineno} getattr(st, …)")
    return hits


def test_set頁原始碼不讀平台登入身分_AST():
    """J-10：個人 OAuth 與平台登入身分 namespace 分離；本頁一律只用 session_state／query_params。
    用 AST（不是字串比對，所以本檔與註解不會自己命中）。"""
    hits = []
    for path in _set_py_files():
        hits += _identity_hits(ast.parse(path.read_text(encoding="utf-8")), path.name)
    assert hits == []


@pytest.mark.parametrize("code", [
    "import streamlit as st\nx = st.user\n",
    "import streamlit as st\nx = st.experimental_user\n",
    "import streamlit as st\nst.login()\n",
    "import streamlit as st\nst.logout()\n",
    "import streamlit as st\nx = st.context\n",
    "import streamlit as s2\nx = s2.user\n",
    "from streamlit import user\n",
    "from streamlit import session_state\n",
    "import streamlit.web as w\n",
    "import streamlit as st\ny = getattr(st, name)\n",
])
def test_AST偵測器本身咬得到_負控(code):
    assert _identity_hits(ast.parse(code))


def test_AST偵測器不誤報正常用法():
    assert _identity_hits(ast.parse("import streamlit as st\nst.session_state['a'] = 1\nst.query_params.get('x')\n")) == []


def test_source只呼叫橋接的身分動作_不碰試算表寫入():
    tree = ast.parse((_SET_DIR / "source.py").read_text(encoding="utf-8"))
    used = {n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "personal_session"}
    # ~~本檔原寫 used 恰為七個身分動作、且不含 Picker 三個~~ → 2026-10-26 批 3b-3（狀態更新，不是漏刪）：source 加上
    # Picker／使用這一本的三個橋接動作（`list_for_picker`／`select_pending`／`use_pending`）。身分七個一個不少；
    # 仍然沒有 `access_target`（讀取試算表內容不在本批）、沒有任何 Sheet 寫入動作（用到的名字恰為下列十個）。
    assert used == {"complete_login", "status", "begin_login", "confirm_login", "reject_login", "logout",
                    "switch_account", "list_for_picker", "select_pending", "use_pending"}
    assert not used & {"access_target"}


def test_source的callback處理_先拿掉網址參數_再呼叫complete_login():
    tree = ast.parse((_SET_DIR / "source.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_handle_oauth_callback")
    delete_line = min(n.lineno for n in ast.walk(fn) if isinstance(n, ast.Delete))
    call_line = min(n.lineno for n in ast.walk(fn) if isinstance(n, ast.Call)
                    and isinstance(n.func, ast.Attribute) and n.func.attr == "complete_login")
    assert delete_line < call_line


def test_page的登入卡只在login_live有傳時畫_且在strip之後():
    src = (_SET_DIR / "page.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "render")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
             and n.func.id == "_render_login"]
    assert len(calls) == 1
    parents = {c: p for p in ast.walk(fn) for c in ast.iter_child_nodes(p)}
    guard = parents[parents[calls[0]]]   # Call → Expr → If
    assert isinstance(guard, ast.If) and ast.unparse(guard.test) == "login_live is not None"
    strip = next(n for n in ast.walk(fn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "readonly.strip_write_controls")
    assert strip.lineno < calls[0].lineno
