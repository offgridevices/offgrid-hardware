# -*- coding: utf-8 -*-
"""The stack as one thermal model: the ESC below, the FC above, their parts.

Builds the two boards' grids (thermal.py), joins them across the gap, gives
each part that heats or has a temperature limit a node, and turns an
operating point into the heat vector.  Temperatures come back per part:
a junction node's temperature, or the mean of the copper under its pads.
"""
import numpy as np
import copper, thermal, copperloss, losses, data, dcflow

CH = (1, 2, 3, 4)
PH = 'ABC'
BOARD = ('ESC', 'FC')


def outer(c, ref):
    """Index of the copper layer a part sits on."""
    return 0 if c.parts[ref]['side'] == 'top' else len(c.layers) - 1


def pad_cells(c, ref, nets=None):
    """Fine cells of a part's pads on its own side (optionally only some nets)."""
    li = outer(c, ref)
    cells = [T['cells'][li] for (r, n), T in c.terminals.items()
             if r == ref and li in T['cells'] and (nets is None or n in nets)]
    return (np.concatenate(cells) if cells else np.zeros(0, int)), li


class StackModel:
    def __init__(self, air, T_amb, h=0.5, gap=None, out='sim/out'):
        self.ce, self.cf = copper.extract('esc'), copper.extract('fc')
        self.ge, self.gf = thermal.Grid(self.ce, h), thermal.Grid(self.cf, h)
        self.T_amb, self.air = T_amb, air
        gap = gap or data.STACK['gap']
        self.st = thermal.Stack([self.ge, self.gf], [gap], air, T_amb)
        g = self.ge
        self.units = coarse_units(self.ce, out, g.f, g.ny, g.nx)
        self.fc_units = fc_copper(self.cf, self.gf)
        self.parts = {}                      # name -> dict(board, ref, node | cells, limit...)
        ce, cf = self.ce, self.cf
        for n in CH:
            for p in PH:
                for s in 'HL':
                    ref = 'Q%d%s%s' % (n, p, s)
                    drain = 'VBAT' if s == 'H' else 'M%d_%s' % (n, p)
                    cells, li = pad_cells(ce, ref, [drain])
                    self._junction(0, ref, cells, li, data.FET['rth_ch_c'], data.FET['c_th'])
            self._junction(0, 'U_GD%d' % n, *pad_cells(ce, 'U_GD%d' % n, ['GND']),
                           data.DRIVER['rth_jb'], 0.02)
            self._junction(0, 'U_ESC%d' % n, *pad_cells(ce, 'U_ESC%d' % n), data.MCU_ESC['rth_jb'], 0.02)
            self._pads(0, 'R_SH%d' % n)
            self._pads(0, 'U_CS%d' % n)
        # rev 1's gate-drive LDO and 3.3 V buck (rev 2 has neither), its
        # stack connector (rev 2: the lead is soldered)
        if data.GATE_LDO:
            self._junction(0, 'U_GVDD', *pad_cells(ce, 'U_GVDD'), data.GATE_LDO['rth_jb'], 0.02)
        if data.ESC_BUCK:
            self._junction(0, 'U_BUCK', *pad_cells(ce, 'U_BUCK'), data.ESC_BUCK['rth_jb'], 0.02)
            self._pads(0, 'L1')
        if not data.LEAD['soldered']:
            self._pads(0, 'J_FC')
        for ref, key in (('U_BUCK5', 'LMR38020F'), ('U_BUCK9', 'LM76003'), ('U_LDO', 'TLV76733'),
                         ('U_FC', 'G473'), ('U_OSD', 'AT7456E')):
            self._junction(1, ref, *pad_cells(cf, ref), getattr(data, key)['rth_jb'], 0.03)
        for ref in ('U_IMU', 'U_FLASH', 'L_5V', 'L_9V', 'J_ESC', 'J_HD', 'D_TVS'):
            self._pads(1, ref)
        # capacitors whose dielectric has a lower temperature limit than the board
        import design
        for bi, c in ((0, ce), (1, cf)):
            for cp in design.circuit().build(c.board):
                if cp.part in data.CAPS:
                    self._pads(bi, cp.ref, kind=cp.part)
        self.solver = thermal.Solver(self.st)
        self.n = self.solver.G.shape[0]

    # ------------------------------------------------------------- parts
    def _junction(self, bi, ref, cells, li, R, C):
        node = self.st.junction(bi, ref, cells, li, R, C)
        self.parts[BOARD[bi] + ' ' + ref] = dict(board=bi, ref=ref, node=node, li=li)

    def _pads(self, bi, ref, kind=None):
        c = (self.ce, self.cf)[bi]
        g = (self.ge, self.gf)[bi]
        cells, li = pad_cells(c, ref)
        if not cells.size:
            return
        (iy, ix), w = g.cells(cells)
        ids = g.ids[li, iy, ix]
        ok = ids >= 0
        self.parts[BOARD[bi] + ' ' + ref] = dict(board=bi, ref=ref, nodes=self.st.off[bi] + ids[ok], w=w[ok] / w[ok].sum(),
                               li=li, kind=kind)

    def temp(self, T, name):
        p = self.parts[name]
        if 'node' in p:
            return float(T[p['node']])
        return float(np.dot(T[p['nodes']], p['w']))

    def put(self, P, name, watts):
        p = self.parts[name]
        if 'node' in p:
            P[p['node']] += watts
        else:
            np.add.at(P, p['nodes'], watts * p['w'])

    # ------------------------------------------------------------- heat
    def heat(self, op, T=None):
        """Heat vector for an operating point; temperatures T (if given) set
        the FETs' on-resistance and the copper's resistance.

        op['esc']: V, f, dead, I {n: phase A}, D {n: duty}, sw (switching energies)
        op['fc']:  i5, i9 (rail currents, A), i_lead (A in the stack lead's VBAT wire)
        """
        P = np.zeros(self.n)
        e = op.get('esc')
        if e:
            V, f = e['V'], e['f']
            for n in CH:
                I, D = e['I'][n], e['D'][n]
                Tj = {p + s: (self.temp(T, 'ESC Q%d%s%s' % (n, p, s)) if T is not None else 100.0)
                      for p in PH for s in 'HL'}
                for k, w in losses.esc_channel(I, D, V, f, e['dead'], Tj, e['sw']).items():
                    name = {'shunt': 'ESC R_SH%d' % n, 'driver': 'ESC U_GD%d' % n}.get(k, 'ESC Q%d%s' % (n, k))
                    self.put(P, name, w)
                self.put(P, 'ESC U_ESC%d' % n, data.MCU_ESC['p_run'])
                self.put(P, 'ESC U_CS%d' % n, data.CSA['p'])
            if data.GATE_LDO:
                self.put(P, 'ESC U_GVDD', (V - data.GVDD) * losses.gvdd_current(f))
            if data.ESC_BUCK:
                p3 = data.ESC_3V3_LOAD * 3.3
                self.put(P, 'ESC U_BUCK', p3 * (1 / data.ESC_BUCK['eff'] - 1))
                self.put(P, 'ESC L1', data.ESC_3V3_LOAD ** 2 * data.INDUCTORS['L1']['dcr'])
            self._copper(P, copperloss.loss_map(self.units, e['I'], e['D']), T)
        fc = op.get('fc')
        if fc:
            pin, parts = losses.fc_power(fc['i5'], fc['i9'])
            for ref, key, rail in (('U_BUCK5', 'L_5V', 'i5'), ('U_BUCK9', 'L_9V', 'i9')):
                pl = fc[rail] ** 2 * data.INDUCTORS[key]['dcr']
                self.put(P, 'FC ' + ref, max(parts[ref] - pl, 0.0))
                self.put(P, 'FC ' + key, pl)
            self.put(P, 'FC U_LDO', parts['U_LDO'])
            self.put(P, 'FC U_FC', data.MCU_FC['p_run'])
            self.put(P, 'FC U_OSD', data.OSD['p'])
            self.put(P, 'FC U_IMU', data.GYRO['p'])
            # the stack lead's two power contacts at each end, and the HD lead's
            ist = fc.get('i_lead', 0.0)
            self.put(P, 'FC J_ESC', 2 * ist ** 2 * data.STACK_CONN['r_contact'])
            self.put(P, 'ESC J_FC', 2 * ist ** 2 * data.STACK_CONN['r_contact'])
            self.put(P, 'FC J_HD', 2 * fc['i9'] ** 2 * data.HD_CONN['r_contact'])
            scale = dict(VBAT=ist, **{'+9V': fc['i9'], 'BUCK9_SW': fc['i9'], '+5V': fc['i5'], 'BUCK5_SW': fc['i5']})
            W = sum(self.fc_units[k][0] * (scale[k] / self.fc_units[k][1]) ** 2 for k in self.fc_units)
            self._copper(P, W, T, board=1)
        return P

    def _copper(self, P, W, T, board=0):
        """W: loss per cell of this board's thermal grid, per layer (W at 20 C)."""
        g = (self.ge, self.gf)[board]
        o = self.st.off[board]
        for li in range(g.L):
            Wc = W[li]
            ids = g.ids[li]
            ok = ids >= 0
            scale = 1.0
            if T is not None:
                Tc = T[o + ids[ok]]
                scale = 1 + dcflow.ALPHA * (Tc - 20.0)
            P[o + ids[ok]] += Wc[ok] * scale

    def summary(self, T):
        return {k: self.temp(T, k) for k in self.parts}


# The FC's supply copper at its full load (20 C): rail -> (loss map, the
# current it was solved at).  The 5 V load is split over the pads that
# carry it in a build: receiver, camera, the spare 5 V pad, and the 3.3 V LDO.
FC_PATHS = {
    'VBAT': ({'J_ESC': 1.55, 'U_BUCK9': -0.98, 'U_BUCK5': -0.57}, 1.55),
    '+9V': ({'L_9V': 2.0, 'J_HD': -2.0}, 2.0),
    'BUCK9_SW': ({'U_BUCK9': 2.0, 'L_9V': -2.0}, 2.0),
    '+5V': ({'L_5V': 2.0, 'P_RX5V': -0.5, 'P_CAM5V': -0.5, 'P_5V': -0.835, 'U_LDO': -0.165}, 2.0),
    'BUCK5_SW': ({'U_BUCK5': 2.0, 'L_5V': -2.0}, 2.0),
}
_fc = {}
_esc = {}


def fc_copper(c, g):
    """The FC's supply-copper loss maps on its thermal grid g, computed once."""
    key = (c.path, g.f)
    if key not in _fc:
        out = {}
        for net, (cur, ref) in FC_PATHS.items():
            s = dcflow.solve(c, net, cur, T=20.0)
            W = dcflow.maps(c, s)['W']
            out[net] = (copperloss.coarse({'W': W}, g.f, g.ny, g.nx)['W'], ref)
        _fc[key] = out
        dcflow.forget()
    return _fc[key]


def coarse_units(c, out, f, ny, nx):
    """The ESC's 1 A copper maps on the thermal grid, computed once."""
    key = (c.path, f)
    if key not in _esc:
        _esc[key] = copperloss.coarse(copperloss.unit_maps(c, out), f, ny, nx)
    return _esc[key]
