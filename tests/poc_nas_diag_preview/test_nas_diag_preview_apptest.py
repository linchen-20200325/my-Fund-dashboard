# -*- coding: utf-8 -*-
"""NAS 中繼站診斷｜隔離式 FAKE Preview：AppTest 與靜態守衛（不開瀏覽器）。

驗：十三個情境切換真的改變頁面、FAKE 標示在 harness 區、整頁無寫入面、斷網仍綠（含正控）、不讀憑證／環境變數（含正控）、
子行程沒有載入取數／憑證相關模組、入口 import 白名單與禁止清單（含負控）、FAKE 輸入與 `tests/ui_v3/nas_diag_support.py` 逐一相等（drift）、
目錄佈局、正式路徑不引用本 Preview。負控一律在記憶體內現編，不寫檔。
"""
from __future__ import annotations

import ast
import os
import pathlib
import re
import subprocess
import sys

import pytest

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_POC = _ROOT / "poc" / "nas_diag_preview"
_APP = _POC / "app_nas_diag_preview.py"
_FAKE = _POC / "nas_diag_fake_inputs.py"
sys.path.insert(0, str(_ROOT / "tests" / "ui_v3"))
sys.path.insert(0, str(_POC))
sys.path.insert(0, str(_ROOT))

import nas_diag_fake_inputs as fake  # noqa: E402
import nas_diag_support as sup  # noqa: E402
import ui_v3_guard_lib as lib  # noqa: E402
from ui_v3.viewmodels import nas_diag as vm  # noqa: E402

KEY = "uvp_nas_scenario"
IDS = list(fake.SCENARIOS)


def _run() -> AppTest:
    at = AppTest.from_file(str(_APP), default_timeout=60).run()
    assert not at.exception, at.exception
    return at


def _select(at: AppTest, sid: str) -> AppTest:
    at.selectbox(key=KEY).set_value(sid).run()
    assert not at.exception, at.exception
    return at


def _md(at: AppTest) -> str:
    return "\n".join(m.value for m in at.markdown)


def _state(at: AppTest) -> str:
    found = re.findall(r'data-block="nas-status" data-state="([^"]+)"', _md(at))
    assert len(found) == 1, found
    return found[0]


# ───────────────────────── 行為 ─────────────────────────

def test_thirteen_scenarios_in_a_selectbox_and_each_changes_the_page():
    at = _run()
    assert len(IDS) == 13 and list(at.selectbox(key=KEY).options) == [fake.SCENARIOS[i][0] for i in IDS]
    pages = {}
    for sid in IDS:
        _select(at, sid)
        assert _state(at) == sup.EXPECTED[sid][0], sid
        pages[sid] = _md(at)
    assert len(set(pages.values())) == len(IDS)   # 情境畫面兩兩不同


def test_default_scenario_is_the_first_and_the_fake_banner_is_in_the_harness_only():
    at = _run()
    assert at.selectbox(key=KEY).value == fake.DEFAULT_SCENARIO == IDS[0]
    banners = [m.value for m in at.markdown if 'data-harness="true"' in m.value]
    assert len(banners) == 1 and "FAKE／測試資料（離線注入，未執行任何真實請求）" in banners[0]
    renderer = [m.value for m in at.markdown if 'data-block="nas-status"' in m.value]
    assert len(renderer) == 1 and "data-harness" not in renderer[0] and "FAKE" not in renderer[0]
    assert at.markdown[0].value == banners[0]   # 頁頂第一個元素
    assert [t.value for t in at.title] == ["NAS 中繼站診斷"]


@pytest.mark.parametrize("sid", IDS)
def test_every_scenario_renders_without_exception_with_pending_notices_and_no_interactive_renderer_element(sid):
    at = _select(_run(), sid)
    md = _md(at)
    assert 'data-pending-wording="pending_notice"' in md and 'data-pending-wording="offline_note"' in md
    renderer = "\n".join(m.value for m in at.markdown if "data-harness" not in m.value)
    assert not re.search(r"<\s*(?:button|a|input|select|textarea|form)\b|\bhref\s*=", renderer, re.I)
    assert len(re.findall(r"<details\b", renderer)) == 1 and not re.search(r"<details\b[^>]*\bopen\b", renderer)   # 只有那一個預設收合的 details
    assert not at.button and not at.text_input   # 沒有假的「立即測試」按鈕、沒有輸入框


def _block_network(monkeypatch, calls):
    import socket

    def blocked(*a, **k):
        calls.append(a)
        raise AssertionError("Preview 不得連網")

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    return socket


def test_network_block_positive_control_really_fires(monkeypatch):
    """正控：斷網攔截被觸發時一定會報錯並留下紀錄（否則下面的「斷網仍綠」可能是空綠）。"""
    calls = []
    socket = _block_network(monkeypatch, calls)
    with pytest.raises(AssertionError):
        socket.create_connection(("127.0.0.1", 9))
    with pytest.raises(AssertionError):
        socket.socket().connect(("127.0.0.1", 9))
    assert len(calls) == 2


def test_all_scenarios_work_with_the_network_blocked(monkeypatch):
    calls = []
    _block_network(monkeypatch, calls)
    at = _run()
    for sid in IDS:
        _select(at, sid)
    assert calls == []   # 整段執行沒有任何連線嘗試


def _spy_environ(monkeypatch, seen):
    real_env_get = os.environ.get

    def spy(key, *a, **k):
        if re.search(r"KEY|TOKEN|SECRET|CRED|PROXY|PASS", str(key), re.I):
            seen.append(key)
        return real_env_get(key, *a, **k)

    monkeypatch.setattr(os.environ, "get", spy)


def test_environ_spy_positive_control_records_a_credential_like_read(monkeypatch):
    """正控：偷看環境變數的觀察器真的會記錄憑證形名稱（否則「沒有讀憑證」可能是空綠）。"""
    seen = []
    _spy_environ(monkeypatch, seen)
    os.environ.get("SOME_API_KEY")
    os.environ.get("HTTPS_PROXY")
    os.environ.get("HARMLESS_NAME")
    assert seen == ["SOME_API_KEY", "HTTPS_PROXY"]


def test_no_credential_secret_or_proxy_environment_access_in_a_run(monkeypatch):
    seen = []
    _spy_environ(monkeypatch, seen)
    at = _run()
    for sid in IDS:
        _select(at, sid)
    assert seen == []
    dump = ast.dump(ast.parse(_APP.read_text(encoding="utf-8")))
    assert "secrets" not in dump and "environ" not in dump and "getenv" not in dump


# ───────────────────────── 子行程：沒有載入取數／憑證相關模組 ─────────────────────────

_SCAN_TAIL = """
new = set(sys.modules) - before
bad = sorted(m for m in new if m.split('.')[0] in ('services', 'gspread', 'requests', 'urllib3', 'repositories', 'infra', 'httpx', 'yfinance')
             or m.startswith('ui_v3.fixtures') or m.startswith('ui_v3.adapters') or m == 'ui_v3.app_preview')
print(repr(bad))
print(repr(sorted(m for m in new if m.startswith('ui_v3'))))
"""


def _scan_subprocess(app_expr: str, loop: str) -> tuple:
    """子行程跑 AppTest 並用**同一段掃描程式**（`_SCAN_TAIL`）回報新載入的禁止模組；真測試與正控共用。"""
    code = (f"import sys\nsys.path.insert(0, {str(_ROOT)!r})\nimport streamlit\nimport streamlit.testing.v1\n"
            f"from streamlit.testing.v1 import AppTest\nbefore = set(sys.modules)\nat = {app_expr}.run()\nassert not at.exception, at.exception\n"
            f"{loop}{_SCAN_TAIL}")
    out = subprocess.run([sys.executable, "-c", code], cwd=str(_ROOT), capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    bad, loaded = out.stdout.strip().splitlines()[-2:]
    return bad, loaded


def test_run_does_not_load_network_data_or_credential_modules():
    loop = (f"for sid in ({IDS!r}):\n    at.selectbox(key={KEY!r}).set_value(sid).run()\n    assert not at.exception, at.exception\n")
    bad, loaded = _scan_subprocess(f"AppTest.from_file({str(_APP)!r}, default_timeout=60)", loop)
    assert bad == "[]", bad
    # `ui_v3.shell.registry` 會被 `ui_v3.shell.nav`（renderer 取斷點常數）間接載入，屬預期；入口「直接」import 它由靜態守衛禁止。
    assert "ui_v3.pages.nas_diag" in loaded and "ui_v3.viewmodels.nas_diag" in loaded and "ui_v3.viewmodels.nas_diag_wording" in loaded


@pytest.mark.parametrize("module", ["urllib3", "requests", "httpx"])
def test_subprocess_scan_positive_control_uses_the_same_scan_function_and_flags_an_importing_app(module):
    """正控：用 `AppTest.from_string` 跑一段會 import 禁止模組的 app，**同一個掃描函式**必須回報它（否則上面的 `[]` 可能是空掃）。"""
    import importlib.util
    if importlib.util.find_spec(module) is None:
        pytest.skip(f"本環境沒有 {module}")   # 至少 urllib3 與 requests 在本專案環境一定有；CI 缺任一個才會 skip
    bad, _ = _scan_subprocess(f"AppTest.from_string({('import ' + module + chr(10) + 'import streamlit as st' + chr(10) + 'st.write(1)')!r})", "")
    assert module in bad, bad


# ───────────────────────── 靜態守衛 ─────────────────────────

_ALLOWED_ENTRY_EXACT = {"ui_v3.pages.nas_diag", "nas_diag_fake_inputs"}
_ALLOWED_ENTRY_PREFIX = ("ui_v3.viewmodels.", "ui_v3.design.")
_ALLOWED_ENTRY_ROOT = {"__future__", "streamlit", "pathlib", "sys"}
_FORBIDDEN_ENTRY = ("ui_v3.app_preview", "ui_v3.shell.registry", "ui_v3.adapters", "ui_v3.fixtures", "services", "gspread", "requests",
                    "urllib", "urllib3", "socket", "ssl", "http", "subprocess", "os", "repositories", "infra", "shared", "ui", "ui_v2", "app")


def entry_import_violations(src: str):
    out = []
    for module in lib.imports_of(ast.parse(src), "x"):
        root = module.split(".")[0]
        if any(module == f or module.startswith(f + ".") for f in _FORBIDDEN_ENTRY):
            out.append(f"禁止的 import：{module}")
        elif (module in _ALLOWED_ENTRY_EXACT or module.startswith(_ALLOWED_ENTRY_PREFIX) or module in ("ui_v3.viewmodels", "ui_v3.design")
              or any(module.startswith(e + ".") for e in _ALLOWED_ENTRY_EXACT)):   # `from X import name` 會連帶回報 X.name
            continue
        elif root in _ALLOWED_ENTRY_ROOT and root != "ui_v3":
            continue
        elif module.startswith("ui_v3.") or module == "ui_v3":
            out.append(f"不在白名單的 ui_v3 import：{module}")
        else:
            out.append(f"不在白名單的 import：{module}")
    return out


def test_entry_imports_are_inside_the_allowlist_and_hit_no_forbidden_module():
    assert entry_import_violations(_APP.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("src", ["import requests\n", "import gspread\n", "from services.v2_tables import x\n", "import urllib.request\n",
                                 "import socket\n", "import os\n", "import subprocess\n", "from ui_v3.app_preview import main\n",
                                 "from ui_v3.shell.registry import IA_PAGES\n", "from ui_v3 import fixtures\n", "from ui_v3.fixtures.x import y\n",
                                 "from infra.proxy import fetch_url\n", "from infra import proxy\n", "from ui_v3.adapters import market_page\n",
                                 "import httpx\n"])
def test_negative_control_entry_import_checker_turns_red(src):
    assert entry_import_violations(src), src


def test_fake_inputs_import_nothing_but_the_future_module():
    mods = lib.imports_of(ast.parse(_FAKE.read_text(encoding="utf-8")), "x")
    assert {m for m in mods if not m.startswith("__future__")} == set(), mods


@pytest.mark.parametrize("path", [_APP, _FAKE, _ROOT / "ui_v3" / "pages" / "nas_diag.py", _ROOT / "ui_v3" / "viewmodels" / "nas_diag.py",
                                  _ROOT / "ui_v3" / "viewmodels" / "nas_diag_wording.py"])
def test_no_write_surface(path):
    rel = path.relative_to(_ROOT).as_posix()
    assert lib.write_surface_violations(rel, path.read_text(encoding="utf-8")) == []


def test_negative_control_write_surface_checker_turns_red():
    assert lib.write_surface_violations("poc/x.py", "open('f', 'w')\n")
    assert lib.write_surface_violations("poc/x.py", "import pathlib\npathlib.Path('f').write_text('x')\n")


def test_entry_has_no_credential_environment_or_network_calls_by_ast():
    tree = ast.parse(_APP.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"environ", "getenv", "secrets", "connect", "create_connection", "urlopen", "get", "post", "request", "session"} - {"get"}, names
    assert "secrets" not in names


def test_directory_layout_has_no_pages_dir_or_package_init():
    assert not [d for d in (_ROOT / "poc").rglob("*") if d.is_dir() and d.name == "pages"]
    assert not (_ROOT / "poc" / "__init__.py").exists() and not (_POC / "__init__.py").exists()
    assert not (_ROOT / "pages").exists()
    assert {p.suffix for p in _POC.rglob("*") if p.is_file() and "__pycache__" not in p.parts} <= {".py", ".md"}
    assert {p.name for p in _POC.iterdir() if p.is_file()} >= {"app_nas_diag_preview.py", "nas_diag_fake_inputs.py", "README.md"}


_PY_DIRS = ("ui", "ui_v2", "ui_v3", "services", "repositories", "shared", "infra", "scripts", "mcp_server", "models")
_TEXT_DIRS = (".streamlit", ".github", ".devcontainer")
_REF = re.compile(r"nas_diag_preview|app_nas_diag_preview|nas_diag_fake_inputs")


def production_references(root: pathlib.Path):
    hits = []
    files = [p for d in _PY_DIRS if (root / d).exists() for p in (root / d).rglob("*.py") if "__pycache__" not in p.parts] + list(root.glob("*.py"))
    files += [p for d in _TEXT_DIRS if (root / d).exists() for p in (root / d).rglob("*") if p.is_file()]
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{p.relative_to(root)}: {m.group(0)}" for m in _REF.finditer(text)]
    return hits


def test_no_production_path_references_the_preview():
    assert production_references(_ROOT) == []


def test_negative_control_reference_scan_turns_red(tmp_path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "x.py").write_text("import nas_diag_fake_inputs\n", encoding="utf-8")
    assert production_references(tmp_path)


def test_formal_shell_and_preview_entry_do_not_mention_nas_diag():
    """隔離守衛：app_preview.py、ui_v3/shell/*、ui_v3/pages/__init__.py 不含 nas_diag 字樣（沒有掛載）。"""
    files = [_ROOT / "ui_v3" / "app_preview.py", _ROOT / "ui_v3" / "pages" / "__init__.py"] + sorted((_ROOT / "ui_v3" / "shell").glob("*.py"))
    assert len(files) >= 4 and all(f.exists() for f in files)
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert not re.search(r"nas_diag|NasDiag", text), f.name
    assert re.search(r"nas_diag|NasDiag", "from ui_v3.pages import nas" + "_diag")   # 負控：偵測得到


def test_formal_page_registry_is_untouched_by_the_preview():
    """正式 ⚙️ 頁掛載未核准：登錄表裡的設定頁仍未掛載，且沒有任何 NAS 診斷頁。"""
    text = (_ROOT / "ui_v3" / "shell" / "registry.py").read_text(encoding="utf-8")
    assert "nas_diag" not in text and "NAS" not in text


# ───────────────────────── drift：FAKE 輸入與測試支援檔、期望表同形 ─────────────────────────

def test_poc_fake_inputs_equal_the_test_support_copy_and_expected_table_covers_every_scenario():
    assert list(fake.SCENARIOS) == list(sup.SCENARIO_KWARGS) == list(sup.EXPECTED)
    for sid in IDS:
        assert fake.build(sid) == sup.kwargs(sid), sid
    assert fake.FAKE_CHECKED_AT == sup.CHECKED_AT and fake.FAKE_TARGET == sup.TARGET and fake.FAKE_FIXTURE is True


@pytest.mark.parametrize("sid", IDS)
def test_poc_fake_inputs_build_valid_observations_that_classify_as_expected(sid):
    view = vm.classify(vm.NasDiagObservation(**fake.build(sid)))
    assert (view.state, view.nas_health, view.target_health, view.reason_key) == sup.EXPECTED[sid]


def test_builders_return_fresh_dicts_and_unknown_scenario_is_an_error():
    a, b = fake.build("nas_ok"), fake.build("nas_ok")
    assert a == b and a is not b
    a["target_label"] = "changed"
    assert fake.build("nas_ok")["target_label"] == sup.TARGET
    with pytest.raises(KeyError):
        fake.build("no_such_scenario")


def test_fake_inputs_contain_no_url_host_or_credential_shape():
    for sid in IDS:
        for value in fake.build(sid).values():
            if isinstance(value, str):
                assert "://" not in value and "@" not in value and not re.search(r":\d{3,5}\b", value), (sid, value)
