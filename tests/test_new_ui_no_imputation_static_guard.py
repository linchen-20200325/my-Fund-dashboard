# -*- coding: utf-8 -*-
"""New UI 資料路徑「缺值不得被補出一個值」的靜態守衛（Missing ≠ 0／不 ffill；`CLAUDE.md` §1、BL-0441／`DEC-2026-10-24-08`）。

缺口來源：`docs/evidence/quality_batch1_delta_2026_11_13.md` Δ3-11／G-1 —— Batch 1 以 `git grep` 確認 New UI 路徑
（`services/v2_tables`、`services/v2_domain`、`ui_v2`、`ui_v3`、`shared/ui_semantics`、`shared/active_sheet.py`）**目前** 0 處補值，
但那只是一次性的字面 grep，**沒有任何測試**在有人日後加上 `fillna(0)`／`ffill()`／`interpolate()` 時轉紅。
既有的 `test_nav_部分NaN_只略過那幾筆_不ffill`、`test_缺段_None保留為null…` 等是**行為**測試，只守它們各自的情境；
本檔是跨層（L2 表 → L2 領域 → ui_v2／ui_v3 → shared 呈現規則）的**結構**守衛。

規則（純 AST；不用字串 grep，所以註解／docstring 提到這些字不會誤報）：
  母體內任何 .py 不得 (1) 呼叫或引用 `fillna`／`ffill`／`bfill`／`interpolate`／`nan_to_num`（屬性、名稱、`from … import`），
  (2) 帶 `fill_value=` 關鍵字，(3) 帶 `method="ffill"|"bfill"|"pad"|"backfill"|"nearest"` 關鍵字。
⛔ 只守「顯式補值 API」。`or 0`／`.get(k, 0)` 計數器等太雜、不在本檔範圍；這不是「New UI 沒有任何補值」的證明。
⛔ 若日後真的需要顯式、有 log 且帶旗標的補值（`CLAUDE.md` §1 允許的形態），那屬資料語意決定：請走 Decision Gate 後再改本守衛，
   不得為了讓測試變綠而直接刪規則或加白名單。

本機執行（conftest 會 import 本環境可能沒有的套件時）：``pytest tests/test_new_ui_no_imputation_static_guard.py -q --noconftest -p no:cacheprovider``
"""

from __future__ import annotations

import ast
import pathlib

import pytest

_ROOT = pathlib.Path(__file__).resolve().parents[1]

#: 母體（目錄會遞迴；單檔直接列）。目錄或檔案被改名／搬走 ⇒ `test_母體_每個根都真的存在且有檔案` 先紅，提醒同步更新。
SCAN_DIRS = ("services/v2_tables", "services/v2_domain", "ui_v2", "ui_v3", "shared/ui_semantics")
SCAN_FILES = ("shared/active_sheet.py",)

IMPUTE_NAMES = frozenset({"fillna", "ffill", "bfill", "interpolate", "nan_to_num"})
IMPUTE_METHODS = frozenset({"ffill", "bfill", "pad", "backfill", "nearest"})


def population(root: pathlib.Path = _ROOT) -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for d in SCAN_DIRS:
        files += sorted((root / d).rglob("*.py"))
    for f in SCAN_FILES:
        if (root / f).is_file():
            files.append(root / f)
    return files


def violations_in_source(source: str, label: str = "<mem>") -> list[str]:
    out: list[str] = []
    for node in ast.walk(ast.parse(source)):
        line = getattr(node, "lineno", 0)
        if isinstance(node, ast.Attribute) and node.attr in IMPUTE_NAMES:
            out.append(f"{label}:{line} 引用 .{node.attr}")
        elif isinstance(node, ast.Name) and node.id in IMPUTE_NAMES:
            out.append(f"{label}:{line} 引用 {node.id}")
        elif isinstance(node, ast.ImportFrom):
            out += [f"{label}:{line} import {a.name}" for a in node.names if a.name in IMPUTE_NAMES]
        elif isinstance(node, ast.keyword):
            if node.arg == "fill_value":
                out.append(f"{label}:{getattr(node.value, 'lineno', line)} fill_value= 關鍵字")
            elif (node.arg == "method" and isinstance(node.value, ast.Constant)
                  and node.value.value in IMPUTE_METHODS):
                out.append(f"{label}:{getattr(node.value, 'lineno', line)} method={node.value.value!r}")
    return out


def scan(root: pathlib.Path = _ROOT) -> list[str]:
    hits: list[str] = []
    for path in population(root):
        hits += violations_in_source(path.read_text(encoding="utf-8"), path.relative_to(root).as_posix())
    return hits


# ═══════════════════════ 主守衛：真實樹 ═══════════════════════


def test_母體_每個根都真的存在且有檔案():
    for d in SCAN_DIRS:
        assert list((_ROOT / d).rglob("*.py")), f"{d} 不存在或沒有 .py —— 目錄改名了？請同步更新 SCAN_DIRS"
    for f in SCAN_FILES:
        assert (_ROOT / f).is_file(), f"{f} 不存在 —— 改名了？請同步更新 SCAN_FILES"


def test_母體_夠大_防空掃():
    files = population()
    assert len(files) >= 100, len(files)
    rels = {p.relative_to(_ROOT).as_posix() for p in files}
    assert "services/v2_tables/nav_dividend.py" in rels
    assert "shared/active_sheet.py" in rels
    assert any(r.startswith("ui_v3/") for r in rels) and any(r.startswith("ui_v2/") for r in rels)


def test_New_UI_路徑沒有顯式補值API_缺值不補0不ffill():
    hits = scan()
    assert hits == [], "New UI 路徑出現補值 API（CLAUDE.md §1／BL-0441；需資料語意決定，不得自行加）：\n" + "\n".join(hits)


# ═══════════════════════ 負向對照：掃描器真的會抓到各種寫法 ═══════════════════════


@pytest.mark.parametrize("src", [
    "x = df.fillna(0)",
    "x = s.ffill()",
    "x = s.bfill(limit=1)",
    "x = s.interpolate()",
    "import numpy as np\nx = np.nan_to_num(a)",
    "from numpy import nan_to_num\n",
    "f = pd.Series.fillna",
    "x = a.reindex(idx, fill_value=0)",
    "x = a.add(b, fill_value=0)",
    "x = s.reindex(idx, method='ffill')",
    "x = s.reindex(idx, method=\"nearest\")",
    "y = fillna(x)",
])
def test_掃描器_抓得到各種補值寫法(src):
    assert violations_in_source(src), src


@pytest.mark.parametrize("src", [
    "# df.fillna(0) 不可以\nx = 1",
    '"""說明：不得 ffill、不得 fillna(0)、不得 interpolate"""\nx = 1',
    "msg = 'fill_value 不可為 0'\nx = 1",
    "ALLOWED = {'gap_policy': 'break'}",            # 字串常數不算（驗證用的詞彙表可以出現這些詞）
    "x = s.dropna()",                                # 丟掉缺值不是補值
    "x = a.get(k)",
    "x = requests_like(method='GET')",
    "x = s.reindex(idx)",                            # 單純 reindex 產生 NaN，不是補值
])
def test_掃描器_不誤報_註解_docstring_字串_dropna_一般method(src):
    assert violations_in_source(src) == [], src


def test_掃描器_回報檔案與行號():
    hits = violations_in_source("a = 1\nb = c.fillna(0)\n", "services/v2_tables/x.py")
    assert hits == ["services/v2_tables/x.py:2 引用 .fillna"]


def test_掃描_對暫存副本植入補值_會抓到(tmp_path):
    """端到端：複製一小份母體檔案結構到暫存目錄，植入違規，確認 `scan(root)` 報出來（不寫真實樹）。"""
    for d in SCAN_DIRS:
        (tmp_path / d).mkdir(parents=True)
        (tmp_path / d / "ok.py").write_text("x = 1\n", encoding="utf-8")
    (tmp_path / "shared").mkdir(exist_ok=True)
    (tmp_path / "shared/active_sheet.py").write_text("x = 1\n", encoding="utf-8")
    assert scan(tmp_path) == []
    (tmp_path / "ui_v3" / "bad.py").write_text("def f(s):\n    return s.fillna(0)\n", encoding="utf-8")
    assert scan(tmp_path) == ["ui_v3/bad.py:2 引用 .fillna"]
