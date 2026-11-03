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
if os.environ.get('NO_HEADER'):
    PLACEMENT = PLACEMENT.replace('.json', '_nohdr.json')
if pcb.LEN != pcb.DEFAULT_LEN:
    # a trial at another board length places afresh, in its own file (the
    # committed placement is the default length's; until 20 Oct such trials
    # silently reused it on the longer outline)
    PLACEMENT = PLACEMENT.replace('.json', '_%g.json' % pcb.LEN)
# a trial run may name its own placement file (several routes at once)
PLACEMENT = os.environ.get('PLACEMENT_FILE', PLACEMENT)
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
# the battery and amplifier current path's track width (mm); an
# environment override is for routing trials only
# the default net class: track and gap (JLCPCB's 6-layer minimum is 0.09 mm);
# an environment override is for routing trials only
SIG = float(os.environ.get('SIG', 0.1))
FAB_MIN = 0.09   # JLCPCB's 6-layer minimum track and gap (mm): the DRC limit
HEAVY_W = float(os.environ.get('HEAVY_W', 0.6))
POWER_W = 0.3
# The routers lay these nets thin (a 0.6 or 0.3 mm track cannot reach a
# 0.4 mm-pitch ball or a 0.5 mm-pitch QFN pin: with them at full width,
# 24 of their connections failed even with every signal left out); the
# finish widens every stretch that has room to HEAVY_W / POWER_W
# (pipeline.fatten), and keeps thin only the necks at fine-pitch pins.
HEAVY_ROUTE_W, POWER_ROUTE_W = 0.3, 0.2
SENSE_W = 0.6     # the protection FETs to the current-sense shunt (drawn with the board, B.Cu)
HEAVY = ['VPA', 'PA_IN', 'PA_LX1', 'PA_LX2', 'BAT_P', 'BATT_PLUS', 'CELL_MINUS', 'PROT_S2',
         'PA_VCC1', 'PA_VCC2', 'PA_V1F', 'PA_V2F']
POWER = ['VSYS', 'VSYS_SW', 'VIN_CHG', 'USB_VBUS', 'USB_5V', 'SOLAR_CONN', 'SOLAR_RAW',
         'DRONE_5V_CONN', 'DRONE_5V_RAW', 'BUCK_SW']
# the 3.3 V rail: at most about 0.15 A (the nRF52840, the SX1262 at +20 dBm,
# the LNA, pull-ups), to dozens of pins; 0.15 mm (0.5 oz inner: about
# 0.35 A for a 10 C rise, IPC-2152) and ground-poured round it
RAIL = ['3V3']


# The USB-C's right locating slot sits where Amphenol's drawing puts it,
# 0.298 mm from the shell tab beside it: the drawing's own spacing, not a
# placement choice.  JLCPCB's NPTH-to-copper minimum is 0.2 mm.
RULES = pcb.POFV_RULES + """
# JLCPCB's finest gap on 6 layers is 0.09 mm: the check allows it between
# tracks, vias and pads (Freerouting's necks), while the net classes keep
# 0.1 mm for the routers (pours keep their own clearances); later rules win
(rule "fab minimum clearance"
  (condition "A.Type != 'Zone' && B.Type != 'Zone'")
  (constraint clearance (min %.2fmm)))
""" % FAB_MIN + """
(rule "RF coplanar gap"
  (condition "A.NetClass == 'RF' && B.Type == 'Zone'")
  (constraint clearance (min %.2fmm)))
""" % RF_GAP + """
(rule "RF gap to other nets' tracks and vias"
  (condition "A.NetClass == 'RF' && A.Type == 'Track' && (B.Type == 'Track' || B.Type == 'Via') && B.NetClass != 'RF' && B.NetName != 'GND'")
  (constraint clearance (min %.2fmm)))
""" % RF_GAP + """(rule "gap pad: ground vias only"
  (condition "A.Type == 'Via' && A.NetName != 'GND' && A.intersectsArea('gap pad')")
  (constraint disallow via))
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
    # (0.25 since 3 Nov, the routers' gap to them: sim/rf R5; the DRC holds
    # tracks and vias of other nets to it, pads to the fab minimum, RULES)
    pcb.netclass(b, 'RF', sorted(nets & set(RF_NETS + RF_EXTRA)), RF_W, clearance=RF_GAP, via_d=VIA_SIG[0],
                 via_drill=VIA_SIG[1])
    pcb.netclass(b, 'Heavy', sorted(nets & set(HEAVY)), HEAVY_ROUTE_W, clearance=0.1, via_d=0.5, via_drill=0.25)
    pcb.netclass(b, 'Power', sorted(nets & set(POWER)), POWER_ROUTE_W, clearance=0.12, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'Rail', sorted(nets & set(RAIL)), 0.15, clearance=0.1, via_d=VIA_SIG[0], via_drill=VIA_SIG[1])
    pcb.netclass(b, 'USB', ['USB_DP', 'USB_DM', 'NRF_DP', 'NRF_DM'], 0.2, clearance=0.12,
                 via_d=VIA_SIG[0], via_drill=VIA_SIG[1])


def npth_keepouts(b, edge=0.3, margin=0.08):
    """No track or via within the edge clearance of a part's unplated hole
    (the USB-C's pegs count as board edge): a ring round each, all layers."""
    k = 0
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetAttribute() != pcbnew.PAD_ATTRIB_NPTH:
                continue
            q = p.GetPosition()
            r = max(p.GetDrillSize().x, p.GetDrillSize().y) / 2e6 + edge + margin
            pcb.rule_area(b, pcb.circle_poly(q.x / 1e6 - pcb.CX, q.y / 1e6 - pcb.CY, r), CU,
                          tracks=True, vias=True, pads=False, pours=False, name='unplated hole keepout')
            k += 1
    return k


def build(out, replace=False):
    import layout
    pcbnew.KIID.SeedGenerator(SEED)
    comps = circuit.build()
    pl, nodes = placement(replace)
    b = pcb.new_board(pcb.NLAYERS, out)
    ds = b.GetDesignSettings()
    # the fab's minimum (JLCPCB 6 layers: 0.09 mm track and gap): Freerouting
    # necks tracks down at small pins, and the routers keep 0.1 elsewhere
    ds.m_TrackMinWidth = pcb.MM(FAB_MIN); ds.m_MinClearance = pcb.MM(FAB_MIN)
    ds.m_ViasMinSize = pcb.MM(VIA_PAD[0]); ds.m_MinThroughDrill = pcb.MM(VIA_PAD[1])
    ds.m_ViasMinAnnularWidth = pcb.MM(0.075)
    nc = ds.m_NetSettings.GetDefaultNetclass()
    # the routers keep 0.1 mm (a router via 0.09 mm from copper puts its hole
    # 0.19 mm from it, under the fab's 0.2); the DRC allows the fab's 0.09
    # (RULES 'fab minimum clearance')
    nc.SetTrackWidth(pcb.MM(SIG)); nc.SetClearance(pcb.MM(SIG))
    nc.SetViaDiameter(pcb.MM(VIA_SIG[0])); nc.SetViaDrill(pcb.MM(VIA_SIG[1]))
    pcb.outline(b)
    pcb.place_components(b, comps, pl)
    net_classes(b, comps)
    # mounting holes: plated, ground
    for k, (x, y) in enumerate(pcb.HOLES):
        fp = pcb.load_fp(pcb.HOLE_FP)
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
    # the cell current's sense loop: the protection FETs' source pins
    # straight into the 15 mR shunt beside them on the bottom, short and
    # wide, no layer change (until 3 Nov it dropped to In1 and back: 18 mR
    # in series with the shunt halved the protector's trip, sim/shorts)
    fet = [c.ref for c in comps if c.part == 'SSM10N954L']
    shunt = [c.ref for c in comps if c.part == 'R15m']
    if fet and shunt:
        mm_ = lambda p: (p.GetPosition().x / 1e6 - pcb.CX, p.GetPosition().y / 1e6 - pcb.CY)
        f = b.FindFootprintByReference(fet[0]); r = b.FindFootprintByReference(shunt[0])
        rx, ry = mm_([p for p in r.Pads() if p.GetNetname() == 'PROT_S2'][0])
        sp = sorted((mm_(p) for p in f.Pads() if p.GetNetname() == 'PROT_S2'), key=lambda q: (round(q[1], 2), -q[0]))
        ends = [sp[0], sp[-1]]                      # the outer pin of each row (its neighbour joins it, join_pads)
        before = set(t.m_Uuid.AsString() for t in b.GetTracks())
        for px, py in ends:
            pcb.track(b, [(px, py), (rx, py), (rx, ry)] if abs(py - ry) > 0.05 else [(px, py), (rx, ry)],
                      SENSE_W, pcbnew.B_Cu, 'PROT_S2')
        for t in b.GetTracks():
            if t.m_Uuid.AsString() not in before:
                t.SetLocked(True)
    # ground: In1 solid everywhere; the other layers are poured after routing
    ex, ey = pcb.HX - 0.3, pcb.HY - 0.3
    full = [(-ex, -ey), (ex, -ey), (ex, ey), (-ex, ey)]
    for gl in [pcb.INNER['gnd']] + ([pcb.INNER['gnd2']] if 'gnd2' in pcb.INNER else []):
        pcb.zone(b, 'GND', pcb.layer_id(gl), full, clearance=0.15, min_width=0.15, priority=0, name='GND plane')
    pcb.hole_keepouts(b, CU)
    npth_keepouts(b)
    # and on F.Cu: no ground pour or via near the antenna (its feed line may pass)
    x0, y0, x1, y1 = layout.ANT_BOX
    pcb.rule_area(b, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], [pcbnew.F_Cu], tracks=False, vias=True,
                  pads=False, pours=True, name='Bluetooth antenna: no pour')
    # the gap pad (layout.GAP_PAD): bare ground copper on the bottom, no
    # solder mask, for a 10 x 10 mm thermal pad to a metal wall.  No tracks on
    # B.Cu there (the ground pour after routing fills it); vias only of ground
    # (RULES 'gap pad: ground vias only')
    gx0, gy0, gx1, gy1 = layout.GAP_PAD
    gpoly = [(gx0, gy0), (gx1, gy0), (gx1, gy1), (gx0, gy1)]
    pcb.rule_area(b, gpoly, [pcbnew.B_Cu], tracks=True, vias=False, pads=False, pours=False, name='gap pad')
    sh = pcbnew.PCB_SHAPE(b)
    sh.SetShape(pcbnew.SHAPE_T_RECT); sh.SetFilled(True); sh.SetLayer(pcbnew.B_Mask); sh.SetWidth(0)
    sh.SetStart(pcb.P(gx0, gy0)); sh.SetEnd(pcb.P(gx1, gy1))
    b.Add(sh)
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
