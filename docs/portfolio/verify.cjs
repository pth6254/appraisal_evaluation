const {chromium}=require(process.env.PLAYWRIGHT_MODULE_PATH || 'playwright');
const {pathToFileURL}=require('node:url');
const path=require('node:path');
const assert=require('node:assert/strict');
const fs=require('node:fs');const output=path.join(__dirname,'verification');fs.mkdirSync(output,{recursive:true});
(async()=>{const browser=await chromium.launch({channel:'chrome',headless:true});
const page=await browser.newPage({viewport:{width:1440,height:900}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
await page.goto(pathToFileURL(path.join(__dirname, 'index.html')).href);await page.evaluate(()=>document.fonts.ready);
assert.equal(await page.locator('.slide').count(),5);
for(const id of ['intro','product','system','engineering','evaluation']){await page.locator('#'+id).screenshot({path:path.join(output,`${id}.png`)});}
assert.equal(await page.locator('[data-screen]').count(),4);
assert.ok(await page.locator('.problem dd').first().evaluate(e=>parseFloat(getComputedStyle(e).fontSize)>=17));
for(const name of ['appraisal','simulation','comparison','candidate']){
  await page.locator(`[data-screen=${name}]`).click();
  assert.equal(await page.locator(`[data-screen=${name}]`).getAttribute('aria-selected'),'true');
  await page.locator('#screen').evaluate(image=>image.decode());
  assert.ok(await page.locator('#screen').evaluate(image=>image.naturalWidth>500));
}
await page.locator('#zoom').click();assert.equal(await page.locator('dialog').evaluate(e=>e.open),true);await page.locator('#close').click();
await page.locator('#sources').click();assert.ok(await page.locator('#modal-body').innerText().then(s=>s.includes('0.2143')));await page.keyboard.press('Escape');
await page.setViewportSize({width:390,height:844});await page.goto(page.url());await page.evaluate(()=>document.fonts.ready);
assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
await page.locator('#intro').screenshot({path:path.join(output,'mobile.png')});
await page.setViewportSize({width:1440,height:900});await page.emulateMedia({media:'print'});await page.pdf({path:path.join(output,'print-check.pdf'),preferCSSPageSize:true,printBackground:true});
assert.deepEqual(errors,[]);console.log('PASS: five slides, screenshot tabs, image dialog, evidence dialog, mobile width, print render; no JavaScript errors');await browser.close();})();
