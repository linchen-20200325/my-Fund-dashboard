const { chromium } = require('/opt/node-tools/node_modules/playwright');
(async () => {
  const [,, scenario, w, h, out, extra] = process.argv;
  const browser = await chromium.launch();
  const ctx = await browser.newContext({ viewport: { width: +w, height: +h }, deviceScaleFactor: 2 });
  const page = await ctx.newPage();
  await page.goto(`http://localhost:8599/?scenario=${scenario}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('.uv3-chart, .uv3-row', { timeout: 60000 });
  await page.waitForTimeout(1500);
  if (extra === 'vix') { await page.getByText('VIX', { exact: true }).first().click(); await page.waitForTimeout(2500); }
  await page.evaluate(() => { const d = document.createElement('div'); d.textContent = 'INJECTED TEST DATA — NOT REAL MARKET DATA'; d.style.cssText = 'position:fixed;bottom:0;left:0;right:0;z-index:99999;background:#000;color:#ff0;font:11px monospace;text-align:center;padding:2px'; document.body.appendChild(d); });
  const overflow = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth }));
  console.log(scenario, w, JSON.stringify(overflow));
  await page.screenshot({ path: out, fullPage: false });
  await browser.close();
})();
