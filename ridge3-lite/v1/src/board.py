# -*- coding: utf-8 -*-
"""Build the placed, unrouted board: outline, rules, parts where
placement.py puts them, power copper (power.py), planes, net classes.

    kd python3 board.py out.kicad_pcb [--repack]

The placement is cached in placement.json (committed): the packer is only
run again with --repack, so a rebuild places every part exactly as before.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, circuit, layout, power

PLACEMENT = os.path.join(HERE, 'placement.json')
LAYERS = {n: pcb.layer_id(n) for n in pcb.CU_NAMES}
CU = list(LAYERS.values())
SEED = 7

# signal via: 0.4 / 0.2 mm (JLCPCB 6-layer standard allows 0.25 / 0.15;
# this keeps a 0.1 mm ring).  Every via is filled and capped (POFV).
VIA_SIG = tuple(float(v) for v in os.environ.get('VIA_SIG', '0.37,0.15').split(','))


def placement(repack=False):
    if repack or not os.path.exists(PLACEMENT):
        import placement as P
        pl, left = P.pack_all()
        if left:
            raise SystemExit('placement: no room for %s' % left)
        json.dump({k: list(v) for k, v in sorted(pl.items())}, open(PLACEMENT, 'w'), indent=0)
    return {k: tuple(v) for k, v in json.load(open(PLACEMENT)).items()}


def net_classes(b, comps):
    nets = set(n for c in comps for n in c.pins.values() if n)
    power_nets = {'VBAT', 'GND'} | {n for n in nets if n.endswith('_SRC') or
                                    (n[:1] == 'M' and n[2:3] == '_' and n[3:] in ('A', 'B', 'C'))}
    supply = {'+5V', '+3V3', '+3V3E', '+3V3_GYRO', 'GVDD', 'GVDD_IN', 'USB_VBUS', 'BEC_SW', 'BEC_BOOT'}
    gate = {n for n in nets if n[:1] == 'M' and ('_GH' in n or '_GL' in n or '_BST' in n)}
    # 0.09 mm: ample for 17.4 V under solder mask (IPC-2221B B4: 0.05 mm
    # below 30 V); the router keeps 0.12 mm from this copper anyway
    pcb.netclass(b, 'Power', sorted(power_nets), 0.3, clearance=0.09, via_d=0.5, via_drill=0.25)
    pcb.netclass(b, 'Supply', sorted(supply & nets), 0.15, clearance=0.09, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'Gate', sorted(gate), 0.15, clearance=0.09, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'USB', ['USB_DP', 'USB_DM'], 0.2, clearance=0.09, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    return {'Power': power_nets, 'Supply': supply, 'Gate': gate}


def build(out, repack=False):
    pcbnew.KIID.SeedGenerator(SEED)
    comps = circuit.build()
    pl = placement(repack)
    b = pcb.new_board(pcb.NLAYERS)
    ds = b.GetDesignSettings()
    ds.m_ViasMinSize = pcb.MM(VIA_SIG[0])
    ds.m_MinThroughDrill = pcb.MM(VIA_SIG[1])
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetViaDiameter(pcb.MM(VIA_SIG[0])); nc.SetViaDrill(pcb.MM(VIA_SIG[1]))
    pcb.outline(b)
    pcb.place_components(b, comps, pl)
    net_classes(b, comps)
    zones, vias, tracks = power.all_copper()
    for net, lay, pts, w in tracks:
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        pcb.track(b, pts, w, LAYERS[lay], net)
        # (GetTracks() is not in insertion order: lock what is new)
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
    for net, lay, pts, w in layout.SPI_TRACKS:
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        pcb.track(b, pts, w, LAYERS[lay], net)
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
    for net, x, y in layout.SPI_VIAS:
        v = pcb.via(b, x, y, net, VIA_SIG[0], VIA_SIG[1])
        v.SetLocked(True)
    for net, lay, pts, w in layout.FC_TRACKS:
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        pcb.track(b, pts, w, LAYERS[lay], net)
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
    for net, lay, poly, pr in zones:
        pcb.zone(b, net, LAYERS[lay], poly, clearance=0.15, min_width=0.15, priority=pr,
                 thermal=False, name='%s %s' % (net, lay))
    for x, y, net, (d, drill) in vias:
        v = pcb.via(b, x, y, net, d, drill)
        v.SetLocked(True)
    # planes: ground on In1, battery on the last inner layer, the full board
    e = pcb.HALF - 0.3
    full = [(-e, -e), (e, -e), (e, e), (-e, e)]
    pcb.zone(b, 'GND', pcbnew.In1_Cu, full, clearance=0.15, min_width=0.15, priority=0, name='GND plane')
    pcb.zone(b, 'VBAT', pcb.layer_id(pcb.INNER['vbat']), full, clearance=0.15, min_width=0.15, priority=0,
             name='VBAT plane')
    pcb.hole_keepouts(b, CU)
    if layout.FLAG:
        # the flag: a ground plate on its side, and no via or track through it
        x0, y0, x1, y1 = layout.flag_box()
        cu = pcbnew.F_Cu if layout.FLAG['side'] == 'T' else pcbnew.B_Cu
        pcb.zone(b, 'GND', cu, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], clearance=0.2, min_width=0.15,
                 priority=9, thermal=False, name='flag plate')
        k0, k1, k2, k3 = layout.flag_box(0.25)
        pcb.rule_area(b, [(k0, k1), (k2, k1), (k2, k3), (k0, k3)], [cu], tracks=True, vias=True, pads=False,
                      pours=False, name='flag keepout')
    b.Save(out)
    pcb.write_rules(out, pcb.POFV_RULES)
    return out


if __name__ == '__main__':
    out = build(sys.argv[1] if len(sys.argv) > 1 else '/w/out/placed.kicad_pcb', '--repack' in sys.argv)
    print('wrote', out)
