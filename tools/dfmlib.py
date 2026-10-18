# -*- coding: utf-8 -*-
"""Delphi binary DFM (TPF0) parser/patcher.

Streams are walked with an explicit cursor so that every value's exact
file offset is recorded; patching rewrites the stream from the recorded
tree, allowing string lengths to change as long as the rebuilt resource
does not exceed the original size (caller pads the tail with zeros).
"""
import struct

# Delphi TValueType (from Classes.pas)
vaNull, vaList, vaInt8, vaInt16, vaInt32, vaExtended, vaString, vaIdent, \
    vaFalse, vaTrue, vaBinary, vaSet, vaLString, vaNil, vaCollection = range(0, 15)

VALUENAMES = {1: 'List', 2: 'Int8', 3: 'Int16', 4: 'Int32', 5: 'Extended',
              6: 'String', 7: 'Ident', 8: 'False', 9: 'True', 10: 'Binary',
              11: 'Set', 12: 'LString', 13: 'Nil', 14: 'Collection'}


class Node:
    def __init__(self, cls, name, parent):
        self.cls, self.name, self.parent = cls, name, parent
        self.props = []          # (name, type, value, value_ofs)
        self.children = []
    def path(self):
        p = self.parent.path() + '.' if self.parent else ''
        return p + (self.name or self.cls)


class Reader:
    def __init__(self, data):
        self.d = data
        self.pos = 0
        # patchable string values: (kind, prefix_ofs, prefix_len, payload)
        # kind: 'str' (vaString), 'lstr' (vaLString), 'ident' (vaIdent)
        self.records = []
    def u8(self):
        v = self.d[self.pos]; self.pos += 1; return v
    def take(self, n):
        v = self.d[self.pos:self.pos + n]; self.pos += n; return v
    def shortstr(self):
        return self.take(self.u8())
    def longstr(self):
        n = struct.unpack_from('<I', self.d, self.pos)[0]
        self.pos += 4
        return self.take(n)


def read_value(r, t):
    if t == vaInt8: return r.u8()
    if t == vaInt16: return struct.unpack('<h', r.take(2))[0]
    if t == vaInt32: return struct.unpack('<i', r.take(4))[0]
    if t == vaExtended: return r.take(10)
    if t == vaString:
        ofs = r.pos
        s = r.shortstr()
        r.records.append(('str', ofs, 1, s))
        return s
    if t == vaLString:
        ofs = r.pos
        s = r.longstr()
        r.records.append(('lstr', ofs, 4, s))
        return s
    if t == vaIdent:
        ofs = r.pos
        s = r.shortstr()
        r.records.append(('ident', ofs, 1, s))
        return s
    if t in (vaFalse, vaTrue): return t == vaTrue
    if t == vaNil: return None
    if t == vaBinary: return ('BIN', r.longstr())
    if t == vaList:
        vals = []
        while True:
            b = r.d[r.pos]
            if b == 0: r.u8(); break
            vals.append(read_value(r, r.u8()))
        return ('LIST', vals)
    if t == vaSet:
        vals = []
        while True:
            s = r.shortstr()
            if not s: break
            vals.append(s)
        return ('SET', vals)
    if t == vaCollection:
        items = []
        while True:
            b = r.d[r.pos]
            if b == 0: r.u8(); break
            item = []
            # optional int index first
            if b in (vaInt8, vaInt16, vaInt32):
                read_value(r, r.u8())
            while r.d[r.pos] != 0:
                name = r.shortstr()
                item.append((name, read_value(r, r.u8())))
            r.u8()
            items.append(item)
        return ('COLL', items)
    raise ValueError('bad value type %d @%#x' % (t, r.pos))


def read_props(r, node):
    while True:
        b = r.d[r.pos]
        if b == 0:
            r.u8(); return
        if b == 0xFF and r.d[r.pos + 1] == 0xFF:
            r.take(2)
            read_object(r, node)
            continue
        name = r.shortstr().decode('latin1')
        t = r.u8()
        vofs = r.pos
        node.props.append((name, t, read_value(r, t), vofs))


def read_object(r, parent):
    cls = r.shortstr().decode('latin1')
    name = r.shortstr().decode('latin1')
    node = Node(cls, name, parent)
    if parent: parent.children.append(node)
    read_props(r, node)
    while r.d[r.pos] != 0:
        read_object(r, node)
    r.u8()
    return node


def parse(data):
    assert data[:4] == b'TPF0', 'not TPF0'
    r = Reader(data[4:])
    root = read_object(r, None)
    return root, r.pos + 4


def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)
