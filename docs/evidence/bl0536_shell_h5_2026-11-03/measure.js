// H5／Shell 量測（Playwright chromium）。用法：node measure.js <scenario> <width> <height> <out.png> [scroll] [viewLabel]
// viewLabel（選填）：點選主圖檢視的 radio 標籤文字（例：美10Y），量該檢視的首屏。
// 首屏名額計法（docs/v2/81 第 10.2 節）：頁級 chip（.uv3-chip，含 Status Bar 與側欄內的）＋頁級核心數字（.uv3-evidence，一格一個；格內以狀態 chip 取代數字時只算一格，不重複計 chip）。
// 資料是 launch_injected_data.py 注入的人造資料，**不是真實行情**；圖底部有黃字標示。
const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const [,, scenario, w, h, out, scroll, viewLabel] = process.argv;
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: +w, height: +h }, deviceScaleFactor: 2 });
  const p = await ctx.newPage();
  await p.goto(`http://localhost:${process.env.PORT || 8599}/?scenario=${scenario}`, { waitUntil: 'networkidle' });
  await p.waitForSelector('[data-field="market_state"]', { state: 'attached', timeout: 60000 });
  await p.waitForTimeout(1500);
  if (viewLabel) { await p.getByText(viewLabel, { exact: true }).first().click(); await p.waitForTimeout(2500); }
  const m = await p.evaluate((vh) => {
    const rect = (e) => { if (!e) return null; const r = e.getBoundingClientRect(); return { top: Math.round(r.top), bottom: Math.round(r.bottom), left: Math.round(r.left), right: Math.round(r.right), w: Math.round(r.width), h: Math.round(r.height) }; };
    const vis = (e) => !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().height > 0;
    const q = (s) => document.querySelector(s);
    const nav = q('.st-key-uv3-bottom-nav'), side = q('[data-testid="stSidebar"]');
    const navTop = vis(nav) ? nav.getBoundingClientRect().top : vh;
    const field = (name) => rect(q(`[data-field="${name}"]`));
    const chart = q('.uv3-chart');
    const body = [...document.querySelectorAll('.uv3-chip')].filter(e => !e.closest('.uv3-statusbar') && !e.closest('[data-testid="stSidebar"]') && e.getBoundingClientRect().top < navTop);
    const nums = [...document.querySelectorAll('.uv3-evidence')].filter(e => e.getBoundingClientRect().top < navTop);
    const inView = (e) => vis(e) && e.getBoundingClientRect().top < navTop;
    const allChips = [...document.querySelectorAll('.uv3-chip')].filter(inView);          // 含 Status Bar、側欄
    const standalone = allChips.filter(e => !e.closest('.uv3-evidence'));                  // 不在核心數字格內的 chip
    const sbChips = allChips.filter(e => e.closest('.uv3-statusbar') || e.closest('[data-testid="stSidebar"]')).length;
    const summary = q('[data-summary="series-status"]');
    const warnTexts = [...nums.map(e => e.innerText), summary ? summary.innerText : ''].join(' ');
    const slots = standalone.length + nums.length;
    return {
      scrollWidth: document.documentElement.scrollWidth, clientWidth: document.documentElement.clientWidth,
      bottomNavVisible: vis(nav), sidebarVisible: vis(side), bottomNav: rect(nav), sidebar: rect(side),
      navLinks: [...document.querySelectorAll(vis(nav) ? '.st-key-uv3-bottom-nav a, .st-key-uv3-bottom-nav [aria-disabled]' : '[data-testid="stSidebar"] a, [data-testid="stSidebar"] [aria-disabled]')].map(e => ({ text: e.innerText.replace(/\n/g, '|'), disabled: e.getAttribute('aria-disabled') === 'true', h: Math.round(e.getBoundingClientRect().height) })),
      statusBar: rect(q('.uv3-statusbar')), statusText: (q('.uv3-statusbar') || {}).innerText,
      marketState: field('market_state'), attention: field('attention'), chart: rect(chart),
      firstScreenVisibleHeight: Math.round(navTop),
      chipsInFirstScreen: body.length, evidenceNumbersInFirstScreen: nums.length,
      firstScreenSlots: slots, standaloneChips: standalone.length, evidenceSlots: nums.length, chromeChips: sbChips,
      seriesStatusSummaryVisible: inView(summary), visibleWarning: /資料未備|取數失敗|尚未設定|缺資料/.test(warnTexts),
      main: rect(q('.stMainBlockContainer')),
    };
  }, +h);
  if (scroll) {
    await p.evaluate(() => { const m = document.querySelector('[data-testid="stMain"]'); (m || window).scrollTo(0, 1e6); }); await p.waitForTimeout(800);
    m.afterScroll = await p.evaluate(() => { const f = document.querySelector('[data-shell="footer"]'); const n = document.querySelector('.st-key-uv3-bottom-nav'); const fr = f && f.getBoundingClientRect(); const nr = n && getComputedStyle(n).display !== 'none' ? n.getBoundingClientRect() : null; return { footerBottom: fr && Math.round(fr.bottom), navTop: nr && Math.round(nr.top), scrollY: Math.round((document.querySelector('[data-testid="stMain"]') || document.documentElement).scrollTop), footerClearOfNav: fr && (nr ? fr.bottom <= nr.top : true) }; });
    await p.evaluate(() => { const m = document.querySelector('[data-testid="stMain"]'); (m || window).scrollTo(0, 0); }); await p.waitForTimeout(300);
  }
  await p.evaluate(() => { const d = document.createElement('div'); d.textContent = 'INJECTED TEST DATA — NOT REAL MARKET DATA'; d.style.cssText = 'position:fixed;top:0;left:0;right:0;z-index:2147483647;background:#000;color:#ff0;font:10px monospace;text-align:center;padding:1px'; document.documentElement.appendChild(d); });
  console.log(JSON.stringify({ scenario, viewport: `${w}x${h}`, ...m }));
  await p.screenshot({ path: out });
  await b.close();
})();
