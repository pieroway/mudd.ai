const { chromium } = require('/tests/node_modules/playwright');
(async () => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 940 }, deviceScaleFactor: 1.5 });
  await page.goto('file:///preview/overlapping-levels.svg');
  await page.screenshot({ path: '/preview/overlapping-levels.png' });
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
