# -*- coding: utf-8 -*-
"""🌍 市場頁：200% 縮放、最小字級、主內容區與展開區焦點的瀏覽器級量測（slow lane；只加測試，不改 production）。

授權：#1296 comment 7077293452 §2（A｜tests-only 單一切片）。補 `test_ui_v3_market_adaptation_browser.py` 沒有量的三件事：

1. **200% 縮放（390／1280）**：橫向溢出（整頁 `docScrollW`、主內容區 `mainScrollW`）與「多出被裁切的容器」。
   縮放的做法：視窗 CSS 寬減半＋`device_scale_factor=2`。這是 Chromium 呈現瀏覽器縮放給頁面的方式
   （`devicePixelRatio` 變 2、`innerWidth` 減半、寬度媒體查詢跟著切換、實際繪製像素加倍）。
   **每次都先驗縮放真的生效**：`devicePixelRatio==2`、`innerWidth` 減半，且同一元素的截圖像素寬 ≈ CSS 寬 × 2；
   只改視窗寬（假縮放）會被 `zoom_effect_violations` 判出（負控）。
   ⚠️ 這**不是**使用者按 Ctrl＋加號的 UI 縮放（headless 沒有那個 UI），列 NOT VERIFIED；頁面端可觀測量相同。
2. **最小字級**：以 Chromium 偏好設定 `webkit.webprefs.minimum_font_size`（＝設定頁「最小字型大小」）啟動持久化 context，
   量同樣的溢出與裁切。先用一個 8px 探針驗設定真的生效；**不生效＝環境不支援，skip（NOT RUN），不當 PASS**。
3. **聚焦外觀**：`stMain`（Streamlit 可捲動主容器，`tabindex=0`）與展開區 `summary` 被鍵盤聚焦時，
   outline、box-shadow、背景與未聚焦時是否有可見差異。
   - `summary`：Streamlit 原生有 box-shadow 焦點環 → 正向守衛。
   - `stMain`：聚焦後 outline、box-shadow、背景皆與未聚焦相同 → **確知缺口**，以 `xfail(strict=True)` 精確鎖定
     （有人修好會 XPASS 轉紅，提醒移除標記）。**本檔不修**：補環＝新增視覺，需另立 Gate。

資料：`market_stubs` 合成 fixture（人造數值，不是市場資料；不連外部來源）。結果是「本機／CI Chromium＋合成 fixture」，
**不是** Cloud、真機、作業系統字級或輔助科技驗收。

變異負控（真 DOM 變異或對真實量測結果做判定，皆在記憶體內）：假縮放必判；縮放後把卡片撐寬必判溢出；
縮放後把一個容器壓成 4px 高並 `overflow:hidden` 必判多出裁切；最小字級下撐寬必判溢出；未設最小字級時探針必判「未生效」；
拿掉 `summary` 焦點環必判；替 `stMain` 加上 2px 外框則判定轉為無違規（證明 xfail 量的就是「沒有外觀」）。
"""
from __future__ import annotations

import json
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
_ZOOM = 2
_MIN_FONT_PX = 24
_PROBE_PX = 8
_ANCHOR = '[data-field="market_state"]'

_LAYOUT_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth;
  let nClipped = 0;
  for (const e of main.querySelectorAll('*')) {
    const s = getComputedStyle(e);
    if (s.display === 'none' || !e.getClientRects().length) continue;
    if (['svg', 'path', 'g'].includes(e.tagName.toLowerCase())) continue;
    const clipY = s.overflowY !== 'visible' && e.scrollHeight > e.clientHeight + 1 && e.clientHeight > 0;
    const clipX = s.overflowX !== 'visible' && e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0;
    if (clipY || clipX) nClipped += 1;
  }
  return {vw, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth,
          mainClientW: main.clientWidth, nClipped};
}
"""
_ENV_JS = "() => ({dpr: window.devicePixelRatio, innerW: window.innerWidth})"
_PROBE_JS = f"""
() => {{ const d = document.createElement('span'); d.style.fontSize = '{_PROBE_PX}px'; d.textContent = 'x';
  document.body.appendChild(d); const px = parseFloat(getComputedStyle(d).fontSize); d.remove(); return px; }}
"""
_ACTIVE_JS = r"""
() => { const a = document.activeElement; if (!a || a === document.body) return null;
  return {tag: a.tagName, tid: a.getAttribute('data-testid'), fv: a.matches(':focus-visible')}; }
"""
_STYLE_JS = r"""
(e) => { const s = getComputedStyle(e);
  return {outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth, boxShadow: s.boxShadow, bg: s.backgroundColor}; }
"""
_TARGETS = {"stMain": 'section[data-testid="stMain"]', "summary": '[data-testid="stMain"] summary'}


# ───────────────────────── 判定函式（正向與負控共用） ─────────────────────────

def zoom_effect_violations(env, css_w, png_w, window_w, zoom=_ZOOM):
    """縮放必須真的生效：dpr＝zoom、CSS 視窗寬＝視窗寬／zoom、同一元素繪製像素寬 ≈ CSS 寬 × zoom。"""
    bad = []
    if env["dpr"] != zoom:
        bad.append(("devicePixelRatio 不是縮放倍率", env["dpr"], zoom))
    if env["innerW"] != window_w // zoom:
        bad.append(("CSS 視窗寬沒有隨縮放減半", env["innerW"], window_w // zoom))
    if abs(png_w - css_w * zoom) > zoom:
        bad.append(("繪製像素沒有隨縮放加倍（只改了視窗寬＝假縮放）", css_w, png_w))
    return bad


def reflow_violations(base, after):
    """與同寬 100% 基準比：不得整頁或主內容區橫向溢出，不得多出被裁切的容器。"""
    bad = []
    if after["docScrollW"] > after["vw"]:
        bad.append(("整頁橫向溢出", after["docScrollW"], after["vw"]))
    if after["mainScrollW"] > after["mainClientW"] + 1:
        bad.append(("主內容區橫向溢出", after["mainScrollW"], after["mainClientW"]))
    if after["nClipped"] > base["nClipped"]:
        bad.append(("多出被裁切的容器", base["nClipped"], after["nClipped"]))
    return bad


def min_font_effect_violations(probe_px, min_px=_MIN_FONT_PX):
    return [] if probe_px >= min_px else [("最小字級設定未生效", probe_px, min_px)]


def focus_appearance_violations(unfocused, focused):
    """聚焦後須有可見差異：outline 非 none／hidden 且 ≥2px，或 box-shadow 與未聚焦不同，或背景不同。"""
    ring = focused["outlineStyle"] not in ("none", "hidden") and float(focused["outlineWidth"].removesuffix("px")) >= 2
    shadow = focused["boxShadow"] != "none" and focused["boxShadow"] != unfocused["boxShadow"]
    return [] if (ring or shadow or focused["bg"] != unfocused["bg"]) else [("聚焦後沒有任何可見焦點外觀", unfocused, focused)]


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


def _measure(browser, base, scenario, *, viewport_w, dsf, css=None):
    ctx = browser.new_context(viewport={"width": viewport_w, "height": 800}, device_scale_factor=dsf, locale="zh-TW")
    try:
        page = ctx.new_page()
        _load(page, base, scenario)
        if css:
            page.add_style_tag(content=css)
            page.wait_for_timeout(400)
        anchor = page.query_selector(_ANCHOR)
        return {"env": page.evaluate(_ENV_JS), "layout": page.evaluate(_LAYOUT_JS),
                "css_w": round(anchor.bounding_box()["width"]), "png_w": _png_width(anchor.screenshot())}
    finally:
        ctx.close()


def _zoomed(base_and_pw, scenario, width, *, css=None, fake=False):
    base, _p, browser = base_and_pw
    before = _measure(browser, base, scenario, viewport_w=width, dsf=1)
    after = _measure(browser, base, scenario, viewport_w=width // _ZOOM, dsf=1 if fake else _ZOOM, css=css)
    return before, after


def _launch_with_min_font(p, user_dir, min_px):
    default = pathlib.Path(user_dir) / "Default"
    default.mkdir(parents=True, exist_ok=True)
    prefs = {"webkit": {"webprefs": {"minimum_font_size": min_px, "minimum_logical_font_size": min_px}}}
    (default / "Preferences").write_text(json.dumps(prefs), encoding="utf-8")
    path = os.environ.get(_ui_v2_chromium.ENV_VAR) or None
    kw = {"executable_path": path} if path else {}
    try:
        return p.chromium.launch_persistent_context(str(user_dir), viewport={"width": 1280, "height": 800}, locale="zh-TW", **kw)
    except Exception as exc:  # noqa: BLE001 - 交給共用規則：CI fail、本機 skip，原因照印
        _ui_v2_chromium.unavailable(f"持久化 context 啟動失敗：{exc}")


def _min_font(base_and_pw, tmp_path, width, *, min_px=_MIN_FONT_PX, css=None):
    base, p, browser = base_and_pw
    before = _measure(browser, base, "normal", viewport_w=width, dsf=1)
    ctx = _launch_with_min_font(p, tmp_path / f"profile_{min_px}", min_px)
    try:
        page = ctx.new_page()
        page.set_viewport_size({"width": width, "height": 800})
        _load(page, base, "normal")
        if css:
            page.add_style_tag(content=css)
            page.wait_for_timeout(400)
        return before["layout"], page.evaluate(_PROBE_JS), page.evaluate(_LAYOUT_JS)
    finally:
        ctx.close()


def _focus(base_and_pw, width, target, *, css=None, max_tabs=20):
    """Tab 到第一個目標元素為止；回傳（聚焦前樣式、聚焦後樣式）。走完仍未落在目標上 → fail（不得空洞通過）。"""
    base, _p, browser = base_and_pw
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW",
                              has_touch=width <= 768)
    try:
        page = ctx.new_page()
        _load(page, base, "normal")
        if css:
            page.add_style_tag(content=css)
            page.wait_for_timeout(300)
        loc = page.locator(_TARGETS[target]).first
        assert loc.count() == 1, f"找不到 {target}：DOM 改名時本測試不得空洞通過"
        unfocused = loc.evaluate(_STYLE_JS)
        for _ in range(max_tabs):
            page.keyboard.press("Tab")
            if loc.evaluate("e => e === document.activeElement"):
                active = page.evaluate(_ACTIVE_JS)
                assert active and active["fv"], ("聚焦但不是 :focus-visible（鍵盤來源）", active)
                return unfocused, loc.evaluate(_STYLE_JS)
        pytest.fail(f"Tab {max_tabs} 次仍未聚焦到 {target}")
    finally:
        ctx.close()


# ───────────────────────── 正向守衛 ─────────────────────────

@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_200pct_zoom_takes_effect_and_causes_no_overflow_or_new_clipping(base_and_pw, scenario, width):
    before, after = _zoomed(base_and_pw, scenario, width)
    assert not zoom_effect_violations(after["env"], after["css_w"], after["png_w"], width), after
    assert not reflow_violations(before["layout"], after["layout"]), (reflow_violations(before["layout"], after["layout"]), before, after)


@pytest.mark.parametrize("width", _WIDTHS)
def test_minimum_font_size_causes_no_overflow_or_new_clipping(base_and_pw, tmp_path, width):
    base_layout, probe_px, after = _min_font(base_and_pw, tmp_path, width)
    if min_font_effect_violations(probe_px):
        pytest.skip(f"NOT RUN：本環境 Chromium 未套用最小字級偏好（8px 探針量得 {probe_px}px）")
    assert not reflow_violations(base_layout, after), (reflow_violations(base_layout, after), base_layout, after)


@pytest.mark.parametrize("width", _WIDTHS)
def test_expander_summary_shows_visible_focus(base_and_pw, width):
    unfocused, focused = _focus(base_and_pw, width, "summary")
    assert not focus_appearance_violations(unfocused, focused), (unfocused, focused)


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="KNOWN-GAP（未修，需新增視覺的 Gate）：stMain 可捲動主容器被鍵盤聚焦後，outline／box-shadow／背景皆與未聚焦相同")
@pytest.mark.parametrize("width", _WIDTHS)
def test_scrollable_main_container_shows_visible_focus_known_gap(base_and_pw, width):
    unfocused, focused = _focus(base_and_pw, width, "stMain")
    assert not focus_appearance_violations(unfocused, focused), (unfocused, focused)


# ───────────────────────── 負控（變異驗證） ─────────────────────────

def test_mutation_viewport_only_fake_zoom_is_flagged(base_and_pw):
    """只把視窗寬減半、不改繪製倍率（假縮放）→ 生效檢查必須報。"""
    _before, after = _zoomed(base_and_pw, "normal", 1280, fake=True)
    assert zoom_effect_violations(after["env"], after["css_w"], after["png_w"], 1280), after


@pytest.mark.parametrize("width", _WIDTHS)
def test_mutation_wide_card_under_zoom_is_flagged(base_and_pw, width):
    before, after = _zoomed(base_and_pw, "normal", width, css=".uv3-card{min-width:1400px !important}")
    assert reflow_violations(before["layout"], after["layout"]), after


def test_mutation_new_clipped_container_under_zoom_is_flagged(base_and_pw):
    before, after = _zoomed(base_and_pw, "normal", 1280, css=f"{_ANCHOR}{{height:4px !important;overflow:hidden !important}}")
    assert reflow_violations(before["layout"], after["layout"]), (before["layout"], after["layout"])


def test_mutation_min_font_probe_without_setting_is_flagged(base_and_pw, tmp_path):
    """不設最小字級（0）→ 8px 探針維持 8px，生效檢查必須報（證明 skip 條件判的是真的「未生效」）。"""
    _base_layout, probe_px, _after = _min_font(base_and_pw, tmp_path, 1280, min_px=0)
    assert min_font_effect_violations(probe_px), probe_px


def test_mutation_wide_card_under_min_font_is_flagged(base_and_pw, tmp_path):
    base_layout, probe_px, after = _min_font(base_and_pw, tmp_path, 390, css=".uv3-card{min-width:1400px !important}")
    if min_font_effect_violations(probe_px):
        pytest.skip(f"NOT RUN：本環境 Chromium 未套用最小字級偏好（8px 探針量得 {probe_px}px）")
    assert reflow_violations(base_layout, after), after


def test_mutation_removing_summary_focus_ring_is_flagged(base_and_pw):
    unfocused, focused = _focus(base_and_pw, 1280, "summary",
                                css="summary:focus-visible,summary:focus{box-shadow:none !important;outline:none !important}")
    assert focus_appearance_violations(unfocused, focused), focused


def test_mutation_adding_ring_to_main_container_clears_the_gap(base_and_pw):
    """替 stMain 加 2px 外框 → 判定轉為無違規（證明 known-gap 測試判的就是「沒有焦點外觀」）。"""
    unfocused, focused = _focus(base_and_pw, 1280, "stMain",
                                css='section[data-testid="stMain"]:focus-visible{outline:2px solid #172033 !important}')
    assert not focus_appearance_violations(unfocused, focused), focused
