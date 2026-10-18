# -*- coding: utf-8 -*-
"""Capture the Kamui game window (client area) to PNG via PrintWindow + GetDIBits."""
import ctypes, ctypes.wintypes as w, sys
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', w.DWORD), ('biWidth', w.LONG), ('biHeight', w.LONG),
                ('biPlanes', w.WORD), ('biBitCount', w.WORD), ('biCompression', w.DWORD),
                ('biSizeImage', w.DWORD), ('biXPelsPerMeter', w.LONG),
                ('biYPelsPerMeter', w.LONG), ('biClrUsed', w.DWORD),
                ('biClrImportant', w.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', w.DWORD * 3)]


def find_window():
    res = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, buf, 256)
        cls = buf.value
        length = user32.GetWindowTextLengthW(hwnd)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value[:length]
        pid = w.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        res.append((hwnd, cls, title, pid.value))
        return True

    user32.EnumWindows(cb, 0)
    return res


def capture(hwnd, path):
    rect = w.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    cw, ch = rect.right - rect.left, rect.bottom - rect.top
    hdc = user32.GetDC(hwnd)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, cw, ch)
    gdi32.SelectObject(mem, bmp)
    user32.PrintWindow(hwnd, mem, 2)  # PW_RENDERFULLCONTENT
    bi = BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = cw
    bi.bmiHeader.biHeight = -ch
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = 0  # BI_RGB
    buf = ctypes.create_string_buffer(cw * ch * 4)
    gdi32.GetDIBits(mem, bmp, 0, ch, buf, ctypes.byref(bi), 0)
    img = Image.frombytes('RGBA', (cw, ch), buf.raw)
    img = img.convert('RGB')
    img.save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(hwnd, hdc)
    return cw, ch


if __name__ == '__main__':
    out = sys.argv[1] if len(sys.argv) > 1 else 'cnmod/work/game_shot.png'
    hwnds = [(h, t, p) for (h, c, t, p) in find_window() if p and 'Kamui' in (t or '')]
    # fall back: window title contains mojibake of 神威
    if not hwnds:
        for (h, c, t, p) in find_window():
            if c in ('WinGL', 'Kamui') or '恄埿' in (t or ''):
                hwnds.append((h, t, 0))
    for h, t, p in hwnds:
        print(f'hwnd={h} title={t!r}')
    if not hwnds:
        print('no game window found')
        sys.exit(1)
    cw, ch = capture(hwnds[0][0], out)
    print(f'saved {out} {cw}x{ch}')
