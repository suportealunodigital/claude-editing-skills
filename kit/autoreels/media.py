"""Strict media validation and deterministic caption geometry/audio QA."""
import hashlib
import json
import math
from pathlib import Path
import subprocess

import numpy as np
from PIL import ImageFont

KIT=Path(__file__).resolve().parents[1]
FONT=KIT/'fonts/TikTokSans.ttf'
SAFE=(120,240,960,1460)


def run(args, timeout=600, log=None):
    result=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=timeout)
    if log:
        Path(log).write_bytes(result.stdout+b'\n'+result.stderr)
    if result.returncode:
        # Never include command arguments (may contain private paths/URLs).
        raise ValueError(f'{Path(str(args[0])).name} failed with exit {result.returncode}; see private task log.' if log else f'{Path(str(args[0])).name} rejected media or failed (exit {result.returncode}).')
    return result.stdout


def probe(path, count=False):
    args=['ffprobe','-v','error','-protocol_whitelist','file,pipe']
    if count:args+=['-count_frames']
    return json.loads(run(args+['-show_streams','-show_format','-of','json',path],timeout=300))


def validate_input(path, max_bytes, max_duration=7200):
    path=Path(path)
    if not path.is_file() or not 0<path.stat().st_size<=max_bytes:raise ValueError('Input file missing, empty or above configured size limit.')
    with path.open('rb') as f:
        header=f.read(32)
    # ISO-BMFF MP4/MOV only. No playlists, archives or remote protocol wrappers.
    if header[4:8] not in (b'ftyp',b'wide',b'mdat',b'moov',b'free'):raise ValueError('Not an MP4/MOV container.')
    p=probe(path)
    if 'mov' not in p['format'].get('format_name','').split(','):raise ValueError('Only MP4/MOV containers are supported.')
    videos=[s for s in p['streams'] if s['codec_type']=='video' and not s.get('disposition',{}).get('attached_pic')]
    audio=[s for s in p['streams'] if s['codec_type']=='audio']
    d=float(p['format']['duration'])
    if not math.isfinite(d) or not .5<=d<=max_duration:raise ValueError('Unsupported media duration (0.5 seconds to 2 hours).')
    if len(videos)!=1 or len(audio)!=1:raise ValueError('Require exactly one video and one audio stream; silent videos are not speech inputs.')
    v=videos[0]
    from fractions import Fraction
    fps=Fraction(v.get('avg_frame_rate') or v.get('r_frame_rate','0/1'))
    if not 0<fps<=240:raise ValueError('Unsupported input frame rate (maximum 240 fps).')
    if not 16<=v['width']<=8192 or not 16<=v['height']<=8192:raise ValueError('Unsupported dimensions.')
    if v['width']*v['height']>34_000_000:raise ValueError('Input resolution exceeds decode resource limit.')
    run(['ffmpeg','-v','error','-xerror','-protocol_whitelist','file,pipe','-i',path,'-map','0:v:0','-map','0:a:0','-f','null','-'],timeout=min(3600,max(60,d*2)))
    return p


def prepare(video,start,end,out):
    run(['ffmpeg','-v','error','-xerror','-y','-protocol_whitelist','file,pipe','-ss',f'{start:.6f}','-i',video,'-t',f'{end-start:.6f}',
         '-map','0:v:0','-map','0:a:0','-vf','scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2,fps=30,setsar=1',
         '-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-c:a','aac','-ar','48000','-af','aresample=async=1:first_pts=0','-map_metadata','-1','-movflags','+faststart',out])


def escape_ass(text):
    return text.replace('\\','').replace('{','').replace('}','').replace('\n',' ').replace('\r',' ')


def stamp(t):
    cs=int(round(t*100));return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'


def captions(words,title,duration,path):
    events=[];layout=[]
    def add(text,a,b,y,size,kind):
        text=escape_ass(text)
        while size>=24:
            font=ImageFont.truetype(str(FONT),size)
            bbox=font.getbbox(text,stroke_width=5)
            width=bbox[2]-bbox[0];height=bbox[3]-bbox[1]+20
            if width<=800 and height<=100:break
            size-=2
        if width>800 or height>100:raise ValueError('Caption cannot fit safe area; shorten unsupported word.')
        box=[540-width/2-8,y-8,540+width/2+8,y+height+8]
        if not(SAFE[0]<=box[0] and SAFE[1]<=box[1] and box[2]<=SAFE[2] and box[3]<=SAFE[3]):raise ValueError('Caption safe area violation.')
        if not 0<=a<b<=duration+.01:raise ValueError('Caption timestamp outside output.')
        style='Title' if kind=='title' else 'Caption'
        events.append(f'Dialogue: 0,{stamp(a)},{stamp(b)},{style},,0,0,0,,{{\\an8\\pos(540,{y})\\fs{size}}}{text}')
        layout.append({'text':text,'start':a,'end':b,'bbox':box,'kind':kind,'font_size':size})
    if title:add(title,0,duration,260,54,'title')
    # A maximum of three real spoken words, with word-level karaoke highlighting.
    for i in range(0,len(words),3):
        group=words[i:i+3]
        for j,w in enumerate(group):
            a=max(0,w['start']);b=min(duration, group[j+1]['start'] if j+1<len(group) else w['end'])
            if b<=a:continue
            text=' '.join(x['word'] for x in group)
            add(text,a,b,1340,60,'caption')
            # The actual word marker is injected only after geometry measurement.
            parts=[escape_ass(x['word']) for x in group]
            parts[j]='{\\c&H00E6FF&}'+parts[j]+'{\\c&HFFFFFF&}'
            events[-1]=events[-1][:-len(escape_ass(text))]+' '.join(parts)
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Title,TikTok Sans,54,&H00FFFFFF,&H00FFFFFF,&H00151515,&H60000000,-1,0,0,0,100,100,0,0,1,4,1,8,120,120,260,1
Style: Caption,TikTok Sans,60,&H00FFFFFF,&H00FFFFFF,&H00151515,&H60000000,-1,0,0,0,100,100,0,0,1,5,1,8,120,120,1340,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    Path(path).write_text(header+'\n'.join(events)+'\n')
    return layout


def pcm(path):
    return np.frombuffer(run(['ffmpeg','-v','error','-i',path,'-map','0:a:0','-ac','1','-ar','8000','-f','f32le','-']),dtype='<f4')


def file_digest(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda:f.read(1024**2),b''):digest.update(chunk)
    return digest.hexdigest()


def quality(output,reference,expected,layout):
    p=probe(output,count=True);v=next(s for s in p['streams'] if s['codec_type']=='video');a=next(s for s in p['streams'] if s['codec_type']=='audio')
    duration=float(p['format']['duration']);vd=float(v['duration']);ad=float(a['duration'])
    from fractions import Fraction
    if (v['width'],v['height'])!=(1080,1920) or Fraction(v['avg_frame_rate'])!=30:raise ValueError('Output format is not 1080x1920 at 30 fps.')
    if abs(duration-expected)>.12 or abs(vd-ad)>.08 or abs(float(v.get('start_time',0))-float(a.get('start_time',0)))>.05:raise ValueError('Output duration or AV timing validation failed.')
    frames=int(v['nb_read_frames'])
    if abs(frames-round(expected*30))>2:raise ValueError('Output decoded frame count mismatch.')
    run(['ffmpeg','-v','error','-xerror','-i',output,'-f','null','-'])
    src=pcm(reference);dst=pcm(output);n=min(len(src),len(dst));src=src[:n];dst=dst[:n]
    power=float(np.sqrt(np.mean(dst.astype('float64')**2)))
    if not math.isfinite(power) or power<.0001:raise ValueError('Output audio is silent or effectively silent.')
    correlation=float(np.dot(src.astype('float64'),dst)/max(1e-12,np.linalg.norm(src.astype('float64'))*np.linalg.norm(dst.astype('float64'))))
    if correlation<.90:raise ValueError('Output voice waveform does not match the prepared source audio.')
    return {'passed':True,'duration':duration,'video_duration':vd,'audio_duration':ad,'decoded_frames':frames,
            'fps':30,'width':1080,'height':1920,'audio_rms':power,'audio_correlation':correlation,
            'caption_events':len([x for x in layout if x['kind']=='caption']),
            'safe_rect':list(SAFE),'safe_geometry':'font-measured generated overlays only; face/graphic occlusion still needs contact-sheet review',
            'sha256':file_digest(output)}
