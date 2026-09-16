#!/usr/bin/env node
const {chromium}=require('playwright');
const fs=require('fs'),path=require('path'),assert=require('assert');
const {pathToFileURL}=require('url');
(async()=>{
 const input=path.resolve(process.argv[2]),output=path.resolve(process.argv[3]);
 const browser=await chromium.launch({headless:true,executablePath:process.env.AIMETH_BROWSER_EXECUTABLE});
 const errors=[],requests=[],views=[];
 try{
  const context=await browser.newContext();await context.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(input).href);
   assert.equal(await page.locator('h1').count(),1);
   assert.equal(await page.locator('#repository').getAttribute('href'),'https://github.com/boshengli/aimeth');
   assert(await page.locator('body').innerText().then(t=>t.includes('32 / 32')&&t.includes('公网发布已完成')&&t.includes('没有 H20')));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
   if(width!==768)await page.screenshot({path:path.join(path.dirname(output),`m1-1-publication-v1-${width}.png`),fullPage:true});
   views.push({width,core_readable:true,no_page_overflow:true});
  }
  const hrefs=await page.locator('a').evaluateAll(a=>a.map(x=>x.getAttribute('href')));
  for(const href of hrefs.filter(h=>h&&!h.startsWith('http')&&!h.startsWith('#')))assert(fs.existsSync(path.resolve(path.dirname(input),href)),`Missing linked file ${href}`);
  await page.locator('#ci-evidence summary').click();assert(await page.locator('#ci-evidence pre').isVisible());
  await page.evaluate(()=>{window.__printed=false;window.print=()=>window.__printed=true;});await page.locator('#print').click();assert(await page.evaluate(()=>window.__printed));
  await page.emulateMedia({media:'print'});assert(!(await page.locator('#print').isVisible()));
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
  await nojs.route(/^https?:\/\//,r=>{requests.push(r.request().url());return r.abort();});
  const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);assert(await staticPage.locator('body').innerText().then(t=>t.includes('公网发布已完成')&&t.includes('934cce6')));
  assert.equal(errors.length,0);assert.equal(requests.length,0);
  fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),views,repository_link:true,local_file_links:true,evidence_disclosure:true,print_wiring:true,print_media:true,no_javascript_core_content:true,page_errors:errors,http_runtime_resources:requests},null,2)+'\n');
  console.log(fs.readFileSync(output,'utf8'));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
