"""Run the sounder-driver SPICE model over the unknown coil inductance and
check the limits. Writes results.json and buzzer.png."""
import json, os, re, subprocess
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
res, waves = {}, {}
for L in ['0.5m', '1m', '2m', '4m']:
    cir = open('buzzer.cir').read().replace('.param LCOIL=2m', f'.param LCOIL={L}')
    open('_run.cir', 'w').write(cir)
    subprocess.run(['ngspice', '-b', '_run.cir'], capture_output=True, check=True)
    v = open('result.txt').read().split()[1:]
    vds, isrc, vmin, iavg, id2, vg = map(float, v)
    res[L] = dict(vds_peak_V=round(vds, 3), supply_peak_A=round(-isrc, 3), vbus_min_V=round(vmin, 3),
                  supply_avg_A=round(-iavg, 3), clamp_peak_A=round(id2, 3), gate_V=round(vg, 3))
    waves[L] = np.loadtxt('wave.txt')
os.remove('_run.cir')
checks = {
    'drain peak < 30 V (AO3400A Vds max) with margin (< 8 V)': all(r['vds_peak_V'] < 8 for r in res.values()),
    'VBUS dip > 4.5 V (LDO keeps 3.3 V, dropout ~0.25 V)': all(r['vbus_min_V'] > 4.5 for r in res.values()),
    'clamp diode peak < 1 A (B5819W If(av) 1 A)': all(r['clamp_peak_A'] < 1.0 for r in res.values()),
    'gate reaches > 3 V (Rds(on) regime)': all(r['gate_V'] > 3.0 for r in res.values()),
}
json.dump(dict(results=res, checks=checks), open('results.json', 'w'), indent=1)
for k, v in res.items(): print(k, v)
for k, v in checks.items(): print('PASS' if v else 'FAIL', k)
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
fig, ax = plt.subplots(3, 1, figsize=(9, 7), sharex=True)
for L, w in waves.items():
    t = w[:, 0] * 1e3
    m = (t > 2.0) & (t < 2.75)
    ax[0].plot(t[m], w[m, 1], label=f'L={L}H')
    ax[1].plot(t[m], w[m, 3], label=f'L={L}H')
    ax[2].plot(t[m], w[m, 7] * 1e3, label=f'L={L}H')
ax[0].set_ylabel('drain V'); ax[1].set_ylabel('VBUS V'); ax[2].set_ylabel('clamp mA')
ax[2].set_xlabel('ms'); ax[0].legend(fontsize=7)
ax[0].set_title('Sounder driver, 4 kHz: drain clamped one diode drop above VBUS')
fig.tight_layout(); fig.savefig('buzzer.png', dpi=110)
import sys; sys.exit(0 if all(checks.values()) else 1)
