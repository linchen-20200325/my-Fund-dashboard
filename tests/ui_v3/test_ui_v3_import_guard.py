# -*- coding: utf-8 -*-
"""ui_v3 import 隔離守衛（80 第 8、9 節；純 AST，不用字串 grep；不依賴 conftest fixture）。

本機執行（conftest 會 import 本環境沒有的套件）：
    /root/.local/bin/pytest tests/ui_v3 -q --noconftest -p no:cacheprovider

規則（逐檔，母體＝`ui_v3/**/*.py`，新檔自動納入，未知層目錄＝紅）：
1. 不得 import Old UI（`ui`、根目錄 `app`）與 `ui_v2`（本批不開任何 reuse 白名單）；
2. 只有 `adapters/` 可以 import `services.v2_tables`／`services.v2_domain`；其餘 services／repositories／shared／infra 一律不准，
   唯一例外：`viewmodels/`、`pages/` 可以 import `shared.ui_semantics`（批 2b 呈現規則資料表；須寫完整路徑）；
3. `viewmodels/`、`fixtures/`、`design/` 只准標準函式庫（＋允許的 ui_v3 內部層），不得 import streamlit；
4. 層間依賴只准 `LAYER_DEPS` 表內的方向（viewmodels 不依賴任何其他層；fixtures 只依賴 viewmodels…）；
5. 網路／外部程序／持久層套件（含 asyncio、imaplib、poplib、smtplib、xmlrpc、ftplib、telnetlib、sqlite3、http、urllib…）、
   動態 import（importlib／`__import__`／`sys.modules`／exec／eval）與 builtins 後門
   （`builtins`、`__builtins__`、`globals()`／`locals()`／`vars()`）一律不准；
   ⚠️ 仍未涵蓋：字串組名後 `getattr(obj, name)`、`__subclasses__`／`__dict__` 取物件（見 `ui_v3_guard_lib` docstring）；
6. import 零副作用：模組層只准 import／def／class／賦值／docstring／`__main__` 守衛。
負控全部在記憶體內餵違規片段，確認守衛會轉紅（不寫檔）。
"""
from __future__ import annotations

import pytest

import ui_v3_guard_lib as lib


def test_population_is_not_empty_and_has_expected_layers():
    rels = {lib.rel_of(p) for p in lib.population()}
    assert "ui_v3/__init__.py" in rels
    assert "ui_v3/viewmodels/components.py" in rels
    assert "ui_v3/adapters/__init__.py" in rels
    layers = {lib.layer_of(r) for r in rels}
    assert layers <= set(lib.LAYER_DEPS), layers - set(lib.LAYER_DEPS)


def test_every_ui_v3_directory_is_a_regular_package():
    dirs = {p.parent for p in lib.population()}
    for d in dirs:
        assert (d / "__init__.py").exists(), f"{d} 缺 __init__.py"


def test_no_import_violations_in_ui_v3():
    hits = lib.all_violations(lib.import_violations)
    assert not hits, "ui_v3 import 違規：\n" + "\n".join(hits)


def test_import_time_is_side_effect_free():
    hits = []
    for p in lib.population():
        hits += [f"{lib.rel_of(p)} {v}" for v in lib.module_level_side_effects(lib.read(p))]
    assert not hits, "模組層有執行語句：\n" + "\n".join(hits)


def test_adapters_stub_imports_nothing_yet():
    """批 1 的 adapters 只是說明（stub）：零 import，確認沒有人偷偷在這一批接了真資料。"""
    import ast
    tree = ast.parse(lib.read(lib.UI_V3 / "adapters" / "__init__.py"))
    assert lib.imports_of(tree, "ui_v3.adapters") == []
    assert [type(s).__name__ for s in tree.body] == ["Expr"]  # 只有 docstring


# ─────────────── 負控：違規片段必須轉紅；合規片段必須綠 ───────────────
VIOLATING = [
    ("ui_v3/viewmodels/x.py", "import streamlit as st", "streamlit"),
    ("ui_v3/viewmodels/x.py", "from services.v2_tables import contract", "adapters"),
    ("ui_v3/fixtures/x.py", "from services.v2_tables.masking import mask", "adapters"),
    ("ui_v3/pages/x.py", "from services.v2_tables import market_view", "adapters"),
    ("ui_v3/shell/x.py", "import services.v2_domain.x", "adapters"),
    ("ui_v3/adapters/x.py", "from services.fund_service import f", "services 模組"),
    ("ui_v3/adapters/x.py", "from repositories.macro import yf", "舊樹"),
    ("ui_v3/adapters/x.py", "from shared import colors", "舊樹"),
    ("ui_v3/adapters/x.py", "import infra.proxy", "舊樹"),
    ("ui_v3/pages/x.py", "from ui.helpers import x", "舊樹"),
    ("ui_v3/pages/x.py", "import app", "舊樹"),
    ("ui_v3/pages/x.py", "import ui_v2.shell", "ui_v2"),
    ("ui_v3/pages/x.py", "from ui_v2.mkt import page", "ui_v2"),
    ("ui_v3/pages/x.py", "from ui_v2 import status_class", "ui_v2"),
    ("ui_v3/viewmodels/x.py", "import pandas as pd", "第三方"),
    ("ui_v3/viewmodels/x.py", "from ui_v3.fixtures import scenarios", "不得 import ui_v3.fixtures"),
    ("ui_v3/viewmodels/x.py", "from ui_v3.adapters import y", "不得 import ui_v3.adapters"),
    ("ui_v3/viewmodels/x.py", "from . import sibling_in_other_layer_is_fine_but_this_is_relative_up\nfrom .. import fixtures", "不得 import ui_v3.fixtures"),
    ("ui_v3/fixtures/x.py", "from ui_v3.pages import p", "不得 import ui_v3.pages"),
    ("ui_v3/app_preview.py", "from ui_v3.fixtures.scenarios import SCENARIOS", "不得 import ui_v3.fixtures"),
    ("ui_v3/pages/x.py", "from ui_v3.app_preview import main", "進入點"),
    ("ui_v3/pages/x.py", "import requests", "網路"),
    ("ui_v3/pages/x.py", "import subprocess", "網路"),
    ("ui_v3/pages/x.py", "import gspread", "網路"),
    ("ui_v3/pages/x.py", "import importlib", "動態 import"),
    ("ui_v3/pages/x.py", "x = __import__('os')", "動態"),
    ("ui_v3/pages/x.py", "import sys\nm = sys.modules", "動態"),
    ("ui_v3/pages/x.py", "exec('1')", "動態"),
    ("ui_v3/pages/x.py", "y = getattr(obj, 'modules')", "動態"),
    ("ui_v3/newlayer/x.py", "import os", "未知的層目錄"),
    # 稽核補強：builtins 後門與標準函式庫的網路／持久層模組
    ("ui_v3/pages/x.py", "import builtins\nb = getattr(builtins, '__imp' + 'ort__')", "builtins"),
    ("ui_v3/pages/x.py", "from builtins import __import__", "builtins"),
    ("ui_v3/viewmodels/x.py", "m = globals()['__builtins__']", "動態"),
    ("ui_v3/viewmodels/x.py", "m = __builtins__", "動態"),
    ("ui_v3/viewmodels/x.py", "g = globals()", "動態"),
    ("ui_v3/viewmodels/x.py", "g = locals()", "動態"),
    ("ui_v3/viewmodels/x.py", "g = vars(obj)", "動態"),
    ("ui_v3/pages/x.py", "import asyncio", "網路"),
    ("ui_v3/pages/x.py", "import imaplib", "網路"),
    ("ui_v3/pages/x.py", "import poplib", "網路"),
    ("ui_v3/pages/x.py", "import smtplib", "網路"),
    ("ui_v3/pages/x.py", "import xmlrpc.client", "網路"),
    ("ui_v3/pages/x.py", "import ftplib", "網路"),
    ("ui_v3/pages/x.py", "import telnetlib", "網路"),
    ("ui_v3/pages/x.py", "import sqlite3", "網路"),
    ("ui_v3/pages/x.py", "import http.client", "網路"),
    ("ui_v3/pages/x.py", "import urllib.request", "網路"),
    ("ui_v3/pages/x.py", "from urllib import request", "網路"),
    ("ui_v3/pages/x.py", "import shutil", "網路"),
    ("ui_v3/pages/x.py", "import multiprocessing", "網路"),
    # 批 2b：shared 只開 shared.ui_semantics、只給 viewmodels／pages、只准完整路徑
    ("ui_v3/viewmodels/x.py", "from shared import colors", "舊樹"),
    ("ui_v3/viewmodels/x.py", "from shared import ui_semantics", "舊樹"),
    ("ui_v3/viewmodels/x.py", "import shared", "舊樹"),
    ("ui_v3/viewmodels/x.py", "from shared.ui_semantics_extra import x", "舊樹"),
    ("ui_v3/viewmodels/x.py", "from shared.colors import MATERIAL_RED", "舊樹"),
    ("ui_v3/pages/x.py", "import shared.fund_identity", "舊樹"),
    ("ui_v3/fixtures/x.py", "from shared.ui_semantics import rules", "不得 import shared.ui_semantics"),
    ("ui_v3/adapters/x.py", "from shared.ui_semantics import rules", "不得 import shared.ui_semantics"),
    ("ui_v3/design/x.py", "from shared.ui_semantics.rules import TONES", "不得 import shared.ui_semantics"),
    ("ui_v3/shell/x.py", "import shared.ui_semantics", "不得 import shared.ui_semantics"),
    ("ui_v3/app_preview.py", "from shared.ui_semantics import rules", "不得 import shared.ui_semantics"),
]


@pytest.mark.parametrize("rel,source,needle", VIOLATING)
def test_negative_control_import_guard_turns_red(rel, source, needle):
    hits = lib.import_violations(rel, source)
    assert hits and any(needle in h for h in hits), (rel, source, hits)


COMPLIANT = [
    ("ui_v3/viewmodels/x.py", "from __future__ import annotations\nimport math\nfrom dataclasses import dataclass"),
    ("ui_v3/viewmodels/x.py", "from ui_v3.viewmodels.common import FactMeta\nfrom . import common"),
    ("ui_v3/fixtures/x.py", "from ui_v3.viewmodels import MetricCard"),
    ("ui_v3/adapters/x.py", "from services.v2_tables import market_view\nfrom services.v2_tables.masking import mask"),
    ("ui_v3/adapters/x.py", "from services.v2_domain.x import y\nimport streamlit as st"),
    ("ui_v3/pages/x.py", "import streamlit as st\nfrom ui_v3.viewmodels import MetricCard\nfrom ui_v3.shell import registry"),
    ("ui_v3/app_preview.py", "from ui_v3.shell.registry import assert_preview_ready"),
    ("ui_v3/viewmodels/x.py", "from shared.ui_semantics import rules\nfrom shared.ui_semantics.rules import MISSING_TEXT"),
    ("ui_v3/pages/x.py", "import shared.ui_semantics.rules as r"),
]


@pytest.mark.parametrize("rel,source", COMPLIANT)
def test_negative_control_compliant_snippets_stay_green(rel, source):
    assert lib.import_violations(rel, source) == []


@pytest.mark.parametrize("source", [
    "print('hi')",
    "register_page()",
    "import os\nos.environ['X'] = '1'",
    "x = 1\nfor i in range(3):\n    pass",
])
def test_negative_control_side_effects_turn_red(source):
    assert lib.module_level_side_effects(source)


def test_side_effect_guard_accepts_defs_assigns_docstring_and_main_guard():
    src = '"""doc"""\nimport os\nX = 1\n\ndef f():\n    print("ok inside def")\n\nif __name__ == "__main__":\n    f()\n'
    assert lib.module_level_side_effects(src) == []
