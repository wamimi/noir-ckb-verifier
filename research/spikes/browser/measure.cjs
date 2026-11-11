// Opens the spike page in headless Chromium (Playwright) and prints the results as JSON.
// Usage: node measure.cjs http://localhost:8765/ [runs]
const { chromium } = require("playwright");
(async () => {
  const [url, runs = "3"] = process.argv.slice(2);
  const browser = await chromium.launch();
  const page = await browser.newPage();
  page.on("pageerror", (e) => console.error("page error:", e.message));
  await page.goto(`${url}?runs=${runs}`);
  await page.waitForFunction(() => window.__results, null, { timeout: 30 * 60 * 1000 });
  console.log(JSON.stringify(await page.evaluate(() => window.__results), null, 2));
  await browser.close();
})();
