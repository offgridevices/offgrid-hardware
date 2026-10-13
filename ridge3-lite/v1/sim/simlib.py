# -*- coding: utf-8 -*-
"""Small helpers shared by the studies: run ngspice in batch mode, read its
wrdata output, and keep every plot in the same plain style.

ngspice 44 (`ngspice -b`) and Python 3 with numpy + matplotlib are all a
study needs.  Scratch files (netlists as run, raw data) go to
<repo>/out/sim/<study>/, which is gitignored; plots and tables land next to
the study's run.py.
"""
import os
import subprocess

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
MODELS = os.path.join(HERE, 'models')


def scratch(study):
    d = os.path.join(REPO, 'out', 'sim', study)
    os.makedirs(d, exist_ok=True)
    return d


def ngspice(netlist, workdir, name, timeout=600):
    """Write netlist to workdir/name.cir, run ngspice -b there, return stdout.

    Raises RuntimeError if ngspice reports a fatal error or a timestep
    failure, so a broken simulation never produces a silently wrong plot."""
    path = os.path.join(workdir, name + '.cir')
    with open(path, 'w') as f:
        f.write(netlist)
    p = subprocess.run(['ngspice', '-b', path], cwd=workdir, capture_output=True,
                       text=True, timeout=timeout)
    out = p.stdout + p.stderr
    with open(os.path.join(workdir, name + '.log'), 'w') as f:
        f.write(out)
    bad = ('Error:', 'error:', 'Timestep too small', 'singular matrix', 'aborted')
    for line in out.splitlines():
        if any(b in line for b in bad) and 'warning' not in line.lower():
            raise RuntimeError('ngspice failed on %s: %s (see %s.log)' % (name, line.strip(), name))
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
