# -*- coding: utf-8 -*-
"""TPN2R304PL model: fitted to Toshiba's datasheet (Rev 3.0, 2019-10-18).

Toshiba publishes PSpice/LTspice models for this part, but their download
server (toshiba.semicon-storage.com docget.jsp) refused every automated
request (HTTP 403 from Akamai) when this was written, so this is a VDMOS
model fitted to the datasheet instead.  Points read off the curves:

  Fig 8.11  Ciss/Coss/Crss vs VDS (VGS 0, 1 MHz)
  Fig 8.3   ID vs VGS at VDS 10 V (transfer)
  Fig 8.6   body diode IDR vs VDS at VGS 0
  Fig 8.8   Vth vs Ta (typ 1.95 V at 25 C, 1.55 V at 100 C, 1.25 V at 150 C)
  Fig 8.9   RDS(on) vs Ta at 10 V (x1.35 at 100 C, x1.70 at 150 C vs 25 C)
  Table 6.3 Qg 41 nC at 10 V, Qgd 6.2 nC, Qgs1 9.6 nC (VDD 20 V, ID 40 A)
  Table 6.3 Qoss 27 nC at 20 V; Table 6.4 Qrr 30 nC, trr 35 ns
  Table 6.2 rg 0.5 typ / 1.0 max ohm

The capacitances (cgs, cgdmax, cgdmin, a, cjo, m, vj) are fitted by
Nelder-Mead against Fig 8.11; the gate-charge and Qoss totals are then
checked by simulation.  Package parasitics are estimates for a
3.3 x 3.3 TSON Advance (no published values): 0.25 nH common source,
0.15 nH drain, 0.5 nH gate.

Writes ../models/tpn2r304pl.lib (25, 100 and 150 C variants) and
fet_model.png.  Run: python3 run.py
"""
import os
import sys

import numpy as np
try:
    from scipy.optimize import minimize
except ImportError:          # the toolchain container has numpy only: reuse the recorded fit
    minimize = None

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

OUT = S.scratch('fet_model')
HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- datasheet
CISS = [(0.1, 3100), (1, 3000), (10, 2800), (20, 2750), (40, 2700)]
COSS = [(0.1, 2600), (1, 2250), (5, 1700), (10, 1150), (15, 750), (20, 650), (40, 430)]
CRSS = [(0.1, 650), (1, 520), (5, 330), (10, 210), (15, 100), (20, 66), (40, 47)]
TRANSFER_25 = [(3.1, 20.0), (3.27, 40.0), (3.5, 80.0)]     # Fig 8.3, VDS 10 V
VTH = {25: 1.95, 100: 1.55, 150: 1.25}                       # Fig 8.8, ID 0.3 mA
RDS_FACTOR = {25: 1.0, 100: 1.35, 150: 1.70}                 # Fig 8.9
RDS_TYP_25 = 1.8e-3

# Fixed (hand-fitted) static parameters.  Square law through Fig 8.2
# (VDS 2 V: 20 A at VGS 3.3 V, 50 A at 3.6 V) gives vto 2.85 V and
# kp 190 A/V^2; that also puts the 40 A Miller plateau at 3.5 V (Fig 8.10:
# ~3.6 V).  Fig 8.3 (VDS 10 V) sits ~0.15 V left of this: the datasheet's
# two plots do not quite agree, and the model follows the plateau.
# ksubthres 0.20 puts Vth (0.3 mA) at 1.90 V, the typical 25 C value.
STATIC = dict(vto=2.85, kp=190.0, lambda_=0.003, ksubthres=0.20,
              is_=4.6e-10, n=1.25, rb=0.5e-3, tt=1.5e-9, rs=0.15e-3)
# Body diode: n Vt = 32 mV -> 74 mV/decade: 0.69 V at 1 A, 0.76 V at 10 A,
# 0.89 V at 100 A with rb (Fig 8.6).  tt 1.5 ns stores 22 nC at 15 A, near
# the 30 nC Qrr Toshiba gives at 20 A, 100 A/us (a charge-control diode
# recovers all of it at the fast di/dt of a hard turn-on: conservative).

CAP0 = dict(cgs=2.68e-9, cgdmax=1.3e-9, cgdmin=40e-12, a=0.5, cjo=2.0e-9, m=0.55, vj=2.0)
CAPKEYS = list(CAP0)


def model_card(name, cap, static=STATIC, vto=None, kp=None, rd=None):
    s = dict(static)
    vto = s['vto'] if vto is None else vto
    kp = s['kp'] if kp is None else kp
    if rd is None:
        rd = rd_for(25, vto, kp)
    return ('.model %s VDMOS (vto=%.4g kp=%.4g lambda=%.4g ksubthres=%.3g rd=%.4g rs=%.4g '
            'cgs=%.4g cgdmax=%.4g cgdmin=%.4g a=%.4g cjo=%.4g m=%.4g vj=%.4g '
            'is=%.3g n=%.3g rb=%.3g tt=%.3g)\n' % (
                name, vto, kp, s['lambda_'], s['ksubthres'], rd, s['rs'],
                cap['cgs'], cap['cgdmax'], cap['cgdmin'], cap['a'], cap['cjo'], cap['m'], cap['vj'],
                s['is_'], s['n'], s['rb'], s['tt']))


def rd_for(temp, vto, kp):
    """Drain resistance that makes RDS(on) at VGS 10 V equal the typical
    datasheet value at temp (channel in triode: 1 / (kp (VGS - vto)))."""
    target = RDS_TYP_25 * RDS_FACTOR[temp]
    rch = 1.0 / (kp * (10.0 - vto))
    return target - rch - STATIC['rs']


def cv_netlist(card):
    vs = ' '.join(str(v) for v in [0.1, 0.3, 1, 2, 3, 5, 7, 10, 12, 15, 20, 25, 30, 40])
    return """* C-V
%s
VD1 d1 0 dc 20 ac 0
VG1 g1 0 dc 0 ac 1
M1 d1 g1 0 QF
VD2 d2 0 dc 20 ac 1
VG2 g2 0 dc 0 ac 0
M2 d2 g2 0 QF
.control
foreach v %s
  alter VD1 dc = $v
  alter VD2 dc = $v
  ac lin 1 1meg 1meg
  let cin = imag(-i(VG1))/(2*pi*1e6)
  let crs = imag(i(VD1))/(2*pi*1e6)
  let cos = imag(-i(VD2))/(2*pi*1e6)
  echo "CV $v $&cin $&crs $&cos"
end
.endc
.end
""" % (card, vs)


def run_cv(cap, tag='cv'):
    out = S.ngspice(cv_netlist(model_card('QF', cap)), OUT, tag)
    rows = [list(map(float, l.split()[1:])) for l in out.splitlines() if l.startswith('CV ')]
    return np.array(rows)


def cost(x):
    cap = {k: float(np.exp(v)) for k, v in zip(CAPKEYS, x)}
    if cap['m'] > 0.95 or cap['vj'] > 30 or cap['cgdmin'] < 10e-12:
        return 1e3
    r = run_cv(cap, 'fit')
    v = r[:, 0]
    e = 0.0
    for col, pts in ((1, CISS), (2, CRSS), (3, COSS)):
        for vd, c in pts:
            e += (np.log(np.interp(vd, v, r[:, col])) - np.log(c * 1e-12)) ** 2
    # Qoss at 20 V (27 nC) and Qgd-like integral of Crss 0..20 V
    qoss = np.trapezoid(np.interp(np.linspace(0.1, 20, 200), v, r[:, 3]), np.linspace(0.1, 20, 200))
    e += 4 * (np.log(qoss / 27e-9)) ** 2
    return e


# Result of the Nelder-Mead fit below (scipy 1.x), used when scipy is absent.
CAP_FIT = dict(cgs=2.571e-09, cgdmax=1.058e-09, cgdmin=1e-11, a=0.2593, cjo=2.353e-09, m=0.5751, vj=2.251)


def fit():
    if minimize is None:
        return dict(CAP_FIT), float('nan')
    x0 = np.log([CAP0[k] for k in CAPKEYS])
    res = minimize(cost, x0, method='Nelder-Mead',
                   options=dict(maxiter=500, xatol=1e-3, fatol=1e-4))
    cap = {k: float(np.exp(v)) for k, v in zip(CAPKEYS, res.x)}
    return cap, res.fun


def library(cap):
    """The .lib text: one subcircuit per temperature, with package
    parasitics and the internal gate resistance as separate elements so
    the die gate-source voltage can be probed (x.gi, x.si)."""
    hdr = ('* TPN2R304PL (Toshiba, 40 V 2.3 mOhm N-MOSFET, TSON Advance)\n'
           '* VDMOS fit to datasheet Rev 3.0 by ridge3-lite/v1/sim/fet_model/run.py.\n'
           '* NOT Toshiba\'s model.  Nodes: D G S.  Internal: di gi si (die).\n'
           '* rg = RG param (datasheet 0.5 typ, 1.0 max); package L estimated.\n'
           '* TT = body-diode transit time (stored charge = TT x IF): 1.5 ns default,\n'
           '* see sim/README.md on why this is the least certain parameter.\n')
    txt = [hdr]
    # 25 / 100 / 150 C typical parts, and '150Cmin': a minimum-Vth part at
    # 150 C (threshold 0.55 V lower: 1.4 V min vs 1.95 V typ at 25 C)
    for t, tag, shift in ((25, '25C', 0.0), (100, '100C', 0.0), (150, '150C', 0.0), (150, '150Cmin', -0.55)):
        dv = VTH[t] - VTH[25] + shift
        vto = STATIC['vto'] + dv
        kp = STATIC['kp'] * ((273.15 + t) / 298.15) ** -1.5
        rd = rd_for(t, vto, kp)
        name = 'TPN2R304PL_%s' % tag
        card = model_card('QCORE_%s' % tag, cap, vto=vto, kp=kp, rd=rd).replace(
            'tt=%.3g' % STATIC['tt'], 'tt={TT}')
        txt.append('.subckt %s D G S params: RG=0.7 TT=%.3g\n'
                   'Ld D di 0.15n\nLg G gx 0.5n\nRgi gx gi {RG}\nLs si S 0.25n\n'
                   'M1 di gi si QCORE_%s\n%s.ends\n' % (name, STATIC['tt'], tag, card))
    return '\n'.join(txt)


def validate(lib):
    """Transfer curves, RDS(on) at 10 V, Vth at 0.3 mA, body diode and a
    gate-charge curve (VDD 20 V, 40 A clamped inductive load, 1 mA gate)."""
    res = {}
    net = """* validate
.include %s
XQ25 d25 g 0 TPN2R304PL_25C
XQ150 d150 g 0 TPN2R304PL_150C
VD25 d25 0 10
VD150 d150 0 10
VG g 0 0
.control
dc VG 0 5 0.01
%s
.endc
.end
""" % (lib, S.control_save(['i(VD25)', 'i(VD150)'], 'transfer.dat'))
    S.ngspice(net, OUT, 'transfer')
    d = S.wrdata(os.path.join(OUT, 'transfer.dat'))
    res['transfer'] = (d['v-sweep'], -d['i(vd25)'], -d['i(vd150)'])
    for t, idv in ((25, -d['i(vd25)']), (150, -d['i(vd150)'])):
        res['vth%d' % t] = float(np.interp(3e-4, idv, d['v-sweep']))

    # RDS(on) at VGS 10 V, ID 40 A, and the body diode at VGS 0
    rds = {}
    for t in (25, 100, 150):
        net = """* rds
.include %s
XQ d g 0 TPN2R304PL_%dC
ID 0 d 40
VG g 0 10
.control
op
echo "RDS $&v(d)"
.endc
.end
""" % (lib, t)
        out = S.ngspice(net, OUT, 'rds%d' % t)
        rds[t] = float([l for l in out.splitlines() if l.startswith('RDS ')][0].split()[1]) / 40
    res['rds'] = rds
    net = """* body diode
.include %s
XQ d 0 0 TPN2R304PL_25C
ID d 0 1
.control
dc ID 0.1 200 0.1
%s
.endc
.end
""" % (lib, S.control_save(['v(d)'], 'diode.dat'))
    S.ngspice(net, OUT, 'diode')
    d = S.wrdata(os.path.join(OUT, 'diode.dat'))
    res['diode'] = (d['i-sweep'], -d['v(d)'])

    # Gate charge: drain current source 40 A from 20 V, clamped by a fast
    # ideal diode to VDD (inductive load), gate charged by ~1 mA (1000 V through 1 Mohm).
    net = """* gate charge
.include %s
.model DCL D (is=1e-12 n=1 rs=1m cjo=200p)
VDD vdd 0 20
IL vdd d 40
DCL d vdd DCL
XQ d g 0 TPN2R304PL_25C
VGG gg 0 pulse(0 1000 1u 1n 1n 1 2)
RGG gg g 1meg
.nodeset v(d)=20.8 v(g)=0
.control
tran 0.5n 51u
%s
.endc
.end
""" % (lib, S.control_save(['v(g)', 'v(d)'], 'qg.dat'))
    S.ngspice(net, OUT, 'qg')
    d = S.wrdata(os.path.join(OUT, 'qg.dat'))
    ig = (1000.0 - d['v(g)']) / 1e6 * (d['time'] > 1e-6)
    q = np.concatenate([[0], np.cumsum(0.5 * (ig[1:] + ig[:-1]) * np.diff(d['time']))]) * 1e9   # nC
    res['qg'] = (q, d['v(g)'], d['v(d)'])
    res['qg10'] = float(np.interp(10.0, d['v(g)'], q))
    vg = d['v(g)']
    # plateau: where VDS swings 90 % -> 10 % of VDD
    vd = d['v(d)']
    i1 = np.argmax(vd < 18.0)
    i2 = np.argmax(vd < 2.0)
    res['qgd'] = float(q[i2] - q[i1])
    res['vplateau'] = float(vg[(i1 + i2) // 2])
    res['qgs'] = float(q[i1])
    return res


def main():
    cap, err = fit()
    lib = library(cap)
    os.makedirs(S.MODELS, exist_ok=True)
    libpath = os.path.join(S.MODELS, 'tpn2r304pl.lib')
    # rewrite only on change: the half-bridge study re-simulates when the lib is newer
    if not os.path.exists(libpath) or open(libpath).read() != lib:
        with open(libpath, 'w') as f:
            f.write(lib)
    cv = run_cv(cap, 'cv_final')
    v = cv[:, 0]
    qoss20 = np.trapezoid(np.interp(np.linspace(0, 20, 400), v, cv[:, 3]), np.linspace(0, 20, 400))
    val = validate(libpath)

    plt = S.style()
    fig, ax = plt.subplots(2, 3, figsize=(13, 7.5))
    a = ax[0, 0]
    for col, pts, lab in ((1, CISS, 'Ciss'), (3, COSS, 'Coss'), (2, CRSS, 'Crss')):
        l, = a.loglog(v, cv[:, col] * 1e12, label=lab + ' model')
        a.loglog(*zip(*pts), 'o', color=l.get_color(), mfc='none', label=lab + ' datasheet')
    a.set_xlabel('VDS (V)'); a.set_ylabel('pF'); a.set_title('Capacitance vs VDS (Fig 8.11)')
    a.legend(fontsize=7)
    a = ax[0, 1]
    vg, i25, i150 = val['transfer']
    a.plot(vg, i25, label='25 C model'); a.plot(vg, i150, label='150 C model')
    a.plot(*zip(*TRANSFER_25), 'o', mfc='none', color='C0', label='25 C Fig 8.3 (VDS 10 V)')
    a.plot([3.3, 3.6, 4.0], [20, 50, 140], 's', mfc='none', color='C2', label='25 C Fig 8.2 (VDS 2 V)')
    a.set_ylim(0, 150); a.set_xlim(1, 5); a.set_xlabel('VGS (V)'); a.set_ylabel('ID (A) at VDS 10 V')
    a.set_title('Transfer (Fig 8.3)'); a.legend()
    a = ax[0, 2]
    q, g, dd = val['qg']
    a.plot(q, g, label='VGS'); a.set_xlim(0, 50); a.set_ylim(0, 12)
    a.axhline(10, color='0.6', lw=0.6); a.axvline(41, color='0.6', lw=0.6)
    a2 = a.twinx(); a2.plot(q, dd, color='C1', label='VDS'); a2.set_ylim(0, 40)
    a2.set_ylabel('VDS (V)')
    a.set_xlabel('Qg (nC)'); a.set_ylabel('VGS (V)')
    a.set_title('Gate charge, VDD 20 V, 40 A: Qg(10 V) %.1f nC (ds 41)' % val['qg10'])
    a = ax[1, 0]
    ii, vf = val['diode']
    a.semilogy(vf, ii, label='model 25 C')
    a.semilogy([0.69, 0.765, 0.89, 0.95], [1, 10, 100, 200], 'o', mfc='none', label='datasheet')
    a.set_xlabel('VSD (V)'); a.set_ylabel('IDR (A)'); a.set_title('Body diode (Fig 8.6)'); a.legend()
    a = ax[1, 1]
    ts = [25, 100, 150]
    a.plot(ts, [val['rds'][t] * 1e3 for t in ts], 'o-', label='model typ')
    a.plot(ts, [RDS_TYP_25 * RDS_FACTOR[t] * 1e3 for t in ts], 's', mfc='none', label='datasheet typ (Fig 8.9)')
    a.plot(ts, [2.3 * RDS_FACTOR[t] for t in ts], '^--', label='datasheet max x Fig 8.9 factor')
    a.set_xlabel('Tj (C)'); a.set_ylabel('RDS(on) mOhm at 10 V'); a.set_title('RDS(on) vs Tj'); a.legend()
    a = ax[1, 2]; a.axis('off')
    txt = ('Fitted capacitance parameters\n' +
           '\n'.join('  %-7s %.4g' % (k, cap[k]) for k in CAPKEYS) +
           '\n\nChecks (model vs datasheet)\n'
           '  Qg at 10 V    %.1f nC  (41 typ)\n'
           '  Qgd           %.1f nC  (6.2 typ)\n'
           '  Qgs (to 90%%)  %.1f nC  (Qgs1 9.6)\n'
           '  plateau       %.2f V\n'
           '  Qoss 0-20 V   %.1f nC  (27 typ)\n'
           '  Vth @0.3 mA   %.2f V 25 C, %.2f V 150 C\n'
           '                (1.4-2.4 V spec; 1.95/1.25 typ curve)\n'
           '  RDS 10 V      %.2f / %.2f / %.2f mOhm @25/100/150 C' % (
               val['qg10'], val['qgd'], val['qgs'], val['vplateau'], qoss20 * 1e9,
               val['vth25'], val['vth150'], val['rds'][25] * 1e3, val['rds'][100] * 1e3, val['rds'][150] * 1e3))
    a.text(0, 1, txt, va='top', family='monospace', fontsize=8)
    fig.suptitle('TPN2R304PL: VDMOS model fitted to the datasheet (Toshiba model download was blocked)')
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'fet_model.png'))
    with open(os.path.join(HERE, 'results.txt'), 'w') as f:
        f.write(txt + '\n')
    print(txt)


if __name__ == '__main__':
    main()
