# -*- coding: utf-8 -*-
"""KAMUI (WinGL) DAR:8 archive library - validated by reverse engineering Kamui.exe.

On-disk format:
  [0:5]   "DAR:8"
  [5]     version (u8, 0 or 1)
  [6:8]   entry count (u16 LE)
  [8:12]  palette offset (u32 LE, always 4 -> palette at file+0xC)
  [0xC:0x40C]  palette: 256 entries x 4 bytes B,G,R,X
  entries follow sequentially from 0x40C, no offset table.

Entry layout (version 1):
  +0   u16 hsize      bytes of header that follow this size field
  +2   u16 f0         display width (biWidth / ROP draw width)
  +4   u16 height     memory rows (biHeight / data rows)
  +6   u16 width      memory pitch (bytes per row on disk)
  +8   s16 f6         type/state (-1 = direct data; 0/250 special)
  +0xa u16 fa         anchor Y (used by ROP draw)
  +0xc u16 fc         anchor X
  +0xe u16 fd         display height (defaults to `height` when hsize < 0xE)
  +0x10 u8  namelen   = strlen(name)+2 (name field is namelen-1 bytes incl NUL)
  +0x11     name      ASCII, NUL-terminated, namelen-1 bytes total
  ...      type_info  4 bytes if hsize >= namelen+0x12 (byte0>>3 = palette bank)
  data: width*height raw palette indices (uncompressed), then next entry.

Rendering (from disassembly): main path reads raw data ptr with pitch=width,
draws f0 x fd pixels using the file palette (bank from type_info). Keep all
header bytes byte-identical when repacking; only swap pixel data.
"""
import struct


class Entry:
    __slots__ = ('idx', 'hdr_ofs', 'raw_header', 'hsize', 'f0', 'height', 'width',
                 'f6', 'fa', 'fc', 'fd', 'name', 'type_info', 'data_ofs')

    @property
    def data_size(self):
        return self.width * self.height

    def load_data(self, dar_bytes):
        return dar_bytes[self.data_ofs:self.data_ofs + self.data_size]


class Dar:
    def __init__(self, raw, filename=''):
        self.raw = raw
        self.filename = filename
        assert raw[:5] == b'DAR:8', 'bad magic'
        self.version = raw[5]
        self.count = struct.unpack_from('<H', raw, 6)[0]
        self.pal_ofs = 8 + struct.unpack_from('<I', raw, 8)[0]
        self.palette = [(raw[self.pal_ofs + i * 4 + 2],
                         raw[self.pal_ofs + i * 4 + 1],
                         raw[self.pal_ofs + i * 4 + 0]) for i in range(256)]
        self.entries = []
        pos = 0x40C
        for i in range(self.count):
            hsize = struct.unpack_from('<H', raw, pos)[0]
            e = Entry()
            e.idx = i
            e.hdr_ofs = pos
            e.hsize = hsize
            e.f0, e.height, e.width = struct.unpack_from('<HHH', raw, pos + 2)
            e.f6 = struct.unpack_from('<h', raw, pos + 8)[0]
            e.fa, e.fc, e.fd = (struct.unpack_from('<HHH', raw, pos + 0xA)
                                if hsize >= 0xE else (0, 0, e.height))
            e.name = None
            e.type_info = None
            if hsize >= 0x10:
                namelen = raw[pos + 0x10]
                if namelen:
                    e.name = raw[pos + 0x11:pos + 0x11 + namelen - 1].decode('ascii', 'replace')
                if hsize >= namelen + 0x12:
                    e.type_info = raw[pos + 0x10 + namelen:pos + 0x10 + namelen + 4]
            # raw header = size field + hsize bytes, kept verbatim for repack
            e.raw_header = raw[pos:pos + 2 + hsize]
            e.data_ofs = pos + 2 + hsize
            self.entries.append(e)
            pos = e.data_ofs + e.data_size
        assert pos == len(raw), f'{filename}: walk ended at {pos} != {len(raw)}'

    def entry_png(self, e):
        from PIL import Image
        data = e.load_data(self.raw)
        img = Image.frombytes('P', (e.width, e.height), bytes(data))
        img.putpalette([c for rgb in self.palette for c in rgb])
        return img.convert('RGB')

    def replace_data(self, e, new_pixels):
        """new_pixels: width*height bytes of palette indices (same size as original)."""
        assert len(new_pixels) == e.data_size, \
            f'entry #{e.idx}: need {e.data_size} bytes, got {len(new_pixels)}'
        self.raw = (self.raw[:e.data_ofs] + bytes(new_pixels)
                    + self.raw[e.data_ofs + e.data_size:])

    def save(self, path):
        with open(path, 'wb') as f:
            f.write(self.raw)


def load(path):
    with open(path, 'rb') as f:
        return Dar(f.read(), path)
