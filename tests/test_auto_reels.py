"""Real media/stream bounds plus mocked Drive protocol tests; no external credentials."""
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit,parse_qs

import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'kit'))
from autoreels.transfer import Storage,TransferError,drive_id,check_url,check_network,DRIVE_HOSTS,CHUNK
from autoreels.planning import choose,validate_transcript,select_window,spec_for,STYLES
from autoreels.media import captions,validate_input,quality
import transcribe

FID='unit_test_file_12345'
FOLDER='unit_test_folder_12345'

class FileStream(httpx.SyncByteStream):
    def __init__(self,path):self.path=path
    def __iter__(self):
        with self.path.open('rb') as f:
            yield from iter(lambda:f.read(1024**2),b'')

class DriveTransfer(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.policy=self.root/'no-policy.json'
    def tearDown(self):self.tmp.cleanup()
    def store(self,handler,max_bytes=2*1024**3):
        return Storage(max_bytes,client=httpx.Client(transport=httpx.MockTransport(handler),follow_redirects=False),policy_path=self.policy)
    def test_drive_file_links_and_url_security(self):
        for link in [f'https://drive.google.com/file/d/{FID}/view',f'https://drive.google.com/open?id={FID}',f'https://drive.google.com/uc?id={FID}&export=download']:
            self.assertEqual(drive_id(link)[0],FID)
        for url in ['http://drive.google.com/a','https://github.com/a','https://127.0.0.1/a','https://drive.google.com.evil.test/a','https://user:pass@drive.google.com/a','https://drive.google.com:444/a','https://drive.google.com/a#secret']:
            with self.assertRaises(TransferError):check_url(url,DRIVE_HOSTS)
    def test_real_network_policy_blocks_unapproved_drive(self):
        self.policy.write_text(json.dumps({'http_network_policy':{'type':'restricted','egress_rules':[{'host':'github.com'}]}}))
        with self.assertRaisesRegex(TransferError,'does not allow'):check_network('drive.google.com',self.policy)
    def test_real_mp4_above_32_mib_over_mocked_stream(self):
        # The container and decoder are real. Only the cloud HTTP transport is mocked.
        raw=self.root/'large.mov'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=128x128:r=30:d=1','-f','lavfi','-i','sine=frequency=440:duration=1','-c:v','libx264','-c:a','aac','-f','mov',str(raw)],check=True)
        padding=34*1024**2-raw.stat().st_size
        with raw.open('ab') as f:
            f.write(struct.pack('>I4s',padding,b'free'))
            for _ in range((padding-8)//65536):f.write(bytes(65536))
            f.write(bytes((padding-8)%65536))
        size=raw.stat().st_size
        self.assertGreater(size,32*1024**2)
        store=self.store(lambda r:httpx.Response(200,headers={'Content-Type':'video/quicktime','Content-Length':str(size)},stream=FileStream(raw)))
        out=self.root/'download.mp4'
        got=store.download_drive(f'https://drive.google.com/file/d/{FID}/view',out)
        self.assertEqual(got['bytes'],size);self.assertEqual(out.stat().st_size,size)
        validate_input(out,2*1024**3)
    def test_stream_over_limit_cleans_partial_file(self):
        class Stream(httpx.SyncByteStream):
            def __iter__(self):yield b'x'*1024;yield b'y'*1024
        store=self.store(lambda r:httpx.Response(200,stream=Stream()),max_bytes=1500)
        dst=self.root/'input.mp4'
        with self.assertRaises(TransferError):store.download_drive(f'https://drive.google.com/open?id={FID}',dst)
        self.assertFalse(dst.exists());self.assertFalse(dst.with_suffix('.part').exists())
    def test_drive_large_file_confirmation(self):
        seen=[]
        def handler(req):
            q=parse_qs(urlsplit(str(req.url)).query);seen.append(q)
            if 'confirm' not in q:
                page=f'<form id="download-form" action="https://drive.usercontent.google.com/download"><input type="hidden" name="id" value="{FID}"><input type="hidden" name="confirm" value="yes"></form>'
                return httpx.Response(200,headers={'Content-Type':'text/html'},text=page)
            return httpx.Response(200,content=b'video-fixture')
        result=self.store(handler).download_drive(f'https://drive.google.com/file/d/{FID}/view',self.root/'a.mp4')
        self.assertEqual(result['bytes'],13);self.assertEqual(len(seen),2)
    def test_private_login_page_does_not_change_sharing(self):
        seen=[]
        def handler(req):seen.append(req.method);return httpx.Response(200,headers={'Content-Type':'text/html'},text='<html>Sign in</html>')
        with self.assertRaisesRegex(TransferError,'authentication'):self.store(handler).download_drive(f'https://drive.google.com/open?id={FID}',self.root/'a.mp4')
        self.assertEqual(seen,['GET'])
    def test_oauth_bearer_not_forwarded_on_redirect(self):
        seen=[]
        def handler(req):
            seen.append((req.url.host,req.headers.get('authorization')))
            if req.url.path.endswith('/'+FID) and 'fields' in req.url.params:
                return httpx.Response(200,json={'mimeType':'video/mp4','capabilities':{'canDownload':True}})
            if req.url.host=='www.googleapis.com':return httpx.Response(302,headers={'Location':'https://drive.usercontent.google.com/download?id='+FID})
            return httpx.Response(200,content=b'media')
        self.store(handler).download_drive(f'https://drive.google.com/open?id={FID}',self.root/'a.mp4',token='unit-test-only')
        self.assertEqual(seen[-1],('drive.usercontent.google.com',None))
    def test_redirect_to_unapproved_host_is_rejected(self):
        with self.assertRaises(TransferError):
            self.store(lambda r:httpx.Response(302,headers={'Location':'https://evil.test/video'})).download_drive(f'https://drive.google.com/open?id={FID}',self.root/'a.mp4')
    def test_resumable_upload_chunks_and_no_sharing_mutation(self):
        data=self.root/'reel.mp4';data.write_bytes(b'x'*(CHUNK+123));seen=[]
        def handler(req):
            seen.append((req.method,req.url.path,req.headers.get('content-range')))
            if req.method=='GET':return httpx.Response(200,json={'mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True},'permissions':[{'type':'user'}]})
            if req.method=='POST':return httpx.Response(200,headers={'Location':'https://www.googleapis.com/upload/drive/v3/files?upload_id=unit-test'})
            if req.headers['content-range'].startswith('bytes 0-'):return httpx.Response(308,headers={'Range':f'bytes=0-{CHUNK-1}'})
            return httpx.Response(200,json={'id':FID})
        result=self.store(handler).upload_drive(data,'unit-test-only',FOLDER)
        self.assertEqual(result['id'],FID)
        self.assertEqual(len([x for x in seen if x[0]=='PUT']),2)
        self.assertTrue(all('permissions' not in x[1] for x in seen))
    def test_public_destination_folder_is_refused(self):
        def handler(req):return httpx.Response(200,json={'mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True},'permissions':[{'type':'anyone'}]})
        with self.assertRaisesRegex(TransferError,'public-folder'):self.store(handler).upload_drive(self.root/'never-read.mp4','unit-test-only',FOLDER)

class PlanningAndQuality(unittest.TestCase):
    def words(self,text):return [{'word':w,'start':i*.2,'end':(i+1)*.2} for i,w in enumerate(text.split())]
    def test_all_eleven_styles_can_be_selected_with_evidence(self):
        cases={'trial-reels':'você sabia segredo','behind-the-person':'gráfico painel dados','explainer':'antes depois comparação',
          'split-screen':'primeiro clique tutorial','ranking-list':'ranking café tier S','storytelling':'ontem aconteceu história',
          'shape-shift':'círculo circular mesma forma','picture-stack':'fotos fotografias coleção','scene-switch':'cenário paisagem ambiente',
          'visual-notes':'detalhe observe amplie','orbit-reel':'órbita 360 portfolio'}
        self.assertEqual(set(cases),set(STYLES))
        for style,text in cases.items():
            with self.subTest(style=style):self.assertEqual(choose(self.words(text),3)['skill'],style)
    def test_no_assets_or_tier_evidence_rules_out_invented_visuals(self):
        p=choose(self.words('ranking fotos gráfico'),0)
        self.assertNotIn(p['skill'],('ranking-list','behind-the-person','picture-stack'))
    def test_invalid_timestamps_rejected(self):
        for words in [[{'word':'x','start':float('nan'),'end':1}],[{'word':'x','start':2,'end':1}],[]]:
            with self.assertRaises(ValueError):validate_transcript({'words':words},3)
    def test_captions_fit_safe_area_and_escape_markup(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'captions.ass'
            layout=captions(self.words('Olá {mundo} teste.'),'Olá mundo',2,out)
            self.assertGreater(len(layout),1)
            self.assertNotIn('{mundo}',out.read_text())
            self.assertTrue(all(120<=x['bbox'][0] and x['bbox'][2]<=960 and x['bbox'][3]<=1460 for x in layout))
    def test_transcript_call_uses_pt_word_timestamps_and_literal_prompt(self):
        class Response:
            def model_dump(self):return {'words':[]}
        from unittest.mock import MagicMock
        client=MagicMock();client.audio.transcriptions.create.return_value=Response()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'a.flac';p.write_bytes(b'unit-test')
            transcribe.call(client,p,'pt')
        kw=client.audio.transcriptions.create.call_args.kwargs
        self.assertEqual(kw['language'],'pt');self.assertEqual(kw['timestamp_granularities'],['word','segment'])
        self.assertIn('português brasileiro',kw['prompt'])
    def test_window_and_spec_are_extractive(self):
        words=self.words('primeiro clique. depois salve.')
        start,end,ws=select_window(words,2,2)
        spec,title=spec_for('split-screen',Path('/input.mp4'),Path('/truth.json'),ws,end-start,[],Path('/out.mp4'))
        for item in spec['visual']['items']:self.assertIn(item['text'],' '.join(w['word'] for w in words))


class RealMediaQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name)
        for name,freq in [('source',440),('different',1100)]:
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i','color=c=blue:s=1080x1920:r=30:d=0.6',
              '-f','lavfi','-i',f'sine=frequency={freq}:duration=0.6','-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-ar','48000',str(cls.root/(name+'.mp4'))],check=True)
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_real_decoded_frames_audio_and_duration(self):
        result=quality(self.root/'source.mp4',self.root/'source.mp4',.6,[])
        self.assertEqual(result['decoded_frames'],18);self.assertGreater(result['audio_correlation'],.99)
    def test_wrong_audio_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'waveform'):quality(self.root/'different.mp4',self.root/'source.mp4',.6,[])
    def test_html_and_missing_audio_are_rejected(self):
        bad=self.root/'html.mp4';bad.write_text('<html>Sign in</html>')
        with self.assertRaises(ValueError):validate_input(bad,2*1024**3)
        with self.assertRaisesRegex(ValueError,'one audio'):validate_input(ROOT/'assets/style-showcase/explainer.mp4',2*1024**3)

class RendererFailureContract(unittest.TestCase):
    def test_failed_renderer_does_not_count_existing_output_as_success(self):
        import reel
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out.mp4';comp=SimpleNamespace(dir=Path(tmp))
            def failed(*a,**kw):
                out.write_bytes(b'partial')
                return SimpleNamespace(returncode=1,stdout='test failure',stderr='')
            with patch('reel.subprocess.run',side_effect=failed),patch.dict('os.environ',{'HYPERFRAMES_CLI':'/test/cli.js'}):
                with self.assertRaises(SystemExit):reel.Comp.render(comp,out)
            self.assertFalse(out.exists())

if __name__=='__main__':unittest.main()
