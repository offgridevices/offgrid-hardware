"""Face layout options, to scale, with G2 (curvature-continuous) corners.
python3 layout.py -> 1-face-options.png, 2-screen-corners.png"""
import math
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle

HERE = os.path.dirname(os.path.abspath(__file__))
SB = os.path.dirname(os.path.dirname(HERE))
BG, INK, BODY, WIN, WELL, EMB, MUTE = '#E9E4D8', '#1B1813', '#2A2621', '#0B0A08', '#14120F', '#E35D00', '#8A8273'

W, D = 100.0, 58.0
TX, TY = 76.2, 22.5                    # toggle (face mm, from the left / back edges), fixed by the board
WELL_W, WELL_H, WELL_CX = 36.7, 22.7, 33.25   # the five sockets fix the well's size and centre
ROCK_W, ROCK_H = 26.0, 8.0


def g2_rect(x0, y0, w, h, r, n=5.0, k=16):
    """Rounded rectangle whose corners are superellipse quadrants
    |x|^n + |y|^n = r^n: the curvature runs from zero at the straight edge
    to a maximum at 45 degrees and back, so every joint is G2."""
    pts = []
    corners = [(x0 + w - r, y0 + r, -90), (x0 + w - r, y0 + h - r, 0), (x0 + r, y0 + h - r, 90), (x0 + r, y0 + r, 180)]
    for cx, cy, a0 in corners:
        for i in range(k + 1):
            t = math.radians(a0 + 90 * i / k)
            c, s = math.cos(t), math.sin(t)
            pts.append((cx + r * math.copysign(abs(c) ** (2 / n), c), cy + r * math.copysign(abs(s) ** (2 / n), s)))
    return pts


def face(ax, title, scr, well, guard_w, notes, rules):
    ax.set_facecolor(BG)
    ax.add_patch(Polygon(g2_rect(0, 0, W, D, 9), fc=BODY, ec=INK))
    sx, sy, sw, sh = scr
    ax.add_patch(Polygon(g2_rect(sx, sy, sw, sh, 3), fc=WIN, ec='#3A352E'))
    ax.text(sx + sw / 2, sy + sh / 2, 'screen', color='#6E675C', ha='center', va='center', fontsize=10)
    wx, wy = well
    ax.add_patch(Polygon(g2_rect(wx, wy, WELL_W, WELL_H, 2.5), fc=WELL, ec='#3A352E'))
    for i, n in enumerate((3, 4, 5, 6, 7)):
        px = wx + 1.2 + 2.875 + 7.1 * i
        L = 2.5 * (n - 1) + 4.9
        ax.add_patch(Polygon(g2_rect(px - 2.875, wy + WELL_H - 1.6 - L, 5.75, L, 0.6), fc='#EDEAE2', ec='none'))
        ax.text(px, D - 2.6, f'{n - 1}S', color='#F1ECE0', ha='center', va='center', fontsize=8, fontweight='bold')
    # toggle, ring, guard footprint, rocker centred under the toggle
    ax.add_patch(Circle((TX, TY), 10.0, fill=False, ec='#7CC88F', lw=2.2))
    ax.add_patch(Circle((TX, TY), 3.0, fc='#B8BCC0', ec='none'))
    gx0 = TX - guard_w / 2
    ax.add_patch(Polygon(g2_rect(gx0, 9.0, guard_w, 31.5, 2), fill=False, ec=EMB, lw=1.4, ls='--'))
    ax.add_patch(Polygon(g2_rect(TX - ROCK_W / 2, 44.0, ROCK_W, ROCK_H, 2.5), fc='#B9BDC1', ec='none'))
    ax.text(TX - 6.5, 48.0, '−', ha='center', va='center', fontsize=11, color=INK)
    ax.text(TX + 6.5, 48.0, '+', ha='center', va='center', fontsize=11, color=INK)
    ax.plot([TX, TX], [45.2, 50.8], c=INK, lw=0.8)
    ax.text(TX, D - 2.6, 'LIMIT', color='#F1ECE0', ha='center', va='center', fontsize=8, fontweight='bold')
    ax.plot([TX, TX], [-2, D + 2], c=EMB, lw=0.6, ls=':')
    # dimensions
    def dim(x0, y0, x1, y1, label, off=(0, 0), col=EMB):
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle='<->', color=col, lw=1.2,
                                                                       shrinkA=0, shrinkB=0))
        ax.text((x0 + x1) / 2 + off[0], (y0 + y1) / 2 + off[1], label, color=col, fontsize=9, ha='center',
                va='center', bbox=dict(fc=BODY, ec='none', pad=0.6))
    dim(sx + sw * 0.25, 0, sx + sw * 0.25, sy, f'{sy:.1f}')
    dim(0, sy + sh * 0.3, sx, sy + sh * 0.3, f'{sx:.1f}')
    dim(wx + WELL_W + 2.5, wy + WELL_H, wx + WELL_W + 2.5, D, f'{D - wy - WELL_H:.1f}')
    ax.plot([sx + sw / 2, sx + sw / 2], [sy, wy + WELL_H], c='#F1ECE0', lw=0.6, ls=':')
    ax.set_xlim(-4, W + 4); ax.set_ylim(D + 16, -12); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(title, fontsize=15, loc='left', color=INK, pad=6)
    for i, (ok, txt) in enumerate(rules):
        ax.text(0, D + 5 + 4.2 * i, ('✓  ' if ok else '✗  ') + txt, color='#2E7D4F' if ok else '#B3261E',
                fontsize=11)
    ax.text(0, -6, notes, color='#4A443B', fontsize=10.5)


fig, axes = plt.subplots(1, 2, figsize=(17, 7.6))
# A. the screen and the well share one centre line; equal top and bottom gaps
t = (D - 22.1 - WELL_H - 3.2) / 2
face(axes[0], 'A. One centre line (keeps the 1.9" screen)', (WELL_CX - 21.05, t, 42.1, 22.1),
     (WELL_CX - WELL_W / 2, D - t - WELL_H), 30,
     'Screen and well stacked on one centre line.',
     [(True, 'well centred under the screen'), (True, 'gap above screen = gap below well'),
      (False, f'left gap {WELL_CX - 21.05:.1f} mm, top gap {t:.1f} mm (not equal)'),
      (True, 'Limit rocker centred under the switch')])
# B. a wide bar screen meets every rule
m = WELL_CX - 55.2 / 2
face(axes[1], 'B. Every rule met (a wider, shorter bar screen)', (m, m, 55.2, 14.8),
     (WELL_CX - WELL_W / 2, D - m - WELL_H), 24,
     '2.25" 284 x 76 bar screen; the switch guard narrows to 24 mm.',
     [(True, 'well centred under the screen'), (True, 'gap above screen = gap below well'),
      (True, f'left gap = top gap = {m:.1f} mm'), (True, 'Limit rocker centred under the switch')])
fig.patch.set_facecolor(BG)
plt.tight_layout()
fig.savefig(os.path.join(HERE, '1-face-options.png'), dpi=120, facecolor=BG)


# 2. the screen's corners: the bezel's G2 radius, matched by the UI
def corners():
    sys.path.insert(0, os.path.join(SB, 'ui'))
    os.environ.setdefault('SB_FONTS', os.path.join(SB, 'brand', 'fonts'))
    import screens as S
    from PIL import Image, ImageDraw
    ui = S.s06_live(0.3).im                                   # 320 x 170 at x4
    px_per_mm = S.PW / 42.7
    r_px = 3.0 * px_per_mm * S.SCALE
    Wp, Hp = ui.size
    mask = Image.new('L', (Wp, Hp), 0)
    ImageDraw.Draw(mask).polygon(g2_rect(0, 0, Wp, Hp, r_px), fill=255)
    out = Image.new('RGB', (Wp + 240, Hp + 240), (42, 38, 33))     # the case face round it
    out.paste(ui, (120, 120), mask)
    d = ImageDraw.Draw(out)
    d.polygon([(x + 120, y + 120) for x, y in g2_rect(0, 0, Wp, Hp, r_px)], outline=(227, 93, 0), width=2)
    out.save(os.path.join(HERE, '2-screen-corners.png'))


corners()
