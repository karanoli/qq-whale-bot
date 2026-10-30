from pathlib import Path
import json,hashlib,uuid,time,subprocess
from memory import atomic
class DirectStream:
 def __init__(self,directory,target):
  self.directory=Path(directory);self.path=self.directory/'direct-cursor.json';self.target=target;self.baseline=False
 def fingerprint(self,row):
  return hashlib.sha256(json.dumps([row['self'],row['sender'],row['body'],row.get('image_count',0)],ensure_ascii=False).encode()).hexdigest()
 def merge(self,raw):
  self.baseline=False;old=json.loads(self.path.read_text(encoding='utf-8')) if self.path.exists() else []
  new=[dict(r,fingerprint=self.fingerprint(r)) for r in raw];overlap=0;start=0
  for n in range(min(len(old),len(new)),0,-1):
   wanted=[x['fingerprint'] for x in old[-n:]]
   hits=[j for j in range(len(new)-n+1) if [x['fingerprint'] for x in new[j:j+n]]==wanted]
   if len(hits)==1:overlap=n;start=hits[0];break
  if not old or not overlap:
   self.baseline=True
   result=[]
   for r in new:result.append(dict(r,id='uia-'+uuid.uuid4().hex))
   atomic(self.directory/'direct-read-status.json',dict(state='baseline' if not old else 'rebased-no-overlap',count=len(result),time=time.strftime('%Y-%m-%d %H:%M:%S')))
  else:
   # Old messages before the overlap remain history, never new pending messages.
   result=[dict(new[start+i],id=old[-overlap+i]['id'],time=old[-overlap+i]['time']) for i in range(overlap)]
   result += [dict(r,id='uia-'+uuid.uuid4().hex) for r in new[start+overlap:]]
   atomic(self.directory/'direct-read-status.json',dict(state='aligned',overlap=overlap,new=len(result)-overlap,time=time.strftime('%Y-%m-%d %H:%M:%S')))
  if result:atomic(self.path,result[-200:])
  return result

def read_direct(transport):
 from desktop import ROOT,DesktopError,check_stop
 import win32gui
 transport.q.ready();handles=[transport.q.hwnd]
 win32gui.EnumChildWindows(transport.q.hwnd,lambda h,_:handles.append(h),None)
 for handle in handles:
  try:win32gui.SendMessageTimeout(handle,0x003D,0,1,2,700)
  except Exception:pass
 output=transport.output/'direct-raw.json'
 proc=subprocess.Popen(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'read-qq-direct.ps1'),'-OutputPath',str(output)],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,creationflags=0x08000000)
 started=time.monotonic()
 try:
  while proc.poll() is None:
   check_stop()
   if time.monotonic()-started>20:raise DesktopError('Direct reader timed out')
   time.sleep(.1)
  error=proc.stderr.read().decode('utf-8',errors='replace')
  if proc.returncode:raise DesktopError('Direct reader failed: '+error[-800:])
 finally:
  if proc.poll() is None:proc.kill();proc.wait()
 if not output.exists():raise DesktopError('Direct reader produced no output')
 data=json.loads(output.read_text(encoding='utf-8-sig'));header=transport.header(data['header'])
 aliases=getattr(transport,'header_aliases',set())|{transport.header(transport.target['name'])}
 if header not in aliases:
  from difflib import SequenceMatcher
  if transport.target['kind']!='group' or transport.verified_group_id!=transport.target['id'] or max(SequenceMatcher(None,header,a).ratio() for a in aliases)<.9:raise DesktopError('Direct reader chat identity changed; no data merged')
 now=time.strftime('%Y-%m-%d %H:%M:%S');raw=[]
 for m in data['messages']:
  body=m.get('body','').strip();images=int(m.get('image_count',0))
  if not body and not images:continue
  body=body+('[图片，尚未获取内容]' if images else '')
  sender=m.get('sender') or (transport.cfg.get('self_names',['小鲸'])[-1] if m['self'] else transport.target['name'])
  raw.append(dict(sender=sender,body=body or '[图片]',self=bool(m['self']),images=[],image_refs=m.get("image_bounds",[]),image_count=images,source='uia',time=now,display_time=m.get('display_time',''),timestamp_kind='observed',observed_at=now))
 if not raw:raise DesktopError('No readable messages; baseline not changed')
 stream=DirectStream(transport.output,transport.target);rows=stream.merge(raw);transport.read_baseline=stream.baseline
 return rows

def open_recent_group(transport):
 from desktop import ROOT,DesktopError,key,win32con,center
 import win32gui
 transport.q.focus()
 handles=[transport.q.hwnd]
 win32gui.EnumChildWindows(transport.q.hwnd,lambda h,_:handles.append(h),None)
 for h in handles:
  try:win32gui.SendMessageTimeout(h,0x003D,0,1,2,700)
  except Exception:pass
 time.sleep(.8)
 result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'read-qq-direct.ps1'),'-Contact',transport.lookup_name,'-OutputPath',str(transport.output/'open-proof.json')],stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=20,creationflags=0x08000000)
 if result.returncode:raise DesktopError('Recent group not uniquely available through UIA; no message sent: '+result.stderr.decode('utf-8',errors='replace')[-300:])
 proof=json.loads((transport.output/'open-proof.json').read_text(encoding='utf-8-sig'))
 d=transport.q.read('uia-opened-group')
 # A similar name only opens a candidate. The exact numeric group ID remains mandatory.
 # Reuse only an exact title binding whose group number was already verified
 # in this Transport instance. A new QQ window, target, or name gets a new instance.
 canonical=transport.header(proof['header'])
 transport.candidate_header=proof['header']
 binding_path=transport.output/'verified-session-binding.json'
 if binding_path.exists():
  try:
   binding=json.loads(binding_path.read_text(encoding='utf-8'))
   if binding.get('version')==1 and binding.get('id')==transport.target['id'] and binding.get('lookup')==transport.lookup_name and binding.get('session')==transport.identity_session() and binding.get('header')==canonical:
    transport.verified_group_id=transport.target['id'];transport.header_aliases=set(binding['aliases'])
    transport.verified_identity_window=(transport.q.hwnd,__import__('win32process').GetWindowThreadProcessId(transport.q.hwnd)[1])
  except (ValueError,KeyError,OSError):pass
 if transport.verified_group_id==transport.target['id'] and canonical in transport.header_aliases and getattr(transport,'verified_identity_window',None)==(transport.q.hwnd,__import__('win32process').GetWindowThreadProcessId(transport.q.hwnd)[1]):
  transport.verify(d)
  return d
 transport.group_card(d)
 # Use the exact accessible header for future lookups, not OCR spelling.
 transport.header_aliases.add(transport.header(proof['header']))
 d=transport.q.read('uia-verified-group');transport.verify(d)
 return d
