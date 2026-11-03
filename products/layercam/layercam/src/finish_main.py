# -*- coding: utf-8 -*-
"""The pipeline's tail on a board Freerouting has already routed: finish
(finish.py), 45-degree corners (miter.py), rules, ground fill and
stitching (stitch.py), KiCad DRC.  For working on the finisher without
waiting for Freerouting.

    python3 finish_main.py ROUTED.kicad_pcb OUT.kicad_pcb [main|ring|usb]

ROUTED is copied (with its .kicad_pro: DRC needs the project beside the
board) and left as it is.
"""
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcb


def copy_board(src, dst):
    shutil.copy(src, dst)
    s, d = os.path.splitext(src)[0], os.path.splitext(dst)[0]
    if src.endswith('.best'):
        s = os.path.splitext(s)[0]
    for ext in ('.kicad_pro', '.kicad_dru'):
        if os.path.exists(s + ext):
            shutil.copy(s + ext, d + ext)


def tail(path, bd, log=print):
    """finish -> miter -> rules -> fill and stitch -> DRC, in place.
    Returns (errors, warnings, unconnected, sharp corners)."""
    import finish, miter, stitch, silk
    t0 = time.time()
    log('== finish (maze router)')
    finish.finish(path, log=log)
    log('== 45-degree corners')
    done, failed, left = miter.miter(path)
    log('  %d corners cut; left at a joint or too tight: %s' % (done, left or 'none'))
    pcb.write_rules(path)
    log('== ground fill')
    n = stitch.pour_and_stitch(path, art=silk.ART.get(bd, ()))
    log('  %d stitching vias' % n)
    e, w, u = pcb.drc(path, os.path.splitext(path)[0] + '-drc.json')
    log('  DRC: %d errors, %d warnings, %d unconnected' % (len(e), len(w), len(u)))
    for v in e + w:
        log('   %s %s %s' % (v['severity'], v['type'], [i['description'][:60] for i in v['items']]))
    for it in u:
        log('   unconnected %s' % [i['description'][:60] for i in it['items']])
    sharp = [c for c in miter.corners(path) if c[0] > miter.LIMIT]
    log('  corners over 45 degrees: %d %s' % (len(sharp), [(round(a), n_, x, y) for a, n_, _, x, y in sharp][:8]))
    log('  tail: %.0f s' % (time.time() - t0))
    return e, w, u, sharp


if __name__ == '__main__':
    src, out = sys.argv[1], sys.argv[2]
    bd = sys.argv[3] if len(sys.argv) > 3 else 'main'
    pcb.configure(bd)
    copy_board(src, out)
    tail(out, bd, log=lambda *a: print(*a, flush=True))
