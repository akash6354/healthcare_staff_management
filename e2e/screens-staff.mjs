// Screenshot walk-through of the staff app against the seeded demo (CLAUDE.md screen-critique loop).
//   STAFF_DEVICE_KEY=<from make seed> node e2e/screens-staff.mjs [outDir]
import { chromium } from '@playwright/test';
import { mkdirSync } from 'node:fs';

const out = process.argv[2] ?? 'docs/screens/phase1';
const base = process.env.STAFF_URL ?? 'http://localhost:5174';
const key = process.env.STAFF_DEVICE_KEY;
const lang = process.env.STAFF_LANG ?? 'en';
mkdirSync(out, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2,
});
await ctx.addInitScript((l) => localStorage.setItem('oglos.lang', l), lang);
const page = await ctx.newPage();
const shot = (name) =>
  page.screenshot({ path: `${out}/staff-${lang}-${name}.png`, fullPage: true });

await page.goto(base);
await page
  .waitForSelector('text=SUNRISE, text=Work email, form', { timeout: 15000 })
  .catch(() => {});
await shot('01-login-email');

if (key) {
  await page.getByRole('button', { name: /shared phone|ಹಂಚಿಕೊಂಡ|साझा/ }).click();
  const inputs = page.locator('input');
  await inputs.nth(0).fill('SUNRISE');
  await inputs.nth(1).fill(key);
  await page.locator('form button[type=submit]').click();
  await page.locator('input').first().fill('HK-101');
  for (const d of '4826') await page.getByRole('button', { name: d, exact: true }).click();
  await shot('02-login-pin');
  await page.locator('main button.h-14').click();
  await page.waitForResponse((r) => r.url().includes('/notice/current'), { timeout: 15000 });
  await page.waitForTimeout(800);
  await shot('03-notice');
  const agree = page.locator('div.fixed button');
  if (await agree.count()) await agree.click();
  await page.waitForTimeout(1500);
  await shot('04-home');
  const open = page.locator('a[href^="/task/"]');
  if (await open.count()) {
    await open.first().click();
    await page.waitForTimeout(1500);
    await shot('05-task');
    if (process.env.STAFF_START) {
      await page.locator('div.fixed button').click();
      await page.waitForTimeout(1500);
      await shot('06-task-in-progress');
    }
  }
}
await browser.close();
console.log(`screens -> ${out}`);
