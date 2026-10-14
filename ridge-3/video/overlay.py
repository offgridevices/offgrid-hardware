"""Labels and title over rendered frames, and the MP4 (make_video.py's last
step; runs in video/.venv).

    python overlay.py SPEC.json ANCHORS.json FRAMES OUT_DIR [OUT.mp4]

While the camera stops on each unit of the tour, the unit in view is named
in a lower third (a counter, its name, what it is) over a soft shade.  When
it pulls back to the whole, every unit's label comes in, left to right,
alternating above and below the board, each on a leader to its layer's
upper or lower edge (a unit of several layers, like the copper, gets a
bracket across them, parallel to the line of their edges and clear of every
layer); labels in a row push each other apart.  They go before the board
closes, and the title comes in over the closing shot.  Every line and text
block is checked against every layer's outline, and any overlap is reported.
Anchors (per frame, from scene.py): the midpoints of each layer group's four
edges on screen, how open it is, how much the tour is on it, and the corners
of its box.  The units (spec 'units') say which groups each label covers.
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


def hull(pts):
    """The convex hull of points, counter-clockwise."""
    pts = sorted(set(pts))
    if len(pts) < 3:
        return pts
    turn = lambda o, a, b: (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and turn(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and turn(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def apart(P, Q):
    """Whether convex shapes P and Q (point lists; two points make a line)
    are apart: some edge's normal separates them."""
    for poly in (P, Q):
        for i in range(len(poly)):
            (x1, y1), (x2, y2) = poly[i], poly[(i + 1) % len(poly)]
            nx, ny = y1 - y2, x2 - x1
            if nx == ny == 0:
                continue
            p = [nx * x + ny * y for x, y in P]
            q = [nx * x + ny * y for x, y in Q]
            if max(p) < min(q) or max(q) < min(p):
                return True
    return False


def bar_across(feet, outlines, above, clear):
    """A bracket's bar across the layers whose near edges are at `feet`:
    parallel to the line through them (least squares), and `clear` above (or
    below) every outline over its span.  Returns y = c + b x and the span."""
    xs, ys = [p[0] for p in feet], [p[1] for p in feet]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    b = sum((x - mx) * (y - my) for x, y in feet) / sum((x - mx) ** 2 for x in xs)
    x0, x1 = min(xs), max(xs)
    reach = []                                 # the outlines' edges, clipped to the span
    for P in outlines:
        for (ax, ay), (bx, by) in zip(P, P[1:] + P[:1]):
            if max(ax, bx) < x0 or min(ax, bx) > x1:
                continue
            for x in (max(min(ax, bx), x0), min(max(ax, bx), x1)):
                y = ay if bx == ax else ay + (by - ay) * (x - ax) / (bx - ax)
                reach.append(y - b * x)
    c = min(reach) - clear if above else max(reach) + clear
    return c, b, x0, x1


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
# each labelled unit: the indices of its groups in the anchors
UNITS = {k: [names.index(g) for g in v if g in names] for k, v in spec['units'].items() if k in LAB}
UNITS = {k: v for k, v in UNITS.items() if v}
STOPS = [k for k in spec['tour'] if k in UNITS]
overlaps = {}                                  # (what, layer) -> frames where a line or text crosses it


def check(what, shapes, outlines, f, skip=()):
    """Note any layer outline that one of `shapes` crosses (but those in skip)."""
    for gi, P in enumerate(outlines):
        if gi not in skip and len(P) > 2 and any(not apart(sh, P) for sh in shapes):
            overlaps.setdefault((what, names[gi]), []).append(f)


def box(d, xy, text, fnt, anchor):
    x0, y0, x1, y1 = d.textbbox(xy, text, font=fnt, anchor=anchor)
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
hold = (TL['tour_end'] + TL['close']) // 2
# left to right as the open board shows them; alternate rows
order = sorted(UNITS, key=lambda k: sum(anch['frames'][hold][i][0] for i in UNITS[k]) / len(UNITS[k]))
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
    outline = [hull([(a[i] * sx, a[i + 1] * sy) for i in range(10, 26, 2)]) for a in A]

    # the whole: every label, in two rows
    ft, fd = font(round(17 * k), 'Medium'), font(round(13.5 * k), 'Regular')
    lh_t, lh_d = round(22 * k), round(17 * k)
    width, margin, space = 200 * k, 24 * k, 16 * k
    items = []
    for i, n in enumerate(order):
        a = (ramp(f, OV['in'] + i * OV['step'], OV['in'] + i * OV['step'] + OV['fade'])
             * (1 - ramp(f, OV['out'], OV['out'] + OV['fade_out'])))
        feet = []                                  # (y, x): each layer's edge nearer the label
        for gi in UNITS[n]:
            x1, y1, x2, y2 = A[gi][:4]
            e = min((y1, x1), (y2, x2)) if row[n] == 'above' else max((y1, x1), (y2, x2))
            feet.append((e[0] * sy, e[1] * sx))
        if len(feet) == 1:
            (y, x), bracket = feet[0], None
        else:                                      # a bar across the layers, clear of them all
            c, b, x0, x1 = bar_across([(p[1], p[0]) for p in feet], outline, row[n] == 'above', 10 * k)
            x = (x0 + x1) / 2
            y = c + b * x
            bracket = dict(c=c, b=b, x0=x0, x1=x1, ticks=[p[1] for p in feet])
        title, detail = LAB[n]
        dl = wrap(d, detail, fd, width) if detail else []
        tw = max([d.textlength(title, font=ft)] + [d.textlength(t, font=fd) for t in dl])
        items.append(dict(n=n, a=a, x=x, y=y, bracket=bracket, title=title, dl=dl, w=tw, cx=x))
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
        x, y, cx, dl, br = it['x'], it['y'], it['cx'], it['dl'], it['bracket']
        block = lh_t + lh_d * len(dl)
        above = row[it['n']] == 'above'
        clear = 0 if br else 5 * k                    # the leader stops short of a dot
        if above:
            yb = OV['above'] * H                      # the block's bottom
            ty = yb - block
            lines = [[(x, y - clear), (cx, yb + 8 * k)]]
        else:
            ty = OV['below'] * H                      # the block's top
            lines = [[(x, y + clear), (cx, ty - 8 * k)]]
        if br:                                        # the bar, a tick toward each layer
            at = lambda bx: (bx, br['c'] + br['b'] * bx)
            lines.append([at(br['x0']), at(br['x1'])])
            lines += [[at(bx), (bx, at(bx)[1] + (6 if above else -6) * k)] for bx in br['ticks']]
        for ln in lines:
            d.line(ln, fill=col((205, 205, 210)), width=line_w)
        # nothing drawn may cross a layer (but the leader its own, where it starts)
        text = [(cx - it['w'] / 2, ty), (cx + it['w'] / 2, ty), (cx + it['w'] / 2, ty + block),
                (cx - it['w'] / 2, ty + block)]
        if a > 0.05:
            if br:
                check('label ' + it['n'], lines + [text], outline, f)
            else:                                     # its leader starts on its own layer
                check('label ' + it['n'], lines, outline, f, skip=UNITS[it['n']])
                check('label ' + it['n'], [text], outline, f)
        if not br:
            rr = 2.4 * k
            d.ellipse([x - rr, y - rr, x + rr, y + rr], fill=col((235, 235, 238)))
        d.text((cx, ty), it['title'], font=ft, fill=col((242, 242, 244)), anchor='ma')
        for j, t in enumerate(dl):
            d.text((cx, ty + lh_t + j * lh_d), t, font=fd, fill=col((150, 152, 158)), anchor='ma')

    # the tour: the unit in view, named in a lower third over a soft shade
    shade = ramp(f, TL['tour'][0] - 2 * TL['tour_fade'], TL['tour'][0]) * \
        (1 - ramp(f, TL['tour'][-1] + TL['dwell'], TL['tour'][-1] + TL['dwell'] + 2 * TL['tour_fade']))
    if shade > 0:
        top = int(0.66 * H)
        for yy in range(top, H):
            d.line([(0, yy), (W, yy)], fill=(0, 0, 0, round(150 * shade * ((yy - top) / (H - top)) ** 1.6)))
    Fc, Ft, Fd = font(round(13 * k), 'Medium'), font(round(32 * k), 'Medium'), font(round(18 * k), 'Regular')
    for i, n in enumerate(STOPS):
        a = A[UNITS[n][0]][9]
        if a <= 0:
            continue
        col = lambda c: (*c, round(255 * a))
        x0, y0 = OV['tour_at'][0] * W, OV['tour_at'][1] * H
        title, detail = LAB[n]
        texts = [((x0, y0), '%02d / %02d' % (i + 1, len(STOPS)), Fc, (140, 142, 148)),
                 ((x0, y0 + 40 * k), title, Ft, (245, 245, 247))]
        if detail:
            texts.append(((x0 + 1 * k, y0 + 66 * k), detail, Fd, (168, 170, 176)))
        for xy, t, fnt, c in texts:
            d.text(xy, t, font=fnt, fill=col(c), anchor='ls')
        if a > 0.05:
            check('caption ' + n, [box(d, xy, t, fnt, 'ls') for xy, t, fnt, c in texts], outline, f)

    a = ramp(f, OV['title_in'], OV['title_in'] + OV['title_fade'])
    if a > 0:
        col = lambda c: (*c, round(255 * a))
        x0, y0 = OV['title_at'][0] * W, OV['title_at'][1] * H
        texts = [((x0, y0), spec['title'][0], font(round(46 * k), 'SemiBold'), (245, 245, 247)),
                 ((x0 + 2 * k, y0 + 34 * k), spec['title'][1], font(round(20 * k), 'Regular'), (165, 167, 172))]
        for xy, t, fnt, c in texts:
            d.text(xy, t, font=fnt, fill=col(c), anchor='ls')
        if a > 0.05:
            check('title', [box(d, xy, t, fnt, 'ls') for xy, t, fnt, c in texts], outline, f)
    Image.alpha_composite(img, lay).convert('RGB').save(os.path.join(OUTDIR, fn))
for (n, g), fr in sorted(overlaps.items()):
    print('overlap: the %s crosses %s in %d frames (%d-%d)' % (n, g, len(fr), fr[0], fr[-1]))
if MP4:
    subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-loglevel', 'error', '-framerate', str(spec['fps']),
                    '-i', os.path.join(OUTDIR, '%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '16',
                    '-preset', 'slow', '-movflags', '+faststart', MP4], check=True)
    print('wrote', MP4, len(files), 'frames')
