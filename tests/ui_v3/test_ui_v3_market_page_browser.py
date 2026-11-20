# -*- coding: utf-8 -*-
"""🌍 市場頁**本體**的瀏覽器級回歸守衛（slow lane；需要 streamlit 與 Chromium；客戶核准 G8／V4，`DEC-2026-11-10-06`）。

與同目錄 `test_ui_v3_top_nav_browser.py` 的分工：那一檔只量 Shell（頁首五格）；本檔量**頁本體**在真瀏覽器的版面事實。
AppTest 不載入 CSS，DOM 級守衛量不到「橫向溢出」「圖是否真的可見、有沒有尺寸、有沒有被蓋住」，這一檔補這一層。

資料：`market_stubs` 的**合成 fixture**（人造數值，不是市場資料；不連 FRED／Yahoo／任何外部來源）。情境用 query string 切換：
`normal`、`tw_missing`（台股缺）、`both_missing`（兩條都缺）、`us_failed`（S&P 取數失敗，原文帶假 token 用來驗不外漏）。

**斷言什麼（條件出處：`docs/evidence/fund_newui2_market_visual_acceptance_plan_2026_11_10.md` §1 MV 表）**
- 390／768／1280 整頁與頁本體元素無橫向溢出（MV-08、§6）。
- 主圖：存在、可見（非 display:none／visibility:hidden）、非零尺寸、水平在視窗內、長寬比維持 viewBox 360:240、
  在摘要之後與第一張 Secondary 卡之前、中心點沒被別的元素蓋住（MV-05、MV-09 只斷言「存在、可見、非零尺寸」）。
- **首屏主圖露出量（G3／G6 施工批起有門檻）**：G5 原本「暫時接受現況、只記錄」；客戶規則為「首屏圖的露出量不得明顯變差，因內距而下降時優先零額外內距」，
  故改為斷言「露出量 ≥ 改前基線 − 1px（容次像素取整）」；基線＝改前 `origin/main`（192848b）同腳本同合成資料實測：390／768／1280 ＝ 156.6／181.4／198.4px
  （`_FOLD_BASELINE`；🌍 視覺批 1 已上調，見該常數註解）。390 另斷言主圖渲染寬 ≥354（改前 358；卡內左右滿版後為卡內寬 356，比例仍 360:240、最大寬 720）。數字仍照舊 print 與 `record_property`。
- 頁首五格 S1（`DEC-2026-11-06-01`／`-07-02`）：≤768 五格全可見、等寬、不重疊、不橫滑、各格 ≥48px 高；≥769 側欄在、頁首隱藏。
- 已核准排版：區塊順序（MV-02）、首屏 chip＋核心數字 ≤5（MV-03）、缺資料恆 `⬜`／`◇ 資料未備`、Missing 不畫零不畫空座標軸、
  取數失敗原文不外漏（MV-04、MV-07）。

**G3／G6 施工批新增的守衛（客戶核准 G3 候選 B 色票＋A 尺寸、G6 限定容器化；`docs/evidence/fund_newui2_market_g3_g6_build_evidence_2026_11_11.md`）**
- 卡片容器：首屏摘要在 `card.summary`、Primary 圖與其原生單選控制項在 `card.chart`、Secondary 兩卡各有外框；利率卡的子序列單選在卡內；
  兩卡（≥768 並排時）卡頂在同一條水平線、**不強制等高**。
- token 實際套用（computed style）：主背景／側欄背景／卡片邊與面與圓角與內距／單選選取點的 primary／chip tone 色＝核准值；
  頁面上沒有殘留的舊色（`.streamlit/config.toml` 的舊 theme 色 `#f6f8fa`／`#0e1117`／`#1f6feb`／`#1f2328`）。
- 圖寬 ≤720（維持 viewBox 比例，既有比例守衛不放寬）、三寬度無橫向溢出；控制項（檢視／期間／利率子序列）真的可操作且仍在卡內。

**穩定性**：不寫像素精確值。容差都有理由：長寬比 ±0.03（SVG `preserveAspectRatio` 縮放為浮點）、水平邊界 ±0.5px（次像素取整）、
五格等寬 ±1px（沿用頁首守衛）。順序用 DOM 順序（`compareDocumentPosition`），不用 y 座標（768／1280 兩欄並排時 y 會相等）。

**🌍 視覺批 1（單選 pill／迷你圖滿寬／主圖置中；`docs/evidence/mkt_visual_batch1_2026_11_20/`）新增守衛**
- `pill_violations`：三組單選共 11 個選項，每個 ≥48px 高、≥44px 寬、圓點隱藏（原生 input 仍在）；選取＝填 `color.pill.selected.bg`＋文字 `color.pill.selected.text`＋
  粗體（≥700；顏色不是唯一訊息）；未選＝`color.pill.bg`＋`color.pill.border`；圓角＝`radius.pill`。
- `spark_violations`：迷你圖寬＝其所在卡的內寬（容 1px）、末點為正圓（`r` 相等、`<circle>` 渲染後寬高比 1）。
- ≥769 主圖水平置中（左右留白差 ≤1px）；鍵盤 Tab 進入單選時焦點環＝2px `color.pill.focus`。

**🌍 視覺批 2（輔助字 12→13px／狀態列折行；`docs/evidence/mkt_visual_batch2_2026_11_20/`）新增守衛**
- `aux_font_violations`：Status Bar／頁尾（三寬度）與側欄「開發中」標籤／更新資料註記（≥769）的字級＝`type.caption`（13px）；Status Bar 高度 ≤ 行數×20px（13px 字不得把它撐高而吃首屏）。
- `top_nav_font_violations`：≤768 頁首五格的字級不得縮小（頁名／未掛載格 ≥12px、「開發中」≥10px；本批不動導覽）。
- `status_row_violations`：`▸ 各項資料狀態` 展開後逐列，日期與「資料日」不在字中折行、每列至多 2 行（768／1280 為 1 行）、無橫向溢出。
- 首屏露出量：施工後三寬度實測與批 1 完全相同（199.8／249.4／266.4；降級情境同），`_FOLD_BASELINE` 不變（未放寬、未收緊）。

**變異驗證（負控）**：本檔後半 `test_mutation_*` 在**測試內**對已載入的頁面注入 CSS／DOM（橫溢、隱藏圖、零尺寸圖、遮蓋圖、縮小頁首格、
改順序、加爆 chip、缺資料畫零），斷言上面同一組判定函式**真的會報**；不改任何 production 程式。負控全在記憶體內現編。
"""

import pathlib
import sys

import pytest

pytestmark = pytest.mark.slow

_HERE = pathlib.Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]
sys.path.insert(0, str(_ROOT / "tests" / "ui_v2"))

pytest.importorskip("streamlit", reason="本環境系統 python3 匯入不到 streamlit")

import _ui_v2_chromium  # noqa: E402  瀏覽器解析（CI 找不到要 fail）

_APP = f"""
import sys
sys.path.insert(0, {str(_ROOT)!r}); sys.path.insert(0, {str(_HERE)!r})
import streamlit as st
import market_stubs as ms
from ui_v3.adapters import market_page as adapter
_SCENARIOS = {{"normal": {{}}, "tw_missing": dict(tw="missing"), "both_missing": dict(tw="missing", us="missing"),
              "us_failed": dict(us="error")}}
_view, _table = ms.view(**_SCENARIOS[st.query_params.get("scenario", "normal")]), ms.table()
adapter.load = lambda sources: (_view, _table)
from ui_v3 import app_preview
app_preview.main()
"""

_MEASURE = r"""
() => {
  const vis = e => { if (!e) return false; const s = getComputedStyle(e); return e.getClientRects().length > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const main = document.querySelector('[data-testid="stMain"]');
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const rect = e => { const b = e.getBoundingClientRect(); return {x: b.x, y: b.y, r: b.right, b: b.bottom, w: b.width, h: b.height}; };
  const out = {vw, vh, docScrollW: document.documentElement.scrollWidth, mainScrollW: main.scrollWidth, mainClientW: main.clientWidth};
  // 頁本體元素水平邊界
  out.bodyBoxes = [...main.querySelectorAll('.uv3-card, [class*="st-key-uv3-card-"], svg.uv3-chart, .uv3-row, .uv3-note, h1, h3, [data-testid="stRadio"], [data-testid="stExpander"]')]
    .filter(vis).map(e => ({t: e.tagName + (e.dataset.card ? '#' + e.dataset.card : ''), ...rect(e)}));
  // 主圖
  const svg = main.querySelector('svg.uv3-chart');
  if (svg) {
    const s = getComputedStyle(svg), b = svg.getBoundingClientRect();
    out.chart = {exists: true, display: s.display, visibility: s.visibility, opacity: s.opacity, visibleBox: vis(svg), ...rect(svg),
                 absTop: b.top + window.scrollY, series: svg.querySelectorAll('path').length,
                 foldPx: Math.max(0, Math.min(vh, b.bottom) - Math.max(0, b.top))};
  } else out.chart = {exists: false};
  // 區塊順序（DOM 順序）
  const q = (sel) => main.querySelector(sel);
  const exp = main.querySelectorAll('[data-testid="stExpander"]');
  const marks = {h1: q('h1'), market_state: q('[data-field="market_state"]'), attention: q('[data-field="attention"]'),
    evidence_row: (q('.uv3-evidence') || {closest: () => null}).closest('.uv3-row'),
    freshness: (q('[data-status-key="threshold_pending"]') || {closest: () => null}).closest('.uv3-row'),
    primary: q('h3'), chart: svg, source_limits: exp[0], vix: q('[data-card="vix"]'), rates: q('[data-card$="_pct"]'),
    'MKT-1': q('[data-card="MKT-1"]'), 'MKT-2': q('[data-card="MKT-2"]'), 'MKT-3': q('[data-card="MKT-3"]'),
    missing_group: exp[1], status_group: exp[2]};
  const present = Object.entries(marks).filter(([, e]) => e);
  present.sort((a, b) => (a[1].compareDocumentPosition(b[1]) & Node.DOCUMENT_POSITION_FOLLOWING) ? -1 : 1);
  out.order = present.map(([k]) => k);
  out.secondaryCount = main.querySelectorAll('[data-card="vix"], [data-card$="_pct"]').length;
  // 圖相對位置（圖在摘要之後、第一張 Secondary 卡之前）
  const fresh = marks.freshness, vixFrame = q('.st-key-uv3-card-sec-vix');
  out.summaryBottom = fresh ? fresh.getBoundingClientRect().bottom : null;
  out.vixTop = vixFrame ? vixFrame.getBoundingClientRect().top : null;
  // 首屏名額：第一張 data-card 之前、可見、不在摺疊區的 chip；格內有 chip 的 evidence 只算一格
  const firstCard = q('[data-card]');
  const scope = [...document.querySelectorAll('.uv3-chip, .uv3-evidence')].filter(e => vis(e) && !e.closest('[data-testid="stExpander"]')
      && !(e.classList.contains('uv3-chip') && e.closest('.uv3-evidence'))
      && (!firstCard || (e.compareDocumentPosition(firstCard) & Node.DOCUMENT_POSITION_FOLLOWING)));
  out.firstScreenBudget = scope.length;
  out.statusbarChips = document.querySelectorAll('.uv3-statusbar .uv3-chip').length;
  out.sidebarChips = document.querySelectorAll('[data-testid="stSidebar"] .uv3-chip').length;
  out.mainText = main.innerText;
  // 視覺批 2：Shell 輔助字（Status Bar／頁尾／側欄註記）與主導覽字級；Status Bar 行數與高度（行高變大會吃首屏）
  const fsOf = sel => { const e = document.querySelector(sel); if (!e || !vis(e)) return null; const s = getComputedStyle(e); return {fontSize: s.fontSize, lineHeight: s.lineHeight, h: e.getBoundingClientRect().height}; };
  out.aux = {statusBar: fsOf('.uv3-statusbar'), footer: fsOf('.uv3-footer'), sideSoon: fsOf('.uv3-nav-soon'), cta: fsOf('.uv3-cta-note'),
             topNavP: fsOf('.st-key-uv3-top-nav a[data-testid="stPageLink-NavLink"] p'), topNavDisabled: fsOf('.uv3-tn-disabled'), topNavSoon: fsOf('.uv3-tn-soon')};
  const sbar = document.querySelector('.uv3-statusbar');
  out.statusBarLines = sbar ? Math.max(1, Math.round(sbar.getBoundingClientRect().height / parseFloat(getComputedStyle(sbar).lineHeight))) : null;   // 行數＝高度÷行高（子元素置中，top 不一致不能用來數行）
  // G6：卡片容器與卡內控制項的位置關係
  const frame = k => q('.st-key-uv3-card-' + k);
  const F = {summary: frame('summary'), chart: frame('chart'), vix: frame('sec-vix'), rates: frame('sec-rates')};
  const css = e => { const s = getComputedStyle(e); return {bw: s.borderTopWidth, bs: s.borderTopStyle, bc: s.borderTopColor, bg: s.backgroundColor, radius: s.borderTopLeftRadius,
                      pad: [s.paddingTop, s.paddingRight, s.paddingBottom, s.paddingLeft].join(' '), shadow: s.boxShadow}; };
  out.frames = Object.fromEntries(Object.entries(F).map(([k, e]) => [k, e ? {...rect(e), css: css(e)} : null]));
  const inside = (e, f) => !!(e && f && f.contains(e));
  const radios = [...main.querySelectorAll('[data-testid="stRadio"]')];
  const radioIn = key => { const r = radios.find(x => x.querySelector('[data-testid="stRadioGroup"]').getAttribute('aria-label') === key); return r || null; };
  out.containment = {
    summaryRows: ['market_state', 'attention'].every(k => inside(q('[data-field="' + k + '"]'), F.summary)) && inside(marks.freshness, F.summary),
    chartInChartFrame: inside(svg, F.chart), h3InChartFrame: inside(q('h3'), F.chart),
    viewRadioInChartFrame: inside(radioIn('檢視'), F.chart), periodRadioInChartFrame: inside(radioIn('期間'), F.chart),
    chartExpanderInChartFrame: inside(exp[0], F.chart),
    ratesRadioInRatesFrame: inside(radioIn('利率與信用'), F.rates), ratesHeadInRatesFrame: inside(q('[data-card$="_pct"]'), F.rates),
    vixInVixFrame: inside(q('[data-card="vix"]'), F.vix),
    radioCount: radios.length,
  };
  // 視覺批 1：單選 pill（每個選項的尺寸／粗體／色／圓點是否隱藏）
  out.pills = [...main.querySelectorAll('label[data-testid="stRadioOption"]')].map(o => {
    const s = getComputedStyle(o), b = o.getBoundingClientRect(), dot = o.querySelector('div > div > div:first-child');
    return {selected: o.getAttribute('data-selected') === 'true', w: b.width, h: b.height, weight: s.fontWeight, bg: s.backgroundColor, color: s.color,
            border: s.borderTopColor, radius: s.borderTopLeftRadius, dotDisplay: dot ? getComputedStyle(dot).display : null,
            textColor: o.querySelector('p') ? getComputedStyle(o.querySelector('p')).color : null};
  });
  out.sparks = [...main.querySelectorAll('svg.uv3-spark')].map(sp => {
    const card = sp.closest('[class*="st-key-uv3-card-"]'), cs = getComputedStyle(card), b = sp.getBoundingClientRect(), dot = sp.querySelector('circle');
    const inner = card.getBoundingClientRect().width - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight) - parseFloat(cs.borderLeftWidth) - parseFloat(cs.borderRightWidth);
    const db = dot ? dot.getBoundingClientRect() : null;
    return {w: b.width, h: b.height, cardInner: inner, dotW: db ? db.width : null, dotH: db ? db.height : null};
  });
  const rr = radioIn('利率與信用');
  out.ratesRadio = rr ? {name: rr.querySelector('[data-testid="stRadioGroup"]').getAttribute('aria-label'), options: rr.querySelectorAll('[data-testid="stRadioOption"]').length,
                         labelVisible: !!rr.querySelector('[data-testid="stWidgetLabel"]') && vis(rr.querySelector('[data-testid="stWidgetLabel"]'))} : null;
  // token 實際套用（computed style）
  const sideEl = document.querySelector('[data-testid="stSidebar"]');
  const sel = main.querySelector('label[data-testid="stRadioOption"][data-selected="true"]');   // 視覺批 1：圓點隱藏，量 label 本體（pill）
  const tone = c => { const e = main.querySelector('.uv3-chip.uv3-tone-' + c); if (!e) return null; const s = getComputedStyle(e); return {color: s.color, bg: s.backgroundColor, bc: s.borderTopColor, radius: s.borderTopLeftRadius, pad: s.paddingTop + ' ' + s.paddingLeft, fs: s.fontSize}; };
  const cs1 = (e, ...ps) => e ? Object.fromEntries(ps.map(p => [p, getComputedStyle(e)[p]])) : null;
  out.applied = {appBg: getComputedStyle(document.querySelector('.stApp')).backgroundColor, appColor: getComputedStyle(document.querySelector('.stApp')).color,
                 headerBg: cs1(document.querySelector('[data-testid="stHeader"]'), 'backgroundColor'),
                 sidebarBg: sideEl ? getComputedStyle(sideEl).backgroundColor : null, sidebarColor: sideEl ? getComputedStyle(sideEl).color : null,
                 radioSelectedBg: sel ? getComputedStyle(sel).backgroundColor : null, h1Color: getComputedStyle(q('h1')).color,
                 h1Size: getComputedStyle(q('h1')).fontSize, noteSize: cs1(q('.uv3-note'), 'fontSize', 'color'), metric: cs1(q('.uv3-metric'), 'fontSize'),
                 gutterLeft: getComputedStyle(document.querySelector('.block-container')).paddingLeft, tones: {grey: tone('grey')}};
  // 舊 theme 色殘留（config.toml 的舊值）：看得到的元素的 color／background／border 色是否等於它們
  const legacy = ['rgb(246, 248, 250)', 'rgb(14, 17, 23)', 'rgb(31, 111, 235)', 'rgb(31, 35, 40)', 'rgb(238, 241, 244)', 'rgb(22, 27, 34)', 'rgb(158, 158, 255)'];
  out.legacyHits = [];
  for (const e of document.querySelectorAll('body *, body')) {
    if (!e.getClientRects().length) continue;
    const s = getComputedStyle(e);
    for (const [p, val] of [['color', s.color], ['bg', s.backgroundColor], ['border', parseFloat(s.borderTopWidth) > 0 ? s.borderTopColor : '']]) {
      if (legacy.includes(val)) out.legacyHits.push(p + '=' + val + ' ' + e.tagName.toLowerCase() + '.' + String(e.className && e.className.baseVal !== undefined ? e.className.baseVal : e.className).slice(0, 40));
    }
  }
  out.chipTexts = [...main.querySelectorAll('.uv3-chip')].filter(e => vis(e) && !e.closest('[data-testid="stExpander"]')).map(e => e.innerText.trim());
  // 頁首五格（S1）
  const nav = document.querySelector('.st-key-uv3-top-nav'), side = document.querySelector('[data-testid="stSidebar"]');
  out.navDisplay = nav ? getComputedStyle(nav).display : null;
  out.sidebarDisplay = side ? getComputedStyle(side).display : null;
  if (nav) {
    out.navScrollW = nav.scrollWidth; out.navClientW = nav.clientWidth;
    out.cells = [...nav.querySelectorAll('a[data-testid="stPageLink-NavLink"], .uv3-tn-disabled')].map(e => ({text: e.innerText.replace(/\s+/g, ' ').trim(), ...rect(e)}));
  }
  return out;
}
"""

_HIT = r"""
() => {   // 把主圖捲到視窗中央再取中心點命中的元素：圖不可被別的元素蓋住
  const svg = document.querySelector('[data-testid="stMain"] svg.uv3-chart');
  if (!svg) return null;
  svg.scrollIntoView({block: 'center'});
  const b = svg.getBoundingClientRect();
  const hit = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
  return {covered: !!hit && !svg.contains(hit) && hit !== svg, hit: hit ? hit.tagName + '.' + String(hit.className.baseVal ?? hit.className).slice(0, 40) : null};
}
"""

_STATUS_ROWS = r"""
() => {   // 已展開的「各項資料狀態」逐列：行數、日期／「資料日」是否被折成兩行（Range 在不同 top 即被拆）、橫向溢出
  const ex = [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stExpander"]')].find(e => e.innerText.includes('各項資料狀態'));
  const out = {vw: document.documentElement.clientWidth, docScrollW: document.documentElement.scrollWidth, rows: []};
  if (!ex) return out;
  const splitOf = (row, re) => { const w = document.createTreeWalker(row, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { const m = re.exec(n.nodeValue); if (m) { const rg = document.createRange(); rg.setStart(n, m.index); rg.setEnd(n, m.index + m[0].length);
      return new Set([...rg.getClientRects()].map(q => Math.round(q.top))).size > 1; } } return null; };
  out.rows = [...ex.querySelectorAll('[data-testid="stExpanderDetails"] .uv3-row')].map(row => { const s = getComputedStyle(row), b = row.getBoundingClientRect();
    return {text: row.innerText.replace(/\s+/g, ' ').trim().slice(0, 60), lines: Math.round(b.height / (parseFloat(s.lineHeight) || 24.8)),
            dateSplit: splitOf(row, /\d{4}-\d{2}-\d{2}/), labelSplit: splitOf(row, /資料日/), scrollW: row.scrollWidth, clientW: row.clientWidth}; });
  return out;
}
"""

_NAMES = ["市場", "資產", "找基金", "AI", "設定"]
_SCENARIOS = ("normal", "tw_missing", "both_missing", "us_failed")
_WIDTHS = (390, 768, 1280)
_BAD_TOKENS = ("NaN", "nan", "None", "null", "undefined", "Infinity")


# ───────────────────────── 判定函式（正向測試與變異驗證共用同一組） ─────────────────────────

def overflow_violations(m):
    bad = []
    if m["docScrollW"] > m["vw"]:
        bad.append(("整頁橫向溢出", m["docScrollW"], m["vw"]))
    if m["mainScrollW"] > m["mainClientW"]:
        bad.append(("主內容橫向溢出", m["mainScrollW"], m["mainClientW"]))
    bad += [("元素超出視窗水平邊界", b["t"], round(b["x"], 1), round(b["r"], 1)) for b in m["bodyBoxes"]
            if b["x"] < -0.5 or b["r"] > m["vw"] + 0.5]
    return bad


def chart_violations(m):
    c = m["chart"]
    if not c["exists"]:
        return [("主圖不存在",)]
    bad = []
    if c["display"] == "none" or c["visibility"] == "hidden" or float(c["opacity"]) == 0 or not c["visibleBox"]:
        bad.append(("主圖不可見", c["display"], c["visibility"], c["opacity"]))
    if c["w"] <= 0 or c["h"] <= 0:
        bad.append(("主圖零尺寸", c["w"], c["h"]))
        return bad
    # 寬 ≥280：viewBox 360 寬、刻度字 11px，窄於 280 字會縮到 <8.6px 難讀；390 視窗實測約 358
    if c["w"] < 280:
        bad.append(("主圖過窄", c["w"]))
    # 長寬比維持 viewBox 360:240（=0.667）；±0.03 容次像素取整
    if abs(c["h"] / c["w"] - 240 / 360) > 0.03:
        bad.append(("主圖長寬比跑掉", round(c["h"] / c["w"], 3)))
    # G3／G6：圖最大寬 720（客戶核准維持；不得為了填滿欄寬而放大）
    if c["w"] > 720.5:
        bad.append(("主圖超過最大寬 720", c["w"]))
    if c["x"] < -0.5 or c["r"] > m["vw"] + 0.5:
        bad.append(("主圖超出視窗水平邊界", c["x"], c["r"]))
    if m["summaryBottom"] is not None and c["y"] < m["summaryBottom"] - 0.5:
        bad.append(("主圖在首屏摘要之上", c["y"], m["summaryBottom"]))
    if m["vixTop"] is not None and c["b"] > m["vixTop"] + 0.5:
        bad.append(("主圖壓到第一張 Secondary 卡", c["b"], m["vixTop"]))
    return bad


# 首屏主圖露出量基線（px；Chromium、視窗高 844／844／800、合成資料）。容差 1px＝次像素取整。
# 🌍 視覺批 1（單選 pill＋標籤內嵌，只上調不下調）：施工後同腳本同合成資料實測 390／768／1280 ＝ 199.8／249.4／266.4px
# （施工前 origin/main 747c7585 實測 159.8／209.4／226.4；舊基線 156.6／181.4／198.4 來自更早的 192848b）。
# 新基線＝施工後實測取整後再扣 5px（容 CI 字型／hinting 差異；仍遠高於施工前，退回舊版面或再多 40px 間距都會被抓）。
# 🌍 視覺批 2（輔助字 13px＋狀態列折行）：同腳本同合成資料實測露出量與批 1 逐位相同（Status Bar 行高固定 18px），基線不變。
_FOLD_BASELINE = {390: 194.0, 768: 244.0, 1280: 261.0}
_FOLD_TOLERANCE = 1.0
_CHART_MIN_W_390 = 354   # 改前 358；卡內左右滿版後 356；窄於此代表卡片內距又吃掉圖寬


def firstscreen_violations(m, width):
    c = m["chart"]
    if not c["exists"]:
        return [("主圖不存在",)]
    bad = []
    if c["foldPx"] < _FOLD_BASELINE[width] - _FOLD_TOLERANCE:
        bad.append(("首屏主圖露出量低於改前基線", round(c["foldPx"], 1), _FOLD_BASELINE[width]))
    if width == 390 and c["w"] < _CHART_MIN_W_390:
        bad.append(("390 主圖渲染寬低於 354（卡片內距吃掉圖寬）", round(c["w"], 1)))
    return bad


def nav_violations(m, width):
    if width >= 769:
        bad = []
        if m["navDisplay"] != "none" or m["sidebarDisplay"] != "block":
            bad.append(("≥769 應為側欄、頁首隱藏", m["navDisplay"], m["sidebarDisplay"]))
        return bad
    bad = []
    if m["navDisplay"] != "flex" or m["sidebarDisplay"] != "none":
        bad.append(("≤768 應為頁首、側欄隱藏", m["navDisplay"], m["sidebarDisplay"]))
    cells = m.get("cells") or []
    if len(cells) != 5:
        return bad + [("頁首格數不是 5", len(cells))]
    for cell, name in zip(cells, _NAMES):
        if name not in cell["text"]:
            bad.append(("格名不符", name, cell["text"]))
        if cell["x"] < -0.5 or cell["r"] > m["vw"] + 0.5:
            bad.append(("頁首格不在視窗內", name))
        if cell["w"] < 48 or cell["h"] < 48:
            bad.append(("觸控目標 <48px", name, round(cell["w"], 1), round(cell["h"], 1)))
    widths = [c["w"] for c in cells]
    if max(widths) - min(widths) > 1.0:
        bad.append(("五格不等寬", widths))
    if any(cells[i]["r"] > cells[i + 1]["x"] + 0.5 for i in range(4)):
        bad.append(("五格重疊",))
    if m["navScrollW"] > m["navClientW"]:
        bad.append(("頁首可橫向捲動", m["navScrollW"], m["navClientW"]))
    return bad


# ───────────────────────── 🌍 視覺批 2（輔助字 12→13px／狀態列折行；`docs/evidence/mkt_visual_batch2_2026_11_20/`）判定函式 ─────────────────────────

_STATUS_BAR_LINE_PX = 20.0   # Status Bar 每一行的占高（行高 18px＋標籤框 2px；批 1 實測單行 20、兩行 40）；13px 字不得把它撐高（會吃首屏主圖）


def aux_font_violations(m, width):
    """Shell 輔助字（非主導覽格）＝`type.caption`（13px）；Status Bar 不因字級變大而增高。"""
    a, want, bad = m["aux"], _tok("type.caption"), []
    for key in ("statusBar", "footer") + (("sideSoon", "cta") if width >= 769 else ()):
        if a[key] is None:
            bad.append(("輔助字元素不存在或不可見", key))
        elif a[key]["fontSize"] != want:
            bad.append(("輔助字不是 type.caption", key, a[key]["fontSize"], want))
    sb = a["statusBar"]
    if sb is not None and m["statusBarLines"] and sb["h"] > m["statusBarLines"] * _STATUS_BAR_LINE_PX + 0.6:
        bad.append(("Status Bar 高度超過行數×20px（字級放大不得吃首屏）", round(sb["h"], 1), m["statusBarLines"]))
    return bad


def top_nav_font_violations(m, width):
    """主導覽格（≤768 頁首五格）字級不得縮小：頁名／未掛載格 ≥12px、「開發中」標籤 ≥10px（本批不動導覽）。"""
    if width >= 769:
        return []
    a, bad = m["aux"], []
    for key, floor in (("topNavP", 12.0), ("topNavDisabled", 12.0), ("topNavSoon", 10.0)):
        if a[key] is None:
            bad.append(("頁首導覽字級元素不存在", key))
        elif float(a[key]["fontSize"].removesuffix("px")) < floor:
            bad.append(("頁首導覽字級被縮小", key, a[key]["fontSize"], floor))
    return bad


def status_row_violations(s, width):
    """`▸ 各項資料狀態` 展開後的逐列：不在字中折行（日期不拆、「資料日」不拆）、每列至多 2 行、無橫向溢出。"""
    bad = []
    if not s["rows"]:
        return [("狀態列沒有任何一列",)]
    if s["docScrollW"] > s["vw"]:
        bad.append(("展開後整頁橫向溢出", s["docScrollW"], s["vw"]))
    for row in s["rows"]:
        if row["dateSplit"]:
            bad.append(("日期在字中折行", row["text"]))
        if row["labelSplit"]:
            bad.append(("「資料日」在字中折行", row["text"]))
        if row["lines"] > 2:
            bad.append(("狀態列超過 2 行", row["lines"], row["text"]))
        if row["scrollW"] > row["clientW"] + 1:
            bad.append(("狀態列橫向溢出", row["scrollW"], row["clientW"]))
    return bad


# ───────────────────────── G3／G6 判定函式（正向測試與變異驗證共用同一組） ─────────────────────────

def _rgb(hex_color):
    h = hex_color.lstrip("#")
    return f"rgb({int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)})"


def _tok(name):
    from ui_v3.design import tokens
    return tokens.value(name)


def container_violations(m):
    """卡片容器存在、尺寸／色＝token、控制項在卡內（G6）。"""
    from ui_v3.design import tokens
    bad = []
    for key in ("summary", "chart", "vix", "rates"):
        f = m["frames"].get(key)
        if f is None:
            bad.append(("缺卡片容器", key))
            continue
        shape = dict(tokens.value("card.detail"))
        expect = {"bw": shape["border_width"], "bs": "solid", "bc": _rgb(_tok("color.card.border")), "bg": _rgb(_tok("color.surface")),
                  "radius": _tok("radius.card"), "pad": " ".join([shape["padding"].split()[0], shape["padding"].split()[1]] * 2), "shadow": "none"}
        for k, want in expect.items():
            if f["css"][k] != want:
                bad.append(("卡片外框與 token 不符", key, k, f["css"][k], want))
    c = m["containment"]
    for name, ok in c.items():
        if name == "radioCount" or (name == "chartInChartFrame" and not m["chart"]["exists"]):   # 兩條都缺＝不畫圖（空狀態），沒有圖可檢
            continue
        if not ok:
            bad.append(("元素不在應在的卡內", name))
    if c["radioCount"] != 3:
        bad.append(("原生單選控制項不是 3 組（檢視／期間／利率子序列）", c["radioCount"]))
    cf, ch = m["frames"].get("chart"), m["chart"]
    if cf and ch["exists"]:
        # 主圖可左右滿版（伸入卡片內距），但不得蓋過卡片邊線；文字（標題）仍須保留卡片內距、不貼邊
        if ch["x"] < cf["x"] + 1 - 0.5 or ch["r"] > cf["r"] - 1 + 0.5:
            bad.append(("主圖蓋過卡片邊線", round(ch["x"], 1), round(ch["r"], 1), round(cf["x"], 1), round(cf["r"], 1)))
        for b in m["bodyBoxes"]:
            if b["t"] == "H3" and b["x"] < cf["x"] + 11:
                bad.append(("卡內標題貼到卡片邊線（內距被吃掉）", round(b["x"], 1), round(cf["x"], 1)))
    r = m["ratesRadio"]
    if r is None or r["name"] != "利率與信用" or r["options"] != 3:
        bad.append(("利率子序列單選的無障礙名稱或選項數不符", r))
    return bad


def secondary_alignment_violations(m, width):
    """Secondary 兩卡：並排時（以實際座標判定，不以視窗寬度推斷；768 仍是兩欄）卡頂同一條水平線、且**不強制等高**；單欄（390）時依序往下排、不重疊。"""
    vix, rates = m["frames"].get("vix"), m["frames"].get("rates")
    if not vix or not rates:
        return [("缺 Secondary 卡容器",)]
    bad = []
    side_by_side = rates["x"] >= vix["r"] - 0.5
    if side_by_side:
        if abs(vix["y"] - rates["y"]) > 1.0:
            bad.append(("兩張 Secondary 卡頂沒有對齊", round(vix["y"], 1), round(rates["y"], 1)))
        if abs(vix["h"] - rates["h"]) <= 1.0:
            bad.append(("兩張 Secondary 卡被強制等高（不應補齊高度）", round(vix["h"], 1), round(rates["h"], 1)))
    elif vix["b"] > rates["y"] + 0.5:
        bad.append(("單欄時兩張 Secondary 卡重疊", vix["b"], rates["y"]))
    return bad


def pill_violations(m):
    """單選 pill（視覺批 1）：觸控尺寸、圓點隱藏、選取＝填色＋粗體、色與圓角＝token。"""
    pills = m["pills"]
    if len(pills) != 11:   # 檢視 4＋期間 4＋利率子序列 3
        return [("單選選項數不是 11", len(pills))]
    bad = []
    want = {"bg": _rgb(_tok("color.pill.bg")), "border": _rgb(_tok("color.pill.border"))}
    want_sel = {"bg": _rgb(_tok("color.pill.selected.bg")), "color": _rgb(_tok("color.pill.selected.text")),
                "border": _rgb(_tok("color.pill.selected.bg"))}
    if sum(p["selected"] for p in pills) != 3:
        bad.append(("每組單選應恰有一個選取項（共 3）", sum(p["selected"] for p in pills)))
    for i, p in enumerate(pills):
        if p["h"] < 48 - 0.5 or p["w"] < 44:
            bad.append(("單選選項低於觸控下限 48×44", i, round(p["w"], 1), round(p["h"], 1)))
        if p["dotDisplay"] != "none":
            bad.append(("單選圓點沒有隱藏", i, p["dotDisplay"]))
        if float(p["radius"].replace("px", "")) < p["h"] / 2 - 0.5:
            bad.append(("單選圓角小於半高（不是膠囊）", i, p["radius"], round(p["h"], 1)))
        exp = want_sel if p["selected"] else want
        for k, v in exp.items():
            if p[k] != v:
                bad.append(("單選色與 token 不符", i, "selected" if p["selected"] else "unselected", k, p[k], v))
        if not p["selected"] and p["textColor"] != _rgb(_tok("color.text.primary")):
            bad.append(("未選項文字色不是 color.text.primary", i, p["textColor"]))
        if p["selected"]:
            if int(float(p["weight"])) < 700:
                bad.append(("選取項不是粗體（顏色不得是唯一訊息）", i, p["weight"]))
            if p["textColor"] != want_sel["color"]:
                bad.append(("選取項文字色不是 color.pill.selected.text", i, p["textColor"]))
    return bad


def centered_violations(m, width):
    """≥769 主圖在卡內水平置中（左右留白差 ≤1px）；≤768 維持卡內滿版（不判）。"""
    c, f = m["chart"], m["frames"].get("chart")
    if width <= 768 or not c["exists"] or not f:
        return []
    left, right = c["x"] - f["x"], f["r"] - c["r"]
    return [("≥769 主圖沒有水平置中", round(left, 1), round(right, 1))] if abs(left - right) > 1.0 else []


def spark_violations(m):
    """迷你圖寬＝其所在卡的內寬（卡寬扣左右邊框與內距）；末點渲染後仍為正圓。"""
    bad = []
    if not m["sparks"]:
        return [("沒有迷你圖",)]
    for sp in m["sparks"]:
        if sp["w"] < sp["cardInner"] - 1.0 or sp["w"] > sp["cardInner"] + 1.0:
            bad.append(("迷你圖寬度沒有對齊卡內寬", round(sp["w"], 1), round(sp["cardInner"], 1)))
        if sp["dotW"] is None or abs(sp["dotW"] - sp["dotH"]) > 0.3:
            bad.append(("迷你圖末點不是正圓", sp["dotW"], sp["dotH"]))
    return bad


def token_violations(m):
    """token 實際套用到 computed style；頁面上沒有殘留舊 theme 色。"""
    a = m["applied"]
    expect = {"appBg": _rgb(_tok("color.page.bg")), "appColor": _rgb(_tok("color.text.primary")),
              "sidebarBg": _rgb(_tok("color.sidebar.bg")), "sidebarColor": _rgb(_tok("color.sidebar.text")),
              "radioSelectedBg": _rgb(_tok("color.pill.selected.bg")), "h1Color": _rgb(_tok("color.text.primary"))}
    bad = [("token 未套用", k, a[k], want) for k, want in expect.items() if a[k] != want]
    if a["headerBg"]["backgroundColor"] != _rgb(_tok("color.page.bg")):
        bad.append(("頁首背景不是 color.page.bg", a["headerBg"]))
    if a["noteSize"]["color"] != _rgb(_tok("color.text.secondary")) or a["noteSize"]["fontSize"] != _tok("type.caption"):
        bad.append(("備註字級／次要文字色不是 type.caption／color.text.secondary", a["noteSize"]))
    if a["metric"]["fontSize"] != _tok("type.metric") or a["gutterLeft"] != _tok("gutter.mobile"):
        bad.append(("主數字字級或 gutter 不符 token", a["metric"], a["gutterLeft"]))
    grey, tone = a["tones"]["grey"], _tok("color.tone.grey")
    if grey and (grey["color"], grey["bg"], grey["bc"]) != (_rgb(tone["text"]), _rgb(tone["background"]), _rgb(tone["border"])):
        bad.append(("grey tone chip 色不符 token", grey))
    bad += [("殘留舊 theme 色", h) for h in m["legacyHits"][:5]]
    return bad


_FULL_ORDER = ["h1", "market_state", "attention", "evidence_row", "freshness", "primary", "chart", "source_limits", "vix", "rates",
               "MKT-1", "MKT-2", "MKT-3", "missing_group", "status_group"]


def order_violations(m):
    expected = [k for k in _FULL_ORDER if k in m["order"]]
    bad = [] if m["order"] == expected else [("區塊順序不符 MV-02", m["order"])]
    for must in ("h1", "market_state", "attention", "freshness", "primary", "vix", "rates", "MKT-1", "MKT-2", "MKT-3",
                 "missing_group", "status_group"):
        if must not in m["order"]:
            bad.append(("缺區塊", must))
    if m["secondaryCount"] > 3:
        bad.append(("Secondary 超過 3 張", m["secondaryCount"]))
    return bad


def budget_violations(m):
    bad = []
    if m["firstScreenBudget"] > 5:
        bad.append(("首屏 chip＋核心數字超過 5", m["firstScreenBudget"]))
    if m["statusbarChips"] or m["sidebarChips"]:
        bad.append(("Status Bar／側欄不得放 chip", m["statusbarChips"], m["sidebarChips"]))
    return bad


def missing_violations(m, scenario):
    """缺資料恆 `⬜`／`◇ 資料未備` 文字；Missing 不畫零、不畫空座標軸；失敗原文不外漏。"""
    text, bad = m["mainText"], []
    bad += [("畫面出現不可呈現的 token", t) for t in _BAD_TOKENS if t in text]
    bad += [("取數失敗原文外漏", t) for t in ("429", "secret-token", "HTTP") if t in text]
    if "⬜ 無法判定" not in text or "⬜ 門檻待裁示" not in text:
        bad.append(("首屏 ⬜ 字樣缺",))
    if "◇ 資料未備" not in text:      # MKT-2 領先／同時指標在 stub 恆缺 → 任何情境都應有
        bad.append(("缺值沒有 ◇ 資料未備 字樣",))
    series = m["chart"].get("series", 0) if m["chart"]["exists"] else 0
    expected_series = {"normal": 2, "tw_missing": 1, "us_failed": 1, "both_missing": 0}[scenario]
    if series != expected_series:
        bad.append(("主圖序列數不符（缺資料不補、不畫零）", series, expected_series))
    if scenario == "both_missing" and m["chart"]["exists"]:
        bad.append(("兩條皆缺不得畫空座標軸",))
    if scenario in ("tw_missing", "both_missing"):
        import re
        row = text.split("重要依據", 1)[-1].split("資料新鮮度", 1)[0]
        if "台股" in row and not re.search(r"台股\s*◇ 資料未備", row):
            bad.append(("台股缺值沒有以 ◇ 資料未備 呈現", row.strip()[:60]))
        if re.search(r"台股[^|｜S]*[+-]?0(\.0+)?\s*%", row):
            bad.append(("台股缺值被畫成 0%", row.strip()[:60]))
    return bad


# ───────────────────────── fixtures ─────────────────────────

@pytest.fixture(scope="module")
def base_and_browser(tmp_path_factory):
    api = _ui_v2_chromium.import_sync_api()
    app = tmp_path_factory.mktemp("uv3_market_page") / "app_market_page.py"
    app.write_text(_APP, encoding="utf-8")
    with _ui_v2_chromium.streamlit_server(app) as base, api.sync_playwright() as p:
        browser = _ui_v2_chromium.launch(p)
        try:
            yield base, browser, {}
        finally:
            browser.close()


def _open(browser, base, scenario, width):
    ctx = browser.new_context(viewport={"width": width, "height": 844 if width <= 768 else 800}, locale="zh-TW", has_touch=width <= 768)
    page = ctx.new_page()
    page.goto(f"{base}/?scenario={scenario}", wait_until="networkidle")
    page.wait_for_selector('[data-field="market_state"]', timeout=60000)
    page.wait_for_timeout(1500)
    return ctx, page


@pytest.fixture
def measure(base_and_browser):
    """(scenario, width) → 量測結果；同一組只開一次頁面（各測試共用）。"""
    base, browser, cache = base_and_browser

    def run(scenario, width):
        key = (scenario, width)
        if key not in cache:
            ctx, page = _open(browser, base, scenario, width)
            try:
                m = page.evaluate(_MEASURE)
                m["hit"] = page.evaluate(_HIT)
            finally:
                ctx.close()
            cache[key] = m
        return cache[key]
    return run


# ───────────────────────── 正向守衛 ─────────────────────────

@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_no_horizontal_overflow(measure, scenario, width):
    assert not overflow_violations(measure(scenario, width))


@pytest.mark.parametrize("width", _WIDTHS)
def test_primary_chart_present_visible_nonzero_and_in_place(measure, width, record_property):
    m = measure("normal", width)
    assert not chart_violations(m), (chart_violations(m), m["chart"])
    assert m["hit"] is not None and not m["hit"]["covered"], ("主圖中心點被別的元素蓋住", m["hit"])
    # 首屏露出量：斷言「不低於改前基線 − 1px」（基線與理由見檔頭 `_FOLD_BASELINE`）
    assert not firstscreen_violations(m, width), (firstscreen_violations(m, width), m["chart"])
    info = f"w{width}: chart top y={m['chart']['y']:.0f}, foldPx={m['chart']['foldPx']:.1f}/{m['chart']['h']:.1f}, w={m['chart']['w']:.0f} (viewport h={m['vh']}; baseline fold {_FOLD_BASELINE[width]})"
    record_property(f"chart_fold_w{width}", info)
    print("\n[first-screen]", info)


@pytest.mark.parametrize("width", _WIDTHS)
def test_top_nav_s1_five_cells_mobile_and_sidebar_desktop(measure, width):
    m = measure("normal", width)
    assert not nav_violations(m, width), nav_violations(m, width)


@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_shell_aux_text_is_13px_and_top_nav_text_is_not_shrunk(measure, scenario, width):
    """🌍 視覺批 2（`DEC-2026-11-11-02` V2）：Status Bar／頁尾／側欄註記 12→13px（`type.caption`）；主導覽格字級不縮、Status Bar 不增高。"""
    m = measure(scenario, width)
    assert not aux_font_violations(m, width), (aux_font_violations(m, width), m["aux"])
    assert not top_nav_font_violations(m, width), (top_nav_font_violations(m, width), m["aux"])


def _status_rows(base_and_browser, scenario, width, *, css=None):
    base, browser, _ = base_and_browser
    ctx, page = _open(browser, base, scenario, width)
    try:
        if css:
            page.add_style_tag(content=css)
        page.locator('[data-testid="stMain"] [data-testid="stExpander"] summary', has_text="各項資料狀態").click()
        page.wait_for_timeout(500)
        return page.evaluate(_STATUS_ROWS)
    finally:
        ctx.close()


@pytest.mark.parametrize("scenario", ("normal", "tw_missing"))
@pytest.mark.parametrize("width", _WIDTHS)
def test_status_group_rows_do_not_break_inside_tokens_or_overflow(base_and_browser, scenario, width):
    """`▸ 各項資料狀態` 在 390 會折兩行：不得在日期／「資料日」字中折行；768／1280 一行；三寬度無橫向溢出。"""
    s = _status_rows(base_and_browser, scenario, width)
    assert len(s["rows"]) == 5, s
    assert not status_row_violations(s, width), (status_row_violations(s, width), s["rows"])
    if width >= 768:
        assert all(r["lines"] == 1 for r in s["rows"]), s["rows"]


@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", _WIDTHS)
def test_block_order_and_first_screen_budget(measure, scenario, width):
    m = measure(scenario, width)
    assert not order_violations(m), order_violations(m)
    assert not budget_violations(m), budget_violations(m)


@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", (390, 1280))
def test_missing_data_wording_no_zero_no_leak(measure, scenario, width):
    m = measure(scenario, width)
    assert not missing_violations(m, scenario), (missing_violations(m, scenario), m["chipTexts"])


@pytest.mark.parametrize("width", _WIDTHS)
def test_card_containers_hold_their_controls_and_use_token_values(measure, width):
    m = measure("normal", width)
    assert not container_violations(m), container_violations(m)


@pytest.mark.parametrize("width", _WIDTHS)
def test_secondary_cards_are_top_aligned_and_not_forced_equal_height(measure, width):
    m = measure("normal", width)
    assert not secondary_alignment_violations(m, width), (secondary_alignment_violations(m, width), m["frames"]["vix"], m["frames"]["rates"])


@pytest.mark.parametrize("width", _WIDTHS)
def test_tokens_are_applied_and_no_legacy_theme_colour_remains(measure, width):
    m = measure("normal", width)
    assert not token_violations(m), token_violations(m)


@pytest.mark.parametrize("width", _WIDTHS)
def test_radio_options_are_pills_with_touch_size_bold_selection_and_token_colours(measure, width):
    m = measure("normal", width)
    assert not pill_violations(m), pill_violations(m)


@pytest.mark.parametrize("width", _WIDTHS)
def test_sparks_fill_card_width_with_round_end_dot_and_primary_chart_is_centered_on_desktop(measure, width):
    m = measure("normal", width)
    assert not spark_violations(m), (spark_violations(m), m["sparks"])
    assert not centered_violations(m, width), centered_violations(m, width)


@pytest.mark.parametrize("scenario", ("tw_missing", "us_failed"))
@pytest.mark.parametrize("width", _WIDTHS)
def test_pills_and_sparks_hold_in_degraded_scenarios(measure, scenario, width):
    m = measure(scenario, width)
    assert not pill_violations(m), pill_violations(m)
    assert not spark_violations(m), spark_violations(m)
    assert not centered_violations(m, width)


@pytest.mark.parametrize("scenario", _SCENARIOS)
@pytest.mark.parametrize("width", (390, 1280))
def test_containers_and_tokens_hold_in_degraded_scenarios(measure, scenario, width):
    m = measure(scenario, width)
    assert not container_violations(m), container_violations(m)
    assert not token_violations(m), token_violations(m)
    assert not secondary_alignment_violations(m, width)


def _radio_option(page, group_label, option_text):
    return page.locator(f'[data-testid="stMain"] [data-testid="stRadioGroup"][aria-label="{group_label}"] label[data-testid="stRadioOption"]',
                        has_text=option_text).first


@pytest.mark.parametrize("width", (390, 1280))
def test_native_radio_controls_inside_cards_are_operable_and_keep_state(base_and_browser, width):
    """原生單選放進卡內後仍可操作（滑鼠與鍵盤）、狀態跨重跑保留、仍在原本那張卡內。"""
    base, browser, _ = base_and_browser
    ctx, page = _open(browser, base, "normal", width)
    try:
        aria = lambda: page.locator('[data-testid="stMain"] svg.uv3-chart').first.get_attribute("aria-label")
        assert "1Y" in aria()
        _radio_option(page, "期間", "3M").click()
        page.wait_for_function("() => document.querySelector('[data-testid=\"stMain\"] svg.uv3-chart').getAttribute('aria-label').includes('3M')", timeout=20000)
        h3_before = page.locator('[data-testid="stMain"] h3').first.inner_text()
        _radio_option(page, "檢視", "VIX").click()
        page.wait_for_function("(t) => document.querySelector('[data-testid=\"stMain\"] h3').innerText !== t", arg=h3_before, timeout=20000)
        assert "3M" in aria(), "切換檢視後，期間選擇應保留（狀態跨重跑）"
        rates = page.locator('[data-testid="stMain"] .st-key-uv3-card-sec-rates')
        _radio_option(page, "利率與信用", "信用利差").click()
        page.wait_for_function("() => document.querySelector('[data-testid=\"stMain\"] .st-key-uv3-card-sec-rates h4').innerText.includes('信用利差')", timeout=20000)
        assert rates.locator('[data-testid="stRadioGroup"][aria-label="利率與信用"]').count() == 1, "切換後利率單選仍在利率卡內"
        # 鍵盤：焦點在利率單選的已選項時，方向鍵右移到下一項（原生可及性行為不因入卡而失效）
        rates.locator('input[type="radio"]:checked').focus()
        page.keyboard.press("ArrowRight")
        page.wait_for_function("() => document.querySelector('[data-testid=\"stMain\"] .st-key-uv3-card-sec-rates h4').innerText.includes('政策利率')", timeout=20000)
        # 切回「比較」後（D1：Secondary 不複製 Primary，VIX 檢視時 VIX 卡本來就不出現），整頁容器／溢出／token 仍然成立
        _radio_option(page, "檢視", "比較").click()
        page.wait_for_function("(t) => document.querySelector('[data-testid=\"stMain\"] h3').innerText === t", arg=h3_before, timeout=20000)
        page.wait_for_selector('.st-key-uv3-card-sec-vix', timeout=20000)
        m = page.evaluate(_MEASURE)
        assert not container_violations(m) and not overflow_violations(m) and not token_violations(m), (
            container_violations(m), overflow_violations(m), token_violations(m))
    finally:
        ctx.close()


_FOCUS_JS = r"""
() => {   // 鍵盤焦點落在「期間」已選項時，量它的 label（pill）外框
  const g = document.querySelector('[data-testid="stMain"] [data-testid="stRadioGroup"][aria-label="期間"]');
  const input = g.querySelector('input[type="radio"]:checked');
  const label = input.closest('label'), s = getComputedStyle(label);
  return {focused: document.activeElement === input, outlineStyle: s.outlineStyle, outlineWidth: s.outlineWidth, outlineColor: s.outlineColor};
}
"""


def focus_violations(f):
    want = _rgb(_tok("color.pill.focus"))
    bad = []
    if not f["focused"]:
        bad.append(("鍵盤焦點沒有落在單選的 input 上",))
    if f["outlineStyle"] != "solid" or f["outlineWidth"] != "2px" or f["outlineColor"] != want:
        bad.append(("鍵盤焦點環不是 2px solid color.pill.focus", f["outlineStyle"], f["outlineWidth"], f["outlineColor"], want))
    return bad


def _focused_period(page):
    page.locator('[data-testid="stMain"] [data-testid="stRadioGroup"][aria-label="期間"] input[type="radio"]:checked').focus()
    page.keyboard.press("Shift+Tab")   # 先離開再以鍵盤回來，讓瀏覽器把焦點標成 focus-visible（鍵盤來源）
    page.keyboard.press("Tab")
    page.wait_for_timeout(200)
    return page.evaluate(_FOCUS_JS)


@pytest.mark.parametrize("width", (390, 1280))
def test_keyboard_focus_ring_on_pill_is_visible(base_and_browser, width):
    base, browser, _ = base_and_browser
    ctx, page = _open(browser, base, "normal", width)
    try:
        f = _focused_period(page)
        assert not focus_violations(f), (focus_violations(f), f)
    finally:
        ctx.close()


# ───────────────────────── 變異驗證（負控；只在測試內對頁面注入，不改 production） ─────────────────────────

def _mutated(base_and_browser, scenario, width, *, css=None, js=None):
    base, browser, _ = base_and_browser
    ctx, page = _open(browser, base, scenario, width)
    try:
        if css:
            page.add_style_tag(content=css)
        if js:
            page.evaluate(js)
        page.wait_for_timeout(300)
        m = page.evaluate(_MEASURE)
        m["hit"] = page.evaluate(_HIT)
        return m
    finally:
        ctx.close()


def test_mutation_forced_wide_card_is_flagged_as_overflow(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css=".uv3-card{min-width:900px !important}")
    assert overflow_violations(m)


def test_mutation_hidden_chart_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css="svg.uv3-chart{display:none !important}")
    assert chart_violations(m)


def test_mutation_zero_size_chart_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css="svg.uv3-chart{width:0 !important;height:0 !important}")
    assert any("零尺寸" in v[0] or "不可見" in v[0] for v in chart_violations(m))


def test_mutation_missing_chart_dom_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, js="document.querySelector('svg.uv3-chart').remove()")
    assert chart_violations(m) == [("主圖不存在",)]


def test_mutation_overlay_covering_chart_is_flagged(base_and_browser):
    js = """() => { const d = document.createElement('div'); d.style.cssText = 'position:fixed;inset:0;z-index:99999;background:#fff';
      document.body.appendChild(d); }"""
    m = _mutated(base_and_browser, "normal", 390, js=js)
    assert m["hit"]["covered"] is True


def test_mutation_shrunk_top_nav_cells_are_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390,
                 css=".st-key-uv3-top-nav a[data-testid='stPageLink-NavLink'],.st-key-uv3-top-nav .uv3-tn-disabled{max-height:30px !important;min-height:0 !important}")
    assert any("<48px" in v[0] for v in nav_violations(m, 390))


def test_mutation_unequal_five_cells_nav_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css=".st-key-uv3-top-nav > div:first-child{flex:3 1 0 !important}")
    assert any("不等寬" in v[0] for v in nav_violations(m, 390)), nav_violations(m, 390)


def test_mutation_reordered_blocks_are_flagged(base_and_browser):
    js = """() => { const box = e => e.closest('[data-testid="stElementContainer"]') || e;
      const vix = document.querySelector('.st-key-uv3-card-sec-vix'), h3 = document.querySelector('[data-testid="stMain"] h3');
      box(h3).before(box(vix)); }"""
    m = _mutated(base_and_browser, "normal", 390, js=js)
    assert any("區塊順序" in v[0] for v in order_violations(m))


def test_mutation_extra_chips_blow_first_screen_budget(base_and_browser):
    js = """() => { const row = document.querySelector('[data-field="attention"]');
      for (let i = 0; i < 4; i++) { const s = document.createElement('span'); s.className = 'uv3-chip'; s.textContent = '⬜ 假chip'; row.appendChild(s); } }"""
    m = _mutated(base_and_browser, "normal", 390, js=js)
    assert any("超過 5" in v[0] for v in budget_violations(m))


def test_mutation_missing_series_drawn_as_zero_or_extra_path_is_flagged(base_and_browser):
    js = """() => { const svg = document.querySelector('svg.uv3-chart'); svg.appendChild(svg.querySelector('path').cloneNode(true));
      const row = document.querySelector('[data-testid="stMain"]').innerText; document.querySelectorAll('.uv3-evidence').forEach(e => {
        if (e.innerText.includes('資料未備')) e.textContent = '台股 近1Y 0.00%'; }); }"""
    m = _mutated(base_and_browser, "tw_missing", 390, js=js)
    msgs = [v[0] for v in missing_violations(m, "tw_missing")]
    assert any("序列數" in s for s in msgs)
    assert any("0%" in s or "沒有以" in s for s in msgs)


def test_mutation_leaked_failure_text_and_nan_are_flagged(base_and_browser):
    js = """() => { const n = document.createElement('div'); n.className = 'uv3-row'; n.textContent = 'HTTP 429 secret-token-abc123 NaN';
      document.querySelector('[data-testid="stMain"] h1').after(n); }"""
    m = _mutated(base_and_browser, "us_failed", 390, js=js)
    msgs = [v[0] for v in missing_violations(m, "us_failed")]
    assert "取數失敗原文外漏" in msgs and "畫面出現不可呈現的 token" in msgs


def test_mutation_rates_radio_moved_out_of_card_is_flagged(base_and_browser):
    js = """() => { const r = [...document.querySelectorAll('[data-testid="stMain"] [data-testid="stRadio"]')]
        .find(x => x.querySelector('[data-testid="stRadioGroup"]').getAttribute('aria-label') === '利率與信用');
      document.querySelector('.st-key-uv3-card-sec-rates').before(r.closest('[data-testid="stElementContainer"]')); }"""
    m = _mutated(base_and_browser, "normal", 1280, js=js)
    assert any(v[0] == "元素不在應在的卡內" and v[1] == "ratesRadioInRatesFrame" for v in container_violations(m))


def test_mutation_secondary_cards_pushed_off_alignment_or_forced_equal_are_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 1280, css=".st-key-uv3-card-sec-rates{margin-top:84px !important}")
    assert any("沒有對齊" in v[0] for v in secondary_alignment_violations(m, 1280))
    m = _mutated(base_and_browser, "normal", 1280,
                 css=".st-key-uv3-card-sec-vix,.st-key-uv3-card-sec-rates{min-height:400px !important}")
    assert any("強制等高" in v[0] for v in secondary_alignment_violations(m, 1280))


def test_mutation_chart_wider_than_720_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 1280, css="svg.uv3-chart{max-width:none !important}")
    assert any("720" in v[0] for v in chart_violations(m))


def test_mutation_stripped_card_frame_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css=".st-key-uv3-card-chart{border:0 !important;border-radius:0 !important}")
    assert any(v[0] == "卡片外框與 token 不符" and v[1] == "chart" for v in container_violations(m))


def test_mutation_legacy_theme_colours_are_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css=".stApp{background:#f6f8fa !important}")
    assert any(v[0] in ("token 未套用", "殘留舊 theme 色") for v in token_violations(m))
    m = _mutated(base_and_browser, "normal", 390,
                 css='html body [data-testid="stMain"] label[data-testid="stRadioOption"][data-selected="true"]{background-color:#1f6feb !important}')
    assert any(v[0] == "token 未套用" and v[1] == "radioSelectedBg" for v in token_violations(m))


def test_mutation_extra_top_spacing_pushing_chart_below_baseline_is_flagged(base_and_browser):
    m = _mutated(base_and_browser, "normal", 390, css=".st-key-uv3-card-summary{margin-bottom:40px !important}")
    assert any("低於改前基線" in v[0] for v in firstscreen_violations(m, 390))
    m = _mutated(base_and_browser, "normal", 390, css="html body svg.uv3-chart{width:100% !important;margin-left:0 !important}")
    assert any("354" in v[0] for v in firstscreen_violations(m, 390))


def test_mutation_pill_visual_regressions_are_flagged(base_and_browser):
    """視覺批 1 負控：縮小觸控高度、取消粗體、顯示圓點、選取底換成舊色、拿掉置中、迷你圖縮回 160px、把末點壓扁成橢圓、拿掉焦點環。"""
    opt = 'html body [data-testid="stMain"] label[data-testid="stRadioOption"]'
    m = _mutated(base_and_browser, "normal", 390, css=f"{opt}{{min-height:30px !important;height:30px !important}}")
    assert any("低於觸控下限" in v[0] for v in pill_violations(m))
    m = _mutated(base_and_browser, "normal", 390, css=f'{opt}[data-selected="true"],{opt}[data-selected="true"] *{{font-weight:400 !important}}')
    assert any("不是粗體" in v[0] for v in pill_violations(m))
    m = _mutated(base_and_browser, "normal", 390, css=f"{opt} > div > div > div:first-child{{display:block !important}}")
    assert any("圓點沒有隱藏" in v[0] for v in pill_violations(m))
    m = _mutated(base_and_browser, "normal", 390, css=f'{opt}[data-selected="true"]{{background:#1f6feb !important}}')
    assert any("單選色與 token 不符" in v[0] for v in pill_violations(m))
    m = _mutated(base_and_browser, "normal", 390, css=f"{opt} p{{color:#1f6feb !important}}")
    assert any("未選項文字色" in v[0] for v in pill_violations(m))
    m = _mutated(base_and_browser, "normal", 1280, css="html body svg.uv3-chart{margin-left:0 !important;margin-right:0 !important}")
    assert centered_violations(m, 1280)
    m = _mutated(base_and_browser, "normal", 1280, css="html body svg.uv3-spark{width:160px !important}")
    assert any("沒有對齊卡內寬" in v[0] for v in spark_violations(m))
    m = _mutated(base_and_browser, "normal", 1280, css="html body svg.uv3-spark{height:40px !important;width:100% !important}",
                 js="() => document.querySelectorAll('svg.uv3-spark').forEach(s => s.setAttribute('preserveAspectRatio', 'none'))")
    assert any("末點不是正圓" in v[0] for v in spark_violations(m))


_STRIP_HAS_JS = r"""
() => {   // 模擬不支援 :has() 的瀏覽器：從所有樣式表刪掉含 ':has(' 的規則
  let n = 0;
  for (const sh of document.styleSheets) { let rules; try { rules = sh.cssRules; } catch (e) { continue; }
    for (let i = rules.length - 1; i >= 0; i--) { if (rules[i].selectorText && rules[i].selectorText.includes(':has(')) { sh.deleteRule(i); n++; } } }
  return n;
}
"""


@pytest.mark.parametrize("width", (390, 1280))
def test_keyboard_focus_ring_survives_without_has_support_via_data_focus_visible(base_and_browser, width):
    """S1：Streamlit（react-aria）在鍵盤聚焦時於 label 加 data-focus-visible="true"；拿掉所有 :has() 規則後焦點環仍在。"""
    base, browser, _ = base_and_browser
    ctx, page = _open(browser, base, "normal", width)
    try:
        assert page.evaluate(_STRIP_HAS_JS) >= 1, "找不到 :has() 規則可移除（守衛本身失效）"
        f = _focused_period(page)
        assert not focus_violations(f), (focus_violations(f), f)
        attr = page.evaluate("""() => document.querySelector('[data-testid="stMain"] [data-testid="stRadioGroup"][aria-label="期間"] input:checked').closest('label').getAttribute('data-focus-visible')""")
        assert attr == "true", "Streamlit 內部屬性 data-focus-visible 不見了（升版改 DOM？）：備援焦點環已失效"
    finally:
        ctx.close()


def test_mutation_removed_focus_ring_is_flagged(base_and_browser):
    base, browser, _ = base_and_browser
    ctx, page = _open(browser, base, "normal", 390)
    try:
        page.add_style_tag(content='html body [data-testid="stMain"] label[data-testid="stRadioOption"]{outline:none !important}')
        assert any("焦點環" in v[0] for v in focus_violations(_focused_period(page)))
    finally:
        ctx.close()


def test_mutation_shell_aux_text_back_to_12px_or_taller_status_bar_is_flagged(base_and_browser):
    """視覺批 2 負控：輔助字退回 12px、Status Bar 行高放大（吃首屏）、側欄註記退回 12px、主導覽字級被縮小。負控全在記憶體內現編。"""
    m = _mutated(base_and_browser, "normal", 390, css="html body .uv3-statusbar{font-size:12px !important}")
    assert any(v[0] == "輔助字不是 type.caption" and v[1] == "statusBar" for v in aux_font_violations(m, 390))
    m = _mutated(base_and_browser, "normal", 390, css="html body .uv3-footer{font-size:12px !important}")
    assert any(v[0] == "輔助字不是 type.caption" and v[1] == "footer" for v in aux_font_violations(m, 390))
    m = _mutated(base_and_browser, "normal", 390, css="html body .uv3-statusbar{line-height:1.5 !important}")
    assert any("Status Bar 高度" in v[0] for v in aux_font_violations(m, 390)), aux_font_violations(m, 390)
    m = _mutated(base_and_browser, "normal", 1280, css="html body .uv3-cta-note,html body .uv3-nav-disabled .uv3-nav-soon{font-size:12px !important}")
    assert {v[1] for v in aux_font_violations(m, 1280) if v[0] == "輔助字不是 type.caption"} == {"sideSoon", "cta"}
    m = _mutated(base_and_browser, "normal", 390,
                 css='html body .st-key-uv3-top-nav a[data-testid="stPageLink-NavLink"] p{font-size:11px !important}')
    assert any(v[0] == "頁首導覽字級被縮小" and v[1] == "topNavP" for v in top_nav_font_violations(m, 390))
    m = _mutated(base_and_browser, "normal", 390, css="html body .uv3-tn-disabled{font-size:11px !important}")
    assert any(v[0] == "頁首導覽字級被縮小" and v[1] == "topNavDisabled" for v in top_nav_font_violations(m, 390))


def test_mutation_status_rows_breaking_inside_date_or_label_are_flagged(base_and_browser):
    """視覺批 2 負控：拿掉 keep-all／單位包裝後，390 的狀態列會在「資料日」或日期中折行（改前實測就是這樣）→ 判定函式要報。"""
    css = ".uv3-status-row{word-break:normal !important;text-wrap:wrap !important}.uv3-unit{display:inline !important}"
    s = _status_rows(base_and_browser, "normal", 390, css=css)
    msgs = [v[0] for v in status_row_violations(s, 390)]
    assert "日期在字中折行" in msgs or "「資料日」在字中折行" in msgs, (msgs, s["rows"])
    s = _status_rows(base_and_browser, "normal", 390, css=".uv3-unit{display:inline-block !important;min-width:420px !important}")
    assert any(v[0] in ("狀態列橫向溢出", "展開後整頁橫向溢出") for v in status_row_violations(s, 390)), s
