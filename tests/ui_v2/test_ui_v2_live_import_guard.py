# -*- coding: utf-8 -*-
"""ui_v2 正式入口的 import 隔離守衛（fast lane；純 AST，不需要 streamlit、pandas）。

依據 docs/v2/49_data_integration_plan.md §3.5「改法」：
- 掃描母體取 `ui_v2/` 底下**全部** `.py`（含各頁子目錄與全部 `app_*.py`），不用寫死的清單 ——
  新增檔自動納入射程。
- (1) 只有 `ui_v2/app_<頁>_live.py` 可以 import 本頁的 `source`；
- (2) 只有 `ui_v2/<頁>/source.py` 可以 import `services.v2_tables`（逐模組列名，不開整個 `services`）；
- (3) `app_<頁>_live.py` 與 `source.py` 不得 import `fixtures`；
- (4) 網路套件在 `ui_v2` 內一律不准出現；
- (5) 舊樹模組（`ui`／`services`／`repositories`／`shared`／`infra`／`fund_fetcher`）在 `ui_v2`
      內一律不准出現，唯一的例外是 (2)。
- (6) `ui_v2` 內任何檔都不得 import `ui_v2.app_*`（進入點不是模組，被 import 就會執行整頁）；
- (7) 動態 import 一律不准：`importlib`、`__import__(...)`、`sys.modules` —— 這三種寫法能繞過
      上面每一條靜態規則（2026-09-26 稽核建議）。
- 兩個新檔（`source.py`、`app_<頁>_live.py`）另走 fail-closed 逐檔白名單：不在白名單就紅。

本檔不改任何既有 ui_v2 測試；既有守衛（各頁 `test_*_logic.py`、`test_*_page.py`）照舊。
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_UI_V2 = _ROOT / "ui_v2"

_PAGES = ("mkt", "hld", "exp", "alo", "set")
_OLD_ROOTS = {"ui", "services", "repositories", "shared", "infra", "fund_fetcher"}
_NET_ROOTS = {
    "requests", "httpx", "urllib", "urllib3", "http", "aiohttp", "websocket", "websockets",
    "yfinance", "gspread", "feedparser", "socket", "ssl", "subprocess", "ftplib", "smtplib",
    "pycurl", "grpc",
}

# 兩個新檔的逐檔白名單（fail-closed）。鍵是相對 repo 根的路徑。
_FILE_ALLOWLIST = {
    "ui_v2/mkt/source.py": {
        "__future__", "os", "streamlit",
        "services.v2_tables.market_indicator", "services.v2_tables.masking",
    },
    "ui_v2/app_mkt_live.py": {
        "__future__", "pathlib", "sys", "streamlit", "ui_v2.mkt.page", "ui_v2.mkt.source",
    },
}


def _module_of(path: pathlib.Path) -> str:
    parts = list(path.relative_to(_ROOT).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _package_of(path: pathlib.Path) -> str:
    module = _module_of(path)
    return module if path.name == "__init__.py" else module.rsplit(".", 1)[0]


def imports_of(tree: ast.AST, package: str) -> list[str]:
    """回傳一棵 AST 裡全部 import 的**絕對**模組名（含 `from X import Y` 的 `X.Y` 兩種讀法）。

    `from . import source` 在 `ui_v2.mkt` 裡換算成 `ui_v2.mkt.source`；
    `from ui_v2.mkt import source` 同時回 `ui_v2.mkt` 與 `ui_v2.mkt.source`。
    函式內的巢狀 import 一併掃（`ast.walk`）。
    """
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            if node.module:
                out.append(prefix)
            for alias in node.names:
                if alias.name != "*":
                    out.append(f"{prefix}.{alias.name}")
    return out


# 經由字串或名稱解析取得模組的屬性名（getattr 第二個引數是這些字串時一律擋）。
_DYNAMIC_ATTRS = {"modules", "__import__", "import_module", "resolve_name", "run_module", "run_path"}
# 能執行任意字串或檔案、進而繞過 import 掃描的內建函式。
_DYNAMIC_CALLS = {"exec", "eval", "compile", "__import__"}


def dynamic_import_uses(tree: ast.AST) -> list[str]:
    """動態 import 的各種寫法（2026-09-26 兩輪稽核）。

    擋：`__import__(...)`（含 `builtins.__import__`、`from builtins import __import__`）；
    `sys.modules`（含 `import sys as s; s.modules`、`from sys import modules`）；
    `getattr(任何物件, "modules" / "__import__" / ...)`；`exec(...)`、`eval(...)`、`compile(...)`。
    `importlib`、`runpy`、`pkgutil` 三個模組本身在 `violations_for` 以 import 擋。
    ⚠️ 只擋上列寫法；`sys.path.insert`、一般 `getattr(obj, "text")` 不擋（負控釘住）。
    """
    sys_aliases = {"sys"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "sys":
                    sys_aliases.add(alias.asname or "sys")
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id == "__import__":
            out.append("__import__")
        elif isinstance(node, ast.Attribute) and node.attr == "__import__":
            out.append("builtins.__import__")
        elif isinstance(node, ast.Attribute) and node.attr == "modules" \
                and isinstance(node.value, ast.Name) and node.value.id in sys_aliases:
            out.append(f"{node.value.id}.modules")
        elif isinstance(node, ast.ImportFrom) and node.module == "sys" \
                and any(a.name == "modules" for a in node.names):
            out.append("from sys import modules")
        elif isinstance(node, ast.ImportFrom) and node.module == "builtins" \
                and any(a.name in _DYNAMIC_CALLS for a in node.names):
            out.append("from builtins import " + ",".join(a.name for a in node.names))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in _DYNAMIC_CALLS:
                out.append(f"{node.func.id}(...)")
            elif node.func.id == "getattr" and len(node.args) >= 2 \
                    and isinstance(node.args[1], ast.Constant) \
                    and node.args[1].value in _DYNAMIC_ATTRS:
                out.append(f"getattr(..., {node.args[1].value!r})")
    return out


def _population() -> list[pathlib.Path]:
    return sorted(p for p in _UI_V2.rglob("*.py") if "__pycache__" not in p.parts)


def violations_for(rel: str, imported: list[str]) -> list[str]:
    """單一檔的違規清單（空清單＝合規）。rel 是相對 repo 根、以 `/` 分隔的路徑。"""
    bad = []
    name = rel.rsplit("/", 1)[-1]
    parts_rel = rel.split("/")
    is_live_app = len(parts_rel) == 2 and name.startswith("app_") and name.endswith("_live.py")
    live_page = name[len("app_"):-len("_live.py")] if is_live_app else None
    is_source = len(parts_rel) == 3 and name == "source.py"
    source_page = parts_rel[1] if is_source else None

    imported = [m for m in imported if not m.startswith("__future__.")]  # 編譯器指示，不是模組
    for module in imported:
        parts = module.split(".")
        root = parts[0]
        if root in _NET_ROOTS:
            bad.append(f"網路套件 {module}")
        if len(parts) >= 3 and parts[0] == "ui_v2" and parts[2] == "source":
            if not (is_live_app and parts[1] == live_page):
                bad.append(f"只有 app_{parts[1]}_live.py 可以 import {module}")
        if module == "services" or module.startswith("services."):
            if module in ("services", "services.v2_tables"):
                # `from services import v2_tables` / `from services.v2_tables import X` 的前綴那一筆
                if not is_source:
                    bad.append(f"只有 source.py 可以 import {module}")
            elif module.startswith("services.v2_tables."):
                if not is_source:
                    bad.append(f"只有 source.py 可以 import {module}")
            else:
                bad.append(f"舊樹模組 {module}（ui_v2 只准經 source.py 碰 services.v2_tables）")
        elif root in _OLD_ROOTS:
            bad.append(f"舊樹模組 {module}")
        if (is_live_app or is_source) and len(parts) >= 3 and parts[0] == "ui_v2" \
                and parts[2] == "fixtures":
            bad.append(f"正式路徑不得 import {module}")
        if len(parts) >= 2 and parts[0] == "ui_v2" and parts[1].startswith("app_"):
            bad.append(f"不得 import 進入點 {module}")
        if root in ("importlib", "runpy", "pkgutil"):
            bad.append(f"動態 import：{module}")
    if is_source and source_page and any(
            m == "services" for m in imported):
        bad.append("source.py 不得 import 整個 services")

    allow = _FILE_ALLOWLIST.get(rel)
    if allow is not None:
        for module in imported:
            # `from X import Y` 產生的 `X` 前綴那一筆：只要它的某個 `X.Y` 在白名單上就放行
            if module in allow:
                continue
            if any(a.startswith(module + ".") for a in allow):
                continue
            bad.append(f"{module} 不在 {rel} 的逐檔白名單")
    elif is_live_app or is_source:
        bad.append(f"{rel} 是正式路徑檔，卻沒有登記逐檔白名單（fail-closed）")
    return bad


# ═══════════════════════ 守衛本體 ═══════════════════════


def test_母體不是空的_而且涵蓋每一頁與兩個新檔():
    files = _population()
    rels = {p.relative_to(_ROOT).as_posix() for p in files}
    assert len(files) >= 31, len(files)  # 五頁 × 六檔 ＋ ui_v2/__init__.py（量測日 2026-09-26）
    for page in _PAGES:
        assert f"ui_v2/{page}/page.py" in rels, page
        assert f"ui_v2/app_{page}.py" in rels, page
    assert "ui_v2/mkt/source.py" in rels
    assert "ui_v2/app_mkt_live.py" in rels
    total = sum(len(imports_of(ast.parse(p.read_text(encoding="utf-8")), _package_of(p)))
                for p in files)
    assert total >= 60, total  # AST 走訪真的看到東西了


def test_ui_v2全部檔案_import都合規():
    problems = {}
    for path in _population():
        rel = path.relative_to(_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"))
        found = violations_for(rel, imports_of(tree, _package_of(path)))
        found += [f"動態 import：{u}" for u in dynamic_import_uses(tree)]
        if found:
            problems[rel] = found
    assert problems == {}


def test_白名單登記的檔都真的存在():
    for rel in _FILE_ALLOWLIST:
        assert (_ROOT / rel).is_file(), rel


def test_正式入口確實import了source與page_而page沒有import_source():
    live = _ROOT / "ui_v2" / "app_mkt_live.py"
    got = imports_of(ast.parse(live.read_text(encoding="utf-8")), "ui_v2")
    assert "ui_v2.mkt.source" in got and "ui_v2.mkt.page" in got
    page = _ROOT / "ui_v2" / "mkt" / "page.py"
    got = imports_of(ast.parse(page.read_text(encoding="utf-8")), "ui_v2.mkt")
    assert "ui_v2.mkt.source" not in got
    src = _ROOT / "ui_v2" / "mkt" / "source.py"
    got = imports_of(ast.parse(src.read_text(encoding="utf-8")), "ui_v2.mkt")
    assert "services.v2_tables.market_indicator" in got


# ═══════════════════════ 正控：守衛真的抓得到 ═══════════════════════


def _check(rel: str, code: str) -> list[str]:
    package = ".".join(rel.split("/")[:-1])
    tree = ast.parse(code)
    return violations_for(rel, imports_of(tree, package)) + dynamic_import_uses(tree)


@pytest.mark.parametrize("rel, code", [
    ("ui_v2/mkt/page.py", "from . import source"),                      # page 不得 import source
    ("ui_v2/mkt/page.py", "from ui_v2.mkt import source"),
    ("ui_v2/mkt/logic.py", "import ui_v2.mkt.source"),
    ("ui_v2/app_mkt.py", "from ui_v2.mkt import source"),               # 示範入口不得
    ("ui_v2/app_hld_live.py", "from ui_v2.mkt import source"),          # 別頁的正式入口不得
    ("ui_v2/mkt/page.py", "from services.v2_tables import market_indicator"),
    ("ui_v2/app_mkt_live.py", "from services.v2_tables import market_indicator"),
    ("ui_v2/mkt/source.py", "from services import fund_service"),       # 只開 v2_tables
    ("ui_v2/mkt/source.py", "import services"),
    ("ui_v2/mkt/source.py", "from . import fixtures"),                  # 正式路徑不得碰 fixtures
    ("ui_v2/app_mkt_live.py", "from ui_v2.mkt import fixtures"),
    ("ui_v2/mkt/source.py", "import requests"),                         # 網路套件
    ("ui_v2/mkt/logic.py", "def f():\n    import urllib.request"),      # 巢狀 import
    ("ui_v2/set/page.py", "from http import client"),
    ("ui_v2/alo/fixtures.py", "import yfinance as yf"),
    ("ui_v2/mkt/source.py", "from repositories.macro.yf import fetch_yf_close"),  # 跳過 L2
    ("ui_v2/hld/logic.py", "from shared.ttls import TTL_5MIN"),
    ("ui_v2/mkt/source.py", "import json"),                             # 逐檔白名單外
    ("ui_v2/app_mkt_live.py", "import os"),
    ("ui_v2/exp/source.py", "from __future__ import annotations"),      # 新 source 沒登記白名單
    ("ui_v2/mkt/page.py", "from ui_v2 import app_mkt_live"),            # (6) import 進入點
    ("ui_v2/mkt/logic.py", "import ui_v2.app_mkt"),
    ("ui_v2/app_mkt_live.py", "from ui_v2.app_mkt import page"),
    ("ui_v2/mkt/page.py", "import importlib"),                          # (7) importlib
    ("ui_v2/mkt/page.py", "from importlib import import_module"),
    ("ui_v2/mkt/logic.py", "def f():\n    import importlib.util"),
    ("ui_v2/mkt/page.py", "m = __import__('ui_v2.mkt.source')"),        # (7) __import__
    ("ui_v2/mkt/page.py", "import builtins\nm = builtins.__import__('x')"),
    ("ui_v2/mkt/page.py", "import sys\nm = sys.modules['ui_v2.mkt.source']"),  # (7) sys.modules
    ("ui_v2/mkt/page.py", "from sys import modules"),
    # 2026-09-26 第二輪稽核登記 6
    ("ui_v2/mkt/page.py", "import sys as s\nm = s.modules"),
    ("ui_v2/mkt/logic.py", "import os, sys as _s\nx = _s.modules.get('a')"),
    ("ui_v2/mkt/page.py", "import sys\nm = getattr(sys, 'modules')"),
    ("ui_v2/mkt/page.py", "import builtins\nf = getattr(builtins, '__import__')"),
    ("ui_v2/mkt/page.py", "from builtins import __import__"),
    ("ui_v2/mkt/page.py", "from builtins import __import__ as imp\nimp('x')"),
    ("ui_v2/mkt/page.py", "exec('import requests')"),
    ("ui_v2/mkt/logic.py", "def f():\n    exec(compile('x=1', 'f', 'exec'))"),
    ("ui_v2/mkt/page.py", "eval('__builtins__')"),
    ("ui_v2/mkt/page.py", "import runpy"),
    ("ui_v2/mkt/page.py", "from runpy import run_module"),
    ("ui_v2/mkt/page.py", "import pkgutil\nm = pkgutil.resolve_name('ui_v2.mkt.source')"),
    ("ui_v2/mkt/page.py", "from pkgutil import resolve_name"),
])
def test_正控_每一種違規都被抓到(rel, code):
    assert _check(rel, code), (rel, code)


@pytest.mark.parametrize("rel, code", [
    ("ui_v2/app_mkt_live.py", "from ui_v2.mkt import page, source"),
    ("ui_v2/mkt/source.py", "from services.v2_tables import market_indicator"),
    ("ui_v2/mkt/page.py", "from . import fixtures, logic, theme"),
    ("ui_v2/app_mkt.py", "from ui_v2.mkt import page"),
    ("ui_v2/app_mkt.py", "import sys\nsys.path.insert(0, 'x')"),     # sys 本身可用，只擋 modules
    ("ui_v2/app_mkt.py", "import sys as s\ns.path.insert(0, 'x')"),     # 別名的 path 同樣可用
    ("ui_v2/mkt/page.py", "x = getattr(obj, 'text', None)"),            # 一般 getattr 不擋
    ("ui_v2/mkt/page.py", "modules = {}\nx = modules.get('a')"),        # 叫 modules 的一般變數不擋
    ("ui_v2/mkt/page.py", "class A:\n    modules = 1\nA.modules"),     # 非 sys 的 .modules 不擋
    ("ui_v2/mkt/source.py", "import os\nimport streamlit as st\nfrom services.v2_tables import masking"),
])
def test_負控_合規寫法不誤報(rel, code):
    assert _check(rel, code) == [], (rel, code)
