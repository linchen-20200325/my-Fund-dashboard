# -*- coding: utf-8 -*-
"""ui_v3 唯讀守衛（80 第 9 節守衛 (2)；鏡像 `tests/ui_v2/test_readonly_write_surface_guard.py` 的做法，純 AST）。

⚠️ 說明：80 第 9 節原寫「擴大 ui_v2 守衛的 SCAN_DIRS 納入 ui_v3」；依本批的邊界（ui_v2 測試一字不動），
改在本目錄**平行**建立等價守衛，涵蓋 `ui_v3/**`：
1. 不得 import／呼叫已知寫入函式（pool／保單／帳本／快照／設定試算表 L1 與 L2 寫入入口）；
2. 不得有 gspread 寫入方法呼叫；
3. 不得有 HTTP 寫入動詞（requests／httpx／session…的 post／put／patch／delete）；
4. 不得有檔案系統寫入（open／`Path.open` 寫入模式、write_text／write_bytes、unlink、mkdir、`os.remove／rename／popen…`、
   `shutil.copy*／move／rmtree…`；`import os as o` 這類一層 alias 會還原）。
⚠️ 仍未涵蓋：多層 alias、`getattr(os, 字串組名)`、經第三方套件的寫入、以變數傳入的 open mode（非字面常數）。
第一階段唯讀（`DEC-2026-10-26-01`、13.2）；負控一律在記憶體內餵違規片段。
"""
from __future__ import annotations

import pytest

import ui_v3_guard_lib as lib


def test_scan_population_is_not_empty():
    assert any(lib.rel_of(p).startswith("ui_v3/viewmodels/") for p in lib.population())


def test_ui_v3_has_no_write_surface():
    hits = lib.all_violations(lib.write_surface_violations)
    assert not hits, "ui_v3 第一階段唯讀，出現寫入面：\n" + "\n".join(hits)


def test_known_write_function_list_covers_ui_v2_guard_list():
    """本檔的名單不得比 ui_v2 守衛的名單少（AST 讀 ui_v2 守衛的 frozenset 字面值；不 import 它）。"""
    import ast
    src = lib.read(lib.ROOT / "tests" / "ui_v2" / "test_readonly_write_surface_guard.py")
    names = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "KNOWN_WRITE_FUNCTIONS" for t in node.targets):
            names = {n.value for n in ast.walk(node.value) if isinstance(n, ast.Constant) and isinstance(n.value, str)}
    assert names, "找不到 ui_v2 守衛的 KNOWN_WRITE_FUNCTIONS（守衛失效）"
    assert names <= set(lib.KNOWN_WRITE_FUNCTIONS), names - set(lib.KNOWN_WRITE_FUNCTIONS)


VIOLATING = [
    "from repositories.pool_repository import add_or_update",
    "write_policy_v2(x)",
    "store.save_user_setting('k', 'v')",
    "mod.append_market_indicator(rows)",
    "sheet.append_row([1])",
    "ws.update_cell(1, 1, 'x')",
    "worksheet.batch_update([])",
    "gc.update([])",
    "spreadsheet.clear()",
    "requests.post(url, json={})",
    "session.put(url)",
    "client.delete(url)",
    "open('f.txt', 'w')",
    "open('f.txt', mode='a')",
    "open('f.bin', 'r+b')",
    "p.write_text('x')",
    "p.write_bytes(b'x')",
    "p.unlink()",
    "os.remove('f')",
    "shutil.rmtree('d')",
    "os.system('rm -rf x')",
    # 稽核補強
    "Path('f').open('w')",
    "p.open('a')",
    "p.open(mode='wb')",
    "Path('f').open('r+')",
    "Path('f').write_text('x')",
    "Path('f').write_bytes(b'x')",
    "import shutil\nshutil.copy('a', 'b')",
    "import shutil\nshutil.copy2('a', 'b')",
    "import shutil\nshutil.copyfile('a', 'b')",
    "import shutil\nshutil.copytree('a', 'b')",
    "import shutil\nshutil.move('a', 'b')",
    "import shutil\nshutil.rmtree('d')",
    "import os\nos.popen('x')",
    "import os\nos.remove('f')",
    "import os\nos.rename('a', 'b')",
    "import os\nos.replace('a', 'b')",
    "import os\nos.unlink('f')",
    "import os\nos.makedirs('d')",
    "import os as o\no.remove('f')",
    "import shutil as sh\nsh.move('a', 'b')",
    "from shutil import copy",
    "from shutil import move, rmtree",
    "from os import remove",
    "from os import popen",
]


@pytest.mark.parametrize("source", VIOLATING)
def test_negative_control_write_guard_turns_red(source):
    assert lib.write_surface_violations("ui_v3/pages/x.py", source), source


@pytest.mark.parametrize("source", [
    "d = {}\nd.update({'a': 1})",  # dict.update：接收者不像 gspread 物件
    "cache.clear()",
    "open('f.txt')",
    "open('f.txt', 'r')",
    "x = ','.join(['a'])",
    "text.replace('a', 'b')",
    "items.remove(3)",  # list.remove：接收者不是 os／shutil
    "Path('f').open()",
    "Path('f').open('rb')",
    "Path('f').read_text()",
    "import os\nos.path.join('a', 'b')",
    "import os\nx = os.environ.get('K')",
    "s.replace('a', 'b')",
])
def test_negative_control_benign_snippets_stay_green(source):
    assert lib.write_surface_violations("ui_v3/pages/x.py", source) == []
