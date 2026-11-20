# -*- coding: utf-8 -*-
"""💼 隔離式 FAKE Preview 的瀏覽器級守衛（slow lane；需要 streamlit 與 Chromium）。

390×844、768、1280 × 十一個情境（①～⑦＋A50 的 ⑧多保單同基金、⑨大量列＋A60 的 ⑩含敏感字串的部分略過、⑪完整但件數未提供）：無水平溢出；390 首屏的 DOM 標記數＝模型點數（A00＋A20 四格＝5），且 fold 內可見的標記數與 DOM 數相等；
切換 selectbox 後畫面真的改變。變異驗證：注入隱藏元素、多一個 chip、把格子推出 fold、強制橫溢，判定函式都必須報紅（全在記憶體內現編）。
另外同時報 `POLICY_A10_TEXT_INCLUDED` 口徑的數字（只記錄、不作斷言；該口徑屬待 UI Review）。
真實 Streamlit Cloud 與真機未驗。
"""
import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_APP = _ROOT / "poc" / "assets_fixture_preview" / "app_assets_preview.py"
for _p in (str(_ROOT / "tests" / "ui_v2"), str(_ROOT / "tests" / "ui_v3"), str(_HERE), str(_ROOT / "poc" / "assets_fixture_preview"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402
import assets_fake_inputs as fake  # noqa: E402
import assets_page_support as sup  # noqa: E402
import assets_preview_browser_lib as lib  # noqa: E402
from ui_v3.adapters.assets_page import build_assets_page  # noqa: E402
from ui_v3.viewmodels import assets_page as vm  # noqa: E402

WIDTHS = (390, 768, 1280)
IDS = list(fake.SCENARIOS)
EXPECTED_STATE = {"multi_currency": "complete", "complete_no_rows": "complete_no_rows", "market_blocked": "not_read", "partial": "partial",
                  "no_active": "not_selected", "read_failed": "read_failed", "unprovided_skip_evidence": "undetermined",
                  "same_fund_two_policies": "complete", "many_rows": "complete", "a60_sensitive_strings": "partial",
                  "complete_counts_unprovided": "undetermined"}
EXPECTED_ROWS = {"multi_currency": 2, "partial": 2, "same_fund_two_policies": 2, "many_rows": 50, "a60_sensitive_strings": 2,
                 "complete_counts_unprovided": 2}   # 其餘情境無列（status-only，不畫容器）
EXPECTED = {sid: vm.first_screen_element_count(build_assets_page(fake.build(sid)), vm.POLICY_A10_TEXT_EXCLUDED) for sid in IDS}
INCLUDED = {sid: vm.first_screen_element_count(build_assets_page(fake.build(sid)), vm.POLICY_A10_TEXT_INCLUDED) for sid in IDS}


@pytest.fixture(scope="module")
def server_and_browser():
    api = _ui_v2_chromium.import_sync_api()
    with _ui_v2_chromium.streamlit_server(_APP) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


def _open(browser, base, width):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    page.goto(base, wait_until="networkidle")
    page.wait_for_selector("[data-source-state]", timeout=60000)
    page.wait_for_timeout(800)
    return ctx, page


def _select(page, sid):
    """用真的 UI 操作切換情境（不繞過 selectbox）。"""
    label = fake.SCENARIOS[sid][0]
    page.locator('[data-testid="stSelectbox"] input').first.click()
    page.get_by_role("option", name=label, exact=True).click()
    page.wait_for_function("s => document.querySelector('[data-source-state]')?.dataset.sourceState === s", arg=EXPECTED_STATE[sid], timeout=30000)
    page.wait_for_function("n => document.querySelectorAll('.uv3-a50-row').length === n", arg=EXPECTED_ROWS.get(sid, 0), timeout=30000)
    page.wait_for_timeout(500)


@pytest.fixture(scope="module")
def measures(server_and_browser):
    """width → {scenario: 量測}；每個寬度只開一次頁面，逐一用 selectbox 切換十一個情境。"""
    base, browser = server_and_browser
    out = {}
    for width in WIDTHS:
        ctx, page = _open(browser, base, width)
        try:
            out[width] = {}
            for sid in IDS:
                _select(page, sid)
                out[width][sid] = page.evaluate(lib.MEASURE_JS)
        finally:
            ctx.close()
    return out


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("width", WIDTHS)
def test_no_horizontal_overflow(measures, width, sid):
    assert lib.overflow_violations(measures[width][sid]) == []


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("width", WIDTHS)
def test_no_streamlit_heading_anchor_tab_stops(measures, width, sid):
    assert lib.anchor_violations(measures[width][sid]) == []


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("width", WIDTHS)
def test_a10_title_keeps_heading_role_and_level_and_page_has_no_h4(measures, width, sid):
    assert lib.a10_title_violations(measures[width][sid]) == []


_POSITIVE_CONTROL_APP = (
    "import streamlit as st\n"
    "st.title('x')\n"                       # 預設會產生錨點
    "st.markdown('<h4>y</h4>', unsafe_allow_html=True)\n"
)


def test_positive_control_detectors_fire_on_a_real_streamlit_page_that_renders_anchors(server_and_browser, tmp_path):
    """正控：用一支極小的暫時 Streamlit 腳本（st.title 不帶 anchor=False、另有 markdown h4）在真實頁面渲染，
    偵測器必須在真正由 Streamlit 產生的錨點上報（不是只注入合成 <a>）；h4 偵測也必須報。"""
    app = tmp_path / "anchor_positive_control_app.py"
    app.write_text(_POSITIVE_CONTROL_APP, encoding="utf-8")
    _, browser = server_and_browser
    with _ui_v2_chromium.streamlit_server(app) as base:
        ctx = browser.new_context(viewport={"width": 390, "height": 844}, locale="zh-TW")
        page = ctx.new_page()
        try:
            page.goto(base, wait_until="networkidle")
            page.wait_for_selector("h1", timeout=60000)
            page.wait_for_function("document.querySelectorAll('a[aria-label=\"Link to heading\"]').length >= 1", timeout=30000)
            m = page.evaluate(lib.MEASURE_JS)
        finally:
            ctx.close()
    kinds = " ".join(v[0] for v in lib.anchor_violations(m))
    assert m["headingAnchors"] >= 1 and m["headingActionElements"] >= 1 and m["headingWrapperLinks"] >= 1, m
    assert "a[aria-label]" in kinds and "stHeaderActionElements" in kinds and "stHeadingWithActionElements" in kinds
    assert m["h4Count"] >= 1 and any("h4" in v[0] for v in lib.a10_title_violations(m))   # 無 A10 區塊＋有 h4：兩項都報


def test_mutation_a10_title_role_stripped_is_flagged(server_and_browser):
    js = "document.querySelector('[data-block=\"a10\"] [role=\"heading\"]').removeAttribute('role')"
    assert lib.a10_title_violations(_mutated(server_and_browser, IDS[0], js=js))


def test_mutation_injected_heading_anchor_is_flagged(server_and_browser):
    js = ("document.querySelector('h1').insertAdjacentHTML('beforeend', "
          "'<a href=\"#x\" aria-label=\"Link to heading\"></a>')")
    assert lib.anchor_violations(_mutated(server_and_browser, IDS[0], js=js))


@pytest.mark.parametrize("sid", IDS)
def test_390_first_screen_marks_equal_model_count_and_are_all_visible_in_the_fold(measures, sid, record_property):
    m = measures[390][sid]
    assert EXPECTED[sid] == 5
    assert lib.first_screen_violations(m, EXPECTED[sid]) == [], m["items"]
    info = (f"{sid}: dom={m['domCount']} visible_in_fold={len(lib.visible_in_fold(m))} "
            f"policy_excluded={EXPECTED[sid]} policy_included={INCLUDED[sid]}")
    record_property(f"first_screen_{sid}", info)
    print("\n[first-screen 390]", info)


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("width", (768, 1280))
def test_wider_widths_keep_the_same_dom_marks_and_order(measures, width, sid):
    m = measures[width][sid]
    assert m["domCount"] == EXPECTED[sid] and m["blocks"][:3] == ["a00", "a10", "a20"] and m["chips"] == 0


@pytest.mark.parametrize("width", WIDTHS)
def test_switching_the_selectbox_really_changes_the_page(measures, width):
    states = [measures[width][sid]["state"] for sid in IDS]
    assert states == [EXPECTED_STATE[sid] for sid in IDS] and len(set(states)) == 7
    assert all(measures[width][sid]["hasBanner"] for sid in IDS)


# ───────────────────────── 變異驗證（注入；判定函式必須報紅） ─────────────────────────

def _mutated(server_and_browser, sid, *, css=None, js=None):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        if sid != IDS[0]:
            _select(page, sid)
        if css:
            page.add_style_tag(content=css)
        if js:
            page.evaluate(js)
        page.wait_for_timeout(200)
        return page.evaluate(lib.MEASURE_JS)
    finally:
        ctx.close()


def test_unmutated_page_passes_the_same_checks(server_and_browser):
    assert lib.first_screen_violations(_mutated(server_and_browser, IDS[0]), 5) == []


def test_mutation_hidden_extra_first_screen_element_is_flagged(server_and_browser):
    js = ("document.querySelector('[data-block=\"a10\"]').insertAdjacentHTML('beforeend', "
          "'<div data-first-screen=\"x\" style=\"display:none\">x</div>')")
    m = _mutated(server_and_browser, IDS[0], js=js)
    assert any("DOM 首屏標記數" in v[0] for v in lib.first_screen_violations(m, 5))


def test_mutation_hidden_real_cell_is_flagged_as_not_visible(server_and_browser):
    m = _mutated(server_and_browser, IDS[0], css='[data-cell="a20_cell_3"]{display:none !important}')
    assert any("fold 內可見" in v[0] for v in lib.first_screen_violations(m, 5))


def test_mutation_cells_pushed_below_the_fold_are_flagged(server_and_browser):
    m = _mutated(server_and_browser, IDS[0], css='[data-block="a20"]{margin-top:1200px !important}')
    assert any("fold 內可見" in v[0] for v in lib.first_screen_violations(m, 5))


def test_mutation_extra_chip_is_flagged(server_and_browser):
    js = "document.querySelector('[data-block=\"a00\"]').insertAdjacentHTML('beforeend', '<span class=\"uv3-chip\">x</span>')"
    m = _mutated(server_and_browser, IDS[0], js=js)
    assert any("chip" in v[0] for v in lib.first_screen_violations(m, 5))


def test_mutation_extra_visible_first_screen_mark_is_flagged(server_and_browser):
    js = ("document.querySelector('[data-block=\"a00\"]').insertAdjacentHTML('afterend', "
          "'<div data-first-screen=\"extra\" data-block=\"zz\">extra</div>')")
    m = _mutated(server_and_browser, IDS[0], js=js)
    assert lib.first_screen_violations(m, 5)


def test_mutation_forced_wide_card_is_flagged_as_overflow(server_and_browser):
    m = _mutated(server_and_browser, IDS[0], css=".uv3-card{min-width:900px !important}")
    assert lib.overflow_violations(m)


# ───────────────────────── A50：單一 `<details>` 容器的實測（DEC-2026-11-16-01） ─────────────────────────
# 事實面：Streamlit 的 st.markdown(unsafe_allow_html) 是否保留 `<details>`／`<summary>`、可否開合、點擊是否 rerun（以 websocket
# client→server 訊息數觀察）、各寬度無水平溢出、觸控 ≥48px、鍵盤 Enter／Space、50 列可垂直捲動不截斷、特殊字元 escape。
# 只在本機 Chromium 驗；真實 Streamlit Cloud 與真機未驗（NOT VERIFIED）。

ROW_SCENARIOS = [sid for sid in IDS if sid in EXPECTED_ROWS]


def _open_counting(browser, base, width):
    """開頁並計數 client→server 的 websocket 訊息（framesent）。回傳 (ctx, page, sent)。"""
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    sent = []
    page.on("websocket", lambda ws: ws.on("framesent", lambda frame: sent.append(1)))
    page.goto(base, wait_until="networkidle")
    page.wait_for_selector("[data-source-state]", timeout=60000)
    page.wait_for_timeout(800)
    return ctx, page, sent


@pytest.fixture(scope="module")
def a50_measures(server_and_browser):
    """width → {scenario: A50 量測（收合狀態）}；沒有容器的情境量測為 None。"""
    base, browser = server_and_browser
    out = {}
    for width in WIDTHS:
        ctx, page = _open(browser, base, width)
        try:
            out[width] = {}
            for sid in IDS:
                _select(page, sid)
                out[width][sid] = page.evaluate(lib.A50_JS)
        finally:
            ctx.close()
    return out


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("width", WIDTHS)
def test_a50_container_exists_only_with_rows_and_is_one_collapsed_details(a50_measures, width, sid):
    a = a50_measures[width][sid]
    if sid not in EXPECTED_ROWS:
        assert a is None   # status-only：不畫容器、不畫導向空內容的入口
        return
    assert lib.a50_violations(a, expect_open=False, expect_rows=EXPECTED_ROWS[sid]) == [], a


@pytest.mark.parametrize("width", WIDTHS)
def test_click_toggles_details_open_and_closed_without_any_client_to_server_message(server_and_browser, width):
    base, browser = server_and_browser
    ctx, page, sent = _open_counting(browser, base, width)
    try:
        # 正控：真的會 rerun 的操作（切換情境）必須讓計數增加，否則「點擊 0 訊息」可能是空綠。
        before = len(sent)
        _select(page, "many_rows")
        assert len(sent) > before
        summary = page.locator('details[data-block="a50"] > summary')
        n0 = len(sent)
        summary.click()
        page.wait_for_function("() => document.querySelector('details[data-block=\"a50\"]').open === true", timeout=10000)
        page.wait_for_timeout(1500)
        assert page.evaluate("() => document.querySelector('.uv3-a50-row').getBoundingClientRect().height") > 0   # 展開後內容真的可見
        summary.click()
        page.wait_for_function("() => document.querySelector('details[data-block=\"a50\"]').open === false", timeout=10000)
        page.wait_for_timeout(1500)
        assert len(sent) == n0, f"開合造成 {len(sent) - n0} 個 client→server 訊息（會 rerun）"
    finally:
        ctx.close()


def test_keyboard_enter_and_space_toggle_the_summary(server_and_browser):
    base, browser = server_and_browser
    ctx, page, sent = _open_counting(browser, base, 1280)
    try:
        summary = page.locator('details[data-block="a50"] > summary')
        is_open = "() => document.querySelector('details[data-block=\"a50\"]').open"
        summary.focus()
        n0 = len(sent)
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        assert page.evaluate(is_open) is True
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        assert page.evaluate(is_open) is False
        page.keyboard.press("Space")
        page.wait_for_timeout(300)
        assert page.evaluate(is_open) is True
        page.keyboard.press("Space")
        page.wait_for_timeout(300)
        assert page.evaluate(is_open) is False
        assert len(sent) == n0
    finally:
        ctx.close()


@pytest.mark.parametrize("sid", ROW_SCENARIOS)
@pytest.mark.parametrize("width", WIDTHS)
def test_opened_a50_has_no_horizontal_overflow_and_keeps_the_first_screen_and_block_order(server_and_browser, width, sid):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, width)
    try:
        _select(page, sid)
        page.locator('details[data-block="a50"] > summary').click()
        page.wait_for_function("() => document.querySelector('details[data-block=\"a50\"]').open === true", timeout=10000)
        page.wait_for_timeout(500)
        a = page.evaluate(lib.A50_JS)
        assert lib.a50_violations(a, expect_open=True, expect_rows=EXPECTED_ROWS[sid]) == [], a
        assert a["rowsClippedX"] == 0
        m = page.evaluate(lib.MEASURE_JS)
        assert lib.overflow_violations(m) == [], m
        assert m["blocks"] == ["a00", "a10", "a20", "a50", "a60"] and m["domCount"] == 5 and m["chips"] == 0
        if width == 390:
            assert lib.first_screen_violations(m, EXPECTED[sid]) == [], m["items"]   # 展開 A50 不影響首屏的 5 個標記
    finally:
        ctx.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_fifty_rows_scroll_vertically_inside_the_container_and_are_not_truncated(server_and_browser, width):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, width)
    try:
        _select(page, "many_rows")
        page.locator('details[data-block="a50"] > summary').click()
        page.wait_for_function("() => document.querySelector('details[data-block=\"a50\"]').open === true", timeout=10000)
        page.wait_for_timeout(500)
        a = page.evaluate(lib.A50_JS)
        assert a["rowCount"] == 50 and a["fieldCount"] == 200
        assert a["bodyOverflowY"] == "auto" and a["bodyScrollH"] > a["bodyClientH"]          # 內容比容器高 → 容器內垂直捲動
        assert a["bodyH"] <= a["vh"] * 0.7 + 1                                                  # 容器本身不撐爆視窗
        end = page.evaluate(lib.A50_SCROLL_END_JS)
        assert end["scrollTop"] > 0 and end["lastBottom"] <= end["bodyBottom"] + 1 and end["lastTop"] >= end["bodyTop"] - 1   # 捲到底，最後一列完整可見
        assert page.evaluate(lib.MEASURE_JS)["docScrollW"] <= width
    finally:
        ctx.close()


def test_special_characters_in_fund_name_are_escaped_not_interpreted(server_and_browser):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        _select(page, "many_rows")
        a = page.evaluate(lib.A50_JS)
        assert a["firstRowName"] == fake.FAKE_MARKUP_NAME      # 文字內容逐字保留（<b>、&、引號、<script> 都只是文字）
        assert a["injectedTags"] == 0                          # DOM 裡沒有被解析出來的 b／script／i 元素
    finally:
        ctx.close()


def test_a50_never_exposes_holding_id_or_policy_in_dom(server_and_browser):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        _select(page, "same_fund_two_policies")
        a = page.evaluate(lib.A50_JS)
        assert a["hasHoldingIdAttr"] is False and a["rowCount"] == 2
        html = page.content()
        assert "FAKE-POLICY" not in html and "holding_id" not in html
    finally:
        ctx.close()


def _a50_mutated(server_and_browser, *, css=None, js=None):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        page.locator('details[data-block="a50"] > summary').click()
        page.wait_for_function("() => document.querySelector('details[data-block=\"a50\"]').open === true", timeout=10000)
        assert lib.a50_violations(page.evaluate(lib.A50_JS), expect_open=True, expect_rows=2) == []   # 正控：未變異時全綠
        if css:
            page.add_style_tag(content=css)
        if js:
            page.evaluate(js)
        page.wait_for_timeout(300)
        return page.evaluate(lib.A50_JS), page.evaluate(lib.MEASURE_JS)
    finally:
        ctx.close()


def test_mutation_a50_wide_row_is_flagged_alone(server_and_browser):
    a, m = _a50_mutated(server_and_browser, css=".uv3-a50-row{width:1000px !important}")
    # 容器 overflow-x:hidden 會裁掉過寬列，所以由「頁本體元素超出視窗右緣」判定抓到（a50_violations 的整頁溢出判定在此不觸發）
    assert any("頁本體元素超出視窗右緣" in v[0] for v in lib.overflow_violations(m)), (a, m)


def test_mutation_a50_small_summary_is_flagged_alone(server_and_browser):
    a, _ = _a50_mutated(server_and_browser, css=".uv3-a50 > summary{min-height:20px !important;padding:0 !important}")
    assert any("觸控" in v[0] for v in lib.a50_violations(a, expect_open=True, expect_rows=2))


def test_mutation_a50_second_details_is_flagged_alone(server_and_browser):
    js = "() => document.querySelector('details[data-block=\"a50\"] [data-a50=\"body\"]').insertAdjacentHTML('beforeend', '<details><summary>x</summary>y</details>')"
    a, _ = _a50_mutated(server_and_browser, js=js)
    assert any("巢狀" in v[0] or "各恰一個" in v[0] for v in lib.a50_violations(a, expect_open=True, expect_rows=2))


# ───────────────────────── A60：獨立 `<details>`（A50 之後；DEC-2026-11-17-01） ─────────────────────────
# 事實面（只在本機 Chromium 驗；真實 Streamlit Cloud 與真機未驗，NOT VERIFIED）：A60 恆畫一次、預設收合、與 A50 並列不巢狀、不標首屏；
# 開合零 rerun（websocket framesent 增量 0＋正控）、鍵盤 Enter／Space、390／768／1280 無水平溢出、觸控目標 ≥48px、A50 與 A60 同時展開不溢出；
# 變異驗證（巢狀、第二個 details、提前 open、順序顛倒、首屏標記、過寬列、縮小摘要、洩漏哨兵）判定函式都各自報紅。

A60_EXPECT_STATE = {"multi_currency": "undetermined", "complete_no_rows": "complete_no_rows", "market_blocked": "undetermined", "partial": "partial",
                    "no_active": "undetermined", "read_failed": "read_failed", "unprovided_skip_evidence": "undetermined",
                    "same_fund_two_policies": "undetermined", "many_rows": "undetermined", "a60_sensitive_strings": "partial",
                    "complete_counts_unprovided": "undetermined"}
A60_EXPECT_COUNTS = {"multi_currency": ["0", "0"], "partial": ["1", "2"], "a60_sensitive_strings": ["1", "2"], "complete_no_rows": ["0", "0"],
                     "same_fund_two_policies": ["0", "0"], "many_rows": ["0", "0"]}
A60_SELECTOR = 'details[data-block="a60"]'
LEAK_TOKENS = (list(sup.FAKE_SENSITIVE_STRINGS) + list(sup.FAKE_A60_PROBLEM_CODES)
               + ["NETWORK_ERROR", "holding_read_failed", "no_active_source", "market_basis", "problem_codes", "cause_key", "failure_code", "partial_source"])


# 整頁層級的禁止字串：不含 `http`／`https://`（Streamlit 自己的頁面含本機位址）與 `partial_source`（A10 暫時字樣的鍵名子字串）；A60 區用完整清單
LEAK_TOKENS_PAGE = [t for t in LEAK_TOKENS if t not in ("http", "https://", "partial_source")]


def _total_details(sid):
    return 2 if sid in EXPECTED_ROWS else 1


def _center(page, selector):
    page.evaluate("sel => document.querySelector(sel).scrollIntoView({block: 'center'})", selector)
    page.wait_for_timeout(200)


def _open_a60(page):
    page.locator(f"{A60_SELECTOR} > summary").click()
    page.wait_for_function(f"() => document.querySelector('{A60_SELECTOR}').open === true", timeout=10000)
    page.wait_for_timeout(300)


@pytest.fixture(scope="module")
def a60_measures(server_and_browser):
    """width → {scenario: A60 量測（收合狀態）}。"""
    base, browser = server_and_browser
    out = {}
    for width in WIDTHS:
        ctx, page = _open(browser, base, width)
        try:
            out[width] = {}
            for sid in IDS:
                _select(page, sid)
                out[width][sid] = page.evaluate(lib.A60_JS)
        finally:
            ctx.close()
    return out


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("width", WIDTHS)
def test_a60_is_always_one_collapsed_details_after_a50_not_nested_and_not_first_screen(a60_measures, width, sid):
    a = a60_measures[width][sid]
    assert lib.a60_violations(a, expect_open=False, expect_total_details=_total_details(sid)) == [], a
    assert a["stateAttr"] == A60_EXPECT_STATE[sid]
    if sid in A60_EXPECT_COUNTS:
        assert [re.sub(r"\D", "", t) for t in a["countsText"]] == A60_EXPECT_COUNTS[sid], a["countsText"]


@pytest.mark.parametrize("width", WIDTHS)
def test_a60_click_toggles_without_any_client_to_server_message(server_and_browser, width):
    base, browser = server_and_browser
    ctx, page, sent = _open_counting(browser, base, width)
    try:
        before = len(sent)
        _select(page, "partial")
        assert len(sent) > before   # 正控：真的會 rerun 的操作（切換情境）計數會增加，所以下面的「0」不是空綠
        summary = page.locator(f"{A60_SELECTOR} > summary")
        n0 = len(sent)
        summary.click()
        page.wait_for_function(f"() => document.querySelector('{A60_SELECTOR}').open === true", timeout=10000)
        page.wait_for_timeout(1500)
        assert page.evaluate(f"() => document.querySelector('{A60_SELECTOR} [data-a60=\"state\"]').getBoundingClientRect().height") > 0   # 展開後內容真的可見
        summary.click()
        page.wait_for_function(f"() => document.querySelector('{A60_SELECTOR}').open === false", timeout=10000)
        page.wait_for_timeout(1500)
        assert len(sent) == n0, f"開合造成 {len(sent) - n0} 個 client→server 訊息（會 rerun）"
    finally:
        ctx.close()


def test_a60_keyboard_enter_and_space_toggle_the_summary(server_and_browser):
    base, browser = server_and_browser
    ctx, page, sent = _open_counting(browser, base, 1280)
    try:
        _select(page, "no_active")   # 無 A50 容器的情境：A60 是唯一的 <details>
        n0 = len(sent)
        is_open = f"() => document.querySelector('{A60_SELECTOR}').open"
        page.locator(f"{A60_SELECTOR} > summary").focus()
        for key, expected in (("Enter", True), ("Enter", False), ("Space", True), ("Space", False)):
            page.keyboard.press(key)
            page.wait_for_timeout(300)
            assert page.evaluate(is_open) is expected, key
        assert len(sent) == n0
    finally:
        ctx.close()


@pytest.mark.parametrize("sid", IDS)
@pytest.mark.parametrize("width", WIDTHS)
def test_opened_a60_has_no_horizontal_overflow_and_keeps_the_first_screen(server_and_browser, width, sid):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, width)
    try:
        _select(page, sid)
        _open_a60(page)
        a = page.evaluate(lib.A60_JS)
        assert lib.a60_violations(a, expect_open=True, expect_total_details=_total_details(sid)) == [], a
        m = page.evaluate(lib.MEASURE_JS)
        assert lib.overflow_violations(m) == [], m
        assert m["blocks"][-1] == "a60" and m["domCount"] == 5 and m["chips"] == 0
        if width == 390:
            assert lib.first_screen_violations(m, EXPECTED[sid]) == [], m["items"]   # 展開 A60 不影響首屏的 5 個標記
    finally:
        ctx.close()


@pytest.mark.parametrize("sid", ROW_SCENARIOS)
@pytest.mark.parametrize("width", WIDTHS)
def test_a50_and_a60_open_together_do_not_overflow_and_stay_siblings(server_and_browser, width, sid):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, width)
    try:
        _select(page, sid)
        page.locator('details[data-block="a50"] > summary').click()
        page.wait_for_function("() => document.querySelector('details[data-block=\"a50\"]').open === true", timeout=10000)
        _open_a60(page)
        _center(page, 'details[data-block="a50"] > summary')   # 點 A60 會把頁面捲走；「摘要被蓋住」以座標判定，須先捲到視窗中央再量（貼頂會被 Streamlit 固定頁首蓋住，那不是版面缺陷）
        a50 = page.evaluate(lib.A50_JS)
        assert lib.a50_violations(a50, expect_open=True, expect_rows=EXPECTED_ROWS[sid]) == [], a50
        _center(page, f"{A60_SELECTOR} > summary")
        a60 = page.evaluate(lib.A60_JS)
        assert lib.a60_violations(a60, expect_open=True, expect_total_details=2) == [], a60
        assert lib.overflow_violations(page.evaluate(lib.MEASURE_JS)) == []
        assert page.evaluate("() => document.documentElement.scrollWidth") <= width
    finally:
        ctx.close()


@pytest.mark.parametrize("sid", IDS)
def test_a60_dom_and_text_never_carry_sensitive_strings_internal_codes_or_urls(server_and_browser, sid):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        _select(page, sid)
        _open_a60(page)
        a = page.evaluate(lib.A60_JS)
        assert lib.leak_violations(a["html"], a["text"], LEAK_TOKENS) == [], sid
        assert lib.leak_violations(page.content(), page.inner_text("body"), LEAK_TOKENS_PAGE) == [], sid   # 整頁（含 A50、harness）也沒有
    finally:
        ctx.close()


def test_sensitive_scenario_is_really_the_one_carrying_the_sentinels_positive_control():
    raw = repr(fake.build("a60_sensitive_strings"))
    assert all(t in raw for t in ("docs.google.com", sup.FAKE_SENSITIVE_SHEET_ID, "Traceback", "settings_read_failed"))


def _a60_mutated(server_and_browser, *, css=None, js=None, open_first=True):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        if open_first:
            _open_a60(page)
        total = _total_details(IDS[0])
        green = lib.a60_violations(page.evaluate(lib.A60_JS), expect_open=open_first, expect_total_details=total)
        assert green == [], green   # 正控：未變異時全綠
        if css:
            page.add_style_tag(content=css)
        if js:
            page.evaluate(js)
        page.wait_for_timeout(300)
        return page.evaluate(lib.A60_JS), page.evaluate(lib.MEASURE_JS)
    finally:
        ctx.close()


def test_mutation_a60_nested_details_is_flagged(server_and_browser):
    a, _ = _a60_mutated(server_and_browser, js="() => document.querySelector('[data-a60=\"body\"]').insertAdjacentHTML('beforeend', '<details><summary>x</summary>y</details>')")
    assert any("巢狀" in v[0] or "數量" in v[0] for v in lib.a60_violations(a, expect_open=True, expect_total_details=2))


def test_mutation_second_a60_details_is_flagged(server_and_browser):
    a, _ = _a60_mutated(server_and_browser, js="() => document.querySelector('details[data-block=\"a60\"]').insertAdjacentHTML('afterend', '<details data-block=\"a60\"><summary>x</summary></details>')")
    assert any("數量" in v[0] for v in lib.a60_violations(a, expect_open=True, expect_total_details=2))


def test_mutation_a60_opened_by_default_is_flagged(server_and_browser):
    a, _ = _a60_mutated(server_and_browser, open_first=False, js="() => document.querySelector('details[data-block=\"a60\"]').setAttribute('open', '')")
    assert any("展開狀態" in v[0] for v in lib.a60_violations(a, expect_open=False, expect_total_details=2))


def test_mutation_a60_before_a50_is_flagged(server_and_browser):
    a, _ = _a60_mutated(server_and_browser, js="() => { const a50 = document.querySelector('details[data-block=\"a50\"]'); a50.parentElement.insertBefore(document.querySelector('details[data-block=\"a60\"]'), a50); }")
    assert any("最後一個區塊" in v[0] for v in lib.a60_violations(a, expect_open=True, expect_total_details=2))


def test_mutation_a60_first_screen_mark_is_flagged(server_and_browser):
    a, _ = _a60_mutated(server_and_browser, js="() => document.querySelector('[data-a60=\"state\"]').setAttribute('data-first-screen', 'x')")
    assert any("首屏" in v[0] for v in lib.a60_violations(a, expect_open=True, expect_total_details=2))


def test_mutation_a60_small_summary_is_flagged(server_and_browser):
    a, _ = _a60_mutated(server_and_browser, css=".uv3-a60 > summary{min-height:20px !important;padding:0 !important}")
    assert any("觸控" in v[0] for v in lib.a60_violations(a, expect_open=True, expect_total_details=2))


def test_mutation_a60_wide_row_is_flagged_as_overflow(server_and_browser):
    _, m = _a60_mutated(server_and_browser, css='[data-a60="state"]{width:1000px !important;white-space:nowrap !important}')
    assert any("超出視窗右緣" in v[0] for v in lib.overflow_violations(m)), m["overflowing"]


def test_mutation_leaked_sentinel_in_a60_is_flagged(server_and_browser):
    a, _ = _a60_mutated(server_and_browser, js="() => document.querySelector('[data-a60=\"state\"]').insertAdjacentHTML('beforeend', '<span>https://docs.google.com/spreadsheets/d/FAKESHEETID0123456789</span>')")
    assert lib.leak_violations(a["html"], a["text"], LEAK_TOKENS)
    assert lib.leak_violations(a["html"], a["text"], ["a-token-that-is-nowhere-on-the-page"]) == []   # 檢查器不會亂報
