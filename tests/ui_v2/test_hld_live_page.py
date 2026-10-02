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


def _app(with_direct, empty):
    from datetime import date

    from ui_v2.hld import fixtures, live, logic, page

    args = fixtures.scenario("full")
    # 正式模式拿到 DIRECT 持倉會 raise（S4 第二輪 M2）：假資料裡掛 DIRECT 的持倉改掛既有保單。
    for holding in args["dataset"]["holding"]:
        if holding["policy_id"] == "DIRECT":
            holding["policy_id"] = "P-001"
    if empty:
        args["dataset"]["holding"] = []
    kw = {"direct_policy_id": "DIRECT"}
    if with_direct:
        kw.update(
            direct=[
                {"source": "_保單資料", "tab": "_保單資料", "row": 7},
                {"source": "保單分頁", "tab": "DIRECT", "row": 3},
                {"source": "保單分頁", "tab": "DIRECT", "row": 5},
            ],
            policy_tab_source="保單分頁",
            direct_sources={"保單分頁", "_保單資料", "_持倉補充"},
        )
    model = live.build_live_model(**args, today=date(2026, 10, 2), **kw)
    page._render_hld5(logic.find_block(model, "HLD-5"))


def _run(with_direct, empty=False):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_app, args=(with_direct, empty), default_timeout=60)
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


def test_持倉全空_HLD5標題只剩筆數_卡尾照畫():
    at = _run(True, empty=True)
    md = _markdown(at)
    assert at.expander[0].label.endswith("—　DIRECT 2 筆未列入")
    assert not [v for v in md + [at.expander[0].label] if "尚未建立任何持倉" in v]
    assert md[-3].endswith(">⚠ DIRECT 列暫不支援，該筆不計入體檢（2 筆）</div>")


def test_示範常數與L2一致():
    """`_app` 裡寫死的三個字面（script 跑在隔離環境、拿不到模組常數）要與 L1／L2 原始檔一致。"""
    import ast

    def const(rel, name):
        for node in ast.parse((_ROOT / rel).read_text(encoding="utf-8")).body:
            if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == name for t in node.targets):
                return ast.literal_eval(node.value)
        raise AssertionError(name)

    l1 = "repositories/policy_supplement_repository.py"
    assert const("services/v2_tables/contract.py", "DIRECT_POLICY_ID") == "DIRECT"
    assert const(l1, "POLICY_TAB_SOURCE") == "保單分頁"
    assert {const(l1, "TAB_POLICY_PROFILE"), const(l1, "TAB_HOLDING_SUPPLEMENT")} == {"_保單資料", "_持倉補充"}
