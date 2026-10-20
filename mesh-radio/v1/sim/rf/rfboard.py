# -*- coding: utf-8 -*-
"""Mesh Radio v1 RF networks, built from src/circuit.py and src/parts.py.

Every passive part in the RF paths comes from the circuit file (value, part
number, size), so a value change there is picked up here.  Integrated parts
(SKY13330, the antenna filter FL1, QPA9510, BGA7L1BN6, BAT15-02EL) are
behavioural models from their data sheets (README "Models").  The antenna
filter model is chosen by the part fitted in circuit.py (LFCG-1000+ since
0f1ee3c; the LFCN-1000+ model stays for the 19 Oct comparison in
followup.py).  Board traces are 50-ohm lines; the antenna section (filter ->
detector coupler -> U.FL, the ESD shunt inside the coupled run) takes its
geometry from src/layout.py, the other lengths are placement estimates
until the board is routed (LINES below).
"""
import os
import sys

import re

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
NETS_DET = ['REFL_CPL', 'REFL_DET']
NETS_RX = ['LNA_INM', 'LNA_AI']
NETS_BLE = ['NRF_ANT', 'BLE_50R', 'BLE_T', 'BLE_FEED']
# trace lengths between blocks, mm.  lpf_sw and sw_lfcn (switch RF1 -> filter RF IN) are the pad-to-pad
# distances src/layout.py places them at (1.1 / 2.1 mm; routed lengths will differ, study 1f sweeps them).
# The antenna section is drawn by layout.py: filter RF OUT -> flt_cpl -> the detector's coupled run
# (CPL_LEN, the ESD shunt's pad esd_from_end before its U.FL end) -> cpl_ufl -> U.FL signal pad; the
# coupled line's ends reach the 49.9 R and the diode through cpl_stub.  Read from layout.py below.
LINES = {'lpf_sw': 1.1, 'sw_lfcn': 2.1, 'sw_rx': 2.0, 'tx50_pad': 1.0}


def _layout_geometry():
    """Detector coupler and antenna-line geometry as src/layout.py draws it (regex on its source, so the
    sim needs no KiCad).  Falls back to the 20 Oct values if a pattern is not found."""
    g = dict(cpl_len=5.5, pitch=0.27, flt_cpl=0.9, cpl_ufl=1.6, esd_from_end=0.6, cpl_stub=1.0, rf_w=0.17, found=[])
    try:
        lay = open(os.path.join(SRC, 'layout.py')).read()
        brd = open(os.path.join(SRC, 'board.py')).read()
    except OSError:
        return g
    pats = {'cpl_len': (lay, r'^CPL_LEN\s*=\s*([0-9.]+)'), 'pitch': (lay, r'^RF_PITCH_CPL\s*=\s*([0-9.]+)'),
            'flt_cpl': (lay, r'xa\s*=\s*fl3\[0\]\s*\+\s*([0-9.]+)'), 'cpl_ufl': (lay, r'xb\s*\+\s*([0-9.]+)\s*-\s*sig\[0\]'),
            'esd_from_end': (lay, r'\(xb\s*-\s*([0-9.]+),\s*ya'), 'cpl_stub': (lay, r'\(xa,\s*yc\s*-\s*([0-9.]+)\)'),
            'rf_w': (brd, r'^RF_W,\s*RF_GAP\s*=\s*([0-9.]+)')}
    for k, (txt, p) in pats.items():
        m = re.search(p, txt, re.M)
        if m:
            g[k] = float(m.group(1))
            g['found'].append(k)
    g['gap'] = round(g['pitch'] - g['rf_w'], 4)
    return g


GEOM = _layout_geometry()
LINES.update(flt_cpl=GEOM['flt_cpl'], cpl_ufl=GEOM['cpl_ufl'], cpl_stub=GEOM['cpl_stub'])
_CPL_CACHE = {}


def coupler_params(gap=None):
    """Even/odd parameters of the coupled pair (0.17 mm lines, 0.25 mm to the pour) from coupler.py's 2-D
    field solve (~7 s, cached)."""
    gap = GEOM['gap'] if gap is None else gap
    if gap not in _CPL_CACHE:
        import coupler
        _CPL_CACHE[gap] = {k: float(v) for k, v in coupler.coupled(gap).items() if k in ('ze', 'zo', 'ee', 'eo', 'k')}
    return _CPL_CACHE[gap]


# REFL_DET as placed (src/placement.json, 20 Oct): the 1 nF and 100 k sit ~21 mm from the diode, by the nRF52840;
# a 0.1 mm track over In1 is ~63 ohm, eeff 3.32 (coupler.py field solve, 0.6 mm to any pour).
REFL_DET_TRACK = dict(length=21.0, z0=63.0, ee=3.32)
# BAT15-02EL (Infineon data sheet v1.0, 2018-06-30): LS 0.4 nH typ; C 0.20 typ / 0.24 max pF at 0 V;
# RF (differential, 10-50 mA) 8 typ / 10 max ohm.  RF model: Ls + Rs + Cj (junction node REFL_J).
BAT15_RF = dict(ls=0.4e-9, rs=8.0, cj=0.20e-12)


def _filter_ref():
    for c in COMPS:
        if parts.PARTS[c.part]['kind'] == 'FL' and 'ANT_SW' in c.pins.values():
            return c
    raise KeyError('no antenna filter on ANT_SW')


FL = _filter_ref()
FL_PART = FL.part                                 # 'LFCG1000' (or 'LFCN1000' before 0f1ee3c)
_flp = parts.PARTS[FL_PART]['symbol']['pins']
FL_IN = [p for p, (n, t) in _flp.items() if n == 'RF IN'][0]
FL_OUT = [p for p, (n, t) in _flp.items() if n == 'RF OUT'][0]
assert FL.pins[FL_IN] == 'ANT_SW' and FL.pins[FL_OUT] == 'ANT', 'antenna filter orientation changed in circuit.py'
FL_NAME = parts.PARTS[FL_PART]['mpn']

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
        # integrated-part spreads (README): switch loss typ..max, antenna-filter frequency scaling
        u = self.rng.uniform(0, 1, nsamp) if mode == 'mc' else np.zeros(nsamp)
        self.sw_u = u
        self.lfcn_k = (1 + self.rng.uniform(-0.01, 0.01, nsamp) + self.rng.uniform(-30e-6, 30e-6, nsamp) * (temp_c - 25)
                       ) if mode == 'mc' else np.ones(nsamp)
        # antenna-filter unit spread (not published, ASSUMED): loss x1.0-1.5 (LFCG-1000+ 0.62 -> ~0.9 dB at
        # 915 MHz; data-sheet maximum 1.8 dB DC-1000 MHz) and +-1 % frequency (+-30 ppm/C)
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

    def add_parts(self, ckt, nets, skip=(), only=None, remap=None):
        """Add the two-terminal parts on `nets`; remap {net: model node} places a net's parts on another
        node (a distributed net: the ESD shunt inside the coupled run, the detector's two ends)."""
        rm = remap or {}
        for c in rf_parts(nets):
            if c.ref in skip or (only is not None and c.ref not in only):
                continue
            a, b = rm.get(c.pins['1'], c.pins['1']), rm.get(c.pins['2'], c.pins['2'])
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
        """LFCN-1000+ as the lumped model fitted to Mini-Circuits' typical table (lfcn.py).  The board's
        filter until 0f1ee3c; kept for followup.py's comparison."""
        import lfcn
        lfcn.add(ckt, a, b, prefix='FL1_', k=self.lfcn_k.reshape(-1, 1), rscale=self.lfcn_r.reshape(-1, 1))
        return ckt

    def lfcg(self, ckt, a, b):
        """LFCG-1000+ (a = RF IN, pad 8; b = RF OUT, pad 4) as the lumped model fitted to Mini-Circuits'
        typical table (lfcn.G_FIT), with the same assumed unit spreads as the LFCN (loss x1.0-1.5,
        +-1 % frequency, +-30 ppm/C)."""
        import lfcn
        lfcn.add(ckt, a, b, prefix='FL1_', p=lfcn.G_FIT, k=self.lfcn_k.reshape(-1, 1), rscale=self.lfcn_r.reshape(-1, 1))
        return ckt

    def ant_filter(self, ckt, a, b):
        """The antenna filter circuit.py fits (FL1), RF IN at a."""
        return self.lfcg(ckt, a, b) if FL_PART == 'LFCG1000' else self.lfcn(ckt, a, b)

    def ant_section(self, c, a, cathode='designed', gap=None, lines=None):
        """Filter RF OUT (node a) -> flt_cpl line -> detector coupler main line (the 47 nH ESD shunt at
        esd_from_end before the coupler's U.FL end) -> cpl_ufl line -> U.FL ('ANT').  Coupled line: filter
        end -> stub -> 49.9 R (REFL_T); U.FL end -> stub -> BAT15 (anode REFL_A, junction REFL_J, cathode
        REFL_K).  cathode='designed': 1 nF and 100 k at the cathode; 'placed': REFL_K -> 21 mm track ->
        1 nF + 100 k (REFL_C), as src/placement.json has them; 'open': the 49.9 R but no diode; None: no
        detector parts at all (coupled line open: never used for the board)."""
        L = dict(self.lines, **(lines or {}))
        p = coupler_params(gap)
        lc = GEOM['cpl_len']
        l2 = min(GEOM['esd_from_end'], lc)
        c.add2(a, 'CPL_A1', R.Line(L['flt_cpl']), 'line_flt_cpl')
        c.addn(['CPL_A1', 'ANT_E', 'CPL_B1', 'CPL_BM'], R.CoupledLine(p['ze'], p['zo'], p['ee'], p['eo'], lc - l2), 'coupler_1')
        c.addn(['ANT_E', 'CPL_A2', 'CPL_BM', 'CPL_B2'], R.CoupledLine(p['ze'], p['zo'], p['ee'], p['eo'], l2), 'coupler_2')
        c.add2('CPL_A2', 'ANT', R.Line(L['cpl_ufl']), 'line_cpl_ufl')
        self.add_parts(c, NETS_ANT, remap={'ANT': 'ANT_E'})
        if cathode is None:
            return c
        c.add2('CPL_B1', 'REFL_T', R.Line(L['cpl_stub']), 'stub_term')
        c.add2('CPL_B2', 'REFL_A', R.Line(L['cpl_stub']), 'stub_diode')
        term = [x.ref for x in rf_parts(['REFL_CPL']) if parts.PARTS[x.part]['kind'] == 'R']
        self.add_parts(c, ['REFL_CPL'], only=term, remap={'REFL_CPL': 'REFL_T'})
        if cathode == 'open':           # the diode's anode left open (Thevenin source for the SPICE check)
            return c
        d = BAT15_RF
        c.add('REFL_A', 'REFL_J', R.Ind(d['ls'], 1e9, 1e9, 0, d['rs']), 'BAT15_LsRs')
        c.add('REFL_J', 'REFL_K', R.Cap(d['cj'], 0.0, 0.0), 'BAT15_Cj')
        if cathode == 'placed':
            t = REFL_DET_TRACK
            c.add2('REFL_K', 'REFL_C', R.Line(t['length'], z0=t['z0'], eps_eff=t['ee']), 'refl_det_track')
            self.add_parts(c, ['REFL_DET'], remap={'REFL_DET': 'REFL_C'})
        else:
            self.add_parts(c, ['REFL_DET'], remap={'REFL_DET': 'REFL_K'})
        return c

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

    def tx_out(self, with_pa=True, lines=None, cathode='designed', gap=None):
        """PA output network (optional) + LPF + line + switch + line + antenna filter + detector coupler
        (with its ESD shunt and detector) + line; antenna node 'ANT' (the U.FL)."""
        L = dict(self.lines, **(lines or {}))
        c = R.Circuit('tx_out')
        if with_pa:
            self.pa_out(c)
        self.add_parts(c, NETS_LPF)
        c.add2('PA_TX', 'SW2', R.Line(L['lpf_sw']), 'line_lpf_sw')
        self.sky13330(c, 'SW2', 'SW1', isolated=None)
        c.add2('SW1', 'ANT_SW', R.Line(L['sw_lfcn']), 'line_sw_lfcn')
        self.ant_filter(c, 'ANT_SW', 'LF_OUT')
        self.ant_section(c, 'LF_OUT', cathode=cathode, gap=gap, lines=lines)
        return c

    def sw_to_ant(self, lines=None):
        """Switch RF1 (node SW1) -> line -> antenna filter -> antenna section -> U.FL (ANT)."""
        L = dict(self.lines, **(lines or {}))
        c = R.Circuit('sw_ant')
        c.add2('SW1', 'ANT_SW', R.Line(L['sw_lfcn']), 'line_sw_lfcn')
        self.ant_filter(c, 'ANT_SW', 'LF_OUT')
        self.ant_section(c, 'LF_OUT', lines=lines)
        return c

    def rx_front(self):
        """U.FL (node ANT) -> antenna section (coupler, ESD shunt, detector) -> antenna filter ->
        switch RF1->RF3 -> RX_SW.  The 1 nF DC block and 11 nH input inductor that follow belong to
        the LNA's data-sheet application circuit (its NF and gain include them)."""
        c = R.Circuit('rx')
        self.ant_section(c, 'LF_OUT')
        self.ant_filter(c, 'ANT_SW', 'LF_OUT')
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
