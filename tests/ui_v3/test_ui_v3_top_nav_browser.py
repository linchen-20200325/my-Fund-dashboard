# -*- coding: utf-8 -*-
"""BL-0544 S1 手機頁首五格：真瀏覽器量測（slow lane；需要 streamlit 與 Chromium；`DEC-2026-11-07-02`）。

AppTest 不載入 CSS，靜態 CSS 字串檢查也量不到實際版面；這一檔用 Chromium 量真的 bounding box，鎖住 PR 實測時抓到的缺陷：
未掛載的四項是 `st.markdown`，Streamlit 預設讓它 shrink-to-fit → 實測只有 30～40px 寬（低於 48px 觸控下限、五格不等寬），
且 `stMarkdownContainer` 的負 margin-bottom 讓外層高度低估，190% 字體時內容被頁首裁掉。

資料：`market_stubs` 的**合成 fixture**（不是市場資料；不打任何網路）。量到的是 Shell 版面，與資料值無關。
每格驗：在視窗內、寬與高都 ≥ 48、五格等寬（±1px）且不重疊；整頁與頁首都不橫向溢出；≥769 頁首不顯示、側欄在；
未掛載四項 `aria-disabled="true"` 且沒有 href；🌍 選取態不只靠顏色（粗體＋底線）；Tab 可聚焦 🌍、不可聚焦未掛載項且焦點外框可見；
≤768 沒有任何貼底（fixed）元素；字放大 190%（以放大 rem 與頁首字級模擬 Android textZoom）五格仍全部可見、不裁字、不橫捲。
"""

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
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
adapter.load = lambda sources: (ms.view(), ms.table())
from ui_v3 import app_preview
app_preview.main()
"""

_MEASURE = r"""
() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const nav = document.querySelector('.st-key-uv3-top-nav');
  const out = {vw, docScrollW: document.documentElement.scrollWidth, mainScrollW: document.querySelector('[data-testid="stMain"]').scrollWidth,
               mainClientW: document.querySelector('[data-testid="stMain"]').clientWidth,
               navDisplay: nav ? getComputedStyle(nav).display : null,
               sidebarDisplay: (document.querySelector('[data-testid="stSidebar"]') ? getComputedStyle(document.querySelector('[data-testid="stSidebar"]')).display : null)};
  if (!nav) return out;
  const hdr = document.querySelector('[data-testid="stHeader"]');
  const hr = hdr ? hdr.getBoundingClientRect() : null;
  out.navPosition = getComputedStyle(nav).position; out.navTop = nav.getBoundingClientRect().top;
  out.header = hr ? {top: hr.top, bottom: hr.bottom, left: hr.left, right: hr.right} : null;
  if (hr) { const hit = document.elementFromPoint((hr.left + hr.right) / 2, (hr.top + hr.bottom) / 2);
            out.headerCovered = !!hit && !hdr.contains(hit) && hit !== hdr; out.headerHitNav = !!hit && nav.contains(hit); }
  out.navScrollW = nav.scrollWidth; out.navClientW = nav.clientWidth;
  const nr = nav.getBoundingClientRect(); out.navBottom = nr.bottom; out.navScrollH = nav.scrollHeight; out.navClientH = nav.clientHeight;
  out.cells = [...nav.querySelectorAll('a[data-testid="stPageLink-NavLink"], .uv3-tn-disabled')].map(e => {
    const b = e.getBoundingClientRect(); const s = getComputedStyle(e);
    // 字被裁：文字 range 超出格子左右緣，或超出頁首下緣（頁首 overflow 會裁；emoji 字形框上緣的內部留白不算）
    let over = 0; const w = document.createTreeWalker(e, NodeFilter.SHOW_TEXT);
    while (w.nextNode()) { if (!w.currentNode.textContent.trim()) continue; const r = document.createRange(); r.selectNodeContents(w.currentNode);
      for (const q of r.getClientRects()) { if (q.right > b.right + 1 || q.left < b.left - 1 || q.bottom > nr.bottom + 1) over++; } }
    return {text: e.innerText.replace(/\s+/g, ' ').trim(), href: e.getAttribute('href'), ariaDisabled: e.getAttribute('aria-disabled'), x: b.x, r: b.right, y: b.y, bt: b.bottom,
            w: b.width, h: b.height, fw: s.fontWeight, deco: s.textDecorationLine, bb: s.borderBottomWidth, overflowingText: over};
  });
  out.fixed = [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).position === 'fixed' && e.getBoundingClientRect().height > 0
      && e.getBoundingClientRect().bottom >= vh - 2 && e.getBoundingClientRect().height < vh - 10).map(e => e.tagName + '.' + (e.className || '').toString().slice(0, 30));
  return out;
}
"""

_NAMES = ["市場", "資產", "找基金", "AI", "設定"]
_SOON = {"資產": "開發中", "找基金": "開發中", "AI": "尚未開放", "設定": "開發中"}


@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_top_nav") / "app_top_nav.py"
    app.write_text(_APP, encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


def _open(browser, base, width, zoom=None):
    ctx = browser.new_context(viewport={"width": width, "height": 844}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    page.goto(base + "/", wait_until="networkidle")
    page.wait_for_selector(".uv3-statusbar", timeout=60000)
    if zoom:
        k = zoom / 100
        page.add_style_tag(content=(
            f"html{{font-size:{16 * k}px !important}}"
            f".st-key-uv3-top-nav a[data-testid='stPageLink-NavLink'] p,.st-key-uv3-top-nav .uv3-tn-disabled{{font-size:{12 * k}px !important}}"
            f".st-key-uv3-top-nav .uv3-tn-icon{{font-size:{20 * k}px !important}}.st-key-uv3-top-nav .uv3-tn-soon{{font-size:{10 * k}px !important}}"))
    page.wait_for_timeout(1500)
    return ctx, page


@pytest.mark.parametrize("width", [374, 375, 390, 768])
def test_mobile_top_nav_five_equal_visible_cells_at_least_48px(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, width)
    try:
        m = page.evaluate(_MEASURE)
    finally:
        ctx.close()
    assert m["navDisplay"] == "flex" and m["sidebarDisplay"] == "none", m
    cells = m["cells"]
    assert len(cells) == 5, cells
    for cell, name in zip(cells, _NAMES):
        assert name in cell["text"], (name, cell)
        assert cell["x"] >= -0.5 and cell["r"] <= m["vw"] + 0.5, ("五格必須全部在視窗內", cell)
        assert cell["w"] >= 48 and cell["h"] >= 48, ("觸控目標不得小於 48px（含未掛載項）", cell)
        assert cell["overflowingText"] == 0, ("文字被裁", cell)
    widths = [c["w"] for c in cells]
    assert max(widths) - min(widths) <= 1.0, ("五格必須等寬", widths)
    assert all(cells[i]["r"] <= cells[i + 1]["x"] + 0.5 for i in range(4)), "五格不得重疊"
    assert m["navScrollW"] <= m["navClientW"] and m["docScrollW"] <= m["vw"] and m["mainScrollW"] <= m["mainClientW"], ("不得橫向捲動", m)
    assert not m["fixed"], ("手機不得有貼底 fixed 元素", m["fixed"])
    # 頁首是文件流內一排（非 sticky／fixed）：位置在頁面開頭，且與 Streamlit 自帶 stHeader 互不重疊、stHeader 沒被蓋住
    assert m["navPosition"] not in ("sticky", "fixed", "absolute"), m["navPosition"]
    assert m["header"] is not None
    assert m["navTop"] >= m["header"]["bottom"] - 0.5 and m["navTop"] < 200, ("頁首在 stHeader 之下、頁面開頭", m["navTop"], m["header"])
    assert not m["headerCovered"] and not m["headerHitNav"], "stHeader 被蓋住"


def test_mobile_top_nav_states_and_aria(base_and_browser):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        m = page.evaluate(_MEASURE)
        page.keyboard.press("Tab")
        focus_path = []
        for _ in range(8):
            focus_path.append(page.evaluate("""() => { const e = document.activeElement; if (!e) return null; const s = getComputedStyle(e);
                return {inNav: !!e.closest('.st-key-uv3-top-nav'), text: (e.innerText || '').replace(/\\s+/g, ' ').trim(), outline: s.outlineStyle + ' ' + s.outlineWidth,
                        visible: e.matches(':focus-visible')}; }"""))
            page.keyboard.press("Tab")
    finally:
        ctx.close()
    now, *soon = m["cells"]
    assert now["href"] is not None and now["ariaDisabled"] is None
    assert int(now["fw"]) >= 600 and now["deco"] == "underline" and float(now["bb"].replace("px", "")) >= 2, ("選取態不能只靠顏色", now)
    for cell, name in zip(soon, _NAMES[1:]):
        assert cell["ariaDisabled"] == "true" and cell["href"] is None, cell
        assert _SOON[name] in cell["text"], cell
    in_nav = [f for f in focus_path if f and f["inNav"]]
    assert len(in_nav) == 1 and "市場" in in_nav[0]["text"], ("頁首只有 🌍 可聚焦、未掛載項不可聚焦", focus_path)
    assert in_nav[0]["visible"] and in_nav[0]["outline"].startswith("solid"), ("焦點外框必須可見", in_nav[0])


@pytest.mark.parametrize("width", [769, 1280])
def test_desktop_keeps_sidebar_and_hides_top_nav(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, width)
    try:
        m = page.evaluate(_MEASURE)
    finally:
        ctx.close()
    assert m["navDisplay"] == "none" and m["sidebarDisplay"] == "block", m
    assert m["docScrollW"] <= m["vw"], m


@pytest.mark.parametrize("width", [374, 390])
def test_top_nav_survives_190_percent_text_without_clipping_or_scrolling(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page = _open(browser, base, width, zoom=190)
    try:
        m = page.evaluate(_MEASURE)
    finally:
        ctx.close()
    cells = m["cells"]
    assert len(cells) == 5
    for cell in cells:
        assert cell["x"] >= -0.5 and cell["r"] <= m["vw"] + 0.5 and cell["w"] >= 48 and cell["h"] >= 48, cell
        assert cell["overflowingText"] == 0, ("190% 字體文字被裁", cell)
    assert m["navScrollW"] <= m["navClientW"] and m["navScrollH"] <= m["navClientH"] + 1, ("頁首不得捲動（橫或直）", m)
    assert m["docScrollW"] <= m["vw"], m


def test_top_nav_scrolls_away_with_the_page_flow(base_and_browser):
    """客戶定案「非 sticky」：頁首隨文流移走是預期；這裡只鎖住它沒有變成吸頂或貼底的 overlay（不斷言吸頂）。"""
    base, browser = base_and_browser
    ctx, page = _open(browser, base, 390)
    try:
        before = page.evaluate("document.querySelector('.st-key-uv3-top-nav').getBoundingClientRect().top")
        page.evaluate("document.querySelector('[data-testid=\"stMain\"]').scrollTop = 600")
        page.wait_for_timeout(400)
        after = page.evaluate("document.querySelector('.st-key-uv3-top-nav').getBoundingClientRect().top")
        fixed = page.evaluate(_MEASURE)["fixed"]
    finally:
        ctx.close()
    assert after < before - 300, ("頁首應隨文流移走", before, after)
    assert not fixed
