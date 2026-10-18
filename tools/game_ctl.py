# -*- coding: utf-8 -*-
"""Interact with the running Kamui game: send keys, capture screenshots.

Usage:
  python game_ctl.py press <VK_HEX> [count]   e.g. press 0x0d 2
  python game_ctl.py cap <name.png>
  python game_ctl.py type <text>              ASCII text via short keys
"""
import ctypes, ctypes.wintypes as w, sys, time
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32


def find_game_hwnd():
    res = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        buf = ctypes.create_unicode_buffer(256)
        n = user32.GetWindowTextLengthW(hwnd)
        user32.GetWindowTextW(hwnd, buf, 256)
        title = buf.value[:n]
        if '恄埿' in title or 'Kamui' in title or '神威' in title:
            res.append(hwnd)
        return True

    user32.EnumWindows(cb, 0)
    return res[0] if res else None


INPUT_KEYBOARD = 1
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_KEYDOWN = 0


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD),
                ('time', w.DWORD), ('dwExtraInfo', ctypes.POINTER(w.ULONG))]


class INPUT(ctypes.Structure):
    class _I(ctypes.Union):
        _fields_ = [('ki', KEYBDINPUT)]
    _anonymous_ = ('i',)
    _fields_ = [('type', w.DWORD), ('i', _I)]


def press_key(hwnd, vk, hold=0.03):
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)
    for flag in (KEYEVENTF_KEYDOWN, KEYEVENTF_KEYUP):
        inp = INPUT()
        inp.type = INPUT_KEYBOARD
        inp.ki.wVk = vk
        inp.ki.dwFlags = flag
        ctypes.windll.user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))
        time.sleep(hold)


class BMIH(ctypes.Structure):
    _fields_ = [('biSize', w.DWORD), ('biWidth', w.LONG), ('biHeight', w.LONG),
                ('biPlanes', w.WORD), ('biBitCount', w.WORD),
                ('biCompression', w.DWORD), ('biSizeImage', w.DWORD),
                ('biXPelsPerMeter', w.LONG), ('biYPelsPerMeter', w.LONG),
                ('biClrUsed', w.DWORD), ('biClrImportant', w.DWORD)]


class BMI(ctypes.Structure):
    _fields_ = [('h', BMIH), ('pad', w.DWORD * 3)]


def capture(hwnd, path):
    crect = w.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(crect))
    cw, ch = crect.right - crect.left, crect.bottom - crect.top
    pt = w.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    sdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(sdc)
    bmp = gdi32.CreateCompatibleBitmap(sdc, cw, ch)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, cw, ch, sdc, pt.x, pt.y, 0x00CC0020)
    bi = BMI()
    bi.h.biSize = ctypes.sizeof(BMIH)
    bi.h.biWidth, bi.h.biHeight = cw, -ch
    bi.h.biPlanes, bi.h.biBitCount, bi.h.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(cw * ch * 4)
    gdi32.GetDIBits(mem, bmp, 0, ch, buf, ctypes.byref(bi), 0)
    Image.frombytes('RGBA', (cw, ch), buf.raw).convert('RGB').save(path)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mem)
    user32.ReleaseDC(0, sdc)
    return cw, ch


if __name__ == '__main__':
    hwnd = find_game_hwnd()
    if not hwnd:
        print('game window not found')
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'press':
        vk = int(sys.argv[2], 0)
        count = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        for _ in range(count):
            press_key(hwnd, vk)
            time.sleep(0.25)
        print(f'pressed vk={vk:#x} x{count}')
    elif cmd == 'cap':
        cw, ch = capture(hwnd, sys.argv[2])
        print(f'saved {sys.argv[2]} {cw}x{ch}')
