"""QQ visual access: screenshot OCR and ordinary desktop input only."""
import ctypes, json, time, os, pathlib, re
from ctypes import wintypes
ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
import win32gui, win32con, win32api
import numpy as np
from PIL import ImageGrab, ImageOps
from rapidocr_onnxruntime import RapidOCR
from runtime import ROOT,load_config
class DesktopError(RuntimeError): pass
class Stopped(DesktopError): pass

def check_stop():
    if (ROOT/'STOP').exists() or win32api.GetAsyncKeyState(win32con.VK_F8)&0x8000:
        raise Stopped('Stopped by STOP file or F8')

def pause(seconds):
    end=time.monotonic()+seconds
    while time.monotonic()<end:
        check_stop(); time.sleep(min(.1,max(0,end-time.monotonic())))

def key(vk):
    check_stop(); win32api.keybd_event(vk,0,0,0); win32api.keybd_event(vk,0,win32con.KEYEVENTF_KEYUP,0)

def chord(mod,vk):
    check_stop(); win32api.keybd_event(mod,0,0,0)
    try: key(vk)
    finally: win32api.keybd_event(mod,0,win32con.KEYEVENTF_KEYUP,0)

ULONG_PTR=ctypes.c_size_t
class KEYBDINPUT(ctypes.Structure):
    _fields_=[('wVk',wintypes.WORD),('wScan',wintypes.WORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ULONG_PTR)]
class MOUSEINPUT(ctypes.Structure):
    _fields_=[('dx',wintypes.LONG),('dy',wintypes.LONG),('mouseData',wintypes.DWORD),('dwFlags',wintypes.DWORD),('time',wintypes.DWORD),('dwExtraInfo',ULONG_PTR)]
class INPUTUNION(ctypes.Union):
    _fields_=[('ki',KEYBDINPUT),('mi',MOUSEINPUT)]
class INPUT(ctypes.Structure):
    _fields_=[('type',wintypes.DWORD),('u',INPUTUNION)]

def unicode_text(text):
    # UTF-16 SendInput leaves the user's clipboard untouched.
    for i in range(0,len(text.encode('utf-16-le')),2):
        check_stop(); unit=int.from_bytes(text.encode('utf-16-le')[i:i+2],'little')
        a=INPUT(type=1,u=INPUTUNION(ki=KEYBDINPUT(0,unit,4,0,0)))
        b=INPUT(type=1,u=INPUTUNION(ki=KEYBDINPUT(0,unit,6,0,0)))
        inputs=(INPUT*2)(a,b)
        if ctypes.windll.user32.SendInput(2,inputs,ctypes.sizeof(INPUT))!=2:
            raise DesktopError('SendInput failed')

def norm(text): return re.sub(r'\s+','',text).casefold()

def center(line):
    a=line['box']; return ((min(p[0] for p in a)+max(p[0] for p in a))/2,(min(p[1] for p in a)+max(p[1] for p in a))/2)

class QQDesktop:
    def __init__(self):
        self.ocr=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=1)
        self.hwnd=None
        self.debug=load_config().get('debug_snapshots',False)
    def window(self):
        found=[]
        def visit(h,_):
            if win32gui.IsWindowVisible(h) and win32gui.GetWindowText(h)=='QQ' and win32gui.GetClassName(h)=='Chrome_WidgetWin_1': found.append(h)
        win32gui.EnumWindows(visit,None)
        if len(found)!=1: raise DesktopError('Expected one visible main QQ window, got '+str(len(found)))
        self.hwnd=found[0]
        return self.hwnd
    def focus(self):
        h=self.window()
        if win32gui.IsIconic(h):win32gui.ShowWindow(h,win32con.SW_RESTORE)
        if win32gui.GetForegroundWindow()!=h:
            try:
                win32api.keybd_event(win32con.VK_MENU,0,0,0)
                win32api.keybd_event(win32con.VK_MENU,0,win32con.KEYEVENTF_KEYUP,0)
                win32gui.SetForegroundWindow(h)
                time.sleep(.3)
            except Exception: pass
        if win32gui.GetForegroundWindow()!=h: raise DesktopError('QQ is not foreground. Click QQ first.')
        self.rect=win32gui.GetWindowRect(h)
        return self.rect
    def ready(self):
        check_stop()
        if not self.hwnd or win32gui.GetForegroundWindow()!=self.hwnd: raise DesktopError('Focus changed; no input sent')
        if win32gui.GetWindowRect(self.hwnd)!=self.rect: raise DesktopError('QQ moved or resized; no input sent')
    def click(self,x,y):
        self.ready(); sx=int(self.rect[0]+x); sy=int(self.rect[1]+y)
        if not (self.rect[0]<sx<self.rect[2] and self.rect[1]<sy<self.rect[3]): raise DesktopError('Point outside QQ')
        top=win32gui.GetAncestor(win32gui.WindowFromPoint((sx,sy)),win32con.GA_ROOT)
        if top!=self.hwnd: raise DesktopError('QQ is covered; no click sent')
        win32api.SetCursorPos((sx,sy));pause(.16);self.ready()
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN,0,0)
        try:pause(.06)
        finally:win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP,0,0)
    def capture(self,tag='latest'):
        self.focus(); pause(.15); self.ready()
        im=ImageGrab.grab(bbox=self.rect,all_screens=True)
        # Capture and screen coordinates use the same per-monitor DPI awareness.
        expected=(self.rect[2]-self.rect[0],self.rect[3]-self.rect[1])
        if im.size!=expected: raise DesktopError('DPI mismatch '+str((im.size,expected)))
        if self.debug:(ROOT/'diagnostics').mkdir(exist_ok=True);im.save(ROOT/'diagnostics'/(tag+'.png'))
        return im
    def read(self,tag='latest'):
        im=self.capture(tag); result,_=self.ocr(np.asarray(im),use_cls=False)
        lines=[dict(box=np.asarray(b).round(1).tolist(),text=t,confidence=round(float(c),4)) for b,t,c in (result or [])]
        data=dict(rect=self.rect,size=im.size,lines=lines,time=time.strftime('%Y-%m-%d %H:%M:%S'))
        if self.debug:(ROOT/'diagnostics'/(tag+'.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        return data
    def search(self,query):
        if not query.strip() or len(query)>80 or any(ord(c)<32 for c in query):raise DesktopError('Invalid search text')
        d=self.read('before-search');w,h=d['size']
        hits=[x for x in d['lines'] if 70<center(x)[0]<w*.31 and 50<center(x)[1]<100 and x['confidence']>.75]
        if len(hits)!=1:raise DesktopError('Search field not uniquely recognized')
        self.click(*center(hits[0]));chord(win32con.VK_CONTROL,ord('A'));unicode_text(query);pause(1.2)
        return self.read('search-result')
if __name__=='__main__':
    import argparse,traceback
    p=argparse.ArgumentParser(); p.add_argument('--search'); args=p.parse_args()
    try:
        q=QQDesktop(); result=q.search(args.search) if args.search else q.read('probe')
        (ROOT/'probe-status.json').write_text(json.dumps(dict(ok=True,size=result['size'],lines=len(result['lines'])),ensure_ascii=False),encoding='utf-8')
    except Exception:
        (ROOT/'probe-status.json').write_text(json.dumps(dict(ok=False,error=traceback.format_exc()),ensure_ascii=False),encoding='utf-8')
        raise
