import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 860 });

page.on('console', m => console.log('CONSOLE', m.type(), m.text().slice(0,200)));
page.on('pageerror', e => console.error('JS ERR:', e.message.slice(0,200)));
page.on('response', r => {
  if (r.url().includes('localhost:8000') || r.url().includes('/api')) {
    console.log('RESPONSE', r.status(), r.url().slice(0,100));
  }
});
page.on('requestfailed', r => console.log('FAILED', r.url(), r.failure()?.errorText));

await page.goto('http://localhost:5174/', { waitUntil: 'networkidle', timeout: 15000 });
await page.waitForSelector('text=OpsAgent', { timeout: 10000 });
await page.waitForTimeout(500);

// Type and send
const input = page.locator('textarea');
await input.fill('Hello');
await page.keyboard.press('Enter');
await page.waitForTimeout(5000);

console.log('\nFinal messages in DOM:');
const msgs = await page.locator('[class]').allTextContents();
// Just show non-empty elements
msgs.filter(t => t.trim().length > 5).slice(0,5).forEach(t => console.log(' -', t.slice(0,100)));

await browser.close();
