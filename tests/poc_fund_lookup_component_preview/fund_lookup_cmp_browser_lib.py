# -*- coding: utf-8 -*-
"""單檔基金查詢呈現元件 隔離式 FAKE Preview 的瀏覽器量測與判定函式（純函式＋兩段 JS）。

只放「量什麼、怎麼判」，不起 server、不開瀏覽器；測試檔負責起 Streamlit 與 Chromium。
對比量測依 WCAG 2.x 相對亮度；全部讀 computed style，不寫死色碼。
"""
from __future__ import annotations

from urllib.parse import urlsplit

MIN_TARGET = 48                # 觸控目標下限（沿既有 fund_search／nas_diag 規格 48px；任務要求 ≥44）
MIN_TEXT_CONTRAST = 4.5
MIN_NONTEXT_CONTRAST = 3.0

MEASURE_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth;
  const shown = e => { const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return e.getClientRects().length > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0 && b.width > 0 && b.height > 0; };
  const top = sel => { const e = main.querySelector(sel); return e && shown(e) ? e.getBoundingClientRect().top + window.scrollY : null; };
  const targetsOf = (sel, kind) => [...main.querySelectorAll(sel)].filter(shown).map(e => { const b = e.getBoundingClientRect(); return {kind, h: b.height, w: b.width, right: b.right}; });
  const targets = [].concat(targetsOf('[data-testid="stTextInputRootElement"]', 'input'), targetsOf('[data-testid="stTextInputRootElement"] input', 'input-el'),
    targetsOf('[data-testid="stFormSubmitButton"] button', 'button'));
  const sel = document.querySelector('[data-testid="stSelectbox"] [role="combobox"], [data-testid="stSelectbox"] input');
  const selBox = sel ? (sel.closest('[data-baseweb="select"]') || sel).getBoundingClientRect() : null;
  const card = main.querySelector('[data-block="lookup-result"], [data-block="lookup-idle"]');
  const rendererEls = [...main.querySelectorAll('[data-block], [data-block] *')].filter(shown);
  const cardEls = card ? [card, ...card.querySelectorAll('*')] : [];
  const rows = card ? [...card.querySelectorAll('[data-row]')].filter(e => e.dataset.row !== 'status' && e.dataset.row !== 'idle') : [];
  const status = card ? card.querySelector('[data-row="status"], [data-row="idle"]') : null;
  const live = card ? card.querySelector('[data-live]') : null;
  const extras = card ? [...card.querySelectorAll('[data-note="extra"]')] : [];
  const labelledBy = card ? card.getAttribute('aria-labelledby') : null;
  const seq = {title: top('h1'), input: top('[data-testid="stTextInput"]'), isin: top('[data-block="isin-note"]'), button: top('[data-testid="stFormSubmitButton"]'),
    card: top('[data-block="lookup-result"], [data-block="lookup-idle"]')};
  const tag = card ? card.querySelector('[data-tag="fake"]') : null;
  const firstRow = rows[0];
  return {vw, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth, targets, selectH: selBox ? selBox.height : null, seq,
    state: card ? (card.dataset.state || null) : null, reason: card ? (card.dataset.reason || null) : null, block: card ? card.dataset.block : null,
    cardText: card ? card.innerText : null, text: main.innerText,
    rowNames: rows.map(e => e.dataset.row), rowStatus: rows.map(e => e.dataset.fieldStatus || null),
    labels: [...(card ? card.querySelectorAll('dt') : [])].map(e => e.innerText.trim()),
    cardRole: card ? card.getAttribute('role') : null, labelledBy, labelTargetOk: !!(labelledBy && document.getElementById(labelledBy) && card.contains(document.getElementById(labelledBy))),
    statusRole: live ? live.getAttribute('role') : (status ? status.getAttribute('role') : null),
    extrasTotal: extras.length, extrasInLive: live ? extras.filter(e => live.contains(e)).length : 0, statusInLive: !!(live && status && live.contains(status)), statusText: status ? status.innerText.trim() : null,
    dlCount: card ? card.querySelectorAll('dl').length : 0, dtCount: card ? card.querySelectorAll('dt').length : 0, ddCount: card ? card.querySelectorAll('dd').length : 0,
    fakeTags: card ? card.querySelectorAll('[data-tag="fake"]').length : 0,
    tagBeforeRows: !!(tag && (!firstRow || (tag.compareDocumentPosition(firstRow) & Node.DOCUMENT_POSITION_FOLLOWING))),
    tagBeforeStatus: !!(tag && status && (tag.compareDocumentPosition(status) & Node.DOCUMENT_POSITION_FOLLOWING)),
    interactiveInCard: cardEls.filter(e => e.matches('button, a, input, select, textarea, summary, details, [tabindex], [onclick], [href]')).length,
    mainLinks: main.querySelectorAll('a[href]').length, scripts: main.querySelectorAll('script').length, imgs: main.querySelectorAll('img').length,
    bold: [...main.querySelectorAll('b, strong')].filter(e => e.closest('[data-block]') && !e.closest('.fl-status')).length,
    pendingKeys: [...main.querySelectorAll('[data-block] [data-pending-wording]')].map(e => e.dataset.pendingWording),
    overflowing: rendererEls.filter(e => e.getBoundingClientRect().right > vw + 0.5).map(e => e.tagName + '.' + (e.className || '')).slice(0, 5),
    inputValue: (main.querySelector('[data-testid="stTextInput"] input') || {}).value ?? null};
}
"""


def overflow_violations(m):
    bad = []
    if m["docScrollW"] > m["vw"]:
        bad.append(("整頁橫向溢出", m["docScrollW"], m["vw"]))
    if m["mainScrollW"] > m["mainClientW"]:
        bad.append(("主內容橫向溢出", m["mainScrollW"], m["mainClientW"]))
    if m["overflowing"]:
        bad.append(("元件元素超出視窗右緣", m["overflowing"]))
    return bad


def touch_target_violations(m):
    """可見控制項（輸入框、輸入元素、查詢鈕）高與寬皆須 ≥48px；harness 的 selectbox 不在此列（據實另量）。"""
    kinds = {t["kind"] for t in m["targets"]}
    bad = [("找不到控制項", need) for need in ("input", "input-el", "button") if need not in kinds]
    for t in m["targets"]:
        if t["h"] < MIN_TARGET - 0.5 or t["w"] < MIN_TARGET - 0.5:
            bad.append(("觸控目標不足 48px", t))
        if t["right"] > m["vw"] + 0.5:
            bad.append(("控制項超出視窗", t))
    return bad


def order_violations(m):
    """首屏順序：標題 → 輸入框 → ISIN 說明 → 查詢鈕 → 結果卡。"""
    s = m["seq"]
    names = ["title", "input", "isin", "button", "card"]
    missing = [n for n in names if s[n] is None]
    if missing:
        return [("找不到區塊", missing)]
    values = [s[n] for n in names]
    return [] if values == sorted(values) and len(set(values)) == len(values) else [("順序不對", dict(zip(names, values)))]


def static_violations(m):
    bad = []
    if m["mainLinks"]:
        bad.append(("主區出現連結", m["mainLinks"]))
    if m["scripts"] or m["imgs"] or m["bold"]:
        bad.append(("使用者輸入被當成標籤執行／渲染", m["scripts"], m["imgs"], m["bold"]))
    if m["interactiveInCard"]:
        bad.append(("結果卡內有可互動元素（不得有假按鈕或連結）", m["interactiveInCard"]))
    for w in ("基金不存在", "查無基金", "查無此", "不存在", "已確認", "推薦", "最佳", "排名", "NAV", "淨值", "報酬", "績效", "幣別", "取得時間", "供應者"):
        if w in m["text"]:
            bad.append(("出現禁用字樣", w))
    return bad


def a11y_violations(m, *, expect_alert):
    """語意：卡片是 region 且 aria-labelledby 指向卡內的狀態列；狀態列有 status／alert 角色；非 idle 的卡以 `dl/dt/dd` 呈現欄位。"""
    bad = []
    if m["cardRole"] != "region" or not m["labelTargetOk"]:
        bad.append(("卡片不是 region 或 aria-labelledby 沒有指到卡內元素", m["cardRole"], m["labelledBy"]))
    want = "alert" if expect_alert else "status"
    if m["statusRole"] != want:
        bad.append(("狀態列角色不對", m["statusRole"], want))
    if m["extrasTotal"] != m["extrasInLive"] or (m["extrasTotal"] and not m["statusInLive"]):
        bad.append(("可操作原因句不在狀態列所在的 live region 內", m["extrasTotal"], m["extrasInLive"], m["statusInLive"]))
    if not m["statusText"]:
        bad.append(("狀態列沒有文字（狀態不得只靠顏色）",))
    if m["rowNames"] and not (m["dlCount"] == 1 and m["dtCount"] == m["ddCount"] == len(m["rowNames"])):
        bad.append(("欄位沒有以 dl/dt/dd 呈現", m["dlCount"], m["dtCount"], m["ddCount"], m["rowNames"]))
    return bad


def card_violations(m, *, fake=True):
    """非 idle 卡：恰好一個 FAKE 標籤且在狀態列與欄位列之前。"""
    bad = []
    if fake:
        if m["fakeTags"] != 1 or not m["tagBeforeRows"] or not m["tagBeforeStatus"]:
            bad.append(("FAKE 標籤不是恰好一個或不在狀態列／欄位列之前", m["fakeTags"], m["tagBeforeRows"], m["tagBeforeStatus"]))
    return bad


def structure_violations(m, *, expect_alert=False, fake=True):
    return (overflow_violations(m) + touch_target_violations(m) + order_violations(m) + static_violations(m)
            + a11y_violations(m, expect_alert=expect_alert) + (card_violations(m, fake=fake) if m["block"] == "lookup-result" else []))


def _origin(url):
    parts = urlsplit(url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    try:
        port = parts.port or {"http": 80, "https": 443}.get(scheme)
    except ValueError:
        port = "invalid"
    return scheme, (parts.hostname or "").lower(), port


def external_request_violations(urls, base):
    """所有請求都必須與本機 Streamlit 的 scheme＋host＋port 完全相等。"""
    own = _origin(base)

    def foreign(u):
        if u.startswith(("data:", "about:")):
            return False
        if u.startswith("blob:"):
            return _origin(u[len("blob:"):]) != own
        return _origin(u) != own
    return [u for u in urls if foreign(u)]


# ───────────────────────── 對比量測 ─────────────────────────

CONTRAST_JS = r"""
(spec) => {
  const P = c => { const m = c.match(/rgba?\(([^)]+)\)/); const p = m[1].split(',').map(s => parseFloat(s)); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; };
  const eff = el => { const layers = [];
    for (let e = el; e; e = e.parentElement) { const c = P(getComputedStyle(e).backgroundColor); if (c[3] > 0) { layers.push(c); if (c[3] >= 1) break; } }
    let base = [255, 255, 255];
    for (let i = layers.length - 1; i >= 0; i--) { const [r, g, b, a] = layers[i]; base = [r * a + base[0] * (1 - a), g * a + base[1] * (1 - a), b * a + base[2] * (1 - a)]; }
    return base.map(x => Math.round(x * 100) / 100); };
  const over = (fg, bg) => { const a = fg[3]; return [fg[0] * a + bg[0] * (1 - a), fg[1] * a + bg[1] * (1 - a), fg[2] * a + bg[2] * (1 - a)].map(x => Math.round(x * 100) / 100); };
  const opacityOf = el => { let o = 1; for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  const shown = e => { const b = e.getBoundingClientRect(); const s = getComputedStyle(e); return e.getClientRects().length > 0 && b.width > 0 && b.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const sides = ['Top', 'Right', 'Bottom', 'Left'];
  const borders = [];
  for (const sel of spec.borders) {
    [...document.querySelectorAll(sel)].filter(shown).forEach((e, i) => { const s = getComputedStyle(e);
      borders.push({sel, i, styles: sides.map(k => s['border' + k + 'Style']), widths: sides.map(k => parseFloat(s['border' + k + 'Width'])),
                    colors: sides.map(k => P(s['border' + k + 'Color'])), own: eff(e), outer: e.parentElement ? eff(e.parentElement) : null}); });
  }
  const texts = [];
  for (const sel of spec.texts) {
    [...document.querySelectorAll(sel)].filter(shown).forEach((root, ri) => {
      [root, ...root.querySelectorAll('*')].forEach(e => {
        const own = [...e.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
        if (!own || !shown(e)) return;
        const s = getComputedStyle(e); const bg = eff(e); const fg = P(s.color);
        texts.push({sel, ri, text: own.slice(0, 40), fg: over(fg, bg), bg, opacity: opacityOf(e), fontSize: parseFloat(s.fontSize)}); }); });
  }
  const inputs = [];
  for (const sel of (spec.inputs || [])) {
    [...document.querySelectorAll(sel)].filter(shown).forEach(e => { const st = getComputedStyle(e);
      inputs.push({sel, fg: over(P(st.color), eff(e)), bg: eff(e), opacity: opacityOf(e), fontSize: parseFloat(st.fontSize)}); });
  }
  const focus = (() => { const e = document.activeElement; if (!e || e === document.body) return null; const s = getComputedStyle(e);
    return {tag: e.tagName, outlineStyle: s.outlineStyle, outlineWidth: parseFloat(s.outlineWidth), outlineColor: P(s.outlineColor), bg: eff(e.parentElement || e), page: eff(document.body)}; })();
  return {borders, texts, inputs, focus};
}
"""


def _lin(v):
    c = v / 255.0
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb):
    r, g, b = rgb[:3]
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast_ratio(a, b):
    """WCAG 2.x 對比值 (L1+0.05)/(L2+0.05)，L1 為較亮者。輸入為不透明 rgb（0–255）。"""
    la, lb = sorted((relative_luminance(a), relative_luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def text_rows(c, selector):
    return [dict(t, ratio=contrast_ratio(t["fg"], t["bg"])) for t in c["texts"] if t["sel"] == selector]


def text_violations(c, selector):
    """指定區塊內每一段可見文字：對其有效底色 ≥4.5:1，且累計 opacity 為 1。"""
    rows = text_rows(c, selector)
    if not rows:
        return [("找不到文字", selector)]
    bad = []
    for r in rows:
        if r["ratio"] < MIN_TEXT_CONTRAST:
            bad.append(("文字對比低於 4.5:1", selector, r["text"], round(r["ratio"], 2), r["fg"], r["bg"]))
        if r["opacity"] < 1:
            bad.append(("文字或祖先有 opacity<1", selector, r["text"], r["opacity"]))
    return bad


def input_violations(c, selector):
    """表單控制項（輸入框內的文字）對其有效底色 ≥4.5:1。"""
    rows = [dict(i, ratio=contrast_ratio(i["fg"], i["bg"])) for i in c["inputs"] if i["sel"] == selector]
    if not rows:
        return [("找不到輸入元素", selector)]
    return [("輸入文字對比低於 4.5:1", selector, round(r["ratio"], 2)) for r in rows if r["ratio"] < MIN_TEXT_CONTRAST]


def border_violations(c, selector):
    """指定選擇器至少出現一個元素；每個元素四邊皆有寬度、不透明，且邊框對外層背景 ≥3:1。"""
    rows = [b for b in c["borders"] if b["sel"] == selector]
    if not rows:
        return [("找不到元素", selector)]
    bad = []
    for b in rows:
        if min(b["widths"]) <= 0 or min(col[3] for col in b["colors"]) < 1:
            bad.append(("邊框無寬度或半透明（量不準）", selector, b["widths"]))
            continue
        worst = min(contrast_ratio(col, b["outer"]) for col in b["colors"])
        if worst < MIN_NONTEXT_CONTRAST:
            bad.append(("邊框對外層背景低於 3:1", selector, round(worst, 2)))
    return bad


def focus_violations(c):
    """目前焦點元素必須有可見焦點環：outline 非 none、寬 ≥2px，且對其周圍底色 ≥3:1。"""
    f = c["focus"]
    if f is None:
        return [("沒有焦點元素",)]
    bad = []
    if f["outlineStyle"] in ("none", "hidden") or f["outlineWidth"] < 2:
        bad.append(("沒有可見焦點環", f["tag"], f["outlineStyle"], f["outlineWidth"]))
    elif contrast_ratio(f["outlineColor"], f["page"]) < MIN_NONTEXT_CONTRAST:
        bad.append(("焦點環對比低於 3:1", round(contrast_ratio(f["outlineColor"], f["page"]), 2)))
    return bad
