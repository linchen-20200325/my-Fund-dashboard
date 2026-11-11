# -*- coding: utf-8 -*-
"""雙模式隔離 PoC 的自帶守衛（DEC-2026-11-11-02 P3）。

證明：(1) 沒有任何正式路徑 import／引用 PoC；(2) PoC 沒有任何寫入面（因此不可能寫 `ui_v3`），也沒有 ui_v3 import；
(3) PoC 不含 JS／browser storage／網路／query-param／st.context 等未授權機制；(4) 沒有 `pages/`、沒有 `__init__.py`、檔名唯一；
(5) 暗色值沒有進 `ui_v3/design/tokens.py`、`.streamlit/config.toml` 沒有被加 dark 區段。
每個守衛都有「記憶體內現編」的負控（變異驗證）：守衛函式對違規內容必須報紅。
"""
import ast
import os
import pathlib
import re
import sys

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_POC = _ROOT / "poc" / "dual_theme_isolated"
_TESTS = _ROOT / "tests"

# 正式路徑（與 `test_ui_v3_preview_not_formal_guard` 的候選清單同向，再加 ui_v3 自己）
_PY_DIRS = ("ui", "ui_v2", "ui_v3", "services", "repositories", "shared", "infra", "scripts", "mcp_server", "models")
_TEXT_DIRS = (".streamlit", ".github", ".devcontainer")
_REF = re.compile(r"dual_theme_isolated|\bapp_poc\b|\bpoc_(?:page|palettes|theme_css|chart_svg|fixtures)\b|(?<![A-Za-z0-9_])poc/")

_ALLOWED_IMPORTS = {"__future__", "html", "math", "datetime", "types", "pathlib", "sys", "streamlit"}
_ALLOWED_LOCAL_PREFIX = "poc_"
_FORBIDDEN_NAMES = {"open", "exec", "eval", "compile", "__import__", "globals", "locals", "vars", "input"}
_FORBIDDEN_ATTRS = {"write_text", "write_bytes", "mkdir", "touch", "unlink", "rename", "replace", "rmdir", "chmod", "symlink_to",
                    "context", "query_params", "components", "session_storage", "local_storage", "cookies", "experimental_get_query_params",
                    "set_query_params", "write", "writelines", "to_csv", "to_parquet", "to_json", "dump", "dumps"}
_FORBIDDEN_STRINGS = ("<script", "javascript:", "localstorage", "sessionstorage", "document.cookie", "indexeddb", "unsafe_allow_javascript", "fetch(", "xmlhttprequest")


# ───────────────────────── 守衛函式（可對任意目錄／來源跑，供負控使用） ─────────────────────────

def scan_poc_references(root: pathlib.Path):
    hits = []
    for d in _PY_DIRS:
        for dirpath, dirnames, filenames in os.walk(root / d):
            dirnames[:] = [x for x in dirnames if x != "__pycache__"]
            for f in filenames:
                if f.endswith(".py"):
                    hits += _scan_file(root, pathlib.Path(dirpath) / f)
    for p in root.glob("*.py"):
        hits += _scan_file(root, p)
    for d in _TEXT_DIRS:
        for dirpath, _dirs, filenames in os.walk(root / d):
            for f in filenames:
                hits += _scan_file(root, pathlib.Path(dirpath) / f)
    return hits


def _scan_file(root, path):
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    return [f"{path.relative_to(root)}: {m.group(0)}" for m in _REF.finditer(text)]


def source_violations(src: str):
    """PoC 原始碼的禁止項：import 白名單、寫入／執行／網路／狀態持久化機制、JS 字串。"""
    out = []
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            full = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                out.append("相對 import")
            full = [node.module or ""]
        else:
            full = []
        out += [f"不允許的 streamlit 子模組：{f}" for f in full if f.startswith("streamlit.")]
        mods = [f.split(".")[0] for f in full]
        for m in mods:
            if m not in _ALLOWED_IMPORTS and not m.startswith(_ALLOWED_LOCAL_PREFIX) and m != "app_poc":
                out.append(f"不在白名單的 import：{m}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_NAMES:
            out.append(f"禁用呼叫：{node.func.id}()")
        if isinstance(node, ast.Attribute) and node.attr in _FORBIDDEN_ATTRS:
            out.append(f"禁用屬性：.{node.attr}")
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            low = node.value.lower()
            out += [f"禁用字串：{s}" for s in _FORBIDDEN_STRINGS if s in low]
    return out


def poc_py_files():
    return sorted(p for p in _POC.rglob("*.py") if "__pycache__" not in p.parts)


# ───────────────────────── 真實檔案 ─────────────────────────

def test_poc_files_exist():
    names = {p.name for p in poc_py_files()}
    assert {"app_poc.py", "poc_page.py", "poc_palettes.py", "poc_theme_css.py", "poc_chart_svg.py", "poc_fixtures.py"} <= names


def test_no_production_path_references_the_poc():
    hits = scan_poc_references(_ROOT)
    assert not hits, "正式路徑引用了 PoC 目錄：\n" + "\n".join(hits)


def test_poc_sources_have_no_forbidden_mechanisms():
    bad = {p.name: source_violations(p.read_text(encoding="utf-8")) for p in poc_py_files()}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, f"PoC 出現禁用機制：{bad}"


def test_poc_has_no_write_surface_and_never_names_ui_v3_in_code():
    """沒有寫入面 ⇒ 不可能寫到 `ui_v3/**`；並且程式碼（非 docstring）不 import／不以字串常數引用 ui_v3。"""
    for p in poc_py_files():
        tree = ast.parse(p.read_text(encoding="utf-8"))
        docstrings = {id(n.body[0].value) for n in ast.walk(tree)
                      if isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef)) and n.body
                      and isinstance(n.body[0], ast.Expr) and isinstance(n.body[0].value, ast.Constant)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and id(n) not in docstrings:
                assert "ui_v3" not in n.value, f"{p.name}: 字串常數引用 ui_v3：{n.value[:60]!r}"
        assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) and "ui_v3" in ast.dump(n) for n in ast.walk(tree)), p.name


def test_poc_dir_layout():
    assert not [d for d in _POC.rglob("*") if d.is_dir() and d.name == "pages"], "PoC 目錄內不得有 pages/ 子目錄"
    assert not (_ROOT / "pages").exists(), "根目錄不得出現 pages/"
    assert not [d for d in (_ROOT / "poc").rglob("pages")]
    assert not (_ROOT / "poc" / "__init__.py").exists() and not (_POC / "__init__.py").exists(), "PoC 不做成可 import 的 package"
    assert not (_TESTS / "poc_dual_theme" / "__init__.py").exists(), "tests/ 沒有 __init__.py（檔名須全域唯一）"
    kinds = {p.suffix for p in _POC.rglob("*") if p.is_file() and "__pycache__" not in p.parts}
    assert kinds <= {".py", ".md"}, f"PoC 目錄只應有 .py／.md：{kinds}"


def test_poc_test_file_names_are_unique_in_tests_tree():
    names = {}
    for p in _TESTS.rglob("*.py"):
        if "__pycache__" in p.parts:
            continue
        names.setdefault(p.name, []).append(p)
    mine = [n for n in names if n.startswith("test_poc_dual_theme_") or n.startswith("poc_dual_theme_")]
    assert mine
    dup = {n: names[n] for n in mine if len(names[n]) > 1}
    assert not dup, dup


def test_tokens_and_config_not_touched_by_dark():
    sys.path.insert(0, str(_POC))
    from poc_palettes import DARK, LIGHT, all_hex
    tokens_src = (_ROOT / "ui_v3" / "design" / "tokens.py").read_text(encoding="utf-8").lower()
    assert not [h for h in (all_hex(DARK) - all_hex(LIGHT)) if h in tokens_src]
    for needle in ('"dark"', "'dark'", "dark_mode", "color.dark"):
        assert needle not in tokens_src, needle
    cfg = (_ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    live = "\n".join(ln for ln in cfg.splitlines() if not ln.lstrip().startswith("#"))
    assert "theme.dark" not in live and 'base = "dark"' not in live, ".streamlit/config.toml 不得被加 dark 區段"


# ───────────────────────── 負控（變異驗證；記憶體／暫存樹內現編，不改任何 production 檔） ─────────────────────────

def test_mutation_reference_scan_detects_production_import(tmp_path):
    for rel, body in (("ui/x.py", "import poc_page\n"), ("app.py", "from poc_palettes import LIGHT\n"), ("ui_v2/y.py", "p = 'poc/dual_theme_isolated/app_poc.py'\n"),
                      (".github/workflows/w.yml", "run: streamlit run poc/dual_theme_isolated/app_poc.py\n"), ("ui_v3/z.py", "import poc_theme_css\n"),
                      ("scripts/s.py", "x = 'app_poc'\n")):
        root = tmp_path / rel.replace("/", "_")
        (root / pathlib.Path(rel).parent).mkdir(parents=True)
        (root / rel).write_text(body, encoding="utf-8")
        assert scan_poc_references(root), f"守衛沒抓到：{rel}"
    clean = tmp_path / "clean"
    (clean / "ui").mkdir(parents=True)
    (clean / "ui" / "ok.py").write_text("import streamlit\nx = 'policy'\n", encoding="utf-8")
    assert scan_poc_references(clean) == []


@pytest.mark.parametrize("src", [
    "import requests\n",
    "from ui_v3.design import tokens\n",
    "import os\n",
    "open('ui_v3/design/tokens.py', 'w')\n",
    "import pathlib\npathlib.Path('x').write_text('y')\n",
    "import streamlit as st\nst.context.theme\n",
    "import streamlit as st\nst.query_params['m'] = 'dark'\n",
    "import streamlit as st\nst.markdown('<script>localStorage.setItem(1,2)</script>', unsafe_allow_html=True)\n",
    "import streamlit as st\nimport streamlit.components.v1 as c\n",
    "exec('1')\n",
    "x = 'javascript:alert(1)'\n",
])
def test_mutation_source_checker_flags_violation(src):
    assert source_violations(src), f"檢查器沒抓到：{src!r}"


def test_mutation_source_checker_accepts_clean_poc_style():
    assert source_violations("import streamlit as st\nimport poc_palettes as pal\nfrom html import escape\nx = escape('<b>')\nst.title('t')\n") == []
