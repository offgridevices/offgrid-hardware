# -*- coding: utf-8 -*-
"""Build Mesh Radio: every committed output, with gates.

    python3 src/make.py              outputs from the committed mesh-radio.kicad_pcb
    python3 src/make.py --reroute    place, route and lay the silkscreen out from scratch first
    python3 src/make.py --artwork    lay the silkscreen out again (copper untouched)
    python3 src/make.py --fab-only   fab files only: no renders or STEP (CI)

Gates (any failure stops the build):
  * circuit.py: every part has a footprint, no single-pin net, every pin on
    its footprint and every footprint pad in circuit.py
  * KiCad DRC: 0 errors, 0 warnings, 0 unconnected items
  * every pad's net on the board equals circuit.py
  * the BOM and CPL list exactly the assembled parts (not the test pads or
    the unfitted expansion header), each with an LCSC number

Adapted from Ridge 3 Lite's src/make.py; there is no production panel.
Run inside the pinned toolchain (tools/Dockerfile), from mesh-radio/v1:
    tools/kd python3 src/make.py
"""
import os, sys, csv, tempfile
if os.environ.get('PYTHONHASHSEED') != '0':
    os.environ['PYTHONHASHSEED'] = '0'
    os.execv(sys.executable, [sys.executable] + sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
import pcb, parts, circuit, fab, check_pins

NAME = 'mesh-radio'
BOARD = os.path.join(V1, NAME + '.kicad_pcb')


def gate(ok, what):
    print('  [%s] %s' % ('ok' if ok else 'FAIL', what), flush=True)
    if not ok:
        raise SystemExit('gate failed: ' + what)


def check_circuit():
    comps = circuit.build()
    gate(all(c.part in parts.PARTS for c in comps), 'every part in circuit.py has a footprint (%d parts)' % len(comps))
    nets = circuit.nets(comps)
    single = [n for n, m in nets.items() if len(m) < 2]
    gate(not single, 'no single-pin nets %s' % (single or ''))
    gate(all(parts.PARTS[c.part].get('lcsc') for c in comps if fab.assembled(parts.PARTS[c.part])),
         'every assembled part has an LCSC number')
    bad = check_pins.check()
    gate(not bad, 'every pin on its footprint, every pad in circuit.py %s' % (bad[:3] or ''))


def check_outputs(board, prod, name=NAME):
    b = pcbnew.LoadBoard(board)
    comps = {c.ref: c for c in circuit.build()}
    asm = sorted(r for r, c in comps.items() if fab.assembled(parts.PARTS[c.part]))
    with open(os.path.join(prod, name + '-cpl-jlcpcb.csv')) as f:
        cpl = sorted(r['Designator'] for r in csv.DictReader(f))
    with open(os.path.join(prod, name + '-bom-jlcpcb.csv')) as f:
        bom = sorted(d for r in csv.DictReader(f) for d in r['Designator'].split(','))
    gate(cpl == asm, 'CPL lists exactly the %d assembled parts' % len(asm))
    gate(bom == asm, 'BOM lists exactly the %d assembled parts' % len(asm))
    fps = {fp.GetReference() for fp in b.GetFootprints()}
    gate(fps == set(comps) | fab.BOARD_ONLY, 'board footprints == circuit.py components (%d) + %s'
         % (len(comps), ', '.join(sorted(fab.BOARD_ONLY))))


def artwork(path, log=print):
    """Lay the silkscreen out again on the board at `path` (copper untouched)."""
    import silk
    b = pcbnew.LoadBoard(path)
    silk.strip(b)
    silk.draw(b, circuit.build(), log=log)
    pcb.save_board(b, path)


def build(reroute=False, art=False, pictures=True):
    print('== Mesh Radio')
    check_circuit()
    if reroute:
        import pipeline
        work = tempfile.mkdtemp(prefix='mesh-radio-')
        fin = pipeline.run(work)
        fab.install(fin, V1, NAME)
        art = True                   # the pipeline routes; the silkscreen is laid out here
    if art:
        artwork(BOARD, log=lambda s: print('  ' + s, flush=True))
    # the design rules come from src/board.py (board.RULES, as the pipeline
    # writes them): a rule change there reaches the board's .kicad_dru (and
    # this DRC) on the next build
    import pipeline
    pipeline.write_rules(BOARD)
    tmp = tempfile.mkdtemp()
    e, w, u = pcb.drc(BOARD, os.path.join(tmp, 'drc.json'))
    gate(not e and not w and not u, 'KiCad DRC: %d errors, %d warnings, %d unconnected' % (len(e), len(w), len(u)))
    bad = fab.check_netlist(BOARD)
    gate(not bad, 'copper nets match circuit.py pad for pad %s' % (bad[:5] or ''))
    out = fab.produce(BOARD, NAME, V1, pictures=pictures)
    print('  wrote %s (%d files), %d parts in %d BOM lines (%d on the bottom), %d pads in the netlist'
          % (os.path.relpath(out['zip'], V1), len(out['gerber_files']), out['parts'], out['bom_lines'],
             out['bottom_parts'], out['pads']))
    check_outputs(BOARD, os.path.join(V1, 'production'))


if __name__ == '__main__':
    fab_only = '--fab-only' in sys.argv          # CI: fab files only, no pictures or STEP
    build('--reroute' in sys.argv, '--artwork' in sys.argv, not fab_only)
    print('all gates passed')
