const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');

const target = path.resolve(process.argv[2] || 'milestones/m2-14-p2-control-arms-v1.html');
const out = path.resolve(process.argv[3] || 'milestones/evidence/m2-14');
fs.mkdirSync(out, { recursive: true });

(async () => {
  const browser = await chromium.launch({
    headless: true,
    executablePath: process.env.AIMETH_BROWSER_EXECUTABLE || chromium.executablePath(),
  });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1050 } });
    const external = [];
    const pageErrors = [];
    await context.route('**/*', route => {
      const url = route.request().url();
      if (/^https?:/.test(url)) { external.push(url); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => pageErrors.push(error.message));
    await page.goto(`file://${target}`);
    const viewports = [];
    for (const width of [1440, 768, 390]) {
      await page.setViewportSize({ width, height: 1050 });
      const layout = await page.evaluate(() => ({ width: innerWidth, scrollWidth: document.documentElement.scrollWidth }));
      if (layout.scrollWidth > layout.width + 1) throw new Error(`Horizontal overflow at ${width}px: ${JSON.stringify(layout)}`);
      viewports.push(layout);
      if (width === 1440) {
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: path.join(out, 'desktop.png'), fullPage: true });
      }
      if (width === 390) {
        await page.evaluate(() => scrollTo(0, 0));
        await page.screenshot({ path: path.join(out, 'narrow.png'), fullPage: true });
      }
    }
    const navLinks = await page.locator('nav a').evaluateAll(nodes => nodes.map(a => ({ href: a.getAttribute('href'), text: a.textContent.trim() })));
    for (const link of navLinks) {
      const targetId = link.href.slice(1);
      if (!targetId || !(await page.locator(`#${targetId}`).count())) throw new Error(`Broken navigation anchor ${link.href}`);
    }
    const armRows = await page.locator('#design tbody tr').count();
    if (armRows !== 7) throw new Error(`Expected seven arms, found ${armRows}`);
    await page.emulateMedia({ media: 'print' });
    const printNavDisplay = await page.locator('nav').evaluate(node => getComputedStyle(node).display);
    if (printNavDisplay !== 'none') throw new Error('Print layout did not hide the on-screen navigation');
    await page.evaluate(() => scrollTo(0, 0));
    await page.screenshot({ path: path.join(out, 'print.png'), fullPage: true });
    const noJs = await browser.newContext({ javaScriptEnabled: false, viewport: { width: 1000, height: 800 } });
    const fallback = await noJs.newPage();
    await fallback.goto(`file://${target}`);
    const core = await fallback.locator('body').innerText();
    if (!core.includes('当前解释边界') || !core.includes('independent') || !core.includes('pending')) {
      throw new Error('Core conclusion or method is missing without JavaScript');
    }
    if (external.length || pageErrors.length) throw new Error('Unexpected network dependency or page error');
    const result = {
      status: 'passed', report: target, browser: await browser.version(),
      viewports, navigation_anchors: navLinks.length, arm_rows: armRows,
      print_css: 'passed', no_javascript_core_content: 'passed',
      external_resource_requests: external, page_errors: pageErrors,
      screenshots: ['desktop.png', 'narrow.png', 'print.png'],
      scope: 'HTML presentation/accessibility checks only; no scientific outcome or cluster state validation.',
    };
    fs.writeFileSync(path.join(out, 'browser-qa.json'), JSON.stringify(result, null, 2) + '\n');
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
