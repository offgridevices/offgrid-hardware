# -*- coding: utf-8 -*-
"""50 ohm line geometry for the RF tracks.

Grounded coplanar waveguide on F.Cu over the In1 ground plane: the first
dielectric of the board's stackup (pcb.DIELECTRIC; 6 layers, JLC06161H-2116B:
0.1164 mm of 2116 prepreg, er 4.16).  Closed-form quasi-static model (conformal mapping,
Wadell, Transmission Line Design Handbook, 4.4.3.1), copper thickness
neglected (it lowers Z by about 1 ohm).

    kd python3 src/impedance.py
"""
import numpy as np
from scipy.special import ellipk

import pcb
H, ER = pcb.DIELECTRIC[pcb.NLAYERS][0][1], pcb.DIELECTRIC[pcb.NLAYERS][0][3]


def _kr(k):
    return ellipk(k * k) / ellipk(1 - k * k)


def cpwg(w, s, h=H, er=ER):
    k = w / (w + 2 * s)
    k1 = np.tanh(np.pi * w / (4 * h)) / np.tanh(np.pi * (w + 2 * s) / (4 * h))
    a, b = 1 / _kr(k), _kr(k1)
    eeff = (1 + er * a * b) / (1 + a * b)
    return 60 * np.pi / np.sqrt(eeff) / (_kr(k) + _kr(k1)), eeff


if __name__ == '__main__':
    import board
    z, e = cpwg(board.RF_W, board.RF_GAP)
    print('RF line %.2f mm, gap %.2f mm: Z0 = %.1f ohm, eeff = %.2f' % (board.RF_W, board.RF_GAP, z, e))
