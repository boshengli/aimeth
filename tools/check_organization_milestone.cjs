const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
(async()=>{
 const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
 const browser=await chromium.launch({headless:true,executablePath:process.env.AIMETH_BROWSER_EXECUTABLE});
 const errors=[],requests=[],views=[];
 try{
  const context=await browser.newContext();
  await context.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(input).href);
   assert.equal(await page.locator('h1').count(),1);
   assert(await page.locator('body').innerText().then(t=>t.includes('46 / 46')&&t.includes('尚未测出组织效果')));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.locator('#graph circle').count(),32);
   if(width!==768)await page.screenshot({path:path.join(path.dirname(output),`m2-1-organization-v1-${width}.png`),fullPage:true});
   if(width!==768)await page.screenshot({path:path.join(path.dirname(output),`m2-1-organization-v1-${width}-top.png`)});
   views.push({width,core_readable:true,no_page_overflow:true});
  }
  for(const arm of ['S','I','L','X']){
   await page.locator(`[data-arm=${arm}]`).click();
   assert.equal(await page.locator('#graph circle').count(),arm==='S'?1:32);
   assert.equal(await page.locator('#graph > svg > path').count(),['L','X'].includes(arm)?64:0);
   assert((await page.locator('#graph-caption').innerText()).startsWith(arm+'：'));
  }
  await page.locator('#population').selectOption('32');
  assert.equal(await page.locator('#tokens').innerText(),'1,327,104');
  await page.locator('#concurrency').fill('200');await page.locator('#concurrency').dispatchEvent('change');
  assert.equal(await page.locator('#concurrency').inputValue(),'32');
  await page.locator('#prompt-known').uncheck();assert((await page.locator('#tokens').innerText()).includes('未知'));
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http')&&!h.startsWith('#'))){
   // Root manifest is produced after screenshots, all other links must already resolve.
   if(href!=='../organization-report-manifest.json')assert(fs.existsSync(path.resolve(path.dirname(input),href)),`Missing file ${href}`);
  }
  await page.locator('#provenance summary').click();assert(await page.locator('#provenance pre').isVisible());
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});
  await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  await page.emulateMedia({media:'print'});assert(!(await page.locator('#print').isVisible()));
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
  assert(await staticPage.locator('body').innerText().then(t=>t.includes('尚未测出组织效果')&&t.includes('10K 提交设计')));
  assert.equal(await staticPage.locator('#graph circle').count(),32);
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,
   four_topology_controls:true,budget_arithmetic:true,concurrency_clamp:true,unknown_input_budget:true,
   local_file_links_except_postbuilt_manifest:true,evidence_disclosure:true,print_wiring:true,print_media:true,
   no_javascript_core_content:true,page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log(fs.readFileSync(output,'utf8'));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
