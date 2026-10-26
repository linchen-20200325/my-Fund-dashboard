# -*- coding: utf-8 -*-
"""新 B UI 第一階段唯讀：五頁正式模式畫面上沒有寫入控制（slow lane；需要 streamlit）。

依據：客戶 2026-10-26 正式裁示第 6、7 節；`DEC-2026-10-25-04` J-6、2026-10-26 J-14 補記（`SET-4` 不出現）。
用 `tests/ui_v2/_plain_scan.py` 的五頁正式模式腳本（真 L2 ＋ 假上游、不打網路；與既有 `_page` 測試同一套腳本），
**不**打開休眠寫入路徑（`_dormant_writes`），驗 production 預設：
- 沒有任何寫 `user_setting` 的按鈕（標籤「存檔」，以及 EXP-5 那一枚「加入觀察清單」—— 44 第五節屬存檔類）；
- 設定與診斷頁沒有「參數編輯」（`SET-4`）展開區，`SET-3`（規則參數卡）照舊在；
- 畫面上沒有叫人按存檔的句子（`ui_v2/readonly.py::PHASE1_TEXT_REWRITES` 那幾種）。
模型層與 AST 的守衛見 `tests/ui_v2/test_readonly_write_surface_guard.py`（fast）。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
for _p in (_HERE, _HERE.parents[1]):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402

from ui_v2 import readonly  # noqa: E402

_WRITE_LABELS = ("存檔", "加入觀察清單")
_CASES = [(page, name) for page in ("mkt", "hld", "alo", "exp", "set") for name in SCAN.SCRIPTS[page]]


def _run(page, name):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCAN.SCRIPTS[page][name], default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_production_default_is_read_only():
    assert readonly.WRITE_CONTROLS_ENABLED is False


@pytest.mark.parametrize("page, name", _CASES)
def test_live_page_has_no_write_controls(page, name):
    at = _run(page, name)
    labels = [b.label for b in at.button]
    assert not [label for label in labels if label in _WRITE_LABELS], labels
    texts = " ".join(" ".join(t.split()) for t in SCAN.screen_texts(at))
    for old, _new in readonly.PHASE1_TEXT_REWRITES:
        assert old not in texts, old
    assert "請按「存檔」" not in texts


@pytest.mark.parametrize("name", list(SCAN.SCRIPTS["set"]))
def test_set_page_has_no_set4_block(name):
    at = _run("set", name)
    titles = [e.label for e in at.expander]
    assert not [t for t in titles if t.startswith("參數編輯")], titles
    assert [t for t in titles if t.startswith("規則參數卡")], titles   # 目前設定值照舊唯讀呈現（SET-3）
