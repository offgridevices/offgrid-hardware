# -*- coding: utf-8 -*-
"""Build the Ridge 3 stack (flight controller + 4-in-1 ESC): every committed output, with gates.

    python3 make.py              outputs from the committed .kicad_pcb files
    python3 make.py --artwork    lay the outline, silkscreen and stackup out again first
                                 (copper untouched)
    python3 make.py --reroute    place and route both boards from scratch first
    python3 make.py --finish=DIR esc
                                 a --reroute run that its final DRC stopped (after a
                                 fix to its last steps): the clean-up, artwork and DRC
                                 again on the routed board it left in its work
                                 directory DIR, then on as --reroute
    python3 make.py fc           one board only (fc or esc)
    python3 make.py --no-panel   skip the production panel (it takes ~3 min)

Gates (any failure stops the build):
  * KiCad DRC: 0 errors, 0 warnings, 0 unconnected items
  * every pad's net on the board equals circuit.py
  * every assembled part appears in the BOM and CPL with an LCSC number
  * circuit.py itself: no part without a footprint, no single-pin net
  * the 3 x 2 production panel (panel.py): DRC equal to six boards', every
    copy's Gerbers, BOM and CPL identical to the single board's, fiducial
    keep-out measured on the Gerbers

Needs KiCad 10 (pcbnew Python module + kicad-cli) and, for --reroute only,
Freerouting 1.9 (FREEROUTING_JAR=path/to/freerouting-1.9.0.jar) with java
and xvfb-run.
"""
import os, sys, csv, shutil, tempfile
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

BOARDS = {'fc': 'ridge3-fc', 'esc': 'ridge3-esc'}


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
    comps = {c.ref: c for c in circuit.build(board)}
    asm = sorted(r for r, c in comps.items() if c.part in parts.PARTS)
    with open(os.path.join(prod, name + '-cpl-jlcpcb.csv')) as f:
        cpl = sorted(r['Designator'] for r in csv.DictReader(f))
    with open(os.path.join(prod, name + '-bom-jlcpcb.csv')) as f:
        bom = sorted(d for r in csv.DictReader(f) for d in r['Designator'].split(','))
    gate(cpl == asm, '%s: CPL lists exactly the %d assembled parts' % (board, len(asm)))
    gate(bom == asm, '%s: BOM lists exactly the %d assembled parts' % (board, len(asm)))
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


def make_panel(board, name, dst):
    """3 x 2 panel for bulk assembly: order files into production/panel/,
    renders into images/.  panel.make_panel stops on any failed check."""
    import panel
    tmp = tempfile.mkdtemp(prefix='ridge3-%s-panel-' % board)
    out = panel.make_panel(dst, tmp, name, board_name=board)
    prod = os.path.join(V1, board, 'production', 'panel')
    shutil.rmtree(prod, ignore_errors=True)
    os.makedirs(prod)
    for k in ('gerbers_zip', 'bom', 'bom_pcbway', 'cpl'):
        shutil.copy(out[k], prod)
    for side in ('top', 'bottom'):
        shutil.copy(os.path.join(tmp, '%s-panel-%s.png' % (name, side)), os.path.join(V1, board, 'images'))
    gate(True, '%s: panel %s, %d copies, %s mm; DRC = %d x the board\'s own; Gerbers, BOM and CPL of '
               'every copy equal the board\'s' % (board, out['grid'], out['copies'],
                                                  out['geometry'].get('size_mm'), out['copies'], ))


def build(board, reroute, art=False, pan=True, finish_dir=None):
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
    tmp = tempfile.mkdtemp()
    e, w, u = pcb.drc(dst, os.path.join(tmp, 'drc.json'))
    gate(not e and not w and not u, '%s: DRC %d errors, %d warnings, %d unconnected' % (board, len(e), len(w), len(u)))
    bad = fab.check_netlist(dst, board)
    gate(not bad, '%s: copper nets match circuit.py pad for pad %s' % (board, bad[:5] or ''))
    out = fab.produce(dst, board, name, V1)
    print('  wrote %s (%d files), %d parts in %d BOM lines (%d on the bottom), %d pads in the netlist'
          % (os.path.relpath(out['zip'], V1), len(out['gerber_files']), out['parts'], out['bom_lines'],
             out['bottom_parts'], out['pads']))
    check_outputs(board, name, os.path.join(V1, board, 'production'))
    if pan:
        make_panel(board, name, dst)


def stack_sheet():
    """Both sides of both boards on one sheet, from their renders."""
    out = fab.stack_sheet(V1, os.path.join(V1, 'images', 'ridge3-stack.png'),
                          [('fc', BOARDS['fc'], 'Flight controller'), ('esc', BOARDS['esc'], '4-in-1 ESC')],
                          'Ridge 3', '36 × 36 mm · 2-6S · 25.5 mm mount')
    print('  wrote %s' % os.path.relpath(out, V1))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    fin_dir = next((a.split('=', 1)[1] for a in sys.argv[1:] if a.startswith('--finish=')), None)
    if fin_dir and len(args) != 1:
        raise SystemExit('--finish takes one board: make.py --finish=DIR fc|esc')
    for bd in (args or ['fc', 'esc']):
        build(bd, '--reroute' in sys.argv, '--artwork' in sys.argv, '--no-panel' not in sys.argv, fin_dir)
    if not args:
        stack_sheet()
    print('all gates passed')
