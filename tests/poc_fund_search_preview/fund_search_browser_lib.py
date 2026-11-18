# -*- coding: utf-8 -*-
"""🔍 找一檔基金／依條件篩選 隔離式 FAKE Preview 的瀏覽器量測與判定函式（純函式＋一段 JS）。

只放「量什麼、怎麼判」，不起 server、不開瀏覽器；測試檔負責起 Streamlit 與 Chromium。
"""
from __future__ import annotations

import re
from urllib.parse import urlsplit

MIN_TARGET = 48

MEASURE_JS = r"""
() => {
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth;
  const shown = e => { const s = getComputedStyle(e); const b = e.getBoundingClientRect();
    return e.getClientRects().length > 0 && s.visibility !== 'hidden' && s.display !== 'none' && parseFloat(s.opacity) > 0 && b.width > 0 && b.height > 0; };
  const top = sel => { const e = main.querySelector(sel); return e && shown(e) ? e.getBoundingClientRect().top + window.scrollY : null; };
  const inSelect = e => !!e.closest('[data-testid="stSelectbox"]');
  const targetsOf = (sel, kind) => [...main.querySelectorAll(sel)].filter(e => shown(e) && !inSelect(e)).map(e => { const b = e.getBoundingClientRect();
    return {kind, h: b.height, w: b.width, right: b.right}; });
  const targets = [].concat(targetsOf('[data-testid="stTextInputRootElement"]', 'input'), targetsOf('[data-testid="stTextInputRootElement"] input', 'input-el'),
    targetsOf('[data-testid="stFormSubmitButton"] button', 'button'), targetsOf('[data-testid="stCheckbox"] label', 'checkbox'),
    targetsOf('summary', 'summary'));
  const sel = document.querySelector('[data-testid="stSelectbox"] [role="combobox"], [data-testid="stSelectbox"] input');
  const selBox = sel ? (sel.closest('[data-baseweb="select"]') || sel).getBoundingClientRect() : null;
  const details = [...main.querySelectorAll('details')];
  const rendererEls = [...main.querySelectorAll('[data-block], [data-block] *')].filter(shown);
  const interactive = [...main.querySelectorAll('button, a, input, select, textarea, summary, details, [tabindex], [onclick], [href]')].filter(e => shown(e));
  const seq = {idle: top('[data-block="lookup-idle"]'), title: top('h1'), input: top('[data-testid="stTextInput"]'), isin: top('[data-block="isin-note"]'), button: top('[data-testid="stFormSubmitButton"]'),
    result: top('[data-block="lookup-result"], [data-block="isin-notice"]'), basic: top('[data-block="basic-info"]'), divider: top('[data-block="exp-divider"]'),
    exp0: top('[data-block="exp0"]'), exp1: top('[data-block="exp1"]'), cond1: top('[data-testid="stCheckbox"]'), exp2: top('[data-block="exp2"]'), exp7: top('[data-block="exp7"]')};
  const card = main.querySelector('[data-block="lookup-result"]');
  const exp0 = main.querySelector('[data-block="exp0"]');
  return {vw, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth, targets,
          selectH: selBox ? selBox.height : null, seq,
          details: {count: details.length, open: details.filter(d => d.open).length, nested: details.reduce((n, d) => n + d.querySelectorAll('details').length, 0)},
          mainLinks: main.querySelectorAll('a[href]').length, scripts: main.querySelectorAll('script').length,
          imgs: main.querySelectorAll('img').length, bold: [...main.querySelectorAll('b, strong')].filter(e => e.closest('[data-block]')).length,
          overflowing: rendererEls.filter(e => e.getBoundingClientRect().right > vw + 0.5).map(e => e.tagName + '.' + (e.className || '')).slice(0, 5),
          text: main.innerText, cardText: card ? card.innerText : null, outcome: card ? card.dataset.outcome : null,
          exp0: exp0 ? {matched: exp0.dataset.matched ?? null, undetermined: exp0.dataset.undetermined ?? null, conditions: exp0.dataset.conditions, text: exp0.innerText} : null,
          fundRows: main.querySelectorAll('[data-fund]').length,
          traceLast: (() => { const t = [...main.querySelectorAll('[data-trace]')].pop(); if (!t) return null;
                              return [t.querySelector('[data-col="matched"]').innerText, t.querySelector('[data-col="undetermined"]').innerText]; })(),
          failed: [...main.querySelectorAll('[data-state="failed"]')].map(e => e.dataset.block)};
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


def touch_target_violations(m):
    """可見控制項（輸入框、查詢鈕、條件勾選、details 摘要列）高度與寬度皆須 ≥48px；harness 的 selectbox 不在此列（據實揭露，另量）。"""
    kinds = {t["kind"] for t in m["targets"]}
    bad = []
    for need in ("input", "button", "checkbox", "summary"):
        if need not in kinds:
            bad.append(("找不到控制項", need))
    for t in m["targets"]:
        if t["h"] < MIN_TARGET - 0.5 or t["w"] < MIN_TARGET - 0.5:
            bad.append(("觸控目標不足 48px", t))
        if t["right"] > m["vw"] + 0.5:
            bad.append(("控制項超出視窗", t))
    return bad


def details_violations(m):
    d = m["details"]
    bad = []
    if d["count"] != 1:
        bad.append(("details 不是恰好一個", d))
    if d["open"]:
        bad.append(("details 預設沒有收合", d))
    if d["nested"]:
        bad.append(("details 巢狀", d))
    return bad


def order_violations(m, with_result):
    """首屏順序：標題 → 輸入框 → ISIN 說明 → 查詢鈕 →（結果卡；查詢前＝『尚未查詢』卡）→ 基本資料 → 分隔 → EXP-0 → EXP-1 → EXP-2 → EXP-7。"""
    s = m["seq"]
    names = ["title", "input", "isin", "button"] + (["result"] if with_result else ["idle"]) + ["basic", "divider", "exp0", "exp1", "cond1", "exp2", "exp7"]
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
    for w in ("基金不存在", "查無基金", "已確認", "推薦", "最佳", "排名", "NAV", "報酬", "績效"):
        if w in m["text"]:
            bad.append(("出現禁用字樣", w))
    return bad


def count_violations(m):
    """展示 N／M 時：EXP-2 列數＝N＋M、EXP-7 末列＝(N, M)；沒有展示（零條件或來源失敗）就不得有結果列。"""
    e = m["exp0"]
    if e is None:
        return [("沒有 EXP-0",)]
    if e["matched"] is None:
        bad = []
        if m["fundRows"]:
            bad.append(("未展示 N／M 卻有結果列", m["fundRows"]))
        if m["traceLast"] is not None:
            bad.append(("未展示 N／M 卻有軌跡列", m["traceLast"]))
        return bad
    n, k = int(e["matched"]), int(e["undetermined"])
    bad = []
    if m["fundRows"] != n + k:
        bad.append(("EXP-2 列數≠N＋M", m["fundRows"], n, k))
    last = None if m["traceLast"] is None else tuple(int(re.search(r"(\d+)\s*$", x).group(1)) for x in m["traceLast"])
    if last != (n, k):
        bad.append(("EXP-7 末列≠(N, M)", m["traceLast"], n, k))
    return bad


def structure_violations(m, with_result=False):
    return (overflow_violations(m) + touch_target_violations(m) + details_violations(m) + order_violations(m, with_result)
            + static_violations(m) + count_violations(m))


def _origin(url):
    """(scheme, host, port)；ws／wss 視同 http／https；沒有明示 port 時取該 scheme 的預設埠。"""
    parts = urlsplit(url)
    scheme = {"ws": "http", "wss": "https"}.get(parts.scheme, parts.scheme)
    try:
        port = parts.port or {"http": 80, "https": 443}.get(scheme)
    except ValueError:   # `8501.evil.example`、`85011` 之類不合法的埠：不可能等於本機埠，標成無效值（必判外部）
        port = "invalid"
    return scheme, (parts.hostname or "").lower(), port


def external_request_violations(urls, base):
    """所有請求都必須與本機 Streamlit 的 scheme＋host＋port **完全相等**；`http://127.0.0.1:8501.evil.example/` 之類只是前綴相同的外部主機一律違規。"""
    own = _origin(base)

    def foreign(u):
        if u.startswith(("data:", "about:")):
            return False
        if u.startswith("blob:"):      # blob: 只放行『本機 origin 自己產生』的（blob:http://<本機 origin>/…）；blob:null／外部 origin 的 blob 一律視為外部
            return _origin(u[len("blob:"):]) != own
        return _origin(u) != own
    return [u for u in urls if foreign(u)]


# ───────────────────────── 對比量測（DEC-2026-11-17-03 視覺對比要求；WCAG 2.x 相對亮度） ─────────────────────────

MIN_NONTEXT_CONTRAST = 3.0     # 重要狀態的邊框（非文字）對比下限
MIN_TEXT_CONTRAST = 4.5        # 文字對比下限（一律用一般字級門檻，不用大字 3:1 的寬鬆門檻）

# 在瀏覽器內取 computed style：邊框四邊的 style／寬／色、元素自身的有效底色（逐層疊 alpha 到不透明）、外層（父元素）有效底色；
# 以及指定區塊內每個有直接文字的元素的 computed color、有效底色與累計 opacity。只回傳原始 rgb，比值由 Python 端的 `contrast_ratio` 算。
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
                    colors: sides.map(k => P(s['border' + k + 'Color'])), own: eff(e), outer: e.parentElement ? eff(e.parentElement) : null,
                    text: e.innerText.trim().slice(0, 60)}); });
  }
  const texts = [];
  for (const sel of spec.texts) {
    [...document.querySelectorAll(sel)].filter(shown).forEach((root, ri) => {
      const els = [root, ...root.querySelectorAll('*')];
      els.forEach(e => { const own = [...e.childNodes].filter(n => n.nodeType === 3 && n.textContent.trim()).map(n => n.textContent.trim()).join(' ');
        if (!own || !shown(e)) return;
        const s = getComputedStyle(e); const bg = eff(e); const fg = P(s.color);
        texts.push({sel, ri, text: own.slice(0, 40), fg: over(fg, bg), bg, opacity: opacityOf(e), fontSize: parseFloat(s.fontSize)}); }); });
  }
  const cells = [...document.querySelectorAll(spec.cells || '__none__')].filter(shown).map(e => { const b = e.getBoundingClientRect(); return {top: Math.round(b.top + window.scrollY), left: Math.round(b.left), right: Math.round(b.right)}; });
  return {borders, texts, cells, vw: document.documentElement.clientWidth};
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


def border_rows(c, selector, *, want_style="dashed"):
    """某選擇器的每個元素：四邊 style 是否都是 want_style、四邊對『外層背景』與『自身背景』的最小對比、邊框寬度。"""
    rows = []
    for b in c["borders"]:
        if b["sel"] != selector:
            continue
        rows.append({
            "i": b["i"], "styles": b["styles"], "widths": b["widths"], "alphas": [col[3] for col in b["colors"]],
            "vs_outer": min(contrast_ratio(col, b["outer"]) for col in b["colors"]),
            "vs_own": min(contrast_ratio(col, b["own"]) for col in b["colors"]),
            "color": b["colors"][0][:3], "own": b["own"], "outer": b["outer"],
            "all_want_style": all(s == want_style for s in b["styles"]),
        })
    return rows


def border_violations(c, selector, *, want_style="dashed"):
    """指定選擇器必須至少出現一個元素；每個元素四邊皆為 want_style、不透明、有寬度，且邊框對外層背景與對自身背景皆 ≥3:1。"""
    rows = border_rows(c, selector, want_style=want_style)
    if not rows:
        return [("找不到元素", selector)]
    bad = []
    for r in rows:
        if not r["all_want_style"]:
            bad.append(("邊框不是預期線型", selector, r["styles"]))
        if min(r["widths"]) <= 0 or min(r["alphas"]) < 1:
            bad.append(("邊框無寬度或半透明（量不準）", selector, r["widths"], r["alphas"]))
        for key in ("vs_outer", "vs_own"):
            if r[key] < MIN_NONTEXT_CONTRAST:
                bad.append(("邊框對比低於 3:1", selector, key, round(r[key], 2), r["color"], r["own"], r["outer"]))
    return bad


def text_rows(c, selector):
    return [dict(t, ratio=contrast_ratio(t["fg"], t["bg"])) for t in c["texts"] if t["sel"] == selector]


def text_violations(c, selector):
    """指定區塊內每一段可見文字：對其有效底色 ≥4.5:1，且累計 opacity 為 1（opacity<1 會讓實際對比低於量到的值）。"""
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
