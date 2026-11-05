"""Adapters call the actual eleven original builders/templates, using pinned HF."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from html.parser import HTMLParser

from .media import run, probe
from .planning import PHOTO

ROOT=Path(__file__).resolve().parents[2]
KIT=ROOT/'kit'
HF_VERSION='0.8.214'


def cli():
    path=os.environ.get('HYPERFRAMES_CLI')
    bundled=KIT/'.hyperframes/node_modules/hyperframes/dist/cli.js'
    if not path and bundled.exists():path=str(bundled)
    command=['node',path] if path else ['npx','--yes','hyperframes@'+HF_VERSION]
    version=run(command+['--version'],timeout=90).decode().strip()
    if version!=HF_VERSION:raise ValueError(f'auto-reels requires HyperFrames {HF_VERSION}; run kit/setup-auto.sh.')
    return command


def render_comp(comp,out,log):
    command=cli()
    run(command+['check',comp,'--json'],timeout=150,log=Path(log).with_suffix('.check.json'))
    cli_path=command[1] if command[0]=='node' else KIT/'.hyperframes/node_modules/hyperframes/dist/cli.js'
    browser=os.environ.get('HYPERFRAMES_BROWSER_PATH') or shutil.which('chromium')
    if not browser:raise ValueError('A system Chromium is required for native text geometry QA.')
    run(['node',KIT/'autoreels/check_layout.mjs',cli_path,comp,Path(log).with_suffix('.layout.json'),browser],timeout=120,log=Path(log).with_suffix('.layout.log'))
    run(command+['render',comp,'-o',out,'--fps','30','--quality','looks','--workers','2'],timeout=900,log=log)
    run(['ffmpeg','-v','error','-xerror','-i',out,'-f','null','-'])


def render_original(style,spec_path,job):
    import reel
    path=ROOT/'skills'/style/'build.py'
    spec=importlib.util.spec_from_file_location('autoreels_style_'+style.replace('-','_'),path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    saved=reel.Job.finish
    result=[]
    def finish(j,c,out=None):
        # Keep the original visual grammar; generate all titles/captions centrally
        # so their word timings and safe rectangles can be checked consistently.
        hidden='#ttl,#h1,#yt,#rc0,.kc,.tk,.rc,.kx,.hz,.pk'
        if style=='split-screen':hidden+=',.sc'
        c.css.append(hidden+'{display:none!important}')
        c.css.append('.tcard .tb{font-size:40px!important;overflow-wrap:anywhere}.li span{font-size:40px!important;max-width:690px;overflow-wrap:anywhere}')
        if style=='storytelling':c.css.append('.sc{top:420px!important}.sc .big{font-size:42px!important}')
        if style=='ranking-list':c.css.append('.itm .nm{font-size:40px!important}')
        c.write()
        html=c.dir/'index.html'
        source=html.read_text()
        source=re.sub(r'<audio\b.*?</audio>','',source,flags=re.S)
        html.write_text(source)
        # Avoid duplicating large media in HyperFrames proxy caches.
        (c.dir/'hyperframes.json').write_text(json.dumps({'media':{'autoProxy':False}}))
        target=Path(out or j.out)
        render_comp(c.dir,target,job/'hyperframes.log')
        result.append(target)
        return target
    reel.Job.finish=finish
    try:
        if style=='trial-reels':
            # Automatic single-MP4 delivery uses the original v1. The original
            # standalone /trial-reels continues producing all three alternatives.
            j=reel.Job(spec_path,style);j.finish(module.v1(j,j.get('v1',{})))
        else:module.main(spec_path)
    finally:reel.Job.finish=saved
    return result[0]


class StripSampleText(HTMLParser):
    def __init__(self):super().__init__(convert_charrefs=False);self.parts=[];self.preserve=[]
    def handle_starttag(self,tag,attrs):
        self.parts.append(self.get_starttag_text())
        if tag in ('script','style'):self.preserve.append(tag)
    def handle_startendtag(self,tag,attrs):self.parts.append(self.get_starttag_text())
    def handle_endtag(self,tag):
        self.parts.append('</'+tag+'>')
        if self.preserve and self.preserve[-1]==tag:self.preserve.pop()
    def handle_data(self,data):
        if self.preserve:
            if self.preserve[-1]=='script':data=re.sub(r"textContent\s*:\s*'(?:\\.|[^'])*'", "textContent:''", data)
            self.parts.append(data)
    def handle_decl(self,decl):self.parts.append('<!'+decl+'>')
    def handle_entityref(self,name):
        if self.preserve:self.parts.append('&'+name+';')


def render_photo(style,video,images,job):
    from cutout import cutout
    template=(ROOT/'skills'/style/'template.html').read_text()
    keys=set(re.findall(r'(?:src|href)="assets/([^"\s]+)"',template))
    overrides={};n=0
    for name in sorted(keys):
        if name.endswith('.mp4'):overrides[name]=str(video)
        elif name.endswith('.webm'):
            alpha=job/'person.webm'
            if not alpha.exists():cutout(video,alpha)
            overrides[name]=str(alpha)
        else:
            if not images:raise ValueError('Photo styles require user-supplied images; sample images are never substituted.')
            overrides[name]=str(images[n%len(images)]);n+=1
    out=job/'styled.mp4';sp=job/'photo-spec.json'
    sp.write_text(json.dumps({'out':str(out),'media_start':0,'assets':overrides}))
    run([sys.executable,ROOT/'skills'/style/'build.py',sp,'--prepare-only'],log=job/'prepare.log')
    comp=job/'styled.composition'
    parser=StripSampleText();parser.feed((comp/'index.html').read_text())
    source=''.join(parser.parts)
    # Consistent center crop, not automatic subject/match-cut tracking.
    if style=='shape-shift':
        source=source.replace('</style>','#photo-stage img{width:100%!important;height:100%!important;left:0!important;top:0!important;object-fit:cover!important}</style>')
    (comp/'index.html').write_text(source)
    render_comp(comp,out,job/'hyperframes.log')
    return out


def finish(styled,source,ass,out,job):
    duration=float(probe(styled)['format']['duration'])
    # All filenames are generated by us, so filter escaping does not contain user
    # input or signed URLs. Run from private job cwd with a relative ASS path.
    args=['ffmpeg','-v','error','-xerror','-y','-i',str(styled),'-i',str(source),'-map','0:v:0','-map','1:a:0',
          '-vf',f'ass=filename=captions.ass:fontsdir={KIT / "fonts"}',
          '-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p','-r','30',
          '-c:a','aac','-ar','48000','-af','aresample=async=1:first_pts=0','-t',str(duration),
          '-map_metadata','-1','-movflags','+faststart',str(out)]
    result=subprocess.run(args,cwd=job,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=600)
    (job/'finalize.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:raise ValueError('Final audio/caption encoding failed; see private finalize.log.')
    return duration
