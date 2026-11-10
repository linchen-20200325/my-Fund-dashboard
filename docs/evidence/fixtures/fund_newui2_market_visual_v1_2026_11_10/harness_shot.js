const { chromium } = require('/opt/node-tools/node_modules/playwright');
const fs = require('fs');
const OUT = process.argv[2]; const DSF = +(process.argv[3]||1);
const MEASURE = () => {
  const q = (s) => document.querySelector(s), r = (el) => { const b = el.getBoundingClientRect(); return {x:+b.x.toFixed(1), y:+b.y.toFixed(1), w:+b.width.toFixed(1), h:+b.height.toFixed(1)}; };
  const cs = (el, props) => { const c = getComputedStyle(el); const o = {}; props.forEach(p => o[p] = c[p]); return o; };
  const vw = document.documentElement.clientWidth, vh = window.innerHeight;
  const out = { vw, vh, docScrollW: document.documentElement.scrollWidth, hOverflow: document.documentElement.scrollWidth > vw };
  const app = q('[data-testid="stApp"]'); out.appBg = getComputedStyle(app).backgroundColor; out.appColor = getComputedStyle(app).color;
  const side = q('[data-testid="stSidebar"]'); out.sidebar = side ? { display: getComputedStyle(side).display, bg: getComputedStyle(side).backgroundColor, rect: r(side) } : null;
  const hdr = q('[data-testid="stHeader"]'); out.stHeader = hdr ? r(hdr) : null;
  const nav = q('.st-key-uv3-top-nav'); out.topNav = nav ? { display: getComputedStyle(nav).display, rect: nav.getBoundingClientRect().height ? r(nav) : null, bg: getComputedStyle(nav).backgroundColor } : null;
  if (nav && getComputedStyle(nav).display !== 'none') out.topNavCells = [...nav.querySelectorAll('a[data-testid="stPageLink-NavLink"], .uv3-tn-disabled')].map(r);
  const blk = q('.stMainBlockContainer, .block-container'); out.mainBlock = blk ? { rect: r(blk), pad: cs(blk, ['paddingLeft','paddingRight','paddingTop']), maxW: getComputedStyle(blk).maxWidth } : null;
  const h1 = q('h1'); out.h1 = h1 ? { rect: r(h1), font: cs(h1, ['fontSize','fontWeight']) } : null;
  const card = q('.uv3-card'); out.card = card ? { rect: r(card), style: cs(card, ['borderRadius','paddingTop','paddingLeft','marginBottom','borderTopWidth','borderTopColor','backgroundColor']) } : null;
  out.cards = [...document.querySelectorAll('.uv3-card')].map(c => ({k: c.dataset.card, ...r(c)}));
  const chip = q('.uv3-chip'); out.chip = chip ? { rect: r(chip), style: cs(chip, ['fontSize','borderRadius','backgroundColor','borderTopColor']) } : null;
  out.chipCountAll = document.querySelectorAll('.uv3-chip').length;
  const row = q('.uv3-row'); out.row = row ? cs(row, ['fontSize','lineHeight']) : null;
  const metric = q('.uv3-metric'); out.metric = metric ? cs(metric, ['fontSize']) : null;
  const note = q('.uv3-note'); out.note = note ? cs(note, ['fontSize']) : null;
  const svg = q('svg.uv3-chart'); if (svg) { const b = svg.getBoundingClientRect(); out.chart = { rect: r(svg), scale: +(b.width/360).toFixed(3), tickFontPx: +(11*b.width/360).toFixed(1), endLabelFontPx: +(12*b.width/360).toFixed(1), topInViewport: b.top < vh, visiblePxAboveFold: Math.max(0, Math.min(vh, b.bottom) - Math.max(0, b.top)) }; }
  const sp = q('svg.uv3-spark'); out.spark = sp ? r(sp) : null;
  out.firstScreenTexts = [...document.querySelectorAll('[data-testid="stMain"] .uv3-row, [data-testid="stMain"] h1, [data-testid="stMain"] h3, [data-testid="stMain"] .uv3-note, [data-testid="stMain"] svg.uv3-chart, [data-testid="stMain"] [data-testid="stRadio"]')].filter(e => { const b = e.getBoundingClientRect(); return b.top < vh && b.bottom > 0; }).map(e => (e.tagName + ' ' + (e.dataset.field||e.dataset.summary||e.className.baseVal||e.className||'') + ' @' + Math.round(e.getBoundingClientRect().top)).slice(0,70));
  // touch targets: interactive elements visible in doc
  const tt = [...document.querySelectorAll('a, button, input, [role="radio"], label[data-baseweb="radio"], summary, [data-testid="stExpander"] summary')].filter(e => { const b = e.getBoundingClientRect(); return b.width > 0 && b.height > 0; }).map(e => { const b = e.getBoundingClientRect(); return { tag: e.tagName, role: e.getAttribute('role')||'', txt: (e.innerText||e.getAttribute('aria-label')||'').trim().slice(0,18), w: +b.width.toFixed(1), h: +b.height.toFixed(1) }; });
  out.touchTargets = tt;
  out.touchBelow44 = tt.filter(x => x.h < 44 || x.w < 44).length; out.touchBelow48 = tt.filter(x => x.h < 48 || x.w < 48).length;
  out.docHeight = document.documentElement.scrollHeight;
  return out;
};
(async () => {
  const browser = await chromium.launch({ executablePath: process.env.CHROME, args: ['--no-sandbox'] });
  const res = {};
  for (const [name, w, h] of [['w390', 390, 844], ['w768', 768, 1024], ['w1280', 1280, 800]]) {
    for (const sc of ['normal', 'missing']) {
      const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: DSF });
      const page = await ctx.newPage();
      await page.goto(`http://localhost:8613/?scenario=${sc}`, { waitUntil: 'networkidle' });
      await page.waitForSelector('[data-field="market_state"]', { timeout: 60000 });
      await page.waitForTimeout(2500);
      res[`${name}_${sc}`] = await page.evaluate(MEASURE);
      await page.screenshot({ path: `${OUT}/${name}_${sc}_first.png`, fullPage: false });
      const H = await page.evaluate(() => { const m = document.querySelector('[data-testid="stMain"]'); return Math.max(m.scrollHeight, document.documentElement.scrollHeight); });
      await page.setViewportSize({ width: w, height: Math.ceil(H) + 8 });
      await page.waitForTimeout(1500);
      res[`${name}_${sc}`].fullPageH = H;
      res[`${name}_${sc}`].fullPageOverflowX = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
      await page.screenshot({ path: `${OUT}/${name}_${sc}_full.png`, fullPage: false });
      await ctx.close();
    }
  }
  fs.writeFileSync(`${OUT}/measure.json`, JSON.stringify(res, null, 1));
  await browser.close();
})();
