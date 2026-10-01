# -*- coding: utf-8 -*-
"""Heat per part for an operating point, from datasheet figures (data.py),
the switching simulation (spice.py) and the copper (copperloss.py).

An ESC operating point is, per motor: phase current I (A, the motor's
current while the bridge drives it), duty D, and the PWM frequency; with
the battery voltage V.  In AM32's six-step drive with complementary PWM,
over a full electrical turn each phase leg is the switched leg a third of
the time, the low leg a third and floats a third.  So per phase:

  high-side FET   conducts D/3 of the time; switches (Eon + Eoff) f / 3
  low-side FET    conducts (1 - D)/3 as the switched leg's free-wheel and
                  1/3 as the low leg; its body diode carries the current for
                  the two dead times of each switched-leg period, 2 t_dead f / 3
  shunt           carries I during D (the free-wheel current circulates
                  between the low sides, on the bridge side of the shunt)
  gate drive      both FETs of the switched leg, Qg Vgvdd f each (rev 1:
                  DRV8300 from the gate-drive LDO); rev 2's DRV8320H runs
                  from the battery: its low side through its regulator
                  (Qg V f), its high side through its charge pump (taken as
                  twice the charge from the battery, 2 Qg V f), its own
                  quiescent current, and the channel's 3.3 V from its DVDD
                  regulator ((V - 3.3) x the MCU, amplifier and thermistor)

On-resistance is the datasheet maximum at 25 C times the datasheet's own
temperature curve (Fig. 8.9), at each FET's junction temperature.
"""
import numpy as np
import data

PH = 'ABC'


def rds(T):
    Ts, r = zip(*data.FET['rds_ratio'])
    return data.FET['rds25_max'] * float(np.interp(T, Ts, r))


def esc_channel(I, D, V, f, dead, Tj, sw):
    """Heat (W) for one channel: {'AH': .., 'AL': .., ..., 'shunt', 'driver'}.

    Tj: FET ('AH', 'AL', ...) -> junction temperature, for its on-resistance.
    sw: switching energies {'V', 'I': [...], 'on': [...], 'off': [...]} (J).
    """
    out = {}
    esw = (np.interp(I, sw['I'], sw['on']) + np.interp(I, sw['I'], sw['off'])) * V / sw['V']
    for p in PH:
        out['%sH' % p] = D / 3 * I * I * rds(Tj['%sH' % p]) + esw * f / 3
        out['%sL' % p] = ((1 - D) / 3 + 1 / 3) * I * I * rds(Tj['%sL' % p]) \
            + 2 * dead * f * data.FET['vsd_hot'] * I / 3
    out['shunt'] = D * I * I * data.SHUNT['r']
    out['driver'] = driver(V, f)
    return out


def driver(V, f):
    """One channel's gate driver heat (W) at battery voltage V, PWM f."""
    D = data.DRIVER
    qg = data.FET['qg_11v']
    if D['kind'] == 'gvdd':
        return 2 * qg * data.GVDD * f + D['i_q'] * data.GVDD
    return 3 * qg * V * f + D['i_vm'][1] * V + (V - 3.3) * data.DVDD_LOAD


def gvdd_current(f):
    """The four drivers' supply current from the gate-drive LDO (A): gate
    charge and quiescent (rev 1; rev 2 has no such LDO)."""
    return 4 * (2 * data.FET['qg_11v'] * f + data.DRIVER['i_q'])


def buck_loss(part, iout, vout):
    """Converter loss (W) at iout, from the maker's efficiency curve at 24 V in.

    The curve is at the part's `vout`; the loss in watts at the same input,
    current and frequency is taken as the same at this board's output."""
    if iout <= 0:
        return 0.0
    I, e = zip(*part['eff'])
    eta = float(np.interp(iout, I, e))
    return part['vout'] * iout * (1 / eta - 1)


def fc_power(i5, i9):
    """FC input power (W) and the heat of each supply part (W)."""
    p5 = buck_loss(data.BUCK5, i5, 5.0)
    p9 = buck_loss(data.BUCK9, i9, 9.1)
    ldo = (5.0 - 3.3) * data.FC_3V3_LOAD
    pin = 5.0 * i5 + p5 + 9.1 * i9 + p9     # the 3.3 V load is part of the 5 V rail's i5
    return pin, dict(U_BUCK5=p5, U_BUCK9=p9, U_LDO=ldo)


def motor(throttle, V=None):
    """Battery current per motor (A), duty and phase current at a throttle (%).

    From the motor maker's load test (data.MOTOR): battery current against
    throttle at 24 V, the rpm there showing that throttle is the duty.  Below
    the first row, current goes as throttle squared (the rows above it do,
    to within a few per cent).  The phase current is the battery current
    over the duty: the bridge passes the motor's current to the battery only
    while it is on."""
    th, ib = [r[0] for r in data.MOTOR['load']], [r[1] for r in data.MOTOR['load']]
    D = max(throttle / 100.0, 0.01)
    if throttle < th[0]:
        I_b = ib[0] * (throttle / th[0]) ** 2
    else:
        I_b = float(np.interp(throttle, th, ib))
    if V:
        # the prop's torque, so the motor current, goes as speed squared, and
        # speed as the applied voltage D V: at the same throttle, current ~ V^2
        I_b *= (V / data.MOTOR['vtest']) ** 2
    return I_b, D, I_b / D


def hover(V):
    """Throttle (%) that holds the quad (data.MOTOR['auw']) up at battery V.

    Thrust against throttle from the load test; thrust goes as rpm squared,
    rpm as the applied voltage, so at V the same thrust needs 24/V of the
    throttle; below the first row thrust goes as throttle squared."""
    th, g = [r[0] for r in data.MOTOR['load']], [r[2] for r in data.MOTOR['load']]
    need = data.MOTOR['auw'] / 4
    t24 = th[0] * (need / g[0]) ** 0.5 if need < g[0] else float(np.interp(need, g, th))
    return t24 * data.MOTOR['vtest'] / V


def limited(throttle, V=None, limit=None):
    """The same, after AM32's per-motor current limit (battery side)."""
    limit = data.AM32['current_limit'] if limit is None else limit
    I_b, D, I = motor(throttle, V)
    if I_b <= limit:
        return I_b, D, I
    lo, hi = 0.0, throttle
    for _ in range(40):
        mid = (lo + hi) / 2
        if motor(mid, V)[0] > limit:
            hi = mid
        else:
            lo = mid
    return motor(lo, V)
