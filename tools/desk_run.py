# -*- coding: utf-8 -*-
"""Run Kamui.exe on a private Windows desktop; capture/input there, unpolluted.

Usage (from game root):
  python cnmod/tools/desk_run.py shot <out.png>        # capture game client
  python cnmod/tools/desk_run.py key <vk>              # SendInput key
  python cnmod/tools/desk_run.py click                 # click client center (wake)
  python cnmod/tools/desk_run.py title                 # print window title
  python cnmod/tools/desk_run.py start                 # launch game on private desktop
  python cnmod/tools/desk_run.py stop                  # terminate game process

The private desktop object lives per-process; each invocation creates its own
desktop named kmcap (CreateDesktop is idempotent-ish; existing handle reused).
Game client is 457x342 windowed (setupkamui.cfg offset0 = 0).
"""
import ctypes, ctypes.wintypes as w, sys, os, time, struct

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

DESKTOP_NAME = 'kmcap'
GAME_EXE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'Kamui.exe')

class STARTUPINFO(ctypes.Structure):
    _fields_ = [('cb', w.DWORD), ('lpReserved', w.LPWSTR), ('lpDesktop', w.LPWSTR),
                ('lpTitle', w.LPWSTR), ('dwX', w.DWORD), ('dwY', w.DWORD),
                ('dwXSize', w.DWORD), ('dwYSize', w.DWORD), ('dwXCountChars', w.DWORD),
                ('dwYCountChars', w.DWORD), ('dwFillAttribute', w.DWORD),
                ('dwFlags', w.DWORD), ('wShowWindow', w.WORD), ('cbReserved2', w.WORD),
                ('lpReserved2', ctypes.c_void_p), ('hStdInput', w.HANDLE),
                ('hStdOutput', w.HANDLE), ('hStdError', w.HANDLE)]

class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [('hProcess', w.HANDLE), ('hThread', w.HANDLE),
                ('dwProcessId', w.DWORD), ('dwThreadId', w.DWORD)]

def open_desktop():
    h = user32.CreateDesktopW(DESKTOP_NAME, None, None, 0,
                              0x01FF,  # GENERIC_ALL
                              None)
    if not h:
        h = user32.OpenDesktopW(DESKTOP_NAME, 0, False, 0x01FF)
    if not h:
        raise ctypes.WinError()
    return h

def set_thread_desktop(h):
    if not user32.SetThreadDesktop(h):
        raise ctypes.WinError()

def start_game():
    h = open_desktop()
    si = STARTUPINFO(); si.cb = ctypes.sizeof(STARTUPINFO)
    si.lpDesktop = DESKTOP_NAME
    si.dwFlags = 1  # STARTF_USESHOWWINDOW
    si.wShowWindow = 1  # SW_SHOWNORMAL
    pi = PROCESS_INFORMATION()
    ok = kernel32.CreateProcessW(GAME_EXE, None, None, None, False,
                                 0x00000004,  # CREATE_SUSPENDED? no: 0 normal
                                 None, None, ctypes.byref(si), ctypes.byref(pi))
    # NOTE: creationflags 0x4 = CREATE_SUSPENDED is wrong; use 0
    return ok, pi

def find_game(max_wait=15.0):
    t0 = time.time()
    while time.time() - t0 < max_wait:
        result = []
        @ctypes.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        def cb(hwnd, _):
            cls = ctypes.create_unicode_buffer(64)
            user32.GetClassNameW(hwnd, cls, 64)
            if 'Kamui' in cls.value:
                result.append(hwnd)
            return True
        user32.EnumDesktopWindows(user32.GetThreadDesktop(kernel32.GetCurrentThreadId()), cb, 0)
        if result:
            return result[0]
        time.sleep(0.5)
    return None

class RECT(ctypes.Structure):
    _fields_ = [('l', ctypes.c_long), ('t', ctypes.c_long),
                ('r', ctypes.c_long), ('b', ctypes.c_long)]

def client_rect_screen(hwnd):
    r = RECT(); user32.GetClientRect(hwnd, ctypes.byref(r))
    pt = w.POINT(0, 0); user32.ClientToScreen(hwnd, ctypes.byref(pt))
    return pt.x, pt.y, r.r - r.l, r.b - r.t

def bitblt_capture(x, y, cw, ch, path):
    gdi32 = ctypes.windll.gdi32
    hdc = user32.GetDC(0)
    mem = gdi32.CreateCompatibleDC(hdc)
    bmi = ctypes.create_string_buffer(struct.pack(
        '<IiiHHIIiiII', 40, cw, -ch, 1, 32, 0, 0, 0, 0, 0, 0) + b'\0' * 12)
    ptr = ctypes.c_void_p()
    hbm = gdi32.CreateDIBSection(mem, bmi, 0, ctypes.byref(ptr), None, 0)
    old = gdi32.SelectObject(mem, hbm)
    gdi32.BitBlt(mem, 0, 0, cw, ch, hdc, x, y, 0x00CC0020)  # SRCCOPY
    import numpy as np, cv2
    arr = (ctypes.c_uint8 * (cw * ch * 4)).from_address(ptr.value)
    img = np.frombuffer(arr, dtype=np.uint8).reshape(ch, cw, 4).copy()
    cv2.imwrite(path, cv2.cvtColor(img, cv2.COLOR_BGRA2BGR))
    gdi32.SelectObject(mem, old); gdi32.DeleteObject(hbm)
    gdi32.DeleteDC(mem); user32.ReleaseDC(0, hdc)
    return img.mean()

def wake_click(hwnd):
    r = RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    cx, cy = (r.l + r.r) // 2, (r.t + r.b) // 2
    sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    user32.mouse_event(0x8000 | 0x0001, int(cx * 65535 / sw), int(cy * 65535 / sh), 0, 0)
    time.sleep(0.2)
    user32.mouse_event(0x0002, 0, 0, 0, 0); time.sleep(0.05)
    user32.mouse_event(0x0004, 0, 0, 0, 0)

def press_key(vk, hold=0.05):
    # INPUT struct with KEYBDINPUT
    INPUT = ctypes.create_string_buffer(struct.pack(
        '<I I H H I I I I', 1, 0, vk, 0, 0, 0, 0, 0), 40)  # wrong; build properly below
    # build properly
    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', w.WORD), ('wScan', w.WORD), ('dwFlags', w.DWORD),
                    ('time', w.DWORD), ('dwExtraInfo', ctypes.c_void_p)]
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', w.LONG), ('dy', w.LONG), ('mouseData', w.DWORD),
                    ('dwFlags', w.DWORD), ('time', w.DWORD),
                    ('dwExtraInfo', ctypes.c_void_p)]
    class _U(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT)]
    class IN(ctypes.Structure):
        _fields_ = [('type', w.DWORD), ('u', _U)]
    for flag in (0, 2):  # down, up
        inp = IN(); inp.type = 1; inp.u.ki.wVk = vk; inp.u.ki.dwFlags = flag
        user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(IN))
        time.sleep(hold)

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'shot'
    h = open_desktop()
    set_thread_desktop(h)
    if cmd == 'start':
        # normal creation
        si = STARTUPINFO(); si.cb = ctypes.sizeof(STARTUPINFO)
        si.lpDesktop = DESKTOP_NAME; si.dwFlags = 1; si.wShowWindow = 1
        pi = PROCESS_INFORMATION()
        ok = kernel32.CreateProcessW(GAME_EXE, None, None, None, False, 0,
                                     None, None, ctypes.byref(si), ctypes.byref(pi))
        print('started' if ok else f'fail {ctypes.GetLastError()}')
        if ok:
            hwnd = find_game()
            print('hwnd', hwnd)
            with open('cnmod/work/game_pid.txt', 'w') as f:
                f.write(str(pi.dwProcessId))
    elif cmd == 'shot':
        hwnd = find_game(2)
        if not hwnd:
            print('no game window'); return
        x, y, cw, ch = client_rect_screen(hwnd)
        m = bitblt_capture(x, y, cw, ch, sys.argv[2] if len(sys.argv) > 2 else 'cnmod/work/desk_shot.png')
        print('shot', cw, 'x', ch, 'mean', round(float(m), 1))
    elif cmd == 'fullshot':
        sw, sh = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
        m = bitblt_capture(0, 0, sw, sh, sys.argv[2] if len(sys.argv) > 2 else 'cnmod/work/desk_full.png')
        print('fullshot', sw, 'x', sh, 'mean', round(float(m), 1))
    elif cmd == 'key':
        hwnd = find_game(2)
        if hwnd:
            wake_click(hwnd) if False else None
        press_key(int(sys.argv[2], 0))
        print('key', sys.argv[2])
    elif cmd == 'click':
        hwnd = find_game(2)
        if hwnd:
            wake_click(hwnd); print('clicked')
    elif cmd == 'title':
        hwnd = find_game(2)
        if hwnd:
            t = ctypes.create_unicode_buffer(64)
            user32.GetWindowTextW(hwnd, t, 64)
            print(t.value)
    elif cmd == 'stop':
        pid = open('cnmod/work/game_pid.txt').read().strip()
        kernel32.TerminateProcess(ctypes.c_void_p(int(pid)), 0)
        print('terminated', pid)

if __name__ == '__main__':
    main()
