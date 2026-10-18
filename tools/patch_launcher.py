# -*- coding: utf-8 -*-
"""Localize the KAMUI launcher (config.exe / SetupKamui.exe) to Simplified
Chinese.

Two patch layers per exe:
1. .data EN string literals (the branch used on non-Japanese systems):
   in-place overwrite, NUL-padded; every replacement must be <= original.
2. .rsrc DFM form (TMAINFORM, TPF0): splice-patch recorded string values,
   rebuild shrink-only, pad the resource tail with zeros to keep the
   resource header size unchanged.  Font -> SimSun / GB2312_CHARSET.

Backups are written to cnmod/backup/ first.  Run with --dry to preview.
"""
import os
import shutil
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dfmlib

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
BACKUP = os.path.join(ROOT, 'cnmod', 'backup')

# --- translations ---------------------------------------------------------
# .data EN literal -> Chinese (GBK). Byte length must be <= original.
DATA_MAP = [
    (b'Kamui Startup Menu ver1.12en', '神威启动菜单 ver1.12'),
    (b'Start in Full Screen', '以全屏模式启动'),
    (b'Use Portrait Orientation', '画面竖置显示'),
    (b'Start in 640x480 Resolution', '以高分辨率(640x480)启动'),
    (b'Apply Filters', '启用滤镜'),
    (b'16:9 Display Support (only available in full screen mode)', '16:9 画面支持（仅全屏时有效）'),
    (b'16:9 Display Support (Valid Only when in Full Screen)', '16:9 画面支持（仅全屏时有效）'),
    (b'Use Vertical Sync', '开启垂直同步'),
    (b'Game Resolution', '画面分辨率'),
    (b'Rotate Display', '画面旋转'),
    (b'Rotate Controls', '控制器旋转'),
    (b'Rotation(Game)', '画面旋转'),
    (b'Rotation(Game Pad)', '控制器旋转'),
    (b'Zoom (Portrait Mode Only)', '画面缩放（仅竖屏模式）'),
    (b'Default', '标准'),
    (b'Rotate Right', '向右旋转'),
    (b'Right Rotate', '向右旋转'),
    (b'Invert', '倒置'),
    (b'Reverse', '倒置'),
    (b'Rotate Left', '向左旋转'),
    (b'Left Rotate', '向左旋转'),
    (b'Fixed', '固定'),
    (b'Fixation', '固定'),
    (b'Match Game Rotation', '跟随游戏画面'),
    (b'The Same as the Game Screen', '跟随游戏画面'),
    (b'Start Game', '开始游戏'),
    (b'Default Settings', '恢复默认设置'),
    (b'Quit', '退出'),
    (b'Initialize Settings. OK?', '要恢复默认设置吗？'),
    (b'Confirmation', '确认'),
]

# DFM string value (decoded cp932) -> Chinese (GBK), by content.
DFM_MAP = {
    'Kamui Startup Menu ver1.12en': '神威启动菜单 ver1.12',
    'Startup Options': '启动选项',
    'Start in Full Screen': '以全屏模式启动',
    'Use Portrait Orientation': '画面竖置显示',
    'Start in 640x480 Resolution': '以高分辨率(640x480)启动',
    'Apply Filters': '启用滤镜',
    '16:9 Display Support (Valid Only when in Full Screen)': '16:9 画面支持（仅全屏时有效）',
    '16:9 Display Support (only available in full screen mode)': '16:9 画面支持（仅全屏时有效）',
    'Use Vertical Sync': '开启垂直同步',
    'Game Resolution': '画面分辨率',
    'Rotation(Game Screen)': '画面旋转',
    'Rotation(Game)': '画面旋转',
    'Rotation(Dipslay)': '控制器旋转',
    'Rotation(Display)': '控制器旋转',
    'Rotation(Game Pad)': '控制器旋转',
    'Zoom (Portrait Mode Only)': '画面缩放（仅竖屏模式）',
    'Default': '标准',
    'Rotate Right': '向右旋转',
    'Right Rotate': '向右旋转',
    'Invert': '倒置',
    'Reverse': '倒置',
    'Rotate Left': '向左旋转',
    'Left Rotate': '向左旋转',
    'Fixed': '固定',
    'Fixation': '固定',
    'Match Game Rotation': '跟随游戏画面',
    'The Same as the Game Screen': '跟随游戏画面',
    'Start Game': '开始游戏',
    'Default Settings': '恢复默认设置',
    'Quit': '退出',
    '説明書を開く': '打开说明书',
    '終了します': '退出程序',
    '800 x 600 (Default)': '800 x 600（默认）',
    'ＭＳ Ｐゴシック': '宋体',           # Font.Name
}
DFM_IDENT_MAP = {b'SHIFTJIS_CHARSET': b'GB2312_CHARSET'}   # Font.Charset


def sections(d):
    pe = struct.unpack_from('<I', d, 0x3c)[0]
    n = struct.unpack_from('<H', d, pe + 6)[0]
    opt = struct.unpack_from('<H', d, pe + 20)[0]
    out = []
    for i in range(n):
        off = pe + 24 + opt + i * 40
        name = d[off:off + 8].rstrip(b'\x00').decode()
        vs, va, rs, ra = struct.unpack_from('<IIII', d, off + 8)
        out.append((name, va, ra, rs))
    return out


def patch_data_literals(d, log):
    """Overwrite EN literals in the .data EN block; returns patched bytes."""
    en_start = d.find(b'Kamui Startup Menu ver1.12en\x00')
    assert en_start != -1, 'EN title literal not found'
    jp = d.find('神威 起動メニュー'.encode('cp932'), en_start)
    assert jp != -1, 'JP title literal not found'
    block_end = jp
    patched = 0
    for en, zh in DATA_MAP:
        zh_b = zh.encode('gbk')
        assert len(zh_b) <= len(en), f'{zh!r} longer than {en!r}'
        pat = en + b'\x00'
        i = d.find(pat, en_start, block_end)
        if i == -1:
            log(f'  [data] MISSING: {en!r}')
            continue
        assert d.find(pat, i + 1, block_end) == -1, f'dup: {en!r}'
        rep = zh_b + b'\x00' * (len(en) + 1 - len(zh_b))
        d = d[:i] + rep + d[i + len(en) + 1:]
        patched += 1
        log(f'  [data] {en.decode():55} -> {zh}')
    return d, patched


def find_dfm(d):
    """Return (offset, size) of the single TPF0 resource inside .rsrc."""
    rsrc = [(va, ra, rs) for n, va, ra, rs in sections(d) if n == '.rsrc'][0]
    va, ra, rs = rsrc
    hits = []
    i = ra
    while True:
        i = d.find(b'TPF0', i, ra + rs)
        if i == -1:
            break
        hits.append(i)
        i += 1
    assert len(hits) == 1, f'expected 1 TPF0, got {hits}'
    start = hits[0]
    # resource size = walk up to the next resource entry; instead parse
    # the directory tree for the RCDATA entry covering this offset
    size = None
    def parse_dir(off):
        nonlocal size
        _, _, _, _, nn, ni = struct.unpack_from('<IIHHHH', d, off)
        for k in range(nn + ni):
            nameid, offset = struct.unpack_from('<II', d, off + 16 + k * 8)
            if offset & 0x80000000:
                parse_dir(ra + (offset & 0x7fffffff))
            else:
                de = ra + offset
                drva, dsize, _, _ = struct.unpack_from('<IIII', d, de)
                if ra + (drva - va) == start:
                    size = dsize
    parse_dir(ra)
    assert size, 'TPF0 resource size not found'
    return start, size


def patch_dfm(d, log):
    start, size = find_dfm(d)
    data = d[start:start + size]
    root, consumed = dfmlib.parse(data)
    assert consumed == size, f'DFM parse {consumed} != resource {size}'
    patches = []
    for kind, ofs, plen, payload in dfmlib_parse_records(data):
        try:
            text = payload.decode('cp932')
        except UnicodeDecodeError:
            continue
        if kind == 'ident':
            if payload in DFM_IDENT_MAP:
                patches.append((ofs, plen, payload, DFM_IDENT_MAP[payload]))
                log(f'  [dfm] ident {text!r} -> GB2312_CHARSET')
            continue
        if text in DFM_MAP:
            zh = DFM_MAP[text].encode('gbk')
            patches.append((ofs, plen, payload, zh))
            log(f'  [dfm] {text!r} -> {DFM_MAP[text]}')
    # splice descending so earlier offsets stay valid
    for ofs, plen, old, new in sorted(patches, reverse=True):
        new_prefix = (struct.pack('<B', len(new)) if plen == 1
                      else struct.pack('<I', len(new)))
        assert len(new) < 0x100 or plen == 4
        data = data[:ofs] + new_prefix + new + data[ofs + plen + len(old):]
    assert len(data) <= size, f'DFM grew: {len(data)} > {size}'
    data = data + b'\x00' * (size - len(data))
    # re-parse to validate the spliced stream
    root2, consumed2 = dfmlib.parse(data)
    assert consumed2 <= size
    return d[:start] + data + d[start + size:], len(patches)


_RECORDS_HACK = {}


def dfmlib_parse_records(data):
    """Re-parse capturing Reader.records (dfmlib.parse doesn't expose it).

    The Reader is positioned at 4 (after TPF0) on the full buffer so the
    recorded offsets index directly into `data`.
    """
    assert data[:4] == b'TPF0'
    r = dfmlib.Reader(data)
    r.pos = 4
    dfmlib.read_object(r, None)
    return r.records


def main():
    dry = '--dry' in sys.argv
    os.makedirs(BACKUP, exist_ok=True)
    total = 0
    for exe in ('config.exe', 'SetupKamui.exe'):
        path = os.path.join(ROOT, exe)
        log = (lambda m: print(m)) if dry else (lambda m: print(m))
        with open(path, 'rb') as f:
            d = f.read()
        print(f'== {exe} ({len(d)} bytes)')
        bak = os.path.join(BACKUP, exe)
        if not dry and not os.path.exists(bak):
            shutil.copy2(path, bak)
            print(f'  backup -> {bak}')
        d, n1 = patch_data_literals(d, log)
        d, n2 = patch_dfm(d, log)
        print(f'  data literals patched: {n1}, dfm strings patched: {n2}')
        if not dry:
            with open(path, 'wb') as f:
                f.write(d)
            print(f'  written ({len(d)} bytes)')
        total += 1
    print('OK' if not dry else 'DRY RUN OK')


if __name__ == '__main__':
    main()
