# -*- coding: utf-8 -*-
"""preview 不是正式入口的守衛（BL-0535 的前置；`DEC-2026-11-02-06`、`PROJECT_RULES.md` 13.2）。

BL-0535 的 cutover 守衛（正式 entrypoint 只註冊 ui_v3 頁、無切換 widget）在 cutover 批撰寫；
本檔只做批 1 能做的前置，防止 preview 在 cutover 之前被「暴露」：
1. 正式入口候選（根目錄 `app.py`、其他根目錄 `.py`、`ui/**`、`ui_v2/**`、`services`／`repositories`／`shared`／`infra`／`scripts`／`mcp_server`／`models`、
   `.streamlit/`、`.github/`、`.devcontainer/`）**不得引用 ui_v3**（import 以 AST；其餘文字檔以字串）；
2. `ui_v3/app_preview.py` 不 import streamlit、不 import fixtures、import 零副作用、`main()` Fail Loud
   （沒有任何已核准的頁 → 拋 `PreviewNotReady`），因此即使被誤設成 main file 也只會大聲失敗、不會顯示空殼頁（`streamlit run` 本身的行為未實測；絕不可設為 Cloud main file）；
   ⚠️ 引用偵測是 import AST＋字串常數；以字串拼接組成 `ui_v3` 名稱的繞法不在涵蓋內（誠實揭露）；
3. preview 檔本身沒有任何 Streamlit 顯示呼叫。
"""
from __future__ import annotations

import ast
import os
import pathlib
import subprocess
import sys

import pytest

import ui_v3_guard_lib as lib

_PREVIEW = lib.UI_V3 / "app_preview.py"
_TEXT_DIRS = (".streamlit", ".github", ".devcontainer")
_PY_DIRS = ("ui", "ui_v2", "services", "repositories", "shared", "infra", "scripts", "mcp_server", "models")


def references_ui_v3(source: str) -> list:
    """import 層級（AST）：任何 import 以 ui_v3 開頭；另抓動態引用字串 `"ui_v3"`／`'ui_v3...'` 出現在字串常數內。"""
    tree = ast.parse(source)
    hits = [m for m in lib.imports_of(tree, "x") if m == "ui_v3" or m.startswith("ui_v3.")]
    hits += [f"字串常數 {n.value!r}" for n in ast.walk(tree)
             if isinstance(n, ast.Constant) and isinstance(n.value, str) and "ui_v3" in n.value]
    return hits


def _py_files_under(dirs):
    for d in dirs:
        base = lib.ROOT / d
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [x for x in dirnames if x != "__pycache__"]
            for f in filenames:
                if f.endswith(".py"):
                    yield os.path.join(dirpath, f)


def test_formal_entry_candidates_do_not_reference_ui_v3():
    import pathlib
    files = [str(p) for p in lib.ROOT.glob("*.py")] + list(_py_files_under(_PY_DIRS))
    assert any(f.endswith("/app.py") for f in files), "找不到根目錄 app.py（守衛失效）"
    hits = []
    for f in files:
        h = references_ui_v3(lib.read(pathlib.Path(f)))
        hits += [f"{os.path.relpath(f, lib.ROOT)}: {x}" for x in h]
    assert not hits, "正式路徑引用了 ui_v3（preview 不得暴露）：\n" + "\n".join(hits)


def test_config_dirs_do_not_reference_ui_v3():
    hits = []
    for d in _TEXT_DIRS:
        for dirpath, _dirs, filenames in os.walk(lib.ROOT / d):
            for f in filenames:
                path = os.path.join(dirpath, f)
                try:
                    text = open(path, encoding="utf-8").read()
                except (UnicodeDecodeError, OSError):
                    continue
                if "ui_v3" in text:
                    hits.append(os.path.relpath(path, lib.ROOT))
    assert not hits, "設定／workflow 引用了 ui_v3（不得把 preview 掛進正式或 CI 入口）：" + ", ".join(hits)


def test_preview_module_is_pure_declaration_without_streamlit_or_fixtures():
    src = lib.read(_PREVIEW)
    assert lib.module_level_side_effects(src) == []
    mods = lib.imports_of(ast.parse(src), "ui_v3")
    assert not any(m.split(".")[0] == "streamlit" for m in mods)
    assert not any(m.startswith("ui_v3.fixtures") for m in mods)
    assert lib.import_violations("ui_v3/app_preview.py", src) == []
    # 沒有任何 Streamlit 顯示呼叫（沒有 import streamlit，名稱 st 也不該出現）
    assert not any(isinstance(n, ast.Name) and n.id == "st" for n in ast.walk(ast.parse(src)))


def test_preview_main_fails_loud_when_no_page_is_registered():
    from ui_v3 import app_preview
    from ui_v3.shell.registry import PreviewNotReady
    with pytest.raises(PreviewNotReady):
        app_preview.main()


def test_running_preview_as_a_script_fails_loud_and_renders_nothing():
    """以 `__main__` 執行（等同 `streamlit run` 的載入方式）：非 0 結束、stderr 有 PreviewNotReady、stdout 無輸出。"""
    proc = subprocess.run([sys.executable, "-s", str(_PREVIEW)], capture_output=True, text=True,
                          cwd=str(lib.ROOT), env={"PYTHONPATH": str(lib.ROOT)}, timeout=60)
    assert proc.returncode != 0
    assert "PreviewNotReady" in proc.stderr
    assert proc.stdout.strip() == ""


def test_importing_ui_v3_does_not_import_streamlit_or_old_tree():
    code = (
        "import sys, importlib, pkgutil, ui_v3\n"
        "for m in pkgutil.walk_packages(ui_v3.__path__, 'ui_v3.'):\n"
        "    importlib.import_module(m.name)\n"
        "bad = sorted(n for n in sys.modules if n.split('.')[0] in "
        "{'streamlit','ui','ui_v2','services','repositories','shared','infra','fund_fetcher','app'})\n"
        "print('BAD:' + ','.join(bad))\n"
    )
    proc = subprocess.run([sys.executable, "-s", "-c", code], capture_output=True, text=True,
                          cwd=str(lib.ROOT), env={"PYTHONPATH": str(lib.ROOT)}, timeout=60)
    assert proc.returncode == 0, proc.stderr
    # 批 2b：viewmodels 讀 shared.ui_semantics（明列白名單）；import 它會連帶載入 `shared` 套件本身（其 __init__ 只有 docstring）。
    # 白名單逐一列名，任何其他 shared 模組或舊樹模組照舊是紅（H3 起另開 services.v2_domain 子樹，見 `runtime_disallowed`）。
    bad = runtime_disallowed(proc.stdout.strip().removeprefix("BAD:").split(","))
    assert proc.stdout.startswith("BAD:") and not bad, proc.stdout


_RUNTIME_ALLOWED = frozenset({"shared", "shared.ui_semantics", "shared.ui_semantics.rules", "services", "services.v2_domain"})


def runtime_disallowed(names):
    """import 全部 ui_v3 後 sys.modules 裡不准出現的模組名。

    BL-0536-H3：`ui_v3/adapters/market_chart.py` 是第一個真的 import 下層的 adapter（靜態守衛本來就准 adapters import
    `services.v2_domain`）。執行期白名單只多開 `services` 套件本身與 `services.v2_domain` 子樹（純 L2、只用標準庫，
    由 `tests/test_v2_domain_port.py` 守）；其他 services 模組（含 `services.v2_tables`）與舊樹模組照舊是紅。
    """
    return [n for n in names if n and n not in _RUNTIME_ALLOWED and not n.startswith("services.v2_domain.")]


@pytest.mark.parametrize("name", [
    "streamlit", "ui.tab1", "ui_v2", "services.v2_tables", "services.v2_tables.market_view", "services.fund_service",
    "services.v2_domainx", "repositories.macro", "shared.colors", "infra.proxy",
])
def test_negative_control_runtime_allowlist_turns_red(name):
    assert runtime_disallowed([name]) == [name]


def test_runtime_allowlist_accepts_v2_domain_and_ui_semantics():
    assert runtime_disallowed(["services", "services.v2_domain", "services.v2_domain.normalization",
                               "shared", "shared.ui_semantics.rules", ""]) == []


@pytest.mark.parametrize("source", [
    "from ui_v3 import app_preview",
    "import ui_v3.shell.registry",
    "from ui_v3.shell import registry",
    "import importlib\nimportlib.import_module('ui_v3.app_preview')",
    "PAGE = 'ui_v3/app_preview.py'",
])
def test_negative_control_reference_detector_turns_red(source):
    assert references_ui_v3(source), source


def test_negative_control_unrelated_source_not_flagged():
    assert references_ui_v3("import ui_v2.shell\nx = 'ui_v2/app_preview.py'") == []


def has_root_pages_dir(root) -> bool:
    """根目錄是否有 `pages/` 目錄（啟發式偵測器；真測試與負控共用同一個函式）。"""
    return (pathlib.Path(root) / "pages").is_dir()


def test_heuristic_no_root_pages_directory():
    """啟發式守衛（BL-0537 相關；`DEC-2026-11-03-02`）：根目錄不得出現 `pages/` 目錄。

    Streamlit 會把根目錄 `pages/` 內的檔案自動長成多頁導覽；若有人把 preview 或舊版頁放進去，
    就會在不經 entrypoint 註冊的情況下被暴露。⚠️ 這只是啟發式：它不證明沒有其他暴露路徑
    （例如 `st.navigation`／`st.Page` 的明確註冊，或 `.streamlit/` 設定），也不是 BL-0535 的 cutover 守衛。
    """
    assert not has_root_pages_dir(lib.ROOT), "根目錄出現 pages/：Streamlit 會自動把它長成導覽，需客戶裁示後才可新增"


def test_negative_control_root_pages_detector(tmp_path):
    assert has_root_pages_dir(tmp_path) is False
    (tmp_path / "pages").mkdir()
    assert has_root_pages_dir(tmp_path) is True
