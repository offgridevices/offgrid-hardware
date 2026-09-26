# -*- coding: utf-8 -*-
"""Place, route and finish one board, from circuit.py to a DRC-clean
.kicad_pcb.  Used by make.py --reroute.

  1. <board>_layout.build()   placement, planes, power copper, plane fan-out,
                              pre-routed critical nets
  2. Freerouting             everything else
  3. finish.finish_board()   in-house maze router for what Freerouting left
  4. finish.repair()         rip-up and re-route for the last few
  5. ESC: POFV hole spacing (pofv.nudge_vias); FC: ground pour on the outer
     layers.  Silkscreen, stray-stub removal.
  6. KiCad DRC               must be 0 errors / 0 warnings / 0 unconnected

Freerouting is not deterministic: two runs give two different, equally
checked boards.
"""
import os, shutil
from collections import Counter
import pcbnew
import pcb, route, finish, artwork, circuit

EXTRA_RULES = ''       # board-specific DRC rules (esc_layout.DRU_EXTRA)


def _copy_project(src_pcb, dst_pcb):
    for ext in ('.kicad_pro',):
        s = os.path.splitext(src_pcb)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(dst_pcb)[0] + ext)
    pcb.write_rules(dst_pcb, EXTRA_RULES)


def run(board_name, work, passes=60, log=print):
    """Returns the path of the finished board in `work`."""
    os.makedirs(work, exist_ok=True)
    if board_name == 'fc':
        import fc_layout as L
        widths = {'VBAT': 0.4, '+5V': 0.4, 'USB_VBUS': 0.4, 'BUCK_SW': 0.4, '+3V3_GYRO': 0.25, 'BUCK_CB': 0.25}
        planes = ['GND', '+3V3']
    else:
        import esc_layout as L
        widths = L.widths(circuit.build('esc'))
        planes = ['GND', 'VBAT']
    clmap = L.clearances(circuit.build('esc')) if board_name == 'esc' else {n: 0.15 for n in widths}
    placed = os.path.join(work, board_name + '.kicad_pcb')
    routed = os.path.join(work, board_name + '_routed.kicad_pcb')
    fin = os.path.join(work, board_name + '_fin.kicad_pcb')
    global EXTRA_RULES
    EXTRA_RULES = getattr(L, 'DRU_EXTRA', '')
    L.build(placed)
    pcb.write_rules(placed, EXTRA_RULES)
    finish.ROUTE_LAYERS = getattr(L, 'ROUTE_LAYERS', [pcbnew.F_Cu, pcbnew.B_Cu])
    if hasattr(L, 'VIA_SIG'):
        finish.VIA_D, finish.VIA_DRILL = L.VIA_SIG
    route.PRE_EXPORT = getattr(L, 'routing_keepouts', None)
    n = route.route(placed, routed, passes=passes, rounds=1 if board_name == 'fc' else 2)
    log('%s: %d connections left after Freerouting, %d duplicate vias removed'
        % (board_name, n, pcb.dedupe_vias(routed)))
    _copy_project(placed, routed); _copy_project(placed, fin)
    n = finish.finish_board(routed, fin, os.path.join(work, board_name + '_fin.json'), rules=widths, clmap=clmap)
    if n:
        b = pcbnew.LoadBoard(fin)
        todo = [x for x in finish.unrouted_nets(b) if x not in planes]
        left = finish.repair(b, todo, protect=planes + list(widths), widths=widths, clmap=clmap, log=log)
        b.Save(fin)
        log('%s: repair left %s' % (board_name, [x for x in left if x not in planes]))
    pcb.tidy_tracks(fin)                 # the maze router's near-duplicate ends and segments
    if board_name == 'fc':
        pcb.pour_ground(fin, [pcbnew.F_Cu, pcbnew.B_Cu])
    else:
        import fanout, pofv
        fanout.drop_unused_escapes(fin)
    artwork.remove_dangling(fin)
    if board_name == 'esc':
        e, w, u = pcb.drc(fin, os.path.join(work, 'esc_pofv_drc.json'))
        if any(v['type'] == 'hole_to_hole' for v in e):
            pofv.nudge_vias(fin, os.path.join(work, 'esc_pofv_drc.json'), clearances=clmap, log=log)
    b = pcbnew.LoadBoard(fin)
    if board_name == 'fc':
        L.artwork(b)
    else:
        L.artwork(b, circuit.build('esc'))
    b.Save(fin)
    pcb.set_stackup(fin)
    e, w, u = pcb.drc(fin, os.path.join(work, board_name + '_final_drc.json'))
    log('%s DRC: %d errors %s, %d warnings %s, %d unconnected'
        % (board_name, len(e), dict(Counter(v['type'] for v in e)), len(w),
           dict(Counter(v['type'] for v in w)), len(u)))
    if e or w or u:
        raise SystemExit('%s: DRC not clean, see %s_final_drc.json' % (board_name, board_name))
    return fin
