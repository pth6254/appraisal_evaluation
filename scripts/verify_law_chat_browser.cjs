// 실제 모델·법령 DB로 두 화면의 비동기 답변과 출처를 검증한다.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const {chromium} = require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
(async()=>{
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const context=await browser.newContext({baseURL:process.env.E2E_BASE_URL || 'http://localhost:3001'});
 const page=await context.newPage();page.setDefaultTimeout(45000);
 const evidence=[];let registered=false;
 try{
  for(let i=0;i<40;i++){const r=await context.request.get('/api/auth/me').catch(()=>null);if(r?.status()===401)break;await new Promise(resolve=>setTimeout(resolve,1000));}
  const reg=await context.request.post('/api/auth/register',{data:{email:`law-chat-${Date.now()}@example.com`,password:'law-chat-test-only-12345',name:'법령 연결 검증'}});
  assert.equal(reg.status(),201);registered=true;
  for(const widget of [false,true]){
   await page.goto(widget?'/':'/chat');
   if(widget)await page.getByRole('button',{name:'AI 컨시어지 열기',exact:true}).click();
   const path=widget?'/api/concierge/jobs':'/api/chat/jobs';
   const pending=page.waitForResponse(r=>r.url().endsWith(path)&&r.request().method()==='POST');
   const question='주택임대차보호법에서 임차권등기명령은 어떤 경우 신청하나요?';
   await page.getByPlaceholder(widget?'예산과 희망 지역을 말씀해 주세요':'질문을 입력하세요 (예: 전세 계약 전 뭘 확인해야 하나요?)').fill(question);
   const start=Date.now();await page.getByRole('button',{name:widget?'메시지 보내기':'전송',exact:true}).click();
   const accepted=await pending;assert.equal(accepted.status(),200);const {job_id}=await accepted.json();
   const acceptance=(Date.now()-start)/1000;
   let job;
   for(let i=0;i<120;i++){
    job=await (await context.request.get(`${path}/${job_id}`)).json();
    if(['done','error'].includes(job.status))break;
    if(i%10===0)console.log(widget?'WIDGET':'CHAT','running',job.step);
    await new Promise(resolve=>setTimeout(resolve,2000));
   }
   assert.equal(job.status,'done',JSON.stringify(job));
   const result=widget?job.result.data:job.result;
   assert.ok(result.sources.some(source=>source.origin==='official_law'));
   assert.ok(job.result.answer && !job.result.answer.includes('자료를 찾지 못했습니다'));
   await page.getByRole('link',{name:/주택임대차보호법.*원문 보기/}).first().waitFor();
   evidence.push({screen:widget?'concierge':'chat',acceptance_seconds:acceptance,elapsed_seconds:(Date.now()-start)/1000,answer:job.result.answer,sources:result.sources});
   console.log('PASS',evidence.at(-1).screen,'accept',acceptance,'total',evidence.at(-1).elapsed_seconds);
   await page.screenshot({path:`evaluation-results/law-${widget?'widget':'chat'}.png`,fullPage:true});
  }
  fs.writeFileSync('evaluation-results/law-chat-live.json',JSON.stringify(evidence,null,2));
 }finally{if(registered)assert.equal((await context.request.delete('/api/auth/me')).status(),200);await browser.close();}
})().catch(error=>{console.error(error.message);process.exitCode=1;});
