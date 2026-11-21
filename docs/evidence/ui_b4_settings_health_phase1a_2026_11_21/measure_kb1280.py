# -*- coding: utf-8 -*-
"""BL-0540 Phase 1A：與 main（含 #1320 側欄焦點）整合後的 1280px 鍵盤驗收截圖＋量測（合成 fixture；非 Cloud、非真機）。

重現（repo 根；需 streamlit、playwright、Chromium）：
    UI_V2_CHROMIUM=<chromium 路徑> python docs/evidence/ui_b4_settings_health_phase1a_2026_11_21/measure_kb1280.py
輸出：同夾 `kb1280.json`、`shot_kb1280_*.png`。json 記錄實測當下的 `git rev-parse HEAD` 與工作樹是否乾淨。
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
FOCUS = """() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
  return {text: (e.innerText || '').replace(/\\s+/g, ' ').trim(), inSidebar: !!e.closest('[data-testid="stSidebar"]'),
          inMain: !!e.closest('[data-testid="stMain"]'), ariaDisabled: !!e.closest('[aria-disabled="true"]'),
          focusVisible: e.matches(':focus-visible'), outline: s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor}; }"""
DISABLED = """() => [...document.querySelectorAll('[data-testid="stSidebar"] [data-nav]')].map(e => ({nav: e.dataset.nav,
  ariaDisabled: e.getAttribute('aria-disabled'), href: e.getAttribute('href')}))"""
H1 = "() => (document.querySelector('h1') || {}).innerText"


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()


def main():
    out = {"head": git("rev-parse", "HEAD"), "worktree_clean_before_run": git("status", "--porcelain", "--", ".") == "",
           "fixture": "tests/ui_v3/market_stubs.py 合成資料（view(us='error')）", "scope": "本地 Chromium 1280×900＋本地 streamlit；非 Cloud、非真機", "steps": []}
    with tempfile.TemporaryDirectory() as tmp:
        app = pathlib.Path(tmp) / "app.py"
        app.write_text(APP, encoding="utf-8")
        api = chrome.import_sync_api()
        with chrome.streamlit_server(app) as base, api.sync_playwright() as p:
            browser = chrome.launch(p)
            ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="zh-TW")
            page = ctx.new_page()
            page.goto(base + "/", wait_until="networkidle")
            page.wait_for_selector(".uv3-statusbar", timeout=60000)
            out["disabled_entries"] = page.evaluate(DISABLED)
            seen = {}
            for i in range(14):
                page.keyboard.press("Tab")
                f = page.evaluate(FOCUS)
                out["steps"].append({"key": "Tab", "n": i + 1, "focus": f})
                if f and f["inSidebar"] and "市場" in f["text"] and "mkt" not in seen:
                    seen["mkt"] = True
                    page.screenshot(path=str(HERE / "shot_kb1280_focus_market.png"))
                if f and f["inSidebar"] and "設定" in f["text"] and "set" not in seen:
                    seen["set"] = True
                    page.screenshot(path=str(HERE / "shot_kb1280_focus_settings.png"))
            for i in range(6):
                page.keyboard.press("Shift+Tab")
                out["steps"].append({"key": "Shift+Tab", "n": i + 1, "focus": page.evaluate(FOCUS)})
            page.locator('[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"][href$="set"]').first.focus()
            page.keyboard.press("Enter")
            page.wait_for_selector('[data-health="scope"]', timeout=60000)
            page.wait_for_timeout(600)
            out["after_enter_on_settings"] = page.evaluate(H1)
            page.screenshot(path=str(HERE / "shot_kb1280_settings_after_enter.png"))
            page.locator('[data-testid="stMain"] a[data-testid="stPageLink-NavLink"]', has_text="市場與趨勢").first.click()
            page.wait_for_selector(".uv3-statusbar", timeout=60000)
            page.wait_for_timeout(600)
            out["after_back_to_market"] = page.evaluate(H1)
            ctx.close()
            browser.close()
    (HERE / "kb1280.json").write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(out["head"], out["worktree_clean_before_run"], out["after_enter_on_settings"], out["after_back_to_market"])


if __name__ == "__main__":
    main()
