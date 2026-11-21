# -*- coding: utf-8 -*-
"""⚙️ 設定→資料健康度（BL-0540 Phase 1A）的真瀏覽器操作守衛（slow lane；需要 streamlit 與 Chromium）。

與 `test_ui_v3_settings_health_page.py`（AppTest；不載入 CSS、沒有真實導覽）互補：這裡用**真的 `st.navigation` 路由**與真 Chromium，
量 390／1280 的版面、鍵盤與真實往返。資料是 `market_stubs` 的**合成 fixture**（`us="error"`：三條 ok、利率兩條取數失敗），
不是市場資料；不打任何網路、不讀 secrets。這不是 Cloud／真機驗證（那些 NOT VERIFIED）。

驗：
1. 從 🌍 經導覽進 ⚙️（390 用頁首五格、1280 用側欄）；頁首明示「市場與利率／不是全站」；逐列有 ok 也有 failed、失敗列不補日期；
2. 無橫向溢出（文件與主區）；主區內文字 ≥13px；返回市場的連結高度 ≥48；
3. 鍵盤：Tab 只落在可進的連結（🌍／⚙️／返回市場），不落在 `aria-disabled` 的三項；焦點外框可見；Enter 可返回市場；
4. 市場→設定→市場→設定 往返後逐列 data 屬性逐值一致；
5. 全新 session 直接開 `/set`：只有「尚未評估」與市場入口，沒有任何逐列；另一個 session 的快照不洩漏。
"""
import pathlib
import re
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
adapter.load = lambda sources: (ms.view(us="error"), ms.table())
from ui_v3 import app_preview
app_preview.main()
"""

_ROWS = """() => [...document.querySelectorAll('.uv3-health-row')].map(e => ({key: e.dataset.healthKey, state: e.dataset.healthState,
  reason: e.dataset.reason, asOf: e.dataset.asOf, fetched: e.dataset.fetchedAt, text: e.innerText.replace(/\\s+/g, ' ').trim()}))"""

_MEASURE = """() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const scope = document.querySelector('[data-health="scope"]');
  const small = [];
  for (const el of document.querySelectorAll('[data-health="scope"] *, .uv3-health-row *')) {
    if (el.children.length) continue;
    if (el.textContent.trim() && parseFloat(getComputedStyle(el).fontSize) < 13) small.push(el.textContent.trim().slice(0, 20));
  }
  const back = [...document.querySelectorAll('[data-testid="stMain"] a[data-testid="stPageLink-NavLink"]')].find(a => a.innerText.includes('市場與趨勢'));
  const bb = back ? back.getBoundingClientRect() : null;
  return {vw: document.documentElement.clientWidth, docScrollW: document.documentElement.scrollWidth,
          mainScrollW: main.scrollWidth, mainClientW: main.clientWidth, scopeText: scope ? scope.innerText : null,
          small, backH: bb ? bb.height : null, backW: bb ? bb.width : null,
          title: (document.querySelector('h1') || {}).innerText};
}"""


@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_settings_health") / "app_settings_health.py"
    app.write_text(_APP, encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser
        finally:
            browser.close()


def _new(browser, base, width, path="/"):
    ctx = browser.new_context(viewport={"width": width, "height": 844}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    page.goto(base + path, wait_until="networkidle")
    return ctx, page


def _nav_link(page, width):
    scope = ".st-key-uv3-top-nav" if width <= 768 else '[data-testid="stSidebar"]'
    return page.locator(f'{scope} a[data-testid="stPageLink-NavLink"][href$="set"]').first


def _market_nav_link(page, width):
    scope = ".st-key-uv3-top-nav" if width <= 768 else '[data-testid="stSidebar"]'
    return page.locator(f'{scope} a[data-testid="stPageLink-NavLink"]:not([href$="set"])').first


def _go_settings(page, width):
    page.wait_for_selector(".uv3-statusbar", timeout=60000)
    _nav_link(page, width).click()
    page.wait_for_selector('[data-health="scope"]', timeout=60000)
    page.wait_for_timeout(500)


def _back_to_market(page):
    page.locator('[data-testid="stMain"] a[data-testid="stPageLink-NavLink"]', has_text="市場與趨勢").first.click()
    page.wait_for_selector(".uv3-statusbar", timeout=60000)
    page.wait_for_timeout(800)


@pytest.mark.parametrize("width", [390, 1280])
def test_navigate_to_settings_shows_scope_rows_without_overflow_and_with_48px_back_link(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page = _new(browser, base, width)
    try:
        _go_settings(page, width)
        rows, m = page.evaluate(_ROWS), page.evaluate(_MEASURE)
    finally:
        ctx.close()
    assert m["title"] == "⚙️ 設定", m
    assert "市場與利率" in m["scopeText"] and "不是全站" in m["scopeText"], m["scopeText"]
    assert len(rows) == 5 and {"ok", "failed"} <= {r["state"] for r in rows}, rows
    for r in rows:
        if r["state"] != "ok":
            assert r["asOf"] == "" and r["fetched"] == "" and not re.search(r"\d{4}-\d{2}-\d{2}", r["text"]), r      # 不補日期
    assert m["docScrollW"] <= m["vw"] and m["mainScrollW"] <= m["mainClientW"], ("不得橫向溢出", m)
    assert not m["small"], ("主區內文字不得小於 13px", m["small"])
    assert m["backH"] is not None and m["backH"] >= 48, ("返回市場連結的觸控高度不足 48px", m["backH"])


@pytest.mark.parametrize("width", [390, 1280])
def test_keyboard_reaches_only_enabled_links_with_visible_focus_and_enter_returns_to_market(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page = _new(browser, base, width)
    try:
        _go_settings(page, width)
        path = []
        for _ in range(14):
            page.keyboard.press("Tab")
            path.append(page.evaluate("""() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
                return {tag: e.tagName, text: (e.innerText || '').replace(/\\s+/g, ' ').trim(), disabled: !!e.closest('[aria-disabled="true"]'),
                        isLink: !!e.closest('a[data-testid="stPageLink-NavLink"]'), outline: s.outlineStyle + ' ' + s.outlineWidth, shadow: s.boxShadow,
                        visible: e.matches(':focus-visible'), inMain: !!e.closest('[data-testid="stMain"]'), inSide: !!e.closest('[data-testid="stSidebar"]'), inTop: !!e.closest('.st-key-uv3-top-nav')}; }"""))
        focused = [f for f in path if f]
        assert focused and not any(f["disabled"] for f in focused), ("焦點不得落在未掛載（aria-disabled）項目", focused)
        links = [f for f in focused if f["isLink"]]
        assert any("市場" in f["text"] for f in links) and any("設定" in f["text"] for f in links), ("🌍／⚙️ 連結可由鍵盤到達", links)
        # 焦點外框：主區返回連結（本批 renderer）與手機頁首（既有守衛已鎖）必須可見。
        # ⚠️ 桌機側欄導覽連結實測沒有焦點外框（outline none、無 box-shadow）——這是既有 Shell（`ui_v3/shell/nav.py`）行為、不在本批授權範圍，
        #    不在此斷言也不在此修改；已登記於 PR 與 #1296（缺口，待總管指派 owner）。
        checked = [f for f in links if f["inMain"] or f["inTop"]]
        assert checked, links
        assert all(f["visible"] and f["outline"].startswith("solid") for f in checked), (
            "焦點外框必須可見", [(f["text"], f["outline"], f["shadow"]) for f in checked if not (f["visible"] and f["outline"].startswith("solid"))])
        main_back = [f for f in focused if f["inMain"] and f["isLink"] and "市場與趨勢" in f["text"]]
        assert main_back, ("返回市場連結可由鍵盤到達", focused)
        # Enter 返回市場：重新對焦到主區的返回連結再按 Enter
        page.locator('[data-testid="stMain"] a[data-testid="stPageLink-NavLink"]', has_text="市場與趨勢").first.focus()
        page.keyboard.press("Enter")
        page.wait_for_selector(".uv3-statusbar", timeout=60000)
        page.wait_for_timeout(800)
        assert page.evaluate("() => (document.querySelector('h1') || {}).innerText") == "🌍 市場與趨勢"
    finally:
        ctx.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_round_trip_keeps_the_same_rows(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page = _new(browser, base, width)
    try:
        _go_settings(page, width)
        first = page.evaluate(_ROWS)
        _back_to_market(page)
        _go_settings(page, width)
        second = page.evaluate(_ROWS)
        _back_to_market(page)
        market_title = page.evaluate("() => (document.querySelector('h1') || {}).innerText")
    finally:
        ctx.close()
    assert first == second and len(first) == 5, (first, second)           # 往返後逐列（key／state／reason／as_of／fetched_at／可見文字）逐值一致
    assert market_title == "🌍 市場與趨勢"


@pytest.mark.parametrize("width", [390, 1280])
def test_fresh_session_on_settings_url_has_no_rows_and_other_sessions_never_leak(base_and_browser, width):
    base, browser = base_and_browser
    owner_ctx, owner = _new(browser, base, width)
    try:
        _go_settings(owner, width)                                         # 這個 session 有快照
        fresh_ctx, fresh = _new(browser, base, width, path="/set")
        try:
            fresh.wait_for_selector('[data-health="no-snapshot"]', timeout=60000)
            rows, m = fresh.evaluate(_ROWS), fresh.evaluate(_MEASURE)
            assert rows == [] and "市場與利率" not in (m["scopeText"] or ""), (rows, m)
            assert fresh.locator('[data-testid="stMain"] a[data-testid="stPageLink-NavLink"]', has_text="市場與趨勢").count() == 1
            assert m["docScrollW"] <= m["vw"]
        finally:
            fresh_ctx.close()
        assert len(owner.evaluate(_ROWS)) == 5                             # 原 session 不受影響
    finally:
        owner_ctx.close()
