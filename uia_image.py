import json,subprocess,hashlib,math
from pathlib import Path
from desktop import ROOT,DesktopError,check_stop

def capture(transport,row,reference,index,directory):
 transport.q.ready()
 proof_path=transport.output/'direct-raw.json'
 proof=json.loads(proof_path.read_text(encoding='utf-8-sig'))
 expected=proof['header'];runtime=reference.get('runtime_id','')
 if not runtime:raise DesktopError('Image has no stable UIA identity')
 if transport.header(expected) not in transport.header_aliases|{transport.header(transport.target['name'])}:raise DesktopError('Image chat binding changed')
 directory=Path(directory)/'captured-images';directory.mkdir(parents=True,exist_ok=True)
 name=hashlib.sha256((row['id']+':'+str(index)).encode()).hexdigest()+'.jpg';path=directory/name
 if path.exists():return str(path)
 def run(action,output):
  check_stop();r=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'read-qq-image.ps1'),'-Handle',str(transport.q.hwnd),'-ExpectedHeader',expected,'-RuntimeId',runtime,'-Action',action,'-OutputPath',str(output)],capture_output=True,timeout=15,creationflags=0x08000000)
  if r.returncode:raise DesktopError('Image capture unavailable: '+r.stderr.decode('utf-8',errors='replace')[-350:])
  return json.loads(output.read_text(encoding='utf-8-sig')) if action!='latest' else None
 before=directory/'bounds-before.json';after=directory/'bounds-after.json'
 try:
  meta=run('prepare',before);transport.q.ready();im=transport.q.capture('image-capture')
  current=run('check',after);transport.q.ready()
  if current['rect']!=meta['rect'] or current['window']!=meta['window']:raise DesktopError('Image moved during capture')
  l,t,r,b=transport.q.rect
  if [l,t,r-l,b-t]!=meta['window']:raise DesktopError('QQ window geometry changed')
  x,y,w,h=meta['rect'];box=(math.ceil(x-l),math.ceil(y-t),math.floor(x+w-l),math.floor(y+h-t))
  crop=im.crop(box).convert('RGB');crop.thumbnail((1024,1024));crop.save(path,format='JPEG',quality=90)
  for old in sorted(directory.glob('*.jpg'),key=lambda f:f.stat().st_mtime,reverse=True)[32:]:
   if len(old.stem)==64 and all(c in 'abcdef0123456789' for c in old.stem):old.unlink()
  return str(path)
 finally:
  try:run('latest',after)
  except Exception:pass
