# -*- coding: utf-8 -*-
"""Table of the hottest part of each class, per case, with the margin to its
limit, from the JSON files thermal.py wrote.

    tools/kd python3 sim/thermal/report.py out/thermal/<board> [set]      (default set: report)

Writes <dir>/classes.md and classes.csv and prints the table.  For a
transient the parts are taken at the moment of the hottest FET junction,
except the ESC MCUs, whose own peak over the run is used (they lag)."""
import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

CLASSES = [  # (label, limit C, test on a part row)
    ('FET', 175, lambda r: r['kind'] == 'fet'),
    ('ESC MCU', 105, lambda r: r['name'].startswith('U_E')),
    ('FC MCU', 105, lambda r: r['name'] == 'U_FC'),
    ('IMU', 85, lambda r: r['name'] == 'U_IMU'),
    ('DRV8300', 150, lambda r: r['name'].startswith('U_D')),
    ('TPS7A16', 125, lambda r: r['name'] == 'U_GVDD'),
    ('LMR36506', 150, lambda r: r['name'] == 'U_BEC'),
    ('TLV767', 125, lambda r: r['name'] in ('U_LDO', 'U_LDOE')),
    ('INA186', 125, lambda r: r['name'].startswith('U_A')),
    ('shunt', 170, lambda r: r['name'].startswith('R_S')),
    ('X7R cap', 125, lambda r: r['kind'] == 'capX7R'),
    ('X5R cap', 85, lambda r: r['kind'] == 'capX5R'),
]


def table(d, names):
    rows = []
    for n in names:
        p = os.path.join(d, n + '.json')
        if not os.path.exists(p):
            continue
        r = json.load(open(p))
        if 'parts' not in r:
            rows.append((n, None, r)); continue
        vals = {}
        for lab, lim, test in CLASSES:
            ts = [x['T_j'] for x in r['parts'] if test(x)]
            vals[lab] = max(ts) if ts else None
        if 'transient' in r and r['transient']['peak'].get('ESC MCU max') == r['transient']['peak'].get('ESC MCU max'):
            vals['ESC MCU'] = r['transient']['peak'].get('ESC MCU max', vals['ESC MCU'])
        if 'transient' in r:
            vals['FET'] = r['transient']['peak']['FET junction max']
        vals['board'] = max(b for a, b in r['layers'].values())
        rows.append((n, vals, r))
    return rows


def main():
    import cases
    d = sys.argv[1]
    names = cases.expand(sys.argv[2] if len(sys.argv) > 2 else 'report', None)
    rows = table(d, names)
    labs = [c[0] for c in CLASSES] + ['board']
    lims = {c[0]: c[1] for c in CLASSES}
    out = ['| case | ' + ' | '.join(labs) + ' |', '|---' * (len(labs) + 1) + '|',
           '| limit C | ' + ' | '.join(str(lims.get(l, '')) for l in labs) + ' |']
    worst = {}
    for n, v, r in rows:
        if v is None:
            out.append('| %s | ' % n + ' | '.join(['runaway'] * len(labs)) + ' |'); continue
        cells = []
        for l in labs:
            x = v.get(l)
            if x is None:
                cells.append('-'); continue
            flag = '**' if l in lims and x > lims[l] else ''
            cells.append('%s%.0f%s' % (flag, x, flag))
            if l in lims:
                worst[l] = min(worst.get(l, 1e9), lims[l] - x)
        out.append('| %s | ' % n + ' | '.join(cells) + ' |')
    out.append('| min margin K | ' + ' | '.join('%.0f' % worst[l] if l in worst else '' for l in labs) + ' |')
    txt = '\n'.join(out)
    print(txt)
    open(os.path.join(d, 'classes.md'), 'w').write(txt + '\n')
    with open(os.path.join(d, 'classes.csv'), 'w') as fh:
        w = csv.writer(fh)
        w.writerow(['case'] + labs)
        for n, v, r in rows:
            w.writerow([n] + (['%.1f' % v[l] if v and v.get(l) is not None else '' for l in labs]))


if __name__ == '__main__':
    main()
