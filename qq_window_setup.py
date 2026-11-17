"""Calibrate the QQ main window once before the visual bot starts."""

import win32con
import win32gui

from desktop import DesktopError, check_stop, find_qq_window


def window_size(hwnd):
    left, top, right, bottom = win32gui.GetWindowRect(hwnd)
    return right - left, bottom - top


def configure_qq_window(size):
    check_stop()
    expected = tuple(size)
    hwnd = find_qq_window()
    before = window_size(hwnd)
    if (win32gui.IsIconic(hwnd)
            or win32gui.GetWindowPlacement(hwnd)[1] == win32con.SW_SHOWMAXIMIZED):
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
    if window_size(hwnd) != expected:
        check_stop()
        flags = win32con.SWP_NOMOVE | win32con.SWP_NOZORDER | win32con.SWP_NOACTIVATE
        win32gui.SetWindowPos(hwnd, 0, 0, 0, *expected, flags)
    actual = window_size(hwnd)
    if actual != expected:
        raise DesktopError(f'QQ window setup expected {expected}, got {actual}')
    return before, actual


if __name__ == '__main__':
    from runtime import load_config

    before, after = configure_qq_window(load_config()['window_size'])
    print(f'QQ window: {before[0]}x{before[1]} -> {after[0]}x{after[1]}')
