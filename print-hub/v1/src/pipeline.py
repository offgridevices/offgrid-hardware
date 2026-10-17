# -*- coding: utf-8 -*-
"""Place and route the board, from circuit.py to a DRC-clean .kicad_pcb.
Used by make.py --reroute.

  1. board.build()      parts, planes, power copper, a via for every
                        ground and 5 V pad (power.py)
  2. Freerouting 1.9   every other connection; ground and the 5 V rail
                        are left out (they are planes)
  3. ground fill on F.Cu and B.Cu, stitched to the plane
  4. KiCad DRC          must be 0 errors / 0 warnings / 0 unconnected

    python3 pipeline.py WORKDIR
"""
import os, sys, shutil
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, board, route, stitch


def log(s):
    print(s, flush=True)


def run(work, passes=int(os.environ.get('PASSES', 40))):
    os.makedirs(work, exist_ok=True)
    placed = os.path.join(work, 'placed.kicad_pcb')
    routed = os.path.join(work, 'routed.kicad_pcb')
    log('== place')
    board.build(placed)
    log('== route (Freerouting)')
    route.DROP_NETS = ('GND', 'VRAIL')
    # Freerouting 1.9.0: 2.5.0 stalled on this board with 13 connections
    # left (17 Oct 2026), the way 2.x stalled on Ridge 3 Lite
    route.FR2 = None
    # the two inner layers are planes (ground, 5 V): marked as power layers
    # in the copy Freerouting sees, so it routes only on F.Cu and B.Cu
    def planes_only(b):
        for l in (pcbnew.In1_Cu, pcbnew.In2_Cu):
            b.SetLayerType(l, pcbnew.LT_POWER)
    route.PRE_EXPORT = planes_only
    left = route.route(placed, routed, passes=passes, rounds=4)
    log('  unrouted after Freerouting: %d' % left)
    pcb.write_rules(routed)
    log('== ground fill')
    stitch.pour_and_stitch(routed)
    e, w, u = pcb.drc(routed, os.path.join(work, 'drc.json'))
    log('  DRC: %d errors, %d warnings, %d unconnected' % (len(e), len(w), len(u)))
    return routed


if __name__ == '__main__':
    run(sys.argv[1])
