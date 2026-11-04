"""Dump the board's parts for the enclosure: python3 dump_board.py (system
python3, it needs pcbnew) -> board_parts.json beside this file.

For every placed part: place.PL's (x, y, rot, side, fixed) in board mm, the
footprint, its courtyard box (board frame, after rotation and flip), its pad
box and its through-hole pads.  enclosure.py (CadQuery venv) reads the JSON.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'src')
sys.path.insert(0, SRC)
os.chdir(SRC)

import pcbnew  # noqa: E402

import board  # noqa: E402
import circuit  # noqa: E402
import parts  # noqa: E402
import place  # noqa: E402

TO_MM = pcbnew.ToMM


def box_of(items):
    xs, ys = [], []
    for bb in items:
        xs += [TO_MM(bb.GetLeft()), TO_MM(bb.GetRight())]
        ys += [TO_MM(bb.GetTop()), TO_MM(bb.GetBottom())]
    if not xs:
        return None
    return [round(min(xs) - board.OX, 3), round(min(ys) - board.OY, 3),
            round(max(xs) - board.OX, 3), round(max(ys) - board.OY, 3)]


def main():
    b = pcbnew.BOARD()
    out = {}
    for ref, (x, y, rot, side, fixed) in place.PL.items():
        c = circuit.COMPONENTS[ref]
        pd = parts.PARTS[c['part']]
        if pd['fp'] is None:
            continue
        fp = board.load_fp(pd['fp'])
        b.Add(fp)
        if side == 'B':
            fp.Flip(fp.GetPosition(), pcbnew.FLIP_DIRECTION_TOP_BOTTOM)
        fp.SetPosition(board.P(x, y))
        fp.SetOrientationDegrees(rot)
        crt = pcbnew.B_CrtYd if side == 'B' else pcbnew.F_CrtYd
        fab = pcbnew.B_Fab if side == 'B' else pcbnew.F_Fab
        cy = box_of([g.GetBoundingBox() for g in fp.GraphicalItems() if g.GetLayer() == crt])
        fb = box_of([g.GetBoundingBox() for g in fp.GraphicalItems() if g.GetLayer() == fab
                     and g.GetClass() != 'PCB_TEXT'])
        pads = box_of([p.GetBoundingBox() for p in fp.Pads()])
        tht = []
        for p in fp.Pads():
            if p.GetAttribute() in (pcbnew.PAD_ATTRIB_PTH, pcbnew.PAD_ATTRIB_NPTH):
                pos = p.GetPosition()
                ds = p.GetDrillSize()
                tht.append([p.GetNumber(), round(TO_MM(pos.x) - board.OX, 3), round(TO_MM(pos.y) - board.OY, 3),
                            round(TO_MM(ds.x), 3), round(TO_MM(ds.y), 3),
                            round(TO_MM(p.GetBoundingBox().GetWidth()), 3)])
        out[ref] = dict(x=x, y=y, rot=rot, side=side, fixed=fixed, part=c['part'], fp=pd['fp'], fit=pd['fit'],
                        mpn=pd['mpn'], courtyard=cy, fab=fb, pads=pads, tht=tht)
    path = os.path.join(HERE, 'board_parts.json')
    with open(path, 'w') as f:
        json.dump(out, f, indent=1, sort_keys=True)
    print(f'{len(out)} parts -> {path}')


if __name__ == '__main__':
    main()
