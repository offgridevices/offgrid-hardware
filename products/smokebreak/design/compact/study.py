"""Compact SmokeBreak: the perfectionist face with the 2.25" bar screen,
smaller and thinner.  python3 study.py -> 1-compact-face.png, 2-height.png, 3-grip.png"""
import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, Rectangle, FancyBboxPatch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'face'))
from layout import g2_rect                                   # noqa: E402

BG, INK, BODY, WIN, WELL, EMB, OK = '#E9E4D8', '#1B1813', '#2A2621', '#0B0A08', '#14120F', '#E35D00', '#2E7D4F'

# ---- the compact face (mm, from the left / back edges)
M = 6.0                                   # the one margin: left, top, under the well, under the rocker
SW, SH = 55.3, 14.8                       # 2.25" 76 x 284 IPS active area (ST7789P3)
WELL_W, WELL_H = 36.7, 22.7
GW, GL = 24.0, 30.0                       # switch guard
GAP = 6.0
W = M + SW + GAP + GW + M
TX, TY = M + SW + GAP + GW / 2, M + 12.0
ROCK_W, ROCK_H = 24.0, 8.0
ROCK_Y = M + GL + 4.0
D = ROCK_Y + ROCK_H + M
WELL_X, WELL_Y = M + SW / 2 - WELL_W / 2, D - M - WELL_H


def draw_face(ax, W_, D_, title, compact=True, ghost=None):
    ax.set_facecolor(BG)
    if ghost:
        ax.add_patch(Polygon(g2_rect(0, 0, *ghost, 9), fill=False, ec='#9C9484', lw=1.3, ls='--'))
        ax.text(ghost[0] - 1, ghost[1] + 2.5, f'today {ghost[0]:g} x {ghost[1]:g}', ha='right', color='#8A8273', fontsize=10)
    ax.add_patch(Polygon(g2_rect(0, 0, W_, D_, 8), fc=BODY, ec=INK))
    ax.add_patch(Polygon(g2_rect(M, M, SW, SH, 2.2), fc=WIN, ec='#3A352E'))
    ax.text(M + SW / 2, M + SH / 2, 'LIVE   0.42 A   4S 16.8 V', color='#7CC88F', ha='center', va='center', fontsize=10,
            family='monospace')
    ax.add_patch(Polygon(g2_rect(WELL_X, WELL_Y, WELL_W, WELL_H, 2.5), fc=WELL, ec='#3A352E'))
    for i, n in enumerate((3, 4, 5, 6, 7)):
        px = WELL_X + 1.2 + 2.875 + 7.1 * i
        L = 2.5 * (n - 1) + 4.9
        ax.add_patch(Polygon(g2_rect(px - 2.875, WELL_Y + WELL_H - 1.6 - L, 5.75, L, 0.6), fc='#EDEAE2', ec='none'))
        ax.text(px, D_ - M / 2, f'{n - 1}S', color='#F1ECE0', ha='center', va='center', fontsize=8, fontweight='bold')
    ax.add_patch(Circle((TX, TY), 10.0, fill=False, ec='#7CC88F', lw=2.2))
    ax.add_patch(Circle((TX, TY), 3.0, fc='#B8BCC0', ec='none'))
    ax.add_patch(Polygon(g2_rect(TX - GW / 2, M, GW, GL, 2), fill=False, ec=EMB, lw=1.4, ls='--'))
    ax.add_patch(Polygon(g2_rect(TX - ROCK_W / 2, ROCK_Y, ROCK_W, ROCK_H, 2.5), fc='#B9BDC1', ec='none'))
    ax.text(TX - 6, ROCK_Y + 4, '−', ha='center', va='center', fontsize=11, color=INK)
    ax.text(TX + 6, ROCK_Y + 4, '+', ha='center', va='center', fontsize=11, color=INK)
    ax.text(TX, D_ - M / 2, 'LIMIT', color='#F1ECE0', ha='center', va='center', fontsize=8, fontweight='bold')

    def dim(x0, y0, x1, y1, label, col=EMB):
        ax.annotate('', xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle='<->', color=col, lw=1.1,
                                                                       shrinkA=0, shrinkB=0))
        ax.text((x0 + x1) / 2, (y0 + y1) / 2, label, color=col, fontsize=8.5, ha='center', va='center',
                bbox=dict(fc=BODY, ec='none', pad=0.5))
    dim(M + 10, 0, M + 10, M, f'{M:g}')
    dim(0, M + SH / 2, M, M + SH / 2, f'{M:g}')
    dim(WELL_X + WELL_W + 3, WELL_Y + WELL_H, WELL_X + WELL_W + 3, D_, f'{M:g}')
    dim(TX + ROCK_W / 2 + 2.5, ROCK_Y + ROCK_H, TX + ROCK_W / 2 + 2.5, D_, f'{M:g}')
    dim(W_ - M, M + GL / 2, W_, M + GL / 2, f'{M:g}')
    ax.plot([M + SW / 2] * 2, [M, WELL_Y + WELL_H], c='#F1ECE0', lw=0.6, ls=':')
    ax.plot([TX] * 2, [M, ROCK_Y + ROCK_H], c='#F1ECE0', lw=0.6, ls=':')
    ax.set_xlim(-4, 104); ax.set_ylim(64, -10); ax.set_aspect('equal'); ax.axis('off')
    ax.set_title(title, fontsize=15, loc='left', color=INK)


fig, ax = plt.subplots(figsize=(11, 7.4))
draw_face(ax, W, D, f'Compact: {W:.0f} x {D:.0f} x 15 mm  (today 100 x 58 x 18)', ghost=(100, 58))
ax.text(0, 63, 'One 6 mm margin everywhere.  Screen and well share a centre line; switch and rocker share another.',
        fontsize=11, color='#4A443B')
fig.patch.set_facecolor(BG)
plt.tight_layout()
fig.savefig(os.path.join(HERE, '1-compact-face.png'), dpi=130, facecolor=BG)
print('face', round(W, 1), round(D, 1))


# ---- the height stack, today vs compact (side section through the battery end)
def stack():
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.4))
    for ax, H, title, pre, xt_under in ((axes[0], 18.0, 'Today: 18 mm', 'AC05 resistors 7.5 mm', True),
                                        (axes[1], 15.0, 'Compact: 15 mm', 'flat SMD resistors 4.5 mm', False)):
        ax.set_facecolor(BG)
        ax.add_patch(FancyBboxPatch((0, 0), 70, H, boxstyle='round,pad=0,rounding_size=3', fc='#2A2621', ec=INK))
        pcb = 4.3 if H == 15 else 4.5
        ax.add_patch(Rectangle((2, pcb - 1.6), 66, 1.6, fc='#2F6B3A'))
        panel = H - 1.6
        ax.add_patch(Rectangle((3, panel - (2.4 if H == 15 else 3.0)), 40, 2.4 if H == 15 else 3.0, fc='#0B0A08',
                               ec='#555'))
        ax.text(23, panel - 1.2, 'screen module', color='#9C9484', ha='center', va='center', fontsize=9)
        ax.add_patch(Rectangle((24, pcb), 16, 7.5 if H == 18 else 4.5, fc='#7A6A55', ec='#4A3F31'))
        ax.text(32, pcb + 1.6, pre, color='#F1ECE0', ha='center', fontsize=8.5)
        ax.add_patch(Rectangle((-3, pcb), 16, 8.2, fc='#E2A90F', ec='#9A7208'))
        ax.text(5, pcb + 4.1, 'XT60', ha='center', va='center', fontsize=9)
        ax.add_patch(Rectangle((52, pcb), 6, 8.9, fc='#B8BCC0', ec='#7C8186'))
        ax.text(55, pcb + 4.4, 'switch', rotation=90, ha='center', va='center', fontsize=8.5)
        ax.annotate('', xy=(-7, 0), xytext=(-7, H), arrowprops=dict(arrowstyle='<->', lw=1.4))
        ax.text(-8, H / 2, f'{H:g} mm', rotation=90, ha='right', va='center', fontsize=13)
        ax.set_title(title, fontsize=15, loc='left')
        note = ('The XT60 sits under the screen, so the\nscreen has to sit above it.' if H == 18 else
                'The XT60 moves out from under the screen,\nthe resistors go flat: 3 mm thinner.')
        ax.text(0, -4.5, note, fontsize=11, color='#4A443B', va='top')
        ax.set_xlim(-16, 74); ax.set_ylim(-12, 24); ax.set_aspect('equal'); ax.axis('off')
    fig.patch.set_facecolor(BG)
    plt.tight_layout()
    fig.savefig(os.path.join(HERE, '2-height.png'), dpi=120, facecolor=BG)


# ---- the grip for a flip-up (away from you) switch
def grip():
    fig, ax = plt.subplots(figsize=(9, 5.2))
    ax.set_facecolor(BG)
    H = 15.0
    ax.add_patch(FancyBboxPatch((0, 0.8), 54, H, boxstyle='round,pad=0,rounding_size=3.5', fc='#2A2621', ec=INK))
    ax.add_patch(Rectangle((-0.01, 0.8), 3.2, 3.2, fc=BG, ec='none'))          # the finger lip under the back edge
    ax.add_patch(Polygon([(0, 4.0), (3.2, 0.8), (0, 0.8)], fc=BG, ec='none'))
    for x in (5, 43):
        ax.add_patch(Rectangle((x, 0), 6, 0.8, fc='#3D3A35'))
    tx = 18.0
    ax.add_patch(Rectangle((tx - 3, H + 0.8), 6, 3.4, fc='#B8BCC0'))
    ax.plot([tx, tx + 3.5], [H + 4.2, H + 12.0], c='#C9CDD1', lw=5, solid_capstyle='round')
    ax.annotate('', xy=(tx - 4, H + 12.5), xytext=(tx + 9, H + 12.5),
                arrowprops=dict(arrowstyle='-|>', color=OK, lw=3))
    ax.text(tx + 10, H + 13.6, 'thumb flips it up (away)', color=OK, fontsize=11)
    ax.annotate('', xy=(5.5, 2.4), xytext=(-8, 2.4), arrowprops=dict(arrowstyle='-|>', color=OK, lw=3))
    ax.text(-9, 5.4, 'fingertips\nhook the lip', color=OK, fontsize=11, ha='center')
    ax.text(-12, 34, 'back', color='#8A8273', fontsize=10)
    ax.text(62, 34, 'front (you)', color='#8A8273', fontsize=10, ha='right')
    ax.text(-12, -6, 'Thumb pushes the switch away, fingertips pull the back lip toward you:\n'
            'the two cancel in the hand, the box never moves. Lifting the guard needs\nonly a light touch (a weak magnet holds it shut).',
            fontsize=11, color='#4A443B', va='top')
    ax.set_title('One hand, flip up', fontsize=15, loc='left')
    ax.set_xlim(-14, 64); ax.set_ylim(-16, 36); ax.set_aspect('equal'); ax.axis('off')
    fig.patch.set_facecolor(BG)
    plt.tight_layout()
    fig.savefig(os.path.join(HERE, '3-grip.png'), dpi=120, facecolor=BG)


stack()
grip()
