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
   const text=await page.locator('body').innerText();
   for(const value of ['GPU08 恢复已暂停','未做群体效果比较','先恢复科研提交','格式合格、数学通过与群体组织有效','32/32','10K','无 Slurm 作业号'])assert(text.includes(value),value);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.locator('#groups tbody tr').count(),8);
   assert.equal(await page.locator('#mapping tbody tr').count(),6);
   assert.equal(await page.locator('#readiness tbody tr').count(),4);
   assert.equal(await page.locator('#cells tbody tr').count(),16);
   if(width===390)assert(await page.locator('#groups').evaluate(t=>{const p=t.parentElement;p.scrollLeft=100;const yes=p.scrollLeft>0;p.scrollLeft=0;return yes;}));
   if(width!==768){
    const stem=path.join(path.dirname(output),`m2-5-task-continuation-v1-${width}`);
    await page.screenshot({path:stem+'.png',fullPage:true});await page.screenshot({path:stem+'-top.png'});
    await page.locator('#next').screenshot({path:stem+'-readiness.png'});
   }
   views.push({width,no_page_overflow:true});
  }
  await page.locator('#case-details summary').click();assert(await page.locator('#cells').isVisible());
  await page.locator('#evidence-details summary').click();assert(await page.locator('#evidence-details pre').isVisible());
  const safe=JSON.parse(await page.locator('#evidence-details pre').innerText());
  assert.equal(safe.planned,16);assert.equal(safe.started+safe.unstarted,16);
  assert.equal(safe.frontier_proof_verified,false);assert.equal(safe.population_efficacy_verified,false);
  assert.equal(safe.slurm_job_id,null);
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http'))){
   if(href.startsWith('#'))assert.equal(await page.locator(href).count(),1);
   else if(!href.endsWith('task-continuation-report-manifest.json')&&!href.endsWith('.browser-qa.json'))assert(fs.existsSync(path.resolve(path.dirname(input),href)),href);
  }
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});
  await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  await page.emulateMedia({media:'print'});assert(!(await page.locator('#print').isVisible()));
  assert.equal(await page.locator('#groups tbody tr:visible').count(),8);
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
  assert((await staticPage.locator('body').innerText()).includes('GPU08 恢复已暂停'));
  assert.equal(await staticPage.locator('#groups tbody tr').count(),8);
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,table_counts:true,wide_tables_scroll:true,source_links_except_postbuilt_qa_and_manifest:true,case_and_evidence_disclosure:true,print_wiring_and_content:true,offline_no_javascript_core:true,page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log('M2.5 task continuation browser checks passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
