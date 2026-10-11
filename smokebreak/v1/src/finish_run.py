"""Finish a Freerouting result: tidy, drop duplicate vias, route what is left
with the maze router (finish.py, on F.Cu, In2 and B.Cu), then rip-up and
re-route for the last few.  python3 finish_run.py ROUTED.kicad_pcb OUT.kicad_pcb
"""
import os
import shutil
import sys

import pcbnew

import board as B
import finish
import make

finish.ROUTE_LAYERS = [pcbnew.F_Cu, pcbnew.In2_Cu, pcbnew.B_Cu]
finish.VIA_D, finish.VIA_DRILL = B.VIA_D, B.VIA_DRILL
finish.POFV_GAP = None
finish.HOLE_TO_HOLE = 0.25


def rules():
    widths, clmap = {}, {}
    for n in make.HV_NETS:
        widths[n], clmap[n] = 0.2, B.HV_CLEAR
    for n in ('PRE_D', 'PRE_K'):
        widths[n], clmap[n] = 0.8, B.HV_CLEAR
    for n in ('+5V', '+3V3'):
        widths[n], clmap[n] = 0.3, B.CLEAR
    return widths, clmap


def copy_project(src, dst):
    for ext in ('.kicad_pro', '.kicad_dru'):
        s = os.path.splitext(src)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(dst)[0] + ext)


def run(src, out, log=print):
    work = os.path.dirname(os.path.abspath(out))
    tmp = os.path.join(work, 'tidy.kicad_pcb')
    shutil.copy(src, tmp)
    copy_project(src, tmp)
    log('tidy', B.tidy_tracks(tmp), 'duplicate vias', B.dedupe_vias(tmp))
    widths, clmap = rules()
    copy_project(src, out)
    n = finish.finish_board(tmp, out, os.path.join(work, 'finish.json'), rules=widths, clmap=clmap)
    log('after the maze router:', n, 'unconnected')
    if n:
        b = pcbnew.LoadBoard(out)
        open_nets = finish.unrouted_nets(b)
        protect = ['GND', 'VIN', 'VOUT', 'DRONE_NEG', 'BATT_NEG', 'SRC']
        left = finish.repair_tx(b, [x for x in open_nets if x not in protect], protect=protect, widths=widths,
                                clmap=clmap, max_victims=8, max_rounds=80, log=log)
        b.Save(out)
        log('after rip-up and re-route:', len(left), 'nets open', left)
    return out


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
