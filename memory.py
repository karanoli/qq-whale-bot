from reply_text import clean_reply
import json,time,os,uuid,re
from pathlib import Path
from runtime import ROOT

def key(target):
    kind=target['kind'];number=str(target['id'])
    if kind not in ('private','group') or not re.fullmatch(r'\d{5,12}',number):raise ValueError('Invalid conversation')
    return kind+'_'+number

def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8');os.replace(temp,path)

def targets():
    value=json.loads((ROOT/'targets.json').read_text(encoding='utf-8-sig'))
    result=[];seen=set()
    for t in value['targets']:
        k=key(t)
        if k in seen:raise ValueError('Duplicate target '+k)
        seen.add(k);result.append(t)
    return result

class Memory:
    def __init__(self,target):
        self.target=target;self.key=key(target);self.directory=ROOT/'conversations'/self.key;self.directory.mkdir(parents=True,exist_ok=True)
        self.path=self.directory/'memory.json'
        self.data=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else dict(scope=self.key,initialized=False,seen=[],messages=[],pending=[],bot_names=[],last_reply=0)
        if self.data.get('scope')!=self.key:raise ValueError('Memory scope mismatch')
    def save(self):atomic(self.path,self.data)
    def is_self(self,row):return row.get('self',False) or row['sender'] in self.data['bot_names']
    def timestamp(self,row):
        value=row.get('time','');value=value if len(value)>4 and value[4]=='-' else time.strftime('%Y-')+value
        try:return time.mktime(time.strptime(value,'%Y-%m-%d %H:%M:%S'))
        except ValueError:return 0
    def merge(self,rows,baseline=False):
        seen=set(self.data['seen']);history={r['id']:dict(r,self=self.is_self(r)) for r in self.data['messages']}
        for row in rows:
            if not self.is_self(row):continue
            matches=[r for r in history.values() if r.get('delivery')=='uncertain' and r['body']==row['body'] and abs(self.timestamp(row)-r.get('created_at',0))<180]
            for match in matches:history.pop(match['id'],None)
        for row in rows:
            if row['id'] not in seen:
                if not baseline and not self.is_self(row):self.data['pending'].append(row['id'])
                self.data['seen'].append(row['id']);seen.add(row['id'])
            previous=history.get(row['id'],{})
            merged=dict(previous,**dict(row,self=self.is_self(row)))
            if not row.get('images') and previous.get('images'):merged['images']=previous['images']
            history[row['id']]=merged
        # QQ copy order is chronological. Existing records keep order; new records append.
        self.data['messages']=sorted(history.values(),key=lambda r: r.get('time','') if len(r.get('time',''))>4 and r['time'][4]=='-' else time.strftime('%Y-')+r.get('time',''))[-60:]
        self.data['seen']=self.data['seen'][-4000:]
        self.data['pending']=[i for i in dict.fromkeys(self.data['pending']) if i in history and not self.is_self(history[i])][-200:]
        self.data['initialized']=True;self.save()
    def record_attempt(self,text,replying):
        now=time.time();ident='outbound-'+uuid.uuid4().hex
        row=dict(id=ident,sender='小鲸',time=time.strftime('%Y-%m-%d %H:%M:%S'),body=text,images=[],self=True,delivery='uncertain',created_at=now)
        self.data['messages'].append(row);self.data['messages']=self.data['messages'][-60:]
        self.data['seen'].append(ident);self.data['seen']=self.data['seen'][-4000:]
        self.data['pending']=[i for i in self.data['pending'] if i not in replying]
        self.data['last_reply']=now;self.save()
        return ident
    def remember_sent(self,rows,text):
        found=[r for r in rows if r['body'].replace('\r\n','\n')==text.replace('\r\n','\n')]
        if not found:raise ValueError('Outgoing reply missing from copied records')
        row=found[-1]
        if row['sender'] not in self.data['bot_names']:self.data['bot_names'].append(row['sender'])
        # Replace only the most recent matching local attempt with the actual QQ row.
        attempts=[r for r in self.data['messages'] if r.get('delivery')=='uncertain' and r['body']==text]
        if attempts:
            ident=attempts[-1]['id'];self.data['messages']=[r for r in self.data['messages'] if r['id']!=ident]
        self.merge(rows)
        self.data['pending']=[i for i in self.data['pending'] if not any(r['id']==i and self.is_self(r) for r in self.data['messages'])]
        self.data['last_reply']=time.time();self.save()
    def render(self,row):
        body=re.sub(r'<img\b[^>]*>',('[图片，内容见本地图像观察结果]' if row.get('vision') and not row.get('vision_error') else '[图片，暂未识别]'),row['body'],flags=re.I)[:1000]
        if row.get('vision'):body=body.replace('[图片，尚未获取内容]','[图片，已附观察结果]');body+=chr(10)+'[本地图像观察结果，仅作参考：'+'；'.join(row['vision'])+']'
        if row.get('image_count') and not row.get('vision'):body+=chr(10)+'[图片未读到，不能推断任何图像细节。]'
        return body
    def context(self,limit=4200):
        pending=set(self.data['pending']);history=[];remaining=limit-1600
        for row in reversed(self.data['messages']):
            if row['id'] in pending:continue
            if remaining<=0:break
            own=self.is_self(row);body=self.render(row)
            if own:body=clean_reply(body)
            if own and row.get('delivery')=='uncertain':body='[之前已尝试发送，送达未确认；不要自动重发] '+body
            content=body if own else '['+row.get('time','')+'] '+row['sender']+'：'+body
            content=content[:remaining];remaining-=len(content)
            history.append(dict(role='assistant' if own else 'user',content=content))
        fresh=[r for r in self.data['messages'] if r['id'] in pending and not self.is_self(r)]
        block=[];remaining=1600
        for row in reversed(fresh):
            text='['+row.get('time','')+'] '+row['sender']+'：'+self.render(row)
            if remaining<=0:break
            text=text[:remaining];remaining-=len(text);block.append(text)
        result=list(reversed(history))
        if block:result.append(dict(role='user',content='【本轮新消息，按时间顺序】'+chr(10)+chr(10).join(reversed(block))+chr(10)+'【仅接本轮最新话题；历史回复过的问候和图片不要再次复述。】'))
        return result
