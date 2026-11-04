"""Rebuild the silkscreen art on the finished board from src/ (make.art_items,
brand.py, art.py), so the committed silkscreen is what the code draws.

    python3 src/artwork.py             replay src/art_settled.json (what CI runs)
    python3 src/artwork.py --settle    search free spots again, rewrite art_settled.json

Every board-level silkscreen shape is removed and drawn again; the copper is
not touched.  The art is first placed by final.py before the stitching vias
exist; replaying the settled offsets keeps those vias from moving it.
"""
import json
import os
import sys

import pcbnew

import board as B
import make

SETTLED = os.path.join(B.HERE, 'art_settled.json')


def main():
    settle = '--settle' in sys.argv
    b = pcbnew.LoadBoard(make.OUT)
    for d in list(b.Drawings()):
        if d.GetLayer() in (pcbnew.F_SilkS, pcbnew.B_SilkS):
            B.remove(b, d)
    work = os.path.join(B.HERE, 'out', 'artwork')
    os.makedirs(work, exist_ok=True)
    settled = None if settle else json.load(open(SETTLED))
    placed = make.add_art(b, work, settled=settled)
    if settle:
        with open(SETTLED, 'w') as f:
            json.dump(make.add_art.settled, f, indent=1, sort_keys=True)
            f.write('\n')
    pcbnew.SaveBoard(make.OUT, b)
    B.set_stackup(make.OUT, inner_oz=1.0)
    print('art: %d items drawn%s' % (len(placed), ', offsets written to art_settled.json' if settle else ''))


if __name__ == '__main__':
    main()
