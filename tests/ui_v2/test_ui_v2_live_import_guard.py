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
- (8) 2026-10-12 客戶核准的 B 線預覽入口 `ui_v2/app_preview.py`（`_PREVIEW`）：
      **只有這一個檔名**、**只限 `_PREVIEW_LIVE_PAGES` 四頁**的 `source` 可以被它 import
      （第 (1) 條對它開的口子就這麼大）；它同時被當成正式路徑檔看待 ——
      第 (3) 條「不得 import fixtures」與 fail-closed 逐檔白名單一併適用。

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
    # 2026-10-13 客戶裁示（市場總覽設定存檔接上 user_setting）：加 `settings_store`（讀寫已存設定，同 set／alo）
    # 與 `ui_v2.mkt.live`（本頁純函式：設定值解析；不 import streamlit、不 import 舊樹，體例同 alo）。
    "ui_v2/mkt/source.py": {
        "__future__", "os", "streamlit",
        "services.v2_tables.market_indicator", "services.v2_tables.masking",
        "services.v2_tables.settings_store", "ui_v2.mkt.live",
        # 2026-10-27 BL-0516 批 1（客戶 `DEC-2026-10-27-41`、執行組讀法 `-42` (c)）：🌍 市場趨勢區段的唯讀 Data View
        # （L2 新檔 `market_view`；只讀、不寫 `market_indicator` 表）。逐模組列名，不開整個 `services`。
        "services.v2_tables.market_view",
    },
    "ui_v2/app_mkt_live.py": {
        "__future__", "pathlib", "sys", "streamlit", "ui_v2.mkt.page", "ui_v2.mkt.source",
    },
    # 2026-09-26 set 頁正式模式（客戶核准的線框草稿）。`spec` 是規格快照（純 tuple），不是 fixtures。
    "ui_v2/set/source.py": {
        "__future__", "logging", "os", "datetime.datetime", "datetime.timezone", "streamlit",
        "services.v2_tables.market_indicator", "services.v2_tables.masking",
        "services.v2_tables.settings_store", "ui_v2.set.spec",
        # 2026-10-26 批 3b-2：Google 個人登入的 L2 橋接（只此一個，只給 set 頁的 source.py）
        "services.v2_tables.personal_session",
    },
    "ui_v2/app_set_live.py": {
        "__future__", "pathlib", "sys", "streamlit", "ui_v2.set.page", "ui_v2.set.source",
    },
    # 2026-09-28 alo 頁正式模式接線骨架（客戶 2026-09-28 核准的 docs/wireframes/draft_alo_live.html）。
    # `ui_v2.alo.live` 是本頁的純函式模組（設定值解析、示意字樣移除、寫入端按鈕停用），
    # 不是 fixtures —— 它不 import streamlit、不 import 舊樹，體例同 `ui_v2/set/source.py` 之於 `spec`。
    # 2026-10-13 客戶裁示（B 線資產配置必須是真資料）：加 `fund_keys`／`nav_dividend`（淨值，同 hld 入口）
    # 與 `market_indicator`（49 §6.1 Q9 非美元匯率鍵，`build_fx_indicator_table`）；`logging`：被包住的取數例外記 log（稽核 B2）；
    # `datetime.datetime`：台灣日曆日（第二輪 N-b）。~~`contract`~~ 第三輪撤掉：門檻改住 `ui_v2/alo/live.py`，用不到了。
    "ui_v2/alo/source.py": {
        "__future__", "logging", "os", "datetime.datetime", "streamlit",
        "services.v2_tables.alo_holdings", "services.v2_tables.fund_keys",
        "services.v2_tables.market_indicator", "services.v2_tables.masking",
        "services.v2_tables.nav_dividend", "services.v2_tables.settings_store", "ui_v2.alo.live",
        # 2026-10-26 批 3b-4：沒有 Active Sheet 的明確狀態（`NoActiveSource`、失敗碼對應字）；純 ui_v2 內部模組，不碰個人憑證
        "ui_v2.active_gate",
    },
    "ui_v2/app_alo_live.py": {
        "__future__", "pathlib", "sys", "streamlit", "ui_v2.alo.page", "ui_v2.alo.source",
    },
    # 2026-10-09 hld 頁正式模式（S6b-3）。`ui_v2.hld.live` 是本頁的純函式模組，體例同 alo。
    "ui_v2/hld/source.py": {
        "__future__", "os", "streamlit",
        "services.v2_tables.alo_holdings", "services.v2_tables.contract", "services.v2_tables.fund_keys",
        "services.v2_tables.masking", "services.v2_tables.nav_dividend", "services.v2_tables.settings_store",
        "ui_v2.hld.live",
        # 2026-10-26 批 3b-4：同 alo（見上）
        "ui_v2.active_gate",
    },
    "ui_v2/app_hld_live.py": {
        "__future__", "pathlib", "sys", "streamlit", "ui_v2.hld.page", "ui_v2.hld.source",
    },
    # 2026-10-13 exp 頁正式模式第一批（客戶 2026-10-13 裁示：骨架＋設定存讀＋母體代碼）。
    # `exp_universe`：選股池代碼（L2 新檔）；`settings_store`：讀寫 `exp_` 四鍵；`ui_v2.exp.live`：本頁純函式（體例同 mkt）。
    # 2026-10-14 C2 接線（基本資料與淨值）：加 `fund_keys`（代碼對照）、`exp_profile`（基本資料逐欄出處）、
    # `exp_nav`（淨值與配息的逐檔記憶）、`nav_dividend`（扣下代碼常數）；`datetime.datetime`：台灣今天的日期（同 alo）。
    # `logging`：代碼對照表讀取失敗記 log（2026-10-14 修正輪）。
    # `traceback`：同一條 log 帶遮蔽後的 traceback（2026-10-15 #966 修正輪 3，獨立稽核小修；標準庫）。
    "ui_v2/exp/source.py": {
        "__future__", "logging", "os", "traceback", "datetime.datetime", "streamlit",
        "services.v2_tables.exp_nav", "services.v2_tables.exp_profile", "services.v2_tables.exp_universe",
        "services.v2_tables.fund_keys", "services.v2_tables.masking", "services.v2_tables.nav_dividend",
        "services.v2_tables.settings_store", "ui_v2.exp.live",
    },
    "ui_v2/app_exp_live.py": {
        "__future__", "pathlib", "sys", "streamlit", "ui_v2.exp.page", "ui_v2.exp.source",
    },
    # 2026-10-12 B 線預覽入口（客戶核准）：~~四頁真資料（page ＋ source）、標的探索只有 page（示意資料）~~。
    # ~~⛔ 沒有 `ui_v2.exp.source`（標的探索沒有真資料版）~~ → 2026-10-13 狀態更新（不是漏刪）：標的探索接上正式模式，
    #   預覽改傳 `exp.source`（與 `app_exp_live.py` 同名參數、同一物件）。⛔ 沒有任何 `fixtures`、沒有任何 `ui_v2.app_*`。
    "ui_v2/app_preview.py": {
        "__future__", "pathlib", "sys", "streamlit",
        "ui_v2.mkt.page", "ui_v2.mkt.source",
        "ui_v2.hld.page", "ui_v2.hld.source",
        "ui_v2.exp.page", "ui_v2.exp.source",
        "ui_v2.alo.page", "ui_v2.alo.source",
        "ui_v2.set.page", "ui_v2.set.source",
        # 2026-10-30 BL-0525 Batch D（客戶 `DEC-2026-10-30-02`）：💼 我的資產合併頁 `ui_v2.asset.page`（只有 page；`source` 仍只能是上列各頁的）。
        # 白名單只多這**一個**口子，其餘一個字沒放寬；`ui_v2/asset/*.py` 本身受同一份守衛（舊樹／網路／動態 import／`ui_v2.app_*`）掃描。
        "ui_v2.asset.page",
        # 2026-10-27 殼層批（BL-0484／BL-0479；D1 方案 A，客戶 `DEC-2026-10-27-01`；D1 草稿第 8.4 節「改守衛，明載於 PR」）：
        # 只多這**一個**口子 `ui_v2.shell`（純導覽；自己只 import `streamlit` 與 `ui_v2.shell_nav`，不碰任何頁、`source`、`fixtures`）。
        # 白名單其餘一個字沒放寬；`shell` 本身受同一份守衛（舊樹／網路／動態 import／`ui_v2.app_*`）掃描。
        "ui_v2.shell",
    },
}

# 第 (8) 條：預覽入口的檔名與它可以 import `source` 的頁（逐一列名，不用前綴比對）。
_PREVIEW = "ui_v2/app_preview.py"
# ~~_PREVIEW_LIVE_PAGES = ("mkt", "hld", "alo", "set")~~ → 2026-10-13 加 exp（狀態更新，不是漏刪）。
_PREVIEW_LIVE_PAGES = ("mkt", "hld", "exp", "alo", "set")


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
    is_preview = rel == _PREVIEW  # 第 (8) 條：只認這一個檔名

    imported = [m for m in imported if not m.startswith("__future__.")]  # 編譯器指示，不是模組
    for module in imported:
        parts = module.split(".")
        root = parts[0]
        if root in _NET_ROOTS:
            bad.append(f"網路套件 {module}")
        if len(parts) >= 3 and parts[0] == "ui_v2" and parts[2] == "source" \
                and not (is_live_app and parts[1] == live_page) \
                and not (is_preview and parts[1] in _PREVIEW_LIVE_PAGES):
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
        if (is_live_app or is_source or is_preview) and len(parts) >= 3 and parts[0] == "ui_v2" \
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
    elif is_live_app or is_source or is_preview:
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


@pytest.mark.parametrize("page_name, l2_module", [
    ("exp", "services.v2_tables.exp_universe"),     # 2026-10-13 新增
])
def test_正式入口確實import了source與page_而page沒有import_source_各頁(page_name, l2_module):
    live = _ROOT / "ui_v2" / f"app_{page_name}_live.py"
    got = imports_of(ast.parse(live.read_text(encoding="utf-8")), "ui_v2")
    assert f"ui_v2.{page_name}.source" in got and f"ui_v2.{page_name}.page" in got
    page = _ROOT / "ui_v2" / page_name / "page.py"
    got = imports_of(ast.parse(page.read_text(encoding="utf-8")), f"ui_v2.{page_name}")
    assert f"ui_v2.{page_name}.source" not in got
    src = _ROOT / "ui_v2" / page_name / "source.py"
    got = imports_of(ast.parse(src.read_text(encoding="utf-8")), f"ui_v2.{page_name}")
    assert l2_module in got


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
    # ~~("ui_v2/exp/source.py", …)~~ → 2026-10-13 exp 已登記白名單；改用一個不存在的頁名，驗同一件事。
    ("ui_v2/zzz/source.py", "from __future__ import annotations"),      # 新 source 沒登記白名單
    ("ui_v2/zzz/source.py", "from services.v2_tables import masking"),
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
    # 2026-10-12 第 (8) 條：預覽入口開的口子只有「四頁的 source」，其餘照擋。
    # ~~("ui_v2/app_preview.py", "from ui_v2.exp import source"),  # 標的探索沒有真資料版~~
    # → 2026-10-13 標的探索接上正式模式（狀態更新，不是漏刪）；口子仍只認列名的五頁，改用不存在的頁名驗。
    ("ui_v2/app_preview.py", "from ui_v2.zzz import source"),
    ("ui_v2/exp/source.py", "from . import fixtures"),                  # 新 source 照樣不得碰 fixtures
    ("ui_v2/app_exp_live.py", "from ui_v2.exp import fixtures"),
    ("ui_v2/exp/page.py", "from . import source"),                      # page 不得 import source
    # ~~("ui_v2/exp/source.py", "from services.v2_tables import nav_dividend")~~ → 2026-10-14 C2 接線後 nav_dividend 已登記白名單
    # （有意識的更正，不是漏刪）；改用 exp 仍未登記的 L2 模組驗同一件事。
    ("ui_v2/exp/source.py", "from services.v2_tables import alo_holdings"),  # 白名單外的 L2 模組
    ("ui_v2/app_preview.py", "from ui_v2.mkt import fixtures"),         # 正式路徑不得碰 fixtures
    ("ui_v2/app_preview.py", "from ui_v2.exp import fixtures"),         # 示意資料也只能經 page 進來
    ("ui_v2/app_preview.py", "import ui_v2.hld.fixtures"),
    ("ui_v2/app_preview.py", "from ui_v2 import app_mkt_live"),         # 不得 import 進入點
    ("ui_v2/app_preview.py", "from services.v2_tables import masking"),  # 只有 source.py 可以碰 L2
    ("ui_v2/app_preview.py", "import json"),                            # 逐檔白名單外
    ("ui_v2/app_preview.py", "import requests"),
    ("ui_v2/app_preview_v2.py", "from ui_v2.mkt import source"),        # 口子只認那一個檔名
    ("ui_v2/app_mkt.py", "from ui_v2.hld import source"),               # 示範入口照擋
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
    ("ui_v2/app_preview.py", "from ui_v2.mkt import page as mkt_page, source as mkt_source"),
    ("ui_v2/app_preview.py", "from ui_v2.exp import page as exp_page"),
    ("ui_v2/app_preview.py", "from ui_v2.exp import source as exp_source"),
    ("ui_v2/app_exp_live.py", "from ui_v2.exp import page, source"),
    ("ui_v2/exp/source.py", "from services.v2_tables import exp_universe, masking, settings_store"),
    ("ui_v2/exp/source.py", "from services.v2_tables import exp_nav, exp_profile, fund_keys, nav_dividend"),
])
def test_負控_合規寫法不誤報(rel, code):
    assert _check(rel, code) == [], (rel, code)
