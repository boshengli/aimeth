#!/usr/bin/env node
// Isolated browser regression checks for the HTML artifact; no personal browser profile.
const {chromium}=require('playwright');
const fs=require('fs');const path=require('path');const assert=require('assert');const {pathToFileURL}=require('url');
(async()=>{
  const input=path.resolve(process.argv[2]);const output=path.resolve(process.argv[3]);
  const browser=await chromium.launch({headless:true,executablePath:process.env.AIMETH_BROWSER_EXECUTABLE});
  const checks=[];const errors=[];const runtimeRequests=[];
  try {
    const context=await browser.newContext();
    await context.route(/^https?:\/\//,route=>{runtimeRequests.push(route.request().url());return route.abort();});
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    for(const width of [1440,768,390]){
      await page.setViewportSize({width,height:1000});await page.goto(pathToFileURL(input).href);
      assert.equal(await page.locator('h1').count(),1);
      assert(await page.locator('body').innerText().then(s=>s.includes('20,000')&&s.includes('100,001')&&s.includes('尚未就绪')));
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),'horizontal page overflow');
      await page.screenshot({path:path.join(path.dirname(output),`${path.basename(input,".html")}-${width}.png`),fullPage:true});
      if(width===1440||width===390) await page.screenshot({path:path.join(path.dirname(output),`${path.basename(input,".html")}-${width}-top.png`)});
      checks.push({viewport_width:width,core_content:true,no_page_overflow:true});
    }
    await page.selectOption('#event-filter','message');assert.equal(await page.locator('#event-rows tr:visible').count(),8);assert.equal(await page.locator('#event-count').textContent(),'8 条事件');
    await page.selectOption('#event-filter','checkpoint');assert.equal(await page.locator('#event-rows tr:visible').count(),8);
    await page.selectOption('#event-filter','attempt');assert.equal(await page.locator('#event-rows tr:visible').count(),16);
    await page.selectOption('#event-filter','all');assert.equal(await page.locator('#event-rows tr:visible').count(),41);
    await page.locator('summary').first().click();assert(await page.locator('details').first().getAttribute('open')!==null);
    await page.evaluate(()=>{window.__printCalled=false;window.print=()=>{window.__printCalled=true;};});
    await page.locator('#print').click();assert(await page.evaluate(()=>window.__printCalled));
    await page.emulateMedia({media:'print'});assert.equal(await page.locator('#print').isVisible(),false);
    const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:390,height:1000}});
    await nojs.route(/^https?:\/\//,route=>{runtimeRequests.push(route.request().url());return route.abort();});
    const staticPage=await nojs.newPage();await staticPage.goto(pathToFileURL(input).href);
    assert.equal(await staticPage.locator('#event-rows tr').count(),41);assert(await staticPage.locator('#outcome').innerText().then(s=>s.includes('公网 GitHub')));
    assert.equal(errors.length,0);assert.equal(runtimeRequests.length,0);
    fs.writeFileSync(output,JSON.stringify({schema_version:'1.0',status:'passed',browser_version:browser.version(),checks,event_filters_checked:['all:41','message:8','checkpoint:8','attempt:16'],evidence_disclosure:true,print_button:true,print_media:true,no_javascript_core_content:true,page_errors:errors,http_runtime_resources:runtimeRequests,scope:'Isolated local Chrome; artifact rendering and controls, not scientific verification'},null,2)+'\n');
    console.log(fs.readFileSync(output,'utf8'));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exit(1);});
