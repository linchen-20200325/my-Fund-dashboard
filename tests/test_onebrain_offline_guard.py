"""OB-B 離線切片守衛：services/onebrain/ 的離線保證 + FAKE 隔離（孤立性）。

授權依據：`DEC-2026-11-20-01`（客戶本人逐字確認）。本檔把下列「不得」從文件宣稱變成 CI 紅燈：

A. **套件邊界**：`services/onebrain/` 恰為 5 檔、`tests/test_onebrain_*.py` 恰為 4 檔
   （白名單；多一個即超範圍，需重新取得授權才能改本檔）。
B. **離線保證（比 L2 通用白名單更窄）**：套件內只准 import
   `__future__` / `abc` / `dataclasses` / `enum` / `typing` 與絕對 `services.onebrain…` 自引；
   禁相對 import；禁用名稱／屬性（os、sys、socket、http、urllib、requests、httpx、subprocess、
   logging、time、random、uuid、datetime、pathlib、open、eval、exec、環境變數存取、input …）；
   無金鑰樣式字串常數。全部用 AST，不用 grep。
C. **FAKE 隔離**：掃全 repo `*.py`，除 `services/onebrain/` 與 `tests/` 外，任何檔以任何形式
   取得 `services.onebrain` 即紅。涵蓋 `import …`、`from … import …`、
   `from services import onebrain`、`import services` 後的屬性存取、`getattr(services, …)`、
   `importlib.import_module` / `__import__` / `sys.modules[…]` 的字串常數形式、與相對 import
   （依檔案位置解析）。

每一類偵測都有**變異負控**：在測試內以 f-string 動態組出違規原始碼，餵給和 production 掃描
同一個函式，證明「拿掉該偵測邏輯就會轉紅」；同時有反向對照（合規原始碼不誤報）。
負控以字串拼接現編，不寫進文件（`CLAUDE.md` §-2.A 第 8 款）；金鑰樣式負控尤其刻意拆開拼接，
不留可 grep 的完整字面量。

⚠️ 本守衛看不到什麼（誠實列出）：
- 名稱在執行期才決定的動態 import（`import_module(變數)`）— 靜態分析無法解析。
- `from services import *`（取決於 `services/__init__.py` 是否導出；目前該檔只有 docstring）。
- 把 import 函式轉存後再呼叫（`f = importlib.import_module; f(...)`）。
- 非 `.py` 檔（例如 `.ipynb`、經 `exec(open(...).read())` 載入的程式）。
- `services/onebrain/` 與 `tests/` 兩個豁免區內的 import 不受 C 檢查（設計如此）。
- **頂層 `tests/` 整體豁免**（Gate 卡 §3-5-5 字面）：任何頂層測試都可 import `services.onebrain`。
  收緊（例如只准 `tests/test_onebrain_*.py`）比 Gate 卡更嚴，屬客戶／總管決定，本檔不單方收緊。
- 變數別名：`x = services; x.onebrain`（只追蹤 `import services [as y]` 綁定的名稱）；
  區域變數剛好叫 `services` 時屬性偵測只會多報、不會漏報。
- `sys.modules.get("…")`／`sys.modules.setdefault`（本檔只偵測下標 `sys.modules["…"]`）。
- 檔案路徑載入器：`importlib.util.spec_from_file_location`、`runpy.run_path` 等以路徑而非模組名載入。
- `exec`／`eval` 字串內的 import（字串內容不被解析）。
- 排除目錄名（`.git`、`venv`、`env`、`site-packages` 等）對**任何深度**生效；專案內若有同名
  一般目錄會被整棵跳過。`.claude/worktrees` 僅在 repo 根下整棵跳過。
- 非 `.py` 檔：`.ipynb`、`.yml` workflow 內的 `python -c "…"`、shell 腳本等不在掃描範圍。
- 全 repo 掃描每次約數秒；CI 時間成本待觀察。`text`／`input_text` 型別允許空字串（設計如此）。
- 白名單相等斷言只看 `*.py`（套件內多放非 .py 檔不會被抓）。

本檔不依賴 conftest 的任何 fixture：只用 stdlib + pytest。
"""

from __future__ import annotations

import ast
import os
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PKG_DIR = ROOT / "services" / "onebrain"
TESTS_DIR = ROOT / "tests"

TARGET = "services" + "." + "onebrain"  # 動態組合，避免被純字串掃描誤當成引用

EXPECTED_PKG_FILES = frozenset(
    {
        "services/onebrain/__init__.py",
        "services/onebrain/provider_types.py",
        "services/onebrain/provider_interface.py",
        "services/onebrain/fake_provider.py",
        "services/onebrain/evidence_input.py",
    }
)
EXPECTED_TEST_FILES = frozenset(
    {
        "tests/test_onebrain_provider_types.py",
        "tests/test_onebrain_fake_provider.py",
        "tests/test_onebrain_offline_guard.py",
        "tests/test_onebrain_evidence_input.py",
    }
)


def _rel(p: pathlib.Path) -> str:
    return p.relative_to(ROOT).as_posix()


# ═══════════════════════════════════════════════════════════════════════════
# A. 套件邊界（白名單恰為 9 檔）
# ═══════════════════════════════════════════════════════════════════════════


def _pkg_py_files() -> list[pathlib.Path]:
    return sorted(p for p in PKG_DIR.rglob("*.py") if "__pycache__" not in p.parts)


def test_package_contains_exactly_the_five_authorised_files():
    assert {_rel(p) for p in _pkg_py_files()} == EXPECTED_PKG_FILES


def test_onebrain_tests_are_exactly_the_four_authorised_files():
    found = {_rel(p) for p in TESTS_DIR.rglob("test_onebrain_*.py")}
    assert found == EXPECTED_TEST_FILES


def test_package_init_is_docstring_only_no_side_effects():
    tree = ast.parse((PKG_DIR / "__init__.py").read_text(encoding="utf-8"))
    assert len(tree.body) == 1
    stmt = tree.body[0]
    assert isinstance(stmt, ast.Expr)
    assert isinstance(stmt.value, ast.Constant) and isinstance(stmt.value.value, str)


# ═══════════════════════════════════════════════════════════════════════════
# B. 離線保證（AST）
# ═══════════════════════════════════════════════════════════════════════════

PKG_ALLOWED_TOP_LEVEL = frozenset({"__future__", "abc", "dataclasses", "enum", "typing"})

BANNED_NAMES = frozenset(
    {
        # 網路／程序／環境／檔案系統／時鐘／隨機／日誌
        "os", "sys", "socket", "http", "urllib", "requests", "httpx", "subprocess",
        "logging", "time", "random", "uuid", "datetime", "pathlib", "importlib",
        "open", "eval", "exec", "compile", "input", "breakpoint", "__import__",
        "environ", "getenv",
        # 動態屬性操作（可繞過上面的名稱禁令）
        "getattr", "setattr", "delattr", "globals", "locals", "vars",
    }
)
BANNED_ATTRS = frozenset(
    {
        "environ", "getenv", "putenv", "system", "popen", "open", "urlopen",
        "read_text", "write_text", "read_bytes", "write_bytes", "connect",
        "sendall", "getaddrinfo", "create_connection",
    }
)

_SECRET_SHAPES = (
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"xox[abprs]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*KEY-----"),
    re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/=_-]{40,}(?![A-Za-z0-9+/=_-])"),
)


def _is_self_target(name: str) -> bool:
    return name == TARGET or name.startswith(TARGET + ".")


def _pkg_import_ok(name: str) -> bool:
    return name.split(".")[0] in PKG_ALLOWED_TOP_LEVEL or _is_self_target(name)


def scan_package_source(src: str) -> list[str]:
    """回傳違反離線保證的描述清單（空 = 合規）。與 production 掃描共用，變異負控也走這裡。"""
    tree = ast.parse(src)
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if not _pkg_import_ok(alias.name):
                    out.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                out.append(f"relative import (level={node.level}, module={node.module})")
            elif not _pkg_import_ok(node.module or ""):
                out.append(f"from {node.module} import …")
        elif isinstance(node, ast.Name):
            if node.id in BANNED_NAMES:
                out.append(f"name {node.id}")
        elif isinstance(node, ast.Attribute):
            if node.attr in BANNED_ATTRS or node.attr in BANNED_NAMES:
                out.append(f"attribute .{node.attr}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            for pat in _SECRET_SHAPES:
                if pat.search(node.value):
                    out.append("key-shaped string constant")
                    break
    return sorted(set(out))


def _scan_package_stats() -> tuple[dict[str, list[str]], int, int]:
    violations: dict[str, list[str]] = {}
    imports = 0
    names = 0
    for p in _pkg_py_files():
        src = p.read_text(encoding="utf-8")
        tree = ast.parse(src)
        imports += sum(isinstance(n, (ast.Import, ast.ImportFrom)) for n in ast.walk(tree))
        names += sum(isinstance(n, ast.Name) for n in ast.walk(tree))
        v = scan_package_source(src)
        if v:
            violations[_rel(p)] = v
    return violations, imports, names


def test_package_is_offline_and_import_clean():
    violations, _, _ = _scan_package_stats()
    assert violations == {}, violations


def test_package_scan_is_not_vacuous():
    """錨點：掃描真的看到東西了（防規則對空氣生效還天天綠）。"""
    _, imports, names = _scan_package_stats()
    assert imports >= 8, imports
    assert names >= 100, names


@pytest.mark.parametrize(
    "label,src",
    [
        ("import_os", "import " + "os\n"),
        ("import_sys", "import " + "sys\n"),
        ("import_socket", "import " + "socket\n"),
        ("import_requests", "import " + "requests\n"),
        ("import_httpx", "import " + "httpx\n"),
        ("import_urllib_request", "import urllib." + "request\n"),
        ("import_http_client", "import http." + "client\n"),
        ("import_subprocess", "import " + "subprocess\n"),
        ("import_logging", "import " + "logging\n"),
        ("import_time", "import " + "time\n"),
        ("import_random", "import " + "random\n"),
        ("import_uuid", "import " + "uuid\n"),
        ("import_datetime", "import " + "datetime\n"),
        ("import_pathlib", "import " + "pathlib\n"),
        ("import_math", "import " + "math\n"),
        ("import_sdk_like", "import " + "anthropic\n"),
        ("import_other_services", "from services import " + "fund_service\n"),
        ("import_shared", "from shared import " + "ttls\n"),
        ("import_infra", "from infra." + "cache import x\n"),
        ("from_os", "from " + "os import path\n"),
        ("nested_import_in_function", "def f():\n    import " + "os\n"),
        ("relative_import", "from . import " + "provider_types\n"),
        ("relative_import_with_module", "from .provider_types import " + "x\n"),
        ("open_call", "x = " + "open('f')\n"),
        ("eval_call", "x = " + "eval('1')\n"),
        ("exec_call", "" + "exec('1')\n"),
        ("input_call", "x = " + "input()\n"),
        ("dunder_import", "x = __" + "import__('os')\n"),
        ("environ_attr", "def f(m):\n    return m." + "environ\n"),
        ("getenv_attr", "def f(m):\n    return m." + "getenv('K')\n"),
        ("getattr_call", "x = " + "getattr(object, 'a')\n"),
        ("setattr_call", "" + "setattr(object, 'a', 1)\n"),
        ("globals_call", "x = " + "globals()\n"),
        ("path_read_attr", "def f(p):\n    return p." + "read_text()\n"),
        ("connect_attr", "def f(s):\n    s." + "connect(('h', 1))\n"),
        ("secret_sk", "K = '" + "sk-" + "A1b2C3d4E5f6G7h8I9j0" + "'\n"),
        ("secret_google", "K = '" + "AIza" + "Sy" + "A" * 24 + "'\n"),
        ("secret_long_token", "K = '" + "A1" * 24 + "'\n"),
        ("secret_github", "K = '" + "gh" + "p_" + "A1" * 12 + "'\n"),
        ("secret_slack", "K = '" + "xo" + "xb-" + "1234567890" + "abcdef" + "'\n"),
        ("secret_pem", "K = '-----BEGIN " + "PRIVATE KEY-----'\n"),
    ],
)
def test_package_mutants_are_caught(label, src):
    assert scan_package_source(src), f"變異 {label} 沒被離線守衛抓到"


@pytest.mark.parametrize(
    "src",
    [
        "from __future__ import annotations\n",
        "from abc import ABC, abstractmethod\n",
        "from dataclasses import dataclass\nfrom enum import Enum\nfrom typing import Optional\n",
        f"from {TARGET}.provider_types import ProviderRequest\n",
        f"import {TARGET}.provider_types\n",
        f"from {TARGET} import provider_types\n",
        "x = 'FAKE｜離線測試標記，非 AI 分析'\n",
        "def f(timeout_seconds: float, input_text: str) -> str:\n    return input_text\n",
    ],
)
def test_package_clean_sources_are_not_flagged(src):
    assert scan_package_source(src) == []


def test_package_import_roots_are_within_this_files_narrow_whitelist():
    """包內實際 import 的頂層模組 ⊆ 本檔白名單（再加上 `services` 自引）。

    刻意**不**讀 `tests/test_services_purity_contract.py` 的 ALLOWED_IMPORTS：讀它會讓本檔綁死該守衛的
    內部常數名稱（改名即紅），且本批不得修改該守衛。與通用 L2 白名單的相容性，由該守衛本身實跑證明。
    """
    tree_imports: set[str] = set()
    for p in _pkg_py_files():
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8"))):
            if isinstance(n, ast.Import):
                tree_imports.update(a.name.split(".")[0] for a in n.names)
            elif isinstance(n, ast.ImportFrom) and n.module and not n.level:
                tree_imports.add(n.module.split(".")[0])
    assert tree_imports <= PKG_ALLOWED_TOP_LEVEL | {"services"}


# ═══════════════════════════════════════════════════════════════════════════
# C. FAKE 隔離：全 repo 孤立性
# ═══════════════════════════════════════════════════════════════════════════

_DYN_IMPORT_FUNCS = frozenset({"import_module", "__import__", "find_spec"})
_EXCLUDED_DIR_NAMES = frozenset(
    {
        ".git", "__pycache__", "node_modules", "venv", ".venv", "env", ".tox",
        ".mypy_cache", ".pytest_cache", ".ruff_cache", "site-packages",
    }
)


def _dotted(node: ast.AST) -> str | None:
    parts: list[str] = []
    cur = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
        return ".".join(reversed(parts))
    return None


def _const_str(node: ast.AST | None) -> str | None:
    """解出可靜態確定的字串（常數、常數相加、純常數 f-string）；否則 None。"""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left, right = _const_str(node.left), _const_str(node.right)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(node, ast.JoinedStr):
        chunks = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                chunks.append(v.value)
            else:
                return None
        return "".join(chunks)
    return None


def _call_arg(call: ast.Call, index: int, kw: str) -> ast.AST | None:
    if len(call.args) > index:
        return call.args[index]
    for k in call.keywords:
        if k.arg == kw:
            return k.value
    return None


def _resolve_relative(rel_posix: str, level: int, module: str | None) -> str | None:
    """依檔案位置把相對 import 解成絕對模組名；解不出來回 None。"""
    parts = rel_posix[:-3].split("/") if rel_posix.endswith(".py") else rel_posix.split("/")
    package = parts[:-1]  # 檔所在的 package（__init__.py 與一般模組皆同）
    drop = level - 1
    if drop > len(package):
        return None
    base = package[: len(package) - drop] if drop else package
    full = list(base) + (module.split(".") if module else [])
    return ".".join(full) if full else None


def find_onebrain_refs(src: str, rel_posix: str | None = None) -> list[str]:
    """回傳此原始碼取得 `services.onebrain` 的所有形式（空 = 無引用）。

    `rel_posix`（相對 repo 根的路徑）用來解析相對 import；單元變異負控可省略。
    """
    tree = ast.parse(src)
    hits: set[str] = set()

    services_names: set[str] = set()
    dyn_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "services":
                    services_names.add(alias.asname or "services")
                elif alias.name.startswith("services.") and not alias.asname:
                    services_names.add("services")
        elif isinstance(node, ast.ImportFrom) and node.module in ("importlib", "importlib.util"):
            for alias in node.names:
                if alias.name in _DYN_IMPORT_FUNCS:
                    dyn_names.add(alias.asname or alias.name)

    def is_dyn_call(call: ast.Call) -> bool:
        f = call.func
        if isinstance(f, ast.Attribute):
            return f.attr in _DYN_IMPORT_FUNCS
        if isinstance(f, ast.Name):
            return f.id in _DYN_IMPORT_FUNCS or f.id in dyn_names
        return False

    for node in ast.walk(tree):
        # 1. import / from-import
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_self_target(alias.name):
                    hits.add(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            if _is_self_target(mod):
                hits.add(f"from {mod} import …")
            if node.level == 0 and mod == "services":
                if any(a.name == "onebrain" for a in node.names):
                    hits.add("from services import onebrain")
            if node.level:
                resolved = _resolve_relative(rel_posix, node.level, node.module) if rel_posix else None
                if resolved is not None:
                    if _is_self_target(resolved):
                        hits.add(f"relative import resolving to {resolved}")
                    elif resolved == "services" and any(a.name == "onebrain" for a in node.names):
                        hits.add("relative import of services.onebrain")

        # 2. 屬性存取
        elif isinstance(node, ast.Attribute):
            d = _dotted(node)
            if d is not None:
                if _is_self_target(d):
                    hits.add(f"attribute {d}")
                segs = d.split(".")
                if len(segs) >= 2 and segs[0] in services_names and segs[1] == "onebrain":
                    hits.add(f"attribute {d} (via imported services)")
            elif (
                node.attr == "onebrain"
                and isinstance(node.value, ast.Call)
                and is_dyn_call(node.value)
                and _const_str(_call_arg(node.value, 0, "name")) == "services"
            ):
                hits.add("dynamic import of services then .onebrain")

        # 3. 呼叫形式
        elif isinstance(node, ast.Call):
            if is_dyn_call(node):
                name = _const_str(_call_arg(node, 0, "name"))
                if name is not None:
                    if name.startswith("."):
                        pkg = _const_str(_call_arg(node, 1, "package"))
                        if pkg is not None:
                            full = pkg + "." + name.lstrip(".")
                            if _is_self_target(full):
                                hits.add(f"dynamic import {full}")
                    elif _is_self_target(name):
                        hits.add(f"dynamic import {name}")
                    elif name == "services":
                        fl = _call_arg(node, 3, "fromlist")
                        if isinstance(fl, (ast.List, ast.Tuple)) and any(
                            _const_str(e) == "onebrain" for e in fl.elts
                        ):
                            hits.add("dynamic import services with fromlist onebrain")
            elif isinstance(node.func, ast.Name) and node.func.id == "getattr" and len(node.args) >= 2:
                base = _dotted(node.args[0])
                if (
                    base is not None
                    and (base.split(".")[0] in services_names or base == "services")
                    and _const_str(node.args[1]) == "onebrain"
                ):
                    hits.add("getattr(services, 'onebrain')")

        # 4. sys.modules["services.onebrain…"]
        elif isinstance(node, ast.Subscript):
            key = _const_str(node.slice)
            if key is not None and _is_self_target(key):
                hits.add(f"module table key {key}")
    return sorted(hits)


def _is_exempt(rel_parts: tuple[str, ...]) -> bool:
    """只豁免「repo 根的 tests/」與「services/onebrain/」；名稱相似者（tests_extra、ui/tests、onebrain2）不豁免。"""
    return rel_parts[:1] == ("tests",) or rel_parts[:2] == ("services", "onebrain")


def scan_repo(root: pathlib.Path) -> tuple[dict[str, list[str]], list[str]]:
    """回傳 ({檔: 命中形式}, 所有被掃描的相對路徑)。無法解析的檔 fail-closed 計為違規。"""
    violations: dict[str, list[str]] = {}
    scanned: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = pathlib.Path(dirpath).relative_to(root)
        if rel_dir.parts[:2] == (".claude", "worktrees"):
            dirnames[:] = []
            continue
        dirnames[:] = [d for d in dirnames if d not in _EXCLUDED_DIR_NAMES]
        for fn in filenames:
            if not fn.endswith(".py"):
                continue
            rel = (rel_dir / fn).as_posix()
            rel_parts = pathlib.PurePosixPath(rel).parts
            if _is_exempt(rel_parts):
                continue
            scanned.append(rel)
            try:
                src = (root / rel).read_text(encoding="utf-8")
                refs = find_onebrain_refs(src, rel)
            except (SyntaxError, UnicodeDecodeError, ValueError) as exc:
                violations[rel] = [f"UNPARSEABLE ({type(exc).__name__})"]
                continue
            if refs:
                violations[rel] = refs
    return violations, sorted(scanned)


def test_no_production_file_imports_services_onebrain():
    violations, _ = scan_repo(ROOT)
    assert violations == {}, (
        "FAKE 隔離被破壞：下列檔案取得了 services.onebrain（FAKE 輸出不得進正式頁面或 production 路徑）：\n"
        + "\n".join(f"  {k}: {v}" for k, v in sorted(violations.items()))
    )


def test_repo_scan_is_not_vacuous():
    """錨點：全 repo 掃描真的涵蓋各層（量測日 2026-11-20 共 1186 個 .py）。"""
    _, scanned = scan_repo(ROOT)
    assert len(scanned) >= 300, len(scanned)
    scanned_set = set(scanned)
    assert "app.py" in scanned_set
    assert "fund_fetcher.py" in scanned_set
    for top in ("ui", "services", "infra", "repositories", "shared", "scripts", "mcp_server"):
        assert any(s.startswith(top + "/") for s in scanned), f"{top}/ 沒被掃到"
    # 豁免區確實沒被掃（掃了反而代表豁免邏輯壞了）
    assert not any(s.startswith("tests/") for s in scanned)
    assert not any(s.startswith("services/onebrain/") for s in scanned)


# ── 變異負控：每一種取得形式都要被 find_onebrain_refs 抓到 ──────────────────

_T = TARGET
_FORMS = {
    "import_plain": f"import {_T}\n",
    "import_submodule": f"import {_T}.fake_provider\n",
    "import_as": f"import {_T} as ob\n",
    "import_submodule_as": f"import {_T}.fake_provider as fpm\n",
    "from_package": f"from {_T} import FakeProvider\n",
    "from_submodule": f"from {_T}.fake_provider import FakeProvider\n",
    "from_submodule_multiline": f"from {_T}.provider_types import (\n    ProviderRequest,\n    ProviderOutcome,\n)\n",
    "from_services_import_onebrain": "from services import onebrain\n",
    "from_services_import_as": "from services import onebrain as ob\n",
    "from_services_import_among_others": "from services import fund_service, onebrain\n",
    "attribute_after_import_services": "import services\nx = services.onebrain.FakeProvider\n",
    "attribute_after_import_services_submodule": "import services.fund_service\nx = services.onebrain\n",
    "attribute_via_alias": "import services as svc\nx = svc.onebrain\n",
    "attribute_chain_full": f"x = {_T}.fake_provider.FakeProvider\n",
    "getattr_form": 'import services\nx = getattr(services, "onebrain")\n',
    "importlib_import_module": f'import importlib\nimportlib.import_module("{_T}.fake_provider")\n',
    "importlib_import_module_pkg": f'import importlib\nimportlib.import_module("{_T}")\n',
    "importlib_keyword_name": f'import importlib\nimportlib.import_module(name="{_T}")\n',
    "importlib_from_import_alias": f'from importlib import import_module as im\nim("{_T}")\n',
    "importlib_concat": 'import importlib\nimportlib.import_module("services." + "onebrain")\n',
    "importlib_fstring_const": f'import importlib\nimportlib.import_module(f"{_T}")\n',
    "importlib_relative_with_package": 'import importlib\nimportlib.import_module(".onebrain", "services")\n',
    "importlib_then_attribute": 'import importlib\nx = importlib.import_module("services").onebrain\n',
    "dunder_import": f'__import__("{_T}")\n',
    "dunder_import_fromlist": '__import__("services", fromlist=["onebrain"])\n',
    "find_spec": f'import importlib.util\nimportlib.util.find_spec("{_T}")\n',
    "sys_modules_key": f'import sys\nm = sys.modules["{_T}"]\n',
    "nested_in_function": f"def f():\n    from {_T} import FakeProvider\n    return FakeProvider\n",
    "inside_try": f"try:\n    from {_T} import FakeProvider\nexcept ImportError:\n    FakeProvider = None\n",
    "inside_type_checking": f"from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from {_T}.provider_types import ProviderOutcome\n",
    "inside_class_body": f"class C:\n    import {_T}\n",
}


@pytest.mark.parametrize("label", sorted(_FORMS))
def test_every_import_form_is_detected(label):
    assert find_onebrain_refs(_FORMS[label]), f"形式 {label} 沒被 FAKE 隔離守衛抓到"


@pytest.mark.parametrize(
    "label,src",
    [
        ("other_service", "import services.fund_service\nfrom services import fund_service\n"),
        ("prefix_lookalike_module", f"from {_T}_other import x\nimport {_T}ish\n"),
        ("prefix_lookalike_attr", f"import services\nx = services.onebrain_other\ny = services.onebrain2\n"),
        ("importlib_other_module", 'import importlib\nimportlib.import_module("services.fund_service")\n'),
        ("importlib_variable_arg_not_resolvable", "import importlib\nname = 'x'\nimportlib.import_module(name)\n"),
        ("bare_string_is_not_an_import", f'x = "{_T}"\n'),
        ("getattr_other_attr", 'import services\nx = getattr(services, "fund_service")\n'),
        ("unrelated_onebrain_name", "onebrain = 1\nx = onebrain + 1\n"),
        ("other_package_with_same_leaf", "from ui import onebrain\nimport shared.onebrain\n"),
    ],
)
def test_clean_sources_are_not_flagged(label, src):
    assert find_onebrain_refs(src) == [], f"{label} 被誤報"


# ── 相對 import（依檔案位置解析）──────────────────────────────────────────


@pytest.mark.parametrize(
    "rel,src",
    [
        ("services/foo.py", "from .onebrain import FakeProvider\n"),
        ("services/foo.py", "from .onebrain.fake_provider import FakeProvider\n"),
        ("services/foo.py", "from . import onebrain\n"),
        ("services/macro/foo.py", "from .. import onebrain\n"),
        ("services/macro/foo.py", "from ..onebrain import FakeProvider\n"),
        ("services/__init__.py", "from . import onebrain\n"),
        ("services/__init__.py", "from .onebrain import FakeProvider\n"),
    ],
)
def test_relative_imports_resolving_to_onebrain_are_detected(rel, src):
    assert find_onebrain_refs(src, rel), f"{rel}: {src!r}"


@pytest.mark.parametrize(
    "rel,src",
    [
        ("ui/foo.py", "from . import onebrain\n"),
        ("ui/foo.py", "from .onebrain import x\n"),
        ("services/foo.py", "from . import fund_service\n"),
        ("services/macro/foo.py", "from .. import fund_service\n"),
    ],
)
def test_relative_imports_not_resolving_to_onebrain_are_not_flagged(rel, src):
    assert find_onebrain_refs(src, rel) == []


# ── 全 repo 掃描邏輯的變異負控（tmp_path 組一個迷你 repo）──────────────────


def _write(root: pathlib.Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def test_scan_repo_flags_violators_and_respects_only_the_two_exempt_zones(tmp_path):
    bad = f"from {_T}.fake_provider import FakeProvider\n"
    # 應被抓到（含名稱相似、但不是真正豁免區者）
    flagged = [
        "app.py",
        "ui/page.py",
        "ui_v3/page.py",
        "infra/x.py",
        "repositories/r.py",
        "scripts/s.py",
        "mcp_server/m.py",
        "services/other.py",
        "services/onebrain2/a.py",
        "services/onebrain_extra.py",
        "ui/tests/helper.py",
        "scripts/tests_helper.py",
        "tests_extra/a.py",
    ]
    for rel in flagged:
        _write(tmp_path, rel, bad)
    # 不應被抓到（豁免區與非掃描區）
    exempt = [
        "services/onebrain/fake_provider.py",
        "services/onebrain/sub/deeper.py",
        "tests/test_x.py",
        "tests/sub/test_y.py",
        ".git/hooks/h.py",
        "venv/lib/v.py",
        ".claude/worktrees/w1/app.py",
    ]
    for rel in exempt:
        _write(tmp_path, rel, bad)
    _write(tmp_path, "ui/clean.py", "import services.fund_service\n")
    _write(tmp_path, "README.txt", bad)  # 非 .py 不掃

    violations, scanned = scan_repo(tmp_path)
    assert set(violations) == set(flagged)
    assert "ui/clean.py" in scanned
    assert not any(s in scanned for s in exempt)


def test_scan_repo_resolves_relative_imports_by_location(tmp_path):
    _write(tmp_path, "services/a.py", "from .onebrain import FakeProvider\n")
    _write(tmp_path, "services/m/b.py", "from .. import onebrain\n")
    _write(tmp_path, "ui/c.py", "from . import onebrain\n")  # ui.onebrain，不是目標
    violations, _ = scan_repo(tmp_path)
    assert set(violations) == {"services/a.py", "services/m/b.py"}


def test_scan_repo_fails_closed_on_unparseable_files(tmp_path):
    _write(tmp_path, "ui/broken.py", "def (:\n")
    violations, _ = scan_repo(tmp_path)
    assert list(violations) == ["ui/broken.py"]
    assert violations["ui/broken.py"][0].startswith("UNPARSEABLE")


def test_scan_repo_with_no_violations_is_clean(tmp_path):
    _write(tmp_path, "ui/ok.py", "import os\n")
    violations, scanned = scan_repo(tmp_path)
    assert violations == {}
    assert scanned == ["ui/ok.py"]


def test_exemption_predicate_is_exact():
    assert _is_exempt(("tests", "x.py"))
    assert _is_exempt(("tests", "a", "b.py"))
    assert _is_exempt(("services", "onebrain", "x.py"))
    assert not _is_exempt(("ui", "tests", "x.py"))
    assert not _is_exempt(("tests_extra", "x.py"))
    assert not _is_exempt(("services", "onebrain2", "x.py"))
    assert not _is_exempt(("services", "x.py"))
    assert not _is_exempt(("app.py",))
