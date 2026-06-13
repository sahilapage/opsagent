import { chromium } from 'playwright';

const browser = await chromium.launch({ headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'] });
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 860 });

await page.goto('http://localhost:5175/', { waitUntil: 'networkidle', timeout: 15000 });
await page.waitForSelector('text=OpsAgent', { timeout: 10000 });
await page.waitForTimeout(600);

// -- Chat: send a message --
const input = page.locator('textarea');
await input.fill('What is the capital of Japan and what is 12 * 8?');
await page.keyboard.press('Enter');
await page.waitForTimeout(9000);
await page.screenshot({ path: '/tmp/live_chat.png' });
console.log('chat done');

// -- Send another to show conversation history --
await input.fill('Now run Python code to show the fibonacci sequence');
await page.keyboard.press('Enter');
await page.waitForTimeout(10000);
await page.screenshot({ path: '/tmp/live_chat2.png' });
console.log('chat2 done');

// -- Settings --
await page.getByText('Settings').first().click();
await page.waitForTimeout(1200);
await page.screenshot({ path: '/tmp/live_settings.png' });
console.log('settings done');

// -- Memory --
await page.getByText('Memory').first().click();
await page.waitForTimeout(1200);
await page.screenshot({ path: '/tmp/live_memory.png' });
console.log('memory done');

// -- Knowledge Base: Collections tab --
await page.getByText('Knowledge Base').first().click();
await page.waitForTimeout(300);
await page.getByText('Collections').first().click();
await page.waitForTimeout(300);
await page.getByText('Refresh').first().click();
await page.waitForTimeout(1500);
await page.screenshot({ path: '/tmp/live_ingest.png' });
console.log('ingest done');

await browser.close();
console.log('ALL DONE');
