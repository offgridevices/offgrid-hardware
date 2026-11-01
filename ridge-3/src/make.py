# -*- coding: utf-8 -*-
"""Build the Ridge 3 stack (flight controller + 4-in-1 ESC): every committed output, with gates.

    python3.12 src/make.py               outputs from the committed .kicad_pcb files
                                         (unchanged boards give unchanged files: stable.py)
    python3.12 src/make.py --artwork     lay the outline, silkscreen and stackup out
                                         again first (copper untouched)
    python3.12 src/make.py --reroute     place and route both boards from scratch first
    python3.12 src/make.py --finish=DIR esc
                                         a --reroute run that its final DRC stopped
                                         (after a fix to its last steps): the clean-up,
                                         artwork and DRC again on the routed board it
                                         left in its work directory DIR, then on as
                                         --reroute
    python3.12 src/make.py fc            one board only (fc or esc)
    python3.12 src/make.py --no-panel    skip the production panel (it takes ~3 min)
    python3.12 src/make.py --fab-only    every gate and every order file, but no
                                         renders (boards, panels, the stack sheet)
                                         and no STEP: what CI runs, without KiCad's
                                         3D models (~5 min for both boards)
    python3.12 src/make.py --help        this text

Flags combine (make.py --fab-only esc).  The unzipped Gerbers (production/
gerbers/) and the panel's board and work files (out/panel/) are left in each
board's folder for a look; git ignores them.

Gates (any failure stops the build):
  * KiCad DRC: 0 errors, 0 warnings, 0 unconnected items
  * every pad's net on the board equals circuit.py
  * every assembled part appears in the BOM and CPL, with an LCSC number or,
    for JLCPCB's global sourcing, a maker part number and a DigiKey number
    (the ESC's FETs)
  * circuit.py itself: no part without a footprint, no single-pin net
  * the ESC's heatsink: made from this board (heatsink.current)
  * the 3 x 2 production panel (panel.py): DRC equal to six boards', every
    copy's Gerbers, BOM and CPL identical to the single board's, fiducial
    keep-out measured on the Gerbers

Needs KiCad 10.0.6 (pcbnew Python module + kicad-cli) and the packages in
requirements.txt; for --reroute only, Freerouting 1.9.0
(FREEROUTING_JAR=path/to/freerouting-1.9.0.jar) with java and xvfb-run.
tools/Dockerfile has all of it.  The ESC's heatsink (heatsink.py) is made
again only when the ESC or its parameters change; that needs CadQuery
(requirements-cadquery.txt; CADQUERY_PYTHON=path/to/python if this python
does not have it).
"""
import os, sys, csv, json, shutil, tempfile

BOARDS = {'fc': 'ridge3-fc', 'esc': 'ridge3-esc'}


def parse(argv):
    """The command line, read before KiCad loads: -h or --help prints the
    docstring, anything it does not know stops with a short message (exit
    status 2)."""
    import argparse
    ap = argparse.ArgumentParser(prog='make.py', add_help=False, allow_abbrev=False,
                                 usage='%(prog)s [--reroute | --artwork | --finish=DIR] [--no-panel] [--fab-only] '
                                       '[fc | esc ...]   (--help: what each does)')
    ap.add_argument('-h', '--help', action='store_true')
    ap.add_argument('--reroute', action='store_true')
    ap.add_argument('--artwork', action='store_true')
    ap.add_argument('--finish', metavar='DIR')
    ap.add_argument('--no-panel', action='store_true')
    ap.add_argument('--fab-only', action='store_true')
    ap.add_argument('boards', nargs='*')
    a = ap.parse_args(argv)
    if a.help:
        print(__doc__)
        sys.exit(0)
    bad = [b for b in a.boards if b not in BOARDS]
    if bad:
        ap.error('no board %s: fc or esc' % ', '.join(bad))
    if a.finish and len(a.boards) != 1:
        ap.error('--finish takes one board: make.py --finish=DIR fc|esc')
    return a


if __name__ == '__main__':
    ARGS = parse(sys.argv[1:])
# one fixed hash seed: set and dict iteration over strings then runs in the
# same order every time, and with the seeded item IDs (pipeline.SEEDS) a
# reroute gives the same board, byte for byte in its copper
if os.environ.get('PYTHONHASHSEED') != '0':
    os.environ['PYTHONHASHSEED'] = '0'
    os.execv(sys.executable, [sys.executable] + sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
import pcb, parts, circuit, fab


def gate(ok, what):
    print('  [%s] %s' % ('ok' if ok else 'FAIL', what))
    if not ok:
        raise SystemExit('gate failed: ' + what)


def check_circuit(board):
    comps = circuit.build(board)
    allp = {**parts.PARTS, **parts.PADS}
    gate(all(c.part in allp for c in comps), '%s: every part in circuit.py has a footprint' % board)
    nets = circuit.nets(comps)
    single = [n for n, m in nets.items() if len(m) < 2]
    gate(not single, '%s: no single-pin nets %s' % (board, single or ''))
    orderable = lambda p: p.get('lcsc') or (p.get('source') == 'global' and p.get('mpn') and p.get('dk'))
    gate(all(orderable(parts.PARTS[c.part]) for c in comps if c.part in parts.PARTS),
         '%s: every assembled part has an LCSC number, or an MPN and DigiKey number for global sourcing' % board)


def check_outputs(board, name, prod):
    b = pcbnew.LoadBoard(os.path.join(V1, board, name + '.kicad_pcb'))
    every = circuit.build(board)
    comps = {c.ref: c for c in every}
    builds = [None] + sorted(x for x in circuit.BUILDS if x != circuit.DEFAULT_BUILD) \
        if any(c.option for c in every) else [None]
    for bld in builds:
        fname = name if bld is None else '%s-%s' % (name, bld)
        label = board if bld is None else '%s %s build' % (board, bld)
        asm = sorted(c.ref for c in circuit.fitted(every, bld) if c.part in parts.PARTS)
        with open(os.path.join(prod, fname + '-cpl-jlcpcb.csv')) as f:
            cpl = sorted(r['Designator'] for r in csv.DictReader(f))
        with open(os.path.join(prod, fname + '-bom-jlcpcb.csv')) as f:
            bom = sorted(d for r in csv.DictReader(f) for d in r['Designator'].split(','))
        gate(cpl == asm, '%s: CPL lists exactly the %d assembled parts' % (label, len(asm)))
        gate(bom == asm, '%s: BOM lists exactly the %d assembled parts' % (label, len(asm)))
    fps = {fp.GetReference() for fp in b.GetFootprints()}
    gate(fps == set(comps), '%s: board footprints == circuit.py components (%d)' % (board, len(comps)))


def artwork(dst, board):
    """Outline, silkscreen and stackup again on the committed board (the
    copper stays; DRC refills the pours against the outline)."""
    L = __import__(board + '_layout')
    b = pcbnew.LoadBoard(dst)
    pcb.redraw_outline(b)
    if board == 'fc':
        L.artwork(b)
    else:
        L.artwork(b, circuit.build(board))
    # (pcbnew's save rewrites the project file too; keep it as it was)
    pro = os.path.splitext(dst)[0] + '.kicad_pro'
    keep = open(pro).read() if os.path.exists(pro) else None
    b.Save(dst)
    if keep is not None:
        open(pro, 'w').write(keep)
    pcb.set_stackup(dst, getattr(L, 'INNER_OZ', 0.5))


def make_panel(board, name, dst, render=True):
    """3 x 2 panel for bulk assembly: order files into production/panel/,
    renders into images/ (render=False: none).  panel.make_panel stops on
    any failed check.  It works in <board>/out/panel/, a fixed folder: the
    panel board's paths to the 3D models are then the same in every
    checkout, and so is its renders' inputs key."""
    import panel, stable
    prod = os.path.join(V1, board, 'production', 'panel')
    img = os.path.join(V1, board, 'images')
    work = os.path.join(V1, board, 'out', 'panel')
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    pngs = ['%s-panel-%s.png' % (name, side) for side in ('top', 'bottom')] if render else []
    for p in pngs:                       # stable.render redraws only if the panel changed
        if os.path.exists(os.path.join(img, p)):
            shutil.copy(os.path.join(img, p), work)
    out = panel.make_panel(dst, work, name, board_name=board, render=render)
    old = stable.snapshot(prod)
    shutil.rmtree(prod, ignore_errors=True)
    os.makedirs(prod)
    for k in ('gerbers_zip', 'bom', 'bom_pcbway', 'cpl'):
        shutil.copy(out[k], prod)
    for f in os.listdir(prod):           # the same panel but for KiCad's stamps: keep the committed file
        stable.keep_if_same(os.path.join(prod, f), old.get(f))
    for p in pngs:
        shutil.copy(os.path.join(work, p), img)
    gate(True, '%s: panel %s, %d copies, %s mm; DRC = %d x the board\'s own; Gerbers, BOM and CPL of '
               'every copy equal the board\'s' % (board, out['grid'], out['copies'],
                                                  out['geometry'].get('size_mm'), out['copies'], ))


def build(board, reroute, art=False, pan=True, finish_dir=None, fab_only=False):
    name = BOARDS[board]
    print('== %s' % name)
    check_circuit(board)
    dst = os.path.join(V1, board, name + '.kicad_pcb')
    if finish_dir:
        import pipeline
        fin = pipeline.finish_run(board, finish_dir)
        fab.install(fin, os.path.join(V1, board), name)
    elif reroute:
        import pipeline
        work = tempfile.mkdtemp(prefix='ridge3-%s-' % board)
        fin = pipeline.run(board, work)
        fab.install(fin, os.path.join(V1, board), name)
        shutil.rmtree(work)              # kept when the run fails, for its logs
    elif art:
        artwork(dst, board)
    # 3D models as the footprint library has them (renders, STEP), and each
    # part's value and LCSC number as circuit.py has them: the copper stays
    import models3d
    got = models3d.refresh(dst)
    if got:
        print('  3D models from the library: %s' % ', '.join(sorted(got)))
    got = pcb.refresh_fields(dst, circuit.build(board))
    if got:
        print('  value and LCSC fields from circuit.py: %s' % ', '.join(sorted(got)))
    with tempfile.TemporaryDirectory() as tmp:
        e, w, u = pcb.drc(dst, os.path.join(tmp, 'drc.json'))
    gate(not e and not w and not u, '%s: DRC %d errors, %d warnings, %d unconnected' % (board, len(e), len(w), len(u)))
    bad = fab.check_netlist(dst, board)
    gate(not bad, '%s: copper nets match circuit.py pad for pad %s' % (board, bad[:5] or ''))
    out = fab.produce(dst, board, name, V1, visual=not fab_only)
    print('  wrote %s (%d files), %d parts in %d BOM lines (%d on the bottom), %d pads in the netlist'
          % (os.path.relpath(out['zip'], V1), len(out['gerber_files']), out['parts'], out['bom_lines'],
             out['bottom_parts'], out['pads']))
    check_outputs(board, name, os.path.join(V1, board, 'production'))
    if board == 'esc':
        heatsink_outputs(dst)
    if pan:
        make_panel(board, name, dst, render=not fab_only)


def heatsink_outputs(dst):
    """The ESC's heatsink (heatsink.py) from the board just built: made
    again when the board or its parameters have changed since the committed
    one (that needs CadQuery: CADQUERY_PYTHON)."""
    import heatsink
    out = os.path.join(V1, 'mechanical')
    if not heatsink.current(out, dst):
        heatsink.build(dst, out)
        print('  heatsink: wrote %s-step.zip, ridge3-esc-gap-pad.dxf, %s.pdf' % (heatsink.NAME, heatsink.NAME))
    s = json.load(open(os.path.join(out, heatsink.NAME + '.json')))
    gate(heatsink.current(out, dst), 'esc: heatsink from this board: every bottom part pocketed to its maximum '
         'height, no wall under %.1f mm, pad at %.0f %% squeeze (in its charts); plate %.1f g, pad %.1f g'
         % (heatsink.PARAMS['floor'], s['pad_deflection_pct'], s['plate_g'], s['pad_g']))


def stack_sheet():
    """Both sides of both boards on one sheet, from their renders."""
    out = fab.stack_sheet(V1, os.path.join(V1, 'images', 'ridge3-stack.png'),
                          [('fc', BOARDS['fc'], 'Flight controller'), ('esc', BOARDS['esc'], '4-in-1 ESC')],
                          'Ridge 3', '36 × 36 mm · 2-6S · 25.5 mm mount')
    print('  stack sheet %s' % os.path.relpath(out, V1))


if __name__ == '__main__':
    a = ARGS
    for bd in (a.boards or ['fc', 'esc']):
        build(bd, a.reroute, a.artwork, not a.no_panel, a.finish, a.fab_only)
    if not a.boards and not a.fab_only:
        stack_sheet()
    print('all gates passed')
