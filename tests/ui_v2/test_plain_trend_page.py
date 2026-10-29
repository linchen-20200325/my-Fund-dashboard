# -*- coding: utf-8 -*-
"""去工程化守衛的射程補強：🌍 市場與趨勢的「市場趨勢」區段（BL-0525 Batch A；T8；slow lane）。

原本 `_plain_scan.SCRIPTS["mkt"]` 的五個情境都沒有餵 `market_view`，所以 `test_plain_page.py` 的「一般畫面沒有工程字樣」
**掃不到**市場趨勢區段（五張圖卡與 Missing 卡）的字；日後 Batch C 把圖卡下方的說明搬進 detail 展開區時，也沒有守衛會替新容器把關。
本檔用 `_plain_scan.MKT_TREND` 情境（合成序列、不打網路）補上：

1. 正控：畫面上真的有市場趨勢區段（圖卡標題在畫面上）—— 證明掃得到，不是空掃。
2. 同一組 PATTERNS（塊代號、層字樣、原始鍵名、秘密鍵名、例外型別名、實作字樣）對一般畫面（含預設收合展開區裡的字）0 命中。
"""

from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _plain_scan as SCAN  # noqa: E402
from test_plain_page import PATTERNS, _hits  # noqa: E402

from ui_v2.mkt import market_section  # noqa: E402


def _run():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_string(SCAN.MKT_TREND, default_timeout=90)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_正控_市場趨勢區段真的在畫面上_掃描不是空掃():
    texts = " ".join(SCAN.screen_texts(_run()))
    assert market_section.LABELS["vix"] in texts, "市場趨勢區段沒畫出來 —— 情境腳本失效"


def test_市場趨勢區段_一般畫面沒有工程字樣():
    texts = SCAN.screen_texts(_run())
    assert len(texts) >= 10
    assert _hits(texts, PATTERNS) == []
