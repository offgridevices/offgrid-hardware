# -*- coding: utf-8 -*-
"""Build the Cheap Drone stack v1: every committed output, with gates.

    python3 make.py              outputs from the committed .kicad_pcb files
    python3 make.py --reroute    place and route both boards from scratch first
    python3 make.py fc           one board only (fc or esc)

Gates (any failure stops the build):
  * KiCad DRC: 0 errors, 0 warnings, 0 unconnected items
  * every pad's net on the board equals circuit.py
  * every assembled part appears in the BOM and CPL with an LCSC number
  * circuit.py itself: no part without a footprint, no single-pin net

Needs KiCad 10 (pcbnew Python module + kicad-cli) and, for --reroute only,
Freerouting 1.9 (FREEROUTING_JAR=path/to/freerouting-1.9.0.jar) with java
and xvfb-run.
"""
import os, sys, csv, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
import pcb, parts, circuit, fab

BOARDS = {'fc': 'cheapdrone-fc', 'esc': 'cheapdrone-esc'}


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
    gate(all(parts.PARTS[c.part].get('lcsc') for c in comps if c.part in parts.PARTS),
         '%s: every assembled part has an LCSC number' % board)


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


def build(board, reroute):
    name = BOARDS[board]
    print('== %s' % name)
    check_circuit(board)
    dst = os.path.join(V1, board, name + '.kicad_pcb')
    if reroute:
        import pipeline
        work = tempfile.mkdtemp(prefix='cheapdrone-%s-' % board)
        fin = pipeline.run(board, work)
        fab.install(fin, os.path.join(V1, board), name)
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


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    for bd in (args or ['fc', 'esc']):
        build(bd, '--reroute' in sys.argv)
    print('all gates passed')
