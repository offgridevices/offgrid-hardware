"""Blender side of make_video.py: render a scene's frames to OUT/####.png.

    python render.py -- SCENE.blend OUT THREADS [FRAMES]

Several of these can run at once on the same OUT: each claims a frame with
a placeholder file, and frames already on disk are skipped, so a stopped
render picks up where it left off.  FRAMES (e.g. "0,120,240") renders only
those frames.
"""
import bpy, sys

args = sys.argv[sys.argv.index('--') + 1:]
blend, out, threads = args[:3]
only = [int(f) for f in args[3].split(',')] if len(args) > 3 and args[3] else None
bpy.ops.wm.open_mainfile(filepath=blend)
sc = bpy.context.scene
r = sc.render
r.threads_mode = 'FIXED'
r.threads = int(threads)
if only:
    for f in only:
        sc.frame_set(f)
        r.filepath = '%s/%04d.png' % (out.rstrip('/'), f)
        bpy.ops.render.render(write_still=True)
else:
    r.filepath = out.rstrip('/') + '/'
    r.use_overwrite = False
    r.use_placeholder = True
    bpy.ops.render.render(animation=True)
