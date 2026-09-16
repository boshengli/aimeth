const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
(async()=>{
 const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
 const name='m2-1-cluster-pilot-v1';
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
   assert(text.includes('13 通过 · 9 错误 · 4 格式不合规 · 6 未完成'));
   assert(text.includes('145,837')&&text.includes('190043'));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.locator('#summary-table tbody tr').count(),8);
   assert.equal(await page.locator('#runs tbody tr:visible').count(),32);
   if(width!==768){
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}.png`),fullPage:true});
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}-top.png`)});
   }
   views.push({width,core_readable:true,no_page_overflow:true});
  }
  await page.locator('#model-filter').selectOption('glm-5.3-flash');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),16);
  await page.locator('#task-filter').selectOption('integral-rational');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),8);
  assert.equal(await page.locator('#filter-count').innerText(),'显示 8 / 32 个群体');
  await page.locator('#model-filter').selectOption('all');await page.locator('#task-filter').selectOption('all');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),32);
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http'))){
   if(href.startsWith('#'))assert.equal(await page.locator(href).count(),1);
   else if(href!=='../cluster-report-manifest.json')assert(fs.existsSync(path.resolve(path.dirname(input),href)),`Missing ${href}`);
  }
  await page.locator('#evidence summary').click();assert(await page.locator('#evidence pre').isVisible());
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});
  await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  await page.emulateMedia({media:'print'});assert(!(await page.locator('#print').isVisible()));
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
  assert.equal(await staticPage.locator('#runs tbody tr:visible').count(),32);
  assert((await staticPage.locator('body').innerText()).includes('尚不能比较组织优劣'));
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,
   filters_model_task_and_reset:true,static_table_counts:true,source_links_except_postbuilt_manifest:true,
   evidence_disclosure:true,print_wiring:true,print_media:true,no_javascript_core_content:true,
   page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log(fs.readFileSync(output,'utf8'));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
