# -*- coding: utf-8 -*-
"""UI-B 線框的量測與截圖（可重現；只讀 HTML、只寫截圖與 stdout）。

用法（repo 根目錄；需要 playwright 與 Pillow）::

    UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome \\
        python docs/evidence/ui_b_settings_health_wireframe_2026_11_20/measure.py

量測對象：視窗 390 與 1280、DPR 1；情境 A／B／C 各量一次（只算「目前可見」的元素，隱藏的情境不計）；
另量「全部 <details> 展開」後的溢出。截圖＝文件頭＋App 框（預設情境 B），存成 128 色 PNG（為了 < 400KB）。
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE.parents[1] / "design" / "ui_b_settings_data_health_wireframe_2026_11_20.html"
EXE = os.environ.get("UI_V2_CHROMIUM") or None

JS = """
() => {
  const de = document.documentElement;
  const shown = el => { for (let a = el; a; a = a.parentElement) { if (getComputedStyle(a).display === 'none') return false; } return true; };
  const o = {scrollWidth: de.scrollWidth, clientWidth: de.clientWidth, fullHeight: de.scrollHeight};
  let min = 1e9, small = 0; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const t = w.currentNode; if (!t.textContent.trim()) continue;
    const el = t.parentElement; if (!shown(el)) continue;
    const d = el.closest('details'); if (d && !d.open && !el.closest('summary')) continue;
    const fs = parseFloat(getComputedStyle(el).fontSize); min = Math.min(min, fs); if (fs < 13) small++;
  }
  o.minFontPx = min; o.textNodesUnder13px = small;
  const t = [...document.querySelectorAll('summary, .sc-bar label, .topnav .tn, .side .sn, .entry')].filter(shown);
  o.touchTargets = t.length; o.touchMinHeightPx = Math.min(...t.map(e => e.getBoundingClientRect().height));
  o.touchUnder48 = t.filter(e => e.getBoundingClientRect().height < 48).length;
  const dt = [...document.querySelectorAll('details')].filter(shown);
  o.detailsVisible = dt.length; o.detailsOpenVisible = dt.filter(d => d.open).length;
  const ch = [...document.querySelectorAll('.chip')].filter(shown);
  o.chipsVisible = ch.length; o.chipsWithoutText = ch.filter(c => !c.textContent.trim()).length;
  o.overflowElements = [...document.querySelectorAll('body *')].filter(e => shown(e) && e.getBoundingClientRect().width
    && e.getBoundingClientRect().right > de.clientWidth + 1).length;
  const vis = s => { const e = document.querySelector(s); return e ? getComputedStyle(e).display : null; };
  o.sideDisplay = vis('.side'); o.topnavDisplay = vis('.topnav');
  return o;
}
"""


def main():
    from PIL import Image
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=EXE, args=["--no-sandbox"])
        for width in (390, 1280):
            page = browser.new_context(viewport={"width": width, "height": 900}, device_scale_factor=1).new_page()
            page.goto("file://" + str(HTML))
            page.wait_for_timeout(300)
            default = page.evaluate("document.querySelector('input.sc-radio:checked').id")
            print(f"== viewport {width} (default scenario radio: {default})")
            for sc in ("a", "b", "c"):
                page.evaluate(f"document.getElementById('sc-{sc}').checked = true")
                page.wait_for_timeout(100)
                print(f"scenario {sc}:", page.evaluate(JS))
            page.evaluate("document.getElementById('sc-b').checked = true")
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            page.wait_for_timeout(100)
            print("scenario b, all <details> open:", page.evaluate(JS))
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = false)")
            box = page.query_selector(".stage").bounding_box()
            height = int(box["y"] + box["height"] + 16)
            raw = HERE / f"_raw_{width}.png"
            page.screenshot(path=str(raw), clip={"x": 0, "y": 0, "width": width, "height": height}, full_page=True)
            out = HERE / f"shot_{width}.png"
            Image.open(raw).convert("RGB").quantize(colors=128, method=Image.MEDIANCUT, dither=Image.Dither.NONE).save(
                out, optimize=True)
            raw.unlink()
            print(f"screenshot {out.name}: {width}x{height}px, {out.stat().st_size} bytes")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
