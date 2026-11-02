# -*- coding: utf-8 -*-
"""fake fixtures 守衛（80 第 9 節）：fixtures 必須標示 FAKE、涵蓋 scenario 清單、且不得被正式路徑 import。

- `ui_v3/fixtures/` 每個模組在模組層宣告 `FAKE_FIXTURE = True`（AST 檢查）；
- 所有 fixture 資料的 source 都以 `FAKE` 起頭，不可能被誤認為真實來源；
- 十個 scenario 名稱（80 第 9 節清單）齊備、每個都能建出合法 view model；
- repo 內**除 `tests/`、`ui_v3/fixtures/` 本身外**，沒有任何 `.py` import `ui_v3.fixtures`（含 `ui_v3/app_preview.py`）。
負控在記憶體內餵違規片段。
"""
from __future__ import annotations

import ast
import os

import pytest

import ui_v3_guard_lib as lib
from ui_v3.fixtures import scenarios

_SKIP_DIRS = {".git", "__pycache__", "tests", "node_modules", ".venv", "venv", "data_cache", "cache"}


def fixtures_importers(rel: str, source: str) -> list:
    """一個檔是否 import `ui_v3.fixtures`（含相對 import 與 `from ui_v3 import fixtures`）。"""
    if rel.endswith("/__init__.py"):
        package = ".".join(rel[: -len("/__init__.py")].split("/"))
    else:
        package = ".".join(rel[:-3].split("/")[:-1])
    mods = lib.imports_of(ast.parse(source), package)
    return [m for m in mods if m == "ui_v3.fixtures" or m.startswith("ui_v3.fixtures.")]


def _repo_python_files():
    for dirpath, dirnames, filenames in os.walk(lib.ROOT):
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            if f.endswith(".py"):
                yield os.path.join(dirpath, f)


def test_every_fixture_module_declares_fake_marker_at_module_level():
    files = sorted((lib.UI_V3 / "fixtures").glob("*.py"))
    assert files
    for p in files:
        tree = ast.parse(lib.read(p))
        marked = any(
            isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "FAKE_FIXTURE" for t in n.targets)
            and isinstance(n.value, ast.Constant) and n.value.value is True
            for n in tree.body
        )
        assert marked, f"{lib.rel_of(p)} 缺 `FAKE_FIXTURE = True`"
        assert "FAKE" in (ast.get_docstring(tree) or ""), f"{lib.rel_of(p)} docstring 必須標示 FAKE"


def test_scenarios_cover_the_80_section9_list():
    assert set(scenarios.REQUIRED_SCENARIO_NAMES) <= set(scenarios.SCENARIOS)
    assert len(scenarios.REQUIRED_SCENARIO_NAMES) == 10
    assert all(isinstance(v, tuple) and v for v in scenarios.SCENARIOS.values())


def _walk(obj):
    import dataclasses
    yield obj
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        for f in dataclasses.fields(obj):
            yield from _walk(getattr(obj, f.name))
    elif isinstance(obj, tuple):
        for x in obj:
            yield from _walk(x)


def test_all_fixture_data_is_visibly_fake_and_never_rule_ref_or_action():
    from ui_v3.viewmodels import ActionSlot, EvidenceItem, FactMeta
    n_meta = 0
    for name, comps in scenarios.SCENARIOS.items():
        for comp in comps:
            for node in _walk(comp):
                if isinstance(node, FactMeta):
                    n_meta += 1
                    if node.source is not None:
                        assert node.source.startswith("FAKE"), (name, node.source)
                if isinstance(node, EvidenceItem):
                    assert node.rule_ref is None  # 不得自造 Rule ID
                assert not isinstance(node, ActionSlot) or not node.visible or node.state == "無法判定"
    assert n_meta > 0


def test_scenarios_are_deterministic():
    assert scenarios.build_scenarios() == scenarios.build_scenarios()


def test_scenario_missing_cases_never_carry_numbers():
    from ui_v3.viewmodels import MISSING_TEXT, MetricCard
    for comps in scenarios.SCENARIOS.values():
        for comp in comps:
            if isinstance(comp, MetricCard) and comp.facts.value is None:
                assert comp.display_value == MISSING_TEXT


def test_no_production_module_imports_fixtures():
    hits = []
    n = 0
    for path in _repo_python_files():
        rel = os.path.relpath(path, lib.ROOT).replace(os.sep, "/")
        if rel.startswith("ui_v3/fixtures/"):
            continue
        n += 1
        try:
            hits += [f"{rel}: {m}" for m in fixtures_importers(rel, lib.read(__import__("pathlib").Path(path)))]
        except SyntaxError:  # 非本批範圍的壞檔不應讓本守衛誤紅；母體數在下方另釘
            continue
    assert n > 100, "掃描母體異常偏小（守衛失效）"
    assert not hits, "正式路徑 import 了 fake fixtures：\n" + "\n".join(hits)


@pytest.mark.parametrize("rel,source", [
    ("ui_v3/app_preview.py", "from ui_v3.fixtures.scenarios import SCENARIOS"),
    ("ui_v3/pages/x.py", "from ui_v3.fixtures import scenarios"),
    ("ui_v3/pages/x.py", "from ui_v3 import fixtures"),
    ("ui_v3/pages/x.py", "from ..fixtures import scenarios"),
    ("ui_v3/shell/x.py", "import ui_v3.fixtures.scenarios"),
    ("services/x.py", "from ui_v3.fixtures import FAKE_FIXTURE"),
])
def test_negative_control_fixture_import_is_detected(rel, source):
    assert fixtures_importers(rel, source), (rel, source)


def test_negative_control_unrelated_import_not_flagged():
    assert fixtures_importers("ui_v3/pages/x.py", "from ui_v3.viewmodels import MetricCard") == []
