// Screenshot walk-through of the web admin against the seeded demo, at 1440 and 390 px.
//   MD_TOTP=<secret> ADMIN_TOTP=<secret> node e2e/screens-admin.mjs [outDir]
import { chromium } from '@playwright/test';
import { createHmac } from 'node:crypto';
import { mkdirSync } from 'node:fs';

const out = process.argv[2] ?? 'docs/screens/phase1';
const base = process.env.ADMIN_URL ?? 'http://localhost:5173';
const PASSWORD = process.env.SEED_PASSWORD ?? 'sunrise-demo-2026';
mkdirSync(out, { recursive: true });

function totp(secret) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567';
  let bits = '';
  for (const c of secret.replace(/=+$/, ''))
    bits += alphabet.indexOf(c).toString(2).padStart(5, '0');
  const key = Buffer.from(bits.match(/.{8}/g).map((b) => parseInt(b, 2)));
  const counter = Buffer.alloc(8);
  counter.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000)));
  const h = createHmac('sha1', key).update(counter).digest();
  const o = h[h.length - 1] & 0xf;
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1_000_000).padStart(6, '0');
}

async function signIn(page, email, secret) {
  await page.goto(base);
  await page.locator('input').nth(0).fill('SUNRISE');
  await page.locator('input[type=email]').fill(email);
  await page.locator('input[type=password]').fill(PASSWORD);
  await page.locator('button[type=submit]').click();
  if (secret) {
    await page.locator('input[autocomplete=one-time-code]').fill(totp(secret));
    await page.locator('button[type=submit]').click();
  }
  await page.waitForSelector('nav[aria-label=Main]', { timeout: 15000 });
  await page.waitForTimeout(1200);
}

const browser = await chromium.launch();
for (const [w, h, tag] of [
  [1440, 900, 'desktop'],
  [390, 844, 'mobile'],
]) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  await ctx.addInitScript(() => localStorage.setItem('oglos.lang', 'en'));
  const page = await ctx.newPage();
  const shot = (name) =>
    page.screenshot({ path: `${out}/admin-${tag}-${name}.png`, fullPage: true });
  if (tag === 'desktop') {
    await page.goto(base);
    await page.waitForTimeout(800);
    await shot('01-login');
  }
  await signIn(page, 'md@sunrise.example.org', process.env.MD_TOTP);
  await shot('02-today');
  const tile = page.locator('button[aria-pressed]').first();
  if (await tile.count()) {
    await tile.click();
    await page.waitForTimeout(500);
    await shot('03-today-desk');
  }
  await ctx.close();

  if (tag === 'desktop') {
    const c2 = await browser.newContext({ viewport: { width: w, height: h } });
    await c2.addInitScript(() => localStorage.setItem('oglos.lang', 'en'));
    const p2 = await c2.newPage();
    await signIn(p2, 'supervisor@sunrise.example.org');
    await p2.goto(`${base}/approvals`);
    await p2.waitForTimeout(2000);
    await p2.screenshot({ path: `${out}/admin-desktop-04-approvals.png`, fullPage: true });
    await p2.goto(`${base}/roster`);
    await p2.waitForTimeout(1500);
    await p2.screenshot({ path: `${out}/admin-desktop-05-roster.png`, fullPage: true });
    await c2.close();

    const c3 = await browser.newContext({ viewport: { width: w, height: h } });
    await c3.addInitScript(() => localStorage.setItem('oglos.lang', 'en'));
    const p3 = await c3.newPage();
    await signIn(p3, 'admin@sunrise.example.org', process.env.ADMIN_TOTP);
    for (const [path, name] of [
      ['/staff', '06-staff'],
      ['/entrance-qr', '07-entrance-qr'],
    ]) {
      await p3.goto(`${base}${path}`);
      await p3.waitForTimeout(1500);
      await p3.screenshot({ path: `${out}/admin-desktop-${name}.png`, fullPage: true });
    }
    await c3.close();
  }
}
await browser.close();
console.log(`screens -> ${out}`);
