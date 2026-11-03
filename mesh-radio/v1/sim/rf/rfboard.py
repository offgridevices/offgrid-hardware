# -*- coding: utf-8 -*-
"""Mesh Radio v1 RF networks, built from src/circuit.py and src/parts.py.

Every passive part in the RF paths comes from the circuit file (value, part
number, size), so a value change there is picked up here.  Integrated parts
(SKY13330, the antenna filter FL1, QPA9510, BGA7L1BN6, BAT15-02EL) are
behavioural models from their data sheets (README "Models").  The antenna
filter model is chosen by the part fitted in circuit.py (LFCG-1000+ since
0f1ee3c; the LFCN-1000+ model stays for the 19 Oct comparison in
followup.py).

Board traces (since 3 Nov): every RF line as routed, from routed.json
(routed.py reads it off mesh-radio.kicad_pcb): each net is a netlist of line
pieces between its parts' pads (the part of a track inside a part's own pad
is left out: the pad is the part's node), the antenna section (filter ->
detector coupler -> U.FL, the ESD shunt's stub, the two terminations and
the two diodes on the coupled line) from the same file, and each shunt
part's ground return (via in its pad, or the pour to the nearest via).
RF_ROUTED=0 (environment) runs the pre-route model instead: lumped parts
joined at their nets, the placement lengths in LINES, the antenna section
from src/layout.py, 0.15 nH per shunt ground; README "What changed on 3 Nov".
"""
import os
import sys

import json
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
NETS_DET = ['REFL_CPL', 'REFL_DET', 'FWD_DET']
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
# the pre-route antenna section: the stubs as layout.py drew them, the 49.9 R and diode together at each end
LINES.update(esd_stub=0.0, stub_term=GEOM['cpl_stub'], term_fwd=0.0, stub_rterm=GEOM['cpl_stub'], rterm_diode=0.0)
_CPL_CACHE = {}

# ----------------------------------------------------------------------------- the routed board (routed.json)
ROUTED_FILE = os.environ.get('RF_ROUTED_FILE', os.path.join(HERE, 'routed.json'))   # (RF_ROUTED_FILE: a trial board's)
USE_ROUTED = os.environ.get('RF_ROUTED', '1') != '0' and os.path.exists(ROUTED_FILE)
RT = json.load(open(ROUTED_FILE)) if USE_ROUTED else None
# A 0.17 mm line on F.Cu over In1 (2-D field solve, coupler.single_line, 35 um copper and mask): 49.9 ohm / eeff
# 3.30 with the pour 0.25 mm away on both sides, 50.8 ohm / 3.35 with no copper within 0.8 mm.  On 0.12 mm of
# prepreg it is nearly a microstrip; each routed piece gets the mix its open fraction (routed.json) gives.
Z_CPW, EE_CPW, Z_MS, EE_MS = 49.9, 3.30, 50.8, 3.35
MANUAL = ('ANT', 'REFL_CPL')       # the antenna section: ant_section() builds it from the routed lengths
ROUTED_NETS = set(RT['nets']) - set(MANUAL) if RT else set()
# shunt ground return on the routed board: a 0.4/0.2 mm via in the pad reaches In1 (0.15 mm down) through
# 0.2 h (1 + ln(4h/d)) = 0.06 nH; a pad with no via in it adds the top pour to its nearest via, 0.2 nH/mm
# (pour 0.12 mm over In1: 0.15 nH per square, about 1.4 squares per mm; ESTIMATE)
V_TO_IN1 = 0.06e-9
POUR_L_MM = 0.2e-9


def _ref_part(part):
    return [c.ref for c in COMPS if c.part == part][0]


def _pin_on(ref, net):
    ps = [p for p, n in BY_REF[ref].pins.items() if n == net]
    return sorted(ps, key=lambda p: (len(p), p))


def _between(a, b, kind=None):
    return [c.ref for c in COMPS if set(c.pins.values()) == {a, b}
            and (kind is None or parts.PARTS[c.part]['kind'] == kind)]


def _ports():
    """The pad each routed net's model node (named as the net) sits at: the chip pin where there is one, else the
    series part that the pre-route model used as the net's port."""
    P = {}
    sx, pa, sw, nrf, ae = (_ref_part(x) for x in ('SX1262', 'QPA9510', 'SKY13330', 'NRF52840', 'ANT2450'))
    lna = _ref_part('BGA7L1BN6')
    for net, ref in (('LORA_RFO', sx), ('PA_RFIN', pa), ('PA_OUT', pa), ('PA_TX', sw), ('ANT_SW', FL.ref),
                     ('NRF_ANT', nrf), ('BLE_FEED', ae), ('LNA_AI', lna), ('LNA_OUT', lna),
                     ('LORA_TX50', _between('LORA_TXC', 'LORA_TX50')[0]), ('PA_M1', DCBLOCK_OUT), ('PA_M2', DCBLOCK_OUT),
                     ('PA_M3', _between('PA_M2', 'PA_M3', 'L')[0]), ('BLE_50R', _between('NRF_ANT', 'BLE_50R')[0])):
        P[net] = '%s.%s' % (ref, _pin_on(ref, net)[0])
    rx = [c.ref for c in COMPS if 'RX_SW' in c.pins.values() and c.ref != sw][0]
    P['RX_SW'] = '%s.%s' % (rx, _pin_on(rx, 'RX_SW')[0])
    return P


def rnode(net, k):
    """Model node name of node k of a routed net: the net's name at its port pad, net:REF.PIN at another pad,
    net#k at a junction."""
    d = RT['nets'][net]
    pk = sorted(p for p, kk in d['pads'].items() if kk == k)
    if PORTS.get(net) in pk:
        return net
    return '%s:%s' % (net, pk[0]) if pk else '%s#%d' % (net, k)


def pad_node(net, ref, pin):
    key = '%s.%s' % (ref, pin)
    d = RT['nets'][net]
    if key not in d['pads']:
        raise KeyError('%s has no pad %s on the routed board' % (net, key))
    return rnode(net, d['pads'][key])


def _path(net, k0, k1):
    """Length (outside pads) along a routed net between nodes k0 and k1."""
    import heapq
    d = RT['nets'][net]
    adj = {}
    for e in d['edges']:
        adj.setdefault(e['a'], []).append((e['b'], e['len_out']))
        adj.setdefault(e['b'], []).append((e['a'], e['len_out']))
    dist, hq = {k0: 0.0}, [(0.0, k0)]
    while hq:
        x, u = heapq.heappop(hq)
        if u == k1:
            return x
        for v, w in adj.get(u, []):
            if x + w < dist.get(v, 1e9):
                dist[v] = x + w
                heapq.heappush(hq, (x + w, v))
    raise ValueError('no path on %s' % net)


def _routed_antenna():
    """The antenna section's lengths on the routed board (mm, outside the pads): FL1 RF OUT -> coupled run ->
    U.FL along ANT, the ESD shunt's junction and stub; on the coupled line its two ends to the 49.9 R
    terminations and on to the two diodes."""
    a, c = RT['nets']['ANT'], RT['nets']['REFL_CPL']
    run = max(c['edges'], key=lambda e: e['len'])
    na, nc = a['nodes'], c['nodes']
    kf, ku = a['pads']['%s.%s' % (FL.ref, FL_OUT)], a['pads']['%s.1' % _ref_part('UFL')]
    pf, pu = np.array(na[kf]), np.array(na[ku])
    u = (pu - pf) / np.linalg.norm(pu - pf)
    s = lambda p: float(np.dot(np.array(p) - pf, u))
    e0, e1 = nc[run['a']], nc[run['b']]
    (kc0, p0), (kc1, p1) = sorted(((run['a'], e0), (run['b'], e1)), key=lambda t: s(t[1]))
    dv = np.array(p0) - pf
    perp = abs(float(u[0] * dv[1] - u[1] * dv[0]))
    esd = [c_ for c_ in rf_parts(NETS_ANT)][0].ref
    ke = a['pads']['%s.%s' % (esd, _pin_on(esd, 'ANT')[0])]
    stub = [e for e in a['edges'] if ke in (e['a'], e['b'])][0]
    kj = stub['b'] if stub['a'] == ke else stub['a']
    trim = lambda k: sum(e['len'] - e['len_out'] for e in a['edges'] if k in (e['a'], e['b']) and e is not stub)
    term = [x for x in rf_parts(['REFL_CPL']) if parts.PARTS[x.part]['kind'] == 'R']
    t_flt = [x.ref for x in term if 'U.FL end' not in x.note][0]
    t_ufl = [x.ref for x in term if 'U.FL end' in x.note]
    pk = lambda ref: c['pads']['%s.%s' % (ref, _pin_on(ref, 'REFL_CPL')[0])]
    g = dict(cpl_len=run['len'], gap=round(perp - run['w'], 4), flt_cpl=s(p0) - trim(kf), cpl_ufl=s(pu) - s(p1) - trim(ku),
             esd_from_end=s(p1) - s(na[kj]), esd_stub=stub['len_out'], stub_term=_path('REFL_CPL', kc0, pk(t_flt)))
    g['term_fwd'] = _path('REFL_CPL', pk(t_flt), pk(DIODE_FWD.ref)) if DIODE_FWD is not None else 0.0
    if t_ufl:
        g['stub_rterm'] = _path('REFL_CPL', kc1, pk(t_ufl[0]))
        g['rterm_diode'] = _path('REFL_CPL', pk(t_ufl[0]), pk(DIODE_REFL.ref))
    else:
        g['stub_rterm'], g['rterm_diode'] = _path('REFL_CPL', kc1, pk(DIODE_REFL.ref)), 0.0
    g['cpl_stub'] = g['stub_term']
    return {k: round(float(v), 4) for k, v in g.items()}


def ground_l(ref):
    """Ground-return inductance (H) of a shunt part on the routed board (None: not on the board's list)."""
    sg = RT['shunt_ground'].get(ref) if RT else None
    if not sg:
        return None
    q = sg[0]
    if q['vias_in_pad']:
        return V_TO_IN1 / q['vias_in_pad']
    return V_TO_IN1 + POUR_L_MM * q['edge_to_via']


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
FWD_DET_TRACK = None
# Detector diode RF models: Ls + Rs + Cj (junction node REFL_J / FWD_J), by the part circuit.py fits.
#   BAT15-02EL (Infineon data sheet v1.0, 2018-06-30): LS 0.4 nH; C 0.20 typ / 0.24 max pF at 0 V; RF 8 / 10 ohm.
#   BAT68-04W (Infineon BAT68 data sheet 2011-06-15): LS 1.4 nH (SOT323); CT 0.75 pF at 0 V, ~0.6 pF at 1 V,
#   0.55 pF at 4 V (fig.), <= 1 pF max; RS 9.2 ohm (fit to the IF-VF curves, sim/rf/run.py); D2 shorted.
DIODE_RF = {'BAT15': dict(ls=0.4e-9, rs=8.0, cj=0.20e-12, cj_max=0.24e-12),
            'BAT68_04W': dict(ls=1.4e-9, rs=9.2, cj=0.65e-12, cj_max=1.0e-12)}


def _det_diode(net):
    for c in COMPS:
        if parts.PARTS[c.part]['kind'] == 'D' and net in c.pins.values() and 'REFL_CPL' in c.pins.values():
            return c
    return None


DIODE_REFL = _det_diode('REFL_DET')
DIODE_FWD = _det_diode('FWD_DET')          # None before the 20 Oct ratio detector
# RF_DIODE=BAT15 (environment) runs the studies with another diode in the same places, for comparison
DIODE_PART = os.environ.get('RF_DIODE') or DIODE_REFL.part
BAT15_RF = DIODE_RF['BAT15']               # kept for older scripts


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
PA_REF = _ref_part('QPA9510')
SW_REF = _ref_part('SKY13330')
ESD_REF = [c.ref for c in rf_parts(NETS_ANT)][0]

PORTS = _ports() if RT else {}
AG_ROUTED = _routed_antenna() if RT else None
LINES_ROUTED = dict(LINES, lpf_sw=0.0, sw_lfcn=0.0, sw_rx=0.0, tx50_pad=0.0, **(AG_ROUTED or {}))
GEOM_PLACED = dict(GEOM)
if RT:
    GEOM.update({k: AG_ROUTED[k] for k in ('cpl_len', 'gap', 'flt_cpl', 'cpl_ufl', 'esd_from_end', 'cpl_stub')})
    GEOM['source'] = 'routed.json (%s)' % RT['board']
    # the detector diodes' cathodes to their 1 nF, along the routed DC track (0.1 mm, F.Cu over In1 near the
    # diode; ~63 ohm as in the 20 Oct note above)
    REFL_DET_TRACK = dict(length=RT['detector_dc']['REFL_DET']['cathode_to_cap_mm'], z0=63.0, ee=3.32)
    if 'FWD_DET' in RT['detector_dc']:
        FWD_DET_TRACK = dict(length=RT['detector_dc']['FWD_DET']['cathode_to_cap_mm'], z0=63.0, ee=3.32)
else:
    GEOM['source'] = 'src/layout.py (pre-route)'


def _tie(c, a, b, length, label):
    """Join two model nodes: a line of `length` mm, or a 1 mohm link at zero length."""
    if length and length > 1e-6:
        c.add2(a, b, R.Line(length), label)
    else:
        c.add(a, b, R.Res(1e-3, 0.0, 0.0), label)


def pin_node(ref, pin, routed=None):
    """The model node a part's pin sits on (as Board.add_parts places it): its pad's node on a routed net."""
    routed = USE_ROUTED if routed is None else (routed and USE_ROUTED)
    net = BY_REF[ref].pins[pin]
    if net == 'GND':
        return 'GND'
    if ref == ESD_REF and net == 'ANT':
        return 'ESD_P' if (routed and AG_ROUTED['esd_stub'] > 1e-6) else 'ANT_E'
    if routed and net in ROUTED_NETS:
        return pad_node(net, ref, pin)
    return net


class Board:
    """Holds the sampled values of every RF part, so one Monte Carlo draw is used
    consistently in all the networks of a study."""

    def __init__(self, nsamp=1, temp_c=25.0, mode='nom', seed=0, overrides=None, lines=None, extra=None, routed=None):
        self.n, self.t, self.mode = nsamp, temp_c, mode
        self.rng = np.random.default_rng(seed)
        self.over = overrides or {}          # ref -> part dict (a parts.py entry or a synthetic one)
        # routed: the board as routed (routed.json); False: the pre-route model (lumped nets, LINES)
        self.routed = USE_ROUTED if routed is None else (routed and USE_ROUTED)
        # lines: in the routed model lpf_sw / sw_lfcn / sw_rx are EXTRA lengths in series (0 = as routed)
        self.lines = dict(LINES_ROUTED if self.routed else LINES, **(lines or {}))
        self.no_route = set()                # routed nets to leave lumped (sensitivity runs)
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

    def route(self, ckt, net):
        """Put a routed net's line pieces into ckt (once); False if the net is not routed in this model."""
        if not self.routed or net not in ROUTED_NETS or net in self.no_route:
            return False
        if not hasattr(ckt, '_routed'):
            ckt._routed = set()
        if net in ckt._routed:
            return True
        ckt._routed.add(net)
        for i, e in enumerate(RT['nets'][net]['edges']):
            a, b = rnode(net, e['a']), rnode(net, e['b'])
            if a == b:
                continue
            if e['len_out'] < 0.005:
                ckt.add(a, b, R.Res(1e-3, 0.0, 0.0), 'rt_%s_%d' % (net, i))
            else:
                f = e['open_frac']
                ckt.add2(a, b, R.Line(e['len_out'], z0=Z_CPW + f * (Z_MS - Z_CPW), eps_eff=EE_CPW + f * (EE_MS - EE_CPW)),
                         'rt_%s_%d' % (net, i))
        return True

    def node(self, ckt, net):
        """The model node named `net` (its routed lines put in ckt when it is routed)."""
        self.route(ckt, net)
        return net

    def add_parts(self, ckt, nets, skip=(), only=None, remap=None):
        """Add the two-terminal parts on `nets`; remap {net: model node} places a net's parts on another
        node (a distributed net: the ESD shunt inside the coupled run, the detector's two ends).  On the routed
        board each pin sits on its pad's node of its net's routed lines, and a shunt part's ground return is
        the board's (ground_l)."""
        rm = remap or {}
        for c in rf_parts(nets):
            if c.ref in skip or (only is not None and c.ref not in only):
                continue
            nd = []
            for pin in ('1', '2'):
                net = c.pins[pin]
                if net in rm:
                    nd.append(rm[net])
                elif net != 'GND' and self.route(ckt, net):
                    nd.append(pad_node(net, c.ref, pin))
                else:
                    nd.append(net)
            a, b = nd
            v = self.value(c.ref)
            info = self.info[c.ref]
            el = R.element(info, v, shunt=('GND' in (a, b)), lmount=ground_l(c.ref) if self.routed else None)
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

    def ant_section(self, c, a, cathode='designed', gap=None, lines=None, cj=None):
        """Filter RF OUT (node a) -> flt_cpl line -> detector coupler main line (the 47 nH ESD shunt at
        esd_from_end before the coupler's U.FL end) -> cpl_ufl line -> U.FL ('ANT').  Coupled line: filter
        end -> stub -> 49.9 R (REFL_T); U.FL end -> stub -> BAT15 (anode REFL_A, junction REFL_J, cathode
        REFL_K).  cathode='designed': 1 nF and 100 k at the cathode; 'placed': REFL_K -> 21 mm track ->
        1 nF + 100 k (REFL_C), as src/placement.json has them; 'open': the 49.9 Rs but no diode; None: no
        detector parts at all (coupled line open: never used for the board)."""
        L = dict(self.lines, **(lines or {}))
        G = AG_ROUTED if self.routed else GEOM_PLACED
        p = coupler_params(gap)
        lc = G['cpl_len']
        l2 = min(G['esd_from_end'], lc)
        c.add2(a, 'CPL_A1', R.Line(L['flt_cpl']), 'line_flt_cpl')
        c.addn(['CPL_A1', 'ANT_E', 'CPL_B1', 'CPL_BM'], R.CoupledLine(p['ze'], p['zo'], p['ee'], p['eo'], lc - l2), 'coupler_1')
        c.addn(['ANT_E', 'CPL_A2', 'CPL_BM', 'CPL_B2'], R.CoupledLine(p['ze'], p['zo'], p['ee'], p['eo'], l2), 'coupler_2')
        c.add2('CPL_A2', 'ANT', R.Line(L['cpl_ufl']), 'line_cpl_ufl')
        esd = 'ANT_E'
        if L['esd_stub'] > 1e-6:          # the routed stub from the line to the ESD shunt's pad
            esd = 'ESD_P'
            c.add2('ANT_E', esd, R.Line(L['esd_stub']), 'stub_esd')
        self.add_parts(c, NETS_ANT, remap={'ANT': esd})
        if cathode is None:
            return c
        # the coupled line's filter end -> its 49.9 R (REFL_T) [-> on to the forward diode (FWD_A)]; its U.FL end ->
        # the second 49.9 R (REFL_R) [-> on to the reflected diode (REFL_A)].  Pre-route: each pair at one node.
        c.add2('CPL_B1', 'REFL_T', R.Line(L['stub_term']), 'stub_term')
        rr = 'REFL_R' if L['rterm_diode'] > 1e-6 else 'REFL_A'
        c.add2('CPL_B2', rr, R.Line(L['stub_rterm']), 'stub_diode')
        if rr != 'REFL_A':
            c.add2(rr, 'REFL_A', R.Line(L['rterm_diode']), 'line_rterm_diode')
        fa = 'FWD_A' if L['term_fwd'] > 1e-6 else 'REFL_T'
        if fa != 'REFL_T':
            c.add2('REFL_T', fa, R.Line(L['term_fwd']), 'line_term_fwd')
        # terminations: the 49.9 R at the filter end (REFL_T) and, since 20 Oct, a second one at the U.FL end by the
        # reflected diode; circuit.py's notes say which end each is
        term = [x for x in rf_parts(['REFL_CPL']) if parts.PARTS[x.part]['kind'] == 'R']
        t_flt = [x.ref for x in term if 'U.FL end' not in x.note]
        t_ufl = [x.ref for x in term if 'U.FL end' in x.note]
        self.add_parts(c, ['REFL_CPL'], only=t_flt, remap={'REFL_CPL': 'REFL_T'})
        self.add_parts(c, ['REFL_CPL'], only=t_ufl, remap={'REFL_CPL': rr})
        if cathode == 'open':           # the diode's anode left open (Thevenin source for the SPICE check)
            return c
        d = dict(DIODE_RF[DIODE_PART])
        if cj is not None:
            d['cj'] = cj
        c.add('REFL_A', 'REFL_J', R.Ind(d['ls'], 1e9, 1e9, 0, d['rs']), 'Drefl_LsRs')
        c.add('REFL_J', 'REFL_K', R.Cap(d['cj'], 0.0, 0.0), 'Drefl_Cj')
        if DIODE_FWD is not None:
            # the forward diode at the 49.9 R end of the coupled line (routed: past the 49.9 R), its 1 nF + 100 k at
            # its cathode ('placed': along the routed track)
            c.add(fa, 'FWD_J', R.Ind(d['ls'], 1e9, 1e9, 0, d['rs']), 'Dfwd_LsRs')
            c.add('FWD_J', 'FWD_K', R.Cap(d['cj'], 0.0, 0.0), 'Dfwd_Cj')
            if cathode == 'placed' and FWD_DET_TRACK:
                t = FWD_DET_TRACK
                c.add2('FWD_K', 'FWD_C', R.Line(t['length'], z0=t['z0'], eps_eff=t['ee']), 'fwd_det_track')
                self.add_parts(c, ['FWD_DET'], remap={'FWD_DET': 'FWD_C'})
            else:
                self.add_parts(c, ['FWD_DET'], remap={'FWD_DET': 'FWD_K'})
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
        pins = _pin_on(PA_REF, 'PA_OUT')
        if self.route(c, 'PA_OUT'):          # routed: a bond wire to each RF OUT pin's pad, together PA_LBOND
            for p_ in pins:
                c.add('DIE', pad_node('PA_OUT', PA_REF, p_), R.Ind(PA_LBOND * len(pins), 40, 1e9, 0, 0.005 * len(pins)),
                      'PA_bond' + p_)
        else:
            c.add('DIE', 'PA_OUT', R.Ind(PA_LBOND, 40, 1e9, 0, 0.005), 'PA_bond')
        c.add('DIE', 'GND', R.Cap(PA_CDIE, 0.05, 0.0), 'PA_Cdie')
        c.add('DIE', 'PA_2F0', R.Ind(PA_L2F0, 30, 1e9, 0, 0.05), 'PA_bond2f0')
        self.add_parts(c, NETS_PA_OUT)
        self.add_parts(c, ['PA_M1', 'PA_M2'], only=[DCBLOCK_OUT])
        return c

    def tx_out(self, with_pa=True, lines=None, cathode='designed', gap=None, cj=None):
        """PA output network (optional) + LPF + line + switch + line + antenna filter + detector coupler
        (with its ESD shunt and detector) + line; antenna node 'ANT' (the U.FL)."""
        L = dict(self.lines, **(lines or {}))
        c = R.Circuit('tx_out')
        if with_pa:
            self.pa_out(c)
        self.add_parts(c, NETS_LPF)
        if self.routed:                      # PA_TX is the switch's RF2 pad; lpf_sw adds line there
            _tie(c, self.node(c, 'PA_TX'), 'SW2', L['lpf_sw'], 'line_lpf_sw')
        else:
            c.add2('PA_TX', 'SW2', R.Line(L['lpf_sw']), 'line_lpf_sw')
        self.sky13330(c, 'SW2', 'SW1', isolated=None)
        self._sw_ant_line(c, L)
        self.ant_filter(c, 'ANT_SW', 'LF_OUT')
        self.ant_section(c, 'LF_OUT', cathode=cathode, gap=gap, lines=lines, cj=cj)
        return c

    def _sw_ant_line(self, c, L):
        """Switch RF1 (SW1) to the filter's RF IN (ANT_SW): the routed ANT_SW net (plus sw_lfcn), or a line."""
        if self.routed and self.route(c, 'ANT_SW'):
            _tie(c, 'SW1', pad_node('ANT_SW', SW_REF, _pin_on(SW_REF, 'ANT_SW')[0]), L['sw_lfcn'], 'line_sw_lfcn')
        else:
            c.add2('SW1', 'ANT_SW', R.Line(L['sw_lfcn']), 'line_sw_lfcn')

    def _sw_rx_line(self, c, L):
        if self.routed and self.route(c, 'RX_SW'):
            _tie(c, 'SW3', pad_node('RX_SW', SW_REF, _pin_on(SW_REF, 'RX_SW')[0]), L['sw_rx'], 'line_sw_rx')
        else:
            c.add2('SW3', 'RX_SW', R.Line(L['sw_rx']), 'line_sw_rx')

    def sw_to_ant(self, lines=None):
        """Switch RF1 (node SW1) -> line -> antenna filter -> antenna section -> U.FL (ANT)."""
        L = dict(self.lines, **(lines or {}))
        c = R.Circuit('sw_ant')
        self._sw_ant_line(c, L)
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
        self._sw_ant_line(c, self.lines)
        self.sky13330(c, 'SW1', 'SW3')
        self._sw_rx_line(c, self.lines)
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
