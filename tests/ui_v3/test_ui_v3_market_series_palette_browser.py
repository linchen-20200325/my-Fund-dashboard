# -*- coding: utf-8 -*-
"""🌍 比較圖雙系列色票方案 A（客戶 2026-11-21 正式裁示，#1296 comment 7057582576）的瀏覽器級守衛（slow lane；真 Chromium＋合成 fixture）。

斷言：390／1280 比較圖兩條線的 computed stroke＝核准色（深藍實線／橙虛線，一字不差）、線型不變、末點圓同色、**文字標籤不上色**；
灰階（亮度比）與對白底的對比達非文字 3:1；forced-colors 下仍靠實／虛線分辨；單序列檢視（VIX）維持 currentColor；缺資料情境不補線、不畫零。
⚠️ 結果是「本機／CI Chromium＋合成 fixture」，不是 Cloud／真機／色覺者研究。色覺模擬數值 NOT VERIFIED。

變異驗證（負控）：把任一系列色值改掉、把虛線拿掉、把標籤文字塗成系列色，判定函式都必須報。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "tests" / "ui_v2"))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402

_APP = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r}); sys.path.insert(0, {str(_HERE)!r})
import streamlit as st
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
_SCENARIOS = {{"normal": {{}}, "tw_missing": dict(tw="missing"), "us_failed": dict(us="error"),
              "both_missing": dict(tw="missing", us="missing")}}
_view, _table = ms.view(**_SCENARIOS[st.query_params.get("scenario", "normal")]), ms.table()
adapter.load = lambda sources: (_view, _table)
from ui_v3 import app_preview
app_preview.main()
"""

NAVY, ORANGE = "rgb(10, 63, 134)", "rgb(208, 106, 0)"
_WIDTHS = (390, 1280)

_CHART_JS = r"""
() => {
  const svg = document.querySelector('[data-testid="stMain"] svg.uv3-chart');
  if (!svg) return {exists: false};
  const paths = [...svg.querySelectorAll('path')].map(p => { const c = getComputedStyle(p); return {stroke: c.stroke, dash: c.strokeDasharray}; });
  const dots = [...svg.querySelectorAll('circle')].map(c => getComputedStyle(c).fill);
  const labels = [...svg.querySelectorAll('text')].filter(t => /台股|S&P/.test(t.textContent)).map(t => ({text: t.textContent, fill: getComputedStyle(t).fill}));
  const ink = getComputedStyle(svg).color;
  return {exists: true, paths, dots, labels, ink};
}
"""


def _lum(rgb: str) -> float:
    r, g, b = (int(x) for x in rgb[rgb.index("(") + 1:rgb.index(")")].split(",")[:3])
    f = lambda c: (c / 255 / 12.92) if c / 255 <= 0.04045 else ((c / 255 + 0.055) / 1.055) ** 2.4
    return .2126 * f(r) + .7152 * f(g) + .0722 * f(b)


def _ratio(a: str, b: str) -> float:
    x, y = sorted((_lum(a), _lum(b)), reverse=True)
    return (x + .05) / (y + .05)


def palette_violations(chart):
    """比較圖（兩條線）：實線深藍、虛線橙、末點圓同色、文字標籤＝文字色（不上色）。"""
    if not chart["exists"]:
        return [("主圖不存在",)]
    bad = []
    p = chart["paths"]
    if len(p) != 2:
        return [("比較圖應為兩條線", len(p))]
    if p[0]["stroke"] != NAVY or p[0]["dash"] != "none":
        bad.append(("第一系列不是深藍實線", p[0]))
    if p[1]["stroke"] != ORANGE or p[1]["dash"] in ("none", ""):
        bad.append(("第二系列不是橙虛線", p[1]))
    if chart["dots"] != [NAVY, ORANGE]:
        bad.append(("末點圓顏色與系列不符", chart["dots"]))
    if any(lab["fill"] != chart["ink"] for lab in chart["labels"]) or len(chart["labels"]) != 2:
        bad.append(("末點文字標籤不是文字色／數量不符", chart["labels"]))
    return bad


@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_series_palette") / "app.py"
    app.write_text(_APP, encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


def _read(base_and_browser, scenario, width, *, css=None, js=None, view=None, **ctx_kw):
    base, browser = base_and_browser
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW", has_touch=width <= 768, **ctx_kw)
    page = ctx.new_page()
    try:
        page.goto(f"{base}/?scenario={scenario}", wait_until="networkidle")
        page.wait_for_selector('[data-field="market_state"]', timeout=60000)
        page.wait_for_timeout(1200)
        if view:
            page.locator('[data-testid="stMain"] [data-testid="stRadioGroup"][aria-label="檢視"] label', has_text=view).first.click()
            page.wait_for_timeout(1500)
        if css:
            page.add_style_tag(content=css)
        if js:
            page.evaluate(js)
        if css or js:
            page.wait_for_timeout(300)
        return page.evaluate(_CHART_JS)
    finally:
        ctx.close()


@pytest.mark.parametrize("width", _WIDTHS)
def test_comparison_chart_uses_approved_navy_solid_and_orange_dashed(base_and_browser, width):
    chart = _read(base_and_browser, "normal", width)
    assert not palette_violations(chart), (palette_violations(chart), chart)


@pytest.mark.parametrize("width", _WIDTHS)
def test_series_contrast_and_grayscale_luminance_hold(base_and_browser, width):
    chart = _read(base_and_browser, "normal", width)
    for stroke in (p["stroke"] for p in chart["paths"]):
        assert _ratio(stroke, "rgb(255, 255, 255)") >= 3.0, stroke           # 非文字 3:1（對卡片底）
        assert _ratio(stroke, "rgb(245, 247, 251)") >= 3.0, stroke           # 對頁面底
    assert _ratio(chart["paths"][0]["stroke"], chart["paths"][1]["stroke"]) >= 2.5   # 灰階亮度比（兩線仍可由亮度分開；另有線型與標籤）


@pytest.mark.parametrize("width", _WIDTHS)
def test_forced_colors_still_separates_series_by_line_style(base_and_browser, width):
    chart = _read(base_and_browser, "normal", width, forced_colors="active")
    assert len({p["dash"] for p in chart["paths"]}) == 2, chart["paths"]
    # 系統不會改寫明確色碼；深藍在黑底高對比主題會看不見 → SVG 內 @media(forced-colors) 讓線與末點回到系統文字色
    assert all(p["stroke"] == chart["ink"] for p in chart["paths"]), (chart["paths"], chart["ink"])
    assert all(d == chart["ink"] for d in chart["dots"]), (chart["dots"], chart["ink"])


def test_mutation_without_forced_colors_fallback_would_keep_navy_and_is_flagged(base_and_browser):
    """負控：拿掉 forced-colors 回退規則 → 線會留在明確色碼；上面的判定必須報。"""
    chart = _read(base_and_browser, "normal", 390, forced_colors="active",
                  js="() => document.querySelectorAll('svg.uv3-chart style').forEach(e => e.remove())")
    assert not all(p["stroke"] == chart["ink"] for p in chart["paths"]), chart


@pytest.mark.parametrize("width", _WIDTHS)
def test_dark_color_scheme_keeps_series_colors_and_layout(base_and_browser, width):
    chart = _read(base_and_browser, "normal", width, color_scheme="dark")
    assert not palette_violations(chart), chart


@pytest.mark.parametrize("scenario,expected", [("tw_missing", [(ORANGE, True)]), ("us_failed", [(NAVY, False)])])
def test_degraded_scenarios_keep_series_identity_and_do_not_invent_lines(base_and_browser, scenario, expected):
    chart = _read(base_and_browser, scenario, 390)
    assert [(p["stroke"], p["dash"] not in ("none", "")) for p in chart["paths"]] == expected, chart


def test_single_series_view_keeps_current_color(base_and_browser):
    chart = _read(base_and_browser, "normal", 390, view="VIX")
    assert chart["exists"] and len(chart["paths"]) == 1
    assert chart["paths"][0]["stroke"] == chart["ink"], chart                # VIX 單序列不套雙系列色


def test_both_missing_draws_no_chart(base_and_browser):
    assert _read(base_and_browser, "both_missing", 390)["exists"] is False


# ───────── 負控 ─────────

def test_mutation_changed_series_colour_is_flagged(base_and_browser):
    chart = _read(base_and_browser, "normal", 390, css="svg.uv3-chart path:nth-of-type(1){stroke:#0a3f87 !important}")
    assert palette_violations(chart), chart


def test_mutation_removed_dash_is_flagged(base_and_browser):
    chart = _read(base_and_browser, "normal", 390, css="svg.uv3-chart path{stroke-dasharray:none !important}")
    assert palette_violations(chart), chart


def test_mutation_coloured_label_text_is_flagged(base_and_browser):
    chart = _read(base_and_browser, "normal", 390, css="svg.uv3-chart text{fill:#d06a00 !important}")
    assert palette_violations(chart), chart
