# -*- coding: utf-8 -*-
"""Print Hub v1: the power chain worked through from the datasheets.

    python3 sim/power_budget.py        writes sim/power_budget.md, exits 1 on a failed check

Every figure is computed here from the part values in src/circuit.py and
the datasheet numbers below (each with its source), so a part change is
re-checked by running this again.  Worst case means the corner that hurts:
low input, hot board, the far end of each tolerance.
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, 'power_budget.md')

# ---------------------------------------------------------------- inputs
# buck: Silergy SY8368A (datasheet rev 0.9C): 800 kHz, VREF 0.6 V +-1.5 %,
# switches about 20 / 10 mOhm (high / low side; LCSC listing), 8 A valley limit
FSW = 800e3
VREF, VREF_TOL = 0.600, 0.015
R_TOP, R_BOT, R_TOL = 76e3, 10e3, 0.01        # 75k + 1k, 10k, 1 % parts
RDS_HI, RDS_LO = 0.020, 0.010
T_SW = 20e-9                                   # rise + fall, assumed
THETA_BUCK = 30.0                              # C/W, QFN 3x3 on a 4-layer board with ground plane (assumed)
# inductor: Changjiang FXL0630-2R2-M: 2.2 uH +-20 %, 15 mOhm, 9.5 A saturation (LCSC C167218)
L, L_TOL, DCR, ISAT = 2.2e-6, 0.20, 0.015, 9.5
# capacitors: Samsung CL31A226KAHNNNE 22 uF 25 V X5R 1206 keeps ~60 % at 5 V
# bias, CL31A106KBHNNNE 10 uF 50 V keeps ~75 % at 9-12 V (Samsung DC-bias curves)
C_OUT = 4 * 22e-6 * 0.60
C_PORTS = 5 * 22e-6 * 0.60 + 5 * 22e-6 * 0.60     # 22 uF at each switch input and each port output
C_IN = 2 * 10e-6 * 0.75
# port path: TI TPS25200 (SLVSCJ7): 60 mOhm typ / 90 mOhm max (-40..85 C junction);
# current limit with 47k: 1.92 / 2.07 / 2.20 A (min / typ / max)
RON_SW_TYP, RON_SW_MAX = 0.060, 0.090
ILIM_MIN, ILIM_TYP, ILIM_MAX = 1.92, 2.07, 2.20
THETA_SW = 66.5                                # C/W, WSON-6 2x2 (TI's figure)
R_SHUNT = 0.020
R_COPPER = 0.010                               # plane + tracks + connector contact, estimate
USB_MIN = 4.75                                 # the USB 2.0 VBUS floor at the receptacle
# sense chain: INA180A2 gain 50 +-1 %, offset 150 uV max (25 uV typ); ESP32-S3
# ADC at 12 dB: 0-3.1 V usable, about +-2 % after Espressif's calibration
GAIN, GAIN_TOL, VOS = 50.0, 0.01, 150e-6
ADC_MAX, ADC_TOL = 3.1, 0.02
# logic supply: B5819W 0.45 V at 0.5 A (LCSC), AP2112K 250 mV dropout at 600 mA
VF_OR, DROPOUT = 0.45, 0.25
VBUS_PC_MIN = 4.75
AMBIENT = 45.0                                 # inside a closed enclosure beside a printer (assumed)

checks = []


def check(ok, what):
    checks.append((ok, what))


def run():
    L_ = []
    w = L_.append
    vout = VREF * (1 + R_TOP / R_BOT)
    vout_lo = VREF * (1 - VREF_TOL) * (1 + R_TOP * (1 - R_TOL) / (R_BOT * (1 + R_TOL)))
    vout_hi = VREF * (1 + VREF_TOL) * (1 + R_TOP * (1 + R_TOL) / (R_BOT * (1 - R_TOL)))
    w('# Print Hub v1: power chain\n')
    w('Computed by `sim/power_budget.py` from the part values and datasheet figures in it.\n')
    w('## 5 V rail (SY8368A buck)\n')
    w('| | value |\n|---|---|')
    w('| output, nominal | %.3f V |' % vout)
    w('| output, tolerance corners | %.3f .. %.3f V |' % (vout_lo, vout_hi))
    check(vout_hi < 5.40, 'rail stays under the port switch\'s 5.4 V output clamp (%.2f V)' % vout_hi)
    for vin in (9.0, 12.0):
        d = vout / vin
        for lval, tag in ((L, 'nominal L'), (L * (1 - L_TOL), 'L -20 %')):
            dI = vout * (1 - d) / (lval * FSW)
            ipk = 5.0 + dI / 2
            w('| %g V in, 5 A, %s: ripple current / peak | %.2f A / %.2f A |' % (vin, tag, dI, ipk))
            check(ipk < ISAT * 0.8, 'inductor peak %.2f A under 80 %% of saturation at %g V, %s' % (ipk, vin, tag))
            check(ipk < 8.0 + dI, 'valley current limit (8 A) above the 5 A load at %g V, %s' % (vin, tag))
        dv = dI / (8 * FSW * C_OUT)
        vin_rip = 5.0 * d * (1 - d) / (FSW * C_IN)
        w('| %g V in: output ripple (buck caps only) / input ripple | %.1f mV / %.0f mV |' % (vin, dv * 1e3, vin_rip * 1e3))
        check(dv < 0.025, 'output ripple %.1f mV under 25 mV at %g V in' % (dv * 1e3, vin))
    # losses at 9 V, 5 A
    vin, iout = 9.0, 5.0
    d = vout / vin
    p_cond = iout ** 2 * (d * RDS_HI + (1 - d) * RDS_LO)
    p_sw = 0.5 * vin * iout * T_SW * FSW
    p_l = iout ** 2 * DCR
    pout = vout * iout
    eff = pout / (pout + p_cond + p_sw + p_l)
    tj = AMBIENT + (p_cond + p_sw) * THETA_BUCK
    w('| 9 V, 5 A: buck loss / inductor loss | %.2f W / %.2f W |' % (p_cond + p_sw, p_l))
    w('| 9 V, 5 A: efficiency (the firmware budgets 90 %%) | %.1f %% |' % (eff * 100))
    w('| 9 V, 5 A: buck junction at %g C air | %.0f C (rated 125 C) |' % (AMBIENT, tj))
    check(eff > 0.90, 'efficiency %.1f %% above the 90 %% the firmware budgets' % (eff * 100))
    check(tj < 110, 'buck junction %.0f C under 110 C at %g C air' % (tj, AMBIENT))

    w('\n## Each port\n')
    w('| | at 1.0 A | at 1.5 A | at the switch\'s limit (2.2 A max) |\n|---|---|---|---|')
    row = []
    for i in (1.0, 1.5, ILIM_MAX):
        v = vout_lo - i * (RON_SW_MAX + R_SHUNT + R_COPPER)
        row.append(v)
    w('| voltage at the USB-A, worst case (low rail, hot switch) | %.2f V | %.2f V | %.2f V |' % tuple(row))
    check(row[1] >= USB_MIN, 'port voltage %.2f V at 1.5 A, worst case, at or over USB\'s 4.75 V' % row[1])
    pts = [i ** 2 * RON_SW_MAX for i in (1.0, 1.5, ILIM_MAX)]
    w('| switch dissipation, hot | %.2f W | %.2f W | %.2f W |' % tuple(pts))
    tsw = AMBIENT + pts[2] * THETA_SW
    w('| switch junction at %g C air | | | %.0f C (thermal shutdown 135-155 C) |' % (AMBIENT, tsw))
    check(tsw < 125, 'switch junction %.0f C at its current limit, under 125 C' % tsw)
    ps = ILIM_MAX ** 2 * R_SHUNT
    w('| shunt dissipation at the limit | | | %.2f W (rated 1 W) |' % ps)
    check(ps < 0.5, 'shunt %.2f W under half its rating' % ps)
    w('\nA dead short on a port: the switch holds it to %.2f A at most and cycles on its thermal '
      'shutdown, and its FAULT line (8 ms deglitch) makes the firmware switch the port off. '
      'The rail sees at most %.1f A from that port, inside the buck\'s 5 A with the others running '
      '(see `sim/port_events.py` for the first microseconds).\n' % (ILIM_MAX, ILIM_MAX))

    w('## Current measurement\n')
    vfs = ILIM_MAX * R_SHUNT * GAIN * (1 + GAIN_TOL)
    w('| | value |\n|---|---|')
    w('| scale | %.2f V per A |' % (R_SHUNT * GAIN))
    w('| reading at the switch\'s highest limit | %.2f V (ADC range %.1f V; amplifier supply 3.3 V) |' % (vfs, ADC_MAX))
    check(vfs < ADC_MAX, 'the highest port current reads %.2f V, inside the ADC range' % vfs)
    off_ma = VOS / R_SHUNT * 1e3
    err = lambda i: (i * (GAIN_TOL + ADC_TOL) + VOS / R_SHUNT) * 1e3
    w('| amplifier offset as current | %.1f mA max |' % off_ma)
    w('| error at 0.5 A / 1.5 A | +-%.0f mA / +-%.0f mA |' % (err(0.5), err(1.5)))
    check(err(1.5) < 100, 'error at 1.5 A (%.0f mA) small next to the 1.5 A software limit\'s margin to the switch (420 mA)' % err(1.5))

    w('\n## Logic supply\n')
    v_pc = VBUS_PC_MIN - VF_OR
    w('| | value |\n|---|---|')
    w('| from the print server\'s USB alone, worst case | %.2f V into the LDO, needs %.2f V |' % (v_pc, 3.3 + DROPOUT))
    check(v_pc >= 3.3 + DROPOUT, 'LDO keeps 3.3 V from the PC\'s USB alone (%.2f V in)' % v_pc)
    v_rail = vout_lo - VF_OR
    w('| from the 5 V rail | %.2f V into the LDO |' % v_rail)
    w('| WS2812B LED supply (3.3-5.3 V) | %.2f .. %.2f V |' % (v_pc, vout_hi - 0.3))
    check(3.3 <= v_pc and vout_hi - 0.3 <= 5.3, 'LED supply inside 3.3-5.3 V')

    w('\n## Charger budget (what the firmware allows, firmware/src/board.cpp)\n')
    w('| charger | contract | ports may draw |\n|---|---|---|')
    for name, v, i in (('20 W', 9, 2.0), ('20 W, full 9 V offer', 9, 2.22), ('30 W', 9, 3.0),
                       ('45 W and up', 9, 3.0), ('5 V only (no USB-PD)', 5, 3.0)):
        if v < 9:
            ma = 0
        else:
            ma = min(5000, (v * i * 0.90 / 5.15 * 1000 - 150) * 0.9)
        w('| %s | %g V %.2f A | %s |' % (name, v, i, ('%.1f A' % (ma / 1000)) if ma else 'nothing: ports stay off'))
    w('\nTypical load (fan 0.45 A, light 0.6 A, two filters charging 0.8 A each, spare 1 A): 3.65 A. '
      'A 30 W charger covers it; a 20 W one covers everything but the spare while both filters charge.\n')

    w('## Checks\n')
    for ok, what in checks:
        w('- %s %s' % ('PASS' if ok else 'FAIL', what))
    open(OUT, 'w').write('\n'.join(L_) + '\n')
    bad = [c for c in checks if not c[0]]
    print('%d checks, %d failed -> %s' % (len(checks), len(bad), os.path.relpath(OUT)))
    for ok, what in bad:
        print('  FAIL', what)
    return not bad


if __name__ == '__main__':
    sys.exit(0 if run() else 1)
