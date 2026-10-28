# -*- coding: utf-8 -*-
"""Place and route one board, from circuit.py to a DRC-checked .kicad_pcb.
Used by make.py --reroute.

  1. board.build()       parts, net classes, planes and keepouts
  2. prerouted copper    (main) the camera's MIPI lanes and the USB pair as
                         coupled pairs, the plane vias (power.py)
  3. Freerouting 1.9     every other connection; the plane nets are left
                         out (ground; on the main board 0.9 V and 3.3 V)
  4. finish.py           the connections Freerouting leaves: a maze router
                         with rip-up and re-route, plane necks re-opened,
                         dangling stubs taken off
  5. every track corner cut to 45 degrees or less (miter.py)
  6. ground fill and stitching (stitch.py)
  7. KiCad DRC           must be 0 errors / 0 warnings / 0 unconnected

    python3 pipeline.py main|ring|usb WORKDIR
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, board, route, stitch, miter, finish


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
    # route.FR2: Freerouting 2.x when FREEROUTING2 is set (route.py)
    inner = [l for l in pcb.cu_layers() if l not in (pcbnew.F_Cu, pcbnew.B_Cu)]

    # FR_IN3=1: Freerouting may route on In3 too, round the 0.9 V core
    # plane and at three times the cost, through the 3.3 V fill (which pours
    # round its tracks afterwards; the finisher checks the plane is whole)
    in3 = bd == 'main' and os.environ.get('FR_IN3') == '1'

    def planes_only(b):
        # In1 / In4 ground, In3 the 0.9 V / 3.3 V planes: power layers in the
        # copy Freerouting sees, so it routes on F, In2 and B only
        for l in inner:
            if l != pcbnew.In2_Cu and not (in3 and l == pcbnew.In3_Cu):
                b.SetLayerType(l, pcbnew.LT_POWER)
        # the escape band's rule area only scopes a DRC rule; Freerouting
        # would read it as a keepout over the whole band
        for z in list(b.Zones()):
            if z.GetIsRuleArea() and z.GetZoneName() == 'escape band':
                b.Remove(z)
                KEEP.append(z)
        if esc:
            # the escape band's stubs and vias keep 0.126 mm (its own DRC
            # rule); Freerouting knows only the 0.127 mm class clearance and
            # will not start a route from a pad that fixed copper already
            # crowds: in its copy they are a hair smaller (put back below)
            for t in b.GetTracks():
                if t.IsLocked() and t.GetClass() == 'PCB_TRACK' and t.GetWidth() == pcbnew.FromMM(esc['w']):
                    t.SetWidth(pcbnew.FromMM(esc['w'] - SHRINK))
                elif t.IsLocked() and t.GetClass() == 'PCB_VIA' and t.GetWidth(pcbnew.F_Cu) == pcbnew.FromMM(esc['via'][0]):
                    t.SetWidth(pcbnew.FromMM(esc['via'][0] - SHRINK))
        if in3:
            for z in list(b.Zones()):
                if not z.GetIsRuleArea() and z.GetLayerSet().Contains(pcbnew.In3_Cu):
                    b.Remove(z)
                    KEEP.append(z)
            import layout_main
            core = layout_main.plane_polys()['VDD_0V9'].buffer(0.3)
            pcb.rule_area_shape(b, core, [pcbnew.In3_Cu], name='0.9 V plane', tracks=True, vias=False)
    KEEP = []
    esc = getattr(__import__('layout_' + bd), 'ESCAPE', None)
    SHRINK = 0.004
    if in3:
        route.AUTOROUTE = dict(route.AUTOROUTE or {}, layer_costs={'In3.Cu': 3.0})
    route.PRE_EXPORT = planes_only if inner else None
    left = route.route(placed, routed, passes=passes, rounds=4)
    if esc:
        # the session brings the shrunk escape copper back: its real sizes
        b = pcbnew.LoadBoard(routed)
        for t in b.GetTracks():
            if t.GetClass() == 'PCB_TRACK' and t.GetWidth() == pcbnew.FromMM(esc['w'] - SHRINK):
                t.SetWidth(pcbnew.FromMM(esc['w']))
            elif t.GetClass() == 'PCB_VIA' and t.GetWidth(pcbnew.F_Cu) == pcbnew.FromMM(esc['via'][0] - SHRINK):
                t.SetWidth(pcbnew.FromMM(esc['via'][0]))
        pcbnew.SaveBoard(routed, b)
    log('  unrouted after Freerouting: %d' % left)
    log('== finish (maze router, rip-up and re-route)')
    unc, split = finish.finish(routed, log=log)
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
