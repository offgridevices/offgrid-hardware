#!/usr/bin/env python3
"""Provisional Meshtastic TX_GAIN_LORA table for Mesh Radio v1.

Meshtastic's table has one entry per SX1262 output setting, 0..21 dBm:
entry i = (power at the antenna port) - i, in whole dB, with the SX1262 set
to i dBm.  For a requested power P (unlicensed mode only) the firmware picks
the first i where i + gain[i] > P and sets the SX1262 to P - gain[i]
(RadioInterface::limitPower).

Until the board is measured the table comes from a model:

  * net small-signal gain, SX1262 pin -> antenna port: 18 dB
    (QPA9510 33.8 dB - 15.9 dB pad; the ~1 dB of filter and switch loss
    after the amplifier is deliberately NOT subtracted, so the model errs
    towards too much gain = too little output, never too much);
  * Rapp compression (p = 2) towards a saturated output that depends on the
    amplifier supply VPA, scaled 20*log10(V) from ~35 dBm at 4.0 V.

The table is computed at the 4.0 V curve, the least-compressed one, and
rounded UP.  So whatever the amplifier supply is (2.7 V, the TPS63810's
3.3 V power-on default, 3.6 V or 4.0 V), a requested power is never exceeded
in the model.  The lowest output is about 9 dBm: the SX1262 cannot go
below -9 dBm and the chain has ~18 dB of gain.  At 2.7 V the board falls
short of the request near 30 dBm (about 29.1 dBm for a 30 dBm request) -
the bench measurement fixes that.

Replace MODEL with bench data: measure antenna-port power for SX1262
settings 0..20 dBm at the US supply (OFFGRID_PA_VOUT_US_MV) and at the
licensed ceiling, take gain[i] = ceil(max over supplies of (Pout - i)).

    python3 pa_gain_table.py            # prints the table and a check
"""
import math

G0 = 18.0          # dB, SX1262 pin -> antenna port, small signal (PROVISIONAL)
P_SAT_4V0 = 35.0   # dBm at the antenna port with VPA = 4.0 V (PROVISIONAL)
RAPP_P = 2.0


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


if __name__ == '__main__':
    t = table()
    print('#define NUM_PA_POINTS 22')
    print('#define TX_GAIN_LORA ' + ', '.join(str(g) for g in t))
    print()
    print('request  SX1262   antenna dBm at VPA = 2.7 / 3.3 / 3.6 / 4.0 V (model)')
    for p in range(0, 31, 2):
        d = meshtastic_drive(p, t)
        outs = [pout(d, v) for v in (2.7, 3.3, 3.6, 4.0)]
        if d > -9:   # below ~9 dBm the SX1262's -9 dBm floor sets the output
            assert max(outs) <= p + 0.05, (p, d, outs)
        print('%5d %8d   %s' % (p, d, '  '.join('%5.1f' % o for o in outs)))
    print()
    print('licensed mode (table not used; tx_power = SX1262 setting, capped at 20):')
    for d in (0, 5, 10, 12, 14, 16, 18, 20):
        print('  SX1262 %3d dBm -> %s' % (d, '  '.join('%5.1f' % pout(d, v) for v in (2.7, 3.3, 3.6, 4.0))))
