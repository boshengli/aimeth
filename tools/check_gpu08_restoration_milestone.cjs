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
   for(const value of ['完整恢复尚未证实','221936','221943','91 秒','No devices were found','尚无借用前的完整快照','8 / 8 保留'])assert(text.includes(value),value);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   assert.equal(await page.locator('#observations tbody tr').count(),5);
   assert.equal(await page.locator('#readiness tbody tr').count(),4);
   if(width===390)assert(await page.locator('#observations').evaluate(t=>{const p=t.parentElement;p.scrollLeft=100;const yes=p.scrollLeft>0;p.scrollLeft=0;return yes;}));
   if(width!==768){
    const stem=path.join(path.dirname(output),`m2-4a-gpu08-restoration-v1-${width}`);
    await page.screenshot({path:stem+'.png',fullPage:true});await page.screenshot({path:stem+'-top.png'});
    await page.locator('#access').screenshot({path:stem+'-access.png'});
   }
   views.push({width,no_page_overflow:true});
  }
  await page.locator('#evidence-details summary').click();assert(await page.locator('#evidence-details pre').isVisible());
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http'))){
   if(href.startsWith('#'))assert.equal(await page.locator(href).count(),1);
   else if(!href.endsWith('gpu08-restoration-report-manifest.json')&&!href.endsWith('.browser-qa.json'))assert(fs.existsSync(path.resolve(path.dirname(input),href)),href);
  }
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});
  await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  await page.emulateMedia({media:'print'});assert(!(await page.locator('#print').isVisible()));
  assert.equal(await page.locator('#observations tbody tr:visible').count(),5);
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
  assert((await staticPage.locator('body').innerText()).includes('完整恢复尚未证实'));
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,table_counts:true,wide_tables_scroll:true,source_links_except_postbuilt_qa_and_manifest:true,evidence_disclosure:true,print_wiring_and_content:true,offline_no_javascript_core:true,page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log('Restoration assessment browser checks passed.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
