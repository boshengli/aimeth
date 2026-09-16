const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
(async()=>{
 const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
 const name='m2-1-service-calibration-v1';
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
   assert(text.includes('18 通过 · 21 错误 · 8 格式不合规 · 1 截断'));
   assert(text.includes('18,256')&&text.includes('2,033')&&text.includes('190045'));
   assert(text.includes('不构成 Navier–Stokes 正则性证明'));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.locator('#factors tbody tr').count(),8);
   assert.equal(await page.locator('#public-cases tbody tr').count(),8);
   assert.equal(await page.locator('#design svg').count(),2);
   if(width!==768){
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}.png`),fullPage:true});
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}-top.png`)});
    await page.locator('#design').screenshot({path:path.join(path.dirname(output),`${name}-${width}-design.png`)});
   }
   views.push({width,core_readable:true,no_page_overflow:true});
  }
  await page.locator('#case-details > summary').click();
  assert.equal(await page.locator('#runs tbody tr:visible').count(),48);
  await page.locator('#model-filter').selectOption('glm-5.3-flash');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),24);
  await page.locator('#task-filter').selectOption('integral-rational');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),8);
  assert.equal(await page.locator('#filter-count').innerText(),'显示 8 / 48 个案例');
  await page.locator('#model-filter').selectOption('all');await page.locator('#task-filter').selectOption('all');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),48);
  await page.locator('#runs tbody tr').first().locator('summary').click();
  assert(await page.locator('#runs tbody tr').first().locator('pre').isVisible());
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http'))){
   if(href.startsWith('#'))assert.equal(await page.locator(href).count(),1);
   else if(!href.endsWith('service-calibration-report-manifest.json')&&!href.endsWith('.browser-qa.json'))assert(fs.existsSync(path.resolve(path.dirname(input),href)),`Missing ${href}`);
  }
  await page.locator('#evidence summary').click();assert(await page.locator('#evidence pre').isVisible());
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});
  await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  await page.emulateMedia({media:'print'});assert(!(await page.locator('#print').isVisible()));
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
  await staticPage.locator('#case-details > summary').click();
  assert.equal(await staticPage.locator('#runs tbody tr:visible').count(),48);
  assert((await staticPage.locator('body').innerText()).includes('尚不能判断哪种群体架构更有效'));
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,
   model_task_filters_reset:true,static_table_counts:true,source_links_except_postbuilt_manifest_and_qa:true,
   candidate_and_evidence_disclosure:true,print_wiring:true,print_media:true,no_javascript_core_content:true,
   page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log(fs.readFileSync(output,'utf8'));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
