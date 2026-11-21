# -*- coding: utf-8 -*-
"""Gate-M M-copy 第一段（客戶 2026-11-21 核准）：`ui_v3/pages/exp_lookup.py` 與 `ui_v3/viewmodels/exp_lookup_wording.py`
離線呈現＋隔離守衛＋變異負控。複本**尚未掛載**；全部離線（假 loader 由既有 `fund_lookup_support` 注入，不 import 真實 L1／L2）。
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

import fund_lookup_support as S
from fund_lookup_support import no_real_network  # noqa: F401 — autouse 網路守衛
import ui_v3_guard_lib as lib
from shared.ui_semantics import rules
from ui_v3.adapters.fund_lookup import lookup_fund, not_queried
from ui_v3.pages import exp_lookup as R
from ui_v3.viewmodels import exp_lookup_wording as W
from ui_v3.viewmodels.fund_lookup import FieldStatus, FieldView, FundLookupView, LookupState, ProfileFields
from ui_v3.viewmodels.preview_wording import PendingWording

ROOT = lib.ROOT
PAGE = ROOT / "ui_v3" / "pages" / "exp_lookup.py"
WORD = ROOT / "ui_v3" / "viewmodels" / "exp_lookup_wording.py"
FILES = (PAGE, WORD)
POISON_TOKENS = ("Traceback", "KeyError", "://", "api_key")


def views():
    c = S.SAMPLE_CODE
    cases = {
        "not_queried": not_queried(),
        "result": lookup_fund(S.CountingLoader(S.profile()), c),
        "result_missing": lookup_fund(S.CountingLoader(S.profile(dividend_policy=S.cell("not_ready"), inception_on=S.cell("not_ready"))), c),
        "failed": lookup_fund(S.CountingLoader(S.failed_profile()), c),
        "cooling": lookup_fund(S.CountingLoader(S.failed_profile(cooling=True)), c),
        "unmatched": lookup_fund(S.CountingLoader(S.unmatched_profile("not_found")), c),
        "rejected": lookup_fund(S.CountingLoader(S.rejected_profile()), c),
        "io_error": lookup_fund(S.CountingLoader(__import__("ui_v3.viewmodels.fund_lookup", fromlist=["x"]).LookupSourceError("x")), c),
        "blocked_empty": lookup_fund(S.sentinel_loader(), "   "),
        "blocked_url": lookup_fund(S.sentinel_loader(), "https://example.invalid/x"),
    }
    return cases


def conflict_view():
    f = ProfileFields(FieldView(FieldStatus.VALUE, "FAKE 範例"), FieldView(FieldStatus.CONFLICT), FieldView(FieldStatus.CONFLICT), FieldView(FieldStatus.MISSING))
    return FundLookupView(LookupState.RESULT, "FAKE-CNFL1", None, f)


# ───────────────────────── 呈現（離線、純函式） ─────────────────────────

@pytest.mark.parametrize("label", list(views()))
def test_every_state_renders_offline_with_a_status_region_and_no_engineering_leak(label):
    html = R.lookup_card_html(views()[label], fake=True)
    assert R.ID_STATUS in html and html.strip()
    for token in POISON_TOKENS:
        assert token not in html, (label, token)
    assert not re.search(r"[a-z]+_[a-z_]+", re.sub(r"<[^>]*>", "", html)), label      # 可見文字無 snake_case


def test_idle_and_isin_note_render_and_conflict_is_shown_as_conflict_not_a_value():
    assert R.idle_html().strip() and R.isin_note_html().strip()
    html = R.lookup_card_html(conflict_view(), fake=True)
    assert "FAKE 範例" in html and html.count('data-field-status="conflict"') == 2


def test_missing_is_explicit_never_zero_and_never_the_formal_missing_text():
    html = R.lookup_card_html(views()["result_missing"], fake=False)
    formal = rules.entry("missing").wording
    assert formal not in html and "◇" not in html
    assert ">0<" not in html and "0%" not in html


def test_failed_and_unmatched_states_do_not_claim_the_fund_does_not_exist():
    for key in ("failed", "cooling", "unmatched", "rejected", "io_error"):
        text = re.sub(r"<[^>]*>", "", R.lookup_card_html(views()[key], fake=False))
        assert "不存在" not in text and "查無" not in text, key


def test_failed_and_unmatched_do_not_render_result_fields():
    for key in ("failed", "unmatched", "rejected", "blocked_empty", "blocked_url"):
        assert R.lookup_card_html(views()[key], fake=False).count("data-field-status") <= 1, key      # 至多只有「輸入代碼」那一列


def test_untrusted_text_is_escaped():
    bad = FundLookupView(LookupState.RESULT, "X", None, ProfileFields(FieldView(FieldStatus.VALUE, "<script>alert(1)</script>"),
                         FieldView(FieldStatus.MISSING), FieldView(FieldStatus.MISSING), FieldView(FieldStatus.MISSING)))
    html = R.lookup_card_html(bad, fake=True)
    assert "<script>" not in html and "&lt;script&gt;" in html
    assert R.safe("<b>") == "&lt;b&gt;"


def test_css_uses_tokens_only_and_keeps_48px_targets_and_focus_ring():
    css = R.CSS      # 色值來自 theme token（執行期解析）；原始碼無色碼字面值由 AST 守衛檢查
    assert "theme.v(" in PAGE.read_text(encoding="utf-8")
    assert "48px" in css and ":focus-visible" in css


def test_the_fake_flag_changes_the_output_so_real_and_fake_are_never_confused():
    v = views()["result"]
    assert R.lookup_card_html(v, fake=True) != R.lookup_card_html(v, fake=False)


def test_rendering_makes_no_network_attempt_and_loader_not_called_for_blocked_inputs(monkeypatch):
    attempts: list = []
    S.install_network_guard(monkeypatch, attempts)
    for v in views().values():
        R.lookup_card_html(v, fake=True)
    assert attempts == []


# ───────────────────────── 字樣 ─────────────────────────

def _approved():
    out = {a.text for a in rules.APPROVED_WORDING.values()} | {a.ruling_text for a in rules.APPROVED_WORDING.values()}
    out |= {e.wording for e in rules.ENTRIES.values() if e.wording and e.wording != rules.PENDING_WORDING}
    return {s for s in out if isinstance(s, str) and s.strip()}


def test_every_new_wording_is_pending_and_never_duplicates_an_approved_wording():
    approved = _approved()
    assert W.FUND_LOOKUP_PENDING
    for key, item in W.FUND_LOOKUP_PENDING.items():
        assert isinstance(item, PendingWording) and item.status == "pending" and item.key == key
        assert key not in rules.APPROVED_WORDING and key not in rules.ENTRIES
        assert item.text not in approved


def test_no_string_literal_in_the_two_files_duplicates_an_approved_wording():
    approved = _approved()
    for path in FILES:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert node.value.strip() not in approved, (path.name, node.value)


def test_unknown_wording_key_is_an_error_not_a_guess():
    with pytest.raises(KeyError):
        W.text("no_such_key")


# ───────────────────────── 隔離守衛（AST） ─────────────────────────

PAGE_ALLOWED = ("ui_v3.design", "ui_v3.viewmodels.fund_lookup", "ui_v3.viewmodels.exp_lookup_wording", "html", "typing", "__future__")
WORD_ALLOWED = ("shared.ui_semantics", "ui_v3.viewmodels.preview_wording", "html", "types", "typing", "__future__")


def _imports_with_scope(tree: ast.AST):
    """依執行作用域走訪：回傳 (節點, 是否在函式／lambda 內)。函式本體在 def 時不執行；
    其餘（模組直下、if／try／except／finally／else／with／for／while／match 區塊、class 本體）都在模組載入時執行。"""
    stack = [(tree, False)]
    while stack:
        node, in_func = stack.pop()
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            yield node, in_func
        inner = in_func or isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda))
        for child in ast.iter_child_nodes(node):
            stack.append((child, inner))


def import_violations(src: str, allowed: tuple, streamlit_ok: bool) -> list:
    out = []
    for node, in_func in _imports_with_scope(ast.parse(src)):
        names = []
        if isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        else:
            base = (node.module or "") if node.level == 0 else "<relative>"
            names = [base + "." + a.name for a in node.names] if base in ("ui_v3.viewmodels", "ui_v3") else [base]
        for m in names:
            if m.split(".")[0] == "streamlit":
                if not streamlit_ok or not in_func:
                    out.append(f"streamlit 不得於此（或不得於模組層）：{m}")
            elif not any(m == a or m.startswith(a + ".") for a in allowed):
                out.append(f"不在白名單：{m}")
    return out


def test_import_allowlists_hold_for_both_files():
    assert import_violations(PAGE.read_text(encoding="utf-8"), PAGE_ALLOWED, True) == []
    assert import_violations(WORD.read_text(encoding="utf-8"), WORD_ALLOWED, False) == []


@pytest.mark.parametrize("src", ["import requests\n", "import os\n", "import socket\n", "import subprocess\n", "import json\n", "import importlib\n",
                                 "from services import fund_search\n", "from repositories.fund import sources\n", "from infra.proxy import fetch_url\n",
                                 "from ui_v3.adapters.fund_lookup import lookup_fund\n", "from ui_v3.shell.registry import IA_PAGES\n",
                                 "from ui_v3.app_preview import main\n", "import gspread\n", "import yfinance\n", "from ui import sidebar\n"])
def test_negative_control_import_checker_turns_red(src):
    assert import_violations(src, PAGE_ALLOWED, True)
    assert import_violations(src, WORD_ALLOWED, False)


def test_negative_control_module_level_streamlit_turns_red():
    assert import_violations("import streamlit as st\n", PAGE_ALLOWED, True)
    assert not import_violations("def f():\n    import streamlit as st\n", PAGE_ALLOWED, True)


@pytest.mark.parametrize("src", [
    "if True:\n    import streamlit as st\n",
    "try:\n    import streamlit as st\nexcept ImportError:\n    st = None\n",
    "try:\n    pass\nexcept ImportError:\n    import streamlit as st\n",
    "try:\n    pass\nfinally:\n    import streamlit as st\n",
    "if False:\n    pass\nelse:\n    from streamlit import write\n",
    "with open_ctx():\n    import streamlit as st\n",
    "for _ in ():\n    import streamlit as st\n",
    "class C:\n    import streamlit as st\n",
    "import sys\nif sys.version_info:\n    if True:\n        import streamlit as st\n",
], ids=["if_true", "try_body", "except_handler", "finally", "else_branch", "with", "for", "class_body", "nested_if"])
def test_negative_control_streamlit_in_module_scope_blocks_turns_red(src):
    """模組載入時就會執行的區塊（if／try／except／finally／else／with／for／class 本體）內的 streamlit import 不是延後 import。"""
    assert any("模組層" in v for v in import_violations(src, PAGE_ALLOWED, True)), src


@pytest.mark.parametrize("src", [
    "def f():\n    import streamlit as st\n",
    "def f():\n    if True:\n        import streamlit as st\n",
    "def f():\n    try:\n        import streamlit as st\n    except ImportError:\n        pass\n",
    "async def f():\n    import streamlit as st\n",
    "class C:\n    def m(self):\n        import streamlit as st\n",
    "if True:\n    def f():\n        import streamlit as st\n",
], ids=["func", "func_if", "func_try", "async_func", "method", "def_inside_if"])
def test_function_scoped_streamlit_import_still_passes(src):
    assert import_violations(src, PAGE_ALLOWED, True) == [], src
    assert import_violations(src, WORD_ALLOWED, False)      # 非 streamlit 檔案：任何位置都不得


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_no_dynamic_import_write_surface_env_or_network_by_ast(path):
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src)
    assert lib.dynamic_import_uses(tree) == []
    assert lib.write_surface_violations(path.relative_to(ROOT).as_posix(), src) == []
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"environ", "getenv", "secrets", "connect", "create_connection", "urlopen", "Popen", "system", "write_text",
                        "set_page_config", "cache_data", "cache_resource", "query_params"}
    calls = {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert not calls & {"open", "exec", "eval", "compile", "__import__", "input"}
    assert not re.search(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b|rgba?\(|hsla?\(", src.replace("&#", ""))


def test_the_copy_is_not_mounted_and_does_not_touch_the_poc_or_shared_entries():
    from ui_v3.shell import registry
    for path in (ROOT / "ui_v3" / "app_preview.py", ROOT / "ui_v3" / "shell" / "registry.py"):
        assert "exp_lookup" not in path.read_text(encoding="utf-8"), path.name
    assert "exp_lookup" not in " ".join(str(getattr(p, "key", p)) for p in registry.IA_PAGES)
    poc = ROOT / "poc" / "fund_lookup_component_preview"
    assert poc.is_dir() and not any(p.name.startswith("exp_lookup") for p in poc.iterdir())


def test_no_production_module_imports_the_copy_yet():
    pat = re.compile(r"exp_lookup(_wording)?\b")
    for base in ("ui", "ui_v2", "ui_v3", "services", "repositories", "infra", "shared"):
        for p in (ROOT / base).rglob("*.py"):
            if p in FILES:
                continue
            assert not pat.search(p.read_text(encoding="utf-8")), p


# ───────────────────────── 變異負控（記憶體內；偵測器須抓到，且不是單純崩潰） ─────────────────────────

def _load(src: str):
    ns: dict = {"__name__": "mutant"}
    exec(compile(src, "mutant", "exec"), ns)
    return ns


def _check_renderer(ns) -> None:
    f = ns["lookup_card_html"]
    miss = f(views()["result_missing"], fake=False)
    assert ">0<" not in miss and "◇" not in miss
    assert f(views()["failed"], fake=False).count("data-field-status") <= 1
    assert "不存在" not in re.sub(r"<[^>]*>", "", f(views()["unmatched"], fake=False))
    bad = FundLookupView(LookupState.RESULT, "X", None, ProfileFields(FieldView(FieldStatus.VALUE, "<script>"), FieldView(FieldStatus.MISSING),
                         FieldView(FieldStatus.MISSING), FieldView(FieldStatus.MISSING)))
    assert "<script>" not in f(bad, fake=True)
    assert f(views()["result"], fake=True) != f(views()["result"], fake=False)
    assert "48px" in ns["CSS"] and ":focus-visible" in ns["CSS"]


def test_unmutated_renderer_passes_the_checker():
    _check_renderer(_load(PAGE.read_text(encoding="utf-8")))


@pytest.mark.parametrize("name,old,new", [
    ("no_escape", "escape(str(value), quote=True)", "str(value)"),
    ("drop_48px", "48px", "20px"),
    ("drop_focus_ring", ":focus-visible", ":hover"),
    ("always_fake_tag", "    if fake:\n", "    if True:\n"),
    ("failed_shows_fields", "if view.state is LookupState.RESULT:\n        f = view.fields", "if True:\n        f = view.fields or _MUT_FIELDS"),
])
def test_renderer_mutations_are_caught(name, old, new):
    src = PAGE.read_text(encoding="utf-8")
    assert old in src, f"mutation anchor missing: {name}"          # 錨點消失＝負控失效，必須紅，不得跳過
    mutated = src.replace(old, new)
    ns = _load(mutated)
    ns["_MUT_FIELDS"] = ProfileFields(FieldView(FieldStatus.VALUE, "x"), FieldView(FieldStatus.MISSING), FieldView(FieldStatus.MISSING), FieldView(FieldStatus.MISSING))
    with pytest.raises(AssertionError):
        _check_renderer(ns)


def test_wording_mutation_duplicating_an_approved_wording_is_caught():
    approved = next(iter(sorted(_approved())))
    src = WORD.read_text(encoding="utf-8")
    first = re.search(r'_w\("(\w+)", "([^"]+)"', src)
    assert first, "wording anchor"
    mutated = src.replace(first.group(2), approved, 1)
    ns = _load(mutated)
    with pytest.raises(AssertionError):
        for key, item in ns["FUND_LOOKUP_PENDING"].items():
            assert item.text not in _approved()


def test_import_checker_catches_a_mutant_that_adds_a_forbidden_import():
    mutated = "import requests\n" + PAGE.read_text(encoding="utf-8")
    assert import_violations(mutated, PAGE_ALLOWED, True)
    mutated2 = PAGE.read_text(encoding="utf-8").replace("from html import escape", "import os\nfrom html import escape")
    assert import_violations(mutated2, PAGE_ALLOWED, True)
