// 실제 API로 지역 위계 이동·필터 유지·관심 지역 저장을 확인한다. 임시 계정은 종료 시 삭제한다.
const assert = require('node:assert/strict');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');

(async () => {
  const browser = await chromium.launch({channel:'chrome',headless:true});
  const context = await browser.newContext({baseURL:process.env.E2E_BASE_URL || 'http://localhost:3001'});
  const page = await context.newPage(); page.setDefaultTimeout(60000);
  let registered = false;
  const waitSummary = (code) => page.waitForResponse(r => r.url().includes('/market/regions/summary') && new URL(r.url()).searchParams.get('region_code') === code);
  const row = (text) => page.getByRole('button').filter({has:page.getByText(text,{exact:true})});
  try {
    const registration = await context.request.post('/api/auth/register',{data:{email:`hierarchy-${Date.now()}@example.com`,password:'hierarchy-test-12345',name:'지역 위계 검증'}});
    assert.equal(registration.status(),201); registered=true;
    await page.goto('/explore');
    await page.getByRole('heading',{name:'동네 탐색',exact:true}).waitFor();
    await page.getByRole('link',{name:'동네 탐색',exact:true}).waitFor();
    await page.locator('#explore-sido option[value="1100000000"]').waitFor({state:'attached'});
    assert.equal(await page.getByLabel('시·도',{exact:true}).inputValue(),'1100000000');
    assert.ok(await page.getByLabel('읍·면·동 (법정동)',{exact:true}).isDisabled());

    let pending = waitSummary('1168000000');
    await row('강남구').click();
    let data = await (await pending).json();
    assert.ok(data.items.length > 1);
    assert.equal(await page.getByLabel('시·군·구',{exact:true}).inputValue(),'1168000000');
    await page.getByRole('heading',{name:'강남구 법정 읍·면·동 비교',exact:true}).waitFor();

    pending = waitSummary('1168010100');
    const complexPending = page.waitForResponse(r=>r.url().endsWith('/recommendation/complexes'));
    await page.getByLabel('읍·면·동 (법정동)',{exact:true}).selectOption('1168010100');
    data = await (await pending).json();
    assert.equal(data.items.length,1); assert.equal(data.items[0].region_code,'1168010100');
    const complexes = await (await complexPending).json();
    assert.ok(complexes.results.length > 0);
    assert.ok(complexes.results.every(r=>r.dong==='역삼동'));
    await page.getByRole('heading',{name:'역삼동 실거래 분석',exact:true}).waitFor();
    await page.getByRole('region',{name:'선택한 동의 실거래 지표'}).waitFor();
    await page.getByRole('button',{name:'케이스 만들고 저장',exact:true}).click();
    await page.getByRole('button',{name:'지역 저장됨',exact:true}).waitFor();

    pending = waitSummary('1168010100');
    await page.getByRole('button',{name:'연립·다세대',exact:true}).click();
    data = await (await pending).json();assert.equal(data.property_type,'row_house');
    assert.equal(await page.getByLabel('읍·면·동 (법정동)',{exact:true}).inputValue(),'1168010100');
    await page.getByPlaceholder('예: 12').fill('8');
    pending = waitSummary('1168010100');
    await page.getByRole('button',{name:'조건 적용',exact:true}).click();
    const budgetResponse=await pending;
    assert.equal(new URL(budgetResponse.url()).searchParams.get('budget_max'),'80000');

    pending = waitSummary('1168000000');
    await page.getByRole('navigation',{name:'선택한 지역 경로'}).getByRole('button',{name:'강남구',exact:true}).click();
    data=await(await pending).json(); assert.ok(data.items.length>1); assert.equal(data.property_type,'row_house');
    assert.equal(await page.getByLabel('읍·면·동 (법정동)',{exact:true}).inputValue(),'');
    pending=waitSummary('1168010100');await row('강남구 역삼동').click();await pending;
    assert.equal(await page.getByLabel('읍·면·동 (법정동)',{exact:true}).inputValue(),'1168010100');

    pending=waitSummary('1171000000');
    await page.getByLabel('시·군·구',{exact:true}).selectOption('1171000000');
    data=await(await pending).json();assert.ok(data.items.every(r=>r.region_code.startsWith('11710')));
    assert.equal(await page.getByLabel('읍·면·동 (법정동)',{exact:true}).inputValue(),'');
    assert.equal(await page.getByPlaceholder('예: 12').inputValue(),'8');
    pending=waitSummary('1100000000');
    await page.getByRole('navigation',{name:'선택한 지역 경로'}).getByRole('button',{name:'서울특별시',exact:true}).click();
    await pending;
    assert.equal(await page.getByLabel('시·군·구',{exact:true}).inputValue(),'');
    assert.ok(await page.getByLabel('읍·면·동 (법정동)',{exact:true}).isDisabled());

    pending=waitSummary('1168000000');await row('강남구').click();await pending;
    pending=waitSummary('1168010100');await page.getByLabel('읍·면·동 (법정동)',{exact:true}).selectOption('1168010100');await pending;
    await page.getByRole('heading',{name:'역삼동 실거래 분석',exact:true}).waitFor();
    await page.screenshot({path:'evaluation-results/explore-hierarchy-desktop.png',fullPage:true});
    await page.setViewportSize({width:390,height:844});
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth));
    await page.screenshot({path:'evaluation-results/explore-hierarchy-mobile.png',fullPage:true});
    console.log('PASS city → district → dong; dropdown/list navigation; parent reset; budget/type retained; same-dong complexes; save; mobile layout');
  } finally {
    try { if(registered) assert.equal((await context.request.delete('/api/auth/me')).status(),200); }
    finally { await browser.close(); }
  }
})().catch(e=>{console.error(e.message);process.exitCode=1;});
