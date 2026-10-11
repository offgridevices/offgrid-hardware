"""SmokeBreak v1 simulation helpers: run ngspice decks with parameter overrides,
parse wrdata output, small measurement utilities and plot styling."""
import os
import re
import subprocess
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

NGSPICE = "/usr/local/bin/ngspice"
SIM = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(SIM, "work")
PLOTS = os.path.join(SIM, "plots")
os.makedirs(WORK, exist_ok=True)
os.makedirs(PLOTS, exist_ok=True)

# categorical palette (fixed order, reference instance)
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": INK2, "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False,
    "lines.linewidth": 1.6, "font.size": 9, "axes.titlesize": 10, "legend.frameon": False,
    "axes.prop_cycle": matplotlib.cycler(color=C),
})


def ngspice_version():
    out = subprocess.run([NGSPICE, "-v"], capture_output=True, text=True).stdout
    m = re.search(r"ngspice-(\S+)", out)
    return m.group(1) if m else "?"


class SimError(RuntimeError):
    pass


def run(cir, tag, params=None, repl=None, timeout=180):
    """Run sim/<cir> with .param overrides; return dict of numpy arrays.
    The deck must write its data with `wrdata work/<something>.dat`."""
    src = open(os.path.join(SIM, cir)).read()
    for k, v in (params or {}).items():
        pat = re.compile(r"(^\.param\b[^\n]*?\b%s=)(\S+)" % re.escape(k), re.M)
        if not pat.search(src):
            raise SimError(f"{cir}: no .param {k}")
        src = pat.sub(lambda m: m.group(1) + str(v), src, count=1)
    for a, b in (repl or {}).items():
        if a not in src:
            raise SimError(f"{cir}: replace target not found: {a}")
        src = src.replace(a, b)
    src, n = re.subn(r"wrdata\s+work/\S+", f"wrdata work/{tag}.dat", src)
    if n != 1:
        raise SimError(f"{cir}: need exactly one wrdata line")
    deck = os.path.join(WORK, f"{tag}.cir")
    dat = os.path.join(WORK, f"{tag}.dat")
    open(deck, "w").write(src)
    if os.path.exists(dat):
        os.remove(dat)
    p = subprocess.run([NGSPICE, "-b", deck], cwd=SIM, capture_output=True, text=True, timeout=timeout)
    log = p.stdout + p.stderr
    open(os.path.join(WORK, f"{tag}.log"), "w").write(log)
    if "Timestep too small" in log or "aborted" in log or not os.path.exists(dat):
        raise SimError(f"{tag}: ngspice failed\n" + "\n".join(log.splitlines()[-15:]))
    a = np.genfromtxt(dat, names=True)
    return {n: np.atleast_1d(a[n]) for n in a.dtype.names}


def at(t, y, tt):
    return float(np.interp(tt, t, y))


def first_cross(t, y, level, rising=True, t0=0.0):
    m = (t >= t0) & ((y >= level) if rising else (y <= level))
    idx = np.nonzero(m)[0]
    return float(t[idx[0]]) if len(idx) else None


def integ(t, y, t0=None, t1=None):
    m = np.ones_like(t, bool)
    if t0 is not None:
        m &= t >= t0
    if t1 is not None:
        m &= t <= t1
    return float(np.trapezoid(y[m], t[m])) if m.sum() > 1 else 0.0


def worst_window_power(t, p, win):
    """Highest average power over any window of length `win` (s)."""
    tu = np.linspace(t[0], t[-1], max(2000, int((t[-1] - t[0]) / (win / 50)) + 1))
    pu = np.interp(tu, t, p)
    e = np.concatenate([[0], np.cumsum(0.5 * (pu[1:] + pu[:-1]) * np.diff(tu))])
    n = max(1, int(round(win / (tu[1] - tu[0]))))
    if n >= len(tu):
        return e[-1] / (tu[-1] - tu[0])
    return float(np.max(e[n:] - e[:-n]) / win)


def savefig(fig, name):
    path = os.path.join(PLOTS, name)
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return path


def fmt(x, nd=3, unit=""):
    if x is None:
        return "n/a"
    if isinstance(x, str):
        return x
    a = abs(x)
    for f, p in ((1e-9, "n"), (1e-6, "u"), (1e-3, "m"), (1, ""), (1e3, "k")):
        if a < f * 1000 or p == "k":
            return f"{x / f:.{nd}g} {p}{unit}".strip()
    return f"{x:.{nd}g} {unit}"
