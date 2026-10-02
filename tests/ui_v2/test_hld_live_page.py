# -*- coding: utf-8 -*-
"""持倉體檢正式模式 HLD-5 卡尾的渲染測試（S4，裁示 3-B (ii)）。slow lane；需要 streamlit。

本頁正式入口（`ui_v2/app_hld_live.py`）是 S6 的工作，尚未建；這裡以 `AppTest.from_function`
直接呼叫 `page._render_hld5`，餵正式模式組出的 HLD-5 塊（展開區預設收合，AppTest 照樣收得到內容）。
"""

import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_ROOT))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

from ui_v2.hld import theme  # noqa: E402


def _app(with_direct):
    from datetime import date

    from ui_v2.hld import fixtures, live, logic, page

    kw = {}
    if with_direct:
        kw = {
            "direct": [
                {"source": "_保單資料", "tab": "_保單資料", "row": 7},
                {"source": "保單分頁", "tab": "DIRECT", "row": 3},
                {"source": "保單分頁", "tab": "DIRECT", "row": 5},
            ],
            "policy_tab_source": "保單分頁",
        }
    model = live.build_live_model(**fixtures.scenario("full"), today=date(2026, 10, 2), **kw)
    page._render_hld5(logic.find_block(model, "HLD-5"))


def _run(with_direct):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app, args=(with_direct,), default_timeout=60)
    at.run()
    assert not at.exception
    return at


def _markdown(at):
    return [m.value for m in at.markdown]


def test_卡尾黃字一行_逐筆位置灰字_排在逐檔清單之後():
    at = _run(True)
    md = _markdown(at)
    warn = f'<div class="hld-line" style="color:{theme.tone_hex("黃")}">⚠ DIRECT 列暫不支援，該筆不計入體檢（2 筆）</div>'
    gray3 = f'<div class="hld-line" style="color:{theme.tone_hex("灰")}">DIRECT 第 3 列</div>'
    gray5 = f'<div class="hld-line" style="color:{theme.tone_hex("灰")}">DIRECT 第 5 列</div>'
    assert md[-3:] == [warn, gray3, gray5]
    last_fund = max(i for i, v in enumerate(md) if 'class="hld-fh"' in v)
    assert md.index(warn) > last_fund
    assert at.expander[0].label.endswith(" · DIRECT 2 筆未列入")


def test_沒有DIRECT時_卡尾一行都不畫():
    md = _markdown(_run(False))
    assert not [v for v in md if "DIRECT" in v]
