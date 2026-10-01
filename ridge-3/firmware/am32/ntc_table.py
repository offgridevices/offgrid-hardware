#!/usr/bin/env python3
"""AM32's NTC_table for the Ridge 3 ESC's FET thermistors.

Each channel reads a Murata NCU15XH103F60RC (10 k, B25/50 3380 K) to ground
under a 10 k bias resistor from the driver's DVDD, which is also the MCU's
VDDA, so the reading is ratiometric:

    ADC = 4096 R / (R + 10k)

AM32 (Mcu/f421/Src/ADC.c, getNTCDegrees) takes NTC_table[ADC >> 6] and
interpolates linearly to the next entry, so entry i is the temperature at
ADC = 64 i.  The resistance-temperature curve is Murata's own, not a B
equation: catalog R44E-18 (NTC Thermistors, "Temperature Characteristics
(Center Value)", column NCpppXH103), -40..125 C in 5 C steps.  Between its
points ln R is interpolated linearly in 1/T (a local B for each 5 C step,
which is exact at Murata's points); beyond them the end step's B is
extended.  Entry 0 (ADC 0: a shorted sensor, or the bias resistor open)
and entry 64 (ADC 4096: an open sensor) are faults, not temperatures: entry
0 is held at 200 C, hot enough to cut the power and within the 8-bit
temperature that extended DShot telemetry sends; entry 64 at -60 C.  An
open sensor so reads cold and the limit never acts: bring-up checks every
channel's reading against a thermometer (../README.md).

    python3 ntc_table.py        prints the table as it goes in ntc_tables.h
"""
import math

R_BIAS = 10e3
# Murata NCpppXH103 center values, kOhm, from -40 C in 5 C steps
MURATA_XH103_KOHM = [
    195.652, 148.171, 113.347, 87.559, 68.237, 53.650, 42.506, 33.892, 27.219, 22.021,
    17.926, 14.674, 12.081, 10.000, 8.315, 6.948, 5.834, 4.917, 4.161, 3.535,
    3.014, 2.586, 2.228, 1.925, 1.669, 1.452, 1.268, 1.110, 0.974, 0.858,
    0.758, 0.672, 0.596, 0.531,
]
T0 = -40.0
STEP = 5.0
K = 273.15


def degrees(r):
    """Temperature (C) at resistance r (ohm) on Murata's curve."""
    pts = [(T0 + STEP * i + K, math.log(kohm * 1e3)) for i, kohm in enumerate(MURATA_XH103_KOHM)]
    lr = math.log(r)
    # the step that brackets ln r (ln R falls with T); the end steps beyond
    i = 0
    while i < len(pts) - 2 and lr < pts[i + 1][1]:
        i += 1
    (ta, la), (tb, lb) = pts[i], pts[i + 1]
    inv_t = 1 / ta + (lr - la) * (1 / tb - 1 / ta) / (lb - la)
    return 1 / inv_t - K


SHORTED, OPEN = 200, -60


def table():
    out = [round(degrees(R_BIAS * 64 * i / (4096 - 64 * i))) for i in range(1, 64)]
    return [SHORTED] + out + [OPEN]


def c_block(values):
    rows = [', '.join('%d' % v for v in values[k:k + 9]) for k in range(0, len(values), 9)]
    return 'int NTC_table[65] = {\n' + ',\n'.join('  ' + r for r in rows) + '\n};'


if __name__ == '__main__':
    for kohm, t in ((10.0, 25), (0.974, 100), (0.531, 125)):     # the curve's own points
        assert abs(degrees(kohm * 1e3) - t) < 1e-6, (kohm, t)
    print(c_block(table()))
