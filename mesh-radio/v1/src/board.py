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
# (JLC04161H-7628: 0.21 mm of 7628 prepreg, er 4.4): 0.36 mm track with
# 0.18 mm gaps to the ground pour is 50.5 ohm (src/impedance.py).
RF_W, RF_GAP = 0.36, 0.18

RF_NETS = ['LORA_RFO', 'LORA_TXA', 'LORA_TXB', 'LORA_TXC', 'LORA_TX50', 'PA_DRIVE', 'PA_RFIN',
           'PA_OUT', 'PA_M1', 'PA_M2', 'PA_M3', 'PA_TX', 'ANT_SW', 'ANT', 'RX_SW', 'LNA_INM', 'LNA_AI',
           'LNA_OUT', 'LORA_RFI_P', 'LORA_RFI_N', 'NRF_ANT', 'BLE_50R', 'BLE_T', 'BLE_FEED']
# the amplifier's supply and the battery path carry up to ~2.5 A in bursts
HEAVY = ['VPA', 'PA_IN', 'PA_LX1', 'PA_LX2', 'BAT_P', 'BATT_PLUS', 'CELL_MINUS', 'PROT_S2',
         'PA_VCC1', 'PA_VCC2', 'PA_V1F', 'PA_V2F']
POWER = ['VSYS', 'VSYS_SW', 'VIN_CHG', 'USB_VBUS', 'USB_5V', 'SOLAR_CONN', 'SOLAR_RAW',
         'DRONE_5V_CONN', 'DRONE_5V_RAW', 'BUCK_SW', '3V3']


def placement(replace=False):
    if replace or not os.path.exists(PLACEMENT):
        import layout
        pl = layout.place_all()
        json.dump({k: list(v) for k, v in sorted(pl.items())}, open(PLACEMENT, 'w'), indent=0)
    return {k: tuple(v) for k, v in json.load(open(PLACEMENT)).items()}


def net_classes(b, comps):
    nets = set(n for c in comps for n in c.pins.values() if n)
    pcb.netclass(b, 'RF', sorted(nets & set(RF_NETS)), RF_W, clearance=RF_GAP, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'Heavy', sorted(nets & set(HEAVY)), 0.6, clearance=0.15, via_d=0.5, via_drill=0.25)
    pcb.netclass(b, 'Power', sorted(nets & set(POWER)), 0.3, clearance=0.12, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'USB', ['USB_DP', 'USB_DM', 'NRF_DP', 'NRF_DM'], 0.2, clearance=0.12,
                 via_d=VIA_SIG[0], via_drill=VIA_SIG[1])


def build(out, replace=False):
    import layout
    pcbnew.KIID.SeedGenerator(SEED)
    comps = circuit.build()
    pl = placement(replace)
    b = pcb.new_board(pcb.NLAYERS)
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
    # the RF lines (layout.rf_tracks: drawn straight between the chain's pads)
    for net, pts, w in layout.rf_tracks(b):
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        pcb.track(b, pts, w, pcbnew.F_Cu, net)
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
    # ground: In1 solid everywhere; F, In2 and B are poured after routing
    ex, ey = pcb.HX - 0.3, pcb.HY - 0.3
    full = [(-ex, -ey), (ex, -ey), (ex, ey), (-ex, ey)]
    pcb.zone(b, 'GND', pcbnew.In1_Cu, full, clearance=0.15, min_width=0.15, priority=0, name='GND plane')
    pcb.hole_keepouts(b, CU)
    for poly, layers, name in layout.keepouts():
        pcb.rule_area(b, poly, [pcb.layer_id(l) for l in layers], tracks=True, vias=True, pads=False,
                      pours=True, name=name)
    b.Save(out)
    pcb.write_rules(out, pcb.POFV_RULES)
    pcb.set_stackup(out, inner_oz=0.5)
    return out


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    out = build(args[0] if args else '/w/out/placed.kicad_pcb', '--replace' in sys.argv)
    print('wrote', out)
