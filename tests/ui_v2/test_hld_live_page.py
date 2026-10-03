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
    page.render(load_live=lambda: {"dataset": dataset, "live_args": live_args}, mask_error=str)


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
    page.render(load_live=lambda: {"dataset": dataset, "live_args": live_args}, mask_error=str)


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


def _shown_strings(node, skip=()) -> set:
    """塊裡會上畫面的字。底線開頭的鍵直接掛著的字串是機器用的（例如 `_fund_code`），不收；
    底線開頭的鍵底下若是清單或 dict（例如 `_rows`），裡面的列照樣會畫出來，照收。`skip`：這一塊不畫的鍵。"""
    out = set()
    if isinstance(node, str):
        out.add(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            if key in skip or (str(key).startswith("_") and not isinstance(value, (dict, list, tuple))):
                continue
            out |= _shown_strings(value)
    elif isinstance(node, (list, tuple)):
        for value in node:
            out |= _shown_strings(value)
    return out


def _diff_texts(old_block, new_block):
    # 層 2 的卡沒有收合列，`summary_text` 不上畫面。
    skip = ("summary_text",) if old_block.get("_layer") == 2 else ()
    a, b = _shown_strings(old_block, skip), _shown_strings(new_block, skip)
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


# ───────────────────────── S6a 第四輪 ─────────────────────────


def _apply_key(live_mode):
    from ui_v2.hld import logic

    hld4 = logic.find_block(_models(live_mode)[0], "HLD-4")
    return next(f"hld4_btn_{i}" for i, b in enumerate(hld4["buttons"]) if b["_action_kind"] == "套用")


def _hld4_expander(at):
    return next(e for e in at.expander if e.label.startswith("HLD-4　"))


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a第四輪_門檻改了按套用_HLD1跟著新門檻重算(live_mode):
    """紅隊 M3／規格組必修 1：門檻列也接上「套用」。"""
    from datetime import date

    from ui_v2.hld import fixtures, live, logic, page

    at = _apply_run(live_mode)
    before = _block_blob(at, "HLD-1")
    at.text_input(key="hld4_rule_0_value").input("-1")
    button = at.button(key=_apply_key(live_mode))
    assert button.disabled is False
    button.click().run()
    assert not at.exception
    rules = [
        {"indicator": "最大回撤", "direction": "低於", "value": -1.0},
        {"indicator": "配息佔淨值比", "direction": "高於", "value": 6.0},
    ]
    args = fixtures.scenario("full")
    if live_mode:
        for holding in args["dataset"]["holding"]:
            if holding["policy_id"] == "DIRECT":
                holding["policy_id"] = "P-001"
        kw = {
            "direct_policy_id": "DIRECT", "today": date(2026, 10, 2),
            "nav_provenance": {r["fund_code"]: {"cache_fallback": False, "stale": None} for r in args["dataset"]["nav"]},
        }
        old, new = live.build_live_model(**args, **kw), live.build_live_model(**args, **kw, applied_rules=rules)
    else:
        old, new = logic.build_page_model(**args), logic.build_page_model(**args, applied_rules=rules)
    gone, came = _diff_texts(logic.find_block(old, "HLD-1"), logic.find_block(new, "HLD-1"))
    assert came, "新門檻算不出任何不同的字 —— 這一條會變成空掃"
    if live_mode:
        # 正式模式的畫面吃的是去掉「（示意）」的假資料（`_apply_app`），對照的模型這裡用原假資料，比對前同樣去掉。
        came = {t.replace(logic.HINT, "") for t in came}
        gone = {t.replace(logic.HINT, "") for t in gone}
    blob = _block_blob(at, "HLD-1")
    assert blob != before
    for text in came:
        assert page._esc(text) in blob, text
    for text in gone:
        assert page._esc(text) not in blob, text


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a第四輪_只改欄位不按套用_摘要與各塊都不動(live_mode):
    """紅隊 M1：只改日期（與門檻）、還沒按「套用」，HLD-4 摘要不能先變成新區間。"""
    at = _apply_run(live_mode)
    codes = ("HLD-1", "HLD-2", "HLD-3", "HLD-7", "HLD-8")
    before = {code: _block_blob(at, code) for code in codes}
    label = _hld4_expander(at).label
    at.text_input(key="hld4_window_start").input(_NEW_START).run()
    at.text_input(key="hld4_rule_0_value").input("-1").run()
    assert not at.exception
    assert _hld4_expander(at).label == label
    for code in codes:
        assert _block_blob(at, code) == before[code], code


@pytest.mark.parametrize("live_mode", [False, True])
@pytest.mark.parametrize("key, value", [
    ("hld4_window_start", "20260601"),     # 紅隊 M4：格式不是 YYYY-MM-DD
    ("hld4_window_start", "2026/06/01"),
    ("hld4_window_end", ""),               # 紅隊建議 2：只填一格
])
def test_S6a第四輪_區間格式錯或只填一格_套用停用_沿用既有原因句(live_mode, key, value):
    from ui_v2.hld import logic

    at = _apply_run(live_mode)
    # 先以合法的新區間套用一次，之後的壞輸入不得把它洗掉（也不得退回存過的區間）。
    at.text_input(key="hld4_window_start").input(_NEW_START)
    at.button(key=_apply_key(live_mode)).click().run()
    before = _block_blob(at, "HLD-2")
    at.text_input(key=key).input(value).run()
    button = at.button(key=_apply_key(live_mode))
    # ⚠️ AppTest 對停用的鈕 `.click()` 照樣觸發 `on_click`，所以先斷言停用（畫面上按不下去），
    #    再點一次確認回呼本身也不寫入（同一支 `logic.applied_from_inputs` 判定）。
    assert button.disabled is True and button.help == logic.TEXT_BAD_RANGE
    button.click().run()
    assert not at.exception
    assert _block_blob(at, "HLD-2") == before


@pytest.mark.parametrize("live_mode", [False, True])
@pytest.mark.parametrize("value", ["abc", "", "1e3", "9" * 400])
def test_S6a第四輪_門檻值既有規則處理不了_套用停用_沒有原因句(live_mode, value):
    """~~沒有既有原因句可用 —— 停用、原因留空（待補文案，已回報）~~ → S6a-2 第 4 項：停用，原因句是客戶
    2026-10-03 核准的「門檻列未填齊，或格式不符」（有意識的更正，不是漏刪）。函式名沿用，免得斷掉既有引用。
    `"9" * 400`：十進位寫法合格，但 `float()` 之後是 inf（第 4 項：拒收非有限數）。"""
    from ui_v2.hld import logic

    at = _apply_run(live_mode)
    at.text_input(key="hld4_rule_0_value").input("-1")
    at.button(key=_apply_key(live_mode)).click().run()
    before = _block_blob(at, "HLD-1")
    at.text_input(key="hld4_rule_0_value").input(value).run()
    button = at.button(key=_apply_key(live_mode))
    assert button.disabled is True and button.help == logic.TEXT_RULES_BAD
    button.click().run()
    assert not at.exception
    assert _block_blob(at, "HLD-1") == before


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a第四輪_按完套用HLD4以展開狀態重建(live_mode):
    """紅隊 M2：標題列一變 Streamlit 就重建這一枚 expander；按完「套用」要以展開狀態重建。"""
    at = _apply_run(live_mode)
    assert _hld4_expander(at).proto.expanded is False   # 首次渲染照舊收合
    at.text_input(key="hld4_window_start").input(_NEW_START).run()
    assert _hld4_expander(at).proto.expanded is True
    at.button(key=_apply_key(live_mode)).click().run()
    exp = _hld4_expander(at)
    assert _NEW_START in exp.label and exp.proto.expanded is True


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))  # 同目錄的共用模組
import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）


def test_S6a第四輪_瀏覽器_改日期與按套用之後_HLD4都維持展開_摘要讀已套用值():
    """紅隊 M1＋M2 的瀏覽器重現：改日期（不按套用）HLD-4 收起來、摘要先變；按完「套用」也收起來。"""
    app = _ROOT / "ui_v2" / "app_hld.py"
    api = _ui_v2_chromium.import_sync_api()

    def hld4(tab):
        det = tab.locator("details", has=tab.locator("summary", has_text="HLD-4")).first
        return det.evaluate("d => d.open"), " ".join(det.locator("summary").inner_text().split())

    with api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            with _ui_v2_chromium.streamlit_server(app) as base:
                tab = browser.new_page(viewport={"width": 1400, "height": 1400})
                tab.goto(base + "/?scenario=full", wait_until="networkidle")
                tab.wait_for_selector("text=體檢結論燈", timeout=60000)
                tab.wait_for_timeout(1500)
                tab.locator("summary", has_text="HLD-4").first.click()
                tab.wait_for_timeout(800)
                opened, label = hld4(tab)
                assert opened and "2026-01-01" in label
                box = tab.get_by_label("區間起日")
                box.fill(_NEW_START)
                box.press("Enter")
                tab.wait_for_timeout(2500)
                opened, label = hld4(tab)
                assert opened, "只改日期，HLD-4 自己收起來了"
                assert "2026-01-01" in label and _NEW_START not in label, label
                tab.get_by_role("button", name="套用").click()
                tab.wait_for_timeout(2500)
                opened, label = hld4(tab)
                assert opened, "按完套用，HLD-4 收起來了"
                assert _NEW_START in label, label
                # 停用時真的按不下去（瀏覽器驗；AppTest 對停用鈕 click 照樣觸發回呼）。
                box = tab.get_by_label("區間起日")
                box.fill("20260601")
                box.press("Enter")
                tab.wait_for_timeout(2500)
                assert tab.get_by_role("button", name="套用").is_disabled()
                tab.close()
        finally:
            browser.close()


# ───────────────────────── S6a-2（客戶 2026-10-03 範圍裁示第 2～5 項） ─────────────────────────


def _key_of(live_mode, kind):
    from ui_v2.hld import logic

    hld4 = logic.find_block(_models(live_mode)[0], "HLD-4")
    return next(f"hld4_btn_{i}" for i, b in enumerate(hld4["buttons"]) if b["_action_kind"] == kind)


def _rule_values(at, index):
    return tuple(at.text_input(key=f"hld4_rule_{index}_{part}").value for part in ("indicator", "direction", "value"))


def _rule_count(at):
    return sum(1 for t in at.text_input if t.key and t.key.startswith("hld4_rule_") and t.key.endswith("_indicator"))


def _lamp(at):
    return next(m.value for m in at.markdown if 'class="hld-lamp"' in m.value)


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a2_第2項_N1_畫面上燈寫不重複的檔數_偏離表照列數(live_mode):
    """門檻改成每一檔都超出兩條 → 偏離表 6 列，燈寫「有 3 檔超出」。"""
    at = _apply_run(live_mode)
    at.text_input(key="hld4_rule_0_value").input("1")      # 最大回撤 低於 1 → 三檔都超出
    at.text_input(key="hld4_rule_1_value").input("-1")     # 配息佔淨值比 高於 -1 → 三檔都超出
    button = at.button(key=_key_of(live_mode, "套用"))
    assert button.disabled is False
    button.click().run()
    assert not at.exception
    assert "有 3 檔超出你設定的門檻" in _lamp(at)
    assert "有 6 檔" not in _lamp(at)
    assert _block_blob(at, "HLD-1").count("<tr><td>") == 6


@pytest.mark.parametrize("live_mode", [False, True])
@pytest.mark.parametrize("direction", ["大於", "低於 "])
def test_S6a2_第3項_N2_方向填錯_套用停用_原因句是客戶核准字面(live_mode, direction):
    from ui_v2.hld import logic

    at = _apply_run(live_mode)
    before = _block_blob(at, "HLD-1")
    at.text_input(key="hld4_rule_0_direction").input(direction).run()
    button = at.button(key=_key_of(live_mode, "套用"))
    # AppTest 對停用的鈕 `.click()` 照樣觸發 `on_click` —— 先斷言停用，再確認回呼也不寫入。
    assert button.disabled is True and button.help == logic.TEXT_RULES_BAD == "門檻列未填齊，或格式不符"
    button.click().run()
    assert not at.exception
    assert _block_blob(at, "HLD-1") == before


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a2_第5項_新增一列_多一列空白格_不重算_填好按套用才算(live_mode):
    at = _apply_run(live_mode)
    before = {code: _block_blob(at, code) for code in ("HLD-1", "HLD-2")}
    assert _rule_count(at) == 2
    add = at.button(key=_key_of(live_mode, "新增列"))
    assert add.disabled is False
    add.click().run()
    assert not at.exception
    assert _rule_count(at) == 3
    assert _rule_values(at, 2) == ("", "", "")
    assert {code: _block_blob(at, code) for code in before} == before       # 只改欄位，不重算
    assert _hld4_expander(at).proto.expanded is True                          # 按完維持展開
    # 第三列全空 → 照舊可以套用（全空的列＝沒有這一列）。
    assert at.button(key=_key_of(live_mode, "套用")).disabled is False
    at.text_input(key="hld4_rule_2_indicator").input("區間報酬率")
    at.text_input(key="hld4_rule_2_direction").input("低於")
    at.text_input(key="hld4_rule_2_value").input("100")
    at.button(key=_key_of(live_mode, "套用")).click().run()
    assert not at.exception
    assert "門檻 3 列" in _hld4_expander(at).label
    assert _block_blob(at, "HLD-1") != before["HLD-1"]


@pytest.mark.parametrize("live_mode", [False, True])
def test_S6a2_第5項_清除這一列_後面的列往上補_只剩一列時清空(live_mode):
    at = _apply_run(live_mode)
    second = _rule_values(at, 1)
    assert second[0], "第二列是空的 —— 這一條會變成空掃"
    at.button(key="hld4_row_0").click().run()
    assert not at.exception
    assert _rule_count(at) == 1
    assert _rule_values(at, 0) == second
    assert _hld4_expander(at).proto.expanded is True
    at.button(key="hld4_row_0").click().run()
    assert _rule_count(at) == 1
    assert _rule_values(at, 0) == ("", "", "")
    # 清空之後按「套用」→ 門檻一列也沒有。
    at.button(key=_key_of(live_mode, "套用")).click().run()
    assert not at.exception
    assert "門檻 0 列" in _hld4_expander(at).label


def test_S6a2_瀏覽器_新增一列與方向填錯時套用真的按不下去():
    """「停用時按了沒反應」用瀏覽器驗（AppTest 對停用鈕 click 照樣觸發回呼）。"""
    app = _ROOT / "ui_v2" / "app_hld.py"
    api = _ui_v2_chromium.import_sync_api()
    with api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            with _ui_v2_chromium.streamlit_server(app) as base:
                tab = browser.new_page(viewport={"width": 1400, "height": 1600})
                tab.goto(base + "/?scenario=full", wait_until="networkidle")
                tab.wait_for_selector("text=體檢結論燈", timeout=60000)
                tab.wait_for_timeout(1500)
                tab.locator("summary", has_text="HLD-4").first.click()
                tab.wait_for_timeout(800)
                assert tab.get_by_label("比較方向").count() == 2
                tab.get_by_role("button", name="新增一列").click()
                tab.wait_for_timeout(2500)
                assert tab.get_by_label("比較方向").count() == 3
                det = tab.locator("details", has=tab.locator("summary", has_text="HLD-4")).first
                assert det.evaluate("d => d.open"), "按完新增一列，HLD-4 收起來了"
                box = tab.get_by_label("比較方向").first
                box.fill("大於")
                box.press("Enter")
                tab.wait_for_timeout(2500)
                apply_button = tab.get_by_role("button", name="套用")
                assert apply_button.is_disabled()
                lamp = " ".join(tab.locator(".hld-lamp").first.inner_text().split())
                apply_button.click(force=True)       # 停用的鈕硬點：畫面不得有任何變化
                tab.wait_for_timeout(2000)
                assert " ".join(tab.locator(".hld-lamp").first.inner_text().split()) == lamp
                tab.close()
        finally:
            browser.close()


# ───────────────────────── S6a-2 追加（客戶 2026-10-03）：刪「N 與列數相等」子句 ─────────────────────────


def _srcmiss_app():
    import streamlit as st

    from ui_v2.hld import page

    st.query_params["scenario"] = "srcmiss"
    page.render()


def test_S6a2追加_畫面_一檔超出兩條門檻_燈寫1檔_表2列_沒有列數相等():
    """`srcmiss`（CCCC 缺淨值，卡尾那一句會出現）；門檻改成只有 AAAA 同時超出兩條。"""
    from streamlit.testing.v1 import AppTest

    from ui_v2.hld import logic

    at = AppTest.from_function(_srcmiss_app, default_timeout=60)
    at.run()
    assert not at.exception
    at.text_input(key="hld4_rule_0_indicator").input("最大回撤")
    at.text_input(key="hld4_rule_0_direction").input("低於")
    at.text_input(key="hld4_rule_0_value").input("-10")
    at.text_input(key="hld4_rule_1_indicator").input("配息佔淨值比")
    at.text_input(key="hld4_rule_1_direction").input("低於")
    at.text_input(key="hld4_rule_1_value").input("5")
    hld4 = logic.find_block(logic.build_page_model(**__import__("ui_v2.hld.fixtures", fromlist=["x"]).scenario("srcmiss")), "HLD-4")
    key = next(f"hld4_btn_{i}" for i, b in enumerate(hld4["buttons"]) if b["_action_kind"] == "套用")
    assert at.button(key=key).disabled is False
    at.button(key=key).click().run()
    assert not at.exception
    lamp = next(m.value for m in at.markdown if 'class="hld-lamp"' in m.value)
    assert "有 1 檔超出你設定的門檻" in lamp
    card = next(m.value for m in at.markdown if '<span class="hld-card-code">HLD-1</span>' in m.value)
    assert card.count("<tr><td>") == 2
    assert f'<div class="hld-note">{logic.HLD1_SKIPPED_NOTE}</div>' in card
    screen = "\n".join([m.value for m in at.markdown] + [c.value for c in at.caption] + [e.label for e in at.expander])
    assert "列數相等" not in screen and "燈上的 N" not in screen
