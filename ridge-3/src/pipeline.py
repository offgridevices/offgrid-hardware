# -*- coding: utf-8 -*-
"""Place, route and finish one board, from circuit.py to a DRC-clean
.kicad_pcb.  Used by make.py --reroute.

  1. <board>_layout.build()   placement, planes, power copper, plane fan-out,
                              pre-routed critical nets (ESC: gate, bootstrap
                              and QFN escape vias)
  2. Freerouting             everything else (ESC: two rounds, tidied between)
  3. finish.finish_board()   in-house maze router for what Freerouting left
  4. rip-up and re-route for the last few: finish.repair (FC),
     finish.repair_tx then finish.repair_orders (ESC)
  5. FC: ground pour on the outer layers, stray stubs removed.
     ESC: cleanup.clean (unused escape vias and stubs, each removal kept only
     if DRC agrees), POFV hole spacing (pofv.nudge_vias).  Silkscreen.
  6. KiCad DRC               must be 0 errors / 0 warnings / 0 unconnected

Freerouting is deterministic for a given board file, but a fresh build
gives every item a new ID, and with it a new order, so a fresh run routes
differently from the committed boards (the reference) and is checked by the
same gates.
"""
import os, shutil
from collections import Counter
import pcbnew
import pcb, route, finish, artwork, circuit, cleanup

EXTRA_RULES = ''       # board-specific DRC rules (esc_layout.DRU_EXTRA)
# KiCad gives every new item a random ID, and the order items reach
# Freerouting follows those IDs.  A fixed seed per board makes the IDs, and
# so the routing, the same on every run (with PYTHONHASHSEED=0, see make.py).
SEEDS = {'fc': 3, 'esc': 3}


def _copy_project(src_pcb, dst_pcb):
    for ext in ('.kicad_pro',):
        s = os.path.splitext(src_pcb)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(dst_pcb)[0] + ext)
    pcb.write_rules(dst_pcb, EXTRA_RULES)


def run(board_name, work, passes=None, log=print):
    """Returns the path of the finished board in `work`."""
    os.makedirs(work, exist_ok=True)
    pcbnew.KIID.SeedGenerator(int(os.environ.get('PIPELINE_SEED', SEEDS[board_name])))
    passes = passes or (15 if board_name == 'esc' else 60)      # Freerouting passes per round
    if board_name == 'fc':
        import fc_layout as L
        planes = ['GND', '+3V3']
    else:
        import esc_layout as L
        planes = ['GND', 'VBAT']
    widths = L.widths(circuit.build(board_name))
    clmap = L.clearances(circuit.build(board_name))
    placed = os.path.join(work, board_name + '.kicad_pcb')
    routed = os.path.join(work, board_name + '_routed.kicad_pcb')
    fin = os.path.join(work, board_name + '_fin.kicad_pcb')
    global EXTRA_RULES
    EXTRA_RULES = getattr(L, 'DRU_EXTRA', '')
    L.build(placed)
    pcb.write_rules(placed, EXTRA_RULES)
    finish.ROUTE_LAYERS = getattr(L, 'ROUTE_LAYERS', [pcbnew.F_Cu, pcbnew.B_Cu])
    finish.RES = getattr(L, 'FINISH_RES', 0.05)
    if hasattr(L, 'VIA_SIG'):
        finish.VIA_D, finish.VIA_DRILL = L.VIA_SIG
    route.PRE_EXPORT = getattr(L, 'routing_keepouts', None)
    route.VIA_IN_PAD = getattr(L, 'VIA_IN_PAD', None)
    route.VIA_RING = getattr(L, 'VIA_RING', None)
    finish.VIA_RING = getattr(L, 'VIA_RING', None) or 0.0
    n = route.route(placed, routed, passes=passes, rounds=2)
    log('%s: %d connections left after Freerouting, %d duplicate vias removed'
        % (board_name, n, pcb.dedupe_vias(routed)))
    _copy_project(placed, routed); _copy_project(placed, fin)
    finish.POFV_GAP = None               # every via is filled (POFV): via to via is the normal rule
    n = finish.finish_board(routed, fin, os.path.join(work, board_name + '_fin.json'), rules=widths, clmap=clmap)
    _copy_project(placed, fin)
    if board_name == 'fc':
        pcb.tidy_tracks(fin)             # the maze router's near-duplicate ends and segments
        protect = planes + list(widths)
    else:
        protect = planes + ['+3V3', 'BUCK_LX', 'GVDD']
    # rip-up and re-route for anything the routers left, then the
    # order-varying repair for the last few.  Both are transactions: an
    # attempt that leaves any net with more islands than before is undone.
    b = pcbnew.LoadBoard(fin)
    todo = [x for x in finish.unrouted_nets(b) if x not in planes]
    if todo:
        finish.repair_tx(b, todo, protect=protect, widths=widths, clmap=clmap, max_victims=14,
                         max_rounds=80, log=log)
        b.Save(fin)
        _copy_project(placed, fin)
    pcb.tidy_tracks(fin)
    b = pcbnew.LoadBoard(fin)
    left = [x for x in finish.unrouted_nets(b) if x not in planes]
    if left:
        left = finish.repair_orders(b, left, protect=protect, widths=widths, clmap=clmap, log=log)
        b.Save(fin)
        _copy_project(placed, fin)
    log('%s: left after repair %s' % (board_name, left))
    pcb.tidy_tracks(fin)
    if board_name == 'fc':
        pcb.pour_ground(fin, [pcbnew.F_Cu, pcbnew.B_Cu])
        artwork.remove_dangling(fin)
    else:
        import pofv
        cleanup.clean(fin, EXTRA_RULES, log=log)
        e, w, u = pcb.drc(fin, os.path.join(work, 'esc_pofv_drc.json'))
        if any(v['type'] == 'hole_to_hole' for v in e):
            pofv.nudge_vias(fin, os.path.join(work, 'esc_pofv_drc.json'), clearances=clmap, log=log)
    if os.environ.get('NO_ARTWORK') == '1':
        pcb.set_stackup(fin, getattr(L, 'INNER_OZ', 0.5))
        e, w, u = pcb.drc(fin, os.path.join(work, board_name + '_final_drc.json'))
        log('%s DRC (no artwork): %d errors %s, %d warnings %s, %d unconnected'
            % (board_name, len(e), dict(Counter(v['type'] for v in e)), len(w),
               dict(Counter(v['type'] for v in w)), len(u)))
        return fin
    b = pcbnew.LoadBoard(fin)
    if board_name == 'fc':
        L.artwork(b)
    else:
        L.artwork(b, circuit.build('esc'))
    b.Save(fin)
    pcb.set_stackup(fin, getattr(L, 'INNER_OZ', 0.5))
    e, w, u = pcb.drc(fin, os.path.join(work, board_name + '_final_drc.json'))
    log('%s DRC: %d errors %s, %d warnings %s, %d unconnected'
        % (board_name, len(e), dict(Counter(v['type'] for v in e)), len(w),
           dict(Counter(v['type'] for v in w)), len(u)))
    if e or w or u:
        raise SystemExit('%s: DRC not clean, see %s_final_drc.json' % (board_name, board_name))
    return fin
