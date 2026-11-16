# -*- coding: utf-8 -*-
"""💼 隔離式 FAKE Preview 的瀏覽器級守衛（slow lane；需要 streamlit 與 Chromium）。

390×844、768、1280 × 七個情境：無水平溢出；390 首屏的 DOM 標記數＝模型點數（A00＋A20 四格＝5），且 fold 內可見的標記數與 DOM 數相等；
切換 selectbox 後畫面真的改變。變異驗證：注入隱藏元素、多一個 chip、把格子推出 fold、強制橫溢，判定函式都必須報紅（全在記憶體內現編）。
另外同時報 `POLICY_A10_TEXT_INCLUDED` 口徑的數字（只記錄、不作斷言；該口徑屬待 UI Review）。
真實 Streamlit Cloud 與真機未驗。
"""
import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
_APP = _ROOT / "poc" / "assets_fixture_preview" / "app_assets_preview.py"
for _p in (str(_ROOT / "tests" / "ui_v2"), str(_HERE), str(_ROOT / "poc" / "assets_fixture_preview"), str(_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402
import assets_fake_inputs as fake  # noqa: E402
import assets_preview_browser_lib as lib  # noqa: E402
from ui_v3.adapters.assets_page import build_assets_page  # noqa: E402
from ui_v3.viewmodels import assets_page as vm  # noqa: E402

WIDTHS = (390, 768, 1280)
IDS = list(fake.SCENARIOS)
EXPECTED_STATE = {"multi_currency": "complete", "complete_no_rows": "complete_no_rows", "market_blocked": "not_read", "partial": "partial",
                  "no_active": "not_selected", "read_failed": "read_failed", "unprovided_skip_evidence": "undetermined"}
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
    page.wait_for_timeout(500)


@pytest.fixture(scope="module")
def measures(server_and_browser):
    """width → {scenario: 量測}；每個寬度只開一次頁面，逐一用 selectbox 切換七個情境。"""
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
