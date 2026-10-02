# -*- coding: utf-8 -*-
"""Place, route and finish one board, from circuit.py to a DRC-clean
.kicad_pcb.  Used by make.py --reroute.

  1. <board>_layout.build()   placement, planes, power copper, plane fan-out,
                              pre-routed critical nets (ESC: gate, bootstrap
                              and QFN escape vias)
  2. ESC: one channel routed alone by Freerouting and stamped, turned, onto
     the other three (stamp.py)
     Freerouting             everything else (ESC: two rounds, tidied between)
  3. finish.finish_board()   in-house maze router for what Freerouting left
  4. rip-up and re-route for the last few: finish.repair_tx, then
     finish.repair_orders.  FC: if nets are still open, steps 2-4 again
     under other Freerouting costs, in parallel (WHOLE_VARIANTS)
  5. FC: ground pour on the outer layers, stray stubs removed.
     ESC: cleanup.clean (unused escape vias and stubs, each removal kept only
     if DRC agrees), POFV hole spacing (pofv.nudge_vias).  Silkscreen.
  6. KiCad DRC               must be 0 errors / 0 warnings / 0 unconnected

Freerouting is deterministic for a given board file, but a fresh build
gives every item a new ID, and with it a new order, so a fresh run routes
differently from the committed boards (the reference) and is checked by the
same gates.
"""
import os, sys, json, shutil, subprocess
from collections import Counter
import pcbnew
import pcb, route, finish, artwork, circuit, cleanup

EXTRA_RULES = ''       # board-specific DRC rules (esc_layout.DRU_EXTRA, the inner copper's fab limits)
# KiCad gives every new item a random ID, and the order items reach
# Freerouting follows those IDs.  A fixed seed per board makes the IDs, and
# so the routing, the same on every run (with PYTHONHASHSEED=0, see make.py).
SEEDS = {'fc': 3, 'esc': 3}

# A board routed whole (no channel template: the FC) gets Freerouting's own
# default costs first, the routing it has always had.  If the finisher and
# the repairs still leave nets open after that, the whole stage is run
# again under each of these costs, all at once, each in a process of its
# own, and the routing that ends with the fewest nets open is kept (the
# first of equals), so the result is the same on every run.  Freerouting is
# deterministic for a given input, and different costs give genuinely
# different routings (route.AUTOROUTE); which of them the repairs can
# finish shows only by trying.
WHOLE_VARIANTS = [dict(via_costs=30), dict(via_costs=70), dict(via_costs=50, start_ripup_costs=50)]


def _copy_project(src_pcb, dst_pcb):
    for ext in ('.kicad_pro',):
        s = os.path.splitext(src_pcb)[0] + ext
        if os.path.exists(s):
            shutil.copy(s, os.path.splitext(dst_pcb)[0] + ext)
    pcb.write_rules(dst_pcb, EXTRA_RULES)


def setup_routers(L):
    """Module settings of the routers for one board's layout module."""
    finish.ROUTE_LAYERS = getattr(L, 'ROUTE_LAYERS', [pcbnew.F_Cu, pcbnew.B_Cu])
    finish.RES = getattr(L, 'FINISH_RES', 0.05)
    if hasattr(L, 'VIA_SIG'):
        finish.VIA_D, finish.VIA_DRILL = L.VIA_SIG
    finish.VIA_RING = getattr(L, 'VIA_RING', None) or 0.0
    finish.POFV_GAP = None               # every via is filled (POFV): via to via is the normal rule
    route.PRE_EXPORT = getattr(L, 'dsn_keepouts', None) or getattr(L, 'routing_keepouts', None)
    route.VIA_IN_PAD = getattr(L, 'VIA_IN_PAD', None)
    route.VIA_RING = getattr(L, 'VIA_RING', None)


def template_repair(b, open_nets, mine, widths, clmap, log=print, deep=False):
    """The maze router's rip-up and re-route on stamp.py's template channel:
    only the channel's own nets move (a temporary net X~ takes X's rules),
    and fixed copper stays.  deep: a second, longer go at a routing the
    first left nearly finished: random orders only, with more of them,
    two passes, and up to 16 nets torn up round each open one."""
    w = dict(widths, **{n + '~': x for n, x in widths.items()})
    c = dict(clmap, **{n + '~': x for n, x in clmap.items()})
    nets = set(p.GetNetname() for fp in b.GetFootprints() for p in fp.Pads() if p.GetNetname())
    pcbnew.ZONE_FILLER(b).Fill(b.Zones())
    protect = sorted(nets - set(mine))
    if deep:
        return finish.repair_orders(b, list(open_nets), protect=protect, widths=w, clmap=c, log=log,
                                    keep_locked=True, tries=40, passes=2, max_victims=16)
    left = finish.repair_tx(b, open_nets, protect=protect, widths=w, clmap=c, max_victims=14, max_rounds=40, log=log,
                            keep_locked=True)
    left = [n for n in left if n in set(mine)]
    if left:
        left = finish.repair_orders(b, left, protect=protect, widths=w, clmap=c, log=log, keep_locked=True,
                                    tries=10, passes=1)
    return left


def _setup(board_name, routers=True):
    """The board's layout module, its plane nets, router widths and
    clearances; sets EXTRA_RULES and (routers) the routers' settings."""
    global EXTRA_RULES
    if board_name == 'fc':
        import fc_layout as L
        planes = ['GND', '+3V3']
    else:
        import esc_layout as L
        planes = ['GND', 'VBAT']
    EXTRA_RULES = getattr(L, 'DRU_EXTRA', '') + pcb.copper_rules(getattr(L, 'INNER_OZ', 0.5))
    if routers:
        setup_routers(L)
    return L, planes, L.widths(circuit.build(board_name)), L.clearances(circuit.build(board_name))


def board_stage(board_name, placed, src, work, passes, log=print):
    """From the placed board `src` (for a stamped board, its channels'
    copies on it): Freerouting over the whole board, the finisher, the
    repairs, cleanup.  Files go to `work`; `placed` lends its project and
    rules.  Returns (finished board, nets still open)."""
    L, planes, widths, clmap = _setup(board_name)
    routed = os.path.join(work, board_name + '_routed.kicad_pcb')
    fin = os.path.join(work, board_name + '_fin.kicad_pcb')
    n = route.route(src, routed, passes=passes, rounds=2)
    log('%s: %d connections left after Freerouting, %d duplicate vias removed'
        % (board_name, n, pcb.dedupe_vias(routed)))
    _copy_project(placed, routed); _copy_project(placed, fin)
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
    return fin, left


def _stamped_stage(board_name, placed, tmpl, nets_json, work, passes, log=print):
    """A template routing stamped onto the placed board, then board_stage."""
    import stamp
    L, planes, widths, clmap = _setup(board_name)
    stamp.VIA_RING = getattr(L, 'VIA_RING', None) or 0.0
    nets = json.load(open(nets_json))
    nets = {t: {int(k): v for k, v in m.items()} for t, m in nets.items()}
    os.makedirs(work, exist_ok=True)
    src = os.path.join(work, board_name + '_stamped.kicad_pcb')
    stamp.stamp(placed, tmpl, src, nets, L.CHANNELS, rules=EXTRA_RULES, log=log)
    return board_stage(board_name, placed, src, work, passes, log=log)


def run(board_name, work, passes=None, log=print):
    """Returns the path of the finished board in `work`."""
    os.makedirs(work, exist_ok=True)
    seed = int(os.environ.get('PIPELINE_SEED', SEEDS[board_name]))
    pcbnew.KIID.SeedGenerator(seed)
    passes = passes or (15 if board_name == 'esc' else 60)      # Freerouting passes per round
    # the board is built before the routers are set up for it, as ever
    L, planes, widths, clmap = _setup(board_name, routers=False)
    placed = os.path.join(work, board_name + '.kicad_pcb')
    fin = os.path.join(work, board_name + '_fin.kicad_pcb')
    L.build(placed)
    pcb.write_rules(placed, EXTRA_RULES)
    setup_routers(L)
    if getattr(L, 'CHANNELS', None) and hasattr(L, 'channel_parts'):
        # one channel routed alone, stamped onto the others (stamp.py)
        import stamp
        stamp.VIA_RING = getattr(L, 'VIA_RING', None) or 0.0
        stamp.CLAIM = getattr(L, 'STAMP_CLAIM', None)
        comps = circuit.build(board_name)
        tmpl, nets, left, _, ties = stamp.route_template(placed, work, L.channel_parts(comps), L.CHANNELS,
                                                         passes=L.STAMP_PASSES, log=log, planes=planes,
                                                         repair=[sys.executable, os.path.abspath(__file__),
                                                                 'template-repair', board_name])
        nets_json = os.path.join(work, 'template_nets.json')
        json.dump(nets, open(nets_json, 'w'), indent=0, sort_keys=True)
        ties = ties[:os.cpu_count() or 4]
        if left and len(ties) > 1:
            fin_, left = _board_stages(board_name, placed, ties, nets_json, work, passes, seed, log)
        else:
            fin_, left = _stamped_stage(board_name, placed, tmpl, nets_json, work, passes, log=log)
    else:
        fin_, left = board_stage(board_name, placed, placed, work, passes, log=log)
        if left:
            fin_, left = _whole_variants(board_name, placed, work, passes, seed, (fin_, left), log)
    if os.path.abspath(fin_) != os.path.abspath(fin):
        shutil.copy(fin_, fin)
        _copy_project(placed, fin)
    return _final(board_name, L, fin, work, log)


def finish_run(board_name, work, log=print):
    """A --reroute run's last steps again, with the code as it is now, on
    the routed board it left in `work` (the routing is not redone): the
    ESC's clean-up, then artwork, stackup and the final DRC.  For a run the
    final DRC stopped after a fix to those steps.  Returns the board."""
    L, planes, widths, clmap = _setup(board_name, routers=False)
    fin = os.path.join(work, board_name + '_fin.kicad_pcb')
    _copy_project(os.path.join(work, board_name + '.kicad_pcb'), fin)
    if board_name == 'esc':
        cleanup.clean(fin, EXTRA_RULES, log=log)
    return _final(board_name, L, fin, work, log)


def _final(board_name, L, fin, work, log):
    """Artwork, stackup and the final DRC on the routed board `fin`."""
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


def _board_stages(board_name, placed, ties, nets_json, work, passes, seed, log):
    """The template channel came out with nets open in several routings
    that tie; which of them the whole board can finish (each channel has
    only its own neighbours there, not all four channels' at once) shows
    only by trying.  Each is stamped and taken through board_stage in a
    process of its own, all at once; the one leaving the fewest nets open
    wins (the first of equals).  Returns (its finished board, nets open)."""
    procs = []
    for i, tmpl in enumerate(ties):
        d = os.path.join(work, 'try%d' % i)
        os.makedirs(d, exist_ok=True)
        logf = open(os.path.join(d, 'log.txt'), 'w')
        env = dict(os.environ, PIPELINE_SEED=str(seed + 1 + i))
        procs.append((i, d, logf, subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), 'board-stage', board_name, placed, tmpl, nets_json, d,
             str(passes)], stdout=logf, stderr=subprocess.STDOUT, env=env)))
    res = []
    for i, d, logf, p in procs:
        p.wait()
        logf.close()
        out = os.path.join(d, 'result.json')
        if p.returncode != 0 or not os.path.exists(out):
            log('%s: whole board from template routing %d failed, see %s' % (board_name, i, logf.name))
            continue
        r = json.load(open(out))
        log('%s: whole board from template routing %d (%s): %d nets open %s'
            % (board_name, i, os.path.basename(ties[i]), len(r['left']), r['left']))
        res.append((len(r['left']), i, r['fin'], r['left']))
    if not res:
        raise SystemExit('%s: no whole-board stage finished' % board_name)
    n, i, fin, left = min(res)
    log('%s: kept the whole board from template routing %d' % (board_name, i))
    return fin, left


def _whole_variants(board_name, placed, work, passes, seed, first, log):
    """board_stage on the placed board again under each of WHOLE_VARIANTS'
    router costs, all at once; `first` is (finished board, nets open) at
    Freerouting's defaults.  Returns the (finished board, nets open) of the
    routing that leaves the fewest nets open, the first of equals."""
    log('%s: %d nets open at Freerouting\'s default costs %s; trying %d other costs'
        % (board_name, len(first[1]), sorted(first[1]), len(WHOLE_VARIANTS)))
    procs = []
    for i, costs in enumerate(WHOLE_VARIANTS, 1):
        d = os.path.join(work, 'costs%d' % i)
        os.makedirs(d, exist_ok=True)
        logf = open(os.path.join(d, 'log.txt'), 'w')
        env = dict(os.environ, PIPELINE_SEED=str(seed))
        procs.append((i, costs, logf, d, subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), 'whole-stage', board_name, placed, d, str(passes),
             json.dumps(costs, sort_keys=True)], stdout=logf, stderr=subprocess.STDOUT, env=env)))
    res = [(len(first[1]), 0, first[0], sorted(first[1]))]
    for i, costs, logf, d, p in procs:
        p.wait()
        logf.close()
        out = os.path.join(d, 'result.json')
        if p.returncode != 0 or not os.path.exists(out):
            log('%s: whole board at costs %s failed, see %s' % (board_name, costs, logf.name))
            continue
        r = json.load(open(out))
        log('%s: whole board at costs %s: %d nets open %s' % (board_name, costs, len(r['left']), r['left']))
        res.append((len(r['left']), i, r['fin'], r['left']))
    n, i, fin, left = min(res)
    log('%s: kept the routing at %s' % (board_name, 'the default costs' if i == 0 else
                                        'costs %s' % WHOLE_VARIANTS[i - 1]))
    return fin, left


def _whole_stage_main(board_name, placed, work, passes, costs):
    pcbnew.KIID.SeedGenerator(int(os.environ.get('PIPELINE_SEED', SEEDS[board_name])))
    route.AUTOROUTE = json.loads(costs)
    fin, left = board_stage(board_name, placed, placed, work, int(passes), log=lambda s: print(s, flush=True))
    json.dump({'fin': fin, 'left': sorted(left)}, open(os.path.join(work, 'result.json'), 'w'))


def _board_stage_main(board_name, placed, tmpl, nets_json, work, passes):
    pcbnew.KIID.SeedGenerator(int(os.environ.get('PIPELINE_SEED', SEEDS[board_name])))
    fin, left = _stamped_stage(board_name, placed, tmpl, nets_json, work, int(passes),
                               log=lambda s: print(s, flush=True))
    json.dump({'fin': fin, 'left': sorted(left)}, open(os.path.join(work, 'result.json'), 'w'))


def _template_repair_main(board_name, src, dst, job):
    """template_repair on the board file `src`, saved as `dst`; `job` is a
    JSON file with the open nets and the nets that may move."""
    L = __import__(board_name + '_layout')
    setup_routers(L)
    comps = circuit.build(board_name)
    j = json.load(open(job))
    b = pcbnew.LoadBoard(src)
    template_repair(b, j['open'], j['mine'], L.widths(comps), L.clearances(comps),
                    log=lambda s: print(s, flush=True), deep=j.get('deep', False))
    b.Save(dst)


if __name__ == '__main__':
    # python3 pipeline.py template-repair <board> <in.kicad_pcb> <out.kicad_pcb> <job.json>
    # (stamp.py runs one of these per routing of the template channel, all at once)
    if sys.argv[1:2] == ['template-repair']:
        _template_repair_main(*sys.argv[2:6])
    elif sys.argv[1:2] == ['board-stage']:
        # python3 pipeline.py board-stage <board> <placed> <template> <nets.json> <work> <passes>
        _board_stage_main(*sys.argv[2:8])
    elif sys.argv[1:2] == ['whole-stage']:
        # python3 pipeline.py whole-stage <board> <placed> <work> <passes> <costs.json>
        _whole_stage_main(*sys.argv[2:7])
    else:
        raise SystemExit('usage: pipeline.py template-repair BOARD IN OUT JOB | '
                         'board-stage BOARD PLACED TEMPLATE NETS WORK PASSES | '
                         'whole-stage BOARD PLACED WORK PASSES COSTS')
