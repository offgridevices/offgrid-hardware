"""Gate: the mark and lockup in mark.py match the brand hand-off.

Two independent checks:
1. Numbers: ring centre, stroke, node, opening, lockup placement.
2. Pixels: Chromium renders the brand's own SVG (the path string from the
   hand-off, and the lockup's text as SVG text in the brand font); PIL
   rasterises mark.py's geometry; the two must overlap (IoU) almost
   completely.

    <venv>/bin/python verify_mark.py [chromium]

Writes mark-reference.png (ours over the brand's, for the eye) and exits
non-zero on any failure.
"""
import os
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image, ImageChops, ImageDraw

import mark as M

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = sys.argv[1] if len(sys.argv) > 1 else '/opt/pw-browsers/chromium-1194/chrome-linux/chrome'
fails = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''))
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- numbers
cx, cy = M.ring_centre()
check('ring centre (100, 107.97)', abs(cx - 100) < 1e-6 and abs(cy - 107.9714) < 1e-3, f'{cx:.3f}, {cy:.3f}')
p = M.proportions()
check('stroke 22 / radius 58', abs(p['stroke'] - 22 / 58) < 1e-9)
check('node r 17 / radius 58', abs(p['node_r'] - 17 / 58) < 1e-9)
check('opening half-angle 24.99 deg', abs(p['gap_half_deg'] - 24.987) < 0.01, f"{p['gap_half_deg']:.3f}")
g = M.mark()
x0, y0, x1, y1 = g.bounds
check('mark ink bounds', abs(x0 - 31) < 0.05 and abs(x1 - 169) < 0.05 and abs(y0 - 23) < 0.05
      and abs(y1 - (cy + 58 + 11)) < 0.05, f'{x0:.2f} {y0:.2f} {x1:.2f} {y1:.2f}')
m, w = M.lockup()
_, cap = M.word()
wx0, wy0, wx1, wy1 = w.bounds
caps_centre = M.MARK_AT[1] + cy                      # where the caps must centre
baseline = caps_centre + cap / 2
check('word starts at x 240 (+ side bearing)', 240 <= wx0 < 246, f'{wx0:.2f}')
check("word's caps centred on the ring", abs((baseline - cap / 2) - (M.MARK_AT[1] + cy)) < 1e-6)


# ---------------------------------------------------------------- pixels
def chrome_png(svg, w, h, out):
    with tempfile.TemporaryDirectory() as tmp:
        html = os.path.join(tmp, 'p.html')
        with open(html, 'w') as f:
            f.write(f'''<!doctype html><html><head><style>
@font-face{{font-family:IS;src:url(file://{M.SANS});}}
html,body{{margin:0;background:#fff;}}</style></head><body>{svg}</body></html>''')
        subprocess.run([CHROME, '--headless=new', '--no-sandbox', '--disable-gpu', '--hide-scrollbars',
                        '--allow-file-access-from-files', '--force-device-scale-factor=1',
                        f'--window-size={w},{h + 200}', f'--screenshot={out}', 'file://' + html],
                       check=True, capture_output=True)
    return Image.open(out).convert('L').crop((0, 0, w, h))


def ours_png(geoms, scale, w, h):
    im = Image.new('L', (w, h), 255)
    d = ImageDraw.Draw(im)
    for geom in geoms:
        for poly in M.polygons(geom):
            d.polygon([(x * scale, y * scale) for x, y in poly.exterior.coords], fill=0)
            for hole in poly.interiors:
                d.polygon([(x * scale, y * scale) for x, y in hole.coords], fill=255)
    return im


def iou(a, b):
    A = np.array(a) < 128
    B = np.array(b) < 128
    return (A & B).sum() / max((A | B).sum(), 1)


def worst_px(a, b, k):
    """Pixels where the two disagree in a band thicker than k-1 px: anti-
    aliasing differs along every edge by a pixel, a wrong shape by more."""
    from PIL import ImageFilter
    A = np.array(a) < 128
    B = np.array(b) < 128
    diff = Image.fromarray(((A ^ B) * 255).astype('uint8'))
    return int((np.array(diff.filter(ImageFilter.MinFilter(k))) > 0).sum())


S = 5   # px per brand unit
brand_mark_svg = (f'<svg width="{200 * S}" height="{200 * S}" viewBox="0 0 200 200">'
                  '<path d="M124.5 55.4 A58 58 0 1 1 75.5 55.4" fill="none" stroke="#000" '
                  'stroke-width="22" stroke-linecap="round"/><circle cx="100" cy="40" r="17" fill="#000"/></svg>')
tmpdir = tempfile.mkdtemp()
theirs = chrome_png(brand_mark_svg, 200 * S, 200 * S, os.path.join(tmpdir, 'mark.png'))
ours = ours_png([g], S, 200 * S, 200 * S)
v, bad = iou(theirs, ours), worst_px(theirs, ours, 3)
check('mark matches the brand SVG: no edge off by more than 1 px at 5 px/unit (0.2 units)', bad == 0,
      f'IoU {v:.4f}, {bad} px off')

S2 = 2
LW, LH = int(M.LOCKUP_BOX[0] * S2), int(M.LOCKUP_BOX[1] * S2)
brand_lockup_svg = (
    f'<svg width="{LW}" height="{LH}" viewBox="0 0 800 200">'
    f'<g transform="translate({M.MARK_AT[0]} {M.MARK_AT[1]})">'
    '<path d="M124.5 55.4 A58 58 0 1 1 75.5 55.4" fill="none" stroke="#000" stroke-width="22" '
    'stroke-linecap="round"/><circle cx="100" cy="40" r="17" fill="#000"/></g>'
    f'<text x="{M.WORD["x"]}" y="{baseline:.3f}" font-family="IS" font-size="{M.WORD["size"]}" '
    f'letter-spacing="{M.WORD["tracking"]}" style="font-variation-settings:\'wght\' {M.WORD["weight"]};'
    'font-weight:600;font-variant-ligatures:none;font-kerning:normal" fill="#000">OffGrid</text></svg>')
theirs_l = chrome_png(brand_lockup_svg, LW, LH, os.path.join(tmpdir, 'lockup.png'))
ours_l = ours_png([m, w], S2, LW, LH)
v, bad = iou(theirs_l, ours_l), worst_px(theirs_l, ours_l, 5)
check('lockup matches the brand SVG in the brand font: no edge off by more than 2 px at 2 px/unit (1 unit)',
      bad == 0, f'IoU {v:.4f}, {bad} px off')

# reference image: ours in Ember, the brand's outline in black over it
ref = Image.new('RGB', (LW, LH), (241, 236, 224))
ref.paste((255, 106, 0), mask=ImageChops.invert(ours_l))
edge = np.array(theirs_l) < 128
edge = edge ^ np.roll(edge, 1, 0) | edge ^ np.roll(edge, 1, 1)
arr = np.array(ref)
arr[edge] = (27, 24, 19)
Image.fromarray(arr).save(os.path.join(HERE, 'mark-reference.png'))

print('ALL PASS' if not fails else f'{len(fails)} FAILED')
sys.exit(1 if fails else 0)
