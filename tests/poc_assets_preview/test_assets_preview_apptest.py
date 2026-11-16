# -*- coding: utf-8 -*-
"""💼 我的資產｜隔離式 FAKE Preview：AppTest 與靜態守衛（不開瀏覽器）。

驗：七情境切換真的改變頁面、FAKE 標示在 harness 區、整頁無寫入面、斷網仍綠、子行程沒有載入取數／憑證相關模組、
入口 import 白名單與禁止清單、FAKE 輸入與 `tests/ui_v3/assets_page_support.py` 同名情境逐一相等（drift）、目錄佈局、正式路徑不引用本 Preview。
負控一律在記憶體內現編，不寫檔。
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
_POC = _ROOT / "poc" / "assets_fixture_preview"
_APP = _POC / "app_assets_preview.py"
_FAKE = _POC / "assets_fake_inputs.py"
sys.path.insert(0, str(_ROOT / "tests" / "ui_v3"))
sys.path.insert(0, str(_POC))

import assets_fake_inputs as fake  # noqa: E402
import assets_page_support as sup  # noqa: E402
import ui_v3_guard_lib as lib  # noqa: E402

KEY = "uvp_assets_scenario"
IDS = list(fake.SCENARIOS)
EXPECTED_STATE = {"multi_currency": "complete", "complete_no_rows": "complete_no_rows", "market_blocked": "not_read", "partial": "partial",
                  "no_active": "not_selected", "read_failed": "read_failed", "unprovided_skip_evidence": "undetermined"}


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
    found = re.findall(r'data-source-state="([^"]+)"', _md(at))
    assert len(found) == 1, found
    return found[0]


# ───────────────────────── 行為 ─────────────────────────

def test_seven_scenarios_in_a_selectbox_and_each_changes_the_page():
    at = _run()
    assert len(IDS) == 7 and list(at.selectbox(key=KEY).options) == [fake.SCENARIOS[i][0] for i in IDS]
    pages = {}
    for sid in IDS:
        _select(at, sid)
        assert _state(at) == EXPECTED_STATE[sid], sid
        pages[sid] = _md(at)
    assert len(set(pages.values())) == 7   # 七個情境畫面兩兩不同


def test_default_scenario_is_the_first_and_banner_is_in_the_harness_only():
    at = _run()
    assert at.selectbox(key=KEY).value == fake.DEFAULT_SCENARIO == IDS[0]
    banners = [m.value for m in at.markdown if 'data-harness="true"' in m.value]
    assert len(banners) == 1 and "FAKE" in banners[0] and "非真實持倉" in banners[0]
    assert "data-first-screen" not in banners[0]
    renderer = [m.value for m in at.markdown if 'data-block="a00"' in m.value]
    assert len(renderer) == 1 and "data-harness" not in renderer[0] and "FAKE" not in renderer[0]
    assert at.markdown[0].value == banners[0]   # 頁頂第一個元素


@pytest.mark.parametrize("sid", IDS)
def test_every_scenario_renders_exactly_five_first_screen_marks_and_no_exception(sid):
    at = _select(_run(), sid)
    marks = re.findall(r'data-first-screen="([^"]+)"', _md(at))
    assert marks == ["a00", "a20_cell_1", "a20_cell_2", "a20_cell_3", "a20_cell_4"]


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


def test_scenarios_work_with_the_network_blocked(monkeypatch):
    calls = []
    _block_network(monkeypatch, calls)
    at = _run()
    for sid in IDS:
        _select(at, sid)
    assert calls == []   # 整段執行沒有任何連線嘗試


def _spy_environ(monkeypatch, seen):
    real_env_get = os.environ.get

    def spy(key, *a, **k):
        if re.search(r"KEY|TOKEN|SECRET|CRED", str(key), re.I):
            seen.append(key)
        return real_env_get(key, *a, **k)

    monkeypatch.setattr(os.environ, "get", spy)


def test_environ_spy_positive_control_records_a_credential_like_read(monkeypatch):
    """正控：偷看環境變數的觀察器真的會記錄憑證形名稱（否則「沒有讀憑證」可能是空綠）。"""
    seen = []
    _spy_environ(monkeypatch, seen)
    os.environ.get("SOME_API_KEY")
    os.environ.get("HARMLESS_NAME")
    assert seen == ["SOME_API_KEY"]


def test_no_credential_or_secret_access_in_a_run(monkeypatch):
    seen = []
    _spy_environ(monkeypatch, seen)
    at = _run()
    for sid in IDS:
        _select(at, sid)
    assert seen == []
    assert "secrets" not in ast.dump(ast.parse(_APP.read_text(encoding="utf-8")))


# ───────────────────────── 子行程：沒有載入取數／憑證相關模組 ─────────────────────────

def test_run_does_not_load_data_loading_or_credential_modules():
    code = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
import streamlit
import streamlit.testing.v1
from streamlit.testing.v1 import AppTest
before = set(sys.modules)
at = AppTest.from_file({str(_APP)!r}, default_timeout=60).run()
assert not at.exception, at.exception
for sid in ({IDS!r}):
    at.selectbox(key={KEY!r}).set_value(sid).run()
    assert not at.exception, at.exception
new = set(sys.modules) - before
bad = sorted(m for m in new if m.split('.')[0] in ('services', 'gspread', 'requests', 'repositories', 'infra')
             or m == 'ui_v3.adapters.assets_source' or m.startswith('ui_v3.fixtures') or m.startswith('services.v2_tables'))
print(repr(bad))
print(repr(sorted(m for m in new if m.startswith('ui_v3'))))
"""
    out = subprocess.run([sys.executable, "-c", code], cwd=str(_ROOT), capture_output=True, text=True, timeout=300)
    assert out.returncode == 0, out.stderr[-2000:]
    bad, ui_v3_loaded = out.stdout.strip().splitlines()[-2:]
    assert bad == "[]", bad
    assert "ui_v3.adapters.assets_page" in ui_v3_loaded and "ui_v3.pages.assets" in ui_v3_loaded
    assert "ui_v3.adapters.assets_source" not in ui_v3_loaded and "ui_v3.app_preview" not in ui_v3_loaded


# ───────────────────────── 靜態守衛 ─────────────────────────

_ALLOWED_ENTRY_EXACT = {"ui_v3.adapters.assets_page", "ui_v3.pages.assets", "assets_fake_inputs"}
_ALLOWED_ENTRY_PREFIX = ("ui_v3.viewmodels.", "ui_v3.design.")
_ALLOWED_ENTRY_ROOT = {"__future__", "streamlit", "pathlib", "sys", "html", "re", "math", "types", "typing"}
_FORBIDDEN_ENTRY = ("ui_v3.app_preview", "ui_v3.shell.registry", "ui_v3.adapters.assets_source", "ui_v3.fixtures", "services", "gspread", "requests",
                    "repositories", "infra", "shared", "ui", "ui_v2", "app")


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


@pytest.mark.parametrize("src", ["import requests\n", "import gspread\n", "from services.v2_tables import x\n",
                                 "from ui_v3.adapters.assets_source import load\n", "from ui_v3.app_preview import main\n",
                                 "from ui_v3.shell.registry import IA_PAGES\n", "from ui_v3 import fixtures\n", "import os\n",
                                 "from ui_v3.fixtures.x import y\n", "from infra.proxy import fetch_url\n"])
def test_negative_control_entry_import_checker_turns_red(src):
    assert entry_import_violations(src), src


def test_fake_inputs_import_nothing_but_the_future_module():
    mods = lib.imports_of(ast.parse(_FAKE.read_text(encoding="utf-8")), "x")
    assert {m for m in mods if not m.startswith("__future__")} == set(), mods


@pytest.mark.parametrize("path", [_APP, _FAKE, _ROOT / "ui_v3" / "pages" / "assets.py"])
def test_no_write_surface(path):
    rel = path.relative_to(_ROOT).as_posix()
    assert lib.write_surface_violations(rel, path.read_text(encoding="utf-8")) == []


def test_negative_control_write_surface_checker_turns_red():
    assert lib.write_surface_violations("poc/x.py", "open('f', 'w')\n")
    assert lib.write_surface_violations("poc/x.py", "import pathlib\npathlib.Path('f').write_text('x')\n")


def test_directory_layout_has_no_pages_dir_or_package_init():
    assert not [d for d in (_ROOT / "poc").rglob("*") if d.is_dir() and d.name == "pages"]
    assert not (_ROOT / "poc" / "__init__.py").exists() and not (_POC / "__init__.py").exists()
    assert not (_ROOT / "pages").exists()
    assert {p.suffix for p in _POC.rglob("*") if p.is_file() and "__pycache__" not in p.parts} <= {".py", ".md"}
    assert {p.name for p in _POC.iterdir() if p.is_file()} >= {"app_assets_preview.py", "assets_fake_inputs.py", "README.md"}


_PY_DIRS = ("ui", "ui_v2", "ui_v3", "services", "repositories", "shared", "infra", "scripts", "mcp_server", "models")
_TEXT_DIRS = (".streamlit", ".github", ".devcontainer")
_REF = re.compile(r"assets_fixture_preview|app_assets_preview|assets_fake_inputs")


def production_references(root: pathlib.Path):
    hits = []
    files = [p for d in _PY_DIRS for p in (root / d).rglob("*.py") if "__pycache__" not in p.parts] + list(root.glob("*.py"))
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
    (tmp_path / "ui" / "x.py").write_text("import assets_fake_inputs\n", encoding="utf-8")
    assert production_references(tmp_path)


# ───────────────────────── drift：FAKE 輸入與測試支援檔同形 ─────────────────────────

_PAIRS = {
    "complete_no_rows": (fake.complete_no_rows_result, sup.complete_no_rows_result),
    "market_blocked": (fake.market_blocked_result, sup.market_blocked_result),
    "partial": (fake.partial_result, sup.partial_result),
    "no_active": (fake.no_active_result, sup.no_active_result),
    "read_failed": (fake.read_failed_result, sup.read_failed_result),
    "unprovided_skip_evidence": (fake.unprovided_skip_evidence_result, lambda: sup.complete_with_unprovided_skip_evidence_result(rows=0)),
    "multi_currency": (fake.multi_currency_result,
                       lambda: sup.fake_result(evidence=sup.fake_evidence(holdings=[sup.fake_holding(1, ccy="TWD"), sup.fake_holding(2, ccy="USD")]))),
}


@pytest.mark.parametrize("sid", IDS)
def test_poc_fake_inputs_equal_the_test_support_builders(sid):
    mine, theirs = _PAIRS[sid]
    assert mine() == theirs()
    assert fake.build(sid) == theirs()


def test_all_seven_scenarios_are_covered_by_a_drift_pair_and_constants_match():
    assert set(_PAIRS) == set(IDS)
    for name in ("SENTINEL_CATEGORY_VALUE", "SENTINEL_HOLDING_VALUE", "SENTINEL_COST_TWD", "SENTINEL_COST_ORIG", "SENTINEL_SHARE_PCT",
                 "FAKE_SKIPPED_TAB_ITEM", "FAKE_SKIPPED_ROW_ITEM"):
        assert getattr(fake, name) == getattr(sup, name), name


def test_builders_return_fresh_dicts_and_unknown_scenario_is_an_error():
    a, b = fake.build("partial"), fake.build("partial")
    assert a == b and a is not b and a["evidence"] is not b["evidence"]
    a["evidence"]["holdings"].clear()
    assert fake.build("partial")["evidence"]["holdings"]
    with pytest.raises(KeyError):
        fake.build("no_such_scenario")


def test_every_fake_holding_is_visibly_fake():
    for sid in IDS:
        for h in fake.build(sid)["evidence"]["holdings"] if fake.build(sid)["evidence"] else []:
            assert str(h["fund_code"]).startswith("FK") and str(h["policy_id"]).startswith("FAKE")
            assert h["fund_name"] is None or str(h["fund_name"]).startswith("FAKE")
    assert fake.FAKE_FIXTURE is True
