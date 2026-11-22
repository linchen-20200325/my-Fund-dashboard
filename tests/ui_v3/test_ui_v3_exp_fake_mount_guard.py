# -*- coding: utf-8 -*-
"""Gate-M 方案 2a（客戶 #7073251388 選方案 B；總管 #7073385776 核可唯一狹窄例外）：fixtures 例外的正控／負控矩陣。

例外的全文：`ui_v3/app_preview.py` 模組層 `def _render_exp` 的**直屬敘述**，以 `import ui_v3.fixtures.exp_lookup_fake [as x]` 單一 alias 載入那一個模組。
其餘（模組層、其他函式、巢狀區塊、`from … import` 寫法、其他 fixtures 模組、其他檔案、第二個重複 import）一律照舊違規。
所有負控都在記憶體內現編，不寫檔、不改 repo 檔案；同一批負控同時餵給三個守衛入口（層級 import 守衛、fixtures 偵測器、Preview 不得有 fake 的守衛邏輯）。
"""
from __future__ import annotations

import ast
import os

import pytest

import fund_lookup_support as S
from fund_lookup_support import no_real_network  # noqa: F401 — autouse 網路守衛
import ui_v3_guard_lib as lib
from test_ui_v3_fixtures_are_fake_guard import _repo_python_files, fixtures_importers

APP_REL = lib.FIXTURE_EXCEPTION_REL
MOD = lib.FIXTURE_EXCEPTION_MODULE
FAKE_REL = "ui_v3/fixtures/exp_lookup_fake.py"


def _flagged(rel: str, source: str) -> bool:
    """任一守衛入口抓到＝True（三個入口邏輯各自獨立：層級 import 守衛、fixtures 偵測器）。"""
    layer_hit = bool(lib.import_violations(rel, source)) if rel.startswith("ui_v3/") else False   # ui_v3 以外的檔不在層級守衛母體
    return layer_hit or bool(fixtures_importers(rel, source))


def _clean(rel: str, source: str) -> bool:
    return not lib.import_violations(rel, source) and not fixtures_importers(rel, source)


# ───────────────────────── 正控（唯一例外必須通過） ─────────────────────────

def test_real_app_preview_has_exactly_one_sanctioned_import_and_is_clean():
    src = (lib.ROOT / APP_REL).read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = lib.sanctioned_fixture_imports(APP_REL, tree)
    assert len(found) == 1
    assert _clean(APP_REL, src)
    # 位置：模組層 `_render_exp` 的直屬敘述，而且是函式內（模組層沒有 import streamlit 或 fixtures）
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == lib.FIXTURE_EXCEPTION_FUNC)
    assert found[0] in fn.body
    assert not any(isinstance(n, (ast.Import, ast.ImportFrom)) and getattr(n, "module", None) != "__future__" for n in tree.body)


@pytest.mark.parametrize("stmt", [f"import {MOD}", f"import {MOD} as fake"])
def test_positive_control_the_exact_sanctioned_statement_passes_only_in_the_sanctioned_place(stmt):
    ok = f"def _render_exp():\n    {stmt}\n"
    assert _clean(APP_REL, ok)
    assert lib.sanctioned_fixture_imports(APP_REL, ast.parse(ok))


def test_the_only_repo_wide_importer_of_any_fixtures_module_is_the_sanctioned_pair():
    """去除例外前的原始偵測（不經 without_sanctioned…）：整個 repo（排除 tests／fixtures 自身）恰好一個 fixtures importer＝app_preview.py。"""
    raw = {}
    for path in _repo_python_files():
        rel = os.path.relpath(path, lib.ROOT).replace(os.sep, "/")
        if rel.startswith("ui_v3/fixtures/"):
            continue
        try:
            tree = ast.parse(lib.read(__import__("pathlib").Path(path)))
        except SyntaxError:
            continue
        pkg = ".".join(rel[:-3].split("/")[:-1])
        mods = [m for m in lib.imports_of(tree, pkg) if m == "ui_v3.fixtures" or m.startswith("ui_v3.fixtures.")]
        if mods:
            raw[rel] = sorted(set(mods))
    assert raw == {APP_REL: [MOD]}, raw


# ───────────────────────── 負控（每一種偏離都必須被抓到） ─────────────────────────

NEGATIVES = [
    ("module_level", APP_REL, f"import {MOD}\n"),
    ("other_function", APP_REL, f"def _render_mkt():\n    import {MOD}\n"),
    ("nested_block_in_render_exp", APP_REL, f"def _render_exp():\n    if True:\n        import {MOD}\n"),
    ("try_block_in_render_exp", APP_REL, f"def _render_exp():\n    try:\n        import {MOD}\n    except ImportError:\n        pass\n"),
    ("from_import_form", APP_REL, "def _render_exp():\n    from ui_v3.fixtures import exp_lookup_fake\n"),
    ("from_module_form", APP_REL, f"def _render_exp():\n    from {MOD} import make_loader\n"),
    ("other_fixtures_module", APP_REL, "def _render_exp():\n    import ui_v3.fixtures.scenarios\n"),
    ("fixtures_package", APP_REL, "def _render_exp():\n    import ui_v3.fixtures\n"),
    ("two_aliases", APP_REL, f"def _render_exp():\n    import {MOD}, ui_v3.fixtures.scenarios\n"),
    ("second_duplicate_import", APP_REL, f"def _render_exp():\n    import {MOD}\n    import {MOD} as again\n"),
    ("async_render_exp", APP_REL, f"async def _render_exp():\n    import {MOD}\n"),
    ("nested_def_render_exp", APP_REL, f"def outer():\n    def _render_exp():\n        import {MOD}\n"),
    ("class_method_render_exp", APP_REL, f"class C:\n    def _render_exp(self):\n        import {MOD}\n"),
    ("other_file_same_function_name", "ui_v3/pages/mkt.py", f"def _render_exp():\n    import {MOD}\n"),
    ("page_importing_fixture", "ui_v3/pages/exp_lookup.py", f"import {MOD}\n"),
    ("adapter_importing_fixture", "ui_v3/adapters/fund_lookup.py", f"def f():\n    import {MOD}\n"),
    ("shell_importing_fixture", "ui_v3/shell/nav.py", f"def f():\n    import {MOD}\n"),
    ("other_package_importing_fixture", "services/x.py", f"def f():\n    import {MOD}\n"),
]


@pytest.mark.parametrize("name,rel,source", NEGATIVES, ids=[n[0] for n in NEGATIVES])
def test_negative_control_every_deviation_from_the_exception_is_still_flagged(name, rel, source):
    assert _flagged(rel, source), name
    # 不只「有人抓到」：fixtures 偵測器（獨立於層級守衛）也必須抓到——兩條路徑各自成立
    assert fixtures_importers(rel, source), name


def test_negative_control_deviation_that_would_slip_through_is_not_in_the_list():
    """守衛自身的反向檢查：最接近例外但不同的寫法都在 NEGATIVES 裡；唯一通過的寫法只有 parametrize 的兩個正控。"""
    exact = {f"import {MOD}", f"import {MOD} as fake"}
    for _name, rel, source in NEGATIVES:
        body = [line.strip() for line in source.splitlines()]
        assert not (rel == APP_REL and body[0] == "def _render_exp():" and len(body) == 2 and body[1] in exact), source


# ───────────────────────── FAKE 模組本身 ─────────────────────────

def test_the_fake_module_itself_obeys_the_fixtures_layer_and_declares_fake():
    src = (lib.ROOT / FAKE_REL).read_text(encoding="utf-8")
    assert lib.import_violations(FAKE_REL, src) == []                       # 只依賴 viewmodels／標準庫；無網路、無舊樹、無 services
    tree = ast.parse(src)
    assert any(isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "FAKE_FIXTURE" for t in n.targets)
               and isinstance(n.value, ast.Constant) and n.value.value is True for n in tree.body)
    assert "FAKE" in (ast.get_docstring(tree) or "")
    assert lib.write_surface_violations(FAKE_REL, src) == [] and lib.dynamic_import_uses(tree) == []


def test_the_fake_module_has_no_network_environment_or_file_surface_by_ast():
    tree = ast.parse((lib.ROOT / FAKE_REL).read_text(encoding="utf-8"))
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
    assert not names & {"environ", "getenv", "secrets", "connect", "create_connection", "urlopen", "Popen", "system", "write_text", "open"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            assert "://" not in node.value and "@" not in node.value, node.value


def test_every_demo_code_and_name_is_visibly_fake_and_the_loader_is_offline_and_shape_correct():
    from ui_v3.fixtures import exp_lookup_fake as fake
    assert fake.FAKE_NAME.startswith("FAKE") and all(code.startswith("FAKE-") for code in fake.DEMO_CODES)
    loader = fake.make_loader()
    for code in fake.DEMO_CODES:
        if code == "FAKE-IOERR":
            continue
        out = loader(code)
        assert set(out) == {"cells", "source_status"} and code in out["cells"] and code in out["source_status"], code
    from ui_v3.viewmodels.fund_lookup import LookupSourceError
    with pytest.raises(LookupSourceError):
        loader("FAKE-IOERR")
    assert loader.calls[-1] == "FAKE-IOERR"
    assert fake.demo_codes_hint().count("FAKE-") == len(fake.DEMO_CODES)


def test_unlisted_codes_are_page_unmatched_never_an_existence_claim():
    from ui_v3.adapters.fund_lookup import lookup_fund
    from ui_v3.fixtures import exp_lookup_fake as fake
    from ui_v3.viewmodels.fund_lookup import LookupState
    view = lookup_fund(fake.make_loader(), "ABC123")
    assert view.state is LookupState.PAGE_UNMATCHED


# ───────────────────────── 變異負控：把例外放寬，矩陣必須有至少一項轉為『沒被抓到』 ─────────────────────────

def _broad(*, any_file=False, any_func=False, module_level=False):
    """放寬版的『例外判定』（變異體）：任意檔／任意函式名／允許模組層。"""
    def sanctioned(rel, tree):
        if not any_file and rel != APP_REL:
            return []
        out = []
        for stmt in getattr(tree, "body", []):
            if module_level and lib.is_sanctioned_fixture_import(stmt):
                out.append(stmt)
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef)) and (any_func or stmt.name == lib.FIXTURE_EXCEPTION_FUNC):
                out.extend(n for n in stmt.body if lib.is_sanctioned_fixture_import(n))
        return out
    return sanctioned


@pytest.mark.parametrize("label,mutant", [
    ("any_function_name", _broad(any_func=True)),
    ("any_file", _broad(any_file=True)),
    ("module_level_allowed", _broad(module_level=True)),
])
def test_mutation_widening_the_exception_makes_the_negative_matrix_go_red(monkeypatch, label, mutant):
    """負控自證：若有人把例外放寬（任何函式名／任何檔／允許模組層），NEGATIVES 至少一項會從『被抓到』變成『沒被抓到』。"""
    baseline = [name for name, rel, src in NEGATIVES if not _flagged(rel, src)]
    assert baseline == []                                         # 未放寬時全部被抓到
    monkeypatch.setattr(lib, "sanctioned_fixture_imports", mutant)
    escaped = [name for name, rel, src in NEGATIVES if not _flagged(rel, src)]
    assert escaped, f"{label}: 放寬例外後矩陣完全沒反應（負控失效）"
