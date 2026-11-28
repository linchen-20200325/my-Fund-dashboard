# -*- coding: utf-8 -*-
"""🌍 市場頁：縮放模擬、最小字級、主內容區與展開區焦點的瀏覽器級量測（slow lane；只加測試，不改 production）。

授權：#1296 comment 7077293452 §2（tests-only 單一切片）；Must-Fix 修補依 #1296 comment 7077680667（Work QA #7077661223）。

1. **縮放模擬（390／1280）**：視窗 CSS 寬高減半＋`device_scale_factor=2`。
   **本檔只宣稱已量到的三件事**：`devicePixelRatio` 變 2、CSS 視窗寬減半、同一元素截圖像素寬 ≈ CSS 寬 × 2；以及在這個模擬下的版面。
   ⚠️ 這**不等於**使用者在 Chrome 按 Ctrl＋加號的真 200% 縮放（headless 沒有那個 UI）：**真瀏覽器縮放 NOT VERIFIED**。
   只改視窗寬、不改繪製倍率的假縮放，會被 `zoom_effect_violations` 判出（負控）。
2. **最小字級**：以 Blink 設定 `--blink-settings=minimumFontSize=24,minimumLogicalFontSize=24` 另起瀏覽器（headless shell 也吃這條；
   前一版用 Chromium Preferences，在 headless shell 不生效）。先用 8px 探針驗設定生效；**探針仍為 8px＝環境不支援，skip（NOT RUN），不當 PASS**。
3. **焦點外觀**：鍵盤 Tab 到 `summary` 與 `stMain`。**先硬性確認**元素存在、Tab 真的命中、`:focus-visible` 成立（任何一項不成立＝FAIL）；
   之後只看**焦點環通道**（outline 與聚焦前不同且 ≥2px、或 box-shadow 與聚焦前不同）。背景色的微小 alpha 變動**不算**焦點環
   （前一版把背景也算進去，移除環後背景偶有 0.016 的變動，負控紅綠交錯）。
   - `summary`：Streamlit 原生 box-shadow 環 → 正向守衛。
   - `stMain`：焦點環通道無變化 → **確知缺口**，`xfail(strict=True, raises=MissingFocusRing)`。只有這個專屬例外會被當成預期失敗；
     找不到元素、沒取得焦點、不是 `:focus-visible` 都是一般 FAIL。補上 2px 環會讓它 XPASS(strict) 轉紅。**本檔不修**（補環＝新增視覺，需 Gate）。

版面判定（`reflow_violations`）回傳 `(種類, 細節)`，種類分開：`doc_overflow`（整頁）、`main_overflow`（主內容區）、`new_clip`（新增的強制裁切）。
強制裁切只算 `overflow` 為 `hidden`／`clip` 的軸；`auto`／`scroll` 是可捲動內容，不算裁切。新增裁切以「元素路徑＋軸」比對前後，
不比總數（A 解除、B 新增時計數不變也會報 B）。

資料：`market_stubs` 合成 fixture（人造數值，不是市場資料；不連外部來源）。結果是「本機／CI Chromium＋合成 fixture」，
**不是** Cloud、真機、作業系統字級或輔助科技驗收。
"""
from __future__ import annotations

import os
import pathlib
import struct
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "tests" / "ui_v2"))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）

_APP = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r}); sys.path.insert(0, {str(_HERE)!r})
import streamlit as st
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
_SCENARIOS = {{"normal": {{}}, "us_failed": dict(us="error")}}
_view, _table = ms.view(**_SCENARIOS[st.query_params.get("scenario", "normal")]), ms.table()
adapter.load = lambda sources: (_view, _table)
from ui_v3 import app_preview
app_preview.main()
"""

_SCENARIOS = ("normal", "us_failed")
_WIDTHS = (390, 1280)
_HEIGHT = 800
_ZOOM = 2
_MIN_FONT_PX = 24
_PROBE_PX = 8
_ANCHOR = '[data-field="market_state"]'
_CLIP_A = _ANCHOR
_CLIP_B = '[data-field="attention"]'
_CLIP_CSS = "{height:4px !important;overflow:hidden !important}"
_TARGETS = {"stMain": 'section[data-testid="stMain"]', "summary": '[data-testid="stMain"] summary'}

_LAYOUT_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const keyOf = (e) => {
    const parts = [];
    for (let n = e; n && n !== main; n = n.parentElement) {
      const sib = n.parentElement ? [...n.parentElement.children].filter(c => c.tagName === n.tagName) : [n];
      const tid = n.getAttribute('data-testid');
      parts.unshift(n.tagName.toLowerCase() + (tid ? `[${tid}]` : '') + `:${sib.indexOf(n) + 1}`);
    }
    return parts.join('>');
  };
  const forced = (v) => v === 'hidden' || v === 'clip';
  const clips = [];
  for (const e of main.querySelectorAll('*')) {
    const s = getComputedStyle(e);
    if (s.display === 'none' || !e.getClientRects().length) continue;
    if (['svg', 'path', 'g'].includes(e.tagName.toLowerCase())) continue;
    if (forced(s.overflowY) && e.clientHeight > 0 && e.scrollHeight > e.clientHeight + 1) clips.push(keyOf(e) + '|y');
    if (forced(s.overflowX) && e.clientWidth > 0 && e.scrollWidth > e.clientWidth + 1) clips.push(keyOf(e) + '|x');
  }
  return {vw: document.documentElement.clientWidth, docScrollW: document.documentElement.scrollWidth,
          mainScrollW: main.scrollWidth, mainClientW: main.clientWidth, clips};
}
"""
_KEY_OF_JS = _LAYOUT_JS.split("const forced")[0] + "return keyOf(document.querySelector(SEL)); }"
_ENV_JS = "() => ({dpr: window.devicePixelRatio, innerW: window.innerWidth})"
_PROBE_JS = f"""
() => {{ const d = document.createElement('span'); d.style.fontSize = '{_PROBE_PX}px'; d.textContent = 'x';
  document.body.appendChild(d); const px = parseFloat(getComputedStyle(d).fontSize); d.remove(); return px; }}
"""
_STYLE_JS = r"""
(e) => { const s = getComputedStyle(e);
  return {outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth, outlineColor: s.outlineColor, boxShadow: s.boxShadow,
          bg: s.backgroundColor}; }
"""


class MissingFocusRing(Exception):
    """已確認鍵盤焦點落在目標上（`:focus-visible`），但焦點環通道沒有任何變化。只有這個例外能被 xfail 吸收。"""


# ───────────────────────── 判定函式（正向與負控共用） ─────────────────────────

def zoom_effect_violations(env, css_w, png_w, window_w, zoom=_ZOOM):
    """縮放模擬必須真的生效：dpr＝zoom、CSS 視窗寬＝視窗寬／zoom、同一元素繪製像素寬 ≈ CSS 寬 × zoom。"""
    bad = []
    if env["dpr"] != zoom:
        bad.append(("zoom_dpr", env["dpr"], zoom))
    if env["innerW"] != window_w // zoom:
        bad.append(("zoom_width", env["innerW"], window_w // zoom))
    if abs(png_w - css_w * zoom) > zoom:
        bad.append(("zoom_pixels", css_w, png_w))
    return bad


def reflow_violations(base, after):
    """與基準比：整頁、主內容區橫向溢出，以及「元素路徑＋軸」層級新增的強制裁切（不比總數）。"""
    bad = []
    if after["docScrollW"] > after["vw"]:
        bad.append(("doc_overflow", after["docScrollW"], after["vw"]))
    if after["mainScrollW"] > after["mainClientW"] + 1:
        bad.append(("main_overflow", after["mainScrollW"], after["mainClientW"]))
    bad += [("new_clip", key) for key in sorted(set(after["clips"]) - set(base["clips"]))]
    return bad


def kinds(violations):
    return {v[0] for v in violations}


def min_font_effect_violations(probe_px, min_px=_MIN_FONT_PX):
    return [] if probe_px >= min_px else [("min_font_not_applied", probe_px, min_px)]


def _outline_visible(s):
    return s["outlineStyle"] not in ("none", "hidden") and float(s["outlineWidth"].removesuffix("px")) >= 2


def focus_ring_violations(unfocused, focused):
    """只看焦點環通道：outline 聚焦後可見（≥2px）且與聚焦前不同，或 box-shadow 聚焦後非 none 且與聚焦前不同。背景不計。"""
    outline_keys = ("outlineStyle", "outlineWidth", "outlineColor")
    outline = _outline_visible(focused) and any(focused[k] != unfocused[k] for k in outline_keys)
    shadow = focused["boxShadow"] != "none" and focused["boxShadow"] != unfocused["boxShadow"]
    return [] if (outline or shadow) else [("ring_missing", unfocused, focused)]


# ───────────────────────── fixtures 與量測 ─────────────────────────

@pytest.fixture(scope="module")
def base_and_pw(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_zoom_focus") / "app_zoom_focus.py"
    app.write_text(_APP, encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, p, browser
        finally:
            browser.close()


def _load(page, base, scenario):
    page.goto(f"{base}/?scenario={scenario}", wait_until="networkidle")
    page.wait_for_selector(_ANCHOR, timeout=60000)
    page.wait_for_timeout(1200)


def _png_width(png: bytes) -> int:
    return struct.unpack(">I", png[16:20])[0]   # PNG IHDR：寬度在第 16～19 位元組


def _style(page, css):
    page.add_style_tag(content=css)
    page.wait_for_timeout(400)


def _measure(browser, base, scenario, *, width, zoom=1, dsf=None, css=None):
    """width＝視窗寬；zoom＝模擬倍率（CSS 視窗寬高 ÷ zoom）；dsf 預設等於 zoom（傳 1 即「只改視窗寬」的假縮放）。"""
    ctx = browser.new_context(viewport={"width": width // zoom, "height": _HEIGHT // zoom},
                              device_scale_factor=zoom if dsf is None else dsf, locale="zh-TW")
    try:
        page = ctx.new_page()
        _load(page, base, scenario)
        if css:
            _style(page, css)
        anchor = page.query_selector(_ANCHOR)
        return {"env": page.evaluate(_ENV_JS), "layout": page.evaluate(_LAYOUT_JS),
                "css_w": round(anchor.bounding_box()["width"]), "png_w": _png_width(anchor.screenshot())}
    finally:
        ctx.close()


def _zoomed(base_and_pw, scenario, width, *, css=None, fake=False):
    base, _p, browser = base_and_pw
    before = _measure(browser, base, scenario, width=width)
    after = _measure(browser, base, scenario, width=width, zoom=_ZOOM, dsf=1 if fake else None, css=css)
    return before, after


def _launch_with_blink_min_font(p, min_px):
    path = os.environ.get(_ui_v2_chromium.ENV_VAR) or None
    kw = {"executable_path": path} if path else {}
    args = [f"--blink-settings=minimumFontSize={min_px},minimumLogicalFontSize={min_px}"] if min_px else []
    try:
        return p.chromium.launch(args=args, **kw)
    except Exception as exc:  # noqa: BLE001 - 交給共用規則：CI fail、本機 skip，原因照印
        _ui_v2_chromium.unavailable(f"帶最小字級設定的 Chromium 啟動失敗：{exc}")


def _min_font(base_and_pw, width, *, min_px=_MIN_FONT_PX, css=None):
    base, p, browser = base_and_pw
    before = _measure(browser, base, "normal", width=width)["layout"]
    other = _launch_with_blink_min_font(p, min_px)
    try:
        ctx = other.new_context(viewport={"width": width, "height": _HEIGHT}, locale="zh-TW")
        page = ctx.new_page()
        _load(page, base, "normal")
        if css:
            _style(page, css)
        return before, page.evaluate(_PROBE_JS), page.evaluate(_LAYOUT_JS)
    finally:
        other.close()


def _focus(base_and_pw, width, selector, *, css=None, max_tabs=20):
    """硬性前提（不成立＝FAIL，不能被 xfail 吸收）：目標唯一存在、Tab 命中、`:focus-visible`。回傳（聚焦前樣式、聚焦後樣式）。"""
    base, _p, browser = base_and_pw
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else _HEIGHT}, locale="zh-TW",
                              has_touch=width <= 768)
    try:
        page = ctx.new_page()
        _load(page, base, "normal")
        if css:
            _style(page, css)
        loc = page.locator(selector).first
        if page.locator(selector).count() < 1:
            pytest.fail(f"找不到 {selector}：DOM 改名時不得空洞通過，也不得被 xfail 吸收")
        unfocused = loc.evaluate(_STYLE_JS)
        for _ in range(max_tabs):
            page.keyboard.press("Tab")
            if loc.evaluate("e => e === document.activeElement"):
                if not loc.evaluate("e => e.matches(':focus-visible')"):
                    pytest.fail(f"{selector} 已聚焦但不是 :focus-visible（不是鍵盤焦點）")
                return unfocused, loc.evaluate(_STYLE_JS)
        pytest.fail(f"Tab {max_tabs} 次仍未聚焦到 {selector}")
    finally:
        ctx.close()


def _check_main_focus_ring(base_and_pw, width, *, css=None):
    unfocused, focused = _focus(base_and_pw, width, _TARGETS["stMain"], css=css)
    violations = focus_ring_violations(unfocused, focused)
    if violations:
        raise MissingFocusRing(violations)


def _clip_swap(base_and_pw, width):
    """同一頁、縮放模擬下：先只裁 A、量；再改成只裁 B、量。回傳（只裁 A 的版面、只裁 B 的版面、A 與 B 的路徑）。"""
    base, _p, browser = base_and_pw
    ctx = browser.new_context(viewport={"width": width // _ZOOM, "height": _HEIGHT // _ZOOM}, device_scale_factor=_ZOOM,
                              locale="zh-TW")
    try:
        page = ctx.new_page()
        _load(page, base, "normal")
        keys = [page.evaluate(_KEY_OF_JS.replace("SEL", repr(s))) for s in (_CLIP_A, _CLIP_B)]
        tag = page.add_style_tag(content=_CLIP_A + _CLIP_CSS)
        page.wait_for_timeout(400)
        only_a = page.evaluate(_LAYOUT_JS)
        tag.evaluate("e => e.remove()")
        _style(page, _CLIP_B + _CLIP_CSS)
        return only_a, page.evaluate(_LAYOUT_JS), keys
    finally:
        ctx.close()


# ───────────────────────── 正向守衛 ─────────────────────────

@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_zoom_simulation_takes_effect_and_causes_no_overflow_or_new_clipping(base_and_pw, scenario, width):
    before, after = _zoomed(base_and_pw, scenario, width)
    assert not zoom_effect_violations(after["env"], after["css_w"], after["png_w"], width), after
    assert not reflow_violations(before["layout"], after["layout"]), (reflow_violations(before["layout"], after["layout"]), before, after)


@pytest.mark.parametrize("width", _WIDTHS)
def test_minimum_font_size_causes_no_overflow_or_new_clipping(base_and_pw, width):
    base_layout, probe_px, after = _min_font(base_and_pw, width)
    if min_font_effect_violations(probe_px):
        pytest.skip(f"NOT RUN：本環境 Chromium 未套用最小字級設定（8px 探針量得 {probe_px}px）")
    assert not reflow_violations(base_layout, after), (reflow_violations(base_layout, after), base_layout, after)


@pytest.mark.parametrize("width", _WIDTHS)
def test_expander_summary_shows_visible_focus_ring(base_and_pw, width):
    unfocused, focused = _focus(base_and_pw, width, _TARGETS["summary"])
    assert not focus_ring_violations(unfocused, focused), (unfocused, focused)


@pytest.mark.xfail(strict=True, raises=MissingFocusRing,
                   reason="KNOWN-GAP（未修，需新增視覺的 Gate）：stMain 可捲動主容器已取得鍵盤焦點（:focus-visible），但 outline／box-shadow 與未聚焦相同")
@pytest.mark.parametrize("width", _WIDTHS)
def test_scrollable_main_container_shows_visible_focus_ring_known_gap(base_and_pw, width):
    _check_main_focus_ring(base_and_pw, width)


# ───────────────────────── 負控：判定函式層級（純資料） ─────────────────────────

def test_judge_reports_new_clip_by_identity_even_when_count_is_unchanged():
    base = {"vw": 100, "docScrollW": 100, "mainScrollW": 90, "mainClientW": 90, "clips": ["div:1>div:1|y"]}
    after = dict(base, clips=["div:1>div:2|y"])   # A 解除、B 新增：計數 1→1
    assert reflow_violations(base, after) == [("new_clip", "div:1>div:2|y")]


def test_judge_ignores_same_clip_and_distinguishes_axis():
    base = {"vw": 100, "docScrollW": 100, "mainScrollW": 90, "mainClientW": 90, "clips": ["div:1|y"]}
    assert reflow_violations(base, dict(base)) == []
    assert reflow_violations(base, dict(base, clips=["div:1|y", "div:1|x"])) == [("new_clip", "div:1|x")]


def test_judge_flags_an_unchanged_existing_outline_as_missing_ring():
    same = {"outlineStyle": "solid", "outlineWidth": "2px", "outlineColor": "rgb(0, 0, 0)", "boxShadow": "none", "bg": "rgba(0, 0, 0, 0)"}
    assert kinds(focus_ring_violations(same, dict(same))) == {"ring_missing"}
    assert kinds(focus_ring_violations(same, dict(same, bg="rgba(147, 164, 189, 0.016)"))) == {"ring_missing"}, "背景微動不得算焦點環"
    assert focus_ring_violations(same, dict(same, outlineColor="rgb(255, 0, 0)")) == []


# ───────────────────────── 負控：瀏覽器真變異 ─────────────────────────

def test_mutation_viewport_only_fake_zoom_is_flagged(base_and_pw):
    """只把視窗寬減半、不改繪製倍率（假縮放）→ 必報 zoom_dpr 與 zoom_pixels。"""
    _before, after = _zoomed(base_and_pw, "normal", 1280, fake=True)
    assert kinds(zoom_effect_violations(after["env"], after["css_w"], after["png_w"], 1280)) == {"zoom_dpr", "zoom_pixels"}, after


@pytest.mark.parametrize("width", _WIDTHS)
def test_mutation_wide_card_under_zoom_is_flagged_as_main_overflow(base_and_pw, width):
    before, after = _zoomed(base_and_pw, "normal", width, css=".uv3-card{min-width:1400px !important}")
    assert "main_overflow" in kinds(reflow_violations(before["layout"], after["layout"])), after["layout"]


def test_mutation_document_only_overflow_is_flagged_as_doc_overflow_not_main(base_and_pw):
    before, after = _zoomed(base_and_pw, "normal", 1280,
                            css='body::after{content:"";display:block;width:3000px;height:1px}')
    found = kinds(reflow_violations(before["layout"], after["layout"]))
    assert "doc_overflow" in found and "main_overflow" not in found, after["layout"]


@pytest.mark.parametrize("width", _WIDTHS)
def test_mutation_new_clipped_container_under_zoom_names_that_container(base_and_pw, width):
    base, _p, browser = base_and_pw
    before = _measure(browser, base, "normal", width=width)
    only_a, _only_b, (key_a, _key_b) = _clip_swap(base_and_pw, width)
    assert ("new_clip", key_a + "|y") in reflow_violations(before["layout"], only_a), (key_a, only_a["clips"])


@pytest.mark.parametrize("width", _WIDTHS)
def test_mutation_clip_swap_reports_the_new_container_regardless_of_count(base_and_pw, width):
    """真 DOM：A 解除、B 新增。總數可能持平或減少（子孫元素跟著變），身分比對仍必報 B、不報 A。
    「計數 1→1」的精確情境由上方判定函式層級的負控鎖定（瀏覽器裡總數不受我們控制）。"""
    only_a, only_b, (key_a, key_b) = _clip_swap(base_and_pw, width)
    found = reflow_violations(only_a, only_b)
    assert ("new_clip", key_b + "|y") in found, (key_b, len(only_a["clips"]), len(only_b["clips"]))
    assert ("new_clip", key_a + "|y") not in found


def test_mutation_scrollable_overflow_auto_is_not_counted_as_clip(base_and_pw):
    """同一個容器壓成 4px：`overflow:auto`（可捲動）不算新增裁切；改成 `hidden` 才算（對照組，證明差別只在 overflow 值）。"""
    base, _p, browser = base_and_pw
    zoomed_plain = _measure(browser, base, "normal", width=1280, zoom=_ZOOM)["layout"]
    scrollable = _measure(browser, base, "normal", width=1280, zoom=_ZOOM,
                          css=_CLIP_A + "{height:4px !important;overflow:auto !important}")["layout"]
    hidden = _measure(browser, base, "normal", width=1280, zoom=_ZOOM, css=_CLIP_A + _CLIP_CSS)["layout"]
    assert "new_clip" not in kinds(reflow_violations(zoomed_plain, scrollable)), scrollable["clips"]
    assert "new_clip" in kinds(reflow_violations(zoomed_plain, hidden)), hidden["clips"]


def test_mutation_min_font_without_setting_is_flagged(base_and_pw):
    """不帶最小字級設定 → 8px 探針維持 8px，必報 min_font_not_applied（證明 skip 條件判的是真的「未生效」）。"""
    _base, probe_px, _after = _min_font(base_and_pw, 1280, min_px=0)
    assert kinds(min_font_effect_violations(probe_px)) == {"min_font_not_applied"}, probe_px


def test_mutation_wide_card_under_min_font_is_flagged_as_main_overflow(base_and_pw):
    base_layout, probe_px, after = _min_font(base_and_pw, 390, css=".uv3-card{min-width:1400px !important}")
    if min_font_effect_violations(probe_px):
        pytest.skip(f"NOT RUN：本環境 Chromium 未套用最小字級設定（8px 探針量得 {probe_px}px）")
    assert "main_overflow" in kinds(reflow_violations(base_layout, after)), after


@pytest.mark.parametrize("width", _WIDTHS)
def test_mutation_removing_summary_focus_ring_is_flagged_as_ring_missing(base_and_pw, width):
    unfocused, focused = _focus(base_and_pw, width, _TARGETS["summary"],
                                css="summary:focus-visible,summary:focus{box-shadow:none !important;outline:none !important}")
    assert kinds(focus_ring_violations(unfocused, focused)) == {"ring_missing"}, focused


@pytest.mark.parametrize("width", _WIDTHS)
def test_mutation_adding_ring_to_main_container_would_xpass_the_known_gap(base_and_pw, width):
    """同一個檢查加上 2px 環 → 不再丟 MissingFocusRing；也就是原 xfail(strict) 測試會 XPASS 轉紅。"""
    _check_main_focus_ring(base_and_pw, width,
                           css='section[data-testid="stMain"]:focus-visible{outline:2px solid #172033 !important}')


def test_mutation_missing_selector_fails_hard_instead_of_being_an_expected_gap(base_and_pw):
    with pytest.raises(pytest.fail.Exception, match="找不到"):
        _focus(base_and_pw, 1280, 'section[data-testid="stMainRenamed"]')


def test_mutation_focus_never_reached_fails_hard_instead_of_being_an_expected_gap(base_and_pw):
    with pytest.raises(pytest.fail.Exception, match="仍未聚焦"):
        _focus(base_and_pw, 1280, _TARGETS["stMain"], max_tabs=1)
