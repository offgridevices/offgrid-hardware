"""Why a light box rocks when you flick its switch, and what fixes it.
python3 forces.py -> 1-why-it-rocks.png"""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, Circle

HERE = os.path.dirname(os.path.abspath(__file__))
BG, INK, EMB, OK, BAD = '#E9E4D8', '#1B1813', '#E35D00', '#2E7D4F', '#B3261E'


def box(ax, H, plate=False, feet=False):
    ax.add_patch(FancyBboxPatch((0, 0.8 if feet else 0), 58, H, boxstyle='round,pad=0,rounding_size=4',
                                fc='#2A2621', ec=INK))
    z0 = 0.8 if feet else 0
    if plate:
        ax.add_patch(Rectangle((1.5, z0), 55, 1.6, fc='#9AA3A8', ec='#6E777C'))
    if feet:
        for x in (3, 49):
            ax.add_patch(Rectangle((x, 0), 6, 0.8, fc='#3D3A35', ec=INK))
    # toggle: bushing + lever at board y 19.5 (face 22.5) seen from the side
    tx = 22.5
    top = H + z0
    ax.add_patch(Rectangle((tx - 3, top), 6, 3.4, fc='#B8BCC0', ec='#7C8186'))
    ax.plot([tx, tx - 3.5], [top + 3.4, top + 11.5], c='#C9CDD1', lw=5, solid_capstyle='round')
    ax.add_patch(Circle((tx - 3.5, top + 11.5), 1.6, fc='#C9CDD1', ec='#7C8186'))
    return top


fig, axes = plt.subplots(1, 3, figsize=(18, 6.2))
for ax in axes:
    ax.set_facecolor(BG); ax.set_xlim(-14, 74); ax.set_ylim(-14, 40); ax.set_aspect('equal'); ax.axis('off')
    ax.plot([-12, 72], [0, 0], c='#B5AD9D', lw=2)

# 1. today: finger pushes the lever, nothing pushes back but the box's own weight
ax = axes[0]
top = box(ax, 18)
ax.annotate('', xy=(13.5, top + 11.5), xytext=(1, top + 11.5), arrowprops=dict(arrowstyle='-|>', color=BAD, lw=3))
ax.text(-1, top + 13.5, 'finger\n2-3 N', color=BAD, fontsize=12, ha='center')
ax.annotate('', xy=(29, -4), xytext=(29, 6), arrowprops=dict(arrowstyle='-|>', color=INK, lw=2))
ax.text(31, -6, 'weight ~1.2 N\n(about 120 g)', fontsize=11)
ax.add_patch(Circle((58, 0), 1.2, fc=BAD, ec='none'))
ax.text(58, -8.5, 'tips over\nthis edge', color=BAD, fontsize=11, ha='center')
ax.set_title('Today: the push is stronger than the box is heavy', fontsize=14, loc='left', color=INK)
ax.text(-12, -13, 'Finger force x lever height > weight x half the depth:\nthe box slides or rocks back.',
        fontsize=11, color='#4A443B')

# 2. heavier + grippier: a steel base plate and silicone feet
ax = axes[1]
top = box(ax, 16, plate=True, feet=True)
ax.annotate('', xy=(13.5, top + 11.5), xytext=(1, top + 11.5), arrowprops=dict(arrowstyle='-|>', color=EMB, lw=3))
ax.text(-1, top + 13.5, 'finger\n2-3 N', color=EMB, fontsize=12, ha='center')
ax.annotate('', xy=(29, -4), xytext=(29, 7), arrowprops=dict(arrowstyle='-|>', color=INK, lw=3.2))
ax.text(31, -6, 'weight ~2 N\n(steel base plate)', fontsize=11)
ax.text(30, 3.2, 'steel plate', fontsize=9, color='#E9E4D8', ha='center')
ax.set_title('Heavier, lower, grippier', fontsize=14, loc='left', color=INK)
ax.text(-12, -13, 'A 1.5 mm steel floor (+80 g) and silicone feet:\nholds against a normal flick, still pocketable.',
        fontsize=11, color='#4A443B')

# 3. pinch: thumb on the front edge, finger on the lever; the forces cancel in the hand
ax = axes[2]
top = box(ax, 16, plate=True, feet=True)
ax.annotate('', xy=(13.5, top + 11.5), xytext=(1, top + 11.5), arrowprops=dict(arrowstyle='-|>', color=OK, lw=3))
ax.text(-1, top + 13.5, 'finger', color=OK, fontsize=12, ha='center')
ax.annotate('', xy=(58.6, 9), xytext=(70, 9), arrowprops=dict(arrowstyle='-|>', color=OK, lw=3))
ax.text(70, 11.5, 'thumb', color=OK, fontsize=12, ha='center')
ax.add_patch(Rectangle((55.5, 6), 3, 6, fc='#4A443B', ec='none'))
ax.text(57, 3.0, 'thumb rest', fontsize=9, ha='center', color='#E9E4D8')
ax.set_title('Pinch: the hand holds itself', fontsize=14, loc='left', color=INK)
ax.text(-12, -13, 'Thumb on a rest in the front edge, finger on the lever:\nthe two pushes cancel, the desk feels nothing. One hand.',
        fontsize=11, color='#4A443B')
for a in axes:
    a.text(-12, 36, 'back', fontsize=10, color='#8A8273')
    a.text(72, 36, 'front (you)', fontsize=10, color='#8A8273', ha='right')
fig.patch.set_facecolor(BG)
plt.tight_layout()
fig.savefig(os.path.join(HERE, '1-why-it-rocks.png'), dpi=110, facecolor=BG)
