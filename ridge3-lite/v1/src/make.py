# -*- coding: utf-8 -*-
"""Build Ridge 3 Lite: every committed output, with gates.

    python3 make.py              outputs from the committed ridge3-lite.kicad_pcb
    python3 make.py --reroute    place and route the board from scratch first
    python3 make.py --artwork    lay the silkscreen out again (copper untouched)
    python3 make.py --no-panel   skip the production panel
    python3 make.py --fab-only   fab files only: no renders, STEP or panel (CI)

Gates (any failure stops the build):
  * circuit.py: every part has a footprint, no single-pin net, every pin on
    its footprint and every footprint pad in circuit.py
  * KiCad DRC: 0 errors, 0 warnings, 0 unconnected items
  * every pad's net on the board equals circuit.py
  * every assembled part appears in the BOM and CPL with an LCSC number

Run inside the pinned toolchain (tools/Dockerfile): tools/kd python3 src/make.py
"""
import os, sys, csv, shutil, tempfile
if os.environ.get('PYTHONHASHSEED') != '0':
    os.environ['PYTHONHASHSEED'] = '0'
    os.execv(sys.executable, [sys.executable] + sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
import pcb, parts, circuit, fab, check_pins

NAME = 'ridge3-lite'
BOARD = os.path.join(V1, NAME + '.kicad_pcb')


def gate(ok, what):
    print('  [%s] %s' % ('ok' if ok else 'FAIL', what), flush=True)
    if not ok:
        raise SystemExit('gate failed: ' + what)


def check_circuit():
    comps = circuit.build()
    allp = {**parts.PARTS, **parts.PADS}
    gate(all(c.part in allp for c in comps), 'every part in circuit.py has a footprint (%d parts)' % len(comps))
    nets = circuit.nets(comps)
    single = [n for n, m in nets.items() if len(m) < 2]
    gate(not single, 'no single-pin nets %s' % (single or ''))
    gate(all(parts.PARTS[c.part].get('lcsc') for c in comps if c.part in parts.PARTS),
         'every assembled part has an LCSC number')
    bad = check_pins.check()
    gate(not bad, 'every pin on its footprint, every pad in circuit.py %s' % (bad[:3] or ''))


def check_outputs(prod):
    b = pcbnew.LoadBoard(BOARD)
    comps = {c.ref: c for c in circuit.build()}
    asm = sorted(r for r, c in comps.items() if c.part in parts.PARTS)
    with open(os.path.join(prod, NAME + '-cpl-jlcpcb.csv')) as f:
        cpl = sorted(r['Designator'] for r in csv.DictReader(f))
    with open(os.path.join(prod, NAME + '-bom-jlcpcb.csv')) as f:
        bom = sorted(d for r in csv.DictReader(f) for d in r['Designator'].split(','))
    gate(cpl == asm, 'CPL lists exactly the %d assembled parts' % len(asm))
    gate(bom == asm, 'BOM lists exactly the %d assembled parts' % len(asm))
    fps = {fp.GetReference() for fp in b.GetFootprints()}
    gate(fps == set(comps), 'board footprints == circuit.py components (%d)' % len(comps))


def artwork(path):
    """Lay the silkscreen out again on the board at `path` (copper untouched)."""
    import silk
    b = pcbnew.LoadBoard(path)
    silk.strip(b)
    silk.draw(b)
    b.Save(path)


def build(reroute=False, art=False, pan=True, pictures=True):
    print('== Ridge 3 Lite')
    check_circuit()
    if reroute:
        import pipeline
        work = tempfile.mkdtemp(prefix='r3lite-')
        fin = pipeline.run(work)
        fab.install(fin, V1, NAME)
    elif art:
        artwork(BOARD)
    # the design rules come from src/pcb.py: a rule change there reaches the
    # board's .kicad_dru (and this DRC) on the next build
    pcb.write_rules(BOARD, pcb.POFV_RULES)
    tmp = tempfile.mkdtemp()
    e, w, u = pcb.drc(BOARD, os.path.join(tmp, 'drc.json'))
    gate(not e and not w and not u, 'KiCad DRC: %d errors, %d warnings, %d unconnected' % (len(e), len(w), len(u)))
    bad = fab.check_netlist(BOARD, None)
    gate(not bad, 'copper nets match circuit.py pad for pad %s' % (bad[:5] or ''))
    out = fab.produce(BOARD, None, NAME, V1, pictures=pictures)
    print('  wrote %s (%d files), %d parts in %d BOM lines (%d on the bottom), %d pads in the netlist'
          % (os.path.relpath(out['zip'], V1), len(out['gerber_files']), out['parts'], out['bom_lines'],
             out['bottom_parts'], out['pads']))
    check_outputs(os.path.join(V1, 'production'))
    if pan:
        import panel
        if hasattr(panel, 'make'):
            panel.make(BOARD, NAME, V1)


if __name__ == '__main__':
    fab_only = '--fab-only' in sys.argv          # CI: fab files only, no pictures, STEP or panel
    build('--reroute' in sys.argv, '--artwork' in sys.argv, '--no-panel' not in sys.argv and not fab_only, not fab_only)
    print('all gates passed')
