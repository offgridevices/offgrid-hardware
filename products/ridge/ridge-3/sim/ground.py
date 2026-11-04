# -*- coding: utf-8 -*-
"""The stack waiting on the ground with its video on, for any flight-controller load.

From ridge-3/:

    sim/.venv/bin/python sim/ground.py [--variant=NAME]

writes GROUND.md to sim/results/variants/NAME/ (rev2/ without
--variant), beside the found.json it reads there.

stress.py's ground section runs three FC loads at 25, 50 and 60 C.  This
runs the same steady state (still air, motors stopped, the video
thermostat cycling where it trips) for the loads a buyer actually wires:
an HD air unit on the 9 V pads, or on the battery directly (DJI's O3 and
O4 Pro take 7.4-26.4 V), with 0.5-1 A on the 5 V rail, at 25, 35 (a
garage), 50 and 60 C.  The switching energies come from that variant's
last stress run (found.json, from `stress.py --variant=NAME`); the motors
are stopped, so they do not enter the result.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stress, data

LOADS = (('HD on the 9 V pads (9 V 1.5 A), 5 V 1 A', dict(i5=1.0, i9=1.5)),
         ('HD on the 9 V pads (9 V 1 A), 5 V 0.5 A', dict(i5=0.5, i9=1.0)),
         ('HD on the battery, 5 V 1 A', dict(i5=1.0, i9=0.0)),
         ('HD on the battery, 5 V 0.5 A', dict(i5=0.5, i9=0.0)),
         ('both rails at 2 A (their rating)', dict(i5=2.0, i9=2.0)))
AIRS = (25.0, 35.0, 50.0, 60.0)
RESULTS = os.path.join(HERE, 'results', 'variants')     # found.json in, GROUND.md out


def main(name='rev2'):
    data.variant(name)
    found = json.load(open(os.path.join(RESULTS, name, 'found.json')))['found']
    sw = found['sw']
    V = data.BATTERY['vfull']
    rows = []
    for Ta in AIRS:
        for tag, fc in LOADS:
            m = stress.model(0.0, Ta)
            op = stress.operating(0.0, V, sw, fc)
            T = stress.steady(m, op)
            over = [x for x in stress.worst(m, T, op) if x[0] < 0]
            rows.append(['%.0f C' % Ta, tag, '%.0f %%' % (100 * op['fc'].get('vtx_on', 1.0)),
                         '%.0f C' % m.temp(T, 'FC U_FC'), '%.0f C' % m.temp(T, 'FC U_BUCK9'),
                         '%.0f C' % m.temp(T, 'FC J_ESC'),
                         '%d: %s' % (len(over), ', '.join('%s %.0f C (%.0f)' % (x[1], x[2], x[3]) for x in over[:3]))
                         if over else 'none'])
            print(' | '.join(rows[-1]), flush=True)
    lines = ['# Ridge 3 on the ground, video on, still air (%s)' % name, '',
             '| Air | FC load | Video on (thermostat) | Processor | 9 V buck | Stack connector | Parts past their rating |',
             '|---|---|---|---|---|---|---|'] + ['| ' + ' | '.join(r) + ' |' for r in rows]
    out = os.path.join(RESULTS, name, 'GROUND.md')
    open(out, 'w').write('\n'.join(lines) + '\n')
    print('wrote', out)


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument('--variant', choices=list(data.VARIANTS), metavar='NAME', default='rev2',
                    help='rev 2 with one change: %s' % ', '.join(data.VARIANTS))
    main(ap.parse_args().variant)
