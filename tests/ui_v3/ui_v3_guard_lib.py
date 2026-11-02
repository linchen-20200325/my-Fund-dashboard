# -*- coding: utf-8 -*-
"""ui_v3 守衛共用的純 AST 輔助（fast lane；不需要 streamlit、pandas，也不依賴 conftest fixture）。

設計：
- 所有判斷函式都吃「原始碼字串＋相對路徑」，所以負控（mutation control）一律在記憶體內餵違規片段，
  **不寫檔、不改 repo 檔案**。
- 掃描母體取 `ui_v3/` 底下**全部** `.py`（不用寫死清單，新增檔自動納入）；未知層目錄＝違規（fail-closed）。
- ⚠️ **仍未涵蓋的繞法（誠實揭露，AST 靜態守衛的結構性極限）**：以字串組出的名稱再經 `getattr(obj, name)` 取用
  （第二引數非字面常數）、經 `type()`／`object.__subclasses__()`／`__dict__` 取得物件、alias 鏈超過一層的
  `os`／`shutil`、第三方套件內部的副作用。守衛 fail-closed 擋掉了能取得 import 能力的常見入口
  （`builtins`、`__builtins__`、`globals()`／`locals()`／`vars()`、importlib、`__import__`、`sys.modules`、exec／eval），
  但**不宣稱**「ui_v3 不可能有副作用」；獨立稽核與日後 review 仍是必要的第二道。
- 只用標準函式庫；本檔被同目錄測試以裸名 import（tests/ 沒有 `__init__.py`），故檔名取唯一的 `ui_v3_guard_lib`。
"""
from __future__ import annotations

import ast
import pathlib
import sys
from typing import Iterable, List

ROOT = pathlib.Path(__file__).resolve().parents[2]
UI_V3 = ROOT / "ui_v3"
if str(ROOT) not in sys.path:  # 本機以 `--noconftest` 跑；pytest 不會自動把 repo 根放進 sys.path
    sys.path.insert(0, str(ROOT))

OLD_ROOTS = {"ui", "services", "repositories", "shared", "infra", "fund_fetcher", "app"}
NET_ROOTS = {
    "requests", "httpx", "urllib", "urllib3", "http", "aiohttp", "websocket", "websockets",
    "yfinance", "gspread", "feedparser", "socket", "ssl", "subprocess", "ftplib", "smtplib",
    "pycurl", "grpc",
    # 稽核補強：標準函式庫裡其餘會連網、起外部程序或寫持久層的模組（純 view model／頁不需要）
    "asyncio", "imaplib", "poplib", "nntplib", "xmlrpc", "telnetlib", "sqlite3", "socketserver",
    "webbrowser", "shelve", "dbm", "multiprocessing", "ctypes", "pty", "shutil",
}
# `builtins`／`__builtins__`／globals() 這類能取得 `__import__` 的後門：純程式碼完全用不到，一律擋。
BACKDOOR_MODULES = {"builtins"}
BACKDOOR_NAMES = {"__builtins__", "__loader__", "__spec__"}
BACKDOOR_CALLS = {"globals", "locals", "vars"}
DYNAMIC_IMPORT_MODULES = {"importlib", "runpy", "pkgutil"}
LOWER_LAYER_PREFIXES = ("services.v2_tables", "services.v2_domain")
# `shared/` 唯一開放的套件（批 2b；80 第 3.3 節 (c) 呈現規則資料表）。只准 `viewmodels/`、`pages/` import，
# 且只准明寫完整路徑（`from shared.ui_semantics import X`／`import shared.ui_semantics.rules`）；
# 裸 `import shared`、`from shared import ui_semantics` 一律擋（後者無法與 `from shared import colors` 在模組名層級區分，fail-closed）。
SHARED_ALLOWED_PACKAGE = "shared.ui_semantics"
SHARED_ALLOWED_LAYERS = frozenset({"viewmodels", "pages"})

# 每層可以 import 的 ui_v3 內部層（fail-closed：不在表內的層目錄一律違規）。
# root ＝ `ui_v3/__init__.py` 與 `ui_v3/app_preview.py`；進入點（app_*）本身不是模組，任何檔都不得 import。
LAYER_DEPS = {
    "viewmodels": {"viewmodels"},
    "fixtures": {"viewmodels", "fixtures"},
    "design": {"design"},
    "shell": {"shell", "design"},
    "pages": {"pages", "shell", "design", "viewmodels"},
    "adapters": {"adapters", "viewmodels"},
    "root": {"shell", "pages", "adapters", "design", "viewmodels"},
}
STREAMLIT_LAYERS = {"pages", "shell", "adapters", "root"}
STDLIB = set(sys.stdlib_module_names) | {"__future__"}


def population() -> List[pathlib.Path]:
    return sorted(p for p in UI_V3.rglob("*.py") if "__pycache__" not in p.parts)


def rel_of(path: pathlib.Path) -> str:
    return path.relative_to(ROOT).as_posix()


def layer_of(rel: str) -> str:
    parts = rel.split("/")
    if parts[0] != "ui_v3":
        raise ValueError(rel)
    return "root" if len(parts) == 2 else parts[1]


def module_of(rel: str) -> str:
    parts = rel[:-3].split("/")
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def package_of(rel: str) -> str:
    module = module_of(rel)
    return module if rel.endswith("/__init__.py") else module.rsplit(".", 1)[0] if "." in module else module


def imports_of(tree: ast.AST, package: str) -> List[str]:
    """全部 import 的絕對模組名（`from X import Y` 回 X 與 X.Y；相對 import 依 package 換算；巢狀 import 一併掃）。"""
    out: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                prefix = ".".join(base + ([node.module] if node.module else []))
            else:
                prefix = node.module or ""
            if prefix:
                out.append(prefix)
            out.extend(f"{prefix}.{a.name}" for a in node.names if a.name != "*")
    return out


_DYNAMIC_CALLS = {"exec", "eval", "compile", "__import__"}
_DYNAMIC_ATTRS = {"modules", "__import__", "import_module", "resolve_name", "run_module", "run_path"}


def dynamic_import_uses(tree: ast.AST) -> List[str]:
    out: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and node.id in BACKDOOR_NAMES:
            out.append(node.id)
        elif isinstance(node, ast.Name) and node.id == "__import__":
            out.append("__import__")
        elif isinstance(node, ast.Attribute) and node.attr in ("__import__", "modules"):
            out.append(f".{node.attr}")
        elif isinstance(node, ast.ImportFrom) and node.module == "sys" and any(a.name == "modules" for a in node.names):
            out.append("from sys import modules")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in BACKDOOR_CALLS:
                out.append(f"{node.func.id}()")
            elif node.func.id in _DYNAMIC_CALLS:
                out.append(f"{node.func.id}(...)")
            elif (node.func.id == "getattr" and len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                  and node.args[1].value in _DYNAMIC_ATTRS):
                out.append(f"getattr(..., {node.args[1].value!r})")
    return out


def import_violations(rel: str, source: str) -> List[str]:
    """單一檔的 import 違規（空 list ＝ 合規）。"""
    layer = layer_of(rel)
    if layer not in LAYER_DEPS:
        return [f"未知的層目錄 {layer!r}（fail-closed；新增層須同步改守衛）"]
    tree = ast.parse(source)
    bad: List[str] = []
    for module in imports_of(tree, package_of(rel)):
        if module.startswith("__future__."):
            continue
        parts = module.split(".")
        root = parts[0]
        if root in NET_ROOTS:
            bad.append(f"網路／外部程序套件 {module}")
        elif root in BACKDOOR_MODULES:
            bad.append(f"builtins 後門 {module}（可取得 __import__）")
        elif root in DYNAMIC_IMPORT_MODULES:
            bad.append(f"動態 import 模組 {module}")
        elif root == "ui_v2":
            bad.append(f"ui_v2 {module}（本批不開任何 reuse 白名單）")
        elif root == "services":
            if layer != "adapters":
                bad.append(f"只有 adapters/ 可以 import {module}")
            elif module != "services" and not module.startswith(LOWER_LAYER_PREFIXES):
                # 裸 `services` 只會來自 `from services import v2_tables` 的前綴那一筆，放行；其餘舊 services 模組一律擋。
                bad.append(f"services 模組 {module} 不在 adapters 的允許清單（只准 {LOWER_LAYER_PREFIXES}）")
        elif root == "shared" and (module == SHARED_ALLOWED_PACKAGE or module.startswith(SHARED_ALLOWED_PACKAGE + ".")):
            if layer not in SHARED_ALLOWED_LAYERS:
                bad.append(f"{layer}/ 不得 import {module}（只准 {sorted(SHARED_ALLOWED_LAYERS)}）")
        elif root in OLD_ROOTS:
            bad.append(f"舊樹模組 {module}（Old UI 與下層一律不准，adapters 亦同；shared 只開 {SHARED_ALLOWED_PACKAGE}）")
        elif root == "streamlit":
            if layer not in STREAMLIT_LAYERS:
                bad.append(f"{layer}/ 不得 import streamlit（{module}）")
        elif root == "ui_v3":
            target = parts[1] if len(parts) > 1 else None
            if target is None:
                continue
            tgt_layer = "root" if target.startswith("app_") or target == "__init__" else target
            if target.startswith("app_"):
                bad.append(f"進入點 {module} 不是模組，任何檔都不得 import")
            elif tgt_layer not in LAYER_DEPS[layer]:
                bad.append(f"{layer}/ 不得 import ui_v3.{target}（{module}）")
        elif root not in STDLIB:
            bad.append(f"第三方套件 {module}（fail-closed；需要時走 Gate 並明列白名單）")
    bad += [f"動態 import／eval 寫法 {u}" for u in dynamic_import_uses(tree)]
    return bad


# ───────────── 唯讀（write surface） ─────────────
KNOWN_WRITE_FUNCTIONS = frozenset({
    "add_or_update", "remove_from_pool", "set_type_override", "set_secid",
    "upsert_policy_row", "delete_policy_row",
    "upsert_fund_in_policy", "delete_fund_in_policy", "delete_policy_worksheet",
    "create_dashboard_sheet", "write_policy_v2", "rename_sheet",
    "append_ledger_row", "append_snapshot", "save_all_ledgers_snapshot", "save_holdings_overview",
    # settings sheet L1／L2 的寫入入口（ui_v2 守衛以 AST 推導；此處列已知名單）
    "save_user_setting", "save_setting_for_page", "open_fetch_log", "close_fetch_log",
    "append_market_indicator",
})
GSPREAD_UNAMBIGUOUS = frozenset({
    "append_rows", "append_row", "update_cell", "update_cells", "batch_update",
    "delete_rows", "add_worksheet", "del_worksheet",
})
GSPREAD_AMBIGUOUS = frozenset({"update", "clear"})
_RECEIVER_HINTS = ("sheet", "ws", "worksheet", "spreadsheet", "gc", "gspread")
HTTP_WRITE_VERBS = frozenset({"post", "put", "patch", "delete"})
_HTTP_RECEIVER_HINTS = ("requests", "httpx", "session", "client", "http", "urllib")
FILE_WRITE_ATTRS = frozenset({"write_text", "write_bytes", "unlink", "touch", "mkdir", "rmdir", "symlink_to",
                              "hardlink_to", "chmod"})
# 以接收者模組分組（接收者以 import alias 還原，一層為限）。
FS_MODULE_ATTRS = {
    "os": frozenset({"remove", "unlink", "rmdir", "removedirs", "rename", "renames", "replace", "mkdir", "makedirs",
                     "truncate", "popen", "system", "write", "chmod", "symlink", "link", "putenv"}),
    "shutil": frozenset({"copy", "copy2", "copyfile", "copyfileobj", "copytree", "copymode", "copystat", "move",
                         "rmtree", "make_archive", "unpack_archive", "chown"}),
}
_WRITE_MODE_CHARS = "wax+"


def _aliases(tree: ast.AST) -> dict:
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out[a.asname or a.name.split(".")[0]] = a.name.split(".")[0]
    return out


def _resolve(aliases: dict, name: str) -> str:
    """接收者名稱 → 模組名（有 import alias 就還原；沒 import 但名稱本身就是 os／shutil 也算，從嚴）。"""
    return aliases.get(name, name if name in FS_MODULE_ATTRS else "")


def _open_mode(node: ast.Call, positional_index: int):
    mode = None
    if len(node.args) > positional_index and isinstance(node.args[positional_index], ast.Constant):
        mode = node.args[positional_index].value
    for kw in node.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return mode


def _receiver_name(node: ast.AST) -> str:
    while isinstance(node, ast.Attribute):
        node = node.value
    if isinstance(node, ast.Call):
        return _receiver_name(node.func)
    return node.id if isinstance(node, ast.Name) else ""


def write_surface_violations(rel: str, source: str) -> List[str]:
    tree = ast.parse(source)
    aliases = _aliases(tree)
    hits: List[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name in KNOWN_WRITE_FUNCTIONS:
                    hits.append(f"{rel}:{node.lineno} import 已知寫入函式 {a.name}")
                if a.name in FS_MODULE_ATTRS.get((node.module or "").split(".")[0], ()):
                    hits.append(f"{rel}:{node.lineno} from {node.module} import {a.name}（檔案系統變更）")
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = f.attr if isinstance(f, ast.Attribute) else getattr(f, "id", None)
        recv = _receiver_name(f.value).lower() if isinstance(f, ast.Attribute) else ""
        if name in KNOWN_WRITE_FUNCTIONS:
            hits.append(f"{rel}:{node.lineno} 呼叫已知寫入函式 {name}")
        elif isinstance(f, ast.Attribute) and (
                name in GSPREAD_UNAMBIGUOUS
                or (name in GSPREAD_AMBIGUOUS and any(h in recv for h in _RECEIVER_HINTS))):
            hits.append(f"{rel}:{node.lineno} gspread 寫入 .{name}(")
        elif isinstance(f, ast.Attribute) and name in HTTP_WRITE_VERBS and any(h in recv for h in _HTTP_RECEIVER_HINTS):
            hits.append(f"{rel}:{node.lineno} HTTP 寫入動詞 .{name}(")
        elif isinstance(f, ast.Attribute) and name in FILE_WRITE_ATTRS:
            hits.append(f"{rel}:{node.lineno} 檔案寫入 .{name}(")
        elif isinstance(f, ast.Attribute) and name in FS_MODULE_ATTRS.get(_resolve(aliases, _receiver_name(f.value)), ()):
            hits.append(f"{rel}:{node.lineno} 檔案系統變更 {_resolve(aliases, _receiver_name(f.value))}.{name}(")
        elif isinstance(f, ast.Attribute) and name == "open":
            # `Path(...).open("w")`／`path.open(mode="w")`：Path.open 的 mode 是第 1 個位置引數
            mode = _open_mode(node, 0)
            if mode is not None and any(c in str(mode) for c in _WRITE_MODE_CHARS):
                hits.append(f"{rel}:{node.lineno} .open({mode!r}) 寫入模式")
        elif isinstance(f, ast.Name) and f.id == "open":
            mode = _open_mode(node, 1)
            if mode is not None and any(c in str(mode) for c in _WRITE_MODE_CHARS):
                hits.append(f"{rel}:{node.lineno} open(..., {mode!r}) 寫入模式")
    return hits


# ───────────── import 零副作用 ─────────────
def module_level_side_effects(source: str) -> List[str]:
    """模組層只准：import、def／class、賦值給單純名稱、docstring、`if __name__ == "__main__":`。"""
    tree = ast.parse(source)
    bad: List[str] = []
    for i, stmt in enumerate(tree.body):
        if isinstance(stmt, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef)):
            continue
        if isinstance(stmt, (ast.Assign, ast.AnnAssign)):
            targets = stmt.targets if isinstance(stmt, ast.Assign) else [stmt.target]
            # 只准賦值給單純名稱（擋 `os.environ[...] = ...`、`obj.attr = ...` 這類改全域狀態的賦值）
            if all(isinstance(n, ast.Name) for t in targets for n in (ast.walk(t) if isinstance(t, ast.Tuple) else [t])
                   if not isinstance(n, (ast.Tuple, ast.Store))):
                continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str) and i == 0:
            continue
        if isinstance(stmt, ast.If) and ast.unparse(stmt.test).replace("'", '"') == '__name__ == "__main__"':
            continue
        bad.append(f"line {stmt.lineno}: {type(stmt).__name__}")
    return bad


def read(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def all_violations(fn, files: Iterable[pathlib.Path] | None = None) -> List[str]:
    out: List[str] = []
    for p in (files if files is not None else population()):
        out += [f"{rel_of(p)}: {v}" if not v.startswith(rel_of(p)) else v for v in fn(rel_of(p), read(p))]
    return out
