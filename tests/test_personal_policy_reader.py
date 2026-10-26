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

    def __init__(self, by_token, status=200):
        self.by_token, self.status, self.calls = by_token, status, []

    def __call__(self, url, params=None, headers=None, timeout=None, allow_redirects=None):
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
    assert e.value.code == ec.SCHEMA_INVALID


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
    assert e.value.code == ec.SCHEMA_INVALID


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


def test_L2把token加進遮蔽清單(monkeypatch):
    """補充分頁標頭不符的訊息帶試算表原文；原文若含 token，L2 的 mask 要遮掉（呼叫端的秘密值清單不含新 session 的 token）。"""
    book = _workbook()
    book["_持倉補充"] = [SUPP_HEADER[:-1] + [f"類別{TOKEN_A}"], book["_持倉補充"][1]]
    _use(monkeypatch, Net({TOKEN_A: book}))
    monkeypatch.setattr(personal_session, "access_target", lambda state: (SHEET, TOKEN_A, SUB_A))
    with pytest.raises(sup.PolicySupplementError) as e:
        alo_holdings.load_alo_tables_active({}, [])
    assert TOKEN_A not in str(e.value)


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


def test_只有alo_holdings與drive_import_personal_policy_reader():
    owners = sorted(str(p.relative_to(_ROOT)).replace("\\", "/") for p in _py_files()
                    if "repositories.personal_policy_reader" in _imports(p))
    assert owners == ["services/v2_tables/alo_holdings.py"], owners


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
