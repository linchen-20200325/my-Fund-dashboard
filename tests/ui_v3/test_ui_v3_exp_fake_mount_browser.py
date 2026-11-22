# -*- coding: utf-8 -*-
"""🔍 找基金本地 FAKE 頁（Gate-M 方案 2a）的真瀏覽器守衛（slow lane；需要 streamlit 與 Chromium）。

與 `test_ui_v3_exp_fake_mount_apptest.py`（AppTest；不載入 CSS、沒有真實導覽）互補：這裡用**真的 `st.navigation` 路由**與真 Chromium，
量 390／1280 的版面、鍵盤、焦點、觸控尺寸與真實往返。🌍 資料是 `market_stubs` 的**合成 fixture**；🔍 資料是 `ui_v3.fixtures.exp_lookup_fake`。
不讀 secrets、不打任何真實來源。這不是 Cloud／真機驗證（那些 NOT VERIFIED）。

⚠️ 網路：瀏覽器端以 `page.on("request")` 驗證**瀏覽器沒有向非本機來源發請求**；伺服器端的零網路請求（socket 層守衛）由 AppTest 檔證明，這裡不重複宣稱。

驗：
1. 從 🌍 經導覽進 🔍（390 用頁首五格、1280 用側欄）；頁級 FAKE 橫幅與卡級 FAKE 標籤在每個狀態可見；沒有 🌍 的 Status Bar；
2. 無橫向溢出；主區內文字 ≥13px；輸入框與送出鈕觸控 ≥48px；
3. 鍵盤：Tab 依序到輸入框與送出鈕、焦點外框可見（2px）、不落在 `aria-disabled` 的 💼／🤖；Enter 可送出；
4. 🌍→🔍→⚙️ 往返：⚙️ 的逐列內容與只走 🌍→⚙️ 時逐值一致（🔍 不讀寫快照）；
5. 導覽：🌍／🔍／⚙️ 可進，💼／🤖 維持停用。
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
adapter.load = lambda sources: (ms.view(us="error"), ms.table())
from ui_v3 import app_preview
app_preview.main()
"""

_ROWS = """() => [...document.querySelectorAll('.uv3-health-row')].map(e => ({key: e.dataset.healthKey, state: e.dataset.healthState,
  reason: e.dataset.reason, asOf: e.dataset.asOf, fetched: e.dataset.fetchedAt}))"""

_MEASURE = """() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const small = [];
  for (const el of document.querySelectorAll('[data-block="page-fake"] *, [data-block="lookup-idle"] *, [data-block="lookup-result"] *')) {
    if (el.children.length) continue;
    if (el.textContent.trim() && parseFloat(getComputedStyle(el).fontSize) < 13) small.push(el.textContent.trim().slice(0, 20));
  }
  const box = (sel) => { const e = document.querySelector(sel); if (!e) return null; const r = e.getBoundingClientRect(); return {h: r.height, w: r.width}; };
  return {vw: document.documentElement.clientWidth, docScrollW: document.documentElement.scrollWidth,
          mainScrollW: main.scrollWidth, mainClientW: main.clientWidth, small,
          input: box('[data-testid="stTextInput"] input'), submit: box('[data-testid="stFormSubmitButton"] button'),
          title: (document.querySelector('h1') || {}).innerText,
          pageFake: (document.querySelector('[data-block="page-fake"]') || {}).innerText || null,
          fakeTags: [...document.querySelectorAll('[data-tag="fake"]')].map(e => e.innerText),
          statusbar: document.querySelectorAll('.uv3-statusbar').length,
          card: (document.querySelector('[data-block="lookup-result"], [data-block="lookup-idle"]') || {dataset: {}}).dataset.state || null,
          rows: [...document.querySelectorAll('[data-block="lookup-result"] [data-row]')].map(e => e.dataset.row)};
}"""

_FOCUS = """() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
  return {tag: e.tagName, label: e.getAttribute('aria-label') || (e.innerText || '').trim().slice(0, 20),
          disabled: !!e.closest('[aria-disabled="true"]'), outline: s.outlineStyle + ' ' + s.outlineWidth,
          visible: e.matches(':focus-visible'), inInput: !!e.closest('[data-testid="stTextInput"]'),
          inSubmit: !!e.closest('[data-testid="stFormSubmitButton"]')}; }"""

_DISABLED = """() => [...document.querySelectorAll('[data-nav][aria-disabled="true"]')].map(e => e.dataset.nav)"""


@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_exp_fake") / "app_exp_fake.py"
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
    requests = []
    page.on("request", lambda r: requests.append(r.url))
    page.goto(base + path, wait_until="networkidle")
    return ctx, page, requests


def _nav(page, width, suffix):
    scope = ".st-key-uv3-top-nav" if width <= 768 else '[data-testid="stSidebar"]'
    if suffix == "mkt":     # 預設頁（🌍）的 href 沒有 url_path 後綴：取不是 exp、不是 set 的那一個
        return page.locator(f'{scope} a[data-testid="stPageLink-NavLink"]:not([href$="exp"]):not([href$="set"])').first
    return page.locator(f'{scope} a[data-testid="stPageLink-NavLink"][href$="{suffix}"]').first


def _go_exp(page, width):
    page.wait_for_selector(".uv3-statusbar", timeout=60000)
    _nav(page, width, "exp").click()
    page.wait_for_selector('[data-block="page-fake"]', timeout=60000)
    page.wait_for_timeout(500)


def _go_settings(page, width):
    _nav(page, width, "set").click()
    page.wait_for_selector('[data-health="scope"]', timeout=60000)
    page.wait_for_timeout(500)


def _go_market(page, width):
    _nav(page, width, "mkt").click()
    page.wait_for_selector(".uv3-statusbar", timeout=60000)
    page.wait_for_timeout(500)


def _submit(page, code):
    page.locator('[data-testid="stTextInput"] input').fill(code)
    page.keyboard.press("Enter")
    page.wait_for_selector('[data-block="lookup-result"]', timeout=60000)
    page.wait_for_timeout(400)


def _local_only(base, requests):
    host = base.split("//", 1)[1].split("/", 1)[0].rsplit(":", 1)[0]
    return [u for u in requests if u.split("//", 1)[-1].split("/", 1)[0].rsplit(":", 1)[0] not in (host, "localhost", "127.0.0.1")
            and not u.startswith(("data:", "blob:", "about:"))]


@pytest.mark.parametrize("width", [390, 1280])
def test_navigate_to_the_search_page_marks_fake_everywhere_without_overflow_and_with_48px_targets(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page, requests = _new(browser, base, width)
    try:
        _go_exp(page, width)
        idle = page.evaluate(_MEASURE)
        for code, state in (("FAKE-OK01", "result"), ("FAKE-FAIL1", "failed"), ("FAKE-PAGE2", "unmatched"), ("ABC123", "unmatched"), ("   ", "blocked")):
            _submit(page, code)
            m = page.evaluate(_MEASURE)
            assert m["card"] == state, (code, m["card"])
            assert m["fakeTags"] == ["FAKE 模擬"], (code, m["fakeTags"])                       # 卡級 FAKE 恆顯
            assert m["pageFake"] and "FAKE" in m["pageFake"], (code, m["pageFake"])            # 頁級 FAKE 恆顯
            assert m["docScrollW"] <= m["vw"] and m["mainScrollW"] <= m["mainClientW"], ("不得橫向溢出", code, m)
            assert not m["small"], ("文字不得小於 13px", m["small"])
            if state == "result":
                assert m["rows"] == ["status", "input-code", "name", "dividend-mode", "inception", "mgmt-fee"], m["rows"]   # 狀態列＋五欄
    finally:
        ctx.close()
    assert idle["title"] == "找一檔基金" and idle["card"] == "idle" and idle["fakeTags"] == ["FAKE 模擬"], idle
    assert idle["pageFake"] and "FAKE" in idle["pageFake"] and idle["statusbar"] == 0, idle          # 沒有 🌍 的 Status Bar
    assert idle["input"]["h"] >= 48 and idle["submit"]["h"] >= 48 and idle["submit"]["w"] >= 48, idle
    assert idle["docScrollW"] <= idle["vw"] and idle["mainScrollW"] <= idle["mainClientW"], idle
    assert _local_only(base, requests) == [], _local_only(base, requests)                      # 瀏覽器沒有向非本機來源發請求


@pytest.mark.parametrize("width", [390, 1280])
def test_keyboard_reaches_input_then_submit_with_visible_focus_and_never_a_disabled_nav(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page, _ = _new(browser, base, width)
    try:
        _go_exp(page, width)
        path = []
        for _ in range(16):
            page.keyboard.press("Tab")
            path.append(page.evaluate(_FOCUS))
        focused = [f for f in path if f]
        assert focused and not any(f["disabled"] for f in focused), ("焦點不得落在停用的導覽項目", focused)
        on_input = [f for f in focused if f["inInput"]]
        on_submit = [f for f in focused if f["inSubmit"]]
        assert on_input and on_submit, ("鍵盤必須能到達輸入框與送出鈕", focused)
        assert path.index(on_input[0]) < path.index(on_submit[0]), "輸入框在送出鈕之前"
        for f in on_input + on_submit:
            assert f["visible"] and f["outline"].startswith("solid") and f["outline"].endswith("2px"), ("焦點外框必須可見（2px 實線）", f)
        # Enter 可送出：從輸入框送出，不用滑鼠
        page.locator('[data-testid="stTextInput"] input').focus()
        page.keyboard.type("FAKE-OK01")
        page.keyboard.press("Enter")
        page.wait_for_selector('[data-block="lookup-result"][data-state="result"]', timeout=60000)
    finally:
        ctx.close()


@pytest.mark.parametrize("width", [390, 1280])
def test_navigation_enables_exactly_market_search_and_settings(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page, _ = _new(browser, base, width)
    try:
        page.wait_for_selector(".uv3-statusbar", timeout=60000)
        disabled = sorted(page.evaluate(_DISABLED))
        enabled = [s for s in ("mkt", "exp", "set") if _nav(page, width, s).count() == 1]
    finally:
        ctx.close()
    assert set(disabled) == {"ast", "ai"}, disabled
    assert enabled == ["mkt", "exp", "set"], enabled


@pytest.mark.parametrize("width", [390, 1280])
def test_round_trip_market_search_settings_keeps_the_health_snapshot_unchanged(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page, _ = _new(browser, base, width)
    try:
        page.wait_for_selector(".uv3-statusbar", timeout=60000)
        _go_settings(page, width)
        control = page.evaluate(_ROWS)                                  # 只走 🌍→⚙️ 的快照
        _go_exp(page, width)
        _submit(page, "FAKE-OK01")
        _go_settings(page, width)
        after_search = page.evaluate(_ROWS)
        _go_market(page, width)
        _go_exp(page, width)
        persisted = page.evaluate(_MEASURE)                             # 回到 🔍：上一次的（淨化後）結果仍在 session
        _go_settings(page, width)
        final = page.evaluate(_ROWS)
    finally:
        ctx.close()
    assert len(control) == 5 and control == after_search == final, (control, after_search, final)
    assert persisted["card"] == "result" and persisted["fakeTags"] == ["FAKE 模擬"], persisted


@pytest.mark.parametrize("width", [390, 1280])
def test_direct_visit_without_market_snapshot_keeps_search_working_and_settings_honest(base_and_browser, width):
    base, browser = base_and_browser
    ctx, page, _ = _new(browser, base, width, path="/exp")
    try:
        page.wait_for_selector('[data-block="page-fake"]', timeout=60000)
        _submit(page, "FAKE-OK02")
        m = page.evaluate(_MEASURE)
        _nav(page, width, "set").click()
        page.wait_for_selector('[data-health="no-snapshot"]', timeout=60000)      # 🔍 沒有替 ⚙️ 製造快照
    finally:
        ctx.close()
    assert m["card"] == "result" and m["fakeTags"] == ["FAKE 模擬"] and m["statusbar"] == 0, m
