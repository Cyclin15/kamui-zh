# -*- coding: utf-8 -*-
"""Map DAR text entries to manual screenshots via blurred NCC + OCR word boxes."""
import cv2, json, os, subprocess, sys
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, 'cnmod', 'tools'))
import darlib

WORK = os.path.join(ROOT, 'cnmod', 'work')
SCREENS = ['title1', 'title2', 'stsel', 'setup', 'config', 'gamemain',
           'game01', 'game02', 'game03', 'game04', 'game05', 'game06',
           'sc_hlong', 'sc_hnomal', 'sis_ban']
DARS = [  # (path, template scale)
    ('pat/KAM_Title.DAR', 1.0),
    ('pat/KAM_Titleplus2.DAR', 0.5),
    ('pat/KAM_TitlePlus.DAR', 1.0),
]


def ocr_boxes(png):
    out = subprocess.run(
        ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
         '-File', os.path.join(ROOT, 'cnmod', 'tools', 'ocr_boxes.ps1'),
         '-Path', png, '-Scale', '3', '-Lang', 'ja'],
        capture_output=True, text=True, encoding='gbk', errors='replace')
    boxes = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if '|' not in line:
            continue
        xywh, text = line.split('|', 1)
        try:
            x, y, w, h = (int(v) for v in xywh.split(','))
        except ValueError:
            continue
        boxes.append((x, y, w, h, text.replace(' ', '')))
    return boxes


def main():
    cache_path = os.path.join(WORK, 'ocr_boxes.json')
    if os.path.exists(cache_path):
        with open(cache_path, encoding='utf-8') as f:
            boxes_by_screen = json.load(f)
    else:
        boxes_by_screen = {}
        for s in SCREENS:
            png = os.path.join(ROOT, 'manual', s + '.png')
            if not os.path.exists(png):
                continue
            boxes_by_screen[s] = ocr_boxes(png)
        with open(cache_path, 'w', encoding='utf-8') as f:
            json.dump(boxes_by_screen, f, ensure_ascii=False, indent=1)

    shots = {}
    for s in boxes_by_screen:
        img = cv2.imread(os.path.join(ROOT, 'manual', s + '.png'), cv2.IMREAD_GRAYSCALE)
        shots[s] = cv2.blur(img.astype(np.float32), (2, 2))

    for rel, scale in DARS:
        dar = darlib.load(os.path.join(ROOT, rel))
        lut = np.array([0.299*r + 0.587*g + 0.114*b for (r, g, b) in dar.palette],
                       dtype=np.float32)
        print(f'=== {rel} ===')
        for e in dar.entries:
            if e.height not in (8, 16, 24, 32) or e.width < 12:
                continue
            d = np.frombuffer(e.load_data(dar.raw), dtype=np.uint8) \
                .reshape(e.height, e.width)[::-1]
            tmpl = lut[d]
            if scale != 1.0:
                tmpl = cv2.resize(tmpl, (int(e.width*scale), int(e.height*scale)),
                                  interpolation=cv2.INTER_AREA)
            tmpl = cv2.blur(tmpl, (2, 2))
            if tmpl.shape[0] > 240 or tmpl.shape[1] > 240:
                print(f'#{e.idx:3d} {(e.name or "?"):26s} {e.width}x{e.height}  TOO BIG')
                continue
            best = (None, -1, None)
            for s, shot in shots.items():
                if tmpl.shape[0] > shot.shape[0] or tmpl.shape[1] > shot.shape[1]:
                    continue
                res = cv2.matchTemplate(shot, tmpl, cv2.TM_CCOEFF_NORMED)
                _, mx, _, loc = cv2.minMaxLoc(res)
                if mx > best[1]:
                    best = (s, mx, loc)
            s, mx, (x, y) = best
            th, tw = tmpl.shape[:2]
            # OCR words overlapping the matched rect
            words = []
            for (bx, by, bw, bh, text) in boxes_by_screen.get(s, []):
                if bx < x + tw and bx + bw > x and by < y + th and by + bh > y:
                    words.append(f'{text}@{bx},{by}')
            print(f'#{e.idx:3d} {(e.name or "?"):26s} {e.width}x{e.height}  '
                  f'{s} ({x},{y}) ncc={mx:.3f}  [{" ".join(words)}]')


if __name__ == '__main__':
    main()
