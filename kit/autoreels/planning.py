"""Auditable extractive planning. No generative claims, metrics or invented examples."""
import math
import re
import unicodedata

ORIGINAL = ('trial-reels','behind-the-person','explainer','split-screen','ranking-list','storytelling')
PHOTO = ('shape-shift','picture-stack','scene-switch','visual-notes','orbit-reel')
STYLES = ORIGINAL + PHOTO


def plain(s):
    return ''.join(c for c in unicodedata.normalize('NFKD',s.lower()) if not unicodedata.combining(c))


def validate_transcript(data, duration):
    words = data.get('words')
    if not isinstance(words,list) or not words:
        raise ValueError('Transcript has no word timestamps; automatic captions cannot be fabricated.')
    previous = -1
    for w in words:
        a,b = float(w['start']),float(w['end'])
        if not isinstance(w.get('word'),str) or not w['word'].strip() or not all(map(math.isfinite,(a,b))) or a<0 or b<a or a<previous or b>duration+.25:
            raise ValueError('Invalid, unordered or out-of-range transcript timestamps.')
        if len(w['word'])>200: raise ValueError('Transcript word exceeds supported length.')
        previous=a
    return words


def select_window(words, duration, max_seconds=25):
    if not words:
        return 0.0, min(duration,max_seconds), []
    # Whole sentence starts only; keep word-accurate source offsets.
    starts=[0]+[i+1 for i,w in enumerate(words[:-1]) if w['word'].endswith(('.', '!', '?'))]
    candidates=[]
    for i in starts:
        a=max(0,words[i]['start']-.08)
        window=[w for w in words[i:] if w['end']<=a+max_seconds]
        if not window: continue
        endings=[k for k,w in enumerate(window) if w['word'].endswith(('.', '!', '?'))]
        if endings: window=window[:endings[-1]+1]
        text=plain(' '.join(w['word'] for w in window))
        score=min(len(window),40)*.02 + sum(text.count(k) for k in ['como','por que','voce','erro','primeiro','melhor','antes','depois','mas','segredo'])
        score+=1 if '?' in text else 0
        score-=a/max(duration,1)*.1
        candidates.append((score,a,min(duration,window[-1]['end']+.12),window))
    if not candidates: raise ValueError('No complete timed words fit the requested edit duration.')
    _,a,b,ws=max(candidates,key=lambda x:x[0])
    return a,b,ws


def sentences(words):
    out=[];current=[]
    for w in words:
        current.append(w)
        if w['word'].endswith(('.', '!', '?')):
            out.append(current);current=[]
    if current:out.append(current)
    return out


def ranks(words):
    result=[]
    # Only an explicit spoken tier judgement authorizes assignment to a tier.
    for i,w in enumerate(words):
        if plain(w['word']).strip('.,:') in ('tier','nivel') and i+1<len(words):
            tier=words[i+1]['word'].upper().strip('.,!?;:')
            if tier in 'SABCDEF' and len(tier)==1 and i:
                prev=words[max(0,i-2):i]
                result.append({'name':' '.join(x['word'] for x in prev),'tier':tier,'pop':prev[0]['start'],'drop':w['start']})
    return result[:4]


def choose(words, image_count=0, max_seconds=25):
    text=plain(' '.join(w['word'] for w in words))
    scores={s:0 for s in STYLES}; reasons={s:[] for s in STYLES}
    rules={
      'trial-reels': ['voce sabia','erro','segredo','nao faca','por que','?'],
      'behind-the-person':['grafico','painel','por tras','dados'],
      'explainer':['antes','depois','compar','versus','diferenca','enquanto','lista','dicas'],
      'split-screen':['passo','primeiro','clique','tutorial','em seguida','como fazer'],
      'storytelling':['ontem','quando','historia','aconteceu','eu era','entao'],
      'ranking-list':['ranking','tier','nivel'],
      'shape-shift':['circulo','circular','mesma forma'],
      'picture-stack':['fotos','fotografias','imagens','colecao'],
      'scene-switch':['cenario','paisagem','ambiente'],
      'visual-notes':['detalhe','observe','olhe','amplie'],
      'orbit-reel':['orbita','360','ao redor','portfolio']}
    scores['trial-reels']=1
    for style,terms in rules.items():
        for term in terms:
            if term in text:scores[style]+=3;reasons[style].append(term)
    if not ranks(words): scores['ranking-list']=-1;reasons['ranking-list']=['no explicit spoken tier verdicts']
    # Photo templates last 4.2 seconds; never use them if they'd truncate a spoken sentence.
    length=words[-1]['end']-words[0]['start'] if words else 0
    needed={'shape-shift':3,'picture-stack':3,'scene-switch':3,'visual-notes':1,'orbit-reel':3}
    for style in PHOTO:
        if image_count<needed[style] or length>4.1 or max_seconds<4.2:
            scores[style]=-1;reasons[style]=['requires suitable user images and a complete sentence within the 4.2s template']
    # No fabricated analytics panel: this workflow requires at least one user image.
    if not image_count:scores['behind-the-person']=-1
    chosen=max(STYLES,key=lambda s:scores[s])
    return {'skill':chosen,'scores':scores,'evidence':reasons[chosen], 'selection_method':'deterministic Portuguese lexical rules; not an LLM quality judgement'}


def excerpt(words, count=5):
    # Remove template markup/control characters while retaining the actual words.
    return ' '.join(re.sub(r'[\x00-\x1f*<>\\{}]','',w['word']) for w in words[:count]).strip()


def spec_for(style, video, transcript, words, duration, images, out):
    title=excerpt(words,5)
    chunks=sentences(words)[:4]
    bullets=[{'text':excerpt(row,3), 'at':max(.05,row[0]['start'])} for row in chunks]
    base={'video':str(video),'transcript':str(transcript),'start':0,'end':duration,'out':str(out),'caption_top':1370}
    if style=='trial-reels':base['v1']={'title':[], 'caption_top':1370}
    elif style=='storytelling':
        rows=(chunks or [words])*3
        base.update(cards=[{'type':'text','big':excerpt(row,3),'small':''} for row in rows[:3]],title=[],zoom=1)
    elif style=='split-screen':base.update(badge='',headline='',visual={'type':'checklist','bar':'','items':bullets},video_top=-430)
    elif style=='explainer':
        base.update(title='',eye_y=750,keys=[],visual={'type':'list','items':bullets})
        split=next((i for i,w in enumerate(words) if plain(w['word']).strip('.,:') in ('depois','versus','enquanto')),None)
        if split and split+1<len(words):
            base['visual']={'type':'compare','left':{'label':'','big':excerpt(words[:split],3)},
              'right':{'label':'','big':excerpt(words[split:],3),'at':words[split]['start'],'reveal_at':words[split]['start']},'arrow_at':max(0,words[split]['start']-.3)}
    elif style=='behind-the-person':base.update(panel={'type':'image','src':str(images[0]),'scroll':0},chest=[],panel_top=240)
    elif style=='ranking-list':
        items=ranks(words)
        tiers=[t for t in 'SABCDEF' if t in {it['tier'] for it in items}]
        if not items:raise ValueError('Ranking requires explicit spoken tier verdicts.')
        base.update(title='',items=items,tiers=[[t,'#F9C74F'] for t in tiers],table_top=1060,item_top=1060)
    else:raise ValueError('Photo styles use their editable HTML templates.')
    return base,title
