# -*- coding: utf-8 -*-
"""BL-0540 Phase 1A：⚙️ 設定→資料健康度 本地 Preview 截圖＋量測（合成 fixture；非 Cloud、非真機、非真資料）。

重現（repo 根目錄；需 streamlit、playwright、Chromium）：
    UI_V2_CHROMIUM=<chromium 路徑> python docs/evidence/ui_b4_settings_health_phase1a_2026_11_21/measure.py
輸出：同夾 `shot_*.png`、`measure.json`。measure.json 會記錄實測當下的 `git rev-parse HEAD` 與工作樹是否乾淨（不事後補填）。
"""
import json
import pathlib
import subprocess
import sys
import tempfile

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "tests" / "ui_v2"))
import _ui_v2_chromium as chrome  # noqa: E402

APP = f"""
import sys
sys.path.insert(0, {str(ROOT)!r}); sys.path.insert(0, {str(ROOT / 'tests' / 'ui_v3')!r})
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
adapter.load = lambda sources: (ms.view(us="error"), ms.table())
from ui_v3 import app_preview
app_preview.main()
"""
ROWS = """() => [...document.querySelectorAll('.uv3-health-row')].map(e => ({key: e.dataset.healthKey, state: e.dataset.healthState,
  reason: e.dataset.reason, asOf: e.dataset.asOf, fetched: e.dataset.fetchedAt}))"""
MEASURE = """() => { const main = document.querySelector('[data-testid="stMain"]');
  const back = [...document.querySelectorAll('[data-testid="stMain"] a[data-testid="stPageLink-NavLink"]')].find(a => a.innerText.includes('市場與趨勢'));
  return {vw: document.documentElement.clientWidth, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth,
          mainClientW: main.clientWidth, backHeight: back ? back.getBoundingClientRect().height : null}; }"""


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main():
    out = {"head": git("rev-parse", "HEAD"), "worktree_clean_before_run": git("status", "--porcelain", "--", ".") == "",
           "fixture": "tests/ui_v3/market_stubs.py 合成資料（view(us='error')）", "scope": "本地 Chromium＋本地 streamlit；非 Cloud、非真機", "runs": []}
    with tempfile.TemporaryDirectory() as tmp:
        app = pathlib.Path(tmp) / "app.py"
        app.write_text(APP, encoding="utf-8")
        api = chrome.import_sync_api()
        with chrome.streamlit_server(app) as base, api.sync_playwright() as p:
            browser = chrome.launch(p)
            for width, nav in ((390, ".st-key-uv3-top-nav"), (1280, '[data-testid="stSidebar"]')):
                ctx = browser.new_context(viewport={"width": width, "height": 900}, locale="zh-TW", has_touch=width <= 768)
                page = ctx.new_page()
                page.goto(base + "/", wait_until="networkidle")
                page.wait_for_selector(".uv3-statusbar", timeout=60000)
                page.locator(f'{nav} a[data-testid="stPageLink-NavLink"][href$="set"]').first.click()
                page.wait_for_selector('[data-health="scope"]', timeout=60000)
                page.wait_for_timeout(800)
                page.screenshot(path=str(HERE / f"shot_{width}_snapshot.png"), full_page=True)
                out["runs"].append({"width": width, "view": "after market (snapshot)", "rows": page.evaluate(ROWS), **page.evaluate(MEASURE)})
                fresh = browser.new_context(viewport={"width": width, "height": 900}, locale="zh-TW", has_touch=width <= 768)
                fp = fresh.new_page()
                fp.goto(base + "/set", wait_until="networkidle")
                fp.wait_for_selector('[data-health="no-snapshot"]', timeout=60000)
                fp.wait_for_timeout(500)
                fp.screenshot(path=str(HERE / f"shot_{width}_no_snapshot.png"), full_page=True)
                out["runs"].append({"width": width, "view": "fresh session (no snapshot)", "rows": fp.evaluate(ROWS), **fp.evaluate(MEASURE)})
                fresh.close()
                ctx.close()
            browser.close()
    (HERE / "measure.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False)[:600])


if __name__ == "__main__":
    main()
