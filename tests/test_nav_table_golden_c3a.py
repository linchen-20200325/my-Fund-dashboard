# -*- coding: utf-8 -*-
"""C3a：`build_nav_table`（`with_dividends=False`；alo 與設定頁走這條）的輸出**逐位元組**不變（fast lane；不打網路）。

證明方式：`tests/fixtures/nav_table_golden_before_c3a.json` 是**改動前**（乾淨的 `origin/main` `4eda84d`，以
`git archive` 解到暫存目錄、只放進 `tests/_nav_dividend_golden_c3a.py` 與 `tests/_nav_table_golden_c3a.py` 兩支錄製腳本）
的程式碼對 `tests/_nav_table_golden_c3a.py` 情境（`chain:*`、`res:*`，共 37 個）跑出來的 `build_nav_table` 整個回傳值，
以 `dumps` 穩定序列化後存檔。改動後再跑一次，序列化結果必須與檔案逐位元組相同。

⚠️ 黃金檔**不得**以改動後的程式重產（那會把要證明的東西變成循環論證）。
"""

from __future__ import annotations

import json
import pathlib

import pytest

import _nav_dividend_golden_c3a as G
import _nav_table_golden_c3a as T

_GOLDEN = pathlib.Path(__file__).resolve().parent / "fixtures" / "nav_table_golden_before_c3a.json"
_NAMES = T.case_names()


def test_淨值單表黃金檔逐位元組相同():
    now = G.dumps({name: T.run_case(name) for name in _NAMES})
    assert now.encode("utf-8") == _GOLDEN.read_bytes()


@pytest.mark.parametrize("name", _NAMES)
def test_淨值單表逐情境序列化相同(name):
    """整份比對失敗時，逐情境指出是哪一個變了。"""
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))[name]
    assert G.dumps(T.run_case(name)) == G.dumps(golden)


def test_淨值單表黃金檔情境與矩陣一致_防空掃():
    golden = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    assert sorted(golden) == _NAMES
    assert len(_NAMES) == 37
    assert {n.split(":", 1)[0] for n in _NAMES} == {"chain", "res"}
    # 不是空殼：真的有寫出列、也有扣下的檔，出處只有 hld 的持倉手填
    assert sum(len(v["rows"]) for v in golden.values()) > 0
    assert any(v["withheld"] for v in golden.values())
    assert {p.get("ccy_source") for v in golden.values() for p in v["provenance"].values()} <= {
        None, "holding_user_input"}


def test_淨值單表的nav與兩表版的nav一致_同一組情境():
    """`build_nav_dividend_tables` 的 docstring 宣稱其 `nav` 與 `build_nav_table` 逐鍵相同；在兩份黃金檔共有的情境上核對。"""
    both = json.loads((_GOLDEN.parent / "nav_dividend_golden_before_c3a.json").read_text(encoding="utf-8"))
    table = json.loads(_GOLDEN.read_text(encoding="utf-8"))
    shared = sorted(set(both) & set(table))
    assert shared == _NAMES
    for name in shared:
        assert both[name]["nav"] == table[name], name
