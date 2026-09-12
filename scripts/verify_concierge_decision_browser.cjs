// 실제 모델·계산기·Redis·후보 DB를 사용한 연속 대화 검증. 임시 계정만 생성·삭제한다.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
(async () => {
  const browser = await chromium.launch({channel: 'chrome', headless: true});
  const context = await browser.newContext({baseURL: process.env.E2E_BASE_URL || 'http://localhost:3001'});
  const page = await context.newPage(); page.setDefaultTimeout(45000);
  let registered = false;
  const evidence = [];
  try {
    for (let i = 0; i < 45; i++) {
      const ready = await context.request.get('/api/auth/me').catch(() => null);
      if (ready?.status() === 401) break;
      await new Promise(resolve => setTimeout(resolve, 1000));
    }
    const reg = await context.request.post('/api/auth/register', {data: {
      email: `concierge-decision-${Date.now()}@example.com`, password: 'decision-browser-only-12345', name: '대화 검증'}});
    assert.equal(reg.status(), 201); registered = true;
    const caseId = (await (await context.request.post('/api/cases', {data: {title: '대화 의사결정 검증'}})).json()).id;
    const ids = [];
    for (const [name, price] of [['후보 A', 600000000], ['후보 B', 700000000]]) {
      const response = await context.request.post(`/api/cases/${caseId}/properties`, {data: {name, asking_price: price, category: 'apartment'}});
      assert.equal(response.status(), 201); ids.push((await response.json()).id);
    }
    await page.goto('/');
    await page.getByRole('button', {name: 'AI 컨시어지 열기', exact: true}).click();
    await page.getByLabel('검토 케이스', {exact: true}).selectOption(String(caseId));
    await page.getByLabel('분석할 후보', {exact: true}).selectOption(String(ids[0]));
    async function send(message) {
      const pending = page.waitForResponse(r => r.url().endsWith('/api/concierge/jobs') && r.request().method() === 'POST');
      await page.getByPlaceholder('예산과 희망 지역을 말씀해 주세요').fill(message);
      await page.getByRole('button', {name: '메시지 보내기', exact: true}).click();
      const accepted = await pending; assert.equal(accepted.status(), 200);
      const {job_id} = await accepted.json();
      let job;
      for (let i = 0; i < 120; i++) {
        job = await (await context.request.get(`/api/concierge/jobs/${job_id}`)).json();
        if (['done', 'error'].includes(job.status)) break;
        await new Promise(resolve => setTimeout(resolve, 1000));
      }
      assert.equal(job.status, 'done', JSON.stringify(job));
      evidence.push({message, result: job.result});
      fs.writeFileSync('evaluation-results/concierge-decision-live.json', JSON.stringify(evidence, null, 2));
      console.log(job.result.status, job.result.tool_used, JSON.stringify(job.result.data.funding_inputs || {}));
      await page.getByPlaceholder('예산과 희망 지역을 말씀해 주세요').waitFor({state: 'visible'});
      await page.waitForFunction(() => !document.querySelector('textarea[placeholder="예산과 희망 지역을 말씀해 주세요"]').disabled);
      await page.getByText(job.result.answer, {exact: true}).last().waitFor();
      if (job.result.data.funding_inputs?.annual_interest_rate != null) {
        const conditions = page.locator('p').filter({hasText: /^반영한 조건:/}).last();
        assert.ok((await conditions.innerText()).includes(`연 금리 ${job.result.data.funding_inputs.annual_interest_rate}%`));
      }
      return job.result;
    }
    const first = await send('이 후보 자금 분석해줘. 보유 현금은 3억이고 대출 비율은 50%야.');
    assert.equal(first.status, 'needs_input'); assert.equal(first.data.funding_inputs.cash_available, 300000000);
    async function reloadAndRestore(expected) {
      await page.reload();
      await page.getByRole('button', {name: 'AI 컨시어지 열기', exact: true}).click();
      await page.getByText(expected.answer, {exact: true}).waitFor();
      assert.equal(await page.getByLabel('분석할 후보', {exact: true}).inputValue(), String(ids[0]));
      assert.equal(await page.getByLabel('검토 케이스', {exact: true}).inputValue(), String(caseId));
      console.log('PASS reload restored messages and selection');
    }
    await reloadAndRestore(first);
    const second = await send('금리는 연 4%, 대출 기간은 30년, 원리금균등이야. 취득 후 1주택이고 비조정지역이야. 기존 대출은 없어. 연소득은 1억이고 월 상환 한도는 200만원이야.');
    assert.equal(second.status, 'completed', JSON.stringify(second));
    assert.equal(second.data.candidate_funding.inputs.cash_available, 300000000);
    assert.equal(second.conversation_id, first.conversation_id);
    await reloadAndRestore(second);
    const monthly = second.data.candidate_funding.monthly_payment;
    const third = await send('그럼 금리만 5%로 바꿔서 다시 계산해줘');
    assert.equal(third.status, 'completed', JSON.stringify(third));
    assert.ok(third.data.candidate_funding.monthly_payment > monthly);
    await page.getByLabel('분석할 후보', {exact: true}).selectOption('');
    const compared = await send('그럼 후보 비교해줘');
    assert.equal(compared.data.comparison.rows.length, 2);
    assert.equal(compared.data.comparison.rows[0].funding.annual_interest_rate, 5);
    assert.equal(compared.data.comparison.rows[1].funding, null);
    const comparisonAnswer = await page.getByText(compared.answer, {exact: true}).innerText();
    assert.ok(comparisonAnswer.includes('후보 A') && comparisonAnswer.includes('후보 B'));
    assert.ok(comparisonAnswer.includes('월 상환액') && comparisonAnswer.includes('확인할 항목'));
    await page.screenshot({path: 'evaluation-results/concierge-comparison-ui.png', fullPage: true});
    await page.getByLabel('분석할 후보', {exact: true}).selectOption(String(ids[1]));
    const switched = await send('이 후보 자금 분석해줘');
    assert.ok(switched.missing_fields.includes('cash_available'));
    await page.getByRole('link', {name: '케이스에서 분석·비교 결과 확인'}).last().waitFor();
    await page.screenshot({path: 'evaluation-results/concierge-decision.png', fullPage: true});
    await page.getByRole('button', {name: '새 대화 시작 · 기억한 조건 초기화', exact: true}).click();
    await page.reload();
    await page.getByRole('button', {name: 'AI 컨시어지 열기', exact: true}).click();
    assert.equal(await page.getByText(second.answer, {exact: true}).count(), 0);
    console.log('PASS new conversation stays cleared after reload');
    console.log('PASS actual model followup, calculation, saved comparison, candidate isolation');
  } finally {
    if (registered) assert.equal((await context.request.delete('/api/auth/me')).status(), 200);
    await browser.close();
  }
})().catch(error => {console.error(error.message); process.exitCode = 1;});
