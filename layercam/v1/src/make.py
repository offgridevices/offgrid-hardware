# -*- coding: utf-8 -*-
"""Build LayerCam v1: every committed output of its three boards, with gates.

    python3 src/make.py [main|ring|usb ...]          outputs from the committed boards
    python3 src/make.py --reroute [main|ring|usb]    place and route from scratch first
    python3 src/make.py --artwork [...]              lay the silkscreen out again (copper untouched)
    python3 src/make.py --fab-only [...]             fab files only: no renders or STEP (CI)

With no board named, all three.  Gates (any failure stops the build):
  * circuit.py: every part has a footprint and an LCSC number, no
    single-pin net, every pin on its footprint and every pad in circuit.py
  * KiCad DRC: 0 errors, 0 warnings, 0 unconnected items
  * every pad's net on the board equals circuit.py
  * every track corner 45 degrees or less
  * the BOM and CPL list exactly the assembled parts
  * (main) the MIPI and USB pairs: each pair's two tracks the same length

Run inside the pinned toolchain (tools/Dockerfile): tools/kd python3 src/make.py
"""
import os, sys, csv, tempfile
if os.environ.get('PYTHONHASHSEED') != '0':
    os.environ['PYTHONHASHSEED'] = '0'
    os.execv(sys.executable, [sys.executable] + sys.argv)
HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import pcbnew
import pcb, parts, circuit, fab, check_pins, miter

PAIR_SKEW = 0.15          # mm, P to N within a pair (about 1 ps)


def gate(ok, what):
    print('  [%s] %s' % ('ok' if ok else 'FAIL', what), flush=True)
    if not ok:
        raise SystemExit('gate failed: ' + what)


def name(bd):
    return 'layercam-' + bd


def check_circuit():
    allp = {**parts.PARTS, **parts.PADS}
    for bd in circuit.BOARDS:
        comps = circuit.build(bd)
        gate(all(c.part in allp for c in comps), '%s: every part has a footprint (%d parts)' % (bd, len(comps)))
        single = [n for n, m in circuit.nets(comps).items() if len(m) < 2]
        gate(not single, '%s: no single-pin nets %s' % (bd, single or ''))
        gate(all(parts.PARTS[c.part].get('lcsc') for c in comps if c.part in parts.PARTS),
             '%s: every assembled part has an LCSC number' % bd)
    bad = check_pins.check()
    gate(not bad, 'every pin on its footprint, every pad in circuit.py %s' % (bad[:3] or ''))


def check_outputs(bd, board):
    prod = os.path.join(os.path.dirname(board), 'production')
    b = pcbnew.LoadBoard(board)
    comps = {c.ref: c for c in circuit.build(bd)}
    asm = sorted(r for r, c in comps.items() if c.part in parts.PARTS)
    with open(os.path.join(prod, name(bd) + '-cpl.csv')) as f:
        cpl = sorted(r['Designator'] for r in csv.DictReader(f))
    with open(os.path.join(prod, name(bd) + '-bom-pcbway.csv')) as f:
        bom = sorted(d for r in csv.DictReader(f) for d in r['Designator'].split(','))
    gate(cpl == asm, 'CPL lists exactly the %d assembled parts' % len(asm))
    gate(bom == asm, 'BOM lists exactly the %d assembled parts' % len(asm))
    fps = {fp.GetReference() for fp in b.GetFootprints()}
    gate(fps == set(comps), 'board footprints == circuit.py components (%d)' % len(comps))


def check_pairs(board):
    import pairs
    ln = pairs.lengths(pcbnew.LoadBoard(board))
    worst = []
    for p, n in pairs.MIPI + (('USB_DP', 'USB_DM'),):
        worst.append((abs(ln[p] - ln[n]), p, n, ln[p], ln[n]))
    d, p, n, lp, lnn = max(worst)
    gate(d <= PAIR_SKEW, 'pairs matched within %.2f mm (worst %s/%s %.2f/%.2f mm)' % (PAIR_SKEW, p, n, lp, lnn))
    print('      lengths: %s' % ', '.join('%s %.1f' % (k, v) for k, v in sorted(ln.items())))


def artwork(path):
    import silk
    b = pcbnew.LoadBoard(path)
    silk.strip(b)
    silk.draw(b)
    pcbnew.SaveBoard(path, b)


def build(bd, reroute=False, art=False, pictures=True):
    print('== LayerCam v1: %s board' % bd)
    pcb.configure(bd)
    board = pcb.board_path(bd)
    if reroute:
        import pipeline
        work = tempfile.mkdtemp(prefix='layercam-%s-' % bd)
        routed = pipeline.run(bd, work)
        fab.install(routed, pcb.board_dir(bd), name(bd))
        art = True
    if art:
        artwork(board)
    pcb.write_rules(board)
    pcb.set_stackup(board)
    tmp = tempfile.mkdtemp()
    e, w, u = pcb.drc(board, os.path.join(tmp, 'drc.json'))
    gate(not e and not w and not u, 'KiCad DRC: %d errors, %d warnings, %d unconnected' % (len(e), len(w), len(u)))
    bad = fab.check_netlist(board, None)
    gate(not bad, 'copper nets match circuit.py pad for pad %s' % (bad[:5] or ''))
    sharp = [c for c in miter.corners(board) if c[0] > miter.LIMIT]
    gate(not sharp, 'every track corner 45 degrees or less %s' % ([(round(a), n, x, y) for a, n, _, x, y in sharp][:6] or ''))
    if bd == 'main':
        check_pairs(board)
    out = fab.produce(board, None, name(bd), V1, pictures=pictures)
    print('  wrote %s (%d files), %d parts in %d BOM lines, %d pads in the netlist'
          % (os.path.relpath(out['zip'], V1), len(out['gerber_files']), out['parts'], out['bom_lines'], out['pads']))
    check_outputs(bd, board)


if __name__ == '__main__':
    args = sys.argv[1:]
    boards = [a for a in args if not a.startswith('--')] or list(circuit.BOARDS)
    check_circuit()
    for bd in boards:
        build(bd, '--reroute' in args, '--artwork' in args, '--fab-only' not in args)
    print('all gates passed')
