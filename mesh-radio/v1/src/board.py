# -*- coding: utf-8 -*-
"""Build the placed, unrouted board: outline, rules, net classes, every part
where layout.py puts it, the RF lines (drawn here, locked), keepouts and the
ground plane.

    kd python3 src/board.py out.kicad_pcb [--replace]

The placement is cached in placement.json (committed): layout.py is only
run again with --replace, so a rebuild places every part exactly as before.
"""
import os, sys, json
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, circuit

PLACEMENT = os.path.join(HERE, 'placement.json')
CU = pcb.CU_IDS
SEED = 7

# Vias.  Signal: 0.4 / 0.2 mm.  In a pad (the nRF52840's inner balls and the
# thermal pads): 0.3 / 0.15 mm, ordered filled and capped (POFV).
VIA_SIG = (0.4, 0.2)
VIA_PAD = (0.3, 0.15)

# 50 ohm grounded coplanar waveguide on F.Cu over the In1 ground plane
# (6 layers, JLC06161H-2116B: 0.1164 mm of 2116 prepreg, er 4.16).  A 2-D
# field solve with the 35 um copper and the solder mask (sim/rf/coupler.py)
# gives 49.9 ohm for 0.17 mm with 0.25 mm gaps to the ground pour; the
# closed form in impedance.py ignores both and reads ~8 ohm high on this
# thin dielectric.
RF_W, RF_GAP = 0.17, 0.25

RF_NETS = ['LORA_RFO', 'LORA_TXA', 'LORA_TXB', 'LORA_TXC', 'LORA_TX50', 'PA_DRIVE', 'PA_RFIN',
           'PA_OUT', 'PA_M1', 'PA_M2', 'PA_M3', 'PA_TX', 'ANT_SW', 'ANT', 'RX_SW', 'LNA_INM', 'LNA_AI',
           'LNA_OUT', 'LORA_RFI_P', 'LORA_RFI_N', 'NRF_ANT', 'BLE_50R', 'BLE_T', 'BLE_FEED']
# the missing-antenna detector's coupled line: drawn with the RF lines
# (layout.rf_paths), same width and gap to the pour
RF_EXTRA = ['REFL_CPL']
# the amplifier's supply and the battery path carry up to ~2.5 A in bursts
HEAVY = ['VPA', 'PA_IN', 'PA_LX1', 'PA_LX2', 'BAT_P', 'BATT_PLUS', 'CELL_MINUS', 'PROT_S2',
         'PA_VCC1', 'PA_VCC2', 'PA_V1F', 'PA_V2F']
POWER = ['VSYS', 'VSYS_SW', 'VIN_CHG', 'USB_VBUS', 'USB_5V', 'SOLAR_CONN', 'SOLAR_RAW',
         'DRONE_5V_CONN', 'DRONE_5V_RAW', 'BUCK_SW', '3V3']


# The USB-C's right locating slot sits where Amphenol's drawing puts it,
# 0.298 mm from the shell tab beside it: the drawing's own spacing, not a
# placement choice.  JLCPCB's NPTH-to-copper minimum is 0.2 mm.
RULES = pcb.POFV_RULES + """
(rule "RF coplanar gap"
  (condition "A.NetClass == 'RF' && B.Type == 'Zone'")
  (constraint clearance (min %.2fmm)))
""" % RF_GAP + """
(rule "USB-C locating slot (Amphenol 12401610 drawing)"
  (condition "A.Type == 'Pad' && A.memberOfFootprint('J1') && B.memberOfFootprint('J1')")
  (constraint edge_clearance (min 0.25mm)))
"""


# the QPA9510 paddle's ground vias, mm from its centre (0.55 mm grid)
PA_VIAS = [(x, y) for x in (-0.55, 0, 0.55) for y in (-0.55, 0, 0.55)]


def placement(replace=False):
    if replace or not os.path.exists(PLACEMENT):
        import layout
        pl = layout.place_all()
        json.dump({k: (v if k == '_nodes' else list(v)) for k, v in sorted(pl.items())}, open(PLACEMENT, 'w'), indent=0)
    d = json.load(open(PLACEMENT))
    nodes = d.pop('_nodes', {})
    return {k: tuple(v) for k, v in d.items()}, {k: tuple(v) for k, v in nodes.items()}


def net_classes(b, comps):
    nets = set(n for c in comps for n in c.pins.values() if n)
    # RF lines keep 0.1 mm to pads (the chips' 0.5 mm pitch needs it); their
    # 0.18 mm gap to ground is the top pour's own clearance (RF_GAP)
    pcb.netclass(b, 'RF', sorted(nets & set(RF_NETS + RF_EXTRA)), RF_W, clearance=0.1, via_d=VIA_SIG[0],
                 via_drill=VIA_SIG[1])
    pcb.netclass(b, 'Heavy', sorted(nets & set(HEAVY)), 0.6, clearance=0.1, via_d=0.5, via_drill=0.25)
    pcb.netclass(b, 'Power', sorted(nets & set(POWER)), 0.3, clearance=0.12, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'USB', ['USB_DP', 'USB_DM', 'NRF_DP', 'NRF_DM'], 0.2, clearance=0.12,
                 via_d=VIA_SIG[0], via_drill=VIA_SIG[1])


def build(out, replace=False):
    import layout
    pcbnew.KIID.SeedGenerator(SEED)
    comps = circuit.build()
    pl, nodes = placement(replace)
    b = pcb.new_board(pcb.NLAYERS, out)
    ds = b.GetDesignSettings()
    ds.m_TrackMinWidth = pcb.MM(0.1); ds.m_MinClearance = pcb.MM(0.1)
    ds.m_ViasMinSize = pcb.MM(VIA_PAD[0]); ds.m_MinThroughDrill = pcb.MM(VIA_PAD[1])
    ds.m_ViasMinAnnularWidth = pcb.MM(0.075)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    nc.SetTrackWidth(pcb.MM(0.1)); nc.SetClearance(pcb.MM(0.1))
    nc.SetViaDiameter(pcb.MM(VIA_SIG[0])); nc.SetViaDrill(pcb.MM(VIA_SIG[1]))
    pcb.outline(b)
    pcb.place_components(b, comps, pl)
    net_classes(b, comps)
    # mounting holes: plated, ground
    for k, (x, y) in enumerate(pcb.HOLES):
        fp = pcb.load_fp('MountingHole:MountingHole_2.2mm_M2_Pad')
        fp.SetReference('H%d' % (k + 1)); fp.SetPosition(pcb.P(x, y))
        for p in fp.Pads():
            p.SetNet(pcb.add_net(b, 'GND'))
        fp.Reference().SetLayer(pcbnew.F_Fab)
        b.Add(fp)
    # the amplifier's nine paddle vias (footprints.qpa9510_fp: Qorvo's grid),
    # its heat path into the planes; filled and capped
    c = b.FindFootprintByReference([c.ref for c in comps if c.part == 'QPA9510'][0]).GetPosition()
    for vx, vy in PA_VIAS:
        v = pcb.via(b, c.x / 1e6 - pcb.CX + vx, c.y / 1e6 - pcb.CY + vy, 'GND', d=0.5, drill=0.3)
        v.SetLocked(True)
    # the RF lines (layout.rf_tracks: drawn straight between the chain's pads)
    for net, pts, w in layout.rf_tracks(b, nodes):
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        pcb.track(b, pts, w, pcbnew.F_Cu, net)
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
    # ground: In1 solid everywhere; the other layers are poured after routing
    ex, ey = pcb.HX - 0.3, pcb.HY - 0.3
    full = [(-ex, -ey), (ex, -ey), (ex, ey), (-ex, ey)]
    for gl in [pcb.INNER['gnd']] + ([pcb.INNER['gnd2']] if 'gnd2' in pcb.INNER else []):
        pcb.zone(b, 'GND', pcb.layer_id(gl), full, clearance=0.15, min_width=0.15, priority=0, name='GND plane')
    pcb.hole_keepouts(b, CU)
    # and on F.Cu: no ground pour or via near the antenna (its feed line may pass)
    x0, y0, x1, y1 = layout.ANT_BOX
    pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [pcbnew.F_Cu], tracks=False, vias=True,
                  pads=False, pours=True, name='Bluetooth antenna: no pour')
    for poly, layers, name in layout.keepouts():
        pcb.rule_area(b, poly, [pcb.layer_id(l) for l in layers], tracks=True, vias=True, pads=False,
                      pours=True, name=name)
    pcb.save_board(b, out)
    pcb.write_rules(out, RULES)
    pcb.set_stackup(out, inner_oz=0.5)
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = build(args[0] if args else '/w/out/placed.kicad_pcb', '--replace' in sys.argv)
    print('wrote', out)
