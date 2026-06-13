import { chromium } from 'playwright';

const browser = await chromium.launch({ 
  headless: true, 
  args: ['--no-sandbox', '--disable-dev-shm-usage']
});
const page = await browser.newPage();
await page.setViewportSize({ width: 1400, height: 860 });

page.on('pageerror', e => console.error('JS ERR:', e.message.slice(0,200)));

// Use vite preview (static build)
await page.goto('http://localhost:5174/', { waitUntil: 'networkidle', timeout: 20000 });
await page.waitForTimeout(1500);

const rootLen = await page.evaluate(() => document.getElementById('root')?.innerHTML?.length);
console.log('root innerHTML length:', rootLen);

await page.screenshot({ path: '/tmp/ss_chat.png' });
console.log('Chat captured');

// Nav buttons are all buttons in the sidebar (first child of root flex div)
const buttons = await page.locator('button').all();
console.log('Total buttons:', buttons.length);
for (const b of buttons.slice(0, 8)) {
  const txt = (await b.textContent()).trim();
  console.log(' btn:', txt.slice(0, 40));
}

// Click by visible text
await page.getByText('Knowledge Base').first().click();
await page.waitForTimeout(500);
await page.screenshot({ path: '/tmp/ss_ingest.png' });
console.log('Ingest captured');

await page.getByText('Memory').first().click();
await page.waitForTimeout(500);
await page.screenshot({ path: '/tmp/ss_memory.png' });
console.log('Memory captured');

await page.getByText('Approvals').first().click();
await page.waitForTimeout(500);
await page.screenshot({ path: '/tmp/ss_approvals.png' });
console.log('Approvals captured');

await page.getByText('Settings').first().click();
await page.waitForTimeout(600);
await page.screenshot({ path: '/tmp/ss_settings.png' });
console.log('Settings captured');

await browser.close();
console.log('ALL DONE');
