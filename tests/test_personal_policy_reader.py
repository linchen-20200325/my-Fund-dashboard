# -*- coding: utf-8 -*-
"""批 3b-4：持倉／保單的「個人 Active Sheet」唯讀讀取（L1 `personal_policy_reader` ＋ L2 `alo_holdings.load_alo_tables_active`）。

快速車道（不需要網路、不需要 streamlit 畫面）。網路以 `requests.get` 替身注入（只換最底層，L1 的 header／錯誤對應照跑真的）。
釘住的事：
- 快取鍵含 account_sub（跨帳號不外洩）——並以「拿掉 sub 的變異版鍵」證明該測試真的會紅（變異檢查）；
- 只快取成功；
- 沒有 Active ＝ 沒有讀取：`POLICY_SHEET_ID`／服務帳戶／網路都不得被碰（任一被碰就紅），L1 原始碼也不得出現它們；
- token 只在 Authorization header：不在 URL／params／例外／錯誤文字；
- `ACTOR == "oauth"`；
- 只有該有的模組 import `personal_session`；hld／alo 的 source 不再呼叫服務帳戶那條 `load_alo_tables`。
"""
from __future__ import annotations

import ast
import pathlib
import re
import sys
import types

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("pandas")
pytest.importorskip("gspread")
requests = pytest.importorskip("requests")

from repositories import personal_drive_repository as drive  # noqa: E402
from repositories import personal_policy_reader as reader  # noqa: E402
from repositories import policy_supplement_repository as sup  # noqa: E402
from services.v2_tables import alo_holdings, personal_session  # noqa: E402
from shared import ui_v2_error_codes as ec  # noqa: E402

SHEET = "SHEET_ID_ABCDEFGHIJ"
TOKEN_A = "tok-A-zzz-1f2e3d"
TOKEN_B = "tok-B-zzz-9a8b7c"
SUB_A, SUB_B = "sub-A", "sub-B"

POLICY_HEADER = ["保單編號", "基金代號", "基金名稱", "幣別", "級別", "淨投資金額", "現金給付%", "持有單位數", "平均買入單位成本", "平均買入匯率"]
SUPP_HEADER = ["保單編號", "基金代號", "持有起始日", "最後核對日", "類別"]
PROFILE_HEADER = ["保單編號", "保單名稱", "發行單位", "計價幣別", "累計已繳保費（新臺幣元）", "生效日", "狀態"]


def _workbook(fund_code="AB123", invest="100000"):
    return {
        "P-001": [POLICY_HEADER, ["P-001", fund_code, "測試基金", "USD", "core", invest, "", "10", "5", "30"]],
        "_持倉補充": [SUPP_HEADER, ["P-001", fund_code, "2024-01-01", "2026-10-01", "成長"]],
        "_保單資料": [PROFILE_HEADER, ["P-001", "保單一", "某壽險", "USD", "1000000", "2024-01-01", "active"]],
    }


class _Resp:
    def __init__(self, status, payload):
        self.status_code, self._p = status, payload

    def json(self):
        return self._p


class Net:
    """`requests.get` 替身：依 token 回不同的活頁簿（證明快取沒有串帳號）；記每一次呼叫。"""

    def __init__(self, by_token, status=200, on_call=None):
        self.by_token, self.status, self.calls, self.on_call = by_token, status, [], on_call

    def __call__(self, url, params=None, headers=None, timeout=None, allow_redirects=None):
        if self.on_call:
            self.on_call()
        self.calls.append({"url": url, "params": params, "headers": dict(headers or {}), "allow_redirects": allow_redirects})
        if self.status != 200:
            return _Resp(self.status, {})
        book = self.by_token[(headers or {})["Authorization"].removeprefix("Bearer ")]
        if url.endswith("values:batchGet"):
            ranges = params["ranges"]
            titles = [r.strip("'").replace("''", "'") for r in ranges]
            return _Resp(200, {"valueRanges": [{"values": book[t]} for t in titles]})
        return _Resp(200, {"sheets": [{"properties": {"title": t}} for t in book]})


@pytest.fixture(autouse=True)
def _fresh_cache():
    reader.clear_cache()
    yield
    reader.clear_cache()


def _use(monkeypatch, net):
    monkeypatch.setattr(drive.requests, "get", net)


def _load(sub, token, mask=lambda s: s):
    return reader.load_workbook_tables((SHEET, token), account_sub=sub, mask=mask)


# ═══════════════════════ 讀取形狀與來源標示 ═══════════════════════

def test_讀到保單分頁與兩張補充分頁_形狀同服務帳戶路徑_actor為oauth(monkeypatch):
    net = Net({TOKEN_A: _workbook()})
    _use(monkeypatch, net)
    out = _load(SUB_A, TOKEN_A)
    assert reader.ACTOR == "oauth" and out["actor"] == "oauth"
    assert [r["fund_code"] for r in out["policy"]["rows"]] == ["AB123"]
    assert out["policy"]["rows"][0]["_tab"] == "P-001" and out["policy"]["rows"][0]["_row"] == 2
    assert out["policy"]["skipped_tabs"] == [] and out["policy"]["invest_twd_parse_errors"] == []
    assert set(out["supplement"]) == {sup.TAB_HOLDING_SUPPLEMENT, sup.TAB_POLICY_PROFILE}
    assert len(net.calls) == 2    # 一次分頁名、一次批次讀值


def test_L2_Active路徑_端到端_算出持倉列且標actor(monkeypatch):
    net = Net({TOKEN_A: _workbook()})
    _use(monkeypatch, net)
    monkeypatch.setattr(personal_session, "access_target", lambda state: (SHEET, TOKEN_A, SUB_A))
    out = alo_holdings.load_alo_tables_active({}, [])
    assert out["actor"] == "oauth"
    assert [h["fund_code"] for h in out["holding"]] == ["AB123"]
    assert [p["policy_id"] for p in out["policy"]] == ["P-001"]


def test_沒有保單分頁_是SCHEMA_INVALID_不是空持倉(monkeypatch):
    book = {"_持倉補充": [SUPP_HEADER], "Policies": [POLICY_HEADER]}
    _use(monkeypatch, Net({TOKEN_A: book}))
    with pytest.raises(drive.PersonalDriveError) as e:
        _load(SUB_A, TOKEN_A)
    assert e.value.code == ec.SCHEMA_INVALID and e.value.reason == "no_policy_tab"


def test_保單分頁標頭壞_該分頁略過並列出_全壞則SCHEMA_INVALID(monkeypatch):
    book = _workbook()
    book["P-002"] = [["保單編號", "保單編號", ""], ["x", "y", "z"]]
    _use(monkeypatch, Net({TOKEN_A: book}))
    out = _load(SUB_A, TOKEN_A)
    assert [s["tab"] for s in out["policy"]["skipped_tabs"]] == ["P-002"]
    assert [r["_tab"] for r in out["policy"]["rows"]] == ["P-001"]
    only_bad = {"P-002": book["P-002"]}
    reader.clear_cache()
    _use(monkeypatch, Net({TOKEN_A: only_bad}))
    with pytest.raises(drive.PersonalDriveError) as e:
        _load(SUB_A, TOKEN_A)
    assert e.value.code == ec.SCHEMA_INVALID and e.value.reason == "policy_header"   # 不是「缺少保單分頁」


@pytest.mark.parametrize("status,code", [(401, ec.AUTH_EXPIRED), (403, ec.PERMISSION_DENIED), (404, ec.SHEET_NOT_FOUND),
                                         (429, ec.UPSTREAM_ERROR), (500, ec.UPSTREAM_ERROR)])
def test_HTTP失敗_對應九code之一(monkeypatch, status, code):
    _use(monkeypatch, Net({TOKEN_A: _workbook()}, status=status))
    with pytest.raises(drive.PersonalDriveError) as e:
        _load(SUB_A, TOKEN_A)
    assert e.value.code == code and code in ec.ALL_ERROR_CODES


def test_缺注入_沒有任何fallback(monkeypatch):
    _use(monkeypatch, lambda *a, **k: pytest.fail("缺注入時不得發任何請求"))
    for target, sub, code in [(None, SUB_A, ec.AUTH_REQUIRED), ((SHEET, ""), SUB_A, ec.AUTH_REQUIRED),
                              ((SHEET, TOKEN_A), "", ec.AUTH_REQUIRED), (("../x", TOKEN_A), SUB_A, ec.SHEET_NOT_FOUND)]:
        with pytest.raises(drive.PersonalDriveError) as e:
            reader.load_workbook_tables(target, account_sub=sub, mask=lambda s: s)
        assert e.value.code == code


# ═══════════════════════ 快取：鍵含 account_sub ═══════════════════════

def _cross_account_assertion():
    """帳號 A 先讀、帳號 B 讀**同一個 sheet id**：B 必須自己打請求、拿到 B 的內容，不得讀到 A 的快取。"""
    net = Net({TOKEN_A: _workbook(fund_code="AAA11"), TOKEN_B: _workbook(fund_code="BBB22")})
    return net


def test_快取鍵含account_sub_跨帳號不外洩(monkeypatch):
    net = _cross_account_assertion()
    _use(monkeypatch, net)
    a = _load(SUB_A, TOKEN_A)
    b = _load(SUB_B, TOKEN_B)
    assert [r["fund_code"] for r in a["policy"]["rows"]] == ["AAA11"]
    assert [r["fund_code"] for r in b["policy"]["rows"]] == ["BBB22"]
    assert len(net.calls) == 4                       # 兩個帳號各自讀了兩個請求
    _load(SUB_A, TOKEN_A)
    assert len(net.calls) == 4                       # 同帳號 60 秒內命中快取
    assert reader.cache_key(SUB_A, SHEET)[0] == SUB_A and reader.cache_key(SUB_A, SHEET) != reader.cache_key(SUB_B, SHEET)


def test_變異檢查_鍵拿掉sub_上一條就會紅(monkeypatch):
    """證明「快取鍵含 sub」那條測試有牙：把鍵換成不含 sub 的版本，同一組斷言必須失敗。"""
    monkeypatch.setattr(reader, "cache_key", lambda account_sub, sheet_id, what="workbook_values": (sheet_id, what))
    net = _cross_account_assertion()
    _use(monkeypatch, net)
    _load(SUB_A, TOKEN_A)
    b = _load(SUB_B, TOKEN_B)
    with pytest.raises(AssertionError):
        assert [r["fund_code"] for r in b["policy"]["rows"]] == ["BBB22"]
    assert len(net.calls) == 2    # B 沒有自己打請求：吃到了 A 的快取（這就是外洩）


def test_cache_key原始碼_sub在鍵裡():
    tree = ast.parse((_ROOT / "repositories" / "personal_policy_reader.py").read_text(encoding="utf-8"))
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "cache_key")
    ret = next(n for n in ast.walk(fn) if isinstance(n, ast.Return))
    assert isinstance(ret.value, ast.Tuple) and any("account_sub" in ast.dump(e) for e in ret.value.elts)


def test_只快取成功_失敗下次重打(monkeypatch):
    bad = Net({TOKEN_A: _workbook()}, status=500)
    _use(monkeypatch, bad)
    with pytest.raises(drive.PersonalDriveError):
        _load(SUB_A, TOKEN_A)
    good = Net({TOKEN_A: _workbook()})
    _use(monkeypatch, good)
    assert _load(SUB_A, TOKEN_A)["policy"]["rows"]
    assert len(bad.calls) == 1 and len(good.calls) == 2


def test_快取內容不含token(monkeypatch):
    _use(monkeypatch, Net({TOKEN_A: _workbook()}))
    _load(SUB_A, TOKEN_A)
    assert TOKEN_A not in repr(reader._CACHE)


# ═══════════════════════ 沒有 fallback ═══════════════════════

def test_沒有Active_不碰POLICY_SHEET_ID_服務帳戶_網路(monkeypatch):
    """環境變數設了 `POLICY_SHEET_ID`、也「有」服務帳戶：沒有 Active 時任何一條被碰到就紅。"""
    monkeypatch.setenv("POLICY_SHEET_ID", "ENV_POLICY_SHEET_SENTINEL")
    touched = []

    def boom(name):
        def fn(*a, **k):
            touched.append(name)
            raise AssertionError(f"沒有 Active 時不得碰 {name}")
        return fn

    monkeypatch.setattr(sup, "policy_sheet_id", boom("policy_sheet_id"))
    monkeypatch.setattr(sup, "_service_account", boom("_service_account"))
    monkeypatch.setattr(sup, "_make_client", boom("_make_client"))
    monkeypatch.setattr(sup, "get_secret", boom("get_secret"))
    monkeypatch.setattr(sup, "load_policy_holding_rows", boom("load_policy_holding_rows"))
    monkeypatch.setattr(sup, "load_supplement_tabs", boom("load_supplement_tabs"))
    monkeypatch.setattr(drive.requests, "get", boom("requests.get"))
    for state in ({}, {"anything": 1}):
        with pytest.raises(alo_holdings.ActiveSourceError) as e:
            alo_holdings.load_alo_tables_active(state, ["x"])
        assert e.value.code in (ec.AUTH_REQUIRED, ec.UNAVAILABLE)
    assert touched == []


def test_L1原始碼_沒有POLICY_SHEET_ID_服務帳戶_環境變數():
    text = (_ROOT / "repositories" / "personal_policy_reader.py").read_text(encoding="utf-8")
    code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    tree = ast.parse(text)
    # 排除 docstring（說明文字會提到這些名字，是在說「沒有」）
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)) and ast.get_docstring(node):
            code = code.replace(ast.get_docstring(node), "")
    for banned in ("POLICY_SHEET_ID", "policy_sheet_id", "get_secret", "google_service_account", "os.environ",
                   "SECRET_KEY", "_service_account", "_make_client", "gspread"):
        assert banned not in code, banned
    imported = {m for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))
                for m in ([a.name for a in n.names] if isinstance(n, ast.Import) else [n.module])}
    assert not any(m.startswith(("infra.config", "infra.gspread_retry", "infra.source_backoff")) for m in imported)


# ═══════════════════════ token 不外洩 ═══════════════════════

def test_token只在Authorization_header_不在URL_params(monkeypatch):
    net = Net({TOKEN_A: _workbook()})
    _use(monkeypatch, net)
    _load(SUB_A, TOKEN_A)
    for call in net.calls:
        assert call["headers"] == {"Authorization": f"Bearer {TOKEN_A}"}
        assert TOKEN_A not in call["url"] and TOKEN_A not in repr(call["params"])
        assert call["allow_redirects"] is False


@pytest.mark.parametrize("failure", [requests.Timeout("t " + TOKEN_A), requests.ConnectionError("c " + TOKEN_A),
                                     requests.RequestException("r " + TOKEN_A)])
def test_網路例外_訊息與例外鏈不含token(monkeypatch, failure):
    def raiser(*a, **k):
        raise failure
    monkeypatch.setattr(drive.requests, "get", raiser)
    with pytest.raises(drive.PersonalDriveError) as e:
        _load(SUB_A, TOKEN_A)
    assert TOKEN_A not in str(e.value) and TOKEN_A not in repr(e.value)
    assert e.value.__context__ is None and e.value.__cause__ is None
    assert e.value.code in (ec.NETWORK_ERROR, ec.UPSTREAM_ERROR)


def test_補充分頁標頭不符_不把儲存格原文帶上畫面_也不帶token(monkeypatch):
    """標頭原文可能是使用者資料（或含 token）：Active 路徑不得把它放進例外／訊息，只回固定細分原因。"""
    secret_cell = f"類別{TOKEN_A}-使用者自填"
    book = _workbook()
    book["_持倉補充"] = [SUPP_HEADER[:-1] + [secret_cell], book["_持倉補充"][1]]
    _use(monkeypatch, Net({TOKEN_A: book}))
    monkeypatch.setattr(personal_session, "access_target", lambda state: (SHEET, TOKEN_A, SUB_A))
    with pytest.raises(alo_holdings.ActiveSourceError) as e:
        alo_holdings.load_alo_tables_active({}, [])
    err = e.value
    assert err.code == ec.SCHEMA_INVALID and err.reason == "supplement_header" and err.tab == sup.TAB_HOLDING_SUPPLEMENT
    for text in (str(err), repr(err), repr(err.args)):
        assert TOKEN_A not in text and "使用者自填" not in text
    assert err.__cause__ is None and err.__suppress_context__


def test_L2失敗只帶code(monkeypatch):
    _use(monkeypatch, Net({TOKEN_A: _workbook()}, status=401))
    monkeypatch.setattr(personal_session, "access_target", lambda state: (SHEET, TOKEN_A, SUB_A))
    with pytest.raises(alo_holdings.ActiveSourceError) as e:
        alo_holdings.load_alo_tables_active({}, [])
    assert e.value.code == ec.AUTH_EXPIRED and str(e.value) == ec.AUTH_EXPIRED
    assert TOKEN_A not in repr(e.value) and e.value.__context__ is None


# ═══════════════════════ 分層與 import 釘死 ═══════════════════════

def _py_files():
    skip = {"tests", ".git", "node_modules", ".venv", "venv"}
    for p in _ROOT.rglob("*.py"):
        if not (set(p.relative_to(_ROOT).parts) & skip):
            yield p


def _imports(path):
    out = set()
    for n in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(n, ast.Import):
            out.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom) and n.module:
            out.add(n.module)
            out.update(f"{n.module}.{a.name}" for a in n.names)
    return out


def test_只有該有的模組import_personal_session():
    owners = sorted(str(p.relative_to(_ROOT)).replace("\\", "/") for p in _py_files()
                    if "services.v2_tables.personal_session" in _imports(p))
    assert owners == ["services/v2_tables/alo_holdings.py", "ui_v2/set/source.py"], owners


def test_只有alo_holdings與personal_session_import_personal_policy_reader():
    owners = sorted(str(p.relative_to(_ROOT)).replace("\\", "/") for p in _py_files()
                    if "repositories.personal_policy_reader" in _imports(p))
    # `personal_session` 只為登出／換帳號／AUTH_EXPIRED 時丟掉該帳號的快取（`drop_account`）
    assert owners == ["services/v2_tables/alo_holdings.py", "services/v2_tables/personal_session.py"], owners


def test_hld_alo的source與page_不直接碰個人憑證或兩條L1讀取():
    banned = {"services.v2_tables.personal_session", "infra.personal_oauth", "repositories.personal_policy_reader",
              "repositories.policy_supplement_repository", "repositories.personal_drive_repository"}
    for rel in ("ui_v2/hld/source.py", "ui_v2/alo/source.py", "ui_v2/hld/page.py", "ui_v2/alo/page.py"):
        assert not (_imports(_ROOT / rel) & banned), rel


def test_hld_alo的source不再呼叫服務帳戶那條load_alo_tables():
    for rel in ("ui_v2/hld/source.py", "ui_v2/alo/source.py"):
        text = (_ROOT / rel).read_text(encoding="utf-8")
        code = re.sub(r"#.*", "", text)
        assert "load_alo_tables_active" in code, rel
        assert not re.search(r"\bload_alo_tables\s*\(", code), rel
        assert "POLICY_SHEET_ID" not in code and "google_service_account" not in code, rel


def test_production中呼叫服務帳戶那條load_alo_tables的檔_恰為settings_store():
    """hld／alo 之外還有誰在用舊路徑（登記，不改）：set 頁「重新取數」（`settings_store.refetch_nav`）。多一個檔就紅。"""
    callers = sorted(str(p.relative_to(_ROOT)).replace("\\", "/") for p in _py_files()
                     if re.search(r"\bload_alo_tables\s*\(", re.sub(r"#.*", "", p.read_text(encoding="utf-8")))
                     and p.name != "alo_holdings.py")
    assert callers == ["services/v2_tables/settings_store.py"], callers


# ═══════════════════════ 批 3b-4 稽核回修 ═══════════════════════

def _session_state(sub=SUB_A):
    from infra import personal_oauth as po
    from shared.personal_oauth_keys import KEY_ACCOUNT_SUB, KEY_TOKENS

    return {KEY_TOKENS: {"access_token": TOKEN_A}, KEY_ACCOUNT_SUB: sub, po.SESSION_PREFIX + "extra": 1}


def _expired_run(monkeypatch, state):
    _use(monkeypatch, Net({TOKEN_A: _workbook()}))
    _load(SUB_A, TOKEN_A)    # 先讀成功一次，快取裡有 A 的內容
    assert any(k[0] == SUB_A for k in reader._CACHE)
    _use(monkeypatch, Net({TOKEN_A: _workbook()}, status=401))
    reader.clear_cache()      # 讓下面那次一定走網路（401）
    monkeypatch.setattr(personal_session, "access_target", lambda st: (SHEET, TOKEN_A, SUB_A))
    with pytest.raises(alo_holdings.ActiveSourceError) as e:
        alo_holdings.load_alo_tables_active(state, [])
    assert e.value.code == ec.AUTH_EXPIRED


def test_讀Google回AUTH_EXPIRED_清整個session_死token不再被重用(monkeypatch):
    from infra import personal_oauth as po

    state = _session_state()
    _expired_run(monkeypatch, state)
    assert not [k for k in state if isinstance(k, str) and k.startswith(po.SESSION_PREFIX)], state


def test_變異檢查_不清session_上一條就會紅(monkeypatch):
    from infra import personal_oauth as po

    monkeypatch.setattr(personal_session, "handle_read_error", lambda state, code: None)
    state = _session_state()
    _expired_run(monkeypatch, state)
    with pytest.raises(AssertionError):
        assert not [k for k in state if isinstance(k, str) and k.startswith(po.SESSION_PREFIX)]


def test_AUTH_EXPIRED_同時丟掉該帳號的讀取快取(monkeypatch):
    _use(monkeypatch, Net({TOKEN_A: _workbook()}))
    _load(SUB_A, TOKEN_A)
    assert any(k[0] == SUB_A for k in reader._CACHE)
    personal_session.handle_read_error(_session_state(), ec.AUTH_EXPIRED)
    assert not any(k[0] == SUB_A for k in reader._CACHE)
    # 其他 code 不動
    _load(SUB_A, TOKEN_A)
    personal_session.handle_read_error(_session_state(), ec.UPSTREAM_ERROR)
    assert any(k[0] == SUB_A for k in reader._CACHE)


@pytest.mark.parametrize("action", ["logout", "switch_account", "confirm_login"])
def test_登出_換帳號_確認新登入_丟掉舊帳號快取_不動別的帳號(monkeypatch, action):
    _use(monkeypatch, Net({TOKEN_A: _workbook(), TOKEN_B: _workbook()}))
    _load(SUB_A, TOKEN_A)
    _load(SUB_B, TOKEN_B)
    ok = types.SimpleNamespace(revoke_confirmed=True)
    monkeypatch.setattr(personal_session.po, "logout", lambda st: ok)
    monkeypatch.setattr(personal_session.po, "begin_account_switch",
                        lambda st: {"authorize_url": "https://accounts.google.com/x", "logout": ok})
    monkeypatch.setattr(personal_session.po, "confirm_pending_login", lambda st: {"email": "a@b.c"})
    getattr(personal_session, action)(_session_state(SUB_A))
    subs = {k[0] for k in reader._CACHE}
    assert SUB_A not in subs and SUB_B in subs


def test_快取_寫入時清過期_並有大小上限(monkeypatch):
    clock = [1000.0]
    monkeypatch.setattr(reader, "_clock", lambda: clock[0])
    net = Net({f"t{i}": _workbook() for i in range(40)})
    _use(monkeypatch, net)
    for i in range(40):
        reader.load_workbook_tables((SHEET, f"t{i}"), account_sub=f"s{i}", mask=lambda s: s)
        clock[0] += 1
        assert len(reader._CACHE) <= reader.CACHE_MAX_ENTRIES
    assert len(reader._CACHE) == reader.CACHE_MAX_ENTRIES
    assert ("s39", SHEET, reader._WHAT) in reader._CACHE and ("s0", SHEET, reader._WHAT) not in reader._CACHE   # 丟最舊
    clock[0] += reader.CACHE_TTL_SEC + 1       # 全部過期；下一次寫入把它們清掉
    reader.load_workbook_tables((SHEET, "t0"), account_sub="fresh", mask=lambda s: s)
    assert [k[0] for k in reader._CACHE] == ["fresh"]


def test_sheet_id驗證用fullmatch_尾端換行不放行(monkeypatch):
    _use(monkeypatch, lambda *a, **k: pytest.fail("不得發請求"))
    with pytest.raises(drive.PersonalDriveError) as e:
        reader.load_workbook_tables((SHEET + "\n", TOKEN_A), account_sub=SUB_A, mask=lambda s: s)
    assert e.value.code == ec.SHEET_NOT_FOUND


def test_命中與存入都交深拷貝_呼叫端改不到快取(monkeypatch):
    net = Net({TOKEN_A: _workbook()})
    _use(monkeypatch, net)
    first = reader._cached_values((SHEET, TOKEN_A), SUB_A)    # 未命中：存入的必須是副本
    first["P-001"][0][0] = "被呼叫端改過"
    second = reader._cached_values((SHEET, TOKEN_A), SUB_A)   # 命中：交出的必須是副本
    assert second["P-001"][0][0] == POLICY_HEADER[0]
    second["P-001"][0][0] = "又被改過"
    third = reader._cached_values((SHEET, TOKEN_A), SUB_A)
    assert third["P-001"][0][0] == POLICY_HEADER[0]
    assert len(net.calls) == 2


def test_世代守衛_讀取期間被清過的結果不存快取(monkeypatch):
    net = Net({TOKEN_A: _workbook()}, on_call=reader.clear_cache)   # 每個請求發出時快取被清一次
    _use(monkeypatch, net)
    _load(SUB_A, TOKEN_A)
    assert reader._CACHE == {}
    n = len(net.calls)
    _load(SUB_A, TOKEN_A)
    assert len(net.calls) == 2 * n    # 沒被存 → 第二次重打


def test_分頁很多_batchGet分批_每批不超過上限(monkeypatch):
    book = {f"P-{i:03d}": [POLICY_HEADER, [f"P-{i:03d}", f"F{i:04d}", "基金", "USD", "core", "1000", "", "1", "1", "30"]]
            for i in range(45)}
    book["_持倉補充"] = [SUPP_HEADER]
    book["_保單資料"] = [PROFILE_HEADER]
    net = Net({TOKEN_A: book})
    _use(monkeypatch, net)
    out = _load(SUB_A, TOKEN_A)
    assert len(out["policy"]["rows"]) == 45 and out["policy"]["skipped_tabs"] == []
    batches = [c for c in net.calls if c["url"].endswith("values:batchGet")]
    assert len(batches) == 3 and all(len(c["params"]["ranges"]) <= reader.BATCH_RANGES_MAX for c in batches)
    assert sum(len(c["params"]["ranges"]) for c in batches) == 47
    assert out["policy"]["read_estimate"]["requests_per_load"] == len(net.calls) == 4


# ═══════════════════════ 與服務帳戶路徑（gspread get_all_records）的邊界行為等價 ═══════════════════════

def _pad(vals):
    w = max((len(r) for r in vals), default=0)
    return [list(r) + [""] * (w - len(r)) for r in vals]


class _FakeWS:
    title = "T"

    def __init__(self, vals):
        self.vals = vals

    def get(self, value_render_option=None, pad_values=True):
        return _pad(self.vals) if self.vals else [[]]

    from gspread.worksheet import Worksheet as _W
    get_all_records = _W.get_all_records


def _old(vals):
    try:
        raw = sup._fetch_policy_tab(_FakeWS(vals))
    except Exception:  # noqa: BLE001 —— gspread 的標頭例外與新路徑的 ValueError 都算「該分頁略過」
        return "ERR"
    return sup._process_policy_tab("T", raw)


def _new(vals):
    try:
        raw = reader._records([[("" if c is None else str(c)) for c in r] for r in vals])
    except ValueError:
        return "ERR"
    return sup._process_policy_tab("T", raw)


_H = ["policy_id", "fund_url", "fund_code", "invest_twd", "policy_tier", "units"]
_EQUIV = {
    "basic": [_H, ["P1", "u1", "FC1", "1,000", "core", "10.5"], ["P1", "u1", "FC1", "500", "", "3"]],
    "short rows": [_H, ["P1", "u1"], [], ["P2", "u2", "F2", "abc"]],
    "invest bad": [_H, ["P1", "u1", "F", "1e3"], ["P1", "u2", "F", "1,00,0"], ["P1", "u3", "F", ""],
                   ["P1", "u4", "F", "1000.0"], ["P1", "u5", "F", "NT$5"]],
    "one extra data column": [_H + [""], ["P1", "u", "F", "1", "", "1", "note"]],
    "two extra data columns": [_H, ["P1", "u", "F", "1", "", "1", "n1", "n2"]],
    "one extra data column no header pad": [_H, ["P1", "u", "F", "1", "", "1", "n1"]],
    "interior blank header": [_H[:3] + [""] + _H[3:], ["P1", "u", "F", "x", "1", "c", "1"]],
    "dup header": [_H + ["fund_code"], ["P1", "u", "F", "1", "", "1", "x"]],
    "header only": [_H],
    "empty": [],
    "zh headers": [["保單編號", "基金連結", "基金代號", "淨投資金額"], ["P1", "u", "F", "2,000"]],
    "leading blank row0": [[], ["P1", "u"]],
    "both invest cols": [_H + ["淨投資金額"], ["P1", "u", "F", "1", "", "1", "999"]],
}


@pytest.mark.parametrize("name", sorted(_EQUIV))
def test_新舊解析等價_標頭邊界(name):
    assert repr(_old(_EQUIV[name])) == repr(_new(_EQUIV[name])), name


def test_新舊解析等價_兩個以上補出來的空欄名是重複_該分頁略過_不靜默丟資料欄():
    assert _old(_EQUIV["two extra data columns"]) == "ERR" == _new(_EQUIV["two extra data columns"])
    assert _old(_EQUIV["interior blank header"]) != "ERR" and _new(_EQUIV["interior blank header"]) != "ERR"
