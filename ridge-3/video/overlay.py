"""Labels and title over rendered frames, and the MP4 (make_video.py's last
step; runs in video/.venv).

    python overlay.py SPEC.json ANCHORS.json FRAMES OUT_DIR [OUT.mp4]

While the camera goes from layer to layer, the layer in view is named in a
lower third (a counter, its name, what it is) over a soft shade.  When it pulls back to the whole,
every label comes in, left to right, alternating above and below the board,
each on a leader to its layer's upper or lower edge; labels in a row push
each other apart.  They go before the board closes, and the title comes in
over the closing shot.  Anchors (per frame, from scene.py): the midpoints of
each layer's four edges on screen, how open it is, how much the tour is on it.
"""
import json, os, sys, subprocess
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg

SPEC, ANCH, FRAMES, OUTDIR = sys.argv[1:5]
MP4 = sys.argv[5] if len(sys.argv) > 5 else None
spec = json.load(open(SPEC))
anch = json.load(open(ANCH))
LAB = spec['labels']                    # {group: [title, detail]}
TL = spec['timeline']
OV = spec['overlay']
fonts = {}


def font(size, weight):
    key = (size, weight)
    if key not in fonts:
        f = ImageFont.truetype(spec['font'], size)
        f.set_variation_by_name(weight)
        fonts[key] = f
    return fonts[key]


def ramp(f, a, b):
    return 0.0 if f <= a else 1.0 if f >= b else (f - a) / (b - a)


def wrap(d, text, fnt, width):
    lines, cur = [], ''
    for w in text.split():
        t = (cur + ' ' + w).strip()
        if cur and d.textlength(t, font=fnt) > width:
            lines.append(cur)
            cur = w
        else:
            cur = t
    return lines + ([cur] if cur else [])


names = anch['groups']
AW, AH = anch['size']
hold = (TL['tour_end'] + TL['close']) // 2
# left to right as the open board shows them; alternate rows
order = sorted([n for n in names if n in LAB], key=lambda n: anch['frames'][hold][names.index(n)][0])
row = {n: ('above' if i % 2 == 0 else 'below') for i, n in enumerate(order)}
os.makedirs(OUTDIR, exist_ok=True)
files = sorted(x for x in os.listdir(FRAMES) if x.endswith('.png') and os.path.getsize(os.path.join(FRAMES, x)))
for fn in files:
    f = int(os.path.splitext(fn)[0])
    img = Image.open(os.path.join(FRAMES, fn)).convert('RGBA')
    W, H = img.size
    k = H / 720.0
    sx, sy = W / AW, H / AH
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    line_w = max(1, round(k))
    A = anch['frames'][f]

    # the whole: every label, in two rows
    ft, fd = font(round(17 * k), 'Medium'), font(round(13.5 * k), 'Regular')
    lh_t, lh_d = round(22 * k), round(17 * k)
    width, margin, space = 200 * k, 24 * k, 16 * k
    items = []
    for i, n in enumerate(order):
        a = (ramp(f, OV['in'] + i * OV['step'], OV['in'] + i * OV['step'] + OV['fade'])
             * (1 - ramp(f, OV['out'], OV['out'] + OV['fade_out'])))
        x1, y1, x2, y2 = A[names.index(n)][:4]
        up = min((y1, x1), (y2, x2))              # the edge nearer the top of the frame
        dn = max((y1, x1), (y2, x2))
        y, x = up if row[n] == 'above' else dn
        title, detail = LAB[n]
        dl = wrap(d, detail, fd, width) if detail else []
        tw = max([d.textlength(title, font=ft)] + [d.textlength(t, font=fd) for t in dl])
        items.append(dict(n=n, a=a, x=x * sx, y=y * sy, title=title, dl=dl, w=tw, cx=x * sx))
    for side in ('above', 'below'):
        rowi = sorted([it for it in items if row[it['n']] == side], key=lambda it: it['x'])
        for _ in range(200):
            moved = False
            for p, q in zip(rowi, rowi[1:]):
                over = (p['cx'] + p['w'] / 2 + space) - (q['cx'] - q['w'] / 2)
                if over > 0.5:
                    p['cx'] -= over / 2
                    q['cx'] += over / 2
                    moved = True
            for it in rowi:
                it['cx'] = min(max(it['cx'], margin + it['w'] / 2), W - margin - it['w'] / 2)
            if not moved:
                break
    for it in items:
        a = it['a']
        if a <= 0:
            continue
        col = lambda c: (*c, round(255 * a))
        x, y, cx, dl = it['x'], it['y'], it['cx'], it['dl']
        block = lh_t + lh_d * len(dl)
        if row[it['n']] == 'above':
            yb = OV['above'] * H                      # the block's bottom
            ty = yb - block
            d.line([(x, y - 5 * k), (cx, yb + 8 * k)], fill=col((205, 205, 210)), width=line_w)
        else:
            ty = OV['below'] * H                      # the block's top
            d.line([(x, y + 5 * k), (cx, ty - 8 * k)], fill=col((205, 205, 210)), width=line_w)
        rr = 2.4 * k
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col((235, 235, 238)))
        d.text((cx, ty), it['title'], font=ft, fill=col((242, 242, 244)), anchor='ma')
        for j, t in enumerate(dl):
            d.text((cx, ty + lh_t + j * lh_d), t, font=fd, fill=col((150, 152, 158)), anchor='ma')

    # the tour: the layer in view, named in a lower third over a soft shade
    tour = [A[names.index(n)][9] for n in order]
    shade = ramp(f, TL['tour'][0] - 2 * TL['tour_fade'], TL['tour'][0]) * \
        (1 - ramp(f, TL['tour'][-1] + TL['dwell'], TL['tour'][-1] + TL['dwell'] + 2 * TL['tour_fade']))
    if shade > 0:
        top = int(0.66 * H)
        for yy in range(top, H):
            d.line([(0, yy), (W, yy)], fill=(0, 0, 0, round(150 * shade * ((yy - top) / (H - top)) ** 1.6)))
    Fc, Ft, Fd = font(round(13 * k), 'Medium'), font(round(32 * k), 'Medium'), font(round(18 * k), 'Regular')
    for i, n in enumerate(order):
        a = tour[i]
        if a <= 0:
            continue
        col = lambda c: (*c, round(255 * a))
        x0, y0 = OV['tour_at'][0] * W, OV['tour_at'][1] * H
        title, detail = LAB[n]
        d.text((x0, y0), '%02d / %02d' % (i + 1, len(order)), font=Fc, fill=col((140, 142, 148)), anchor='ls')
        d.text((x0, y0 + 40 * k), title, font=Ft, fill=col((245, 245, 247)), anchor='ls')
        if detail:
            d.text((x0 + 1 * k, y0 + 66 * k), detail, font=Fd, fill=col((168, 170, 176)), anchor='ls')

    a = ramp(f, OV['title_in'], OV['title_in'] + OV['title_fade'])
    if a > 0:
        col = lambda c: (*c, round(255 * a))
        x0, y0 = OV['title_at'][0] * W, OV['title_at'][1] * H
        d.text((x0, y0), spec['title'][0], font=font(round(46 * k), 'SemiBold'), fill=col((245, 245, 247)), anchor='ls')
        d.text((x0 + 2 * k, y0 + 34 * k), spec['title'][1], font=font(round(20 * k), 'Regular'),
               fill=col((165, 167, 172)), anchor='ls')
    Image.alpha_composite(img, lay).convert('RGB').save(os.path.join(OUTDIR, fn))
if MP4:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-framerate', str(spec['fps']),
                    '-i', os.path.join(OUTDIR, '%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16',
                    '-preset', 'slow', '-movflags', '+faststart', MP4], check=True)
    print('wrote', MP4, len(files), 'frames')
