"""Per-motor loss and board thermal estimate for the OG3 4-in-1 ESC.
All inputs are datasheet numbers or stated assumptions; see esc_power.md."""
import math
FETS = {
 # name: R25max, R100max, R125max (mOhm), Qg(10V)max nC, Qrr nC (used), Qoss nC, VSD_hot V, RthJC K/W, Tjmax, Vds
 'BSZ040N06LS5 (Infineon, 60V)': dict(r25=4.0, r100=5.3, r125=6.0, qg=42, qrr=30, qoss=42, vsd=0.7, rjc=1.8, tjmax=150, vds=60),
 'MCG60N06YHE3 (MCC, 60V)':      dict(r25=6.0, r100=9.0, r125=9.9, qg=40, qrr=32, qoss=40, vsd=0.7, rjc=2.5, tjmax=175, vds=60),
 'CSD18543Q3A (TI, 60V)':        dict(r25=9.9, r100=13.9, r125=15.3, qg=14.5, qrr=37, qoss=20, vsd=0.7, rjc=1.9, tjmax=150, vds=60),
 'TPN2R304PL (Toshiba, 40V)':    dict(r25=2.3, r100=3.3, r125=3.7, qg=41, qrr=30, qoss=40, vsd=0.7, rjc=1.43, tjmax=175, vds=40),
}
R_LOCAL = 10.0     # K/W case -> surrounding board copper (assumption: via array into 6-layer planes)
RSH = 0.0005       # 0.5 mOhm shunt per channel
DT_DRV = 215e-9    # DRV8300 internal dead time (typ, DT pin open)
SLEW = 2.0         # V/ns, DRV8300D max SHx slew (datasheet rec. op.)
T_I = 5e-9         # current-commutation part of each edge (assumption)

def motor(f, V, I, fsw, dt_counts, D=0.95, fclk=64e6, vgs=11.5):
    R = f['r125'] * 1e-3
    t_dt = max(dt_counts / fclk, DT_DRV)
    t_edge = V / SLEW * 1e-9 + T_I
    p_cond = 2 * I**2 * R * (1.0)                  # sync. rect.: always 2 FETs in the path
    e_sw = V * I * t_edge + V * (f['qrr'] + f['qoss']) * 1e-9
    p_sw = e_sw * fsw
    p_dt = 2 * t_dt * fsw * f['vsd'] * I
    p_sh = (D * I)**2 * RSH
    p_gate = 2 * f['qg'] * 1e-9 * vgs * fsw
    tot = p_cond + p_sw + p_dt + p_sh + p_gate
    # hottest single FET (low side of the PWM'd leg)
    p_ls = I**2 * R / 3 * (1 + (1 - D)) + p_dt / 3
    p_hs = I**2 * R / 3 * D + p_sw / 3
    return dict(cond=p_cond, sw=p_sw, dt=p_dt, sh=p_sh, gate=p_gate, tot=tot, fet=max(p_ls, p_hs), t_dt=t_dt)

CASES = [
 ('6S worst, 20 A, 48 kHz, AM32 stock DEAD_TIME 60', 25.2, 20, 48e3, 60),
 ('6S worst, 20 A, 48 kHz, DEAD_TIME 20 (custom)',   25.2, 20, 48e3, 20),
 ('6S worst, 20 A, 24 kHz, DEAD_TIME 20',            25.2, 20, 24e3, 20),
 ('6S peak, 30 A, 48 kHz, DEAD_TIME 20',             25.2, 30, 48e3, 20),
 ('4S owner (XING2 1404), 15.8 A, 48 kHz, DT 20',    16.8, 15.8, 48e3, 20),
]
if __name__ == '__main__':
    for fn, f in FETS.items():
        print('==', fn)
        for name, V, I, fsw, dt in CASES:
            m = motor(f, V, I, fsw, dt)
            tj = 100 + m['fet'] * (f['rjc'] + R_LOCAL)
            print('  %-50s cond %5.2f sw %4.2f dt %4.2f sh %4.2f gate %4.2f | motor %5.2f W, 4x %5.1f W | hottest FET %4.2f W -> Tj %5.1f C (board 100 C) | Vds use %2.0f%%' % (
                name, m['cond'], m['sw'], m['dt'], m['sh'], m['gate'], m['tot'], 4*m['tot'], m['fet'], tj, 100*V/f['vds']))
    # board-level
    A = 2 * 0.0338**2
    C = 6.5
    print('\nBoard: area both sides %.1f cm2, heat capacity ~%.1f J/K (estimate)' % (A*1e4, C))
    f = FETS['BSZ040N06LS5 (Infineon, 60V)']
    for air, h in (('still air (h~15)', 15), ('some airflow (h~35)', 35), ('strong prop wash (h~60)', 60)):
        hA = h * A
        cap = hA * (100 - 25)           # W the board can shed at 100 C, 25 C ambient
        # max current per motor, 4 motors, 6S 48 kHz DT 20
        lo, hi = 0, 40
        for _ in range(60):
            mid = (lo + hi) / 2
            if 4 * motor(f, 25.2, mid, 48e3, 20)['tot'] > cap: hi = mid
            else: lo = mid
        i6 = lo
        lo, hi = 0, 40
        for _ in range(60):
            mid = (lo + hi) / 2
            if 4 * motor(f, 16.8, mid, 48e3, 20)['tot'] > cap: hi = mid
            else: lo = mid
        i4 = lo
        tau = C / hA
        out = []
        for name, V, I, fsw, dt in CASES:
            P = 4 * motor(f, V, I, fsw, dt)['tot']
            tss = 25 + P / hA
            t60 = tss - (tss - 40) * math.exp(-60 / tau)
            out.append('%s: Tss %.0f C, T(60 s from 40 C) %.0f C' % (name.split(',')[0] + ',' + name.split(',')[1], tss, t60))
        print('  %-26s hA %.3f W/K, sheds %4.1f W at 100 C; tau %3.0f s; max sustained per motor: 6S %.1f A, 4S %.1f A' % (air, hA, cap, tau, i6, i4))
        for o in out: print('      ', o)
