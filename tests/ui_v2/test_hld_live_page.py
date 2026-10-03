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
    # S5 第二輪（紅隊建議 3）：日期整段包在不斷行的一段裡，字面不變。
    day = "2026-09-18"
    text = text.replace(day, f'<span style="white-space:nowrap">{day}</span>')
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


# ───────────────────────── S6a：上線前的呈現層清理 ─────────────────────────


def _bad_sync_app(raw):
    from datetime import date

    import streamlit as st

    from ui_v2.hld import fixtures, live, logic, page

    args = fixtures.scenario("full")
    for holding in args["dataset"]["holding"]:
        if holding["policy_id"] == "DIRECT":
            holding["policy_id"] = "P-001"
    target = args["dataset"]["holding"][0]
    target["last_synced_at"] = raw
    kw = {
        "direct_policy_id": "DIRECT",
        "nav_provenance": {
            row["fund_code"]: {"cache_fallback": False, "stale": None} for row in args["dataset"]["nav"]
        },
    }
    st.session_state[logic.HLD5_OPEN_KEY] = target["holding_id"]
    model = live.build_live_model(**args, today=date(2026, 10, 2), open_fund=target["holding_id"], **kw)
    page._render_hld5(logic.find_block(model, "HLD-5"))


def _run_bad_sync(raw):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_bad_sync_app, args=(raw,), default_timeout=60)
    at.run()
    assert not at.exception
    return "\n".join(m.value for m in at.markdown)


def test_S6a_最後核對日不合格那一格_印值節點的字_顏色照狀態():
    """S3 讓那一格變成值節點，`_render_hld5` 原本把它當字串 `_esc(dict)` 印出來。"""
    from ui_v2.hld import logic

    md = _run_bad_sync("2026/09/19")
    cell = f'<span>最後核對日（只記日期）</span><b style="color:{theme.tone_hex("紅")}">{logic.ERR_TEXT}</b>'
    assert cell in md
    # dict 的字樣一個都不能上畫面（`_esc(dict)` 會印出 `&#123;&#39;_value_node&#39;…`）。
    for leak in ("_value_node", "value_text", "reason_text", "&#123;"):
        assert leak not in md, leak


def test_S6a_最後核對日合格時_照舊印字串_不帶顏色():
    md = _run_bad_sync("2026-09-19")
    assert "<span>最後核對日（只記日期）</span><b>2026-09-19</b>" in md


def _demo_full_app():
    import streamlit as st

    from ui_v2.hld import page

    st.query_params["scenario"] = "full"
    page.render()


def test_S6a_展開鈕_沒展開時不帶提示_展開中的那一枚才帶():
    """提示「這一檔已經展開」原本無條件傳給 `help`，啟用中的鈕滑過去就讀到一句假話。示範模式同樣修。"""
    from streamlit.testing.v1 import AppTest

    from ui_v2.hld import fixtures, logic

    at = AppTest.from_function(_demo_full_app, default_timeout=60)
    at.run()
    assert not at.exception
    hids = [h["holding_id"] for h in fixtures.scenario("full")["dataset"]["holding"]]
    assert len(hids) >= 2
    for hid in hids:
        button = at.button(key=f"hld5_open_{hid}")
        assert button.disabled is False and not button.help, (hid, button.help)
    at.button(key=f"hld5_open_{hids[0]}").click().run()
    opened = at.button(key=f"hld5_open_{hids[0]}")
    assert opened.disabled is True and opened.help == logic.HLD5_OPEN_DISABLED_REASON
    for hid in hids[1:]:
        assert not at.button(key=f"hld5_open_{hid}").help, hid


def _render_app(live_mode):
    from ui_v2.hld import fixtures, logic, page

    if not live_mode:
        page.render()
        return

    def scrub(node):
        if isinstance(node, str):
            return node.replace(logic.HINT, "")
        if isinstance(node, dict):
            return {k: scrub(v) for k, v in node.items()}
        if isinstance(node, list):
            return [scrub(v) for v in node]
        return node

    dataset = scrub(fixtures.scenario("full")["dataset"])
    for holding in dataset["holding"]:
        if holding["policy_id"] == "DIRECT":
            holding["policy_id"] = "P-001"
    live_args = {
        "direct_policy_id": "DIRECT",
        "nav_provenance": {
            row["fund_code"]: {"cache_fallback": False, "stale": None} for row in dataset["nav"]
        },
    }
    page.render(load_live=lambda: {"dataset": dataset, "live_args": live_args})


def _run_render(live_mode):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_render_app, args=(live_mode,), default_timeout=60)
    at.run()
    assert not at.exception
    return [m.value for m in at.markdown]


def test_S6a_正式模式頁首副標只印提問句():
    from ui_v2.hld import fixtures, logic

    md = _run_render(True)
    answers = logic.build_page_model(**fixtures.scenario("full"))["answers"]
    assert [m for m in md if 'class="hld-sub"' in m] == [f'<div class="hld-sub">{answers}</div>']
    blob = "\n".join(md)
    for word in ("假資料", "示意", "情境 "):
        assert word not in blob, word


def test_S6a_示範模式頁首副標照舊():
    """正控：不傳 `load_live` 時副標與加這個參數之前逐字相同。"""
    from ui_v2.hld import fixtures, logic

    md = _run_render(False)
    answers = logic.build_page_model(**fixtures.scenario("full"))["answers"]
    expected = (
        f'<div class="hld-sub">{answers}　·　資料為假資料，每一個數字都帶「示意」二字　·　'
        f'情境 {fixtures.SCENARIO_LABELS["full"]}</div>'
    )
    assert [m for m in md if 'class="hld-sub"' in m] == [expected]


# ───────────────────────── S6a 第三輪：「套用」真的生效（紅隊 M1） ─────────────────────────
# `44` HLD-4：「套用」只讀欄位的當下值、重算 HLD-1、HLD-2、HLD-3、HLD-5、HLD-7、HLD-8 六塊，
# 不寫任何資料表、不改欄位的內容。原本 `page.render` 從來沒把欄位值交給 logic，按了什麼都不變。

_NEW_START = "2026-06-01"
_SAVED_END = "2026-09-19"   # 假資料 `full` 存過的迄日


def _apply_app(live_mode):
    from ui_v2.hld import fixtures, logic, page

    if not live_mode:
        import streamlit as st

        st.query_params["scenario"] = "full"
        page.render()
        return

    def scrub(node):
        if isinstance(node, str):
            return node.replace(logic.HINT, "")
        if isinstance(node, dict):
            return {k: scrub(v) for k, v in node.items()}
        if isinstance(node, list):
            return [scrub(v) for v in node]
        return node

    dataset = scrub(fixtures.scenario("full")["dataset"])
    for holding in dataset["holding"]:
        if holding["policy_id"] == "DIRECT":
            holding["policy_id"] = "P-001"
    live_args = {
        "direct_policy_id": "DIRECT",
        "today": __import__("datetime").date(2026, 10, 2),
        "nav_provenance": {
            row["fund_code"]: {"cache_fallback": False, "stale": None} for row in dataset["nav"]
        },
    }
    page.render(load_live=lambda: {"dataset": dataset, "live_args": live_args})


def _apply_run(live_mode):
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_function(_apply_app, args=(live_mode,), default_timeout=60)
    at.run()
    assert not at.exception
    return at


def _block_blob(at, code) -> str:
    """一塊在畫面上的全部文字。層 2 的卡是一整段 markdown；層 3、層 4 是一枚 expander（含標題列）。"""
    for m in at.markdown:
        if f'<span class="hld-card-code">{code}</span>' in m.value:
            return m.value
    for exp in at.expander:
        if exp.label.startswith(f"{code}　"):
            parts = [exp.label] + [m.value for m in exp.markdown] + [c.value for c in exp.caption]
            return "\n".join(parts)
    raise AssertionError(f"畫面上找不到 {code}")


def _models(live_mode):
    """沒按「套用」與以新區間按過「套用」的兩份模型（同一支 logic 算的，當對照）。"""
    from datetime import date

    from ui_v2.hld import fixtures, live, logic

    args = fixtures.scenario("full")
    if live_mode:
        for holding in args["dataset"]["holding"]:
            if holding["policy_id"] == "DIRECT":
                holding["policy_id"] = "P-001"
        kw = {
            "direct_policy_id": "DIRECT",
            "today": date(2026, 10, 2),
            "nav_provenance": {
                row["fund_code"]: {"cache_fallback": False, "stale": None} for row in args["dataset"]["nav"]
            },
        }
        old = live.build_live_model(**args, **kw)
        new = live.build_live_model(**args, **kw, applied_window=(_NEW_START, _SAVED_END))
    else:
        old = logic.build_page_model(**args)
        new = logic.build_page_model(**args, applied_window=(_NEW_START, _SAVED_END))
    return old, new


def _diff_texts(old_block, new_block):
    from ui_v2.hld import logic

    a = set(logic.collect_ui_strings({"b": old_block}))
    b = set(logic.collect_ui_strings({"b": new_block}))
    return a - b, b - a


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a_套用_六塊跟著新區間重算_HLD6不變(live_mode):
    from ui_v2.hld import logic, page

    at = _apply_run(live_mode)
    before = {code: _block_blob(at, code) for code in ("HLD-1", "HLD-2", "HLD-3", "HLD-5", "HLD-6", "HLD-7", "HLD-8")}
    at.text_input(key="hld4_window_start").input(_NEW_START)
    apply_key = next(
        f"hld4_btn_{i}" for i, b in enumerate(logic.find_block(_models(live_mode)[0], "HLD-4")["buttons"])
        if b["_action_kind"] == "套用"
    )
    at.button(key=apply_key).click().run()
    assert not at.exception
    old, new = _models(live_mode)
    changed_any = []
    for code in logic.APPLY_RECALC_BLOCKS:
        gone, came = _diff_texts(logic.find_block(old, code), logic.find_block(new, code))
        blob = _block_blob(at, code)
        # 新區間算出來、舊區間沒有的字，畫面上都在；反過來，舊區間才有的字都不在。
        for text in came:
            assert page._esc(text) in blob, (code, text)
        for text in gone:
            assert page._esc(text) not in blob, (code, text)
        if came or gone:
            changed_any.append(code)
            assert blob != before[code], code
    # 驗的不是空集合：數字真的跟著區間動的那幾塊（HLD-5 的內容與區間無關，不會動）。
    assert {"HLD-2", "HLD-3", "HLD-7", "HLD-8"} <= set(changed_any), changed_any
    # 不在六塊之內的 HLD-6（原始序列）一字不動。
    assert _block_blob(at, "HLD-6") == before["HLD-6"]


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a_套用_不改欄位內容_改了沒按套用就不重算(live_mode):
    from ui_v2.hld import logic

    at = _apply_run(live_mode)
    before = _block_blob(at, "HLD-2")
    at.text_input(key="hld4_window_start").input(_NEW_START).run()
    assert not at.exception
    # 只改欄位、沒按「套用」：卡上的數字照舊（`44` HLD-4：重算只由「套用」觸發）。
    assert _block_blob(at, "HLD-2") == before
    apply_key = next(
        f"hld4_btn_{i}" for i, b in enumerate(logic.find_block(_models(live_mode)[0], "HLD-4")["buttons"])
        if b["_action_kind"] == "套用"
    )
    at.button(key=apply_key).click().run()
    assert at.text_input(key="hld4_window_start").value == _NEW_START
    assert at.text_input(key="hld4_window_end").value == _SAVED_END


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a_起迄日顛倒_套用照既有規則停用_卡上維持上一次套用的結果(live_mode):
    from ui_v2.hld import logic

    at = _apply_run(live_mode)
    hld4 = logic.find_block(_models(live_mode)[0], "HLD-4")
    apply_key = next(f"hld4_btn_{i}" for i, b in enumerate(hld4["buttons"]) if b["_action_kind"] == "套用")
    at.text_input(key="hld4_window_start").input(_NEW_START)
    at.button(key=apply_key).click().run()
    applied = _block_blob(at, "HLD-2")
    at.text_input(key="hld4_window_start").input("2026-12-31").run()
    assert not at.exception
    button = at.button(key=apply_key)
    assert button.disabled is True and button.help == logic.TEXT_BAD_RANGE
    assert _block_blob(at, "HLD-2") == applied
