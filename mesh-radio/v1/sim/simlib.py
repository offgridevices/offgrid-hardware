# -*- coding: utf-8 -*-
"""Small helpers shared by the studies: run ngspice in batch mode, read its
wrdata output, write results, and keep every plot in the same plain style
(the same helpers as ridge3-lite/v1/sim/simlib.py).

ngspice (`ngspice -b`, 44 tested) and Python 3 with numpy + matplotlib are
all a study needs.  From mesh-radio/v1 the pinned toolchain container has
both: `tools/kd python3 sim/<study>/run.py`.  Scratch files (netlists as
run, ngspice logs, raw data) go to sim/out/<study>/, which the repository's
`out/` rule ignores; results.txt, stress.json and plots land next to the
study's run.py.
"""
import json
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))


def scratch(study):
    d = os.path.join(HERE, 'out', study)
    os.makedirs(d, exist_ok=True)
    return d


class TimestepError(RuntimeError):
    """ngspice stopped with 'timestep too small' at time .t (the rawfile up
    to that point has been written)."""
    def __init__(self, msg, t=0.0):
        RuntimeError.__init__(self, msg)
        self.t = t

    def __reduce__(self):
        return (TimestepError, (str(self), self.t))


OPTS = ['.option method=gear reltol=2e-3 abstol=1e-9 vntol=1e-5 itl4=200',
        '.option method=trap reltol=3e-3 abstol=1e-8 vntol=1e-5 itl4=300',
        '.option method=gear reltol=5e-3 abstol=1e-7 vntol=1e-4 itl4=500 gmin=1e-10']


def ngspice_retry(make, workdir, name, timeout=900):
    """Run make(option_line) through ngspice with each of OPTS until one
    finishes.  Returns None, or the time at which the last attempt stopped
    with 'timestep too small' (its rawfile holds the data up to there: the
    studies treat that as a collapse of the circuit and say so)."""
    stopped = None
    for o in OPTS:
        try:
            ngspice(make(o), workdir, name, timeout=timeout)
            return None
        except TimestepError as e:
            stopped = e.t
    return stopped


def ngspice(netlist, workdir, name, timeout=900):
    """Write netlist to workdir/name.cir, run ngspice -b there, return stdout.

    Raises RuntimeError if ngspice reports a fatal error or a timestep
    failure (TimestepError), so a broken simulation never produces a
    silently wrong plot."""
    path = os.path.join(workdir, name + '.cir')
    with open(path, 'w') as f:
        f.write(netlist)
    p = subprocess.run(['ngspice', '-b', path], cwd=workdir, capture_output=True,
                       text=True, timeout=timeout)
    out = p.stdout + p.stderr
    with open(os.path.join(workdir, name + '.log'), 'w') as f:
        f.write(out)
    bad = ('Error:', 'error:', 'Timestep too small', 'singular matrix', 'aborted',
           'doAnalyses: TRAN:')
    for line in out.splitlines():
        if 'Timestep too small' in line:
            import re
            m = re.search(r'time = ([0-9.eE+-]+)', line)
            raise TimestepError('ngspice stopped on %s: %s' % (name, line.strip()), float(m.group(1)) if m else 0.0)
        if any(b in line for b in bad) and 'warning' not in line.lower():
            raise RuntimeError('ngspice failed on %s: %s (see %s/%s.log)' % (name, line.strip(), workdir, name))
    return out


def wrdata(path):
    """Read a file written by ngspice `wrdata` with wr_singlescale and
    wr_vecnames set: a header line of names, then columns."""
    with open(path) as f:
        names = f.readline().lower().split()
    data = np.loadtxt(path, skiprows=1, ndmin=2)
    return {n: data[:, i] for i, n in enumerate(names)}


def control_save(vectors, fname):
    """ngspice .control lines that write the given vectors to fname."""
    return ('set wr_singlescale\nset wr_vecnames\noption numdgt=7\n'
            'wrdata %s %s\n' % (fname, ' '.join(vectors)))


def style():
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        'figure.dpi': 110, 'savefig.dpi': 110, 'font.size': 9,
        'axes.grid': True, 'grid.alpha': 0.3, 'axes.spines.top': False,
        'axes.spines.right': False, 'legend.frameon': False,
        'axes.prop_cycle': matplotlib.cycler(color=[
            '#2a6fdb', '#e8590c', '#2b8a3e', '#c2255c', '#7048e8', '#495057', '#f59f00']),
    })
    return plt


def table(rows, header):
    """Plain fixed-width text table (for stdout and results.txt)."""
    cols = [header] + [[('%.4g' % c) if isinstance(c, float) else str(c) for c in r] for r in rows]
    w = [max(len(r[i]) for r in cols) for i in range(len(header))]
    lines = ['  '.join(c.rjust(w[i]) for i, c in enumerate(r)) for r in cols]
    lines.insert(1, '  '.join('-' * x for x in w))
    return '\n'.join(lines)


def verdict(ok, marginal=False):
    return 'PASS' if ok and not marginal else ('MARGINAL' if ok else 'FAIL')


def write_results(here, lines):
    txt = '\n'.join(lines)
    with open(os.path.join(here, 'results.txt'), 'w') as f:
        f.write(txt + '\n')
    print(txt)


def write_stress(here, rows):
    """Worst-case stress rows for the derating table (derating/run.py reads
    every <study>/stress.json).  Each row: part, ref/net, quantity, value,
    unit, rating, rating_kind ('derate' = E4 70 % rule applies, 'absmax' =
    must stay below, 'rec' = recommended maximum), case (where it came from)."""
    with open(os.path.join(here, 'stress.json'), 'w') as f:
        json.dump(rows, f, indent=1)


def stress(part, ref, qty, value, unit, rating, kind, case):
    return dict(part=part, ref=ref, qty=qty, value=float(value), unit=unit, rating=float(rating),
                kind=kind, case=case)


def rawread(path):
    """Read an ngspice binary rawfile (`set filetype=binary`, `write`):
    returns {name: array}, names lower-case as ngspice prints them."""
    with open(path, 'rb') as f:
        blob = f.read()
    i = blob.index(b'Binary:\n')
    head = blob[:i].decode('ascii', 'replace').splitlines()
    nvar = npts = None
    names = []
    invars = False
    for line in head:
        if line.startswith('No. Variables:'):
            nvar = int(line.split(':')[1])
        elif line.startswith('No. Points:'):
            npts = int(line.split(':')[1])
        elif line.startswith('Variables:'):
            invars = True
        elif invars and line.strip():
            parts = line.split()
            names.append(parts[1].lower())
    data = np.frombuffer(blob[i + 8:], dtype='<f8', count=nvar * npts).reshape(npts, nvar)
    return {n: data[:, k].copy() for k, n in enumerate(names)}
