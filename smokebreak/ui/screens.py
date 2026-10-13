"""SmokeBreak screen design: the Arm sequence on a 2.25" 284 x 76 IPS bar.

The panel's active area is 55.3 x 14.8 mm.  The case opening over it has G2
(curvature-continuous) corners: superellipse quadrants, n = 5, r = 2.2 mm,
about 11 px.  Content stays inside a safe area at least 4 px in from that
outline (checked by lint() on every screen), and every final frame is masked
with the same outline, black outside.

Every screen is drawn at the panel's real resolution in logical pixels and
scaled by SCALE for review, so what is drawn here is what fits the panel.

A bar is wide and short, so each screen is one or two rows (three lines of
small text at most): the status ring or dot and the state word at the left,
the big number next, secondary facts at the right.  Words are Instrument
Sans, numerals JetBrains Mono; no text is under 9 px cap height (13 px).

    python3 screens.py    # storyboard.png, bar-screens.png, arm-sequence.mp4
                          # (with beeps), frames/ and frames24/

Screens are numbered S00..S21 so feedback can point at one (S14-S21, the
battery and pack screens, are in the storyboard but not in the video
timeline).
"""
import math
import os
import shutil
import subprocess
import tempfile
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFilter, ImageFont

sys_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'brand')
import sys  # noqa: E402
sys.path.insert(0, sys_path)
import mark as brand  # noqa: E402  the one source of the Beacon Ring

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('SB_FONTS', os.path.join(os.path.dirname(HERE), 'brand', 'fonts'))

PW, PH = 284, 76           # panel, pixels (2.25" bar, 55.3 x 14.8 mm active)
SCALE = 4                  # review scale
FPS = 30

MM = PW / 55.3             # pixels per mm (5.14)
CORNER = 2.2 * MM          # the opening's G2 corner radius, px (11.3)
CORNER_N = 5.0             # its superellipse exponent
SAFE = 4                   # content keeps this far in from the opening, px

INK = (11, 10, 8)
BONE = (241, 236, 224)
DIM = (120, 114, 104)
EMBER = (255, 106, 0)
GREEN = (76, 175, 80)
RED = (229, 57, 53)
BLUE = (61, 139, 255)

FAINT = (60, 56, 50)       # checks not reached yet
BAR_BG = (40, 36, 30)      # empty part of a bar or chip

# the grid: left and right content edges, and the baselines of the three
# lines of 13 px text (A top, B middle, C bottom)
L, R = 12, PW - 12
RA, RB, RC = 21, 43.5, 66
MIN_TEXT = 13              # px; 9.4 px cap height in either face
CAP = {'sans': 0.720, 'mono': 0.730}   # cap height / size (measured)


def g2_rect(x0, y0, w, h, r, n=5.0, k=16):
    """Rounded rectangle whose corners are superellipse quadrants
    |x|^n + |y|^n = r^n: the curvature runs from zero at the straight edge
    to a maximum at 45 degrees and back, so every joint is G2.
    (Copied from design/face/layout.py.)"""
    pts = []
    corners = [(x0 + w - r, y0 + r, -90), (x0 + w - r, y0 + h - r, 0), (x0 + r, y0 + h - r, 90), (x0 + r, y0 + r, 180)]
    for cx, cy, a0 in corners:
        for i in range(k + 1):
            t = math.radians(a0 + 90 * i / k)
            c, s = math.cos(t), math.sin(t)
            pts.append((cx + r * math.copysign(abs(c) ** (2 / n), c), cy + r * math.copysign(abs(s) ** (2 / n), s)))
    return pts


@lru_cache(maxsize=None)
def opening_mask(scale=SCALE):
    """The case opening at `scale`, antialiased: 255 inside, 0 outside."""
    ss = 4
    big = Image.new('L', (PW * scale * ss, PH * scale * ss), 0)
    ImageDraw.Draw(big).polygon(g2_rect(0, 0, PW * scale * ss, PH * scale * ss, CORNER * scale * ss, CORNER_N, 64),
                                fill=255)
    return big.resize((PW * scale, PH * scale), Image.LANCZOS)


@lru_cache(maxsize=None)
def safe_mask():
    """Where content may go (at SCALE): the opening eroded by SAFE px.
    A square erosion, so it is a little stricter than SAFE at the corners."""
    m = opening_mask().point(lambda v: 255 if v >= 250 else 0)
    k = 2 * SAFE * SCALE + 1
    pad = Image.new('L', (m.size[0] + 2 * k, m.size[1] + 2 * k), 0)     # outside the panel is outside
    pad.paste(m, (k, k))
    return pad.filter(ImageFilter.MinFilter(k)).crop((k, k, k + m.size[0], k + m.size[1]))


def masked(im):
    """A final frame: the screen inside the opening, black outside."""
    out = Image.new('RGB', im.size, (0, 0, 0))
    m = opening_mask(im.size[0] // PW)
    out.paste(im, (0, 0), m)
    return out


@lru_cache(maxsize=None)
def font(kind, px, weight=500):
    path = os.path.join(FONTS, 'JetBrainsMono-VariableFont.ttf' if kind == 'mono'
                        else 'InstrumentSans-VariableFont.ttf')
    f = ImageFont.truetype(path, int(px * SCALE))
    try:
        f.set_variation_by_axes([weight] if kind == 'mono' else [weight, 100])
    except Exception:
        try:
            f.set_variation_by_axes([weight])
        except Exception:
            pass
    return f


def width(s, size, kind='sans', weight=500):
    """Advance width of `s` in panel pixels."""
    return font(kind, size, weight).getlength(s) / SCALE


def cap(size, kind='sans'):
    """Cap height in panel pixels."""
    return int(size * SCALE) * CAP[kind] / SCALE


class Canvas:
    def __init__(self, bg=INK):
        self.im = Image.new('RGB', (PW * SCALE, PH * SCALE), bg)
        self.d = ImageDraw.Draw(self.im)
        # what counts as content (text, numbers, rings, bars) is also drawn
        # here, so lint() can check it against the safe area; full-bleed
        # backgrounds, hazard stripes, rules and frames are not content
        self.ink = Image.new('L', self.im.size, 0)
        self.di = ImageDraw.Draw(self.ink)
        self.texts = []        # (box in panel px, string, size) for lint()
        self.name = ''

    def _box(self, pts):
        return [v * SCALE for v in pts]

    def text(self, x, y, s, size, colour=BONE, kind='sans', anchor='la', weight=500, record=True):
        f = font(kind, size, weight)
        xy = (x * SCALE, y * SCALE)
        self.d.text(xy, s, font=f, fill=colour, anchor=anchor)
        self.di.text(xy, s, font=f, fill=255, anchor=anchor)
        if record:
            b = self.d.textbbox(xy, s, font=f, anchor=anchor)
            self.texts.append(([v / SCALE for v in b], s, size))

    def run(self, x, y, parts, align='l'):
        """Several styled pieces on one baseline: parts are (s, size, colour,
        kind[, weight]).  align 'l' starts at x, 'r' ends at x."""
        parts = [p + (500,) if len(p) == 4 else p for p in parts]
        total = sum(width(s, size, kind, w) for s, size, _, kind, w in parts)
        x0 = x - total if align == 'r' else x
        cx = x0
        for s, size, colour, kind, w in parts:
            self.text(cx, y, s, size, colour, kind, 'ls', w, record=False)
            cx += width(s, size, kind, w)
        top = y - max(cap(size, kind) for _, size, _, kind, _ in parts)
        self.texts.append(([x0, top, cx, y], ''.join(p[0] for p in parts), min(p[1] for p in parts if p[0].strip())))
        return cx

    def rect(self, x0, y0, x1, y1, colour, width=0, r=0, decor=False):
        box = self._box([x0, y0, x1, y1])
        draws = [(self.d, colour)] + ([] if decor else [(self.di, 255)])
        for d, col in draws:
            if width:
                d.rounded_rectangle(box, r * SCALE, outline=col, width=int(width * SCALE))
            else:
                d.rounded_rectangle(box, r * SCALE, fill=col)

    def line(self, pts, colour, width=1):
        p = [(x * SCALE, y * SCALE) for x, y in pts]
        self.d.line(p, fill=colour, width=int(width * SCALE))
        self.di.line(p, fill=255, width=int(width * SCALE))

    def mark(self, cx, cy, R, colour=BONE):
        """The OffGrid mark, exactly as the brand draws it (brand/mark.py),
        ring centreline radius R, centred on its ring.  Only ever drawn
        static and alone (the start-up screen): never a status icon, never
        animated, never with anything inside it."""
        for poly in brand.polygons(brand.by_ring_radius(R, centre=(cx, cy))):
            p = [(x * SCALE, y * SCALE) for x, y in poly.exterior.coords]
            self.d.polygon(p, fill=colour)
            self.di.polygon(p, fill=255)

    def status(self, cx, cy, r, colour, frac=1.0, fill=False):
        """The status light on screen: a plain closed ring (or a dot), the
        same shape as the light round the switch.  Deliberately not the
        mark: no opening, no node."""
        box = [(cx - r) * SCALE, (cy - r) * SCALE, (cx + r) * SCALE, (cy + r) * SCALE]
        w = int(max(1.5, r * 0.18) * SCALE)
        for d, col in ((self.d, colour), (self.di, 255)):
            if fill:
                d.ellipse(box, fill=col)
            elif frac >= 1:
                d.ellipse(box, outline=col, width=w)
            elif frac > 0:
                d.arc(box, -90, -90 + 360 * frac, fill=col, width=w)

    def stripes(self, y0, y1, colour, phase=0.0):
        """Hazard chevrons across the panel, scrolling with `phase`."""
        step = 14
        off = (phase * step) % step
        for k in range(-2, PW // step + 3):
            x = k * step + off
            self.d.polygon([((x) * SCALE, y1 * SCALE), ((x + 7) * SCALE, y1 * SCALE),
                            ((x + 7 + (y1 - y0)) * SCALE, y0 * SCALE), ((x + (y1 - y0)) * SCALE, y0 * SCALE)],
                           fill=colour)

    def frame(self, colour, inset=1.5, w=2.5):
        """A border that follows the opening's own G2 outline."""
        s = SCALE
        pts = g2_rect(inset * s, inset * s, (PW - 2 * inset) * s, (PH - 2 * inset) * s,
                      (CORNER - inset) * s, CORNER_N, 32)
        self.d.line(pts + pts[:1], fill=colour, width=int(w * s), joint='curve')

    def dot_for(self, x, base, size, colour, r=5, kind='sans'):
        """A status dot in the gutter left of a line of text, centred on its caps."""
        self.status(x, base - cap(size, kind) / 2, r, colour, fill=True)

    def tag(self, s):
        """Screen number, for review only: kept off the panel (it would sit
        in the opening's corner) and shown in the storyboard's labels."""
        self.name = s

    def final(self):
        return masked(self.im)


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


def rocker(c, x, y, choices, align='r'):
    """The rocker hint: '+' and '−' in mono Bone, what each means in Dim."""
    parts = []
    for i, (key, word) in enumerate(choices):
        if i:
            parts.append(('   ', MIN_TEXT, DIM, 'sans'))
        parts += [(key, MIN_TEXT, BONE, 'mono'), (' ' + word, MIN_TEXT, DIM, 'sans')]
    return c.run(x, y, parts, align)


# ------------------------------------------------------------------ screens
# Each takes t in [0, 1] (progress through that screen) and returns a Canvas.

BATT = '16.8 V  4S'
DRONE = 'Drone 3'


def s00_startup(t):
    """Start-up: the mark alone, static, centred, Bone on black, with more
    than a quarter of its width clear on every side.  It cuts in and cuts out."""
    c = Canvas()
    R0 = 14
    x0, y0, x1, y1 = brand.by_ring_radius(R0).bounds
    c.mark(PW / 2 - (x0 + x1) / 2, PH / 2 - (y0 + y1) / 2, R0)
    c.tag('S00')
    return c


def s01_safe(t):
    c = Canvas()
    c.status(25, 38, 13, lerp(DIM, EMBER, 0.35 + 0.25 * math.sin(t * math.tau)))
    c.text(46, 36, 'SAFE', 30, BONE, 'sans', 'ls', 600)
    c.text(46, 60, 'Drone is off', 13, DIM, anchor='ls')
    c.text(R, 36, BATT, 16, BONE, 'mono', 'rs')
    c.text(R, 60, 'Lift the guard to arm', 13, EMBER, anchor='rs')
    c.tag('S01')
    return c


def s02_armed(t):
    c = Canvas()
    c.stripes(0, 6, EMBER, t * 6)
    c.stripes(PH - 6, PH, EMBER, -t * 6)
    c.rect(0, 6, PW, PH - 6, INK, decor=True)
    pulse = 0.6 + 0.4 * abs(math.sin(t * math.pi * 3))
    c.text(L, 30, 'ARMED', 26, lerp(INK, EMBER, pulse), 'sans', 'ls', 600)
    c.text(R, 30, 'Flick the switch up', 15, BONE, anchor='rs')
    c.text(R, 47, 'to check and power the drone', 13, DIM, anchor='rs')
    c.text(L, 64, BATT, 13, BONE, 'mono', 'ls')
    c.text(R, 64, DRONE + ' · 0.42 A last', 13, DIM, anchor='rs')
    c.tag('S02')
    return c


CHECKS = [('3 V probe', 'OK'), ('Short circuit', 'NONE'), ('Polarity', 'OK'),
          ('Capacitor', '1020 µF'), ('Pre-charge', '')]
STEP = 11                  # pitch of the progress squares in the header


def check_header(c, done, frac_last, active_colour=EMBER):
    """'CHECKING' and one square per check: green done, blinking active."""
    c.text(L, RA, 'CHECKING', 13, EMBER, 'mono', 'ls', 600)
    x0 = L + width('CHECKING', 13, 'mono', 600) + 12
    blink = int(frac_last * 8) % 2 == 0
    ym = RA - cap(13, 'mono') / 2
    for i in range(len(CHECKS)):
        col = GREEN if i < done else (active_colour if blink else BAR_BG) if i == done else FAINT
        c.rect(x0 + i * STEP, ym - 3.5, x0 + i * STEP + 7, ym + 3.5, col, r=1)


def check_row(c, y, i, state, frac=0.0, active_colour=EMBER, dots=True):
    """One check on a line: square, name, result (or progress dots)."""
    name, val = CHECKS[i]
    ym = y - cap(15) / 2
    if state == 'done':
        c.rect(L, ym - 3.5, L + 7, ym + 3.5, GREEN, r=1)
        c.text(26, y, name, 15, BONE, anchor='ls')
        c.text(R, y, val, 14, GREEN, 'mono', 'rs')
    elif state == 'active':
        blink = int(frac * 8) % 2 == 0
        if blink:
            c.rect(L, ym - 3.5, L + 7, ym + 3.5, active_colour, r=1)
        c.text(26, y, name, 15, BONE, anchor='ls')
        if dots:
            c.text(R, y, '.' * (1 + int(frac * 6) % 4), 14, active_colour, 'mono', 'rs')
    else:
        c.text(26, y, name, 15, FAINT, anchor='ls')


def s03_checking(t):
    """The checklist as a two-line window: the last result and the check
    running now (or, at the start, the running check and the next one)."""
    c = Canvas()
    n = len(CHECKS) - 1
    done = min(n, int(t * n))
    frac = (t * n) % 1
    check_header(c, done, frac)
    c.text(R, RA, 'Battery held back', 13, DIM, anchor='rs')
    if done == 0:
        check_row(c, RB, 0, 'active', frac)
        check_row(c, RC, 1, 'todo')
    else:
        check_row(c, RB, done - 1, 'done')
        check_row(c, RC, done, 'active', frac)
    c.tag('S03')
    return c


def s04_precharge(t):
    c = Canvas()
    check_header(c, 4, t)
    check_row(c, RB, 3, 'done')
    check_row(c, RC, 4, 'active', t, dots=False)
    v = 16.8 * ease(t)
    ym = RC - cap(15) / 2
    x0 = 26 + width('Pre-charge', 15) + 12
    x1 = R - width('00.0 V', 14, 'mono') - 12
    c.rect(x0, ym - 3, x1, ym + 3, BAR_BG, r=3)
    if ease(t) > 0.03:
        c.rect(x0, ym - 3, x0 + (x1 - x0) * ease(t), ym + 3, EMBER, r=3)
    c.text(R, RC, f'{v:4.1f} V', 14, EMBER, 'mono', 'rs')
    c.tag('S04')
    return c


def s05_engaged(t):
    flash = 1 - ease(t * 1.6)
    c = Canvas(lerp(INK, GREEN, flash))
    rmax, gap, size = 22, 14, 34
    w = 2 * rmax + gap + width('LIVE', size, 'sans', 600)
    x0 = (PW - w) / 2
    c.status(x0 + rmax, PH / 2, 4 + (rmax - 4) * ease(t * 1.4), lerp(GREEN, INK, flash * 0.8))
    c.text(x0 + 2 * rmax + gap, PH / 2 + cap(size) / 2, 'LIVE', size, lerp(GREEN, INK, flash), 'sans', 'ls', 600)
    c.tag('S05')
    return c


def spark(c, x0, y0, w, h, t, colour):
    pts = []
    for i in range(60):
        u = i / 59
        v = 0.42 + 0.03 * math.sin((u * 9 + t * 6)) + (0.25 if 0.2 < u < 0.26 else 0)
        pts.append((x0 + u * w, y0 + h - (v / 1.0) * h))
    c.line(pts, colour, 1.2)


def s06_live(t):
    c = Canvas()
    c.dot_for(17, RA, 16, GREEN)
    x = c.run(27, RA, [('LIVE', 16, GREEN, 'sans', 600)])
    c.text(x + 10, RA, DRONE, 13, DIM, anchor='ls')
    c.text(R, RA, 'Same as last time', 13, GREEN, anchor='rs')
    amps = 0.42 + 0.01 * math.sin(t * 20)
    x = c.run(L, RC, [(f'{amps:0.2f}', 38, BONE, 'mono'), (' ', 6, BONE, 'mono'), ('A', 18, DIM, 'mono')])
    sx = x + 10
    spark(c, sx, 31, 46, 22, t, GREEN)
    c.text(sx, RC, f'0:{int(t * 30):02d}', 13, DIM, 'mono', 'ls')
    c.text(R, RB, BATT, 13, BONE, 'mono', 'rs')
    c.text(R, RC, 'Limit AUTO 2.0 A', 13, DIM, anchor='rs')
    c.tag('S06')
    return c


def s07_warning(t):
    c = Canvas()
    c.rect(0, 0, PW, 3, EMBER, decor=True)
    c.dot_for(17, RA, 15, EMBER)
    c.text(27, RA, 'LIVE · LOOK', 15, EMBER, 'sans', 'ls', 600)
    c.text(R, RA, 'More than last time', 13, BONE, anchor='rs')
    c.run(L, 47, [('0.42', 22, DIM, 'mono'), (' ', 10, DIM, 'mono'), ('→', 22, EMBER, 'mono'), (' ', 10, DIM, 'mono'),
                  ('0.71', 22, EMBER, 'mono'), (' ', 10, DIM, 'mono'), ('A', 22, EMBER, 'mono')])
    c.text(R, 47, 'Close the guard', 13, BONE, anchor='rs')
    c.text(R, RC, 'to cut power.', 13, BONE, anchor='rs')
    c.text(L, RC, 'Often a 5 V regulator or VTX', 13, DIM, anchor='ls')
    c.tag('S07')
    return c


def _abort(t, title, value, line1, line2, tagname):
    on = int(t * 6) % 2 == 0
    c = Canvas(RED if t < 0.08 else INK)
    c.frame(RED if on else (90, 20, 18))
    x = c.run(14, 28, [('ABORT', 24, RED, 'sans', 600)])
    c.text(x + 10, 28, title, 16, BONE, 'sans', 'ls', 600)
    c.text(14, 47, line1, 13, BONE, anchor='ls')
    c.text(PW - 14, 47, value, 15, RED, 'mono', 'rs')
    c.text(14, RC, line2, 13, DIM, anchor='ls')
    c.tag(tagname)
    return c


def s08_short(t):
    return _abort(t, 'Short circuit', '0.3 Ω', 'Battery never reached the drone',
                  'Find the short, then close the guard.', 'S08')


def s09_reversed(t):
    return _abort(t, 'Leads reversed', 'RED ↔ BLACK', 'Drone lead is backwards',
                  'Nothing was powered. Close the guard.', 'S09')


def s10_bind(t):
    c = Canvas()
    step = min(3, 1 + int(t * 3))
    c.text(L, 34, f'BIND  {step}/3', 20, BLUE, 'sans', 'ls', 600)
    for k in range(3):
        c.status(L + 6 + 16 * k, 54, 6, BLUE if k < step else (30, 45, 70), fill=True)
    c.text(R, 34, 'Power-cycling the receiver', 13, BONE, anchor='rs')
    c.text(R, 58, 'Then press Bind in your radio', 13, DIM, anchor='rs')
    c.tag('S10')
    return c


def s11_motor(t):
    c = Canvas()
    c.stripes(0, 6, EMBER, t * 6)
    c.text(L, 25, '25 A MOTOR TEST', 15, EMBER, 'sans', 'ls', 600)
    c.text(L, RC, 'Props off?', 24, BONE, 'sans', 'ls', 600)
    c.text(R, 41, 'Press + again to confirm', 13, BONE, anchor='rs')
    tx = R - width('3 s', 13, 'mono')
    x0, x1 = L + width('Props off?', 24, 'sans', 600) + 16, tx - 10
    ym = RC - cap(13, 'mono') / 2
    c.rect(x0, ym - 2.5, x0 + (x1 - x0) * (1 - t), ym + 2.5, EMBER, r=2.5)
    c.text(R, RC, '3 s', 13, DIM, 'mono', 'rs')
    c.tag('S11')
    return c


def s12_closing(t):
    k = ease(t * 2)
    c = Canvas()
    h = int(PH * (1 - k) / 2)
    c.rect(0, 0, PW, PH, INK, decor=True)
    c.text(PW / 2, 38, 'POWER CUT', 28, lerp(EMBER, BONE, k), 'sans', 'ms', 600)
    c.text(PW / 2, 59, 'Guard closed · drone off', 13, DIM, anchor='ms')
    c.rect(0, 0, PW, h, (30, 27, 22), decor=True)
    c.rect(0, PH - h, PW, PH, (30, 27, 22), decor=True)
    c.tag('S12')
    return c


def s13_limit(t):
    c = Canvas()
    c.text(L, RA, 'LIMIT', 13, DIM, 'mono', 'ls', 600)
    c.text(R, RA, '2 A average · 8 A peak cut-off', 13, BONE, anchor='rs')
    opts = ['AUTO', '1', '2', '5', '10', '25']
    sel = 2
    gap = 6
    w = (R - L - gap * (len(opts) - 1)) / len(opts)
    y0, y1 = 28, 49
    for i, o in enumerate(opts):
        x = L + i * (w + gap)
        on = i == sel
        c.rect(x, y0, x + w, y1, EMBER if on else BAR_BG, r=4)
        c.text(x + w / 2, (y0 + y1) / 2 + cap(13, 'mono') / 2, o, 13, INK if on else BONE, 'mono', 'ms', 600)
    c.text(L, RC, 'Auto learns each drone.', 13, DIM, anchor='ls')
    c.text(R, RC, '25 A: props off only', 13, DIM, anchor='rs')
    c.tag('S13')
    return c


# ------------------------------------------------------------ battery screens
# Shown with the guard closed (S14-S16, S18) or whenever the drone side has a
# battery (S17).  Numbers come from firmware/model/battery.py.

BAR_V0, BAR_V1 = 3.30, 4.35        # bar scale: empty LiPo .. full LiHV


def cell_bars(c, cells, x0, y0, x1, y1):
    """One bar per cell, lowest in Ember, highest in Bone, the rest Dim."""
    n = len(cells)
    lo = min(range(n), key=lambda i: cells[i])
    hi = max(range(n), key=lambda i: cells[i])
    gap = 6 if n <= 3 else 4
    w = (x1 - x0 - gap * (n - 1)) / n
    for i, v in enumerate(cells):
        x = x0 + i * (w + gap)
        f = max(0.04, min(1.0, (v - BAR_V0) / (BAR_V1 - BAR_V0)))
        col = EMBER if i == lo else BONE if i == hi else DIM
        c.rect(x, y0, x + w, y1, BAR_BG, r=2)
        c.rect(x, y1 - (y1 - y0) * f, x + w, y1, col, r=2)


DELTA_WORDS = [(20, 'Balanced', GREEN), (50, 'Drifting', EMBER), (10 ** 6, 'Out of balance', RED)]


def delta_line(c, x, y, cells):
    d = round((max(cells) - min(cells)) * 1000)
    word, col = next((w, k) for lim, w, k in DELTA_WORDS if d <= lim)
    return c.run(x, y, [(f'Δ {d} mV', 13, col, 'mono'), ('  ' + word, 13, col, 'sans')])


BARS_X0 = R - 84                   # cell bars sit at the right, over the cell range


def battery_view(c, header, kind, context, cells, pct, pct_colour):
    """S14 / S16: header and context on top, total and charge in the
    middle with the cell bars to the right, the balance verdict under."""
    x = c.run(L, RA, [(header, 13, DIM, 'mono', 600)])
    c.text(x + 10, RA, kind, 13, DIM, anchor='ls')
    c.text(R, RA, context, 13, DIM, anchor='rs')
    x = c.run(L, 47, [(f'{sum(cells):.2f}', 26, BONE, 'mono'), (' ', 6, BONE, 'mono'), ('V', 16, DIM, 'mono')])
    c.text(x + 14, 47, f'{pct} %', 20, pct_colour, 'mono', 'ls')
    cell_bars(c, cells, BARS_X0, 28, R, 47)
    delta_line(c, L, RC, cells)


PACK = [4.11, 4.12, 4.09, 4.13, 4.12, 4.11]


def s14_battery(t):
    c = Canvas()
    battery_view(c, 'BATTERY', '6S · LiPo', 'Above storage', PACK, 91, GREEN)
    lo, hi = min(PACK), max(PACK)
    c.run(R, RC, [(f'{lo:.2f}', 13, EMBER, 'mono'), ('–', 13, DIM, 'mono'), (f'{hi:.2f}', 13, BONE, 'mono')], 'r')
    c.tag('S14')
    return c


def s15_battery_warning(t):
    c = Canvas()
    c.rect(0, 0, PW, 3, EMBER, decor=True)
    c.dot_for(17, RA, 14, EMBER)
    c.text(27, RA, 'CHECK BATTERY', 14, EMBER, 'sans', 'ls', 600)
    c.text(R, RA, 'others 3.30 V', 13, DIM, anchor='rs')
    c.text(L, 47, '2.71 V', 24, EMBER, 'mono', 'ls')
    c.text(R, 47, 'Cell 3 is over-discharged', 13, BONE, anchor='rs')
    c.text(L, RC, 'Charge at 1C or less', 13, DIM, anchor='ls')
    c.text(R, RC, "Retire it if it won't hold", 13, BONE, anchor='rs')
    c.tag('S15')
    return c


STORE = [3.85, 3.84, 3.86]


def s16_balance_only(t):
    c = Canvas()
    battery_view(c, 'BALANCE CHECK', '3S', 'No drone attached', STORE, 55, BONE)
    c.text(R, RC, 'At storage: put away', 13, GREEN, anchor='rs')
    c.tag('S16')
    return c


def s17_wrong_side(t):
    c = Canvas()
    c.status(25, 38, 13, EMBER)
    c.text(46, RA, 'Battery on the drone side', 15, BONE, 'sans', 'ls', 600)
    c.text(46, RB, '← Move it to the Battery end', 13, BONE, anchor='ls')
    c.text(46, RC, 'Nothing was powered.', 13, DIM, anchor='ls')
    c.text(R, RC, '16.4 V', 16, EMBER, 'mono', 'rs')
    c.tag('S17')
    return c


def s18_shifted(t):
    c = Canvas()
    c.text(L, RA, 'Balance plug shifted', 15, BONE, 'sans', 'ls', 600)
    c.text(R, RA, 'Reading OK', 13, GREEN, anchor='rs')
    # the 9-pin header, pin 1 on the left; a 4S plug sitting 2 pins along.
    # The plug's black wire (Dim) is on pin 3.
    shift, wires = 2, 5
    x0, pitch, y, s = L, 13, 31, 10
    for p in range(9):
        x = x0 + p * pitch
        c.rect(x, y, x + s, y + s, FAINT, width=1, r=1.5)
        if shift <= p < shift + wires:
            black = p == shift
            c.rect(x + 2.5, y + 2.5, x + s - 2.5, y + s - 2.5, DIM if black else BONE, r=1)
        c.text(x + s / 2, RC, str(p + 1), 13, EMBER if p == shift else DIM, 'mono', 'ms')
    c.rect(x0 + shift * pitch - 3, y - 3, x0 + (shift + wires - 1) * pitch + s + 3, y + s + 3, EMBER,
           width=1, r=2.5)
    c.text(R, RB, 'Black wire to pin 1', 13, EMBER, anchor='rs')
    c.text(R, RC, "Alone, it can't be read", 13, DIM, anchor='rs')
    c.tag('S18')
    return c


# --------------------------------------------------------------- pack memory
# The box numbers each new pack; the owner writes the number on it.  Next
# time it guesses which pack it is and the owner confirms on the rocker.

def pack_view(c, dot, name):
    """The pack's number, big, with a status dot in the gutter."""
    size = 30
    c.dot_for(18, RB, size, dot, r=6)
    c.text(30, RB, name, size, BONE, 'sans', 'ls', 600)


def s19_new_pack(t):
    c = Canvas()
    pack_view(c, BLUE, 'Pack 12')
    c.text(R, RA, 'New pack', 13, BLUE, anchor='rs')
    c.text(R, RB, '16.42 V  4S', 16, BONE, 'mono', 'rs')
    c.text(30, RC, 'Write 12 on it', 13, BONE, anchor='ls')
    rocker(c, R, RC, [('+', 'yes, new'), ('−', 'no, old one')])
    c.tag('S19')
    return c


def s20_pack_guess(t):
    c = Canvas()
    pack_view(c, GREEN, 'Pack 7?')
    c.text(R, RA, 'Used 23 times', 13, DIM, anchor='rs')
    c.text(R, RB, '16.61 V  4S', 16, BONE, 'mono', 'rs')
    c.run(30, RC, [('R ', 13, BONE, 'sans'), ('+18 %', 13, EMBER, 'mono'), ('  since new', 13, BONE, 'sans')])
    rocker(c, R, RC, [('+', 'yes'), ('−', 'other')])
    c.tag('S20')
    return c


def s21_too_high(t):
    """A pack above 14S: refused before anything happens; nothing arms."""
    c = Canvas()
    c.status(25, 38, 13, RED)
    c.text(46, RA, 'Too high', 15, BONE, 'sans', 'ls', 600)
    x = c.run(46, 47, [('61.9 V', 22, RED, 'mono')])
    c.text(x + 8, 47, 'is above 14S.', 15, RED, anchor='ls')
    c.text(46, RC, 'Unplug it.', 15, RED, anchor='ls')
    c.text(R, RC, 'Nothing will arm', 13, DIM, anchor='rs')
    c.tag('S21')
    return c


SCREENS = [s00_startup, s01_safe, s02_armed, s03_checking, s04_precharge, s05_engaged, s06_live, s07_warning,
           s08_short, s09_reversed, s10_bind, s11_motor, s12_closing, s13_limit,
           s14_battery, s15_battery_warning, s16_balance_only, s17_wrong_side, s18_shifted,
           s19_new_pack, s20_pack_guess, s21_too_high]
TITLES = ['Start-up', 'Guard closed', 'Guard lifted', 'Switch up: checks', 'Pre-charge', 'Engaged', 'Live',
          'Changed since last time', 'Fault: short', 'Fault: reversed', 'Bind', 'Motor test confirm',
          'Guard closed again', 'Limit', 'Battery', 'Battery warning', 'Balance check only',
          'Battery on the drone side', 'Balance plug shifted', 'New pack', 'Pack 7?', 'Too high']

# the story told by the video: (screen, seconds, sound)
TIMELINE = [(s00_startup, 1.5, None), (s01_safe, 2.0, None), (s02_armed, 2.2, 'arm'), (s03_checking, 2.4, 'tick'),
            (s04_precharge, 1.4, 'rise'), (s05_engaged, 0.9, 'engage'), (s06_live, 2.6, None),
            (s07_warning, 2.4, 'warn'), (s12_closing, 1.2, 'cut'), (s01_safe, 1.0, None),
            (s02_armed, 1.0, 'arm'), (s03_checking, 0.8, 'tick'), (s08_short, 2.6, 'alarm'),
            (s12_closing, 1.0, 'cut'), (s10_bind, 2.4, 'bind'), (s11_motor, 1.8, 'warn'),
            (s13_limit, 1.8, None)]


# ------------------------------------------------------------------- checks

def lint(ts=(0.0, 0.3, 0.55, 0.8, 1.0)):
    """Every screen at several moments: content inside the safe area, no
    text under MIN_TEXT, no two pieces of text closer than 4 px."""
    import numpy as np
    safe = np.asarray(safe_mask()) > 0
    problems = []
    for i, fn in enumerate(SCREENS):
        for t in ts:
            c = fn(t)
            ink = np.asarray(c.ink) > 96
            out = ink & ~safe
            if out.any():
                ys, xs = np.nonzero(out)
                problems.append(f'S{i:02d} t={t}: {out.sum()} px outside the safe area, '
                                f'x {xs.min() / SCALE:.0f}-{xs.max() / SCALE:.0f}, '
                                f'y {ys.min() / SCALE:.0f}-{ys.max() / SCALE:.0f}')
            for box, s, size in c.texts:
                if size < MIN_TEXT:
                    problems.append(f'S{i:02d}: "{s}" is {size} px (min {MIN_TEXT})')
            bx = c.texts
            for a in range(len(bx)):
                for b in range(a + 1, len(bx)):
                    (ax0, ay0, ax1, ay1), sa, _ = bx[a]
                    (bx0, by0, bx1, by1), sb, _ = bx[b]
                    gx = max(bx0 - ax1, ax0 - bx1)
                    gy = max(by0 - ay1, ay0 - by1)
                    if gx < 4 and gy < 4:
                        problems.append(f'S{i:02d} t={t}: "{sa}" and "{sb}" {max(gx, gy):.1f} px apart')
    return sorted(set(problems))


# ------------------------------------------------------------------ outputs

PAPER = (233, 228, 216)
FACE = (42, 38, 33)                # the case face round the opening
LABEL = (27, 24, 19)


def sheet(out, k, cols, t=0.55):
    """Every screen at k x, masked to the opening, set in a strip of case
    face, labelled with its number."""
    pad, bez, lab_h = 28, 8 * k // 2, 40
    tw, th = PW * k, PH * k
    cw, ch = tw + 2 * bez, th + 2 * bez
    rows = (len(SCREENS) + cols - 1) // cols
    im = Image.new('RGB', (cols * (cw + pad) + pad, rows * (ch + lab_h + pad) + pad), PAPER)
    d = ImageDraw.Draw(im)
    lab = ImageFont.truetype(os.path.join(FONTS, 'InstrumentSans-VariableFont.ttf'), 13 + 3 * k)
    for i, (fn, title) in enumerate(zip(SCREENS, TITLES)):
        x = pad + (i % cols) * (cw + pad)
        y = pad + (i // cols) * (ch + lab_h + pad)
        d.text((x, y + lab_h - 10), f'S{i:02d}  {title}', font=lab, fill=LABEL, anchor='ls')
        d.rounded_rectangle([x, y + lab_h, x + cw, y + lab_h + ch], radius=bez + CORNER * k / 2, fill=FACE)
        scr = fn(t).final().resize((tw, th), Image.LANCZOS)
        m = opening_mask(k)
        im.paste(scr, (x + bez, y + lab_h + bez), m)
    im.save(out)


def storyboard(out):
    sheet(out, 2, 3)


def contact_sheet(out):
    sheet(out, 3, 2)


def sound(kind, dur):
    """An ffmpeg aevalsrc expression for a beep pattern lasting `dur` s."""
    return {
        'arm': "0.4*sin(2*PI*(880+600*t)*t)*between(t,0,0.18)+0.4*sin(2*PI*1760*t)*between(t,0.22,0.3)",
        'tick': "0.25*sin(2*PI*2400*t)*lt(mod(t,0.48),0.03)",
        'rise': "0.3*sin(2*PI*(400+900*t/%f)*t)" % dur,
        'engage': "0.45*sin(2*PI*1320*t)*between(t,0,0.12)+0.45*sin(2*PI*1760*t)*between(t,0.14,0.4)",
        'warn': "0.35*sin(2*PI*1200*t)*(lt(mod(t,0.5),0.08)+between(mod(t,0.5),0.12,0.2))*lt(t,1)",
        'alarm': "0.45*sin(2*PI*700*t)*lt(mod(t,0.33),0.2)",
        'cut': "0.45*sin(2*PI*(900-500*t)*t)*between(t,0,0.25)",
        'bind': "0.3*sin(2*PI*1500*t)*lt(mod(t,0.8),0.06)",
    }.get(kind, '0')


def video(out):
    tmp = tempfile.mkdtemp(prefix='sb-ui-')
    try:
        n = 0
        audio = []
        for fn, secs, snd in TIMELINE:
            frames = int(secs * FPS)
            for k in range(frames):
                fn(k / max(frames - 1, 1)).final().save(os.path.join(tmp, f'f{n:05d}.png'))
                n += 1
            a = os.path.join(tmp, f'a{len(audio):02d}.wav')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'lavfi', '-i',
                            f"aevalsrc='{sound(snd, secs)}':s=44100:d={secs}", a], check=True)
            audio.append(a)
        lst = os.path.join(tmp, 'a.txt')
        with open(lst, 'w') as f:
            f.writelines(f"file '{a}'\n" for a in audio)
        wav = os.path.join(tmp, 'all.wav')
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', lst, wav],
                       check=True)
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', str(FPS), '-i',
                        os.path.join(tmp, 'f%05d.png'), '-i', wav, '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                        '-crf', '18', '-c:a', 'aac', '-b:a', '128k', '-shortest', out], check=True)
        # the frames, kept for the Blender screen texture: frames/ at 30 fps
        # from f00000, frames24/ resampled to 24 fps from f00001 (an image
        # sequence in Blender starts at 1)
        seq = os.path.join(HERE, 'frames')
        seq24 = os.path.join(HERE, 'frames24')
        for p in (seq, seq24):
            shutil.rmtree(p, ignore_errors=True)
            os.makedirs(p)
        for i in range(n):
            Image.open(os.path.join(tmp, f'f{i:05d}.png')).resize((PW * 2, PH * 2), Image.LANCZOS) \
                .save(os.path.join(seq, f'f{i:05d}.png'))
        n24 = round(n * 24 / FPS)
        for j in range(n24):
            src = os.path.join(seq, f'f{min(n - 1, round(j * FPS / 24)):05d}.png')
            shutil.copyfile(src, os.path.join(seq24, f'f{j + 1:05d}.png'))
        return n
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    issues = lint()
    print('\n'.join(issues) if issues else 'lint: clean')
    storyboard(os.path.join(HERE, 'storyboard.png'))
    contact_sheet(os.path.join(HERE, 'bar-screens.png'))
    if '--no-video' not in sys.argv:
        print('frames', video(os.path.join(HERE, 'arm-sequence.mp4')))
