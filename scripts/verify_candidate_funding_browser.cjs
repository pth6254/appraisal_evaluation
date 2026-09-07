// 실제 계산 API와 후보 저장을 호출한다. 실행 후 임시 계정을 삭제한다.
const fs = require('node:fs');
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
  const evidence = { stages: [], calculator_mocked: false };
  try {
    for (let i = 0; i < 40; i++) {
      const response = await context.request.get('/api/auth/me').catch(() => null);
      if (response?.status() === 401) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    const register = await context.request.post('/api/auth/register', { data: {
      email: `funding-browser-${Date.now()}@example.com`, password: 'funding-browser-only-12345', name: '자금 검증 임시 계정',
    } });
    assert.equal(register.status(), 201); registered = true;
    const created = await context.request.post('/api/cases', { data: { title: '자금 의사결정 검증' } });
    const caseId = (await created.json()).id;
    const path = `/api/cases/${caseId}`;
    const added = await context.request.post(`${path}/properties`, { data: {
      name: '자금 검증 후보', category: 'apartment', asking_price: 600000000,
    } });
    assert.equal(added.status(), 201);
    const candidateId = (await added.json()).id;
    await page.goto(`/cases/${caseId}`);
    await page.getByRole('link').filter({ hasText: '자금 분석' }).click();
    await page.getByPlaceholder('예: 8000만').waitFor();
    assert.equal(await page.getByLabel('매수가 (원)', { exact: true }).inputValue(), '60000만', '후보 가격 자동 채움');
    assert.equal(await page.locator('select').first().inputValue(), '아파트');
    await page.getByLabel('보유 현금 (원)', { exact: true }).fill('3억');
    await page.getByLabel('월 대출 상환 한도 (원)', { exact: true }).fill('10만');
    await page.getByPlaceholder('예: 8000만').fill('1억');
    const calculate = async () => {
      const pending = page.waitForResponse(r => r.url().endsWith('/api/simulation') && r.request().method() === 'POST');
      await page.getByRole('button', { name: '💰 시뮬레이션 계산', exact: true }).click();
      const response = await pending;
      assert.equal(response.status(), 200);
      const body = await response.json(); assert.ok(!body.error);
      assert.equal(body.result.purchase_price, 600000000);
      assert.ok(body.candidate_funding);
      return body;
    };
    const first = await calculate();
    evidence.stages.push('candidate_price_type_prefill', 'real_calculation_saved');
    await page.getByRole('link', { name: '후보 비교·다음 행동 확인' }).click();
    await page.getByText('부족한 자금 조달 확인', { exact: true }).waitFor();
    await page.getByText('월 상환 부담 확인', { exact: true }).waitFor();
    const comparison = await (await context.request.get(`${path}/comparison`)).json();
    assert.equal(comparison.rows[0].funding.monthly_payment, first.result.loan.monthly_payment);
    assert.equal(comparison.rows[0].funding.cash_shortfall, first.result.acquisition_cost.total);
    assert.equal(comparison.rows[0].decision_ready, false);
    evidence.stages.push('comparison_funding_warnings');
    await page.goto(`/cases/${caseId}`);
    await page.getByRole('link').filter({ hasText: '자금 분석' }).click();
    await page.getByLabel('보유 현금 (원)', { exact: true }).waitFor();
    assert.equal(await page.getByLabel('보유 현금 (원)', { exact: true }).inputValue(), '300000000');
    await page.getByLabel('보유 현금 (원)', { exact: true }).fill('6.5억');
    await page.getByLabel('월 대출 상환 한도 (원)', { exact: true }).fill('500만');
    const second = await calculate();
    assert.equal(second.candidate_funding.cash_available, 650000000);
    assert.equal(second.candidate_funding.cash_shortfall, 0);
    assert.equal(second.candidate_funding.monthly_payment_exceeded, false);
    const detail = await (await context.request.get(path)).json();
    assert.ok(!detail.properties[0].next_actions.some(a => a.code.startsWith('funding_')));
    evidence.stages.push('saved_criteria_prefill', 'decimal_money_parsing', 'recalculation_clears_warnings');
    await context.request.patch(`${path}/properties/${candidateId}`, { data: { asking_price: 610000000 } });
    await page.goto(`/cases/${caseId}`); await page.reload();
    await page.getByText('변경된 가격으로 자금 조건 확인', { exact: true }).waitFor();
    evidence.stages.push('price_change_requires_review');
    fs.mkdirSync('evaluation-results', { recursive: true });
    await page.screenshot({ path: 'evaluation-results/funding-browser.png', fullPage: true });
    assert.deepEqual(errors, []);
    console.log('PASS', evidence.stages.join(', '));
  } catch (error) {
    evidence.error = error.message.split('Call log:')[0];
    console.log(evidence.error); process.exitCode = 1;
    console.log((await page.locator('body').innerText()).slice(0, 1800));
  } finally {
    if (registered) {
      const cleanup = await context.request.delete('/api/auth/me');
      evidence.cleanup_status = cleanup.status();
      if (cleanup.status() !== 200) process.exitCode = 1;
    }
    fs.mkdirSync('evaluation-results', { recursive: true });
    fs.writeFileSync('evaluation-results/funding-browser-result.json', JSON.stringify(evidence, null, 2));
    await browser.close();
  }
})();
