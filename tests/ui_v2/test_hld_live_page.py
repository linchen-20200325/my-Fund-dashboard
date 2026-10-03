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
    kw = {
        "direct_policy_id": "DIRECT",
        # S5：L2 `provenance` 形狀；全部即時取回（新鮮度另有專測，見檔尾）。
        "nav_provenance": {
            row["fund_code"]: {"cache_fallback": False, "stale": None}
            for row in args["dataset"]["nav"]
        },
    }
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


# ───────────────────────── S5：舊淨值的新鮮度標示（裁示 1-A＋1-C） ─────────────────────────
# 假資料每一檔最後一筆 `nav_date` 是 2026-09-18；`days` 是台灣今天減它。AAAA 走預存那一支。


def _fresh_app(days, live_mode, name):
    from datetime import date, timedelta

    from ui_v2.hld import fixtures, live, logic, page

    args = fixtures.scenario(name)
    for holding in args["dataset"]["holding"]:
        if holding["policy_id"] == "DIRECT":
            holding["policy_id"] = "P-001"
    if live_mode:
        prov = {
            row["fund_code"]: {"cache_fallback": row["fund_code"] == "AAAA", "stale": None}
            for row in args["dataset"]["nav"]
        }
        model = live.build_live_model(
            **args, today=date(2026, 9, 18) + timedelta(days=days), direct_policy_id="DIRECT", nav_provenance=prov
        )
    else:
        model = logic.build_page_model(**args)
    for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-6", "HLD-8"):
        page._RENDERERS[code](logic.find_block(model, code))


def _run_fresh(days, live_mode=True, name="full"):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_fresh_app, args=(days, live_mode, name), default_timeout=60)
    at.run()
    assert not at.exception
    return "\n".join(m.value for m in at.markdown)


def _badge(text, tone):
    return f'<span class="hld-badge" style="--hld-tone:{theme.tone_hex(tone)}">{text}</span>'


@pytest.mark.parametrize("days, text, tone", [(0, "當日", "中性"), (10, "延遲 10 日", "中性"), (11, "延遲 11 日", "黃")])
def test_S5_徽章畫在HLD2_HLD3標頭旁_HLD8每一列_HLD6分組標頭(days, text, tone):
    md = _run_fresh(days)
    badge = _badge(text, tone)
    # HLD-2／HLD-3 每檔標頭旁（3 檔 × 2 塊）＋ HLD-8 每一列（3）＋ HLD-6 分組標頭（3）
    assert md.count(badge) == 12
    assert md.count(f'<div class="hld-fh">基金 A（示意） · 幣別 USD {badge}</div>') == 2   # HLD-2、HLD-3
    assert md.count(f"<td>基金 A（示意） {badge}") == 1                                   # HLD-8 基金名那一格
    assert md.count(f'<tr><td colspan="6"><b>AAAA</b> {badge}</td></tr>') == 1


@pytest.mark.parametrize("days, text, tone", [
    (11, "⚠ 淨值取自預存序列，不是本次取得；最近一筆 2026-09-18，已超過 10 日", "黃"),
    (10, "淨值取自預存序列，不是本次取得；最近一筆 2026-09-18", "中性"),
])
def test_S5_副標畫在HLD2_HLD3_HLD8_HLD5_HLD6_只有預存那一檔(days, text, tone):
    md = _run_fresh(days)
    color = theme.tone_hex(tone)
    note = f'style="color:{color}">{text}</div>'
    # HLD-2、HLD-3、HLD-8（儲存格內）、HLD-6（分組標頭下一列）各 1；HLD-5 該檔展開標頭下 1
    assert md.count(note) == 5
    assert f'<div class="hld-line" style="color:{color}">{text}</div>' in md          # HLD-5
    assert f'<tr><td colspan="6"><div class="hld-note" style="color:{color}">{text}</div></td></tr>' in md  # HLD-6


@pytest.mark.parametrize("days, tone", [(10, "中性"), (11, "黃")])
def test_S5_HLD1卡尾第3句排在既有卡尾之後(days, tone):
    md = _run_fresh(days, name="srcmiss")   # 這一組卡尾有「未列入的檔不進上表…」那兩行
    tail = f'<div class="hld-note" style="color:{theme.tone_hex(tone)}">本卡所列的檔中，1 檔的淨值取自預存序列，逐檔見 HLD-6</div>'
    assert tail in md
    assert md.index("未列入的檔不進上表") < md.index(tail)


def test_S5_示範模式_一個新鮮度字樣都不畫():
    md = _run_fresh(30, live_mode=False)
    for word in ("延遲", "當日", "預存序列", "colspan"):
        assert word not in md
