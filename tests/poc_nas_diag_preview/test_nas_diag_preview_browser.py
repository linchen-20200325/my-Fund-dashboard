# -*- coding: utf-8 -*-
"""NAS 中繼站診斷隔離式 FAKE Preview 的瀏覽器級守衛（slow lane；需要 streamlit 與 Chromium）。

390×844、768、1280 × 全部情境：無水平溢出、共同結構（徽章／兩軸卡片／暫行提示／無可互動元素）、兩軸卡片的響應式排列；
降級直連的徽章與橫幅可見且與連線成功不同詞不同色；用真的 UI 操作切換情境（selectbox），並驗證鍵盤可達（Tab 到 selectbox、方向鍵＋Enter 換情境）。
變異驗證：把降級直連渲染成成功的詞／色、注入溢出、注入假按鈕、拿掉橫幅，判定函式都必須報紅（全在記憶體內現編）。
真實 Streamlit Cloud 與真機未驗（NOT VERIFIED）。
"""
import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_APP = _ROOT / "poc" / "nas_diag_preview" / "app_nas_diag_preview.py"
for _p in (str(_ROOT / "tests" / "ui_v2"), str(_ROOT / "tests" / "ui_v3"), str(_HERE), str(_ROOT / "poc" / "nas_diag_preview"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402
import nas_diag_fake_inputs as fake  # noqa: E402
import nas_diag_preview_browser_lib as lib  # noqa: E402
import nas_diag_support as sup  # noqa: E402

WIDTHS = (390, 768, 1280)
IDS = list(fake.SCENARIOS)
DEGRADED = ("degraded_direct", "blocked_403_then_direct")


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
    page.wait_for_selector("[data-block='nas-status']", timeout=60000)
    page.wait_for_timeout(800)
    return ctx, page


def _select(page, sid):
    """用真的 UI 操作切換情境（不繞過 selectbox）。"""
    label = fake.SCENARIOS[sid][0]
    page.locator('[data-testid="stSelectbox"] input').first.click()
    # 選單項目多（13 個）、清單是虛擬化捲動：依序往下捲，直到目標選項出現在 DOM 再點擊
    page.wait_for_selector("[role=option]", timeout=30000)
    option = page.get_by_role("option", name=label, exact=True)
    for position in ("0", "l.scrollHeight"):
        page.evaluate("() => { const l = document.querySelector('[role=listbox]'); if (l) l.scrollTop = " + position + "; }")
        page.wait_for_timeout(300)
        if option.count():
            break
    option.click()
    page.wait_for_function("s => document.querySelector('[data-block=\"nas-status\"]')?.dataset.state === s", arg=sup.EXPECTED[sid][0], timeout=30000)
    page.wait_for_timeout(500)


@pytest.fixture(scope="module")
def measures(server_and_browser):
    """width → {scenario: 量測}；每個寬度只開一次頁面，逐一用 selectbox 切換全部情境。"""
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
def test_common_structure_and_axes_layout(measures, width, sid):
    m = measures[width][sid]
    assert m["state"] == sup.EXPECTED[sid][0]
    assert lib.structure_violations(m) == [], m
    assert lib.axes_layout_violations(m) == [], m
    assert [a["health"] for a in sorted(m["axes"], key=lambda a: a["axis"])] == [sup.EXPECTED[sid][1], sup.EXPECTED[sid][2]]
    assert m["badge"]["right"] <= m["vw"] + 0.5   # 徽章不超出視窗


@pytest.mark.parametrize("width", WIDTHS)
def test_switching_the_selectbox_really_changes_the_page(measures, width):
    states = [measures[width][sid]["state"] for sid in IDS]
    assert states == [sup.EXPECTED[sid][0] for sid in IDS] and len(set(states)) == 6
    assert len({measures[width][sid]["text"] for sid in IDS}) == len(IDS)


@pytest.mark.parametrize("sid", DEGRADED)
@pytest.mark.parametrize("width", WIDTHS)
def test_degraded_direct_badge_and_banner_are_visible_and_differ_from_success(measures, width, sid):
    deg, ok = measures[width][sid], measures[width]["nas_ok"]
    assert lib.degraded_distinct_violations(deg, ok) == []
    assert deg["badge"]["text"] == "▲ 已降級直連" and ok["badge"]["text"] == "✓ 本次連線成功"
    assert deg["banner"]["text"] == "NAS 失敗，改走直連；NAS 並未正常" and deg["banner"]["right"] <= deg["vw"] + 0.5
    assert ok["banner"] is None   # 成功時沒有降級橫幅


@pytest.mark.parametrize("width", WIDTHS)
def test_no_interactive_element_in_the_renderer_so_no_touch_target_below_minimum(measures, width):
    assert all(measures[width][sid]["interactiveCount"] == 0 for sid in IDS)
    # harness 的 selectbox 是 Streamlit 預設高度（約 40px），未達 48px 觸控下限：據實記錄，不屬 renderer
    assert all(measures[width][sid]["selectH"] and measures[width][sid]["selectH"] >= 38 for sid in IDS)


@pytest.mark.parametrize("width", WIDTHS)
def test_evidence_details_is_collapsed_by_default_and_opening_it_neither_overflows_nor_adds_links(server_and_browser, width):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, width)
    try:
        before = page.evaluate(lib.MEASURE_JS)
        assert before["evidence"]["open"] is False and lib.structure_violations(before) == []
        assert page.locator('[data-block="evidence"] [data-row="latency"]').first.is_visible() is False   # 收合時內容不可見
        page.locator('[data-summary="evidence"]').click()
        page.wait_for_timeout(300)
        after = page.evaluate(lib.MEASURE_JS)
        assert after["evidence"]["open"] is True and lib.overflow_violations(after) == [] and after["mainLinks"] == 0
        assert page.locator('[data-block="evidence"] [data-row="latency"]').first.is_visible() is True
    finally:
        ctx.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_summary_is_keyboard_operable_with_enter(server_and_browser, width):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, width)
    try:
        page.locator('[data-summary="evidence"]').focus()
        page.keyboard.press("Enter")
        page.wait_for_timeout(300)
        assert page.evaluate("() => document.querySelector('details[data-block=\"evidence\"]').open") is True
    finally:
        ctx.close()


def test_selectbox_is_keyboard_reachable_and_changes_the_scenario_with_arrow_and_enter(server_and_browser):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, 1280)
    try:
        reached = False
        for _ in range(12):
            page.keyboard.press("Tab")
            if page.evaluate("() => !!document.activeElement && !!document.activeElement.closest('[data-testid=\"stSelectbox\"]')"):
                reached = True
                break
        assert reached, "Tab 12 次內沒有到達 selectbox"
        before = page.evaluate("() => document.querySelector('[data-block=\"nas-status\"]').dataset.state")
        assert before == sup.EXPECTED[IDS[0]][0]
        page.keyboard.press("ArrowDown")
        page.wait_for_timeout(400)
        page.keyboard.press("ArrowDown")   # 第一次打開選單，第二次移到下一個選項
        page.keyboard.press("Enter")
        page.wait_for_function("s => document.querySelector('[data-block=\"nas-status\"]')?.dataset.state !== s", arg=before, timeout=30000)
        after = page.evaluate("() => document.querySelector('[data-block=\"nas-status\"]').dataset.state")
        assert after != before and after in {v[0] for v in sup.EXPECTED.values()}   # 鍵盤選到的是另一個情境（哪一個取決於選單開啟時的高亮位置）
    finally:
        ctx.close()


# ───────────────────────── 變異驗證（注入；判定函式必須報紅） ─────────────────────────

def _mutated(server_and_browser, sid, *, width=390, css=None, js=None):
    base, browser = server_and_browser
    ctx, page = _open(browser, base, width)
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


def test_unmutated_pages_pass_the_same_checks(server_and_browser, measures):
    m = _mutated(server_and_browser, "degraded_direct")
    assert lib.structure_violations(m) == [] and lib.overflow_violations(m) == []
    assert lib.degraded_distinct_violations(m, measures[390]["nas_ok"]) == []


def test_mutation_degraded_rendered_with_the_success_wording_is_flagged(server_and_browser, measures):
    js = "() => { document.querySelector('[data-badge=\"state\"]').textContent = '✓ 本次連線成功'; }"
    m = _mutated(server_and_browser, "degraded_direct", js=js)
    assert any("同詞" in v[0] for v in lib.degraded_distinct_violations(m, measures[390]["nas_ok"]))


def test_mutation_degraded_rendered_with_the_success_color_is_flagged(server_and_browser, measures):
    ok = measures[390]["nas_ok"]
    css = (f".uv3n-badge{{background-color:{ok['badge']['bg']} !important;border-color:{ok['badge']['border']} !important}}")
    m = _mutated(server_and_browser, "degraded_direct", css=css)
    assert any("同色" in v[0] for v in lib.degraded_distinct_violations(m, ok))


def test_mutation_degraded_without_the_banner_is_flagged(server_and_browser, measures):
    m = _mutated(server_and_browser, "degraded_direct", css=".uv3n-banner{display:none !important}")
    assert any("橫幅" in v[0] for v in lib.degraded_distinct_violations(m, measures[390]["nas_ok"]))


def test_mutation_success_text_leaking_into_the_degraded_page_is_flagged(server_and_browser, measures):
    js = "() => { document.querySelector('[data-block=\"nas-status\"]').insertAdjacentHTML('beforeend', '<div>✓ 本次連線成功</div>'); }"
    m = _mutated(server_and_browser, "degraded_direct", js=js)
    assert any("連線成功字樣" in v[0] for v in lib.degraded_distinct_violations(m, measures[390]["nas_ok"]))


def test_mutation_forced_wide_card_is_flagged_as_overflow(server_and_browser):
    m = _mutated(server_and_browser, "nas_ok", css=".uv3-card{min-width:900px !important}")
    assert lib.overflow_violations(m)


def test_mutation_injected_fake_test_button_is_flagged(server_and_browser):
    js = "() => { document.querySelector('[data-block=\"nas-status\"]').insertAdjacentHTML('beforeend', '<button>立即測試連線</button>'); }"
    m = _mutated(server_and_browser, "nas_ok", js=js)
    assert any("可互動元素" in v[0] for v in lib.structure_violations(m))


def test_mutation_summary_shrunk_below_48px_is_flagged(server_and_browser):
    m = _mutated(server_and_browser, "nas_ok", css=".uv3n-evidence > summary{min-height:20px !important;height:20px !important}")
    assert any("48px" in v[0] for v in lib.structure_violations(m))


def test_mutation_details_open_by_default_or_nested_is_flagged(server_and_browser):
    m = _mutated(server_and_browser, "nas_ok", js="() => { document.querySelector('details[data-block=\"evidence\"]').open = true; }")
    assert any("預設不是收合" in v[0] for v in lib.structure_violations(m))
    m = _mutated(server_and_browser, "nas_ok", js="() => { document.querySelector('details[data-block=\"evidence\"]').insertAdjacentHTML('beforeend', '<details><summary>x</summary></details>'); }")
    assert any("不巢狀" in v[0] for v in lib.structure_violations(m))


def test_mutation_axes_forced_side_by_side_on_mobile_is_flagged(server_and_browser):
    m = _mutated(server_and_browser, "nas_ok", css=".uv3n-axes{grid-template-columns:repeat(2,minmax(0,1fr)) !important}")
    assert lib.axes_layout_violations(m)
