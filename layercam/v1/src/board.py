# -*- coding: utf-8 -*-
"""Build a placed, unrouted board: outline, parts, net classes, planes and
keepouts.  Routing (route.py), the fills and the artwork come after, in
pipeline.py.

    python3 board.py main|ring|usb OUT.kicad_pcb

Main board layers (JLCPCB 6-layer, JLC06161H-3313):
    F.Cu    the back face: SoC, flash, power stage; signals
    In1.Cu  ground plane, unbroken
    In2.Cu  signals (the long runs round the window), ground fill
    In3.Cu  power planes: 0.9 V under the SoC, 3.3 V, 1.8 V, DDR, 5 V
    In4.Cu  ground plane, unbroken
    B.Cu    the front face: Wi-Fi, connectors, SoC decoupling; signals
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import pcbnew
import pcb, circuit, placer, geometry as G

# net classes: width for the current each carries
POWER = {
    # no wider than the finest pins each net lands on, or the router cannot
    # reach them: 0.25 at the EA3036C's 0.4 mm pitch, 0.2 at the RV1106's
    # 0.35 mm (VCC_DDR, VCC_1V8); every rail here carries 1 A or less
    'main': {'VSYS': 0.25, 'SW_0V9': 0.5, 'LX_3V3': 0.25, 'VCC_DDR': 0.2, 'LX_DDR': 0.25,
             'VCC_1V8': 0.2, 'LX_1V8': 0.25, 'VWIFI': 0.4, 'SW_WIFI': 0.4, 'WIFI_LX': 0.4,
             'WIFI_VLDO': 0.4, 'LED_K': 0.4, 'IRCUT_1': 0.2, 'IRCUT_2': 0.2},
    'ring': {'VSYS': 0.4, 'LED_K': 0.4, 'STR1_A': 0.3, 'STR2_A': 0.3, 'STR3_A': 0.3,
             'STR1_M': 0.3, 'STR2_M': 0.3, 'STR3_M': 0.3},
    'usb': {'VSYS': 0.4},
}
PLANE_NETS = {'main': ('GND', 'VDD_0V9', 'VCC_3V3'), 'usb': ('GND',), 'ring': ()}
# boards whose big parts' plane pins get their vias from the router (it
# leaves gaps between them; vias placed beforehand, one per pin, walled the
# pins next to them in): the plane nets are routed, to the planes
ROUTER_PLANE_VIAS = set()        # tried for 'main': 82 left unrouted against 52
# differential pairs (width, gap) for 100 ohm (MIPI) and 90 ohm (USB) on
# the outer layers over PCBWay's 0.12 mm prepreg, centred in the etch
# tolerance (sim/impedance.md: 102 and 90 ohm on the main board, 92 ohm on
# the 2-layer USB board).  The main board's USB gap is 0.13, not the
# 0.127 minimum: a coupled bend must not round to under the rule
DIFF = {'main': {'MIPI': (['CSI_D0P', 'CSI_D0N', 'CSI_D1P', 'CSI_D1N', 'CSI_CKP', 'CSI_CKN'], 0.12, 0.15),
                 'USB': (['USB_DP', 'USB_DM'], 0.15, 0.13)},
        'ring': {}, 'usb': {'USB': (['USB_DP', 'USB_DM'], 0.25, 0.13)}}


# the antenna feed: 50 ohm microstrip on B over In4 (sim/impedance.md)
RF_W = 0.18


def build(board, path, rounds=12):
    """Build the board; a small part that ends up with a plane pad and no
    room for its via is moved: the board is built again with that spot
    barred to it (placer.place's `avoid`), up to `rounds` times."""
    avoid = {}
    for k in range(rounds):
        b, failed, stuck = _build(board, path, avoid)
        if not stuck:
            break
        print('  no via room for %s: placing again' % ' '.join(sorted(stuck)))
        for ref in stuck:
            fp = b.FindFootprintByReference(ref)
            avoid.setdefault(ref, []).append(placer.courtyard(fp, 'B' if fp.IsFlipped() else 'F'))
    # a part left unplaced sits at the origin (in the lens window on the
    # main board): never route such a board
    if failed or stuck:
        raise SystemExit('placement failed: no room for %s, no via room for %s'
                         % (' '.join(failed) or '-', ' '.join(sorted(stuck)) or '-'))
    return b, failed


def _build(board, path, avoid):
    pcbnew.KIID.SeedGenerator({'main': 11, 'ring': 12, 'usb': 13}[board])
    pcb.configure(board)
    layout = __import__('layout_' + board)
    b = pcb.new_board(path)
    pcb.outline(b)
    comps = circuit.build(board)
    fixed = layout.FIXED
    pl = {c.ref: fixed.get(c.ref, (0.0, 0.0, 0, 'F')) for c in comps}
    pcb.place_components(b, comps, pl)
    if hasattr(layout, 'zones'):
        layout.zones(b)
    # copper drawn first (pairs, the USB board's VBUS), then the fixed
    # parts' plane vias, then the small parts round them, then theirs
    import power
    manual = power.draw(b)
    nets = PLANE_NETS[board]
    allowed = layout.plane_polys() if hasattr(layout, 'plane_polys') else None
    inward = getattr(layout, 'INWARD', ())
    ring = layout.via_ring() if hasattr(layout, 'via_ring') else None
    small = {c.ref for c in comps if placer.is_small(c) and c.ref not in fixed}
    big = {c.ref for c in comps} - small
    # a fine-pitch chip's pins (layout.ESCAPE: its ref, a smaller via, the
    # band's clearance, the stub width) fan out at its own rules
    esc = getattr(layout, 'ESCAPE', None)
    d1, f1 = power.fanout(b, nets=nets, done_pads=manual, allowed=allowed, inward=inward,
                          refs=big - ({esc['ref']} if esc else set()),
                          pins=board not in ROUTER_PLANE_VIAS, ring=ring)
    if esc:
        d0, f0 = power.fanout(b, nets=nets, done_pads=manual, allowed=allowed, inward=inward, refs={esc['ref']},
                              ring=ring, via=esc['via'], clr=esc['clr'], stub_w=lambda n: esc['w'])
        d1, f1 = d1 + d0, f1 + f0
    failed = placer.place(b, comps, layout, layout.height, avoid)
    if failed:
        print('  NO ROOM for: %s' % ' '.join(failed))
    d2, f2 = power.fanout(b, nets=nets, done_pads=manual, allowed=allowed, inward=inward, refs=small, ring=ring)
    if hasattr(layout, 'escapes'):
        # a fine-pitch chip's signal pins that leave its face: a stub and a
        # via each, laid out together before routing (locked, or Freerouting
        # drops a via that has one connection so far)
        for ref, esc in layout.escapes(b).items():
            # the pins squeezed between two other escapes first (straight
            # out), the rest after, as thin as the rules near the pins allow
            lean = power.squeezed_first(b.FindFootprintByReference(ref), set(esc))
            e = getattr(layout, 'ESCAPE', {})
            d3, f3 = power.fanout(b, nets=esc, refs={ref}, ring=ring, lean=lean, via=e.get('via'),
                                  clr=e.get('clr'), stub_w=lambda n: e.get('w', 0.12))
            print('  %s escapes: %d%s' % (ref, d3, ('; none for ' + ' '.join(f3)) if f3 else ''))
            # a small part whose pad stands where an escape via must go
            # moves, as one with no via room does
            f2 = f2 + [f.split('(pad ')[1].rstrip(')') for f in f3 if '(pad ' in f]
    print('  plane vias: %d%s' % (d1 + d2, ('; NO SPOT for ' + ' '.join(f1 + f2)) if f1 + f2 else ''))
    for w in sorted(set(POWER[board].values())):
        group = [n for n, x in POWER[board].items() if x == w]
        pcb.netclass(b, ('Power_%g' % w).replace('.', '_'), group, w)
    if board == 'main':
        pcb.netclass(b, 'RF', ['ANT_FEED', 'ANT'], RF_W)
    for name, (nets, w, gap) in DIFF[board].items():
        pcb.netclass(b, name, nets, w, diff_w=w, diff_gap=gap)
    pcb.rule_area_shape(b, pcb.edge_band(), pcb.cu_layers(), name='edge clearance')
    if hasattr(layout, 'escape_area'):
        # where the escape band's own clearance applies (pcb.write_rules)
        pcb.rule_area_shape(b, layout.escape_area(), pcb.cu_layers(), name='escape band', tracks=False, vias=False)
    pcbnew.SaveBoard(path, b)
    pcb.write_rules(path)
    stuck = {f.split('.')[0] for f in f2} & small
    return b, failed, stuck


if __name__ == '__main__':
    bd = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else '/tmp/layercam-%s-placed.kicad_pcb' % bd
    build(bd, out)
    print('wrote', out)
