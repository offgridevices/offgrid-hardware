# -*- coding: utf-8 -*-
"""Follow-up to run.py: ways to tame the switching overshoot without 24
switch-node snubbers (board area is the constraint).

  A  asymmetric gate resistors, no snubber: high side Rg_H 10/15/22/33 ohm,
     low side Rg_L 4.7 or 3.3 ohm
  B  a DC-link RC damper per phase where the bridge cap sits (VBAT to SRC,
     1 nH incl. two 0.5 mm vias), 1 ohm + 22 nF or 2.2 ohm + 10 nF, gates 4.7
  C  combinations: A + a gate-source cap on the low side, A + B

Same model and circuit as run.py; 15 and 30 A, loop 2 and 4 nH, Tj 25 and
150 C.  Pass criteria (from the brief):
  peak die VDS (either FET) <= 34 V at 15 A / 2 nH, <= 40 V at 30 A / 4 nH
  (abuse); GLx >= -5 V; switch-node 10-90 % dV/dt <= 2 V/ns (DRV8300D);
  low-side Miller bump < 0.7 V at 150 C (goal, "if possible").

Writes options.txt and options.png.  Run: python3 options.py (after run.py
has built the FET library).
"""
import os
import sys
from multiprocessing import Pool

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run as H
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
import simlib as S

HERE = os.path.dirname(os.path.abspath(__file__))

CONFIGS = [('as drawn, 4.7/4.7', 4.7, None)]
for rh in (10, 15, 22, 33):
    for rl in (4.7, 3.3):
        CONFIGS.append(('A: Rg_H %g / Rg_L %g' % (rh, rl), (rh, rl), None))
for rh, rl in ((15, 10), (15, 15), (22, 10), (22, 22)):
    CONFIGS.append(('A: Rg_H %g / Rg_L %g' % (rh, rl), (rh, rl), None))
CONFIGS += [('B: damper 1R + 22n', 4.7, (('dc', 1.0, 22e-9),)),
            ('B: damper 2.2R + 10n', 4.7, (('dc', 2.2, 10e-9),)),
            ('C: Rg_H 22/4.7 + Cgs_L 2.2n', (22, 4.7), (('cgsl', 2.2e-9),)),
            ('C: Rg_H 22/4.7 + Cgs_L 4.7n', (22, 4.7), (('cgsl', 4.7e-9),)),
            ('C: Rg_H 15/4.7 + Cgs_L 2.2n', (15, 4.7), (('cgsl', 2.2e-9),)),
            ('C: Rg_H 10/4.7 + damper 1R+22n', (10, 4.7), (('dc', 1.0, 22e-9),)),
            ('C: Rg_H 15/4.7 + damper 1R+22n', (15, 4.7), (('dc', 1.0, 22e-9),)),
            ('ref: 1R+4.7n sw-SRC snubber', 4.7, (('low', 1.0, 4.7e-9),))]
CASES = [(I, L, T) for I in (15, 30) for L in (2e-9, 4e-9) for T in (25, 150)]
LIGHT = [(5, 2e-9, 150), (0.5, 2e-9, 150)]          # Miller bump is largest at light load
# braking / regen: phase current INTO the switch node, so the low side
# hard-switches at its turn-on and the high side's diode recovers
NEG = [(I, L, T) for I, L in ((-15, 2e-9), (-30, 4e-9)) for T in (25, 150)]
# a minimum-Vth part at 150 C (Tj code 151): does the Miller bump turn it on?
MINV = [(15, 2e-9, 151), (-15, 2e-9, 151), (30, 4e-9, 151), (-30, 4e-9, 151), (0.5, 2e-9, 151)]


def job(cfg, I, L, T):
    return (I, cfg[1], L, T, H.TT0, cfg[2])


def main():
    jobs = sorted({job(c, *k) for c in CONFIGS for k in CASES + LIGHT + NEG + MINV}, key=str)
    with Pool(4) as pool:
        res = dict(pool.map(H.simulate, jobs))

    def r(c, I, L, T):
        return res[job(c, I, L, T)]

    rows, summary = [], []
    for c in CONFIGS:
        for (I, L, T) in CASES:
            x = r(c, I, L, T)
            rows.append([c[0], I, '%g nH' % (L * 1e9), T, x['vds_l_pk_all'], x['vds_h_pk_all'],
                         x['dvdt_rise'], x['dvdt_rise_pk'], x['dvdt_fall'], x['vgs_l_bump'], x['gld_min'],
                         x['eon'] * 1e6, x['eoff'] * 1e6])
        v15 = max(max(r(c, 15, 2e-9, T)['vds_l_pk_all'], r(c, 15, 2e-9, T)['vds_h_pk_all']) for T in (25, 150))
        v30 = max(max(r(c, 30, 4e-9, T)['vds_l_pk_all'], r(c, 30, 4e-9, T)['vds_h_pk_all']) for T in (25, 150))
        gl = min(r(c, *k)['gld_min'] for k in CASES)
        dv = max(r(c, *k)['dvdt_rise'] for k in CASES + LIGHT)
        bump150 = max(r(c, *k)['vgs_l_bump'] for k in CASES + LIGHT if k[2] == 150)
        bump150_15 = max(r(c, I, L, 150)['vgs_l_bump'] for I in (15, 30) for L in (2e-9, 4e-9))
        e15 = r(c, 15, 2e-9, 150)
        e30 = r(c, 30, 2e-9, 150)
        psw = [(e['eon'] + e['eoff']) * f for e in (e15, e30) for f in (24e3, 48e3)]
        b15 = max(max(r(c, -15, 2e-9, T)['vds_h_pk_all'], r(c, -15, 2e-9, T)['vds_l_pk_all']) for T in (25, 150))
        b30 = max(max(r(c, -30, 4e-9, T)['vds_h_pk_all'], r(c, -30, 4e-9, T)['vds_l_pk_all']) for T in (25, 150))
        gl = min(gl, min(r(c, *k)['gld_min'] for k in NEG))
        hb150 = max(r(c, *k)['vgs_h_bump_lon'] for k in NEG if k[2] == 150)
        # shoot-through cost: switching energy of a min-Vth part vs a typical part, 150 C
        def etot(I, L, T):
            x = r(c, I, L, T)
            return x['elon'] if I < 0 else x['eon'] + x['eoff']
        st = max((etot(I, L, 151) / etot(I, L, 150) - 1) * 100 for I, L in ((15, 2e-9), (-15, 2e-9), (30, 4e-9), (-30, 4e-9)))
        vmin = max(max(r(c, *k)['vds_h_pk_all'], r(c, *k)['vds_l_pk_all']) for k in MINV if k[0] != 0.5)
        ok = (v15 <= 34 and v30 <= 40 and b15 <= 34 and b30 <= 40 and gl >= -5 and dv <= 2.0)
        summary.append([c[0], v15, v30, b15, b30, dv, gl, bump150, hb150, psw[0], psw[1], psw[2], psw[3],
                        st, vmin, 'PASS' if ok else 'fail'])
    hdr = ['config', 'I', 'Lloop', 'Tj', 'VDS_L pk', 'VDS_H pk', 'dV/dt rise', 'pk', 'fall', 'VGS_L bump',
           'GL min', 'Eon uJ', 'Eoff uJ']
    txt = ['Options study (options.py).  Same model and circuit as run.py; VBUS 17.4 V.  Voltages at the die.\n'
           'Criteria: VDS <= 34 V at 15 A / 2 nH and <= 40 V at 30 A / 4 nH (worst of Tj 25 / 150 C), motoring\n'
           'and braking (phase current -15 / -30 A: the low side hard-switches);\n'
           'GLx >= -5 V; 10-90 % rising dV/dt <= 2 V/ns (incl. 0.5 / 5 A at 150 C); Miller bump < 0.7 V at\n'
           '150 C is the goal.  Psw per motor = (Eon + Eoff) x f at Tj 150 C, 2 nH.\n',
           S.table(summary, ['config', 'VDS 15A/2nH', 'VDS 30A/4nH', 'brake -15A/2nH', 'brake -30A/4nH',
                             'dV/dt max', 'GL min', 'LS bump 150C', 'HS bump 150C (brake)',
                             'Psw 15A 24k W', 'Psw 15A 48k W', 'Psw 30A 24k W', 'Psw 30A 48k W',
                             'min-Vth E rise %', 'min-Vth VDS', 'verdict']),
           '\nShoot-through scale (model transfer curve, VDS 10 V, typical part): at 150 C a die VGS of\n'
           '1.5 / 1.8 / 2.1 / 2.4 V conducts 3 mA / 0.06 A / 0.8 A / 5 A; at 25 C 2.1 V conducts 2 mA.\n'
           'A minimum-Vth part sits ~0.55 V lower.  Bumps last 3-10 ns.  "min-Vth E rise %": the worst\n'
           'change in switching energy per cycle (Eon + Eoff motoring; the low-side turn-on edge braking) when\n'
           'both FETs are minimum-Vth parts at 150 C, i.e. the shoot-through the bumps cause, as energy.\n'
           'Positive values at +15/+30 A are mostly a slower turn-off (lower Vth), not shoot-through.\n'
           '"min-Vth VDS": peak VDS in those runs.',
           '\nAll runs:\n' + S.table(rows, hdr)]
    out = '\n'.join(txt)
    with open(os.path.join(HERE, 'options.txt'), 'w') as f:
        f.write(out + '\n')
    print(out)

    plt = S.style()
    fig, ax = plt.subplots(1, 4, figsize=(18, 4.6))
    names = [c[0] for c in CONFIGS]
    y = np.arange(len(names))
    sm = np.array([[max(s[1], s[3]), max(s[2], s[4]), s[5], s[6], s[7], s[8], s[10]] for s in summary], dtype=float)
    ax[0].barh(y - 0.2, sm[:, 0], 0.4, label='+-15 A, 2 nH')
    ax[0].barh(y + 0.2, sm[:, 1], 0.4, label='+-30 A, 4 nH')
    ax[0].axvline(34, color='C1', lw=0.8); ax[0].axvline(40, color='C3', lw=0.8)
    ax[0].set_title('peak die VDS, worse FET, Tj and direction (V)\nlimits 34 V (15 A) / 40 V (30 A)', fontsize=8)
    ax[1].barh(y, sm[:, 2]); ax[1].axvline(2, color='C3', lw=0.8)
    ax[1].set_title('max sw dV/dt rising 10-90 % (V/ns)', fontsize=8)
    ax[2].barh(y - 0.2, sm[:, 4], 0.4, label='low side, motoring')
    ax[2].barh(y + 0.2, sm[:, 5], 0.4, label='high side, braking')
    ax[2].axvline(0.7, color='C3', lw=0.8, ls=':'); ax[2].axvline(1.8, color='C1', lw=0.8)
    ax[2].set_title('Miller bump at 150 C (V); 1.8 V = 0.06 A, 2.1 V = 0.8 A (typ part)', fontsize=8)
    ax[3].barh(y, sm[:, 6]); ax[3].set_title('Psw per motor, 15 A, 48 kHz, 150 C (W)', fontsize=8)
    for a in ax:
        a.set_yticks(y); a.set_yticklabels(names if a is ax[0] else [], fontsize=7)
        a.invert_yaxis()
    ax[0].legend(fontsize=7); ax[2].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(HERE, 'options.png'))


if __name__ == '__main__':
    main()
