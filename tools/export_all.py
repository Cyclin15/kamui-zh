# -*- coding: utf-8 -*-
"""Export every DAR entry as PNG + a manifest CSV into cnmod/export/."""
import sys, os, csv, glob
sys.path.insert(0, os.path.dirname(__file__))
from darlib import load

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(ROOT, 'cnmod', 'export')

rows = []
for path in sorted(glob.glob(os.path.join(ROOT, 'pat', '*.DAR'))):
    dar = load(path)
    base = os.path.splitext(os.path.basename(path))[0]
    outdir = os.path.join(OUT, base)
    os.makedirs(outdir, exist_ok=True)
    for e in dar.entries:
        name = (e.name or '').replace('\x00', '')
        safe = ''.join(c if c.isalnum() or c in '_-' else '_' for c in name)[:40]
        fname = f'{e.idx:04d}' + (f'_{safe}' if safe else '') + '.png'
        dar.entry_png(e).save(os.path.join(outdir, fname))
        rows.append([base, e.idx, name, e.f0, e.fd, e.height, e.width, e.f6,
                     e.fa, e.fc,
                     (e.type_info[0] >> 3) if e.type_info else '',
                     e.data_ofs, e.data_size])

with open(os.path.join(OUT, 'manifest.csv'), 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['file', 'idx', 'name', 'disp_w(f0)', 'disp_h(fd)', 'rows(h)',
                'pitch(w)', 'f6', 'anchor_y(fa)', 'anchor_x(fc)', 'pal_bank',
                'data_ofs', 'data_size'])
    w.writerows(rows)
print('exported', len(rows), 'entries ->', OUT)
