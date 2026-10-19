# -*- coding: utf-8 -*-
"""Print Hub v1: what the 5 V rail does when ports switch on, and when one
is shorted while the others run (ngspice).

    python3 sim/port_events.py     writes sim/port_events.md and port_events.png; exits 1 on a failed check

The model, and why each piece is pessimistic:
  buck       a current source that follows the rail's demand with a 10 us
             lag (an 800 kHz constant-on-time buck answers in a few
             switching cycles, ~5 us) and stops at its 8 A valley limit, set
             to hold 5.16 V
  rail caps  what the board has, derated for DC bias (power_budget.py):
             4 x 22 uF at the buck, 22 uF at each switch input
  switch     TPS25200 as a current limiter with its soft start: the output
             follows a 1 ms ramp at switch-on (TI: 2.05 ms typical rise
             time; faster is worse here), 90 mOhm (hot) until the current
             reaches 2.2 A (its highest limit), then constant current.  A
             short is first met with only the on-resistance for 2 us (the
             limiter's response time, TI E2E for the TPS2553 family), so the
             rail takes the full surge for that long
  output     22 uF at each port; the loads are the accessories: fan 0.45 A
             plus 220 uF, light 0.6 A plus 100 uF, two filters charging at
             0.8 A
Events: t = 1 ms ports 1-4 come on 250 ms apart in the firmware; here they
are all switched on together (worse); t = 20 ms port 5 is shorted to ground.
"""
import os, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))

DECK = """* Print Hub v1 port events
.param vset=5.16 cap_buck={4*22u*0.6} cap_sw={22u*0.6} cap_port={22u*0.6}
* buck: lagged current source, limited to 8 A
Berr nerr 0 V = {max(0, min(8, 200*(vset - v(rail))))}
Rlag nerr nlag 1k
Clag nlag 0 10n
Bbuck 0 rail I = {max(0, min(8, v(nlag)))}
Cb rail 0 {cap_buck}
Rbleed rail 0 1k
* port n: switch (on-resistance, limited at 2.2 A after a 2 us response), shunt, output cap, load
.subckt port rail out en lim=2.2
Bsw rail sw I = {min(max(0, v(en)*v(rail) - v(sw))/0.09, v(lim_ok) > 0.5 ? 2.2 : 1000)}
Rsh sw out 0.02
Co out 0 {cap_port}
Cin rail 0 {cap_sw}
* the limiter arms 2 us after the current first exceeds the limit
Bdet ndet 0 V = {(v(en)*v(rail)-v(sw))/0.09 > 2.2 ? 1 : 0}
Rd ndet lim_ok 2k
Cd lim_ok 0 1n
.ends
Ven1 en1 0 PWL(0 0 1m 0 2m 1)
Ven2 en2 0 PWL(0 0 1m 0 2m 1)
Ven3 en3 0 PWL(0 0 1m 0 2m 1)
Ven4 en4 0 PWL(0 0 1m 0 2m 1)
Ven5 en5 0 PWL(0 0 1m 0 2m 1)
X1 rail o1 en1 port
X2 rail o2 en2 port
X3 rail o3 en3 port
X4 rail o4 en4 port
X5 rail o5 en5 port
* loads: fan, light, two filters charging, and port 5: a phone at 1 A until it is shorted
Rf o1 0 {5/0.45}
Cf o1 0 220u
Rl o2 0 {5/0.6}
Cl o2 0 100u
Rc3 o3 0 {5/0.8}
Rc4 o4 0 {5/0.8}
Rp5 o5 0 5
Sshort o5 0 nsh 0 swmod
Vsh nsh 0 PWL(0 0 20m 0 20.0001m 1)
.model swmod sw(vt=0.5 ron=0.01 roff=1e9)
.ic v(rail)=5.16 v(nlag)=0
.tran 0.2u 40m 0 0.2u
.control
run
wrdata {out} v(rail) v(o1) v(o2) v(o3) v(o4) v(o5)
.endc
.end
"""


def main():
    import numpy as np
    tmp = tempfile.mkdtemp()
    data = os.path.join(tmp, 'ev.txt')
    deck = os.path.join(tmp, 'ev.cir')
    open(deck, 'w').write(DECK.replace('{out}', data))
    r = subprocess.run(['ngspice', '-b', deck], capture_output=True, text=True)
    if not os.path.exists(data):
        print(r.stdout[-2000:], r.stderr[-2000:])
        raise SystemExit('ngspice failed')
    a = np.loadtxt(data)
    t = a[:, 0]
    rail = a[:, 1]
    outs = [a[:, 3 + 2 * k] for k in range(5)]
    ok = []

    def win(t0, t1):
        return (t >= t0) & (t < t1)

    w_on, w_steady, w_short = win(1e-3, 19e-3), win(15e-3, 19.9e-3), win(20e-3, 40e-3)
    rail_min_on = rail[w_on].min()
    rail_min_short = rail[w_short].min()
    others_min_short = min(o[w_short].min() for o in outs[:4])
    others_late = min(o[win(21e-3, 40e-3)].min() for o in outs[:4])
    steady = [o[w_steady].mean() for o in outs]
    ok.append((rail_min_on > 4.9, 'all five ports on together: the rail dips to %.2f V (logic needs > 3.6 V)' % rail_min_on))
    ok.append((others_min_short > 4.6, 'port 5 shorted: the other ports dip to %.2f V for the 2 us before the limiter acts' % others_min_short))
    ok.append((others_late > 4.75, 'port 5 shorted, after 1 ms: the other ports hold %.2f V' % others_late))
    L = ['# Print Hub v1: port events (ngspice)\n', 'Computed by `sim/port_events.py`; the model and its '
         'pessimistic choices are in its docstring.\n', '| | value |', '|---|---|',
         '| rail before any port | 5.16 V |',
         '| rail, lowest, while every port switches on together | %.2f V |' % rail_min_on,
         '| port voltages with fan, light, two filters and a 1 A phone | %s V |' % ' / '.join('%.2f' % v for v in steady),
         '| rail, lowest, when port 5 is shorted | %.2f V |' % rail_min_short,
         '| ports 1-4, lowest, during the short\'s first microseconds | %.2f V |' % others_min_short,
         '| ports 1-4, from 1 ms after the short on | %.2f V |' % others_late,
         '\nThe firmware then switches port 5 off on the switch\'s FAULT line (8 ms deglitch); the '
         'model leaves it on, current-limited, to show the steady case.\n', '## Checks\n']
    L += ['- %s %s' % ('PASS' if g else 'FAIL', s) for g, s in ok]
    open(os.path.join(HERE, 'port_events.md'), 'w').write('\n'.join(L) + '\n')
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots(figsize=(9, 4))
        ax.plot(t * 1e3, rail, label='5 V rail', lw=1.2)
        for k, o in enumerate(outs):
            ax.plot(t * 1e3, o, label='USB%d' % (k + 1), lw=0.8)
        ax.axhline(4.75, color='0.5', ls='--', lw=0.8)
        ax.set_xlabel('ms'); ax.set_ylabel('V'); ax.set_ylim(-0.2, 5.6); ax.legend(ncol=6, fontsize=8)
        ax.set_title('Ports switch on at 1 ms; USB5 shorted at 20 ms')
        plt.tight_layout(); plt.savefig(os.path.join(HERE, 'port_events.png'), dpi=90)
    except ImportError:
        pass
    bad = [s for g, s in ok if not g]
    print('%d checks, %d failed -> sim/port_events.md' % (len(ok), len(bad)))
    for s in bad:
        print('  FAIL', s)
    return not bad


if __name__ == '__main__':
    sys.exit(0 if main() else 1)
