# -*- coding: utf-8 -*-
"""資產配置正式頁：同鍵兩列而類別或幣別不同 → 畫既有錯誤呈現，不出現 Traceback（總管 2026-10-16 判定，必修；slow）。

`logic.aggregated_holdings` 對這兩種衝突 raise ValueError（bucket 為既有、ccy 為客戶 2026-10-16 裁示第 8 點新增）；
`page.render` 正式路徑接住，畫頁名、提問句與一行「⛔ 取數失敗：ValueError：<原文>」，其餘塊不畫。
"""

from __future__ import annotations

import copy
import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import test_alo_live_page as T  # noqa: E402  —— 沿用正式模式的合格資料

from ui_v2.alo import logic  # noqa: E402


def _run(dataset, mask=""):
    from streamlit.testing.v1 import AppTest

    script = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r})
from ui_v2.alo import page
page.render(load_live=lambda: {{"dataset": {dataset!r}, "notes": {{}}}}{mask})
"""
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    return at


@pytest.mark.parametrize("column, value", [("bucket", T._SAT), ("ccy", "USD")])
def test_同鍵兩列語意欄不同_畫既有錯誤呈現_沒有Traceback(column, value):
    dataset = copy.deepcopy(T._DATASET)
    first = dataset["holding"][0]
    dup = dict(first, holding_id=first["holding_id"][:-1] + "2")
    dup[column] = value
    assert dup[column] != first[column], "兩列沒有不同 —— 這一條會測錯東西"
    dataset["holding"].append(dup)
    at = _run(dataset)
    assert len(at.exception) == 0, [e.message for e in at.exception]
    md = "\n".join(m.value for m in at.markdown)
    assert "Traceback" not in md and not at.code
    assert logic.fetch_failed_text("ValueError：") in md
    assert f"兩列的 {column} 不同" in md
    assert logic.PAGE_TITLE in md and logic.PAGE_ANSWERS in md
    assert [b.label for b in at.button] == []


def test_正控_沒有衝突時照常畫整頁():
    at = _run(copy.deepcopy(T._DATASET))
    assert len(at.exception) == 0
    assert "取數失敗：ValueError" not in "\n".join(m.value for m in at.markdown)
    assert at.button, "整頁沒有任何按鈕 —— 上一條的「沒有按鈕」驗不到東西"


def test_錯誤行經過遮蔽函式_遮蔽失敗只印型別():
    """總管 2026-10-16 判定（PR #976 稽核後）：錯誤原文經 `mask_error`（正式入口傳 `source.mask_error`）才上畫面。"""
    dataset = copy.deepcopy(T._DATASET)
    first = dataset["holding"][0]
    dataset["holding"].append(dict(first, holding_id=first["holding_id"][:-1] + "2", ccy="USD"))
    pid = first["policy_id"]
    md = "\n".join(m.value for m in _run(dataset, f', mask_error=lambda s: s.replace({pid!r}, "‹已遮蔽›")').markdown)
    assert "‹已遮蔽›" in md and f"&#x27;{pid}&#x27;" not in md and f"'{pid}'" not in md
    at = _run(dataset, ", mask_error=lambda s: 1 / 0")
    assert len(at.exception) == 0
    md = "\n".join(m.value for m in at.markdown)
    assert logic.fetch_failed_text("ValueError") in md and "兩列的 ccy 不同" not in md
