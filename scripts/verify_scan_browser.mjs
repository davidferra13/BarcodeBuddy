import fs from 'node:fs';
import path from 'node:path';
import assert from 'node:assert/strict';
if (process.env.BB_PROOF_SCOPE !== 'isolated-synthetic' || !process.env.BB_PROOF_URL || !process.env.BB_PROOF_OUT) throw new Error('Use an explicitly provisioned isolated-synthetic runtime and output directory.');
if (!['127.0.0.1','localhost','[::1]'].includes(new URL(process.env.BB_PROOF_URL).hostname)) throw new Error('Browser verification is restricted to a local synthetic runtime.');
const { chromium } = await import(process.env.BB_PLAYWRIGHT_MODULE || 'playwright');
const base=process.env.BB_PROOF_URL||'http://127.0.0.1:18081';
const output=process.env.BB_PROOF_OUT;
const fixture=path.join(output,'fixture.png');
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--mute-audio','--disable-background-networking','--disable-component-update']});
const report={at:new Date().toISOString(),target:base,scope:'isolated actual API, synthetic camera MediaStream, browser-sized mobile',checks:[]};
const check=async(name,fn)=>{try{await fn();report.checks.push({name,pass:true});}catch(e){report.checks.push({name,pass:false,error:e.message.slice(0,400),state:await page.evaluate(()=>({count:document.querySelector('#stp-count')?.textContent,storage:localStorage.getItem('stp_session'),notice:document.querySelector('#stp-storage-status')?.textContent})).catch(()=>null)});}fs.writeFileSync(path.join(output,'browser-'+(process.env.BB_PROOF_LABEL||'red')+'.json'),JSON.stringify(report,null,2));};
const context=await browser.newContext({viewport:{width:390,height:844}});
await context.route('**/proof-fixture.png',route=>route.fulfill({body:fs.readFileSync(fixture),contentType:'image/png'}));
const login=await context.request.post(base+'/auth/api/signup',{data:{email:'barcode-recovery@example.invalid',password:'Synthetic-test-only-20261008!',display_name:'Barcode Recovery'}});
if(!login.ok()&&login.status()!==409)throw new Error('isolated signup failed '+login.status()+':'+await login.text());
if(!login.ok()) {const r=await context.request.post(base+'/auth/api/login',{data:{email:'barcode-recovery@example.invalid',password:'Synthetic-test-only-20261008!'}});if(!r.ok())throw new Error('isolated login failed');}
const page=await context.newPage();
await page.goto(base+'/scan-to-pdf');
await check('real PNG upload decodes and persists after reload',async()=>{
 await page.getByRole('button',{name:'Upload File',exact:true}).click();
 await page.locator('#stp-file').setInputFiles(fixture);
 await page.waitForFunction(()=>document.querySelector('#stp-upload-status').textContent.includes('Found'),null,{timeout:15000});
 assert.equal(await page.locator('#stp-count').textContent(),'1');
 assert.match(await page.locator('#stp-tbody').textContent(),/BB-RECOVERY-01/);
 await page.reload();
 assert.equal(await page.locator('#stp-count').textContent(),'1');
});
await check('failed upload releases input so same file can be retried',async()=>{
 await page.getByRole('button',{name:'Upload File',exact:true}).click();
 await page.locator('#stp-file').setInputFiles({name:'broken.png',mimeType:'image/png',buffer:Buffer.from('not-an-image')});
 await page.waitForFunction(()=>document.querySelector('#stp-upload-status').textContent.startsWith('Error:'),null,{timeout:10000});
 assert.equal(await page.locator('#stp-file').inputValue(),'');
 assert.equal(await page.locator('#stp-count').textContent(),'1');
 await page.locator('#stp-file').setInputFiles(fixture);
 await page.waitForFunction(()=>document.querySelector('#stp-count').textContent==='2' && document.querySelector('#stp-upload-status').textContent.startsWith('Found'),null,{timeout:15000});
});
await check('corrupt saved session recovers without disabling manual entry',async()=>{
 await page.waitForLoadState('networkidle');
 await page.evaluate(()=>localStorage.setItem('stp_session','broken-json'));
 await page.reload();
 await page.locator('#manual-input').fill('RECOVERY-MANUAL');
 await page.locator('#manual-input').press('Enter');
 await page.waitForFunction(()=>document.querySelector('#stp-count').textContent==='1',null,{timeout:3000});
 assert.match(await page.locator('#stp-tbody').textContent(),/RECOVERY-MANUAL/);
 assert.match(await page.locator('#stp-storage-status').textContent(),/recovery|unreadable/i);
 assert.equal(await page.evaluate(()=>Object.keys(localStorage).some(k=>k.startsWith('stp_session_recovery_')&&localStorage.getItem(k)==='broken-json')),true);
});
await check('malformed saved session and unavailable storage leave manual entry usable',async()=>{
 await page.evaluate(()=>localStorage.setItem('stp_session','{}'));
 await page.reload();
 await page.locator('#manual-input').fill('MALFORMED-RECOVERY');await page.locator('#manual-input').press('Enter');
 await page.waitForFunction(()=>document.querySelector('#stp-count').textContent==='1',null,{timeout:3000});
 await page.evaluate(()=>{window.testStorageSet=Storage.prototype.setItem;Storage.prototype.setItem=function(){throw new DOMException('Fixture quota','QuotaExceededError')};});
 try {
  await page.locator('#manual-input').fill('IN-MEMORY');await page.locator('#manual-input').press('Enter');
  assert.equal(await page.locator('#stp-count').textContent(),'2');
  assert.match(await page.locator('#stp-storage-status').textContent(),/export|saved/i);
 } finally {await page.evaluate(()=>{Storage.prototype.setItem=window.testStorageSet;});}
});
await page.evaluate(()=>localStorage.removeItem('stp_session'));
await page.reload();
await check('synthetic camera decodes through real API without BarcodeDetector',async()=>{
 await page.addInitScript(()=>{
  try {delete window.BarcodeDetector;}catch{}
  let sourceCanvas;
  Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{
   enumerateDevices:async()=>[{kind:'videoinput',deviceId:'fixture',label:'Synthetic fixture camera'}],
   getUserMedia:async()=>{
    sourceCanvas=document.createElement('canvas');sourceCanvas.width=960;sourceCanvas.height=540;
    const ctx=sourceCanvas.getContext('2d');const img=new Image();img.src='/proof-fixture.png';
    await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=reject;});
    ctx.fillStyle='white';ctx.fillRect(0,0,960,540);ctx.drawImage(img,0,0,960,540);
    return sourceCanvas.captureStream(4);
   }
  }});
 });
 await page.reload();
 await page.getByRole('button',{name:'Camera',exact:true}).click();
 await page.getByRole('button',{name:'Start Camera',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#stp-count').textContent==='1',null,{timeout:7000});
 assert.match(await page.locator('#stp-tbody').textContent(),/BB-RECOVERY-01/);
 await page.evaluate(()=>{window.proofCameraStream=document.getElementById('stp-vid').srcObject;});
 await page.getByRole('button',{name:'Stop Camera',exact:true}).click();
 assert.equal(await page.locator('#stp-vid').evaluate(v=>v.srcObject),null);
 assert.equal(await page.evaluate(()=>window.proofCameraStream.getTracks().every(t=>t.readyState==='ended')),true);
});
await check('denied camera remains retryable',async()=>{
 await page.evaluate(()=>{window.proofGetMedia=navigator.mediaDevices.getUserMedia;navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Fixture permission denied','NotAllowedError')};});
 try {
  await page.getByRole('button',{name:'Start Camera',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#stp-cam-stat').textContent.includes('Camera unavailable'),null,{timeout:3000});
  assert.equal(await page.getByRole('button',{name:'Start Camera',exact:true}).isVisible(),true);
 } finally {await page.evaluate(()=>{navigator.mediaDevices.getUserMedia=window.proofGetMedia;});}
});
await check('stopping camera cancels late decode responses',async()=>{
 await page.evaluate(()=>localStorage.removeItem('stp_session'));await page.reload();
 await page.getByRole('button',{name:'Camera',exact:true}).click();
 let pending;
 await page.route('**/api/scan-to-pdf/decode',async route=>{pending=route;});
 try {
  await page.getByRole('button',{name:'Start Camera',exact:true}).click();
  for(let i=0;i<40&&!pending;i++)await page.waitForTimeout(100);
  assert.ok(pending,'Camera decode was never requested');
  await page.getByRole('button',{name:'Stop Camera',exact:true}).click();
  await pending.fulfill({json:{count:1,barcodes:[{value:'LATE-FRAME',format:'Code128'}]}}).catch(()=>{});
  await page.waitForTimeout(200);
  assert.equal(await page.locator('#stp-count').textContent(),'0');
  assert.equal(await page.locator('#stp-cam-stat').textContent(),'Stopped');
 } finally {await page.unroute('**/api/scan-to-pdf/decode');}
});
await check('camera aiming guide is visible inside the video viewport',async()=>{
 const guide=page.locator('#stp-cam-guide');
 assert.equal(await guide.isVisible(),true);
 const g=await guide.boundingBox(),v=await page.locator('#stp-cam-box').boundingBox();
 assert.ok(g.width>40&&g.height>40&&g.x>=v.x&&g.y>=v.y&&g.x+g.width<=v.x+v.width+1);
});
await check('mobile scan page fits viewport and export returns a real PDF',async()=>{
 assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
 await page.evaluate(()=>localStorage.removeItem('stp_session'));await page.reload();
 await page.locator('#manual-input').fill('PDF-RECOVERY');await page.locator('#manual-input').press('Enter');
 const download=page.waitForEvent('download',{timeout:10000});
 await page.locator('#stp-export-btn').click();
 const item=await download;const p=await item.path();assert.ok(fs.readFileSync(p).subarray(0,5).toString()==='%PDF-');
 await page.screenshot({path:path.join(output,'scan-mobile-'+(process.env.BB_PROOF_LABEL||'red')+'.png'),fullPage:true});
 await page.setViewportSize({width:1440,height:1000});
 await page.screenshot({path:path.join(output,'scan-desktop-'+(process.env.BB_PROOF_LABEL||'red')+'.png'),fullPage:true});
});
await browser.close();
console.log(JSON.stringify(report));
process.exitCode=report.checks.some(x=>!x.pass)?1:0;

