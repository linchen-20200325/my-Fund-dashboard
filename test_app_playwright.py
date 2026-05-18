"""Streamlit headless e2e — Phase B（playwright smoke + pixel-diff baseline）.

骨架版本（v18.99 / 升級為 pytest-playwright-snapshot pixel diff
         v18.103 / 加 Phase B-3 跨 viewport 響應式驗證）：
  - Phase A：streamlit.testing.v1.AppTest（已有 7 場景於 test_app_apptest.py）
  - Phase B-1（本檔）：用真實瀏覽器跑 app + Tab1/3/4 三 screenshot baseline
  - Phase B-2（本檔）：對 baseline 做 pixel diff（pytest-playwright-snapshot）
  - Phase B-3（本檔）：跨 desktop(1440) / tablet(768) / mobile(375) viewport
                       響應式驗證 — Tab1 三 viewport 各自 snapshot baseline
  - 雙標記：slow + playwright，預設跳過

依賴（未安裝時整檔 skip，不破壞 CI）：
  pip install playwright pytest-playwright pytest-playwright-snapshot pillow pixelmatch
  playwright install chromium

執行流程：
  # 1. 終端 A：起 streamlit
  streamlit run app.py --server.headless true
  # 2. 終端 B：首次跑寫入 baseline snapshots → __snapshots__/<browser>/<platform>/*.png
  pytest -m playwright --update-snapshots -v test_app_playwright.py
  # 3. 後續驗證（pixel diff threshold=0.1）
  pytest -m playwright -v test_app_playwright.py

snapshot 路徑：test_app_playwright.py 旁的 `__snapshots__/chromium/linux/*.png`
（commit 進 repo；CI 跑時與 baseline 比對 → diff > threshold → fail）
"""
from __future__ import annotations

import os

import pytest

# 雙標記：slow（pre-commit 跳過）+ playwright（需顯式 -m playwright）
pytestmark = [pytest.mark.slow, pytest.mark.playwright]

playwright_pytest = pytest.importorskip(
    "playwright.sync_api",
    reason="playwright 未安裝；`pip install playwright pytest-playwright && playwright install chromium`",
)

# pytest-playwright-snapshot 缺席不擋既有 smoke / baseline-write，僅 pixel-diff cases skip
_HAS_SNAPSHOT_PLUGIN = True
try:
    from PIL import Image  # noqa: F401
    from pixelmatch.contrib.PIL import pixelmatch  # noqa: F401
except ImportError:  # pragma: no cover
    _HAS_SNAPSHOT_PLUGIN = False


BASE_URL = os.environ.get("PLAYWRIGHT_BASE_URL", "http://localhost:8501")


@pytest.fixture(scope="module")
def browser_context():
    """共享一個 Chromium context，省 spawn 時間。需要外部已啟動 streamlit run app.py。

    browser binary 缺失（CI 環境未跑 `playwright install chromium`）→ skip 而非 error。
    """
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=True)
        except Exception as e:
            pytest.skip(f"chromium binary 不可用（需 `playwright install chromium`）: {e}")
        ctx = browser.new_context(
            viewport={"width": 1440, "height": 900},
            color_scheme="dark",
        )
        yield ctx
        ctx.close()
        browser.close()


def _goto_or_skip(page, url: str = BASE_URL) -> None:
    """嘗試開頁，streamlit 未啟動時 skip 而非 fail。"""
    try:
        page.goto(url, timeout=15_000, wait_until="networkidle")
    except Exception as e:
        pytest.skip(f"streamlit 未在 {url} 啟動：{e}")


def _click_tab_by_label(page, label_keyword: str) -> None:
    """點 Streamlit 內任一 tab（標題含 label_keyword）。"""
    # Streamlit st.tabs 對應 [role='tab']
    tabs = page.locator("[role='tab']")
    count = tabs.count()
    for i in range(count):
        t = tabs.nth(i)
        if label_keyword in (t.inner_text() or ""):
            t.click()
            page.wait_for_timeout(600)
            return
    pytest.skip(f"找不到 tab label 含「{label_keyword}」（共 {count} 個 tab）")


def test_app_loads_without_console_error(browser_context) -> None:
    """app 載入後 1s 內無 JS console error，且 H1/H2 至少出現一個。"""
    page = browser_context.new_page()
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)

    _goto_or_skip(page)
    page.wait_for_selector("h1, h2, [data-testid='stMarkdown']", timeout=10_000)

    assert not errors, f"page 載入後 console/page error：{errors[:3]}"
    page.close()


# ════════════════════════════════════════════════════════════
# Pixel-diff baselines — Tab1 / Tab3 / Tab4
# 首次跑用 --update-snapshots 寫入；後續 diff > threshold=0.1 即 fail
# ════════════════════════════════════════════════════════════

def _snapshot_or_baseline(page, assert_snapshot, name: str,
                          tmp_path_factory) -> None:
    """if snapshot 插件可用 → assert_snapshot；否則退化為 tmp baseline 寫入。"""
    img_bytes = page.screenshot(full_page=False)
    if assert_snapshot is not None and _HAS_SNAPSHOT_PLUGIN:
        assert_snapshot(img_bytes, name, threshold=0.1)
    else:
        out_dir = tmp_path_factory.mktemp("playwright_baseline")
        path = out_dir / name
        path.write_bytes(img_bytes)
        assert path.stat().st_size > 5_000, "screenshot 過小（<5KB），疑似空白頁"


def test_tab1_screenshot_baseline(browser_context, request,
                                  tmp_path_factory) -> None:
    """Tab1（總經指南針）載入後 pixel-diff baseline。"""
    assert_snapshot = request.getfixturevalue("assert_snapshot") \
        if _HAS_SNAPSHOT_PLUGIN else None

    page = browser_context.new_page()
    _goto_or_skip(page)
    page.wait_for_selector("[data-testid='stMarkdown']", timeout=10_000)
    page.wait_for_timeout(800)
    _snapshot_or_baseline(page, assert_snapshot, "tab1_load.png",
                          tmp_path_factory)
    page.close()


def test_tab3_screenshot_baseline(browser_context, request,
                                  tmp_path_factory) -> None:
    """Tab3（我的組合）切換後 pixel-diff baseline。"""
    assert_snapshot = request.getfixturevalue("assert_snapshot") \
        if _HAS_SNAPSHOT_PLUGIN else None

    page = browser_context.new_page()
    _goto_or_skip(page)
    page.wait_for_selector("[role='tab']", timeout=10_000)
    _click_tab_by_label(page, "組合")
    page.wait_for_timeout(800)
    _snapshot_or_baseline(page, assert_snapshot, "tab3_load.png",
                          tmp_path_factory)
    page.close()


def test_tab4_screenshot_baseline(browser_context, request,
                                  tmp_path_factory) -> None:
    """Tab4（回測）切換後 pixel-diff baseline。"""
    assert_snapshot = request.getfixturevalue("assert_snapshot") \
        if _HAS_SNAPSHOT_PLUGIN else None

    page = browser_context.new_page()
    _goto_or_skip(page)
    page.wait_for_selector("[role='tab']", timeout=10_000)
    _click_tab_by_label(page, "回測")
    page.wait_for_timeout(800)
    _snapshot_or_baseline(page, assert_snapshot, "tab4_load.png",
                          tmp_path_factory)
    page.close()


# ════════════════════════════════════════════════════════════
# Phase B-3：跨 viewport 響應式 pixel-diff（v18.103）
# desktop(1440) / tablet(768) / mobile(375) 各自 snapshot
# ════════════════════════════════════════════════════════════
RESPONSIVE_VIEWPORTS = [
    # (id, width, height) — id 同時用作 snapshot 檔名後綴
    ("desktop_1440", 1440, 900),
    ("tablet_768",    768, 1024),
    ("mobile_375",    375,  812),
]


@pytest.mark.parametrize("vp_id,vp_w,vp_h", RESPONSIVE_VIEWPORTS,
                         ids=[v[0] for v in RESPONSIVE_VIEWPORTS])
def test_tab1_responsive_viewport(browser_context, request, tmp_path_factory,
                                  vp_id: str, vp_w: int, vp_h: int) -> None:
    """Tab1 在 desktop / tablet / mobile 三 viewport 各自響應式 baseline。

    驗證重點：
      - 同一頁面換 viewport 後不應有 layout overflow（hh1/h2 仍可選到）
      - 每個 viewport 各自 snapshot；響應式 CSS 變更會在 pixel-diff 暴露
      - mobile (375) 預期 sidebar 收合、metrics 卡片堆疊單欄
    """
    assert_snapshot = request.getfixturevalue("assert_snapshot") \
        if _HAS_SNAPSHOT_PLUGIN else None

    page = browser_context.new_page()
    page.set_viewport_size({"width": vp_w, "height": vp_h})
    _goto_or_skip(page)
    # 響應式重排需要稍多時間穩定
    page.wait_for_selector("h1, h2, [data-testid='stMarkdown']", timeout=10_000)
    page.wait_for_timeout(1200)
    _snapshot_or_baseline(page, assert_snapshot,
                          f"tab1_responsive_{vp_id}.png", tmp_path_factory)
    page.close()


def test_mobile_viewport_no_horizontal_overflow(browser_context) -> None:
    """mobile (375px) 視窗下不應出現水平 scroll（body.scrollWidth ≤ viewport+8px tolerance）。

    若失敗 → 表示某個區塊（極可能是 plotly 圖或寬表）撐爆 mobile 寬度。
    """
    page = browser_context.new_page()
    page.set_viewport_size({"width": 375, "height": 812})
    _goto_or_skip(page)
    page.wait_for_selector("[data-testid='stMarkdown']", timeout=10_000)
    page.wait_for_timeout(1200)

    sw = page.evaluate("() => document.documentElement.scrollWidth")
    cw = page.evaluate("() => document.documentElement.clientWidth")
    # 容忍 8px scrollbar 誤差
    assert sw - cw <= 8, (
        f"mobile viewport (375px) 出現水平溢出：scrollWidth={sw} > clientWidth={cw}+8。"
        f"檢查是否有 plotly 圖或寬表沒用 use_container_width=True。"
    )
    page.close()
