"""Write the *Verdict* section of sim/README.md from the studies' own
results.txt files, so it cannot drift from them (PR #13 review, 6 Nov 2026:
the hand-kept table still showed the first routing's results).

    python3 sim/verdict.py          # rewrites the block between the verdict markers in sim/README.md

Reads: hotplug, reverse, shorts, burst, solar, derating (power, this folder),
rf/results.txt, thermal/results.txt, extract.txt.  Writes nothing else.
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
TEMPS = ['-40 C', '-20 C', '0 C', '25 C', '60 C', '85 C']
BEGIN, END = '<!-- verdict:begin (sim/verdict.py writes this block) -->', '<!-- verdict:end -->'
SHORT = {'PASS': 'PASS', 'MARGINAL': 'MARG', 'FAIL': '**FAIL**'}


def read(*p):
    return open(os.path.join(HERE, *p)).read().split('\n')


def block(lines, title):
    """The fixed-width table after a line equal to `title`: rows up to the first blank line."""
    i = lines.index(title)
    out = []
    for ln in lines[i + 3:]:
        if not ln.strip() or ln.startswith('  '):
            break
        out.append(ln)
    return out


def case_table(study, label):
    L = read(study, 'results.txt')
    i = L.index('Verdict per case and ambient:')
    rows = []
    for ln in L[i + 3:]:
        t = ln.split()
        if len(t) < 7 or any(x not in SHORT for x in t[-6:]):
            break
        rows.append(['%s: %s' % (label, ' '.join(t[:-6]))] + [SHORT[x] for x in t[-6:]] + [''])
    return rows


def trip_row():
    L = read('shorts', 'results.txt')
    i = [k for k, ln in enumerate(L) if ln.startswith('OCD / SCD trip currents')][0]
    d = {}
    for ln in L[i + 4:i + 10]:
        t = ln.split()
        d[t[0] + ' C'] = '%.1f-%.1f A' % (float(t[2]), float(t[3]))
    return [['shorts: the cell protector\'s over-current (OCD) trip, min-max'] + [d.get(t, '') for t in TEMPS] + ['']]


def burst_rows():
    L = read('burst', 'results.txt')
    i = L.index('Highest PA level that passes, battery only (R_int at 25 C in the header) = the firmware cap:')
    cap = {}
    for ln in L[i + 3:]:
        m = re.match(r'\s*new\s+(-?\d+) C\s+([\d.]+) V\s+(.*)$', ln)
        if not m:
            break
        cells = re.split(r'\s{2,}', m.group(3).strip())
        for r, c in zip(('50', '150', '300'), cells):
            cap.setdefault((m.group(2), r), {})[m.group(1) + ' C'] = c.replace(' dBm', ' dBm ').split('(')[-1].rstrip(')') if c != 'none' else 'none'
    rows = []
    for (ocv, r), d in sorted(cap.items(), key=lambda kv: (-float(kv[0][0]), int(kv[0][1]))):
        rows.append(['burst, battery only: highest passing level, cell %s V / %s mOhm' % (ocv, r)] +
                    [d.get(t, '') for t in TEMPS] + ['the firmware battery cap; heat caps it lower (thermal rows)'])
    for ln in L:
        m = re.match(r'\s*((?:u|n|h)_\S+)\s+(-?\d+ C)\s.*?\b(PASS|FAIL|MARGINAL)\b\s*(.*)$', ln)
        if m:
            row = ['burst case %s' % m.group(1)] + [''] * 6 + [m.group(4).strip()]
            row[1 + TEMPS.index(m.group(2))] = SHORT[m.group(3)]
            rows.append(row)
    return rows


def solar_rows():
    L = read('solar', 'results.txt')
    worst = {}
    for ln in L:
        t = ln.split()
        m = None
        if t and t[-1] in ('PASS', 'FAIL', 'MARGINAL'):
            for k_ in range(len(t) - 1):
                if t[k_ + 1:k_ + 2] == ['C'] and t[k_] + ' C' in TEMPS:
                    m = (t[k_] + ' C', t[-1])
                    break
        if m:
            m = type('M', (), {'group': lambda self, i, m=m: m[i - 1]})()
            o = ['PASS', 'MARGINAL', 'FAIL']
            w = worst.get(m.group(1), 'PASS')
            worst[m.group(1)] = max(w, m.group(2), key=o.index)
    return [['solar: 6 V panel and USB charge path, every case'] + [SHORT[worst.get(t, 'PASS')] for t in TEMPS] + ['']]


def fixed_width(lines, start):
    """Rows of the fixed-width table whose dashes line is lines[start + 1]: dicts by header name."""
    head, dash = lines[start], lines[start + 1]
    spans = [(m.start(), m.end()) for m in re.finditer(r'-+', dash)]
    spans = [(a_, spans[k + 1][0] if k + 1 < len(spans) else None) for k, (a_, _) in enumerate(spans)]
    names = [head[a_:b_].strip() for a_, b_ in spans]
    out = []
    for ln in lines[start + 2:]:
        if not ln.strip():
            break
        out.append({n: ln[a_:b_].strip() for n, (a_, b_) in zip(names, spans)})
    return out


def derating_rows():
    L = read('derating', 'results.txt')
    tot = [ln for ln in L if re.match(r'\d+ rows: ', ln)][0]
    rows = [['derating (E4): ' + tot.rstrip('.')] + [''] * 6 + ['']]
    k = [i for i, ln in enumerate(L) if ln.strip().startswith('part') and 'verdict' in ln][0]
    order = {'FAIL': 0, 'OVER (owner-accepted)': 1, 'MARGINAL': 2}
    for r in sorted((r for r in fixed_width(L, k) if r['verdict'] in order), key=lambda r: order[r['verdict']]):
        rows.append(['derating %s: %s (%s): %s' % (r['verdict'], r['part'], r['where'], r['quantity'])] + [''] * 6 +
                    ['%s against %s (%s, rule %s)%s' % (r['worst case'], r['rating'], r['%'], r['rule'],
                                                         ('; ' + r['case / note']) if r.get('case / note') else '')])
    return rows


def rf_rows():
    L = read('rf', 'results.txt')
    i = L.index('SUMMARY')
    rows = []
    for ln in L[i + 2:]:
        m = re.match(r'\s+(\S+)\s+(.*?)\s+(PASS|FAIL|MARGINAL)\s+(.*)$', ln)
        if m:
            rows.append(['rf study %s: %s' % (m.group(1), m.group(2).strip())] + [''] * 6 +
                        ['%s: %s' % (m.group(3), m.group(4).strip())])
    return rows


def thermal_rows():
    L = read('thermal', 'results.txt')
    i = [k for k, ln in enumerate(L) if ln.startswith('--- Highest transmit duty cycle that passes every criterion')][0]
    rows = []
    for ln in L[i + 3:i + 6]:
        m = re.match(r'\s+(\S+)\s+(.*)$', ln)
        cells = dict(re.findall(r'(-?\d+ C): ([^|]+?)\s*(?:\||$)', m.group(2)))
        rows.append(['thermal: highest passing transmit duty at %s, 1 s messages, no gap pad, no charging' % m.group(1)] +
                    [cells.get(t, '').strip() for t in TEMPS] + [''])
    return rows


def extract_rows():
    L = read('extract.txt')
    rows = []
    for ln in L:
        m = re.match(r'  ((?:TRACE_\w+|SENSE_TRACE)) = (.*)$', ln)
        if m:
            rows.append(['copper (extract.py): %s' % m.group(1)] + [''] * 6 + ['(R ohm, L H) = %s' % m.group(2)])
    return rows


def main():
    rows = (case_table('hotplug', 'hotplug') + case_table('reverse', 'reverse') + case_table('shorts', 'shorts') + trip_row() +
            burst_rows() + solar_rows() + derating_rows() + thermal_rows() + rf_rows() + extract_rows())
    md = ['| study / case | ' + ' | '.join(TEMPS) + ' | note |', '|---' * 8 + '|']
    for r in rows:
        md.append('| ' + ' | '.join(c.replace('|', '/') for c in r) + ' |')
    text = '\n'.join([BEGIN, '', 'Generated by `sim/verdict.py` from each study\'s `results.txt` (rf, thermal, the power',
                      'studies, `extract.txt`); re-run it after any study.  Notes are copied from those files.', ''] + md + ['', END])
    p = os.path.join(HERE, 'README.md')
    s = open(p).read()
    if BEGIN in s:
        a, b = s.index(BEGIN), s.index(END) + len(END)
        s = s[:a] + text + s[b:]
    else:
        raise SystemExit('no verdict markers in %s' % p)
    open(p, 'w').write(s)
    print('verdict: %d rows' % len(rows))


if __name__ == '__main__':
    main()
