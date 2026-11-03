"""Render one SmokeBreak concept in the shared studio.

    <venv>/bin/python render_concept.py <concept folder> [--video] [--quick] [--frames N]

Reads <folder>/model.py (def build(s): ...), then writes into the folder:

    hero.png        3/4 view, 1600 x 1000, the concept number and name on it
    top.png         straight-down view (for the face layout)
    turntable.mp4   (--video) a 360 degree turn, numbered, 3 s at 16 fps

--quick renders at a quarter of the samples and half size, for checking a
model while working on it.  --video-only skips the stills.
"""
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bpy           # noqa: E402
import studio as s   # noqa: E402

FONT_MONO = os.path.join(s.FONTS, 'JetBrainsMono-VariableFont.ttf')
FONT_SANS = os.path.join(s.FONTS, 'InstrumentSans-VariableFont.ttf')


def label_of(folder):
    """('07', 'Field clip') from '07-field-clip' and concept.md's title."""
    base = os.path.basename(os.path.normpath(folder))
    num = base.split('-', 1)[0]
    name = base.split('-', 1)[1].replace('-', ' ').title() if '-' in base else base
    md = os.path.join(folder, 'concept.md')
    if os.path.exists(md):
        for line in open(md, encoding='utf-8'):
            m = re.match(r'#+\s*(?:\d+\s*[—:\-–.]?\s*)?(.+)', line.strip())
            if m:
                name = m.group(1).strip().strip('*')
                break
    return num, name[:48]


def overlay(src, dst, num, name, video=False):
    esc = lambda t: t.replace('\\', '\\\\').replace(':', '\\:').replace("'", "’").replace('%', '\\%')
    vf = (f"drawtext=fontfile={FONT_MONO}:text='{esc(num)}':x=56:y=40:fontsize=96:fontcolor=0x1B1813,"
          f"drawtext=fontfile={FONT_SANS}:text='{esc(name)}':x=56:y=150:fontsize=38:fontcolor=0x1B1813,"
          f"drawtext=fontfile={FONT_SANS}:text='SmokeBreak concept':x=w-tw-56:y=h-th-40:fontsize=26:fontcolor=0x6B6459")
    cmd = ['ffmpeg', '-y', '-loglevel', 'error', '-i', src, '-vf', vf]
    if video:
        cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '20']
    cmd.append(dst)
    subprocess.run(cmd, check=True)


def build_scene(model, view, quick, samples=None, percent=100):
    sc = s.reset()
    model.build(s)
    cam, pivot = s.stage(**{k: v for k, v in view.items()
                            if k in ('elevation', 'azimuth', 'lens', 'radius_hint')})
    sc.cycles.samples = 12 if quick else (samples or sc.cycles.samples)
    sc.render.resolution_percentage = 50 if quick else percent
    return sc, cam, pivot


def main():
    args = sys.argv[1:]
    folder = os.path.abspath(args[0])
    video = '--video' in args or '--video-only' in args
    stills = '--video-only' not in args
    quick = '--quick' in args
    frames = int(args[args.index('--frames') + 1]) if '--frames' in args else 48
    num, name = label_of(folder)

    spec = importlib.util.spec_from_file_location('model', os.path.join(folder, 'model.py'))
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    view = getattr(model, 'VIEW', {})

    tmp = tempfile.mkdtemp(prefix='sb-render-')
    try:
        if stills:
            sc, cam, pivot = build_scene(model, view, quick)
            sc.render.filepath = os.path.join(tmp, 'hero.png')
            bpy.ops.render.render(write_still=True)
            overlay(sc.render.filepath, os.path.join(folder, 'hero.png'), num, name)
            # straight-down orthographic view of the face
            lo, hi = s.bounds([o for o in sc.objects if o.name != 'floor'])
            size = max(hi.x - lo.x, hi.y - lo.y)
            cam.constraints.clear()
            cam.parent = None
            cam.data.type = 'ORTHO'
            cam.data.ortho_scale = size * 1.35
            c = (lo + hi) / 2
            cam.location = (c.x, c.y, hi.z + 500)
            cam.rotation_euler = (0, 0, 0)
            sc.cycles.samples = 16
            sc.render.resolution_percentage = 60 if not quick else 50
            sc.render.filepath = os.path.join(tmp, 'top.png')
            bpy.ops.render.render(write_still=True)
            overlay(sc.render.filepath, os.path.join(folder, 'top.png'), num, name + ' (top)')
        if video:
            sc, cam, pivot = build_scene(model, view, quick, samples=12, percent=50)
            s.turntable(pivot, frames=frames)
            sc.render.use_persistent_data = True
            sc.cycles.max_bounces = 4
            sc.cycles.samples = 8
            sc.render.filepath = os.path.join(tmp, 'f_')
            sc.render.image_settings.file_format = 'PNG'
            bpy.ops.render.render(animation=True)
            raw = os.path.join(tmp, 'raw.mp4')
            subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-framerate', '16', '-i',
                            os.path.join(tmp, 'f_%04d.png'), '-c:v', 'libx264', '-pix_fmt', 'yuv420p',
                            '-crf', '18', raw], check=True)
            overlay(raw, os.path.join(folder, 'turntable.mp4'), num, name, video=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps({'concept': num, 'name': name}))


if __name__ == '__main__':
    main()
