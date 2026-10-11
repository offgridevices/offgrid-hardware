"""SmokeBreak screen design: the Arm sequence on a 1.9" 320 x 170 colour IPS.

Every screen is drawn at the panel's real resolution in logical pixels and
scaled by SCALE for review, so what is drawn here is what fits the panel.

    python3 screens.py            # storyboard.png + arm-sequence.mp4 (with beeps)

Screens are numbered S01..S13 so feedback can point at one.
"""
import math
import os
import shutil
import subprocess
import tempfile

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = os.environ.get('SB_FONTS', '/tmp/claude-0/-home-user-offgrid-hardware/'
                       'bb4d9657-83a6-5d9a-b4a3-ba3efc9cb84f/scratchpad/ref')

PW, PH = 320, 170          # panel, pixels
SCALE = 4                  # review scale
FPS = 30

INK = (11, 10, 8)
BONE = (241, 236, 224)
DIM = (120, 114, 104)
EMBER = (255, 106, 0)
GREEN = (76, 175, 80)
RED = (229, 57, 53)
BLUE = (61, 139, 255)


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


class Canvas:
    def __init__(self, bg=INK):
        self.im = Image.new('RGB', (PW * SCALE, PH * SCALE), bg)
        self.d = ImageDraw.Draw(self.im)

    def text(self, x, y, s, size, colour=BONE, kind='sans', anchor='la', weight=500):
        self.d.text((x * SCALE, y * SCALE), s, font=font(kind, size, weight), fill=colour, anchor=anchor)

    def rect(self, x0, y0, x1, y1, colour, width=0, r=0):
        box = [x0 * SCALE, y0 * SCALE, x1 * SCALE, y1 * SCALE]
        if width:
            self.d.rounded_rectangle(box, r * SCALE, outline=colour, width=int(width * SCALE))
        else:
            self.d.rounded_rectangle(box, r * SCALE, fill=colour)

    def line(self, pts, colour, width=1):
        self.d.line([(x * SCALE, y * SCALE) for x, y in pts], fill=colour, width=int(width * SCALE))

    def ring(self, cx, cy, r, w, colour, frac=1.0, node=True):
        """The Beacon Ring, open at 12 o'clock, drawn `frac` of the way round."""
        gap = 24
        a0 = -90 + gap
        a1 = a0 + (360 - 2 * gap) * frac
        box = [(cx - r) * SCALE, (cy - r) * SCALE, (cx + r) * SCALE, (cy + r) * SCALE]
        if frac > 0:
            self.d.arc(box, a0, a1, fill=colour, width=int(w * SCALE))
        if node:
            nr = r * 17 / 58
            self.d.ellipse([(cx - nr) * SCALE, (cy - r - nr * 0.9) * SCALE,
                            (cx + nr) * SCALE, (cy - r + nr * 1.1) * SCALE], fill=colour)

    def stripes(self, y0, y1, colour, phase=0.0):
        """Hazard chevrons across the panel, scrolling with `phase`."""
        step = 14
        off = (phase * step) % step
        for k in range(-2, PW // step + 3):
            x = k * step + off
            self.d.polygon([((x) * SCALE, y1 * SCALE), ((x + 7) * SCALE, y1 * SCALE),
                            ((x + 7 + (y1 - y0)) * SCALE, y0 * SCALE), ((x + (y1 - y0)) * SCALE, y0 * SCALE)],
                           fill=colour)

    def tag(self, s):
        """Screen number in the corner (review only, not on the device)."""
        self.text(PW - 3, PH - 3, s, 7, DIM, 'mono', 'rd')


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3 - 2 * t)


# ------------------------------------------------------------------ screens
# Each takes t in [0, 1] (progress through that screen) and returns a Canvas.

BATT = '16.8 V  4S'
DRONE = 'Drone 3'


def s01_safe(t):
    c = Canvas()
    c.ring(34, 70, 20, 4, lerp(DIM, EMBER, 0.35 + 0.25 * math.sin(t * math.tau)))
    c.text(70, 44, 'SAFE', 38, BONE, 'sans', weight=600)
    c.text(72, 92, 'Drone is off', 12, DIM)
    c.text(12, 128, BATT, 16, BONE, 'mono')
    c.text(12, 150, 'Lift the guard to arm', 11, EMBER)
    c.tag('S01')
    return c


def s02_armed(t):
    c = Canvas()
    c.stripes(0, 12, EMBER, t * 6)
    c.stripes(PH - 12, PH, EMBER, -t * 6)
    c.rect(0, 12, PW, PH - 12, INK)
    pulse = 0.6 + 0.4 * abs(math.sin(t * math.pi * 3))
    c.text(PW / 2, 26, 'ARMED', 44, lerp(INK, EMBER, pulse), 'sans', 'ma', 600)
    c.text(PW / 2, 84, 'Flick the switch up', 14, BONE, anchor='ma')
    c.text(PW / 2, 104, 'to check and power the drone', 11, DIM, anchor='ma')
    c.text(16, 136, BATT, 11, BONE, 'mono')
    c.text(PW - 16, 136, DRONE + ' · 0.42 A last', 10, DIM, 'sans', 'ra')
    c.tag('S02')
    return c


CHECKS = [('3 V probe', 'OK'), ('Short circuit', 'NONE'), ('Polarity', 'OK'),
          ('Capacitor', '1020 µF'), ('Pre-charge', '')]


def checklist(c, done, frac_last=0.0, active_colour=EMBER, dots=True):
    for i, (name, val) in enumerate(CHECKS):
        y = 30 + i * 22
        if i < done:
            c.text(16, y, '■', 9, GREEN, 'mono')
            c.text(32, y - 2, name, 13, BONE)
            c.text(PW - 16, y - 2, val, 12, GREEN, 'mono', 'ra')
        elif i == done:
            blink = int(frac_last * 8) % 2 == 0
            c.text(16, y, '■', 9, active_colour if blink else INK, 'mono')
            c.text(32, y - 2, name, 13, BONE)
            if dots:
                c.text(PW - 16, y - 2, '.' * (1 + int(frac_last * 6) % 4), 12, active_colour, 'mono', 'ra')
        else:
            c.text(32, y - 2, name, 13, (60, 56, 50))


def s03_checking(t):
    c = Canvas()
    c.text(16, 6, 'CHECKING', 13, EMBER, 'mono', weight=600)
    c.text(PW - 16, 6, 'Battery held back', 10, DIM, anchor='ra')
    n = len(CHECKS) - 1
    done = min(n, int(t * n))
    checklist(c, done, (t * n) % 1)
    c.tag('S03')
    return c


def s04_precharge(t):
    c = Canvas()
    c.text(16, 6, 'CHECKING', 13, EMBER, 'mono', weight=600)
    checklist(c, 4, t, dots=False)
    v = 16.8 * ease(t)
    c.rect(32, 140, PW - 16, 156, (40, 36, 30), r=3)
    c.rect(32, 140, 32 + (PW - 48) * ease(t), 156, EMBER, r=3)
    c.text(PW - 16, 116, f'{v:4.1f} V', 12, EMBER, 'mono', 'ra')
    c.tag('S04')
    return c


def s05_engaged(t):
    flash = 1 - ease(t * 1.6)
    c = Canvas(lerp(INK, GREEN, flash))
    c.ring(PW / 2, 64, 34, 6, lerp(GREEN, INK, flash * 0.8), frac=ease(t * 1.4))
    c.text(PW / 2, 116, 'LIVE', 34, lerp(GREEN, INK, flash), 'sans', 'ma', 600)
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
    c.ring(26, 26, 13, 3, GREEN)
    c.text(48, 13, 'LIVE', 16, GREEN, 'sans', weight=600)
    c.text(PW - 16, 16, DRONE, 11, DIM, anchor='ra')
    amps = 0.42 + 0.01 * math.sin(t * 20)
    c.text(14, 46, f'{amps:0.2f}', 64, BONE, 'mono')
    c.text(196, 82, 'A', 26, DIM, 'mono')
    spark(c, 228, 58, 78, 40, t, GREEN)
    c.text(14, 132, BATT, 12, BONE, 'mono')
    c.text(PW - 16, 132, 'Limit AUTO 2.0 A', 11, DIM, anchor='ra')
    c.text(14, 152, 'Same as last time', 11, GREEN)
    c.text(PW - 16, 152, f'0:{int(t * 30):02d}', 11, DIM, 'mono', 'ra')
    c.tag('S06')
    return c


def s07_warning(t):
    c = Canvas()
    c.rect(0, 0, PW, 4, EMBER)
    c.ring(26, 30, 13, 3, EMBER)
    c.text(48, 17, 'LIVE · LOOK', 16, EMBER, 'sans', weight=600)
    c.text(14, 52, 'Draws more than last time', 15, BONE)
    c.text(14, 78, '0.42', 34, DIM, 'mono')
    c.text(110, 86, '→', 22, EMBER, 'mono')
    c.text(146, 78, '0.71 A', 34, EMBER, 'mono')
    c.text(14, 130, 'Often a failing 5 V regulator or VTX.', 11, DIM)
    c.text(14, 148, 'Close the guard to cut power.', 11, BONE)
    c.tag('S07')
    return c


def _abort(t, title, value, line1, line2, tagname):
    on = int(t * 6) % 2 == 0
    c = Canvas(RED if t < 0.08 else INK)
    border = RED if on else (90, 20, 18)
    c.rect(2, 2, PW - 2, PH - 2, border, width=3, r=6)
    c.text(PW / 2, 14, 'ABORT', 40, RED, 'sans', 'ma', 600)
    c.text(PW / 2, 66, title, 18, BONE, 'sans', 'ma', 600)
    c.text(PW / 2, 92, value, 16, RED, 'mono', 'ma')
    c.text(PW / 2, 122, line1, 11, BONE, anchor='ma')
    c.text(PW / 2, 142, line2, 11, DIM, anchor='ma')
    c.tag(tagname)
    return c


def s08_short(t):
    return _abort(t, 'Short circuit', '0.3 Ω', 'The battery never reached the drone.',
                  'Find the short, then close the guard.', 'S08')


def s09_reversed(t):
    return _abort(t, 'Leads reversed', 'RED ↔ BLACK', 'The drone lead is soldered backwards.',
                  'Nothing was powered. Close the guard.', 'S09')


def s10_bind(t):
    c = Canvas()
    step = min(3, 1 + int(t * 3))
    c.ring(PW / 2, 58, 30, 5, BLUE, frac=(t * 3) % 1 if t < 1 else 1)
    c.text(PW / 2, 100, f'BIND  {step}/3', 24, BLUE, 'sans', 'ma', 600)
    c.text(PW / 2, 136, 'Power-cycling the receiver', 11, BONE, anchor='ma')
    c.text(PW / 2, 152, 'Then press Bind in your radio', 10, DIM, anchor='ma')
    c.tag('S10')
    return c


def s11_motor(t):
    c = Canvas()
    c.stripes(0, 10, EMBER, t * 6)
    c.text(PW / 2, 20, '25 A MOTOR TEST', 22, EMBER, 'sans', 'ma', 600)
    c.text(PW / 2, 60, 'Props off?', 30, BONE, 'sans', 'ma', 600)
    c.text(PW / 2, 108, 'Press + again to confirm', 13, BONE, anchor='ma')
    w = (PW - 60) * (1 - t)
    c.rect(30, 140, 30 + w, 146, EMBER, r=3)
    c.text(PW / 2, 152, '3 s', 9, DIM, 'mono', 'ma')
    c.tag('S11')
    return c


def s12_closing(t):
    k = ease(t * 2)
    c = Canvas()
    h = int(PH * (1 - k) / 2)
    c.rect(0, 0, PW, PH, INK)
    c.text(PW / 2, 60, 'POWER CUT', 30, lerp(EMBER, BONE, k), 'sans', 'ma', 600)
    c.text(PW / 2, 104, 'Guard closed · drone off', 12, DIM, anchor='ma')
    c.rect(0, 0, PW, h, (30, 27, 22))
    c.rect(0, PH - h, PW, PH, (30, 27, 22))
    c.tag('S12')
    return c


def s13_limit(t):
    c = Canvas()
    c.text(16, 10, 'LIMIT', 14, DIM, 'mono', weight=600)
    opts = ['AUTO', '1', '2', '5', '10', '25']
    sel = 2
    for i, o in enumerate(opts):
        x = 16 + i * 50
        on = i == sel
        c.rect(x, 50, x + 44, 96, EMBER if on else (40, 36, 30), r=6)
        c.text(x + 22, 62, o, 18 if o != 'AUTO' else 11, INK if on else BONE, 'mono', 'ma', 600)
    c.text(16, 112, '2 A average · 8 A peak cut-off', 12, BONE)
    c.text(16, 136, 'Auto learns each drone. 25 A is for', 11, DIM)
    c.text(16, 152, 'spinning motors with props off.', 11, DIM)
    c.tag('S13')
    return c


SCREENS = [s01_safe, s02_armed, s03_checking, s04_precharge, s05_engaged, s06_live, s07_warning,
           s08_short, s09_reversed, s10_bind, s11_motor, s12_closing, s13_limit]
TITLES = ['Guard closed', 'Guard lifted', 'Switch up: checks', 'Pre-charge', 'Engaged', 'Live',
          'Changed since last time', 'Fault: short', 'Fault: reversed', 'Bind', 'Motor test confirm',
          'Guard closed again', 'Limit']

# the story told by the video: (screen, seconds, sound)
TIMELINE = [(s01_safe, 2.0, None), (s02_armed, 2.2, 'arm'), (s03_checking, 2.4, 'tick'),
            (s04_precharge, 1.4, 'rise'), (s05_engaged, 0.9, 'engage'), (s06_live, 2.6, None),
            (s07_warning, 2.4, 'warn'), (s12_closing, 1.2, 'cut'), (s01_safe, 1.0, None),
            (s02_armed, 1.0, 'arm'), (s03_checking, 0.8, 'tick'), (s08_short, 2.6, 'alarm'),
            (s12_closing, 1.0, 'cut'), (s10_bind, 2.4, 'bind'), (s11_motor, 1.8, 'warn'),
            (s13_limit, 1.8, None)]


def storyboard(out):
    cols, pad = 4, 24
    tw, th = PW * 2, PH * 2
    rows = (len(SCREENS) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * (tw + pad) + pad, rows * (th + 56) + pad), (233, 228, 216))
    d = ImageDraw.Draw(sheet)
    lab = ImageFont.truetype(os.path.join(FONTS, 'InstrumentSans-VariableFont.ttf'), 22)
    for i, (fn, title) in enumerate(zip(SCREENS, TITLES)):
        im = fn(0.55).im.resize((tw, th), Image.LANCZOS)
        x = pad + (i % cols) * (tw + pad)
        y = pad + (i // cols) * (th + 56)
        sheet.paste(im, (x, y + 34))
        d.text((x, y + 4), f'S{i + 1:02d}  {title}', font=lab, fill=(27, 24, 19))
    sheet.save(out)


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
                fn(k / max(frames - 1, 1)).im.save(os.path.join(tmp, f'f{n:05d}.png'))
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
        # the frames, kept for the Blender screen texture
        seq = os.path.join(HERE, 'frames')
        shutil.rmtree(seq, ignore_errors=True)
        os.makedirs(seq)
        for i in range(n):
            if i % 1 == 0:
                Image.open(os.path.join(tmp, f'f{i:05d}.png')).resize((PW * 2, PH * 2), Image.LANCZOS) \
                    .save(os.path.join(seq, f'f{i:05d}.png'))
        return n
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == '__main__':
    storyboard(os.path.join(HERE, 'storyboard.png'))
    print('frames', video(os.path.join(HERE, 'arm-sequence.mp4')))
