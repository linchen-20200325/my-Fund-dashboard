# -*- coding: utf-8 -*-
"""預覽殼層的真瀏覽器測試（BL-0484／BL-0479；D1 方案 A；slow lane；需要 streamlit 與 Chromium）。

起 `ui_v2/app_preview.py`（真的 `st.navigation(position="hidden")` ＋ 殼層），不打任何資料來源（本機／CI 沒有憑證，
各頁走既有的「尚未設定」路徑）。客戶 `DEC-2026-10-27-11`（4A）要求「必須實測 390px」：

1. **390×844（手機）**：底部導覽可見、固定在視窗底、五格等寬同一列、順序與頁名＝`PAGES`；每格寬高 ≥ 44px；
   目前頁有粗體＋底線＋色條；整頁與 `stMain` 都不橫捲；內容底部讓出導覽的高度（不被蓋住）；
   **從任一頁一次點擊就到另一個主頁**（≤ 2 次互動的上限，這裡是 1 次）；換頁後沒有「Page not found」、沒有例外；
   手機畫面沒有任何「切回舊版」之類的出口文字。
2. **1280／1440（桌機）**：深色側欄（`#0e1117`）固定在左、五個連結同一欄 ≥ 44px 高、順序與頁名＝`PAGES`；
   底部導覽不顯示；主內容區淺色；一次點擊換頁；`/set` 直接開啟時目前頁標在設定（OAuth 落點不受殼層影響）。
3. **斷點邊界**：768 寬（含）是手機（底部導覽顯示）、769 寬是桌機（底部導覽不顯示）。
4. 每一頁的顏色不是唯一語意載體：目前頁的粗體與底線由瀏覽器量到的 computed style 驗。

⚠️ 本檔量的是殼層本身；頁內內容（數字、燈、卡片）屬各頁測試，本檔不碰。
"""

import pathlib
import sys

import pytest

# 整檔標 slow：畫面測試不進 fast lane（守衛：tests/ui_v2/test_ui_v2_lane_guards.py）。
pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_HERE))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）

_APP = _ROOT / "ui_v2" / "app_preview.py"

# (slug, url 路徑, 頁名)。預設頁（mkt）的網址是根路徑；其餘為 url_path。頁名逐字取自 `PAGES`（fast lane 守衛另鎖）。
_PAGES = (
    ("mkt", "", "市場與趨勢"),
    ("alo", "alo", "資產配置"),
    ("hld", "hld", "我的持股"),
    ("exp", "exp", "找基金"),
    ("set", "set", "設定"),
)
_SETTLE_MS = 4500
_DARK = "rgb(14, 17, 23)"
_LIGHT = "rgb(246, 248, 250)"


@pytest.fixture(scope="module")
def browser_page():
    playwright_api = _ui_v2_chromium.import_sync_api()
    with playwright_api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)  # 先確認瀏覽器在，再起 streamlit
        try:
            with _ui_v2_chromium.streamlit_server(_APP) as base:
                yield browser, base
        finally:
            browser.close()


def _open(browser, base, path, width, height=844):
    context = browser.new_context(viewport={"width": width, "height": height}, has_touch=width <= 768)
    tab = context.new_page()
    tab.goto(f"{base}/{path}", wait_until="networkidle")
    tab.wait_for_timeout(_SETTLE_MS)
    return context, tab


_MEASURE = """
() => {
  const q = (s) => document.querySelector(s);
  const rect = (e) => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; };
  const links = (root) => Array.from(document.querySelectorAll(root + ' [data-testid="stPageLink-NavLink"]')).map((a) => ({
    text: a.textContent.trim(), rect: rect(a), fw: getComputedStyle(a.querySelector('p')).fontWeight,
    deco: getComputedStyle(a.querySelector('p')).textDecorationLine,
  }));
  const main = q('[data-testid="stMain"]');
  const bn = q('.st-key-shell-bottom-nav');
  const block = q('[data-testid="stMainBlockContainer"]');
  return {
    docSW: document.documentElement.scrollWidth, docCW: document.documentElement.clientWidth,
    mainSW: main.scrollWidth, mainCW: main.clientWidth,
    exceptions: document.querySelectorAll('[data-testid="stException"]').length,
    bodyText: document.body.innerText,
    appBg: getComputedStyle(q('.stApp')).backgroundColor,
    sbBg: getComputedStyle(q('[data-testid="stSidebar"]')).backgroundColor,
    sbRect: rect(q('[data-testid="stSidebar"]')),
    bnDisplay: getComputedStyle(bn).display, bnRect: rect(bn),
    side: links('[data-testid="stSidebar"]'), bottom: links('.st-key-shell-bottom-nav'),
    nowSide: Array.from(document.querySelectorAll('[data-testid="stSidebar"] [class*="-isnow"]')).map((e) => (e.className.match(/st-key-shell-side-[a-z-]+/) || [''])[0]),
    nowBottom: Array.from(document.querySelectorAll('.st-key-shell-bottom-nav [class*="-isnow"]')).map((e) => (e.className.match(/st-key-shell-bottom-[a-z-]+/) || [''])[0]),
    blockPadBottom: parseFloat(getComputedStyle(block).paddingBottom),
    viewH: window.innerHeight,
  };
}
"""

_NAMES = [name for _slug, _path, name in _PAGES]


def _names(entries):
    """連結文字去掉圖示後的名稱（圖示是 emoji，與名稱連在一起）。"""
    return [next(n for n in _NAMES if e["text"].endswith(n)) for e in entries]


# ═══════════════════════ 1. 手機 390×844 ═══════════════════════


@pytest.mark.parametrize("slug,path,name", _PAGES)
def test_390_底部導覽五主頁_固定在底_可點_不橫捲(browser_page, slug, path, name):
    browser, base = browser_page
    context, tab = _open(browser, base, path, 390)
    try:
        m = tab.evaluate(_MEASURE)
        # 版面
        assert m["exceptions"] == 0
        assert "Page not found" not in m["bodyText"]
        assert m["docSW"] <= m["docCW"] and m["mainSW"] <= m["mainCW"], (m["docSW"], m["mainSW"], m["mainCW"])
        # 底部導覽：顯示、貼視窗底、整列寬
        assert m["bnDisplay"] == "block"
        assert abs(m["bnRect"]["y"] + m["bnRect"]["h"] - m["viewH"]) <= 1.5, m["bnRect"]
        assert m["bnRect"]["x"] == 0 and abs(m["bnRect"]["w"] - 390) <= 1
        # 五格、順序＝PAGES、同一列等寬
        assert _names(m["bottom"]) == _NAMES
        ys = {round(e["rect"]["y"]) for e in m["bottom"]}
        assert len(ys) == 1, ys
        widths = [round(e["rect"]["w"]) for e in m["bottom"]]
        assert max(widths) - min(widths) <= 1 and sum(widths) <= 391, widths
        # 觸控目標 ≥ 44px
        for entry in m["bottom"]:
            assert entry["rect"]["w"] >= 44 and entry["rect"]["h"] >= 44, entry
        # 目前頁恰好一格，且粗體＋底線（顏色以外的辨識）
        assert m["nowBottom"] == [f"st-key-shell-bottom-{slug}-isnow"], m["nowBottom"]
        current = next(e for e in m["bottom"] if e["text"].endswith(name))
        assert int(current["fw"]) >= 700 and "underline" in current["deco"], current
        others = [e for e in m["bottom"] if not e["text"].endswith(name)]
        assert all(int(e["fw"]) < 700 and "underline" not in e["deco"] for e in others), others
        # 內容底部讓出導覽的高度（不被蓋住）
        assert m["blockPadBottom"] >= m["bnRect"]["h"], (m["blockPadBottom"], m["bnRect"]["h"])
        # 不得有「切回舊版」之類的死路出口
        for banned in ("切回舊版", "前往舊站", "回到舊版"):
            assert banned not in m["bodyText"], banned
    finally:
        context.close()


def test_390_從任一頁一次點擊到任一主頁_換頁後無例外(browser_page):
    browser, base = browser_page
    context, tab = _open(browser, base, "", 390)
    try:
        for target_slug, target_path, target_name in _PAGES[1:] + _PAGES[:1]:
            before = tab.url
            tab.locator('.st-key-shell-bottom-nav [data-testid="stPageLink-NavLink"]', has_text=target_name).first.click()
            tab.wait_for_timeout(_SETTLE_MS)
            assert tab.url.rstrip("/").endswith(("/" + target_path).rstrip("/")) or target_path == "", (before, tab.url)
            m = tab.evaluate(_MEASURE)
            assert m["exceptions"] == 0 and "Page not found" not in m["bodyText"]
            assert m["nowBottom"] == [f"st-key-shell-bottom-{target_slug}-isnow"], (target_slug, m["nowBottom"])
            assert m["mainSW"] <= m["mainCW"]
    finally:
        context.close()


def test_390_網址直入設定頁_目前頁標對(browser_page):
    """網址直入（deep link）會新開 session，殼層仍要把目前頁標對；`/set` 是 OAuth 落點，殼層不得改它。"""
    browser, base = browser_page
    context, tab = _open(browser, base, "set", 390)
    try:
        m = tab.evaluate(_MEASURE)
        assert m["nowBottom"] == ["st-key-shell-bottom-set-isnow"]
        assert tab.url.rstrip("/").endswith("/set")
    finally:
        context.close()


# ═══════════════════════ 2. 桌機 1280／1440 ═══════════════════════


@pytest.mark.parametrize("width", [1280, 1440])
@pytest.mark.parametrize("slug,path,name", _PAGES)
def test_桌機_深色側欄固定_淺色主區_底部導覽不顯示(browser_page, width, slug, path, name):
    browser, base = browser_page
    context, tab = _open(browser, base, path, width, 800)
    try:
        m = tab.evaluate(_MEASURE)
        assert m["exceptions"] == 0 and "Page not found" not in m["bodyText"]
        assert m["docSW"] <= m["docCW"] and m["mainSW"] <= m["mainCW"]
        assert m["sbBg"] == _DARK and m["appBg"] == _LIGHT, (m["sbBg"], m["appBg"])
        assert m["sbRect"]["x"] == 0 and m["sbRect"]["w"] >= 200
        assert m["bnDisplay"] == "none"
        assert _names(m["side"]) == _NAMES
        assert len({round(e["rect"]["x"]) for e in m["side"]}) == 1                     # 同一欄
        ys = [e["rect"]["y"] for e in m["side"]]
        assert ys == sorted(ys)
        for entry in m["side"]:
            assert entry["rect"]["h"] >= 44, entry
        assert m["nowSide"] == [f"st-key-shell-side-{slug}-isnow"], m["nowSide"]
        current = next(e for e in m["side"] if e["text"].endswith(name))
        assert int(current["fw"]) >= 700 and "underline" in current["deco"], current
        assert all(int(e["fw"]) < 700 for e in m["side"] if not e["text"].endswith(name))
    finally:
        context.close()


def test_桌機_一次點擊換頁(browser_page):
    browser, base = browser_page
    context, tab = _open(browser, base, "", 1280, 800)
    try:
        for target_slug, _target_path, target_name in _PAGES[1:]:
            tab.locator('[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]', has_text=target_name).first.click()
            tab.wait_for_timeout(_SETTLE_MS)
            m = tab.evaluate(_MEASURE)
            assert m["nowSide"] == [f"st-key-shell-side-{target_slug}-isnow"], (target_slug, m["nowSide"])
            assert m["exceptions"] == 0
    finally:
        context.close()


# ═══════════════════════ 3. 斷點邊界 ═══════════════════════


@pytest.mark.parametrize("width,mobile", [(768, True), (769, False)])
def test_斷點邊界_768含是手機_769是桌機(browser_page, width, mobile):
    browser, base = browser_page
    context, tab = _open(browser, base, "alo", width)
    try:
        m = tab.evaluate(_MEASURE)
        assert (m["bnDisplay"] == "block") is mobile, (width, m["bnDisplay"])
        assert m["exceptions"] == 0
        assert m["docSW"] <= m["docCW"]
    finally:
        context.close()
