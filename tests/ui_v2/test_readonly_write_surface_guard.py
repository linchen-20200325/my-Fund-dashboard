# -*- coding: utf-8 -*-
"""新 B UI 第一階段唯讀：寫入面守衛（fast，不碰網路）。

1. ui_v2/ 與 services/v2_tables/ 不得 import／呼叫已知寫入函式（pool／保單）。
2. gspread 寫入方法呼叫只允許白名單檔案（AST，不是字串 grep）。
3. `UI_V2_READ_ONLY` 開關：真值 → `read_only` 且 repository 零呼叫；其他 → 現行路徑。

已知寫入函式名單的來源（2026-10-26 讀 repositories 原始碼）：
- repositories/pool_repository.py：add_or_update、remove_from_pool、set_type_override、set_secid
- repositories/policy/v1.py：upsert_policy_row、delete_policy_row
- repositories/policy/v2.py：upsert_fund_in_policy、delete_fund_in_policy、delete_policy_worksheet、
  create_dashboard_sheet、write_policy_v2
（repositories/policy_supplement_repository.py 實測沒有公開寫入函式。）
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCAN_DIRS = ("ui_v2", "services/v2_tables")

KNOWN_WRITE_FUNCTIONS = frozenset({
    "add_or_update", "remove_from_pool", "set_type_override", "set_secid",
    "upsert_policy_row", "delete_policy_row",
    "upsert_fund_in_policy", "delete_fund_in_policy", "delete_policy_worksheet",
    "create_dashboard_sheet", "write_policy_v2",
})
WRITE_MODULES = ("repositories.pool_repository", "repositories.policy",
                 "repositories.policy_supplement_repository")

# 名稱本身只可能是 gspread 寫入者的方法；任何接收者都算。
GSPREAD_WRITE_UNAMBIGUOUS = frozenset({
    "append_rows", "append_row", "update_cell", "update_cells", "batch_update",
    "delete_rows", "add_worksheet", "del_worksheet",
})
# dict.update／cache.clear 同名，只在接收者名稱像 gspread 物件時才算。
GSPREAD_WRITE_AMBIGUOUS = frozenset({"update", "clear"})
_GSPREAD_RECEIVER_HINTS = ("sheet", "ws", "worksheet", "spreadsheet", "gc", "gspread")

# 白名單（repo 相對路徑，posix）。L1 repository 不在掃描目錄內，不用列。
GSPREAD_WRITE_ALLOWLIST = frozenset({"services/v2_tables/settings_store.py"})


def _files():
    out = []
    for d in SCAN_DIRS:
        for p in sorted((ROOT / d).rglob("*.py")):
            if "tests" in p.relative_to(ROOT).parts:
                continue
            out.append(p)
    return out


def _tree(path):
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _receiver_name(node):
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Call):
        return _receiver_name(node.func)
    return node.id if isinstance(node, ast.Name) else ""


def test_scan_sets_are_not_empty():
    names = {p.relative_to(ROOT).as_posix() for p in _files()}
    assert "services/v2_tables/settings_store.py" in names
    assert any(n.startswith("ui_v2/") for n in names)


def test_no_known_write_function_imported_or_called():
    hits = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(WRITE_MODULES):
                for a in node.names:
                    if a.name in KNOWN_WRITE_FUNCTIONS:
                        hits.append(f"{rel}:{node.lineno} from {node.module} import {a.name}")
            elif isinstance(node, ast.Call):
                f = node.func
                name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
                if name in KNOWN_WRITE_FUNCTIONS:
                    hits.append(f"{rel}:{node.lineno} call {name}")
    assert not hits, "新 B UI 第一階段唯讀，出現已知寫入函式：\n" + "\n".join(hits)


def test_gspread_write_calls_only_in_allowlist():
    hits = []
    for path in _files():
        rel = path.relative_to(ROOT).as_posix()
        if rel in GSPREAD_WRITE_ALLOWLIST:
            continue
        for node in ast.walk(_tree(path)):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                attr = node.func.attr
                recv = _receiver_name(node.func.value).lower()
                if attr in GSPREAD_WRITE_UNAMBIGUOUS or (
                        attr in GSPREAD_WRITE_AMBIGUOUS and any(h in recv for h in _GSPREAD_RECEIVER_HINTS)):
                    hits.append(f"{rel}:{node.lineno} .{attr}(")
    assert not hits, "白名單外的 gspread 寫入呼叫：\n" + "\n".join(hits)


def test_detectors_catch_synthetic_violations():
    """負控：掃描器本身要抓得到（用現編程式碼，不落檔）。"""
    tree = ast.parse("from repositories.pool_repository import add_or_update\nws.append_rows(x)\n")
    imp = [n for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)][0]
    assert imp.module.startswith(WRITE_MODULES) and imp.names[0].name in KNOWN_WRITE_FUNCTIONS
    call = [n for n in ast.walk(tree) if isinstance(n, ast.Call)][0]
    assert call.func.attr in GSPREAD_WRITE_UNAMBIGUOUS


# ───────── 開關行為 ─────────
from services.v2_tables import settings_store as ss  # noqa: E402


class _FakeStore:
    """記錄對 L1 `save_user_setting` 的呼叫次數（只替換這一個函式，其餘沿用真 L1 模組）。"""

    def __init__(self):
        self.calls = 0

    def save_user_setting(self, key, value, kind, mask=None):
        self.calls += 1
        return {"key": key}


@pytest.fixture
def fake_store(monkeypatch):
    fake = _FakeStore()
    monkeypatch.setattr(ss.store, "save_user_setting", fake.save_user_setting)
    return fake


def _set_flag(monkeypatch, value):
    monkeypatch.setattr(
        ss, "get_secret",
        lambda key, default=None: value if key == ss.READ_ONLY_SECRET_KEY else default)


@pytest.mark.parametrize("flag", ["1", "true", " TRUE ", "Yes", "on"])
def test_read_only_true_short_circuits(monkeypatch, fake_store, flag):
    _set_flag(monkeypatch, flag)
    assert ss.is_read_only() is True
    out = ss.save_setting_for_page("k", "5", "int", {})
    assert out["status"] == "read_only" and out["key"] == "k" and out["message"]
    assert fake_store.calls == 0


@pytest.mark.parametrize("flag", ["", "0", "false", "maybe", None])
def test_read_only_false_keeps_current_path(monkeypatch, fake_store, flag):
    _set_flag(monkeypatch, flag)
    assert ss.is_read_only() is False
    out = ss.save_setting_for_page("k", "5", "int", {})
    assert out["status"] == "saved"
    assert fake_store.calls == 1
