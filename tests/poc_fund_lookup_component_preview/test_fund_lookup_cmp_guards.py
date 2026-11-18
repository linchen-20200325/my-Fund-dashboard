# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件 隔離式 FAKE Preview：AST／靜態／隔離／字樣／fixtures-are-fake 守衛（不開 Streamlit、不開瀏覽器）。

負控一律在記憶體內現編，不寫檔。
"""
from __future__ import annotations

import ast
import re

import pytest

import fund_lookup_cmp_support as S

import fund_lookup_fake_inputs as fake  # noqa: E402
import fund_lookup_wording as W  # noqa: E402
import ui_v3_guard_lib as lib  # noqa: E402
from shared.ui_semantics import rules  # noqa: E402
from ui_v3.viewmodels import exp_counts  # noqa: E402
from ui_v3.viewmodels.preview_wording import PendingWording  # noqa: E402

ROOT, POC = S.ROOT, S.POC
POC_PY = sorted(POC.glob("*.py"))
ENTRY = POC / "app_fund_lookup_component_preview.py"
RENDERER = POC / "fund_lookup_renderer.py"
WORDING = POC / "fund_lookup_wording.py"
FAKE_INPUTS = POC / "fund_lookup_fake_inputs.py"
LOCAL_MODULES = {"fund_lookup_fake_inputs", "fund_lookup_renderer", "fund_lookup_wording"}

# ───────────────────────── import 白名單（每個檔各有更窄的許可） ─────────────────────────
STDLIB_OK = {"__future__", "html", "types", "typing", "pathlib", "sys"}
# 全目錄通用的 ui_v3／shared 許可：design token、fund_lookup ViewModel、PendingWording 型別、已核准的 shared.ui_semantics（DEC-2026-11-17-03 G-1）。
SHARED_PREFIX = ("ui_v3.design", "ui_v3.viewmodels.fund_lookup", "ui_v3.viewmodels.preview_wording", "shared.ui_semantics")
PARENT_ONLY = {"ui_v3", "ui_v3.viewmodels", "shared"}     # `from a.b import c` 會連帶回報上層套件名，上層本身不是新依賴
# 每個檔再縮窄：只有 harness 入口可 import adapter 與 streamlit 的頂層；renderer 只在函式內 import streamlit。
PER_FILE_EXTRA = {
    "app_fund_lookup_component_preview.py": ("ui_v3.adapters.fund_lookup",),
    "fund_lookup_renderer.py": (),
    "fund_lookup_wording.py": (),
    "fund_lookup_fake_inputs.py": (),
}
STREAMLIT_FILES = {"app_fund_lookup_component_preview.py", "fund_lookup_renderer.py"}
FORBIDDEN = ("ui_v3.app_preview", "ui_v3.shell", "ui_v3.pages", "ui_v3.fixtures", "ui_v3.adapters.assets_page", "ui_v3.adapters.assets_source",
             "ui_v3.adapters.exp_pool", "ui_v3.adapters.market_chart", "ui_v3.adapters.market_page", "ui_v3.adapters.shell_status",
             "services", "gspread", "requests", "urllib", "urllib3", "socket", "ssl", "http", "subprocess", "os", "repositories", "infra", "ui", "ui_v2",
             "app", "yfinance", "httpx", "feedparser", "secrets", "tempfile", "shutil", "json", "pickle", "sqlite3", "glob", "importlib", "logging",
             "fund_fetcher", "ui_v3.viewmodels.exp_counts", "ui_v3.viewmodels.exp_pool", "ui_v3.viewmodels.market_page")


def import_violations(src: str, filename: str = "fund_lookup_renderer.py"):
    out = []
    extra = PER_FILE_EXTRA.get(filename, ())
    for module in lib.imports_of(ast.parse(src), "x"):
        root = module.split(".")[0]
        if any(module == f or module.startswith(f + ".") for f in FORBIDDEN):
            out.append(f"禁止的 import：{module}")
        elif root in LOCAL_MODULES or module in PARENT_ONLY or root in STDLIB_OK:
            continue
        elif root == "streamlit":
            if filename not in STREAMLIT_FILES:
                out.append(f"此檔不得 import streamlit：{module}")
        elif any(module == p or module.startswith(p + ".") for p in SHARED_PREFIX + tuple(extra)):
            continue
        elif module.startswith("shared"):
            out.append(f"shared 只開 shared.ui_semantics：{module}")
        else:
            out.append(f"不在白名單的 import：{module}")
    return out


@pytest.mark.parametrize("path", POC_PY, ids=lambda p: p.name)
def test_imports_are_inside_the_per_file_allowlist(path):
    assert import_violations(path.read_text(encoding="utf-8"), path.name) == []


def test_only_the_harness_entry_may_import_the_adapter_and_only_the_renderer_and_entry_may_import_streamlit():
    for path in POC_PY:
        mods = lib.imports_of(ast.parse(path.read_text(encoding="utf-8")), "x")
        assert (any(m.startswith("ui_v3.adapters") for m in mods)) is (path == ENTRY), path.name
        assert (any(m.split(".")[0] == "streamlit" for m in mods)) is (path.name in STREAMLIT_FILES), path.name


def test_the_renderer_imports_streamlit_only_inside_functions_so_the_pure_part_runs_without_it():
    tree = ast.parse(RENDERER.read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom)) and any((getattr(n, "module", None) or a.name).split(".")[0] == "streamlit"
                                                                                       for a in n.names + [ast.alias(name=getattr(n, "module", "") or "")])]
    assert top == []


def test_the_only_ui_v3_internal_imports_are_fund_lookup_viewmodel_adapter_design_and_preview_wording():
    allowed = ("ui_v3.viewmodels.fund_lookup", "ui_v3.adapters.fund_lookup", "ui_v3.design", "ui_v3.viewmodels.preview_wording")
    for path in POC_PY:
        for m in lib.imports_of(ast.parse(path.read_text(encoding="utf-8")), "x"):
            if m.split(".")[0] == "ui_v3" and m not in PARENT_ONLY:
                assert any(m == a or m.startswith(a + ".") for a in allowed), (path.name, m)


@pytest.mark.parametrize("src", [
    "import requests\n", "import urllib.request\n", "from urllib import request\n", "import socket\n", "import subprocess\n", "import os\n",
    "import ssl\n", "import http.client\n", "import gspread\n", "import httpx\n", "import yfinance\n", "import json\n", "import shutil\n", "import logging\n",
    "from services import fund_search\n", "from repositories.fund import sources\n", "from infra.proxy import fetch_url\n", "from ui import sidebar\n",
    "import ui_v2\n", "from shared.ttls import TTL_1MIN\n", "from shared import fred_series\n", "from ui_v3.app_preview import main\n",
    "from ui_v3.shell.registry import IA_PAGES\n", "from ui_v3.pages import nas_diag\n", "from ui_v3 import fixtures\n", "from ui_v3.adapters import market_page\n",
    "from ui_v3.viewmodels import exp_counts\n", "from ui_v3.viewmodels.exp_pool import X\n", "import secrets\n", "import tempfile\n", "import fund_fetcher\n",
    "from ui_v3.viewmodels import market_page\n", "import importlib\n", "from ui_v3.adapters.exp_pool import X\n"])
def test_negative_control_import_checker_turns_red(src):
    assert import_violations(src), src


def test_negative_control_streamlit_and_adapter_scoping():
    assert import_violations("import streamlit as st\n", "fund_lookup_wording.py")
    assert import_violations("from ui_v3.adapters.fund_lookup import lookup_fund\n", "fund_lookup_renderer.py")
    assert not import_violations("from ui_v3.adapters.fund_lookup import lookup_fund\n", "app_fund_lookup_component_preview.py")


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
                   "write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "rmtree", "set_page_config", "cache_data", "cache_resource",
                   "get_session_state", "secrets_manager", "query_params", "experimental_get_query_params"}
    assert not bad, bad
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"open", "exec", "eval", "compile", "__import__", "input"}


def test_negative_control_for_the_ast_name_scan():
    tree = ast.parse("import os\nos.environ.get('X')\n")
    assert {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} & {"environ", "getenv"}


def test_module_level_has_no_side_effects_except_the_entry_path_setup_and_main_call():
    for path in POC_PY:
        bad = lib.module_level_side_effects(path.read_text(encoding="utf-8"))
        if path == ENTRY:     # 入口慣例：sys.path 設定迴圈＋最後一行 `main()`；其餘模組 import 零副作用
            assert [b.split(": ")[1] for b in bad] == ["For", "Expr"], bad
            body = ast.parse(path.read_text(encoding="utf-8")).body
            assert isinstance(body[-1], ast.Expr) and ast.unparse(body[-1]) == "main()"
        else:
            assert bad == [], (path.name, bad)


# ───────────────────────── session_state：只存淨化後的 ViewModel，不存輸入原值 ─────────────────────────

def _is_session_state(node, aliases=frozenset()) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == "session_state") or (isinstance(node, ast.Name) and (node.id == "session_state" or node.id in aliases))


def _aliases(tree) -> frozenset:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "streamlit":
            out |= {a.asname for a in node.names if a.name == "session_state" and a.asname}
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
            targets = node.targets if isinstance(node, ast.Assign) else ([node.target] if isinstance(node, ast.AnnAssign) else [])
            if value is not None and _is_session_state(value, frozenset(out)):
                for t in targets:
                    if isinstance(t, ast.Name) and t.id not in out:
                        out.add(t.id)
                        changed = True
    return frozenset(out)


def session_state_writes(src: str):
    """所有寫 `session_state` 的形式（下標賦值、增量賦值、整個物件被賦值、刪除、屬性賦值、update／setdefault／pop／popitem／clear；含別名）。回傳 (描述, 右值 unparse)。"""
    tree = ast.parse(src)
    aliases = _aliases(tree)
    out = []
    for node in ast.walk(tree):
        targets, value = [], None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            targets, value = [node.target], node.value
        elif isinstance(node, ast.Delete):
            targets = node.targets
        for t in targets:
            rhs = ast.unparse(value) if value is not None else ""
            if isinstance(t, ast.Subscript) and _is_session_state(t.value, aliases):
                out.append((f"{type(node).__name__}[{ast.unparse(t.slice)}]", rhs))
            elif isinstance(t, ast.Attribute) and _is_session_state(t.value, aliases):
                out.append((f"{type(node).__name__}.{t.attr}", rhs))
            elif isinstance(node, ast.AugAssign) and _is_session_state(t, aliases):
                out.append((f"AugAssign.{type(node.op).__name__}", rhs))
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and _is_session_state(node.func.value, aliases) \
                and node.func.attr in {"update", "setdefault", "pop", "popitem", "clear"}:
            out.append((f"call.{node.func.attr}", ast.unparse(node)))
    return out


def test_only_one_session_state_write_exists_and_its_value_is_the_adapter_view_not_the_raw_input():
    writes = {p.name: session_state_writes(p.read_text(encoding="utf-8")) for p in POC_PY}
    assert writes["app_fund_lookup_component_preview.py"] == [("Assign[R.KEY_VIEW]", "lookup_fund(fake.make_loader(), raw)")], writes
    assert all(v == [] for k, v in writes.items() if k != "app_fund_lookup_component_preview.py"), writes


@pytest.mark.parametrize("src,expected", [
    ("import streamlit as st\nst.session_state['k'] = 1\n", [("Assign['k']", "1")]),
    ("import streamlit as st\nst.session_state['k'] += 1\n", [("AugAssign['k']", "1")]),
    ("import streamlit as st\ndel st.session_state['k']\n", [("Delete['k']", "")]),
    ("import streamlit as st\nst.session_state.k = 1\n", [("Assign.k", "1")]),
    ("import streamlit as st\nst.session_state.update({'k': 1})\n", [("call.update", "st.session_state.update({'k': 1})")]),
    ("from streamlit import session_state as ss\nss['k'] = raw\n", [("Assign['k']", "raw")]),
    ("import streamlit as st\nss = st.session_state\nss['k'] = raw\n", [("Assign['k']", "raw")]),
    ("import streamlit as st\nst.session_state |= {'k': 1}\n", [("AugAssign.BitOr", "{'k': 1}")]),
    ("import streamlit as st\nx = st.session_state.get('k')\ny = {}\ny['k'] = 1\n", [])])
def test_negative_control_session_state_write_scan(src, expected):
    assert session_state_writes(src) == expected


# ───────────────────────── ViewModel 只經 adapter 產生，不繞過 ─────────────────────────

def test_fund_lookup_view_is_constructed_only_inside_the_conflict_demo_never_in_the_renderer_or_the_harness():
    for path in POC_PY:
        tree = ast.parse(path.read_text(encoding="utf-8"))
        hits = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and (getattr(n.func, "id", None) == "FundLookupView" or getattr(n.func, "attr", None) == "FundLookupView")]
        if path == FAKE_INPUTS:
            fns = {f.name for f in ast.walk(tree) if isinstance(f, ast.FunctionDef) and any(h in list(ast.walk(f)) for h in hits)}
            assert fns == {"conflict_view"}, fns
        else:
            assert hits == [], path.name


def test_the_harness_gets_the_view_from_lookup_fund_with_a_fake_loader_and_marks_the_conflict_case_as_direct_construction():
    src = ENTRY.read_text(encoding="utf-8")
    assert "lookup_fund(fake.make_loader(), raw)" in src and "fake.conflict_view()" in src
    assert "直接建構" in src and "現行 L2 不可達" in src


# ───────────────────────── 字樣守衛 ─────────────────────────

def code_strings(path):
    """檔內所有字串常數，**排除 docstring**（模組／函式／類別的第一個字串運算式）；說明文字可以提到字樣，程式碼的字串常數不行。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docs = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                docs.add(id(first.value))
    return [n.value for n in ast.walk(tree) if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docs]


def _approved_strings():
    out = {a.text for a in rules.APPROVED_WORDING.values()} | {a.ruling_text for a in rules.APPROVED_WORDING.values()}
    out |= {e.wording for e in rules.ENTRIES.values() if e.wording and e.wording != rules.PENDING_WORDING}
    out |= {getattr(exp_counts, n) for n in dir(exp_counts) if n.startswith("TEXT_")}
    return {s for s in out if isinstance(s, str) and s.strip()}


def test_every_new_wording_is_a_pending_wording_with_the_dec_source_and_never_a_rules_key_or_text():
    approved = _approved_strings()
    assert W.FUND_LOOKUP_PENDING and W.SOURCE == "DEC-2026-11-18-04（轉述，待核）"
    for key, item in W.FUND_LOOKUP_PENDING.items():
        assert isinstance(item, PendingWording) and item.status == "pending" and item.key == key and item.source == W.SOURCE
        assert key not in rules.APPROVED_WORDING and key not in rules.ENTRIES
        assert item.text not in approved and item.text.strip() not in approved
        assert not any(a in item.text for a in approved if len(a) >= 4 and a not in ("尚未查詢",)), (key, item.text)   # 也不得內含任何已核准字樣


def test_no_string_literal_in_the_poc_files_duplicates_an_approved_wording():
    approved = _approved_strings()
    for path in POC_PY:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value.strip() not in approved, (path.name, node.value)


def test_negative_control_literal_scan_would_catch_a_duplicate():
    approved = _approved_strings()
    assert "◇ 資料未備" in approved and "資料不足" in approved
    assert any(isinstance(n, ast.Constant) and n.value in approved for n in ast.walk(ast.parse("x = '◇ 資料未備'\n")))


def test_approved_symbols_and_wording_are_taken_from_the_rules_api_not_retyped_in_code():
    for path in POC_PY:
        joined = "\n".join(code_strings(path))
        for token in ("⛔ 取數失敗", "⬜ 無法判定", "◇ 資料未備", "資料不足"):
            assert token not in joined, (path.name, token)
        for symbol in "◆◇⬜⛔◷":
            assert symbol not in joined, (path.name, symbol)
    assert rules.entry("undetermined").wording in W.status("undetermined") and rules.entry("fetch_failed").wording in W.status("fetch_failed")


def test_negative_control_code_strings_excludes_docstrings_but_catches_code_constants(tmp_path):
    p = tmp_path / "x.py"
    p.write_text('"""doc ⛔ 取數失敗"""\nx = "⛔ 取數失敗"\ndef f():\n    """d ⬜"""\n    return "⬜"\n', encoding="utf-8")
    assert code_strings(p) == ["⛔ 取數失敗", "⬜"]


def test_the_formal_mode_missing_text_never_appears_in_any_rendered_state_and_the_missing_entry_is_never_used():
    formal = rules.entry("missing").wording
    for _label, view in S.build_views():
        for fake_flag in (True, False):
            import fund_lookup_renderer as R
            html = R.lookup_card_html(view, fake=fake_flag)
            assert formal not in html and "◇" not in html
    for path in POC_PY:
        src = path.read_text(encoding="utf-8")
        assert "MISSING_TEXT" not in src and 'entry("missing")' not in src and "entry('missing')" not in src, path.name


def test_wording_never_contains_a_forbidden_or_unapproved_field_word():
    for key, item in W.FUND_LOOKUP_PENDING.items():
        assert not [w for w in S.FORBIDDEN_WORDS if w in item.text], (key, item.text)
        assert not [w for w in ("存檔", "儲存", "保存") if w in item.text], key


def test_source_string_literals_in_code_files_contain_no_unapproved_field_names():
    tokens = ("ccy", "NAV", "fetched_at", "Provider", "provider", "淨值", "報酬", "績效", "幣別", "取得時間", "供應者", "來源等級", "原始回應", "資料日")
    for path in (RENDERER, ENTRY, FAKE_INPUTS, WORDING):
        for value in code_strings(path):
            assert not [t for t in tokens if t in value], (path.name, value[:60])


def test_states_do_not_share_wording_across_unrelated_meanings():
    texts = {k: v.text for k, v in W.FUND_LOOKUP_PENDING.items()}
    assert len(set(texts.values())) == len(texts)                                            # 沒有兩個鍵字樣相同
    for key in texts:
        if key.startswith(("failed_", "unmatched_", "blocked_")):
            assert "不存在" not in texts[key] and "查無" not in texts[key]


def test_unknown_wording_keys_are_errors_not_guesses():
    with pytest.raises(KeyError):
        W.text("no_such_key")


# ───────────────────────── token：不寫死色碼 ─────────────────────────

def test_no_literal_color_codes_in_the_poc_sources_colors_come_from_tokens():
    for path in POC_PY:
        src = path.read_text(encoding="utf-8")
        assert not re.search(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\(|hsla?\(", src.replace("&#", "")), path.name
    assert "theme.v(" in RENDERER.read_text(encoding="utf-8") and "theme.m(" in RENDERER.read_text(encoding="utf-8")


def test_negative_control_color_literal_scan():
    assert re.search(r"#[0-9a-fA-F]{6}\b", "color:#1a2b3c")
    assert re.search(r"rgba?\(", "color:rgb(0,0,0)")


# ───────────────────────── fixtures-are-fake ─────────────────────────

def test_every_demo_code_name_and_date_is_marked_fake_and_no_real_identity_or_url_is_present():
    assert fake.FAKE_NAME.startswith("FAKE") and fake.CONFLICT_CODE.startswith("FAKE-")
    for code in fake.FAKE_CODES:
        assert code.startswith("FAKE-"), code
    src = FAKE_INPUTS.read_text(encoding="utf-8")
    assert "://" not in src and "@" not in src.replace("@dataclass", "") and not re.search(r":\d{3,5}\b", src.replace("::", ""))
    for label, view in S.build_views():
        if view.fields is not None and label not in ("nasty-name", "xss-name"):
            assert view.fields.fund_name.value.startswith("FAKE"), label


def test_fixture_module_imports_only_the_fund_lookup_viewmodel_and_stdlib():
    mods = {m for m in lib.imports_of(ast.parse(FAKE_INPUTS.read_text(encoding="utf-8")), "x") if not m.startswith("__future__")}
    assert {m for m in mods if not m.startswith(("typing", "ui_v3.viewmodels.fund_lookup"))} <= {"ui_v3", "ui_v3.viewmodels"} | set(), mods


def test_fake_codes_cover_every_adapter_reason_code_and_every_state():
    from ui_v3.adapters.fund_lookup import lookup_fund
    from ui_v3.viewmodels import fund_lookup as VM
    seen = set()
    for code in fake.FAKE_CODES:
        view = lookup_fund(fake.make_loader(), code)
        seen.add((view.state, view.reason_code))
    for raw in ("   ", "US0378331005", "http://x.example", "A<B>C", "\tA", "L" * 70, "ZZZ999"):
        view = lookup_fund(fake.make_loader(), raw)
        seen.add((view.state, view.reason_code))
    reasons = {r for (_s, r) in seen}
    assert reasons >= (VM.BLOCKED_REASONS | VM.SOURCE_FAILED_REASONS | VM.PAGE_UNMATCHED_REASONS), (VM.BLOCKED_REASONS | VM.SOURCE_FAILED_REASONS | VM.PAGE_UNMATCHED_REASONS) - reasons
    assert {s for (s, _r) in seen} >= {VM.LookupState.RESULT, VM.LookupState.BLOCKED, VM.LookupState.SOURCE_FAILED, VM.LookupState.PAGE_UNMATCHED}
    for code, (_desc, expect) in fake.FAKE_CODES.items():
        view = lookup_fund(fake.make_loader(), code)
        got = view.state.name if view.reason_code is None else f"{view.state.name}/{view.reason_code}"
        assert got == expect, (code, got, expect)


# ───────────────────────── 隔離守衛 ─────────────────────────

_NAMES = re.compile(r"fund_lookup_component_preview|app_fund_lookup_component_preview|fund_lookup_fake_inputs|fund_lookup_renderer|fund_lookup_wording")
_PY_DIRS = ("ui", "ui_v2", "ui_v3", "services", "repositories", "shared", "infra", "scripts", "mcp_server", "models")
_TEXT_DIRS = (".streamlit", ".github", ".devcontainer")


def production_references(root):
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
    (tmp_path / "ui" / "x.py").write_text("import fund_lookup_renderer\n", encoding="utf-8")
    assert production_references(tmp_path)


def test_registry_app_preview_pages_and_shell_do_not_mention_the_preview_and_ui_v3_never_mentions_poc():
    files = [ROOT / "ui_v3" / "shell" / "registry.py", ROOT / "ui_v3" / "app_preview.py"]
    files += sorted((ROOT / "ui_v3" / "pages").glob("*.py")) + sorted((ROOT / "ui_v3" / "shell").glob("*.py"))
    assert len(files) >= 8 and all(f.exists() for f in files)
    for f in files:
        assert not re.search(r"fund_lookup_component|FundLookupComponent", f.read_text(encoding="utf-8")), f.name
    for f in sorted((ROOT / "ui_v3").rglob("*.py")):
        assert "poc/" not in f.read_text(encoding="utf-8"), f.relative_to(ROOT).as_posix()


def test_no_pages_dir_no_package_init_no_config_or_secret_files_and_the_exact_file_set():
    assert not [d for d in (ROOT / "poc").rglob("*") if d.is_dir() and d.name == "pages"]
    assert not (POC / "__init__.py").exists() and not (ROOT / "pages").exists()
    assert not list(POC.rglob(".streamlit")) and not list(POC.rglob("secrets*")) and not list(POC.rglob("*.toml"))
    assert {p.name for p in POC.iterdir() if p.is_file()} == {"app_fund_lookup_component_preview.py", "fund_lookup_fake_inputs.py", "fund_lookup_renderer.py",
                                                              "fund_lookup_wording.py", "README.md"}


def test_readme_states_fake_non_formal_not_verified_the_authorization_and_the_open_points():
    text = (POC / "README.md").read_text(encoding="utf-8")
    for needle in ("streamlit run poc/fund_lookup_component_preview/app_fund_lookup_component_preview.py", "FAKE", "NOT VERIFIED", "DEC-2026-11-18-04",
                   "PendingWording", "待客戶", "EXP-2", "收合區標題", "◇", "⬜", "Cloud", "真機", "螢幕閱讀器", "CONFLICT", "不可達",
                   "不掛 registry", "390", "1280", "full_key", "別名表", "InputInstructions", "display:inline", "component_css", "fl-status"):
        assert needle in text, needle
    assert "待定字" in text


def test_readme_pending_word_table_lists_every_pending_key():
    text = (POC / "README.md").read_text(encoding="utf-8")
    missing = [k for k in W.FUND_LOOKUP_PENDING if f"`{k}`" not in text]
    assert missing == [], missing
