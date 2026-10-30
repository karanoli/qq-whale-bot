from reply_text import clean_reply
import json,time,traceback,threading,queue,re,sys
from pathlib import Path
import requests,win32event,win32api,winerror
from desktop import ROOT,check_stop,pause,Stopped,DesktopError
from transport import Transport
from memory import Memory,atomic,targets,key
from storage import rotate_log
from vision import Vision
from reasoning import choose
from runtime import load_config,api_headers,chat_payload
CFG=load_config()
def log(event,target=None,**data):
    row=dict(time=time.strftime('%Y-%m-%d %H:%M:%S'),event=event,**data)
    if target:row['scope']=key(target)
    rotate_log(ROOT/'bot-log.jsonl')
    with (ROOT/'bot-log.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    atomic(ROOT/'bot-status.json',row)
    if target:atomic(ROOT/'conversations'/key(target)/'status.json',row)
def generate(memory):
    from native_vision import fresh_rows,context,system_prompt,NO_REPLY,note_image,image_question
    target=memory.target;fresh=fresh_rows(memory)
    native=CFG.get('vision',{}).get('mode')=='native'
    if not native:raise RuntimeError('vision.mode must be native; disable vision.enabled for text-only APIs')
    profile=choose(memory,CFG);started=time.monotonic()
    messages,image_meta=context(memory,limit=1500 if profile['effort']=='high' else 2400,enable_images=CFG.get('vision',{}).get('enabled',False))
    has_images=any(r.get('image_count') or r.get('images') for r in fresh)
    latest='\n'.join(r.get('body','') for r in fresh[-3:])
    if has_images and not image_meta['image_attached']:
        plain=re.sub(r'<img\b[^>]*>|\[图片[^\]]*\]','',latest,flags=re.I).strip()
        if not plain:
            atomic(memory.directory/'last-model-reply.json',dict(scope=memory.key,text=None,source='unasked-image-unavailable',image_meta=image_meta))
            return None
        if image_question(plain):
            text='这张没读到，先不瞎猜。'
            atomic(memory.directory/'last-model-reply.json',dict(scope=memory.key,text=text,source='asked-image-unavailable',image_meta=image_meta))
            return text
    persona=Path(CFG['persona']).read_text(encoding='utf-8')
    slang=Path(CFG['slang']).read_text(encoding='utf-8')[:2200]
    system=system_prompt(persona,slang,target,has_images)
    result=queue.Queue()
    def work():
        try:
            with requests.Session() as s:
                s.trust_env=CFG.get('trust_env',False)
                r=s.post(CFG['endpoint'],json=chat_payload(CFG,[dict(role='system',content=system)]+messages,profile),headers=api_headers(CFG),timeout=(8,profile['timeout_seconds']));r.raise_for_status();result.put((True,r.json()))
        except Exception as e:result.put((False,str(e)))
    threading.Thread(target=work,daemon=True).start()
    while True:
        check_stop()
        try:ok,value=result.get(timeout=.2);break
        except queue.Empty:pass
    if not ok:raise RuntimeError(value)
    choice=value['choices'][0]
    if choice.get('finish_reason')=='length':raise RuntimeError('Reply truncated; not sent')
    raw=re.sub(r'<think>.*?</think>','',choice['message'].get('content') or '',flags=re.S).strip()
    skipped=has_images and raw==NO_REPLY
    if re.search(r'NO[_ ]?REPLY',raw,re.I) and not skipped:raise RuntimeError('Invalid silence marker; not sent')
    text=None if skipped else clean_reply(raw)
    if not skipped and (not text or len(text)>CFG['max_reply_chars']):raise RuntimeError('Reply empty or exceeds limit; not sent')
    note_image(memory,image_meta);memory.save()
    atomic(memory.directory/'last-model-reply.json',dict(scope=memory.key,text=text,decision='silent' if skipped else 'reply',usage=value.get('usage'),reasoning=profile,image_meta=image_meta,elapsed_seconds=round(time.monotonic()-started,2)))
    return text

def process(target,transport):
    process_started=time.monotonic()
    memory=Memory(target)
    memory.data['bot_names']=list(dict.fromkeys(memory.data['bot_names']+CFG.get('self_names',[])))
    rows=transport.collect()
    if not memory.data['initialized'] or memory.data.get('reader_version')!='uia-1' or getattr(transport,'read_baseline',False):
        memory.merge(rows,baseline=True);memory.data['pending']=[];memory.data['reader_version']='uia-1';memory.save();log('baseline_ready',target,count=len(rows),reader='uia');return
    memory.merge(rows)
    if not memory.data['pending'] or time.time()-max(memory.data['last_reply'],memory.data.get('last_image_decision',0))<target.get('cooldown_seconds',CFG['cooldown_seconds']):return
    replying=list(memory.data['pending']);log('generating',target,incoming=len(replying))
    vision_started=time.monotonic();Vision(CFG).enrich(memory,transport);vision_seconds=time.monotonic()-vision_started
    text=generate(memory)
    if text is None:
        memory.data['pending']=[i for i in memory.data['pending'] if i not in replying]
        memory.data['last_image_decision']=time.time()
        memory.save();log('image_silent',target,incoming=len(replying),vision_seconds=round(vision_seconds,2));return
    # Persist a send attempt at the click boundary, before fallible readback.
    log('sending',target,reply=text)
    def attempted():
        memory.record_attempt(text,replying);log('send_attempted',target,reply=text)
    after=transport.send(text,on_attempt=attempted)
    memory.remember_sent(after,text);log('delivered',target,reply=text,vision_seconds=round(vision_seconds,2),turn_seconds=round(time.monotonic()-process_started,2))

def main():
    legacy_mutex=win32event.CreateMutex(None,False,'Local\\AIchatVisualBot')
    if win32api.GetLastError()==winerror.ERROR_ALREADY_EXISTS:raise RuntimeError('旧版小鲸正在操作QQ，请先停止旧版。')
    mutex=win32event.CreateMutex(None,False,'Local\\QQWhaleBot')
    if win32api.GetLastError()==winerror.ERROR_ALREADY_EXISTS:raise RuntimeError('Visual bot already running')
    pool={};retry={};log('multi_target_started')
    while True:
        check_stop()
        for target in targets():
            if not target.get('enabled',True):continue
            scope=key(target)
            if time.monotonic()<retry.get(scope,0):continue
            signature=json.dumps(target,ensure_ascii=False,sort_keys=True)
            if scope not in pool or pool[scope][0]!=signature:pool[scope]=(signature,Transport(dict(CFG,target=target)))
            try:process(target,pool[scope][1])
            except Stopped:raise
            except Exception:
                log('conversation_error',target,error=traceback.format_exc());retry[scope]=time.monotonic()+30
        pause(CFG['poll_seconds'])
if __name__=='__main__':
    try:main()
    except Stopped:log('stopped')
    except Exception:log('error',error=traceback.format_exc());raise
