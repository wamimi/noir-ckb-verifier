// Opens the spike page in headless Chromium (Playwright), prints the results as JSON and, with
// a third argument, writes them to that file. Exits non-zero if the page reported an error,
// any check failed, or the page threw.
// Usage: node measure.cjs http://localhost:8765/ [runs] [results.json]
const { chromium } = require("playwright");
const fs = require("fs");
(async () => {
  const [url, runs = "3", out] = process.argv.slice(2);
  const browser = await chromium.launch();
  const errors = [];
  try {
    const page = await browser.newPage();
    page.on("pageerror", (e) => { errors.push(e.message); console.error("page error:", e.message); });
    await page.goto(`${url}?runs=${runs}`);
    await page.waitForFunction(() => window.__results, null, { timeout: 60 * 60 * 1000 });
    const results = await page.evaluate(() => window.__results);
    results.browserVersion = browser.version();
    if (errors.length) results.pageErrors = errors;
    const text = JSON.stringify(results, null, 2);
    console.log(text);
    if (out) fs.writeFileSync(out, text + "\n");
    if (results.error || results.ok !== true || errors.length) {
      console.error(`FAILED: ${results.error ?? (errors.length ? "page errors" : "a check failed; see ok fields")}`);
      process.exitCode = 1;
    }
  } finally {
    await browser.close();
  }
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
