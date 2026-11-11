# -*- coding: utf-8 -*-
"""雙模式隔離 PoC：真實瀏覽器（Playwright／Chromium）測試。標 `slow`（自己起 streamlit；CI slow lane 有 chromium）。

三寬度（390／768／1280）× 兩模式：computed style（頁底／卡面／字／邊／原生 radio、expander、button、disabled、hover、focus、側欄、chip、SVG）、
無頁級水平溢位、圖寬 ≤ 720、chip 有符號＋字樣、缺資料不出現數字、滑鼠與鍵盤都能切模式、切換後其他 widget 狀態保留、重載回預設（session-only）。
色值一律由 `poc_palettes`（單一來源）轉成 rgb 後與瀏覽器 computed style 比對，不在測試裡另寫色碼。
負控：測試內對已載入頁面注入破壞性 CSS，斷言同一組判定函式「真的會報」。
"""
import os
import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE.parents[1] / "poc" / "dual_theme_isolated"))

pytest.importorskip("streamlit", reason="本環境匯入不到 streamlit")

import poc_dual_theme_browser_lib as L  # noqa: E402  （同時把 tests/ui_v2 放進 sys.path）
import _ui_v2_chromium  # noqa: E402  找 Chromium；CI 找不到要 fail
import poc_dual_theme_contrast_lib as cl  # noqa: E402
import poc_palettes as pal  # noqa: E402


def _rgb(hexv: str):
    r, g, b, _ = cl.parse_color(hexv)
    return (round(r), round(g), round(b))


def _css_rgb(css: str):
    r, g, b, a = cl.parse_color(css)
    return (round(r), round(g), round(b))


@pytest.fixture(scope="module")
def env():
    api = _ui_v2_chromium.import_sync_api()
    with _ui_v2_chromium.streamlit_server(L.APP) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


@pytest.fixture
def page_at(env):
    base, browser = env
    opened = []

    def open_(width, mode="light"):
        ctx, page = L.open_page(browser, base, width)
        opened.append(ctx)
        if mode == "dark":
            L.switch_mode(page, "dark")
        return page

    yield open_
    for c in opened:
        c.close()


# ───────────────────────── computed style 判定（可被負控重用） ─────────────────────────

_PROBE = """(sel) => { const e = document.querySelector(sel); if (!e) return null; const c = getComputedStyle(e);
  return {bg: c.backgroundColor, color: c.color, border: c.borderTopColor, borderW: c.borderTopWidth, stroke: c.stroke, fill: c.fill, cursor: c.cursor,
          colorScheme: c.colorScheme}; }"""

_RADIO_CHART = '.st-key-poc-card-chart label[data-testid="stRadioOption"]'
_IND = " > div > div > div:first-child"


def style_mismatches(page, p) -> list:
    """目前頁面的 computed style 與 palette 不符之處（空 list ＝ 全部吻合）。"""
    t = p["tones"]
    checks = [
        ("app 底", ".stApp", "bg", p["page_bg"]),
        ("頁首底", '[data-testid="stHeader"]', "bg", p["page_bg"]),
        ("主標題字", '[data-testid="stMain"] h1', "color", p["text"]),
        ("卡片面", ".st-key-poc-card-chart", "bg", p["surface"]),
        ("卡片邊", ".st-key-poc-card-chart", "border", p["card_border"]),
        ("次要文字", '.poc-note[data-field="chart_note"]', "color", p["text2"]),
        ("radio 選取圓點", f'{_RADIO_CHART}[data-selected="true"]{_IND}', "bg", p["primary"]),
        ("radio 未選圓環", f'{_RADIO_CHART}:not([data-selected="true"]){_IND}', "bg", p["control_border"]),
        ("radio 標籤字", f"{_RADIO_CHART} p", "color", p["text"]),
        ("expander 邊", '[data-testid="stExpander"] details', "border", p["card_border"]),
        ("expander 底", '[data-testid="stExpander"] details', "bg", p["surface"]),
        ("expander 字", '[data-testid="stExpander"] summary p', "color", p["text"]),
        ("button 底", '.st-key-poc-card-disabled [data-testid="stBaseButton-secondary"]:not(:disabled)', "bg", p["surface"]),
        ("button 邊", '.st-key-poc-card-disabled [data-testid="stBaseButton-secondary"]:not(:disabled)', "border", p["control_border"]),
        ("disabled button 字", '.st-key-poc-card-disabled [data-testid="stBaseButton-secondary"]:disabled p', "color", p["disabled_text"]),
        ("disabled radio 字", '.st-key-poc-card-disabled label[data-testid="stRadioOption"] p', "color", p["disabled_text"]),
        ("側欄底", '[data-testid="stSidebar"]', "bg", p["sidebar_bg"]),
        ("側欄字", '[data-testid="stSidebar"] p', "color", p["sidebar_text"]),
        ("圖 甲 線", "svg.poc-chart path.poc-line:not(.poc-dash)", "stroke", p["primary"]),
        ("圖 乙 虛線", "svg.poc-chart path.poc-dash", "stroke", p["text"]),
        ("圖 刻度字", "svg.poc-chart text.poc-tick", "fill", p["text"]),
    ]
    for key, kind in (("attention", "neutral"), ("missing", "grey"), ("undetermined", "grey"), ("failed", "red"), ("stale", "yellow"), ("neutral", "neutral")):
        sel = f'.st-key-poc-card-summary .poc-chip[data-status-key="{key}"]'
        checks += [(f"chip {key} 字", sel, "color", t[kind]["text"]), (f"chip {key} 底", sel, "bg", t[kind]["background"]),
                   (f"chip {key} 邊", sel, "border", t[kind]["border"])]
    bad = []
    for name, sel, prop, want in checks:
        got = page.evaluate(_PROBE, sel)
        if got is None:
            bad.append(f"{name}: 找不到 {sel}")
        elif _css_rgb(got[prop]) != _rgb(want):
            bad.append(f"{name}: 期望 {_rgb(want)}，實得 {got[prop]}")
    scheme = page.evaluate(_PROBE, "html")["colorScheme"]
    if scheme != p["color_scheme"]:
        bad.append(f"color-scheme: 期望 {p['color_scheme']}，實得 {scheme}")
    return bad


def assert_styles(page, p, timeout_ms=4000):
    """輪詢到 computed style 全部吻合（Streamlit 原生元件有 CSS transition；切換當下立刻量會量到過渡中的值）。逾時則以最後一次的不符清單失敗。"""
    waited, bad = 0, style_mismatches(page, p)
    while bad and waited < timeout_ms:
        page.wait_for_timeout(250)
        waited += 250
        bad = style_mismatches(page, p)
    assert bad == [], bad


def overflow_problems(page) -> list:
    m = page.evaluate(L.JS_LAYOUT)
    bad = []
    if m["scrollW"] > m["clientW"] + 1:
        bad.append(f"頁級水平溢位：scrollWidth {m['scrollW']} > clientWidth {m['clientW']}")
    if m["bodyScrollW"] > m["clientW"] + 1:
        bad.append(f"body 水平溢位：{m['bodyScrollW']} > {m['clientW']}")
    # Streamlit 的主區自己是捲動容器：寬內容會在 stMain 內產生水平捲動，documentElement 看不到 —— 兩者都要查
    if m["mainScrollW"] > m["mainClientW"] + 1:
        bad.append(f"主區水平溢位：stMain scrollWidth {m['mainScrollW']} > clientWidth {m['mainClientW']}")
    if m["viewScrollW"] > m["viewClientW"] + 1:
        bad.append(f"view container 水平溢位：{m['viewScrollW']} > {m['viewClientW']}")
    if m["svgW"] is not None and not (0 < m["svgW"] <= 720.5):
        bad.append(f"圖寬 {m['svgW']} 不在 (0, 720]")
    return bad


# ───────────────────────── 預設、computed style、三寬度 × 兩模式 ─────────────────────────

@pytest.mark.parametrize("width", L.WIDTHS)
def test_default_is_light_then_dark_then_light_computed_styles(page_at, width):
    page = page_at(width)
    assert L.mode_of(page) == "light", "新 session 預設必須是淺色"
    assert_styles(page, pal.LIGHT)
    L.switch_mode(page, "dark")
    assert_styles(page, pal.DARK)
    L.switch_mode(page, "light")
    assert_styles(page, pal.LIGHT)  # 切回淺色後必須完全回到淺色（沒有殘留暗色）


@pytest.mark.parametrize("mode", L.MODES)
@pytest.mark.parametrize("width", L.WIDTHS)
def test_layout_overflow_chart_width_and_chips(page_at, width, mode):
    page = page_at(width, mode)
    assert overflow_problems(page) == []
    m = page.evaluate(L.JS_LAYOUT)
    assert m["svgW"] > 0
    chips = page.evaluate("""() => Array.from(document.querySelectorAll('.st-key-poc-card-summary .poc-chip')).map(e => [e.dataset.statusKey, e.innerText.trim()])""")
    assert len(chips) == 6
    for key, text in chips:
        assert re.match(r"^[^\w\s]", text) and len(text) > 2 and re.search(r"[一-鿿]", text), f"chip 需符號＋字樣：{key} {text!r}"
    # 所有 chip／狀態文字都在可視寬度內（沒有被切掉）
    out = page.evaluate("""() => Array.from(document.querySelectorAll('.poc-chip')).filter(e => { const r = e.getBoundingClientRect(); return r.right > innerWidth + 1 || r.left < -1; }).length""")
    assert out == 0


@pytest.mark.parametrize("mode", L.MODES)
@pytest.mark.parametrize("width", L.WIDTHS)
def test_missing_state_has_no_numeric_and_no_chart(page_at, width, mode):
    page = page_at(width, mode)
    page.get_by_text("丙（資料未備示範）").first.click()
    page.wait_for_selector('[data-field="chart_missing"]', timeout=15000)
    page.wait_for_timeout(300)
    text = page.inner_text('[data-field="chart_missing"]')
    assert "◇ 資料未備" in text
    assert not re.search(r"\d", text), f"缺資料不得有數字：{text!r}"
    assert page.locator("svg.poc-chart").count() == 0, "缺資料不得畫圖"
    for state in ("missing", "failed", "stale"):
        t = page.inner_text(f'.poc-card-html[data-poc-state="{state}"] .poc-chip')
        assert re.match(r"^[^\w\s]", t), t
    assert not re.search(r"\d", page.inner_text('.poc-card-html[data-poc-state="missing"]').replace("台股示範", "")), "缺資料卡不得出現數字"
    assert overflow_problems(page) == []


# ───────────────────────── 切換：滑鼠、鍵盤、狀態保留、session-only ─────────────────────────

@pytest.mark.parametrize("width", L.WIDTHS)
def test_switch_by_mouse_keeps_other_widget_states(page_at, width):
    page = page_at(width)
    page.get_by_text("甲", exact=True).first.click()
    page.get_by_text("3M", exact=True).first.click()
    page.wait_for_timeout(500)
    sel_before = page.evaluate("""() => Array.from(document.querySelectorAll('.st-key-poc-card-chart label[data-selected="true"]')).map(e => e.innerText.trim())""")
    assert sel_before == ["甲", "3M"], sel_before
    for mode in ("dark", "light", "dark", "light"):
        L.switch_mode(page, mode)
        sel = page.evaluate("""() => Array.from(document.querySelectorAll('.st-key-poc-card-chart label[data-selected="true"]')).map(e => e.innerText.trim())""")
        assert sel == ["甲", "3M"], (mode, sel)
        assert L.mode_of(page) == mode


@pytest.mark.parametrize("width", (390, 1280))
def test_switch_by_keyboard(page_at, width):
    page = page_at(width)
    # Tab 到模式 radio（頁面第一個可聚焦的 radio），ArrowRight 選下一項
    page.focus('.st-key-poc-card-switch input[type=radio][tabindex="0"]')
    page.keyboard.press("ArrowRight")
    page.wait_for_function("() => (document.querySelector('style[data-poc-theme]')||{getAttribute:()=>null}).getAttribute('data-poc-theme') === 'dark'", timeout=15000)
    page.wait_for_timeout(400)
    assert_styles(page, pal.DARK)
    page.focus('.st-key-poc-card-switch input[type=radio][tabindex="0"]')
    page.keyboard.press("ArrowLeft")
    page.wait_for_function("() => (document.querySelector('style[data-poc-theme]')||{getAttribute:()=>null}).getAttribute('data-poc-theme') === 'light'", timeout=15000)
    page.wait_for_timeout(400)
    assert_styles(page, pal.LIGHT)


def test_reload_returns_to_default_light_session_only(page_at):
    """瀏覽器重載＝新 session ⇒ 回到預設淺色。這是 PoC 的**已知、預期**行為（DEC T3：session-only；永久記憶未核准），不是 bug 也不是持久化。"""
    page = page_at(1280, "dark")
    assert L.mode_of(page) == "dark"
    page.reload(wait_until="networkidle")
    page.wait_for_selector('[data-field="mode_state"]', timeout=60000)
    page.wait_for_timeout(800)
    assert L.mode_of(page) == "light"
    # PoC 沒有寫任何 browser storage／cookie：切換前後的 storage 鍵與 cookie 名稱完全相同（Streamlit 自己的 xsrf cookie／內部鍵不算 PoC 寫入）
    snap = "() => [Object.entries(localStorage).sort(), Object.entries(sessionStorage).sort(), document.cookie.split('; ').map(c => c.split('=')[0]).sort()]"
    before = page.evaluate(snap)
    L.switch_mode(page, "dark")
    L.switch_mode(page, "light")
    assert page.evaluate(snap) == before, "切換模式不得新增任何 storage 鍵或 cookie"
    # Streamlit 自己會寫 `stActiveTheme-…`（它的 app-menu 主題選擇；與 PoC 無關，值在切換前後不變＝PoC 沒動它）；其餘鍵不得含 poc／theme／mode
    for group in before:
        names = [(k if isinstance(k, str) else k[0]) for k in group]
        assert not [k for k in names if ("poc" in k.lower() or "theme" in k.lower() or "mode" in k.lower()) and not k.startswith("stActiveTheme")], before
    assert "theme" not in page.url and "mode" not in page.url, "不得用 URL／query 參數保存模式"


def test_two_contexts_are_independent_sessions(env):
    base, browser = env
    c1, p1 = L.open_page(browser, base, 1280)
    c2, p2 = L.open_page(browser, base, 1280)
    try:
        L.switch_mode(p1, "dark")
        assert L.mode_of(p1) == "dark" and L.mode_of(p2) == "light"
    finally:
        c1.close()
        c2.close()


# ───────────────────────── 原生元件 hover／focus／disabled／expander ─────────────────────────

@pytest.mark.parametrize("mode", L.MODES)
def test_native_hover_focus_disabled_expander_states(page_at, mode):
    p = pal.get(mode)
    page = page_at(1280, mode)
    # hover：radio 標籤、expander summary、button
    opt = f'{_RADIO_CHART}:not([data-selected="true"])'
    page.hover(opt)
    page.wait_for_timeout(300)
    assert _css_rgb(page.evaluate(_PROBE, opt)["bg"]) == _rgb(p["hover_bg"]), "radio hover 底色"
    page.mouse.move(2, 2)
    summ = '[data-testid="stExpander"] summary'
    page.hover(summ)
    page.wait_for_timeout(300)
    assert _css_rgb(page.evaluate(_PROBE, summ)["bg"]) == _rgb(p["hover_bg"]), "expander hover 底色"
    btn = '.st-key-poc-card-disabled [data-testid="stBaseButton-secondary"]:not(:disabled)'
    page.hover(btn)
    page.wait_for_timeout(300)
    got = page.evaluate(_PROBE, btn)
    assert _css_rgb(got["bg"]) == _rgb(p["hover_bg"]) and _css_rgb(got["border"]) == _rgb(p["primary"]), "button hover"
    page.mouse.move(2, 2)
    # 鍵盤 focus：button 外框、radio 標籤外框
    page.focus(btn)
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    page.wait_for_timeout(300)
    out = page.evaluate("(s) => { const c = getComputedStyle(document.querySelector(s)); return [c.outlineStyle, c.outlineColor, c.outlineWidth, c.boxShadow]; }", btn)
    assert out[0] == "solid" and _css_rgb(out[1]) == _rgb(p["focus_ring"]) and out[2] == "2px" and out[3] == "none", out
    page.mouse.move(2, 2)
    page.focus(f'{_RADIO_CHART.replace("label", "label")} input[type=radio][tabindex="0"]'.replace('label[data-testid="stRadioOption"] ', ""))
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    page.wait_for_timeout(300)
    foc = page.evaluate("""() => { const l = document.querySelector('.st-key-poc-card-chart label[data-focus-visible="true"]'); if (!l) return null; const c = getComputedStyle(l); return [c.outlineStyle, c.outlineColor, c.outlineWidth]; }""")
    assert foc and foc[0] == "solid" and _css_rgb(foc[1]) == _rgb(p["focus_ring"]), foc
    # disabled：button 的 disabled 屬性、radio 的 aria-disabled、游標不可用
    assert page.evaluate("() => document.querySelector('.st-key-poc-card-disabled button:disabled') !== null")
    assert page.evaluate("() => document.querySelector('.st-key-poc-card-disabled [role=radiogroup]').getAttribute('aria-disabled')") == "true"
    assert page.evaluate(_PROBE, '.st-key-poc-card-disabled button:disabled')["cursor"] == "not-allowed"
    dis_before = page.evaluate("() => document.querySelector('.st-key-poc-card-disabled label[data-selected=\"true\"]').innerText.trim()")
    page.locator('.st-key-poc-card-disabled label[data-testid="stRadioOption"]').nth(1).click(force=True)
    page.wait_for_timeout(400)
    assert page.evaluate("() => document.querySelector('.st-key-poc-card-disabled label[data-selected=\"true\"]').innerText.trim()") == dis_before, "disabled radio 不得被點動"
    # expander：點開後內容可見、字色吻合
    page.click(summ)
    page.wait_for_timeout(500)
    assert page.is_visible('[data-testid="stExpanderDetails"] .poc-note')
    assert _css_rgb(page.evaluate(_PROBE, '[data-testid="stExpanderDetails"] .poc-note')["color"]) == _rgb(p["text2"])


# ───────────────────────── 負控：注入破壞，判定函式必須報 ─────────────────────────

def _inject(page, css):
    page.add_style_tag(content=css)
    page.wait_for_timeout(200)


def test_mutation_stale_light_background_in_dark_is_detected(page_at):
    page = page_at(1280, "dark")
    assert_styles(page, pal.DARK)
    _inject(page, ".stApp{background:#ffffff !important}")
    assert any("app 底" in m for m in style_mismatches(page, pal.DARK))


def test_mutation_native_radio_dot_wrong_color_is_detected(page_at):
    page = page_at(1280, "dark")
    _inject(page, f'html body {_RADIO_CHART}[data-selected="true"]{_IND}{{background-color:#1f6feb !important}}')
    assert any("radio 選取圓點" in m for m in style_mismatches(page, pal.DARK))


def test_mutation_header_stays_light_is_detected(page_at):
    page = page_at(1280, "dark")
    _inject(page, '[data-testid="stHeader"]{background:#f6f8fa !important}')
    assert any("頁首底" in m for m in style_mismatches(page, pal.DARK))


def test_mutation_horizontal_overflow_is_detected(page_at):
    page = page_at(390)
    assert overflow_problems(page) == []
    _inject(page, ".poc-card-html{min-width:900px !important}")
    assert overflow_problems(page), "橫向溢位偵測失效"


def test_mutation_oversized_chart_is_detected(page_at):
    page = page_at(1280)
    _inject(page, "svg.poc-chart{max-width:none !important}")
    assert any("圖寬" in m for m in overflow_problems(page))


# ───────────────────────── 截圖 ─────────────────────────

@pytest.mark.parametrize("mode", L.MODES)
@pytest.mark.parametrize("width", L.WIDTHS)
def test_screenshots_are_saved(page_at, width, mode, tmp_path):
    """截圖寫到 `POC_DUAL_THEME_SHOT_DIR`（未設定則寫暫存目錄）。不 commit 任何影像。"""
    out = pathlib.Path(os.environ.get("POC_DUAL_THEME_SHOT_DIR") or tmp_path)
    out.mkdir(parents=True, exist_ok=True)
    page = page_at(width, mode)
    page.set_viewport_size({"width": width, "height": 3000 if width == 390 else 2000})
    page.wait_for_timeout(400)
    path = out / f"poc_dual_theme_{mode}_{width}.png"
    page.screenshot(path=str(path))
    assert path.exists() and path.stat().st_size > 5000
