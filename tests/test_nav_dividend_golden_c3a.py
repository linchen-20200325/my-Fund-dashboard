# -*- coding: utf-8 -*-
"""C3a（`nav_dividend` 多吃「meta 頁自報幣別」的純重構）：hld 路徑的輸出**逐位元組**不變（fast lane；不打網路）。

證明方式：`tests/fixtures/nav_dividend_golden_before_c3a.json` 是**改動前**（乾淨的 `origin/main` `4eda84d`）的程式碼
對 `tests/_nav_dividend_golden_c3a.py` 情境矩陣跑出來的結果（`build_nav_dividend_tables` 整個回傳值，以及幾個純函式的
回傳值），以 `dumps` 穩定序列化後存檔。改動後再跑一次，序列化結果必須與檔案逐位元組相同 —— **不拿掉任何鍵、
不放寬任何欄位**（與 A 鏈黃金檔「除新增鍵外逐欄相同」不同：本輪 hld 路徑一個鍵都不該多）。

⚠️ 黃金檔**不得**以改動後的程式重產（那會把要證明的東西變成循環論證）。
"""

from __future__ import annotations

import json
import pathlib

import pytest

import _nav_dividend_golden_c3a as G

_GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "nav_dividend_golden_before_c3a.json"
_NAMES = G.case_names()


def _golden_text() -> str:
    return _GOLDEN.read_text(encoding="utf-8")


def test_整份黃金檔逐位元組相同():
    now = G.dumps({name: G.run_case(name) for name in _NAMES})
    assert now.encode("utf-8") == _GOLDEN.read_bytes()


@pytest.mark.parametrize("name", _NAMES)
def test_逐情境序列化相同(name):
    """整份比對失敗時，逐情境指出是哪一個變了。"""
    golden = json.loads(_golden_text())[name]
    assert G.dumps(G.run_case(name)) == G.dumps(golden)


def test_黃金檔情境與矩陣一致_防空掃():
    golden = json.loads(_golden_text())
    assert sorted(golden) == _NAMES
    assert len(_NAMES) == 51
    kinds = {n.split(":", 1)[0] for n in _NAMES}
    assert kinds == {"chain", "res", "pure"}
