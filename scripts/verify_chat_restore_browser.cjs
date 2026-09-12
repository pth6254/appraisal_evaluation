// 실제 모델과 법령 DB를 사용해 /chat 복원 및 후속 질문을 검증한다.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
(async () => {
  const browser = await chromium.launch({channel:'chrome', headless:true});
  const context = await browser.newContext({baseURL:process.env.E2E_BASE_URL || 'http://localhost:3001'});
  const page = await context.newPage(); page.setDefaultTimeout(45000);
  const evidence = []; let registered = false;
  try {
    for (let i=0;i<45;i++) {
      if ((await context.request.get('/api/auth/me').catch(()=>null))?.status()===401) break;
      await new Promise(r=>setTimeout(r,1000));
    }
    const reg = await context.request.post('/api/auth/register',{data:{email:`chat-restore-${Date.now()}@example.com`,password:'chat-restore-test-12345',name:'대화 복원 검증'}});
    assert.equal(reg.status(),201); registered=true;
    await page.goto('/chat');
    const input = page.getByPlaceholder('질문을 입력하세요 (예: 전세 계약 전 뭘 확인해야 하나요?)');
    async function send(question) {
      const pending = page.waitForResponse(r=>r.url().endsWith('/api/chat/jobs') && r.request().method()==='POST');
      await input.fill(question); await page.getByRole('button',{name:'전송',exact:true}).click();
      const response=await pending; assert.equal(response.status(),200);
      const {job_id}=await response.json(); let job;
      for(let i=0;i<160;i++) {
        job=await (await context.request.get(`/api/chat/jobs/${job_id}`)).json();
        if(['done','error'].includes(job.status)) break;
        if(i%20===0) console.log('대화 답변 대기',i);
        await new Promise(r=>setTimeout(r,1000));
      }
      assert.equal(job.status,'done',JSON.stringify(job));
      await page.getByText(job.result.answer,{exact:true}).last().waitFor();
      evidence.push({question,result:job.result});
      fs.writeFileSync('evaluation-results/chat-restore-live.json',JSON.stringify(evidence,null,2));
      console.log('답변 완료', job.result.tool_used || '법령 검색');
      return job.result;
    }
    const first=await send('주택임대차보호법에서 임차권등기명령은 어떤 경우 신청하나요?');
    assert.ok(first.sources.some(s=>s.origin==='official_law'));
    await page.reload();
    await page.getByText(first.answer,{exact:true}).waitFor();
    await page.getByRole('link',{name:/주택임대차보호법.*원문 보기/}).first().waitFor();
    console.log('PASS 법령 답변 및 출처 복원');
    const follow=await send('그 경우 어느 법원에 신청하나요?');
    assert.equal(follow.conversation_id,first.conversation_id);
    assert.ok(follow.sources.some(s=>s.title.includes('주택임대차보호법')));
    assert.ok(!follow.answer.includes('자료를 찾지 못했습니다'));
    await page.getByRole('button',{name:'새 대화 시작',exact:true}).click();
    const tax=await send('성인 자녀에게 5억 증여하면 증여세 얼마인가요?');
    assert.notEqual(tax.conversation_id,first.conversation_id);
    assert.equal(tax.tool_used,'증여세 계산');
    await page.reload(); await page.getByText(tax.answer,{exact:true}).waitFor();
    const spouse=await send('그럼 배우자에게 같은 금액을 증여하면 증여세는 얼마야?');
    assert.equal(spouse.conversation_id,tax.conversation_id);
    assert.equal(spouse.tool_used,'증여세 계산');
    assert.match(spouse.answer, /0원|없습니다|발생하지 않|과세되지 않/);
    await page.screenshot({path:'evaluation-results/chat-restore.png',fullPage:true});
    await page.getByRole('button',{name:'새 대화 시작',exact:true}).click();
    await page.reload();
    assert.equal(await page.getByText(spouse.answer,{exact:true}).count(),0);
    console.log('PASS 새로고침 후 법령 후속 질문, 계산 조건 유지 및 변경, 새 대화 초기화');
  } finally {
    if(registered) assert.equal((await context.request.delete('/api/auth/me')).status(),200);
    await browser.close();
  }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
