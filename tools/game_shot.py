# -*- coding: utf-8 -*-
"""Force-focus the game, send keys via PostMessage, capture D3DProxyWindow area."""
import ctypes, ctypes.wintypes as w, sys, time
sys.path.insert(0, 'cnmod/tools')
import game_ctl
from PIL import Image

user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32

WM_KEYDOWN, WM_KEYUP = 0x0100, 0x0101


def find_by_class(cls):
    res = []
    @ctypes.WINFUNCTYPE(ctypes.c_bool, w.HWND, w.LPARAM)
    def cb(hwnd, _):
        buf = ctypes.create_unicode_buffer(64)
        user32.GetClassNameW(hwnd, buf, 64)
        if buf.value == cls:
            res.append(hwnd)
        return True
    user32.EnumWindows(cb, 0)
    return res


def focus():
    hwnds = find_by_class('D3DProxyWindow')
    if not hwnds:
        return None
    h = hwnds[0]
    user32.ShowWindow(h, 9)  # SW_RESTORE
    # ALT-key trick to allow SetForegroundWindow
    user32.keybd_event(0x12, 0, 0, 0)
    user32.SetForegroundWindow(h)
    user32.keybd_event(0x12, 0, 2, 0)
    time.sleep(0.3)
    return h


def send_key(vk):
    hwnds = find_by_class('D3DProxyWindow')
    h = hwnds[0] if hwnds else None
    if h:
        user32.PostMessageW(h, WM_KEYDOWN, vk, 0)
        time.sleep(0.05)
        user32.PostMessageW(h, WM_KEYUP, vk, 0)


def capture_screen(x, y, cw, ch, path):
    sdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(sdc)
    bmp = gdi32.CreateCompatibleBitmap(sdc, cw, ch)
    gdi32.SelectObject(mem, bmp)
    gdi32.BitBlt(mem, 0, 0, cw, ch, sdc, x, y, 0x00CC0020)
    bi = game_ctl.BMI()
    bi.h.biSize = ctypes.sizeof(game_ctl.BMIH)
    bi.h.biWidth, bi.h.biHeight = cw, -ch
    bi.h.biPlanes, bi.h.biBitCount, bi.h.biCompression = 1, 32, 0
    buf = ctypes.create_string_buffer(cw * ch * 4)
    gdi32.GetDIBits(mem, bmp, 0, ch, buf, ctypes.byref(bi), 0)
    Image.frombytes('RGBA', (cw, ch), buf.raw).convert('RGB').save(path)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mem); user32.ReleaseDC(0, sdc)


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'focus':
        h = focus()
        print('focused', h)
    elif cmd == 'key':
        vk = int(sys.argv[2], 0)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 1
        for _ in range(n):
            send_key(vk); time.sleep(0.3)
        print('sent', hex(vk), 'x', n)
    elif cmd == 'shot':
        focus(); time.sleep(0.5)
        capture_screen(0, 0, 800, 600, sys.argv[2])
        print('saved', sys.argv[2])


def bring_top():
    hwnds = find_by_class('D3DProxyWindow')
    if not hwnds:
        return None, None
    h = hwnds[0]
    r = w.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    user32.SetWindowPos(h, -1, 0, 0, 0, 0, 0x0003)  # HWND_TOPMOST, NOSIZE|NOMOVE
    time.sleep(0.3)
    user32.SetWindowPos(h, -2, 0, 0, 0, 0, 0x0003)  # HWND_NOTOPMOST
    return h, (r.left, r.top, r.right - r.left, r.bottom - r.top)
