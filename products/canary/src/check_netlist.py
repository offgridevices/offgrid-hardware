"""Gate: the schematic's netlist (exported by KiCad) equals circuit.nets()."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import circuit
from sexpr import parse, find, findall

def kicad_nets(path):
    root = parse(open(path).read())
    out = {}
    for n in findall(find(root, 'nets'), 'net'):
        name = find(n, 'name')[1].lstrip('/')
        conns = sorted((find(x, 'ref')[1], find(x, 'pin')[1]) for x in findall(n, 'node'))
        if name.startswith('unconnected-') or name.startswith('Net-('):
            continue
        out[name] = conns
    return out

def main(path):
    want = {k: sorted(c for c in v if c not in circuit.BOARD_ONLY) for k, v in circuit.nets().items()}
    got = kicad_nets(path)
    bad = 0
    for n in sorted(set(want) | set(got)):
        if want.get(n) != got.get(n):
            bad += 1
            print('MISMATCH', n, '\n  circuit:', want.get(n), '\n  kicad:  ', got.get(n))
    print(f'netlist check: {len(want)} nets, {bad} mismatches')
    return bad

if __name__ == '__main__':
    sys.exit(1 if main(sys.argv[1]) else 0)
