# -*- coding: utf-8 -*-
"""🌍 市場頁「使用者端調整」瀏覽器級守衛（slow lane；需要 streamlit 與 Chromium；只加測試，不改 production）。

補 `test_ui_v3_market_page_browser.py`／`docs/evidence/ui_a2_mkt_ops_qa_2026_11_21/` 尚未覆蓋、且**不需要任何新 Gate** 就能量的三件事：
1. **WCAG 1.4.12 文字間距覆寫**（行高 1.5、字距 .12em、詞距 .16em、段距 2em）：頁面不得出現橫向溢出，也不得多出被裁切的容器。
2. **forced-colors（高對比）**：顏色全被系統收掉後，主圖兩條線仍須靠「實線／虛線」分辨（非顏色識別）。
3. **鍵盤順序可逆**：Tab 走 N 站後 Shift+Tab 走回，須逐站為正向順序的鏡像（無單向陷阱、無跳站）。

資料：`market_stubs` 合成 fixture（人造數值，不是市場資料；不連任何外部來源）。⚠️ 本檔結果是「本機／CI Chromium＋合成 fixture」，
**不是** Cloud 部署或真機（iOS／Android／系統字級）驗證。

4. **導覽連結的可見焦點指示**（WCAG 2.4.7）：≤768 頁首五格有 2px 實線環（正向守衛）；**≥769 側欄導覽連結目前沒有任何可見焦點指示**
   （outline／box-shadow／背景皆與未聚焦相同）——以 `xfail(strict=True)` 鎖成 known-gap（修了會轉紅，提醒移除標記），**本批不修**（改導覽樣式需 Gate）。

**刻意不斷言的事（只在 `docs/evidence/ui_a5_mkt_adaptation_2026_11_21/report.md` 以 FACT 記錄）**
- 暗色（`prefers-color-scheme: dark`）：頁面維持淺色、文字可讀；這是現況，不在任何核准規格內，故不鎖。
- Chromium 對可捲動容器（`stMain`，`tabindex=0`）給的 Tab 停駐點沒有可見焦點環：那是 Streamlit／瀏覽器原生行為，要改須新視覺元件，屬 Gate 差額。

**變異驗證（負控）**：文字間距下把卡片撐寬 → 必須被判溢出；forced-colors 下把虛線拿掉 → 必須被判「僅靠顏色」；
Tab 走訪結果被反轉／插入空站 → 必須被判不可逆（判定函式層級）。負控全在記憶體內現編。
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

# WCAG 2.1 SC 1.4.12 的四個覆寫值（行高≥1.5、段距≥2em、字距≥.12em、詞距≥.16em）
_TEXT_SPACING_CSS = ("*{line-height:1.5 !important;letter-spacing:.12em !important;word-spacing:.16em !important}"
                     " p{margin-bottom:2em !important}")

_LAYOUT_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth;
  const clipped = [];
  for (const e of main.querySelectorAll('*')) {
    const s = getComputedStyle(e);
    if (s.display === 'none' || !e.getClientRects().length) continue;
    const tag = e.tagName.toLowerCase();
    if (['svg', 'path', 'g'].includes(tag)) continue;
    const clipY = s.overflowY !== 'visible' && e.scrollHeight > e.clientHeight + 1 && e.clientHeight > 0;
    const clipX = s.overflowX !== 'visible' && e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0;
    if (clipY || clipX) clipped.push(tag);
  }
  return {vw, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth,
          nClipped: clipped.length};
}
"""

_CHART_JS = r"""
() => {
  const svg = document.querySelector('[data-testid="stMain"] svg.uv3-chart');
  if (!svg) return {exists: false};
  const paths = [...svg.querySelectorAll('path')].map(p => { const c = getComputedStyle(p); return {stroke: c.stroke, dash: c.strokeDasharray}; });
  return {exists: true, paths};
}
"""

_STOP_JS = r"""
() => { const a = document.activeElement; if (!a || a === document.body) return null;
  const lab = (a.getAttribute('aria-label') || a.innerText || a.value || '').replace(/\s+/g, ' ').trim();
  return a.tagName + '|' + Array.from(lab).slice(0, 12).join(''); }
"""


# ───────────────────────── 判定函式（負控與正向共用） ─────────────────────────

def text_spacing_violations(before, after):
    bad = []
    if after["docScrollW"] > after["vw"]:
        bad.append(("文字間距覆寫後整頁橫向溢出", after["docScrollW"], after["vw"]))
    if after["mainScrollW"] > after["mainClientW"] + 1:
        bad.append(("文字間距覆寫後主內容區橫向溢出", after["mainScrollW"], after["mainClientW"]))
    if after["nClipped"] > before["nClipped"]:
        bad.append(("文字間距覆寫後多出被裁切的容器", before["nClipped"], after["nClipped"]))
    return bad


def non_color_series_violations(chart):
    """forced-colors 下顏色被收掉：兩條線至少要有不同的 stroke-dasharray，否則只剩顏色可分（違反非顏色識別）。"""
    if not chart["exists"]:
        return [("主圖不存在",)]
    paths = chart["paths"]
    if len(paths) < 2:
        return [("主圖序列數不足 2", len(paths))]
    if len({p["dash"] for p in paths}) < 2:
        return [("兩條序列 stroke-dasharray 相同，顏色被收掉後無法分辨", [p["dash"] for p in paths])]
    return []


def tab_reversibility_violations(fwd, rev):
    """正向走 N 站 [s0..s(N-1)]，再 Shift+Tab 走 N-1 站，期望 [s(N-2)..s0]。"""
    if None in fwd or None in rev:
        return [("Tab 途中焦點掉到 document.body（出現空站）", fwd, rev)]
    want = list(reversed(fwd[:-1]))
    if rev != want:
        return [("Shift+Tab 不是 Tab 順序的鏡像", want, rev)]
    return []


# ───────────────────────── fixtures ─────────────────────────

@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_market_adapt") / "app_market_adapt.py"
    app.write_text(_APP, encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


def _open(browser, base, scenario, width, **ctx_kw):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW",
                              has_touch=width <= 768, **ctx_kw)
    page = ctx.new_page()
    page.goto(f"{base}/?scenario={scenario}", wait_until="networkidle")
    page.wait_for_selector('[data-field="market_state"]', timeout=60000)
    page.wait_for_timeout(1200)
    return ctx, page


def _spacing(base_and_browser, scenario, width, *, extra_css=None):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, scenario, width)
    try:
        before = page.evaluate(_LAYOUT_JS)
        page.add_style_tag(content=_TEXT_SPACING_CSS + (extra_css or ""))
        page.wait_for_timeout(500)
        return before, page.evaluate(_LAYOUT_JS)
    finally:
        ctx.close()


def _chart_forced_colors(base_and_browser, width, *, css=None):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, "normal", width, forced_colors="active")
    try:
        if css:
            page.add_style_tag(content=css)
            page.wait_for_timeout(300)
        return page.evaluate(_CHART_JS)
    finally:
        ctx.close()


_FOCUS_JS = r"""
() => { const a = document.activeElement; if (!a || a === document.body) return null;
  const s = getComputedStyle(a);
  return {tag: a.tagName, fv: a.matches(':focus-visible'), outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth,
          boxShadow: s.boxShadow, bg: s.backgroundColor, deco: s.textDecorationLine}; }
"""
_UNFOCUSED_JS = r"""
() => { const a = document.querySelector('a[data-testid="stPageLink-NavLink"]'); const s = getComputedStyle(a);
  return {outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth, boxShadow: s.boxShadow, bg: s.backgroundColor, deco: s.textDecorationLine}; }
"""


def focus_indicator_violations(unfocused, focused):
    """聚焦後須有「可見」變化：實線 outline ≥2px、或 box-shadow、或背景／底線與未聚焦不同；否則鍵盤使用者看不到焦點在哪。"""
    if focused is None or focused["tag"] != "A":
        return [("焦點不在導覽連結上", focused)]
    if not focused["fv"]:
        return [("導覽連結聚焦但不是 :focus-visible（鍵盤來源）", focused)]
    ring = focused["outlineStyle"] not in ("none", "hidden") and float(focused["outlineWidth"].removesuffix("px")) >= 2
    shadow = focused["boxShadow"] != "none" and focused["boxShadow"] != unfocused["boxShadow"]
    changed = focused["bg"] != unfocused["bg"] or focused["deco"] != unfocused["deco"]
    return [] if (ring or shadow or changed) else [("導覽連結聚焦後沒有任何可見焦點指示", unfocused, focused)]


def _nav_focus(base_and_browser, width, *, css=None):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, "normal", width)
    try:
        if css:
            page.add_style_tag(content=css)
            page.wait_for_timeout(300)
        unfocused = page.evaluate(_UNFOCUSED_JS)
        for _ in range(6):
            page.keyboard.press("Tab")
            f = page.evaluate(_FOCUS_JS)
            if f and f["tag"] == "A":
                return unfocused, f
        return unfocused, None
    finally:
        ctx.close()


_N_STOPS = 10   # 與 `ui_a2_mkt_ops_qa` 記錄的每輪 Tab 站數一致（390／1280 皆為 10，含 Streamlit 開發工具列兩站）


def _tab_walk(base_and_browser, width, *, js=None):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, "normal", width)
    try:
        if js:
            page.evaluate(js)
        fwd = []
        for _ in range(_N_STOPS):
            page.keyboard.press("Tab")
            fwd.append(page.evaluate(_STOP_JS))
        rev = []
        for _ in range(_N_STOPS - 1):
            page.keyboard.press("Shift+Tab")
            rev.append(page.evaluate(_STOP_JS))
        return fwd, rev
    finally:
        ctx.close()


# ───────────────────────── 正向守衛 ─────────────────────────

@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_text_spacing_override_causes_no_overflow_or_new_clipping(base_and_browser, scenario, width):
    before, after = _spacing(base_and_browser, scenario, width)
    assert not text_spacing_violations(before, after), (text_spacing_violations(before, after), before, after)


@pytest.mark.parametrize("width", _WIDTHS)
def test_forced_colors_keeps_series_distinguishable_without_colour(base_and_browser, width):
    chart = _chart_forced_colors(base_and_browser, width)
    assert not non_color_series_violations(chart), (non_color_series_violations(chart), chart)


@pytest.mark.parametrize("width", _WIDTHS)
def test_keyboard_order_is_reversible_with_shift_tab(base_and_browser, width):
    fwd, rev = _tab_walk(base_and_browser, width)
    assert not tab_reversibility_violations(fwd, rev), (tab_reversibility_violations(fwd, rev), fwd, rev)


def test_mobile_top_nav_link_shows_visible_focus_indicator(base_and_browser):
    unfocused, focused = _nav_focus(base_and_browser, 390)
    assert not focus_indicator_violations(unfocused, focused), (focus_indicator_violations(unfocused, focused), unfocused, focused)


@pytest.mark.xfail(strict=True, reason="KNOWN-GAP（未修，需導覽樣式 Gate）：≥769 側欄導覽連結聚焦後無任何可見焦點指示；"
                                       "見 docs/evidence/ui_a5_mkt_adaptation_2026_11_21/report.md §4。修好後本測試會 XPASS(strict)→紅，屆時移除此標記。")
def test_desktop_sidebar_nav_link_shows_visible_focus_indicator_known_gap(base_and_browser):
    unfocused, focused = _nav_focus(base_and_browser, 1280)
    assert not focus_indicator_violations(unfocused, focused), (focus_indicator_violations(unfocused, focused), unfocused, focused)


# ───────────────────────── 負控（變異驗證） ─────────────────────────

def test_mutation_wide_card_under_text_spacing_is_flagged(base_and_browser):
    before, after = _spacing(base_and_browser, "normal", 390, extra_css=".uv3-card{min-width:900px !important}")
    assert text_spacing_violations(before, after), after


def test_mutation_removed_dash_under_forced_colors_is_flagged(base_and_browser):
    chart = _chart_forced_colors(base_and_browser, 390, css="svg.uv3-chart path{stroke-dasharray:none !important}")
    assert non_color_series_violations(chart), chart


def test_mutation_non_mirror_or_empty_stop_is_flagged_by_tab_reversibility_check(base_and_browser):
    """負控：以真實走訪的結果為基底，把 rev 反過來／插入空站，判定函式必須報（正向走訪本身為空，作對照）。
    ⚠️ 這是判定函式層級的負控，不是對 production 的 DOM 變異（正 tabindex 仍是可逆順序，不能拿來當負控）。"""
    fwd, rev = _tab_walk(base_and_browser, 390)
    assert not tab_reversibility_violations(fwd, rev)        # 對照：未變異時為空
    assert tab_reversibility_violations(fwd, list(rev)[::-1]), "把 rev 反過來（非鏡像）必須被判為不可逆"
    assert tab_reversibility_violations(fwd, rev[:-1] + [None]), "出現空站（焦點掉到 body）必須被判"


def test_mutation_focus_ring_added_makes_desktop_gap_check_pass_and_removed_ring_is_flagged_on_mobile(base_and_browser):
    """負控（真 DOM 變異）：桌機側欄加上 2px 實線焦點環 → 判定轉為無違規（證明判定看得到「有環」）；
    手機頁首把環與底線拿掉 → 判定必須報（證明判定看得到「沒環」）。"""
    unfocused, focused = _nav_focus(base_and_browser, 1280,
                                    css='a[data-testid="stPageLink-NavLink"]:focus-visible{outline:2px solid #fff !important}')
    assert not focus_indicator_violations(unfocused, focused), focused
    unfocused, focused = _nav_focus(base_and_browser, 390,
                                    css='a[data-testid="stPageLink-NavLink"]:focus-visible{outline:none !important;box-shadow:none !important;'
                                        'background:rgb(24,37,74) !important;text-decoration:none !important}')
    assert focus_indicator_violations(unfocused, focused), focused
