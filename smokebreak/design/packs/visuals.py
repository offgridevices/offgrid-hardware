"""Visuals for three questions: the Limit rocker, battery packs remembered
by number, and a thinner case.  python3 visuals.py -> *.png here."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DESIGN = os.path.dirname(HERE)                        # smokebreak/design
V1 = os.path.join(os.path.dirname(DESIGN), 'v1')       # smokebreak/v1
os.environ.setdefault('SB_FONTS', os.path.join(V1, 'fonts'))
sys.path.insert(0, os.path.join(V1, 'ui'))
import screens as S                              # noqa: E402
from PIL import Image, ImageDraw, ImageFont      # noqa: E402

FONT = os.path.join(V1, 'fonts', 'InstrumentSans-VariableFont.ttf')


def f(px):
    return ImageFont.truetype(FONT, px)


# 1. the rocker, pointed out on the product
def rocker():
    im = Image.open(os.path.join(DESIGN, 'arm', 'top.png')).convert('RGB')
    d = ImageDraw.Draw(im)
    # rocker paddle in top.png (1600 x 1000): about x 655-875, y 685-745
    d.rounded_rectangle([640, 672, 890, 758], 18, outline=(255, 106, 0), width=7)
    d.line([765, 758, 765, 860], fill=(255, 106, 0), width=6)
    d.text((765, 872), 'The Limit rocker: one paddle, a switch under each end', font=f(40), fill=(27, 24, 19),
           anchor='ma')
    d.text((765, 922), 'press  −  or  +  to set how much current the drone may draw', font=f(32),
           fill=(80, 74, 66), anchor='ma')
    im.save(os.path.join(HERE, '1-limit-rocker.png'))


# 2. packs remembered by number
def pack_screens():
    a = S.Canvas()
    a.status(22, 22, 8, S.BLUE, fill=True)
    a.text(40, 11, 'New pack', 15, S.BLUE, weight=600)
    a.text(14, 40, 'Pack 12', 44, S.BONE, weight=600)
    a.text(14, 98, '4S   16.42 V   cells within 0.01 V', 11, S.BONE, 'mono')
    a.text(14, 122, 'Write 12 on it with a marker.', 12, S.BONE)
    a.text(14, 146, '+ yes, new      − no, it is an old one', 11, S.DIM)
    b = S.Canvas()
    b.status(22, 22, 8, S.GREEN, fill=True)
    b.text(40, 11, 'Pack 7?', 15, S.GREEN, weight=600)
    b.text(PW_ := S.PW - 14, 13, '+ yes   − other', 10, S.DIM, anchor='ra')
    b.text(14, 38, '4S  16.61 V', 30, S.BONE, 'mono')
    b.text(14, 80, 'Seen 23 times, first on 14 Mar', 11, S.BONE)
    b.text(14, 100, 'Resistance 9 mΩ per cell, up 18 % since new', 11, S.BONE)
    b.text(14, 120, 'Cells balanced (0.01 V apart)', 11, S.GREEN)
    b.text(14, 146, 'Cell 3 is the weakest, as last time', 11, S.DIM)
    gap, pad = 60, 60
    W = 2 * S.PW * S.SCALE + gap + 2 * pad
    H = S.PH * S.SCALE + 2 * pad + 120
    im = Image.new('RGB', (W, H), (233, 228, 216))
    im.paste(a.im, (pad, pad))
    im.paste(b.im, (pad + S.PW * S.SCALE + gap, pad))
    d = ImageDraw.Draw(im)
    y = pad + S.PH * S.SCALE + 30
    d.text((pad, y), 'First time: the box gives the pack a number', font=f(40), fill=(27, 24, 19))
    d.text((pad + S.PW * S.SCALE + gap, y), 'Next time: it guesses which pack, you confirm', font=f(40),
           fill=(27, 24, 19))
    im.save(os.path.join(HERE, '2-pack-screens.png'))


# 3. side cross-section: now vs thinner, to scale
def section():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch, Rectangle

    fig, axes = plt.subplots(1, 2, figsize=(16, 5.6))
    for ax, H, title, well, note in (
            (axes[0], 18.0, 'Now: 18 mm tall', 18.0 - 11.5, 'the plug sits 6.5 mm down in the well'),
            (axes[1], 15.4, 'Thinner: about 15.5 mm', 15.4 - 11.5, 'the plug sits 4 mm down: easier to grab')):
        bg = '#E9E4D8'
        ax.set_facecolor(bg)
        pcb_top = 4.5
        # case shell (side view, battery end on the left), well cut in the top
        x0, x1 = 0, 60
        ax.add_patch(FancyBboxPatch((x0, 0), x1 - x0, H, boxstyle='round,pad=0,rounding_size=3',
                                    fc='#2A2621', ec='#1B1813'))
        wx0, wx1 = 15, 51
        ax.add_patch(Rectangle((wx0, pcb_top + 7.0), wx1 - wx0, H - (pcb_top + 7.0) + 0.2, fc=bg, ec='none'))
        # board
        ax.add_patch(Rectangle((3, pcb_top - 1.6), 54, 1.6, fc='#2F6B3A', ec='none'))
        # XT60 on the end wall, its mouth outside
        ax.add_patch(Rectangle((-3, pcb_top), 16, 8.2, fc='#E2A90F', ec='#9A7208'))
        # balance socket and a plug in it, wires going up and out
        ax.add_patch(Rectangle((wx0 + 9, pcb_top), 6, 7.0, fc='#EDEAE2', ec='#9C978C'))
        ax.add_patch(Rectangle((wx0 + 9.4, pcb_top + 3.0), 5.2, 7.5, fc='#F4F1E8', ec='#9C978C'))
        for dx, c in ((0.9, '#C62828'), (2.6, '#1B1813'), (4.3, '#C62828')):
            ax.plot([wx0 + 9.4 + dx, wx0 + 9.4 + dx, wx0 - 6], [pcb_top + 10.5, H + 3.0, H + 9.0], c=c, lw=2.2)
        ax.annotate('', xy=(wx1 - 3.0, H), xytext=(wx1 - 3.0, pcb_top + 7.0),
                    arrowprops=dict(arrowstyle='<->', color='#E35D00', lw=2))
        ax.text(wx1 - 4.0, (H + pcb_top + 7) / 2, f'{well:.1f} mm deep', color='#E35D00', va='center', ha='right', fontsize=13)
        ax.annotate('', xy=(-6, 0), xytext=(-6, H), arrowprops=dict(arrowstyle='<->', color='#1B1813', lw=1.5))
        ax.text(-7, H / 2, f'{H:g} mm', rotation=90, va='center', ha='right', fontsize=13)
        ax.text(5, -3.2, 'XT60', fontsize=11, ha='center')
        ax.text(wx0 + 12, -3.2, 'balance socket + plug', fontsize=11, ha='center')
        ax.set_title(title, fontsize=17, loc='left', pad=12)
        ax.text(0, -6.6, note, fontsize=12, color='#4A443B')
        ax.set_xlim(-14, 66)
        ax.set_ylim(-8, 30)
        ax.set_aspect('equal')
        ax.axis('off')
    fig.patch.set_facecolor('#E9E4D8')
    plt.tight_layout()
    fig.savefig(os.path.join(HERE, '3-thinner-case.png'), dpi=110, facecolor=fig.get_facecolor())


if __name__ == '__main__':
    rocker()
    pack_screens()
    section()
