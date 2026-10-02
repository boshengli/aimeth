const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const root=path.resolve(__dirname,'..');
const stem='m2-11-public-api-submission-plan-v1';
(async()=>{
const browser=await chromium.launch({headless:true,executablePath:process.env.AIMETH_BROWSER_EXECUTABLE||'/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'});
try{
 const page=await browser.newPage();const results={validated_at:new Date().toISOString(),browser:await browser.version(),viewports:[],checks:{}};
 await page.goto('file://'+root+'/milestones/'+stem+'.html');
 for(const width of [1440,390]){
  await page.setViewportSize({width,height:1000});
  const overflow=await page.evaluate(()=>({viewport:innerWidth,scroll:document.documentElement.scrollWidth}));
  if(overflow.scroll>width+1)throw Error('Overflow '+width);
  await page.screenshot({path:root+'/milestones/'+stem+'-'+width+'.png',fullPage:true});
  await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:root+'/milestones/'+stem+'-'+width+'-top.png'});
  await page.locator('#submission').screenshot({path:root+'/milestones/'+stem+'-'+width+'-submission.png'});
  results.viewports.push(overflow);
 }
 await page.locator('nav a[href="#submission"]').click();
 if(!page.url().endsWith('#submission'))throw Error('Anchor failed');
 results.checks.navigation='passed';
 const links=await page.locator('a').evaluateAll(as=>as.map(a=>a.getAttribute('href')));
 for(const href of links){if(!href.startsWith('#')&&!href.startsWith('https:')&&!href.endsWith('.validation.json')&&!href.endsWith('.manifest.json')){if(!fs.existsSync(path.resolve(root,'milestones',href)))throw Error('Missing '+href);}}
 results.checks.source_links='existing local sources resolve; validation/manifest checked after creation';
 await page.emulateMedia({media:'print'});if(await page.locator('nav').isVisible())throw Error('Print navigation not hidden');results.checks.print_css='passed';
 const nojs=await browser.newContext({javaScriptEnabled:false});const p=await nojs.newPage();await p.goto('file://'+root+'/milestones/'+stem+'.html');
 if(await p.locator('section').count()<10)throw Error('Missing content');results.checks.no_js_core='passed';
 const card=JSON.parse(fs.readFileSync(root+'/plans/public-api-submission-test-v1.json'));
 const n=card.blocks.reduce((s,b)=>s+b.requests,0),input=card.blocks.reduce((s,b)=>s+b.requests*b.max_input_tokens,0),output=card.blocks.reduce((s,b)=>s+b.requests*b.max_tokens,0);
 if(n!==76||input!==90112||output!==69632||input+output!==card.budget.max_total_tokens)throw Error('Budget mismatch');
 results.checks.budget_arithmetic={requests:n,input,output,total:input+output};
 results.scope='Report and candidate-card validation only; no model calls, runtime fault tests or scientific verification.';
 fs.writeFileSync(root+'/milestones/'+stem+'.validation.json',JSON.stringify(results,null,2)+'\n');
 console.log(JSON.stringify(results));
}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
