"""Resize the one visible QQ window; this does not recalibrate OCR thresholds."""
import sys
if sys.platform != 'win32':
    raise SystemExit('请在 Windows 上运行。')
from desktop import QQDesktop
from runtime import load_config
import win32gui
import win32con

cfg = load_config()
qq = QQDesktop()
left, top, _, _ = qq.focus()
width, height = cfg['window_size']
win32gui.SetWindowPos(qq.hwnd, 0, max(0, left), max(0, top), width, height, win32con.SWP_NOZORDER)
print('QQ 窗口已调整为', width, '×', height)
print('仅调整窗口大小；若 DPI 或 QQ 布局不同，仍需人工校准。')
