"""2026-10-23 客戶裁示 1B(PR1b)—— UI 層只准讀 SSOT,不准自組吃本金 / 配息率輸入。

守三件事(全部 `ui/**/*.py`,`tests/` 與 `ui_v2/` 不在射程):
  1. **不得 import** `dividend_safety`(唯一合法 caller 是 L2 的
     `check_eating_principal_1y_mk`)、`classify_eating_principal`(純核心,UI 不該自己判)、
     `compute_1y_total_return_mk_simple`(嚴格單利舊算法,已無 production caller)。
     走 AST(ImportFrom / Import / 屬性存取),註解與 docstring 裡提到名字不算。
  2. **不得把 `moneydj_div_yield`(MoneyDJ wb05 官方年化配息率)當配息率的值**:
     年化配息率唯一算法 = 近 12 個月實際配息合計 ÷ 最新淨值(`_resolve_adr_with_fallback` /
     `metrics.annual_div_rate`,同值);官方值只作對帳 / 診斷。
     允許的例外必須在**同一行或上一行**標 `# ssot-reconcile-only`(白名單標記),
     逐處可被 grep 稽核;純註解行與 docstring / 獨立字串常數(AST `Expr(Constant[str])`)不算命中。
  3. 突變驗證(由人手跑,不在本檔自動化):在任一 ui 檔加回
     `from services.portfolio_service import dividend_safety` → 本檔第 1 條必須轉紅。

⚠️ **射程(據實寫明,不要把本檔讀成「UI 已全面 SSOT 化」的證明)**:
  · 擋的是 **import 名**(第 1 條)與 **wb05 鍵字串**(第 2 條)。
  · **不擋**直讀 `metrics.annual_div_rate` / `metrics.ret_1y` / `perf["1Y"]` 當值,
    也**不擋** UI 自己 inline `tr < adr` 判吃本金 —— 那些要靠逐檔讀碼(2026-10-23 稽核 M2
    就是這樣在 `tab1_macro_inflection` / `tab1_macro_longterm` 抓到的,本守衛當時全綠)。
    `annual_div_rate` 與 SSOT 同值、`ret_1y` 另有純淨值用途,字串掃描分不出「當配息率 / 當含息」
    與「當純淨值變化」,硬擋會誤殺;要擋得先把那兩個鍵的讀法分流,屬另案。
  · 動態 `getattr` / 字串組名不在射程。

為什麼要有這張守衛:2026-10-23 之前 UI 共有 7 處自己餵 tr1y / adr 進 `dividend_safety`、
10+ 處直接拿 wb05 當配息率 —— 同一檔基金在不同分頁拿到不同燈號(§2.1 SSOT)。
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
UI_DIR = ROOT / "ui"

#: UI 層不得 import 的名字(任一 alias 都算)
_BANNED_NAMES = frozenset({
    "dividend_safety",
    "classify_eating_principal",
    "compute_1y_total_return_mk_simple",
})

#: 白名單標記:同一行或上一行帶它,才允許出現 `moneydj_div_yield`
_WHITELIST_MARK = "# ssot-reconcile-only"

_RAW_KEY = "moneydj_div_yield"


def _ui_files() -> list[Path]:
    return sorted(p for p in UI_DIR.rglob("*.py") if p.is_file())


def _banned_imports(path: Path) -> list[tuple[int, str]]:
    """回 [(lineno, 名字)]:ImportFrom / Import / `<x>.<banned>` 屬性存取。"""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in _BANNED_NAMES:
                    hits.append((node.lineno, alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                _last = alias.name.rsplit(".", 1)[-1]
                if _last in _BANNED_NAMES:
                    hits.append((node.lineno, alias.name))
        elif isinstance(node, ast.Attribute) and node.attr in _BANNED_NAMES:
            # `services.portfolio_service.dividend_safety(...)` 這種繞過 ImportFrom 的寫法
            hits.append((node.lineno, node.attr))
    return hits


def _docstring_lines(src: str, path: Path) -> set[int]:
    """docstring / 獨立字串常數(`Expr(Constant[str])`)佔的行號(1-based),掃描時跳過。"""
    out: set[int] = set()
    try:
        tree = ast.parse(src, filename=str(path))
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
                and isinstance(node.value.value, str)):
            out.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return out


def _raw_key_hits(path: Path) -> list[tuple[int, str]]:
    """回未標白名單的 `moneydj_div_yield` 命中 [(lineno, line)]。

    純註解行與 docstring 行不算;同一行或上一行帶 `# ssot-reconcile-only` 的放行。
    """
    src = path.read_text(encoding="utf-8")
    lines = src.splitlines()
    skip = _docstring_lines(src, path)
    hits: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        if _RAW_KEY not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("#") or (i + 1) in skip:
            continue
        prev = lines[i - 1] if i > 0 else ""
        if _WHITELIST_MARK in line or _WHITELIST_MARK in prev:
            continue
        hits.append((i + 1, stripped))
    return hits


def test_ui_tree_is_not_empty():
    assert len(_ui_files()) > 10, "ui/ 掃不到檔案 → 守衛整個失效,先確認路徑"


@pytest.mark.parametrize("path", _ui_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_ui_does_not_import_eating_internals(path: Path):
    hits = _banned_imports(path)
    assert not hits, (
        f"{path.relative_to(ROOT)} 仍 import / 存取 {hits} —— 吃本金只准走 "
        "`services.health.dividend.check_eating_principal_1y_mk`(唯一判定);"
        "UI 自組輸入餵 dividend_safety 會讓同一檔在不同分頁拿到不同燈號。"
    )


@pytest.mark.parametrize("path", _ui_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_ui_does_not_take_wb05_as_dividend_rate(path: Path):
    hits = _raw_key_hits(path)
    assert not hits, (
        f"{path.relative_to(ROOT)} 直接讀 `{_RAW_KEY}` 而未標 `{_WHITELIST_MARK}`:{hits}\n"
        "年化配息率唯一算法 = 近 12 個月實際配息合計 ÷ 最新淨值"
        "(`_resolve_adr_with_fallback` / `metrics.annual_div_rate`);"
        "wb05 官方值只作對帳 / 診斷,要用請在同一行或上一行標白名單並說明用途。"
    )


def test_whitelist_mark_is_only_used_for_reconcile_or_transport():
    """白名單不是萬用通行證:每一處標記都要能 grep 到,且數量不該無聲膨脹。"""
    marked = []
    for p in _ui_files():
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
            if _WHITELIST_MARK in line:
                marked.append(f"{p.relative_to(ROOT)}:{i}")
    # 2026-10-23 PR1b 實測:Tab3 Raw dump(對帳)+ d_mode 的 meta 搬運(不當值)。
    # 新增白名單時請把理由寫在標記旁,並更新此上限 —— 這條會紅是刻意的。
    assert len(marked) <= 3, f"白名單標記數量超出預期:{marked}"


# ── 正向:守衛本身要抓得到(自我檢驗,不靠「跑過了」) ────────────────────────
def test_guard_catches_banned_import(tmp_path: Path):
    f = tmp_path / "x.py"
    f.write_text("from services.portfolio_service import dividend_safety as d\n", encoding="utf-8")
    assert _banned_imports(f) == [(1, "dividend_safety")]
    f.write_text("import services.portfolio_service as ps\nps.dividend_safety(1, 2)\n",
                 encoding="utf-8")
    assert [h[1] for h in _banned_imports(f)] == ["dividend_safety"]


def test_guard_catches_unmarked_raw_key_but_allows_marked(tmp_path: Path):
    f = tmp_path / "y.py"
    f.write_text(
        '"""模組 docstring 提到 moneydj_div_yield → 不算\n'
        '第二行也提到 moneydj_div_yield\n"""\n'
        "a = mj.get('moneydj_div_yield')\n"
        "# moneydj_div_yield 只在註解裡 → 不算\n"
        "b = mj.get('moneydj_div_yield')  # ssot-reconcile-only\n"
        "# ssot-reconcile-only\n"
        "c = mj.get('moneydj_div_yield')\n"
        "def g():\n"
        '    """函式 docstring 的 moneydj_div_yield 也不算"""\n'
        "    return mj.get('moneydj_div_yield')\n",
        encoding="utf-8")
    assert [h[0] for h in _raw_key_hits(f)] == [4, 11]
