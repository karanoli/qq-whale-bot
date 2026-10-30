import contextlib,time,uuid
import win32clipboard as clip
import win32con
from desktop import DesktopError

def opened():
 for _ in range(20):
  try: clip.OpenClipboard(); return
  except Exception: time.sleep(.05)
 raise DesktopError('Clipboard busy')

@contextlib.contextmanager
def preserved_clipboard():
 saved=[]; opened()
 try:
  f=0
  while True:
   f=clip.EnumClipboardFormats(f)
   if not f: break
   v=clip.GetClipboardData(f)
   if not isinstance(v,(str,bytes)): raise DesktopError('Cannot preserve clipboard format; pause before copying')
   saved.append((f,v))
 finally: clip.CloseClipboard()
 try: yield
 finally:
  opened()
  try:
   clip.EmptyClipboard()
   for f,v in saved: clip.SetClipboardData(f,v)
  finally: clip.CloseClipboard()

def put(text):
 opened()
 try: clip.EmptyClipboard();clip.SetClipboardText(text,win32con.CF_UNICODETEXT)
 finally: clip.CloseClipboard()

def get():
 opened()
 try: return clip.GetClipboardData(win32con.CF_UNICODETEXT) if clip.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT) else ''
 finally: clip.CloseClipboard()
