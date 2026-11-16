# -*- coding: utf-8 -*-
"""💼 隔離式 FAKE Preview 的瀏覽器量測與判定函式（純函式＋一段 JS；邏輯參考 ui_v3 市場頁的瀏覽器守衛，最小複製）。

只放「量什麼、怎麼判」，不起 server、不開瀏覽器；測試檔負責起 Streamlit 與 Chromium。
"""
from __future__ import annotations

MEASURE_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const shown = e => { const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return e.getClientRects().length > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0 && b.width > 0 && b.height > 0; };
  const marks = [...document.querySelectorAll('[data-first-screen]')];
  const items = marks.map(e => { const b = e.getBoundingClientRect();
    const hit = document.elementFromPoint(Math.min(Math.max(b.x + b.width / 2, 0), vw - 1), Math.min(Math.max(b.y + b.height / 2, 0), vh - 1));
    return {mark: e.dataset.firstScreen, shown: shown(e), inFold: b.top >= 0 && b.bottom <= vh && b.left >= -0.5 && b.right <= vw + 0.5,
            covered: !(hit && (hit === e || e.contains(hit))), top: b.top, bottom: b.bottom, left: b.left, right: b.right}; });
  const body = [...main.querySelectorAll('[data-block], [data-block] *, [data-harness]')].filter(shown);
  return {vw, vh, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth,
          domCount: marks.length, items, chips: document.querySelectorAll('.uv3-chip').length,
          harnessMarks: document.querySelectorAll('[data-harness] [data-first-screen], [data-harness][data-first-screen]').length,
          blocks: [...document.querySelectorAll('[data-block]')].map(e => e.dataset.block),
          overflowing: body.filter(e => e.getBoundingClientRect().right > vw + 0.5).map(e => e.tagName + '.' + (e.className || '')).slice(0, 5),
          state: (document.querySelector('[data-source-state]') || {dataset: {}}).dataset.sourceState || null,
          hasBanner: !!document.querySelector('[data-harness="true"]')};
}
"""


def overflow_violations(m):
    bad = []
    if m["docScrollW"] > m["vw"]:
        bad.append(("整頁橫向溢出", m["docScrollW"], m["vw"]))
    if m["mainScrollW"] > m["mainClientW"]:
        bad.append(("主內容橫向溢出", m["mainScrollW"], m["mainClientW"]))
    if m["overflowing"]:
        bad.append(("頁本體元素超出視窗右緣", m["overflowing"]))
    return bad


def visible_in_fold(m):
    return [i for i in m["items"] if i["shown"] and i["inFold"] and not i["covered"]]


def first_screen_violations(m, expected_count):
    """DOM 標記數必須等於模型點數；fold 內「可見」的標記數必須等於 DOM 標記數（隱藏／被蓋住／在 fold 外都算不可見）；不得有額外 chip。"""
    bad = []
    if m["domCount"] != expected_count:
        bad.append(("DOM 首屏標記數不等於模型點數", m["domCount"], expected_count))
    visible = visible_in_fold(m)
    if len(visible) != m["domCount"]:
        bad.append(("fold 內可見的首屏標記數少於 DOM 標記數", len(visible), m["domCount"],
                    [i["mark"] for i in m["items"] if i not in visible]))
    if m["chips"]:
        bad.append(("頁面出現 chip 形式元素", m["chips"]))
    if m["harnessMarks"]:
        bad.append(("harness 區內出現首屏標記", m["harnessMarks"]))
    if m["blocks"][:3] != ["a00", "a10", "a20"]:
        bad.append(("區塊順序不是 a00→a10→a20", m["blocks"]))
    return bad
