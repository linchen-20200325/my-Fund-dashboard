"""2026-10-12：名稱推定核心／衛星的函式已刪除（客戶 2026-10-10 裁示不以基金名稱猜級別）。

本守衛斷言 `is_core_fund` / `assign_asset_role` 不得重新出現在 production 檔
（定義、呼叫、import 皆算；AST 掃描，註解與字串不算；排除 tests/）。
突變：把任一函式加回（或在 production 檔 import／呼叫它）→ 本條紅。
"""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_BANNED = {"is_core_fund", "_is_core_fund", "assign_asset_role"}
_SKIP_DIRS = {"tests", ".git", "venv", ".venv", "node_modules", "__pycache__"}


def _production_py():
    for p in ROOT.rglob("*.py"):
        rel = p.relative_to(ROOT).parts
        if rel[0] in _SKIP_DIRS or any(x.startswith(".") for x in rel[:-1]):
            continue
        yield p


def _hits(tree):
    out = []
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in _BANNED:
            out.append(n.lineno)
        elif isinstance(n, ast.ImportFrom):
            out += [n.lineno for a in n.names if a.name in _BANNED or (a.asname in _BANNED)]
        elif (isinstance(n, ast.Name) and n.id in _BANNED) or (
                isinstance(n, ast.Attribute) and n.attr in _BANNED):
            out.append(n.lineno)
    return out


def test_name_heuristics_absent_from_production():
    bad = {}
    for p in _production_py():
        try:
            t = ast.parse(p.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        h = _hits(t)
        if h:
            bad[str(p.relative_to(ROOT))] = h
    assert not bad, f"名稱推定級別函式不得重新出現：{bad}"


def test_scanner_detects_reintroduction():
    """自檢：掃描器本身抓得到定義／import／呼叫（防守衛空轉）。"""
    for src in ("def is_core_fund(n):\n    return True\n",
                "from x import assign_asset_role as r\n",
                "y = ui.session.is_core_fund('a')\n"):
        assert _hits(ast.parse(src)), src
