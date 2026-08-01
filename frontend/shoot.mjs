import { chromium } from "playwright";

const out = process.argv[2];
const scheme = process.argv[3] || "light";
const clipTo = process.argv[4];

const browser = await chromium.launch();
const page = await browser.newPage({
  viewport: { width: 1280, height: 1400 },
  colorScheme: scheme,
  deviceScaleFactor: 2,
});
await page.goto("http://localhost:3000/preview", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);

if (clipTo) {
  const el = await page.locator(clipTo).first();
  await el.scrollIntoViewIfNeeded();
  await page.waitForTimeout(500);
  await el.screenshot({ path: out });
} else {
  await page.screenshot({ path: out, fullPage: true });
}

// Horizontal overflow check: the page body must never scroll sideways.
const overflow = await page.evaluate(() => ({
  scrollW: document.documentElement.scrollWidth,
  clientW: document.documentElement.clientWidth,
}));
console.log(JSON.stringify({ scheme, ...overflow, overflows: overflow.scrollW > overflow.clientW }));

await browser.close();
