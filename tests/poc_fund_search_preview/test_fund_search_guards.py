# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview：AST／靜態／隔離／字樣／fixtures-are-fake 守衛（不開 Streamlit、不開瀏覽器）。

負控一律在記憶體內現編，不寫檔。
"""
from __future__ import annotations

import ast
import pathlib
import re

import pytest

import fund_search_support as S  # noqa: F401

import fund_search_fake_inputs as fake  # noqa: E402
import fund_search_wording as W  # noqa: E402
import ui_v3_guard_lib as lib  # noqa: E402
from shared.ui_semantics import rules  # noqa: E402
from ui_v3.viewmodels import exp_counts  # noqa: E402
from ui_v3.viewmodels.preview_wording import PendingWording  # noqa: E402

ROOT, POC = S.ROOT, S.POC
POC_PY = sorted(p for p in POC.glob("*.py"))
ENTRY = POC / "app_fund_search_preview.py"
RENDERER = POC / "fund_search_renderer.py"
LOCAL_MODULES = {"fund_search_fake_inputs", "fund_search_logic", "fund_search_renderer", "fund_search_wording"}

# ───────────────────────── import 白名單 ─────────────────────────
ALLOWED_ROOT = {"__future__", "dataclasses", "html", "re", "types", "typing", "pathlib", "sys", "streamlit"}
ALLOWED_PREFIX = ("ui_v3.design", "ui_v3.viewmodels.exp_counts", "ui_v3.viewmodels.preview_wording",
                  "shared.ui_semantics")   # `shared` 只開 `shared.ui_semantics`（已核准字樣的唯一來源），與 ui_v3 自己的白名單一致
ALLOWED_EXACT = {"ui_v3", "ui_v3.viewmodels", "shared"}   # `from ui_v3.viewmodels import exp_counts` 會連帶回報上層套件名
FORBIDDEN = ("ui_v3.app_preview", "ui_v3.shell", "ui_v3.pages", "ui_v3.adapters", "ui_v3.fixtures", "services", "gspread", "requests",
             "urllib", "urllib3", "socket", "ssl", "http", "subprocess", "os", "repositories", "infra", "ui", "ui_v2", "app",
             "yfinance", "httpx", "feedparser", "secrets", "tempfile", "shutil", "json", "pickle", "sqlite3", "glob")


def import_violations(src: str):
    out = []
    for module in lib.imports_of(ast.parse(src), "x"):
        root = module.split(".")[0]
        if any(module == f or module.startswith(f + ".") for f in FORBIDDEN):
            out.append(f"禁止的 import：{module}")
        elif root in LOCAL_MODULES or module in ALLOWED_EXACT or root in ALLOWED_ROOT:
            continue
        elif any(module == p or module.startswith(p + ".") for p in ALLOWED_PREFIX):
            continue
        elif module.startswith("shared"):
            out.append(f"shared 只開 shared.ui_semantics：{module}")
        else:
            out.append(f"不在白名單的 import：{module}")
    return out


@pytest.mark.parametrize("path", POC_PY, ids=lambda p: p.name)
def test_imports_are_inside_the_allowlist(path):
    assert import_violations(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("src", [
    "import requests\n", "import urllib.request\n", "from urllib import request\n", "import socket\n", "import subprocess\n", "import os\n",
    "import ssl\n", "import http.client\n", "import gspread\n", "import httpx\n", "import yfinance\n", "import json\n", "import shutil\n",
    "from services import fund_search\n", "from repositories.fund import sources\n", "from infra.proxy import fetch_url\n", "from ui import sidebar\n",
    "import ui_v2\n", "from ui_v2.exp import source\n", "from shared.ttls import TTL_1MIN\n", "from shared import fred_series\n",
    "from ui_v3.app_preview import main\n", "from ui_v3.shell.registry import IA_PAGES\n", "from ui_v3.pages import nas_diag\n",
    "from ui_v3 import fixtures\n", "from ui_v3.adapters import market_page\n", "import secrets\n", "import tempfile\n"])
def test_negative_control_import_checker_turns_red(src):
    assert import_violations(src), src


def test_the_entry_does_not_import_the_registry_or_the_preview_shell_directly():
    mods = lib.imports_of(ast.parse(ENTRY.read_text(encoding="utf-8")), "x")
    assert not [m for m in mods if m.startswith(("ui_v3.shell", "ui_v3.app_preview", "ui_v3.pages"))]


@pytest.mark.parametrize("path", POC_PY, ids=lambda p: p.name)
def test_no_dynamic_import_and_no_write_surface(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assert lib.dynamic_import_uses(tree) == []
    assert lib.write_surface_violations(path.relative_to(ROOT).as_posix(), path.read_text(encoding="utf-8")) == []


def test_negative_control_write_surface_checker_turns_red():
    assert lib.write_surface_violations("poc/x.py", "open('f', 'w')\n")
    assert lib.write_surface_violations("poc/x.py", "import pathlib\npathlib.Path('f').write_text('x')\n")


@pytest.mark.parametrize("path", POC_PY, ids=lambda p: p.name)
def test_no_network_environment_secret_or_file_call_by_ast(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    bad = names & {"environ", "getenv", "secrets", "connect", "create_connection", "urlopen", "urlretrieve", "Popen", "system", "run",
                   "write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "rmtree", "set_page_config", "cache_data", "cache_resource"}
    assert not bad, bad
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"open", "exec", "eval", "compile", "__import__", "input"}


def test_negative_control_for_the_ast_name_scan():
    tree = ast.parse("import os\nos.environ.get('X')\n")
    names = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert names & {"environ", "getenv"}


def test_module_level_has_no_side_effects_except_the_entry_path_setup_and_main_call():
    for path in POC_PY:
        bad = lib.module_level_side_effects(path.read_text(encoding="utf-8"))
        if path == ENTRY:   # 入口慣例：sys.path 設定迴圈＋最後一行 `main()`；其餘模組 import 零副作用
            assert [b.split(": ")[1] for b in bad] == ["For", "Expr"], bad
            body = ast.parse(path.read_text(encoding="utf-8")).body
            assert isinstance(body[-1], ast.Expr) and ast.unparse(body[-1]) == "main()"
        else:
            assert bad == [], (path.name, bad)


def _is_session_state(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "session_state") or (isinstance(node, ast.Name) and node.id == "session_state")


def session_state_writes(src: str):
    """所有寫 `session_state` 的形式：下標賦值、增量賦值、刪除、屬性賦值，以及 update／setdefault／pop／popitem／clear 呼叫。回傳每處的描述。"""
    out = []
    for node in ast.walk(ast.parse(src)):
        targets = []
        if isinstance(node, ast.Assign):
            targets = node.targets
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets = [node.target]
        elif isinstance(node, ast.Delete):
            targets = node.targets
        for t in targets:
            if isinstance(t, ast.Subscript) and _is_session_state(t.value):
                out.append(f"{type(node).__name__}[{ast.unparse(t.slice)}]")
            elif isinstance(t, ast.Attribute) and _is_session_state(t.value):
                out.append(f"{type(node).__name__}.{t.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and _is_session_state(node.func.value) \
                and node.func.attr in {"update", "setdefault", "pop", "popitem", "clear"}:
            out.append(f"call.{node.func.attr}")
    return out


def test_no_session_state_write_outside_the_one_session_key():
    """持久層守衛：整個 poc 目錄只可寫 `fs_last_query`（本次 session 的查詢）一處，其餘一律是 widget 自己的 key。"""
    writes = {p.name: session_state_writes(p.read_text(encoding="utf-8")) for p in POC_PY}
    assert writes["fund_search_renderer.py"] == ["Assign[KEY_QUERY]"], writes
    assert all(v == [] for k, v in writes.items() if k != "fund_search_renderer.py"), writes


@pytest.mark.parametrize("src,expected", [
    ("import streamlit as st\nst.session_state['k'] = 1\n", ["Assign['k']"]),
    ("import streamlit as st\nst.session_state['k'] += 1\n", ["AugAssign['k']"]),
    ("import streamlit as st\ndel st.session_state['k']\n", ["Delete['k']"]),
    ("import streamlit as st\nst.session_state.k = 1\n", ["Assign.k"]),
    ("import streamlit as st\nst.session_state.update({'k': 1})\n", ["call.update"]),
    ("import streamlit as st\nst.session_state.setdefault('k', 1)\n", ["call.setdefault"]),
    ("import streamlit as st\nst.session_state.pop('k')\n", ["call.pop"]),
    ("import streamlit as st\nst.session_state.clear()\n", ["call.clear"]),
    ("from streamlit import session_state\nsession_state['k'] = 1\n", ["Assign['k']"]),
    ("import streamlit as st\nx = st.session_state.get('k')\n", [])])
def test_negative_control_session_state_write_scan(src, expected):
    assert session_state_writes(src) == expected


# ───────────────────────── 字樣守衛 ─────────────────────────

def _approved_strings():
    out = {a.text for a in rules.APPROVED_WORDING.values()} | {a.ruling_text for a in rules.APPROVED_WORDING.values()}
    out |= {e.wording for e in rules.ENTRIES.values() if e.wording and e.wording != rules.PENDING_WORDING}
    out |= {getattr(exp_counts, n) for n in dir(exp_counts) if n.startswith("TEXT_")}
    return {s for s in out if s and s.strip()}


def test_every_new_wording_is_a_pending_wording_with_the_required_source_and_never_a_rules_key_or_text():
    approved = _approved_strings()
    assert W.FUND_SEARCH_PENDING
    for key, item in W.FUND_SEARCH_PENDING.items():
        assert isinstance(item, PendingWording) and item.status == "pending" and item.key == key
        assert item.source.startswith("ChatGPT UI 設計方向 2026-11-17＋DEC-2026-11-17-02；暫行")
        assert key not in rules.APPROVED_WORDING and key not in rules.ENTRIES
        assert item.text not in approved and item.text.strip() not in approved   # 不得重複定義已核准字樣


def test_no_string_literal_in_the_poc_files_duplicates_an_approved_wording():
    approved = _approved_strings()
    for path in POC_PY:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value.strip() not in approved, (path.name, node.value)


def test_negative_control_literal_scan_would_catch_a_duplicate():
    approved = _approved_strings()
    assert "◇ 資料未備" in approved and "目前條件下沒有符合的基金" in approved and "尚未設定條件" in approved
    tree = ast.parse("x = '◇ 資料未備'\n")
    assert any(isinstance(n, ast.Constant) and n.value in approved for n in ast.walk(tree))


def test_approved_wording_is_taken_from_the_rules_table_not_retyped():
    assert rules.entry("missing").wording == "◇ 資料未備" and rules.entry("undetermined").wording == "⬜ 無法判定"
    assert rules.entry("fetch_failed").wording == "⛔ 取數失敗" and rules.APPROVED_WORDING["insufficient"].text == "資料不足"
    assert W.status("missing").count(rules.entry("missing").wording) == 1
    assert rules.APPROVED_WORDING["insufficient"].text in W.plain("insufficient")
    for bad in ("ok", "attention", "stale", "not_configured"):
        with pytest.raises(KeyError):
            W.status(bad)


def test_unknown_wording_keys_are_errors_not_guesses():
    with pytest.raises(KeyError):
        W.text("no_such_key")
    with pytest.raises(KeyError):
        W.pending("no_such_key")


def test_wording_never_contains_a_forbidden_word_or_a_save_word():
    for key, item in W.FUND_SEARCH_PENDING.items():
        visible = item.text
        assert not [w for w in S.FORBIDDEN_WORDS if w in visible], (key, visible)
        assert not [w for w in S.SAVE_WORDS if w in visible], (key, visible)


def test_isin_note_is_symbol_free_and_marked_pending():
    assert not any(c in W.text("isin_note") for c in "◆◇⬜⛔◷✓✕▲◌")


# ───────────────────────── fixtures-are-fake ─────────────────────────

def test_every_fixture_value_is_marked_fake_or_missing():
    for sid in fake.SCENARIOS:
        for f in fake.build(sid)["pool"]:
            cells = f["cells"]
            assert cells["code"].startswith("FAKE-") and cells["name"].startswith("FAKE")
            for col, value in cells.items():
                assert value is None or value.startswith("FAKE"), (sid, col, value)
            assert set(cells) == set(fake.COLUMNS)
            assert len(f["states"]) == fake.CONDITION_COUNT and set(f["states"]) <= {fake.MATCH, fake.NOMATCH, fake.UNDET}
            if fake.UNDET in f["states"]:
                assert None in cells.values(), (sid, cells["code"])   # 資料不足無法判定的基金至少一格缺值
    assert fake.FAKE_FOUND_NAME.startswith("FAKE") and all(c.startswith("FAKE-") for c in fake.LOOKUP_FIXTURES)
    assert fake.FAKE_VALUE.startswith("FAKE")


def test_fixture_module_imports_nothing_but_the_future_module():
    mods = lib.imports_of(ast.parse((POC / "fund_search_fake_inputs.py").read_text(encoding="utf-8")), "x")
    assert {m for m in mods if not m.startswith("__future__")} == set(), mods


def test_fixture_codes_are_unique_per_pool_and_contain_no_url_host_or_credential_shape():
    for sid in fake.SCENARIOS:
        pool = fake.build(sid)["pool"]
        codes = [f["cells"]["code"] for f in pool]
        assert len(codes) == len(set(codes))
        for f in pool:
            for v in f["cells"].values():
                if isinstance(v, str):
                    assert "://" not in v and "@" not in v and not re.search(r":\d{3,5}\b", v)


# ───────────────────────── 隔離守衛 ─────────────────────────

_NAMES = re.compile(r"fund_search_fixture_preview|app_fund_search_preview|fund_search_fake_inputs|fund_search_renderer|fund_search_logic|fund_search_wording")
_PY_DIRS = ("ui", "ui_v2", "ui_v3", "services", "repositories", "shared", "infra", "scripts", "mcp_server", "models")
_TEXT_DIRS = (".streamlit", ".github", ".devcontainer")


def production_references(root: pathlib.Path):
    hits = []
    files = [p for d in _PY_DIRS if (root / d).exists() for p in (root / d).rglob("*.py") if "__pycache__" not in p.parts] + list(root.glob("*.py"))
    files += [p for d in _TEXT_DIRS if (root / d).exists() for p in (root / d).rglob("*") if p.is_file()]
    for p in files:
        try:
            text = p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        hits += [f"{p.relative_to(root)}: {m.group(0)}" for m in _NAMES.finditer(text)]
    return hits


def test_no_production_path_references_the_preview():
    assert production_references(ROOT) == []


def test_negative_control_reference_scan_turns_red(tmp_path):
    (tmp_path / "ui").mkdir()
    (tmp_path / "ui" / "x.py").write_text("import fund_search_renderer\n", encoding="utf-8")
    assert production_references(tmp_path)


def test_registry_app_preview_pages_and_shell_do_not_mention_the_preview_and_ui_v3_never_mentions_poc():
    files = [ROOT / "ui_v3" / "shell" / "registry.py", ROOT / "ui_v3" / "app_preview.py"]
    files += sorted((ROOT / "ui_v3" / "pages").glob("*.py")) + sorted((ROOT / "ui_v3" / "shell").glob("*.py"))
    assert len(files) >= 8 and all(f.exists() for f in files)
    for f in files:
        assert not re.search(r"fund_search|FundSearch", f.read_text(encoding="utf-8")), f.name
    for f in sorted((ROOT / "ui_v3").rglob("*.py")):
        assert "poc/" not in f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix()
    assert re.search(r"fund_search|FundSearch", "from ui_v3.pages import fund" + "_search")   # 負控：偵測得到


def test_registry_does_not_register_the_exp_page_and_navigation_is_untouched():
    text = (ROOT / "ui_v3" / "shell" / "registry.py").read_text(encoding="utf-8")
    assert "fund_search" not in text and "poc" not in text
    assert not (ROOT / "ui_v3" / "pages" / "exp.py").exists() and not (ROOT / "ui_v3" / "pages" / "fund_search.py").exists()


def test_directory_layout_has_no_pages_dir_or_package_init():
    assert not [d for d in (ROOT / "poc").rglob("*") if d.is_dir() and d.name == "pages"]
    assert not (ROOT / "poc" / "__init__.py").exists() and not (POC / "__init__.py").exists() and not (ROOT / "pages").exists()
    assert {p.suffix for p in POC.rglob("*") if p.is_file() and "__pycache__" not in p.parts} <= {".py", ".md"}
    assert {p.name for p in POC.iterdir() if p.is_file()} >= {"app_fund_search_preview.py", "fund_search_fake_inputs.py", "fund_search_renderer.py",
                                                              "fund_search_wording.py", "README.md"}


def test_no_streamlit_pages_or_config_files_were_added_for_the_preview():
    assert not list(POC.rglob(".streamlit")) and not list(POC.rglob("secrets*")) and not list(POC.rglob("*.toml"))


def test_readme_states_fake_non_formal_not_verified_pending_words_and_the_authorization():
    text = (POC / "README.md").read_text(encoding="utf-8")
    for needle in ("streamlit run poc/fund_search_fixture_preview/app_fund_search_preview.py", "FAKE", "NOT VERIFIED", "DEC-2026-11-17-02",
                   "PendingWording", "僅供畫面與計數演示，不得搬入 production", "S2-T0"):
        assert needle in text, needle
    assert "待定字" in text


def test_readme_pending_word_table_lists_every_pending_key():
    text = (POC / "README.md").read_text(encoding="utf-8")
    missing = [k for k in W.FUND_SEARCH_PENDING if f"`{k}`" not in text]
    assert missing == [], missing
