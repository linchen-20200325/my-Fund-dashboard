# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件 隔離式 FAKE Preview 的瀏覽器級守衛（slow lane；需要 streamlit 與 Chromium）。

390×844 與 1280×800：無橫向溢出、控制項觸控目標 ≥48px、首屏順序、每個狀態的語意與文字、鍵盤 Tab／Enter 與焦點環、
文字／邊框對比（computed style 實測，不寫死色碼）、無外部請求、輸入內容不被當標籤執行、CONFLICT 演示、重新載入回到初始。
CI（環境變數 CI=true）找不到 playwright 或 Chromium → fail，不得 skip（`_ui_v2_chromium.unavailable`）。
變異驗證：注入溢出、縮小觸控目標、移除焦點環、移除 role、插入禁用字樣，判定函式都必須報紅（全在記憶體內現編）。
⚠️ 這裡的變異對象是**判定函式（checker）與 DOM**；真正對 production renderer 的變異在 `test_fund_lookup_cmp_mutations.py`。
真實 Streamlit Cloud、真機、螢幕閱讀器未驗（NOT VERIFIED）。
"""
import pytest

import fund_lookup_cmp_support as S  # noqa: F401

pytestmark = pytest.mark.slow

try:
    import streamlit  # noqa: F401
except ImportError as _exc:    # CI 缺 streamlit 必須 fail，不得靜默 skip（與 AppTest 檔一致）
    import os as _os
    if _os.environ.get("CI", "").strip().lower() == "true":
        pytest.fail(f"[CI] 匯入不到 streamlit：{_exc}（CI 環境必須有完整依賴；此處不得跳過）", pytrace=False)
    pytest.skip(f"本環境匯入不到 streamlit：{_exc}", allow_module_level=True)

import _ui_v2_chromium  # noqa: E402
import fund_lookup_cmp_browser_lib as lib  # noqa: E402

WIDTHS = (390, 1280)
LABEL = "MoneyDJ 基金代碼或 ISIN"
FORM_TEXTS = ['[data-testid="stTextInput"] label', '[data-testid="stFormSubmitButton"] button']
FORM_BORDERS = ['[data-testid="stTextInputRootElement"]', '[data-testid="stFormSubmitButton"] button']
CONTRAST_SPEC = {"borders": [".fl-card", *FORM_BORDERS], "texts": [".fl-card", "[data-block=\"isin-note\"]", *FORM_TEXTS],
                 "inputs": ['[data-testid="stTextInput"] input']}

_ALL_FIVE = list(S.FIVE_ROWS)
# (輸入, 預期 state, 預期 reason, 預期欄位列, 預期欄位狀態, 卡內必須出現的字樣, 預期狀態列角色)
CASES = [
    ("FAKE-OK01", "result", None, _ALL_FIVE, ["value", "value", "value", "value", "missing"],
     ["FAKE 模擬", "FAKE 範例基金甲", "配息型", "2000-01-02", "此欄尚無可顯示的值"], "status"),
    ("FAKE-OK02", "result", None, _ALL_FIVE, ["value", "value", "value", "missing", "missing"], ["累積型", "此欄尚無可顯示的值"], "status"),
    ("FAKE-OK03", "result", None, _ALL_FIVE, ["value", "value", "missing", "missing", "missing"], ["FAKE 範例基金甲"], "status"),
    ("FAKE-FAIL1", "failed", "source_failed", ["input-code"], ["value"], ["⛔ 取數失敗", "這不是對基金身份的判斷", "來源回報取數失敗"], "alert"),
    ("FAKE-COOL1", "failed", "source_cooling", ["input-code"], ["value"], ["⛔ 取數失敗", "暫時冷卻中"], "alert"),
    ("FAKE-IOERR", "failed", "loader_io_error", ["input-code"], ["value"], ["⛔ 取數失敗", "取數連線失敗"], "alert"),
    ("FAKE-PAGE1", "unmatched", "unrecognized_page", ["input-code"], ["value"], ["⬜ 無法判定", "頁面無法確認是這一檔", "頁面格式無法辨識"], "status"),
    ("FAKE-PAGE2", "unmatched", "no_page", ["input-code"], ["value"], ["⬜ 無法判定", "找不到對應頁面", "這不是對基金身份的判斷"], "status"),
    ("FAKE-PAGE3", "unmatched", "source_not_listed", ["input-code"], ["value"], ["來源沒有列出這一檔"], "status"),
    ("FAKE-NAME1", "unmatched", "name_unconfirmed", ["input-code"], ["value"], ["頁面上的基金名稱無法確認"], "status"),
    ("ABC123", "unmatched", "no_page", ["input-code"], ["value"], ["ABC123", "找不到對應頁面"], "status"),
    ("FAKE-REJ1", "blocked", "key_rejected", ["input-code"], ["value"], ["輸入未通過檢查，未發出查詢", "這個代碼無法用於查詢"], "alert"),
    ("   ", "blocked", "blank", [], [], ["請先輸入基金代碼"], "alert"),
    ("US0378331005", "blocked", "isin_shape", [], [], ["ISIN 目前未啟用", "未用 ISIN 取數、未猜測任何代碼"], "alert"),
    ("http://x.example/a", "blocked", "url_shape", [], [], ["請輸入基金代碼，不要貼網址"], "alert"),
    ("A<B>C", "blocked", "code_format", ["input-code"], ["value"], ["A<B>C", "代碼格式不符"], "alert"),
    ("A$B", "blocked", "code_format", ["input-code"], ["value"], ["A$B"], "alert"),
    ("L" * 100, "blocked", "code_format", [], [], ["代碼格式不符"], "alert"),
]


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
    def __init__(self, ctx, page, requests, dialogs):
        self.ctx, self.page, self.requests, self.dialogs = ctx, page, requests, dialogs

    def measure(self):
        return self.page.evaluate(lib.MEASURE_JS)

    def contrast(self):
        return self.page.evaluate(lib.CONTRAST_JS, CONTRAST_SPEC)

    def close(self):
        self.ctx.close()


def _open(browser, base, width):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    requests, dialogs = [], []
    page.on("request", lambda r: requests.append(r.url))
    page.on("dialog", lambda d: (dialogs.append(d.message), d.dismiss()))
    page.goto(base, wait_until="networkidle")
    page.wait_for_selector('[data-block="lookup-idle"]', timeout=60000)
    page.wait_for_timeout(600)
    return Opened(ctx, page, requests, dialogs)


def _card_text(page):
    return page.evaluate("() => (document.querySelector('[data-block=\"lookup-result\"], [data-block=\"lookup-idle\"]') || {}).innerText || null")


def _wait_card(page, state, reason, before):
    page.wait_for_function(
        "([s, r, b]) => { const c = document.querySelector('[data-block=\"lookup-result\"]'); return !!c && c.dataset.state === s && (c.dataset.reason || null) === r && c.innerText !== b; }",
        arg=[state, reason, before], timeout=30000)
    page.wait_for_timeout(300)


def _query_by_enter(page, raw, state, reason):
    before = _card_text(page)
    page.get_by_label(LABEL).fill(raw)
    page.keyboard.press("Enter")
    _wait_card(page, state, reason, before)


@pytest.fixture(scope="module")
def initial(server_and_browser):
    base, browser = server_and_browser
    out = {}
    for width in WIDTHS:
        o = _open(browser, base, width)
        try:
            out[width] = (o.measure(), o.contrast(), list(o.requests))
        finally:
            o.close()
    return out


@pytest.fixture(scope="module")
def sweep(server_and_browser):
    """每個寬度各開一頁，依序送出全部案例，收集量測、對比與請求（一次掃完，測試只斷言）。"""
    base, browser = server_and_browser
    out = {}
    for width in WIDTHS:
        o = _open(browser, base, width)
        try:
            rows = {}
            for raw, state, reason, *_ in CASES:
                _query_by_enter(o.page, raw, state, reason)
                rows[raw] = (o.measure(), o.contrast())
            out[width] = (rows, list(o.requests), list(o.dialogs))
        finally:
            o.close()
    return out


# ───────────────────────── 初始畫面 ─────────────────────────

@pytest.mark.parametrize("width", WIDTHS)
def test_initial_page_shows_only_not_queried_with_no_overflow_48px_targets_and_the_right_order(initial, width):
    m, _c, _r = initial[width]
    assert lib.overflow_violations(m) == []
    assert lib.touch_target_violations(m) == [], m["targets"]
    assert lib.order_violations(m) == [], m["seq"]
    assert lib.static_violations(m) == [] and lib.a11y_violations(m, expect_alert=False) == []
    assert m["block"] == "lookup-idle" and m["state"] == "idle" and m["rowNames"] == [] and m["fakeTags"] == 0
    assert m["cardText"].strip() == "尚未查詢"


@pytest.mark.parametrize("width", WIDTHS)
def test_harness_selectbox_height_is_disclosed_and_all_component_controls_are_at_least_48px(initial, width):
    # harness 的 selectbox 是 Streamlit 預設高度（約 40px），未達 48px：據實記錄，屬 harness 不屬元件。
    m, _c, _r = initial[width]
    assert m["selectH"] is not None and 36 <= m["selectH"] < 48
    assert all(t["h"] >= 47.5 and t["w"] >= 47.5 for t in m["targets"])


@pytest.mark.parametrize("width", WIDTHS)
def test_no_external_request_on_load(initial, server_and_browser, width):
    base, _ = server_and_browser
    urls = initial[width][2]
    assert urls and lib.external_request_violations(urls, base) == []


def test_first_screen_on_a_phone_shows_title_input_isin_note_button_and_the_card_above_the_fold(initial):
    m, _c, _r = initial[390]
    assert m["seq"]["button"] < 844 and m["seq"]["card"] < 844
    assert m["seq"]["title"] < m["seq"]["input"] < m["seq"]["isin"] < m["seq"]["button"] < m["seq"]["card"]


@pytest.mark.parametrize("width", WIDTHS)
def test_initial_text_and_isin_note_contrast_is_at_least_4_5(initial, width):
    _m, c, _r = initial[width]
    assert lib.text_violations(c, ".fl-card") == [] and lib.text_violations(c, '[data-block="isin-note"]') == []
    assert lib.border_violations(c, ".fl-card") == []


@pytest.mark.parametrize("width", WIDTHS)
def test_form_controls_label_input_text_button_text_and_borders_meet_contrast(initial, width):
    _m, c, _r = initial[width]
    for sel in FORM_TEXTS:
        assert lib.text_violations(c, sel) == [], (sel, lib.text_violations(c, sel))
    assert lib.input_violations(c, '[data-testid="stTextInput"] input') == []
    for sel in FORM_BORDERS:
        assert lib.border_violations(c, sel) == [], (sel, lib.border_violations(c, sel))


# ───────────────────────── 每個狀態（真的操作） ─────────────────────────

@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("case", CASES, ids=[c[0][:14] or "blank" for c in CASES])
def test_each_state_renders_the_right_semantics_without_overflow(sweep, width, case):
    raw, state, reason, rows, fstatus, needles, role = case
    m, _c = sweep[width][0][raw]
    assert lib.structure_violations(m, expect_alert=role == "alert") == [], (raw, lib.structure_violations(m, expect_alert=role == "alert"))
    assert m["state"] == state and m["reason"] == reason and m["statusRole"] == role
    assert m["rowNames"] == rows and m["rowStatus"] == fstatus, (raw, m["rowNames"], m["rowStatus"])
    assert all(n in m["cardText"] for n in needles), (raw, m["cardText"])
    assert "尚未查詢" not in m["cardText"]                                   # 查過之後『尚未查詢』卡消失
    for w in S.FORBIDDEN_WORDS:
        assert w not in m["cardText"], (raw, w)
    # 欄位標籤只有客戶指定的五欄，且依序（RESULT 全五欄；其他狀態最多只有輸入代碼）
    assert m["labels"] == [S.FIVE_LABELS[S.FIVE_ROWS.index(n)] for n in rows], (raw, m["labels"])
    if state != "result":
        assert "基金名稱" not in m["labels"] and "配息方式" not in m["labels"] and "FAKE 範例基金甲" not in m["cardText"]   # 非 RESULT 結構上不帶任何欄位值
    if state == "failed":
        assert "不存在" not in m["cardText"] and "⬜ 無法判定" not in m["cardText"]    # 取數失敗不與無法判定混用
    if state == "unmatched":
        assert "⛔" not in m["cardText"]                                          # 無法判定不與取數失敗混用


@pytest.mark.parametrize("width", WIDTHS)
def test_blocked_inputs_that_must_not_be_echoed_do_not_appear_in_the_page_text(sweep, width):
    for raw in ("US0378331005", "http://x.example/a"):
        m, _c = sweep[width][0][raw]
        assert raw not in m["cardText"] and "x.example" not in m["cardText"] and m["rowNames"] == []
    m, _c = sweep[width][0]["L" * 100]
    assert "LLLLL" not in m["cardText"]


@pytest.mark.parametrize("width", WIDTHS)
def test_user_input_is_shown_literally_and_never_rendered_as_markup(sweep, width):
    for raw in ("A<B>C", "A$B"):
        m, _c = sweep[width][0][raw]
        assert raw in m["cardText"] and m["scripts"] == 0 and m["imgs"] == 0 and m["bold"] == 0


@pytest.mark.parametrize("width", WIDTHS)
def test_every_state_text_and_card_border_contrast_is_measured_and_passes(sweep, width):
    rows = sweep[width][0]
    for raw, (_m, c) in rows.items():
        assert lib.text_violations(c, ".fl-card") == [], (raw, lib.text_violations(c, ".fl-card"))
        assert lib.border_violations(c, ".fl-card") == [], (raw, lib.border_violations(c, ".fl-card"))
        # 狀態的實測樣式也是依 state 套的：dashed／solid 都量得到
        assert c["borders"] and all(min(b["widths"]) >= 1 for b in c["borders"])
        for sel in FORM_BORDERS:
            assert lib.border_violations(c, sel) == [], (raw, sel)


@pytest.mark.parametrize("width", WIDTHS)
def test_unmatched_and_blocked_cards_are_dashed_and_failed_is_solid_so_states_are_not_color_only(sweep, width):
    rows = sweep[width][0]

    def styles(raw):
        return {s for b in rows[raw][1]["borders"] if b["sel"] == ".fl-card" for s in b["styles"]}
    assert styles("FAKE-PAGE1") == {"dashed"} and styles("US0378331005") == {"dashed"}
    assert styles("FAKE-FAIL1") == {"solid"} and styles("FAKE-OK01") == {"solid"}


@pytest.mark.parametrize("width", WIDTHS)
def test_no_external_request_and_no_dialog_after_all_queries(sweep, server_and_browser, width):
    base, _ = server_and_browser
    _rows, urls, dialogs = sweep[width]
    assert lib.external_request_violations(urls, base) == [] and dialogs == []


# ───────────────────────── 鍵盤與焦點 ─────────────────────────

def _tab_to(page, predicate_js, limit=15):
    for _ in range(limit):
        page.keyboard.press("Tab")
        if page.evaluate(predicate_js):
            return True
    return False


IN_INPUT = "() => !!document.activeElement && document.activeElement.matches('[data-testid=\"stTextInputRootElement\"] input')"
IN_BUTTON = "() => !!document.activeElement && !!document.activeElement.closest('[data-testid=\"stFormSubmitButton\"]')"


@pytest.mark.parametrize("width", WIDTHS)
def test_keyboard_tab_order_is_input_then_button_and_enter_or_button_give_the_same_visible_result(server_and_browser, width):
    base, browser = server_and_browser
    by_enter, by_button = _open(browser, base, width), _open(browser, base, width)
    try:
        assert _tab_to(by_enter.page, IN_INPUT)
        assert lib.focus_violations(by_enter.contrast()) == []                       # 輸入框焦點環
        by_enter.page.keyboard.type("FAKE-OK01")
        by_enter.page.keyboard.press("Enter")
        _wait_card(by_enter.page, "result", None, "尚未查詢")
        assert _tab_to(by_button.page, IN_INPUT)
        by_button.page.keyboard.type("FAKE-OK01")
        by_button.page.keyboard.press("Tab")
        assert by_button.page.evaluate(IN_BUTTON)                                    # Tab 順序：輸入框的下一個就是查詢鈕
        assert lib.focus_violations(by_button.contrast()) == []                      # 查詢鈕焦點環
        by_button.page.keyboard.press("Shift+Tab")
        assert by_button.page.evaluate(IN_INPUT)                                     # Shift+Tab 回到輸入框
        by_button.page.keyboard.press("Tab")
        by_button.page.keyboard.press("Enter")
        _wait_card(by_button.page, "result", None, "尚未查詢")
        a, b = by_enter.measure(), by_button.measure()
        assert a["cardText"] == b["cardText"] and a["state"] == b["state"] == "result"
        assert lib.structure_violations(a) == [] and lib.structure_violations(b) == []
    finally:
        by_enter.close()
        by_button.close()


def test_mouse_click_on_the_button_equals_enter(server_and_browser):
    base, browser = server_and_browser
    click, enter = _open(browser, base, 390), _open(browser, base, 390)
    try:
        click.page.get_by_label(LABEL).fill("FAKE-FAIL1")
        click.page.get_by_role("button", name="查詢").click()
        _wait_card(click.page, "failed", "source_failed", "尚未查詢")
        _query_by_enter(enter.page, "FAKE-FAIL1", "failed", "source_failed")
        assert click.measure()["cardText"] == enter.measure()["cardText"]
    finally:
        click.close()
        enter.close()


def test_the_result_card_has_no_focusable_elements_so_tab_never_lands_inside_it(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _query_by_enter(o.page, "FAKE-OK01", "result", None)
        assert o.measure()["interactiveInCard"] == 0
        o.page.get_by_label(LABEL).focus()
        for _ in range(6):
            o.page.keyboard.press("Tab")
            assert not o.page.evaluate("() => !!document.activeElement && !!document.activeElement.closest('[data-block=\"lookup-result\"]')")
    finally:
        o.close()


# ───────────────────────── CONFLICT 演示與重新載入 ─────────────────────────

def _mode(page, label):
    for _ in range(3):
        page.wait_for_timeout(500)
        page.locator('[data-testid="stSelectbox"] input').first.click()
        try:
            page.wait_for_selector("[role=option]", timeout=6000)
            break
        except Exception:  # noqa: BLE001 - 重試前先關掉可能殘留的選單
            page.keyboard.press("Escape")
    page.get_by_role("option", name=label, exact=True).click()
    page.wait_for_timeout(900)


@pytest.mark.parametrize("width", WIDTHS)
def test_conflict_fields_render_with_their_own_wording_and_marker_without_overflow(server_and_browser, width):
    import fund_lookup_fake_inputs as fake
    base, browser = server_and_browser
    o = _open(browser, base, width)
    try:
        label = "CONFLICT 欄位：直接建構 ViewModel（現行 L2 不可達，非 adapter 結果）"
        _mode(o.page, label)
        o.page.wait_for_function("() => (document.querySelector('[data-block=\"lookup-result\"]') || {dataset: {}}).dataset.state === 'result'", timeout=30000)
        m = o.measure()
        c = o.contrast()
        assert lib.structure_violations(m) == [], lib.structure_violations(m)
        assert m["rowNames"] == _ALL_FIVE and m["rowStatus"] == ["value", "value", "conflict", "conflict", "missing"]
        assert m["cardText"].count("此欄的來源值不一致，未選用任何一個") == 2 and fake.CONFLICT_CODE in m["cardText"]
        assert "此欄尚無可顯示的值" in m["cardText"]                                 # CONFLICT 與 MISSING 文案不同
        assert lib.text_violations(c, ".fl-card") == [] and lib.border_violations(c, ".fl-card") == []
    finally:
        o.close()


def test_reloading_the_page_returns_to_the_not_queried_state(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _query_by_enter(o.page, "FAKE-OK01", "result", None)
        o.page.reload(wait_until="networkidle")
        o.page.wait_for_selector('[data-block="lookup-idle"]', timeout=60000)
        o.page.wait_for_timeout(600)
        m = o.measure()
        assert m["block"] == "lookup-idle" and m["cardText"].strip() == "尚未查詢" and m["inputValue"] == ""
    finally:
        o.close()


# ───────────────────────── 變異驗證（判定函式必須報紅） ─────────────────────────

def _mutated(server_and_browser, *, css=None, js=None, query=None):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        if query:
            _query_by_enter(o.page, *query)
        if css:
            o.page.add_style_tag(content=css)
        if js:
            o.page.evaluate(js)
        o.page.wait_for_timeout(200)
        return o.measure()
    finally:
        o.close()


def test_unmutated_page_passes_the_same_checks(server_and_browser):
    assert lib.structure_violations(_mutated(server_and_browser, query=("FAKE-OK01", "result", None))) == []


def test_mutation_forced_wide_card_is_flagged_as_overflow(server_and_browser):
    assert lib.overflow_violations(_mutated(server_and_browser, css=".fl-card{min-width:900px !important}"))


def test_mutation_submit_button_and_input_shrunk_below_48px_are_flagged(server_and_browser):
    css = ('[data-testid="stFormSubmitButton"] button{min-height:20px !important;height:20px !important}'
           '[data-testid="stTextInputRootElement"]{min-height:20px !important;height:20px !important}')
    kinds = {v[1]["kind"] for v in lib.touch_target_violations(_mutated(server_and_browser, css=css)) if v[0].startswith("觸控")}
    assert kinds >= {"button", "input"}


def test_negative_control_external_request_checker_turns_red_on_foreign_urls():
    base = "http://127.0.0.1:8501"
    assert lib.external_request_violations([base + "/x", "data:text/plain,a", "blob:" + base + "/id"], base) == []
    for url in ("https://example.invalid/a", "http://127.0.0.1:8501.evil.example/", "http://127.0.0.1:9999/", "ws://evil.example/s", "blob:null/x", "blob:https://evil.example/y"):
        assert lib.external_request_violations([url], base) == [url], url


def test_negative_control_order_checker_turns_red_on_a_shuffled_layout():
    ok = {"title": 10, "input": 60, "isin": 120, "button": 150, "card": 200}
    assert lib.order_violations({"seq": ok}) == []
    for swap in (("input", "title"), ("isin", "button"), ("card", "input")):
        bad = dict(ok)
        bad[swap[0]], bad[swap[1]] = ok[swap[1]], ok[swap[0]]
        assert lib.order_violations({"seq": bad}), swap
    assert lib.order_violations({"seq": {**ok, "card": None}})
    assert lib.order_violations({"seq": {**ok, "button": 60}})          # 同一高度＝順序不明


def test_mutation_removing_role_or_label_target_or_status_text_is_flagged(server_and_browser):
    m = _mutated(server_and_browser, query=("FAKE-FAIL1", "failed", "source_failed"),
                 js="() => { const c = document.querySelector('[data-block=\"lookup-result\"]'); c.removeAttribute('role'); c.removeAttribute('aria-labelledby'); }")
    assert any("region" in v[0] for v in lib.a11y_violations(m, expect_alert=True))
    m = _mutated(server_and_browser, query=("FAKE-FAIL1", "failed", "source_failed"),
                 js="() => { document.querySelector('[data-live]').setAttribute('role', 'status'); }")
    assert any("角色" in v[0] for v in lib.a11y_violations(m, expect_alert=True))
    m = _mutated(server_and_browser, query=("FAKE-FAIL1", "failed", "source_failed"),
                 js="() => { document.querySelector('[data-row=\"status\"]').innerHTML = ''; }")
    assert any("沒有文字" in v[0] for v in lib.a11y_violations(m, expect_alert=True))


def test_mutation_extra_reason_note_outside_the_live_region_is_flagged(server_and_browser):
    m = _mutated(server_and_browser, query=("FAKE-FAIL1", "failed", "source_failed"),
                 js="() => { const l = document.querySelector('[data-live]'); const n = l.querySelector('[data-note=\"extra\"]'); l.after(n); }")
    assert any("live region" in v[0] for v in lib.a11y_violations(m, expect_alert=True))


def test_mutation_forbidden_word_and_inserted_link_are_flagged(server_and_browser):
    m = _mutated(server_and_browser, query=("FAKE-OK01", "result", None),
                 js="() => { document.querySelector('[data-block=\"lookup-result\"]').insertAdjacentHTML('beforeend', '<div>' + '基金' + '不存在' + '<a href=\"#x\">x</a></div>'); }")
    kinds = {v[0] for v in lib.static_violations(m)}
    assert {"出現禁用字樣", "主區出現連結"} <= kinds


def test_mutation_removing_the_focus_ring_is_flagged(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        assert _tab_to(o.page, IN_INPUT)
        assert lib.focus_violations(o.contrast()) == []
        o.page.add_style_tag(content="*:focus,*:focus-visible{outline:none !important}")
        o.page.wait_for_timeout(200)
        assert lib.focus_violations(o.contrast())
    finally:
        o.close()


def test_mutation_low_contrast_text_and_border_are_flagged(server_and_browser):
    base, browser = server_and_browser
    o = _open(browser, base, 390)
    try:
        _query_by_enter(o.page, "FAKE-FAIL1", "failed", "source_failed")
        o.page.add_style_tag(content=".fl-card,.fl-card *{color:#bbbbbb !important} .fl-card{border-color:#eeeeee !important}")
        o.page.wait_for_timeout(200)
        c = o.contrast()
        assert lib.text_violations(c, ".fl-card") and lib.border_violations(c, ".fl-card")
    finally:
        o.close()
