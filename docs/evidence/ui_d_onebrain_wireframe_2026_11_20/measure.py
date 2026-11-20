# -*- coding: utf-8 -*-
"""UI-D 線框的量測與截圖（可重現；只讀 HTML、只寫截圖與 stdout）。

用法（repo 根目錄；需要 playwright 與 Pillow）::

    UI_V2_CHROMIUM=/opt/pw-browsers/chromium-1243/chrome-linux64/chrome \\
        python docs/evidence/ui_d_onebrain_wireframe_2026_11_20/measure.py

量測對象：視窗 390 與 1280、DPR 1。
- 文件溢出：documentElement 的 scrollWidth 與 clientWidth。
- 框內溢出：390 視窗下，桌機框（`.fr.desk`）本來就比視窗寬，改放在自己的橫向捲動容器（`.deskwrap`）內；
  只有在 `.deskwrap` 外的元素才算文件溢出；1280 視窗下桌機框應完全容得下（`deskWrapScrolls` 應為 False）。
- 最小字級：可見文字節點的 computed font-size（未展開的 `<details>` 內容不計）。
- 觸控：`summary`、頁首五格、側欄項、輸入欄、按鈕、pill、入口列、OneBrain slice pill 的高度。
- 手機頁首五格：每個手機框的 `.topnav` 是 5 格、每格高 >= 60px、position 不是 sticky／fixed。
另量「全部 <details> 展開」後的溢出與字級。截圖＝整頁，存成調色盤 PNG（為了單檔 < 400KB）。
"""
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
HTML = HERE.parents[1] / "design" / "onebrain_new_ui2_shared_slice_wireframe_2026_11_20.html"
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
  const sel = 'summary, .tn, .sn, .field, .btn, .pillb, .entry, .slice';
  const vt = [...document.querySelectorAll(sel)].filter(e => shown(e) && e.getBoundingClientRect().height > 0);
  o.touchTargets = vt.length; o.touchMinHeightPx = Math.min(...vt.map(e => e.getBoundingClientRect().height));
  o.touchUnder48 = vt.filter(e => e.getBoundingClientRect().height < 48).length;
  const ch = [...document.querySelectorAll('.chip')].filter(shown);
  o.chipsVisible = ch.length; o.chipsWithoutText = ch.filter(c => !c.textContent.trim()).length;
  o.overflowElementsOutsideDeskWrap = [...document.querySelectorAll('body *')].filter(e => shown(e) && !e.closest('.deskwrap')
    && e.getBoundingClientRect().width && e.getBoundingClientRect().right > de.clientWidth + 1).length;
  const dw = [...document.querySelectorAll('.deskwrap')];
  o.deskWraps = dw.length; o.deskWrapScrolls = dw.filter(x => x.scrollWidth > x.clientWidth + 1).length;
  const mob = [...document.querySelectorAll('.fr.mob')];
  o.mobFrames = mob.length;
  o.mobFrameMaxWidthPx = Math.max(...mob.map(f => f.getBoundingClientRect().width));
  o.mobFramesScrollingInside = mob.filter(f => f.scrollWidth > f.clientWidth + 1).length;
  const tops = mob.map(f => f.querySelector('.topnav'));
  o.mobTopnavCells = tops.map(n => n.querySelectorAll('.tn').length).join(',');
  o.mobTopnavMinCellHeightPx = Math.min(...tops.flatMap(n => [...n.querySelectorAll('.tn')].map(c => c.getBoundingClientRect().height)));
  o.mobTopnavPositions = [...new Set(tops.map(n => getComputedStyle(n).position))].join(',');
  const desk = [...document.querySelectorAll('.fr.desk')];
  o.deskFrames = desk.length;
  o.deskTopnavHidden = desk.every(f => getComputedStyle(f.querySelector('.topnav')).display === 'none');
  o.mobSideHidden = mob.every(f => getComputedStyle(f.querySelector('.side')).display === 'none');
  o.obSlotsClosedByDefault = [...document.querySelectorAll('details.ob')].every(d => !d.open);
  o.obSlots = document.querySelectorAll('details.ob').length;
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
            print(f"== viewport {width}")
            print("default (all <details> closed):", page.evaluate(JS))
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = true)")
            page.wait_for_timeout(100)
            print("all <details> open:", page.evaluate(JS))
            page.evaluate("document.querySelectorAll('details').forEach(d => d.open = false)")
            raw = HERE / f"_raw_{width}.png"
            page.screenshot(path=str(raw), full_page=True)
            out = HERE / f"shot_{width}.png"
            im = Image.open(raw).convert("RGB")
            colors = 64
            while True:
                im.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.Dither.NONE).save(out, optimize=True)
                if out.stat().st_size < 400_000 or colors <= 16:
                    break
                colors //= 2
            raw.unlink()
            print(f"screenshot {out.name}: {im.width}x{im.height}px, {colors} colors, {out.stat().st_size} bytes")
        browser.close()


if __name__ == "__main__":
    sys.exit(main())
