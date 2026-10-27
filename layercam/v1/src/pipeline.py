# -*- coding: utf-8 -*-
"""Place and route one board, from circuit.py to a DRC-checked .kicad_pcb.
Used by make.py --reroute.

  1. board.build()       parts, net classes, planes and keepouts
  2. prerouted copper    (main) the camera's MIPI lanes and the USB pair as
                         coupled pairs, the plane vias (power.py)
  3. Freerouting 1.9     every other connection; the plane nets are left
                         out (ground; on the main board 0.9 V and 3.3 V)
  4. every track corner cut to 45 degrees or less (miter.py)
  5. ground fill and stitching (stitch.py)
  6. KiCad DRC           must be 0 errors / 0 warnings / 0 unconnected

    python3 pipeline.py main|ring|usb WORKDIR
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, board, route, stitch, miter


def log(s):
    print(s, flush=True)


from board import PLANE_NETS


def run(bd, work, passes=int(os.environ.get('PASSES', 40))):
    os.makedirs(work, exist_ok=True)
    placed = os.path.join(work, '%s-placed.kicad_pcb' % bd)
    routed = os.path.join(work, '%s-routed.kicad_pcb' % bd)
    log('== %s: place' % bd)
    board.build(bd, placed)
    pcb.configure(bd)
    log('== route (Freerouting)')
    from board import ROUTER_PLANE_VIAS
    route.DROP_NETS = () if bd in ROUTER_PLANE_VIAS else PLANE_NETS[bd]
    route.FR2 = None
    inner = [l for l in pcb.cu_layers() if l not in (pcbnew.F_Cu, pcbnew.B_Cu)]

    def planes_only(b):
        # In1 / In4 ground, In3 the 0.9 V / 3.3 V planes: power layers in the
        # copy Freerouting sees, so it routes on F, In2 and B only
        for l in inner:
            if l != pcbnew.In2_Cu:
                b.SetLayerType(l, pcbnew.LT_POWER)
    route.PRE_EXPORT = planes_only if inner else None
    left = route.route(placed, routed, passes=passes, rounds=4)
    log('  unrouted after Freerouting: %d' % left)
    log('== 45-degree corners')
    done, failed, left = miter.miter(routed)
    log('  %d corners cut; left at a joint or too tight: %s' % (done, left or 'none'))
    pcb.write_rules(routed)
    log('== ground fill')
    import silk
    n = stitch.pour_and_stitch(routed, art=silk.ART.get(bd, ()))
    log('  %d stitching vias' % n)
    e, w, u = pcb.drc(routed, os.path.join(work, '%s-drc.json' % bd))
    log('  DRC: %d errors, %d warnings, %d unconnected' % (len(e), len(w), len(u)))
    return routed


if __name__ == '__main__':
    run(sys.argv[1], sys.argv[2])
