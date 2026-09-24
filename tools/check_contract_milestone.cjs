const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
(async()=>{
 const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]),name='m2-3-role-contract-v1';
 const browser=await chromium.launch({headless:true,executablePath:process.env.AIMETH_BROWSER_EXECUTABLE});
 const errors=[],requests=[],views=[];
 try{
  const context=await browser.newContext();
  await context.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(input).href);
   assert.equal(await page.locator('h1').count(),1);
   const text=await page.locator('body').innerText();
   for(const value of ['31.25','15 / 32','25 / 32','59,122','59,177','0/16','216262','32/32 格式门槛未通过'])assert(text.includes(value),value);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   for(const [id,count] of Object.entries({comparison:2,roles:8,contexts:4,tasks:4,cross:16,cases:64,probes:2,unstarted:128}))assert.equal(await page.locator(`#${id} tbody tr`).count(),count,id);
   assert.equal(await page.locator('#cases tbody tr:visible').count(),64);
   if(width===390)assert(await page.locator('#cases').evaluate(t=>{const c=t.parentElement;c.scrollLeft=150;const ok=c.scrollLeft>0;c.scrollLeft=0;return ok;}));
   if(width!==768){
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}.png`),fullPage:true});
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}-top.png`)});
    await page.locator('#deployment').screenshot({path:path.join(path.dirname(output),`${name}-${width}-deployment.png`)});
   }
   views.push({width,core_readable:true,no_page_overflow:true});
  }
  await page.locator('#contract-filter').selectOption('output-card');
  assert.equal(await page.locator('#cases tbody tr:visible').count(),32);
  await page.locator('#role-filter').selectOption('C');
  assert.equal(await page.locator('#cases tbody tr:visible').count(),8);
  await page.locator('#context-filter').selectOption('recorded');
  assert.equal(await page.locator('#cases tbody tr:visible').count(),4);
  assert.equal(await page.locator('#filter-count').innerText(),'显示 4 / 64 个请求');
  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('#cases tbody tr:visible').count(),64);
  assert(!(await page.locator('#print').isVisible()));
  await page.emulateMedia({media:'screen'});
  for(const id of ['contract','role','context'])await page.locator(`#${id}-filter`).selectOption('all');
  assert.equal(await page.locator('#cases tbody tr:visible').count(),64);
  await page.locator('#cases tbody tr').first().locator('summary').click();
  assert(await page.locator('#cases tbody tr').first().locator('pre').isVisible());
  await page.locator('#failure details summary').click();assert.equal(await page.locator('#unstarted tbody tr:visible').count(),128);
  await page.locator('#design details summary').click();assert(await page.locator('#design details pre').isVisible());
  await page.locator('#strata details summary').click();assert.equal(await page.locator('#cross tbody tr:visible').count(),16);
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http'))){
   if(href.startsWith('#'))assert.equal(await page.locator(href).count(),1);
   else if(!href.endsWith('role-contract-report-manifest.json')&&!href.endsWith('.browser-qa.json'))assert(fs.existsSync(path.resolve(path.dirname(input),href)),`Missing ${href}`);
  }
  await page.locator('#evidence summary').click();assert(await page.locator('#evidence pre').isVisible());
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});
  await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
  assert.equal(await staticPage.locator('#cases tbody tr:visible').count(),64);
  assert.equal(await staticPage.locator('#unstarted tbody tr').count(),128);
  assert((await staticPage.locator('body').innerText()).includes('32/32 格式门槛未通过'));
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,
   contract_role_context_filters_reset:true,unstarted_cells_retained:128,formal_cells:64,static_table_counts:true,wide_tables_horizontal_scroll:true,
   source_links_except_postbuilt_manifest_and_qa:true,candidate_card_strata_and_evidence_disclosure:true,
   print_wiring:true,print_restores_full_denominator:true,no_javascript_core_content:true,
   page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log(fs.readFileSync(output,'utf8'));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
