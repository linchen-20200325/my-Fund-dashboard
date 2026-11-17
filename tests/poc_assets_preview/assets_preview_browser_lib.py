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


# ───────────────────────── A50（單一 `<details>` 容器）量測 ─────────────────────────

A50_JS = r"""
() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const d = document.querySelector('details[data-block="a50"]');
  if (!d) return null;
  const s = d.querySelector(':scope > summary'), body = d.querySelector('[data-a50="body"]');
  const sr = s.getBoundingClientRect();
  const hit = document.elementFromPoint(Math.min(Math.max(sr.x + sr.width / 2, 0), vw - 1), Math.min(Math.max(sr.y + sr.height / 2, 0), vh - 1));
  const rows = [...d.querySelectorAll('.uv3-a50-row')];
  const br = body.getBoundingClientRect();
  return {vw, vh, open: d.open, detailsTotal: document.querySelectorAll('details').length, nestedInside: d.querySelectorAll('details').length,
          insideAnotherDetails: !!d.parentElement.closest('details'), summaryCount: d.querySelectorAll('summary').length,
          summaryH: sr.height, summaryW: sr.width, summaryCovered: !(hit && (hit === s || s.contains(hit))),
          a60Sibling: !!document.querySelector('details[data-block="a60"]') && !d.contains(document.querySelector('details[data-block="a60"]')),
          rowCount: rows.length, fieldCount: d.querySelectorAll('[data-field]').length,
          bodyClientH: body.clientHeight, bodyScrollH: body.scrollHeight, bodyH: br.height, bodyOverflowY: getComputedStyle(body).overflowY,
          rowsClippedX: rows.filter(r => r.scrollWidth > r.clientWidth + 1).length,
          docScrollW: document.documentElement.scrollWidth,
          detailsRight: d.getBoundingClientRect().right, bodyRight: br.right,
          hasFirstScreenMark: !!d.querySelector('[data-first-screen]'), hasHoldingIdAttr: !![...d.querySelectorAll('*')].find(e => [...e.attributes].some(a => /holding|policy/i.test(a.name + a.value))),
          firstRowName: rows.length ? [...rows[0].querySelector('[data-field="fund_name"]').childNodes].filter(n => n.nodeType === 3).map(n => n.textContent).join('') : null,
          injectedTags: d.querySelectorAll('b, script, i').length};
}
"""

# 把 A50 內容捲到底，回傳最後一列是否完整落在容器可視範圍內（不截斷）。
A50_SCROLL_END_JS = r"""
() => {
  const body = document.querySelector('details[data-block="a50"] [data-a50="body"]');
  body.scrollTop = body.scrollHeight;
  const rows = body.querySelectorAll('.uv3-a50-row'), last = rows[rows.length - 1].getBoundingClientRect(), br = body.getBoundingClientRect();
  return {lastBottom: last.bottom, bodyBottom: br.bottom, lastTop: last.top, bodyTop: br.top, scrollTop: body.scrollTop};
}
"""


def a50_violations(a, *, expect_open, expect_rows):
    """A50 結構與幾何判定（純函式）。a ＝ A50_JS 的量測結果。"""
    bad = []
    if a is None:
        return [("沒有 A50 容器",)]
    if a["detailsTotal"] != 2 or a["summaryCount"] != 1 or not a["a60Sibling"]:
        bad.append(("<details> 不是 A50＋A60 各恰一個（A50 內恰一個 <summary>）", a["detailsTotal"], a["summaryCount"], a["a60Sibling"]))
    if a["nestedInside"] or a["insideAnotherDetails"]:
        bad.append(("A50 巢狀或被放進別的展開容器", a["nestedInside"], a["insideAnotherDetails"]))
    if a["open"] is not expect_open:
        bad.append(("展開狀態不符", a["open"], expect_open))
    if a["rowCount"] != expect_rows or a["fieldCount"] != expect_rows * 4:
        bad.append(("列數或欄數不符", a["rowCount"], a["fieldCount"], expect_rows))
    if a["summaryH"] < 48 or a["summaryCovered"]:
        bad.append(("摘要的觸控目標小於 48px 或被蓋住", a["summaryH"], a["summaryCovered"]))
    if a["docScrollW"] > a["vw"] or a["detailsRight"] > a["vw"] + 0.5:
        bad.append(("A50 造成水平溢出", a["docScrollW"], a["detailsRight"], a["vw"]))
    if a["hasFirstScreenMark"] or a["hasHoldingIdAttr"]:
        bad.append(("A50 內有首屏標記或身份鍵屬性", a["hasFirstScreenMark"], a["hasHoldingIdAttr"]))
    return bad


# ───────────────────────── A60（獨立 `<details>`，A50 之後；DEC-2026-11-17-01） ─────────────────────────

A60_JS = r"""
() => {
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const d = document.querySelector('details[data-block="a60"]');
  if (!d) return null;
  const a50 = document.querySelector('details[data-block="a50"], [data-a50="status-only"]');
  const s = d.querySelector(':scope > summary'), body = d.querySelector('[data-a60="body"]');
  const sr = s.getBoundingClientRect(), br = body.getBoundingClientRect(), dr = d.getBoundingClientRect();
  const hit = document.elementFromPoint(Math.min(Math.max(sr.x + sr.width / 2, 0), vw - 1), Math.min(Math.max(sr.y + sr.height / 2, 0), vh - 1));
  const blocks = [...document.querySelectorAll('[data-block]')].map(e => e.dataset.block);
  return {vw, vh, open: d.open, detailsTotal: document.querySelectorAll('details').length, countA60: document.querySelectorAll('details[data-block="a60"]').length,
          nestedInside: d.querySelectorAll('details').length, insideAnotherDetails: !!d.parentElement.closest('details'),
          summaryCount: d.querySelectorAll('summary').length, summaryH: sr.height, summaryCovered: !(hit && (hit === s || s.contains(hit))),
          docScrollW: document.documentElement.scrollWidth, detailsRight: dr.right, bodyRight: br.right,
          bodyClipped: [...d.querySelectorAll('*')].filter(e => e.scrollWidth > e.clientWidth + 1 && getComputedStyle(e).overflowX === 'visible' && e.getBoundingClientRect().right > vw + 0.5).length,
          hasFirstScreenMark: !!d.querySelector('[data-first-screen]'), lastBlock: blocks[blocks.length - 1], blocks,
          afterA50: !a50 || !!(a50.compareDocumentPosition(d) & Node.DOCUMENT_POSITION_FOLLOWING),
          stateAttr: (d.querySelector('[data-a60="state"]') || {dataset: {}}).dataset.a60State || null,
          countsText: [...d.querySelectorAll('[data-a60="skipped-tabs"], [data-a60="skipped-rows"]')].map(e => e.textContent),
          html: d.outerHTML, text: d.textContent};
}
"""


def a60_violations(a, *, expect_open, expect_total_details):
    """A60 結構與幾何判定（純函式）。a ＝ A60_JS 的量測結果；expect_total_details＝頁面上 `<details>` 總數（有列 2、無列 1）。"""
    bad = []
    if a is None:
        return [("沒有 A60 容器",)]
    if a["countA60"] != 1 or a["detailsTotal"] != expect_total_details or a["summaryCount"] != 1:
        bad.append(("<details> 數量不符（A60 恰一個、A50 有列才有）", a["countA60"], a["detailsTotal"], a["summaryCount"]))
    if a["nestedInside"] or a["insideAnotherDetails"]:
        bad.append(("A60 巢狀或被放進別的展開容器", a["nestedInside"], a["insideAnotherDetails"]))
    if a["open"] is not expect_open:
        bad.append(("展開狀態不符", a["open"], expect_open))
    if a["lastBlock"] != "a60" or not a["afterA50"]:
        bad.append(("A60 不是最後一個區塊或不在 A50 之後", a["blocks"], a["afterA50"]))
    if a["summaryH"] < 48 or a["summaryCovered"]:
        bad.append(("摘要的觸控目標小於 48px 或被蓋住", a["summaryH"], a["summaryCovered"]))
    if a["docScrollW"] > a["vw"] or a["detailsRight"] > a["vw"] + 0.5 or a["bodyClipped"]:
        bad.append(("A60 造成水平溢出", a["docScrollW"], a["detailsRight"], a["vw"], a["bodyClipped"]))
    if a["hasFirstScreenMark"]:
        bad.append(("A60 內有首屏標記",))
    return bad


def leak_violations(html, text, tokens):
    """畫面（DOM 原文與文字）裡出現任一禁止字串（含 escape 後形態）→ 回傳命中的字串。"""
    from html import escape

    return sorted({t for t in tokens if t in html or escape(t) in html or t in text})
