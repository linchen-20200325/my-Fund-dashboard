# -*- coding: utf-8 -*-
"""設定頁「試算表連線」來源層的行為測試（批 3b-3；fast lane，不需要 streamlit）。

載入方式同 `test_set_login_source.py`（替身 streamlit、私有名字載入 `ui_v2/set/source.py`）。與登入來源測試不同：
這裡的橋接是**真的** `services.v2_tables.personal_session` ＋ 真的 `shared.active_sheet`，只把網路那一層
（`infra.personal_oauth` 的 token 交換與身分、`repositories.personal_drive_repository` 的列清單與驗證）換成假的，
所以「只有驗證成功才換 Active」「失敗保留舊 Active」「只收最近一次清單內的 id」測的是真的狀態機，不是替身。
變異式檢查：把守衛拿掉（換成壞掉的版本）→ 同一個斷言必須失敗。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import time
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

import infra.personal_oauth as po  # noqa: E402
from services.v2_tables import personal_session as ps  # noqa: E402
from shared import active_sheet as asheet  # noqa: E402
from shared import ui_v2_error_codes as ec  # noqa: E402
from shared.personal_oauth_keys import KEY_PICKER_IDS  # noqa: E402

_MISSING = object()


def _load_source_under_test():
    stub = types.ModuleType("streamlit")
    saved = sys.modules.get("streamlit", _MISSING)
    before = set(sys.modules)
    spec = importlib.util.spec_from_file_location("ui_v2.set._picker_source_under_test", _ROOT / "ui_v2" / "set" / "source.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["streamlit"] = stub
    sys.modules["ui_v2.set._picker_source_under_test"] = module
    try:
        spec.loader.exec_module(module)
    finally:
        if saved is _MISSING:
            sys.modules.pop("streamlit", None)
        else:
            sys.modules["streamlit"] = saved
        for name in set(sys.modules) - before:
            held = sys.modules.get(name)
            if name != "ui_v2.set._picker_source_under_test" and held is not None and any(
                    v is stub for v in vars(held).values()):
                del sys.modules[name]
    return module


source = _load_source_under_test()

AT = "fake-access-SECRET-aaa"
RT = "fake-refresh-SECRET-bbb"
S1, S2, S3 = "1AAAAAAAAAAAAAAAAAAAA", "1BBBBBBBBBBBBBBBBBBBB", "1CCCCCCCCCCCCCCCCCCCC"


@pytest.fixture
def env(monkeypatch):
    class Env:
        identity = ("sub-A", "a@example.com")
        sheets = [{"id": S1, "name": "甲"}, {"id": S2, "name": "乙"}]
        list_exc = None
        verify_result = None   # None → ok
        list_calls = 0
        verify_calls = []

    e = Env()
    e.verify_calls = []
    monkeypatch.setattr(po, "load_client_config", lambda: po.ClientConfig("cid", "csecret", "https://x.example/cb"))
    monkeypatch.setattr(po, "exchange_code", lambda code, state, now=None: (po.consume_pending(state) and None) or {
        "access_token": AT, "refresh_token": RT, "expires_at": time.time() + 3600,
        "scope": " ".join(po.PERSONAL_OAUTH_SCOPES)})
    monkeypatch.setattr(po, "fetch_verified_identity", lambda tok: e.identity)
    monkeypatch.setattr(po, "_revoke_token", lambda t: po.LogoutResult(True, True, None))

    def fake_list(token):
        e.list_calls += 1
        if e.list_exc:
            raise e.list_exc
        return list(e.sheets)

    def fake_verify(token, sid):
        e.verify_calls.append(sid)
        if e.verify_result is not None:
            return e.verify_result
        return asheet.VerifyResult(ok=True, name="驗證名-" + sid[1:3])

    monkeypatch.setattr(ps.drive, "list_spreadsheets", fake_list)
    monkeypatch.setattr(ps.drive, "verify_spreadsheet", fake_verify)
    st = types.SimpleNamespace(session_state={}, query_params={})
    monkeypatch.setattr(source, "st", st)
    e.st = st
    return e


def _login(e):
    s = e.st.session_state
    assert ps.begin_login(s)["ok"]
    assert ps.complete_login(s, "code123", s[po.KEY_AUTH_PENDING_STATE])["ok"]
    assert ps.confirm_login(s)["ok"]


def _ids(out):
    return [x["id"] for x in out["list"]["sheets"]]


def _fail(code, detail=None):
    return asheet.VerifyResult(ok=False, error_code=code)


# ───────────── 只在正式登入後出現／才列清單 ─────────────


def test_未登入_不列清單_不呼叫Drive(env):
    out = source.picker_load()
    assert out["list"] is None and env.list_calls == 0


def test_待確認登入_也不列清單(env):
    s = env.st.session_state
    ps.begin_login(s)
    ps.complete_login(s, "c", s[po.KEY_AUTH_PENDING_STATE])
    assert ps.status(s)["login_state"] == "pending_login"
    assert source.picker_load()["list"] is None and env.list_calls == 0


def _assert_no_listing_when_logged_out(env, monkeypatch):
    # 狀態雖說未登入、卻帶著一個 email（刻意讓「帳號讀不到」那道守衛不介入，單獨檢驗登入檢查）
    monkeypatch.setattr(source, "_safe_status", lambda: {"login_state": "logged_out", "email": "a@example.com"})
    out = source.picker_load()
    assert out["list"] is None and source._KEY_PICKER_LIST not in env.st.session_state


def test_未登入_清單輸入是None_不留快取(env, monkeypatch):
    _assert_no_listing_when_logged_out(env, monkeypatch)


def test_mutation_登入檢查拿掉_未登入也會往下列清單就會紅燈(env, monkeypatch):
    """變異：`_logged_in` 恆真 → 未登入也進入列清單分支（清單輸入不再是 None、並留下快取）→ 上面的斷言必須失敗。"""
    monkeypatch.setattr(source, "_logged_in", lambda status: True)
    with pytest.raises(AssertionError):
        _assert_no_listing_when_logged_out(env, monkeypatch)


def test_登入後列一次清單_之後用快取_不每次重打(env):
    _login(env)
    first = source.picker_load()
    assert _ids(first) == [S1, S2] and env.list_calls == 1
    source.picker_load()
    source.picker_load()
    assert env.list_calls == 1


def test_重新列出_丟快取_下次重列(env):
    _login(env)
    source.picker_load()
    env.sheets = [{"id": S3, "name": "丙"}]
    source.picker_act("relist")
    assert _ids(source.picker_load()) == [S3] and env.list_calls == 2


def test_換帳號_舊帳號的清單快取不沿用(env):
    _login(env)
    source.picker_load()
    env.identity = ("sub-B", "b@example.com")
    env.sheets = [{"id": S3, "name": "丙"}]
    assert ps.switch_account(env.st.session_state)["ok"]
    assert source.picker_load()["list"] is None   # 登出狀態：清掉快取
    _login(env)
    assert _ids(source.picker_load()) == [S3]


def test_登出後清單與提示一併清掉(env):
    _login(env)
    source.picker_load()
    source.picker_act("select", S1)
    ps.logout(env.st.session_state)
    out = source.picker_load()
    assert out["list"] is None and source._KEY_PICKER_LIST not in env.st.session_state


def test_列清單失敗_只交錯誤代號_不當成空清單(env):
    _login(env)
    env.list_exc = ps.drive.PersonalDriveError(ec.NETWORK_ERROR)
    out = source.picker_load()
    assert out["list"] == {"ok": False, "error_code": ec.NETWORK_ERROR}


def test_列清單遇到登入失效_以動作之後的狀態為準_變未登入(env):
    _login(env)
    env.list_exc = ps.drive.PersonalDriveError(ec.AUTH_EXPIRED)
    out = source.picker_load()
    assert out["status"]["login_state"] == "logged_out" and out["list"] is None


def test_列清單炸了_落UNAVAILABLE_只記例外類型(env, monkeypatch, caplog):
    _login(env)

    def boom(state):
        raise RuntimeError("secret-message-xyz")
    monkeypatch.setattr(source.personal_session, "list_for_picker", boom)
    with caplog.at_level("WARNING"):
        out = source.picker_load()
    assert out["list"] == {"ok": False, "error_code": "UNAVAILABLE"}
    assert "RuntimeError" in caplog.text and "secret-message-xyz" not in caplog.text


# ───────────── 選本：只收最近一次清單內的 id；只設 Pending ─────────────


def _assert_select_only_listed(env):
    _login(env)
    source.picker_load()
    source.picker_act("select", "1ZZZZZZZZZZZZZZZZZZZZ")   # 手打／猜的 id
    assert ps.status(env.st.session_state)["pending_sheet"] is None
    assert env.st.session_state[source._KEY_PICKER_NOTICE]["code"] == ec.SHEET_NOT_FOUND
    source.picker_act("select", S1)
    assert ps.status(env.st.session_state)["pending_sheet"] == {"id": S1, "name": "甲"}


def test_選本只收清單內的id_選到的只是Pending_不是Active(env):
    _assert_select_only_listed(env)
    st = ps.status(env.st.session_state)
    assert st["active_sheet"] is None and env.verify_calls == []   # 選本不驗證、不切換


def test_mutation_選本守衛拿掉_橋接白名單也拿掉就會紅燈(env, monkeypatch):
    """變異：來源層守衛放行任何 id，且橋接也不再檢查白名單 → 手打的 id 進了 Pending → 斷言必須失敗。"""
    monkeypatch.setattr(source, "_displayed_ids", lambda: frozenset({"1ZZZZZZZZZZZZZZZZZZZZ"}))
    real_select = ps.select_pending
    monkeypatch.setattr(ps, "select_pending",
                        lambda state, sid, name="": (asheet.set_pending(state, sid, "手打"), {"ok": True})[1])
    with pytest.raises(AssertionError):
        _assert_select_only_listed(env)
    monkeypatch.setattr(ps, "select_pending", real_select)


def test_選本_來源層守衛單獨成立_橋接有白名單也有(env):
    _login(env)
    source.picker_load()
    # 來源層：id 不在畫面清單 → 根本不會呼叫橋接
    calls = []
    orig = source.personal_session.select_pending
    source.personal_session.select_pending = lambda *a, **k: (calls.append(a), orig(*a, **k))[1]
    try:
        source.picker_act("select", "1ZZZZZZZZZZZZZZZZZZZZ")
        source.picker_act("select", None)
        source.picker_act("select", 123)
    finally:
        source.personal_session.select_pending = orig
    assert calls == []


def test_清單被重列後_舊清單的id不能再選(env):
    _login(env)
    source.picker_load()
    env.sheets = [{"id": S3, "name": "丙"}]
    source.picker_act("relist")
    source.picker_load()
    source.picker_act("select", S1)   # S1 已不在最近一次清單
    assert ps.status(env.st.session_state)["pending_sheet"] is None


def test_橋接白名單獨立擋_即使來源層快取還留著舊清單(env):
    _login(env)
    source.picker_load()
    env.st.session_state.pop(KEY_PICKER_IDS)   # 橋接白名單沒了、來源層快取還在
    source.picker_act("select", S1)
    assert ps.status(env.st.session_state)["pending_sheet"] is None
    assert env.st.session_state[source._KEY_PICKER_NOTICE]["code"] == ec.SHEET_NOT_FOUND


# ───────────── 使用這一本：成功才換；失敗留舊；綁定畫面上的待確認 ─────────────


def _pend(env, sid):
    source.picker_act("select", sid)
    return ps.status(env.st.session_state)["pending_sheet"]


def _assert_switch_only_on_success(env):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    source.picker_act("use", S1)
    assert ps.status(env.st.session_state)["active_sheet"]["id"] == S1   # 先有一本舊的 Active
    _pend(env, S2)
    env.verify_result = _fail(ec.PERMISSION_DENIED)
    source.picker_act("use", S2)
    st = ps.status(env.st.session_state)
    assert st["active_sheet"]["id"] == S1   # 失敗：舊 Active 不變
    return st


def test_驗證失敗_舊Active不變_Pending保留_只交錯誤代號(env):
    st = _assert_switch_only_on_success(env)
    assert st["active_sheet"]["id"] == S1 and st["pending_sheet"]["id"] == S2
    assert env.st.session_state[source._KEY_PICKER_NOTICE] == {"kind": "use_fail", "code": ec.PERMISSION_DENIED, "name": "乙"}


def test_mutation_先切換再驗證_舊Active被洗掉就會紅燈(env, monkeypatch):
    """變異：`activate_pending` 不驗證就先換 Active、再回報失敗 → 失敗後 Active 變成待確認那一本 → 斷言必須失敗
    （且是「舊 Active 不變」那一條斷言失敗，不是別的錯）。"""
    def bad_activate(state, verify):
        p = asheet.get_pending(state)
        sub = asheet.current_account_sub(state)
        state[asheet.KEY_ACTIVE_SHEET] = {"sheet_id": p.sheet_id, "name": p.name, "verified_at": 1.0, "account_sub": sub}
        return asheet.ActivationResult(ok=False, error_code=ec.PERMISSION_DENIED, message="x")
    monkeypatch.setattr(asheet, "activate_pending", bad_activate)
    with pytest.raises(AssertionError) as info:
        _assert_switch_only_on_success(env)
    assert info.value.args  # 斷言訊息存在（pytest 重寫斷言會帶出 Active id）


def test_驗證成功_才換Active_且清掉Pending(env):
    _login(env)
    source.picker_load()
    _pend(env, S2)
    assert ps.status(env.st.session_state)["active_sheet"] is None   # 選了還沒用 → 不是 Active
    source.picker_act("use", S2)
    st = ps.status(env.st.session_state)
    assert st["active_sheet"]["id"] == S2 and st["active_sheet"]["name"] == "驗證名-BB"
    assert env.st.session_state[source._KEY_PICKER_NOTICE]["kind"] == "use_ok"
    assert env.verify_calls == [S2]   # 驗證只在按下［使用這一本］後才開始


@pytest.mark.parametrize("code", [ec.PERMISSION_DENIED, ec.SHEET_NOT_FOUND, ec.SCHEMA_INVALID, ec.NETWORK_ERROR,
                                  ec.UPSTREAM_ERROR, ec.UNAVAILABLE])
def test_各種驗證失敗_舊Active都不變(env, code):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    source.picker_act("use", S1)
    _pend(env, S2)
    env.verify_result = _fail(code)
    source.picker_act("use", S2)
    st = ps.status(env.st.session_state)
    assert st["active_sheet"]["id"] == S1 and env.st.session_state[source._KEY_PICKER_NOTICE]["code"] == code


def test_驗證時登入失效_清session_Active不再可用(env):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    env.verify_result = _fail(ec.AUTH_EXPIRED)
    source.picker_act("use", S1)
    st = ps.status(env.st.session_state)
    assert st["login_state"] == "logged_out" and st["active_sheet"] is None
    assert source.picker_load()["list"] is None


def test_使用鈕綁定畫面上的待確認_與目前Pending不同就不驗證不切換(env):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    source.picker_act("use", S2)   # 畫面上顯示的是 S2，但目前 Pending 是 S1
    assert env.verify_calls == [] and ps.status(env.st.session_state)["active_sheet"] is None
    for bad in (None, "", "  ", 5, "1ZZZZZZZZZZZZZZZZZZZZ"):
        source.picker_act("use", bad)
    assert env.verify_calls == []


def test_沒有Pending時按使用_不動作(env):
    _login(env)
    source.picker_load()
    source.picker_act("use", S1)
    assert env.verify_calls == [] and ps.status(env.st.session_state)["active_sheet"] is None


def test_未登入時任何動作都不做(env):
    for action, arg in (("select", S1), ("use", S1), ("relist", None)):
        source.picker_act(action, arg)
    assert env.verify_calls == [] and env.list_calls == 0 and source._KEY_PICKER_NOTICE not in env.st.session_state


@pytest.mark.parametrize("action", ["clear", "clear_active", "delete", "", None, "USE", "use ", 7, ("use",)])
def test_動作白名單_沒有清除Active_未知動作什麼都不做(env, action):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    source.picker_act("use", S1)
    before = ps.status(env.st.session_state)
    source.picker_act(action, S1)
    assert ps.status(env.st.session_state) == before


def test_動作白名單與畫面層同步():
    from ui_v2.set import live
    assert tuple(source._PICKER_ACTIONS) == tuple(live.PICKER_ACTIONS)


def test_動作炸了_只記例外類型_交UNAVAILABLE_Active不變(env, monkeypatch, caplog):
    _login(env)
    source.picker_load()
    _pend(env, S1)

    def boom(state):
        raise RuntimeError("secret-message-xyz")
    monkeypatch.setattr(source.personal_session, "use_pending", boom)
    with caplog.at_level("WARNING"):
        source.picker_act("use", S1)
    assert ps.status(env.st.session_state)["active_sheet"] is None
    assert env.st.session_state[source._KEY_PICKER_NOTICE]["code"] == "UNAVAILABLE"
    assert "RuntimeError" in caplog.text and "secret-message-xyz" not in caplog.text


def test_提示讀一次就清(env):
    _login(env)
    source.picker_load()
    source.picker_act("select", "1ZZZZZZZZZZZZZZZZZZZZ")
    assert source.picker_load()["notice"]["code"] == ec.SHEET_NOT_FOUND
    assert source.picker_load()["notice"] is None


def test_交給畫面的輸入不含權杖(env):
    _login(env)
    out = source.picker_load()
    _pend(env, S1)
    out = source.picker_load()
    blob = repr(out) + repr(env.st.session_state.get(source._KEY_PICKER_LIST))
    assert AT not in blob and RT not in blob and "code_verifier" not in blob


def test_不跨session持久化_source沒有任何寫檔或寫入Sheet的呼叫():
    import ast
    tree = ast.parse((_ROOT / "ui_v2" / "set" / "source.py").read_text(encoding="utf-8"))
    fn_names = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
                and n.name in ("picker_load", "picker_act", "_displayed_ids", "_clean_listing", "_safe_status", "_notice")}
    assert fn_names == {"picker_load", "picker_act", "_displayed_ids", "_clean_listing", "_safe_status", "_notice"}
    for fn in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in fn_names):
        for node in ast.walk(fn):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("open", "exec", "eval"), fn.name
            if isinstance(node, ast.Attribute):
                assert node.attr not in ("write_text", "write_bytes", "save_setting", "set_pending", "activate_pending",
                                         "clear_pending", "access_target", "worksheet", "update"), (fn.name, node.attr)


# ───────────── 回修一：登入失效轉給登入卡；下拉元件值；M3／M4；email 讀不到 ─────────────

_WIDGET = "set_picker_select"


def _assert_expired_reaches_login_card(env):
    out = source.login_load()
    assert out["status"]["login_state"] == "logged_out" and out["notice"] == ec.AUTH_EXPIRED


def test_列清單遇到登入失效_登入卡讀得到已過期_且讀到的是清掉之後的狀態(env):
    _login(env)
    env.list_exc = ps.drive.PersonalDriveError(ec.AUTH_EXPIRED)
    source.picker_load()   # 頁面先讀選本資料（會清 session 並留下提示），再讀登入卡
    _assert_expired_reaches_login_card(env)


def test_使用時登入失效_登入卡讀得到已過期(env):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    env.verify_result = _fail(ec.AUTH_EXPIRED)
    source.picker_act("use", S1)
    _assert_expired_reaches_login_card(env)


def test_mutation_不轉給登入卡_登入失效就無聲消失(env, monkeypatch):
    monkeypatch.setattr(source, "_login_notice_if_expired", lambda code: None)
    _login(env)
    env.list_exc = ps.drive.PersonalDriveError(ec.AUTH_EXPIRED)
    source.picker_load()
    with pytest.raises(AssertionError):
        _assert_expired_reaches_login_card(env)


def test_其他失敗代號不轉給登入卡(env):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    env.verify_result = _fail(ec.PERMISSION_DENIED)
    source.picker_act("use", S1)
    assert source._KEY_NOTICE not in env.st.session_state


def test_下拉元件值_與Pending不一致就丟掉(env):
    _login(env)
    env.st.session_state[_WIDGET] = S2   # 殘值：沒有 Pending
    source.picker_load()
    assert _WIDGET not in env.st.session_state
    _pend(env, S1)
    env.st.session_state[_WIDGET] = S1   # 與 Pending 一致 → 保留
    source.picker_load()
    assert env.st.session_state[_WIDGET] == S1


def test_登出與重列_下拉元件值一併丟掉(env):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    env.st.session_state[_WIDGET] = S1
    source.picker_act("relist")
    assert _WIDGET not in env.st.session_state
    env.st.session_state[_WIDGET] = S1
    ps.logout(env.st.session_state)
    source.picker_load()
    assert _WIDGET not in env.st.session_state


def test_選本被拒_下拉元件值丟掉(env):
    _login(env)
    source.picker_load()
    env.st.session_state[_WIDGET] = "1ZZZZZZZZZZZZZZZZZZZZ"
    source.picker_act("select", "1ZZZZZZZZZZZZZZZZZZZZ")
    assert _WIDGET not in env.st.session_state


def test_清掉下拉選擇_arg是None_當成沒事_不顯示找不到(env):
    _login(env)
    source.picker_load()
    source.picker_act("select", None)
    assert source._KEY_PICKER_NOTICE not in env.st.session_state


def test_元件key與page一致():
    import ast
    tree = ast.parse((_ROOT / "ui_v2" / "set" / "page.py").read_text(encoding="utf-8"))
    vals = [n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Constant)
            and any(isinstance(t, ast.Name) and t.id == "_PICKER_WIDGET_KEY" for t in n.targets)]
    assert vals == [source._KEY_PICKER_WIDGET]


def _seed_pending_and_cache(env):
    _login(env)
    source.picker_load()
    _pend(env, S1)
    ps.logout(env.st.session_state)   # 登出會清橋接的 Pending；下面再手動塞回「殘留」的狀態
    env.st.session_state[source._KEY_PICKER_LIST] = {"email": "a@example.com", "result": {
        "ok": True, "sheets": [{"id": S1, "name": "甲"}]}}


def _assert_act_inert_when_logged_out(env):
    calls = []
    for name in ("select_pending", "use_pending", "list_for_picker"):
        setattr(source.personal_session, name, lambda *a, _n=name, **k: calls.append(_n) or {"ok": False})
    source.picker_act("select", S1)
    source.picker_act("use", S1)
    source.picker_act("relist")
    assert calls == []


def test_M3_未登入時動作不碰L2_即使殘留清單快取(env, monkeypatch):
    _seed_pending_and_cache(env)
    for name in ("select_pending", "use_pending", "list_for_picker"):
        monkeypatch.setattr(source.personal_session, name, getattr(source.personal_session, name))   # 事後還原
    _assert_act_inert_when_logged_out(env)


def test_M3_mutation_登入檢查拿掉_動作就會碰L2(env, monkeypatch):
    _seed_pending_and_cache(env)
    for name in ("select_pending", "use_pending", "list_for_picker"):
        monkeypatch.setattr(source.personal_session, name, getattr(source.personal_session, name))
    monkeypatch.setattr(source, "_logged_in", lambda status: True)
    monkeypatch.setattr(source, "_safe_status", lambda: {"login_state": "logged_out", "email": "a@example.com",
                                                         "pending_sheet": {"id": S1, "name": "甲"}})
    with pytest.raises(AssertionError):
        _assert_act_inert_when_logged_out(env)


def _assert_foreign_cache_relisted(env):
    _login(env)   # 登入為 a@example.com
    env.st.session_state[source._KEY_PICKER_LIST] = {"email": "b@example.com", "result": {
        "ok": True, "sheets": [{"id": S3, "name": "別人的"}]}}
    out = source.picker_load()
    assert env.list_calls == 1 and _ids(out) == [S1, S2]


def test_M4_快取屬於別的帳號_重列(env):
    _assert_foreign_cache_relisted(env)


def test_M4_mutation_快取檢查拿掉_會沿用別人的清單(env, monkeypatch):
    monkeypatch.setattr(source, "_cache_valid", lambda rec, email: isinstance(rec, dict))
    with pytest.raises(AssertionError):
        _assert_foreign_cache_relisted(env)


def test_帳號讀不到_不列清單_不信快取_落無法判定_不每次重打(env, monkeypatch):
    _login(env)
    monkeypatch.setattr(source, "_safe_status", lambda: {"login_state": "logged_in", "email": None,
                                                         "pending_sheet": None, "active_sheet": None})
    env.st.session_state[source._KEY_PICKER_LIST] = {"email": None, "result": {"ok": True, "sheets": [{"id": S3}]}}
    for _ in range(3):
        out = source.picker_load()
        assert out["list"] is None
    assert env.list_calls == 0
