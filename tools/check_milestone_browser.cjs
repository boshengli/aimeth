const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('playwright');
const target=path.resolve(process.argv[2]||'milestones/m1-foundation-v1.html');
const out=path.resolve(process.argv[3]||'reports/milestone-browser-check');
fs.mkdirSync(out,{recursive:true});
(async()=>{
 const options={headless:true};
 if(process.env.AIMETH_BROWSER_EXECUTABLE)options.executablePath=process.env.AIMETH_BROWSER_EXECUTABLE;
 const browser=await chromium.launch(options);
 try{
  const context=await browser.newContext({viewport:{width:1440,height:1000},deviceScaleFactor:1});
  const external=[]; const errors=[];
  await context.route('**/*',route=>{const url=route.request().url();if(/^https?:/.test(url)){external.push(url);return route.abort();}return route.continue();});
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto('file://'+target);await page.screenshot({path:out+'/desktop-top.png'});
  const results={report_path:target,browser:await browser.version(),topologies:[],viewports:[],page_errors:errors,external_resource_requests:external};
  for(const arm of ['S','I','L','X']){
   await page.locator('[data-arm="'+arm+'"]').click();
   const graph=await page.locator('#topology').evaluate(svg=>({arm:svg.dataset.arm,nodes:svg.querySelectorAll('[data-node]').length,edges:[...svg.querySelectorAll('[data-edge]')].map(l=>({a:Number(l.dataset.from),b:Number(l.dataset.to),type:l.dataset.edge}))}));
   if(graph.nodes!==(arm==='S'?1:32))throw new Error('Wrong node count: '+arm);
   if(graph.edges.length!==(arm==='L'||arm==='X'?32:0))throw new Error('Wrong edge count: '+arm);
   if(arm==='L'||arm==='X'){
    const degree=Array(32).fill(0),seen=new Set();
    for(const e of graph.edges){degree[e.a]++;degree[e.b]++;const key=[e.a,e.b].sort((a,b)=>a-b).join(',');if(seen.has(key)||e.a===e.b)throw new Error('Invalid duplicate/self edge');seen.add(key);}
    if(degree.some(d=>d!==2))throw new Error('Degree preservation failed');
    graph.degree_min=Math.min(...degree);graph.degree_max=Math.max(...degree);
   }
   graph.cross_edges=graph.edges.filter(e=>e.type==='cross').length;graph.edge_count=graph.edges.length;delete graph.edges;
   if(arm==='L'&&graph.cross_edges!==0||arm==='X'&&graph.cross_edges!==8)throw new Error('Wrong cross-edge count');
   results.topologies.push(graph);
  }
  await page.locator('.explorer').screenshot({path:out+'/desktop-topology.png'});
  for(const width of [1440,768,390]){
   await page.setViewportSize({width,height:1000});
   const overflow=await page.evaluate(()=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth}));
   if(overflow.scrollWidth>overflow.width+1)throw new Error('Page overflow: '+JSON.stringify(overflow));
   results.viewports.push(overflow);
   if(width===390){await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:out+'/mobile-top.png'});await page.locator('.explorer').screenshot({path:out+'/mobile-topology.png'});}
  }
  await page.setViewportSize({width:1440,height:1000});
  await page.locator('#requirements').screenshot({path:out+'/requirements.png'});
  const details=page.locator('#sources details').first();await details.locator('summary').click();
  if(!await details.getAttribute('open').then(v=>v!==null))throw new Error('Evidence detail did not open');
  let printed=false;await page.exposeFunction('recordPrint',()=>{printed=true;});await page.evaluate(()=>{window.print=()=>window.recordPrint();});await page.locator('#print-report').click();
  if(!printed)throw new Error('Print button not wired');
  await page.emulateMedia({media:'print'});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:out+'/print-top.png'});
  results.print_css_checked=true;results.print_button_connected=printed;results.evidence_detail_opened=true;
  const nojs=await browser.newContext({javaScriptEnabled:false,viewport:{width:1000,height:800}});const fallback=await nojs.newPage();await fallback.goto('file://'+target);
  if(await fallback.locator('#topology circle').count()!==32||await fallback.locator('tbody tr').count()!==8)throw new Error('No-JS content missing');
  results.no_js_core_content=true;
  if(errors.length||external.length)throw new Error('Unexpected JS errors or runtime network dependency');
  results.status='passed';results.scope='HTML layout, interaction, offline-content checks only; no cluster or mathematical validation.';
  fs.writeFileSync(out+'/browser-qa.json',JSON.stringify(results,null,2)+'\n');
  console.log(JSON.stringify(results,null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
