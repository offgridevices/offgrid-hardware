"""Canary v1 product video scenes. Design coordinates are 4K (3840 x 2160);
broll_lib renders them to 1080p. Every number on screen is read from a
result file (DRC report, HIL results, SPICE results) or from the design.
"""
import csv, json, math, os, re
from PIL import Image
from broll_lib import (Canvas, TEAL, AMBER, RED, GREEN, SLATE, SLATE_DK, WHITE, SOFTWHITE,
                       CHIP_BG, PCB, COPPER, lerp, lerpc, smooth, smoother, clamp01,
                       ease_out, pulse, bold, med, reg, light, mono, chip, checkmark, xmark)

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
OUT = os.path.join(HERE, 'out')
LEAD = 0.6                       # narration starts this far into each segment
WORDS = json.load(open(os.path.join(OUT, 'words.json')))
YELLOW = (246, 228, 40)
GREY = (120, 116, 110)

_img = {}
def img(name):
    if name not in _img:
        _img[name] = Image.open(os.path.join(OUT, 'stills', name)).convert('RGBA')
    return _img[name]


def cue(seg, word, after=0.0, default=None):
    """time (segment clock) at which `word` is spoken"""
    w = word.lower()
    for s, t0, t1 in WORDS[seg]:
        if re.sub(r'[^a-z0-9%]', '', s.lower()).startswith(w) and t0 + LEAD >= after:
            return t0 + LEAD
    if default is None:
        raise KeyError(f'{seg}: no word {word!r} after {after}')
    return default


def A(t, t0, d=0.6):
    return smooth((t - t0) / d)


def eyebrow(cv, t, s, y=230):
    cv.text(1920, y, s, med(46), SOFTWHITE, a=int(255 * A(t, 0.2)), ls=9)


def closing(cv, t, t0, s, color=TEAL):
    a = A(t, t0, 0.8)
    if a > 0.02:
        cv.text(1920, 2010, s, bold(68), color, a=int(255 * a))


# ------------------------------------------------------------------ icons
def battery(cv, cx, cy, w, h, col, a, frac=1.0):
    cv.rrect(cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2, None, a=a, radius=26, width=10, outline=col, oa=a)
    cv.rrect(cx - w * 0.16, cy - h / 2 - 34, cx + w * 0.16, cy - h / 2 + 4, col, a=a, radius=8)
    inner = h - 44
    top = cy + h / 2 - 22 - inner * frac
    cv.rrect(cx - w / 2 + 22, top, cx + w / 2 - 22, cy + h / 2 - 22, col, a=int(a * 0.85), radius=12)


def cloud(cv, cx, cy, s, col, a, t=0):
    for i, (dx, dy, r) in enumerate([(-0.45, 0.1, 0.36), (0.0, -0.18, 0.46), (0.45, 0.08, 0.36),
                                     (-0.2, 0.25, 0.3), (0.25, 0.28, 0.3)]):
        wob = 6 * math.sin(t * 1.7 + i)
        cv.disk(cx + dx * s + wob, cy + dy * s, r * s, col, a=a)


def thermo(cv, cx, cy, h, level, col, a):
    cv.rrect(cx - 34, cy - h / 2, cx + 34, cy + h / 2 - 40, None, a=a, radius=34, width=9, outline=SLATE, oa=a)
    cv.disk(cx, cy + h / 2 - 20, 62, SLATE, a=a)
    cv.disk(cx, cy + h / 2 - 20, 46, col, a=a)
    top = cy + h / 2 - 40 - (h - 80) * level
    cv.rect(cx - 16, top, cx + 16, cy + h / 2 - 20, col, a=a)


def flame(cv, cx, cy, s, a, t=0):
    f = 1 + 0.06 * math.sin(t * 9)
    cv.poly([(cx, cy - s * 1.1 * f), (cx + s * 0.62, cy + s * 0.1), (cx + s * 0.45, cy + s * 0.6),
             (cx - s * 0.45, cy + s * 0.6), (cx - s * 0.62, cy + s * 0.1)], RED, a=a)
    cv.poly([(cx, cy - s * 0.45 * f), (cx + s * 0.3, cy + s * 0.25), (cx, cy + s * 0.55),
             (cx - s * 0.3, cy + s * 0.25)], AMBER, a=a)


def smoke(cv, cx, cy, s, a, t=0):
    for i in range(5):
        ph = (t * 0.25 + i / 5) % 1
        cv.disk(cx + 40 * math.sin(i * 2.1 + t), cy + s * 0.6 - ph * s * 1.4, s * (0.25 + 0.25 * ph),
                GREY, a=int(a * (1 - ph) * 0.9))


def arrow(cv, x0, y0, x1, y1, col, a, w=8, head=26):
    cv.line(x0, y0, x1, y1, col, a=a, width=w)
    ang = math.atan2(y1 - y0, x1 - x0)
    p = [(x1, y1), (x1 - head * math.cos(ang - 0.45), y1 - head * math.sin(ang - 0.45)),
         (x1 - head * math.cos(ang + 0.45), y1 - head * math.sin(ang + 0.45))]
    cv.poly(p, col, a=a)


def alarm_puck(cv, cx, cy, s, col, a):
    cv.disk(cx, cy, s, (200, 194, 182), a=a)
    cv.ring(cx, cy, s * 0.62, SLATE_DK, a=a, width=6)
    cv.disk(cx, cy, s * 0.14, col, a=a)


# ================================================================== scenes
def title(t, D, ending=False):
    cv = Canvas()
    z = 1.0 + 0.04 * (t / D)
    cv.glow_disk(2450, 1150, 900, AMBER, 0.20 * A(t, 0.0, 1.2))
    cv.composite(glow_radius=120)
    cv.image(img('hero.png'), 2450, 1080, 3000 * z, a=A(t, 0.0, 1.2))
    a1, a2, a3 = A(t, 0.4), A(t, 0.8), A(t, 1.2)
    cv.text(300, 700, 'OPEN HARDWARE  ·  v1' if not ending else 'OFFGRID DEVICES', mono(46), TEAL,
            a=int(255 * a1), anchor='lm')
    cv.text(290, 880, 'CANARY', bold(230), WHITE, a=int(255 * a2), anchor='lm')
    if not ending:
        cv.text(300, 1060, 'a first-vent detector', med(66), SOFTWHITE, a=int(255 * a3), anchor='lm')
        cv.text(300, 1145, 'for lithium batteries', med(66), SOFTWHITE, a=int(255 * a3), anchor='lm')
    else:
        cv.text(300, 1060, 'Hear the battery,', med(70), SOFTWHITE, a=int(255 * a3), anchor='lm')
        cv.text(300, 1150, 'before you smell the smoke.', med(70), SOFTWHITE, a=int(255 * a3), anchor='lm')
        cv.text(300, 1420, 'CERN-OHL-S v2  ·  KiCad 10', mono(44), SOFTWHITE, a=int(200 * A(t, 2.0)), anchor='lm')
    return cv.finish()


def problem(t, D):
    S = 'problem'
    X = [520, 1220, 1920, 2620, 3320]
    Y = 880
    T = [cue(S, 'charged'), cue(S, 'vent'), cue(S, 'heats'), cue(S, 'runs'), cue(S, 'burns')]
    t_alarm, t_end = cue(S, 'smoke', after=T[4]), cue(S, 'end', after=T[4])
    cv = Canvas()
    for i, x in enumerate(X):
        a = A(t, T[i])
        if a > 0.02 and i == 1:
            cv.glow_disk(x, Y, 260, AMBER, 0.25 * a)
        if a > 0.02 and i >= 3:
            cv.glow_disk(x, Y, 240, RED, 0.25 * a)
    a5 = A(t, t_alarm)
    if a5 > 0.02:
        cv.glow_disk(X[4], 1560, 200, RED, 0.3 * a5 * pulse(t, 3))
    cv.composite(glow_radius=60)
    eyebrow(cv, t, 'HOW A LITHIUM CELL FAILS')
    labels = [('CHARGING', 'overnight'), ('FIRST VENT', 'solvent vapour + CO2'), ('SELF-HEATING', 'faster and faster'),
              ('RUNAWAY', 'fire'), ('SMOKE', 'last sign')]
    for i, x in enumerate(X):
        a = A(t, T[i])
        if a <= 0.02:
            continue
        ai = int(255 * a)
        if i == 0:
            battery(cv, x, Y, 190, 300, GREEN, ai, frac=0.35 + 0.6 * ((t * 0.12) % 1))
        elif i == 1:
            battery(cv, x, Y + 60, 170, 250, SLATE, ai, 0.9)
            cloud(cv, x, Y - 150, 170, AMBER, int(ai * 0.85), t)
        elif i == 2:
            thermo(cv, x, Y, 360, clamp01(0.3 + 0.6 * smooth((t - T[2]) / 4)), lerpc(AMBER, RED, smooth((t - T[2]) / 4)), ai)
        elif i == 3:
            flame(cv, x, Y + 20, 170, ai, t)
        else:
            smoke(cv, x, Y, 200, ai, t)
        cv.text(x, 1180, labels[i][0], bold(54), WHITE, a=ai, ls=6)
        cv.text(x, 1262, labels[i][1], med(44), SOFTWHITE, a=ai)
        if i:
            arrow(cv, X[i - 1] + 190, Y, x - 190, Y, SLATE, ai, w=7)
    if a5 > 0.02:
        ai = int(255 * a5)
        alarm_puck(cv, X[4], 1560, 95, RED, ai)
        cv.text(X[4], 1730, 'SMOKE ALARM', bold(50), RED, a=ai, ls=5)
        arrow(cv, X[4], 1440, X[4], 1330, RED, ai, w=7)
        # the window already lost
        cv.line(X[1], 1560, X[4] - 160, 1560, SLATE_DK, a=int(ai * 0.9), width=5)
        cv.text((X[1] + X[4]) / 2 - 80, 1620, 'time you never get', med(46), SOFTWHITE, a=ai)
    closing(cv, t, t_end, 'smoke is the last sign, not the first')
    return cv.finish()


def gap(t, D):
    S = 'gap'
    X = [880, 1920, 2960]
    t1, t2, t3, t4 = LEAD + 0.0, cue(S, 'electric'), cue(S, 'battery'), cue(S, 'design')
    cv = Canvas()
    a4 = A(t, t4, 0.8)
    if a4 > 0.02:
        cv.glow_disk(X[2], 1400, 230, TEAL, 0.45 * a4)
    cv.composite(glow_radius=50)
    eyebrow(cv, t, 'WHO GETS AN OFF-GAS DETECTOR')
    cols = [('GRID STORAGE', t1, True), ('ELECTRIC CARS', t2, True), ('YOUR HALLWAY', t3, False)]
    for i, (name, tc, ok) in enumerate(cols):
        a = A(t, tc)
        if a <= 0.02:
            continue
        ai, x = int(255 * a), X[i]
        if i == 0:      # container with ribs
            cv.rrect(x - 260, 640, x + 260, 960, (70, 66, 60), a=ai, radius=14, width=6, outline=SLATE, oa=ai)
            for k in range(7):
                cv.line(x - 210 + k * 70, 670, x - 210 + k * 70, 930, SLATE_DK, a=ai, width=6)
        elif i == 1:    # car
            cv.rrect(x - 290, 780, x + 290, 920, SLATE, a=ai, radius=40)
            cv.poly([(x - 170, 780), (x - 90, 680), (x + 120, 680), (x + 200, 780)], SLATE, a=ai)
            for wx in (x - 170, x + 170):
                cv.disk(wx, 930, 62, (40, 36, 30), a=ai)
                cv.disk(wx, 930, 26, SLATE_DK, a=ai)
        else:           # e-bike battery on a charger lead
            cv.rrect(x - 110, 640, x + 110, 960, (66, 62, 56), a=ai, radius=30, width=6, outline=SLATE, oa=ai)
            cv.rrect(x - 60, 610, x + 60, 650, SLATE, a=ai, radius=10)
            cv.line(x + 110, 900, x + 260, 900, SLATE_DK, a=ai, width=8)
            cv.rrect(x + 250, 860, x + 330, 940, SLATE_DK, a=ai, radius=10)
        cv.text(x, 1150, name, bold(56), WHITE, a=ai, ls=6)
        if ok:
            checkmark(cv, x, 1390, 120, GREEN, a=ai, width=18)
            cv.text(x, 1560, 'off-gas detection', med(48), SOFTWHITE, a=ai)
        else:
            ax = int(ai * (1 - a4))
            if ax > 5:
                xmark(cv, x, 1390, 110, RED, a=ax, width=18)
                cv.text(x, 1560, 'nothing', med(48), SOFTWHITE, a=ax)
    if a4 > 0.02:
        chip(cv, X[2], 1400, 'CANARY', bold(70), (30, 24, 16), bg=YELLOW, pad=36, a=int(255 * a4))
        cv.text(X[2], 1560, 'order it assembled', med(48), WHITE, a=int(255 * a4))
    closing(cv, t, t4 + 1.0, 'an off-gas detector for the battery at home')
    return cv.finish()


TT_N = 240
def turntable(t, D):
    S = 'turntable'
    cv = Canvas()
    cv.glow_disk(1920, 1250, 1100, AMBER, 0.12)
    cv.composite(glow_radius=160)
    f = (t / D) * (TT_N - 1)
    i0 = int(f); i1 = min(i0 + 1, TT_N - 1); w = f - i0
    a = Image.open(os.path.join(OUT, 'tt', f't{i0:03d}.png')).convert('RGBA')
    if w > 0.01:
        b = Image.open(os.path.join(OUT, 'tt', f't{i1:03d}.png')).convert('RGBA')
        a = Image.blend(a, b, w)
    cv.image(a, 1920, 1000, 3840, a=A(t, 0.0, 0.8))
    eyebrow(cv, t, 'CANARY  v1')
    chips = [('60 x 40 mm', cue(S, '60')), ('2 COPPER LAYERS', cue(S, '2')),
             ('PARTS ON ONE SIDE', cue(S, 'every')), ('USB-C  5 V', cue(S, 'usb'))]
    xs = [690, 1510, 2420, 3220]
    for (s, tc), x in zip(chips, xs):
        ac = A(t, tc)
        if ac > 0.02:
            chip(cv, x, 1960, s, bold(50), WHITE, bg=CHIP_BG, pad=30, a=int(255 * ac), border=TEAL)
    return cv.finish()


# top render geometry: board mm -> top.png pixels
TOPX0, TOPY0, TOPK = 863.0, 370.0, 34.68
def mm2px(x, y):
    return TOPX0 + (x - 100) * TOPK, TOPY0 + (y - 100) * TOPK

TOUR = [  # (cue word, after-word, title, line 2, line 3, (x0,y0,x1,y1) board mm, zoom)
    ('mega', None, 'ATmega328P', 'runs the firmware', '8 MHz  ·  32 KB', (123, 116, 133, 126), 1.15),
    ('right', None, 'SENSOR HEAD', 'slot keeps board heat away', 'isolated by a routed slot', (149.2, 103.5, 159.5, 124), 1.25),
    ('sgp', None, 'SGP40', 'gas: solvent vapour', 'metal-oxide VOC sensor', (153.6, 105.8, 157.2, 109.4), 1.6),
    ('sht', None, 'SHT40', 'humidity + air temperature', 'compensates the gas reading', (153.9, 116.9, 156.9, 119.9), 1.6),
    ('middle', None, 'SCD41', 'carbon dioxide', 'photoacoustic, every 5 s', (137.9, 115.3, 149.3, 126.7), 1.3),
    ('bottom', None, 'THERMAL TAB', "the pack's skin temperature", 'NTC 1 %  ·  copper both faces', (100.4, 130.2, 115.2, 139.6), 1.3),
    ('remote', None, 'PROBE PORT', 'for packs inside a frame', 'JST-PH, any 10k NTC probe', (119.8, 129.6, 129.4, 139.8), 1.3),
    ('sounder', None, 'SOUNDER', '100 dB at 10 cm', '4 kHz magnetic transducer', (119.8, 101.4, 130.2, 111.8), 1.3),
    ('status', None, 'STATUS LIGHTS', 'OK  ·  WARN  ·  ALARM', 'green  ·  amber  ·  red', (137.0, 101.4, 148.6, 109.2), 1.4),
    ('hush', None, 'TEST / HUSH', 'one button', 'self-test, or 2 min hush', (141.8, 133.4, 150.6, 139.4), 1.4),
]


def tour(t, D):
    S = 'tour'
    times = [cue(S, w) for w, *_ in TOUR]
    k = 0
    for i, tc in enumerate(times):
        if t >= tc - 0.3:
            k = i
    # camera: ease from previous focus to current
    def focus(i):
        x0, y0, x1, y1 = TOUR[i][5]
        return mm2px((x0 + x1) / 2, (y0 + y1) / 2), TOUR[i][6]
    (fx, fy), z = focus(k)
    if k > 0:
        (px, py), pz = focus(k - 1)
        m = smoother((t - (times[k] - 0.3)) / 1.2)
        fx, fy, z = lerp(px, fx, m), lerp(py, fy, m), lerp(pz, z, m)
    else:
        m = smoother(t / 1.5)
        cx, cy = mm2px(130, 120)
        fx, fy, z = lerp(cx, fx, m), lerp(cy, fy, m), lerp(1.0, z, m)
    KD = 2000 / (60 * TOPK)            # design px per top.png px at zoom 1 (board 2000 wide)
    AX, AY = 1420, 1110
    def scr(px, py):
        return AX + (px - fx) * KD * z, AY + (py - fy) * KD * z
    cv = Canvas()
    x0, y0, x1, y1 = TOUR[k][5]
    sx0, sy0 = scr(*mm2px(x0, y0)); sx1, sy1 = scr(*mm2px(x1, y1))
    ah = A(t, times[k] - 0.1, 0.5)
    cv.glow_rect(sx0 - 20, sy0 - 20, sx1 + 20, sy1 + 20, TEAL, 0.35 * ah, radius=30)
    cv.composite(glow_radius=40)
    im = img('top.png')
    icx, icy = scr(im.width / 2, im.height / 2)
    cv.image(im, icx, icy, im.width * KD * z)
    # dim everything but the panel side a little for legibility
    for j in range(12):                     # soft-edged opaque side panel
        cv.rect(2560 + j * 10, 0, 2570 + j * 10, 2160, (24, 20, 16), a=int(255 * (j + 1) / 12))
    cv.rect(2680, 0, 3840, 2160, (24, 20, 16), a=255)
    cv.rrect(sx0 - 14, sy0 - 14, sx1 + 14, sy1 + 14, None, radius=22, width=8, outline=TEAL, oa=int(255 * ah))
    cv.text(3230, 230, 'ON THE BOARD', med(46), SOFTWHITE, a=int(255 * A(t, 0.2)), ls=9)
    _, _, tt_, l2, l3, *_ = TOUR[k]
    ap = A(t, times[k], 0.5)
    cv.text(3230, 900, tt_, bold(84), WHITE, a=int(255 * ap))
    cv.text(3230, 1040, l2, med(50), TEAL, a=int(255 * ap))
    cv.text(3230, 1130, l3, med(44), SOFTWHITE, a=int(255 * ap))
    # progress dots
    for i in range(len(TOUR)):
        cv.disk(2880 + i * 58, 1900, 12 if i != k else 17, TEAL if i <= k else SLATE_DK, a=230)
    return cv.finish()


def fusion(t, D):
    S = 'fusion'
    tsp, tbr, twa = cue(S, 'cleaning'), cue(S, 'someone'), cue(S, 'warm')
    tea, tve, tso = cue(S, 'each'), cue(S, 'venting'), cue(S, 'solvent')
    the = cue(S, 'heat', after=tso)
    ttw, tth, tca = cue(S, 'two'), cue(S, 'three'), cue(S, 'canary')
    # evidence levels (gas, co2, heat): 0 none, 1 weak, 2 strong; scenario name
    if t < tsp:
        lv, scen = (0, 0, 0), ''
    elif t < tbr:
        lv, scen = (1, 0, 0), 'CLEANING SPRAY'
    elif t < twa:
        lv, scen = (0, 1, 0), 'SOMEONE BREATHING'
    elif t < tve:
        lv, scen = (0, 0, 1), 'WARM ROOM'
    elif t < tso:
        lv, scen = (0, 0, 0), 'VENTING CELL'
    elif t < the:
        lv, scen = (2, 2, 0), 'VENTING CELL'
    elif t < tth:
        lv, scen = (2, 2, 2), 'VENTING CELL'
    else:
        lv, scen = (0, 0, 2), 'PACK HEATING > 3 °C/min'
    kinds = sum(1 for v in lv if v)
    alarm = (lv[0] and lv[1]) or lv[2] == 2
    state = 'ALARM' if alarm else ('WARN' if kinds else 'NORMAL')
    scol = {'ALARM': RED, 'WARN': AMBER, 'NORMAL': GREEN}[state]
    LX, YS = 720, [740, 1060, 1380]
    cv = Canvas()
    for i, v in enumerate(lv):
        if v:
            cv.glow_disk(LX, YS[i], 150, AMBER if v == 1 else RED, 0.45)
    cv.glow_disk(2900, 1060, 320, scol, 0.35 * (pulse(t, 6) if state == 'ALARM' else 1.0))
    cv.composite(glow_radius=40)
    eyebrow(cv, t, 'EVIDENCE, NOT A SINGLE SENSOR')
    if scen:
        chip(cv, 1920, 420, scen, bold(54), WHITE, bg=CHIP_BG, pad=30, border=SLATE)
    names = [('GAS', 'SGP40'), ('CO2', 'SCD41'), ('HEAT', 'NTC tab / probe')]
    for i, (n, sub) in enumerate(names):
        v = lv[i]
        col = (60, 54, 46) if not v else (AMBER if v == 1 else RED)
        cv.disk(LX, YS[i], 90, col)
        cv.ring(LX, YS[i], 90, SLATE, width=6)
        cv.text(LX + 160, YS[i] - 26, n, bold(60), WHITE, anchor='lm')
        cv.text(LX + 160, YS[i] + 44, sub, med(42), SOFTWHITE, anchor='lm')
        cv.line(1400, YS[i], 1700, 1060, col if v else SLATE_DK, width=8)
    cv.rrect(1700, 900, 2240, 1220, CHIP_BG, radius=30, width=6, outline=SLATE)
    cv.text(1970, 1010, 'KINDS OF', med(44), SOFTWHITE, ls=5)
    cv.text(1970, 1100, 'EVIDENCE', med(44), SOFTWHITE, ls=5)
    cv.text(1970, 1180, str(kinds), mono(48), WHITE)
    cv.line(2240, 1060, 2560, 1060, scol, width=8)
    cv.disk(2900, 1060, 300, scol, a=220 if not (state == 'ALARM' and int(t * 4) % 2) else 120)
    cv.text(2900, 1060, state, bold(92), (30, 24, 16), ls=6)
    # rule chips
    if t >= tea:
        chip(cv, 1300, 1700, 'one kind  =  WARN', bold(52), AMBER, bg=CHIP_BG, pad=30, a=int(255 * A(t, tea)))
    if t >= ttw:
        chip(cv, 2540, 1700, 'two kinds  =  ALARM', bold(52), RED, bg=CHIP_BG, pad=30, a=int(255 * A(t, ttw)))
    closing(cv, t, tca + 0.6, 'one sensor warns. agreement alarms.')
    return cv.finish()


# ---------------------------------------------------------------- simulation
_sim = None
def sim_data():
    global _sim
    if _sim is None:
        tel = []
        for line in open(os.path.join(V1, 'sim', 'hil', 'out', 'vent_uart.log')):
            ts, _, msg = line.partition(' ')
            if msg.startswith('t='):
                d = dict(kv.split('=') for kv in msg.split())
                tel.append((float(ts), int(d['sraw']), int(d['co2']), int(d['tp']) / 10, int(d['st'])))
        io = [(float(r['t']), float(r['green']), float(r['amber']), float(r['red']), float(r['tone_on']))
              for r in csv.DictReader(open(os.path.join(V1, 'sim', 'hil', 'out', 'vent_io.csv')))]
        res = json.load(open(os.path.join(V1, 'sim', 'hil', 'out', 'results.json')))
        _sim = tel, io, res
    return _sim


def sim_clock(t):
    """segment time -> simulated time (s): fast-forward to the vent, then real time
    lined up so the alarm lands on the words 'red light'."""
    S = 'sim'
    lat = sim_data()[2]['vent']['latency_s']
    va = cue(S, 'red') - lat
    if t < va:
        return 300 + 100 * (t / va), round(100 / va, 1)
    return 400 + (t - va), 1.0


def sim(t, D):
    tel, io, res = sim_data()
    st, speed = sim_clock(t)
    T1 = max(st + 8, 340.0)                 # sliding 40 s window
    T0 = T1 - 40
    def gx(s):
        return 320 + (s - T0) / (T1 - T0) * 2000
    panels = [('SGP40 GAS SIGNAL', 1, 21000, 31000, AMBER, '{:.0f}'), ('CO2  ppm', 2, 0, 7500, (170, 200, 230), '{:.0f}'),
              ('PACK  °C', 3, 20, 40, RED, '{:.1f}')]
    PY = [(420, 820), (930, 1330), (1440, 1840)]
    # current outputs
    row = io[min(len(io) - 1, max(0, int(st * 10) - 1))]
    g, am, r, tone = row[1], row[2], row[3], row[4]
    state = 0
    for ts, *v in tel:
        if ts <= st:
            state = v[3]
    cv = Canvas()
    BX, BY, BWD = 3060, 900, 1300           # board image placement
    KD = BWD / 3808
    def bpos(x, y):
        px, py = mm2px(x, y)
        return BX + (px - 1904) * KD, BY + (py - 1064) * KD
    for (x, col, val) in ((138.6, GREEN, g), (142.8, AMBER, am), (147.0, RED, r)):
        if val > 0.02:
            lx, ly = bpos(x, 102.6)
            cv.glow_disk(lx, ly, 40 + 110 * val, col, 0.9 * min(1, val * 2.5))
    cv.composite(glow_radius=30)
    eyebrow(cv, t, 'REAL FIRMWARE  ·  SIMULATED ATMEGA328P  ·  VIRTUAL SENSORS', y=210)
    for (name, idx, lo, hi, col, fmt), (y0, y1) in zip(panels, PY):
        cv.rrect(300, y0, 2340, y1, (28, 24, 19), a=230, radius=18)
        cv.text(340, y0 + 50, name, med(42), SOFTWHITE, anchor='lm')
        pts = [(gx(ts), y1 - 30 - (v[idx - 1] - lo) / (hi - lo) * (y1 - y0 - 110))
               for ts, *v in tel if T0 <= ts <= st and (idx != 2 or v[1] > 0)]
        for p, q in zip(pts, pts[1:]):
            cv.line(p[0], p[1], q[0], q[1], col, width=7)
        if pts:
            cv.disk(pts[-1][0], pts[-1][1], 12, col)
            last = [v for ts, *v in tel if ts <= st][-1][idx - 1]
            cv.text(2300, y0 + 50, fmt.format(last), mono(46), WHITE, anchor='rm')
    # vent marker
    if st >= 400 and T0 <= 400:
        x = gx(400)
        for y in range(420, 1840, 40):
            cv.line(x, y, x, y + 20, WHITE, a=150, width=4)
        cv.text(x - 20, 380, 'VENT', bold(44), WHITE, anchor='rm')
    lat = res['vent']['latency_s']
    if st >= 400 + lat:
        x = gx(400 + lat)
        for y in range(420, 1840, 40):
            cv.line(x, y, x, y + 20, RED, a=200, width=4)
        cv.text(x + 20, 380, f'ALARM +{lat:.1f} s', bold(44), RED, anchor='lm')
    cv.text(gx(T0), 1890, f'{T0:.0f} s', mono(40), SOFTWHITE, anchor='lm')
    cv.text(gx(T1), 1890, f'{T1:.0f} s', mono(40), SOFTWHITE, anchor='rm')
    # board + outputs
    cv.image(img('top.png'), BX, BY, 3808 * KD)
    if tone > 0.4:
        bx, by = bpos(125.0, 106.6)
        for k in range(3):
            ph = (t * 2.2 + k / 3) % 1
            cv.ring(bx, by, 60 + ph * 260, RED, a=int(230 * (1 - ph)), width=8)
    names = {0: ('WARM-UP', SLATE), 1: ('NORMAL', GREEN), 2: ('WARN', AMBER), 3: ('ALARM', RED), 4: ('FAULT', AMBER)}
    sn, sc = names[state]
    chip(cv, BX, 1520, sn, bold(70), (30, 24, 16), bg=sc, pad=36)
    cv.text(BX, 1700, f'sim t = {st:6.1f} s', mono(52), WHITE)
    cv.text(BX, 1790, 'REAL TIME' if speed == 1.0 else f'fast-forward x{speed:.0f}', med(44),
            TEAL if speed == 1.0 else SOFTWHITE, ls=3)
    if tone > 0.4:
        cv.text(BX, 1880, '4 kHz  ·  T3 pattern', med(44), RED)
    return cv.finish()


# ---------------------------------------------------------------- verification
def results():
    drc = open(os.path.join(V1, 'out', 'drc.rpt')).read()
    drc_items = len(re.findall(r'^\[', drc, re.M))
    erc = open(os.path.join(V1, 'out', 'erc.rpt')).read()
    erc_items = len(re.findall(r'^\[', erc, re.M))
    hil = json.load(open(os.path.join(V1, 'sim', 'hil', 'out', 'results.json')))
    n = sum(len(v['checks']) for v in hil.values())
    ok = sum(c['ok'] for v in hil.values() for c in v['checks'])
    sp = json.load(open(os.path.join(V1, 'sim', 'spice', 'results.json')))
    vds = max(r['vds_peak_V'] for r in sp['results'].values())
    return erc_items, drc_items, ok, n, len(hil), vds


def verify(t, D):
    S = 'verify'
    erc, drc, ok, n, ns, vds = results()
    rows = [(cue(S, 'electrical'), 'ERC', f'{erc} violations', erc == 0),
            (cue(S, 'design'), 'DRC', f'{drc} errors  ·  0 warnings  ·  0 unconnected' if drc == 0 else f'{drc} items', drc == 0),
            (cue(S, 'pcb'), 'RULES', "PCBWay 2-layer limits", True),
            (cue(S, '65', default=cue(S, 'hardware')), 'HIL', f'{ok} / {n} checks  ·  {ns} scenarios', ok == n),
            (cue(S, 'spice'), 'SPICE', f'drain clamp {vds:.1f} V on a 5 V rail', vds < 8)]
    cv = Canvas()
    for i, (tc, *_ ) in enumerate(rows):
        a = A(t, tc)
        if a > 0.02:
            cv.glow_disk(640, 560 + i * 270, 80, GREEN, 0.3 * a)
    cv.composite(glow_radius=30)
    eyebrow(cv, t, 'GENERATED FROM CODE  ·  CHECKED ON EVERY BUILD')
    for i, (tc, k, s, good) in enumerate(rows):
        a = A(t, tc)
        if a <= 0.02:
            continue
        y = 560 + i * 270
        ai = int(255 * a)
        cv.disk(640, y, 70, GREEN if good else RED, a=ai)
        (checkmark if good else xmark)(cv, 640, y, 70, (30, 24, 16), a=ai, width=14)
        cv.text(800, y, k, bold(64), WHITE, a=ai, anchor='lm')
        cv.text(1240, y, s, med(58), SOFTWHITE, a=ai, anchor='lm')
    closing(cv, t, cue(S, 'supply') + 0.4, 'every gate fails the build')
    return cv.finish()


def order(t, D):
    S = 'order'
    tup, tpw, tfl, tpl = cue(S, 'upload'), cue(S, 'pcb'), cue(S, 'flash'), cue(S, 'plug')
    tho, tth, tun, tke = cue(S, 'honest'), cue(S, 'that', after=cue(S, 'board')), cue(S, 'until'), cue(S, 'keep')
    fade = 1 - A(t, tho, 0.8)
    cv = Canvas()
    if t >= tpl:
        cv.glow_disk(2620, 980, 420, GREEN, 0.18 * A(t, tpl) * fade)
    cv.composite(glow_radius=60)
    eyebrow(cv, t, 'ORDER ONE')
    files = ['GERBERS  .zip', 'BOM  .csv', 'PLACEMENT  .csv', 'FIRMWARE  .hex']
    for i, f in enumerate(files):
        tc = tup + i * 0.9 if i < 3 else tfl
        a = A(t, tc) * fade
        if a > 0.02:
            y = 620 + i * 210
            chip(cv, 560, y, f, mono(46), WHITE, bg=CHIP_BG, pad=30, a=int(255 * a), border=TEAL if i == 3 else SLATE)
            cv.line(900, y, 1240, 960, SLATE, a=int(255 * a), width=6)
    a = A(t, tpw) * fade
    if a > 0.02:
        cv.rrect(1240, 790, 1760, 1130, CHIP_BG, a=int(255 * a), radius=30, width=7, outline=TEAL, oa=int(255 * a))
        cv.text(1500, 920, 'PCBWAY', bold(70), WHITE, a=int(255 * a), ls=6)
        cv.text(1500, 1030, 'assembled + flashed', med(42), SOFTWHITE, a=int(255 * a))
        arrow(cv, 1780, 960, 1960, 960, SLATE, int(255 * a))
        cv.image(img('hero.png'), 2620, 980, 1500, a=a)
    a = A(t, tpl) * fade
    if a > 0.02:
        arrow(cv, 3240, 960, 3380, 960, SLATE, int(255 * a))
        cv.rrect(3420, 880, 3620, 1040, (200, 194, 182), a=int(255 * a), radius=24)
        cv.rrect(3470, 930, 3570, 990, (40, 36, 30), a=int(255 * a), radius=18)
        cv.text(3520, 1130, 'USB 5 V', bold(46), WHITE, a=int(255 * a), ls=4)
    # the caveat
    a = A(t, tho, 0.8)
    if a > 0.02:
        ai = int(255 * a)
        cv.rrect(560, 560, 1800, 1500, CHIP_BG, a=int(ai * 0.95), radius=34, width=6, outline=GREEN, oa=ai)
        checkmark(cv, 1180, 820, 150, GREEN, a=ai, width=22)
        cv.text(1180, 1060, 'SIMULATED', bold(66), WHITE, a=ai, ls=6)
        cv.text(1180, 1160, 'firmware  ·  circuit  ·  board', med(46), SOFTWHITE, a=ai)
        b = A(t, cue(S, 'real', after=tho))
        if b > 0.02:
            bi = int(255 * b)
            cv.rrect(2040, 560, 3280, 1500, CHIP_BG, a=int(bi * 0.95), radius=34, width=6, outline=AMBER, oa=bi)
            cv.ring(2660, 820, 110, AMBER, a=bi, width=14)
            cv.line(2660, 820, 2660, 745, AMBER, a=bi, width=14)
            cv.line(2660, 820, 2720, 860, AMBER, a=bi, width=14)
            cv.text(2660, 1060, 'REAL VENT TEST', bold(66), WHITE, a=bi, ls=6)
            cv.text(2660, 1160, 'a cell venting beside the board', med(46), SOFTWHITE, a=bi)
            c = A(t, tth)
            if c > 0.02:
                chip(cv, 2660, 1330, 'NEXT', bold(56), (30, 24, 16), bg=AMBER, pad=28, a=int(255 * c))
        u = A(t, tun)
        if u > 0.02:
            chip(cv, 1920, 1720, 'early warning  ·  not a certified alarm', med(54), WHITE, bg=CHIP_BG, pad=32,
                 a=int(255 * u), border=SLATE)
    closing(cv, t, tke, 'keep your smoke alarm', color=AMBER)
    return cv.finish()


def end(t, D):
    return title(t, D, ending=True)


SCENES = {'title': title, 'problem': problem, 'gap': gap, 'turntable': turntable, 'tour': tour,
          'fusion': fusion, 'sim': sim, 'verify': verify, 'order': order, 'end': end}
