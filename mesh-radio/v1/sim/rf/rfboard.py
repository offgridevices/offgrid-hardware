# -*- coding: utf-8 -*-
"""Mesh Radio v1 RF networks, built from src/circuit.py and src/parts.py.

Every passive part in the RF paths comes from the circuit file (value, part
number, size), so a value change there is picked up here.  Integrated parts
(SKY13330, LFCN-1000+, QPA9510, BGA7L1BN6) are behavioural models from
their data sheets (README "Models").  Board traces are short 50-ohm lines
of assumed length until the board is routed (LINES below).
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, '..', '..', 'src')
sys.path.insert(0, SRC)
sys.path.insert(0, HERE)
import circuit   # noqa: E402
import parts     # noqa: E402
import rflib as R   # noqa: E402

COMPS = circuit.build()
BY_REF = {c.ref: c for c in COMPS}

# ----------------------------------------------------------------------------- net groups
NETS_SX_TX = ['LORA_VRPA', 'LORA_RFO', 'LORA_TXA', 'LORA_TXB', 'LORA_TXC', 'LORA_TX50', 'PA_DRIVE', 'PA_RFIN']
NETS_PA_OUT = ['VPA', 'PA_OUT', 'PA_M1', 'PA_2F0']
NETS_LPF = ['PA_M2', 'PA_M3', 'PA_TX']
NETS_ANT = ['ANT']
NETS_RX = ['LNA_INM', 'LNA_AI']
NETS_BLE = ['NRF_ANT', 'BLE_50R', 'BLE_T', 'BLE_FEED']
# trace lengths between blocks, mm (assumed until layout; study 1 sweeps them)
LINES = {'lpf_sw': 2.0, 'sw_lfcn': 2.0, 'lfcn_ant': 2.0, 'tx50_pad': 1.0, 'sw_rx': 2.0}

# QPA9510 internal model (ASSUMED; README): bond wires from the die to the RF OUT pins,
# die output capacitance, and the 2F0 trap bond wire (tuned with the external 1.5 pF to 2f).
PA_LBOND = 0.25e-9
PA_CDIE = 6e-12
PA_L2F0 = 4.6e-9


def _refs(pred):
    return [c.ref for c in COMPS if pred(c)]


PAD_REFS = _refs(lambda c: parts.PARTS[c.part]['kind'] == 'R' and set(c.pins.values()) <= {'LORA_TX50', 'PA_DRIVE', 'GND'})
DCBLOCK_PA = _refs(lambda c: set(c.pins.values()) == {'PA_DRIVE', 'PA_RFIN'})[0]
DCBLOCK_OUT = _refs(lambda c: set(c.pins.values()) == {'PA_M1', 'PA_M2'})[0]


def rf_parts(nets):
    """Two-terminal R/L/C parts whose pins all sit on `nets` or GND."""
    s = set(nets) | {'GND'}
    out = []
    for c in COMPS:
        p = parts.PARTS[c.part]
        if p['kind'] not in ('R', 'L', 'C'):
            continue
        pins = [n for n in c.pins.values()]
        if all(n in s for n in pins) and any(n in nets for n in pins):
            out.append(c)
    return out


BLE_PI_REFS = [c.ref for c in rf_parts(['NRF_ANT', 'BLE_50R'])]


class Board:
    """Holds the sampled values of every RF part, so one Monte Carlo draw is used
    consistently in all the networks of a study."""

    def __init__(self, nsamp=1, temp_c=25.0, mode='nom', seed=0, overrides=None, lines=None, extra=None):
        self.n, self.t, self.mode = nsamp, temp_c, mode
        self.rng = np.random.default_rng(seed)
        self.over = overrides or {}          # ref -> part dict (a parts.py entry or a synthetic one)
        self.lines = dict(LINES, **(lines or {}))
        self.extra = extra or {}
        self.info, self.val = {}, {}
        # integrated-part spreads (README): switch loss typ..max, LFCN frequency scaling
        u = self.rng.uniform(0, 1, nsamp) if mode == 'mc' else np.zeros(nsamp)
        self.sw_u = u
        self.lfcn_k = (1 + self.rng.uniform(-0.01, 0.01, nsamp) + self.rng.uniform(-30e-6, 30e-6, nsamp) * (temp_c - 25)
                       ) if mode == 'mc' else np.ones(nsamp)
        # LFCN unit spread (not published, ASSUMED): loss x1.0-1.5 (0.66 -> ~0.95 dB at 915 MHz,
        # inside the 1.0 dB data-sheet maximum) and +-1 % frequency (+-30 ppm/C)
        self.lfcn_r = self.rng.uniform(1.0, 1.5, nsamp) if mode == 'mc' else np.ones(nsamp)

    def part(self, ref):
        c = BY_REF[ref]
        return self.over.get(ref, parts.PARTS[c.part])

    def value(self, ref):
        if ref not in self.val:
            info = R.part_info(self.part(ref))
            self.info[ref] = info
            self.val[ref] = R.draw(info, self.rng, self.n, self.t, self.mode)
        return self.val[ref]

    def add_parts(self, ckt, nets, skip=(), only=None):
        for c in rf_parts(nets):
            if c.ref in skip or (only is not None and c.ref not in only):
                continue
            a, b = c.pins['1'], c.pins['2']
            v = self.value(c.ref)
            info = self.info[c.ref]
            el = R.element(info, v, shunt=('GND' in (a, b)))
            ckt.add(a, b, el, c.ref)
        return ckt

    # ------------------------------------------------------------------ integrated parts
    def sky13330(self, ckt, a, b, isolated=None):
        """SKY13330 through path a -> b (data sheet 201407E table 3): insertion loss
        0.30 typ / 0.35 max dB to 1 GHz, 0.35 / 0.50 to 2.5 GHz, 0.45 / 0.65 to 5 GHz,
        0.60 / 0.80 to 6 GHz; return loss 20 dB (0.1 pF at each port gives |S11| <= 0.1
        to 6 GHz); the isolated port is a reflective short (data sheet)."""
        u = self.sw_u.reshape(-1, 1)

        def il_db(f):
            fe = [0.1e9, 1.0e9, 1.0001e9, 2.5e9, 2.5001e9, 5e9, 5.0001e9, 6e9, 12e9]
            typ = [0.30, 0.30, 0.35, 0.35, 0.45, 0.45, 0.60, 0.60, 0.80]
            mx = [0.35, 0.35, 0.50, 0.50, 0.65, 0.65, 0.80, 0.80, 1.00]
            t, m = np.interp(f, fe, typ), np.interp(f, fe, mx)
            return t + u * (m - t)

        def sfn(w):
            f = w / (2 * np.pi)
            s21 = 10 ** (-il_db(f) / 20) * np.exp(-1j * w * 0.5e-3 * np.sqrt(3.3) / R.C0_LIGHT)
            z = np.zeros_like(s21)
            return z, s21, s21, z

        ckt.add(a, 'GND', R.Cap(0.1e-12, 0.0, 0.0), 'SW_C_' + a)
        ckt.add(b, 'GND', R.Cap(0.1e-12, 0.0, 0.0), 'SW_C_' + b)
        ckt.add2(a, b, R.TwoPortS(sfn), 'SKY13330')
        if isolated:
            ckt.add(isolated, 'GND', R.Res(0.5, 0.1e-9, 0.0), 'SW_short_' + isolated)
        return ckt

    def lfcn(self, ckt, a, b):
        """LFCN-1000+ as the lumped model fitted to Mini-Circuits' typical table (lfcn.py)."""
        import lfcn
        lfcn.add(ckt, a, b, prefix='FL1_', k=self.lfcn_k.reshape(-1, 1), rscale=self.lfcn_r.reshape(-1, 1))
        return ckt

    # ------------------------------------------------------------------ networks
    def sx_match(self):
        """SX1262 RFO -> VR_PA feed, 2f trap and match -> LORA_TX50 (Semtech values)."""
        c = R.Circuit('sx_match')
        self.add_parts(c, NETS_SX_TX[:6], skip=PAD_REFS)
        return c

    def pad(self, pa_in_gamma=None):
        """LORA_TX50 -> 68/150/68 pi pad -> 47 pF DC block -> PA_RFIN (QPA9510 input,
        reflection pa_in_gamma if given)."""
        c = R.Circuit('pad')
        self.add_parts(c, ['LORA_TX50', 'PA_DRIVE', 'PA_RFIN'], only=PAD_REFS + [DCBLOCK_PA])
        if pa_in_gamma is not None:
            zin = R.gamma_to_z(pa_in_gamma)
            c.add('PA_RFIN', 'GND', R.Admittance(lambda w, z=zin: np.ones(w.shape) / z), 'QPA9510_in')
        return c

    def lpf_only(self):
        c = R.Circuit('lpf')
        self.add_parts(c, NETS_LPF)
        return c

    def pa_out(self, c):
        """QPA9510 output: die (current source node DIE) -> bond wires -> PA_OUT pins and
        the external match, choke and 2F0 trap from circuit.py."""
        c.add('DIE', 'PA_OUT', R.Ind(PA_LBOND, 40, 1e9, 0, 0.005), 'PA_bond')
        c.add('DIE', 'GND', R.Cap(PA_CDIE, 0.05, 0.0), 'PA_Cdie')
        c.add('DIE', 'PA_2F0', R.Ind(PA_L2F0, 30, 1e9, 0, 0.05), 'PA_bond2f0')
        self.add_parts(c, NETS_PA_OUT)
        self.add_parts(c, ['PA_M1', 'PA_M2'], only=[DCBLOCK_OUT])
        return c

    def tx_out(self, with_pa=True, lines=None):
        """PA output network (optional) + LPF + line + switch + line + LFCN + line + ESD
        shunt; antenna node 'ANT_P' (the U.FL)."""
        L = dict(self.lines, **(lines or {}))
        c = R.Circuit('tx_out')
        if with_pa:
            self.pa_out(c)
        self.add_parts(c, NETS_LPF)
        c.add2('PA_TX', 'SW2', R.Line(L['lpf_sw']), 'line_lpf_sw')
        self.sky13330(c, 'SW2', 'SW1', isolated=None)
        c.add2('SW1', 'ANT_SW', R.Line(L['sw_lfcn']), 'line_sw_lfcn')
        self.lfcn(c, 'ANT_SW', 'LF_OUT')
        c.add2('LF_OUT', 'ANT', R.Line(L['lfcn_ant']), 'line_lfcn_ant')
        self.add_parts(c, NETS_ANT)
        return c

    def rx_front(self):
        """U.FL (node ANT) -> ESD shunt -> LFCN -> switch RF1->RF3 -> RX_SW.  The 1 nF DC
        block and 11 nH input inductor that follow belong to the LNA's data-sheet
        application circuit (its NF and gain include them)."""
        c = R.Circuit('rx')
        self.add_parts(c, NETS_ANT)
        c.add2('LF_OUT', 'ANT', R.Line(self.lines['lfcn_ant']), 'line_lfcn_ant')
        self.lfcn(c, 'ANT_SW', 'LF_OUT')
        c.add2('SW1', 'ANT_SW', R.Line(self.lines['sw_lfcn']), 'line_sw_lfcn')
        self.sky13330(c, 'SW1', 'SW3')
        c.add2('SW3', 'RX_SW', R.Line(self.lines['sw_rx']), 'line_sw_rx')
        return c

    def ble_pi(self):
        """Nordic's ANT network: shunt 0.8 pF, series 4.7 nH, shunt 0.5 pF."""
        c = R.Circuit('ble_pi')
        self.add_parts(c, ['NRF_ANT', 'BLE_50R'])
        return c

    def ble_tee(self):
        """Johanson's tee for the 2450AT18A100: series 1.0 pF, shunt 2.7 nH, series 3.9 nH."""
        c = R.Circuit('ble_tee')
        self.add_parts(c, ['BLE_50R', 'BLE_T', 'BLE_FEED'], skip=[r for r in BLE_PI_REFS])
        return c
    def ble(self):
        c = R.Circuit('ble')
        self.add_parts(c, NETS_BLE)
        return c
