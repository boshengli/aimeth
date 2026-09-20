const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
(async()=>{
 const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]),name='m2-2-role-routing-v1';
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
   assert(text.includes('1 通过 · 1 错误 · 4 格式不合规 · 2 截断未完成'));
   assert(text.includes('195,352')&&text.includes('196060')&&text.includes('1,238,453'));
   assert(text.includes('尚无 10K 实际推理'));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.locator('#diagnostic tbody tr').count(),4);
   assert.equal(await page.locator('#comparison tbody tr').count(),2);
   assert.equal(await page.locator('#scale-table tbody tr').count(),5);
   assert.equal(await page.locator('#runs tbody tr:visible').count(),16);
   assert.equal(await page.locator('#design svg').count(),2);
   if(width===390){for(const id of ['runs','scale-table']){assert(await page.locator('#'+id).evaluate(t=>{const c=t.parentElement;c.scrollLeft=150;const ok=c.scrollLeft>0;c.scrollLeft=0;return ok;}));}}
   if(width!==768){
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}.png`),fullPage:true});
    await page.screenshot({path:path.join(path.dirname(output),`${name}-${width}-top.png`)});
    await page.locator('#scale').screenshot({path:path.join(path.dirname(output),`${name}-${width}-scale.png`)});
   }
   views.push({width,core_readable:true,no_page_overflow:true});
  }
  await page.locator('#model-filter').selectOption('glm');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),8);
  await page.locator('#arm-filter').selectOption('H');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),4);
  assert.equal(await page.locator('#filter-count').innerText(),'显示 4 / 16 个群体');
  await page.locator('#model-filter').selectOption('deepseek');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),4);
  assert((await page.locator('#runs tbody tr:visible').first().innerText()).includes('未启动'));
  await page.emulateMedia({media:'print'});
  assert.equal(await page.locator('#runs tbody tr:visible').count(),16);
  assert(!(await page.locator('#print').isVisible()));
  await page.emulateMedia({media:'screen'});
  await page.locator('#model-filter').selectOption('all');await page.locator('#arm-filter').selectOption('all');
  assert.equal(await page.locator('#runs tbody tr:visible').count(),16);
  await page.locator('#runs tbody tr').first().locator('summary').click();
  assert(await page.locator('#runs tbody tr').first().locator('pre').isVisible());
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http'))){
   if(href.startsWith('#'))assert.equal(await page.locator(href).count(),1);
   else if(!href.endsWith('role-pilot-report-manifest.json')&&!href.endsWith('.browser-qa.json'))assert(fs.existsSync(path.resolve(path.dirname(input),href)),`Missing ${href}`);
  }
  await page.locator('#evidence summary').click();assert(await page.locator('#evidence pre').isVisible());
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});
  await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
  assert.equal(await staticPage.locator('#runs tbody tr:visible').count(),16);
  assert((await staticPage.locator('body').innerText()).includes('本轮不支持 H/F 优劣判断'));
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,
   model_arm_filters_reset:true,unstarted_populations_retained:true,static_table_counts:true,wide_tables_horizontal_scroll:true,
   source_links_except_postbuilt_manifest_and_qa:true,candidate_and_evidence_disclosure:true,
   print_wiring:true,print_restores_full_denominator:true,no_javascript_core_content:true,
   page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log(fs.readFileSync(output,'utf8'));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
