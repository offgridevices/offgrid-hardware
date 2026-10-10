"""Concept render of the faceplate: writes concept-faceplate.html, then
renders it to concept-faceplate.png with headless Chromium.

A sketch of what the silkscreen says and where, in the brand's colours and
type. It is not the board: the final layout comes from the generator.

    python3 concept_faceplate.py [path/to/chromium]

Fonts: ridge-3/fonts (branch claude/fpv-stack-3in), looked up beside this
repository's root or in FONTS_DIR.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('FONTS_DIR', os.path.join(HERE, '..', '..', 'ridge-3', 'fonts'))

PITCH, BONE, EMBER = '#1B1813', '#F1ECE0', '#FF6A00'
W, H = 84.0, 54.0                     # board, mm

# The brand arrow (ridge-3/src/brand.py arrow_mm): a flat 0.25 mm shaft and
# a solid head 0.9 mm each side of the shaft, 1.26 mm long.  One arrow, the
# same everywhere it is printed, so it always reads the same.
SHAFT, HEAD = 0.25, 0.9
HEAD_L = HEAD * 1.4


def arrow(x0, y0, x1, y1, colour=BONE):
    """Brand arrow from (x0, y0) to its tip at (x1, y1)."""
    import math
    d = math.hypot(x1 - x0, y1 - y0)
    ux, uy = (x1 - x0) / d, (y1 - y0) / d
    px, py = -uy, ux
    bx, by = x1 - ux * HEAD_L, y1 - uy * HEAD_L
    sx, sy = x1 - ux * HEAD_L * 0.9, y1 - uy * HEAD_L * 0.9
    shaft = (f'<line x1="{x0:.3f}" y1="{y0:.3f}" x2="{sx:.3f}" y2="{sy:.3f}" '
             f'stroke="{colour}" stroke-width="{SHAFT}" stroke-linecap="butt"/>')
    head = (f'<polygon points="{x1:.3f},{y1:.3f} {bx + px * HEAD:.3f},{by + py * HEAD:.3f} '
            f'{bx - px * HEAD:.3f},{by - py * HEAD:.3f}" fill="{colour}"/>')
    return shaft + head


def text(x, y, s, size, mono=False, anchor='start', colour=BONE, weight=500):
    cls = 'm' if mono else 's'
    return (f'<text class="{cls}" x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" '
            f'font-weight="{weight}" style="fill:{colour}">{s}</text>')


def button(cx, cy, r):
    return (f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="#2a2620" stroke="#4a443b" stroke-width="0.3"/>')


def face():
    o = []
    # the board
    o.append(f'<rect x="0" y="0" width="{W}" height="{H}" rx="4" fill="{PITCH}"/>')

    # -- the power path, edge to edge: Battery -> | -> Drone ------------------
    o.append(text(1.6, 18.6, 'Battery', 1.7))
    o.append(arrow(1.6, 20.6, 7.0, 20.6))
    o.append(text(W - 1.6, 18.6, 'Drone', 1.7, anchor='end'))
    o.append(arrow(W - 7.0, 20.6, W - 1.6, 20.6))

    # -- USB-C on the back edge -------------------------------------------------
    o.append(f'<rect x="38.5" y="-0.6" width="9" height="3.2" rx="1.2" fill="#6d665c"/>')
    o.append(arrow(43.0, 6.2, 43.0, 3.2))
    o.append(text(45.0, 5.6, 'USB-C: updates', 1.4))

    # -- screen ----------------------------------------------------------------
    o.append(f'<rect x="9" y="5" width="28" height="17" rx="1.2" fill="none" stroke="{BONE}" stroke-width="0.2"/>')
    o.append('<rect x="10.2" y="6.2" width="25.6" height="14.6" rx="0.6" fill="#0b0b0b"/>')
    green = '#9fe0a0'
    o.append(text(12, 11.6, '16.8V  4S', 3.0, mono=True, colour=green))
    o.append(text(12, 15.8, 'ON  0.42A', 2.3, mono=True, colour=green))
    o.append(text(12, 19.4, 'AUTO 2.0A · DRONE 3', 1.6, mono=True, colour=green))

    # -- Power: the Beacon Ring --------------------------------------------------
    cx, cy = 62.0, 17.5
    o.append(f'<g transform="translate({cx},{cy})">'
             f'<path d="M 3.4 -8.3 A 9 9 0 1 1 -3.4 -8.3" fill="none" stroke="{EMBER}" '
             f'stroke-width="2.2" stroke-linecap="round"/>'
             f'<circle cx="0" cy="-10.3" r="1.7" fill="{EMBER}"/>'
             f'<circle r="5.6" fill="#2a2620" stroke="#4a443b" stroke-width="0.3"/>'
             + text(0, 0.9, 'Power', 2.5, anchor='middle') + '</g>')
    o.append(text(cx, 31.6, 'Press to check, then power on', 1.8, anchor='middle'))
    o.append(text(cx, 34.0, 'Press again to turn off', 1.8, anchor='middle'))

    # -- Bind and Limit: an arrow from each label to its button ----------------
    o.append(button(12.5, 30.5, 3.4))
    o.append(arrow(23.0, 30.5, 17.0, 30.5))
    o.append(text(24.2, 30.0, 'Bind', 2.2))
    o.append(text(24.2, 32.5, 'Puts the receiver in bind', 1.5))
    o.append(button(12.5, 40.5, 3.4))
    o.append(arrow(23.0, 40.5, 17.0, 40.5))
    o.append(text(24.2, 40.0, 'Limit', 2.2))
    o.append(text(24.2, 42.5, 'AUTO 1A 2A 5A 10A 20A', 1.4, mono=True))
    o.append(text(24.2, 44.3, '20A: props off', 1.4))

    # -- ring legend --------------------------------------------------------------
    for (x, y, c, s) in ((47.0, 38.4, BONE, 'Checking'), (65.0, 38.4, '#4caf50', 'On, safe'),
                         (47.0, 41.6, EMBER, 'Look at screen'), (65.0, 41.6, '#e53935', 'Stopped')):
        o.append(f'<circle cx="{x}" cy="{y}" r="0.8" fill="{c}"/>')
        o.append(text(x + 1.6, y + 0.6, s, 1.6))

    # -- the three steps, joined by arrows --------------------------------------
    o.append(f'<line x1="5" y1="46.4" x2="{W - 5}" y2="46.4" stroke="{BONE}" stroke-width="0.15"/>')
    y = 50.4
    steps = [(5.0, '1  Battery in'), (22.5, '2  Drone in'), (38.5, '3  Press Power')]
    for i, (x, s) in enumerate(steps):
        o.append(text(x, y, s, 1.9))
    o.append(arrow(17.0, y - 0.65, 20.8, y - 0.65))
    o.append(arrow(32.8, y - 0.65, 36.6, y - 0.65))

    # -- lockup ---------------------------------------------------------------------
    o.append(f'<g transform="translate(65.6,47.7) scale(0.024)">'
             f'<path d="M124.5 55.4 A58 58 0 1 1 75.5 55.4" fill="none" stroke="{BONE}" stroke-width="22" stroke-linecap="round"/>'
             f'<circle cx="100" cy="40" r="17" fill="{BONE}"/></g>')
    o.append(f'<text x="71" y="50.7" font-family="IS" font-weight="600" font-size="3.1" fill="{BONE}" letter-spacing="-0.1">OffGrid</text>')
    return '\n'.join(o)


def page():
    leads = (f'<rect x="-14" y="17" width="14" height="3" rx="1.5" fill="#b5302b"/>'
             f'<rect x="-14" y="24" width="14" height="3" rx="1.5" fill="#222"/>'
             f'<rect x="{W}" y="17" width="14" height="3" rx="1.5" fill="#b5302b"/>'
             f'<rect x="{W}" y="24" width="14" height="3" rx="1.5" fill="#222"/>')
    note = ('<text x="0" y="-7" font-family="IS" font-weight="500" font-size="2.2" fill="#5b5650">'
            'Concept faceplate, 84 x 54 mm, top view. Not the final layout.</text>')
    return f'''<!doctype html>
<html><head><meta charset="utf-8">
<style>
@font-face{{font-family:IS;src:url({FONTS}/InstrumentSans-VariableFont.ttf);}}
@font-face{{font-family:JB;src:url({FONTS}/JetBrainsMono-VariableFont.ttf);}}
html,body{{margin:0;background:#d9d4c8;}}
svg{{display:block}}
.s{{font-family:IS;letter-spacing:.01em}}
.m{{font-family:JB;letter-spacing:.06em}}
</style></head><body>
<svg width="1700" height="1140" viewBox="-14 -11 112 74">
{note}
{leads}
{face()}
</svg></body></html>'''


if __name__ == '__main__':
    html = os.path.join(HERE, 'concept-faceplate.html')
    with open(html, 'w') as f:
        f.write(page())
    chrome = sys.argv[1] if len(sys.argv) > 1 else 'chromium'
    subprocess.run([chrome, '--headless=new', '--no-sandbox', '--disable-gpu',
                    '--allow-file-access-from-files', '--hide-scrollbars',
                    '--window-size=1700,1140',
                    '--screenshot=' + os.path.join(HERE, 'concept-faceplate.png'),
                    'file://' + html], check=True, capture_output=True)
