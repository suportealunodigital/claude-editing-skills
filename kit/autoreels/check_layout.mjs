// Read-only geometry audit of native template text at every output frame.
import {createRequire} from 'node:module';
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
const [cliPath, composition, output, executablePath] = process.argv.slice(2);
const require=createRequire(path.resolve(cliPath));
const puppeteer=require('puppeteer-core');
let browser,server;
const base=path.resolve(composition);
server=http.createServer((request,response)=>{
  try {
    const file=path.resolve(base,'.'+decodeURIComponent(new URL(request.url,'http://localhost').pathname));
    if(!file.startsWith(base+path.sep)||!fs.statSync(file).isFile()){response.writeHead(404);response.end();return;}
    const mime={'.html':'text/html','.js':'application/javascript','.json':'application/json','.woff2':'font/woff2','.ttf':'font/ttf','.mp4':'video/mp4','.webm':'video/webm','.jpg':'image/jpeg','.png':'image/png'};
    response.writeHead(200,{'Content-Type':mime[path.extname(file)]||'application/octet-stream','Content-Length':fs.statSync(file).size});
    fs.createReadStream(file).pipe(response);
  } catch {response.writeHead(404);response.end();}
});
await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
const origin='http://127.0.0.1:'+server.address().port;
try {
  browser=await puppeteer.launch({executablePath,headless:true});
  const page=await browser.newPage();
  await page.setViewport({width:1080,height:1920,deviceScaleFactor:1});
  await page.setRequestInterception(true);
  page.on('request',request=>(request.url().startsWith(origin+'/')||/^(data:|blob:)/.test(request.url()))?request.continue():request.abort());
  await page.goto(origin+'/index.html',{waitUntil:'load',timeout:30000});
  await page.evaluate(()=>document.fonts.ready);
  const result=await page.evaluate(()=>{
    const root=document.querySelector('[data-composition-id]');
    const duration=Number(root.dataset.duration),frames=Math.ceil(duration*30),timeline=window.__timelines?.main;
    if(!timeline)throw Error('Missing GSAP timeline');
    const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);
    const nodes=[];let node;
    while((node=walker.nextNode()))if(node.textContent.trim()&&!['SCRIPT','STYLE'].includes(node.parentElement.tagName))nodes.push(node);
    const findings=[];let visibleChecks=0;
    for(let frame=0;frame<frames;frame++){
      timeline.seek(frame/30,false);
      for(const n of nodes){
        let e=n.parentElement,hidden=false;
        for(let p=e;p;p=p.parentElement){
          const s=getComputedStyle(p);
          if(s.display==='none'||s.visibility==='hidden'||Number(s.opacity)<.05){hidden=true;break;}
        }
        if(hidden)continue;
        const range=document.createRange();range.selectNodeContents(n);
        for(const r of range.getClientRects()){
          if(!r.width||!r.height)continue;
          visibleChecks++;
          if(r.left<100||r.right>980||r.top<220||r.bottom>1500){
            if(findings.length<30)findings.push({frame,text:n.textContent.slice(0,120),rect:[r.left,r.top,r.right,r.bottom]});
          }
        }
      }
    }
    return {passed:!findings.length,frames,visibleTextChecks:visibleChecks,findings,scope:'native DOM text, not text embedded in images or face occlusion'};
  });
  fs.writeFileSync(output,JSON.stringify(result,null,2));
  if(!result.passed)process.exitCode=2;
} catch(error) {
  fs.writeFileSync(output,JSON.stringify({passed:false,error:'Browser/layout audit failed; no private paths or text logged to console.'}));
  fs.writeFileSync(output+'.debug.log',String(error));
  process.exitCode=1;
} finally {if(browser)await browser.close();if(server)server.closeAllConnections();if(server)await new Promise(resolve=>server.close(resolve));}
