"""Labels and title over rendered frames, and the MP4 (make_video.py's last
step; runs in video/.venv).

    python overlay.py SPEC.json ANCHORS.json FRAMES OUT_DIR [OUT.mp4]

The open board runs left to right across the frame, so the layer labels
alternate above and below it, each on a thin leader to the layer's upper or
lower edge (scene.py's anchors, per frame).  They fade in left to right once
the board is open and out before it closes; the title fades in over the
closing shot.
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
hold = (TL['open_end'] + TL['close']) // 2
# left to right as the open board shows them; alternate rows
order = sorted([n for n in names if n in LAB], key=lambda n: anch['frames'][hold][names.index(n)][0])
row = {n: ('above' if i % 2 == 0 else 'below') for i, n in enumerate(order)}
os.makedirs(OUTDIR, exist_ok=True)
files = sorted(x for x in os.listdir(FRAMES) if x.endswith('.png') and os.path.getsize(os.path.join(FRAMES, x)))
for fn in files:
    f = int(fn[:4])
    img = Image.open(os.path.join(FRAMES, fn)).convert('RGBA')
    W, H = img.size
    k = H / 720.0
    sx, sy = W / AW, H / AH
    lay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(lay)
    ft, fd = font(round(17 * k), 'Medium'), font(round(13.5 * k), 'Regular')
    lh_t, lh_d = round(22 * k), round(17 * k)
    width = 200 * k                           # detail lines wrap at this
    margin, space = 24 * k, 16 * k
    items = []
    for i, n in enumerate(order):
        a = (ramp(f, OV['in'] + i * OV['step'], OV['in'] + i * OV['step'] + OV['fade'])
             * (1 - ramp(f, OV['out'], OV['out'] + OV['fade_out'])))
        x1, y1, x2, y2, _ = anch['frames'][f][names.index(n)]
        up = min((y1, x1), (y2, x2))              # the edge nearer the top of the frame
        dn = max((y1, x1), (y2, x2))
        y, x = up if row[n] == 'above' else dn
        title, detail = LAB[n]
        dl = wrap(d, detail, fd, width) if detail else []
        tw = max([d.textlength(title, font=ft)] + [d.textlength(t, font=fd) for t in dl])
        items.append(dict(n=n, a=a, x=x * sx, y=y * sy, title=title, dl=dl, w=tw, cx=x * sx))
    # labels in a row push each other apart, and stay in the frame
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
            d.line([(x, y - 5 * k), (cx, yb + 8 * k)], fill=col((205, 205, 210)), width=max(1, round(k)))
        else:
            ty = OV['below'] * H                      # the block's top
            d.line([(x, y + 5 * k), (cx, ty - 8 * k)], fill=col((205, 205, 210)), width=max(1, round(k)))
        rr = 2.4 * k
        d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col((235, 235, 238)))
        d.text((cx, ty), it['title'], font=ft, fill=col((242, 242, 244)), anchor='ma')
        for j, t in enumerate(dl):
            d.text((cx, ty + lh_t + j * lh_d), t, font=fd, fill=col((150, 152, 158)), anchor='ma')
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
                    '-i', os.path.join(OUTDIR, '%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '17',
                    '-preset', 'slow', '-movflags', '+faststart', MP4], check=True)
    print('wrote', MP4, len(files), 'frames')
