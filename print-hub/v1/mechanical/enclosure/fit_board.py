# -*- coding: utf-8 -*-
"""Fit check of the real board model in the enclosure.

enclosure.py checks the case against boxes built from the layout; this
loads the assembled board's STEP as KiCad exports it (every part's 3D model
on its land) and checks it against the case's own STEP: no solid of the
board may overlap the base or the lid.

    python3 mechanical/enclosure/fit_board.py      (from print-hub/v1, in the toolchain image)

Frames: KiCad's STEP has the page origin (the board centre at x 100,
y -100) with y up; the enclosure's has the board centre at 0, +Y towards
the back (USB-C) edge; both have the board's bottom face at z = 0.
"""
import os, sys, zipfile, tempfile
import build123d as bd

HERE = os.path.dirname(os.path.abspath(__file__))
V1 = os.path.normpath(os.path.join(HERE, '..', '..'))


def load(zp):
    z = zipfile.ZipFile(zp)
    name = [n for n in z.namelist() if n.endswith('.step')][0]
    path = os.path.join(tempfile.mkdtemp(), name)
    open(path, 'wb').write(z.read(name))
    return bd.import_step(path)


def overlaps(a, b):
    return (a.min.X < b.max.X and b.min.X < a.max.X and a.min.Y < b.max.Y and b.min.Y < a.max.Y
            and a.min.Z < b.max.Z and b.min.Z < a.max.Z)


def main():
    board = load(os.path.join(V1, 'mechanical', 'print-hub-step.zip'))
    case = load(os.path.join(HERE, 'printhub-enclosure-step.zip'))
    board = bd.Pos(-100, 100, 0) * board
    bb = board.bounding_box()
    print('board model: x %.1f..%.1f  y %.1f..%.1f  z %.2f..%.2f' % (bb.min.X, bb.max.X, bb.min.Y, bb.max.Y, bb.min.Z, bb.max.Z))
    case_solids = case.solids()
    bad = 0
    for s in board.solids():
        sb = s.bounding_box()
        for c in case_solids:
            if not overlaps(sb, c.bounding_box()):     # cheap reject first
                continue
            i = s & c
            v = i.volume if i is not None else 0.0
            if v > 0.01:
                bad += 1
                print('  OVERLAP %.2f mm^3: board solid at x %.1f..%.1f y %.1f..%.1f z %.1f..%.1f'
                      % (v, sb.min.X, sb.max.X, sb.min.Y, sb.max.Y, sb.min.Z, sb.max.Z))
    print('%d board solids against %d case solids: %s' % (len(board.solids()), len(case_solids),
                                                          'PASS' if not bad else 'FAIL (%d overlaps)' % bad))
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
