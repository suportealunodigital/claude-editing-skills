#!/usr/bin/env python3
"""One command: ingest, transcribe, choose a skill, edit, validate and privately deliver."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import re
import os
from pathlib import Path
import shutil
import sys
import tempfile
import uuid

from autoreels.transfer import Storage, MAX_BYTES, TransferError, check_network
from autoreels.media import validate_input, prepare, probe, captions, quality, run
from autoreels.planning import validate_transcript, select_window, choose, spec_for, PHOTO, excerpt
from autoreels.rendering import render_original, render_photo, finish

ROOT=Path(__file__).resolve().parents[1]


def write_json(path,data):
    path.write_text(json.dumps(data,indent=2,ensure_ascii=False))


def doctor():
    names=['ffmpeg','ffprobe','node','npm','chromium']
    hosts=['api.groq.com','drive.google.com','drive.usercontent.google.com','www.googleapis.com']
    network={}
    for host in hosts:
        try:check_network(host);network[host]='allowed or policy unavailable; endpoint access still requires a real request'
        except TransferError as e:network[host]=str(e)
    return {'tools':{x:shutil.which(x) for x in names},'groq_key_present':bool(os.getenv('GROQ_API_KEY')),
      'drive_oauth_token_present':bool(os.getenv('GOOGLE_DRIVE_ACCESS_TOKEN')),'network':network,
      'max_download_bytes':MAX_BYTES,'limit_32_mib':False,
      'model_mobilenetv3_present':(ROOT/'kit/models/rvm_mobilenetv3_fp32.onnx').is_file(),
      'environment_identity':'This process inspects the task-bound executor only; it cannot switch to a published environment by name.',
      'artifact_api':'No automatic task artifact registration API is assumed. Return workspace file or authorized Drive upload.'}


def deliver(job_id, folder_env):
    if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',job_id) or not folder_env:
        raise ValueError('Use an existing auto-reels job ID and --drive-folder-env.')
    root=(ROOT/'.autoreels').resolve();job=(root/job_id).resolve()
    if job.parent!=root:raise ValueError('Invalid private job location.')
    storage=Storage()
    try:
        report=json.loads((job/'report.json').read_text())
        if not report.get('quality',{}).get('passed'):raise ValueError('This job has no validated output to deliver.')
        original_hash=report['quality']['sha256']
        checked=quality(job/'reel.mp4',job/'prepared.mp4',report['quality']['duration'],json.loads((job/'caption-layout.json').read_text()))
        if checked['sha256']!=original_hash:raise ValueError('Rendered output changed after validation.')
        uploaded=storage.upload_drive(job/'reel.mp4',os.getenv('GOOGLE_DRIVE_ACCESS_TOKEN'),os.getenv(folder_env))
        report['delivery']['drive']=uploaded
        report['delivery']['sharing']='unchanged; inherits authorized destination folder permissions'
        report['status']=('controlled-fixture-render-passed' if report['transcription'].get('controlled_test_fixture') else
                          'render-test-passed' if report['transcription']['source']=='explicitly-skipped-render-test' else 'completed')
        report.pop('error',None);write_json(job/'report.json',report)
        print(json.dumps({'status':'delivered','drive':uploaded,'report':str(job/'report.json')},ensure_ascii=False));return 0
    except Exception as exc:
        safe=str(exc) if isinstance(exc,ValueError) and 'https://' not in str(exc) else 'Private delivery failed; sensitive details omitted.'
        print(json.dumps({'status':'delivery-failed','error':safe}),file=sys.stderr);return 1
    finally:storage.close()


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('video',nargs='?',type=Path,help='local uploaded MP4/MOV')
    ap.add_argument('--url-env',help='environment variable holding the Drive file URL (do not log its value)')
    ap.add_argument('--images',type=Path,nargs='*',default=[])
    ap.add_argument('--max-mib',type=int,default=2048)
    ap.add_argument('--max-seconds',type=float,default=25)
    ap.add_argument('--sha256',help='optional expected SHA256 of downloaded/local input')
    ap.add_argument('--transcript',type=Path,help='existing truthful word-timed transcript; never fabricate it')
    ap.add_argument('--no-transcription',action='store_true',help='explicit render-only test: no captions or speech-based choice; not end-to-end speech validation')
    ap.add_argument('--drive-folder-env',help='environment variable with authorized destination Drive folder ID')
    ap.add_argument('--deliver-job',help='retry private Drive delivery of an already validated job ID')
    ap.add_argument('--doctor',action='store_true')
    args=ap.parse_args(argv)
    if args.doctor:print(json.dumps(doctor(),indent=2,ensure_ascii=False));return 0
    if args.deliver_job:
        if not args.drive_folder_env or not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}',args.deliver_job):ap.error('Use a valid job ID and --drive-folder-env.')
        return deliver(args.deliver_job,args.drive_folder_env)
    if bool(args.video)==bool(args.url_env):ap.error('Provide exactly one local video or --url-env.')
    if args.no_transcription and args.transcript:ap.error('--no-transcription cannot be combined with --transcript.')
    if not 1<=args.max_mib<=8192 or not .5<=args.max_seconds<=60:ap.error('Byte limit must be 1–8192 MiB; edit duration 0.5–60 seconds.')
    os.umask(0o077)
    root=ROOT/'.autoreels';root.mkdir(mode=0o700,exist_ok=True)
    job=root/(datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-'+uuid.uuid4().hex[:8]);job.mkdir(mode=0o700)
    manifest={'version':1,'status':'running','job':job.name,'private':True,'published':False}
    storage=Storage(args.max_mib*1024**2)
    try:
        if args.url_env:
            url=os.getenv(args.url_env)
            if not url:raise ValueError('Input URL environment variable is absent; no URL value is logged.')
            source=job/'input.mp4'
            manifest['ingest']=storage.download_drive(url,source,os.getenv('GOOGLE_DRIVE_ACCESS_TOKEN'))
        else:
            source=args.video.resolve()
            if source.suffix.lower() not in ('.mp4','.mov'):raise ValueError('Only local MP4/MOV files are accepted.')
            if not source.is_file() or source.stat().st_size>storage.max_bytes:raise ValueError('Missing input or file above configured limit.')
            digest=hashlib.sha256()
            with source.open('rb') as f:
                for chunk in iter(lambda:f.read(1024**2),b''):digest.update(chunk)
            manifest['ingest']={'bytes':source.stat().st_size,'sha256':digest.hexdigest(),'transport':'local'}
        if args.sha256 and args.sha256.lower()!=manifest['ingest']['sha256']:raise ValueError('Input SHA256 mismatch.')
        meta=validate_input(source,storage.max_bytes);total=float(meta['format']['duration'])
        manifest['input_validated']=True
        if args.no_transcription:
            words=[];manifest['transcription']={'source':'explicitly-skipped-render-test','speech_validated':False}
        else:
            if args.transcript:
                data=json.loads(args.transcript.read_text());manifest['transcription']={'source':'user-existing-transcript','speech_validated':False}
                if str(data.get('provenance','')).startswith('CONTROLLED SYNTHETIC TEST'):
                    manifest['transcription']['controlled_test_fixture']=True
            else:
                if not os.getenv('GROQ_API_KEY'):raise ValueError('GROQ_API_KEY is absent in this task executor. Select the published environment with the real secret; no replacement key is created.')
                check_network('api.groq.com')
                from transcribe import transcribe
                tp=job/'source.transcript.json'
                transcribe(source,tp,language='pt')
                data=json.loads(tp.read_text());manifest['transcription']={'source':'groq-whisper-large-v3','language':'pt-BR (Groq language code pt)','speech_validated':True}
            words=validate_transcript(data,total)
        start,end,window=select_window(words,total,args.max_seconds)
        images=[]
        if len(args.images)>12:raise ValueError('At most twelve user images are accepted.')
        from PIL import Image
        Image.MAX_IMAGE_PIXELS=25_000_000
        for n,image in enumerate(args.images):
            if not image.is_file() or image.stat().st_size>25*1024**2:raise ValueError('User image missing or exceeds 25 MiB.')
            dst=job/f'user-image-{n}.jpg'
            with Image.open(image) as im:
                if im.width*im.height>25_000_000:raise ValueError('User image exceeds 25 megapixels.')
                im.load();im.convert('RGB').resize((1080,1080)).save(dst,quality=92)
            images.append(dst)
        local_words=[dict(w,start=round(max(0,w['start']-start),3),end=round(w['end']-start,3)) for w in window]
        plan=choose(local_words,len(images),args.max_seconds)
        if plan['skill'] in PHOTO:
            if start+4.24<=total:end=start+4.24
            else:plan=choose(local_words,0,args.max_seconds);plan['photo_rejected']='source too short for complete 4.2s template'
        manifest['plan']={**plan,'source_start':start,'source_end':end}
        normalized=job/'prepared.mp4';prepare(source,start,end,normalized)
        transcript=job/'edit.transcript.json';write_json(transcript,{'words':local_words,'source_start':start})
        style=plan['skill'];styled=job/'styled.mp4'
        if style in PHOTO:
            title=excerpt(local_words,5);styled=render_photo(style,normalized,images,job)
        else:
            spec,title=spec_for(style,normalized,transcript,local_words,end-start,images,styled)
            sp=job/'edit-spec.json';write_json(sp,spec);styled=render_original(style,sp,job)
        d=float(probe(styled)['format']['duration'])
        visible=[dict(w,end=min(w['end'],d)) for w in local_words if w['start']<d and min(w['end'],d)>w['start']]
        layout=captions(visible,title,d,job/'captions.ass');write_json(job/'caption-layout.json',layout)
        final=job/'reel.mp4';finish(styled,normalized,job/'captions.ass',final,job)
        manifest['quality']=quality(final,normalized,d,layout)
        manifest['quality']['native_text_layout']=json.loads((job/'hyperframes.layout.json').read_text())
        manifest['quality']['caption_source']='none (explicit test)' if args.no_transcription else manifest['transcription']['source']
        import reel
        reel.sheet(final,job/'contact-sheet.jpg',5)
        manifest['delivery']={'local_file':str(final),'contact_sheet':str(job/'contact-sheet.jpg'),'artifact_registration':'client-dependent; no public upload'}
        if args.drive_folder_env:
            folder=os.getenv(args.drive_folder_env)
            uploaded=storage.upload_drive(final,os.getenv('GOOGLE_DRIVE_ACCESS_TOKEN'),folder)
            manifest['delivery']['drive']=uploaded
            manifest['delivery']['sharing']='unchanged; inherits authorized destination folder permissions'
        manifest['status']=('render-test-passed' if args.no_transcription else
          'controlled-fixture-render-passed' if manifest['transcription'].get('controlled_test_fixture') else 'completed')
        write_json(job/'report.json',manifest)
        print(json.dumps({'status':manifest['status'],'skill':style,'mp4':str(final),'report':str(job/'report.json')},ensure_ascii=False))
        return 0
    except (Exception,SystemExit) as exc:
        # HTTP clients and SDK exceptions can echo signed URLs or secrets.
        # Only our own ValueErrors are safe; third-party exceptions are summarized.
        safe=str(exc) if isinstance(exc,ValueError) and not any(x in str(exc) for x in ('https://','Bearer ','gsk_')) else type(exc).__name__+' in processing; sensitive details omitted'
        manifest.update(status='failed',error=safe)
        write_json(job/'report.json',manifest)
        print(json.dumps({'status':'failed','error':safe,'report':str(job/'report.json')},ensure_ascii=False),file=sys.stderr)
        return 1
    finally:storage.close()

if __name__=='__main__':sys.exit(main())
