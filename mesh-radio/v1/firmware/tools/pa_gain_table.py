#!/usr/bin/env python3
"""Provisional Meshtastic TX_GAIN_LORA table for Mesh Radio v1.

Meshtastic's table has one entry per SX1262 output setting, 0..21 dBm:
entry i = (power at the antenna port) - i, in whole dB, with the SX1262 set
to i dBm.  For a requested power P (unlicensed mode only) the firmware picks
the first i where i + gain[i] > P and sets the SX1262 to P - gain[i]
(RadioInterface::limitPower).  The variant uses the same rule to turn a
power cap (temperature, battery, antenna fault) into a highest SX1262
setting for each packet (variant.cpp, driveForCapDbm()).

Until the board is measured the table comes from a model:

  * net small-signal gain, SX1262 pin -> U.FL: 16.8 dB
    (QPA9510 33.8 dB - 15.9 dB pad - 1.1 dB from the amplifier output to
    the U.FL: harmonic filter, SKY13330 switch and LFCG-1000+, sim/rf
    study 1, 1.10-1.12 dB nominal).  Before sim/rf put a number on that
    loss the model left it out (18 dB), which erred towards too little
    output; with the loss known the table is ~1 dB higher in the middle.
  * Rapp compression (p = 2) towards a saturated output at the U.FL that
    depends on the amplifier supply VPA, scaled 20*log10(V) from ~35 dBm
    at 4.0 V (sim/rf Monte Carlo: 34.8-35.2 dBm at 4.0 V, 33.9-34.3 dBm at
    3.6 V).

The table is computed at the 4.0 V curve, the least-compressed one, and
rounded UP.  So whatever the amplifier supply is (2.7 V, the TPS63810's
3.3 V power-on default, 3.6 V or 4.0 V), a requested power is never exceeded
in the model.  The US supply (2.7 V) adds margin of its own: even with the
QPA9510 1 dB above its typical gain, a 30 dBm request gives ~29.7 dBm there.
The lowest output is about 8 dBm: the SX1262 cannot go below -9 dBm and the
chain has ~17 dB of gain.

Replace MODEL with bench data: measure U.FL power for SX1262 settings
0..20 dBm at the US supply (OFFGRID_PA_VOUT_US_MV) and at the licensed
ceiling, take gain[i] = ceil(max over supplies of (Pout - i)).

    python3 pa_gain_table.py            # prints the table and a check
"""
import math

PA_GAIN = 33.8     # dB, QPA9510 small-signal gain (data sheet, typical)
PAD = 15.9         # dB, 68/150/68 ohm pi pad
LOSS_TX = 1.1      # dB, PA output -> U.FL (sim/rf study 1)
G0 = PA_GAIN - PAD - LOSS_TX   # 16.8 dB, SX1262 pin -> U.FL (PROVISIONAL)
P_SAT_4V0 = 35.0   # dBm at the U.FL with VPA = 4.0 V (PROVISIONAL)
RAPP_P = 2.0
VPA_US = 2.7       # V, unlicensed supply (OFFGRID_PA_VOUT_US_MV)
VPA_MIN = 2.7      # V, lowest supply the variant uses for a transmitting PA


def psat(vpa):
    return P_SAT_4V0 + 20 * math.log10(vpa / 4.0)


def pout(drive_dbm, vpa):
    a = 10 ** ((drive_dbm + G0 - psat(vpa)) / 20)          # normalised amplitude
    return psat(vpa) + 20 * math.log10(a / (1 + a ** (2 * RAPP_P)) ** (1 / (2 * RAPP_P)))


def table(vpa_worst=4.0):
    return [math.ceil(round(pout(i, vpa_worst) - i, 3)) for i in range(22)]


def meshtastic_drive(p_req, gain, max_power=20, min_power=-9):
    """What RadioInterface::limitPower + SX126xInterface do with a request."""
    for i in range(len(gain)):
        if i + gain[i] > p_req or i == len(gain) - 1:
            d = p_req - gain[i]
            break
    return max(min(d, max_power), min_power)


def vpa_for_cap(cap_dbm, ceiling):
    """Supply the variant sets for an antenna-power cap: Psat(VPA) = cap,
    rounded up to the TPS63810's 25 mV step, between 2.7 V and the ceiling."""
    v = 4.0 * 10 ** ((cap_dbm - P_SAT_4V0) / 20)
    v = math.ceil(v * 40 - 1e-9) / 40
    return min(max(v, VPA_MIN), ceiling)


if __name__ == '__main__':
    t = table()
    print('#define NUM_PA_POINTS 22')
    print('#define TX_GAIN_LORA ' + ', '.join(str(g) for g in t))
    print()
    print('request  SX1262   U.FL dBm at VPA = 2.7 / 3.3 / 3.6 / 4.0 V (model)')
    for p in range(0, 31, 2):
        d = meshtastic_drive(p, t)
        outs = [pout(d, v) for v in (2.7, 3.3, 3.6, 4.0)]
        if d > -9:   # below ~8 dBm the SX1262's -9 dBm floor sets the output
            assert max(outs) <= p + 0.05, (p, d, outs)
        print('%5d %8d   %s' % (p, d, '  '.join('%5.1f' % o for o in outs)))
    print()
    print('licensed mode (table not used; tx_power = SX1262 setting, capped at 20):')
    for d in (0, 5, 10, 12, 14, 16, 18, 20):
        print('  SX1262 %3d dBm -> %s' % (d, '  '.join('%5.1f' % pout(d, v) for v in (2.7, 3.3, 3.6, 4.0))))
    print()
    print('power caps (variant.cpp): highest SX1262 setting and supply for a cap, licensed ceiling 3.6 / 4.0 V')
    for cap in (30, 32, 33, 34, 35):
        d = meshtastic_drive(cap, t)
        for ceil_v in (3.6, 4.0):
            v = vpa_for_cap(cap, ceil_v)
            print('  cap %2d dBm: SX1262 <= %2d dBm, VPA %.3f V (ceiling %.1f V) -> %5.1f dBm'
                  % (cap, d, v, ceil_v, pout(20 if d >= 20 else d, v)))
