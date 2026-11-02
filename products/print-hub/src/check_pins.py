# -*- coding: utf-8 -*-
"""Gate: every pin circuit.py connects exists on its part's footprint, and
every copper pad of every footprint is either connected or listed as
deliberately open (None) in circuit.py."""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import circuit, parts, pcb


def check():
    allp = {**parts.PARTS, **parts.PADS}
    bad = []
    for c in circuit.build():
        fp = pcb.load_fp(allp[c.part]['fp'])
        pads = {p.GetNumber() for p in fp.Pads() if p.GetNumber()}
        for pin in c.pins:
            if pin not in pads:
                bad.append('%s (%s): pin %s not on footprint %s' % (c.ref, c.part, pin, sorted(pads)))
        for pad in pads:
            if pad not in c.pins:
                bad.append('%s (%s): footprint pad %s not in circuit.py' % (c.ref, c.part, pad))
    return bad


if __name__ == '__main__':
    b = check()
    print('\n'.join(b) or 'every pin and pad accounted for')
    sys.exit(1 if b else 0)
