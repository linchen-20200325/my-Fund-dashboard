"""tests/test_schema_gate_inventory.py — A1 Phase D CI gate inventory(v19.165)

CLAUDE.md §3.1 / SPEC §18 — 守 schema test 檔案 vs CI gate 一致性。
新增 schema test 檔案時必須同步加入 .github/workflows/pr-check.yml schema-gate
job,否則 PR 不被 CI 覆蓋(silent test 漂移)。

本檔守:
1. 所有 tests/test_schemas_*.py 必須出現在 pr-check.yml schema-gate job
2. 反之亦然 — workflow 提到的檔案必須真實存在
"""
from __future__ import annotations

import re
from pathlib import Path

PROJ_ROOT = Path(__file__).parent.parent
WORKFLOW = PROJ_ROOT / ".github" / "workflows" / "pr-check.yml"
TESTS_DIR = PROJ_ROOT / "tests"


def _discover_schema_test_files() -> set[str]:
    """掃描 tests/ 找所有 test_schemas_*.py。"""
    return {
        p.name
        for p in TESTS_DIR.glob("test_schemas_*.py")
    }


def _parse_workflow_schema_files() -> set[str]:
    """從 pr-check.yml 找 schema-gate job 引用的 test 檔名。"""
    text = WORKFLOW.read_text(encoding="utf-8")
    # 抓 tests/test_schemas_*.py 出現的所有檔名
    return set(re.findall(r"tests/(test_schemas_[a-z0-9_]+\.py)", text))


def test_all_schema_tests_in_ci_gate():
    """新增 tests/test_schemas_*.py → 必須同步加 pr-check.yml schema-gate job。"""
    discovered = _discover_schema_test_files()
    in_ci = _parse_workflow_schema_files()
    missing = discovered - in_ci
    assert not missing, (
        f"A1 Phase D CI gate 漂移:以下 schema test 檔在 tests/ 但未加入 pr-check.yml:\n  "
        + "\n  ".join(sorted(missing))
        + "\n→ 編輯 .github/workflows/pr-check.yml schema-gate job 加入這些檔案。"
    )


def test_ci_gate_files_actually_exist():
    """pr-check.yml schema-gate job 引用的 test 檔案必須真實存在(防 typo)。"""
    in_ci = _parse_workflow_schema_files()
    stale = {f for f in in_ci if not (TESTS_DIR / f).exists()}
    assert not stale, (
        f"pr-check.yml schema-gate 引用的檔案不存在(typo / 已刪):\n  "
        + "\n  ".join(sorted(stale))
    )


def test_at_least_5_schema_tests():
    """sanity:Phase A/B/B2/B3/C 至少有 5 個 schema test 檔。"""
    discovered = _discover_schema_test_files()
    assert len(discovered) >= 5, (
        f"預期至少 5 個 schema test 檔(Phase A/B/B2/B3/C),實際 {len(discovered)}: "
        f"{sorted(discovered)}"
    )
