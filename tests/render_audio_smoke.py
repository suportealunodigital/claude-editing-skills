#!/usr/bin/env python3
"""Explicit real audio/render integration test, not a Groq or Google Drive test.

FFmpeg flite generates isolated known words; timestamps come from exact PCM sample
boundaries, not fabricated recognition. All media stays in ignored .autoreels/.
Requires installed auto runtime, flite, Chromium, and browser execution permission.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import wave

ROOT=Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--explainer',action='store_true',help='also exercise Python ONNX cutout in the real explainer builder')
    ap.add_argument('--photo',action='store_true',help='also exercise automatic picture-stack with explicit bundled test images')
    args=ap.parse_args()
    parent=ROOT/'.autoreels';parent.mkdir(mode=0o700,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='controlled-fixture-',dir=parent) as tmp:
        root=Path(tmp);words=[];raw=bytearray();rate=16000
        if args.photo and args.explainer:ap.error('Choose one integration fixture.')
        text=(['fotos','fotografias','colecao'] if args.photo else ['antes','depois','comparacao'] if args.explainer else ['primeiro','clique','depois','salve'])
        for i,word in enumerate(text):
            wav=root/f'word-{i}.wav'
            subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'flite=text={word}:voice=kal','-ac','1','-ar',str(rate),str(wav)],check=True)
            with wave.open(str(wav)) as w:data=w.readframes(w.getnframes())
            a=len(raw)/2/rate;raw.extend(data);b=len(raw)/2/rate
            words.append({'word':word+('.' if i==len(text)-1 else ''),'start':a,'end':b})
            raw.extend(bytes(int(rate*.12)*2))
        # Photo source must have a complete 4.24 second window.
        duration=max(4.3,len(raw)/2/rate) if args.photo else len(raw)/2/rate
        raw.extend(bytes(max(0,int(duration*rate*2)-len(raw))))
        with wave.open(str(root/'speech.wav'),'wb') as w:
            w.setnchannels(1);w.setsampwidth(2);w.setframerate(rate);w.writeframes(raw)
        transcript=root/'controlled.transcript.json'
        transcript.write_text(json.dumps({'words':words,'provenance':'CONTROLLED SYNTHETIC TEST: flite words, timestamps measured from concatenated PCM samples. Not Groq recognition.'}))
        video=root/'source.mp4'
        subprocess.run(['ffmpeg','-v','error','-y','-f','lavfi','-i',f'testsrc2=size=540x960:rate=30:duration={duration}',
          '-i',str(root/'speech.wav'),'-map','0:v','-map','1:a','-c:v','libx264','-preset','fast','-c:a','aac','-shortest',str(video)],check=True)
        command=[str(ROOT/'auto-reels'),str(video),'--transcript',str(transcript)]
        if args.photo:
            command+=['--images']+[str(ROOT/'assets/style-showcase'/x) for x in ['orange.jpg','record.jpg','camera.jpg']]
        proc=subprocess.run(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        if proc.returncode:
            sys.stderr.write(proc.stderr);return proc.returncode
        response=json.loads(proc.stdout.splitlines()[-1]);report=json.loads(Path(response['report']).read_text())
        assert report['status']=='controlled-fixture-render-passed'
        assert report['quality']['passed'] and report['quality']['caption_events']>0
        assert report['quality']['audio_correlation']>.9
        assert report['plan']['skill']==('picture-stack' if args.photo else 'explainer' if args.explainer else 'split-screen'),report['plan']
        print(json.dumps(response,ensure_ascii=False))
    return 0

if __name__=='__main__':sys.exit(main())
