from reply_text import clean_reply
import re,json,hashlib,uuid,html
import numpy as np,cv2
import win32api,win32con
from desktop import QQDesktop,DesktopError,Stopped,ROOT,center,norm,key,chord,pause,unicode_text
from clipboard_util import preserved_clipboard,put,get
HEADER=re.compile(r'^(.+?):\s*((?:\d{4}-)?\d{1,2}-\d{1,2}\s+\d{1,2}:\d{2}:\d{2})\s*$',re.M)
IMG=re.compile(r'<img\b[^>]*src="(file://[^"]+)"[^>]*>',re.I)
def parse_batch(text,target):
    matches=list(HEADER.finditer(text)); rows=[]
    for i,m in enumerate(matches):
        body=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip()
        sender,stamp=m.group(1).strip(),m.group(2)
        identity='\0'.join((target,sender,stamp,body))
        rows.append(dict(id=hashlib.sha256(identity.encode()).hexdigest(),sender=sender,time=stamp,body=body,images=[html.unescape(x[7:]) for x in IMG.findall(body)]))
    return rows
class Transport:
    def __init__(self,cfg):
        self.cfg=cfg;self.target=dict(cfg['target']);self.lookup_name=self.target['name'];self.q=QQDesktop();self.verified_group_id=None;self.header_aliases=set()
        self.output=ROOT/'conversations'/(self.target['kind']+'_'+self.target['id']);self.output.mkdir(parents=True,exist_ok=True)
    def header(self,text):
        import unicodedata
        return re.sub(r'\(\d+人?\)$','',norm(unicodedata.normalize('NFKC',text)))
    def title_line(self,d):
        hits=[x for x in d['lines'] if 390<=min(p[0] for p in x['box'])<450 and 45<center(x)[1]<110 and len(x['text'])>=2 and x['confidence']>.8]
        if len(hits)!=1:raise DesktopError('Chat title is not uniquely readable')
        return hits[0]
    def verify(self,d):
        w,h=d['size']
        if list(d['size'])!=self.cfg['window_size']:raise DesktopError('QQ window size changed; recalibration required')
        title=self.header(self.title_line(d)['text']);expected=self.header(self.target['name'])
        matched=title==expected
        if self.target['kind']=='group' and self.verified_group_id==self.target['id']:
            from difflib import SequenceMatcher
            matched=title in self.header_aliases or max(SequenceMatcher(None,title,x).ratio() for x in self.header_aliases|{expected})>=.90
        if not matched:raise DesktopError('Target chat header not verified')
        if self.target['kind']=='group':
            sidebar=any(('群聊成员' in x['text'] or '群公告' in x['text']) and center(x)[0]>w*.79 for x in d['lines'])
            if sidebar:self.chat_right=int(w*.8)
            elif not hasattr(self,'chat_right'):raise DesktopError('Group members panel layout changed; recalibration required')
        else:self.chat_right=w
        return w,h
    def identity_session(self):
        import win32process,win32api,win32con
        pid=win32process.GetWindowThreadProcessId(self.q.hwnd)[1]
        handle=win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION,False,pid)
        try:created=win32process.GetProcessTimes(handle)['CreationTime'].isoformat()
        finally:handle.Close()
        return dict(hwnd=self.q.hwnd,pid=pid,created=created)
    def group_card(self,d):
        import win32gui,win32process
        from PIL import ImageGrab
        title=self.title_line(d);title_alias=self.header(title['text'])
        pid=win32process.GetWindowThreadProcessId(self.q.hwnd)[1]
        def cards():
            found=[]
            def visit(h,_):
                if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h)=='资料卡' and win32process.GetWindowThreadProcessId(h)[1]==pid:found.append(h)
            win32gui.EnumWindows(visit,None)
            return found
        def close_cards():
            old=[]
            def visit(h,_):
                if win32gui.GetWindowText(h)=='资料卡' and win32process.GetWindowThreadProcessId(h)[1]==pid:old.append(h)
            win32gui.EnumWindows(visit,None)
            for h in old:win32gui.PostMessage(h,win32con.WM_CLOSE,0,0)
            for _ in range(20):
                if not cards():return
                pause(.1)
            raise DesktopError('QQ identity card did not close; no input sent')
        close_cards()
        self.q.focus();self.q.click(550,610);pause(.5)
        point=center(title)
        lines=[];numbers=set()
        try:
            import subprocess
            found=cards()
            # QQ occasionally consumes the first title click while changing chats.
            # Retry only while no identity popup exists and the same title is visible.
            for opening in range(3):
                if len(found)==1:break
                if found:raise DesktopError('Multiple QQ identity cards; no message sent')
                opened=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'open-qq-identity.ps1'),'-Handle',str(self.q.hwnd),'-ExpectedContact',self.lookup_name,'-OutputPath',str(self.output/'identity-open-proof.json')],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=8,creationflags=0x08000000)
                if opened.returncode:raise DesktopError('Identity header invocation failed: '+opened.stderr.decode('utf-8',errors='replace')[-300:])
                for attempt in range(8):
                    pause(.25);found=cards()
                    if found:break

            if len(found)!=1:
                (self.output/'card-open-failure.json').write_text(json.dumps(dict(target=self.target,title=title,point=point,foreground=win32gui.GetForegroundWindow(),hwnd=self.q.hwnd,rect=self.q.rect),ensure_ascii=False,default=lambda x:float(x)),encoding='utf-8')
                ImageGrab.grab(all_screens=True).save(self.output/'card-open-failure.png')
                raise DesktopError('Group identity card did not become ready; no message sent')
            h=found[0]
            for object_id in [1,-4]:
                try:win32gui.SendMessageTimeout(h,0x003D,0,object_id,2,700)
                except Exception:pass
            path=self.output/'identity-uia.json'
            task=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'read-qq-identity.ps1'),'-Handle',str(h),'-ExpectedId',self.target['id'],'-OutputPath',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=8,creationflags=0x08000000)
            (self.output/'identity-uia-error.txt').write_bytes(task.stderr)
            if task.returncode==0 and path.exists():
                names=json.loads(path.read_text(encoding='utf-8-sig'))
                lines=[dict(text=x,confidence=1.0,source='uia') for x in names]
                numbers=set(n for x in lines for n in re.findall(r'(?<!\d)\d{5,12}(?!\d)',x['text']))
            (self.output/'identity-card.json').write_text(json.dumps(lines,ensure_ascii=False,indent=2),encoding='utf-8')
            if self.target['id'] not in numbers:raise DesktopError('Group identity number not confirmed; no message sent')
            self.verified_group_id=self.target['id'];self.verified_identity_window=(self.q.hwnd,pid);self.header_aliases={title_alias,self.header(self.target['name'])}
        finally:close_cards()
        self.q.focus();pause(.15)
        from memory import atomic
        self.header_aliases.add(self.header(self.candidate_header))
        atomic(self.output/'verified-session-binding.json',dict(version=1,id=self.target['id'],lookup=self.lookup_name,session=self.identity_session(),header=self.header(self.candidate_header),aliases=sorted(self.header_aliases),proof='Exact numeric group ID from QQ identity card',verified_at=__import__('time').strftime('%Y-%m-%d %H:%M:%S')))
    def open(self):
        if self.target['kind']=='group':
            from direct_reader import open_recent_group
            return open_recent_group(self)
        d=self.q.search(self.target['id']);w,h=d['size']
        pat=re.compile(r'[（(]'+re.escape(self.target['id'])+r'[）)]')
        hits=[x for x in d['lines'] if pat.search(x['text']) and center(x)[0]<w*.48 and .12*h<center(x)[1]<.6*h and x['confidence']>.85]
        if self.target['kind']=='private':
            if len(hits)!=1:raise DesktopError('Exact QQ number contact result not unique')
            name=pat.split(hits[0]['text'])[0]
            if not self.target.get('name'):self.target['name']=name
            if norm(name)!=norm(self.target['name']):raise DesktopError('QQ number nickname mismatch')
        elif self.target['kind']=='group':
            if not hits:
                if not self.target.get('name'):raise DesktopError('QQ did not find this group number. Enter its full group name too.')
                d=self.q.search(self.target['name'])
                hits=[x for x in d['lines'] if self.header(x['text'])==self.header(self.target['name']) and center(x)[0]<w*.32 and .12*h<center(x)[1]<.6*h and x['confidence']>.85]
            if len(hits)!=1:raise DesktopError('Group name search result not unique')
        else:raise DesktopError('Unsupported conversation type')
        self.q.click(*center(hits[0]));pause(.5);d=self.q.read('opened-chat')
        if self.target['kind']=='group':self.group_card(d);d=self.q.read('opened-chat')
        self.verify(d);return d
    def goto_latest(self):
        right=self.chat_right
        def thumb():
            self.q.ready();win32api.SetCursorPos((self.q.rect[0]+right-9,self.q.rect[1]+320));pause(.15)
            image=np.asarray(self.q.capture('navigation'));cut=image[110:535,right-14:right,:3].astype(int)
            level=cut.mean(axis=2);mask=(((cut.max(axis=2)-cut.min(axis=2)<8)&(level>64)&(level<180))*255).astype('uint8')
            count,labels,stats,centers=cv2.connectedComponentsWithStats(mask)
            found=[(x+right-14,y+110,w,h,area,cx+right-14,cy+110) for (x,y,w,h,area),(cx,cy) in zip(stats[1:],centers[1:]) if 2<=w<=12 and 10<=h<390 and area>=20]
            return max(found,key=lambda r:r[4]) if found else None
        for attempt in range(3):
            box=thumb()
            if box is None:
                if attempt==0:
                    self.q.click(right-45,320)
                    for _ in range(20):win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL,0,0,-120,0);pause(.015)
                    continue
                (self.output/'navigation.json').write_text(json.dumps(dict(method='all_visible_or_no_scrollbar')),encoding='utf-8');return
            x,y,w,h,area,cx,cy=box
            if y+h>=525:
                (self.output/'navigation.json').write_text(json.dumps(dict(method='scrollbar',bottom=int(y+h))),encoding='utf-8');return
            self.q.click(cx,cy);self.q.ready();win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0)
            try:
                for step in range(1,13):
                    self.q.ready();dest=cy+(530-cy)*step/12
                    win32api.SetCursorPos((int(self.q.rect[0]+cx),int(self.q.rect[1]+dest)));pause(.018)
            finally:win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0)
            pause(.4)
        box=thumb()
        if box and box[1]+box[3]<520:raise DesktopError('Could not reach latest messages; old history will not be used')
        (self.output/'navigation.json').write_text(json.dumps(dict(method='scrollbar',bottom=int(box[1]+box[3]) if box else None)),encoding='utf-8')
    def collect(self,views=6,current=False):
        from direct_reader import read_direct
        d=self.q.read('current-chat') if current else self.open()
        self.verify(d)
        return read_direct(self)
    def _collect_selected(self,views=6,current=False):
        views=max(2,min(6,int(views)))
        d=self.q.read('current-chat') if current else self.open(); w,h=self.verify(d)
        self.goto_latest()
        with preserved_clipboard():
            marker='AICHAT-'+str(uuid.uuid4()); put(marker)
            self.q.click(self.chat_right-20,h*.65)
            self.q.ready(); win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0)
            try:
                for i in range(1,31):
                    self.q.ready(); t=i/30
                    win32api.SetCursorPos((int(self.q.rect[0]+((self.chat_right-20)+(w*.34-(self.chat_right-20))*t)),int(self.q.rect[1]+h*(.65-.49*t))))
                    pause(.012)
            finally: win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0)
            pause(.25); d=self.q.read('bulk-mode'); self.verify(d)
            hits=[x for x in d['lines'] if x['text']=='复制' and center(x)[1]>.7*h]
            if len(hits)!=1: raise DesktopError('Batch selection toolbar not recognized')
            for page in range(views):
                im=np.asarray(self.q.capture('checkboxes'))
                count=0
                for left,right in [(395,440)]:
                    gray=cv2.cvtColor(im[110:535,left:right],cv2.COLOR_RGB2GRAY)
                    circles=cv2.HoughCircles(gray,cv2.HOUGH_GRADIENT,1,26,param1=80,param2=14,minRadius=6,maxRadius=13)
                    if circles is None: continue
                    for cx,cy,radius in sorted(circles[0],key=lambda c:c[1]):
                        cx,cy=int(cx+left),int(cy+110)
                        patch=im[max(0,cy-5):cy+6,cx-5:cx+6,:3].astype(int)
                        selected=((patch[:,:,2]>patch[:,:,0]+45)&(patch[:,:,1]>patch[:,:,0]+30)).sum()>10
                        if not selected: self.q.click(cx,cy); pause(.15)
                        count+=1
                if page<views-1:
                    self.q.click(self.chat_right-55,h*.4); win32api.mouse_event(win32con.MOUSEEVENTF_WHEEL,0,0,120,0); pause(.3)
            pause(.3)
            d=self.q.read('bulk-selected'); self.verify(d)
            hits=[x for x in d['lines'] if x['text']=='复制' and center(x)[1]>.7*h]
            if len(hits)!=1: raise DesktopError('Copy toolbar changed')
            x,y=center(hits[0])
            im=np.asarray(self.q.capture('selection-check')).astype(int)
            strip=im[110:535,395:440,:3]
            checked=int(((strip[:,:,2]>strip[:,:,0]+45)&(strip[:,:,1]>strip[:,:,0]+30)).sum())
            if checked<=20: raise DesktopError('No checked message; copy cancelled')
            self.q.click(x,y-48); text=marker
            for _ in range(15):
                pause(.2); text=get()
                if text and text!=marker: break
            if not text or text==marker:
                import win32clipboard as cb
                formats=[]; cb.OpenClipboard()
                try:
                    f=0
                    while True:
                        f=cb.EnumClipboardFormats(f)
                        if not f: break
                        try: name=cb.GetClipboardFormatName(f)
                        except Exception: name=str(f)
                        try:
                            value=cb.GetClipboardData(f); formats.append(dict(id=f,name=name,type=type(value).__name__,length=len(value) if hasattr(value,'__len__') else None,preview=value[:250] if isinstance(value,str) else None))
                        except Exception: formats.append(dict(id=f,name=name))
                finally: cb.CloseClipboard()
                (self.output/'clipboard-diagnostic.json').write_text(json.dumps(formats,ensure_ascii=False,indent=2),encoding='utf-8')
                raise DesktopError('QQ did not copy a transcript')
        rows=parse_batch(text,self.target['id'])
        if not rows: raise DesktopError('Transcript format not recognized')
        self.verify(self.q.read('bulk-after'))
        (self.output/'last-transcript.txt').write_text(text,encoding='utf-8')
        (self.output/'last-batch.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
        return rows
    def send(self,text,on_attempt=None):
        text=clean_reply(text)
        if not text.strip() or len(text)>self.cfg['max_reply_chars']: raise DesktopError('Invalid reply length')
        if any(ord(c)<32 and c not in '\n\t' for c in text): raise DesktopError('Control character in reply')
        d=self.open(); w,h=self.verify(d)
        with preserved_clipboard():
            marker='AICHAT-'+str(uuid.uuid4()); put(marker)
            self.q.click(w*.55,h*.79); chord(win32con.VK_CONTROL,ord('A')); chord(win32con.VK_CONTROL,ord('C')); pause(.15)
            old=get()
            from memory import atomic
            import time
            def draft_text(value):return value.replace('\r\n','\n').rstrip('\n')
            def same_draft(a,b):return draft_text(a)==draft_text(b) or draft_text(a).replace('\n','')==draft_text(b).replace('\n','')
            manifest=self.output/'draft-state.json'
            if old and old!=marker:
                known=[]
                if manifest.exists():
                    saved=json.loads(manifest.read_text(encoding='utf-8'))
                    if saved.get('status') in ('prepared','verified'):known.append(saved.get('text',''))
                log_path=ROOT/'bot-log.jsonl'
                for line in (log_path.read_text(encoding='utf-8').splitlines()[-180:] if log_path.exists() else []):
                    try:r=json.loads(line)
                    except ValueError:continue
                    if r.get('scope')==self.output.name and r.get('event')=='sending':known.append(r.get('reply',''))
                if not any(value and same_draft(old,value) for value in known):raise DesktopError('Existing draft preserved; send cancelled')
                atomic(self.output/'unsent-draft-backup.json',dict(text=old,time=time.strftime('%Y-%m-%d %H:%M:%S'),reason='Recovering known bot draft'))
                chord(win32con.VK_CONTROL,ord('A'));key(win32con.VK_BACK);pause(.1)
            atomic(manifest,dict(text=text,status='prepared',time=time.strftime('%Y-%m-%d %H:%M:%S')))
            self.q.ready();put(text);chord(win32con.VK_CONTROL,ord('V'));pause(.3)
            chord(win32con.VK_CONTROL,ord('A'));chord(win32con.VK_CONTROL,ord('C'));pause(.2)
            if draft_text(get())!=draft_text(text):raise DesktopError('Typed draft verification failed; left for inspection')
            atomic(manifest,dict(text=text,status='verified',time=time.strftime('%Y-%m-%d %H:%M:%S')))
            d=self.q.read('before-send'); self.verify(d)
            hits=[x for x in d['lines'] if x['text'].startswith('发送') and center(x)[0]>.8*self.chat_right and center(x)[0]<self.chat_right and center(x)[1]>.85*h and x['confidence']>.6]
            if len(hits)!=1: raise DesktopError('Send button not uniquely recognized; draft retained')
            if on_attempt:on_attempt()
            self.q.click(*center(hits[0]))
            atomic(manifest,dict(text=text,status='attempted',time=time.strftime('%Y-%m-%d %H:%M:%S')))
        pause(.8)
        try:rows=self.collect(views=2,current=True)
        except Stopped:raise
        except DesktopError:rows=self.collect(current=True)
        if not any(r['sender']!=self.target['name'] and r['body'].replace('\r\n','\n')==text.replace('\r\n','\n') for r in rows[-6:]):
            raise DesktopError('Delivery uncertain; never retry automatically')
        return rows
