#!/usr/bin/env python3
"""Exploded-view video of a board, made straight from its KiCad file.

    python3 video/make_video.py fc                  # draft, 720p
    python3 video/make_video.py fc --final          # 1080p, into fc/images/
    python3 video/make_video.py fc --stills 0,200   # a few labelled stills
    python3 video/make_video.py path/to/x.kicad_pcb --config x.json

Run it with the Python that has KiCad's pcbnew (kicad-cli on PATH).  The
first run makes video/.venv (Python 3.11 and Blender as a module) from
video/requirements.txt; set VIDEO_PYTHON to use another Python 3.11.

What it does, every step from the board file (so a changed board or a new
one needs no other work):
  1. kicad-cli exports the board as GLB: parts, copper, mask, silkscreen.
  2. The board's facts come from its file: the copper layers and the FR-4
     between them (stackup), what each copper layer carries (a layer mostly
     covered by one net's zone and nearly free of tracks is that net's
     plane), and the parts on each side.  These make the layer labels.
  3. scene.py (Blender) takes the board apart into its layers, stands it on
     its edge, opens it sideways across the 16:9 frame, holds, closes and
     lays it down; the camera shots are fitted to what is in view.
  4. render.py renders the frames in parallel, resuming where it stopped.
  5. overlay.py adds the labels and the title and writes the MP4.

The board's own settings are a small JSON beside this file (fc.json,
esc.json): the title, a few words on the main parts of each side, and
optionally any label, role, timing, camera or light to override, and
"music": an audio file under the video (see video/music/README.md).
"""
import argparse, collections, hashlib, json, os, re, shutil, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
VENV = os.path.join(HERE, '.venv')
VPY = os.path.join(VENV, 'bin', 'python')
BOARDS = {'fc': 'fc/ridge3-fc.kicad_pcb', 'esc': 'esc/ridge3-esc.kicad_pcb'}
QUALITY = {'draft': dict(resolution=[1280, 720], samples=12, noise_threshold=0.05),
           'final': dict(resolution=[1920, 1080], samples=24, noise_threshold=0.03)}
DEFAULTS = {
    'fps': 24,
    'look': 'AgX - Medium High Contrast',
    'font': os.path.join(V1, 'fonts', 'InstrumentSans-VariableFont.ttf'),
    # space between neighbouring layers when open, in board widths
    'gaps': {'components': 0.8, 'copper': 0.7, 'other': 0.5},
    'via_thin': 0.6,
    'camera': {'lens': 85, 'fstop': 8,
               # where the board must sit in the frame (x0, x1, y0, y1)
               'frame': {'flat': [0.22, 0.78, 0.18, 0.82], 'standing': [0.3, 0.7, 0.2, 0.8],
                         'open': [0.04, 0.96, 0.28, 0.72]}},
    'world': {'hdri': 'studio.exr', 'hdri_rotation': 120, 'hdri_strength': 0.8,
              'centre': [0.030, 0.032, 0.036], 'edge': [0.002, 0.002, 0.003]},
    # for a 36 mm board; scene.py scales them with the board
    'lights': [{'name': 'key', 'loc': [-35, -25, 40], 'size': 30, 'energy': 26000, 'color': [1.0, 0.97, 0.92]},
               {'name': 'fill', 'loc': [30, -30, 15], 'size': 25, 'energy': 6000, 'color': [0.95, 0.97, 1.0]},
               {'name': 'back', 'loc': [-10, 40, 50], 'size': 20, 'energy': 15000, 'color': [0.80, 0.88, 1.0]}],
    'sheen': {'distance': 45, 'size': 45, 'energy': 30000},
    'sweep': {'from': [-30, 35, 18], 'to': [35, 25, 18], 'size': 1.5, 'size_y': 60, 'energy': 7000,
              'f0': 0, 'f1': 110},
    'overlay': {'above': 0.2, 'below': 0.8, 'step': 4, 'fade': 12, 'fade_out': 14, 'title_fade': 20,
                'title_at': [0.075, 0.82]},
    'mask': {'top': 'gold pads show through'},
    'silkscreen': {'top': 'labels and markings'},
}


def run(cmd, **kw):
    print('  $', ' '.join(os.path.basename(c) if i == 0 else c for i, c in enumerate(cmd))[:200], flush=True)
    subprocess.run(cmd, check=True, **kw)


def merge(a, b):
    """b over a, dicts merged key by key."""
    out = dict(a)
    for k, v in b.items():
        out[k] = merge(a[k], v) if isinstance(v, dict) and isinstance(a.get(k), dict) else v
    return out


# ------------------------------------------------------------ the board
def human(net):
    net = net.lstrip('+')
    names = {'GND': 'ground', 'VBAT': 'battery'}
    if net in names:
        return names[net]
    m = re.fullmatch(r'(\d+)V(\d+)', net) or re.fullmatch(r'(\d+)V', net)
    if m:
        return '%s V' % '.'.join(m.groups())
    return net


def board_facts(path):
    """Copper layers (top first), the dielectric under each, what each layer
    carries, and the assembled parts on each side."""
    import pcbnew
    b = pcbnew.LoadBoard(path)
    layers = list(b.GetEnabledLayers().CuStack())
    copper = [b.GetLayerName(l) for l in layers]
    # the stackup as the file has it, top to bottom
    text = open(path).read()
    stack = text[text.index('(stackup'):]
    under, last = {}, None
    for m in re.finditer(r'\(layer "([^"]+)"\s*\(type "([^"]+)"\)(.*?)\n\t*\)', stack, re.S):
        name, typ, body = m.groups()
        if typ == 'copper':
            last = name
        elif last and typ in ('core', 'prepreg') and last not in under:
            t = re.search(r'\(thickness ([\d.]+)', body)
            under[last] = dict(type=typ, t=float(t.group(1)) if t else None)
    # what each copper layer carries
    poly = pcbnew.SHAPE_POLY_SET()
    b.GetBoardPolygonOutlines(poly, True)
    area = poly.Area()
    cover = collections.defaultdict(collections.Counter)
    for z in b.Zones():
        if z.GetIsRuleArea():
            continue
        for l in z.GetLayerSet().Seq():
            if pcbnew.IsCopperLayer(l):
                fp = z.GetFilledPolysList(l)
                cover[l][z.GetNetname()] += fp.Area() / area if fp else 0
    tracks = collections.Counter()
    for t in b.GetTracks():
        if t.Type() == pcbnew.PCB_TRACE_T:
            tracks[t.GetLayer()] += t.GetLength() / 1e6
    roles = {}
    for l, name in zip(layers, copper):
        net, frac = cover[l].most_common(1)[0] if cover[l] else ('', 0)
        if frac >= 0.5 and tracks[l] < 20:
            roles[name] = '%s plane' % human(net)
        elif frac >= 0.3:
            roles[name] = 'signals and %s' % human(net)
        elif sum(cover[l].values()) >= 0.25:
            roles[name] = 'signals and power'
        else:
            roles[name] = 'signals'
    skip = pcbnew.FP_EXCLUDE_FROM_POS_FILES | pcbnew.FP_BOARD_ONLY
    parts = {'top': 0, 'bottom': 0}
    for fp in b.GetFootprints():
        if not (fp.GetAttributes() & skip) and not fp.IsDNP():
            parts['bottom' if fp.IsFlipped() else 'top'] += 1
    return dict(copper=copper, dielectric_under=under, roles=roles, parts=parts)


def labels(facts, cfg):
    """{layer group: [title, detail]} from the board's facts and settings."""
    hl = cfg.get('highlights', {})
    out = {}
    for side in ('top', 'bottom'):
        n = facts['parts'][side]
        if n:
            out['components ' + side] = ['%s side' % side.capitalize(),
                                         '%d parts%s' % (n, ': ' + hl[side] if hl.get(side) else '')]
        out['silkscreen ' + side] = ['Silkscreen', cfg['silkscreen'].get(side, '')]
        out['mask ' + side] = ['Solder mask', cfg['mask'].get(side, '')]
    for i, name in enumerate(facts['copper']):
        role = cfg.get('roles', {}).get(name) or facts['roles'][name]
        di = facts['dielectric_under'].get(name)
        if di and name != facts['copper'][-1]:
            role += ', on %g mm %s' % (di['t'], di['type'])
        out[name] = ['Copper %d' % (i + 1), role]
    out.update(cfg.get('labels', {}))
    return out


def timeline(n, o):
    """Frame numbers for n layer groups: stand up, open, hold, close, lie
    down, the closing shot."""
    maxr = (n - 1) / 2
    t = dict(stagger=o.get('stagger', 3), move=o.get('move', 84))
    t['stand'] = o.get('stand', [54, 114])
    t['open'] = o.get('open', t['stand'][1] - 6)
    t['open_end'] = t['open'] + round(maxr * t['stagger']) + t['move']
    t['close'] = t['open_end'] + o.get('hold', 132)
    close_end = t['close'] + round(maxr * t['stagger']) + t['move']
    t['lay'] = [close_end - 18, close_end + 48]
    t['end'] = t['lay'][1] + o.get('tail', 84)
    return t


def shots(t):
    """[frame, azimuth, elevation, what is framed, distance factor]: the
    camera's key positions (azimuth 0 = from the front, negative = from the
    left, where the standing board's top side faces)."""
    return [[0, -34, 30, 'flat', 1.1], [t['stand'][0], -26, 27, 'flat', 1.0],
            [t['open'], -44, 14, 'standing', 1.0], [t['open_end'], -40, 12, 'open', 1.0],
            [t['close'], -33, 14, 'open', 0.96], [t['lay'][0], -34, 18, 'standing', 1.0],
            [t['lay'][1], -28, 28, 'flat', 1.0], [t['end'], -20, 30, 'flat', 0.94]]


# -------------------------------------------------------------- steps
def ensure_venv():
    if not os.path.exists(VPY):
        run([os.environ.get('VIDEO_PYTHON', 'python3.11'), '-m', 'venv', VENV])
        run([VPY, '-m', 'pip', 'install', '-q', '-r', os.path.join(HERE, 'requirements.txt')])


def export_glb(pcb, glb):
    if os.path.exists(glb) and os.path.getmtime(glb) >= os.path.getmtime(pcb):
        return
    run(['kicad-cli', 'pcb', 'export', 'glb', '--force', '-o', glb, '--include-tracks', '--include-pads',
         '--include-zones', '--include-inner-copper', '--include-silkscreen', '--include-soldermask', pcb],
        stdout=subprocess.DEVNULL)


def blender(script, *args):
    run([VPY, os.path.join(HERE, script), '--', *args], stdout=subprocess.DEVNULL)


def render_all(blend, frames, n_frames, jobs):
    for f in os.listdir(frames):              # placeholders of a stopped run
        p = os.path.join(frames, f)
        if f.endswith('.png') and not os.path.getsize(p):
            os.remove(p)
    threads = max(1, (os.cpu_count() or 4) // jobs)
    procs = [subprocess.Popen([VPY, os.path.join(HERE, 'render.py'), '--', blend, frames, str(threads)],
                              stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) for _ in range(jobs)]
    for p in procs:
        p.wait()
    done = [f for f in os.listdir(frames) if f.endswith('.png') and os.path.getsize(os.path.join(frames, f))]
    if len(done) != n_frames:
        raise SystemExit('render stopped with %d of %d frames; run again to resume' % (len(done), n_frames))


def add_music(mp4, music, seconds, gain_db=0.0):
    """The music under the video: a short fade in, a fade out over the last
    second, 1 dB of headroom (plus gain_db), cut or padded to the video."""
    ff = subprocess.run([VPY, '-c', 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())'],
                        capture_output=True, text=True, check=True).stdout.strip()
    af = 'volume=%gdB,afade=t=in:st=0:d=0.6,afade=t=out:st=%.3f:d=1.0,apad' % (gain_db - 1.0, max(0.0, seconds - 1.0))
    tmp = mp4[:-4] + '.music.mp4'
    run([ff, '-y', '-loglevel', 'error', '-i', mp4, '-i', music, '-filter_complex', '[1:a]%s[a]' % af,
         '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '256k', '-t', '%.3f' % seconds,
         '-movflags', '+faststart', tmp])
    os.replace(tmp, mp4)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('board', help='fc, esc, or a .kicad_pcb file')
    ap.add_argument('--config', help='the board\'s settings (default: video/<board>.json)')
    ap.add_argument('--final', action='store_true', help='1080p, more samples, saved beside the board')
    ap.add_argument('--stills', help='only these frames, labelled (e.g. 0,200,300)')
    ap.add_argument('--jobs', type=int, default=2, help='renders at once')
    ap.add_argument('--out', help='the MP4 (default: see --final)')
    ap.add_argument('--music', help='an audio file under the video (default: the board settings\' "music")')
    a = ap.parse_args()
    pcb = os.path.join(V1, BOARDS[a.board]) if a.board in BOARDS else os.path.abspath(a.board)
    name = os.path.splitext(os.path.basename(pcb))[0]
    key = a.board if a.board in BOARDS else name
    cfg_path = a.config or os.path.join(HERE, key + '.json')
    cfg = merge(DEFAULTS, json.load(open(cfg_path)) if os.path.exists(cfg_path) else {})
    quality = 'final' if a.final else 'draft'
    work = os.path.join(HERE, 'out', key)
    os.makedirs(work, exist_ok=True)

    print('== %s (%s)' % (name, quality))
    ensure_venv()
    glb = os.path.join(work, name + '.glb')
    export_glb(pcb, glb)
    facts = board_facts(pcb)
    n = sum(1 for side in ('top', 'bottom') if facts['parts'][side]) + 4 + len(facts['copper'])
    tl = timeline(n, cfg.get('timeline', {}))
    spec = merge(cfg, dict(copper=facts['copper'], labels=labels(facts, cfg), timeline=tl,
                           quality=merge(QUALITY[quality], cfg.get('quality', {})),
                           title=cfg.get('title', [name, ''])))
    spec['camera']['shots'] = cfg['camera'].get('shots') or shots(tl)
    spec['overlay'] = merge(cfg['overlay'], {'in': tl['open_end'] - 12, 'out': tl['close'] - 16,
                                             'title_in': tl['lay'][1] + 6})
    spec_path = os.path.join(work, 'spec-%s.json' % quality)
    json.dump(spec, open(spec_path, 'w'), indent=1)
    print('  %d copper layers; %s; parts %s' % (len(facts['copper']),
                                                 ', '.join('%s %s' % kv for kv in facts['roles'].items()),
                                                 facts['parts']))
    blend = os.path.join(work, 'scene-%s.blend' % quality)
    anchors = os.path.join(work, 'anchors-%s.json' % quality)
    blender('scene.py', glb, spec_path, blend, anchors)

    if a.stills:
        stills = os.path.join(work, 'stills')
        shutil.rmtree(stills, ignore_errors=True)
        os.makedirs(stills)
        blender('render.py', blend, stills, str(os.cpu_count() or 4), a.stills)
        run([VPY, os.path.join(HERE, 'overlay.py'), spec_path, anchors, stills, stills + '-labelled'])
        print('stills in', os.path.relpath(stills + '-labelled', os.getcwd()))
        return

    # frames are kept while the board and the spec (but for the music) stay the same
    frames = os.path.join(work, 'frames-' + quality)
    looks = {k: v for k, v in spec.items() if not k.startswith('music')}
    stamp = hashlib.sha1(json.dumps(looks, indent=1).encode() + open(glb, 'rb').read()).hexdigest()
    stamp_file = os.path.join(frames, 'STAMP')
    if os.path.exists(frames) and (not os.path.exists(stamp_file) or open(stamp_file).read() != stamp):
        shutil.rmtree(frames)
    os.makedirs(frames, exist_ok=True)
    open(stamp_file, 'w').write(stamp)
    render_all(blend, frames, tl['end'] + 1, a.jobs)
    if a.out:
        mp4 = os.path.abspath(a.out)
    elif a.final:
        mp4 = os.path.join(os.path.dirname(pcb), 'images', name + '-explode.mp4')
    else:
        mp4 = os.path.join(work, name + '-explode-draft.mp4')
    os.makedirs(os.path.dirname(mp4), exist_ok=True)
    run([VPY, os.path.join(HERE, 'overlay.py'), spec_path, anchors, frames, frames + '-labelled', mp4])
    music = a.music or cfg.get('music')
    if music:
        music = music if os.path.isabs(music) else os.path.join(HERE, music)
        if os.path.exists(music):
            add_music(mp4, music, (tl['end'] + 1) / spec['fps'], cfg.get('music_gain_db', 0.0))
            print('  music:', os.path.relpath(music, HERE))
        else:
            print('  no music: %s is not here (licensed tracks are not in the repo, see video/music/README.md)'
                  % os.path.relpath(music, HERE))
    print('video:', os.path.relpath(mp4, os.getcwd()))


if __name__ == '__main__':
    main()
