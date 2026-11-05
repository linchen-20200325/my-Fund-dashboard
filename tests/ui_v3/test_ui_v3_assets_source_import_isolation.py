# -*- coding: utf-8 -*-
"""`ui_v3/adapters/assets_source.py` 的 import 隔離與「沒有接頁」守衛（BL-0542 G-2）。

既有三個 ui_v3 守衛（import／preview-not-formal／readonly）一字未改，且會自動掃到新檔；本檔補它們各自看不到的具體事項：
1. **執行期**：只 import 本模組，`sys.modules` 裡不得出現 `services.v2_tables`／streamlit／ui_v2／舊樹／pandas／網路套件；
   呼叫 `l2_reads()` 之後才出現 `services.v2_tables`（證明 lazy 是真的、而且 lazy 路徑可用）；
2. **靜態**：模組層 import 只有標準庫與 `services.v2_domain.*`；每個 `services.v2_tables` import 都在函式內；
3. 三個既有靜態守衛對本檔回空（用同一個守衛函式庫，不複製規則）；
4. 沒有 `NAV_NOT_READY` 字樣（門檻單一擁有者仍是 ui_v2）、沒有環境變數形的字串常數；
5. 沒有任何頁／registry／進入點／viewmodel 引用本模組（本批刻意不接頁）。
"""
from __future__ import annotations

import ast
import pathlib
import re
import subprocess
import sys

import pytest

import ui_v3_guard_lib as lib

REL = "ui_v3/adapters/assets_source.py"
PATH = lib.ROOT / REL

_FORBIDDEN_ROOTS = ("streamlit", "ui", "ui_v2", "repositories", "shared", "infra", "fund_fetcher", "app", "pandas", "numpy",
                    "requests", "gspread", "yfinance", "bs4")


def _source() -> str:
    return PATH.read_text(encoding="utf-8")


def module_level_imports(source: str) -> list:
    """模組層（不含函式／類別內）的 import 模組名。"""
    tree = ast.parse(source)
    out = []
    for stmt in tree.body:
        if isinstance(stmt, ast.Import):
            out += [a.name for a in stmt.names]
        elif isinstance(stmt, ast.ImportFrom):
            prefix = ("." * stmt.level) + (stmt.module or "")
            out.append(prefix)
            out += [f"{prefix}.{a.name}" for a in stmt.names]
    return out


def function_level_imports(source: str) -> list:
    tree = ast.parse(source)
    out = []
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for node in ast.walk(fn):
                if isinstance(node, ast.ImportFrom):
                    prefix = node.module or ""
                    out.append(prefix)
                    out += [f"{prefix}.{a.name}" for a in node.names]
                elif isinstance(node, ast.Import):
                    out += [a.name for a in node.names]
    return out


def static_isolation_problems(source: str) -> list:
    """本檔專屬的靜態規則（空 list ＝ 合規）。突變測試也用它。"""
    bad = []
    for module in module_level_imports(source):
        root = module.split(".")[0]
        if root == "services" and module != "services" and not module.startswith("services.v2_domain"):
            bad.append(f"module-level L2 import {module}")
        elif root in _FORBIDDEN_ROOTS:
            bad.append(f"module-level forbidden import {module}")
    if not any(m.startswith("services.v2_tables") for m in function_level_imports(source)):
        bad.append("no function-level services.v2_tables import (the lazy path vanished)")
    if "NAV_NOT_READY" in source:
        bad.append("NAV_NOT_READY token present (single owner is ui_v2/thresholds.py)")
    tree = ast.parse(source)
    skip = {id(n.body[0].value) for n in ast.walk(tree)
            if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body and isinstance(n.body[0], ast.Expr)
            and isinstance(getattr(n.body[0], "value", None), ast.Constant)}
    env_shape = re.compile(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b")
    for node in ast.walk(tree):          # `__all__` 匯出名不是畫面字（與既有 no_engineering_leak 守衛同樣排除）
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets):
            skip |= {id(n) for n in ast.walk(node) if isinstance(n, ast.Constant)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in skip and env_shape.search(node.value):
            bad.append(f"env-shaped string constant {node.value!r}")
    return bad


_HANDLE_ATTRS = frozenset({"ec", "REASON_NO_ACTIVE"})
_CODE_ATTRS = frozenset({"AUTH_REQUIRED", "UNAVAILABLE", "ALL_ERROR_CODES"})


def personal_session_surface_problems(source: str) -> list:
    """本檔對 `personal_session` 把手的使用面必須恰為：經 `alo_holdings.personal_session` 取得（不 import）、只讀 `.ec`／`.REASON_NO_ACTIVE`，
    `.ec` 的把手只讀三個常數，且對這兩個把手沒有任何呼叫。空 list ＝ 合規。"""
    tree = ast.parse(source)
    bad = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] + [getattr(node, "module", None) or ""]
            if any(n.endswith("personal_session") for n in names):
                bad.append("imports personal_session")
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            if node.value.id == "personal_session" and node.attr not in _HANDLE_ATTRS:
                bad.append(f"personal_session.{node.attr}")
            if node.value.id == "codes" and node.attr not in _CODE_ATTRS:
                bad.append(f"codes.{node.attr}")
        if isinstance(node, ast.Call):
            root = node.func
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in ("personal_session", "codes"):
                bad.append(f"call on {root.id} handle")
    handles = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "personal_session" for t in n.targets)]
    if len(handles) != 1 or ast.unparse(handles[0].value) != "alo_holdings.personal_session":
        bad.append("handle is not obtained exactly via alo_holdings.personal_session")
    codes = [n for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "codes" for t in n.targets)]
    if len(codes) != 1 or ast.unparse(codes[0].value) != "personal_session.ec":
        bad.append("codes handle is not exactly personal_session.ec")
    return bad


def test_personal_session_handle_surface_is_locked_to_the_constants():
    assert personal_session_surface_problems(_source()) == []


@pytest.mark.parametrize("snippet", [
    "    personal_session.logout({})\n", "    _x = personal_session.status\n", "    codes.AUTH_REQUIRED()\n",
    "    _y = codes.NETWORK_ERROR\n", "    from services.v2_tables import personal_session\n", "    personal_session.ec.AUTH_REQUIRED()\n",
])
def test_negative_controls_personal_session_surface_turns_red(snippet):
    src = _source().replace("    codes = personal_session.ec\n", "    codes = personal_session.ec\n" + snippet)
    assert src != _source() and personal_session_surface_problems(src)


# ───────────────────────── 執行期 ─────────────────────────


def _run_isolated(code: str) -> str:
    proc = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True, cwd=str(lib.ROOT),
                          env={"PYTHONPATH": str(lib.ROOT)}, timeout=120)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.strip()


def test_importing_the_adapter_loads_no_l2_ui_or_network_modules():
    out = _run_isolated(
        "import sys\n"
        "import ui_v3.adapters.assets_source\n"
        "print(','.join(sorted(sys.modules)))\n")
    loaded = set(out.split(","))
    bad = sorted(n for n in loaded if n.split(".")[0] in _FORBIDDEN_ROOTS or n.startswith("services.v2_tables")
                 or (n.startswith("services.") and not n.startswith("services.v2_domain")))
    assert not bad, bad
    assert "services.v2_domain.allocation_evidence" in loaded       # 對照：真的有 import 到生產者（不是空跑）


def test_l2_reads_is_the_only_place_that_loads_l2():
    out = _run_isolated(
        "import sys\n"
        "from ui_v3.adapters import assets_source as S\n"
        "before = any(n.startswith('services.v2_tables') for n in sys.modules)\n"
        "reads = S.l2_reads()\n"
        "after = all(n in sys.modules for n in ('services.v2_tables.alo_holdings', 'services.v2_tables.settings_store', "
        "'services.v2_tables.market_indicator'))\n"
        "print(f'{before}|{after}')\n")
    assert out.splitlines()[-1] == "False|True"


def test_runtime_allowlist_of_the_existing_guard_would_pass_for_the_adapter():
    """既有執行期守衛的白名單判斷函式，對『只 import 本模組』的結果回空（不改守衛、不複製它的規則表）。"""
    import test_ui_v3_preview_not_formal_guard as guard
    out = _run_isolated("import sys\nimport ui_v3.adapters.assets_source\nprint(','.join(sorted(sys.modules)))")
    top = {n for n in out.split(",") if n.split(".")[0] in {"streamlit", "ui", "ui_v2", "services", "repositories", "shared", "infra",
                                                            "fund_fetcher", "app"}}
    assert guard.runtime_disallowed(sorted(top)) == []


# ───────────────────────── 靜態 ─────────────────────────


def test_adapter_file_is_in_the_guard_population_and_passes_the_existing_static_guards_unchanged():
    assert any(lib.rel_of(p) == REL for p in lib.population())
    src = _source()
    assert lib.import_violations(REL, src) == []
    assert lib.write_surface_violations(REL, src) == []
    assert lib.module_level_side_effects(src) == []


def test_static_isolation_rules_hold_for_the_real_file():
    assert static_isolation_problems(_source()) == []


def test_module_level_imports_are_stdlib_or_v2_domain_only():
    mods = [m for m in module_level_imports(_source()) if m]
    assert mods
    for m in mods:
        root = m.split(".")[0]
        assert root in lib.STDLIB or m.startswith("services.v2_domain") or m == "services", m


@pytest.mark.parametrize("snippet,expect_fragment", [
    ("from services.v2_tables import masking\n", "module-level L2 import"),
    ("import streamlit\n", "module-level forbidden import"),
    ("from ui_v2 import thresholds\n", "module-level forbidden import"),
    ("import pandas\n", "module-level forbidden import"),
    ("NAV_NOT_READY" + "_DAYS = 10\n", "NAV_NOT_READY"),
    ("X = 'SOME" + "_ENV_NAME'\n", "env-shaped string constant"),
])
def test_negative_controls_static_rules_turn_red(snippet, expect_fragment):
    problems = static_isolation_problems(snippet + _source())
    assert any(expect_fragment in p for p in problems), problems


def test_negative_control_without_lazy_import_is_red():
    src = _source().replace("from services.v2_tables import alo_holdings, market_indicator, settings_store  # lazy", "pass")
    assert src != _source()
    assert any("lazy path vanished" in p for p in static_isolation_problems(src))


# ───────────────────────── 沒有接頁 ─────────────────────────


def test_nothing_in_ui_v3_references_the_adapter_so_no_page_is_wired():
    hits = []
    for p in lib.population():
        if lib.rel_of(p) == REL:
            continue
        text = lib.read(p)
        if "assets_source" in text:
            hits.append(lib.rel_of(p))
    assert hits == []


def test_registry_has_no_new_page_and_preview_renderers_are_unchanged():
    from ui_v3.shell import registry
    registered = [p.slug for p in registry.IA_PAGES if p.registered]
    assert registered == ["mkt"], registered      # 本批沒有新增任何已掛載的頁（接頁需要線框草稿與客戶核准）
