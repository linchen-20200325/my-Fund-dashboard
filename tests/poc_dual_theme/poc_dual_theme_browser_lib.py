# -*- coding: utf-8 -*-
"""PoC 瀏覽器測試共用：起 PoC、開頁、切模式、量測 computed style、由量測結果導出對比度配對。

- 起 streamlit 與找 Chromium 一律用 `tests/ui_v2/_ui_v2_chromium.py`（唯讀沿用；CI 找不到瀏覽器要 fail、本機 skip）。
- 對比度配對**不寫死色碼**：全部由瀏覽器 computed style 導出（文字節點的 color／fill、各層祖先 background 與 opacity），
  再由 `poc_dual_theme_contrast_lib` 以 alpha 合成後計算。
"""
from __future__ import annotations

import pathlib
import sys

_HERE = pathlib.Path(__file__).resolve().parent
ROOT = _HERE.parents[1]
POC_DIR = ROOT / "poc" / "dual_theme_isolated"
APP = POC_DIR / "app_poc.py"
sys.path.insert(0, str(ROOT / "tests" / "ui_v2"))

import poc_dual_theme_contrast_lib as cl  # noqa: E402

WIDTHS = (390, 768, 1280)
MODES = ("light", "dark")
LABEL = {"light": "☀️ 淺色", "dark": "🌙 深色"}

# 沿著祖先收集 (backgroundColor, 累計 opacity)；累計 opacity＝該層與其所有祖先 opacity 的乘積。
_JS_COMMON = """
const chainOf = (el) => {
  const els = []; for (let e = el; e; e = e.parentElement) els.push(e);
  const cum = new Array(els.length); let o = 1;
  for (let i = els.length - 1; i >= 0; i--) { o *= parseFloat(getComputedStyle(els[i]).opacity); cum[i] = o; }
  return els.map((e, i) => [getComputedStyle(e).backgroundColor, cum[i]]);
};
const opacityOf = (el) => { let o = 1; for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
const area = (el) => { const r = el.getBoundingClientRect(); return [r.width, r.height]; };
"""

# 所有「看得見」的文字節點：顏色（HTML 用 color，SVG 用 fill）＋底色鏈＋字級／字重。
JS_TEXTS = "() => {" + _JS_COMMON + """
const out = []; const skip = new Set(['STYLE','SCRIPT','TITLE','DESC','NOSCRIPT']);
const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
let n; while ((n = w.nextNode())) {
  const t = n.nodeValue.replace(/\\s+/g, ' ').trim(); if (!t) continue;
  const el = n.parentElement; if (!el || skip.has(el.tagName.toUpperCase())) continue;
  const cs = getComputedStyle(el); const [aw, ah] = area(el);
  if (cs.display === 'none' || cs.visibility === 'hidden' || aw < 2 || ah < 2) continue;
  const isSvg = el instanceof SVGElement;
  let region = 'other'; if (el.closest('[data-testid="stSidebar"]')) region = 'sidebar'; else if (el.closest('[data-testid="stHeader"]')) region = 'header';
  else if (el.closest('[data-testid="stMain"]')) region = 'main';
  out.push({text: t.slice(0, 40), tag: el.tagName.toLowerCase(), region, svg: isSvg, color: isSvg ? cs.fill : cs.color,
            size: parseFloat(cs.fontSize), weight: parseInt(cs.fontWeight, 10) || 400, opacity: opacityOf(el),
            bg: chainOf(el), testid: (el.closest('[data-testid]') || {getAttribute: () => ''}).getAttribute('data-testid') || '',
            disabled: !!el.closest('[disabled],[data-disabled="true"],[aria-disabled="true"]')});
}
return out; }"""

# 指定選擇器的第一個元素：邊框色／寬、自身底色鏈、父層底色鏈（＝緊鄰的外側底色）。
JS_BOX = "(sel) => {" + _JS_COMMON + """
const el = document.querySelector(sel); if (!el) return null;
const cs = getComputedStyle(el); const par = el.parentElement;
return {border: cs.borderTopColor, borderWidth: parseFloat(cs.borderTopWidth), outline: cs.outlineColor, outlineWidth: parseFloat(cs.outlineWidth),
        outlineStyle: cs.outlineStyle, color: cs.color, fill: cs.fill, stroke: cs.stroke, strokeWidth: cs.strokeWidth,
        bg: chainOf(el), parentBg: par ? chainOf(par) : [], opacity: opacityOf(el), cursor: cs.cursor,
        boxShadow: cs.boxShadow};
}"""

# 版面：頁級水平溢位、各關鍵元素寬度、圖寬。
JS_LAYOUT = """() => {
const de = document.documentElement; const q = (s) => document.querySelector(s);
const wd = (s) => { const e = q(s); return e ? e.getBoundingClientRect().width : null; };
const mainEl = q('[data-testid="stMain"]'); const viewEl = q('[data-testid="stAppViewContainer"]');
return {scrollW: de.scrollWidth, clientW: de.clientWidth, bodyScrollW: document.body.scrollWidth, svgW: wd('svg.poc-chart'),
        mainScrollW: mainEl ? mainEl.scrollWidth : 0, mainClientW: mainEl ? mainEl.clientWidth : 0,
        viewScrollW: viewEl ? viewEl.scrollWidth : 0, viewClientW: viewEl ? viewEl.clientWidth : 0,
        cardW: wd('.st-key-poc-card-chart'), mode: (q('style[data-poc-theme]') || {getAttribute: () => null}).getAttribute('data-poc-theme'),
        bodyText: document.body.innerText};
}"""


def open_page(browser, base: str, width: int, *, hover: bool = True):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 900}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    page.goto(f"{base}/", wait_until="networkidle")
    page.wait_for_selector('[data-field="mode_state"]', timeout=60000)
    page.wait_for_timeout(1200)
    return ctx, page


def mode_of(page):
    return page.evaluate("() => (document.querySelector('style[data-poc-theme]')||{getAttribute:()=>null}).getAttribute('data-poc-theme')")


def switch_mode(page, mode: str):
    """用滑鼠點切換 radio 的選項；等到頁面真的換成該模式才回傳。"""
    page.get_by_text(LABEL[mode], exact=False).first.click()
    page.wait_for_function(f"() => (document.querySelector('style[data-poc-theme]')||{{getAttribute:()=>null}}).getAttribute('data-poc-theme') === '{mode}'", timeout=15000)
    page.wait_for_timeout(500)


def text_pairs(page):
    """每個可見文字節點 → (描述, 對比值, 門檻, 區域)。"""
    rows = []
    for t in page.evaluate(JS_TEXTS):
        bg = cl.effective_background([(c, o) for c, o in t["bg"]])
        r = cl.text_ratio(t["color"], bg, t["opacity"])
        rows.append({"text": t["text"], "region": t["region"], "tag": t["tag"], "testid": t["testid"], "size": t["size"], "weight": t["weight"],
                     "disabled": t["disabled"], "svg": t["svg"], "ratio": round(r, 2), "need": cl.required_text_ratio(t["size"], t["weight"]),
                     "fg": t["color"], "bg": "rgb(%d,%d,%d)" % tuple(round(x) for x in bg)})
    return rows


def box_pair(page, sel: str, *, prop: str = "border"):
    """元素的邊界色（border／outline／stroke／fill）對其緊鄰外側底色的對比；沒有該元素回 None。"""
    b = page.evaluate(JS_BOX, sel)
    if b is None:
        return None
    outer = cl.effective_background([(c, o) for c, o in b["parentBg"]])
    own = cl.effective_background([(c, o) for c, o in b["bg"]])
    col = {"border": b["border"], "outline": b["outline"], "stroke": b["stroke"], "fill": b["fill"], "bg": None}[prop] if prop != "bg" else None
    if prop == "bg":
        r = cl.ratio(own, outer)
        fg = "rgb(%d,%d,%d)" % tuple(round(x) for x in own)
    else:
        fgc = cl.parse_color(col)
        r = cl.ratio(cl.composite(fgc, outer), outer)
        fg = col
    return {"sel": sel, "prop": prop, "ratio": round(r, 2), "fg": fg, "outer": "rgb(%d,%d,%d)" % tuple(round(x) for x in outer),
            "width": b["borderWidth"] if prop == "border" else b["outlineWidth"] if prop == "outline" else b["strokeWidth"], "raw": b}


# ───────────────────────── 對比度蒐集（多狀態） ─────────────────────────

_RADIO = '.st-key-poc-card-chart label[data-testid="stRadioOption"]'
_IND = " > div > div > div:first-child"
# (名稱, 選擇器, 屬性, 是否「功能性邊界」：功能性者要求 ≥3:1，其餘只報告)
BOUNDARIES = (
    ("radio 未選圓環", f'{_RADIO}:not([data-selected="true"]){_IND}', "bg", True),
    ("radio 選取圓點", f'{_RADIO}[data-selected="true"]{_IND}', "bg", True),
    ("expander 邊框", '[data-testid="stExpander"] details', "border", True),
    ("button 邊框", '.st-key-poc-card-disabled [data-testid="stBaseButton-secondary"]:not(:disabled)', "border", True),
    ("圖 甲 線", "svg.poc-chart path.poc-line:not(.poc-dash)", "stroke", True),
    ("圖 乙 虛線", "svg.poc-chart path.poc-dash", "stroke", True),
    ("圖 座標軸", "svg.poc-chart line.poc-axis", "stroke", True),
    ("卡片邊框", ".st-key-poc-card-chart", "border", False),
    ("chip 邊框 neutral", '.poc-chip[data-status-key="attention"]', "border", False),
    ("chip 邊框 grey", '.poc-chip[data-status-key="missing"]', "border", False),
    ("chip 邊框 red", '.poc-chip[data-status-key="failed"]', "border", False),
    ("chip 邊框 yellow", '.poc-chip[data-status-key="stale"]', "border", False),
    ("disabled button 邊框", ".st-key-poc-card-disabled [data-testid=\"stBaseButton-secondary\"]:disabled", "border", False),
)


def ensure_sidebar_open(page) -> bool:
    """窄螢幕側欄預設收合：點原生展開鈕。回傳側欄目前是否可見。"""
    vis = lambda: page.evaluate("() => { const s = document.querySelector('[data-testid=\"stSidebar\"]'); if (!s) return false; const r = s.getBoundingClientRect(); return r.width > 50 && r.right > 0; }")  # noqa: E731
    if vis():
        return True
    for sel in ('[data-testid="stExpandSidebarButton"]', '[data-testid="stSidebarCollapsedControl"] button', '[data-testid="stSidebarCollapsedControl"]'):
        if page.locator(sel).count():
            page.locator(sel).first.click()
            page.wait_for_timeout(700)
            break
    return vis()


def collect_contrast(page):
    """目前頁面（已在某模式）→ {"texts": [...], "boundaries": [...]}；跨多個互動狀態蒐集。"""
    texts, seen = [], set()

    def grab(state):
        for r in text_pairs(page):
            k = (r["text"], r["fg"], r["bg"], r["region"])
            if k in seen:
                continue
            seen.add(k)
            r["state"] = state
            texts.append(r)

    page.set_viewport_size({"width": page.viewport_size["width"], "height": 2400})
    page.wait_for_timeout(300)
    sidebar_default = page.evaluate("() => { const s = document.querySelector('[data-testid=\"stSidebar\"]'); if (!s) return false; const r = s.getBoundingClientRect(); return r.width > 50 && r.right > 0; }")
    grab("idle")
    page.locator('[data-testid="stExpander"] summary').first.click()
    page.wait_for_timeout(400)
    grab("expander 展開（hover）")
    page.mouse.move(2, 2)
    page.evaluate("() => document.activeElement && document.activeElement.blur()")
    page.wait_for_timeout(500)
    grab("expander 展開（靜止）")  # 曾漏量：未 hover、未 focus 的展開 header（QA 抓到）
    page.locator('[data-testid="stExpander"] summary').first.click()
    page.hover(f'{_RADIO}:not([data-selected="true"])')
    page.wait_for_timeout(300)
    grab("radio hover")
    page.mouse.move(2, 2)
    page.focus('.st-key-poc-card-chart input[type=radio][tabindex="0"]')
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    page.wait_for_timeout(300)
    grab("radio 鍵盤 focus")
    b = box_pair(page, '.st-key-poc-card-chart label[data-focus-visible="true"]', prop="outline")
    boundaries = []
    if b:
        b["name"], b["functional"], b["state"] = "radio 鍵盤 focus 外框", True, "focus"
        boundaries.append(b)
    page.mouse.move(2, 2)
    btn = '.st-key-poc-card-disabled [data-testid="stBaseButton-secondary"]:not(:disabled)'
    page.focus(btn)
    page.keyboard.press("Shift+Tab")
    page.keyboard.press("Tab")
    page.wait_for_timeout(300)
    b = box_pair(page, btn, prop="outline")
    if b:
        b["name"], b["functional"], b["state"] = "button 鍵盤 focus 外框", True, "focus"
        boundaries.append(b)
    page.hover(btn)
    page.wait_for_timeout(300)
    grab("button hover")
    page.mouse.move(2, 2)
    page.click('[data-testid="stMainMenuButton"]')
    page.wait_for_timeout(600)
    grab("主選單 popover 開啟")
    page.keyboard.press("Escape")
    page.mouse.click(600, 600)
    page.wait_for_timeout(300)
    for name, sel, prop, functional in BOUNDARIES:
        b = box_pair(page, sel, prop=prop)
        if b is None:
            continue
        b["name"], b["functional"], b["state"] = name, functional, "idle"
        boundaries.append(b)
    # 側欄：寬螢幕預設展開（idle 已蒐到）；窄螢幕預設收合（原生展開鈕點開後是覆蓋層，最後才蒐，避免擋住主區）
    sidebar = sidebar_default or ensure_sidebar_open(page)
    grab("側欄")
    for b in boundaries:
        b.pop("raw", None)
    return {"texts": texts, "boundaries": boundaries, "sidebar_visible": sidebar}
