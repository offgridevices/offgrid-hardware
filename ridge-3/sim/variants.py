# -*- coding: utf-8 -*-
"""The variants side by side, from their runs' numbers.

From ridge-3/:

    sim/.venv/bin/python sim/variants.py [NAME ...]

Reads sim/results/variants/NAME/found.json (`stress.py --variant=NAME`) for
each variant that has been run (all of data.VARIANTS by default) and writes
the comparison table to sim/results/VARIANTS.md.  Throttle figures are the
reference motor's (data.MOTOR); the amps beside them are the battery current
per motor at that throttle, which carries over to other motors.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(HERE), 'src'))
import data, losses

RESULTS = os.path.join(HERE, 'results')


def load(name):
    p = os.path.join(RESULTS, 'variants', name, 'found.json')
    return json.load(open(p)) if os.path.exists(p) else None


def amps(name, throttle):
    data.variant(name)
    return losses.limited(throttle, data.BATTERY['vfull'])[0]


def rows_for(names):
    got = {n: load(n) for n in names}
    got = {n: g for n, g in got.items() if g}
    if not got:
        raise SystemExit('no sim/results/variants/NAME/found.json for %s: run stress.py --variant=NAME first'
                         % ', '.join(names))
    cols = list(got)
    def row(label, fn):
        out = [label]
        for n in cols:
            try:
                out.append(fn(n, got[n]['found'], got[n]))
            except (KeyError, TypeError, IndexError):
                out.append('-')
        return out
    v = lambda d, *k: d[' | '.join(str(x) for x in k)]
    R = []
    R.append(row('Change', lambda n, f, g: g['desc']))
    R.append(row('Verdicts: pass / marginal / fail', lambda n, f, g: '%d / %d / %d' % tuple(
        sum(1 for x in g['verdicts'] if x[2] == k) for k in ('PASS', 'MARGINAL', 'FAIL'))))
    for a, c, *_ in got[cols[0]]['verdicts']:
        if a == 'Voltage' and c.startswith('SHx'):
            R.append(row('SHx below ground (DRV8320H: -7 V for 200 ns)', lambda n, f, g, c=c: next(
                x[3] for x in g['verdicts'] if x[1] == c)))
    R.append(row('High-side FET peak at turn-off, 30 A (V)', lambda n, f, g: '%.1f' % f['hs_peak']))
    R.append(row('Low-side FET peak (V)', lambda n, f, g: '%.1f' % f['ls_peak']))
    R.append(row('Hover throttle', lambda n, f, g: '%.0f %%' % g['hover']))
    for Ta, air in ((25.0, 5.0), (50.0, 5.0), (60.0, 5.0), (50.0, 2.0), (60.0, 2.0)):
        R.append(row('Held all day before AM32 cuts, %.0f C, %.0f m/s' % (Ta, air), lambda n, f, g, Ta=Ta, air=air:
                     '%.0f %% (%.1f A/motor)' % (v(f['am32_hold'], air, Ta), amps(n, v(f['am32_hold'], air, Ta)))))
        R.append(row('Held all day, every part in rating, %.0f C, %.0f m/s' % (Ta, air), lambda n, f, g, Ta=Ta, air=air:
                     '%.0f %%' % v(f['hold'], air, Ta)[0]))
    R.append(row('Full-throttle burst, 50 C: hottest FET with AM32 acting', lambda n, f, g:
                 '%.0f C' % v(f['bursts_protected'], 50.0, 5.0)))
    R.append(row('Hard 3-min flight, 50 C: AM32 cuts a motor', lambda n, f, g:
                 ('from %.0f s, %.0f %% of the flight' % (f['flight']['cut'], 100 * f['flight']['frac']))
                 if f['flight']['cut'] is not None else 'never'))
    R.append(row('Hard 3-min flight, 50 C: hottest FET / ESC processor', lambda n, f, g:
                 '%.0f / %.0f C' % (f['flight']['fet'], f['flight']['mcu'])))
    R.append(row('Ground, 60 C, HD 9 V 1.5 A + 5 V 1 A: parts past rating', lambda n, f, g:
                 str(len(v(f['ground'], 60.0, '9 V at 1.5 A, 5 V at 1 A')[0]))))
    return cols, R


def main(names):
    cols, R = rows_for(names)
    lines = ['# Ridge 3 variants', '', 'Each column is rev 2 with one change (sim/data.py VARIANTS), '
             'run through the same simulations (`stress.py --variant=NAME`).', '',
             '| | ' + ' | '.join('`%s`' % c for c in cols) + ' |', '|---' * (len(cols) + 1) + '|']
    lines += ['| ' + ' | '.join(r) + ' |' for r in R]
    os.makedirs(RESULTS, exist_ok=True)
    open(os.path.join(RESULTS, 'VARIANTS.md'), 'w').write('\n'.join(lines) + '\n')
    print('\n'.join(lines))


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 allow_abbrev=False)
    ap.add_argument('names', nargs='*', metavar='NAME', help='variants to compare: %s' % ', '.join(data.VARIANTS))
    names = ap.parse_args().names
    bad = [n for n in names if n not in data.VARIANTS]
    if bad:
        ap.error('unknown variant %s (data.VARIANTS: %s)' % (', '.join(bad), ', '.join(data.VARIANTS)))
    main(names or list(data.VARIANTS))
