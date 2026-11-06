# -*- coding: utf-8 -*-
"""Gate: every footprint parts.py names exists, every pin circuit.py
connects exists on its part's footprint, and every copper pad of every
footprint is either connected or listed as deliberately open (None) in
circuit.py.  Unnamed pads (non-plated locating holes) are not pins.

Run with KiCad's Python:  tools/kd python3 src/check_pins.py
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import circuit, parts

LIBS = {'og': os.path.normpath(os.path.join(HERE, '..', 'og.pretty'))}


def load_fp(fpid):
    lib, name = fpid.split(':')
    path = LIBS.get(lib, os.path.join('/usr/share/kicad/footprints', lib + '.pretty'))
    if not os.path.exists(os.path.join(path, name + '.kicad_mod')):
        return None
    return pcbnew.FootprintLoad(path, name)


def check():
    bad = []
    fps = {}
    for key, p in sorted(parts.PARTS.items()):
        if p['fp'] not in fps:
            fps[p['fp']] = load_fp(p['fp'])
        if fps[p['fp']] is None:
            bad.append('%s: footprint %s not found' % (key, p['fp']))
    for c in circuit.build():
        fp = fps.get(parts.PARTS[c.part]['fp'])
        if fp is None:
            continue
        pads = {p.GetNumber() for p in fp.Pads() if p.GetNumber() and p.IsOnCopperLayer()}
        for pin in c.pins:
            if pin not in pads:
                bad.append('%s (%s): pin %s not on footprint %s' % (c.ref, c.part, pin, sorted(pads)))
        for pad in sorted(pads):
            if pad not in c.pins:
                bad.append('%s (%s): footprint pad %s not in circuit.py' % (c.ref, c.part, pad))
    return bad


if __name__ == '__main__':
    b = check()
    print('\n'.join(b) or 'every footprint found; every pin and pad accounted for')
    sys.exit(1 if b else 0)
