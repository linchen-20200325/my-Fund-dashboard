# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview 的瀏覽器級守衛（slow lane；需要 streamlit 與 Chromium）。

390×844、768、1280：無水平溢出、可見控制項觸控目標 ≥48px（harness 的 selectbox 約 40px，據實另量）、details 預設收合且不巢狀、首屏順序、
無外部請求（攔截 request 事件）、輸入 script 字串不執行、鍵盤 Tab／Enter 可操作且結果與滑鼠點擊一致、情境切換與條件勾選真的改變結果。
變異驗證：注入溢出、縮小觸控目標、展開／巢狀 details、插入禁用字樣、改錯 N、拿掉 escape，判定函式都必須報紅（全在記憶體內現編）。
真實 Streamlit Cloud 與真機未驗（NOT VERIFIED）。
"""
import pytest

import fund_search_support as S  # noqa: F401

pytestmark = pytest.mark.slow

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402
import fund_search_browser_lib as lib  # noqa: E402
import fund_search_fake_inputs as fake  # noqa: E402

WIDTHS = (390, 768, 1280)
BASE_KEY = "fs"


@pytest.fixture(scope="module")
def server_and_browser():
    api = _ui_v2_chromium.import_sync_api()
    with _ui_v2_chromium.streamlit_server(S.APP) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


class Opened:
    """一個已載入的頁面與它收到的請求／對話框紀錄。"""

    def __init__(self, ctx, page, requests, dialogs):
        self.ctx, self.page, self.requests, self.dialogs = ctx, page, requests, dialogs

    def measure(self):
        return self.page.evaluate(lib.MEASURE_JS)

    def close(self):
        self.ctx.close()


def _open(browser, base, width):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    requests, dialogs = [], []
    page.on("request", lambda r: requests.append(r.url))
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(base, wait_until="networkidle")
    page.wait_for_selector('[data-block="basic-info"]', timeout=60000)
    page.wait_for_timeout(600)
    return Opened(ctx, page, requests, dialogs)


def _input(page):
    return page.get_by_label("MoneyDJ 基金代碼或 ISIN")


def _wait_outcome(page, outcome):
    page.wait_for_function("o => (document.querySelector('[data-block=\"lookup-result\"]') || {dataset: {}}).dataset.outcome === o", arg=outcome, timeout=30000)
    page.wait_for_timeout(300)


def _wait_isin(page):
    page.wait_for_selector('[data-block="isin-notice"]', timeout=30000)
    page.wait_for_timeout(300)


def _query_by_enter(page, raw, outcome):
    _input(page).fill(raw)
    page.keyboard.press("Enter")
    _wait_outcome(page, outcome)


def _scenario(page, sid):
    """用真的 UI 操作切換情境（selectbox）；選單偶爾在重跑中沒打開，所以最多重試三次。"""
    label = fake.SCENARIOS[sid][0]
    for attempt in range(3):
        page.wait_for_timeout(500)
        page.locator('[data-testid="stSelectbox"] input').first.click()
        try:
            page.wait_for_selector("[role=option]", timeout=6000)
            break
        except Exception:  # noqa: BLE001 - 重試前先關掉可能殘留的選單
            page.keyboard.press("Escape")
    page.get_by_role("option", name=label, exact=True).click()
    page.wait_for_timeout(900)


def _toggle(page, n):
    page.locator('[data-testid="stCheckbox"] label').nth(n - 1).click()
    page.wait_for_timeout(700)


def _set_conditions(page, wanted):
    """把三個條件勾成 `wanted`（序號集合）；只點需要改的那幾個。"""
    for n in (1, 2, 3):
        if page.locator('[data-testid="stCheckbox"] input').nth(n - 1).is_checked() != (n in wanted):
            _toggle(page, n)


@pytest.fixture(scope="module")
def initial(server_and_browser):
    base, browser = server_and_browser
    out = {}
    for width in WIDTHS:
        o = _open(browser, base, width)
        try:
            out[width] = o.measure()
            out[("requests", width)] = list(o.requests)
        finally:
            o.close()
    return out


# ───────────────────────── 初始畫面 ─────────────────────────

@pytest.mark.parametrize("width", WIDTHS)
def test_initial_page_has_no_overflow_collapsed_details_48px_targets_and_the_right_order(initial, width):
    m = initial[width]
    assert lib.overflow_violations(m) == []
    assert lib.touch_target_violations(m) == [], m["targets"]
    assert lib.details_violations(m) == []
    assert lib.order_violations(m, with_result=False) == [], m["seq"]
    assert lib.static_violations(m) == [] and lib.count_violations(m) == []
    assert m["exp0"]["matched"] is None and "尚未設定條件" in m["exp0"]["text"]
    assert m["outcome"] is None and m["fundRows"] == 0


@pytest.mark.parametrize("width", WIDTHS)
def test_harness_selectbox_height_is_disclosed_and_is_the_only_control_below_48px(initial, width):
    # harness 的 selectbox 是 Streamlit 預設高度（約 40px），未達 48px 觸控下限：據實記錄，不屬 renderer。
    assert initial[width]["selectH"] is not None and 36 <= initial[width]["selectH"] < 48
    assert all(t["h"] >= 47.5 for t in initial[width]["targets"])


@pytest.mark.parametrize("width", WIDTHS)
def test_no_external_request_on_load(initial, server_and_browser, width):
    base, _ = server_and_browser
    urls = initial[("requests", width)]
    assert urls and lib.external_request_violations(urls, base) == []


def test_first_screen_on_a_phone_shows_title_input_isin_note_and_button_above_the_fold(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        m = o.measure()
        assert m["seq"]["button"] is not None and m["seq"]["button"] < 844   # 查詢鈕在首屏內（390×844）
        assert m["seq"]["title"] < m["seq"]["input"] < m["seq"]["isin"] < m["seq"]["button"]
    finally:
        o.close()


# ───────────────────────── 單檔查詢（真的操作） ─────────────────────────

@pytest.mark.parametrize("width", WIDTHS)
def test_each_lookup_outcome_renders_without_overflow_and_with_the_right_content(server_and_browser, width):
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        cases = [("FAKE-OK01", "found", ["FAKE 模擬", fake.FAKE_FOUND_NAME, "◇ 尚未確認", "◇ 資料未備"]),
                 ("FAKE-LOW1", "insufficient", ["資料不足", "◇ 資料未備"]),
                 ("FAKE-ERR1", "failed", ["⛔ 取數失敗", "無法顯示這檔基金"]),
                 ("???", "unrecognized", ["⬜ 無法判定", "（無法辨識格式）"]),
                 ("ABC123", "no_fixture", ["⬜ 無法判定"])]
        for raw, outcome, needles in cases:
            _query_by_enter(o.page, raw, outcome)
            m = o.measure()
            assert lib.structure_violations(m, with_result=True) == [], (raw, lib.structure_violations(m, with_result=True))
            assert all(n in m["cardText"] for n in needles), (raw, m["cardText"])
            assert "已確認" not in m["cardText"] and "◇ 尚未確認" in m["cardText"]
        assert lib.external_request_violations(o.requests, base) == []
    finally:
        o.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_isin_shaped_input_shows_only_the_inactive_notice(server_and_browser, width):
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        _input(o.page).fill("US0378331005")
        o.page.keyboard.press("Enter")
        _wait_isin(o.page)
        m = o.measure()
        assert m["outcome"] is None and "ISIN 目前未啟用" in m["text"] and "US0378331005" not in m["text"]
        assert lib.structure_violations(m, with_result=True) == []
    finally:
        o.close()


@pytest.mark.parametrize("width", (390, 1280))
def test_script_and_html_in_the_input_never_execute_and_are_shown_as_text(server_and_browser, width):
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        payloads = ['<script>window.__xss=1</script>', '<img src=x onerror="window.__xss=2">', '"><b id=xssb>bold</b>',
                    "$x^2$ **b** [a](http://example.invalid) `c`"]
        for raw in payloads:
            _query_by_enter(o.page, raw, "unrecognized")
            m = o.measure()
            assert raw in m["cardText"], (raw, m["cardText"])        # 逐字當成文字顯示
            assert lib.static_violations(m) == [] and lib.overflow_violations(m) == []
            assert o.page.evaluate("() => window.__xss === undefined && !document.getElementById('xssb')")
        assert o.dialogs == [] and lib.external_request_violations(o.requests, base) == []
    finally:
        o.close()


def test_long_input_does_not_overflow(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _query_by_enter(o.page, "A" * 100, "unrecognized")
        assert lib.overflow_violations(o.measure()) == []
    finally:
        o.close()


# ───────────────────────── 鍵盤 ─────────────────────────

def _tab_to(page, predicate_js, limit=15):
    for _ in range(limit):
        page.keyboard.press("Tab")
        if page.evaluate(predicate_js):
            return True
    return False


@pytest.mark.parametrize("width", WIDTHS)
def test_keyboard_tab_to_input_type_enter_and_tab_to_button_enter_give_the_same_visible_result(server_and_browser, width):
    base, browser = server_and_browser
    by_enter, by_button = _open(browser, base, width), _open(browser, base, width)
    try:
        # 路徑 A：Tab 到輸入框 → 輸入 → Enter
        assert _tab_to(by_enter.page, "() => !!document.activeElement && document.activeElement.matches('[data-testid=\"stTextInputRootElement\"] input')")
        by_enter.page.keyboard.type("FAKE-OK01")
        by_enter.page.keyboard.press("Enter")
        _wait_outcome(by_enter.page, "found")
        # 路徑 B：Tab 到輸入框 → 輸入 → Tab 到查詢鈕 → Enter
        assert _tab_to(by_button.page, "() => !!document.activeElement && document.activeElement.matches('[data-testid=\"stTextInputRootElement\"] input')")
        by_button.page.keyboard.type("FAKE-OK01")
        assert _tab_to(by_button.page, "() => !!document.activeElement && !!document.activeElement.closest('[data-testid=\"stFormSubmitButton\"]')", limit=3)
        by_button.page.keyboard.press("Enter")
        _wait_outcome(by_button.page, "found")
        a, b = by_enter.measure(), by_button.measure()
        assert a["cardText"] == b["cardText"] and a["outcome"] == b["outcome"] == "found"
        assert lib.structure_violations(a, with_result=True) == [] and lib.structure_violations(b, with_result=True) == []
        card_visible = by_enter.page.locator('[data-block="lookup-result"]').is_visible()
        assert card_visible
    finally:
        by_enter.close()
        by_button.close()


def test_mouse_click_on_the_button_equals_enter(server_and_browser):
    base, browser = server_and_browser
    click, enter = _open(browser, base, 390), _open(browser, base, 390)
    try:
        _input(click.page).fill("FAKE-LOW1")
        click.page.get_by_role("button", name="查詢").click()
        _wait_outcome(click.page, "insufficient")
        _query_by_enter(enter.page, "FAKE-LOW1", "insufficient")
        assert click.measure()["cardText"] == enter.measure()["cardText"]
    finally:
        click.close()
        enter.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_details_opens_with_click_and_with_the_keyboard_and_neither_overflows(server_and_browser, width):
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        assert lib.details_violations(o.measure()) == []
        o.page.locator('[data-summary="basic-info"]').click()
        o.page.wait_for_timeout(300)
        after = o.measure()
        assert after["details"]["open"] == 1 and lib.overflow_violations(after) == [] and after["mainLinks"] == 0
        o.page.locator('[data-summary="basic-info"]').click()
        o.page.locator('[data-summary="basic-info"]').focus()
        o.page.keyboard.press("Enter")
        o.page.wait_for_timeout(300)
        assert o.measure()["details"]["open"] == 1
    finally:
        o.close()


# ───────────────────────── 下區：情境與條件（真的操作） ─────────────────────────

@pytest.mark.parametrize("width", WIDTHS)
def test_scenarios_and_conditions_change_the_result_and_keep_counts_consistent(server_and_browser, width):
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        _scenario(o.page, "mixed")
        seen = []
        for wanted, expected in (({1, 2, 3}, ("2", "2")), ({1}, ("4", "1")), ({1, 2}, ("2", "2"))):
            _set_conditions(o.page, wanted)
            m = o.measure()
            assert (m["exp0"]["matched"], m["exp0"]["undetermined"]) == expected, wanted
            assert m["fundRows"] == int(expected[0]) + int(expected[1]) and lib.structure_violations(m) == [], lib.structure_violations(m)
            seen.append(m["exp0"]["text"])
        assert len(set(seen)) == 2   # 子集合不同，文案真的跟著變（{1,2,3} 與 {1,2} 的 N／M 相同，文案也相同）
        for sid, expected in (("has_match", ("2", "0")), ("no_match", ("0", "0")), ("undetermined_only", ("0", "3"))):
            _scenario(o.page, sid)
            _set_conditions(o.page, {1, 2, 3})
            m = o.measure()
            assert (m["exp0"]["matched"], m["exp0"]["undetermined"]) == expected, sid
            assert lib.structure_violations(m) == [], (sid, lib.structure_violations(m))
            _set_conditions(o.page, set())   # 全部取消 → 零條件：不展示 N／M、沒有結果列
            m = o.measure()
            assert m["exp0"]["matched"] is None and "尚未設定條件" in m["exp0"]["text"] and m["fundRows"] == 0 and lib.count_violations(m) == []
    finally:
        o.close()


@pytest.mark.parametrize("width", WIDTHS)
def test_source_failure_scenario_shows_failure_wording_without_counts(server_and_browser, width):
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        _scenario(o.page, "source_failed")
        _set_conditions(o.page, {1, 2, 3})
        m = o.measure()
        assert m["failed"] == ["exp0", "exp2", "exp7"] and m["exp0"]["matched"] is None and m["fundRows"] == 0
        assert "⛔ 取數失敗" in m["text"] and "目前條件下" not in m["text"]
        assert lib.structure_violations(m) == [], lib.structure_violations(m)
    finally:
        o.close()


def test_reloading_the_page_returns_to_the_initial_state(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _scenario(o.page, "mixed")
        _set_conditions(o.page, {1, 2})
        _query_by_enter(o.page, "FAKE-OK01", "found")
        o.page.reload(wait_until="networkidle")
        o.page.wait_for_selector('[data-block="basic-info"]', timeout=60000)
        o.page.wait_for_timeout(600)
        m = o.measure()
        assert m["exp0"]["matched"] is None and m["outcome"] is None and lib.structure_violations(m) == []
    finally:
        o.close()


# ───────────────────────── 變異驗證（判定函式必須報紅） ─────────────────────────

def _mutated(server_and_browser, *, width=390, css=None, js=None, setup=None):
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        if setup:
            setup(o.page)
        if css:
            o.page.add_style_tag(content=css)
        if js:
            o.page.evaluate(js)
        o.page.wait_for_timeout(200)
        return o.measure()
    finally:
        o.close()


def test_unmutated_page_passes_the_same_checks(server_and_browser):
    m = _mutated(server_and_browser)
    assert lib.structure_violations(m) == []


def test_mutation_forced_wide_card_is_flagged_as_overflow(server_and_browser):
    m = _mutated(server_and_browser, css=".uv3-card{min-width:900px !important}")
    assert lib.overflow_violations(m)


def test_mutation_submit_button_and_checkbox_and_summary_shrunk_below_48px_are_flagged(server_and_browser):
    css = ('[data-testid="stFormSubmitButton"] button{min-height:20px !important;height:20px !important}'
           '[data-testid="stCheckbox"] label{min-height:20px !important;height:20px !important}'
           '.fs-details > summary{min-height:20px !important;height:20px !important}'
           '[data-testid="stTextInputRootElement"]{min-height:20px !important;height:20px !important}')
    m = _mutated(server_and_browser, css=css)
    kinds = {v[1]["kind"] for v in lib.touch_target_violations(m) if v[0].startswith("觸控")}
    assert kinds >= {"button", "checkbox", "summary", "input"}


def test_mutation_details_open_or_nested_is_flagged(server_and_browser):
    m = _mutated(server_and_browser, js="() => { document.querySelector('details[data-block=\"basic-info\"]').open = true; }")
    assert any("沒有收合" in v[0] for v in lib.details_violations(m))
    m = _mutated(server_and_browser, js="() => { document.querySelector('details[data-block=\"basic-info\"]').insertAdjacentHTML('beforeend', '<details><summary>x</summary></details>'); }")
    assert any("巢狀" in v[0] for v in lib.details_violations(m)) and any("恰好一個" in v[0] for v in lib.details_violations(m))


def test_mutation_forbidden_wording_is_flagged(server_and_browser):
    for word in ("基金不存在", "查無基金", "最佳", "推薦"):
        js = "() => { document.querySelector('[data-block=\"exp0\"]').insertAdjacentHTML('beforeend', '<div>" + word + "</div>'); }"
        m = _mutated(server_and_browser, js=js)
        assert any(word == v[1] for v in lib.static_violations(m) if v[0] == "出現禁用字樣"), word


def test_mutation_wrong_n_in_the_dom_is_flagged(server_and_browser):
    def setup(page):
        _scenario(page, "mixed")
        _set_conditions(page, {1, 2, 3})
    base_m = _mutated(server_and_browser, setup=setup)
    assert lib.count_violations(base_m) == []
    m = _mutated(server_and_browser, setup=setup, js="() => { document.querySelector('[data-block=\"exp0\"]').dataset.matched = '3'; }")
    assert lib.count_violations(m)
    m = _mutated(server_and_browser, setup=setup, js="() => { document.querySelector('[data-fund]').remove(); }")
    assert lib.count_violations(m)


def test_mutation_unescaped_script_in_the_card_is_flagged(server_and_browser):
    def setup(page):
        _query_by_enter(page, "FAKE-OK01", "found")
    js = "() => { document.querySelector('[data-block=\"lookup-result\"]').insertAdjacentHTML('beforeend', '<b>x</b><img src=x>'); }"
    m = _mutated(server_and_browser, setup=setup, js=js)
    assert lib.static_violations(m)


def test_mutation_zero_instead_of_the_missing_wording_in_a_card_is_detectable_in_dom_text(server_and_browser):
    def setup(page):
        _query_by_enter(page, "FAKE-LOW1", "insufficient")
    m = _mutated(server_and_browser, setup=setup)
    assert m["cardText"].count("◇ 資料未備") == 4
    js = "() => { document.querySelector('[data-row=\"mgmt-fee\"]').lastChild.textContent = '0'; }"
    m2 = _mutated(server_and_browser, setup=setup, js=js)
    assert m2["cardText"].count("◇ 資料未備") == 3          # 缺值字樣被 0 取代 → 計數少一個，判定可抓


def test_external_request_checker_flags_a_foreign_host_and_passes_the_local_one():
    assert lib.external_request_violations(["http://127.0.0.1:8501/x", "data:image/png;base64,AA"], "http://127.0.0.1:8501") == []
    assert lib.external_request_violations(["http://127.0.0.1:8501/x", "https://example.invalid/a"], "http://127.0.0.1:8501") == ["https://example.invalid/a"]


def test_a_real_external_request_would_be_caught_by_the_request_listener(server_and_browser):
    """正控：頁面真的發出對外請求時，request 事件監聽會收到，檢查函式會報紅（攔截本身是有效的）。"""
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        o.page.route("https://example.invalid/**", lambda route: route.abort())
        o.page.evaluate("() => { fetch('https://example.invalid/ping').catch(() => {}); }")
        o.page.wait_for_timeout(500)
        assert lib.external_request_violations(o.requests, base) == ["https://example.invalid/ping"]
    finally:
        o.close()
