const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const out = path.resolve(root, process.argv[2] || 'reports/manuscript-qa/current');
const milestone = path.resolve(root, process.argv[3] || 'milestones/m2-12-manuscript-progress-v1.html');
fs.mkdirSync(path.dirname(out), {recursive:true});
if(out.includes(path.sep+'milestones'+path.sep) && fs.existsSync(out+'.validation.json')) {
  throw Error('Do not overwrite an archived milestone validation; choose a new version.');
}
(async () => {
  const browser = await chromium.launch({headless:true, executablePath:'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
  const result = {checked_at:new Date().toISOString(), browser:await browser.version(), viewports:[], checks:{}, scope:'HTML accessibility, layout and links only; not scientific validation.'};
  try {
    const context = await browser.newContext();
    const external = [], errors = [];
    await context.route('**/*', r => /^https?:/.test(r.request().url()) ? (external.push(r.request().url()),r.abort()) : r.continue());
    const page = await context.newPage(); page.on('pageerror', e=>errors.push(e.message));
    const targets = ['progress','manuscript','candidate-framings-v0','science-review-v1'].map(name=>({name,target:path.join(root,'manuscripts/aimeth',name+'.html')}));
    targets.push({name:'milestone',target:milestone});
    for (const {name,target} of targets) {
      await page.goto('file://'+target);
      for (const width of [1440,390]) {
        await page.setViewportSize({width,height:1000});
        await page.evaluate(()=>scrollTo(0,0));
        const dimensions = await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
        if(dimensions.scrollWidth>width+1) throw Error('Overflow '+name+' '+width);
        await page.screenshot({path:out+'-'+name+'-'+width+'.png'});
        if(name==='progress') await page.locator('#evidence').screenshot({path:out+'-figure-'+width+'.png'});
        result.viewports.push({name,...dimensions});
      }
      const anchors = await page.locator('nav a').evaluateAll(as=>as.map(a=>a.getAttribute('href')));
      for (const href of anchors.filter(h=>h.startsWith('#'))) {
        if(await page.evaluate(id=>document.getElementById(decodeURIComponent(id.slice(1)))?1:0,href)!==1) throw Error('Missing anchor '+href);
        const navIndex=await page.evaluate(expected=>Array.from(document.querySelectorAll('nav a')).findIndex(a=>a.getAttribute('href')===expected),href);
        if(navIndex<0)throw Error('Missing navigation link '+href);
        await page.locator('nav a').nth(navIndex).click();
        if(decodeURIComponent(new URL(page.url()).hash.slice(1))!==decodeURIComponent(href.slice(1))) throw Error('Navigation '+href);
      }
      const local = await page.locator('a').evaluateAll(as=>as.map(a=>a.getAttribute('href')).filter(h=>h&&!h.startsWith('#')&&!h.startsWith('http')));
      for(const href of local) if(!fs.existsSync(path.resolve(path.dirname(target),href))) throw Error('Missing link '+href);
      if(name==='manuscript') {
        let printed=false; await page.exposeFunction('recordPrint',()=>{printed=true;});
        await page.evaluate(()=>{window.print=()=>window.recordPrint();});
        await page.getByRole('button',{name:'Print / PDF'}).click();
        if(!printed)throw Error('Print control'); result.checks.print_control='passed';
      }
      await page.emulateMedia({media:'print'});
      if(await page.locator('nav').isVisible()) throw Error('Print navigation not hidden');
      await page.emulateMedia({media:'screen'});
    }
    const nojs=await browser.newContext({javaScriptEnabled:false}); const np=await nojs.newPage();
    await np.goto('file://'+root+'/manuscripts/aimeth/manuscript.html');
    if((await np.locator('article').innerText()).length<18000)throw Error('Missing offline body');
    await np.goto('file://'+milestone);
    if(await np.locator('#requirements').count()!==1)throw Error('Missing milestone mapping');
    if(external.length||errors.length)throw Error('Unexpected resources/errors');
    result.checks.navigation='passed';result.checks.local_links='passed';result.checks.no_js_content='passed';
    result.checks.print_layout='passed';result.external_requests=external;result.page_errors=errors;result.status='passed';result.milestone=path.relative(root,milestone);
    fs.writeFileSync(out+'.validation.json',JSON.stringify(result,null,2)+'\n'); console.log(JSON.stringify(result));
  } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
