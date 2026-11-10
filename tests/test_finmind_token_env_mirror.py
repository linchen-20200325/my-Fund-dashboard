"""FINMIND_TOKEN 讀取一致性守衛(2026-11-10)。

`ui/views/page_01_macro.py` 只讀 `os.environ`(該頁設計不碰 infra),
故 `app.py::_load_keys` 必須把 st.secrets 的 FINMIND_TOKEN 鏡射到 os.environ。
以 AST 掃 app.py(不 import streamlit;app.py import 有副作用)。
"""
from __future__ import annotations

import ast
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def _mirror_keys() -> set[str]:
    tree = ast.parse((_ROOT / "app.py").read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_load_keys")
    keys: set[str] = set()
    for n in ast.walk(fn):
        if isinstance(n, ast.For) and isinstance(n.iter, ast.Tuple):
            keys |= {e.value for e in n.iter.elts
                     if isinstance(e, ast.Constant) and isinstance(e.value, str)}
    return keys


def test_load_keys_mirrors_finmind_token():
    assert "FINMIND_TOKEN" in _mirror_keys()


def test_existing_mirrored_llm_keys_unchanged():
    assert {"ANTHROPIC_API_KEY", "OPENAI_API_KEY"} <= _mirror_keys()


def test_environ_only_readers_require_mirror():
    """任何以 os.environ.get('FINMIND_TOKEN') 讀取者存在時,鏡射集合必含該鍵(防再脫鉤)。"""
    readers = []
    for p in _ROOT.joinpath("ui").rglob("*.py"):
        src = p.read_text(encoding="utf-8")
        if 'environ.get("FINMIND_TOKEN"' in src:
            readers.append(p.name)
    if readers:
        assert "FINMIND_TOKEN" in _mirror_keys(), readers
