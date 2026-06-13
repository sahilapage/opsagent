import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 860 });

await page.goto('http://localhost:5174/', { waitUntil: 'networkidle', timeout: 20000 });
await page.waitForSelector('text=OpsAgent', { timeout: 10000 });
await page.waitForTimeout(600);

// --- Chat: type and send a message ---
const input = page.locator('textarea');
await input.fill('What is the capital of Japan?');
await page.locator('button').filter({ hasText: '' }).last().click(); // send button
await page.waitForTimeout(6000); // wait for agent response
await page.screenshot({ path: '/tmp/live_chat.png' });
console.log('chat captured');

// --- Settings (to show health = connected) ---
await page.getByText('Settings').first().click();
await page.waitForTimeout(1000);
await page.screenshot({ path: '/tmp/live_settings.png' });
console.log('settings captured');

// --- Memory (to show auto-extracted memories) ---
await page.getByText('Memory').first().click();
await page.waitForTimeout(1200);
await page.screenshot({ path: '/tmp/live_memory.png' });
console.log('memory captured');

// --- Ingest (switch to Collections tab to show ingested data) ---
await page.getByText('Knowledge Base').first().click();
await page.waitForTimeout(300);
await page.getByText('Collections').first().click();
await page.waitForTimeout(200);
await page.getByText('Refresh').first().click();
await page.waitForTimeout(1500);
await page.screenshot({ path: '/tmp/live_ingest.png' });
console.log('ingest captured');

await browser.close();
console.log('ALL DONE');
