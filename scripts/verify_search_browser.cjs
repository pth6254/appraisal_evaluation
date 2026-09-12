// 실제 검색 API와 화면을 함께 검증하고 생성한 임시 계정만 삭제한다.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const context = await browser.newContext({ baseURL: process.env.E2E_BASE_URL || 'http://localhost:3001' });
  const page = await context.newPage();
  page.setDefaultTimeout(45000);
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  let registered = false;
  try {
    for (let i = 0; i < 40; i++) {
      const response = await context.request.get('/api/auth/me').catch(() => null);
      if (response?.status() === 401) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    const register = await context.request.post('/api/auth/register', { data: {
      email: `search-browser-${Date.now()}@example.com`, password: 'search-browser-only-12345', name: '검색 검증 임시 계정',
    } });
    assert.equal(register.status(), 201); registered = true;
    await page.goto('/explore');
    await page.getByRole('heading', { name: '어느 동네부터 볼까요?', exact: true }).waitFor();
    const regions = await context.request.get('/api/market/regions');
    assert.equal(regions.status(), 200);
    console.log('PASS explore and regions API; region count:', (await regions.json()).items.length);
    await page.goto('/recommendation');
    await page.getByPlaceholder('예: 춘천시, 해운대구, 서초구').fill('서초구');
    let pending = page.waitForResponse(r => r.url().endsWith('/recommendation/complexes') && r.request().method() === 'POST', { timeout: 120000 });
    await page.getByRole('button', { name: '🔍 단지 추천받기', exact: true }).click();
    let response = await pending;
    assert.equal(response.status(), 200);
    let body = await response.json();
    assert.ok(!body.error && body.results.length > 0);
    await page.getByText(body.results[0].complex_name, { exact: true }).first().waitFor();
    console.log('PASS real transaction complex search:', body.results.length);
    await page.getByRole('button', { name: '📋 샘플 매물 추천', exact: true }).click();
    await page.locator('select').filter({ has: page.getByRole('option', { name: '투자', exact: true }) }).selectOption({ label: '투자' });
    await page.getByPlaceholder('예: 3억').fill('2.5억');
    pending = page.waitForResponse(r => r.url().endsWith('/recommendation') && r.request().method() === 'POST', { timeout: 120000 });
    await page.getByRole('button', { name: '🔍 매물 추천받기', exact: true }).click();
    response = await pending;
    assert.equal(response.request().postDataJSON().budget_min, 250000000);
    assert.equal(response.status(), 200);
    body = await response.json();
    assert.ok(!body.error && body.results.length > 0);
    assert.equal(body.query.purpose, 'investment');
    assert.equal(body.query.intent, 'recommendation');
    assert.deepEqual(errors, []);
    console.log('PASS sample search, purpose normalization, decimal budget:', body.results.length);
  } finally {
    if (registered) assert.equal((await context.request.delete('/api/auth/me')).status(), 200);
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
